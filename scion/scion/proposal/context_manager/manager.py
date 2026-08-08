"""Direct V3 proposal-context assembly.

The context manager has one job: expose the smallest complete set of research
facts needed by the two proposal calls.  It does not steer the search through
quality gates, retry advice, portfolio controls, or host-generated repairs.
"""

from __future__ import annotations

import os
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from scion.config.problem import ProblemSpec
from scion.contract.patch_paths import matches_config_pattern
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import (
    Branch,
    ChampionState,
    ExperimentStage,
    HypothesisProposal,
    StepRecord,
    patch_file_changes,
)
from scion.core.paths import normalize_relative_patch_path
from scion.core.screening_visibility import runtime_evidence_policy_for_protocol
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
    _include_operator_files_for_research_code,
    _is_solver_design_context_surface,
    _solver_design_surface_names,
    surface_action_allowed,
    surface_target_files,
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
    _expand_surface_targets_for_champion,
    _expand_surface_targets_for_root,
    _list_branch_surface_files,
    _list_champion_operator_files,
    _list_champion_surface_files,
    _read_branch_code_projection,
)
from scion.proposal.solver_design_guidance import (
    RENDERER_INPUTS_KEY,
    SOLVER_DESIGN_GUIDANCE_KEY,
    materialize_solver_design_prompt_guidance,
)
from scion.proposal.prompt_manifest import stable_digest

_MEASUREMENT_VISIBLE_FIELDS_KEY = "proposal_visible_fields"
_MEASUREMENT_VISIBLE_ENVELOPE_FIELDS = (
    "schema_version",
    "proposal_visibility_only",
    "decision_features_excluded",
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
    }
)
_RESEARCH_REJECTION_PHASES = frozenset(
    {"hypothesis_contract", "patch_contract", "verification"}
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
        campaign_branches: Optional[Sequence[Branch]] = None,
        branch_workspace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Return the V3 round-one research context.

        Each prior screening experiment is exposed once. Validation/frozen
        details, branch status mirrors, host search controls, repair loops,
        and cross-branch governance artifacts are deliberately absent.
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
        experiment_history = campaign_canonical_screening_history(
            branch,
            campaign_branches,
            _filter_hypothesis_prompt_steps(history_steps),
        )
        rejection_history = campaign_research_rejection_history(
            branch,
            campaign_branches,
            history_steps,
        )
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
        if rejection_history:
            context["research_rejection_history"] = rejection_history

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
        workspace_visible = bool(branch_workspace and os.path.isdir(branch_workspace))
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
            context[RENDERER_INPUTS_KEY] = {SOLVER_DESIGN_GUIDANCE_KEY: guidance}
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
    if step.decision is not None:
        experiment_evidence["decision_outcome"] = _drop_empty(
            {
                "decision": _primitive(step.decision),
                "reason_codes": list(step.decision_reason_codes or ()),
            }
        )
    proposal_changes = patch_file_changes(step.patch) if step.patch is not None else ()
    current_step = {
        "hypothesis_id": step.hypothesis_id,
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
    screening_attempt_id = stable_digest(
        {
            "branch_id": step.branch_id,
            "hypothesis_id": step.hypothesis_id,
            "round_num": step.round_num,
            "raw_metrics_ref": protocol.raw_metrics_ref,
        },
        length=32,
    )
    return {
        "screening_attempt_id": screening_attempt_id,
        "attempt_id": step.hypothesis_id or f"{step.branch_id}:{step.round_num}",
        "round_num": step.round_num,
        "hypothesis": _hypothesis_projection(step.hypothesis),
        "candidate_composition": candidate_composition,
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
        natural_key = _screening_record_natural_key(record)
        if natural_key in positions:
            raise ValueError("branch canonical screening history identity is invalid")
        positions[natural_key] = index
    for step in steps:
        record = canonical_screening_record(step)
        natural_key = _screening_record_natural_key(record)
        previous = positions.get(natural_key)
        if previous is not None:
            if records[previous] != record:
                if _legacy_screening_record_can_upgrade(
                    records[previous],
                    record,
                ):
                    records[previous] = record
                    continue
                raise ValueError(
                    "canonical screening history conflicts with current step"
                )
            continue
        positions[natural_key] = len(records)
        records.append(record)
    return records


def campaign_canonical_screening_history(
    current_branch: Branch,
    campaign_branches: Optional[Sequence[Branch]],
    steps: list[StepRecord],
) -> list[dict[str, Any]]:
    """Return every safe screening record owned by this campaign.

    Durable records remain branch-owned and unchanged.  Source provenance is
    added only to the proposal-context projection so a new branch can
    distinguish its own evidence from sibling evidence without seeing branch
    state, validation/frozen outcomes, or other lifecycle mirrors.
    """

    complete_campaign_scope = campaign_branches is not None
    sources: dict[str, Branch] = {}
    for source in campaign_branches or ():
        source_id = str(getattr(source, "branch_id", "") or "").strip()
        if not source_id:
            raise ValueError("campaign screening source branch identity is invalid")
        if source_id in sources:
            raise ValueError("campaign screening source branch identity is duplicated")
        sources[source_id] = source
    # The in-memory current branch is authoritative over a persisted snapshot.
    sources[current_branch.branch_id] = current_branch

    steps_by_branch: dict[str, list[StepRecord]] = {}
    for step in steps:
        source_id = str(step.branch_id or "").strip()
        if not source_id:
            raise ValueError("campaign screening step branch identity is invalid")
        steps_by_branch.setdefault(source_id, []).append(step)

    merged: list[tuple[dict[str, Any], str]] = []
    positions: dict[str, int] = {}

    def merge_record(record: Mapping[str, Any], source_id: str) -> None:
        projected = dict(record)
        if {"source_branch_id", "relation"}.intersection(projected):
            raise ValueError("canonical screening record provenance is reserved")
        natural_key = _screening_record_natural_key(projected)
        previous = positions.get(natural_key)
        if previous is None:
            positions[natural_key] = len(merged)
            merged.append((projected, source_id))
            return
        existing, existing_source = merged[previous]
        if existing_source != source_id:
            raise ValueError("campaign canonical screening ownership is invalid")
        if existing == projected:
            return
        if _legacy_screening_record_can_upgrade(existing, projected):
            merged[previous] = (projected, source_id)
            return
        raise ValueError("campaign canonical screening history conflicts")

    for source_id, source in sources.items():
        for record in canonical_screening_history(
            source,
            steps_by_branch.pop(source_id, []),
        ):
            merge_record(record, source_id)

    if steps_by_branch and complete_campaign_scope:
        raise ValueError("campaign screening step owner is unknown")
    # Compatibility for legacy/injected ContextManager callers that do not
    # provide campaign ownership: retain only current-branch evidence.  Sibling
    # steps cannot be attributed safely without the complete owner set.
    steps_by_branch.clear()

    merged.sort(
        key=lambda item: (
            int(item[0]["round_num"]),
            item[1],
            _screening_record_natural_key(item[0]),
        )
    )
    return [
        {
            **record,
            "source_branch_id": source_id,
            "relation": (
                "current" if source_id == current_branch.branch_id else "sibling"
            ),
        }
        for record, source_id in merged
    ]


def campaign_research_rejection_history(
    current_branch: Branch,
    campaign_branches: Optional[Sequence[Branch]],
    steps: Sequence[StepRecord],
) -> list[dict[str, Any]]:
    """Project minimal pre-Protocol rejection facts for a fresh H call.

    Only typed Hypothesis Contract, Patch Contract, and Verification outcomes
    are eligible. Provider prose, check details/metadata, Protocol results, and
    evaluation-stage data never enter this projection.
    """

    known_branch_ids = {
        str(getattr(branch, "branch_id", "") or "").strip()
        for branch in campaign_branches or (current_branch,)
    }
    known_branch_ids.discard("")
    known_branch_ids.add(current_branch.branch_id)

    records: list[dict[str, Any]] = []
    for step in steps:
        phase = str(step.failure_stage or "").strip()
        source_branch_id = str(step.branch_id or "").strip()
        if (
            phase not in _RESEARCH_REJECTION_PHASES
            or source_branch_id not in known_branch_ids
            or step.protocol_result is not None
            or step.execution_outcome is not ExecutionOutcome.RESEARCH_REJECTED
            or not _rejection_state_matches_phase(step, phase)
        ):
            continue
        record = {
            "round_num": int(step.round_num),
            "source_branch_id": source_branch_id,
            "relation": (
                "current"
                if source_branch_id == current_branch.branch_id
                else "sibling"
            ),
            "phase": phase,
            "reason_code": str(step.execution_outcome_reason_code or "").strip(),
            "failed_check_codes": list(_failed_rejection_check_codes(step, phase)),
            **_rejection_target_projection(step, phase),
        }
        records.append(_drop_empty(record))

    records.sort(
        key=lambda record: (
            int(record["round_num"]),
            str(record["source_branch_id"]),
            str(record["phase"]),
        )
    )
    return records


def _rejection_state_matches_phase(step: StepRecord, phase: str) -> bool:
    if phase == "hypothesis_contract":
        return not step.contract_passed and step.patch is None
    if phase == "patch_contract":
        return not step.contract_passed and step.patch is not None
    return (
        phase == "verification"
        and step.contract_passed
        and not step.verification_passed
    )


def _failed_rejection_check_codes(
    step: StepRecord,
    phase: str,
) -> tuple[str, ...]:
    provenance = step.execution_outcome_provenance
    if not isinstance(provenance, Mapping):
        return ()
    key = "contract_checks" if phase.endswith("contract") else "verification_checks"
    checks = provenance.get(key, ())
    if not isinstance(checks, (list, tuple)):
        return ()
    codes: list[str] = []
    for check in checks:
        if not isinstance(check, Mapping) or check.get("passed") is not False:
            continue
        code = str(check.get("name") or "").strip()
        if code and code not in codes:
            codes.append(code)
    return tuple(codes)


def _rejection_target_projection(
    step: StepRecord,
    phase: str,
) -> dict[str, Any]:
    hypothesis = step.hypothesis
    projection: dict[str, Any] = {
        "research_surface": str(hypothesis.change_locus or "").strip(),
    }
    if phase == "hypothesis_contract" or step.patch is None:
        projection.update(
            {
                "action": str(hypothesis.action or "").strip(),
                "target_file": str(hypothesis.target_file or "").strip(),
            }
        )
        return _drop_empty(projection)

    targets = []
    for change in patch_file_changes(step.patch):
        target_file = str(change.file_path or "").strip()
        action = str(change.action or "").strip()
        if target_file or action:
            targets.append(
                _drop_empty({"action": action, "target_file": target_file})
            )
    if targets:
        projection["patch_targets"] = targets
    return _drop_empty(projection)


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
    natural_key = _screening_record_natural_key(record)
    for index, existing in enumerate(records):
        if _screening_record_natural_key(existing) != natural_key:
            continue
        if existing == record:
            return False
        if _legacy_screening_record_can_upgrade(existing, record):
            records[index] = record
            break
        raise ValueError("durable canonical screening record conflict")
    else:
        records.append(record)
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    summary[CANONICAL_SCREENING_HISTORY_KEY] = records
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


def _screening_record_natural_key(record: Mapping[str, Any]) -> str:
    attempt_id = str(record.get("attempt_id") or "").strip()
    round_num = record.get("round_num")
    if not attempt_id or isinstance(round_num, bool):
        raise ValueError("branch canonical screening history identity is invalid")
    try:
        normalized_round = int(round_num)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "branch canonical screening history identity is invalid"
        ) from exc
    if normalized_round <= 0:
        raise ValueError("branch canonical screening history identity is invalid")
    return f"{attempt_id}:{normalized_round}"


def _legacy_screening_record_needs_upgrade(record: Mapping[str, Any]) -> bool:
    composition = record.get("candidate_composition")
    evidence = record.get("experiment_evidence")
    if not isinstance(composition, Mapping) or not isinstance(evidence, Mapping):
        return True
    objective = evidence.get("objective_outcome")
    return (
        "protocol_outcome" not in evidence
        or "decision_outcome" not in evidence
        or not isinstance(objective, Mapping)
        or not isinstance(objective.get("aggregation"), Mapping)
    )


def _legacy_screening_record_can_upgrade(
    existing: Mapping[str, Any],
    current: Mapping[str, Any],
) -> bool:
    """Upgrade only a schema-old row whose pre-existing facts still match."""

    if not _legacy_screening_record_needs_upgrade(existing):
        return False
    return _legacy_screening_comparable_projection(
        existing
    ) == _legacy_screening_comparable_projection(current)


def _legacy_screening_comparable_projection(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Remove only fields introduced by the current display schema."""

    comparable = dict(record)
    comparable.pop("screening_attempt_id", None)
    comparable.pop("candidate_composition", None)
    evidence = comparable.get("experiment_evidence")
    if isinstance(evidence, Mapping):
        evidence_copy = dict(evidence)
        evidence_copy.pop("protocol_outcome", None)
        evidence_copy.pop("decision_outcome", None)
        objective = evidence_copy.get("objective_outcome")
        if isinstance(objective, Mapping):
            objective_copy = dict(objective)
            objective_copy.pop("aggregation", None)
            evidence_copy["objective_outcome"] = objective_copy
        comparable["experiment_evidence"] = evidence_copy
    return comparable


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
    if valid_pairs + candidate_failed_pairs != len(pair_feedback):
        raise ValueError(
            "screening pair feedback cardinality conflicts with "
            "valid/candidate-failure pair counts"
        )
    aggregation = {
        "statistical_unit": "case",
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
        "objective_outcome": {
            "semantics": protocol.objective_semantics,
            "aggregate": _primitive(stats),
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
            "first_error": _primitive(protocol.candidate_first_runtime_failure),
        },
    }
    from scion.protocol.experiment.proposal_evidence import (
        is_proposal_mechanism_evidence_envelope,
    )

    mechanism_evidence = None
    if is_proposal_mechanism_evidence_envelope(protocol.mechanism_evidence):
        mechanism_evidence = _primitive(protocol.mechanism_evidence)
    projected = _drop_empty(payload)
    if getattr(protocol, "runtime_model", None):
        projected["runtime_evidence_policy"] = (
            runtime_evidence_policy_for_protocol(protocol)
        )
    if mechanism_evidence is not None:
        # The verified generic envelope is already the visibility boundary.
        # Keep unavailable/empty problem-owned observations byte-for-byte;
        # interpreting them here would acquire problem semantics in core.
        projected["mechanism_evidence"] = mechanism_evidence
    return projected


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
    declared_fields = payload.get(_MEASUREMENT_VISIBLE_FIELDS_KEY, ())
    if not isinstance(declared_fields, (list, tuple)) or not all(
        isinstance(field, str) and field.strip() for field in declared_fields
    ):
        declared_fields = ()
    visible_fields = tuple(
        dict.fromkeys(str(field).strip() for field in declared_fields)
    )
    projected: dict[str, Any] = {}
    for key in (*_MEASUREMENT_VISIBLE_ENVELOPE_FIELDS, *visible_fields):
        if key in _MEASUREMENT_PRIVATE_FIELDS or key not in payload:
            continue
        projected[key] = _project_measurement_value(payload[key])
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
    "CANONICAL_SCREENING_HISTORY_KEY",
    "ContextManager",
    "campaign_research_rejection_history",
    "canonical_screening_history",
    "canonical_screening_record",
    "persist_canonical_screening_record",
]
