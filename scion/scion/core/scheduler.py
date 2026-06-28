from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Literal, Mapping, Optional

from scion.core.branch_hygiene import (
    BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
    MECHANISM_CONTRACT_BRANCH_LOCAL_FOLLOWUP_REASON,
    branch_is_parked_lineage,
    branch_lifecycle_new_mechanism_ineligible,
    branch_mechanism_ids,
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
    branch_scheduling_status as _branch_scheduling_status,
    reclaim_active_slot_for_new_branch as _reclaim_active_slot_for_new_branch,
    reconcile_active_slot_overflow as _reconcile_active_slot_overflow,
)
from scion.core.scheduling.runtime_pressure import (
    RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON,
    branch_runtime_evidence_clean_fork_pressure_summary,
)
from scion.core.scheduling.audits import (
    clean_fork_selection_audit as _clean_fork_selection_audit,
    low_value_active_slot_release_audit as _low_value_active_slot_release_audit,
    same_branch_refinement_sampling_audit as _same_branch_refinement_sampling_audit,
    weak_positive_followup_suppression_audit as _weak_positive_followup_suppression_audit,
    weak_positive_runtime_evidence_suppression_audit as _weak_positive_runtime_evidence_suppression_audit,
)
from scion.core.scheduling.signals import (
    LOW_VALUE_CLEAN_FORK_MATERIAL_DIFFERENCE_REASON,
    PLATEAU_GATE_MATERIAL_DIFFERENCE_REASON,
    PLATEAU_GATE_SAME_BRANCH_REFINEMENT_REASON,
    PLATEAU_REROUTE_REASON as _PLATEAU_REROUTE_REASON,
    QUALITY_REGRESSION_ACTIVE_SLOT_RELEASE_REASON,
    SAME_BRANCH_REFINEMENT_SAMPLE_REASON,
    FRESH_CHAMPION_RUNTIME_REPLAY_FOLLOWUP_REASON,
    active_slot_reclaim_sort_key as _active_slot_reclaim_sort_key,
    branch_lifecycle_budget_exhausted as _branch_lifecycle_budget_exhausted,
    branch_is_weak_positive_priority as _branch_is_weak_positive_priority,
    branch_plateau_gate_same_branch_candidate as _branch_plateau_gate_same_branch_candidate,
    branch_plateau_reroute_preferred as _branch_plateau_reroute_preferred,
    branch_research_priority as _branch_research_priority,
    branch_runtime_evidence_pressure_preferred as _branch_runtime_evidence_pressure_preferred,
    branch_same_branch_refinement_sampling_candidate as _branch_same_branch_refinement_sampling_candidate,
    eligible_new_branch_slot_reclaim as _signals_eligible_new_branch_slot_reclaim,
    established_branch as _established_branch,
    low_value_active_slot_candidate_reason as _signals_low_value_active_slot_candidate_reason,
    no_effect_slot_release_preferred as _no_effect_slot_release_preferred,
    no_effect_without_actionable_diagnostic as _no_effect_without_actionable_diagnostic,
    quality_regression_slot_release_preferred as _quality_regression_slot_release_preferred,
    reason_for_branch as _reason_for_branch,
    retained_checkpoint_no_effect_current_head as _retained_checkpoint_no_effect_current_head,
    scheduler_owned_active_slot_release_reason as _signals_scheduler_owned_active_slot_release_reason,
    slot_for_branch as _slot_for_branch,
)


@dataclass(frozen=True)
class SchedulerAction:
    action: Literal["run_existing", "replay_existing", "create_new", "at_capacity"]
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
PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON = (
    "prepared_successor_focus_clean_fork"
)


@dataclass(frozen=True)
class _SchedulerActiveSlotPolicy:
    scheduler_owned_release_reason: Callable[[Branch | None], str]
    eligible_new_branch_reclaim: Callable[[Branch], bool]
    reclaim_sort_key: Callable[[Branch], tuple[Any, ...]]


@dataclass(frozen=True)
class _PreparedSuccessorSchedulingFocus:
    active: bool = False
    configured: bool = False
    reviewed_mechanism_ids: tuple[str, ...] = ()
    successor_opportunity_families: tuple[str, ...] = ()
    required_mechanism_ids: tuple[str, ...] = ()


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

    def select_next(
        self,
        branches: List[Branch],
        *,
        launch_research_focus: Mapping[str, Any] | None = None,
    ) -> SchedulerAction:
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
        successor_focus = _prepared_successor_scheduling_focus(
            launch_research_focus
        )
        active = [b for b in branches if b.state not in _TERMINAL_STATES]
        scheduling_statuses = {
            b.branch_id: branch_scheduling_status(b)
            for b in active
        }
        active_for_slots = active_slot_branches(active)
        # BLOCKED_INFRA branches are not schedulable, though they still count
        # toward the active-branch cap until recovery/abandon clears them.
        schedulable = [
            b
            for b in active
            if scheduling_statuses[b.branch_id].schedulable
            and b.state != BranchState.BLOCKED_INFRA
            and not branch_is_parked_lineage(b)
            and not _branch_has_decision_origin_park_marker(b)
            and _low_value_filters_allow(
                b,
                scheduling_statuses[b.branch_id],
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
            pending_retry = [
                b
                for b in research
                if b.pending_retry
                and not _prepared_successor_focus_excludes_branch(
                    b,
                    successor_focus,
                )
            ]
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
                    or _same_mechanism_low_signal_followup_candidate(branch)
                    or _required_branch_local_diagnostic_followup(
                        scheduling_statuses[branch.branch_id]
                    )
                )
            ]
            successor_excluded_research = [
                branch
                for branch in eligible_research
                if _prepared_successor_focus_excludes_branch(
                    branch,
                    successor_focus,
                )
            ]
            successor_focus_audit = _prepared_successor_focus_audit_metadata(
                successor_focus,
                excluded_branches=successor_excluded_research,
            )
            if successor_excluded_research:
                successor_excluded_ids = {
                    branch.branch_id for branch in successor_excluded_research
                }
                eligible_research = [
                    branch
                    for branch in eligible_research
                    if branch.branch_id not in successor_excluded_ids
                ]
            if not eligible_research:
                if len(active_for_slots) < self._max_active_branches:
                    if successor_excluded_research:
                        return SchedulerAction(
                            action="create_new",
                            branch=None,
                            reason=PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON,
                            slot="explore_new",
                            audit_metadata=_merge_audit_metadata(
                                _clean_fork_selection_audit(
                                    successor_excluded_research,
                                    reason=(
                                        PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON
                                    ),
                                ),
                                successor_focus_audit,
                            ),
                        )
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
                    audit_metadata=successor_focus_audit,
                )
            weak_positive_priority_candidates = [
                branch
                for branch in eligible_research
                if _branch_is_weak_positive_priority(branch)
                and not _branch_plateau_reroute_preferred(branch)
            ]
            if weak_positive_priority_candidates:
                selected = _select_budgeted(weak_positive_priority_candidates)
                action: Literal["run_existing", "replay_existing"] = (
                    "replay_existing"
                    if _reason_for_branch(selected)
                    == FRESH_CHAMPION_RUNTIME_REPLAY_FOLLOWUP_REASON
                    else "run_existing"
                )
                return SchedulerAction(
                    action=action,
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot=_slot_for_branch(selected),
                    audit_metadata=(
                        _weak_positive_runtime_evidence_suppression_audit(
                            selected
                        )
                    ),
                )
            required_branch_local_followup_candidates = [
                branch
                for branch in eligible_research
                if _required_branch_local_diagnostic_followup(
                    scheduling_statuses[branch.branch_id]
                )
            ]
            if required_branch_local_followup_candidates:
                selected = _select_budgeted(
                    required_branch_local_followup_candidates
                )
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot=_slot_for_branch(selected),
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
                    slot="refine_active",
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
            same_mechanism_followup_candidates = [
                branch
                for branch in eligible_research
                if _same_mechanism_low_signal_followup_candidate(branch)
            ]
            if same_mechanism_followup_candidates:
                selected = _select_budgeted(same_mechanism_followup_candidates)
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
                selected = _select_budgeted(eligible_research)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot=_slot_for_branch(selected),
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


def _required_branch_local_diagnostic_followup(status: Any) -> bool:
    return bool(
        getattr(status, "schedulable", False)
        and not str(getattr(status, "release_reason", "") or "")
        and str(getattr(status, "lane", "") or "") == "diagnostic_followup"
        and str(getattr(status, "next_action_reason", "") or "")
        == MECHANISM_CONTRACT_BRANCH_LOCAL_FOLLOWUP_REASON
    )


def _low_value_filters_allow(branch: Branch, scheduling_status: Any) -> bool:
    # BranchSchedulingStatus owns required follow-up semantics; older
    # low-value release predicates must not override that generic contract.
    if _required_branch_local_diagnostic_followup(scheduling_status):
        return True
    return (
        (
            not _retained_checkpoint_no_effect_current_head(branch)
            or _same_mechanism_low_signal_followup_candidate(branch)
        )
        and (
            not _no_effect_slot_release_preferred(branch)
            or _branch_same_branch_refinement_sampling_candidate(branch)
            or _same_mechanism_low_signal_followup_candidate(branch)
        )
        and not _quality_regression_slot_release_preferred(branch)
        and (
            not _branch_lifecycle_budget_exhausted(branch)
            or _branch_plateau_gate_same_branch_candidate(branch)
            or _same_mechanism_low_signal_followup_candidate(branch)
        )
    )


def _same_mechanism_low_signal_followup_candidate(branch: Branch) -> bool:
    if not branch_requires_same_mechanism_followup(branch):
        return False
    if branch_lifecycle_new_mechanism_ineligible(branch):
        return False
    if branch_is_parked_lineage(branch):
        return False
    if _quality_regression_slot_release_preferred(branch):
        return False
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    return status in {
        "active_marginal",
        "active_neutral",
        "active_no_effect",
        "active_runtime_regression",
    } or tier in {
        "marginal",
        "neutral",
        "no_effect",
        "runtime_regression",
    }


def _prepared_successor_scheduling_focus(
    launch_research_focus: Mapping[str, Any] | None,
) -> _PreparedSuccessorSchedulingFocus:
    payload = _launch_focus_research_payload(launch_research_focus)
    if not payload:
        return _PreparedSuccessorSchedulingFocus()
    required_ids = _unique_strings(payload.get("required_mechanism_ids"))
    reviewed_ids = _unique_strings(payload.get("reviewed_mechanism_ids"))
    successor_families = _unique_strings(
        payload.get("successor_opportunity_families")
    )
    configured = bool(reviewed_ids or successor_families or required_ids)
    return _PreparedSuccessorSchedulingFocus(
        active=bool(not required_ids and reviewed_ids and successor_families),
        configured=configured,
        reviewed_mechanism_ids=tuple(reviewed_ids),
        successor_opportunity_families=tuple(successor_families),
        required_mechanism_ids=tuple(required_ids),
    )


def _launch_focus_research_payload(
    value: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    nested = value.get("launch_research_focus")
    if isinstance(nested, Mapping):
        return _launch_focus_research_payload(nested)
    research_focus = value.get("research_focus")
    if isinstance(research_focus, Mapping):
        return research_focus
    return value


def _prepared_successor_focus_excludes_branch(
    branch: Branch,
    focus: _PreparedSuccessorSchedulingFocus,
) -> bool:
    if not focus.active:
        return False
    if not branch_requires_same_mechanism_followup(branch):
        return False
    reviewed_ids = set(focus.reviewed_mechanism_ids)
    return bool(
        reviewed_ids
        and set(_prepared_successor_branch_mechanism_ids(branch)) & reviewed_ids
    )


def _prepared_successor_branch_mechanism_ids(branch: Branch | None) -> tuple[str, ...]:
    if branch is None:
        return ()
    return tuple(
        _unique_strings(
            branch_mechanism_ids(branch),
            getattr(branch, "allowed_mechanism_ids", ()),
        )
    )


def _prepared_successor_focus_audit_metadata(
    focus: _PreparedSuccessorSchedulingFocus,
    *,
    excluded_branches: Iterable[Branch],
) -> dict[str, Any]:
    if not focus.active:
        return {}
    excluded = list(excluded_branches)
    if not excluded:
        return {}
    return {
        "prepared_successor_focus": {
            "schema_version": "scion.prepared_successor_scheduler_focus.v1",
            "active": True,
            "decision_features_excluded": True,
            "proposal_visibility_only": True,
            "required_mechanism_ids": list(focus.required_mechanism_ids),
            "reviewed_mechanism_ids": list(focus.reviewed_mechanism_ids),
            "successor_opportunity_families": list(
                focus.successor_opportunity_families
            ),
            "excluded_branch_ids": [
                branch.branch_id for branch in excluded if branch.branch_id
            ],
            "excluded_branch_mechanism_ids": {
                branch.branch_id: list(
                    _prepared_successor_branch_mechanism_ids(branch)
                )
                for branch in excluded
                if branch.branch_id
            },
            "selection_policy": (
                "reviewed_same_mechanism_followup_requires_clean_fork"
            ),
            "clean_fork_reason": PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON,
        }
    }


def _unique_strings(*values: Any) -> tuple[str, ...]:
    items: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidates = (value,)
        elif isinstance(value, Mapping):
            candidates = value.values()
        elif isinstance(value, Iterable):
            candidates = value
        else:
            candidates = ()
        for item in candidates:
            text = str(item or "").strip()
            if text and text not in items:
                items.append(text)
    return tuple(items)


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


def branch_scheduling_status(branch: Branch | None):
    """Return the shared scheduling status used by scheduler consumers."""
    return _branch_scheduling_status(
        branch,
        policy=_active_slot_policy(),
    )


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


def _scheduler_owned_active_slot_release_reason(branch: Branch | None) -> str:
    return _signals_scheduler_owned_active_slot_release_reason(
        branch,
        has_decision_origin_park_marker=_branch_has_decision_origin_park_marker(
            branch
        ),
    )


def _low_value_active_slot_candidate_reason(branch: Branch | None) -> str:
    return _signals_low_value_active_slot_candidate_reason(
        branch,
        has_decision_origin_park_marker=_branch_has_decision_origin_park_marker(
            branch
        ),
    )


def _eligible_new_branch_slot_reclaim(branch: Branch) -> bool:
    return _signals_eligible_new_branch_slot_reclaim(
        branch,
        has_decision_origin_park_marker=_branch_has_decision_origin_park_marker(
            branch
        ),
    )
