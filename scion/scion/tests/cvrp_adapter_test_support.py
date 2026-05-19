"""CVRP adapter tests for v0.4 route-native verification."""
from __future__ import annotations

import json
import os
import random
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.models import PatchProposal, RunResult, SolverOutput
from scion.problem.contracts import ProblemAdapter
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import ProblemSpecV1
from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution
from scion.problems.cvrp.solver import solve
from scion.verification.gate import VerificationGate
from scion.problems.cvrp import adapter as cvrp_adapter_module


CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"
TINY_5 = CVRP_DIR / "data" / "tiny_5.json"


@pytest.fixture
def cvrp_spec() -> ProblemSpecV1:
    with open(CVRP_DIR / "problem-v1.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data["root_dir"] = str(CVRP_DIR)
    data["canary_case_path"] = str(TINY_5)
    return ProblemSpecV1(**data)


@pytest.fixture
def cvrp_adapter(cvrp_spec: ProblemSpecV1) -> ProblemAdapter:
    return load_problem_adapter(cvrp_spec)


def _raw(routes: list[list[int]], *, distance: float = 8.0, fleet: int = 0) -> dict[str, Any]:
    return {
        "routes": routes,
        "objective": {
            "fleet_violation": fleet,
            "total_distance": distance,
            "routes": len(routes),
        },
        "feasible": True,
    }




__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
