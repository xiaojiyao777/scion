"""Declared research-surface telemetry extraction."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.runtime.audit import normalize_surface_name
from scion.runtime.surface_telemetry import (
    declared_runtime_field_roles as _surface_declared_runtime_field_roles,
    declared_surface_telemetry_fields as _surface_declared_surface_telemetry_fields,
    runtime_field_roles_for as _surface_runtime_field_roles_for,
)
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
TELEMETRY_FIELD_ROLES = frozenset(
    {
        "activity",
        "aggregate_activity",
        "aggregate_effect",
        "budget",
        "diagnostic",
        "effect",
        "mechanism_activity",
        "mechanism_activation",
        "mechanism_effect",
        "objective_outcome",
        "outcome",
        "protected_outcome",
    }
)
_ROLE_MAPPING_FIELD_NAMES = (
    "runtime_field_roles",
    "telemetry_field_roles",
    "runtime_telemetry_roles",
    "field_roles",
)


def declared_surface_telemetry_fields(
    surface: Any | None,
    *,
    problem_spec: Any | None = None,
    declared_mechanisms: Sequence[str] = (),
    include_templates: bool = False,
) -> frozenset[str]:
    """Return all runtime telemetry fields a surface exposes for guard use."""

    return _surface_declared_surface_telemetry_fields(
        surface,
        problem_spec=problem_spec,
        declared_mechanisms=declared_mechanisms,
        include_templates=include_templates,
    )


def declared_runtime_field_roles(
    surface: Any | None,
    *,
    problem_spec: Any | None = None,
    declared_mechanisms: Sequence[str] = (),
    include_templates: bool = False,
) -> dict[str, frozenset[str]]:
    """Return role -> runtime fields declared by the selected surface.

    Role declarations are problem-owned metadata. Generic telemetry guards use
    these role labels to reason about category misuse without knowing concrete
    problem field names.
    """

    return _surface_declared_runtime_field_roles(
        surface,
        problem_spec=problem_spec,
        declared_mechanisms=declared_mechanisms,
        include_templates=include_templates,
    )


def runtime_field_roles_for(
    field: str,
    role_map: Mapping[str, Sequence[str] | frozenset[str]],
) -> frozenset[str]:
    return _surface_runtime_field_roles_for(field, role_map)


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


def _role_mapping_sources(
    *,
    surface: Any | None,
    evidence: Any | None,
    problem_spec: Any | None,
) -> tuple[Any, ...]:
    sources: list[Any] = []
    for owner in (
        _field(problem_spec, "telemetry_guard"),
        _field(problem_spec, "runtime_telemetry_guard"),
        _field(problem_spec, "telemetry_probes"),
        _field(problem_spec, "runtime_telemetry_probes"),
        _field(_field(problem_spec, "evidence"), "telemetry_guard"),
        _field(_field(problem_spec, "evidence"), "runtime_telemetry_guard"),
        evidence,
        surface,
        _field(evidence, "telemetry_guard"),
        _field(evidence, "runtime_telemetry_guard"),
        _field(surface, "telemetry_guard"),
        _field(surface, "runtime_telemetry_guard"),
    ):
        if owner is None:
            continue
        for field_name in _ROLE_MAPPING_FIELD_NAMES:
            source = _field(owner, field_name)
            if source is not None:
                sources.append(source)
    return tuple(sources)


def _merge_role_mapping(
    roles: dict[str, set[str]],
    value: Any,
    *,
    declared_mechanisms: Sequence[str],
) -> None:
    if not isinstance(value, Mapping):
        return
    for raw_key, raw_value in value.items():
        key = str(raw_key or "").strip()
        normalized_key = key.lower()
        if normalized_key in TELEMETRY_FIELD_ROLES:
            _add_role_fields(
                roles,
                normalized_key,
                _string_list(raw_value),
                declared_mechanisms=declared_mechanisms,
            )
            continue
        for role in _string_list(raw_value):
            normalized_role = str(role or "").strip().lower()
            if normalized_role not in TELEMETRY_FIELD_ROLES:
                continue
            _add_role_fields(
                roles,
                normalized_role,
                [key],
                declared_mechanisms=declared_mechanisms,
            )


def _add_role_fields(
    roles: dict[str, set[str]],
    role: str,
    fields: Sequence[str],
    *,
    declared_mechanisms: Sequence[str],
) -> None:
    normalized_role = str(role or "").strip().lower()
    if not normalized_role:
        return
    target = roles.setdefault(normalized_role, set())
    for field in _expand_role_field_templates(fields, declared_mechanisms):
        if field:
            target.add(field)


def _expand_role_field_templates(
    fields: Sequence[str],
    mechanisms: Sequence[str],
) -> tuple[str, ...]:
    expanded: list[str] = []
    for field in fields:
        text = str(field or "").strip()
        if not text:
            continue
        if "{mechanism}" in text and mechanisms:
            expanded.extend(
                text.replace("{mechanism}", str(mechanism))
                for mechanism in mechanisms
            )
        else:
            expanded.append(text)
    return tuple(dict.fromkeys(expanded))
