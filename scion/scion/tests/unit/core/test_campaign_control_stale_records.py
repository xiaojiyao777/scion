"""Focused tests split from test_campaign_control_boundaries.py."""

from .campaign_control_boundaries_test_support import *  # noqa: F401,F403

class TestStaleReconcile:
    def test_reconcile_contract_failure_skips_workspace_and_materialization(self, tmp_path):
        """Contract failure must happen before any stale workspace/code side effect."""
        protocol = _MockProtocol(results=[
            _make_protocol_result("pass"),  # initial screening
            _make_protocol_result("pass"),  # would pass if reconcile reached screening
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        r = cm.run_one_step()
        assert r.branch_id is not None
        bid = r.branch_id

        branch = cm._branch_ctrl.get_branch(bid)
        branch.state = BranchState.STALE

        runner = cm._branch_step_runner
        runner.setup_workspace = MagicMock(return_value=str(tmp_path / "should-not-exist"))
        runner.apply_patch = MagicMock()
        cm._vgate.run = MagicMock(wraps=cm._vgate.run)
        cm._contract_gate.validate_patch = MagicMock(
            return_value=ContractResult(
                passed=False,
                checks=(),
                failure_reason="forced reconcile contract failure",
            )
        )

        result = cm.run_one_step()

        assert result.action == "reconcile"
        assert "reconcile contract failed" in (result.reason or "")
        cm._contract_gate.validate_patch.assert_called_once_with(
            cm._branch_patches[bid],
            approved_hypothesis=cm._branch_hypotheses[bid],
        )
        runner.setup_workspace.assert_not_called()
        runner.apply_patch.assert_not_called()
        cm._vgate.run.assert_not_called()
        assert len(protocol.experiment_calls) == 1, (
            "contract failure must not proceed to reconcile re-screening"
        )

    def test_reconcile_contract_runs_before_workspace_and_apply_patch(self, tmp_path):
        """Stale reconcile must run Contract Gate before materialization."""
        order: List[str] = []
        protocol = _MockProtocol(results=[
            _make_protocol_result("pass"),  # initial screening
            _make_protocol_result("pass"),  # re-screening
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        r = cm.run_one_step()
        assert r.branch_id is not None
        bid = r.branch_id

        branch = cm._branch_ctrl.get_branch(bid)
        branch.state = BranchState.STALE

        runner = cm._branch_step_runner
        original_validate_patch = cm._contract_gate.validate_patch
        original_setup_workspace = runner.setup_workspace
        original_apply_patch = runner.apply_patch

        def spy_validate_patch(patch, *args, **kwargs):
            order.append("contract")
            return original_validate_patch(patch, *args, **kwargs)

        def spy_setup_workspace(*args, **kwargs):
            order.append("setup_workspace")
            return original_setup_workspace(*args, **kwargs)

        def spy_apply_patch(*args, **kwargs):
            order.append("apply_patch")
            return original_apply_patch(*args, **kwargs)

        cm._contract_gate.validate_patch = spy_validate_patch
        runner.setup_workspace = spy_setup_workspace
        runner.apply_patch = spy_apply_patch

        cm.run_one_step()

        assert "contract" in order
        assert "setup_workspace" in order
        assert "apply_patch" in order
        assert order.index("contract") < order.index("setup_workspace")
        assert order.index("contract") < order.index("apply_patch")
        assert len(protocol.experiment_calls) >= 2, (
            "happy reconcile must still reach re-screening"
        )

    def test_reconcile_reruns_contract_verification_screening(self, tmp_path):
        """_run_reconcile_step must call validate_patch, vgate.run, and run_experiment."""
        protocol = _MockProtocol(results=[
            _make_protocol_result("pass"),  # screening (step 1)
            _make_protocol_result("pass"),  # re-screening (reconcile)
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        # Step 1: create branch, do an explore step → stores patch
        r = cm.run_one_step()
        assert r.branch_id is not None
        bid = r.branch_id

        # Manually put branch in STALE state (simulate champion change)
        branch = cm._branch_ctrl.get_branch(bid)
        from scion.core.branch import BranchController
        branch.state = BranchState.STALE

        validate_patch_calls: List[Tuple[PatchProposal, Any]] = []
        original_validate_patch = cm._contract_gate.validate_patch

        def spy_validate_patch(patch, *args, **kwargs):
            validate_patch_calls.append((patch, kwargs.get("approved_hypothesis")))
            return original_validate_patch(patch, *args, **kwargs)

        vgate_calls = [0]
        original_vgate_run = cm._vgate.run

        def spy_vgate_run(ws, champ_ws, patch):
            vgate_calls[0] += 1
            return original_vgate_run(ws, champ_ws, patch)

        cm._contract_gate.validate_patch = spy_validate_patch
        cm._vgate.run = spy_vgate_run

        cm.run_one_step()  # should be reconcile

        expected_hypothesis = cm._branch_hypotheses[bid]
        assert validate_patch_calls, "reconcile must call validate_patch"
        assert all(
            approved_hypothesis is expected_hypothesis
            for _, approved_hypothesis in validate_patch_calls
        ), "reconcile must pass the approved hypothesis to validate_patch"
        assert vgate_calls[0] >= 1, "reconcile must call VerificationGate.run"
        assert len(protocol.experiment_calls) >= 2, (
            "reconcile must call run_experiment for re-screening"
        )

    def test_reconcile_action_mismatch_fails_closed(self, tmp_path):
        """A stale patch whose action no longer matches its hypothesis is abandoned."""
        protocol = _MockProtocol(results=[
            _make_protocol_result("pass"),  # initial screening
            _make_protocol_result("pass"),  # would pass if reconcile reached screening
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        r = cm.run_one_step()
        assert r.branch_id is not None
        bid = r.branch_id

        branch = cm._branch_ctrl.get_branch(bid)
        branch.state = BranchState.STALE
        cm._branch_hypotheses[bid] = HypothesisProposal(
            hypothesis_text="Remove the local search operator.",
            change_locus="local_search",
            action="remove",
            target_file="operators/local_search.py",
        )
        runner = cm._branch_step_runner
        runner.setup_workspace = MagicMock(return_value=str(tmp_path / "should-not-exist"))
        runner.apply_patch = MagicMock()
        cm._vgate.run = MagicMock(wraps=cm._vgate.run)

        result = cm.run_one_step()

        final_state = cm._branch_ctrl.get_branch(bid).state
        assert result.action == "reconcile"
        assert "reconcile contract failed" in (result.reason or "")
        assert final_state == BranchState.ABANDONED
        runner.setup_workspace.assert_not_called()
        runner.apply_patch.assert_not_called()
        cm._vgate.run.assert_not_called()
        assert len(protocol.experiment_calls) == 1, (
            "contract failure must not proceed to reconcile re-screening"
        )

    def test_reconcile_fails_to_abandoned_when_rescreen_fails(self, tmp_path):
        """If re-screening fails, the stale branch must be ABANDONED."""
        protocol = _MockProtocol(results=[
            _make_protocol_result("pass"),  # initial screening
            _make_protocol_result("fail", win_rate=0.1),  # reconcile re-screening → fail
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        # initial explore step
        r = cm.run_one_step()
        bid = r.branch_id

        # Put branch in STALE
        branch = cm._branch_ctrl.get_branch(bid)
        branch.state = BranchState.STALE

        cm.run_one_step()  # reconcile

        final_state = cm._branch_ctrl.get_branch(bid).state
        assert final_state == BranchState.ABANDONED, (
            f"stale branch should be ABANDONED after failed re-screening, "
            f"but state is {final_state.value!r}"
        )


class TestContractFailStepRecord:
    def test_contract_fail_step_record_has_no_decision(self, tmp_path):
        """StepRecord.decision must be None (not ABANDON) for contract failures."""
        cm = _campaign(tmp_path)

        # Make validate_hypothesis always fail
        cm._contract_gate.validate_hypothesis = lambda hyp, active, blacklist, rejected_hypotheses=None, current_champion_version=0: ContractResult(
            passed=False, checks=(), failure_reason="forced contract failure"
        )

        cm.run_one_step()

        contract_fail_steps = [
            s for s in cm._step_history
            if s.failure_stage == "hypothesis_contract"
        ]
        assert contract_fail_steps, "should have a hypothesis_contract failure step"
        for step in contract_fail_steps:
            assert step.decision is None, (
                f"StepRecord.decision should be None for contract failure, "
                f"but got {step.decision!r}"
            )

    def test_hypothesis_proposal_failure_writes_step_record(self, tmp_path):
        """Round-1 LLM/schema failures must appear in step history and summaries."""
        cm = _campaign(tmp_path, llm_client=MockLLMClient(mode="format_error"))

        result = cm.run_one_step()

        proposal_steps = [
            s for s in cm._step_history
            if s.failure_stage == "proposal"
        ]
        assert result.reason == "hypothesis generation failed"
        assert proposal_steps, "proposal failure should write a StepRecord"
        step = proposal_steps[0]
        assert step.round_num == 1
        assert step.decision is None
        assert step.protocol_result is None
        assert "simulated format error" in (step.failure_detail or "")
        assert step.hypothesis.change_locus == "proposal"
        events = cm._registry.query_by_branch(result.branch_id)
        assert any(e.get("event_kind") == "proposal_fail" for e in events)
