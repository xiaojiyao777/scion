"""Immutable facts for the generic contained-process execution boundary.

This module intentionally contains no process, cgroup, filesystem, or systemd
authority.  It validates copied facts and provides deterministic, strict
codecs for the live authority owners in the sibling modules.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, fields
from enum import Enum
from typing import Mapping, Optional, Tuple, Type, TypeVar


_UINT64_MAX = (1 << 64) - 1
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_JOB_NAME_RE = re.compile(r"job-(0|[1-9][0-9]{0,19})-([0-9a-f]{16})\Z")
_CGROUP_FIELD_RE = re.compile(r"[a-z][a-z0-9_.-]*\Z")
_DECIMAL_RE = re.compile(r"0|[1-9][0-9]*\Z")


class ModelValidationError(ValueError):
    """A copied execution fact is malformed or noncanonical."""


class _FinalFact:
    """Allow direct facts while rejecting subclasses of those facts."""

    __slots__ = ()

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls.__bases__ != (_FinalFact,):
            raise TypeError(f"{cls.__bases__[0].__name__} is not subclassable")

    def to_mapping(self) -> dict[str, object]:
        return {
            item.name: _encode_mapping_value(getattr(self, item.name))
            for item in fields(self)
        }

    @classmethod
    def from_pairs(cls, value: Tuple[Tuple[str, object], ...]) -> "_FinalFact":
        """Decode ordered fields while preserving duplicate-key rejection."""

        pairs = _exact_tuple(value, field=f"{cls.__name__} pairs")
        decoded: dict[str, object] = {}
        for index, pair in enumerate(pairs):
            pair_tuple = _exact_tuple(pair, field=f"{cls.__name__} pairs[{index}]")
            if len(pair_tuple) != 2:
                raise ModelValidationError(
                    f"{cls.__name__} pairs[{index}] must contain two items"
                )
            key = _exact_str(pair_tuple[0], field=f"{cls.__name__} pairs[{index}][0]")
            if key in decoded:
                raise ModelValidationError(f"duplicate {cls.__name__} field {key!r}")
            decoded[key] = pair_tuple[1]
        decoder = getattr(cls, "from_mapping")
        return decoder(decoded)


_FactT = TypeVar("_FactT", bound=_FinalFact)
_EnumT = TypeVar("_EnumT", bound=Enum)


def _require_exact_mapping_keys(
    value: Mapping[str, object], expected: Tuple[str, ...], *, label: str
) -> None:
    if type(value) is not dict:
        raise TypeError(f"{label} must be an exact dict")
    actual = tuple(value.keys())
    if any(type(key) is not str for key in actual):
        raise TypeError(f"{label} keys must be exact strings")
    missing = tuple(key for key in expected if key not in value)
    unknown = tuple(key for key in actual if key not in expected)
    if missing or unknown:
        raise ModelValidationError(
            f"{label} fields mismatch: missing={missing!r}, unknown={unknown!r}"
        )


def _exact_bool(value: object, *, field: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{field} must be an exact bool")
    return value


def _exact_int(
    value: object,
    *,
    field: str,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    if type(value) is not int:
        raise TypeError(f"{field} must be an exact int")
    if minimum is not None and value < minimum:
        raise ModelValidationError(f"{field} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ModelValidationError(f"{field} must be <= {maximum}")
    return value


def _exact_str(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field} must be an exact str")
    return value


def _exact_bytes(value: object, *, field: str) -> bytes:
    if type(value) is not bytes:
        raise TypeError(f"{field} must be exact bytes")
    return value


def _exact_sha256(value: object, *, field: str) -> str:
    text = _exact_str(value, field=field)
    if _SHA256_RE.fullmatch(text) is None:
        raise ModelValidationError(f"{field} must be 64 lowercase hexadecimal chars")
    return text


def _canonical_ascii(value: object, *, field: str) -> str:
    text = _exact_str(value, field=field)
    if not text or any(ord(char) < 0x21 or ord(char) > 0x7E for char in text):
        raise ModelValidationError(f"{field} must be nonempty canonical visible ASCII")
    return text


def _cgroup_component(value: object, *, field: str) -> str:
    text = _canonical_ascii(value, field=field)
    if "/" in text or text in (".", ".."):
        raise ModelValidationError(f"{field} must be one cgroup name component")
    return text


def _job_cgroup_name(value: object, *, field: str) -> str:
    text = _cgroup_component(value, field=field)
    match = _JOB_NAME_RE.fullmatch(text)
    if match is None or int(match.group(1), 10) > _UINT64_MAX:
        raise ModelValidationError(f"{field} must use the exact bounded job grammar")
    return text


def _absolute_exec_bytes(value: object, *, field: str) -> bytes:
    raw = _exact_bytes(value, field=field)
    if not raw.startswith(b"/") or b"\x00" in raw:
        raise ModelValidationError(f"{field} must be absolute NUL-free bytes")
    return raw


def _argument_bytes(value: object, *, field: str) -> bytes:
    raw = _exact_bytes(value, field=field)
    if b"\x00" in raw:
        raise ModelValidationError(f"{field} must be NUL-free")
    return raw


def _environment_bytes(value: object, *, field: str) -> bytes:
    raw = _argument_bytes(value, field=field)
    name, separator, _ = raw.partition(b"=")
    if not separator or not name or b"=" in name:
        raise ModelValidationError(f"{field} must be NAME=VALUE bytes")
    return raw


def _exact_tuple(value: object, *, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{field} must be an exact tuple")
    return value


def _enum_value(enum_type: Type[_EnumT], value: object, *, field: str) -> _EnumT:
    text = _exact_str(value, field=field)
    try:
        return enum_type(text)
    except ValueError as error:
        allowed = tuple(member.value for member in enum_type)
        raise ModelValidationError(f"{field} must be one of {allowed!r}") from error


def _fact_from_mapping(
    fact_type: Type[_FactT], value: object, *, field: str
) -> _FactT:
    if type(value) is not dict:
        raise TypeError(f"{field} must be an exact dict")
    decoder = getattr(fact_type, "from_mapping")
    return decoder(value)


def _encode_mapping_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, _FinalFact):
        return value.to_mapping()
    if type(value) is tuple:
        return tuple(_encode_mapping_value(item) for item in value)
    return value


def _canonical_value_bytes(value: object) -> bytes:
    if value is None:
        return b"n"
    if type(value) is bool:
        return b"t" if value else b"f"
    if type(value) is int:
        encoded = str(value).encode("ascii")
        return b"i" + str(len(encoded)).encode("ascii") + b":" + encoded
    if type(value) is str:
        encoded = value.encode("utf-8", errors="strict")
        return b"s" + str(len(encoded)).encode("ascii") + b":" + encoded
    if type(value) is bytes:
        return b"b" + str(len(value)).encode("ascii") + b":" + value
    if isinstance(value, Enum):
        return _canonical_value_bytes(value.value)
    if isinstance(value, _FinalFact):
        return _canonical_value_bytes(value.to_mapping())
    if type(value) is tuple:
        return b"q" + b"".join(_canonical_value_bytes(item) for item in value) + b"e"
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError("canonical mapping keys must be exact strings")
        return b"m" + b"".join(
            _canonical_value_bytes(key) + _canonical_value_bytes(value[key])
            for key in sorted(value)
        ) + b"e"
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def _canonical_sha256(domain: bytes, value: object) -> str:
    return hashlib.sha256(domain + b"\x00" + _canonical_value_bytes(value)).hexdigest()


class StreamAvailability(Enum):
    NOT_STARTED = "NOT_STARTED"
    UNAVAILABLE = "UNAVAILABLE"
    COMPLETE = "COMPLETE"


class LeaderOutcome(Enum):
    ZERO = "ZERO"
    NONZERO = "NONZERO"
    SIGNALLED = "SIGNALLED"


class BackendOpenPhase(Enum):
    SERVICE_CONSUME = "SERVICE_CONSUME"
    CAPTURE_DIRECTORY_ACQUIRE = "CAPTURE_DIRECTORY_ACQUIRE"
    BACKEND_ALLOCATION = "BACKEND_ALLOCATION"


class BackendOpenReason(Enum):
    INVALID_SERVICE_AUTHORITY = "INVALID_SERVICE_AUTHORITY"
    CAPTURE_DIRECTORY_INVALID = "CAPTURE_DIRECTORY_INVALID"
    CAPTURE_DIRECTORY_OPEN_FAILED = "CAPTURE_DIRECTORY_OPEN_FAILED"
    BACKEND_ALLOCATION_FAILED = "BACKEND_ALLOCATION_FAILED"
    ISSUER_INTERRUPTED = "ISSUER_INTERRUPTED"


class PreHandlePhase(Enum):
    SPEC_VALIDATION = "SPEC_VALIDATION"
    CAPTURE_PREPARE = "CAPTURE_PREPARE"
    JOB_CREATE = "JOB_CREATE"
    PRE_NATIVE_READY = "PRE_NATIVE_READY"
    NATIVE_NO_HANDLE = "NATIVE_NO_HANDLE"


class PreHandleReason(Enum):
    SPEC_INVALID = "SPEC_INVALID"
    CAPTURE_TMPFILE_UNSUPPORTED = "CAPTURE_TMPFILE_UNSUPPORTED"
    CAPTURE_ALLOCATION_FAILED = "CAPTURE_ALLOCATION_FAILED"
    CAPTURE_OPEN_FAILED = "CAPTURE_OPEN_FAILED"
    JOB_CREATE_FAILED = "JOB_CREATE_FAILED"
    NATIVE_NO_HANDLE = "NATIVE_NO_HANDLE"
    ISSUER_INTERRUPTED_PRE_HANDLE = "ISSUER_INTERRUPTED_PRE_HANDLE"


class ChildCreation(Enum):
    NOT_CALLED = "NOT_CALLED"
    NATIVE_INTERNAL_SETTLED = "NATIVE_INTERNAL_SETTLED"


class ContainedSpawnReason(Enum):
    ACTIVE_NOT_DURABLE = "ACTIVE_NOT_DURABLE"
    RELEASE_UNCERTAIN = "RELEASE_UNCERTAIN"
    EXEC_FAILED = "EXEC_FAILED"
    DESCENDANT_SURVIVED = "DESCENDANT_SURVIVED"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    ISSUER_INTERRUPTED = "ISSUER_INTERRUPTED"


class ContainedSpawnPhase(Enum):
    BLOCKED = "BLOCKED"
    SETTLING_BLOCKED = "SETTLING_BLOCKED"
    RELEASED_DRAINING = "RELEASED_DRAINING"
    LEADER_TERMINAL = "LEADER_TERMINAL"
    LEADER_REAPED_DRAINING = "LEADER_REAPED_DRAINING"
    SETTLING_DESCENDANTS = "SETTLING_DESCENDANTS"
    FAILED_SETTLING = "FAILED_SETTLING"


@dataclass(frozen=True, slots=True)
class GenericProcessSpec(_FinalFact):
    opaque_job_key: str
    executable: bytes
    argv: Tuple[bytes, ...]
    environment: Tuple[bytes, ...]
    cwd: bytes
    spec_sha256: str

    def __post_init__(self) -> None:
        _canonical_ascii(self.opaque_job_key, field="opaque_job_key")
        _absolute_exec_bytes(self.executable, field="executable")
        argv = _exact_tuple(self.argv, field="argv")
        if not argv:
            raise ModelValidationError("argv must be nonempty")
        for index, argument in enumerate(argv):
            _argument_bytes(argument, field=f"argv[{index}]")
        if argv[0] != self.executable:
            raise ModelValidationError("argv[0] must equal executable exactly")
        environment = _exact_tuple(self.environment, field="environment")
        for index, entry in enumerate(environment):
            _environment_bytes(entry, field=f"environment[{index}]")
        if tuple(sorted(environment)) != environment:
            raise ModelValidationError("environment must be sorted by exact entry bytes")
        environment_names = tuple(entry.partition(b"=")[0] for entry in environment)
        if len(set(environment_names)) != len(environment_names):
            raise ModelValidationError("environment variable names must be unique")
        _absolute_exec_bytes(self.cwd, field="cwd")
        claimed = _exact_sha256(self.spec_sha256, field="spec_sha256")
        expected = self.compute_spec_sha256(
            opaque_job_key=self.opaque_job_key,
            executable=self.executable,
            argv=self.argv,
            environment=self.environment,
            cwd=self.cwd,
        )
        if claimed != expected:
            raise ModelValidationError("spec_sha256 does not bind the exact process spec")

    @classmethod
    def create(
        cls,
        *,
        opaque_job_key: str,
        executable: bytes,
        argv: Tuple[bytes, ...],
        environment: Tuple[bytes, ...],
        cwd: bytes,
    ) -> "GenericProcessSpec":
        digest = cls.compute_spec_sha256(
            opaque_job_key=opaque_job_key,
            executable=executable,
            argv=argv,
            environment=environment,
            cwd=cwd,
        )
        return cls(opaque_job_key, executable, argv, environment, cwd, digest)

    @staticmethod
    def compute_spec_sha256(
        *,
        opaque_job_key: str,
        executable: bytes,
        argv: Tuple[bytes, ...],
        environment: Tuple[bytes, ...],
        cwd: bytes,
    ) -> str:
        return _canonical_sha256(
            b"scion.generic-process-spec.v1",
            {
                "opaque_job_key": opaque_job_key,
                "executable": executable,
                "argv": argv,
                "environment": environment,
                "cwd": cwd,
            },
        )

    @property
    def executable_sha256(self) -> str:
        return hashlib.sha256(self.executable).hexdigest()

    @property
    def argv_sha256(self) -> str:
        return _canonical_sha256(b"scion.argv.v1", self.argv)

    @property
    def environment_sha256(self) -> str:
        return _canonical_sha256(b"scion.environment.v1", self.environment)

    @property
    def cwd_sha256(self) -> str:
        return hashlib.sha256(self.cwd).hexdigest()

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "GenericProcessSpec":
        expected = (
            "opaque_job_key",
            "executable",
            "argv",
            "environment",
            "cwd",
            "spec_sha256",
        )
        _require_exact_mapping_keys(value, expected, label="GenericProcessSpec")
        return cls(
            _exact_str(value["opaque_job_key"], field="opaque_job_key"),
            _exact_bytes(value["executable"], field="executable"),
            tuple(
                _exact_bytes(item, field=f"argv[{index}]")
                for index, item in enumerate(_exact_tuple(value["argv"], field="argv"))
            ),
            tuple(
                _exact_bytes(item, field=f"environment[{index}]")
                for index, item in enumerate(
                    _exact_tuple(value["environment"], field="environment")
                )
            ),
            _exact_bytes(value["cwd"], field="cwd"),
            _exact_str(value["spec_sha256"], field="spec_sha256"),
        )


@dataclass(frozen=True, slots=True)
class JobCgroupKey(_FinalFact):
    ordinal: int
    invocation_nonce: str
    rendered_name: str
    key_sha256: str

    def __post_init__(self) -> None:
        ordinal = _exact_int(
            self.ordinal, field="ordinal", minimum=0, maximum=_UINT64_MAX
        )
        nonce = _exact_sha256(self.invocation_nonce, field="invocation_nonce")
        rendered = _exact_str(self.rendered_name, field="rendered_name")
        expected_name = f"job-{ordinal}-{nonce[:16]}"
        match = _JOB_NAME_RE.fullmatch(rendered)
        if match is None or rendered != expected_name:
            raise ModelValidationError("rendered_name is not the exact JobCgroupKey name")
        if len(rendered.encode("ascii")) > 41:
            raise ModelValidationError("rendered_name exceeds the frozen 41-byte bound")
        claimed = _exact_sha256(self.key_sha256, field="key_sha256")
        expected_digest = self.compute_key_sha256(
            ordinal=ordinal, invocation_nonce=nonce, rendered_name=rendered
        )
        if claimed != expected_digest:
            raise ModelValidationError("key_sha256 does not bind the full job key")

    @classmethod
    def create(cls, *, ordinal: int, invocation_nonce: str) -> "JobCgroupKey":
        checked_ordinal = _exact_int(
            ordinal, field="ordinal", minimum=0, maximum=_UINT64_MAX
        )
        checked_nonce = _exact_sha256(invocation_nonce, field="invocation_nonce")
        rendered = f"job-{checked_ordinal}-{checked_nonce[:16]}"
        return cls(
            checked_ordinal,
            checked_nonce,
            rendered,
            cls.compute_key_sha256(
                ordinal=checked_ordinal,
                invocation_nonce=checked_nonce,
                rendered_name=rendered,
            ),
        )

    @classmethod
    def from_rendered(
        cls, *, rendered_name: str, invocation_nonce: str
    ) -> "JobCgroupKey":
        rendered = _exact_str(rendered_name, field="rendered_name")
        match = _JOB_NAME_RE.fullmatch(rendered)
        if match is None:
            raise ModelValidationError("rendered_name has invalid JobCgroupKey grammar")
        ordinal_text = match.group(1)
        ordinal = int(ordinal_text, 10)
        decoded = cls.create(ordinal=ordinal, invocation_nonce=invocation_nonce)
        if decoded.rendered_name != rendered:
            raise ModelValidationError(
                "rendered_name nonce prefix disagrees with the full invocation nonce"
            )
        return decoded

    @staticmethod
    def compute_key_sha256(
        *, ordinal: int, invocation_nonce: str, rendered_name: str
    ) -> str:
        return _canonical_sha256(
            b"scion.job-cgroup-key.v1",
            {
                "ordinal": ordinal,
                "invocation_nonce": invocation_nonce,
                "rendered_name": rendered_name,
            },
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "JobCgroupKey":
        expected = ("ordinal", "invocation_nonce", "rendered_name", "key_sha256")
        _require_exact_mapping_keys(value, expected, label="JobCgroupKey")
        return cls(
            _exact_int(value["ordinal"], field="ordinal"),
            _exact_str(value["invocation_nonce"], field="invocation_nonce"),
            _exact_str(value["rendered_name"], field="rendered_name"),
            _exact_str(value["key_sha256"], field="key_sha256"),
        )


@dataclass(frozen=True, slots=True)
class ProcessIdentity(_FinalFact):
    pid: int
    proc_starttime_ticks: int
    pidfd_device: int
    pidfd_inode: int
    creator_pid: int
    creator_starttime_ticks: int

    def __post_init__(self) -> None:
        _exact_int(self.pid, field="pid", minimum=1)
        _exact_int(self.proc_starttime_ticks, field="proc_starttime_ticks", minimum=1)
        _exact_int(self.pidfd_device, field="pidfd_device", minimum=0)
        _exact_int(self.pidfd_inode, field="pidfd_inode", minimum=1)
        _exact_int(self.creator_pid, field="creator_pid", minimum=1)
        _exact_int(
            self.creator_starttime_ticks,
            field="creator_starttime_ticks",
            minimum=1,
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ProcessIdentity":
        expected = (
            "pid",
            "proc_starttime_ticks",
            "pidfd_device",
            "pidfd_inode",
            "creator_pid",
            "creator_starttime_ticks",
        )
        _require_exact_mapping_keys(value, expected, label="ProcessIdentity")
        return cls(*( _exact_int(value[name], field=name) for name in expected ))


@dataclass(frozen=True, slots=True)
class WaitFact(_FinalFact):
    pid: int
    uid: int
    si_code: int
    si_status: int
    wait_status: int
    return_code: int
    signal: int
    core_dumped: bool

    def __post_init__(self) -> None:
        pid = _exact_int(self.pid, field="pid", minimum=1)
        del pid
        _exact_int(self.uid, field="uid", minimum=0)
        code = _exact_int(self.si_code, field="si_code", minimum=1, maximum=3)
        status = _exact_int(self.si_status, field="si_status", minimum=0, maximum=255)
        wait_status = _exact_int(self.wait_status, field="wait_status", minimum=0)
        return_code = _exact_int(self.return_code, field="return_code", minimum=-255, maximum=255)
        signal_number = _exact_int(self.signal, field="signal", minimum=0, maximum=255)
        core_dumped = _exact_bool(self.core_dumped, field="core_dumped")
        if code == 1:
            expected = (status << 8, status, 0, False)
        else:
            expected_core = code == 3
            expected = (
                status | (0x80 if expected_core else 0),
                -status,
                status,
                expected_core,
            )
            if status == 0:
                raise ModelValidationError("signalled WaitFact must contain a signal")
        if (wait_status, return_code, signal_number, core_dumped) != expected:
            raise ModelValidationError("WaitFact fields are not one coherent native wait tuple")

    @classmethod
    def from_native(cls, value: Tuple[int, ...]) -> "WaitFact":
        raw = _exact_tuple(value, field="native_wait")
        if len(raw) != 8:
            raise ModelValidationError("native_wait must contain exactly eight fields")
        ints = tuple(
            _exact_int(item, field=f"native_wait[{index}]")
            for index, item in enumerate(raw)
        )
        return cls(*ints[:7], bool(ints[7]) if ints[7] in (0, 1) else ints[7])

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "WaitFact":
        expected = (
            "pid",
            "uid",
            "si_code",
            "si_status",
            "wait_status",
            "return_code",
            "signal",
            "core_dumped",
        )
        _require_exact_mapping_keys(value, expected, label="WaitFact")
        return cls(
            *(_exact_int(value[name], field=name) for name in expected[:-1]),
            _exact_bool(value["core_dumped"], field="core_dumped"),
        )


@dataclass(frozen=True, slots=True)
class CapturedStream(_FinalFact):
    data: bytes
    byte_length: int
    sha256: str

    def __post_init__(self) -> None:
        data = _exact_bytes(self.data, field="data")
        length = _exact_int(self.byte_length, field="byte_length", minimum=0)
        if length != len(data):
            raise ModelValidationError("byte_length does not equal the complete stream length")
        claimed = _exact_sha256(self.sha256, field="sha256")
        if claimed != hashlib.sha256(data).hexdigest():
            raise ModelValidationError("sha256 does not match the complete stream bytes")

    @classmethod
    def from_bytes(cls, data: bytes) -> "CapturedStream":
        raw = _exact_bytes(data, field="data")
        return cls(raw, len(raw), hashlib.sha256(raw).hexdigest())

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "CapturedStream":
        expected = ("data", "byte_length", "sha256")
        _require_exact_mapping_keys(value, expected, label="CapturedStream")
        return cls(
            _exact_bytes(value["data"], field="data"),
            _exact_int(value["byte_length"], field="byte_length"),
            _exact_str(value["sha256"], field="sha256"),
        )


@dataclass(frozen=True, slots=True)
class FilesystemIdentity(_FinalFact):
    device: int
    inode: int

    def __post_init__(self) -> None:
        _exact_int(self.device, field="device", minimum=0)
        _exact_int(self.inode, field="inode", minimum=1)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "FilesystemIdentity":
        expected = ("device", "inode")
        _require_exact_mapping_keys(value, expected, label="FilesystemIdentity")
        return cls(
            _exact_int(value["device"], field="device"),
            _exact_int(value["inode"], field="inode"),
        )


@dataclass(frozen=True, slots=True)
class ServiceCgroupLineage(_FinalFact):
    service_name: str
    supervisor_name: str
    service_device: int
    service_inode: int
    supervisor_device: int
    supervisor_inode: int
    service_relative_lineage: Tuple[str, ...]

    def __post_init__(self) -> None:
        service = _cgroup_component(self.service_name, field="service_name")
        supervisor = _cgroup_component(self.supervisor_name, field="supervisor_name")
        if supervisor != "supervisor":
            raise ModelValidationError("supervisor_name must be literal 'supervisor'")
        _exact_int(self.service_device, field="service_device", minimum=0)
        _exact_int(self.service_inode, field="service_inode", minimum=1)
        _exact_int(self.supervisor_device, field="supervisor_device", minimum=0)
        _exact_int(self.supervisor_inode, field="supervisor_inode", minimum=1)
        lineage = _exact_tuple(
            self.service_relative_lineage, field="service_relative_lineage"
        )
        for index, component in enumerate(lineage):
            _cgroup_component(component, field=f"service_relative_lineage[{index}]")
        if lineage != (service, supervisor):
            raise ModelValidationError(
                "service_relative_lineage must be exactly (service_name, supervisor_name)"
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ServiceCgroupLineage":
        expected = (
            "service_name",
            "supervisor_name",
            "service_device",
            "service_inode",
            "supervisor_device",
            "supervisor_inode",
            "service_relative_lineage",
        )
        _require_exact_mapping_keys(value, expected, label="ServiceCgroupLineage")
        return cls(
            _exact_str(value["service_name"], field="service_name"),
            _exact_str(value["supervisor_name"], field="supervisor_name"),
            _exact_int(value["service_device"], field="service_device"),
            _exact_int(value["service_inode"], field="service_inode"),
            _exact_int(value["supervisor_device"], field="supervisor_device"),
            _exact_int(value["supervisor_inode"], field="supervisor_inode"),
            tuple(
                _exact_str(item, field=f"service_relative_lineage[{index}]")
                for index, item in enumerate(
                    _exact_tuple(
                        value["service_relative_lineage"],
                        field="service_relative_lineage",
                    )
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class CgroupIdentity(_FinalFact):
    service_name: str
    supervisor_name: str
    job_name: str
    service_device: int
    service_inode: int
    supervisor_device: int
    supervisor_inode: int
    job_device: int
    job_inode: int
    service_relative_lineage: Tuple[str, ...]

    def __post_init__(self) -> None:
        _cgroup_component(self.service_name, field="service_name")
        supervisor = _cgroup_component(self.supervisor_name, field="supervisor_name")
        if supervisor != "supervisor":
            raise ModelValidationError("supervisor_name must be literal 'supervisor'")
        job = _job_cgroup_name(self.job_name, field="job_name")
        for name in (
            "service_device",
            "supervisor_device",
            "job_device",
        ):
            _exact_int(getattr(self, name), field=name, minimum=0)
        for name in ("service_inode", "supervisor_inode", "job_inode"):
            _exact_int(getattr(self, name), field=name, minimum=1)
        lineage = _exact_tuple(
            self.service_relative_lineage, field="service_relative_lineage"
        )
        for index, component in enumerate(lineage):
            _cgroup_component(component, field=f"service_relative_lineage[{index}]")
        if lineage != (self.service_name, job):
            raise ModelValidationError(
                "service_relative_lineage must be exactly (service_name, job_name)"
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "CgroupIdentity":
        expected = (
            "service_name",
            "supervisor_name",
            "job_name",
            "service_device",
            "service_inode",
            "supervisor_device",
            "supervisor_inode",
            "job_device",
            "job_inode",
            "service_relative_lineage",
        )
        _require_exact_mapping_keys(value, expected, label="CgroupIdentity")
        return cls(
            _exact_str(value["service_name"], field="service_name"),
            _exact_str(value["supervisor_name"], field="supervisor_name"),
            _exact_str(value["job_name"], field="job_name"),
            *(_exact_int(value[name], field=name) for name in expected[3:9]),
            tuple(
                _exact_str(item, field=f"service_relative_lineage[{index}]")
                for index, item in enumerate(
                    _exact_tuple(
                        value["service_relative_lineage"],
                        field="service_relative_lineage",
                    )
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class CgroupEventsFact(_FinalFact):
    raw: bytes
    populated: int
    frozen: int
    fields: Tuple[Tuple[str, int], ...]

    def __post_init__(self) -> None:
        decoded = self.decode(_exact_bytes(self.raw, field="raw"))
        populated = _exact_int(self.populated, field="populated", minimum=0, maximum=1)
        frozen = _exact_int(self.frozen, field="frozen", minimum=0, maximum=1)
        pairs = _exact_tuple(self.fields, field="fields")
        checked_pairs = []
        for index, pair in enumerate(pairs):
            pair_tuple = _exact_tuple(pair, field=f"fields[{index}]")
            if len(pair_tuple) != 2:
                raise ModelValidationError(f"fields[{index}] must contain two items")
            checked_pairs.append(
                (
                    _exact_str(pair_tuple[0], field=f"fields[{index}][0]"),
                    _exact_int(pair_tuple[1], field=f"fields[{index}][1]"),
                )
            )
        if (
            populated != decoded.populated
            or frozen != decoded.frozen
            or tuple(checked_pairs) != decoded.fields
        ):
            raise ModelValidationError("decoded cgroup.events fields do not match raw bytes")

    @classmethod
    def decode(cls, raw: bytes) -> "CgroupEventsFact":
        data = _exact_bytes(raw, field="raw")
        if not data or not data.endswith(b"\n") or b"\x00" in data:
            raise ModelValidationError("cgroup.events must be nonempty canonical line bytes")
        try:
            text = data.decode("ascii", errors="strict")
        except UnicodeDecodeError as error:
            raise ModelValidationError("cgroup.events must be exact ASCII") from error
        pairs = []
        seen = set()
        for index, line in enumerate(text[:-1].split("\n")):
            if line.count(" ") != 1:
                raise ModelValidationError(f"cgroup.events line {index} is malformed")
            key, raw_value = line.split(" ", 1)
            if _CGROUP_FIELD_RE.fullmatch(key) is None:
                raise ModelValidationError(f"cgroup.events key {key!r} is noncanonical")
            if key in seen:
                raise ModelValidationError(f"duplicate cgroup.events key {key!r}")
            if _DECIMAL_RE.fullmatch(raw_value) is None:
                raise ModelValidationError(
                    f"cgroup.events value for {key!r} is noncanonical"
                )
            seen.add(key)
            pairs.append((key, int(raw_value, 10)))
        field_map = dict(pairs)
        for required in ("populated", "frozen"):
            if required not in field_map:
                raise ModelValidationError(f"cgroup.events missing {required!r}")
            if field_map[required] not in (0, 1):
                raise ModelValidationError(f"cgroup.events {required!r} must be 0 or 1")
        instance = object.__new__(cls)
        object.__setattr__(instance, "raw", data)
        object.__setattr__(instance, "populated", field_map["populated"])
        object.__setattr__(instance, "frozen", field_map["frozen"])
        object.__setattr__(instance, "fields", tuple(pairs))
        return instance

    def value(self, key: str) -> int:
        checked = _exact_str(key, field="key")
        for name, value in self.fields:
            if name == checked:
                return value
        raise KeyError(checked)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "CgroupEventsFact":
        expected = ("raw", "populated", "frozen", "fields")
        _require_exact_mapping_keys(value, expected, label="CgroupEventsFact")
        raw_pairs = _exact_tuple(value["fields"], field="fields")
        pairs = []
        for index, pair in enumerate(raw_pairs):
            pair_tuple = _exact_tuple(pair, field=f"fields[{index}]")
            if len(pair_tuple) != 2:
                raise ModelValidationError(f"fields[{index}] must contain two items")
            pairs.append(
                (
                    _exact_str(pair_tuple[0], field=f"fields[{index}][0]"),
                    _exact_int(pair_tuple[1], field=f"fields[{index}][1]"),
                )
            )
        return cls(
            _exact_bytes(value["raw"], field="raw"),
            _exact_int(value["populated"], field="populated"),
            _exact_int(value["frozen"], field="frozen"),
            tuple(pairs),
        )


def _leader_outcome(wait_fact: WaitFact) -> LeaderOutcome:
    if wait_fact.signal:
        return LeaderOutcome.SIGNALLED
    if wait_fact.return_code == 0:
        return LeaderOutcome.ZERO
    return LeaderOutcome.NONZERO


@dataclass(frozen=True, slots=True)
class ClosedSpawnObservation(_FinalFact):
    opaque_job_key: str
    process_spec_sha256: str
    executable_sha256: str
    argv_sha256: str
    environment_sha256: str
    cwd_sha256: str
    start_wall_ns: int
    end_wall_ns: int
    start_monotonic_ns: int
    end_monotonic_ns: int
    process_identity: ProcessIdentity
    wait_fact: WaitFact
    stdout: CapturedStream
    stderr: CapturedStream
    exec_error_clean_eof: bool
    cgroup_identity: CgroupIdentity
    initial_cgroup_events: CgroupEventsFact
    final_cgroup_events: CgroupEventsFact
    leader_outcome: LeaderOutcome

    def __post_init__(self) -> None:
        _canonical_ascii(self.opaque_job_key, field="opaque_job_key")
        for name in (
            "process_spec_sha256",
            "executable_sha256",
            "argv_sha256",
            "environment_sha256",
            "cwd_sha256",
        ):
            _exact_sha256(getattr(self, name), field=name)
        _exact_int(self.start_wall_ns, field="start_wall_ns", minimum=0)
        _exact_int(self.end_wall_ns, field="end_wall_ns", minimum=0)
        start_mono = _exact_int(
            self.start_monotonic_ns, field="start_monotonic_ns", minimum=0
        )
        end_mono = _exact_int(
            self.end_monotonic_ns, field="end_monotonic_ns", minimum=0
        )
        if end_mono < start_mono:
            raise ModelValidationError("end_monotonic_ns precedes start_monotonic_ns")
        for name, fact_type in (
            ("process_identity", ProcessIdentity),
            ("wait_fact", WaitFact),
            ("stdout", CapturedStream),
            ("stderr", CapturedStream),
            ("cgroup_identity", CgroupIdentity),
            ("initial_cgroup_events", CgroupEventsFact),
            ("final_cgroup_events", CgroupEventsFact),
        ):
            if type(getattr(self, name)) is not fact_type:
                raise TypeError(f"{name} must be exact {fact_type.__name__}")
        if self.process_identity.pid != self.wait_fact.pid:
            raise ModelValidationError("process and wait identities disagree")
        if not _exact_bool(self.exec_error_clean_eof, field="exec_error_clean_eof"):
            raise ModelValidationError("positive observation requires clean exec-error EOF")
        if (
            self.initial_cgroup_events.populated != 0
            or self.initial_cgroup_events.frozen != 0
        ):
            raise ModelValidationError("initial job cgroup must be empty and thawed")
        if (
            self.final_cgroup_events.populated != 0
            or self.final_cgroup_events.frozen != 0
        ):
            raise ModelValidationError(
                "positive observation requires final empty and thawed cgroup"
            )
        if type(self.leader_outcome) is not LeaderOutcome:
            raise TypeError("leader_outcome must be exact LeaderOutcome")
        if self.leader_outcome is not _leader_outcome(self.wait_fact):
            raise ModelValidationError("leader_outcome disagrees with WaitFact")

    @property
    def observation_sha256(self) -> str:
        return _canonical_sha256(b"scion.closed-spawn-observation.v1", self.to_mapping())

    @classmethod
    def create(
        cls,
        *,
        spec: GenericProcessSpec,
        start_wall_ns: int,
        end_wall_ns: int,
        start_monotonic_ns: int,
        end_monotonic_ns: int,
        process_identity: ProcessIdentity,
        wait_fact: WaitFact,
        stdout: CapturedStream,
        stderr: CapturedStream,
        cgroup_identity: CgroupIdentity,
        initial_cgroup_events: CgroupEventsFact,
        final_cgroup_events: CgroupEventsFact,
    ) -> "ClosedSpawnObservation":
        if type(spec) is not GenericProcessSpec:
            raise TypeError("spec must be exact GenericProcessSpec")
        return cls(
            spec.opaque_job_key,
            spec.spec_sha256,
            spec.executable_sha256,
            spec.argv_sha256,
            spec.environment_sha256,
            spec.cwd_sha256,
            start_wall_ns,
            end_wall_ns,
            start_monotonic_ns,
            end_monotonic_ns,
            process_identity,
            wait_fact,
            stdout,
            stderr,
            True,
            cgroup_identity,
            initial_cgroup_events,
            final_cgroup_events,
            _leader_outcome(wait_fact),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ClosedSpawnObservation":
        expected = tuple(item.name for item in fields(cls))
        _require_exact_mapping_keys(value, expected, label="ClosedSpawnObservation")
        return cls(
            *(_exact_str(value[name], field=name) for name in expected[:6]),
            *(_exact_int(value[name], field=name) for name in expected[6:10]),
            _fact_from_mapping(ProcessIdentity, value["process_identity"], field="process_identity"),
            _fact_from_mapping(WaitFact, value["wait_fact"], field="wait_fact"),
            _fact_from_mapping(CapturedStream, value["stdout"], field="stdout"),
            _fact_from_mapping(CapturedStream, value["stderr"], field="stderr"),
            _exact_bool(value["exec_error_clean_eof"], field="exec_error_clean_eof"),
            _fact_from_mapping(CgroupIdentity, value["cgroup_identity"], field="cgroup_identity"),
            _fact_from_mapping(CgroupEventsFact, value["initial_cgroup_events"], field="initial_cgroup_events"),
            _fact_from_mapping(CgroupEventsFact, value["final_cgroup_events"], field="final_cgroup_events"),
            _enum_value(LeaderOutcome, value["leader_outcome"], field="leader_outcome"),
        )


@dataclass(frozen=True, slots=True)
class BackendOpenFailure(_FinalFact):
    phase: BackendOpenPhase
    reason: BackendOpenReason
    service_lineage: ServiceCgroupLineage
    capture_directory_acquired: bool
    capture_directory_identity: Optional[FilesystemIdentity]
    errno: Optional[int]

    def __post_init__(self) -> None:
        if type(self.phase) is not BackendOpenPhase:
            raise TypeError("phase must be exact BackendOpenPhase")
        if type(self.reason) is not BackendOpenReason:
            raise TypeError("reason must be exact BackendOpenReason")
        if type(self.service_lineage) is not ServiceCgroupLineage:
            raise TypeError("service_lineage must be exact ServiceCgroupLineage")
        acquired = _exact_bool(
            self.capture_directory_acquired, field="capture_directory_acquired"
        )
        if acquired != (self.capture_directory_identity is not None):
            raise ModelValidationError(
                "capture_directory_identity is required iff acquisition succeeded"
            )
        if self.capture_directory_identity is not None and type(
            self.capture_directory_identity
        ) is not FilesystemIdentity:
            raise TypeError("capture_directory_identity must be exact FilesystemIdentity")
        if self.reason is BackendOpenReason.CAPTURE_DIRECTORY_OPEN_FAILED:
            if self.errno is None:
                raise ModelValidationError("capture-directory open failure requires errno")
            _exact_int(self.errno, field="errno", minimum=1)
        elif self.errno is not None:
            raise ModelValidationError("errno is legal only for CAPTURE_DIRECTORY_OPEN_FAILED")
        exact_phase = {
            BackendOpenReason.INVALID_SERVICE_AUTHORITY: BackendOpenPhase.SERVICE_CONSUME,
            BackendOpenReason.CAPTURE_DIRECTORY_INVALID: BackendOpenPhase.CAPTURE_DIRECTORY_ACQUIRE,
            BackendOpenReason.CAPTURE_DIRECTORY_OPEN_FAILED: BackendOpenPhase.CAPTURE_DIRECTORY_ACQUIRE,
            BackendOpenReason.BACKEND_ALLOCATION_FAILED: BackendOpenPhase.BACKEND_ALLOCATION,
        }.get(self.reason)
        if exact_phase is not None and self.phase is not exact_phase:
            raise ModelValidationError("BackendOpenFailure phase/reason mismatch")
        if self.reason in (
            BackendOpenReason.INVALID_SERVICE_AUTHORITY,
            BackendOpenReason.CAPTURE_DIRECTORY_INVALID,
            BackendOpenReason.CAPTURE_DIRECTORY_OPEN_FAILED,
        ) and acquired:
            raise ModelValidationError("failure reason occurs before capture acquisition")
        if self.reason is BackendOpenReason.BACKEND_ALLOCATION_FAILED and not acquired:
            raise ModelValidationError("backend allocation requires acquired capture directory")
        if self.reason is BackendOpenReason.ISSUER_INTERRUPTED:
            if self.phase is BackendOpenPhase.SERVICE_CONSUME and acquired:
                raise ModelValidationError("capture cannot be acquired during SERVICE_CONSUME")
            if self.phase is BackendOpenPhase.BACKEND_ALLOCATION and not acquired:
                raise ModelValidationError("BACKEND_ALLOCATION requires capture acquisition")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "BackendOpenFailure":
        expected = tuple(item.name for item in fields(cls))
        _require_exact_mapping_keys(value, expected, label="BackendOpenFailure")
        identity_raw = value["capture_directory_identity"]
        errno_raw = value["errno"]
        return cls(
            _enum_value(BackendOpenPhase, value["phase"], field="phase"),
            _enum_value(BackendOpenReason, value["reason"], field="reason"),
            _fact_from_mapping(ServiceCgroupLineage, value["service_lineage"], field="service_lineage"),
            _exact_bool(value["capture_directory_acquired"], field="capture_directory_acquired"),
            None
            if identity_raw is None
            else _fact_from_mapping(FilesystemIdentity, identity_raw, field="capture_directory_identity"),
            None if errno_raw is None else _exact_int(errno_raw, field="errno"),
        )


def _validate_stream_state(
    availability: StreamAvailability,
    stream: Optional[CapturedStream],
    *,
    field: str,
    allow_not_started: bool,
) -> None:
    if type(availability) is not StreamAvailability:
        raise TypeError(f"{field}_availability must be exact StreamAvailability")
    if availability is StreamAvailability.NOT_STARTED:
        if not allow_not_started:
            raise ModelValidationError(f"{field} cannot be NOT_STARTED")
        if stream is not None:
            raise ModelValidationError(f"{field} must be absent when NOT_STARTED")
    elif availability is StreamAvailability.UNAVAILABLE:
        if stream is not None:
            raise ModelValidationError(f"{field} must be absent when UNAVAILABLE")
    else:
        if type(stream) is not CapturedStream:
            raise ModelValidationError(f"{field} must be complete when COMPLETE")


def _decode_exec_error_record(record: bytes) -> Tuple[int, int]:
    raw = _exact_bytes(record, field="exec_error_record")
    if len(raw) != 12:
        raise ModelValidationError("exec-error record must contain exactly 12 bytes")
    if raw[:4] != b"SCXE":
        raise ModelValidationError("exec-error record has invalid magic")
    if raw[4] != 1:
        raise ModelValidationError("exec-error record has invalid version")
    stage = raw[5]
    if not 1 <= stage <= 13:
        raise ModelValidationError("exec-error record has invalid stage")
    if raw[6:8] != b"\x00\x00":
        raise ModelValidationError("exec-error record has nonzero reserved bytes")
    error_number = int.from_bytes(raw[8:12], "little", signed=False)
    if error_number == 0:
        raise ModelValidationError("exec-error record has invalid zero errno")
    return stage, error_number


@dataclass(frozen=True, slots=True)
class PreHandleFailure(_FinalFact):
    phase: PreHandlePhase
    reason: PreHandleReason
    native_called: bool
    native_handle_acquired: bool
    child_creation: ChildCreation
    job_cgroup_created: bool
    job_cgroup_identity: Optional[CgroupIdentity]
    initial_cgroup_events: Optional[CgroupEventsFact]
    final_cgroup_events: Optional[CgroupEventsFact]
    stdout_availability: StreamAvailability
    stdout: Optional[CapturedStream]
    stderr_availability: StreamAvailability
    stderr: Optional[CapturedStream]
    exec_error_availability: StreamAvailability
    exec_error: Optional[CapturedStream]

    def __post_init__(self) -> None:
        if type(self.phase) is not PreHandlePhase:
            raise TypeError("phase must be exact PreHandlePhase")
        if type(self.reason) is not PreHandleReason:
            raise TypeError("reason must be exact PreHandleReason")
        native_called = _exact_bool(self.native_called, field="native_called")
        if _exact_bool(
            self.native_handle_acquired, field="native_handle_acquired"
        ):
            raise ModelValidationError("PreHandleFailure cannot have a native handle")
        if type(self.child_creation) is not ChildCreation:
            raise TypeError("child_creation must be exact ChildCreation")
        expected_creation = (
            ChildCreation.NATIVE_INTERNAL_SETTLED
            if native_called
            else ChildCreation.NOT_CALLED
        )
        if self.child_creation is not expected_creation:
            raise ModelValidationError("child_creation disagrees with native_called")
        if native_called != (self.phase is PreHandlePhase.NATIVE_NO_HANDLE):
            raise ModelValidationError("native_called requires exact NATIVE_NO_HANDLE phase")
        exact_phase = {
            PreHandleReason.SPEC_INVALID: PreHandlePhase.SPEC_VALIDATION,
            PreHandleReason.CAPTURE_TMPFILE_UNSUPPORTED: PreHandlePhase.CAPTURE_PREPARE,
            PreHandleReason.CAPTURE_ALLOCATION_FAILED: PreHandlePhase.CAPTURE_PREPARE,
            PreHandleReason.CAPTURE_OPEN_FAILED: PreHandlePhase.CAPTURE_PREPARE,
            PreHandleReason.JOB_CREATE_FAILED: PreHandlePhase.JOB_CREATE,
            PreHandleReason.NATIVE_NO_HANDLE: PreHandlePhase.NATIVE_NO_HANDLE,
        }.get(self.reason)
        if exact_phase is not None and self.phase is not exact_phase:
            raise ModelValidationError("PreHandleFailure phase/reason mismatch")
        if self.reason is PreHandleReason.NATIVE_NO_HANDLE and not native_called:
            raise ModelValidationError("NATIVE_NO_HANDLE reason requires a native call")
        created = _exact_bool(self.job_cgroup_created, field="job_cgroup_created")
        cgroup_facts = (
            self.job_cgroup_identity,
            self.initial_cgroup_events,
            self.final_cgroup_events,
        )
        if created:
            expected_types = (CgroupIdentity, CgroupEventsFact, CgroupEventsFact)
            if any(type(value) is not expected for value, expected in zip(cgroup_facts, expected_types)):
                raise ModelValidationError(
                    "fully created job cgroup requires identity and initial/final events"
                )
            assert self.initial_cgroup_events is not None
            assert self.final_cgroup_events is not None
            if (
                self.initial_cgroup_events.populated != 0
                or self.initial_cgroup_events.frozen != 0
                or self.final_cgroup_events.populated != 0
                or self.final_cgroup_events.frozen != 0
            ):
                raise ModelValidationError(
                    "PreHandleFailure cgroup must be initially/finally empty and thawed"
                )
        elif any(value is not None for value in cgroup_facts):
            raise ModelValidationError("job-cgroup facts require job_cgroup_created=true")
        if self.phase in (PreHandlePhase.SPEC_VALIDATION, PreHandlePhase.CAPTURE_PREPARE):
            if created:
                raise ModelValidationError("phase occurs before job-cgroup creation")
        if self.reason is PreHandleReason.JOB_CREATE_FAILED and created:
            raise ModelValidationError("JOB_CREATE_FAILED cannot return partial authority")
        if self.phase in (PreHandlePhase.PRE_NATIVE_READY, PreHandlePhase.NATIVE_NO_HANDLE):
            if not created:
                raise ModelValidationError("phase requires a fully pinned job cgroup")
        for field_name in ("stdout", "stderr", "exec_error"):
            availability = getattr(self, f"{field_name}_availability")
            stream = getattr(self, field_name)
            _validate_stream_state(
                availability, stream, field=field_name, allow_not_started=True
            )
            if availability is not StreamAvailability.NOT_STARTED:
                raise ModelValidationError(
                    "every PreHandleFailure stream must be NOT_STARTED"
                )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "PreHandleFailure":
        expected = tuple(item.name for item in fields(cls))
        _require_exact_mapping_keys(value, expected, label="PreHandleFailure")

        def optional_fact(name: str, fact_type: Type[_FactT]) -> Optional[_FactT]:
            raw = value[name]
            return None if raw is None else _fact_from_mapping(fact_type, raw, field=name)

        return cls(
            _enum_value(PreHandlePhase, value["phase"], field="phase"),
            _enum_value(PreHandleReason, value["reason"], field="reason"),
            _exact_bool(value["native_called"], field="native_called"),
            _exact_bool(value["native_handle_acquired"], field="native_handle_acquired"),
            _enum_value(ChildCreation, value["child_creation"], field="child_creation"),
            _exact_bool(value["job_cgroup_created"], field="job_cgroup_created"),
            optional_fact("job_cgroup_identity", CgroupIdentity),
            optional_fact("initial_cgroup_events", CgroupEventsFact),
            optional_fact("final_cgroup_events", CgroupEventsFact),
            _enum_value(StreamAvailability, value["stdout_availability"], field="stdout_availability"),
            optional_fact("stdout", CapturedStream),
            _enum_value(StreamAvailability, value["stderr_availability"], field="stderr_availability"),
            optional_fact("stderr", CapturedStream),
            _enum_value(StreamAvailability, value["exec_error_availability"], field="exec_error_availability"),
            optional_fact("exec_error", CapturedStream),
        )


@dataclass(frozen=True, slots=True)
class ContainedSpawnFailure(_FinalFact):
    phase: ContainedSpawnPhase
    reason: ContainedSpawnReason
    opaque_job_key: str
    process_spec_sha256: str
    process_identity: ProcessIdentity
    wait_fact: WaitFact
    cgroup_identity: CgroupIdentity
    initial_cgroup_events: CgroupEventsFact
    final_cgroup_events: CgroupEventsFact
    stdout_availability: StreamAvailability
    stdout: Optional[CapturedStream]
    stderr_availability: StreamAvailability
    stderr: Optional[CapturedStream]
    exec_error_availability: StreamAvailability
    exec_error: Optional[CapturedStream]
    exec_error_stage: Optional[int]
    exec_error_errno: Optional[int]

    def __post_init__(self) -> None:
        if type(self.phase) is not ContainedSpawnPhase:
            raise TypeError("phase must be exact ContainedSpawnPhase")
        if type(self.reason) is not ContainedSpawnReason:
            raise TypeError("reason must be exact ContainedSpawnReason")
        if (
            self.reason is ContainedSpawnReason.ACTIVE_NOT_DURABLE
            and self.phase is not ContainedSpawnPhase.BLOCKED
        ):
            raise ModelValidationError("ACTIVE_NOT_DURABLE first occurs while BLOCKED")
        if (
            self.reason is ContainedSpawnReason.RELEASE_UNCERTAIN
            and self.phase is not ContainedSpawnPhase.RELEASED_DRAINING
        ):
            raise ModelValidationError(
                "RELEASE_UNCERTAIN first occurs while RELEASED_DRAINING"
            )
        if self.reason is ContainedSpawnReason.EXEC_FAILED and self.phase not in (
            ContainedSpawnPhase.RELEASED_DRAINING,
            ContainedSpawnPhase.LEADER_TERMINAL,
            ContainedSpawnPhase.LEADER_REAPED_DRAINING,
        ):
            raise ModelValidationError("EXEC_FAILED first occurs after release")
        if self.reason is ContainedSpawnReason.DESCENDANT_SURVIVED and self.phase not in (
            ContainedSpawnPhase.LEADER_TERMINAL,
            ContainedSpawnPhase.LEADER_REAPED_DRAINING,
            ContainedSpawnPhase.SETTLING_DESCENDANTS,
        ):
            raise ModelValidationError(
                "DESCENDANT_SURVIVED first occurs after leader terminal"
            )
        _canonical_ascii(self.opaque_job_key, field="opaque_job_key")
        _exact_sha256(self.process_spec_sha256, field="process_spec_sha256")
        for name, fact_type in (
            ("process_identity", ProcessIdentity),
            ("wait_fact", WaitFact),
            ("cgroup_identity", CgroupIdentity),
            ("initial_cgroup_events", CgroupEventsFact),
            ("final_cgroup_events", CgroupEventsFact),
        ):
            if type(getattr(self, name)) is not fact_type:
                raise TypeError(f"{name} must be exact {fact_type.__name__}")
        if self.process_identity.pid != self.wait_fact.pid:
            raise ModelValidationError("process and wait identities disagree")
        if (
            self.initial_cgroup_events.populated != 0
            or self.initial_cgroup_events.frozen != 0
        ):
            raise ModelValidationError(
                "ContainedSpawnFailure requires initial empty and thawed cgroup"
            )
        if (
            self.final_cgroup_events.populated != 0
            or self.final_cgroup_events.frozen != 0
        ):
            raise ModelValidationError(
                "ContainedSpawnFailure requires final empty and thawed cgroup"
            )
        for field_name in ("stdout", "stderr", "exec_error"):
            _validate_stream_state(
                getattr(self, f"{field_name}_availability"),
                getattr(self, field_name),
                field=field_name,
                allow_not_started=False,
            )
        if self.exec_error_availability is not StreamAvailability.COMPLETE:
            raise ModelValidationError(
                "ContainedSpawnFailure requires a complete exec-error channel"
            )
        if self.reason is ContainedSpawnReason.CAPTURE_FAILED and all(
            item is not StreamAvailability.UNAVAILABLE
            for item in (
                self.stdout_availability,
                self.stderr_availability,
            )
        ):
            raise ModelValidationError(
                "CAPTURE_FAILED requires unavailable stdout or stderr"
            )
        has_exec_record = False
        if self.exec_error_availability is StreamAvailability.COMPLETE:
            exec_error = self.exec_error
            if exec_error is None:
                raise ModelValidationError("complete exec-error stream is absent")
            if exec_error.byte_length == 0:
                if self.exec_error_stage is not None or self.exec_error_errno is not None:
                    raise ModelValidationError(
                        "clean exec-error EOF cannot carry decoded stage/errno"
                    )
            elif exec_error.byte_length == 12:
                has_exec_record = True
                if self.phase not in (
                    ContainedSpawnPhase.RELEASED_DRAINING,
                    ContainedSpawnPhase.LEADER_TERMINAL,
                    ContainedSpawnPhase.LEADER_REAPED_DRAINING,
                    ContainedSpawnPhase.SETTLING_DESCENDANTS,
                ):
                    raise ModelValidationError(
                        "exec-error record requires an exact post-release phase"
                    )
                if self.wait_fact.return_code != 127:
                    raise ModelValidationError(
                        "exec-error record requires the accepted exit-127 wait fact"
                    )
                stage, error_number = _decode_exec_error_record(exec_error.data)
                claimed_stage = _exact_int(
                    self.exec_error_stage,
                    field="exec_error_stage",
                    minimum=1,
                    maximum=13,
                )
                claimed_errno = _exact_int(
                    self.exec_error_errno, field="exec_error_errno", minimum=1
                )
                if claimed_stage != stage or claimed_errno != error_number:
                    raise ModelValidationError(
                        "decoded exec-error stage/errno disagree with the exact record"
                    )
            else:
                raise ModelValidationError(
                    "complete exec-error must be clean EOF or one exact 12-byte record"
                )
        elif self.exec_error_stage is not None or self.exec_error_errno is not None:
            raise ModelValidationError(
                "unavailable exec-error stream cannot carry decoded stage/errno"
            )
        if self.reason is ContainedSpawnReason.EXEC_FAILED and not has_exec_record:
            raise ModelValidationError(
                "EXEC_FAILED requires one exact 12-byte record and exit 127"
            )
        if self.reason is ContainedSpawnReason.ACTIVE_NOT_DURABLE and has_exec_record:
            raise ModelValidationError(
                "ACTIVE_NOT_DURABLE requires clean exec-error EOF"
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ContainedSpawnFailure":
        expected = tuple(item.name for item in fields(cls))
        _require_exact_mapping_keys(value, expected, label="ContainedSpawnFailure")

        def required_fact(name: str, fact_type: Type[_FactT]) -> _FactT:
            return _fact_from_mapping(fact_type, value[name], field=name)

        def optional_stream(name: str) -> Optional[CapturedStream]:
            raw = value[name]
            return None if raw is None else _fact_from_mapping(CapturedStream, raw, field=name)

        return cls(
            _enum_value(ContainedSpawnPhase, value["phase"], field="phase"),
            _enum_value(ContainedSpawnReason, value["reason"], field="reason"),
            _exact_str(value["opaque_job_key"], field="opaque_job_key"),
            _exact_str(value["process_spec_sha256"], field="process_spec_sha256"),
            required_fact("process_identity", ProcessIdentity),
            required_fact("wait_fact", WaitFact),
            required_fact("cgroup_identity", CgroupIdentity),
            required_fact("initial_cgroup_events", CgroupEventsFact),
            required_fact("final_cgroup_events", CgroupEventsFact),
            _enum_value(StreamAvailability, value["stdout_availability"], field="stdout_availability"),
            optional_stream("stdout"),
            _enum_value(StreamAvailability, value["stderr_availability"], field="stderr_availability"),
            optional_stream("stderr"),
            _enum_value(StreamAvailability, value["exec_error_availability"], field="exec_error_availability"),
            optional_stream("exec_error"),
            None
            if value["exec_error_stage"] is None
            else _exact_int(value["exec_error_stage"], field="exec_error_stage"),
            None
            if value["exec_error_errno"] is None
            else _exact_int(value["exec_error_errno"], field="exec_error_errno"),
        )


@dataclass(frozen=True, slots=True)
class _CleanupPermitIdentity(_FinalFact):
    backend_generation: int
    job_key: JobCgroupKey
    observation_sha256: str

    def __post_init__(self) -> None:
        _exact_int(self.backend_generation, field="backend_generation", minimum=1)
        if type(self.job_key) is not JobCgroupKey:
            raise TypeError("job_key must be exact JobCgroupKey")
        _exact_sha256(self.observation_sha256, field="observation_sha256")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "_CleanupPermitIdentity":
        expected = ("backend_generation", "job_key", "observation_sha256")
        _require_exact_mapping_keys(value, expected, label="_CleanupPermitIdentity")
        return cls(
            _exact_int(value["backend_generation"], field="backend_generation"),
            _fact_from_mapping(JobCgroupKey, value["job_key"], field="job_key"),
            _exact_str(value["observation_sha256"], field="observation_sha256"),
        )


# Keep accidental imports honest without editing the package public surface.
__all__ = [
    "BackendOpenFailure",
    "BackendOpenPhase",
    "BackendOpenReason",
    "CapturedStream",
    "CgroupEventsFact",
    "CgroupIdentity",
    "ChildCreation",
    "ClosedSpawnObservation",
    "ContainedSpawnFailure",
    "ContainedSpawnPhase",
    "ContainedSpawnReason",
    "FilesystemIdentity",
    "GenericProcessSpec",
    "JobCgroupKey",
    "LeaderOutcome",
    "ModelValidationError",
    "PreHandleFailure",
    "PreHandlePhase",
    "PreHandleReason",
    "ProcessIdentity",
    "ServiceCgroupLineage",
    "StreamAvailability",
    "WaitFact",
]
