"""Runtime telemetry audit helpers for solver-design smoke."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.runtime.surface_telemetry import (
    declared_event_fields_for,
    declared_surface_telemetry_fields,
    find_research_surface,
    runtime_path_present,
    runtime_path_value,
)

from .utils import _attr

if TYPE_CHECKING:
    from scion.proposal.tools import ProposalToolContext
else:
    ProposalToolContext = Any


def _runtime_smoke_audit_failure(
    raw: Mapping[str, Any],
    *,
    context: ProposalToolContext,
    selected_surface: str,
) -> Mapping[str, Any] | None:
    from scion.runtime.audit import runtime_audit_failure_from_raw

    problem_spec = _problem_spec_for_runtime_audit(context.problem_spec)
    return runtime_audit_failure_from_raw(
        raw,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
    )


def _problem_spec_for_runtime_audit(problem_spec: Any) -> Any:
    if (
        str(_attr(problem_spec, "spec_version", "") or "") == "problem-v1"
        and _attr(problem_spec, "id") is not None
    ):
        return legacy_problem_spec_from_v1(problem_spec)
    return problem_spec


def _compact_runtime_smoke_payload(
    runtime: Any,
    *,
    context: ProposalToolContext | None = None,
    selected_surface: str | None = None,
) -> dict[str, Any]:
    if not isinstance(runtime, Mapping):
        return {}
    fields = _declared_runtime_smoke_fields(
        runtime,
        context=context,
        selected_surface=selected_surface,
    )
    return {
        field: _bounded_runtime_value(runtime_path_value(runtime, field))
        for field in fields
        if runtime_path_present(runtime, field)
    }


def _compact_runtime_audit_failure(value: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "error_category",
        "detail",
        "failed_runtime_fields",
        "runtime_error_field",
        "runtime_error_count",
        "runtime_events",
    )
    return {key: value.get(key) for key in keys if key in value}


def _declared_runtime_smoke_fields(
    runtime: Mapping[str, Any],
    *,
    context: ProposalToolContext | None,
    selected_surface: str | None,
) -> tuple[str, ...]:
    problem_spec = (
        _problem_spec_for_runtime_audit(context.problem_spec)
        if context is not None
        else None
    )
    surface = find_research_surface(problem_spec, selected_surface)
    fields = set(declared_surface_telemetry_fields(surface, problem_spec=problem_spec))
    for field in tuple(fields):
        fields.update(declared_event_fields_for(runtime, field))
    if fields:
        return tuple(sorted(fields))
    return tuple(
        key
        for key, value in runtime.items()
        if _compact_runtime_value_allowed(value)
    )[:24]


def _bounded_runtime_value(value: Any) -> Any:
    if isinstance(value, str):
        return value[:240]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {
            str(key)[:120]: _bounded_runtime_value(item)
            for key, item in list(value.items())[:12]
        }
    if isinstance(value, (list, tuple)):
        return [_bounded_runtime_value(item) for item in list(value)[:5]]
    return str(value)[:240]


def _compact_runtime_value_allowed(value: Any) -> bool:
    return isinstance(value, (bool, int, float, str, Mapping, list, tuple))
