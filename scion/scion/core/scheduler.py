from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable, List, Literal, Mapping, Optional

from scion.core.branch_hygiene import (
    BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE,
    BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
    CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM,
    branch_has_actionable_diagnostic,
    branch_has_retained_checkpoint,
    branch_is_parked_lineage,
    branch_lifecycle_new_mechanism_ineligible,
    branch_lineage_status,
    branch_requires_repair_focus,
    branch_requires_same_mechanism_followup,
)
from scion.core.models import Branch, BranchState
from scion.core.scheduling.active_slots import (
    ACTIVE_SLOT_HARD_CAP_BLOCKED,
    ACTIVE_SLOT_HARD_CAP_RECONCILED,
    ACTIVE_SLOT_RECLAIMED_FOR_NEW_BRANCH,
    ActiveSlotReconciliation,
    active_slot_branches as _active_slot_branches,
    active_slot_capacity_block_metadata as _active_slot_capacity_block_metadata,
    active_slot_inventory as _active_slot_inventory,
    branch_active_slot_release_reason as _branch_active_slot_release_reason,
    branch_counts_toward_active_slots as _branch_counts_toward_active_slots,
    branch_has_decision_origin_park_marker as _branch_has_decision_origin_park_marker,
    reclaim_active_slot_for_new_branch as _reclaim_active_slot_for_new_branch,
    reconcile_active_slot_overflow as _reconcile_active_slot_overflow,
)
from scion.core.scheduling.runtime_pressure import (
    RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON,
    _runtime_aggregate_excluded,
    _runtime_evidence_low_or_incomplete,
    _runtime_evidence_pressure_count,
    _runtime_evidence_pressure_triggers,
    _summary_nonnegative_int,
    _summary_text,
    branch_runtime_evidence_clean_fork_pressure_summary,
)


@dataclass(frozen=True)
class SchedulerAction:
    action: Literal["run_existing", "create_new", "at_capacity"]
    branch: Optional[Branch] = None
    reason: str = ""
    slot: Literal[
        "explore_new",
        "exploit_weak_positive",
        "repair_diagnostic",
        "refine_active",
        "capacity_blocked",
    ] = "refine_active"
    audit_metadata: Mapping[str, Any] = field(default_factory=dict)


# High-priority tiers (index 0 = highest priority).
# BLOCKED_INFRA is intentionally excluded — those branches are not schedulable.
_HIGH_PRIORITY_TIERS: List[frozenset] = [
    frozenset({BranchState.READY_FROZEN}),
    frozenset({BranchState.READY_VALIDATE}),
    frozenset({BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE}),
    frozenset({
        BranchState.EXPLORE_EXPAND,
        BranchState.VALIDATING,
        BranchState.VALIDATING_EXPAND,
        BranchState.FROZEN_TESTING,
    }),
]
# Backward-compatible name for older white-box tests and downstream checks.
_PRIORITY_TIERS = _HIGH_PRIORITY_TIERS
_RESEARCH_STATES = frozenset({BranchState.EXPLORE})
_TERMINAL_STATES = frozenset({
    BranchState.PROMOTED,
    BranchState.ABANDONED,
    BranchState.PARKED_LINEAGE,
})

_DEFAULT_MAX_ACTIVE_BRANCHES = 3
_PLATEAU_REROUTE_REASON = "plateau_reroute_clean_fork"
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
_LOW_VALUE_CLEAN_FORK_MATERIAL_DIFFERENCE_RELEASE_REASONS = frozenset(
    {
        "repeated_no_effect_zero_effect_slot_release",
        "retained_checkpoint_no_effect_current_head",
    }
)
_PLATEAU_GATE_THRESHOLD = 2


@dataclass(frozen=True)
class _SchedulerActiveSlotPolicy:
    scheduler_owned_release_reason: Callable[[Branch | None], str]
    eligible_new_branch_reclaim: Callable[[Branch], bool]
    reclaim_sort_key: Callable[[Branch], tuple[Any, ...]]


def _active_slot_policy() -> _SchedulerActiveSlotPolicy:
    return _SchedulerActiveSlotPolicy(
        scheduler_owned_release_reason=_scheduler_owned_active_slot_release_reason,
        eligible_new_branch_reclaim=_eligible_new_branch_slot_reclaim,
        reclaim_sort_key=_active_slot_reclaim_sort_key,
    )


class Scheduler:
    def __init__(self, max_active_branches: int = _DEFAULT_MAX_ACTIVE_BRANCHES) -> None:
        self._max_active_branches = max_active_branches

    @property
    def max_active_branches(self) -> int:
        return self._max_active_branches

    def select_next(self, branches: List[Branch]) -> SchedulerAction:
        """
        Select the next branch to process using lexicographic priority plus a
        small portfolio rule for low-priority research branches.

        P1: READY_FROZEN
        P2: READY_VALIDATE
        P3: STALE
        P4: EXPLORE_EXPAND / VALIDATING / VALIDATING_EXPAND / FROZEN_TESTING
        P5: pending_retry research branches
        P6: create new branch when only established research branches exist and
            active count is below max_active_branches
        P7: run research branch by oldest updated_at
        P8: at_capacity (when no actionable branch and active count >= max_active_branches)

        BLOCKED_INFRA branches are never scheduled.
        Within the same tier, pending_retry=True branches precede others; ties
        are broken by oldest updated_at as a last-run approximation.
        """
        active = [b for b in branches if b.state not in _TERMINAL_STATES]
        active_for_slots = active_slot_branches(active)
        # BLOCKED_INFRA branches are not schedulable, though they still count
        # toward the active-branch cap until recovery/abandon clears them.
        schedulable = [
            b
            for b in active
            if b.state != BranchState.BLOCKED_INFRA
            and not branch_is_parked_lineage(b)
            and not _branch_has_decision_origin_park_marker(b)
            and not _retained_checkpoint_no_effect_current_head(b)
            and (
                not _no_effect_slot_release_preferred(b)
                or _branch_same_branch_refinement_sampling_candidate(b)
            )
            and not _quality_regression_slot_release_preferred(b)
            and (
                not _branch_lifecycle_budget_exhausted(b)
                or _branch_plateau_gate_same_branch_candidate(b)
            )
        ]

        for tier in _HIGH_PRIORITY_TIERS:
            candidates = [b for b in schedulable if b.state in tier]
            if candidates:
                selected = _select_fair(candidates)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot=_slot_for_branch(selected),
                )

        research = [b for b in schedulable if b.state in _RESEARCH_STATES]
        if research:
            pending_retry = [b for b in research if b.pending_retry]
            if pending_retry:
                selected = _select_fair(pending_retry)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot="repair_diagnostic",
                )
            eligible_research = [
                branch
                for branch in research
                if not branch_lifecycle_new_mechanism_ineligible(branch)
                and not branch_is_parked_lineage(branch)
                and (
                    not _branch_lifecycle_budget_exhausted(branch)
                    or _branch_plateau_gate_same_branch_candidate(branch)
                )
            ]
            if not eligible_research:
                if len(active_for_slots) < self._max_active_branches:
                    return SchedulerAction(
                        action="create_new",
                        branch=None,
                        reason=BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
                        slot="repair_diagnostic",
                    )
                return SchedulerAction(
                    action="at_capacity",
                    branch=None,
                    reason="active_branch_limit_reached",
                    slot="capacity_blocked",
                )
            weak_positive_priority_candidates = [
                branch
                for branch in eligible_research
                if _branch_is_weak_positive_priority(branch)
                and not _branch_plateau_reroute_preferred(branch)
            ]
            if weak_positive_priority_candidates:
                selected = _select_budgeted(weak_positive_priority_candidates)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot=_slot_for_branch(selected),
                    audit_metadata=(
                        _weak_positive_runtime_evidence_suppression_audit(
                            selected
                        )
                    ),
                )
            same_branch_sample_candidates = [
                branch
                for branch in eligible_research
                if _branch_same_branch_refinement_sampling_candidate(branch)
            ]
            if same_branch_sample_candidates:
                selected = _select_budgeted(same_branch_sample_candidates)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=(
                        PLATEAU_GATE_SAME_BRANCH_REFINEMENT_REASON
                        if _branch_plateau_gate_same_branch_candidate(selected)
                        else SAME_BRANCH_REFINEMENT_SAMPLE_REASON
                    ),
                    slot=_slot_for_branch(selected),
                    audit_metadata=_same_branch_refinement_sampling_audit(
                        selected,
                        candidate_count=len(same_branch_sample_candidates),
                    ),
                )
            if (
                len(active_for_slots) < self._max_active_branches
                and any(
                    _branch_runtime_evidence_pressure_preferred(branch)
                    for branch in eligible_research
                )
            ):
                return SchedulerAction(
                    action="create_new",
                    branch=None,
                    reason=RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON,
                    slot="explore_new",
                    audit_metadata=_clean_fork_selection_audit(
                        eligible_research,
                        reason=RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON,
                    ),
                )
            preferred_research = [
                branch
                for branch in eligible_research
                if not _branch_plateau_reroute_preferred(branch)
            ]
            priority_candidates = [
                branch
                for branch in preferred_research
                if _branch_research_priority(branch) <= 40
            ]
            if priority_candidates:
                selected = _select_budgeted(priority_candidates)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot=_slot_for_branch(selected),
                )
            if not preferred_research:
                reason = (
                    RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
                    if any(
                        _branch_runtime_evidence_pressure_preferred(branch)
                        for branch in eligible_research
                    )
                    else _PLATEAU_REROUTE_REASON
                )
                if len(active_for_slots) < self._max_active_branches:
                    return SchedulerAction(
                        action="create_new",
                        branch=None,
                        reason=reason,
                        slot="explore_new",
                        audit_metadata=_clean_fork_selection_audit(
                            eligible_research,
                            reason=reason,
                        ),
                    )
                return SchedulerAction(
                    action="at_capacity",
                    branch=None,
                    reason="active_branch_limit_reached",
                    slot="capacity_blocked",
                )
            if all(
                branch_requires_same_mechanism_followup(branch)
                for branch in eligible_research
            ):
                if len(active_for_slots) < self._max_active_branches:
                    return SchedulerAction(
                        action="create_new",
                        branch=None,
                        reason=CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM,
                        slot="explore_new",
                    )
                return SchedulerAction(
                    action="at_capacity",
                    branch=None,
                    reason="active_branch_limit_reached",
                    slot="capacity_blocked",
                )
            clean_research = [
                branch
                for branch in preferred_research
                if not branch_requires_same_mechanism_followup(branch)
            ]
            clean_candidates = [
                branch
                for branch in clean_research
                if not _established_branch(branch)
            ]
            if clean_candidates:
                selected = _select_fair(clean_candidates)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot=_slot_for_branch(selected),
                )
            if len(active_for_slots) < self._max_active_branches and any(
                _established_branch(branch) for branch in eligible_research
            ):
                return SchedulerAction(
                    action="create_new",
                    branch=None,
                    reason="established_branch_portfolio_expansion",
                    slot="explore_new",
                    audit_metadata=_merge_audit_metadata(
                        _weak_positive_followup_suppression_audit(
                            active,
                            selected_policy="clean_fork_selected",
                            selected_reason="established_branch_portfolio_expansion",
                        ),
                        _low_value_active_slot_release_audit(active),
                    ),
                )
            selection_pool = clean_research or preferred_research or eligible_research
            selected = _select_budgeted(selection_pool)
            return SchedulerAction(
                action="run_existing",
                branch=selected,
                reason=_reason_for_branch(selected),
                slot=_slot_for_branch(selected),
            )

        # No actionable branch: only create new if below capacity (§4.6 / §11.5)
        if len(active_for_slots) >= self._max_active_branches:
            return SchedulerAction(
                action="at_capacity",
                branch=None,
                reason="active_branch_limit_reached",
                slot="capacity_blocked",
            )

        return SchedulerAction(
            action="create_new",
            branch=None,
            reason="new_exploration_slot_available",
            slot="explore_new",
            audit_metadata=_merge_audit_metadata(
                _clean_fork_selection_audit(
                    active,
                    reason="new_exploration_slot_available",
                ),
                _low_value_active_slot_release_audit(active),
            ),
        )


def _select_fair(candidates: List[Branch]) -> Branch:
    return sorted(
        candidates,
        key=lambda b: (0 if b.pending_retry else 1, b.updated_at, b.created_at),
    )[0]


def _select_budgeted(candidates: List[Branch]) -> Branch:
    return sorted(
        candidates,
        key=lambda b: (
            _branch_research_priority(b),
            0 if b.pending_retry else 1,
            b.updated_at,
            b.created_at,
        ),
    )[0]


def _merge_audit_metadata(*items: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in items:
        if item:
            merged.update(dict(item))
    return merged


def _established_branch(branch: Branch) -> bool:
    return bool(branch.direction)


def branch_counts_toward_active_slots(branch: Branch) -> bool:
    """Return whether ``branch`` consumes a reported active lineage slot.

    Proposal scheduling may prefer a clean fork over a weak or exhausted
    follow-up.  Active-slot accounting tracks schedulable resource pressure,
    so deterministic low-value heads that the scheduler already excludes can
    release capacity without turning proposal text into a promotion/abandon
    decision.
    """
    return _branch_counts_toward_active_slots(
        branch,
        policy=_active_slot_policy(),
    )


def branch_active_slot_release_reason(branch: Branch | None) -> str:
    """Return why ``branch`` is excluded from active-slot accounting, if known."""
    return _branch_active_slot_release_reason(
        branch,
        policy=_active_slot_policy(),
    )


def _scheduler_owned_active_slot_release_reason(branch: Branch | None) -> str:
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
    low_value_reason = _low_value_active_slot_candidate_reason(branch)
    if (
        low_value_reason == "retained_checkpoint_no_effect_current_head"
        and not _branch_lifecycle_budget_exhausted(branch)
    ):
        return ""
    if low_value_reason:
        return low_value_reason
    return ""


def _low_value_active_slot_candidate_reason(branch: Branch | None) -> str:
    """Return Scheduler-only low-value candidate pressure without releasing slots."""
    if branch is None or branch.state in _TERMINAL_STATES:
        return ""
    if (
        branch_is_parked_lineage(branch)
        and _branch_has_decision_origin_park_marker(branch)
    ):
        return "parked_lineage"
    if _retained_checkpoint_no_effect_current_head(branch):
        return "retained_checkpoint_no_effect_current_head"
    if _no_effect_slot_release_preferred(branch):
        return "repeated_no_effect_zero_effect_slot_release"
    if _quality_regression_slot_release_preferred(branch):
        return QUALITY_REGRESSION_ACTIVE_SLOT_RELEASE_REASON
    return ""


def active_slot_branches(branches: Iterable[Branch]) -> list[Branch]:
    """Filter branches to the active-slot capacity pool."""
    return _active_slot_branches(
        branches,
        policy=_active_slot_policy(),
    )


def active_slot_inventory(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> dict[str, Any]:
    """Build a status/summary inventory for active scheduling slots."""
    return _active_slot_inventory(
        branches,
        max_active_branches=max_active_branches,
        policy=_active_slot_policy(),
    )


def reconcile_active_slot_overflow(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> ActiveSlotReconciliation:
    """Persist Decision-marked parked lineages until active slots fit the cap."""
    return _reconcile_active_slot_overflow(
        branches,
        max_active_branches=max_active_branches,
        policy=_active_slot_policy(),
    )


def reclaim_active_slot_for_new_branch(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> ActiveSlotReconciliation:
    """Persist one Decision-marked parked lineage before admitting a clean fork."""
    return _reclaim_active_slot_for_new_branch(
        branches,
        max_active_branches=max_active_branches,
        policy=_active_slot_policy(),
    )


def active_slot_capacity_block_metadata(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> dict[str, Any]:
    return _active_slot_capacity_block_metadata(
        branches,
        max_active_branches=max_active_branches,
        policy=_active_slot_policy(),
    )


def _eligible_new_branch_slot_reclaim(branch: Branch) -> bool:
    if branch.state not in _RESEARCH_STATES:
        return False
    if _branch_has_decision_origin_park_marker(branch):
        return True
    return (
        _branch_lifecycle_budget_exhausted(branch)
        or branch_lifecycle_new_mechanism_ineligible(branch)
        or _no_effect_slot_release_preferred(branch)
        or _no_effect_without_actionable_diagnostic(branch)
        or _quality_regression_slot_release_preferred(branch)
        or _branch_plateau_reroute_preferred(branch)
    )


def _active_slot_reclaim_sort_key(branch: Branch) -> tuple[Any, ...]:
    status = branch_lineage_status(branch)
    if _branch_lifecycle_budget_exhausted(branch):
        bucket = 0
    elif branch_lifecycle_new_mechanism_ineligible(branch):
        bucket = 1
    elif _quality_regression_slot_release_preferred(branch):
        bucket = 2
    elif _no_effect_without_actionable_diagnostic(branch):
        bucket = 3
    elif _branch_plateau_reroute_preferred(branch):
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


def _branch_lifecycle_budget_exhausted(branch: Branch) -> bool:
    if branch.state not in _RESEARCH_STATES:
        return False
    return _rollback_budget_exhausted(branch) or _marginal_loop_exhausted(branch)


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


def _branch_plateau_reroute_preferred(branch: Branch) -> bool:
    if _branch_plateau_gate_same_branch_candidate(branch):
        return False
    if _branch_runtime_evidence_pressure_preferred(branch):
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


def _branch_runtime_evidence_pressure_preferred(branch: Branch) -> bool:
    if _branch_is_weak_positive_priority(branch):
        return False
    if _branch_plateau_gate_same_branch_candidate(branch):
        return False
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return False
    return _runtime_evidence_pressure_count(summary) >= 2


def _clean_fork_selection_audit(
    branches: Iterable[Branch],
    *,
    reason: str,
) -> dict[str, Any]:
    branch_list = list(branches)
    audit = _weak_positive_followup_suppression_audit(
        branch_list,
        selected_policy="clean_fork_selected",
        selected_reason=reason,
    )
    pressure_candidates: list[dict[str, Any]] = []
    pressure_count_max = 0
    for branch in branch_list:
        summary = branch_runtime_evidence_clean_fork_pressure_summary(branch)
        if not summary and not _branch_runtime_evidence_pressure_preferred(branch):
            continue
        evidence_summary = getattr(branch, "branch_evidence_summary", {}) or {}
        if isinstance(evidence_summary, Mapping):
            pressure_count = _runtime_evidence_pressure_count(evidence_summary)
            pressure_count_max = max(pressure_count_max, pressure_count)
        else:
            pressure_count = 0
        candidate = {
            "branch_id": str(getattr(branch, "branch_id", "") or ""),
            "lineage_status": branch_lineage_status(branch),
            "runtime_evidence_pressure_count": pressure_count,
            "runtime_evidence_pressure_triggers": (
                _runtime_evidence_pressure_triggers(evidence_summary)
                if isinstance(evidence_summary, Mapping)
                else []
            ),
        }
        if summary:
            candidate.update(
                {
                    "case_wins": summary.get("case_wins", 0),
                    "case_losses": summary.get("case_losses", 0),
                    "case_balance": summary.get("case_balance", "unknown"),
                    "runtime_evidence_confidence": summary.get(
                        "runtime_evidence_confidence",
                        "unknown",
                    ),
                    "runtime_evidence_status": summary.get(
                        "runtime_evidence_status",
                        "unknown",
                    ),
                }
            )
        pressure_candidates.append(candidate)
    if pressure_candidates:
        audit.update(
            {
                "runtime_evidence_clean_fork_selected": True,
                "runtime_evidence_clean_fork_reason": reason,
                "runtime_evidence_clean_fork_candidate_count": len(
                    pressure_candidates
                ),
                "runtime_evidence_pressure_count_max": pressure_count_max,
                "runtime_evidence_clean_fork_candidates": pressure_candidates[:8],
            }
        )
    plateau_candidates = _plateau_gate_clean_fork_candidates(branch_list)
    if plateau_candidates:
        material_requirement = _material_difference_requirement_record(
            reason=PLATEAU_GATE_MATERIAL_DIFFERENCE_REASON,
            source="plateau_gate",
            required_for="clean_fork_new_branch",
            candidate_count=len(plateau_candidates),
            candidate_branch_ids=[
                str(candidate.get("branch_id") or "")
                for candidate in plateau_candidates
                if str(candidate.get("branch_id") or "").strip()
            ],
        )
        audit.update(
            {
                "plateau_gate_clean_fork_selected": True,
                "plateau_gate_reason": PLATEAU_GATE_MATERIAL_DIFFERENCE_REASON,
                "material_difference_required": True,
                "material_difference_required_for": "clean_fork_new_branch",
                "material_difference_requirement": material_requirement,
                "material_difference_audit_records": [material_requirement],
                "plateau_gate_clean_fork_candidate_count": len(
                    plateau_candidates
                ),
                "plateau_gate_clean_fork_candidates": plateau_candidates[:8],
            }
        )
    low_value_candidates = _low_value_clean_fork_material_difference_candidates(
        branch_list
    )
    if low_value_candidates and not audit.get("material_difference_required"):
        material_requirement = _material_difference_requirement_record(
            reason=LOW_VALUE_CLEAN_FORK_MATERIAL_DIFFERENCE_REASON,
            source="low_value_clean_fork_pressure",
            required_for="clean_fork_new_branch",
            candidate_count=len(low_value_candidates),
            candidate_branch_ids=[
                str(candidate.get("branch_id") or "")
                for candidate in low_value_candidates
                if str(candidate.get("branch_id") or "").strip()
            ],
        )
        audit.update(
            {
                "low_value_clean_fork_material_difference_selected": True,
                "low_value_clean_fork_material_difference_reason": (
                    LOW_VALUE_CLEAN_FORK_MATERIAL_DIFFERENCE_REASON
                ),
                "material_difference_required": True,
                "material_difference_required_for": "clean_fork_new_branch",
                "material_difference_requirement": material_requirement,
                "material_difference_audit_records": [material_requirement],
                "low_value_clean_fork_material_difference_candidate_count": len(
                    low_value_candidates
                ),
                "low_value_clean_fork_material_difference_candidates": (
                    low_value_candidates[:8]
                ),
            }
        )
    return audit


def _material_difference_requirement_record(
    *,
    reason: str,
    source: str,
    required_for: str,
    candidate_count: int,
    candidate_branch_ids: Iterable[str],
) -> dict[str, Any]:
    if source == "plateau_gate":
        reason_codes = [
            "PLATEAU_GATE_THRESHOLD_MET",
            "PLATEAU_GATE_CLEAN_FORK_REQUIRES_MATERIAL_DIFFERENCE",
        ]
    else:
        reason_codes = [
            "LOW_VALUE_CLEAN_FORK_PRESSURE",
            "CLEAN_FORK_REQUIRES_MATERIAL_DIFFERENCE",
        ]
    stable_payload = {
        "schema_version": "material_difference_requirement.v1",
        "record_type": "material_difference_requirement",
        "requirement_source": str(source),
        "reason": str(reason),
        "reason_codes": reason_codes,
        "required_for": str(required_for),
        "required_metadata_key": "material_difference_required",
        "candidate_count": max(0, int(candidate_count)),
        "candidate_branch_ids": sorted(
            str(branch_id)
            for branch_id in candidate_branch_ids
            if str(branch_id).strip()
        ),
        "proposal_visibility_only": True,
        "proposal_guidance_only": True,
        "audit_only": True,
        "decision_features_excluded": True,
    }
    digest_input = json.dumps(
        stable_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(digest_input).hexdigest()
    stable_payload["record_digest"] = f"sha256:{digest}"
    stable_payload["record_id"] = f"material_difference_requirement:{digest[:16]}"
    return stable_payload


def _low_value_active_slot_release_audit(
    branches: Iterable[Branch],
) -> dict[str, Any]:
    candidates = [
        summary
        for branch in branches
        for summary in (_low_value_active_slot_release_summary(branch),)
        if summary
    ]
    if not candidates:
        return {}
    return {
        "low_value_active_slot_release": True,
        "low_value_active_slot_release_policy": (
            "audit_low_value_current_head_without_scheduler_lifecycle_change"
        ),
        "low_value_active_slot_release_candidate_count": len(candidates),
        "low_value_active_slot_release_candidates": candidates[:8],
        "proposal_guidance_only": True,
        "decision_features_excluded": True,
    }


def _low_value_clean_fork_material_difference_candidates(
    branches: Iterable[Branch],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for branch in branches:
        release_reason = _low_value_active_slot_candidate_reason(branch)
        if (
            release_reason
            not in _LOW_VALUE_CLEAN_FORK_MATERIAL_DIFFERENCE_RELEASE_REASONS
        ):
            continue
        if (
            release_reason != "retained_checkpoint_no_effect_current_head"
            and _branch_same_branch_refinement_sampling_candidate(branch)
        ):
            continue
        summary = _low_value_active_slot_release_summary(branch)
        if summary:
            candidates.append(summary)
    return candidates


def _plateau_gate_clean_fork_candidates(
    branches: Iterable[Branch],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for branch in branches:
        gate = _branch_plateau_gate(branch)
        if not gate or not bool(gate.get("threshold_met")):
            continue
        if _branch_plateau_gate_same_branch_candidate(branch):
            continue
        candidates.append(
            {
                "branch_id": str(getattr(branch, "branch_id", "") or ""),
                "lineage_status": branch_lineage_status(branch),
                "branch_state": _branch_state_value(branch),
                "branch_code_status": str(
                    getattr(branch, "branch_code_status", "") or ""
                ),
                "screening_tier": _branch_screening_tier(branch)
                or str(gate.get("tier") or "unknown"),
                "effective_screened_no_effect_count": _gate_nonnegative_int(
                    gate,
                    "effective_screened_no_effect_count",
                ),
                "runtime_evidence_pressure_count": _gate_nonnegative_int(
                    gate,
                    "runtime_evidence_pressure_count",
                ),
                "scheduler_preference": str(
                    gate.get("scheduler_preference") or ""
                ),
                "plateau_gate_reason_codes": [
                    str(code)
                    for code in gate.get("reason_codes", ())
                    if str(code).strip()
                ],
            }
        )
    return candidates


def _low_value_active_slot_release_summary(branch: Branch) -> dict[str, Any]:
    reason = _low_value_active_slot_candidate_reason(branch)
    if not reason:
        return {}
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    evidence = summary if isinstance(summary, Mapping) else {}
    return {
        "branch_id": str(getattr(branch, "branch_id", "") or ""),
        "lineage_status": branch_lineage_status(branch),
        "branch_state": _branch_state_value(branch),
        "branch_code_status": str(getattr(branch, "branch_code_status", "") or ""),
        "screening_tier": _branch_screening_tier(branch)
        or _summary_text(evidence, "tier", default="unknown"),
        "release_reason": reason,
        "case_wins": _summary_nonnegative_int(evidence, "wins"),
        "case_losses": _summary_nonnegative_int(evidence, "losses"),
        "activation_zero_effect_streak": _activation_zero_effect_streak(branch),
        "runtime_evidence_pressure_count": _runtime_evidence_pressure_count(evidence),
    }


def _weak_positive_runtime_evidence_suppression_audit(
    branch: Branch,
) -> dict[str, Any]:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return {}
    pressure_count = _runtime_evidence_pressure_count(summary)
    if pressure_count < 2 or not _runtime_evidence_low_or_incomplete(summary):
        return {}
    wins = _summary_nonnegative_int(summary, "wins")
    losses = _summary_nonnegative_int(summary, "losses")
    if wins <= 0 or losses != 0:
        return {}
    return {
        "runtime_evidence_clean_fork_suppression": "weak_positive_exception",
        "runtime_evidence_clean_fork_reason": (
            RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
        ),
        "runtime_evidence_pressure_count": pressure_count,
        "case_wins": wins,
        "case_losses": losses,
        "runtime_evidence_confidence": _summary_text(
            summary,
            "runtime_evidence_confidence",
            default="unknown",
        ),
        "runtime_evidence_status": _summary_text(
            summary,
            "runtime_evidence_status",
            default="unknown",
        ),
        "runtime_aggregate_excluded": _runtime_aggregate_excluded(summary),
        "runtime_evidence_pressure_triggers": _runtime_evidence_pressure_triggers(
            summary
        ),
    }


def _same_branch_refinement_sampling_audit(
    branch: Branch,
    *,
    candidate_count: int,
) -> dict[str, Any]:
    reason = _same_branch_refinement_sampling_signal(branch)
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    evidence = summary if isinstance(summary, Mapping) else {}
    gate = _branch_plateau_gate(branch)
    audit = {
        "same_branch_refinement_selected": True,
        "same_branch_refinement_reason": (
            reason or SAME_BRANCH_REFINEMENT_SAMPLE_REASON
        ),
        "same_branch_refinement_sampling": True,
        "same_branch_refinement_sampling_reason": (
            reason or SAME_BRANCH_REFINEMENT_SAMPLE_REASON
        ),
        "same_branch_refinement_sampling_candidate_count": max(
            0,
            int(candidate_count),
        ),
        "clean_fork_suppressed_for_same_branch_sample": True,
        "same_branch_refinement_sampling_candidate": {
            "branch_id": str(getattr(branch, "branch_id", "") or ""),
            "lineage_status": branch_lineage_status(branch),
            "branch_state": _branch_state_value(branch),
            "branch_code_status": str(
                getattr(branch, "branch_code_status", "") or ""
            ),
            "screening_tier": _branch_screening_tier(branch)
            or _summary_text(evidence, "tier", default="unknown"),
            "runtime_evidence_pressure_count": _runtime_evidence_pressure_count(
                evidence
            ),
            "activation_zero_effect_streak": _activation_zero_effect_streak(
                branch
            ),
            "lifecycle_no_effect_diagnostic_followups": _no_effect_followup_count(
                branch
            ),
            "runtime_evidence_pressure_triggers": (
                _runtime_evidence_pressure_triggers(evidence)
            ),
        },
    }
    if gate:
        audit.update(
            {
                "plateau_gate_same_branch_refinement_selected": True,
                "plateau_gate_reason": PLATEAU_GATE_SAME_BRANCH_REFINEMENT_REASON,
                "plateau_gate_reason_codes": [
                    str(code)
                    for code in gate.get("reason_codes", ())
                    if str(code).strip()
                ],
                "plateau_gate": {
                    "schema_version": str(
                        gate.get("schema_version") or "plateau_gate.v1"
                    ),
                    "tier": str(gate.get("tier") or "unknown"),
                    "threshold_met": bool(gate.get("threshold_met")),
                    "effective_screened_no_effect_count": _gate_nonnegative_int(
                        gate,
                        "effective_screened_no_effect_count",
                    ),
                    "runtime_evidence_pressure_count": _gate_nonnegative_int(
                        gate,
                        "runtime_evidence_pressure_count",
                    ),
                    "scheduler_preference": str(
                        gate.get("scheduler_preference") or ""
                    ),
                    "proposal_guidance_only": True,
                    "audit_only": True,
                    "decision_features_excluded": True,
                },
                "same_branch_refinement_allowed_actions": [
                    str(item)
                    for item in gate.get("allowed_same_branch_actions", ())
                    if str(item).strip()
                ],
            }
        )
    return audit


def _branch_same_branch_refinement_sampling_candidate(branch: Branch) -> bool:
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
    if _branch_plateau_gate_same_branch_candidate(branch):
        return True
    if branch_has_actionable_diagnostic(branch):
        return False
    if branch_requires_repair_focus(branch):
        return False
    if getattr(branch, "telemetry_repair_mechanism_ids", ()) or ():
        return False
    if _branch_lifecycle_budget_exhausted(branch):
        return False
    if _branch_has_weak_positive_followup_signal(branch):
        return False
    if _same_branch_refinement_sample_already_observed(branch):
        return False
    return bool(_same_branch_refinement_sampling_signal(branch))


def _branch_plateau_gate(branch: Branch) -> Mapping[str, Any]:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return {}
    gate = summary.get("plateau_gate")
    return gate if isinstance(gate, Mapping) else {}


def _branch_plateau_gate_same_branch_candidate(branch: Branch) -> bool:
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
    if _branch_has_weak_positive_followup_signal(branch):
        return False
    gate = _branch_plateau_gate(branch)
    if not gate or not bool(gate.get("threshold_met")):
        return False
    if bool(gate.get("same_branch_refinement_sampled")):
        return False
    if _same_branch_refinement_marker_observed(branch):
        return False
    effective_count = _gate_nonnegative_int(
        gate,
        "effective_screened_no_effect_count",
    )
    runtime_pressure_count = _gate_nonnegative_int(
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


def _gate_nonnegative_int(gate: Mapping[str, Any], key: str) -> int:
    try:
        return max(0, int(gate.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def _same_branch_refinement_sample_already_observed(branch: Branch) -> bool:
    if _same_branch_refinement_marker_observed(branch):
        return True
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    evidence = summary if isinstance(summary, Mapping) else {}
    if _no_effect_followup_count(branch) >= 2:
        return True
    if _activation_zero_effect_streak(branch) >= 2:
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


def _same_branch_refinement_marker_observed(branch: Branch) -> bool:
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


def _same_branch_refinement_sampling_signal(branch: Branch) -> str:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    evidence = summary if isinstance(summary, Mapping) else {}
    if not evidence:
        return ""
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = _branch_screening_tier(branch) or _summary_text(evidence, "tier")
    gate = _branch_plateau_gate(branch)
    if gate and bool(gate.get("threshold_met")):
        return "plateau_gate_diagnostic_refinement"
    if (status == "active_no_effect" or tier == "no_effect") and (
        _summary_text(evidence, "tier") == "no_effect"
        or any(key in evidence for key in ("wins", "losses", "ties"))
    ):
        return "no_effect_observation"
    if _activation_zero_effect_streak(branch) > 0:
        return "telemetry_effect_zero_observation"
    reason_codes = _summary_reason_code_set(evidence)
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


def _summary_reason_code_set(summary: Mapping[str, Any]) -> set[str]:
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


def _no_effect_followup_count(branch: Branch) -> int:
    try:
        return max(
            0,
            int(getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0) or 0),
        )
    except (TypeError, ValueError):
        return 0


def _weak_positive_followup_suppression_audit(
    branches: Iterable[Branch],
    *,
    selected_policy: str,
    selected_reason: str,
) -> dict[str, Any]:
    suppressed: list[dict[str, Any]] = []
    for branch in branches:
        if not _branch_has_weak_positive_followup_signal(branch):
            continue
        suppression_reason = _weak_positive_followup_not_selected_reason(branch)
        if not suppression_reason:
            continue
        suppressed.append(
            {
                "branch_id": str(getattr(branch, "branch_id", "") or ""),
                "lineage_status": branch_lineage_status(branch),
                "branch_state": _branch_state_value(branch),
                "branch_code_status": str(
                    getattr(branch, "branch_code_status", "") or ""
                ),
                "screening_tier": _branch_screening_tier(branch),
                "reason": suppression_reason,
                "runtime_evidence_pressure_count": _runtime_evidence_pressure_count(
                    getattr(branch, "branch_evidence_summary", {}) or {}
                )
                if isinstance(getattr(branch, "branch_evidence_summary", None), Mapping)
                else 0,
            }
        )
    if not suppressed:
        return {}
    return {
        "weak_positive_followup_suppressed": True,
        "weak_positive_followup_suppression_reason": selected_reason,
        "weak_positive_followup_suppression_selected_policy": selected_policy,
        "weak_positive_followup_suppression_audit": suppressed[:8],
    }


def _branch_has_weak_positive_followup_signal(branch: Branch) -> bool:
    if _branch_is_weak_positive_lineage(branch):
        return True
    if _branch_screening_tier(branch) == "weak_positive":
        return True
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    return isinstance(summary, Mapping) and str(summary.get("tier") or "") == (
        "weak_positive"
    )


def _weak_positive_followup_not_selected_reason(branch: Branch) -> str:
    if branch.state in _TERMINAL_STATES:
        return "terminal_or_parked"
    if branch_is_parked_lineage(branch):
        return "parked_lineage"
    if branch.state != BranchState.EXPLORE:
        return "not_research_state"
    if getattr(branch, "pending_retry", False):
        return "pending_retry_diagnostic_followup"
    if _retained_checkpoint_no_effect_current_head(branch):
        return "retained_checkpoint_no_effect_current_head"
    if branch_lifecycle_new_mechanism_ineligible(branch):
        return BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE
    if _branch_lifecycle_budget_exhausted(branch):
        return "branch_lifecycle_budget_exhausted"
    if branch_runtime_evidence_clean_fork_pressure_summary(branch):
        return RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
    if _branch_plateau_reroute_preferred(branch):
        return _PLATEAU_REROUTE_REASON
    if branch_lineage_status(branch) == "diagnostic_repair":
        return "diagnostic_repair_required"
    if _branch_is_weak_positive_priority(branch):
        return "lower_scheduler_priority_or_slot_reconciliation"
    return "not_schedulable_as_weak_positive_followup"


def _branch_is_weak_positive_priority(branch: Branch) -> bool:
    return (
        _branch_is_weak_positive_lineage(branch)
        and not branch_runtime_evidence_clean_fork_pressure_summary(branch)
    )


def _branch_is_weak_positive_lineage(branch: Branch) -> bool:
    return branch_lineage_status(branch) in {
        "active_weak_positive",
        "restored_weak_positive",
    }


def _branch_screening_tier(branch: Branch) -> str:
    return str(getattr(branch, "last_screening_feedback_tier", "") or "")


def _branch_state_value(branch: Branch) -> str:
    state = getattr(branch, "state", "")
    return str(getattr(state, "value", state) or "")


def _branch_research_priority(branch: Branch) -> int:
    status = branch_lineage_status(branch)
    if getattr(branch, "pending_retry", False):
        return 0
    if status in {"active_weak_positive", "restored_weak_positive"}:
        return 10
    if status == "restored_checkpoint":
        return 20
    if status == "active_marginal":
        return 30
    if branch_has_actionable_diagnostic(branch):
        return 40
    if not _established_branch(branch):
        return 50
    if _no_effect_without_actionable_diagnostic(branch):
        return 70
    if branch_has_retained_checkpoint(branch):
        return 80
    return 60


def _no_effect_without_actionable_diagnostic(branch: Branch) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    return (
        (status == "active_no_effect" or tier == "no_effect")
        and not branch_has_actionable_diagnostic(branch)
    )


def _quality_regression_slot_release_preferred(branch: Branch) -> bool:
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
    if _branch_has_weak_positive_followup_signal(branch):
        return False
    if not _quality_regression_without_actionable_diagnostic(branch):
        return False
    return True


def _quality_regression_without_actionable_diagnostic(branch: Branch) -> bool:
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


def _no_effect_slot_release_preferred(branch: Branch) -> bool:
    if getattr(branch, "pending_retry", False):
        return False
    if branch_requires_repair_focus(branch):
        return False
    if getattr(branch, "telemetry_repair_mechanism_ids", ()) or ():
        return False
    if not _no_effect_without_actionable_diagnostic(branch):
        return False
    if _activation_zero_effect_streak(branch) >= 2:
        return True
    no_effect_followups = max(
        0,
        int(getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0) or 0),
    )
    return no_effect_followups >= 2


def _activation_zero_effect_streak(branch: Branch) -> int:
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


def _retained_checkpoint_no_effect_current_head(branch: Branch) -> bool:
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


def _slot_for_branch(
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


def _reason_for_branch(branch: Branch) -> str:
    if getattr(branch, "pending_retry", False):
        return "pending_retry_diagnostic_followup"
    slot = _slot_for_branch(branch)
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    if slot == "exploit_weak_positive":
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
        if _no_effect_without_actionable_diagnostic(branch):
            return "no_effect_without_actionable_diagnostic_deprioritized"
        if status.startswith("active_") or tier:
            return "effect_diagnostic_followup"
        return "diagnostic_followup"
    return "active_branch_refinement"
