"""Telemetry summary fallback checks when no explicit telemetry is expected."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from scion.runtime.telemetry_guard.declarations import (
    declared_activity_runtime_fields,
    declared_stage_budget_runtime_fields,
)
from scion.runtime.telemetry_guard.evidence import _as_bool
from scion.runtime.telemetry_guard.issues import _guard_issue
from scion.runtime.telemetry_guard.observations import _runtime_field_summary
from scion.runtime.telemetry_guard.utils import _field


def _record_no_expected_telemetry_fallbacks(
    *,
    surface: Any,
    evidence: Any,
    candidate_runtimes: Sequence[Mapping[str, Any]],
    champion_runtimes: Sequence[Mapping[str, Any]],
    implicit_activity_claim: bool,
    field_summaries: dict[str, dict[str, Any]],
    failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    zero_activity_issue_code: Callable[[str, Mapping[str, Any]], str],
) -> None:
    activity_fields = declared_activity_runtime_fields(surface)
    if activity_fields:
        activity_positive = 0
        activity_present = 0
        activity_missing = 0
        activity_champion_positive = 0
        for field in activity_fields:
            summary = field_summaries.get(field)
            if summary is None:
                summary = _runtime_field_summary(
                    field,
                    candidate_runtimes=candidate_runtimes,
                    champion_runtimes=champion_runtimes,
                )
                field_summaries[field] = summary
            activity_positive += int(summary["candidate_positive"])
            activity_present += int(summary["candidate_present"])
            activity_missing += int(summary["candidate_missing"])
            activity_champion_positive += int(summary["champion_positive"])
        if candidate_runtimes and activity_positive == 0:
            issue = _guard_issue(
                zero_activity_issue_code(
                    "activity",
                    {
                        "candidate_present": activity_present,
                        "candidate_missing": activity_missing,
                        "candidate_positive": activity_positive,
                    },
                ),
                category="activity",
                field=",".join(activity_fields),
                severity=(
                    "fail"
                    if implicit_activity_claim
                    or _as_bool(_field(evidence, "fail_closed_on_zero_activity"))
                    else "warn"
                ),
                summary={
                    "candidate_runs": len(candidate_runtimes),
                    "candidate_positive": activity_positive,
                    "candidate_present": activity_present,
                    "candidate_missing": activity_missing,
                    "champion_positive": activity_champion_positive,
                },
            )
            (failures if issue["severity"] == "fail" else warnings).append(issue)

    budget_fields = declared_stage_budget_runtime_fields(surface)
    for field in budget_fields:
        if field in field_summaries:
            continue
        summary = _runtime_field_summary(
            field,
            candidate_runtimes=candidate_runtimes,
            champion_runtimes=champion_runtimes,
        )
        field_summaries[field] = summary
        if (
            candidate_runtimes
            and summary["candidate_positive"] == 0
            and summary["champion_positive"] > 0
        ):
            issue = _guard_issue(
                "TELEMETRY_BUDGET_STARVED",
                category="budget",
                field=field,
                severity=(
                    "fail"
                    if _as_bool(
                        _field(evidence, "fail_closed_on_stage_budget_starvation")
                    )
                    else "warn"
                ),
                summary=summary,
            )
            (failures if issue["severity"] == "fail" else warnings).append(issue)
