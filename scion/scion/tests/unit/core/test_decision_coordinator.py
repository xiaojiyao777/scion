from __future__ import annotations

from scion.config.problem import ProtocolConfig
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.models import Decision, DecisionFeatures, DecisionOutcome


def _features(**overrides) -> DecisionFeatures:
    data = {
        "hypothesis_action": "modify",
        "stage": "screening",
        "contract_passed": True,
        "verification_passed": True,
        "canary_passed": True,
        "n_cases": 6,
        "win_rate": 0.7,
        "median_delta": 0.02,
        "ci_low": None,
        "ci_high": None,
        "stale": False,
        "recent_failure_codes": (),
        "runtime_ratio_median": 1.25,
        "runtime_delta_median_ms": 20.0,
        "runtime_regression_rate": 0.5,
        "runtime_pairs": 4,
        "protocol_gate_outcome": "pass",
        "protocol_reason_codes": ("SCREENING_PASS",),
    }
    data.update(overrides)
    return DecisionFeatures(**data)


def test_coordinator_returns_formal_decision_reason_codes_and_rule() -> None:
    result = DecisionCoordinator(config=ProtocolConfig()).decide(_features())
    assert result.decision is Decision.QUEUE_VALIDATE
    assert result.reason_codes == ("SCREENING_PASS",)
    assert result.rule == "screening:SCREENING_PASS->queue_validate"


def test_coordinator_normalizes_empty_reason_codes() -> None:
    class EmptyReasonEngine:
        def decide(self, features: DecisionFeatures) -> DecisionOutcome:
            return DecisionOutcome(
                decision=Decision.CONTINUE_EXPLORE,
                reason_codes=(),
            )

    result = DecisionCoordinator(engine=EmptyReasonEngine()).decide(  # type: ignore[arg-type]
        _features(win_rate=None, median_delta=None)
    )
    assert result.reason_codes == ("CONTINUE_EXPLORE_NO_REASON",)


def test_runtime_regression_is_a_formal_abandon() -> None:
    result = DecisionCoordinator(config=ProtocolConfig()).decide(
        _features(
            stage="frozen",
            win_rate=1.0,
            ci_low=0.01,
            ci_high=0.02,
            runtime_ratio_median=3.0,
            protocol_gate_outcome="fail",
            protocol_reason_codes=("RUNTIME_REGRESSION",),
        )
    )
    assert result.decision is Decision.ABANDON
    assert result.reason_codes == ("RUNTIME_REGRESSION",)
