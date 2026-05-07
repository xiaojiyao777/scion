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

class TestSyntaxCheck:
    def test_valid_code_passes(self):
        r = check_syntax(_make_patch(_VALID_CODE))
        assert r.passed is True
        assert r.name == "V1_syntax"
        assert r.severity == "light"

    def test_bad_syntax_fails(self):
        r = check_syntax(_make_patch(_BAD_SYNTAX))
        assert r.passed is False
        assert r.severity == "light"
        assert "SyntaxError" in r.detail

    def test_delete_action_skipped(self):
        r = check_syntax(_make_patch(action="delete"))
        assert r.passed is True
        assert "delete" in r.detail


# ---------------------------------------------------------------------------
# V2: interface
# ---------------------------------------------------------------------------

class TestInterfaceCheck:
    def test_valid_class_passes_ast(self, tmp_path):
        r = check_interface(_make_patch(_VALID_CODE), str(tmp_path))
        assert r.passed is True
        assert r.name == "V2_interface"

    def test_missing_execute_fails_ast(self, tmp_path):
        r = check_interface(_make_patch(_NO_EXECUTE), str(tmp_path))
        assert r.passed is False
        assert r.severity == "light"

    def test_wrong_args_fails_ast(self, tmp_path):
        r = check_interface(_make_patch(_WRONG_ARGS), str(tmp_path))
        assert r.passed is False

    def test_problem_defined_signature_passes(self, tmp_path):
        code = """\
class MyOp:
    def execute(self, solution, instance, rng):
        return solution
"""
        r = check_interface(
            _make_patch(code),
            str(tmp_path),
            operator_execute_signature="execute(self, solution, instance, rng) -> TspSolution",
        )
        assert r.passed is True

    def test_problem_defined_signature_rejects_legacy_args(self, tmp_path):
        r = check_interface(
            _make_patch(_VALID_CODE),
            str(tmp_path),
            operator_execute_signature="execute(self, solution, instance, rng) -> TspSolution",
        )
        assert r.passed is False
        assert "instance" in r.detail

    def test_delete_action_skipped(self, tmp_path):
        r = check_interface(_make_patch(action="delete"), str(tmp_path))
        assert r.passed is True

    def test_no_class_skipped(self, tmp_path):
        code = "x = 1\ndef foo(): pass\n"
        r = check_interface(_make_patch(code), str(tmp_path))
        assert r.passed is True

    def test_runtime_check_with_real_file(self, tmp_path):
        """When operator file exists in workspace, runtime check is used."""
        op_dir = tmp_path / "operators"
        op_dir.mkdir()
        op_file = op_dir / "my_op.py"
        op_file.write_text(_VALID_CODE)

        patch = _make_patch(_VALID_CODE)
        r = check_interface(patch, str(tmp_path))
        assert r.passed is True

    def test_runtime_check_fails_no_execute(self, tmp_path):
        op_dir = tmp_path / "operators"
        op_dir.mkdir()
        op_file = op_dir / "my_op.py"
        op_file.write_text(_NO_EXECUTE)

        patch = _make_patch(_NO_EXECUTE)
        r = check_interface(patch, str(tmp_path))
        assert r.passed is False

    def test_interface_check_does_not_execute_top_level_code(self, tmp_path):
        op_dir = tmp_path / "operators"
        op_dir.mkdir()
        marker = tmp_path / "executed.txt"
        code = f"""\
from pathlib import Path
Path({str(marker)!r}).write_text("executed")

class MyOp:
    def execute(self, solution, rng):
        return solution
"""
        (op_dir / "my_op.py").write_text(code)

        patch = _make_patch(code)
        r = check_interface(patch, str(tmp_path))
        assert r.passed is True
        assert not marker.exists()

    def test_interface_check_rejects_invalid_patch_path(self, tmp_path):
        patch = PatchProposal(
            file_path="operators/../../outside.py",
            action="modify",
            code_content=_VALID_CODE,
        )
        r = check_interface(patch, str(tmp_path))
        assert r.passed is False
        assert "path segment" in r.detail

    def test_surface_policy_missing_required_function_fails_ast(self, tmp_path):
        patch = PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content=(
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.5\n"
            ),
        )

        r = check_interface(
            patch,
            str(tmp_path),
            problem_spec=_make_policy_interface_spec(),
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert r.name == "V2_interface"
        assert "missing required functions ['max_operator_rounds']" in r.detail

    def test_surface_policy_declared_signature_fails_ast(self, tmp_path):
        patch = PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content=(
                "def baseline_time_fraction(instance):\n"
                "    return 0.5\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 10\n"
            ),
        )

        r = check_interface(
            patch,
            str(tmp_path),
            problem_spec=_make_policy_interface_spec(),
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert "do not match declared prefix" in r.detail

    def test_surface_policy_static_return_constraint_fails_ast(self, tmp_path):
        patch = PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content=(
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 1.5\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 10\n"
            ),
        )

        r = check_interface(
            patch,
            str(tmp_path),
            problem_spec=_make_policy_interface_spec(),
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert "outside declared range" in r.detail

    def test_valid_surface_policy_module_without_class_passes_ast(self, tmp_path):
        patch = PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content=(
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.5\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 10\n"
            ),
        )

        r = check_interface(
            patch,
            str(tmp_path),
            problem_spec=_make_policy_interface_spec(),
            selected_surface="search_policy",
        )

        assert r.passed is True
        assert r.name == "V2_interface"

    def test_selected_surface_target_mismatch_fails_ast(self, tmp_path):
        spec = _make_policy_interface_spec()
        patch = _make_patch(_VALID_CODE)

        r = check_interface(
            patch,
            str(tmp_path),
            problem_spec=spec,
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert "is not in target files" in r.detail


# ---------------------------------------------------------------------------
# V3: feasibility
# ---------------------------------------------------------------------------

class TestFeasibilityCheck:
    def test_skipped_when_no_canary(self):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        r = check_feasibility(spec, runner, "/tmp")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_skipped_when_canary_not_found(self):
        spec = _make_spec(canary="/nonexistent/path/instance.json")
        runner = _mock_runner()
        r = check_feasibility(spec, runner, "/tmp")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_solver_failure_fails(self, tmp_path):
        # Create a dummy canary file.
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _mock_runner(success=False)
        r = check_feasibility(spec, runner, str(tmp_path))
        assert r.passed is False
        assert r.name == "V6_feasibility"

    def test_adapter_required_spec_without_adapter_fails_before_legacy_fallback(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        (tmp_path / "oracle.py").write_text(
            "def check_solver_output_feasibility(raw, canary):\n"
            "    raise AssertionError('legacy oracle should not be called')\n"
        )
        spec = _make_adapter_required_spec(canary).model_copy(
            update={"root_dir": str(tmp_path), "oracle_path": "oracle.py"}
        )
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_feasibility(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.name == "V6_feasibility"
        assert "problem adapter is required" in r.detail
        assert "legacy feasibility fallback disabled" in r.detail

    def test_legacy_oracle_fallback_remains_compatible(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        (tmp_path / "oracle.py").write_text(
            "def check_solver_output_feasibility(raw, canary):\n"
            "    return True\n"
        )
        spec = _make_spec(canary=canary).model_copy(
            update={"root_dir": str(tmp_path), "oracle_path": "oracle.py"}
        )
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_feasibility(spec, runner, str(tmp_path))

        assert r.passed is True
        assert r.name == "V6_feasibility"
        assert "feasibility ok" in r.detail

    def test_selected_surface_missing_runtime_field_preempts_adapter_required(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_adapter_required_spec(canary).model_copy(
            update={
                "research_surfaces": [
                    {
                        "name": "search_policy",
                        "kind": "policy",
                        "target_files": ["policies/search_policy.py"],
                        "evidence": {
                            "required_runtime_fields": ["policy_loaded"],
                        },
                    }
                ],
            }
        )
        output = _solver_output_dict()
        output["runtime"] = {}
        runner = _mock_runner(output_dict=output)

        r = check_feasibility(
            spec,
            runner,
            str(tmp_path),
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert "solver runtime audit failed" in r.detail
        assert "missing=policy_loaded" in r.detail
        assert "problem adapter is required" not in r.detail


# ---------------------------------------------------------------------------
# V5: solution consistency
# ---------------------------------------------------------------------------

class TestSolutionConsistencyCheck:
    def test_top_level_assignment_vehicle_mismatch_fails(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        output = _solver_output_dict()
        output["assignment"] = {"O1": "V_MISMATCH"}
        runner = _mock_runner(output_dict=output)

        r = check_state_mutation(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.severity == "heavy"
        assert "assignment says" in r.detail

    def test_adapter_consistency_failure_fails_closed(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _mock_runner(output_dict={"routes": [[1, 1]], "objective": {"cost": 1.0}})

        class RejectingAdapter:
            def load_instance(self, instance_path):
                return {"path": instance_path}

            def deserialize_solver_output(self, raw_output, instance):
                return SolverArtifact(
                    raw_output=raw_output,
                    objective={"cost": 1.0},
                    feasible=True,
                    normalized_solution=raw_output,
                )

            def check_solution_consistency(self, artifact, instance):
                return CheckReport(False, ("customer 1 appears twice",))

        r = check_state_mutation(spec, runner, str(tmp_path), adapter=RejectingAdapter())

        assert r.passed is False
        assert r.name == "V5_solution_consistency"
        assert "adapter consistency failed" in r.detail
        assert "customer 1 appears twice" in r.detail

    def test_adapter_required_spec_without_adapter_fails_before_legacy_fallback(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_adapter_required_spec(canary)
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_state_mutation(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.name == "V5_solution_consistency"
        assert "problem adapter is required" in r.detail
        assert "legacy solution consistency fallback disabled" in r.detail
        assert runner.run_solver.called

    def test_solver_runtime_audit_failure_fails_closed(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        output = _solver_output_dict()
        output["runtime"] = {
            "operator_errors": 1,
            "operator_events": [
                {
                    "operator": "bad_op",
                    "status": "error",
                    "detail": "'CvrpInstance' object has no attribute 'vehicle_capacity'",
                }
            ],
        }
        runner = _mock_runner(output_dict=output)

        r = check_state_mutation(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.name == "V5_solution_consistency"
        assert "solver runtime audit failed" in r.detail
        assert "operator_errors=1" in r.detail

    def test_surface_runtime_contract_all_required_fields_present_passes(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_surface_spec(
            canary,
            [
                {
                    "name": "search_policy",
                    "evidence": {
                        "required_runtime_fields": [
                            "policy_loaded",
                            "policy_errors",
                            "baseline_time_fraction",
                        ],
                    },
                },
            ],
        )
        output = _solver_output_dict()
        output["runtime"] = {
            "policy_loaded": True,
            "policy_errors": 0,
            "baseline_time_fraction": 0.6,
        }
        runner = _mock_runner(output_dict=output)

        r = check_state_mutation(
            spec,
            runner,
            str(tmp_path),
            selected_surface="search_policy",
        )

        assert r.passed is True

    def test_surface_without_declared_evidence_keeps_legacy_behavior(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_surface_spec(
            canary,
            [{"name": "local_search", "evidence": {"required_runtime_fields": []}}],
        )
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_state_mutation(
            spec,
            runner,
            str(tmp_path),
            selected_surface="local_search",
        )

        assert r.passed is True

    def test_surface_runtime_contract_skips_when_no_surface_selected(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_surface_spec(
            canary,
            [
                {
                    "name": "search_policy",
                    "evidence": {
                        "required_runtime_fields": ["policy_loaded"],
                    },
                },
            ],
        )
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_state_mutation(spec, runner, str(tmp_path))

        assert r.passed is True

    @pytest.mark.parametrize(
        ("required_field", "runtime_value", "expected_detail"),
        [
            ("dispatch_loaded", False, "failed=dispatch_loaded"),
            ("dispatch_executed", False, "failed=dispatch_executed"),
            ("dispatch_errors", 1, "failed=dispatch_errors"),
            ("dispatch_errors", "not-an-int", "failed=dispatch_errors"),
        ],
    )
    def test_generic_surface_runtime_evidence_fields_fail_closed(
        self,
        required_field,
        runtime_value,
        expected_detail,
    ):
        spec = _make_surface_spec(
            "",
            [
                {
                    "name": "dispatch_policy",
                    "evidence": {"required_runtime_fields": [required_field]},
                },
            ],
        )

        issue = runtime_audit_failure_from_runtime(
            {required_field: runtime_value},
            problem_spec=spec,
            selected_surface="dispatch_policy",
        )

        assert issue is not None
        assert issue["error_category"] == "surface_runtime_contract_error"
        assert issue["failed_runtime_fields"] == (required_field,)
        assert expected_detail in issue["detail"]


# ---------------------------------------------------------------------------
# V4: objective
# ---------------------------------------------------------------------------

class TestObjectiveCheck:
    def test_skipped_when_no_canary(self):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        r = check_objective(spec, runner, "/tmp")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_skipped_when_canary_not_found(self):
        spec = _make_spec(canary="/no/such/file.json")
        runner = _mock_runner()
        r = check_objective(spec, runner, "/tmp")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_solver_failure_fails(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _mock_runner(success=False)
        r = check_objective(spec, runner, str(tmp_path))
        assert r.passed is False
        assert r.name == "V7_objective"

    def test_solver_runtime_audit_failure_fails(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        output = _solver_output_dict()
        output["runtime"] = {"operator_errors": 1}
        runner = _mock_runner(output_dict=output)

        r = check_objective(spec, runner, str(tmp_path))

        assert r.passed is False
        assert "solver runtime audit failed" in r.detail

    def test_adapter_required_spec_without_adapter_fails_before_legacy_fallback(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        (tmp_path / "oracle.py").write_text(
            "def recompute_solver_output_objective(raw, canary):\n"
            "    raise AssertionError('legacy oracle should not be called')\n"
        )
        spec = _make_adapter_required_spec(canary).model_copy(
            update={"root_dir": str(tmp_path), "oracle_path": "oracle.py"}
        )
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_objective(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.name == "V7_objective"
        assert "problem adapter is required" in r.detail
        assert "legacy objective fallback disabled" in r.detail

    def test_adapter_declared_objective_missing_from_solver_output_fails(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _with_objectives(_make_spec(canary=canary), "cost", "penalty")
        runner = _mock_runner(
            output_dict={
                "objective": {"penalty": 0},
                "feasible": True,
            }
        )

        class ObjectiveAdapter:
            def load_instance(self, instance_path):
                return {"path": instance_path}

            def deserialize_solver_output(self, raw_output, instance):
                return SolverArtifact(
                    raw_output=raw_output,
                    objective=dict(raw_output.get("objective", {})),
                    feasible=True,
                    normalized_solution={},
                )

            def recompute_objective(self, artifact, instance):
                return {"cost": 10, "penalty": 0}

        r = check_objective(
            spec,
            runner,
            str(tmp_path),
            adapter=ObjectiveAdapter(),
        )

        assert r.passed is False
        assert "solver objective missing declared metrics: cost" in r.detail

    def test_adapter_declared_objective_missing_from_recomputation_fails(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _with_objectives(_make_spec(canary=canary), "cost", "penalty")
        runner = _mock_runner(
            output_dict={
                "objective": {"cost": 10, "penalty": 0},
                "feasible": True,
            }
        )

        class ObjectiveAdapter:
            def load_instance(self, instance_path):
                return {"path": instance_path}

            def deserialize_solver_output(self, raw_output, instance):
                return SolverArtifact(
                    raw_output=raw_output,
                    objective=dict(raw_output.get("objective", {})),
                    feasible=True,
                    normalized_solution={},
                )

            def recompute_objective(self, artifact, instance):
                return {"cost": 10}

        r = check_objective(
            spec,
            runner,
            str(tmp_path),
            adapter=ObjectiveAdapter(),
        )

        assert r.passed is False
        assert "adapter recomputation missing declared metrics: penalty" in r.detail

    def test_selected_surface_missing_runtime_field_preempts_adapter_required(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_adapter_required_spec(canary).model_copy(
            update={
                "research_surfaces": [
                    {
                        "name": "search_policy",
                        "kind": "policy",
                        "target_files": ["policies/search_policy.py"],
                        "evidence": {
                            "required_runtime_fields": ["policy_loaded"],
                        },
                    }
                ],
            }
        )
        output = _solver_output_dict()
        output["runtime"] = {}
        runner = _mock_runner(output_dict=output)

        r = check_objective(
            spec,
            runner,
            str(tmp_path),
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert "solver runtime audit failed" in r.detail
        assert "missing=policy_loaded" in r.detail
        assert "problem adapter is required" not in r.detail


# ---------------------------------------------------------------------------
# V8: nondeterminism
# ---------------------------------------------------------------------------

class TestStateleakCheck:
    def test_skipped_when_no_canary(self):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        r = check_nondeterminism(spec, runner, "/tmp")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_deterministic_runs_pass(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        # Both runs return same objective.
        runner = _mock_runner(output_dict=_solver_output_dict(splits=2, cost=6600))
        r = check_nondeterminism(spec, runner, str(tmp_path))
        # Check passes (even if oracle isn't available — we compare raw JSON objects).
        assert r.name == "V8_nondeterminism"
        assert r.passed is True
        assert r.metadata["comparison_mode"] == "legacy_objective"
        assert r.metadata["adapter_backed"] is False
        assert r.metadata["comparison_equal"] is True

    def test_non_deterministic_runs_fail(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)

        call_count = [0]

        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            call_count[0] += 1
            fd, path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            # Return different objective on second call.
            splits = 2 if call_count[0] == 1 else 5
            data = _solver_output_dict(splits=splits)
            with open(path, "w") as f:
                json.dump(data, f)
            sol = SolverOutput(
                vehicles=data["vehicles"],
                assignment=data["assignment"],
                objective=data["objective"],
                feasible=True,
            )
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=100, output=sol, output_path=path, error_category=None,
            )

        runner = MagicMock()
        runner.run_solver.side_effect = run_solver

        r = check_nondeterminism(spec, runner, str(tmp_path))
        assert r.passed is False
        assert r.name == "V8_nondeterminism"
        # detail is now a JSON string with diff_keys
        detail = json.loads(r.detail)
        assert "diff_keys" in detail
        assert len(detail["diff_keys"]) > 0

    def test_adapter_required_spec_without_adapter_fails_closed(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_adapter_required_spec(canary)
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_nondeterminism(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.name == "V8_nondeterminism"
        detail = json.loads(r.detail)
        assert detail["comparison_mode"] == "adapter_required_missing"
        assert detail["selected_surface"] is None
        assert "problem adapter is required" in detail["error"]
        assert "legacy nondeterminism fallback disabled" in detail["error"]

    def test_adapter_backed_fails_when_normalized_artifacts_differ(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _sequential_runner(
            [
                {"routes": [[0, 1, 0]], "objective": {"cost": 10}, "feasible": True},
                {"routes": [[0, 2, 0]], "objective": {"cost": 10}, "feasible": True},
            ]
        )

        class RouteAdapter:
            def load_instance(self, instance_path):
                return {"path": instance_path}

            def deserialize_solver_output(self, raw_output, instance):
                return SolverArtifact(
                    raw_output=raw_output,
                    objective=dict(raw_output.get("objective", {})),
                    feasible=bool(raw_output.get("feasible")),
                    normalized_solution=raw_output.get("routes"),
                )

        r = check_nondeterminism(
            spec,
            runner,
            str(tmp_path),
            adapter=RouteAdapter(),
        )

        assert r.passed is False
        detail = json.loads(r.detail)
        assert detail["comparison_mode"] == "adapter_canonical_signature"
        assert detail["diff_keys"] == ["normalized_solution"]
        assert detail["run1_signature"]["objective"] == {"cost": 10}
        assert detail["run2_signature"]["objective"] == {"cost": 10}

    def test_adapter_backed_passes_when_raw_output_differs_but_signature_equal(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _sequential_runner(
            [
                {
                    "routes": [[0, 1, 0]],
                    "objective": {"cost": 10},
                    "feasible": True,
                    "diagnostics": {"nonce": "a"},
                },
                {
                    "routes": [[0, 1, 0]],
                    "objective": {"cost": 10},
                    "feasible": True,
                    "diagnostics": {"nonce": "b"},
                },
            ]
        )

        class RouteAdapter:
            def load_instance(self, instance_path):
                return {"path": instance_path}

            def deserialize_solver_output(self, raw_output, instance):
                return SolverArtifact(
                    raw_output=raw_output,
                    objective=dict(raw_output.get("objective", {})),
                    feasible=bool(raw_output.get("feasible")),
                    normalized_solution=raw_output.get("routes"),
                )

        r = check_nondeterminism(
            spec,
            runner,
            str(tmp_path),
            adapter=RouteAdapter(),
        )

        assert r.passed is True
        assert "adapter_canonical_signature identical" in r.detail
        assert r.metadata["comparison_mode"] == "adapter_canonical_signature"
        assert r.metadata["adapter_backed"] is True
        assert r.metadata["comparison_equal"] is True

    @pytest.mark.parametrize(
        ("bad_run", "expected_run"),
        [
            (0, "first"),
            (1, "second"),
        ],
    )
    def test_selected_surface_runtime_audit_fails_on_either_run(
        self,
        tmp_path,
        bad_run,
        expected_run,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_adapter_required_spec(canary).model_copy(
            update={
                "research_surfaces": [
                    {
                        "name": "search_policy",
                        "kind": "policy",
                        "target_files": ["policies/search_policy.py"],
                        "evidence": {
                            "required_runtime_fields": ["policy_loaded"],
                        },
                    }
                ],
            }
        )
        ok_output = _solver_output_dict()
        ok_output["runtime"] = {"policy_loaded": True}
        bad_output = _solver_output_dict()
        bad_output["runtime"] = {}
        outputs = [ok_output, ok_output]
        outputs[bad_run] = bad_output
        runner = _sequential_runner(outputs)

        r = check_nondeterminism(
            spec,
            runner,
            str(tmp_path),
            selected_surface="search_policy",
        )

        assert r.passed is False
        detail = json.loads(r.detail)
        assert detail["comparison_mode"] == "runtime_audit"
        assert detail["selected_surface"] == "search_policy"
        assert detail["run"] == expected_run
        assert f"{expected_run} run runtime audit failed" in detail["error"]
        assert "missing=policy_loaded" in detail["error"]
        assert "problem adapter is required" not in detail["error"]


# ---------------------------------------------------------------------------
# V6: perf_guard
# ---------------------------------------------------------------------------

class TestPerfGuardCheck:
    def test_skipped_when_no_canary(self):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        r = check_perf(spec, runner, "/tmp", "/tmp/champ")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_skipped_when_no_champion_workspace(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _mock_runner()
        r = check_perf(spec, runner, str(tmp_path), "")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_fast_candidate_passes(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        champ_ws = str(tmp_path / "champ")
        Path(champ_ws).mkdir()
        spec = _make_spec(canary=canary)

        # Candidate: 500ms, Champion: 1000ms → ratio=0.5 → passes
        call_count = [0]
        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            call_count[0] += 1
            ms = 500 if workdir != champ_ws else 1000
            fd, path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            data = _solver_output_dict()
            with open(path, "w") as f:
                json.dump(data, f)
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=ms, output=None, output_path=path, error_category=None,
            )

        runner = MagicMock()
        runner.run_solver.side_effect = run_solver
        r = check_perf(spec, runner, str(tmp_path), champ_ws)
        assert r.passed is True
        assert r.name == "V9_perf_guard"
        assert r.metadata["candidate_ms"] == 500
        assert r.metadata["champion_ms"] == 1000
        assert r.metadata["ratio"] == pytest.approx(0.5)
        assert r.metadata["candidate_timeout"] is False

    def test_slow_candidate_fails(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        champ_ws = str(tmp_path / "champ")
        Path(champ_ws).mkdir()
        spec = _make_spec(canary=canary)

        # Candidate: 6000ms, Champion: 1000ms → ratio=6 > 5 → fails
        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            ms = 6000 if workdir != champ_ws else 1000
            fd, path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            data = _solver_output_dict()
            with open(path, "w") as f:
                json.dump(data, f)
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=ms, output=None, output_path=path, error_category=None,
            )

        runner = MagicMock()
        runner.run_solver.side_effect = run_solver
        r = check_perf(spec, runner, str(tmp_path), champ_ws)
        assert r.passed is False
        assert "too slow" in r.detail
        assert r.metadata["ratio"] == pytest.approx(6.0)
        assert r.metadata["limit_ratio"] == 5.0

    def test_configured_slowdown_limit_is_used(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        champ_ws = str(tmp_path / "champ")
        Path(champ_ws).mkdir()
        spec = _make_spec(canary=canary)

        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            ms = 3000 if workdir != champ_ws else 1000
            fd, path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            with open(path, "w") as f:
                json.dump(_solver_output_dict(), f)
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=ms, output=None, output_path=path, error_category=None,
            )

        runner = MagicMock()
        runner.run_solver.side_effect = run_solver
        r = check_perf(spec, runner, str(tmp_path), champ_ws, max_slowdown=2.0)
        assert r.passed is False
        assert r.metadata["ratio"] == pytest.approx(3.0)
        assert r.metadata["limit_ratio"] == 2.0
        assert "limit=2x" in r.detail


# ---------------------------------------------------------------------------
# VerificationGate (integration)
# ---------------------------------------------------------------------------

class TestVerificationGateIntegration:
    def test_no_runner_runs_static_checks_only(self):
        gate = VerificationGate()
        patch = _make_patch(_VALID_CODE)
        result = gate.run("/tmp", "", patch)
        assert result.passed is True
        # Only V1+V2 checks (no runner, no spec)
        check_names = [c.name for c in result.checks]
        assert "V1_syntax" in check_names
        assert "V2_interface" in check_names
        # No runtime checks
        assert "V6_feasibility" not in check_names

    def test_syntax_fail_stops_early(self):
        gate = VerificationGate()
        patch = _make_patch(_BAD_SYNTAX)
        result = gate.run("/tmp", "", patch)
        assert result.passed is False
        assert result.failure_severity == "light"
        assert result.first_failure == "V1_syntax"

    def test_interface_fail_stops_early(self, tmp_path):
        gate = VerificationGate()
        patch = _make_patch(_NO_EXECUTE)
        result = gate.run(str(tmp_path), "", patch)
        assert result.passed is False
        assert result.failure_severity == "light"
        assert result.first_failure == "V2_interface"

    def test_with_spec_no_canary_skips_runtime(self):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        gate = VerificationGate(problem_spec=spec, runner=runner)
        patch = _make_patch(_VALID_CODE)
        result = gate.run("/tmp", "", patch)
        assert result.passed is True
        # All runtime checks should be present (but skipped/passed)
        check_names = [c.name for c in result.checks]
        assert "V6_feasibility" in check_names
        assert "V7_objective" in check_names
        assert "V8_nondeterminism" in check_names
        assert "V9_perf_guard" in check_names

    def test_strict_runtime_checks_fail_without_runner_or_spec(self):
        gate = VerificationGate(strict_runtime_checks=True)
        patch = _make_patch(_VALID_CODE)
        result = gate.run("/tmp", "/tmp", patch)
        assert result.passed is False
        assert result.failure_severity == "heavy"
        assert result.first_failure == "V_runtime_config"

    def test_strict_runtime_checks_fail_without_canary(self, tmp_path):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        gate = VerificationGate(
            problem_spec=spec,
            runner=runner,
            strict_runtime_checks=True,
        )
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), str(tmp_path), patch)
        assert result.passed is False
        assert result.first_failure == "V_runtime_config"
        assert "canary_case_path" in result.checks[-1].detail

    def test_strict_runtime_checks_fail_without_champion_workspace(self, tmp_path):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_spec(canary=str(canary))
        runner = _mock_runner()
        gate = VerificationGate(
            problem_spec=spec,
            runner=runner,
            strict_runtime_checks=True,
        )
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), str(tmp_path / "missing_champion"), patch)
        assert result.passed is False
        assert result.first_failure == "V_runtime_config"
        assert "champion workspace" in result.checks[-1].detail

    def test_strict_runtime_config_resolves_problem_relative_canary(self, tmp_path):
        from scion.verification.gate import _validate_runtime_config

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "small.json").write_text("{}")
        spec = _make_spec(canary="data/small.json").model_copy(
            update={"root_dir": str(tmp_path)}
        )

        result = _validate_runtime_config(spec, str(tmp_path))

        assert result is None

    def test_strict_runtime_checks_can_require_adapter(self, tmp_path):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_spec(canary=str(canary))
        runner = _mock_runner()
        gate = VerificationGate(
            problem_spec=spec,
            runner=runner,
            strict_runtime_checks=True,
            require_adapter_for_runtime=True,
        )
        patch = _make_patch(_VALID_CODE)

        result = gate.run(str(tmp_path), str(tmp_path), patch)

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "problem adapter" in result.checks[-1].detail

    def test_adapter_backed_problem_v1_without_adapter_fails_v5(self, tmp_path):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_adapter_required_spec(str(canary))
        runner = _mock_runner(output_dict=_solver_output_dict())
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = gate.run(str(tmp_path), str(tmp_path), _make_patch(_VALID_CODE))

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "problem adapter is required" in result.checks[-1].detail
        assert "legacy solution consistency fallback disabled" in result.checks[-1].detail

    def test_selected_surface_runtime_fields_do_not_enable_legacy_v5_fallback(
        self,
        tmp_path,
    ):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_adapter_required_spec(str(canary)).model_copy(
            update={
                "operator_categories": ["search_policy"],
                "research_surfaces": [
                    {
                        "name": "search_policy",
                        "kind": "operator",
                        "target_files": ["operators/*.py"],
                        "evidence": {
                            "required_runtime_fields": [
                                "policy_loaded",
                                "policy_errors",
                            ],
                        },
                    }
                ],
            }
        )
        output = _solver_output_dict()
        output["runtime"] = {
            "policy_loaded": True,
            "policy_errors": 0,
        }
        runner = _mock_runner(output_dict=output)
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = gate.run(
            str(tmp_path),
            str(tmp_path),
            _make_patch(_VALID_CODE),
            selected_surface="search_policy",
        )

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "problem adapter is required" in result.checks[-1].detail
        assert "legacy solution consistency fallback disabled" in result.checks[-1].detail

    def test_strict_adapter_backed_runtime_passes_toy_tsp(self, tmp_path):
        spec_v1, adapter = _load_toy_tsp_adapter()
        canary = os.path.join(spec_v1.root_dir, "data", "tsp_10.json")
        spec = _make_spec(canary=canary).model_copy(update={"root_dir": spec_v1.root_dir})
        runner = _mock_runner(output_dict={"tour": list(range(10))}, elapsed_ms=100)
        gate = VerificationGate(
            problem_spec=spec,
            runner=runner,
            adapter=adapter,
            strict_runtime_checks=True,
            require_adapter_for_runtime=True,
            operator_execute_signature=spec_v1.operator_interface.execute_signature,
        )

        result = gate.run(str(tmp_path), str(tmp_path), _make_toy_tsp_patch())

        assert result.passed is True
        check_names = [c.name for c in result.checks]
        assert "V6_feasibility" in check_names
        assert "V7_objective" in check_names

    def test_gate_uses_problem_defined_interface_signature(self, tmp_path):
        gate = VerificationGate(
            operator_execute_signature="execute(self, solution, instance, rng) -> TspSolution"
        )
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), "", patch)
        assert result.passed is False
        assert result.first_failure == "V2_interface"

    def test_gate_forwards_hypothesis_surface_to_v2_interface(self, tmp_path):
        gate = VerificationGate(problem_spec=_make_policy_interface_spec())
        patch = _make_patch(_VALID_CODE)

        result = gate.run(
            str(tmp_path),
            "",
            patch,
            hypothesis=_make_hypothesis("search_policy"),
        )

        assert result.passed is False
        assert result.first_failure == "V2_interface"
        assert "is not in target files" in result.checks[-1].detail

    def test_delete_patch_passes_all(self):
        gate = VerificationGate()
        patch = _make_patch(action="delete")
        result = gate.run("/tmp", "", patch)
        assert result.passed is True

    def test_selected_surface_missing_runtime_field_fails_closed(self, tmp_path):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_surface_spec(
            str(canary),
            [
                {
                    "name": "search_policy",
                    "evidence": {
                        "required_runtime_fields": [
                            "policy_loaded",
                            "policy_errors",
                        ],
                    },
                },
            ],
        )
        runner = _mock_runner(
            output_dict={
                **_solver_output_dict(),
                "runtime": {"policy_loaded": True},
            }
        )
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = gate.run(
            str(tmp_path),
            str(tmp_path),
            _make_patch(_VALID_CODE),
            selected_surface="search_policy",
        )

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "failed runtime evidence contract" in result.checks[-1].detail
        assert "missing=policy_errors" in result.checks[-1].detail

    def test_unknown_selected_surface_fails_at_v2_interface(self, tmp_path):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_surface_spec(
            str(canary),
            [
                {
                    "name": "search_policy",
                    "evidence": {
                        "required_runtime_fields": ["policy_loaded"],
                    },
                },
            ],
        )
        runner = _mock_runner(
            output_dict={
                **_solver_output_dict(),
                "runtime": {"policy_loaded": True},
            }
        )
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = gate.run(
            str(tmp_path),
            str(tmp_path),
            _make_patch(_VALID_CODE),
            selected_surface="not_declared",
        )

        assert result.passed is False
        assert result.first_failure == "V2_interface"
        assert "is not declared" in result.checks[-1].detail

    def test_hypothesis_change_locus_selects_surface_for_runtime_contract(
        self,
        tmp_path,
    ):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_surface_spec(
            str(canary),
            [
                {
                    "name": "search_policy",
                    "evidence": {
                        "required_runtime_fields": [
                            "policy_loaded",
                            "policy_errors",
                        ],
                    },
                },
            ],
        )
        runner = _mock_runner(
            output_dict={
                **_solver_output_dict(),
                "runtime": {"policy_loaded": True},
            }
        )
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = gate.run(
            str(tmp_path),
            str(tmp_path),
            _make_patch(_VALID_CODE),
            hypothesis=_make_hypothesis("search_policy"),
        )

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "failed runtime evidence contract" in result.checks[-1].detail
        assert "missing=policy_errors" in result.checks[-1].detail

    def test_run_verification_gate_helper_forwards_hypothesis_surface(
        self,
        tmp_path,
    ):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_surface_spec(
            str(canary),
            [
                {
                    "name": "dispatch_policy",
                    "evidence": {
                        "required_runtime_fields": [
                            "dispatch_executed",
                            "dispatch_errors",
                        ],
                    },
                },
            ],
        )
        runner = _mock_runner(
            output_dict={
                **_solver_output_dict(),
                "runtime": {
                    "dispatch_executed": False,
                    "dispatch_errors": 0,
                },
            }
        )
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = run_verification_gate(
            gate,
            str(tmp_path),
            str(tmp_path),
            _make_patch(_VALID_CODE),
            hypothesis=_make_hypothesis("dispatch_policy"),
        )

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "failed=dispatch_executed" in result.checks[-1].detail


# ---------------------------------------------------------------------------
# V3: unit tests
# ---------------------------------------------------------------------------

class TestUnitTestsCheck:
    def test_skipped_when_no_test_file(self, tmp_path):
        """Returns passed=True with 'skipped' detail when no test file found."""
        spec = _make_spec()
        r = check_unit_tests(spec, None, str(tmp_path))
        assert r.passed is True
        assert "skipped" in r.detail
        assert r.name == "V3_unit_tests"
        assert r.severity == "light"

    def test_passes_on_valid_test_file(self, tmp_path):
        """Passing pytest file → check passes."""
        test_file = tmp_path / "test_dummy.py"
        test_file.write_text("def test_pass(): assert True\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"unit_test_path": str(test_file)})
        r = check_unit_tests(spec, None, str(tmp_path))
        assert r.passed is True
        assert r.name == "V3_unit_tests"

    def test_fails_on_failing_test_file(self, tmp_path):
        """Failing pytest file → check fails."""
        test_file = tmp_path / "test_dummy.py"
        test_file.write_text("def test_fail(): assert False, 'intentional failure'\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"unit_test_path": str(test_file)})
        r = check_unit_tests(spec, None, str(tmp_path))
        assert r.passed is False
        assert r.severity == "light"

    def test_uses_fallback_path_when_not_configured(self, tmp_path):
        """Falls back to tests/test_operators.py relative to root_dir."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_operators.py").write_text("def test_ok(): pass\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"root_dir": str(tmp_path)})
        r = check_unit_tests(spec, None, str(tmp_path))
        assert r.passed is True


# ---------------------------------------------------------------------------
# V4: regression tests
# ---------------------------------------------------------------------------

class TestRegressionTestsCheck:
    def test_skipped_when_no_test_file(self, tmp_path):
        """Returns passed=True with 'skipped' detail when no test file found."""
        spec = _make_spec()
        r = check_regression_tests(spec, None, str(tmp_path))
        assert r.passed is True
        assert "skipped" in r.detail
        assert r.name == "V4_regression_tests"
        assert r.severity == "light"

    def test_passes_on_valid_test_file(self, tmp_path):
        """Passing pytest regression file → check passes."""
        test_file = tmp_path / "test_regression.py"
        test_file.write_text("def test_pass(): assert 1 + 1 == 2\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"regression_test_path": str(test_file)})
        r = check_regression_tests(spec, None, str(tmp_path))
        assert r.passed is True
        assert r.name == "V4_regression_tests"

    def test_fails_on_failing_test_file(self, tmp_path):
        """Failing regression test → check fails with light severity."""
        test_file = tmp_path / "test_regression.py"
        test_file.write_text("def test_fail(): raise AssertionError('regression')\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"regression_test_path": str(test_file)})
        r = check_regression_tests(spec, None, str(tmp_path))
        assert r.passed is False
        assert r.severity == "light"

    def test_uses_fallback_path_when_not_configured(self, tmp_path):
        """Falls back to tests/test_solver.py relative to root_dir."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_solver.py").write_text("def test_noop(): pass\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"root_dir": str(tmp_path)})
        r = check_regression_tests(spec, None, str(tmp_path))
        assert r.passed is True


# ---------------------------------------------------------------------------
# VerificationGate: V3/V4 test checks included when runner+spec present
# ---------------------------------------------------------------------------

class TestVerificationGateTestChecks:
    def test_unit_tests_in_gate_with_spec_and_runner(self, tmp_path):
        """V3_unit_tests and V4_regression_tests appear when runner+spec set."""
        spec = _make_spec()
        runner = _mock_runner()
        gate = VerificationGate(problem_spec=spec, runner=runner)
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), str(tmp_path), patch)
        check_names = [c.name for c in result.checks]
        assert "V3_unit_tests" in check_names
        assert "V4_regression_tests" in check_names

    def test_test_checks_absent_when_no_runner(self, tmp_path):
        """V3_unit_tests and V4_regression_tests not included without runner."""
        gate = VerificationGate()
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), str(tmp_path), patch)
        check_names = [c.name for c in result.checks]
        assert "V3_unit_tests" not in check_names
        assert "V4_regression_tests" not in check_names

    def test_failing_unit_test_has_light_severity(self, tmp_path):
        """Unit test failure → VerificationResult has light severity."""
        test_file = tmp_path / "test_fail.py"
        test_file.write_text("def test_fail(): assert False\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"unit_test_path": str(test_file)})
        runner = _mock_runner()
        gate = VerificationGate(problem_spec=spec, runner=runner)
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), str(tmp_path), patch)
        assert result.passed is False
        assert result.failure_severity == "light"
        assert result.first_failure == "V3_unit_tests"
