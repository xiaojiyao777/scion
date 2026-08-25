from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from scion.core.branch import BranchController, StateTransitionError
from scion.core.campaign_loop import CampaignLoop
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    BranchState,
    ChampionState,
    Decision,
    ExperimentStage,
    HypothesisProposal,
    PatchProposal,
)
from scion.core.proposal_pipeline import ProposalAttempt
from scion.core.qualification import (
    QUALIFICATION_BOUNDARY_REACHED,
    QUALIFICATION_NOT_REACHED,
    QualificationDevelopmentBoundaryMode,
    QualificationOnlyConfig,
    QualificationProgress,
    QualificationRuntime,
    normalize_qualification_only_config,
)
from scion.core.resource_envelope import ResourceEnvelope
from scion.core.step_result import StepResult
from scion.tests.campaign_test_support import (
    _VALID_CODE_AFTER_PATCH,
    _VALID_HYPOTHESIS,
    MockExperimentProtocol,
    _campaign,
    _make_protocol_result,
)

_INITIAL_ONLY_MODE: QualificationDevelopmentBoundaryMode = "initial_screening_only_v1"
_ATTEMPT_CAP = 6


class _NoCallClient:
    model = "m32-s1a-no-call"

    def call_with_tool(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("S1a composition unexpectedly dispatched a provider")


def _initial_only_config(attempt_cap: int = _ATTEMPT_CAP) -> QualificationOnlyConfig:
    return QualificationOnlyConfig(
        max_proposal_attempts=attempt_cap,
        max_verified_candidate_chains=attempt_cap,
        max_formal_screening_stages=attempt_cap,
        development_boundary_mode=_INITIAL_ONLY_MODE,
    )


def _limits(*, candidates: int = 1) -> CodeResearchLimits:
    return CodeResearchLimits(
        max_turns=5,
        max_hypothesis_candidates=candidates,
    )


def _envelope() -> ResourceEnvelope:
    return ResourceEnvelope(provider_call_cap=200, outer_hardwall_sec=60)


def _candidate_failure_result() -> Any:
    result = _make_protocol_result(ExperimentStage.SCREENING, "pass")
    return replace(
        result,
        stats=replace(
            result.stats,
            total_pairs=1,
            attempted_pairs=1,
            valid_pairs=0,
            failed_pairs=1,
            candidate_failed_pairs=1,
        ),
    )


def _six_initial_results() -> list[Any]:
    return [
        _make_protocol_result(ExperimentStage.SCREENING, "pass"),
        _make_protocol_result(ExperimentStage.SCREENING, "expand"),
        _make_protocol_result(ExperimentStage.SCREENING, "fail"),
        _candidate_failure_result(),
        _make_protocol_result(ExperimentStage.SCREENING, "pass"),
        _make_protocol_result(ExperimentStage.SCREENING, "expand"),
    ]


def _install_synthetic_bounded_proposals(cm: Any, *, candidates: int) -> None:
    telemetry = cm._proposal_runtime_telemetry
    assert telemetry is not None

    def generate_hypothesis(_branch: Any) -> ProposalAttempt[HypothesisProposal]:
        for _ in range(candidates):
            telemetry.record_hypothesis_candidate_completed()
        telemetry.record_hypothesis_candidate_selected()
        return ProposalAttempt.success(
            HypothesisProposal(**deepcopy(_VALID_HYPOTHESIS))
        )

    def generate_code(
        _branch: Any,
        _hypothesis: HypothesisProposal,
    ) -> ProposalAttempt[PatchProposal]:
        return ProposalAttempt.success(
            PatchProposal(
                file_path="operators/local_search.py",
                action="modify",
                code_content=_VALID_CODE_AFTER_PATCH,
            )
        )

    cm._explore_step_pipeline.generate_hypothesis = generate_hypothesis
    cm._explore_step_pipeline.generate_code = generate_code


def test_default_config_and_projection_remain_byte_compatible() -> None:
    config = QualificationOnlyConfig(3, 2, 4)

    assert config.development_boundary_mode == "qualification_v1"
    assert config.to_projection() == {
        "max_proposal_attempts": 3,
        "max_verified_candidate_chains": 2,
        "max_formal_screening_stages": 4,
    }
    assert QualificationProgress(config=config).to_projection() == {
        "mode": "qualification_only",
        "limits": config.to_projection(),
        "proposal_attempts": 0,
        "verified_candidate_chains": 0,
        "formal_screening_stages": 0,
        "initial_screening_stages": 0,
        "expanded_screening_stages": 0,
        "disposition": "pending",
    }


def test_initial_only_projects_versioned_mode_outside_legacy_limits() -> None:
    config = _initial_only_config()
    projection = QualificationProgress(config=config).to_projection()

    assert projection["development_boundary_mode"] == _INITIAL_ONLY_MODE
    assert projection["limits"] == {
        "max_proposal_attempts": _ATTEMPT_CAP,
        "max_verified_candidate_chains": _ATTEMPT_CAP,
        "max_formal_screening_stages": _ATTEMPT_CAP,
    }
    assert "development_boundary_mode" not in projection["limits"]


@pytest.mark.parametrize(
    "value",
    ("legacy", "initial_screening_only", "future_mode", True, 1, None),
)
def test_development_boundary_mode_fails_closed(value: object) -> None:
    with pytest.raises(ValueError, match="development_boundary_mode"):
        QualificationOnlyConfig(
            development_boundary_mode=value,  # type: ignore[arg-type]
        )


def test_initial_only_requires_all_three_caps_to_equal_a() -> None:
    with pytest.raises(ValueError, match="all qualification caps"):
        normalize_qualification_only_config(
            {
                "max_proposal_attempts": 6,
                "max_verified_candidate_chains": 5,
                "max_formal_screening_stages": 6,
                "development_boundary_mode": _INITIAL_ONLY_MODE,
            }
        )


@pytest.mark.parametrize(
    ("qualification", "reason"),
    (
        (
            {
                "max_proposal_attempts": 6,
                "max_verified_candidate_chains": 5,
                "max_formal_screening_stages": 6,
                "development_boundary_mode": _INITIAL_ONLY_MODE,
            },
            "all qualification caps",
        ),
        (
            {
                "max_proposal_attempts": 6,
                "max_verified_candidate_chains": 6,
                "max_formal_screening_stages": 6,
                "development_boundary_mode": "future_mode",
            },
            "development_boundary_mode",
        ),
    ),
)
def test_invalid_initial_only_mode_or_caps_fail_before_campaign_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    qualification: dict[str, object],
    reason: str,
) -> None:
    def development_tripwire(**_kwargs: Any) -> None:
        raise AssertionError("S1a config guard ran after development closure")

    monkeypatch.setattr(
        "scion.core.campaign_composition.validate_development_closure_boundary",
        development_tripwire,
    )

    with pytest.raises(ValueError, match=reason):
        _campaign(
            tmp_path,
            llm_client=_NoCallClient(),
            qualification_only=qualification,
            resource_envelope=_envelope(),
            code_research_limits=_limits(),
        )

    assert not (tmp_path / "campaign").exists()


@pytest.mark.parametrize(
    ("limits", "envelope", "reason"),
    (
        (None, _envelope(), "bounded code_research_limits"),
        (
            _limits(),
            ResourceEnvelope(outer_hardwall_sec=60),
            "provider_call_cap",
        ),
        (
            _limits(),
            ResourceEnvelope(provider_call_cap=200),
            "outer_hardwall_sec",
        ),
    ),
)
def test_initial_only_composition_guards_run_before_root_or_development_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limits: CodeResearchLimits | None,
    envelope: ResourceEnvelope,
    reason: str,
) -> None:
    def development_tripwire(**_kwargs: Any) -> None:
        raise AssertionError("S1a guard ran after development closure")

    monkeypatch.setattr(
        "scion.core.campaign_composition.validate_development_closure_boundary",
        development_tripwire,
    )

    with pytest.raises(ValueError, match=reason):
        _campaign(
            tmp_path,
            llm_client=_NoCallClient(),
            qualification_only=_initial_only_config(),
            resource_envelope=envelope,
            code_research_limits=limits,
        )

    assert not (tmp_path / "campaign").exists()


@pytest.mark.parametrize(
    ("decision", "post_state"),
    (
        (Decision.CONTINUE_EXPLORE, BranchState.EXPLORE),
        (Decision.ABANDON, BranchState.ABANDONED),
        (Decision.EXPAND_SCREENING, BranchState.EXPLORE_EXPAND),
        (Decision.QUEUE_VALIDATE, BranchState.READY_VALIDATE),
    ),
)
def test_dedicated_branch_retirement_accepts_only_exact_decision_poststate(
    decision: Decision,
    post_state: BranchState,
) -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(version=1, operator_pool={}, code_snapshot_path="/champion")
    )
    branch.state = post_state

    controller.park_initial_screening_study_branch(branch.branch_id, decision)

    assert branch.state is BranchState.PARKED_LINEAGE
    assert branch.hypothesis is None


@pytest.mark.parametrize(
    ("decision", "post_state"),
    (
        (Decision.QUEUE_VALIDATE, BranchState.EXPLORE),
        (Decision.QUEUE_VALIDATE, BranchState.VALIDATING),
        (Decision.EXPAND_SCREENING, BranchState.READY_VALIDATE),
        (Decision.CONTINUE_EXPLORE, BranchState.ABANDONED),
    ),
)
def test_dedicated_branch_retirement_rejects_pending_heldout_and_mismatch(
    decision: Decision,
    post_state: BranchState,
) -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(version=1, operator_pool={}, code_snapshot_path="/champion")
    )
    branch.state = post_state

    with pytest.raises(StateTransitionError, match="decision/state mismatch"):
        controller.park_initial_screening_study_branch(branch.branch_id, decision)

    assert branch.state is post_state


def test_initial_only_runtime_rejects_every_expansion_authority() -> None:
    runtime = QualificationRuntime(_initial_only_config(attempt_cap=1))
    runtime.record_verified_candidate("branch")

    with pytest.raises(ValueError, match="forbids expanded"):
        runtime.record_screening_stage("branch", expanded=True)
    runtime.record_screening_stage("branch", expanded=False)
    with pytest.raises(ValueError, match="forbids expansion requests"):
        runtime.request_expansion("branch")
    runtime.pending_expansion_branch_id = "branch"

    assert runtime.authorize_expansion("branch") is False
    assert runtime.expanded_screening_stages == 0


def test_direct_initial_only_loop_requires_retirement_callback_before_side_effects() -> (
    None
):
    runtime = QualificationRuntime(_initial_only_config(attempt_cap=1))
    side_effects: list[str] = []

    def unexpected_step() -> StepResult:
        side_effects.append("run_one_step")
        raise AssertionError("initial-only loop dispatched before wiring preflight")

    def should_stop() -> bool:
        side_effects.append("should_stop")
        return False

    def get_last_stop_reason() -> None:
        side_effects.append("get_stop")

    def get_final_wait_timeout() -> float:
        side_effects.append("timeout")
        return 0.0

    loop = CampaignLoop(
        write_status=lambda **_kwargs: side_effects.append("write_status"),
        drain_weight_opt_events=lambda: side_effects.append("drain"),
        should_stop=should_stop,
        get_last_stop_reason=get_last_stop_reason,
        set_last_stop_reason=lambda _reason: side_effects.append("set_stop"),
        run_one_step=unexpected_step,
        write_terminal_artifacts=lambda _result: side_effects.append("terminal"),
        get_final_wait_timeout=get_final_wait_timeout,
        wait_weight_opt_all=lambda _timeout: side_effects.append("wait"),
        qualification_runtime=runtime,
    )

    with pytest.raises(RuntimeError, match="retirement callback is unavailable"):
        loop.run(requested_rounds=1)

    assert side_effects == []
    assert runtime.started is False
    assert loop.current_result is None


def test_direct_legacy_qualification_loop_allows_missing_retirement_callback() -> None:
    runtime = QualificationRuntime(
        QualificationOnlyConfig(
            max_proposal_attempts=1,
            max_verified_candidate_chains=1,
            max_formal_screening_stages=1,
        )
    )
    calls = 0

    def run_one_step() -> StepResult:
        nonlocal calls
        calls += 1
        runtime.reserve_proposal_attempt()
        return StepResult(
            action="explore",
            branch_id="branch-legacy",
            decision=Decision.QUEUE_VALIDATE,
            verification_passed=True,
            protocol_result=_make_protocol_result(ExperimentStage.SCREENING, "pass"),
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.EVALUATED,
                reason_code="EVALUATION_COMPLETED",
                provenance={"stage": "screening"},
            ),
        )

    loop = CampaignLoop(
        write_status=lambda **_kwargs: None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda _reason: None,
        run_one_step=run_one_step,
        write_terminal_artifacts=lambda _result: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda _timeout: None,
        qualification_runtime=runtime,
    )

    terminal = loop.run(requested_rounds=99)

    assert calls == 1
    assert terminal.stop_reason == QUALIFICATION_BOUNDARY_REACHED
    assert terminal.completed is True


@pytest.mark.parametrize(
    ("requested_rounds", "candidates"),
    ((1, 1), (_ATTEMPT_CAP, 1), (99, 1), (1, 2)),
)
def test_initial_only_closes_exact_a_fresh_b0_opportunities_for_k1_and_k2(
    tmp_path: Path,
    requested_rounds: int,
    candidates: int,
) -> None:
    protocol = MockExperimentProtocol(results=_six_initial_results())
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_initial_only_config(),
        resource_envelope=_envelope(),
        code_research_limits=_limits(candidates=candidates),
    )
    _install_synthetic_bounded_proposals(cm, candidates=candidates)

    terminal = cm.run(requested_rounds=requested_rounds)
    projection = terminal.to_projection()
    expected_decisions = [
        Decision.QUEUE_VALIDATE,
        Decision.EXPAND_SCREENING,
        Decision.CONTINUE_EXPLORE,
        Decision.ABANDON,
        Decision.QUEUE_VALIDATE,
        Decision.EXPAND_SCREENING,
    ]

    assert terminal.stop_reason == QUALIFICATION_NOT_REACHED
    assert terminal.completed is True
    assert terminal.requested_rounds == requested_rounds
    assert terminal.scheduled_calls == _ATTEMPT_CAP
    assert terminal.evaluated_rounds == _ATTEMPT_CAP
    assert terminal.protocol_stage_counts == {
        "screening": _ATTEMPT_CAP,
        "validation": 0,
        "frozen": 0,
    }
    assert projection["qualification"] == {
        "mode": "qualification_only",
        "development_boundary_mode": _INITIAL_ONLY_MODE,
        "limits": {
            "max_proposal_attempts": _ATTEMPT_CAP,
            "max_verified_candidate_chains": _ATTEMPT_CAP,
            "max_formal_screening_stages": _ATTEMPT_CAP,
        },
        "proposal_attempts": _ATTEMPT_CAP,
        "verified_candidate_chains": _ATTEMPT_CAP,
        "formal_screening_stages": _ATTEMPT_CAP,
        "initial_screening_stages": _ATTEMPT_CAP,
        "expanded_screening_stages": 0,
        "disposition": QUALIFICATION_NOT_REACHED,
    }
    assert protocol.experiment_call_count == _ATTEMPT_CAP
    assert [step.decision for step in cm._step_history] == expected_decisions
    assert all(
        step.protocol_result is not None
        and step.protocol_result.stage is ExperimentStage.SCREENING
        and step.candidate_parent_scope == "declared_champion"
        for step in cm._step_history
    )
    branch_ids = [step.branch_id for step in cm._step_history]
    assert len(set(branch_ids)) == _ATTEMPT_CAP
    for branch_id, decision in zip(branch_ids, expected_decisions, strict=True):
        branch = cm._branch_ctrl.get_branch(branch_id)
        assert branch.state is BranchState.PARKED_LINEAGE
        assert branch.current_code_hash is None
        assert branch.hypothesis is None
        assert branch.direction is None
        events = [
            event
            for event in cm._registry.query_by_branch(branch_id)
            if event["event_kind"] == "experiment"
        ]
        assert len(events) == 1
        assert events[0]["decision"] == decision.value
    assert cm._branch_workspaces == {}
    assert cm._branch_patches == {}
    assert cm._qualification_runtime.pending_expansion_branch_id is None

    status = json.loads(
        (tmp_path / "campaign" / "status.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (tmp_path / "campaign" / "campaign_summary.json").read_text(encoding="utf-8")
    )
    history = [
        json.loads(line)
        for line in (tmp_path / "campaign" / "research_history.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert status["run_result"] == summary["run_result"] == projection
    assert status["run_result"]["stop_reason"] != "qualification_boundary_reached"
    assert all(
        branch["state"] != BranchState.READY_VALIDATE.value
        for branch in status["branches"]
    )
    assert all(branch["current_code_hash"] is None for branch in status["branches"])
    assert [step["decision"] for step in summary["steps"]] == [
        decision.value for decision in expected_decisions
    ]
    assert [record["decision"]["value"] for record in history] == [
        decision.value for decision in expected_decisions
    ]


def test_run_cleanup_failure_is_incomplete_and_clears_candidate_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = MockExperimentProtocol(
        results=[_make_protocol_result(ExperimentStage.SCREENING, "pass")]
    )
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_initial_only_config(attempt_cap=1),
        resource_envelope=_envelope(),
        code_research_limits=_limits(),
    )
    _install_synthetic_bounded_proposals(cm, candidates=1)

    def fail_cleanup(_workspace: str) -> None:
        raise OSError("cleanup unavailable")

    monkeypatch.setattr(cm._materializer, "cleanup", fail_cleanup)

    with pytest.raises(OSError, match="cleanup unavailable"):
        cm.run(requested_rounds=1)

    assert len(cm._step_history) == 1
    branch = cm._branch_ctrl.get_branch(cm._step_history[0].branch_id)
    assert branch.state is BranchState.PARKED_LINEAGE
    assert branch.current_code_hash is None
    assert branch.hypothesis is None
    assert branch.direction is None
    assert branch.branch_id not in cm._branch_workspaces
    assert branch.branch_id not in cm._branch_patches
    terminal = cm._campaign_loop.current_result
    assert terminal is not None
    assert terminal.stop_reason == "unhandled_exception"
    qualification = terminal.to_projection()["qualification"]
    assert qualification["proposal_attempts"] == 1
    assert qualification["initial_screening_stages"] == 1
    assert qualification["expanded_screening_stages"] == 0
    assert qualification["disposition"] == "incomplete"
    status = json.loads(
        (tmp_path / "campaign" / "status.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (tmp_path / "campaign" / "campaign_summary.json").read_text(encoding="utf-8")
    )
    assert status["run_result"] == summary["run_result"] == terminal.to_projection()


def test_typed_h_research_failure_before_a_is_incomplete_without_imputation(
    tmp_path: Path,
) -> None:
    protocol = MockExperimentProtocol(
        results=[_make_protocol_result(ExperimentStage.SCREENING, "pass")]
    )
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_initial_only_config(),
        resource_envelope=_envelope(),
        code_research_limits=_limits(),
    )
    _install_synthetic_bounded_proposals(cm, candidates=1)
    successful_hypothesis = cm._explore_step_pipeline.generate_hypothesis
    calls = 0

    def fail_second_hypothesis(branch: Any) -> ProposalAttempt[HypothesisProposal]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return successful_hypothesis(branch)
        return ProposalAttempt.failure(
            ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESOURCE_EXHAUSTED,
                reason_code="HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED",
                provenance={"stage": "proposal_hypothesis"},
            )
        )

    cm._explore_step_pipeline.generate_hypothesis = fail_second_hypothesis

    terminal = cm.run(requested_rounds=99)
    qualification = terminal.to_projection()["qualification"]

    assert terminal.stop_reason == "execution_resource_exhausted"
    assert terminal.completed is False
    assert terminal.scheduled_calls == 2
    assert terminal.evaluated_rounds == 1
    assert qualification["proposal_attempts"] == 2
    assert qualification["verified_candidate_chains"] == 1
    assert qualification["formal_screening_stages"] == 1
    assert qualification["initial_screening_stages"] == 1
    assert qualification["expanded_screening_stages"] == 0
    assert qualification["disposition"] == "incomplete"
    assert protocol.experiment_call_count == 1
    assert len(cm._step_history) == 2
    assert cm._step_history[-1].execution_outcome is not None
    assert (
        cm._step_history[-1].execution_outcome.reason_code
        == "HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED"
    )


def test_outer_stop_before_a_is_incomplete_and_does_not_impute_attempts(
    tmp_path: Path,
) -> None:
    protocol = MockExperimentProtocol(results=_six_initial_results())
    cm = _campaign(
        tmp_path,
        experiment_protocol=protocol,
        qualification_only=_initial_only_config(),
        resource_envelope=_envelope(),
        code_research_limits=_limits(),
    )
    _install_synthetic_bounded_proposals(cm, candidates=1)
    retire = cm._campaign_loop.retire_initial_screening_study_chain

    def retire_then_stop(branch_id: str, decision: Decision) -> None:
        retire(branch_id, decision)
        cm.request_stop("operator_requested_stop")

    cm._campaign_loop.retire_initial_screening_study_chain = retire_then_stop

    terminal = cm.run(requested_rounds=99)
    qualification = terminal.to_projection()["qualification"]

    assert terminal.stop_reason == "operator_requested_stop"
    assert terminal.completed is False
    assert terminal.scheduled_calls == 1
    assert terminal.evaluated_rounds == 1
    assert qualification["proposal_attempts"] == 1
    assert qualification["initial_screening_stages"] == 1
    assert qualification["expanded_screening_stages"] == 0
    assert qualification["disposition"] == "incomplete"
    assert protocol.experiment_call_count == 1
