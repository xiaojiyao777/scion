"""Tests for T02: V8 nondeterminism diagnostics enhancement."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.models import RunResult, SolverOutput
from scion.verification.nondeterminism import check_nondeterminism


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(canary: str) -> ProblemSpec:
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
        "vehicles": {"V0": {"vehicle_id": "V0", "cost": cost}},
        "assignment": {"O1": "V0"},
        "objective": {
            "subcategory_splits": splits,
            "total_cost": cost,
            "solve_time_ms": 100,
        },
        "feasible": True,
    }


def _make_nondeterministic_runner(tmp_path: Path) -> MagicMock:
    """Runner that returns different objectives on call 1 vs call 2."""
    call_count = [0]
    runner = MagicMock()

    def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
        call_count[0] += 1
        splits = 2 if call_count[0] == 1 else 5
        data = _solver_output_dict(splits=splits)
        sol = SolverOutput(
            objective=data["objective"],
            feasible=True,
            solution_payload={
                key: value
                for key, value in data.items()
                if key not in {"objective", "feasible", "runtime"}
            },
        )
        return RunResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            elapsed_ms=100,
            output=sol,
            error_category=None,
        )

    runner.run_solver.side_effect = run_solver
    return runner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStateleakDiagnostics:
    def test_v5_failure_detail_is_structured_json(self, tmp_path: Path):
        """On failure, detail must be valid JSON with diff_keys."""
        canary = str(tmp_path / "canary.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary)
        runner = _make_nondeterministic_runner(tmp_path)

        r = check_nondeterminism(spec, runner, str(tmp_path))

        assert r.passed is False
        # detail must be valid JSON
        detail = json.loads(r.detail)
        assert "diff_keys" in detail
        assert isinstance(detail["diff_keys"], list)
        assert len(detail["diff_keys"]) > 0

    def test_v8_failure_detail_caps_diff_keys_and_never_embeds_objectives(
        self,
        tmp_path: Path,
    ) -> None:
        canary = str(tmp_path / "canary.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary)
        call_count = [0]
        runner = MagicMock()

        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            call_count[0] += 1
            marker = (
                "first-objective-secret"
                if call_count[0] == 1
                else ("second-objective-secret")
            )
            objective = {
                f"metric_{index:03d}": f"{marker}-{index}" for index in range(100)
            }
            return RunResult(
                success=True,
                exit_code=0,
                stdout="",
                stderr="",
                elapsed_ms=100,
                output=SolverOutput(objective=objective, feasible=True),
                error_category=None,
            )

        runner.run_solver.side_effect = run_solver

        result = check_nondeterminism(spec, runner, str(tmp_path))

        assert result.passed is False
        detail = json.loads(result.detail)
        assert len(detail["diff_keys"]) == 32
        assert all(len(key) <= 128 for key in detail["diff_keys"])
        assert "run1_objective" not in detail
        assert "run2_objective" not in detail
        assert len(detail["run1_objective_digest"]) == 16
        assert len(detail["run2_objective_digest"]) == 16
        assert "first-objective-secret" not in result.detail
        assert "second-objective-secret" not in result.detail
        assert len(result.detail.encode("utf-8")) <= 8 * 1024

    def test_v8_failure_writes_one_bounded_diagnostic(self, tmp_path: Path):
        canary = str(tmp_path / "canary.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary)
        metrics_dir = tmp_path / "metrics"
        metrics_dir.mkdir()
        runner = _make_nondeterministic_runner(tmp_path)

        r = check_nondeterminism(
            spec, runner, str(tmp_path), metrics_dir=str(metrics_dir)
        )

        assert r.passed is False
        diagnostics = list(metrics_dir.glob("v8_failure_*.json"))
        assert len(diagnostics) == 1
        assert diagnostics[0].stat().st_size <= 8 * 1024
        assert json.loads(diagnostics[0].read_text(encoding="utf-8")) == json.loads(
            r.detail
        )
        assert r.metadata == {"diagnostic_ref": str(diagnostics[0])}
        assert "run1_ref" not in r.detail
        assert "run2_ref" not in r.detail

    def test_v8_success_writes_no_diagnostic_even_with_large_runtime(
        self,
        tmp_path: Path,
    ) -> None:
        canary = str(tmp_path / "canary.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary)
        metrics_dir = tmp_path / "metrics"
        metrics_dir.mkdir()
        call_count = [0]
        runner = MagicMock()

        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            call_count[0] += 1
            size = 1 if call_count[0] == 1 else 10_000
            runtime = {
                "solver_algorithm_alns_iteration_trace": ["trace-secret"] * size,
            }
            return RunResult(
                success=True,
                exit_code=0,
                stdout="",
                stderr="",
                elapsed_ms=100,
                output=SolverOutput(
                    objective={"total_cost": 6600},
                    feasible=True,
                    runtime=runtime,
                    solution_payload={"routes": [["solution-secret"]] * size},
                ),
                error_category=None,
            )

        runner.run_solver.side_effect = run_solver

        result = check_nondeterminism(
            spec,
            runner,
            str(tmp_path),
            metrics_dir=str(metrics_dir),
        )

        assert result.passed is True
        assert not list(metrics_dir.iterdir())
        assert "diagnostic_ref" not in result.metadata

    def test_v5_no_metrics_dir_still_works(self, tmp_path: Path):
        """metrics_dir=None must not crash and check still returns result."""
        canary = str(tmp_path / "canary.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary)
        runner = _make_nondeterministic_runner(tmp_path)

        r = check_nondeterminism(spec, runner, str(tmp_path), metrics_dir=None)

        assert r.passed is False
        assert r.name == "V8_nondeterminism"

    def test_v8_diagnostic_persistence_failure_does_not_change_result(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        canary = str(tmp_path / "canary.json")
        Path(canary).write_text("{}")
        metrics_dir = tmp_path / "metrics"
        metrics_dir.mkdir()
        baseline = check_nondeterminism(
            _make_spec(canary),
            _make_nondeterministic_runner(tmp_path),
            str(tmp_path),
        )

        from scion.verification import nondeterminism

        def fail_publish(source, target):
            raise OSError("diagnostic publish failed")

        monkeypatch.setattr(nondeterminism.os, "replace", fail_publish)

        result = check_nondeterminism(
            _make_spec(canary),
            _make_nondeterministic_runner(tmp_path),
            str(tmp_path),
            metrics_dir=str(metrics_dir),
        )

        assert result.passed is baseline.passed is False
        assert result.detail == baseline.detail
        assert (
            "diagnostic publish failed"
            in result.metadata["diagnostic_persistence_error"]
        )
        assert not list(metrics_dir.iterdir())
