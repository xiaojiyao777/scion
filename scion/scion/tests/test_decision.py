"""Tests for scion/core/features.py and scion/core/decision.py."""
from __future__ import annotations
import uuid
import pytest

from scion.core.models import (
    Branch, BranchState, ContractResult, VerificationResult, CanaryResult,
    ProtocolResult, ExperimentStage, EvalStats, Decision, CheckResult,
)
from scion.config.problem import ProtocolConfig
from scion.core.features import (
    SafeFeatureExtractor, BudgetState, DecisionInputGuardError, _validate_no_free_text,
)
from scion.core.decision import DecisionEngine


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _branch(state: BranchState = BranchState.EXPLORE, retry: int = 0) -> Branch:
    return Branch(
        branch_id=str(uuid.uuid4()),
        state=state,
        base_champion_id=0,
        base_champion_hash="h",
        retry_count=retry,
    )


def _contract(passed: bool = True) -> ContractResult:
    return ContractResult(passed=passed, checks=(), failure_reason=None)


def _verification(passed: bool = True) -> VerificationResult:
    return VerificationResult(passed=passed, checks=(), failure_severity=None, first_failure=None)


def _canary(passed: bool = True) -> CanaryResult:
    return CanaryResult(passed=passed, reason=None)


def _protocol(
    win_rate: float = 0.7,
    median_delta: float = 0.01,
    ci_low: float = 0.005,
    ci_high: float = 0.02,
    stage: ExperimentStage = ExperimentStage.SCREENING,
    runtime_ratio_median=None,
    runtime_delta_median_ms=None,
    runtime_regression_rate=None,
    runtime_pairs: int = 0,
    total_pairs: int = 0,
    attempted_pairs: int = 0,
    valid_pairs: int = 0,
    failed_pairs: int = 0,
    candidate_failed_pairs: int = 0,
    champion_failed_pairs: int = 0,
    gate_outcome: str = "pass",
) -> ProtocolResult:
    stats = EvalStats(
        n_cases=10, wins=7, losses=2, ties=1,
        win_rate=win_rate, median_delta=median_delta,
        ci_low=ci_low, ci_high=ci_high,
        runtime_ratio_median=runtime_ratio_median,
        runtime_delta_median_ms=runtime_delta_median_ms,
        runtime_regression_rate=runtime_regression_rate,
        runtime_pairs=runtime_pairs,
        total_pairs=total_pairs,
        attempted_pairs=attempted_pairs,
        valid_pairs=valid_pairs,
        failed_pairs=failed_pairs,
        candidate_failed_pairs=candidate_failed_pairs,
        champion_failed_pairs=champion_failed_pairs,
    )
    return ProtocolResult(
        stage=stage,
        stats=stats,
        gate_outcome=gate_outcome,  # type: ignore[arg-type]
        reason_codes=("SCREENING_PASS",),
        exposed_summary="ok",
        raw_metrics_ref="/tmp/m.json",
    )


_extractor = SafeFeatureExtractor()
_cfg = ProtocolConfig()
_engine = DecisionEngine(_cfg)


# ─────────────────────────────────────────────────────────────────────────────
# SafeFeatureExtractor
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_basic():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=_protocol(),
        budget=BudgetState(total=100, used=10),
    )
    assert features.contract_passed is True
    assert features.verification_passed is True
    assert features.canary_passed is True
    assert features.win_rate == pytest.approx(0.7)
    assert features.stage == "screening"
    assert features.budget_remaining_ratio == pytest.approx(0.9)


def test_extract_no_protocol():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
        budget=BudgetState(total=100, used=0),
    )
    assert features.win_rate is None
    assert features.n_cases == 0


def test_extract_stale_flag():
    branch = _branch(state=BranchState.STALE)
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
        budget=BudgetState(total=100, used=0),
    )
    assert features.stale is True


def test_extract_validation_stage():
    branch = _branch(state=BranchState.VALIDATING)
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=_protocol(stage=ExperimentStage.VALIDATION),
        budget=BudgetState(total=100, used=0),
    )
    assert features.stage == "validation"


def test_extract_expand_counters_propagate():
    """T3: SafeFeatureExtractor must copy stage-aware expand counters from
    Branch to DecisionFeatures so decision rules can use them."""
    branch = _branch()
    branch.screening_expand_count = 2
    branch.validation_expand_count = 1
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
        budget=BudgetState(total=100, used=0),
    )
    assert features.screening_expand_count == 2
    assert features.validation_expand_count == 1


def test_extract_runtime_guard_facts_without_free_text():
    branch = _branch()
    verification = VerificationResult(
        passed=True,
        checks=(
            CheckResult(
                "V9_perf_guard",
                True,
                "heavy",
                "perf ok",
                3,
                metadata={
                    "ratio": 1.25,
                    "candidate_timeout": False,
                    "case_id": "case-a",
                },
            ),
        ),
    )
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=verification,
        canary=_canary(),
        protocol=None,
        budget=BudgetState(total=100, used=0),
    )
    assert features.runtime_guard_passed is True
    assert features.runtime_guard_ratio == pytest.approx(1.25)
    assert features.runtime_guard_timeout is False
    _validate_no_free_text(features)


def test_extract_protocol_runtime_facts_without_free_text():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=_protocol(
            runtime_ratio_median=1.42,
            runtime_delta_median_ms=37.5,
            runtime_regression_rate=0.75,
            runtime_pairs=8,
            total_pairs=10,
            attempted_pairs=10,
            valid_pairs=8,
            failed_pairs=2,
            candidate_failed_pairs=1,
            champion_failed_pairs=1,
        ),
        budget=BudgetState(total=100, used=0),
    )
    assert features.runtime_ratio_median == pytest.approx(1.42)
    assert features.runtime_delta_median_ms == pytest.approx(37.5)
    assert features.runtime_regression_rate == pytest.approx(0.75)
    assert features.runtime_pairs == 8
    assert features.protocol_gate_outcome == "pass"
    assert features.total_pairs == 10
    assert features.valid_pairs == 8
    assert features.failed_pairs == 2
    assert features.candidate_failed_pairs == 1
    assert features.champion_failed_pairs == 1
    _validate_no_free_text(features)


def test_extract_legacy_continue_protocol_gate_outcome():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=_protocol(win_rate=0.3, gate_outcome="continue"),
        budget=BudgetState(total=100, used=0),
    )
    assert features.protocol_gate_outcome == "continue"
    _validate_no_free_text(features)


# ─────────────────────────────────────────────────────────────────────────────
# _validate_no_free_text
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_no_free_text_valid():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
        budget=BudgetState(total=100, used=0),
    )
    # Should not raise
    _validate_no_free_text(features)


def test_validate_invalid_uuid_raises():
    from scion.core.models import DecisionFeatures
    import dataclasses
    features = DecisionFeatures(
        branch_id="not-a-uuid",
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=0,
        win_rate=None,
        median_delta=None,
        ci_low=None,
        ci_high=None,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0,
    )
    with pytest.raises(DecisionInputGuardError):
        _validate_no_free_text(features)


def test_validate_unknown_failure_code_raises():
    from scion.core.models import DecisionFeatures
    features = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=0,
        win_rate=None,
        median_delta=None,
        ci_low=None,
        ci_high=None,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=("FREE_TEXT_FAILURE_REASON",),
        budget_remaining_ratio=1.0,
    )
    with pytest.raises(DecisionInputGuardError):
        _validate_no_free_text(features)


# ─────────────────────────────────────────────────────────────────────────────
# DecisionEngine
# ─────────────────────────────────────────────────────────────────────────────

def _make_features(
    stage: str = "screening",
    contract_passed: bool = True,
    verification_passed: bool = True,
    canary_passed: bool = True,
    win_rate: float = None,
    median_delta: float = None,
    ci_low: float = None,
    ci_high: float = None,
    budget_remaining_ratio: float = 1.0,
):
    return DecisionEngine.__new__(DecisionEngine)  # won't use this


def _features(
    stage: str = "screening",
    contract_passed: bool = True,
    verification_passed: bool = True,
    canary_passed: bool = True,
    win_rate=None,
    median_delta=None,
    ci_low=None,
    ci_high=None,
    budget_ratio: float = 1.0,
    branch_id: str = None,
    statistical_status=None,
    statistical_metric=None,
    runtime_guard_passed=None,
    runtime_guard_timeout=False,
    runtime_ratio_median=None,
    failed_pairs: int = 0,
    candidate_failed_pairs: int = 0,
    protocol_gate_outcome=None,
):
    from scion.core.models import DecisionFeatures
    return DecisionFeatures(
        branch_id=branch_id or str(uuid.uuid4()),
        hypothesis_action="modify",
        stage=stage,
        contract_passed=contract_passed,
        verification_passed=verification_passed,
        canary_passed=canary_passed,
        n_cases=10,
        win_rate=win_rate,
        median_delta=median_delta,
        ci_low=ci_low,
        ci_high=ci_high,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=budget_ratio,
        statistical_status=statistical_status,
        statistical_metric=statistical_metric,
        runtime_guard_passed=runtime_guard_passed,
        runtime_guard_timeout=runtime_guard_timeout,
        runtime_ratio_median=runtime_ratio_median,
        failed_pairs=failed_pairs,
        candidate_failed_pairs=candidate_failed_pairs,
        protocol_gate_outcome=protocol_gate_outcome,
    )


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
