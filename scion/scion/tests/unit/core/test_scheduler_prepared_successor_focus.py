from __future__ import annotations

from datetime import datetime, timedelta

from scion.core.models import Branch, BranchState
from scion.core.scheduler import (
    PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON,
    Scheduler,
)


def _branch(
    branch_id: str,
    *,
    state: BranchState = BranchState.EXPLORE,
    created_offset_s: int = 0,
) -> Branch:
    created_at = datetime(2026, 1, 1) + timedelta(seconds=created_offset_s)
    return Branch(
        branch_id=branch_id,
        state=state,
        base_champion_id=1,
        base_champion_hash="champion",
        created_at=created_at,
        updated_at=created_at,
    )


def _successor_focus(
    *,
    required: tuple[str, ...] = (),
    reviewed: tuple[str, ...] = ("reviewed_mechanism",),
    suppressed: tuple[str, ...] = (),
    successors: tuple[str, ...] = ("successor_family",),
) -> dict[str, object]:
    return {
        "required_mechanism_ids": list(required),
        "reviewed_mechanism_ids": list(reviewed),
        "suppressed_mechanism_ids": list(suppressed),
        "successor_opportunity_families": list(successors),
    }


def test_prepared_successor_focus_creates_clean_fork_for_reviewed_followup():
    branch = _branch("reviewed-branch")
    branch.branch_code_status = "active_no_effect"
    branch.branch_mechanism_ids = ("reviewed_mechanism",)

    action = Scheduler(max_active_branches=3).select_next(
        [branch],
        launch_research_focus=_successor_focus(),
    )

    assert action.action == "create_new"
    assert action.branch is None
    assert action.slot == "explore_new"
    assert action.reason == PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON
    focus_audit = action.audit_metadata["prepared_successor_focus"]
    assert focus_audit["decision_features_excluded"] is True
    assert focus_audit["excluded_branch_ids"] == ["reviewed-branch"]
    assert focus_audit["reviewed_mechanism_ids"] == ["reviewed_mechanism"]


def test_prepared_successor_focus_handles_multiple_reviewed_ids():
    branch = _branch("second-reviewed-branch")
    branch.branch_code_status = "active_no_effect"
    branch.branch_mechanism_ids = ("reviewed_b",)

    action = Scheduler(max_active_branches=3).select_next(
        [branch],
        launch_research_focus=_successor_focus(
            reviewed=("reviewed_a", "reviewed_b"),
        ),
    )

    assert action.action == "create_new"
    assert action.branch is None
    assert action.reason == PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON
    focus_audit = action.audit_metadata["prepared_successor_focus"]
    assert focus_audit["excluded_branch_ids"] == ["second-reviewed-branch"]
    assert focus_audit["reviewed_mechanism_ids"] == ["reviewed_a", "reviewed_b"]


def test_prepared_successor_focus_creates_clean_fork_for_suppressed_pending_retry():
    branch = _branch("suppressed-retry")
    branch.branch_code_status = "active_no_effect"
    branch.branch_mechanism_ids = ("suppressed_mechanism",)
    branch.pending_retry = True

    action = Scheduler(max_active_branches=3).select_next(
        [branch],
        launch_research_focus=_successor_focus(
            reviewed=(),
            suppressed=("suppressed_mechanism",),
        ),
    )

    assert action.action == "create_new"
    assert action.branch is None
    assert action.slot == "explore_new"
    assert action.reason == PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON
    focus_audit = action.audit_metadata["prepared_successor_focus"]
    assert focus_audit["excluded_branch_ids"] == ["suppressed-retry"]
    assert focus_audit["reviewed_mechanism_ids"] == []
    assert focus_audit["suppressed_mechanism_ids"] == ["suppressed_mechanism"]


def test_prepared_successor_focus_does_not_override_required_mechanism_focus():
    branch = _branch("required-branch")
    branch.branch_code_status = "active_no_effect"
    branch.branch_mechanism_ids = ("reviewed_mechanism",)

    action = Scheduler(max_active_branches=3).select_next(
        [branch],
        launch_research_focus=_successor_focus(
            required=("required_mechanism",),
        ),
    )

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.reason == "no_effect_same_mechanism_followup"


def test_prepared_successor_focus_runs_clean_existing_branch_when_available():
    reviewed = _branch("reviewed-branch", created_offset_s=0)
    reviewed.branch_code_status = "active_no_effect"
    reviewed.branch_mechanism_ids = ("reviewed_mechanism",)
    clean = _branch("clean-branch", created_offset_s=10)

    action = Scheduler(max_active_branches=3).select_next(
        [reviewed, clean],
        launch_research_focus=_successor_focus(),
    )

    assert action.action == "run_existing"
    assert action.branch is clean


def test_prepared_successor_focus_creates_clean_fork_for_reviewed_expand():
    branch = _branch("reviewed-expand", state=BranchState.EXPLORE_EXPAND)
    branch.branch_code_status = "clean"
    branch.last_screening_feedback_tier = "marginal"
    branch.branch_mechanism_ids = ("reviewed_mechanism",)

    action = Scheduler(max_active_branches=3).select_next(
        [branch],
        launch_research_focus=_successor_focus(),
    )

    assert action.action == "create_new"
    assert action.branch is None
    assert action.slot == "explore_new"
    assert action.reason == PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON
    focus_audit = action.audit_metadata["prepared_successor_focus"]
    assert focus_audit["excluded_branch_ids"] == ["reviewed-expand"]
    assert focus_audit["reviewed_mechanism_ids"] == ["reviewed_mechanism"]


def test_prepared_successor_focus_runs_unrelated_expand_when_available():
    reviewed = _branch(
        "reviewed-expand",
        state=BranchState.EXPLORE_EXPAND,
        created_offset_s=0,
    )
    reviewed.branch_code_status = "clean"
    reviewed.last_screening_feedback_tier = "marginal"
    reviewed.branch_mechanism_ids = ("reviewed_mechanism",)
    unrelated = _branch(
        "unrelated-expand",
        state=BranchState.EXPLORE_EXPAND,
        created_offset_s=10,
    )
    unrelated.branch_mechanism_ids = ("unrelated_mechanism",)

    action = Scheduler(max_active_branches=3).select_next(
        [reviewed, unrelated],
        launch_research_focus=_successor_focus(),
    )

    assert action.action == "run_existing"
    assert action.branch is unrelated


def test_prepared_successor_focus_does_not_override_validating_branch():
    branch = _branch("validating-reviewed", state=BranchState.VALIDATING)
    branch.branch_code_status = "active_no_effect"
    branch.branch_mechanism_ids = ("reviewed_mechanism",)

    action = Scheduler(max_active_branches=3).select_next(
        [branch],
        launch_research_focus=_successor_focus(),
    )

    assert action.action == "run_existing"
    assert action.branch is branch


def test_prepared_successor_focus_capacity_block_for_reviewed_expand():
    branch = _branch("reviewed-expand", state=BranchState.EXPLORE_EXPAND)
    branch.branch_code_status = "active_no_effect"
    branch.branch_mechanism_ids = ("reviewed_mechanism",)

    action = Scheduler(max_active_branches=1).select_next(
        [branch],
        launch_research_focus=_successor_focus(),
    )

    assert action.action == "at_capacity"
    assert action.branch is None
    assert action.slot == "capacity_blocked"
    assert action.reason == "active_branch_limit_reached"
    focus_audit = action.audit_metadata["prepared_successor_focus"]
    assert focus_audit["excluded_branch_ids"] == ["reviewed-expand"]
    assert focus_audit["reviewed_mechanism_ids"] == ["reviewed_mechanism"]
