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
    construction_errors = _as_int(runtime.get("construction_errors"))
    portfolio_errors = _as_int(runtime.get("portfolio_errors"))
    policy_errors = _as_int(runtime.get("policy_errors"))
    operator_errors = _as_int(runtime.get("operator_errors"))
    operator_invalid_outputs = _as_int(runtime.get("operator_invalid_outputs"))
    if (
        baseline_issue is None
        and surface_error_issue is None
        and construction_errors <= 0
        and portfolio_errors <= 0
        and policy_errors <= 0
        and operator_errors <= 0
        and operator_invalid_outputs <= 0
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
        surface_issue = _surface_runtime_contract_failure(
            runtime,
            problem_spec=problem_spec,
            selected_surface=selected_surface,
            require_declared_surface=require_declared_surface,
        )
        if surface_issue is not None:
            return surface_issue
        return None

    events = runtime.get("operator_events")
    if not isinstance(events, list):
        events = []
    policy_events = runtime.get("policy_events")
    if not isinstance(policy_events, list):
        policy_events = []
    construction_events = runtime.get("construction_events")
    if not isinstance(construction_events, list):
        construction_events = []
    portfolio_events = runtime.get("portfolio_events")
    if not isinstance(portfolio_events, list):
        portfolio_events = []

    if baseline_issue is not None:
        return {
            "error_category": "baseline_runtime_error",
            "baseline_mode": runtime.get("baseline_mode"),
            "baseline_required": bool(runtime.get("baseline_required")),
            "baseline_error": runtime.get("baseline_error"),
            "construction_errors": construction_errors,
            "portfolio_errors": portfolio_errors,
            "operator_errors": operator_errors,
            "operator_invalid_outputs": operator_invalid_outputs,
            "operator_loaded": _as_int(runtime.get("operator_loaded")),
            "operator_attempts": _as_int(runtime.get("operator_attempts")),
            "operator_accepted": _as_int(runtime.get("operator_accepted")),
            "operator_events": events[:5],
            "detail": baseline_issue,
        }

    if surface_error_issue is not None:
        return surface_error_issue

    if construction_errors > 0:
        return {
            "error_category": "construction_runtime_error",
            "construction_errors": construction_errors,
            "construction_policy_path": runtime.get("construction_policy_path"),
            "construction_surface_loaded": bool(
                runtime.get("construction_surface_loaded")
            ),
            "construction_mode": runtime.get("construction_mode"),
            "construction_bias": runtime.get("construction_bias"),
            "construction_feasible": runtime.get("construction_feasible"),
            "construction_events": construction_events[:5],
            "policy_errors": policy_errors,
            "portfolio_errors": portfolio_errors,
            "operator_errors": operator_errors,
            "operator_invalid_outputs": operator_invalid_outputs,
            "detail": (
                "solver runtime audit reported "
                f"construction_errors={construction_errors}"
            ),
        }

    if portfolio_errors > 0:
        return {
            "error_category": "portfolio_runtime_error",
            "portfolio_errors": portfolio_errors,
            "portfolio_policy_path": runtime.get("portfolio_policy_path"),
            "portfolio_surface_loaded": bool(
                runtime.get("portfolio_surface_loaded")
            ),
            "enabled_components": runtime.get("enabled_components"),
            "component_weights": runtime.get("component_weights"),
            "candidate_limits": runtime.get("candidate_limits"),
            "portfolio_events": portfolio_events[:5],
            "policy_errors": policy_errors,
            "operator_errors": operator_errors,
            "operator_invalid_outputs": operator_invalid_outputs,
            "detail": f"solver runtime audit reported portfolio_errors={portfolio_errors}",
        }

    if policy_errors > 0:
        return {
            "error_category": "policy_runtime_error",
            "policy_errors": policy_errors,
            "policy_path": runtime.get("policy_path"),
            "policy_loaded": bool(runtime.get("policy_loaded")),
            "baseline_time_fraction": runtime.get("baseline_time_fraction"),
            "operator_round_limit": runtime.get("operator_round_limit"),
            "post_baseline_operators_enabled": runtime.get(
                "post_baseline_operators_enabled"
            ),
            "policy_events": policy_events[:5],
            "operator_errors": operator_errors,
            "operator_invalid_outputs": operator_invalid_outputs,
            "detail": f"solver runtime audit reported policy_errors={policy_errors}",
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
    construction_events = issue.get("construction_events")
    if isinstance(construction_events, list) and construction_events:
        first_construction = construction_events[0]
        if isinstance(first_construction, Mapping):
            event_detail = first_construction.get("detail")
            if event_detail:
                return f"{detail}: first_construction_event detail={event_detail}"
    portfolio_events = issue.get("portfolio_events")
    if isinstance(portfolio_events, list) and portfolio_events:
        first_portfolio = portfolio_events[0]
        if isinstance(first_portfolio, Mapping):
            event_detail = first_portfolio.get("detail")
            if event_detail:
                return f"{detail}: first_portfolio_event detail={event_detail}"
    policy_events = issue.get("policy_events")
    if isinstance(policy_events, list) and policy_events:
        first_policy = policy_events[0]
        if isinstance(first_policy, Mapping):
            event_detail = first_policy.get("detail")
            if event_detail:
                return f"{detail}: first_policy_event detail={event_detail}"
    runtime_events = issue.get("runtime_events")
    if isinstance(runtime_events, list) and runtime_events:
        first_runtime_event = runtime_events[0]
        if isinstance(first_runtime_event, Mapping):
            event_detail = first_runtime_event.get("detail")
            if event_detail:
                return f"{detail}: first_runtime_event detail={event_detail}"
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
