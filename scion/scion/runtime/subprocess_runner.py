"""LocalSubprocessRunner: MVP implementation using subprocess + resource limits."""
from __future__ import annotations

import json
import logging
import hashlib
import os
import resource
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from scion.core.models import RunResult, SolverOutput
from scion.runtime.runner import ResourceLimits

logger = logging.getLogger(__name__)

MAX_INLINE_OUTPUT_BYTES = 50_000
_OFFLOAD_PREFIX = "__offloaded__:"
_SOLVER_WALL_CLOCK_GRACE_SEC = 2
_POST_KILL_DRAIN_GRACE_SEC = 1


# Environment variables passed through to the subprocess (whitelist).
#
# Problem adapters may define their own SCION_* runtime variables. The runner
# keeps the framework problem-agnostic by allowing the SCION_ namespace instead
# of naming individual research-object variables here.
_ENV_PASSTHROUGH = {"PATH", "PYTHONPATH"}
_ENV_PREFIX_PASSTHROUGH = ("SCION_",)
_ENV_FIXED = {"PYTHONHASHSEED": "0"}
_SOLVER_OUTPUT_FRAMEWORK_FIELDS = frozenset({"objective", "feasible", "runtime"})


def _build_clean_env() -> dict[str, str]:
    """Return a sanitized environment containing only whitelisted variables."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k in _ENV_PASSTHROUGH
        or any(k.startswith(prefix) for prefix in _ENV_PREFIX_PASSTHROUGH)
    }
    env.update(_ENV_FIXED)
    return env


def _effective_scion_env(selected_surface: str | None = None) -> dict[str, str]:
    """Return the effective SCION_* environment passed to solver subprocesses."""
    env = _build_clean_env()
    surface = str(selected_surface or "").strip()
    if surface:
        env["SCION_SELECTED_SURFACE"] = surface
    else:
        env.pop("SCION_SELECTED_SURFACE", None)
    return {k: v for k, v in env.items() if k.startswith("SCION_")}


def _scion_env_value_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="surrogateescape")).hexdigest()


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
        self._progress_callback: Callable[..., None] | None = None
        self._active_proc_lock = threading.Lock()
        self._active_procs: set[subprocess.Popen] = set()

    def set_progress_callback(self, callback: Callable[..., None] | None) -> None:
        """Register a best-effort subprocess lifecycle callback."""
        self._progress_callback = callback

    def terminate_active_processes(self, *, reason: str = "shutdown") -> int:
        """Best-effort kill for solver subprocesses currently owned by this runner."""
        with self._active_proc_lock:
            procs = list(self._active_procs)
        terminated = 0
        for proc in procs:
            if _proc_is_running(proc):
                logger.warning(
                    "Terminating solver subprocess pid=%s due to %s",
                    getattr(proc, "pid", None),
                    reason,
                )
                _kill_proc(proc)
                terminated += 1
        return terminated

    def cache_identity(self, *, selected_surface: str | None = None) -> dict[str, Any]:
        """Return subprocess inputs that affect cacheable champion results."""
        scion_env = _effective_scion_env(selected_surface)
        return {
            "schema": "scion.local_subprocess_runner.cache_identity.v1",
            "scion_env": {
                name: _scion_env_value_digest(value)
                for name, value in sorted(scion_env.items())
            },
        }

    def run_solver(
        self,
        workdir: str,
        instance_path: str,
        seed: int,
        time_limit_sec: int,
        registry_path: str,
        selected_surface: str | None = None,
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
        effective_timeout = self._limits.timeout_sec
        if time_limit_sec and time_limit_sec > 0:
            # ``time_limit_sec`` is the solver's algorithm budget. Keep the
            # subprocess kill guard close to that budget, but leave a small
            # margin for Python teardown and JSON output flushing.
            solver_budget = max(1, int(time_limit_sec))
            effective_timeout = min(
                self._limits.timeout_sec,
                solver_budget + _SOLVER_WALL_CLOCK_GRACE_SEC,
            )
        effective_limits = ResourceLimits(
            timeout_sec=effective_timeout,
            memory_mb=self._limits.memory_mb,
            max_file_descriptors=self._limits.max_file_descriptors,
        )

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
        surface = str(selected_surface or "").strip()
        env.update(_effective_scion_env(surface or None))
        if not surface:
            env.pop("SCION_SELECTED_SURFACE", None)
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
                preexec_fn=_make_preexec_fn(effective_limits),
            )
            self._register_proc(proc)
            self._emit_progress(
                child_pid=proc.pid,
                child_phase="solver_subprocess",
                case=instance_path,
                seed=seed,
                selected_surface=surface or None,
            )

            try:
                stdout_bytes, stderr_bytes = proc.communicate(
                    timeout=effective_timeout
                )
            except subprocess.TimeoutExpired as exc:
                # Hard-kill the whole process group
                _kill_proc(proc)
                stdout_bytes, stderr_bytes, drain_timed_out = _drain_after_timeout(
                    proc,
                    initial_stdout=exc.output,
                    initial_stderr=exc.stderr,
                    timeout_sec=_POST_KILL_DRAIN_GRACE_SEC,
                )
                if drain_timed_out:
                    stderr_bytes = _append_stderr_note(
                        stderr_bytes,
                        (
                            "Subprocess timed out; stdout/stderr drain did not "
                            f"finish within {_POST_KILL_DRAIN_GRACE_SEC}s after kill."
                        ),
                    )
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
        finally:
            if proc is not None:
                self._unregister_proc(proc)

        elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)

        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        stderr_str = stderr_bytes.decode("utf-8", errors="replace")

        # Offload large outputs to disk to keep RunResult lightweight
        run_id = str(uuid.uuid4())[:8]
        stdout_str = self._maybe_offload(stdout_str, workdir, f"{run_id}_stdout")
        stderr_str = self._maybe_offload(stderr_str, workdir, f"{run_id}_stderr")

        exit_code = proc.returncode
        if exit_code is None:
            exit_code = -signal.SIGKILL
        self._emit_progress(
            child_pid=None,
            child_exit_code=exit_code,
            child_elapsed_ms=elapsed_ms,
            child_phase="solver_subprocess_complete",
            case=instance_path,
            seed=seed,
            selected_surface=surface or None,
        )

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
                if not isinstance(raw, dict):
                    raise TypeError("solver output JSON must be an object")
                solver_output = SolverOutput(
                    objective=raw.get("objective", {}),
                    feasible=raw.get("feasible", False),
                    runtime=(
                        raw.get("runtime", {})
                        if isinstance(raw.get("runtime", {}), dict)
                        else {}
                    ),
                    solution_payload={
                        key: value
                        for key, value in raw.items()
                        if key not in _SOLVER_OUTPUT_FRAMEWORK_FIELDS
                    },
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

    def _emit_progress(self, **payload: Any) -> None:
        if self._progress_callback is None:
            return
        try:
            self._progress_callback(**payload)
        except Exception:
            logger.debug("Solver subprocess progress callback failed", exc_info=True)


    def _maybe_offload(self, output: str, workspace: str, run_id: str) -> str:
        """If output exceeds MAX_INLINE_OUTPUT_BYTES, write to disk and return a reference."""
        if len(output.encode()) <= MAX_INLINE_OUTPUT_BYTES:
            return output
        artifact_dir = os.path.join(workspace, "artifacts")
        os.makedirs(artifact_dir, exist_ok=True)
        path = os.path.join(artifact_dir, f"run_{run_id}_output.json")
        with open(path, "w") as f:
            f.write(output)
        logger.info("Output offloaded to disk (%d KB): %s", len(output) // 1024, path)
        return f"{_OFFLOAD_PREFIX}{path}"

    def _register_proc(self, proc: subprocess.Popen) -> None:
        with self._active_proc_lock:
            self._active_procs.add(proc)

    def _unregister_proc(self, proc: subprocess.Popen) -> None:
        with self._active_proc_lock:
            self._active_procs.discard(proc)


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


def _proc_is_running(proc: subprocess.Popen) -> bool:
    poll = getattr(proc, "poll", None)
    if callable(poll):
        try:
            return poll() is None
        except Exception:
            pass
    return getattr(proc, "returncode", None) is None


def _drain_after_timeout(
    proc: subprocess.Popen,
    *,
    initial_stdout: bytes | str | None,
    initial_stderr: bytes | str | None,
    timeout_sec: int,
) -> tuple[bytes, bytes, bool]:
    """Drain output after killing a timed-out subprocess, without unbounded wait."""
    try:
        stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout_sec)
        return (
            _output_to_bytes(stdout_bytes),
            _output_to_bytes(stderr_bytes),
            False,
        )
    except subprocess.TimeoutExpired as exc:
        _close_proc_pipes(proc)
        return (
            _output_to_bytes(exc.output, fallback=initial_stdout),
            _output_to_bytes(exc.stderr, fallback=initial_stderr),
            True,
        )


def _close_proc_pipes(proc: subprocess.Popen) -> None:
    for pipe in (proc.stdout, proc.stderr):
        if pipe is None:
            continue
        try:
            pipe.close()
        except OSError:
            pass


def _output_to_bytes(
    value: bytes | str | None,
    *,
    fallback: bytes | str | None = None,
) -> bytes:
    output = fallback if value is None else value
    if output is None:
        return b""
    if isinstance(output, bytes):
        return output
    return output.encode("utf-8", errors="replace")


def _append_stderr_note(stderr_bytes: bytes, note: str) -> bytes:
    separator = b"\n" if stderr_bytes else b""
    return stderr_bytes + separator + note.encode("utf-8")


def _try_remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def resolve_offloaded(output: str) -> str:
    """Resolve an offloaded output reference back to its full content.

    If ``output`` is an ``__offloaded__:<path>`` reference, reads and returns
    the content from disk.  Otherwise returns ``output`` unchanged.
    """
    if output.startswith(_OFFLOAD_PREFIX):
        path = output[len(_OFFLOAD_PREFIX):]
        with open(path, "r") as f:
            return f.read()
    return output
