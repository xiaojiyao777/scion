"""Hard-safety behavior at the Decision boundary."""

import pytest

from .decision_test_support import *  # noqa: F401,F403


@pytest.mark.parametrize(
    ("overrides", "reason_code"),
    (
        ({"contract_passed": False}, "CONTRACT_FAILED"),
        ({"verification_passed": False}, "VERIFICATION_FAILED"),
        ({"canary_passed": False}, "CANARY_FAILED"),
        (
            {"runtime_guard_passed": False, "runtime_guard_timeout": True},
            "RUNTIME_GUARD_TIMEOUT",
        ),
        ({"runtime_guard_passed": False}, "RUNTIME_GUARD_FAILED"),
        ({"candidate_failed_pairs": 1}, "CANDIDATE_RUNTIME_FAILURE"),
    ),
)
def test_decision_hard_safety_flags_override_protocol_pass(overrides, reason_code):
    features = _features(
        protocol_gate_outcome="pass",
        protocol_reason_codes=("SCREENING_PASS",),
        **overrides,
    )

    outcome = _engine.decide(features)

    assert outcome.decision is Decision.ABANDON
    assert outcome.reason_codes == (reason_code,)


def test_screening_partial_champion_evidence_blocks_validation_queue():
    features = _features(
        protocol_gate_outcome="pass",
        protocol_reason_codes=("SCREENING_PASS",),
        failed_pairs=1,
        champion_failed_pairs=1,
    )

    outcome = _engine.decide(features)

    assert outcome.decision is Decision.CONTINUE_EXPLORE
    assert outcome.reason_codes == ("SCREENING_PARTIAL_CHAMPION_EVIDENCE",)


def test_bilateral_pair_failure_is_not_candidate_only_evidence():
    features = _features(
        protocol_gate_outcome="pass",
        protocol_reason_codes=("SCREENING_PARTIAL_CHAMPION_EVIDENCE",),
        failed_pairs=1,
        candidate_failed_pairs=1,
        champion_failed_pairs=1,
        bilateral_failed_pairs=1,
    )

    outcome = _engine.decide(features)

    assert outcome.decision is Decision.CONTINUE_EXPLORE
    assert outcome.reason_codes == ("SCREENING_PARTIAL_CHAMPION_EVIDENCE",)


def test_separate_candidate_failure_remains_hard_with_bilateral_failure():
    features = _features(
        protocol_gate_outcome="unclear",
        protocol_reason_codes=("SCREENING_PARTIAL_CHAMPION_EVIDENCE",),
        failed_pairs=2,
        candidate_failed_pairs=2,
        champion_failed_pairs=1,
        bilateral_failed_pairs=1,
    )

    outcome = _engine.decide(features)

    assert outcome.decision is Decision.ABANDON
    assert outcome.reason_codes == ("CANDIDATE_RUNTIME_FAILURE",)


def test_decision_does_not_recompute_screening_science_from_aggregates():
    features = _features(
        win_rate=0.0,
        median_delta=-1000.0,
        ci_low=-1000.0,
        ci_high=-500.0,
        runtime_ratio_median=99.0,
        runtime_regression_rate=1.0,
        protocol_gate_outcome="pass",
        protocol_reason_codes=("SCREENING_PASS",),
    )

    outcome = _engine.decide(features)

    assert outcome.decision is Decision.QUEUE_VALIDATE
    assert outcome.reason_codes == ("SCREENING_PASS",)


def test_missing_screening_protocol_verdict_fails_closed_to_exploration():
    outcome = _engine.decide(_features(protocol_gate_outcome=None))

    assert outcome.decision is Decision.CONTINUE_EXPLORE
    assert outcome.reason_codes == ("MISSING_PROTOCOL_GATE_OUTCOME",)
