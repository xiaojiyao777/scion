"""ContextManager orchestration for proposal prompt contexts."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Mapping, Optional

from scion.config.problem import ProblemSpec
from scion.core.forced_surface import validate_forced_surface_request
from scion.core.models import (
    Branch,
    ChampionState,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.core.explore_step.branch_lesson_usage import (
    branch_lesson_usage_requirement_from_records,
    project_branch_lesson_records,
)
from scion.core.repeated_contract_failures import (
    contract_preview_failure_signature_feedback,
)
from scion.measurement.readiness import measurement_readiness_status
from scion.problem.providers import (
    active_subject_code_constraints_payload,
    active_subject_taxonomy_payload,
    resolve_solver_design_prompt_provider,
)
from scion.proposal.context_ablation import normalize_proposal_context_ablation
from scion.proposal.context.feedback import (
    _build_agent_quality_feedback,
    _build_champion_baselines,
    _build_experiment_history,
    _filter_hypothesis_prompt_steps,
)
from scion.proposal.context.branch_dossier import (
    build_branch_dossier,
    render_branch_dossier,
)
from scion.proposal.context.branch_followup import (
    branch_created_files,
    branch_current_file_sources,
    branch_touched_files,
    build_branch_followup_policy,
    render_branch_followup_policy,
)
from scion.proposal.context.cross_branch_research import (
    build_cross_branch_research_map,
    render_cross_branch_research_map,
)
from scion.proposal.context.research_shape import (
    build_proposal_research_shape_diagnostics,
)
from scion.proposal.context.problem_adapter import (
    _build_operator_interface_spec,
    _build_problem_object,
    _build_problem_summary,
    _build_solver_mechanics,
    _get_adapter_problem_spec,
)
from scion.proposal.context.surfaces import (
    _build_forced_surface_constraint,
    _build_inactive_surface_exclusion_block,
    _build_research_surfaces_block,
    _find_research_surface,
    _get_research_surfaces,
    _hypothesis_visible_research_surfaces,
    _include_operator_files_for_research_code,
    _is_solver_design_context_surface,
    _solver_design_surface_names,
    _surface_target_files_for_names,
)

from .code_context import (
    _build_solver_design_api_manifest,
    _build_solver_design_branch_current_integration_files,
    _read_champion_research_code,
    _read_reference_operators,
)
from .guidance import (
    _build_failure_pattern_warning,
    _build_objective_guidance,
    _build_objective_opportunity_profile,
    _build_objective_policy_guidance,
    _build_recent_objective_feedback,
    _build_search_control_guidance,
    _build_solver_design_boundary_guidance,
    _build_strategy_guidance,
    _get_family_taxonomy,
)
from .history import (
    _build_branch_direction_prompt,
    _extract_families_from_steps,
    _summarise_active_hypotheses,
    _summarise_blacklist,
    _summarise_siblings,
    build_exploration_coverage,
)
from .io import (
    _available_hypothesis_actions,
    _build_champion_stats,
    _expand_surface_targets_for_champion,
    _expand_surface_targets_for_root,
    _list_branch_surface_files,
    _list_champion_operator_files,
    _list_champion_surface_files,
    _read_branch_code,
    _read_target_file_from_root,
)
from .rendering import _format_hypothesis, _hypothesis_implementation_brief
from .runtime import _build_runtime_feedback, _build_runtime_failure_guidance


def _normalize_measurement_governance_mode(value: Any | None) -> str:
    text = "on" if value is None else str(value).strip().lower().replace("-", "_")
    if text in {"on", "record_only"}:
        return text
    raise ValueError("measurement_governance must be on or record_only")


def _target_file_exists_in_root(root: str, target_file: Optional[str]) -> bool:
    if not root or not target_file:
        return False
    normalized = str(target_file).replace("\\", "/").lstrip("/")
    if not normalized:
        return False
    candidate = os.path.join(root, normalized)
    return os.path.isfile(candidate)


def _render_branch_current_target_file(target_file: str, content: str) -> str:
    return (
        f"File: {target_file}\n"
        "Provenance: branch_history_current; readable=True; "
        "source_status=current_branch_source\n"
        f"```python\n{content}\n```"
    )


def _render_missing_branch_current_target_file(target_file: str) -> str:
    return (
        f"File: {target_file}\n"
        "Provenance: missing_current_source; readable=False; "
        "source_status=missing_current_source; visibility=not_visible\n"
        "Current branch source is unavailable. Do not use this placeholder "
        "as editable source; read the current branch file before exact_replace "
        "or choose a target with visible current source.\n"
        f"```python\n# could not read {target_file}\n```"
    )


def _render_new_file_target_placeholder(target_file: str) -> str:
    return (
        f"File: {target_file}\n"
        "Provenance: new_file_placeholder; readable=False; "
        "source_status=new_file; visibility=new_file_placeholder\n"
        "This target file does not currently exist and may be created by a "
        "create_new proposal. Provide full file content for this new target; "
        "do not use exact_replace against this placeholder.\n"
        f"```python\n# new file placeholder for {target_file}\n```"
    )


def _build_launch_research_focus() -> dict[str, Any]:
    """Project prepared launch research focus into proposal-only context."""

    manifest_path = (
        os.environ.get("PREPARED_RUN_MANIFEST")
        or os.environ.get("SCION_PREPARED_RUN_MANIFEST")
        or ""
    ).strip()
    if not manifest_path:
        return {}
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(manifest, Mapping):
        return {}
    research_focus = manifest.get("research_focus")
    if not isinstance(research_focus, Mapping):
        return {}
    projected_focus = _project_launch_research_focus(research_focus)
    if not projected_focus:
        return {}
    return {
        "schema_version": "scion.launch_research_focus_prompt.v1",
        "taint": "prepared_launch_research_focus",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "decision_input_policy": "excluded_from_decision_features",
        "source": "PREPARED_RUN_MANIFEST",
        "manifest_path": manifest_path,
        "problem_family": _string_or_empty(manifest.get("problem_family")),
        "analysis_intent": _string_or_empty(manifest.get("analysis_intent")),
        "acceptance_focus": _string_items(manifest.get("acceptance_focus")),
        "research_focus": projected_focus,
    }


def _project_launch_research_focus(value: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "schema_version",
        "scope",
        "accepted_checkpoint",
        "current_question",
        "route_merge_exception_rule",
        "construction_seed_rule",
        "decision_boundary",
    )
    projected: dict[str, Any] = {
        field: _string_or_empty(value.get(field))
        for field in fields
        if _string_or_empty(value.get(field))
    }
    list_fields = (
        "default_avoid_directions",
        "required_evidence",
        "measurable_opportunity_classes",
    )
    for field in list_fields:
        items = _string_items(value.get(field))
        if items:
            projected[field] = items
    measurement = value.get("measurement_opportunity_diagnostics")
    if isinstance(measurement, Mapping):
        projected["measurement_opportunity_diagnostics"] = {
            key: child
            for key, child in {
                "schema_version": _string_or_empty(
                    measurement.get("schema_version")
                ),
                "metric": _string_or_empty(measurement.get("metric")),
                "runtime_model": _string_or_empty(
                    measurement.get("runtime_model")
                ),
                "pairing_validity": _string_or_empty(
                    measurement.get("pairing_validity")
                ),
                "practical_screen_delta": measurement.get(
                    "practical_screen_delta"
                ),
                "screening_mde_at_power_80": measurement.get(
                    "screening_mde_at_power_80"
                ),
                "recommended_min_seeds": measurement.get("recommended_min_seeds"),
                "reason_codes": _string_items(measurement.get("reason_codes")),
                "summary": _string_or_empty(measurement.get("summary")),
                "decision_features_excluded": measurement.get(
                    "decision_features_excluded"
                ),
                "proposal_visibility_only": measurement.get(
                    "proposal_visibility_only"
                ),
            }.items()
            if child not in ("", [], {}, None)
        }
    return projected


def _string_or_empty(value: Any) -> str:
    return str(value or "").strip()


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    items: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            items.append(text)
    return items


def _proposal_material_difference_requirement(branch: Branch) -> dict[str, Any]:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return {}
    raw_requirement = summary.get("material_difference_requirement")
    if not isinstance(raw_requirement, Mapping):
        return {}
    candidates = [
        _material_difference_candidate_projection(item)
        for item in summary.get("material_difference_requirement_candidates", []) or []
        if isinstance(item, Mapping)
    ]
    candidates = [item for item in candidates if item]
    return {
        key: value
        for key, value in {
            "schema_version": "proposal_material_difference_requirement.v1",
            "required": True,
            "record_id": str(raw_requirement.get("record_id") or "").strip(),
            "record_digest": str(raw_requirement.get("record_digest") or "").strip(),
            "record_type": str(raw_requirement.get("record_type") or "").strip(),
            "requirement_source": str(
                raw_requirement.get("requirement_source") or ""
            ).strip(),
            "reason": str(raw_requirement.get("reason") or "").strip(),
            "reason_codes": _string_list(raw_requirement.get("reason_codes")),
            "required_for": str(
                raw_requirement.get("required_for")
                or summary.get("material_difference_required_for")
                or ""
            ).strip(),
            "required_metadata_key": str(
                raw_requirement.get("required_metadata_key") or ""
            ).strip(),
            "candidate_count": _nonnegative_int(
                raw_requirement.get("candidate_count")
            ),
            "candidate_branch_ids": _string_list(
                raw_requirement.get("candidate_branch_ids")
            ),
            "candidate_release_reasons": sorted(
                {
                    str(item.get("release_reason") or "").strip()
                    for item in candidates
                    if str(item.get("release_reason") or "").strip()
                }
            ),
            "candidate_summaries": candidates[:8],
            "required_output_field": "material_difference",
            "required_output_contract": (
                "The next hypothesis must include a non-empty, non-boilerplate "
                "material_difference object with compact generic dimensions, "
                "signature digests, or evidence-status deltas."
            ),
            "proposal_visibility_only": True,
            "proposal_guidance_only": True,
            "audit_only": True,
            "decision_features_excluded": True,
        }.items()
        if value not in ("", None, [], {}, ())
    }


def _problem_measurement_diagnostics(
    problem_spec: ProblemSpec,
    *,
    adapter: Any | None = None,
) -> dict[str, Any]:
    measurement = getattr(problem_spec, "measurement", None)
    if measurement is None:
        adapter_payload = _adapter_problem_measurement_diagnostics(adapter)
        if not adapter_payload:
            return {}
        adapter_opportunities = _adapter_opportunity_diagnostics(adapter_payload)
        payload = {
            "schema_version": "problem_measurement_proposal_diagnostic.v1",
            "taint": "problem_owned_proposal_diagnostic",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "adapter_diagnostics": adapter_payload,
        }
        if adapter_opportunities:
            payload["opportunity_diagnostics"] = adapter_opportunities
        return payload
    effect_scale = getattr(measurement, "effect_scale", None)
    readiness = measurement_readiness_status(problem_spec)
    payload = {
        "schema_version": "problem_measurement_proposal_diagnostic.v1",
        "taint": "problem_owned_proposal_diagnostic",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "policy": (
            "Measurement/noise readiness facts may guide hypothesis planning "
            "only; raw calibration rows, BKS/gap details, validation/frozen "
            "case details, LLM text, prompt ratios, and cross-branch lessons "
            "remain excluded from DecisionFeatures."
        ),
        "runtime_model": str(getattr(measurement, "runtime_model", "") or ""),
        "pairing_validity": str(getattr(measurement, "pairing_validity", "") or ""),
        "effect_scale": {
            key: value
            for key, value in {
                "metric": str(getattr(effect_scale, "metric", "") or ""),
                "unit": str(getattr(effect_scale, "unit", "") or ""),
                "practical_delta_screen": getattr(
                    effect_scale,
                    "practical_delta_screen",
                    None,
                ),
                "practical_delta_validate": getattr(
                    effect_scale,
                    "practical_delta_validate",
                    None,
                ),
            }.items()
            if value not in ("", None, [], {}, ())
        },
        "measurement_readiness": readiness.to_diagnostic_payload(),
        "calibration": {
            key: value
            for key, value in {
                "calibration_ref": str(
                    getattr(measurement, "calibration_ref", "") or ""
                ),
                "calibration_max_age_days": getattr(
                    measurement,
                    "calibration_max_age_days",
                    None,
                ),
            }.items()
            if value not in ("", None, [], {}, ())
        },
    }
    adapter_payload = _adapter_problem_measurement_diagnostics(adapter)
    if adapter_payload:
        adapter_opportunities = _adapter_opportunity_diagnostics(adapter_payload)
        if adapter_opportunities:
            payload["opportunity_diagnostics"] = adapter_opportunities
        payload["adapter_diagnostics"] = adapter_payload
    return {
        key: value
        for key, value in payload.items()
        if value not in ("", None, [], {}, ())
    }


def _adapter_problem_measurement_diagnostics(adapter: Any | None) -> dict[str, Any]:
    hook = getattr(adapter, "render_problem_measurement_diagnostics", None)
    if not callable(hook):
        return {}
    try:
        payload = hook()
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _adapter_opportunity_diagnostics(
    adapter_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw_items = adapter_payload.get("opportunity_diagnostics")
    if not isinstance(raw_items, (list, tuple)):
        return []
    fields = (
        "diagnostic_type",
        "surface",
        "mechanism_family",
        "metric",
        "summary",
        "recommended_action",
        "confidence",
        "reason_codes",
    )
    items: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            continue
        projected: dict[str, Any] = {}
        for field in fields:
            if field not in raw:
                continue
            if field == "reason_codes":
                value = _string_list(raw.get(field))
            else:
                value = raw.get(field)
                if not isinstance(value, (str, int, float, bool)):
                    value = str(value) if value not in (None, "", [], {}, ()) else ""
                if isinstance(value, str):
                    value = value.strip()
            if value not in ("", None, [], {}, ()):
                projected[field] = value
        if projected:
            items.append(projected)
    return items[:8]


def _proposal_branch_lesson_usage_requirement(
    cross_branch_research_payload: Mapping[str, Any],
) -> dict[str, Any]:
    return branch_lesson_usage_requirement_from_records(
        cross_branch_research_payload.get("branch_lesson_records")
    )


def _record_proposal_branch_lesson_usage_requirement(
    branch: Branch,
    *,
    requirement: Mapping[str, Any],
    records: list[dict[str, Any]],
) -> None:
    summary = getattr(branch, "branch_evidence_summary", None)
    if not isinstance(summary, dict):
        return
    if not requirement:
        summary.pop("branch_lesson_usage_requirement", None)
        summary.pop("branch_lesson_records", None)
        summary.pop("branch_lesson_usage_required_for", None)
        return
    summary["branch_lesson_usage_requirement"] = dict(requirement)
    summary["branch_lesson_records"] = [dict(item) for item in records[:8]]
    required_for = str(requirement.get("required_for") or "").strip()
    if required_for:
        summary["branch_lesson_usage_required_for"] = required_for


def _material_difference_candidate_projection(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "branch_id": str(candidate.get("branch_id") or "").strip(),
            "release_reason": str(candidate.get("release_reason") or "").strip(),
            "scheduler_preference": str(
                candidate.get("scheduler_preference") or ""
            ).strip(),
            "lineage_status": str(candidate.get("lineage_status") or "").strip(),
            "branch_state": str(candidate.get("branch_state") or "").strip(),
            "branch_code_status": str(
                candidate.get("branch_code_status") or ""
            ).strip(),
            "screening_tier": str(candidate.get("screening_tier") or "").strip(),
            "candidate_source": str(candidate.get("candidate_source") or "").strip(),
        }.items()
        if value not in ("", None, [], {}, ())
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _nonnegative_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


class ContextManager:
    """Constructs context dicts for CreativeLayer calls.

    Exposure-control matrix (§5.3):
    ┌─────────────────────────┬─────────────────────────────────────────┐
    │ Context type            │ Excluded fields                         │
    ├─────────────────────────┼─────────────────────────────────────────┤
    │ hypothesis_context      │ validation/frozen results, raw metrics  │
    │ code_context            │ experiment stats, branch history        │
    │ fix_context             │ experiment stats, branch history        │
    └─────────────────────────┴─────────────────────────────────────────┘
    """

    def __init__(
        self,
        *,
        adapter=None,
        runtime_slow_threshold: float = 2.0,
        measurement_governance: str = "on",
        proposal_context_ablation: str = "full",
    ):
        self._adapter = adapter
        self._runtime_slow_threshold = runtime_slow_threshold
        self._measurement_governance = _normalize_measurement_governance_mode(
            measurement_governance
        )
        self._proposal_context_ablation = normalize_proposal_context_ablation(
            proposal_context_ablation
        )

    # ------------------------------------------------------------------
    # Round 1 — hypothesis context
    # ------------------------------------------------------------------

    def build_hypothesis_context(
        self,
        branch: Branch,
        champion: ChampionState,
        problem_spec: ProblemSpec,
        active_hypotheses: List[HypothesisRecord],
        blacklist: List[HypothesisRecord],
        sibling_branches: Optional[List[Branch]] = None,
        step_history: Optional[List[StepRecord]] = None,
        branch_workspace: Optional[str] = None,
        failure_streak: Optional[Dict[str, int]] = None,
        forced_locus: Optional[str] = None,
        forced_action: Optional[str] = None,
        forced_target_file: Optional[str] = None,
        forced_surface_diagnostic: bool = False,
        rejected_hypotheses: Optional[List[HypothesisRecord]] = None,
        search_memory: Optional[Any] = None,
        saturation_signals: Optional[List[Any]] = None,
        weight_opt_result: Optional[Any] = None,
        research_log: Optional[Any] = None,
        measurement_governance: Optional[str] = None,
        proposal_context_ablation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Context for generate_hypothesis (Round 1).

        Includes full problem summary, champion research code, branch experiment
        history, and blacklist. Deliberately excludes validation/frozen data.

        If branch_workspace is provided and differs from the champion snapshot,
        branch_code shows the modified research-surface files so the LLM can
        build on them.

        If failure_streak is provided, injects a failure pattern warning when
        any failure code has a streak >= 2.
        """
        problem_summary = _build_problem_summary(problem_spec, adapter=self._adapter)
        measurement_governance_mode = _normalize_measurement_governance_mode(
            self._measurement_governance
            if measurement_governance is None
            else measurement_governance
        )
        proposal_context_ablation_mode = normalize_proposal_context_ablation(
            self._proposal_context_ablation
            if proposal_context_ablation is None
            else proposal_context_ablation
        )
        problem_object = _build_problem_object(adapter=self._adapter)
        solver_mechanics = _build_solver_mechanics(adapter=self._adapter)
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
        declared_problem_boundary_surfaces = _solver_design_surface_names(
            research_surfaces
        )
        active_problem_boundary_surfaces = (
            []
            if forced_request is not None
            else declared_problem_boundary_surfaces
        )
        visible_research_surfaces = _hypothesis_visible_research_surfaces(
            research_surfaces,
            forced_surface=forced_request.surface if forced_request else None,
            active_problem_boundary_surfaces=active_problem_boundary_surfaces,
        )
        research_surfaces_block = _build_research_surfaces_block(
            visible_research_surfaces
        )
        legacy_surface_exclusion = _build_inactive_surface_exclusion_block(
            research_surfaces,
            visible_research_surfaces=visible_research_surfaces,
            active_problem_boundary_surfaces=active_problem_boundary_surfaces,
        )
        if legacy_surface_exclusion:
            research_surfaces_block = "\n".join(
                block
                for block in (research_surfaces_block, legacy_surface_exclusion)
                if block
            )
        champion_operators_code = _read_champion_research_code(
            champion,
            research_surfaces=visible_research_surfaces,
            include_operator_files=_include_operator_files_for_research_code(
                visible_research_surfaces
            ),
        )
        family_taxonomy = (
            _get_family_taxonomy(problem_spec)
            or _get_family_taxonomy(adapter_spec)
        )
        safe_hypothesis_steps = _filter_hypothesis_prompt_steps(step_history or [])
        experiment_history = _build_experiment_history(
            safe_hypothesis_steps, branch.branch_id, taxonomy=family_taxonomy
        )
        blacklist_summary = _summarise_blacklist(blacklist)
        solver_design_boundary_guidance = _build_solver_design_boundary_guidance(
            safe_hypothesis_steps,
            research_surfaces=research_surfaces,
            blacklist=blacklist,
            rejected_hypotheses=rejected_hypotheses or [],
        )
        sibling_summary = _summarise_siblings(sibling_branches or [])
        champion_stats = _build_champion_stats(champion)
        branch_code = (
            _read_branch_code(
                branch_workspace,
                champion,
                research_surfaces=visible_research_surfaces,
                include_operator_files=_include_operator_files_for_research_code(
                    visible_research_surfaces
                ),
            )
            if branch_workspace
            else None
        )
        branch_direction = _build_branch_direction_prompt(branch)

        # T07: Build family tracking and coverage (J-patch: use global step_history)
        all_steps = safe_hypothesis_steps
        targetable_operator_files = _list_champion_operator_files(champion)
        targetable_surface_files = _list_champion_surface_files(
            champion,
            research_surfaces=research_surfaces,
        )
        branch_surface_files = (
            _list_branch_surface_files(
                branch_workspace,
                research_surfaces=research_surfaces,
            )
            if branch_workspace
            else []
        )
        if branch_surface_files:
            targetable_surface_files = sorted(
                set(targetable_surface_files) | set(branch_surface_files)
            )
        active_boundary_declared_target_files = _surface_target_files_for_names(
            research_surfaces,
            active_problem_boundary_surfaces,
        )
        active_boundary_target_files = _expand_surface_targets_for_champion(
            champion,
            active_boundary_declared_target_files,
        )
        if branch_workspace:
            active_boundary_target_files = sorted(
                set(active_boundary_target_files)
                | set(
                    item
                    for item in _expand_surface_targets_for_root(
                        branch_workspace,
                        active_boundary_declared_target_files,
                    )
                    if "*" not in item
                )
            )
        effective_operator_categories = (
            active_problem_boundary_surfaces
            if active_problem_boundary_surfaces
            else list(problem_spec.operator_categories)
        )
        effective_targetable_files = (
            active_boundary_target_files
            if active_boundary_target_files
            else sorted(set(targetable_operator_files) | set(targetable_surface_files))
        )
        available_actions = _available_hypothesis_actions(
            targetable_operator_files,
            targetable_policy_files=targetable_surface_files,
        )
        forced_surface_name = (
            forced_request.surface
            if forced_request is not None and forced_surface_diagnostic
            else None
        )
        forced_action_name = (
            forced_request.action
            if forced_request is not None and forced_surface_diagnostic
            else None
        )
        effective_available_actions = (
            {forced_action_name}
            if forced_action_name
            else available_actions
        )
        families = _extract_families_from_steps(all_steps, taxonomy=family_taxonomy)
        exploration_coverage = (
            build_exploration_coverage(
                families,
                available_actions=effective_available_actions,
                forced_action=forced_action_name,
            )
            if families
            else ""
        )

        # T08: Build strategy guidance from family data (J-patch: global)
        strategy_guidance = (
            _build_strategy_guidance(
                families,
                problem_spec,
                available_actions=effective_available_actions,
                forced_surface=forced_surface_name,
                forced_action=forced_action_name,
                active_problem_boundary_surfaces=active_problem_boundary_surfaces,
            )
            if families
            else ""
        )

        # T10: Champion baseline hints from most recent screening experiment
        champion_baselines = _build_champion_baselines(safe_hypothesis_steps)

        # Sprint H2 T5: Failure pattern warning
        failure_pattern_warning = _build_failure_pattern_warning(failure_streak or {})

        # I3: Forced locus diversification / diagnostic surface constraint
        locus_constraint = ""
        if forced_request is not None:
            surface = _find_research_surface(
                research_surfaces,
                forced_request.surface,
            )
            locus_constraint = _build_forced_surface_constraint(
                surface=surface,
                surface_name=forced_request.surface,
                action=forced_request.action,
                target_file=forced_request.target_file,
                diagnostic=forced_surface_diagnostic,
                blocking_hypotheses=[
                    *(active_hypotheses or []),
                    *(blacklist or []),
                    *(rejected_hypotheses or []),
                ],
            )

        # J1: Render search memory (cross-branch search history)
        search_memory_block = ""
        if search_memory is not None:
            try:
                search_memory_block = search_memory.render(
                    view="hypothesis",
                    branch_id=branch.branch_id,
                )
            except TypeError:
                search_memory_block = search_memory.render(view="hypothesis")

        # J2: Render saturation signals
        saturation_block = ""
        if saturation_signals:
            from scion.proposal.saturation import render_saturation_signals
            saturation_block = render_saturation_signals(saturation_signals)

        # Objective policy/guidance is generic: lexicographic protection or
        # weighted-sum scalar improvement, plus recent screening tendencies.
        objective_policy_guidance = _build_objective_policy_guidance(adapter_spec)
        objective_feedback = _build_recent_objective_feedback(
            safe_hypothesis_steps, branch.branch_id, adapter_spec
        )
        objective_opportunity_profile = _build_objective_opportunity_profile(
            safe_hypothesis_steps, adapter_spec
        )
        objective_guidance = _build_objective_guidance(
            saturation_signals, objective_feedback=objective_feedback
        )
        solver_design_prompt_provider = None
        if declared_problem_boundary_surfaces:
            solver_design_prompt_provider = resolve_solver_design_prompt_provider(
                problem_spec=problem_spec,
                adapter=self._adapter,
            )
        search_control_guidance = _build_search_control_guidance(
            families,
            safe_hypothesis_steps,
            adapter_spec,
            forced_surface=forced_surface_name,
            solver_design_prompt_provider=solver_design_prompt_provider,
        )
        runtime_feedback = _build_runtime_feedback(
            safe_hypothesis_steps,
            slow_case_threshold=self._runtime_slow_threshold,
        )
        runtime_failure_guidance = _build_runtime_failure_guidance(
            safe_hypothesis_steps,
            problem_spec=problem_spec,
            adapter_spec=adapter_spec,
            forced_surface=forced_surface_name,
        )
        agent_quality_feedback = _build_agent_quality_feedback(
            safe_hypothesis_steps,
            branch.branch_id,
        )
        branch_dossier_payload = build_branch_dossier(
            branch,
            safe_hypothesis_steps,
        )
        branch_dossier = render_branch_dossier(branch_dossier_payload)
        cross_branch_research_payload = build_cross_branch_research_map(
            branch,
            [branch, *(sibling_branches or [])],
            safe_hypothesis_steps,
            available_actions=effective_available_actions,
        )
        cross_branch_research = render_cross_branch_research_map(
            cross_branch_research_payload
        )
        research_shape_diagnostics = build_proposal_research_shape_diagnostics(
            cross_branch_research_payload
        )
        branch_followup_policy_payload = build_branch_followup_policy(
            branch,
            safe_hypothesis_steps,
        )
        branch_followup_policy = render_branch_followup_policy(
            branch_followup_policy_payload
        )
        material_difference_requirement = _proposal_material_difference_requirement(
            branch
        )
        branch_lesson_records = project_branch_lesson_records(
            cross_branch_research_payload.get("branch_lesson_records")
        )
        branch_lesson_usage_requirement = (
            _proposal_branch_lesson_usage_requirement(
                cross_branch_research_payload
            )
        )
        _record_proposal_branch_lesson_usage_requirement(
            branch,
            requirement=branch_lesson_usage_requirement,
            records=branch_lesson_records,
        )
        contract_preview_failure_signature = (
            contract_preview_failure_signature_feedback(branch)
        )

        # W10: Weight optimization feedback (coarse-grained operator signals)
        weight_opt_block = ""
        if weight_opt_result is not None:
            from scion.proposal.weight_feedback import render_weight_feedback
            weight_opt_block = render_weight_feedback(weight_opt_result)

        # J-patch: Render research log (cross-branch trajectory)
        research_log_block = ""
        if research_log is not None:
            research_log_block = research_log.render(view="hypothesis")

        problem_measurement_diagnostics = (
            _problem_measurement_diagnostics(problem_spec, adapter=self._adapter)
            if measurement_governance_mode == "on"
            else {}
        )
        launch_research_focus = _build_launch_research_focus() or ""

        return {
            "problem_summary": problem_summary,
            "problem_object": problem_object,
            "solver_mechanics": solver_mechanics,
            "measurement_governance": measurement_governance_mode,
            "proposal_context_ablation": proposal_context_ablation_mode,
            "branch_id": branch.branch_id,
            "champion_version": champion.version,
            "operator_categories": ", ".join(effective_operator_categories),
            "research_surfaces": research_surfaces_block,
            "available_actions": ", ".join(sorted(available_actions)),
            "targetable_files": ", ".join(effective_targetable_files),
            "active_problem_boundary_surfaces": ", ".join(
                active_problem_boundary_surfaces
            ),
            "champion_operators_code": champion_operators_code,
            "champion_stats": champion_stats,
            "experiment_history": experiment_history,
            "blacklist_summary": blacklist_summary,
            "solver_design_boundary_guidance": solver_design_boundary_guidance,
            "sibling_summary": sibling_summary,
            "branch_code": branch_code,
            "branch_direction": branch_direction,
            "branch_dossier": branch_dossier,
            "branch_dossier_payload": branch_dossier_payload,
            "cross_branch_research": cross_branch_research,
            "cross_branch_research_payload": cross_branch_research_payload,
            "research_shape_diagnostics": research_shape_diagnostics,
            "launch_research_focus": launch_research_focus,
            "cross_branch_research_audit_records": (
                cross_branch_research_payload.get(
                    "material_difference_audit_records",
                    [],
                )
            ),
            "cross_branch_research_session_metadata": (
                cross_branch_research_payload.get(
                    "cross_branch_research_metadata",
                    {},
                )
            ),
            "material_difference_requirement": material_difference_requirement,
            "branch_lesson_usage_requirement": (
                branch_lesson_usage_requirement
            ),
            "branch_lesson_records": branch_lesson_records,
            "contract_preview_failure_signature": (
                contract_preview_failure_signature
            ),
            "branch_followup_policy": branch_followup_policy,
            "branch_followup_policy_payload": branch_followup_policy_payload,
            "exploration_coverage": exploration_coverage,
            "strategy_guidance": strategy_guidance,
            "champion_baselines": champion_baselines,
            "failure_pattern_warning": failure_pattern_warning,
            "locus_constraint": locus_constraint,
            "forced_surface": forced_request.surface if forced_request else "",
            "forced_action": forced_request.action if forced_request else "",
            "forced_target_file": (
                forced_request.target_file if forced_request else ""
            ),
            "objective_policy_guidance": objective_policy_guidance,
            "problem_measurement_diagnostics": problem_measurement_diagnostics,
            "objective_opportunity_profile": objective_opportunity_profile,
            "objective_guidance": objective_guidance,
            "solver_design_prompt_provider": solver_design_prompt_provider,
            "solver_design_prompt_provider_ref": (
                (
                    f"{type(solver_design_prompt_provider).__module__}."
                    f"{type(solver_design_prompt_provider).__qualname__}"
                )
                if solver_design_prompt_provider is not None
                else ""
            ),
            "search_control_guidance": search_control_guidance,
            "runtime_feedback": runtime_feedback,
            "runtime_failure_guidance": runtime_failure_guidance,
            "agent_quality_feedback": agent_quality_feedback,
            "search_memory": search_memory_block,
            "saturation_signal": saturation_block,
            "weight_opt_feedback": weight_opt_block,
            "research_log": research_log_block,
            "active_hyp_summary": _summarise_active_hypotheses(active_hypotheses),
        }

    # ------------------------------------------------------------------
    # Round 2 — code context
    # ------------------------------------------------------------------

    def build_code_context(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        champion: ChampionState,
        problem_spec: ProblemSpec,
        prior_failure: Optional[str] = None,
        branch_workspace: Optional[str] = None,
        step_history: Optional[list[StepRecord]] = None,
    ) -> Dict[str, Any]:
        """Context for generate_code (Round 2).

        Contains problem summary, hypothesis details, target file content,
        research-surface interface spec, and import whitelist.
        Does NOT contain experiment stats or branch history.
        If prior_failure is set, a previous code generation attempt failed for
        this hypothesis — the failure detail is included so the LLM can learn.
        If branch_workspace is set for a previously verified branch, read the
        current branch research-object code rather than falling back to the
        champion snapshot.
        """
        problem_summary = _build_problem_summary(problem_spec, adapter=self._adapter)
        problem_object = _build_problem_object(adapter=self._adapter)
        solver_mechanics = _build_solver_mechanics(adapter=self._adapter)
        hypothesis_detail = _format_hypothesis(hypothesis)
        adapter_spec = _get_adapter_problem_spec(self._adapter)
        research_surfaces = _get_research_surfaces(problem_spec, adapter_spec)
        surface = _find_research_surface(research_surfaces, hypothesis.change_locus)
        source_root = (
            branch_workspace
            if branch_workspace and os.path.isdir(branch_workspace)
            else champion.code_snapshot_path
        )
        branch_step_history = step_history or []
        branch_file_sources = branch_current_file_sources(
            branch,
            branch_step_history,
        )
        branch_workspace_visible = bool(
            branch_workspace and os.path.isdir(branch_workspace)
        )
        branch_created = (
            branch_created_files(branch, branch_step_history)
            if branch_workspace_visible or branch_file_sources
            else ()
        )
        branch_touched = (
            branch_touched_files(branch, branch_step_history)
            if branch_workspace_visible or branch_file_sources
            else ()
        )
        normalized_target_file = str(hypothesis.target_file or "").replace(
            "\\",
            "/",
        ).lstrip("/")
        target_file_exists = _target_file_exists_in_root(
            source_root,
            hypothesis.target_file,
        )
        if normalized_target_file in branch_file_sources:
            target_file_exists = True
            target_file_code = _render_branch_current_target_file(
                normalized_target_file,
                branch_file_sources[normalized_target_file],
            )
        elif (
            normalized_target_file
            and normalized_target_file in set(branch_created) | set(branch_touched)
        ):
            target_file_exists = False
            target_file_code = _render_missing_branch_current_target_file(
                normalized_target_file
            )
        elif hypothesis.action == "create_new" and not target_file_exists:
            target_file_code = _render_new_file_target_placeholder(
                normalized_target_file
            )
        else:
            target_file_code = _read_target_file_from_root(
                source_root,
                hypothesis.target_file,
            )
        champion_operators_code = _read_champion_research_code(
            champion,
            research_surfaces=research_surfaces,
        )
        # Operator surfaces get reference operators as style/interface reference.
        reference_operators = _read_reference_operators(
            champion,
            hypothesis.change_locus,
            problem_spec,
            research_surfaces=research_surfaces,
        )
        operator_interface_spec = _build_operator_interface_spec(
            problem_spec,
            adapter=self._adapter,
            surface_name=hypothesis.change_locus,
        )
        import_whitelist = "\n".join(
            f"  - {imp}" for imp in problem_spec.search_space.import_whitelist
        )

        ctx: Dict[str, Any] = {
            "problem_summary": problem_summary,
            "problem_object": problem_object,
            "solver_mechanics": solver_mechanics,
            "branch_id": branch.branch_id,
            "champion_version": champion.version,
            "hypothesis_detail": hypothesis_detail,
            "hypothesis_implementation_brief": _hypothesis_implementation_brief(
                hypothesis
            ),
            "target_file": hypothesis.target_file,
            "target_file_code": target_file_code,
            "target_file_exists": target_file_exists,
            "solver_design_source_root": source_root,
            "solver_design_champion_root": champion.code_snapshot_path,
            "champion_operators_code": champion_operators_code,
            "reference_operators": reference_operators,
            "operator_interface_spec": operator_interface_spec,
            "research_surface_name": hypothesis.change_locus,
            "research_surface_kind": getattr(surface, "kind", "operator"),
            "import_whitelist": import_whitelist,
            "editable_patterns": ", ".join(problem_spec.search_space.editable),
            "frozen_patterns": ", ".join(problem_spec.search_space.frozen),
        }
        contract_preview_failure_signature = (
            contract_preview_failure_signature_feedback(branch)
        )
        if contract_preview_failure_signature:
            ctx["contract_preview_failure_signature"] = (
                contract_preview_failure_signature
            )
        if branch_workspace and os.path.isdir(branch_workspace):
            ctx["branch_workspace"] = branch_workspace
        active_subject_taxonomy = active_subject_taxonomy_payload(
            problem_spec=problem_spec,
            adapter=self._adapter,
            surface=hypothesis.change_locus,
        )
        if active_subject_taxonomy:
            ctx["active_subject_taxonomy"] = active_subject_taxonomy
        active_subject_code_constraints = active_subject_code_constraints_payload(
            context=ctx,
            problem_spec=problem_spec,
            adapter=self._adapter,
            surface=hypothesis.change_locus,
        )
        if active_subject_code_constraints:
            ctx["active_subject_code_constraints"] = active_subject_code_constraints
        if _is_solver_design_context_surface(hypothesis.change_locus, surface):
            solver_design_prompt_provider = resolve_solver_design_prompt_provider(
                problem_spec=problem_spec,
                adapter=self._adapter,
            )
            if solver_design_prompt_provider is not None:
                ctx["solver_design_prompt_provider"] = solver_design_prompt_provider
                ctx["solver_design_prompt_provider_ref"] = (
                    f"{type(solver_design_prompt_provider).__module__}."
                    f"{type(solver_design_prompt_provider).__qualname__}"
                )
            ctx["solver_design_api_manifest"] = _build_solver_design_api_manifest(
                source_root=source_root,
                champion_root=champion.code_snapshot_path,
                target_file=hypothesis.target_file,
                provider=solver_design_prompt_provider,
            )
            ctx["solver_design_branch_current_integration_files"] = (
                _build_solver_design_branch_current_integration_files(
                    source_root=source_root,
                    champion_root=champion.code_snapshot_path,
                    target_file=hypothesis.target_file,
                    provider=solver_design_prompt_provider,
                    branch_created_files=branch_created,
                    branch_touched_files=branch_touched,
                    branch_current_file_sources=branch_file_sources,
                )
            )
        if prior_failure is not None:
            ctx["prior_code_failure"] = prior_failure
            ctx["pending_code_retry_policy"] = {
                "status": "approved_hypothesis_code_repair",
                "fresh_proposal_duplicate_gate": "skip_for_same_approved_hypothesis",
                "rule": (
                    "Repair code for the already approved hypothesis. Do not "
                    "rename the mechanism or generate a fresh replacement "
                    "hypothesis unless the framework explicitly closes this "
                    "pending retry."
                ),
            }
        return ctx

    # ------------------------------------------------------------------
    # Fix context — after light verification failure
    # ------------------------------------------------------------------

    def build_fix_context(
        self,
        branch: Branch,
        patch: PatchProposal,
        verification_result: VerificationResult,
        problem_spec: ProblemSpec,
        failure_streak: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Context for fix_code (after a light verification failure).

        Contains the failed patch, failure details, and operator interface spec.
        Does NOT contain experiment stats.
        If failure_streak is provided, injects a failure pattern warning.
        """
        problem_summary = _build_problem_summary(problem_spec, adapter=self._adapter)
        problem_object = _build_problem_object(adapter=self._adapter)
        solver_mechanics = _build_solver_mechanics(adapter=self._adapter)
        failed_checks = [c for c in verification_result.checks if not c.passed]
        failure_detail = (
            f"Severity: {verification_result.failure_severity or 'unknown'}\n"
            f"First failure: {verification_result.first_failure or 'N/A'}\n"
            "Details:\n"
            + "\n".join(
                f"  [{c.name}] ({c.severity}) {c.detail}" for c in failed_checks
            )
        ) or "No detail available."

        operator_interface_spec = _build_operator_interface_spec(problem_spec, adapter=self._adapter)
        import_whitelist = "\n".join(
            f"  - {imp}" for imp in problem_spec.search_space.import_whitelist
        )

        failure_pattern_warning = _build_failure_pattern_warning(failure_streak or {})

        ctx = {
            "problem_summary": problem_summary,
            "problem_object": problem_object,
            "solver_mechanics": solver_mechanics,
            "branch_id": branch.branch_id,
            "original_code": (
                f"File: {patch.file_path}\nAction: {patch.action}\n"
                f"```python\n{patch.code_content}\n```"
            ),
            "failure_detail": failure_detail,
            "operator_interface_spec": operator_interface_spec,
            "import_whitelist": import_whitelist,
            "editable_patterns": ", ".join(problem_spec.search_space.editable),
            "frozen_patterns": ", ".join(problem_spec.search_space.frozen),
        }
        if failure_pattern_warning:
            ctx["failure_pattern_warning"] = failure_pattern_warning
        return ctx
