"""One-owner adapter from the accepted native spawn ABI to generic execution.

This module owns live process/capture capabilities.  It deliberately contains
no problem semantics, publication policy, or alternate process launcher.
"""

from __future__ import annotations

import errno
import fcntl
import itertools
import os
import select
import signal
import stat
import struct
import time
from typing import Optional, Tuple

from scion.runtime import native

from .cgroup_v2 import (
    CgroupIntegrityError,
    CgroupStateError,
    ServiceCgroup,
)
from .model import (
    BackendOpenFailure,
    BackendOpenPhase,
    BackendOpenReason,
    ChildCreation,
    CapturedStream,
    ClosedSpawnObservation,
    ContainedSpawnPhase,
    ContainedSpawnFailure,
    ContainedSpawnReason,
    FilesystemIdentity,
    GenericProcessSpec,
    JobCgroupKey,
    PreHandleFailure,
    PreHandlePhase,
    PreHandleReason,
    ProcessIdentity,
    StreamAvailability,
    WaitFact,
    _CleanupPermitIdentity,
)


_PROC_SELF_TASK = "/proc/self/task"
_PROC_ROOT = "/proc"
_READ_BLOCK = 64 * 1024
_MIN_DUP_FD = 3
_BACKEND_GENERATIONS = itertools.count(1)
_UNSET_CHILD = object()
_CATCHABLE_SIGNALS = frozenset(
    item
    for item in signal.valid_signals()
    if item not in (signal.SIGKILL, signal.SIGSTOP)
)
_CAPTURE_UNSUPPORTED_ERRNOS = frozenset(
    value
    for value in (
        getattr(errno, "EOPNOTSUPP", None),
        getattr(errno, "EINVAL", None),
        getattr(errno, "EISDIR", None),
    )
    if value is not None
)
_CAPTURE_ALLOCATION_ERRNOS = frozenset(
    value
    for value in (
        getattr(errno, "ENOSPC", None),
        getattr(errno, "EDQUOT", None),
        getattr(errno, "ENOMEM", None),
    )
    if value is not None
)


class BackendStateError(RuntimeError):
    """A live execution capability was used in the wrong exact state."""


class _IssuerSignalGuard:
    """Short, exact signal-mask guard for one ownership micro-transaction."""

    __slots__ = (
        "_creator_pid",
        "_entry_pending",
        "_prior_mask",
        "_state",
    )

    _NEW = "NEW"
    _BLOCK_STARTED = "BLOCK_STARTED"
    _BLOCKED = "BLOCKED"
    _RESTORE_STARTED = "RESTORE_STARTED"
    _RESTORED = "RESTORED"

    def __init__(self) -> None:
        self._creator_pid = os.getpid()
        self._entry_pending = frozenset()
        self._prior_mask = frozenset()
        self._state = self._NEW

    @staticmethod
    def _current_mask() -> frozenset[signal.Signals | int]:
        return frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set()))

    def _recover_block_start(self) -> None:
        """Restore after an exception around SIG_BLOCK, or fail-stop."""

        try:
            current = self._current_mask()
            expected = self._prior_mask | _CATCHABLE_SIGNALS
            if current == self._prior_mask:
                self._state = self._RESTORED
                return
            if current != expected:
                _failstop()
        except BaseException:
            _failstop()
        self._state = self._RESTORE_STARTED
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, self._prior_mask)
        except BaseException:
            # The syscall may have restored the mask before Python delivered
            # the pending handler.  Recovery is decided only by readback.
            pass
        try:
            if self._current_mask() != self._prior_mask:
                _failstop()
            self._state = self._RESTORED
        except BaseException:
            _failstop()

    def block(self) -> None:
        if self._state != self._NEW or os.getpid() != self._creator_pid:
            _failstop()
        if not _single_threaded():
            _failstop()
        try:
            # Query first, without changing state.  The guard therefore knows
            # how to recover even if a pending Python handler is raised at the
            # SIG_BLOCK return boundary.
            self._prior_mask = self._current_mask()
            self._entry_pending = frozenset(signal.sigpending())
        except BaseException:
            _failstop()
        self._state = self._BLOCK_STARTED
        try:
            signal.pthread_sigmask(signal.SIG_BLOCK, _CATCHABLE_SIGNALS)
            if self._current_mask() != self._prior_mask | _CATCHABLE_SIGNALS:
                _failstop()
            self._state = self._BLOCKED
        except BaseException:
            self._recover_block_start()
            raise

    def restore(self) -> bool:
        """Restore exactly once and report issuer delivery during the guard."""

        if os.getpid() != self._creator_pid:
            _failstop()
        if self._state == self._RESTORED:
            _failstop()
        if self._state not in (self._BLOCKED, self._RESTORE_STARTED):
            _failstop()
        interrupted = False
        if self._state == self._BLOCKED:
            try:
                interrupted = bool(
                    frozenset(signal.sigpending()) - self._entry_pending
                )
            except BaseException:
                interrupted = True
            self._state = self._RESTORE_STARTED
            try:
                signal.pthread_sigmask(signal.SIG_SETMASK, self._prior_mask)
                if self._current_mask() != self._prior_mask:
                    _failstop()
                self._state = self._RESTORED
                return interrupted
            except BaseException:
                interrupted = True

        # SIG_SETMASK may already have restored the mask before a Python
        # handler raised.  Only an exact readback permits ordinary recovery.
        try:
            if self._current_mask() != self._prior_mask:
                _failstop()
            self._state = self._RESTORED
            return True
        except BaseException:
            _failstop()

    def interrupted(self) -> bool:
        """Query newly pending issuer delivery without restoring the mask."""

        if os.getpid() != self._creator_pid or self._state != self._BLOCKED:
            _failstop()
        try:
            return bool(frozenset(signal.sigpending()) - self._entry_pending)
        except BaseException:
            return True

    def __del__(self) -> None:
        if getattr(self, "_state", self._RESTORED) in (self._NEW, self._RESTORED):
            return
        if os.getpid() == getattr(self, "_creator_pid", -1):
            _failstop()


class _MoveLedger:
    """Pre-existing target for a signal-safe FD or capability move."""

    __slots__ = ("assigned", "interrupted", "value")

    def __init__(self) -> None:
        self.assigned = False
        self.interrupted = False
        self.value = None


def _failstop() -> None:
    """End the issuer when ownership or containment can no longer be proved."""

    os.abort()


def _reject_live_copy(_self: object, _argument: object = None) -> None:
    del _argument
    raise TypeError("live execution capabilities are not copyable or pickleable")


def _read_all(fd: int, *, rewind: bool) -> bytes:
    if rewind:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
        except BaseException:
            _failstop()
    chunks = []
    while True:
        try:
            chunk = os.read(fd, _READ_BLOCK)
        except InterruptedError:
            continue
        except BaseException:
            _failstop()
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _close_exact(fd: int) -> None:
    if fd < 0:
        return
    try:
        os.close(fd)
    except BaseException:
        _failstop()


def _close_after_fork(fd: int) -> None:
    if fd < 0:
        return
    try:
        os.close(fd)
    except OSError:
        pass


def _set_nonblocking(fd: int) -> None:
    try:
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        descriptor_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
    except BaseException:
        _failstop()
    if not descriptor_flags & fcntl.FD_CLOEXEC:
        _failstop()


def _parse_proc_starttime(raw: bytes) -> int:
    right_paren = raw.rfind(b")")
    if right_paren < 0 or right_paren + 2 >= len(raw):
        _failstop()
    fields = raw[right_paren + 2 :].split()
    if len(fields) <= 19:
        _failstop()
    value = fields[19]
    if not value.isdigit() or value.startswith(b"0"):
        _failstop()
    return int(value, 10)


def _process_starttime(pid: int) -> int:
    if type(pid) is not int or pid <= 0:
        _failstop()
    proc_fd = stat_fd = -1
    try:
        proc_fd = os.open(
            _PROC_ROOT,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0),
        )
        stat_fd = os.open(
            f"{pid}/stat",
            os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=proc_fd,
        )
        return _parse_proc_starttime(_read_all(stat_fd, rewind=False))
    except BaseException:
        _failstop()
    finally:
        _close_exact(stat_fd)
        _close_exact(proc_fd)


def _single_threaded() -> bool:
    try:
        entries = os.listdir(_PROC_SELF_TASK)
    except BaseException:
        _failstop()
    canonical = []
    for entry in entries:
        if type(entry) is not str or not entry.isascii() or not entry.isdecimal():
            _failstop()
        if entry.startswith("0"):
            _failstop()
        canonical.append(int(entry, 10))
    if len(canonical) != len(set(canonical)):
        _failstop()
    return canonical == [os.getpid()]


def _capture_open_reason(error_number: int) -> PreHandleReason:
    if error_number in _CAPTURE_UNSUPPORTED_ERRNOS:
        return PreHandleReason.CAPTURE_TMPFILE_UNSUPPORTED
    if error_number in _CAPTURE_ALLOCATION_ERRNOS:
        return PreHandleReason.CAPTURE_ALLOCATION_FAILED
    return PreHandleReason.CAPTURE_OPEN_FAILED


def _make_backend_open_failure(
    *,
    phase: BackendOpenPhase,
    reason: BackendOpenReason,
    service_lineage: object,
    capture_directory_acquired: bool,
    capture_directory_identity: Optional[FilesystemIdentity],
    error_number: Optional[int],
) -> BackendOpenFailure:
    try:
        return BackendOpenFailure(
            phase=phase,
            reason=reason,
            service_lineage=service_lineage,
            capture_directory_acquired=capture_directory_acquired,
            capture_directory_identity=capture_directory_identity,
            errno=error_number,
        )
    except BaseException:
        _failstop()


class _Spool:
    __slots__ = ("fd", "identity")

    def __init__(self, fd: int, identity: FilesystemIdentity) -> None:
        self.fd = fd
        self.identity = identity

    def close(self) -> None:
        fd = self.fd
        self.fd = -1
        _close_exact(fd)


def _write_spool(spool: _Spool, data: bytes) -> bool:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        try:
            written = os.write(spool.fd, view[offset:])
        except InterruptedError:
            continue
        except OSError:
            return False
        except MemoryError:
            return False
        if written <= 0:
            return False
        offset += written
    return True


def _read_spool(
    spool: _Spool,
    result_ledger: _MoveLedger,
) -> Optional[CapturedStream]:
    if type(result_ledger) is not _MoveLedger or result_ledger.assigned:
        _failstop()
    try:
        while True:
            try:
                os.fsync(spool.fd)
                break
            except InterruptedError:
                continue
        while True:
            try:
                os.lseek(spool.fd, 0, os.SEEK_SET)
                break
            except InterruptedError:
                continue
        chunks = []
        while True:
            try:
                chunk = os.read(spool.fd, _READ_BLOCK)
            except InterruptedError:
                continue
            if not chunk:
                break
            chunks.append(chunk)
        data = b"".join(chunks)
        result_ledger.value = CapturedStream.from_bytes(data)
        result_ledger.assigned = True
        return result_ledger.value
    except (OSError, MemoryError):
        result_ledger.value = None
        result_ledger.assigned = True
        return None
    finally:
        spool.close()


def _decode_exec_error(data: bytes) -> Optional[Tuple[int, int]]:
    if data == b"":
        return None
    if len(data) != native.ERROR_RECORD_SIZE:
        _failstop()
    try:
        magic, version, stage, reserved, error_number = struct.unpack(
            native.ERROR_RECORD_FORMAT,
            data,
        )
    except (struct.error, TypeError, ValueError):
        _failstop()
    if (
        magic != native.ERROR_RECORD_MAGIC
        or version != native.ERROR_RECORD_VERSION
        or not 1 <= stage <= 13
        or reserved != 0
        or error_number <= 0
    ):
        _failstop()
    return stage, error_number


class _StreamDrain:
    __slots__ = (
        "name",
        "fd",
        "spool",
        "buffer",
        "available",
        "storage_failed",
        "eof",
        "finished",
        "captured",
        "finish_interrupted",
    )

    def __init__(
        self,
        name: str,
        fd: int,
        *,
        spool: Optional[_Spool],
    ) -> None:
        self.name = name
        self.fd = fd
        self.spool = spool
        self.buffer = bytearray() if spool is None else None
        self.available = True
        self.storage_failed = False
        self.eof = False
        self.finished = False
        self.captured = None
        self.finish_interrupted = False

    def consume(self, data: bytes) -> bool:
        if not self.available:
            return False
        if self.spool is not None:
            if _write_spool(self.spool, data):
                return False
            self.storage_failed = True
            self.available = False
            return True
        try:
            self.buffer.extend(data)
        except MemoryError:
            self.storage_failed = True
            self.available = False
            self.buffer = None
            return True
        return False

    def close_reader(self) -> None:
        fd = self.fd
        self.fd = -1
        self.eof = True
        _close_exact(fd)

    def finish(self) -> Optional[CapturedStream]:
        if self.finished:
            return self.captured
        if not self.eof or self.fd >= 0:
            _failstop()
        if self.spool is not None:
            if not self.available:
                try:
                    self.spool.close()
                    self.captured = None
                    self.finished = True
                except BaseException:
                    if self.finished and self.spool.fd < 0:
                        self.finish_interrupted = True
                        return None
                    _failstop()
                return None
            readback = _MoveLedger()
            try:
                value = _read_spool(self.spool, readback)
                if value is None:
                    self.storage_failed = True
                    self.available = False
                self.captured = value
                self.finished = True
            except Exception:
                _failstop()
            except BaseException:
                self.finish_interrupted = True
                if readback.assigned and readback.value is None:
                    self.storage_failed = True
                if readback.assigned and readback.value is not None:
                    self.captured = readback.value
                    self.finished = True
                    return self.captured
                self.available = False
                if self.spool.fd >= 0:
                    try:
                        self.spool.close()
                    except BaseException:
                        _failstop()
                self.captured = None
                self.finished = True
                return None
            return value
        if not self.available or self.buffer is None:
            self.captured = None
            self.finished = True
            return None
        try:
            self.captured = CapturedStream.from_bytes(bytes(self.buffer))
            self.finished = True
            return self.captured
        except MemoryError:
            self.available = False
            self.captured = None
            self.finished = True
            return None
        except Exception:
            _failstop()
        except BaseException:
            self.finish_interrupted = True
            self.available = False
            self.captured = None
            self.finished = True
            return None


def _drain_one_stream_snapshot(stream: _StreamDrain) -> Tuple[bool, bool]:
    """Perform one fair destructive read and commit it before returning.

    The booleans are ``issuer_interrupted`` and ``storage_failed``.  A
    stdout/stderr interruption after the destructive read permanently makes
    that stream unavailable.  Equivalent uncertainty on exec-error is fatal.
    """

    read_ledger = _MoveLedger()
    guard = _IssuerSignalGuard()
    entered = False
    read_started = False
    read_error: Optional[OSError] = None
    issuer_interrupted = False
    exec_commit_started = False
    exec_committed = False
    try:
        guard.block()
        entered = True
        read_started = True
        read_ledger.value = os.read(stream.fd, _READ_BLOCK)
        read_ledger.assigned = True
    except OSError as exc:
        read_error = exc
    except Exception:
        if entered:
            guard.restore()
        _failstop()
    except BaseException:
        issuer_interrupted = True

    try:
        if entered:
            if guard.restore():
                issuer_interrupted = True

        if issuer_interrupted and read_started and not read_ledger.assigned:
            if stream.name == "exec_error":
                _failstop()
            stream.available = False
            return True, False

        if read_error is not None:
            if read_error.errno in (
                errno.EINTR,
                errno.EAGAIN,
                errno.EWOULDBLOCK,
            ):
                return issuer_interrupted, False
            _failstop()

        if not read_ledger.assigned or type(read_ledger.value) is not bytes:
            _failstop()
        if issuer_interrupted and stream.name != "exec_error":
            stream.available = False

        chunk = read_ledger.value
        if chunk == b"":
            close_guard = _IssuerSignalGuard()
            close_guard.block()
            stream.close_reader()
            if close_guard.restore():
                issuer_interrupted = True
            return issuer_interrupted, False

        if stream.name == "exec_error":
            commit_guard = _IssuerSignalGuard()
            commit_guard.block()
            exec_commit_started = True
            storage_failed = stream.consume(chunk)
            exec_committed = True
            if commit_guard.restore():
                issuer_interrupted = True
            if storage_failed:
                _failstop()
            return issuer_interrupted, False

        storage_failed = stream.consume(chunk)
        return issuer_interrupted, storage_failed
    except Exception:
        _failstop()
    except BaseException:
        if stream.name == "exec_error":
            if not read_ledger.assigned:
                _failstop()
            if exec_commit_started and not exec_committed:
                _failstop()
            chunk = read_ledger.value
            if not exec_committed and chunk != b"":
                recovery_guard = _IssuerSignalGuard()
                try:
                    recovery_guard.block()
                    if stream.consume(chunk):
                        _failstop()
                except BaseException:
                    _failstop()
                recovery_guard.restore()
            elif chunk == b"" and not stream.eof:
                recovery_guard = _IssuerSignalGuard()
                try:
                    recovery_guard.block()
                    stream.close_reader()
                except BaseException:
                    _failstop()
                recovery_guard.restore()
            return True, False
        if read_started:
            if stream.name == "exec_error" and stream.storage_failed:
                _failstop()
            stream.available = False
            if (
                read_ledger.assigned
                and read_ledger.value == b""
                and not stream.eof
            ):
                recovery_guard = _IssuerSignalGuard()
                try:
                    recovery_guard.block()
                    stream.close_reader()
                except BaseException:
                    _failstop()
                recovery_guard.restore()
        return True, stream.storage_failed


class _TerminalDrainLedger:
    """Caller-owned commit record for peek/fact/reap/pidfd-close."""

    __slots__ = (
        "terminal",
        "wait_fact",
        "fact_assigned",
        "phase_committed",
        "interruption_phase",
        "reap_started",
        "reaped",
        "pidfd_closed",
    )

    def __init__(self) -> None:
        self.terminal = None
        self.wait_fact = None
        self.fact_assigned = False
        self.phase_committed = False
        self.interruption_phase = None
        self.reap_started = False
        self.reaped = False
        self.pidfd_closed = False


def _drain_terminal_snapshot(
    child: object,
    poll_pidfd: int,
    ledger: _TerminalDrainLedger,
) -> bool:
    """Resume terminal fact, exact reap and poll-pidfd close from one ledger."""

    issuer_interrupted = False
    if ledger.pidfd_closed:
        _failstop()
    if ledger.terminal is None:
        try:
            ledger.terminal = child.peek_wait()
        except Exception:
            _failstop()
        except BaseException:
            return True
    if ledger.terminal is None:
        _failstop()

    if not ledger.fact_assigned:
        fact_guard = _IssuerSignalGuard()
        fact_entered = False
        try:
            fact_guard.block()
            fact_entered = True
            ledger.wait_fact = WaitFact.from_native(ledger.terminal)
            ledger.fact_assigned = True
            ledger.phase_committed = True
        except Exception:
            if fact_entered:
                fact_guard.restore()
            _failstop()
        except BaseException:
            issuer_interrupted = True
            if ledger.phase_committed and ledger.interruption_phase is None:
                ledger.interruption_phase = ContainedSpawnPhase.LEADER_TERMINAL
        try:
            if fact_entered and fact_guard.restore():
                issuer_interrupted = True
                if ledger.interruption_phase is None:
                    ledger.interruption_phase = (
                        ContainedSpawnPhase.LEADER_TERMINAL
                    )
        except Exception:
            _failstop()
        except BaseException:
            issuer_interrupted = True
            if ledger.interruption_phase is None:
                ledger.interruption_phase = ContainedSpawnPhase.LEADER_TERMINAL
    if not ledger.fact_assigned or type(ledger.wait_fact) is not WaitFact:
        if issuer_interrupted:
            return True
        _failstop()
    if not ledger.phase_committed:
        phase_guard = _IssuerSignalGuard()
        try:
            phase_guard.block()
            ledger.phase_committed = True
        except BaseException:
            phase_guard.restore()
            _failstop()
        try:
            if phase_guard.restore():
                issuer_interrupted = True
                if ledger.interruption_phase is None:
                    ledger.interruption_phase = (
                        ContainedSpawnPhase.LEADER_TERMINAL
                    )
        except Exception:
            _failstop()
        except BaseException:
            issuer_interrupted = True
            if ledger.interruption_phase is None:
                ledger.interruption_phase = ContainedSpawnPhase.LEADER_TERMINAL

    if not ledger.reaped:
        reap_ledger = _MoveLedger()
        reap_guard = _IssuerSignalGuard()
        reap_entered = False
        try:
            reap_guard.block()
            reap_entered = True
            ledger.reap_started = True
            reap_ledger.value = child.reap()
            reap_ledger.assigned = True
            ledger.reaped = True
        except Exception:
            if reap_entered:
                reap_guard.restore()
            _failstop()
        except BaseException:
            issuer_interrupted = True
            if ledger.interruption_phase is None:
                ledger.interruption_phase = ContainedSpawnPhase.LEADER_TERMINAL
            if child.state == "REAPED":
                ledger.reaped = True
                reap_ledger.value = ledger.terminal
                reap_ledger.assigned = True
        try:
            if reap_entered and reap_guard.restore():
                issuer_interrupted = True
                if ledger.interruption_phase is None:
                    ledger.interruption_phase = (
                        ContainedSpawnPhase.LEADER_TERMINAL
                    )
        except Exception:
            _failstop()
        except BaseException:
            issuer_interrupted = True
            if ledger.interruption_phase is None:
                ledger.interruption_phase = ContainedSpawnPhase.LEADER_TERMINAL
        if not ledger.reaped:
            return True
        if not reap_ledger.assigned or reap_ledger.value != ledger.terminal:
            _failstop()

    if not ledger.pidfd_closed:
        close_guard = _IssuerSignalGuard()
        close_entered = False
        try:
            close_guard.block()
            close_entered = True
            _close_exact(poll_pidfd)
            ledger.pidfd_closed = True
        except BaseException:
            if close_entered:
                close_guard.restore()
            _failstop()
        try:
            if close_guard.restore():
                issuer_interrupted = True
                if ledger.interruption_phase is None:
                    ledger.interruption_phase = (
                        ContainedSpawnPhase.LEADER_REAPED_DRAINING
                    )
        except Exception:
            _failstop()
        except BaseException:
            issuer_interrupted = True
            if ledger.interruption_phase is None:
                ledger.interruption_phase = (
                    ContainedSpawnPhase.LEADER_REAPED_DRAINING
                )
    return issuer_interrupted


class _DrainResult:
    __slots__ = (
        "wait_fact",
        "stdout",
        "stderr",
        "exec_error",
        "final_events",
        "failure_reason",
        "failure_phase",
        "exec_error_stage",
        "exec_error_errno",
    )

    def __init__(
        self,
        *,
        wait_fact: WaitFact,
        stdout: Optional[CapturedStream],
        stderr: Optional[CapturedStream],
        exec_error: Optional[CapturedStream],
        final_events: object,
        failure_reason: Optional[ContainedSpawnReason],
        failure_phase: Optional[ContainedSpawnPhase],
        exec_error_stage: Optional[int],
        exec_error_errno: Optional[int],
    ) -> None:
        self.wait_fact = wait_fact
        self.stdout = stdout
        self.stderr = stderr
        self.exec_error = exec_error
        self.final_events = final_events
        self.failure_reason = failure_reason
        self.failure_phase = failure_phase
        self.exec_error_stage = exec_error_stage
        self.exec_error_errno = exec_error_errno


class _DrainAttemptLedger:
    """Caller-owned drain state spanning every poll and dispatch boundary."""

    __slots__ = (
        "blocked",
        "child",
        "job",
        "streams",
        "poll_pidfd",
        "events_fd",
        "terminal",
        "wait_fact",
        "final_events",
        "failure_reason",
        "failure_phase",
        "current_phase",
        "containment_killed",
    )

    def __init__(
        self,
        blocked: object,
        *,
        initial_reason: Optional[ContainedSpawnReason],
        initial_phase: Optional[ContainedSpawnPhase],
        kill_initially: bool,
    ) -> None:
        self.blocked = blocked
        self.child = blocked._child
        self.job = blocked._job
        self.streams = {
            blocked._stdout_fd: _StreamDrain(
                "stdout", blocked._stdout_fd, spool=blocked._stdout_spool
            ),
            blocked._stderr_fd: _StreamDrain(
                "stderr", blocked._stderr_fd, spool=blocked._stderr_spool
            ),
            blocked._exec_error_fd: _StreamDrain(
                "exec_error", blocked._exec_error_fd, spool=None
            ),
        }
        self.poll_pidfd = blocked._poll_pidfd
        self.events_fd = self.job._events_fileno()
        self.terminal = _TerminalDrainLedger()
        self.wait_fact = None
        self.final_events = None
        self.failure_reason = initial_reason
        self.failure_phase = initial_phase
        self.current_phase = (
            ContainedSpawnPhase.SETTLING_BLOCKED
            if kill_initially
            else ContainedSpawnPhase.RELEASED_DRAINING
        )
        self.containment_killed = False

    def kill_containment(self) -> None:
        if self.containment_killed:
            return
        try:
            self.job._kill()
        except BaseException:
            _failstop()
        self.containment_killed = True

    def remember_failure(
        self,
        reason: ContainedSpawnReason,
        phase: ContainedSpawnPhase,
        *,
        kill: bool,
    ) -> None:
        if self.failure_reason is None:
            self.failure_reason = reason
            self.failure_phase = phase
        if kill:
            self.kill_containment()

    def remember_issuer(self) -> None:
        if any(
            stream.name == "exec_error" and stream.storage_failed
            for stream in self.streams.values()
        ):
            _failstop()
        if self.failure_reason is None and any(
            stream.name != "exec_error" and stream.storage_failed
            for stream in self.streams.values()
        ):
            self.failure_reason = ContainedSpawnReason.CAPTURE_FAILED
            self.failure_phase = self.current_phase
        if self.terminal.phase_committed:
            self.current_phase = ContainedSpawnPhase.LEADER_TERMINAL
        if self.terminal.pidfd_closed:
            self.wait_fact = self.terminal.wait_fact
            self.current_phase = ContainedSpawnPhase.LEADER_REAPED_DRAINING
            self.poll_pidfd = -1
        self.remember_failure(
            ContainedSpawnReason.ISSUER_INTERRUPTED,
            self.current_phase,
            kill=True,
        )

    @property
    def complete(self) -> bool:
        return (
            self.wait_fact is not None
            and all(stream.eof for stream in self.streams.values())
            and self.final_events is not None
            and self.final_events.populated == 0
        )


class _HandleAssemblyLedger:
    """Sole local owner from native return through BlockedSpawn commit."""

    __slots__ = (
        "key",
        "spec",
        "job",
        "child",
        "stdout_spool",
        "stderr_spool",
        "capture_fds",
        "capture_assigned",
        "poll_pidfd",
        "pidfd_assigned",
        "process_identity",
        "blocked",
        "blocked_assigned",
    )

    def __init__(
        self,
        *,
        key: JobCgroupKey,
        spec: GenericProcessSpec,
        job: Optional[object] = None,
        stdout_spool: Optional[_Spool] = None,
        stderr_spool: Optional[_Spool] = None,
    ) -> None:
        self.key = key
        self.spec = spec
        self.job = job
        self.child = _UNSET_CHILD
        self.stdout_spool = stdout_spool
        self.stderr_spool = stderr_spool
        self.capture_fds = None
        self.capture_assigned = False
        self.poll_pidfd = -1
        self.pidfd_assigned = False
        self.process_identity = None
        self.blocked = None
        self.blocked_assigned = False


class _StartLedger:
    """Caller-owned state from first spool through public start dispatch."""

    __slots__ = (
        "key",
        "spec",
        "phase",
        "prehandle_reason",
        "stdout",
        "stderr",
        "job",
        "borrow",
        "assembly",
        "native_called",
        "start_wall_ns",
        "start_monotonic_ns",
        "result",
    )

    def __init__(self, key: JobCgroupKey, spec: GenericProcessSpec) -> None:
        self.key = key
        self.spec = spec
        self.phase = PreHandlePhase.CAPTURE_PREPARE
        self.prehandle_reason = None
        self.stdout = _MoveLedger()
        self.stderr = _MoveLedger()
        self.job = _MoveLedger()
        self.borrow = _MoveLedger()
        self.assembly = _HandleAssemblyLedger(key=key, spec=spec)
        self.native_called = False
        self.start_wall_ns = 0
        self.start_monotonic_ns = 0
        self.result = _MoveLedger()


class _ConsumedBlockedLedger:
    """Sole owner from public wrapper consume through drain handoff."""

    __slots__ = (
        "blocked",
        "settle_reason",
        "wrapper_consumed",
        "active_cleared",
        "release_started",
        "release_state",
        "drain_started",
        "drain_attempt",
        "drain_result",
        "completion",
        "initial_reason",
        "initial_phase",
        "kill_initially",
    )

    def __init__(
        self,
        blocked: object,
        settle_reason: Optional[ContainedSpawnReason],
    ) -> None:
        self.blocked = blocked
        self.settle_reason = settle_reason
        self.wrapper_consumed = False
        self.active_cleared = False
        self.release_started = False
        self.release_state = None
        self.drain_started = False
        self.drain_attempt = None
        self.drain_result = _MoveLedger()
        self.completion = _MoveLedger()
        self.initial_reason = settle_reason
        self.initial_phase = (
            ContainedSpawnPhase.BLOCKED if settle_reason is not None else None
        )
        self.kill_initially = settle_reason is not None

    def latch_issuer_from_child(self) -> None:
        state = self.blocked._child.state
        if not self.release_started or state == "BLOCKED":
            phase = ContainedSpawnPhase.BLOCKED
        elif state in ("RELEASED", "POISONED"):
            phase = ContainedSpawnPhase.RELEASED_DRAINING
        else:
            _failstop()
        if self.initial_reason is None:
            self.initial_reason = ContainedSpawnReason.ISSUER_INTERRUPTED
            self.initial_phase = phase
        self.kill_initially = True

    def latch_release_uncertain(self) -> None:
        if self.release_state != "POISONED":
            _failstop()
        if self.initial_reason is None:
            self.initial_reason = ContainedSpawnReason.RELEASE_UNCERTAIN
        if self.initial_reason is ContainedSpawnReason.RELEASE_UNCERTAIN:
            if self.initial_phase is None:
                self.initial_phase = ContainedSpawnPhase.RELEASED_DRAINING
            self.kill_initially = True


class _PositiveCommitLedger:
    """Recorded positive facts until a SettledJob is safely handed off."""

    __slots__ = (
        "blocked",
        "result",
        "final_events",
        "observation",
        "settled",
        "backend_committed",
        "blocked_cleared",
    )

    def __init__(self, blocked: object, result: _DrainResult) -> None:
        self.blocked = blocked
        self.result = result
        self.final_events = None
        self.observation = None
        self.settled = _MoveLedger()
        self.backend_committed = False
        self.blocked_cleared = False


def _open_spool_into(
    ledger: _MoveLedger,
    capture_directory_fd: int,
    capture_directory_identity: FilesystemIdentity,
) -> None:
    if type(ledger) is not _MoveLedger or ledger.assigned:
        _failstop()
    try:
        directory_stat = os.fstat(capture_directory_fd)
    except BaseException:
        _failstop()
    if (
        not stat.S_ISDIR(directory_stat.st_mode)
        or directory_stat.st_dev != capture_directory_identity.device
        or directory_stat.st_ino != capture_directory_identity.inode
    ):
        _failstop()
    if not hasattr(os, "O_TMPFILE"):
        raise OSError(errno.EOPNOTSUPP, "O_TMPFILE is unavailable")
    flags = os.O_RDWR | os.O_TMPFILE | os.O_CLOEXEC
    guard = _IssuerSignalGuard()
    entered = False
    fd = -1
    try:
        guard.block()
        entered = True
        fd = os.open(
            ".",
            flags,
            0o600,
            dir_fd=capture_directory_fd,
        )
        value = os.fstat(fd)
        descriptor_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        if (
            not stat.S_ISREG(value.st_mode)
            or stat.S_IMODE(value.st_mode) != 0o600
            or value.st_dev != capture_directory_identity.device
            or not descriptor_flags & fcntl.FD_CLOEXEC
        ):
            _failstop()
        ledger.value = _Spool(
            fd,
            FilesystemIdentity(device=value.st_dev, inode=value.st_ino),
        )
        ledger.assigned = True
        fd = -1
    except OSError:
        if entered:
            if fd >= 0:
                _close_exact(fd)
            guard.restore()
        raise
    except (KeyboardInterrupt, SystemExit, GeneratorExit):
        if not entered:
            raise
        if fd >= 0:
            _close_exact(fd)
        guard.restore()
        raise
    except Exception:
        if entered:
            if fd >= 0:
                _close_exact(fd)
            guard.restore()
        _failstop()
    except BaseException:
        if not entered:
            raise
        if fd >= 0:
            _close_exact(fd)
        guard.restore()
        _failstop()
    ledger.interrupted = guard.restore()


def _make_cleanup_permit_surface() -> Tuple[type, object]:
    construction_authority = object()

    class _Permit:
        __slots__ = ("_creator_pid", "_identity", "_state")

        def __init__(self, authority: object, identity: _CleanupPermitIdentity) -> None:
            if authority is not construction_authority:
                raise TypeError("cleanup permits cannot be constructed directly")
            if type(identity) is not _CleanupPermitIdentity:
                raise TypeError("identity must be exact _CleanupPermitIdentity")
            self._creator_pid = os.getpid()
            self._identity = identity
            self._state = "OPEN"

        def __init_subclass__(cls, **kwargs: object) -> None:
            del kwargs
            raise TypeError("_SettledJobCleanupPermit is final")

        def _require_open(self) -> None:
            if os.getpid() != self._creator_pid:
                raise BackendStateError("cleanup permit belongs to another process")
            if self._state != "OPEN":
                raise BackendStateError("cleanup permit is consumed")

        @property
        def identity(self) -> _CleanupPermitIdentity:
            self._require_open()
            return self._identity

        def _consume(self, expected: _CleanupPermitIdentity) -> None:
            self._require_open()
            if type(expected) is not _CleanupPermitIdentity:
                raise TypeError("expected must be exact _CleanupPermitIdentity")
            if self._identity != expected:
                raise BackendStateError("cleanup permit identity mismatch")
            self._state = "CONSUMED"

        __copy__ = _reject_live_copy
        __deepcopy__ = _reject_live_copy
        __reduce__ = _reject_live_copy
        __reduce_ex__ = _reject_live_copy

    def issue(identity: _CleanupPermitIdentity) -> _Permit:
        if type(identity) is not _CleanupPermitIdentity:
            raise TypeError("identity must be exact _CleanupPermitIdentity")
        return _Permit(construction_authority, identity)

    _Permit.__name__ = "_SettledJobCleanupPermit"
    _Permit.__qualname__ = "_SettledJobCleanupPermit"
    return _Permit, issue


_SettledJobCleanupPermit, _issue_cleanup_permit_for_tests = (
    _make_cleanup_permit_surface()
)
del _make_cleanup_permit_surface


class BlockedSpawn:
    """One moved native blocked-child authority owned by its backend."""

    __slots__ = (
        "_state",
        "_creator_pid",
        "_backend",
        "_backend_generation",
        "_key",
        "_spec",
        "_job",
        "_child",
        "_stdout_fd",
        "_stderr_fd",
        "_exec_error_fd",
        "_poll_pidfd",
        "_stdout_spool",
        "_stderr_spool",
        "_process_identity",
        "_start_wall_ns",
        "_start_monotonic_ns",
    )

    _OPEN = "OPEN"
    _CONSUMED = "CONSUMED"

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        del _args, _kwargs
        raise TypeError("BlockedSpawn is created only by SpawnBackend")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("BlockedSpawn is final")

    @classmethod
    def _create(
        cls,
        *,
        backend: "SpawnBackend",
        key: JobCgroupKey,
        spec: GenericProcessSpec,
        job: object,
        child: native.BlockedChild,
        capture_fds: Tuple[int, int, int],
        poll_pidfd: int,
        stdout_spool: _Spool,
        stderr_spool: _Spool,
        process_identity: ProcessIdentity,
        start_wall_ns: int,
        start_monotonic_ns: int,
    ) -> "BlockedSpawn":
        value = object.__new__(cls)
        value._state = cls._CONSUMED
        value._creator_pid = os.getpid()
        value._backend = backend
        value._backend_generation = backend._generation
        value._key = key
        value._spec = spec
        value._job = job
        value._child = child
        value._stdout_fd, value._stderr_fd, value._exec_error_fd = capture_fds
        value._poll_pidfd = poll_pidfd
        value._stdout_spool = stdout_spool
        value._stderr_spool = stderr_spool
        value._process_identity = process_identity
        value._start_wall_ns = start_wall_ns
        value._start_monotonic_ns = start_monotonic_ns
        value._state = cls._OPEN
        return value

    def _require_open(self) -> None:
        if os.getpid() != self._creator_pid:
            raise BackendStateError("BlockedSpawn belongs to another process")
        if self._state != self._OPEN:
            raise BackendStateError("BlockedSpawn is consumed")

    @property
    def job_key(self) -> JobCgroupKey:
        self._require_open()
        return self._key

    @property
    def process_spec_sha256(self) -> str:
        self._require_open()
        return self._spec.spec_sha256

    @property
    def process_identity(self) -> ProcessIdentity:
        self._require_open()
        return self._process_identity

    @property
    def cgroup_identity(self):
        self._require_open()
        return self._job.identity

    def _consume_for(self, backend: "SpawnBackend") -> None:
        self._require_open()
        if (
            backend is not self._backend
            or backend._generation != self._backend_generation
            or backend._active != id(self)
        ):
            raise BackendStateError("BlockedSpawn belongs to another backend")
        self._state = self._CONSUMED

    __copy__ = _reject_live_copy
    __deepcopy__ = _reject_live_copy
    __reduce__ = _reject_live_copy
    __reduce_ex__ = _reject_live_copy

    def __del__(self) -> None:
        if getattr(self, "_state", self._CONSUMED) != self._OPEN:
            return
        if os.getpid() == getattr(self, "_creator_pid", -1):
            _failstop()
        for name in (
            "_stdout_fd",
            "_stderr_fd",
            "_exec_error_fd",
            "_poll_pidfd",
        ):
            _close_after_fork(getattr(self, name, -1))
        for name in ("_stdout_spool", "_stderr_spool"):
            spool = getattr(self, name, None)
            if spool is not None:
                _close_after_fork(getattr(spool, "fd", -1))


class SettledJob:
    """Positive observation plus the still-pinned empty job cgroup."""

    __slots__ = (
        "_state",
        "_creator_pid",
        "_backend",
        "_backend_generation",
        "_key",
        "_job",
        "_observation",
    )

    _OPEN = "OPEN"
    _CONSUMED = "CONSUMED"

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        del _args, _kwargs
        raise TypeError("SettledJob is created only by SpawnBackend")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SettledJob is final")

    @classmethod
    def _create(
        cls,
        *,
        backend: "SpawnBackend",
        key: JobCgroupKey,
        job: object,
        observation: ClosedSpawnObservation,
    ) -> "SettledJob":
        value = object.__new__(cls)
        value._state = cls._CONSUMED
        value._creator_pid = os.getpid()
        value._backend = backend
        value._backend_generation = backend._generation
        value._key = key
        value._job = job
        value._observation = observation
        value._state = cls._OPEN
        return value

    def _require_open(self) -> None:
        if os.getpid() != self._creator_pid:
            raise BackendStateError("SettledJob belongs to another process")
        if self._state != self._OPEN:
            raise BackendStateError("SettledJob is consumed")

    @property
    def observation(self) -> ClosedSpawnObservation:
        self._require_open()
        return self._observation

    def _cleanup_identity(self) -> _CleanupPermitIdentity:
        self._require_open()
        return _CleanupPermitIdentity(
            backend_generation=self._backend_generation,
            job_key=self._key,
            observation_sha256=self._observation.observation_sha256,
        )

    def _consume_for(self, backend: "SpawnBackend") -> None:
        self._require_open()
        if (
            backend is not self._backend
            or backend._generation != self._backend_generation
            or backend._active != id(self)
        ):
            raise BackendStateError("SettledJob belongs to another backend")
        self._state = self._CONSUMED

    __copy__ = _reject_live_copy
    __deepcopy__ = _reject_live_copy
    __reduce__ = _reject_live_copy
    __reduce_ex__ = _reject_live_copy

    def __del__(self) -> None:
        if getattr(self, "_state", self._CONSUMED) != self._OPEN:
            return
        if os.getpid() == getattr(self, "_creator_pid", -1):
            _failstop()


class SpawnBackend:
    """One consumed service authority and one exact job lifecycle at a time."""

    __slots__ = (
        "_state",
        "_creator_pid",
        "_creator_starttime",
        "_generation",
        "_authority",
        "_capture_directory_fd",
        "_capture_directory_identity",
        "_active",
    )

    _IDLE = "IDLE"
    _BLOCKED_OWNED = "BLOCKED_OWNED"
    _SETTLED_PENDING_CLEANUP = "SETTLED_PENDING_CLEANUP"
    _CLOSED = "CLOSED"
    _POISONED_CLOSED = "POISONED_CLOSED"

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        del _args, _kwargs
        raise TypeError("SpawnBackend is created only by open")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SpawnBackend is final")

    @classmethod
    def open(
        cls,
        service_cgroup: ServiceCgroup,
        pinned_capture_directory: int,
    ) -> "SpawnBackend | BackendOpenFailure":
        if type(service_cgroup) is not ServiceCgroup:
            raise TypeError("service_cgroup must be exact ServiceCgroup")
        if type(pinned_capture_directory) is not int or pinned_capture_directory < 0:
            raise TypeError("pinned_capture_directory must be an exact open fd")

        if not _single_threaded():
            raise BackendStateError("SpawnBackend requires an exact single-thread issuer")

        service_lineage = service_cgroup.copied_lineage
        consume_ledger = _MoveLedger()
        capture_ledger = _MoveLedger()
        backend_ledger = _MoveLedger()
        capture_identity: Optional[FilesystemIdentity] = None
        failure_phase: Optional[BackendOpenPhase] = None
        failure_reason: Optional[BackendOpenReason] = None
        failure_errno: Optional[int] = None
        current_phase = BackendOpenPhase.SERVICE_CONSUME

        try:
            consume_guard = _IssuerSignalGuard()
            consume_entered = False
            try:
                consume_guard.block()
                consume_entered = True
                consume_ledger.value = service_cgroup._consume()
                consume_ledger.assigned = True
            except (CgroupStateError, TypeError):
                if consume_entered:
                    consume_guard.restore()
                raise
            except BaseException:
                if consume_entered:
                    consume_guard.restore()
                if consume_ledger.assigned:
                    failure_phase = current_phase
                    failure_reason = BackendOpenReason.ISSUER_INTERRUPTED
                else:
                    # A direct post-consume exception can hide the returned
                    # authority; an interruption before entry owns nothing.
                    if getattr(service_cgroup, "_state", None) != "OPEN":
                        _failstop()
                    raise
            if consume_ledger.assigned:
                if consume_guard._state != consume_guard._RESTORED:
                    consume_interrupted = consume_guard.restore()
                    if consume_interrupted and failure_reason is None:
                        failure_phase = current_phase
                        failure_reason = BackendOpenReason.ISSUER_INTERRUPTED
            elif failure_reason is None:
                _failstop()

            current_phase = BackendOpenPhase.CAPTURE_DIRECTORY_ACQUIRE
            if failure_reason is None:
                capture_guard = _IssuerSignalGuard()
                capture_entered = False
                try:
                    capture_guard.block()
                    capture_entered = True
                    capture_ledger.value = fcntl.fcntl(
                        pinned_capture_directory,
                        fcntl.F_DUPFD_CLOEXEC,
                        _MIN_DUP_FD,
                    )
                    capture_ledger.assigned = True
                except OSError as exc:
                    failure_phase = current_phase
                    failure_reason = (
                        BackendOpenReason.CAPTURE_DIRECTORY_OPEN_FAILED
                    )
                    failure_errno = exc.errno or errno.EIO
                except BaseException:
                    if capture_entered:
                        capture_guard.restore()
                    if capture_ledger.assigned:
                        failure_phase = current_phase
                        failure_reason = BackendOpenReason.ISSUER_INTERRUPTED
                    elif capture_entered:
                        # The injected primitive may have acquired an FD
                        # without returning its number.
                        _failstop()
                    else:
                        raise
                if (
                    capture_entered
                    and capture_guard._state != capture_guard._RESTORED
                ):
                    capture_interrupted = capture_guard.restore()
                    if capture_interrupted and failure_reason is None:
                        failure_phase = current_phase
                        failure_reason = BackendOpenReason.ISSUER_INTERRUPTED

            if failure_reason is None:
                if not capture_ledger.assigned or type(capture_ledger.value) is not int:
                    _failstop()
                capture_fd = capture_ledger.value
                phase_guard = _IssuerSignalGuard()
                phase_entered = False
                current_phase = BackendOpenPhase.CAPTURE_DIRECTORY_ACQUIRE
                try:
                    phase_guard.block()
                    phase_entered = True
                    supplied_stat = os.fstat(pinned_capture_directory)
                    capture_stat = os.fstat(capture_fd)
                    descriptor_flags = fcntl.fcntl(capture_fd, fcntl.F_GETFD)
                    if (
                        not stat.S_ISDIR(capture_stat.st_mode)
                        or (supplied_stat.st_dev, supplied_stat.st_ino)
                        != (capture_stat.st_dev, capture_stat.st_ino)
                        or not descriptor_flags & fcntl.FD_CLOEXEC
                    ):
                        failure_phase = current_phase
                        failure_reason = BackendOpenReason.CAPTURE_DIRECTORY_INVALID
                    else:
                        capture_identity = FilesystemIdentity(
                            device=capture_stat.st_dev,
                            inode=capture_stat.st_ino,
                        )
                        current_phase = BackendOpenPhase.BACKEND_ALLOCATION
                        backend_ledger.value = object.__new__(cls)
                        backend_ledger.assigned = True
                        value = backend_ledger.value
                        # Arm only after every live authority is recorded.
                        value._state = cls._CLOSED
                        value._creator_pid = os.getpid()
                        value._creator_starttime = (
                            consume_ledger.value.invocation_lineage.main_starttime
                        )
                        value._generation = next(_BACKEND_GENERATIONS)
                        value._authority = consume_ledger.value
                        value._capture_directory_fd = capture_fd
                        value._capture_directory_identity = capture_identity
                        value._active = None
                        value._state = cls._IDLE
                except Exception:
                    if failure_reason is None:
                        failure_phase = current_phase
                        failure_reason = (
                            BackendOpenReason.BACKEND_ALLOCATION_FAILED
                            if current_phase is BackendOpenPhase.BACKEND_ALLOCATION
                            else BackendOpenReason.CAPTURE_DIRECTORY_INVALID
                        )
                except BaseException:
                    if phase_entered:
                        phase_guard.restore()
                    if failure_reason is None:
                        failure_phase = current_phase
                        failure_reason = BackendOpenReason.ISSUER_INTERRUPTED
                if phase_entered and phase_guard._state != phase_guard._RESTORED:
                    phase_interrupted = phase_guard.restore()
                    if phase_interrupted and failure_reason is None:
                        failure_phase = current_phase
                        failure_reason = BackendOpenReason.ISSUER_INTERRUPTED
            if failure_reason is None:
                if not backend_ledger.assigned:
                    _failstop()
                return backend_ledger.value
        except (CgroupStateError, TypeError):
            if not consume_ledger.assigned:
                raise
            _failstop()
        except BaseException:
            if not consume_ledger.assigned:
                raise
            if failure_reason is None:
                failure_phase = current_phase
                failure_reason = BackendOpenReason.ISSUER_INTERRUPTED

        if failure_reason is not None:
            if failure_phase is None:
                _failstop()
            try:
                return cls._finish_open_failure(
                    authority=consume_ledger.value,
                    capture_ledger=capture_ledger,
                    backend_ledger=backend_ledger,
                    phase=failure_phase,
                    reason=failure_reason,
                    service_lineage=service_lineage,
                    capture_directory_identity=capture_identity,
                    error_number=failure_errno,
                )
            except BaseException:
                _failstop()
        _failstop()

    @classmethod
    def _finish_open_failure(
        cls,
        *,
        authority: object,
        capture_ledger: _MoveLedger,
        backend_ledger: _MoveLedger,
        phase: BackendOpenPhase,
        reason: BackendOpenReason,
        service_lineage: object,
        capture_directory_identity: Optional[FilesystemIdentity],
        error_number: Optional[int],
    ) -> BackendOpenFailure:
        result_ledger = _MoveLedger()
        guard = _IssuerSignalGuard()
        entered = False
        try:
            guard.block()
            entered = True
            if backend_ledger.assigned:
                backend = backend_ledger.value
                backend._state = cls._CLOSED
                backend._capture_directory_fd = -1
                backend._authority = None
            if capture_ledger.assigned:
                _close_exact(capture_ledger.value)
                capture_ledger.assigned = False
                capture_ledger.value = None
            authority._close()
            result_ledger.value = _make_backend_open_failure(
                phase=phase,
                reason=reason,
                service_lineage=service_lineage,
                capture_directory_acquired=(
                    phase is BackendOpenPhase.BACKEND_ALLOCATION
                ),
                capture_directory_identity=(
                    capture_directory_identity
                    if phase is BackendOpenPhase.BACKEND_ALLOCATION
                    else None
                ),
                error_number=error_number,
            )
            result_ledger.assigned = True
        except BaseException:
            if entered:
                guard.restore()
            _failstop()
        try:
            guard.restore()
            if not result_ledger.assigned:
                _failstop()
            return result_ledger.value
        except Exception:
            _failstop()
        except BaseException:
            if not result_ledger.assigned:
                _failstop()
            return result_ledger.value

    def _require_creator(self) -> None:
        if os.getpid() != self._creator_pid:
            raise BackendStateError("SpawnBackend belongs to another process")

    def _require_state(self, expected: str) -> None:
        self._require_creator()
        if self._state != expected:
            raise BackendStateError(
                f"SpawnBackend is {self._state}, expected {expected}"
            )

    @property
    def state(self) -> str:
        self._require_creator()
        return self._state

    def _close_spools(self, *spools: Optional[_Spool]) -> None:
        for spool in spools:
            if spool is not None:
                spool.close()

    def _poison_without_job(self, *spools: Optional[_Spool]) -> None:
        self._close_spools(*spools)
        try:
            self._authority._close()
        except BaseException:
            _failstop()
        _close_exact(self._capture_directory_fd)
        self._capture_directory_fd = -1
        self._authority = None
        self._state = self._POISONED_CLOSED

    def _prehandle_without_job(
        self,
        *,
        phase: PreHandlePhase,
        reason: PreHandleReason,
        spools: Tuple[Optional[_Spool], ...] = (),
        completion_ledger: Optional[_MoveLedger] = None,
    ) -> PreHandleFailure:
        if not _single_threaded():
            _failstop()
        guard = _IssuerSignalGuard()
        try:
            guard.block()
            self._poison_without_job(*spools)
            result = PreHandleFailure(
                phase=phase,
                reason=reason,
                native_called=False,
                native_handle_acquired=False,
                child_creation=ChildCreation.NOT_CALLED,
                job_cgroup_created=False,
                job_cgroup_identity=None,
                initial_cgroup_events=None,
                final_cgroup_events=None,
                stdout_availability=StreamAvailability.NOT_STARTED,
                stdout=None,
                stderr_availability=StreamAvailability.NOT_STARTED,
                stderr=None,
                exec_error_availability=StreamAvailability.NOT_STARTED,
                exec_error=None,
            )
            if completion_ledger is not None:
                completion_ledger.value = result
                completion_ledger.assigned = True
        except BaseException:
            guard.restore()
            _failstop()
        guard.restore()
        return result

    def _prehandle_with_job(
        self,
        *,
        job: object,
        phase: PreHandlePhase,
        reason: PreHandleReason,
        native_called: bool,
        child_creation: ChildCreation,
        spools: Tuple[_Spool, _Spool],
        completion_ledger: Optional[_MoveLedger] = None,
    ) -> PreHandleFailure:
        guard = _IssuerSignalGuard()
        try:
            guard.block()
            identity = job.identity
            initial = job.initial_events
            final = job.close_retained()
            self._close_spools(*spools)
            self._authority._close()
            _close_exact(self._capture_directory_fd)
            self._capture_directory_fd = -1
            self._authority = None
            self._state = self._POISONED_CLOSED
            result = PreHandleFailure(
                phase=phase,
                reason=reason,
                native_called=native_called,
                native_handle_acquired=False,
                child_creation=child_creation,
                job_cgroup_created=True,
                job_cgroup_identity=identity,
                initial_cgroup_events=initial,
                final_cgroup_events=final,
                stdout_availability=StreamAvailability.NOT_STARTED,
                stdout=None,
                stderr_availability=StreamAvailability.NOT_STARTED,
                stderr=None,
                exec_error_availability=StreamAvailability.NOT_STARTED,
                exec_error=None,
            )
            if completion_ledger is not None:
                completion_ledger.value = result
                completion_ledger.assigned = True
        except BaseException:
            guard.restore()
            _failstop()
        guard.restore()
        return result

    def _assemble_handle(
        self,
        assembly: _HandleAssemblyLedger,
        *,
        start_wall_ns: int,
        start_monotonic_ns: int,
        issuer_interrupted: bool,
        recovering: bool = False,
        completion_ledger: Optional[_MoveLedger] = None,
    ) -> "BlockedSpawn | ContainedSpawnFailure":
        guard = _IssuerSignalGuard()
        entered = False
        stage = "BLOCK"
        direct_issuer = False
        try:
            guard.block()
            entered = True
            child = assembly.child
            if type(child) is not native.BlockedChild:
                _failstop()

            if not assembly.capture_assigned:
                stage = "CAPTURE_MOVE"
                assembly.capture_fds = child.take_capture_fds()
                assembly.capture_assigned = True
            if not assembly.pidfd_assigned:
                stage = "PIDFD_MOVE"
                assembly.poll_pidfd = child.dup_pidfd()
                assembly.pidfd_assigned = True

            stage = "VALIDATE"
            capture_fds = assembly.capture_fds
            poll_pidfd = assembly.poll_pidfd
            if (
                type(capture_fds) is not tuple
                or len(capture_fds) != 3
                or any(type(fd) is not int or fd < 0 for fd in capture_fds)
                or len(set(capture_fds)) != 3
                or type(poll_pidfd) is not int
                or poll_pidfd < 0
                or poll_pidfd in capture_fds
            ):
                _failstop()
            for fd in capture_fds:
                if not stat.S_ISFIFO(os.fstat(fd).st_mode):
                    _failstop()
                _set_nonblocking(fd)
            pidfd_stat = os.fstat(poll_pidfd)
            if not fcntl.fcntl(poll_pidfd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC:
                _failstop()
            pid = child.pid
            if type(pid) is not int or pid <= 0 or child.state != "BLOCKED":
                _failstop()
            assembly.job._require_blocked_leader(pid)
            assembly.process_identity = ProcessIdentity(
                pid=pid,
                proc_starttime_ticks=_process_starttime(pid),
                pidfd_device=pidfd_stat.st_dev,
                pidfd_inode=pidfd_stat.st_ino,
                creator_pid=self._creator_pid,
                creator_starttime_ticks=self._creator_starttime,
            )

            if not assembly.blocked_assigned:
                stage = "WRAPPER_CREATE"
                assembly.blocked = BlockedSpawn._create(
                    backend=self,
                    key=assembly.key,
                    spec=assembly.spec,
                    job=assembly.job,
                    child=child,
                    capture_fds=capture_fds,
                    poll_pidfd=poll_pidfd,
                    stdout_spool=assembly.stdout_spool,
                    stderr_spool=assembly.stderr_spool,
                    process_identity=assembly.process_identity,
                    start_wall_ns=start_wall_ns,
                    start_monotonic_ns=start_monotonic_ns,
                )
                assembly.blocked_assigned = True
            stage = "BACKEND_COMMIT"
            blocked = assembly.blocked
            self._active = id(blocked)
            self._state = self._BLOCKED_OWNED
        except BaseException:
            direct_issuer = True

        if entered and guard._state != guard._RESTORED:
            restore_interrupted = guard.restore()
        else:
            restore_interrupted = direct_issuer

        if direct_issuer:
            if stage == "CAPTURE_MOVE" and not assembly.capture_assigned:
                _failstop()
            if stage == "PIDFD_MOVE" and not assembly.pidfd_assigned:
                _failstop()
            if stage == "WRAPPER_CREATE" and not assembly.blocked_assigned:
                _failstop()
            if recovering:
                _failstop()
            return self._assemble_handle(
                assembly,
                start_wall_ns=start_wall_ns,
                start_monotonic_ns=start_monotonic_ns,
                issuer_interrupted=True,
                recovering=True,
                completion_ledger=completion_ledger,
            )

        if not assembly.blocked_assigned:
            _failstop()
        blocked = assembly.blocked
        if issuer_interrupted or restore_interrupted:
            settlement = _ConsumedBlockedLedger(
                blocked,
                ContainedSpawnReason.ISSUER_INTERRUPTED,
            )
            if completion_ledger is not None:
                settlement.completion = completion_ledger
            return self._consume_and_drive_blocked(settlement)
        if completion_ledger is not None:
            completion_ledger.value = blocked
            completion_ledger.assigned = True
        return blocked

    def start_blocked(
        self,
        key: JobCgroupKey,
        spec: GenericProcessSpec,
    ) -> "BlockedSpawn | PreHandleFailure | ContainedSpawnFailure":
        if type(key) is not JobCgroupKey:
            raise TypeError("key must be exact JobCgroupKey")
        if type(spec) is not GenericProcessSpec:
            raise TypeError("spec must be exact GenericProcessSpec")
        self._require_state(self._IDLE)

        # Open already moved live authority into this backend.  Thread-shape
        # drift can no longer be returned as an ordinary spec failure because
        # a thread-local mask cannot guard the close/settlement transaction.
        if not _single_threaded():
            _failstop()

        ledger = _StartLedger(key, spec)
        try:
            value = self._start_blocked_phases(ledger)
            ledger.result.value = value
            ledger.result.assigned = True
            return value
        except Exception:
            _failstop()
        except BaseException:
            try:
                return self._recover_start_interruption(ledger)
            except BaseException:
                _failstop()

    def _recover_start_interruption(
        self,
        ledger: _StartLedger,
    ) -> "BlockedSpawn | PreHandleFailure | ContainedSpawnFailure":
        if ledger.result.assigned:
            value = ledger.result.value
            if type(value) is BlockedSpawn:
                return self.settle_blocked(
                    value,
                    ContainedSpawnReason.ISSUER_INTERRUPTED,
                )
            return value
        assembly = ledger.assembly
        if assembly.child is not _UNSET_CHILD:
            ledger.native_called = True
            ledger.phase = PreHandlePhase.NATIVE_NO_HANDLE
            if assembly.blocked_assigned:
                return self.settle_blocked(
                    assembly.blocked,
                    ContainedSpawnReason.ISSUER_INTERRUPTED,
                )
            return self._assemble_handle(
                assembly,
                start_wall_ns=ledger.start_wall_ns,
                start_monotonic_ns=ledger.start_monotonic_ns,
                issuer_interrupted=True,
                completion_ledger=ledger.result,
            )
        spools = tuple(
            item.value
            for item in (ledger.stdout, ledger.stderr)
            if item.assigned
        )
        if ledger.job.assigned:
            if len(spools) != 2:
                _failstop()
            native_called = (
                ledger.native_called
                or ledger.prehandle_reason is PreHandleReason.NATIVE_NO_HANDLE
            )
            return self._prehandle_with_job(
                job=ledger.job.value,
                phase=(
                    PreHandlePhase.NATIVE_NO_HANDLE
                    if native_called
                    else PreHandlePhase.PRE_NATIVE_READY
                ),
                reason=(
                    ledger.prehandle_reason
                    or PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE
                ),
                native_called=native_called,
                child_creation=(
                    ChildCreation.NATIVE_INTERNAL_SETTLED
                    if native_called
                    else ChildCreation.NOT_CALLED
                ),
                spools=spools,
                completion_ledger=ledger.result,
            )
        return self._prehandle_without_job(
            phase=ledger.phase,
            reason=(
                ledger.prehandle_reason
                or PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE
            ),
            spools=spools,
            completion_ledger=ledger.result,
        )

    def _start_blocked_phases(
        self,
        ledger: _StartLedger,
    ) -> "BlockedSpawn | PreHandleFailure | ContainedSpawnFailure":
        key = ledger.key
        spec = ledger.spec
        stdout_ledger = ledger.stdout
        stderr_ledger = ledger.stderr

        try:
            _open_spool_into(
                stdout_ledger,
                self._capture_directory_fd,
                self._capture_directory_identity,
            )
            if stdout_ledger.interrupted:
                return self._prehandle_without_job(
                    phase=PreHandlePhase.CAPTURE_PREPARE,
                    reason=PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
                    spools=(stdout_ledger.value,),
                    completion_ledger=ledger.result,
                )
            _open_spool_into(
                stderr_ledger,
                self._capture_directory_fd,
                self._capture_directory_identity,
            )
        except OSError as exc:
            ledger.prehandle_reason = _capture_open_reason(exc.errno or errno.EIO)
            return self._prehandle_without_job(
                phase=PreHandlePhase.CAPTURE_PREPARE,
                reason=ledger.prehandle_reason,
                spools=(stdout_ledger.value, stderr_ledger.value),
                completion_ledger=ledger.result,
            )
        except BaseException:
            return self._prehandle_without_job(
                phase=PreHandlePhase.CAPTURE_PREPARE,
                reason=PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
                spools=(stdout_ledger.value, stderr_ledger.value),
                completion_ledger=ledger.result,
            )
        if not stdout_ledger.assigned or not stderr_ledger.assigned:
            _failstop()
        stdout_spool = stdout_ledger.value
        stderr_spool = stderr_ledger.value
        ledger.assembly.stdout_spool = stdout_spool
        ledger.assembly.stderr_spool = stderr_spool
        if stderr_ledger.interrupted:
            return self._prehandle_without_job(
                phase=PreHandlePhase.CAPTURE_PREPARE,
                reason=PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
                spools=(stdout_spool, stderr_spool),
                completion_ledger=ledger.result,
            )
        if stdout_spool.identity == stderr_spool.identity:
            _failstop()

        ledger.phase = PreHandlePhase.JOB_CREATE
        job_ledger = ledger.job
        job_guard = _IssuerSignalGuard()
        job_entered = False
        job_issuer = False
        try:
            job_guard.block()
            job_entered = True
            job_ledger.value = self._authority._create_job(key)
            job_ledger.assigned = True
        except OSError:
            ledger.prehandle_reason = PreHandleReason.JOB_CREATE_FAILED
            if job_entered:
                job_guard.restore()
            return self._prehandle_without_job(
                phase=PreHandlePhase.JOB_CREATE,
                reason=ledger.prehandle_reason,
                spools=(stdout_spool, stderr_spool),
                completion_ledger=ledger.result,
            )
        except (CgroupIntegrityError, CgroupStateError):
            if job_entered:
                job_guard.restore()
            _failstop()
        except BaseException:
            if job_entered:
                job_guard.restore()
            job_issuer = True
        job_interrupted = False
        if job_entered and job_guard._state != job_guard._RESTORED:
            job_interrupted = job_guard.restore()
        if not job_ledger.assigned:
            if job_issuer and not job_entered:
                return self._prehandle_without_job(
                    phase=PreHandlePhase.JOB_CREATE,
                    reason=PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
                    spools=(stdout_spool, stderr_spool),
                    completion_ledger=ledger.result,
                )
            _failstop()
        job = job_ledger.value
        ledger.assembly.job = job
        if job_issuer or job_interrupted:
            return self._prehandle_with_job(
                job=job,
                phase=PreHandlePhase.JOB_CREATE,
                reason=PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
                native_called=False,
                child_creation=ChildCreation.NOT_CALLED,
                spools=(stdout_spool, stderr_spool),
                completion_ledger=ledger.result,
            )

        ledger.phase = PreHandlePhase.PRE_NATIVE_READY
        try:
            ledger.start_wall_ns = time.time_ns()
            ledger.start_monotonic_ns = time.monotonic_ns()
        except BaseException:
            return self._prehandle_with_job(
                job=job,
                phase=PreHandlePhase.PRE_NATIVE_READY,
                reason=PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
                native_called=False,
                child_creation=ChildCreation.NOT_CALLED,
                spools=(stdout_spool, stderr_spool),
                completion_ledger=ledger.result,
            )

        borrow_ledger = ledger.borrow
        borrow_guard = _IssuerSignalGuard()
        borrow_entered = False
        borrow_issuer = False
        try:
            borrow_guard.block()
            borrow_entered = True
            borrow_ledger.value = job._consume_spawn_dirfd_borrow()
            borrow_ledger.assigned = True
        except (CgroupIntegrityError, CgroupStateError, OSError, TypeError, ValueError):
            if borrow_entered:
                borrow_guard.restore()
            _failstop()
        except BaseException:
            if borrow_entered:
                borrow_guard.restore()
            borrow_issuer = True
        borrow_interrupted = False
        if borrow_entered and borrow_guard._state != borrow_guard._RESTORED:
            borrow_interrupted = borrow_guard.restore()
        if borrow_issuer and not borrow_ledger.assigned:
            return self._prehandle_with_job(
                job=job,
                phase=PreHandlePhase.PRE_NATIVE_READY,
                reason=PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
                native_called=False,
                child_creation=ChildCreation.NOT_CALLED,
                spools=(stdout_spool, stderr_spool),
                completion_ledger=ledger.result,
            )
        if not borrow_ledger.assigned or type(borrow_ledger.value) is not int:
            _failstop()
        if borrow_issuer or borrow_interrupted:
            return self._prehandle_with_job(
                job=job,
                phase=PreHandlePhase.PRE_NATIVE_READY,
                reason=PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
                native_called=False,
                child_creation=ChildCreation.NOT_CALLED,
                spools=(stdout_spool, stderr_spool),
                completion_ledger=ledger.result,
            )

        assembly = ledger.assembly
        try:
            native_spawn = native.spawn_blocked
            native_borrow = borrow_ledger.value
            native_executable = spec.executable
            native_argv = spec.argv
            native_environment = spec.environment
            native_cwd = spec.cwd
        except BaseException:
            return self._prehandle_with_job(
                job=job,
                phase=PreHandlePhase.PRE_NATIVE_READY,
                reason=PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
                native_called=False,
                child_creation=ChildCreation.NOT_CALLED,
                spools=(stdout_spool, stderr_spool),
                completion_ledger=ledger.result,
            )
        native_guard = _IssuerSignalGuard()
        native_issuer = False
        try:
            native_guard.block()
        except BaseException:
            return self._prehandle_with_job(
                job=job,
                phase=PreHandlePhase.PRE_NATIVE_READY,
                reason=PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
                native_called=False,
                child_creation=ChildCreation.NOT_CALLED,
                spools=(stdout_spool, stderr_spool),
                completion_ledger=ledger.result,
            )
        try:
            assembly.child = native_spawn(
                native_borrow,
                native_executable,
                native_argv,
                native_environment,
                native_cwd,
            )
            ledger.native_called = True
            ledger.phase = PreHandlePhase.NATIVE_NO_HANDLE
        except Exception:
            ledger.prehandle_reason = PreHandleReason.NATIVE_NO_HANDLE
            ledger.native_called = True
            ledger.phase = PreHandlePhase.NATIVE_NO_HANDLE
        except BaseException:
            native_issuer = True
            ledger.native_called = True
            ledger.phase = PreHandlePhase.NATIVE_NO_HANDLE
        native_interrupted = native_guard.restore()
        native_failed = ledger.prehandle_reason is PreHandleReason.NATIVE_NO_HANDLE
        if assembly.child is _UNSET_CHILD:
            return self._prehandle_with_job(
                job=job,
                phase=PreHandlePhase.NATIVE_NO_HANDLE,
                reason=(
                    ledger.prehandle_reason
                    or PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE
                ),
                native_called=ledger.native_called or native_failed,
                child_creation=ChildCreation.NATIVE_INTERNAL_SETTLED,
                spools=(stdout_spool, stderr_spool),
                completion_ledger=ledger.result,
            )
        if native_failed or type(assembly.child) is not native.BlockedChild:
            _failstop()
        return self._assemble_handle(
            assembly,
            start_wall_ns=ledger.start_wall_ns,
            start_monotonic_ns=ledger.start_monotonic_ns,
            issuer_interrupted=native_interrupted or native_issuer,
            completion_ledger=ledger.result,
        )

    def _commit_cgroup_events(
        self,
        ledger: _DrainAttemptLedger,
    ) -> object:
        """Read and record one cgroup fact before issuer delivery resumes."""

        event_guard = _IssuerSignalGuard()
        entered = False
        try:
            event_guard.block()
            entered = True
            events = ledger.job._read_events()
            if events.frozen != 0:
                _failstop()
            ledger.final_events = events
            if events.populated != 0 and ledger.wait_fact is not None:
                ledger.remember_failure(
                    ContainedSpawnReason.DESCENDANT_SURVIVED,
                    ledger.current_phase,
                    kill=False,
                )
                ledger.current_phase = (
                    ContainedSpawnPhase.SETTLING_DESCENDANTS
                )
        except Exception:
            if entered:
                event_guard.restore()
            _failstop()
        except BaseException:
            if entered:
                event_guard.restore()
            raise
        interrupted = event_guard.restore()
        if events.populated != 0 and ledger.wait_fact is not None:
            ledger.kill_containment()
        if interrupted:
            ledger.remember_issuer()
        return events

    def _dispatch_drain_iteration(self, ledger: _DrainAttemptLedger) -> None:
        """Build, poll and completely dispatch one resumable ready snapshot."""

        poller = select.poll()
        pipe_mask = select.POLLIN | select.POLLHUP | select.POLLERR
        for stream in ledger.streams.values():
            if not stream.eof:
                poller.register(stream.fd, pipe_mask)
        if ledger.wait_fact is None:
            poller.register(
                ledger.poll_pidfd,
                select.POLLIN | select.POLLERR,
            )
        if ledger.final_events is None or ledger.final_events.populated != 0:
            poller.register(
                ledger.events_fd,
                getattr(select, "POLLPRI", 0) | select.POLLERR,
            )
        ready = poller.poll()
        seen_ready = set()
        for fd, mask in ready:
            if type(fd) is not int or type(mask) is not int or fd in seen_ready:
                _failstop()
            seen_ready.add(fd)
            stream = ledger.streams.get(fd)
            if stream is not None:
                if stream.eof or stream.fd != fd:
                    _failstop()
                if mask & getattr(select, "POLLNVAL", 0):
                    _failstop()
                read_interrupted, storage_failed = _drain_one_stream_snapshot(
                    stream
                )
                if storage_failed:
                    ledger.remember_failure(
                        ContainedSpawnReason.CAPTURE_FAILED,
                        ledger.current_phase,
                        kill=True,
                    )
                if read_interrupted:
                    ledger.remember_failure(
                        ContainedSpawnReason.ISSUER_INTERRUPTED,
                        ledger.current_phase,
                        kill=True,
                    )
                continue

            if fd == ledger.poll_pidfd and ledger.wait_fact is None:
                authority_bad = (
                    getattr(select, "POLLNVAL", 0)
                    | select.POLLERR
                    | select.POLLHUP
                )
                if mask & authority_bad:
                    _failstop()
                terminal_interrupted = _drain_terminal_snapshot(
                    ledger.child,
                    ledger.poll_pidfd,
                    ledger.terminal,
                )
                if ledger.terminal.phase_committed:
                    ledger.current_phase = ContainedSpawnPhase.LEADER_TERMINAL
                if terminal_interrupted:
                    ledger.remember_failure(
                        ContainedSpawnReason.ISSUER_INTERRUPTED,
                        ledger.terminal.interruption_phase
                        or ledger.current_phase,
                        kill=True,
                    )
                if not ledger.terminal.reaped:
                    continue
                if not ledger.terminal.pidfd_closed:
                    _failstop()
                ledger.wait_fact = ledger.terminal.wait_fact
                ledger.poll_pidfd = -1
                ledger.current_phase = (
                    ContainedSpawnPhase.LEADER_REAPED_DRAINING
                )
                events = self._commit_cgroup_events(ledger)
                if events.populated != 0:
                    if ledger.failure_reason is None:
                        _failstop()
                continue

            if fd == ledger.events_fd:
                authority_bad = (
                    getattr(select, "POLLNVAL", 0)
                    | select.POLLERR
                    | select.POLLHUP
                )
                if mask & authority_bad:
                    _failstop()
                # A pidfd item earlier in this same snapshot may already have
                # proved empty; the remaining ordinary POLLPRI is then stale.
                if (
                    ledger.final_events is not None
                    and ledger.final_events.populated == 0
                ):
                    continue
                self._commit_cgroup_events(ledger)
                continue
            _failstop()

    def _drain_attempt(
        self,
        ledger: _DrainAttemptLedger,
        result_ledger: _MoveLedger,
    ) -> _DrainResult:
        if type(result_ledger) is not _MoveLedger or result_ledger.assigned:
            _failstop()
        blocked = ledger.blocked
        while not ledger.complete:
            try:
                self._dispatch_drain_iteration(ledger)
            except InterruptedError:
                continue
            except Exception:
                _failstop()
            except BaseException:
                ledger.remember_issuer()
                continue
        if ledger.poll_pidfd >= 0:
            _failstop()
        try:
            proved_final_events = ledger.job._final_empty()
        except Exception:
            _failstop()
        except BaseException:
            ledger.remember_issuer()
            raise
        if ledger.final_events is None:
            _failstop()

        stdout_stream = ledger.streams[blocked._stdout_fd]
        stderr_stream = ledger.streams[blocked._stderr_fd]
        exec_stream = ledger.streams[blocked._exec_error_fd]
        stdout = stdout_stream.finish()
        stderr = stderr_stream.finish()
        exec_error = exec_stream.finish()
        if exec_stream.finish_interrupted:
            _failstop()
        if stdout_stream.storage_failed or stderr_stream.storage_failed:
            ledger.remember_failure(
                ContainedSpawnReason.CAPTURE_FAILED,
                ledger.current_phase,
                kill=False,
            )
        if stdout_stream.finish_interrupted or stderr_stream.finish_interrupted:
            ledger.remember_failure(
                ContainedSpawnReason.ISSUER_INTERRUPTED,
                ledger.current_phase,
                kill=False,
            )
        if exec_error is None:
            _failstop()
        if stdout is None or stderr is None:
            if ledger.failure_reason is None:
                ledger.failure_reason = ContainedSpawnReason.CAPTURE_FAILED
                ledger.failure_phase = ledger.current_phase

        exec_stage = exec_errno = None
        decoded = _decode_exec_error(exec_error.data)
        if decoded is not None:
            exec_stage, exec_errno = decoded
            if ledger.wait_fact.return_code != 127:
                _failstop()
            if ledger.failure_phase in (
                ContainedSpawnPhase.BLOCKED,
                ContainedSpawnPhase.SETTLING_BLOCKED,
            ):
                _failstop()
            if ledger.failure_reason is None:
                ledger.failure_reason = ContainedSpawnReason.EXEC_FAILED
                ledger.failure_phase = ContainedSpawnPhase.LEADER_REAPED_DRAINING

        result_guard = _IssuerSignalGuard()
        try:
            result_guard.block()
            result_ledger.value = _DrainResult(
                wait_fact=ledger.wait_fact,
                stdout=stdout,
                stderr=stderr,
                exec_error=exec_error,
                final_events=proved_final_events,
                failure_reason=ledger.failure_reason,
                failure_phase=ledger.failure_phase,
                exec_error_stage=exec_stage,
                exec_error_errno=exec_errno,
            )
            result_ledger.assigned = True
        except BaseException:
            result_guard.restore()
            _failstop()
        try:
            interrupted = result_guard.restore()
        except BaseException:
            interrupted = True
        if not result_ledger.assigned:
            _failstop()
        if interrupted and result_ledger.value.failure_reason is None:
            result_ledger.value.failure_reason = (
                ContainedSpawnReason.ISSUER_INTERRUPTED
            )
            result_ledger.value.failure_phase = ledger.current_phase
        return result_ledger.value

    def _close_failed_attempt(
        self,
        blocked: BlockedSpawn,
        result: _DrainResult,
        completion_ledger: Optional[_MoveLedger] = None,
    ) -> ContainedSpawnFailure:
        if result.failure_reason is None or result.failure_phase is None:
            _failstop()
        failure_ledger = _MoveLedger()
        close_guard = _IssuerSignalGuard()
        try:
            close_guard.block()
            cgroup_identity = blocked._job.identity
            initial_events = blocked._job.initial_events
            final_events = blocked._job.close_retained()
            self._authority._close()
            _close_exact(self._capture_directory_fd)
            self._capture_directory_fd = -1
            self._authority = None
            self._active = None
            self._state = self._POISONED_CLOSED

            def availability(value: Optional[CapturedStream]) -> StreamAvailability:
                return (
                    StreamAvailability.COMPLETE
                    if value is not None
                    else StreamAvailability.UNAVAILABLE
                )

            failure_ledger.value = ContainedSpawnFailure(
                phase=result.failure_phase,
                reason=result.failure_reason,
                opaque_job_key=blocked._spec.opaque_job_key,
                process_spec_sha256=blocked._spec.spec_sha256,
                process_identity=blocked._process_identity,
                wait_fact=result.wait_fact,
                cgroup_identity=cgroup_identity,
                initial_cgroup_events=initial_events,
                final_cgroup_events=final_events,
                stdout_availability=availability(result.stdout),
                stdout=result.stdout,
                stderr_availability=availability(result.stderr),
                stderr=result.stderr,
                exec_error_availability=availability(result.exec_error),
                exec_error=result.exec_error,
                exec_error_stage=result.exec_error_stage,
                exec_error_errno=result.exec_error_errno,
            )
            failure_ledger.assigned = True
            if completion_ledger is not None:
                completion_ledger.value = failure_ledger.value
                completion_ledger.assigned = True
            self._clear_consumed_blocked(blocked)
        except BaseException:
            close_guard.restore()
            _failstop()
        close_guard.restore()
        if not failure_ledger.assigned:
            _failstop()
        return failure_ledger.value

    def _finish_drained_attempt(
        self,
        blocked: BlockedSpawn,
        result: _DrainResult,
        completion_ledger: Optional[_MoveLedger] = None,
    ) -> "SettledJob | ContainedSpawnFailure":
        if result.failure_reason is not None:
            return self._close_failed_attempt(
                blocked,
                result,
                completion_ledger,
            )
        if result.stdout is None or result.stderr is None or result.exec_error is None:
            _failstop()
        if result.exec_error.data != b"":
            _failstop()
        positive = _PositiveCommitLedger(blocked, result)
        commit_guard: Optional[_IssuerSignalGuard] = None
        commit_entered = False
        commit_restored = False
        try:
            positive.final_events = blocked._job._final_empty()
            positive.observation = ClosedSpawnObservation.create(
                spec=blocked._spec,
                start_wall_ns=blocked._start_wall_ns,
                end_wall_ns=time.time_ns(),
                start_monotonic_ns=blocked._start_monotonic_ns,
                end_monotonic_ns=time.monotonic_ns(),
                process_identity=blocked._process_identity,
                wait_fact=result.wait_fact,
                stdout=result.stdout,
                stderr=result.stderr,
                cgroup_identity=blocked._job.identity,
                initial_cgroup_events=blocked._job.initial_events,
                final_cgroup_events=positive.final_events,
            )
            commit_guard = _IssuerSignalGuard()
            commit_guard.block()
            commit_entered = True
            positive.settled.value = SettledJob._create(
                backend=self,
                key=blocked._key,
                job=blocked._job,
                observation=positive.observation,
            )
            positive.settled.assigned = True
            settled = positive.settled.value
            self._active = id(settled)
            self._state = self._SETTLED_PENDING_CLEANUP
            positive.backend_committed = True
            if completion_ledger is not None:
                completion_ledger.value = settled
                completion_ledger.assigned = True
            commit_interrupted = commit_guard.interrupted()
            if not commit_interrupted:
                self._clear_consumed_blocked(blocked)
                positive.blocked_cleared = True
            if commit_guard.restore():
                commit_interrupted = True
            commit_restored = True
            if commit_interrupted:
                return self._rollback_settled_commit(
                    settled,
                    blocked,
                    result,
                    completion_ledger,
                )
            return settled
        except Exception:
            _failstop()
        except BaseException:
            if (
                commit_guard is not None
                and commit_entered
                and not commit_restored
            ):
                if (
                    getattr(commit_guard, "_state", None)
                    == commit_guard._RESTORED
                ):
                    commit_restored = True
                else:
                    try:
                        commit_guard.restore()
                        commit_restored = True
                    except BaseException:
                        _failstop()
            if positive.settled.assigned:
                return self._rollback_settled_commit(
                    positive.settled.value,
                    blocked,
                    result,
                    completion_ledger,
                )
            result.failure_reason = ContainedSpawnReason.ISSUER_INTERRUPTED
            result.failure_phase = ContainedSpawnPhase.LEADER_REAPED_DRAINING
            return self._close_failed_attempt(
                blocked,
                result,
                completion_ledger,
            )

    def _rollback_settled_commit(
        self,
        settled: SettledJob,
        blocked: BlockedSpawn,
        result: _DrainResult,
        completion_ledger: Optional[_MoveLedger] = None,
    ) -> ContainedSpawnFailure:
        rollback_guard = _IssuerSignalGuard()
        try:
            rollback_guard.block()
            if blocked._job is None:
                blocked._job = settled._job
            settled._state = settled._CONSUMED
            settled._backend = None
            settled._job = None
            self._active = None
            self._state = self._BLOCKED_OWNED
            result.failure_reason = ContainedSpawnReason.ISSUER_INTERRUPTED
            result.failure_phase = ContainedSpawnPhase.LEADER_REAPED_DRAINING
            failure = self._close_failed_attempt(
                blocked,
                result,
                completion_ledger,
            )
        except BaseException:
            rollback_guard.restore()
            _failstop()
        rollback_guard.restore()
        return failure

    @staticmethod
    def _clear_consumed_blocked(blocked: BlockedSpawn) -> None:
        blocked._backend = None
        blocked._job = None
        blocked._child = None
        blocked._stdout_fd = -1
        blocked._stderr_fd = -1
        blocked._exec_error_fd = -1
        blocked._poll_pidfd = -1
        blocked._stdout_spool = None
        blocked._stderr_spool = None

    def _consume_and_drive_blocked(
        self,
        ledger: _ConsumedBlockedLedger,
    ) -> "SettledJob | ContainedSpawnFailure":
        move_guard = _IssuerSignalGuard()
        move_entered = False
        move_restored = False
        try:
            move_guard.block()
            move_entered = True
            ledger.blocked._state = ledger.blocked._CONSUMED
            ledger.wrapper_consumed = True
            self._active = None
            ledger.active_cleared = True
        except Exception:
            _failstop()
        except BaseException:
            if move_entered:
                move_guard.restore()
                move_restored = True
            if not ledger.wrapper_consumed or not ledger.active_cleared:
                _failstop()
            if ledger.drain_started and ledger.drain_attempt is not None:
                ledger.drain_attempt.remember_issuer()
            else:
                ledger.latch_issuer_from_child()

        release_guard: Optional[_IssuerSignalGuard] = None
        release_entered = False
        release_restored = False
        try:
            if not move_restored:
                if move_guard.restore():
                    ledger.latch_issuer_from_child()
                move_restored = True

            if ledger.settle_reason is None and ledger.initial_reason is None:
                release_guard = _IssuerSignalGuard()
                release_issuer = False
                try:
                    release_guard.block()
                    release_entered = True
                    ledger.release_started = True
                    ledger.blocked._child.release()
                except OSError:
                    ledger.release_state = ledger.blocked._child.state
                    ledger.latch_release_uncertain()
                except BaseException:
                    release_issuer = True
                try:
                    if release_guard.restore():
                        release_issuer = True
                    release_restored = True
                except BaseException:
                    release_issuer = True
                    release_restored = True
                if ledger.release_state is None:
                    ledger.release_state = ledger.blocked._child.state
                if release_issuer:
                    ledger.latch_issuer_from_child()
                elif ledger.initial_reason is ContainedSpawnReason.RELEASE_UNCERTAIN:
                    ledger.latch_release_uncertain()
                elif ledger.release_state != "RELEASED":
                    _failstop()

            ledger.drain_attempt = _DrainAttemptLedger(
                ledger.blocked,
                initial_reason=ledger.initial_reason,
                initial_phase=ledger.initial_phase,
                kill_initially=ledger.kill_initially,
            )
            ledger.drain_started = True
            if ledger.kill_initially:
                ledger.drain_attempt.kill_containment()
            result = self._drain_attempt(
                ledger.drain_attempt,
                ledger.drain_result,
            )
            return self._finish_drained_attempt(
                ledger.blocked,
                result,
                ledger.completion,
            )

        except Exception:
            _failstop()
        except BaseException:
            if (
                release_guard is not None
                and release_entered
                and not release_restored
            ):
                try:
                    release_guard.restore()
                except BaseException:
                    _failstop()
            if ledger.completion.assigned:
                completed = ledger.completion.value
                if type(completed) is ContainedSpawnFailure:
                    return completed
                if type(completed) is SettledJob:
                    if not ledger.drain_result.assigned:
                        _failstop()
                    return self._rollback_settled_commit(
                        completed,
                        ledger.blocked,
                        ledger.drain_result.value,
                        ledger.completion,
                    )
                _failstop()
            if ledger.release_state == "POISONED":
                ledger.latch_release_uncertain()
            if ledger.drain_started and ledger.drain_attempt is not None:
                ledger.drain_attempt.remember_issuer()
            else:
                ledger.latch_issuer_from_child()
            if not ledger.drain_started:
                ledger.drain_attempt = _DrainAttemptLedger(
                    ledger.blocked,
                    initial_reason=ledger.initial_reason,
                    initial_phase=ledger.initial_phase,
                    kill_initially=True,
                )
                ledger.drain_started = True
                ledger.drain_attempt.kill_containment()
                result = self._drain_attempt(
                    ledger.drain_attempt,
                    ledger.drain_result,
                )
            elif ledger.drain_result.assigned:
                result = ledger.drain_result.value
                if result.failure_reason is None:
                    if (
                        ledger.drain_attempt is None
                        or ledger.drain_attempt.failure_reason is None
                        or ledger.drain_attempt.failure_phase is None
                    ):
                        _failstop()
                    result.failure_reason = (
                        ledger.drain_attempt.failure_reason
                    )
                    result.failure_phase = ledger.drain_attempt.failure_phase
            elif ledger.drain_attempt is not None:
                result = self._drain_attempt(
                    ledger.drain_attempt,
                    ledger.drain_result,
                )
            else:
                _failstop()
            return self._finish_drained_attempt(
                ledger.blocked,
                result,
                ledger.completion,
            )

    def _recover_public_completion(
        self,
        ledger: _ConsumedBlockedLedger,
    ) -> ContainedSpawnFailure:
        if not ledger.completion.assigned:
            _failstop()
        completed = ledger.completion.value
        if type(completed) is ContainedSpawnFailure:
            return completed
        if type(completed) is not SettledJob:
            _failstop()
        if not ledger.drain_result.assigned:
            _failstop()
        return self._rollback_settled_commit(
            completed,
            ledger.blocked,
            ledger.drain_result.value,
            ledger.completion,
        )

    def settle_blocked(
        self,
        blocked: BlockedSpawn,
        reason: ContainedSpawnReason,
    ) -> ContainedSpawnFailure:
        if type(blocked) is not BlockedSpawn:
            raise TypeError("blocked must be exact BlockedSpawn")
        if type(reason) is not ContainedSpawnReason:
            raise TypeError("reason must be exact ContainedSpawnReason")
        if reason not in (
            ContainedSpawnReason.ACTIVE_NOT_DURABLE,
            ContainedSpawnReason.ISSUER_INTERRUPTED,
        ):
            raise ValueError("blocked settlement reason is not pre-release")
        self._require_state(self._BLOCKED_OWNED)
        if not _single_threaded():
            _failstop()
        blocked._require_open()
        if (
            blocked._backend is not self
            or blocked._backend_generation != self._generation
            or self._active != id(blocked)
        ):
            raise BackendStateError("BlockedSpawn belongs to another backend")
        ledger = _ConsumedBlockedLedger(blocked, reason)
        try:
            failure = self._consume_and_drive_blocked(ledger)
            if type(failure) is not ContainedSpawnFailure:
                _failstop()
            return failure
        except Exception:
            _failstop()
        except BaseException:
            return self._recover_public_completion(ledger)

    def release_and_collect(
        self,
        blocked: BlockedSpawn,
    ) -> "SettledJob | ContainedSpawnFailure":
        if type(blocked) is not BlockedSpawn:
            raise TypeError("blocked must be exact BlockedSpawn")
        self._require_state(self._BLOCKED_OWNED)
        if not _single_threaded():
            _failstop()
        blocked._require_open()
        if (
            blocked._backend is not self
            or blocked._backend_generation != self._generation
            or self._active != id(blocked)
        ):
            raise BackendStateError("BlockedSpawn belongs to another backend")
        ledger = _ConsumedBlockedLedger(blocked, None)
        try:
            result = self._consume_and_drive_blocked(ledger)
            if type(result) not in (SettledJob, ContainedSpawnFailure):
                _failstop()
            return result
        except Exception:
            _failstop()
        except BaseException:
            return self._recover_public_completion(ledger)

    def remove_after_durable_cleanup(
        self,
        settled: SettledJob,
        cleanup_permit: object,
    ) -> None:
        if type(settled) is not SettledJob:
            raise TypeError("settled must be exact SettledJob")
        if type(cleanup_permit) is not _SettledJobCleanupPermit:
            raise TypeError("cleanup_permit must be exact _SettledJobCleanupPermit")
        self._require_state(self._SETTLED_PENDING_CLEANUP)
        settled._require_open()
        expected = _CleanupPermitIdentity(
            backend_generation=self._generation,
            job_key=settled._key,
            observation_sha256=settled._observation.observation_sha256,
        )
        if cleanup_permit.identity != expected:
            raise BackendStateError("cleanup permit does not bind the settled job")
        if settled._backend is not self or self._active != id(settled):
            raise BackendStateError("SettledJob is not the active backend job")
        if not _single_threaded():
            _failstop()
        cleanup_guard = _IssuerSignalGuard()
        try:
            cleanup_guard.block()
            settled._job.remove_empty()
            cleanup_permit._consume(expected)
            settled._consume_for(self)
            settled._backend = None
            settled._job = None
            self._active = None
            self._state = self._IDLE
        except BaseException:
            cleanup_guard.restore()
            _failstop()
        cleanup_guard.restore()

    def close_idle(self) -> None:
        self._require_state(self._IDLE)
        if not _single_threaded():
            _failstop()
        close_guard = _IssuerSignalGuard()
        try:
            close_guard.block()
            self._authority._close()
            _close_exact(self._capture_directory_fd)
            self._capture_directory_fd = -1
            self._authority = None
            self._state = self._CLOSED
        except BaseException:
            close_guard.restore()
            _failstop()
        close_guard.restore()

    __copy__ = _reject_live_copy
    __deepcopy__ = _reject_live_copy
    __reduce__ = _reject_live_copy
    __reduce_ex__ = _reject_live_copy

    def __del__(self) -> None:
        state = getattr(self, "_state", self._CLOSED)
        if state in (self._CLOSED, self._POISONED_CLOSED):
            return
        if os.getpid() == getattr(self, "_creator_pid", -1):
            _failstop()
        _close_after_fork(getattr(self, "_capture_directory_fd", -1))


__all__ = [
    "BackendStateError",
    "BlockedSpawn",
    "SettledJob",
    "SpawnBackend",
]
