"""Contract validation for proposal-declared runtime telemetry."""
from __future__ import annotations

from typing import Any

from scion.runtime.audit import normalize_surface_name
from scion.runtime.telemetry_guard.declarations import (
    declared_surface_telemetry_fields,
    find_research_surface,
)
from scion.runtime.telemetry_guard.expected_schema import (
    EXPECTED_TELEMETRY_CATEGORIES,
    _expected_telemetry_category_errors,
    normalize_declared_mechanisms,
    normalize_expected_telemetry,
)
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

    allowed = set(declared_surface_telemetry_fields(surface))
    for probe in declared_mechanism_runtime_probes(
        problem_spec=problem_spec,
        surface=surface,
        declared_mechanisms=mechanisms,
    ):
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
        errors.extend(_category_field_semantic_errors(category, fields))
        unknown = [field for field in fields if field not in allowed]
        if unknown:
            errors.append(
                f"expected_telemetry.{category} references undeclared "
                f"runtime field(s): {', '.join(sorted(unknown))}"
            )
    return tuple(errors)


_OBJECTIVE_OUTCOME_TELEMETRY_FIELDS = frozenset(
    {
        "solver_algorithm_fleet_violation",
        "solver_algorithm_total_distance",
        "solver_algorithm_objective",
        "solver_algorithm_solution_routes",
    }
)


def _category_field_semantic_errors(
    category: str,
    fields: tuple[str, ...],
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
        if field_text in _OBJECTIVE_OUTCOME_TELEMETRY_FIELDS:
            errors.append(
                "expected_telemetry.activation references outcome/objective field "
                f"{field_text}; activation must use mechanism-specific activity "
                "evidence such as adapter-declared context_records or "
                "phase_runtime fields, while objective fields belong under effect "
                "or protected-objective checks."
            )
    return errors


def _looks_like_prose_field(value: str) -> bool:
    field = str(value or "").strip()
    if not field:
        return False
    return any(ch.isspace() for ch in field)
