"""Later-stage hard-safety behavior at the Decision boundary."""

import pytest

from .decision_test_support import *  # noqa: F401,F403


@pytest.mark.parametrize("stage", ("validation", "frozen"))
def test_incomplete_later_stage_runtime_evidence_overrides_protocol_pass(stage):
    features = _features(
        stage=stage,
        protocol_gate_outcome="pass",
        protocol_reason_codes=(
            "VALIDATION_PASS" if stage == "validation" else "FROZEN_PASS",
        ),
        failed_pairs=1,
    )

    outcome = _engine.decide(features)

    assert outcome.decision is Decision.ABANDON
    assert outcome.reason_codes == ("INCOMPLETE_RUNTIME_EVIDENCE",)


@pytest.mark.parametrize(
    ("stage", "decision", "reason_code"),
    (
        ("validation", Decision.QUEUE_FROZEN, "VALIDATION_PASS"),
        ("frozen", Decision.PROMOTE, "FROZEN_PASS"),
    ),
)
def test_decision_does_not_recompute_later_stage_science(
    stage,
    decision,
    reason_code,
):
    features = _features(
        stage=stage,
        win_rate=0.0,
        median_delta=-1000.0,
        ci_low=-1000.0,
        ci_high=-500.0,
        statistical_status="negative",
        runtime_ratio_median=99.0,
        runtime_regression_rate=1.0,
        protocol_gate_outcome="pass",
        protocol_reason_codes=(reason_code,),
    )

    outcome = _engine.decide(features)

    assert outcome.decision is decision
    assert outcome.reason_codes == (reason_code,)


@pytest.mark.parametrize("stage", ("validation", "frozen"))
def test_missing_later_stage_protocol_verdict_fails_closed(stage):
    outcome = _engine.decide(_features(stage=stage, protocol_gate_outcome=None))

    assert outcome.decision is Decision.ABANDON
    assert outcome.reason_codes == ("MISSING_PROTOCOL_GATE_OUTCOME",)
