from __future__ import annotations

import json
from types import SimpleNamespace

from scion.core.models import MechanismChange
from scion.runtime.telemetry_guard import (
    expected_telemetry_template,
    validate_expected_telemetry_contract,
)


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
                    runtime_field_roles={
                        "mechanism_activation": [
                            "solver_algorithm_context_records.{mechanism}_iterations",
                            "solver_algorithm_phase_runtime_ms.{mechanism}",
                        ],
                        "budget": [
                            "solver_algorithm_phase_runtime_ms",
                            "solver_algorithm_phase_runtime_ms.{mechanism}",
                        ],
                        "aggregate_effect": [
                            "solver_algorithm_improving_moves",
                            "solver_algorithm_best_improving_moves",
                        ],
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

    assert errors[0] == (
        "expected_telemetry.activation references aggregate runtime field "
        "solver_algorithm_phase_runtime_ms; activation must use the "
        "mechanism-specific field "
        "solver_algorithm_phase_runtime_ms.construction_route_merge rather than "
        "the whole telemetry map."
    )
    assert "Legal expected_telemetry template" in errors[1]
    assert "selected_surface='solver_design'" in errors[1]
    assert "mechanism_id='construction_route_merge'" in errors[1]
    assert (
        "activation=[solver_algorithm_context_records."
        "construction_route_merge_iterations, "
        "solver_algorithm_phase_runtime_ms.construction_route_merge]"
        in errors[1]
    )
    assert "budget=[solver_algorithm_phase_runtime_ms.construction_route_merge]" in errors[1]


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


def test_activation_rejects_unbound_phase_runtime_subpath_for_new_mechanism() -> None:
    errors = validate_expected_telemetry_contract(
        problem_spec=_surface_spec(),
        selected_surface="solver_design",
        expected_telemetry={
            "activation": [
                "solver_algorithm_phase_runtime_ms.vns_initial",
                "solver_algorithm_phase_runtime_ms.vns_embedded",
            ],
        },
        declared_mechanisms=[
            MechanismChange(id="intra_reinsertion_vns", change_type="add")
        ],
    )

    assert errors[0] == (
        "expected_telemetry.activation references undeclared runtime field(s): "
        "solver_algorithm_phase_runtime_ms.vns_embedded, "
        "solver_algorithm_phase_runtime_ms.vns_initial"
    )
    assert "Legal expected_telemetry template" in errors[1]
    assert "solver_algorithm_phase_runtime_ms.intra_reinsertion_vns" in errors[1]


def test_activation_accepts_adapter_declared_phase_subpath_evidence() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver_design",
                evidence=SimpleNamespace(
                    required_runtime_fields=["solver_algorithm_phase_runtime_ms"],
                    activation_runtime_fields={
                        "existing_vns_phase": [
                            "solver_algorithm_phase_runtime_ms.vns_initial",
                            "solver_algorithm_phase_runtime_ms.vns_embedded",
                        ]
                    },
                    runtime_field_roles={
                        "mechanism_activation": [
                            "solver_algorithm_phase_runtime_ms.vns_initial",
                            "solver_algorithm_phase_runtime_ms.vns_embedded",
                        ],
                        "budget": ["solver_algorithm_phase_runtime_ms"],
                    },
                ),
            )
        ]
    )

    errors = validate_expected_telemetry_contract(
        problem_spec=spec,
        selected_surface="solver_design",
        expected_telemetry={
            "activation": [
                "solver_algorithm_phase_runtime_ms.vns_initial",
                "solver_algorithm_phase_runtime_ms.vns_embedded",
            ],
        },
        declared_mechanisms=[
            MechanismChange(id="intra_reinsertion_vns", change_type="add")
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

        assert errors[0] == (
            "expected_telemetry.activation references declared aggregate or "
            f"effect field {field} (role(s): aggregate_effect); activation "
            "must use mechanism-specific activity evidence declared by the "
            "selected research surface."
        )
        assert "adaptive_vns_operator_weights" in errors[1]
        assert "solver_algorithm_phase_runtime_ms.adaptive_vns_operator_weights" in errors[1]


def test_c11_guidance_is_declared_surface_driven_without_cvrp_defaults() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="dispatch_solver",
                evidence=SimpleNamespace(
                    required_runtime_fields=[
                        "dispatch.loaded",
                        "dispatch.node_count",
                        "dispatch.effect_delta",
                        "dispatch.budget_ms",
                    ],
                    activation_runtime_fields={
                        "{mechanism}": [
                            "dispatch.records.{mechanism}.started",
                            "dispatch.budget_ms.{mechanism}",
                        ]
                    },
                    effect_probe_runtime_fields=[
                        "dispatch.effect_delta.{mechanism}",
                    ],
                    runtime_field_roles={
                        "activity": ["dispatch.node_count"],
                        "mechanism_activation": [
                            "dispatch.records.{mechanism}.started",
                            "dispatch.budget_ms.{mechanism}",
                        ],
                        "budget": ["dispatch.budget_ms.{mechanism}"],
                        "mechanism_effect": [
                            "dispatch.effect_delta.{mechanism}",
                        ],
                    },
                ),
            )
        ]
    )

    errors = validate_expected_telemetry_contract(
        problem_spec=spec,
        selected_surface="dispatch_solver",
        expected_telemetry={
            "activation": ["dispatch.effect_delta.guided_repair"],
        },
        declared_mechanisms=[
            MechanismChange(id="guided_repair", change_type="add")
        ],
    )
    template = expected_telemetry_template(
        problem_spec=spec,
        selected_surface="dispatch_solver",
        declared_mechanisms=["guided_repair"],
    )
    rendered = json.dumps({"errors": errors, "template": template}, sort_keys=True)

    assert errors[0].startswith(
        "expected_telemetry.activation references declared aggregate or "
        "effect field dispatch.effect_delta.guided_repair"
    )
    assert "selected_surface='dispatch_solver'" in errors[1]
    assert "dispatch.records.guided_repair.started" in rendered
    assert "dispatch.budget_ms.guided_repair" in rendered
    assert "dispatch.effect_delta.guided_repair" in rendered
    assert "solver_algorithm" not in rendered
    assert "route" not in rendered.lower()
    assert "cvrp" not in rendered.lower()
