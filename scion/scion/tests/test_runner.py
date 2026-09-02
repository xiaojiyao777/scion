"""Tests for LocalSubprocessRunner (T06)."""
from __future__ import annotations

import io
import json
import signal
import subprocess
import tempfile
import textwrap
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from scion.core.models import RunResult, SolverOutput
from scion.runtime.runner import ResourceLimits, Runner
from scion.runtime.subprocess_runner import (
    _SOLVER_WALL_CLOCK_GRACE_SEC,
    LocalSubprocessRunner,
    _build_clean_env,
)

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


def _tracked_mkstemp(root: Path):
    original = tempfile.mkstemp
    paths: list[Path] = []

    def create(*args, **kwargs):
        kwargs["dir"] = str(root)
        fd, path = original(*args, **kwargs)
        paths.append(Path(path))
        return fd, path

    return create, paths


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
        create, interchange_paths = _tracked_mkstemp(workdir)
        with patch(
            "scion.runtime.subprocess_runner.tempfile.mkstemp",
            side_effect=create,
        ):
            result = run(workdir)
        assert result.success is True
        assert result.exit_code == 0
        assert result.error_category is None
        assert result.output is not None
        assert result.output.feasible is True
        assert result.output.solution_payload == {"solution": {"items": ["a"]}}
        assert result.output.to_raw_mapping() == {
            "objective": {"cost": 1.0},
            "feasible": True,
            "runtime": {},
            "solution": {"items": ["a"]},
        }
        assert not hasattr(result, "output_path")
        assert len(interchange_paths) == 1
        assert not interchange_paths[0].exists()

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

    def test_new_child_progress_clears_previous_completion(self, workdir: Path):
        _write_solver(
            workdir,
            """\
            import argparse, json, pathlib
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed", "--time-limit", "--registry", "--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            pathlib.Path(args.output).write_text(json.dumps({
                "solution": {}, "objective": {}, "feasible": True,
            }))
            """,
        )
        current = {
            "child_pid": None,
            "child_phase": "solver_subprocess_complete",
            "child_exit_code": 7,
            "child_elapsed_ms": 123,
        }
        snapshots = []

        def merge_progress(**payload):
            current.update(payload)
            snapshots.append(dict(current))

        runner = LocalSubprocessRunner()
        runner.set_progress_callback(merge_progress)
        result = runner.run_solver(
            workdir=str(workdir),
            instance_path=str(workdir / "instance.json"),
            seed=42,
            time_limit_sec=5,
            registry_path=str(workdir / "registry.json"),
        )

        assert result.success is True
        child_start, child_complete = snapshots
        assert child_start["child_pid"] is not None
        assert child_start["child_phase"] == "solver_subprocess"
        assert child_start["child_exit_code"] is None
        assert child_start["child_elapsed_ms"] is None
        assert child_complete["child_pid"] is None
        assert child_complete["child_phase"] == "solver_subprocess_complete"
        assert child_complete["child_exit_code"] == 0
        assert child_complete["child_elapsed_ms"] >= 0

    def test_solver_output_reconstruction_is_stable_and_typed(self):
        output = SolverOutput(
            objective={"cost": 7},
            feasible=True,
            runtime={"iterations": 3},
            solution_payload={
                "zeta": 2,
                "objective": {"borrowed": True},
                "alpha": 1,
            },
        )

        raw = output.to_raw_mapping()

        assert list(raw) == [
            "objective",
            "feasible",
            "runtime",
            "alpha",
            "zeta",
        ]
        assert raw["objective"] == {"cost": 7}
        assert raw["feasible"] is True
        assert raw["runtime"] == {"iterations": 3}

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
        assert result.output is None

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

    @pytest.mark.parametrize(
        ("body", "detail"),
        [
            ("pathlib.Path(args.output).write_text('{broken')", "parse error"),
            ("pathlib.Path(args.output).write_text('[]')", "must be an object"),
            ("pathlib.Path(args.output).unlink()", "No such file"),
        ],
    )
    def test_successful_process_with_unusable_output_is_crash(
        self,
        workdir: Path,
        body: str,
        detail: str,
    ):
        _write_solver(
            workdir,
            f"""\
            import argparse, pathlib
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed", "--time-limit", "--registry", "--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            {body}
            """,
        )
        create, interchange_paths = _tracked_mkstemp(workdir)
        with patch(
            "scion.runtime.subprocess_runner.tempfile.mkstemp",
            side_effect=create,
        ):
            result = run(workdir)

        assert result.success is False
        assert result.error_category == "crash"
        assert result.output is None
        assert detail in result.stderr
        assert interchange_paths and not interchange_paths[0].exists()

    def test_unreadable_output_is_crash_and_cleaned(self, workdir: Path):
        _write_solver(
            workdir,
            """\
            import argparse, json, pathlib
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed", "--time-limit", "--registry", "--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            pathlib.Path(args.output).write_text(json.dumps({
                "objective": {}, "feasible": True, "runtime": {},
            }))
            """,
        )
        create, interchange_paths = _tracked_mkstemp(workdir)
        real_open = open

        def guarded_open(path, *args, **kwargs):
            if str(path).endswith(".json") and "scion_run_" in str(path):
                raise PermissionError("interchange unreadable")
            return real_open(path, *args, **kwargs)

        with (
            patch(
                "scion.runtime.subprocess_runner.tempfile.mkstemp",
                side_effect=create,
            ),
            patch("builtins.open", side_effect=guarded_open),
        ):
            result = run(workdir)

        assert result.success is False
        assert result.output is None
        assert result.error_category == "crash"
        assert "interchange unreadable" in result.stderr
        assert interchange_paths and not interchange_paths[0].exists()

    @pytest.mark.parametrize(
        ("popen_error", "category"),
        [(OSError("popen failed"), "crash"), (MemoryError(), "oom")],
    )
    def test_popen_failure_leaves_no_interchange_file(
        self,
        workdir: Path,
        popen_error: BaseException,
        category: str,
    ):
        _write_solver(workdir, "raise AssertionError('Popen is mocked')")
        create, interchange_paths = _tracked_mkstemp(workdir)
        with (
            patch(
                "scion.runtime.subprocess_runner.tempfile.mkstemp",
                side_effect=create,
            ),
            patch(
                "scion.runtime.subprocess_runner.subprocess.Popen",
                side_effect=popen_error,
            ),
        ):
            result = run(workdir)

        assert result.success is False
        assert result.error_category == category
        assert result.output is None
        assert interchange_paths and not interchange_paths[0].exists()

    def test_base_exception_kills_child_rethrows_and_cleans(self, workdir: Path):
        _write_solver(workdir, "raise AssertionError('Popen is mocked')")
        proc = _FakeTimeoutProc([KeyboardInterrupt()], returncode=None)
        runner = LocalSubprocessRunner()
        create, interchange_paths = _tracked_mkstemp(workdir)

        with (
            patch(
                "scion.runtime.subprocess_runner.tempfile.mkstemp",
                side_effect=create,
            ),
            patch(
                "scion.runtime.subprocess_runner.subprocess.Popen",
                return_value=proc,
            ),
            patch("scion.runtime.subprocess_runner._kill_proc") as kill_proc,
            pytest.raises(KeyboardInterrupt),
        ):
            runner.run_solver(
                workdir=str(workdir),
                instance_path=str(workdir / "instance.json"),
                seed=42,
                time_limit_sec=5,
                registry_path=str(workdir / "registry.json"),
            )

        kill_proc.assert_called_once_with(proc)
        assert runner._active_procs == set()
        assert interchange_paths and not interchange_paths[0].exists()

    def test_communicate_return_with_live_child_kills_and_cleans(
        self,
        workdir: Path,
    ):
        _write_solver(workdir, "raise AssertionError('Popen is mocked')")
        proc = _FakeTimeoutProc([(b"partial", b"")], returncode=None)
        create, interchange_paths = _tracked_mkstemp(workdir)

        with (
            patch(
                "scion.runtime.subprocess_runner.tempfile.mkstemp",
                side_effect=create,
            ),
            patch(
                "scion.runtime.subprocess_runner.subprocess.Popen",
                return_value=proc,
            ),
            patch("scion.runtime.subprocess_runner._kill_proc") as kill_proc,
        ):
            result = run(workdir)

        kill_proc.assert_called_once_with(proc)
        assert result.success is False
        assert result.exit_code == -signal.SIGKILL
        assert result.error_category == "oom"
        assert result.output is None
        assert interchange_paths and not interchange_paths[0].exists()

    def test_memory_error_after_popen_kills_child_and_cleans(self, workdir: Path):
        _write_solver(workdir, "raise AssertionError('Popen is mocked')")
        proc = _FakeTimeoutProc([MemoryError()], returncode=None)
        create, interchange_paths = _tracked_mkstemp(workdir)

        with (
            patch(
                "scion.runtime.subprocess_runner.tempfile.mkstemp",
                side_effect=create,
            ),
            patch(
                "scion.runtime.subprocess_runner.subprocess.Popen",
                return_value=proc,
            ),
            patch("scion.runtime.subprocess_runner._kill_proc") as kill_proc,
        ):
            result = run(workdir)

        kill_proc.assert_called_once_with(proc)
        assert result.success is False
        assert result.error_category == "oom"
        assert result.output is None
        assert interchange_paths and not interchange_paths[0].exists()

    def test_already_removed_interchange_is_silent(self, workdir: Path, caplog):
        _write_solver(
            workdir,
            """\
            import argparse, json, pathlib
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed", "--time-limit", "--registry", "--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            pathlib.Path(args.output).write_text(json.dumps({
                "objective": {}, "feasible": True, "runtime": {},
            }))
            """,
        )
        create, interchange_paths = _tracked_mkstemp(workdir)
        real_load = json.load

        def load_then_remove(handle):
            raw = real_load(handle)
            Path(handle.name).unlink()
            return raw

        with (
            patch(
                "scion.runtime.subprocess_runner.tempfile.mkstemp",
                side_effect=create,
            ),
            patch(
                "scion.runtime.subprocess_runner.json.load",
                side_effect=load_then_remove,
            ),
        ):
            result = run(workdir)

        assert result.success is True
        assert result.output is not None
        assert interchange_paths and not interchange_paths[0].exists()
        assert "Failed to remove runner-owned" not in caplog.text

    def test_unlink_error_warns_without_replacing_success(
        self,
        workdir: Path,
        caplog,
    ):
        _write_solver(
            workdir,
            """\
            import argparse, json, pathlib
            p = argparse.ArgumentParser()
            p.add_argument("instance", nargs="?", default="")
            for name in ["--seed", "--time-limit", "--registry", "--output"]:
                p.add_argument(name, default="")
            args = p.parse_args()
            pathlib.Path(args.output).write_text(json.dumps({
                "objective": {"cost": 1}, "feasible": True, "runtime": {},
            }))
            """,
        )
        create, interchange_paths = _tracked_mkstemp(workdir)
        with (
            patch(
                "scion.runtime.subprocess_runner.tempfile.mkstemp",
                side_effect=create,
            ),
            patch(
                "scion.runtime.subprocess_runner.os.unlink",
                side_effect=PermissionError("unlink denied"),
            ),
        ):
            result = run(workdir)

        assert result.success is True
        assert result.output is not None
        assert "Failed to remove runner-owned" in caplog.text
        assert "unlink denied" in caplog.text
        assert interchange_paths and interchange_paths[0].exists()
        interchange_paths[0].unlink()

    def test_unlink_error_warns_without_replacing_base_exception(
        self,
        workdir: Path,
        caplog,
    ):
        _write_solver(workdir, "raise AssertionError('Popen is mocked')")
        proc = _FakeTimeoutProc([KeyboardInterrupt()], returncode=None)
        create, interchange_paths = _tracked_mkstemp(workdir)

        with (
            patch(
                "scion.runtime.subprocess_runner.tempfile.mkstemp",
                side_effect=create,
            ),
            patch(
                "scion.runtime.subprocess_runner.subprocess.Popen",
                return_value=proc,
            ),
            patch("scion.runtime.subprocess_runner._kill_proc"),
            patch(
                "scion.runtime.subprocess_runner.os.unlink",
                side_effect=PermissionError("unlink denied"),
            ),
            pytest.raises(KeyboardInterrupt),
        ):
            run(workdir)

        assert "Failed to remove runner-owned" in caplog.text
        assert "unlink denied" in caplog.text
        assert interchange_paths and interchange_paths[0].exists()
        interchange_paths[0].unlink()


# ---------------------------------------------------------------------------
# Tests: timeout
# ---------------------------------------------------------------------------


class TestRunnerTimeout:
    def test_timeout_is_detected(self, workdir: Path):
        _write_solver(workdir, "import time; time.sleep(9999)")
        limits = ResourceLimits(timeout_sec=1)
        create, interchange_paths = _tracked_mkstemp(workdir)
        with patch(
            "scion.runtime.subprocess_runner.tempfile.mkstemp",
            side_effect=create,
        ):
            result = run(workdir, limits=limits)
        assert result.success is False
        assert result.error_category == "timeout"
        assert result.output is None
        assert interchange_paths and not interchange_paths[0].exists()

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
        assert result.output is not None

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
        assert result.output is None
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
        assert result.output is None
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

    def test_concurrent_runs_leave_zero_owned_files(self, workdir: Path):
        _write_solver(workdir, "raise AssertionError('Popen is mocked')")
        runner = LocalSubprocessRunner()
        create, interchange_paths = _tracked_mkstemp(workdir)

        def popen(cmd, **kwargs):
            output_index = cmd.index("--output") + 1
            Path(cmd[output_index]).write_text(
                '{"objective":{"cost":1},"feasible":true,"runtime":{},"solution":{}}',
                encoding="utf-8",
            )
            return _FakeTimeoutProc([(b"", b"")], returncode=0)

        def invoke(seed: int) -> RunResult:
            return runner.run_solver(
                workdir=str(workdir),
                instance_path=str(workdir / "instance.json"),
                seed=seed,
                time_limit_sec=5,
                registry_path=str(workdir / "registry.json"),
            )

        with (
            patch(
                "scion.runtime.subprocess_runner.tempfile.mkstemp",
                side_effect=create,
            ),
            patch(
                "scion.runtime.subprocess_runner.subprocess.Popen",
                side_effect=popen,
            ),
            ThreadPoolExecutor(max_workers=4) as pool,
        ):
            results = list(pool.map(invoke, range(12)))

        assert all(result.success and result.output is not None for result in results)
        assert len(interchange_paths) == 12
        assert all(not path.exists() for path in interchange_paths)
        assert runner._active_procs == set()

    def test_concurrent_run_cleanup_never_removes_another_runs_file(
        self,
        workdir: Path,
    ):
        _write_solver(workdir, "raise AssertionError('Popen is mocked')")
        runner = LocalSubprocessRunner()
        create, interchange_paths = _tracked_mkstemp(workdir)
        first_started = threading.Event()
        release_first = threading.Event()
        popen_count = 0
        popen_lock = threading.Lock()

        class BlockingProc(_FakeTimeoutProc):
            def communicate(self, timeout=None):
                self.communicate_timeouts.append(timeout)
                first_started.set()
                assert release_first.wait(timeout=5)
                return b"", b""

        def popen(cmd, **kwargs):
            nonlocal popen_count
            output_index = cmd.index("--output") + 1
            Path(cmd[output_index]).write_text(
                '{"objective":{"cost":1},"feasible":true,"runtime":{},"solution":{}}',
                encoding="utf-8",
            )
            with popen_lock:
                popen_count += 1
                call_number = popen_count
            if call_number == 1:
                return BlockingProc([], returncode=0)
            return _FakeTimeoutProc([(b"", b"")], returncode=0)

        def invoke(seed: int) -> RunResult:
            return runner.run_solver(
                workdir=str(workdir),
                instance_path=str(workdir / "instance.json"),
                seed=seed,
                time_limit_sec=5,
                registry_path=str(workdir / "registry.json"),
            )

        with (
            patch(
                "scion.runtime.subprocess_runner.tempfile.mkstemp",
                side_effect=create,
            ),
            patch(
                "scion.runtime.subprocess_runner.subprocess.Popen",
                side_effect=popen,
            ),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            first_future = pool.submit(invoke, 1)
            assert first_started.wait(timeout=5)
            second_result = invoke(2)
            assert second_result.success is True
            assert len(interchange_paths) == 2
            assert interchange_paths[0].exists()
            assert not interchange_paths[1].exists()
            release_first.set()
            first_result = first_future.result(timeout=5)

        assert first_result.success is True
        assert all(not path.exists() for path in interchange_paths)
        assert runner._active_procs == set()


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
