from __future__ import annotations
import re
from dataclasses import dataclass
from math import isfinite
from typing import Optional, Tuple

from scion.core.models import (
    Branch, BranchState, ContractResult, VerificationResult,
    CanaryResult, ProtocolResult, DecisionFeatures,
)
from scion.core.telemetry_validation import (
    is_repairable_telemetry_validation_failure,
    telemetry_guard_summary,
)


# Failure taxonomy — two layers, both allowed in branch.failure_codes / DecisionFeatures.
#
# Layer 1: raw failure category (what pipeline stage the failure happened in).
# These are what campaign._handle_failure pushes (uppercased from FailureEvent.category).
_RAW_CATEGORIES = frozenset({
    "PROPOSAL", "CONTRACT",
    "VERIFICATION_LIGHT", "VERIFICATION_HEAVY",
    "EVALUATION", "INFRA", "SEARCH_GUIDANCE",
})
# Layer 2: normalized check / outcome codes. Used by some legacy lineage paths
# and by protocol outcomes. Kept for backward compatibility — v0.3 doesn't push
# these from _handle_failure, but lineage_store / tests may carry them.
_NORMALIZED_CODES = frozenset({
    "SYNTAX", "INTERFACE", "UNIT_TEST", "REGRESSION",
    "FEASIBILITY", "OBJECTIVE", "SOLUTION_CONSISTENCY", "STATE_LEAK",
    "WALL_CLOCK", "NONDETERMINISM",
    "CANARY_FAIL", "SCREENING_FAIL", "VALIDATION_FAIL", "FROZEN_FAIL",
})
KNOWN_FAILURE_CODES = _RAW_CATEGORIES | _NORMALIZED_CODES

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


class DecisionInputGuardError(Exception):
    pass


@dataclass
class BudgetState:
    total: int
    used: int

    @property
    def remaining_ratio(self) -> float:
        if self.total <= 0:
            return 0.0
        return max(0.0, (self.total - self.used) / self.total)


def _branch_state_to_stage(state: BranchState) -> str:
    if state in (BranchState.VALIDATING, BranchState.VALIDATING_EXPAND):
        return "validation"
    elif state == BranchState.FROZEN_TESTING:
        return "frozen"
    return "screening"


class SafeFeatureExtractor:
    def extract(
        self,
        branch: Branch,
        hypothesis_action: str,
        contract: ContractResult,
        verification: VerificationResult,
        canary: CanaryResult,
        protocol: Optional[ProtocolResult],
        budget: BudgetState,
    ) -> DecisionFeatures:
        """
        Extract DecisionFeatures from raw stage results.
        All fields are numeric/enum — no free text.
        """
        stage = _branch_state_to_stage(branch.state)

        win_rate: Optional[float] = None
        median_delta: Optional[float] = None
        ci_low: Optional[float] = None
        ci_high: Optional[float] = None
        statistical_status = None
        statistical_metric = None
        runtime_ratio_median: Optional[float] = None
        runtime_delta_median_ms: Optional[float] = None
        runtime_regression_rate: Optional[float] = None
        runtime_pairs = 0
        protocol_gate_outcome = None
        total_pairs = 0
        attempted_pairs = 0
        valid_pairs = 0
        failed_pairs = 0
        candidate_failed_pairs = 0
        champion_failed_pairs = 0
        n_cases = 0

        if protocol is not None:
            stats = protocol.stats
            n_cases = stats.n_cases
            protocol_gate_outcome = protocol.gate_outcome
            win_rate = stats.win_rate
            median_delta = stats.median_delta
            ci_low = stats.ci_low
            ci_high = stats.ci_high
            statistical_status = stats.statistical_status
            statistical_metric = stats.statistical_metric
            runtime_ratio_median = stats.runtime_ratio_median
            runtime_delta_median_ms = stats.runtime_delta_median_ms
            runtime_regression_rate = stats.runtime_regression_rate
            runtime_pairs = stats.runtime_pairs
            total_pairs = stats.total_pairs
            attempted_pairs = stats.attempted_pairs
            valid_pairs = stats.valid_pairs
            failed_pairs = stats.failed_pairs
            candidate_failed_pairs = stats.candidate_failed_pairs
            champion_failed_pairs = stats.champion_failed_pairs

        recent_failure_codes: Tuple[str, ...] = tuple(
            c for c in branch.failure_codes if c in KNOWN_FAILURE_CODES
        )
        runtime_guard_passed, runtime_guard_ratio, runtime_guard_timeout = (
            _extract_runtime_guard(verification)
        )
        telemetry_guard = telemetry_guard_summary(protocol)

        features = DecisionFeatures(
            branch_id=branch.branch_id,
            hypothesis_action=hypothesis_action,  # type: ignore[arg-type]
            stage=stage,  # type: ignore[arg-type]
            contract_passed=contract.passed,
            verification_passed=verification.passed,
            canary_passed=canary.passed,
            n_cases=n_cases,
            win_rate=win_rate,
            median_delta=median_delta,
            ci_low=ci_low,
            ci_high=ci_high,
            statistical_status=statistical_status,
            statistical_metric=statistical_metric,
            stale=branch.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE),
            recent_retry_count=branch.retry_count,
            screening_expand_count=branch.screening_expand_count,
            validation_expand_count=branch.validation_expand_count,
            recent_failure_codes=recent_failure_codes,
            budget_remaining_ratio=budget.remaining_ratio,
            runtime_guard_passed=runtime_guard_passed,
            runtime_guard_ratio=runtime_guard_ratio,
            runtime_guard_timeout=runtime_guard_timeout,
            runtime_ratio_median=runtime_ratio_median,
            runtime_delta_median_ms=runtime_delta_median_ms,
            runtime_regression_rate=runtime_regression_rate,
            runtime_pairs=runtime_pairs,
            protocol_gate_outcome=protocol_gate_outcome,  # type: ignore[arg-type]
            total_pairs=total_pairs,
            attempted_pairs=attempted_pairs,
            valid_pairs=valid_pairs,
            failed_pairs=failed_pairs,
            candidate_failed_pairs=candidate_failed_pairs,
            champion_failed_pairs=champion_failed_pairs,
            telemetry_validation_repairable=(
                is_repairable_telemetry_validation_failure(protocol)
            ),
            telemetry_guard_failed=(
                telemetry_guard is not None and bool(telemetry_guard.get("passed")) is False
            ),
        )

        _validate_no_free_text(features)
        return features


def _validate_no_free_text(features: DecisionFeatures) -> None:
    """
    Runtime invariant: DecisionFeatures must not carry free text.
    Raises DecisionInputGuardError if violated.
    """
    if not _UUID_RE.match(features.branch_id):
        raise DecisionInputGuardError(
            f"branch_id is not a valid UUID: {features.branch_id!r}"
        )
    if features.hypothesis_action not in ("modify", "create_new", "remove"):
        raise DecisionInputGuardError(
            f"hypothesis_action is not a known enum: {features.hypothesis_action!r}"
        )
    if features.stage not in ("screening", "validation", "frozen"):
        raise DecisionInputGuardError(
            f"stage is not a known enum: {features.stage!r}"
        )
    if features.protocol_gate_outcome is not None and features.protocol_gate_outcome not in (
        "pass",
        "fail",
        "unclear",
        "expand",
        "continue",
    ):
        raise DecisionInputGuardError(
            f"protocol_gate_outcome is not a known enum: {features.protocol_gate_outcome!r}"
        )
    for code in features.recent_failure_codes:
        if code not in KNOWN_FAILURE_CODES:
            raise DecisionInputGuardError(
                f"Unknown failure code in recent_failure_codes: {code!r}"
            )
    if features.runtime_guard_ratio is not None:
        if features.runtime_guard_ratio < 0 or not isfinite(features.runtime_guard_ratio):
            raise DecisionInputGuardError(
                "runtime_guard_ratio must be finite and non-negative: "
                f"{features.runtime_guard_ratio!r}"
            )
    if features.runtime_ratio_median is not None:
        if features.runtime_ratio_median < 0 or not isfinite(features.runtime_ratio_median):
            raise DecisionInputGuardError(
                "runtime_ratio_median must be finite and non-negative: "
                f"{features.runtime_ratio_median!r}"
            )
    if features.runtime_delta_median_ms is not None and not isfinite(
        features.runtime_delta_median_ms
    ):
        raise DecisionInputGuardError(
            "runtime_delta_median_ms must be finite: "
            f"{features.runtime_delta_median_ms!r}"
        )
    if features.runtime_regression_rate is not None:
        if not 0.0 <= features.runtime_regression_rate <= 1.0:
            raise DecisionInputGuardError(
                "runtime_regression_rate must be in [0, 1]: "
                f"{features.runtime_regression_rate!r}"
            )
    if features.runtime_pairs < 0:
        raise DecisionInputGuardError(
            f"runtime_pairs must be non-negative: {features.runtime_pairs!r}"
        )
    for field_name in (
        "total_pairs",
        "attempted_pairs",
        "valid_pairs",
        "failed_pairs",
        "candidate_failed_pairs",
        "champion_failed_pairs",
    ):
        value = getattr(features, field_name)
        if value < 0:
            raise DecisionInputGuardError(
                f"{field_name} must be non-negative: {value!r}"
            )


def _extract_runtime_guard(
    verification: VerificationResult,
) -> tuple[Optional[bool], Optional[float], bool]:
    """Extract structured V9 facts for DecisionFeatures without free text."""
    for check in verification.checks:
        if check.name != "V9_perf_guard":
            continue
        metadata = check.metadata or {}
        ratio_raw = metadata.get("ratio")
        try:
            ratio = float(ratio_raw) if ratio_raw is not None else None
        except (TypeError, ValueError):
            ratio = None
        timeout = bool(metadata.get("candidate_timeout", False))
        return check.passed, ratio, timeout
    return None, None, False
