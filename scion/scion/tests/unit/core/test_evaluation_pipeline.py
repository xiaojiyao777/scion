from __future__ import annotations

import uuid

import pytest

from scion.core.evaluation_pipeline import EvaluationPipeline, EvaluationRequest
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
from scion.core.runtime_budget_diagnostics import SCREENING_RUNTIME_BUDGET_SATURATION


def _request(
    *,
    state: BranchState = BranchState.EXPLORE,
    selected_surface: str | None = None,
    priority_case_ids: tuple[str, ...] = (),
    force_fresh_champion: bool = False,
) -> EvaluationRequest:
    return EvaluationRequest(
        branch_id=str(uuid.uuid4()),
        branch_state=state,
        candidate_workspace="/tmp/candidate",
        champion_workspace="/tmp/champion",
        hypothesis_action="modify",
        selected_surface=selected_surface,
        priority_case_ids=priority_case_ids,
        force_fresh_champion=force_fresh_champion,
    )


def _protocol_result(
    *,
    stage: ExperimentStage = ExperimentStage.SCREENING,
    reason_codes: tuple[str, ...] = ("SCREENING_PASS",),
    gate_outcome: str = "pass",
    pair_feedback: tuple[PairwiseCaseFeedback, ...] = (),
    case_feedback: tuple[CaseAggregateFeedback, ...] = (),
    candidate_surface_runtime_summary: dict | None = None,
) -> ProtocolResult:
    return ProtocolResult(
        stage=stage,
        stats=EvalStats(
            n_cases=4,
            wins=3,
            losses=1,
            ties=0,
            win_rate=0.75,
            median_delta=0.1,
            ci_low=0.01,
            ci_high=0.2,
        ),
        gate_outcome=gate_outcome,
        reason_codes=reason_codes,
        exposed_summary="aggregate summary",
        raw_metrics_ref="/tmp/metrics.json",
        pair_feedback=pair_feedback,
        case_feedback=case_feedback,
        case_ids=("case-A",),
        seed_set=(1,),
        candidate_surface_runtime_summary=(
            candidate_surface_runtime_summary or {}
        ),
    )


class RecordingProtocol:
    def __init__(self, result: ProtocolResult) -> None:
        self.result = result
        self._problem_spec = {
            "research_surfaces": [{"name": "dispatch_policy"}],
        }
        self.canary_calls: list[dict] = []
        self.experiment_calls: list[dict] = []

    def run_canary(
        self,
        candidate_ws: str,
        champion_ws: str,
        *,
        selected_surface: str | None = None,
    ) -> CanaryResult:
        self.canary_calls.append(
            {
                "candidate_ws": candidate_ws,
                "champion_ws": champion_ws,
                "selected_surface": selected_surface,
            }
        )
        return CanaryResult(passed=True)

    def run_experiment(
        self,
        *,
        selected_surface: str | None = None,
        **kwargs,
    ) -> ProtocolResult:
        self.experiment_calls.append(
            {"selected_surface": selected_surface, **dict(kwargs)}
        )
        return self.result


class FailingCanaryProtocol(RecordingProtocol):
    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(passed=False, reason="algorithm canary failed")

    def run_experiment(self, **kwargs) -> ProtocolResult:  # pragma: no cover
        raise AssertionError(f"experiment must not run after canary failure: {kwargs}")


def test_screening_result_generates_numeric_decision_features() -> None:
    protocol = RecordingProtocol(_protocol_result())
    pipeline = EvaluationPipeline(experiment_protocol=protocol)

    outcome = pipeline.evaluate(_request(selected_surface="dispatch_policy"))

    assert outcome.protocol_result is not None
    assert outcome.decision_features.stage == "screening"
    assert outcome.decision_features.win_rate == pytest.approx(0.75)
    assert outcome.raw_metrics_ref == "/tmp/metrics.json"
    assert protocol.experiment_calls[0]["selected_surface"] == "dispatch_policy"
    assert "expected_telemetry" not in protocol.experiment_calls[0]
    assert "mechanism_changes" not in protocol.experiment_calls[0]
    assert "protected_objectives" not in protocol.experiment_calls[0]


def test_priority_cases_forward_as_protocol_measurement_input() -> None:
    protocol = RecordingProtocol(_protocol_result())
    outcome = EvaluationPipeline(experiment_protocol=protocol).evaluate(
        _request(priority_case_ids=("CMT2.vrp", "CMT4.vrp"))
    )

    assert outcome.canary_result.passed is True
    assert protocol.experiment_calls[0]["priority_case_ids"] == (
        "CMT2.vrp",
        "CMT4.vrp",
    )


def test_verification_failure_skips_protocol() -> None:
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

    protocol = RecordingProtocol(_protocol_result())
    outcome = EvaluationPipeline(
        verification_evaluator=verification,
        experiment_protocol=protocol,
    ).evaluate(_request())

    assert outcome.verification_result.passed is False
    assert outcome.protocol_result is None
    assert protocol.experiment_calls == []


def test_canary_failure_skips_protocol_experiment() -> None:
    outcome = EvaluationPipeline(
        experiment_protocol=FailingCanaryProtocol(_protocol_result())
    ).evaluate(_request())

    assert outcome.canary_result.passed is False
    assert outcome.protocol_result is None
    assert outcome.decision_features.canary_passed is False


@pytest.mark.parametrize(
    ("branch_state", "stage"),
    (
        (BranchState.VALIDATING, ExperimentStage.VALIDATION),
        (BranchState.FROZEN_TESTING, ExperimentStage.FROZEN),
    ),
)
def test_validation_and_frozen_keep_aggregate_but_hide_pair_feedback(
    branch_state: BranchState,
    stage: ExperimentStage,
) -> None:
    pair = PairwiseCaseFeedback(
        case_id="case-A",
        seed=1,
        comparison="win",
        delta=0.1,
    )
    case = CaseAggregateFeedback(
        case_id="case-A",
        n_pairs=1,
        wins=1,
        losses=0,
        ties=0,
        win_rate=1.0,
        dominant_result="win",
    )
    outcome = EvaluationPipeline(
        experiment_protocol=RecordingProtocol(
            _protocol_result(
                stage=stage,
                reason_codes=(f"{stage.value.upper()}_PASS",),
                pair_feedback=(pair,),
                case_feedback=(case,),
            )
        )
    ).evaluate(_request(state=branch_state))

    assert outcome.protocol_result is not None
    assert outcome.protocol_result.pair_feedback == ()
    assert outcome.protocol_result.case_feedback == ()
    assert outcome.protocol_result.case_ids == ("case-A",)
    assert outcome.protocol_result.seed_set == (1,)


def test_legacy_telemetry_guard_payload_is_observation_not_gate() -> None:
    legacy_guard = {
        "passed": False,
        "failures": [
            {
                "code": "TELEMETRY_ACTIVITY_NOT_OBSERVED",
                "severity": "fail",
            }
        ],
    }
    outcome = EvaluationPipeline(
        experiment_protocol=RecordingProtocol(
            _protocol_result(
                reason_codes=("SCREENING_PASS",),
                candidate_surface_runtime_summary={
                    "selected_surface": "solver_design",
                    "telemetry_guard": legacy_guard,
                },
            )
        )
    ).evaluate(_request())

    assert outcome.protocol_result is not None
    assert outcome.protocol_result.reason_codes == ("SCREENING_PASS",)
    assert outcome.protocol_result.gate_outcome == "pass"
    assert not hasattr(outcome.decision_features, "telemetry_guard_failed")
    assert not hasattr(outcome.decision_features, "telemetry_validation_repairable")


def test_runtime_budget_diagnostic_remains_protocol_observation() -> None:
    diagnostic = {
        "schema": "scion.runtime_budget_diagnostic.v1",
        "code": SCREENING_RUNTIME_BUDGET_SATURATION,
        "stage": "screening",
        "severity": "warn",
        "total_pairs": 16,
        "saturation_ratio": 0.97,
    }
    outcome = EvaluationPipeline(
        experiment_protocol=RecordingProtocol(
            _protocol_result(
                reason_codes=("SCREENING_FAIL_WIN_RATE",),
                gate_outcome="fail",
                candidate_surface_runtime_summary={
                    "selected_surface": "solver_design",
                    "runtime_budget_diagnostic": diagnostic,
                },
            )
        )
    ).evaluate(_request())

    assert outcome.protocol_result is not None
    assert outcome.protocol_result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)
    assert outcome.protocol_result.candidate_surface_runtime_summary[
        "runtime_budget_diagnostic"
    ] == diagnostic
