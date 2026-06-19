"""Tests for LocalSubprocessRunner (T06)."""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from scion.runtime.runner import ResourceLimits, Runner
from scion.runtime.subprocess_runner import (
    LocalSubprocessRunner,
    _SOLVER_WALL_CLOCK_GRACE_SEC,
    _build_clean_env,
)
from scion.core.models import RunResult


# ---------------------------------------------------------------------------
# Fixture: minimal fake solver scripts
# ---------------------------------------------------------------------------


def _write_solver(workdir: Path, script: str) -> None:
    """Write a solver.py to workdir."""
    (workdir / "solver.py").write_text(textwrap.dedent(script))


@pytest.fixture()
def workdir(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def run(workdir: Path, limits: ResourceLimits | None = None) -> RunResult:
    runner = LocalSubprocessRunner(limits=limits)
    # dummy paths — the fake solvers don't actually read them
    return runner.run_solver(
        workdir=str(workdir),
        instance_path=str(workdir / "instance.json"),
        seed=42,
        time_limit_sec=5,
        registry_path=str(workdir / "registry.json"),
    )


class _FakeTimeoutProc:
    def __init__(self, communicate_results, *, returncode):
        self.pid = 12345
        self.returncode = returncode
        self.stdout = io.BytesIO()
        self.stderr = io.BytesIO()
        self._communicate_results = list(communicate_results)
        self.communicate_timeouts = []

    def communicate(self, timeout=None):
        self.communicate_timeouts.append(timeout)
        result = self._communicate_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


# ---------------------------------------------------------------------------
# Tests: success
# ---------------------------------------------------------------------------


class TestRunnerSuccess:
    def test_success_exit_zero(self, workdir: Path):
        _write_solver(
            workdir,
            """\
            import sys, json, argparse
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default=""); p.add_argument("--seed"); p.add_argument("--time-limit")
            p.add_argument("--registry"); p.add_argument("--output")
            args = p.parse_args()
            result = {
                "feasible": True,
                "objective": {"cost": 1.0},
                "solution": {"items": ["a"]},
            }
            if args.output:
                import pathlib
                pathlib.Path(args.output).write_text(json.dumps(result))
            sys.exit(0)
            """,
        )
        result = run(workdir)
        assert result.success is True
        assert result.exit_code == 0
        assert result.error_category is None
        assert result.output is not None
        assert result.output.feasible is True
        assert result.output.solution_payload == {"solution": {"items": ["a"]}}
        assert result.output_path is not None
        assert Path(result.output_path).exists()

    def test_elapsed_ms_positive(self, workdir: Path):
        _write_solver(
            workdir,
            """\
            import sys, json, argparse
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed","--time-limit","--registry","--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            with open(args.output, 'w') as f:
                json.dump({"solution":{},"objective":{},"feasible":True}, f)
            sys.exit(0)
            """,
        )
        result = run(workdir)
        assert result.elapsed_ms >= 0

    def test_stdout_captured(self, workdir: Path):
        _write_solver(
            workdir,
            """\
            import sys, json, argparse
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed","--time-limit","--registry","--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            print("hello solver")
            with open(args.output, 'w') as f:
                json.dump({"solution":{},"objective":{},"feasible":True}, f)
            sys.exit(0)
            """,
        )
        result = run(workdir)
        assert "hello solver" in result.stdout

    def test_runner_satisfies_protocol(self):
        runner = LocalSubprocessRunner()
        assert isinstance(runner, Runner)

    def test_relative_pythonpath_is_resolved_before_child_cwd_switch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        parent_cwd = tmp_path / "parent"
        workspace = tmp_path / "workspace"
        package_dir = parent_cwd / "relpkg"
        parent_cwd.mkdir()
        workspace.mkdir()
        package_dir.mkdir()
        (package_dir / "solver_marker.py").write_text(
            "VALUE = 'current-checkout-marker'\n",
            encoding="utf-8",
        )
        _write_solver(
            workspace,
            """\
            import argparse, json, pathlib
            import solver_marker
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed", "--time-limit", "--registry", "--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            pathlib.Path(args.output).write_text(json.dumps({
                "feasible": True,
                "objective": {"marker": solver_marker.VALUE},
                "solution": {},
            }))
            """,
        )
        monkeypatch.chdir(parent_cwd)
        monkeypatch.setenv("PYTHONPATH", "relpkg")

        result = run(workspace)

        assert result.success is True
        assert result.output is not None
        assert result.output.objective["marker"] == "current-checkout-marker"


# ---------------------------------------------------------------------------
# Tests: crash
# ---------------------------------------------------------------------------


class TestRunnerCrash:
    def test_nonzero_exit_is_crash(self, workdir: Path):
        _write_solver(workdir, "import sys; sys.exit(1)")
        result = run(workdir)
        assert result.success is False
        assert result.exit_code == 1
        assert result.error_category == "crash"
        assert result.output_path is None

    def test_exception_in_solver_is_crash(self, workdir: Path):
        _write_solver(workdir, "raise RuntimeError('boom')")
        result = run(workdir)
        assert result.success is False
        assert result.error_category == "crash"

    def test_stderr_captured_on_crash(self, workdir: Path):
        _write_solver(
            workdir,
            """\
            import sys
            print("err msg", file=sys.stderr)
            sys.exit(2)
            """,
        )
        result = run(workdir)
        assert "err msg" in result.stderr


# ---------------------------------------------------------------------------
# Tests: timeout
# ---------------------------------------------------------------------------


class TestRunnerTimeout:
    def test_timeout_is_detected(self, workdir: Path):
        _write_solver(workdir, "import time; time.sleep(9999)")
        limits = ResourceLimits(timeout_sec=1)
        result = run(workdir, limits=limits)
        assert result.success is False
        assert result.error_category == "timeout"
        assert result.output_path is None

    def test_timeout_elapsed_reasonable(self, workdir: Path):
        _write_solver(workdir, "import time; time.sleep(9999)")
        limits = ResourceLimits(timeout_sec=1)
        result = run(workdir, limits=limits)
        # Should finish not too long after the 1 s timeout
        assert result.elapsed_ms < 10_000  # <10 s

    def test_per_call_time_limit_is_enforced(self, workdir: Path):
        _write_solver(workdir, "import time; time.sleep(9999)")
        runner = LocalSubprocessRunner(limits=ResourceLimits(timeout_sec=30))
        result = runner.run_solver(
            workdir=str(workdir),
            instance_path=str(workdir / "instance.json"),
            seed=42,
            time_limit_sec=1,
            registry_path=str(workdir / "registry.json"),
        )
        assert result.success is False
        assert result.error_category == "timeout"
        assert result.elapsed_ms < (_SOLVER_WALL_CLOCK_GRACE_SEC + 5) * 1000

    def test_per_call_time_limit_allows_output_flush_grace(self, workdir: Path):
        _write_solver(
            workdir,
            """\
            import argparse, json, pathlib, time
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed", "--time-limit", "--registry", "--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            time.sleep(1.2)
            pathlib.Path(args.output).write_text(json.dumps({
                "feasible": True,
                "objective": {"cost": 1.0},
                "solution": {},
            }))
            """,
        )
        runner = LocalSubprocessRunner(limits=ResourceLimits(timeout_sec=30))
        result = runner.run_solver(
            workdir=str(workdir),
            instance_path=str(workdir / "instance.json"),
            seed=42,
            time_limit_sec=1,
            registry_path=str(workdir / "registry.json"),
        )
        assert result.success is True
        assert result.output_path is not None

    def test_timeout_drain_is_bounded_when_pipes_do_not_close(self, workdir: Path):
        _write_solver(workdir, "raise AssertionError('Popen is mocked')")
        proc = _FakeTimeoutProc(
            [
                subprocess.TimeoutExpired(
                    cmd="solver",
                    timeout=1,
                    output=b"partial stdout",
                    stderr=b"partial stderr",
                ),
                subprocess.TimeoutExpired(cmd="solver", timeout=1),
            ],
            returncode=None,
        )

        with (
            patch("scion.runtime.subprocess_runner.subprocess.Popen", return_value=proc),
            patch("scion.runtime.subprocess_runner._kill_proc") as kill_proc,
        ):
            result = run(workdir, limits=ResourceLimits(timeout_sec=1))

        assert result.success is False
        assert result.error_category == "timeout"
        assert result.exit_code == -9
        assert result.output_path is None
        assert "partial stdout" in result.stdout
        assert "partial stderr" in result.stderr
        assert "stdout/stderr drain did not finish within" in result.stderr
        assert proc.communicate_timeouts == [1, 1]
        assert proc.stdout.closed is True
        assert proc.stderr.closed is True
        kill_proc.assert_called_once_with(proc)

    def test_timeout_cleanup_preserves_drained_stdout_and_stderr(self, workdir: Path):
        _write_solver(workdir, "raise AssertionError('Popen is mocked')")
        proc = _FakeTimeoutProc(
            [
                subprocess.TimeoutExpired(cmd="solver", timeout=1),
                (b"final stdout tail", b"final stderr tail"),
            ],
            returncode=-9,
        )

        with (
            patch("scion.runtime.subprocess_runner.subprocess.Popen", return_value=proc),
            patch("scion.runtime.subprocess_runner._kill_proc") as kill_proc,
        ):
            result = run(workdir, limits=ResourceLimits(timeout_sec=1))

        assert result.success is False
        assert result.error_category == "timeout"
        assert result.exit_code == -9
        assert result.output_path is None
        assert result.stdout == "final stdout tail"
        assert result.stderr == "final stderr tail"
        assert "stdout/stderr drain did not finish within" not in result.stderr
        assert proc.communicate_timeouts == [1, 1]
        kill_proc.assert_called_once_with(proc)

    def test_terminate_active_processes_kills_registered_solver(self):
        runner = LocalSubprocessRunner()
        proc = _FakeTimeoutProc([], returncode=None)

        runner._register_proc(proc)  # type: ignore[arg-type]
        with patch("scion.runtime.subprocess_runner._kill_proc") as kill_proc:
            terminated = runner.terminate_active_processes(reason="final_wait_timeout")

        assert terminated == 1
        kill_proc.assert_called_once_with(proc)


# ---------------------------------------------------------------------------
# Tests: ResourceLimits dataclass
# ---------------------------------------------------------------------------


class TestResourceLimits:
    def test_defaults(self):
        limits = ResourceLimits()
        assert limits.timeout_sec == 300
        assert limits.memory_mb == 4096
        assert limits.max_file_descriptors == 256

    def test_custom(self):
        limits = ResourceLimits(timeout_sec=60, memory_mb=512)
        assert limits.timeout_sec == 60
        assert limits.memory_mb == 512


# ---------------------------------------------------------------------------
# Tests: environment sanitization
# ---------------------------------------------------------------------------


class TestEnvSanitization:
    def test_only_whitelisted_environment_visible(self, workdir: Path, monkeypatch):
        monkeypatch.setenv("SECRET_TOKEN", "hunter2")
        monkeypatch.setenv("SCION_PROBLEM_DATA_ROOT", "/tmp/scion-problem-data")
        _write_solver(
            workdir,
            """\
            import os, sys, json, argparse
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed","--time-limit","--registry","--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            if "SECRET_TOKEN" in os.environ:
                print("LEAKED", file=sys.stderr)
                sys.exit(1)
            if os.environ.get("SCION_PROBLEM_DATA_ROOT") != "/tmp/scion-problem-data":
                print("MISSING_DATA_ROOT", file=sys.stderr)
                sys.exit(2)
            with open(args.output, 'w') as f:
                json.dump({"solution":{},"objective":{},"feasible":True}, f)
            sys.exit(0)
            """,
        )
        result = run(workdir)
        assert result.success is True
        assert "LEAKED" not in result.stderr

    def test_selected_surface_is_passed_to_child(self, workdir: Path):
        _write_solver(
            workdir,
            """\
            import os, sys, json, argparse
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed","--time-limit","--registry","--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            if os.environ.get("SCION_SELECTED_SURFACE") != "solver_design":
                print("MISSING_SELECTED_SURFACE", file=sys.stderr)
                sys.exit(1)
            with open(args.output, 'w') as f:
                json.dump({"solution":{},"objective":{},"feasible":True}, f)
            sys.exit(0)
            """,
        )
        runner = LocalSubprocessRunner()
        result = runner.run_solver(
            workdir=str(workdir),
            instance_path=str(workdir / "instance.json"),
            seed=42,
            time_limit_sec=5,
            registry_path=str(workdir / "registry.json"),
            selected_surface="solver_design",
        )
        assert result.success is True

    def test_unselected_surface_clears_parent_env(self, workdir: Path, monkeypatch):
        monkeypatch.setenv("SCION_SELECTED_SURFACE", "stale_surface")
        _write_solver(
            workdir,
            """\
            import os, sys, json, argparse
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed","--time-limit","--registry","--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            if "SCION_SELECTED_SURFACE" in os.environ:
                print("LEAKED_SELECTED_SURFACE", file=sys.stderr)
                sys.exit(1)
            with open(args.output, 'w') as f:
                json.dump({"solution":{},"objective":{},"feasible":True}, f)
            sys.exit(0)
            """,
        )
        result = run(workdir)
        assert result.success is True


# ---------------------------------------------------------------------------
# Tests: _build_clean_env (T01)
# ---------------------------------------------------------------------------


class TestBuildCleanEnv:
    def test_build_clean_env_contains_pythonhashseed(self, monkeypatch):
        env = _build_clean_env()
        assert "PYTHONHASHSEED" in env
        assert env["PYTHONHASHSEED"] == "0"

    def test_build_clean_env_fixed_overrides_system(self, monkeypatch):
        monkeypatch.setenv("PYTHONHASHSEED", "42")
        env = _build_clean_env()
        assert env["PYTHONHASHSEED"] == "0"

    def test_build_clean_env_excludes_other_vars(self, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "abc")
        env = _build_clean_env()
        assert "MY_SECRET" not in env

    def test_build_clean_env_allows_scion_problem_runtime_vars(self, monkeypatch):
        monkeypatch.setenv("SCION_PROBLEM_DATA_ROOT", "/tmp/scion-problem-data")
        env = _build_clean_env()
        assert env["SCION_PROBLEM_DATA_ROOT"] == "/tmp/scion-problem-data"
