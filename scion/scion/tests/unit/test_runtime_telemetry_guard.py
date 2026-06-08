from __future__ import annotations

from types import SimpleNamespace

from scion.core.models import (
    EvalStats,
    ExperimentStage,
    MechanismChange,
    ProtocolResult,
)
from scion.core.telemetry_validation import (
    is_repairable_telemetry_validation_failure,
    screened_experiment_effective,
    telemetry_validation_failure_codes,
)
from scion.runtime import surface_telemetry as surface_decl
from scion.runtime.telemetry_guard import (
    build_telemetry_guard_summary,
    declared_runtime_field_roles,
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
                        "solution_cost",
                        "violation_count",
                        "solver_best_delta",
                    ],
                    stage_budget_runtime_fields=["solver_phase_runtime_ms"],
                    runtime_field_roles={
                        "objective_outcome": ["solution_cost"],
                        "protected_outcome": ["violation_count"],
                        "aggregate_effect": ["solver_best_delta"],
                    },
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


def test_screening_telemetry_repairable_is_not_effective_formal_candidate() -> None:
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=8,
            wins=0,
            losses=1,
            ties=7,
            win_rate=0.0,
            median_delta=-0.5,
            ci_low=-9.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("TELEMETRY_GUARD_FAILED", "TELEMETRY_BUDGET_STARVED"),
        exposed_summary=(
            "telemetry guard observed stage budget starvation: "
            "solver_algorithm_phase_runtime_ms.alns had no positive evidence"
        ),
        raw_metrics_ref="/tmp/screening.json",
        candidate_surface_runtime_summary={
            "telemetry_guard": {
                "schema": "scion.telemetry_guard.v1",
                "selected_surface": "solver_design",
                "passed": False,
                "expected_telemetry_present": True,
                "failures": [
                    {
                        "code": "TELEMETRY_BUDGET_STARVED",
                        "severity": "fail",
                        "category": "budget",
                        "field": "solver_algorithm_phase_runtime_ms.alns",
                        "candidate_positive": 0,
                        "candidate_present": 0,
                        "candidate_missing": 16,
                        "champion_positive": 0,
                    }
                ],
            }
        },
    )

    assert is_repairable_telemetry_validation_failure(protocol) is True
    assert screened_experiment_effective(protocol) is False
    assert telemetry_validation_failure_codes(protocol) == (
        "TELEMETRY_VALIDATION_REPAIRABLE",
        "SCREENING_TELEMETRY_REPAIRABLE",
        "TELEMETRY_BUDGET_STARVED",
    )


def test_telemetry_guard_distinguishes_present_all_zero_activity() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {"solver_search_iterations": 0},
            {"solver_search_iterations": 0},
        ],
        champion_runtimes=[{"solver_search_iterations": 7}],
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={"activity": ["solver_search_iterations"]},
    )

    assert summary["passed"] is False
    assert summary["failures"][0]["code"] == "TELEMETRY_ACTIVITY_FIELD_ALL_ZERO"
    assert summary["failures"][0]["candidate_present"] == 2
    assert summary["failures"][0]["candidate_missing"] == 0
    assert (
        format_telemetry_guard_issue(summary)
        == "telemetry guard observed declared activity telemetry but all "
        "candidate values were zero: solver_search_iterations=0 across "
        "2 candidate run(s)"
    )


def test_telemetry_guard_keeps_missing_activity_not_observed_code() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[{}, {}],
        champion_runtimes=[{"solver_search_iterations": 7}],
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={"activity": ["solver_search_iterations"]},
    )

    assert summary["passed"] is False
    assert summary["failures"][0]["code"] == "TELEMETRY_ACTIVITY_NOT_OBSERVED"
    assert summary["failures"][0]["candidate_present"] == 0
    assert summary["failures"][0]["candidate_missing"] == 2


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
                "violation_count": 0,
                "solver_best_delta": 2.0,
            }
        ],
        champion_runtimes=[
            {
                "violation_count": 0,
                "solver_best_delta": 1.0,
            }
        ],
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={
            "effect": [
                "violation_count",
                "solver_best_delta",
            ]
        },
        protected_objectives=("violation_count",),
    )

    assert summary["passed"] is True
    assert summary["protected_objectives"] == ["violation_count"]
    assert summary["fields"]["violation_count"][
        "candidate_present"
    ] == 1
    assert summary["fields"]["violation_count"][
        "candidate_positive"
    ] == 0


def test_effect_objective_outcome_field_accepts_zero_when_present() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[{"violation_count": 0}],
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={"effect": ["violation_count"]},
    )

    assert summary["passed"] is True
    assert summary["failures"] == []
    assert summary["fields"]["violation_count"][
        "candidate_present"
    ] == 1
    assert summary["fields"]["violation_count"][
        "candidate_positive"
    ] == 0


def test_telemetry_guard_requires_protected_objective_probe_presence() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[{"solver_best_delta": 2.0}],
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={"effect": ["violation_count"]},
        protected_objectives=("violation_count",),
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
                            "solution_cost",
                            "planner_stage_runtime_ms",
                        ],
                        runtime_field_roles={
                            "objective_outcome": ["solution_cost"],
                        },
                    ),
                )
            ]
        ),
        selected_surface="solver",
        expected_telemetry={
            "activation": ["solution_cost"],
            "effect": ["solution_cost"],
        },
    )

    assert errors == (
        "expected_telemetry.activation references declared outcome field "
        "solution_cost (role(s): objective_outcome); activation must use "
        "mechanism-specific activity evidence declared by the selected "
        "research surface.",
    )


def test_synthetic_surface_declares_non_cvrp_telemetry_roles() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="planner_solver",
                evidence=SimpleNamespace(
                    required_runtime_fields=[
                        "planner_stage_runtime_ms",
                        "search_node_count",
                        "solution_cost",
                        "violation_count",
                    ],
                    activation_runtime_fields={
                        "{mechanism}": ["planner_stage_runtime_ms.{mechanism}"]
                    },
                    runtime_field_roles={
                        "mechanism_activation": [
                            "planner_stage_runtime_ms.{mechanism}"
                        ],
                        "activity": ["search_node_count"],
                        "objective_outcome": ["solution_cost"],
                        "protected_outcome": ["violation_count"],
                    },
                ),
            )
        ]
    )

    accepted = validate_expected_telemetry_contract(
        problem_spec=spec,
        selected_surface="planner_solver",
        expected_telemetry={
            "activation": ["planner_stage_runtime_ms.regret_seed"],
            "activity": ["search_node_count"],
            "effect": ["solution_cost", "violation_count"],
        },
        declared_mechanisms=[MechanismChange(id="regret_seed", change_type="add")],
    )
    rejected = validate_expected_telemetry_contract(
        problem_spec=spec,
        selected_surface="planner_solver",
        expected_telemetry={"activation": ["solution_cost"]},
        declared_mechanisms=[MechanismChange(id="regret_seed", change_type="add")],
    )
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "planner_stage_runtime_ms": {"regret_seed": 4},
                "search_node_count": 12,
                "solution_cost": 0,
                "violation_count": 0,
            }
        ],
        problem_spec=spec,
        selected_surface="planner_solver",
        expected_telemetry={
            "activation": ["planner_stage_runtime_ms.regret_seed"],
            "activity": ["search_node_count"],
            "effect": ["solution_cost", "violation_count"],
        },
        declared_mechanisms=[MechanismChange(id="regret_seed", change_type="add")],
        protected_objectives=("violation_count",),
    )

    assert accepted == ()
    assert rejected[0] == (
        "expected_telemetry.activation references declared outcome field "
        "solution_cost (role(s): objective_outcome); activation must use "
        "mechanism-specific activity evidence declared by the selected "
        "research surface."
    )
    assert "planner_stage_runtime_ms.regret_seed" in rejected[1]
    assert "selected_surface='planner_solver'" in rejected[1]
    assert summary["passed"] is True
    assert summary["fields"]["solution_cost"]["candidate_positive"] == 0
    assert summary["fields"]["violation_count"]["candidate_present"] == 1


def test_provider_level_telemetry_roles_are_used_by_generic_guard() -> None:
    spec = SimpleNamespace(
        telemetry_guard=SimpleNamespace(
            runtime_field_roles={
                "mechanism_activation": ["planner_stage_runtime_ms.{mechanism}"],
                "objective_outcome": ["solution_cost"],
            }
        ),
        research_surfaces=[
            SimpleNamespace(
                name="planner_solver",
                evidence=SimpleNamespace(required_runtime_fields=["solution_cost"]),
            )
        ],
    )

    errors = validate_expected_telemetry_contract(
        problem_spec=spec,
        selected_surface="planner_solver",
        expected_telemetry={"activation": ["solution_cost"]},
    )
    accepted = validate_expected_telemetry_contract(
        problem_spec=spec,
        selected_surface="planner_solver",
        expected_telemetry={
            "activation": ["planner_stage_runtime_ms.regret_seed"],
        },
        declared_mechanisms=["regret_seed"],
    )

    assert accepted == ()
    assert errors[0] == (
        "expected_telemetry.activation references declared outcome field "
        "solution_cost (role(s): objective_outcome); activation must use "
        "mechanism-specific activity evidence declared by the selected "
        "research surface."
    )
    assert "planner_stage_runtime_ms.<mechanism_id>" in errors[1]


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


def test_guard_declaration_fields_match_surface_telemetry_source() -> None:
    surface = SimpleNamespace(
        name="solver",
        evidence=SimpleNamespace(
            required_runtime_fields=[
                "solver_loaded",
                "solver_active",
                "solver_errors",
            ],
            optional_runtime_fields=["solver_optional_counter"],
            activity_runtime_fields=["solver_iterations"],
            activation_runtime_fields={
                "{mechanism}": ["mechanisms.{mechanism}.active"]
            },
            effect_probe_runtime_fields=[
                "mechanisms.{mechanism}.delta",
                "solver_best_delta",
            ],
            stage_budget_runtime_fields=["solver_budget_ms"],
            phase_runtime_fields=["solver_phase_runtime_ms"],
            runtime_field_roles={
                "diagnostic": ["solver_errors"],
                "protected_outcome": ["solution_cost"],
            },
        ),
    )
    problem_spec = SimpleNamespace(research_surfaces=[surface])
    declared_mechanisms = ("target_probe",)

    guard_fields = declared_surface_telemetry_fields(
        surface,
        problem_spec=problem_spec,
        declared_mechanisms=declared_mechanisms,
    )
    surface_fields = surface_decl.declared_surface_telemetry_fields(
        surface,
        problem_spec=problem_spec,
        declared_mechanisms=declared_mechanisms,
    )

    assert guard_fields == surface_fields
    assert "solver_phase_runtime_ms" in guard_fields
    assert "mechanisms.target_probe.active" in guard_fields
    assert "mechanisms.{mechanism}.active" not in guard_fields
    assert validate_expected_telemetry_contract(
        problem_spec=problem_spec,
        selected_surface="solver",
        expected_telemetry={"budget": ["solver_phase_runtime_ms"]},
        declared_mechanisms=declared_mechanisms,
    ) == ()
    assert declared_runtime_field_roles(
        surface,
        problem_spec=problem_spec,
        declared_mechanisms=declared_mechanisms,
    ) == surface_decl.declared_runtime_field_roles(
        surface,
        problem_spec=problem_spec,
        declared_mechanisms=declared_mechanisms,
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

    assert "mechanisms.search_seed.active" in declared_surface_telemetry_fields(
        surface,
        declared_mechanisms=("search_seed",),
    )
    assert validate_expected_telemetry_contract(
        problem_spec=problem_spec,
        selected_surface="solver",
        expected_telemetry={"activation": ["mechanisms.search_seed.active"]},
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

    assert summary["passed"] is True
    assert summary["failures"] == []
    assert [warning["code"] for warning in summary["warnings"]] == [
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
        "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
    ]
    assert {warning["diagnostic_kind"] for warning in summary["warnings"]} == {
        "evaluated_no_effect"
    }
    assert (
        summary["mechanisms"]["target_probe"]["fields"]["mechanism_activation"][
            "candidate_positive"
        ]
        == 0
    )


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
