"""Read-only systemd-255 and Linux acquisition for the execution contract."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Mapping, Protocol

from .systemd255 import (
    ConfiguredUnitProperties,
    InvocationLineage,
    StopPostEnvironment,
    StopPostTopology,
    Systemd255ContractError,
    UnitHandoffProperties,
    UnitRole,
    validate_run_close_pair,
)

_UNIT_RE = re.compile(r"[A-Za-z0-9:_.@-]+\.service\Z")
_INVOCATION_RE = re.compile(r"[0-9a-f]{32}\Z")
_BOOT_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-" r"[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_SECTION_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*\Z")
_DIRECTIVE_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*\Z")
_UINT64_MAX = (1 << 64) - 1

_RUN_EXPANDED = (
    "Id",
    "Type",
    "User",
    "Group",
    "UMask",
    "ExecStart",
    "ExecStopPost",
    "ExitType",
    "SendSIGKILL",
    "OOMPolicy",
    "NoNewPrivileges",
    "PrivateTmp",
    "PrivateMounts",
    "ProtectSystem",
    "ProtectHome",
    "ProtectControlGroups",
    "ProtectProc",
    "ProcSubset",
    "ReadOnlyPaths",
    "ReadWritePaths",
    "Delegate",
    "DelegateControllers",
    "DelegateSubgroup",
    "CollectMode",
    "Restart",
    "KillMode",
    "TimeoutStopUSec",
    "OnSuccess",
    "OnFailure",
)
_CLOSE_EXPANDED = (
    "Id",
    "Type",
    "User",
    "Group",
    "UMask",
    "ExecStart",
    "NoNewPrivileges",
    "PrivateTmp",
    "ProtectSystem",
    "ProtectHome",
    "ReadOnlyPaths",
    "ReadWritePaths",
    "CollectMode",
    "Restart",
    "TimeoutStartUSec",
    "After",
)
_LINEAGE_PROPERTIES = (
    "Id",
    "InvocationID",
    "ControlGroup",
    "MainPID",
)
_FINAL_PROPERTIES = (
    "Id",
    "InvocationID",
    "LoadState",
    "ActiveState",
    "SubState",
    "Result",
    "ExecMainCode",
    "ExecMainStatus",
    "ExecStopPost",
)
_UNIT_INTERFACE = "org.freedesktop.systemd1.Unit"
_SERVICE_INTERFACE = "org.freedesktop.systemd1.Service"
_PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
_MANAGER_INTERFACE = "org.freedesktop.systemd1.Manager"
_UNIT_PROPERTY_NAMES = frozenset(
    {
        "Id",
        "InvocationID",
        "CollectMode",
        "OnSuccess",
        "OnFailure",
        "After",
        "LoadState",
        "ActiveState",
        "SubState",
    }
)
_SERVICE_PROPERTY_NAMES = frozenset(
    {
        "Delegate",
        "DelegateControllers",
        "DelegateSubgroup",
        "Restart",
        "KillMode",
        "TimeoutStartUSec",
        "TimeoutStopUSec",
        "ControlGroup",
        "MainPID",
        "Result",
        "ExecMainCode",
        "ExecMainStatus",
        "ExecStopPost",
        "Type",
        "User",
        "Group",
        "UMask",
        "ExecStart",
        "ExitType",
        "SendSIGKILL",
        "OOMPolicy",
        "NoNewPrivileges",
        "PrivateTmp",
        "PrivateMounts",
        "ProtectSystem",
        "ProtectHome",
        "ProtectControlGroups",
        "ProtectProc",
        "ProcSubset",
        "ReadOnlyPaths",
        "ReadWritePaths",
    }
)


class SystemdAcquisitionError(RuntimeError):
    """A live manager, proc, cgroup, or unit-template fact is invalid."""


class SystemdPropertyReader(Protocol):
    """The complete manager transport surface accepted by this module."""

    def read_properties(
        self,
        unit: str,
        names: tuple[str, ...],
    ) -> Mapping[str, object]:
        """Copy exactly the requested properties for one already-known unit."""


class SystemdDbusPropertyReader:
    """Read-only dbus-python adapter; it exposes no manager mutation method."""

    __slots__ = ("_dbus", "_manager", "_bus")

    def __init__(self) -> None:
        try:
            dbus = importlib.import_module("dbus")
            bus = dbus.SystemBus()
            manager_object = bus.get_object(
                "org.freedesktop.systemd1",
                "/org/freedesktop/systemd1",
            )
            manager = dbus.Interface(
                manager_object,
                dbus_interface=_MANAGER_INTERFACE,
            )
        except Exception as exc:
            raise SystemdAcquisitionError(
                "cannot acquire read-only systemd D-Bus transport"
            ) from exc
        self._dbus = dbus
        self._bus = bus
        self._manager = manager

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SystemdDbusPropertyReader is final")

    def _decode(self, value: object) -> object:
        dbus = self._dbus
        if isinstance(value, dbus.Boolean):
            return bool(value)
        integer_types = tuple(
            getattr(dbus, name)
            for name in (
                "Byte",
                "Int16",
                "UInt16",
                "Int32",
                "UInt32",
                "Int64",
                "UInt64",
            )
        )
        if isinstance(value, integer_types):
            return int(value)
        string_types = tuple(
            getattr(dbus, name) for name in ("String", "ObjectPath", "Signature")
        )
        if isinstance(value, string_types):
            return str(value)
        if isinstance(value, dbus.Struct):
            return tuple(self._decode(item) for item in value)
        if isinstance(value, dbus.Array):
            return [self._decode(item) for item in value]
        raise SystemdAcquisitionError(
            f"unsupported D-Bus property value {type(value).__name__}"
        )

    def read_properties(
        self,
        unit: str,
        names: tuple[str, ...],
    ) -> Mapping[str, object]:
        _unit(unit, field="D-Bus unit")
        if (
            type(names) is not tuple
            or not names
            or len(set(names)) != len(names)
            or any(
                name not in _UNIT_PROPERTY_NAMES | _SERVICE_PROPERTY_NAMES
                for name in names
            )
        ):
            raise SystemdAcquisitionError(
                "D-Bus property request is outside the fixed allowlist"
            )
        try:
            unit_path = self._manager.GetUnit(unit)
            unit_object = self._bus.get_object(
                "org.freedesktop.systemd1",
                unit_path,
            )
            properties = self._dbus.Interface(
                unit_object,
                dbus_interface=_PROPERTIES_INTERFACE,
            )
            copied = {}
            for name in names:
                interface = (
                    _UNIT_INTERFACE
                    if name in _UNIT_PROPERTY_NAMES
                    else _SERVICE_INTERFACE
                )
                copied[name] = self._decode(properties.Get(interface, name))
            return copied
        except SystemdAcquisitionError:
            raise
        except Exception as exc:
            raise SystemdAcquisitionError(
                f"read-only D-Bus property acquisition failed for {unit}"
            ) from exc


def _canonical_json(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SystemdAcquisitionError(
            "acquired fact is not canonical JSON data"
        ) from exc


def _json_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if type(value) is tuple:
        return [_json_value(item) for item in value]
    if type(value) is dict:
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _text(value: object, *, field: str, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value):
        raise SystemdAcquisitionError(f"{field} must be exact text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise SystemdAcquisitionError(f"{field} is not UTF-8") from exc
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise SystemdAcquisitionError(f"{field} contains a control character")
    return value


def _unit(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if not text.isascii() or _UNIT_RE.fullmatch(text) is None:
        raise SystemdAcquisitionError(f"{field} is not a canonical service unit")
    return text


def _invocation_id(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _INVOCATION_RE.fullmatch(text) is None:
        raise SystemdAcquisitionError(f"{field} is not a canonical invocation id")
    return text


def _uint(
    value: object,
    *,
    field: str,
    positive: bool = False,
    maximum: int = _UINT64_MAX,
) -> int:
    minimum = 1 if positive else 0
    if type(value) is not int or not minimum <= value <= maximum:
        raise SystemdAcquisitionError(
            f"{field} is not an integer in [{minimum}, {maximum}]"
        )
    return value


def _manager_mapping(
    reader: SystemdPropertyReader,
    unit: str,
    names: tuple[str, ...],
) -> dict[str, object]:
    _unit(unit, field="manager unit")
    try:
        copied = reader.read_properties(unit, names)
    except Exception as exc:
        raise SystemdAcquisitionError(
            f"manager property read failed for {unit}"
        ) from exc
    if not isinstance(copied, Mapping):
        raise SystemdAcquisitionError("manager reader did not return a mapping")
    if frozenset(copied) != frozenset(names) or any(
        type(key) is not str for key in copied
    ):
        raise SystemdAcquisitionError("manager property inventory differs")
    return {name: copied[name] for name in names}


def _manager_bool(value: object, *, field: str) -> str:
    if type(value) is not bool:
        raise SystemdAcquisitionError(f"{field} is not an exact boolean")
    return "yes" if value else "no"


def _manager_units(value: object, *, field: str) -> str:
    if type(value) not in {tuple, list}:
        raise SystemdAcquisitionError(f"{field} is not a unit array")
    units = tuple(_unit(item, field=field) for item in value)
    if len(set(units)) != len(units):
        raise SystemdAcquisitionError(f"{field} contains a duplicate")
    return " ".join(units)


def _manager_tokens(value: object, *, field: str) -> str:
    if type(value) not in {tuple, list}:
        raise SystemdAcquisitionError(f"{field} is not a token array")
    tokens = tuple(_text(item, field=field) for item in value)
    if any(not item.isascii() or " " in item for item in tokens):
        raise SystemdAcquisitionError(f"{field} contains a noncanonical token")
    if len(set(tokens)) != len(tokens):
        raise SystemdAcquisitionError(f"{field} contains a duplicate")
    return " ".join(tokens)


def _manager_timeout(value: object, *, field: str) -> str:
    number = _uint(value, field=field)
    return "infinity" if number == _UINT64_MAX else str(number)


def _manager_path_list(value: object, *, field: str) -> str:
    if type(value) not in {tuple, list}:
        raise SystemdAcquisitionError(f"{field} is not a manager string array")
    items = tuple(_text(item, field=field) for item in value)
    if any(any(character.isspace() for character in item) for item in items) or len(
        set(items)
    ) != len(items):
        raise SystemdAcquisitionError(f"{field} contains ambiguous or duplicate paths")
    return " ".join(items)


def _manager_command(value: object, *, field: str) -> str:
    if type(value) not in {tuple, list} or len(value) != 1:
        raise SystemdAcquisitionError(f"{field} is not one structured command")
    command = StructuredExecCommand.from_value(value[0])
    if (
        command.ignore_failure
        or not command.argv
        or command.argv[0] != command.path
        or any(any(character.isspace() for character in item) for item in command.argv)
    ):
        raise SystemdAcquisitionError(f"{field} structured command differs")
    return " ".join(command.argv)


def _manager_umask(value: object, *, field: str) -> str:
    number = _uint(value, field=field, maximum=0o7777)
    return f"{number:04o}"


def _configured_mapping(
    source: Mapping[str, str],
    expected: frozenset[str],
    *,
    label: str,
) -> dict[str, str]:
    if not isinstance(source, Mapping) or frozenset(source) != expected:
        raise SystemdAcquisitionError(f"{label} configured directive inventory differs")
    result: dict[str, str] = {}
    for key, value in source.items():
        if type(key) is not str or type(value) is not str:
            raise SystemdAcquisitionError(
                f"{label} configured directives are not exact text"
            )
        _text(value, field=f"{label}.{key}", allow_empty=True)
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class ConfiguredPairFact:
    run: ConfiguredUnitProperties
    closer: ConfiguredUnitProperties
    configured_pair_sha256: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("ConfiguredPairFact is final")

    @classmethod
    def create(
        cls,
        run: ConfiguredUnitProperties,
        closer: ConfiguredUnitProperties,
    ) -> "ConfiguredPairFact":
        if (
            type(run) is not ConfiguredUnitProperties
            or type(closer) is not ConfiguredUnitProperties
        ):
            raise TypeError("run and closer must be exact ConfiguredUnitProperties")
        try:
            validate_run_close_pair(run, closer)
        except Systemd255ContractError as exc:
            raise SystemdAcquisitionError("configured run/closer pair differs") from exc
        value = {
            "schema": "scion.systemd255-configured-pair.v1",
            "run": _json_value(asdict(run)),
            "closer": _json_value(asdict(closer)),
        }
        return cls(
            run=run,
            closer=closer,
            configured_pair_sha256=hashlib.sha256(_canonical_json(value)).hexdigest(),
        )

    @classmethod
    def from_mapping(cls, value: object) -> "ConfiguredPairFact":
        if type(value) is not dict or frozenset(value) != frozenset(
            {"schema", "run", "closer"}
        ):
            raise SystemdAcquisitionError("configured pair mapping fields differ")
        if value["schema"] != "scion.systemd255-configured-pair.v1":
            raise SystemdAcquisitionError("configured pair mapping schema differs")

        def decode(
            item: object,
            role: UnitRole,
        ) -> ConfiguredUnitProperties:
            if type(item) is not dict:
                raise SystemdAcquisitionError("configured unit is not a mapping")
            expected = frozenset(ConfiguredUnitProperties.__dataclass_fields__)
            if frozenset(item) != expected or item.get("role") != role.value:
                raise SystemdAcquisitionError("configured unit fields or role differ")
            copied = dict(item)
            copied["role"] = role
            for field in (
                "configured_directives",
                "delegate_controllers",
                "on_success",
                "on_failure",
                "after",
            ):
                raw = copied[field]
                if type(raw) is not list:
                    raise SystemdAcquisitionError(
                        f"configured unit {field} is not an array"
                    )
                copied[field] = tuple(
                    (
                        tuple(entry)
                        if field == "configured_directives" and type(entry) is list
                        else entry
                    )
                    for entry in raw
                )
            try:
                return ConfiguredUnitProperties(**copied)
            except (TypeError, Systemd255ContractError) as exc:
                raise SystemdAcquisitionError(
                    "configured unit mapping differs"
                ) from exc

        return cls.create(
            decode(value["run"], UnitRole.RUN),
            decode(value["closer"], UnitRole.CLOSER),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": "scion.systemd255-configured-pair.v1",
            "run": _json_value(asdict(self.run)),
            "closer": _json_value(asdict(self.closer)),
        }


@dataclass(frozen=True, slots=True)
class StructuredExecCommand:
    path: str
    argv: tuple[str, ...]
    ignore_failure: bool
    start_realtime_usec: int
    start_monotonic_usec: int
    exit_realtime_usec: int
    exit_monotonic_usec: int
    pid: int
    code: int
    status: int

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("StructuredExecCommand is final")

    @classmethod
    def from_value(cls, value: object) -> "StructuredExecCommand":
        if type(value) not in {tuple, list} or len(value) != 10:
            raise SystemdAcquisitionError(
                "ExecStopPost is not one a(sasbttttuii) struct"
            )
        path = _text(value[0], field="ExecStopPost.path")
        if not path.startswith("/") or PurePosixPath(path).as_posix() != path:
            raise SystemdAcquisitionError("ExecStopPost.path is not canonical absolute")
        raw_argv = value[1]
        if type(raw_argv) not in {tuple, list} or not raw_argv:
            raise SystemdAcquisitionError("ExecStopPost.argv is not a nonempty array")
        argv = tuple(_text(item, field="ExecStopPost.argv") for item in raw_argv)
        if type(value[2]) is not bool:
            raise SystemdAcquisitionError("ExecStopPost.ignore_failure is not boolean")
        integers = tuple(
            _uint(item, field=f"ExecStopPost[{index}]")
            for index, item in enumerate(value[3:], start=3)
        )
        return cls(
            path=path,
            argv=argv,
            ignore_failure=value[2],
            start_realtime_usec=integers[0],
            start_monotonic_usec=integers[1],
            exit_realtime_usec=integers[2],
            exit_monotonic_usec=integers[3],
            pid=integers[4],
            code=integers[5],
            status=integers[6],
        )


@dataclass(frozen=True, slots=True)
class UnitFinalAcquisition:
    command: StructuredExecCommand
    handoff: UnitHandoffProperties

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("UnitFinalAcquisition is final")


@dataclass(frozen=True, slots=True)
class UnitSection:
    name: str
    directives: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class UnitTemplate:
    raw_sha256: str
    sections: tuple[UnitSection, ...]

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("UnitTemplate is final")

    def section(self, name: str) -> Mapping[str, str]:
        matches = [
            dict(section.directives)
            for section in self.sections
            if section.name == name
        ]
        if len(matches) != 1:
            raise SystemdAcquisitionError(f"unit template lacks one [{name}] section")
        return matches[0]


def parse_unit_template(raw: bytes) -> UnitTemplate:
    """Parse one closed, duplicate-free unit template without expansion."""

    if type(raw) is not bytes:
        raise TypeError("unit template must be exact bytes")
    if not raw or b"\x00" in raw or b"\r" in raw:
        raise SystemdAcquisitionError("unit template bytes are not canonical")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise SystemdAcquisitionError("unit template is not UTF-8") from exc
    if not text.endswith("\n"):
        raise SystemdAcquisitionError("unit template lacks its final newline")
    sections: list[UnitSection] = []
    section_name: str | None = None
    directives: list[tuple[str, str]] = []
    seen_sections: set[str] = set()
    seen_directives: set[str] = set()

    def finish_section() -> None:
        nonlocal directives
        if section_name is not None:
            sections.append(UnitSection(section_name, tuple(directives)))
        directives = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1]
            if _SECTION_RE.fullmatch(name) is None or name in seen_sections:
                raise SystemdAcquisitionError(
                    f"duplicate or invalid unit section at line {line_number}"
                )
            finish_section()
            section_name = name
            seen_sections.add(name)
            seen_directives = set()
            continue
        if section_name is None or "=" not in line:
            raise SystemdAcquisitionError(
                f"unit directive is outside a section at line {line_number}"
            )
        key, value = line.split("=", 1)
        if (
            _DIRECTIVE_RE.fullmatch(key) is None
            or key in seen_directives
            or value != value.strip()
        ):
            raise SystemdAcquisitionError(
                f"duplicate or invalid unit directive at line {line_number}"
            )
        _text(value, field=f"unit directive {key}", allow_empty=True)
        seen_directives.add(key)
        directives.append((key, value))
    finish_section()
    if not sections:
        raise SystemdAcquisitionError("unit template has no sections")
    return UnitTemplate(
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        sections=tuple(sections),
    )


def _open_directory(path: Path) -> int:
    absolute = Path(os.path.abspath(path))
    if absolute == Path(absolute.anchor):
        raise SystemdAcquisitionError("filesystem root is not an acquisition root")
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(absolute.anchor, flags)
    except OSError as exc:
        raise SystemdAcquisitionError(
            f"cannot open acquisition anchor {absolute.anchor}"
        ) from exc
    try:
        for component in absolute.parts[1:]:
            next_descriptor = os.open(
                component,
                flags,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        result = descriptor
        descriptor = -1
        return result
    except OSError as exc:
        raise SystemdAcquisitionError(
            f"cannot pin acquisition directory {absolute}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _open_child_directory(parent_fd: int, name: str) -> int:
    if type(name) is not str or not name or name in {".", ".."} or "/" in name:
        raise SystemdAcquisitionError("invalid acquisition path component")
    try:
        return os.open(
            name,
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise SystemdAcquisitionError(f"cannot pin child directory {name}") from exc


def _read_regular(parent_fd: int, name: str) -> bytes:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise SystemdAcquisitionError(f"cannot open acquired file {name}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SystemdAcquisitionError(f"acquired file is not regular: {name}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise SystemdAcquisitionError(f"cannot read acquired file {name}") from exc
    finally:
        os.close(descriptor)
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        != (
            named.st_dev,
            named.st_ino,
            named.st_size,
            named.st_mtime_ns,
        )
        or sum(len(chunk) for chunk in chunks) != after.st_size
    ):
        raise SystemdAcquisitionError(f"acquired file changed while read: {name}")
    return b"".join(chunks)


def _proc_starttime(proc_fd: int, pid: int) -> int:
    pid_fd = _open_child_directory(proc_fd, str(pid))
    try:
        raw = _read_regular(pid_fd, "stat")
    finally:
        os.close(pid_fd)
    right_paren = raw.rfind(b")")
    fields = raw[right_paren + 2 :].split() if right_paren >= 0 else []
    if len(fields) <= 19 or not fields[19].isdigit():
        raise SystemdAcquisitionError("proc stat starttime is malformed")
    starttime = int(fields[19], 10)
    if starttime <= 0:
        raise SystemdAcquisitionError("proc stat starttime is not positive")
    return starttime


def _proc_cgroup(proc_fd: int, pid: int) -> str:
    pid_fd = _open_child_directory(proc_fd, str(pid))
    try:
        raw = _read_regular(pid_fd, "cgroup")
    finally:
        os.close(pid_fd)
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise SystemdAcquisitionError("proc cgroup is not canonical ASCII") from exc
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].startswith("0::"):
        raise SystemdAcquisitionError("proc cgroup is not one unified-v2 lineage")
    lineage = lines[0][3:]
    if not lineage.startswith("/") or lineage.endswith("/"):
        raise SystemdAcquisitionError("proc cgroup lineage is malformed")
    return lineage


def _control_components(control_group: object) -> tuple[str, ...]:
    text = _text(control_group, field="ControlGroup")
    path = PurePosixPath(text)
    if (
        not path.is_absolute()
        or path.as_posix() != text
        or text == "/"
        or any(part in {"", ".", ".."} for part in path.parts[1:])
    ):
        raise SystemdAcquisitionError("ControlGroup is not canonical absolute")
    return path.parts[1:]


def _open_beneath(parent_fd: int, components: tuple[str, ...]) -> int:
    descriptor = os.dup(parent_fd)
    try:
        for component in components:
            next_descriptor = _open_child_directory(
                descriptor,
                component,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        result = descriptor
        descriptor = -1
        return result
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _pids(directory_fd: int) -> tuple[int, ...]:
    raw = _read_regular(directory_fd, "cgroup.procs")
    if not raw:
        return ()
    try:
        lines = raw.decode("ascii", "strict").splitlines()
    except UnicodeError as exc:
        raise SystemdAcquisitionError("cgroup.procs is not canonical ASCII") from exc
    pids: list[int] = []
    for line in lines:
        if not line or not line.isdecimal() or (line.startswith("0") and line != "0"):
            raise SystemdAcquisitionError("cgroup.procs is malformed")
        pids.append(int(line, 10))
    result = tuple(pids)
    if (
        any(pid <= 0 for pid in result)
        or result != tuple(sorted(result))
        or len(set(result)) != len(result)
    ):
        raise SystemdAcquisitionError(
            "cgroup.procs is not positive, sorted, and unique"
        )
    return result


def _child_directories(directory_fd: int) -> tuple[str, ...]:
    names = os.listdir(directory_fd)
    children = []
    for name in names:
        metadata = os.stat(
            name,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if stat.S_ISDIR(metadata.st_mode):
            children.append(name)
    return tuple(sorted(children, key=lambda item: item.encode("utf-8")))


class Systemd255Acquirer:
    """Read-only owner for exact manager, proc, and cgroup facts."""

    __slots__ = (
        "_reader",
        "_proc_root",
        "_cgroup_root",
        "_boot_id_path",
    )

    def __init__(
        self,
        reader: SystemdPropertyReader,
        *,
        proc_root: Path = Path("/proc"),
        cgroup_root: Path = Path("/sys/fs/cgroup"),
        boot_id_path: Path = Path("/proc/sys/kernel/random/boot_id"),
    ) -> None:
        if not callable(getattr(reader, "read_properties", None)):
            raise TypeError("reader lacks read_properties")
        self._reader = reader
        self._proc_root = proc_root
        self._cgroup_root = cgroup_root
        self._boot_id_path = boot_id_path

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("Systemd255Acquirer is final")

    def acquire_configured_pair(
        self,
        *,
        run_unit: str,
        close_unit: str,
        run_directives: Mapping[str, str],
        close_directives: Mapping[str, str],
        run_wiring: Mapping[str, str],
        close_wiring: Mapping[str, str],
    ) -> ConfiguredPairFact:
        run_unit = _unit(run_unit, field="run_unit")
        close_unit = _unit(close_unit, field="close_unit")
        run_configured = _configured_mapping(
            run_directives,
            frozenset(
                {
                    "Delegate",
                    "DelegateSubgroup",
                    "CollectMode",
                    "Restart",
                    "KillMode",
                    "TimeoutStopSec",
                    "OnSuccess",
                    "OnFailure",
                }
            ),
            label="run",
        )
        close_configured = _configured_mapping(
            close_directives,
            frozenset({"CollectMode", "Restart", "TimeoutStartSec", "After"}),
            label="closer",
        )
        expected_run_wiring = _configured_mapping(
            run_wiring,
            frozenset(
                {
                    "Type",
                    "User",
                    "Group",
                    "UMask",
                    "ExecStart",
                    "ExecStopPost",
                    "ExitType",
                    "SendSIGKILL",
                    "OOMPolicy",
                    "NoNewPrivileges",
                    "PrivateTmp",
                    "PrivateMounts",
                    "ProtectSystem",
                    "ProtectHome",
                    "ProtectControlGroups",
                    "ProtectProc",
                    "ProcSubset",
                    "ReadOnlyPaths",
                    "ReadWritePaths",
                }
            ),
            label="run wiring",
        )
        expected_close_wiring = _configured_mapping(
            close_wiring,
            frozenset(
                {
                    "Type",
                    "User",
                    "Group",
                    "UMask",
                    "ExecStart",
                    "NoNewPrivileges",
                    "PrivateTmp",
                    "ProtectSystem",
                    "ProtectHome",
                    "ReadOnlyPaths",
                    "ReadWritePaths",
                }
            ),
            label="closer wiring",
        )
        run_raw = _manager_mapping(
            self._reader,
            run_unit,
            _RUN_EXPANDED,
        )
        close_raw = _manager_mapping(
            self._reader,
            close_unit,
            _CLOSE_EXPANDED,
        )
        run_expanded = {
            "Id": _unit(run_raw["Id"], field="run.Id"),
            "Delegate": _manager_bool(run_raw["Delegate"], field="run.Delegate"),
            "DelegateControllers": _manager_tokens(
                run_raw["DelegateControllers"],
                field="run.DelegateControllers",
            ),
            "DelegateSubgroup": _text(
                run_raw["DelegateSubgroup"],
                field="run.DelegateSubgroup",
            ),
            "CollectMode": _text(run_raw["CollectMode"], field="run.CollectMode"),
            "Restart": _text(run_raw["Restart"], field="run.Restart"),
            "KillMode": _text(run_raw["KillMode"], field="run.KillMode"),
            "TimeoutStopUSec": _manager_timeout(
                run_raw["TimeoutStopUSec"],
                field="run.TimeoutStopUSec",
            ),
            "OnSuccess": _manager_units(run_raw["OnSuccess"], field="run.OnSuccess"),
            "OnFailure": _manager_units(run_raw["OnFailure"], field="run.OnFailure"),
        }
        close_expanded = {
            "Id": _unit(close_raw["Id"], field="closer.Id"),
            "CollectMode": _text(close_raw["CollectMode"], field="closer.CollectMode"),
            "Restart": _text(close_raw["Restart"], field="closer.Restart"),
            "TimeoutStartUSec": _manager_timeout(
                close_raw["TimeoutStartUSec"],
                field="closer.TimeoutStartUSec",
            ),
            "After": _manager_units(close_raw["After"], field="closer.After"),
        }
        run_wiring_actual = {
            "Type": _text(run_raw["Type"], field="run.Type"),
            "User": _text(run_raw["User"], field="run.User"),
            "Group": _text(run_raw["Group"], field="run.Group"),
            "UMask": _manager_umask(run_raw["UMask"], field="run.UMask"),
            "ExecStart": _manager_command(run_raw["ExecStart"], field="run.ExecStart"),
            "ExecStopPost": _manager_command(
                run_raw["ExecStopPost"],
                field="run.ExecStopPost",
            ),
            "ExitType": _text(run_raw["ExitType"], field="run.ExitType"),
            "SendSIGKILL": _manager_bool(
                run_raw["SendSIGKILL"], field="run.SendSIGKILL"
            ),
            "OOMPolicy": _text(run_raw["OOMPolicy"], field="run.OOMPolicy"),
            "NoNewPrivileges": _manager_bool(
                run_raw["NoNewPrivileges"],
                field="run.NoNewPrivileges",
            ),
            "PrivateTmp": _manager_bool(run_raw["PrivateTmp"], field="run.PrivateTmp"),
            "PrivateMounts": _manager_bool(
                run_raw["PrivateMounts"],
                field="run.PrivateMounts",
            ),
            "ProtectSystem": _text(
                run_raw["ProtectSystem"],
                field="run.ProtectSystem",
            ),
            "ProtectHome": _text(run_raw["ProtectHome"], field="run.ProtectHome"),
            "ProtectControlGroups": _manager_bool(
                run_raw["ProtectControlGroups"],
                field="run.ProtectControlGroups",
            ),
            "ProtectProc": _text(run_raw["ProtectProc"], field="run.ProtectProc"),
            "ProcSubset": _text(run_raw["ProcSubset"], field="run.ProcSubset"),
            "ReadOnlyPaths": _manager_path_list(
                run_raw["ReadOnlyPaths"],
                field="run.ReadOnlyPaths",
            ),
            "ReadWritePaths": _manager_path_list(
                run_raw["ReadWritePaths"],
                field="run.ReadWritePaths",
            ),
        }
        close_wiring_actual = {
            "Type": _text(close_raw["Type"], field="closer.Type"),
            "User": _text(close_raw["User"], field="closer.User"),
            "Group": _text(close_raw["Group"], field="closer.Group"),
            "UMask": _manager_umask(close_raw["UMask"], field="closer.UMask"),
            "ExecStart": _manager_command(
                close_raw["ExecStart"],
                field="closer.ExecStart",
            ),
            "NoNewPrivileges": _manager_bool(
                close_raw["NoNewPrivileges"],
                field="closer.NoNewPrivileges",
            ),
            "PrivateTmp": _manager_bool(
                close_raw["PrivateTmp"],
                field="closer.PrivateTmp",
            ),
            "ProtectSystem": _text(
                close_raw["ProtectSystem"],
                field="closer.ProtectSystem",
            ),
            "ProtectHome": _text(
                close_raw["ProtectHome"],
                field="closer.ProtectHome",
            ),
            "ReadOnlyPaths": _manager_path_list(
                close_raw["ReadOnlyPaths"],
                field="closer.ReadOnlyPaths",
            ),
            "ReadWritePaths": _manager_path_list(
                close_raw["ReadWritePaths"],
                field="closer.ReadWritePaths",
            ),
        }
        if (
            run_wiring_actual != expected_run_wiring
            or close_wiring_actual != expected_close_wiring
        ):
            raise SystemdAcquisitionError(
                "loaded run/closer wiring differs from templates"
            )
        try:
            run = ConfiguredUnitProperties.from_receipts(
                UnitRole.RUN,
                run_configured,
                run_expanded,
                expected_unit=run_unit,
                expected_peer=close_unit,
            )
            closer = ConfiguredUnitProperties.from_receipts(
                UnitRole.CLOSER,
                close_configured,
                close_expanded,
                expected_unit=close_unit,
                expected_peer=run_unit,
            )
            validate_run_close_pair(run, closer)
        except Systemd255ContractError as exc:
            raise SystemdAcquisitionError("configured run/closer pair differs") from exc
        return ConfiguredPairFact.create(run, closer)

    def acquire_self_lineage(
        self,
        *,
        expected_unit: str,
        expected_invocation_id: str,
        expected_main_pid: int | None = None,
    ) -> InvocationLineage:
        expected_unit = _unit(expected_unit, field="expected_unit")
        expected_invocation_id = _invocation_id(
            expected_invocation_id,
            field="expected_invocation_id",
        )
        pid = (
            os.getpid()
            if expected_main_pid is None
            else _uint(
                expected_main_pid,
                field="expected_main_pid",
                positive=True,
            )
        )
        raw = _manager_mapping(
            self._reader,
            expected_unit,
            _LINEAGE_PROPERTIES,
        )
        manager_pid = _uint(raw["MainPID"], field="MainPID", positive=True)
        if (
            raw["Id"] != expected_unit
            or raw["InvocationID"] != expected_invocation_id
            or manager_pid != pid
        ):
            raise SystemdAcquisitionError("manager invocation identity differs")
        components = _control_components(raw["ControlGroup"])
        proc_fd = _open_directory(self._proc_root)
        cgroup_fd = _open_directory(self._cgroup_root)
        boot_parent_fd = _open_directory(self._boot_id_path.parent)
        service_fd = supervisor_fd = -1
        try:
            starttime = _proc_starttime(proc_fd, pid)
            process_cgroup = _proc_cgroup(proc_fd, pid)
            expected_process_cgroup = f"{raw['ControlGroup']}/supervisor"
            if process_cgroup != expected_process_cgroup:
                raise SystemdAcquisitionError(
                    "main process is not in delegated supervisor"
                )
            service_fd = _open_beneath(cgroup_fd, components)
            supervisor_fd = _open_child_directory(
                service_fd,
                "supervisor",
            )
            service_identity = os.fstat(service_fd)
            supervisor_identity = os.fstat(supervisor_fd)
            boot_raw = _read_regular(
                boot_parent_fd,
                self._boot_id_path.name,
            )
        finally:
            if supervisor_fd >= 0:
                os.close(supervisor_fd)
            if service_fd >= 0:
                os.close(service_fd)
            os.close(boot_parent_fd)
            os.close(cgroup_fd)
            os.close(proc_fd)
        try:
            boot_id = boot_raw.decode("ascii", "strict").strip()
        except UnicodeError as exc:
            raise SystemdAcquisitionError("boot id is not ASCII") from exc
        if _BOOT_RE.fullmatch(boot_id) is None:
            raise SystemdAcquisitionError("boot id is not canonical")
        try:
            return InvocationLineage.from_properties(
                {
                    "BootID": boot_id,
                    "Id": expected_unit,
                    "InvocationID": expected_invocation_id,
                    "ControlGroup": raw["ControlGroup"],
                    "ServiceDevice": str(service_identity.st_dev),
                    "ServiceInode": str(service_identity.st_ino),
                    "SupervisorDevice": str(supervisor_identity.st_dev),
                    "SupervisorInode": str(supervisor_identity.st_ino),
                    "MainPID": str(pid),
                    "MainStartTime": str(starttime),
                }
            )
        except Systemd255ContractError as exc:
            raise SystemdAcquisitionError(
                "acquired invocation lineage differs"
            ) from exc

    def acquire_stop_post_environment(
        self,
        environment: Mapping[str, str],
    ) -> StopPostEnvironment:
        try:
            return StopPostEnvironment.from_environment(environment)
        except Systemd255ContractError as exc:
            raise SystemdAcquisitionError("ExecStopPost environment differs") from exc

    def acquire_stop_post_topology(
        self,
        *,
        lineage: InvocationLineage,
        environment: StopPostEnvironment,
        sealer_pid: int | None = None,
    ) -> StopPostTopology:
        if type(lineage) is not InvocationLineage:
            raise TypeError("lineage must be exact InvocationLineage")
        if type(environment) is not StopPostEnvironment:
            raise TypeError("environment must be exact StopPostEnvironment")
        if environment.invocation_id != lineage.invocation_id:
            raise SystemdAcquisitionError(
                "stop-post environment belongs to another invocation"
            )
        pid = (
            os.getpid()
            if sealer_pid is None
            else _uint(sealer_pid, field="sealer_pid", positive=True)
        )
        components = _control_components(lineage.control_group)
        proc_fd = _open_directory(self._proc_root)
        cgroup_fd = _open_directory(self._cgroup_root)
        service_fd = supervisor_fd = control_fd = -1
        try:
            starttime = _proc_starttime(proc_fd, pid)
            if _proc_cgroup(proc_fd, pid) != (f"{lineage.control_group}/.control"):
                raise SystemdAcquisitionError(
                    "sealer is not in the service .control cgroup"
                )
            service_fd = _open_beneath(cgroup_fd, components)
            service_identity = os.fstat(service_fd)
            supervisor_fd = _open_child_directory(
                service_fd,
                "supervisor",
            )
            supervisor_identity = os.fstat(supervisor_fd)
            control_fd = _open_child_directory(service_fd, ".control")
            if (
                service_identity.st_dev != lineage.service_device
                or service_identity.st_ino != lineage.service_inode
                or supervisor_identity.st_dev != lineage.supervisor_device
                or supervisor_identity.st_ino != lineage.supervisor_inode
            ):
                raise SystemdAcquisitionError(
                    "stop-post cgroup identities differ from lineage"
                )
            if _child_directories(service_fd) != (
                ".control",
                "supervisor",
            ):
                raise SystemdAcquisitionError("service cgroup child topology differs")
            if (
                _child_directories(supervisor_fd)
                or _child_directories(control_fd)
                or _pids(service_fd)
                or _pids(supervisor_fd)
                or _pids(control_fd) != (pid,)
            ):
                raise SystemdAcquisitionError(
                    "stop-post cgroup process topology differs"
                )
        finally:
            if control_fd >= 0:
                os.close(control_fd)
            if supervisor_fd >= 0:
                os.close(supervisor_fd)
            if service_fd >= 0:
                os.close(service_fd)
            os.close(cgroup_fd)
            os.close(proc_fd)
        try:
            return StopPostTopology.from_mapping(
                {
                    "ServiceControlGroup": lineage.control_group,
                    "ControlGroup": f"{lineage.control_group}/.control",
                    "SealerPID": str(pid),
                    "SealerStartTime": str(starttime),
                    "ControlPIDs": str(pid),
                    "SupervisorPIDs": "",
                    "JobCgroups": "",
                    "JobPIDs": "",
                }
            )
        except Systemd255ContractError as exc:
            raise SystemdAcquisitionError(
                "acquired stop-post topology differs"
            ) from exc

    def acquire_unit_final(
        self,
        *,
        expected_unit: str,
        expected_invocation_id: str,
        expected_exec_path: str,
        expected_argv: tuple[str, ...],
    ) -> UnitFinalAcquisition:
        expected_unit = _unit(expected_unit, field="expected_unit")
        expected_invocation_id = _invocation_id(
            expected_invocation_id,
            field="expected_invocation_id",
        )
        expected_exec_path = _text(
            expected_exec_path,
            field="expected_exec_path",
        )
        if type(expected_argv) is not tuple or not expected_argv:
            raise TypeError("expected_argv must be a nonempty exact tuple")
        for item in expected_argv:
            _text(item, field="expected_argv")
        raw = _manager_mapping(
            self._reader,
            expected_unit,
            _FINAL_PROPERTIES,
        )
        commands = raw["ExecStopPost"]
        if type(commands) not in {tuple, list} or len(commands) != 1:
            raise SystemdAcquisitionError("ExecStopPost is not one structured command")
        command = StructuredExecCommand.from_value(commands[0])
        if (
            command.path != expected_exec_path
            or command.argv != expected_argv
            or command.ignore_failure
        ):
            raise SystemdAcquisitionError(
                "ExecStopPost command differs from installation"
            )
        try:
            handoff = UnitHandoffProperties.from_properties(
                {
                    "Id": _unit(raw["Id"], field="final.Id"),
                    "InvocationID": _invocation_id(
                        raw["InvocationID"],
                        field="final.InvocationID",
                    ),
                    "LoadState": _text(raw["LoadState"], field="final.LoadState"),
                    "ActiveState": _text(raw["ActiveState"], field="final.ActiveState"),
                    "SubState": _text(raw["SubState"], field="final.SubState"),
                    "Result": _text(raw["Result"], field="final.Result"),
                    "ExecMainCode": str(
                        _uint(
                            raw["ExecMainCode"],
                            field="final.ExecMainCode",
                            maximum=255,
                        )
                    ),
                    "ExecMainStatus": str(
                        _uint(
                            raw["ExecMainStatus"],
                            field="final.ExecMainStatus",
                            maximum=255,
                        )
                    ),
                    "ExecStopPostCode": str(command.code),
                    "ExecStopPostStatus": str(command.status),
                },
                expected_unit=expected_unit,
            )
        except Systemd255ContractError as exc:
            raise SystemdAcquisitionError("final unit properties differ") from exc
        if handoff.invocation_id != expected_invocation_id:
            raise SystemdAcquisitionError("final unit belongs to another invocation")
        return UnitFinalAcquisition(
            command=command,
            handoff=handoff,
        )


__all__ = [
    "ConfiguredPairFact",
    "StructuredExecCommand",
    "Systemd255Acquirer",
    "SystemdAcquisitionError",
    "SystemdDbusPropertyReader",
    "SystemdPropertyReader",
    "UnitFinalAcquisition",
    "UnitSection",
    "UnitTemplate",
    "parse_unit_template",
]
