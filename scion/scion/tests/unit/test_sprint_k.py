"""Sprint K unit tests: hypothesis cleanup, visibility improvements."""
from __future__ import annotations

import types
from datetime import datetime
from typing import Dict, List, Optional
from unittest.mock import MagicMock, call, patch

import pytest

from scion.core.branch import BranchController, _ACTIVE_STATES
from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, ContractResult,
    Decision, HypothesisProposal, HypothesisRecord, PatchProposal,
)
from scion.contract.gate import ContractGate
from scion.proposal.context_manager import ContextManager, _summarise_active_hypotheses
from scion.proposal.search_memory import (
    CampaignSearchMemory, FamilyEntry, _make_family_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_branch(state: BranchState = BranchState.STALE, bid: str = "branch-1") -> Branch:
    return Branch(
        branch_id=bid,
        state=state,
        base_champion_id=1,
        base_champion_hash="abc",
    )


def _make_h_record(bid: str = "branch-1", hid: str = "hyp-1") -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id=hid,
        branch_id=bid,
        change_locus="vehicle_level",
        action="modify",
        status="active",
        target_file="operators/foo.py",
        hypothesis_text="Improve subcategory swap operator",
    )


def _make_champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="x",
        code_snapshot_path="/tmp/champ",
        code_snapshot_hash="y",
    )


def _make_patch() -> PatchProposal:
    return PatchProposal(
        file_path="operators/foo.py",
        action="modify",
        code_content="class Foo:\n    def execute(self, solution, rng): pass\n",
    )


def _make_hypothesis(
    text: str = "Improve subcategory swap",
    locus: str = "vehicle_level",
    action: str = "modify",
    target_file: str = "operators/foo.py",
) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus=locus,
        action=action,
        target_file=target_file,
    )


# ---------------------------------------------------------------------------
# Minimal campaign harness for K1/K2
# ---------------------------------------------------------------------------

def _make_campaign_harness(
    bid: str = "branch-1",
    h_record: Optional[HypothesisRecord] = None,
    patch: Optional[PatchProposal] = None,
) -> types.SimpleNamespace:
    """Build a minimal namespace that looks like CampaignManager from K1/K2's POV."""
    champion = _make_champion()
    harness = types.SimpleNamespace()
    harness._branch_current_hypothesis = {bid: h_record} if h_record else {}
    harness._branch_patches = {bid: patch} if patch else {}
    harness._branch_hypotheses = {}
    harness._branch_workspaces = {}
    harness._champion = champion
    harness._campaign_id = "campaign-test"

    harness._hyp_store = MagicMock()
    harness._branch_ctrl = MagicMock()
    harness._contract_gate = MagicMock()
    harness._vgate = MagicMock()
    harness._materializer = MagicMock()
    harness._registry = MagicMock()
    harness._experiment_protocol = None
    return harness


# ---------------------------------------------------------------------------
# K1: _run_reconcile_step hypothesis cleanup
# ---------------------------------------------------------------------------

class TestK1ReconcileCleanup:
    """Verify _cleanup() is called on all abandon paths in _run_reconcile_step."""

    def _call(self, harness, branch):
        from scion.core.campaign import CampaignManager
        return CampaignManager._run_reconcile_step(harness, branch)

    def test_no_patch_calls_mark_status_rejected(self):
        """No patch → cleanup → reconcile_stale(success=False)."""
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        harness = _make_campaign_harness(bid=bid, h_record=h_record, patch=None)
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        result = self._call(harness, branch)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")
        assert bid not in harness._branch_current_hypothesis
        harness._branch_ctrl.reconcile_stale.assert_called_once()

    def test_workspace_setup_failed_calls_cleanup(self):
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        p = _make_patch()
        harness = _make_campaign_harness(bid=bid, h_record=h_record, patch=p)
        harness._setup_workspace = MagicMock(return_value=None)
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")

    def test_apply_patch_failed_calls_cleanup(self):
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        p = _make_patch()
        harness = _make_campaign_harness(bid=bid, h_record=h_record, patch=p)
        harness._setup_workspace = MagicMock(return_value="/tmp/ws")
        harness._materializer.apply_patch.side_effect = RuntimeError("patch fail")
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")

    def test_contract_failed_calls_cleanup(self):
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        p = _make_patch()
        harness = _make_campaign_harness(bid=bid, h_record=h_record, patch=p)
        harness._setup_workspace = MagicMock(return_value="/tmp/ws")
        harness._materializer.apply_patch.return_value = "hash1"
        harness._contract_gate.validate_patch.return_value = ContractResult(
            passed=False, checks=(), failure_reason="C4 failed"
        )
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")

    def test_verification_failed_calls_cleanup(self):
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        p = _make_patch()
        harness = _make_campaign_harness(bid=bid, h_record=h_record, patch=p)
        harness._setup_workspace = MagicMock(return_value="/tmp/ws")
        harness._materializer.apply_patch.return_value = "hash1"
        harness._contract_gate.validate_patch.return_value = ContractResult(
            passed=True, checks=()
        )
        vresult = MagicMock()
        vresult.passed = False
        vresult.first_failure = "test suite failed"
        harness._vgate.run.return_value = vresult
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")

    def test_no_experiment_protocol_calls_cleanup(self):
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        p = _make_patch()
        harness = _make_campaign_harness(bid=bid, h_record=h_record, patch=p)
        harness._setup_workspace = MagicMock(return_value="/tmp/ws")
        harness._materializer.apply_patch.return_value = "hash1"
        harness._contract_gate.validate_patch.return_value = ContractResult(
            passed=True, checks=()
        )
        vresult = MagicMock()
        vresult.passed = True
        harness._vgate.run.return_value = vresult
        harness._experiment_protocol = None
        harness._branch_hypotheses[bid] = _make_hypothesis()
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")

    def test_canary_failed_calls_cleanup(self):
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        p = _make_patch()
        harness = _make_campaign_harness(bid=bid, h_record=h_record, patch=p)
        harness._setup_workspace = MagicMock(return_value="/tmp/ws")
        harness._materializer.apply_patch.return_value = "hash1"
        harness._contract_gate.validate_patch.return_value = ContractResult(
            passed=True, checks=()
        )
        vresult = MagicMock()
        vresult.passed = True
        harness._vgate.run.return_value = vresult
        proto = MagicMock()
        proto.run_canary.return_value = CanaryResult(passed=False, reason="canary bad")
        harness._experiment_protocol = proto
        harness._branch_hypotheses[bid] = _make_hypothesis()
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")

    def test_rescreening_exception_calls_cleanup(self):
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        p = _make_patch()
        harness = _make_campaign_harness(bid=bid, h_record=h_record, patch=p)
        harness._setup_workspace = MagicMock(return_value="/tmp/ws")
        harness._materializer.apply_patch.return_value = "hash1"
        harness._contract_gate.validate_patch.return_value = ContractResult(
            passed=True, checks=()
        )
        vresult = MagicMock()
        vresult.passed = True
        harness._vgate.run.return_value = vresult
        proto = MagicMock()
        proto.run_canary.return_value = CanaryResult(passed=True, reason="ok")
        proto.run_experiment.side_effect = RuntimeError("runner crashed")
        harness._experiment_protocol = proto
        harness._branch_hypotheses[bid] = _make_hypothesis()
        harness._n_experiments = 0
        harness._budget = MagicMock()
        harness._budget.used = 0
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")

    def test_rescreening_fail_outcome_calls_cleanup(self):
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        p = _make_patch()
        harness = _make_campaign_harness(bid=bid, h_record=h_record, patch=p)
        harness._setup_workspace = MagicMock(return_value="/tmp/ws")
        harness._materializer.apply_patch.return_value = "hash1"
        harness._contract_gate.validate_patch.return_value = ContractResult(
            passed=True, checks=()
        )
        vresult = MagicMock()
        vresult.passed = True
        harness._vgate.run.return_value = vresult
        screening_result = MagicMock()
        screening_result.gate_outcome = "fail"
        proto = MagicMock()
        proto.run_canary.return_value = CanaryResult(passed=True, reason="ok")
        proto.run_experiment.return_value = screening_result
        harness._experiment_protocol = proto
        harness._branch_hypotheses[bid] = _make_hypothesis()
        harness._n_experiments = 0
        harness._budget = MagicMock()
        harness._budget.used = 0
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")

    def test_reconcile_success_does_not_call_mark_status(self):
        """Success path must NOT call mark_status — hypothesis stays active."""
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        p = _make_patch()
        harness = _make_campaign_harness(bid=bid, h_record=h_record, patch=p)
        harness._setup_workspace = MagicMock(return_value="/tmp/ws")
        harness._materializer.apply_patch.return_value = "hash1"
        harness._contract_gate.validate_patch.return_value = ContractResult(
            passed=True, checks=()
        )
        vresult = MagicMock()
        vresult.passed = True
        harness._vgate.run.return_value = vresult
        screening_result = MagicMock()
        screening_result.gate_outcome = "pass"
        proto = MagicMock()
        proto.run_canary.return_value = CanaryResult(passed=True, reason="ok")
        proto.run_experiment.return_value = screening_result
        harness._experiment_protocol = proto
        harness._branch_hypotheses[bid] = _make_hypothesis()
        harness._n_experiments = 0
        harness._budget = MagicMock()
        harness._budget.used = 0
        # Reconcile branch controller state
        reconciled_branch = _make_branch(state=BranchState.EXPLORE, bid=bid)
        harness._branch_ctrl.get_branch.return_value = reconciled_branch
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_not_called()

    def test_no_h_record_no_error(self):
        """If there's no h_record, cleanup is a no-op (no AttributeError)."""
        bid = "b1"
        harness = _make_campaign_harness(bid=bid, h_record=None, patch=None)
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        # Should not raise
        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_not_called()


# ---------------------------------------------------------------------------
# K2: _run_eval_step abort paths
# ---------------------------------------------------------------------------

class TestK2EvalCleanup:
    """Verify hypothesis cleanup happens on eval abort paths."""

    def _call(self, harness, branch):
        from scion.core.campaign import CampaignManager
        return CampaignManager._run_eval_step(harness, branch)

    def test_workspace_lost_calls_mark_status(self):
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        harness = _make_campaign_harness(bid=bid, h_record=h_record)
        # No workspace in dict
        branch = _make_branch(state=BranchState.VALIDATING, bid=bid)

        result = self._call(harness, branch)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")
        assert bid not in harness._branch_current_hypothesis
        harness._branch_ctrl.apply_decision.assert_called_with(bid, Decision.ABANDON)

    def test_hypothesis_lost_calls_mark_status(self):
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        harness = _make_campaign_harness(bid=bid, h_record=h_record)
        harness._branch_workspaces[bid] = "/tmp/ws"
        # No hypothesis in dict
        branch = _make_branch(state=BranchState.VALIDATING, bid=bid)

        result = self._call(harness, branch)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")
        assert bid not in harness._branch_current_hypothesis
        harness._branch_ctrl.apply_decision.assert_called_with(bid, Decision.ABANDON)

    def test_workspace_lost_no_h_record_no_error(self):
        """If h_record is also missing, cleanup is a no-op."""
        bid = "b1"
        harness = _make_campaign_harness(bid=bid, h_record=None)
        branch = _make_branch(state=BranchState.VALIDATING, bid=bid)

        result = self._call(harness, branch)

        harness._hyp_store.mark_status.assert_not_called()


# ---------------------------------------------------------------------------
# K2: RuntimeError abort in the run_one_step dispatcher
# ---------------------------------------------------------------------------

class TestK2RuntimeErrorCleanup:
    """Verify the outer RuntimeError handler also cleans up hypothesis."""

    def test_runtime_error_outer_calls_mark_status(self):
        """RuntimeError from _run_eval_step inside run_one_step cleans up hypothesis."""
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        harness = _make_campaign_harness(bid=bid, h_record=h_record)
        branch = _make_branch(state=BranchState.VALIDATING, bid=bid)

        from scion.core.campaign import CampaignManager

        # Mock all the run_one_step scaffolding
        harness.should_stop = MagicMock(return_value=False)
        harness._tick_blocked_branches = MagicMock()
        harness._branch_ctrl = MagicMock()
        harness._branch_ctrl.get_active_branches.return_value = [branch]
        harness._branch_ctrl.get_branch.return_value = branch

        sched = MagicMock()
        sched.action = "run_branch"
        sched.branch = branch
        harness._scheduler = MagicMock()
        harness._scheduler.select_next.return_value = sched

        harness._champion_lock = MagicMock()
        harness._champion_lock.__enter__ = MagicMock(return_value=None)
        harness._champion_lock.__exit__ = MagicMock(return_value=False)

        # _run_eval_step raises RuntimeError
        harness._branch_current_hypothesis[bid] = h_record
        harness._run_eval_step = MagicMock(side_effect=RuntimeError("no canonical"))
        result = CampaignManager.run_one_step(harness)

        harness._hyp_store.mark_status.assert_called_once_with(h_record.hypothesis_id, "rejected")
        assert bid not in harness._branch_current_hypothesis


# ---------------------------------------------------------------------------
# K3: mark_all_stale skips FROZEN_TESTING
# ---------------------------------------------------------------------------

class TestK3MarkAllStale:
    def _make_ctrl_with_branches(self, state_map: dict) -> BranchController:
        ctrl = BranchController()
        champion = _make_champion()
        for bid, state in state_map.items():
            b = Branch(
                branch_id=bid,
                state=state,
                base_champion_id=1,
                base_champion_hash="abc",
            )
            ctrl._branches[bid] = b
        return ctrl

    def test_frozen_testing_not_marked_stale(self):
        ctrl = self._make_ctrl_with_branches({
            "b-frozen": BranchState.FROZEN_TESTING,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert "b-frozen" not in affected
        assert ctrl._branches["b-frozen"].state == BranchState.FROZEN_TESTING

    def test_explore_is_marked_stale(self):
        ctrl = self._make_ctrl_with_branches({
            "b-explore": BranchState.EXPLORE,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert "b-explore" in affected
        assert ctrl._branches["b-explore"].state == BranchState.STALE

    def test_validating_is_marked_stale(self):
        ctrl = self._make_ctrl_with_branches({
            "b-val": BranchState.VALIDATING,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert "b-val" in affected
        assert ctrl._branches["b-val"].state == BranchState.STALE

    def test_ready_frozen_is_marked_stale(self):
        ctrl = self._make_ctrl_with_branches({
            "b-rf": BranchState.READY_FROZEN,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert "b-rf" in affected
        assert ctrl._branches["b-rf"].state == BranchState.STALE

    def test_mixed_states(self):
        ctrl = self._make_ctrl_with_branches({
            "b-frozen": BranchState.FROZEN_TESTING,
            "b-explore": BranchState.EXPLORE,
            "b-val": BranchState.VALIDATING,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert "b-frozen" not in affected
        assert "b-explore" in affected
        assert "b-val" in affected
        assert ctrl._branches["b-frozen"].state == BranchState.FROZEN_TESTING
        assert ctrl._branches["b-explore"].state == BranchState.STALE
        assert ctrl._branches["b-val"].state == BranchState.STALE

    def test_promoted_and_abandoned_not_affected(self):
        ctrl = self._make_ctrl_with_branches({
            "b-prom": BranchState.PROMOTED,
            "b-aband": BranchState.ABANDONED,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert affected == []


# ---------------------------------------------------------------------------
# K4: active_hyp_summary in build_round1_context
# ---------------------------------------------------------------------------

class TestK4ActiveHypSummary:
    def test_summarise_empty(self):
        result = _summarise_active_hypotheses([])
        assert result == "(none)"

    def test_summarise_single_with_file(self):
        h = HypothesisRecord(
            hypothesis_id="h1",
            branch_id="b1",
            change_locus="vehicle_level",
            action="modify",
            status="active",
            target_file="operators/foo.py",
        )
        result = _summarise_active_hypotheses([h])
        assert "vehicle_level/modify" in result
        assert "operators/foo.py" in result
        assert "OCCUPIED" in result

    def test_summarise_without_target_file(self):
        h = HypothesisRecord(
            hypothesis_id="h1",
            branch_id="b1",
            change_locus="order_level",
            action="create_new",
            status="active",
        )
        result = _summarise_active_hypotheses([h])
        assert "order_level/create_new" in result
        assert "OCCUPIED" in result

    def test_summarise_multiple(self):
        hs = [
            HypothesisRecord("h1", "b1", "vehicle_level", "modify", "active", "ops/a.py"),
            HypothesisRecord("h2", "b2", "order_level", "create_new", "active"),
        ]
        result = _summarise_active_hypotheses(hs)
        assert "vehicle_level" in result
        assert "order_level" in result
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) == 2

    def test_build_hypothesis_context_contains_occupied_key(self):
        """build_hypothesis_context returns dict with 'active_hyp_summary' key containing OCCUPIED."""
        from scion.config.problem import ProblemSpec, SearchSpace
        ctx_mgr = ContextManager()
        champion = _make_champion()
        branch = _make_branch(state=BranchState.EXPLORE)

        spec = MagicMock()
        spec.operator_categories = ["vehicle_level"]
        spec.search_space = MagicMock()
        spec.search_space.editable = ["operators/*.py"]
        spec.search_space.frozen = []
        spec.description = "test"

        active_hyps = [
            HypothesisRecord("h1", "b1", "vehicle_level", "modify", "active", "ops/a.py"),
        ]

        ctx = ctx_mgr.build_hypothesis_context(
            branch=branch,
            champion=champion,
            problem_spec=spec,
            active_hypotheses=active_hyps,
            blacklist=[],
        )

        assert "active_hyp_summary" in ctx
        assert "OCCUPIED" in ctx["active_hyp_summary"]
        assert "ops/a.py" in ctx["active_hyp_summary"]

    def test_build_hypothesis_context_empty_active(self):
        """With no active hypotheses, summary is '(none)'."""
        ctx_mgr = ContextManager()
        champion = _make_champion()
        branch = _make_branch(state=BranchState.EXPLORE)
        spec = MagicMock()
        spec.operator_categories = ["vehicle_level"]
        spec.search_space = MagicMock()
        spec.search_space.editable = ["operators/*.py"]
        spec.search_space.frozen = []
        spec.description = "test"

        ctx = ctx_mgr.build_hypothesis_context(
            branch=branch,
            champion=champion,
            problem_spec=spec,
            active_hypotheses=[],
            blacklist=[],
        )

        assert ctx["active_hyp_summary"] == "(none)"


# ---------------------------------------------------------------------------
# K5: record_contract_failure
# ---------------------------------------------------------------------------

class TestK5ContractFailure:
    def test_record_contract_failure_stored(self, tmp_path):
        from scion.lineage.registry import LineageRegistry
        db = str(tmp_path / "scion.db")
        reg = LineageRegistry(db)
        reg.record_contract_failure(
            campaign_id="c1",
            branch_id="b1",
            hypothesis_text="some text",
            change_locus="vehicle_level",
            action="modify",
            target_file="ops/foo.py",
            failure_reason="C10_novelty: duplicate",
        )
        import sqlite3
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT * FROM experiment_events WHERE event_kind='contract_fail'"
        ).fetchall()
        conn.close()
        assert len(rows) == 1

    def test_record_contract_failure_fields(self, tmp_path):
        from scion.lineage.registry import LineageRegistry
        db = str(tmp_path / "scion.db")
        reg = LineageRegistry(db)
        reg.record_contract_failure(
            campaign_id="c1",
            branch_id="b42",
            hypothesis_text="X" * 600,  # should be truncated to 500
            change_locus="order_level",
            action="create_new",
            target_file=None,
            failure_reason="C2_change_locus: invalid",
        )
        import sqlite3, json
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM experiment_events WHERE event_kind='contract_fail' LIMIT 1"
        ).fetchone()
        conn.close()
        assert row["branch_id"] == "b42"
        assert row["campaign_id"] == "c1"
        assert len(row["hypothesis_text"]) <= 500
        assert row["contract_result"] == "failed"
        assert row["stage"] == "hypothesis_contract"
        assert row["decision"] == "abandon"

    def test_campaign_calls_record_contract_failure_on_c10_fail(self):
        """campaign.py calls registry.record_contract_failure when hypothesis contract fails."""
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        harness = _make_campaign_harness(bid=bid, h_record=h_record)
        harness._branch_hypotheses = {}
        harness._pending_hypotheses = {}
        harness._round_num = 0
        harness._branch_workspaces[bid] = "/tmp/ws"
        harness._failure_streak = {}
        harness._step_history = []
        harness._hyp_store.get_by_status.return_value = []

        hyp = _make_hypothesis(text="Duplicate idea")
        h_record2 = _make_h_record(bid=bid, hid="hyp-2")

        # Contract gate returns failure
        harness._contract_gate.validate_hypothesis.return_value = ContractResult(
            passed=False, checks=(), failure_reason="C10_novelty: duplicate"
        )

        # Inject mocked round1 to return the hypothesis
        harness._round1_generate_hypothesis = MagicMock(return_value=(hyp, h_record2))
        harness._handle_failure = MagicMock()
        harness._record_step = MagicMock()
        harness._record_step_lineage = MagicMock()

        from scion.core.campaign import CampaignManager
        branch = _make_branch(state=BranchState.EXPLORE, bid=bid)
        CampaignManager._run_explore_step(harness, branch)

        harness._registry.record_contract_failure.assert_called_once()
        call_kwargs = harness._registry.record_contract_failure.call_args
        assert call_kwargs.kwargs["failure_reason"] == "C10_novelty: duplicate"
        assert call_kwargs.kwargs["branch_id"] == bid


# ---------------------------------------------------------------------------
# K6: C10 modify key includes hypothesis_text[:50]
# ---------------------------------------------------------------------------

class TestK6C10ModifyKey:
    def _make_spec(self) -> MagicMock:
        spec = MagicMock()
        spec.operator_categories = ["vehicle_level"]
        spec.search_space = MagicMock()
        spec.search_space.editable = ["operators/*.py"]
        spec.search_space.frozen = []
        return spec

    def test_modify_different_text_passes_c10(self):
        """Two modify hypotheses on same file but different text[:50] should both pass."""
        gate = ContractGate(self._make_spec())
        h1 = HypothesisRecord(
            hypothesis_id="h1", branch_id="b1",
            change_locus="vehicle_level", action="modify",
            status="active", target_file="ops/foo.py",
            hypothesis_text="A" * 60,
        )
        hyp = HypothesisProposal(
            hypothesis_text="B" * 60,  # different first 50 chars
            change_locus="vehicle_level",
            action="modify",
            target_file="ops/foo.py",
        )
        result = gate._c10_novelty(hyp, [h1], [])
        assert result.passed, f"Should pass but failed: {result.detail}"

    def test_modify_same_text_blocked_by_c10(self):
        """Two modify hypotheses with same locus/file/text[:50] should be blocked."""
        gate = ContractGate(self._make_spec())
        shared_text = "Improve the subcategory consolidation logic in foo operator"
        h1 = HypothesisRecord(
            hypothesis_id="h1", branch_id="b1",
            change_locus="vehicle_level", action="modify",
            status="active", target_file="ops/foo.py",
            hypothesis_text=shared_text,
        )
        hyp = HypothesisProposal(
            hypothesis_text=shared_text,
            change_locus="vehicle_level",
            action="modify",
            target_file="ops/foo.py",
        )
        result = gate._c10_novelty(hyp, [h1], [])
        assert not result.passed

    def test_remove_action_uses_original_key_no_text(self):
        """remove action should still use (locus, action, file) without text."""
        gate = ContractGate(self._make_spec())
        h1 = HypothesisRecord(
            hypothesis_id="h1", branch_id="b1",
            change_locus="vehicle_level", action="remove",
            status="active", target_file="ops/foo.py",
            hypothesis_text="any text",
        )
        # Same remove target — should be blocked regardless of text
        hyp = HypothesisProposal(
            hypothesis_text="completely different text here",
            change_locus="vehicle_level",
            action="remove",
            target_file="ops/foo.py",
        )
        result = gate._c10_novelty(hyp, [h1], [])
        assert not result.passed

    def test_create_new_still_uses_text_key(self):
        """create_new should also be keyed with text[:50]."""
        gate = ContractGate(self._make_spec())
        h1 = HypothesisRecord(
            hypothesis_id="h1", branch_id="b1",
            change_locus="vehicle_level", action="create_new",
            status="active", target_file=None,
            hypothesis_text="Create operator A for subcategory handling",
        )
        hyp = HypothesisProposal(
            hypothesis_text="Create operator B for totally different purpose",
            change_locus="vehicle_level",
            action="create_new",
            target_file=None,
        )
        result = gate._c10_novelty(hyp, [h1], [])
        assert result.passed, f"Different create_new text should pass, got: {result.detail}"


# ---------------------------------------------------------------------------
# K7: search_memory family_key includes target_file
# ---------------------------------------------------------------------------

class TestK7FamilyKey:
    def test_different_target_files_give_different_keys(self):
        key1 = _make_family_key("generic", "modify", "vehicle_level", "operators/foo.py")
        key2 = _make_family_key("generic", "modify", "vehicle_level", "operators/bar.py")
        assert key1 != key2

    def test_same_target_file_gives_same_key(self):
        key1 = _make_family_key("generic", "modify", "vehicle_level", "operators/foo.py")
        key2 = _make_family_key("generic", "modify", "vehicle_level", "operators/foo.py")
        assert key1 == key2

    def test_no_target_file_backward_compat(self):
        """Without target_file, key should match original 3-component format."""
        key_new = _make_family_key("generic", "modify", "vehicle_level", "")
        key_old = "generic/modify/vehicle_level"
        assert key_new == key_old

    def test_target_file_uses_filename_only(self):
        key = _make_family_key("generic", "modify", "vehicle_level", "some/deep/path/operators/foo.py")
        assert key == "generic/modify/vehicle_level/foo"

    def test_different_file_exhaustion_tracked_separately(self):
        """Two attempts on different files should create separate family entries."""
        from scion.core.models import EvalStats, ExperimentStage, HypothesisProposal, ProtocolResult, StepRecord

        mem = CampaignSearchMemory()

        def _make_step(text, file, wr=0.1, bid="b1", rnum=1):
            hyp = HypothesisProposal(
                hypothesis_text=text,
                change_locus="vehicle_level",
                action="modify",
                target_file=file,
            )
            proto = ProtocolResult(
                stage=ExperimentStage.SCREENING,
                stats=EvalStats(n_cases=5, wins=1, losses=4, ties=0,
                               win_rate=wr, median_delta=0.0, ci_low=0.0, ci_high=0.0),
                gate_outcome="fail",
                reason_codes=(),
                exposed_summary="",
                raw_metrics_ref="",
            )
            return StepRecord(
                round_num=rnum, branch_id=bid,
                hypothesis=hyp, patch=None,
                contract_passed=True, verification_passed=True,
                protocol_result=proto,
                decision=None, failure_stage=None, failure_detail=None,
            )

        for i in range(6):
            mem.update(_make_step("swap subcats in foo", "operators/foo.py", wr=0.1, rnum=i))
        for i in range(3):
            mem.update(_make_step("swap subcats in bar", "operators/bar.py", wr=0.1, rnum=i+10))

        foo_key = _make_family_key("order_swap", "modify", "vehicle_level", "operators/foo.py")
        bar_key = _make_family_key("order_swap", "modify", "vehicle_level", "operators/bar.py")
        assert foo_key in mem.families
        assert bar_key in mem.families
        assert mem.families[foo_key].total_attempts == 6
        assert mem.families[bar_key].total_attempts == 3
        # foo is exhausted (6 attempts, wr < 0.35); bar is not (only 3 attempts)
        assert mem.families[foo_key].is_exhausted
        assert not mem.families[bar_key].is_exhausted

    def test_family_entry_key_property_matches_make_family_key(self):
        entry = FamilyEntry(
            label="generic",
            locus="vehicle_level",
            action="modify",
            target_file="operators/baz.py",
        )
        expected = _make_family_key("generic", "modify", "vehicle_level", "operators/baz.py")
        assert entry.family_key == expected

    def test_family_entry_no_file_backward_compat(self):
        entry = FamilyEntry(label="generic", locus="vehicle_level", action="modify")
        assert entry.family_key == "generic/modify/vehicle_level"


# ---------------------------------------------------------------------------
# K8: C10 novelty check includes rejected hypotheses
# ---------------------------------------------------------------------------

class TestK8C10RejectsRejected:
    def _make_spec(self) -> MagicMock:
        spec = MagicMock()
        spec.operator_categories = ["order_level"]
        spec.search_space = MagicMock()
        spec.search_space.editable = ["operators/*.py"]
        spec.search_space.frozen = []
        return spec

    def _make_rejected(
        self,
        locus: str = "order_level",
        action: str = "modify",
        target_file: str = "operators/foo.py",
        text: str = "same text approach",
        hid: str = "h-rej",
    ) -> HypothesisRecord:
        return HypothesisRecord(
            hypothesis_id=hid,
            branch_id="b1",
            change_locus=locus,
            action=action,
            status="rejected",
            target_file=target_file,
            hypothesis_text=text,
        )

    # K8-1: basic — rejected hypothesis with same key blocks new proposal
    def test_rejected_same_text_blocks_c10(self):
        gate = ContractGate(self._make_spec())
        shared_text = "same text approach for foo"
        rejected = self._make_rejected(text=shared_text)
        hyp = HypothesisProposal(
            hypothesis_text=shared_text,
            change_locus="order_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate.validate_hypothesis(hyp, [], [], rejected_hypotheses=[rejected])
        assert not result.passed
        assert "C10_novelty" in (result.failure_reason or "")

    # K8-2: complement to K6 — different text[:50] is allowed even if rejected exists
    def test_rejected_different_text_passes_c10(self):
        gate = ContractGate(self._make_spec())
        rejected = self._make_rejected(text="approach A" + "x" * 50)
        hyp = HypothesisProposal(
            hypothesis_text="approach B" + "y" * 50,  # first 50 chars differ
            change_locus="order_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate.validate_hypothesis(hyp, [], [], rejected_hypotheses=[rejected])
        assert result.passed, f"Different text should pass, got: {result.failure_reason}"

    # K8-3a: backward compat — not passing rejected_hypotheses defaults to None, same behaviour
    def test_no_rejected_arg_backward_compat(self):
        gate = ContractGate(self._make_spec())
        hyp = HypothesisProposal(
            hypothesis_text="novel idea here",
            change_locus="order_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate.validate_hypothesis(hyp, [], [])
        assert result.passed

    # K8-3b: empty rejected list has no effect
    def test_empty_rejected_list_passes(self):
        gate = ContractGate(self._make_spec())
        hyp = HypothesisProposal(
            hypothesis_text="another novel idea",
            change_locus="order_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate.validate_hypothesis(hyp, [], [], rejected_hypotheses=[])
        assert result.passed

    # K8-4: blacklisted behaviour unchanged (regression)
    def test_blacklisted_still_blocked(self):
        gate = ContractGate(self._make_spec())
        shared_text = "blacklisted approach here"
        blacklisted = HypothesisRecord(
            hypothesis_id="h-bl",
            branch_id="b1",
            change_locus="order_level",
            action="modify",
            status="blacklisted",
            target_file="operators/foo.py",
            hypothesis_text=shared_text,
        )
        hyp = HypothesisProposal(
            hypothesis_text=shared_text,
            change_locus="order_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate.validate_hypothesis(hyp, [], [blacklisted])
        assert not result.passed
        assert "C10_novelty" in (result.failure_reason or "")
