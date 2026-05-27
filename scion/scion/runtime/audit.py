"""Helpers for turning solver-side runtime audit fields into evidence failures."""
from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import RunResult, SolverOutput
from scion.runtime.surface_telemetry import (
    component_from_runtime_field,
    declared_error_runtime_fields,
    declared_event_fields_for,
    declared_sibling_field,
    declared_surface_telemetry_fields,
    find_research_surface,
    normalize_surface_name as _surface_normalize_surface_name,
    runtime_path_present,
    runtime_path_value,
)


def runtime_audit_failure_from_result(
    result: RunResult,
    *,
    problem_spec: Any | None = None,
    selected_surface: str | None = None,
    require_declared_surface: bool = False,
) -> dict[str, Any] | None:
    """Return a structured failure if a successful solver run reports errors."""

    return runtime_audit_failure_from_output(
        result.output,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
        require_declared_surface=require_declared_surface,
    )


def runtime_audit_failure_from_output(
    output: SolverOutput | None,
    *,
    problem_spec: Any | None = None,
    selected_surface: str | None = None,
    require_declared_surface: bool = False,
) -> dict[str, Any] | None:
    if output is None:
        if selected_surface is not None or require_declared_surface:
            return _surface_runtime_contract_failure(
                {},
                problem_spec=problem_spec,
                selected_surface=selected_surface,
                require_declared_surface=require_declared_surface,
                runtime_missing=True,
            )
        return None
    return runtime_audit_failure_from_runtime(
        output.runtime,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
        require_declared_surface=require_declared_surface,
    )


def runtime_audit_failure_from_raw(
    raw: Mapping[str, Any],
    *,
    problem_spec: Any | None = None,
    selected_surface: str | None = None,
    require_declared_surface: bool = False,
) -> dict[str, Any] | None:
    runtime = raw.get("runtime")
    if not isinstance(runtime, Mapping):
        if selected_surface is not None or require_declared_surface:
            return _surface_runtime_contract_failure(
                {},
                problem_spec=problem_spec,
                selected_surface=selected_surface,
                require_declared_surface=require_declared_surface,
                runtime_missing=True,
            )
        return None
    return runtime_audit_failure_from_runtime(
        runtime,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
        require_declared_surface=require_declared_surface,
    )


def runtime_audit_failure_from_runtime(
    runtime: Mapping[str, Any],
    *,
    problem_spec: Any | None = None,
    selected_surface: str | None = None,
    require_declared_surface: bool = False,
) -> dict[str, Any] | None:
    """Detect solver-reported runtime audit errors.

    A solver may recover from a surface exception by returning a fallback or
    unchanged incumbent solution. That keeps the process alive, but the
    candidate surface did not actually produce valid evidence. Such runs must be
    treated as runtime failures rather than objective ties.
    """

    surface = find_research_surface(problem_spec, selected_surface)
    baseline_issue = _baseline_audit_failure(runtime)
    surface_error_issue = _declared_surface_runtime_error_failure(
        runtime,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
        surface=surface,
    )
    runtime_error_counts = _runtime_error_counts(
        runtime,
        problem_spec=problem_spec,
        surface=surface,
    )
    surface_contract_issue = None
    if baseline_issue is None and surface_error_issue is None:
        surface_contract_issue = _surface_runtime_contract_failure(
            runtime,
            problem_spec=problem_spec,
            selected_surface=selected_surface,
            require_declared_surface=require_declared_surface,
        )
    fallback_issue = None
    if (
        baseline_issue is None
        and surface_error_issue is None
        and surface_contract_issue is None
    ):
        fallback_issue = _surface_runtime_fallback_failure(
            runtime,
            problem_spec=problem_spec,
            surface=surface,
            selected_surface=selected_surface,
        )
    if (
        baseline_issue is None
        and surface_error_issue is None
        and not runtime_error_counts
        and fallback_issue is None
    ):
        telemetry_issue = (
            _declared_telemetry_consistency_failure(
                runtime,
                problem_spec=problem_spec,
                selected_surface=selected_surface,
                surface=surface,
            )
        )
        if telemetry_issue is not None:
            return telemetry_issue
        if surface_contract_issue is not None:
            return surface_contract_issue
        return None

    if baseline_issue is not None:
        issue: dict[str, Any] = {
            "error_category": "baseline_runtime_error",
            "baseline_mode": runtime.get("baseline_mode"),
            "baseline_required": bool(runtime.get("baseline_required")),
            "baseline_error": runtime.get("baseline_error"),
            "runtime_error_counts": runtime_error_counts,
            "detail": baseline_issue,
        }
        issue.update(runtime_error_counts)
        return issue

    if surface_error_issue is not None:
        return surface_error_issue
    if surface_contract_issue is not None:
        return surface_contract_issue
    if fallback_issue is not None:
        return fallback_issue

    return _runtime_error_issue(runtime, runtime_error_counts)


def _declared_surface_runtime_error_failure(
    runtime: Mapping[str, Any],
    *,
    problem_spec: Any | None,
    selected_surface: str | None,
    surface: Any | None,
) -> dict[str, Any] | None:
    if surface is None:
        return None
    for error_field in declared_error_runtime_fields(
        surface,
        problem_spec=problem_spec,
    ):
        count = _as_int(runtime_path_value(runtime, error_field))
        if count <= 0:
            continue
        component = component_from_runtime_field(error_field)
        event_fields = declared_event_fields_for(runtime, error_field)
        events = _first_list_runtime_value(runtime, event_fields)
        issue: dict[str, Any] = {
            "error_category": _runtime_error_category(component),
            "selected_surface": normalize_surface_name(selected_surface),
            "runtime_error_field": error_field,
            "runtime_error_count": count,
            "runtime_event_fields": event_fields,
            "runtime_events": events[:5],
            error_field: count,
            "detail": f"solver runtime audit reported {error_field}={count}",
        }
        for suffix in ("path", "loaded", "active", "stop_reason"):
            sibling = declared_sibling_field(runtime, error_field, suffix)
            if sibling is not None:
                issue[f"runtime_{suffix}_field"] = sibling
                issue[sibling] = runtime_path_value(runtime, sibling)
        for event_field in event_fields:
            issue[event_field] = runtime_path_value(runtime, event_field)
        return issue
    return None


def _declared_telemetry_consistency_failure(
    runtime: Mapping[str, Any],
    *,
    problem_spec: Any | None,
    selected_surface: str | None,
    surface: Any | None,
) -> dict[str, Any] | None:
    if surface is None:
        return None
    fields = declared_surface_telemetry_fields(surface, problem_spec=problem_spec)
    phase_fields = [
        field
        for field in sorted(fields)
        if str(field).replace(".", "_").endswith("phase_runtime_ms")
        and runtime_path_present(runtime, field)
    ]
    if not phase_fields:
        return None
    elapsed_fields = [
        field
        for field in sorted(fields)
        if str(field).replace(".", "_").endswith(("elapsed_ms", "runtime_ms"))
        and "phase_runtime" not in str(field).replace(".", "_")
        and runtime_path_present(runtime, field)
    ]
    for phase_field in phase_fields:
        phase_runtime = runtime_path_value(runtime, phase_field)
        if not isinstance(phase_runtime, Mapping):
            continue
        elapsed_field, elapsed_ms = _best_elapsed_reference(runtime, elapsed_fields)
        if elapsed_ms <= 0:
            continue
        max_allowed = max(elapsed_ms * 20, elapsed_ms + 60000)
        for phase, value in phase_runtime.items():
            phase_ms = _as_int(value)
            if phase_ms <= max_allowed:
                continue
            component = component_from_runtime_field(phase_field)
            return {
                "error_category": _runtime_telemetry_error_category(component),
                "selected_surface": normalize_surface_name(selected_surface),
                "runtime_elapsed_field": elapsed_field,
                "runtime_phase_field": phase_field,
                "runtime_phase": str(phase),
                "runtime_phase_ms": phase_ms,
                elapsed_field: elapsed_ms,
                phase_field: phase_runtime,
                "detail": (
                    "solver runtime audit reported inconsistent phase runtime: "
                    f"{phase_field}.{phase}={phase_ms} exceeds "
                    f"{elapsed_field}={elapsed_ms}; phase runtime fields must "
                    "record per-phase elapsed delta, not cumulative elapsed time"
                ),
            }
    return None


def _runtime_error_counts(
    runtime: Mapping[str, Any],
    *,
    problem_spec: Any | None,
    surface: Any | None,
) -> dict[str, int]:
    fields = list(declared_error_runtime_fields(surface, problem_spec=problem_spec))
    fields.extend(
        str(key)
        for key in runtime
        if _is_runtime_error_counter_field(str(key))
    )
    counts: dict[str, int] = {}
    for field in dict.fromkeys(fields):
        count = _as_int(runtime_path_value(runtime, field))
        if count > 0:
            counts[field] = count
    return counts


def _runtime_error_issue(
    runtime: Mapping[str, Any],
    counts: Mapping[str, int],
) -> dict[str, Any]:
    if not counts:
        return {
            "error_category": "surface_runtime_error",
            "detail": "solver runtime audit reported runtime error",
        }
    first_field, first_count = next(iter(counts.items()))
    component = component_from_runtime_field(first_field)
    event_fields = declared_event_fields_for(runtime, first_field)
    events = _first_list_runtime_value(runtime, event_fields)
    issue: dict[str, Any] = {
        "error_category": _runtime_error_category(component),
        "runtime_error_field": first_field,
        "runtime_error_count": first_count,
        "runtime_error_counts": dict(counts),
        "runtime_event_fields": event_fields,
        "runtime_events": events[:5],
        first_field: first_count,
        "detail": f"solver runtime audit reported {first_field}={first_count}",
    }
    for field, count in counts.items():
        issue[field] = count
    for suffix in ("path", "loaded", "active", "stop_reason"):
        sibling = declared_sibling_field(runtime, first_field, suffix)
        if sibling is not None:
            issue[f"runtime_{suffix}_field"] = sibling
            issue[sibling] = runtime_path_value(runtime, sibling)
    for event_field in event_fields:
        issue[event_field] = runtime_path_value(runtime, event_field)
    return issue


def _surface_runtime_fallback_failure(
    runtime: Mapping[str, Any],
    *,
    problem_spec: Any | None,
    surface: Any | None,
    selected_surface: str | None,
) -> dict[str, Any] | None:
    if surface is None:
        return None
    event_fields = _surface_event_fields(runtime, problem_spec=problem_spec, surface=surface)
    for field in event_fields:
        events = _first_list_runtime_value(runtime, (field,))
        event = _first_fallback_event(events)
        if event is None:
            continue
        return {
            "error_category": "surface_runtime_fallback",
            "selected_surface": normalize_surface_name(selected_surface),
            "runtime_event_field": field,
            "runtime_event_fields": (field,),
            "runtime_events": events[:5],
            field: events,
            "detail": (
                f"solver runtime audit reported fallback event in {field}: "
                f"{_fallback_event_detail(event)}"
            ),
        }
    return None


def _surface_event_fields(
    runtime: Mapping[str, Any],
    *,
    problem_spec: Any | None,
    surface: Any | None,
) -> tuple[str, ...]:
    fields: list[str] = []
    for telemetry_field in declared_surface_telemetry_fields(
        surface,
        problem_spec=problem_spec,
    ):
        fields.extend(declared_event_fields_for(runtime, telemetry_field))
    fields.extend(
        str(key)
        for key, value in runtime.items()
        if str(key).replace(".", "_").endswith("events") and isinstance(value, list)
    )
    return tuple(dict.fromkeys(field for field in fields if field))


def _first_fallback_event(events: Any) -> Mapping[str, Any] | None:
    if not isinstance(events, (list, tuple)):
        return None
    for event in events:
        if not isinstance(event, Mapping):
            continue
        text = " ".join(
            str(event.get(key) or "")
            for key in ("status", "detail", "message", "reason", "mode")
        ).lower()
        if "fallback" in text:
            return event
    return None


def _fallback_event_detail(event: Mapping[str, Any]) -> str:
    for key in ("detail", "message", "reason", "status", "mode"):
        text = str(event.get(key) or "").strip()
        if text:
            return text
    return "fallback emitted"


def _best_elapsed_reference(
    runtime: Mapping[str, Any],
    elapsed_fields: list[str],
) -> tuple[str, int]:
    for field in elapsed_fields:
        value = _as_int(runtime_path_value(runtime, field))
        if value > 0:
            return field, value
    return "elapsed_ms", 0


def _first_list_runtime_value(
    runtime: Mapping[str, Any],
    fields: tuple[str, ...],
) -> list[Any]:
    for field in fields:
        value = runtime_path_value(runtime, field)
        if isinstance(value, list):
            return value
    return []


def _runtime_error_category(component: str) -> str:
    normalized = _identifier(component)
    return f"{normalized}_runtime_error" if normalized else "surface_runtime_error"


def _runtime_telemetry_error_category(component: str) -> str:
    normalized = _identifier(component)
    if normalized:
        return f"{normalized}_runtime_telemetry_error"
    return "surface_runtime_telemetry_error"


def _is_runtime_error_counter_field(field_name: str) -> bool:
    text = str(field_name or "").strip()
    return (
        text.endswith("_errors")
        or text.endswith(".errors")
        or text.endswith("_error_count")
        or text.endswith(".error_count")
        or text.endswith("_invalid_outputs")
        or text.endswith(".invalid_outputs")
    )


def _identifier(value: str) -> str:
    text = str(value or "").strip().replace(".", "_").strip("_")
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text).strip("_")


def declared_surface_required_runtime_fields(
    problem_spec: Any | None,
    selected_surface: str | None,
) -> tuple[str, ...]:
    """Return declared required runtime fields for a selected surface, if any."""

    surface_name = normalize_surface_name(selected_surface)
    if not surface_name:
        return ()
    surface = _find_research_surface(problem_spec, surface_name)
    if surface is None:
        return ()
    return _required_runtime_fields(surface)


def format_runtime_audit_failure(issue: Mapping[str, Any]) -> str:
    detail = str(issue.get("detail") or "solver runtime audit failed")
    for event_field in _runtime_event_fields(issue):
        events = issue.get(event_field)
        if not isinstance(events, list) or not events:
            continue
        first = events[0]
        if not isinstance(first, Mapping):
            continue
        event_detail = first.get("detail")
        if event_detail:
            return f"{detail}: first_event field={event_field} detail={event_detail}"
        event_subject = first.get("operator") or first.get("component")
        if event_subject:
            return f"{detail}: first_event field={event_field} subject={event_subject}"
    return detail


def _runtime_event_fields(issue: Mapping[str, Any]) -> tuple[str, ...]:
    fields: list[str] = []
    declared = issue.get("runtime_event_fields")
    if isinstance(declared, (list, tuple)):
        fields.extend(str(field) for field in declared if str(field or "").strip())
    for key, value in issue.items():
        if isinstance(value, list) and str(key).replace(".", "_").endswith("events"):
            fields.append(str(key))
    return tuple(dict.fromkeys(field for field in fields if field))


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


def _surface_runtime_contract_failure(
    runtime: Mapping[str, Any],
    *,
    problem_spec: Any | None,
    selected_surface: str | None,
    require_declared_surface: bool,
    runtime_missing: bool = False,
) -> dict[str, Any] | None:
    surface_name = normalize_surface_name(selected_surface)
    if not surface_name:
        if require_declared_surface:
            return _surface_issue(
                selected_surface=None,
                detail="selected research surface is required for runtime audit",
            )
        return None

    surface = _find_research_surface(problem_spec, surface_name)
    if surface is None:
        return _surface_issue(
            selected_surface=surface_name,
            detail=(
                f"selected research surface '{surface_name}' is not declared "
                "in problem_spec.research_surfaces"
            ),
        )

    required_fields = _required_runtime_fields(surface)
    if not required_fields:
        return None

    if runtime_missing:
        return _surface_issue(
            selected_surface=surface_name,
            required_runtime_fields=required_fields,
            missing_runtime_fields=required_fields,
            detail=(
                f"selected research surface '{surface_name}' requires runtime "
                "audit fields but solver output has no runtime mapping"
            ),
        )

    missing: list[str] = []
    empty: list[str] = []
    failed: list[str] = []
    for field in required_fields:
        if field not in runtime:
            missing.append(field)
            continue
        value = runtime[field]
        if _is_empty_evidence_value(value):
            empty.append(field)
            continue
        if _is_error_count_field(field):
            count = _parse_int(value)
            if count is None or count > 0:
                failed.append(field)
            continue
        if _is_generic_true_evidence_field(field) and not _as_truthy(value):
            failed.append(field)

    if not missing and not empty and not failed:
        return None

    parts = [
        f"selected research surface '{surface_name}' failed runtime evidence contract"
    ]
    if missing:
        parts.append("missing=" + ",".join(missing))
    if empty:
        parts.append("empty=" + ",".join(empty))
    if failed:
        parts.append("failed=" + ",".join(failed))

    return _surface_issue(
        selected_surface=surface_name,
        required_runtime_fields=required_fields,
        missing_runtime_fields=tuple(missing),
        empty_runtime_fields=tuple(empty),
        failed_runtime_fields=tuple(failed),
        detail="; ".join(parts),
    )


def _surface_issue(
    *,
    selected_surface: str | None,
    detail: str,
    required_runtime_fields: tuple[str, ...] = (),
    missing_runtime_fields: tuple[str, ...] = (),
    empty_runtime_fields: tuple[str, ...] = (),
    failed_runtime_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "error_category": "surface_runtime_contract_error",
        "selected_surface": selected_surface,
        "required_runtime_fields": required_runtime_fields,
        "missing_runtime_fields": missing_runtime_fields,
        "empty_runtime_fields": empty_runtime_fields,
        "failed_runtime_fields": failed_runtime_fields,
        "detail": detail,
    }


def _find_research_surface(problem_spec: Any | None, name: str) -> Any | None:
    name = normalize_surface_name(name)
    surfaces = getattr(problem_spec, "research_surfaces", None)
    if not surfaces:
        return None
    for surface in surfaces:
        surface_name = str(_get_field(surface, "name") or "").strip()
        if surface_name == name:
            return surface
    return None


def normalize_surface_name(name: Any) -> str:
    """Normalize public compatibility aliases to declared research surfaces."""

    return _surface_normalize_surface_name(name)


def _required_runtime_fields(surface: Any) -> tuple[str, ...]:
    evidence = _get_field(surface, "evidence")
    raw_fields = _get_field(evidence, "required_runtime_fields") if evidence else None
    if raw_fields is None:
        return ()
    if not isinstance(raw_fields, (list, tuple)):
        return ()
    return tuple(str(field).strip() for field in raw_fields if str(field).strip())


def _get_field(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _is_empty_evidence_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set, frozenset)):
        return len(value) == 0
    return False


def _is_error_count_field(field_name: str) -> bool:
    return field_name.endswith("_errors") or field_name.endswith("_error_count")


def _is_generic_true_evidence_field(field_name: str) -> bool:
    return (
        field_name.endswith("_loaded")
        or field_name.endswith("_executed")
        or field_name.endswith("_active")
    )


def _as_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _parse_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
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
