"""Branch card and prompt-context rendering helpers."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.branch_cards_evidence import (
    _best_checkpoint_mapping,
    _best_checkpoint_reason_codes,
    _best_checkpoint_scalar,
    _branch_block,
    _branch_block_codes,
    _branch_card_allowed_actions,
    _branch_card_forbidden_actions,
    _branch_code_retention_status,
    _branch_case_outcomes,
    _branch_evidence_retention_status,
    _branch_evidence_codes,
    _branch_evidence_summary,
    _branch_fresh_runtime_followup,
    _branch_generic_evidence_summary,
    _branch_lifecycle_block,
    _branch_lifecycle_block_codes,
    _branch_mechanism_evidence_contract,
    _branch_phase_activation_summary,
    _branch_rollback_codes,
    _branch_runtime_evidence_confidence,
    _branch_runtime_evidence_pressure_count,
    _branch_state_value,
    _current_gate_observation_codes,
    _current_reason_codes,
    _history_mapping_list,
    _history_reason_codes,
    _is_current_gate_observation_code,
    _is_lifecycle_action_code,
    _is_proposal_block_code,
    _lifecycle_action_reason_codes,
    _mapping_codes,
    _metric_value,
    _optional_float,
    _optional_int,
    _proposal_block_codes,
    _tier_from_status,
    _why_abandoned_codes,
    _why_not_promoted_codes,
)
from scion.core.branch_cards_guidance import (
    branch_hygiene_guidance_from_context as _render_branch_hygiene_guidance,
)
from scion.core.branch_cards_rendering import (
    _card_list,
    _card_mapping,
    _card_mapping_list,
    _compact_card_value,
    _format_case_outcomes,
    _format_evidence_summary,
    _format_phase_activation_history,
    _format_phase_activation_summary,
    branch_prompt_card_from_context as _render_branch_prompt_card_from_context,
)
from scion.core.branch_cards_runtime import (
    _runtime_evidence_prompt_advisory_projection,
    _runtime_saturated_diversity_guidance,
)
from scion.core.branch_cards_slots import active_slot_inventory_from_branch_cards
from scion.core.branch_hygiene import (
    BRANCH_LOCAL_FOLLOWUP_MODE,
    BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE,
    CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM,
    NO_UNRELATED_MECHANISM_IDS,
    OPEN_EXPLORATION_ALLOWED,
    OPEN_EXPLORATION_MODE,
    REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK,
    SAME_MECHANISM_ALLOWED_ACTIONS,
    SAME_MECHANISM_FOLLOWUP_ONLY,
    SAME_MECHANISM_ONLY_MODE,
    WIRING_SUSPECT_REQUIRES_REPAIR,
    branch_checkpoint_status,
    branch_code_status,
    branch_has_retained_checkpoint,
    branch_is_parked_lineage,
    branch_lifecycle_closure_classification,
    branch_lifecycle_reroute_context,
    branch_lineage_status,
    branch_mechanism_ids,
    branch_requires_repair_focus,
    branch_requires_same_mechanism_followup,
)
from scion.core.models import Branch
from scion.core.scheduler import (
    branch_runtime_evidence_clean_fork_pressure_summary,
    branch_active_slot_release_reason,
    branch_scheduling_status,
)


def branch_prompt_card(branch: Branch | None) -> str:
    """Compact generic branch card for APS prompts and sibling summaries."""
    context = branch_hygiene_context(branch)
    return branch_prompt_card_from_context(context)


def branch_prompt_card_from_context(context: Mapping[str, Any]) -> str:
    """Render an already reconciled generic branch-card context."""
    return _render_branch_prompt_card_from_context(context)


def branch_hygiene_context(branch: Branch | None) -> dict[str, Any]:
    """Prompt/status payload that makes branch-code provenance explicit."""
    status = branch_code_status(branch)
    last_screening_feedback_tier = (
        getattr(branch, "last_screening_feedback_tier", None)
        if branch is not None
        else None
    )
    last_telemetry_outcome = (
        getattr(branch, "last_telemetry_outcome", None)
        if branch is not None
        else None
    )
    repair_focus_required = branch_requires_repair_focus(branch)
    same_mechanism_followup_required = branch_requires_same_mechanism_followup(
        branch
    )
    scheduling_status = (
        branch_scheduling_status(branch) if branch is not None else None
    )
    weak_positive_followup = bool(
        scheduling_status
        and scheduling_status.lane == "weak_positive_followup"
    )
    parked_lineage = branch_is_parked_lineage(branch)
    final_classification = branch_lifecycle_closure_classification(branch)
    classification = str(final_classification.get("classification") or "")
    replay_blocked = classification == "replay_blocked"
    strict_same_mechanism_followup = (
        same_mechanism_followup_required
        and not weak_positive_followup
        and not replay_blocked
    )
    followup_policy = (
        "parked_lineage_clean_fork_only"
        if parked_lineage
        else "fresh_runtime_replay_blocked_clean_fork_required"
        if replay_blocked
        else
        BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE
        if weak_positive_followup
        else
        SAME_MECHANISM_FOLLOWUP_ONLY
        if same_mechanism_followup_required
        else OPEN_EXPLORATION_ALLOWED
    )
    generation_mode = (
        "clean_fork_only"
        if parked_lineage or replay_blocked
        else
        BRANCH_LOCAL_FOLLOWUP_MODE
        if weak_positive_followup
        else
        SAME_MECHANISM_ONLY_MODE
        if strict_same_mechanism_followup
        else OPEN_EXPLORATION_MODE
    )
    clean_fork_policy = (
        "parked_lineage_clean_fork_required"
        if parked_lineage
        else "fresh_runtime_replay_blocked_missing_identity"
        if replay_blocked
        else
        CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM
        if strict_same_mechanism_followup
        else None
    )
    protected_mechanism_ids = list(branch_mechanism_ids(branch))
    allowed_mechanism_ids = (
        list(protected_mechanism_ids)
        if strict_same_mechanism_followup
        else []
    )
    if repair_focus_required:
        baseline_policy = "champion_required_for_repair"
        repair_focus_reason = WIRING_SUSPECT_REQUIRES_REPAIR
    elif parked_lineage:
        baseline_policy = "parked_lineage_clean_fork_required"
        repair_focus_reason = None
    elif replay_blocked:
        baseline_policy = "fresh_runtime_replay_blocked_clean_fork_required"
        repair_focus_reason = None
    elif weak_positive_followup:
        baseline_policy = "branch_workspace_branch_local_followup"
        repair_focus_reason = None
    elif status.startswith("active_"):
        baseline_policy = "branch_workspace_same_mechanism_followup_only"
        repair_focus_reason = None
    else:
        baseline_policy = "clean"
        repair_focus_reason = None
    lineage_status = (
        scheduling_status.lineage_status
        if scheduling_status is not None
        else branch_lineage_status(branch)
    )
    current_head_status = status
    state_value = _branch_state_value(branch)
    counts_toward_active_slots = (
        scheduling_status.consumes_active_slot
        if scheduling_status is not None
        else False
    )
    if replay_blocked:
        counts_toward_active_slots = False
    current_head_active_slot_release_reason = (
        scheduling_status.release_reason
        if scheduling_status is not None
        else ""
    )
    if not current_head_active_slot_release_reason and branch is not None:
        current_head_active_slot_release_reason = branch_active_slot_release_reason(
            branch
        )
    if replay_blocked and not current_head_active_slot_release_reason:
        current_head_active_slot_release_reason = (
            "fresh_runtime_replay_blocked_missing_identity"
        )
    runtime_evidence_pressure_count = _branch_runtime_evidence_pressure_count(branch)
    fresh_runtime_followup = _branch_fresh_runtime_followup(branch)
    fresh_runtime_pending = bool(
        fresh_runtime_followup.get("fresh_runtime_pending")
    )
    fresh_runtime_required = bool(
        fresh_runtime_followup.get("fresh_runtime_required")
    )
    mechanism_evidence_contract = _branch_mechanism_evidence_contract(branch)
    mechanism_followup_required = bool(
        mechanism_evidence_contract.get("followup_required")
        and mechanism_evidence_contract.get("decision_features_excluded") is True
    )
    candidate_code_retention_status = _branch_code_retention_status(branch)
    evidence_retention_status = _branch_evidence_retention_status(branch)
    followup_required = bool(
        fresh_runtime_required
        or fresh_runtime_followup.get("followup_required")
        or mechanism_followup_required
    )
    followup_recommended = bool(
        followup_required
        or weak_positive_followup
        or fresh_runtime_followup.get("followup_recommended")
    )
    runtime_low_confidence_advisory = (
        _runtime_evidence_prompt_advisory_projection(
            branch_runtime_evidence_clean_fork_pressure_summary(branch)
        )
    )
    best_checkpoint_status = branch_checkpoint_status(branch)
    rollback_count = (
        max(0, int(getattr(branch, "rollback_count", 0) or 0))
        if branch is not None
        else 0
    )
    latest_head_failed = status in {
        "discarded",
        "regressed_followup",
        "quality_regression",
        "active_quality_regression",
    }
    lineage_retained_checkpoint = branch_has_retained_checkpoint(branch)
    allowed_next_actions = _branch_card_allowed_actions(
        branch,
        lineage_status=lineage_status,
        strict_same_mechanism_followup=strict_same_mechanism_followup,
        repair_focus_required=repair_focus_required,
    )
    forbidden_next_actions = _branch_card_forbidden_actions(
        branch,
        lineage_status=lineage_status,
        strict_same_mechanism_followup=strict_same_mechanism_followup,
        latest_head_failed=latest_head_failed,
        has_checkpoint=lineage_retained_checkpoint,
    )
    context = {
        "branch_id": getattr(branch, "branch_id", None) if branch is not None else None,
        "lineage_id": (
            getattr(branch, "lineage_id", None)
            or getattr(branch, "branch_id", None)
        )
        if branch is not None
        else None,
        "direction": getattr(branch, "direction", None) if branch is not None else None,
        "status": state_value,
        "branch_code_status": status,
        "lineage_status": lineage_status,
        "current_head_status": current_head_status,
        "candidate_code_retention_status": candidate_code_retention_status,
        "candidate_code_retained": candidate_code_retention_status
        in {"retained", "checkpoint_retained"},
        "evidence_retention_status": evidence_retention_status,
        "candidate_evidence_retained": evidence_retention_status == "retained",
        "followup_recommended": followup_recommended,
        "followup_required": followup_required,
        "fresh_runtime_pending": fresh_runtime_pending,
        "fresh_runtime_required": fresh_runtime_required,
        "fresh_runtime_followup": fresh_runtime_followup,
        "mechanism_evidence_contract": mechanism_evidence_contract,
        "mechanism_followup_required": mechanism_followup_required,
        "final_branch_classification": final_classification,
        "branch_final_classification": classification,
        "branch_next_action": final_classification.get("next_action"),
        "branch_classification_reason": final_classification.get("reason"),
        "active_slot_status": (
            "active_slot"
            if counts_toward_active_slots
            else "parked_lineage"
            if current_head_active_slot_release_reason == "parked_lineage"
            or branch_is_parked_lineage(branch)
            else "released_active_slot"
            if current_head_active_slot_release_reason
            else "inactive"
        ),
        "counts_toward_active_slots": counts_toward_active_slots,
        "current_head_active_slot_release_reason": (
            current_head_active_slot_release_reason
        ),
        "retained_checkpoint_no_effect_current_head_released": (
            current_head_active_slot_release_reason
            == "retained_checkpoint_no_effect_current_head"
        ),
        "branch_scheduling_status": (
            scheduling_status.as_dict()
            if scheduling_status is not None
            else None
        ),
        "branch_scheduling_lane": (
            scheduling_status.lane
            if scheduling_status is not None
            else "not_schedulable"
        ),
        "branch_scheduling_next_action_reason": (
            scheduling_status.next_action_reason
            if scheduling_status is not None
            else "inspect_branch_state"
        ),
        "best_checkpoint_status": best_checkpoint_status,
        "best_quality_checkpoint_id": (
            getattr(branch, "best_quality_checkpoint_id", None)
            if branch is not None
            else None
        ),
        "last_valid_checkpoint_id": (
            getattr(branch, "last_valid_checkpoint_id", None)
            if branch is not None
            else None
        ),
        "rollback_count": rollback_count,
        "last_rollback_reason": (
            getattr(branch, "last_rollback_reason", None)
            if branch is not None
            else None
        ),
        "allowed_next_actions": allowed_next_actions,
        "forbidden_next_actions": forbidden_next_actions,
        "latest_head_failed": latest_head_failed,
        "lineage_retained_checkpoint": lineage_retained_checkpoint,
        "mechanism_ids": list(protected_mechanism_ids),
        "generic_evidence_summary": _branch_generic_evidence_summary(
            branch,
            current_tier=last_screening_feedback_tier,
        ),
        "current_head_generic_evidence_summary": _branch_generic_evidence_summary(
            branch,
            current_tier=last_screening_feedback_tier,
        ),
        "case_level_winners": _branch_case_outcomes(branch, "case_level_winners"),
        "case_level_losses": _branch_case_outcomes(branch, "case_level_losses"),
        "phase_activation_summary": _branch_phase_activation_summary(branch),
        "current_head_phase_activation_summary": _branch_phase_activation_summary(
            branch
        ),
        "runtime_evidence_confidence": _branch_runtime_evidence_confidence(branch),
        "current_head_runtime_evidence_confidence": (
            _branch_runtime_evidence_confidence(branch)
        ),
        "gate_observation_reason_codes": _current_gate_observation_codes(branch),
        "lifecycle_action_reason_codes": _lifecycle_action_reason_codes(branch),
        "rollback_reason_codes": _branch_rollback_codes(branch),
        "why_not_promoted_reason_codes": _why_not_promoted_codes(branch),
        "best_checkpoint_reason_codes": _best_checkpoint_reason_codes(branch),
        "history_reason_codes": _history_reason_codes(branch),
        "best_checkpoint_generic_evidence_summary": (
            _best_checkpoint_mapping(branch, "best_checkpoint_generic_evidence_summary")
        ),
        "best_checkpoint_phase_activation_summary": (
            _best_checkpoint_mapping(branch, "best_checkpoint_phase_activation_summary")
        ),
        "best_checkpoint_runtime_evidence_confidence": _best_checkpoint_scalar(
            branch,
            "best_checkpoint_runtime_evidence_confidence",
        ),
        "best_checkpoint_telemetry_outcome": _best_checkpoint_scalar(
            branch,
            "best_checkpoint_telemetry_outcome",
        ),
        "history_phase_activation_summaries": _history_mapping_list(
            branch,
            "history_phase_activation_summaries",
        ),
        "history_runtime_evidence_confidences": _branch_evidence_codes(
            branch,
            "history_runtime_evidence_confidences",
        ),
        "proposal_block_reason_codes": _proposal_block_codes(branch),
        "why_abandoned_reason_codes": _why_abandoned_codes(branch),
        "last_screening_feedback_tier": last_screening_feedback_tier,
        "last_telemetry_outcome": last_telemetry_outcome,
        "repair_focus_required": repair_focus_required,
        "same_mechanism_followup_required": same_mechanism_followup_required,
        "hypothesis_generation_mode": generation_mode,
        "repair_focus_reason": repair_focus_reason,
        "repair_policy": (
            REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK
            if repair_focus_required
            else None
        ),
        "branch_followup_policy": followup_policy,
        "weak_positive_followup": weak_positive_followup,
        "clean_fork_policy": clean_fork_policy,
        "branch_mechanism_ids": list(protected_mechanism_ids),
        "allowed_mechanism_ids": allowed_mechanism_ids,
        "protected_mechanism_ids": list(protected_mechanism_ids),
        "forbidden_mechanism_policy": (
            NO_UNRELATED_MECHANISM_IDS
            if strict_same_mechanism_followup
            else None
        ),
        "same_mechanism_allowed_actions": (
            list(SAME_MECHANISM_ALLOWED_ACTIONS)
            if strict_same_mechanism_followup
            else []
        ),
        "mechanism_change_policy": (
            "mechanism_changes_must_use_allowed_or_protected_ids"
            if strict_same_mechanism_followup
            else None
        ),
        "repair_mechanism_ids": list(
            getattr(branch, "telemetry_repair_mechanism_ids", ()) or ()
        )
        if branch is not None
        else [],
        "telemetry_repair_attempts": dict(
            getattr(branch, "telemetry_repair_attempts", {}) or {}
        )
        if branch is not None
        else {},
        "baseline_policy": baseline_policy,
    }
    if runtime_evidence_pressure_count is not None:
        context["runtime_evidence_pressure_count"] = runtime_evidence_pressure_count
        context["current_head_runtime_evidence_pressure_count"] = (
            runtime_evidence_pressure_count
        )
    if runtime_low_confidence_advisory:
        context["runtime_evidence_low_confidence_advisory"] = (
            runtime_low_confidence_advisory
        )
    context.update(branch_lifecycle_reroute_context(branch))
    diversity_guidance = _runtime_saturated_diversity_guidance(context)
    if diversity_guidance:
        context["diversity_reroute_guidance"] = diversity_guidance
    return context


def branch_hygiene_guidance(branch: Branch | None) -> str:
    """Human-readable branch hygiene guidance for prompts and diagnostics."""
    context = branch_hygiene_context(branch)
    card = branch_prompt_card(branch)
    return _render_branch_hygiene_guidance(
        context,
        card=card,
        parked_lineage=branch_is_parked_lineage(branch),
    )


__all__ = [
    "active_slot_inventory_from_branch_cards",
    "branch_hygiene_context",
    "branch_hygiene_guidance",
    "branch_prompt_card",
    "branch_prompt_card_from_context",
]
