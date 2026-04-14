"""Tests for T02: V8 nondeterminism diagnostics enhancement."""
from __future__ import annotations

import json
import os
import tempfile
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
        "objective": {"subcategory_splits": splits, "total_cost": cost, "solve_time_ms": 100},
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
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
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

    runner.run_solver.side_effect = run_solver
    return runner


def _make_deterministic_runner(tmp_path: Path) -> MagicMock:
    """Runner that always returns the same objective."""
    runner = MagicMock()

    def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
        data = _solver_output_dict(splits=2, cost=6600)
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
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

    def test_v5_failure_saves_run_outputs(self, tmp_path: Path):
        """When metrics_dir is given, two JSON run files must be written."""
        canary = str(tmp_path / "canary.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary)
        metrics_dir = tmp_path / "metrics"
        metrics_dir.mkdir()
        runner = _make_nondeterministic_runner(tmp_path)

        r = check_nondeterminism(spec, runner, str(tmp_path), metrics_dir=str(metrics_dir))

        assert r.passed is False
        run_files = list(metrics_dir.glob("v8_run*.json"))
        assert len(run_files) == 2

    def test_v5_failure_archives_candidate_code(self, tmp_path: Path):
        """On failure, operators/ from workspace are archived to metrics_dir."""
        canary = str(tmp_path / "canary.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary)

        # Create a workspace with operators/
        workspace = tmp_path / "ws"
        (workspace / "operators").mkdir(parents=True)
        (workspace / "operators" / "my_op.py").write_text("class MyOp: pass\n")

        metrics_dir = tmp_path / "metrics"
        metrics_dir.mkdir()
        runner = _make_nondeterministic_runner(tmp_path)

        r = check_nondeterminism(spec, runner, str(workspace), metrics_dir=str(metrics_dir))

        assert r.passed is False
        detail = json.loads(r.detail)
        archive_ref = detail.get("candidate_archive_ref")
        assert archive_ref is not None
        assert Path(archive_ref).exists()

    def test_v5_no_metrics_dir_still_works(self, tmp_path: Path):
        """metrics_dir=None must not crash and check still returns result."""
        canary = str(tmp_path / "canary.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary)
        runner = _make_nondeterministic_runner(tmp_path)

        r = check_nondeterminism(spec, runner, str(tmp_path), metrics_dir=None)

        assert r.passed is False
        assert r.name == "V8_nondeterminism"
