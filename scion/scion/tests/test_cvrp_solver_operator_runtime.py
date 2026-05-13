"""CVRP solver registry-operator runtime tests."""
from __future__ import annotations

import json
import random
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from scion.contract.gate import ContractGate
from scion.core.models import PatchProposal
from scion.problem.bridge import load_problem_spec_v1_from_yaml, legacy_problem_spec_from_v1
from scion.problems.cvrp import solver as cvrp_solver
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution
from scion.runtime.audit import runtime_audit_failure_from_raw, runtime_audit_failure_from_result
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.verification.state_mutation import check_state_mutation


CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"


class _Spec:
    pass


def _default_algorithm_body() -> dict[str, Any]:
    return {
        "phase_sequence": [
            "construction",
            "baseline",
            "global_recombination",
            "route_structure_repair",
            "local_cleanup",
        ],
        "baseline_budget_policy": "declared",
        "route_pool_activation": "adaptive",
        "route_pool_min_customers": 80,
        "route_pool_max_rounds": 8,
        "local_cleanup_after_recombination": False,
        "adaptive_component_budget": True,
    }


def _runner() -> LocalSubprocessRunner:
    return LocalSubprocessRunner(ResourceLimits(timeout_sec=10, memory_mb=1024))


def _workspace(tmp_path: Path) -> Path:
    target = tmp_path / "cvrp_ws"
    shutil.copytree(CVRP_DIR, target)
    return target


def _write_operator_case(workspace: Path) -> Path:
    data_dir = workspace / "data"
    data_dir.mkdir(exist_ok=True)
    case_path = data_dir / "operator_case.json"
    case_path.write_text(
        json.dumps(
            {
                "name": "operator_case",
                "capacity": 99,
                "depot": 0,
                "allowed_routes": 1,
                "use_integer_cost": True,
                "nodes": [
                    {"id": 0, "x": 0, "y": 0, "demand": 0},
                    {"id": 1, "x": 0, "y": 1, "demand": 1},
                    {"id": 2, "x": 0, "y": 2, "demand": 1},
                    {"id": 3, "x": 0, "y": 3, "demand": 1},
                    {"id": 4, "x": 1, "y": 0, "demand": 1},
                    {"id": 5, "x": 2, "y": 5, "demand": 1},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return case_path


def _write_route_pair_swap_case(workspace: Path) -> Path:
    data_dir = workspace / "data"
    data_dir.mkdir(exist_ok=True)
    case_path = data_dir / "route_pair_swap_case.json"
    case_path.write_text(
        json.dumps(
            {
                "name": "route_pair_swap_case",
                "capacity": 2,
                "depot": 0,
                "allowed_routes": 2,
                "use_integer_cost": True,
                "nodes": [
                    {"id": 0, "x": 0, "y": 0, "demand": 0},
                    {"id": 1, "x": 0, "y": 10, "demand": 1},
                    {"id": 2, "x": 100, "y": 10, "demand": 1},
                    {"id": 3, "x": 0, "y": 11, "demand": 1},
                    {"id": 4, "x": 100, "y": 11, "demand": 1},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return case_path


def _write_synthetic_vrp(tmp_path: Path) -> Path:
    path = tmp_path / "operator_runtime_smoke.vrp"
    path.write_text(
        "\n".join(
            [
                "NAME : operator_runtime_smoke",
                "TYPE : CVRP",
                "DIMENSION : 4",
                "EDGE_WEIGHT_TYPE : EUC_2D",
                "CAPACITY : 10",
                "NODE_COORD_SECTION",
                "1 0 0",
                "2 10 0",
                "3 10 10",
                "4 0 10",
                "DEMAND_SECTION",
                "1 0",
                "2 4",
                "3 3",
                "4 2",
                "DEPOT_SECTION",
                "1",
                "-1",
                "EOF",
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.with_suffix(".sol").write_text(
        "Route #1: 2 3 4\nCost : 40\n",
        encoding="utf-8",
    )
    return path


def _run_solver(
    workspace: Path,
    instance_path: str,
    *,
    seed: int = 14,
    registry_path: str | None = None,
) -> dict[str, Any]:
    result = _runner().run_solver(
        workdir=str(workspace),
        instance_path=instance_path,
        seed=seed,
        time_limit_sec=2,
        registry_path="" if registry_path is None else registry_path,
    )
    assert result.success is True, result.stderr
    assert result.output is not None
    assert result.output.feasible is True
    assert result.output_path is not None

    output_path = Path(result.output_path)
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    finally:
        output_path.unlink(missing_ok=True)


def _artifact(raw: dict[str, Any], workspace: Path, instance_path: str):
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    instance = adapter.load_instance(str(workspace / instance_path))
    artifact = adapter.deserialize_solver_output(raw, instance)
    return adapter, instance, artifact


def test_empty_registry_keeps_json_nearest_neighbor_behavior(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert raw["objective"] == {
        "fleet_violation": 0,
        "total_distance": 16.0,
        "routes": 1,
    }
    assert raw["runtime"]["operator_loaded"] == 0
    assert raw["runtime"]["operator_attempts"] == 0
    assert raw["runtime"]["algorithm_blueprint_loaded"] is True
    assert raw["runtime"]["algorithm_blueprint_active"] is False
    assert raw["runtime"]["algorithm_blueprint_errors"] == 0
    assert raw["runtime"]["algorithm_stop_reason"] == "inactive"

    adapter, instance, artifact = _artifact(raw, workspace, "data/operator_case.json")
    assert adapter.check_solution_consistency(artifact, instance).passed is True
    assert adapter.check_feasibility(artifact, instance).passed is True
    assert adapter.recompute_objective(artifact, instance) == raw["objective"]


def test_missing_registry_keeps_vrp_nearest_neighbor_behavior(
    tmp_path: Path,
) -> None:
    vrp_path = _write_synthetic_vrp(tmp_path)

    raw = _run_solver(CVRP_DIR, str(vrp_path), seed=11, registry_path=None)

    assert raw["objective"] == {
        "fleet_violation": 0,
        "total_distance": 40.0,
        "routes": 1,
    }
    assert raw["runtime"]["operator_loaded"] == 0
    assert raw["runtime"]["operator_attempts"] == 0


def test_registry_operator_can_improve_route_and_is_audited(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "better_route.py").write_text(
        "\n".join(
            [
                "from scion.problems.cvrp.models import CvrpSolution",
                "",
                "class BetterRoute:",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2, 3, 5, 4),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: better_route",
                "    file_path: operators/better_route.py",
                "    class_name: BetterRoute",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 5, 4]]
    assert raw["objective"] == {
        "fleet_violation": 0,
        "total_distance": 12.0,
        "routes": 1,
    }
    assert raw["runtime"]["operator_loaded"] == 1
    assert raw["runtime"]["operator_accepted"] == 1
    assert raw["runtime"]["operator_attempts"] == 2
    assert raw["runtime"]["operator_rounds"] == 2
    assert raw["runtime"]["operator_rounds_with_acceptance"] == 1
    assert raw["runtime"]["operator_no_improvement_rounds"] == 1
    assert raw["runtime"]["operator_stop_reason"] == "no_improvement_round"
    assert {
        (event["operator"], event["status"])
        for event in raw["runtime"]["operator_events"]
    } >= {("better_route", "accepted")}

    adapter, instance, artifact = _artifact(raw, workspace, "data/operator_case.json")
    assert adapter.check_solution_consistency(artifact, instance).passed is True
    assert adapter.check_feasibility(artifact, instance).passed is True
    assert adapter.recompute_objective(artifact, instance) == raw["objective"]


def test_noop_registry_operator_stops_after_one_no_improvement_round(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "noop.py").write_text(
        "\n".join(
            [
                "class NoopOperator:",
                "    def execute(self, solution, instance, rng):",
                "        return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: noop_operator",
                "    file_path: operators/noop.py",
                "    class_name: NoopOperator",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert raw["objective"]["total_distance"] == 16.0
    assert raw["runtime"]["operator_loaded"] == 1
    assert raw["runtime"]["operator_attempts"] == 1
    assert raw["runtime"]["operator_accepted"] == 0
    assert raw["runtime"]["operator_rounds"] == 1
    assert raw["runtime"]["operator_rounds_with_acceptance"] == 0
    assert raw["runtime"]["operator_no_improvement_rounds"] == 1
    assert raw["runtime"]["operator_stop_reason"] == "no_improvement_round"
    assert runtime_audit_failure_from_raw(raw) is None


def test_workspace_local_cvrp_solution_is_coerced_and_can_improve(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "local_model_better_route.py").write_text(
        "\n".join(
            [
                "from models import CvrpSolution",
                "",
                "class LocalModelBetterRoute:",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2, 3, 5, 4),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: local_model_better_route",
                "    file_path: operators/local_model_better_route.py",
                "    class_name: LocalModelBetterRoute",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 5, 4]]
    assert raw["objective"]["total_distance"] == 12.0
    assert raw["runtime"]["operator_accepted"] == 1
    assert raw["runtime"]["operator_errors"] == 0


def test_search_policy_surface_runtime_fields_match_solver_output(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "search_policy"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert required_fields == (
        "policy_loaded",
        "policy_errors",
        "baseline_time_fraction",
        "operator_round_limit",
        "post_baseline_operators_enabled",
    )
    assert set(required_fields).issubset(raw["runtime"])
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="search_policy",
    ) is None


def test_construction_policy_surface_runtime_fields_match_solver_output(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "construction_policy"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert required_fields == (
        "construction_surface_loaded",
        "construction_errors",
        "construction_mode",
        "construction_elapsed_ms",
        "construction_routes",
        "construction_distance",
        "construction_feasible",
    )
    assert set(required_fields).issubset(runtime)
    assert runtime["construction_surface_loaded"] is True
    assert runtime["construction_errors"] == 0
    assert runtime["construction_mode"] == "nearest_neighbor"
    assert runtime["construction_routes"] == len(raw["routes"])
    assert runtime["construction_distance"] == raw["objective"]["total_distance"]
    assert runtime["construction_feasible"] is True
    assert runtime["baseline_required"] is False
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="construction_policy",
    ) is None


def test_neighborhood_portfolio_surface_runtime_fields_match_solver_output(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "neighborhood_portfolio"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert required_fields == (
        "portfolio_surface_loaded",
        "portfolio_errors",
        "enabled_components",
        "component_weights",
        "candidate_limits",
        "component_attempts",
        "component_accepted",
        "component_runtime_ms",
        "portfolio_stop_reason",
    )
    assert set(required_fields).issubset(runtime)
    assert runtime["portfolio_surface_loaded"] is True
    assert runtime["portfolio_errors"] == 0
    assert "route_local" in runtime["enabled_components"]
    assert runtime["component_weights"]["route_local"] == 1.0
    assert runtime["candidate_limits"]["max_rounds"] == 3
    assert runtime["candidate_limits"]["top_k"] == 16
    assert runtime["component_attempts"]["route_local"] == 0
    assert runtime["component_accepted"]["route_local"] == 0
    assert runtime["component_runtime_ms"]["route_local"] == 0
    assert runtime["portfolio_stop_reason"] == "no_registry_operators"
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="neighborhood_portfolio",
    ) is None


def test_default_algorithm_blueprint_policy_matches_contract_gate_interface() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(CVRP_DIR / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    policy_path = CVRP_DIR / "policies" / "algorithm_blueprint.py"
    gate = ContractGate(legacy_spec)

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/algorithm_blueprint.py",
            action="modify",
            code_content=policy_path.read_text(encoding="utf-8"),
        )
    )

    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert result.passed is True
    assert c7.passed is True


def test_default_baseline_policy_matches_contract_gate_interface() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(CVRP_DIR / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    policy_path = CVRP_DIR / "policies" / "baseline_policy.py"
    gate = ContractGate(legacy_spec)

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_policy.py",
            action="modify",
            code_content=policy_path.read_text(encoding="utf-8"),
        )
    )

    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert result.passed is True
    assert c7.passed is True


def test_baseline_policy_surface_declares_runtime_fields_and_defaults(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "baseline_policy"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert required_fields == (
        "baseline_policy_loaded",
        "baseline_policy_errors",
        "baseline_policy_params",
        "baseline_destroy_ratio",
        "baseline_segment_length",
        "baseline_reaction_factor",
        "baseline_use_vns",
        "baseline_vns_max_no_improve",
        "baseline_max_destroy_customers",
    )
    assert set(required_fields).issubset(runtime)
    assert runtime["baseline_policy_loaded"] is True
    assert runtime["baseline_policy_errors"] == 0
    assert runtime["baseline_policy_params"]["destroy_ratio"] == [0.1, 0.4]
    assert runtime["baseline_destroy_ratio"] == [0.1, 0.4]
    assert runtime["baseline_use_vns"] is True
    assert runtime["baseline_vns_max_no_improve"] == 5000
    assert runtime["baseline_max_destroy_customers"] == 200
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="baseline_policy",
        )
        is None
    )


def test_invalid_baseline_policy_output_is_runtime_audit_failure(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_policy.py").write_text(
        "\n".join(
            [
                "def baseline_params(instance, time_limit_sec):",
                "    return {",
                "        'destroy_ratio': (0.9, 0.1),",
                "        'segment_length': 0,",
                "        'use_vns': 'yes',",
                "        'unknown': 1,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="baseline_policy",
    )

    assert raw["runtime"]["baseline_policy_errors"] == 5
    assert raw["runtime"]["baseline_policy_params"]["destroy_ratio"] == [0.1, 0.4]
    assert raw["runtime"]["baseline_segment_length"] == 1
    assert raw["runtime"]["baseline_use_vns"] is True
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"
    assert "baseline_policy_errors" in issue["detail"]
    assert "unknown" in json.dumps(raw["runtime"]["baseline_policy_events"])


def test_modified_baseline_policy_changes_repo_local_baseline_kwargs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    fake_root = tmp_path / "fake_vrp"
    fake_src = fake_root / "src"
    fake_src.mkdir(parents=True)
    (fake_src / "__init__.py").write_text("", encoding="utf-8")
    (fake_src / "parser.py").write_text(
        "\n".join(
            [
                "from types import SimpleNamespace",
                "",
                "def parse_vrp(path):",
                "    return SimpleNamespace(depot=0, dimension=4)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    capture_path = tmp_path / "baseline_kwargs.json"
    (fake_src / "solver.py").write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "from types import SimpleNamespace",
                "",
                "def solve(instance, **kwargs):",
                "    capture = os.environ.get('SCION_FAKE_BASELINE_CAPTURE')",
                "    if capture:",
                "        with open(capture, 'w', encoding='utf-8') as f:",
                "            json.dump(kwargs, f, sort_keys=True)",
                "    route = SimpleNamespace(customers=[1, 2, 3])",
                "    solution = SimpleNamespace(routes=[route])",
                "    return SimpleNamespace(",
                "        solution=solution,",
                "        elapsed=0.01,",
                "        iterations=3,",
                "        best_cost=30.0,",
                "    )",
                "",
            ]
        ),
        encoding="utf-8",
    )
    case_dir = fake_root / "cases"
    case_dir.mkdir()
    instance_path = case_dir / "case.vrp"
    instance_path.write_text("", encoding="utf-8")
    (workspace / "policies" / "baseline_policy.py").write_text(
        "\n".join(
            [
                "def baseline_params(instance, time_limit_sec):",
                "    return {",
                "        'destroy_ratio': (0.05, 0.25),",
                "        'segment_length': 25,",
                "        'reaction_factor': 0.3,",
                "        'vns_max_no_improve': 17,",
                "        'use_vns': False,",
                "        'cw_threshold': 7,",
                "        'vns_threshold': 8,",
                "        'alns_threshold': 9,",
                "        'max_destroy_customers': 11,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    instance = CvrpInstance(
        name="fake_baseline_case",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=1),
            CvrpNode(id=2, x=2.0, y=0.0, demand=1),
            CvrpNode(id=3, x=3.0, y=0.0, demand=1),
        ),
        allowed_routes=1,
        use_integer_cost=True,
    )
    monkeypatch.setenv("SCION_CVRP_DATA_ROOT", str(fake_root))
    monkeypatch.setenv("SCION_FAKE_BASELINE_CAPTURE", str(capture_path))
    for module_name in ("src", "src.parser", "src.solver"):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    baseline_policy = cvrp_solver._load_baseline_policy(
        workspace_root=workspace,
        instance=instance,
        time_limit_sec=2.0,
    )
    solution, audit = cvrp_solver.solve_baseline(
        instance=instance,
        instance_path=str(instance_path),
        seed=5,
        rng=random.Random(5),
        time_limit_sec=2.0,
        baseline_time_fraction=0.5,
        baseline_policy=baseline_policy,
    )
    if str(fake_root) in sys.path:
        sys.path.remove(str(fake_root))

    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert solution.routes == ((1, 2, 3),)
    assert captured["time_limit"] == 1.0
    assert captured["seed"] == 5
    assert captured["max_routes"] == 1
    assert captured["destroy_ratio"] == [0.05, 0.25]
    assert captured["segment_length"] == 25
    assert captured["reaction_factor"] == 0.3
    assert captured["vns_max_no_improve"] == 17
    assert captured["use_vns"] is False
    assert captured["cw_threshold"] == 7
    assert captured["vns_threshold"] == 8
    assert captured["alns_threshold"] == 9
    assert captured["max_destroy_customers"] == 11
    assert audit["baseline_mode"] == "vrp_alns_vns"
    assert audit["baseline_policy_errors"] == 0
    assert audit["baseline_destroy_ratio"] == [0.05, 0.25]
    assert audit["baseline_use_vns"] is False


def test_alns_vns_policy_overrides_repo_local_baseline_kwargs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    fake_root = tmp_path / "fake_vrp"
    fake_src = fake_root / "src"
    fake_src.mkdir(parents=True)
    (fake_src / "__init__.py").write_text("", encoding="utf-8")
    (fake_src / "parser.py").write_text(
        "\n".join(
            [
                "from types import SimpleNamespace",
                "",
                "def parse_vrp(path):",
                "    return SimpleNamespace(depot=0, dimension=4)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    capture_path = tmp_path / "alns_vns_kwargs.json"
    (fake_src / "solver.py").write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "from types import SimpleNamespace",
                "",
                "def solve(instance, **kwargs):",
                "    capture = os.environ.get('SCION_FAKE_BASELINE_CAPTURE')",
                "    if capture:",
                "        with open(capture, 'w', encoding='utf-8') as f:",
                "            json.dump(kwargs, f, sort_keys=True)",
                "    route = SimpleNamespace(customers=[1, 2, 3])",
                "    solution = SimpleNamespace(routes=[route])",
                "    return SimpleNamespace(",
                "        solution=solution,",
                "        elapsed=0.02,",
                "        iterations=4,",
                "        best_cost=28.0,",
                "    )",
                "",
            ]
        ),
        encoding="utf-8",
    )
    case_dir = fake_root / "cases"
    case_dir.mkdir()
    instance_path = case_dir / "case.vrp"
    instance_path.write_text("", encoding="utf-8")
    (workspace / "policies" / "alns_vns_policy.py").write_text(
        "\n".join(
            [
                "def alns_vns_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'components': ['alns'],",
                "        'component_weights': {'alns': 2.5, 'vns': 0.5},",
                "        'params': {",
                "            'destroy_ratio': (0.12, 0.2),",
                "            'segment_length': 31,",
                "            'reaction_factor': 0.25,",
                "            'vns_max_no_improve': 19,",
                "            'use_vns': False,",
                "            'cw_threshold': 6,",
                "            'vns_threshold': 7,",
                "            'alns_threshold': 8,",
                "            'max_destroy_customers': 9,",
                "        },",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    instance = CvrpInstance(
        name="fake_alns_vns_case",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=1),
            CvrpNode(id=2, x=2.0, y=0.0, demand=1),
            CvrpNode(id=3, x=3.0, y=0.0, demand=1),
        ),
        allowed_routes=1,
        use_integer_cost=True,
    )
    monkeypatch.setenv("SCION_CVRP_DATA_ROOT", str(fake_root))
    monkeypatch.setenv("SCION_FAKE_BASELINE_CAPTURE", str(capture_path))
    for module_name in ("src", "src.parser", "src.solver"):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    alns_vns_policy = cvrp_solver._load_alns_vns_policy(
        workspace_root=workspace,
        instance=instance,
        time_limit_sec=2.0,
    )
    solution, audit = cvrp_solver.solve_baseline(
        instance=instance,
        instance_path=str(instance_path),
        seed=5,
        rng=random.Random(5),
        time_limit_sec=2.0,
        baseline_time_fraction=0.5,
        alns_vns_policy=alns_vns_policy,
    )
    if str(fake_root) in sys.path:
        sys.path.remove(str(fake_root))

    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert solution.routes == ((1, 2, 3),)
    assert captured["destroy_ratio"] == [0.12, 0.2]
    assert captured["segment_length"] == 31
    assert captured["reaction_factor"] == 0.25
    assert captured["vns_max_no_improve"] == 19
    assert captured["use_vns"] is False
    assert captured["cw_threshold"] == 6
    assert captured["vns_threshold"] == 7
    assert captured["alns_threshold"] == 8
    assert captured["max_destroy_customers"] == 9
    assert audit["baseline_policy_params"]["segment_length"] == 31
    assert audit["alns_vns_surface_loaded"] is True
    assert audit["alns_vns_active"] is True
    assert audit["alns_vns_errors"] == 0
    assert audit["alns_vns_components"] == ["alns"]
    assert audit["alns_vns_component_weights"] == {"alns": 2.5, "vns": 0.5}
    assert audit["alns_vns_attempts"] == 4
    assert audit["alns_vns_accepted"] == 1
    assert audit["alns_vns_initial_distance"] == 6.0
    assert audit["alns_vns_returned_distance"] == 28.0
    assert audit["alns_vns_phase_delta_sum"] == 0.0
    assert audit["alns_vns_objective_delta"] == {
        "baseline_phase": 0.0,
        "initial_distance": 6.0,
        "returned_distance": 28.0,
    }
    assert audit["alns_vns_runtime_ms"] == 20
    assert audit["alns_vns_stop_reason"] == "vrp_alns_vns"


def test_alns_vns_policy_audit_records_positive_baseline_phase_delta() -> None:
    policy = cvrp_solver._alns_vns_policy_defaults()
    policy["alns_vns_active"] = True

    audit = cvrp_solver._finalize_alns_vns_policy_audit(
        policy,
        {
            "baseline_mode": "vrp_alns_vns",
            "baseline_elapsed_s": 0.5,
            "baseline_iterations": 12,
            "baseline_cost": 90.0,
        },
        construction_audit={"construction_distance": 125.0},
    )

    assert audit["alns_vns_attempts"] == 12
    assert audit["alns_vns_accepted"] == 1
    assert audit["alns_vns_initial_distance"] == 125.0
    assert audit["alns_vns_returned_distance"] == 90.0
    assert audit["alns_vns_phase_delta_sum"] == 35.0
    assert audit["alns_vns_objective_delta"] == {
        "baseline_phase": 35.0,
        "initial_distance": 125.0,
        "returned_distance": 90.0,
    }


def test_active_main_search_declared_baseline_fraction_controls_formal_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    fake_root = tmp_path / "fake_vrp"
    fake_src = fake_root / "src"
    fake_src.mkdir(parents=True)
    (fake_src / "__init__.py").write_text("", encoding="utf-8")
    (fake_src / "parser.py").write_text(
        "from types import SimpleNamespace\n\n"
        "def parse_vrp(path):\n"
        "    return SimpleNamespace(depot=0, dimension=4)\n",
        encoding="utf-8",
    )
    capture_path = tmp_path / "baseline_kwargs.json"
    (fake_src / "solver.py").write_text(
        "import json\n"
        "import os\n"
        "from types import SimpleNamespace\n\n"
        "def solve(instance, **kwargs):\n"
        "    capture = os.environ.get('SCION_FAKE_BASELINE_CAPTURE')\n"
        "    if capture:\n"
        "        with open(capture, 'w', encoding='utf-8') as f:\n"
        "            json.dump(kwargs, f, sort_keys=True)\n"
        "    route = SimpleNamespace(customers=[1, 2, 3])\n"
        "    solution = SimpleNamespace(routes=[route])\n"
        "    return SimpleNamespace(solution=solution, elapsed=0.01, iterations=3, best_cost=30.0)\n",
        encoding="utf-8",
    )
    case_dir = fake_root / "cases"
    case_dir.mkdir()
    instance_path = case_dir / "case.vrp"
    instance_path.write_text("", encoding="utf-8")
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.2, 'params': {}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair'], 'rounds': 1, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    instance = CvrpInstance(
        name="fake_baseline_case",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=1),
            CvrpNode(id=2, x=2.0, y=0.0, demand=1),
            CvrpNode(id=3, x=3.0, y=0.0, demand=1),
        ),
        allowed_routes=1,
        use_integer_cost=True,
    )
    monkeypatch.setenv("SCION_CVRP_DATA_ROOT", str(fake_root))
    monkeypatch.setenv("SCION_FAKE_BASELINE_CAPTURE", str(capture_path))
    for module_name in ("src", "src.parser", "src.solver"):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    main_search_strategy = cvrp_solver._load_main_search_strategy(
        workspace_root=workspace,
        instance=instance,
        time_limit_sec=2.0,
    )
    solution, audit = cvrp_solver.solve_baseline(
        instance=instance,
        instance_path=str(instance_path),
        seed=5,
        rng=random.Random(5),
        time_limit_sec=2.0,
        baseline_time_fraction=main_search_strategy[
            "main_search_baseline_time_fraction"
        ],
        main_search_strategy=main_search_strategy,
    )
    if str(fake_root) in sys.path:
        sys.path.remove(str(fake_root))

    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert solution.routes == ((1, 2, 3),)
    assert main_search_strategy["main_search_baseline_time_fraction"] == 0.2
    assert main_search_strategy["main_search_baseline_budget_policy"] == "declared"
    assert captured["time_limit"] == 0.4
    assert audit["main_search_baseline_time_fraction_effective"] == 0.2
    assert audit["main_search_baseline_quality_guard_applied"] is False


def test_active_main_search_formal_floor_budget_policy_clamps_budget() -> None:
    main_search_strategy = {
        "main_search_strategy_active": True,
        "main_search_baseline_budget_policy": "formal_floor",
    }

    assert (
        cvrp_solver._effective_baseline_time_fraction(
            0.2,
            is_vrp=True,
            baseline_required=True,
            main_search_strategy=main_search_strategy,
        )
        == 0.75
    )


def test_algorithm_blueprint_surface_declares_runtime_fields_and_default_is_inactive(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "algorithm_blueprint"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert required_fields == (
        "algorithm_blueprint_loaded",
        "algorithm_blueprint_active",
        "algorithm_blueprint_errors",
        "algorithm_plan",
        "algorithm_phases_executed",
        "algorithm_construction_methods",
        "algorithm_baseline_time_fraction",
        "algorithm_operator_round_limit",
        "algorithm_post_baseline_operators_enabled",
        "algorithm_local_search_components",
        "algorithm_local_search_rounds",
        "algorithm_local_search_attempts",
        "algorithm_local_search_accepted",
        "algorithm_restart_enabled",
        "algorithm_restart_stagnation_rounds",
        "algorithm_restart_count",
        "algorithm_best_delta_by_phase",
        "algorithm_phase_runtime_ms",
        "algorithm_stop_reason",
    )
    assert set(required_fields).issubset(runtime)
    assert runtime["algorithm_blueprint_loaded"] is True
    assert runtime["algorithm_blueprint_active"] is False
    assert runtime["algorithm_plan"]["enabled"] is False
    assert runtime["algorithm_phases_executed"] == ["inactive"]
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="algorithm_blueprint",
    )
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"


def test_enabled_algorithm_blueprint_runs_package_owned_local_search_without_solver_edit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    solver_before = (workspace / "solver.py").read_text(encoding="utf-8")
    (workspace / "policies" / "algorithm_blueprint.py").write_text(
        "\n".join(
            [
                "def algorithm_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'construction_methods': ['nearest_neighbor'],",
                "        'construction_keep_top_k': 1,",
                "        'construction_bias': 0.0,",
                "        'baseline_time_fraction': 0.8,",
                "        'operator_round_limit': 0,",
                "        'post_baseline_operators_enabled': False,",
                "        'local_search': {",
                "            'enabled_components': ['intra_route_2opt'],",
                "            'rounds': 2,",
                "            'top_k': 32,",
                "        },",
                "        'restart': {'enabled': True, 'stagnation_rounds': 1},",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert (workspace / "solver.py").read_text(encoding="utf-8") == solver_before
    assert raw["routes"] == [[1, 2, 3, 5, 4]]
    assert raw["objective"]["total_distance"] == 12.0
    assert runtime["algorithm_blueprint_loaded"] is True
    assert runtime["algorithm_blueprint_active"] is True
    assert runtime["algorithm_blueprint_errors"] == 0
    assert runtime["algorithm_plan"]["enabled"] is True
    assert runtime["post_baseline_operators_enabled"] is False
    assert runtime["operator_round_limit"] == 0
    assert runtime["algorithm_local_search_components"] == ["intra_route_2opt"]
    assert runtime["algorithm_local_search_attempts"] > 0
    assert runtime["algorithm_local_search_accepted"] == 1
    assert runtime["algorithm_restart_enabled"] is True
    assert runtime["algorithm_restart_stagnation_rounds"] == 1
    assert runtime["algorithm_restart_count"] == 1
    assert "construction_ensemble" in runtime["algorithm_phases_executed"]
    assert "baseline" in runtime["algorithm_phases_executed"]
    assert "local_search" in runtime["algorithm_phases_executed"]
    assert runtime["algorithm_best_delta_by_phase"]["local_search"] == 4.0
    assert runtime["operator_attempts"] == 0
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="algorithm_blueprint",
        )
        is None
    )


def test_invalid_algorithm_blueprint_output_is_runtime_audit_failure(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "algorithm_blueprint.py").write_text(
        "\n".join(
            [
                "def algorithm_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'construction_methods': ['nearest_neighbor'],",
                "        'construction_keep_top_k': 1,",
                "        'construction_bias': 0.0,",
                "        'baseline_time_fraction': 0.8,",
                "        'operator_round_limit': 0,",
                "        'post_baseline_operators_enabled': False,",
                "        'local_search': {'enabled_components': ['unknown_move'], 'rounds': 1, 'top_k': 8},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0},",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="algorithm_blueprint",
    )

    assert raw["runtime"]["algorithm_blueprint_errors"] == 1
    assert raw["runtime"]["algorithm_blueprint_active"] is False
    assert raw["runtime"]["algorithm_stop_reason"] == "invalid_plan"
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"
    assert "algorithm_blueprint_errors" in issue["detail"]
    assert "unknown_move" in json.dumps(raw["runtime"]["algorithm_blueprint_events"])


def test_default_main_search_strategy_policy_matches_contract_gate_interface() -> None:
    spec = load_problem_spec_v1_from_yaml(CVRP_DIR / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))
    policy_path = CVRP_DIR / "policies" / "main_search_strategy.py"

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/main_search_strategy.py",
            action="modify",
            code_content=policy_path.read_text(encoding="utf-8"),
        )
    )

    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert c7.passed, c7.detail


def test_main_search_strategy_surface_declares_runtime_fields_and_default_is_inactive(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "main_search_strategy"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert "main_search_strategy_loaded" in required_fields
    assert "main_search_strategy_errors" in required_fields
    assert "main_search_problem_adaptation" in required_fields
    assert "main_search_algorithm_body" in required_fields
    assert "main_search_algorithm_body_source" in required_fields
    assert "main_search_strategy_family" in required_fields
    assert "main_search_instance_profile" in required_fields
    assert "main_search_component_roles" in required_fields
    assert "main_search_component_order" in required_fields
    assert "main_search_phase_component_order" in required_fields
    assert "main_search_evidence_targets" in required_fields
    assert "main_search_selected_components" in required_fields
    assert "main_search_attempted_components" in required_fields
    assert "main_search_component_coverage_status" in required_fields
    assert "main_search_deep_components_selected" in required_fields
    assert "main_search_component_attempts" in required_fields
    assert "main_search_component_skip_reasons" in required_fields
    assert "main_search_component_repair_fallback_counts" in required_fields
    assert "main_search_baseline_time_fraction_effective" in required_fields
    assert "main_search_baseline_budget_policy" in required_fields
    assert "main_search_baseline_quality_guard_applied" in required_fields
    assert "main_search_baseline_params_clamped" in required_fields
    assert "main_search_baseline_param_clamps" in required_fields
    assert "main_search_component_min_distance_improvement" in required_fields
    assert "main_search_bounded_destroy_repair_accept_limit" in required_fields
    assert "main_search_best_returned" in required_fields
    assert "main_search_objective_trace" in required_fields
    assert "main_search_component_accepted_delta_sum" in required_fields
    assert "main_search_component_accepted_best_delta" in required_fields
    assert "main_search_component_accepted_positive_counts" in required_fields
    assert "main_search_component_recovery_delta_sum" in required_fields
    assert "main_search_component_recovery_best_delta" in required_fields
    assert "main_search_component_recovery_counts" in required_fields
    assert "main_search_component_phase_delta_sum" in required_fields
    assert "main_search_component_phase_best_delta" in required_fields
    assert "main_search_component_phase_improvement_counts" in required_fields
    assert "main_search_component_top_k_effective" in required_fields
    assert "main_search_construction_pool_size" in required_fields
    assert "main_search_construction_pool_distances" in required_fields
    assert "main_search_route_pool_source_solutions" in required_fields
    assert "main_search_route_pool_sample_count" in required_fields
    assert "main_search_route_pool_size" in required_fields
    assert "main_search_route_pool_branch_calls" in required_fields
    assert "main_search_route_pool_recombined_routes" in required_fields
    assert "main_search_route_pool_auto_added" in required_fields
    assert "main_search_route_pool_invocations" in required_fields
    assert "main_search_route_pool_activation" in required_fields
    assert "main_search_route_pool_min_customers" in required_fields
    assert "main_search_route_pool_max_rounds" in required_fields
    assert "main_search_local_cleanup_after_recombination" in required_fields
    assert "main_search_adaptive_component_budget" in required_fields
    assert "main_search_perturbation_schedule" in required_fields
    assert set(required_fields).issubset(runtime)
    assert runtime["main_search_strategy_loaded"] is True
    assert runtime["main_search_strategy_active"] is False
    assert runtime["main_search_plan"]["enabled"] is False
    assert runtime["main_search_strategy_family"] == "balanced_lifecycle"
    assert runtime["main_search_problem_adaptation_source"] == "declared"
    assert runtime["main_search_algorithm_body_source"] == "declared"
    assert runtime["main_search_algorithm_body"]["route_pool_activation"] == "adaptive"
    assert runtime["main_search_route_pool_auto_added"] is False
    assert runtime["main_search_route_pool_invocations"] == 0
    assert runtime["main_search_route_pool_min_customers"] == 80
    assert runtime["main_search_route_pool_max_rounds"] == 8
    assert runtime["main_search_phases"] == ["inactive"]
    assert runtime["main_search_component_coverage_status"]["status"] == "inactive"
    assert runtime["main_search_deep_components_selected"] == []
    assert runtime["main_search_baseline_quality_guard_applied"] is False
    assert runtime["main_search_baseline_params_clamped"] is False
    assert runtime["main_search_baseline_param_clamps"]["applied"] is False
    assert runtime["main_search_baseline_param_clamps"]["status"] == "no_clamps"
    assert runtime["main_search_best_returned"] is False
    assert runtime["main_search_objective_trace"]["status"] == "inactive"
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="main_search_strategy",
    )
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"
    assert "main_search_strategy_active" in issue["failed_runtime_fields"]


def test_solver_algorithm_surface_declares_runtime_fields_and_default_is_inactive(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(workspace, "data/operator_case.json")
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "solver_design"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert "solver_algorithm_loaded" in required_fields
    assert "solver_algorithm_active" in required_fields
    assert "solver_algorithm_phase_runtime_ms" in required_fields
    assert set(required_fields).issubset(runtime)
    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is False
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_stop_reason"] == "inactive"
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    )
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"
    assert "solver_algorithm_active" in issue["failed_runtime_fields"]


def test_enabled_solver_algorithm_returns_valid_solution_and_skips_legacy_loop(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "solver_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    start = context.elapsed_ms()",
                "    solution = context.nearest_neighbor()",
                "    context.record_phase('construct', context.elapsed_ms() - start)",
                "    return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "search_policy.py").write_text(
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    raise RuntimeError('legacy search policy should not run')\n",
        encoding="utf-8",
    )
    (workspace / "policies" / "construction_policy.py").write_text(
        "def construction_mode(instance, time_limit_sec):\n"
        "    raise RuntimeError('legacy construction policy should not run')\n",
        encoding="utf-8",
    )

    raw = _run_solver(workspace, "data/operator_case.json")
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_solution_valid"] is True
    assert runtime["solver_algorithm_solution_routes"] >= 1
    assert runtime["solver_algorithm_total_distance"] > 0
    assert "construct" in runtime["solver_algorithm_phase_runtime_ms"]
    assert "inactive" not in runtime["solver_algorithm_phase_runtime_ms"]
    assert runtime["policy_loaded"] is False
    assert runtime["construction_surface_loaded"] is False
    assert runtime["main_search_strategy_active"] is False
    assert runtime["algorithm_blueprint_active"] is False
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    ) is None


def test_solver_algorithm_context_accepts_baseline_alias_and_objective_comparison(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "solver_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    seed = context.nearest_neighbor()",
                "    baseline = context.baseline(seed, time_limit_sec=0.1)",
                "    seed_obj = context.objective(seed)",
                "    baseline_obj = context.objective(baseline)",
                "    if baseline_obj <= seed_obj and baseline_obj[0] <= seed_obj[0]:",
                "        context.record_phase('baseline_alias', 1)",
                "        return baseline",
                "    return seed",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(workspace, "data/operator_case.json")
    runtime = raw["runtime"]

    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_baseline_calls"] == 1
    assert runtime["solver_algorithm_solution_valid"] is True
    assert "baseline_alias" in runtime["solver_algorithm_phase_runtime_ms"]


def test_enabled_main_search_strategy_runs_owned_main_loop_and_disables_registry_by_default(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    solver_before = (workspace / "solver.py").read_text(encoding="utf-8")
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor', 'sequential'], 'keep_top_k': 2, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.5, 'params': {'destroy_ratio': (0.05, 0.20), 'use_vns': False, 'max_destroy_customers': 16}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair', 'intra_route_2opt'], 'rounds': 3, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': True, 'stagnation_rounds': 1, 'max_restarts': 1},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert (workspace / "solver.py").read_text(encoding="utf-8") == solver_before
    assert raw["objective"]["total_distance"] == 12.0
    assert runtime["main_search_strategy_loaded"] is True
    assert runtime["main_search_strategy_active"] is True
    assert runtime["main_search_strategy_errors"] == 0
    assert runtime["main_search_plan"]["enabled"] is True
    assert runtime["baseline_time_fraction"] == 0.5
    assert runtime["main_search_baseline_time_fraction_effective"] == 0.5
    assert runtime["main_search_baseline_quality_guard_applied"] is False
    assert runtime["main_search_baseline_params_clamped"] is False
    assert runtime["main_search_baseline_param_clamps"] == {
        "applied": False,
        "status": "no_clamps",
        "count": 0,
        "fields": [],
        "clamps": {},
    }
    assert runtime["baseline_policy_params"]["destroy_ratio"] == [0.05, 0.2]
    assert runtime["baseline_use_vns"] is False
    assert runtime["post_baseline_operators_enabled"] is False
    assert runtime["operator_round_limit"] == 0
    assert runtime["main_search_components"] == [
        "bounded_destroy_repair",
        "intra_route_2opt",
    ]
    assert runtime["main_search_selected_components"] == [
        "bounded_destroy_repair",
        "intra_route_2opt",
    ]
    assert runtime["main_search_deep_components_selected"] == [
        "bounded_destroy_repair",
        "intra_route_2opt",
    ]
    assert runtime["main_search_component_coverage_status"]["status"] == (
        "partial_problem_components_attempted"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == [
        "inter_route_relocate",
        "route_pair_swap",
        "route_pool_recombination",
    ]
    assert runtime["main_search_attempted_components"] == [
        "bounded_destroy_repair",
        "intra_route_2opt",
    ]
    assert runtime["main_search_component_attempts"]["intra_route_2opt"] > 0
    assert sum(runtime["main_search_component_accepted"].values()) == 1
    assert runtime["main_search_component_best_delta"]["bounded_destroy_repair"] == 4.0
    assert (
        runtime["main_search_component_accepted_delta_sum"]["bounded_destroy_repair"]
        == 4.0
    )
    assert (
        runtime["main_search_component_accepted_best_delta"]["bounded_destroy_repair"]
        == 4.0
    )
    assert (
        runtime["main_search_component_accepted_positive_counts"][
            "bounded_destroy_repair"
        ]
        == 1
    )
    assert (
        runtime["main_search_component_min_distance_improvement"][
            "bounded_destroy_repair"
        ]
        == 1.0
    )
    assert runtime["main_search_component_removed_counts"]["bounded_destroy_repair"] >= 2
    assert (
        runtime["main_search_component_reinserted_counts"]["bounded_destroy_repair"]
        == runtime["main_search_component_removed_counts"]["bounded_destroy_repair"]
    )
    assert set(runtime["main_search_skipped_components"]) == {
        "bounded_destroy_repair",
        "intra_route_2opt",
    }
    assert "no_improving_candidate" in json.dumps(
        runtime["main_search_component_skip_reasons"]
    )
    assert runtime["main_search_restart_enabled"] is True
    assert runtime["main_search_restart_count"] == 1
    assert "construction" in runtime["main_search_phases"]
    assert "baseline" in runtime["main_search_phases"]
    assert "improvement_loop" in runtime["main_search_phases"]
    assert runtime["main_search_objective_delta_by_phase"]["improvement_loop"] == 4.0
    assert runtime["main_search_component_phase_delta_sum"]["bounded_destroy_repair"] == 4.0
    assert runtime["main_search_component_phase_best_delta"]["bounded_destroy_repair"] == 4.0
    assert (
        runtime["main_search_component_phase_improvement_counts"][
            "bounded_destroy_repair"
        ]
        == 1
    )
    assert runtime["main_search_best_returned"] is True
    assert runtime["main_search_objective_trace"]["status"] == "returned_best"
    assert runtime["main_search_objective_trace"]["phase_delta"] == 4.0
    assert (
        runtime["main_search_objective_trace"]["phase_delta_sum_by_component"][
            "bounded_destroy_repair"
        ]
        == 4.0
    )
    assert runtime["main_search_objective_trace"]["accepted_but_zero_phase_delta"] == {}
    assert runtime["operator_attempts"] == 0
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="main_search_strategy",
        )
        is None
    )
    v5 = check_state_mutation(
        legacy_spec,
        _runner(),
        str(workspace),
        adapter=CvrpAdapter(_Spec()),  # type: ignore[arg-type]
        selected_surface="main_search_strategy",
    )
    assert v5.passed, v5.detail
    missing_field_raw = json.loads(json.dumps(raw))
    del missing_field_raw["runtime"]["main_search_baseline_param_clamps"]
    missing_issue = runtime_audit_failure_from_raw(
        missing_field_raw,
        problem_spec=legacy_spec,
        selected_surface="main_search_strategy",
    )
    assert missing_issue is not None
    assert missing_issue["error_category"] == "surface_runtime_contract_error"
    assert "main_search_baseline_param_clamps" in (
        missing_issue["missing_runtime_fields"]
    )


def test_main_search_strategy_records_clamp_details_in_selected_surface_runtime(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.75, 'params': {'destroy_ratio': (0.05, 0.50), 'segment_length': 400, 'reaction_factor': 0.05, 'vns_max_no_improve': 10000, 'max_destroy_customers': 200}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair', 'intra_route_2opt'], 'rounds': 3, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["main_search_baseline_params_clamped"] is True
    clamp_evidence = runtime["main_search_baseline_param_clamps"]
    assert clamp_evidence["applied"] is True
    assert clamp_evidence["status"] == "clamped"
    assert set(clamp_evidence["fields"]) == {
        "destroy_ratio",
        "segment_length",
        "reaction_factor",
        "vns_max_no_improve",
        "max_destroy_customers",
    }
    assert clamp_evidence["clamps"]["destroy_ratio"] == {
        "requested": [0.05, 0.5],
        "effective": [0.05, 0.35],
    }
    assert clamp_evidence["clamps"]["max_destroy_customers"] == {
        "requested": 200,
        "effective": 16,
    }
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="main_search_strategy",
        )
        is None
    )


def test_main_search_strategy_runtime_marks_both_deep_components_attempted(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.5, 'params': {}},",
                "        'improvement': {'enabled_components': ['route_pair_swap', 'bounded_destroy_repair'], 'rounds': 1, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]

    assert runtime["main_search_selected_components"] == [
        "route_pool_recombination",
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert runtime["main_search_attempted_components"] == [
        "route_pool_recombination",
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert runtime["main_search_deep_components_selected"] == [
        "route_pool_recombination",
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert runtime["main_search_component_coverage_status"]["status"] == (
        "partial_problem_components_attempted"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == [
        "inter_route_relocate",
        "intra_route_2opt",
    ]
    assert runtime["main_search_component_coverage_status"]["unattempted_deep_components"] == []
    assert runtime["main_search_component_attempts"]["route_pool_recombination"] > 0
    assert runtime["main_search_component_attempts"]["route_pair_swap"] == 0
    assert runtime["main_search_component_attempts"]["bounded_destroy_repair"] > 1
    assert runtime["main_search_component_skip_reasons"].get(
        "route_pool_recombination",
        {},
    ) in ({}, {"route_pool_no_improvement": 1})
    assert runtime["main_search_component_skip_reasons"]["route_pair_swap"] == {
        "no_candidates": 1,
    }
    assert (
        runtime["main_search_component_accepted"]["route_pool_recombination"]
        + runtime["main_search_component_accepted"]["bounded_destroy_repair"]
        >= 1
    )
    assert (
        runtime["main_search_component_accepted_delta_sum"]["route_pool_recombination"]
        + runtime["main_search_component_accepted_delta_sum"]["bounded_destroy_repair"]
        > 0.0
    )


def test_main_search_strategy_route_pair_swap_is_ranked_attempted_and_accepted(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_route_pair_swap_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['sequential'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.5, 'params': {}},",
                "        'improvement': {'enabled_components': ['route_pair_swap'], 'rounds': 1, 'top_k': 1},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/route_pair_swap_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert {frozenset(route) for route in raw["routes"]} == {
        frozenset((1, 3)),
        frozenset((2, 4)),
    }
    assert raw["objective"]["total_distance"] == 224.0
    assert runtime["main_search_selected_components"] == ["route_pair_swap"]
    assert runtime["main_search_deep_components_selected"] == ["route_pair_swap"]
    assert runtime["main_search_component_coverage_status"]["status"] == (
        "partial_problem_components_attempted"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == [
        "bounded_destroy_repair",
        "inter_route_relocate",
        "intra_route_2opt",
        "route_pool_recombination",
    ]
    assert runtime["main_search_attempted_components"] == ["route_pair_swap"]
    assert runtime["main_search_accepted_components"] == ["route_pair_swap"]
    assert runtime["main_search_component_attempts"]["route_pair_swap"] == 1
    assert runtime["main_search_component_accepted"]["route_pair_swap"] == 1
    assert runtime["main_search_component_best_delta"]["route_pair_swap"] == 198.0
    assert runtime["main_search_component_accepted_delta_sum"]["route_pair_swap"] == 198.0
    assert runtime["main_search_component_accepted_best_delta"]["route_pair_swap"] == 198.0
    assert runtime["main_search_component_accepted_positive_counts"]["route_pair_swap"] == 1
    assert runtime["main_search_component_improvement_counts"]["route_pair_swap"] == 1
    assert runtime["main_search_component_skip_reasons"]["route_pair_swap"] == {}
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="main_search_strategy",
        )
        is None
    )


def test_main_search_strategy_returns_best_even_after_worse_perturbation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    instance = adapter.load_instance(str(workspace / "data/operator_case.json"))
    best_solution = CvrpSolution(routes=((1, 2, 3, 5, 4),))
    worse_solution = CvrpSolution(routes=((1, 2, 3, 4, 5),))
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.75, 'params': {}},",
                "        'improvement': {'enabled_components': ['route_pair_swap'], 'rounds': 2, 'top_k': 8},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': True, 'strength': 1, 'max_perturbations': 1},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    main_search_strategy = cvrp_solver._load_main_search_strategy(
        workspace_root=workspace,
        instance=instance,
        time_limit_sec=2.0,
    )
    monkeypatch.setattr(
        cvrp_solver,
        "_perturb_solution",
        lambda *args, **kwargs: worse_solution,
    )

    returned, audit = cvrp_solver.improve_with_main_search_strategy(
        best_solution,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=2.0,
        start_time=time.perf_counter(),
        main_search_strategy=main_search_strategy,
    )

    returned_objective = cvrp_solver._objective_for_solution(adapter, instance, returned)
    best_objective = cvrp_solver._objective_for_solution(adapter, instance, best_solution)
    worse_objective = cvrp_solver._objective_for_solution(adapter, instance, worse_solution)
    assert returned.routes == best_solution.routes
    assert returned_objective == best_objective
    assert worse_objective["total_distance"] > best_objective["total_distance"]
    assert audit["main_search_perturbation_count"] == 1
    assert audit["main_search_best_returned"] is True


def test_main_search_strategy_can_perturb_before_first_round(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    instance = adapter.load_instance(str(workspace / "data/operator_case.json"))
    best_solution = CvrpSolution(routes=((1, 2, 3, 5, 4),))
    perturbed_solution = CvrpSolution(routes=((1, 2, 3, 4, 5),))
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "problem_adaptation": {
                "component_roles": {"route_pool_recombination": "disabled"},
            },
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pair_swap"],
                "rounds": 1,
                "top_k": 8,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": True,
                "strength": 1,
                "max_perturbations": 1,
                "schedule": "before_first_round",
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )
    seen_current: list[CvrpSolution] = []
    monkeypatch.setattr(
        cvrp_solver,
        "_perturb_solution",
        lambda *args, **kwargs: perturbed_solution,
    )

    def fake_candidate_choice(
        component: str,
        _instance: CvrpInstance,
        *,
        current_solution: CvrpSolution,
        best_solution: CvrpSolution,
        adapter: CvrpAdapter,
        current_objective: dict[str, int | float],
        best_objective: dict[str, int | float],
        top_k: int,
        min_distance_improvement: float,
        mechanism_policies: dict[str, Any] | None = None,
    ) -> tuple[None, int, dict[str, Any], dict[str, Any]]:
        del (
            component,
            _instance,
            best_solution,
            adapter,
            current_objective,
            best_objective,
            top_k,
            min_distance_improvement,
            mechanism_policies,
        )
        seen_current.append(current_solution)
        return None, 1, {}, {}

    monkeypatch.setattr(
        cvrp_solver,
        "_main_search_component_candidate_choice",
        fake_candidate_choice,
    )

    returned, runtime = cvrp_solver.improve_with_main_search_strategy(
        best_solution,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
    )

    assert returned.routes == best_solution.routes
    assert seen_current and seen_current[0].routes == perturbed_solution.routes
    assert runtime["main_search_perturbation_schedule"] == "before_first_round"
    assert runtime["main_search_perturbation_count"] == 1
    assert "pre_improvement_perturbation" in runtime["main_search_phases"]
    assert runtime["main_search_best_returned"] is True


def test_main_search_strategy_does_not_gate_bdr_after_non_phase_route_pair_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="phase_best_guard",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
            CvrpNode(3, 3, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    best_solution = CvrpSolution(routes=((1,),))
    worse_solution = CvrpSolution(routes=((2,),))
    recovered_solution = CvrpSolution(routes=((3,),))
    improved_solution = CvrpSolution(routes=((1, 2, 3),))
    objective_by_routes = {
        best_solution.routes: 10.0,
        worse_solution.routes: 20.0,
        recovered_solution.routes: 15.0,
        improved_solution.routes: 8.0,
    }
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": [
                    "route_pair_swap",
                    "bounded_destroy_repair",
                ],
                "rounds": 2,
                "top_k": 8,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": True,
                "strength": 1,
                "max_perturbations": 1,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )

    def fake_objective(
        _adapter: CvrpAdapter,
        _instance: CvrpInstance,
        solution: CvrpSolution,
    ) -> dict[str, int | float]:
        return {
            "fleet_violation": 0,
            "total_distance": objective_by_routes[solution.routes],
        }

    def fake_component_candidate(
        component: str,
        solution: CvrpSolution,
        _instance: CvrpInstance,
        *,
        adapter: CvrpAdapter,
        current_objective: dict[str, int | float],
        top_k: int,
        mechanism_policies: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
        del adapter, current_objective, top_k, mechanism_policies, kwargs
        if solution.routes == best_solution.routes:
            return None, 1, {}
        if component == "route_pair_swap" and solution.routes == worse_solution.routes:
            return recovered_solution, 1, {}
        if (
            component == "bounded_destroy_repair"
            and solution.routes == recovered_solution.routes
        ):
            return improved_solution, 1, {
                "removed_count": 2,
                "reinserted_count": 2,
                "repair_fallback_count": 0,
            }
        return None, 1, {}

    monkeypatch.setattr(cvrp_solver, "_objective_for_solution", fake_objective)
    monkeypatch.setattr(cvrp_solver, "_solution_is_valid", lambda *args: (True, ""))
    monkeypatch.setattr(
        cvrp_solver,
        "_perturb_solution",
        lambda *args, **kwargs: worse_solution,
    )
    monkeypatch.setattr(
        cvrp_solver,
        "_main_search_component_candidate",
        fake_component_candidate,
    )

    returned, runtime = cvrp_solver.improve_with_main_search_strategy(
        best_solution,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
    )

    assert returned.routes == improved_solution.routes
    assert runtime["main_search_component_accepted"]["route_pair_swap"] == 1
    assert runtime["main_search_component_accepted"]["bounded_destroy_repair"] == 1
    assert (
        runtime["main_search_component_skip_reasons"]["bounded_destroy_repair"].get(
            "route_pair_phase_improved",
            0,
        )
        == 0
    )
    assert runtime["main_search_component_phase_delta_sum"]["route_pair_swap"] == 0.0
    assert runtime["main_search_component_recovery_counts"]["route_pair_swap"] == 1
    assert runtime["main_search_component_recovery_delta_sum"]["route_pair_swap"] == 5.0
    assert runtime["main_search_component_recovery_best_delta"]["route_pair_swap"] == 5.0
    assert (
        runtime["main_search_component_phase_delta_sum"]["bounded_destroy_repair"]
        == 2.0
    )
    assert (
        runtime["main_search_component_recovery_counts"]["bounded_destroy_repair"]
        == 0
    )
    assert (
        runtime["main_search_component_phase_improvement_counts"][
            "bounded_destroy_repair"
        ]
        == 1
    )
    assert runtime["main_search_objective_delta_by_phase"]["improvement_loop"] == 2.0
    assert runtime["main_search_objective_trace"]["accepted_but_zero_phase_delta"] == {
        "route_pair_swap": 1,
    }
    assert runtime["main_search_objective_trace"]["recovery_count_by_component"][
        "route_pair_swap"
    ] == 1


def test_main_search_strategy_phase_best_probe_prefers_true_improvement_over_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="phase_probe_prefers_best",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
            CvrpNode(3, 3, 0, 1),
            CvrpNode(4, 4, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    best_solution = CvrpSolution(routes=((1,),))
    worse_solution = CvrpSolution(routes=((2,),))
    recovered_solution = CvrpSolution(routes=((3,),))
    phase_improved_solution = CvrpSolution(routes=((4,),))
    objective_by_routes = {
        best_solution.routes: 10.0,
        worse_solution.routes: 20.0,
        recovered_solution.routes: 15.0,
        phase_improved_solution.routes: 8.0,
    }
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pair_swap"],
                "rounds": 2,
                "top_k": 8,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": True,
                "strength": 1,
                "max_perturbations": 1,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )
    best_probe_calls = 0

    def fake_objective(
        _adapter: CvrpAdapter,
        _instance: CvrpInstance,
        solution: CvrpSolution,
    ) -> dict[str, int | float]:
        return {
            "fleet_violation": 0,
            "total_distance": objective_by_routes[solution.routes],
        }

    def fake_component_candidate(
        component: str,
        solution: CvrpSolution,
        _instance: CvrpInstance,
        *,
        adapter: CvrpAdapter,
        current_objective: dict[str, int | float],
        top_k: int,
        mechanism_policies: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
        nonlocal best_probe_calls
        del component, adapter, current_objective, top_k, mechanism_policies, kwargs
        if solution.routes == best_solution.routes:
            best_probe_calls += 1
            if best_probe_calls == 1:
                return None, 1, {}
            return phase_improved_solution, 1, {}
        if solution.routes == worse_solution.routes:
            return recovered_solution, 1, {}
        return None, 1, {}

    monkeypatch.setattr(cvrp_solver, "_objective_for_solution", fake_objective)
    monkeypatch.setattr(cvrp_solver, "_solution_is_valid", lambda *args: (True, ""))
    monkeypatch.setattr(
        cvrp_solver,
        "_perturb_solution",
        lambda *args, **kwargs: worse_solution,
    )
    monkeypatch.setattr(
        cvrp_solver,
        "_main_search_component_candidate",
        fake_component_candidate,
    )

    returned, runtime = cvrp_solver.improve_with_main_search_strategy(
        best_solution,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
    )

    assert returned.routes == phase_improved_solution.routes
    assert runtime["main_search_component_accepted"]["route_pair_swap"] == 1
    assert runtime["main_search_component_accepted_delta_sum"]["route_pair_swap"] == 2.0
    assert runtime["main_search_component_recovery_counts"]["route_pair_swap"] == 0
    assert runtime["main_search_component_recovery_delta_sum"]["route_pair_swap"] == 0.0
    assert runtime["main_search_component_phase_delta_sum"]["route_pair_swap"] == 2.0
    assert (
        runtime["main_search_component_phase_improvement_counts"]["route_pair_swap"]
        == 1
    )
    assert runtime["main_search_objective_delta_by_phase"]["improvement_loop"] == 2.0
    assert runtime["main_search_objective_trace"]["accepted_but_zero_phase_delta"] == {}


def test_bounded_destroy_repair_recovery_does_not_consume_phase_accept_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="bdr_recovery_limit",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
            CvrpNode(3, 3, 0, 1),
            CvrpNode(4, 4, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    best_solution = CvrpSolution(routes=((1,),))
    worse_solution = CvrpSolution(routes=((2,),))
    recovered_solution = CvrpSolution(routes=((3,),))
    phase_improved_solution = CvrpSolution(routes=((4,),))
    objective_by_routes = {
        best_solution.routes: 10.0,
        worse_solution.routes: 20.0,
        recovered_solution.routes: 15.0,
        phase_improved_solution.routes: 8.0,
    }
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["bounded_destroy_repair"],
                "rounds": 3,
                "top_k": 8,
            },
            "acceptance": {
                "min_distance_improvement": 0.0,
                "bounded_destroy_repair_accept_limit": 1,
            },
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": True,
                "strength": 1,
                "max_perturbations": 1,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )
    best_probe_calls = 0

    def fake_objective(
        _adapter: CvrpAdapter,
        _instance: CvrpInstance,
        solution: CvrpSolution,
    ) -> dict[str, int | float]:
        return {
            "fleet_violation": 0,
            "total_distance": objective_by_routes[solution.routes],
        }

    def fake_component_candidate(
        component: str,
        solution: CvrpSolution,
        _instance: CvrpInstance,
        *,
        adapter: CvrpAdapter,
        current_objective: dict[str, int | float],
        top_k: int,
        mechanism_policies: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
        nonlocal best_probe_calls
        del component, adapter, current_objective, top_k, mechanism_policies, kwargs
        if solution.routes == worse_solution.routes:
            return recovered_solution, 1, {
                "removed_count": 2,
                "reinserted_count": 2,
                "repair_fallback_count": 0,
            }
        if solution.routes == recovered_solution.routes:
            return phase_improved_solution, 1, {
                "removed_count": 2,
                "reinserted_count": 2,
                "repair_fallback_count": 0,
            }
        if solution.routes == best_solution.routes:
            best_probe_calls += 1
            if best_probe_calls >= 3:
                return phase_improved_solution, 1, {
                    "removed_count": 2,
                    "reinserted_count": 2,
                    "repair_fallback_count": 0,
                }
        return None, 1, {}

    monkeypatch.setattr(cvrp_solver, "_objective_for_solution", fake_objective)
    monkeypatch.setattr(cvrp_solver, "_solution_is_valid", lambda *args: (True, ""))
    monkeypatch.setattr(
        cvrp_solver,
        "_perturb_solution",
        lambda *args, **kwargs: worse_solution,
    )
    monkeypatch.setattr(
        cvrp_solver,
        "_main_search_component_candidate",
        fake_component_candidate,
    )

    returned, runtime = cvrp_solver.improve_with_main_search_strategy(
        best_solution,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
    )

    assert returned.routes == phase_improved_solution.routes
    assert runtime["main_search_component_accepted"]["bounded_destroy_repair"] == 2
    assert runtime["main_search_component_recovery_counts"]["bounded_destroy_repair"] == 1
    assert (
        runtime["main_search_component_phase_improvement_counts"][
            "bounded_destroy_repair"
        ]
        == 1
    )
    assert (
        runtime["main_search_component_skip_reasons"]["bounded_destroy_repair"].get(
            "bounded_destroy_repair_accept_limit_reached",
            0,
        )
        == 0
    )


def test_route_pool_recombination_combines_routes_from_solution_pool() -> None:
    instance = CvrpInstance(
        name="route_pool_recombination",
        capacity=3,
        depot=0,
        allowed_routes=3,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 0, 10, 1),
            CvrpNode(2, 0, 11, 1),
            CvrpNode(3, 100, 10, 1),
            CvrpNode(4, 100, 11, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 3), (2, 4)))
    pool_a = CvrpSolution(routes=((1, 2), (3,), (4,)))
    pool_b = CvrpSolution(routes=((3, 4), (1,), (2,)))
    current_objective = cvrp_solver._objective_for_solution(
        adapter,
        instance,
        current,
    )

    candidate, calls, telemetry = cvrp_solver._route_pool_recombination_from_solutions(
        current,
        [current, pool_a, pool_b],
        instance,
        adapter=adapter,
        current_objective=current_objective,
        top_k=32,
    )

    assert candidate is not None
    assert {frozenset(route) for route in candidate.routes} == {
        frozenset({1, 2}),
        frozenset({3, 4}),
    }
    assert calls > 0
    assert telemetry["route_pool_size"] >= 6
    assert telemetry["route_pool_recombined_routes"] == 2
    assert cvrp_solver._objective_for_solution(
        adapter,
        instance,
        candidate,
    )["total_distance"] < current_objective["total_distance"]


def test_route_pool_samples_multiple_distinct_baseline_seeds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    instance = CvrpInstance(
        name="route_pool_sample_seeds",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 2),))
    current_objective = cvrp_solver._objective_for_solution(
        adapter,
        instance,
        current,
    )
    seen_seeds: list[int] = []

    def fake_baseline_root() -> Path:
        return tmp_path

    def fake_solve_with_vrp_baseline(*args: Any, **kwargs: Any) -> tuple[CvrpSolution, dict[str, Any]]:
        del args
        seen_seeds.append(int(kwargs["seed"]))
        return current, {}

    monkeypatch.setattr(cvrp_solver, "_find_vrp_baseline_root", fake_baseline_root)
    monkeypatch.setattr(
        cvrp_solver,
        "_solve_with_vrp_baseline",
        fake_solve_with_vrp_baseline,
    )
    rng = random.Random(11)

    for _call in range(2):
        cvrp_solver._best_route_pool_recombination(
            current,
            instance,
            adapter=adapter,
            current_objective=current_objective,
            top_k=32,
            rng=rng,
            time_limit_sec=20.0,
            start_time=time.perf_counter(),
            instance_path=tmp_path / "sample.vrp",
            seed=29,
        )

    assert len(seen_seeds) == 8
    assert len(set(seen_seeds)) == len(seen_seeds)
    assert cvrp_solver._route_pool_sample_cap(32) == 4


def test_route_pool_sampling_keeps_exit_time_reserve(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    instance = CvrpInstance(
        name="route_pool_time_reserve",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 2),))
    current_objective = cvrp_solver._objective_for_solution(
        adapter,
        instance,
        current,
    )
    budgets: list[float] = []

    def fake_baseline_root() -> Path:
        return tmp_path

    def fake_solve_with_vrp_baseline(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[CvrpSolution, dict[str, Any]]:
        del args
        budgets.append(float(kwargs["time_limit_sec"]))
        return current, {}

    monkeypatch.setattr(cvrp_solver, "_find_vrp_baseline_root", fake_baseline_root)
    monkeypatch.setattr(
        cvrp_solver,
        "_solve_with_vrp_baseline",
        fake_solve_with_vrp_baseline,
    )

    cvrp_solver._best_route_pool_recombination(
        current,
        instance,
        adapter=adapter,
        current_objective=current_objective,
        top_k=32,
        rng=random.Random(11),
        time_limit_sec=20.0,
        start_time=time.perf_counter() - 16.0,
        instance_path=tmp_path / "sample.vrp",
        seed=29,
    )

    assert len(budgets) == 4
    assert max(budgets) < 0.5

    budgets.clear()
    cvrp_solver._best_route_pool_recombination(
        current,
        instance,
        adapter=adapter,
        current_objective=current_objective,
        top_k=32,
        rng=random.Random(11),
        time_limit_sec=20.0,
        start_time=time.perf_counter() - 17.4,
        instance_path=tmp_path / "sample.vrp",
        seed=29,
    )

    assert budgets == []


def test_route_pool_recombination_stops_before_exit_reserve() -> None:
    instance = CvrpInstance(
        name="route_pool_recombination_time_guard",
        capacity=3,
        depot=0,
        allowed_routes=2,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 0, 10, 1),
            CvrpNode(2, 0, 11, 1),
            CvrpNode(3, 100, 10, 1),
            CvrpNode(4, 100, 11, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 3), (2, 4)))
    current_objective = cvrp_solver._objective_for_solution(
        adapter,
        instance,
        current,
    )

    candidate, calls, telemetry = cvrp_solver._route_pool_recombination_from_solutions(
        current,
        [current],
        instance,
        adapter=adapter,
        current_objective=current_objective,
        top_k=32,
        start_time=time.perf_counter() - 9.0,
        time_limit_sec=10.0,
        exit_reserve_sec=2.0,
    )

    assert candidate is None
    assert calls == 0
    assert telemetry["skip_reason"] == "route_pool_time_limit"


def test_route_pool_can_complete_pool_route_with_incumbent_residual() -> None:
    instance = CvrpInstance(
        name="route_pool_residual_completion",
        capacity=10,
        depot=0,
        allowed_routes=3,
        use_integer_cost=False,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 100, 0, 1),
            CvrpNode(2, 101, 0, 1),
            CvrpNode(3, 100, 1, 1),
            CvrpNode(4, 101, 1, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 4), (2,), (3,)))
    partial_pool = CvrpSolution(routes=((1, 2),))
    current_objective = cvrp_solver._objective_for_solution(
        adapter,
        instance,
        current,
    )

    candidate, calls, telemetry = cvrp_solver._route_pool_recombination_from_solutions(
        current,
        [current, partial_pool],
        instance,
        adapter=adapter,
        current_objective=current_objective,
        top_k=16,
    )

    assert candidate is not None
    assert calls > 0
    assert (1, 2) in candidate.routes
    assert telemetry["route_pool_recombined_routes"] == 3
    assert cvrp_solver._objective_for_solution(
        adapter,
        instance,
        candidate,
    )["total_distance"] < current_objective["total_distance"]


def test_main_search_strategy_auto_adds_route_pool_for_old_deep_pair() -> None:
    instance = CvrpInstance(
        name="auto_route_pool",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
        ),
    )
    audit = cvrp_solver._main_search_strategy_defaults()

    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "problem_adaptation": {
                "strategy_family": "baseline_intensification",
                "instance_profile": {},
                "phase_objective": "phase_best_distance",
                "component_roles": {
                    "route_pair_swap": "primary",
                    "bounded_destroy_repair": "support",
                },
                "fallback_order": ["route_pair_swap", "bounded_destroy_repair"],
                "evidence_targets": [
                    "main_search_component_phase_delta_sum",
                    "main_search_objective_delta_by_phase",
                ],
            },
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pair_swap", "bounded_destroy_repair"],
                "rounds": 1,
                "top_k": 16,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )

    assert audit["main_search_strategy_errors"] == 0
    assert audit["main_search_components"] == [
        "route_pool_recombination",
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert audit["main_search_route_pool_auto_added"] is True
    assert audit["main_search_route_pool_activation"] == "adaptive"
    assert audit["main_search_route_pool_min_customers"] == 80
    assert audit["main_search_route_pool_max_rounds"] == 8
    assert audit["main_search_algorithm_body_source"] == "declared"
    assert (
        audit["main_search_component_roles"]["route_pool_recombination"]
        == "support"
    )


def test_main_search_strategy_algorithm_body_controls_route_pool_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    instance = CvrpInstance(
        name="algorithm_body_scope",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 2),))
    audit = cvrp_solver._main_search_strategy_defaults()

    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": {
                "phase_sequence": [
                    "construction",
                    "baseline",
                    "global_recombination",
                    "route_structure_repair",
                    "local_cleanup",
                ],
                "route_pool_activation": "adaptive",
                "route_pool_min_customers": 80,
                "route_pool_max_rounds": 8,
                "local_cleanup_after_recombination": False,
                "adaptive_component_budget": True,
            },
            "problem_adaptation": {
                "strategy_family": "baseline_intensification",
                "instance_profile": {},
                "phase_objective": "phase_best_distance",
                "component_roles": {
                    "route_pair_swap": "primary",
                    "bounded_destroy_repair": "support",
                },
                "fallback_order": ["route_pair_swap", "bounded_destroy_repair"],
                "evidence_targets": [
                    "main_search_component_phase_delta_sum",
                    "main_search_objective_delta_by_phase",
                ],
            },
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pair_swap", "bounded_destroy_repair"],
                "rounds": 1,
                "top_k": 16,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )

    def fail_route_pool(*args: Any, **kwargs: Any) -> tuple[None, int, dict[str, Any]]:
        del args, kwargs
        raise AssertionError("route_pool_recombination should be scoped out")

    monkeypatch.setattr(
        cvrp_solver,
        "_best_route_pool_recombination",
        fail_route_pool,
    )

    _, runtime = cvrp_solver.improve_with_main_search_strategy(
        current,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
        instance_path=tmp_path / "tiny.vrp",
    )

    assert runtime["main_search_route_pool_auto_added"] is True
    assert runtime["main_search_route_pool_invocations"] == 0
    assert runtime["main_search_attempted_components"][0] == "route_pool_recombination"
    assert runtime["main_search_component_skip_reasons"]["route_pool_recombination"] == {
        "algorithm_body_route_pool_scope": 1,
    }


def test_main_search_strategy_algorithm_body_allows_explicit_small_route_pool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    instance = CvrpInstance(
        name="algorithm_body_always",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 2),))
    audit = cvrp_solver._main_search_strategy_defaults()

    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": {
                "phase_sequence": ["construction", "baseline", "global_recombination"],
                "route_pool_activation": "always",
                "route_pool_min_customers": 80,
                "route_pool_max_rounds": 1,
                "local_cleanup_after_recombination": False,
                "adaptive_component_budget": True,
            },
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pool_recombination"],
                "rounds": 2,
                "top_k": 16,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )

    def no_candidate_route_pool(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[None, int, dict[str, Any]]:
        del args, kwargs
        return None, 1, {
            "route_pool_source_solutions": 1,
            "route_pool_sample_count": 1,
            "route_pool_size": 1,
            "route_pool_branch_calls": 0,
            "route_pool_recombined_routes": 0,
        }

    monkeypatch.setattr(
        cvrp_solver,
        "_best_route_pool_recombination",
        no_candidate_route_pool,
    )

    _, runtime = cvrp_solver.improve_with_main_search_strategy(
        current,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
        instance_path=tmp_path / "tiny.vrp",
    )

    assert runtime["main_search_route_pool_activation"] == "always"
    assert runtime["main_search_route_pool_invocations"] == 1
    assert runtime["main_search_component_attempts"]["route_pool_recombination"] == 1
    assert runtime["main_search_component_skip_reasons"]["route_pool_recombination"] == {
        "no_improving_candidate": 1,
    }


def test_main_search_strategy_phase_sequence_controls_component_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="phase_order",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 2),))
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": {
                "phase_sequence": [
                    "route_structure_repair",
                    "global_recombination",
                    "local_cleanup",
                ],
                "baseline_budget_policy": "declared",
                "route_pool_activation": "always",
                "route_pool_min_customers": 0,
                "route_pool_max_rounds": 1,
                "local_cleanup_after_recombination": False,
                "adaptive_component_budget": True,
            },
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.5, "params": {}},
            "improvement": {
                "enabled_components": [
                    "route_pool_recombination",
                    "route_pair_swap",
                    "intra_route_2opt",
                ],
                "rounds": 1,
                "top_k": 128,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )
    calls: list[tuple[str, int]] = []

    def no_candidate(
        component: str,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[None, int, dict[str, Any]]:
        del args
        calls.append((component, int(kwargs["top_k"])))
        return None, 1, {}

    monkeypatch.setattr(cvrp_solver, "_main_search_component_candidate", no_candidate)

    _, runtime = cvrp_solver.improve_with_main_search_strategy(
        current,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
    )

    assert [component for component, _top_k in calls] == [
        "route_pair_swap",
        "route_pool_recombination",
        "intra_route_2opt",
    ]
    assert runtime["main_search_phase_component_order"] == {
        "route_structure_repair": ["route_pair_swap"],
        "global_recombination": ["route_pool_recombination"],
        "local_cleanup": ["intra_route_2opt"],
    }
    assert runtime["main_search_component_top_k_effective"][
        "route_pool_recombination"
    ] == 24


def test_route_pool_recombination_receives_construction_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="route_pool_uses_construction_pool",
        capacity=3,
        depot=0,
        allowed_routes=2,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 0, 10, 1),
            CvrpNode(2, 0, 11, 1),
            CvrpNode(3, 100, 10, 1),
            CvrpNode(4, 100, 11, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 3), (2, 4)))
    construction_solution = CvrpSolution(routes=((1, 2), (3, 4)))
    seen: dict[str, int] = {}

    def capture_pool(
        solution: CvrpSolution,
        pool_solutions: list[CvrpSolution],
        *args: Any,
        **kwargs: Any,
    ) -> tuple[None, int, dict[str, Any]]:
        del solution, args, kwargs
        seen["pool_size"] = len(pool_solutions)
        return None, 0, {
            "route_pool_source_solutions": len(pool_solutions),
            "route_pool_size": 0,
            "route_pool_branch_calls": 0,
            "route_pool_recombined_routes": 0,
        }

    monkeypatch.setattr(
        cvrp_solver,
        "_route_pool_recombination_from_solutions",
        capture_pool,
    )

    _candidate, _calls, telemetry = cvrp_solver._best_route_pool_recombination(
        current,
        instance,
        adapter=adapter,
        current_objective={"fleet_violation": 0.0, "total_distance": 500.0},
        top_k=16,
        mechanism_policies={
            "_main_search_construction_pool_solutions": [construction_solution],
        },
    )

    assert seen["pool_size"] == 2
    assert telemetry["route_pool_source_solutions"] == 2


def test_local_cleanup_after_recombination_runs_cleanup_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="cleanup_after_recombination",
        capacity=3,
        depot=0,
        allowed_routes=2,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 0, 10, 1),
            CvrpNode(2, 0, 11, 1),
            CvrpNode(3, 100, 10, 1),
            CvrpNode(4, 100, 11, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 3), (2, 4)))
    recombined = CvrpSolution(routes=((1, 2), (3, 4)))
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": {
                "phase_sequence": ["global_recombination"],
                "baseline_budget_policy": "declared",
                "route_pool_activation": "always",
                "route_pool_min_customers": 0,
                "route_pool_max_rounds": 1,
                "local_cleanup_after_recombination": True,
                "adaptive_component_budget": False,
            },
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.5, "params": {}},
            "improvement": {
                "enabled_components": [
                    "route_pool_recombination",
                    "intra_route_2opt",
                ],
                "rounds": 1,
                "top_k": 16,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )
    calls: list[str] = []

    def fake_choice(
        component: str,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[CvrpSolution | None, int, dict[str, Any], dict[str, Any]]:
        del args, kwargs
        calls.append(component)
        if component == "route_pool_recombination":
            return recombined, 1, {}, {
                "objective": {"fleet_violation": 0.0, "total_distance": 202.0},
                "accepted_delta": 198.0,
                "phase_delta": 198.0,
            }
        return None, 1, {}, {}

    monkeypatch.setattr(
        cvrp_solver,
        "_main_search_component_candidate_choice",
        fake_choice,
    )

    returned, runtime = cvrp_solver.improve_with_main_search_strategy(
        current,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
    )

    assert returned.routes == recombined.routes
    assert calls == ["route_pool_recombination", "intra_route_2opt"]
    assert runtime["main_search_phase_component_order"] == {
        "global_recombination": ["route_pool_recombination"],
    }
    assert runtime["main_search_component_skip_reasons"]["intra_route_2opt"] == {
        "no_improving_candidate": 1,
    }


def test_main_search_strategy_respects_explicit_route_pool_disabled_role() -> None:
    instance = CvrpInstance(
        name="disabled_route_pool",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
        ),
    )
    audit = cvrp_solver._main_search_strategy_defaults()

    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "problem_adaptation": {
                "strategy_family": "baseline_intensification",
                "instance_profile": {},
                "phase_objective": "phase_best_distance",
                "component_roles": {
                    "route_pair_swap": "primary",
                    "bounded_destroy_repair": "support",
                    "route_pool_recombination": "disabled",
                },
                "fallback_order": ["route_pair_swap", "bounded_destroy_repair"],
                "evidence_targets": [
                    "main_search_component_phase_delta_sum",
                    "main_search_objective_delta_by_phase",
                ],
            },
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pair_swap", "bounded_destroy_repair"],
                "rounds": 1,
                "top_k": 16,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )

    assert audit["main_search_strategy_errors"] == 0
    assert audit["main_search_components"] == [
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert audit["main_search_component_roles"]["route_pool_recombination"] == "disabled"


def test_main_search_strategy_route_pool_recombination_records_phase_improvement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="route_pool_main_search",
        capacity=3,
        depot=0,
        allowed_routes=2,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 0, 10, 1),
            CvrpNode(2, 0, 11, 1),
            CvrpNode(3, 100, 10, 1),
            CvrpNode(4, 100, 11, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 3), (2, 4)))
    recombined = CvrpSolution(routes=((1, 2), (3, 4)))
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pool_recombination"],
                "rounds": 1,
                "top_k": 32,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )

    def fake_route_pool_recombination(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[CvrpSolution, int, dict[str, Any]]:
        del args, kwargs
        return recombined, 5, {
            "route_pool_source_solutions": 3,
            "route_pool_sample_count": 2,
            "route_pool_size": 8,
            "route_pool_branch_calls": 4,
            "route_pool_recombined_routes": 2,
        }

    monkeypatch.setattr(
        cvrp_solver,
        "_best_route_pool_recombination",
        fake_route_pool_recombination,
    )

    returned, runtime = cvrp_solver.improve_with_main_search_strategy(
        current,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
    )

    assert returned.routes == recombined.routes
    assert runtime["main_search_component_accepted"]["route_pool_recombination"] == 1
    assert (
        runtime["main_search_component_phase_improvement_counts"][
            "route_pool_recombination"
        ]
        == 1
    )
    assert runtime["main_search_route_pool_source_solutions"] == 3
    assert runtime["main_search_route_pool_sample_count"] == 2
    assert runtime["main_search_route_pool_size"] == 8
    assert runtime["main_search_route_pool_branch_calls"] == 4
    assert runtime["main_search_route_pool_recombined_routes"] == 2


def test_acceptance_restart_policy_can_reject_recovery_only_moves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="reject_recovery_only",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
            CvrpNode(3, 3, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    best_solution = CvrpSolution(routes=((1,),))
    worse_solution = CvrpSolution(routes=((2,),))
    recovered_solution = CvrpSolution(routes=((3,),))
    objective_by_routes = {
        best_solution.routes: 10.0,
        worse_solution.routes: 20.0,
        recovered_solution.routes: 15.0,
    }
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pair_swap"],
                "rounds": 1,
                "top_k": 8,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": True,
                "strength": 1,
                "max_perturbations": 1,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )
    acceptance_policy = cvrp_solver._acceptance_restart_policy_defaults()
    cvrp_solver._normalize_acceptance_restart_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "min_distance_improvement": 0.0,
            "recovery_only_policy": "reject_recovery_only",
            "restart": {"enabled": False, "stagnation_rounds": 0, "max_restarts": 0},
            "perturbation": {
                "enabled": True,
                "schedule": "before_first_round",
                "strength": 1,
                "max_perturbations": 1,
            },
        },
        audit=acceptance_policy,
    )

    def fake_objective(
        _adapter: CvrpAdapter,
        _instance: CvrpInstance,
        solution: CvrpSolution,
    ) -> dict[str, int | float]:
        return {
            "fleet_violation": 0,
            "total_distance": objective_by_routes[solution.routes],
        }

    def fake_component_candidate(
        component: str,
        solution: CvrpSolution,
        _instance: CvrpInstance,
        *,
        adapter: CvrpAdapter,
        current_objective: dict[str, int | float],
        top_k: int,
        mechanism_policies: dict[str, Any] | None = None,
    ) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
        del component, adapter, current_objective, top_k, mechanism_policies
        if solution.routes == worse_solution.routes:
            return recovered_solution, 1, {}
        return None, 1, {}

    monkeypatch.setattr(cvrp_solver, "_objective_for_solution", fake_objective)
    monkeypatch.setattr(cvrp_solver, "_solution_is_valid", lambda *args: (True, ""))
    monkeypatch.setattr(
        cvrp_solver,
        "_perturb_solution",
        lambda *args, **kwargs: worse_solution,
    )
    monkeypatch.setattr(
        cvrp_solver,
        "_main_search_component_candidate",
        fake_component_candidate,
    )

    returned, runtime = cvrp_solver.improve_with_main_search_strategy(
        best_solution,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
        acceptance_restart_policy=acceptance_policy,
    )

    assert returned.routes == best_solution.routes
    assert runtime["acceptance_restart_active"] is True
    assert runtime["recovery_only_policy"] == "reject_recovery_only"
    assert runtime["accepted_recovery_only_count"] == 0
    assert runtime["main_search_component_recovery_counts"]["route_pair_swap"] == 0
    assert runtime["main_search_component_skip_reasons"]["route_pair_swap"] == {
        "recovery_only_rejected": 1,
    }


def test_main_search_strategy_gates_destroy_repair_after_route_pair_improvement(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_route_pair_swap_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'problem_adaptation': {'component_roles': {'route_pool_recombination': 'disabled'}},",
                "        'construction': {'methods': ['sequential'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.75, 'params': {}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair', 'route_pair_swap'], 'rounds': 1, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/route_pair_swap_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]

    assert runtime["main_search_components"] == [
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert runtime["main_search_accepted_components"] == ["route_pair_swap"]
    assert runtime["main_search_component_attempts"]["bounded_destroy_repair"] == 0
    assert runtime["main_search_component_skip_reasons"]["bounded_destroy_repair"] == {
        "route_pair_phase_improved": 1,
    }


def test_main_search_strategy_bounded_destroy_repair_removes_subset_and_is_audited(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.5, 'params': {}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair'], 'rounds': 1, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert raw["objective"]["total_distance"] == 12.0
    assert runtime["main_search_selected_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_deep_components_selected"] == ["bounded_destroy_repair"]
    assert runtime["main_search_component_coverage_status"]["status"] == (
        "partial_problem_components_attempted"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == [
        "inter_route_relocate",
        "intra_route_2opt",
        "route_pair_swap",
        "route_pool_recombination",
    ]
    assert runtime["main_search_attempted_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_accepted_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_component_attempts"]["bounded_destroy_repair"] > 1
    assert runtime["main_search_component_accepted"]["bounded_destroy_repair"] == 1
    assert runtime["main_search_component_best_delta"]["bounded_destroy_repair"] == 4.0
    assert (
        runtime["main_search_component_accepted_delta_sum"]["bounded_destroy_repair"]
        == 4.0
    )
    assert (
        runtime["main_search_component_accepted_best_delta"]["bounded_destroy_repair"]
        == 4.0
    )
    assert (
        runtime["main_search_component_accepted_positive_counts"][
            "bounded_destroy_repair"
        ]
        == 1
    )
    assert runtime["main_search_component_improvement_counts"]["bounded_destroy_repair"] == 1
    assert runtime["main_search_component_removed_counts"]["bounded_destroy_repair"] >= 2
    assert (
        runtime["main_search_component_reinserted_counts"]["bounded_destroy_repair"]
        == runtime["main_search_component_removed_counts"]["bounded_destroy_repair"]
    )
    assert runtime["main_search_component_skip_reasons"]["bounded_destroy_repair"] == {}
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="main_search_strategy",
        )
        is None
    )


def test_route_pair_candidate_policy_changes_main_search_candidate_telemetry(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_route_pair_swap_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['sequential'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.5, 'params': {}},",
                "        'improvement': {'enabled_components': ['route_pair_swap'], 'rounds': 1, 'top_k': 1},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "route_pair_candidate_policy.py").write_text(
        "\n".join(
            [
                "def route_pair_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'scoring_terms': ['route_distance', 'removal_saving', 'distance_saving'],",
                "        'move_families': ['customer_swap'],",
                "        'candidate_limits': {'pair_cap': 1, 'position_cap': 2},",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/route_pair_swap_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["route_pair_surface_loaded"] is True
    assert runtime["route_pair_active"] is True
    assert runtime["route_pair_errors"] == 0
    assert runtime["route_pair_candidate_limits"] == {"pair_cap": 1, "position_cap": 2}
    assert runtime["route_pair_candidates_generated"] > 0
    assert runtime["route_pair_attempts"] == 1
    assert runtime["route_pair_accepted_phase_best"] == 1
    assert runtime["route_pair_phase_delta_sum"] == 198.0
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="route_pair_candidate_policy",
        )
        is None
    )


def test_route_pair_policy_can_activate_default_mechanism_main_search(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_route_pair_swap_case(workspace)
    (workspace / "policies" / "route_pair_candidate_policy.py").write_text(
        "\n".join(
            [
                "def route_pair_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'scoring_terms': ['route_distance', 'removal_saving', 'distance_saving'],",
                "        'move_families': ['customer_swap'],",
                "        'candidate_limits': {'pair_cap': 1, 'position_cap': 2},",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/route_pair_swap_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["main_search_strategy_active"] is True
    assert runtime["main_search_components"] == ["route_pair_swap"]
    assert runtime["route_pair_active"] is True
    assert runtime["route_pair_candidates_generated"] > 0
    assert runtime["route_pair_attempts"] > 0
    assert "default mechanism-surface main search activated" in json.dumps(
        runtime["main_search_strategy_events"]
    )
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="route_pair_candidate_policy",
        )
        is None
    )


def test_destroy_repair_policy_changes_main_search_repair_telemetry(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.5, 'params': {}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair'], 'rounds': 1, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "destroy_repair_policy.py").write_text(
        "\n".join(
            [
                "def destroy_repair_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'destroy_selectors': ['worst_removal'],",
                "        'repair_selectors': ['regret_2'],",
                "        'subset_strategy': 'single_worst',",
                "        'max_destroy_customers': 2,",
                "        'repair_budget_per_customer': 8,",
                "        'fallback_to_smaller_subsets': False,",
                "        'phase_best_preference': True,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["destroy_repair_surface_loaded"] is True
    assert runtime["destroy_repair_active"] is True
    assert runtime["destroy_repair_errors"] == 0
    assert runtime["destroy_subset_strategy"] == "single_worst"
    assert runtime["destroy_max_customers"] == 2
    assert runtime["destroy_subset_count"] >= 1
    assert runtime["destroy_repair_attempts"] > 0
    assert runtime["destroy_repair_accepted_phase_best"] == 1
    assert runtime["destroy_repair_phase_delta_sum"] == 4.0
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="destroy_repair_policy",
        )
        is None
    )


def test_destroy_repair_policy_selectors_drive_ranking_and_repair_budget() -> None:
    instance = CvrpInstance(
        name="destroy_repair_selector_semantics",
        capacity=99,
        depot=0,
        allowed_routes=2,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 100, 0, 1),
            CvrpNode(2, 0, 100, 1),
            CvrpNode(3, 100, 100, 1),
            CvrpNode(4, 1, 0, 1),
            CvrpNode(5, 2, 0, 1),
            CvrpNode(6, 3, 0, 1),
            CvrpNode(7, 10, 0, 1),
            CvrpNode(8, 20, 0, 1),
            CvrpNode(9, 30, 0, 1),
        ),
    )
    routes = [[1, 2, 3], [4, 5, 6]]
    worst_policy = {
        "destroy_repair_active": True,
        "destroy_selectors": ["worst_removal"],
    }
    diverse_policy = {
        "destroy_repair_active": True,
        "destroy_selectors": ["route_diverse_worst"],
    }

    worst_ranked = cvrp_solver._rank_destroy_repair_customers(
        routes,
        instance,
        destroy_repair_policy=worst_policy,
    )
    diverse_ranked = cvrp_solver._rank_destroy_repair_customers(
        routes,
        instance,
        destroy_repair_policy=diverse_policy,
    )

    assert [item[1] for item in worst_ranked[:2]] == [0, 0]
    assert [item[1] for item in diverse_ranked[:2]] == [0, 1]

    removed = [7, 8, 9]
    repair_base_routes = [[1, 2, 3], [4, 5, 6]]
    regret_policy = {
        "destroy_repair_active": True,
        "repair_selectors": ["regret_2"],
        "repair_budget_per_customer": 2,
    }
    cheapest_policy = {
        "destroy_repair_active": True,
        "repair_selectors": ["cheapest"],
        "repair_budget_per_customer": 2,
    }
    _routes, _attempts, regret_reinserted, regret_reason = (
        cvrp_solver._repair_destroyed_customers_with_policy(
            repair_base_routes,
            removed,
            instance,
            top_k=4,
            destroy_repair_policy=regret_policy,
        )
    )
    _routes, _attempts, cheapest_reinserted, cheapest_reason = (
        cvrp_solver._repair_destroyed_customers_with_policy(
            repair_base_routes,
            removed,
            instance,
            top_k=4,
            destroy_repair_policy=cheapest_policy,
        )
    )

    assert regret_reason == "repair_budget_exhausted"
    assert cheapest_reason == "repair_budget_exhausted"
    assert cheapest_reinserted > regret_reinserted


def test_bounded_regret_insertions_rank_globally_across_routes() -> None:
    instance = CvrpInstance(
        name="global_repair_insertion",
        capacity=99,
        depot=0,
        allowed_routes=2,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 100, 0, 1),
            CvrpNode(2, 0, 100, 1),
            CvrpNode(3, 0, 101, 1),
        ),
    )

    insertions = cvrp_solver._bounded_regret_insertions(
        [[1], [2]],
        3,
        instance,
        remaining_budget=1,
    )

    assert len(insertions) == 1
    assert insertions[0].route_index == 1
    assert insertions[0].delta == 2.0


def test_bounded_destroy_repair_preserves_budget_for_fallback_subsets() -> None:
    policy = {
        "destroy_repair_active": True,
        "repair_fallback_enabled": True,
        "repair_budget_per_customer": 4,
    }
    disabled_policy = {
        "destroy_repair_active": True,
        "repair_fallback_enabled": False,
        "repair_budget_per_customer": 4,
    }

    reserved_budget = cvrp_solver._bounded_destroy_repair_subset_budget(
        64,
        selected_count=6,
        remaining_subsets=5,
        destroy_repair_policy=policy,
    )
    unreserved_budget = cvrp_solver._bounded_destroy_repair_subset_budget(
        64,
        selected_count=6,
        remaining_subsets=5,
        destroy_repair_policy=disabled_policy,
    )

    assert 6 <= reserved_budget < 64
    assert unreserved_budget == 64


def test_bounded_destroy_repair_fallback_flag_controls_smaller_subsets() -> None:
    removable = [(float(10 - i), 0, i, i + 1) for i in range(6)]

    enabled = cvrp_solver._bounded_destroy_repair_subsets(
        removable,
        6,
        destroy_repair_policy={
            "destroy_repair_active": True,
            "repair_fallback_enabled": True,
            "destroy_subset_strategy": "single_worst",
        },
    )
    disabled = cvrp_solver._bounded_destroy_repair_subsets(
        removable,
        6,
        destroy_repair_policy={
            "destroy_repair_active": True,
            "repair_fallback_enabled": False,
            "destroy_subset_strategy": "single_worst",
        },
    )

    assert [len(subset) for subset in enabled] == [6, 4, 3, 2, 1]
    assert [len(subset) for subset in disabled] == [6]


def test_main_search_strategy_bounded_destroy_repair_accepts_formal_like_budget() -> None:
    instance = CvrpInstance(
        name="bounded_destroy_repair_formal_like",
        capacity=3,
        depot=0,
        allowed_routes=2,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 0, 10, 1),
            CvrpNode(2, 0, 11, 1),
            CvrpNode(3, 0, 12, 1),
            CvrpNode(4, 100, 10, 1),
            CvrpNode(5, 100, 11, 1),
            CvrpNode(6, 100, 12, 1),
        ),
    )
    solution = CvrpSolution(routes=((1, 4, 2), (5, 3, 6)))
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "construction": {
                "methods": ["sequential"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.5, "params": {}},
            "improvement": {
                "enabled_components": ["bounded_destroy_repair"],
                "rounds": 5,
                "top_k": 64,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )

    improved, runtime = cvrp_solver.improve_with_main_search_strategy(
        solution,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.time(),
        main_search_strategy=audit,
    )

    assert improved != solution
    assert runtime["main_search_selected_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_attempted_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_accepted_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_component_attempts"]["bounded_destroy_repair"] >= 64
    assert runtime["main_search_component_accepted"]["bounded_destroy_repair"] == 1
    assert runtime["main_search_bounded_destroy_repair_accept_limit"] == 1
    assert runtime["main_search_component_best_delta"]["bounded_destroy_repair"] > 0.0
    assert runtime["main_search_component_removed_counts"]["bounded_destroy_repair"] >= 2
    assert (
        runtime["main_search_component_reinserted_counts"]["bounded_destroy_repair"]
        == runtime["main_search_component_removed_counts"]["bounded_destroy_repair"]
    )
    assert (
        runtime["main_search_component_skip_reasons"]["bounded_destroy_repair"].get(
            "bounded_destroy_repair_accept_limit_reached",
            0,
        )
        > 0
    )


def test_invalid_main_search_strategy_output_is_selected_surface_runtime_failure(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.8, 'params': {}},",
                "        'improvement': {'enabled_components': ['unknown_move'], 'rounds': 1, 'top_k': 8},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="main_search_strategy",
    )

    assert raw["runtime"]["main_search_strategy_errors"] >= 1
    assert raw["runtime"]["main_search_strategy_active"] is False
    assert raw["runtime"]["main_search_stop_reason"] == "invalid_plan"
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"
    assert "main_search_strategy_errors" in issue["detail"]
    assert "main_search_strategy_errors" in issue["failed_runtime_fields"]
    assert "unknown_move" in json.dumps(raw["runtime"]["main_search_strategy_events"])


def test_policy_surfaces_accept_safe_cvrp_instance_api_without_runtime_errors(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "search_policy.py").write_text(
        "\n".join(
            [
                "def baseline_time_fraction(instance, time_limit_sec):",
                "    return 0.5 if instance.customer_count == len(instance.customer_ids) else 0.6",
                "",
                "def max_operator_rounds(instance, time_limit_sec):",
                "    return min(3, max(1, instance.customer_count))",
                "",
                "def enable_post_baseline_operators(instance, time_limit_sec):",
                "    return len(instance.customer_ids) > 0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "construction_policy.py").write_text(
        "\n".join(
            [
                "def construction_mode(instance, time_limit_sec):",
                "    total_demand = sum(instance.demands[c] for c in instance.customer_ids)",
                "    return 'nearest_neighbor_demand_bias' if total_demand <= instance.capacity else 'nearest_neighbor'",
                "",
                "def construction_bias(instance, time_limit_sec):",
                "    farthest = max((instance.distance(instance.depot, c) for c in instance.customer_ids), default=0.0)",
                "    return 0.2 if farthest >= 0.0 else 0.0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "neighborhood_portfolio.py").write_text(
        "\n".join(
            [
                "def enabled_components(instance, time_limit_sec):",
                "    return ['route_local', 'route_pair'] if instance.customer_count == len(instance.customer_ids) else ['registry_operator']",
                "",
                "def component_weights(instance, time_limit_sec):",
                "    avg_demand = sum(instance.demands[c] for c in instance.customer_ids) / max(1, instance.customer_count)",
                "    demand_ratio = avg_demand / max(1, instance.capacity)",
                "    return {'route_local': 1.0, 'route_pair': min(5.0, 1.0 + demand_ratio)}",
                "",
                "def candidate_limits(instance, time_limit_sec):",
                "    count = instance.customer_count",
                "    return {",
                "        'max_rounds': min(3, count),",
                "        'top_k': min(4, count),",
                "        'total_attempts': min(200, count * 4),",
                "        'per_component_attempts': min(80, max(1, count * 2)),",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["policy_errors"] == 0
    assert runtime["baseline_time_fraction"] == 0.5
    assert runtime["operator_round_limit"] == 3
    assert runtime["post_baseline_operators_enabled"] is True
    assert runtime["construction_errors"] == 0
    assert runtime["construction_mode"] == "nearest_neighbor_demand_bias"
    assert runtime["construction_bias"] == 0.2
    assert runtime["portfolio_errors"] == 0
    assert runtime["enabled_components"] == ["route_local", "route_pair"]
    assert runtime["candidate_limits"]["top_k"] == 4
    for surface_name in (
        "search_policy",
        "construction_policy",
        "neighborhood_portfolio",
    ):
        assert (
            runtime_audit_failure_from_raw(
                raw,
                problem_spec=legacy_spec,
                selected_surface=surface_name,
            )
            is None
        )


def test_search_policy_using_instance_customers_fails_runtime_audit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "search_policy.py").write_text(
        "\n".join(
            [
                "def baseline_time_fraction(instance, time_limit_sec):",
                "    return 0.7 if instance.customers else 0.8",
                "",
                "def max_operator_rounds(instance, time_limit_sec):",
                "    return 1",
                "",
                "def enable_post_baseline_operators(instance, time_limit_sec):",
                "    return True",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="search_policy",
    )

    assert raw["runtime"]["policy_errors"] == 1
    assert issue is not None
    assert issue["error_category"] == "policy_runtime_error"
    assert "customers" in json.dumps(raw["runtime"]["policy_events"])


def test_modified_construction_policy_changes_mode_without_solver_edit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    solver_before = (workspace / "solver.py").read_text(encoding="utf-8")
    (workspace / "policies" / "construction_policy.py").write_text(
        "\n".join(
            [
                "def construction_mode(instance, time_limit_sec):",
                "    return 'demand_descending'",
                "",
                "def construction_bias(instance, time_limit_sec):",
                "    return 0.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert (workspace / "solver.py").read_text(encoding="utf-8") == solver_before
    assert raw["runtime"]["construction_surface_loaded"] is True
    assert raw["runtime"]["construction_errors"] == 0
    assert raw["runtime"]["construction_mode"] == "demand_descending"
    assert runtime_audit_failure_from_raw(raw) is None


def test_invalid_construction_policy_output_is_runtime_audit_failure(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "construction_policy.py").write_text(
        "\n".join(
            [
                "def construction_mode(instance, time_limit_sec):",
                "    return 'benchmark_answer_mode'",
                "",
                "def construction_bias(instance, time_limit_sec):",
                "    return 0.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["runtime"]["construction_errors"] == 1
    assert raw["runtime"]["construction_mode"] == "nearest_neighbor"
    issue = runtime_audit_failure_from_raw(raw)
    assert issue is not None
    assert issue["error_category"] == "construction_runtime_error"
    assert "construction_errors=1" in issue["detail"]
    assert "benchmark_answer_mode" in issue["construction_events"][0]["detail"]


def test_modified_neighborhood_portfolio_changes_component_schedule_without_solver_edit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    solver_before = (workspace / "solver.py").read_text(encoding="utf-8")
    (workspace / "operators" / "route_local_noop.py").write_text(
        "\n".join(
            [
                "class RouteLocalNoop:",
                "    category = 'route_local'",
                "    def execute(self, solution, instance, rng):",
                "        return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "operators" / "route_pair_better.py").write_text(
        "\n".join(
            [
                "from scion.problems.cvrp.models import CvrpSolution",
                "",
                "class RoutePairBetter:",
                "    category = 'route_pair'",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2, 3, 5, 4),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: route_pair_better",
                "    file_path: operators/route_pair_better.py",
                "    category: route_pair",
                "    class_name: RoutePairBetter",
                "    weight: 2.0",
                "  - name: route_local_noop",
                "    file_path: operators/route_local_noop.py",
                "    category: route_local",
                "    class_name: RouteLocalNoop",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "neighborhood_portfolio.py").write_text(
        "\n".join(
            [
                "def enabled_components(instance, time_limit_sec):",
                "    return ['route_local']",
                "",
                "def component_weights(instance, time_limit_sec):",
                "    return {'route_local': 1.0}",
                "",
                "def candidate_limits(instance, time_limit_sec):",
                "    return {'max_rounds': 20, 'top_k': 1}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]

    assert (workspace / "solver.py").read_text(encoding="utf-8") == solver_before
    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert runtime["portfolio_surface_loaded"] is True
    assert runtime["portfolio_errors"] == 0
    assert runtime["enabled_components"] == ["route_local"]
    assert runtime["operator_loaded"] == 1
    assert runtime["operator_attempts"] == 1
    assert runtime["component_attempts"]["route_local"] == 1
    assert runtime["component_attempts"].get("route_pair", 0) == 0
    assert runtime["portfolio_stop_reason"] == "no_improvement_round"
    assert runtime_audit_failure_from_raw(raw) is None


def test_invalid_neighborhood_portfolio_output_is_runtime_audit_failure(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "neighborhood_portfolio.py").write_text(
        "\n".join(
            [
                "def enabled_components(instance, time_limit_sec):",
                "    return ['unknown_component']",
                "",
                "def component_weights(instance, time_limit_sec):",
                "    return {'route_local': -1.0}",
                "",
                "def candidate_limits(instance, time_limit_sec):",
                "    return {'top_k': -1}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["runtime"]["portfolio_surface_loaded"] is True
    assert raw["runtime"]["portfolio_errors"] >= 3
    issue = runtime_audit_failure_from_raw(raw)
    assert issue is not None
    assert issue["error_category"] == "portfolio_runtime_error"
    assert "portfolio_errors=" in issue["detail"]
    assert "unknown_component" in issue["portfolio_events"][0]["detail"]


def test_invalid_operator_outputs_do_not_pollute_solution(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "bad_type.py").write_text(
        "\n".join(
            [
                "class BadType:",
                "    def execute(self, solution, instance, rng):",
                "        return []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "operators" / "missing_customers.py").write_text(
        "\n".join(
            [
                "from scion.problems.cvrp.models import CvrpSolution",
                "",
                "class MissingCustomers:",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: bad_type",
                "    file_path: operators/bad_type.py",
                "    class_name: BadType",
                "    weight: 2.0",
                "  - name: missing_customers",
                "    file_path: operators/missing_customers.py",
                "    class_name: MissingCustomers",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert raw["objective"]["total_distance"] == 16.0
    assert raw["runtime"]["operator_loaded"] == 2
    assert raw["runtime"]["operator_accepted"] == 0
    assert raw["runtime"]["operator_skipped"] >= 2
    assert raw["runtime"]["operator_errors"] >= 2
    assert raw["runtime"]["operator_invalid_outputs"] >= 2
    assert {
        (event["operator"], event["status"])
        for event in raw["runtime"]["operator_events"]
    } >= {
        ("bad_type", "error"),
        ("missing_customers", "error"),
    }
    issue = runtime_audit_failure_from_raw(raw)
    assert issue is not None
    assert issue["error_category"] == "operator_runtime_error"

    adapter, instance, artifact = _artifact(raw, workspace, "data/operator_case.json")
    assert adapter.check_solution_consistency(artifact, instance).passed is True
    assert adapter.check_feasibility(artifact, instance).passed is True


def test_operator_exception_is_reported_in_run_result_runtime_audit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "bad_attribute.py").write_text(
        "\n".join(
            [
                "class BadAttribute:",
                "    def execute(self, solution, instance, rng):",
                "        _ = instance.vehicle_capacity",
                "        return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: bad_attribute",
                "    file_path: operators/bad_attribute.py",
                "    class_name: BadAttribute",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = _runner().run_solver(
        workdir=str(workspace),
        instance_path="data/operator_case.json",
        seed=14,
        time_limit_sec=2,
        registry_path=str(workspace / "registry.yaml"),
    )

    assert result.success is True
    assert result.output is not None
    assert result.output.runtime["operator_errors"] == 1
    issue = runtime_audit_failure_from_result(result)
    assert issue is not None
    assert issue["error_category"] == "operator_runtime_error"
    assert "vehicle_capacity" in issue["operator_events"][0]["detail"]


def test_registry_path_escape_entry_is_not_loaded(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    escaped = tmp_path / "escaped_operator.py"
    escaped.write_text(
        "\n".join(
            [
                "from scion.problems.cvrp.models import CvrpSolution",
                "",
                "class EscapedOperator:",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2, 3, 5, 4),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: escaped_operator",
                "    file_path: ../escaped_operator.py",
                "    class_name: EscapedOperator",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert raw["objective"]["total_distance"] == 16.0
    assert raw["runtime"]["operator_loaded"] == 0
    assert raw["runtime"]["operator_skipped"] == 1
    assert raw["runtime"]["operator_events"] == [
        {
            "operator": "escaped_operator",
            "status": "skipped",
            "detail": "operator path escapes workspace",
        }
    ]
