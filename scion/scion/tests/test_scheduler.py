"""Tests for scion/core/scheduler.py — Scheduler."""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta
import pytest

from scion.core.models import Branch, BranchState
from scion.core.scheduler import (
    Scheduler,
    active_slot_inventory,
    reclaim_active_slot_for_new_branch,
)


def _branch(
    state: BranchState,
    created_offset_s: float = 0,
    updated_offset_s: float | None = None,
) -> Branch:
    created_at = datetime(2026, 1, 1) + timedelta(seconds=created_offset_s)
    return Branch(
        branch_id=str(uuid.uuid4()),
        state=state,
        base_champion_id=0,
        base_champion_hash="h",
        created_at=created_at,
        updated_at=(
            datetime(2026, 1, 1)
            + timedelta(
                seconds=created_offset_s
                if updated_offset_s is None
                else updated_offset_s
            )
        ),
    )


sched = Scheduler()


def test_no_branches_creates_new():
    action = sched.select_next([])
    assert action.action == "create_new"
    assert action.branch is None
    assert action.slot == "explore_new"
    assert action.reason == "new_exploration_slot_available"


def test_parked_lineage_does_not_consume_active_slot_or_schedule():
    parked = _branch(BranchState.PARKED_LINEAGE)
    parked.branch_code_status = "parked_lineage"

    action = Scheduler(max_active_branches=1).select_next([parked])
    inventory = active_slot_inventory([parked], max_active_branches=1)

    assert action.action == "create_new"
    assert action.reason == "new_exploration_slot_available"
    assert inventory["used"] == 0
    assert inventory["available"] == 1
    assert inventory["parked_lineage_ids"] == [parked.branch_id]


def test_ready_frozen_has_highest_priority():
    branches = [
        _branch(BranchState.READY_VALIDATE),
        _branch(BranchState.EXPLORE),
        _branch(BranchState.READY_FROZEN),
        _branch(BranchState.STALE),
    ]
    action = sched.select_next(branches)
    assert action.action == "run_existing"
    assert action.branch.state == BranchState.READY_FROZEN


def test_ready_validate_over_stale():
    branches = [
        _branch(BranchState.STALE),
        _branch(BranchState.READY_VALIDATE),
        _branch(BranchState.EXPLORE),
    ]
    action = sched.select_next(branches)
    assert action.branch.state == BranchState.READY_VALIDATE


def test_stale_over_explore():
    branches = [
        _branch(BranchState.EXPLORE),
        _branch(BranchState.STALE),
    ]
    action = sched.select_next(branches)
    assert action.branch.state == BranchState.STALE


def test_unestablished_explore_over_create_new():
    branches = [_branch(BranchState.EXPLORE)]
    action = sched.select_next(branches)
    assert action.action == "run_existing"
    assert action.branch.state == BranchState.EXPLORE


def test_established_explore_under_capacity_creates_new_branch():
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: bounded construction"

    action = Scheduler(max_active_branches=3).select_next([branch])

    assert action.action == "create_new"
    assert action.branch is None
    assert action.slot == "explore_new"
    assert action.reason == "established_branch_portfolio_expansion"


def test_verified_code_hash_without_direction_does_not_create_new_branch():
    branch = _branch(BranchState.EXPLORE)
    branch.current_code_hash = "candidate"
    branch.last_clean_code_hash = "candidate"

    action = Scheduler(max_active_branches=3).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.reason == "active_branch_refinement"


def test_pending_retry_under_capacity_runs_existing_branch():
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: bounded construction"
    branch.pending_retry = True

    action = Scheduler(max_active_branches=3).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.reason == "pending_retry_diagnostic_followup"


def test_lifecycle_blocked_research_branch_reroutes_to_clean_branch():
    blocked = _branch(
        BranchState.EXPLORE,
        created_offset_s=0,
        updated_offset_s=0,
    )
    blocked.direction = "solver: established"
    blocked.branch_code_status = "active_no_effect"
    blocked.branch_lifecycle_new_mechanism_ineligible = True
    blocked.branch_lifecycle_reroute_reason = (
        "clean_fork_after_branch_lifecycle_policy_block"
    )
    clean = _branch(
        BranchState.EXPLORE,
        created_offset_s=10,
        updated_offset_s=10,
    )

    action = Scheduler(max_active_branches=3).select_next([blocked, clean])

    assert action.action == "run_existing"
    assert action.branch is clean


def test_lifecycle_blocked_research_branches_do_not_create_clean_fork_at_capacity():
    branches = []
    for offset in (0, 10, 20):
        branch = _branch(
            BranchState.EXPLORE,
            created_offset_s=offset,
            updated_offset_s=offset,
        )
        branch.direction = "solver: established"
        branch.branch_code_status = "active_no_effect"
        branch.branch_lifecycle_new_mechanism_ineligible = True
        branch.branch_lifecycle_reroute_reason = (
            "clean_fork_after_branch_lifecycle_policy_block"
        )
        branches.append(branch)

    action = Scheduler(max_active_branches=3).select_next(branches)

    assert action.action == "at_capacity"
    assert action.branch is None
    assert action.reason == "active_branch_limit_reached"
    assert action.slot == "capacity_blocked"


def test_lifecycle_blocked_research_branch_under_capacity_creates_clean_fork():
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: established"
    branch.branch_code_status = "active_no_effect"
    branch.branch_lifecycle_new_mechanism_ineligible = True
    branch.branch_lifecycle_reroute_reason = (
        "clean_fork_after_branch_lifecycle_policy_block"
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "create_new"
    assert action.branch is None
    assert action.reason == "clean_fork_after_branch_lifecycle_policy_block"
    assert action.slot == "repair_diagnostic"


def test_no_effect_without_actionable_diagnostic_does_not_bypass_hard_cap():
    branch = _branch(BranchState.EXPLORE)
    branch.branch_code_status = "active_no_effect"
    branch.branch_mechanism_ids = ("bounded_probe",)

    action = Scheduler(max_active_branches=1).select_next([branch])

    assert action.action == "at_capacity"
    assert action.branch is None
    assert action.slot == "capacity_blocked"
    assert action.reason == "active_branch_limit_reached"


def test_no_effect_with_actionable_diagnostic_runs_existing_branch():
    branch = _branch(BranchState.EXPLORE)
    branch.branch_code_status = "active_no_effect"
    branch.branch_mechanism_ids = ("bounded_probe",)
    branch.failure_codes = ["diagnostic_requires_repair"]

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.slot == "repair_diagnostic"
    assert action.reason == "effect_diagnostic_followup"


def test_non_clean_followup_branch_under_capacity_prefers_clean_fork():
    branch = _branch(BranchState.EXPLORE)
    branch.branch_code_status = "active_no_effect"
    branch.branch_mechanism_ids = ("bounded_probe",)

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "create_new"
    assert action.branch is None
    assert action.reason == "clean_fork_required_for_new_mechanism"


def test_non_actionable_no_effect_followup_branches_create_clean_branch():
    branches = []
    for offset in (1, 2):
        branch = _branch(BranchState.EXPLORE, created_offset_s=offset)
        branch.branch_code_status = "active_no_effect"
        branch.branch_mechanism_ids = (f"bounded_probe_{offset}",)
        branches.append(branch)

    action = Scheduler(max_active_branches=3).select_next(branches)

    assert action.action == "create_new"
    assert action.branch is None
    assert action.reason == "clean_fork_required_for_new_mechanism"


def test_runtime_regression_diagnostic_runs_before_clean_fork():
    branch = _branch(BranchState.EXPLORE)
    branch.branch_code_status = "active_runtime_regression"
    branch.branch_mechanism_ids = ("bounded_probe",)

    action = Scheduler(max_active_branches=3).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.slot == "repair_diagnostic"
    assert action.reason == "runtime_diagnostic_followup"


def test_at_capacity_prefers_clean_research_candidate_over_non_clean_followup():
    clean = _branch(
        BranchState.EXPLORE,
        created_offset_s=20,
        updated_offset_s=20,
    )
    followup = _branch(
        BranchState.EXPLORE,
        created_offset_s=0,
        updated_offset_s=0,
    )
    followup.branch_code_status = "active_no_effect"
    followup.branch_mechanism_ids = ("bounded_probe",)

    action = Scheduler(max_active_branches=2).select_next([followup, clean])

    assert action.action == "run_existing"
    assert action.branch is clean


def test_under_capacity_prefers_clean_candidate_over_non_clean_followup():
    clean = _branch(
        BranchState.EXPLORE,
        created_offset_s=20,
        updated_offset_s=20,
    )
    followup = _branch(
        BranchState.EXPLORE,
        created_offset_s=0,
        updated_offset_s=0,
    )
    followup.direction = "solver: same-mechanism follow-up"
    followup.branch_code_status = "active_no_effect"
    followup.branch_mechanism_ids = ("bounded_probe",)

    action = Scheduler(max_active_branches=3).select_next([followup, clean])

    assert action.action == "run_existing"
    assert action.branch is clean


def test_at_capacity_multiple_explore_branches_selects_oldest_updated_at():
    b_recent = _branch(
        BranchState.EXPLORE,
        created_offset_s=0,
        updated_offset_s=30,
    )
    b_oldest_updated = _branch(
        BranchState.EXPLORE,
        created_offset_s=10,
        updated_offset_s=5,
    )
    b_middle = _branch(
        BranchState.EXPLORE,
        created_offset_s=20,
        updated_offset_s=15,
    )
    for branch in (b_recent, b_oldest_updated, b_middle):
        branch.direction = "solver: established"

    action = Scheduler(max_active_branches=3).select_next(
        [b_recent, b_middle, b_oldest_updated]
    )

    assert action.action == "run_existing"
    assert action.branch.branch_id == b_oldest_updated.branch_id
    assert action.slot == "refine_active"


def test_weak_positive_branch_uses_exploit_slot_at_capacity():
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: established"
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"

    action = Scheduler(max_active_branches=1).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.slot == "exploit_weak_positive"
    assert action.reason == "weak_positive_signal_followup"


def test_restored_checkpoint_priority_over_marginal_and_no_effect():
    restored = _branch(
        BranchState.EXPLORE,
        created_offset_s=20,
        updated_offset_s=20,
    )
    restored.direction = "solver: restored checkpoint"
    restored.branch_code_status = "regressed_followup"
    restored.best_quality_checkpoint_id = "checkpoint-best"
    restored.rollback_count = 1

    marginal = _branch(
        BranchState.EXPLORE,
        created_offset_s=0,
        updated_offset_s=0,
    )
    marginal.direction = "solver: marginal"
    marginal.branch_code_status = "active_marginal"
    marginal.last_screening_feedback_tier = "marginal"

    no_effect = _branch(
        BranchState.EXPLORE,
        created_offset_s=10,
        updated_offset_s=10,
    )
    no_effect.direction = "solver: no effect"
    no_effect.branch_code_status = "active_no_effect"

    action = Scheduler(max_active_branches=3).select_next(
        [marginal, no_effect, restored]
    )

    assert action.action == "run_existing"
    assert action.branch is restored
    assert action.slot == "refine_active"
    assert action.reason == "restored_checkpoint_followup"


def test_weak_positive_rollback_checkpoint_stays_exploit_slot():
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: restored weak positive"
    branch.branch_code_status = "regressed_followup"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.best_quality_checkpoint_id = "checkpoint-best"
    branch.rollback_count = 1

    action = Scheduler(max_active_branches=3).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.slot == "exploit_weak_positive"
    assert action.reason == "restored_weak_positive_checkpoint_followup"


def test_rollback_budget_exhausted_branch_does_not_bypass_hard_cap():
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: restored weak positive"
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.best_quality_checkpoint_id = "checkpoint-best"
    branch.rollback_count = 2

    action = Scheduler(max_active_branches=1).select_next([branch])

    assert action.action == "at_capacity"
    assert action.branch is None
    assert action.slot == "capacity_blocked"
    assert action.reason == "active_branch_limit_reached"


def test_repeated_marginal_loop_does_not_bypass_hard_cap():
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: repeated marginal"
    branch.branch_code_status = "active_marginal"
    branch.last_screening_feedback_tier = "marginal"
    branch.lifecycle_marginal_no_effect_streak = 2
    branch.lifecycle_signal_repeat_count = 2
    branch.lifecycle_last_signal_signature = (
        "wins=3;losses=3;ties=6;median_delta=0"
    )

    action = Scheduler(max_active_branches=1).select_next([branch])

    assert action.action == "at_capacity"
    assert action.branch is None
    assert action.slot == "capacity_blocked"
    assert action.reason == "active_branch_limit_reached"


def test_marginal_plateau_prefers_other_active_lineage():
    plateau = _branch(
        BranchState.EXPLORE,
        created_offset_s=0,
        updated_offset_s=0,
    )
    plateau.direction = "solver: plateau marginal"
    plateau.branch_code_status = "active_marginal"
    plateau.last_screening_feedback_tier = "marginal"
    plateau.lifecycle_marginal_no_effect_streak = 2

    clean = _branch(
        BranchState.EXPLORE,
        created_offset_s=10,
        updated_offset_s=10,
    )

    action = Scheduler(max_active_branches=2).select_next([plateau, clean])

    assert action.action == "run_existing"
    assert action.branch is clean


def test_repeated_weak_signal_does_not_bypass_hard_cap():
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: repeated weak signal"
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.lifecycle_signal_repeat_count = 2

    action = Scheduler(max_active_branches=1).select_next([branch])
    inventory = active_slot_inventory([branch], max_active_branches=1)

    assert action.action == "at_capacity"
    assert action.branch is None
    assert action.slot == "capacity_blocked"
    assert action.reason == "active_branch_limit_reached"
    assert inventory["used"] == 1
    assert inventory["available"] == 0
    assert inventory["branch_ids"] == [branch.branch_id]


@pytest.mark.parametrize(
    "status,tier,extra",
    [
        ("active_no_effect", "no_effect", {"branch_mechanism_ids": ("probe",)}),
        (
            "active_marginal",
            "marginal",
            {
                "lifecycle_marginal_no_effect_streak": 2,
                "lifecycle_signal_repeat_count": 2,
            },
        ),
        (
            "active_weak_positive",
            "weak_positive",
            {"lifecycle_signal_repeat_count": 2},
        ),
    ],
)
def test_low_value_branch_reclaim_parks_and_releases_active_slot(
    status: str,
    tier: str,
    extra: dict,
) -> None:
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: repeated low signal"
    branch.branch_code_status = status
    branch.last_screening_feedback_tier = tier
    for key, value in extra.items():
        setattr(branch, key, value)

    reconciliation = reclaim_active_slot_for_new_branch(
        [branch],
        max_active_branches=1,
    )
    inventory = active_slot_inventory([branch], max_active_branches=1)

    assert reconciliation.changed is True
    assert reconciliation.parked_branch_ids == (branch.branch_id,)
    assert branch.state == BranchState.PARKED_LINEAGE
    assert branch.branch_code_status == "parked_lineage"
    assert branch.last_branch_lifecycle_policy_block[
        "active_slot_reconciliation"
    ]["mode"] == "new_branch_reclaim"
    assert inventory["used"] == 0
    assert inventory["parked_lineage_ids"] == [branch.branch_id]


def test_parked_lineage_does_not_block_clean_fork_capacity():
    branches = []
    for offset in (0, 10, 20):
        branch = _branch(
            BranchState.EXPLORE,
            created_offset_s=offset,
            updated_offset_s=offset,
        )
        branch.direction = "solver: parked"
        branch.branch_code_status = "parked_lineage"
        branch.best_quality_checkpoint_id = f"checkpoint-{offset}"
        branches.append(branch)

    action = Scheduler(max_active_branches=3).select_next(branches)

    assert action.action == "create_new"
    assert action.branch is None
    assert action.slot == "explore_new"
    assert action.reason == "new_exploration_slot_available"


def test_regressed_followup_with_stale_weak_positive_tier_is_not_exploited():
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: established"
    branch.branch_code_status = "regressed_followup"
    branch.last_screening_feedback_tier = "weak_positive"

    action = Scheduler(max_active_branches=1).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.slot == "repair_diagnostic"
    assert action.reason == "effect_diagnostic_followup"


def test_capacity_blocked_slot_is_auditable():
    branches = []
    for offset in (0, 10, 20):
        branch = _branch(BranchState.BLOCKED_INFRA, created_offset_s=offset)
        branch.direction = "solver: established"
        branches.append(branch)

    action = Scheduler(max_active_branches=3).select_next(branches)

    assert action.action == "at_capacity"
    assert action.slot == "capacity_blocked"
    assert action.reason == "active_branch_limit_reached"


def test_fifo_within_same_tier_for_unestablished_branches():
    b_old = _branch(BranchState.EXPLORE, created_offset_s=0)
    b_new = _branch(BranchState.EXPLORE, created_offset_s=10)
    action = sched.select_next([b_new, b_old])
    assert action.branch.branch_id == b_old.branch_id


def test_ready_validate_prioritized_over_create_new_under_capacity():
    explore = _branch(BranchState.EXPLORE)
    explore.direction = "solver: established"
    ready = _branch(BranchState.READY_VALIDATE)

    action = Scheduler(max_active_branches=3).select_next([explore, ready])

    assert action.action == "run_existing"
    assert action.branch.branch_id == ready.branch_id


def test_ready_frozen_prioritized_over_create_new_under_capacity():
    explore = _branch(BranchState.EXPLORE)
    explore.current_code_hash = "candidate"
    ready = _branch(BranchState.READY_FROZEN)

    action = Scheduler(max_active_branches=3).select_next([explore, ready])

    assert action.action == "run_existing"
    assert action.branch.branch_id == ready.branch_id


def test_explore_expand_prioritized_over_create_new_under_capacity():
    explore = _branch(BranchState.EXPLORE)
    explore.direction = "solver: established"
    expand = _branch(BranchState.EXPLORE_EXPAND)

    action = Scheduler(max_active_branches=3).select_next([explore, expand])

    assert action.action == "run_existing"
    assert action.branch.branch_id == expand.branch_id


def test_only_terminal_branches_creates_new():
    from scion.core.models import BranchState
    branches = [
        _branch(BranchState.PROMOTED),
        _branch(BranchState.ABANDONED),
    ]
    action = sched.select_next(branches)
    assert action.action == "create_new"
