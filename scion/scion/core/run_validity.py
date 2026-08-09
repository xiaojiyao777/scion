"""Run validity classification for campaign status and summaries."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from scion.core.execution_outcome import (
    ExecutionOutcome,
    execution_outcome_evidence_from_counts,
)

RUN_VALIDITY_VALID = "valid"
RUN_VALIDITY_VALID_BUT_INCOMPLETE = "valid_but_incomplete"
RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED = "valid_partial_interrupted"
RUN_VALIDITY_INVALID_NO_EFFECTIVE_ROUNDS = "invalid_no_effective_rounds"
RUN_VALIDITY_INVALID_INFRA_ONLY = "invalid_infra_only"
RUN_VALIDITY_INVALID_NO_EXPERIMENTS = "invalid_no_experiments"
RUN_VALIDITY_INVALID_NO_PROTOCOL_ROWS = "invalid_no_protocol_rows"
RUN_VALIDITY_INVALID_RESEARCH_REJECTED_ONLY = "invalid_research_rejected_only"
RUN_VALIDITY_INVALID_NOT_EVALUATED_ONLY = "invalid_not_evaluated_only"
RUN_VALIDITY_INVALID_RESOURCE_EXHAUSTED_ONLY = "invalid_resource_exhausted_only"
RUN_VALIDITY_INVALID_INTERRUPTED_ONLY = "invalid_interrupted_only"
RUN_VALIDITY_UNKNOWN_HISTORICAL = "unknown_historical"

_INFRA_CATEGORY_MARKERS = {
    "infra",
    "provider",
    "provider_error",
    "llm_transient_api_error",
    "api_balance_exhausted",
    "balance_exhausted",
    "transient_api",
    "transient_provider",
}

_INFRA_TEXT_MARKERS = (
    "no_available_accounts",
    "llm_transient_api_error",
    "transient api",
    "transient provider error",
    "provider error",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
    "temporarily unavailable",
    "rate limit",
    "rate_limit",
    "ratelimit",
    "http 429",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
    "error code: 429",
    "error code: 500",
    "error code: 502",
    "error code: 503",
    "error code: 504",
    "status code: 429",
    "status code: 500",
    "status code: 502",
    "status code: 503",
    "status code: 504",
    "api_balance_exhausted",
    "balance is insufficient",
    "insufficient balance",
    "credit balance",
    "no credits",
)


def failure_category_for_run_validity(
    detail: Any = None,
    *,
    category: Any = None,
    failure_stage: Any = None,
    session_ref: Mapping[str, Any] | None = None,
) -> str:
    """Return a coarse failure category suitable for run-validity accounting."""
    explicit_category = _first_text(
        category,
        _nested(session_ref, "primary_failure", "category"),
        _nested(session_ref, "failure_category"),
    )
    if _is_infra_category(explicit_category) or _is_infra_text(explicit_category):
        return "infra"

    combined = " ".join(
        part
        for part in (
            str(detail or ""),
            str(failure_stage or ""),
            str(_nested(session_ref, "primary_failure", "reason") or ""),
            str(_nested(session_ref, "primary_failure", "detail") or ""),
            str(_nested(session_ref, "failure_code") or ""),
            str(_nested(session_ref, "termination_reason") or ""),
        )
        if part
    )
    if _is_infra_text(combined):
        return "infra"
    if "stale_source" in combined.lower():
        return "code_generation"
    if explicit_category:
        return explicit_category
    stage = str(failure_stage or "").strip()
    return stage or "unknown"


def step_failure_categories(
    steps: Sequence[Any],
) -> dict[str, int]:
    """Count coarse failure categories from recorded campaign steps."""
    counts: dict[str, int] = {}
    for step in steps:
        if not getattr(step, "failure_stage", None) and not getattr(
            step,
            "failure_detail",
            None,
        ):
            continue
        category = failure_category_for_run_validity(
            getattr(step, "failure_detail", None),
            failure_stage=getattr(step, "failure_stage", None),
            session_ref=getattr(step, "proposal_session_ref", None),
        )
        if not category:
            continue
        counts[category] = counts.get(category, 0) + 1
    return counts


def build_run_validity(
    *,
    requested_rounds: Any = None,
    effective_rounds_completed: Any = None,
    n_experiments: Any = None,
    proposal_attempts: Any = None,
    protocol_metric_results: Any = None,
    effective_protocol_rounds: Any = None,
    stopped_reason: Any = None,
    failure_categories: Mapping[str, Any] | None = None,
    stopped: bool = True,
    partial_in_flight: Any = None,
    execution_outcome_counts: Mapping[str, Any] | None = None,
    last_execution_outcome: Mapping[str, Any] | None = None,
    unknown_outcome_count: Any = 0,
    committed_research_rejections: Any = 0,
) -> dict[str, Any]:
    """Build a stable validity record for wrapper/report consumers.

    Validity is intentionally about scientific usefulness of the campaign
    invocation, not process success. A wrapper can exit 0 after writing evidence
    for an invalid infra-only run.
    """
    requested = _coerce_int(requested_rounds, default=0)
    effective = _coerce_int(effective_rounds_completed, default=0)
    experiments = _coerce_int(n_experiments, default=0)
    attempts = _coerce_int(proposal_attempts, default=0)
    protocol_rows = _coerce_int(
        protocol_metric_results,
        default=_coerce_int(effective_protocol_rounds, default=experiments),
    )
    counts = _normalized_counts(failure_categories or {})
    committed_rejections = max(
        0,
        _coerce_int(committed_research_rejections, default=0),
    )
    typed_outcomes_available = (
        execution_outcome_counts is not None or committed_rejections > 0
    )
    projected_outcome_counts = (
        dict(execution_outcome_counts)
        if execution_outcome_counts is not None
        else ({} if committed_rejections else None)
    )
    if projected_outcome_counts is not None and committed_rejections:
        projected_outcome_counts[ExecutionOutcome.RESEARCH_REJECTED.value] = max(
            _coerce_int(
                projected_outcome_counts.get(
                    ExecutionOutcome.RESEARCH_REJECTED.value
                ),
                default=0,
            ),
            committed_rejections,
        )
    outcome_evidence = execution_outcome_evidence_from_counts(
        projected_outcome_counts,
        last_execution_outcome=last_execution_outcome,
        unknown_count=_coerce_int(unknown_outcome_count, default=0),
    )
    outcome_counts = outcome_evidence["execution_outcome_counts"]
    evaluated_count = outcome_evidence["evaluated_count"]
    non_evaluated_count = outcome_evidence["non_evaluated_count"]
    scheduler_forward_rejections = min(
        committed_rejections,
        outcome_counts[ExecutionOutcome.RESEARCH_REJECTED.value],
    )
    blocking_non_evaluated_count = max(
        0,
        non_evaluated_count - scheduler_forward_rejections,
    )
    stopped_reason_infra = (
        False
        if typed_outcomes_available
        else _is_infra_category(stopped_reason) or _is_infra_text(stopped_reason)
    )
    if stopped_reason_infra and not counts:
        counts["infra"] = 1
    infra_failures = (
        outcome_counts[ExecutionOutcome.BLOCKED_INFRA.value]
        if typed_outcomes_available
        else sum(
            count
            for category, count in counts.items()
            if _is_infra_category(category)
        )
    )
    total_failures = sum(counts.values())
    noninfra_failures = max(0, total_failures - infra_failures)
    completed_requested = bool(requested <= 0 or effective >= requested)
    stopped_reason_text = str(stopped_reason or "")
    interrupted = (
        outcome_counts[ExecutionOutcome.INTERRUPTED.value] > 0
        if typed_outcomes_available
        else bool(
            stopped
            and stopped_reason_text
            and stopped_reason_text
            not in {
                "max_rounds",
                "max_rounds_exhausted",
                "requested_rounds_completed",
                "run_complete",
                "completed",
                "complete",
            }
        )
    )
    protocol_in_flight = _coerce_bool(partial_in_flight, default=False)
    partial_hint = _coerce_bool(
        partial_in_flight,
        default=bool(not completed_requested and interrupted),
    )

    if not stopped:
        reason = "running"
        status = "pending"
        valid = None
    elif typed_outcomes_available and evaluated_count > 0:
        # ``effective_rounds_completed`` counts the formal Protocol stages that
        # the invocation requested.  Candidate-local proposal/verification
        # rejections remain useful attempt evidence, but they do not make a
        # campaign resumable after that formal horizon has been completed.
        if completed_requested:
            reason = RUN_VALIDITY_VALID
        else:
            reason = (
                RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED
                if interrupted
                else RUN_VALIDITY_VALID_BUT_INCOMPLETE
            )
        status = "valid"
        valid = True
    elif typed_outcomes_available and non_evaluated_count > 0:
        if (
            outcome_counts[ExecutionOutcome.BLOCKED_INFRA.value]
            == non_evaluated_count
        ):
            reason = RUN_VALIDITY_INVALID_INFRA_ONLY
        elif (
            outcome_counts[ExecutionOutcome.RESOURCE_EXHAUSTED.value]
            == non_evaluated_count
        ):
            reason = RUN_VALIDITY_INVALID_RESOURCE_EXHAUSTED_ONLY
        elif (
            outcome_counts[ExecutionOutcome.INTERRUPTED.value]
            == non_evaluated_count
        ):
            reason = RUN_VALIDITY_INVALID_INTERRUPTED_ONLY
        elif (
            outcome_counts[ExecutionOutcome.RESEARCH_REJECTED.value]
            == non_evaluated_count
        ):
            reason = RUN_VALIDITY_INVALID_RESEARCH_REJECTED_ONLY
        elif (
            outcome_counts[ExecutionOutcome.NOT_EVALUATED.value]
            == non_evaluated_count
        ):
            reason = RUN_VALIDITY_INVALID_NOT_EVALUATED_ONLY
        else:
            reason = RUN_VALIDITY_INVALID_NO_EFFECTIVE_ROUNDS
        status = "invalid"
        valid = False
    elif typed_outcomes_available and outcome_evidence["unknown_outcome_count"] > 0:
        # Historical rows which predate the typed outcome field stay unknown.
        # In particular, failure text and missing protocol rows must not silently
        # turn them into evaluated, negative, or infrastructure-only evidence.
        reason = RUN_VALIDITY_UNKNOWN_HISTORICAL
        status = "unknown"
        valid = None
    elif typed_outcomes_available and (attempts > 0 or effective > 0 or experiments > 0):
        reason = RUN_VALIDITY_UNKNOWN_HISTORICAL
        status = "unknown"
        valid = None
    elif effective > 0 and experiments <= 0 and protocol_rows <= 0:
        reason = RUN_VALIDITY_INVALID_NO_PROTOCOL_ROWS
        status = "invalid"
        valid = False
    elif effective > 0 or experiments > 0:
        if completed_requested:
            reason = RUN_VALIDITY_VALID
        elif interrupted:
            reason = RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED
        else:
            reason = RUN_VALIDITY_VALID_BUT_INCOMPLETE
        status = "valid"
        valid = True
    elif requested <= 0:
        reason = RUN_VALIDITY_VALID
        status = "valid"
        valid = True
    elif infra_failures > 0 and noninfra_failures == 0 and (
        attempts > 0 or stopped_reason_infra
    ):
        reason = RUN_VALIDITY_INVALID_INFRA_ONLY
        status = "invalid"
        valid = False
    elif experiments == 0 and attempts == 0:
        reason = RUN_VALIDITY_INVALID_NO_EXPERIMENTS
        status = "invalid"
        valid = False
    else:
        reason = RUN_VALIDITY_INVALID_NO_EFFECTIVE_ROUNDS
        status = "invalid"
        valid = False

    if completed_requested:
        partial_campaign = False
    elif typed_outcomes_available and evaluated_count > 0 and (
        blocking_non_evaluated_count > 0
        or outcome_evidence["unknown_outcome_count"] > 0
    ):
        partial_campaign = True
    elif reason == RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED:
        partial_campaign = True
    elif status == "invalid":
        partial_campaign = False
    else:
        partial_campaign = partial_hint

    record: dict[str, Any] = {
        "schema_version": "run-validity.v1",
        "status": status,
        "reason": reason,
        "valid": valid,
        "requested_rounds": requested,
        "effective_rounds_completed": effective,
        "completed_requested_rounds": completed_requested,
        "interrupted": interrupted,
        "partial_campaign_evidence": partial_campaign,
        "protocol_in_flight": protocol_in_flight,
        "partial_in_flight": partial_campaign,
        "completeness_status": _completeness_status(
            stopped=stopped,
            completed_requested=completed_requested,
            interrupted=interrupted,
            partial_in_flight=partial_campaign,
        ),
        "complete": completed_requested,
        "n_experiments": experiments,
        "protocol_metric_results": protocol_rows,
        "proposal_attempts": attempts,
        "stopped_reason": str(stopped_reason or ""),
        "failure_categories": counts,
        "infra_failure_attempts": infra_failures,
        "noninfra_failure_attempts": noninfra_failures,
        "committed_scheduler_forward_rejections": scheduler_forward_rejections,
        "blocking_non_evaluated_count": blocking_non_evaluated_count,
        **outcome_evidence,
    }
    if reason == RUN_VALIDITY_INVALID_INFRA_ONLY:
        record["operator_action"] = (
            "Treat this run as infrastructure-only; fix provider/proxy/account "
            "availability and rerun before drawing scientific conclusions."
        )
    elif reason in {
        RUN_VALIDITY_INVALID_NO_EFFECTIVE_ROUNDS,
        RUN_VALIDITY_INVALID_NO_EXPERIMENTS,
        RUN_VALIDITY_INVALID_NO_PROTOCOL_ROWS,
    }:
        record["operator_action"] = (
            "Do not treat this invocation as scientific evidence until at least "
            "one effective screening round completes."
        )
    elif reason in {
        RUN_VALIDITY_INVALID_RESEARCH_REJECTED_ONLY,
        RUN_VALIDITY_INVALID_NOT_EVALUATED_ONLY,
        RUN_VALIDITY_INVALID_RESOURCE_EXHAUSTED_ONLY,
        RUN_VALIDITY_INVALID_INTERRUPTED_ONLY,
    }:
        record["operator_action"] = (
            "Do not draw algorithm-quality conclusions: this invocation has "
            "no evaluated execution outcome."
        )
    elif reason in {
        RUN_VALIDITY_VALID_BUT_INCOMPLETE,
        RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED,
    }:
        record["operator_action"] = (
            "Treat this as scientifically useful partial evidence, not a "
            "complete requested-round validation; resume or rerun to complete "
            "the requested campaign length."
        )
    return record


def apply_run_completion_aliases(
    payload: Mapping[str, Any],
    run_validity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return ``payload`` with top-level aliases for run completion semantics."""
    normalized = dict(payload)
    validity = run_validity
    if validity is None:
        raw_validity = normalized.get("run_validity")
        validity = raw_validity if isinstance(raw_validity, Mapping) else None
    stopped_reason = normalized.get("stopped_reason")
    if stopped_reason is None and validity is not None:
        stopped_reason = validity.get("stopped_reason")
    if stopped_reason is not None:
        normalized["last_stop_reason"] = stopped_reason
    if validity is None:
        return normalized
    completed = _coerce_bool(
        validity.get("completed_requested_rounds"),
        default=_coerce_bool(validity.get("complete"), default=False),
    )
    normalized["completed_requested_rounds"] = completed
    normalized["run_complete"] = completed
    completeness_status = validity.get("completeness_status")
    if completeness_status is not None:
        normalized["run_completeness_status"] = completeness_status
    return normalized


def _normalized_counts(value: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, raw_count in value.items():
        category = str(key or "unknown").strip() or "unknown"
        count = _coerce_int(raw_count, default=0)
        if count <= 0:
            continue
        counts[category] = counts.get(category, 0) + count
    return counts


def _is_infra_category(category: Any) -> bool:
    text = str(category or "").strip().lower()
    return text in _INFRA_CATEGORY_MARKERS


def _is_infra_text(value: Any) -> bool:
    text = str(value or "").lower()
    return bool(text and any(marker in text for marker in _INFRA_TEXT_MARKERS))


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _nested(mapping: Mapping[str, Any] | None, *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _coerce_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return default


def _completeness_status(
    *,
    stopped: bool,
    completed_requested: bool,
    interrupted: bool,
    partial_in_flight: bool,
) -> str:
    if not stopped:
        return "running"
    if completed_requested:
        return "complete"
    if interrupted and partial_in_flight:
        return "partial_interrupted"
    if interrupted:
        return "interrupted_incomplete"
    return "incomplete"


__all__ = [
    "RUN_VALIDITY_INVALID_INFRA_ONLY",
    "RUN_VALIDITY_INVALID_NO_EFFECTIVE_ROUNDS",
    "RUN_VALIDITY_INVALID_NO_EXPERIMENTS",
    "RUN_VALIDITY_INVALID_NOT_EVALUATED_ONLY",
    "RUN_VALIDITY_INVALID_RESEARCH_REJECTED_ONLY",
    "RUN_VALIDITY_INVALID_RESOURCE_EXHAUSTED_ONLY",
    "RUN_VALIDITY_INVALID_INTERRUPTED_ONLY",
    "RUN_VALIDITY_UNKNOWN_HISTORICAL",
    "RUN_VALIDITY_VALID",
    "RUN_VALIDITY_VALID_BUT_INCOMPLETE",
    "RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED",
    "apply_run_completion_aliases",
    "build_run_validity",
    "failure_category_for_run_validity",
    "step_failure_categories",
]
