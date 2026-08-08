"""Focused tests split from test_campaign.py."""

import json
import shutil
from pathlib import Path

from .campaign_test_support import *  # noqa: F401,F403

from scion.core.candidate_evaluation import candidate_evaluation
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import ContractResult
from scion.proposal.context_manager.code_context import branch_current_file_sources


def _install_changed_champion_and_mark_stale(cm, tmp_path, branch_id):
    source = tmp_path / "champion_v2_source"
    shutil.copytree(tmp_path / "champion_code", source)
    (source / "operators" / "champion_added.py").write_text("CHAMPION_VERSION = 2\n")
    provisional = ChampionState(
        version=2,
        operator_pool=cm._champion.operator_pool,
        solver_config_hash=cm._champion.solver_config_hash,
        code_snapshot_path=str(source),
        code_snapshot_hash="provisional",
        weight_revision=cm._champion.weight_revision,
    )
    snapshot = cm._materializer.create_champion_snapshot(
        provisional,
        str(cm._materializer._champions_dir),
    )
    champion = ChampionState(
        version=2,
        operator_pool=cm._champion.operator_pool,
        solver_config_hash=cm._champion.solver_config_hash,
        code_snapshot_path=snapshot,
        code_snapshot_hash=cm._materializer.compute_snapshot_hash(snapshot),
        weight_revision=cm._champion.weight_revision,
    )
    cm._champion_store.promote(champion)
    cm._champion = champion
    cm._branch_ctrl.mark_all_stale(new_champion_id=champion.version)
    cm._persist_branch_state(branch_id)
    return champion


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
        assert branch.last_clean_code_hash == candidate_hash
        assert branch.branch_code_status == "provisional"
        assert branch.direction is not None
        marker = candidate_evaluation(branch)
        assert marker is not None
        assert marker["status"] == "completed"
        assert marker["kind"] == "explore"

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
        durable_workspace = Path(cm._branch_workspaces[result.branch_id])
        assert durable_workspace == tmp_path / "campaign" / "workspaces" / result.branch_id
        assert durable_workspace.is_dir()
        assert not Path(created_staging[0]).exists()
        assert cm._materializer.compute_code_hash(str(durable_workspace)) == (
            branch.last_clean_code_hash
        )
        assert cm._workspace_lifecycle.pending_candidates == {}
        assert branch.current_code_hash == branch.last_clean_code_hash
        assert branch.branch_code_status == "clean"
        marker = candidate_evaluation(branch)
        assert marker is not None
        assert marker["status"] == "completed"


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
    def test_stale_after_pending_evaluation_rejects_staging_before_reconcile(
        self,
        tmp_path,
        monkeypatch,
    ):
        """A stale interruption cannot strand a pre-Protocol staging candidate."""
        cm = _campaign(tmp_path)
        original_persist = cm._explore_step_pipeline.persist_branch_state
        marked_stale = False

        def persist_then_mark_stale(branch_id):
            nonlocal marked_stale
            original_persist(branch_id)
            if not marked_stale:
                marked_stale = True
                _install_changed_champion_and_mark_stale(cm, tmp_path, branch_id)

        monkeypatch.setattr(
            cm._explore_step_pipeline,
            "persist_branch_state",
            persist_then_mark_stale,
        )

        result = cm.run_one_step()

        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert result.reason == "stale_during_explore"
        assert result.action == "create_branch"
        assert result.execution_outcome is ExecutionOutcome.NOT_EVALUATED
        assert branch.state is BranchState.ABANDONED
        assert cm._workspace_lifecycle.pending_candidates == {}
        assert candidate_evaluation(branch) is None
        assert candidate_evaluation(cm._branch_store.load(result.branch_id)) is None
        assert branch_current_file_sources(branch, cm._step_history) == {}
        assert not any((Path(cm._campaign_dir) / "candidate_workspaces").iterdir())
        assert result.branch_id not in cm._branch_hypotheses
        assert result.branch_id not in cm._branch_patches
        assert result.branch_id not in cm._branch_current_hypothesis
        assert (
            cm._hyp_store.get_by_branch(result.branch_id)[-1].status == "not_evaluated"
        )
        workspace = Path(cm._branch_workspaces[result.branch_id])
        assert (
            "candidate = solution"
            not in (workspace / "operators" / "local_search.py").read_text()
        )

        # A fresh process reconstructs no pending/stale branch and may start
        # a new hypothesis from the current champion without stale replay.
        shutil.rmtree(tmp_path / "champion_code")
        reopened = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [_make_protocol_result(ExperimentStage.SCREENING, gate_outcome="fail")]
            ),
        )
        assert result.branch_id not in reopened._branch_ctrl._branches
        fresh_result = reopened.run_one_step()
        assert fresh_result.branch_id != result.branch_id
        assert fresh_result.decision is Decision.CONTINUE_EXPLORE

    def test_stale_branch_reconcile_with_no_patch_closes_lifecycle(self, tmp_path):
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
        assert result.attempt_kind == "reconcile_lifecycle"
        assert result.execution_outcome is None
        assert result.attempt_disposition is None
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
        champion = _install_changed_champion_and_mark_stale(
            cm,
            tmp_path,
            old_branches[0].branch_id,
        )
        cm._persist_branch_state(old_branches[1].branch_id)

        cm.run(requested_rounds=1)

        assert champion.version == 2
        assert all(
            branch.state is BranchState.ABANDONED for branch in old_branches
        )
        new_branches = [
            branch
            for branch in cm._branch_ctrl._branches.values()
            if branch.branch_id not in {old.branch_id for old in old_branches}
        ]
        assert len(new_branches) == 1
        assert new_branches[0].base_champion_id == champion.version
        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        assert status["campaign_loop"]["scheduled_calls"] == 3
        assert status["campaign_loop"]["effective_rounds_completed"] == 1
        assert status["stopped_reason"] == "requested_rounds_completed"

    def test_reconcile_verification_reject_preserves_old_durable_source(
        self,
        tmp_path,
    ):
        class PassThenFailGate(AlwaysPassVerificationGate):
            def __init__(self):
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
        old_marker = candidate_evaluation(branch)
        assert old_marker is not None
        champion = _install_changed_champion_and_mark_stale(cm, tmp_path, bid)
        champion_workspace = Path(champion.code_snapshot_path)
        clean_source = (
            champion_workspace / "operators" / "local_search.py"
        ).read_text()
        clean_hash = cm._materializer.compute_code_hash(str(champion_workspace))

        rejected = cm.run_one_step()

        branch = cm._branch_ctrl.get_branch(bid)
        clean_branch_workspace = Path(cm._branch_workspaces[bid])
        assert rejected.execution_outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert rejected.failure_stage == "verification"
        assert rejected.failure_detail == "RECONCILE_REJECT"
        assert rejected.failure_category == "research_rejected"
        assert cm._step_history[-1].attempt_kind == "reconcile_lifecycle"
        assert cm._step_history[-1].verification_passed is False
        assert "RECONCILE_REJECT" in (cm._step_history[-1].verification_detail or "")
        lineage = cm._registry.get_latest_execution_outcome(branch_id=bid)
        assert lineage is not None
        assert lineage["event_kind"] == "verification_fail"
        assert lineage["reason_code"] == "VERIFICATION_LIGHT_REJECTED"
        assert lineage["provenance"]["attempt_kind"] == "reconcile_lifecycle"
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
        assert cm._registry.query_failures()[0]["failure_code"] == ("RECONCILE_REJECT")
        assert branch.state is BranchState.ABANDONED
        assert branch.current_code_hash == clean_hash
        assert branch.last_clean_code_hash == clean_hash
        assert (
            clean_branch_workspace / "operators" / "local_search.py"
        ).read_text() == clean_source
        assert (clean_branch_workspace / "operators" / "champion_added.py").is_file()
        assert candidate_evaluation(branch) == old_marker
        assert cm._workspace_lifecycle.pending_candidates == {}

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
        clean_hash = branch.last_clean_code_hash
        old_marker = candidate_evaluation(branch)
        assert old_marker is not None
        _install_changed_champion_and_mark_stale(cm, tmp_path, bid)

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
        assert rejected.execution_outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert rejected.failure_stage == "patch_contract"
        assert rejected.failure_category == "research_rejected"
        assert cm._step_history[-1].attempt_kind == "reconcile_lifecycle"
        assert cm._step_history[-1].contract_passed is False
        lineage = cm._registry.get_latest_execution_outcome(branch_id=bid)
        assert lineage is not None
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
        assert branch.last_clean_code_hash == clean_hash
        assert (
            clean_branch_workspace / "operators" / "local_search.py"
        ).read_text() == clean_source
        assert candidate_evaluation(branch) == old_marker

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

        class ConditionalGate:
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

    def test_reopen_recomputes_verified_workspace_hash_before_provider_call(
        self,
        tmp_path,
    ):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                results=[
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="fail",
                    )
                ]
            ),
        )
        first = cm.run_one_step()
        workspace = Path(cm._branch_workspaces[first.branch_id])
        (workspace / "operators" / "local_search.py").write_text("corrupt = True\n")

        class NoCallClient:
            calls = 0

            def call(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("provider must not run during reopen validation")

            def call_with_tool(self, *args, **kwargs):
                return self.call(*args, **kwargs)

        client = NoCallClient()
        code_dir = tmp_path / "champion_code"
        with pytest.raises(RuntimeError, match="verified workspace hash mismatch"):
            CampaignManager(
                problem_spec=_make_problem_spec(str(code_dir)),
                protocol_config=_make_protocol_config(),
                split_manifest=_make_split_manifest(),
                seed_ledger=_make_seed_ledger(),
                llm_client=client,
                champion=_make_champion(str(code_dir)),
                campaign_dir=str(tmp_path / "campaign"),
                verification_gate=AlwaysPassVerificationGate(),
                experiment_protocol=MockExperimentProtocol(results=[]),
            )
        assert client.calls == 0

    def test_verification_exception_rolls_back_and_same_manager_can_continue(
        self,
        tmp_path,
    ):
        class RaiseThenPassGate:
            def __init__(self):
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
        assert cm._workspace_lifecycle.pending_candidates == {}
        assert branch.current_code_hash == branch.last_clean_code_hash
        assert branch.branch_code_status == "clean"

        result = cm.run_one_step()

        assert result.decision == Decision.CONTINUE_EXPLORE
        assert gate.calls == 2
        assert cm._workspace_lifecycle.pending_candidates == {}

    def test_cleanup_failure_is_reported_without_polluting_clean_source(
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
        result = cm.run_one_step()

        assert result.execution_outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert cm._workspace_lifecycle.pending_candidates == {}
        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert branch.current_code_hash == branch.last_clean_code_hash
        assert branch.branch_code_status == "clean"
        events = [
            event
            for event in cm._registry.query_by_branch(result.branch_id)
            if event["event_kind"] == "research_rejection"
        ]
        assert len(events) == 1
        audit = json.loads(events[0]["audit_payload_json"])
        cleanup = audit["candidate_cleanup"]
        assert cleanup["cleaned"] is False
        assert cleanup["cleanup_error"] == "OSError: cleanup unavailable"
        assert Path(cleanup["workspace"]).is_dir()

    def test_hypothesis_state_failure_stops_after_restoring_clean_source(
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
        original_mark_status = cm._hyp_store.mark_status

        def fail_mark_status(_hypothesis_id, _status):
            raise OSError("hypothesis store unavailable")

        monkeypatch.setattr(cm._hyp_store, "mark_status", fail_mark_status)
        with pytest.raises(OSError, match="hypothesis store unavailable"):
            cm.run_one_step()

        branch = next(iter(cm._branch_ctrl._branches.values()))
        assert cm._workspace_lifecycle.pending_candidates == {}
        assert branch.current_code_hash == branch.last_clean_code_hash
        assert branch.branch_code_status == "clean"
        record = cm._hyp_store.get_by_branch(branch.branch_id)[-1]
        assert record.status != "research_rejected"

        monkeypatch.setattr(cm._hyp_store, "mark_status", original_mark_status)
        cm._vgate = AlwaysPassVerificationGate()
        cm._explore_step_pipeline.verification_gate = cm._vgate
        continued = cm.run_one_step()
        assert continued.decision == Decision.CONTINUE_EXPLORE

    def test_outer_decision_persists_completed_marker_in_same_write(
        self,
        tmp_path,
        monkeypatch,
    ):
        protocol = MockExperimentProtocol(
            results=[
                _make_protocol_result(
                    ExperimentStage.SCREENING,
                    gate_outcome="fail",
                )
            ]
        )
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        def persist_then_crash(branch_id):
            branch = cm._branch_ctrl.get_branch(branch_id)
            marker = candidate_evaluation(branch)
            assert marker is not None
            assert marker["status"] == "completed"
            cm._branch_store.save(branch)
            raise OSError("crash after decision persistence")

        monkeypatch.setattr(
            cm._decision_finalizer,
            "persist_branch_state",
            persist_then_crash,
        )
        with pytest.raises(OSError, match="crash after decision persistence"):
            cm.run_one_step()

        branch = next(iter(cm._branch_ctrl._branches.values()))
        persisted = cm._branch_store.load(branch.branch_id)
        assert persisted is not None
        persisted_marker = candidate_evaluation(persisted)
        assert persisted_marker is not None
        assert persisted_marker["status"] == "completed"
        assert protocol.experiment_call_count == 1

        shutil.rmtree(tmp_path / "champion_code")
        reopened = _campaign(tmp_path, experiment_protocol=MockExperimentProtocol([]))
        restored = reopened._branch_ctrl.get_branch(branch.branch_id)
        restored_marker = candidate_evaluation(restored)
        assert restored_marker is not None
        assert restored_marker["status"] == "completed"

    def test_pending_evaluation_records_active_hypothesis_owner(
        self,
        tmp_path,
        monkeypatch,
    ):
        cm = _campaign(tmp_path, experiment_protocol=MockExperimentProtocol([]))

        def crash_before_formal(*_args, **_kwargs):
            raise OSError("crash before formal evaluation")

        monkeypatch.setattr(cm._explore_step_pipeline, "evaluate", crash_before_formal)
        with pytest.raises(OSError, match="crash before formal evaluation"):
            cm.run_one_step()

        branch = next(iter(cm._branch_ctrl._branches.values()))
        marker = candidate_evaluation(branch)
        assert marker is not None
        assert marker["status"] == "pending"
        active_records = [
            record
            for record in cm._hyp_store.get_by_branch(branch.branch_id)
            if record.status == "active"
        ]
        assert [record.hypothesis_id for record in active_records] == [
            marker["hypothesis_id"]
        ]

    def test_run_respects_max_rounds_arg(self, tmp_path):
        """run(requested_rounds=N) targets N formal evaluated rounds."""
        cm = _campaign(tmp_path, experiment_protocol=None)
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
