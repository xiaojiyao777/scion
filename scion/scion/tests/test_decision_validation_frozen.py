"""Focused tests split from test_decision.py."""

from .decision_test_support import *  # noqa: F401,F403

def test_decision_validation_pass_to_queue_frozen():
    f = _features(stage="validation", win_rate=0.7, ci_low=0.005, ci_high=0.02)
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_FROZEN


def test_decision_validation_hierarchical_positive_to_queue_frozen():
    f = _features(
        stage="validation",
        win_rate=1.0,
        ci_low=1.0,
        ci_high=2.0,
        statistical_status="positive",
        statistical_metric="subcategory_splits",
    )
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_FROZEN
    assert "VALIDATION_PASS_HIERARCHICAL" in out.reason_codes


def test_decision_validation_runtime_tie_improvement_queues_frozen_even_if_protocol_gate_failed():
    f = _features(
        stage="validation",
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        statistical_status="tie",
        runtime_ratio_median=0.4,
        runtime_delta_median_ms=-500.0,
        runtime_pairs=8,
        protocol_gate_outcome="fail",
    )
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_FROZEN
    assert "VALIDATION_PASS_RUNTIME_TIE_IMPROVEMENT" in out.reason_codes


def test_decision_validation_fail_ci_negative():
    f = _features(stage="validation", win_rate=0.4, ci_low=-0.02, ci_high=-0.001)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON


def test_decision_validation_expand():
    f = _features(stage="validation", win_rate=0.7, ci_low=-0.005, ci_high=0.02)
    out = _engine.decide(f)
    assert out.decision == Decision.EXPAND_VALIDATION


def test_decision_validation_expand_exhausted_marginal_pass_queue_frozen():
    """T2: after val_expand (validation_expand_count >= 1), ci_low<0 AND md>=0
    → QUEUE_FROZEN (MARGINAL_PASS). md is non-negative so give frozen the
    final judgment."""
    from scion.core.models import DecisionFeatures
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="validation",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=12, win_rate=0.7, median_delta=5.0,
        ci_low=-0.01, ci_high=0.02,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        validation_expand_count=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_FROZEN
    assert "VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS" in out.reason_codes


def test_decision_validation_expand_exhausted_md_negative_abandon():
    """T2: after val_expand (validation_expand_count >= 1), ci_low<0 AND md<0
    → ABANDON (EXHAUSTED_FAIL). Triple negative signal: wr passes but ci_low<0
    AND md<0 → candidate is genuinely cost-regressive at validation layer.
    Don't burn frozen slot."""
    from scion.core.models import DecisionFeatures
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="validation",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=12, win_rate=0.7, median_delta=-800.0,
        ci_low=-0.01, ci_high=0.02,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        validation_expand_count=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "VALIDATION_EXPAND_EXHAUSTED_FAIL" in out.reason_codes


def test_decision_validation_expand_not_blocked_by_screening_expand_count():
    """T3: screening_expand_count on current candidate should NOT cause
    _decide_validation to think validation has been expanded. First validation
    eval (validation_expand_count=0) should EXPAND_VALIDATION, regardless of
    how many screening expands happened for this candidate."""
    from scion.core.models import DecisionFeatures
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="validation",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=12, win_rate=0.7, median_delta=5.0,
        ci_low=-0.01, ci_high=0.02,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        screening_expand_count=3, validation_expand_count=0,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.EXPAND_VALIDATION
    assert "VALIDATION_EXPAND" in out.reason_codes


def test_decision_frozen_promote():
    f = _features(stage="frozen", ci_low=0.005, ci_high=0.02)
    out = _engine.decide(f)
    assert out.decision == Decision.PROMOTE


def test_decision_frozen_hierarchical_positive_promotes():
    f = _features(
        stage="frozen",
        ci_low=1.0,
        ci_high=2.0,
        statistical_status="positive",
        statistical_metric="subcategory_splits",
    )
    out = _engine.decide(f)
    assert out.decision == Decision.PROMOTE
    assert "FROZEN_PASS_HIERARCHICAL" in out.reason_codes


def test_decision_frozen_runtime_tie_improvement_promotes_even_if_protocol_gate_failed():
    f = _features(
        stage="frozen",
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        statistical_status="tie",
        runtime_ratio_median=0.5,
        runtime_delta_median_ms=-250.0,
        runtime_pairs=8,
        protocol_gate_outcome="fail",
    )
    out = _engine.decide(f)
    assert out.decision == Decision.PROMOTE
    assert "FROZEN_PASS_RUNTIME_TIE_IMPROVEMENT" in out.reason_codes


def test_decision_runtime_tie_improvement_rejects_runtime_failures():
    f = _features(
        stage="frozen",
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        statistical_status="tie",
        runtime_ratio_median=0.5,
        runtime_delta_median_ms=-250.0,
        runtime_pairs=8,
        failed_pairs=1,
        protocol_gate_outcome="fail",
    )
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "INCOMPLETE_RUNTIME_EVIDENCE" in out.reason_codes


def test_decision_frozen_hierarchical_uncertain_fails_even_with_positive_legacy_ci():
    f = _features(
        stage="frozen",
        ci_low=0.005,
        ci_high=0.02,
        statistical_status="uncertain",
        statistical_metric="subcategory_splits",
    )
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "FROZEN_FAIL_HIERARCHICAL_UNCERTAIN" in out.reason_codes


def test_decision_frozen_fail():
    f = _features(stage="frozen", ci_low=-0.01, ci_high=0.005)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON


def test_decision_budget_exhausted_does_not_veto_completed_result():
    f = _features(stage="screening", budget_ratio=0.0)
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE


def test_decision_last_budget_frozen_pass_can_promote():
    f = _features(
        stage="frozen",
        ci_low=0.005,
        ci_high=0.02,
        budget_ratio=0.0,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.PROMOTE
