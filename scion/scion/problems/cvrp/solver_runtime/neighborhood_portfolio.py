"""Neighborhood portfolio policy loading and runtime scheduling helpers."""
from __future__ import annotations

import math
from pathlib import Path
import time
from typing import Any, Mapping

from scion.problems.cvrp.models import CvrpInstance
from scion.problems.cvrp.solver_runtime.policy_modules import (
    _call_policy_function,
    _load_policy_module,
)


_MAX_OPERATOR_ROUNDS = 20
_NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH = "policies/neighborhood_portfolio.py"
_MAX_COMPONENT_WEIGHT = 5.0
_MAX_PORTFOLIO_TOP_K = 1000
_MAX_PORTFOLIO_ATTEMPTS = 1_000_000
_ALLOWED_PORTFOLIO_COMPONENTS = frozenset(
    {
        "route_local",
        "route_pair",
        "ruin_recreate",
        "registry_operator",
    }
)
_DEFAULT_ENABLED_COMPONENTS = tuple(sorted(_ALLOWED_PORTFOLIO_COMPONENTS))
_DEFAULT_COMPONENT_WEIGHTS = {
    component: 1.0 for component in _DEFAULT_ENABLED_COMPONENTS
}
_DEFAULT_CANDIDATE_LIMITS = {
    "max_rounds": _MAX_OPERATOR_ROUNDS,
    "top_k": _MAX_PORTFOLIO_TOP_K,
    "total_attempts": _MAX_PORTFOLIO_ATTEMPTS,
    "per_component_attempts": _MAX_PORTFOLIO_ATTEMPTS,
}


def _load_neighborhood_portfolio(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _portfolio_audit_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_portfolio_event(audit, "error", "portfolio policy path escapes workspace")
        audit["portfolio_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"portfolio policy load failed: {exc}")
        return audit

    audit["portfolio_surface_loaded"] = True
    audit["enabled_components"] = _portfolio_enabled_components(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["component_weights"] = _portfolio_component_weights(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["candidate_limits"] = _portfolio_candidate_limits(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    return audit


def _portfolio_audit_defaults(
    portfolio: dict[str, Any] | None = None,
) -> dict[str, Any]:
    audit = dict(portfolio or {})
    audit.setdefault("portfolio_policy_path", _NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH)
    audit.setdefault("portfolio_surface_loaded", False)
    audit.setdefault("portfolio_errors", 0)
    audit.setdefault("portfolio_events", [])
    audit.setdefault("enabled_components", list(_DEFAULT_ENABLED_COMPONENTS))
    audit.setdefault("component_weights", dict(_DEFAULT_COMPONENT_WEIGHTS))
    audit.setdefault("candidate_limits", dict(_DEFAULT_CANDIDATE_LIMITS))
    audit.setdefault(
        "component_attempts",
        {component: 0 for component in audit["enabled_components"]},
    )
    audit.setdefault(
        "component_accepted",
        {component: 0 for component in audit["enabled_components"]},
    )
    audit.setdefault(
        "component_runtime_ms",
        {component: 0 for component in audit["enabled_components"]},
    )
    audit.setdefault("portfolio_stop_reason", "")
    audit.setdefault(
        "portfolio_effective_round_limit",
        int(audit["candidate_limits"].get("max_rounds", _MAX_OPERATOR_ROUNDS))
        if isinstance(audit.get("candidate_limits"), Mapping)
        else _MAX_OPERATOR_ROUNDS,
    )
    return audit


def _portfolio_enabled_components(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> list[str]:
    try:
        value = _call_policy_function(module, "enabled_components", instance, time_limit_sec)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"enabled_components failed: {exc}")
        return list(_DEFAULT_ENABLED_COMPONENTS)
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"enabled_components returned non-sequence value {value!r}",
        )
        return list(_DEFAULT_ENABLED_COMPONENTS)

    enabled: list[str] = []
    seen: set[str] = set()
    for item in value:
        component = str(item).strip()
        if component not in _ALLOWED_PORTFOLIO_COMPONENTS:
            audit["portfolio_errors"] += 1
            _record_portfolio_event(
                audit,
                "error",
                f"enabled_components contains unknown component {component!r}",
            )
            continue
        if component not in seen:
            seen.add(component)
            enabled.append(component)
    if not enabled:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            "enabled_components produced no valid enabled components",
        )
        return list(_DEFAULT_ENABLED_COMPONENTS)
    return enabled


def _portfolio_component_weights(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> dict[str, float]:
    weights = dict(_DEFAULT_COMPONENT_WEIGHTS)
    try:
        value = _call_policy_function(module, "component_weights", instance, time_limit_sec)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"component_weights failed: {exc}")
        return weights
    if not isinstance(value, Mapping):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"component_weights returned non-mapping value {value!r}",
        )
        return weights

    for raw_component, raw_weight in value.items():
        component = str(raw_component).strip()
        if component not in _ALLOWED_PORTFOLIO_COMPONENTS:
            audit["portfolio_errors"] += 1
            _record_portfolio_event(
                audit,
                "error",
                f"component_weights contains unknown component {component!r}",
            )
            continue
        weight = _portfolio_float(
            raw_weight,
            default=weights[component],
            minimum=0.0,
            maximum=_MAX_COMPONENT_WEIGHT,
            field_name=f"component_weights[{component}]",
            audit=audit,
        )
        weights[component] = weight
    return weights


def _portfolio_candidate_limits(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> dict[str, int]:
    limits = dict(_DEFAULT_CANDIDATE_LIMITS)
    try:
        value = _call_policy_function(module, "candidate_limits", instance, time_limit_sec)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"candidate_limits failed: {exc}")
        return limits
    if not isinstance(value, Mapping):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"candidate_limits returned non-mapping value {value!r}",
        )
        return limits

    known_limit_keys = {
        "max_rounds",
        "top_k",
        "total_attempts",
        "per_component_attempts",
    }
    for raw_key, raw_limit in value.items():
        key = str(raw_key).strip()
        if key in _ALLOWED_PORTFOLIO_COMPONENTS:
            limits[key] = _portfolio_int(
                raw_limit,
                default=limits.get(key, limits["per_component_attempts"]),
                minimum=0,
                maximum=_MAX_PORTFOLIO_ATTEMPTS,
                field_name=f"candidate_limits[{key}]",
                audit=audit,
            )
            continue
        if key not in known_limit_keys:
            audit["portfolio_errors"] += 1
            _record_portfolio_event(
                audit,
                "error",
                f"candidate_limits contains unknown key {key!r}",
            )
            continue
        maximum = _MAX_OPERATOR_ROUNDS if key == "max_rounds" else _MAX_PORTFOLIO_ATTEMPTS
        if key == "top_k":
            maximum = _MAX_PORTFOLIO_TOP_K
        limits[key] = _portfolio_int(
            raw_limit,
            default=limits[key],
            minimum=0,
            maximum=maximum,
            field_name=f"candidate_limits[{key}]",
            audit=audit,
        )
    return limits


def _portfolio_float(
    value: Any,
    *,
    default: float,
    minimum: float,
    maximum: float,
    field_name: str,
    audit: dict[str, Any],
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name} returned non-numeric value {value!r}",
        )
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name} returned non-finite value {value!r}",
        )
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _portfolio_int(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
    field_name: str,
    audit: dict[str, Any],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name} returned non-integer value {value!r}",
        )
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _record_portfolio_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("portfolio_events", [])
    if len(events) >= 10:
        return
    events.append(
        {
            "policy": _NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH,
            "status": status,
            "detail": detail,
        }
    )


def _apply_neighborhood_portfolio(
    operators: tuple[Any, ...],
    *,
    audit: dict[str, Any],
    max_operator_rounds: int,
) -> tuple[Any, ...]:
    enabled = {
        str(component)
        for component in audit.get("enabled_components", [])
        if str(component) in _ALLOWED_PORTFOLIO_COMPONENTS
    }
    component_weights = audit.get("component_weights")
    if not isinstance(component_weights, Mapping):
        component_weights = _DEFAULT_COMPONENT_WEIGHTS
    candidate_limits = audit.get("candidate_limits")
    if not isinstance(candidate_limits, Mapping):
        candidate_limits = _DEFAULT_CANDIDATE_LIMITS

    for component in enabled:
        audit["component_attempts"].setdefault(component, 0)
        audit["component_accepted"].setdefault(component, 0)
        audit["component_runtime_ms"].setdefault(component, 0)

    effective_rounds = min(
        max_operator_rounds,
        int(candidate_limits.get("max_rounds", _MAX_OPERATOR_ROUNDS)),
    )
    audit["portfolio_effective_round_limit"] = max(0, effective_rounds)
    top_k = max(0, int(candidate_limits.get("top_k", _MAX_PORTFOLIO_TOP_K)))

    filtered = [operator for operator in operators if operator.component in enabled]
    filtered.sort(
        key=lambda op: (
            -op.weight * float(component_weights.get(op.component, 1.0)),
            op.order,
        )
    )
    if top_k == 0:
        audit["operator_loaded"] = 0
        audit["portfolio_stop_reason"] = "top_k_zero"
        return tuple()
    scheduled = tuple(filtered[:top_k])
    audit["operator_loaded"] = len(scheduled)
    if operators and not scheduled and not audit["portfolio_stop_reason"]:
        audit["portfolio_stop_reason"] = "no_enabled_components"
    return scheduled


def _portfolio_attempt_limit_reached(
    audit: dict[str, Any],
    component: str,
) -> bool:
    candidate_limits = audit.get("candidate_limits")
    if not isinstance(candidate_limits, Mapping):
        return False
    component_attempts = audit.get("component_attempts")
    if not isinstance(component_attempts, Mapping):
        return False
    total_limit = int(candidate_limits.get("total_attempts", _MAX_PORTFOLIO_ATTEMPTS))
    total_attempts = sum(_as_nonnegative_int(value) for value in component_attempts.values())
    if total_attempts >= total_limit:
        return True
    component_limit = int(
        candidate_limits.get(
            component,
            candidate_limits.get("per_component_attempts", _MAX_PORTFOLIO_ATTEMPTS),
        )
    )
    return _as_nonnegative_int(component_attempts.get(component)) >= component_limit


def _record_component_runtime(
    audit: dict[str, Any],
    component: str,
    start_ns: int,
) -> None:
    elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
    runtime = audit["component_runtime_ms"]
    runtime[component] = _as_nonnegative_int(runtime.get(component)) + elapsed_ms


def _as_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
