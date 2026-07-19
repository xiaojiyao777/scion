"""Pinned cgroup-v2 authorities for the contained execution backend.

The public :class:`ServiceCgroup` is a one-shot acquisition wrapper.  It never
creates jobs itself: ``SpawnBackend`` consumes it and receives the
package-private authority that owns all subsequent service/job operations.
Every cgroup operation after acquisition is relative to a pinned directory FD;
mutable absolute cgroup paths are never reopened.
"""

from __future__ import annotations

import errno
import os
import stat
from typing import Optional, Tuple

from .model import (
    CgroupEventsFact,
    CgroupIdentity,
    JobCgroupKey,
    ServiceCgroupLineage,
)
from .systemd255 import ConfiguredUnitProperties, InvocationLineage, UnitRole


_CGROUP_ROOT = "/sys/fs/cgroup"
_PROC_SELF_CGROUP = "/proc/self/cgroup"
_PROC_SELF_STAT = "/proc/self/stat"

_OPEN_DIRECTORY_FLAGS = (
    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
)
_OPEN_CONTROL_FLAGS = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
_OPEN_WRITE_FLAGS = os.O_WRONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
_READ_BLOCK = 64 * 1024
_CONSTRUCTION_TOKEN = object()


class CgroupValidationError(ValueError):
    """The configured receipt or initial delegated topology is invalid."""


class CgroupStateError(RuntimeError):
    """A live cgroup capability was used by the wrong owner or in the wrong state."""


class CgroupIntegrityError(RuntimeError):
    """A pinned cgroup identity or containment fact became uncertain."""


def _reject_live_copy(_self: object, _memo: object = None) -> None:
    raise TypeError("live cgroup capabilities are not copyable or pickleable")


def _read_all(fd: int, *, rewind: bool) -> bytes:
    if rewind:
        while True:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                break
            except InterruptedError:
                continue
    chunks = []
    while True:
        try:
            chunk = os.read(fd, _READ_BLOCK)
        except InterruptedError:
            continue
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _read_absolute(path: str) -> bytes:
    fd = os.open(path, _OPEN_CONTROL_FLAGS)
    try:
        return _read_all(fd, rewind=False)
    finally:
        _close_many_exact(fd)


def _open_control_at(directory_fd: int, name: str, flags: int = _OPEN_CONTROL_FLAGS) -> int:
    if type(name) is not str or not name or "/" in name or name in (".", ".."):
        raise TypeError("control name must be one exact path component")
    return os.open(name, flags, dir_fd=directory_fd)


def _read_at(directory_fd: int, name: str) -> bytes:
    fd = _open_control_at(directory_fd, name)
    try:
        return _read_all(fd, rewind=False)
    finally:
        _close_many_exact(fd)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        try:
            written = os.write(fd, view[offset:])
        except InterruptedError:
            continue
        if written <= 0:
            raise CgroupIntegrityError("cgroup control write made no progress")
        offset += written


def _parse_unified_lineage(raw: bytes) -> Tuple[str, ...]:
    try:
        text = raw.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise CgroupValidationError("/proc/self/cgroup is not exact ASCII") from exc
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].startswith("0::"):
        raise CgroupValidationError("host is not an exact unified cgroup-v2 hierarchy")
    path = lines[0][3:]
    if not path.startswith("/") or path == "/" or path.endswith("/"):
        raise CgroupValidationError("current cgroup lineage is not canonical absolute text")
    components = tuple(path[1:].split("/"))
    if any(
        not component
        or component in (".", "..")
        or any(ord(char) < 0x21 or ord(char) > 0x7E for char in component)
        for component in components
    ):
        raise CgroupValidationError("current cgroup lineage contains an invalid component")
    return components


def _parse_starttime(raw: bytes) -> int:
    right_paren = raw.rfind(b")")
    if right_paren < 0 or right_paren + 2 >= len(raw):
        raise CgroupValidationError("/proc stat record is malformed")
    fields = raw[right_paren + 2 :].split()
    if len(fields) <= 19:
        raise CgroupValidationError("/proc stat record omits process starttime")
    value = fields[19]
    if not value.isdigit() or value.startswith(b"0"):
        raise CgroupValidationError("/proc stat starttime is noncanonical")
    return int(value, 10)


def _current_starttime() -> int:
    return _parse_starttime(_read_absolute(_PROC_SELF_STAT))


def _parse_procs(raw: bytes) -> Tuple[int, ...]:
    if raw == b"":
        return ()
    if not raw.endswith(b"\n"):
        raise CgroupIntegrityError("cgroup.procs is not newline terminated")
    result = []
    for line in raw[:-1].split(b"\n"):
        if not line or not line.isdigit() or line.startswith(b"0"):
            raise CgroupIntegrityError("cgroup.procs contains a noncanonical PID")
        result.append(int(line, 10))
    if len(result) != len(set(result)):
        raise CgroupIntegrityError("cgroup.procs contains a duplicate PID")
    return tuple(result)


def _parse_controller_tokens(raw: bytes, *, field: str) -> Tuple[str, ...]:
    if not raw.endswith(b"\n"):
        raise CgroupValidationError(f"{field} is not newline terminated")
    body = raw[:-1]
    if not body:
        return ()
    if body.startswith(b" ") or body.endswith(b" ") or b"  " in body or b"\t" in body:
        raise CgroupValidationError(f"{field} is not canonical token text")
    try:
        tokens = tuple(item.decode("ascii", errors="strict") for item in body.split(b" "))
    except UnicodeDecodeError as exc:
        raise CgroupValidationError(f"{field} is not exact ASCII") from exc
    if len(tokens) != len(set(tokens)) or any(
        not token
        or any(not (char.islower() or char.isdigit() or char in "_-") for char in token)
        for token in tokens
    ):
        raise CgroupValidationError(f"{field} contains a noncanonical controller")
    return tokens


def _identity(fd: int) -> Tuple[int, int]:
    value = os.fstat(fd)
    if not stat.S_ISDIR(value.st_mode):
        raise CgroupIntegrityError("pinned cgroup authority is not a directory")
    return value.st_dev, value.st_ino


def _require_regular_at(directory_fd: int, name: str) -> None:
    value = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if not stat.S_ISREG(value.st_mode):
        raise CgroupValidationError(f"required cgroup control {name!r} is not regular")


def _child_directories(directory_fd: int) -> Tuple[str, ...]:
    children = []
    for name in os.listdir(directory_fd):
        if type(name) is not str:
            raise CgroupIntegrityError("cgroup directory yielded a non-text name")
        value = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISDIR(value.st_mode):
            children.append(name)
        elif stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode):
            raise CgroupIntegrityError("cgroup contains an unexpected filesystem node")
    return tuple(sorted(children))


def _same_identity_at(parent_fd: int, name: str, expected: Tuple[int, int]) -> bool:
    try:
        value = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return stat.S_ISDIR(value.st_mode) and (value.st_dev, value.st_ino) == expected


def _name_absent_at(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return True
    return False


def _mkdir_job_at(parent_fd: int, name: str) -> None:
    os.mkdir(name, mode=0o700, dir_fd=parent_fd)


def _rmdir_job_at(parent_fd: int, name: str) -> None:
    os.rmdir(name, dir_fd=parent_fd)


def _close_many_exact(*fds: int) -> None:
    first_error: Optional[BaseException] = None
    for fd in fds:
        if fd < 0:
            continue
        try:
            os.close(fd)
        except BaseException as exc:  # a close ambiguity is an integrity failure
            if first_error is None:
                first_error = exc
    if first_error is not None:
        raise CgroupIntegrityError("cgroup authority close was ambiguous") from first_error


def _close_many_after_fork(*fds: int) -> None:
    for fd in fds:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass


class ServiceCgroup:
    """Creator-bound, one-shot authority for the current delegated service."""

    __slots__ = (
        "_state",
        "_creator_pid",
        "_creator_starttime",
        "_service_fd",
        "_supervisor_fd",
        "_configured",
        "_invocation",
        "_lineage",
        "_available_controllers",
    )

    _OPEN = "OPEN"
    _CONSUMED = "CONSUMED"
    _CLOSED = "CLOSED"

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("ServiceCgroup is final")

    def __init__(
        self,
        token: object,
        *,
        creator_pid: int,
        creator_starttime: int,
        service_fd: int,
        supervisor_fd: int,
        configured: ConfiguredUnitProperties,
        invocation: InvocationLineage,
        lineage: ServiceCgroupLineage,
        available_controllers: Tuple[str, ...],
    ) -> None:
        if token is not _CONSTRUCTION_TOKEN:
            raise TypeError("ServiceCgroup cannot be constructed directly")
        self._state = self._OPEN
        self._creator_pid = creator_pid
        self._creator_starttime = creator_starttime
        self._service_fd = service_fd
        self._supervisor_fd = supervisor_fd
        self._configured = configured
        self._invocation = invocation
        self._lineage = lineage
        self._available_controllers = available_controllers

    @classmethod
    def open_current(
        cls,
        expected_properties: ConfiguredUnitProperties,
        expected_lineage: InvocationLineage,
    ) -> "ServiceCgroup":
        if type(expected_properties) is not ConfiguredUnitProperties:
            raise TypeError("expected_properties must be exact ConfiguredUnitProperties")
        if type(expected_lineage) is not InvocationLineage:
            raise TypeError("expected_lineage must be exact InvocationLineage")
        if (
            expected_properties.role is not UnitRole.RUN
            or expected_properties.delegate != "pids"
            or expected_properties.delegate_effective != "yes"
            or expected_properties.delegate_controllers != ("pids",)
            or expected_properties.delegate_subgroup != "supervisor"
        ):
            raise CgroupValidationError("configured delegation must be exact pids/supervisor")
        if expected_properties.unit != expected_lineage.unit:
            raise CgroupValidationError("configured unit and invocation lineage disagree")

        creator_pid = os.getpid()
        if expected_lineage.main_pid != creator_pid:
            raise CgroupValidationError("invocation MainPID is not the current guardian")
        creator_starttime = _current_starttime()
        if expected_lineage.main_starttime != creator_starttime:
            raise CgroupValidationError("invocation MainStartTime does not match /proc")

        components = _parse_unified_lineage(_read_absolute(_PROC_SELF_CGROUP))
        actual_lineage = "/" + "/".join(components)
        if actual_lineage != expected_lineage.control_group + "/supervisor":
            raise CgroupValidationError("/proc cgroup and invocation ControlGroup disagree")
        if len(components) < 2 or components[-1] != "supervisor":
            raise CgroupValidationError("current guardian is not in a supervisor leaf")
        service_name = components[-2]
        if service_name != expected_properties.unit:
            raise CgroupValidationError("service cgroup leaf does not equal configured unit")

        root_fd = service_fd = supervisor_fd = -1
        try:
            root_fd = os.open(_CGROUP_ROOT, _OPEN_DIRECTORY_FLAGS)
            _require_regular_at(root_fd, "cgroup.controllers")
            cursor_fd = root_fd
            for component in components[:-1]:
                next_fd = os.open(component, _OPEN_DIRECTORY_FLAGS, dir_fd=cursor_fd)
                previous_fd = cursor_fd
                cursor_fd = next_fd
                service_fd = cursor_fd
                if previous_fd != root_fd:
                    _close_many_exact(previous_fd)
            service_fd = cursor_fd
            if service_fd == root_fd:
                root_fd = -1
            supervisor_fd = os.open("supervisor", _OPEN_DIRECTORY_FLAGS, dir_fd=service_fd)

            service_identity = _identity(service_fd)
            supervisor_identity = _identity(supervisor_fd)
            if service_identity != (
                expected_lineage.service_device,
                expected_lineage.service_inode,
            ) or supervisor_identity != (
                expected_lineage.supervisor_device,
                expected_lineage.supervisor_inode,
            ):
                raise CgroupValidationError("pinned cgroup identities disagree with lineage")

            for directory_fd, controls in (
                (
                    service_fd,
                    ("cgroup.procs", "cgroup.controllers", "cgroup.subtree_control"),
                ),
                (supervisor_fd, ("cgroup.procs",)),
            ):
                for control in controls:
                    _require_regular_at(directory_fd, control)

            if _parse_procs(_read_at(service_fd, "cgroup.procs")):
                raise CgroupValidationError("service-root cgroup.procs must be empty")
            if _parse_procs(_read_at(supervisor_fd, "cgroup.procs")) != (creator_pid,):
                raise CgroupValidationError("supervisor must contain only the guardian PID")
            if _child_directories(service_fd) != ("supervisor",):
                raise CgroupValidationError("service root has an unexpected child cgroup")
            if _child_directories(supervisor_fd):
                raise CgroupValidationError("supervisor has an unexpected nested cgroup")

            controllers = _parse_controller_tokens(
                _read_at(service_fd, "cgroup.controllers"),
                field="cgroup.controllers",
            )
            if "pids" not in controllers:
                raise CgroupValidationError("pids is not available to the delegated subtree")
            effective = _parse_controller_tokens(
                _read_at(service_fd, "cgroup.subtree_control"),
                field="cgroup.subtree_control",
            )
            if effective != ("pids",):
                raise CgroupValidationError("only pids may be effective for the job subtree")

            lineage = ServiceCgroupLineage(
                service_name=service_name,
                supervisor_name="supervisor",
                service_device=service_identity[0],
                service_inode=service_identity[1],
                supervisor_device=supervisor_identity[0],
                supervisor_inode=supervisor_identity[1],
                service_relative_lineage=(service_name, "supervisor"),
            )
            result = cls(
                _CONSTRUCTION_TOKEN,
                creator_pid=creator_pid,
                creator_starttime=creator_starttime,
                service_fd=service_fd,
                supervisor_fd=supervisor_fd,
                configured=expected_properties,
                invocation=expected_lineage,
                lineage=lineage,
                available_controllers=controllers,
            )
            service_fd = supervisor_fd = -1
            return result
        except CgroupIntegrityError:
            raise
        except (OSError, ValueError) as exc:
            if isinstance(exc, CgroupValidationError):
                raise
            raise CgroupValidationError("current delegated cgroup validation failed") from exc
        finally:
            _close_many_exact(supervisor_fd, service_fd, root_fd)

    def _check_open_creator(self) -> None:
        if self._state != self._OPEN:
            raise CgroupStateError(f"ServiceCgroup is {self._state}")
        if os.getpid() != self._creator_pid or _current_starttime() != self._creator_starttime:
            raise CgroupStateError("ServiceCgroup used outside its creator process")

    @property
    def copied_lineage(self) -> ServiceCgroupLineage:
        self._check_open_creator()
        return self._lineage

    @property
    def invocation_lineage(self) -> InvocationLineage:
        self._check_open_creator()
        return self._invocation

    @property
    def available_controllers(self) -> Tuple[str, ...]:
        self._check_open_creator()
        return self._available_controllers

    def close_unconsumed(self) -> None:
        self._check_open_creator()
        self._validate_idle_boundary()
        service_fd, supervisor_fd = self._service_fd, self._supervisor_fd
        self._service_fd = self._supervisor_fd = -1
        self._state = self._CLOSED
        _close_many_exact(supervisor_fd, service_fd)

    def _consume(self) -> "_ServiceCgroupAuthority":
        self._check_open_creator()
        authority = _ServiceCgroupAuthority.__new__(_ServiceCgroupAuthority)
        service_fd, supervisor_fd = self._service_fd, self._supervisor_fd
        self._service_fd = self._supervisor_fd = -1
        self._state = self._CONSUMED
        authority._initialize(
            creator_pid=self._creator_pid,
            creator_starttime=self._creator_starttime,
            service_fd=service_fd,
            supervisor_fd=supervisor_fd,
            configured=self._configured,
            invocation=self._invocation,
            lineage=self._lineage,
            available_controllers=self._available_controllers,
        )
        return authority

    def _validate_idle_boundary(self) -> None:
        if _identity(self._service_fd) != (
            self._lineage.service_device,
            self._lineage.service_inode,
        ) or _identity(self._supervisor_fd) != (
            self._lineage.supervisor_device,
            self._lineage.supervisor_inode,
        ):
            raise CgroupIntegrityError("service cgroup identity drifted")
        if _child_directories(self._service_fd) != ("supervisor",):
            raise CgroupIntegrityError("service child inventory drifted")
        if _child_directories(self._supervisor_fd):
            raise CgroupIntegrityError("supervisor gained a nested cgroup")
        if _parse_procs(_read_at(self._service_fd, "cgroup.procs")):
            raise CgroupIntegrityError("service root gained a process")
        if _parse_procs(_read_at(self._supervisor_fd, "cgroup.procs")) != (
            self._creator_pid,
        ):
            raise CgroupIntegrityError("supervisor process inventory drifted")

    __copy__ = _reject_live_copy
    __deepcopy__ = _reject_live_copy
    __reduce__ = _reject_live_copy
    __reduce_ex__ = _reject_live_copy

    def __del__(self) -> None:
        state = getattr(self, "_state", self._CLOSED)
        if state != self._OPEN:
            return
        fds = (getattr(self, "_supervisor_fd", -1), getattr(self, "_service_fd", -1))
        if os.getpid() != getattr(self, "_creator_pid", -1):
            _close_many_after_fork(*fds)
            return
        os.abort()


class _ServiceCgroupAuthority:
    """Package-private service authority owned solely by ``SpawnBackend``."""

    __slots__ = (
        "_state",
        "_creator_pid",
        "_creator_starttime",
        "_service_fd",
        "_supervisor_fd",
        "_configured",
        "_invocation",
        "_lineage",
        "_available_controllers",
        "_active_job_id",
        "_retained_job",
        "_integrity_hold",
    )

    _OPEN = "OPEN"
    _CLOSED = "CLOSED"

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("_ServiceCgroupAuthority is created only by consume")

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("_ServiceCgroupAuthority is final")

    def _initialize(
        self,
        *,
        creator_pid: int,
        creator_starttime: int,
        service_fd: int,
        supervisor_fd: int,
        configured: ConfiguredUnitProperties,
        invocation: InvocationLineage,
        lineage: ServiceCgroupLineage,
        available_controllers: Tuple[str, ...],
    ) -> None:
        self._state = self._OPEN
        self._creator_pid = creator_pid
        self._creator_starttime = creator_starttime
        self._service_fd = service_fd
        self._supervisor_fd = supervisor_fd
        self._configured = configured
        self._invocation = invocation
        self._lineage = lineage
        self._available_controllers = available_controllers
        # Identity guard only: the backend wrapper is the sole live job owner.
        self._active_job_id: Optional[int] = None
        self._retained_job: Optional[CgroupIdentity] = None
        self._integrity_hold = False

    def _check_open_creator(self) -> None:
        if self._state != self._OPEN:
            raise CgroupStateError(f"service authority is {self._state}")
        if os.getpid() != self._creator_pid or _current_starttime() != self._creator_starttime:
            raise CgroupStateError("service authority used outside its creator process")

    @property
    def copied_lineage(self) -> ServiceCgroupLineage:
        self._check_open_creator()
        return self._lineage

    @property
    def invocation_lineage(self) -> InvocationLineage:
        self._check_open_creator()
        return self._invocation

    def _create_job(self, key: JobCgroupKey) -> "_JobCgroup":
        self._check_open_creator()
        if type(key) is not JobCgroupKey:
            raise TypeError("key must be exact JobCgroupKey")
        if (
            self._active_job_id is not None
            or self._retained_job is not None
            or self._integrity_hold
        ):
            raise CgroupStateError("service authority cannot create another job")
        self._validate_inventory(None)

        name = key.rendered_name
        try:
            _mkdir_job_at(self._service_fd, name)
        except BaseException as exc:
            try:
                name_absent = _name_absent_at(self._service_fd, name)
            except BaseException as proof_error:
                self._integrity_hold = True
                raise CgroupIntegrityError(
                    "job cgroup creation outcome cannot be proved absent"
                ) from proof_error
            if (
                name_absent
                and isinstance(exc, OSError)
                and exc.errno not in (errno.EEXIST, errno.EINTR)
            ):
                raise
            self._integrity_hold = True
            raise CgroupIntegrityError(
                "job cgroup creation outcome is ambiguous or name is present"
            ) from exc

        self._integrity_hold = True

        job_fd = events_fd = -1
        try:
            job_fd = os.open(name, _OPEN_DIRECTORY_FLAGS, dir_fd=self._service_fd)
            job_identity = _identity(job_fd)
            if not _same_identity_at(self._service_fd, name, job_identity):
                raise CgroupIntegrityError("new job cgroup identity is not pinned")
            for control in ("cgroup.events", "cgroup.procs", "cgroup.kill"):
                _require_regular_at(job_fd, control)
            events_fd = _open_control_at(job_fd, "cgroup.events")
            initial = CgroupEventsFact.decode(_read_all(events_fd, rewind=True))
            if initial.populated != 0 or initial.frozen != 0:
                raise CgroupIntegrityError("new job cgroup is not initially empty and thawed")
            if _parse_procs(_read_at(job_fd, "cgroup.procs")):
                raise CgroupIntegrityError("new job cgroup unexpectedly contains a process")
            if _child_directories(job_fd):
                raise CgroupIntegrityError("new job cgroup unexpectedly contains a child")
            self._validate_inventory(name)
            identity = CgroupIdentity(
                service_name=self._lineage.service_name,
                supervisor_name=self._lineage.supervisor_name,
                job_name=name,
                service_device=self._lineage.service_device,
                service_inode=self._lineage.service_inode,
                supervisor_device=self._lineage.supervisor_device,
                supervisor_inode=self._lineage.supervisor_inode,
                job_device=job_identity[0],
                job_inode=job_identity[1],
                service_relative_lineage=(self._lineage.service_name, name),
            )
            job = _JobCgroup(
                _CONSTRUCTION_TOKEN,
                owner=self,
                key=key,
                identity=identity,
                initial_events=initial,
                job_fd=job_fd,
                events_fd=events_fd,
            )
            job_fd = events_fd = -1
            self._active_job_id = id(job)
            self._integrity_hold = False
            return job
        except BaseException as exc:
            _close_many_exact(events_fd, job_fd)
            if isinstance(exc, CgroupIntegrityError):
                raise
            raise CgroupIntegrityError(
                "job cgroup creation failed after exclusive mkdir"
            ) from exc

    def _validate_inventory(self, job_name: Optional[str]) -> None:
        self._check_open_creator()
        if _identity(self._service_fd) != (
            self._lineage.service_device,
            self._lineage.service_inode,
        ) or _identity(self._supervisor_fd) != (
            self._lineage.supervisor_device,
            self._lineage.supervisor_inode,
        ):
            raise CgroupIntegrityError("service authority identity drifted")
        expected = ("supervisor",) if job_name is None else tuple(sorted(("supervisor", job_name)))
        if _child_directories(self._service_fd) != expected:
            raise CgroupIntegrityError("service child cgroup inventory drifted")
        if _child_directories(self._supervisor_fd):
            raise CgroupIntegrityError("supervisor gained a nested cgroup")
        if _parse_procs(_read_at(self._service_fd, "cgroup.procs")):
            raise CgroupIntegrityError("service root gained a process")
        if _parse_procs(_read_at(self._supervisor_fd, "cgroup.procs")) != (
            self._creator_pid,
        ):
            raise CgroupIntegrityError("supervisor process inventory drifted")

    def _job_closed(
        self,
        job: "_JobCgroup",
        identity: CgroupIdentity,
        *,
        retained: bool,
    ) -> None:
        self._check_open_creator()
        self._require_active_job(job)
        self._active_job_id = None
        self._retained_job = identity if retained else None

    def _require_active_job(self, job: "_JobCgroup") -> None:
        self._check_open_creator()
        if self._active_job_id != id(job):
            raise CgroupIntegrityError("job is not the active service job")

    def _close(self) -> None:
        self._check_open_creator()
        if self._active_job_id is not None:
            raise CgroupStateError("cannot close service authority with a live job")
        if self._integrity_hold:
            raise CgroupIntegrityError("cannot close a partially established job authority")
        if self._retained_job is None:
            self._validate_inventory(None)
        else:
            retained = self._retained_job
            self._validate_inventory(retained.job_name)
            if not _same_identity_at(
                self._service_fd,
                retained.job_name,
                (retained.job_device, retained.job_inode),
            ):
                raise CgroupIntegrityError("retained job cgroup identity drifted")
        service_fd, supervisor_fd = self._service_fd, self._supervisor_fd
        self._service_fd = self._supervisor_fd = -1
        self._state = self._CLOSED
        _close_many_exact(supervisor_fd, service_fd)

    __copy__ = _reject_live_copy
    __deepcopy__ = _reject_live_copy
    __reduce__ = _reject_live_copy
    __reduce_ex__ = _reject_live_copy

    def __del__(self) -> None:
        if getattr(self, "_state", self._CLOSED) != self._OPEN:
            return
        fds = (getattr(self, "_supervisor_fd", -1), getattr(self, "_service_fd", -1))
        if os.getpid() != getattr(self, "_creator_pid", -1):
            _close_many_after_fork(*fds)
            return
        os.abort()


class _JobCgroup:
    """Package-private pinned job-cgroup capability."""

    __slots__ = (
        "_state",
        "_creator_pid",
        "_creator_starttime",
        "_owner",
        "_key",
        "_identity",
        "_initial_events",
        "_job_fd",
        "_events_fd",
        "_spawn_dirfd_issued",
    )

    _OPEN = "OPEN"
    _CLOSED_RETAINED = "CLOSED_RETAINED"
    _REMOVED = "REMOVED"

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("_JobCgroup is final")

    def __init__(
        self,
        token: object,
        *,
        owner: _ServiceCgroupAuthority,
        key: JobCgroupKey,
        identity: CgroupIdentity,
        initial_events: CgroupEventsFact,
        job_fd: int,
        events_fd: int,
    ) -> None:
        if token is not _CONSTRUCTION_TOKEN:
            raise TypeError("_JobCgroup cannot be constructed directly")
        self._state = self._OPEN
        self._creator_pid = owner._creator_pid
        self._creator_starttime = owner._creator_starttime
        self._owner = owner
        self._key = key
        self._identity = identity
        self._initial_events = initial_events
        self._job_fd = job_fd
        self._events_fd = events_fd
        self._spawn_dirfd_issued = False

    def _check_open_creator(self) -> None:
        if self._state != self._OPEN:
            raise CgroupStateError(f"job cgroup is {self._state}")
        if os.getpid() != self._creator_pid or _current_starttime() != self._creator_starttime:
            raise CgroupStateError("job cgroup used outside its creator process")

    @property
    def key(self) -> JobCgroupKey:
        self._check_open_creator()
        return self._key

    @property
    def identity(self) -> CgroupIdentity:
        self._check_open_creator()
        return self._identity

    @property
    def initial_events(self) -> CgroupEventsFact:
        self._check_open_creator()
        return self._initial_events

    def _consume_spawn_dirfd_borrow(self) -> int:
        """Issue the pinned pre-native dirfd number exactly once.

        The FD remains owned and closed by this capability.  The execution
        backend may only pass the returned integer directly to the accepted
        native spawn call.
        """

        self._check_open_creator()
        if self._spawn_dirfd_issued:
            raise CgroupStateError("job cgroup spawn dirfd was already issued")
        self._verify_identity()
        self._owner._validate_inventory(self._identity.job_name)
        if _child_directories(self._job_fd):
            raise CgroupIntegrityError("job cgroup contains an unexpected nested cgroup")
        events = self._read_events()
        if events.populated != 0 or events.frozen != 0:
            raise CgroupIntegrityError("pre-native job cgroup is not empty and thawed")
        if _parse_procs(_read_at(self._job_fd, "cgroup.procs")):
            raise CgroupIntegrityError("pre-native job cgroup unexpectedly has a process")
        self._spawn_dirfd_issued = True
        return self._job_fd

    def _events_fileno(self) -> int:
        self._check_open_creator()
        return self._events_fd

    def _read_events(self) -> CgroupEventsFact:
        self._check_open_creator()
        self._verify_identity()
        return CgroupEventsFact.decode(_read_all(self._events_fd, rewind=True))

    def _require_blocked_leader(self, pid: int) -> None:
        """Prove the exact blocked leader and topology before release."""

        self._check_open_creator()
        if type(pid) is not int:
            raise TypeError("pid must be an exact int")
        if pid <= 0:
            raise ValueError("pid must be positive")
        if not self._spawn_dirfd_issued:
            raise CgroupStateError("job cgroup spawn dirfd was not issued")
        self._verify_identity()
        self._owner._validate_inventory(self._identity.job_name)
        if _child_directories(self._job_fd):
            raise CgroupIntegrityError("blocked job contains an unexpected nested cgroup")
        events = self._read_events()
        if events.populated != 1 or events.frozen != 0:
            raise CgroupIntegrityError("blocked job events are not populated=1/frozen=0")
        if _parse_procs(_read_at(self._job_fd, "cgroup.procs")) != (pid,):
            raise CgroupIntegrityError(
                "job cgroup does not contain only the exact blocked leader PID"
            )

    def _kill(self) -> None:
        self._check_open_creator()
        self._verify_identity()
        fd = _open_control_at(self._job_fd, "cgroup.kill", _OPEN_WRITE_FLAGS)
        try:
            _write_all(fd, b"1\n")
        finally:
            _close_many_exact(fd)

    def _final_empty(self) -> CgroupEventsFact:
        events = self._read_events()
        if events.populated != 0 or events.frozen != 0:
            raise CgroupIntegrityError("job cgroup is not empty and thawed")
        if _parse_procs(_read_at(self._job_fd, "cgroup.procs")):
            raise CgroupIntegrityError("empty job cgroup still lists a process")
        if _child_directories(self._job_fd):
            raise CgroupIntegrityError("job cgroup contains an unexpected nested cgroup")
        self._owner._validate_inventory(self._identity.job_name)
        return events

    def close_retained(self) -> CgroupEventsFact:
        self._check_open_creator()
        events = self._final_empty()
        self._owner._require_active_job(self)
        job_fd, events_fd = self._job_fd, self._events_fd
        self._job_fd = self._events_fd = -1
        self._state = self._CLOSED_RETAINED
        self._owner._job_closed(self, self._identity, retained=True)
        _close_many_exact(events_fd, job_fd)
        return events

    def remove_empty(self) -> CgroupEventsFact:
        self._check_open_creator()
        events = self._final_empty()
        self._owner._require_active_job(self)
        expected = (self._identity.job_device, self._identity.job_inode)
        if not _same_identity_at(self._owner._service_fd, self._identity.job_name, expected):
            raise CgroupIntegrityError("job identity drifted before removal")
        _rmdir_job_at(self._owner._service_fd, self._identity.job_name)
        if not _name_absent_at(self._owner._service_fd, self._identity.job_name):
            raise CgroupIntegrityError("a cgroup name remains after exact job removal")
        job_fd, events_fd = self._job_fd, self._events_fd
        self._job_fd = self._events_fd = -1
        self._state = self._REMOVED
        self._owner._job_closed(self, self._identity, retained=False)
        _close_many_exact(events_fd, job_fd)
        return events

    def _verify_identity(self) -> None:
        if _identity(self._job_fd) != (
            self._identity.job_device,
            self._identity.job_inode,
        ) or not _same_identity_at(
            self._owner._service_fd,
            self._identity.job_name,
            (self._identity.job_device, self._identity.job_inode),
        ):
            raise CgroupIntegrityError("pinned job cgroup identity drifted")

    __copy__ = _reject_live_copy
    __deepcopy__ = _reject_live_copy
    __reduce__ = _reject_live_copy
    __reduce_ex__ = _reject_live_copy

    def __del__(self) -> None:
        if getattr(self, "_state", self._REMOVED) != self._OPEN:
            return
        fds = (getattr(self, "_events_fd", -1), getattr(self, "_job_fd", -1))
        if os.getpid() != getattr(self, "_creator_pid", -1):
            _close_many_after_fork(*fds)
            return
        os.abort()


__all__ = [
    "CgroupIntegrityError",
    "CgroupStateError",
    "CgroupValidationError",
    "ServiceCgroup",
]
