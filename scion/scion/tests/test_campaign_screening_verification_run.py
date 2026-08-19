"""Focused tests split from test_campaign.py."""

import json
import shutil
from pathlib import Path

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import ContractResult

from .campaign_test_support import *  # noqa: F401,F403


def _install_changed_champion_and_mark_stale(cm, tmp_path):
    source = tmp_path / "champion_v2_source"
    shutil.copytree(tmp_path / "champion_code", source)
    (source / "operators" / "champion_added.py").write_text("CHAMPION_VERSION = 2\n")
    provisional = ChampionState(
        version=2,
        operator_pool=cm._champion.operator_pool,
        code_snapshot_path=str(source),
        weight_revision=cm._champion.weight_revision,
    )
    snapshot = cm._materializer.create_champion_snapshot(
        provisional,
        str(cm._materializer._champions_dir),
    )
    champion = ChampionState(
        version=2,
        operator_pool=cm._champion.operator_pool,
        code_snapshot_path=snapshot,
        weight_revision=cm._champion.weight_revision,
    )
    cm._champion = champion
    cm._branch_ctrl.mark_all_stale(new_champion_id=champion.version)
    return champion


class TestPreProtocolObservations:
    def test_second_and_third_h_see_each_verification_rejection_once(
        self,
        tmp_path,
        monkeypatch,
    ):
        from scion.proposal.context_manager import ContextManager

        captured_h_contexts = []
        original_build = ContextManager.build_hypothesis_context

        def capture_h_context(self, **kwargs):
            context = original_build(self, **kwargs)
            captured_h_contexts.append(context)
            return context

        monkeypatch.setattr(
            ContextManager,
            "build_hypothesis_context",
            capture_h_context,
        )

        class FailTwiceThenPass(AlwaysPassVerificationGate):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def run(self, workspace, champion_workspace, patch):
                self.calls += 1
                if self.calls > 2:
                    return super().run(workspace, champion_workspace, patch)
                check = CheckResult(
                    name="V3_unit_tests",
                    passed=False,
                    severity="light",
                    detail="PRIVATE/TEST/OUTPUT",
                    elapsed_ms=0,
                    metadata={"raw_prompt": "FORBIDDEN_RAW_PROMPT"},
                )
                return VerificationResult(
                    passed=False,
                    checks=(check,),
                    failure_severity="light",
                    first_failure="PRIVATE/TEST/OUTPUT",
                )

        cm = _campaign(
            tmp_path,
            verification_gate=FailTwiceThenPass(),
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )

        first = cm.run_one_step()
        second = cm.run_one_step()
        third = cm.run_one_step()

        assert first.execution_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert second.execution_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert third.execution_outcome.outcome is ExecutionOutcome.EVALUATED
        assert "pre_protocol_observations" not in captured_h_contexts[0]
        assert len(captured_h_contexts[1]["pre_protocol_observations"]) == 1
        assert len(captured_h_contexts[2]["pre_protocol_observations"]) == 2
        assert captured_h_contexts[2]["pre_protocol_observations"] == [
            captured_h_contexts[1]["pre_protocol_observations"][0],
            captured_h_contexts[1]["pre_protocol_observations"][0],
        ]
        rendered = json.dumps(captured_h_contexts[2], sort_keys=True)
        assert "PRIVATE/TEST/OUTPUT" not in rendered
        assert "FORBIDDEN_RAW_PROMPT" not in rendered
        assert "last_research_rejection" not in rendered


class TestScreeningFail:
    def test_screening_fail_keeps_verified_candidate_and_branch_research_open(
        self, tmp_path
    ):
        """V3 §11.2 iterates from verified code without promoting it."""
        protocol = MockExperimentProtocol(
            results=[
                _make_protocol_result(
                    ExperimentStage.SCREENING,
                    gate_outcome="fail",
                    win_rate=0.3,
                    median_delta=-0.005,
                    ci_low=-0.01,
                    ci_high=0.0,
                )
            ]
        )
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        clean_workspace = Path(cm._champion.code_snapshot_path)
        clean_source = (clean_workspace / "operators" / "local_search.py").read_text()

        result = cm.run_one_step()

        branch = cm._branch_ctrl.get_branch(result.branch_id)
        workspace = Path(cm._branch_workspaces[result.branch_id])
        assert result.decision == Decision.CONTINUE_EXPLORE
        assert branch.state == BranchState.EXPLORE
        assert cm._step_history[-1].protocol_result.gate_outcome == "fail"
        candidate_source = (workspace / "operators" / "local_search.py").read_text()
        assert candidate_source != clean_source
        candidate_hash = cm._materializer.compute_code_hash(str(workspace))
        assert branch.current_code_hash == candidate_hash
        assert branch.direction is not None

    @pytest.mark.parametrize(
        ("gate_outcome", "expected_decision"),
        [
            ("pass", Decision.QUEUE_VALIDATE),
            ("expand", Decision.EXPAND_SCREENING),
        ],
    )
    def test_screening_accepts_exact_verified_staging_workspace(
        self,
        tmp_path,
        monkeypatch,
        gate_outcome,
        expected_decision,
    ):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                results=[
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome=gate_outcome,
                    )
                ]
            ),
        )
        created_staging = []
        create_candidate_workspace = cm._materializer.create_candidate_workspace

        def capture_staging(*args, **kwargs):
            workspace = create_candidate_workspace(*args, **kwargs)
            created_staging.append(workspace)
            return workspace

        monkeypatch.setattr(
            cm._materializer,
            "create_candidate_workspace",
            capture_staging,
        )

        result = cm.run_one_step()

        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert result.decision is expected_decision
        assert len(created_staging) == 1
        accepted_workspace = Path(cm._branch_workspaces[result.branch_id])
        assert accepted_workspace == Path(created_staging[0])
        assert accepted_workspace.is_dir()
        assert (
            cm._materializer.compute_code_hash(str(accepted_workspace))
            == branch.current_code_hash
        )


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
    def test_stale_after_evaluation_rejects_staging_before_reconcile(
        self,
        tmp_path,
        monkeypatch,
    ):
        """A stale interruption cannot strand a pre-Protocol staging candidate."""
        cm = _campaign(tmp_path)
        original_verify = cm._vgate.run
        marked_stale = False

        def verify_then_mark_stale(workspace, champion_workspace, patch):
            nonlocal marked_stale
            verification = original_verify(workspace, champion_workspace, patch)
            if not marked_stale:
                marked_stale = True
                _install_changed_champion_and_mark_stale(cm, tmp_path)
            return verification

        monkeypatch.setattr(
            cm._vgate,
            "run",
            verify_then_mark_stale,
        )

        result = cm.run_one_step()

        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert result.reason == "stale_during_explore"
        assert result.action == "create_branch"
        assert result.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED
        assert branch.state is BranchState.ABANDONED
        assert not any((Path(cm._campaign_dir) / "candidate_workspaces").iterdir())
        assert result.branch_id not in cm._branch_patches
        assert branch.hypothesis is None
        workspace = Path(cm._branch_workspaces[result.branch_id])
        assert (
            "candidate = solution"
            not in (workspace / "operators" / "local_search.py").read_text()
        )

    def test_stale_branch_reconcile_with_no_patch_abandons_branch(self, tmp_path):
        """A stale branch without a candidate closes without a research outcome."""
        cm = _campaign(tmp_path)
        # A promotion/weight update can stale an old branch before it owns a patch.
        branch = cm._branch_ctrl.create_branch(cm._champion)
        affected = cm._branch_ctrl.mark_stale_for_weight_update(
            champion_version=cm._champion.version,
        )
        assert affected == [branch.branch_id]
        assert branch.state is BranchState.STALE_WEIGHT_UPDATE

        result = cm.run_one_step()
        assert result.action == "reconcile"
        assert result.execution_outcome is None
        assert not hasattr(result, "attempt_disposition")
        branch_state = cm._branch_ctrl.get_branch(branch.branch_id)
        assert branch_state.state == BranchState.ABANDONED

    def test_two_patchless_stale_branches_retire_before_new_v2_research(
        self,
        tmp_path,
    ):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        old_branches = [
            cm._branch_ctrl.create_branch(cm._champion),
            cm._branch_ctrl.create_branch(cm._champion),
        ]
        champion = _install_changed_champion_and_mark_stale(cm, tmp_path)

        cm.run(requested_rounds=1)

        assert champion.version == 2
        assert all(branch.state is BranchState.ABANDONED for branch in old_branches)
        new_branches = [
            branch
            for branch in cm._branch_ctrl._branches.values()
            if branch.branch_id not in {old.branch_id for old in old_branches}
        ]
        assert len(new_branches) == 1
        assert new_branches[0].base_champion_id == champion.version
        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        assert status["run_result"]["scheduled_calls"] == 1
        assert status["run_result"]["evaluated_rounds"] == 1
        assert status["run_result"]["stop_reason"] == "requested_rounds_completed"

    def test_reconcile_verification_reject_preserves_previous_accepted_hash(
        self,
        tmp_path,
    ):
        class PassThenFailGate(AlwaysPassVerificationGate):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def run(self, workspace, champion_workspace, patch):
                self.calls += 1
                if self.calls == 1:
                    return super().run(workspace, champion_workspace, patch)
                check = CheckResult(
                    name="RECONCILE_REJECT",
                    passed=False,
                    severity="light",
                    detail="reject rebased patch",
                    elapsed_ms=0,
                )
                return VerificationResult(
                    passed=False,
                    checks=(check,),
                    failure_severity="light",
                    first_failure="RECONCILE_REJECT",
                )

        gate = PassThenFailGate()
        cm = _campaign(
            tmp_path,
            verification_gate=gate,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        initial = cm.run_one_step()
        bid = initial.branch_id
        branch = cm._branch_ctrl.get_branch(bid)
        accepted_hash = branch.current_code_hash
        assert accepted_hash is not None
        accepted_source = (
            Path(cm._branch_workspaces[bid]) / "operators" / "local_search.py"
        ).read_text()
        champion = _install_changed_champion_and_mark_stale(cm, tmp_path)
        champion_workspace = Path(champion.code_snapshot_path)
        clean_hash = cm._materializer.compute_code_hash(str(champion_workspace))

        rejected = cm.run_one_step()

        branch = cm._branch_ctrl.get_branch(bid)
        clean_branch_workspace = Path(cm._branch_workspaces[bid])
        assert rejected.execution_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert rejected.failure_stage == "verification"
        assert rejected.failure_detail == "RECONCILE_REJECT"
        assert rejected.failure_category == "research_rejected"
        assert cm._step_history[-1].verification_passed is False
        lineage = cm._registry.query_execution_outcomes(branch_id=bid)[0]
        assert lineage["event_kind"] == "verification_fail"
        assert lineage["reason_code"] == "VERIFICATION_LIGHT_REJECTED"
        assert lineage["provenance"]["verification_checks"] == [
            {
                "name": "RECONCILE_REJECT",
                "passed": False,
                "severity": "light",
                "detail": "reject rebased patch",
                "elapsed_ms": 0,
                "metadata": {},
            }
        ]
        assert cm._registry.query_failures()[0]["reason_code"] == (
            "VERIFICATION_LIGHT_REJECTED"
        )
        assert branch.state is BranchState.ABANDONED
        assert branch.current_code_hash == accepted_hash
        assert branch.current_code_hash != clean_hash
        assert (
            clean_branch_workspace / "operators" / "local_search.py"
        ).read_text() == accepted_source
        assert not (clean_branch_workspace / "operators" / "champion_added.py").exists()

    def test_reconcile_contract_reject_records_typed_failure_without_pollution(
        self,
        tmp_path,
    ):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        initial = cm.run_one_step()
        bid = initial.branch_id
        branch = cm._branch_ctrl.get_branch(bid)
        clean_branch_workspace = Path(cm._branch_workspaces[bid])
        clean_source = (
            clean_branch_workspace / "operators" / "local_search.py"
        ).read_text()
        clean_hash = branch.current_code_hash
        _install_changed_champion_and_mark_stale(cm, tmp_path)

        class RejectingContract:
            def validate_patch(self, patch, approved_hypothesis):
                del patch, approved_hypothesis
                check = CheckResult(
                    name="C_RECONCILE_SCOPE",
                    passed=False,
                    severity="heavy",
                    detail="reconcile scope rejected",
                    elapsed_ms=3,
                    metadata={"policy": "outer"},
                )
                return ContractResult(
                    passed=False,
                    checks=(check,),
                    failure_reason="C_RECONCILE_SCOPE",
                )

        cm._branch_step_runner.contract_gate = RejectingContract()
        rejected = cm.run_one_step()

        branch = cm._branch_ctrl.get_branch(bid)
        assert rejected.execution_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert rejected.failure_stage == "patch_contract"
        assert rejected.failure_category == "research_rejected"
        assert cm._step_history[-1].contract_passed is False
        lineage = cm._registry.query_execution_outcomes(branch_id=bid)[0]
        assert lineage["event_kind"] == "contract_fail"
        assert lineage["reason_code"] == "PATCH_CONTRACT_REJECTED"
        assert lineage["provenance"]["contract_checks"][0] == {
            "name": "C_RECONCILE_SCOPE",
            "passed": False,
            "severity": "heavy",
            "detail": "reconcile scope rejected",
            "elapsed_ms": 3,
            "metadata": {"policy": "outer"},
        }
        assert branch.state is BranchState.ABANDONED
        assert branch.current_code_hash == clean_hash
        assert (
            clean_branch_workspace / "operators" / "local_search.py"
        ).read_text() == clean_source

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

    def test_direct_verification_fail_light_does_not_trigger_fix(self, tmp_path):
        """Direct v3 preserves the failed patch instead of adding a third call."""
        fix_call_count = [0]

        class FixSuccessClient:
            def call(self, prompt, schema, model=None, system_blocks=None):
                if _schema_requests_patch(schema):
                    fix_call_count[0] += 1
                    if fix_call_count[0] > 1:
                        return dict(_VALID_PATCH_REPAIR)
                    return dict(_VALID_PATCH)
                return dict(_VALID_HYPOTHESIS)

            def call_with_tool(
                self, prompt, tool, model=None, system_blocks=None, request_kind=None
            ):
                del request_kind
                return self.call(
                    prompt, tool.get("input_schema", {}), model, system_blocks
                )

        # Gate fails on first run (bad code), passes on second (fixed code)
        run_count = [0]

        class ConditionalGate(AlwaysPassVerificationGate):
            def __init__(self):
                super().__init__()

            def run(self, workspace, champion_workspace, patch):
                run_count[0] += 1
                if run_count[0] == 1:
                    # First call (original patch): fail
                    check = CheckResult(
                        name="SYNTAX",
                        passed=False,
                        severity="light",
                        detail="bad syntax",
                        elapsed_ms=0,
                    )
                    return VerificationResult(
                        passed=False,
                        checks=(check,),
                        failure_severity="light",
                        first_failure="SYNTAX",
                    )
                # Subsequent calls: pass
                check = CheckResult(
                    name="SYNTAX",
                    passed=True,
                    severity="light",
                    detail="ok",
                    elapsed_ms=0,
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
        assert fix_call_count[0] == 1  # one code proposal; no fix_code call
        assert run_count[0] == 1
        assert result.decision is None
        assert cm._step_history[-1].failure_stage == "verification"

    def test_existing_output_is_rejected_before_provider_call(
        self,
        tmp_path,
    ):
        _campaign(tmp_path)

        class NoCallClient:
            calls = 0

            def call(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("provider must not run for an existing output")

            def call_with_tool(self, *args, **kwargs):
                return self.call(*args, **kwargs)

        client = NoCallClient()
        code_dir = tmp_path / "champion_code"
        spec = _make_problem_spec(str(code_dir))
        with pytest.raises(ValueError, match="campaign output must be fresh"):
            CampaignManager(
                problem_spec=spec,
                protocol_config=_make_protocol_config(),
                split_manifest=_make_split_manifest(),
                seed_ledger=_make_seed_ledger(),
                llm_client=client,
                champion=_make_champion(str(code_dir)),
                campaign_dir=str(tmp_path / "campaign"),
                verification_gate=AlwaysPassVerificationGate(),
                experiment_protocol=MockExperimentProtocol(results=[]),
                adapter=SimpleNamespace(spec=spec),
            )
        assert client.calls == 0

    def test_verification_exception_cleans_candidate_and_manager_can_continue(
        self,
        tmp_path,
    ):
        class RaiseThenPassGate(AlwaysPassVerificationGate):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def run(self, workspace, champion_workspace, patch):
                del workspace, champion_workspace, patch
                self.calls += 1
                if self.calls == 1:
                    raise OSError("verification unavailable")
                return VerificationResult(
                    passed=True,
                    checks=(
                        CheckResult(
                            name="SYNTAX",
                            passed=True,
                            severity="light",
                            detail="ok",
                            elapsed_ms=0,
                        ),
                    ),
                )

        gate = RaiseThenPassGate()
        cm = _campaign(
            tmp_path,
            verification_gate=gate,
            experiment_protocol=MockExperimentProtocol(
                results=[
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="fail",
                    )
                ]
            ),
        )

        with pytest.raises(OSError, match="verification unavailable"):
            cm.run_one_step()

        branch = next(iter(cm._branch_ctrl._branches.values()))
        assert branch.current_code_hash is None

        result = cm.run_one_step()

        assert result.decision == Decision.CONTINUE_EXPLORE
        assert gate.calls == 2

    def test_cleanup_failure_propagates_without_polluting_clean_source(
        self,
        tmp_path,
        monkeypatch,
    ):
        cm = _campaign(
            tmp_path,
            verification_gate=AlwaysFailVerificationGate(),
            experiment_protocol=MockExperimentProtocol(
                results=[
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="fail",
                    )
                ]
            ),
        )

        def fail_cleanup(_workspace):
            raise OSError("cleanup unavailable")

        monkeypatch.setattr(
            cm._materializer,
            "cleanup_candidate_workspace",
            fail_cleanup,
        )
        with pytest.raises(OSError, match="cleanup unavailable"):
            cm.run_one_step()

        branch = next(iter(cm._branch_ctrl._branches.values()))
        assert branch.current_code_hash is None
        events = [
            event
            for event in cm._registry.query_by_branch(branch.branch_id)
            if event["event_kind"] == "research_rejection"
        ]
        assert events == []

    def test_run_respects_max_rounds_arg(self, tmp_path):
        """run(requested_rounds=N) targets N formal evaluated rounds."""
        cm = _campaign(tmp_path)
        cm.run(requested_rounds=3)
        assert cm._n_experiments <= 3


class TestArchiveWorkspaceReturnsPath:
    def test_archive_workspace_returns_path(self, tmp_path):
        """archive_workspace() must return the archive directory path."""
        from scion.runtime.workspace import WorkspaceMaterializer

        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()
        mat = WorkspaceMaterializer(
            str(campaign_dir),
            editable_patterns=("operators/*.py",),
        )

        # Create a minimal declared research-surface workspace.
        ws = tmp_path / "ws"
        (ws / "operators").mkdir(parents=True)
        (ws / "operators" / "my_op.py").write_text("class MyOp: pass\n")

        result = mat.archive_workspace(str(ws), branch_id="testbranch123")
        assert result is not None
        from pathlib import Path

        assert Path(result).exists()
