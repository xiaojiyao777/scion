from __future__ import annotations

from types import SimpleNamespace

from scion.core.models import MechanismChange
from scion.runtime.telemetry_guard import (
    build_telemetry_guard_summary,
    declared_surface_telemetry_fields,
    format_telemetry_guard_issue,
    normalize_declared_mechanisms,
    normalize_expected_telemetry,
    normalize_expected_telemetry_by_mechanism,
    validate_expected_telemetry_contract,
)
from scion.runtime.telemetry_guard.evidence import (
    _bounded_value,
    _empty_value,
    _positive_evidence,
)
from scion.runtime.telemetry_guard.runtime_paths import _parse_runtime_path


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
    assert (
        format_telemetry_guard_issue(summary)
        == "telemetry guard observed stage budget starvation: "
        "solver_phase_runtime_ms had no positive candidate runtime evidence"
    )


def test_expected_telemetry_normalization_preserves_categories() -> None:
    normalized = normalize_expected_telemetry(
        {
            "activity": "solver_search_iterations",
            "activation": ["mechanisms.seed.active"],
            "effect": {"seed": ["mechanisms.seed.delta"]},
            "budget": ("solver_phase_runtime_ms",),
            "mechanism": "seed",
        }
    )

    assert normalized == {
        "activation": ("mechanisms.seed.active",),
        "activity": ("solver_search_iterations",),
        "budget": ("solver_phase_runtime_ms",),
        "effect": ("mechanisms.seed.delta",),
    }


def test_runtime_field_map_key_is_not_auto_declared_mechanism() -> None:
    expected = {
        "activation": {
            "solver_algorithm_phase_runtime_ms": (
                "solver_algorithm_phase_runtime_ms.multi_start_construction"
            )
        }
    }
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": [
                            "solver_algorithm_phase_runtime_ms.{mechanism}"
                        ]
                    },
                ),
            )
        ]
    )

    assert normalize_declared_mechanisms(expected_telemetry=expected) == ()
    assert normalize_expected_telemetry_by_mechanism(expected) == {}
    assert normalize_declared_mechanisms(
        [MechanismChange(id="multi_start_construction", change_type="add")],
        expected_telemetry=expected,
    ) == ("multi_start_construction",)

    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "solver_algorithm_phase_runtime_ms": {
                    "multi_start_construction": 3
                }
            }
        ],
        problem_spec=spec,
        selected_surface="solver",
        expected_telemetry=expected,
        declared_mechanisms=[
            MechanismChange(id="multi_start_construction", change_type="add")
        ],
    )

    assert summary["passed"] is True
    assert summary["declared_mechanisms"] == ["multi_start_construction"]
    assert "solver_algorithm_phase_runtime_ms" not in summary["mechanisms"]
    assert set(summary["mechanisms"]) == {"multi_start_construction"}


def test_telemetry_guard_treats_protected_objective_effect_as_no_regression_probe() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "solver_algorithm_fleet_violation": 0,
                "solver_algorithm_best_delta": 2.0,
            }
        ],
        champion_runtimes=[
            {
                "solver_algorithm_fleet_violation": 0,
                "solver_algorithm_best_delta": 1.0,
            }
        ],
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={
            "effect": [
                "solver_algorithm_fleet_violation",
                "solver_algorithm_best_delta",
            ]
        },
        protected_objectives=("fleet_violation",),
    )

    assert summary["passed"] is True
    assert summary["protected_objectives"] == ["fleet_violation"]
    assert summary["fields"]["solver_algorithm_fleet_violation"][
        "candidate_present"
    ] == 1
    assert summary["fields"]["solver_algorithm_fleet_violation"][
        "candidate_positive"
    ] == 0


def test_effect_objective_outcome_field_accepts_zero_when_present() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[{"solver_algorithm_fleet_violation": 0}],
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={"effect": ["solver_algorithm_fleet_violation"]},
    )

    assert summary["passed"] is True
    assert summary["failures"] == []
    assert summary["fields"]["solver_algorithm_fleet_violation"][
        "candidate_present"
    ] == 1
    assert summary["fields"]["solver_algorithm_fleet_violation"][
        "candidate_positive"
    ] == 0


def test_telemetry_guard_requires_protected_objective_probe_presence() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[{"solver_algorithm_best_delta": 2.0}],
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={"effect": ["solver_algorithm_fleet_violation"]},
        protected_objectives=("fleet_violation",),
    )

    assert summary["passed"] is False
    assert summary["failures"][0]["code"] == "TELEMETRY_PROTECTED_EFFECT_NOT_OBSERVED"


def test_expected_telemetry_invalid_category_fails_even_without_fields() -> None:
    errors = validate_expected_telemetry_contract(
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={"attribution": []},
    )

    assert errors
    assert "category 'attribution' is not supported" in errors[0]


def test_expected_telemetry_activation_rejects_objective_outcome_fields() -> None:
    errors = validate_expected_telemetry_contract(
        problem_spec=SimpleNamespace(
            research_surfaces=[
                SimpleNamespace(
                    name="solver",
                    evidence=SimpleNamespace(
                        required_runtime_fields=[
                            "solver_algorithm_fleet_violation",
                            "solver_algorithm_context_records",
                        ],
                    ),
                )
            ]
        ),
        selected_surface="solver",
        expected_telemetry={
            "activation": ["solver_algorithm_fleet_violation"],
            "effect": ["solver_algorithm_fleet_violation"],
        },
    )

    assert errors == (
        "expected_telemetry.activation references outcome/objective field "
        "solver_algorithm_fleet_violation; activation must use "
        "mechanism-specific activity evidence such as adapter-declared "
        "context_records or phase_runtime fields, while objective fields "
        "belong under effect or protected-objective checks.",
    )


def test_expected_telemetry_rejects_prose_field_values() -> None:
    errors = validate_expected_telemetry_contract(
        problem_spec=SimpleNamespace(
            research_surfaces=[
                SimpleNamespace(
                    name="solver",
                    evidence=SimpleNamespace(
                        required_runtime_fields=["solver_algorithm_phase_runtime_ms"],
                    ),
                )
            ]
        ),
        selected_surface="solver",
        expected_telemetry={
            "activation": {
                "solver_algorithm_phase_runtime_ms": (
                    "merge phase entry recorded via context.record_phase"
                )
            }
        },
    )

    assert any("contains prose instead of an exact runtime field key" in e for e in errors)


def test_expected_telemetry_missing_declared_fields_fails_closed() -> None:
    problem_spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(name="solver", evidence=SimpleNamespace())
        ]
    )

    errors = validate_expected_telemetry_contract(
        problem_spec=problem_spec,
        selected_surface="solver",
        expected_telemetry={"effect": ["solver_best_delta"]},
    )

    assert errors == (
        "research surface 'solver' does not declare telemetry fields in "
        "surface.evidence",
    )


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
    ]
    assert [warning["code"] for warning in summary["warnings"]] == [
        "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
    ]
    assert (
        summary["mechanisms"]["target_probe"]["fields"]["mechanism_activation"][
            "candidate_positive"
        ]
        == 0
    )


def test_auto_declared_mechanism_effect_probe_warns_when_activation_present() -> None:
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
                "mechanism_activation": {"target_probe": 1},
                "mechanism_effect": {"target_probe": 0.0},
            }
        ],
        problem_spec=spec,
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is True
    assert summary["failures"] == []
    assert [warning["code"] for warning in summary["warnings"]] == [
        "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
    ]


def test_mechanism_diagnostics_separate_activation_runtime_and_zero_effect() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": [
                            "mechanism_iterations.{mechanism}",
                            "mechanism_phase_runtime_ms.{mechanism}",
                        ]
                    },
                    effect_probe_runtime_fields={
                        "{mechanism}": [
                            "mechanism_improvement_counts.{mechanism}",
                            "mechanism_best_delta.{mechanism}",
                        ]
                    },
                ),
            )
        ]
    )

    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_iterations": {"target_probe": 3},
                "mechanism_phase_runtime_ms": {"target_probe": 0},
                "mechanism_improvement_counts": {"target_probe": 0},
                "mechanism_best_delta": {"target_probe": 0.0},
            }
        ],
        problem_spec=spec,
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is True
    diagnostic = summary["mechanism_diagnostics"][0]
    assert diagnostic["activation_status"] == "observed"
    assert diagnostic["runtime_status"] == "zero"
    assert diagnostic["effect_status"] == "zero"
    assert diagnostic["activation"]["candidate_positive"] == 1
    assert diagnostic["runtime"]["candidate_zero"] == 1
    assert diagnostic["effect"]["candidate_zero"] == 2


def test_mechanism_diagnostics_report_move_only_as_activation_missing() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    activation_runtime_fields={
                        "{mechanism}": [
                            "mechanism_iterations.{mechanism}",
                            "mechanism_phase_runtime_ms.{mechanism}",
                        ]
                    },
                    effect_probe_runtime_fields={
                        "{mechanism}": [
                            "mechanism_improvement_counts.{mechanism}",
                            "mechanism_best_delta.{mechanism}",
                        ]
                    },
                ),
            )
        ]
    )

    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "mechanism_improvement_counts": {"target_probe": 0},
                "mechanism_best_delta": {"target_probe": 0.0},
            }
        ],
        problem_spec=spec,
        selected_surface="solver",
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is False
    assert summary["failures"][0]["code"] == (
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED"
    )
    diagnostic = summary["mechanism_diagnostics"][0]
    assert diagnostic["activation_status"] == "missing"
    assert diagnostic["runtime_status"] == "missing"
    assert diagnostic["effect_status"] == "zero"
    assert "direct activation telemetry" in diagnostic["repair_guidance"][0]


def test_explicit_mechanism_effect_claim_still_fails_when_not_observed() -> None:
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
                "mechanism_activation": {"target_probe": 1},
                "mechanism_effect": {"target_probe": 0.0},
            }
        ],
        problem_spec=spec,
        selected_surface="solver",
        expected_telemetry={"effect": {"target_probe": ["mechanism_effect"]}},
        declared_mechanisms=[
            MechanismChange(id="target_probe", change_type="modify")
        ],
    )

    assert summary["passed"] is False
    assert "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED" in [
        failure["code"] for failure in summary["failures"]
    ]


def test_runtime_path_parser_handles_dotted_brackets_and_indices() -> None:
    assert _parse_runtime_path("mechanisms['target_probe'].events[0].delta") == (
        "mechanisms",
        "target_probe",
        "events",
        "0",
        "delta",
    )


def test_evidence_value_checks_are_positive_empty_and_bounded() -> None:
    assert _positive_evidence({"zero": 0, "active": "yes"})
    assert not _positive_evidence(["0", "false", 0])
    assert _empty_value("")
    assert _empty_value([])
    assert not _empty_value(0)

    bounded = _bounded_value({"k" * 120: ["x" * 200 for _ in range(10)]})
    [(key, values)] = bounded.items()
    assert len(key) == 80
    assert len(values) == 8
    assert all(len(value) == 160 for value in values)
