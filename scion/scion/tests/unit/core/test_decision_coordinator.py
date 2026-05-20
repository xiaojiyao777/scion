from __future__ import annotations

import uuid

from scion.config.problem import ProtocolConfig
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.models import Decision, DecisionFeatures, DecisionOutcome


def _features(**overrides) -> DecisionFeatures:
    data = {
        "branch_id": str(uuid.uuid4()),
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
        "recent_retry_count": 0,
        "recent_failure_codes": (),
        "budget_remaining_ratio": 1.0,
        "runtime_ratio_median": 1.25,
        "runtime_delta_median_ms": 20.0,
        "runtime_regression_rate": 0.5,
        "runtime_pairs": 4,
    }
    data.update(overrides)
    return DecisionFeatures(**data)


def test_decision_coordinator_returns_engine_decision_reason_codes_and_rule() -> None:
    coordinator = DecisionCoordinator(config=ProtocolConfig())

    result = coordinator.decide(_features())

    assert result.decision == Decision.QUEUE_VALIDATE
    assert result.reason_codes == ("SCREENING_PASS",)
    assert result.rule == "screening:SCREENING_PASS->queue_validate"
    assert result.features_snapshot.runtime_ratio_median == 1.25


def test_decision_coordinator_normalizes_empty_reason_codes() -> None:
    class EmptyReasonEngine:
        def decide(self, features: DecisionFeatures) -> DecisionOutcome:
            return DecisionOutcome(
                decision=Decision.CONTINUE_EXPLORE,
                reason_codes=(),
                features_snapshot=features,
            )

    coordinator = DecisionCoordinator(engine=EmptyReasonEngine())  # type: ignore[arg-type]

    result = coordinator.decide(_features(win_rate=None, median_delta=None))

    assert result.reason_codes == ("CONTINUE_EXPLORE_NO_REASON",)
    assert result.rule == "screening:CONTINUE_EXPLORE_NO_REASON->continue_explore"


def test_telemetry_validation_repairable_preempts_win_rate_abandon() -> None:
    coordinator = DecisionCoordinator(config=ProtocolConfig())

    result = coordinator.decide(
        _features(
            win_rate=0.0,
            median_delta=0.0,
            telemetry_validation_repairable=True,
            telemetry_guard_failed=True,
        )
    )

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert result.reason_codes == ("TELEMETRY_VALIDATION_REPAIRABLE",)
    assert "SCREENING_FAIL_WIN_RATE" not in result.reason_codes
