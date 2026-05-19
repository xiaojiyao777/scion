"""Shared helpers for CVRP adapter preview validators."""
from __future__ import annotations

import math
import types
from typing import Any, Mapping

from scion.problems.cvrp.models import CvrpInstance
from scion.problems.cvrp.surface_policy import (
    is_active_research_surface,
    is_legacy_research_surface,
)
from scion.problems.cvrp.surface_schema import (
    _POLICY_PREVIEW_TIME_LIMIT_SEC,
)

def _policy_preview_result(
    surface: str,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    active = is_active_research_surface(surface)
    return {
        "passed": not issues,
        "surface": surface,
        "active_research_surface": active,
        "legacy_surface": is_legacy_research_surface(surface),
        "preview_scope": "active" if active else "legacy_compatibility",
        "checks": checks,
        "issues": issues,
        "synthetic_instance": {
            "name": "synthetic_preview",
            "customer_ids": [1, 2, 3],
            "customer_count": 3,
            "capacity": 10,
        },
        "workspace_materialized": False,
        "verification_run": False,
    }

def _preview_mapping_section(
    name: str,
    value: Any,
    issues: list[str],
) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    issues.append(f"{name} returned non-mapping value {value!r}")
    return None

def _preview_section_keys(
    name: str,
    section: Mapping[str, Any],
    *,
    allowed: frozenset[str],
    required: frozenset[str],
    require_missing: bool,
    issues: list[str],
) -> None:
    unknown = sorted(str(key) for key in section if str(key) not in allowed)
    if unknown:
        issues.append(f"{name} returned unknown keys {unknown}")
    if require_missing:
        missing = sorted(key for key in required if key not in section)
        if missing:
            issues.append(f"enabled {name} missing required keys {missing}")

def _preview_policy_keys(
    name: str,
    plan: Mapping[str, Any],
    *,
    allowed: frozenset[str],
    issues: list[str],
) -> None:
    unknown = sorted(str(key) for key in plan if str(key) not in allowed)
    if unknown:
        issues.append(f"{name} returned unknown keys {unknown}")

def _preview_weight_mapping(
    name: str,
    value: Any,
    *,
    allowed: frozenset[str],
    issues: list[str],
) -> None:
    if not isinstance(value, Mapping):
        issues.append(f"{name} returned non-mapping value {value!r}")
        return
    for key, weight in value.items():
        item = str(key).strip()
        if item not in allowed:
            issues.append(f"{name} returned unknown key {item!r}")
            continue
        _check_number(
            f"{name}[{item}]",
            weight,
            minimum=0.0,
            maximum=5.0,
            integral=False,
            issues=issues,
        )

def _preview_limit_mapping(
    name: str,
    value: Mapping[str, Any],
    *,
    ranges: Mapping[str, tuple[int, int]],
    issues: list[str],
) -> None:
    for key, limit in value.items():
        item = str(key).strip()
        if item not in ranges:
            issues.append(f"{name} returned unknown key {item!r}")
            continue
        lo, hi = ranges[item]
        _check_number(
            f"{name}[{item}]",
            limit,
            minimum=lo,
            maximum=hi,
            integral=True,
            issues=issues,
        )

def _preview_baseline_params_mapping(
    params: Mapping[str, Any],
    issues: list[str],
) -> None:
    allowed_keys = {
        "destroy_ratio",
        "segment_length",
        "reaction_factor",
        "vns_max_no_improve",
        "use_vns",
        "cw_threshold",
        "vns_threshold",
        "alns_threshold",
        "max_destroy_customers",
    }
    unknown = sorted(str(key) for key in params if str(key) not in allowed_keys)
    if unknown:
        issues.append(f"baseline.params returned unknown keys {unknown}")
    if "destroy_ratio" in params:
        _check_destroy_ratio(params["destroy_ratio"], issues)
    if "segment_length" in params:
        _check_number(
            "baseline.params.segment_length",
            params["segment_length"],
            minimum=1,
            maximum=1000,
            integral=True,
            issues=issues,
        )
    if "reaction_factor" in params:
        _check_number(
            "baseline.params.reaction_factor",
            params["reaction_factor"],
            minimum=0.01,
            maximum=1.0,
            integral=False,
            issues=issues,
        )
    if "vns_max_no_improve" in params:
        _check_number(
            "baseline.params.vns_max_no_improve",
            params["vns_max_no_improve"],
            minimum=0,
            maximum=20000,
            integral=True,
            issues=issues,
        )
    if "use_vns" in params and not isinstance(params["use_vns"], bool):
        issues.append(f"baseline.params.use_vns returned non-bool value {params['use_vns']!r}")
    for name in ("cw_threshold", "vns_threshold", "alns_threshold"):
        if name in params:
            _check_number(
                f"baseline.params.{name}",
                params[name],
                minimum=0,
                maximum=10000,
                integral=True,
                issues=issues,
            )
    if "max_destroy_customers" in params:
        _check_number(
            "baseline.params.max_destroy_customers",
            params["max_destroy_customers"],
            minimum=1,
            maximum=500,
            integral=True,
            issues=issues,
        )

def _check_sequence_literals(
    field: str,
    value: Any,
    *,
    allowed: frozenset[str],
    allow_empty: bool,
    issues: list[str],
) -> None:
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        issues.append(f"{field} returned non-sequence value {value!r}")
        return
    normalized = [str(item).strip() for item in value]
    bad = [item for item in normalized if item not in allowed]
    if bad:
        issues.append(f"{field} returned unknown values {bad}")
    if not normalized and not allow_empty:
        issues.append(f"{field} returned an empty sequence")

def _check_destroy_ratio(value: Any, issues: list[str]) -> None:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        issues.append(f"destroy_ratio returned non-pair value {value!r}")
        return
    if len(value) != 2:
        issues.append(f"destroy_ratio must contain exactly two values, got {value!r}")
        return
    before = len(issues)
    _check_number(
        "destroy_ratio[0]",
        value[0],
        minimum=0.01,
        maximum=0.80,
        integral=False,
        issues=issues,
    )
    _check_number(
        "destroy_ratio[1]",
        value[1],
        minimum=0.01,
        maximum=0.80,
        integral=False,
        issues=issues,
    )
    if len(issues) != before:
        return
    if float(value[0]) > float(value[1]):
        issues.append(
            f"destroy_ratio lower bound {value[0]!r} exceeds upper bound {value[1]!r}"
        )

_PREVIEW_FAILED = object()

def _call_preview_function(
    module: types.ModuleType,
    name: str,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> Any:
    func = getattr(module, name, None)
    if not callable(func):
        issues.append(f"missing callable {name}")
        checks.append({"name": name, "passed": False, "detail": "missing callable"})
        return _PREVIEW_FAILED
    try:
        value = func(instance, _POLICY_PREVIEW_TIME_LIMIT_SEC)
    except Exception as exc:
        issues.append(f"{name} raised during synthetic preview: {exc}")
        checks.append({"name": name, "passed": False, "detail": str(exc)})
        return _PREVIEW_FAILED
    checks.append({"name": name, "passed": True, "detail": repr(value)[:200]})
    return value

def _check_number(
    field: str,
    value: Any,
    *,
    minimum: float,
    maximum: float,
    integral: bool,
    issues: list[str],
) -> None:
    if isinstance(value, bool):
        issues.append(f"{field} returned bool where numeric value is required")
        return
    if integral:
        if not isinstance(value, int):
            issues.append(f"{field} returned non-integer value {value!r}")
            return
        numeric = float(value)
    else:
        if not isinstance(value, (int, float)):
            issues.append(f"{field} returned non-numeric value {value!r}")
            return
        numeric = float(value)
    if not math.isfinite(numeric):
        issues.append(f"{field} returned non-finite value {value!r}")
        return
    if numeric < minimum or numeric > maximum:
        issues.append(f"{field}={value!r} outside [{minimum}, {maximum}]")
