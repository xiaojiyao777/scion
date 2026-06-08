"""Focused tests split from test_decision.py."""

from scion.core.branch_lifecycle_policy import (
    BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
)

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


def test_decision_candidate_runtime_failure_preempts_lifecycle_policy():
    class ExplodingLifecyclePolicy:
        def decide(self, *_args, **_kwargs):
            raise AssertionError("lifecycle policy should not run")

        def evidence_metadata(self, *_args, **_kwargs):
            raise AssertionError("lifecycle evidence should not be requested")

    engine = DecisionEngine(_cfg, lifecycle_policy=ExplodingLifecyclePolicy())
    f = _features(
        stage="screening",
        win_rate=0.0,
        median_delta=0.0,
        candidate_failed_pairs=1,
    )

    out = engine.decide(f)

    assert out.decision == Decision.ABANDON
    assert out.reason_codes == ("CANDIDATE_RUNTIME_FAILURE",)
    assert out.decision_layer_source == "stage_decision"


def test_decision_screening_champion_partial_evidence_blocks_validation_queue():
    f = _features(
        stage="screening",
        win_rate=1.0,
        median_delta=100.0,
        failed_pairs=1,
        champion_failed_pairs=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE
    assert out.reason_codes == ("SCREENING_PARTIAL_CHAMPION_EVIDENCE",)


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


def test_decision_screening_high_win_positive_effect_queues_validation():
    f = _features(stage="screening", win_rate=0.7, median_delta=0.01)
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_PASS" in out.reason_codes


def test_decision_lifecycle_archive_abandon_has_structured_fields():
    f = _features(
        stage="screening",
        win_rate=0.4,
        median_delta=-0.01,
        ci_low=-0.02,
        ci_high=0.01,
    )

    out = _engine.decide(f)

    assert out.stage_decision == Decision.CONTINUE_EXPLORE
    assert out.decision == Decision.ABANDON
    assert out.final_decision == Decision.ABANDON
    assert out.lifecycle_action == "archive_lineage"
    assert out.lifecycle_reason_codes == (
        BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
        "SCREENING_SOFT_ABANDON_NEGATIVE_DELTA",
    )
    assert out.decision_layer_source == "stage_decision"
    assert out.lifecycle_policy_evidence["bookkeeping_role"] == (
        "screening_result_lifecycle_annotation"
    )
    assert out.lifecycle_policy_evidence["legacy_decision_layer_source"] == (
        "lifecycle_policy"
    )


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


def test_decision_runtime_tie_fresh_required_continues_without_promotion():
    f = _features(
        stage="screening",
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        runtime_pairs=0,
        runtime_evidence_status="fresh_champion_required",
    )
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE
    assert out.reason_codes == ("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",)


def test_decision_screening_low_win_positive_effect_expands_screening():
    f = _features(stage="screening", win_rate=0.55, median_delta=0.01)
    out = _engine.decide(f)
    assert out.decision == Decision.EXPAND_SCREENING
    assert "SCREENING_EXPAND" in out.reason_codes


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


def test_decision_screening_high_win_negative_effect_does_not_queue_validation():
    """wr >= threshold but md < 0 stays in exploration by default."""
    f = _features(stage="screening", win_rate=0.7, median_delta=-1000.0)
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT" in out.reason_codes
    assert all("PASS" not in reason for reason in out.reason_codes)


def test_decision_screening_high_win_negative_effect_ignores_screening_expand_count():
    """The high-win negative-effect decision is not an expand retry path."""
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
    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT" in out.reason_codes
    assert all("PASS" not in reason for reason in out.reason_codes)


def test_decision_screening_high_win_negative_effect_ignores_validation_expand_count():
    """Validation expand history cannot promote a negative-effect screening result."""
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
    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT" in out.reason_codes
    assert all("PASS" not in reason for reason in out.reason_codes)
