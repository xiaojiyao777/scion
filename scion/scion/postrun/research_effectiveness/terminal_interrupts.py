"""Strict terminal-interrupt shapes shared by offline artifact validators."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from .models import _OUTCOMES, _Attempt, _is_incomplete_reason, _JoinedRow

_CAMPAIGN_INTERRUPT_REASONS = {
    "OUTER_HARDWALL_EXCEEDED": {"OUTER_HARDWALL_EXCEEDED"},
    "EXTERNAL_STOP_REQUESTED": {
        "signal:SIGINT",
        "signal:SIGTERM",
        "external_stop_requested",
    },
}
_TERMINAL_CLOSED = "closed"
_TERMINAL_PREFLIGHT = "preflight_exception"
_TERMINAL_ZERO_EVIDENCE = "zero_evidence_interrupt"
_TERMINAL_ADMITTED = "admitted_pre_round_interrupt"
_TERMINAL_PRE_RESERVATION = "pre_reservation_interrupt"
_TERMINAL_RESERVED = "reserved_pre_attempt_interrupt"
_TERMINAL_UNMATCHED = "unmatched_nonclosed_attempt"
_TERMINAL_DURABLE = "durable_nonclosed_attempt"
_CLOSED_EXTERNAL_STOP_REASONS = frozenset(
    {
        "OUTER_HARDWALL_EXCEEDED",
        "external_stop_requested",
        "signal:SIGINT",
        "signal:SIGTERM",
    }
)


def _stopped_projection_kind(
    status: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> str | None:
    """Classify one exact producer-reachable stopped projection."""

    run = status.get("run_result")
    if not isinstance(run, Mapping) or run.get("status") != "stopped":
        return None
    if _is_preflight_exception(status, rows, attempts):
        return _TERMINAL_PREFLIGHT
    if _is_zero_evidence_interrupt(status, rows, attempts):
        return _TERMINAL_ZERO_EVIDENCE
    if _is_admitted_pre_round_interrupt(status, rows, attempts):
        return _TERMINAL_ADMITTED
    if _is_pre_reservation_interrupt(status, rows, attempts):
        return _TERMINAL_PRE_RESERVATION
    if _is_reserved_pre_attempt_interrupt(status, rows, attempts):
        return _TERMINAL_RESERVED
    if _is_unmatched_nonclosed_terminal(run, rows, attempts):
        return _TERMINAL_UNMATCHED
    if _is_durable_nonclosed_terminal(run, rows, attempts):
        return _TERMINAL_DURABLE
    if _is_closed_stopped_projection(status, run, rows, attempts):
        return _TERMINAL_CLOSED
    return None


def _is_preflight_exception(
    status: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> bool:
    run = status.get("run_result")
    if not isinstance(run, Mapping):
        return False
    return bool(
        not rows
        and not attempts
        and run.get("scheduled_calls") == 0
        and status.get("total_rounds") == 0
        and status.get("balance_exhausted") is False
        and _loop_projection_matches(run, (), "closed", proposal_attempts=0)
        and run.get("stop_reason") == "preflight_exception"
    )


def _is_pre_reservation_interrupt(
    status: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> bool:
    return _pre_attempt_interrupt_matches(
        status,
        rows,
        attempts,
        round_delta=1,
        proposal_delta=0,
    )


def _is_zero_evidence_interrupt(
    status: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> bool:
    run = status.get("run_result")
    last = run.get("last_execution_outcome") if isinstance(run, Mapping) else None
    return bool(
        not rows
        and not attempts
        and status.get("branches") == []
        and isinstance(last, Mapping)
        and last.get("reason_code") == "OUTER_HARDWALL_EXCEEDED"
        and _pre_attempt_interrupt_matches(
            status,
            rows,
            attempts,
            round_delta=0,
            proposal_delta=0,
        )
    )


def _is_admitted_pre_round_interrupt(
    status: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> bool:
    return bool(
        not _is_zero_evidence_interrupt(status, rows, attempts)
        and _pre_attempt_interrupt_matches(
            status,
            rows,
            attempts,
            round_delta=0,
            proposal_delta=0,
        )
    )


def _is_reserved_pre_attempt_interrupt(
    status: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> bool:
    return _pre_attempt_interrupt_matches(
        status,
        rows,
        attempts,
        round_delta=1,
        proposal_delta=1,
    )


def _pre_attempt_interrupt_matches(
    status: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
    *,
    round_delta: int,
    proposal_delta: int,
) -> bool:
    run = status.get("run_result")
    if not isinstance(run, Mapping):
        return False
    qualification = run.get("qualification")
    last = run.get("last_execution_outcome")
    counts = run.get("execution_outcome_counts")
    failures = run.get("failure_categories")
    if not all(
        isinstance(value, Mapping) for value in (qualification, last, counts, failures)
    ):
        return False
    assert isinstance(qualification, Mapping)
    assert isinstance(last, Mapping)
    assert isinstance(counts, Mapping)
    assert isinstance(failures, Mapping)
    limits = qualification.get("limits")
    if not isinstance(limits, Mapping):
        return False
    reason = last.get("reason_code")
    return bool(
        len(rows) == len(attempts)
        and _ordinals_are_exact(rows, attempts)
        and all(attempt.accounting_state == "closed" for attempt in attempts)
        and all(row.attempt is not None and not row.expanded for row in rows)
        and status.get("balance_exhausted") is False
        and status.get("total_rounds") == len(attempts) + round_delta
        and run.get("status") == "stopped"
        and run.get("scheduled_calls") == len(attempts) + 1
        and _campaign_stop_matches(run.get("stop_reason"), reason)
        and _loop_projection_matches(
            run,
            rows,
            "interrupted",
            proposal_attempts=len(attempts) + proposal_delta,
        )
        and qualification.get("proposal_attempts") == len(attempts) + proposal_delta
        and type(limits.get("max_proposal_attempts")) is int
        and len(attempts) + proposal_delta <= limits["max_proposal_attempts"]
        and len(attempts) < limits["max_proposal_attempts"]
    )


def _terminal_projection_rows(
    run: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> tuple[_JoinedRow, ...]:
    """Exclude one exact durable-but-unreturned terminal row from loop counts."""

    if _is_durable_nonclosed_terminal(run, rows, attempts):
        return rows[:-1]
    return rows


def _is_unmatched_nonclosed_terminal(
    run: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> bool:
    if len(attempts) != len(rows) + 1 or not _ordinals_are_exact(rows, attempts):
        return False
    terminal_state = attempts[-1].accounting_state
    return bool(
        run.get("status") == "stopped"
        and run.get("scheduled_calls") == len(attempts)
        and all(attempt.accounting_state == "closed" for attempt in attempts[:-1])
        and terminal_state in {"interrupted", "unresolved"}
        and _loop_projection_matches(
            run,
            rows,
            terminal_state,
            proposal_attempts=len(attempts),
        )
    )


def _has_one_unprojected_experiment(
    status: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> bool:
    run = status.get("run_result")
    return bool(
        isinstance(run, Mapping)
        and (
            (
                _is_unmatched_nonclosed_terminal(run, rows, attempts)
                and attempts[-1].code_candidates_ready == 1
                and "current_progress" not in status
            )
            or (
                _is_closed_stopped_projection(status, run, rows, attempts)
                and _last_row_is_event_write_failed(rows)
            )
            or _last_row_is_champion_evidence_blocked(rows)
        )
    )


def _requires_one_unprojected_experiment(rows: tuple[_JoinedRow, ...]) -> bool:
    """Return whether a visible terminal row proves the +1 experiment counter."""

    return _last_row_is_event_write_failed(rows) or (
        _last_row_is_champion_evidence_blocked(rows)
    )


def _last_row_is_champion_evidence_blocked(
    rows: tuple[_JoinedRow, ...],
) -> bool:
    if not rows:
        return False
    row = rows[-1]
    outcome = row.history["outcome"]
    return bool(
        row.protocol is None
        and row.summary.get("verification_passed") is True
        and row.canary_classification == "passed"
        and outcome.get("outcome") == "blocked_infra"
        and outcome.get("reason_code") == "EVALUATION_CHAMPION_EVIDENCE_BLOCKED"
        and outcome.get("stage") == "screening"
    )


def _last_row_is_event_write_failed(rows: tuple[_JoinedRow, ...]) -> bool:
    if not rows:
        return False
    row = rows[-1]
    outcome = row.history["outcome"]
    return bool(
        row.attempt is not None
        and not row.expanded
        and row.attempt.accounting_state == "closed"
        and row.attempt.code_candidates_ready == 1
        and row.h_key is not None
        and row.patch_key is not None
        and row.protocol is None
        and row.canary_classification is None
        and row.summary.get("contract_passed") is True
        and row.summary.get("verification_passed") is True
        and row.summary.get("decision") is None
        and row.history.get("decision") is None
        and row.summary.get("failure_stage") == "decision_event"
        and type(row.summary.get("failure_detail")) is str
        and outcome.get("outcome") == "blocked_infra"
        and outcome.get("reason_code") == "EXPERIMENT_EVENT_WRITE_FAILED"
        and outcome.get("stage") == "decision_event"
    )


def _is_closed_stopped_projection(
    status: Mapping[str, Any],
    run: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> bool:
    return bool(
        len(rows) == len(attempts)
        and _ordinals_are_exact(rows, attempts)
        and all(attempt.accounting_state == "closed" for attempt in attempts)
        and run.get("scheduled_calls") == len(attempts)
        and _loop_projection_matches(
            run,
            rows,
            "closed",
            proposal_attempts=len(attempts),
        )
        and _closed_stop_matches(status, run, rows)
    )


def _closed_stop_matches(
    status: Mapping[str, Any],
    run: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
) -> bool:
    stop_reason = run.get("stop_reason")
    exhausted = status.get("balance_exhausted")
    if type(exhausted) is not bool:
        return False
    if stop_reason == "unhandled_exception":
        return True
    if stop_reason in _CLOSED_EXTERNAL_STOP_REASONS:
        return True
    if exhausted:
        return bool(
            stop_reason == "api_balance_exhausted"
            and (not rows or _row_allows_next_attempt(rows[-1]))
            or rows
            and stop_reason == "execution_resource_exhausted"
            and rows[-1].history["outcome"]["outcome"] == "resource_exhausted"
            and rows[-1].history["outcome"]["reason_code"]
            == "PROVIDER_BALANCE_EXHAUSTED"
        )
    if stop_reason == "api_balance_exhausted":
        return False
    if rows and rows[-1].history["outcome"]["reason_code"] == (
        "PROVIDER_BALANCE_EXHAUSTED"
    ):
        return False
    if not rows:
        return False
    terminal = rows[-1]
    outcome = terminal.history["outcome"]["outcome"]
    if outcome in {
        "not_evaluated",
        "blocked_infra",
        "resource_exhausted",
        "interrupted",
    }:
        return stop_reason == f"execution_{outcome}"
    return bool(
        stop_reason == "evaluated_without_formal_protocol_result"
        and terminal.protocol is None
        and terminal.canary_classification in {"champion", "shared", "bilateral"}
    )


def _row_allows_next_attempt(row: _JoinedRow) -> bool:
    outcome = row.history["outcome"]
    if _is_incomplete_reason(str(outcome["reason_code"])):
        return False
    if outcome["outcome"] == "research_rejected":
        return True
    return bool(
        outcome["outcome"] == "evaluated"
        and (row.protocol is not None or row.canary_classification == "candidate")
    )


def _is_durable_nonclosed_terminal(
    run: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> bool:
    if (
        not rows
        or len(rows) != len(attempts)
        or not _ordinals_are_exact(rows, attempts)
    ):
        return False
    terminal_attempt = attempts[-1]
    terminal_row = rows[-1]
    prefix = rows[:-1]
    if (
        run.get("status") != "stopped"
        or run.get("scheduled_calls") != len(attempts)
        or any(attempt.accounting_state != "closed" for attempt in attempts[:-1])
        or terminal_attempt.accounting_state not in {"interrupted", "unresolved"}
        or terminal_row.attempt is None
        or terminal_row.expanded
        or terminal_row.protocol is not None
        or terminal_row.canary_classification is not None
        or terminal_row.summary.get("verification_passed") is True
        or terminal_attempt.code_candidates_ready != 0
        or terminal_row.history["outcome"]["outcome"] != "research_rejected"
        or terminal_row.history.get("decision") is not None
    ):
        return False
    return _loop_projection_matches(
        run,
        prefix,
        terminal_attempt.accounting_state,
        proposal_attempts=len(attempts),
    )


def _loop_projection_matches(
    run: Mapping[str, Any],
    prefix: tuple[_JoinedRow, ...],
    terminal_state: str,
    *,
    proposal_attempts: int,
) -> bool:
    observed = Counter(str(row.history["outcome"]["outcome"]) for row in prefix)
    counts = run.get("execution_outcome_counts")
    failures = run.get("failure_categories")
    if not isinstance(counts, Mapping) or not isinstance(failures, Mapping):
        return False
    expected_counts = {name: observed.get(name, 0) for name in _OUTCOMES}
    if terminal_state == "interrupted":
        expected_counts["interrupted"] += 1
    if dict(counts) != expected_counts or not _failure_projection_matches(
        failures, prefix
    ):
        return False
    if run.get("last_execution_outcome") != _terminal_last_outcome(
        run, prefix, terminal_state
    ):
        return False
    if run.get("run_validity") != _terminal_validity(expected_counts):
        return False
    if not _run_stage_projection_matches(run, prefix) or not (
        _qualification_projection_matches(run, prefix, proposal_attempts)
    ):
        return False
    if terminal_state == "unresolved":
        return _unresolved_projection_matches(run)
    if terminal_state == "interrupted":
        return _interrupted_projection_matches(run)
    return _closed_projection_matches(run)


def _run_stage_projection_matches(
    run: Mapping[str, Any], rows: tuple[_JoinedRow, ...]
) -> bool:
    stage_counts = run.get("protocol_stage_counts")
    if not isinstance(stage_counts, Mapping):
        return False
    protocol_rows = sum(row.protocol is not None for row in rows)
    expected = {"screening": protocol_rows, "validation": 0, "frozen": 0}
    return bool(
        dict(stage_counts) == expected
        and run.get("formal_screened_candidates") == protocol_rows
        and run.get("evaluated_rounds") == protocol_rows
    )


def _qualification_projection_matches(
    run: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    proposal_attempts: int,
) -> bool:
    qualification = run.get("qualification")
    if not isinstance(qualification, Mapping):
        return False
    protocol_rows = tuple(row for row in rows if row.protocol is not None)
    initial_rows = tuple(row for row in protocol_rows if row.attempt is not None)
    expanded_rows = tuple(row for row in protocol_rows if row.expanded)
    verified = _verified_candidate_chains(rows)
    if verified is None:
        return False
    return bool(
        qualification.get("proposal_attempts") == proposal_attempts
        and qualification.get("verified_candidate_chains") == verified
        and qualification.get("formal_screening_stages") == len(protocol_rows)
        and qualification.get("initial_screening_stages") == len(initial_rows)
        and qualification.get("expanded_screening_stages") == len(expanded_rows)
        and qualification.get("disposition") == "incomplete"
    )


def _closed_projection_matches(run: Mapping[str, Any]) -> bool:
    exception = run.get("terminal_exception")
    has_exception = "terminal_exception" in run
    return bool(
        run.get("unknown_outcome_count") == 0
        and has_exception
        == (run.get("stop_reason") in {"unhandled_exception", "preflight_exception"})
        and (
            not has_exception
            or isinstance(exception, Mapping)
            and exception.get("reason") == run.get("stop_reason")
        )
    )


def _unresolved_projection_matches(run: Mapping[str, Any]) -> bool:
    exception = run.get("terminal_exception")
    return bool(
        run.get("stop_reason") == "unhandled_exception"
        and run.get("unknown_outcome_count") == 1
        and isinstance(exception, Mapping)
        and set(exception) == {"reason", "type", "message"}
        and exception.get("reason") == "unhandled_exception"
        and type(exception.get("type")) is str
        and bool(exception["type"])
        and type(exception.get("message")) is str
    )


def _interrupted_projection_matches(run: Mapping[str, Any]) -> bool:
    last = run.get("last_execution_outcome")
    return bool(
        isinstance(last, Mapping)
        and _campaign_stop_matches(run.get("stop_reason"), last.get("reason_code"))
        and run.get("unknown_outcome_count") == 0
        and "terminal_exception" not in run
    )


def _terminal_last_outcome(
    run: Mapping[str, Any],
    prefix: tuple[_JoinedRow, ...],
    terminal_state: str,
) -> Mapping[str, Any] | None:
    if terminal_state == "interrupted":
        last = run.get("last_execution_outcome")
        reason = last.get("reason_code") if isinstance(last, Mapping) else None
        return {"outcome": "interrupted", "reason_code": reason, "stage": "campaign"}
    return _row_outcome(prefix[-1]) if prefix else None


def _row_outcome(row: _JoinedRow) -> dict[str, Any]:
    outcome = row.history["outcome"]
    summary_outcome = row.summary["execution_outcome"]
    provenance = summary_outcome["provenance"]
    return {
        "outcome": outcome["outcome"],
        "reason_code": outcome["reason_code"],
        "stage": provenance["stage"],
    }


def _terminal_validity(counts: Mapping[str, int]) -> dict[str, Any]:
    if counts.get("evaluated", 0):
        return {"valid": True, "status": "valid", "reason": "valid_incomplete"}
    return {
        "valid": False,
        "status": "invalid",
        "reason": "invalid_no_evaluated_outcome",
    }


def _ordinals_are_exact(
    rows: tuple[_JoinedRow, ...], attempts: tuple[_Attempt, ...]
) -> bool:
    return bool(
        tuple(attempt.round_num for attempt in attempts)
        == tuple(range(1, len(attempts) + 1))
        and tuple(int(row.summary["round"]) for row in rows)
        == tuple(range(1, len(rows) + 1))
    )


def _campaign_stop_matches(stop_reason: Any, reason_code: Any) -> bool:
    allowed = _CAMPAIGN_INTERRUPT_REASONS.get(reason_code)
    return allowed is not None and stop_reason in allowed


def _expected_failure_categories(
    rows: tuple[_JoinedRow, ...],
) -> dict[str, int] | None:
    counts: Counter[str] = Counter()
    for row in rows:
        stage = row.summary.get("failure_stage")
        detail = row.summary.get("failure_detail")
        if not stage and not detail:
            continue
        outcome = row.history["outcome"]["outcome"]
        canary = row.summary.get("canary_result")
        category: Any
        if outcome == "research_rejected":
            category = "research_rejected"
        elif outcome != "evaluated":
            category = outcome
        elif isinstance(canary, Mapping) and canary.get("passed") is False:
            category = canary.get("failure_category")
        else:
            category = stage
        if not isinstance(category, str) or not category:
            return None
        counts[category] += 1
    return dict(counts)


def _failure_projection_matches(
    projection: Mapping[str, Any], rows: tuple[_JoinedRow, ...]
) -> bool:
    expected = _expected_failure_categories(rows)
    return expected is not None and dict(projection) == expected


def _verified_candidate_chains(rows: tuple[_JoinedRow, ...]) -> int | None:
    branch_ids: set[str] = set()
    for row in rows:
        if row.attempt is None or row.summary.get("verification_passed") is not True:
            continue
        branch_id = row.summary.get("branch_id")
        if type(branch_id) is not str or not branch_id:
            return None
        branch_ids.add(branch_id)
    return len(branch_ids)
