"""Tests for scion.verification — V1–V8 checks and VerificationGate."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.models import (
    CheckResult,
    HypothesisProposal,
    PatchProposal,
    RunResult,
    SolverOutput,
    VerificationResult,
)
from scion.core.verification_call import run_verification_gate
from scion.runtime.audit import runtime_audit_failure_from_runtime
from scion.verification.gate import VerificationGate
from scion.verification.syntax import check_syntax
from scion.verification.interface import check_interface
from scion.verification.tests import check_unit_tests, check_regression_tests
from scion.verification.state_mutation import check_state_mutation
from scion.verification.feasibility import check_feasibility
from scion.verification.objective import check_objective
from scion.verification.nondeterminism import check_nondeterminism
from scion.verification.perf_guard import check_perf
from scion.problem.contracts import CheckReport, SolverArtifact
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import ProblemSpecV1


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_VALID_CODE = """\
class MyOp:
    def execute(self, solution, rng):
        return solution
"""

_BAD_SYNTAX = "def bad(:\n    pass"

_NO_EXECUTE = """\
class MyOp:
    def do_stuff(self, x):
        return x
"""

_WRONG_ARGS = """\
class MyOp:
    def execute(self, solution):
        return solution
"""


def _make_patch(code: str = _VALID_CODE, action: str = "modify") -> PatchProposal:
    return PatchProposal(
        file_path="operators/my_op.py",
        action=action,
        code_content=code,
    )


def _make_toy_tsp_patch() -> PatchProposal:
    return PatchProposal(
        file_path="operators/two_opt.py",
        action="modify",
        code_content=(
            "class MyOp:\n"
            "    def execute(self, solution, instance, rng):\n"
            "        return solution\n"
        ),
    )


def _make_hypothesis(change_locus: str = "search_policy") -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="Tune the selected research surface.",
        change_locus=change_locus,
        action="modify",
        target_file="policies/search_policy.py",
    )


def _make_spec(canary: str = "") -> ProblemSpec:
    return ProblemSpec(
        name="test",
        root_dir="/tmp",
        canary_case_path=canary,
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["random", "math"],
        ),
    )


def _make_surface_spec(canary: str, surfaces: list[dict[str, Any]]) -> ProblemSpec:
    normalized_surfaces: list[dict[str, Any]] = []
    for surface in surfaces:
        item = dict(surface)
        item.setdefault("kind", "operator")
        if "target_files" not in item and "targets" not in item:
            item["target_files"] = ["operators/*.py"]
        normalized_surfaces.append(item)
    return _make_spec(canary=canary).model_copy(
        update={"research_surfaces": normalized_surfaces}
    )


def _make_policy_interface_spec(canary: str = "") -> ProblemSpec:
    return _make_spec(canary=canary).model_copy(
        update={
            "operator_categories": ["search_policy"],
            "research_surfaces": [
                {
                    "name": "search_policy",
                    "kind": "policy",
                    "target_files": ["policies/search_policy.py"],
                    "interface": {
                        "required_functions": [
                            "baseline_time_fraction",
                            "max_operator_rounds",
                        ],
                        "function_signatures": {
                            "baseline_time_fraction": [
                                "instance",
                                "time_limit_sec",
                            ],
                            "max_operator_rounds": [
                                "instance",
                                "time_limit_sec",
                            ],
                        },
                        "return_values": {
                            "baseline_time_fraction": {
                                "value_type": "number",
                                "numeric_range": [0.05, 0.95],
                            },
                            "max_operator_rounds": {
                                "value_type": "int",
                                "numeric_range": [0, 50],
                            },
                        },
                    },
                }
            ],
        }
    )


def _make_adapter_required_spec(canary: str) -> ProblemSpec:
    return _make_spec(canary=canary).model_copy(
        update={
            "spec_version": "problem-v1",
            "adapter_import_path": "scion.problems.demo.adapter:DemoAdapter",
            "requires_adapter_for_runtime": True,
        }
    )


def _with_objectives(spec: ProblemSpec, *names: str) -> ProblemSpec:
    object.__setattr__(
        spec,
        "objectives",
        tuple(SimpleNamespace(name=name) for name in names),
    )
    return spec


def _solver_output_dict(splits: int = 2, cost: int = 6600) -> dict:
    return {
        "vehicles": {
            "V0": {
                "vehicle_id": "V0",
                "vehicle_type": "HQ40",
                "region": "东莞",
                "order_ids": ["O1"],
                "cost": cost,
            }
        },
        "assignment": {"O1": "V0"},
        "objective": {
            "subcategory_splits": splits,
            "total_cost": cost,
            "solve_time_ms": 100,
        },
        "feasible": True,
    }


def _load_toy_tsp_adapter():
    import yaml

    toy_dir = Path(__file__).resolve().parents[1] / "problems" / "toy_tsp"
    with open(toy_dir / "problem.yaml", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    data["root_dir"] = str(toy_dir)
    spec_v1 = ProblemSpecV1(**data)
    return spec_v1, load_problem_adapter(spec_v1)


def _mock_runner(
    success: bool = True,
    elapsed_ms: int = 500,
    output_dict: dict | None = None,
    output_path: str | None = None,
) -> Any:
    """Create a mock runner that writes output to a temp file."""
    runner = MagicMock()

    def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
        if not success:
            return RunResult(
                success=False, exit_code=1, stdout="", stderr="fail",
                elapsed_ms=elapsed_ms, output=None, output_path=None,
                error_category="crash",
            )
        # Write output to a temp file.
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        data = output_dict or _solver_output_dict()
        with open(path, "w") as f:
            json.dump(data, f)
        sol_out = SolverOutput(
            vehicles=data.get("vehicles", {}),
            assignment=data.get("assignment", {}),
            objective=data.get("objective", {}),
            feasible=data.get("feasible", False),
            runtime=(
                data.get("runtime", {})
                if isinstance(data.get("runtime", {}), dict)
                else {}
            ),
        )
        return RunResult(
            success=True, exit_code=0, stdout="", stderr="",
            elapsed_ms=elapsed_ms, output=sol_out, output_path=path,
            error_category=None,
        )

    runner.run_solver.side_effect = run_solver
    return runner


def _sequential_runner(outputs: list[dict]) -> Any:
    """Create a mock runner that returns one output per solver call."""
    runner = MagicMock()
    call_count = [0]

    def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
        index = min(call_count[0], len(outputs) - 1)
        call_count[0] += 1
        data = outputs[index]
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w") as f:
            json.dump(data, f)
        return RunResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            elapsed_ms=100,
            output=SolverOutput(
                vehicles=data.get("vehicles", {}),
                assignment=data.get("assignment", {}),
                objective=data.get("objective", {}),
                feasible=data.get("feasible", False),
                runtime=(
                    data.get("runtime", {})
                    if isinstance(data.get("runtime", {}), dict)
                    else {}
                ),
            ),
            output_path=path,
            error_category=None,
        )

    runner.run_solver.side_effect = run_solver
    return runner


# ---------------------------------------------------------------------------
# V1: syntax
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# V2: interface
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# V3: feasibility
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# V5: solution consistency
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# V4: objective
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# V8: nondeterminism
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# V6: perf_guard
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# VerificationGate (integration)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# V3: unit tests
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# V4: regression tests
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# VerificationGate: V3/V4 test checks included when runner+spec present
# ---------------------------------------------------------------------------


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
