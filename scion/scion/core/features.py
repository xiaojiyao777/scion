from __future__ import annotations
import re
from math import isfinite
from typing import Any, Optional, Tuple, get_args

from scion.core.models import (
    Branch, BranchState, ContractResult, VerificationResult,
    CanaryResult, ProtocolResult, DecisionFeatures,
    DecisionRuntimeEvidenceConfidence, DecisionRuntimeEvidenceStatus,
)
from scion.core.screening_visibility import runtime_confidence_for_protocol


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
_METRIC_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,79}$")
RUNTIME_EVIDENCE_CONFIDENCE_VALUES = frozenset(
    get_args(DecisionRuntimeEvidenceConfidence)
)
RUNTIME_EVIDENCE_STATUS_VALUES = frozenset(get_args(DecisionRuntimeEvidenceStatus))
PROTOCOL_REASON_CODES = frozenset({
    "BOTH_RUNTIME_BUDGET_SATURATION",
    "CANDIDATE_RUNTIME_BUDGET_SATURATION",
    "CANDIDATE_RUNTIME_FAILURE",
    "CHAMPION_RUNTIME_BUDGET_SATURATION",
    "CHAMPION_RUNTIME_FAILURE",
    "FROZEN_FAIL_CI_NEGATIVE",
    "FROZEN_FAIL_CASE_QUALITY",
    "FROZEN_FAIL_HIERARCHICAL_NEGATIVE",
    "FROZEN_FAIL_HIERARCHICAL_UNCERTAIN",
    "FROZEN_FAIL_NO_HIERARCHICAL_GAIN",
    "FROZEN_FAIL_UNCLEAR",
    "FROZEN_PASS",
    "FROZEN_PASS_HIERARCHICAL",
    "FROZEN_PASS_RUNTIME_TIE_IMPROVEMENT",
    "INCOMPLETE_EVIDENCE",
    "NO_VALID_RUNS",
    "RUNTIME_REGRESSION",
    "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
    "SCREENING_BELOW_WIN_RATE_MIN_ALLOWED_BY_POLICY",
    "SCREENING_BORDERLINE_POLICY_FAIL_CLOSED",
    "SCREENING_EXPAND",
    "SCREENING_EXPAND_CASE_LEVEL_UNCERTAIN",
    "SCREENING_EXPAND_EXHAUSTED",
    "SCREENING_EXPAND_EXHAUSTED_CASE_LEVEL_UNCERTAIN",
    "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_CI_LOW",
    "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA",
    "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_POLICY_PASS",
    "SCREENING_EXPAND_EXHAUSTED_PAIR_SIGNAL_POLICY_PASS",
    "SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT",
    "SCREENING_EXPAND_REQUIRED_FOR_PASS",
    "SCREENING_EXPAND_INITIAL_QUALITY_ROUTE",
    "SCREENING_EXPAND_SPARSE_NO_LOSS",
    "SCREENING_FAIL_PROTECTED_OBJECTIVE_REGRESSION",
    "SCREENING_FAIL_CASE_QUALITY",
    "SCREENING_FAIL_WIN_RATE",
    "SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT",
    "SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE",
    "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE",
    "SCREENING_PARTIAL_CHAMPION_EVIDENCE",
    "SCREENING_PASS",
    "SCREENING_PASS_MARGINAL_DELTA",
    "SCREENING_PASS_RUNTIME_TIE_IMPROVEMENT",
    "SCREENING_RUNTIME_BUDGET_SATURATION",
    "TINY_RUNTIME_BUDGET_SATURATION",
    "VALIDATION_EXPAND",
    "VALIDATION_EXPAND_PRACTICAL_EFFECT",
    "VALIDATION_EXPAND_EXHAUSTED_FAIL",
    "VALIDATION_EXPAND_EXHAUSTED_INSUFFICIENT_EVIDENCE",
    "VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS",
    "VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN",
    "VALIDATION_FAIL_CI_NEGATIVE",
    "VALIDATION_FAIL_CASE_QUALITY",
    "VALIDATION_FAIL_BELOW_PRACTICAL_EFFECT",
    "VALIDATION_FAIL_HIERARCHICAL_NEGATIVE",
    "VALIDATION_FAIL_NO_HIERARCHICAL_GAIN",
    "VALIDATION_FAIL_WIN_RATE",
    "VALIDATION_PASS",
    "VALIDATION_PASS_HIERARCHICAL",
    "VALIDATION_PASS_RUNTIME_TIE_IMPROVEMENT",
})


class DecisionInputGuardError(Exception):
    pass


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
        runtime_evidence_confidence = "high"
        runtime_evidence_status = "sufficient"
        protocol_gate_outcome = None
        protocol_reason_codes: Tuple[str, ...] = ()
        total_pairs = 0
        attempted_pairs = 0
        valid_pairs = 0
        failed_pairs = 0
        candidate_failed_pairs = 0
        champion_failed_pairs = 0
        pair_wins = 0
        pair_losses = 0
        pair_ties = 0
        n_cases = 0
        wins = 0
        losses = 0
        ties = 0

        if protocol is not None:
            stats = protocol.stats
            n_cases = stats.n_cases
            wins = stats.wins
            losses = stats.losses
            ties = stats.ties
            protocol_gate_outcome = protocol.gate_outcome
            protocol_reason_codes = tuple(protocol.reason_codes)
            win_rate = stats.win_rate
            median_delta = stats.median_delta
            ci_low = stats.ci_low
            ci_high = stats.ci_high
            statistical_status = stats.statistical_status
            statistical_metric = _declared_statistical_metric_id(stats)
            runtime_ratio_median = stats.runtime_ratio_median
            runtime_delta_median_ms = stats.runtime_delta_median_ms
            runtime_regression_rate = stats.runtime_regression_rate
            runtime_pairs = stats.runtime_pairs
            runtime_evidence_status = str(
                getattr(stats, "runtime_evidence_status", "sufficient")
                or "sufficient"
            )
            runtime_evidence_confidence = runtime_confidence_for_protocol(
                protocol,
                runtime_ratio=runtime_ratio_median,
                runtime_delta=runtime_delta_median_ms,
                runtime_regression_rate=runtime_regression_rate,
                runtime_pairs=runtime_pairs,
            )
            total_pairs = stats.total_pairs
            attempted_pairs = stats.attempted_pairs
            valid_pairs = stats.valid_pairs
            failed_pairs = stats.failed_pairs
            candidate_failed_pairs = stats.candidate_failed_pairs
            champion_failed_pairs = stats.champion_failed_pairs
            pair_wins = int(getattr(stats, "pair_wins", 0) or 0)
            pair_losses = int(getattr(stats, "pair_losses", 0) or 0)
            pair_ties = int(getattr(stats, "pair_ties", 0) or 0)
            pair_feedback = list(getattr(protocol, "pair_feedback", ()) or ())
            if pair_feedback:
                pair_wins = sum(
                    1
                    for item in pair_feedback
                    if getattr(item, "comparison", None) == "win"
                )
                pair_losses = sum(
                    1
                    for item in pair_feedback
                    if getattr(item, "comparison", None) == "loss"
                )
                pair_ties = len(pair_feedback) - pair_wins - pair_losses

        recent_failure_codes: Tuple[str, ...] = tuple(
            c for c in branch.failure_codes if c in KNOWN_FAILURE_CODES
        )
        runtime_guard_passed, runtime_guard_ratio, runtime_guard_timeout = (
            _extract_runtime_guard(verification)
        )
        features = DecisionFeatures(
            branch_id=branch.branch_id,
            hypothesis_action=hypothesis_action,  # type: ignore[arg-type]
            stage=stage,  # type: ignore[arg-type]
            contract_passed=contract.passed,
            verification_passed=verification.passed,
            canary_passed=canary.passed,
            n_cases=n_cases,
            wins=wins,
            losses=losses,
            ties=ties,
            win_rate=win_rate,
            median_delta=median_delta,
            ci_low=ci_low,
            ci_high=ci_high,
            statistical_status=statistical_status,
            statistical_metric=statistical_metric,
            stale=branch.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE),
            screening_expand_count=branch.screening_expand_count,
            validation_expand_count=branch.validation_expand_count,
            recent_failure_codes=recent_failure_codes,
            runtime_guard_passed=runtime_guard_passed,
            runtime_guard_ratio=runtime_guard_ratio,
            runtime_guard_timeout=runtime_guard_timeout,
            runtime_ratio_median=runtime_ratio_median,
            runtime_delta_median_ms=runtime_delta_median_ms,
            runtime_regression_rate=runtime_regression_rate,
            runtime_pairs=runtime_pairs,
            runtime_evidence_confidence=runtime_evidence_confidence,
            runtime_evidence_status=runtime_evidence_status,
            protocol_gate_outcome=protocol_gate_outcome,  # type: ignore[arg-type]
            protocol_reason_codes=protocol_reason_codes,
            total_pairs=total_pairs,
            attempted_pairs=attempted_pairs,
            valid_pairs=valid_pairs,
            failed_pairs=failed_pairs,
            candidate_failed_pairs=candidate_failed_pairs,
            champion_failed_pairs=champion_failed_pairs,
            pair_wins=pair_wins,
            pair_losses=pair_losses,
            pair_ties=pair_ties,
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
    for code in features.protocol_reason_codes:
        if code not in PROTOCOL_REASON_CODES:
            raise DecisionInputGuardError(
                f"Unknown protocol reason code: {code!r}"
            )
    if features.statistical_metric is not None:
        metric = str(features.statistical_metric)
        if not _METRIC_ID_RE.fullmatch(metric):
            raise DecisionInputGuardError(
                "statistical_metric must be a declared metric id, not free text: "
                f"{features.statistical_metric!r}"
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
    runtime_confidence = str(features.runtime_evidence_confidence or "")
    if runtime_confidence not in RUNTIME_EVIDENCE_CONFIDENCE_VALUES:
        raise DecisionInputGuardError(
            "runtime_evidence_confidence is not a known enum: "
            f"{features.runtime_evidence_confidence!r}"
        )
    runtime_status = str(features.runtime_evidence_status or "")
    if runtime_status not in RUNTIME_EVIDENCE_STATUS_VALUES:
        raise DecisionInputGuardError(
            "runtime_evidence_status is not a known enum: "
            f"{features.runtime_evidence_status!r}"
        )
    for field_name in (
        "total_pairs",
        "attempted_pairs",
        "valid_pairs",
        "failed_pairs",
        "candidate_failed_pairs",
        "champion_failed_pairs",
        "pair_wins",
        "pair_losses",
        "pair_ties",
        "wins",
        "losses",
        "ties",
        "screening_expand_count",
        "validation_expand_count",
    ):
        value = getattr(features, field_name)
        if value < 0:
            raise DecisionInputGuardError(
                f"{field_name} must be non-negative: {value!r}"
            )


def _declared_statistical_metric_id(stats: Any) -> str | None:
    metric = getattr(stats, "statistical_metric", None)
    if metric in (None, ""):
        return None
    metric_id = str(metric).strip()
    if not _METRIC_ID_RE.fullmatch(metric_id):
        raise DecisionInputGuardError(
            "statistical_metric must be a declared metric id, not free text: "
            f"{metric!r}"
        )
    declared = {
        str(getattr(row, "metric_name", "") or "").strip()
        for row in getattr(stats, "metric_stats", ()) or ()
        if str(getattr(row, "metric_name", "") or "").strip()
    }
    if declared and metric_id not in declared:
        raise DecisionInputGuardError(
            f"statistical_metric {metric_id!r} is not present in metric_stats"
        )
    return metric_id


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
