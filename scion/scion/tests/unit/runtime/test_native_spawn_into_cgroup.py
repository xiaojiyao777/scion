from __future__ import annotations

import copy
import errno
import fcntl
import gc
import hashlib
import os
import pickle
import selectors
import signal
import struct
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

import pytest

from scion.runtime import native
import scion.runtime.native._spawn_into_cgroup as _native_extension


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.fixture(scope="session", autouse=True)
def _prove_native_artifact_identity() -> Iterator[None]:
    assert pytest.__version__ == "9.0.2"
    extension = Path(_native_extension.__file__).resolve(strict=True)
    assert extension.is_file()
    assert extension.is_relative_to(Path(sys.prefix).resolve())
    expected_extension = os.environ.get("SCION_NATIVE_EXPECTED_ELF_SHA256")
    if expected_extension:
        assert _sha256(extension) == expected_extension

    probe_raw = os.environ.get("SCION_NATIVE_PROBE")
    probe = Path(probe_raw).resolve(strict=True) if probe_raw else None
    expected_probe = os.environ.get("SCION_NATIVE_PROBE_SHA256")
    if probe is not None:
        assert probe.is_absolute() and probe.is_file()
        if expected_probe:
            assert _sha256(probe) == expected_probe

    extension_hash = _sha256(extension)
    probe_hash = _sha256(probe) if probe is not None else None
    yield
    assert Path(_native_extension.__file__).resolve(strict=True) == extension
    assert _sha256(extension) == extension_hash
    if probe is not None:
        assert _sha256(probe) == probe_hash


def _open_fd_count() -> int:
    return len(os.listdir("/proc/self/fd"))


def _stable_open_fd_flags() -> dict[int, int]:
    flags: dict[int, int] = {}
    for name in os.listdir("/proc/self/fd"):
        fd = int(name)
        try:
            flags[fd] = fcntl.fcntl(fd, fcntl.F_GETFD)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise
    return flags


@contextmanager
def _no_fd_leak() -> Iterator[None]:
    before = _open_fd_count()
    try:
        yield
    finally:
        assert _open_fd_count() == before


def _current_cgroup_fd() -> int:
    unified = next(
        line for line in Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
        if line.startswith("0::")
    )
    path = Path("/sys/fs/cgroup") / unified[3:].lstrip("/")
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)


def test_native_abi_constants_are_frozen() -> None:
    assert native.CLONE_FLAGS == (0x1000 | (1 << 33))
    assert native.CLONE_ARGS_SIZE == 88
    assert native.EXIT_SIGNAL == signal.SIGCHLD
    assert (
        native.CHILD_STDIN_FD,
        native.CHILD_STDOUT_FD,
        native.CHILD_STDERR_FD,
        native.CHILD_RELEASE_FD,
        native.CHILD_EXEC_ERROR_FD,
    ) == (0, 1, 2, 3, 4)
    assert native.RELEASE_BYTE == 1
    assert native.ERROR_RECORD_MAGIC == b"SCXE"
    assert native.ERROR_RECORD_FORMAT == "<4sBBHI"
    assert native.ERROR_RECORD_VERSION == 1
    assert native.ERROR_RECORD_SIZE == 12
    assert (
        native.ERROR_STAGE_DUP_EXEC_ERROR,
        native.ERROR_STAGE_DUP_STDIN,
        native.ERROR_STAGE_DUP_STDOUT,
        native.ERROR_STAGE_DUP_STDERR,
        native.ERROR_STAGE_DUP_RELEASE,
        native.ERROR_STAGE_CLOSE_RANGE,
        native.ERROR_STAGE_SIGNAL_DISPOSITIONS,
        native.ERROR_STAGE_SIGNAL_MASK,
        native.ERROR_STAGE_RELEASE_READ,
        native.ERROR_STAGE_RELEASE_BYTE,
        native.ERROR_STAGE_RELEASE_CLOSE,
        native.ERROR_STAGE_CHDIR,
        native.ERROR_STAGE_EXECVE,
    ) == tuple(range(1, 14))
    assert native.WAIT_RESULT_FIELDS == (
        "pid",
        "uid",
        "si_code",
        "si_status",
        "wait_status",
        "return_code",
        "signal",
        "core_dumped",
    )


def test_blocked_child_is_not_publicly_constructible_or_subclassable() -> None:
    with pytest.raises(TypeError):
        native.BlockedChild()
    with pytest.raises(TypeError):
        class Forged(native.BlockedChild):
            pass

    assert "__copy__" in native.BlockedChild.__dict__
    assert "__deepcopy__" in native.BlockedChild.__dict__
    assert "__reduce__" in native.BlockedChild.__dict__
    assert "__reduce_ex__" in native.BlockedChild.__dict__


def test_spawn_rejects_bool_cgroup_fd_before_resource_preparation() -> None:
    with _no_fd_leak():
        with pytest.raises(TypeError, match="exact int"):
            native.spawn_blocked(
                True,
                b"/bin/true",
                (b"/bin/true",),
                (),
                b"/",
            )


def test_spawn_rejects_container_and_bytes_subclasses() -> None:
    class BytesSubclass(bytes):
        pass

    class TupleSubclass(tuple):
        pass

    cases = (
        (BytesSubclass(b"/bin/true"), (b"/bin/true",), (), b"/"),
        (b"/bin/true", TupleSubclass((b"/bin/true",)), (), b"/"),
        (b"/bin/true", (BytesSubclass(b"/bin/true"),), (), b"/"),
        (b"/bin/true", (b"/bin/true",), TupleSubclass(()), b"/"),
        (b"/bin/true", (b"/bin/true",), (BytesSubclass(b"A=1"),), b"/"),
        (b"/bin/true", (b"/bin/true",), (), BytesSubclass(b"/")),
    )
    for executable, argv, env, cwd in cases:
        with _no_fd_leak(), pytest.raises(TypeError):
            native.spawn_blocked(
                -1,
                executable,
                argv,
                env,
                cwd,
            )


@pytest.mark.parametrize(
    ("cgroup_fd", "executable", "argv", "expected"),
    [
        (-1, b"/bin/true", (b"/bin/true",), ValueError),
        (1 << 80, b"/bin/true", (b"/bin/true",), OverflowError),
        (-1, b"/bin/true\0drift", (b"/bin/true",), ValueError),
        (-1, b"/bin/true", (b"/bin/true", b"bad\0arg"), ValueError),
        (-1, b"/bin/true", (), ValueError),
    ],
)
def test_spawn_rejects_invalid_fd_nul_and_empty_argv(
    cgroup_fd: int,
    executable: bytes,
    argv: tuple[bytes, ...],
    expected: type[Exception],
) -> None:
    with _no_fd_leak():
        with pytest.raises(expected):
            native.spawn_blocked(cgroup_fd, executable, argv, (), b"/")


def test_spawn_rejects_closed_cgroup_fd() -> None:
    fd = os.open("/tmp", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    os.close(fd)
    with _no_fd_leak(), pytest.raises(OSError) as raised:
        native.spawn_blocked(fd, b"/bin/true", (b"/bin/true",), (), b"/")
    assert raised.value.errno == errno.EBADF


@pytest.mark.parametrize(
    ("executable", "argv", "env", "cwd", "error"),
    [
        ("/bin/true", (b"/bin/true",), (), b"/", TypeError),
        (b"bin/true", (b"bin/true",), (), b"/", ValueError),
        (b"/bin/true", [b"/bin/true"], (), b"/", TypeError),
        (b"/bin/true", (b"not-the-executable",), (), b"/", ValueError),
        (b"/bin/true", (b"/bin/true",), (b"MISSING_EQUALS",), b"/", ValueError),
        (b"/bin/true", (b"/bin/true",), (b"A=bad\0value",), b"/", ValueError),
        (
            b"/bin/true",
            (b"/bin/true",),
            (b"A=one", b"A=two"),
            b"/",
            ValueError,
        ),
        (b"/bin/true", (b"/bin/true",), (), b"relative", ValueError),
        (b"/bin/true", (b"/bin/true",), (), b"/bad\0cwd", ValueError),
    ],
)
def test_spawn_rejects_noncanonical_inputs_before_clone(
    executable: object,
    argv: object,
    env: object,
    cwd: object,
    error: type[Exception],
) -> None:
    with _no_fd_leak():
        with pytest.raises(error):
            native.spawn_blocked(-1, executable, argv, env, cwd)


def test_spawn_rejects_non_cgroup_directory() -> None:
    fd = os.open("/tmp", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        with _no_fd_leak():
            with pytest.raises(ValueError, match="cgroup-v2"):
                native.spawn_blocked(
                    fd,
                    b"/bin/true",
                    (b"/bin/true",),
                    (),
                    b"/",
                )
    finally:
        os.close(fd)


def _custom_sigchld(_signal_number: int, _frame: object) -> None:
    return None


@pytest.mark.parametrize("handler", [signal.SIG_IGN, _custom_sigchld])
def test_spawn_rejects_nondefault_sigchld_without_clone(handler: object) -> None:
    cgroup_fd = _current_cgroup_fd()
    previous = signal.getsignal(signal.SIGCHLD)
    try:
        signal.signal(signal.SIGCHLD, handler)
        with _no_fd_leak():
            with pytest.raises(RuntimeError, match="SIGCHLD exactly SIG_DFL"):
                native.spawn_blocked(
                    cgroup_fd,
                    b"/bin/true",
                    (b"/bin/true",),
                    (),
                    b"/",
                )
    finally:
        signal.signal(signal.SIGCHLD, previous)
        os.close(cgroup_fd)


def test_spawn_rejects_multitask_process_without_clone() -> None:
    ready = threading.Event()
    stop = threading.Event()

    def worker() -> None:
        ready.set()
        stop.wait()

    thread = threading.Thread(target=worker)
    thread.start()
    assert ready.wait(5.0)
    cgroup_fd = _current_cgroup_fd()
    try:
        with _no_fd_leak():
            with pytest.raises(RuntimeError, match="exactly one process task"):
                native.spawn_blocked(
                    cgroup_fd,
                    b"/bin/true",
                    (b"/bin/true",),
                    (),
                    b"/",
                )
    finally:
        os.close(cgroup_fd)
        stop.set()
        thread.join()


def test_validation_failure_preserves_nontrivial_signal_mask() -> None:
    previous = signal.pthread_sigmask(
        signal.SIG_BLOCK, {signal.SIGUSR1, signal.SIGUSR2}
    )
    try:
        expected = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        with pytest.raises(ValueError):
            native.spawn_blocked(
                -1, b"/bin/true", (b"/bin/true",), (), b"/"
            )
        assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == expected
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def _decode_exec_error(record: bytes) -> tuple[int, int]:
    assert len(record) == native.ERROR_RECORD_SIZE
    magic, version, stage, reserved, error_number = struct.unpack(
        native.ERROR_RECORD_FORMAT, record
    )
    assert magic == native.ERROR_RECORD_MAGIC
    assert version == native.ERROR_RECORD_VERSION
    assert reserved == 0
    assert 1 <= stage <= 13
    assert error_number > 0
    return stage, error_number


def _drain_to_terminal(
    child: native.BlockedChild,
    capture_fds: tuple[int, int, int],
) -> tuple[tuple[int, ...], tuple[bytes, bytes, bytes]]:
    pidfd = child.dup_pidfd()
    buffers = {fd: bytearray() for fd in capture_fds}
    selector = selectors.DefaultSelector()
    for fd in capture_fds:
        selector.register(fd, selectors.EVENT_READ, ("capture", fd))
    selector.register(pidfd, selectors.EVENT_READ, ("pidfd", pidfd))
    terminal: tuple[int, ...] | None = None
    deadline = time.monotonic() + 10.0  # Test-only deadlock guard, not runtime policy.
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                child.send_signal(int(signal.SIGKILL))
                pytest.fail("native integration child did not terminate")
            for key, _ in selector.select(remaining):
                kind, fd = key.data
                if kind == "pidfd":
                    observed = child.peek_wait()
                    if observed is not None:
                        terminal = observed
                    selector.unregister(fd)
                    os.close(fd)
                    pidfd = -1
                    continue
                while True:
                    try:
                        chunk = os.read(fd, 65536)
                    except BlockingIOError:
                        break
                    if not chunk:
                        selector.unregister(fd)
                        os.close(fd)
                        break
                    buffers[fd].extend(chunk)
        if terminal is None:
            terminal = child.peek_wait()
        assert terminal is not None
        reaped = child.reap()
        assert reaped == terminal
        return reaped, tuple(bytes(buffers[fd]) for fd in capture_fds)
    finally:
        selector.close()
        if pidfd >= 0:
            os.close(pidfd)
        for fd in capture_fds:
            try:
                os.close(fd)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise


def _wait_for_terminal(child: native.BlockedChild) -> tuple[int, ...]:
    pidfd = child.dup_pidfd()
    selector = selectors.DefaultSelector()
    selector.register(pidfd, selectors.EVENT_READ)
    try:
        if not selector.select(10.0):
            pytest.fail("native integration child did not reach terminal state")
        terminal = child.peek_wait()
        assert terminal is not None
        return terminal
    finally:
        selector.close()
        os.close(pidfd)


def _drain_capture_fds(
    capture_fds: tuple[int, int, int],
) -> tuple[bytes, bytes, bytes]:
    buffers = {fd: bytearray() for fd in capture_fds}
    selector = selectors.DefaultSelector()
    for fd in capture_fds:
        selector.register(fd, selectors.EVENT_READ)
    deadline = time.monotonic() + 10.0
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                pytest.fail("native integration capture FDs did not reach EOF")
            for key, _ in selector.select(remaining):
                fd = key.fd
                while True:
                    try:
                        chunk = os.read(fd, 65536)
                    except BlockingIOError:
                        break
                    if not chunk:
                        selector.unregister(fd)
                        os.close(fd)
                        break
                    buffers[fd].extend(chunk)
        return tuple(bytes(buffers[fd]) for fd in capture_fds)
    finally:
        selector.close()
        for fd in capture_fds:
            try:
                os.close(fd)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise


class _DelegatedCgroup:
    def __init__(self, path: str) -> None:
        if not os.path.isabs(path) or os.path.normpath(path) != path:
            pytest.fail("SCION_TEST_DELEGATED_CGROUP must be canonical absolute")
        self.path = path
        self.fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        status = os.fstat(self.fd)
        self.identity = (status.st_dev, status.st_ino)
        self.initial_events = self.read("cgroup.events")

    def assert_identity(self) -> None:
        status = os.fstat(self.fd)
        assert (status.st_dev, status.st_ino) == self.identity

    def read(self, name: str) -> str:
        self.assert_identity()
        fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC, dir_fd=self.fd)
        try:
            chunks: list[bytes] = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    return b"".join(chunks).decode("ascii")
                chunks.append(chunk)
        finally:
            os.close(fd)

    def write(self, name: str, value: bytes) -> None:
        self.assert_identity()
        fd = os.open(name, os.O_WRONLY | os.O_CLOEXEC, dir_fd=self.fd)
        try:
            assert os.write(fd, value) == len(value)
        finally:
            os.close(fd)

    def populated(self) -> bool:
        fields = dict(
            line.split(maxsplit=1)
            for line in self.read("cgroup.events").splitlines()
        )
        return fields.get("populated") == "1"

    def member_pids(self) -> set[int]:
        return {
            int(line) for line in self.read("cgroup.procs").splitlines() if line
        }

    def kill_and_drain(self) -> None:
        if self.populated():
            self.write("cgroup.kill", b"1\n")
        deadline = time.monotonic() + 10.0  # Fixture-only deadlock guard.
        while self.populated():
            if time.monotonic() >= deadline:
                pytest.fail("delegated cgroup did not drain after cgroup.kill")
            time.sleep(0.01)

    def close(self) -> None:
        os.close(self.fd)


@pytest.fixture
def delegated_cgroup() -> Iterator[_DelegatedCgroup]:
    raw_path = os.environ.get("SCION_TEST_DELEGATED_CGROUP")
    if not raw_path:
        pytest.skip("SCION_TEST_DELEGATED_CGROUP is unavailable")
    root = _DelegatedCgroup(raw_path)
    if root.initial_events.splitlines().count("populated 0") != 1:
        root.close()
        pytest.fail("delegated native-test cgroup must initially be empty")
    leaf_name = f"case-{os.getpid()}-{time.monotonic_ns()}"
    os.mkdir(leaf_name, mode=0o755, dir_fd=root.fd)
    delegated = _DelegatedCgroup(os.path.join(raw_path, leaf_name))
    try:
        yield delegated
        delegated.assert_identity()
        assert delegated.read("cgroup.events").splitlines().count("populated 0") == 1
    finally:
        if delegated.populated():
            delegated.kill_and_drain()
        delegated.close()
        os.rmdir(leaf_name, dir_fd=root.fd)
        assert root.read("cgroup.events").splitlines().count("populated 0") == 1
        root.close()


@pytest.fixture
def native_probe() -> Path:
    raw_path = os.environ.get("SCION_NATIVE_PROBE")
    if not raw_path:
        pytest.skip("SCION_NATIVE_PROBE is unavailable")
    path = Path(raw_path).resolve(strict=True)
    assert path.is_file() and os.access(path, os.X_OK)
    expected = os.environ.get("SCION_NATIVE_PROBE_SHA256")
    if expected:
        assert _sha256(path) == expected
    return path


def _spawn_probe(
    delegated: _DelegatedCgroup,
    probe: Path,
    *arguments: str,
    cwd: bytes = b"/",
) -> native.BlockedChild:
    executable = os.fsencode(probe)
    argv = (executable, *(argument.encode("ascii") for argument in arguments))
    return native.spawn_blocked(delegated.fd, executable, argv, (b"LC_ALL=C",), cwd)


def _assert_fd_cloexec(fd: int) -> None:
    assert fcntl.fcntl(fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC


def _assert_rejected_without_authority_drift(
    child: native.BlockedChild,
    call: Callable[[], object],
    error_type: type[BaseException],
    message: str,
) -> None:
    state = child.state
    before = _stable_open_fd_flags()
    with pytest.raises(error_type, match=message):
        call()
    assert child.state == state
    assert _stable_open_fd_flags() == before


def _terminal_and_capture(
    child: native.BlockedChild,
) -> tuple[tuple[int, ...], tuple[bytes, bytes, bytes]]:
    captures = child.take_capture_fds()
    child.release()
    return _drain_to_terminal(child, captures)


@pytest.mark.integration
def test_delegated_block_release_probe_and_exact_reap(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
) -> None:
    before_fds = set(os.listdir("/proc/self/fd"))
    child = _spawn_probe(delegated_cgroup, native_probe, "inspect")
    assert type(child) is native.BlockedChild
    assert child.state == "BLOCKED"
    assert child.peek_wait() is None
    assert child.pid in delegated_cgroup.member_pids()
    assert set(os.listdir("/proc/self/fd")) > before_fds
    _assert_rejected_without_authority_drift(
        child, child.reap, RuntimeError, "requires a terminal fact"
    )
    _assert_rejected_without_authority_drift(
        child, lambda: copy.copy(child), TypeError, "cannot be copied"
    )
    _assert_rejected_without_authority_drift(
        child, lambda: copy.deepcopy(child), TypeError, "cannot be copied"
    )
    _assert_rejected_without_authority_drift(
        child, lambda: pickle.dumps(child), TypeError, "cannot be copied"
    )
    captures = child.take_capture_fds()
    for fd in captures:
        _assert_fd_cloexec(fd)
        assert fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_NONBLOCK
        with pytest.raises(BlockingIOError):
            os.read(fd, 1)
    _assert_rejected_without_authority_drift(
        child, child.take_capture_fds, RuntimeError, "exactly once"
    )
    polling_pidfd = child.dup_pidfd()
    _assert_fd_cloexec(polling_pidfd)
    os.close(polling_pidfd)
    child.release()
    _assert_rejected_without_authority_drift(
        child, child.release, RuntimeError, "one-shot"
    )
    terminal, (stdout, stderr, exec_error) = _drain_to_terminal(child, captures)
    assert terminal[0] == child.pid
    assert terminal[2:] == (os.CLD_EXITED, 0, 0, 0, 0, 0)
    assert stdout == b"INSPECT_OK\n"
    assert stderr == b"INSPECT_ERR\n"
    assert exec_error == b""
    assert child.state == "REAPED"
    _assert_rejected_without_authority_drift(
        child, child.reap, RuntimeError, "exact one-shot"
    )
    _assert_rejected_without_authority_drift(
        child, child.dup_pidfd, RuntimeError, "after reap"
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("executable", "cwd", "expected_stage", "expected_errno"),
    [
        (b"/definitely-not-a-scion-executable", b"/", 13, errno.ENOENT),
        (None, b"/definitely-not-a-scion-directory", 12, errno.ENOENT),
    ],
)
def test_delegated_exec_failures_have_fixed_records(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
    executable: bytes | None,
    cwd: bytes,
    expected_stage: int,
    expected_errno: int,
) -> None:
    path = executable if executable is not None else os.fsencode(native_probe)
    child = native.spawn_blocked(
        delegated_cgroup.fd, path, (path,), (b"LC_ALL=C",), cwd
    )
    terminal, (stdout, stderr, record) = _terminal_and_capture(child)
    assert terminal[2:4] == (os.CLD_EXITED, 127)
    assert stdout == stderr == b""
    assert _decode_exec_error(record) == (expected_stage, expected_errno)


@pytest.mark.integration
def test_delegated_exactly_one_release_starts_one_target(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "sentinel"
    child = _spawn_probe(delegated_cgroup, native_probe, "sentinel", str(sentinel))
    assert not sentinel.exists()
    terminal, (_, _, record) = _terminal_and_capture(child)
    assert terminal[2:4] == (os.CLD_EXITED, 0)
    assert record == b"" and sentinel.read_bytes() == b"executed\n"
    _assert_rejected_without_authority_drift(
        child, child.release, RuntimeError, "one-shot"
    )


@pytest.mark.integration
@pytest.mark.parametrize("handler", [signal.SIG_IGN, "custom"])
def test_blocked_child_uses_default_user_signal_disposition(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
    tmp_path: Path,
    handler: object,
) -> None:
    sentinel = tmp_path / "must-not-exist"
    calls: list[int] = []

    def custom(number: int, _frame: object) -> None:
        calls.append(number)

    previous = signal.getsignal(signal.SIGUSR1)
    signal.signal(signal.SIGUSR1, custom if handler == "custom" else handler)
    try:
        child = _spawn_probe(
            delegated_cgroup, native_probe, "sentinel", str(sentinel)
        )
        captures = child.take_capture_fds()
        child.send_signal(int(signal.SIGUSR1))
        terminal = _wait_for_terminal(child)
        assert terminal[2] in (os.CLD_KILLED, os.CLD_DUMPED)
        assert terminal[6] == signal.SIGUSR1
        with pytest.raises(BrokenPipeError):
            child.release()
        _drain_capture_fds(captures)
        assert child.reap() == terminal
        assert calls == [] and not sentinel.exists()
    finally:
        signal.signal(signal.SIGUSR1, previous)


@pytest.mark.integration
def test_parent_pending_signal_and_mask_are_preserved_but_not_inherited(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
) -> None:
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR2})
    try:
        os.kill(os.getpid(), signal.SIGUSR2)
        assert signal.SIGUSR2 in signal.sigpending()
        mask_before = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        child = _spawn_probe(delegated_cgroup, native_probe, "inspect")
        assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == mask_before
        terminal, (_, _, record) = _terminal_and_capture(child)
        assert terminal[2:4] == (os.CLD_EXITED, 0) and record == b""
        assert signal.SIGUSR2 in signal.sigpending()
        assert signal.sigwait({signal.SIGUSR2}) == signal.SIGUSR2
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["default", "ignored", "custom", "pending"])
def test_dead_reader_release_never_mutates_sigpipe_state(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
    mode: str,
) -> None:
    previous_handler = signal.getsignal(signal.SIGPIPE)
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
    calls: list[int] = []
    pending_created = False

    def handler(number: int, _frame: object) -> None:
        calls.append(number)

    try:
        if mode == "default":
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)
            signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGPIPE})
        elif mode == "ignored":
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
            signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGPIPE})
        elif mode == "custom":
            signal.signal(signal.SIGPIPE, handler)
            signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGPIPE})
        elif mode == "pending":
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)
            signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGPIPE})
            os.kill(os.getpid(), signal.SIGPIPE)
            pending_created = True
        disposition_before = signal.getsignal(signal.SIGPIPE)
        mask_before = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        pending_before = signal.SIGPIPE in signal.sigpending()
        child = _spawn_probe(delegated_cgroup, native_probe, "exit", "0")
        captures = child.take_capture_fds()
        child.send_signal(int(signal.SIGKILL))
        terminal = _wait_for_terminal(child)
        with pytest.raises(BrokenPipeError) as raised:
            child.release()
        assert raised.value.errno == errno.EPIPE
        assert child.state == "POISONED"
        assert signal.getsignal(signal.SIGPIPE) is disposition_before
        assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == mask_before
        assert (signal.SIGPIPE in signal.sigpending()) is pending_before
        assert calls == []
        _drain_capture_fds(captures)
        assert child.reap() == terminal
    finally:
        if pending_created and signal.SIGPIPE in signal.sigpending():
            assert signal.sigwait({signal.SIGPIPE}) == signal.SIGPIPE
        signal.signal(signal.SIGPIPE, previous_handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


@pytest.mark.integration
@pytest.mark.parametrize("already_terminal", [False, True])
@pytest.mark.parametrize("transfer_captures", [False, True])
def test_drop_blocked_settles_exact_leader_without_exec_or_fd_leak(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
    tmp_path: Path,
    already_terminal: bool,
    transfer_captures: bool,
) -> None:
    sentinel = tmp_path / "must-not-exist"
    gc.collect()
    before = _open_fd_count()
    child = _spawn_probe(delegated_cgroup, native_probe, "sentinel", str(sentinel))
    captures = child.take_capture_fds() if transfer_captures else None
    leader_pid = child.pid
    pidfd = child.dup_pidfd()
    if already_terminal:
        child.send_signal(int(signal.SIGKILL))
        selector = selectors.DefaultSelector()
        selector.register(pidfd, selectors.EVENT_READ)
        assert selector.select(10.0)
        selector.close()
    del child
    gc.collect()
    with pytest.raises(ChildProcessError):
        os.waitpid(leader_pid, os.WNOHANG)
    os.close(pidfd)
    if captures is not None:
        stdout, stderr, exec_error = _drain_capture_fds(captures)
        assert stdout == stderr == b""
        if exec_error:
            assert _decode_exec_error(exec_error) == (9, errno.EPIPE)
    assert not sentinel.exists()
    assert _open_fd_count() == before


def _exercise_failstop_destructor(
    delegated: _DelegatedCgroup,
    probe: Path,
    target_state: str,
    ready_fd: int,
) -> None:
    if target_state == "RELEASED":
        child = _spawn_probe(delegated, probe, "pause")
    else:
        child = _spawn_probe(delegated, probe, "exit", "0")
    captures = child.take_capture_fds()
    if target_state == "RELEASED":
        child.release()
    else:
        child.send_signal(int(signal.SIGKILL))
        _wait_for_terminal(child)
        try:
            child.release()
        except BrokenPipeError:
            pass
        assert child.state == "POISONED"
    for fd in captures:
        os.close(fd)
    assert child.state == target_state
    assert os.write(ready_fd, target_state.encode("ascii")) == len(target_state)
    os.close(ready_fd)
    del child
    gc.collect()
    os._exit(99)


@pytest.mark.integration
@pytest.mark.parametrize("target_state", ["RELEASED", "POISONED"])
def test_released_and_poisoned_destructors_fail_stop(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
    target_state: str,
) -> None:
    ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
    issuer = os.fork()
    if issuer == 0:
        os.close(ready_read)
        _exercise_failstop_destructor(
            delegated_cgroup, native_probe, target_state, ready_write
        )
    os.close(ready_write)
    assert os.read(ready_read, 32) == target_state.encode("ascii")
    os.close(ready_read)
    waited, wait_status = os.waitpid(issuer, 0)
    assert waited == issuer
    assert os.WIFSIGNALED(wait_status)
    assert os.WTERMSIG(wait_status) == signal.SIGABRT
    delegated_cgroup.kill_and_drain()


@pytest.mark.integration
def test_large_binary_output_is_drained_without_truncation(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
) -> None:
    observed_read, observed_write = os.pipe2(os.O_CLOEXEC)
    try:
        capacity = fcntl.fcntl(observed_read, fcntl.F_GETPIPE_SZ)
    finally:
        os.close(observed_read)
        os.close(observed_write)
    count = capacity + 4097
    child = _spawn_probe(delegated_cgroup, native_probe, "emit", str(count))
    captures = child.take_capture_fds()
    assert fcntl.fcntl(captures[0], fcntl.F_GETPIPE_SZ) == capacity
    # The count is evidence-driven from the observed pipe, not a runtime cap.
    child.release()
    terminal, (stdout, stderr, record) = _drain_to_terminal(child, captures)
    stdout_block = bytes(index % 251 for index in range(4096))
    stderr_block = bytes(255 - (index % 251) for index in range(4096))
    expected_stdout = (stdout_block * ((count + 4095) // 4096))[:count]
    expected_stderr = (stderr_block * ((count + 4095) // 4096))[:count]
    assert record == b"" and terminal[2:4] == (os.CLD_EXITED, 0)
    assert (len(stdout), hashlib.sha256(stdout).digest()) == (
        count,
        hashlib.sha256(expected_stdout).digest(),
    )
    assert (len(stderr), hashlib.sha256(stderr).digest()) == (
        count,
        hashlib.sha256(expected_stderr).digest(),
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("role", "argument", "code", "status", "return_code", "signal_number"),
    [
        ("exit", "0", os.CLD_EXITED, 0, 0, 0),
        ("exit", "23", os.CLD_EXITED, 23, 23, 0),
        ("raise", str(signal.SIGTERM), os.CLD_KILLED, signal.SIGTERM,
         -signal.SIGTERM, signal.SIGTERM),
    ],
)
def test_terminal_facts_are_coherent_and_one_shot(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
    role: str,
    argument: str,
    code: int,
    status: int,
    return_code: int,
    signal_number: int,
) -> None:
    child = _spawn_probe(delegated_cgroup, native_probe, role, argument)
    terminal, (_, _, record) = _terminal_and_capture(child)
    assert terminal[2] == code and terminal[3] == status
    assert terminal[5] == return_code and terminal[6] == signal_number
    assert terminal[7] == 0 and record == b""


@pytest.mark.integration
def test_capture_transfer_is_rejected_after_reap(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
) -> None:
    before = _open_fd_count()
    child = _spawn_probe(delegated_cgroup, native_probe, "exit", "0")
    child.release()
    terminal = _wait_for_terminal(child)
    assert child.reap() == terminal
    _assert_rejected_without_authority_drift(
        child, child.take_capture_fds, RuntimeError, "exactly once"
    )
    del child
    gc.collect()
    assert _open_fd_count() == before


@pytest.mark.integration
def test_core_dump_fact_when_available(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
) -> None:
    child = _spawn_probe(delegated_cgroup, native_probe, "abort")
    terminal, (_, _, record) = _terminal_and_capture(child)
    assert terminal[2] in (os.CLD_KILLED, os.CLD_DUMPED)
    assert terminal[6] == signal.SIGABRT and record == b""
    assert terminal[7] == int(terminal[2] == os.CLD_DUMPED)


def _invoke_all_methods_in_fork(
    child: native.BlockedChild,
    authority_fds: frozenset[int],
) -> tuple[int, str, dict[int, int]]:
    calls = (
        lambda: child.take_capture_fds(),
        lambda: child.release(),
        lambda: child.dup_pidfd(),
        lambda: child.send_signal(int(signal.SIGKILL)),
        lambda: child.peek_wait(),
        lambda: child.reap(),
    )
    gc.collect()
    before = _stable_open_fd_flags()
    assert authority_fds <= before.keys()
    rejected = 0
    for call in calls:
        try:
            call()
        except RuntimeError as exc:
            if "creator PID" in str(exc):
                rejected += 1
    assert _stable_open_fd_flags() == before
    return rejected, child.state, before


@pytest.mark.integration
def test_forked_handle_copy_has_no_authority_or_destructor_effect(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
) -> None:
    before_spawn = _stable_open_fd_flags()
    child = _spawn_probe(delegated_cgroup, native_probe, "exit", "9")
    after_spawn = _stable_open_fd_flags()
    authority_fds = frozenset(after_spawn.keys() - before_spawn.keys())
    assert len(authority_fds) == 5
    assert all(after_spawn[fd] & fcntl.FD_CLOEXEC for fd in authority_fds)
    report_read, report_write = os.pipe2(os.O_CLOEXEC)
    forked = os.fork()
    if forked == 0:
        os.close(report_read)
        rejected, copied_state, before_drop = _invoke_all_methods_in_fork(
            child, authority_fds
        )
        del child
        gc.collect()
        after_drop = _stable_open_fd_flags()
        expected_after_drop = {
            fd: flags
            for fd, flags in before_drop.items()
            if fd not in authority_fds
        }
        assert after_drop == expected_after_drop
        report = f"{rejected}:{copied_state}:{len(authority_fds)}".encode("ascii")
        assert os.write(report_write, report) == len(report)
        os.close(report_write)
        os._exit(0)
    os.close(report_write)
    report = os.read(report_read, 128)
    os.close(report_read)
    waited, status = os.waitpid(forked, 0)
    assert waited == forked and status == 0
    rejected_raw, copied_state, closed_raw = report.decode("ascii").split(":")
    assert int(rejected_raw) == 6 and copied_state == "BLOCKED"
    assert int(closed_raw) == 5
    assert child.state == "BLOCKED" and child.peek_wait() is None
    terminal, (_, _, record) = _terminal_and_capture(child)
    assert terminal[3] == 9 and record == b""


@pytest.mark.integration
@pytest.mark.parametrize("drift", ["task", "sigchld"])
@pytest.mark.parametrize(
    "method_name",
    [
        "take_capture_fds",
        "release",
        "dup_pidfd",
        "send_signal",
        "peek_wait",
        "reap",
    ],
)
def test_live_task_and_sigchld_drift_reject_every_authority_method(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
    drift: str,
    method_name: str,
) -> None:
    child = _spawn_probe(delegated_cgroup, native_probe, "exit", "0")
    call = {
        "take_capture_fds": child.take_capture_fds,
        "release": child.release,
        "dup_pidfd": child.dup_pidfd,
        "send_signal": lambda: child.send_signal(int(signal.SIGKILL)),
        "peek_wait": child.peek_wait,
        "reap": child.reap,
    }[method_name]
    if drift == "task":
        ready = threading.Event()
        stop = threading.Event()
        thread = threading.Thread(target=lambda: (ready.set(), stop.wait()))
        thread.start()
        assert ready.wait(5.0)
        try:
            _assert_rejected_without_authority_drift(
                child, call, RuntimeError, "exactly one process task"
            )
        finally:
            stop.set()
            thread.join()
        assert not thread.is_alive()
    else:
        previous = signal.getsignal(signal.SIGCHLD)
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        try:
            _assert_rejected_without_authority_drift(
                child, call, RuntimeError, "SIGCHLD exactly SIG_DFL"
            )
        finally:
            signal.signal(signal.SIGCHLD, previous)
    terminal, (_, _, _) = _terminal_and_capture(child)
    assert terminal[3] == 0


@pytest.mark.integration
def test_all_hidden_transferred_and_duplicated_fds_are_cloexec(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
) -> None:
    before = _stable_open_fd_flags()
    child = _spawn_probe(delegated_cgroup, native_probe, "inspect")
    after = _stable_open_fd_flags()
    hidden = set(after) - set(before)
    assert hidden
    for fd in hidden:
        assert after[fd] & fcntl.FD_CLOEXEC
    captures = child.take_capture_fds()
    duplicate = child.dup_pidfd()
    for fd in (*captures, duplicate):
        _assert_fd_cloexec(fd)
    os.close(duplicate)
    child.release()
    terminal, (_, _, record) = _drain_to_terminal(child, captures)
    assert terminal[3] == 0 and record == b""


@pytest.mark.integration
def test_fork_exec_observes_no_parent_authority_fds(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
) -> None:
    child = _spawn_probe(delegated_cgroup, native_probe, "exit", "0")
    captures = child.take_capture_fds()
    duplicate = child.dup_pidfd()
    forked = os.fork()
    if forked == 0:
        os.execve(
            native_probe,
            (os.fsencode(native_probe), b"fds"),
            {b"LC_ALL": b"C"},
        )
    waited, status = os.waitpid(forked, 0)
    assert waited == forked and status == 0
    os.close(duplicate)
    child.release()
    terminal, (_, _, record) = _drain_to_terminal(child, captures)
    assert terminal[3] == 0 and record == b""


@pytest.mark.integration
def test_denied_clone_preserves_mask_and_creates_no_child_or_fd(
    native_probe: Path,
) -> None:
    denied_fd = os.open(
        "/sys/fs/cgroup", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    )
    executable = os.fsencode(native_probe)
    children_path = Path(f"/proc/self/task/{os.getpid()}/children")
    before_children = children_path.read_bytes()
    before_fds = _open_fd_count()
    previous_mask = signal.pthread_sigmask(
        signal.SIG_BLOCK, {signal.SIGUSR1, signal.SIGUSR2}
    )
    before_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
    try:
        with pytest.raises(OSError) as raised:
            native.spawn_blocked(
                denied_fd, executable, (executable, b"exit", b"0"), (), b"/"
            )
        assert raised.value.errno in (errno.EPERM, errno.EACCES)
        assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == before_mask
        assert children_path.read_bytes() == before_children
        assert _open_fd_count() == before_fds
    finally:
        os.close(denied_fd)
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


@pytest.mark.integration
def test_leader_reap_does_not_claim_cgroup_empty(
    delegated_cgroup: _DelegatedCgroup,
    native_probe: Path,
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "descendant"
    child = _spawn_probe(delegated_cgroup, native_probe, "descendant", str(sentinel))
    terminal, (_, _, record) = _terminal_and_capture(child)
    assert terminal[2:4] == (os.CLD_EXITED, 0) and record == b""
    deadline = time.monotonic() + 10.0
    while not sentinel.exists():
        if time.monotonic() >= deadline:
            pytest.fail("setsid descendant did not publish sentinel")
        time.sleep(0.01)
    descendant_pid = int(sentinel.read_text(encoding="ascii"))
    assert descendant_pid in delegated_cgroup.member_pids()
    assert delegated_cgroup.populated()
    assert not hasattr(child, "cgroup_empty")
    delegated_cgroup.kill_and_drain()
