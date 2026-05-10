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


def test_active_main_search_formal_baseline_fraction_guard_clamps_budget(
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
    assert captured["time_limit"] == 1.5
    assert audit["main_search_baseline_time_fraction_effective"] == 0.75
    assert audit["main_search_baseline_quality_guard_applied"] is True


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
    assert "main_search_selected_components" in required_fields
    assert "main_search_attempted_components" in required_fields
    assert "main_search_component_coverage_status" in required_fields
    assert "main_search_deep_components_selected" in required_fields
    assert "main_search_component_attempts" in required_fields
    assert "main_search_component_skip_reasons" in required_fields
    assert "main_search_component_repair_fallback_counts" in required_fields
    assert "main_search_baseline_time_fraction_effective" in required_fields
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
    assert "main_search_perturbation_schedule" in required_fields
    assert set(required_fields).issubset(runtime)
    assert runtime["main_search_strategy_loaded"] is True
    assert runtime["main_search_strategy_active"] is False
    assert runtime["main_search_plan"]["enabled"] is False
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
    ]
    assert runtime["main_search_component_coverage_status"]["status"] == (
        "missing_forced_diagnostic_deep_components"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == [
        "route_pair_swap",
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
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert runtime["main_search_attempted_components"] == [
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert runtime["main_search_deep_components_selected"] == [
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert runtime["main_search_component_coverage_status"]["status"] == (
        "deep_components_attempted"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == []
    assert runtime["main_search_component_coverage_status"]["unattempted_deep_components"] == []
    assert runtime["main_search_component_attempts"]["route_pair_swap"] == 0
    assert runtime["main_search_component_attempts"]["bounded_destroy_repair"] > 1
    assert runtime["main_search_component_skip_reasons"]["route_pair_swap"] == {
        "no_candidates": 1,
    }
    assert runtime["main_search_component_accepted"]["bounded_destroy_repair"] == 1
    assert (
        runtime["main_search_component_accepted_delta_sum"]["bounded_destroy_repair"]
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
        "missing_forced_diagnostic_deep_components"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == [
        "bounded_destroy_repair",
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
    ) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
        del adapter, current_objective, top_k
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
    ) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
        nonlocal best_probe_calls
        del component, adapter, current_objective, top_k
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
        "missing_forced_diagnostic_deep_components"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == [
        "route_pair_swap",
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
