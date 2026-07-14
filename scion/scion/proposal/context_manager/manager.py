"""Direct V3 proposal-context assembly.

The context manager has one job: expose the smallest complete set of research
facts needed by the two proposal calls.  It does not steer the search through
quality gates, retry advice, portfolio controls, or host-generated repairs.
"""
from __future__ import annotations

import os
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Mapping, Optional

from scion.config.problem import ProblemSpec
from scion.core.forced_surface import (
    surface_action_allowed,
    surface_target_files,
    validate_forced_surface_request,
)
from scion.core.models import (
    Branch,
    ChampionState,
    ExperimentStage,
    HypothesisProposal,
    StepRecord,
    patch_file_changes,
)
from scion.measurement.consumer_view import measurement_consumer_view
from scion.problem.providers import (
    active_subject_code_constraints_payload,
    resolve_solver_design_prompt_provider,
    typed_research_question_payload,
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
    _hypothesis_visible_research_surfaces,
    _include_operator_files_for_research_code,
    _is_solver_design_context_surface,
    _solver_design_surface_names,
)

from .code_context import (
    DURABLE_BRANCH_CREATED_FILES_KEY,
    DURABLE_BRANCH_TOUCHED_FILES_KEY,
    SOURCE_LEDGER_KEY,
    _build_code_source_ledger,
    _read_champion_research_code,
    branch_created_files,
    branch_current_file_sources,
    branch_touched_files,
)
from .io import (
    _available_hypothesis_actions,
    _expand_surface_targets_for_champion,
    _expand_surface_targets_for_root,
    _list_branch_surface_files,
    _list_champion_operator_files,
    _list_champion_surface_files,
    _read_branch_code,
)
from scion.proposal.solver_design_guidance import (
    RENDERER_INPUTS_KEY,
    SOLVER_DESIGN_GUIDANCE_KEY,
    materialize_solver_design_prompt_guidance,
)
from scion.proposal.prompt_manifest import stable_digest


_MEASUREMENT_FORBIDDEN_KEY_FRAGMENTS = (
    "pair_evidence",
    "pair_rows",
    "raw_pair",
    "raw_calibration",
    "calibration_pair",
    "bks",
    "validation_case",
    "frozen_case",
    "holdout",
    "prompt_ratio",
    "llm_text",
    "opportunity",
    "typed_attribution",
    "telemetry",
    "activation",
    "mechanism",
    "operator",
)

CANONICAL_SCREENING_HISTORY_KEY = "canonical_screening_history"

def _filter_hypothesis_prompt_steps(
    step_history: list[StepRecord],
) -> list[StepRecord]:
    """Expose one canonical evidence record per completed screening experiment."""

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
    ) -> None:
        self._adapter = adapter

    def build_hypothesis_context(
        self,
        branch: Branch,
        champion: ChampionState,
        problem_spec: ProblemSpec,
        step_history: Optional[list[StepRecord]] = None,
        branch_workspace: Optional[str] = None,
        forced_locus: Optional[str] = None,
        forced_action: Optional[str] = None,
        forced_target_file: Optional[str] = None,
        forced_surface_diagnostic: bool = False,
    ) -> dict[str, Any]:
        """Return the V3 round-one research context.

        Each prior screening experiment is exposed once. Validation/frozen
        details, branch status mirrors, host search controls, repair loops,
        and cross-branch governance artifacts are deliberately absent.
        """

        adapter_spec = _get_adapter_problem_spec(self._adapter)
        research_surfaces = _get_research_surfaces(problem_spec, adapter_spec)
        forced_request = (
            validate_forced_surface_request(
                problem_spec,
                forced_locus,
                action=forced_action,
                target_file=forced_target_file,
                adapter_spec=adapter_spec,
            )
            if forced_locus
            else None
        )
        active_boundary_surfaces = (
            []
            if forced_request is not None
            else _solver_design_surface_names(research_surfaces)
        )
        visible_surfaces = _hypothesis_visible_research_surfaces(
            research_surfaces,
            forced_surface=forced_request.surface if forced_request else None,
            active_problem_boundary_surfaces=active_boundary_surfaces,
        )
        include_operator_files = _include_operator_files_for_research_code(
            visible_surfaces
        )
        champion_source = _read_champion_research_code(
            champion,
            research_surfaces=visible_surfaces,
            include_operator_files=include_operator_files,
        )
        branch_source = (
            _read_branch_code(
                branch_workspace,
                champion,
                research_surfaces=visible_surfaces,
                include_operator_files=include_operator_files,
            )
            if branch_workspace
            else None
        )
        targetable_files = _targetable_files(
            champion,
            branch_workspace=branch_workspace,
            research_surfaces=visible_surfaces,
        )
        available_actions = _available_hypothesis_actions(
            _list_champion_operator_files(champion),
            targetable_policy_files=_list_champion_surface_files(
                champion,
                research_surfaces=visible_surfaces,
            ),
        )
        safe_steps = _filter_hypothesis_prompt_steps(step_history or [])
        branch_steps = [
            step for step in safe_steps if step.branch_id == branch.branch_id
        ]
        experiment_history = canonical_screening_history(
            branch,
            branch_steps,
        )
        provider = (
            resolve_solver_design_prompt_provider(
                problem_spec=problem_spec,
                adapter=self._adapter,
            )
            if active_boundary_surfaces
            else None
        )

        context: dict[str, Any] = {
            "problem_summary": _build_problem_summary(
                problem_spec,
                adapter=self._adapter,
            ),
            "problem_object": _build_problem_object(adapter=self._adapter),
            "solver_mechanics": _build_solver_mechanics(adapter=self._adapter),
            "objective_policy_guidance": _build_objective_policy_guidance(
                adapter_spec
            ),
            "branch_id": branch.branch_id,
            "champion_version": champion.version,
            "research_surfaces": _hypothesis_surface_projections(
                visible_surfaces,
                problem_spec,
            ),
            "available_actions": sorted(available_actions),
            "targetable_files": targetable_files,
            "champion_operators_code": champion_source,
            "champion_stats": _champion_projection(champion),
            "experiment_history": experiment_history,
        }
        if branch_source:
            context["branch_current_code"] = branch_source

        measurement = _problem_measurement_diagnostics(
            problem_spec,
            adapter=self._adapter,
        )
        if measurement:
            context["problem_measurement_diagnostics"] = measurement
        research_question = typed_research_question_payload(
            problem_spec=problem_spec,
            adapter=self._adapter,
        )
        if research_question:
            context["research_question"] = research_question
        if forced_request is not None:
            context["forced_research_target"] = _forced_target_projection(
                forced_request,
                visible_surfaces,
                diagnostic=forced_surface_diagnostic,
            )

        guidance = materialize_solver_design_prompt_guidance(
            provider,
            context,
            phase="hypothesis",
        )
        if any(guidance.values()):
            context[RENDERER_INPUTS_KEY] = {
                SOLVER_DESIGN_GUIDANCE_KEY: guidance
            }
        return context

    def build_code_context(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        champion: ChampionState,
        problem_spec: ProblemSpec,
        branch_workspace: Optional[str] = None,
        step_history: Optional[list[StepRecord]] = None,
    ) -> dict[str, Any]:
        """Return the V3 round-two implementation context only."""

        adapter_spec = _get_adapter_problem_spec(self._adapter)
        research_surfaces = _get_research_surfaces(problem_spec, adapter_spec)
        surface = _find_research_surface(
            research_surfaces,
            hypothesis.change_locus,
        )
        source_root = (
            branch_workspace
            if branch_workspace and os.path.isdir(branch_workspace)
            else champion.code_snapshot_path
        )
        branch_file_sources = branch_current_file_sources(
            branch,
            step_history or [],
        )
        workspace_visible = bool(
            branch_workspace and os.path.isdir(branch_workspace)
        )
        created = (
            branch_created_files(branch, step_history or [])
            if workspace_visible or branch_file_sources
            else ()
        )
        touched = (
            branch_touched_files(branch, step_history or [])
            if workspace_visible or branch_file_sources
            else ()
        )
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
        source_ledger = _build_code_source_ledger(
            champion=champion,
            research_surfaces=research_surfaces,
            change_locus=hypothesis.change_locus,
            source_root=source_root,
            target_file=hypothesis.target_file,
            target_action=hypothesis.action,
            provider=provider,
            branch_created_files=created,
            branch_touched_files=touched,
            branch_current_file_sources=branch_file_sources,
        )
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
            SOURCE_LEDGER_KEY: source_ledger,
            "operator_interface_spec": _build_operator_interface_spec(
                problem_spec,
                adapter=self._adapter,
                surface_name=hypothesis.change_locus,
            ),
            "research_surface": _surface_projection(surface),
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
            context[RENDERER_INPUTS_KEY] = {
                SOLVER_DESIGN_GUIDANCE_KEY: guidance
            }
        return context


def _targetable_files(
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
    for surface in research_surfaces:
        files.update(surface_target_files(surface))
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
        files.update(
            _expand_surface_targets_for_root(branch_workspace, declared)
        )
    else:
        declared = [
            path
            for surface in research_surfaces
            for path in surface_target_files(surface)
        ]
        files.update(_expand_surface_targets_for_champion(champion, declared))
    return sorted(path for path in files if str(path).strip())


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
            else "Improve the declared objective while preserving feasibility."
            if mode == "single"
            else (
                "Preserve higher-priority objectives within their tie tolerances "
                "before claiming a lower-priority gain."
            )
        ),
    }


def _surface_projection(surface: Any | None) -> dict[str, Any]:
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
    # Prompt/novelty metadata belonged to legacy semantic gates. Direct V3 gets
    # problem-owned guidance from the explicit provider packet instead.
    return {
        key: value
        for key, value in projection.items()
        if value not in (None, "", [], {})
    }


def _hypothesis_surface_projections(
    surfaces: list[Any],
    problem_spec: ProblemSpec,
) -> list[dict[str, Any]]:
    projections = [_surface_projection(surface) for surface in surfaces]
    if projections:
        return projections
    return [
        {"name": category, "kind": "operator"}
        for category in problem_spec.operator_categories
    ]


def _champion_projection(champion: ChampionState) -> dict[str, Any]:
    return {
        "version": champion.version,
        "code_snapshot_hash": champion.code_snapshot_hash,
        "solver_config_hash": champion.solver_config_hash,
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


def canonical_screening_record(step: StepRecord) -> dict[str, Any]:
    protocol = step.protocol_result
    if protocol is None or protocol.stage != ExperimentStage.SCREENING:
        raise ValueError("canonical hypothesis evidence requires screening result")
    experiment_evidence = _screening_projection(protocol)
    screening_attempt_id = stable_digest(
        {
            "branch_id": step.branch_id,
            "hypothesis_id": step.hypothesis_id,
            "round_num": step.round_num,
            "raw_metrics_ref": protocol.raw_metrics_ref,
            "experiment_evidence": experiment_evidence,
        },
        length=32,
    )
    return {
        "screening_attempt_id": screening_attempt_id,
        "attempt_id": step.hypothesis_id or f"{step.branch_id}:{step.round_num}",
        "round_num": step.round_num,
        "hypothesis": _hypothesis_projection(step.hypothesis),
        "experiment_evidence": experiment_evidence,
    }


def canonical_screening_history(
    branch: Branch,
    steps: list[StepRecord],
) -> list[dict[str, Any]]:
    """Merge durable and current screening facts without dropping evidence."""

    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    durable = summary.get(CANONICAL_SCREENING_HISTORY_KEY, [])
    if not isinstance(durable, list) or not all(
        isinstance(item, Mapping) for item in durable
    ):
        raise ValueError("branch canonical screening history is invalid")
    records = [dict(item) for item in durable]
    positions: dict[str, int] = {}
    for index, record in enumerate(records):
        screening_attempt_id = str(
            record.get("screening_attempt_id") or ""
        ).strip()
        if not screening_attempt_id or screening_attempt_id in positions:
            raise ValueError("branch canonical screening history identity is invalid")
        positions[screening_attempt_id] = index
    for step in steps:
        record = canonical_screening_record(step)
        screening_attempt_id = str(record["screening_attempt_id"])
        previous = positions.get(screening_attempt_id)
        if previous is not None:
            if records[previous] != record:
                raise ValueError("canonical screening history conflicts with current step")
            continue
        positions[screening_attempt_id] = len(records)
        records.append(record)
    return records


def persist_canonical_screening_record(
    branch: Branch,
    step: StepRecord,
) -> bool:
    """Append one lossless screening record to the durable branch owner."""

    protocol = step.protocol_result
    if protocol is None or protocol.stage != ExperimentStage.SCREENING:
        return False
    records = canonical_screening_history(branch, [])
    record = canonical_screening_record(step)
    screening_attempt_id = str(record["screening_attempt_id"])
    for existing in records:
        if (
            str(existing.get("screening_attempt_id") or "")
            != screening_attempt_id
        ):
            continue
        if existing != record:
            raise ValueError("durable canonical screening record conflict")
        return False
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    summary[CANONICAL_SCREENING_HISTORY_KEY] = [*records, record]
    created = list(summary.get(DURABLE_BRANCH_CREATED_FILES_KEY, []) or [])
    touched = list(summary.get(DURABLE_BRANCH_TOUCHED_FILES_KEY, []) or [])
    if not all(isinstance(path, str) for path in [*created, *touched]):
        raise ValueError("durable branch source footprint is invalid")
    if step.verification_passed and step.patch is not None:
        for change in patch_file_changes(step.patch):
            path = str(getattr(change, "file_path", "") or "").strip()
            if path and path not in touched:
                touched.append(path)
            if (
                path
                and str(getattr(change, "action", "") or "") == "create"
                and path not in created
            ):
                created.append(path)
    summary[DURABLE_BRANCH_CREATED_FILES_KEY] = created
    summary[DURABLE_BRANCH_TOUCHED_FILES_KEY] = touched
    branch.branch_evidence_summary = summary
    return True


def _screening_projection(protocol: Any) -> dict[str, Any]:
    stats = protocol.stats
    payload = {
        "stage": protocol.stage.value,
        "objective_outcome": {
            "semantics": protocol.objective_semantics,
            "aggregate": _primitive(stats),
        },
        "case_outcomes": {
            "case_ids": list(protocol.case_ids or ()),
            "seed_set": list(protocol.seed_set or ()),
            "pair_feedback": _primitive(list(protocol.pair_feedback or ())),
            "case_feedback": _primitive(list(protocol.case_feedback or ())),
        },
        "runtime_errors": {
            "categories": _primitive(
                protocol.candidate_runtime_failure_categories
            ),
            "first_error": _primitive(protocol.candidate_first_runtime_failure),
        },
    }
    return _drop_empty(payload)


def _forced_target_projection(
    request: Any,
    surfaces: list[Any],
    *,
    diagnostic: bool,
) -> dict[str, Any]:
    surface = _find_research_surface(surfaces, request.surface)
    return {
        "source": "operator_diagnostic" if diagnostic else "campaign_request",
        "surface": request.surface,
        "action": request.action,
        "target_file": request.target_file,
        "declared_target_files": surface_target_files(surface) if surface else [],
        "allowed_actions": [
            action
            for action in ("create_new", "modify", "remove")
            if surface is not None and surface_action_allowed(surface, action)
        ],
    }


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
        payload["measurement_readiness"] = (
            view.to_readiness_status_payload()
        )
    hook = getattr(adapter, "render_problem_measurement_diagnostics", None)
    if callable(hook):
        try:
            adapter_payload = hook()
        except Exception:
            adapter_payload = None
        if isinstance(adapter_payload, Mapping):
            redacted = _redact_measurement_payload(adapter_payload)
            if redacted:
                payload["problem_owned_diagnostics"] = redacted
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }


def _redact_measurement_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if any(
                fragment in lowered
                for fragment in _MEASUREMENT_FORBIDDEN_KEY_FRAGMENTS
            ):
                continue
            projected[key] = _redact_measurement_payload(child)
        return projected
    if isinstance(value, (list, tuple)):
        return [_redact_measurement_payload(item) for item in value]
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
    "CANONICAL_SCREENING_HISTORY_KEY",
    "ContextManager",
    "canonical_screening_history",
    "canonical_screening_record",
    "persist_canonical_screening_record",
]
