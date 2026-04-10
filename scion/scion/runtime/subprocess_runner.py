"""LocalSubprocessRunner: MVP implementation using subprocess + resource limits."""
from __future__ import annotations

import json
import os
import resource
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from scion.core.models import RunResult, SolverOutput
from scion.runtime.runner import ResourceLimits


# Environment variables passed through to the subprocess (whitelist)
_ENV_PASSTHROUGH = {"PATH", "PYTHONPATH"}
_ENV_FIXED = {"PYTHONHASHSEED": "0"}


def _build_clean_env() -> dict[str, str]:
    """Return a sanitized environment containing only whitelisted variables."""
    env = {k: v for k, v in os.environ.items() if k in _ENV_PASSTHROUGH}
    env.update(_ENV_FIXED)
    return env


def _make_preexec_fn(limits: ResourceLimits):
    """Return a pre-exec callable that applies resource limits in the child process."""

    def _preexec():
        # New session so killpg targets only the child tree
        os.setsid()

        # CPU time hard + soft limit (seconds)
        cpu_limit = limits.timeout_sec + 10  # small grace period above wall-clock
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))

        # Virtual memory limit
        mem_bytes = limits.memory_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except ValueError:
            # Some platforms don't support RLIMIT_AS — use DATA as fallback
            try:
                resource.setrlimit(resource.RLIMIT_DATA, (mem_bytes, mem_bytes))
            except (ValueError, resource.error):
                pass

        # File descriptor limit
        try:
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (limits.max_file_descriptors, limits.max_file_descriptors),
            )
        except (ValueError, resource.error):
            pass

    return _preexec


class LocalSubprocessRunner:
    """Runs solver.py in a local subprocess with resource limits and env sanitization.

    Conforms to the Runner Protocol.
    """

    def __init__(self, limits: Optional[ResourceLimits] = None) -> None:
        self._limits = limits or ResourceLimits()

    def run_solver(
        self,
        workdir: str,
        instance_path: str,
        seed: int,
        time_limit_sec: int,
        registry_path: str,
    ) -> RunResult:
        """Execute solver.py in an isolated subprocess.

        Command constructed:
            python solver.py --instance <path> --seed <seed>
                             --time-limit <sec> --registry <path>
                             --output <tmpfile>

        Returns RunResult.  output_path points to the solver's output JSON when
        the process exits with code 0; it is a temp file that the caller is
        responsible for reading and deleting.
        """
        solver_path = Path(workdir) / "solver.py"
        python_exe = sys.executable

        # Create a temporary output file so the solver can write results
        out_fd, out_path = tempfile.mkstemp(suffix=".json", prefix="scion_run_")
        os.close(out_fd)

        cmd = [
            python_exe,
            str(solver_path),
            str(instance_path),
            "--seed", str(seed),
            "--time-limit", str(time_limit_sec),
            "--registry", str(registry_path),
            "--output", out_path,
        ]

        env = _build_clean_env()
        # Ensure the workspace itself is on PYTHONPATH so operators can be imported
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (workdir + os.pathsep + existing_pp).rstrip(os.pathsep)

        start_ns = time.monotonic_ns()
        error_category: Optional[str] = None
        proc: Optional[subprocess.Popen] = None

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=workdir,
                env=env,
                preexec_fn=_make_preexec_fn(self._limits),
            )

            try:
                stdout_bytes, stderr_bytes = proc.communicate(
                    timeout=self._limits.timeout_sec
                )
            except subprocess.TimeoutExpired:
                # Hard-kill the whole process group
                _kill_proc(proc)
                stdout_bytes, stderr_bytes = proc.communicate()
                error_category = "timeout"

        except MemoryError:
            if proc is not None:
                _kill_proc(proc)
            elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
            _try_remove(out_path)
            return RunResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="MemoryError in runner",
                elapsed_ms=elapsed_ms,
                output_path=None,
                error_category="oom",
            )
        except Exception as exc:
            if proc is not None:
                _kill_proc(proc)
            elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
            _try_remove(out_path)
            return RunResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                elapsed_ms=elapsed_ms,
                output_path=None,
                error_category="crash",
            )

        elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)

        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        stderr_str = stderr_bytes.decode("utf-8", errors="replace")

        exit_code = proc.returncode

        # Classify non-zero exits
        if error_category is None and exit_code != 0:
            # OOM: returncode -9 (SIGKILL) and stderr hints
            if exit_code in (-9, -signal.SIGKILL) or "MemoryError" in stderr_str:
                error_category = "oom"
            else:
                error_category = "crash"

        success = exit_code == 0 and error_category is None

        # Parse solver output JSON if successful
        solver_output: Optional[SolverOutput] = None
        if success and out_path and os.path.exists(out_path):
            try:
                with open(out_path, 'r') as f:
                    raw = json.load(f)
                solver_output = SolverOutput(
                    vehicles=raw.get("vehicles", {}),
                    assignment=raw.get("assignment", {}),
                    objective=raw.get("objective", {}),
                    feasible=raw.get("feasible", False),
                )
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                # JSON parse failure → treat as crash
                success = False
                error_category = "crash"
                stderr_str += f"\nJSON parse error: {e}"

        # If failed, clean up the (empty) output file
        if not success:
            _try_remove(out_path)
            out_path = None  # type: ignore[assignment]

        return RunResult(
            success=success,
            exit_code=exit_code,
            stdout=stdout_str,
            stderr=stderr_str,
            elapsed_ms=elapsed_ms,
            output=solver_output,
            output_path=out_path if success else None,
            error_category=error_category,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _kill_proc(proc: subprocess.Popen) -> None:
    """Send SIGKILL to the process group, then wait."""
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        try:
            proc.kill()
        except (ProcessLookupError, OSError):
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _try_remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass
