"""Helpers for turning solver-side runtime audit fields into evidence failures."""
from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import RunResult, SolverOutput


def runtime_audit_failure_from_result(result: RunResult) -> dict[str, Any] | None:
    """Return a structured failure if a successful solver run reports errors."""

    return runtime_audit_failure_from_output(result.output)


def runtime_audit_failure_from_output(output: SolverOutput | None) -> dict[str, Any] | None:
    if output is None:
        return None
    return runtime_audit_failure_from_runtime(output.runtime)


def runtime_audit_failure_from_raw(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    runtime = raw.get("runtime")
    if not isinstance(runtime, Mapping):
        return None
    return runtime_audit_failure_from_runtime(runtime)


def runtime_audit_failure_from_runtime(runtime: Mapping[str, Any]) -> dict[str, Any] | None:
    """Detect solver-reported operator runtime errors.

    A solver may recover from an operator exception by returning the unchanged
    incumbent solution. That keeps the process alive, but the candidate operator
    did not actually produce valid evidence. Such runs must be treated as
    runtime failures rather than objective ties.
    """

    baseline_issue = _baseline_audit_failure(runtime)
    operator_errors = _as_int(runtime.get("operator_errors"))
    operator_invalid_outputs = _as_int(runtime.get("operator_invalid_outputs"))
    if (
        baseline_issue is None
        and operator_errors <= 0
        and operator_invalid_outputs <= 0
    ):
        return None

    events = runtime.get("operator_events")
    if not isinstance(events, list):
        events = []

    if baseline_issue is not None:
        return {
            "error_category": "baseline_runtime_error",
            "baseline_mode": runtime.get("baseline_mode"),
            "baseline_required": bool(runtime.get("baseline_required")),
            "baseline_error": runtime.get("baseline_error"),
            "operator_errors": operator_errors,
            "operator_invalid_outputs": operator_invalid_outputs,
            "operator_loaded": _as_int(runtime.get("operator_loaded")),
            "operator_attempts": _as_int(runtime.get("operator_attempts")),
            "operator_accepted": _as_int(runtime.get("operator_accepted")),
            "operator_events": events[:5],
            "detail": baseline_issue,
        }

    detail_parts = []
    if operator_errors > 0:
        detail_parts.append(f"operator_errors={operator_errors}")
    if operator_invalid_outputs > 0:
        detail_parts.append(f"operator_invalid_outputs={operator_invalid_outputs}")

    return {
        "error_category": "operator_runtime_error",
        "operator_errors": operator_errors,
        "operator_invalid_outputs": operator_invalid_outputs,
        "operator_loaded": _as_int(runtime.get("operator_loaded")),
        "operator_attempts": _as_int(runtime.get("operator_attempts")),
        "operator_accepted": _as_int(runtime.get("operator_accepted")),
        "operator_events": events[:5],
        "detail": "solver runtime audit reported " + ", ".join(detail_parts),
    }


def format_runtime_audit_failure(issue: Mapping[str, Any]) -> str:
    detail = str(issue.get("detail") or "solver runtime audit failed")
    events = issue.get("operator_events")
    if isinstance(events, list) and events:
        first = events[0]
        if isinstance(first, Mapping):
            op = first.get("operator")
            event_detail = first.get("detail")
            if op or event_detail:
                return f"{detail}: first_event operator={op} detail={event_detail}"
    return detail


def _baseline_audit_failure(runtime: Mapping[str, Any]) -> str | None:
    if not bool(runtime.get("baseline_required")):
        return None
    error = runtime.get("baseline_error")
    mode = str(runtime.get("baseline_mode") or "")
    if error:
        return f"required solver baseline failed: {error}"
    if mode.endswith("_fallback"):
        return f"required solver baseline used fallback mode: {mode}"
    return None


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0
