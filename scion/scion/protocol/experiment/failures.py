from __future__ import annotations

from typing import Any

from scion.core.models import RunResult
from .values import _as_int, _bounded_text, _increment_category


def _candidate_process_failure_category(result: RunResult) -> str:
    category = str(result.error_category or "").strip().lower()
    if category in {"timeout", "oom", "crash"}:
        return category
    return "process_error"


def _candidate_audit_failure_category(issue: dict[str, Any]) -> str:
    raw = str(issue.get("error_category") or "").strip().lower()
    if raw == "operator_runtime_error":
        if _as_int(issue.get("operator_invalid_outputs")) > 0:
            return "invalid_output"
        return "operator_error"
    if raw == "policy_runtime_error":
        return "policy_error"
    if raw == "construction_runtime_error":
        return "construction_error"
    if raw == "portfolio_runtime_error":
        return "portfolio_error"
    if raw == "solver_algorithm_runtime_error":
        return "solver_algorithm_error"
    if raw == "surface_runtime_contract_error":
        return "surface_contract_error"
    if raw == "baseline_runtime_error":
        return "baseline_error"
    return raw or "runtime_error"


def _bounded_runtime_failure_from_audit(
    issue: dict[str, Any],
    *,
    category: str,
) -> dict[str, Any]:
    component = "runtime_audit"
    for candidate in ("component", "operator", "policy_path", "construction_policy_path", "portfolio_policy_path"):
        value = issue.get(candidate)
        if value:
            component = str(value)
            break
    return _bounded_runtime_failure(
        category=category,
        code=str(issue.get("error_category") or category),
        surface=issue.get("selected_surface"),
        component=component,
        detail_summary=str(issue.get("detail") or "solver runtime audit failed"),
    )


def _bounded_runtime_failure(
    *,
    category: str,
    code: str,
    surface: Any,
    component: str,
    detail_summary: str,
) -> dict[str, Any]:
    return {
        "category": _bounded_text(category, 80),
        "code": _bounded_text(code, 120),
        "surface": _bounded_text(surface, 120),
        "component": _bounded_text(component, 160),
        "detail_summary": _bounded_text(detail_summary, 240),
    }


def _format_runtime_failure_categories(categories: dict[str, int]) -> str:
    parts = [
        f"{category}:{count}"
        for category, count in sorted(categories.items())
        if count > 0
    ]
    return ";".join(parts[:8])


__all__ = [
    "_bounded_runtime_failure",
    "_bounded_runtime_failure_from_audit",
    "_candidate_audit_failure_category",
    "_candidate_process_failure_category",
    "_format_runtime_failure_categories",
]
