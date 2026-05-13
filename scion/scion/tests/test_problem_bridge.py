"""Tests for ProblemSpecV1 -> legacy ProblemSpec bridge."""
from __future__ import annotations

from pathlib import Path

import yaml

from scion.config.problem import ParameterSearchConfig, ProblemSpec
from scion.problem.bridge import (
    bridge_problem_spec_v1,
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problem.spec import ParameterSearchSpec, ProblemSpecV1


PROBLEMS_DIR = Path(__file__).resolve().parents[1] / "problems"


def _load_spec(path: Path, *, canary_case_path: str = "") -> ProblemSpecV1:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data["root_dir"] = str(path.parent)
    if canary_case_path:
        data["canary_case_path"] = canary_case_path
    return ProblemSpecV1(**data)


def test_toy_tsp_bridge_maps_legacy_problem_spec_fields() -> None:
    toy_dir = PROBLEMS_DIR / "toy_tsp"
    spec = _load_spec(toy_dir / "problem.yaml", canary_case_path="data/tsp_10.json")

    legacy = legacy_problem_spec_from_v1(spec)

    assert isinstance(legacy, ProblemSpec)
    assert legacy.name == "toy_tsp"
    assert legacy.root_dir == str(toy_dir.resolve())
    assert legacy.description.startswith("Minimal Travelling Salesman")
    assert legacy.operator_categories == ["local_search"]
    assert legacy.search_space.editable == ["operators/*.py"]
    assert legacy.search_space.frozen == ["solver.py", "models.py", "oracle.py"]
    assert legacy.search_space.import_whitelist == [
        "__future__",
        "math",
        "random",
        "typing",
    ]
    assert legacy.solver.time_limit_sec == 30
    assert legacy.solver.max_iter == 100
    assert legacy.parameter_search.enabled is False
    assert legacy.canary_case_path == str((toy_dir / "data" / "tsp_10.json").resolve())


def test_bridge_exposes_runtime_fields_kept_out_of_legacy_spec() -> None:
    toy_dir = PROBLEMS_DIR / "toy_tsp"
    spec = _load_spec(toy_dir / "problem.yaml", canary_case_path="data/tsp_10.json")

    bridge = bridge_problem_spec_v1(spec)

    assert bridge.spec_v1 is spec
    assert bridge.problem_spec.name == "toy_tsp"
    assert bridge.problem_spec.spec_version == "problem-v1"
    assert bridge.problem_spec.adapter_import_path == spec.adapter.import_path
    assert bridge.problem_spec.requires_adapter_for_runtime is True
    assert [metric.name for metric in bridge.metric_specs] == ["tour_cost"]
    assert bridge.objective_policy.mode == "single"
    assert (
        bridge.operator_execute_signature
        == "execute(self, solution, instance, rng) -> TspSolution"
    )
    assert not hasattr(bridge.problem_spec, "operator_execute_signature")


def test_cvrp_bridge_maps_route_native_categories_and_objectives() -> None:
    cvrp_dir = PROBLEMS_DIR / "cvrp"
    spec = _load_spec(cvrp_dir / "problem-v1.yaml")

    bridge = bridge_problem_spec_v1(spec)
    legacy = bridge.problem_spec

    assert legacy.name == "cvrp"
    assert legacy.root_dir == str(cvrp_dir.resolve())
    assert legacy.operator_categories == [
        "route_local",
        "route_pair",
        "ruin_recreate",
        "search_policy",
        "baseline_policy",
        "construction_policy",
        "neighborhood_portfolio",
        "algorithm_blueprint",
        "solver_design",
        "main_search_strategy",
        "alns_vns_policy",
        "destroy_repair_policy",
        "route_pair_candidate_policy",
        "acceptance_restart_policy",
    ]
    assert [surface.name for surface in legacy.research_surfaces] == [
        "route_local",
        "route_pair",
        "ruin_recreate",
        "search_policy",
        "baseline_policy",
        "construction_policy",
        "neighborhood_portfolio",
        "algorithm_blueprint",
        "solver_design",
        "main_search_strategy",
        "alns_vns_policy",
        "destroy_repair_policy",
        "route_pair_candidate_policy",
        "acceptance_restart_policy",
    ]
    assert legacy.family_taxonomy.families == [
        "route_local",
        "route_pair",
        "ruin_recreate",
        "search_policy",
        "baseline_policy",
        "construction_policy",
        "neighborhood_portfolio",
        "algorithm_blueprint",
        "solver_design",
        "alns_vns_policy",
        "destroy_repair_policy",
        "route_pair_candidate_policy",
        "acceptance_restart_policy",
    ]
    assert "intra-route" in legacy.family_taxonomy.aliases["route_local"]
    assert "route-pair" in legacy.family_taxonomy.aliases["route_pair"]
    assert "ruin" in legacy.family_taxonomy.aliases["ruin_recreate"]
    assert "alns/vns policy" in legacy.family_taxonomy.aliases["alns_vns_policy"]
    assert legacy.search_space.frozen == [
        "adapter.py",
        "cvrplib.py",
        "models.py",
        "solver.py",
        "operators/base.py",
        "operators/__init__.py",
        "policies/__init__.py",
    ]
    assert "policies/*.py" in legacy.search_space.editable
    assert "dataclasses" in legacy.search_space.import_whitelist
    assert legacy.parameter_search.enabled is False
    assert legacy.canary_case_path == str((cvrp_dir / "data" / "tiny_canary.json").resolve())
    assert [metric.name for metric in bridge.metric_specs] == [
        "fleet_violation",
        "total_distance",
    ]
    assert bridge.objective_policy.mode == "lexicographic"
    assert (
        bridge.operator_execute_signature
        == "execute(self, solution, instance, rng) -> CvrpSolution"
    )
    assert spec.runtime_dependencies.required_python_modules == ["numpy"]
    assert legacy.runtime_dependencies.required_python_modules == ["numpy"]


def test_warehouse_problem_spec_declares_legacy_family_taxonomy() -> None:
    warehouse_dir = PROBLEMS_DIR / "warehouse_delivery"
    spec = _load_spec(warehouse_dir / "problem-v1.yaml")

    assert spec.family_taxonomy is not None
    assert "subcategory_consolidation" in spec.family_taxonomy.families
    assert "order_swap" in spec.family_taxonomy.families
    assert "cost_reduction" in spec.family_taxonomy.families
    assert "subcategory swap" in spec.family_taxonomy.aliases["subcategory_consolidation"]
    assert "swap orders" in spec.family_taxonomy.aliases["order_swap"]
    assert "downsize" in spec.family_taxonomy.aliases["cost_reduction"]


def test_load_problem_spec_v1_resolves_placeholder_root_dir() -> None:
    cvrp_dir = PROBLEMS_DIR / "cvrp"
    spec = load_problem_spec_v1_from_yaml(cvrp_dir / "problem-v1.yaml")

    assert spec.root_dir == str(cvrp_dir)
    legacy = legacy_problem_spec_from_v1(spec)
    assert legacy.root_dir == str(cvrp_dir.resolve())
    assert legacy.canary_case_path == str((cvrp_dir / "data" / "tiny_canary.json").resolve())


def test_bridge_preserves_shared_parameter_search_fields() -> None:
    toy_dir = PROBLEMS_DIR / "toy_tsp"
    spec = _load_spec(toy_dir / "problem.yaml")
    tuned = spec.model_copy(
        update={
            "parameter_search": ParameterSearchSpec(
                enabled=True,
                n_initial_random=3,
                n_iterations=5,
                n_eval_seeds=2,
                weight_bounds=(0.2, 2.0),
                eval_cases=["data/tsp_10.json"],
            )
        }
    )

    legacy = legacy_problem_spec_from_v1(tuned)

    assert isinstance(legacy.parameter_search, ParameterSearchConfig)
    assert legacy.parameter_search.enabled is True
    assert legacy.parameter_search.n_initial_random == 3
    assert legacy.parameter_search.n_iterations == 5
    assert legacy.parameter_search.weight_bounds == (0.2, 2.0)
    assert legacy.parameter_search.eval_cases == ["data/tsp_10.json"]
    assert legacy.parameter_search.execution == "async"
