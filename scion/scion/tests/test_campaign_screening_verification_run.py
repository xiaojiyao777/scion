"""Focused tests split from test_campaign.py."""

import hashlib
import shutil

import scion.runtime.workspace as workspace_module
import scion.core.verified_candidate_commit as verified_commit_module
from .campaign_test_support import *  # noqa: F401,F403

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.evidence_recording.accounting import accounting_reconciliation_fields
from scion.core.models import ContractResult, HypothesisRecord
from scion.lineage.branch_store import HypothesisStore


def _install_changed_champion_and_mark_stale(cm, tmp_path, branch_id):
    source = tmp_path / "champion_v2_source"
    shutil.copytree(tmp_path / "champion_code", source)
    (source / "operators" / "champion_added.py").write_text(
        "CHAMPION_VERSION = 2\n"
    )
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


def _leave_pending_reconcile(cm, tmp_path, branch_id, monkeypatch):
    _install_changed_champion_and_mark_stale(cm, tmp_path, branch_id)

    def crash_before_protocol(*_args, **_kwargs):
        raise OSError("crash before reconcile protocol")

    monkeypatch.setattr(cm._branch_step_runner, "evaluate", crash_before_protocol)
    with pytest.raises(OSError, match="crash before reconcile protocol"):
        cm.run_one_step()
    return cm._branch_store.load(branch_id)


class TestScreeningFail:
    def test_screening_fail_rejects_candidate_and_keeps_branch_research_open(
        self, tmp_path
    ):
        """A regressive candidate ends without turning one result into branch policy."""
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
        result = cm.run_one_step()
        assert result.decision == Decision.CONTINUE_EXPLORE
        assert cm._branch_ctrl.get_branch(result.branch_id).state == BranchState.EXPLORE
        assert cm._step_history[-1].protocol_result.gate_outcome == "fail"


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
        protocol = MockExperimentProtocol(
            results=[
                _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            ]
        )
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
        assert cm._step_history[-1].attempt_kind == "screening"
        accounting = accounting_reconciliation_fields(
            steps=cm._step_history,
            screened_rounds=2,
            effective_rounds_completed=2,
            counted_experiment_steps=2,
        )
        assert accounting["reconcile_lifecycle_steps"] == 0
        assert accounting["non_counted_lifecycle_steps"] == 0

    def test_stale_branch_reconcile_expand_uses_decision_engine(self, tmp_path):
        """STALE reconcile preserves screening expand instead of forcing validation."""
        protocol = MockExperimentProtocol(
            results=[
                _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
                _make_protocol_result(
                    ExperimentStage.SCREENING,
                    gate_outcome="expand",
                    win_rate=0.55,
                    median_delta=0.001,
                ),
            ]
        )
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

    def test_changed_champion_reconcile_reopens_with_exact_typed_identity(
        self,
        tmp_path,
    ):
        protocol = MockExperimentProtocol(
            results=[
                _make_protocol_result(ExperimentStage.SCREENING),
                _make_protocol_result(ExperimentStage.SCREENING),
            ]
        )
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        initial = cm.run_one_step()
        bid = initial.branch_id
        before = cm._branch_ctrl.get_branch(bid)
        old_hash = before.last_clean_code_hash
        old_marker = dict(
            before.branch_evidence_summary["verified_candidate_commit"]
        )
        _install_changed_champion_and_mark_stale(cm, tmp_path, bid)

        reconciled = cm.run_one_step()

        branch = cm._branch_ctrl.get_branch(bid)
        marker = branch.branch_evidence_summary["verified_candidate_commit"]
        assert reconciled.action == "reconcile"
        assert reconciled.decision == Decision.QUEUE_VALIDATE
        assert branch.last_clean_code_hash != old_hash
        assert marker["commit_kind"] == "reconcile"
        assert marker["evaluation_status"] == "completed"
        assert marker["artifact_ref"] != old_marker["artifact_ref"]
        assert cm._materializer.compute_code_hash(cm._branch_workspaces[bid]) == (
            branch.last_clean_code_hash
        )

        shutil.rmtree(tmp_path / "champion_code")
        reopened = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(results=[]),
        )
        restored = reopened._branch_ctrl.get_branch(bid)
        restored_marker = restored.branch_evidence_summary[
            "verified_candidate_commit"
        ]
        assert restored_marker == marker
        assert reopened._materializer.compute_code_hash(
            reopened._branch_workspaces[bid]
        ) == restored.last_clean_code_hash
        assert (Path(reopened._branch_workspaces[bid]) / "operators" / "champion_added.py").is_file()

    def test_reconcile_pending_reopen_runs_exact_screening_without_provider_calls(
        self,
        tmp_path,
        monkeypatch,
    ):
        client = MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        )
        cm = _campaign(
            tmp_path,
            llm_client=client,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        initial = cm.run_one_step()
        bid = initial.branch_id
        _install_changed_champion_and_mark_stale(cm, tmp_path, bid)

        def crash_before_protocol(*_args, **_kwargs):
            raise OSError("crash before reconcile protocol")

        monkeypatch.setattr(cm._branch_step_runner, "evaluate", crash_before_protocol)
        with pytest.raises(OSError, match="crash before reconcile protocol"):
            cm.run_one_step()

        persisted = cm._branch_store.load(bid)
        marker = persisted.branch_evidence_summary["verified_candidate_commit"]
        assert persisted.state is BranchState.EXPLORE
        assert marker["promotion_status"] == "committed"
        assert marker["evaluation_status"] == "pending"
        assert marker["commit_kind"] == "reconcile"

        class NoCallClient:
            calls = 0

            def call(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("reconcile recovery must not issue H/C calls")

            def call_with_tool(self, *args, **kwargs):
                return self.call(*args, **kwargs)

        class ExactScreeningProtocol(MockExperimentProtocol):
            def run_experiment(self, stage, candidate_ws, champion_ws, *args, **kwargs):
                assert stage is ExperimentStage.SCREENING
                assert Path(candidate_ws, "operators", "champion_added.py").is_file()
                return super().run_experiment(
                    stage,
                    candidate_ws,
                    champion_ws,
                    *args,
                    **kwargs,
                )

        no_call_client = NoCallClient()
        recovery_protocol = ExactScreeningProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)]
        )
        shutil.rmtree(tmp_path / "champion_code")
        reopened = CampaignManager(
            problem_spec=_make_problem_spec(str(tmp_path / "champion_code")),
            protocol_config=_make_protocol_config(),
            split_manifest=_make_split_manifest(),
            seed_ledger=_make_seed_ledger(),
            llm_client=no_call_client,
            champion=_make_champion(str(tmp_path / "champion_code")),
            campaign_dir=str(tmp_path / "campaign"),
            verification_gate=AlwaysPassVerificationGate(),
            experiment_protocol=recovery_protocol,
        )

        recovered = reopened.run_one_step()

        assert no_call_client.calls == 0
        assert recovery_protocol.experiment_call_count == 1
        assert recovered.action == "reconcile"
        assert recovered.attempt_kind == "screening"
        assert recovered.protocol_stage == "screening"
        assert recovered.decision == Decision.QUEUE_VALIDATE

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
        durable = Path(cm._branch_workspaces[bid])
        old_source = (durable / "operators" / "local_search.py").read_text()
        old_hash = branch.last_clean_code_hash
        old_marker = dict(
            branch.branch_evidence_summary["verified_candidate_commit"]
        )
        _install_changed_champion_and_mark_stale(cm, tmp_path, bid)

        rejected = cm.run_one_step()

        branch = cm._branch_ctrl.get_branch(bid)
        assert rejected.execution_outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert rejected.failure_stage == "verification"
        assert rejected.failure_detail == "RECONCILE_REJECT"
        assert rejected.failure_category == "research_rejected"
        assert cm._step_history[-1].attempt_kind == "reconcile_lifecycle"
        assert cm._step_history[-1].verification_passed is False
        assert "RECONCILE_REJECT" in (
            cm._step_history[-1].verification_detail or ""
        )
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
        assert cm._registry.query_failures()[0]["failure_code"] == (
            "RECONCILE_REJECT"
        )
        assert branch.state is BranchState.ABANDONED
        assert branch.current_code_hash == old_hash
        assert branch.last_clean_code_hash == old_hash
        assert (durable / "operators" / "local_search.py").read_text() == old_source
        assert not (durable / "operators" / "champion_added.py").exists()
        assert branch.branch_evidence_summary["verified_candidate_commit"] == (
            old_marker
        )
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
        durable = Path(cm._branch_workspaces[bid])
        old_hash = branch.last_clean_code_hash
        old_source = (durable / "operators" / "local_search.py").read_text()
        old_marker = dict(
            branch.branch_evidence_summary["verified_candidate_commit"]
        )
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
        assert branch.current_code_hash == old_hash
        assert branch.last_clean_code_hash == old_hash
        assert (durable / "operators" / "local_search.py").read_text() == old_source
        assert branch.branch_evidence_summary["verified_candidate_commit"] == (
            old_marker
        )
        assert not (
            tmp_path / "campaign" / "promotion_journals" / f"{bid}.json"
        ).exists()

    def test_reconcile_prepared_persist_failure_reopens_old_hypothesis_identity(
        self,
        tmp_path,
        monkeypatch,
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
        old_hash = branch.last_clean_code_hash
        old_hypothesis_id = cm._branch_current_hypothesis[bid].hypothesis_id
        old_marker = dict(
            branch.branch_evidence_summary["verified_candidate_commit"]
        )
        old_source = Path(
            cm._branch_workspaces[bid], "operators", "local_search.py"
        ).read_text()
        _install_changed_champion_and_mark_stale(cm, tmp_path, bid)

        def fail_prepared_persist(_branch_id):
            raise OSError("reconcile prepared persist failed")

        monkeypatch.setattr(
            cm._branch_step_runner,
            "persist_branch_state",
            fail_prepared_persist,
        )
        with pytest.raises(OSError, match="reconcile prepared persist failed"):
            cm.run_one_step()

        assert cm._branch_ctrl.get_branch(bid).state is BranchState.BLOCKED_INFRA

        journal = tmp_path / "campaign" / "promotion_journals" / f"{bid}.json"
        assert json.loads(journal.read_text())[
            "terminalize_hypothesis_on_rollback"
        ] is False

        shutil.rmtree(tmp_path / "champion_code")
        reopened = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(results=[]),
        )

        restored = reopened._branch_ctrl.get_branch(bid)
        assert restored.state is BranchState.STALE
        assert restored.current_code_hash == old_hash
        assert restored.last_clean_code_hash == old_hash
        assert reopened._branch_current_hypothesis[bid].hypothesis_id == (
            old_hypothesis_id
        )
        assert reopened._hyp_store.get_one(old_hypothesis_id).status == "active"
        assert reopened._branch_patches[bid].file_path == (
            cm._branch_patches[bid].file_path
        )
        assert restored.branch_evidence_summary["verified_candidate_commit"] == (
            old_marker
        )
        assert Path(
            reopened._branch_workspaces[bid], "operators", "local_search.py"
        ).read_text() == old_source
        assert not journal.exists()


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

    def test_rejected_second_candidate_preserves_and_persists_first_clean_source(
        self,
        tmp_path,
    ):
        second_patch = {
            "file_path": "operators/local_search.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": source_digest_for_content(_VALID_CODE_AFTER_PATCH),
            "old_string": "        return candidate\n",
            "new_string": "        return missing_name\n",
            "replace_all": False,
            "test_hint": None,
        }

        class SequentialClient:
            def __init__(self):
                self.code_calls = 0

            def call(self, prompt, schema, model=None, system_blocks=None):
                del prompt, model, system_blocks
                if _schema_requests_patch(schema):
                    self.code_calls += 1
                    return dict(_VALID_PATCH if self.code_calls == 1 else second_patch)
                return dict(_VALID_HYPOTHESIS)

            def call_with_tool(
                self,
                prompt,
                tool,
                model=None,
                system_blocks=None,
                request_kind=None,
            ):
                del request_kind
                return self.call(
                    prompt,
                    tool.get("input_schema", {}),
                    model,
                    system_blocks,
                )

        class PassThenFailGate:
            def __init__(self):
                self.calls = 0

            def run(self, workspace, champion_workspace, patch):
                del workspace, champion_workspace, patch
                self.calls += 1
                passed = self.calls == 1
                check = CheckResult(
                    name="V1b_undefined_names",
                    passed=passed,
                    severity="light",
                    detail="ok" if passed else "missing_name",
                    elapsed_ms=0,
                )
                return VerificationResult(
                    passed=passed,
                    checks=(check,),
                    failure_severity=None if passed else "light",
                    first_failure=None if passed else "V1b_undefined_names",
                )

        cm = _campaign(
            tmp_path,
            llm_client=SequentialClient(),
            verification_gate=PassThenFailGate(),
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
        bid = first.branch_id
        durable = Path(cm._branch_workspaces[bid])
        clean_source = (durable / "operators" / "local_search.py").read_text()
        clean_hash = cm._materializer.compute_code_hash(str(durable))
        assert clean_source == _VALID_CODE_AFTER_PATCH

        rejected = cm.run_one_step()

        assert rejected.execution_outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert cm._branch_workspaces[bid] == str(durable)
        assert (durable / "operators" / "local_search.py").read_text() == clean_source
        assert cm._materializer.compute_code_hash(str(durable)) == clean_hash
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.current_code_hash == clean_hash
        assert branch.last_clean_code_hash == clean_hash
        persisted = cm._branch_store.load(bid)
        assert persisted is not None
        assert persisted.current_code_hash == clean_hash
        assert persisted.last_clean_code_hash == clean_hash
        assert cm._workspace_lifecycle.pending_candidates == {}

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

    def test_cleanup_failure_requires_reopen_before_rejection_is_committed(
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
        original_cleanup = cm._materializer.cleanup_candidate_workspace

        def fail_cleanup(_workspace):
            raise OSError("cleanup unavailable")

        monkeypatch.setattr(
            cm._materializer,
            "cleanup_candidate_workspace",
            fail_cleanup,
        )
        with pytest.raises(OSError, match="cleanup unavailable"):
            cm.run_one_step()

        pending = cm._research_rejection_completion_store.pending()
        assert len(pending) == 1
        assert pending[0].status == "state_committed"
        assert pending[0].workspace_disposition == "archive_cleanup"

        monkeypatch.setattr(
            cm._materializer,
            "cleanup_candidate_workspace",
            original_cleanup,
        )
        shutil.rmtree(tmp_path / "champion_code")
        reopened = _campaign(
            tmp_path,
            verification_gate=AlwaysPassVerificationGate(),
            experiment_protocol=MockExperimentProtocol(results=[]),
        )

        assert reopened._research_rejection_completion_store.pending() == []
        counts = reopened._research_rejection_completion_store.durable_counts(
            reopened._campaign_id,
            archive_validator=lambda intent: reopened._materializer.validate_research_rejection_archive_receipt(
                dict(intent.payload)
            ),
        )
        assert counts["total"] == 1
        restored = reopened._branch_store.load(pending[0].branch_id)
        assert restored.current_code_hash == restored.last_clean_code_hash

    def test_rejection_completion_does_not_use_nontransactional_mark_status(
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
        rejected = cm.run_one_step()

        assert rejected.execution_outcome is ExecutionOutcome.RESEARCH_REJECTED
        branch = cm._branch_ctrl.get_branch(rejected.branch_id)
        assert cm._workspace_lifecycle.pending_candidates == {}
        assert branch.current_code_hash == branch.last_clean_code_hash
        assert branch.branch_code_status == "clean"
        record = cm._hyp_store.get_one(cm._step_history[-1].hypothesis_id)
        assert record.status == "research_rejected"

        monkeypatch.setattr(cm._hyp_store, "mark_status", original_mark_status)
        cm._vgate = AlwaysPassVerificationGate()
        cm._explore_step_pipeline.verification_gate = cm._vgate
        continued = cm.run_one_step()
        assert continued.decision == Decision.CONTINUE_EXPLORE

    def test_reopen_rejects_registry_activation_identity_tamper(
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
        result = cm.run_one_step()
        workspace = Path(cm._branch_workspaces[result.branch_id])
        marker = cm._branch_ctrl.get_branch(
            result.branch_id
        ).branch_evidence_summary["verified_candidate_commit"]
        assert marker["executable_snapshot_hash"] == (
            cm._materializer.compute_snapshot_hash(str(workspace))
        )
        (workspace / "registry.yaml").write_text("operators: tampered\n")

        class NoCallClient:
            calls = 0

            def call(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("provider must not run during reopen validation")

            def call_with_tool(self, *args, **kwargs):
                return self.call(*args, **kwargs)

        client = NoCallClient()
        shutil.rmtree(tmp_path / "champion_code")
        with pytest.raises(RuntimeError, match="executable identity mismatch"):
            CampaignManager(
                problem_spec=_make_problem_spec(str(tmp_path / "champion_code")),
                protocol_config=_make_protocol_config(),
                split_manifest=_make_split_manifest(),
                seed_ledger=_make_seed_ledger(),
                llm_client=client,
                champion=_make_champion(str(tmp_path / "champion_code")),
                campaign_dir=str(tmp_path / "campaign"),
                verification_gate=AlwaysPassVerificationGate(),
                experiment_protocol=MockExperimentProtocol(results=[]),
            )
        assert client.calls == 0

    def test_verified_commit_recovers_patch_ownership_after_preformal_crash(
        self,
        tmp_path,
        monkeypatch,
    ):
        second_patch = {
            "file_path": "operators/local_search.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": source_digest_for_content(_VALID_CODE_AFTER_PATCH),
            "old_string": "        return candidate\n",
            "new_string": (
                "        second_candidate = candidate\n"
                "        return second_candidate\n"
            ),
            "replace_all": False,
            "test_hint": None,
        }

        class SequentialClient:
            def __init__(self):
                self.code_calls = 0
                self.calls = 0

            def call(self, prompt, schema, model=None, system_blocks=None):
                del prompt, model, system_blocks
                self.calls += 1
                if _schema_requests_patch(schema):
                    self.code_calls += 1
                    return dict(_VALID_PATCH if self.code_calls == 1 else second_patch)
                return dict(_VALID_HYPOTHESIS)

            def call_with_tool(
                self,
                prompt,
                tool,
                model=None,
                system_blocks=None,
                request_kind=None,
            ):
                del request_kind
                return self.call(
                    prompt,
                    tool.get("input_schema", {}),
                    model,
                    system_blocks,
                )

        client = SequentialClient()
        cm = _campaign(
            tmp_path,
            llm_client=client,
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
        branch = cm._branch_ctrl.get_branch(first.branch_id)
        h1_formal_ref = branch.branch_evidence_summary[
            "formal_candidate_patch_artifact_ref"
        ]
        assert (tmp_path / "campaign" / h1_formal_ref).is_file()

        def crash_before_formal(*_args, **_kwargs):
            raise OSError("crash before formal evaluation")

        monkeypatch.setattr(cm._explore_step_pipeline, "evaluate", crash_before_formal)
        with pytest.raises(OSError, match="crash before formal evaluation"):
            cm.run_one_step()

        assert client.calls == 4
        marker = branch.branch_evidence_summary["verified_candidate_commit"]
        assert marker["evaluation_status"] == "pending"
        assert marker["promotion_status"] == "committed"
        assert "patch" not in marker
        assert "code_content" not in marker
        artifact_path = tmp_path / "campaign" / marker["artifact_ref"]
        assert artifact_path.is_file()
        assert json.loads(artifact_path.read_text())["base_code_hash"]

        class NoCallClient:
            calls = 0

            def call(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("pending evaluation must not issue H/C calls")

            def call_with_tool(self, *args, **kwargs):
                return self.call(*args, **kwargs)

        class CapturingProtocol(MockExperimentProtocol):
            def run_experiment(
                self,
                stage,
                candidate_ws,
                champion_ws,
                hypothesis_action,
                expand=False,
                expand_round=1,
            ):
                assert stage is ExperimentStage.SCREENING
                assert expand is False
                source = Path(candidate_ws, "operators", "local_search.py").read_text()
                assert "second_candidate = candidate" in source
                return super().run_experiment(
                    stage,
                    candidate_ws,
                    champion_ws,
                    hypothesis_action,
                    expand=expand,
                    expand_round=expand_round,
                )

        no_call_client = NoCallClient()
        recovery_protocol = CapturingProtocol(
            results=[
                _make_protocol_result(
                    ExperimentStage.SCREENING,
                    gate_outcome="pass",
                )
            ]
        )

        shutil.rmtree(tmp_path / "champion_code")
        reopened = CampaignManager(
            problem_spec=_make_problem_spec(str(tmp_path / "champion_code")),
            protocol_config=_make_protocol_config(),
            split_manifest=_make_split_manifest(),
            seed_ledger=_make_seed_ledger(),
            llm_client=no_call_client,
            champion=_make_champion(str(tmp_path / "champion_code")),
            campaign_dir=str(tmp_path / "campaign"),
            verification_gate=AlwaysPassVerificationGate(),
            experiment_protocol=recovery_protocol,
        )

        bid = branch.branch_id
        assert reopened._branch_patches[bid].file_path == "operators/local_search.py"
        assert "second_candidate = candidate" in reopened._branch_patches[
            bid
        ].code_content
        assert reopened._branch_current_hypothesis[bid].hypothesis_id == (
            marker["hypothesis_id"]
        )
        recovered = reopened.run_one_step()
        assert no_call_client.calls == 0
        assert recovery_protocol.experiment_call_count == 1
        assert recovered.action == "explore"
        assert recovered.protocol_stage == "screening"
        assert recovered.decision == Decision.QUEUE_VALIDATE
        completed = reopened._branch_ctrl.get_branch(bid).branch_evidence_summary[
            "verified_candidate_commit"
        ]
        assert completed["evaluation_status"] == "completed"

        artifact_path.write_text(artifact_path.read_text() + " ")
        with pytest.raises(RuntimeError, match="commit artifact digest mismatch"):
            _campaign(tmp_path)

    def test_promote_to_commit_persistence_window_fails_closed_on_reopen(
        self,
        tmp_path,
        monkeypatch,
    ):
        second_patch = {
            "file_path": "operators/local_search.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": source_digest_for_content(_VALID_CODE_AFTER_PATCH),
            "old_string": "        return candidate\n",
            "new_string": (
                "        second_candidate = candidate\n"
                "        return second_candidate\n"
            ),
            "replace_all": False,
            "test_hint": None,
        }

        class SequentialClient:
            def __init__(self):
                self.code_calls = 0

            def call(self, prompt, schema, model=None, system_blocks=None):
                del prompt, model, system_blocks
                if _schema_requests_patch(schema):
                    self.code_calls += 1
                    return dict(_VALID_PATCH if self.code_calls == 1 else second_patch)
                return dict(_VALID_HYPOTHESIS)

            def call_with_tool(
                self,
                prompt,
                tool,
                model=None,
                system_blocks=None,
                request_kind=None,
            ):
                del request_kind
                return self.call(
                    prompt,
                    tool.get("input_schema", {}),
                    model,
                    system_blocks,
                )

        cm = _campaign(
            tmp_path,
            llm_client=SequentialClient(),
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
        bid = first.branch_id
        persisted_h1 = cm._branch_store.load(bid)
        persisted_clean_hash = persisted_h1.last_clean_code_hash
        h1_marker = dict(
            persisted_h1.branch_evidence_summary["verified_candidate_commit"]
        )

        def fail_prepared_branch_persist(_branch_id):
            raise OSError("branch store unavailable")

        monkeypatch.setattr(
            cm._explore_step_pipeline,
            "persist_branch_state",
            fail_prepared_branch_persist,
        )
        with pytest.raises(OSError, match="branch store unavailable"):
            cm.run_one_step()

        h2_id = cm._branch_ctrl.get_branch(bid).branch_evidence_summary[
            "verified_candidate_commit"
        ]["hypothesis_id"]
        workspace = cm._branch_workspaces[bid]
        assert cm._materializer.compute_code_hash(workspace) != persisted_clean_hash

        third_hypothesis = dict(_VALID_HYPOTHESIS)
        third_hypothesis["hypothesis_text"] = "Third hypothesis after rollback."
        third_patch = {
            "file_path": "operators/local_search.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": source_digest_for_content(_VALID_CODE_AFTER_PATCH),
            "old_string": "        return candidate\n",
            "new_string": (
                "        third_candidate = candidate\n"
                "        return third_candidate\n"
            ),
            "replace_all": False,
            "test_hint": None,
        }

        class NextClient:
            def __init__(self):
                self.calls = 0

            def call(self, prompt, schema, model=None, system_blocks=None):
                del prompt, model, system_blocks
                self.calls += 1
                if _schema_requests_patch(schema):
                    return dict(third_patch)
                return dict(third_hypothesis)

            def call_with_tool(
                self,
                prompt,
                tool,
                model=None,
                system_blocks=None,
                request_kind=None,
            ):
                del request_kind
                return self.call(
                    prompt,
                    tool.get("input_schema", {}),
                    model,
                    system_blocks,
                )

        next_client = NextClient()
        original_mark_status = HypothesisStore.mark_status

        def fail_rollback_terminalization(self, hypothesis_id, status):
            if hypothesis_id == h2_id and status == "blocked_infra":
                raise OSError("rollback ownership persistence unavailable")
            return original_mark_status(self, hypothesis_id, status)

        monkeypatch.setattr(
            HypothesisStore,
            "mark_status",
            fail_rollback_terminalization,
        )
        shutil.rmtree(tmp_path / "champion_code")
        with pytest.raises(
            OSError,
            match="rollback ownership persistence unavailable",
        ):
            _campaign(tmp_path)
        rollback_journal = (
            tmp_path / "campaign" / "promotion_journals" / f"{bid}.json"
        )
        assert json.loads(rollback_journal.read_text())["status"] == "rolled_back"

        monkeypatch.setattr(HypothesisStore, "mark_status", original_mark_status)
        shutil.rmtree(tmp_path / "champion_code")
        reopened = _campaign(
            tmp_path,
            llm_client=next_client,
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="fail",
                    )
                ]
            ),
        )
        restored = reopened._branch_ctrl.get_branch(bid)
        assert (
            reopened._materializer.compute_code_hash(reopened._branch_workspaces[bid])
            == persisted_clean_hash
        )
        assert restored.current_code_hash == persisted_clean_hash
        assert restored.last_clean_code_hash == persisted_clean_hash
        assert restored.branch_evidence_summary["verified_candidate_commit"] == h1_marker
        h2_record = reopened._hyp_store.get_one(h2_id)
        assert h2_record is not None
        assert h2_record.status == "blocked_infra"
        assert bid not in reopened._branch_current_hypothesis

        next_result = reopened.run_one_step()

        assert next_client.calls == 2
        assert next_result.decision == Decision.CONTINUE_EXPLORE
        assert reopened._step_history[-1].hypothesis.hypothesis_text == (
            "Third hypothesis after rollback."
        )
        assert reopened._step_history[-1].hypothesis_id != h2_id

    def test_failed_promoted_journal_write_reopen_terminalizes_h2(
        self,
        tmp_path,
        monkeypatch,
    ):
        second_patch = {
            "file_path": "operators/local_search.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": source_digest_for_content(_VALID_CODE_AFTER_PATCH),
            "old_string": "        return candidate\n",
            "new_string": (
                "        second_candidate = candidate\n"
                "        return second_candidate\n"
            ),
            "replace_all": False,
            "test_hint": None,
        }

        class SequentialClient:
            def __init__(self):
                self.code_calls = 0

            def call(self, prompt, schema, model=None, system_blocks=None):
                del prompt, model, system_blocks
                if _schema_requests_patch(schema):
                    self.code_calls += 1
                    return dict(_VALID_PATCH if self.code_calls == 1 else second_patch)
                return dict(_VALID_HYPOTHESIS)

            def call_with_tool(
                self,
                prompt,
                tool,
                model=None,
                system_blocks=None,
                request_kind=None,
            ):
                del request_kind
                return self.call(
                    prompt,
                    tool.get("input_schema", {}),
                    model,
                    system_blocks,
                )

        cm = _campaign(
            tmp_path,
            llm_client=SequentialClient(),
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="fail",
                    )
                ]
            ),
        )
        first = cm.run_one_step()
        bid = first.branch_id
        h1_hash = cm._branch_store.load(bid).last_clean_code_hash
        original_write = workspace_module._atomic_json_write
        writes = 0

        def fail_promoted_write(path, payload):
            nonlocal writes
            writes += 1
            if writes == 2:
                raise OSError("promoted journal write unavailable")
            return original_write(path, payload)

        monkeypatch.setattr(
            workspace_module,
            "_atomic_json_write",
            fail_promoted_write,
        )
        with pytest.raises(OSError, match="promoted journal write unavailable"):
            cm.run_one_step()

        active_records = [
            record
            for record in cm._hyp_store.get_by_branch(bid)
            if record.status == "active"
        ]
        assert len(active_records) == 1
        h2_id = active_records[0].hypothesis_id
        journal = tmp_path / "campaign" / "promotion_journals" / f"{bid}.json"
        assert json.loads(journal.read_text())["status"] == "rolled_back"

        monkeypatch.setattr(workspace_module, "_atomic_json_write", original_write)
        shutil.rmtree(tmp_path / "champion_code")
        reopened = _campaign(tmp_path)

        restored = reopened._branch_ctrl.get_branch(bid)
        assert restored.current_code_hash == h1_hash
        assert restored.last_clean_code_hash == h1_hash
        assert reopened._hyp_store.get_one(h2_id).status == "blocked_infra"
        assert not journal.exists()

    @pytest.mark.parametrize("crash_phase", ["prepared", "committed"])
    def test_promotion_journal_reopen_finalizes_candidate_commit(
        self,
        tmp_path,
        monkeypatch,
        crash_phase,
    ):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                results=[
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="pass",
                    )
                ]
            ),
        )
        if crash_phase == "prepared":
            def crash_before_commit(_branch):
                raise OSError("crash with prepared marker")

            monkeypatch.setattr(
                cm._explore_step_pipeline,
                "commit_verified_candidate_promotion",
                crash_before_commit,
            )
            expected_error = "prepared marker"
        else:
            def crash_before_backup_release(_branch_id):
                raise OSError("crash with committed marker")

            monkeypatch.setattr(
                cm._materializer,
                "finalize_candidate_promotion",
                crash_before_backup_release,
            )
            expected_error = "committed marker"

        with pytest.raises(OSError, match=expected_error):
            cm.run_one_step()

        branch = next(iter(cm._branch_ctrl._branches.values()))
        persisted = cm._branch_store.load(branch.branch_id)
        assert persisted is not None
        assert persisted.branch_evidence_summary["verified_candidate_commit"][
            "promotion_status"
        ] == crash_phase
        journal = (
            tmp_path
            / "campaign"
            / "promotion_journals"
            / f"{branch.branch_id}.json"
        )
        assert journal.is_file()

        shutil.rmtree(tmp_path / "champion_code")
        reopened = _campaign(tmp_path)

        restored = reopened._branch_ctrl.get_branch(branch.branch_id)
        marker = restored.branch_evidence_summary["verified_candidate_commit"]
        assert marker["promotion_status"] == "committed"
        assert marker["evaluation_status"] == "pending"
        assert not journal.exists()

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
            marker = branch.branch_evidence_summary["verified_candidate_commit"]
            assert marker["evaluation_status"] == "completed"
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
        assert persisted.branch_evidence_summary["verified_candidate_commit"][
            "evaluation_status"
        ] == "completed"
        assert protocol.experiment_call_count == 1

        shutil.rmtree(tmp_path / "champion_code")
        reopened = _campaign(tmp_path, experiment_protocol=MockExperimentProtocol([]))
        restored = reopened._branch_ctrl.get_branch(branch.branch_id)
        assert restored.branch_evidence_summary["verified_candidate_commit"][
            "evaluation_status"
        ] == "completed"

    @pytest.mark.parametrize("active_mode", ["missing", "mismatch"])
    def test_pending_evaluation_requires_exact_active_hypothesis_owner(
        self,
        tmp_path,
        monkeypatch,
        active_mode,
    ):
        cm = _campaign(tmp_path, experiment_protocol=MockExperimentProtocol([]))

        def crash_before_formal(*_args, **_kwargs):
            raise OSError("crash before formal evaluation")

        monkeypatch.setattr(cm._explore_step_pipeline, "evaluate", crash_before_formal)
        with pytest.raises(OSError, match="crash before formal evaluation"):
            cm.run_one_step()

        branch = next(iter(cm._branch_ctrl._branches.values()))
        marker = branch.branch_evidence_summary["verified_candidate_commit"]
        cm._hyp_store.mark_status(marker["hypothesis_id"], "rejected")
        if active_mode == "mismatch":
            cm._hyp_store.save(
                HypothesisRecord(
                    hypothesis_id="different-active-hypothesis",
                    branch_id=branch.branch_id,
                    change_locus="local_search",
                    action="modify",
                    status="active",
                    target_file="operators/local_search.py",
                    hypothesis_text="Different owner.",
                )
            )

        shutil.rmtree(tmp_path / "champion_code")
        expected_conflict = (
            "pending evaluation ownership conflict"
            if active_mode == "missing"
            else "active hypothesis ownership conflict"
        )
        with pytest.raises(RuntimeError, match=expected_conflict):
            _campaign(tmp_path)

    def test_completed_commit_rejects_different_active_hypothesis_owner(
        self,
        tmp_path,
    ):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="fail",
                    )
                ]
            ),
        )
        result = cm.run_one_step()
        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert branch.branch_evidence_summary["verified_candidate_commit"][
            "evaluation_status"
        ] == "completed"
        cm._hyp_store.save(
            HypothesisRecord(
                hypothesis_id="orphan-active-h2",
                branch_id=branch.branch_id,
                change_locus="local_search",
                action="modify",
                status="active",
                target_file="operators/local_search.py",
                hypothesis_text="Orphan active H2.",
            )
        )

        shutil.rmtree(tmp_path / "champion_code")
        with pytest.raises(RuntimeError, match="active hypothesis ownership conflict"):
            _campaign(tmp_path)

    def test_pending_reconcile_rejects_same_id_mutated_hypothesis_metadata(
        self,
        tmp_path,
        monkeypatch,
    ):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        first = cm.run_one_step()
        persisted = _leave_pending_reconcile(
            cm,
            tmp_path,
            first.branch_id,
            monkeypatch,
        )
        marker = persisted.branch_evidence_summary["verified_candidate_commit"]
        record = cm._hyp_store.get_one(marker["hypothesis_id"])
        record.hypothesis_text = "Mutated content under the same hypothesis ID."
        record.predicted_direction = "tradeoff"
        record.suggested_weight = 0.91
        cm._hyp_store.save(record)

        shutil.rmtree(tmp_path / "champion_code")
        with pytest.raises(RuntimeError, match="active hypothesis metadata conflict"):
            _campaign(tmp_path)

    @pytest.mark.parametrize(
        ("field", "value", "expected"),
        [
            ("lineage_id", "foreign-lineage", "commit lineage ownership"),
            ("base_code_hash", "foreign-base", "reconcile base mismatch"),
        ],
    )
    def test_reconcile_artifact_rejects_base_or_lineage_tamper(
        self,
        tmp_path,
        monkeypatch,
        field,
        value,
        expected,
    ):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        first = cm.run_one_step()
        persisted = _leave_pending_reconcile(
            cm,
            tmp_path,
            first.branch_id,
            monkeypatch,
        )
        marker = dict(
            persisted.branch_evidence_summary["verified_candidate_commit"]
        )
        artifact = tmp_path / "campaign" / marker["artifact_ref"]
        payload = json.loads(artifact.read_text())
        payload[field] = value
        artifact_bytes = (
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
        ).encode()
        artifact.write_bytes(artifact_bytes)
        marker["artifact_sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
        summary = dict(persisted.branch_evidence_summary)
        summary["verified_candidate_commit"] = marker
        persisted.branch_evidence_summary = summary
        cm._branch_store.save(persisted)

        shutil.rmtree(tmp_path / "champion_code")
        with pytest.raises(RuntimeError, match=expected):
            _campaign(tmp_path)

    def test_verified_candidate_artifact_write_is_immutable(self, tmp_path):
        artifact = tmp_path / "immutable-artifact.json"
        verified_commit_module._atomic_write(artifact, b"first\n")
        verified_commit_module._atomic_write(artifact, b"first\n")

        with pytest.raises(RuntimeError, match="artifact is immutable"):
            verified_commit_module._atomic_write(artifact, b"second\n")

        assert artifact.read_bytes() == b"first\n"

    @pytest.mark.parametrize("tamper", ["hypothesis_id", "promotion_kind"])
    def test_committed_promotion_journal_rejects_typed_owner_tamper(
        self,
        tmp_path,
        monkeypatch,
        tamper,
    ):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )

        def crash_with_prepared_marker(_branch):
            raise OSError("leave candidate promotion journal")

        monkeypatch.setattr(
            cm._explore_step_pipeline,
            "commit_verified_candidate_promotion",
            crash_with_prepared_marker,
        )
        with pytest.raises(OSError, match="leave candidate promotion journal"):
            cm.run_one_step()
        branch = next(iter(cm._branch_ctrl._branches.values()))
        journal = (
            tmp_path
            / "campaign"
            / "promotion_journals"
            / f"{branch.branch_id}.json"
        )
        payload = json.loads(journal.read_text())
        if tamper == "hypothesis_id":
            payload["hypothesis_id"] = "foreign-hypothesis"
        else:
            payload["promotion_kind"] = "reconcile"
            payload["terminalize_hypothesis_on_rollback"] = False
        journal.write_text(json.dumps(payload))

        shutil.rmtree(tmp_path / "champion_code")
        with pytest.raises(RuntimeError, match="committed promotion ownership conflict"):
            _campaign(tmp_path)

    def test_stale_malformed_typed_marker_cannot_fallback_to_valid_legacy_artifact(
        self,
        tmp_path,
    ):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="fail",
                    )
                ]
            ),
        )
        result = cm.run_one_step()
        branch = cm._branch_ctrl.get_branch(result.branch_id)
        legacy_ref = branch.branch_evidence_summary[
            "formal_candidate_patch_artifact_ref"
        ]
        assert (tmp_path / "campaign" / legacy_ref).is_file()
        cm._branch_ctrl.mark_all_stale(new_champion_id=2)
        branch.branch_evidence_summary["verified_candidate_commit"] = "malformed"
        cm._persist_branch_state(branch.branch_id)

        shutil.rmtree(tmp_path / "champion_code")
        with pytest.raises(RuntimeError, match="commit ref is invalid"):
            _campaign(tmp_path)


class TestRunLoop:
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
