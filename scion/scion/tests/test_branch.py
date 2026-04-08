"""Tests for scion/core/branch.py — BranchController."""
from __future__ import annotations
import uuid
import pytest

from scion.core.models import (
    Branch, BranchState, ChampionState, Decision, ExperimentStage, OperatorConfig,
)
from scion.core.branch import BranchController, StateTransitionError


def _champion(version: int = 0) -> ChampionState:
    return ChampionState(
        version=version,
        operator_pool={},
        solver_config_hash="cfg_hash",
        code_snapshot_path="/snap",
        code_snapshot_hash=f"hash_v{version}",
    )


def _ctrl() -> BranchController:
    return BranchController()


# ─────────────────────────────────────────────────────────────────────────────
# create_branch
# ─────────────────────────────────────────────────────────────────────────────

def test_create_branch_starts_as_explore():
    ctrl = _ctrl()
    branch = ctrl.create_branch(_champion())
    assert branch.state == BranchState.EXPLORE
    assert branch.base_champion_id == 0


# ─────────────────────────────────────────────────────────────────────────────
# apply_decision — happy paths
# ─────────────────────────────────────────────────────────────────────────────

def test_explore_to_ready_validate():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    ctrl.apply_decision(b.branch_id, Decision.QUEUE_VALIDATE)
    assert ctrl.get_branch(b.branch_id).state == BranchState.READY_VALIDATE


def test_explore_to_explore_expand():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    ctrl.apply_decision(b.branch_id, Decision.EXPAND_SCREENING)
    assert ctrl.get_branch(b.branch_id).state == BranchState.EXPLORE_EXPAND


def test_full_promotion_path():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())

    ctrl.apply_decision(b.branch_id, Decision.QUEUE_VALIDATE)
    ctrl.schedule_branch(b.branch_id)  # READY_VALIDATE → VALIDATING
    ctrl.apply_decision(b.branch_id, Decision.QUEUE_FROZEN)
    ctrl.schedule_branch(b.branch_id)  # READY_FROZEN → FROZEN_TESTING
    ctrl.apply_decision(b.branch_id, Decision.PROMOTE)

    assert ctrl.get_branch(b.branch_id).state == BranchState.PROMOTED


def test_abandon_from_any_active():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    ctrl.apply_decision(b.branch_id, Decision.ABANDON)
    assert ctrl.get_branch(b.branch_id).state == BranchState.ABANDONED


# ─────────────────────────────────────────────────────────────────────────────
# apply_decision — invalid transitions
# ─────────────────────────────────────────────────────────────────────────────

def test_invalid_transition_raises():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    with pytest.raises(StateTransitionError):
        ctrl.apply_decision(b.branch_id, Decision.PROMOTE)  # EXPLORE → PROMOTED invalid


# ─────────────────────────────────────────────────────────────────────────────
# mark_all_stale
# ─────────────────────────────────────────────────────────────────────────────

def test_mark_all_stale():
    ctrl = _ctrl()
    b1 = ctrl.create_branch(_champion())
    b2 = ctrl.create_branch(_champion())

    affected = ctrl.mark_all_stale(new_champion_id=1)
    assert set(affected) == {b1.branch_id, b2.branch_id}
    assert ctrl.get_branch(b1.branch_id).state == BranchState.STALE


def test_mark_all_stale_skips_terminal():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    ctrl.apply_decision(b.branch_id, Decision.ABANDON)

    affected = ctrl.mark_all_stale(new_champion_id=1)
    assert b.branch_id not in affected
    assert ctrl.get_branch(b.branch_id).state == BranchState.ABANDONED


# ─────────────────────────────────────────────────────────────────────────────
# reconcile_stale
# ─────────────────────────────────────────────────────────────────────────────

def test_reconcile_stale_success():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion(version=0))
    ctrl.mark_all_stale(new_champion_id=1)
    ctrl.reconcile_stale(b.branch_id, success=True, new_champion=_champion(version=1))
    assert ctrl.get_branch(b.branch_id).state == BranchState.EXPLORE
    assert ctrl.get_branch(b.branch_id).base_champion_id == 1


def test_reconcile_stale_failure():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    ctrl.mark_all_stale(new_champion_id=1)
    ctrl.reconcile_stale(b.branch_id, success=False, new_champion=_champion(version=1))
    assert ctrl.get_branch(b.branch_id).state == BranchState.ABANDONED


# ─────────────────────────────────────────────────────────────────────────────
# get_code_base
# ─────────────────────────────────────────────────────────────────────────────

def test_get_code_base_no_clean_hash():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    assert ctrl.get_code_base(b.branch_id) == "champion"


def test_get_code_base_with_clean_hash():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    ctrl.record_verification_result(b.branch_id, passed=True, code_hash="abc123")
    # Both current_code_hash and last_clean_code_hash are set → caller should
    # reuse the existing branch workspace rather than copying from champion.
    assert ctrl.get_code_base(b.branch_id) == "branch_workspace"


def test_get_code_base_stale_returns_champion():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    ctrl.record_verification_result(b.branch_id, passed=True, code_hash="abc123")
    ctrl.mark_all_stale(new_champion_id=1)
    assert ctrl.get_code_base(b.branch_id) == "champion"


# ─────────────────────────────────────────────────────────────────────────────
# record_verification_result
# ─────────────────────────────────────────────────────────────────────────────

def test_record_verification_result_passed():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    ctrl.record_verification_result(b.branch_id, passed=True, code_hash="good_hash")
    branch = ctrl.get_branch(b.branch_id)
    assert branch.current_code_hash == "good_hash"
    assert branch.last_clean_code_hash == "good_hash"


def test_record_verification_result_failed():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    ctrl.record_verification_result(b.branch_id, passed=False, code_hash="bad_hash")
    branch = ctrl.get_branch(b.branch_id)
    assert branch.current_code_hash == "bad_hash"
    assert branch.last_clean_code_hash is None


# ─────────────────────────────────────────────────────────────────────────────
# next_stage
# ─────────────────────────────────────────────────────────────────────────────

def test_next_stage_screening():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    assert ctrl.next_stage(b.branch_id) == ExperimentStage.SCREENING


def test_next_stage_validation():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    ctrl.apply_decision(b.branch_id, Decision.QUEUE_VALIDATE)
    ctrl.schedule_branch(b.branch_id)  # → VALIDATING
    assert ctrl.next_stage(b.branch_id) == ExperimentStage.VALIDATION


def test_next_stage_frozen():
    ctrl = _ctrl()
    b = ctrl.create_branch(_champion())
    ctrl.apply_decision(b.branch_id, Decision.QUEUE_VALIDATE)
    ctrl.schedule_branch(b.branch_id)
    ctrl.apply_decision(b.branch_id, Decision.QUEUE_FROZEN)
    ctrl.schedule_branch(b.branch_id)  # → FROZEN_TESTING
    assert ctrl.next_stage(b.branch_id) == ExperimentStage.FROZEN


# ─────────────────────────────────────────────────────────────────────────────
# get_active_branches
# ─────────────────────────────────────────────────────────────────────────────

def test_get_active_branches():
    ctrl = _ctrl()
    b1 = ctrl.create_branch(_champion())
    b2 = ctrl.create_branch(_champion())
    ctrl.apply_decision(b2.branch_id, Decision.ABANDON)
    active = ctrl.get_active_branches()
    ids = {b.branch_id for b in active}
    assert b1.branch_id in ids
    assert b2.branch_id not in ids
