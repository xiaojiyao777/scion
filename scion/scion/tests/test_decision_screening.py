"""Focused tests split from test_decision.py."""

from .decision_test_support import *  # noqa: F401,F403

def test_decision_contract_fail():
    f = _features(contract_passed=False)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "CONTRACT_FAILED" in out.reason_codes


def test_decision_verification_fail():
    f = _features(verification_passed=False)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON


def test_decision_canary_fail():
    f = _features(canary_passed=False)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON


def test_decision_runtime_guard_timeout_vetoes_candidate():
    f = _features(runtime_guard_passed=False, runtime_guard_timeout=True)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "RUNTIME_GUARD_TIMEOUT" in out.reason_codes


def test_decision_candidate_runtime_failure_vetoes_objective_win():
    f = _features(
        stage="screening",
        win_rate=1.0,
        median_delta=100.0,
        candidate_failed_pairs=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "CANDIDATE_RUNTIME_FAILURE" in out.reason_codes


def test_decision_runtime_regression_vetoes_objective_win():
    f = _features(
        stage="frozen",
        ci_low=10.0,
        ci_high=20.0,
        protocol_gate_outcome="pass",
        runtime_ratio_median=2.5,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "RUNTIME_REGRESSION" in out.reason_codes


def test_decision_runtime_regression_threshold_comes_from_protocol_config():
    f = _features(
        stage="frozen",
        ci_low=10.0,
        ci_high=20.0,
        protocol_gate_outcome="pass",
        runtime_ratio_median=2.5,
    )
    engine = DecisionEngine(ProtocolConfig(runtime={"max_runtime_ratio": 3.0}))
    out = engine.decide(f)
    assert out.decision == Decision.PROMOTE
    assert "FROZEN_PASS" in out.reason_codes


def test_decision_frozen_protocol_gate_fail_cannot_promote():
    f = _features(
        stage="frozen",
        ci_low=10.0,
        ci_high=20.0,
        protocol_gate_outcome="fail",
    )
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "FROZEN_PROTOCOL_GATE_NOT_PASS" in out.reason_codes


def test_decision_screening_pass_to_queue_validate():
    f = _features(stage="screening", win_rate=0.7, median_delta=0.01)
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_VALIDATE


def test_decision_screening_fail():
    f = _features(stage="screening", win_rate=0.3, median_delta=0.01)
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE


def test_decision_screening_runtime_tie_improvement_queues_validation():
    f = _features(
        stage="screening",
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        runtime_ratio_median=0.25,
        runtime_delta_median_ms=-1000.0,
        runtime_pairs=4,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_PASS_RUNTIME_TIE_IMPROVEMENT" in out.reason_codes


def test_decision_screening_expand():
    f = _features(stage="screening", win_rate=0.55, median_delta=0.01)
    out = _engine.decide(f)
    assert out.decision == Decision.EXPAND_SCREENING


def test_decision_screening_expand_exhausted_borderline_positive_delta():
    """wr in [threshold-0.05, threshold) with md>=0 after 1 screening expand → queue_validate."""
    from scion.core.models import DecisionFeatures
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=10, win_rate=0.63, median_delta=100.0,
        ci_low=None, ci_high=None,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0, screening_expand_count=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_EXPAND_EXHAUSTED_BORDERLINE" in out.reason_codes


def test_decision_screening_expand_exhausted_borderline_negative_delta():
    """wr in [threshold-0.05, threshold) with md<0 after 1 screening expand → continue_explore.
    Cost-regressive candidates must not leak through BORDERLINE path."""
    from scion.core.models import DecisionFeatures
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=10, win_rate=0.63, median_delta=-1200.0,
        ci_low=None, ci_high=None,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0, screening_expand_count=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA" in out.reason_codes


def test_decision_screening_pass_negative_delta_queues_validation():
    """wr >= threshold but md < 0 → queue_validate (v3 lex-order: splits-better candidate,
    validation's bootstrap CI on diverse cases is the authoritative judge)."""
    f = _features(stage="screening", win_rate=0.7, median_delta=-1000.0)
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_PASS_NEGATIVE_DELTA" in out.reason_codes


def test_decision_screening_pass_negative_delta_unaffected_by_screening_expand():
    """T1: SPND no longer has expand_count cap. A prior screening_expand on the
    same candidate (or leaked from the same branch pre-T3) must NOT block SPND
    from QUEUE_VALIDATE. Per v3, screening_expand_count and the SPND decision
    are independent concerns."""
    from scion.core.models import DecisionFeatures
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=10, win_rate=0.7, median_delta=-1500.0,
        ci_low=None, ci_high=None,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0, screening_expand_count=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_PASS_NEGATIVE_DELTA" in out.reason_codes


def test_decision_screening_pass_negative_delta_unaffected_by_validation_expand_count():
    """T3: validation_expand_count leaking from a prior candidate must NOT affect
    SPND decision on the current candidate (this was the cross-stage counter leak
    that caused sonnet s11 to 0-promote in the 2026-04-24 F experiment)."""
    from scion.core.models import DecisionFeatures
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=10, win_rate=0.7, median_delta=-1500.0,
        ci_low=None, ci_high=None,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        screening_expand_count=0, validation_expand_count=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_PASS_NEGATIVE_DELTA" in out.reason_codes
