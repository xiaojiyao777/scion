"""Telemetry guard issue construction and text formatting."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _guard_issue(
    code: str,
    *,
    category: str,
    field: str,
    severity: str,
    summary: Mapping[str, Any],
    mechanism: str | None = None,
    diagnostic_type: str | None = None,
    diagnostic_kind: str | None = None,
    branch_repair_signal: str | None = None,
    telemetry_outcome: str | None = None,
    repairable: bool | None = None,
) -> dict[str, Any]:
    issue = {
        "code": code,
        "severity": severity,
        "category": category,
        "field": field,
        "candidate_positive": summary.get("candidate_positive", 0),
        "candidate_present": summary.get("candidate_present", 0),
        "candidate_zero": summary.get("candidate_zero", 0),
        "candidate_false": summary.get("candidate_false", 0),
        "candidate_missing": summary.get("candidate_missing", 0),
        "champion_positive": summary.get("champion_positive", 0),
    }
    if mechanism:
        issue["mechanism"] = mechanism
    if diagnostic_type:
        issue["diagnostic_type"] = diagnostic_type
    if diagnostic_kind:
        issue["diagnostic_kind"] = diagnostic_kind
    if branch_repair_signal:
        issue["branch_repair_signal"] = branch_repair_signal
    if telemetry_outcome:
        issue["telemetry_outcome"] = telemetry_outcome
    if repairable is not None:
        issue["repairable"] = bool(repairable)
    return issue


def format_telemetry_guard_issue(summary: Mapping[str, Any]) -> str | None:
    failures = summary.get("failures")
    if not isinstance(failures, Sequence) or not failures:
        return None
    first = failures[0]
    if not isinstance(first, Mapping):
        return "telemetry guard failed"
    code = str(first.get("code") or "TELEMETRY_GUARD_FAILED")
    field = str(first.get("field") or "")
    mechanism = str(first.get("mechanism") or "")
    category = str(first.get("category") or "telemetry")
    if code in {
        "TELEMETRY_ACTIVITY_NOT_OBSERVED",
        "TELEMETRY_ACTIVITY_FIELD_ALL_ZERO",
        "TELEMETRY_ACTIVITY_ZERO",
    }:
        activity_fields = []
        for item in failures:
            if (
                isinstance(item, Mapping)
                and item.get("code")
                in {
                    "TELEMETRY_ACTIVITY_NOT_OBSERVED",
                    "TELEMETRY_ACTIVITY_FIELD_ALL_ZERO",
                    "TELEMETRY_ACTIVITY_ZERO",
                }
            ):
                activity_fields.extend(
                    part.strip()
                    for part in str(item.get("field") or "").split(",")
                    if part.strip()
                )
        if activity_fields:
            field = ",".join(dict.fromkeys(activity_fields))
        field_zero_text = ", ".join(
            f"{item.strip()}=0" for item in field.split(",") if item.strip()
        )
        if code in {
            "TELEMETRY_ACTIVITY_FIELD_ALL_ZERO",
            "TELEMETRY_ACTIVITY_ZERO",
        }:
            return (
                "telemetry guard observed declared activity telemetry but all "
                f"candidate values were zero: {field_zero_text or field} across "
                f"{summary.get('candidate_runs', 0)} candidate run(s)"
            )
        return (
            "telemetry guard did not observe declared activity telemetry: "
            f"{field or 'activity fields'} had no positive runtime evidence across "
            f"{summary.get('candidate_runs', 0)} candidate run(s)"
        )
    if code == "TELEMETRY_BUDGET_STARVED":
        return (
            "telemetry guard observed stage budget starvation: "
            f"{field} had no positive candidate runtime evidence"
        )
    if code == "TELEMETRY_PROTECTED_EFFECT_NOT_OBSERVED":
        return (
            "telemetry guard observed no protected-objective no-regression "
            f"runtime field presence for {field}"
        )
    if code == "TELEMETRY_ACTIVATION_NOT_OBSERVED":
        return (
            "telemetry guard observed no activation evidence for declared "
            f"mechanism telemetry field {field}"
        )
    if code == "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED":
        qualifier = _zero_or_missing_observation(first)
        return (
            f"telemetry guard observed {qualifier} activation evidence for declared "
            f"mechanism {mechanism or 'unknown'} via runtime path(s) {field}"
        )
    if code == "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED":
        qualifier = _zero_or_missing_observation(first)
        return (
            f"telemetry guard observed {qualifier} effect evidence for declared "
            f"mechanism {mechanism or 'unknown'} via runtime path(s) {field}"
        )
    if code == "TELEMETRY_MECHANISM_BUDGET_STARVED":
        qualifier = _zero_or_missing_observation(first)
        return (
            f"telemetry guard observed {qualifier} budget/runtime evidence for declared "
            f"mechanism {mechanism or 'unknown'} via runtime path(s) {field}"
        )
    return f"telemetry guard failed for {category} field {field}: {code}"


def _zero_or_missing_observation(issue: Mapping[str, Any]) -> str:
    try:
        present = int(issue.get("candidate_present", 0) or 0)
        positive = int(issue.get("candidate_positive", 0) or 0)
        false_count = int(issue.get("candidate_false", 0) or 0)
    except (TypeError, ValueError):
        return "no"
    if false_count > 0 and positive == 0:
        return "explicitly inactive"
    if present > 0 and positive == 0:
        return "zero-valued"
    return "no"
