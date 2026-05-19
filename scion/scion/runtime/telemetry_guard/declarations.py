"""Declared research-surface telemetry extraction."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scion.runtime.audit import normalize_surface_name
from scion.runtime.telemetry_guard.utils import (
    _field,
    _fields_with_suffix,
    _string_list,
)

_ACTIVITY_SUFFIXES = (
    "_search_iterations",
    "_iterations",
    "_move_attempts",
    "_attempts",
)
_EFFECT_SUFFIXES = (
    "_improving_moves",
    "_best_improving_moves",
    "_best_delta",
    "_phase_delta_sum",
    "_phase_best_delta",
    "_phase_improvement_counts",
    "_improvement_counts",
)
_BUDGET_SUFFIXES = (
    "_stage_budget_ms",
    "_stage_budget_ratio",
    "_phase_budget_ms",
    "_phase_budget_ratio",
    "_phase_runtime_ms",
    "_runtime_ms",
    "_elapsed_ms",
)


def declared_surface_telemetry_fields(surface: Any | None) -> frozenset[str]:
    """Return all runtime telemetry fields a surface exposes for guard use."""

    evidence = _field(surface, "evidence")
    fields: set[str] = set()
    for name in (
        "required_runtime_fields",
        "optional_runtime_fields",
        "activity_runtime_fields",
        "effect_probe_runtime_fields",
        "stage_budget_runtime_fields",
    ):
        fields.update(_string_list(_field(evidence, name)))
    activation = _field(evidence, "activation_runtime_fields")
    if isinstance(activation, Mapping):
        for value in activation.values():
            fields.update(_string_list(value))
    else:
        fields.update(_string_list(activation))
    for telemetry in _mechanism_telemetry_values(evidence):
        fields.update(_string_list(_field(telemetry, "activation_runtime_fields")))
        fields.update(_string_list(_field(telemetry, "effect_probe_runtime_fields")))
    return frozenset(field for field in fields if field)


def declared_activity_runtime_fields(surface: Any | None) -> tuple[str, ...]:
    evidence = _field(surface, "evidence")
    explicit = _string_list(_field(evidence, "activity_runtime_fields"))
    if explicit:
        return tuple(explicit)
    mechanism_fields: list[str] = []
    for telemetry in _mechanism_telemetry_values(evidence):
        mechanism_fields.extend(
            _string_list(_field(telemetry, "activation_runtime_fields"))
        )
    if mechanism_fields:
        return tuple(dict.fromkeys(mechanism_fields))
    declared = _string_list(_field(evidence, "required_runtime_fields"))
    return tuple(_fields_with_suffix(declared, _ACTIVITY_SUFFIXES))


def declared_effect_probe_runtime_fields(surface: Any | None) -> tuple[str, ...]:
    evidence = _field(surface, "evidence")
    explicit = _string_list(_field(evidence, "effect_probe_runtime_fields"))
    if explicit:
        return tuple(explicit)
    mechanism_fields: list[str] = []
    for telemetry in _mechanism_telemetry_values(evidence):
        mechanism_fields.extend(
            _string_list(_field(telemetry, "effect_probe_runtime_fields"))
        )
    if mechanism_fields:
        return tuple(dict.fromkeys(mechanism_fields))
    declared = _string_list(_field(evidence, "required_runtime_fields"))
    return tuple(_fields_with_suffix(declared, _EFFECT_SUFFIXES))


def declared_stage_budget_runtime_fields(surface: Any | None) -> tuple[str, ...]:
    evidence = _field(surface, "evidence")
    explicit = _string_list(_field(evidence, "stage_budget_runtime_fields"))
    if explicit:
        return tuple(explicit)
    declared = _string_list(_field(evidence, "required_runtime_fields"))
    return tuple(_fields_with_suffix(declared, _BUDGET_SUFFIXES))


def find_research_surface(problem_spec: Any | None, name: str | None) -> Any | None:
    surface_name = normalize_surface_name(name)
    if not surface_name:
        return None
    for surface in _field(problem_spec, "research_surfaces") or ():
        if str(_field(surface, "name") or "").strip() == surface_name:
            return surface
    return None


def _mechanism_telemetry_values(evidence: Any | None) -> tuple[Any, ...]:
    telemetry = _field(evidence, "mechanism_telemetry")
    if not isinstance(telemetry, Mapping):
        return ()
    return tuple(telemetry.values())
