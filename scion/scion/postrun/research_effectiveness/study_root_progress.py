"""Private safe-state audit for initial-screening status progress projections."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import _as_mapping, _fail, _JoinedRow, _Physical
from .terminal_interrupts import (
    _TERMINAL_CLOSED,
    _TERMINAL_DURABLE,
)

_FORBIDDEN_DECISIONS = frozenset({"queue_frozen", "promote", "expand_validation"})
_FORBIDDEN_STAGES = frozenset({"validation", "frozen", "retained"})


def _validate_last_result_shape(value: Any) -> Mapping[str, Any]:
    last = _as_mapping(value, "STUDY_LAST_RESULT_INVALID")
    if set(last) != {
        "action",
        "branch_id",
        "decision",
        "stopped",
        "reason",
        "execution_outcome",
    }:
        _fail("STUDY_LAST_RESULT_INVALID")
    outcome = _as_mapping(last.get("execution_outcome"), "STUDY_LAST_RESULT_INVALID")
    if not _last_result_scalars_are_valid(last, outcome):
        _fail("STUDY_LAST_RESULT_INVALID")
    return last


def _last_result_scalars_are_valid(
    last: Mapping[str, Any], outcome: Mapping[str, Any]
) -> bool:
    decision = last.get("decision")
    return bool(
        type(last.get("action")) is str
        and bool(last["action"])
        and type(last.get("branch_id")) is str
        and bool(last["branch_id"])
        and (decision is None or type(decision) is str)
        and decision not in _FORBIDDEN_DECISIONS
        and type(last.get("stopped")) is bool
        and _nonempty_string(last.get("reason"))
        and set(outcome) == {"outcome", "reason_code", "stage"}
        and all(_nonempty_string(outcome.get(key)) for key in outcome)
        and outcome.get("stage") not in _FORBIDDEN_STAGES
    )


def _validate_completed_last_result(
    status: Mapping[str, Any], rows: tuple[_JoinedRow, ...]
) -> None:
    if "current_progress" in status:
        _fail("STUDY_COMPLETED_PROGRESS_REMAINS")
    _validate_last_result_against_rows(status, rows)


def _validate_stopped_last_result(
    status: Mapping[str, Any], physical: _Physical, terminal_kind: str
) -> None:
    run = _as_mapping(status.get("run_result"), "RUN_RESULT_INVALID")
    if terminal_kind == _TERMINAL_CLOSED and (
        run.get("stop_reason") == "unhandled_exception"
    ):
        if any(
            _last_result_projection_is_valid(status, rows)
            for rows in (physical.rows, physical.rows[:-1])
        ):
            return
        _fail("STUDY_LAST_RESULT_MISMATCH")
    rows = _last_result_projection_rows(status, physical.rows, terminal_kind)
    _validate_last_result_against_rows(status, rows)


def _last_result_projection_rows(
    status: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    terminal_kind: str,
) -> tuple[_JoinedRow, ...]:
    run = _as_mapping(status.get("run_result"), "RUN_RESULT_INVALID")
    omit_terminal = terminal_kind == _TERMINAL_DURABLE or (
        terminal_kind == _TERMINAL_CLOSED
        and run.get("stop_reason") == "unhandled_exception"
    )
    return rows[:-1] if omit_terminal else rows


def _validate_last_result_against_rows(
    status: Mapping[str, Any], rows: tuple[_JoinedRow, ...]
) -> None:
    if not _last_result_projection_is_valid(status, rows):
        _fail("STUDY_LAST_RESULT_MISMATCH")


def _last_result_projection_is_valid(
    status: Mapping[str, Any], rows: tuple[_JoinedRow, ...]
) -> bool:
    if not rows:
        return "last_result" not in status
    if "last_result" not in status:
        return False
    last = _validate_last_result_shape(status["last_result"])
    row = rows[-1]
    return _last_result_matches_row(last, row, rows[:-1])


def _last_result_matches_row(
    last: Mapping[str, Any],
    row: _JoinedRow,
    prior_rows: tuple[_JoinedRow, ...],
) -> bool:
    outcome = _as_mapping(
        row.summary.get("execution_outcome"), "SUMMARY_EXECUTION_OUTCOME_INVALID"
    )
    provenance = _as_mapping(
        outcome.get("provenance"), "SUMMARY_EXECUTION_OUTCOME_PROVENANCE_INVALID"
    )
    branch_id = row.summary.get("branch_id")
    action = (
        "explore"
        if any(prior.summary.get("branch_id") == branch_id for prior in prior_rows)
        else "create_branch"
    )
    return bool(
        last.get("action") == action
        and last.get("branch_id") == branch_id
        and last.get("decision") == row.summary.get("decision")
        and last.get("stopped") is False
        and last.get("execution_outcome")
        == {
            "outcome": outcome.get("outcome"),
            "reason_code": outcome.get("reason_code"),
            "stage": provenance.get("stage"),
        }
    )


def _validate_stopped_current_progress(
    status: Mapping[str, Any], _physical: _Physical, _terminal_kind: str
) -> None:
    if "current_progress" in status:
        _fail("STUDY_CURRENT_PROGRESS_INVALID")


def _nonempty_string(value: Any) -> bool:
    return type(value) is str and bool(value)
