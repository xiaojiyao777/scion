"""CVRP solver registry-operator runtime tests."""
from __future__ import annotations

"""Shared fixtures/helpers for CVRP solver runtime tests."""

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
    selected_surface: str | None = None,
) -> dict[str, Any]:
    result = _runner().run_solver(
        workdir=str(workspace),
        instance_path=instance_path,
        seed=seed,
        time_limit_sec=2,
        registry_path="" if registry_path is None else registry_path,
        selected_surface=selected_surface,
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




__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
