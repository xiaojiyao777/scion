from __future__ import annotations

import ast
import contextlib
import copy
import errno
import faulthandler
import fcntl
import gc
import importlib
import os
import pickle
import resource
import signal
import stat
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Iterator

import pytest


# The default interpreter intentionally has no built native extension.  Import
# the adapter against a complete, inert ABI-shaped module, then remove that
# import shim so this test module cannot change later native-package imports.
class _NativeBlockedChild:
    pass


def _native_not_configured(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("native spawn was not configured by the test")


_NATIVE_CONSTANTS: dict[str, object] = {
    "CHILD_EXEC_ERROR_FD": 198,
    "CHILD_RELEASE_FD": 199,
    "CHILD_STDERR_FD": 197,
    "CHILD_STDIN_FD": 195,
    "CHILD_STDOUT_FD": 196,
    "CLONE_ARGS_SIZE": 88,
    "CLONE_FLAGS": 0,
    "ERROR_RECORD_MAGIC": b"SCXE",
    "ERROR_RECORD_FORMAT": "<4sBBHI",
    "ERROR_RECORD_SIZE": 12,
    "ERROR_RECORD_VERSION": 1,
    "ERROR_STAGE_CHDIR": 12,
    "ERROR_STAGE_CLOSE_RANGE": 10,
    "ERROR_STAGE_DUP_EXEC_ERROR": 8,
    "ERROR_STAGE_DUP_RELEASE": 9,
    "ERROR_STAGE_DUP_STDERR": 7,
    "ERROR_STAGE_DUP_STDIN": 5,
    "ERROR_STAGE_DUP_STDOUT": 6,
    "ERROR_STAGE_EXECVE": 13,
    "ERROR_STAGE_RELEASE_BYTE": 4,
    "ERROR_STAGE_RELEASE_CLOSE": 3,
    "ERROR_STAGE_RELEASE_READ": 2,
    "ERROR_STAGE_SIGNAL_DISPOSITIONS": 11,
    "ERROR_STAGE_SIGNAL_MASK": 1,
    "EXIT_SIGNAL": 17,
    "RELEASE_BYTE": b"\x01",
    "WAIT_RESULT_FIELDS": (
        "pid",
        "uid",
        "si_code",
        "si_status",
        "wait_status",
        "return_code",
        "signal",
        "core_dumped",
    ),
    "BlockedChild": _NativeBlockedChild,
    "spawn_blocked": _native_not_configured,
}
_extension_name = "scion.runtime.native._spawn_into_cgroup"
_package_name = "scion.runtime.native"
_old_extension = sys.modules.get(_extension_name)
_old_package = sys.modules.get(_package_name)
_loaded_package = None
_fake_extension = types.ModuleType(_extension_name)
for _name, _value in _NATIVE_CONSTANTS.items():
    setattr(_fake_extension, _name, _value)
sys.modules[_extension_name] = _fake_extension
try:
    spawn_backend = importlib.import_module("scion.runtime.execution.spawn_backend")
finally:
    if _old_extension is None:
        sys.modules.pop(_extension_name, None)
    else:
        sys.modules[_extension_name] = _old_extension
    if _old_package is None:
        _loaded_package = sys.modules.pop(_package_name, None)
        _runtime_package = sys.modules.get("scion.runtime")
        if (
            _runtime_package is not None
            and getattr(_runtime_package, "native", None) is _loaded_package
        ):
            delattr(_runtime_package, "native")
    else:
        sys.modules[_package_name] = _old_package
del _fake_extension, _loaded_package, _name, _old_extension, _old_package, _value

from scion.runtime.execution.model import (  # noqa: E402
    BackendOpenFailure,
    BackendOpenPhase,
    BackendOpenReason,
    CgroupEventsFact,
    CgroupIdentity,
    ChildCreation,
    ContainedSpawnFailure,
    ContainedSpawnPhase,
    ContainedSpawnReason,
    FilesystemIdentity,
    GenericProcessSpec,
    JobCgroupKey,
    LeaderOutcome,
    PreHandleFailure,
    PreHandlePhase,
    PreHandleReason,
    ServiceCgroupLineage,
    StreamAvailability,
    _CleanupPermitIdentity,
)
from scion.runtime.execution.invocation_terminal import (  # noqa: E402
    IncompleteFact,
    ObservationCommit,
    OpaqueRowCommit,
    _issue_incomplete_cleanup_for_tests,
    _issue_opaque_row_commit_for_tests,
)

_SERVICE = "scion-test.service"
_EVENTS = CgroupEventsFact.decode(b"populated 0\nfrozen 0\n")


def _key(ordinal: int = 0) -> JobCgroupKey:
    return JobCgroupKey.create(ordinal=ordinal, invocation_nonce="b" * 64)


def _spec() -> GenericProcessSpec:
    return GenericProcessSpec.create(
        opaque_job_key="pure-unit-job",
        executable=b"/bin/true",
        argv=(b"/bin/true",),
        environment=(b"LANG=C", b"PATH=/usr/bin"),
        cwd=b"/",
    )


def _lineage() -> ServiceCgroupLineage:
    return ServiceCgroupLineage(
        service_name=_SERVICE,
        supervisor_name="supervisor",
        service_device=11,
        service_inode=12,
        supervisor_device=11,
        supervisor_inode=13,
        service_relative_lineage=(_SERVICE, "supervisor"),
    )


class _FakeJob:
    def __init__(self, key: JobCgroupKey, directory_fd: int) -> None:
        if type(key) is not JobCgroupKey:
            raise TypeError("key must be exact JobCgroupKey")
        self.key = key
        self.identity = CgroupIdentity(
            service_name=_SERVICE,
            supervisor_name="supervisor",
            job_name=key.rendered_name,
            service_device=11,
            service_inode=12,
            supervisor_device=11,
            supervisor_inode=13,
            job_device=11,
            job_inode=14 + key.ordinal,
            service_relative_lineage=(_SERVICE, key.rendered_name),
        )
        self.initial_events = _EVENTS
        self._directory_fd = directory_fd
        self._spawn_dirfd_issued = False
        self.closed_retained = False
        self.removed = False
        self.required_pid: int | None = None
        self.kill_calls = 0
        self.read_events_calls = 0
        self.final_empty_calls = 0
        self.events: list[CgroupEventsFact] = [_EVENTS]

    def _consume_spawn_dirfd_borrow(self) -> int:
        if self.closed_retained or self._spawn_dirfd_issued:
            raise AssertionError("invalid fake job borrow")
        self._spawn_dirfd_issued = True
        return self._directory_fd

    def _require_blocked_leader(self, pid: int) -> None:
        if (
            type(pid) is not int
            or pid <= 0
            or self.closed_retained
            or not self._spawn_dirfd_issued
        ):
            raise AssertionError("invalid fake membership proof")
        self.required_pid = pid

    def close_retained(self) -> CgroupEventsFact:
        if self.closed_retained or self.removed:
            raise AssertionError("invalid fake retained close")
        self.closed_retained = True
        return _EVENTS

    def _events_fileno(self) -> int:
        if self.closed_retained or self.removed:
            raise AssertionError("closed fake job has no events fd")
        return self._directory_fd

    def _read_events(self) -> CgroupEventsFact:
        if self.closed_retained or self.removed or not self.events:
            raise AssertionError("invalid fake cgroup.events read")
        index = min(self.read_events_calls, len(self.events) - 1)
        self.read_events_calls += 1
        return self.events[index]

    def _final_empty(self) -> CgroupEventsFact:
        if self.closed_retained or self.removed:
            raise AssertionError("invalid fake final-empty proof")
        self.final_empty_calls += 1
        value = self.events[-1]
        if value.populated != 0 or value.frozen != 0:
            raise AssertionError("fake final event is not empty")
        return value

    def _kill(self) -> None:
        if self.closed_retained or self.removed:
            raise AssertionError("invalid fake cgroup kill")
        self.kill_calls += 1

    def remove_empty(self) -> None:
        if self.closed_retained or self.removed:
            raise AssertionError("invalid fake positive removal")
        if self.events[-1].populated != 0:
            raise AssertionError("fake nonempty job removal")
        self.removed = True


class _FakeAuthority:
    def __init__(
        self,
        directory_fd: int,
        job_factory: Callable[[JobCgroupKey, int], _FakeJob] | None = None,
    ) -> None:
        self.invocation_lineage = SimpleNamespace(
            main_starttime=spawn_backend._process_starttime(os.getpid())
        )
        self._directory_fd = directory_fd
        self._job_factory = job_factory or _FakeJob
        self.closed = False
        self.created_keys: list[JobCgroupKey] = []
        self.last_job: _FakeJob | None = None

    def _create_job(self, key: JobCgroupKey) -> _FakeJob:
        if self.closed or type(key) is not JobCgroupKey:
            raise AssertionError("invalid fake authority create")
        self.created_keys.append(key)
        self.last_job = self._job_factory(key, self._directory_fd)
        return self.last_job

    def _close(self) -> None:
        if self.closed:
            raise AssertionError("fake authority closed twice")
        self.closed = True


class _FakeServiceCgroup:
    def __init__(self, authority: _FakeAuthority) -> None:
        self._authority = authority
        self._state = "OPEN"

    @property
    def copied_lineage(self) -> ServiceCgroupLineage:
        if self._state != "OPEN":
            raise AssertionError("fake service alias already consumed")
        return _lineage()

    def _consume(self) -> _FakeAuthority:
        if self._state != "OPEN":
            raise AssertionError("fake service consumed twice")
        self._state = "CONSUMED"
        return self._authority


@pytest.fixture(autouse=True)
def _install_exact_fake_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spawn_backend, "ServiceCgroup", _FakeServiceCgroup)


@pytest.fixture
def capture_directory(tmp_path: Path) -> Iterator[int]:
    fd = os.open(
        tmp_path,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
    )
    try:
        yield fd
    finally:
        os.close(fd)


def _open_backend(
    capture_directory: int,
    *,
    job_factory: Callable[[JobCgroupKey, int], _FakeJob] | None = None,
) -> tuple[spawn_backend.SpawnBackend, _FakeAuthority]:
    authority = _FakeAuthority(capture_directory, job_factory)
    value = spawn_backend.SpawnBackend.open(
        _FakeServiceCgroup(authority), capture_directory
    )
    assert type(value) is spawn_backend.SpawnBackend
    return value, authority


def _assert_not_copyable(value: object) -> None:
    with pytest.raises(TypeError):
        copy.copy(value)
    with pytest.raises(TypeError):
        copy.deepcopy(value)
    with pytest.raises(TypeError):
        pickle.dumps(value)


class _SuccessfulBlockedChild(_NativeBlockedChild):
    def __init__(
        self,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        exec_error: bytes = b"",
        exit_code: int = 0,
        release_error: bool = False,
    ) -> None:
        self.pid = os.getpid()
        self.state = "BLOCKED"
        self._release_error = release_error
        self.release_calls = 0
        self.peek_calls = 0
        self.reap_calls = 0
        self.terminal = (
            self.pid,
            os.getuid(),
            1,
            exit_code,
            exit_code << 8,
            exit_code,
            0,
            0,
        )
        self._capture_fds = tuple(
            self._pipe_with_complete_bytes(data)
            for data in (stdout, stderr, exec_error)
        )

    @staticmethod
    def _pipe_with_complete_bytes(data: bytes) -> int:
        reader, writer = os.pipe2(os.O_CLOEXEC)
        if data:
            os.write(writer, data)
        os.close(writer)
        return reader

    def take_capture_fds(self) -> tuple[int, int, int]:
        if self._capture_fds is None:
            raise AssertionError("capture fds moved twice")
        value = self._capture_fds
        self._capture_fds = None
        return value

    def dup_pidfd(self) -> int:
        return os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)

    def release(self) -> None:
        if self.state != "BLOCKED":
            raise AssertionError("fake native child released from wrong state")
        self.release_calls += 1
        if self._release_error:
            self.state = "POISONED"
            raise OSError(errno.EIO, "uncertain release")
        self.state = "RELEASED"

    def peek_wait(self) -> tuple[int, ...]:
        if self.state not in ("BLOCKED", "RELEASED", "POISONED"):
            raise AssertionError("fake terminal observation from wrong state")
        self.peek_calls += 1
        return self.terminal

    def reap(self) -> tuple[int, ...]:
        if self.state not in ("BLOCKED", "RELEASED", "POISONED"):
            raise AssertionError("fake reap from wrong state")
        self.reap_calls += 1
        self.state = "REAPED"
        return self.terminal


class _ScriptedPoll:
    def __init__(self, steps: list[list[tuple[int, int]]]) -> None:
        self._steps = list(steps)
        self.registered: dict[int, int] = {}
        self.registration_snapshots: list[dict[int, int]] = []

    def register(self, fd: int, mask: int) -> None:
        if fd in self.registered:
            raise AssertionError("fake poll duplicate registration")
        self.registered[fd] = mask

    def unregister(self, fd: int) -> None:
        if fd not in self.registered:
            raise AssertionError("fake poll unregister of unknown fd")
        del self.registered[fd]

    def poll(self) -> list[tuple[int, int]]:
        while self._steps:
            ready = [
                (fd, mask) for fd, mask in self._steps.pop(0) if fd in self.registered
            ]
            if ready:
                self.registration_snapshots.append(dict(self.registered))
                # Production discards this poll object after one ready snapshot.
                self.registered.clear()
                return ready
        raise AssertionError("fake poll exhausted")


class _FreshPoll:
    def __init__(
        self,
        factory: "_FreshPollFactory",
        ready: list[tuple[int, int]],
    ) -> None:
        self._factory = factory
        self._ready = ready
        self.registered: dict[int, int] = {}
        self.poll_calls = 0

    def register(self, fd: int, mask: int) -> None:
        if fd in self.registered:
            raise AssertionError("fresh poll duplicate registration")
        self.registered[fd] = mask

    def unregister(self, _fd: int) -> None:
        self._factory.unregister_calls += 1
        raise AssertionError("drain must discard poll objects, never unregister")

    def poll(self) -> list[tuple[int, int]]:
        self.poll_calls += 1
        if self.poll_calls != 1:
            raise AssertionError("a poll object must represent one fresh snapshot")
        return [(fd, mask) for fd, mask in self._ready if fd in self.registered]


class _FreshPollFactory:
    def __init__(self, steps: list[list[tuple[int, int]]]) -> None:
        self._steps = list(steps)
        self.instances: list[_FreshPoll] = []
        self.requests = 0
        self.unregister_calls = 0

    def __call__(self) -> _FreshPoll:
        self.requests += 1
        if not self._steps:
            raise AssertionError("fresh poll factory exhausted")
        value = _FreshPoll(self, self._steps.pop(0))
        self.instances.append(value)
        return value


class _AllRegisteredReadyPoll:
    def __init__(self) -> None:
        self.registered: dict[int, int] = {}

    def register(self, fd: int, mask: int) -> None:
        self.registered[fd] = mask

    def poll(self) -> list[tuple[int, int]]:
        ready = []
        for fd, mask in self.registered.items():
            if mask & spawn_backend.select.POLLHUP:
                ready.append((fd, spawn_backend.select.POLLHUP))
            elif mask & spawn_backend.select.POLLPRI:
                ready.append((fd, spawn_backend.select.POLLPRI))
            else:
                ready.append((fd, spawn_backend.select.POLLIN))
        return ready


def _install_poll_steps(
    monkeypatch: pytest.MonkeyPatch,
    steps: list[list[tuple[int, int]]],
) -> _ScriptedPoll:
    value = _ScriptedPoll(steps)
    monkeypatch.setattr(spawn_backend.select, "poll", lambda: value)
    return value


def _independent_completion_steps(
    blocked: spawn_backend.BlockedSpawn,
    job: _FakeJob,
) -> list[list[tuple[int, int]]]:
    # cgroup empty, pidfd terminal, and each stream EOF are deliberately five
    # separate readiness observations.  None of the facts implies another.
    return [
        [(blocked._stdout_fd, spawn_backend.select.POLLIN)],
        [(blocked._stdout_fd, spawn_backend.select.POLLHUP)],
        [(job._events_fileno(), spawn_backend.select.POLLPRI)],
        [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
        [(blocked._stderr_fd, spawn_backend.select.POLLIN)],
        [(blocked._stderr_fd, spawn_backend.select.POLLHUP)],
        [(blocked._exec_error_fd, spawn_backend.select.POLLIN)],
        [(blocked._exec_error_fd, spawn_backend.select.POLLHUP)],
    ]


class _FailstopSentinel(RuntimeError):
    pass


class _InjectedIssuerBase(BaseException):
    pass


def _raise_failstop() -> None:
    raise _FailstopSentinel("isolated fail-stop")


def _start_child(
    owner: spawn_backend.SpawnBackend,
    child: _SuccessfulBlockedChild,
    monkeypatch: pytest.MonkeyPatch,
    *,
    key: JobCgroupKey | None = None,
) -> spawn_backend.BlockedSpawn:
    monkeypatch.setattr(spawn_backend, "_failstop", _raise_failstop)
    monkeypatch.setattr(spawn_backend, "_single_threaded", lambda: True)
    monkeypatch.setattr(spawn_backend.native, "BlockedChild", _SuccessfulBlockedChild)
    monkeypatch.setattr(spawn_backend.native, "spawn_blocked", lambda *_args: child)
    result = owner.start_blocked(key or _key(), _spec())
    assert type(result) is spawn_backend.BlockedSpawn
    return result


def _dispose_blocked(
    owner: spawn_backend.SpawnBackend,
    blocked: spawn_backend.BlockedSpawn,
) -> None:
    for name in ("_stdout_fd", "_stderr_fd", "_exec_error_fd", "_poll_pidfd"):
        fd = getattr(blocked, name)
        if fd >= 0:
            try:
                os.close(fd)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise
            setattr(blocked, name, -1)
    blocked._stdout_spool.close()
    blocked._stderr_spool.close()
    blocked._job.close_retained()
    blocked._state = blocked._CONSUMED
    owner._active = None
    owner._state = owner._IDLE
    owner.close_idle()


def test_issuer_signal_guard_restores_exact_prior_mask() -> None:
    prior = frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set()))
    guard = spawn_backend._IssuerSignalGuard()
    try:
        guard.block()
        assert (
            frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set()))
            == prior | spawn_backend._CATCHABLE_SIGNALS
        )
        assert guard.restore() is False
        assert frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set())) == prior
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, prior)


def test_issuer_signal_guard_double_restore_failstops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior = frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set()))
    guard = spawn_backend._IssuerSignalGuard()
    try:
        guard.block()
        assert guard.restore() is False
        monkeypatch.setattr(spawn_backend, "_failstop", _raise_failstop)
        with pytest.raises(_FailstopSentinel, match="isolated fail-stop"):
            guard.restore()
        assert frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set())) == prior
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, prior)


def test_issuer_signal_guard_reports_only_new_pending_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior = frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set()))
    pending = iter(
        (
            frozenset({signal.SIGUSR2}),
            frozenset({signal.SIGUSR1, signal.SIGUSR2}),
        )
    )
    monkeypatch.setattr(spawn_backend.signal, "sigpending", lambda: next(pending))
    guard = spawn_backend._IssuerSignalGuard()
    try:
        guard.block()
        assert guard.restore() is True
        assert frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set())) == prior
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, prior)


def test_issuer_signal_guard_readback_recovers_handler_exception_after_restore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_pthread_sigmask = signal.pthread_sigmask
    prior = frozenset(real_pthread_sigmask(signal.SIG_BLOCK, set()))
    restored_then_raised = False

    def injected(how: int, mask: object) -> object:
        nonlocal restored_then_raised
        value = real_pthread_sigmask(how, mask)
        if how == signal.SIG_SETMASK and not restored_then_raised:
            restored_then_raised = True
            raise KeyboardInterrupt
        return value

    monkeypatch.setattr(spawn_backend.signal, "pthread_sigmask", injected)
    guard = spawn_backend._IssuerSignalGuard()
    try:
        guard.block()
        assert guard.restore() is True
        assert restored_then_raised is True
        assert frozenset(real_pthread_sigmask(signal.SIG_BLOCK, set())) == prior
    finally:
        real_pthread_sigmask(signal.SIG_SETMASK, prior)


def test_guard_block_start_recovery_readbacks_restore_after_handler_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_pthread_sigmask = signal.pthread_sigmask
    prior = frozenset(real_pthread_sigmask(signal.SIG_BLOCK, set()))
    block_raised = False
    restore_raised = False

    def injected(how: int, mask: object) -> object:
        nonlocal block_raised, restore_raised
        value = real_pthread_sigmask(how, mask)
        if how == signal.SIG_BLOCK and mask and not block_raised:
            block_raised = True
            raise KeyboardInterrupt
        if how == signal.SIG_SETMASK and not restore_raised:
            restore_raised = True
            raise KeyboardInterrupt
        return value

    monkeypatch.setattr(spawn_backend.signal, "pthread_sigmask", injected)
    monkeypatch.setattr(spawn_backend, "_failstop", _raise_failstop)
    guard = spawn_backend._IssuerSignalGuard()
    try:
        with pytest.raises(KeyboardInterrupt):
            guard.block()
        assert block_raised is True
        assert restore_raised is True
        assert frozenset(real_pthread_sigmask(signal.SIG_BLOCK, set())) == prior
        assert guard._state == guard._RESTORED
    finally:
        guard._state = guard._RESTORED
        real_pthread_sigmask(signal.SIG_SETMASK, prior)


def test_open_duplicates_and_pins_capture_directory_identity(
    capture_directory: int,
) -> None:
    supplied_stat = os.fstat(capture_directory)
    owner, authority = _open_backend(capture_directory)
    try:
        assert owner.state == "IDLE"
        assert owner._capture_directory_fd != capture_directory
        duplicate_stat = os.fstat(owner._capture_directory_fd)
        assert (duplicate_stat.st_dev, duplicate_stat.st_ino) == (
            supplied_stat.st_dev,
            supplied_stat.st_ino,
        )
        assert owner._capture_directory_identity == FilesystemIdentity(
            device=supplied_stat.st_dev,
            inode=supplied_stat.st_ino,
        )
        assert (
            fcntl.fcntl(owner._capture_directory_fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC
        )
        _assert_not_copyable(owner)
    finally:
        owner.close_idle()
    assert owner.state == "CLOSED"
    assert authority.closed is True
    assert os.fstat(capture_directory).st_ino == supplied_stat.st_ino
    with pytest.raises(spawn_backend.BackendStateError):
        owner.close_idle()


def test_open_rejects_regular_file_and_closes_consumed_authority(
    tmp_path: Path,
) -> None:
    path = tmp_path / "not-a-directory"
    path.write_bytes(b"capture")
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    authority = _FakeAuthority(fd)
    try:
        result = spawn_backend.SpawnBackend.open(_FakeServiceCgroup(authority), fd)
        assert result == BackendOpenFailure(
            phase=BackendOpenPhase.CAPTURE_DIRECTORY_ACQUIRE,
            reason=BackendOpenReason.CAPTURE_DIRECTORY_INVALID,
            service_lineage=_lineage(),
            capture_directory_acquired=False,
            capture_directory_identity=None,
            errno=None,
        )
        assert authority.closed is True
        assert os.fstat(fd).st_ino == path.stat().st_ino
    finally:
        os.close(fd)


def test_open_classifies_duplicate_failure(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _FakeAuthority(capture_directory)
    real_fcntl = spawn_backend.fcntl.fcntl

    def denied(fd: int, command: int, *args: object) -> int:
        if command == fcntl.F_DUPFD_CLOEXEC:
            raise OSError(errno.EMFILE, "descriptor table full")
        return real_fcntl(fd, command, *args)

    monkeypatch.setattr(spawn_backend.fcntl, "fcntl", denied)
    result = spawn_backend.SpawnBackend.open(
        _FakeServiceCgroup(authority), capture_directory
    )
    assert type(result) is BackendOpenFailure
    assert result.phase is BackendOpenPhase.CAPTURE_DIRECTORY_ACQUIRE
    assert result.reason is BackendOpenReason.CAPTURE_DIRECTORY_OPEN_FAILED
    assert result.errno == errno.EMFILE
    assert authority.closed is True


def test_open_first_ordinary_duplicate_failure_is_not_overwritten_by_pending_issuer(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _FakeAuthority(capture_directory)
    real_guard = spawn_backend._IssuerSignalGuard
    real_fcntl = spawn_backend.fcntl.fcntl
    guard_count = 0

    class _PendingGuard:
        def block(self) -> None:
            return None

        def restore(self) -> bool:
            return True

    def guards() -> object:
        nonlocal guard_count
        guard_count += 1
        return _PendingGuard() if guard_count == 2 else real_guard()

    def denied(fd: int, command: int, *args: object) -> int:
        if command == fcntl.F_DUPFD_CLOEXEC:
            raise OSError(errno.EMFILE, "ordinary duplicate failure")
        return real_fcntl(fd, command, *args)

    monkeypatch.setattr(spawn_backend, "_IssuerSignalGuard", guards)
    monkeypatch.setattr(spawn_backend.fcntl, "fcntl", denied)
    result = spawn_backend.SpawnBackend.open(
        _FakeServiceCgroup(authority), capture_directory
    )
    assert type(result) is BackendOpenFailure
    assert result.phase is BackendOpenPhase.CAPTURE_DIRECTORY_ACQUIRE
    assert result.reason is BackendOpenReason.CAPTURE_DIRECTORY_OPEN_FAILED
    assert result.errno == errno.EMFILE
    assert authority.closed is True


def test_open_duplicate_oserror_then_real_restore_base_keeps_open_failure(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _FakeAuthority(capture_directory)
    real_fcntl = spawn_backend.fcntl.fcntl
    real_restore = spawn_backend._IssuerSignalGuard.restore
    restore_calls = 0
    injected = False

    def denied(fd: int, command: int, *args: object) -> int:
        if command == fcntl.F_DUPFD_CLOEXEC:
            raise OSError(errno.EMFILE, "ordinary duplicate failure")
        return real_fcntl(fd, command, *args)

    def restore_then_interrupt(guard: object) -> bool:
        nonlocal restore_calls, injected
        restore_calls += 1
        value = real_restore(guard)
        if restore_calls == 2:
            injected = True
            raise _InjectedIssuerBase
        return value

    monkeypatch.setattr(spawn_backend.fcntl, "fcntl", denied)
    monkeypatch.setattr(
        spawn_backend._IssuerSignalGuard, "restore", restore_then_interrupt
    )
    result = spawn_backend.SpawnBackend.open(
        _FakeServiceCgroup(authority), capture_directory
    )
    assert injected is True
    assert type(result) is BackendOpenFailure
    assert result.phase is BackendOpenPhase.CAPTURE_DIRECTORY_ACQUIRE
    assert result.reason is BackendOpenReason.CAPTURE_DIRECTORY_OPEN_FAILED
    assert result.errno == errno.EMFILE
    assert result.capture_directory_acquired is False
    assert authority.closed is True


def test_open_recorded_duplicate_is_closed_when_restore_reports_interruption(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _FakeAuthority(capture_directory)
    real_guard = spawn_backend._IssuerSignalGuard
    real_fcntl = spawn_backend.fcntl.fcntl
    guard_count = 0
    acquired: list[int] = []

    class _PendingGuard:
        def block(self) -> None:
            return None

        def restore(self) -> bool:
            return True

    def guards() -> object:
        nonlocal guard_count
        guard_count += 1
        return _PendingGuard() if guard_count == 2 else real_guard()

    def recorded(fd: int, command: int, *args: object) -> int:
        value = real_fcntl(fd, command, *args)
        if command == fcntl.F_DUPFD_CLOEXEC:
            acquired.append(value)
        return value

    monkeypatch.setattr(spawn_backend, "_IssuerSignalGuard", guards)
    monkeypatch.setattr(spawn_backend.fcntl, "fcntl", recorded)
    result = spawn_backend.SpawnBackend.open(
        _FakeServiceCgroup(authority), capture_directory
    )
    assert type(result) is BackendOpenFailure
    assert result.reason is BackendOpenReason.ISSUER_INTERRUPTED
    assert result.capture_directory_acquired is False
    assert len(acquired) == 1
    with pytest.raises(OSError) as closed:
        fcntl.fcntl(acquired[0], fcntl.F_GETFD)
    assert closed.value.errno == errno.EBADF
    assert authority.closed is True


def test_open_hidden_duplicate_then_baseexception_failstops_instead_of_typing(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _FakeAuthority(capture_directory)
    real_fcntl = spawn_backend.fcntl.fcntl

    def hidden(fd: int, command: int, *args: object) -> int:
        value = real_fcntl(fd, command, *args)
        if command == fcntl.F_DUPFD_CLOEXEC:
            raise _InjectedIssuerBase
        return value

    monkeypatch.setattr(spawn_backend.fcntl, "fcntl", hidden)
    child_pid = os.fork()
    if child_pid == 0:
        faulthandler.disable()
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        spawn_backend.SpawnBackend.open(
            _FakeServiceCgroup(authority), capture_directory
        )
        os._exit(76)
    waited_pid, status = os.waitpid(child_pid, 0)
    assert waited_pid == child_pid
    assert os.WIFSIGNALED(status)
    assert os.WTERMSIG(status) == signal.SIGABRT


def test_open_backend_commit_return_boundary_base_closes_as_issuer_failure(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _FakeAuthority(capture_directory)
    backend_value_reads = 0
    committed: list[spawn_backend.SpawnBackend] = []

    def ledger_getattribute(self: object, name: str) -> object:
        nonlocal backend_value_reads
        value = object.__getattribute__(self, name)
        if name == "value" and type(value) is spawn_backend.SpawnBackend:
            backend_value_reads += 1
            if not committed:
                committed.append(value)
            if backend_value_reads == 2:
                raise _InjectedIssuerBase
        return value

    monkeypatch.setattr(
        spawn_backend._MoveLedger, "__getattribute__", ledger_getattribute
    )
    result = spawn_backend.SpawnBackend.open(
        _FakeServiceCgroup(authority), capture_directory
    )
    assert type(result) is BackendOpenFailure
    assert result.phase is BackendOpenPhase.BACKEND_ALLOCATION
    assert result.reason is BackendOpenReason.ISSUER_INTERRUPTED
    assert result.capture_directory_acquired is True
    assert result.capture_directory_identity is not None
    assert backend_value_reads >= 2
    assert len(committed) == 1
    assert committed[0]._state == committed[0]._CLOSED
    assert committed[0]._capture_directory_fd == -1
    assert committed[0]._authority is None
    assert authority.closed is True


def test_otmpfile_spools_are_private_distinct_complete_files(
    capture_directory: int,
) -> None:
    value = os.fstat(capture_directory)
    identity = FilesystemIdentity(device=value.st_dev, inode=value.st_ino)
    first = second = None
    try:
        first_ledger = spawn_backend._MoveLedger()
        second_ledger = spawn_backend._MoveLedger()
        spawn_backend._open_spool_into(first_ledger, capture_directory, identity)
        spawn_backend._open_spool_into(second_ledger, capture_directory, identity)
        first = first_ledger.value
        second = second_ledger.value
    except OSError as error:
        if error.errno in spawn_backend._CAPTURE_UNSUPPORTED_ERRNOS:
            pytest.skip("test filesystem does not implement O_TMPFILE")
        raise
    try:
        assert first is not None and second is not None
        assert first.identity != second.identity
        for spool in (first, second):
            spool_stat = os.fstat(spool.fd)
            assert stat.S_ISREG(spool_stat.st_mode)
            assert stat.S_IMODE(spool_stat.st_mode) == 0o600
            assert spool_stat.st_dev == identity.device
            assert fcntl.fcntl(spool.fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC
            os.write(spool.fd, b"complete bytes")
            assert spawn_backend._read_all(spool.fd, rewind=True) == b"complete bytes"
    finally:
        if first is not None:
            first.close()
        if second is not None:
            second.close()


def test_capture_unsupported_is_typed_and_poisoned_closed(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)

    def unsupported(*_args: object, **_kwargs: object) -> object:
        raise OSError(errno.EOPNOTSUPP, "no anonymous tmpfile")

    monkeypatch.setattr(spawn_backend, "_open_spool_into", unsupported)
    result = owner.start_blocked(_key(), _spec())
    assert type(result) is PreHandleFailure
    assert result.phase is PreHandlePhase.CAPTURE_PREPARE
    assert result.reason is PreHandleReason.CAPTURE_TMPFILE_UNSUPPORTED
    assert result.native_called is False
    assert result.job_cgroup_created is False
    assert owner.state == "POISONED_CLOSED"
    assert authority.closed is True


def test_multithread_shape_after_backend_ownership_failstops_without_mutation(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    monkeypatch.setattr(spawn_backend, "_failstop", _raise_failstop)
    monkeypatch.setattr(spawn_backend, "_single_threaded", lambda: False)
    with pytest.raises(_FailstopSentinel, match="isolated fail-stop"):
        owner.start_blocked(_key(), _spec())
    assert authority.created_keys == []
    assert authority.closed is False
    assert owner.state == "IDLE"
    monkeypatch.setattr(spawn_backend, "_single_threaded", lambda: True)
    owner.close_idle()


def test_job_create_oserror_is_ordinary_typed_prehandle_failure(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    monkeypatch.setattr(spawn_backend, "_single_threaded", lambda: True)

    def denied(_key_value: JobCgroupKey) -> _FakeJob:
        raise OSError(errno.EACCES, "job create denied")

    authority._create_job = denied  # type: ignore[method-assign]
    result = owner.start_blocked(_key(), _spec())
    assert type(result) is PreHandleFailure
    assert result.phase is PreHandlePhase.JOB_CREATE
    assert result.reason is PreHandleReason.JOB_CREATE_FAILED
    assert result.native_called is False
    assert result.job_cgroup_created is False
    assert owner.state == "POISONED_CLOSED"
    assert authority.closed is True


def test_pre_native_ready_interruption_has_not_called_native_and_exact_facts(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    monkeypatch.setattr(spawn_backend, "_single_threaded", lambda: True)
    native_calls = 0

    def counted_native(*_args: object, **_kwargs: object) -> object:
        nonlocal native_calls
        native_calls += 1
        raise AssertionError("PRE_NATIVE_READY must precede native entry")

    def interrupted_clock() -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(spawn_backend.native, "spawn_blocked", counted_native)
    monkeypatch.setattr(spawn_backend.time, "time_ns", interrupted_clock)
    result = owner.start_blocked(_key(), _spec())
    assert result == PreHandleFailure(
        phase=PreHandlePhase.PRE_NATIVE_READY,
        reason=PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE,
        native_called=False,
        native_handle_acquired=False,
        child_creation=ChildCreation.NOT_CALLED,
        job_cgroup_created=True,
        job_cgroup_identity=authority.last_job.identity,
        initial_cgroup_events=_EVENTS,
        final_cgroup_events=_EVENTS,
        stdout_availability=StreamAvailability.NOT_STARTED,
        stdout=None,
        stderr_availability=StreamAvailability.NOT_STARTED,
        stderr=None,
        exec_error_availability=StreamAvailability.NOT_STARTED,
        exec_error=None,
    )
    assert native_calls == 0
    assert authority.last_job is not None
    assert authority.last_job._spawn_dirfd_issued is False
    assert authority.last_job.closed_retained is True
    assert owner.state == "POISONED_CLOSED"
    assert authority.closed is True


def test_start_job_and_borrow_recorded_then_pre_native_boundary_base_is_typed(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    real_guard = spawn_backend._IssuerSignalGuard
    guard_count = 0
    native_calls = 0

    class _PreNativeBoundaryInterrupt:
        def block(self) -> None:
            raise _InjectedIssuerBase

    def guards() -> object:
        nonlocal guard_count
        guard_count += 1
        if guard_count == 5:
            return _PreNativeBoundaryInterrupt()
        return real_guard()

    def counted_native(*_args: object) -> object:
        nonlocal native_calls
        native_calls += 1
        raise AssertionError("native must not be called after PRE_NATIVE_READY")

    monkeypatch.setattr(spawn_backend, "_IssuerSignalGuard", guards)
    monkeypatch.setattr(spawn_backend.native, "spawn_blocked", counted_native)
    result = owner.start_blocked(_key(), _spec())
    assert type(result) is PreHandleFailure
    assert result.phase is PreHandlePhase.PRE_NATIVE_READY
    assert result.reason is PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE
    assert result.native_called is False
    assert result.child_creation is ChildCreation.NOT_CALLED
    assert result.job_cgroup_created is True
    assert native_calls == 0
    assert authority.last_job is not None
    assert authority.last_job._spawn_dirfd_issued is True
    assert authority.last_job.closed_retained is True
    assert authority.closed is True
    assert owner.state == "POISONED_CLOSED"


def test_native_no_handle_returns_retained_empty_cgroup_facts(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    monkeypatch.setattr(spawn_backend, "_single_threaded", lambda: True)
    native_calls = 0

    def no_handle(*_args: object, **_kwargs: object) -> object:
        nonlocal native_calls
        native_calls += 1
        raise RuntimeError("native returned no authority")

    monkeypatch.setattr(spawn_backend.native, "spawn_blocked", no_handle)
    result = owner.start_blocked(_key(), _spec())
    assert type(result) is PreHandleFailure
    assert result.phase is PreHandlePhase.NATIVE_NO_HANDLE
    assert result.reason is PreHandleReason.NATIVE_NO_HANDLE
    assert result.native_called is True
    assert result.native_handle_acquired is False
    assert result.child_creation is ChildCreation.NATIVE_INTERNAL_SETTLED
    assert result.job_cgroup_created is True
    assert result.job_cgroup_identity == authority.last_job.identity
    assert result.initial_cgroup_events == _EVENTS
    assert result.final_cgroup_events == _EVENTS
    assert authority.last_job is not None
    assert native_calls == 1
    assert authority.last_job._spawn_dirfd_issued is True
    assert authority.last_job.closed_retained is True
    assert owner.state == "POISONED_CLOSED"
    assert authority.closed is True


def test_first_ordinary_native_failure_is_not_overwritten_by_pending_issuer(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    real_guard = spawn_backend._IssuerSignalGuard
    guard_count = 0
    native_calls = 0

    class _PendingGuard:
        def block(self) -> None:
            return None

        def restore(self) -> bool:
            return True

    def guards() -> object:
        nonlocal guard_count
        guard_count += 1
        return _PendingGuard() if guard_count == 5 else real_guard()

    def ordinary_native_failure(*_args: object) -> object:
        nonlocal native_calls
        native_calls += 1
        raise RuntimeError("accepted native no-handle failure")

    monkeypatch.setattr(spawn_backend, "_IssuerSignalGuard", guards)
    monkeypatch.setattr(spawn_backend.native, "spawn_blocked", ordinary_native_failure)
    result = owner.start_blocked(_key(), _spec())
    assert type(result) is PreHandleFailure
    assert result.phase is PreHandlePhase.NATIVE_NO_HANDLE
    assert result.reason is PreHandleReason.NATIVE_NO_HANDLE
    assert result.native_called is True
    assert result.child_creation is ChildCreation.NATIVE_INTERNAL_SETTLED
    assert native_calls == 1
    assert authority.last_job is not None
    assert authority.last_job.closed_retained is True
    assert authority.closed is True
    assert owner.state == "POISONED_CLOSED"


def test_native_local_parameter_boundary_base_is_pre_native_and_not_called(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    spec = _spec()
    native_calls = 0

    def interrupted_executable(_self: object) -> bytes:
        raise _InjectedIssuerBase

    def counted_native(*_args: object) -> object:
        nonlocal native_calls
        native_calls += 1
        raise AssertionError("native must not be called before local args commit")

    monkeypatch.setattr(
        GenericProcessSpec,
        "executable",
        property(interrupted_executable),
    )
    monkeypatch.setattr(spawn_backend.native, "spawn_blocked", counted_native)
    result = owner.start_blocked(_key(), spec)
    assert type(result) is PreHandleFailure
    assert result.phase is PreHandlePhase.PRE_NATIVE_READY
    assert result.reason is PreHandleReason.ISSUER_INTERRUPTED_PRE_HANDLE
    assert result.native_called is False
    assert result.child_creation is ChildCreation.NOT_CALLED
    assert native_calls == 0
    assert authority.last_job is not None
    assert authority.last_job._spawn_dirfd_issued is True
    assert authority.last_job.closed_retained is True
    assert authority.closed is True
    assert owner.state == "POISONED_CLOSED"


def test_native_ordinary_error_then_real_restore_base_stays_native_no_handle(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    real_restore = spawn_backend._IssuerSignalGuard.restore
    restore_calls = 0
    native_calls = 0
    injected = False

    def ordinary_native_failure(*_args: object) -> object:
        nonlocal native_calls
        native_calls += 1
        raise RuntimeError("accepted native no-handle failure")

    def restore_then_interrupt(guard: object) -> bool:
        nonlocal restore_calls, injected
        restore_calls += 1
        value = real_restore(guard)
        if restore_calls == 5:
            injected = True
            raise _InjectedIssuerBase
        return value

    monkeypatch.setattr(spawn_backend.native, "spawn_blocked", ordinary_native_failure)
    monkeypatch.setattr(
        spawn_backend._IssuerSignalGuard, "restore", restore_then_interrupt
    )
    result = owner.start_blocked(_key(), _spec())
    assert injected is True
    assert native_calls == 1
    assert type(result) is PreHandleFailure
    assert result.phase is PreHandlePhase.NATIVE_NO_HANDLE
    assert result.reason is PreHandleReason.NATIVE_NO_HANDLE
    assert result.native_called is True
    assert result.child_creation is ChildCreation.NATIVE_INTERNAL_SETTLED
    assert authority.last_job is not None
    assert authority.last_job.closed_retained is True
    assert authority.closed is True
    assert owner.state == "POISONED_CLOSED"


def test_successful_start_owns_exact_resources_identity_and_membership(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    monkeypatch.setattr(spawn_backend, "_single_threaded", lambda: True)
    child = _SuccessfulBlockedChild()
    native_calls: list[tuple[object, ...]] = []

    def successful(*args: object) -> _SuccessfulBlockedChild:
        native_calls.append(args)
        return child

    monkeypatch.setattr(spawn_backend.native, "BlockedChild", _SuccessfulBlockedChild)
    monkeypatch.setattr(spawn_backend.native, "spawn_blocked", successful)
    key = _key(7)
    spec = _spec()
    blocked = owner.start_blocked(key, spec)
    assert type(blocked) is spawn_backend.BlockedSpawn
    try:
        assert owner.state == "BLOCKED_OWNED"
        assert blocked.job_key == key
        assert blocked.process_spec_sha256 == spec.spec_sha256
        assert blocked.cgroup_identity == authority.last_job.identity
        assert blocked.process_identity.pid == os.getpid()
        assert blocked.process_identity.creator_pid == os.getpid()
        assert blocked.process_identity.proc_starttime_ticks > 0
        assert blocked.process_identity.pidfd_inode > 0
        assert authority.last_job is not None
        assert authority.last_job.required_pid == os.getpid()
        assert len(native_calls) == 1
        assert native_calls[0][1:] == (
            spec.executable,
            spec.argv,
            spec.environment,
            spec.cwd,
        )
        capture_fds = (
            blocked._stdout_fd,
            blocked._stderr_fd,
            blocked._exec_error_fd,
        )
        assert len(set(capture_fds)) == 3
        assert blocked._poll_pidfd not in capture_fds
        for fd in capture_fds:
            assert stat.S_ISFIFO(os.fstat(fd).st_mode)
            assert fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_NONBLOCK
            assert fcntl.fcntl(fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC
        assert blocked._stdout_spool.identity != blocked._stderr_spool.identity
        _assert_not_copyable(blocked)
        with pytest.raises(spawn_backend.BackendStateError):
            owner.start_blocked(_key(8), spec)
    finally:
        _dispose_blocked(owner, blocked)
    assert owner.state == "CLOSED"


def test_native_child_value_commit_then_base_settles_acquired_handle(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(
        stdout=b"committed-child-out",
        stderr=b"committed-child-err",
    )
    capture_fds = child._capture_fds
    assert type(capture_fds) is tuple
    native_calls = 0
    interrupted = False

    def successful_native(*_args: object) -> _SuccessfulBlockedChild:
        nonlocal native_calls
        native_calls += 1
        return child

    def interrupt_after_child_commit(
        ledger: object,
        name: str,
        value: object,
    ) -> None:
        nonlocal interrupted
        object.__setattr__(ledger, name, value)
        if name == "child" and value is child and not interrupted:
            assert object.__getattribute__(ledger, "child") is child
            interrupted = True
            raise _InjectedIssuerBase

    monkeypatch.setattr(spawn_backend, "_failstop", _raise_failstop)
    monkeypatch.setattr(spawn_backend, "_single_threaded", lambda: True)
    monkeypatch.setattr(spawn_backend.native, "BlockedChild", _SuccessfulBlockedChild)
    monkeypatch.setattr(spawn_backend.native, "spawn_blocked", successful_native)
    monkeypatch.setattr(
        spawn_backend._HandleAssemblyLedger,
        "__setattr__",
        interrupt_after_child_commit,
    )
    monkeypatch.setattr(
        spawn_backend.select,
        "poll",
        lambda: _AllRegisteredReadyPoll(),
    )

    result = owner.start_blocked(_key(), _spec())
    assert interrupted is True
    assert native_calls == 1
    assert type(result) is ContainedSpawnFailure
    assert not isinstance(result, PreHandleFailure)
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.BLOCKED
    assert result.process_identity.pid == child.pid
    assert result.stdout is not None
    assert result.stdout.data == b"committed-child-out"
    assert result.stderr is not None
    assert result.stderr.data == b"committed-child-err"

    # The child was still blocked at interruption, so containment is killed
    # without ever releasing it to execute, then the exact leader is reaped.
    assert child.release_calls == 0
    assert child.peek_calls == child.reap_calls == 1
    assert child.state == "REAPED"
    assert child._capture_fds is None
    for fd in capture_fds:
        with pytest.raises(OSError) as closed:
            os.fstat(fd)
        assert closed.value.errno == errno.EBADF
    assert authority.last_job is not None
    assert authority.last_job.required_pid == child.pid
    assert authority.last_job.kill_calls == 1
    assert authority.last_job.closed_retained is True
    assert authority.closed is True
    assert owner.state == "POISONED_CLOSED"


@pytest.mark.parametrize(
    "recorded_boundary",
    [
        "capture_assigned",
        "pidfd_assigned",
        "blocked_assigned",
        "backend_commit",
    ],
)
def test_recorded_assembly_interruption_explicitly_settles(
    recorded_boundary: str,
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild()
    monkeypatch.setattr(spawn_backend, "_failstop", _raise_failstop)
    monkeypatch.setattr(spawn_backend, "_single_threaded", lambda: True)
    monkeypatch.setattr(spawn_backend.native, "BlockedChild", _SuccessfulBlockedChild)
    monkeypatch.setattr(spawn_backend.native, "spawn_blocked", lambda *_args: child)
    monkeypatch.setattr(spawn_backend.select, "poll", lambda: _AllRegisteredReadyPoll())
    interrupted = False

    if recorded_boundary == "backend_commit":

        def backend_setattr(self: object, name: str, value: object) -> None:
            nonlocal interrupted
            object.__setattr__(self, name, value)
            if (
                not interrupted
                and name == "_state"
                and value == spawn_backend.SpawnBackend._BLOCKED_OWNED
            ):
                interrupted = True
                raise _InjectedIssuerBase

        monkeypatch.setattr(spawn_backend.SpawnBackend, "__setattr__", backend_setattr)
    else:

        def ledger_setattr(self: object, name: str, value: object) -> None:
            nonlocal interrupted
            object.__setattr__(self, name, value)
            if not interrupted and name == recorded_boundary and value is True:
                interrupted = True
                raise _InjectedIssuerBase

        monkeypatch.setattr(
            spawn_backend._HandleAssemblyLedger,
            "__setattr__",
            ledger_setattr,
        )

    result = owner.start_blocked(_key(), _spec())
    assert interrupted is True
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.BLOCKED
    assert child.release_calls == 0
    assert child.peek_calls == child.reap_calls == 1
    assert authority.last_job is not None
    assert authority.last_job.kill_calls == 1
    assert authority.last_job.closed_retained is True
    assert authority.closed is True
    assert owner.state == "POISONED_CLOSED"


def test_wrapper_real_restore_then_next_boundary_base_settles_blocked(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild()
    monkeypatch.setattr(spawn_backend, "_failstop", _raise_failstop)
    monkeypatch.setattr(spawn_backend, "_single_threaded", lambda: True)
    monkeypatch.setattr(spawn_backend.native, "BlockedChild", _SuccessfulBlockedChild)
    monkeypatch.setattr(spawn_backend.native, "spawn_blocked", lambda *_args: child)
    monkeypatch.setattr(spawn_backend.select, "poll", lambda: _AllRegisteredReadyPoll())
    injected = False

    def assembly_getattribute(self: object, name: str) -> object:
        nonlocal injected
        value = object.__getattribute__(self, name)
        if name == "blocked_assigned" and value is True and not injected:
            injected = True
            raise _InjectedIssuerBase
        return value

    monkeypatch.setattr(
        spawn_backend._HandleAssemblyLedger,
        "__getattribute__",
        assembly_getattribute,
    )
    result = owner.start_blocked(_key(), _spec())
    assert injected is True
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.BLOCKED
    assert child.release_calls == 0
    assert child.peek_calls == child.reap_calls == 1
    assert authority.last_job is not None
    assert authority.last_job.kill_calls == 1
    assert authority.last_job.closed_retained is True
    assert authority.closed is True
    assert owner.state == "POISONED_CLOSED"


@pytest.mark.parametrize("hidden_boundary", ["capture", "pidfd", "wrapper"])
def test_hidden_assembly_move_failstops_in_isolated_process(
    hidden_boundary: str,
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _HiddenMoveChild(_SuccessfulBlockedChild):
        def take_capture_fds(self) -> tuple[int, int, int]:
            value = super().take_capture_fds()
            if hidden_boundary == "capture":
                self.hidden_capture = value
                raise _InjectedIssuerBase
            return value

        def dup_pidfd(self) -> int:
            value = super().dup_pidfd()
            if hidden_boundary == "pidfd":
                self.hidden_pidfd = value
                raise _InjectedIssuerBase
            return value

    monkeypatch.setattr(spawn_backend, "_single_threaded", lambda: True)
    monkeypatch.setattr(spawn_backend.native, "BlockedChild", _HiddenMoveChild)
    monkeypatch.setattr(
        spawn_backend.native,
        "spawn_blocked",
        lambda *_args: _HiddenMoveChild(),
    )
    if hidden_boundary == "wrapper":
        real_create = spawn_backend.BlockedSpawn._create

        def hidden_create(_cls: type, **kwargs: object) -> object:
            value = real_create(**kwargs)
            del value
            raise _InjectedIssuerBase

        monkeypatch.setattr(
            spawn_backend.BlockedSpawn,
            "_create",
            classmethod(hidden_create),
        )

    child_pid = os.fork()
    if child_pid == 0:
        faulthandler.disable()
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        owner, _authority = _open_backend(capture_directory)
        owner.start_blocked(_key(), _spec())
        os._exit(77)
    waited_pid, status = os.waitpid(child_pid, 0)
    assert waited_pid == child_pid
    assert os.WIFSIGNALED(status)
    assert os.WTERMSIG(status) == signal.SIGABRT


def test_settle_active_kills_drains_reaps_and_poison_closes_every_alias(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"active\x00out", stderr=b"active-err")
    blocked = _start_child(owner, child, monkeypatch)
    alias = blocked
    job = authority.last_job
    assert job is not None
    poller = _install_poll_steps(
        monkeypatch, _independent_completion_steps(blocked, job)
    )

    result = owner.settle_blocked(blocked, ContainedSpawnReason.ACTIVE_NOT_DURABLE)
    assert type(result) is ContainedSpawnFailure
    assert result.phase is ContainedSpawnPhase.BLOCKED
    assert result.reason is ContainedSpawnReason.ACTIVE_NOT_DURABLE
    assert result.stdout is not None and result.stdout.data == b"active\x00out"
    assert result.stderr is not None and result.stderr.data == b"active-err"
    assert result.exec_error is not None and result.exec_error.data == b""
    assert job.kill_calls == 1
    assert job.closed_retained is True
    assert child.release_calls == 0
    assert child.peek_calls == child.reap_calls == 1
    assert poller.registered == {}
    assert owner.state == "POISONED_CLOSED"
    assert authority.closed is True
    for moved_alias in (blocked, alias):
        with pytest.raises(spawn_backend.BackendStateError, match="consumed"):
            _ = moved_alias.job_key


def test_release_nonzero_is_positive_pending_then_exact_cleanup_allows_next(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(
        stdout=b"\x00binary\xffstdout",
        stderr=b"stderr\x00bytes",
        exit_code=3,
    )
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    poller = _install_poll_steps(
        monkeypatch, _independent_completion_steps(blocked, job)
    )

    settled = owner.release_and_collect(blocked)
    assert type(settled) is spawn_backend.SettledJob
    assert settled.observation.stdout.data == b"\x00binary\xffstdout"
    assert settled.observation.stderr.data == b"stderr\x00bytes"
    assert settled.observation.exec_error_clean_eof is True
    assert settled.observation.wait_fact.return_code == 3
    assert settled.observation.leader_outcome is LeaderOutcome.NONZERO
    assert child.release_calls == child.peek_calls == child.reap_calls == 1
    assert job.kill_calls == 0
    assert job.read_events_calls == 2
    assert poller.registered == {}
    event_masks = [
        snapshot[job._events_fileno()]
        for snapshot in poller.registration_snapshots
        if job._events_fileno() in snapshot
    ]
    assert event_masks
    assert set(event_masks) == {
        spawn_backend.select.POLLPRI | spawn_backend.select.POLLERR
    }
    assert all(not (mask & spawn_backend.select.POLLIN) for mask in event_masks)
    assert owner.state == "SETTLED_PENDING_CLEANUP"
    with pytest.raises(spawn_backend.BackendStateError, match="expected IDLE"):
        owner.start_blocked(_key(1), _spec())
    with pytest.raises(spawn_backend.BackendStateError, match="consumed"):
        _ = blocked.job_key
    _assert_not_copyable(settled)

    wrong_identity = _CleanupPermitIdentity(
        backend_generation=owner._generation,
        job_key=settled._key,
        observation_sha256="d" * 64,
    )
    wrong_permit = spawn_backend._issue_cleanup_permit_for_tests(wrong_identity)
    with pytest.raises(spawn_backend.BackendStateError, match="does not bind"):
        owner.remove_after_durable_cleanup(settled, wrong_permit)
    assert wrong_permit.identity == wrong_identity
    assert settled.observation.stdout.data == b"\x00binary\xffstdout"
    assert owner.state == "SETTLED_PENDING_CLEANUP"

    wrong_commit = OpaqueRowCommit(
        job_ordinal=1,
        observation_sha256=settled.observation.observation_sha256,
        evidence_sha256="e" * 64,
        row_sha256="f" * 64,
        row_size_bytes=1,
    )
    with pytest.raises(spawn_backend.BackendStateError, match="does not bind"):
        owner.remove_after_opaque_commit(settled, wrong_commit)
    durable_commit = OpaqueRowCommit(
        job_ordinal=0,
        observation_sha256=settled.observation.observation_sha256,
        evidence_sha256="e" * 64,
        row_sha256="f" * 64,
        row_size_bytes=1,
    )
    owner.remove_after_opaque_commit(
        settled,
        _issue_opaque_row_commit_for_tests(durable_commit),
    )
    assert job.removed is True
    assert owner.state == "IDLE"
    with pytest.raises(spawn_backend.BackendStateError, match="consumed"):
        _ = settled.observation

    next_child = _SuccessfulBlockedChild()
    next_blocked = _start_child(owner, next_child, monkeypatch, key=_key(1))
    next_job = authority.last_job
    assert next_job is not None and next_job is not job
    _install_poll_steps(
        monkeypatch, _independent_completion_steps(next_blocked, next_job)
    )
    next_failure = owner.settle_blocked(
        next_blocked, ContainedSpawnReason.ACTIVE_NOT_DURABLE
    )
    assert type(next_failure) is ContainedSpawnFailure
    assert authority.created_keys == [_key(), _key(1)]


def test_incomplete_cleanup_requires_writer_issued_evidence_and_terminal(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    blocked = _start_child(
        owner,
        _SuccessfulBlockedChild(exit_code=3),
        monkeypatch,
    )
    job = authority.last_job
    assert job is not None
    _install_poll_steps(
        monkeypatch,
        _independent_completion_steps(blocked, job),
    )
    settled = owner.release_and_collect(blocked)
    assert type(settled) is spawn_backend.SettledJob
    observation = ObservationCommit(
        job_ordinal=0,
        observation_sha256=(settled.observation.observation_sha256),
        evidence_sha256="e" * 64,
        evidence_size_bytes=1,
    )
    incomplete = IncompleteFact(
        policy_sha256="a" * 64,
        reason_code="WAREHOUSE_VALIDATION_FAILED",
        evidence_count=1,
        row_count=0,
        incomplete_sha256="f" * 64,
    )
    with pytest.raises(
        spawn_backend.BackendStateError,
        match="terminal authority",
    ):
        owner.remove_after_incomplete_commit(
            settled,
            observation,
            incomplete,
        )

    observation, incomplete = _issue_incomplete_cleanup_for_tests(
        observation,
        incomplete,
    )
    owner.remove_after_incomplete_commit(
        settled,
        observation,
        incomplete,
    )
    assert job.removed is True
    assert owner.state == "IDLE"
    owner.close_idle()


def test_drain_uses_fresh_exact_poll_sets_and_processes_complete_snapshot_fairly(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"one-pass", stderr=b"stderr")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    stdout_fd = blocked._stdout_fd
    stderr_fd = blocked._stderr_fd
    exec_error_fd = blocked._exec_error_fd
    poll_pidfd = blocked._poll_pidfd
    events_fd = job._events_fileno()
    factory = _FreshPollFactory(
        [
            [
                (stdout_fd, spawn_backend.select.POLLIN),
                (events_fd, spawn_backend.select.POLLPRI),
                (poll_pidfd, spawn_backend.select.POLLIN),
            ],
            [
                (stdout_fd, spawn_backend.select.POLLHUP),
                (stderr_fd, spawn_backend.select.POLLIN),
                (exec_error_fd, spawn_backend.select.POLLHUP),
            ],
            [(stderr_fd, spawn_backend.select.POLLHUP)],
        ]
    )
    monkeypatch.setattr(spawn_backend.select, "poll", factory)

    settled = owner.release_and_collect(blocked)
    assert type(settled) is spawn_backend.SettledJob
    assert settled.observation.stdout.data == b"one-pass"
    assert settled.observation.stderr.data == b"stderr"
    assert child.peek_calls == child.reap_calls == 1
    assert job.read_events_calls == 2
    assert len(factory.instances) == 3
    assert factory.unregister_calls == 0
    assert all(item.poll_calls == 1 for item in factory.instances)

    first = factory.instances[0].registered
    assert first[stdout_fd] == (
        spawn_backend.select.POLLIN
        | spawn_backend.select.POLLHUP
        | spawn_backend.select.POLLERR
    )
    assert first[poll_pidfd] == (
        spawn_backend.select.POLLIN | spawn_backend.select.POLLERR
    )
    assert first[events_fd] == (
        spawn_backend.select.POLLPRI | spawn_backend.select.POLLERR
    )
    assert not first[events_fd] & spawn_backend.select.POLLIN
    second = factory.instances[1].registered
    assert poll_pidfd not in second
    assert events_fd not in second

    permit = spawn_backend._issue_cleanup_permit_for_tests(settled._cleanup_identity())
    owner.remove_after_durable_cleanup(settled, permit)
    owner.close_idle()


def test_continuous_large_stream_cannot_starve_pidfd_before_events_snapshot(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild()
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    stdout_fd = blocked._stdout_fd
    poll_pidfd = blocked._poll_pidfd
    events_fd = job._events_fileno()
    chunks = [
        b"a" * spawn_backend._READ_BLOCK,
        b"b" * 257,
        b"",
    ]
    stdout_reads = 0
    real_read = spawn_backend.os.read

    def continuous_read(fd: int, size: int) -> bytes:
        nonlocal stdout_reads
        if fd != stdout_fd:
            return real_read(fd, size)
        assert size == spawn_backend._READ_BLOCK
        stdout_reads += 1
        return chunks.pop(0)

    factory = _FreshPollFactory(
        [
            [
                (stdout_fd, spawn_backend.select.POLLIN),
                (poll_pidfd, spawn_backend.select.POLLIN),
                (events_fd, spawn_backend.select.POLLPRI),
            ],
            [
                (stdout_fd, spawn_backend.select.POLLIN),
                (blocked._stderr_fd, spawn_backend.select.POLLHUP),
                (blocked._exec_error_fd, spawn_backend.select.POLLHUP),
            ],
            [(stdout_fd, spawn_backend.select.POLLHUP)],
        ]
    )
    monkeypatch.setattr(spawn_backend.os, "read", continuous_read)
    monkeypatch.setattr(spawn_backend.select, "poll", factory)
    settled = None
    try:
        settled = owner.release_and_collect(blocked)
        assert type(settled) is spawn_backend.SettledJob
        assert settled.observation.stdout.data == (
            b"a" * spawn_backend._READ_BLOCK + b"b" * 257
        )
        assert len(settled.observation.stdout.data) > 64 * 1024
        assert stdout_reads == 3
        assert child.peek_calls == child.reap_calls == 1
        assert factory.instances[0].poll_calls == 1
        assert factory.instances[1].poll_calls == 1
        assert factory.unregister_calls == 0
    finally:
        if type(settled) is spawn_backend.SettledJob:
            permit = spawn_backend._issue_cleanup_permit_for_tests(
                settled._cleanup_identity()
            )
            owner.remove_after_durable_cleanup(settled, permit)
            owner.close_idle()
        elif owner._state not in (owner._CLOSED, owner._POISONED_CLOSED):
            _dispose_blocked(owner, blocked)


def test_terminal_ledger_resumes_after_phase_commit_before_reap_without_repeek(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"terminal", stderr=b"resume")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    injected = False

    def terminal_getattribute(self: object, name: str) -> object:
        nonlocal injected
        value = object.__getattribute__(self, name)
        if name == "reaped" and value is False and not injected:
            if object.__getattribute__(
                self, "fact_assigned"
            ) and object.__getattribute__(self, "phase_committed"):
                injected = True
                raise _InjectedIssuerBase
        return value

    monkeypatch.setattr(
        spawn_backend._TerminalDrainLedger,
        "__getattribute__",
        terminal_getattribute,
    )
    _install_poll_steps(
        monkeypatch,
        [
            [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
            [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLHUP)],
            [(blocked._stderr_fd, spawn_backend.select.POLLIN)],
            [(blocked._stderr_fd, spawn_backend.select.POLLHUP)],
            [(blocked._exec_error_fd, spawn_backend.select.POLLHUP)],
        ],
    )
    result = owner.release_and_collect(blocked)
    assert injected is True
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.LEADER_TERMINAL
    assert child.peek_calls == 1
    assert child.reap_calls == 1
    assert result.stdout is not None and result.stdout.data == b"terminal"
    assert result.stderr is not None and result.stderr.data == b"resume"
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_terminal_value_commit_next_boundary_base_resumes_without_repeek(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"terminal", stderr=b"value")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    injected = False

    def terminal_setattr(self: object, name: str, value: object) -> None:
        nonlocal injected
        object.__setattr__(self, name, value)
        if name == "terminal" and value is not None and not injected:
            injected = True
            raise _InjectedIssuerBase

    monkeypatch.setattr(
        spawn_backend._TerminalDrainLedger,
        "__setattr__",
        terminal_setattr,
    )
    _install_poll_steps(
        monkeypatch,
        [
            [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
            [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLHUP)],
            [(blocked._stderr_fd, spawn_backend.select.POLLIN)],
            [(blocked._stderr_fd, spawn_backend.select.POLLHUP)],
            [(blocked._exec_error_fd, spawn_backend.select.POLLHUP)],
        ],
    )
    result = owner.release_and_collect(blocked)
    assert injected is True
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.RELEASED_DRAINING
    assert child.peek_calls == 1
    assert child.reap_calls == 1
    assert result.stdout is not None and result.stdout.data == b"terminal"
    assert result.stderr is not None and result.stderr.data == b"value"
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_poll_constructor_base_once_recovers_with_fresh_poll_and_contains(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"fresh", stderr=b"poll")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    scripted = _ScriptedPoll(_independent_completion_steps(blocked, job))
    constructor_calls = 0

    def poll_factory() -> object:
        nonlocal constructor_calls
        constructor_calls += 1
        if constructor_calls == 1:
            raise _InjectedIssuerBase
        return scripted

    monkeypatch.setattr(spawn_backend.select, "poll", poll_factory)
    result = owner.release_and_collect(blocked)
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.RELEASED_DRAINING
    assert constructor_calls >= 2
    assert child.peek_calls == child.reap_calls == 1
    assert result.stdout is not None and result.stdout.data == b"fresh"
    assert result.stderr is not None and result.stderr.data == b"poll"
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_ready_iterator_base_after_one_item_resumes_without_duplicate_damage(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"once", stderr=b"iterator")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    scripted = _ScriptedPoll(
        [
            [(blocked._stdout_fd, spawn_backend.select.POLLHUP)],
            [(job._events_fileno(), spawn_backend.select.POLLPRI)],
            [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
            [(blocked._stderr_fd, spawn_backend.select.POLLIN)],
            [(blocked._stderr_fd, spawn_backend.select.POLLHUP)],
            [(blocked._exec_error_fd, spawn_backend.select.POLLHUP)],
        ]
    )
    constructor_calls = 0

    class _ExplodingReady:
        def __iter__(self) -> Iterator[tuple[int, int]]:
            yield blocked._stdout_fd, spawn_backend.select.POLLIN
            raise _InjectedIssuerBase

    class _FirstPoll:
        def register(self, _fd: int, _mask: int) -> None:
            return None

        def poll(self) -> _ExplodingReady:
            return _ExplodingReady()

    def poll_factory() -> object:
        nonlocal constructor_calls
        constructor_calls += 1
        return _FirstPoll() if constructor_calls == 1 else scripted

    monkeypatch.setattr(spawn_backend.select, "poll", poll_factory)
    result = owner.release_and_collect(blocked)
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.RELEASED_DRAINING
    assert result.stdout is not None and result.stdout.data == b"once"
    assert result.stderr is not None and result.stderr.data == b"iterator"
    assert child.peek_calls == child.reap_calls == 1
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_pidfd_first_stale_events_still_rejects_authority_bad_bits(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild()
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    factory = _FreshPollFactory(
        [
            [
                (blocked._poll_pidfd, spawn_backend.select.POLLIN),
                (job._events_fileno(), spawn_backend.select.POLLHUP),
            ]
        ]
    )
    monkeypatch.setattr(spawn_backend.select, "poll", factory)
    try:
        with pytest.raises(_FailstopSentinel, match="isolated fail-stop"):
            owner.release_and_collect(blocked)
        assert child.reap_calls == 1
        assert factory.requests == 1
    finally:
        if owner._state not in (owner._CLOSED, owner._POISONED_CLOSED):
            _dispose_blocked(owner, blocked)


def test_interrupted_blocked_wrapper_move_still_settles_owned_authority(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"moved", stderr=b"authority")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    real_guard = spawn_backend._IssuerSignalGuard
    issued = 0

    class _ReportedInterruptedGuard:
        def block(self) -> None:
            return None

        def interrupted(self) -> bool:
            return True

        def restore(self) -> bool:
            return True

    def guard_factory() -> object:
        nonlocal issued
        issued += 1
        if issued == 1:
            return _ReportedInterruptedGuard()
        return real_guard()

    monkeypatch.setattr(spawn_backend, "_IssuerSignalGuard", guard_factory)
    result = owner.release_and_collect(blocked)
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.BLOCKED
    assert result.stdout is not None and result.stdout.data == b"moved"
    assert result.stderr is not None and result.stderr.data == b"authority"
    assert job.kill_calls == 1
    assert job.closed_retained is True
    assert owner.state == "POISONED_CLOSED"
    with pytest.raises(spawn_backend.BackendStateError, match="consumed"):
        _ = blocked.job_key


def test_wrapper_move_restore_base_before_drain_still_explicitly_settles(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"restore", stderr=b"boundary")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    real_guard = spawn_backend._IssuerSignalGuard
    guard_count = 0

    class _RestoreRaisesAfterMove:
        def block(self) -> None:
            return None

        def interrupted(self) -> bool:
            return False

        def restore(self) -> bool:
            raise _InjectedIssuerBase

    def guards() -> object:
        nonlocal guard_count
        guard_count += 1
        return _RestoreRaisesAfterMove() if guard_count == 1 else real_guard()

    monkeypatch.setattr(spawn_backend, "_IssuerSignalGuard", guards)
    result = None
    try:
        result = owner.settle_blocked(
            blocked,
            ContainedSpawnReason.ISSUER_INTERRUPTED,
        )
        assert type(result) is ContainedSpawnFailure
        assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
        assert result.phase is ContainedSpawnPhase.BLOCKED
        assert child.release_calls == 0
        assert child.peek_calls == child.reap_calls == 1
        assert job.kill_calls == 1
        assert job.closed_retained is True
        assert owner.state == "POISONED_CLOSED"
    finally:
        if result is None and owner._state not in (
            owner._CLOSED,
            owner._POISONED_CLOSED,
        ):
            _dispose_blocked(owner, blocked)


def test_stdout_read_ledger_restore_base_marks_unavailable_and_contains(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"destructively-read", stderr=b"safe")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_guard = spawn_backend._IssuerSignalGuard
    guard_count = 0

    class _RestoreRaisesAfterLedger:
        def block(self) -> None:
            return None

        def restore(self) -> bool:
            raise _InjectedIssuerBase

    def guards() -> object:
        nonlocal guard_count
        guard_count += 1
        return _RestoreRaisesAfterLedger() if guard_count == 3 else real_guard()

    monkeypatch.setattr(spawn_backend, "_IssuerSignalGuard", guards)
    _install_poll_steps(
        monkeypatch,
        [
            [(blocked._stdout_fd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLHUP)],
            [(job._events_fileno(), spawn_backend.select.POLLPRI)],
            [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
            [(blocked._stderr_fd, spawn_backend.select.POLLIN)],
            [(blocked._stderr_fd, spawn_backend.select.POLLHUP)],
            [(blocked._exec_error_fd, spawn_backend.select.POLLHUP)],
        ],
    )
    result = None
    try:
        result = owner.release_and_collect(blocked)
        assert type(result) is ContainedSpawnFailure
        assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
        assert result.phase is ContainedSpawnPhase.RELEASED_DRAINING
        assert result.stdout_availability is StreamAvailability.UNAVAILABLE
        assert result.stdout is None
        assert result.stderr is not None and result.stderr.data == b"safe"
        assert result.exec_error is not None and result.exec_error.data == b""
        assert job.kill_calls == 1
        assert job.closed_retained is True
        assert owner.state == "POISONED_CLOSED"
    finally:
        if result is None and owner._state not in (
            owner._CLOSED,
            owner._POISONED_CLOSED,
        ):
            _dispose_blocked(owner, blocked)


def test_stream_snapshot_normal_restore_then_next_boundary_base_is_contained(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"committed-stream", stderr=b"safe")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_snapshot = spawn_backend._drain_one_stream_snapshot
    injected = False

    def interrupt_after_return(stream: object) -> tuple[bool, bool]:
        nonlocal injected
        value = real_snapshot(stream)
        if not injected and stream.name == "stdout":
            injected = True
            raise _InjectedIssuerBase
        return value

    monkeypatch.setattr(
        spawn_backend, "_drain_one_stream_snapshot", interrupt_after_return
    )
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    result = owner.release_and_collect(blocked)
    assert injected is True
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.RELEASED_DRAINING
    assert result.stdout is not None and result.stdout.data == b"committed-stream"
    assert result.stderr is not None and result.stderr.data == b"safe"
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_stream_storage_failure_commit_next_boundary_base_keeps_capture_first(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"cannot-store", stderr=b"safe")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_snapshot = spawn_backend._drain_one_stream_snapshot
    real_write = spawn_backend._write_spool
    injected = False

    def fail_stdout(spool: object, data: bytes) -> bool:
        if spool is blocked._stdout_spool:
            return False
        return real_write(spool, data)

    def interrupt_after_storage_failure(stream: object) -> tuple[bool, bool]:
        nonlocal injected
        value = real_snapshot(stream)
        if not injected and stream.name == "stdout" and stream.storage_failed:
            assert value[1] is True
            injected = True
            raise _InjectedIssuerBase
        return value

    monkeypatch.setattr(spawn_backend, "_write_spool", fail_stdout)
    monkeypatch.setattr(
        spawn_backend,
        "_drain_one_stream_snapshot",
        interrupt_after_storage_failure,
    )
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    result = owner.release_and_collect(blocked)
    assert injected is True
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.CAPTURE_FAILED
    assert result.phase is ContainedSpawnPhase.RELEASED_DRAINING
    assert result.stdout_availability is StreamAvailability.UNAVAILABLE
    assert result.stdout is None
    assert result.stderr is not None and result.stderr.data == b"safe"
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_cgroup_ready_normal_read_then_next_boundary_base_is_contained(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"cgroup", stderr=b"ready")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_read_events = job._read_events
    injected = False

    def interrupt_after_read() -> CgroupEventsFact:
        nonlocal injected
        value = real_read_events()
        if not injected:
            injected = True
            raise _InjectedIssuerBase
        return value

    job._read_events = interrupt_after_read  # type: ignore[method-assign]
    _install_poll_steps(
        monkeypatch,
        [
            [(job._events_fileno(), spawn_backend.select.POLLPRI)],
            [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLHUP)],
            [(blocked._stderr_fd, spawn_backend.select.POLLIN)],
            [(blocked._stderr_fd, spawn_backend.select.POLLHUP)],
            [(blocked._exec_error_fd, spawn_backend.select.POLLHUP)],
        ],
    )
    result = owner.release_and_collect(blocked)
    assert injected is True
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.RELEASED_DRAINING
    assert result.stdout is not None and result.stdout.data == b"cgroup"
    assert result.stderr is not None and result.stderr.data == b"ready"
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_positive_commit_normal_restore_then_next_boundary_base_is_contained(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"positive", stderr=b"commit")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    real_restore = spawn_backend._IssuerSignalGuard.restore
    injected = False

    def restore_then_interrupt(
        guard: spawn_backend._IssuerSignalGuard,
    ) -> bool:
        nonlocal injected
        value = real_restore(guard)
        if owner.state == "SETTLED_PENDING_CLEANUP" and not injected:
            injected = True
            raise _InjectedIssuerBase
        return value

    monkeypatch.setattr(
        spawn_backend._IssuerSignalGuard, "restore", restore_then_interrupt
    )
    result = owner.release_and_collect(blocked)
    assert injected is True
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.LEADER_REAPED_DRAINING
    assert job.closed_retained is True
    assert owner.state == "POISONED_CLOSED"


@pytest.mark.parametrize("recorded_boundary", ["final_empty", "observation"])
def test_positive_recorded_fact_next_boundary_base_is_leader_reaped_contained(
    recorded_boundary: str,
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"positive", stderr=b"fact")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    injected = False

    if recorded_boundary == "final_empty":

        def interrupt_before_observation(
            _cls: type,
            **_kwargs: object,
        ) -> object:
            nonlocal injected
            injected = True
            raise _InjectedIssuerBase

        monkeypatch.setattr(
            spawn_backend.ClosedSpawnObservation,
            "create",
            classmethod(interrupt_before_observation),
        )
    else:

        def positive_setattr(self: object, name: str, value: object) -> None:
            nonlocal injected
            object.__setattr__(self, name, value)
            if name == "observation" and value is not None and not injected:
                injected = True
                raise _InjectedIssuerBase

        monkeypatch.setattr(
            spawn_backend._PositiveCommitLedger,
            "__setattr__",
            positive_setattr,
        )

    result = owner.release_and_collect(blocked)
    assert injected is True
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.LEADER_REAPED_DRAINING
    assert result.stdout is not None and result.stdout.data == b"positive"
    assert result.stderr is not None and result.stderr.data == b"fact"
    assert job.closed_retained is True
    assert owner.state == "POISONED_CLOSED"


def test_public_release_inner_positive_return_boundary_rolls_back_without_live_settled(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"inner", stderr=b"positive")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    real_drive = spawn_backend.SpawnBackend._consume_and_drive_blocked
    inner_values: list[spawn_backend.SettledJob] = []
    injected = False

    def drive_then_interrupt(self: object, ledger: object) -> object:
        nonlocal injected
        value = real_drive(self, ledger)
        if type(value) is spawn_backend.SettledJob and not injected:
            inner_values.append(value)
            injected = True
            raise _InjectedIssuerBase
        return value

    monkeypatch.setattr(
        spawn_backend.SpawnBackend,
        "_consume_and_drive_blocked",
        drive_then_interrupt,
    )
    result = owner.release_and_collect(blocked)
    assert injected is True
    assert len(inner_values) == 1
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
    assert result.phase is ContainedSpawnPhase.LEADER_REAPED_DRAINING
    with pytest.raises(spawn_backend.BackendStateError, match="consumed"):
        _ = inner_values[0].observation
    assert job.closed_retained is True
    assert authority.closed is True
    assert owner.state == "POISONED_CLOSED"


def test_exec_read_ledger_restore_base_is_exact_and_contained(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild()
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_guard = spawn_backend._IssuerSignalGuard
    guard_count = 0

    class _RestoreRaisesAfterLedger:
        def block(self) -> None:
            return None

        def restore(self) -> bool:
            raise _InjectedIssuerBase

    def guards() -> object:
        nonlocal guard_count
        guard_count += 1
        return _RestoreRaisesAfterLedger() if guard_count == 3 else real_guard()

    monkeypatch.setattr(spawn_backend, "_IssuerSignalGuard", guards)
    factory = _install_poll_steps(
        monkeypatch,
        [
            [(blocked._exec_error_fd, spawn_backend.select.POLLHUP)],
            [(job._events_fileno(), spawn_backend.select.POLLPRI)],
            [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLHUP)],
            [(blocked._stderr_fd, spawn_backend.select.POLLHUP)],
        ],
    )
    result = None
    try:
        result = owner.release_and_collect(blocked)
        assert type(result) is ContainedSpawnFailure
        assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
        assert result.phase is ContainedSpawnPhase.RELEASED_DRAINING
        assert result.exec_error_availability is StreamAvailability.COMPLETE
        assert result.exec_error is not None and result.exec_error.data == b""
        assert job.closed_retained is True
    finally:
        if result is None and owner._state not in (
            owner._CLOSED,
            owner._POISONED_CLOSED,
        ):
            _dispose_blocked(owner, blocked)


@pytest.mark.parametrize(
    "restore_guard_number,expected_phase",
    [
        (3, ContainedSpawnPhase.LEADER_TERMINAL),
        (4, ContainedSpawnPhase.LEADER_TERMINAL),
    ],
)
def test_waitfact_or_reap_restore_base_is_contained_at_exact_phase(
    restore_guard_number: int,
    expected_phase: ContainedSpawnPhase,
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"terminal", stderr=b"window")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_guard = spawn_backend._IssuerSignalGuard
    guard_count = 0

    class _RestoreRaisesAfterLedger:
        def block(self) -> None:
            return None

        def restore(self) -> bool:
            raise _InjectedIssuerBase

    def guards() -> object:
        nonlocal guard_count
        guard_count += 1
        if guard_count == restore_guard_number:
            return _RestoreRaisesAfterLedger()
        return real_guard()

    monkeypatch.setattr(spawn_backend, "_IssuerSignalGuard", guards)
    _install_poll_steps(
        monkeypatch,
        [
            [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLHUP)],
            [(blocked._stderr_fd, spawn_backend.select.POLLIN)],
            [(blocked._stderr_fd, spawn_backend.select.POLLHUP)],
            [(blocked._exec_error_fd, spawn_backend.select.POLLHUP)],
        ],
    )
    result = None
    try:
        result = owner.release_and_collect(blocked)
        assert type(result) is ContainedSpawnFailure
        assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
        assert result.phase is expected_phase
        assert result.wait_fact.return_code == 0
        assert child.peek_calls == child.reap_calls == 1
        assert job.kill_calls == 1
        assert job.closed_retained is True
        assert owner.state == "POISONED_CLOSED"
    finally:
        if result is None and owner._state not in (
            owner._CLOSED,
            owner._POISONED_CLOSED,
        ):
            _dispose_blocked(owner, blocked)


def test_post_reap_issuer_window_is_contained_as_leader_reaped_draining(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"post", stderr=b"reap")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    original_read_events = job._read_events
    read_calls = 0

    def interrupted_once() -> CgroupEventsFact:
        nonlocal read_calls
        read_calls += 1
        if read_calls == 1:
            raise _InjectedIssuerBase
        return original_read_events()

    job._read_events = interrupted_once  # type: ignore[method-assign]
    _install_poll_steps(
        monkeypatch,
        [
            [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
            [(job._events_fileno(), spawn_backend.select.POLLPRI)],
            [(blocked._stdout_fd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLHUP)],
            [(blocked._stderr_fd, spawn_backend.select.POLLIN)],
            [(blocked._stderr_fd, spawn_backend.select.POLLHUP)],
            [(blocked._exec_error_fd, spawn_backend.select.POLLHUP)],
        ],
    )
    result = None
    try:
        result = owner.release_and_collect(blocked)
        assert type(result) is ContainedSpawnFailure
        assert result.reason is ContainedSpawnReason.ISSUER_INTERRUPTED
        assert result.phase is ContainedSpawnPhase.LEADER_REAPED_DRAINING
        assert child.peek_calls == child.reap_calls == 1
        assert job.kill_calls == 1
        assert job.closed_retained is True
        assert owner.state == "POISONED_CLOSED"
    finally:
        if result is None and owner._state not in (
            owner._CLOSED,
            owner._POISONED_CLOSED,
        ):
            job._read_events = original_read_events  # type: ignore[method-assign]
            _dispose_blocked(owner, blocked)


def test_cleanup_restore_interruption_commits_remove_and_all_consumptions(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild()
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    settled = owner.release_and_collect(blocked)
    assert type(settled) is spawn_backend.SettledJob
    permit = spawn_backend._issue_cleanup_permit_for_tests(settled._cleanup_identity())

    class _ReportedInterruptedGuard:
        def block(self) -> None:
            return None

        def restore(self) -> bool:
            return True

    monkeypatch.setattr(spawn_backend, "_IssuerSignalGuard", _ReportedInterruptedGuard)
    owner.remove_after_durable_cleanup(settled, permit)
    assert job.removed is True
    assert owner.state == "IDLE"
    with pytest.raises(spawn_backend.BackendStateError, match="consumed"):
        _ = settled.observation
    with pytest.raises(spawn_backend.BackendStateError, match="consumed"):
        _ = permit.identity

    owner.close_idle()


def test_cleanup_direct_interruption_before_remove_consumes_nothing(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild()
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    settled = owner.release_and_collect(blocked)
    assert type(settled) is spawn_backend.SettledJob
    permit = spawn_backend._issue_cleanup_permit_for_tests(settled._cleanup_identity())
    original_remove = job.remove_empty

    def interrupted_remove() -> None:
        raise KeyboardInterrupt

    job.remove_empty = interrupted_remove  # type: ignore[method-assign]
    with pytest.raises(_FailstopSentinel, match="isolated fail-stop"):
        owner.remove_after_durable_cleanup(settled, permit)
    assert job.removed is False
    assert owner.state == "SETTLED_PENDING_CLEANUP"
    assert settled.observation.exec_error_clean_eof is True
    assert permit.identity == settled._cleanup_identity()

    job.remove_empty = original_remove  # type: ignore[method-assign]
    owner.remove_after_durable_cleanup(settled, permit)
    owner.close_idle()


def test_exact_exec_error_record_and_exit_127_is_exec_failed(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = spawn_backend.struct.pack(
        spawn_backend.native.ERROR_RECORD_FORMAT,
        b"SCXE",
        1,
        13,
        0,
        errno.ENOENT,
    )
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(exec_error=record, exit_code=127)
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    result = owner.release_and_collect(blocked)
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.EXEC_FAILED
    assert result.phase is ContainedSpawnPhase.LEADER_REAPED_DRAINING
    assert result.exec_error is not None and result.exec_error.data == record
    assert result.exec_error_stage == 13
    assert result.exec_error_errno == errno.ENOENT
    assert result.exec_error_availability is StreamAvailability.COMPLETE
    assert owner.state == "POISONED_CLOSED"


def test_release_oserror_poisoned_with_stage9_is_release_uncertain(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = spawn_backend.struct.pack(
        spawn_backend.native.ERROR_RECORD_FORMAT,
        b"SCXE",
        1,
        9,
        0,
        errno.EPIPE,
    )
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(
        exec_error=record,
        exit_code=127,
        release_error=True,
    )
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    result = owner.release_and_collect(blocked)
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.RELEASE_UNCERTAIN
    assert result.phase is ContainedSpawnPhase.RELEASED_DRAINING
    assert result.exec_error_stage == 9
    assert result.exec_error_errno == errno.EPIPE
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_release_oserror_then_real_restore_base_keeps_release_uncertain(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = spawn_backend.struct.pack(
        spawn_backend.native.ERROR_RECORD_FORMAT,
        b"SCXE",
        1,
        9,
        0,
        errno.EPIPE,
    )
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(
        exec_error=record,
        exit_code=127,
        release_error=True,
    )
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_restore = spawn_backend._IssuerSignalGuard.restore
    restore_calls = 0
    injected = False

    def restore_then_interrupt(guard: object) -> bool:
        nonlocal restore_calls, injected
        restore_calls += 1
        value = real_restore(guard)
        if restore_calls == 2:
            injected = True
            raise _InjectedIssuerBase
        return value

    monkeypatch.setattr(
        spawn_backend._IssuerSignalGuard, "restore", restore_then_interrupt
    )
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    result = owner.release_and_collect(blocked)
    assert injected is True
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.RELEASE_UNCERTAIN
    assert result.phase is ContainedSpawnPhase.RELEASED_DRAINING
    assert result.exec_error_stage == 9
    assert result.exec_error_errno == errno.EPIPE
    assert child.release_calls == child.peek_calls == child.reap_calls == 1
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_terminal_leader_with_populated_descendant_kills_then_waits_for_empty(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    populated = CgroupEventsFact.decode(b"populated 1\nfrozen 0\n")
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"leader", stderr=b"descendant")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    job.events = [populated, _EVENTS]
    poller = _install_poll_steps(
        monkeypatch,
        [
            [(blocked._poll_pidfd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLIN)],
            [(blocked._stdout_fd, spawn_backend.select.POLLHUP)],
            [(job._events_fileno(), spawn_backend.select.POLLPRI)],
            [(blocked._stderr_fd, spawn_backend.select.POLLIN)],
            [(blocked._stderr_fd, spawn_backend.select.POLLHUP)],
            [(blocked._exec_error_fd, spawn_backend.select.POLLIN)],
            [(blocked._exec_error_fd, spawn_backend.select.POLLHUP)],
        ],
    )
    result = owner.release_and_collect(blocked)
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.DESCENDANT_SURVIVED
    assert result.phase is ContainedSpawnPhase.LEADER_REAPED_DRAINING
    assert result.final_cgroup_events == _EVENTS
    assert job.kill_calls == 1
    assert job.read_events_calls == 2
    assert poller.registered == {}
    assert owner.state == "POISONED_CLOSED"


def test_capture_spool_write_failure_is_contained_and_unavailable(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"cannot-spool", stderr=b"complete")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_write = spawn_backend._write_spool

    def fail_stdout(spool: object, data: bytes) -> bool:
        if spool is blocked._stdout_spool:
            return False
        return real_write(spool, data)

    monkeypatch.setattr(spawn_backend, "_write_spool", fail_stdout)
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    result = owner.release_and_collect(blocked)
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.CAPTURE_FAILED
    assert result.stdout_availability is StreamAvailability.UNAVAILABLE
    assert result.stdout is None
    assert result.stderr_availability is StreamAvailability.COMPLETE
    assert result.exec_error_availability is StreamAvailability.COMPLETE
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_active_not_durable_remains_first_reason_when_stdout_becomes_unavailable(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"discard-after-active")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_write = spawn_backend._write_spool

    def fail_stdout(spool: object, data: bytes) -> bool:
        if spool is blocked._stdout_spool:
            return False
        return real_write(spool, data)

    monkeypatch.setattr(spawn_backend, "_write_spool", fail_stdout)
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    result = owner.settle_blocked(blocked, ContainedSpawnReason.ACTIVE_NOT_DURABLE)
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.ACTIVE_NOT_DURABLE
    assert result.phase is ContainedSpawnPhase.BLOCKED
    assert result.stdout_availability is StreamAvailability.UNAVAILABLE
    assert result.stdout is None
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_release_uncertain_remains_first_reason_when_stdout_becomes_unavailable(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = spawn_backend.struct.pack(
        spawn_backend.native.ERROR_RECORD_FORMAT,
        b"SCXE",
        1,
        9,
        0,
        errno.EPIPE,
    )
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(
        stdout=b"discard-after-release",
        exec_error=record,
        exit_code=127,
        release_error=True,
    )
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_write = spawn_backend._write_spool

    def fail_stdout(spool: object, data: bytes) -> bool:
        if spool is blocked._stdout_spool:
            return False
        return real_write(spool, data)

    monkeypatch.setattr(spawn_backend, "_write_spool", fail_stdout)
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    result = owner.release_and_collect(blocked)
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.RELEASE_UNCERTAIN
    assert result.phase is ContainedSpawnPhase.RELEASED_DRAINING
    assert result.stdout_availability is StreamAvailability.UNAVAILABLE
    assert result.stdout is None
    assert result.exec_error_stage == 9
    assert result.exec_error_errno == errno.EPIPE
    assert job.kill_calls == 1
    assert owner.state == "POISONED_CLOSED"


def test_capture_spool_read_failure_is_contained_and_unavailable(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"durability-read", stderr=b"complete")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_read = spawn_backend._read_spool

    def fail_stdout(spool: object, result_ledger: object) -> object:
        if spool is blocked._stdout_spool:
            spool.close()
            result_ledger.value = None
            result_ledger.assigned = True
            return None
        return real_read(spool, result_ledger)

    monkeypatch.setattr(spawn_backend, "_read_spool", fail_stdout)
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    result = owner.release_and_collect(blocked)
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.CAPTURE_FAILED
    assert result.stdout_availability is StreamAvailability.UNAVAILABLE
    assert result.stdout is None
    assert result.stderr is not None and result.stderr.data == b"complete"
    assert result.exec_error is not None and result.exec_error.data == b""
    assert owner.state == "POISONED_CLOSED"


def test_spool_readback_none_ledger_next_boundary_base_keeps_capture_first(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"readback-none", stderr=b"complete")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_read = spawn_backend._read_spool
    injected = False

    def recorded_none_then_interrupt(spool: object, result_ledger: object) -> object:
        nonlocal injected
        if spool is blocked._stdout_spool and not injected:
            spool.close()
            result_ledger.value = None
            result_ledger.assigned = True
            injected = True
            raise _InjectedIssuerBase
        return real_read(spool, result_ledger)

    monkeypatch.setattr(spawn_backend, "_read_spool", recorded_none_then_interrupt)
    _install_poll_steps(monkeypatch, _independent_completion_steps(blocked, job))
    result = owner.release_and_collect(blocked)
    assert injected is True
    assert type(result) is ContainedSpawnFailure
    assert result.reason is ContainedSpawnReason.CAPTURE_FAILED
    assert result.phase is ContainedSpawnPhase.LEADER_REAPED_DRAINING
    assert result.stdout_availability is StreamAvailability.UNAVAILABLE
    assert result.stdout is None
    assert result.stderr is not None and result.stderr.data == b"complete"
    assert result.exec_error is not None and result.exec_error.data == b""
    assert job.kill_calls == 0
    assert owner.state == "POISONED_CLOSED"


def test_non_eagain_pipe_read_error_failstops_in_same_ready_snapshot(
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild(stdout=b"unread")
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    real_read = spawn_backend.os.read

    def injected_read(fd: int, size: int) -> bytes:
        if fd == blocked._stdout_fd:
            raise OSError(errno.EIO, "channel state is unknowable")
        return real_read(fd, size)

    factory = _FreshPollFactory([[(blocked._stdout_fd, spawn_backend.select.POLLIN)]])
    monkeypatch.setattr(spawn_backend.os, "read", injected_read)
    monkeypatch.setattr(spawn_backend.select, "poll", factory)
    with pytest.raises(_FailstopSentinel, match="isolated fail-stop"):
        owner.release_and_collect(blocked)
    assert factory.requests == 1
    assert len(factory.instances) == 1
    _dispose_blocked(owner, blocked)


@pytest.mark.parametrize("authority_name", ["pidfd", "cgroup.events"])
def test_pidfd_or_cgroup_hup_is_immediate_authority_failstop(
    authority_name: str,
    capture_directory: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, authority = _open_backend(capture_directory)
    child = _SuccessfulBlockedChild()
    blocked = _start_child(owner, child, monkeypatch)
    job = authority.last_job
    assert job is not None
    fd = blocked._poll_pidfd if authority_name == "pidfd" else job._events_fileno()
    factory = _FreshPollFactory([[(fd, spawn_backend.select.POLLHUP)]])
    monkeypatch.setattr(spawn_backend.select, "poll", factory)
    with pytest.raises(_FailstopSentinel, match="isolated fail-stop"):
        owner.release_and_collect(blocked)
    assert factory.requests == 1
    assert len(factory.instances) == 1
    _dispose_blocked(owner, blocked)


@pytest.mark.parametrize(
    "record",
    [
        b"SCXE\x01\x09\x00",
        b"SCXE\x01\x09\x00\x00\x05\x00\x00\x00trailing",
        b"BAD!\x01\x09\x00\x00\x05\x00\x00\x00",
        b"SCXE\x01\x00\x00\x00\x05\x00\x00\x00",
        b"SCXE\x01\x09\x01\x00\x05\x00\x00\x00",
    ],
)
def test_partial_trailing_or_malformed_exec_record_failstops(
    record: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(spawn_backend, "_failstop", _raise_failstop)
    with pytest.raises(_FailstopSentinel, match="isolated fail-stop"):
        spawn_backend._decode_exec_error(record)


def test_cleanup_permit_has_hidden_constructor_and_one_shot_identity() -> None:
    identity = _CleanupPermitIdentity(
        backend_generation=1,
        job_key=_key(),
        observation_sha256="c" * 64,
    )
    with pytest.raises(TypeError, match="cannot be constructed directly"):
        spawn_backend._SettledJobCleanupPermit(object(), identity)
    permit = spawn_backend._issue_cleanup_permit_for_tests(identity)
    assert permit.identity == identity
    _assert_not_copyable(permit)
    with pytest.raises(spawn_backend.BackendStateError, match="mismatch"):
        permit._consume(
            _CleanupPermitIdentity(
                backend_generation=2,
                job_key=_key(),
                observation_sha256="c" * 64,
            )
        )
    assert permit.identity == identity
    permit._consume(identity)
    with pytest.raises(spawn_backend.BackendStateError, match="consumed"):
        permit._consume(identity)
    with pytest.raises(spawn_backend.BackendStateError, match="consumed"):
        _ = permit.identity


def test_cleanup_issuer_has_no_package_wide_production_calls_or_token() -> None:
    source_path = Path(spawn_backend.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    package_root = source_path.parents[2]
    issuer_calls: list[tuple[Path, int]] = []
    issuer_imports: list[tuple[Path, int]] = []
    for production_path in sorted(package_root.rglob("*.py")):
        if "tests" in production_path.relative_to(package_root).parts:
            continue
        production_tree = ast.parse(
            production_path.read_text(encoding="utf-8"),
            filename=str(production_path),
        )
        for node in ast.walk(production_tree):
            if isinstance(node, ast.Call) and (
                (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "_issue_cleanup_permit_for_tests"
                )
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "_issue_cleanup_permit_for_tests"
                )
            ):
                issuer_calls.append((production_path, node.lineno))
            if isinstance(node, ast.ImportFrom):
                issuer_imports.extend(
                    (production_path, node.lineno)
                    for alias in node.names
                    if alias.name == "_issue_cleanup_permit_for_tests"
                )
    assert issuer_calls == []
    assert issuer_imports == []

    module_bound_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    module_bound_names.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    module_bound_names.update(
                        item.id for item in target.elts if isinstance(item, ast.Name)
                    )
    assert "construction_authority" not in module_bound_names
    assert not any("token" in name.lower() for name in module_bound_names)
    assert "_make_cleanup_permit_surface" not in vars(spawn_backend)


def test_production_boundary_has_no_forbidden_launch_or_policy_imports() -> None:
    source_path = Path(spawn_backend.__file__)
    execution_root = source_path.parent
    sources = {
        path: path.read_text(encoding="utf-8")
        for path in sorted(execution_root.rglob("*.py"))
    }
    trees = {
        path: ast.parse(source, filename=str(path)) for path, source in sources.items()
    }
    assert all("NotImplemented" not in source for source in sources.values())
    imported_roots: set[str] = set()
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.lstrip(".").split(".", 1)[0])
    assert imported_roots.isdisjoint(
        {"subprocess", "multiprocessing", "asyncio", "problems"}
    )

    forbidden_calls: list[tuple[Path, str, int]] = []
    forbidden_call_names = {
        "Popen",
        "fork",
        "forkpty",
        "kill",
        "killpg",
        "popen",
        "posix_spawn",
        "posix_spawnp",
        "setpgid",
        "setsid",
        "system",
        "vfork",
        "waitpid",
    }
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden_call_names
            ):
                forbidden_calls.append((path, node.func.attr, node.lineno))
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_call_names:
                forbidden_calls.append((path, node.func.id, node.lineno))
            for keyword in node.keywords:
                assert keyword.arg not in {
                    "timeout",
                    "byte_cap",
                    "truncate",
                    "retry",
                }
    assert forbidden_calls == []

    forbidden_exact_names = {
        "timeout",
        "deadline",
        "byte_cap",
        "truncate",
        "truncation",
        "retry",
        "retries",
        "problem",
        "problem_spec",
    }
    identifiers = {
        node.id
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    assert identifiers.isdisjoint(forbidden_exact_names)


@pytest.mark.parametrize(
    "wrapper_type",
    [
        spawn_backend.SpawnBackend,
        spawn_backend.BlockedSpawn,
        spawn_backend.SettledJob,
    ],
)
def test_live_wrapper_types_are_final(wrapper_type: type) -> None:
    with pytest.raises(TypeError, match="final"):
        type("ForbiddenLiveSubclass", (wrapper_type,), {})


@pytest.mark.parametrize(
    "wrapper_type,live_state",
    [
        (spawn_backend.SpawnBackend, spawn_backend.SpawnBackend._IDLE),
        (spawn_backend.BlockedSpawn, spawn_backend.BlockedSpawn._OPEN),
        (spawn_backend.SettledJob, spawn_backend.SettledJob._OPEN),
    ],
)
def test_creator_live_wrapper_destructor_failstops_only_in_isolated_process(
    wrapper_type: type,
    live_state: str,
) -> None:
    child_pid = os.fork()
    if child_pid == 0:
        faulthandler.disable()
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        value = object.__new__(wrapper_type)
        value._state = live_state
        value._creator_pid = os.getpid()
        del value
        gc.collect()
        os._exit(71)

    waited_pid, status = os.waitpid(child_pid, 0)
    assert waited_pid == child_pid
    assert os.WIFSIGNALED(status)
    assert os.WTERMSIG(status) == signal.SIGABRT


@pytest.mark.parametrize("wrapper_name", ["backend", "blocked", "settled"])
def test_forked_noncreator_rejects_live_wrapper_and_only_closes_child_fds(
    wrapper_name: str,
) -> None:
    creator_pid = os.getpid()
    owned_fds: list[int] = []
    if wrapper_name == "backend":
        value = object.__new__(spawn_backend.SpawnBackend)
        value._state = spawn_backend.SpawnBackend._IDLE
        value._creator_pid = creator_pid
        value._capture_directory_fd = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        owned_fds.append(value._capture_directory_fd)
    elif wrapper_name == "blocked":
        value = object.__new__(spawn_backend.BlockedSpawn)
        value._state = spawn_backend.BlockedSpawn._OPEN
        value._creator_pid = creator_pid
        for attribute in (
            "_stdout_fd",
            "_stderr_fd",
            "_exec_error_fd",
            "_poll_pidfd",
        ):
            fd = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
            setattr(value, attribute, fd)
            owned_fds.append(fd)
        for attribute in ("_stdout_spool", "_stderr_spool"):
            fd = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
            setattr(value, attribute, SimpleNamespace(fd=fd))
            owned_fds.append(fd)
    else:
        value = object.__new__(spawn_backend.SettledJob)
        value._state = spawn_backend.SettledJob._OPEN
        value._creator_pid = creator_pid
        value._observation = object()

    child_pid = os.fork()
    if child_pid == 0:
        try:
            try:
                if wrapper_name == "backend":
                    _ = value.state
                elif wrapper_name == "blocked":
                    _ = value.job_key
                else:
                    _ = value.observation
            except spawn_backend.BackendStateError:
                pass
            else:
                os._exit(72)
            del value
            gc.collect()
            for fd in owned_fds:
                try:
                    fcntl.fcntl(fd, fcntl.F_GETFD)
                except OSError as exc:
                    if exc.errno == errno.EBADF:
                        continue
                    os._exit(73)
                os._exit(74)
            os._exit(0)
        except BaseException:
            os._exit(75)

    try:
        waited_pid, status = os.waitpid(child_pid, 0)
        assert waited_pid == child_pid
        assert os.WIFEXITED(status)
        assert os.WEXITSTATUS(status) == 0
        for fd in owned_fds:
            assert fcntl.fcntl(fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC
    finally:
        value._state = value._CLOSED if wrapper_name == "backend" else value._CONSUMED
        for fd in owned_fds:
            os.close(fd)
