from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from scion.cli.app import app
from scion.cli.commands.init_run import (
    _campaign_start_message,
    _completion_from_run_result,
)
from scion.core.branch import StateTransitionError
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import BranchState, CanaryResult, Decision, ExperimentStage
from scion.core.proposal_pipeline import ProposalAttempt
from scion.core.qualification import (
    QUALIFICATION_BOUNDARY_REACHED,
    QUALIFICATION_NOT_REACHED,
    QUALIFICATION_READY_DISPOSITION,
    QualificationOnlyConfig,
    QualificationProposalBudgetExhausted,
    normalize_qualification_only_config,
)
from scion.core.scheduler import SchedulerAction
from scion.core.step_result import StepResult

from ...campaign_test_support import (
    MockExperimentProtocol,
    _campaign,
    _make_protocol_result,
)


def _config(**overrides: int) -> QualificationOnlyConfig:
    values = {
        "max_proposal_attempts": 4,
        "max_verified_candidate_chains": 2,
        "max_formal_screening_stages": 4,
    }
    values.update(overrides)
    return QualificationOnlyConfig(**values)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("max_proposal_attempts", 0),
        ("max_verified_candidate_chains", -1),
        ("max_formal_screening_stages", True),
        ("max_proposal_attempts", 1.5),
    ),
)
def test_qualification_limits_fail_closed_independently(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValueError, match=field):
        _config(**{field: value})  # type: ignore[arg-type]


def test_qualification_mapping_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="unknown fields"):
        normalize_qualification_only_config({"max_proposal_attempts": 4, "x": 1})


@pytest.mark.parametrize(
    ("option", "value"),
    (
        ("--max-proposal-attempts", "4"),
        ("--max-verified-candidate-chains", "2"),
        ("--max-formal-screening-stages", "4"),
    ),
)
def test_cli_qualification_limit_without_mode_fails_before_loading_problem(
    tmp_path,
    option: str,
    value: str,
) -> None:
    result = CliRunner().invoke(
        app,
        ["run", option, value, "--problem", str(tmp_path / "missing.yaml")],
    )

    assert result.exit_code == 1
    assert "qualification limit options require --qualification-only" in result.output
    assert "problem.yaml not found" not in result.output


def test_cli_start_line_is_byte_compatible_for_ordinary_and_auditable_for_mode(
) -> None:
    ordinary = _campaign_start_message(
        problem_name="demo",
        requested_rounds=3,
        mock_llm=True,
        qualification_config=None,
    )
    qualification = _campaign_start_message(
        problem_name="demo",
        requested_rounds=3,
        mock_llm=True,
        qualification_config=_config(),
    )

    assert ordinary == (
        "Starting campaign: demo (requested_rounds=3, mock_llm=True)"
    )
    assert qualification == (
        "Starting campaign: demo (requested_rounds=3, mock_llm=True, "
        "mode=qualification_only, max_proposal_attempts=4, "
        "max_verified_candidate_chains=2, max_formal_screening_stages=4)"
    )


def test_queue_validate_stops_at_boundary_without_heldout_dispatch(tmp_path) -> None:
    protocol = MockExperimentProtocol(
        results=[_make_protocol_result(ExperimentStage.SCREENING, "pass")]
    )
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_config(),
    )

    terminal = cm.run(requested_rounds=99)

    assert terminal.stop_reason == QUALIFICATION_BOUNDARY_REACHED
    assert terminal.completed is True
    projection = terminal.to_projection()
    assert projection["status"] == "completed"
    assert projection["run_validity"] == {
        "status": "valid",
        "reason": "valid",
        "valid": True,
    }
    assert projection["qualification"] == {
        "mode": "qualification_only",
        "limits": {
            "max_proposal_attempts": 4,
            "max_verified_candidate_chains": 2,
            "max_formal_screening_stages": 4,
        },
        "proposal_attempts": 1,
        "verified_candidate_chains": 1,
        "formal_screening_stages": 1,
        "initial_screening_stages": 1,
        "expanded_screening_stages": 0,
        "disposition": QUALIFICATION_READY_DISPOSITION,
    }
    assert _completion_from_run_result(terminal) == (
        0,
        QUALIFICATION_BOUNDARY_REACHED,
    )
    branch = cm._branch_ctrl.get_branch(cm._step_history[-1].branch_id)
    assert branch.state is BranchState.READY_VALIDATE
    assert branch.current_code_hash
    assert branch.branch_id in cm._branch_workspaces
    assert protocol.experiment_call_count == 1
    carrier_workspace = cm._branch_workspaces[branch.branch_id]
    carrier_hash = branch.current_code_hash
    carrier_hypothesis = branch.hypothesis
    carrier_patch = cm._branch_patches[branch.branch_id]

    with pytest.raises(StateTransitionError, match="cannot park branch"):
        cm._park_qualification_chain(branch.branch_id)
    assert branch.state is BranchState.READY_VALIDATE
    assert cm._branch_workspaces[branch.branch_id] == carrier_workspace
    assert cm._branch_patches[branch.branch_id] is carrier_patch
    assert branch.current_code_hash == carrier_hash
    assert branch.hypothesis is carrier_hypothesis

    blocked = cm._branch_step_runner.run_one_step()
    assert blocked.execution_outcome is not None
    assert blocked.execution_outcome.reason_code == (
        "QUALIFICATION_HELDOUT_DISPATCH_BLOCKED"
    )
    assert protocol.experiment_call_count == 1
    with pytest.raises(RuntimeError, match="blocks validation/frozen"):
        cm._evaluate(
            branch,
            cm._branch_workspaces[branch.branch_id],
            branch.hypothesis,
        )
    assert protocol.experiment_call_count == 1

    status = json.loads(
        (tmp_path / "campaign" / "status.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (tmp_path / "campaign" / "campaign_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["run_result"] == projection
    assert summary["run_result"] == projection
    assert status["campaign_mode"] == "qualification_only"


def test_pending_expansion_ignores_attempt_and_chain_caps(tmp_path) -> None:
    protocol = MockExperimentProtocol(
        results=[
            _make_protocol_result(ExperimentStage.SCREENING, "expand"),
            _make_protocol_result(ExperimentStage.SCREENING, "pass"),
        ]
    )
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_config(
            max_proposal_attempts=1,
            max_verified_candidate_chains=1,
            max_formal_screening_stages=2,
        ),
    )

    terminal = cm.run(requested_rounds=1)

    assert terminal.stop_reason == QUALIFICATION_BOUNDARY_REACHED
    qualification = terminal.to_projection()["qualification"]
    assert qualification["proposal_attempts"] == 1
    assert qualification["verified_candidate_chains"] == 1
    assert qualification["formal_screening_stages"] == 2
    assert qualification["initial_screening_stages"] == 1
    assert qualification["expanded_screening_stages"] == 1
    assert terminal.protocol_stage_counts == {
        "screening": 2,
        "validation": 0,
        "frozen": 0,
    }
    assert len({step.branch_id for step in cm._step_history}) == 1
    assert protocol.experiment_call_count == 2


class _SequencedCanaryProtocol(MockExperimentProtocol):
    def __init__(
        self,
        *,
        results,
        canary_passes: list[bool],
    ) -> None:
        super().__init__(results=results)
        self._canary_passes = list(canary_passes)

    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        del candidate_ws, champion_ws
        self.canary_call_count += 1
        return CanaryResult(passed=self._canary_passes.pop(0))


def test_expanded_canary_negative_retires_pending_then_uses_fresh_sibling(
    tmp_path,
) -> None:
    protocol = _SequencedCanaryProtocol(
        results=[
            _make_protocol_result(ExperimentStage.SCREENING, "expand"),
            _make_protocol_result(ExperimentStage.SCREENING, "pass"),
        ],
        canary_passes=[True, False, True],
    )
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_config(),
    )

    terminal = cm.run(requested_rounds=99)

    assert terminal.stop_reason == QUALIFICATION_BOUNDARY_REACHED
    qualification = terminal.to_projection()["qualification"]
    assert qualification["proposal_attempts"] == 2
    assert qualification["verified_candidate_chains"] == 2
    assert qualification["formal_screening_stages"] == 2
    assert qualification["initial_screening_stages"] == 2
    assert qualification["expanded_screening_stages"] == 0
    assert terminal.protocol_stage_counts == {
        "screening": 2,
        "validation": 0,
        "frozen": 0,
    }
    assert protocol.canary_call_count == 3
    assert protocol.experiment_call_count == 2
    assert terminal.scheduled_calls == 3

    first, expanded_canary, second = cm._step_history
    assert first.branch_id == expanded_canary.branch_id
    assert second.branch_id != first.branch_id
    assert expanded_canary.failure_stage == "canary"
    assert expanded_canary.execution_outcome is not None
    assert expanded_canary.execution_outcome.provenance == {"stage": "screening"}
    assert cm._branch_ctrl.get_branch(first.branch_id).state is (
        BranchState.PARKED_LINEAGE
    )
    assert cm._branch_ctrl.get_branch(first.branch_id).current_code_hash is None
    assert first.branch_id not in cm._branch_workspaces
    assert first.branch_id not in cm._branch_patches
    assert cm._qualification_runtime.pending_expansion_branch_id is None
    assert second.candidate_parent_scope == "declared_champion"


def test_stage_cap_parks_pending_expansion_without_dispatching_it(tmp_path) -> None:
    protocol = MockExperimentProtocol(
        results=[
            _make_protocol_result(ExperimentStage.SCREENING, "expand"),
            _make_protocol_result(ExperimentStage.SCREENING, "pass"),
        ]
    )
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_config(max_formal_screening_stages=1),
    )

    terminal = cm.run(requested_rounds=99)

    assert terminal.stop_reason == QUALIFICATION_NOT_REACHED
    assert terminal.completed is True
    assert protocol.experiment_call_count == 1
    qualification = terminal.to_projection()["qualification"]
    assert qualification["proposal_attempts"] == 1
    assert qualification["verified_candidate_chains"] == 1
    assert qualification["formal_screening_stages"] == 1
    assert qualification["disposition"] == QUALIFICATION_NOT_REACHED
    branch = cm._branch_ctrl.get_branch(cm._step_history[-1].branch_id)
    assert branch.state is BranchState.PARKED_LINEAGE
    assert branch.current_code_hash is None
    assert cm._branch_workspaces == {}
    assert cm._branch_patches == {}


def test_pending_expansion_blocks_wrong_branch_and_wrong_state_before_dispatch(
    tmp_path,
) -> None:
    protocol = MockExperimentProtocol(results=[])
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_config(),
    )
    pending = cm._branch_ctrl.create_branch(cm._champion)
    pending.state = BranchState.EXPLORE_EXPAND
    other = cm._branch_ctrl.create_branch(cm._champion)
    other.state = BranchState.EXPLORE_EXPAND
    runtime = cm._qualification_runtime
    runtime.record_verified_candidate(pending.branch_id)
    runtime.record_screening_stage(pending.branch_id, expanded=False)
    runtime.request_expansion(pending.branch_id)

    cm._branch_step_runner._select_next = lambda _active: SchedulerAction(
        action="run_existing",
        branch=other,
    )
    wrong_branch = cm._branch_step_runner.run_one_step()

    pending.state = BranchState.STALE
    cm._branch_step_runner._select_next = lambda _active: SchedulerAction(
        action="run_existing",
        branch=pending,
    )
    wrong_state = cm._branch_step_runner.run_one_step()

    for result in (wrong_branch, wrong_state):
        assert result.execution_outcome is not None
        assert result.execution_outcome.reason_code == (
            "QUALIFICATION_PENDING_EXPANSION_MISMATCH"
        )
    assert runtime.pending_expansion_branch_id == pending.branch_id
    assert runtime.proposal_attempts == 0
    assert protocol.canary_call_count == 0
    assert protocol.experiment_call_count == 0


def test_scheduler_create_new_while_expansion_pending_is_incomplete_invariant(
    tmp_path,
) -> None:
    cm = _campaign(tmp_path, qualification_only=_config())
    pending = cm._branch_ctrl.create_branch(cm._champion)
    pending.state = BranchState.EXPLORE_EXPAND
    runtime = cm._qualification_runtime
    runtime.record_verified_candidate(pending.branch_id)
    runtime.record_screening_stage(pending.branch_id, expanded=False)
    runtime.request_expansion(pending.branch_id)
    branch_count = len(cm._branch_ctrl._branches)
    cm._branch_step_runner._select_next = lambda _active: SchedulerAction(
        action="create_new",
    )

    terminal = cm.run(requested_rounds=99)

    assert terminal.stop_reason == "execution_not_evaluated"
    assert terminal.completed is False
    assert terminal.last_execution_outcome == {
        "outcome": "not_evaluated",
        "reason_code": "QUALIFICATION_PENDING_EXPANSION_MISMATCH",
        "stage": "scheduler",
    }
    assert len(cm._branch_ctrl._branches) == branch_count
    assert pending.state is BranchState.EXPLORE_EXPAND
    assert runtime.pending_expansion_branch_id == pending.branch_id
    assert _completion_from_run_result(terminal)[0] == 22


def test_two_failed_chains_are_clean_siblings_from_declared_champion(tmp_path) -> None:
    protocol = MockExperimentProtocol(
        results=[
            _make_protocol_result(ExperimentStage.SCREENING, "fail"),
            _make_protocol_result(ExperimentStage.SCREENING, "fail"),
        ]
    )
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_config(),
    )

    terminal = cm.run(requested_rounds=99)

    assert terminal.stop_reason == QUALIFICATION_NOT_REACHED
    assert terminal.completed is True
    qualification = terminal.to_projection()["qualification"]
    assert qualification["proposal_attempts"] == 2
    assert qualification["verified_candidate_chains"] == 2
    assert qualification["formal_screening_stages"] == 2
    assert [step.candidate_parent_scope for step in cm._step_history] == [
        "declared_champion",
        "declared_champion",
    ]
    branch_ids = [step.branch_id for step in cm._step_history]
    assert len(set(branch_ids)) == 2
    branches = [cm._branch_ctrl.get_branch(branch_id) for branch_id in branch_ids]
    assert all(branch.state is BranchState.PARKED_LINEAGE for branch in branches)
    assert all(branch.current_code_hash is None for branch in branches)
    assert cm._branch_workspaces == {}
    assert cm._branch_patches == {}
    assert cm.get_state(run_result=terminal)["n_active_branches"] == 0
    experiment_events = [
        event
        for branch_id in branch_ids
        for event in cm._registry.query_by_branch(branch_id)
        if event["event_kind"] == "experiment"
    ]
    assert len(experiment_events) == 2
    assert len({event["code_hash"] for event in experiment_events}) == 1


def test_preformal_rejections_consume_attempts_not_candidate_chains(tmp_path) -> None:
    protocol = MockExperimentProtocol(
        results=[_make_protocol_result(ExperimentStage.SCREENING, "pass")]
    )
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_config(max_proposal_attempts=2),
    )
    generate_hypothesis = cm._explore_step_pipeline.generate_hypothesis
    calls = 0

    def reject_once(branch):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ProposalAttempt.failure(
                ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.RESEARCH_REJECTED,
                    reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
                    provenance={"stage": "proposal_hypothesis"},
                )
            )
        return generate_hypothesis(branch)

    cm._explore_step_pipeline.generate_hypothesis = reject_once

    terminal = cm.run(requested_rounds=99)

    assert terminal.stop_reason == QUALIFICATION_BOUNDARY_REACHED
    qualification = terminal.to_projection()["qualification"]
    assert qualification["proposal_attempts"] == 2
    assert qualification["verified_candidate_chains"] == 1
    assert qualification["formal_screening_stages"] == 1
    assert terminal.scheduled_calls == 2
    assert terminal.execution_outcome_counts["research_rejected"] == 1


def test_four_preformal_retries_count_actual_hc_dispatches_only(tmp_path) -> None:
    cm = _campaign(
        tmp_path,
        qualification_only=_config(max_proposal_attempts=4),
    )

    def always_reject(_branch):
        return ProposalAttempt.failure(
            ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
                provenance={"stage": "proposal_hypothesis"},
            )
        )

    cm._explore_step_pipeline.generate_hypothesis = always_reject

    terminal = cm.run(requested_rounds=99)

    assert terminal.stop_reason == QUALIFICATION_NOT_REACHED
    assert terminal.to_projection()["run_validity"] == {
        "status": "valid",
        "reason": "valid",
        "valid": True,
    }
    qualification = terminal.to_projection()["qualification"]
    assert qualification["proposal_attempts"] == 4
    assert qualification["verified_candidate_chains"] == 0
    assert qualification["formal_screening_stages"] == 0
    assert terminal.scheduled_calls == 4
    assert len(cm._branch_ctrl.get_reportable_branches()) == 3
    assert _completion_from_run_result(terminal) == (0, QUALIFICATION_NOT_REACHED)


def test_qualification_run_is_idempotent_and_cannot_reset_hard_caps(tmp_path) -> None:
    cm = _campaign(
        tmp_path,
        qualification_only=_config(max_proposal_attempts=1),
    )
    calls = 0

    def reject(_branch):
        nonlocal calls
        calls += 1
        return ProposalAttempt.failure(
            ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
                provenance={"stage": "proposal_hypothesis"},
            )
        )

    cm._explore_step_pipeline.generate_hypothesis = reject

    first = cm.run(requested_rounds=99)
    second = cm.run(requested_rounds=99)

    assert second is first
    assert calls == 1
    assert len(cm._step_history) == 1
    assert second.to_projection()["qualification"]["proposal_attempts"] == 1


def test_public_direct_step_is_disabled_in_qualification_mode(tmp_path) -> None:
    cm = _campaign(tmp_path, qualification_only=_config())

    result = cm.run_one_step()

    assert result.stopped is True
    assert result.execution_outcome is not None
    assert result.execution_outcome.reason_code == "QUALIFICATION_OUTER_LOOP_REQUIRED"
    assert cm._qualification_runtime.proposal_attempts == 0
    assert cm._branch_ctrl._branches == {}


def test_proposal_cap_blocks_before_branch_creation_without_consuming(tmp_path) -> None:
    cm = _campaign(
        tmp_path,
        qualification_only=_config(max_proposal_attempts=1),
    )
    runtime = cm._qualification_runtime
    runtime.proposal_attempts = 1

    with pytest.raises(
        QualificationProposalBudgetExhausted,
        match="proposal budget exhausted",
    ):
        cm._branch_step_runner.run_one_step()

    assert runtime.proposal_attempts == 1
    assert cm._branch_ctrl._branches == {}


def test_inflight_proposal_exception_refreshes_reserved_attempt_in_terminal(
    tmp_path,
) -> None:
    cm = _campaign(tmp_path, qualification_only=_config())

    def fail_after_dispatch(_branch):
        raise RuntimeError("synthetic proposal failure")

    cm._explore_step_pipeline.generate_hypothesis = fail_after_dispatch

    with pytest.raises(RuntimeError, match="synthetic proposal failure"):
        cm.run(requested_rounds=99)

    terminal = cm._campaign_loop.current_result
    assert terminal is not None
    projection = terminal.to_projection()
    assert projection["qualification"]["proposal_attempts"] == 1
    assert projection["status"] == "stopped"
    assert projection["run_validity"]["valid"] is False
    assert terminal.scheduled_calls == 1
    assert terminal.unknown_outcome_count == 1
    status = json.loads(
        (tmp_path / "campaign" / "status.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (tmp_path / "campaign" / "campaign_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["run_result"]["qualification"]["proposal_attempts"] == 1
    assert summary["run_result"]["qualification"]["proposal_attempts"] == 1


def test_heartbeat_interrupt_precedes_proposal_attempt_reservation(tmp_path) -> None:
    cm = _campaign(tmp_path, qualification_only=_config())
    hypothesis_calls: list[str] = []

    def interrupt_heartbeat(payload) -> None:
        assert payload["phase"] == "proposal_hypothesis"
        raise KeyboardInterrupt("synthetic heartbeat hardwall")

    def generate_hypothesis(branch):
        hypothesis_calls.append(branch.branch_id)
        return cm._proposal_pipeline.generate_hypothesis(branch)

    cm._explore_step_pipeline.update_status_progress = interrupt_heartbeat
    cm._explore_step_pipeline.generate_hypothesis = generate_hypothesis

    with pytest.raises(KeyboardInterrupt, match="synthetic heartbeat hardwall"):
        cm.run(requested_rounds=99)
    cm.finalize_requested_stop(
        "OUTER_HARDWALL_EXCEEDED",
        interrupted_override=True,
    )

    terminal = cm._campaign_loop.current_result
    assert terminal is not None
    projection = terminal.to_projection()
    assert projection["qualification"]["proposal_attempts"] == 0
    assert hypothesis_calls == []
    assert terminal.scheduled_calls == 1
    assert terminal.execution_outcome_counts["interrupted"] == 1


def test_inflight_hardwall_terminal_refreshes_reserved_attempt(tmp_path) -> None:
    cm = _campaign(tmp_path, qualification_only=_config())

    def interrupt_after_dispatch(_branch):
        raise KeyboardInterrupt("synthetic hardwall")

    cm._explore_step_pipeline.generate_hypothesis = interrupt_after_dispatch

    with pytest.raises(KeyboardInterrupt, match="synthetic hardwall"):
        cm.run(requested_rounds=99)
    cm.finalize_requested_stop(
        "OUTER_HARDWALL_EXCEEDED",
        interrupted_override=True,
    )

    terminal = cm._campaign_loop.current_result
    assert terminal is not None
    projection = terminal.to_projection()
    assert projection["qualification"]["proposal_attempts"] == 1
    assert projection["status"] == "stopped"
    assert terminal.scheduled_calls == 1
    assert terminal.execution_outcome_counts["interrupted"] == 1
    assert _completion_from_run_result(terminal)[0] == 22
    status = json.loads(
        (tmp_path / "campaign" / "status.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (tmp_path / "campaign" / "campaign_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["run_result"]["qualification"]["proposal_attempts"] == 1
    assert summary["run_result"]["qualification"]["proposal_attempts"] == 1


def test_runner_cleans_unaccepted_baseline_without_pre_reserving_proposal(
    tmp_path,
) -> None:
    cm = _campaign(tmp_path, qualification_only=_config())
    branch = cm._branch_ctrl.create_branch(cm._champion)
    baseline = tmp_path / "unaccepted-baseline"
    baseline.mkdir()
    cm._branch_workspaces[branch.branch_id] = str(baseline)
    seen_mapping: list[bool] = []

    cm._branch_step_runner._select_next = lambda _active: SchedulerAction(
        action="run_existing",
        branch=branch,
    )

    def run_explore(selected):
        seen_mapping.append(selected.branch_id in cm._branch_workspaces)
        return StepResult(
            action="explore",
            branch_id=selected.branch_id,
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
                provenance={"stage": "proposal_hypothesis"},
            ),
        )

    cm._branch_step_runner.run_explore_step = run_explore

    result = cm._branch_step_runner.run_one_step()

    assert result.execution_outcome is not None
    assert seen_mapping == [False]
    assert not baseline.exists()
    assert cm._qualification_runtime.proposal_attempts == 0


def test_baseline_cleanup_failure_blocks_before_hc_and_clears_mapping(
    tmp_path,
    monkeypatch,
) -> None:
    cm = _campaign(tmp_path, qualification_only=_config())
    branch = cm._branch_ctrl.create_branch(cm._champion)
    baseline = tmp_path / "unavailable-baseline"
    baseline.mkdir()
    cm._branch_workspaces[branch.branch_id] = str(baseline)
    dispatched: list[str] = []
    cm._branch_step_runner._select_next = lambda _active: SchedulerAction(
        action="run_existing",
        branch=branch,
    )
    cm._branch_step_runner.run_explore_step = lambda selected: (
        dispatched.append(selected.branch_id)
    )

    def fail_cleanup(_workspace: str) -> None:
        raise OSError("cleanup unavailable")

    monkeypatch.setattr(cm._materializer, "cleanup", fail_cleanup)

    result = cm._branch_step_runner.run_one_step()

    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert result.execution_outcome.reason_code == (
        "QUALIFICATION_PROPOSAL_BASE_CLEANUP_FAILED"
    )
    assert dispatched == []
    assert branch.branch_id not in cm._branch_workspaces
    assert cm._qualification_runtime.proposal_attempts == 0


def test_post_result_cleanup_exception_preserves_completed_accounting(
    tmp_path,
    monkeypatch,
) -> None:
    protocol = MockExperimentProtocol(
        results=[_make_protocol_result(ExperimentStage.SCREENING, "fail")]
    )
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_config(),
    )

    def fail_cleanup(_workspace: str) -> None:
        raise OSError("cleanup unavailable")

    monkeypatch.setattr(cm._materializer, "cleanup", fail_cleanup)

    with pytest.raises(OSError, match="cleanup unavailable"):
        cm.run(requested_rounds=99)

    terminal = cm._campaign_loop.current_result
    assert terminal is not None
    assert terminal.stop_reason == "unhandled_exception"
    assert terminal.scheduled_calls == 1
    assert terminal.evaluated_rounds == 1
    assert terminal.execution_outcome_counts["evaluated"] == 1
    assert terminal.unknown_outcome_count == 0
    projection = terminal.to_projection()
    assert projection["qualification"]["proposal_attempts"] == 1
    assert projection["qualification"]["verified_candidate_chains"] == 1
    assert projection["qualification"]["formal_screening_stages"] == 1
    assert projection["run_validity"] == {
        "status": "valid",
        "reason": "valid_incomplete",
        "valid": True,
    }
    branch = cm._branch_ctrl.get_branch(cm._step_history[-1].branch_id)
    assert branch.state is BranchState.PARKED_LINEAGE
    assert branch.current_code_hash is None
    assert branch.branch_id not in cm._branch_workspaces
    assert branch.branch_id not in cm._branch_patches


def test_candidate_canary_failures_count_chains_and_write_narrow_history(tmp_path) -> None:
    protocol = MockExperimentProtocol(results=[], canary_pass=False)
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_config(),
    )

    terminal = cm.run(requested_rounds=99)

    assert terminal.stop_reason == QUALIFICATION_NOT_REACHED
    qualification = terminal.to_projection()["qualification"]
    assert qualification["proposal_attempts"] == 2
    assert qualification["verified_candidate_chains"] == 2
    assert qualification["formal_screening_stages"] == 0
    assert protocol.experiment_call_count == 0
    assert cm._branch_workspaces == {}
    assert cm._branch_patches == {}
    branch_ids = [step.branch_id for step in cm._step_history]
    assert len(branch_ids) == 2
    assert len(set(branch_ids)) == 2
    assert [
        cm._branch_ctrl.get_branch(branch_id).state for branch_id in branch_ids
    ] == [BranchState.PARKED_LINEAGE, BranchState.PARKED_LINEAGE]
    records = [
        json.loads(line)
        for line in (
            tmp_path / "campaign" / "research_history.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    for record in records:
        assert record["patch"] is not None
        assert record["protocol"] is None
        assert record["outcome"]["outcome"] == "evaluated"
        assert record["outcome"]["stage"] == "canary"
        assert record["decision"]["value"] == Decision.ABANDON.value


def test_failed_chain_cleanup_error_still_retires_all_branch_authority(
    tmp_path,
    monkeypatch,
) -> None:
    cm = _campaign(tmp_path, qualification_only=_config())
    branch = cm._branch_ctrl.create_branch(cm._champion)
    branch.state = BranchState.ABANDONED
    branch.current_code_hash = "failed-candidate-hash"
    branch.hypothesis = cm._proposal_pipeline.generate_hypothesis(branch).proposal
    branch.direction = "failed candidate direction"
    workspace = tmp_path / "failed-workspace"
    workspace.mkdir()
    cm._branch_workspaces[branch.branch_id] = str(workspace)
    cm._branch_patches[branch.branch_id] = cm._proposal_pipeline.generate_code(
        branch,
        branch.hypothesis,
    ).proposal

    def fail_cleanup(_workspace: str) -> None:
        raise OSError("cleanup unavailable")

    monkeypatch.setattr(cm._materializer, "cleanup", fail_cleanup)

    with pytest.raises(OSError, match="cleanup unavailable"):
        cm._park_qualification_chain(branch.branch_id)

    assert branch.state is BranchState.PARKED_LINEAGE
    assert branch.current_code_hash is None
    assert branch.hypothesis is None
    assert branch.direction is None
    assert branch.branch_id not in cm._branch_workspaces
    assert branch.branch_id not in cm._branch_patches


class _CanaryConfigurationFailureProtocol(MockExperimentProtocol):
    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        del candidate_ws, champion_ws
        self.canary_call_count += 1
        raise ValueError("invalid canary configuration")


def test_canary_configuration_failure_is_incomplete_and_does_not_continue(
    tmp_path,
) -> None:
    protocol = _CanaryConfigurationFailureProtocol(results=[])
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_config(),
    )

    terminal = cm.run(requested_rounds=99)

    assert terminal.stop_reason == "evaluated_without_formal_protocol_result"
    assert terminal.completed is False
    qualification = terminal.to_projection()["qualification"]
    assert qualification["verified_candidate_chains"] == 1
    assert qualification["formal_screening_stages"] == 0
    assert qualification["disposition"] == "incomplete"
    assert _completion_from_run_result(terminal) == (
        22,
        "incomplete_qualification_stop:evaluated_without_formal_protocol_result",
    )
    assert protocol.canary_call_count == 1
    attempts = qualification["proposal_attempts"]
    branch_count = len(cm._branch_ctrl._branches)

    blocked = cm.run_one_step()

    assert blocked.execution_outcome is not None
    assert blocked.execution_outcome.reason_code == "QUALIFICATION_OUTER_LOOP_REQUIRED"
    assert cm._qualification_runtime.proposal_attempts == attempts
    assert len(cm._branch_ctrl._branches) == branch_count
    assert protocol.canary_call_count == 1


@pytest.mark.parametrize(
    ("outcome", "reason_code", "expected_completion"),
    (
        (
            ExecutionOutcome.BLOCKED_INFRA,
            "PROVIDER_CALL_BLOCKED_INFRA",
            (20, "incomplete_infra_stop:execution_blocked_infra"),
        ),
        (
            ExecutionOutcome.RESOURCE_EXHAUSTED,
            "PROVIDER_CALL_CAP_EXHAUSTED",
            (21, "incomplete_resource_stop:resource_exhausted"),
        ),
    ),
)
def test_typed_provider_terminals_remain_incomplete(
    tmp_path,
    outcome: ExecutionOutcome,
    reason_code: str,
    expected_completion: tuple[int, str],
) -> None:
    cm = _campaign(tmp_path, qualification_only=_config())
    cm._explore_step_pipeline.generate_hypothesis = lambda _branch: (
        ProposalAttempt.failure(
            ExecutionOutcomeRecord(
                outcome=outcome,
                reason_code=reason_code,
                provenance={"stage": "proposal_hypothesis"},
            )
        )
    )

    terminal = cm.run(requested_rounds=99)

    assert terminal.completed is False
    assert terminal.stop_reason == f"execution_{outcome.value}"
    qualification = terminal.to_projection()["qualification"]
    assert qualification["proposal_attempts"] == 1
    assert qualification["verified_candidate_chains"] == 0
    assert qualification["formal_screening_stages"] == 0
    assert qualification["disposition"] == "incomplete"
    assert _completion_from_run_result(terminal) == expected_completion
