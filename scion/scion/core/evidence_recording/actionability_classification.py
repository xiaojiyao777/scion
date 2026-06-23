"""Report-only actionability classifiers for research continuity artifacts."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

MISSED_SAME_BRANCH_REFINEMENT_REASONS = {
    "scheduler_selected_clean_exploration_branch",
}
ACCEPTED_CLEAN_FORK_POLICY_REASONS = {
    "clean_fork_required_for_new_mechanism",
    "new_exploration_slot_available",
    "runtime_evidence_completeness_clean_fork",
}
CLEAN_FORK_POLICY_CHOICE_REASON = "clean_fork_selected_instead_of_same_branch"
SCHEDULER_RESULT_CONTEXT_KEYS = (
    "scheduler_slot",
    "scheduler_reason",
    "result_action",
    "result_reason",
    "attempt_kind",
    "pre_finalizer_scheduler_slot",
    "pre_finalizer_scheduler_reason",
    "post_finalizer_actual_branch_action",
)


def scheduler_metadata_with_result_context(
    record: Mapping[str, Any],
) -> Mapping[str, Any]:
    audit = record.get("scheduler_audit_metadata")
    if not isinstance(audit, Mapping):
        return record
    context = {
        key: record[key]
        for key in SCHEDULER_RESULT_CONTEXT_KEYS
        if key in record
    }
    return {**context, **audit}


def same_branch_refinement_followup_counts(
    metadata: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    """Classify report-only same-branch followup outcomes from scheduler metadata."""

    rows = [item for item in metadata if isinstance(item, Mapping)]
    return {
        "selected_same_branch_refinement_count": sum(
            1 for item in rows if _is_same_branch_refinement_selected(item)
        ),
        "not_selected_same_branch_refinement_count": sum(
            1 for item in rows if _is_missed_same_branch_refinement_opportunity(item)
        ),
        "accepted_clean_fork_policy_choice_count": sum(
            1 for item in rows if _is_accepted_clean_fork_policy_choice(item)
        ),
    }


def _is_same_branch_refinement_selected(item: Mapping[str, Any]) -> bool:
    return (
        item.get("same_branch_refinement_selected") is True
        or item.get("pre_finalizer_same_branch_refinement_selected") is True
        or str(item.get("post_finalizer_actual_branch_action") or "")
        == "continue_same_branch"
    )


def _is_missed_same_branch_refinement_opportunity(
    item: Mapping[str, Any],
) -> bool:
    if _is_accepted_clean_fork_policy_choice(item):
        return False
    reason = _clean_token(item.get("same_branch_refinement_not_selected_reason"))
    if reason in MISSED_SAME_BRANCH_REFINEMENT_REASONS:
        return True
    justification = item.get("same_mechanism_clean_fork_justification")
    if isinstance(justification, Mapping):
        return (
            _clean_token(justification.get("reason"))
            == CLEAN_FORK_POLICY_CHOICE_REASON
        )
    return False


def _is_accepted_clean_fork_policy_choice(item: Mapping[str, Any]) -> bool:
    justification = item.get("same_mechanism_clean_fork_justification")
    justification_context: Mapping[str, Any] = {}
    if isinstance(justification, Mapping):
        context = justification.get("active_branch_cap_context")
        if isinstance(context, Mapping):
            justification_context = context
    reason = _clean_token(
        item.get("same_branch_refinement_not_selected_reason")
        or item.get("clean_fork_reason")
        or item.get("runtime_evidence_clean_fork_reason")
        or item.get("scheduler_reason")
        or (
            justification.get("clean_fork_reason")
            if isinstance(justification, Mapping)
            else ""
        )
        or justification_context.get("scheduler_reason")
    )
    if reason not in ACCEPTED_CLEAN_FORK_POLICY_REASONS:
        return False
    slot = _clean_token(
        item.get("pre_finalizer_scheduler_slot")
        or item.get("scheduler_slot")
        or justification_context.get("scheduler_slot")
    )
    actual_action = _clean_token(
        item.get("post_finalizer_actual_branch_action")
        or item.get("actual_branch_action")
    )
    selected_policy = _clean_token(item.get("post_finalizer_next_proposal_policy"))
    justification_reason = (
        _clean_token(justification.get("reason"))
        if isinstance(justification, Mapping)
        else ""
    )
    has_clean_fork_context = (
        item.get("clean_fork_selected") is True
        or item.get("runtime_evidence_clean_fork_selected") is True
        or selected_policy == "clean_fork_selected"
        or actual_action == "explore_new_clean_fork"
        or justification_reason == CLEAN_FORK_POLICY_CHOICE_REASON
    )
    if not has_clean_fork_context:
        return False
    return (
        slot == "explore_new"
        or actual_action == "explore_new_clean_fork"
        or _clean_token(item.get("result_action")) == "skip"
        or item.get("runtime_evidence_clean_fork_selected") is True
    )


def _clean_token(value: Any) -> str:
    return str(value or "").strip()
