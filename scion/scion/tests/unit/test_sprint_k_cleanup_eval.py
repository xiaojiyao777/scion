"""Focused tests split from test_sprint_k.py."""

from .sprint_k_test_support import *  # noqa: F401,F403

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
        harness._setup_workspace.assert_not_called()
        harness._materializer.apply_patch.assert_not_called()
        harness._vgate.run.assert_not_called()

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

    def test_canary_failed_uses_decision_finalizer(self):
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
        harness._experiment_protocol = MagicMock()
        harness._branch_hypotheses[bid] = _make_hypothesis()
        reconciled_branch = _make_branch(state=BranchState.EXPLORE, bid=bid)
        harness._branch_ctrl.get_branch.return_value = reconciled_branch
        canary_result = CanaryResult(passed=False, reason="canary bad")
        harness._evaluate = MagicMock(return_value=(Decision.ABANDON, None, canary_result))
        from scion.core.campaign import StepResult
        harness._apply_decision_and_finalize = MagicMock(
            return_value=StepResult(
                action="reconcile",
                branch_id=bid,
                decision=Decision.ABANDON,
                reason="decision=abandon",
            )
        )
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._branch_ctrl.reconcile_stale.assert_called_once_with(
            bid, success=True, new_champion=harness._champion
        )
        harness._apply_decision_and_finalize.assert_called_once()
        harness._record_step.assert_called_once()

    def test_evaluation_abandon_uses_decision_finalizer(self):
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
        harness._experiment_protocol = MagicMock()
        harness._branch_hypotheses[bid] = _make_hypothesis()
        reconciled_branch = _make_branch(state=BranchState.EXPLORE, bid=bid)
        harness._branch_ctrl.get_branch.return_value = reconciled_branch
        canary_result = CanaryResult(passed=True, reason="ok")
        harness._evaluate = MagicMock(return_value=(Decision.ABANDON, None, canary_result))
        from scion.core.campaign import StepResult
        harness._apply_decision_and_finalize = MagicMock(
            return_value=StepResult(
                action="reconcile",
                branch_id=bid,
                decision=Decision.ABANDON,
                reason="decision=abandon",
            )
        )
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._apply_decision_and_finalize.assert_called_once()
        harness._record_step.assert_called_once()

    def test_rescreening_fail_outcome_uses_decision_finalizer(self):
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
        protocol_result = MagicMock()
        protocol_result.gate_outcome = "fail"
        protocol_result.reason_codes = ("SCREENING_FAIL_WIN_RATE",)
        harness._experiment_protocol = MagicMock()
        harness._branch_hypotheses[bid] = _make_hypothesis()
        reconciled_branch = _make_branch(state=BranchState.EXPLORE, bid=bid)
        harness._branch_ctrl.get_branch.return_value = reconciled_branch
        canary_result = CanaryResult(passed=True, reason="ok")
        harness._evaluate = MagicMock(return_value=(Decision.ABANDON, protocol_result, canary_result))
        from scion.core.campaign import StepResult
        harness._apply_decision_and_finalize = MagicMock(
            return_value=StepResult(
                action="reconcile",
                branch_id=bid,
                decision=Decision.ABANDON,
                reason="decision=abandon",
            )
        )
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._apply_decision_and_finalize.assert_called_once()
        harness._record_step.assert_called_once()

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
        protocol_result = MagicMock()
        protocol_result.gate_outcome = "pass"
        protocol_result.reason_codes = ("SCREENING_PASS",)
        harness._experiment_protocol = MagicMock()
        hypothesis = _make_hypothesis()
        harness._branch_hypotheses[bid] = hypothesis
        # Reconcile branch controller state
        reconciled_branch = _make_branch(state=BranchState.EXPLORE, bid=bid)
        harness._branch_ctrl.get_branch.return_value = reconciled_branch
        canary_result = CanaryResult(passed=True, reason="ok")
        harness._evaluate = MagicMock(
            return_value=(Decision.QUEUE_VALIDATE, protocol_result, canary_result)
        )
        from scion.core.campaign import StepResult
        harness._apply_decision_and_finalize = MagicMock(
            return_value=StepResult(
                action="reconcile",
                branch_id=bid,
                decision=Decision.QUEUE_VALIDATE,
                reason="decision=queue_validate",
            )
        )
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_not_called()
        harness._contract_gate.validate_patch.assert_called_once_with(
            p,
            approved_hypothesis=hypothesis,
        )
        harness._apply_decision_and_finalize.assert_called_once()
        harness._record_step.assert_called_once()

    def test_no_h_record_no_error(self):
        """If there's no h_record, cleanup is a no-op (no AttributeError)."""
        bid = "b1"
        harness = _make_campaign_harness(bid=bid, h_record=None, patch=None)
        branch = _make_branch(state=BranchState.STALE, bid=bid)

        # Should not raise
        self._call(harness, branch)

        harness._hyp_store.mark_status.assert_not_called()


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
