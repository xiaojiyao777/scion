"""Focused tests split from test_campaign.py."""

from scion.core.branch import StateTransitionError
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.scheduler import Scheduler

from .campaign_test_support import *


def _assert_single_typed_terminal(
    cm,
    result,
    *,
    reason_code: str,
    event_kind: str,
    event_stage: str,
    failure_stage: str,
):
    assert result.branch_id is not None
    record = result.execution_outcome
    assert record is not None
    assert record.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert record.reason_code == reason_code
    assert record.provenance["stage"] == event_stage
    assert result.failure_stage == failure_stage
    assert result.failure_category == ExecutionOutcome.BLOCKED_INFRA.value
    assert result.decision is None
    assert result.protocol_result is None

    branch = cm._branch_ctrl.get_branch(result.branch_id)
    assert branch.state is BranchState.BLOCKED_INFRA

    step = cm._step_history[-1]
    assert step.execution_outcome is record
    assert step.decision is None
    assert step.protocol_result is None
    assert step.failure_stage == failure_stage

    outcomes = [
        item
        for item in cm._registry.query_execution_outcomes(branch_id=result.branch_id)
        if item["event_kind"] == event_kind
    ]
    assert len(outcomes) == 1
    assert outcomes[0]["event_kind"] == event_kind
    assert outcomes[0]["stage"] == event_stage
    assert outcomes[0]["outcome"] == ExecutionOutcome.BLOCKED_INFRA.value
    assert outcomes[0]["reason_code"] == reason_code
    return record


class TestFullSuccessPath:
    def test_validation_and_frozen_reuse_do_not_regenerate_h_or_c(self, tmp_path):
        """One verified candidate owns H/C across exact stage reuse."""
        llm = MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        )
        cm = _campaign(
            tmp_path,
            llm_client=llm,
            experiment_protocol=_promote_protocol(),
        )

        screening = cm.run_one_step()
        assert screening.decision is Decision.QUEUE_VALIDATE
        assert llm.call_count == 2

        validation = cm.run_one_step()
        assert validation.decision is Decision.QUEUE_FROZEN
        assert llm.call_count == 2

        frozen = cm.run_one_step()
        assert frozen.decision is Decision.PROMOTE
        assert llm.call_count == 2

    def test_screening_pass_queues_validate(self, tmp_path):
        """Screening pass → decision=QUEUE_VALIDATE, branch in READY_VALIDATE."""
        protocol = MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass")]
        )
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        result = cm.run_one_step()
        assert result.decision == Decision.QUEUE_VALIDATE
        bid = result.branch_id
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state == BranchState.READY_VALIDATE

    def test_validation_step_after_screening(self, tmp_path):
        """Second step (READY_VALIDATE → VALIDATING) produces QUEUE_FROZEN decision."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        # Step 1: EXPLORE → QUEUE_VALIDATE
        cm.run_one_step()
        # Step 2: READY_VALIDATE → VALIDATING → eval → QUEUE_FROZEN
        result = cm.run_one_step()
        assert result.decision == Decision.QUEUE_FROZEN

    def test_frozen_step_promotes(self, tmp_path):
        """Third step (FROZEN_TESTING) with ci_low >= 0 → PROMOTE."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
            _make_protocol_result(ExperimentStage.FROZEN, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        cm.run_one_step()  # EXPLORE → QUEUE_VALIDATE
        cm.run_one_step()  # VALIDATING → QUEUE_FROZEN
        result = cm.run_one_step()  # FROZEN_TESTING → PROMOTE
        assert result.decision == Decision.PROMOTE

    def test_promote_updates_champion_version(self, tmp_path):
        """After PROMOTE, champion version increments."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
            _make_protocol_result(ExperimentStage.FROZEN, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        assert cm._champion.version == 1
        cm.run_one_step()
        cm.run_one_step()
        cm.run_one_step()
        assert cm._champion.version == 2

    def test_promote_writes_one_ordinary_experiment_event(self, tmp_path):
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
            _make_protocol_result(ExperimentStage.FROZEN, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        cm.run_one_step()
        cm.run_one_step()
        cm.run_one_step()

        assert cm._champion.version == 2
        with sqlite3.connect(Path(cm._campaign_dir) / "scion.db") as conn:
            events = conn.execute(
                "SELECT event_kind, decision FROM experiment_events "
                "WHERE event_kind = 'experiment' AND decision = 'promote'",
            ).fetchall()
        assert events == [("experiment", "promote")]

    def test_promote_marks_other_branches_stale(self, tmp_path):
        """After PROMOTE, all sibling branches should be STALE."""
        protocol = MockExperimentProtocol(results=[
            # Branch 1: screening pass
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
            _make_protocol_result(ExperimentStage.FROZEN, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        # Step 1: creates branch A (EXPLORE → QUEUE_VALIDATE)
        cm.run_one_step()

        # Manually create a second branch for testing
        branch_b = cm._branch_ctrl.create_branch(cm._champion)

        # Steps 2-3: branch A → PROMOTE
        cm.run_one_step()
        cm.run_one_step()

        # Branch B should now be STALE
        branch_b_state = cm._branch_ctrl.get_branch(branch_b.branch_id)
        assert branch_b_state.state == BranchState.STALE

    def test_promote_precondition_failure_is_one_typed_terminal(
        self,
        tmp_path,
        monkeypatch,
    ):
        cm = _campaign(tmp_path, experiment_protocol=_promote_protocol())
        screening = cm.run_one_step()
        bid = screening.branch_id
        assert bid is not None
        cm.run_one_step()

        def fail_precondition(_branch):
            raise StateTransitionError("forced promotion precondition failure")

        monkeypatch.setattr(
            cm._decision_finalizer,
            "require_promotable_branch",
            fail_precondition,
        )
        result = cm.run_one_step()

        assert result.reason.startswith("promotion_precondition_failed")
        _assert_single_typed_terminal(
            cm,
            result,
            reason_code="PROMOTION_PRECONDITION_FAILED",
            event_kind="promotion_execution_outcome",
            event_stage="promotion_precondition",
            failure_stage="promotion_precondition",
        )
        assert cm._champion.version == 1
        assert bid is not None
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state is BranchState.BLOCKED_INFRA
        assert branch.hypothesis is not None

    def test_promote_snapshot_failure_does_not_commit_state(self, tmp_path, monkeypatch):
        """PROMOTE snapshot/freeze failure must not mark branch/hypothesis/champion promoted."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
            _make_protocol_result(ExperimentStage.FROZEN, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        r1 = cm.run_one_step()
        bid = r1.branch_id
        cm.run_one_step()

        def fail_freeze(path):
            raise OSError("freeze failed")

        monkeypatch.setattr(cm._materializer, "freeze_snapshot", fail_freeze)
        result = cm.run_one_step()

        assert result.reason.startswith("promotion_failed")
        _assert_single_typed_terminal(
            cm,
            result,
            reason_code="PROMOTION_FAILED",
            event_kind="promotion_execution_outcome",
            event_stage="promotion",
            failure_stage="promotion",
        )
        assert cm._champion.version == 1
        assert bid is not None
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state is BranchState.BLOCKED_INFRA
        assert branch.hypothesis is not None


class TestContractFailure:
    def test_patch_contract_fail_clears_workspace(self, tmp_path):
        """When patch contract fails, workspace is not retained."""
        bad_patch = {
            "file_path": "solver.py",  # frozen file — C5 will fail
            "action": "create",
            "edit_intent": "full_file",
            "content_after": _VALID_CODE,
            "test_hint": None,
        }
        llm = MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=bad_patch,
        )
        cm = _campaign(tmp_path, llm_client=llm)
        result = cm.run_one_step()
        assert result.branch_id is not None
        assert result.decision is None  # no decision was made
        assert result.branch_id not in cm._branch_workspaces

    def test_contract_fail_branch_stays_explore(self, tmp_path):
        """After contract failure, branch remains in EXPLORE for retry."""
        bad_patch = {
            "file_path": "solver.py",  # frozen file
            "action": "create",
            "edit_intent": "full_file",
            "content_after": _VALID_CODE,
            "test_hint": None,
        }
        llm = MockLLMClient(hypothesis_response=_VALID_HYPOTHESIS, patch_response=bad_patch)
        cm = _campaign(tmp_path, llm_client=llm)
        result = cm.run_one_step()
        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert branch.state == BranchState.EXPLORE  # can still be retried

    def test_workspace_creation_failure_is_one_typed_terminal(self, tmp_path):
        """Workspace setup failure stops the branch with one typed outcome."""
        cm = _campaign(tmp_path)

        def fail_create_workspace(branch_id, source_snapshot):
            raise OSError("disk unavailable")

        cm._materializer.create_branch_workspace = fail_create_workspace

        result = cm.run_one_step()

        assert result.reason == "workspace setup failed"
        _assert_single_typed_terminal(
            cm,
            result,
            reason_code="WORKSPACE_SETUP_FAILED",
            event_kind="workspace_execution_outcome",
            event_stage="workspace_setup",
            failure_stage="workspace",
        )
        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert branch.hypothesis is None
        row = next(
            row
            for row in cm._registry.query_by_branch(result.branch_id)
            if row["event_kind"] == "workspace_execution_outcome"
        )
        assert row["selected_hypothesis_research_basis_json"] is None

    def test_patch_materialization_failure_is_one_typed_terminal(self, tmp_path):
        """Post-Contract filesystem failure is not a research rejection."""
        cm = _campaign(tmp_path)

        def fail_apply_patch(*args, **kwargs):
            raise OSError("disk write unavailable")

        cm._explore_step_pipeline.apply_patch = fail_apply_patch

        result = cm.run_one_step()

        assert result.reason == "apply_patch failed"
        _assert_single_typed_terminal(
            cm,
            result,
            reason_code="PATCH_MATERIALIZATION_FAILED",
            event_kind="workspace_execution_outcome",
            event_stage="patch_materialization",
            failure_stage="workspace",
        )
        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert branch.hypothesis is None

    def test_hypothesis_locus_outside_call_enum_is_provider_invalid(self, tmp_path):
        """An enum-external locus is rejected before publishing a hypothesis."""
        bad_hypothesis = {
            "hypothesis_text": "test",
            "change_locus": "unknown_category",
            "action": "modify",
            "target_file": "operators/local_search.py",
            "predicted_direction": "improve",
            "target_weakness": "slow convergence",
            "expected_effect": "better solutions",
        }
        llm = MockLLMClient(hypothesis_response=bad_hypothesis, patch_response=_VALID_PATCH)
        cm = _campaign(tmp_path, llm_client=llm)
        result = cm.run_one_step()
        assert result.branch_id is not None
        assert result.decision is None
        assert cm._branch_ctrl.get_branch(result.branch_id).hypothesis is None
        assert result.execution_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED

    def test_contract_fail_next_tick_starts_fresh_candidate_same_branch(self, tmp_path):
        """An explicit next tick starts a fresh candidate on the same branch.

        Step 2 uses a distinct target so the fresh candidate is observable.
        """
        bad_patch = {
            "file_path": "solver.py",  # frozen file
            "action": "create",
            "edit_intent": "full_file",
            "content_after": _VALID_CODE,
            "test_hint": None,
        }
        hyp1 = dict(_VALID_HYPOTHESIS)  # target_file=operators/local_search.py
        hyp2 = dict(_VALID_HYPOTHESIS)
        hyp2["action"] = "create_new"
        hyp2["target_file"] = "operators/other_op.py"
        good_patch2 = {
            "file_path": "operators/other_op.py",
            "action": "create",
            "edit_intent": "full_file",
            "content_after": _VALID_CODE,
            "test_hint": None,
        }

        call_count = [0]

        class SequencedLLM:
            def __init__(self):
                self.hyp_calls = 0
            def call(self, prompt, schema, model=None, system_blocks=None):
                call_count[0] += 1
                if _schema_requests_patch(schema):
                    # patch call — step 1 returns bad (→ contract fail), step 2 returns good
                    if call_count[0] <= 2:
                        return dict(bad_patch)
                    return dict(good_patch2)
                # hypothesis call — vary target_file so step 2 passes novelty
                self.hyp_calls += 1
                return hyp1 if self.hyp_calls == 1 else hyp2
            def call_with_tool(
                self, prompt, tool, model=None, system_blocks=None, request_kind=None
            ):
                del request_kind
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        cm, _bounded_client = _bounded_campaign(
            tmp_path,
            llm_client=SequencedLLM(),
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        cm._scheduler = Scheduler(max_active_branches=1)
        cm._branch_step_runner.scheduler = cm._scheduler
        # Step 1: contract fails
        r1 = cm.run_one_step()
        assert r1.decision is None
        # Step 2: succeeds
        r2 = cm.run_one_step()
        assert r2.branch_id == r1.branch_id
        assert r2.decision is not None
