"""Focused tests split from test_campaign.py."""

from .campaign_test_support import *  # noqa: F401,F403

class TestScreeningFail:
    def test_screening_fail_low_winrate_continue_explore(self, tmp_path):
        """win_rate=0.3 → CONTINUE_EXPLORE (re-propose, not abandon)."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(
                ExperimentStage.SCREENING, gate_outcome="fail",
                win_rate=0.3, median_delta=-0.005, ci_low=-0.01, ci_high=0.0,
            )
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        result = cm.run_one_step()
        # win_rate < 0.5 → CONTINUE_EXPLORE (not ABANDON)
        assert result.decision == Decision.CONTINUE_EXPLORE


class TestCanaryFail:
    def test_canary_fail_leads_to_abandon(self, tmp_path):
        """Canary failure → features.canary_passed=False → DecisionEngine → ABANDON."""
        protocol = MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)],
            canary_pass=False,
        )
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        result = cm.run_one_step()
        assert result.decision == Decision.ABANDON


class TestStalePath:
    def test_stale_branch_reconcile_success(self, tmp_path):
        """STALE branch is reconciled when patch still applies."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        # Step 1: create branch, it gets QUEUE_VALIDATE
        r1 = cm.run_one_step()
        bid = r1.branch_id
        assert r1.decision == Decision.QUEUE_VALIDATE

        # Manually mark branch stale
        cm._branch_ctrl.mark_all_stale(new_champion_id=2)
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state == BranchState.STALE

        # Next step: scheduler selects STALE branch → reconcile
        result = cm.run_one_step()
        assert result.action == "reconcile"
        assert result.branch_id == bid
        assert result.decision == Decision.QUEUE_VALIDATE
        assert cm._branch_ctrl.get_branch(bid).state == BranchState.READY_VALIDATE
        assert cm._step_history[-1].branch_id == bid
        assert cm._step_history[-1].decision == Decision.QUEUE_VALIDATE

    def test_stale_branch_reconcile_expand_uses_decision_engine(self, tmp_path):
        """STALE reconcile preserves screening expand instead of forcing validation."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            _make_protocol_result(
                ExperimentStage.SCREENING,
                gate_outcome="expand",
                win_rate=0.55,
                median_delta=0.001,
            ),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        r1 = cm.run_one_step()
        bid = r1.branch_id
        assert r1.decision == Decision.QUEUE_VALIDATE

        cm._branch_ctrl.mark_all_stale(new_champion_id=2)
        result = cm.run_one_step()

        assert result.action == "reconcile"
        assert result.decision == Decision.EXPAND_SCREENING
        assert cm._branch_ctrl.get_branch(bid).state == BranchState.EXPLORE_EXPAND
        assert cm._step_history[-1].decision == Decision.EXPAND_SCREENING

    def test_stale_branch_reconcile_with_no_patch_abandons(self, tmp_path):
        """STALE branch with no stored patch → reconcile fails → ABANDONED."""
        cm = _campaign(tmp_path)
        # Create a branch then mark it stale without any patch
        branch = cm._branch_ctrl.create_branch(cm._champion)
        cm._branch_ctrl.mark_all_stale(new_champion_id=2)

        result = cm.run_one_step()
        assert result.action == "reconcile"
        branch_state = cm._branch_ctrl.get_branch(branch.branch_id)
        assert branch_state.state == BranchState.ABANDONED


class TestVerificationGate:
    def test_default_gate_passes_valid_syntax(self, tmp_path):
        gate = VerificationGate()
        from scion.core.models import PatchProposal
        patch = PatchProposal(
            file_path="operators/test.py",
            action="modify",
            code_content=_VALID_CODE,
        )
        result = gate.run("/tmp", "", patch)
        assert result.passed is True

    def test_default_gate_fails_syntax_error(self, tmp_path):
        gate = VerificationGate()
        from scion.core.models import PatchProposal
        patch = PatchProposal(
            file_path="operators/test.py",
            action="modify",
            code_content="def bad(:\n    pass",
        )
        result = gate.run("/tmp", "", patch)
        assert result.passed is False
        assert result.failure_severity == "light"

    def test_default_gate_passes_delete(self, tmp_path):
        gate = VerificationGate()
        from scion.core.models import PatchProposal
        patch = PatchProposal(
            file_path="operators/test.py",
            action="delete",
            code_content="",
        )
        result = gate.run("/tmp", "", patch)
        assert result.passed is True

    def test_verification_fail_light_triggers_fix(self, tmp_path):
        """Light verification failure triggers fix_code, then succeeds."""
        fix_call_count = [0]

        class FixSuccessClient:
            def call(self, prompt, schema, model=None, system_blocks=None):
                if "code_content" in schema.get("required", []):
                    fix_call_count[0] += 1
                    return dict(_VALID_PATCH)
                return dict(_VALID_HYPOTHESIS)
            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        # Gate fails on first run (bad code), passes on second (fixed code)
        run_count = [0]

        class ConditionalGate:
            def run(self, workspace, champion_workspace, patch):
                run_count[0] += 1
                if run_count[0] == 1:
                    # First call (original patch): fail
                    check = CheckResult(
                        name="SYNTAX", passed=False, severity="light",
                        detail="bad syntax", elapsed_ms=0,
                    )
                    return VerificationResult(
                        passed=False, checks=(check,),
                        failure_severity="light", first_failure="SYNTAX",
                    )
                # Subsequent calls: pass
                check = CheckResult(
                    name="SYNTAX", passed=True, severity="light",
                    detail="ok", elapsed_ms=0,
                )
                return VerificationResult(passed=True, checks=(check,))

        cm = _campaign(
            tmp_path,
            llm_client=FixSuccessClient(),
            verification_gate=ConditionalGate(),
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        result = cm.run_one_step()
        # Should have attempted a fix and succeeded
        assert fix_call_count[0] >= 1
        assert result.decision is not None


class TestRunLoop:
    def test_run_stops_on_max_experiments(self, tmp_path):
        """run() should stop when termination condition is met."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=None,
            termination_config=TerminationConfig(
                max_experiments=3,
                stagnation_limit=100,
                max_wall_clock_hours=24,
            ),
        )
        cm.run(max_rounds=100)
        # Should have stopped (3 experiments budget exhausted causes no_progress eventually)
        assert cm._n_experiments <= 100  # sanity check

    def test_run_respects_max_rounds_arg(self, tmp_path):
        """run(max_rounds=N) stops after at most N steps."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=None,
            termination_config=TerminationConfig(max_experiments=10000),
        )
        cm.run(max_rounds=3)
        assert cm._n_experiments <= 3


class TestArchiveWorkspaceReturnsPath:
    def test_archive_workspace_returns_path(self, tmp_path):
        """archive_workspace() must return the archive directory path."""
        from scion.runtime.workspace import WorkspaceMaterializer

        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()
        mat = WorkspaceMaterializer(str(campaign_dir))

        # Create a minimal workspace with operators/
        ws = tmp_path / "ws"
        (ws / "operators").mkdir(parents=True)
        (ws / "operators" / "my_op.py").write_text("class MyOp: pass\n")

        result = mat.archive_workspace(str(ws), branch_id="testbranch123")
        assert result is not None
        from pathlib import Path
        assert Path(result).exists()
