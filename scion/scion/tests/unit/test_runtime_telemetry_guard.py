from __future__ import annotations

from types import SimpleNamespace

from scion.core.models import MechanismChange
from scion.runtime.telemetry_guard import (
    build_telemetry_guard_summary,
    declared_surface_telemetry_fields,
    validate_expected_telemetry_contract,
)


def _problem_spec() -> SimpleNamespace:
    return SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    required_runtime_fields=[
                        "solver_search_iterations",
                        "solver_phase_runtime_ms",
                    ],
                    stage_budget_runtime_fields=["solver_phase_runtime_ms"],
                ),
            )
        ]
    )


def test_telemetry_guard_flags_stage_budget_starvation() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "solver_search_iterations": 4,
                "solver_phase_runtime_ms": {"search": 0},
            }
        ],
        champion_runtimes=[
            {
                "solver_search_iterations": 7,
                "solver_phase_runtime_ms": {"search": 25},
            }
        ],
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={"budget": ["solver_phase_runtime_ms"]},
    )

    assert summary["passed"] is False
    assert summary["failures"][0]["code"] == "TELEMETRY_BUDGET_STARVED"
    assert summary["fields"]["solver_phase_runtime_ms"]["champion_positive"] == 1


def test_expected_telemetry_invalid_category_fails_even_without_fields() -> None:
    errors = validate_expected_telemetry_contract(
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={"attribution": []},
    )

    assert errors
    assert "category 'attribution' is not supported" in errors[0]


def test_mechanism_telemetry_fields_are_declared_and_guarded() -> None:
    surface = SimpleNamespace(
        name="solver",
        evidence=SimpleNamespace(
            required_runtime_fields=["solver_loaded"],
            mechanism_telemetry={
                "search_*": SimpleNamespace(
                    activation_runtime_fields=["mechanisms.{mechanism}.active"],
                    effect_probe_runtime_fields=["mechanisms.{mechanism}.delta"],
                )
            },
        ),
    )
    problem_spec = SimpleNamespace(research_surfaces=[surface])

    assert "mechanisms.{mechanism}.active" in declared_surface_telemetry_fields(
        surface
    )
    assert validate_expected_telemetry_contract(
        problem_spec=problem_spec,
        selected_surface="solver",
        expected_telemetry={"activation": ["mechanisms.{mechanism}.active"]},
        declared_mechanisms=["search_seed"],
    ) == ()

    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {"mechanisms": {"search_seed": {"active": 1, "delta": 2.0}}}
        ],
        problem_spec=problem_spec,
        selected_surface="solver",
        declared_mechanisms=["search_seed"],
    )

    assert summary["passed"] is True
    assert summary["mechanisms"]["search_seed"]["categories"]["activation"] == [
        "mechanisms.search_seed.active"
    ]


def test_telemetry_guard_expands_nested_mechanism_paths() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": ["mechanism_stats.{mechanism}.active"]
                    },
                    effect_probe_runtime_fields=[
                        "mechanism_stats.{mechanism}.delta"
                    ],
                ),
            )
        ]
    )

    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_stats": {
                    "target_probe": {"active": 1, "delta": 2.5},
                    "other_probe": {"active": 1, "delta": 0.0},
                }
            }
        ],
        problem_spec=spec,
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is True
    assert summary["declared_mechanisms"] == ["target_probe"]
    assert (
        summary["mechanisms"]["target_probe"]["fields"][
            "mechanism_stats.target_probe.active"
        ]["candidate_positive"]
        == 1
    )


def test_telemetry_guard_scopes_map_paths_to_current_mechanism() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": ["mechanism_activation"]
                    },
                    effect_probe_runtime_fields={
                        "{mechanism}": ["mechanism_effect"]
                    },
                ),
            )
        ]
    )

    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_activation": {"target_probe": 0, "other_probe": 1},
                "mechanism_effect": {"target_probe": 0.0, "other_probe": 4.0},
            }
        ],
        problem_spec=spec,
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is False
    assert [failure["code"] for failure in summary["failures"]] == [
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
        "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
    ]
    assert (
        summary["mechanisms"]["target_probe"]["fields"]["mechanism_activation"][
            "candidate_positive"
        ]
        == 0
    )
