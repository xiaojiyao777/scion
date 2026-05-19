"""Failure classification and repair cues for algorithm-smoke feedback."""

from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.tools.previews.algorithm_smoke_feedback_runtime import (
    _compact_algorithm_smoke_telemetry_guard,
    _telemetry_guard_primary_issue,
)
from scion.proposal.tools.previews.algorithm_smoke_feedback_static import (
    _failed_check_summaries,
)
from scion.proposal.tools.previews.algorithm_smoke_feedback_text import (
    _ALGORITHM_SMOKE_AGENT_LIST_ITEMS,
    _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
    _compact_agent_text,
    _compact_agent_text_list,
    _first_mapping,
    _mapping_or_none,
    _runtime_event_text,
)
from scion.proposal.tools.surface import _drop_empty_items
from scion.proposal.tools.utils import _limit_text


def _algorithm_smoke_selected_surface(
    raw_payload: Mapping[str, Any],
    runtime_smoke: Mapping[str, Any] | None,
) -> str | None:
    if runtime_smoke is not None and runtime_smoke.get("selected_surface"):
        return str(runtime_smoke.get("selected_surface"))
    problem_preview = _mapping_or_none(raw_payload.get("problem_preview"))
    if problem_preview is not None and problem_preview.get("surface"):
        return str(problem_preview.get("surface"))
    hypothesis = _mapping_or_none(raw_payload.get("hypothesis"))
    hypothesis_summary = (
        _mapping_or_none(hypothesis.get("hypothesis")) if hypothesis else None
    )
    if hypothesis_summary is not None and hypothesis_summary.get("change_locus"):
        return str(hypothesis_summary.get("change_locus"))
    return None


def _algorithm_smoke_case_count(runtime_smoke: Mapping[str, Any] | None) -> int | None:
    if runtime_smoke is None:
        return None
    value = runtime_smoke.get("case_count")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _algorithm_smoke_primary_issue(
    raw_payload: Mapping[str, Any],
    *,
    runtime_smoke: Mapping[str, Any] | None,
    telemetry_guard: Mapping[str, Any] | None,
    subprocess_tail: Mapping[str, Any] | None,
) -> str:
    candidates: list[Any] = []
    if runtime_smoke is not None:
        issues = runtime_smoke.get("issues")
        if isinstance(issues, (list, tuple)):
            candidates.extend(issues)
        elif issues:
            candidates.append(issues)
        audit = _mapping_or_none(runtime_smoke.get("runtime_audit_failure"))
        if audit is not None:
            candidates.extend(
                [
                    audit.get("detail"),
                    _runtime_event_text(audit.get("solver_algorithm_events")),
                    audit.get("error_category"),
                ]
            )
        runtime = _mapping_or_none(runtime_smoke.get("runtime"))
        if runtime is not None:
            candidates.extend(
                [
                    _runtime_event_text(runtime.get("solver_algorithm_events")),
                    (
                        f"solver_algorithm_errors={runtime.get('solver_algorithm_errors')}"
                        if runtime.get("solver_algorithm_errors") not in (None, "")
                        else None
                    ),
                ]
            )
    telemetry_issue = _telemetry_guard_primary_issue(telemetry_guard)
    if telemetry_issue:
        candidates.append(telemetry_issue)
    if subprocess_tail is not None:
        candidates.extend(
            [
                subprocess_tail.get("detail"),
                subprocess_tail.get("stderr_tail"),
                subprocess_tail.get("stdout_tail"),
            ]
        )
    telemetry_static = _mapping_or_none(raw_payload.get("telemetry_static_preview"))
    if telemetry_static is not None and telemetry_static.get("passed") is False:
        candidates.extend(_compact_agent_text_list(telemetry_static.get("issues")))
    candidates.extend(
        [
            raw_payload.get("issue_summary"),
            raw_payload.get("errors"),
        ]
    )
    for candidate in candidates:
        text = _compact_agent_text(candidate)
        if text:
            return text
    return ""


def _algorithm_smoke_failure_class(
    *,
    passed: bool,
    raw_payload: Mapping[str, Any],
    runtime_smoke: Mapping[str, Any] | None,
    telemetry_guard: Mapping[str, Any] | None,
    primary_issue: str,
    subprocess_tail: Mapping[str, Any] | None,
) -> str:
    if passed:
        return "passed"
    if telemetry_guard is not None and telemetry_guard.get("triggered"):
        return "telemetry_guard_failure"
    telemetry_static = _mapping_or_none(raw_payload.get("telemetry_static_preview"))
    if telemetry_static is not None and telemetry_static.get("passed") is False:
        return "telemetry_static_preview_failure"
    if runtime_smoke is not None:
        if runtime_smoke.get("runtime_audit_failure") not in (None, "", {}, []):
            return "runtime_audit_failure"
        run = _mapping_or_none(runtime_smoke.get("run"))
        if run is not None and run.get("success") is False:
            return "runtime_execution_failure"
    if subprocess_tail is not None and subprocess_tail.get("error_category"):
        return "runtime_execution_failure"
    lowered = primary_issue.lower()
    if "zero active search" in lowered:
        return "zero_search_effort"
    if "low active search" in lowered or "under-spent" in lowered:
        return "low_search_effort"
    if "micro-benchmark" in lowered or "objective regression" in lowered:
        return "objective_regression"
    if _algorithm_smoke_failed_checks(
        raw_payload,
        runtime_smoke=runtime_smoke,
        primary_issue="",
        failure_class="static_contract_failure",
    ):
        return "static_contract_failure"
    return "algorithm_smoke_failure"


def _algorithm_smoke_repair_hints(
    raw_payload: Mapping[str, Any],
    *,
    runtime_smoke: Mapping[str, Any] | None,
    telemetry_guard: Mapping[str, Any] | None,
) -> list[str]:
    hints: list[str] = []
    if runtime_smoke is not None:
        hints.extend(_compact_agent_text_list(runtime_smoke.get("repair_guidance")))
    for section_name in ("patch", "hypothesis", "problem_preview"):
        section = _mapping_or_none(raw_payload.get(section_name))
        if section is None:
            continue
        hints.extend(_compact_agent_text_list(section.get("repair_guidance")))
        hints.extend(_compact_agent_text_list(section.get("repair_hints")))
    telemetry_static = _mapping_or_none(raw_payload.get("telemetry_static_preview"))
    if telemetry_static is not None and telemetry_static.get("passed") is False:
        hints.extend(_compact_agent_text_list(telemetry_static.get("repair_hints")))
    if telemetry_guard is not None and telemetry_guard.get("triggered"):
        first_failure = _first_mapping(telemetry_guard.get("failures"))
        code = str(first_failure.get("code") or "").strip() if first_failure else ""
        field = str(first_failure.get("field") or "").strip() if first_failure else ""
        mechanism = (
            str(first_failure.get("mechanism") or "").strip()
            if first_failure
            else ""
        )
        if code == "TELEMETRY_PROTECTED_EFFECT_NOT_OBSERVED":
            hint = (
                "Ensure the candidate emits the protected-objective "
                "no-regression runtime field"
            )
        else:
            hint = "Ensure the candidate emits positive runtime evidence"
        if mechanism:
            hint += f" for declared mechanism {mechanism}"
        if field:
            hint += f" via {field}"
        hints.append(hint + ".")
    return list(dict.fromkeys(hints))[:_ALGORITHM_SMOKE_AGENT_LIST_ITEMS]


def _algorithm_smoke_failed_checks(
    raw_payload: Mapping[str, Any],
    *,
    runtime_smoke: Mapping[str, Any] | None,
    primary_issue: str,
    failure_class: str,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for section_name in ("hypothesis", "patch", "problem_preview"):
        section = _mapping_or_none(raw_payload.get(section_name))
        checks.extend(_failed_check_summaries(section, prefix=section_name))
    if runtime_smoke is not None:
        telemetry = _mapping_or_none(runtime_smoke.get("telemetry_guard"))
        if telemetry is not None and telemetry.get("passed") is False:
            first_failure = _first_mapping(telemetry.get("failures"))
            checks.append(
                _drop_empty_items(
                    {
                        "name": "runtime_smoke.telemetry_guard",
                        "passed": False,
                        "detail": _telemetry_guard_primary_issue(
                            _compact_algorithm_smoke_telemetry_guard(telemetry)
                        ),
                        "code": first_failure.get("code") if first_failure else None,
                    }
                )
            )
    telemetry_static = _mapping_or_none(raw_payload.get("telemetry_static_preview"))
    if telemetry_static is not None and telemetry_static.get("passed") is False:
        checks.append(
            _drop_empty_items(
                {
                    "name": "telemetry_static_preview",
                    "passed": False,
                    "detail": _limit_text(
                        "; ".join(
                            _compact_agent_text_list(telemetry_static.get("issues"))
                        ),
                        _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
                    ),
                }
            )
        )
    if not checks and primary_issue:
        checks.append(
            {
                "name": failure_class or "algorithm_smoke",
                "passed": False,
                "detail": _limit_text(primary_issue, _ALGORITHM_SMOKE_AGENT_TEXT_CHARS),
            }
        )
    return checks[:_ALGORITHM_SMOKE_AGENT_LIST_ITEMS]


__all__ = [
    "_algorithm_smoke_case_count",
    "_algorithm_smoke_failed_checks",
    "_algorithm_smoke_failure_class",
    "_algorithm_smoke_primary_issue",
    "_algorithm_smoke_repair_hints",
    "_algorithm_smoke_selected_surface",
]
