"""Protocol is the single owner of scientific verdicts consumed by Decision."""

import pytest

from scion.core.models import Decision

from .decision_test_support import _engine, _features


@pytest.mark.parametrize(
    ("stage", "gate_outcome", "reason_code", "expected"),
    (
        ("screening", "pass", "SCREENING_PASS", Decision.QUEUE_VALIDATE),
        ("screening", "fail", "SCREENING_FAIL_WIN_RATE", Decision.CONTINUE_EXPLORE),
        (
            "screening",
            "unclear",
            "SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT",
            Decision.CONTINUE_EXPLORE,
        ),
        ("screening", "expand", "SCREENING_EXPAND", Decision.EXPAND_SCREENING),
        ("screening", "continue", "SCREENING_FAIL_WIN_RATE", Decision.CONTINUE_EXPLORE),
        ("validation", "pass", "VALIDATION_PASS", Decision.QUEUE_FROZEN),
        ("validation", "fail", "VALIDATION_FAIL_WIN_RATE", Decision.ABANDON),
        (
            "validation",
            "unclear",
            "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
            Decision.CONTINUE_EXPLORE,
        ),
        ("validation", "expand", "VALIDATION_EXPAND", Decision.EXPAND_VALIDATION),
        (
            "validation",
            "continue",
            "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
            Decision.CONTINUE_EXPLORE,
        ),
        ("frozen", "pass", "FROZEN_PASS", Decision.PROMOTE),
        ("frozen", "fail", "FROZEN_FAIL_UNCLEAR", Decision.ABANDON),
        (
            "frozen",
            "unclear",
            "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
            Decision.CONTINUE_EXPLORE,
        ),
        ("frozen", "expand", "FROZEN_FAIL_UNCLEAR", Decision.ABANDON),
        (
            "frozen",
            "continue",
            "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
            Decision.CONTINUE_EXPLORE,
        ),
    ),
)
def test_protocol_verdict_maps_to_branch_action(
    stage,
    gate_outcome,
    reason_code,
    expected,
):
    features = _features(
        stage=stage,
        win_rate=0.01,
        median_delta=-999.0,
        ci_low=-999.0,
        ci_high=-998.0,
        runtime_ratio_median=42.0,
        runtime_regression_rate=1.0,
        protocol_gate_outcome=gate_outcome,
        protocol_reason_codes=(reason_code,),
    )

    outcome = _engine.decide(features)

    assert outcome.decision is expected
    assert outcome.reason_codes == (reason_code,)
