"""CVRP solver smoke tests for adapter-loaded JSON and CVRPLIB inputs."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from scion.problems.cvrp.adapter import CvrpAdapter
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner


CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"
TINY_5 = CVRP_DIR / "data" / "tiny_5.json"


class _Spec:
    pass


def _adapter() -> CvrpAdapter:
    return CvrpAdapter(_Spec())  # type: ignore[arg-type]


def _runner() -> LocalSubprocessRunner:
    return LocalSubprocessRunner(ResourceLimits(timeout_sec=10, memory_mb=1024))


def _write_synthetic_vrp(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic_solver_smoke.vrp"
    path.write_text(
        "\n".join(
            [
                "NAME : synthetic_solver_smoke",
                "TYPE : CVRP",
                "COMMENT : solver wrapper fixture only",
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
        "\n".join(
            [
                "Route #1: 2 3 4",
                "Cost : 40",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _run_solver(instance_path: str) -> dict[str, Any]:
    result = _runner().run_solver(
        workdir=str(CVRP_DIR),
        instance_path=instance_path,
        seed=11,
        time_limit_sec=1,
        registry_path="",
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


def _run_solver_with_env(instance_path: str, *, data_root: Path) -> dict[str, Any]:
    previous = os.environ.get("SCION_PROBLEM_DATA_ROOT")
    os.environ["SCION_PROBLEM_DATA_ROOT"] = str(data_root)
    try:
        return _run_solver(instance_path)
    finally:
        if previous is None:
            os.environ.pop("SCION_PROBLEM_DATA_ROOT", None)
        else:
            os.environ["SCION_PROBLEM_DATA_ROOT"] = previous


def test_local_subprocess_runner_solves_synthetic_vrp(tmp_path: Path) -> None:
    vrp_path = _write_synthetic_vrp(tmp_path)
    assert vrp_path.parent == tmp_path

    raw = _run_solver(str(vrp_path))

    assert raw["feasible"] is True
    assert isinstance(raw["routes"], list)
    assert set(raw["objective"]) == {"fleet_violation", "total_distance", "routes"}
    assert raw["objective"] == {
        "fleet_violation": 0,
        "total_distance": 40.0,
        "routes": 1,
    }
    assert raw["runtime"]["time_limit_s"] == 1
    assert raw["runtime"]["elapsed_s"] >= 0
    assert raw["runtime"]["solver_algorithm_path"] == "policies/baseline_algorithm.py"
    assert raw["runtime"]["solver_algorithm_loaded"] is True
    assert raw["runtime"]["solver_algorithm_active"] is True
    assert raw["runtime"]["solver_algorithm_errors"] == 0


def test_vrp_solver_output_passes_adapter_checks_and_recomputation(
    tmp_path: Path,
) -> None:
    vrp_path = _write_synthetic_vrp(tmp_path)
    adapter = _adapter()
    instance = adapter.load_instance(str(vrp_path))

    raw = _run_solver(str(vrp_path))
    artifact = adapter.deserialize_solver_output(raw, instance)

    assert instance.bks == 40.0
    assert instance.bks_routes == 1
    assert adapter.check_solution_consistency(artifact, instance).passed is True
    assert adapter.check_feasibility(artifact, instance).passed is True
    assert adapter.recompute_objective(artifact, instance) == raw["objective"]


def test_json_tiny_fixture_runner_behavior_still_succeeds() -> None:
    adapter = _adapter()
    instance = adapter.load_instance(str(TINY_5))

    raw = _run_solver("data/tiny_5.json")
    artifact = adapter.deserialize_solver_output(raw, instance)

    assert raw["feasible"] is True
    assert raw["objective"]["fleet_violation"] == 0
    assert raw["objective"]["total_distance"] == 8.0
    assert raw["objective"]["routes"] == 2
    assert adapter.check_solution_consistency(artifact, instance).passed is True
    assert adapter.check_feasibility(artifact, instance).passed is True
    assert adapter.recompute_objective(artifact, instance) == raw["objective"]


def test_data_root_relative_vrp_runs_active_algorithm_package(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data_root"
    case_dir = data_root / "cvrplib" / "synthetic"
    case_dir.mkdir(parents=True)
    vrp_path = _write_synthetic_vrp(case_dir)

    raw = _run_solver_with_env(
        "cvrplib/synthetic/synthetic_solver_smoke.vrp",
        data_root=data_root,
    )

    adapter = _adapter()
    instance = adapter.load_instance(str(vrp_path))
    artifact = adapter.deserialize_solver_output(raw, instance)
    assert raw["objective"] == {
        "fleet_violation": 0,
        "total_distance": 40.0,
        "routes": 1,
    }
    assert raw["runtime"]["solver_algorithm_loaded"] is True
    assert raw["runtime"]["solver_algorithm_active"] is True
    assert raw["runtime"]["solver_algorithm_errors"] == 0
    assert adapter.check_solution_consistency(artifact, instance).passed is True
    assert adapter.check_feasibility(artifact, instance).passed is True
