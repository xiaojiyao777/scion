from __future__ import annotations

import uuid

import pytest

from scion.core.evaluation_pipeline import EvaluationPipeline, EvaluationRequest
from scion.core.features import BudgetState
from scion.core.models import (
    BranchState,
    CanaryResult,
    CaseAggregateFeedback,
    CheckResult,
    EvalStats,
    ExperimentStage,
    PairwiseCaseFeedback,
    ProtocolResult,
    VerificationResult,
)


def _request(
    *,
    state: BranchState = BranchState.EXPLORE,
    action: str = "modify",
    expand: bool = False,
    expand_round: int = 0,
) -> EvaluationRequest:
    return EvaluationRequest(
        branch_id=str(uuid.uuid4()),
        branch_state=state,
        candidate_workspace="/tmp/candidate",
        champion_workspace="/tmp/champion",
        hypothesis_action=action,
        expand=expand,
        expand_round=expand_round,
    )


def _protocol_result(
    *,
    stage: ExperimentStage = ExperimentStage.SCREENING,
    raw_metrics_ref: str = "/tmp/metrics.json",
    pair_feedback: tuple[PairwiseCaseFeedback, ...] = (),
    case_feedback: tuple[CaseAggregateFeedback, ...] = (),
    case_ids: tuple[str, ...] = (),
    seed_set: tuple[int, ...] = (),
    exposed_summary: str = "aggregate summary",
) -> ProtocolResult:
    return ProtocolResult(
        stage=stage,
        stats=EvalStats(
            n_cases=4,
            wins=3,
            losses=1,
            ties=0,
            win_rate=0.75,
            median_delta=0.12,
            ci_low=0.02,
            ci_high=0.2,
            statistical_status="positive",
            statistical_metric="total_cost",
        ),
        gate_outcome="pass",
        reason_codes=(f"{stage.value.upper()}_PASS",),
        exposed_summary=exposed_summary,
        raw_metrics_ref=raw_metrics_ref,
        case_ids=case_ids,
        seed_set=seed_set,
        pair_feedback=pair_feedback,
        case_feedback=case_feedback,
    )


class RecordingProtocol:
    def __init__(self, result: ProtocolResult) -> None:
        self.result = result
        self.canary_calls: list[tuple[str, str]] = []
        self.experiment_calls: list[dict[str, object]] = []

    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        self.canary_calls.append((candidate_ws, champion_ws))
        return CanaryResult(passed=True, reason=None)

    def run_experiment(self, **kwargs: object) -> ProtocolResult:
        self.experiment_calls.append(kwargs)
        return self.result


class FailingIfCalledProtocol:
    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        raise AssertionError("protocol should not run after verification failure")

    def run_experiment(self, **kwargs: object) -> ProtocolResult:
        raise AssertionError("protocol should not run after verification failure")


class MissingCanaryProtocol:
    def __init__(self) -> None:
        self.experiment_called = False

    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        raise ValueError("Canary split not configured")

    def run_experiment(self, **kwargs: object) -> ProtocolResult:
        self.experiment_called = True
        return _protocol_result()


def test_screening_pass_generates_expected_decision_features() -> None:
    protocol = RecordingProtocol(_protocol_result())
    pipeline = EvaluationPipeline(
        experiment_protocol=protocol,
        budget_provider=lambda: BudgetState(total=10, used=3),
    )

    outcome = pipeline.evaluate(
        _request(state=BranchState.EXPLORE, expand=True, expand_round=1)
    )

    features = outcome.decision_features
    assert features.stage == "screening"
    assert features.contract_passed is True
    assert features.verification_passed is True
    assert features.canary_passed is True
    assert features.n_cases == 4
    assert features.win_rate == pytest.approx(0.75)
    assert features.median_delta == pytest.approx(0.12)
    assert features.ci_low == pytest.approx(0.02)
    assert features.statistical_status == "positive"
    assert features.statistical_metric == "total_cost"
    assert features.budget_remaining_ratio == pytest.approx(0.7)
    assert outcome.raw_metrics_ref == "/tmp/metrics.json"
    assert protocol.experiment_calls == [
        {
            "stage": ExperimentStage.SCREENING,
            "candidate_ws": "/tmp/candidate",
            "champion_ws": "/tmp/champion",
            "hypothesis_action": "modify",
            "expand": True,
            "expand_round": 1,
        }
    ]


def test_verification_failure_generates_failed_features_and_detail() -> None:
    failed = CheckResult(
        name="V6_feasibility",
        passed=False,
        severity="heavy",
        detail="capacity violation",
        elapsed_ms=17,
    )

    def verification(_: EvaluationRequest) -> VerificationResult:
        return VerificationResult(
            passed=False,
            checks=(failed,),
            failure_severity="heavy",
            first_failure="V6_feasibility",
        )

    pipeline = EvaluationPipeline(
        verification_evaluator=verification,
        experiment_protocol=FailingIfCalledProtocol(),
    )

    outcome = pipeline.evaluate(_request())

    assert outcome.protocol_result is None
    assert outcome.raw_metrics_ref is None
    assert outcome.decision_features.contract_passed is True
    assert outcome.decision_features.verification_passed is False
    assert outcome.decision_features.canary_passed is True
    assert outcome.decision_features.n_cases == 0
    assert outcome.verification_detail is not None
    assert "severity=heavy" in outcome.verification_detail
    assert "V6_feasibility" in outcome.verification_detail
    assert "capacity violation" in outcome.verification_detail


def test_missing_canary_fails_closed_and_skips_protocol_experiment() -> None:
    protocol = MissingCanaryProtocol()
    pipeline = EvaluationPipeline(experiment_protocol=protocol)

    outcome = pipeline.evaluate(_request(state=BranchState.FROZEN_TESTING))

    assert outcome.protocol_result is None
    assert outcome.raw_metrics_ref is None
    assert outcome.canary_result.passed is False
    assert outcome.decision_features.canary_passed is False
    assert protocol.experiment_called is False
    assert "Canary split not configured" in (outcome.canary_result.reason or "")


@pytest.mark.parametrize(
    ("branch_state", "stage"),
    [
        (BranchState.VALIDATING, ExperimentStage.VALIDATION),
        (BranchState.FROZEN_TESTING, ExperimentStage.FROZEN),
    ],
)
def test_validation_and_frozen_strip_per_case_feedback(
    branch_state: BranchState,
    stage: ExperimentStage,
) -> None:
    pair_feedback = (
        PairwiseCaseFeedback(
            case_id="case-A",
            seed=1,
            comparison="win",
            delta=0.1,
        ),
    )
    case_feedback = (
        CaseAggregateFeedback(
            case_id="case-A",
            n_pairs=1,
            wins=1,
            losses=0,
            ties=0,
            win_rate=1.0,
            dominant_result="win",
        ),
    )
    protocol = RecordingProtocol(
        _protocol_result(
            stage=stage,
            raw_metrics_ref="/tmp/private-full-metrics.json",
            pair_feedback=pair_feedback,
            case_feedback=case_feedback,
            case_ids=("case-A",),
            seed_set=(1,),
            exposed_summary="case-A should not be exposed",
        )
    )
    pipeline = EvaluationPipeline(experiment_protocol=protocol)

    outcome = pipeline.evaluate(_request(state=branch_state))

    assert outcome.protocol_result is not None
    assert outcome.protocol_result.raw_metrics_ref == "/tmp/private-full-metrics.json"
    assert outcome.raw_metrics_ref == "/tmp/private-full-metrics.json"
    assert outcome.protocol_result.stats.n_cases == 4
    assert outcome.protocol_result.pair_feedback == ()
    assert outcome.protocol_result.case_feedback == ()
    assert outcome.protocol_result.case_ids == ("case-A",)
    assert outcome.protocol_result.seed_set == (1,)
    assert "case-A" not in outcome.protocol_result.exposed_summary
    assert "raw_metrics_ref=" not in outcome.protocol_result.exposed_summary
    assert "/tmp/private-full-metrics.json" not in outcome.protocol_result.exposed_summary
    assert outcome.decision_features.stage == stage.value
    assert outcome.decision_features.n_cases == 4
    assert outcome.decision_features.win_rate == pytest.approx(0.75)
