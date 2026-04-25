"""Tests for scion.verification — V1–V8 checks and VerificationGate."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.models import CheckResult, PatchProposal, RunResult, SolverOutput, VerificationResult
from scion.verification.gate import VerificationGate
from scion.verification.syntax import check_syntax
from scion.verification.interface import check_interface
from scion.verification.tests import check_unit_tests, check_regression_tests
from scion.verification.state_mutation import check_state_mutation
from scion.verification.feasibility import check_feasibility
from scion.verification.objective import check_objective
from scion.verification.nondeterminism import check_nondeterminism
from scion.verification.perf_guard import check_perf
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
        )
        return RunResult(
            success=True, exit_code=0, stdout="", stderr="",
            elapsed_ms=elapsed_ms, output=sol_out, output_path=path,
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
        assert result.first_failure == "V_runtime_config"
        assert "problem adapter" in result.checks[-1].detail

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

    def test_delete_patch_passes_all(self):
        gate = VerificationGate()
        patch = _make_patch(action="delete")
        result = gate.run("/tmp", "", patch)
        assert result.passed is True


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
