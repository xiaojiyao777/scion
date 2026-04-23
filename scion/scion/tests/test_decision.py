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
) -> ProtocolResult:
    stats = EvalStats(
        n_cases=10, wins=7, losses=2, ties=1,
        win_rate=win_rate, median_delta=median_delta,
        ci_low=ci_low, ci_high=ci_high,
    )
    return ProtocolResult(
        stage=stage,
        stats=stats,
        gate_outcome="pass",
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


def test_decision_screening_pass_negative_delta_queues_validation():
    """wr >= threshold but md < 0 → queue_validate (not expand, to avoid dead loop)."""
    f = _features(stage="screening", win_rate=0.7, median_delta=-1000.0)
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_PASS_NEGATIVE_DELTA" in out.reason_codes


def test_decision_validation_pass_to_queue_frozen():
    f = _features(stage="validation", win_rate=0.7, ci_low=0.005, ci_high=0.02)
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_FROZEN


def test_decision_validation_fail_ci_negative():
    f = _features(stage="validation", win_rate=0.4, ci_low=-0.02, ci_high=-0.001)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON


def test_decision_validation_expand():
    f = _features(stage="validation", win_rate=0.7, ci_low=-0.005, ci_high=0.02)
    out = _engine.decide(f)
    assert out.decision == Decision.EXPAND_VALIDATION


def test_decision_frozen_promote():
    f = _features(stage="frozen", ci_low=0.005, ci_high=0.02)
    out = _engine.decide(f)
    assert out.decision == Decision.PROMOTE


def test_decision_frozen_fail():
    f = _features(stage="frozen", ci_low=-0.01, ci_high=0.005)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON


def test_decision_budget_exhausted():
    f = _features(stage="screening", budget_ratio=0.0)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
