from __future__ import annotations

from types import SimpleNamespace

from scion.core.models import MechanismChange
from scion.runtime.telemetry_guard import validate_expected_telemetry_contract


def _surface_spec() -> SimpleNamespace:
    return SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver_design",
                evidence=SimpleNamespace(
                    required_runtime_fields=[
                        "solver_algorithm_phase_runtime_ms",
                        "solver_algorithm_improving_moves",
                        "solver_algorithm_best_improving_moves",
                    ],
                    activation_runtime_fields={
                        "{mechanism}": [
                            "solver_algorithm_context_records.{mechanism}_iterations",
                            "solver_algorithm_phase_runtime_ms.{mechanism}",
                        ]
                    },
                ),
            )
        ]
    )


def test_activation_rejects_aggregate_runtime_map_when_mechanism_path_exists() -> None:
    errors = validate_expected_telemetry_contract(
        problem_spec=_surface_spec(),
        selected_surface="solver_design",
        expected_telemetry={
            "activation": ["solver_algorithm_phase_runtime_ms"],
        },
        declared_mechanisms=[
            MechanismChange(id="construction_route_merge", change_type="add")
        ],
    )

    assert errors == (
        "expected_telemetry.activation references aggregate runtime field "
        "solver_algorithm_phase_runtime_ms; activation must use the "
        "mechanism-specific field "
        "solver_algorithm_phase_runtime_ms.construction_route_merge rather than "
        "the whole telemetry map.",
    )


def test_activation_accepts_mechanism_specific_runtime_map_path() -> None:
    errors = validate_expected_telemetry_contract(
        problem_spec=_surface_spec(),
        selected_surface="solver_design",
        expected_telemetry={
            "activation": [
                "solver_algorithm_phase_runtime_ms.construction_route_merge"
            ],
        },
        declared_mechanisms=[
            MechanismChange(id="construction_route_merge", change_type="add")
        ],
    )

    assert errors == ()


def test_activation_rejects_aggregate_effect_activity_fields() -> None:
    for field in (
        "solver_algorithm_improving_moves",
        "solver_algorithm_best_improving_moves",
    ):
        errors = validate_expected_telemetry_contract(
            problem_spec=_surface_spec(),
            selected_surface="solver_design",
            expected_telemetry={
                "activation": [field],
            },
            declared_mechanisms=[
                MechanismChange(id="adaptive_vns_operator_weights", change_type="add")
            ],
        )

        assert errors == (
            "expected_telemetry.activation references aggregate effect/activity "
            f"field {field}; activation must use mechanism-specific activity "
            "evidence such as adapter-declared context_records or phase_runtime "
            "fields, while aggregate effect/activity fields belong under "
            "activity or effect checks.",
        )
