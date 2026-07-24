"""Warehouse-owned semantic and relocation receipts for one W3 environment.

The generic :mod:`environment_integrity` receipt remains the byte-inventory
authority.  This module binds Warehouse semantic evidence to that exact
generic receipt through fixed local-interpreter readers and explicit synthetic
test-only seams.  It owns no root, mount, manager, or publication capability.
Its only subprocess connects to the local SystemBus and reads process-local
runtime facts.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from email.parser import Parser
from email.policy import strict as strict_email_policy
from pathlib import Path, PurePosixPath
from typing import Mapping, Protocol

from scion.problems.warehouse_delivery.w3_wheel import (
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    FIXED_REQUIRED_WHEEL_MEMBERS,
    OfflineDoubleWheelReceipt,
)
from scion.runtime.execution.environment_integrity import (
    EnvironmentContentReceipt,
    verify_environment_content,
)

FINAL_ENVIRONMENT_PARENT = PurePosixPath("/var/lib/scion/environments/w3")

_SEMANTIC_SCHEMA = "scion.w3-environment-semantic-content.v2"
_PROBE_SCHEMA = "scion.w3-environment-probe.v3"
_NAMESPACE_PROBE_SCHEMA = "scion.w3-namespace-probe-execution.v1"
_LIVE_REHASH_SCHEMA = "scion.w3-environment-live-rehash.v2"
_RELOCATION_SCHEMA = "scion.w3-environment-relocation.v3"
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SUBJECT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.:+-]{0,255}\Z")
_IMPORT_KINDS = frozenset(
    {
        "python",
        "native_extension",
        "shared_library",
        "stdlib",
        "executable",
    }
)
_IMPORT_SCOPES = frozenset({"environment", "external_runtime"})
_PROBE_PHASES = frozenset({"candidate", "namespace_final"})
_LIVE_PHASES = frozenset(
    {
        "imported_candidate",
        "relocation_pre",
        "relocation_post",
        "preclaim",
        "completion",
    }
)
_DBUS_PACKAGE_SUBJECT = "dbus"
_DBUS_BINDINGS_SUBJECT = "_dbus_bindings"
_DBUS_GLIB_BINDINGS_SUBJECT = "_dbus_glib_bindings"
_DBUS_DISTRIBUTION_NAME = "dbus-python"
_WHEEL_INSTALLATION_MANIFEST_SCHEMA = "scion.w3-wheel-installation-map.v1"
_WHEEL_INSTALLATION_MANIFEST_PATH = ".scion/w3-wheel-installation.json"
_RUNTIME_OBSERVATION_SCHEMA = "scion.w3-environment-runtime-observation.v2"
_ELF_MAGIC = b"\x7fELF"
_PROBE_TIMEOUT_SECONDS = 60
_BWRAP = "/usr/bin/bwrap"

# The target environment executes this fixed, repository-reviewed helper with
# ``bin/python -I -B -c``.  It performs no network operation: SystemBus uses the
# local system-bus socket and the only process-introspection input is procfs.
_FIXED_PROBE_HELPER = r"""
import importlib
import json
import os
import sys

for _name in (
    "scion.tools.scion_w3_tool",
    "scion.problems.warehouse_delivery.w2_preservation",
    "scion.problems.warehouse_delivery.w3_counter_fixtures",
    "scion.problems.warehouse_delivery.w3_installed_replay",
    "scion.problems.warehouse_delivery.w3_root_coordinator",
    "scion.problems.warehouse_delivery.w3_start_store",
    "scion.runtime.native._spawn_into_cgroup",
    "dbus",
    "_dbus_bindings",
    "_dbus_glib_bindings",
):
    importlib.import_module(_name)

import dbus

_bus = dbus.SystemBus()
_unique_name = _bus.get_unique_name()
if not isinstance(_unique_name, str) or not _unique_name.startswith(":"):
    raise RuntimeError("SystemBus did not return one unique connection name")

_modules = []
for _subject, _module in sorted(sys.modules.items()):
    _path = getattr(_module, "__file__", None)
    if not isinstance(_path, str) or not os.path.isabs(_path):
        continue
    _path = os.path.realpath(_path)
    if os.path.isfile(_path):
        _modules.append({"subject": _subject, "path": _path})

_mapped = set()
with open("/proc/self/maps", "r", encoding="utf-8", errors="strict") as _stream:
    for _line in _stream:
        _parts = _line.rstrip("\n").split(maxsplit=5)
        if len(_parts) != 6:
            continue
        _path = _parts[5]
        if not _path.startswith("/") or _path.endswith(" (deleted)"):
            continue
        _path = os.path.realpath(_path)
        _name = os.path.basename(_path)
        if (".so" in _name or _name.startswith("ld-linux")) and os.path.isfile(_path):
            _mapped.add(_path)

_value = {
    "schema": "scion.w3-environment-runtime-observation.v2",
    "sys_executable": os.path.realpath(sys.executable),
    "sys_prefix": os.path.realpath(sys.prefix),
    "sys_path": [os.path.realpath(_path) for _path in sys.path if _path],
    "module_files": _modules,
    "mapped_shared_libraries": sorted(_mapped),
    "dbus_acquired": True,
    "dbus_unique_name": _unique_name,
    "effective_uid": os.geteuid(),
    "effective_gid": os.getegid(),
    "no_new_privs": next(
        int(_line.split(":", 1)[1].strip())
        for _line in open(
            "/proc/self/status",
            "r",
            encoding="utf-8",
            errors="strict",
        )
        if _line.startswith("NoNewPrivs:")
    ),
    "network_namespace": os.readlink("/proc/self/ns/net"),
    "mount_namespace": os.readlink("/proc/self/ns/mnt"),
}
sys.stdout.buffer.write(
    (json.dumps(
        _value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n").encode("utf-8")
)
"""


class WarehouseW3EnvironmentReceiptError(RuntimeError):
    """Warehouse semantic or relocation evidence is not one closed fact."""


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
        raise WarehouseW3EnvironmentReceiptError(
            "receipt value is not canonical JSON data"
        ) from exc


def _decode_canonical(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError(f"{label} must be exact bytes")

    def mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"{label} contains a duplicate field")
            result[key] = item
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=mapping,
            parse_float=lambda _value: (_ for _ in ()).throw(
                ValueError(f"{label} contains a floating-point value")
            ),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"{label} contains {token}")
            ),
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        if "contains a duplicate field" in str(exc):
            raise WarehouseW3EnvironmentReceiptError(str(exc)) from exc
        raise WarehouseW3EnvironmentReceiptError(
            f"{label} is not canonical JSON"
        ) from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3EnvironmentReceiptError(f"{label} bytes are not canonical")
    return value


def _exact_fields(
    value: object,
    expected: frozenset[str],
    *,
    label: str,
) -> dict[str, object]:
    if (
        type(value) is not dict
        or frozenset(value) != expected
        or any(type(key) is not str for key in value)
    ):
        raise WarehouseW3EnvironmentReceiptError(f"{label} fields differ")
    return value


def _false_controls(value: Mapping[str, object], *, label: str) -> None:
    if any(value.get(field) is not False for field in ("retry", "resume", "reuse")):
        raise WarehouseW3EnvironmentReceiptError(
            f"{label} enables retry, resume, or reuse"
        )


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3EnvironmentReceiptError(f"{field} is not one SHA-256")
    return value


def _uint(value: object, *, field: str) -> int:
    if type(value) is not int or not 0 <= value <= (1 << 64) - 1:
        raise WarehouseW3EnvironmentReceiptError(
            f"{field} is not one unsigned 64-bit integer"
        )
    return value


def _text(value: object, *, field: str, maximum: int = 4096) -> str:
    if type(value) is not str or not value:
        raise WarehouseW3EnvironmentReceiptError(f"{field} is not exact text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise WarehouseW3EnvironmentReceiptError(f"{field} is not UTF-8") from exc
    if len(encoded) > maximum or any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise WarehouseW3EnvironmentReceiptError(f"{field} is not bounded text")
    return value


def _subject(value: object, *, field: str) -> str:
    text = _text(value, field=field, maximum=256)
    if _SUBJECT_RE.fullmatch(text) is None:
        raise WarehouseW3EnvironmentReceiptError(f"{field} is not canonical")
    return text


def _relative_path(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or path.as_posix() != text
        or text in {"", "."}
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise WarehouseW3EnvironmentReceiptError(
            f"{field} is not a canonical relative path"
        )
    return text


def _absolute_path(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    path = PurePosixPath(text)
    if (
        not path.is_absolute()
        or text in {"/", ""}
        or text.startswith("//")
        or path.as_posix() != text
        or any(part in {"", ".", ".."} for part in path.parts[1:])
    ):
        raise WarehouseW3EnvironmentReceiptError(
            f"{field} is not a canonical absolute path"
        )
    return text


def _string_tuple(
    value: object,
    *,
    field: str,
    absolute: bool = False,
    sorted_unique: bool = False,
) -> tuple[str, ...]:
    if type(value) is not list:
        raise WarehouseW3EnvironmentReceiptError(f"{field} is not an array")
    validator = _absolute_path if absolute else _text
    items = tuple(
        validator(item, field=f"{field} item") for item in value  # type: ignore[misc]
    )
    if not items:
        raise WarehouseW3EnvironmentReceiptError(f"{field} is empty")
    if len(set(items)) != len(items):
        raise WarehouseW3EnvironmentReceiptError(f"{field} contains a duplicate")
    if sorted_unique and items != tuple(sorted(items, key=lambda item: item.encode())):
        raise WarehouseW3EnvironmentReceiptError(f"{field} is not byte-sorted")
    return items


@dataclass(frozen=True, slots=True)
class _LoadedModuleFile:
    subject: str
    path: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "subject",
            _subject(self.subject, field="loaded module subject"),
        )
        object.__setattr__(
            self,
            "path",
            _absolute_path(self.path, field="loaded module path"),
        )


@dataclass(frozen=True, slots=True)
class _RuntimeObservation:
    sys_executable: str
    sys_prefix: str
    sys_path: tuple[str, ...]
    module_files: tuple[_LoadedModuleFile, ...]
    mapped_shared_libraries: tuple[str, ...]
    dbus_acquired: bool
    dbus_unique_name: str
    effective_uid: int
    effective_gid: int
    no_new_privs: int
    network_namespace: str
    mount_namespace: str
    raw: bytes
    raw_sha256: str

    @classmethod
    def from_bytes(cls, raw: bytes) -> "_RuntimeObservation":
        value = _exact_fields(
            _decode_canonical(raw, label="environment runtime observation"),
            frozenset(
                {
                    "schema",
                    "sys_executable",
                    "sys_prefix",
                    "sys_path",
                    "module_files",
                    "mapped_shared_libraries",
                    "dbus_acquired",
                    "dbus_unique_name",
                    "effective_uid",
                    "effective_gid",
                    "no_new_privs",
                    "network_namespace",
                    "mount_namespace",
                }
            ),
            label="environment runtime observation",
        )
        if value["schema"] != _RUNTIME_OBSERVATION_SCHEMA:
            raise WarehouseW3EnvironmentReceiptError(
                "environment runtime observation schema differs"
            )
        sys_path = _string_tuple(
            value["sys_path"],
            field="runtime sys.path",
            absolute=True,
        )
        mapped = _string_tuple(
            value["mapped_shared_libraries"],
            field="runtime mapped shared libraries",
            absolute=True,
            sorted_unique=True,
        )
        raw_modules = value["module_files"]
        if type(raw_modules) is not list or not raw_modules:
            raise WarehouseW3EnvironmentReceiptError(
                "runtime loaded module inventory is empty"
            )
        modules = tuple(
            _LoadedModuleFile(
                subject=_exact_fields(
                    item,
                    frozenset({"subject", "path"}),
                    label="runtime loaded module",
                )[
                    "subject"
                ],  # type: ignore[arg-type]
                path=_exact_fields(
                    item,
                    frozenset({"subject", "path"}),
                    label="runtime loaded module",
                )[
                    "path"
                ],  # type: ignore[arg-type]
            )
            for item in raw_modules
        )
        if modules != tuple(
            sorted(
                modules,
                key=lambda item: (
                    item.subject.encode("utf-8"),
                    item.path.encode("utf-8"),
                ),
            )
        ) or len({item.subject for item in modules}) != len(modules):
            raise WarehouseW3EnvironmentReceiptError(
                "runtime loaded modules are not unique and byte-sorted"
            )
        acquired = value["dbus_acquired"]
        unique_name = _text(
            value["dbus_unique_name"],
            field="runtime D-Bus unique name",
            maximum=256,
        )
        if acquired is not True or not unique_name.startswith(":"):
            raise WarehouseW3EnvironmentReceiptError(
                "runtime SystemBus acquisition did not succeed"
            )
        return cls(
            sys_executable=_absolute_path(
                value["sys_executable"],
                field="runtime sys.executable",
            ),
            sys_prefix=_absolute_path(
                value["sys_prefix"],
                field="runtime sys.prefix",
            ),
            sys_path=sys_path,
            module_files=modules,
            mapped_shared_libraries=mapped,
            dbus_acquired=True,
            dbus_unique_name=unique_name,
            effective_uid=_uint(
                value["effective_uid"],
                field="runtime effective_uid",
            ),
            effective_gid=_uint(
                value["effective_gid"],
                field="runtime effective_gid",
            ),
            no_new_privs=_uint(
                value["no_new_privs"],
                field="runtime no_new_privs",
            ),
            network_namespace=_text(
                value["network_namespace"],
                field="runtime network namespace",
                maximum=128,
            ),
            mount_namespace=_text(
                value["mount_namespace"],
                field="runtime mount namespace",
                maximum=128,
            ),
            raw=raw,
            raw_sha256=hashlib.sha256(raw).hexdigest(),
        )


def _utf8_document(value: object, *, field: str, maximum: int = 1 << 20) -> str:
    if type(value) is not str:
        raise WarehouseW3EnvironmentReceiptError(f"{field} is not exact text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise WarehouseW3EnvironmentReceiptError(f"{field} is not UTF-8") from exc
    if (
        not encoded
        or len(encoded) > maximum
        or b"\x00" in encoded
        or any(byte < 0x20 and byte not in {0x09, 0x0A, 0x0D} for byte in encoded)
    ):
        raise WarehouseW3EnvironmentReceiptError(f"{field} is not a bounded document")
    return value


def _validated_generic(
    receipt: EnvironmentContentReceipt,
) -> EnvironmentContentReceipt:
    if type(receipt) is not EnvironmentContentReceipt:
        raise TypeError("generic_receipt must be exact EnvironmentContentReceipt")
    try:
        parsed = EnvironmentContentReceipt.from_bytes(receipt.raw)
    except Exception as exc:
        raise WarehouseW3EnvironmentReceiptError(
            "generic environment receipt cannot be reopened"
        ) from exc
    if parsed != receipt:
        raise WarehouseW3EnvironmentReceiptError(
            "generic environment receipt object differs"
        )
    for entry in receipt.environment_inventory:
        parts = tuple(part.casefold() for part in PurePosixPath(entry.path).parts)
        if (
            (parts and parts[-1].endswith(".pth"))
            or (parts and parts[-1] in {"sitecustomize.py", "usercustomize.py"})
            or any(part.endswith(".data") for part in parts)
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "environment contains a Python-startup or installer-data payload"
            )
    return receipt


def _inventory_sha256(receipt: EnvironmentContentReceipt) -> str:
    return hashlib.sha256(
        b"scion.w3-environment-inventory.v1\0"
        + _canonical_json(
            {
                "environment_inventory": [
                    entry.to_mapping() for entry in receipt.environment_inventory
                ]
            }
        )
    ).hexdigest()


def _external_runtime_sha256(receipt: EnvironmentContentReceipt) -> str:
    return hashlib.sha256(
        b"scion.w3-external-runtime-closure.v1\0"
        + _canonical_json(
            {
                "external_runtime": [
                    entry.to_mapping() for entry in receipt.external_runtime
                ]
            }
        )
    ).hexdigest()


def _validated_wheel(
    receipt: OfflineDoubleWheelReceipt,
) -> OfflineDoubleWheelReceipt:
    if type(receipt) is not OfflineDoubleWheelReceipt:
        raise TypeError("wheel_receipt must be exact OfflineDoubleWheelReceipt")
    try:
        parsed = OfflineDoubleWheelReceipt.from_bytes(receipt.raw)
    except Exception as exc:
        raise WarehouseW3EnvironmentReceiptError(
            "offline double-wheel receipt cannot be reopened"
        ) from exc
    if parsed != receipt:
        raise WarehouseW3EnvironmentReceiptError(
            "offline double-wheel receipt object differs"
        )
    return receipt


def _native_wheel_member_size(receipt: OfflineDoubleWheelReceipt) -> int:
    matches = tuple(
        member
        for member in receipt.member_inventory
        if member.path == receipt.native_member_path
    )
    if len(matches) != 1:
        raise WarehouseW3EnvironmentReceiptError(
            "offline double-wheel native member identity differs"
        )
    return matches[0].size_bytes


@dataclass(frozen=True, slots=True)
class InstalledWheelMember:
    wheel_member_path: str
    environment_path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "wheel_member_path",
            _relative_path(self.wheel_member_path, field="wheel member path"),
        )
        object.__setattr__(
            self,
            "environment_path",
            _relative_path(self.environment_path, field="installed wheel member path"),
        )
        object.__setattr__(
            self,
            "sha256",
            _sha256(self.sha256, field="installed wheel member sha256"),
        )
        object.__setattr__(
            self,
            "size_bytes",
            _uint(self.size_bytes, field="installed wheel member size_bytes"),
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("InstalledWheelMember is final")

    @classmethod
    def from_mapping(cls, value: object) -> "InstalledWheelMember":
        fields = _exact_fields(
            value,
            frozenset(
                {"wheel_member_path", "environment_path", "sha256", "size_bytes"}
            ),
            label="installed wheel member",
        )
        return cls(
            wheel_member_path=fields["wheel_member_path"],  # type: ignore[arg-type]
            environment_path=fields["environment_path"],  # type: ignore[arg-type]
            sha256=fields["sha256"],  # type: ignore[arg-type]
            size_bytes=fields["size_bytes"],  # type: ignore[arg-type]
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "wheel_member_path": self.wheel_member_path,
            "environment_path": self.environment_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class WheelInstallationProvenance:
    manifest_path: str
    wheel_receipt_sha256: str
    wheel_sha256: str
    installed_members: tuple[InstalledWheelMember, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "manifest_path",
            _relative_path(
                self.manifest_path, field="wheel installation manifest path"
            ),
        )
        object.__setattr__(
            self,
            "wheel_receipt_sha256",
            _sha256(
                self.wheel_receipt_sha256,
                field="wheel installation receipt sha256",
            ),
        )
        object.__setattr__(
            self,
            "wheel_sha256",
            _sha256(self.wheel_sha256, field="installed wheel sha256"),
        )
        if (
            type(self.installed_members) is not tuple
            or not self.installed_members
            or any(
                type(item) is not InstalledWheelMember
                for item in self.installed_members
            )
        ):
            raise TypeError("installed_members must be one nonempty exact tuple")
        ordered = tuple(
            sorted(
                self.installed_members,
                key=lambda item: item.wheel_member_path.encode("utf-8"),
            )
        )
        if (
            ordered != self.installed_members
            or len({item.wheel_member_path for item in ordered}) != len(ordered)
            or len({item.environment_path for item in ordered}) != len(ordered)
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "installed wheel member map is not complete, unique, and byte-sorted"
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WheelInstallationProvenance is final")

    @classmethod
    def from_mapping(cls, value: object) -> "WheelInstallationProvenance":
        fields = _exact_fields(
            value,
            frozenset(
                {
                    "schema",
                    "manifest_path",
                    "wheel_receipt_sha256",
                    "wheel_sha256",
                    "installed_members",
                }
            ),
            label="wheel installation provenance",
        )
        if fields["schema"] != _WHEEL_INSTALLATION_MANIFEST_SCHEMA:
            raise WarehouseW3EnvironmentReceiptError(
                "wheel installation manifest schema differs"
            )
        raw_members = fields["installed_members"]
        if type(raw_members) is not list or not raw_members:
            raise WarehouseW3EnvironmentReceiptError(
                "installed wheel member map is empty"
            )
        return cls(
            manifest_path=fields["manifest_path"],  # type: ignore[arg-type]
            wheel_receipt_sha256=fields["wheel_receipt_sha256"],  # type: ignore[arg-type]
            wheel_sha256=fields["wheel_sha256"],  # type: ignore[arg-type]
            installed_members=tuple(
                InstalledWheelMember.from_mapping(item) for item in raw_members
            ),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": _WHEEL_INSTALLATION_MANIFEST_SCHEMA,
            "manifest_path": self.manifest_path,
            "wheel_receipt_sha256": self.wheel_receipt_sha256,
            "wheel_sha256": self.wheel_sha256,
            "installed_members": [item.to_mapping() for item in self.installed_members],
        }

    def manifest_bytes(self) -> bytes:
        value = self.to_mapping()
        del value["manifest_path"]
        return _canonical_json(value)


@dataclass(frozen=True, slots=True)
class NativeElfIdentity:
    environment_path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "environment_path",
            _relative_path(
                self.environment_path,
                field="native ELF environment path",
            ),
        )
        object.__setattr__(
            self,
            "sha256",
            _sha256(self.sha256, field="native ELF sha256"),
        )
        object.__setattr__(
            self,
            "size_bytes",
            _uint(self.size_bytes, field="native ELF size_bytes"),
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("NativeElfIdentity is final")

    @classmethod
    def from_mapping(cls, value: object) -> "NativeElfIdentity":
        fields = _exact_fields(
            value,
            frozenset({"environment_path", "sha256", "size_bytes"}),
            label="native ELF identity",
        )
        return cls(
            environment_path=fields["environment_path"],  # type: ignore[arg-type]
            sha256=fields["sha256"],  # type: ignore[arg-type]
            size_bytes=fields["size_bytes"],  # type: ignore[arg-type]
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "environment_path": self.environment_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class ImportIdentity:
    """One loaded Python/native/shared-runtime file in the complete table."""

    subject: str
    kind: str
    scope: str
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "subject",
            _subject(self.subject, field="import subject"),
        )
        if self.kind not in _IMPORT_KINDS:
            raise WarehouseW3EnvironmentReceiptError("import kind differs")
        if self.scope not in _IMPORT_SCOPES:
            raise WarehouseW3EnvironmentReceiptError("import scope differs")
        path = (
            _relative_path(self.path, field="environment import path")
            if self.scope == "environment"
            else _absolute_path(self.path, field="external runtime import path")
        )
        object.__setattr__(self, "path", path)
        object.__setattr__(
            self,
            "sha256",
            _sha256(self.sha256, field="import sha256"),
        )
        object.__setattr__(
            self,
            "size_bytes",
            _uint(self.size_bytes, field="import size_bytes"),
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("ImportIdentity is final")

    @classmethod
    def from_mapping(cls, value: object) -> "ImportIdentity":
        fields = _exact_fields(
            value,
            frozenset({"subject", "kind", "scope", "path", "sha256", "size_bytes"}),
            label="import identity",
        )
        return cls(
            subject=fields["subject"],  # type: ignore[arg-type]
            kind=fields["kind"],  # type: ignore[arg-type]
            scope=fields["scope"],  # type: ignore[arg-type]
            path=fields["path"],  # type: ignore[arg-type]
            sha256=fields["sha256"],  # type: ignore[arg-type]
            size_bytes=fields["size_bytes"],  # type: ignore[arg-type]
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "subject": self.subject,
            "kind": self.kind,
            "scope": self.scope,
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class DbusProvenance:
    package_version: str
    package_metadata_path: str
    package_metadata_contents: str
    package_subject: str
    bindings_subject: str
    glib_bindings_subject: str
    shared_library_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "package_version",
            _text(self.package_version, field="D-Bus package version", maximum=128),
        )
        object.__setattr__(
            self,
            "package_metadata_path",
            _relative_path(
                self.package_metadata_path,
                field="D-Bus package metadata path",
            ),
        )
        expected_metadata_suffix = (
            f"/site-packages/dbus_python-{self.package_version}.dist-info/METADATA"
        )
        if not self.package_metadata_path.endswith(expected_metadata_suffix):
            raise WarehouseW3EnvironmentReceiptError(
                "D-Bus package metadata path differs"
            )
        metadata_contents = _utf8_document(
            self.package_metadata_contents,
            field="D-Bus package metadata contents",
        )
        object.__setattr__(
            self,
            "package_metadata_contents",
            metadata_contents,
        )
        try:
            metadata = Parser(policy=strict_email_policy).parsestr(
                metadata_contents,
                headersonly=True,
            )
        except Exception as exc:
            raise WarehouseW3EnvironmentReceiptError(
                "D-Bus package metadata cannot be parsed"
            ) from exc
        if metadata.get_all("Name", failobj=[]) != [
            _DBUS_DISTRIBUTION_NAME
        ] or metadata.get_all("Version", failobj=[]) != [self.package_version]:
            raise WarehouseW3EnvironmentReceiptError(
                "D-Bus package metadata name or version differs"
            )
        object.__setattr__(
            self,
            "package_subject",
            _subject(self.package_subject, field="D-Bus package subject"),
        )
        object.__setattr__(
            self,
            "bindings_subject",
            _subject(self.bindings_subject, field="D-Bus bindings subject"),
        )
        object.__setattr__(
            self,
            "glib_bindings_subject",
            _subject(
                self.glib_bindings_subject,
                field="D-Bus GLib bindings subject",
            ),
        )
        if (
            type(self.shared_library_paths) is not tuple
            or not self.shared_library_paths
        ):
            raise TypeError("D-Bus shared_library_paths must be one nonempty tuple")
        paths = tuple(
            _absolute_path(path, field="D-Bus shared library path")
            for path in self.shared_library_paths
        )
        if paths != tuple(sorted(set(paths), key=lambda item: item.encode())):
            raise WarehouseW3EnvironmentReceiptError(
                "D-Bus shared library paths are not unique and byte-sorted"
            )
        object.__setattr__(self, "shared_library_paths", paths)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("DbusProvenance is final")

    @classmethod
    def from_mapping(cls, value: object) -> "DbusProvenance":
        fields = _exact_fields(
            value,
            frozenset(
                {
                    "package_version",
                    "package_metadata_path",
                    "package_metadata_contents",
                    "package_subject",
                    "bindings_subject",
                    "glib_bindings_subject",
                    "shared_library_paths",
                }
            ),
            label="D-Bus provenance",
        )
        paths = _string_tuple(
            fields["shared_library_paths"],
            field="D-Bus shared_library_paths",
            absolute=True,
            sorted_unique=True,
        )
        return cls(
            package_version=fields["package_version"],  # type: ignore[arg-type]
            package_metadata_path=fields["package_metadata_path"],  # type: ignore[arg-type]
            package_metadata_contents=fields["package_metadata_contents"],  # type: ignore[arg-type]
            package_subject=fields["package_subject"],  # type: ignore[arg-type]
            bindings_subject=fields["bindings_subject"],  # type: ignore[arg-type]
            glib_bindings_subject=fields["glib_bindings_subject"],  # type: ignore[arg-type]
            shared_library_paths=paths,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "package_version": self.package_version,
            "package_metadata_path": self.package_metadata_path,
            "package_metadata_contents": self.package_metadata_contents,
            "package_subject": self.package_subject,
            "bindings_subject": self.bindings_subject,
            "glib_bindings_subject": self.glib_bindings_subject,
            "shared_library_paths": list(self.shared_library_paths),
        }


@dataclass(frozen=True, slots=True)
class WarehouseEnvironmentEvidence:
    native_elf: NativeElfIdentity
    wheel_installation: WheelInstallationProvenance
    import_table: tuple[ImportIdentity, ...]
    dbus_provenance: DbusProvenance

    def __post_init__(self) -> None:
        if type(self.native_elf) is not NativeElfIdentity:
            raise TypeError("native_elf must be exact NativeElfIdentity")
        if type(self.wheel_installation) is not WheelInstallationProvenance:
            raise TypeError(
                "wheel_installation must be exact WheelInstallationProvenance"
            )
        if (
            type(self.import_table) is not tuple
            or not self.import_table
            or any(type(item) is not ImportIdentity for item in self.import_table)
        ):
            raise TypeError("import_table must be one nonempty exact tuple")
        ordered = tuple(
            sorted(
                self.import_table,
                key=lambda item: (
                    item.subject.encode("utf-8"),
                    item.path.encode("utf-8"),
                ),
            )
        )
        if (
            ordered != self.import_table
            or len({item.subject for item in ordered}) != len(ordered)
            or len({(item.scope, item.path) for item in ordered}) != len(ordered)
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "import table is not complete, unique, and byte-sorted"
            )
        if type(self.dbus_provenance) is not DbusProvenance:
            raise TypeError("dbus_provenance must be exact DbusProvenance")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseEnvironmentEvidence is final")

    @classmethod
    def from_mapping(cls, value: object) -> "WarehouseEnvironmentEvidence":
        fields = _exact_fields(
            value,
            frozenset(
                {
                    "native_elf",
                    "wheel_installation",
                    "import_table",
                    "dbus_provenance",
                }
            ),
            label="Warehouse environment evidence",
        )
        raw_imports = fields["import_table"]
        if type(raw_imports) is not list or not raw_imports:
            raise WarehouseW3EnvironmentReceiptError("import table is empty")
        return cls(
            native_elf=NativeElfIdentity.from_mapping(fields["native_elf"]),
            wheel_installation=WheelInstallationProvenance.from_mapping(
                fields["wheel_installation"]
            ),
            import_table=tuple(
                ImportIdentity.from_mapping(item) for item in raw_imports
            ),
            dbus_provenance=DbusProvenance.from_mapping(fields["dbus_provenance"]),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "native_elf": self.native_elf.to_mapping(),
            "wheel_installation": self.wheel_installation.to_mapping(),
            "import_table": [item.to_mapping() for item in self.import_table],
            "dbus_provenance": self.dbus_provenance.to_mapping(),
        }


def _import_table_sha256(imports: tuple[ImportIdentity, ...]) -> str:
    return hashlib.sha256(
        b"scion.w3-environment-import-table.v1\0"
        + _canonical_json({"import_table": [item.to_mapping() for item in imports]})
    ).hexdigest()


def _validate_wheel_installation(
    generic: EnvironmentContentReceipt,
    wheel: OfflineDoubleWheelReceipt,
    evidence: WarehouseEnvironmentEvidence,
) -> None:
    provenance = evidence.wheel_installation
    if (
        provenance.wheel_receipt_sha256 != wheel.raw_sha256
        or provenance.wheel_sha256 != wheel.wheel_sha256
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "installed wheel manifest names another double-wheel receipt"
        )
    native_environment = PurePosixPath(evidence.native_elf.environment_path)
    native_member = PurePosixPath(wheel.native_member_path)
    if (
        len(native_environment.parts) <= len(native_member.parts)
        or native_environment.parts[-len(native_member.parts) :] != native_member.parts
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "installed wheel prefix cannot be derived from native member"
        )
    installation_prefix = PurePosixPath(
        *native_environment.parts[: -len(native_member.parts)]
    )
    environment = {
        item.path: item
        for item in generic.environment_inventory
        if item.kind == "regular"
    }
    expected_members = []
    for member in wheel.member_inventory:
        environment_path = (installation_prefix / member.path).as_posix()
        installed = environment.get(environment_path)
        if (
            installed is None
            or installed.sha256 != member.sha256
            or installed.size_bytes != member.size_bytes
        ):
            raise WarehouseW3EnvironmentReceiptError(
                f"wheel member is not installed byte-for-byte: {member.path}"
            )
        expected_members.append(
            InstalledWheelMember(
                wheel_member_path=member.path,
                environment_path=environment_path,
                sha256=member.sha256,
                size_bytes=member.size_bytes,
            )
        )
    if provenance.installed_members != tuple(expected_members):
        raise WarehouseW3EnvironmentReceiptError(
            "installed wheel map does not close the exact member inventory"
        )
    manifest = environment.get(provenance.manifest_path)
    manifest_raw = provenance.manifest_bytes()
    if (
        manifest is None
        or manifest.sha256 != hashlib.sha256(manifest_raw).hexdigest()
        or manifest.size_bytes != len(manifest_raw)
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "wheel installation manifest is not bound by environment content"
        )


def _validate_semantic_evidence(
    generic: EnvironmentContentReceipt,
    wheel: OfflineDoubleWheelReceipt,
    evidence: WarehouseEnvironmentEvidence,
) -> None:
    _validate_wheel_installation(generic, wheel, evidence)
    environment = {
        item.path: item
        for item in generic.environment_inventory
        if item.kind == "regular"
    }
    external = {item.path: item for item in generic.external_runtime}
    for item in evidence.import_table:
        bound = (
            environment.get(item.path)
            if item.scope == "environment"
            else external.get(item.path)
        )
        if (
            bound is None
            or bound.sha256 != item.sha256
            or bound.size_bytes != item.size_bytes
        ):
            raise WarehouseW3EnvironmentReceiptError(
                f"import identity is not bound by generic content: {item.subject}"
            )
    external_import_paths = {
        item.path for item in evidence.import_table if item.scope == "external_runtime"
    }
    if external_import_paths != set(external):
        raise WarehouseW3EnvironmentReceiptError(
            "import table does not close the external runtime inventory"
        )
    imports_by_path = {
        item.path: item for item in evidence.import_table if item.scope == "environment"
    }
    installed_by_member = {
        item.wheel_member_path: item
        for item in evidence.wheel_installation.installed_members
    }
    required_runtime_modules = tuple(
        member for member in FIXED_REQUIRED_WHEEL_MEMBERS if member.endswith(".py")
    )
    for member_path in required_runtime_modules:
        installed = installed_by_member.get(member_path)
        if installed is None:
            raise WarehouseW3EnvironmentReceiptError(
                f"required wheel module has no installed mapping: {member_path}"
            )
        module_path = (
            PurePosixPath(member_path).parent
            if member_path.endswith("/__init__.py")
            else PurePosixPath(member_path[:-3])
        )
        expected_subject = ".".join(module_path.parts)
        imported = imports_by_path.get(installed.environment_path)
        if (
            imported is None
            or imported.subject != expected_subject
            or imported.kind != "python"
        ):
            raise WarehouseW3EnvironmentReceiptError(
                f"target interpreter omitted one required wheel module: {member_path}"
            )
    interpreter = imports_by_path.get("bin/python")
    if (
        interpreter is None
        or interpreter.subject != "sys.executable"
        or interpreter.kind != "executable"
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "target interpreter executable is absent from the import table"
        )
    native = evidence.native_elf
    native_entry = environment.get(native.environment_path)
    native_imports = [
        item
        for item in evidence.import_table
        if item.path == native.environment_path
        and item.scope == "environment"
        and item.kind == "native_extension"
    ]
    if (
        native_entry is None
        or native_entry.sha256 != native.sha256
        or native_entry.size_bytes != native.size_bytes
        or len(native_imports) != 1
        or wheel.native_elf_sha256 != native.sha256
        or _native_wheel_member_size(wheel) != native.size_bytes
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "native ELF identity is not cross-bound to wheel and environment"
        )
    by_subject = {item.subject: item for item in evidence.import_table}
    dbus = evidence.dbus_provenance
    metadata_entry = environment.get(dbus.package_metadata_path)
    metadata_raw = dbus.package_metadata_contents.encode("utf-8", "strict")
    package = by_subject.get(dbus.package_subject)
    bindings = by_subject.get(dbus.bindings_subject)
    glib = by_subject.get(dbus.glib_bindings_subject)
    if (
        dbus.package_subject != _DBUS_PACKAGE_SUBJECT
        or dbus.bindings_subject != _DBUS_BINDINGS_SUBJECT
        or dbus.glib_bindings_subject != _DBUS_GLIB_BINDINGS_SUBJECT
        or metadata_entry is None
        or metadata_entry.sha256 != hashlib.sha256(metadata_raw).hexdigest()
        or metadata_entry.size_bytes != len(metadata_raw)
        or package is None
        or package.kind != "python"
        or package.scope != "environment"
        or not package.path.endswith("/site-packages/dbus/__init__.py")
        or bindings is None
        or bindings.kind != "native_extension"
        or bindings.scope != "environment"
        or not PurePosixPath(bindings.path).name.startswith("_dbus_bindings.")
        or glib is None
        or glib.kind != "native_extension"
        or glib.scope != "environment"
        or not PurePosixPath(glib.path).name.startswith("_dbus_glib_bindings.")
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "D-Bus package and native bindings are not in the import table"
        )
    shared = {
        item.path
        for item in evidence.import_table
        if item.kind == "shared_library" and item.scope == "external_runtime"
    }
    if (
        any(
            item.kind == "shared_library" and item.scope != "external_runtime"
            for item in evidence.import_table
        )
        or set(dbus.shared_library_paths) != shared
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "D-Bus shared-library provenance does not close the import table"
        )


def _relative_to_environment(path: str, root: Path) -> str | None:
    try:
        return PurePosixPath(path).relative_to(PurePosixPath(str(root))).as_posix()
    except ValueError:
        return None


def _read_bound_regular(
    path: Path,
    *,
    expected_sha256: str,
    expected_size_bytes: int,
    maximum: int | None = None,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WarehouseW3EnvironmentReceiptError(
            f"cannot open one receipt-bound runtime file: {path}"
        ) from exc
    chunks: list[bytes] = []
    total = 0
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise WarehouseW3EnvironmentReceiptError(
                f"receipt-bound runtime path is not regular: {path}"
            )
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if maximum is not None and total > maximum:
                raise WarehouseW3EnvironmentReceiptError(
                    f"receipt-bound runtime file exceeds its bound: {path}"
                )
            chunks.append(chunk)
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        named = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise WarehouseW3EnvironmentReceiptError(
            f"cannot reopen one receipt-bound runtime file: {path}"
        ) from exc
    identity = lambda item: (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )
    if (
        identity(before) != identity(after)
        or identity(after) != identity(named)
        or total != expected_size_bytes
        or digest.hexdigest() != expected_sha256
    ):
        raise WarehouseW3EnvironmentReceiptError(
            f"receipt-bound runtime file changed or differs: {path}"
        )
    return b"".join(chunks)


def _runtime_import_table(
    observation: _RuntimeObservation,
    *,
    environment_root: Path,
    generic_receipt: EnvironmentContentReceipt,
) -> tuple[ImportIdentity, ...]:
    expected_root = _absolute_path(
        str(environment_root),
        field="runtime observation environment root",
    )
    if (
        observation.sys_executable != f"{expected_root}/bin/python"
        or observation.sys_prefix != expected_root
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "runtime observation interpreter or prefix differs"
        )
    environment = {
        item.path: item
        for item in generic_receipt.environment_inventory
        if item.kind == "regular"
    }
    external = {item.path: item for item in generic_receipt.external_runtime}
    subjects_by_path: dict[str, set[str]] = {}
    for item in observation.module_files:
        subjects_by_path.setdefault(item.path, set()).add(item.subject)
    subjects_by_path.setdefault(observation.sys_executable, set()).add("sys.executable")
    mapped = set(observation.mapped_shared_libraries)
    all_paths = set(subjects_by_path) | mapped
    if not all_paths:
        raise WarehouseW3EnvironmentReceiptError(
            "runtime observation contains no loaded files"
        )
    imports: list[ImportIdentity] = []
    used_subjects: set[str] = set()
    for path in sorted(all_paths, key=lambda item: item.encode("utf-8")):
        relative = _relative_to_environment(path, environment_root)
        scope = "environment" if relative is not None else "external_runtime"
        receipt_path = relative if relative is not None else path
        bound = (
            environment.get(receipt_path)
            if scope == "environment"
            else external.get(receipt_path)
        )
        if bound is None:
            raise WarehouseW3EnvironmentReceiptError(
                f"runtime loaded file is absent from generic content: {path}"
            )
        subjects = subjects_by_path.get(path, set())
        preferred = tuple(
            subject
            for subject in (
                _DBUS_PACKAGE_SUBJECT,
                _DBUS_BINDINGS_SUBJECT,
                _DBUS_GLIB_BINDINGS_SUBJECT,
                "scion.runtime.native._spawn_into_cgroup",
                "scion.tools.scion_w3_tool",
                "sys.executable",
            )
            if subject in subjects
        )
        if preferred:
            subject = preferred[0]
        elif subjects:
            subject = sorted(subjects, key=lambda item: item.encode("utf-8"))[0]
        else:
            subject = f"mapped:{hashlib.sha256(path.encode('utf-8')).hexdigest()[:24]}"
        if subject in used_subjects:
            subject = (
                f"{subject}:{hashlib.sha256(path.encode('utf-8')).hexdigest()[:16]}"
            )
        used_subjects.add(subject)
        name = PurePosixPath(path).name
        if path == observation.sys_executable:
            kind = "executable"
        elif subjects and (name.endswith(".so") or ".so." in name):
            kind = "native_extension"
        elif not subjects:
            kind = "shared_library"
        elif scope == "external_runtime":
            kind = "stdlib"
        else:
            kind = "python"
        imports.append(
            ImportIdentity(
                subject=subject,
                kind=kind,
                scope=scope,
                path=receipt_path,
                sha256=bound.sha256 or "",  # type: ignore[union-attr]
                size_bytes=bound.size_bytes,
            )
        )
    ordered = tuple(
        sorted(
            imports,
            key=lambda item: (
                item.subject.encode("utf-8"),
                item.path.encode("utf-8"),
            ),
        )
    )
    if {item.path for item in ordered if item.scope == "external_runtime"} != set(
        external
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "runtime observation does not close the external runtime inventory"
        )
    return ordered


def _verify_observed_elf_files(
    imports: tuple[ImportIdentity, ...],
    *,
    environment_root: Path,
) -> None:
    required_native_subjects = {
        "scion.runtime.native._spawn_into_cgroup",
        _DBUS_BINDINGS_SUBJECT,
        _DBUS_GLIB_BINDINGS_SUBJECT,
    }
    required_python_subjects = {
        "scion.tools.scion_w3_tool",
        _DBUS_PACKAGE_SUBJECT,
    }
    by_subject = {item.subject: item for item in imports}
    if not (required_native_subjects | required_python_subjects).issubset(by_subject):
        raise WarehouseW3EnvironmentReceiptError(
            "runtime observation omits a required Python or native module"
        )
    for subject in required_native_subjects:
        if by_subject[subject].kind != "native_extension":
            raise WarehouseW3EnvironmentReceiptError(
                f"runtime native extension kind differs: {subject}"
            )
    for subject in required_python_subjects:
        if by_subject[subject].kind != "python":
            raise WarehouseW3EnvironmentReceiptError(
                f"runtime Python module kind differs: {subject}"
            )
    for item in imports:
        if item.kind not in {"native_extension", "shared_library", "executable"}:
            continue
        path = (
            environment_root / item.path
            if item.scope == "environment"
            else Path(item.path)
        )
        raw = _read_bound_regular(
            path,
            expected_sha256=item.sha256,
            expected_size_bytes=item.size_bytes,
        )
        if not raw.startswith(_ELF_MAGIC):
            raise WarehouseW3EnvironmentReceiptError(
                f"runtime executable, native, or shared file is not ELF: {item.subject}"
            )


@dataclass(frozen=True, slots=True)
class SubprocessEnvironmentProbeReader:
    """Fixed local subprocess producer for actual target-interpreter facts."""

    def __post_init__(self) -> None:
        if os.geteuid() == 0:
            raise PermissionError("environment probe reader rejects effective UID zero")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SubprocessEnvironmentProbeReader is final")

    def _observe(self, environment_root: Path) -> _RuntimeObservation:
        if not isinstance(environment_root, Path):
            raise TypeError("environment_root must be Path")
        root = Path(
            _absolute_path(
                str(environment_root),
                field="subprocess probe environment root",
            )
        )
        executable = root / "bin" / "python"
        argv = (
            str(executable),
            "-I",
            "-B",
            "-c",
            _FIXED_PROBE_HELPER,
        )
        environment = {
            "DBUS_SYSTEM_BUS_ADDRESS": "unix:path=/run/dbus/system_bus_socket",
            "HOME": "/nonexistent",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": "/usr/bin:/bin",
            "TMPDIR": "/tmp",
        }
        try:
            completed = subprocess.run(
                argv,
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=_PROBE_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise WarehouseW3EnvironmentReceiptError(
                "fixed environment probe could not execute"
            ) from exc
        if (
            type(completed.returncode) is not int
            or completed.returncode != 0
            or type(completed.stdout) is not bytes
            or not completed.stdout
            or len(completed.stdout) > 4 * 1024 * 1024
            or type(completed.stderr) is not bytes
            or completed.stderr
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "fixed environment probe did not return one clean fact"
            )
        return _RuntimeObservation.from_bytes(completed.stdout)

    def discover_external_runtime_paths(
        self,
        environment_root: Path,
    ) -> tuple[Path, ...]:
        """Discover the fixed helper's complete environment-external file set."""

        observation = self._observe(environment_root)
        external = {
            path
            for path in (
                observation.sys_executable,
                *(item.path for item in observation.module_files),
                *observation.mapped_shared_libraries,
            )
            if _relative_to_environment(path, environment_root) is None
        }
        if not external:
            raise WarehouseW3EnvironmentReceiptError(
                "fixed probe discovered no external runtime files"
            )
        paths = tuple(
            Path(path)
            for path in sorted(external, key=lambda item: item.encode("utf-8"))
        )
        for path in paths:
            try:
                opened = os.stat(path, follow_symlinks=False)
            except OSError as exc:
                raise WarehouseW3EnvironmentReceiptError(
                    f"discovered external runtime path cannot be reopened: {path}"
                ) from exc
            if not stat.S_ISREG(opened.st_mode):
                raise WarehouseW3EnvironmentReceiptError(
                    f"discovered external runtime path is not regular: {path}"
                )
        return paths

    def probe(
        self,
        environment_root: Path,
        *,
        phase: str,
        content_receipt: WarehouseEnvironmentContentReceipt,
    ) -> EnvironmentProbeFact:
        content = _validated_content(content_receipt)
        observation = self._observe(environment_root)
        imports = _runtime_import_table(
            observation,
            environment_root=environment_root,
            generic_receipt=content.generic_receipt,
        )
        if imports != content.evidence.import_table:
            raise WarehouseW3EnvironmentReceiptError(
                "runtime loaded-file inventory differs from semantic content"
            )
        _verify_observed_elf_files(imports, environment_root=environment_root)
        return EnvironmentProbeFact.create(
            phase=phase,
            content_receipt_sha256=content.raw_sha256,
            environment_root=environment_root,
            sys_executable=Path(observation.sys_executable),
            sys_prefix=Path(observation.sys_prefix),
            sys_path=tuple(Path(path) for path in observation.sys_path),
            import_table_sha256=content.import_table_sha256,
            loaded_import_table=imports,
            native_loaded_paths=tuple(
                sorted(
                    (
                        (
                            environment_root / item.path
                            if item.scope == "environment"
                            else Path(item.path)
                        )
                        for item in imports
                        if item.kind == "native_extension"
                    ),
                    key=lambda item: str(item).encode("utf-8"),
                )
            ),
            shared_library_paths=tuple(
                sorted(
                    (
                        (
                            environment_root / item.path
                            if item.scope == "environment"
                            else Path(item.path)
                        )
                        for item in imports
                        if item.kind == "shared_library"
                    ),
                    key=lambda item: str(item).encode("utf-8"),
                )
            ),
            dbus_acquired=observation.dbus_acquired,
            dbus_unique_name=observation.dbus_unique_name,
            dispatcher_argv=(
                str(environment_root / "bin" / "python"),
                "-m",
                "scion.tools.scion_w3_tool",
                "run",
            ),
        )


def discover_environment_external_runtime_paths(
    environment_root: Path,
) -> tuple[Path, ...]:
    """Discover the fixed target interpreter's external runtime closure.

    This read-only production API intentionally accepts no caller-selected
    reader.  It runs before :class:`EnvironmentContentReceipt` acquisition so
    that the generic receipt can bind the mechanically observed external file
    set without a bootstrap loop.
    """

    if not isinstance(environment_root, Path):
        raise TypeError("environment_root must be Path")
    _absolute_path(str(environment_root), field="environment_root")
    return SubprocessEnvironmentProbeReader().discover_external_runtime_paths(
        environment_root
    )


@dataclass(frozen=True, slots=True)
class FilesystemEnvironmentSemanticReader:
    """Final production semantic collector backed only by the fixed probe."""

    probe_reader: SubprocessEnvironmentProbeReader

    def __post_init__(self) -> None:
        if type(self.probe_reader) is not SubprocessEnvironmentProbeReader:
            raise TypeError(
                "probe_reader must be exact SubprocessEnvironmentProbeReader"
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("FilesystemEnvironmentSemanticReader is final")

    def read(
        self,
        environment_root: Path,
        *,
        generic_receipt: EnvironmentContentReceipt,
        wheel_receipt: OfflineDoubleWheelReceipt,
    ) -> WarehouseEnvironmentEvidence:
        generic = _validated_generic(generic_receipt)
        wheel = _validated_wheel(wheel_receipt)
        observation = self.probe_reader._observe(environment_root)
        imports = _runtime_import_table(
            observation,
            environment_root=environment_root,
            generic_receipt=generic,
        )
        _verify_observed_elf_files(imports, environment_root=environment_root)
        environment = {
            item.path: item
            for item in generic.environment_inventory
            if item.kind == "regular"
        }
        native_matches = tuple(
            item
            for item in environment.values()
            if item.path.endswith(f"/{wheel.native_member_path}")
            and item.sha256 == wheel.native_elf_sha256
            and item.size_bytes == _native_wheel_member_size(wheel)
        )
        if len(native_matches) != 1:
            raise WarehouseW3EnvironmentReceiptError(
                "runtime observation does not identify one installed native wheel member"
            )
        native_entry = native_matches[0]
        native_path = PurePosixPath(native_entry.path)
        member_path = PurePosixPath(wheel.native_member_path)
        installation_prefix = PurePosixPath(
            *native_path.parts[: -len(member_path.parts)]
        )
        installed_members = tuple(
            InstalledWheelMember(
                wheel_member_path=member.path,
                environment_path=(installation_prefix / member.path).as_posix(),
                sha256=member.sha256,
                size_bytes=member.size_bytes,
            )
            for member in wheel.member_inventory
        )
        wheel_installation = WheelInstallationProvenance(
            manifest_path=_WHEEL_INSTALLATION_MANIFEST_PATH,
            wheel_receipt_sha256=wheel.raw_sha256,
            wheel_sha256=wheel.wheel_sha256,
            installed_members=installed_members,
        )
        metadata_matches = tuple(
            item
            for item in environment.values()
            if re.fullmatch(
                r"lib/python3\.12/site-packages/"
                r"dbus_python-[^/]+\.dist-info/METADATA",
                item.path,
            )
        )
        if len(metadata_matches) != 1:
            raise WarehouseW3EnvironmentReceiptError(
                "environment does not contain one exact D-Bus METADATA file"
            )
        metadata_entry = metadata_matches[0]
        metadata_raw = _read_bound_regular(
            environment_root / metadata_entry.path,
            expected_sha256=metadata_entry.sha256 or "",
            expected_size_bytes=metadata_entry.size_bytes,
            maximum=1 << 20,
        )
        try:
            metadata_contents = metadata_raw.decode("utf-8", "strict")
            metadata = Parser(policy=strict_email_policy).parsestr(
                metadata_contents,
                headersonly=True,
            )
        except (UnicodeError, Exception) as exc:
            raise WarehouseW3EnvironmentReceiptError(
                "installed D-Bus METADATA cannot be read"
            ) from exc
        names = metadata.get_all("Name", failobj=[])
        versions = metadata.get_all("Version", failobj=[])
        if names != [_DBUS_DISTRIBUTION_NAME] or len(versions) != 1:
            raise WarehouseW3EnvironmentReceiptError(
                "installed D-Bus METADATA identity differs"
            )
        shared_paths = tuple(
            sorted(
                (
                    item.path
                    for item in imports
                    if item.kind == "shared_library"
                    and item.scope == "external_runtime"
                ),
                key=lambda item: item.encode("utf-8"),
            )
        )
        evidence = WarehouseEnvironmentEvidence(
            native_elf=NativeElfIdentity(
                environment_path=native_entry.path,
                sha256=native_entry.sha256 or "",
                size_bytes=native_entry.size_bytes,
            ),
            wheel_installation=wheel_installation,
            import_table=imports,
            dbus_provenance=DbusProvenance(
                package_version=versions[0],
                package_metadata_path=metadata_entry.path,
                package_metadata_contents=metadata_contents,
                package_subject=_DBUS_PACKAGE_SUBJECT,
                bindings_subject=_DBUS_BINDINGS_SUBJECT,
                glib_bindings_subject=_DBUS_GLIB_BINDINGS_SUBJECT,
                shared_library_paths=shared_paths,
            ),
        )
        _validate_semantic_evidence(generic, wheel, evidence)
        return evidence


class EnvironmentSemanticReader(Protocol):
    """Read all Warehouse semantic facts without mutating the environment."""

    def read(
        self,
        environment_root: Path,
        *,
        generic_receipt: EnvironmentContentReceipt,
        wheel_receipt: OfflineDoubleWheelReceipt,
    ) -> WarehouseEnvironmentEvidence: ...


@dataclass(frozen=True, slots=True, init=False)
class WarehouseEnvironmentContentReceipt:
    generic_receipt: EnvironmentContentReceipt
    wheel_receipt: OfflineDoubleWheelReceipt
    generic_receipt_sha256: str
    wheel_receipt_sha256: str
    wheel_sha256: str
    evidence: WarehouseEnvironmentEvidence
    import_table_sha256: str
    environment_inventory_sha256: str
    external_runtime_closure_sha256: str
    external_runtime_count: int
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseEnvironmentContentReceipt":
        del cls
        raise TypeError(
            "WarehouseEnvironmentContentReceipt must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseEnvironmentContentReceipt is final")

    @classmethod
    def create(
        cls,
        generic_receipt: EnvironmentContentReceipt,
        wheel_receipt: OfflineDoubleWheelReceipt,
        evidence: WarehouseEnvironmentEvidence,
    ) -> "WarehouseEnvironmentContentReceipt":
        generic = _validated_generic(generic_receipt)
        wheel = _validated_wheel(wheel_receipt)
        if type(evidence) is not WarehouseEnvironmentEvidence:
            raise TypeError("evidence must be exact WarehouseEnvironmentEvidence")
        _validate_semantic_evidence(generic, wheel, evidence)
        value = {
            "schema": _SEMANTIC_SCHEMA,
            "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "generic_receipt_sha256": generic.raw_sha256,
            "wheel_receipt_sha256": wheel.raw_sha256,
            "wheel_sha256": wheel.wheel_sha256,
            "native_elf": evidence.native_elf.to_mapping(),
            "wheel_installation": evidence.wheel_installation.to_mapping(),
            "import_table": [item.to_mapping() for item in evidence.import_table],
            "import_table_sha256": _import_table_sha256(evidence.import_table),
            "dbus_provenance": evidence.dbus_provenance.to_mapping(),
            "environment_inventory_sha256": _inventory_sha256(generic),
            "external_runtime_closure_sha256": _external_runtime_sha256(generic),
            "external_runtime_count": len(generic.external_runtime),
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        raw = _canonical_json(value)
        if str(FINAL_ENVIRONMENT_PARENT).encode("ascii") in raw:
            raise WarehouseW3EnvironmentReceiptError(
                "semantic content receipt contains a final digest-derived path"
            )
        return cls.from_bytes(
            raw,
            generic_receipt=generic,
            wheel_receipt=wheel,
        )

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        generic_receipt: EnvironmentContentReceipt,
        wheel_receipt: OfflineDoubleWheelReceipt,
    ) -> "WarehouseEnvironmentContentReceipt":
        generic = _validated_generic(generic_receipt)
        wheel = _validated_wheel(wheel_receipt)
        value = _exact_fields(
            _decode_canonical(raw, label="Warehouse environment content receipt"),
            frozenset(
                {
                    "schema",
                    "plan_sha256",
                    "generic_receipt_sha256",
                    "wheel_receipt_sha256",
                    "wheel_sha256",
                    "native_elf",
                    "wheel_installation",
                    "import_table",
                    "import_table_sha256",
                    "dbus_provenance",
                    "environment_inventory_sha256",
                    "external_runtime_closure_sha256",
                    "external_runtime_count",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="Warehouse environment content receipt",
        )
        if (
            value["schema"] != _SEMANTIC_SCHEMA
            or value["plan_sha256"] != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "Warehouse environment content plan or schema differs"
            )
        _false_controls(value, label="Warehouse environment content receipt")
        raw_imports = value["import_table"]
        if type(raw_imports) is not list or not raw_imports:
            raise WarehouseW3EnvironmentReceiptError("semantic import table is empty")
        evidence = WarehouseEnvironmentEvidence(
            native_elf=NativeElfIdentity.from_mapping(value["native_elf"]),
            wheel_installation=WheelInstallationProvenance.from_mapping(
                value["wheel_installation"]
            ),
            import_table=tuple(
                ImportIdentity.from_mapping(item) for item in raw_imports
            ),
            dbus_provenance=DbusProvenance.from_mapping(value["dbus_provenance"]),
        )
        _validate_semantic_evidence(generic, wheel, evidence)
        expected = {
            "generic_receipt_sha256": generic.raw_sha256,
            "wheel_receipt_sha256": wheel.raw_sha256,
            "wheel_sha256": wheel.wheel_sha256,
            "import_table_sha256": _import_table_sha256(evidence.import_table),
            "environment_inventory_sha256": _inventory_sha256(generic),
            "external_runtime_closure_sha256": _external_runtime_sha256(generic),
            "external_runtime_count": len(generic.external_runtime),
        }
        for field, item in expected.items():
            if value[field] != item:
                raise WarehouseW3EnvironmentReceiptError(
                    f"Warehouse environment content {field} differs"
                )
        if str(FINAL_ENVIRONMENT_PARENT).encode("ascii") in raw:
            raise WarehouseW3EnvironmentReceiptError(
                "semantic content receipt contains a final digest-derived path"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("generic_receipt", generic),
            ("wheel_receipt", wheel),
            ("generic_receipt_sha256", generic.raw_sha256),
            ("wheel_receipt_sha256", wheel.raw_sha256),
            ("wheel_sha256", wheel.wheel_sha256),
            ("evidence", evidence),
            ("import_table_sha256", expected["import_table_sha256"]),
            (
                "environment_inventory_sha256",
                expected["environment_inventory_sha256"],
            ),
            (
                "external_runtime_closure_sha256",
                expected["external_runtime_closure_sha256"],
            ),
            ("external_runtime_count", expected["external_runtime_count"]),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


def _validated_content(
    receipt: WarehouseEnvironmentContentReceipt,
) -> WarehouseEnvironmentContentReceipt:
    if type(receipt) is not WarehouseEnvironmentContentReceipt:
        raise TypeError(
            "content_receipt must be exact WarehouseEnvironmentContentReceipt"
        )
    parsed = WarehouseEnvironmentContentReceipt.from_bytes(
        receipt.raw,
        generic_receipt=receipt.generic_receipt,
        wheel_receipt=receipt.wheel_receipt,
    )
    if parsed != receipt:
        raise WarehouseW3EnvironmentReceiptError(
            "Warehouse environment content receipt object differs"
        )
    return receipt


def acquire_warehouse_environment_content(
    environment_root: Path,
    *,
    generic_receipt: EnvironmentContentReceipt,
    wheel_receipt: OfflineDoubleWheelReceipt,
    reader: FilesystemEnvironmentSemanticReader,
) -> WarehouseEnvironmentContentReceipt:
    """Read one stable semantic view and bind it to exact generic/wheel receipts."""

    if not isinstance(environment_root, Path):
        raise TypeError("environment_root must be Path")
    _absolute_path(str(environment_root), field="environment_root")
    if type(reader) is not FilesystemEnvironmentSemanticReader:
        raise TypeError("reader must be exact FilesystemEnvironmentSemanticReader")
    return _acquire_warehouse_environment_content(
        environment_root,
        generic_receipt=generic_receipt,
        wheel_receipt=wheel_receipt,
        reader=reader,
    )


def acquire_warehouse_environment_content_for_test(
    environment_root: Path,
    *,
    generic_receipt: EnvironmentContentReceipt,
    wheel_receipt: OfflineDoubleWheelReceipt,
    reader: EnvironmentSemanticReader,
) -> WarehouseEnvironmentContentReceipt:
    """Explicit synthetic seam for receipt codec tests; never production authority."""

    if not isinstance(environment_root, Path):
        raise TypeError("environment_root must be Path")
    _absolute_path(str(environment_root), field="environment_root")
    return _acquire_warehouse_environment_content(
        environment_root,
        generic_receipt=generic_receipt,
        wheel_receipt=wheel_receipt,
        reader=reader,
    )


def _acquire_warehouse_environment_content(
    environment_root: Path,
    *,
    generic_receipt: EnvironmentContentReceipt,
    wheel_receipt: OfflineDoubleWheelReceipt,
    reader: EnvironmentSemanticReader,
) -> WarehouseEnvironmentContentReceipt:
    method = getattr(reader, "read", None)
    if not callable(method):
        raise TypeError("reader must expose read")
    first = method(
        environment_root,
        generic_receipt=generic_receipt,
        wheel_receipt=wheel_receipt,
    )
    if type(first) is not WarehouseEnvironmentEvidence:
        raise WarehouseW3EnvironmentReceiptError(
            "semantic reader returned an inexact evidence type"
        )
    receipt = WarehouseEnvironmentContentReceipt.create(
        generic_receipt,
        wheel_receipt,
        first,
    )
    second = method(
        environment_root,
        generic_receipt=generic_receipt,
        wheel_receipt=wheel_receipt,
    )
    if second != first:
        raise WarehouseW3EnvironmentReceiptError(
            "semantic environment evidence changed while acquired"
        )
    return receipt


def derive_final_environment_path(
    receipt: WarehouseEnvironmentContentReceipt,
) -> Path:
    content = _validated_content(receipt)
    return Path(str(FINAL_ENVIRONMENT_PARENT / content.generic_receipt_sha256))


@dataclass(frozen=True, slots=True, init=False)
class EnvironmentProbeFact:
    phase: str
    content_receipt_sha256: str
    environment_root: str
    sys_executable: str
    sys_prefix: str
    sys_path: tuple[str, ...]
    import_table_sha256: str
    loaded_import_table: tuple[ImportIdentity, ...]
    native_loaded_paths: tuple[str, ...]
    shared_library_paths: tuple[str, ...]
    dbus_acquired: bool
    dbus_unique_name: str
    dispatcher_argv: tuple[str, ...]
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "EnvironmentProbeFact":
        del cls
        raise TypeError("EnvironmentProbeFact must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("EnvironmentProbeFact is final")

    @classmethod
    def create(
        cls,
        *,
        phase: str,
        content_receipt_sha256: str,
        environment_root: Path,
        sys_executable: Path,
        sys_prefix: Path,
        sys_path: tuple[Path, ...],
        import_table_sha256: str,
        loaded_import_table: tuple[ImportIdentity, ...],
        native_loaded_paths: tuple[Path, ...],
        shared_library_paths: tuple[Path, ...],
        dbus_acquired: bool,
        dbus_unique_name: str,
        dispatcher_argv: tuple[str, ...],
    ) -> "EnvironmentProbeFact":
        if phase not in _PROBE_PHASES:
            raise WarehouseW3EnvironmentReceiptError("environment probe phase differs")
        if type(sys_path) is not tuple or not sys_path:
            raise TypeError("sys_path must be one nonempty exact tuple")
        if (
            type(loaded_import_table) is not tuple
            or not loaded_import_table
            or any(type(item) is not ImportIdentity for item in loaded_import_table)
        ):
            raise TypeError(
                "loaded_import_table must be one nonempty exact ImportIdentity tuple"
            )
        if type(native_loaded_paths) is not tuple or not native_loaded_paths:
            raise TypeError("native_loaded_paths must be one nonempty exact tuple")
        if type(shared_library_paths) is not tuple or not shared_library_paths:
            raise TypeError("shared_library_paths must be one nonempty exact tuple")
        if type(dispatcher_argv) is not tuple or not dispatcher_argv:
            raise TypeError("dispatcher_argv must be one nonempty exact tuple")
        value = {
            "schema": _PROBE_SCHEMA,
            "phase": phase,
            "content_receipt_sha256": _sha256(
                content_receipt_sha256,
                field="content_receipt_sha256",
            ),
            "environment_root": _absolute_path(
                str(environment_root),
                field="probe environment_root",
            ),
            "sys_executable": _absolute_path(
                str(sys_executable),
                field="probe sys_executable",
            ),
            "sys_prefix": _absolute_path(
                str(sys_prefix),
                field="probe sys_prefix",
            ),
            "sys_path": [
                _absolute_path(str(path), field="probe sys_path") for path in sys_path
            ],
            "import_table_sha256": _sha256(
                import_table_sha256,
                field="probe import_table_sha256",
            ),
            "loaded_import_table": [item.to_mapping() for item in loaded_import_table],
            "native_loaded_paths": [
                _absolute_path(str(path), field="native loaded path")
                for path in native_loaded_paths
            ],
            "shared_library_paths": [
                _absolute_path(str(path), field="shared library path")
                for path in shared_library_paths
            ],
            "dbus_acquired": dbus_acquired,
            "dbus_unique_name": _text(
                dbus_unique_name,
                field="probe D-Bus unique name",
                maximum=256,
            ),
            "dispatcher_argv": [
                _text(item, field="dispatcher argv item", maximum=4096)
                for item in dispatcher_argv
            ],
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "EnvironmentProbeFact":
        value = _exact_fields(
            _decode_canonical(raw, label="environment probe fact"),
            frozenset(
                {
                    "schema",
                    "phase",
                    "content_receipt_sha256",
                    "environment_root",
                    "sys_executable",
                    "sys_prefix",
                    "sys_path",
                    "import_table_sha256",
                    "loaded_import_table",
                    "native_loaded_paths",
                    "shared_library_paths",
                    "dbus_acquired",
                    "dbus_unique_name",
                    "dispatcher_argv",
                }
            ),
            label="environment probe fact",
        )
        phase = value["phase"]
        if value["schema"] != _PROBE_SCHEMA or phase not in _PROBE_PHASES:
            raise WarehouseW3EnvironmentReceiptError(
                "environment probe schema or phase differs"
            )
        sys_path = _string_tuple(
            value["sys_path"],
            field="probe sys_path",
            absolute=True,
        )
        native_paths = _string_tuple(
            value["native_loaded_paths"],
            field="native loaded paths",
            absolute=True,
            sorted_unique=True,
        )
        shared_paths = _string_tuple(
            value["shared_library_paths"],
            field="shared library paths",
            absolute=True,
            sorted_unique=True,
        )
        argv = _string_tuple(value["dispatcher_argv"], field="dispatcher argv")
        raw_loaded = value["loaded_import_table"]
        if type(raw_loaded) is not list or not raw_loaded:
            raise WarehouseW3EnvironmentReceiptError(
                "probe loaded import table is empty"
            )
        loaded_imports = tuple(ImportIdentity.from_mapping(item) for item in raw_loaded)
        if (
            loaded_imports
            != tuple(
                sorted(
                    loaded_imports,
                    key=lambda item: (
                        item.subject.encode("utf-8"),
                        item.path.encode("utf-8"),
                    ),
                )
            )
            or len({item.subject for item in loaded_imports}) != len(loaded_imports)
            or len({(item.scope, item.path) for item in loaded_imports})
            != len(loaded_imports)
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "probe loaded import table is not unique and byte-sorted"
            )
        unique_name = _text(
            value["dbus_unique_name"],
            field="probe D-Bus unique name",
            maximum=256,
        )
        if value["dbus_acquired"] is not True or not unique_name.startswith(":"):
            raise WarehouseW3EnvironmentReceiptError(
                "probe SystemBus acquisition did not succeed"
            )
        environment_root = _absolute_path(
            value["environment_root"],
            field="probe environment_root",
        )
        sys_executable = _absolute_path(
            value["sys_executable"],
            field="probe sys_executable",
        )
        sys_prefix = _absolute_path(
            value["sys_prefix"],
            field="probe sys_prefix",
        )
        expected_executable = f"{environment_root}/bin/python"
        if (
            sys_executable != expected_executable
            or sys_prefix != environment_root
            or argv
            != (
                expected_executable,
                "-m",
                "scion.tools.scion_w3_tool",
                "run",
            )
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "probe dispatcher argv or interpreter identity differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("phase", phase),
            (
                "content_receipt_sha256",
                _sha256(
                    value["content_receipt_sha256"],
                    field="content_receipt_sha256",
                ),
            ),
            (
                "environment_root",
                environment_root,
            ),
            (
                "sys_executable",
                sys_executable,
            ),
            (
                "sys_prefix",
                sys_prefix,
            ),
            ("sys_path", sys_path),
            (
                "import_table_sha256",
                _sha256(
                    value["import_table_sha256"],
                    field="probe import_table_sha256",
                ),
            ),
            ("loaded_import_table", loaded_imports),
            ("native_loaded_paths", native_paths),
            ("shared_library_paths", shared_paths),
            ("dbus_acquired", value["dbus_acquired"]),
            ("dbus_unique_name", unique_name),
            ("dispatcher_argv", argv),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True, init=False)
class NamespaceProbeExecutionFact:
    """Exact non-root bubblewrap execution boundary for a future-path probe."""

    physical_environment_root: str
    visible_environment_root: str
    environment_probe_sha256: str
    producer_euid: int
    producer_egid: int
    no_new_privs: bool
    parent_network_namespace: str
    child_network_namespace: str
    parent_mount_namespace: str
    child_mount_namespace: str
    bwrap_path: str
    bwrap_sha256: str
    bwrap_device: int
    bwrap_inode: int
    bwrap_size_bytes: int
    bwrap_mode: int
    host_root_read_only: bool
    network_unshared: bool
    writable_host_bind_count: int
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "NamespaceProbeExecutionFact":
        del cls
        raise TypeError("NamespaceProbeExecutionFact must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("NamespaceProbeExecutionFact is final")

    @classmethod
    def create(
        cls,
        *,
        physical_environment_root: Path,
        visible_environment_root: Path,
        environment_probe: EnvironmentProbeFact,
        producer_euid: int,
        producer_egid: int,
        no_new_privs: bool,
        parent_network_namespace: str,
        child_network_namespace: str,
        parent_mount_namespace: str,
        child_mount_namespace: str,
        bwrap_sha256: str,
        bwrap_device: int,
        bwrap_inode: int,
        bwrap_size_bytes: int,
        bwrap_mode: int,
    ) -> "NamespaceProbeExecutionFact":
        value = {
            "schema": _NAMESPACE_PROBE_SCHEMA,
            "physical_environment_root": str(physical_environment_root),
            "visible_environment_root": str(visible_environment_root),
            "environment_probe_sha256": environment_probe.raw_sha256,
            "producer_euid": producer_euid,
            "producer_egid": producer_egid,
            "no_new_privs": no_new_privs,
            "parent_network_namespace": parent_network_namespace,
            "child_network_namespace": child_network_namespace,
            "parent_mount_namespace": parent_mount_namespace,
            "child_mount_namespace": child_mount_namespace,
            "bwrap_path": _BWRAP,
            "bwrap_sha256": bwrap_sha256,
            "bwrap_device": bwrap_device,
            "bwrap_inode": bwrap_inode,
            "bwrap_size_bytes": bwrap_size_bytes,
            "bwrap_mode": bwrap_mode,
            "host_root_read_only": True,
            "network_unshared": True,
            "writable_host_bind_count": 0,
        }
        return cls.from_bytes(
            _canonical_json(value),
            environment_probe=environment_probe,
        )

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        environment_probe: EnvironmentProbeFact,
    ) -> "NamespaceProbeExecutionFact":
        if type(environment_probe) is not EnvironmentProbeFact:
            raise TypeError("environment_probe must be exact EnvironmentProbeFact")
        value = _exact_fields(
            _decode_canonical(raw, label="namespace probe execution fact"),
            frozenset(
                {
                    "schema",
                    "physical_environment_root",
                    "visible_environment_root",
                    "environment_probe_sha256",
                    "producer_euid",
                    "producer_egid",
                    "no_new_privs",
                    "parent_network_namespace",
                    "child_network_namespace",
                    "parent_mount_namespace",
                    "child_mount_namespace",
                    "bwrap_path",
                    "bwrap_sha256",
                    "bwrap_device",
                    "bwrap_inode",
                    "bwrap_size_bytes",
                    "bwrap_mode",
                    "host_root_read_only",
                    "network_unshared",
                    "writable_host_bind_count",
                }
            ),
            label="namespace probe execution fact",
        )
        physical = _absolute_path(
            value["physical_environment_root"],
            field="namespace physical environment root",
        )
        visible = _absolute_path(
            value["visible_environment_root"],
            field="namespace visible environment root",
        )
        namespace_pattern = re.compile(r"(?:net|mnt):\[[0-9]+\]\Z")
        parent_net = _text(
            value["parent_network_namespace"],
            field="parent network namespace",
            maximum=128,
        )
        child_net = _text(
            value["child_network_namespace"],
            field="child network namespace",
            maximum=128,
        )
        parent_mount = _text(
            value["parent_mount_namespace"],
            field="parent mount namespace",
            maximum=128,
        )
        child_mount = _text(
            value["child_mount_namespace"],
            field="child mount namespace",
            maximum=128,
        )
        euid = _uint(value["producer_euid"], field="namespace producer_euid")
        egid = _uint(value["producer_egid"], field="namespace producer_egid")
        bwrap_mode = _uint(value["bwrap_mode"], field="bwrap mode")
        if (
            value["schema"] != _NAMESPACE_PROBE_SCHEMA
            or physical == visible
            or visible != environment_probe.environment_root
            or environment_probe.phase != "namespace_final"
            or value["environment_probe_sha256"] != environment_probe.raw_sha256
            or euid == 0
            or value["no_new_privs"] is not True
            or namespace_pattern.fullmatch(parent_net) is None
            or namespace_pattern.fullmatch(child_net) is None
            or namespace_pattern.fullmatch(parent_mount) is None
            or namespace_pattern.fullmatch(child_mount) is None
            or parent_net == child_net
            or parent_mount == child_mount
            or value["bwrap_path"] != _BWRAP
            or bwrap_mode != 0o755
            or value["host_root_read_only"] is not True
            or value["network_unshared"] is not True
            or value["writable_host_bind_count"] != 0
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "namespace probe execution boundary differs"
            )
        fields = {
            "physical_environment_root": physical,
            "visible_environment_root": visible,
            "environment_probe_sha256": environment_probe.raw_sha256,
            "producer_euid": euid,
            "producer_egid": egid,
            "no_new_privs": True,
            "parent_network_namespace": parent_net,
            "child_network_namespace": child_net,
            "parent_mount_namespace": parent_mount,
            "child_mount_namespace": child_mount,
            "bwrap_path": _BWRAP,
            "bwrap_sha256": _sha256(
                value["bwrap_sha256"],
                field="bwrap sha256",
            ),
            "bwrap_device": _uint(value["bwrap_device"], field="bwrap device"),
            "bwrap_inode": _uint(value["bwrap_inode"], field="bwrap inode"),
            "bwrap_size_bytes": _uint(
                value["bwrap_size_bytes"],
                field="bwrap size_bytes",
            ),
            "bwrap_mode": bwrap_mode,
            "host_root_read_only": True,
            "network_unshared": True,
            "writable_host_bind_count": 0,
            "raw": raw,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        instance = object.__new__(cls)
        for field, item in fields.items():
            object.__setattr__(instance, field, item)
        return instance


def _read_root_owned_bwrap_identity() -> tuple[str, os.stat_result]:
    try:
        descriptor = os.open(
            _BWRAP,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
    except OSError as exc:
        raise WarehouseW3EnvironmentReceiptError(
            "cannot open fixed bubblewrap executable"
        ) from exc
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        named = os.stat(_BWRAP, follow_symlinks=False)
    except OSError as exc:
        raise WarehouseW3EnvironmentReceiptError(
            "cannot reopen fixed bubblewrap executable"
        ) from exc
    identity = lambda item: (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_uid,
        item.st_gid,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )
    if (
        identity(before) != identity(after)
        or identity(after) != identity(named)
        or not stat.S_ISREG(named.st_mode)
        or named.st_uid != 0
        or named.st_gid != 0
        or named.st_nlink != 1
        or stat.S_IMODE(named.st_mode) != 0o755
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "fixed bubblewrap executable identity differs"
        )
    return digest.hexdigest(), named


def verify_namespace_probe_execution_binary(
    fact: NamespaceProbeExecutionFact,
) -> NamespaceProbeExecutionFact:
    """Reopen fixed bubblewrap and match the candidate execution fact."""

    if type(fact) is not NamespaceProbeExecutionFact:
        raise TypeError("fact must be exact NamespaceProbeExecutionFact")
    digest, identity = _read_root_owned_bwrap_identity()
    if (
        fact.bwrap_path != _BWRAP
        or fact.bwrap_sha256 != digest
        or fact.bwrap_device != identity.st_dev
        or fact.bwrap_inode != identity.st_ino
        or fact.bwrap_size_bytes != identity.st_size
        or fact.bwrap_mode != stat.S_IMODE(identity.st_mode)
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "live bubblewrap identity differs from namespace probe execution"
        )
    return fact


@dataclass(frozen=True, slots=True)
class NonRootNamespaceEnvironmentProbeReader:
    """Run the target interpreter non-root at its exact future visible path."""

    def __post_init__(self) -> None:
        if os.geteuid() == 0:
            raise PermissionError(
                "namespace environment probe rejects effective UID zero"
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("NonRootNamespaceEnvironmentProbeReader is final")

    def probe(
        self,
        physical_environment_root: Path,
        *,
        content_receipt: WarehouseEnvironmentContentReceipt,
    ) -> tuple[EnvironmentProbeFact, NamespaceProbeExecutionFact]:
        content = _validated_content(content_receipt)
        physical = Path(
            _absolute_path(
                str(physical_environment_root),
                field="namespace physical environment root",
            )
        )
        visible = derive_final_environment_path(content)
        if physical == visible:
            raise WarehouseW3EnvironmentReceiptError(
                "namespace probe physical and visible roots are equal"
            )
        bwrap_sha256, bwrap_identity = _read_root_owned_bwrap_identity()
        parent_net = os.readlink("/proc/self/ns/net")
        parent_mount = os.readlink("/proc/self/ns/mnt")
        argv = (
            _BWRAP,
            "--unshare-net",
            "--unshare-pid",
            "--die-with-parent",
            "--new-session",
            "--clearenv",
            "--ro-bind",
            "/",
            "/",
            "--tmpfs",
            "/var/lib",
            "--dir",
            "/var/lib/scion",
            "--dir",
            "/var/lib/scion/environments",
            "--dir",
            "/var/lib/scion/environments/w3",
            "--ro-bind",
            str(physical),
            str(visible),
            "--proc",
            "/proc",
            "--chdir",
            str(visible),
            "--setenv",
            "DBUS_SYSTEM_BUS_ADDRESS",
            "unix:path=/run/dbus/system_bus_socket",
            "--setenv",
            "HOME",
            "/nonexistent",
            "--setenv",
            "LANG",
            "C.UTF-8",
            "--setenv",
            "LC_ALL",
            "C.UTF-8",
            "--setenv",
            "PATH",
            "/usr/bin:/bin",
            "--setenv",
            "TMPDIR",
            "/tmp",
            "--",
            f"{visible}/bin/python",
            "-I",
            "-B",
            "-c",
            _FIXED_PROBE_HELPER,
        )
        try:
            completed = subprocess.run(
                argv,
                cwd=physical,
                env={
                    "HOME": "/nonexistent",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                    "PATH": "/usr/bin:/bin",
                },
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=_PROBE_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise WarehouseW3EnvironmentReceiptError(
                "namespace environment probe could not execute"
            ) from exc
        if (
            completed.returncode != 0
            or type(completed.stdout) is not bytes
            or not completed.stdout
            or len(completed.stdout) > 4 * 1024 * 1024
            or type(completed.stderr) is not bytes
            or completed.stderr
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "namespace environment probe did not return one clean fact"
            )
        observation = _RuntimeObservation.from_bytes(completed.stdout)
        if (
            observation.effective_uid != os.geteuid()
            or observation.effective_gid != os.getegid()
            or observation.effective_uid == 0
            or observation.no_new_privs != 1
            or observation.network_namespace == parent_net
            or observation.mount_namespace == parent_mount
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "namespace environment execution facts differ"
            )
        imports = _runtime_import_table(
            observation,
            environment_root=visible,
            generic_receipt=content.generic_receipt,
        )
        if imports != content.evidence.import_table:
            raise WarehouseW3EnvironmentReceiptError(
                "namespace loaded-file inventory differs from semantic content"
            )
        _verify_observed_elf_files(imports, environment_root=physical)
        probe = EnvironmentProbeFact.create(
            phase="namespace_final",
            content_receipt_sha256=content.raw_sha256,
            environment_root=visible,
            sys_executable=Path(observation.sys_executable),
            sys_prefix=Path(observation.sys_prefix),
            sys_path=tuple(Path(path) for path in observation.sys_path),
            import_table_sha256=content.import_table_sha256,
            loaded_import_table=imports,
            native_loaded_paths=tuple(
                sorted(
                    (
                        (
                            visible / item.path
                            if item.scope == "environment"
                            else Path(item.path)
                        )
                        for item in imports
                        if item.kind == "native_extension"
                    ),
                    key=lambda item: str(item).encode("utf-8"),
                )
            ),
            shared_library_paths=tuple(
                sorted(
                    (
                        (
                            visible / item.path
                            if item.scope == "environment"
                            else Path(item.path)
                        )
                        for item in imports
                        if item.kind == "shared_library"
                    ),
                    key=lambda item: str(item).encode("utf-8"),
                )
            ),
            dbus_acquired=observation.dbus_acquired,
            dbus_unique_name=observation.dbus_unique_name,
            dispatcher_argv=(
                f"{visible}/bin/python",
                "-m",
                "scion.tools.scion_w3_tool",
                "run",
            ),
        )
        execution = NamespaceProbeExecutionFact.create(
            physical_environment_root=physical,
            visible_environment_root=visible,
            environment_probe=probe,
            producer_euid=os.geteuid(),
            producer_egid=os.getegid(),
            no_new_privs=True,
            parent_network_namespace=parent_net,
            child_network_namespace=observation.network_namespace,
            parent_mount_namespace=parent_mount,
            child_mount_namespace=observation.mount_namespace,
            bwrap_sha256=bwrap_sha256,
            bwrap_device=bwrap_identity.st_dev,
            bwrap_inode=bwrap_identity.st_ino,
            bwrap_size_bytes=bwrap_identity.st_size,
            bwrap_mode=stat.S_IMODE(bwrap_identity.st_mode),
        )
        return probe, execution


class EnvironmentProbeReader(Protocol):
    """Acquire one exact import/D-Bus/dispatcher probe without mutation."""

    def probe(
        self,
        environment_root: Path,
        *,
        phase: str,
        content_receipt: WarehouseEnvironmentContentReceipt,
    ) -> EnvironmentProbeFact: ...


def _expected_loaded_paths(
    root: Path,
    content: WarehouseEnvironmentContentReceipt,
    *,
    kind: str,
) -> tuple[str, ...]:
    values = []
    for item in content.evidence.import_table:
        if item.kind != kind:
            continue
        path = root / item.path if item.scope == "environment" else Path(item.path)
        values.append(str(path))
    return tuple(sorted(values, key=lambda item: item.encode()))


def _expected_sys_path(
    root: Path,
    content: WarehouseEnvironmentContentReceipt,
) -> tuple[str, ...]:
    relative_roots: set[str] = set()
    external_roots: set[str] = set()
    for item in content.evidence.import_table:
        if item.kind not in {"python", "native_extension", "stdlib"}:
            continue
        path = PurePosixPath(item.path)
        if item.scope == "environment":
            parts = path.parts
            if "site-packages" in parts:
                index = parts.index("site-packages")
                relative_roots.add(PurePosixPath(*parts[: index + 1]).as_posix())
            elif "lib-dynload" in parts:
                index = parts.index("lib-dynload")
                relative_roots.add(PurePosixPath(*parts[: index + 1]).as_posix())
            elif len(parts) >= 2 and parts[0] == "lib" and parts[1] == "python3.12":
                relative_roots.add("lib/python3.12")
            else:
                raise WarehouseW3EnvironmentReceiptError(
                    f"import path has no accepted Python root: {item.subject}"
                )
        else:
            parts = path.parts
            if "site-packages" in parts:
                index = parts.index("site-packages")
                external_roots.add(PurePosixPath(*parts[: index + 1]).as_posix())
            elif "lib-dynload" in parts:
                index = parts.index("lib-dynload")
                external_roots.add(PurePosixPath(*parts[: index + 1]).as_posix())
            elif "python3.12" in parts:
                index = parts.index("python3.12")
                external_roots.add(PurePosixPath(*parts[: index + 1]).as_posix())
            else:
                raise WarehouseW3EnvironmentReceiptError(
                    f"external import has no accepted Python root: {item.subject}"
                )
    for value in tuple(external_roots):
        path = PurePosixPath(value)
        if "python3.12" in path.parts:
            index = path.parts.index("python3.12")
            parent = PurePosixPath(*path.parts[:index])
            external_roots.add((parent / "python312.zip").as_posix())
    return tuple(
        sorted(
            (
                *(str(root / value) for value in relative_roots),
                *external_roots,
            ),
            key=lambda item: item.encode(),
        )
    )


def _validate_probe(
    fact: EnvironmentProbeFact,
    *,
    phase: str,
    root: Path,
    content: WarehouseEnvironmentContentReceipt,
) -> None:
    if type(fact) is not EnvironmentProbeFact:
        raise WarehouseW3EnvironmentReceiptError(
            "probe reader returned an inexact fact type"
        )
    if EnvironmentProbeFact.from_bytes(fact.raw) != fact:
        raise WarehouseW3EnvironmentReceiptError("probe fact object differs")
    expected_root = _absolute_path(str(root), field="expected probe root")
    expected_executable = f"{expected_root}/bin/python"
    if (
        fact.phase != phase
        or fact.content_receipt_sha256 != content.raw_sha256
        or fact.environment_root != expected_root
        or fact.sys_executable != expected_executable
        or fact.sys_prefix != expected_root
        or fact.import_table_sha256 != content.import_table_sha256
        or fact.loaded_import_table != content.evidence.import_table
        or fact.native_loaded_paths
        != _expected_loaded_paths(root, content, kind="native_extension")
        or fact.shared_library_paths
        != _expected_loaded_paths(root, content, kind="shared_library")
        or fact.dbus_acquired is not True
        or not fact.dbus_unique_name.startswith(":")
        or fact.dispatcher_argv
        != (
            expected_executable,
            "-m",
            "scion.tools.scion_w3_tool",
            "run",
        )
    ):
        raise WarehouseW3EnvironmentReceiptError(
            f"{phase} environment probe is not cross-bound"
        )
    _sys_path_shape(fact.sys_path, root=root, content=content)


def validate_environment_probe_fact(
    fact: EnvironmentProbeFact,
    *,
    phase: str,
    root: Path,
    content: WarehouseEnvironmentContentReceipt,
) -> None:
    """Reopen and validate one exact problem-owned environment probe fact."""

    _validate_probe(
        fact,
        phase=phase,
        root=root,
        content=content,
    )


def _sys_path_shape(
    values: tuple[str, ...],
    *,
    root: Path,
    content: WarehouseEnvironmentContentReceipt,
) -> tuple[tuple[str, str], ...]:
    expected = _expected_sys_path(root, content)
    if len(values) != len(expected) or set(values) != set(expected):
        raise WarehouseW3EnvironmentReceiptError(
            "probe sys.path differs from the exact import-root closure"
        )
    root_path = PurePosixPath(str(root))
    shaped = []
    for value in values:
        path = PurePosixPath(value)
        try:
            relative = path.relative_to(root_path)
        except ValueError:
            shaped.append(("external_runtime", path.as_posix()))
        else:
            shaped.append(("environment", relative.as_posix()))
    return tuple(shaped)


def _validate_relocation_probe_equivalence(
    candidate: EnvironmentProbeFact,
    namespace_final: EnvironmentProbeFact,
    *,
    content: WarehouseEnvironmentContentReceipt,
) -> None:
    shapes = tuple(
        _sys_path_shape(
            fact.sys_path,
            root=Path(fact.environment_root),
            content=content,
        )
        for fact in (candidate, namespace_final)
    )
    if (
        shapes[0] != shapes[1]
        or candidate.dispatcher_argv[1:] != namespace_final.dispatcher_argv[1:]
    ):
        raise WarehouseW3EnvironmentReceiptError(
            "candidate and namespace-final probe shapes differ"
        )


@dataclass(frozen=True, slots=True, init=False)
class LiveEnvironmentRehashFact:
    phase: str
    content_receipt_sha256: str
    generic_receipt_sha256: str
    environment_root: str
    observed_generic_receipt: EnvironmentContentReceipt
    environment_inventory_sha256: str
    external_runtime_closure_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "LiveEnvironmentRehashFact":
        del cls
        raise TypeError("LiveEnvironmentRehashFact must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("LiveEnvironmentRehashFact is final")

    @classmethod
    def _from_observed(
        cls,
        *,
        phase: str,
        environment_root: Path,
        content_receipt: WarehouseEnvironmentContentReceipt,
        observed_generic_receipt: EnvironmentContentReceipt,
    ) -> "LiveEnvironmentRehashFact":
        if phase not in _LIVE_PHASES:
            raise WarehouseW3EnvironmentReceiptError("live rehash phase differs")
        content_receipt = _validated_content(content_receipt)
        observed = _validated_generic(observed_generic_receipt)
        value = {
            "schema": _LIVE_REHASH_SCHEMA,
            "phase": phase,
            "content_receipt_sha256": content_receipt.raw_sha256,
            "generic_receipt_sha256": observed.raw_sha256,
            "environment_root": _absolute_path(
                str(environment_root),
                field="live rehash environment root",
            ),
            "observed_generic_receipt": observed.to_mapping(),
            "environment_inventory_sha256": _inventory_sha256(observed),
            "external_runtime_closure_sha256": _external_runtime_sha256(observed),
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "LiveEnvironmentRehashFact":
        value = _exact_fields(
            _decode_canonical(raw, label="live environment rehash fact"),
            frozenset(
                {
                    "schema",
                    "phase",
                    "content_receipt_sha256",
                    "generic_receipt_sha256",
                    "environment_root",
                    "observed_generic_receipt",
                    "environment_inventory_sha256",
                    "external_runtime_closure_sha256",
                }
            ),
            label="live environment rehash fact",
        )
        phase = value["phase"]
        if value["schema"] != _LIVE_REHASH_SCHEMA or phase not in _LIVE_PHASES:
            raise WarehouseW3EnvironmentReceiptError(
                "live environment rehash schema or phase differs"
            )
        observed = EnvironmentContentReceipt.from_bytes(
            _canonical_json(value["observed_generic_receipt"])
        )
        if (
            value["generic_receipt_sha256"] != observed.raw_sha256
            or value["environment_inventory_sha256"] != _inventory_sha256(observed)
            or value["external_runtime_closure_sha256"]
            != _external_runtime_sha256(observed)
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "live rehash observed receipt closure differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("phase", phase),
            (
                "content_receipt_sha256",
                _sha256(
                    value["content_receipt_sha256"],
                    field="content_receipt_sha256",
                ),
            ),
            (
                "generic_receipt_sha256",
                _sha256(
                    value["generic_receipt_sha256"],
                    field="generic_receipt_sha256",
                ),
            ),
            (
                "environment_root",
                _absolute_path(
                    value["environment_root"],
                    field="live rehash environment_root",
                ),
            ),
            ("observed_generic_receipt", observed),
            (
                "environment_inventory_sha256",
                _sha256(
                    value["environment_inventory_sha256"],
                    field="environment_inventory_sha256",
                ),
            ),
            (
                "external_runtime_closure_sha256",
                _sha256(
                    value["external_runtime_closure_sha256"],
                    field="external_runtime_closure_sha256",
                ),
            ),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True)
class FilesystemLiveEnvironmentReader:
    """Read-only concrete producer for complete live environment observations."""

    external_runtime_paths: tuple[Path, ...]
    candidate_root: Path
    selection_root: Path

    def __post_init__(self) -> None:
        if (
            type(self.external_runtime_paths) is not tuple
            or not self.external_runtime_paths
            or any(not isinstance(path, Path) for path in self.external_runtime_paths)
        ):
            raise TypeError("external_runtime_paths must be one nonempty Path tuple")
        if not isinstance(self.candidate_root, Path) or not isinstance(
            self.selection_root,
            Path,
        ):
            raise TypeError("candidate_root and selection_root must be exact Paths")
        for path in (
            *self.external_runtime_paths,
            self.candidate_root,
            self.selection_root,
        ):
            _absolute_path(str(path), field="live reader path")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("FilesystemLiveEnvironmentReader is final")

    def rehash(
        self,
        environment_root: Path,
        *,
        phase: str,
        content_receipt: WarehouseEnvironmentContentReceipt,
        generic_receipt: EnvironmentContentReceipt,
    ) -> LiveEnvironmentRehashFact:
        content = _validated_content(content_receipt)
        generic = _validated_generic(generic_receipt)
        if generic != content.generic_receipt:
            raise WarehouseW3EnvironmentReceiptError(
                "live reader generic receipt differs from semantic content"
            )
        verify_environment_content(
            environment_root,
            generic,
            external_runtime_paths=self.external_runtime_paths,
            candidate_root=self.candidate_root,
            selection_root=self.selection_root,
        )
        observed = EnvironmentContentReceipt.create(
            environment_root,
            external_runtime_paths=self.external_runtime_paths,
            candidate_root=self.candidate_root,
            selection_root=self.selection_root,
        )
        if observed != generic:
            raise WarehouseW3EnvironmentReceiptError(
                "live environment changed after complete verification"
            )
        return LiveEnvironmentRehashFact._from_observed(
            phase=phase,
            environment_root=environment_root,
            content_receipt=content,
            observed_generic_receipt=observed,
        )


def _validate_live_rehash(
    fact: LiveEnvironmentRehashFact,
    *,
    phase: str,
    content: WarehouseEnvironmentContentReceipt,
    expected_root: Path | None = None,
) -> None:
    if type(fact) is not LiveEnvironmentRehashFact:
        raise WarehouseW3EnvironmentReceiptError(
            "live reader returned an inexact rehash fact type"
        )
    if LiveEnvironmentRehashFact.from_bytes(fact.raw) != fact:
        raise WarehouseW3EnvironmentReceiptError("live rehash fact object differs")
    expected_path = str(
        derive_final_environment_path(content)
        if expected_root is None
        else expected_root
    )
    if (
        fact.phase != phase
        or fact.content_receipt_sha256 != content.raw_sha256
        or fact.generic_receipt_sha256 != content.generic_receipt_sha256
        or fact.observed_generic_receipt != content.generic_receipt
        or fact.environment_root != expected_path
        or fact.environment_inventory_sha256 != content.environment_inventory_sha256
        or fact.external_runtime_closure_sha256
        != content.external_runtime_closure_sha256
    ):
        raise WarehouseW3EnvironmentReceiptError(
            f"{phase} live environment rehash is not cross-bound"
        )


@dataclass(frozen=True, slots=True, init=False)
class EnvironmentRelocationReceipt:
    content_receipt_sha256: str
    final_environment_path: str
    imported_candidate_environment_path: str
    candidate_probe: EnvironmentProbeFact
    namespace_final_probe: EnvironmentProbeFact
    namespace_probe_execution: NamespaceProbeExecutionFact
    imported_candidate_rehash: LiveEnvironmentRehashFact
    relocation_pre_rehash: LiveEnvironmentRehashFact
    relocation_post_rehash: LiveEnvironmentRehashFact
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "EnvironmentRelocationReceipt":
        del cls
        raise TypeError("EnvironmentRelocationReceipt must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("EnvironmentRelocationReceipt is final")

    @classmethod
    def create(
        cls,
        content_receipt: WarehouseEnvironmentContentReceipt,
        *,
        candidate_probe: EnvironmentProbeFact,
        namespace_final_probe: EnvironmentProbeFact,
        namespace_probe_execution: NamespaceProbeExecutionFact,
        imported_candidate_rehash: LiveEnvironmentRehashFact,
        relocation_pre_rehash: LiveEnvironmentRehashFact,
        relocation_post_rehash: LiveEnvironmentRehashFact,
    ) -> "EnvironmentRelocationReceipt":
        content_receipt = _validated_content(content_receipt)
        candidate_root = Path(candidate_probe.environment_root)
        namespace_root = Path(namespace_final_probe.environment_root)
        imported_root = Path(imported_candidate_rehash.environment_root)
        final_root = derive_final_environment_path(content_receipt)
        if (
            candidate_root.name != "environment"
            or candidate_root == final_root
            or namespace_root != final_root
            or imported_root.name != "environment"
            or imported_root in {candidate_root, final_root}
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "candidate, imported, or namespace-final environment path differs"
            )
        _validate_probe(
            candidate_probe,
            phase="candidate",
            root=candidate_root,
            content=content_receipt,
        )
        _validate_probe(
            namespace_final_probe,
            phase="namespace_final",
            root=final_root,
            content=content_receipt,
        )
        namespace_execution = NamespaceProbeExecutionFact.from_bytes(
            namespace_probe_execution.raw,
            environment_probe=namespace_final_probe,
        )
        if namespace_execution != namespace_probe_execution:
            raise WarehouseW3EnvironmentReceiptError(
                "namespace probe execution object differs"
            )
        _validate_relocation_probe_equivalence(
            candidate_probe,
            namespace_final_probe,
            content=content_receipt,
        )
        _validate_live_rehash(
            imported_candidate_rehash,
            phase="imported_candidate",
            content=content_receipt,
            expected_root=imported_root,
        )
        _validate_live_rehash(
            relocation_pre_rehash,
            phase="relocation_pre",
            content=content_receipt,
        )
        _validate_live_rehash(
            relocation_post_rehash,
            phase="relocation_post",
            content=content_receipt,
        )
        value = {
            "schema": _RELOCATION_SCHEMA,
            "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "content_receipt_sha256": content_receipt.raw_sha256,
            "final_environment_path": str(final_root),
            "imported_candidate_environment_path": str(imported_root),
            "candidate_probe": json.loads(candidate_probe.raw),
            "namespace_final_probe": json.loads(namespace_final_probe.raw),
            "namespace_probe_execution": json.loads(namespace_probe_execution.raw),
            "imported_candidate_rehash": json.loads(imported_candidate_rehash.raw),
            "relocation_pre_rehash": json.loads(relocation_pre_rehash.raw),
            "relocation_post_rehash": json.loads(relocation_post_rehash.raw),
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(_canonical_json(value), content_receipt=content_receipt)

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        content_receipt: WarehouseEnvironmentContentReceipt,
    ) -> "EnvironmentRelocationReceipt":
        content_receipt = _validated_content(content_receipt)
        value = _exact_fields(
            _decode_canonical(raw, label="environment relocation receipt"),
            frozenset(
                {
                    "schema",
                    "plan_sha256",
                    "content_receipt_sha256",
                    "final_environment_path",
                    "imported_candidate_environment_path",
                    "candidate_probe",
                    "namespace_final_probe",
                    "namespace_probe_execution",
                    "imported_candidate_rehash",
                    "relocation_pre_rehash",
                    "relocation_post_rehash",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="environment relocation receipt",
        )
        if (
            value["schema"] != _RELOCATION_SCHEMA
            or value["plan_sha256"] != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "environment relocation plan or schema differs"
            )
        _false_controls(value, label="environment relocation receipt")

        def nested_bytes(field: str) -> bytes:
            return _canonical_json(value[field])

        candidate = EnvironmentProbeFact.from_bytes(nested_bytes("candidate_probe"))
        namespace_final = EnvironmentProbeFact.from_bytes(
            nested_bytes("namespace_final_probe")
        )
        namespace_execution = NamespaceProbeExecutionFact.from_bytes(
            nested_bytes("namespace_probe_execution"),
            environment_probe=namespace_final,
        )
        imported = LiveEnvironmentRehashFact.from_bytes(
            nested_bytes("imported_candidate_rehash")
        )
        pre = LiveEnvironmentRehashFact.from_bytes(
            nested_bytes("relocation_pre_rehash")
        )
        post = LiveEnvironmentRehashFact.from_bytes(
            nested_bytes("relocation_post_rehash")
        )
        expected_final = str(derive_final_environment_path(content_receipt))
        imported_path = _absolute_path(
            value["imported_candidate_environment_path"],
            field="imported candidate environment path",
        )
        if (
            value["content_receipt_sha256"] != content_receipt.raw_sha256
            or value["final_environment_path"] != expected_final
            or Path(candidate.environment_root).name != "environment"
            or candidate.environment_root == expected_final
            or namespace_final.environment_root != expected_final
            or Path(imported_path).name != "environment"
            or imported_path in {candidate.environment_root, expected_final}
        ):
            raise WarehouseW3EnvironmentReceiptError(
                "environment relocation content or path binding differs"
            )
        _validate_probe(
            candidate,
            phase="candidate",
            root=Path(candidate.environment_root),
            content=content_receipt,
        )
        _validate_probe(
            namespace_final,
            phase="namespace_final",
            root=Path(expected_final),
            content=content_receipt,
        )
        _validate_relocation_probe_equivalence(
            candidate,
            namespace_final,
            content=content_receipt,
        )
        _validate_live_rehash(
            imported,
            phase="imported_candidate",
            content=content_receipt,
            expected_root=Path(imported_path),
        )
        _validate_live_rehash(pre, phase="relocation_pre", content=content_receipt)
        _validate_live_rehash(post, phase="relocation_post", content=content_receipt)
        instance = object.__new__(cls)
        for field, item in (
            ("content_receipt_sha256", content_receipt.raw_sha256),
            ("final_environment_path", expected_final),
            ("imported_candidate_environment_path", imported_path),
            ("candidate_probe", candidate),
            ("namespace_final_probe", namespace_final),
            ("namespace_probe_execution", namespace_execution),
            ("imported_candidate_rehash", imported),
            ("relocation_pre_rehash", pre),
            ("relocation_post_rehash", post),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


def verify_live_environment(
    content_receipt: WarehouseEnvironmentContentReceipt,
    *,
    phase: str,
    live_reader: FilesystemLiveEnvironmentReader,
) -> LiveEnvironmentRehashFact:
    """Runtime hook for the exact preclaim and completion rehash gates."""

    content_receipt = _validated_content(content_receipt)
    if phase not in {"preclaim", "completion"}:
        raise WarehouseW3EnvironmentReceiptError("runtime live-rehash phase differs")
    method = getattr(live_reader, "rehash", None)
    if not callable(method):
        raise TypeError("live_reader lacks rehash")
    if type(live_reader) is not FilesystemLiveEnvironmentReader:
        raise TypeError("live_reader must be exact FilesystemLiveEnvironmentReader")
    fact = method(
        derive_final_environment_path(content_receipt),
        phase=phase,
        content_receipt=content_receipt,
        generic_receipt=content_receipt.generic_receipt,
    )
    _validate_live_rehash(fact, phase=phase, content=content_receipt)
    return fact


__all__ = [
    "ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256",
    "DbusProvenance",
    "EnvironmentProbeFact",
    "EnvironmentProbeReader",
    "EnvironmentRelocationReceipt",
    "EnvironmentSemanticReader",
    "FINAL_ENVIRONMENT_PARENT",
    "FilesystemEnvironmentSemanticReader",
    "FilesystemLiveEnvironmentReader",
    "ImportIdentity",
    "InstalledWheelMember",
    "LiveEnvironmentRehashFact",
    "NamespaceProbeExecutionFact",
    "NativeElfIdentity",
    "NonRootNamespaceEnvironmentProbeReader",
    "SubprocessEnvironmentProbeReader",
    "WarehouseEnvironmentContentReceipt",
    "WarehouseEnvironmentEvidence",
    "WarehouseW3EnvironmentReceiptError",
    "WheelInstallationProvenance",
    "acquire_warehouse_environment_content",
    "acquire_warehouse_environment_content_for_test",
    "discover_environment_external_runtime_paths",
    "derive_final_environment_path",
    "validate_environment_probe_fact",
    "verify_live_environment",
    "verify_namespace_probe_execution_binary",
]
