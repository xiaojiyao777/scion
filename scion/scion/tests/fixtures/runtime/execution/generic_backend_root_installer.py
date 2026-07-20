#!/usr/bin/env python3
"""Root-only infrastructure transactions for generic-backend formal roots.

The transactions are deliberately separate and one-way: prepare the tree,
seal already-authored static inputs, install preflighted concrete units,
authorize one explicit H11 operator release, freeze the closed evidence
inventory, and (only when explicitly requested) remove the installed fragments.
A failed mutating transaction is retained as poisoned evidence; this module
never rolls it back, retries it, or launches a unit.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import Enum
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import select
import stat
import sys
from typing import Any, Callable, NoReturn, Protocol, TypeAlias, Union


PREPARE_SCHEMA = "scion.generic_backend.root_prepare.v1"
SEAL_SCHEMA = "scion.generic_backend.root_seal.v1"
INSTALL_SCHEMA = "scion.generic_backend.root_install.v1"
FREEZE_SCHEMA = "scion.generic_backend.root_final_freeze.v1"
CLEANUP_SCHEMA = "scion.generic_backend.root_cleanup.v1"
TREE_RECEIPT_SCHEMA = "scion.generic_backend.root_tree_receipt.v1"
SEAL_RECEIPT_SCHEMA = "scion.generic_backend.root_seal_receipt.v1"
PREFLIGHT_RECEIPT_SCHEMA = "scion.generic_backend.static_preflight_receipt.v1"
INSTALL_RECEIPT_SCHEMA = "scion.generic_backend.root_install_receipt.v1"
FREEZE_RECEIPT_SCHEMA = "scion.generic_backend.root_final_freeze_receipt.v1"
CLEANUP_RECEIPT_SCHEMA = "scion.generic_backend.root_cleanup_receipt.v1"
PREFLIGHT_MANIFEST_SCHEMA = "scion.generic_backend.static_preflight.v1"
HARNESS_RECEIPT_SCHEMA = "scion.generic_backend.systemd_harness_receipt.v1"
H11_AUTHORIZATION_SCHEMA = "scion.generic_backend.h11_release_authorization.v1"
H11_PERMIT_READY_SCHEMA = "scion.generic_backend.h11_permit_ready.v1"
H11_PERMIT_AUTHORITY_SCHEMA = (
    "scion.generic_backend.h11_operator_permit_authority.v1"
)
H11_PERMIT_SCHEMA = "scion.generic_backend.h11_operator_permit.v1"
H11_COMMIT_FIFO_RECEIPT_SCHEMA = (
    "scion.generic_backend.h11_commit_fifo_receipt.v1"
)
H11_READY_BYTES = b"SCION_GENERIC_BACKEND_READY_V1\n"
H11_RELEASE_BYTES = b"SCION_GENERIC_BACKEND_RELEASE_V1\n"
H11_READY_COMMITTED_BYTES = b"SCION_H11_READY_COMMITTED_V1\n"
H11_PERMIT_COMMITTED_BYTES = b"SCION_H11_PERMIT_COMMITTED_V1\n"

_UNIT_RE = re.compile(r"scion-w3-[A-Za-z0-9_.:-]+\.service\Z")
_ROLE_RE = re.compile(r"[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*\Z")
_HEX_RE = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_ABSOLUTE_RE = re.compile(r"/[A-Za-z0-9_./:+-]+\Z")
_UNIQUE_OWNER_RE = re.compile(
    r":(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z"
)
_DESCRIPTION_SUFFIX_RE = re.compile(r"[A-Za-z0-9_.:/+-]+\Z")
_MODE_RE = re.compile(r"0[0-7]{3}\Z")
_INVOCATION_RE = re.compile(r"[0-9a-f]{32}\Z")
_BOOT_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_AT_EMPTY_PATH = 0x1000
_ASSET_KINDS = frozenset(
    {
        "unit-fragment",
        "python-program",
        "json-plan",
        "start-descriptor",
        "installer-program",
        "harness-program",
        "static-input",
    }
)
_FIFO_OWNERS = frozenset({"fixture", "root"})
_H11_COMMIT_FIFO_NAMES = {
    "h11-permit-commit": "h11-permit-committed.fifo",
    "h11-ready-commit": "h11-ready-committed.fifo",
}
_H11_HARNESS_MANIFEST_KEYS = {
    "schema",
    "scenario",
    "descriptor",
    "installer_receipt",
    "harness_program",
    "run_unit",
    "closer_unit",
    "boot_id_file",
    "input_root",
    "receipt_root",
    "acquisitions",
    "outputs",
    "scenario_input",
    "formal_actions",
    "preflight_receipt",
    "static_inventory",
    "static_roles",
    "permit_authority",
}
_H11_PERMIT_AUTHORITY_KEYS = {
    "schema",
    "scenario",
    "run_unit",
    "permit_path",
    "permit_parent",
    "permit_ready_path",
    "permit_ledger_path",
    "permit_ready_staging_path",
    "permit_staging_path",
    "permit_ledger_staging_path",
    "directory_chain",
    "ready_commit_fifo",
    "permit_commit_fifo",
    "present_prerequisite_roles",
    "future_absence_inventory",
}
_H11_OUTPUT_ROLES = frozenset(
    {
        "closer-properties",
        "exec-stop-post-properties",
        "final",
        "final-closer-properties",
        "final-run-properties",
        "h0",
        "h12-absence",
        "journal",
        "manager-events",
        "run-main-properties",
        "signals",
        "source-selector",
    }
)
_H11_PRESENT_ROLES = ("h0", "run-main-properties")
_H11_DIRECTORY_LAYOUT = (
    ("formal-root", 0o711),
    ("authority-root", 0o700),
    ("harness-root", 0o700),
    ("scenario-root", 0o700),
    ("input-root", 0o555),
    ("receipt-root", 0o555),
    ("fifo-root", 0o711),
)
_H11_TRANSACTION_LAYOUT = (
    ("authorization", "AUTHORIZE-RELEASE.json"),
    ("permit-ready-staging", "PERMIT_READY.pending"),
    ("permit-ready", "PERMIT_READY.json"),
    ("permit-staging", "PERMIT.pending"),
    ("permit", "PERMIT.json"),
    ("permit-ledger-staging", "PERMIT-LEDGER.pending"),
    ("permit-ledger", "PERMIT-LEDGER.json"),
)
_H11_TRANSACTION_PHASES = {
    "pre-start": ("absent",) * 7,
    "ready-visible": (
        "absent", "absent", "present", "absent", "absent", "absent", "absent"
    ),
    "authorizer-input": (
        "present", "absent", "present", "absent", "absent", "absent", "absent"
    ),
    "permit-committed": (
        "present", "absent", "present", "absent", "present", "absent", "absent"
    ),
    "ledger-committed": (
        "present", "absent", "present", "absent", "present", "absent", "present"
    ),
}
_H11_PUBLICATION_PAIRS = {
    "PERMIT_READY.pending": "PERMIT_READY.json",
    "PERMIT.pending": "PERMIT.json",
    "PERMIT-LEDGER.pending": "PERMIT-LEDGER.json",
}
_H11_PUBLICATION_TEST_FAILURES = frozenset(
    {"pre-rename"}
)
_H11_AUTHORIZATION_KEYS = {
    "schema",
    "formal_root",
    "harness_manifest",
    "permit_ready",
    "run_armed",
    "permit_path",
}
_H11_READY_KEYS = {
    "schema",
    "scenario",
    "run_unit",
    "boot_id",
    "invocation_id",
    "harness_manifest",
    "run_armed",
    "permit_authority",
    "present_outputs",
    "absent_paths",
    "phase",
}
_H11_ADVERSARY_ARMED_KEYS = {
    "schema",
    "scenario",
    "unit",
    "actor",
    "plan_path",
    "plan_sha256",
    "program",
    "request_path",
    "request_sha256",
    "receipt_path",
    "ready_fifo",
    "release_fifo",
    "ready_sha256",
    "release_sha256",
}
_H11_ADVERSARY_ACTOR_KEYS = {
    "boot_id",
    "invocation_id",
    "pid",
    "proc_cgroup_raw",
    "session_id",
    "starttime",
    "stop_selector_environment",
    "unified_cgroup",
}
_H11_ACQUISITION_ROLES = ("run-main", "exec-stop-post", "closer")
_H11_STATIC_ROLE_KEYS = {"role", "unit", "owner", "mode", "plan", "program"}
_H11_HASHED_PATH_KEYS = {"path", "sha256"}
_H11_ARMED_PROGRAM_KEYS = {"path", "sha256", "identity"}
_H11_ARMED_PROGRAM_IDENTITY_KEYS = {"device", "inode", "mode"}


class InstallerError(RuntimeError):
    """The root installation contract could not be proved."""


class Manager(Protocol):
    owner: str

    def reload(self) -> None: ...

    def load_unit(self, unit: str) -> str: ...

    def unit_property(self, object_path: str, interface: str, name: str) -> Any: ...


def _fail(message: str) -> NoReturn:
    raise InstallerError(message)


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail(f"forbidden JSON constant {value!r}")


def _canonical(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise InstallerError("value is not canonical JSON") from exc


def _decode(path: Path) -> dict[str, Any]:
    raw = _read_regular(path, label="manifest")
    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_constant,
        )
    except InstallerError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InstallerError("manifest is not strict UTF-8 JSON") from exc
    if type(value) is not dict or _canonical(value) != raw:
        _fail("manifest must be one exact canonical JSON object")
    return value


def _exact(value: dict[str, Any], keys: set[str], *, label: str) -> None:
    actual = set(value)
    if actual != keys:
        _fail(
            f"{label} keys mismatch: missing={sorted(keys - actual)!r}, "
            f"unknown={sorted(actual - keys)!r}"
        )


def _text(value: Any, *, label: str) -> str:
    if type(value) is not str or not value or any(ord(ch) < 0x20 for ch in value):
        _fail(f"{label} must be one nonempty control-free string")
    return value


def _path(value: Any, *, label: str) -> Path:
    raw = _text(value, label=label)
    result = Path(raw)
    if not result.is_absolute() or str(result) != raw or any(
        part in {".", ".."} for part in result.parts
    ):
        _fail(f"{label} must be one normalized absolute path")
    return result


def _uint(value: Any, *, label: str) -> int:
    if type(value) is not str or not re.fullmatch(r"0|[1-9][0-9]*", value):
        _fail(f"{label} must be canonical unsigned decimal text")
    result = int(value, 10)
    if result > (1 << 64) - 1:
        _fail(f"{label} exceeds uint64")
    return result


def _read_regular(path: Path, *, label: str) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        raise InstallerError(f"cannot stat {label}: {path}") from exc
    if not stat.S_ISREG(before.st_mode):
        _fail(f"{label} must be a non-symlink regular file: {path}")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                _fail(f"{label} identity changed while opening")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            raw = b"".join(chunks)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
    except InstallerError:
        raise
    except OSError as exc:
        raise InstallerError(f"cannot read {label}: {path}") from exc
    if (
        (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
        or after.st_size != len(raw)
        or after.st_mtime_ns != before.st_mtime_ns
    ):
        _fail(f"{label} changed while being read")
    try:
        final = path.lstat()
    except OSError as exc:
        raise InstallerError(f"{label} disappeared after being read: {path}") from exc
    if (
        (final.st_dev, final.st_ino) != (before.st_dev, before.st_ino)
        or final.st_size != before.st_size
        or final.st_mtime_ns != before.st_mtime_ns
    ):
        _fail(f"{label} path identity changed while being read")
    return raw


def _write_no_replace(path: Path, value: Any, *, mode: int) -> None:
    raw = _canonical(value)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, mode)
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    _fail("receipt write made no progress")
                view = view[written:]
            os.fchmod(descriptor, mode)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _fsync_directory(path.parent)
    except InstallerError:
        raise
    except OSError as exc:
        raise InstallerError(f"cannot publish no-replace receipt: {path}") from exc


def _write_bytes_no_replace(path: Path, raw: bytes, *, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, mode)
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    _fail("file write made no progress")
                view = view[written:]
            os.fchmod(descriptor, mode)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _fsync_directory(path.parent)
    except InstallerError:
        raise
    except OSError as exc:
        raise InstallerError(f"cannot publish no-replace file: {path}") from exc


def _publish_unnamed_no_replace(
    descriptor: int,
    *,
    directory_descriptor: int,
    name: str,
) -> None:
    """Link one complete ``O_TMPFILE`` inode into a directory exactly once."""

    if name != "FROZEN":
        _fail("unnamed publication is reserved for the exact FROZEN marker")
    libc = ctypes.CDLL(None, use_errno=True)
    linkat = libc.linkat
    linkat.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    linkat.restype = ctypes.c_int
    ctypes.set_errno(0)
    if (
        linkat(
            descriptor,
            b"",
            directory_descriptor,
            name.encode("ascii"),
            _AT_EMPTY_PATH,
        )
        != 0
    ):
        error = ctypes.get_errno()
        raise InstallerError(
            f"cannot publish no-replace FROZEN marker: {os.strerror(error)}"
        )


def _identity(path: Path) -> dict[str, str]:
    info = path.lstat()
    return {"path": str(path), "device": str(info.st_dev), "inode": str(info.st_ino)}


def _directory_reference(path: Path, *, mode: int | None = None) -> dict[str, str]:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        _fail(f"directory reference is not an exact directory: {path}")
    return {
        **_identity(path),
        "uid": str(info.st_uid),
        "gid": str(info.st_gid),
        "mode": format(stat.S_IMODE(info.st_mode) if mode is None else mode, "04o"),
    }


def _fifo_reference(
    path: Path,
    *,
    role: str,
    owner: str,
    uid: int,
    gid: int,
    allow_test_root_owner: bool = False,
) -> dict[str, str]:
    info = path.lstat()
    if (
        not stat.S_ISFIFO(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o600
        or (
            (info.st_uid, info.st_gid) != (uid, gid)
            and not (
                allow_test_root_owner
                and owner == "root"
                and (info.st_uid, info.st_gid) == (os.geteuid(), os.getegid())
            )
        )
    ):
        _fail(f"FIFO reference is not one exact 0600 FIFO: {path}")
    return {
        "role": role,
        "path": str(path),
        "owner": owner,
        "uid": str(uid),
        "gid": str(gid),
        "mode": "0600",
        "device": str(info.st_dev),
        "inode": str(info.st_ino),
    }


def _decode_fifo_specs(
    value: Any,
    *,
    root: Path,
    label: str,
) -> list[tuple[str, Path, str]]:
    if type(value) is not list or not value:
        _fail(f"{label} must be one nonempty FIFO array")
    result: list[tuple[str, Path, str]] = []
    seen_roles: set[str] = set()
    seen_paths: set[Path] = set()
    for ordinal, item in enumerate(value):
        if type(item) is not dict:
            _fail(f"{label}[{ordinal}] must be one object")
        _exact(item, {"role", "path", "owner"}, label=f"{label}[{ordinal}]")
        role = _text(item["role"], label=f"{label}[{ordinal}].role")
        path = _path(item["path"], label=f"{label}[{ordinal}].path")
        owner = _text(item["owner"], label=f"{label}[{ordinal}].owner")
        if (
            _ROLE_RE.fullmatch(role) is None
            or owner not in _FIFO_OWNERS
            or role in seen_roles
            or path in seen_paths
            or path.parent != root / "fifo"
        ):
            _fail(f"{label} role/path/owner is invalid, duplicated or misplaced")
        reserved_name = _H11_COMMIT_FIFO_NAMES.get(role)
        if reserved_name is None:
            if owner != "fixture":
                _fail(f"{label} ordinary FIFO must be fixture-owned")
        elif owner != "root" or path != root / "fifo" / reserved_name:
            _fail(f"{label} H11 commit FIFO path/owner drifted")
        seen_roles.add(role)
        seen_paths.add(path)
        result.append((role, path, owner))
    roles = [role for role, _path_value, _owner in result]
    if roles != sorted(roles):
        _fail(f"{label} is not sorted canonically by role")
    if not set(_H11_COMMIT_FIFO_NAMES).issubset(seen_roles):
        _fail(f"{label} lacks the exact H11 commit FIFO pair")
    return result


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _pin_canonical_directory(
    path: Path,
    *,
    expected_mode: int,
    require_root: bool,
    label: str,
) -> int:
    """Open one exact directory and reject symlink or metadata drift."""

    try:
        before = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise InstallerError(f"cannot stat {label}: {path}") from exc
    if (
        resolved != path
        or not stat.S_ISDIR(before.st_mode)
        or stat.S_IMODE(before.st_mode) != expected_mode
        or (require_root and (before.st_uid != 0 or before.st_gid != 0))
    ):
        _fail(f"{label} is not one canonical directory with exact metadata")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise InstallerError(f"cannot pin {label}: {path}") from exc
    try:
        opened = os.fstat(descriptor)
        current = path.lstat()
        expected_identity = (before.st_dev, before.st_ino)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != expected_identity
            or (current.st_dev, current.st_ino) != expected_identity
            or stat.S_IMODE(opened.st_mode) != expected_mode
            or stat.S_IMODE(current.st_mode) != expected_mode
            or (opened.st_uid, opened.st_gid) != (before.st_uid, before.st_gid)
            or (current.st_uid, current.st_gid) != (before.st_uid, before.st_gid)
        ):
            _fail(f"{label} identity or metadata drifted while pinning")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _fsync_regular(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            _fail(f"fsync target is not an exact regular file: {path}")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _require_absent(path: Path, *, label: str) -> None:
    if path.exists() or path.is_symlink():
        _fail(f"{label} already exists: {path}")


def _file_reference(path: Path, raw: bytes | None = None) -> dict[str, str]:
    payload = _read_regular(path, label="referenced file") if raw is None else raw
    return {**_identity(path), "sha256": hashlib.sha256(payload).hexdigest()}


def _asset_reference(path: Path, raw: bytes | None = None) -> dict[str, str]:
    result = _file_reference(path, raw)
    result["mode"] = format(stat.S_IMODE(path.lstat().st_mode), "04o")
    return result


def _manifest_reference(path: Path) -> dict[str, str]:
    return _file_reference(path, _read_regular(path, label="transaction manifest"))


def _bound_json_input(
    value: Any, *, label: str
) -> tuple[Path, dict[str, Any], bytes]:
    if type(value) is not dict:
        _fail(f"{label} must be one exact identity-bound input")
    _exact(value, {"path", "sha256", "device", "inode"}, label=label)
    path = _path(value["path"], label=f"{label}.path")
    expected = _text(value["sha256"], label=f"{label}.sha256")
    if _HEX_RE.fullmatch(expected) is None:
        _fail(f"{label}.sha256 is not canonical")
    device = _uint(value["device"], label=f"{label}.device")
    inode = _uint(value["inode"], label=f"{label}.inode")
    before = path.lstat()
    if (before.st_dev, before.st_ino) != (device, inode):
        _fail(f"{label} path identity differs from its frozen binding")
    raw = _read_regular(path, label=label)
    if hashlib.sha256(raw).hexdigest() != expected:
        _fail(f"{label} SHA-256 drifted")
    try:
        decoded = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_constant,
        )
    except InstallerError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InstallerError(f"{label} is not JSON") from exc
    if type(decoded) is not dict or _canonical(decoded) != raw:
        _fail(f"{label} is not canonical JSON")
    return path, decoded, raw


def _bound_reference(value: Any, *, label: str) -> dict[str, str]:
    path, _decoded, raw = _bound_json_input(value, label=label)
    return _file_reference(path, raw)


def _validate_directory_identity(
    value: Any,
    *,
    expected_path: Path,
    expected_mode: int,
    label: str,
) -> None:
    if type(value) is not dict:
        _fail(f"{label} must be one directory identity")
    _exact(value, {"path", "device", "inode"}, label=label)
    if _path(value["path"], label=f"{label}.path") != expected_path:
        _fail(f"{label} path differs from the formal root layout")
    info = expected_path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        _fail(f"{label} is not a directory")
    if (str(info.st_dev), str(info.st_ino)) != (value["device"], value["inode"]):
        _fail(f"{label} identity drifted")
    if stat.S_IMODE(info.st_mode) != expected_mode:
        _fail(f"{label} mode drifted")


def _validate_tree_receipt(
    receipt: dict[str, Any],
    *,
    root: Path,
    receipt_path: Path,
    require_root: bool,
    sealed: bool = False,
) -> tuple[str, str, int, int, list[dict[str, str]]]:
    _exact(
        receipt,
        {
            "schema",
            "formal_root",
            "sealed_root",
            "input_root",
            "work_root",
            "fifo_root",
            "authority_root",
            "fixture_user",
            "fixture_group",
            "fixture_uid",
            "fixture_gid",
            "fifos",
            "prepare_manifest",
            "phase",
        },
        label="tree receipt",
    )
    if receipt["schema"] != TREE_RECEIPT_SCHEMA or receipt["phase"] != "tree-prepared":
        _fail("tree receipt schema/phase is not supported")
    _prepare_path, prepare_manifest, _prepare_raw = _bound_json_input(
        receipt["prepare_manifest"], label="tree prepare_manifest"
    )
    if (
        prepare_manifest.get("schema") != PREPARE_SCHEMA
        or prepare_manifest.get("formal_root") != str(root)
    ):
        _fail("tree prepare manifest does not bind this formal root")
    _exact(
        prepare_manifest,
        {
            "schema",
            "formal_root",
            "fixture_user",
            "fixture_group",
            "fifos",
            "receipt_path",
        },
        label="tree prepare manifest",
    )
    root_mode = 0o711
    sealed_mode = 0o555 if sealed else 0o755
    input_mode = 0o555 if sealed else 0o755
    _validate_directory_identity(
        receipt["formal_root"], expected_path=root, expected_mode=root_mode, label="formal root"
    )
    _validate_directory_identity(
        receipt["sealed_root"],
        expected_path=root / "sealed",
        expected_mode=sealed_mode,
        label="sealed root",
    )
    _validate_directory_identity(
        receipt["input_root"],
        expected_path=root / "input",
        expected_mode=input_mode,
        label="input root",
    )
    _validate_directory_identity(
        receipt["work_root"],
        expected_path=root / "work",
        expected_mode=0o700,
        label="work root",
    )
    _validate_directory_identity(
        receipt["fifo_root"],
        expected_path=root / "fifo",
        expected_mode=0o711,
        label="fifo root",
    )
    _validate_directory_identity(
        receipt["authority_root"],
        expected_path=root / "authority",
        expected_mode=0o700,
        label="authority root",
    )
    user = _text(receipt["fixture_user"], label="tree fixture_user")
    group = _text(receipt["fixture_group"], label="tree fixture_group")
    uid = _uint(receipt["fixture_uid"], label="tree fixture_uid")
    gid = _uint(receipt["fixture_gid"], label="tree fixture_gid")
    if uid == 0:
        _fail("tree fixture user must not be root")
    if (
        prepare_manifest["fixture_user"] != user
        or prepare_manifest["fixture_group"] != group
        or _path(
            prepare_manifest["receipt_path"],
            label="tree prepare manifest.receipt_path",
        )
        != receipt_path
    ):
        _fail("tree receipt identity/destination differs from its prepare manifest")
    work_info = (root / "work").lstat()
    if (work_info.st_uid, work_info.st_gid) != (uid, gid):
        _fail("tree work root fixture ownership drifted")
    if require_root:
        for path in (root, root / "sealed", root / "input", root / "fifo", root / "authority"):
            info = path.lstat()
            if info.st_uid != 0 or info.st_gid != 0:
                _fail(f"root-owned formal tree directory drifted: {path}")
    fifos = receipt["fifos"]
    if type(fifos) is not list or not fifos:
        _fail("tree receipt FIFO inventory is empty")
    prepare_specs = _decode_fifo_specs(
        prepare_manifest["fifos"], root=root, label="tree prepare_manifest.fifos"
    )
    seen_roles: set[str] = set()
    seen_identities: set[tuple[str, str]] = set()
    validated_fifos: list[dict[str, str]] = []
    for ordinal, item in enumerate(fifos):
        if type(item) is not dict:
            _fail(f"tree receipt fifos[{ordinal}] must be one object")
        _exact(
            item,
            {"role", "path", "owner", "uid", "gid", "mode", "device", "inode"},
            label=f"tree receipt fifos[{ordinal}]",
        )
        role = _text(item["role"], label=f"tree receipt fifos[{ordinal}].role")
        path = _path(item["path"], label=f"tree receipt fifos[{ordinal}].path")
        owner = _text(item["owner"], label=f"tree receipt fifos[{ordinal}].owner")
        item_uid = _uint(item["uid"], label=f"tree receipt fifos[{ordinal}].uid")
        item_gid = _uint(item["gid"], label=f"tree receipt fifos[{ordinal}].gid")
        item_mode = _text(item["mode"], label=f"tree receipt fifos[{ordinal}].mode")
        item_device = _uint(
            item["device"], label=f"tree receipt fifos[{ordinal}].device"
        )
        item_inode = _uint(
            item["inode"], label=f"tree receipt fifos[{ordinal}].inode"
        )
        expected_owner = "root" if role in _H11_COMMIT_FIFO_NAMES else "fixture"
        expected_uid_gid = (0, 0) if expected_owner == "root" else (uid, gid)
        if (
            role in seen_roles
            or path.parent != root / "fifo"
            or owner != expected_owner
            or (item_uid, item_gid) != expected_uid_gid
            or item_mode != "0600"
        ):
            _fail("tree receipt FIFO role/path/owner metadata drifted")
        reserved_name = _H11_COMMIT_FIFO_NAMES.get(role)
        if reserved_name is not None and path != root / "fifo" / reserved_name:
            _fail("tree receipt H11 commit FIFO path drifted")
        info = path.lstat()
        identity = (str(info.st_dev), str(info.st_ino))
        if (
            not stat.S_ISFIFO(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or identity != (str(item_device), str(item_inode))
            or identity in seen_identities
        ):
            _fail("tree receipt FIFO identity or mode drifted")
        if (info.st_uid, info.st_gid) != expected_uid_gid:
            if not (
                not require_root
                and owner == "root"
                and (info.st_uid, info.st_gid) == (os.geteuid(), os.getegid())
            ):
                _fail("tree receipt FIFO filesystem ownership drifted")
        seen_roles.add(role)
        seen_identities.add(identity)
        validated_fifos.append(dict(item))
    receipt_specs = [
        (item["role"], Path(item["path"]), item["owner"])
        for item in validated_fifos
    ]
    if receipt_specs != prepare_specs:
        _fail("tree receipt FIFO inventory differs from its prepare manifest")
    if [item["role"] for item in validated_fifos] != sorted(seen_roles):
        _fail("tree receipt FIFO inventory is not sorted canonically by role")
    return user, group, uid, gid, validated_fifos


def _parse_concrete_fragment(
    raw: bytes, *, role: str, unit: str
) -> dict[str, dict[str, str]]:
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise InstallerError(f"unit fragment is not exact ASCII: {unit}") from exc
    if not text.endswith("\n") or "\r" in text or "\x00" in text:
        _fail(f"unit fragment is not canonical line data: {unit}")
    if "@" in text or "%" in text:
        _fail(f"concrete unit contains a placeholder/specifier: {unit}")
    expected_comments = (
        ["# H10 NEGATIVE CONTROL ONLY. This unit can never satisfy formal acceptance."]
        if role == "gc-fragment"
        else []
    )
    comments: list[str] = []
    sections: dict[str, dict[str, str]] = {}
    section_order: list[str] = []
    current: str | None = None
    for line in text[:-1].split("\n"):
        if line == "":
            continue
        if line.startswith("#"):
            if current is not None:
                _fail(f"unit fragment contains an in-section comment: {unit}")
            comments.append(line)
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            if section not in {"Unit", "Service"} or section in sections:
                _fail(f"unit fragment section set is not closed: {unit}")
            sections[section] = {}
            section_order.append(section)
            current = section
            continue
        if current is None or "=" not in line:
            _fail(f"unit fragment contains a non-directive line: {unit}")
        key, value = line.split("=", 1)
        if (
            re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", key) is None
            or value == ""
            or key in sections[current]
        ):
            _fail(f"unit fragment directive multiset is invalid: {unit}")
        sections[current][key] = value
    if comments != expected_comments or section_order != ["Unit", "Service"]:
        _fail(f"unit fragment comments/section order differs from the closed form: {unit}")
    return sections


def _require_concrete_fragment(
    raw: bytes,
    *,
    role: str,
    unit: str,
    root: Path,
    user: str,
    group: str,
    run_unit: str,
    close_unit: str,
) -> list[tuple[str, Path, Path]]:
    sections = _parse_concrete_fragment(raw, role=role, unit=unit)
    roots = {
        "ReadOnlyPaths": f"{root / 'sealed'} {root / 'input'}",
        "ReadWritePaths": f"{root / 'work'} {root / 'fifo'}",
    }
    common = {
        "User": user,
        "Group": group,
        "UMask": "0077",
        "Restart": "no",
        "NoNewPrivileges": "yes",
        "PrivateTmp": "yes",
        "ProtectSystem": "strict",
        "ProtectHome": "read-only",
        **roots,
    }
    if role == "run-fragment":
        expected = {
            "Unit": {
                "Description": None,
                "OnSuccess": close_unit,
                "OnFailure": close_unit,
                "CollectMode": "inactive",
            },
            "Service": {
                **common,
                "Type": "exec",
                "ExecStart": None,
                "ExecStopPost": None,
                "ExitType": "main",
                "KillMode": "control-group",
                "SendSIGKILL": "yes",
                "TimeoutStopSec": "infinity",
                "OOMPolicy": "stop",
                "Delegate": "pids",
                "DelegateSubgroup": "supervisor",
                "PrivateMounts": "yes",
                "ProtectControlGroups": "no",
                "ProtectProc": "invisible",
                "ProcSubset": "all",
            },
        }
        description_prefix = "Scion generic SpawnBackend formal run "
    elif role == "close-fragment":
        expected = {
            "Unit": {
                "Description": None,
                "After": run_unit,
                "CollectMode": "inactive",
            },
            "Service": {
                **common,
                "Type": "oneshot",
                "ExecStart": None,
                "TimeoutStartSec": "infinity",
            },
        }
        description_prefix = "Scion generic SpawnBackend formal closer "
    elif role == "gc-fragment":
        expected = {
            "Unit": {
                "Description": None,
                "X-Scion-Acceptance-Case": "H10-negative-control-only",
                "X-Scion-Expected-Result": "rejected-failed-identity-loss",
                "CollectMode": "inactive-or-failed",
            },
            "Service": {
                **common,
                "Type": "exec",
                "ExecStart": None,
                "KillMode": "control-group",
                "SendSIGKILL": "yes",
                "TimeoutStopSec": "infinity",
            },
        }
        description_prefix = "Scion H10 GC negative control (rejected) "
    else:
        _fail(f"unit fragment role is outside the exact closed set: {role}")
    for section in ("Unit", "Service"):
        actual_values = sections[section]
        expected_values = expected[section]
        if set(actual_values) != set(expected_values):
            _fail(
                f"unit fragment {section} directive multiset is not closed: {unit}"
            )
        for key, value in expected_values.items():
            if value is not None and actual_values[key] != value:
                _fail(f"unit fragment {key} value differs from the closed form: {unit}")
    description = sections["Unit"]["Description"]
    suffix = description[len(description_prefix) :] if description.startswith(description_prefix) else ""
    if not suffix or _DESCRIPTION_SUFFIX_RE.fullmatch(suffix) is None:
        _fail(f"unit fragment Description is not canonical: {unit}")
    return _fragment_argv(raw, unit=unit)


def _require_root(require_root: bool) -> None:
    if not require_root:
        return
    if os.geteuid() != 0:
        _fail("root authority is required; installer does not invoke sudo")
    if Path(sys.executable).resolve() != Path("/usr/bin/python3.12"):
        _fail("privileged installer requires exact /usr/bin/python3.12")
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        _fail("privileged installer requires Python -I -B")


def _require_manifest_authority(path: Path, *, require_root: bool) -> None:
    if not require_root:
        return
    info = path.lstat()
    if info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) != 0o444:
        _fail("privileged installer manifest must be root:root 0444")


def _decode_canonical_object(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_constant,
        )
    except InstallerError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InstallerError(f"{label} is not strict UTF-8 JSON") from exc
    if type(value) is not dict or _canonical(value) != raw:
        _fail(f"{label} must be one exact canonical JSON object")
    return value


H11RootFrozenJsonValue: TypeAlias = Union[
    None,
    bool,
    int,
    str,
    tuple["H11RootFrozenJsonValue", ...],
    tuple[tuple[str, "H11RootFrozenJsonValue"], ...],
]
H11RootFrozenJsonObject = tuple[tuple[str, H11RootFrozenJsonValue], ...]


def _freeze_h11_json_value(value: Any) -> H11RootFrozenJsonValue:
    if value is None or type(value) is bool or type(value) is int or type(value) is str:
        return value
    if type(value) is list:
        return tuple(_freeze_h11_json_value(item) for item in value)
    if type(value) is dict:
        return tuple(
            (key, _freeze_h11_json_value(item))
            for key, item in dict.items(value)
            if type(key) is str
        )
    _fail("H11 canonical JSON contains a non-JSON value")


def _decode_h11_canonical_frozen_object(
    raw: bytes,
    *,
    label: str,
) -> H11RootFrozenJsonObject:
    try:
        text = bytes.decode(raw, "utf-8", "strict")
        parsed = json.loads(text)
        encoded = str.encode(
            json.dumps(
                parsed,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n",
            "ascii",
        )
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise InstallerError(f"{label} is not strict canonical JSON") from exc
    if type(parsed) is not dict or encoded != raw:
        _fail(f"{label} must be one exact canonical JSON object")
    frozen = _freeze_h11_json_value(parsed)
    if type(frozen) is not tuple or any(
        type(row) is not tuple or len(row) != 2 or type(row[0]) is not str
        for row in frozen
    ):
        _fail(f"{label} did not freeze to one exact object")
    return frozen


def _h11_exact_object_fields(
    value: H11RootFrozenJsonValue,
    expected_fields: tuple[str, ...],
    *,
    label: str,
) -> H11RootFrozenJsonObject:
    if type(value) is not tuple or tuple(key for key, _item in value) != expected_fields:
        _fail(f"{label} fields differ from the exact closed set")
    return value


def _h11_object_member(
    value: H11RootFrozenJsonObject,
    field: str,
    *,
    label: str,
) -> H11RootFrozenJsonValue:
    matches = tuple(item for key, item in value if key == field)
    if len(matches) != 1:
        _fail(f"{label}.{field} is missing or duplicated")
    return matches[0]


def _h11_text(value: H11RootFrozenJsonValue, *, label: str) -> str:
    if type(value) is not str:
        _fail(f"{label} must be one string")
    return value


def _h11_uint(value: H11RootFrozenJsonValue, *, label: str) -> int:
    if type(value) is not str or re.fullmatch(r"0|[1-9][0-9]*", value) is None:
        _fail(f"{label} must be one canonical unsigned integer")
    result = int(value, 10)
    if result > (1 << 64) - 1:
        _fail(f"{label} exceeds uint64")
    return result


def _h11_path(value: H11RootFrozenJsonValue, *, label: str) -> Path:
    if type(value) is not str:
        _fail(f"{label} must be one path string")
    result = Path(value)
    if (
        not result.is_absolute()
        or str(result) != value
        or any(part in {".", ".."} for part in result.parts)
    ):
        _fail(f"{label} must be one normalized absolute path")
    return result


def _h11_sha256_text(value: H11RootFrozenJsonValue, *, label: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail(f"{label} must be one canonical SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class H11RootDirectoryReference:
    role: str
    path: Path
    device: int
    inode: int
    mode: int
    uid: int
    gid: int

    @classmethod
    def decode(
        cls,
        value: H11RootFrozenJsonValue,
        *,
        label: str,
    ) -> "H11RootDirectoryReference":
        if type(value) is not tuple or tuple(key for key, _item in value) != (
            "device", "gid", "inode", "mode", "path", "role", "uid"
        ):
            _fail(f"{label} fields differ from the exact closed set")
        row = dict(value)
        if (
            type(row["role"]) is not str
            or type(row["path"]) is not str
            or type(row["mode"]) is not str
            or re.fullmatch(r"0[0-7]{3}", row["mode"]) is None
        ):
            _fail(f"{label} role/path/mode is not canonical")
        path = Path(row["path"])
        if (
            not path.is_absolute()
            or str(path) != row["path"]
            or any(part in {".", ".."} for part in path.parts)
        ):
            _fail(f"{label}.path is not canonical")
        numbers: list[int] = []
        for field in ("device", "inode", "uid", "gid"):
            text = row[field]
            if (
                type(text) is not str
                or re.fullmatch(r"0|[1-9][0-9]*", text) is None
            ):
                _fail(f"{label}.{field} is not canonical")
            number = int(text, 10)
            if number > (1 << 64) - 1:
                _fail(f"{label}.{field} exceeds uint64")
            numbers.append(number)
        return H11RootDirectoryReference(
            row["role"],
            path,
            numbers[0],
            numbers[1],
            int(row["mode"], 8),
            numbers[2],
            numbers[3],
        )

    @property
    def parent_reference(self) -> dict[str, str]:
        return {
            "path": str(self.path),
            "device": str(self.device),
            "inode": str(self.inode),
            "mode": format(self.mode, "04o"),
            "uid": str(self.uid),
            "gid": str(self.gid),
        }

    def prove(self, info: os.stat_result, *, require_root: bool, label: str) -> None:
        if (
            not stat.S_ISDIR(info.st_mode)
            or (info.st_dev, info.st_ino) != (self.device, self.inode)
            or stat.S_IMODE(info.st_mode) != self.mode
            or (info.st_uid, info.st_gid) != (self.uid, self.gid)
            or (require_root and (self.uid != 0 or self.gid != 0))
        ):
            _fail(f"{label} directory identity/mode/owner drifted")


@dataclass(frozen=True, slots=True)
class H11RootFifoReference:
    path: Path
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    accepted_owners: tuple[tuple[int, int], ...]

    @classmethod
    def decode(
        cls,
        value: H11RootFrozenJsonValue,
        *,
        label: str,
        require_root: bool,
        process_euid: int,
        process_egid: int,
    ) -> "H11RootFifoReference":
        if type(value) is not tuple or tuple(key for key, _item in value) != (
            "device", "gid", "inode", "mode", "path", "uid"
        ):
            _fail(f"{label} fields differ from the exact closed set")
        row = dict(value)
        if (
            type(row["path"]) is not str
            or type(row["mode"]) is not str
            or re.fullmatch(r"0[0-7]{3}", row["mode"]) is None
        ):
            _fail(f"{label} path/mode is not canonical")
        path = Path(row["path"])
        if (
            not path.is_absolute()
            or str(path) != row["path"]
            or any(part in {".", ".."} for part in path.parts)
        ):
            _fail(f"{label}.path is not canonical")
        numbers: list[int] = []
        for field in ("device", "inode", "uid", "gid"):
            text = row[field]
            if (
                type(text) is not str
                or re.fullmatch(r"0|[1-9][0-9]*", text) is None
            ):
                _fail(f"{label}.{field} is not canonical")
            number = int(text, 10)
            if number > (1 << 64) - 1:
                _fail(f"{label}.{field} exceeds uint64")
            numbers.append(number)
        uid = numbers[2]
        gid = numbers[3]
        if require_root and (uid, gid) != (0, 0):
            _fail(f"{label} must declare root ownership")
        accepted_owners = (
            tuple(sorted({(0, 0), (process_euid, process_egid)}))
            if not require_root and (uid, gid) == (0, 0)
            else ((uid, gid),)
        )
        return H11RootFifoReference(
            path,
            numbers[0],
            numbers[1],
            int(row["mode"], 8),
            uid,
            gid,
            accepted_owners,
        )

    @property
    def reference(self) -> dict[str, str]:
        return {
            "path": str(self.path),
            "device": str(self.device),
            "inode": str(self.inode),
            "mode": format(self.mode, "04o"),
            "uid": str(self.uid),
            "gid": str(self.gid),
        }

    def prove(self, info: os.stat_result, *, label: str) -> None:
        if (
            not stat.S_ISFIFO(info.st_mode)
            or (info.st_dev, info.st_ino) != (self.device, self.inode)
            or stat.S_IMODE(info.st_mode) != self.mode
            or self.mode != 0o600
            or (info.st_uid, info.st_gid) not in self.accepted_owners
        ):
            _fail(f"{label} FIFO identity/mode/owner drifted")


@dataclass(frozen=True, slots=True)
class H11RootCommitReceipt:
    phase: str
    fifo: H11RootFifoReference
    payload_sha256: str
    byte_count: str

    @classmethod
    def ready_committed(
        cls,
        fifo: "H11RootFifoView",
        payload: bytes,
    ) -> "H11RootCommitReceipt":
        if fifo.role != "h11-ready-commit" or payload != H11_READY_COMMITTED_BYTES:
            _fail("H11 READY commit receipt source is not the exact committed frame")
        return H11RootCommitReceipt(
            "ready-committed",
            fifo.reference,
            hashlib.sha256(payload).hexdigest(),
            str(len(payload)),
        )

    @classmethod
    def permit_committed(
        cls,
        fifo: "H11RootFifoView",
        payload: bytes,
    ) -> "H11RootCommitReceipt":
        if (
            fifo.role != "h11-permit-commit"
            or payload != H11_PERMIT_COMMITTED_BYTES
        ):
            _fail("H11 PERMIT commit receipt source is not the exact committed frame")
        return H11RootCommitReceipt(
            "permit-committed",
            fifo.reference,
            hashlib.sha256(payload).hexdigest(),
            str(len(payload)),
        )

    @property
    def reference(self) -> dict[str, Any]:
        return {
            "schema": H11_COMMIT_FIFO_RECEIPT_SCHEMA,
            "phase": self.phase,
            "fifo": self.fifo.reference,
            "payload_sha256": self.payload_sha256,
            "byte_count": self.byte_count,
        }


@dataclass(frozen=True, slots=True)
class H11RootRolePath:
    role: str
    path: Path

    @classmethod
    def decode(cls, value: Any, *, label: str) -> "H11RootRolePath":
        if type(value) is not dict:
            _fail(f"{label} must be one exact role/path object")
        _exact(value, {"role", "path"}, label=label)
        role = _text(value["role"], label=f"{label}.role")
        if _ROLE_RE.fullmatch(role) is None:
            _fail(f"{label}.role is not canonical")
        return cls(role, _path(value["path"], label=f"{label}.path"))

    @property
    def reference(self) -> dict[str, str]:
        return {"role": self.role, "path": str(self.path)}


@dataclass(frozen=True, slots=True)
class H11RootClosedPartition:
    present_prerequisites: tuple[H11RootRolePath, ...]
    future_absence_inventory: tuple[H11RootRolePath, ...]
    frozen_root: H11RootRolePath
    input_future_absence: tuple[H11RootRolePath, ...]
    receipt_future_absence: tuple[H11RootRolePath, ...]


@dataclass(frozen=True, slots=True)
class H11RootTransactionState:
    role: str
    path: Path
    state: str

    @property
    def reference(self) -> dict[str, str]:
        return {"role": self.role, "path": str(self.path), "state": self.state}


@dataclass(frozen=True, slots=True)
class H11RootValidatedFifo:
    role: str
    path: Path
    owner: str
    uid: int
    gid: int
    mode: int
    device: int
    inode: int
    accepted_owners: tuple[tuple[int, int], ...]

    @property
    def acquisition_reference(self) -> dict[str, str]:
        return {
            "path": str(self.path),
            "device": str(self.device),
            "inode": str(self.inode),
        }


@dataclass(frozen=True, slots=True)
class H11RootNamedStagingPlan:
    parent: H11RootDirectoryReference
    staging_name: str
    final_name: str
    raw: bytes
    expected_owner: tuple[int, int]
    require_root: bool
    test_failure: str | None


@dataclass(frozen=True, slots=True)
class H11RootPrePermitBarrier:
    directory_chain: tuple[H11RootDirectoryReference, ...]
    present_outputs_sha256: str
    future_absence_sha256: str
    transaction_state: tuple[H11RootTransactionState, ...]
    future_absence_inventory: tuple[H11RootRolePath, ...]

def prepare_tree(manifest_path: Path, *, require_root: bool = True) -> dict[str, Any]:
    """Create the unique authority tree and all named FIFO identities."""

    _require_root(require_root)
    _require_manifest_authority(manifest_path, require_root=require_root)
    plan = _decode(manifest_path)
    _exact(
        plan,
        {"schema", "formal_root", "fixture_user", "fixture_group", "fifos", "receipt_path"},
        label="prepare manifest",
    )
    if plan["schema"] != PREPARE_SCHEMA:
        _fail("unexpected prepare schema")
    root = _path(plan["formal_root"], label="formal_root")
    receipt_path = _path(plan["receipt_path"], label="receipt_path")
    user = _text(plan["fixture_user"], label="fixture_user")
    group = _text(plan["fixture_group"], label="fixture_group")
    try:
        uid = pwd.getpwnam(user).pw_uid
        gid = grp.getgrnam(group).gr_gid
    except KeyError as exc:
        raise InstallerError("fixture user/group does not exist") from exc
    if uid == 0:
        _fail("fixture user must not be root")
    authority = root / "authority"
    if receipt_path.parent != authority:
        _fail("tree receipt must be an immediate child of authority root")
    fifo_specs = _decode_fifo_specs(plan["fifos"], root=root, label="fifos")
    if root.exists() or root.is_symlink():
        _fail("formal_root already exists")
    _require_absent(receipt_path, label="tree receipt destination")
    manifest_reference = _manifest_reference(manifest_path)
    root.mkdir(mode=0o711)
    sealed = root / "sealed"
    input_root = root / "input"
    work = root / "work"
    fifo_root = root / "fifo"
    authority = root / "authority"
    sealed.mkdir(mode=0o755)
    input_root.mkdir(mode=0o755)
    work.mkdir(mode=0o700)
    fifo_root.mkdir(mode=0o711)
    authority.mkdir(mode=0o700)
    os.chmod(root, 0o711)
    os.chmod(sealed, 0o755)
    os.chmod(input_root, 0o755)
    os.chmod(work, 0o700)
    os.chmod(fifo_root, 0o711)
    os.chmod(authority, 0o700)
    os.chown(work, uid, gid)
    fifo_receipts: list[dict[str, Any]] = []
    for role, fifo, owner in fifo_specs:
        os.mkfifo(fifo, 0o600)
        owner_uid, owner_gid = (0, 0) if owner == "root" else (uid, gid)
        if require_root or owner == "fixture":
            os.chown(fifo, owner_uid, owner_gid)
        os.chmod(fifo, 0o600)
        fifo_receipts.append(
            _fifo_reference(
                fifo,
                role=role,
                owner=owner,
                uid=owner_uid,
                gid=owner_gid,
                allow_test_root_owner=not require_root,
            )
        )
    for directory in (sealed, input_root, work, fifo_root, authority):
        _fsync_directory(directory)
    _fsync_directory(root)
    _fsync_directory(root.parent)
    receipt = {
        "schema": TREE_RECEIPT_SCHEMA,
        "formal_root": _identity(root),
        "sealed_root": _identity(sealed),
        "input_root": _identity(input_root),
        "work_root": _identity(work),
        "fifo_root": _identity(fifo_root),
        "authority_root": _identity(authority),
        "fixture_user": user,
        "fixture_group": group,
        "fixture_uid": str(uid),
        "fixture_gid": str(gid),
        "fifos": fifo_receipts,
        "prepare_manifest": manifest_reference,
        "phase": "tree-prepared",
    }
    _write_no_replace(receipt_path, receipt, mode=0o444)
    _fsync_directory(authority)
    _fsync_directory(root)
    _fsync_directory(root.parent)
    return receipt


def seal_tree(manifest_path: Path, *, require_root: bool = True) -> dict[str, Any]:
    """Verify authored files and make the static/input authorities immutable."""

    _require_root(require_root)
    _require_manifest_authority(manifest_path, require_root=require_root)
    plan = _decode(manifest_path)
    _exact(
        plan,
        {"schema", "formal_root", "tree_receipt", "files", "receipt_path"},
        label="seal manifest",
    )
    if plan["schema"] != SEAL_SCHEMA:
        _fail("unexpected seal schema")
    root = _path(plan["formal_root"], label="formal_root")
    sealed = root / "sealed"
    input_root = root / "input"
    authority = root / "authority"
    receipt_path = _path(plan["receipt_path"], label="receipt_path")
    if receipt_path.parent != authority:
        _fail("seal receipt must be an immediate child of authority root")
    _require_absent(receipt_path, label="seal receipt destination")
    tree_receipt_path, tree_receipt, _tree_raw = _bound_json_input(
        plan["tree_receipt"], label="tree_receipt"
    )
    if tree_receipt_path.parent != authority:
        _fail("tree receipt is outside the authority root")
    _validate_tree_receipt(
        tree_receipt,
        root=root,
        receipt_path=tree_receipt_path,
        require_root=require_root,
    )
    if type(plan["files"]) is not list or not plan["files"]:
        _fail("files must be one nonempty array")
    validated: list[tuple[str, Path, str, bytes]] = []
    seen: set[Path] = set()
    seen_roles: set[str] = set()
    for ordinal, item_value in enumerate(plan["files"]):
        if type(item_value) is not dict:
            _fail(f"files[{ordinal}] must be one object")
        _exact(item_value, {"role", "path", "sha256"}, label=f"files[{ordinal}]")
        role = _text(item_value["role"], label=f"files[{ordinal}].role")
        path = _path(item_value["path"], label=f"files[{ordinal}].path")
        expected = _text(item_value["sha256"], label=f"files[{ordinal}].sha256")
        if (
            _ROLE_RE.fullmatch(role) is None
            or role in seen_roles
            or _HEX_RE.fullmatch(expected) is None
        ):
            _fail("invalid frozen role or SHA-256")
        if path in seen or (path.parent != sealed and path.parent != input_root):
            _fail("frozen file must be unique and immediately below sealed/input")
        seen.add(path)
        seen_roles.add(role)
        raw = _read_regular(path, label=role)
        if hashlib.sha256(raw).hexdigest() != expected:
            _fail(f"SHA-256 mismatch for {role}")
        validated.append((role, path, expected, raw))
    manifest_reference = _manifest_reference(manifest_path)
    frozen: list[dict[str, str]] = []
    for role, path, expected, raw in validated:
        if require_root:
            os.chown(path, 0, 0)
        os.chmod(path, 0o444)
        _fsync_regular(path)
        frozen.append(
            {"role": role, "sha256": expected, **_identity(path), "mode": "0444"}
        )
    receipt = {
        "schema": SEAL_RECEIPT_SCHEMA,
        "formal_root": _identity(root),
        "tree_receipt": dict(plan["tree_receipt"]),
        "seal_manifest": manifest_reference,
        "files": frozen,
        "phase": "static-authority-sealed",
    }
    os.chmod(sealed, 0o555)
    os.chmod(input_root, 0o555)
    _fsync_directory(sealed)
    _fsync_directory(input_root)
    _fsync_directory(root)
    _write_no_replace(receipt_path, receipt, mode=0o444)
    _fsync_directory(authority)
    _fsync_directory(root)
    _fsync_directory(root.parent)
    return receipt


def _validate_seal_receipt(
    receipt: dict[str, Any],
    *,
    root: Path,
    tree_reference: dict[str, Any],
    require_root: bool,
) -> dict[str, dict[str, str]]:
    _exact(
        receipt,
        {
            "schema",
            "formal_root",
            "tree_receipt",
            "seal_manifest",
            "files",
            "phase",
        },
        label="seal receipt",
    )
    formal_root = receipt["formal_root"]
    if type(formal_root) is not dict:
        _fail("seal receipt formal_root must be one identity")
    if (
        receipt["schema"] != SEAL_RECEIPT_SCHEMA
        or receipt["phase"] != "static-authority-sealed"
        or receipt["tree_receipt"] != tree_reference
        or formal_root.get("path") != str(root)
    ):
        _fail("seal receipt does not bind the tree/install root")
    _seal_manifest_path, seal_manifest, _seal_manifest_raw = _bound_json_input(
        receipt["seal_manifest"], label="seal receipt seal_manifest"
    )
    if (
        seal_manifest.get("schema") != SEAL_SCHEMA
        or seal_manifest.get("formal_root") != str(root)
        or seal_manifest.get("tree_receipt") != tree_reference
    ):
        _fail("seal manifest authority differs from its receipt")
    files = receipt["files"]
    if type(files) is not list or not files:
        _fail("seal receipt file inventory is empty")
    by_role: dict[str, dict[str, str]] = {}
    seen_paths: set[str] = set()
    seen_identities: set[tuple[str, str]] = set()
    for ordinal, item in enumerate(files):
        if type(item) is not dict:
            _fail(f"seal receipt files[{ordinal}] must be one object")
        _exact(
            item,
            {"role", "path", "sha256", "device", "inode", "mode"},
            label=f"seal receipt files[{ordinal}]",
        )
        role = _text(item["role"], label=f"seal receipt files[{ordinal}].role")
        path = _path(item["path"], label=f"seal receipt files[{ordinal}].path")
        sha256 = _text(item["sha256"], label=f"seal receipt files[{ordinal}].sha256")
        if (
            _ROLE_RE.fullmatch(role) is None
            or role in by_role
            or str(path) in seen_paths
            or (item["device"], item["inode"]) in seen_identities
            or path.parent not in {root / "sealed", root / "input"}
            or _HEX_RE.fullmatch(sha256) is None
            or item["mode"] != "0444"
        ):
            _fail("seal receipt contains a duplicate or invalid file binding")
        raw = _read_regular(path, label=f"sealed file {role}")
        info = path.lstat()
        if (
            hashlib.sha256(raw).hexdigest() != sha256
            or (str(info.st_dev), str(info.st_ino))
            != (item["device"], item["inode"])
            or stat.S_IMODE(info.st_mode) != 0o444
            or (require_root and (info.st_uid != 0 or info.st_gid != 0))
        ):
            _fail(f"sealed file binding drifted for role {role}")
        by_role[role] = item
        seen_paths.add(str(path))
        seen_identities.add((item["device"], item["inode"]))
    return by_role


def _decode_preflight_inventory(path: Path) -> dict[str, Any]:
    raw = _read_regular(path, label="static preflight inventory manifest")
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise InstallerError("static preflight inventory must be ASCII") from exc
    if not text.endswith("\n") or "\r" in text or "\x00" in text:
        _fail("static preflight inventory is not canonical line data")
    lines = text[:-1].split("\n")
    if len(lines) < 7:
        _fail("static preflight inventory is incomplete")
    expected_headers = (
        ("schema", PREFLIGHT_MANIFEST_SCHEMA),
        ("formal_root", None),
        ("run_unit", None),
        ("close_unit", None),
        ("destination_path", None),
    )
    headers: dict[str, str] = {}
    for ordinal, (key, fixed) in enumerate(expected_headers):
        fields = lines[ordinal].split("\t")
        if len(fields) != 2 or fields[0] != key or (fixed is not None and fields[1] != fixed):
            _fail(f"static preflight header {key!r} is missing or reordered")
        headers[key] = fields[1]
    formal_root = _path(headers["formal_root"], label="preflight formal_root")
    destination = _path(headers["destination_path"], label="preflight destination_path")
    if (
        _SAFE_ABSOLUTE_RE.fullmatch(str(formal_root)) is None
        or _SAFE_ABSOLUTE_RE.fullmatch(str(destination)) is None
        or destination.parent != formal_root / "authority"
        or _UNIT_RE.fullmatch(headers["run_unit"]) is None
        or _UNIT_RE.fullmatch(headers["close_unit"]) is None
        or headers["run_unit"] == headers["close_unit"]
    ):
        _fail("static preflight root/unit/destination header is invalid")
    references: dict[str, dict[str, str]] = {}
    for offset, key in enumerate(("tree_receipt",), start=5):
        fields = lines[offset].split("\t")
        if len(fields) != 6 or fields[0] != key:
            _fail(f"static preflight reference {key!r} is missing or reordered")
        reference = dict(zip(("path", "sha256", "device", "inode", "mode"), fields[1:]))
        _path(reference["path"], label=f"preflight {key}.path")
        if (
            _HEX_RE.fullmatch(reference["sha256"]) is None
            or not all(
                re.fullmatch(r"0|[1-9][0-9]*", reference[name])
                for name in ("device", "inode")
            )
            or reference["mode"] != "0444"
        ):
            _fail(f"static preflight reference {key!r} is not canonical")
        references[key] = reference
    assets: list[dict[str, str]] = []
    seen_roles: set[str] = set()
    seen_paths: set[str] = set()
    seen_identities: set[tuple[str, str]] = set()
    for ordinal, line in enumerate(lines[6:]):
        fields = line.split("\t")
        if len(fields) != 8 or fields[0] != "asset":
            _fail(f"static preflight asset record {ordinal} is malformed")
        role, kind, raw_path, sha256, device, inode, mode = fields[1:]
        asset_path = _path(raw_path, label=f"preflight asset[{ordinal}].path")
        if (
            _ROLE_RE.fullmatch(role) is None
            or role in seen_roles
            or kind not in _ASSET_KINDS
            or raw_path in seen_paths
            or (device, inode) in seen_identities
            or _HEX_RE.fullmatch(sha256) is None
            or not re.fullmatch(r"0|[1-9][0-9]*", device)
            or not re.fullmatch(r"0|[1-9][0-9]*", inode)
            or mode != "0444"
            or _SAFE_ABSOLUTE_RE.fullmatch(str(asset_path)) is None
        ):
            _fail("static preflight asset binding is invalid or duplicated")
        assets.append(
            {
                "role": role,
                "kind": kind,
                "path": str(asset_path),
                "sha256": sha256,
                "device": device,
                "inode": inode,
                "mode": mode,
            }
        )
        seen_roles.add(role)
        seen_paths.add(raw_path)
        seen_identities.add((device, inode))
    return {**headers, **references, "assets": assets, "raw": raw}


def _fragment_argv(raw: bytes, *, unit: str) -> list[tuple[str, Path, Path]]:
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise InstallerError(f"unit fragment is not ASCII: {unit}") from exc
    if "@" in text or "%" in text:
        _fail(f"concrete unit contains a placeholder/specifier: {unit}")
    result: list[tuple[str, Path, Path]] = []
    for key in ("ExecStart", "ExecStopPost"):
        matches = [line[len(key) + 1 :] for line in text.splitlines() if line.startswith(f"{key}=")]
        if len(matches) > 1:
            _fail(f"unit contains duplicate {key}: {unit}")
        if not matches:
            continue
        fields = matches[0].split(" ")
        if (
            len(fields) != 6
            or fields[:3] != ["/usr/bin/python3.12", "-I", "-B"]
            or fields[4] != "--plan"
        ):
            _fail(f"unit {key} is not exact /usr/bin/python3.12 -I -B PROGRAM --plan PLAN")
        result.append(
            (
                key,
                _path(fields[3], label=f"{unit} {key} program"),
                _path(fields[5], label=f"{unit} {key} plan"),
            )
        )
    if not result or result[0][0] != "ExecStart":
        _fail(f"unit lacks one exact ExecStart: {unit}")
    return result


def _systemd_unit_object_path(unit: str) -> str:
    if _UNIT_RE.fullmatch(unit) is None:
        _fail("cannot escape a noncanonical formal unit name")
    escaped = "".join(
        character
        if character.isascii() and character.isalnum()
        else f"_{ord(character):02x}"
        for character in unit
    )
    return "/org/freedesktop/systemd1/unit/" + escaped


class DBusManager:
    """Small system-manager adapter; imported only for privileged execution."""

    def __init__(self) -> None:
        try:
            import dbus  # type: ignore[import-not-found]
        except ImportError as exc:
            raise InstallerError("dbus-python is unavailable") from exc
        self._dbus = dbus
        self._bus = dbus.SystemBus()
        dbus_obj = self._bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus")
        dbus_iface = dbus.Interface(dbus_obj, "org.freedesktop.DBus")
        self.owner = str(dbus_iface.GetNameOwner("org.freedesktop.systemd1"))
        manager_obj = self._bus.get_object(self.owner, "/org/freedesktop/systemd1")
        self._manager = dbus.Interface(manager_obj, "org.freedesktop.systemd1.Manager")

    def reload(self) -> None:
        self._manager.Reload()

    def load_unit(self, unit: str) -> str:
        return str(self._manager.LoadUnit(unit))

    def unit_property(self, object_path: str, interface: str, name: str) -> Any:
        obj = self._bus.get_object(self.owner, object_path)
        props = self._dbus.Interface(obj, "org.freedesktop.DBus.Properties")
        value = props.Get(interface, name)
        if name == "NeedDaemonReload":
            if not isinstance(value, self._dbus.Boolean):
                _fail("NeedDaemonReload D-Bus reply is not boolean")
            return bool(value)
        return value


def install_units(
    manifest_path: Path,
    *,
    manager: Manager | None = None,
    require_root: bool = True,
    unit_directory: Path = Path("/run/systemd/system"),
) -> dict[str, Any]:
    """Validate the full authority chain, then install and query each unit."""

    _require_root(require_root)
    _require_manifest_authority(manifest_path, require_root=require_root)
    plan = _decode(manifest_path)
    _exact(
        plan,
        {
            "schema",
            "formal_root",
            "tree_receipt",
            "seal_receipt",
            "preflight_receipt",
            "units",
            "receipt_path",
        },
        label="install manifest",
    )
    if plan["schema"] != INSTALL_SCHEMA:
        _fail("unexpected install schema")
    root = _path(plan["formal_root"], label="formal_root")
    sealed = root / "sealed"
    authority = root / "authority"
    receipt_path = _path(plan["receipt_path"], label="receipt_path")
    if receipt_path.parent != authority:
        _fail("install receipt must be an immediate child of authority root")
    started_path = authority / "INSTALL-STARTED.json"
    if receipt_path == started_path:
        _fail("install receipt and mutation marker paths alias")
    _require_absent(receipt_path, label="install receipt destination")
    _require_absent(started_path, label="install transaction marker")
    tree_path, tree_receipt, _tree_raw = _bound_json_input(
        plan["tree_receipt"], label="tree_receipt"
    )
    if tree_path.parent != authority:
        _fail("tree receipt is outside the authority root")
    (
        fixture_user,
        fixture_group,
        fixture_uid,
        fixture_gid,
        tree_fifos,
    ) = _validate_tree_receipt(
        tree_receipt,
        root=root,
        receipt_path=tree_path,
        require_root=require_root,
        sealed=True,
    )
    seal_path, seal_receipt, _seal_raw = _bound_json_input(
        plan["seal_receipt"], label="seal_receipt"
    )
    if seal_path.parent != authority:
        _fail("seal receipt is outside the authority root")
    sealed_by_role = _validate_seal_receipt(
        seal_receipt,
        root=root,
        tree_reference=plan["tree_receipt"],
        require_root=require_root,
    )
    preflight_path, preflight, _preflight_raw = _bound_json_input(
        plan["preflight_receipt"], label="preflight_receipt"
    )
    _exact(
        preflight,
        {
            "schema",
            "asset_count",
            "close_unit",
            "formal_root",
            "inventory_manifest",
            "fifos",
            "phase",
            "run_unit",
            "seal_receipt",
            "tree_receipt",
        },
        label="preflight receipt",
    )
    if (
        preflight["schema"] != PREFLIGHT_RECEIPT_SCHEMA
        or preflight["phase"] != "static-preflight-complete"
        or preflight["formal_root"] != str(root)
        or preflight_path.parent.parent != authority
        or preflight_path.name != "PREFLIGHT.json"
    ):
        _fail("preflight receipt does not bind this install root")
    if preflight["fifos"] != tree_fifos:
        _fail("preflight FIFO authority differs from the exact tree receipt")
    for key in ("tree_receipt", "seal_receipt"):
        value = preflight[key]
        if type(value) is not dict:
            _fail(f"preflight {key} must be one full file binding")
        _exact(value, {"path", "sha256", "device", "inode", "mode"}, label=f"preflight {key}")
        expected = {**plan[key], "mode": "0444"}
        if value != expected:
            _fail(f"preflight {key} differs from the install manifest")
    inventory_binding = preflight["inventory_manifest"]
    if type(inventory_binding) is not dict:
        _fail("preflight inventory_manifest must be one full file binding")
    _exact(
        inventory_binding,
        {"path", "sha256", "device", "inode", "mode"},
        label="preflight inventory_manifest",
    )
    inventory_path = _path(inventory_binding["path"], label="inventory manifest path")
    inventory = _decode_preflight_inventory(inventory_path)
    if _asset_reference(inventory_path, inventory["raw"]) != inventory_binding:
        _fail("preflight inventory manifest identity drifted")
    inventory_seal_matches = [
        item
        for item in sealed_by_role.values()
        if item["path"] == str(inventory_path)
    ]
    if len(inventory_seal_matches) != 1 or inventory_seal_matches[0] != {
        "role": inventory_seal_matches[0]["role"] if inventory_seal_matches else "",
        **inventory_binding,
    }:
        _fail("preflight inventory manifest is absent from the seal receipt")
    if inventory["formal_root"] != str(root):
        _fail("preflight inventory formal root differs from install root")
    if inventory["tree_receipt"] != preflight["tree_receipt"]:
        _fail("preflight tree receipt reference drifted")
    if str(len(inventory["assets"])) != preflight["asset_count"]:
        _fail("preflight asset count differs from its inventory")
    if (
        preflight["run_unit"] != inventory["run_unit"]
        or preflight["close_unit"] != inventory["close_unit"]
    ):
        _fail("preflight unit names differ from their inventory")
    run_unit = _text(inventory["run_unit"], label="preflight run_unit")
    close_unit = _text(inventory["close_unit"], label="preflight close_unit")

    preflight_destination = _path(
        inventory["destination_path"], label="preflight destination_path"
    )
    if preflight_path.parent != preflight_destination:
        _fail("preflight receipt is outside its inventory-bound destination")
    destination_descriptor = _pin_canonical_directory(
        preflight_destination,
        expected_mode=0o500,
        require_root=require_root,
        label="preflight destination",
    )
    try:
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            receipt_descriptor = os.open(
                preflight_path.name,
                flags,
                dir_fd=destination_descriptor,
            )
        except OSError as exc:
            raise InstallerError(
                "cannot pin inventory-bound preflight receipt"
            ) from exc
        try:
            opened = os.fstat(receipt_descriptor)
            chunks: list[bytes] = []
            while True:
                chunk = os.read(receipt_descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            pinned_raw = b"".join(chunks)
            after = os.fstat(receipt_descriptor)
            current = preflight_path.lstat()
            expected_device = _uint(
                plan["preflight_receipt"]["device"],
                label="preflight_receipt.device",
            )
            expected_inode = _uint(
                plan["preflight_receipt"]["inode"],
                label="preflight_receipt.inode",
            )
            expected_identity = (expected_device, expected_inode)
            if (
                not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != expected_identity
                or (after.st_dev, after.st_ino) != expected_identity
                or (current.st_dev, current.st_ino) != expected_identity
                or pinned_raw != _preflight_raw
                or after.st_size != len(pinned_raw)
                or stat.S_IMODE(opened.st_mode) != 0o444
                or stat.S_IMODE(after.st_mode) != 0o444
                or stat.S_IMODE(current.st_mode) != 0o444
                or (
                    require_root
                    and (
                        opened.st_uid != 0
                        or opened.st_gid != 0
                        or current.st_uid != 0
                        or current.st_gid != 0
                    )
                )
            ):
                _fail("inventory-bound preflight receipt identity or metadata drifted")
        finally:
            os.close(receipt_descriptor)
        destination_after = os.fstat(destination_descriptor)
        destination_current = preflight_destination.lstat()
        if (
            (destination_after.st_dev, destination_after.st_ino)
            != (destination_current.st_dev, destination_current.st_ino)
            or stat.S_IMODE(destination_after.st_mode) != 0o500
            or stat.S_IMODE(destination_current.st_mode) != 0o500
        ):
            _fail("preflight destination drifted while validating its receipt")
    finally:
        os.close(destination_descriptor)

    assets_by_path: dict[str, dict[str, str]] = {}
    unit_assets: list[dict[str, str]] = []
    for asset in inventory["assets"]:
        asset_path = Path(asset["path"])
        raw = _read_regular(asset_path, label=f"preflight asset {asset['role']}")
        if _asset_reference(asset_path, raw) != {
            key: asset[key] for key in ("path", "device", "inode", "sha256", "mode")
        }:
            _fail(f"preflight asset identity drifted: {asset['role']}")
        sealed_item = sealed_by_role.get(asset["role"])
        if sealed_item is None or sealed_item != {
            key: asset[key] for key in ("role", "path", "sha256", "device", "inode", "mode")
        }:
            _fail(f"preflight asset is absent from seal receipt: {asset['role']}")
        assets_by_path[asset["path"]] = asset
        if asset["kind"] == "unit-fragment":
            unit_assets.append(asset)
    if {item["path"] for item in sealed_by_role.values()} != {
        str(inventory_path),
        *(asset["path"] for asset in inventory["assets"]),
    }:
        _fail("preflight inventory does not enumerate the exact sealed file set")
    if {asset["role"] for asset in unit_assets} != {
        "run-fragment",
        "close-fragment",
        "gc-fragment",
    }:
        _fail("preflight inventory must contain the exact three concrete unit roles")
    if not any(
        asset["kind"] == "installer-program"
        and Path(asset["path"]).resolve() == Path(__file__).resolve()
        for asset in inventory["assets"]
    ):
        _fail("preflight inventory does not bind this root installer program")
    if sum(asset["kind"] == "harness-program" for asset in inventory["assets"]) != 1:
        _fail("preflight inventory must bind exactly one harness program")
    if sum(asset["kind"] == "start-descriptor" for asset in inventory["assets"]) != 1:
        _fail("preflight inventory must bind exactly one start descriptor")

    if require_root and unit_directory != Path("/run/systemd/system"):
        _fail("privileged install target must be exact /run/systemd/system")
    try:
        resolved_unit_directory = unit_directory.resolve(strict=True)
    except OSError as exc:
        raise InstallerError("unit installation directory does not exist") from exc
    if (
        not unit_directory.is_absolute()
        or resolved_unit_directory != unit_directory
        or unit_directory.is_symlink()
        or not unit_directory.is_dir()
    ):
        _fail("unit installation directory must be one canonical real directory")
    units_value = plan["units"]
    if type(units_value) is not list or not units_value:
        _fail("units must be one nonempty array")
    if len(units_value) != len(unit_assets):
        _fail("install units differ from the preflighted unit inventory")
    validated: list[dict[str, Any]] = []
    seen_roles: set[str] = set()
    seen_units: set[str] = set()
    seen_sources: set[Path] = set()
    seen_targets: set[Path] = set()
    for ordinal, (item_value, inventory_asset) in enumerate(zip(units_value, unit_assets)):
        if type(item_value) is not dict:
            _fail(f"units[{ordinal}] must be one object")
        _exact(item_value, {"role", "unit", "source", "sha256"}, label=f"units[{ordinal}]")
        role = _text(item_value["role"], label=f"units[{ordinal}].role")
        unit = _text(item_value["unit"], label=f"units[{ordinal}].unit")
        source = _path(item_value["source"], label=f"units[{ordinal}].source")
        expected = _text(item_value["sha256"], label=f"units[{ordinal}].sha256")
        target = unit_directory / unit
        if (
            _ROLE_RE.fullmatch(role) is None
            or _UNIT_RE.fullmatch(unit) is None
            or _HEX_RE.fullmatch(expected) is None
            or role in seen_roles
            or unit in seen_units
            or source in seen_sources
            or target in seen_targets
            or source.parent != sealed
            or item_value != {
                "role": inventory_asset["role"],
                "unit": unit,
                "source": inventory_asset["path"],
                "sha256": inventory_asset["sha256"],
            }
        ):
            _fail("install unit binding is invalid, duplicated or not preflighted")
        if Path(inventory_asset["path"]).name != unit:
            _fail("preflight unit path basename differs from the concrete unit name")
        raw = _read_regular(source, label=role)
        if hashlib.sha256(raw).hexdigest() != expected:
            _fail(f"unit SHA-256 mismatch for {unit}")
        argv = _require_concrete_fragment(
            raw,
            role=role,
            unit=unit,
            root=root,
            user=fixture_user,
            group=fixture_group,
            run_unit=run_unit,
            close_unit=close_unit,
        )
        for _key, program, program_plan in argv:
            if assets_by_path.get(str(program), {}).get("kind") not in {
                "python-program",
                "installer-program",
                "harness-program",
            }:
                _fail(f"unit program is absent from sealed preflight inventory: {program}")
            if assets_by_path.get(str(program_plan), {}).get("kind") != "json-plan":
                _fail(f"unit plan is absent from sealed preflight inventory: {program_plan}")
        if target.exists() or target.is_symlink():
            _fail(f"unit fragment already exists: {target}")
        validated.append(
            {
                "role": role,
                "unit": unit,
                "source": source,
                "source_raw": raw,
                "source_binding": _asset_reference(source, raw),
                "target": target,
            }
        )
        seen_roles.add(role)
        seen_units.add(unit)
        seen_sources.add(source)
        seen_targets.add(target)

    active_manager = manager if manager is not None else DBusManager()
    owner = _text(active_manager.owner, label="system manager unique owner")
    if _UNIQUE_OWNER_RE.fullmatch(owner) is None:
        _fail("system manager owner is not one canonical unique bus name")
    manifest_reference = _manifest_reference(manifest_path)
    installer_reference = _asset_reference(Path(__file__).resolve())
    _write_no_replace(
        started_path,
        {
            "schema": "scion.generic_backend.root_install_started.v1",
            "formal_root": str(root),
            "install_manifest": manifest_reference,
            "phase": "mutation-started",
        },
        mode=0o400,
    )
    for item in validated:
        target = item["target"]
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
        descriptor = os.open(target, flags, 0o644)
        try:
            view = memoryview(item["source_raw"])
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    _fail("fragment write made no progress")
                view = view[written:]
            os.fchmod(descriptor, 0o644)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    _fsync_directory(unit_directory)

    ledger: list[dict[str, Any]] = []

    def record(
        *,
        interface: str,
        member: str,
        object_path: str,
        signature: str,
        arguments: list[Any],
        reply: Any,
    ) -> None:
        begin = 2 * len(ledger) + 1
        ledger.append(
            {
                "begin_ordinal": str(begin),
                "reply_ordinal": str(begin + 1),
                "interface": interface,
                "member": member,
                "object_path": object_path,
                "signature": signature,
                "arguments": arguments,
                "reply": reply,
            }
        )

    active_manager.reload()
    record(
        interface="org.freedesktop.systemd1.Manager",
        member="Reload",
        object_path="/org/freedesktop/systemd1",
        signature="",
        arguments=[],
        reply=None,
    )
    object_paths: list[str] = []
    for item in validated:
        object_path = _text(
            active_manager.load_unit(item["unit"]), label="LoadUnit object path"
        )
        expected_object_path = _systemd_unit_object_path(item["unit"])
        if object_path != expected_object_path or object_path in object_paths:
            _fail("LoadUnit returned a noncanonical or duplicate object path")
        object_paths.append(object_path)
        record(
            interface="org.freedesktop.systemd1.Manager",
            member="LoadUnit",
            object_path="/org/freedesktop/systemd1",
            signature="s",
            arguments=[item["unit"]],
            reply=object_path,
        )

    records: list[dict[str, Any]] = []
    for item, object_path in zip(validated, object_paths):
        fragment = str(
            active_manager.unit_property(
                object_path, "org.freedesktop.systemd1.Unit", "FragmentPath"
            )
        )
        record(
            interface="org.freedesktop.DBus.Properties",
            member="Get",
            object_path=object_path,
            signature="ss",
            arguments=["org.freedesktop.systemd1.Unit", "FragmentPath"],
            reply=fragment,
        )
        need_reload_value = active_manager.unit_property(
            object_path, "org.freedesktop.systemd1.Unit", "NeedDaemonReload"
        )
        if type(need_reload_value) is not bool:
            _fail("NeedDaemonReload did not return one exact boolean")
        record(
            interface="org.freedesktop.DBus.Properties",
            member="Get",
            object_path=object_path,
            signature="ss",
            arguments=["org.freedesktop.systemd1.Unit", "NeedDaemonReload"],
            reply=need_reload_value,
        )
        target = item["target"]
        raw = _read_regular(target, label=f"installed fragment {item['unit']}")
        info = target.lstat()
        if (
            fragment != str(target)
            or need_reload_value is not False
            or raw != item["source_raw"]
            or stat.S_IMODE(info.st_mode) != 0o644
            or (require_root and (info.st_uid != 0 or info.st_gid != 0))
        ):
            _fail(f"manager/installed fragment binding failed for {item['unit']}")
        records.append(
            {
                "role": item["role"],
                "unit": item["unit"],
                "source": item["source_binding"],
                "target": {
                    **_identity(target),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "uid": str(info.st_uid),
                    "gid": str(info.st_gid),
                    "mode": "0644",
                },
                "object_path": object_path,
                "fragment_path": fragment,
                "need_daemon_reload": False,
            }
        )
    receipt = {
        "schema": INSTALL_RECEIPT_SCHEMA,
        "formal_root": _identity(root),
        "installer": installer_reference,
        "install_manifest": {**manifest_reference, "mode": format(stat.S_IMODE(manifest_path.lstat().st_mode), "04o")},
        "tree_receipt": dict(plan["tree_receipt"]),
        "seal_receipt": dict(plan["seal_receipt"]),
        "preflight_receipt": dict(plan["preflight_receipt"]),
        "manager_owner": owner,
        "manager_ledger": ledger,
        "fixture_user": fixture_user,
        "fixture_group": fixture_group,
        "fixture_uid": str(fixture_uid),
        "fixture_gid": str(fixture_gid),
        "reload_call_count": "1",
        "load_call_count": str(len(records)),
        "units": records,
        "phase": "installed-before-observation",
    }
    _write_no_replace(receipt_path, receipt, mode=0o444)
    return receipt


def _validate_install_receipt(
    receipt: dict[str, Any],
    *,
    root: Path,
    reference: dict[str, Any] | None = None,
    require_root: bool = True,
) -> list[dict[str, Any]]:
    _exact(
        receipt,
        {
            "schema",
            "formal_root",
            "installer",
            "install_manifest",
            "tree_receipt",
            "seal_receipt",
            "preflight_receipt",
            "manager_owner",
            "manager_ledger",
            "fixture_user",
            "fixture_group",
            "fixture_uid",
            "fixture_gid",
            "reload_call_count",
            "load_call_count",
            "units",
            "phase",
        },
        label="install receipt",
    )
    formal_root = receipt["formal_root"]
    if type(formal_root) is not dict:
        _fail("install receipt formal_root must be one directory identity")
    if (
        receipt["schema"] != INSTALL_RECEIPT_SCHEMA
        or receipt["phase"] != "installed-before-observation"
        or formal_root.get("path") != str(root)
        or receipt["reload_call_count"] != "1"
    ):
        _fail("install receipt schema/root/phase is invalid")
    _validate_directory_identity(
        formal_root, expected_path=root, expected_mode=0o711, label="install formal root"
    )
    for key in ("installer", "install_manifest"):
        binding = receipt[key]
        if type(binding) is not dict:
            _fail(f"install receipt {key} must be one full file binding")
        _exact(
            binding,
            {"path", "sha256", "device", "inode", "mode"},
            label=f"install receipt {key}",
        )
        bound_path = _path(binding["path"], label=f"install receipt {key}.path")
        if _asset_reference(bound_path) != binding:
            _fail(f"install receipt {key} identity drifted")
    _install_manifest_path, install_manifest, _install_manifest_raw = _bound_json_input(
        {
            key: receipt["install_manifest"][key]
            for key in ("path", "sha256", "device", "inode")
        },
        label="install receipt install_manifest authority",
    )
    _exact(
        install_manifest,
        {
            "schema",
            "formal_root",
            "tree_receipt",
            "seal_receipt",
            "preflight_receipt",
            "units",
            "receipt_path",
        },
        label="bound install manifest",
    )
    if (
        install_manifest["schema"] != INSTALL_SCHEMA
        or install_manifest["formal_root"] != str(root)
        or any(
            install_manifest[key] != receipt[key]
            for key in ("tree_receipt", "seal_receipt", "preflight_receipt")
        )
        or (
            reference is not None
            and install_manifest["receipt_path"] != reference["path"]
        )
    ):
        _fail("install receipt differs from its bound install manifest")
    input_schemas = {
        "tree_receipt": TREE_RECEIPT_SCHEMA,
        "seal_receipt": SEAL_RECEIPT_SCHEMA,
        "preflight_receipt": PREFLIGHT_RECEIPT_SCHEMA,
    }
    for key, schema in input_schemas.items():
        _input_path, decoded, _input_raw = _bound_json_input(
            receipt[key], label=f"install receipt {key}"
        )
        if decoded.get("schema") != schema:
            _fail(f"install receipt {key} schema drifted")
    owner = _text(receipt["manager_owner"], label="install manager owner")
    if _UNIQUE_OWNER_RE.fullmatch(owner) is None:
        _fail("install manager owner is not canonical")
    units = receipt["units"]
    ledger = receipt["manager_ledger"]
    if type(units) is not list or not units or type(ledger) is not list:
        _fail("install receipt unit/manager ledger is malformed")
    if receipt["load_call_count"] != str(len(units)) or len(ledger) != 1 + 3 * len(units):
        _fail("install receipt manager call counts differ from its ledger")
    if type(install_manifest["units"]) is not list or len(install_manifest["units"]) != len(units):
        _fail("install receipt unit count differs from its bound install manifest")
    expected_members = ["Reload"] + ["LoadUnit"] * len(units) + [
        member for _item in units for member in ("Get", "Get")
    ]
    for ordinal, (entry, member) in enumerate(zip(ledger, expected_members), start=1):
        if type(entry) is not dict:
            _fail("install manager ledger entry is not one object")
        _exact(
            entry,
            {
                "begin_ordinal",
                "reply_ordinal",
                "interface",
                "member",
                "object_path",
                "signature",
                "arguments",
                "reply",
            },
            label=f"install manager ledger[{ordinal - 1}]",
        )
        if (
            entry["begin_ordinal"] != str(2 * ordinal - 1)
            or entry["reply_ordinal"] != str(2 * ordinal)
            or entry["member"] != member
        ):
            _fail("install manager ledger is reordered or has a wrong member")
    seen_units: set[str] = set()
    seen_targets: set[str] = set()
    seen_object_paths: set[str] = set()
    for ordinal, unit_record in enumerate(units):
        if type(unit_record) is not dict:
            _fail(f"install units[{ordinal}] must be one object")
        _exact(
            unit_record,
            {
                "role",
                "unit",
                "source",
                "target",
                "object_path",
                "fragment_path",
                "need_daemon_reload",
            },
            label=f"install units[{ordinal}]",
        )
        unit = _text(unit_record["unit"], label=f"install units[{ordinal}].unit")
        target = unit_record["target"]
        source = unit_record["source"]
        if type(target) is not dict or type(source) is not dict:
            _fail("install unit source/target must be objects")
        _exact(source, {"path", "device", "inode", "sha256", "mode"}, label="installed source")
        _exact(
            target,
            {"path", "device", "inode", "sha256", "uid", "gid", "mode"},
            label="installed target",
        )
        if (
            _UNIT_RE.fullmatch(unit) is None
            or unit in seen_units
            or target["path"] in seen_targets
            or unit_record["object_path"] != _systemd_unit_object_path(unit)
            or unit_record["object_path"] in seen_object_paths
            or unit_record["fragment_path"] != target["path"]
            or unit_record["need_daemon_reload"] is not False
            or target["mode"] != "0644"
        ):
            _fail("install receipt unit binding is invalid or duplicated")
        if install_manifest["units"][ordinal] != {
            "role": unit_record["role"],
            "unit": unit,
            "source": source["path"],
            "sha256": source["sha256"],
        }:
            _fail("install receipt unit differs from its bound install manifest")
        source_path = _path(source["path"], label="installed source path")
        target_path = _path(target["path"], label="installed target path")
        source_raw = _read_regular(source_path, label=f"installed source {unit}")
        target_raw = _read_regular(target_path, label=f"installed target {unit}")
        source_info = source_path.lstat()
        target_info = target_path.lstat()
        if (
            hashlib.sha256(source_raw).hexdigest() != source["sha256"]
            or (str(source_info.st_dev), str(source_info.st_ino))
            != (source["device"], source["inode"])
            or format(stat.S_IMODE(source_info.st_mode), "04o") != source["mode"]
            or hashlib.sha256(target_raw).hexdigest() != target["sha256"]
            or (str(target_info.st_dev), str(target_info.st_ino))
            != (target["device"], target["inode"])
            or str(target_info.st_uid) != target["uid"]
            or str(target_info.st_gid) != target["gid"]
            or format(stat.S_IMODE(target_info.st_mode), "04o") != target["mode"]
            or source_raw != target_raw
        ):
            _fail(f"install receipt source/target identity drifted: {unit}")
        seen_units.add(unit)
        seen_targets.add(target["path"])
        seen_object_paths.add(unit_record["object_path"])
    reload_entry = ledger[0]
    if reload_entry != {
        "begin_ordinal": "1",
        "reply_ordinal": "2",
        "interface": "org.freedesktop.systemd1.Manager",
        "member": "Reload",
        "object_path": "/org/freedesktop/systemd1",
        "signature": "",
        "arguments": [],
        "reply": None,
    }:
        _fail("install Reload ledger entry is not exact")
    load_entries = ledger[1 : 1 + len(units)]
    property_entries = ledger[1 + len(units) :]
    for unit_record, load_entry in zip(units, load_entries):
        if load_entry != {
            "begin_ordinal": load_entry["begin_ordinal"],
            "reply_ordinal": load_entry["reply_ordinal"],
            "interface": "org.freedesktop.systemd1.Manager",
            "member": "LoadUnit",
            "object_path": "/org/freedesktop/systemd1",
            "signature": "s",
            "arguments": [unit_record["unit"]],
            "reply": unit_record["object_path"],
        }:
            _fail("install LoadUnit ledger entry differs from its unit binding")
    for unit_record, fragment_entry, reload_property_entry in zip(
        units, property_entries[::2], property_entries[1::2]
    ):
        common = {
            "interface": "org.freedesktop.DBus.Properties",
            "member": "Get",
            "object_path": unit_record["object_path"],
            "signature": "ss",
        }
        if fragment_entry != {
            "begin_ordinal": fragment_entry["begin_ordinal"],
            "reply_ordinal": fragment_entry["reply_ordinal"],
            **common,
            "arguments": ["org.freedesktop.systemd1.Unit", "FragmentPath"],
            "reply": unit_record["fragment_path"],
        }:
            _fail("install FragmentPath ledger entry differs from its unit binding")
        if reload_property_entry != {
            "begin_ordinal": reload_property_entry["begin_ordinal"],
            "reply_ordinal": reload_property_entry["reply_ordinal"],
            **common,
            "arguments": ["org.freedesktop.systemd1.Unit", "NeedDaemonReload"],
            "reply": False,
        }:
            _fail("install NeedDaemonReload ledger entry differs from its unit binding")
    if require_root:
        for key in ("installer", "install_manifest"):
            info = Path(receipt[key]["path"]).lstat()
            if info.st_uid != 0 or info.st_gid != 0:
                _fail(f"install receipt {key} is no longer root-owned")
    if reference is not None and formal_root.get("path") != str(root):
        _fail("install receipt reference differs from the freeze root")
    return units


def _pin_regular_reference(
    value: Any, *, label: str
) -> tuple[int, Path, bytes, dict[str, str]]:
    if type(value) is not dict:
        _fail(f"{label} must be one exact frozen file reference")
    _exact(value, {"path", "sha256", "device", "inode"}, label=label)
    path = _path(value["path"], label=f"{label}.path")
    sha256 = _text(value["sha256"], label=f"{label}.sha256")
    device = _uint(value["device"], label=f"{label}.device")
    inode = _uint(value["inode"], label=f"{label}.inode")
    if _HEX_RE.fullmatch(sha256) is None:
        _fail(f"{label}.sha256 is not canonical")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise InstallerError(f"cannot pin {label}: {path}") from exc
    try:
        opened = os.fstat(descriptor)
        current = path.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (device, inode)
            or (current.st_dev, current.st_ino) != (device, inode)
        ):
            _fail(f"{label} identity differs from its frozen reference")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            hashlib.sha256(raw).hexdigest() != sha256
            or after.st_size != len(raw)
            or (after.st_dev, after.st_ino) != (device, inode)
        ):
            _fail(f"{label} bytes/identity drifted while pinning")
        os.lseek(descriptor, 0, os.SEEK_SET)
        return descriptor, path, raw, dict(value)
    except BaseException:
        os.close(descriptor)
        raise


def freeze_receipts(
    manifest_path: Path,
    *,
    require_root: bool = True,
    _test_final_publisher: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Copy the closed policy inventory and publish ``FROZEN`` last."""

    _require_root(require_root)
    if _test_final_publisher is not None and (
        require_root or not callable(_test_final_publisher)
    ):
        _fail("test-only final publisher is invalid for privileged execution")
    _require_manifest_authority(manifest_path, require_root=require_root)
    plan = _decode(manifest_path)
    _exact(
        plan,
        {
            "schema",
            "formal_root",
            "policy_id",
            "install_receipt",
            "harness_receipt",
            "outputs",
            "destination_path",
        },
        label="final freeze manifest",
    )
    if plan["schema"] != FREEZE_SCHEMA:
        _fail("unexpected final freeze schema")
    root = _path(plan["formal_root"], label="formal_root")
    destination = _path(plan["destination_path"], label="destination_path")
    if destination != root / "frozen":
        _fail("final freeze destination must be exact formal_root/frozen")
    if destination.exists() or destination.is_symlink():
        _fail("final freeze destination already exists; replacement is forbidden")
    policy_id = _text(plan["policy_id"], label="policy_id")
    install_path, install_receipt, _install_raw = _bound_json_input(
        plan["install_receipt"], label="install_receipt"
    )
    _validate_install_receipt(
        install_receipt,
        root=root,
        reference=plan["install_receipt"],
        require_root=require_root,
    )
    harness_path, harness_receipt, _harness_raw = _bound_json_input(
        plan["harness_receipt"], label="harness_receipt"
    )
    if (
        harness_receipt.get("schema") != HARNESS_RECEIPT_SCHEMA
        or harness_receipt.get("scenario") != policy_id
    ):
        _fail("harness final receipt schema/policy differs from freeze manifest")
    final_freeze = harness_receipt.get("final_freeze")
    if type(final_freeze) is not dict:
        _fail("harness final receipt lacks its closed freeze inventory")
    _exact(final_freeze, {"policy_id", "output_roles"}, label="harness final_freeze")
    output_roles = final_freeze["output_roles"]
    if (
        final_freeze["policy_id"] != policy_id
        or type(output_roles) is not list
        or not output_roles
        or any(type(role) is not str or _ROLE_RE.fullmatch(role) is None for role in output_roles)
        or len(set(output_roles)) != len(output_roles)
    ):
        _fail("harness final freeze policy/output roles are invalid")
    outputs = plan["outputs"]
    if type(outputs) is not list or [
        item.get("role") if type(item) is dict else None for item in outputs
    ] != output_roles:
        _fail("freeze outputs differ from the harness-closed ordered role inventory")

    pinned: list[tuple[int, str, Path, bytes, dict[str, str]]] = []
    destination_descriptor: int | None = None
    frozen_descriptor: int | None = None
    seen_paths: set[Path] = set()
    seen_identities: set[tuple[str, str]] = set()
    try:
        for ordinal, item in enumerate(outputs):
            if type(item) is not dict:
                _fail(f"freeze outputs[{ordinal}] must be one object")
            _exact(
                item,
                {"role", "path", "sha256", "device", "inode"},
                label=f"freeze outputs[{ordinal}]",
            )
            role = _text(item["role"], label=f"freeze outputs[{ordinal}].role")
            descriptor, source, raw, reference = _pin_regular_reference(
                {key: item[key] for key in ("path", "sha256", "device", "inode")},
                label=f"freeze output {role}",
            )
            identity = (reference["device"], reference["inode"])
            if source in seen_paths or identity in seen_identities:
                os.close(descriptor)
                _fail("freeze output source path/identity is duplicated")
            pinned.append((descriptor, role, source, raw, reference))
            seen_paths.add(source)
            seen_identities.add(identity)
        by_role = {role: reference for _fd, role, _path_value, _raw, reference in pinned}
        if by_role.get("install-receipt") != plan["install_receipt"]:
            _fail("freeze inventory does not contain the exact install receipt")
        if by_role.get("harness-final") != plan["harness_receipt"]:
            _fail("freeze inventory does not contain the exact harness final receipt")

        manifest_reference = _manifest_reference(manifest_path)
        destination.mkdir(mode=0o700)
        destination_descriptor = _pin_canonical_directory(
            destination,
            expected_mode=0o700,
            require_root=require_root,
            label="final freeze destination",
        )
        tmpfile_flag = getattr(os, "O_TMPFILE", None)
        if tmpfile_flag is None:
            _fail("Linux O_TMPFILE is unavailable for FROZEN publication")
        try:
            frozen_descriptor = os.open(
                ".",
                os.O_WRONLY | os.O_CLOEXEC | tmpfile_flag,
                0o400,
                dir_fd=destination_descriptor,
            )
        except OSError as exc:
            raise InstallerError(
                "cannot create unnamed FROZEN publication inode"
            ) from exc
        os.fsync(destination_descriptor)
        _fsync_directory(root)
        _fsync_directory(root.parent)
        frozen_files: list[dict[str, Any]] = []
        checksum_lines: list[str] = []
        for descriptor, role, source, raw, reference in pinned:
            source_info = os.fstat(descriptor)
            if (str(source_info.st_dev), str(source_info.st_ino)) != (
                reference["device"],
                reference["inode"],
            ):
                _fail(f"pinned freeze source identity drifted: {role}")
            target = destination / role
            _write_bytes_no_replace(target, raw, mode=0o400)
            checksum_lines.append(f"{reference['sha256']}  {role}\n")
            frozen_files.append(
                {
                    "role": role,
                    "source": reference,
                    "destination": _asset_reference(target, raw),
                }
            )
        checksum_raw = "".join(checksum_lines).encode("ascii")
        _write_bytes_no_replace(destination / "SHA256SUMS", checksum_raw, mode=0o400)
        os.chmod(destination, 0o500)
        frozen_root_binding = _directory_reference(destination)
        if require_root and (
            frozen_root_binding["uid"] != "0" or frozen_root_binding["gid"] != "0"
        ):
            _fail("final freeze destination is not root-owned")
        destination_info = os.fstat(destination_descriptor)
        if (
            (str(destination_info.st_dev), str(destination_info.st_ino))
            != (frozen_root_binding["device"], frozen_root_binding["inode"])
            or stat.S_IMODE(destination_info.st_mode) != 0o500
            or str(destination_info.st_uid) != frozen_root_binding["uid"]
            or str(destination_info.st_gid) != frozen_root_binding["gid"]
        ):
            _fail("final freeze destination identity drifted before publication")
        os.fsync(destination_descriptor)
        _fsync_directory(root)
        _fsync_directory(root.parent)
        frozen = {
            "schema": FREEZE_RECEIPT_SCHEMA,
            "formal_root": _identity(root),
            "frozen_root": frozen_root_binding,
            "policy_id": policy_id,
            "freeze_manifest": manifest_reference,
            "install_receipt": dict(plan["install_receipt"]),
            "harness_receipt": dict(plan["harness_receipt"]),
            "files": frozen_files,
            "sha256sums": _asset_reference(destination / "SHA256SUMS", checksum_raw),
            "phase": "frozen-complete",
        }
        frozen_raw = _canonical(frozen)
        view = memoryview(frozen_raw)
        while view:
            written = os.write(frozen_descriptor, view)
            if written <= 0:
                _fail("unnamed FROZEN write made no progress")
            view = view[written:]
        os.fchmod(frozen_descriptor, 0o400)
        os.fsync(frozen_descriptor)
        final_publisher = (
            _publish_unnamed_no_replace
            if _test_final_publisher is None
            else _test_final_publisher
        )
        final_publisher(
            frozen_descriptor,
            directory_descriptor=destination_descriptor,
            name="FROZEN",
        )
        return frozen
    finally:
        if frozen_descriptor is not None:
            os.close(frozen_descriptor)
        if destination_descriptor is not None:
            os.close(destination_descriptor)
        for descriptor, _role, _source, _raw, _reference in pinned:
            os.close(descriptor)


def _validate_frozen_receipt(
    receipt: dict[str, Any],
    *,
    root: Path,
    install_reference: dict[str, Any],
    require_root: bool,
) -> None:
    _exact(
        receipt,
        {
            "schema",
            "formal_root",
            "frozen_root",
            "policy_id",
            "freeze_manifest",
            "install_receipt",
            "harness_receipt",
            "files",
            "sha256sums",
            "phase",
        },
        label="frozen receipt",
    )
    if (
        receipt["schema"] != FREEZE_RECEIPT_SCHEMA
        or receipt["phase"] != "frozen-complete"
        or receipt["install_receipt"] != install_reference
    ):
        _fail("frozen receipt schema/phase/install binding is invalid")
    _validate_directory_identity(
        receipt["formal_root"],
        expected_path=root,
        expected_mode=0o711,
        label="frozen formal root",
    )
    frozen_root = receipt["frozen_root"]
    if type(frozen_root) is not dict:
        _fail("frozen receipt frozen_root must be one directory binding")
    _exact(
        frozen_root,
        {"path", "device", "inode", "uid", "gid", "mode"},
        label="frozen frozen_root",
    )
    frozen_path = root / "frozen"
    if _path(frozen_root["path"], label="frozen frozen_root.path") != frozen_path:
        _fail("frozen directory path differs from formal_root/frozen")
    current_frozen_root = _directory_reference(frozen_path)
    if frozen_root != current_frozen_root or frozen_root["mode"] != "0500":
        _fail("frozen directory identity/owner/mode drifted")
    if require_root and (frozen_root["uid"] != "0" or frozen_root["gid"] != "0"):
        _fail("frozen directory is no longer root-owned")
    freeze_manifest = receipt["freeze_manifest"]
    if type(freeze_manifest) is not dict:
        _fail("frozen receipt freeze_manifest must be one full binding")
    _exact(
        freeze_manifest,
        {"path", "sha256", "device", "inode"},
        label="frozen freeze_manifest",
    )
    freeze_manifest_path = _path(
        freeze_manifest["path"], label="frozen freeze_manifest.path"
    )
    if _file_reference(freeze_manifest_path) != freeze_manifest:
        _fail("frozen freeze manifest identity drifted")
    _harness_path, harness, _harness_raw = _bound_json_input(
        receipt["harness_receipt"], label="frozen harness_receipt"
    )
    if (
        harness.get("schema") != HARNESS_RECEIPT_SCHEMA
        or harness.get("scenario") != receipt["policy_id"]
        or type(harness.get("final_freeze")) is not dict
    ):
        _fail("frozen harness receipt policy/schema drifted")
    final_freeze = harness["final_freeze"]
    _exact(final_freeze, {"policy_id", "output_roles"}, label="frozen harness final_freeze")
    files = receipt["files"]
    if (
        type(files) is not list
        or not files
        or final_freeze["policy_id"] != receipt["policy_id"]
        or final_freeze["output_roles"]
        != [item.get("role") if type(item) is dict else None for item in files]
    ):
        _fail("frozen file roles differ from the harness-closed inventory")
    checksum_lines: list[str] = []
    seen_roles: set[str] = set()
    for ordinal, item in enumerate(files):
        if type(item) is not dict:
            _fail(f"frozen files[{ordinal}] must be one object")
        _exact(item, {"role", "source", "destination"}, label=f"frozen files[{ordinal}]")
        role = _text(item["role"], label=f"frozen files[{ordinal}].role")
        source = item["source"]
        destination = item["destination"]
        if type(source) is not dict or type(destination) is not dict:
            _fail("frozen source/destination binding must be objects")
        _exact(source, {"path", "sha256", "device", "inode"}, label="frozen source")
        _exact(
            destination,
            {"path", "sha256", "device", "inode", "mode"},
            label="frozen destination",
        )
        target = _path(destination["path"], label="frozen destination.path")
        raw = _read_regular(target, label=f"frozen destination {role}")
        if (
            role in seen_roles
            or target != root / "frozen" / role
            or destination["mode"] != "0400"
            or destination != _asset_reference(target, raw)
            or destination["sha256"] != source["sha256"]
        ):
            _fail("frozen destination identity/hash/role drifted")
        if require_root:
            info = target.lstat()
            if info.st_uid != 0 or info.st_gid != 0:
                _fail("frozen destination is no longer root-owned")
        checksum_lines.append(f"{source['sha256']}  {role}\n")
        seen_roles.add(role)
    checksum_raw = "".join(checksum_lines).encode("ascii")
    checksum_path = root / "frozen" / "SHA256SUMS"
    checksum_actual = _read_regular(checksum_path, label="SHA256SUMS")
    if (
        _asset_reference(checksum_path, checksum_actual)
        != receipt["sha256sums"]
        or checksum_actual != checksum_raw
    ):
        _fail("frozen SHA256SUMS drifted")


class H11RootAuthorizationState(Enum):
    NEW = "new"
    AUTHORITIES_RETAINED = "authorities-retained"
    READY_CONSUMED = "ready-consumed"
    PERMIT_PUBLISHED = "permit-published"
    PERMIT_WRITER_OPEN = "permit-writer-open"
    PERMIT_FRAME_WRITTEN = "permit-frame-written"
    COMPLETE = "complete"
    FAILED_PREWRITE = "failed-prewrite"
    FAILED_WRITE_AMBIGUOUS = "failed-write-ambiguous"
    FAILED_POSTWRITE = "failed-postwrite"
    CLOSED = "closed"


class H11RootCommitBoundary(Enum):
    PREWRITE = "prewrite"
    WRITE_IN_FLIGHT = "write-in-flight"
    POSTWRITE = "postwrite"


class H11OwnedFdSlot:
    __slots__ = ("_role", "_descriptor", "_open_started")

    def __init__(self, *, role: str) -> None:
        self._role = role
        self._descriptor = -1
        self._open_started = False

    @property
    def role(self) -> str:
        return self._role

    def open(
        self,
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> None:
        if self._open_started or self._descriptor != -1:
            _fail(f"H11 FD slot {self._role} cannot be opened twice")
        self._open_started = True
        self._bind(os.open(path, flags, mode, dir_fd=dir_fd))

    def _bind(self, descriptor: int) -> None:
        if self._descriptor != -1 or type(descriptor) is not int or descriptor < 0:
            _fail(f"H11 FD slot {self._role} cannot bind this descriptor")
        self._descriptor = descriptor

    def borrow(self) -> int:
        if self._descriptor < 0:
            _fail(f"H11 FD slot {self._role} is empty")
        return self._descriptor

    def detach(self) -> int:
        descriptor = self._descriptor
        self._descriptor = -1
        return descriptor


def _prove_h11_execution_authority(
    *,
    require_root: bool,
    process_euid: int,
) -> None:
    if not require_root:
        return
    if process_euid != 0:
        _fail("root authority is required; installer does not invoke sudo")
    if Path.resolve(Path(sys.executable)) != Path("/usr/bin/python3.12"):
        _fail("privileged installer requires exact /usr/bin/python3.12")
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        _fail("privileged installer requires Python -I -B")


@dataclass(frozen=True, slots=True)
class H11RootIndirectAuthoritySpec:
    semantic_role: str
    equivalence_class: str
    install_ordinal: int | None
    path: Path
    kind: str
    device: int
    inode: int
    mode: int | None
    accepted_owners: tuple[tuple[int, int], ...] | None


@dataclass(frozen=True, slots=True)
class H11RootObservedPathIdentity:
    semantic_role: str
    equivalence_class: str
    install_ordinal: int | None
    path: Path
    kind: str
    device: int
    inode: int
    mode: int
    uid: int
    gid: int


def _make_h11_indirect_authority_spec(
    *,
    semantic_role: str,
    equivalence_class: str,
    install_ordinal: int | None,
    path: Path,
    kind: str,
    device: int,
    inode: int,
    mode: int | None,
    accepted_owners: tuple[tuple[int, int], ...] | None,
) -> H11RootIndirectAuthoritySpec:
    if kind not in ("directory", "fifo", "regular"):
        _fail("H11 indirect authority kind is outside the exact closed set")
    if install_ordinal is not None and install_ordinal not in (0, 1, 2):
        _fail("H11 install authority ordinal is outside the exact closed set")
    if accepted_owners is not None and (
        not accepted_owners
        or accepted_owners != tuple(sorted(set(accepted_owners)))
    ):
        _fail("H11 indirect accepted-owner policy is not canonical")
    return H11RootIndirectAuthoritySpec(
        semantic_role,
        equivalence_class,
        install_ordinal,
        path,
        kind,
        device,
        inode,
        mode,
        accepted_owners,
    )


def _observe_h11_indirect_authority(
    spec: H11RootIndirectAuthoritySpec,
) -> H11RootObservedPathIdentity:
    try:
        info = Path.lstat(spec.path)
    except OSError as exc:
        raise InstallerError(
            f"cannot observe H11 indirect authority {spec.semantic_role}"
        ) from exc
    kind = (
        "directory"
        if stat.S_ISDIR(info.st_mode)
        else "fifo"
        if stat.S_ISFIFO(info.st_mode)
        else "regular"
        if stat.S_ISREG(info.st_mode)
        else ""
    )
    if kind != spec.kind:
        _fail(f"H11 indirect authority {spec.semantic_role} kind drifted")
    return H11RootObservedPathIdentity(
        spec.semantic_role,
        spec.equivalence_class,
        spec.install_ordinal,
        spec.path,
        kind,
        info.st_dev,
        info.st_ino,
        stat.S_IMODE(info.st_mode),
        info.st_uid,
        info.st_gid,
    )


def _prove_h11_indirect_observations(
    indirect_specs: tuple[H11RootIndirectAuthoritySpec, ...],
    observed_identities: tuple[H11RootObservedPathIdentity, ...],
) -> None:
    if type(indirect_specs) is not tuple or type(observed_identities) is not tuple:
        _fail("H11 indirect authority proof requires exact tuples")
    if len(indirect_specs) != len(observed_identities):
        _fail("H11 indirect authority observation count drifted")
    seen_paths: set[Path] = set()
    seen_identities: set[tuple[int, int]] = set()
    for spec, observed in zip(indirect_specs, observed_identities):
        if (
            type(spec) is not H11RootIndirectAuthoritySpec
            or type(observed) is not H11RootObservedPathIdentity
            or observed.semantic_role != spec.semantic_role
            or observed.equivalence_class != spec.equivalence_class
            or observed.install_ordinal != spec.install_ordinal
            or observed.path != spec.path
            or observed.kind != spec.kind
            or (observed.device, observed.inode) != (spec.device, spec.inode)
            or (spec.mode is not None and observed.mode != spec.mode)
            or (
                spec.accepted_owners is not None
                and (observed.uid, observed.gid) not in spec.accepted_owners
            )
            or observed.path in seen_paths
            or (observed.device, observed.inode) in seen_identities
        ):
            _fail(f"H11 indirect authority {spec.semantic_role} drifted")
        seen_paths.add(observed.path)
        seen_identities.add((observed.device, observed.inode))


def _prove_h11_direct_authority_bindings(
    *,
    authorization_manifest: H11RootFrozenJsonObject,
    harness_manifest: H11RootFrozenJsonObject,
    install_receipt: H11RootFrozenJsonObject,
    install_manifest: H11RootFrozenJsonObject,
    tree_receipt: H11RootFrozenJsonObject,
    seal_receipt: H11RootFrozenJsonObject,
    preflight_receipt: H11RootFrozenJsonObject,
    permit_ready: H11RootFrozenJsonObject,
    run_armed: H11RootFrozenJsonObject,
    authorization_source_reference: H11RootFrozenJsonObject,
    harness_source_reference: H11RootFrozenJsonObject,
    install_receipt_source_reference: H11RootFrozenJsonObject,
    install_manifest_source_reference: H11RootFrozenJsonObject,
    tree_receipt_source_reference: H11RootFrozenJsonObject,
    seal_receipt_source_reference: H11RootFrozenJsonObject,
    preflight_receipt_source_reference: H11RootFrozenJsonObject,
    permit_ready_source_reference: H11RootFrozenJsonObject,
    run_armed_source_reference: H11RootFrozenJsonObject,
    formal_root_directory_reference: H11RootDirectoryReference,
    authority_root_directory_reference: H11RootDirectoryReference,
    harness_root_directory_reference: H11RootDirectoryReference,
    scenario_root_directory_reference: H11RootDirectoryReference,
    input_root_directory_reference: H11RootDirectoryReference,
    receipt_root_directory_reference: H11RootDirectoryReference,
    fifo_root_directory_reference: H11RootDirectoryReference,
    ready_commit_fifo_reference: H11RootFifoReference,
    permit_commit_fifo_reference: H11RootFifoReference,
) -> None:
    authorization_manifest = _h11_exact_object_fields(
        authorization_manifest,
        (
            "formal_root",
            "harness_manifest",
            "permit_path",
            "permit_ready",
            "run_armed",
            "schema",
        ),
        label="H11 authorization",
    )
    harness_manifest = _h11_exact_object_fields(
        harness_manifest,
        (
            "acquisitions",
            "boot_id_file",
            "closer_unit",
            "descriptor",
            "formal_actions",
            "harness_program",
            "input_root",
            "installer_receipt",
            "outputs",
            "permit_authority",
            "preflight_receipt",
            "receipt_root",
            "run_unit",
            "scenario",
            "scenario_input",
            "schema",
            "static_inventory",
            "static_roles",
        ),
        label="H11 harness manifest",
    )
    permit_authority = _h11_exact_object_fields(
        _h11_object_member(
            harness_manifest,
            "permit_authority",
            label="H11 harness manifest",
        ),
        (
            "directory_chain",
            "future_absence_inventory",
            "permit_commit_fifo",
            "permit_ledger_path",
            "permit_ledger_staging_path",
            "permit_parent",
            "permit_path",
            "permit_ready_path",
            "permit_ready_staging_path",
            "permit_staging_path",
            "present_prerequisite_roles",
            "ready_commit_fifo",
            "run_unit",
            "scenario",
            "schema",
        ),
        label="H11 permit authority",
    )
    permit_ready = _h11_exact_object_fields(
        permit_ready,
        (
            "absent_paths",
            "boot_id",
            "harness_manifest",
            "invocation_id",
            "permit_authority",
            "phase",
            "present_outputs",
            "run_armed",
            "run_unit",
            "scenario",
            "schema",
        ),
        label="H11 PERMIT_READY receipt",
    )
    run_armed = _h11_exact_object_fields(
        run_armed,
        (
            "actor",
            "plan_path",
            "plan_sha256",
            "program",
            "ready_fifo",
            "ready_sha256",
            "receipt_path",
            "release_fifo",
            "release_sha256",
            "request_path",
            "request_sha256",
            "scenario",
            "schema",
            "unit",
        ),
        label="H11 run ARMED",
    )
    actor = _h11_exact_object_fields(
        _h11_object_member(run_armed, "actor", label="H11 run ARMED"),
        (
            "boot_id",
            "invocation_id",
            "pid",
            "proc_cgroup_raw",
            "session_id",
            "starttime",
            "stop_selector_environment",
            "unified_cgroup",
        ),
        label="H11 run ARMED actor",
    )
    harness_run_unit = _h11_text(
        _h11_object_member(
            harness_manifest,
            "run_unit",
            label="H11 harness manifest",
        ),
        label="H11 harness manifest.run_unit",
    )
    ready_boot_id = _h11_text(
        _h11_object_member(
            permit_ready,
            "boot_id",
            label="H11 PERMIT_READY receipt",
        ),
        label="H11 PERMIT_READY receipt.boot_id",
    )
    ready_invocation_id = _h11_text(
        _h11_object_member(
            permit_ready,
            "invocation_id",
            label="H11 PERMIT_READY receipt",
        ),
        label="H11 PERMIT_READY receipt.invocation_id",
    )
    if (
        _h11_text(
            _h11_object_member(
                authorization_manifest,
                "schema",
                label="H11 authorization",
            ),
            label="H11 authorization.schema",
        )
        != H11_AUTHORIZATION_SCHEMA
        or _h11_text(
            _h11_object_member(
                harness_manifest,
                "schema",
                label="H11 harness manifest",
            ),
            label="H11 harness manifest.schema",
        )
        != "scion.generic_backend.systemd_harness_manifest.v1"
        or _h11_text(
            _h11_object_member(
                harness_manifest,
                "scenario",
                label="H11 harness manifest",
            ),
            label="H11 harness manifest.scenario",
        )
        != "H11"
        or _h11_text(
            _h11_object_member(
                permit_authority,
                "schema",
                label="H11 permit authority",
            ),
            label="H11 permit authority.schema",
        )
        != H11_PERMIT_AUTHORITY_SCHEMA
        or _h11_text(
            _h11_object_member(
                permit_authority,
                "scenario",
                label="H11 permit authority",
            ),
            label="H11 permit authority.scenario",
        )
        != "H11"
        or _h11_text(
            _h11_object_member(
                permit_authority,
                "run_unit",
                label="H11 permit authority",
            ),
            label="H11 permit authority.run_unit",
        )
        != harness_run_unit
        or _h11_text(
            _h11_object_member(
                permit_ready,
                "schema",
                label="H11 PERMIT_READY receipt",
            ),
            label="H11 PERMIT_READY receipt.schema",
        )
        != H11_PERMIT_READY_SCHEMA
        or _h11_text(
            _h11_object_member(
                permit_ready,
                "scenario",
                label="H11 PERMIT_READY receipt",
            ),
            label="H11 PERMIT_READY receipt.scenario",
        )
        != "H11"
        or _h11_text(
            _h11_object_member(
                permit_ready,
                "run_unit",
                label="H11 PERMIT_READY receipt",
            ),
            label="H11 PERMIT_READY receipt.run_unit",
        )
        != harness_run_unit
        or _h11_text(
            _h11_object_member(
                permit_ready,
                "phase",
                label="H11 PERMIT_READY receipt",
            ),
            label="H11 PERMIT_READY receipt.phase",
        )
        != "h11-permit-ready"
        or _h11_object_member(
            permit_ready,
            "permit_authority",
            label="H11 PERMIT_READY receipt",
        )
        != permit_authority
        or re.fullmatch(r"scion-w3-[A-Za-z0-9_.:-]+\.service", harness_run_unit)
        is None
        or re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            ready_boot_id,
        )
        is None
        or re.fullmatch(r"[0-9a-f]{32}", ready_invocation_id) is None
        or _h11_text(
            _h11_object_member(run_armed, "schema", label="H11 run ARMED"),
            label="H11 run ARMED.schema",
        )
        != "scion.generic_backend.systemd_adversary_armed.v1"
        or _h11_text(
            _h11_object_member(run_armed, "scenario", label="H11 run ARMED"),
            label="H11 run ARMED.scenario",
        )
        != "h11-unbounded-hold"
        or _h11_text(
            _h11_object_member(run_armed, "unit", label="H11 run ARMED"),
            label="H11 run ARMED.unit",
        )
        != harness_run_unit
        or _h11_text(
            _h11_object_member(actor, "boot_id", label="H11 run ARMED actor"),
            label="H11 run ARMED actor.boot_id",
        )
        != ready_boot_id
        or _h11_text(
            _h11_object_member(
                actor,
                "invocation_id",
                label="H11 run ARMED actor",
            ),
            label="H11 run ARMED actor.invocation_id",
        )
        != ready_invocation_id
    ):
        _fail("H11 direct wire schema or phase cross-binding drifted")
    source_rows = (
        ("authorization-source", authorization_source_reference, "0444"),
        ("harness-source", harness_source_reference, "0444"),
        ("install-receipt-source", install_receipt_source_reference, "0444"),
        ("install-manifest-source", install_manifest_source_reference, "0444"),
        ("tree-receipt-source", tree_receipt_source_reference, "0444"),
        ("seal-receipt-source", seal_receipt_source_reference, "0444"),
        ("preflight-receipt-source", preflight_receipt_source_reference, "0444"),
        ("permit-ready-source", permit_ready_source_reference, "0444"),
        ("run-armed-source", run_armed_source_reference, "0600"),
    )
    source_paths: set[Path] = set()
    source_identities: set[tuple[int, int]] = set()
    for label, source, expected_mode in source_rows:
        source = _h11_exact_object_fields(
            source,
            ("device", "gid", "inode", "mode", "path", "sha256", "uid"),
            label=f"H11 {label}",
        )
        source_values = dict(source)
        source_path = _h11_path(
            source_values["path"],
            label=f"H11 {label}.path",
        )
        source_device = _h11_uint(
            source_values["device"],
            label=f"H11 {label}.device",
        )
        source_inode = _h11_uint(
            source_values["inode"],
            label=f"H11 {label}.inode",
        )
        _h11_uint(source_values["uid"], label=f"H11 {label}.uid")
        _h11_uint(source_values["gid"], label=f"H11 {label}.gid")
        _h11_sha256_text(
            source_values["sha256"],
            label=f"H11 {label}.sha256",
        )
        if (
            source_values["mode"] != expected_mode
            or source_path in source_paths
            or (source_device, source_inode) in source_identities
        ):
            _fail(f"H11 {label} class or identity drifted")
        source_paths.add(source_path)
        source_identities.add((source_device, source_inode))

    authorization_source_values = dict(authorization_source_reference)
    harness_source_values = dict(harness_source_reference)
    install_receipt_source_values = dict(install_receipt_source_reference)
    install_manifest_source_values = dict(install_manifest_source_reference)
    tree_receipt_source_values = dict(tree_receipt_source_reference)
    seal_receipt_source_values = dict(seal_receipt_source_reference)
    preflight_receipt_source_values = dict(preflight_receipt_source_reference)
    permit_ready_source_values = dict(permit_ready_source_reference)
    run_armed_source_values = dict(run_armed_source_reference)
    harness_source_full = tuple(harness_source_reference)
    install_receipt_source_path_sha = (
        ("path", install_receipt_source_values["path"]),
        ("sha256", install_receipt_source_values["sha256"]),
    )
    install_manifest_source_base = (
        ("device", install_manifest_source_values["device"]),
        ("inode", install_manifest_source_values["inode"]),
        ("mode", install_manifest_source_values["mode"]),
        ("path", install_manifest_source_values["path"]),
        ("sha256", install_manifest_source_values["sha256"]),
    )
    tree_receipt_source_base = (
        ("device", tree_receipt_source_values["device"]),
        ("inode", tree_receipt_source_values["inode"]),
        ("path", tree_receipt_source_values["path"]),
        ("sha256", tree_receipt_source_values["sha256"]),
    )
    tree_receipt_source_with_mode = (
        ("device", tree_receipt_source_values["device"]),
        ("inode", tree_receipt_source_values["inode"]),
        ("mode", tree_receipt_source_values["mode"]),
        ("path", tree_receipt_source_values["path"]),
        ("sha256", tree_receipt_source_values["sha256"]),
    )
    seal_receipt_source_base = (
        ("device", seal_receipt_source_values["device"]),
        ("inode", seal_receipt_source_values["inode"]),
        ("path", seal_receipt_source_values["path"]),
        ("sha256", seal_receipt_source_values["sha256"]),
    )
    seal_receipt_source_with_mode = (
        ("device", seal_receipt_source_values["device"]),
        ("inode", seal_receipt_source_values["inode"]),
        ("mode", seal_receipt_source_values["mode"]),
        ("path", seal_receipt_source_values["path"]),
        ("sha256", seal_receipt_source_values["sha256"]),
    )
    preflight_receipt_source_base = (
        ("device", preflight_receipt_source_values["device"]),
        ("inode", preflight_receipt_source_values["inode"]),
        ("path", preflight_receipt_source_values["path"]),
        ("sha256", preflight_receipt_source_values["sha256"]),
    )
    preflight_receipt_source_path_sha = (
        ("path", preflight_receipt_source_values["path"]),
        ("sha256", preflight_receipt_source_values["sha256"]),
    )

    if (
        _h11_object_member(
            authorization_manifest,
            "harness_manifest",
            label="H11 authorization",
        )
        != harness_source_full
        or _h11_object_member(
            permit_ready,
            "harness_manifest",
            label="H11 PERMIT_READY receipt",
        )
        != harness_source_full
        or _h11_object_member(
            authorization_manifest,
            "permit_ready",
            label="H11 authorization",
        )
        != permit_ready_source_reference
        or _h11_object_member(
            authorization_manifest,
            "run_armed",
            label="H11 authorization",
        )
        != run_armed_source_reference
        or _h11_object_member(
            permit_ready,
            "run_armed",
            label="H11 PERMIT_READY receipt",
        )
        != run_armed_source_reference
        or _h11_object_member(
            harness_manifest,
            "installer_receipt",
            label="H11 harness manifest",
        )
        != install_receipt_source_path_sha
        or _h11_object_member(
            install_receipt,
            "install_manifest",
            label="H11 install receipt",
        )
        != install_manifest_source_base
        or _h11_path(
            _h11_object_member(
                install_manifest,
                "receipt_path",
                label="H11 install manifest",
            ),
            label="H11 install manifest.receipt_path",
        )
        != _h11_path(
            install_receipt_source_values["path"],
            label="H11 install receipt source.path",
        )
    ):
        _fail("H11 direct source projection drifted")

    if (
        _h11_object_member(
            install_receipt,
            "tree_receipt",
            label="H11 install receipt",
        )
        != tree_receipt_source_base
        or _h11_object_member(
            install_manifest,
            "tree_receipt",
            label="H11 install manifest",
        )
        != tree_receipt_source_base
        or _h11_object_member(
            seal_receipt,
            "tree_receipt",
            label="H11 SEAL receipt",
        )
        != tree_receipt_source_base
        or _h11_object_member(
            preflight_receipt,
            "tree_receipt",
            label="H11 PREFLIGHT receipt",
        )
        != tree_receipt_source_with_mode
        or _h11_object_member(
            install_receipt,
            "seal_receipt",
            label="H11 install receipt",
        )
        != seal_receipt_source_base
        or _h11_object_member(
            install_manifest,
            "seal_receipt",
            label="H11 install manifest",
        )
        != seal_receipt_source_base
        or _h11_object_member(
            preflight_receipt,
            "seal_receipt",
            label="H11 PREFLIGHT receipt",
        )
        != seal_receipt_source_with_mode
        or _h11_object_member(
            install_receipt,
            "preflight_receipt",
            label="H11 install receipt",
        )
        != preflight_receipt_source_base
        or _h11_object_member(
            install_manifest,
            "preflight_receipt",
            label="H11 install manifest",
        )
        != preflight_receipt_source_base
        or _h11_object_member(
            harness_manifest,
            "preflight_receipt",
            label="H11 harness manifest",
        )
        != preflight_receipt_source_path_sha
    ):
        _fail("H11 direct receipt source projection drifted")

    if (
        type(formal_root_directory_reference) is not H11RootDirectoryReference
        or type(authority_root_directory_reference) is not H11RootDirectoryReference
        or type(harness_root_directory_reference) is not H11RootDirectoryReference
        or type(scenario_root_directory_reference) is not H11RootDirectoryReference
        or type(input_root_directory_reference) is not H11RootDirectoryReference
        or type(receipt_root_directory_reference) is not H11RootDirectoryReference
        or type(fifo_root_directory_reference) is not H11RootDirectoryReference
        or type(ready_commit_fifo_reference) is not H11RootFifoReference
        or type(permit_commit_fifo_reference) is not H11RootFifoReference
    ):
        _fail("H11 direct directory or FIFO reference type drifted")
    formal_root = formal_root_directory_reference.path
    authority_root = authority_root_directory_reference.path
    harness_root = harness_root_directory_reference.path
    scenario_root = scenario_root_directory_reference.path
    if (
        authority_root != formal_root / "authority"
        or harness_root != authority_root / "harness"
        or scenario_root != harness_root / "H11"
        or input_root_directory_reference.path != formal_root / "input"
        or receipt_root_directory_reference.path != scenario_root / "receipts"
        or fifo_root_directory_reference.path != formal_root / "fifo"
        or _h11_path(
            _h11_object_member(
                authorization_manifest,
                "formal_root",
                label="H11 authorization",
            ),
            label="H11 authorization.formal_root",
        )
        != formal_root
        or _h11_path(
            _h11_object_member(
                authorization_manifest,
                "permit_path",
                label="H11 authorization",
            ),
            label="H11 authorization.permit_path",
        )
        != scenario_root / "PERMIT.json"
        or _h11_path(
            _h11_object_member(
                permit_authority,
                "permit_path",
                label="H11 permit authority",
            ),
            label="H11 permit authority.permit_path",
        )
        != scenario_root / "PERMIT.json"
        or _h11_path(
            _h11_object_member(
                permit_authority,
                "permit_ready_path",
                label="H11 permit authority",
            ),
            label="H11 permit authority.permit_ready_path",
        )
        != _h11_path(
            permit_ready_source_values["path"],
            label="H11 PERMIT_READY source.path",
        )
        or _h11_path(
            authorization_source_values["path"],
            label="H11 authorization source.path",
        )
        != scenario_root / "AUTHORIZE-RELEASE.json"
        or _h11_path(
            harness_source_values["path"],
            label="H11 harness source.path",
        )
        != scenario_root / "MANIFEST.json"
        or _h11_path(
            permit_ready_source_values["path"],
            label="H11 PERMIT_READY source.path",
        )
        != scenario_root / "PERMIT_READY.json"
    ):
        _fail("H11 direct source or transaction layout drifted")

    if (
        _h11_path(
            run_armed_source_values["path"],
            label="H11 run ARMED source.path",
        )
        != formal_root / "work" / "RUN-MAIN-ARMED.json"
    ):
        _fail("H11 authorization cannot select a different run ARMED source")
    directory_chain = _h11_object_member(
        permit_authority,
        "directory_chain",
        label="H11 permit authority",
    )
    expected_directories = (
        formal_root_directory_reference,
        authority_root_directory_reference,
        harness_root_directory_reference,
        scenario_root_directory_reference,
        input_root_directory_reference,
        receipt_root_directory_reference,
        fifo_root_directory_reference,
    )
    if type(directory_chain) is not tuple or len(directory_chain) != 7:
        _fail("H11 direct directory chain drifted")
    for row, reference in zip(directory_chain, expected_directories):
        if row != (
            ("device", str(reference.device)),
            ("gid", str(reference.gid)),
            ("inode", str(reference.inode)),
            ("mode", format(reference.mode, "04o")),
            ("path", str(reference.path)),
            ("role", reference.role),
            ("uid", str(reference.uid)),
        ):
            _fail("H11 direct directory reference drifted")
    if (
        _h11_object_member(permit_authority, "ready_commit_fifo", label="H11 permit authority")
        != tuple(sorted(ready_commit_fifo_reference.reference.items()))
        or _h11_object_member(permit_authority, "permit_commit_fifo", label="H11 permit authority")
        != tuple(sorted(permit_commit_fifo_reference.reference.items()))
    ):
        _fail("H11 direct commit FIFO reference drifted")


def _build_h11_tree_indirect_specs(
    *,
    tree_receipt: H11RootFrozenJsonObject,
    preflight_receipt: H11RootFrozenJsonObject,
    harness_manifest: H11RootFrozenJsonObject,
    run_armed: H11RootFrozenJsonObject,
    formal_root_directory_reference: H11RootDirectoryReference,
    authority_root_directory_reference: H11RootDirectoryReference,
    input_root_directory_reference: H11RootDirectoryReference,
    fifo_root_directory_reference: H11RootDirectoryReference,
    ready_commit_fifo_reference: H11RootFifoReference,
    permit_commit_fifo_reference: H11RootFifoReference,
    require_root: bool,
    process_euid: int,
    process_egid: int,
) -> tuple[
    int,
    int,
    tuple[H11RootValidatedFifo, ...],
    tuple[H11RootIndirectAuthoritySpec, ...],
]:
    tree_receipt = _h11_exact_object_fields(
        tree_receipt,
        (
            "authority_root",
            "fifo_root",
            "fifos",
            "fixture_gid",
            "fixture_group",
            "fixture_uid",
            "fixture_user",
            "formal_root",
            "input_root",
            "phase",
            "prepare_manifest",
            "schema",
            "sealed_root",
            "work_root",
        ),
        label="H11 TREE receipt",
    )
    if _h11_text(
        _h11_object_member(tree_receipt, "schema", label="H11 TREE receipt"),
        label="H11 TREE receipt.schema",
    ) != TREE_RECEIPT_SCHEMA or _h11_text(
        _h11_object_member(tree_receipt, "phase", label="H11 TREE receipt"),
        label="H11 TREE receipt.phase",
    ) != "tree-prepared":
        _fail("H11 TREE schema or phase drifted")
    fixture_uid = _h11_uint(
        _h11_object_member(tree_receipt, "fixture_uid", label="H11 TREE receipt"),
        label="H11 TREE fixture_uid",
    )
    fixture_gid = _h11_uint(
        _h11_object_member(tree_receipt, "fixture_gid", label="H11 TREE receipt"),
        label="H11 TREE fixture_gid",
    )
    fixture_user = _h11_text(
        _h11_object_member(tree_receipt, "fixture_user", label="H11 TREE receipt"),
        label="H11 TREE fixture_user",
    )
    fixture_group = _h11_text(
        _h11_object_member(tree_receipt, "fixture_group", label="H11 TREE receipt"),
        label="H11 TREE fixture_group",
    )
    if (
        not fixture_user
        or any(ord(character) < 0x20 for character in fixture_user)
        or not fixture_group
        or any(ord(character) < 0x20 for character in fixture_group)
        or fixture_uid == 0
    ):
        _fail("H11 TREE fixture identity is not canonical non-root authority")
    fixture_owners = ((fixture_uid, fixture_gid),)
    directory_roles = (
        (
            "formal_root",
            "formal-root",
            0o711,
            formal_root_directory_reference,
            formal_root_directory_reference.path,
            ((formal_root_directory_reference.uid, formal_root_directory_reference.gid),),
        ),
        (
            "sealed_root",
            "sealed-root",
            0o555,
            None,
            formal_root_directory_reference.path / "sealed",
            ((0, 0),) if require_root else None,
        ),
        (
            "input_root",
            "input-root",
            0o555,
            input_root_directory_reference,
            input_root_directory_reference.path,
            ((input_root_directory_reference.uid, input_root_directory_reference.gid),),
        ),
        (
            "work_root",
            "work-root",
            0o700,
            None,
            formal_root_directory_reference.path / "work",
            fixture_owners,
        ),
        (
            "fifo_root",
            "fifo-root",
            0o711,
            fifo_root_directory_reference,
            fifo_root_directory_reference.path,
            ((fifo_root_directory_reference.uid, fifo_root_directory_reference.gid),),
        ),
        (
            "authority_root",
            "authority-root",
            0o700,
            authority_root_directory_reference,
            authority_root_directory_reference.path,
            ((authority_root_directory_reference.uid, authority_root_directory_reference.gid),),
        ),
    )
    tree_inputs: list[
        tuple[str, str, int | None, Path, str, int, int, int | None, tuple[tuple[int, int], ...] | None]
    ] = []
    for field, role, mode, direct_reference, expected_path, accepted_owners in directory_roles:
        row = _h11_object_member(tree_receipt, field, label="H11 TREE receipt")
        _h11_exact_object_fields(
            row,
            ("device", "inode", "path"),
            label=f"H11 TREE {role}",
        )
        path = _h11_path(
            _h11_object_member(row, "path", label=role),
            label=f"{role}.path",
        )
        device = _h11_uint(
            _h11_object_member(row, "device", label=role),
            label=f"{role}.device",
        )
        inode = _h11_uint(
            _h11_object_member(row, "inode", label=role),
            label=f"{role}.inode",
        )
        if path != expected_path:
            _fail(f"H11 TREE {role} path drifted")
        if direct_reference is not None and (
            direct_reference.role != role
            or direct_reference.path != path
            or (direct_reference.device, direct_reference.inode) != (device, inode)
            or direct_reference.mode != mode
            or (require_root and (direct_reference.uid, direct_reference.gid) != (0, 0))
        ):
            _fail(f"H11 TREE {role} direct directory projection drifted")
        tree_inputs.append(
            (
                role,
                f"tree/directory/{role}",
                None,
                path,
                "directory",
                device,
                inode,
                mode,
                accepted_owners,
            )
        )
    if (
        len({row[3] for row in tree_inputs}) != len(tree_inputs)
        or len({(row[5], row[6]) for row in tree_inputs}) != len(tree_inputs)
    ):
        _fail("H11 TREE directory authority is duplicated or aliased")
    fifo_values = _h11_object_member(tree_receipt, "fifos", label="H11 TREE receipt")
    preflight_fifo_values = _h11_object_member(
        preflight_receipt, "fifos", label="H11 PREFLIGHT receipt"
    )
    if (
        type(fifo_values) is not tuple
        or len(fifo_values) != 8
        or type(preflight_fifo_values) is not tuple
        or len(preflight_fifo_values) != 8
    ):
        _fail("H11 TREE/PREFLIGHT FIFO inventory drifted")
    for row in preflight_fifo_values:
        _h11_exact_object_fields(
            row,
            ("device", "gid", "inode", "mode", "owner", "path", "role", "uid"),
            label="H11 PREFLIGHT FIFO",
        )
        _h11_text(
            _h11_object_member(row, "role", label="H11 PREFLIGHT FIFO"),
            label="H11 PREFLIGHT FIFO.role",
        )
        _h11_path(
            _h11_object_member(row, "path", label="H11 PREFLIGHT FIFO"),
            label="H11 PREFLIGHT FIFO.path",
        )
        _h11_text(
            _h11_object_member(row, "owner", label="H11 PREFLIGHT FIFO"),
            label="H11 PREFLIGHT FIFO.owner",
        )
        _h11_uint(
            _h11_object_member(row, "uid", label="H11 PREFLIGHT FIFO"),
            label="H11 PREFLIGHT FIFO.uid",
        )
        _h11_uint(
            _h11_object_member(row, "gid", label="H11 PREFLIGHT FIFO"),
            label="H11 PREFLIGHT FIFO.gid",
        )
        _h11_text(
            _h11_object_member(row, "mode", label="H11 PREFLIGHT FIFO"),
            label="H11 PREFLIGHT FIFO.mode",
        )
        _h11_uint(
            _h11_object_member(row, "device", label="H11 PREFLIGHT FIFO"),
            label="H11 PREFLIGHT FIFO.device",
        )
        _h11_uint(
            _h11_object_member(row, "inode", label="H11 PREFLIGHT FIFO"),
            label="H11 PREFLIGHT FIFO.inode",
        )
    if fifo_values != preflight_fifo_values:
        _fail("H11 TREE/PREFLIGHT FIFO inventory drifted")
    validated: list[H11RootValidatedFifo] = []
    for row in fifo_values:
        _h11_exact_object_fields(
            row,
            ("device", "gid", "inode", "mode", "owner", "path", "role", "uid"),
            label="H11 TREE FIFO",
        )
        role = _h11_text(_h11_object_member(row, "role", label="H11 TREE FIFO"), label="H11 TREE FIFO.role")
        owner = _h11_text(_h11_object_member(row, "owner", label="H11 TREE FIFO"), label="H11 TREE FIFO.owner")
        uid = _h11_uint(_h11_object_member(row, "uid", label="H11 TREE FIFO"), label="H11 TREE FIFO.uid")
        gid = _h11_uint(_h11_object_member(row, "gid", label="H11 TREE FIFO"), label="H11 TREE FIFO.gid")
        device = _h11_uint(_h11_object_member(row, "device", label="H11 TREE FIFO"), label="H11 TREE FIFO.device")
        inode = _h11_uint(_h11_object_member(row, "inode", label="H11 TREE FIFO"), label="H11 TREE FIFO.inode")
        mode_text = _h11_text(_h11_object_member(row, "mode", label="H11 TREE FIFO"), label="H11 TREE FIFO.mode")
        if mode_text != "0600":
            _fail("H11 TREE FIFO mode drifted")
        path = _h11_path(
            _h11_object_member(row, "path", label="H11 TREE FIFO"),
            label="H11 TREE FIFO.path",
        )
        if path.parent != fifo_root_directory_reference.path:
            _fail("H11 TREE FIFO path is outside the retained FIFO root")
        is_ready_commit = role == "h11-ready-commit"
        is_permit_commit = role == "h11-permit-commit"
        is_commit = is_ready_commit or is_permit_commit
        expected_owner = "root" if is_commit else "fixture"
        expected_uid_gid = (0, 0) if is_commit else (fixture_uid, fixture_gid)
        if owner != expected_owner or (uid, gid) != expected_uid_gid:
            _fail("H11 TREE FIFO owner drifted")
        direct_reference = (
            ready_commit_fifo_reference
            if is_ready_commit
            else permit_commit_fifo_reference
            if is_permit_commit
            else None
        )
        accepted_owners = (
            direct_reference.accepted_owners
            if direct_reference is not None
            else fixture_owners
        )
        if direct_reference is not None and (
            direct_reference.path != path
            or (direct_reference.device, direct_reference.inode) != (device, inode)
            or direct_reference.mode != 0o600
            or (direct_reference.uid, direct_reference.gid) != (0, 0)
            or direct_reference.accepted_owners
            != (
                ((0, 0),)
                if require_root
                else tuple(sorted({(0, 0), (process_euid, process_egid)}))
            )
        ):
            _fail("H11 TREE commit FIFO owner translation drifted")
        validated.append(
            H11RootValidatedFifo(
                role,
                path,
                owner,
                uid,
                gid,
                0o600,
                device,
                inode,
                accepted_owners,
            )
        )
    if (
        len({row.path for row in validated}) != len(validated)
        or len({(row.device, row.inode) for row in validated}) != len(validated)
    ):
        _fail("H11 TREE FIFO authority is duplicated or aliased")
    if tuple(item.role for item in validated) != tuple(sorted(item.role for item in validated)):
        _fail("H11 TREE FIFO order drifted")
    expected_fifo_roles = (
        "closer-ready",
        "closer-release",
        "exec-stop-post-ready",
        "exec-stop-post-release",
        "h11-permit-commit",
        "h11-ready-commit",
        "run-main-ready",
        "run-main-release",
    )
    if tuple(item.role for item in validated) != expected_fifo_roles:
        _fail("H11 TREE FIFO role closure drifted")
    directory_by_role = {
        spec[0]: spec for spec in tree_inputs[:6]
    }
    if (
        directory_by_role["formal-root"][3]
        != formal_root_directory_reference.path
        or (directory_by_role["formal-root"][5], directory_by_role["formal-root"][6])
        != (formal_root_directory_reference.device, formal_root_directory_reference.inode)
        or directory_by_role["authority-root"][3]
        != authority_root_directory_reference.path
        or (directory_by_role["authority-root"][5], directory_by_role["authority-root"][6])
        != (authority_root_directory_reference.device, authority_root_directory_reference.inode)
        or directory_by_role["input-root"][3]
        != input_root_directory_reference.path
        or (directory_by_role["input-root"][5], directory_by_role["input-root"][6])
        != (input_root_directory_reference.device, input_root_directory_reference.inode)
        or directory_by_role["fifo-root"][3]
        != fifo_root_directory_reference.path
        or (directory_by_role["fifo-root"][5], directory_by_role["fifo-root"][6])
        != (fifo_root_directory_reference.device, fifo_root_directory_reference.inode)
        or directory_by_role["sealed-root"][3]
        != formal_root_directory_reference.path / "sealed"
        or directory_by_role["work-root"][3]
        != formal_root_directory_reference.path / "work"
    ):
        _fail("H11 TREE directory projection drifted")
    fifo_by_role = {row.role: row for row in validated}
    if (
        fifo_by_role["h11-ready-commit"].path
        != ready_commit_fifo_reference.path
        or (
            fifo_by_role["h11-ready-commit"].device,
            fifo_by_role["h11-ready-commit"].inode,
        )
        != (
            ready_commit_fifo_reference.device,
            ready_commit_fifo_reference.inode,
        )
        or fifo_by_role["h11-permit-commit"].path
        != permit_commit_fifo_reference.path
        or (
            fifo_by_role["h11-permit-commit"].device,
            fifo_by_role["h11-permit-commit"].inode,
        )
        != (
            permit_commit_fifo_reference.device,
            permit_commit_fifo_reference.inode,
        )
    ):
        _fail("H11 TREE commit FIFO projection drifted")
    acquisition_values = _h11_object_member(
        harness_manifest,
        "acquisitions",
        label="H11 harness manifest",
    )
    if type(acquisition_values) is not tuple or len(acquisition_values) != 3:
        _fail("H11 acquisition inventory drifted")
    expected_acquisition_roles = ("run-main", "exec-stop-post", "closer")
    acquisition_fifo_roles = (
        ("run-main-ready", "run-main-release"),
        ("exec-stop-post-ready", "exec-stop-post-release"),
        ("closer-ready", "closer-release"),
    )
    run_main_acquisition: H11RootFrozenJsonObject | None = None
    acquisition_armed_paths: list[Path] = []
    for acquisition, expected_role, fifo_roles in zip(
        acquisition_values,
        expected_acquisition_roles,
        acquisition_fifo_roles,
    ):
        _h11_exact_object_fields(
            acquisition,
            ("armed_receipt_path", "ready_fifo", "release_fifo", "role"),
            label=f"H11 acquisition {expected_role}",
        )
        if _h11_text(
            _h11_object_member(
                acquisition,
                "role",
                label=f"H11 acquisition {expected_role}",
            ),
            label=f"H11 acquisition {expected_role}.role",
        ) != expected_role:
            _fail("H11 acquisition role order drifted")
        armed_receipt_path = _h11_path(
            _h11_object_member(
                acquisition,
                "armed_receipt_path",
                label=f"H11 acquisition {expected_role}",
            ),
            label=f"H11 acquisition {expected_role}.armed_receipt_path",
        )
        if armed_receipt_path.parent != formal_root_directory_reference.path / "work":
            _fail(f"H11 acquisition {expected_role} ARMED path drifted")
        acquisition_armed_paths.append(armed_receipt_path)
        ready_acquisition = _h11_object_member(
            acquisition,
            "ready_fifo",
            label=f"H11 acquisition {expected_role}",
        )
        release_acquisition = _h11_object_member(
            acquisition,
            "release_fifo",
            label=f"H11 acquisition {expected_role}",
        )
        ready_row = fifo_by_role[fifo_roles[0]]
        release_row = fifo_by_role[fifo_roles[1]]
        if (
            ready_acquisition != (
                ("device", str(ready_row.device)),
                ("inode", str(ready_row.inode)),
                ("path", str(ready_row.path)),
            )
            or release_acquisition != (
                ("device", str(release_row.device)),
                ("inode", str(release_row.inode)),
                ("path", str(release_row.path)),
            )
        ):
            _fail(f"H11 acquisition {expected_role} FIFO projection drifted")
        if expected_role == "run-main":
            run_main_acquisition = acquisition
    if len(set(acquisition_armed_paths)) != len(acquisition_armed_paths):
        _fail("H11 acquisition ARMED paths are duplicated")
    if run_main_acquisition is None:
        _fail("H11 run-main acquisition is missing")
    if (
        _h11_object_member(
            run_armed,
            "ready_fifo",
            label="H11 run ARMED",
        )
        != _h11_object_member(
            run_main_acquisition,
            "ready_fifo",
            label="H11 run-main acquisition",
        )
        or _h11_object_member(
            run_armed,
            "release_fifo",
            label="H11 run ARMED",
        )
        != _h11_object_member(
            run_main_acquisition,
            "release_fifo",
            label="H11 run-main acquisition",
        )
    ):
        _fail("H11 run ARMED FIFO projection drifted")
    for row in validated:
        tree_inputs.append(
            (
                row.role,
                f"tree/fifo/{row.role}",
                None,
                row.path,
                "fifo",
                row.device,
                row.inode,
                row.mode,
                row.accepted_owners,
            )
        )
    prepare = _h11_exact_object_fields(
        _h11_object_member(tree_receipt, "prepare_manifest", label="H11 TREE receipt"),
        ("device", "inode", "path", "sha256"),
        label="H11 TREE prepare manifest",
    )
    _h11_sha256_text(
        _h11_object_member(prepare, "sha256", label="H11 TREE prepare manifest"),
        label="H11 TREE prepare manifest.sha256",
    )
    tree_inputs.append(
        (
            "prepare-manifest",
            "tree/prepare-manifest",
            None,
            _h11_path(_h11_object_member(prepare, "path", label="H11 prepare manifest"), label="H11 prepare manifest.path"),
            "regular",
            _h11_uint(_h11_object_member(prepare, "device", label="H11 prepare manifest"), label="H11 prepare manifest.device"),
            _h11_uint(_h11_object_member(prepare, "inode", label="H11 prepare manifest"), label="H11 prepare manifest.inode"),
            None,
            None,
        )
    )
    if (
        len({row[3] for row in tree_inputs}) != len(tree_inputs)
        or len({(row[5], row[6]) for row in tree_inputs}) != len(tree_inputs)
    ):
        _fail("H11 TREE indirect authority is duplicated or aliased")
    specs = tuple(
        _make_h11_indirect_authority_spec(
            semantic_role=row[0],
            equivalence_class=row[1],
            install_ordinal=row[2],
            path=row[3],
            kind=row[4],
            device=row[5],
            inode=row[6],
            mode=row[7],
            accepted_owners=row[8],
        )
        for row in tree_inputs
    )
    ready_row = tuple(item for item in validated if item.role == "h11-ready-commit")
    permit_row = tuple(item for item in validated if item.role == "h11-permit-commit")
    ready_spec = tuple(item for item in specs if item.semantic_role == "h11-ready-commit")
    permit_spec = tuple(item for item in specs if item.semantic_role == "h11-permit-commit")
    if (
        len(ready_row) != 1
        or len(permit_row) != 1
        or len(ready_spec) != 1
        or len(permit_spec) != 1
        or ready_row[0].accepted_owners is not ready_commit_fifo_reference.accepted_owners
        or permit_row[0].accepted_owners is not permit_commit_fifo_reference.accepted_owners
        or ready_spec[0].accepted_owners is not ready_commit_fifo_reference.accepted_owners
        or permit_spec[0].accepted_owners is not permit_commit_fifo_reference.accepted_owners
    ):
        _fail("H11 commit owner policy identity drifted")
    return fixture_uid, fixture_gid, tuple(validated), specs


def _build_h11_seal_indirect_specs(
    *,
    seal_receipt: H11RootFrozenJsonObject,
    tree_receipt: H11RootFrozenJsonObject,
    preflight_receipt: H11RootFrozenJsonObject,
    install_receipt: H11RootFrozenJsonObject,
    install_manifest: H11RootFrozenJsonObject,
    harness_manifest: H11RootFrozenJsonObject,
    run_armed: H11RootFrozenJsonObject,
    install_receipt_source_reference: H11RootFrozenJsonObject,
    install_manifest_source_reference: H11RootFrozenJsonObject,
    preflight_receipt_source_reference: H11RootFrozenJsonObject,
    formal_root: Path,
    require_root: bool,
) -> tuple[H11RootIndirectAuthoritySpec, ...]:
    seal_receipt = _h11_exact_object_fields(
        seal_receipt,
        ("files", "formal_root", "phase", "schema", "seal_manifest", "tree_receipt"),
        label="H11 SEAL receipt",
    )
    if (
        _h11_text(
            _h11_object_member(seal_receipt, "schema", label="H11 SEAL receipt"),
            label="H11 SEAL receipt.schema",
        )
        != SEAL_RECEIPT_SCHEMA
        or _h11_text(
            _h11_object_member(seal_receipt, "phase", label="H11 SEAL receipt"),
            label="H11 SEAL receipt.phase",
        )
        != "static-authority-sealed"
    ):
        _fail("H11 SEAL schema or phase drifted")
    seal_formal_root = _h11_exact_object_fields(
        _h11_object_member(seal_receipt, "formal_root", label="H11 SEAL receipt"),
        ("device", "inode", "path"),
        label="H11 SEAL formal root",
    )
    if (
        seal_formal_root
        != _h11_object_member(tree_receipt, "formal_root", label="H11 TREE receipt")
        or _h11_path(
            _h11_object_member(
                seal_formal_root,
                "path",
                label="H11 SEAL formal root",
            ),
            label="H11 SEAL formal root.path",
        )
        != formal_root
    ):
        _fail("H11 SEAL formal root drifted")
    seal_inputs: list[
        tuple[str, str, int | None, Path, str, int, int, int | None, tuple[tuple[int, int], ...] | None]
    ] = []
    seal_manifest = _h11_exact_object_fields(
        _h11_object_member(seal_receipt, "seal_manifest", label="H11 SEAL receipt"),
        ("device", "inode", "path", "sha256"),
        label="H11 seal manifest",
    )
    seal_manifest_path = _h11_path(
        _h11_object_member(seal_manifest, "path", label="H11 seal manifest"),
        label="H11 seal manifest.path",
    )
    seal_manifest_device = _h11_uint(
        _h11_object_member(seal_manifest, "device", label="H11 seal manifest"),
        label="H11 seal manifest.device",
    )
    seal_manifest_inode = _h11_uint(
        _h11_object_member(seal_manifest, "inode", label="H11 seal manifest"),
        label="H11 seal manifest.inode",
    )
    _h11_sha256_text(
        _h11_object_member(seal_manifest, "sha256", label="H11 seal manifest"),
        label="H11 seal manifest.sha256",
    )
    seal_inputs.append(
        (
            "seal-manifest",
            "seal/manifest",
            None,
            seal_manifest_path,
            "regular",
            seal_manifest_device,
            seal_manifest_inode,
            None,
            None,
        )
    )
    files = _h11_object_member(seal_receipt, "files", label="H11 SEAL receipt")
    if type(files) is not tuple or not files:
        _fail("H11 SEAL files inventory is invalid")
    parsed_files: list[tuple[str, Path, str, int, int, int]] = []
    seen_roles: set[str] = set()
    seen_paths = {seal_manifest_path}
    seen_identities = {(seal_manifest_device, seal_manifest_inode)}
    for row in files:
        _h11_exact_object_fields(row, ("device", "inode", "mode", "path", "role", "sha256"), label="H11 SEAL file")
        role = _h11_text(_h11_object_member(row, "role", label="H11 SEAL file"), label="H11 SEAL file.role")
        mode_text = _h11_text(_h11_object_member(row, "mode", label="H11 SEAL file"), label="H11 SEAL file.mode")
        sha256 = _h11_sha256_text(
            _h11_object_member(row, "sha256", label="H11 SEAL file"),
            label="H11 SEAL file.sha256",
        )
        path = _h11_path(
            _h11_object_member(row, "path", label="H11 SEAL file"),
            label="H11 SEAL file.path",
        )
        device = _h11_uint(
            _h11_object_member(row, "device", label="H11 SEAL file"),
            label="H11 SEAL file.device",
        )
        inode = _h11_uint(
            _h11_object_member(row, "inode", label="H11 SEAL file"),
            label="H11 SEAL file.inode",
        )
        if (
            re.fullmatch(r"[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*", role) is None
            or mode_text != "0444"
            or path.parent not in {formal_root / "sealed", formal_root / "input"}
            or role in seen_roles
            or path in seen_paths
            or (device, inode) in seen_identities
        ):
            _fail("H11 SEAL file mode drifted")
        seen_roles.add(role)
        seen_paths.add(path)
        seen_identities.add((device, inode))
        parsed_files.append((role, path, sha256, device, inode, 0o444))
    ordered_files = tuple(item for item in parsed_files if item[0] == "preflight-manifest") + tuple(
        sorted((item for item in parsed_files if item[0] != "preflight-manifest"), key=lambda item: item[0])
    )
    files_by_role = {row[0]: row for row in parsed_files}
    files_by_hashed_reference = {(row[1], row[2]): row for row in parsed_files}

    if "preflight-manifest" not in files_by_role:
        _fail("H11 SEAL preflight inventory class is missing")
    preflight_row = files_by_role["preflight-manifest"]
    preflight_inventory = _h11_exact_object_fields(
        _h11_object_member(
            preflight_receipt,
            "inventory_manifest",
            label="H11 PREFLIGHT receipt",
        ),
        ("device", "inode", "mode", "path", "sha256"),
        label="H11 PREFLIGHT inventory manifest",
    )
    preflight_full_reference = (
        ("device", str(preflight_row[3])),
        ("inode", str(preflight_row[4])),
        ("mode", format(preflight_row[5], "04o")),
        ("path", str(preflight_row[1])),
        ("sha256", preflight_row[2]),
    )
    harness_static_inventory = _h11_exact_object_fields(
        _h11_object_member(
            harness_manifest,
            "static_inventory",
            label="H11 harness manifest",
        ),
        ("path", "sha256"),
        label="H11 harness static inventory",
    )
    if (
        preflight_inventory != preflight_full_reference
        or harness_static_inventory
        != (("path", str(preflight_row[1])), ("sha256", preflight_row[2]))
    ):
        _fail("H11 SEAL preflight inventory class drifted")

    named_member_roles = {"preflight-manifest"}
    for harness_field, seal_role in (
        ("descriptor", "start-descriptor"),
        ("harness_program", "harness-program"),
    ):
        if seal_role not in files_by_role:
            _fail(f"H11 SEAL {seal_role} class is missing")
        seal_row = files_by_role[seal_role]
        harness_reference = _h11_exact_object_fields(
            _h11_object_member(
                harness_manifest,
                harness_field,
                label="H11 harness manifest",
            ),
            ("path", "sha256"),
            label=f"H11 harness {harness_field}",
        )
        if harness_reference != (
            ("path", str(seal_row[1])),
            ("sha256", seal_row[2]),
        ):
            _fail(f"H11 SEAL {seal_role} class drifted")
        named_member_roles.add(seal_role)

    if "installer-program" not in files_by_role:
        _fail("H11 SEAL installer-program class is missing")
    installer_row = files_by_role["installer-program"]
    installer_reference = _h11_exact_object_fields(
        _h11_object_member(install_receipt, "installer", label="H11 install receipt"),
        ("device", "inode", "mode", "path", "sha256"),
        label="H11 install receipt installer",
    )
    if installer_reference != (
        ("device", str(installer_row[3])),
        ("inode", str(installer_row[4])),
        ("mode", format(installer_row[5], "04o")),
        ("path", str(installer_row[1])),
        ("sha256", installer_row[2]),
    ):
        _fail("H11 SEAL installer-program class drifted")
    named_member_roles.add("installer-program")

    install_units = _h11_object_member(
        install_receipt,
        "units",
        label="H11 install receipt",
    )
    if type(install_units) is not tuple:
        _fail("H11 SEAL install source inventory is invalid")
    for unit_row in install_units:
        role = _h11_text(
            _h11_object_member(unit_row, "role", label="H11 install unit"),
            label="H11 install unit.role",
        )
        source_reference = _h11_exact_object_fields(
            _h11_object_member(unit_row, "source", label="H11 install unit"),
            ("device", "inode", "mode", "path", "sha256"),
            label=f"H11 install source {role}",
        )
        if role not in files_by_role:
            _fail(f"H11 SEAL install source {role} class drifted")
        seal_row = files_by_role[role]
        if source_reference != (
            ("device", str(seal_row[3])),
            ("inode", str(seal_row[4])),
            ("mode", format(seal_row[5], "04o")),
            ("path", str(seal_row[1])),
            ("sha256", seal_row[2]),
        ):
            _fail(f"H11 SEAL install source {role} class drifted")
        named_member_roles.add(role)

    static_roles = _h11_object_member(
        harness_manifest,
        "static_roles",
        label="H11 harness manifest",
    )
    if type(static_roles) is not tuple or len(static_roles) != 3:
        _fail("H11 SEAL static role closure drifted")
    harness_run_unit = _h11_text(
        _h11_object_member(harness_manifest, "run_unit", label="H11 harness manifest"),
        label="H11 harness manifest.run_unit",
    )
    harness_closer_unit = _h11_text(
        _h11_object_member(
            harness_manifest,
            "closer_unit",
            label="H11 harness manifest",
        ),
        label="H11 harness manifest.closer_unit",
    )
    expected_static_roles = (
        ("run-main", harness_run_unit, "adversary", "h11-unbounded-hold"),
        ("exec-stop-post", harness_run_unit, "observer", "exec-stop-post"),
        ("closer", harness_closer_unit, "observer", "closer"),
    )
    expected_static_member_roles = (
        ("run-plan", "run-program"),
        ("stop-plan", "stop-program"),
        ("close-plan", "close-program"),
    )
    static_members: list[tuple[tuple[str, Path, str, int, int, int], tuple[str, Path, str, int, int, int]]] = []
    static_member_roles: set[str] = set()
    for static_role, expected, expected_member_roles in zip(
        static_roles,
        expected_static_roles,
        expected_static_member_roles,
    ):
        static_role = _h11_exact_object_fields(
            static_role,
            ("mode", "owner", "plan", "program", "role", "unit"),
            label=f"H11 SEAL static role {expected[0]}",
        )
        if (
            _h11_text(
                _h11_object_member(static_role, "role", label="H11 SEAL static role"),
                label="H11 SEAL static role.role",
            ),
            _h11_text(
                _h11_object_member(static_role, "unit", label="H11 SEAL static role"),
                label="H11 SEAL static role.unit",
            ),
            _h11_text(
                _h11_object_member(static_role, "owner", label="H11 SEAL static role"),
                label="H11 SEAL static role.owner",
            ),
            _h11_text(
                _h11_object_member(static_role, "mode", label="H11 SEAL static role"),
                label="H11 SEAL static role.mode",
            ),
        ) != expected:
            _fail("H11 SEAL static role tuple drifted")
        matched_members: list[tuple[str, Path, str, int, int, int]] = []
        for member_name, expected_member_role in zip(
            ("plan", "program"),
            expected_member_roles,
        ):
            reference = _h11_exact_object_fields(
                _h11_object_member(
                    static_role,
                    member_name,
                    label="H11 SEAL static role",
                ),
                ("path", "sha256"),
                label=f"H11 SEAL static role {expected[0]} {member_name}",
            )
            path = _h11_path(
                _h11_object_member(
                    reference,
                    "path",
                    label=f"H11 SEAL static role {member_name}",
                ),
                label=f"H11 SEAL static role {member_name}.path",
            )
            sha256 = _h11_sha256_text(
                _h11_object_member(
                    reference,
                    "sha256",
                    label=f"H11 SEAL static role {member_name}",
                ),
                label=f"H11 SEAL static role {member_name}.sha256",
            )
            if (path, sha256) not in files_by_hashed_reference:
                _fail(f"H11 SEAL static role {expected[0]} {member_name} is unbound")
            matched = files_by_hashed_reference[(path, sha256)]
            if matched[0] != expected_member_role:
                _fail(
                    f"H11 SEAL static role {expected[0]} {member_name} "
                    "is bound to the wrong SEAL role"
                )
            matched_members.append(matched)
        static_members.append((matched_members[0], matched_members[1]))
        static_member_roles.update((matched_members[0][0], matched_members[1][0]))
    if (
        len(static_member_roles) != 6
        or static_member_roles & named_member_roles
    ):
        _fail("H11 SEAL static role classes are duplicated or aliased")

    run_plan_row, run_program_row = static_members[0]
    armed_plan_path = _h11_path(
        _h11_object_member(run_armed, "plan_path", label="H11 run ARMED"),
        label="H11 run ARMED.plan_path",
    )
    armed_plan_sha256 = _h11_sha256_text(
        _h11_object_member(run_armed, "plan_sha256", label="H11 run ARMED"),
        label="H11 run ARMED.plan_sha256",
    )
    armed_program = _h11_exact_object_fields(
        _h11_object_member(run_armed, "program", label="H11 run ARMED"),
        ("identity", "path", "sha256"),
        label="H11 run ARMED program",
    )
    armed_program_identity = _h11_exact_object_fields(
        _h11_object_member(
            armed_program,
            "identity",
            label="H11 run ARMED program",
        ),
        ("device", "inode", "mode"),
        label="H11 run ARMED program identity",
    )
    armed_identity_values = dict(armed_program_identity)
    if (
        armed_plan_path != run_plan_row[1]
        or armed_plan_sha256 != run_plan_row[2]
        or _h11_path(
            _h11_object_member(armed_program, "path", label="H11 run ARMED program"),
            label="H11 run ARMED program.path",
        )
        != run_program_row[1]
        or _h11_sha256_text(
            _h11_object_member(
                armed_program,
                "sha256",
                label="H11 run ARMED program",
            ),
            label="H11 run ARMED program.sha256",
        )
        != run_program_row[2]
        or type(armed_identity_values["device"]) is not int
        or type(armed_identity_values["inode"]) is not int
        or type(armed_identity_values["mode"]) is not int
        or armed_identity_values["device"] != run_program_row[3]
        or armed_identity_values["inode"] != run_program_row[4]
        or armed_identity_values["mode"] != run_program_row[5]
    ):
        _fail("H11 SEAL run ARMED plan or program class drifted")

    for role, path, _sha256, device, inode, mode in ordered_files:
        seal_inputs.append((
            "preflight-manifest" if role == "preflight-manifest" else role,
            "preflight/inventory" if role == "preflight-manifest" else f"seal/file/{role}",
            None, path, "regular", device, inode, mode,
            ((0, 0),) if require_root else None,
        ))
    return tuple(
        _make_h11_indirect_authority_spec(
            semantic_role=row[0], equivalence_class=row[1], install_ordinal=row[2],
            path=row[3], kind=row[4], device=row[5], inode=row[6], mode=row[7],
            accepted_owners=row[8],
        )
        for row in seal_inputs
    )


def _prove_h11_preflight_snapshot_bindings(
    *,
    preflight_receipt: H11RootFrozenJsonObject,
    tree_receipt: H11RootFrozenJsonObject,
    seal_receipt: H11RootFrozenJsonObject,
    harness_manifest: H11RootFrozenJsonObject,
    preflight_receipt_source_reference: H11RootFrozenJsonObject,
    formal_root: Path,
    validated_fifos: tuple[H11RootValidatedFifo, ...],
) -> None:
    if _h11_text(_h11_object_member(preflight_receipt, "schema", label="H11 PREFLIGHT receipt"), label="H11 PREFLIGHT receipt.schema") != PREFLIGHT_RECEIPT_SCHEMA or _h11_text(_h11_object_member(preflight_receipt, "phase", label="H11 PREFLIGHT receipt"), label="H11 PREFLIGHT receipt.phase") != "static-preflight-complete":
        _fail("H11 PREFLIGHT schema or phase drifted")
    if _h11_path(_h11_object_member(preflight_receipt, "formal_root", label="H11 PREFLIGHT receipt"), label="H11 PREFLIGHT formal_root") != formal_root:
        _fail("H11 PREFLIGHT formal root drifted")
    fifo_values = _h11_object_member(preflight_receipt, "fifos", label="H11 PREFLIGHT receipt")
    if type(fifo_values) is not tuple or len(fifo_values) != len(validated_fifos):
        _fail("H11 PREFLIGHT FIFO projection drifted")


def _build_h11_install_target_specs(
    *,
    install_receipt: H11RootFrozenJsonObject,
    install_manifest: H11RootFrozenJsonObject,
    harness_manifest: H11RootFrozenJsonObject,
    seal_receipt: H11RootFrozenJsonObject,
    install_receipt_source_reference: H11RootFrozenJsonObject,
    install_manifest_source_reference: H11RootFrozenJsonObject,
    formal_root: Path,
    require_root: bool,
) -> tuple[H11RootIndirectAuthoritySpec, ...]:
    if _h11_text(_h11_object_member(install_receipt, "schema", label="H11 install receipt"), label="H11 install receipt.schema") != INSTALL_RECEIPT_SCHEMA or _h11_text(_h11_object_member(install_manifest, "schema", label="H11 install manifest"), label="H11 install manifest.schema") != INSTALL_SCHEMA:
        _fail("H11 install receipt or manifest schema drifted")
    units = _h11_object_member(install_receipt, "units", label="H11 install receipt")
    manifest_units = _h11_object_member(install_manifest, "units", label="H11 install manifest")
    if type(units) is not tuple or type(manifest_units) is not tuple or len(units) != 3 or len(manifest_units) != 3:
        _fail("H11 install unit inventory drifted")
    install_inputs: list[
        tuple[str, str, int | None, Path, str, int, int, int | None, tuple[tuple[int, int], ...] | None]
    ] = []
    for ordinal, (unit_row, manifest_row) in enumerate(zip(units, manifest_units)):
        role = _h11_text(_h11_object_member(unit_row, "role", label="H11 install unit"), label="H11 install unit.role")
        unit = _h11_text(_h11_object_member(unit_row, "unit", label="H11 install unit"), label="H11 install unit.unit")
        if _systemd_unit_object_path(unit) != _h11_text(_h11_object_member(unit_row, "object_path", label="H11 install unit"), label="H11 install unit.object_path"):
            _fail("H11 install unit object path drifted")
        target = _h11_object_member(unit_row, "target", label="H11 install unit")
        uid = _h11_uint(_h11_object_member(target, "uid", label="H11 install target"), label="H11 install target.uid")
        gid = _h11_uint(_h11_object_member(target, "gid", label="H11 install target"), label="H11 install target.gid")
        mode_text = _h11_text(_h11_object_member(target, "mode", label="H11 install target"), label="H11 install target.mode")
        if mode_text != "0644" or role != _h11_text(_h11_object_member(manifest_row, "role", label="H11 install manifest unit"), label="H11 install manifest unit.role"):
            _fail("H11 install target mode or role drifted")
        install_inputs.append((
            role,
            f"install/target/{role}",
            ordinal,
            _h11_path(_h11_object_member(target, "path", label="H11 install target"), label="H11 install target.path"),
            "regular",
            _h11_uint(_h11_object_member(target, "device", label="H11 install target"), label="H11 install target.device"),
            _h11_uint(_h11_object_member(target, "inode", label="H11 install target"), label="H11 install target.inode"),
            0o644,
            ((uid, gid),),
        ))
    return tuple(
        _make_h11_indirect_authority_spec(
            semantic_role=row[0], equivalence_class=row[1], install_ordinal=row[2],
            path=row[3], kind=row[4], device=row[5], inode=row[6], mode=row[7],
            accepted_owners=row[8],
        )
        for row in install_inputs
    )


def _build_h11_indirect_authority_inventory(
    *,
    authorization_manifest: H11RootFrozenJsonObject,
    harness_manifest: H11RootFrozenJsonObject,
    install_receipt: H11RootFrozenJsonObject,
    install_manifest: H11RootFrozenJsonObject,
    tree_receipt: H11RootFrozenJsonObject,
    seal_receipt: H11RootFrozenJsonObject,
    preflight_receipt: H11RootFrozenJsonObject,
    permit_ready: H11RootFrozenJsonObject,
    run_armed: H11RootFrozenJsonObject,
    authorization_source_reference: H11RootFrozenJsonObject,
    harness_source_reference: H11RootFrozenJsonObject,
    install_receipt_source_reference: H11RootFrozenJsonObject,
    install_manifest_source_reference: H11RootFrozenJsonObject,
    tree_receipt_source_reference: H11RootFrozenJsonObject,
    seal_receipt_source_reference: H11RootFrozenJsonObject,
    preflight_receipt_source_reference: H11RootFrozenJsonObject,
    permit_ready_source_reference: H11RootFrozenJsonObject,
    run_armed_source_reference: H11RootFrozenJsonObject,
    formal_root_directory_reference: H11RootDirectoryReference,
    authority_root_directory_reference: H11RootDirectoryReference,
    harness_root_directory_reference: H11RootDirectoryReference,
    scenario_root_directory_reference: H11RootDirectoryReference,
    input_root_directory_reference: H11RootDirectoryReference,
    receipt_root_directory_reference: H11RootDirectoryReference,
    fifo_root_directory_reference: H11RootDirectoryReference,
    ready_commit_fifo_reference: H11RootFifoReference,
    permit_commit_fifo_reference: H11RootFifoReference,
    formal_root: Path,
    require_root: bool,
    process_euid: int,
    process_egid: int,
) -> tuple[int, int, tuple[H11RootValidatedFifo, ...], tuple[H11RootIndirectAuthoritySpec, ...]]:
    _prove_h11_direct_authority_bindings(
        authorization_manifest=authorization_manifest, harness_manifest=harness_manifest,
        install_receipt=install_receipt, install_manifest=install_manifest,
        tree_receipt=tree_receipt, seal_receipt=seal_receipt,
        preflight_receipt=preflight_receipt, permit_ready=permit_ready,
        run_armed=run_armed, authorization_source_reference=authorization_source_reference,
        harness_source_reference=harness_source_reference,
        install_receipt_source_reference=install_receipt_source_reference,
        install_manifest_source_reference=install_manifest_source_reference,
        tree_receipt_source_reference=tree_receipt_source_reference,
        seal_receipt_source_reference=seal_receipt_source_reference,
        preflight_receipt_source_reference=preflight_receipt_source_reference,
        permit_ready_source_reference=permit_ready_source_reference,
        run_armed_source_reference=run_armed_source_reference,
        formal_root_directory_reference=formal_root_directory_reference,
        authority_root_directory_reference=authority_root_directory_reference,
        harness_root_directory_reference=harness_root_directory_reference,
        scenario_root_directory_reference=scenario_root_directory_reference,
        input_root_directory_reference=input_root_directory_reference,
        receipt_root_directory_reference=receipt_root_directory_reference,
        fifo_root_directory_reference=fifo_root_directory_reference,
        ready_commit_fifo_reference=ready_commit_fifo_reference,
        permit_commit_fifo_reference=permit_commit_fifo_reference,
    )
    fixture_uid, fixture_gid, validated_fifos, tree_specs = _build_h11_tree_indirect_specs(
        tree_receipt=tree_receipt, preflight_receipt=preflight_receipt,
        harness_manifest=harness_manifest, run_armed=run_armed,
        formal_root_directory_reference=formal_root_directory_reference,
        authority_root_directory_reference=authority_root_directory_reference,
        input_root_directory_reference=input_root_directory_reference,
        fifo_root_directory_reference=fifo_root_directory_reference,
        ready_commit_fifo_reference=ready_commit_fifo_reference,
        permit_commit_fifo_reference=permit_commit_fifo_reference,
        require_root=require_root, process_euid=process_euid, process_egid=process_egid,
    )
    seal_specs = _build_h11_seal_indirect_specs(
        seal_receipt=seal_receipt, tree_receipt=tree_receipt,
        preflight_receipt=preflight_receipt, install_receipt=install_receipt,
        install_manifest=install_manifest, harness_manifest=harness_manifest,
        run_armed=run_armed, install_receipt_source_reference=install_receipt_source_reference,
        install_manifest_source_reference=install_manifest_source_reference,
        preflight_receipt_source_reference=preflight_receipt_source_reference,
        formal_root=formal_root, require_root=require_root,
    )
    _prove_h11_preflight_snapshot_bindings(
        preflight_receipt=preflight_receipt, tree_receipt=tree_receipt,
        seal_receipt=seal_receipt, harness_manifest=harness_manifest,
        preflight_receipt_source_reference=preflight_receipt_source_reference,
        formal_root=formal_root, validated_fifos=validated_fifos,
    )
    install_specs = _build_h11_install_target_specs(
        install_receipt=install_receipt, install_manifest=install_manifest,
        harness_manifest=harness_manifest, seal_receipt=seal_receipt,
        install_receipt_source_reference=install_receipt_source_reference,
        install_manifest_source_reference=install_manifest_source_reference,
        formal_root=formal_root, require_root=require_root,
    )
    indirect_specs = tree_specs + seal_specs + install_specs
    direct_source_references = (
        authorization_source_reference,
        harness_source_reference,
        install_receipt_source_reference,
        install_manifest_source_reference,
        tree_receipt_source_reference,
        seal_receipt_source_reference,
        preflight_receipt_source_reference,
        permit_ready_source_reference,
        run_armed_source_reference,
    )
    direct_only_directory_references = (
        harness_root_directory_reference,
        scenario_root_directory_reference,
        receipt_root_directory_reference,
    )
    if len(
        {
            (reference.device, reference.inode)
            for reference in direct_only_directory_references
        }
    ) != len(direct_only_directory_references):
        _fail("H11 direct-only directory identities alias")
    for directory_reference in direct_only_directory_references:
        for source_reference in direct_source_references:
            if (
                ("path", str(directory_reference.path)) in source_reference
                or (
                    ("device", str(directory_reference.device)) in source_reference
                    and ("inode", str(directory_reference.inode)) in source_reference
                )
            ):
                _fail("H11 direct-only directory aliases a direct source")
    for spec in indirect_specs:
        if any(
            ("path", str(spec.path)) in reference
            or (
                ("device", str(spec.device)) in reference
                and ("inode", str(spec.inode)) in reference
            )
            for reference in direct_source_references
        ) or any(
            spec.path == reference.path
            or (spec.device, spec.inode) == (reference.device, reference.inode)
            for reference in direct_only_directory_references
        ):
            _fail("H11 direct-only authority aliases indirect authority")
    if (
        len(indirect_specs) != len({item.path for item in indirect_specs})
        or len(indirect_specs) != len({(item.device, item.inode) for item in indirect_specs})
    ):
        _fail("H11 indirect authority aliases path or identity")
    return fixture_uid, fixture_gid, validated_fifos, indirect_specs


@dataclass(frozen=True, slots=True, init=False)
class H11RootDirectoryView:
    _flow: "H11RootAuthorizationFlow"
    _slot: H11OwnedFdSlot
    _parent_slot: H11OwnedFdSlot | None
    reference: H11RootDirectoryReference
    child_name: str | None

    def __init__(
        self,
        *,
        flow: "H11RootAuthorizationFlow",
        slot: H11OwnedFdSlot,
        parent_slot: H11OwnedFdSlot | None,
        reference: H11RootDirectoryReference,
        child_name: str | None,
    ) -> None:
        valid = (
            (slot is flow._slots[15] and parent_slot is None)
            or (slot is flow._slots[14] and parent_slot is flow._slots[15])
            or (slot is flow._slots[13] and parent_slot is flow._slots[14])
            or (slot is flow._slots[12] and parent_slot is flow._slots[13])
            or (slot is flow._slots[11] and parent_slot is flow._slots[15])
            or (slot is flow._slots[10] and parent_slot is flow._slots[12])
            or (slot is flow._slots[9] and parent_slot is flow._slots[15])
        )
        if not valid:
            _fail("H11 directory view slot topology is invalid")
        object.__setattr__(self, "_flow", flow)
        object.__setattr__(self, "_slot", slot)
        object.__setattr__(self, "_parent_slot", parent_slot)
        object.__setattr__(self, "reference", reference)
        object.__setattr__(self, "child_name", child_name)

    def revalidate(self) -> None:
        allowed = (
            H11RootAuthorizationState.NEW,
            H11RootAuthorizationState.AUTHORITIES_RETAINED,
            H11RootAuthorizationState.READY_CONSUMED,
            H11RootAuthorizationState.PERMIT_PUBLISHED,
            H11RootAuthorizationState.PERMIT_WRITER_OPEN,
        )
        if self._flow.state not in allowed:
            _fail("H11 directory view used outside an active state")
        try:
            if self._flow.state not in allowed:
                _fail("H11 directory view state changed before fstat")
            opened = os.fstat(self._slot.borrow())
            if self._parent_slot is None:
                current = Path.lstat(self.reference.path)
            else:
                if self._flow.state not in allowed:
                    _fail("H11 directory view state changed before current-name proof")
                current = os.stat(
                    self.child_name,
                    dir_fd=self._parent_slot.borrow(),
                    follow_symlinks=False,
                )
        except OSError as exc:
            raise InstallerError(
                f"cannot revalidate H11 {self.reference.role}"
            ) from exc
        self.reference.prove(
            opened,
            require_root=self._flow._require_root,
            label=f"H11 {self.reference.role}",
        )
        self.reference.prove(
            current,
            require_root=self._flow._require_root,
            label=f"H11 {self.reference.role}",
        )


@dataclass(frozen=True, slots=True, init=False)
class H11RootFifoView:
    _flow: "H11RootAuthorizationFlow"
    _slot: H11OwnedFdSlot
    _parent_slot: H11OwnedFdSlot
    role: str
    reference: H11RootFifoReference

    def __init__(
        self,
        *,
        flow: "H11RootAuthorizationFlow",
        slot: H11OwnedFdSlot,
        parent_slot: H11OwnedFdSlot | None,
        role: str,
        reference: H11RootFifoReference,
    ) -> None:
        if not (
            parent_slot is flow._slots[9]
            and (slot is flow._slots[7] or slot is flow._slots[8])
        ):
            _fail("H11 FIFO view slot topology is invalid")
        object.__setattr__(self, "_flow", flow)
        object.__setattr__(self, "_slot", slot)
        object.__setattr__(self, "_parent_slot", parent_slot)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "reference", reference)

    def revalidate(self) -> None:
        allowed = (
            H11RootAuthorizationState.NEW,
            H11RootAuthorizationState.AUTHORITIES_RETAINED,
            H11RootAuthorizationState.READY_CONSUMED,
            H11RootAuthorizationState.PERMIT_PUBLISHED,
            H11RootAuthorizationState.PERMIT_WRITER_OPEN,
        )
        if self._flow.state not in allowed:
            _fail("H11 FIFO view used outside an active state")
        try:
            if self._flow.state not in allowed:
                _fail("H11 FIFO view state changed before fstat")
            opened = os.fstat(self._slot.borrow())
            if self._flow.state not in allowed:
                _fail("H11 FIFO view state changed before current-name proof")
            current = os.stat(
                self.reference.path.name,
                dir_fd=self._parent_slot.borrow(),
                follow_symlinks=False,
            )
        except OSError as exc:
            raise InstallerError(f"cannot revalidate H11 {self.role}") from exc
        self.reference.prove(opened, label=f"H11 {self.role}")
        self.reference.prove(current, label=f"H11 {self.role}")


@dataclass(frozen=True, slots=True, init=False)
class H11RootJsonSourceView:
    _flow: "H11RootAuthorizationFlow"
    _slot: H11OwnedFdSlot
    _parent_slot: H11OwnedFdSlot | None
    path: Path
    raw: bytes
    source: H11RootFrozenJsonObject
    label: str
    child_name: str | None

    def __init__(
        self,
        *,
        flow: "H11RootAuthorizationFlow",
        slot: H11OwnedFdSlot,
        parent_slot: H11OwnedFdSlot | None,
        path: Path,
        raw: bytes,
        source: H11RootFrozenJsonObject,
        label: str,
        child_name: str | None,
    ) -> None:
        valid = (
            (slot is flow._slots[22] and parent_slot is flow._slots[12])
            or (slot is flow._slots[6] and parent_slot is flow._slots[12])
            or (
                parent_slot is None
                and (
                    slot is flow._slots[5]
                    or slot is flow._slots[16]
                    or slot is flow._slots[17]
                    or slot is flow._slots[18]
                    or slot is flow._slots[19]
                    or slot is flow._slots[20]
                    or slot is flow._slots[21]
                )
            )
        )
        if not valid:
            _fail("H11 JSON source view slot topology is invalid")
        object.__setattr__(self, "_flow", flow)
        object.__setattr__(self, "_slot", slot)
        object.__setattr__(self, "_parent_slot", parent_slot)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "raw", raw)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "child_name", child_name)

    def revalidate(self) -> None:
        allowed = (
            H11RootAuthorizationState.NEW,
            H11RootAuthorizationState.AUTHORITIES_RETAINED,
            H11RootAuthorizationState.READY_CONSUMED,
            H11RootAuthorizationState.PERMIT_PUBLISHED,
            H11RootAuthorizationState.PERMIT_WRITER_OPEN,
        )
        if self._flow.state not in allowed:
            _fail("H11 JSON source view used outside an active state")
        try:
            if self._flow.state not in allowed:
                _fail("H11 JSON source state changed before fstat")
            opened = os.fstat(self._slot.borrow())
            if self._parent_slot is None:
                current = Path.lstat(self.path)
            else:
                if self._flow.state not in allowed:
                    _fail("H11 JSON source state changed before current-name proof")
                current = os.stat(
                    self.child_name,
                    dir_fd=self._parent_slot.borrow(),
                    follow_symlinks=False,
                )
            if self._flow.state not in allowed:
                _fail("H11 JSON source state changed before rewind")
            os.lseek(self._slot.borrow(), 0, os.SEEK_SET)
            chunks: list[bytes] = []
            while True:
                if self._flow.state not in allowed:
                    _fail("H11 JSON source state changed during read")
                chunk = os.read(self._slot.borrow(), 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            reread = bytes.join(b"", chunks)
            if self._flow.state not in allowed:
                _fail("H11 JSON source state changed before final rewind")
            os.lseek(self._slot.borrow(), 0, os.SEEK_SET)
        except OSError as exc:
            raise InstallerError(f"cannot revalidate retained {self.label}") from exc
        expected = dict(self.source)
        if (
            reread != self.raw
            or hashlib.sha256(reread).hexdigest() != expected["sha256"]
            or (str(opened.st_dev), str(opened.st_ino))
            != (expected["device"], expected["inode"])
            or (str(current.st_dev), str(current.st_ino))
            != (expected["device"], expected["inode"])
            or format(stat.S_IMODE(opened.st_mode), "04o") != expected["mode"]
            or format(stat.S_IMODE(current.st_mode), "04o") != expected["mode"]
            or str(opened.st_uid) != expected["uid"]
            or str(opened.st_gid) != expected["gid"]
            or str(current.st_uid) != expected["uid"]
            or str(current.st_gid) != expected["gid"]
        ):
            _fail(f"retained {self.label} drifted")


@dataclass(frozen=True, slots=True, init=False)
class H11RootPresentOutputView:
    _flow: "H11RootAuthorizationFlow"
    _slot: H11OwnedFdSlot
    _parent_slot: H11OwnedFdSlot
    role: str
    path: Path
    raw: bytes
    reference_items: tuple[tuple[str, str], ...]

    def __init__(
        self,
        *,
        flow: "H11RootAuthorizationFlow",
        slot: H11OwnedFdSlot,
        parent_slot: H11OwnedFdSlot | None,
        role: str,
        path: Path,
        raw: bytes,
        reference_items: tuple[tuple[str, str], ...],
    ) -> None:
        if not (
            (slot is flow._slots[4] and parent_slot is flow._slots[10])
            or (slot is flow._slots[3] and parent_slot is flow._slots[11])
        ):
            _fail("H11 present-output view slot topology is invalid")
        object.__setattr__(self, "_flow", flow)
        object.__setattr__(self, "_slot", slot)
        object.__setattr__(self, "_parent_slot", parent_slot)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "raw", raw)
        object.__setattr__(self, "reference_items", reference_items)

    @property
    def reference(self) -> dict[str, str]:
        return dict(self.reference_items)

    def revalidate(self) -> None:
        allowed = (
            H11RootAuthorizationState.AUTHORITIES_RETAINED,
            H11RootAuthorizationState.READY_CONSUMED,
            H11RootAuthorizationState.PERMIT_PUBLISHED,
            H11RootAuthorizationState.PERMIT_WRITER_OPEN,
        )
        if self._flow.state not in allowed:
            _fail("H11 present-output view used outside an active state")
        try:
            if self._flow.state not in allowed:
                _fail("H11 present-output state changed before fstat")
            opened = os.fstat(self._slot.borrow())
            if self._flow.state not in allowed:
                _fail("H11 present-output state changed before rewind")
            os.lseek(self._slot.borrow(), 0, os.SEEK_SET)
            chunks: list[bytes] = []
            while True:
                if self._flow.state not in allowed:
                    _fail("H11 present-output state changed during read")
                chunk = os.read(self._slot.borrow(), 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            reread = bytes.join(b"", chunks)
            if self._flow.state not in allowed:
                _fail("H11 present-output state changed before final rewind")
            os.lseek(self._slot.borrow(), 0, os.SEEK_SET)
            if self._flow.state not in allowed:
                _fail("H11 present-output state changed before current-name proof")
            current = os.stat(
                self.path.name,
                dir_fd=self._parent_slot.borrow(),
                follow_symlinks=False,
            )
        except OSError as exc:
            raise InstallerError(
                f"cannot revalidate H11 present output {self.role}"
            ) from exc
        expected = self.reference
        actual = {
            "role": self.role,
            "path": str(self.path),
            "sha256": hashlib.sha256(reread).hexdigest(),
            "device": str(opened.st_dev),
            "inode": str(opened.st_ino),
            "mode": format(stat.S_IMODE(opened.st_mode), "04o"),
            "uid": str(opened.st_uid),
            "gid": str(opened.st_gid),
        }
        if (
            reread != self.raw
            or actual != expected
            or not stat.S_ISREG(current.st_mode)
            or (str(current.st_dev), str(current.st_ino))
            != (expected["device"], expected["inode"])
            or format(stat.S_IMODE(current.st_mode), "04o") != "0444"
            or (str(current.st_uid), str(current.st_gid))
            != (expected["uid"], expected["gid"])
        ):
            _fail(f"retained H11 present output {self.role} drifted")


@dataclass(frozen=True, slots=True, init=False)
class H11RootPublicationView:
    _flow: "H11RootAuthorizationFlow"
    _slot: H11OwnedFdSlot
    _parent_slot: H11OwnedFdSlot
    final_name: str
    raw: bytes
    reference_items: tuple[tuple[str, str], ...]

    def __init__(
        self,
        *,
        flow: "H11RootAuthorizationFlow",
        slot: H11OwnedFdSlot,
        parent_slot: H11OwnedFdSlot | None,
        final_name: str,
        raw: bytes,
        reference_items: tuple[tuple[str, str], ...],
    ) -> None:
        if not (slot is flow._slots[2] and parent_slot is flow._slots[12]):
            _fail("H11 publication view slot topology is invalid")
        object.__setattr__(self, "_flow", flow)
        object.__setattr__(self, "_slot", slot)
        object.__setattr__(self, "_parent_slot", parent_slot)
        object.__setattr__(self, "final_name", final_name)
        object.__setattr__(self, "raw", raw)
        object.__setattr__(self, "reference_items", reference_items)

    @property
    def reference(self) -> dict[str, str]:
        return dict(self.reference_items)

    def revalidate(self) -> None:
        allowed = (
            H11RootAuthorizationState.READY_CONSUMED,
            H11RootAuthorizationState.PERMIT_PUBLISHED,
            H11RootAuthorizationState.PERMIT_WRITER_OPEN,
        )
        if self._flow.state not in allowed:
            _fail("H11 publication view used outside an active state")
        try:
            if self._flow.state not in allowed:
                _fail("H11 publication state changed before fstat")
            opened = os.fstat(self._slot.borrow())
            if self._flow.state not in allowed:
                _fail("H11 publication state changed before current-name proof")
            current = os.stat(
                self.final_name,
                dir_fd=self._parent_slot.borrow(),
                follow_symlinks=False,
            )
            if self._flow.state not in allowed:
                _fail("H11 publication state changed before rewind")
            os.lseek(self._slot.borrow(), 0, os.SEEK_SET)
            chunks: list[bytes] = []
            while True:
                if self._flow.state not in allowed:
                    _fail("H11 publication state changed during read")
                chunk = os.read(self._slot.borrow(), 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            reread = bytes.join(b"", chunks)
            if self._flow.state not in allowed:
                _fail("H11 publication state changed before final rewind")
            os.lseek(self._slot.borrow(), 0, os.SEEK_SET)
        except OSError as exc:
            raise InstallerError("cannot revalidate retained H11 publication") from exc
        expected = self.reference
        actual = {
            "path": expected["path"],
            "sha256": hashlib.sha256(reread).hexdigest(),
            "device": str(opened.st_dev),
            "inode": str(opened.st_ino),
            "mode": format(stat.S_IMODE(opened.st_mode), "04o"),
            "uid": str(opened.st_uid),
            "gid": str(opened.st_gid),
        }
        if (
            reread != self.raw
            or actual != expected
            or not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
            or stat.S_IMODE(current.st_mode) != 0o444
            or (current.st_uid, current.st_gid) != (opened.st_uid, opened.st_gid)
        ):
            _fail("retained H11 publication drifted")


@dataclass(frozen=True, slots=True, init=False)
class H11RootAuthorityView:
    _flow: "H11RootAuthorizationFlow"
    authorization_view: H11RootJsonSourceView
    harness_manifest_view: H11RootJsonSourceView
    install_receipt_view: H11RootJsonSourceView
    install_manifest_view: H11RootJsonSourceView
    tree_receipt_view: H11RootJsonSourceView
    seal_receipt_view: H11RootJsonSourceView
    preflight_receipt_view: H11RootJsonSourceView
    permit_ready_view: H11RootJsonSourceView
    run_armed_view: H11RootJsonSourceView
    formal_root_directory: H11RootDirectoryView
    authority_root_directory: H11RootDirectoryView
    harness_root_directory: H11RootDirectoryView
    scenario_root_directory: H11RootDirectoryView
    input_root_directory: H11RootDirectoryView
    receipt_root_directory: H11RootDirectoryView
    fifo_root_directory: H11RootDirectoryView
    ready_commit_fifo: H11RootFifoView
    permit_commit_fifo: H11RootFifoView
    authorization_manifest: H11RootFrozenJsonObject
    harness_manifest: H11RootFrozenJsonObject
    ready_receipt: H11RootFrozenJsonObject
    armed_receipt: H11RootFrozenJsonObject
    fixture_uid: int
    fixture_gid: int
    validated_fifos: tuple[H11RootValidatedFifo, ...]

    def __init__(
        self,
        *,
        flow: "H11RootAuthorizationFlow",
        authorization_view: H11RootJsonSourceView,
        harness_manifest_view: H11RootJsonSourceView,
        install_receipt_view: H11RootJsonSourceView,
        install_manifest_view: H11RootJsonSourceView,
        tree_receipt_view: H11RootJsonSourceView,
        seal_receipt_view: H11RootJsonSourceView,
        preflight_receipt_view: H11RootJsonSourceView,
        permit_ready_view: H11RootJsonSourceView,
        run_armed_view: H11RootJsonSourceView,
        formal_root_directory: H11RootDirectoryView,
        authority_root_directory: H11RootDirectoryView,
        harness_root_directory: H11RootDirectoryView,
        scenario_root_directory: H11RootDirectoryView,
        input_root_directory: H11RootDirectoryView,
        receipt_root_directory: H11RootDirectoryView,
        fifo_root_directory: H11RootDirectoryView,
        ready_commit_fifo: H11RootFifoView,
        permit_commit_fifo: H11RootFifoView,
        authorization_manifest: H11RootFrozenJsonObject,
        harness_manifest: H11RootFrozenJsonObject,
        ready_receipt: H11RootFrozenJsonObject,
        armed_receipt: H11RootFrozenJsonObject,
        fixture_uid: int,
        fixture_gid: int,
        validated_fifos: tuple[H11RootValidatedFifo, ...],
    ) -> None:
        views = (
            authorization_view,
            harness_manifest_view,
            install_receipt_view,
            install_manifest_view,
            tree_receipt_view,
            seal_receipt_view,
            preflight_receipt_view,
            permit_ready_view,
            run_armed_view,
            formal_root_directory,
            authority_root_directory,
            harness_root_directory,
            scenario_root_directory,
            input_root_directory,
            receipt_root_directory,
            fifo_root_directory,
            ready_commit_fifo,
            permit_commit_fifo,
        )
        if any(view._flow is not flow for view in views):
            _fail("H11 authority view contains a foreign-flow borrowed view")
        if (
            ready_commit_fifo.role != "h11-ready-commit"
            or permit_commit_fifo.role != "h11-permit-commit"
            or ready_commit_fifo is permit_commit_fifo
        ):
            _fail("H11 authority view commit FIFO topology is invalid")
        object.__setattr__(self, "_flow", flow)
        object.__setattr__(self, "authorization_view", authorization_view)
        object.__setattr__(self, "harness_manifest_view", harness_manifest_view)
        object.__setattr__(self, "install_receipt_view", install_receipt_view)
        object.__setattr__(self, "install_manifest_view", install_manifest_view)
        object.__setattr__(self, "tree_receipt_view", tree_receipt_view)
        object.__setattr__(self, "seal_receipt_view", seal_receipt_view)
        object.__setattr__(self, "preflight_receipt_view", preflight_receipt_view)
        object.__setattr__(self, "permit_ready_view", permit_ready_view)
        object.__setattr__(self, "run_armed_view", run_armed_view)
        object.__setattr__(self, "formal_root_directory", formal_root_directory)
        object.__setattr__(self, "authority_root_directory", authority_root_directory)
        object.__setattr__(self, "harness_root_directory", harness_root_directory)
        object.__setattr__(self, "scenario_root_directory", scenario_root_directory)
        object.__setattr__(self, "input_root_directory", input_root_directory)
        object.__setattr__(self, "receipt_root_directory", receipt_root_directory)
        object.__setattr__(self, "fifo_root_directory", fifo_root_directory)
        object.__setattr__(self, "ready_commit_fifo", ready_commit_fifo)
        object.__setattr__(self, "permit_commit_fifo", permit_commit_fifo)
        object.__setattr__(self, "authorization_manifest", authorization_manifest)
        object.__setattr__(self, "harness_manifest", harness_manifest)
        object.__setattr__(self, "ready_receipt", ready_receipt)
        object.__setattr__(self, "armed_receipt", armed_receipt)
        object.__setattr__(self, "fixture_uid", fixture_uid)
        object.__setattr__(self, "fixture_gid", fixture_gid)
        object.__setattr__(self, "validated_fifos", validated_fifos)


@dataclass(frozen=True, slots=True, init=False)
class H11RootAuthorityPhaseData:
    authority: H11RootAuthorityView

    def __init__(self, *, authority: H11RootAuthorityView) -> None:
        if type(authority) is not H11RootAuthorityView:
            _fail("H11 authority phase data requires exact authority view")
        object.__setattr__(self, "authority", authority)


@dataclass(frozen=True, slots=True, init=False)
class H11RootReadyPhaseData:
    authority_data: H11RootAuthorityPhaseData
    ready_commit: H11RootCommitReceipt
    partition: H11RootClosedPartition
    present_h0: H11RootPresentOutputView
    present_run_main_properties: H11RootPresentOutputView
    transaction_state: tuple[H11RootTransactionState, ...]
    present_outputs_sha256: str
    future_absence_sha256: str

    def __init__(
        self,
        *,
        authority_data: H11RootAuthorityPhaseData,
        ready_commit: H11RootCommitReceipt,
        partition: H11RootClosedPartition,
        present_h0: H11RootPresentOutputView,
        present_run_main_properties: H11RootPresentOutputView,
        transaction_state: tuple[H11RootTransactionState, ...],
        present_outputs_sha256: str,
        future_absence_sha256: str,
    ) -> None:
        if (
            type(authority_data) is not H11RootAuthorityPhaseData
            or present_h0._flow is not authority_data.authority._flow
            or present_run_main_properties._flow is not authority_data.authority._flow
            or type(ready_commit) is not H11RootCommitReceipt
            or type(partition) is not H11RootClosedPartition
            or type(transaction_state) is not tuple
        ):
            _fail("H11 READY phase data predecessor or flow identity drifted")
        object.__setattr__(self, "authority_data", authority_data)
        object.__setattr__(self, "ready_commit", ready_commit)
        object.__setattr__(self, "partition", partition)
        object.__setattr__(self, "present_h0", present_h0)
        object.__setattr__(
            self,
            "present_run_main_properties",
            present_run_main_properties,
        )
        object.__setattr__(self, "transaction_state", transaction_state)
        object.__setattr__(self, "present_outputs_sha256", present_outputs_sha256)
        object.__setattr__(self, "future_absence_sha256", future_absence_sha256)


@dataclass(frozen=True, slots=True, init=False)
class H11RootPermitPhaseData:
    ready_data: H11RootReadyPhaseData
    barrier: H11RootPrePermitBarrier
    publication: H11RootPublicationView
    transaction_state: tuple[H11RootTransactionState, ...]

    def __init__(
        self,
        *,
        ready_data: H11RootReadyPhaseData,
        barrier: H11RootPrePermitBarrier,
        publication: H11RootPublicationView,
        transaction_state: tuple[H11RootTransactionState, ...],
    ) -> None:
        if (
            type(ready_data) is not H11RootReadyPhaseData
            or type(barrier) is not H11RootPrePermitBarrier
            or type(publication) is not H11RootPublicationView
            or type(transaction_state) is not tuple
            or publication._flow is not ready_data.authority_data.authority._flow
        ):
            _fail("H11 PERMIT phase data predecessor or flow identity drifted")
        object.__setattr__(self, "ready_data", ready_data)
        object.__setattr__(self, "barrier", barrier)
        object.__setattr__(self, "publication", publication)
        object.__setattr__(self, "transaction_state", transaction_state)


class H11RootAuthorizationFlow:
    def __init__(
        self,
        manifest_path: Path,
        *,
        require_root: bool = True,
    ) -> None:
        self._slots = (
            H11OwnedFdSlot(role="permit-writer-endpoint"),
            H11OwnedFdSlot(role="ready-reader-endpoint"),
            H11OwnedFdSlot(role="permit-publication"),
            H11OwnedFdSlot(role="present-run-main-properties"),
            H11OwnedFdSlot(role="present-h0"),
            H11OwnedFdSlot(role="run-armed"),
            H11OwnedFdSlot(role="permit-ready"),
            H11OwnedFdSlot(role="permit-commit-fifo-pin"),
            H11OwnedFdSlot(role="ready-commit-fifo-pin"),
            H11OwnedFdSlot(role="directory-fifo-root"),
            H11OwnedFdSlot(role="directory-receipt-root"),
            H11OwnedFdSlot(role="directory-input-root"),
            H11OwnedFdSlot(role="directory-scenario-root"),
            H11OwnedFdSlot(role="directory-harness-root"),
            H11OwnedFdSlot(role="directory-authority-root"),
            H11OwnedFdSlot(role="directory-formal-root"),
            H11OwnedFdSlot(role="source-preflight-receipt"),
            H11OwnedFdSlot(role="source-seal-receipt"),
            H11OwnedFdSlot(role="source-tree-receipt"),
            H11OwnedFdSlot(role="source-install-manifest"),
            H11OwnedFdSlot(role="source-install-receipt"),
            H11OwnedFdSlot(role="source-harness-manifest"),
            H11OwnedFdSlot(role="source-authorization"),
        )
        self._manifest_path = manifest_path
        self._require_root = require_root
        self._phase_data: (
            None
            | H11RootAuthorityPhaseData
            | H11RootReadyPhaseData
            | H11RootPermitPhaseData
        ) = None
        self._state = H11RootAuthorizationState.NEW
        self._commit_boundary = H11RootCommitBoundary.PREWRITE

    @property
    def state(self) -> H11RootAuthorizationState:
        return self._state

    def _transition(
        self,
        *,
        expected: H11RootAuthorizationState,
        target: H11RootAuthorizationState,
    ) -> None:
        if self._state is not expected:
            _fail("H11 authorization flow state transition source drifted")
        allowed = (
            (
                H11RootAuthorizationState.NEW,
                H11RootAuthorizationState.AUTHORITIES_RETAINED,
                H11RootAuthorityPhaseData,
            ),
            (
                H11RootAuthorizationState.AUTHORITIES_RETAINED,
                H11RootAuthorizationState.READY_CONSUMED,
                H11RootReadyPhaseData,
            ),
            (
                H11RootAuthorizationState.READY_CONSUMED,
                H11RootAuthorizationState.PERMIT_PUBLISHED,
                H11RootPermitPhaseData,
            ),
            (
                H11RootAuthorizationState.PERMIT_PUBLISHED,
                H11RootAuthorizationState.PERMIT_WRITER_OPEN,
                H11RootPermitPhaseData,
            ),
            (
                H11RootAuthorizationState.PERMIT_WRITER_OPEN,
                H11RootAuthorizationState.PERMIT_FRAME_WRITTEN,
                H11RootPermitPhaseData,
            ),
        )
        matches = tuple(
            row for row in allowed if row[0] is expected and row[1] is target
        )
        if len(matches) != 1 or type(self._phase_data) is not matches[0][2]:
            _fail("H11 authorization flow state transition is not allowed")
        self._state = target

    def _mark_write_in_flight(self) -> None:
        if (
            self._state is not H11RootAuthorizationState.PERMIT_WRITER_OPEN
            or self._commit_boundary is not H11RootCommitBoundary.PREWRITE
            or type(self._phase_data) is not H11RootPermitPhaseData
        ):
            _fail("H11 permit write cannot enter the in-flight boundary")
        self._commit_boundary = H11RootCommitBoundary.WRITE_IN_FLIGHT

    def _mark_postwrite(self) -> None:
        if (
            self._state is not H11RootAuthorizationState.PERMIT_WRITER_OPEN
            or self._commit_boundary is not H11RootCommitBoundary.WRITE_IN_FLIGHT
            or type(self._phase_data) is not H11RootPermitPhaseData
        ):
            _fail("H11 permit write cannot enter the postwrite boundary")
        self._commit_boundary = H11RootCommitBoundary.POSTWRITE

    def _close_slot_once(
        self,
        slot: H11OwnedFdSlot,
        *,
        active_error: BaseException | None = None,
    ) -> BaseException | None:
        descriptor = slot.detach()
        if descriptor < 0:
            return None
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if active_error is not None:
                try:
                    BaseException.add_note(
                        active_error,
                        "H11 ownership teardown secondary close failure",
                    )
                except BaseException:
                    pass
            return close_error
        return None

    def _sweep_slots(
        self,
        *,
        active_error: BaseException | None = None,
    ) -> None:
        first_close_error: BaseException | None = None
        for slot in self._slots:
            observed = self._close_slot_once(
                slot,
                active_error=(
                    active_error if first_close_error is None else None
                ),
            )
            if observed is not None and first_close_error is None:
                first_close_error = observed
        if active_error is None and first_close_error is not None:
            raise first_close_error

    def _fail(self, active_error: BaseException) -> NoReturn:
        if self._commit_boundary is H11RootCommitBoundary.PREWRITE:
            self._state = H11RootAuthorizationState.FAILED_PREWRITE
        elif self._commit_boundary is H11RootCommitBoundary.WRITE_IN_FLIGHT:
            self._state = H11RootAuthorizationState.FAILED_WRITE_AMBIGUOUS
        else:
            self._state = H11RootAuthorizationState.FAILED_POSTWRITE
        self._sweep_slots(active_error=active_error)
        raise active_error

    def _finish(self, receipt: H11RootCommitReceipt) -> H11RootCommitReceipt:
        if (
            self._state is not H11RootAuthorizationState.PERMIT_FRAME_WRITTEN
            or self._commit_boundary is not H11RootCommitBoundary.POSTWRITE
        ):
            _fail("H11 authorization flow cannot finish before exact commit")
        try:
            self._sweep_slots(active_error=None)
        except BaseException:
            self._state = H11RootAuthorizationState.FAILED_POSTWRITE
            raise
        self._state = H11RootAuthorizationState.COMPLETE
        return receipt

    def close(self) -> None:
        if self._state in (
            H11RootAuthorizationState.COMPLETE,
            H11RootAuthorizationState.FAILED_PREWRITE,
            H11RootAuthorizationState.FAILED_WRITE_AMBIGUOUS,
            H11RootAuthorizationState.FAILED_POSTWRITE,
            H11RootAuthorizationState.CLOSED,
        ):
            return
        primary: InstallerError | None = None
        if self._commit_boundary is H11RootCommitBoundary.WRITE_IN_FLIGHT:
            primary = InstallerError(
                "H11 authorization flow closed while permit write outcome is ambiguous"
            )
            self._state = H11RootAuthorizationState.FAILED_WRITE_AMBIGUOUS
        elif self._state is H11RootAuthorizationState.PERMIT_FRAME_WRITTEN:
            primary = InstallerError(
                "H11 authorization flow closed after permit frame write"
            )
            self._state = H11RootAuthorizationState.FAILED_POSTWRITE
        try:
            self._sweep_slots(active_error=primary)
        except BaseException:
            self._state = H11RootAuthorizationState.FAILED_PREWRITE
            raise
        if primary is not None:
            raise primary
        self._state = H11RootAuthorizationState.CLOSED

    def _acquire_authorities(self) -> None:
        if (
            self._state is not H11RootAuthorizationState.NEW
            or self._phase_data is not None
        ):
            _fail("H11 authority acquisition requires a fresh flow")
        process_euid = os.geteuid()
        process_egid = os.getegid()
        _prove_h11_execution_authority(
            require_root=self._require_root,
            process_euid=process_euid,
        )
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        root = self._manifest_path.parents[3]
        scenario_root = root / "authority" / "harness" / "H11"
        if self._manifest_path != scenario_root / "AUTHORIZE-RELEASE.json":
            _fail("H11 authorization path differs from the exact layout")

        authorization_before = Path.lstat(self._manifest_path)
        self._slots[22].open(self._manifest_path, flags)
        authorization_opened = os.fstat(self._slots[22].borrow())
        authorization_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[22].borrow(), 1024 * 1024)
            if not chunk:
                break
            authorization_chunks.append(chunk)
        authorization_raw = bytes.join(b"", authorization_chunks)
        authorization_after = os.fstat(self._slots[22].borrow())
        authorization_current = Path.lstat(self._manifest_path)
        if (
            not stat.S_ISREG(authorization_before.st_mode)
            or not stat.S_ISREG(authorization_after.st_mode)
            or (authorization_before.st_dev, authorization_before.st_ino)
            != (authorization_after.st_dev, authorization_after.st_ino)
            or (authorization_current.st_dev, authorization_current.st_ino)
            != (authorization_after.st_dev, authorization_after.st_ino)
            or authorization_after.st_size != len(authorization_raw)
            or stat.S_IMODE(authorization_after.st_mode) != 0o444
            or (
                self._require_root
                and (authorization_after.st_uid, authorization_after.st_gid)
                != (0, 0)
            )
        ):
            _fail("H11 authorization source drifted while pinning")
        os.lseek(self._slots[22].borrow(), 0, os.SEEK_SET)
        authorization_source = (
            ("device", str(authorization_after.st_dev)),
            ("gid", str(authorization_after.st_gid)),
            ("inode", str(authorization_after.st_ino)),
            ("mode", format(stat.S_IMODE(authorization_after.st_mode), "04o")),
            ("path", str(self._manifest_path)),
            ("sha256", hashlib.sha256(authorization_raw).hexdigest()),
            ("uid", str(authorization_after.st_uid)),
        )
        authorization_manifest = _decode_h11_canonical_frozen_object(
            authorization_raw,
            label="H11 authorization manifest",
        )
        authorization_values = dict(authorization_manifest)
        try:
            harness_binding = authorization_values["harness_manifest"]
        except KeyError as exc:
            raise InstallerError(
                "H11 authorization harness_manifest is missing"
            ) from exc
        if type(harness_binding) is not tuple:
            _fail("H11 authorization harness_manifest is not frozen")
        try:
            harness_path_value = dict(harness_binding)["path"]
        except (KeyError, TypeError, ValueError) as exc:
            raise InstallerError(
                "H11 authorization harness_manifest.path is missing or malformed"
            ) from exc
        if type(harness_path_value) is not str:
            _fail("H11 authorization harness_manifest.path is not text")
        harness_path = Path(harness_path_value)
        if (
            not harness_path.is_absolute()
            or str(harness_path) != harness_path_value
            or any(part in {".", ".."} for part in harness_path.parts)
        ):
            _fail("H11 authorization harness_manifest.path is not canonical")
        if harness_path != scenario_root / "MANIFEST.json":
            _fail("H11 harness manifest path differs from the exact layout")

        harness_before = Path.lstat(harness_path)
        self._slots[21].open(harness_path, flags)
        harness_opened = os.fstat(self._slots[21].borrow())
        harness_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[21].borrow(), 1024 * 1024)
            if not chunk:
                break
            harness_chunks.append(chunk)
        harness_raw = bytes.join(b"", harness_chunks)
        harness_after = os.fstat(self._slots[21].borrow())
        harness_current = Path.lstat(harness_path)
        if (
            not stat.S_ISREG(harness_before.st_mode)
            or not stat.S_ISREG(harness_after.st_mode)
            or (harness_before.st_dev, harness_before.st_ino)
            != (harness_after.st_dev, harness_after.st_ino)
            or (harness_current.st_dev, harness_current.st_ino)
            != (harness_after.st_dev, harness_after.st_ino)
            or harness_after.st_size != len(harness_raw)
            or stat.S_IMODE(harness_after.st_mode) != 0o444
            or (
                self._require_root
                and (harness_after.st_uid, harness_after.st_gid) != (0, 0)
            )
        ):
            _fail("H11 harness manifest drifted while pinning")
        os.lseek(self._slots[21].borrow(), 0, os.SEEK_SET)
        harness_source = (
            ("device", str(harness_after.st_dev)),
            ("gid", str(harness_after.st_gid)),
            ("inode", str(harness_after.st_ino)),
            ("mode", format(stat.S_IMODE(harness_after.st_mode), "04o")),
            ("path", str(harness_path)),
            ("sha256", hashlib.sha256(harness_raw).hexdigest()),
            ("uid", str(harness_after.st_uid)),
        )
        if harness_binding != harness_source:
            _fail("H11 harness source differs from authorization authority")
        harness_manifest = _decode_h11_canonical_frozen_object(
            harness_raw,
            label="H11 harness manifest",
        )
        harness_values = dict(harness_manifest)
        try:
            installer_binding = harness_values["installer_receipt"]
        except KeyError as exc:
            raise InstallerError(
                "H11 harness installer_receipt is missing"
            ) from exc
        if type(installer_binding) is not tuple:
            _fail("H11 harness installer_receipt is not frozen")
        try:
            install_receipt_path_value = dict(installer_binding)["path"]
        except (KeyError, TypeError, ValueError) as exc:
            raise InstallerError(
                "H11 harness installer_receipt.path is missing or malformed"
            ) from exc
        if type(install_receipt_path_value) is not str:
            _fail("H11 harness installer_receipt.path is not text")
        install_receipt_path = Path(install_receipt_path_value)
        if (
            not install_receipt_path.is_absolute()
            or str(install_receipt_path) != install_receipt_path_value
            or any(part in {".", ".."} for part in install_receipt_path.parts)
        ):
            _fail("H11 harness installer_receipt.path is not canonical")

        install_receipt_before = Path.lstat(install_receipt_path)
        self._slots[20].open(install_receipt_path, flags)
        install_receipt_opened = os.fstat(self._slots[20].borrow())
        install_receipt_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[20].borrow(), 1024 * 1024)
            if not chunk:
                break
            install_receipt_chunks.append(chunk)
        install_receipt_raw = bytes.join(b"", install_receipt_chunks)
        install_receipt_after = os.fstat(self._slots[20].borrow())
        install_receipt_current = Path.lstat(install_receipt_path)
        if (
            not stat.S_ISREG(install_receipt_before.st_mode)
            or not stat.S_ISREG(install_receipt_after.st_mode)
            or (install_receipt_before.st_dev, install_receipt_before.st_ino)
            != (install_receipt_after.st_dev, install_receipt_after.st_ino)
            or (install_receipt_current.st_dev, install_receipt_current.st_ino)
            != (install_receipt_after.st_dev, install_receipt_after.st_ino)
            or install_receipt_after.st_size != len(install_receipt_raw)
            or stat.S_IMODE(install_receipt_after.st_mode) != 0o444
            or (
                self._require_root
                and (install_receipt_after.st_uid, install_receipt_after.st_gid)
                != (0, 0)
            )
        ):
            _fail("H11 install receipt drifted while pinning")
        os.lseek(self._slots[20].borrow(), 0, os.SEEK_SET)
        install_receipt_source = (
            ("device", str(install_receipt_after.st_dev)),
            ("gid", str(install_receipt_after.st_gid)),
            ("inode", str(install_receipt_after.st_ino)),
            ("mode", format(stat.S_IMODE(install_receipt_after.st_mode), "04o")),
            ("path", str(install_receipt_path)),
            ("sha256", hashlib.sha256(install_receipt_raw).hexdigest()),
            ("uid", str(install_receipt_after.st_uid)),
        )
        try:
            installer_sha256 = dict(installer_binding)["sha256"]
        except (KeyError, TypeError, ValueError) as exc:
            raise InstallerError(
                "H11 harness installer_receipt.sha256 is missing or malformed"
            ) from exc
        if (
            type(installer_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", installer_sha256) is None
            or installer_sha256 != dict(install_receipt_source)["sha256"]
        ):
            _fail("H11 install receipt hash differs from harness authority")
        install_receipt = _decode_h11_canonical_frozen_object(
            install_receipt_raw,
            label="H11 install receipt",
        )

        install_receipt_values = dict(install_receipt)
        try:
            install_manifest_binding = install_receipt_values["install_manifest"]
        except KeyError as exc:
            raise InstallerError(
                "H11 install receipt install_manifest is missing"
            ) from exc
        if type(install_manifest_binding) is not tuple:
            _fail("H11 install_manifest reference is not frozen")
        try:
            install_manifest_path_value = dict(install_manifest_binding)["path"]
        except (KeyError, TypeError, ValueError) as exc:
            raise InstallerError(
                "H11 install_manifest.path is missing or malformed"
            ) from exc
        if type(install_manifest_path_value) is not str:
            _fail("H11 install_manifest.path is not text")
        install_manifest_path = Path(install_manifest_path_value)
        if (
            not install_manifest_path.is_absolute()
            or str(install_manifest_path) != install_manifest_path_value
            or any(part in {".", ".."} for part in install_manifest_path.parts)
        ):
            _fail("H11 install_manifest.path is not canonical")
        install_manifest_before = Path.lstat(install_manifest_path)
        self._slots[19].open(install_manifest_path, flags)
        install_manifest_opened = os.fstat(self._slots[19].borrow())
        install_manifest_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[19].borrow(), 1024 * 1024)
            if not chunk:
                break
            install_manifest_chunks.append(chunk)
        install_manifest_raw = bytes.join(b"", install_manifest_chunks)
        install_manifest_after = os.fstat(self._slots[19].borrow())
        install_manifest_current = Path.lstat(install_manifest_path)
        if (
            not stat.S_ISREG(install_manifest_before.st_mode)
            or not stat.S_ISREG(install_manifest_after.st_mode)
            or (install_manifest_before.st_dev, install_manifest_before.st_ino)
            != (install_manifest_after.st_dev, install_manifest_after.st_ino)
            or (install_manifest_current.st_dev, install_manifest_current.st_ino)
            != (install_manifest_after.st_dev, install_manifest_after.st_ino)
            or install_manifest_after.st_size != len(install_manifest_raw)
            or stat.S_IMODE(install_manifest_after.st_mode) != 0o444
            or (
                self._require_root
                and (install_manifest_after.st_uid, install_manifest_after.st_gid)
                != (0, 0)
            )
        ):
            _fail("H11 install manifest drifted while pinning")
        os.lseek(self._slots[19].borrow(), 0, os.SEEK_SET)
        install_manifest_source = (
            ("device", str(install_manifest_after.st_dev)),
            ("gid", str(install_manifest_after.st_gid)),
            ("inode", str(install_manifest_after.st_ino)),
            ("mode", format(stat.S_IMODE(install_manifest_after.st_mode), "04o")),
            ("path", str(install_manifest_path)),
            ("sha256", hashlib.sha256(install_manifest_raw).hexdigest()),
            ("uid", str(install_manifest_after.st_uid)),
        )
        if install_manifest_binding != tuple(
            (key, value)
            for key, value in install_manifest_source
            if key not in ("uid", "gid")
        ):
            _fail("H11 install manifest differs from its full reference")
        install_manifest = _decode_h11_canonical_frozen_object(
            install_manifest_raw,
            label="H11 install manifest",
        )

        receipt_values: list[
            tuple[
                H11RootFrozenJsonObject,
                H11RootFrozenJsonObject,
                bytes,
                Path,
            ]
        ] = []
        for field in ("tree_receipt", "seal_receipt", "preflight_receipt"):
            try:
                binding = install_receipt_values[field]
            except KeyError as exc:
                raise InstallerError(
                    f"H11 install receipt {field} is missing"
                ) from exc
            if type(binding) is not tuple:
                _fail(f"H11 {field} reference is not frozen")
            try:
                source_path_value = dict(binding)["path"]
            except (KeyError, TypeError, ValueError) as exc:
                raise InstallerError(
                    f"H11 {field}.path is missing or malformed"
                ) from exc
            if type(source_path_value) is not str:
                _fail(f"H11 {field}.path is not text")
            source_path = Path(source_path_value)
            if (
                not source_path.is_absolute()
                or str(source_path) != source_path_value
                or any(part in {".", ".."} for part in source_path.parts)
            ):
                _fail(f"H11 {field}.path is not canonical")
            receipt_values.append((binding, (), b"", source_path))
        tree_binding, _empty_tree, _empty_tree_raw, tree_path = receipt_values[0]
        seal_binding, _empty_seal, _empty_seal_raw, seal_path = receipt_values[1]
        preflight_binding, _empty_preflight, _empty_preflight_raw, preflight_path = receipt_values[2]

        tree_before = Path.lstat(tree_path)
        self._slots[18].open(tree_path, flags)
        tree_opened = os.fstat(self._slots[18].borrow())
        tree_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[18].borrow(), 1024 * 1024)
            if not chunk:
                break
            tree_chunks.append(chunk)
        tree_raw = bytes.join(b"", tree_chunks)
        tree_after = os.fstat(self._slots[18].borrow())
        tree_current = Path.lstat(tree_path)
        if (
            not stat.S_ISREG(tree_before.st_mode)
            or not stat.S_ISREG(tree_after.st_mode)
            or (tree_before.st_dev, tree_before.st_ino)
            != (tree_after.st_dev, tree_after.st_ino)
            or (tree_current.st_dev, tree_current.st_ino)
            != (tree_after.st_dev, tree_after.st_ino)
            or tree_after.st_size != len(tree_raw)
            or stat.S_IMODE(tree_after.st_mode) != 0o444
            or (
                self._require_root
                and (tree_after.st_uid, tree_after.st_gid) != (0, 0)
            )
        ):
            _fail("H11 TREE receipt drifted while pinning")
        os.lseek(self._slots[18].borrow(), 0, os.SEEK_SET)
        tree_source = (
            ("device", str(tree_after.st_dev)),
            ("gid", str(tree_after.st_gid)),
            ("inode", str(tree_after.st_ino)),
            ("mode", format(stat.S_IMODE(tree_after.st_mode), "04o")),
            ("path", str(tree_path)),
            ("sha256", hashlib.sha256(tree_raw).hexdigest()),
            ("uid", str(tree_after.st_uid)),
        )
        if tuple(
            (key, value)
            for key, value in tree_source
            if key in ("device", "inode", "path", "sha256")
        ) != tree_binding:
            _fail("H11 TREE receipt differs from its full reference")
        tree_receipt = _decode_h11_canonical_frozen_object(
            tree_raw,
            label="H11 TREE receipt",
        )

        seal_before = Path.lstat(seal_path)
        self._slots[17].open(seal_path, flags)
        seal_opened = os.fstat(self._slots[17].borrow())
        seal_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[17].borrow(), 1024 * 1024)
            if not chunk:
                break
            seal_chunks.append(chunk)
        seal_raw = bytes.join(b"", seal_chunks)
        seal_after = os.fstat(self._slots[17].borrow())
        seal_current = Path.lstat(seal_path)
        if (
            not stat.S_ISREG(seal_before.st_mode)
            or not stat.S_ISREG(seal_after.st_mode)
            or (seal_before.st_dev, seal_before.st_ino)
            != (seal_after.st_dev, seal_after.st_ino)
            or (seal_current.st_dev, seal_current.st_ino)
            != (seal_after.st_dev, seal_after.st_ino)
            or seal_after.st_size != len(seal_raw)
            or stat.S_IMODE(seal_after.st_mode) != 0o444
            or (
                self._require_root
                and (seal_after.st_uid, seal_after.st_gid) != (0, 0)
            )
        ):
            _fail("H11 SEAL receipt drifted while pinning")
        os.lseek(self._slots[17].borrow(), 0, os.SEEK_SET)
        seal_source = (
            ("device", str(seal_after.st_dev)),
            ("gid", str(seal_after.st_gid)),
            ("inode", str(seal_after.st_ino)),
            ("mode", format(stat.S_IMODE(seal_after.st_mode), "04o")),
            ("path", str(seal_path)),
            ("sha256", hashlib.sha256(seal_raw).hexdigest()),
            ("uid", str(seal_after.st_uid)),
        )
        if tuple(
            (key, value)
            for key, value in seal_source
            if key in ("device", "inode", "path", "sha256")
        ) != seal_binding:
            _fail("H11 SEAL receipt differs from its full reference")
        seal_receipt = _decode_h11_canonical_frozen_object(
            seal_raw,
            label="H11 SEAL receipt",
        )

        preflight_before = Path.lstat(preflight_path)
        self._slots[16].open(preflight_path, flags)
        preflight_opened = os.fstat(self._slots[16].borrow())
        preflight_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[16].borrow(), 1024 * 1024)
            if not chunk:
                break
            preflight_chunks.append(chunk)
        preflight_raw = bytes.join(b"", preflight_chunks)
        preflight_after = os.fstat(self._slots[16].borrow())
        preflight_current = Path.lstat(preflight_path)
        if (
            not stat.S_ISREG(preflight_before.st_mode)
            or not stat.S_ISREG(preflight_after.st_mode)
            or (preflight_before.st_dev, preflight_before.st_ino)
            != (preflight_after.st_dev, preflight_after.st_ino)
            or (preflight_current.st_dev, preflight_current.st_ino)
            != (preflight_after.st_dev, preflight_after.st_ino)
            or preflight_after.st_size != len(preflight_raw)
            or stat.S_IMODE(preflight_after.st_mode) != 0o444
            or (
                self._require_root
                and (preflight_after.st_uid, preflight_after.st_gid) != (0, 0)
            )
        ):
            _fail("H11 PREFLIGHT receipt drifted while pinning")
        os.lseek(self._slots[16].borrow(), 0, os.SEEK_SET)
        preflight_source = (
            ("device", str(preflight_after.st_dev)),
            ("gid", str(preflight_after.st_gid)),
            ("inode", str(preflight_after.st_ino)),
            ("mode", format(stat.S_IMODE(preflight_after.st_mode), "04o")),
            ("path", str(preflight_path)),
            ("sha256", hashlib.sha256(preflight_raw).hexdigest()),
            ("uid", str(preflight_after.st_uid)),
        )
        if tuple(
            (key, value)
            for key, value in preflight_source
            if key in ("device", "inode", "path", "sha256")
        ) != preflight_binding:
            _fail("H11 PREFLIGHT receipt differs from its full reference")
        preflight_receipt = _decode_h11_canonical_frozen_object(
            preflight_raw,
            label="H11 PREFLIGHT receipt",
        )

        try:
            permit_authority = harness_values["permit_authority"]
        except KeyError as exc:
            raise InstallerError(
                "H11 harness permit_authority is missing"
            ) from exc
        if type(permit_authority) is not tuple:
            _fail("H11 permit authority is not frozen")
        permit_authority_values = dict(permit_authority)
        try:
            directory_chain = permit_authority_values["directory_chain"]
        except KeyError as exc:
            raise InstallerError(
                "H11 permit authority directory_chain is missing"
            ) from exc
        if type(directory_chain) is not tuple or len(directory_chain) != 7:
            _fail("H11 directory chain must contain exactly seven references")
        formal_reference = H11RootDirectoryReference.decode(
            directory_chain[0], label="H11 directory_chain[0]"
        )
        authority_reference = H11RootDirectoryReference.decode(
            directory_chain[1], label="H11 directory_chain[1]"
        )
        harness_reference = H11RootDirectoryReference.decode(
            directory_chain[2], label="H11 directory_chain[2]"
        )
        scenario_reference = H11RootDirectoryReference.decode(
            directory_chain[3], label="H11 directory_chain[3]"
        )
        input_reference = H11RootDirectoryReference.decode(
            directory_chain[4], label="H11 directory_chain[4]"
        )
        receipt_reference = H11RootDirectoryReference.decode(
            directory_chain[5], label="H11 directory_chain[5]"
        )
        fifo_reference = H11RootDirectoryReference.decode(
            directory_chain[6], label="H11 directory_chain[6]"
        )
        if tuple(
            (item.role, item.path, item.mode)
            for item in (
                formal_reference,
                authority_reference,
                harness_reference,
                scenario_reference,
                input_reference,
                receipt_reference,
                fifo_reference,
            )
        ) != (
            ("formal-root", root, 0o711),
            ("authority-root", root / "authority", 0o700),
            ("harness-root", root / "authority" / "harness", 0o700),
            ("scenario-root", scenario_root, 0o700),
            ("input-root", root / "input", 0o555),
            ("receipt-root", scenario_root / "receipts", 0o555),
            ("fifo-root", root / "fifo", 0o711),
        ):
            _fail("H11 directory chain order/path/mode drifted")
        directory_flags = (
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
        )

        formal_before = Path.lstat(formal_reference.path)
        self._slots[15].open(formal_reference.path, directory_flags)
        formal_reference.prove(
            formal_before,
            require_root=self._require_root,
            label="H11 formal-root",
        )
        formal_view = H11RootDirectoryView(
            flow=self,
            slot=self._slots[15],
            parent_slot=None,
            reference=formal_reference,
            child_name=None,
        )
        formal_view.revalidate()

        authority_before = os.stat(
            "authority",
            dir_fd=self._slots[15].borrow(),
            follow_symlinks=False,
        )
        self._slots[14].open(
            "authority",
            directory_flags,
            dir_fd=self._slots[15].borrow(),
        )
        authority_reference.prove(
            authority_before,
            require_root=self._require_root,
            label="H11 authority-root",
        )
        authority_view = H11RootDirectoryView(
            flow=self,
            slot=self._slots[14],
            parent_slot=self._slots[15],
            reference=authority_reference,
            child_name="authority",
        )
        authority_view.revalidate()

        harness_before = os.stat(
            "harness",
            dir_fd=self._slots[14].borrow(),
            follow_symlinks=False,
        )
        self._slots[13].open(
            "harness",
            directory_flags,
            dir_fd=self._slots[14].borrow(),
        )
        harness_reference.prove(
            harness_before,
            require_root=self._require_root,
            label="H11 harness-root",
        )
        harness_root_view = H11RootDirectoryView(
            flow=self,
            slot=self._slots[13],
            parent_slot=self._slots[14],
            reference=harness_reference,
            child_name="harness",
        )
        harness_root_view.revalidate()

        scenario_before = os.stat(
            "H11",
            dir_fd=self._slots[13].borrow(),
            follow_symlinks=False,
        )
        self._slots[12].open(
            "H11",
            directory_flags,
            dir_fd=self._slots[13].borrow(),
        )
        scenario_reference.prove(
            scenario_before,
            require_root=self._require_root,
            label="H11 scenario-root",
        )
        scenario_view = H11RootDirectoryView(
            flow=self,
            slot=self._slots[12],
            parent_slot=self._slots[13],
            reference=scenario_reference,
            child_name="H11",
        )
        scenario_view.revalidate()

        input_before = os.stat(
            "input",
            dir_fd=self._slots[15].borrow(),
            follow_symlinks=False,
        )
        self._slots[11].open(
            "input",
            directory_flags,
            dir_fd=self._slots[15].borrow(),
        )
        input_reference.prove(
            input_before,
            require_root=self._require_root,
            label="H11 input-root",
        )
        input_view = H11RootDirectoryView(
            flow=self,
            slot=self._slots[11],
            parent_slot=self._slots[15],
            reference=input_reference,
            child_name="input",
        )
        input_view.revalidate()

        receipt_before = os.stat(
            "receipts",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        self._slots[10].open(
            "receipts",
            directory_flags,
            dir_fd=self._slots[12].borrow(),
        )
        receipt_reference.prove(
            receipt_before,
            require_root=self._require_root,
            label="H11 receipt-root",
        )
        receipt_view = H11RootDirectoryView(
            flow=self,
            slot=self._slots[10],
            parent_slot=self._slots[12],
            reference=receipt_reference,
            child_name="receipts",
        )
        receipt_view.revalidate()

        fifo_before = os.stat(
            "fifo",
            dir_fd=self._slots[15].borrow(),
            follow_symlinks=False,
        )
        self._slots[9].open(
            "fifo",
            directory_flags,
            dir_fd=self._slots[15].borrow(),
        )
        fifo_reference.prove(
            fifo_before,
            require_root=self._require_root,
            label="H11 fifo-root",
        )
        fifo_root_view = H11RootDirectoryView(
            flow=self,
            slot=self._slots[9],
            parent_slot=self._slots[15],
            reference=fifo_reference,
            child_name="fifo",
        )
        fifo_root_view.revalidate()

        try:
            ready_commit_fifo_value = permit_authority_values["ready_commit_fifo"]
        except KeyError as exc:
            raise InstallerError(
                "H11 permit authority ready_commit_fifo is missing"
            ) from exc
        ready_fifo_reference = H11RootFifoReference.decode(
            ready_commit_fifo_value,
            label="H11 ready_commit_fifo",
            require_root=self._require_root,
            process_euid=process_euid,
            process_egid=process_egid,
        )
        try:
            permit_commit_fifo_value = permit_authority_values[
                "permit_commit_fifo"
            ]
        except KeyError as exc:
            raise InstallerError(
                "H11 permit authority permit_commit_fifo is missing"
            ) from exc
        permit_fifo_reference = H11RootFifoReference.decode(
            permit_commit_fifo_value,
            label="H11 permit_commit_fifo",
            require_root=self._require_root,
            process_euid=process_euid,
            process_egid=process_egid,
        )
        if (
            ready_fifo_reference.path
            != fifo_reference.path / _H11_COMMIT_FIFO_NAMES["h11-ready-commit"]
            or permit_fifo_reference.path
            != fifo_reference.path / _H11_COMMIT_FIFO_NAMES["h11-permit-commit"]
            or (ready_fifo_reference.device, ready_fifo_reference.inode)
            == (permit_fifo_reference.device, permit_fifo_reference.inode)
        ):
            _fail("H11 commit FIFO authority drifted or aliased")
        self._slots[8].open(
            _H11_COMMIT_FIFO_NAMES["h11-ready-commit"],
            os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=self._slots[9].borrow(),
        )
        ready_fifo_view = H11RootFifoView(
            flow=self,
            slot=self._slots[8],
            parent_slot=self._slots[9],
            role="h11-ready-commit",
            reference=ready_fifo_reference,
        )
        ready_fifo_view.revalidate()
        self._slots[7].open(
            _H11_COMMIT_FIFO_NAMES["h11-permit-commit"],
            os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=self._slots[9].borrow(),
        )
        permit_fifo_view = H11RootFifoView(
            flow=self,
            slot=self._slots[7],
            parent_slot=self._slots[9],
            role="h11-permit-commit",
            reference=permit_fifo_reference,
        )
        permit_fifo_view.revalidate()

        formal_view.revalidate()
        authority_view.revalidate()
        harness_root_view.revalidate()
        scenario_view.revalidate()
        input_view.revalidate()
        receipt_view.revalidate()
        fifo_root_view.revalidate()
        ready_fifo_view.revalidate()
        permit_fifo_view.revalidate()

        try:
            permit_ready_binding = authorization_values["permit_ready"]
        except KeyError as exc:
            raise InstallerError(
                "H11 authorization permit_ready is missing"
            ) from exc
        if type(permit_ready_binding) is not tuple:
            _fail("H11 authorization permit_ready is not frozen")
        try:
            permit_ready_path_value = dict(permit_ready_binding)["path"]
        except (KeyError, TypeError, ValueError) as exc:
            raise InstallerError(
                "H11 authorization permit_ready.path is missing or malformed"
            ) from exc
        if type(permit_ready_path_value) is not str:
            _fail("H11 authorization permit_ready.path is not text")
        permit_ready_path = Path(permit_ready_path_value)
        if (
            not permit_ready_path.is_absolute()
            or str(permit_ready_path) != permit_ready_path_value
            or any(part in {".", ".."} for part in permit_ready_path.parts)
        ):
            _fail("H11 authorization permit_ready.path is not canonical")
        if permit_ready_path != scenario_root / "PERMIT_READY.json":
            _fail("H11 PERMIT_READY path differs from the exact layout")
        permit_ready_before = os.stat(
            "PERMIT_READY.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        self._slots[6].open(
            "PERMIT_READY.json",
            flags,
            dir_fd=self._slots[12].borrow(),
        )
        permit_ready_opened = os.fstat(self._slots[6].borrow())
        permit_ready_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[6].borrow(), 1024 * 1024)
            if not chunk:
                break
            permit_ready_chunks.append(chunk)
        permit_ready_raw = bytes.join(b"", permit_ready_chunks)
        permit_ready_after = os.fstat(self._slots[6].borrow())
        permit_ready_current = os.stat(
            "PERMIT_READY.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(permit_ready_before.st_mode)
            or not stat.S_ISREG(permit_ready_after.st_mode)
            or (permit_ready_before.st_dev, permit_ready_before.st_ino)
            != (permit_ready_after.st_dev, permit_ready_after.st_ino)
            or (permit_ready_current.st_dev, permit_ready_current.st_ino)
            != (permit_ready_after.st_dev, permit_ready_after.st_ino)
            or permit_ready_after.st_size != len(permit_ready_raw)
            or stat.S_IMODE(permit_ready_after.st_mode) != 0o444
            or (
                self._require_root
                and (permit_ready_after.st_uid, permit_ready_after.st_gid) != (0, 0)
            )
        ):
            _fail("H11 PERMIT_READY drifted while pinning")
        os.lseek(self._slots[6].borrow(), 0, os.SEEK_SET)
        permit_ready_source = (
            ("device", str(permit_ready_after.st_dev)),
            ("gid", str(permit_ready_after.st_gid)),
            ("inode", str(permit_ready_after.st_ino)),
            ("mode", format(stat.S_IMODE(permit_ready_after.st_mode), "04o")),
            ("path", str(permit_ready_path)),
            ("sha256", hashlib.sha256(permit_ready_raw).hexdigest()),
            ("uid", str(permit_ready_after.st_uid)),
        )
        if permit_ready_binding != permit_ready_source:
            _fail("H11 PERMIT_READY differs from authorization authority")
        permit_ready = _decode_h11_canonical_frozen_object(
            permit_ready_raw,
            label="H11 PERMIT_READY",
        )

        try:
            run_armed_binding = authorization_values["run_armed"]
        except KeyError as exc:
            raise InstallerError("H11 authorization run_armed is missing") from exc
        if type(run_armed_binding) is not tuple:
            _fail("H11 authorization run_armed is not frozen")
        try:
            run_armed_path_value = dict(run_armed_binding)["path"]
        except (KeyError, TypeError, ValueError) as exc:
            raise InstallerError(
                "H11 authorization run_armed.path is missing or malformed"
            ) from exc
        if type(run_armed_path_value) is not str:
            _fail("H11 authorization run_armed.path is not text")
        run_armed_path = Path(run_armed_path_value)
        if (
            not run_armed_path.is_absolute()
            or str(run_armed_path) != run_armed_path_value
            or any(part in {".", ".."} for part in run_armed_path.parts)
        ):
            _fail("H11 authorization run_armed.path is not canonical")
        run_armed_before = Path.lstat(run_armed_path)
        self._slots[5].open(run_armed_path, flags)
        run_armed_opened = os.fstat(self._slots[5].borrow())
        run_armed_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[5].borrow(), 1024 * 1024)
            if not chunk:
                break
            run_armed_chunks.append(chunk)
        run_armed_raw = bytes.join(b"", run_armed_chunks)
        run_armed_after = os.fstat(self._slots[5].borrow())
        run_armed_current = Path.lstat(run_armed_path)
        if (
            not stat.S_ISREG(run_armed_before.st_mode)
            or not stat.S_ISREG(run_armed_after.st_mode)
            or (run_armed_before.st_dev, run_armed_before.st_ino)
            != (run_armed_after.st_dev, run_armed_after.st_ino)
            or (run_armed_current.st_dev, run_armed_current.st_ino)
            != (run_armed_after.st_dev, run_armed_after.st_ino)
            or run_armed_after.st_size != len(run_armed_raw)
            or stat.S_IMODE(run_armed_after.st_mode) != 0o600
        ):
            _fail("H11 run ARMED drifted while pinning")
        os.lseek(self._slots[5].borrow(), 0, os.SEEK_SET)
        run_armed_source = (
            ("device", str(run_armed_after.st_dev)),
            ("gid", str(run_armed_after.st_gid)),
            ("inode", str(run_armed_after.st_ino)),
            ("mode", format(stat.S_IMODE(run_armed_after.st_mode), "04o")),
            ("path", str(run_armed_path)),
            ("sha256", hashlib.sha256(run_armed_raw).hexdigest()),
            ("uid", str(run_armed_after.st_uid)),
        )
        if run_armed_binding != run_armed_source:
            _fail("H11 run ARMED differs from authorization authority")
        run_armed = _decode_h11_canonical_frozen_object(
            run_armed_raw,
            label="H11 run ARMED",
        )

        authorization_json_view = H11RootJsonSourceView(
            flow=self, slot=self._slots[22], parent_slot=self._slots[12],
            path=self._manifest_path, raw=authorization_raw,
            source=authorization_source, label="H11 authorization manifest",
            child_name="AUTHORIZE-RELEASE.json",
        )
        harness_json_view = H11RootJsonSourceView(
            flow=self, slot=self._slots[21], parent_slot=None,
            path=harness_path, raw=harness_raw, source=harness_source,
            label="H11 harness manifest", child_name=None,
        )
        install_receipt_json_view = H11RootJsonSourceView(
            flow=self, slot=self._slots[20], parent_slot=None,
            path=install_receipt_path, raw=install_receipt_raw,
            source=install_receipt_source, label="H11 install receipt",
            child_name=None,
        )
        install_manifest_json_view = H11RootJsonSourceView(
            flow=self, slot=self._slots[19], parent_slot=None,
            path=install_manifest_path, raw=install_manifest_raw,
            source=install_manifest_source, label="H11 install manifest",
            child_name=None,
        )
        tree_json_view = H11RootJsonSourceView(
            flow=self, slot=self._slots[18], parent_slot=None,
            path=tree_path, raw=tree_raw, source=tree_source,
            label="H11 TREE receipt", child_name=None,
        )
        seal_json_view = H11RootJsonSourceView(
            flow=self, slot=self._slots[17], parent_slot=None,
            path=seal_path, raw=seal_raw, source=seal_source,
            label="H11 SEAL receipt", child_name=None,
        )
        preflight_json_view = H11RootJsonSourceView(
            flow=self, slot=self._slots[16], parent_slot=None,
            path=preflight_path, raw=preflight_raw, source=preflight_source,
            label="H11 PREFLIGHT receipt", child_name=None,
        )
        permit_ready_json_view = H11RootJsonSourceView(
            flow=self, slot=self._slots[6], parent_slot=self._slots[12],
            path=permit_ready_path, raw=permit_ready_raw,
            source=permit_ready_source, label="H11 PERMIT_READY",
            child_name="PERMIT_READY.json",
        )
        run_armed_json_view = H11RootJsonSourceView(
            flow=self, slot=self._slots[5], parent_slot=None,
            path=run_armed_path, raw=run_armed_raw, source=run_armed_source,
            label="H11 run ARMED", child_name=None,
        )

        authorization_json_view.revalidate()
        harness_json_view.revalidate()
        install_receipt_json_view.revalidate()
        install_manifest_json_view.revalidate()
        tree_json_view.revalidate()
        seal_json_view.revalidate()
        preflight_json_view.revalidate()
        permit_ready_json_view.revalidate()
        run_armed_json_view.revalidate()
        fixture_uid, fixture_gid, validated_fifos, indirect_specs = (
            _build_h11_indirect_authority_inventory(
                authorization_manifest=authorization_manifest,
                harness_manifest=harness_manifest,
                install_receipt=install_receipt,
                install_manifest=install_manifest,
                tree_receipt=tree_receipt,
                seal_receipt=seal_receipt,
                preflight_receipt=preflight_receipt,
                permit_ready=permit_ready,
                run_armed=run_armed,
                authorization_source_reference=authorization_source,
                harness_source_reference=harness_source,
                install_receipt_source_reference=install_receipt_source,
                install_manifest_source_reference=install_manifest_source,
                tree_receipt_source_reference=tree_source,
                seal_receipt_source_reference=seal_source,
                preflight_receipt_source_reference=preflight_source,
                permit_ready_source_reference=permit_ready_source,
                run_armed_source_reference=run_armed_source,
                formal_root_directory_reference=formal_reference,
                authority_root_directory_reference=authority_reference,
                harness_root_directory_reference=harness_reference,
                scenario_root_directory_reference=scenario_reference,
                input_root_directory_reference=input_reference,
                receipt_root_directory_reference=receipt_reference,
                fifo_root_directory_reference=fifo_reference,
                ready_commit_fifo_reference=ready_fifo_reference,
                permit_commit_fifo_reference=permit_fifo_reference,
                formal_root=root,
                require_root=self._require_root,
                process_euid=process_euid,
                process_egid=process_egid,
            )
        )
        observed_identities = tuple(
            _observe_h11_indirect_authority(spec) for spec in indirect_specs
        )
        authorization_json_view.revalidate()
        harness_json_view.revalidate()
        install_receipt_json_view.revalidate()
        install_manifest_json_view.revalidate()
        tree_json_view.revalidate()
        seal_json_view.revalidate()
        preflight_json_view.revalidate()
        permit_ready_json_view.revalidate()
        run_armed_json_view.revalidate()
        _prove_h11_indirect_observations(indirect_specs, observed_identities)
        formal_view.revalidate()
        authority_view.revalidate()
        harness_root_view.revalidate()
        scenario_view.revalidate()
        input_view.revalidate()
        receipt_view.revalidate()
        fifo_root_view.revalidate()
        ready_fifo_view.revalidate()
        permit_fifo_view.revalidate()

        authority = H11RootAuthorityView(
            flow=self,
            authorization_view=authorization_json_view,
            harness_manifest_view=harness_json_view,
            install_receipt_view=install_receipt_json_view,
            install_manifest_view=install_manifest_json_view,
            tree_receipt_view=tree_json_view,
            seal_receipt_view=seal_json_view,
            preflight_receipt_view=preflight_json_view,
            permit_ready_view=permit_ready_json_view,
            run_armed_view=run_armed_json_view,
            formal_root_directory=formal_view,
            authority_root_directory=authority_view,
            harness_root_directory=harness_root_view,
            scenario_root_directory=scenario_view,
            input_root_directory=input_view,
            receipt_root_directory=receipt_view,
            fifo_root_directory=fifo_root_view,
            ready_commit_fifo=ready_fifo_view,
            permit_commit_fifo=permit_fifo_view,
            authorization_manifest=authorization_manifest,
            harness_manifest=harness_manifest,
            ready_receipt=permit_ready,
            armed_receipt=run_armed,
            fixture_uid=fixture_uid,
            fixture_gid=fixture_gid,
            validated_fifos=validated_fifos,
        )
        self._phase_data = H11RootAuthorityPhaseData(authority=authority)
        self._transition(
            expected=H11RootAuthorizationState.NEW,
            target=H11RootAuthorizationState.AUTHORITIES_RETAINED,
        )
        return None

    def _consume_ready_commit(self) -> None:
        phase_data = self._phase_data
        if (
            self._state is not H11RootAuthorizationState.AUTHORITIES_RETAINED
            or type(phase_data) is not H11RootAuthorityPhaseData
        ):
            _fail("H11 READY consume requires exact retained authority data")
        authority = phase_data.authority
        if authority._flow is not self:
            _fail("H11 READY consume received foreign-flow authority")
        authority.authorization_view.revalidate()
        authority.harness_manifest_view.revalidate()
        authority.install_receipt_view.revalidate()
        authority.install_manifest_view.revalidate()
        authority.tree_receipt_view.revalidate()
        authority.seal_receipt_view.revalidate()
        authority.preflight_receipt_view.revalidate()
        authority.permit_ready_view.revalidate()
        authority.run_armed_view.revalidate()
        authority.formal_root_directory.revalidate()
        authority.authority_root_directory.revalidate()
        authority.harness_root_directory.revalidate()
        authority.scenario_root_directory.revalidate()
        authority.input_root_directory.revalidate()
        authority.receipt_root_directory.revalidate()
        authority.fifo_root_directory.revalidate()
        authority.ready_commit_fifo.revalidate()
        authority.permit_commit_fifo.revalidate()

        self._slots[1].open(
            f"/proc/self/fd/{self._slots[8].borrow()}",
            os.O_RDONLY | os.O_CLOEXEC,
        )
        authority.ready_commit_fifo.reference.prove(
            os.fstat(self._slots[1].borrow()),
            label="H11 ready-commit reader",
        )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[1].borrow(), select.PIPE_BUF)
            if not chunk:
                break
            chunks.append(chunk)
        payload = bytes.join(b"", chunks)
        close_error = self._close_slot_once(self._slots[1])
        if close_error is not None:
            raise close_error
        if payload != H11_READY_COMMITTED_BYTES:
            _fail("H11 READY commit FIFO frame differs before EOF")
        fifo = authority.ready_commit_fifo
        if (
            fifo is not authority.ready_commit_fifo
            or fifo._flow is not self
            or fifo._slot is not self._slots[8]
            or fifo._parent_slot is not self._slots[9]
        ):
            _fail("H11 READY receipt FIFO identity gate failed")
        receipt = H11RootCommitReceipt.ready_committed(fifo, payload)
        authority.authorization_view.revalidate()
        authority.harness_manifest_view.revalidate()
        authority.install_receipt_view.revalidate()
        authority.install_manifest_view.revalidate()
        authority.tree_receipt_view.revalidate()
        authority.seal_receipt_view.revalidate()
        authority.preflight_receipt_view.revalidate()
        authority.permit_ready_view.revalidate()
        authority.run_armed_view.revalidate()
        authority.formal_root_directory.revalidate()
        authority.authority_root_directory.revalidate()
        authority.harness_root_directory.revalidate()
        authority.scenario_root_directory.revalidate()
        authority.input_root_directory.revalidate()
        authority.receipt_root_directory.revalidate()
        authority.fifo_root_directory.revalidate()
        authority.ready_commit_fifo.revalidate()
        authority.permit_commit_fifo.revalidate()

        ready = dict(authority.ready_receipt)
        present_rows = ready.get("present_outputs")
        absent_rows = ready.get("absent_paths")
        if type(present_rows) is not tuple or len(present_rows) != 2:
            _fail("H11 READY present inventory differs from exact pair")
        if type(absent_rows) is not tuple or len(absent_rows) != 11:
            _fail("H11 READY future absence inventory differs from exact eleven")
        sealed_output_rows = dict(authority.harness_manifest).get("outputs")
        sealed_permit_authority = dict(authority.harness_manifest).get(
            "permit_authority"
        )
        if (
            type(sealed_output_rows) is not tuple
            or len(sealed_output_rows) != 12
            or type(sealed_permit_authority) is not tuple
            or ready.get("permit_authority") != sealed_permit_authority
        ):
            _fail("H11 READY authority differs from the sealed harness manifest")
        sealed_future_rows = dict(sealed_permit_authority).get(
            "future_absence_inventory"
        )
        if (
            type(sealed_future_rows) is not tuple
            or len(sealed_future_rows) != 11
            or absent_rows != sealed_future_rows
        ):
            _fail("H11 READY future inventory differs from sealed authority")
        if any(
            type(row) is not tuple
            or tuple(key for key, _value in row) != ("path", "role")
            for row in sealed_output_rows
        ):
            _fail("H11 sealed output rows differ from exact role/path objects")
        canonical_output_roles = (
            "closer-properties",
            "exec-stop-post-properties",
            "final",
            "final-closer-properties",
            "final-run-properties",
            "h0",
            "h12-absence",
            "journal",
            "manager-events",
            "run-main-properties",
            "signals",
            "source-selector",
        )
        sealed_output_paths_items: list[Path] = []
        seen_output_paths: set[Path] = set()
        seen_output_parent_leaves: set[tuple[Path, str]] = set()
        for row, expected_role in zip(
            sealed_output_rows,
            canonical_output_roles,
        ):
            row_values = dict(row)
            role = row_values["role"]
            path_text = row_values["path"]
            if type(role) is not str or role != expected_role:
                _fail("H11 sealed output role closure or order drifted")
            if type(path_text) is not str:
                _fail(f"H11 sealed output {role} path is not one string")
            path = Path(path_text)
            parent_leaf = (path.parent, path.name)
            if (
                not path.is_absolute()
                or str(path) != path_text
                or any(part in {".", ".."} for part in path.parts)
                or path in seen_output_paths
                or parent_leaf in seen_output_parent_leaves
                or path.parent
                not in (
                    authority.input_root_directory.reference.path,
                    authority.receipt_root_directory.reference.path,
                )
                or (
                    role == "h0"
                    and path.parent
                    != authority.receipt_root_directory.reference.path
                )
                or (
                    role == "run-main-properties"
                    and path.parent
                    != authority.input_root_directory.reference.path
                )
            ):
                _fail(f"H11 sealed output {role} path closure drifted")
            sealed_output_paths_items.append(path)
            seen_output_paths.add(path)
            seen_output_parent_leaves.add(parent_leaf)
            del row_values
        sealed_output_paths = tuple(sealed_output_paths_items)
        del sealed_output_paths_items
        del seen_output_paths
        del seen_output_parent_leaves
        del canonical_output_roles
        frozen_path = authority.formal_root_directory.reference.path / "frozen"
        if frozen_path in sealed_output_paths:
            _fail("H11 frozen-root overlaps one sealed output path")
        expected_present_role_paths = (
            ("h0", str(sealed_output_paths[5])),
            ("run-main-properties", str(sealed_output_paths[9])),
        )
        expected_future_role_paths = (
            ("closer-properties", str(sealed_output_paths[0])),
            ("exec-stop-post-properties", str(sealed_output_paths[1])),
            ("final", str(sealed_output_paths[2])),
            ("final-closer-properties", str(sealed_output_paths[3])),
            ("final-run-properties", str(sealed_output_paths[4])),
            ("frozen-root", str(frozen_path)),
            ("h12-absence", str(sealed_output_paths[6])),
            ("journal", str(sealed_output_paths[7])),
            ("manager-events", str(sealed_output_paths[8])),
            ("signals", str(sealed_output_paths[10])),
            ("source-selector", str(sealed_output_paths[11])),
        )
        if any(
            type(row) is not tuple
            or tuple(key for key, _value in row)
            != (
                "device",
                "gid",
                "inode",
                "mode",
                "path",
                "role",
                "sha256",
                "uid",
            )
            for row in present_rows
        ):
            _fail("H11 READY present rows differ from exact full references")
        ready_present_role_paths = tuple(
            (dict(row)["role"], dict(row)["path"])
            for row in present_rows
        )
        sealed_future_role_paths = tuple(
            (dict(row)["role"], dict(row)["path"])
            for row in sealed_future_rows
            if type(row) is tuple
            and tuple(key for key, _value in row) == ("path", "role")
        )
        if (
            ready_present_role_paths != expected_present_role_paths
            or sealed_future_role_paths != expected_future_role_paths
            or len(sealed_future_role_paths) != 11
            or set(path for _role, path in ready_present_role_paths)
            & set(path for _role, path in sealed_future_role_paths)
        ):
            _fail("H11 READY present/future role-path partition drifted")
        h0_matches = tuple(
            dict(row) for row in present_rows if dict(row).get("role") == "h0"
        )
        run_matches = tuple(
            dict(row)
            for row in present_rows
            if dict(row).get("role") == "run-main-properties"
        )
        if len(h0_matches) != 1 or len(run_matches) != 1:
            _fail("H11 READY present roles drifted")
        h0_reference = h0_matches[0]
        run_reference = run_matches[0]
        h0_path = Path(h0_reference["path"])
        run_path = Path(run_reference["path"])
        if (
            h0_path.parent != authority.receipt_root_directory.reference.path
            or run_path.parent != authority.input_root_directory.reference.path
        ):
            _fail("H11 READY present paths escaped retained parents")

        h0_before = os.stat(
            h0_path.name,
            dir_fd=self._slots[10].borrow(),
            follow_symlinks=False,
        )
        self._slots[4].open(
            h0_path.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=self._slots[10].borrow(),
        )
        h0_opened = os.fstat(self._slots[4].borrow())
        h0_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[4].borrow(), 1024 * 1024)
            if not chunk:
                break
            h0_chunks.append(chunk)
        h0_raw = bytes.join(b"", h0_chunks)
        h0_after = os.fstat(self._slots[4].borrow())
        h0_current = os.stat(
            h0_path.name,
            dir_fd=self._slots[10].borrow(),
            follow_symlinks=False,
        )
        h0_actual = {
            "role": "h0", "path": str(h0_path),
            "sha256": hashlib.sha256(h0_raw).hexdigest(),
            "device": str(h0_after.st_dev), "inode": str(h0_after.st_ino),
            "mode": format(stat.S_IMODE(h0_after.st_mode), "04o"),
            "uid": str(h0_after.st_uid), "gid": str(h0_after.st_gid),
        }
        if (
            h0_actual != h0_reference
            or any(not stat.S_ISREG(info.st_mode) for info in (h0_before, h0_opened, h0_after, h0_current))
            or any((info.st_dev, info.st_ino) != (h0_after.st_dev, h0_after.st_ino) for info in (h0_before, h0_opened, h0_current))
        ):
            _fail("H11 H0 present source drifted while pinning")
        os.lseek(self._slots[4].borrow(), 0, os.SEEK_SET)
        present_h0 = H11RootPresentOutputView(
            flow=self, slot=self._slots[4], parent_slot=self._slots[10],
            role="h0", path=h0_path, raw=h0_raw,
            reference_items=tuple(sorted(h0_reference.items())),
        )

        run_before = os.stat(
            run_path.name,
            dir_fd=self._slots[11].borrow(),
            follow_symlinks=False,
        )
        self._slots[3].open(
            run_path.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=self._slots[11].borrow(),
        )
        run_opened = os.fstat(self._slots[3].borrow())
        run_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[3].borrow(), 1024 * 1024)
            if not chunk:
                break
            run_chunks.append(chunk)
        run_raw = bytes.join(b"", run_chunks)
        run_after = os.fstat(self._slots[3].borrow())
        run_current = os.stat(
            run_path.name,
            dir_fd=self._slots[11].borrow(),
            follow_symlinks=False,
        )
        run_actual = {
            "role": "run-main-properties", "path": str(run_path),
            "sha256": hashlib.sha256(run_raw).hexdigest(),
            "device": str(run_after.st_dev), "inode": str(run_after.st_ino),
            "mode": format(stat.S_IMODE(run_after.st_mode), "04o"),
            "uid": str(run_after.st_uid), "gid": str(run_after.st_gid),
        }
        if (
            run_actual != run_reference
            or any(not stat.S_ISREG(info.st_mode) for info in (run_before, run_opened, run_after, run_current))
            or any((info.st_dev, info.st_ino) != (run_after.st_dev, run_after.st_ino) for info in (run_before, run_opened, run_current))
        ):
            _fail("H11 run-main-properties source drifted while pinning")
        os.lseek(self._slots[3].borrow(), 0, os.SEEK_SET)
        present_run = H11RootPresentOutputView(
            flow=self, slot=self._slots[3], parent_slot=self._slots[11],
            role="run-main-properties", path=run_path, raw=run_raw,
            reference_items=tuple(sorted(run_reference.items())),
        )
        present_h0.revalidate()
        present_run.revalidate()

        present_partition = (
            H11RootRolePath("h0", h0_path),
            H11RootRolePath("run-main-properties", run_path),
        )
        future_partition = tuple(
            H11RootRolePath(str(dict(row)["role"]), Path(dict(row)["path"]))
            for row in absent_rows
        )
        if tuple(item.role for item in future_partition) != (
            "closer-properties",
            "exec-stop-post-properties",
            "final",
            "final-closer-properties",
            "final-run-properties",
            "frozen-root",
            "h12-absence",
            "journal",
            "manager-events",
            "signals",
            "source-selector",
        ):
            _fail("H11 READY future absence role order drifted")
        frozen_root = future_partition[5]
        if (
            frozen_root.path
            != authority.formal_root_directory.reference.path / "frozen"
        ):
            _fail("H11 frozen-root escaped its retained parent")
        if (
            authority.input_root_directory.reference.path
            == authority.receipt_root_directory.reference.path
            or (
                authority.input_root_directory.reference.device,
                authority.input_root_directory.reference.inode,
            )
            == (
                authority.receipt_root_directory.reference.device,
                authority.receipt_root_directory.reference.inode,
            )
        ):
            _fail("H11 future output retained parents are aliased")
        output_inventory = future_partition[:5] + future_partition[6:]
        input_future_absence_items: list[H11RootRolePath] = []
        receipt_future_absence_items: list[H11RootRolePath] = []
        for item in output_inventory:
            if (
                item.path.parent
                == authority.input_root_directory.reference.path
            ):
                input_future_absence_items.append(item)
            elif (
                item.path.parent
                == authority.receipt_root_directory.reference.path
            ):
                receipt_future_absence_items.append(item)
            else:
                _fail(f"H11 future output {item.role} escaped its retained parent")
        input_future_absence = tuple(input_future_absence_items)
        receipt_future_absence = tuple(receipt_future_absence_items)
        del input_future_absence_items
        del receipt_future_absence_items
        if len(input_future_absence) + len(receipt_future_absence) != 10:
            _fail("H11 future output parent partition is incomplete")
        partition = H11RootClosedPartition(
            present_prerequisites=present_partition,
            future_absence_inventory=future_partition,
            frozen_root=frozen_root,
            input_future_absence=input_future_absence,
            receipt_future_absence=receipt_future_absence,
        )
        transaction_paths = tuple(
            authority.scenario_root_directory.reference.path / leaf
            for _role, leaf in _H11_TRANSACTION_LAYOUT
        )
        transaction_rows: list[H11RootTransactionState] = []
        for (role, leaf), path, expected_state in zip(
            _H11_TRANSACTION_LAYOUT,
            transaction_paths,
            _H11_TRANSACTION_PHASES["authorizer-input"],
        ):
            try:
                os.stat(
                    leaf,
                    dir_fd=self._slots[12].borrow(),
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                actual_state = "absent"
            else:
                actual_state = "present"
            if actual_state != expected_state:
                _fail(f"H11 transaction {role} differs before READY closure")
            transaction_rows.append(H11RootTransactionState(role, path, actual_state))
        authorization_current = os.stat(
            "AUTHORIZE-RELEASE.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        ready_current = os.stat(
            "PERMIT_READY.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        if (
            (str(authorization_current.st_dev), str(authorization_current.st_ino))
            != (dict(authority.authorization_view.source)["device"], dict(authority.authorization_view.source)["inode"])
            or (str(ready_current.st_dev), str(ready_current.st_ino))
            != (dict(authority.permit_ready_view.source)["device"], dict(authority.permit_ready_view.source)["inode"])
        ):
            _fail("H11 retained transaction sources drifted")
        transaction_state = tuple(transaction_rows)
        present_raw = str.encode(
            json.dumps(
                [h0_reference, run_reference],
                sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                allow_nan=False,
            ) + "\n",
            "ascii",
        )
        future_raw = str.encode(
            json.dumps(
                [item.reference for item in future_partition],
                sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                allow_nan=False,
            ) + "\n",
            "ascii",
        )
        self._phase_data = H11RootReadyPhaseData(
            authority_data=phase_data,
            ready_commit=receipt,
            partition=partition,
            present_h0=present_h0,
            present_run_main_properties=present_run,
            transaction_state=transaction_state,
            present_outputs_sha256=hashlib.sha256(present_raw).hexdigest(),
            future_absence_sha256=hashlib.sha256(future_raw).hexdigest(),
        )
        self._transition(
            expected=H11RootAuthorizationState.AUTHORITIES_RETAINED,
            target=H11RootAuthorizationState.READY_CONSUMED,
        )
        return None

    def _publish_permit(self) -> None:
        phase_data = self._phase_data
        if (
            self._state is not H11RootAuthorizationState.READY_CONSUMED
            or type(phase_data) is not H11RootReadyPhaseData
        ):
            _fail("H11 permit publication requires exact READY data")
        authority = phase_data.authority_data.authority
        if authority._flow is not self:
            _fail("H11 permit publication received foreign-flow authority")
        authority.authorization_view.revalidate()
        authority.harness_manifest_view.revalidate()
        authority.install_receipt_view.revalidate()
        authority.install_manifest_view.revalidate()
        authority.tree_receipt_view.revalidate()
        authority.seal_receipt_view.revalidate()
        authority.preflight_receipt_view.revalidate()
        authority.permit_ready_view.revalidate()
        authority.run_armed_view.revalidate()
        authority.formal_root_directory.revalidate()
        authority.authority_root_directory.revalidate()
        authority.harness_root_directory.revalidate()
        authority.scenario_root_directory.revalidate()
        authority.input_root_directory.revalidate()
        authority.receipt_root_directory.revalidate()
        authority.fifo_root_directory.revalidate()
        authority.ready_commit_fifo.revalidate()
        authority.permit_commit_fifo.revalidate()
        phase_data.present_h0.revalidate()
        phase_data.present_run_main_properties.revalidate()
        before_rows: list[H11RootTransactionState] = []
        for (role, leaf), expected in zip(
            _H11_TRANSACTION_LAYOUT,
            _H11_TRANSACTION_PHASES["authorizer-input"],
        ):
            try:
                os.stat(
                    leaf,
                    dir_fd=self._slots[12].borrow(),
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                observed = "absent"
            else:
                observed = "present"
            if observed != expected:
                _fail(f"H11 transaction {role} drifted before permit publication")
            before_rows.append(
                H11RootTransactionState(
                    role,
                    authority.scenario_root_directory.reference.path / leaf,
                    observed,
                )
            )
        if tuple(before_rows) != phase_data.transaction_state:
            _fail("H11 authorizer-input transaction evidence drifted")
        authorization_current = os.stat(
            "AUTHORIZE-RELEASE.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        ready_current = os.stat(
            "PERMIT_READY.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        if (
            (str(authorization_current.st_dev), str(authorization_current.st_ino))
            != (dict(authority.authorization_view.source)["device"], dict(authority.authorization_view.source)["inode"])
            or (str(ready_current.st_dev), str(ready_current.st_ino))
            != (dict(authority.permit_ready_view.source)["device"], dict(authority.permit_ready_view.source)["inode"])
        ):
            _fail("H11 transaction source identity drifted before publication")
        try:
            os.stat(
                "frozen",
                dir_fd=self._slots[15].borrow(),
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            _fail("H11 future output frozen-root exists before permit")
        for item in phase_data.partition.input_future_absence:
            try:
                os.stat(
                    item.path.name,
                    dir_fd=self._slots[11].borrow(),
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                _fail(f"H11 future output {item.role} exists before permit")
        for item in phase_data.partition.receipt_future_absence:
            try:
                os.stat(
                    item.path.name,
                    dir_fd=self._slots[10].borrow(),
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                _fail(f"H11 future output {item.role} exists before permit")
        try:
            os.stat(
                "PERMIT.pending",
                dir_fd=self._slots[12].borrow(),
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            _fail("H11 permit staging exists before publication")

        ready = dict(authority.ready_receipt)
        payload = {
            "schema": H11_PERMIT_SCHEMA,
            "scenario": "H11",
            "run_unit": ready["run_unit"],
            "boot_id": ready["boot_id"],
            "invocation_id": ready["invocation_id"],
            "authorization_manifest": dict(authority.authorization_view.source),
            "harness_manifest": dict(authority.harness_manifest_view.source),
            "permit_ready": dict(authority.permit_ready_view.source),
            "run_armed": dict(authority.run_armed_view.source),
            "ready_commit": phase_data.ready_commit.reference,
            "present_outputs_sha256": phase_data.present_outputs_sha256,
            "future_absence_sha256": phase_data.future_absence_sha256,
            "phase": "operator-release-authorized",
        }
        publication_raw = str.encode(
            json.dumps(
                payload,
                sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                allow_nan=False,
            ) + "\n",
            "ascii",
        )
        barrier = H11RootPrePermitBarrier(
            (
                authority.formal_root_directory.reference,
                authority.authority_root_directory.reference,
                authority.harness_root_directory.reference,
                authority.scenario_root_directory.reference,
                authority.input_root_directory.reference,
                authority.receipt_root_directory.reference,
                authority.fifo_root_directory.reference,
            ),
            phase_data.present_outputs_sha256,
            phase_data.future_absence_sha256,
            phase_data.transaction_state,
            phase_data.partition.future_absence_inventory,
        )
        self._slots[2].open(
            "PERMIT.pending",
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o444,
            dir_fd=self._slots[12].borrow(),
        )
        remaining = memoryview(publication_raw)
        while remaining:
            written = os.write(self._slots[2].borrow(), remaining)
            if written <= 0:
                _fail("H11 permit staging write made no progress")
            remaining = remaining[written:]
        os.fchmod(self._slots[2].borrow(), 0o444)
        os.lseek(self._slots[2].borrow(), 0, os.SEEK_SET)
        publication_chunks: list[bytes] = []
        while True:
            chunk = os.read(self._slots[2].borrow(), 1024 * 1024)
            if not chunk:
                break
            publication_chunks.append(chunk)
        reread = bytes.join(b"", publication_chunks)
        os.lseek(self._slots[2].borrow(), 0, os.SEEK_SET)
        retained_before = os.fstat(self._slots[2].borrow())
        expected_owner = (
            (0, 0)
            if self._require_root
            else (
                authority.scenario_root_directory.reference.uid,
                authority.scenario_root_directory.reference.gid,
            )
        )
        if (
            reread != publication_raw
            or retained_before.st_size != len(publication_raw)
            or not stat.S_ISREG(retained_before.st_mode)
            or stat.S_IMODE(retained_before.st_mode) != 0o444
            or (retained_before.st_uid, retained_before.st_gid) != expected_owner
        ):
            _fail("H11 permit staging readback or metadata drifted")
        os.fsync(self._slots[2].borrow())
        libc = ctypes.CDLL(None, use_errno=True)
        libc.renameat2.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
            ctypes.c_uint,
        ]
        libc.renameat2.restype = ctypes.c_int
        ctypes.set_errno(0)
        if libc.renameat2(
            self._slots[12].borrow(),
            str.encode("PERMIT.pending", "ascii"),
            self._slots[12].borrow(),
            str.encode("PERMIT.json", "ascii"),
            1,
        ) != 0:
            error = ctypes.get_errno()
            raise InstallerError(
                f"cannot publish no-replace H11 permit: {os.strerror(error)}"
            )
        os.fsync(self._slots[12].borrow())
        final_info = os.stat(
            "PERMIT.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        retained_after = os.fstat(self._slots[2].borrow())
        if (
            not stat.S_ISREG(final_info.st_mode)
            or (final_info.st_dev, final_info.st_ino)
            != (retained_after.st_dev, retained_after.st_ino)
            or stat.S_IMODE(final_info.st_mode) != 0o444
            or (final_info.st_uid, final_info.st_gid) != expected_owner
        ):
            _fail("H11 final permit name differs from retained publication")
        reference_items = tuple(sorted({
            "path": str(authority.scenario_root_directory.reference.path / "PERMIT.json"),
            "sha256": hashlib.sha256(publication_raw).hexdigest(),
            "device": str(retained_after.st_dev), "inode": str(retained_after.st_ino),
            "mode": "0444", "uid": str(retained_after.st_uid),
            "gid": str(retained_after.st_gid),
        }.items()))
        publication = H11RootPublicationView(
            flow=self, slot=self._slots[2], parent_slot=self._slots[12],
            final_name="PERMIT.json", raw=publication_raw,
            reference_items=reference_items,
        )
        publication.revalidate()
        final_rows: list[H11RootTransactionState] = []
        for (role, leaf), expected in zip(
            _H11_TRANSACTION_LAYOUT,
            _H11_TRANSACTION_PHASES["permit-committed"],
        ):
            try:
                os.stat(
                    leaf,
                    dir_fd=self._slots[12].borrow(),
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                observed = "absent"
            else:
                observed = "present"
            if observed != expected:
                _fail(f"H11 transaction {role} drifted after permit publication")
            final_rows.append(
                H11RootTransactionState(
                    role,
                    authority.scenario_root_directory.reference.path / leaf,
                    observed,
                )
            )
        authorization_final = os.stat(
            "AUTHORIZE-RELEASE.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        ready_final = os.stat(
            "PERMIT_READY.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        if (
            (str(authorization_final.st_dev), str(authorization_final.st_ino))
            != (dict(authority.authorization_view.source)["device"], dict(authority.authorization_view.source)["inode"])
            or (str(ready_final.st_dev), str(ready_final.st_ino))
            != (dict(authority.permit_ready_view.source)["device"], dict(authority.permit_ready_view.source)["inode"])
        ):
            _fail("H11 transaction sources drifted after publication")
        transaction_state = tuple(final_rows)
        authority.authorization_view.revalidate()
        authority.harness_manifest_view.revalidate()
        authority.install_receipt_view.revalidate()
        authority.install_manifest_view.revalidate()
        authority.tree_receipt_view.revalidate()
        authority.seal_receipt_view.revalidate()
        authority.preflight_receipt_view.revalidate()
        authority.permit_ready_view.revalidate()
        authority.run_armed_view.revalidate()
        authority.formal_root_directory.revalidate()
        authority.authority_root_directory.revalidate()
        authority.harness_root_directory.revalidate()
        authority.scenario_root_directory.revalidate()
        authority.input_root_directory.revalidate()
        authority.receipt_root_directory.revalidate()
        authority.fifo_root_directory.revalidate()
        authority.ready_commit_fifo.revalidate()
        authority.permit_commit_fifo.revalidate()
        phase_data.present_h0.revalidate()
        phase_data.present_run_main_properties.revalidate()
        self._phase_data = H11RootPermitPhaseData(
            ready_data=phase_data,
            barrier=barrier,
            publication=publication,
            transaction_state=transaction_state,
        )
        self._transition(
            expected=H11RootAuthorizationState.READY_CONSUMED,
            target=H11RootAuthorizationState.PERMIT_PUBLISHED,
        )
        return None

    def _commit_permit(self) -> H11RootCommitReceipt:
        phase_data = self._phase_data
        if (
            self._state is not H11RootAuthorizationState.PERMIT_PUBLISHED
            or type(phase_data) is not H11RootPermitPhaseData
        ):
            _fail("H11 permit commit requires exact published permit data")
        authority = phase_data.ready_data.authority_data.authority
        if (
            phase_data.barrier.directory_chain
            != (
                authority.formal_root_directory.reference,
                authority.authority_root_directory.reference,
                authority.harness_root_directory.reference,
                authority.scenario_root_directory.reference,
                authority.input_root_directory.reference,
                authority.receipt_root_directory.reference,
                authority.fifo_root_directory.reference,
            )
            or phase_data.barrier.present_outputs_sha256
            != phase_data.ready_data.present_outputs_sha256
            or phase_data.barrier.future_absence_sha256
            != phase_data.ready_data.future_absence_sha256
            or phase_data.barrier.transaction_state
            != phase_data.ready_data.transaction_state
            or phase_data.barrier.future_absence_inventory
            != phase_data.ready_data.partition.future_absence_inventory
        ):
            _fail("H11 pre-permit barrier evidence drifted before commit")
        authority.authorization_view.revalidate()
        authority.harness_manifest_view.revalidate()
        authority.install_receipt_view.revalidate()
        authority.install_manifest_view.revalidate()
        authority.tree_receipt_view.revalidate()
        authority.seal_receipt_view.revalidate()
        authority.preflight_receipt_view.revalidate()
        authority.permit_ready_view.revalidate()
        authority.run_armed_view.revalidate()
        authority.formal_root_directory.revalidate()
        authority.authority_root_directory.revalidate()
        authority.harness_root_directory.revalidate()
        authority.scenario_root_directory.revalidate()
        authority.input_root_directory.revalidate()
        authority.receipt_root_directory.revalidate()
        authority.fifo_root_directory.revalidate()
        authority.ready_commit_fifo.revalidate()
        authority.permit_commit_fifo.revalidate()
        phase_data.publication.revalidate()
        phase_data.ready_data.present_h0.revalidate()
        phase_data.ready_data.present_run_main_properties.revalidate()
        entry_rows: list[H11RootTransactionState] = []
        for (role, leaf), expected in zip(
            _H11_TRANSACTION_LAYOUT,
            _H11_TRANSACTION_PHASES["permit-committed"],
        ):
            try:
                os.stat(
                    leaf,
                    dir_fd=self._slots[12].borrow(),
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                observed = "absent"
            else:
                observed = "present"
            if observed != expected:
                _fail(f"H11 transaction {role} drifted before permit commit")
            entry_rows.append(
                H11RootTransactionState(
                    role,
                    authority.scenario_root_directory.reference.path / leaf,
                    observed,
                )
            )
        if tuple(entry_rows) != phase_data.transaction_state:
            _fail("H11 permit transaction evidence drifted before writer open")
        authorization_entry = os.stat(
            "AUTHORIZE-RELEASE.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        ready_entry = os.stat(
            "PERMIT_READY.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        if (
            (str(authorization_entry.st_dev), str(authorization_entry.st_ino))
            != (dict(authority.authorization_view.source)["device"], dict(authority.authorization_view.source)["inode"])
            or (str(ready_entry.st_dev), str(ready_entry.st_ino))
            != (dict(authority.permit_ready_view.source)["device"], dict(authority.permit_ready_view.source)["inode"])
        ):
            _fail("H11 transaction sources drifted before permit writer")
        fifo = authority.permit_commit_fifo
        if (
            fifo is not authority.permit_commit_fifo
            or fifo._flow is not self
            or fifo._slot is not self._slots[7]
            or fifo._parent_slot is not self._slots[9]
        ):
            _fail("H11 PERMIT receipt FIFO identity gate failed")
        receipt = H11RootCommitReceipt.permit_committed(
            fifo,
            H11_PERMIT_COMMITTED_BYTES,
        )
        self._slots[0].open(
            f"/proc/self/fd/{self._slots[7].borrow()}",
            os.O_WRONLY | os.O_CLOEXEC,
        )
        authority.permit_commit_fifo.reference.prove(
            os.fstat(self._slots[0].borrow()),
            label="H11 permit-commit writer",
        )
        self._transition(
            expected=H11RootAuthorizationState.PERMIT_PUBLISHED,
            target=H11RootAuthorizationState.PERMIT_WRITER_OPEN,
        )
        authority.authorization_view.revalidate()
        authority.harness_manifest_view.revalidate()
        authority.install_receipt_view.revalidate()
        authority.install_manifest_view.revalidate()
        authority.tree_receipt_view.revalidate()
        authority.seal_receipt_view.revalidate()
        authority.preflight_receipt_view.revalidate()
        authority.permit_ready_view.revalidate()
        authority.run_armed_view.revalidate()
        authority.formal_root_directory.revalidate()
        authority.authority_root_directory.revalidate()
        authority.harness_root_directory.revalidate()
        authority.scenario_root_directory.revalidate()
        authority.input_root_directory.revalidate()
        authority.receipt_root_directory.revalidate()
        authority.fifo_root_directory.revalidate()
        authority.ready_commit_fifo.revalidate()
        authority.permit_commit_fifo.revalidate()
        phase_data.publication.revalidate()
        phase_data.ready_data.present_h0.revalidate()
        phase_data.ready_data.present_run_main_properties.revalidate()
        writer_rows: list[H11RootTransactionState] = []
        for (role, leaf), expected in zip(
            _H11_TRANSACTION_LAYOUT,
            _H11_TRANSACTION_PHASES["permit-committed"],
        ):
            try:
                os.stat(
                    leaf,
                    dir_fd=self._slots[12].borrow(),
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                observed = "absent"
            else:
                observed = "present"
            if observed != expected:
                _fail(f"H11 transaction {role} drifted after permit writer open")
            writer_rows.append(
                H11RootTransactionState(
                    role,
                    authority.scenario_root_directory.reference.path / leaf,
                    observed,
                )
            )
        if tuple(writer_rows) != phase_data.transaction_state:
            _fail("H11 permit transaction evidence drifted after writer open")
        authorization_writer = os.stat(
            "AUTHORIZE-RELEASE.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        ready_writer = os.stat(
            "PERMIT_READY.json",
            dir_fd=self._slots[12].borrow(),
            follow_symlinks=False,
        )
        if (
            (str(authorization_writer.st_dev), str(authorization_writer.st_ino))
            != (dict(authority.authorization_view.source)["device"], dict(authority.authorization_view.source)["inode"])
            or (str(ready_writer.st_dev), str(ready_writer.st_ino))
            != (dict(authority.permit_ready_view.source)["device"], dict(authority.permit_ready_view.source)["inode"])
        ):
            _fail("H11 transaction sources drifted after permit writer open")
        self._mark_write_in_flight()
        written = os.write(
            self._slots[0].borrow(),
            H11_PERMIT_COMMITTED_BYTES,
        )
        if written != len(H11_PERMIT_COMMITTED_BYTES):
            _fail("H11 PERMIT commit FIFO write was incomplete")
        self._mark_postwrite()
        self._transition(
            expected=H11RootAuthorizationState.PERMIT_WRITER_OPEN,
            target=H11RootAuthorizationState.PERMIT_FRAME_WRITTEN,
        )
        close_error = self._close_slot_once(self._slots[0])
        if close_error is not None:
            raise close_error
        return receipt

    def authorize_once(self) -> H11RootCommitReceipt:
        if self._state is not H11RootAuthorizationState.NEW:
            _fail("H11 authorization flow is one-shot")
        try:
            self._acquire_authorities()
            self._consume_ready_commit()
            self._publish_permit()
            receipt = self._commit_permit()
        except BaseException as primary:
            self._fail(active_error=primary)
        return self._finish(receipt)

def authorize_h11_release(
    manifest_path: Path,
    *,
    require_root: bool = True,
) -> dict[str, Any]:
    """Publish and commit the one external operator permit."""

    flow = H11RootAuthorizationFlow(
        manifest_path,
        require_root=require_root,
    )
    receipt = flow.authorize_once()
    return receipt.reference


def cleanup_units(
    manifest_path: Path,
    *,
    manager: Manager | None = None,
    require_root: bool = True,
) -> dict[str, Any]:
    """Explicitly remove the exact installed fragments after a complete freeze."""

    _require_root(require_root)
    _require_manifest_authority(manifest_path, require_root=require_root)
    plan = _decode(manifest_path)
    _exact(
        plan,
        {
            "schema",
            "formal_root",
            "install_receipt",
            "frozen_receipt",
            "receipt_path",
        },
        label="cleanup manifest",
    )
    if plan["schema"] != CLEANUP_SCHEMA:
        _fail("unexpected cleanup schema")
    root = _path(plan["formal_root"], label="formal_root")
    authority = root / "authority"
    receipt_path = _path(plan["receipt_path"], label="receipt_path")
    started_path = authority / "CLEANUP-STARTED.json"
    if receipt_path.parent != authority:
        _fail("cleanup receipt must be one immediate authority child")
    if receipt_path == started_path:
        _fail("cleanup receipt and mutation marker paths alias")
    _require_absent(receipt_path, label="cleanup receipt destination")
    _require_absent(started_path, label="cleanup transaction marker")
    _install_path, install_receipt, _install_raw = _bound_json_input(
        plan["install_receipt"], label="install_receipt"
    )
    units = _validate_install_receipt(
        install_receipt,
        root=root,
        reference=plan["install_receipt"],
        require_root=require_root,
    )
    frozen_path, frozen, _frozen_raw = _bound_json_input(
        plan["frozen_receipt"], label="frozen_receipt"
    )
    if (
        frozen_path != root / "frozen" / "FROZEN"
    ):
        _fail("cleanup frozen receipt path is not exact formal_root/frozen/FROZEN")
    _validate_frozen_receipt(
        frozen,
        root=root,
        install_reference=plan["install_receipt"],
        require_root=require_root,
    )
    validated: list[tuple[str, Path, dict[str, Any]]] = []
    parents: set[Path] = set()
    for item in units:
        target_binding = item["target"]
        target = _path(target_binding["path"], label="cleanup target")
        raw = _read_regular(target, label=f"cleanup target {item['unit']}")
        info = target.lstat()
        if (
            hashlib.sha256(raw).hexdigest() != target_binding["sha256"]
            or (str(info.st_dev), str(info.st_ino))
            != (target_binding["device"], target_binding["inode"])
            or str(info.st_uid) != target_binding["uid"]
            or str(info.st_gid) != target_binding["gid"]
            or format(stat.S_IMODE(info.st_mode), "04o") != target_binding["mode"]
            or (require_root and target.parent != Path("/run/systemd/system"))
        ):
            _fail(f"installed cleanup target drifted: {item['unit']}")
        validated.append((item["unit"], target, target_binding))
        parents.add(target.parent)
    active_manager = manager if manager is not None else DBusManager()
    owner = _text(active_manager.owner, label="cleanup manager owner")
    if _UNIQUE_OWNER_RE.fullmatch(owner) is None:
        _fail("cleanup manager owner is not one canonical unique bus name")
    if owner != install_receipt["manager_owner"]:
        _fail("system manager owner changed before explicit cleanup")
    manifest_reference = _manifest_reference(manifest_path)
    _write_no_replace(
        started_path,
        {
            "schema": "scion.generic_backend.root_cleanup_started.v1",
            "formal_root": str(root),
            "cleanup_manifest": manifest_reference,
            "phase": "cleanup-mutation-started",
        },
        mode=0o400,
    )
    removed: list[dict[str, Any]] = []
    for unit, target, binding in validated:
        os.unlink(target)
        removed.append({"unit": unit, "target": binding})
    for parent in sorted(parents):
        _fsync_directory(parent)
    active_manager.reload()
    for _unit, target, _binding in validated:
        if target.exists() or target.is_symlink():
            _fail(f"cleanup target remains after unlink: {target}")
    cleanup = {
        "schema": CLEANUP_RECEIPT_SCHEMA,
        "formal_root": _identity(root),
        "cleanup_manifest": manifest_reference,
        "install_receipt": dict(plan["install_receipt"]),
        "frozen_receipt": dict(plan["frozen_receipt"]),
        "manager_owner": owner,
        "manager_ledger": [
            {
                "begin_ordinal": "1",
                "reply_ordinal": "2",
                "interface": "org.freedesktop.systemd1.Manager",
                "member": "Reload",
                "object_path": "/org/freedesktop/systemd1",
                "signature": "",
                "arguments": [],
                "reply": None,
            }
        ],
        "reload_call_count": "1",
        "removed_units": removed,
        "phase": "explicit-cleanup-complete-not-evidence",
    }
    _write_no_replace(receipt_path, cleanup, mode=0o444)
    return cleanup


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise InstallerError(
            "usage: generic_backend_root_installer.py "
            "prepare-tree|seal|install|authorize-h11-release|freeze|cleanup "
            "MANIFEST.json"
        )
    command, raw_path = argv[1:]
    path = Path(raw_path)
    if command == "prepare-tree":
        prepare_tree(path)
    elif command == "seal":
        seal_tree(path)
    elif command == "install":
        install_units(path)
    elif command == "authorize-h11-release":
        authorize_h11_release(path)
    elif command == "freeze":
        freeze_receipts(path)
    elif command == "cleanup":
        cleanup_units(path)
    else:
        _fail("unknown installer transaction")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except InstallerError as exc:
        print(f"generic-backend-root-installer: {exc}", file=sys.stderr)
        raise SystemExit(64) from exc
