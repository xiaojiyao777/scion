from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, Tuple

from scion.core.models import (
    Branch, BranchState, ContractResult, VerificationResult,
    CanaryResult, ProtocolResult, DecisionFeatures,
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
        n_cases = 0

        if protocol is not None:
            stats = protocol.stats
            n_cases = stats.n_cases
            win_rate = stats.win_rate
            median_delta = stats.median_delta
            ci_low = stats.ci_low
            ci_high = stats.ci_high
            statistical_status = stats.statistical_status
            statistical_metric = stats.statistical_metric

        recent_failure_codes: Tuple[str, ...] = tuple(
            c for c in branch.failure_codes if c in KNOWN_FAILURE_CODES
        )

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
    for code in features.recent_failure_codes:
        if code not in KNOWN_FAILURE_CODES:
            raise DecisionInputGuardError(
                f"Unknown failure code in recent_failure_codes: {code!r}"
            )
