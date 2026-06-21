"""Structured scheduler signals for branch resource policy."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Mapping

from scion.core.branch_hygiene import (
    BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE,
    branch_has_actionable_diagnostic,
    branch_has_retained_checkpoint,
    branch_is_parked_lineage,
    branch_lifecycle_new_mechanism_ineligible,
    branch_lineage_status,
    branch_requires_repair_focus,
)
from scion.core.models import Branch, BranchState
from scion.core.scheduling.runtime_pressure import (
    RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON,
    _runtime_evidence_low_or_incomplete,
    _runtime_evidence_pressure_count,
    _runtime_evidence_pressure_triggers,
    _summary_text,
    branch_runtime_evidence_clean_fork_pressure_summary,
)


PLATEAU_REROUTE_REASON = "plateau_reroute_clean_fork"
QUALITY_REGRESSION_ACTIVE_SLOT_RELEASE_REASON = (
    "quality_regression_without_actionable_diagnostic_slot_release"
)
SAME_BRANCH_REFINEMENT_SAMPLE_REASON = (
    "same_branch_low_signal_observation_sample"
)
PLATEAU_GATE_SAME_BRANCH_REFINEMENT_REASON = (
    "plateau_gate_same_branch_diagnostic_refinement"
)
PLATEAU_GATE_MATERIAL_DIFFERENCE_REASON = (
    "plateau_gate_material_difference_required"
)
LOW_VALUE_CLEAN_FORK_MATERIAL_DIFFERENCE_REASON = (
    "low_value_clean_fork_material_difference_required"
)
FRESH_CHAMPION_RUNTIME_REPLAY_FOLLOWUP_REASON = (
    "fresh_champion_runtime_replay_followup"
)

_RESEARCH_STATES = frozenset({BranchState.EXPLORE})
_TERMINAL_STATES = frozenset({
    BranchState.PROMOTED,
    BranchState.ABANDONED,
    BranchState.PARKED_LINEAGE,
})
_PLATEAU_GATE_THRESHOLD = 2


def scheduler_owned_active_slot_release_reason(
    branch: Branch | None,
    *,
    has_decision_origin_park_marker: bool = False,
) -> str:
    if branch is None or branch.state in _TERMINAL_STATES:
        return ""
    if branch.state != BranchState.EXPLORE:
        return ""
    if getattr(branch, "pending_retry", False):
        return ""
    if branch_requires_repair_focus(branch):
        return ""
    if getattr(branch, "telemetry_repair_mechanism_ids", ()) or ():
        return ""
    if branch_has_actionable_diagnostic(branch):
        return ""
    low_value_reason = low_value_active_slot_candidate_reason(
        branch,
        has_decision_origin_park_marker=has_decision_origin_park_marker,
    )
    if (
        not has_decision_origin_park_marker
        and low_value_reason
        in {
            "retained_checkpoint_no_effect_current_head",
            "repeated_no_effect_zero_effect_slot_release",
        }
    ):
        return ""
    if (
        low_value_reason == "retained_checkpoint_no_effect_current_head"
        and not branch_lifecycle_budget_exhausted(branch)
    ):
        return ""
    if low_value_reason:
        return low_value_reason
    return ""


def low_value_active_slot_candidate_reason(
    branch: Branch | None,
    *,
    has_decision_origin_park_marker: bool = False,
) -> str:
    """Return Scheduler-only low-value candidate pressure without releasing slots."""
    if branch is None or branch.state in _TERMINAL_STATES:
        return ""
    if branch_is_parked_lineage(branch) and has_decision_origin_park_marker:
        return "parked_lineage"
    if retained_checkpoint_no_effect_current_head(branch):
        return "retained_checkpoint_no_effect_current_head"
    if no_effect_slot_release_preferred(branch):
        return "repeated_no_effect_zero_effect_slot_release"
    if quality_regression_slot_release_preferred(branch):
        return QUALITY_REGRESSION_ACTIVE_SLOT_RELEASE_REASON
    return ""


def eligible_new_branch_slot_reclaim(
    branch: Branch,
    *,
    has_decision_origin_park_marker: bool = False,
) -> bool:
    if branch.state not in _RESEARCH_STATES:
        return False
    if has_decision_origin_park_marker:
        return True
    return (
        branch_lifecycle_new_mechanism_ineligible(branch)
        or quality_regression_slot_release_preferred(branch)
    )


def active_slot_reclaim_sort_key(branch: Branch) -> tuple[Any, ...]:
    status = branch_lineage_status(branch)
    if branch_lifecycle_budget_exhausted(branch):
        bucket = 0
    elif branch_lifecycle_new_mechanism_ineligible(branch):
        bucket = 1
    elif quality_regression_slot_release_preferred(branch):
        bucket = 2
    elif no_effect_without_actionable_diagnostic(branch):
        bucket = 3
    elif branch_plateau_reroute_preferred(branch):
        bucket = 4
    elif status == "active_no_effect":
        bucket = 5
    elif status == "active_marginal":
        bucket = 6
    elif branch.state == BranchState.BLOCKED_INFRA:
        bucket = 10
    elif branch.state in _RESEARCH_STATES:
        bucket = 20
    elif branch.state in {BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE}:
        bucket = 30
    else:
        bucket = 40
    if getattr(branch, "pending_retry", False):
        bucket += 25
    policy_blocks = max(
        0,
        int(getattr(branch, "branch_lifecycle_policy_blocks", 0) or 0),
    )
    return (
        bucket,
        1 if branch_has_retained_checkpoint(branch) else 0,
        -policy_blocks,
        getattr(branch, "updated_at", datetime.min),
        getattr(branch, "created_at", datetime.min),
        branch.branch_id,
    )


def branch_lifecycle_budget_exhausted(branch: Branch) -> bool:
    if branch.state not in _RESEARCH_STATES:
        return False
    return _rollback_budget_exhausted(branch) or _marginal_loop_exhausted(branch)


def branch_plateau_reroute_preferred(branch: Branch) -> bool:
    if branch_plateau_gate_same_branch_candidate(branch):
        return False
    if branch_runtime_evidence_pressure_preferred(branch):
        return True
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    repeated = max(
        0,
        int(getattr(branch, "lifecycle_signal_repeat_count", 0) or 0),
    )
    marginal_or_no_effect_streak = max(
        0,
        int(getattr(branch, "lifecycle_marginal_no_effect_streak", 0) or 0),
    )
    no_effect_followups = max(
        0,
        int(getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0) or 0),
    )
    if (
        status in {"active_marginal", "active_no_effect"}
        or tier in {"marginal", "no_effect"}
    ):
        return marginal_or_no_effect_streak >= 2 or no_effect_followups >= 1
    if status == "active_weak_positive" or tier == "weak_positive":
        return repeated >= 2
    return False


def branch_runtime_evidence_pressure_preferred(branch: Branch) -> bool:
    if branch_fresh_runtime_replay_pending(branch):
        return False
    if branch_is_weak_positive_priority(branch):
        return False
    if branch_plateau_gate_same_branch_candidate(branch):
        return False
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return False
    return _runtime_evidence_pressure_count(summary) >= 2


def branch_same_branch_refinement_sampling_candidate(branch: Branch) -> bool:
    if branch.state not in _RESEARCH_STATES:
        return False
    if getattr(branch, "pending_retry", False):
        return False
    if branch.state == BranchState.BLOCKED_INFRA:
        return False
    if branch_is_parked_lineage(branch):
        return False
    if branch_lifecycle_new_mechanism_ineligible(branch):
        return False
    if branch_plateau_gate_same_branch_candidate(branch):
        return True
    if branch_has_actionable_diagnostic(branch):
        return False
    if branch_requires_repair_focus(branch):
        return False
    if getattr(branch, "telemetry_repair_mechanism_ids", ()) or ():
        return False
    if branch_lifecycle_budget_exhausted(branch):
        return False
    if branch_has_weak_positive_followup_signal(branch):
        return False
    if same_branch_refinement_sample_already_observed(branch):
        return False
    return bool(same_branch_refinement_sampling_signal(branch))


def branch_plateau_gate(branch: Branch) -> Mapping[str, Any]:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return {}
    gate = summary.get("plateau_gate")
    return gate if isinstance(gate, Mapping) else {}


def branch_plateau_gate_same_branch_candidate(branch: Branch) -> bool:
    if branch.state not in _RESEARCH_STATES:
        return False
    if getattr(branch, "pending_retry", False):
        return False
    if branch.state == BranchState.BLOCKED_INFRA:
        return False
    if branch_is_parked_lineage(branch):
        return False
    if branch_lifecycle_new_mechanism_ineligible(branch):
        return False
    if branch_has_weak_positive_followup_signal(branch):
        return False
    gate = branch_plateau_gate(branch)
    if not gate or not bool(gate.get("threshold_met")):
        return False
    if bool(gate.get("same_branch_refinement_sampled")):
        return False
    if same_branch_refinement_marker_observed(branch):
        return False
    effective_count = gate_nonnegative_int(
        gate,
        "effective_screened_no_effect_count",
    )
    runtime_pressure_count = gate_nonnegative_int(
        gate,
        "runtime_evidence_pressure_count",
    )
    if effective_count != _PLATEAU_GATE_THRESHOLD:
        return False
    if runtime_pressure_count < _PLATEAU_GATE_THRESHOLD:
        return False
    preference = str(gate.get("scheduler_preference") or "")
    return preference in {
        "",
        "same_branch_diagnostic_refinement",
    }


def gate_nonnegative_int(gate: Mapping[str, Any], key: str) -> int:
    try:
        return max(0, int(gate.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def same_branch_refinement_sample_already_observed(branch: Branch) -> bool:
    if same_branch_refinement_marker_observed(branch):
        return True
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    evidence = summary if isinstance(summary, Mapping) else {}
    if no_effect_followup_count(branch) >= 2:
        return True
    if activation_zero_effect_streak(branch) >= 2:
        return True
    if _runtime_evidence_pressure_count(evidence) >= 2:
        return True
    repeated = max(
        0,
        int(getattr(branch, "lifecycle_signal_repeat_count", 0) or 0),
    )
    marginal_or_no_effect_streak = max(
        0,
        int(getattr(branch, "lifecycle_marginal_no_effect_streak", 0) or 0),
    )
    return marginal_or_no_effect_streak >= 2 and repeated >= 2


def same_branch_refinement_marker_observed(branch: Branch) -> bool:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    evidence = summary if isinstance(summary, Mapping) else {}
    if bool(evidence.get("same_branch_refinement_sampling")):
        return True
    if bool(evidence.get("same_branch_refinement_selected")):
        return True
    gate = evidence.get("plateau_gate")
    if isinstance(gate, Mapping) and bool(gate.get("same_branch_refinement_sampled")):
        return True
    return False


def same_branch_refinement_sampling_signal(branch: Branch) -> str:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    evidence = summary if isinstance(summary, Mapping) else {}
    if not evidence:
        return ""
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = branch_screening_tier(branch) or _summary_text(evidence, "tier")
    gate = branch_plateau_gate(branch)
    if gate and bool(gate.get("threshold_met")):
        return "plateau_gate_diagnostic_refinement"
    if (status == "active_no_effect" or tier == "no_effect") and (
        _summary_text(evidence, "tier") == "no_effect"
        or any(key in evidence for key in ("wins", "losses", "ties"))
    ):
        return "no_effect_observation"
    if activation_zero_effect_streak(branch) > 0:
        return "telemetry_effect_zero_observation"
    reason_codes = summary_reason_code_set(evidence)
    if "SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC" in reason_codes:
        return "telemetry_effect_zero_observation"
    if reason_codes.intersection(
        {
            "SCREENING_WEAK_SIGNAL_CONTINUE",
            "SCREENING_MARGINAL_SIGNAL_CONTINUE",
            "SCREENING_NEUTRAL_SIGNAL_CONTINUE",
        }
    ):
        return "weak_signal_refinement_observation"
    runtime_triggers = _runtime_evidence_pressure_triggers(evidence)
    if any(
        trigger == "runtime_saturation_without_objective_signal"
        for trigger in runtime_triggers
    ) or reason_codes.intersection(
        {
            "SCREENING_RUNTIME_BUDGET_SATURATION",
            "TINY_RUNTIME_BUDGET_SATURATION",
            "SCREENING_RUNTIME_SATURATION_DIAGNOSTIC",
            "SCREENING_RUNTIME_SATURATION_REROUTE",
        }
    ):
        return "runtime_budget_saturation_observation"
    if (
        _runtime_evidence_pressure_count(evidence) > 0
        or bool(runtime_triggers)
    ) and _runtime_evidence_low_or_incomplete(evidence):
        return "runtime_low_confidence_observation"
    return ""


def summary_reason_code_set(summary: Mapping[str, Any]) -> set[str]:
    codes: list[Any] = []
    for key in (
        "reason_codes",
        "decision_reason_codes",
        "why_not_promoted_reason_codes",
        "gate_observation_reason_codes",
        "lifecycle_action_reason_codes",
        "history_reason_codes",
    ):
        value = summary.get(key)
        if isinstance(value, str):
            codes.append(value)
        elif isinstance(value, (list, tuple, set)):
            codes.extend(value)
    return {str(code).strip().upper() for code in codes if str(code).strip()}


def no_effect_followup_count(branch: Branch) -> int:
    try:
        return max(
            0,
            int(getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0) or 0),
        )
    except (TypeError, ValueError):
        return 0


def branch_has_weak_positive_followup_signal(branch: Branch) -> bool:
    if branch_is_weak_positive_lineage(branch):
        return True
    if branch_screening_tier(branch) == "weak_positive":
        return True
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    return isinstance(summary, Mapping) and str(summary.get("tier") or "") == (
        "weak_positive"
    )


def branch_fresh_runtime_replay_marker(branch: Branch | None) -> Mapping[str, Any]:
    if branch is None:
        return {}
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return {}
    marker = summary.get("fresh_runtime_followup")
    return marker if isinstance(marker, Mapping) else {}


def branch_fresh_runtime_replay_pending(branch: Branch | None) -> bool:
    marker = branch_fresh_runtime_replay_marker(branch)
    if not marker:
        return False
    return (
        bool(marker.get("fresh_runtime_pending"))
        and str(marker.get("scheduler_marker") or "")
        == "fresh_champion_runtime_replay_pending"
    )


def weak_positive_followup_not_selected_reason(branch: Branch) -> str:
    if branch.state in _TERMINAL_STATES:
        return "terminal_or_parked"
    if branch_is_parked_lineage(branch):
        return "parked_lineage"
    if branch.state != BranchState.EXPLORE:
        return "not_research_state"
    if getattr(branch, "pending_retry", False):
        return "pending_retry_diagnostic_followup"
    if retained_checkpoint_no_effect_current_head(branch):
        return "retained_checkpoint_no_effect_current_head"
    if branch_lifecycle_new_mechanism_ineligible(branch):
        return BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE
    if branch_lifecycle_budget_exhausted(branch):
        return "branch_lifecycle_budget_exhausted"
    if branch_runtime_evidence_clean_fork_pressure_summary(branch):
        return RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
    if branch_plateau_reroute_preferred(branch):
        return PLATEAU_REROUTE_REASON
    if branch_lineage_status(branch) == "diagnostic_repair":
        return "diagnostic_repair_required"
    if branch_is_weak_positive_priority(branch):
        return "lower_scheduler_priority_or_slot_reconciliation"
    return "not_schedulable_as_weak_positive_followup"


def branch_is_weak_positive_priority(branch: Branch) -> bool:
    if branch_fresh_runtime_replay_pending(branch):
        return True
    return (
        branch_is_weak_positive_lineage(branch)
        and not branch_runtime_evidence_clean_fork_pressure_summary(branch)
    )


def branch_is_weak_positive_lineage(branch: Branch) -> bool:
    return branch_lineage_status(branch) in {
        "active_weak_positive",
        "restored_weak_positive",
    }


def branch_screening_tier(branch: Branch) -> str:
    return str(getattr(branch, "last_screening_feedback_tier", "") or "")


def branch_state_value(branch: Branch) -> str:
    state = getattr(branch, "state", "")
    return str(getattr(state, "value", state) or "")


def branch_research_priority(branch: Branch) -> int:
    status = branch_lineage_status(branch)
    if getattr(branch, "pending_retry", False):
        return 0
    if branch_fresh_runtime_replay_pending(branch):
        return 5
    if status in {"active_weak_positive", "restored_weak_positive"}:
        return 10
    if status == "restored_checkpoint":
        return 20
    if status == "active_marginal":
        return 30
    if branch_has_actionable_diagnostic(branch):
        return 40
    if not established_branch(branch):
        return 50
    if no_effect_without_actionable_diagnostic(branch):
        return 70
    if branch_has_retained_checkpoint(branch):
        return 80
    return 60


def established_branch(branch: Branch) -> bool:
    return bool(branch.direction)


def no_effect_without_actionable_diagnostic(branch: Branch) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    return (
        (status == "active_no_effect" or tier == "no_effect")
        and not branch_has_actionable_diagnostic(branch)
    )


def quality_regression_slot_release_preferred(branch: Branch) -> bool:
    if branch.state not in _RESEARCH_STATES:
        return False
    if getattr(branch, "pending_retry", False):
        return False
    if branch_requires_repair_focus(branch):
        return False
    if getattr(branch, "telemetry_repair_mechanism_ids", ()) or ():
        return False
    if branch_has_retained_checkpoint(branch):
        return False
    if branch_has_weak_positive_followup_signal(branch):
        return False
    if not quality_regression_without_actionable_diagnostic(branch):
        return False
    return True


def quality_regression_without_actionable_diagnostic(branch: Branch) -> bool:
    if branch_has_actionable_diagnostic(branch):
        return False
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    summary_tier = (
        str(summary.get("tier") or "")
        if isinstance(summary, Mapping)
        else ""
    )
    return (
        status in {"active_quality_regression", "quality_regression"}
        or tier == "quality_regression"
        or summary_tier == "quality_regression"
    )


def no_effect_slot_release_preferred(branch: Branch) -> bool:
    if getattr(branch, "pending_retry", False):
        return False
    if branch_requires_repair_focus(branch):
        return False
    if getattr(branch, "telemetry_repair_mechanism_ids", ()) or ():
        return False
    if not no_effect_without_actionable_diagnostic(branch):
        return False
    if activation_zero_effect_streak(branch) >= 2:
        return True
    no_effect_followups = max(
        0,
        int(getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0) or 0),
    )
    return no_effect_followups >= 2


def activation_zero_effect_streak(branch: Branch) -> int:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return 0
    zero_summary = summary.get("activation_zero_effect_summary")
    if isinstance(zero_summary, Mapping):
        try:
            return max(0, int(zero_summary.get("streak") or 0))
        except (TypeError, ValueError):
            return 0
    try:
        return max(0, int(summary.get("activation_zero_effect_streak") or 0))
    except (TypeError, ValueError):
        return 0


def retained_checkpoint_no_effect_current_head(branch: Branch) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    current_no_effect = status in {"active_no_effect", "active_neutral"} or tier in {
        "no_effect",
        "neutral",
    }
    if not current_no_effect or not branch_has_retained_checkpoint(branch):
        return False
    if getattr(branch, "pending_retry", False):
        return False
    if branch_requires_repair_focus(branch):
        return False
    if getattr(branch, "telemetry_repair_mechanism_ids", ()) or ():
        return False
    return True


def slot_for_branch(
    branch: Branch,
) -> Literal[
    "explore_new",
    "exploit_weak_positive",
    "repair_diagnostic",
    "refine_active",
    "capacity_blocked",
]:
    if getattr(branch, "pending_retry", False):
        return "repair_diagnostic"
    if branch_fresh_runtime_replay_pending(branch):
        return "exploit_weak_positive"
    lineage_status = branch_lineage_status(branch)
    if lineage_status in {"active_weak_positive", "restored_weak_positive"}:
        return "exploit_weak_positive"
    if lineage_status == "restored_checkpoint":
        return "refine_active"
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    if branch_requires_repair_focus(branch):
        return "repair_diagnostic"
    if getattr(branch, "telemetry_repair_mechanism_ids", ()) or ():
        return "repair_diagnostic"
    diagnostic_tiers = {
        "inactive",
        "invalid",
        "no_effect",
        "quality_regression",
        "runtime_regression",
    }
    diagnostic_statuses = {
        "discarded",
        "regressed_followup",
        "telemetry_wiring_suspect",
        "telemetry_invalid",
        *(f"active_{item}" for item in diagnostic_tiers),
    }
    if status in diagnostic_statuses:
        return "repair_diagnostic"
    if tier in diagnostic_tiers:
        return "repair_diagnostic"
    return "refine_active"


def reason_for_branch(branch: Branch) -> str:
    if getattr(branch, "pending_retry", False):
        return "pending_retry_diagnostic_followup"
    if branch_fresh_runtime_replay_pending(branch):
        return FRESH_CHAMPION_RUNTIME_REPLAY_FOLLOWUP_REASON
    slot = slot_for_branch(branch)
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    if slot == "exploit_weak_positive":
        if branch_fresh_runtime_replay_pending(branch):
            return FRESH_CHAMPION_RUNTIME_REPLAY_FOLLOWUP_REASON
        if branch_lineage_status(branch) == "restored_weak_positive":
            return "restored_weak_positive_checkpoint_followup"
        return "weak_positive_signal_followup"
    if branch_lineage_status(branch) == "restored_checkpoint":
        return "restored_checkpoint_followup"
    if slot == "repair_diagnostic":
        if (
            status in {"telemetry_wiring_suspect", "telemetry_invalid"}
            or branch_requires_repair_focus(branch)
            or (getattr(branch, "telemetry_repair_mechanism_ids", ()) or ())
        ):
            return "telemetry_diagnostic_followup"
        if status == "active_runtime_regression" or tier == "runtime_regression":
            return "runtime_diagnostic_followup"
        if no_effect_without_actionable_diagnostic(branch):
            return "no_effect_same_mechanism_followup"
        if status.startswith("active_") or tier:
            return "effect_diagnostic_followup"
        return "diagnostic_followup"
    return "active_branch_refinement"


def _rollback_budget_exhausted(branch: Branch) -> bool:
    return (
        max(0, int(getattr(branch, "rollback_count", 0) or 0)) >= 2
        and (
            bool(getattr(branch, "best_quality_checkpoint_id", None))
            or bool(getattr(branch, "last_valid_checkpoint_id", None))
        )
    )


def _marginal_loop_exhausted(branch: Branch) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    if status not in {"active_marginal", "active_no_effect"} and tier not in {
        "marginal",
        "no_effect",
    }:
        return False
    repeated = max(
        0,
        int(getattr(branch, "lifecycle_signal_repeat_count", 0) or 0),
    )
    marginal_or_no_effect_streak = max(
        0,
        int(getattr(branch, "lifecycle_marginal_no_effect_streak", 0) or 0),
    )
    no_effect_followups = max(
        0,
        int(getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0) or 0),
    )
    return (
        marginal_or_no_effect_streak >= 2
        and repeated >= 2
        or no_effect_followups >= 2
    )
