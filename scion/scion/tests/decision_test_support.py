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
    statistical_status=None,
    statistical_metric=None,
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
        statistical_status=statistical_status,
        statistical_metric=statistical_metric,
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

















# ─────────────────────────────────────────────────────────────────────────────
# _validate_no_free_text
# ─────────────────────────────────────────────────────────────────────────────







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
    runtime_delta_median_ms=None,
    runtime_pairs: int = 0,
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
        runtime_delta_median_ms=runtime_delta_median_ms,
        runtime_pairs=runtime_pairs,
        failed_pairs=failed_pairs,
        candidate_failed_pairs=candidate_failed_pairs,
        protocol_gate_outcome=protocol_gate_outcome,
    )


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
