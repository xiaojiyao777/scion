"""Single-process, fail-closed bubblewrap backend for public observations."""
from __future__ import annotations

import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RunLimits:
    wall_seconds: float
    cpu_seconds: int
    memory_bytes: int
    output_bytes: int
    scratch_bytes: int

    def __post_init__(self):
        if type(self.wall_seconds) not in (int, float) or not math.isfinite(self.wall_seconds) or self.wall_seconds <= 0:
            raise ValueError("wall_seconds must be finite and positive")
        for value in (self.cpu_seconds, self.memory_bytes, self.output_bytes, self.scratch_bytes):
            if type(value) is not int or value <= 0:
                raise ValueError("CPU seconds and byte limits must be positive integers")


@dataclass(frozen=True)
class SandboxResult:
    reason_code: str
    returncode: int | None
    started: bool
    stdout: bytes
    stderr: bytes
    result: bytes
    wall_seconds: float
    cpu_seconds: float | None
    peak_memory_bytes: int | None
    limits: RunLimits

    @property
    def captured_bytes(self):
        return len(self.stdout) + len(self.stderr) + len(self.result)


class ObservationSandbox:
    """Only fixed prepared mounts enter this API; there is no host fallback."""

    def __init__(self, *, bwrap: str = "/usr/bin/bwrap"):
        self.bwrap = bwrap

    def run(self, *, subject: Path, runtime: Path, inputs: Path,
            module: str, mode: str, limits: RunLimits,
            dependencies: tuple[str, ...] = ()) -> SandboxResult:
        start = time.monotonic()
        raw = {"stdout": bytearray(), "stderr": bytearray(), "result": bytearray()}
        result_read, result_write = os.pipe()
        notice_read, notice_write = os.pipe()
        entered = False
        proc = None
        usage = None
        reason = "COMPLETED"
        returncode = None
        selector = selectors.DefaultSelector()
        try:
            argv = self._argv(subject, runtime, inputs, module, mode, limits, dependencies, result_write, notice_write)
            proc = subprocess.Popen(
                argv, cwd="/", env={}, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                close_fds=True, pass_fds=(result_write, notice_write), start_new_session=True,
            )
            os.close(result_write)
            result_write = -1
            os.close(notice_write)
            notice_write = -1
            for stream, label in ((proc.stdout, "stdout"), (proc.stderr, "stderr"), (result_read, "result"), (notice_read, "notice")):
                fd = stream if isinstance(stream, int) else stream.fileno()
                os.set_blocking(fd, False)
                selector.register(fd, selectors.EVENT_READ, label)
            reaped = False
            while not reaped or selector.get_map():
                if not reaped and time.monotonic() - start >= limits.wall_seconds:
                    reason = "WALL_LIMIT"
                    self._kill(proc.pid)
                for key, _ in selector.select(0.01):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fd)
                        continue
                    if key.data == "notice":
                        entered = chunk == b"\x01"
                        continue
                    remaining = limits.output_bytes - sum(map(len, raw.values()))
                    raw[key.data].extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        reason = "OUTPUT_LIMIT"
                        self._kill(proc.pid)
                if not reaped:
                    waited, status, measured = os.wait4(proc.pid, os.WNOHANG)
                    if waited:
                        returncode = os.waitstatus_to_exitcode(status)
                        proc.returncode = returncode
                        usage = measured
                        reaped = True
            if reason == "COMPLETED":
                if not entered:
                    reason = "ISOLATION_UNAVAILABLE"
                elif returncode in (-signal.SIGXCPU, 128 + signal.SIGXCPU):
                    reason = "CPU_LIMIT"
                elif returncode in (-signal.SIGKILL, 128 + signal.SIGKILL):
                    # A hard CPU limit, OOM, or another kill may have the same
                    # status. Even near-limit rusage does not establish cause.
                    reason = "PROCESS_KILLED"
                elif returncode:
                    reason = "PROCESS_ERROR"
        except (OSError, ValueError):
            reason = "ISOLATION_UNAVAILABLE" if proc is None else "INTERNAL_ERROR"
        except KeyboardInterrupt:
            reason = "USER_INTERRUPTED"
        except BaseException:
            if proc is not None:
                self._kill(proc.pid)
                if proc.returncode is None:
                    _, status, _ = os.wait4(proc.pid, 0)
                    proc.returncode = os.waitstatus_to_exitcode(status)
            raise
        finally:
            if proc is not None and proc.returncode is None:
                self._kill(proc.pid)
                _, status, usage = os.wait4(proc.pid, 0)
                returncode = proc.returncode = os.waitstatus_to_exitcode(status)
            selector.close()
            os.close(result_read)
            os.close(notice_read)
            if result_write >= 0:
                os.close(result_write)
            if notice_write >= 0:
                os.close(notice_write)
            if proc is not None:
                proc.stdout.close()
                proc.stderr.close()
        return SandboxResult(
            reason, returncode, entered, *(bytes(raw[k]) for k in ("stdout", "stderr", "result")),
            time.monotonic() - start,
            (usage.ru_utime + usage.ru_stime) if usage is not None else None,
            usage.ru_maxrss * 1024 if usage is not None else None,
            limits,
        )

    @staticmethod
    def _kill(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def _argv(self, subject, runtime, inputs, module, mode, limits, dependencies, result_fd, notice_fd):
        prefix = Path(sys.prefix).resolve()
        python = Path(sys.executable).resolve()
        python.relative_to(prefix)
        argv = [self.bwrap, "--unshare-all", "--as-pid-1", "--die-with-parent", "--new-session",
                "--clearenv", "--cap-drop", "ALL"]
        for path in ("/lib", "/lib64"):
            if Path(path).exists():
                argv += ["--ro-bind", path, path]
        argv += ["--ro-bind", str(prefix / "lib"), "/python/lib",
                 "--ro-bind", str(python), "/python/bin/python"]
        for site in (prefix / "lib").glob("python*/site-packages"):
            masked = "/python/lib/" + str(site.relative_to(prefix / "lib"))
            argv += ["--tmpfs", masked, "--remount-ro", masked]
        site = prefix / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
        allowed = {"pydantic", "pydantic_core", "annotated_types", "typing_extensions.py", "typing_inspection", "yaml"}
        argv += ["--dir", "/deps"]
        for name in dependencies:
            if name not in allowed or not (site / name).exists():
                raise ValueError("unsupported public dependency")
            argv += ["--ro-bind", str(site / name), "/deps/" + name]
        argv += ["--ro-bind", str(subject.resolve()), "/subject",
                 "--ro-bind", str(runtime.resolve()), "/runtime",
                 "--ro-bind", str(inputs.resolve()), "/input",
                 "--ro-bind", str(subject.resolve() if mode == "checker" else runtime.parent.resolve() / "public"), "/public",
                 "--size", str(limits.scratch_bytes), "--tmpfs", "/scratch",
                 "--ro-bind", "/dev/null", "/dev/null", "--remount-ro", "/",
                 "--chdir", "/scratch", "--setenv", "TMPDIR", "/scratch",
                 "--setenv", "PYTHONHASHSEED", "0",
                 "/python/bin/python", "-I", "-S", "-B", "/runtime/bootstrap.py",
                 mode, module, str(result_fd), str(notice_fd), str(limits.cpu_seconds),
                 str(limits.memory_bytes), str(limits.output_bytes)]
        return argv
