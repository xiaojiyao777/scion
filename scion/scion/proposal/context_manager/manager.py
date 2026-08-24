"""Direct V3 proposal-context assembly.

The context manager has one job: expose the smallest complete set of research
facts needed by the two proposal calls.  It does not steer the search through
quality gates, retry advice, portfolio controls, or host-generated repairs.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from scion.config.problem import ProblemSpec
from scion.contract.patch_paths import matches_config_pattern
from scion.core.models import (
    Branch,
    ChampionState,
    ExperimentStage,
    HypothesisProposal,
    StepRecord,
    patch_file_changes,
)
from scion.core.paths import normalize_relative_patch_path
from scion.core.research_history import provider_research_history
from scion.core.research_input import normalize_research_input
from scion.measurement.consumer_view import measurement_consumer_view
from scion.problem.providers import (
    active_subject_code_constraints_payload,
    project_prior_research_observation,
    resolve_prior_research_observation_provider,
    resolve_solver_design_prompt_provider,
)
from scion.proposal.context.problem_adapter import (
    _build_operator_interface_spec,
    _build_problem_object,
    _build_problem_summary,
    _build_solver_mechanics,
    _get_adapter_problem_spec,
)
from scion.proposal.context.surfaces import (
    _find_research_surface,
    _get_research_surfaces,
    _include_operator_files_for_research_code,
    _is_solver_design_context_surface,
    _solver_design_surface_names,
    surface_action_allowed,
    surface_target_files,
)
from scion.proposal.solver_design_guidance import (
    RENDERER_INPUTS_KEY,
    SOLVER_DESIGN_GUIDANCE_KEY,
    materialize_solver_design_prompt_guidance,
)

from .code_context import (
    EDITABLE_SOURCE_CONTEXT_KEY,
    _build_editable_source_context,
    _read_champion_research_code,
)
from .history_projection import (
    proposal_pre_protocol_observations,
    proposal_screening_history,
    screening_eval_stats,
)
from .io import (
    _expand_surface_targets_for_champion,
    _expand_surface_targets_for_root,
    _list_branch_surface_files,
    _list_champion_operator_files,
    _list_champion_surface_files,
    _read_branch_code_projection,
)

_MEASUREMENT_PRIVATE_FIELDS = frozenset(
    {
        "pair_evidence",
        "pair_rows",
        "raw_pair",
        "raw_pair_rows",
        "raw_calibration",
        "raw_calibration_pair_rows",
        "calibration_pair",
        "calibration_ref",
        "bks_gap_details",
        "validation_case_details",
        "frozen_case_details",
        "holdout_rows",
        "prompt_ratios",
        "llm_text",
        "phase_telemetry",
    }
)


def _filter_hypothesis_prompt_steps(
    step_history: list[StepRecord],
) -> list[StepRecord]:
    """Expose each completed screening experiment once."""

    return [
        step
        for step in step_history
        if (
            step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
        )
    ]


class ContextManager:
    """Build the sole direct-V3 hypothesis and code contexts."""

    def __init__(
        self,
        *,
        adapter: Any | None = None,
        research_input: Mapping[str, Any] | None = None,
        research_history: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        self._adapter = adapter
        self._research_input = (
            normalize_research_input(research_input)
            if research_input is not None
            else None
        )
        self._prior_research_observations = self._project_prior_observations()
        self._research_history = tuple(dict(record) for record in research_history)

    def _project_prior_observations(self) -> tuple[dict[str, Any], ...]:
        if self._research_input is None or not self._research_input["observations"]:
            return ()
        provider = resolve_prior_research_observation_provider(
            adapter=self._adapter,
        )
        if provider is None:
            raise ValueError(
                "research input observations require a "
                "prior_research_observation_provider"
            )
        projected: list[dict[str, Any]] = []
        for observation in self._research_input["observations"]:
            value = project_prior_research_observation(
                provider,
                observation=observation,
            )
            if value is not None:
                projected.append(value)
        bounded_projection = normalize_research_input(
            {
                "current_question": self._research_input["current_question"],
                "observations": projected,
            }
        )
        return tuple(bounded_projection["observations"])

    def build_hypothesis_context(
        self,
        branch: Branch,
        champion: ChampionState,
        problem_spec: ProblemSpec,
        step_history: Optional[list[StepRecord]] = None,
        branch_workspace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Return the V3 round-one research context.

        Each prior screening experiment is exposed once. Safe pre-Protocol gate
        observations remain ordinary research facts rather than repair advice.
        Validation/frozen details, branch status mirrors, host search controls,
        repair loops, and cross-branch governance artifacts are deliberately
        absent.
        """

        adapter_spec = _get_adapter_problem_spec(self._adapter)
        research_surfaces = _get_research_surfaces(problem_spec, adapter_spec)
        solver_design_surfaces = _solver_design_surface_names(research_surfaces)
        # H receives every research surface declared safe by the problem. A
        # problem-owned guidance provider may describe solver-design mechanics,
        # but it does not acquire authority to hide other declared source.
        visible_surfaces = research_surfaces
        include_operator_files = _include_operator_files_for_research_code(
            visible_surfaces
        )
        branch_source, branch_changed_paths = (
            _read_branch_code_projection(
                branch_workspace,
                champion,
                research_surfaces=visible_surfaces,
                include_operator_files=include_operator_files,
            )
            if branch_workspace
            else (None, ())
        )
        champion_source = _read_champion_research_code(
            champion,
            research_surfaces=visible_surfaces,
            include_operator_files=include_operator_files,
            excluded_paths=branch_changed_paths,
        )
        existing_target_files = _existing_target_files(
            champion,
            branch_workspace=branch_workspace,
            research_surfaces=visible_surfaces,
        )
        create_path_patterns = sorted(
            {
                str(pattern).lstrip("/")
                for surface in visible_surfaces
                if surface_action_allowed(surface, "create_new")
                for pattern in surface_target_files(surface)
                if _contains_glob_magic(str(pattern))
                or str(pattern).lstrip("/") not in existing_target_files
            }
        )
        available_actions = _available_actions_for_context(
            visible_surfaces,
            existing_target_files=existing_target_files,
        )
        history_steps = step_history or []
        experiment_history = proposal_screening_history(
            campaign_screening_history(
                branch,
                _filter_hypothesis_prompt_steps(history_steps),
            )
        )
        pre_protocol_observations = proposal_pre_protocol_observations(history_steps)
        provider = (
            resolve_solver_design_prompt_provider(
                problem_spec=problem_spec,
                adapter=self._adapter,
            )
            if solver_design_surfaces
            else None
        )

        context: dict[str, Any] = {
            "problem_summary": _build_problem_summary(
                problem_spec,
                adapter=self._adapter,
            ),
            "problem_object": _build_problem_object(adapter=self._adapter),
            "solver_mechanics": _build_solver_mechanics(adapter=self._adapter),
            "objective_policy_guidance": _build_objective_policy_guidance(adapter_spec),
            "branch_id": branch.branch_id,
            "champion_version": champion.version,
            "research_surfaces": _hypothesis_surface_projections(
                visible_surfaces,
                problem_spec,
                include_problem_prompt=provider is None,
            ),
            "available_actions": sorted(available_actions),
            "existing_target_files": existing_target_files,
            "create_path_patterns": create_path_patterns,
            "champion_operators_code": champion_source,
            "champion_stats": _champion_projection(champion),
            "experiment_history": experiment_history,
        }
        if branch_source:
            context["branch_current_code"] = branch_source
        if pre_protocol_observations:
            context["pre_protocol_observations"] = pre_protocol_observations

        measurement = _problem_measurement_diagnostics(
            problem_spec,
            adapter=self._adapter,
        )
        if measurement:
            context["problem_measurement_diagnostics"] = measurement
        if self._research_input is not None:
            context["research_question"] = {
                "current_question": self._research_input["current_question"],
            }
        if self._prior_research_observations:
            context["prior_research_observations"] = list(
                self._prior_research_observations
            )
        if self._research_history:
            context["prior_research_history"] = provider_research_history(
                self._research_history,
            )
        guidance = materialize_solver_design_prompt_guidance(
            provider,
            context,
            phase="hypothesis",
        )
        if any(guidance.values()):
            context[RENDERER_INPUTS_KEY] = {SOLVER_DESIGN_GUIDANCE_KEY: guidance}
        return context

    def build_code_context(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        champion: ChampionState,
        problem_spec: ProblemSpec,
        branch_workspace: Optional[str] = None,
        step_history: Optional[list[StepRecord]] = None,
        development_suites: Sequence[Any] = (),
    ) -> dict[str, Any]:
        """Return the V3 round-two implementation context only."""

        adapter_spec = _get_adapter_problem_spec(self._adapter)
        research_surfaces = _get_research_surfaces(problem_spec, adapter_spec)
        surface = _find_research_surface(
            research_surfaces,
            hypothesis.change_locus,
        )
        if branch.current_code_hash and not (
            branch_workspace and os.path.isdir(branch_workspace)
        ):
            raise ValueError(
                "branch-current code requires its materialized branch workspace"
            )
        source_root = (
            branch_workspace
            if branch_workspace and os.path.isdir(branch_workspace)
            else champion.code_snapshot_path
        )
        source_root_path = Path(str(source_root or ""))
        if not source_root_path.is_dir() or source_root_path.is_symlink():
            raise ValueError("current source root must be a non-symlink directory")
        provider = (
            resolve_solver_design_prompt_provider(
                problem_spec=problem_spec,
                adapter=self._adapter,
            )
            if _is_solver_design_context_surface(
                hypothesis.change_locus,
                surface,
            )
            else None
        )
        problem_id = str(
            getattr(adapter_spec, "id", None)
            or getattr(problem_spec, "name", "")
            or ""
        ).strip()
        qualified_module_prefixes = (
            (f"scion.problems.{problem_id}.",) if problem_id else ()
        )
        editable_source_context = _build_editable_source_context(
            champion=champion,
            selected_surface=surface,
            source_root=source_root,
            target_file=hypothesis.target_file,
            target_action=hypothesis.action,
            provider=provider,
            editable_patterns=tuple(problem_spec.search_space.editable),
            frozen_patterns=tuple(problem_spec.search_space.frozen),
            development_suites=development_suites,
            qualified_module_prefixes=qualified_module_prefixes,
        )
        operator_interface_spec = _build_operator_interface_spec(
            problem_spec,
            adapter=self._adapter,
            surface_name=hypothesis.change_locus,
        )
        research_surface = _surface_projection(surface, prompt_phase="code")
        context: dict[str, Any] = {
            "problem_summary": _build_problem_summary(
                problem_spec,
                adapter=self._adapter,
            ),
            "problem_object": _build_problem_object(adapter=self._adapter),
            "solver_mechanics": _build_solver_mechanics(adapter=self._adapter),
            "branch_id": branch.branch_id,
            "champion_version": champion.version,
            "approved_hypothesis": _hypothesis_projection(hypothesis),
            EDITABLE_SOURCE_CONTEXT_KEY: editable_source_context,
            "operator_interface_spec": operator_interface_spec,
            "research_surface": research_surface,
            "import_whitelist": list(problem_spec.search_space.import_whitelist),
            "editable_patterns": list(problem_spec.search_space.editable),
            "frozen_patterns": list(problem_spec.search_space.frozen),
        }
        code_constraints = active_subject_code_constraints_payload(
            context=context,
            problem_spec=problem_spec,
            adapter=self._adapter,
            surface=hypothesis.change_locus,
        )
        if code_constraints:
            context["active_subject_code_constraints"] = code_constraints
        guidance = materialize_solver_design_prompt_guidance(
            provider,
            context,
            phase="code",
            hypothesis=hypothesis,
        )
        if any(guidance.values()):
            context[RENDERER_INPUTS_KEY] = {SOLVER_DESIGN_GUIDANCE_KEY: guidance}
        positive_code_constraints: list[str] = []
        for name in ("object_model_hints", "api_contracts"):
            for item in code_constraints.get(name, ()):
                value = item.get("constraint") if isinstance(item, Mapping) else item
                if text := str(value or "").strip():
                    positive_code_constraints.append(text)
        positive_operator_interface = "\n".join(
            line
            for line in operator_interface_spec.splitlines()
            if "import whitelist" not in line.casefold()
        ).strip()
        guidance_parts = [
            editable_source_context["target_api_guidance"],
            positive_operator_interface,
            research_surface.get("implementation_guidance", ""),
            *positive_code_constraints,
            *guidance.get("code_rules", ()),
            *guidance.get("user_constraints", ()),
        ]
        editable_source_context["target_api_guidance"] = "\n\n".join(
            dict.fromkeys(
                text for part in guidance_parts if (text := str(part or "").strip())
            )
        )
        return context


def _existing_target_files(
    champion: ChampionState,
    *,
    branch_workspace: str | None,
    research_surfaces: list[Any],
) -> list[str]:
    files = set(_list_champion_operator_files(champion))
    files.update(
        _list_champion_surface_files(
            champion,
            research_surfaces=research_surfaces,
        )
    )
    if branch_workspace:
        files.update(
            _list_branch_surface_files(
                branch_workspace,
                research_surfaces=research_surfaces,
            )
        )
        declared = [
            path
            for surface in research_surfaces
            for path in surface_target_files(surface)
        ]
        files.update(_expand_surface_targets_for_root(branch_workspace, declared))
    else:
        declared = [
            path
            for surface in research_surfaces
            for path in surface_target_files(surface)
        ]
        files.update(_expand_surface_targets_for_champion(champion, declared))
    return sorted(
        path
        for path in files
        if str(path).strip() and not _contains_glob_magic(str(path))
    )


def _available_actions_for_context(
    research_surfaces: list[Any],
    *,
    existing_target_files: list[str],
) -> list[str]:
    """Project only actions that at least one declared surface can execute."""

    available: set[str] = set()
    existing = tuple(existing_target_files)
    for surface in research_surfaces:
        has_existing_target = any(
            any(
                _matches_surface_pattern(path, pattern)
                for pattern in surface_target_files(surface)
            )
            for path in existing
        )
        if surface_action_allowed(surface, "create_new"):
            available.add("create_new")
        if has_existing_target and surface_action_allowed(surface, "modify"):
            available.add("modify")
        if has_existing_target and surface_action_allowed(surface, "remove"):
            available.add("remove")
    return sorted(available)


def _contains_glob_magic(path: str) -> bool:
    return any(character in path for character in "*?[")


def _matches_surface_pattern(path: str, pattern: str) -> bool:
    return matches_config_pattern(path, str(pattern).lstrip("/"))


def _build_objective_policy_guidance(adapter_spec: Any | None) -> dict[str, Any]:
    if adapter_spec is None:
        return {}
    objectives = sorted(
        list(getattr(adapter_spec, "objectives", []) or []),
        key=lambda item: getattr(item, "priority", 0),
    )
    policy = getattr(adapter_spec, "objective_policy", None)
    if not objectives:
        return {}
    mode = str(getattr(policy, "mode", "lexicographic") or "lexicographic")
    projected = [
        {
            key: value
            for key, value in {
                "name": getattr(objective, "name", ""),
                "direction": getattr(objective, "direction", ""),
                "priority": getattr(objective, "priority", None),
                "tie_tolerance": getattr(objective, "tie_tolerance", None),
                "weight": (
                    getattr(objective, "weight", None)
                    if bool(getattr(policy, "expose_weights_to_llm", False))
                    else None
                ),
            }.items()
            if value not in (None, "", [], {})
        }
        for objective in objectives
    ]
    return {
        "mode": mode,
        "objectives": projected,
        "interpretation": (
            "Improve the weighted aggregate while preserving feasibility."
            if mode == "weighted_sum"
            else (
                "Improve the declared objective while preserving feasibility."
                if mode == "single"
                else (
                    "Preserve higher-priority objectives within their tie tolerances "
                    "before claiming a lower-priority gain."
                )
            )
        ),
    }


def _surface_projection(
    surface: Any | None,
    *,
    prompt_phase: str | None = None,
) -> dict[str, Any]:
    if surface is None:
        return {}
    projection: dict[str, Any] = {
        "name": str(getattr(surface, "name", "") or ""),
        "kind": str(getattr(surface, "kind", "") or ""),
        "description": str(getattr(surface, "description", "") or ""),
        "target_files": surface_target_files(surface),
        "allowed_actions": [
            action
            for action in ("create_new", "modify", "remove")
            if surface_action_allowed(surface, action)
        ],
    }
    for name in ("interface",):
        value = getattr(surface, name, None)
        primitive = _primitive(value)
        if primitive not in (None, "", [], {}):
            projection[name] = primitive
    prompt = getattr(surface, "prompt", None)
    if prompt is not None and prompt_phase == "hypothesis":
        guidance = str(getattr(prompt, "hypothesis_guidance", "") or "").strip()
        if guidance:
            projection["hypothesis_guidance"] = guidance
    elif prompt is not None and prompt_phase == "code":
        implementation = str(
            getattr(prompt, "implementation_guidance", "") or ""
        ).strip()
        anti_patterns = str(getattr(prompt, "anti_patterns", "") or "").strip()
        if implementation:
            projection["implementation_guidance"] = implementation
        if anti_patterns:
            projection["anti_patterns"] = anti_patterns
    # Novelty metadata belonged to legacy semantic gates. Problem prompt text
    # is phase-projected only when no explicit problem prompt provider exists.
    return {
        key: value
        for key, value in projection.items()
        if value not in (None, "", [], {})
    }


def _hypothesis_surface_projections(
    surfaces: list[Any],
    problem_spec: ProblemSpec,
    *,
    include_problem_prompt: bool = False,
) -> list[dict[str, Any]]:
    projections = [
        _surface_projection(
            surface,
            prompt_phase=("hypothesis" if include_problem_prompt else None),
        )
        for surface in surfaces
    ]
    if projections:
        return projections
    return [
        {"name": category, "kind": "operator"}
        for category in problem_spec.operator_categories
    ]


def _champion_projection(champion: ChampionState) -> dict[str, Any]:
    return {
        "version": champion.version,
        "operators": [
            {
                "name": name,
                "category": getattr(operator, "category", ""),
                "file_path": getattr(operator, "file_path", ""),
                "class_name": getattr(operator, "class_name", ""),
                "weight": getattr(operator, "weight", None),
            }
            for name, operator in sorted((champion.operator_pool or {}).items())
        ],
    }


def _hypothesis_projection(hypothesis: HypothesisProposal) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "hypothesis_text": hypothesis.hypothesis_text,
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "target_file": hypothesis.target_file,
            "predicted_direction": hypothesis.predicted_direction,
            "target_weakness": hypothesis.target_weakness,
            "expected_effect": hypothesis.expected_effect,
            "suggested_weight": hypothesis.suggested_weight,
        }.items()
        if value not in (None, "", [], {})
    }


def screening_record(step: StepRecord) -> dict[str, Any]:
    """Project one in-process screening step into proposal memory."""

    protocol = step.protocol_result
    if protocol is None or protocol.stage != ExperimentStage.SCREENING:
        raise ValueError("hypothesis evidence requires a screening result")
    if step.hypothesis is None:
        raise ValueError("screening evidence requires a hypothesis")
    experiment_evidence = _screening_projection(protocol)
    if step.decision is not None:
        experiment_evidence["decision_outcome"] = _drop_empty(
            {
                "decision": _primitive(step.decision),
                "reason_codes": list(step.decision_reason_codes or ()),
            }
        )
    proposal_changes = patch_file_changes(step.patch) if step.patch is not None else ()
    current_step = {
        "target_files": sorted(
            {
                normalize_relative_patch_path(change.file_path)
                for change in proposal_changes
                if change.file_path
            }
        ),
    }
    has_current_patch = bool(proposal_changes)
    clean_current_step_candidate = (
        has_current_patch and step.candidate_parent_scope == "declared_champion"
    )
    candidate_composition = {
        "attribution_scope": (
            "current_step_candidate"
            if clean_current_step_candidate
            else "cumulative_branch_candidate"
        ),
        "protocol_comparison_scope": "candidate_vs_champion",
        "evaluation_candidate": (
            "branch_state_after_current_step_patch"
            if has_current_patch
            else "reused_verified_branch_state"
        ),
        "current_step_change_scope": (
            "incremental_patch" if has_current_patch else "eval_only_reuse"
        ),
        "incremental_effect_isolated": clean_current_step_candidate,
        "current_step": _drop_empty(current_step),
    }
    return {
        "round_num": step.round_num,
        "hypothesis": _hypothesis_projection(step.hypothesis),
        "candidate_composition": candidate_composition,
        "experiment_evidence": experiment_evidence,
    }


def campaign_screening_history(
    current_branch: Branch,
    steps: list[StepRecord],
) -> list[dict[str, Any]]:
    """Return every in-process screening step in ordinary round order."""

    records: list[dict[str, Any]] = []
    for step in steps:
        relation = (
            "current" if step.branch_id == current_branch.branch_id else "sibling"
        )
        records.append({**screening_record(step), "relation": relation})
    return records


def _screening_projection(protocol: Any) -> dict[str, Any]:
    stats = protocol.stats
    pair_feedback = list(protocol.pair_feedback or ())
    pair_counts = {
        "win": int(getattr(stats, "pair_wins", 0) or 0),
        "loss": int(getattr(stats, "pair_losses", 0) or 0),
        "tie": int(getattr(stats, "pair_ties", 0) or 0),
    }
    declared_pair_total = sum(pair_counts.values())
    observed_pair_counts = {"win": 0, "loss": 0, "tie": 0}
    for item in pair_feedback:
        comparison = str(getattr(item, "comparison", "") or "").strip()
        if comparison not in observed_pair_counts:
            raise ValueError("screening pair feedback comparison is invalid")
        observed_pair_counts[comparison] += 1
    if observed_pair_counts != pair_counts:
        raise ValueError("screening pair feedback conflicts with Protocol stats")
    valid_pairs = int(getattr(stats, "valid_pairs", 0) or 0)
    candidate_failed_pairs = int(getattr(stats, "candidate_failed_pairs", 0) or 0)
    feedback_count = len(pair_feedback)
    if not valid_pairs <= feedback_count <= valid_pairs + candidate_failed_pairs:
        raise ValueError(
            "screening pair feedback cardinality conflicts with "
            "valid/candidate-failure pair counts"
        )
    aggregation = {
        "statistical_unit": "case",
        "method": str(
            getattr(protocol, "case_aggregation_method", "") or "seed_vote_majority"
        ),
        "effect_metric": str(getattr(protocol, "case_effect_metric", "") or ""),
        "equivalence_band": float(
            getattr(protocol, "case_equivalence_band", 0.0) or 0.0
        ),
        "win_rate_scope": "case_level_gate",
        "median_delta_scope": "case_medians",
        "ci_scope": "case_medians",
    }
    if declared_pair_total > 0:
        aggregation.update(
            {
                "pair_win_rate_scope": "pair_level_protocol_stats",
                "pair_win_rate": pair_counts["win"] / declared_pair_total,
            }
        )
    payload = {
        "stage": protocol.stage.value,
        "protocol_outcome": {
            "gate_outcome": protocol.gate_outcome,
            "reason_codes": list(protocol.reason_codes or ()),
        },
        "runtime_model": protocol.runtime_model,
        "objective_outcome": {
            "semantics": protocol.objective_semantics,
            "aggregate": _screening_stats_projection(stats),
            "aggregation": aggregation,
        },
        "case_outcomes": {
            "case_ids": list(protocol.case_ids or ()),
            "seed_set": list(protocol.seed_set or ()),
            "pair_feedback": _primitive(pair_feedback),
            "case_feedback": _primitive(list(protocol.case_feedback or ())),
        },
        "runtime_errors": {
            "categories": _primitive(protocol.candidate_runtime_failure_categories),
        },
    }
    from scion.protocol.experiment.proposal_evidence import (
        is_proposal_mechanism_evidence_envelope,
    )

    mechanism_evidence = None
    if is_proposal_mechanism_evidence_envelope(protocol.mechanism_evidence):
        mechanism_evidence = _primitive(protocol.mechanism_evidence)
    projected = _drop_empty(payload)
    if mechanism_evidence is not None:
        # The verified generic envelope is already the visibility boundary.
        # Keep unavailable/empty problem-owned observations byte-for-byte;
        # interpreting them here would acquire problem semantics in core.
        projected["mechanism_evidence"] = mechanism_evidence
    return projected


def _screening_stats_projection(stats: Any) -> dict[str, Any]:
    """Expose measured aggregates without runtime qualification advice."""

    projected = _primitive(stats)
    if not isinstance(projected, Mapping):
        return {}
    return screening_eval_stats(projected)


def _problem_measurement_diagnostics(
    problem_spec: ProblemSpec,
    *,
    adapter: Any | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    measurement = getattr(problem_spec, "measurement", None)
    if measurement is not None:
        view = measurement_consumer_view(problem_spec)
        payload["runtime_model"] = view.runtime_model
        payload["pairing_validity"] = view.pairing_validity
        payload["effect_scale"] = {
            "metric": view.effect_metric,
            "unit": view.effect_unit,
            "practical_delta_screen": view.practical_delta_screen,
            "practical_delta_validate": view.practical_delta_validate,
        }
        payload["measurement_readiness"] = view.to_readiness_status_payload()
    hook = getattr(adapter, "render_problem_measurement_diagnostics", None)
    if callable(hook):
        try:
            adapter_payload = hook()
        except Exception:
            adapter_payload = None
        if isinstance(adapter_payload, Mapping):
            projected = _project_measurement_payload(adapter_payload)
            if projected:
                payload["problem_owned_diagnostics"] = projected
    return {
        key: value for key, value in payload.items() if value not in (None, "", [], {})
    }


def _project_measurement_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for raw_key, value in payload.items():
        key = str(raw_key)
        if key in _MEASUREMENT_PRIVATE_FIELDS:
            continue
        projected[key] = _project_measurement_value(value)
    return projected


def _project_measurement_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(raw_key): _project_measurement_value(child)
            for raw_key, child in value.items()
            if str(raw_key) not in _MEASUREMENT_PRIVATE_FIELDS
        }
    if isinstance(value, (list, tuple)):
        return [_project_measurement_value(item) for item in value]
    return _primitive(value)


def _primitive(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return _primitive(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _primitive(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _primitive(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_primitive(child) for child in value]
    state = getattr(value, "__dict__", None)
    if isinstance(state, Mapping):
        return {
            str(key): _primitive(child)
            for key, child in state.items()
            if not str(key).startswith("_")
        }
    return str(value)


def _drop_empty(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): projected
            for key, child in value.items()
            if (projected := _drop_empty(child)) not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [_drop_empty(child) for child in value]
    return value


__all__ = [
    "ContextManager",
    "campaign_screening_history",
    "screening_record",
]
