"""Contract validation for proposal-declared runtime telemetry."""
from __future__ import annotations

import re
from typing import Any

from scion.runtime.audit import normalize_surface_name
from scion.runtime.telemetry_guard.declarations import (
    declared_runtime_field_roles,
    declared_surface_telemetry_fields,
    find_research_surface,
    runtime_field_roles_for,
)
from scion.runtime.telemetry_guard.expected_schema import (
    EXPECTED_TELEMETRY_CATEGORIES,
    _expected_telemetry_category_errors,
    normalize_declared_mechanisms,
    normalize_expected_telemetry,
)
from scion.runtime.telemetry_guard.guidance import expected_telemetry_guidance
from scion.runtime.telemetry_guard.mechanism_probes import (
    declared_mechanism_runtime_probes,
)


def validate_expected_telemetry_contract(
    *,
    problem_spec: Any | None,
    selected_surface: str | None,
    expected_telemetry: Any,
    declared_mechanisms: Any = None,
) -> tuple[str, ...]:
    """Validate proposal-declared telemetry keys against adapter declarations."""

    category_errors = list(_expected_telemetry_category_errors(expected_telemetry))
    claims = normalize_expected_telemetry(expected_telemetry)
    mechanisms = normalize_declared_mechanisms(
        declared_mechanisms,
        expected_telemetry=expected_telemetry,
    )
    if not any(claims.values()):
        return tuple(category_errors)

    surface_name = normalize_surface_name(selected_surface)
    if not surface_name:
        return tuple(
            [
                *category_errors,
                "expected_telemetry requires a selected research surface",
            ]
        )

    surface = find_research_surface(problem_spec, surface_name)
    if surface is None:
        return tuple(
            [
                *category_errors,
                f"selected research surface '{surface_name}' is not declared "
                "in problem_spec.research_surfaces",
            ]
        )

    allowed = set(
        declared_surface_telemetry_fields(
            surface,
            problem_spec=problem_spec,
            declared_mechanisms=mechanisms,
            include_templates=True,
        )
    )
    mechanism_probes = declared_mechanism_runtime_probes(
        problem_spec=problem_spec,
        surface=surface,
        declared_mechanisms=mechanisms,
    )
    role_map = declared_runtime_field_roles(
        surface,
        problem_spec=problem_spec,
        declared_mechanisms=mechanisms,
        include_templates=True,
    )
    for probe in mechanism_probes:
        allowed.add(probe.field)
    if not allowed:
        return tuple(
            [
                *category_errors,
                f"research surface '{surface_name}' does not declare telemetry "
                "fields in surface.evidence",
            ]
        )

    errors: list[str] = list(category_errors)
    for category, fields in claims.items():
        if category not in EXPECTED_TELEMETRY_CATEGORIES:
            continue
        mechanism_fields = tuple(
            probe.field for probe in mechanism_probes if probe.category == category
        )
        errors.extend(
            _category_field_semantic_errors(
                category,
                fields,
                mechanism_fields=mechanism_fields,
                role_map=role_map,
            )
        )
        unknown = [
            field
            for field in fields
            if field not in allowed
            and not _is_allowed_declared_runtime_subfield(
                field,
                allowed_fields=allowed,
                role_map=role_map,
                category=category,
                declared_mechanisms=mechanisms,
            )
        ]
        if unknown:
            errors.append(
                f"expected_telemetry.{category} references undeclared "
                f"runtime field(s): {', '.join(sorted(unknown))}"
            )
    if errors:
        guidance = expected_telemetry_guidance(
            problem_spec=problem_spec,
            selected_surface=surface_name,
            declared_mechanisms=mechanisms,
        )
        if guidance:
            errors.append(guidance)
    return tuple(errors)


_ACTIVATION_OUTCOME_ROLES = frozenset(
    {"objective_outcome", "outcome", "protected_outcome"}
)
_ACTIVATION_AGGREGATE_ROLES = frozenset(
    {
        "activity",
        "aggregate_activity",
        "aggregate_effect",
        "effect",
        "mechanism_effect",
    }
)
_ACTIVATION_ALLOWED_ROLES = frozenset(
    {"mechanism_activity", "mechanism_activation"}
)
_ACTIVATION_COMPATIBLE_CONTAINER_ROLES = frozenset(
    {"activity", "budget", "diagnostic", "mechanism_activity", "mechanism_activation"}
)
_SUBFIELD_FORBIDDEN_CONTAINER_ROLES = frozenset(
    {
        "aggregate_effect",
        "effect",
        "mechanism_effect",
        "objective_outcome",
        "outcome",
        "protected_outcome",
    }
)


def _is_allowed_declared_runtime_subfield(
    field: str,
    *,
    allowed_fields: set[str],
    role_map: dict[str, frozenset[str]] | None,
    category: str,
    declared_mechanisms: tuple[str, ...] = (),
) -> bool:
    """Allow adapter-declared runtime map children without hard-coding keys.

    Problem adapters often expose telemetry maps such as
    ``surface_phase_runtime_ms`` whose concrete children are created
    by algorithm phases or newly declared mechanisms. The generic Scion
    contract should verify that the container is adapter-declared and has a
    compatible role, but it should not require every child key to be known
    before the agent writes the mechanism.
    """

    field_text = str(field or "").strip()
    if "." not in field_text:
        return False
    base, child = field_text.rsplit(".", 1)
    if not base or not child or base not in allowed_fields:
        return False
    if not _runtime_subfield_key_is_safe(child):
        return False
    roles = runtime_field_roles_for(base, role_map or {})
    if roles & _SUBFIELD_FORBIDDEN_CONTAINER_ROLES:
        return False
    if category == "activation":
        if roles & _ACTIVATION_ALLOWED_ROLES:
            return True
        if not (roles & _ACTIVATION_COMPATIBLE_CONTAINER_ROLES):
            return False
        return _subfield_child_matches_declared_mechanism(
            child,
            declared_mechanisms,
        )
    if declared_mechanisms:
        return _subfield_child_matches_declared_mechanism(
            child,
            declared_mechanisms,
        )
    return True


def _runtime_subfield_key_is_safe(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", str(value or "")))


def _subfield_child_matches_declared_mechanism(
    child: str,
    declared_mechanisms: tuple[str, ...],
) -> bool:
    child_text = str(child or "").strip()
    if not child_text:
        return False
    return any(
        child_text == str(mechanism or "").strip()
        for mechanism in declared_mechanisms
        if str(mechanism or "").strip()
    )


def _category_field_semantic_errors(
    category: str,
    fields: tuple[str, ...],
    *,
    mechanism_fields: tuple[str, ...] = (),
    role_map: dict[str, frozenset[str]] | None = None,
) -> list[str]:
    errors: list[str] = []
    for field in fields:
        field_text = str(field or "").strip()
        if _looks_like_prose_field(field_text):
            errors.append(
                f"expected_telemetry.{category} contains prose instead of an "
                f"exact runtime field key: {field_text!r}. Values must be "
                "declared runtime telemetry field strings, for example a "
                "surface-declared mechanism probe with the concrete mechanism "
                "id substituted."
            )
        if category != "activation":
            continue
        roles = runtime_field_roles_for(field_text, role_map or {})
        outcome_roles = roles & _ACTIVATION_OUTCOME_ROLES
        aggregate_roles = roles & _ACTIVATION_AGGREGATE_ROLES
        if outcome_roles:
            errors.append(
                "expected_telemetry.activation references declared outcome field "
                f"{field_text} (role(s): {', '.join(sorted(outcome_roles))}); "
                "activation must use mechanism-specific activity evidence "
                "declared by the selected research surface."
            )
        if aggregate_roles and not (roles & _ACTIVATION_ALLOWED_ROLES):
            errors.append(
                "expected_telemetry.activation references declared aggregate or "
                f"effect field {field_text} (role(s): "
                f"{', '.join(sorted(aggregate_roles))}); activation must use "
                "mechanism-specific activity evidence declared by the selected "
                "research surface."
            )
        specific_field = _mechanism_specific_field_for_aggregate(
            field_text,
            mechanism_fields,
        )
        if specific_field:
            errors.append(
                "expected_telemetry.activation references aggregate runtime field "
                f"{field_text}; activation must use the mechanism-specific field "
                f"{specific_field} rather than the whole telemetry map."
            )
    return errors


def _mechanism_specific_field_for_aggregate(
    field: str,
    mechanism_fields: tuple[str, ...],
) -> str:
    field_text = str(field or "").strip()
    if not field_text:
        return ""
    prefix = f"{field_text}."
    for mechanism_field in mechanism_fields:
        if str(mechanism_field or "").startswith(prefix):
            return str(mechanism_field)
    return ""


def _looks_like_prose_field(value: str) -> bool:
    field = str(value or "").strip()
    if not field:
        return False
    return any(ch.isspace() for ch in field)
