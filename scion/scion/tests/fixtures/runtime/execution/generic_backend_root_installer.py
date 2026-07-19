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
from typing import Any, Callable, NoReturn, Protocol


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


def _pin_h11_json_source(
    path: Path,
    *,
    label: str,
    expected_reference: Any | None = None,
    ownership_bound: bool = False,
    required_mode: int | None = None,
    require_root_owner: bool = False,
) -> tuple[int, dict[str, Any], bytes, dict[str, str]]:
    """Open one H11 authority once and retain the exact decoded source."""

    expected: dict[str, Any] | None = None
    if expected_reference is not None:
        if type(expected_reference) is not dict:
            _fail(f"{label} reference must be one exact object")
        expected_keys = {"path", "sha256", "device", "inode", "mode"}
        if ownership_bound:
            expected_keys |= {"uid", "gid"}
        _exact(expected_reference, expected_keys, label=f"{label} reference")
        expected = dict(expected_reference)
        if _path(expected["path"], label=f"{label}.path") != path:
            _fail(f"{label} path differs from its reference")
        if _HEX_RE.fullmatch(_text(expected["sha256"], label=f"{label}.sha256")) is None:
            _fail(f"{label}.sha256 is not canonical")
        _uint(expected["device"], label=f"{label}.device")
        _uint(expected["inode"], label=f"{label}.inode")
        mode = _text(expected["mode"], label=f"{label}.mode")
        if _MODE_RE.fullmatch(mode) is None:
            _fail(f"{label}.mode is not canonical")
        if ownership_bound:
            _uint(expected["uid"], label=f"{label}.uid")
            _uint(expected["gid"], label=f"{label}.gid")
    try:
        before = path.lstat()
    except OSError as exc:
        raise InstallerError(f"cannot stat {label}: {path}") from exc
    if not stat.S_ISREG(before.st_mode):
        _fail(f"{label} must be one non-symlink regular file")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise InstallerError(f"cannot pin {label}: {path}") from exc
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
        current = path.lstat()
        source = {
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "device": str(after.st_dev),
            "inode": str(after.st_ino),
            "mode": format(stat.S_IMODE(after.st_mode), "04o"),
            "uid": str(after.st_uid),
            "gid": str(after.st_gid),
        }
        if (
            not stat.S_ISREG(after.st_mode)
            or (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
            or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
            or after.st_size != len(raw)
            or after.st_mtime_ns != before.st_mtime_ns
            or current.st_size != before.st_size
            or current.st_mtime_ns != before.st_mtime_ns
        ):
            _fail(f"{label} bytes or identity drifted while pinning")
        if required_mode is not None and stat.S_IMODE(after.st_mode) != required_mode:
            _fail(f"{label} mode is not {required_mode:04o}")
        if require_root_owner and (after.st_uid != 0 or after.st_gid != 0):
            _fail(f"{label} must be root-owned")
        if expected is not None:
            actual_reference = {
                key: source[key]
                for key in expected
            }
            if actual_reference != expected:
                _fail(f"{label} differs from its frozen full reference")
        decoded = _decode_canonical_object(raw, label=label)
        os.lseek(descriptor, 0, os.SEEK_SET)
        return descriptor, decoded, raw, source
    except BaseException as exc:
        closing_descriptor = descriptor
        descriptor = -1
        _close_h11_ownership(
            (),
            active_error=exc,
            initial_descriptor=closing_descriptor,
        )
        raise


def _revalidate_h11_source(
    descriptor: int,
    path: Path,
    raw: bytes,
    source: dict[str, str],
    *,
    label: str,
) -> None:
    """Revalidate one retained H11 source without reopening its path for bytes."""

    try:
        opened = os.fstat(descriptor)
        current = path.lstat()
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        reread = b"".join(chunks)
        os.lseek(descriptor, 0, os.SEEK_SET)
    except OSError as exc:
        raise InstallerError(f"cannot revalidate retained {label}") from exc
    if (
        reread != raw
        or hashlib.sha256(reread).hexdigest() != source["sha256"]
        or (str(opened.st_dev), str(opened.st_ino))
        != (source["device"], source["inode"])
        or (str(current.st_dev), str(current.st_ino))
        != (source["device"], source["inode"])
        or format(stat.S_IMODE(opened.st_mode), "04o") != source["mode"]
        or format(stat.S_IMODE(current.st_mode), "04o") != source["mode"]
        or str(opened.st_uid) != source["uid"]
        or str(opened.st_gid) != source["gid"]
        or str(current.st_uid) != source["uid"]
        or str(current.st_gid) != source["gid"]
    ):
        _fail(f"retained {label} drifted before permit publication")


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
    def decode(cls, value: Any, *, label: str) -> "H11RootDirectoryReference":
        if type(value) is not dict:
            _fail(f"{label} must be one exact directory reference")
        _exact(
            value,
            {"role", "path", "device", "inode", "mode", "uid", "gid"},
            label=label,
        )
        mode_text = _text(value["mode"], label=f"{label}.mode")
        if _MODE_RE.fullmatch(mode_text) is None:
            _fail(f"{label}.mode is not canonical")
        return cls(
            _text(value["role"], label=f"{label}.role"),
            _path(value["path"], label=f"{label}.path"),
            _uint(value["device"], label=f"{label}.device"),
            _uint(value["inode"], label=f"{label}.inode"),
            int(mode_text, 8),
            _uint(value["uid"], label=f"{label}.uid"),
            _uint(value["gid"], label=f"{label}.gid"),
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

    @classmethod
    def decode(cls, value: Any, *, label: str) -> "H11RootFifoReference":
        if type(value) is not dict:
            _fail(f"{label} must be one exact FIFO reference")
        _exact(
            value,
            {"path", "device", "inode", "mode", "uid", "gid"},
            label=label,
        )
        mode_text = _text(value["mode"], label=f"{label}.mode")
        if _MODE_RE.fullmatch(mode_text) is None:
            _fail(f"{label}.mode is not canonical")
        return cls(
            _path(value["path"], label=f"{label}.path"),
            _uint(value["device"], label=f"{label}.device"),
            _uint(value["inode"], label=f"{label}.inode"),
            int(mode_text, 8),
            _uint(value["uid"], label=f"{label}.uid"),
            _uint(value["gid"], label=f"{label}.gid"),
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

    def prove(self, info: os.stat_result, *, require_root: bool, label: str) -> None:
        test_root_owner = (
            not require_root
            and (self.uid, self.gid) == (0, 0)
            and (info.st_uid, info.st_gid) == (os.geteuid(), os.getegid())
        )
        if (
            not stat.S_ISFIFO(info.st_mode)
            or (info.st_dev, info.st_ino) != (self.device, self.inode)
            or stat.S_IMODE(info.st_mode) != self.mode
            or self.mode != 0o600
            or (
                (info.st_uid, info.st_gid) != (self.uid, self.gid)
                and not test_root_owner
            )
            or (require_root and (self.uid != 0 or self.gid != 0))
        ):
            _fail(f"{label} FIFO identity/mode/owner drifted")


def _close_h11_ownership(
    owners: tuple[Any, ...],
    *,
    active_error: BaseException | None = None,
    initial_descriptor: int = -1,
    final_descriptor: int = -1,
) -> None:
    first_error: BaseException | None = None
    if initial_descriptor >= 0:
        try:
            os.close(initial_descriptor)
        except BaseException as exc:
            first_error = exc
    for owner in owners:
        try:
            owner.close()
        except BaseException as exc:
            if first_error is None:
                first_error = exc
    if final_descriptor >= 0:
        try:
            os.close(final_descriptor)
        except BaseException as exc:
            if first_error is None:
                first_error = exc
    if first_error is not None:
        if active_error is None:
            raise first_error
        active_error.add_note(
            "H11 ownership teardown secondary: "
            f"{type(first_error).__name__}: {first_error}"
        )


@dataclass(frozen=True, slots=True)
class H11RootCommitReceipt:
    phase: str
    fifo: H11RootFifoReference
    payload_sha256: str
    byte_count: str

    @classmethod
    def ready_committed(
        cls,
        fifo: "RetainedH11RootFifo",
        payload: bytes,
    ) -> "H11RootCommitReceipt":
        if fifo.role != "h11-ready-commit" or payload != H11_READY_COMMITTED_BYTES:
            _fail("H11 READY commit receipt source is not the exact committed frame")
        return cls(
            "ready-committed",
            fifo.reference,
            hashlib.sha256(payload).hexdigest(),
            str(len(payload)),
        )

    @classmethod
    def permit_committed(
        cls,
        fifo: "RetainedH11RootFifo",
        payload: bytes,
    ) -> "H11RootCommitReceipt":
        if (
            fifo.role != "h11-permit-commit"
            or payload != H11_PERMIT_COMMITTED_BYTES
        ):
            _fail("H11 PERMIT commit receipt source is not the exact committed frame")
        return cls(
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


@dataclass
class RetainedH11RootDirectory:
    reference: H11RootDirectoryReference
    descriptor: int
    parent_descriptor: int | None
    child_name: str | None

    def revalidate(self, *, require_root: bool) -> None:
        if self.descriptor < 0:
            _fail(f"H11 {self.reference.role} descriptor closed before last use")
        try:
            opened = os.fstat(self.descriptor)
            current = (
                self.reference.path.lstat()
                if self.parent_descriptor is None
                else os.stat(
                    self.child_name,
                    dir_fd=self.parent_descriptor,
                    follow_symlinks=False,
                )
            )
        except OSError as exc:
            raise InstallerError(
                f"cannot revalidate H11 {self.reference.role}"
            ) from exc
        self.reference.prove(
            opened, require_root=require_root, label=f"H11 {self.reference.role}"
        )
        self.reference.prove(
            current, require_root=require_root, label=f"H11 {self.reference.role}"
        )

    def close(self) -> None:
        if self.descriptor >= 0:
            descriptor = self.descriptor
            self.descriptor = -1
            os.close(descriptor)


@dataclass
class RetainedH11RootFifo:
    role: str
    reference: H11RootFifoReference
    descriptor: int
    parent_descriptor: int

    def revalidate(self, *, require_root: bool) -> None:
        if self.descriptor < 0:
            _fail(f"H11 {self.role} descriptor closed before last use")
        try:
            opened = os.fstat(self.descriptor)
            current = os.stat(
                self.reference.path.name,
                dir_fd=self.parent_descriptor,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise InstallerError(f"cannot revalidate H11 {self.role}") from exc
        self.reference.prove(
            opened, require_root=require_root, label=f"H11 {self.role}"
        )
        self.reference.prove(
            current, require_root=require_root, label=f"H11 {self.role}"
        )

    def read_ready_commit(self, *, require_root: bool) -> H11RootCommitReceipt:
        """Consume the one blocking descriptor-bound READY commit frame."""

        if self.role != "h11-ready-commit":
            _fail("only the retained READY commit FIFO authorizes a root reader")
        if self.descriptor < 0:
            _fail("H11 READY commit FIFO descriptor closed before endpoint open")
        descriptor = -1
        chunks: list[bytes] = []
        try:
            try:
                descriptor = os.open(
                    f"/proc/self/fd/{self.descriptor}",
                    os.O_RDONLY | os.O_CLOEXEC,
                )
            except OSError as exc:
                raise InstallerError(
                    "cannot open H11 READY commit reader"
                ) from exc
            self.reference.prove(
                os.fstat(descriptor),
                require_root=require_root,
                label="H11 ready-commit reader",
            )
            while True:
                chunk = os.read(descriptor, select.PIPE_BUF)
                if not chunk:
                    break
                chunks.append(chunk)
            closing_descriptor = descriptor
            descriptor = -1
            os.close(closing_descriptor)
            payload = b"".join(chunks)
            if payload != H11_READY_COMMITTED_BYTES:
                _fail("H11 READY commit FIFO frame differs before EOF")
            return H11RootCommitReceipt.ready_committed(self, payload)
        except BaseException as exc:
            closing_descriptor = descriptor
            descriptor = -1
            _close_h11_ownership(
                (),
                active_error=exc,
                initial_descriptor=closing_descriptor,
            )
            raise

    def open_permit_commit_writer(self, *, require_root: bool) -> int:
        """Open and prove the retained blocking PERMIT commit writer."""

        if self.role != "h11-permit-commit":
            _fail("only the retained PERMIT commit FIFO authorizes a root writer")
        if self.descriptor < 0:
            _fail("H11 PERMIT commit FIFO descriptor closed before endpoint open")
        descriptor = -1
        try:
            descriptor = os.open(
                f"/proc/self/fd/{self.descriptor}",
                os.O_WRONLY | os.O_CLOEXEC,
            )
            self.reference.prove(
                os.fstat(descriptor),
                require_root=require_root,
                label="H11 permit-commit writer",
            )
            return descriptor
        except OSError as exc:
            error = InstallerError("cannot open H11 PERMIT commit writer")
            closing_descriptor = descriptor
            descriptor = -1
            _close_h11_ownership(
                (),
                active_error=error,
                initial_descriptor=closing_descriptor,
            )
            raise error from exc
        except BaseException as exc:
            closing_descriptor = descriptor
            descriptor = -1
            _close_h11_ownership(
                (),
                active_error=exc,
                initial_descriptor=closing_descriptor,
            )
            raise

    def close(self) -> None:
        if self.descriptor >= 0:
            descriptor = self.descriptor
            self.descriptor = -1
            os.close(descriptor)


@dataclass
class RetainedH11RootJsonSource:
    descriptor: int
    path: Path
    raw: bytes
    source: dict[str, str]
    label: str

    def revalidate(self) -> None:
        if self.descriptor < 0:
            _fail(f"retained {self.label} descriptor closed before last use")
        _revalidate_h11_source(
            self.descriptor,
            self.path,
            self.raw,
            self.source,
            label=self.label,
        )

    def close(self) -> None:
        if self.descriptor >= 0:
            descriptor = self.descriptor
            self.descriptor = -1
            os.close(descriptor)


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

    @classmethod
    def from_tree_row(
        cls, value: dict[str, str], *, label: str
    ) -> "H11RootValidatedFifo":
        mode_text = _text(value["mode"], label=f"{label}.mode")
        if _MODE_RE.fullmatch(mode_text) is None:
            _fail(f"{label}.mode is not canonical")
        return cls(
            _text(value["role"], label=f"{label}.role"),
            _path(value["path"], label=f"{label}.path"),
            _text(value["owner"], label=f"{label}.owner"),
            _uint(value["uid"], label=f"{label}.uid"),
            _uint(value["gid"], label=f"{label}.gid"),
            int(mode_text, 8),
            _uint(value["device"], label=f"{label}.device"),
            _uint(value["inode"], label=f"{label}.inode"),
        )

    @property
    def acquisition_reference(self) -> dict[str, str]:
        return {
            "path": str(self.path),
            "device": str(self.device),
            "inode": str(self.inode),
        }


@dataclass
class H11RootRetainedAuthority:
    manifest_path: Path
    manifest_descriptor: int
    manifest: dict[str, Any]
    manifest_raw: bytes
    manifest_source: dict[str, str]
    require_root: bool
    bound_sources: tuple[RetainedH11RootJsonSource, ...]
    directories: tuple[RetainedH11RootDirectory, ...]
    commit_fifos: tuple[RetainedH11RootFifo, ...]
    fixture_uid: int
    fixture_gid: int
    validated_fifos: tuple[H11RootValidatedFifo, ...]

    @staticmethod
    def _decode_fifo_rows(
        tree_receipt: Any, preflight_receipt: Any
    ) -> dict[str, dict[str, Any]]:
        if type(tree_receipt) is not dict or type(preflight_receipt) is not dict:
            _fail("H11 TREE/PREFLIGHT receipts must be exact objects")
        tree_rows = tree_receipt.get("fifos")
        preflight_rows = preflight_receipt.get("fifos")
        if type(tree_rows) is not list or preflight_rows != tree_rows:
            _fail("H11 TREE/PREFLIGHT FIFO inventories differ")
        rows: dict[str, dict[str, Any]] = {}
        for index, row in enumerate(tree_rows):
            if type(row) is not dict:
                _fail(f"H11 TREE FIFO row {index} is not an object")
            _exact(
                row,
                {"role", "path", "owner", "uid", "gid", "mode", "device", "inode"},
                label=f"H11 TREE FIFO row {index}",
            )
            role = _text(row["role"], label=f"H11 TREE FIFO row {index}.role")
            if role in rows:
                _fail("H11 TREE FIFO role is duplicated")
            rows[role] = row
        if list(rows) != sorted(rows):
            _fail("H11 TREE FIFO inventory is not sorted by role")
        return rows

    @classmethod
    def open(
        cls,
        manifest_path: Path,
        *,
        require_root: bool = True,
    ) -> "H11RootRetainedAuthority":
        manifest_descriptor = -1
        bound_sources: list[RetainedH11RootJsonSource] = []
        directories: list[RetainedH11RootDirectory] = []
        fifos: list[RetainedH11RootFifo] = []
        result: H11RootRetainedAuthority | None = None
        try:
            (
                manifest_descriptor,
                manifest,
                manifest_raw,
                manifest_source,
            ) = _pin_h11_json_source(
                manifest_path,
                label="H11 harness manifest",
                required_mode=0o444,
                require_root_owner=require_root,
            )
            _exact(
                manifest,
                _H11_HARNESS_MANIFEST_KEYS,
                label="H11 harness manifest",
            )
            if (
                manifest["schema"]
                != "scion.generic_backend.systemd_harness_manifest.v1"
                or manifest["scenario"] != "H11"
            ):
                _fail("H11 harness manifest schema/scenario drifted")
            permit_authority = manifest["permit_authority"]
            if type(permit_authority) is not dict:
                _fail("H11 permit_authority must be one exact object")
            _exact(
                permit_authority,
                _H11_PERMIT_AUTHORITY_KEYS,
                label="H11 permit_authority",
            )
            if (
                permit_authority["schema"] != H11_PERMIT_AUTHORITY_SCHEMA
                or permit_authority["scenario"] != "H11"
                or permit_authority["run_unit"] != manifest["run_unit"]
            ):
                _fail("H11 permit_authority schema/scenario/run unit drifted")

            root = manifest_path.parents[3]
            scenario_root = root / "authority" / "harness" / "H11"
            if manifest_path != scenario_root / "MANIFEST.json":
                _fail("H11 harness manifest path is outside the exact root layout")
            if (
                _path(manifest["input_root"], label="H11 manifest input_root")
                != root / "input"
                or _path(
                    manifest["receipt_root"], label="H11 manifest receipt_root"
                )
                != scenario_root / "receipts"
            ):
                _fail("H11 manifest output roots differ from the exact directory chain")

            installer_binding = manifest["installer_receipt"]
            if type(installer_binding) is not dict:
                _fail("H11 installer_receipt must be one exact hashed reference")
            _exact(
                installer_binding,
                {"path", "sha256"},
                label="H11 installer_receipt",
            )
            install_receipt_path = _path(
                installer_binding["path"], label="H11 installer_receipt.path"
            )
            if install_receipt_path.parent != root / "authority":
                _fail("H11 install receipt is outside the exact authority root")
            (
                install_receipt_descriptor,
                install_receipt,
                install_receipt_raw,
                install_receipt_source,
            ) = _pin_h11_json_source(
                install_receipt_path,
                label="H11 install receipt",
                required_mode=0o444,
                require_root_owner=require_root,
            )
            install_receipt_retained = RetainedH11RootJsonSource(
                install_receipt_descriptor,
                install_receipt_path,
                install_receipt_raw,
                install_receipt_source,
                "H11 install receipt",
            )
            bound_sources.append(install_receipt_retained)
            if {
                "path": install_receipt_source["path"],
                "sha256": install_receipt_source["sha256"],
            } != installer_binding:
                _fail("H11 installer_receipt differs from its retained source")
            _exact(
                install_receipt,
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
                label="H11 install receipt",
            )
            formal_root = install_receipt["formal_root"]
            if type(formal_root) is not dict:
                _fail("H11 install receipt formal_root must be one exact object")
            if (
                install_receipt["schema"] != INSTALL_RECEIPT_SCHEMA
                or install_receipt["phase"] != "installed-before-observation"
                or install_receipt["reload_call_count"] != "1"
            ):
                _fail("H11 install receipt schema/phase drifted")
            _validate_directory_identity(
                formal_root,
                expected_path=root,
                expected_mode=0o711,
                label="H11 install formal root",
            )
            _validate_install_receipt(
                install_receipt,
                root=root,
                reference={"path": str(install_receipt_path)},
                require_root=require_root,
            )

            install_manifest_binding = install_receipt["install_manifest"]
            if type(install_manifest_binding) is not dict:
                _fail("H11 install_manifest must be one exact full reference")
            (
                install_manifest_descriptor,
                install_manifest,
                install_manifest_raw,
                install_manifest_source,
            ) = _pin_h11_json_source(
                _path(
                    install_manifest_binding.get("path"),
                    label="H11 install_manifest.path",
                ),
                label="H11 install manifest",
                expected_reference=install_manifest_binding,
                required_mode=0o444,
                require_root_owner=require_root,
            )
            bound_sources.append(
                RetainedH11RootJsonSource(
                    install_manifest_descriptor,
                    Path(install_manifest_source["path"]),
                    install_manifest_raw,
                    install_manifest_source,
                    "H11 install manifest",
                )
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
                label="H11 bound install manifest",
            )
            if (
                install_manifest["schema"] != INSTALL_SCHEMA
                or install_manifest["formal_root"] != str(root)
                or install_manifest["receipt_path"] != str(install_receipt_path)
                or any(
                    install_manifest[key] != install_receipt[key]
                    for key in ("tree_receipt", "seal_receipt", "preflight_receipt")
                )
            ):
                _fail("H11 install receipt differs from its bound install manifest")

            retained_receipts: dict[str, tuple[dict[str, Any], dict[str, str]]] = {}
            for key, schema in (
                ("tree_receipt", TREE_RECEIPT_SCHEMA),
                ("seal_receipt", SEAL_RECEIPT_SCHEMA),
                ("preflight_receipt", PREFLIGHT_RECEIPT_SCHEMA),
            ):
                binding = install_receipt[key]
                if type(binding) is not dict:
                    _fail(f"H11 {key} must be one exact full reference")
                _exact(
                    binding,
                    {"path", "sha256", "device", "inode"},
                    label=f"H11 {key}",
                )
                source_path = _path(binding["path"], label=f"H11 {key}.path")
                descriptor, decoded, raw, source_reference = _pin_h11_json_source(
                    source_path,
                    label=f"H11 {key}",
                    required_mode=0o444,
                    require_root_owner=require_root,
                )
                retained = RetainedH11RootJsonSource(
                    descriptor,
                    source_path,
                    raw,
                    source_reference,
                    f"H11 {key}",
                )
                bound_sources.append(retained)
                if {
                    field: source_reference[field]
                    for field in ("path", "sha256", "device", "inode")
                } != binding:
                    _fail(f"H11 {key} differs from its retained full reference")
                if decoded.get("schema") != schema:
                    _fail(f"H11 {key} schema drifted")
                retained_receipts[key] = (decoded, source_reference)

            tree_receipt, tree_source = retained_receipts["tree_receipt"]
            seal_receipt, _seal_source = retained_receipts["seal_receipt"]
            preflight_receipt, _preflight_source = retained_receipts[
                "preflight_receipt"
            ]
            preflight_path = Path(_preflight_source["path"])
            if Path(tree_source["path"]).parent != root / "authority":
                _fail("H11 TREE receipt is outside the exact authority root")
            (
                _fixture_user,
                _fixture_group,
                fixture_uid,
                fixture_gid,
                tree_fifos,
            ) = _validate_tree_receipt(
                tree_receipt,
                root=root,
                receipt_path=Path(tree_source["path"]),
                require_root=require_root,
                sealed=True,
            )
            _validate_seal_receipt(
                seal_receipt,
                root=root,
                tree_reference=install_receipt["tree_receipt"],
                require_root=require_root,
            )
            _exact(
                preflight_receipt,
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
                label="H11 preflight receipt",
            )
            if (
                preflight_receipt["schema"] != PREFLIGHT_RECEIPT_SCHEMA
                or preflight_receipt["phase"] != "static-preflight-complete"
                or preflight_receipt["formal_root"] != str(root)
                or preflight_path.parent.parent != root / "authority"
                or preflight_path.name != "PREFLIGHT.json"
                or preflight_receipt["run_unit"] != manifest["run_unit"]
                or preflight_receipt["close_unit"] != manifest["closer_unit"]
                or preflight_receipt["fifos"] != tree_fifos
                or preflight_receipt["tree_receipt"]
                != {**install_receipt["tree_receipt"], "mode": "0444"}
                or preflight_receipt["seal_receipt"]
                != {**install_receipt["seal_receipt"], "mode": "0444"}
            ):
                _fail("H11 preflight receipt differs from TREE/install authority")
            manifest_preflight = manifest["preflight_receipt"]
            if type(manifest_preflight) is not dict:
                _fail("H11 manifest preflight_receipt must be one exact reference")
            _exact(
                manifest_preflight,
                {"path", "sha256"},
                label="H11 manifest preflight_receipt",
            )
            if manifest_preflight != {
                "path": _preflight_source["path"],
                "sha256": _preflight_source["sha256"],
            }:
                _fail("H11 manifest preflight authority differs from install authority")

            expected_paths = (
                root,
                root / "authority",
                root / "authority" / "harness",
                scenario_root,
                root / "input",
                scenario_root / "receipts",
                root / "fifo",
            )
            chain_values = permit_authority["directory_chain"]
            if type(chain_values) is not list or len(chain_values) != 7:
                _fail("H11 directory_chain must contain exactly seven objects")
            references = tuple(
                H11RootDirectoryReference.decode(
                    value, label=f"H11 directory_chain[{index}]"
                )
                for index, value in enumerate(chain_values)
            )
            expected_layout = tuple(
                (role, path, mode)
                for (role, mode), path in zip(_H11_DIRECTORY_LAYOUT, expected_paths)
            )
            if tuple(
                (item.role, item.path, item.mode) for item in references
            ) != expected_layout:
                _fail("H11 directory_chain order/path/mode drifted")
            if len({(item.device, item.inode) for item in references}) != 7:
                _fail("H11 directory_chain reuses one inode")
            if permit_authority["permit_parent"] != references[3].parent_reference:
                _fail("H11 permit_parent differs from retained scenario-root")

            parent_topology = (
                (None, None),
                (0, "authority"),
                (1, "harness"),
                (2, "H11"),
                (0, "input"),
                (3, "receipts"),
                (0, "fifo"),
            )
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
            for reference, (parent_index, child_name) in zip(
                references, parent_topology
            ):
                parent_descriptor = (
                    None
                    if parent_index is None
                    else directories[parent_index].descriptor
                )
                before = (
                    reference.path.lstat()
                    if parent_descriptor is None
                    else os.stat(
                        child_name,
                        dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                )
                descriptor = (
                    os.open(reference.path, flags)
                    if parent_descriptor is None
                    else os.open(
                        child_name,
                        flags,
                        dir_fd=parent_descriptor,
                    )
                )
                retained = RetainedH11RootDirectory(
                    reference, descriptor, parent_descriptor, child_name
                )
                directories.append(retained)
                reference.prove(
                    before,
                    require_root=require_root,
                    label=f"H11 {reference.role}",
                )
                retained.revalidate(require_root=require_root)

            rows = cls._decode_fifo_rows(tree_receipt, preflight_receipt)
            fifo_references = (
                (
                    "h11-ready-commit",
                    H11RootFifoReference.decode(
                        permit_authority["ready_commit_fifo"],
                        label="H11 ready_commit_fifo",
                    ),
                ),
                (
                    "h11-permit-commit",
                    H11RootFifoReference.decode(
                        permit_authority["permit_commit_fifo"],
                        label="H11 permit_commit_fifo",
                    ),
                ),
            )
            fifo_root = references[6].path
            fifo_root_descriptor = directories[6].descriptor
            for role, reference in fifo_references:
                expected_name = _H11_COMMIT_FIFO_NAMES[role]
                expected_row = {"role": role, "owner": "root", **reference.reference}
                if (
                    reference.path != fifo_root / expected_name
                    or rows.get(role) != expected_row
                ):
                    _fail(f"H11 {role} differs from TREE/PREFLIGHT authority")
                descriptor = os.open(
                    expected_name,
                    os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=fifo_root_descriptor,
                )
                retained_fifo = RetainedH11RootFifo(
                    role, reference, descriptor, fifo_root_descriptor
                )
                fifos.append(retained_fifo)
                retained_fifo.revalidate(require_root=require_root)
            if len(
                {(item.reference.device, item.reference.inode) for item in fifos}
            ) != 2:
                _fail("H11 commit FIFO identities alias")

            validated_fifos = tuple(
                H11RootValidatedFifo.from_tree_row(
                    row, label=f"H11 validated TREE FIFO {index}"
                )
                for index, row in enumerate(tree_fifos)
            )

            result = cls(
                manifest_path,
                manifest_descriptor,
                manifest,
                manifest_raw,
                manifest_source,
                require_root,
                tuple(bound_sources),
                tuple(directories),
                tuple(fifos),
                fixture_uid,
                fixture_gid,
                validated_fifos,
            )
            result.revalidate(require_root=require_root)
            return result
        except BaseException as exc:
            if result is not None:
                owners: tuple[Any, ...] = (result,)
                closing_descriptor = -1
            else:
                owners = (
                    *reversed(fifos),
                    *reversed(directories),
                    *reversed(bound_sources),
                )
                closing_descriptor = manifest_descriptor
                manifest_descriptor = -1
            _close_h11_ownership(
                owners,
                active_error=exc,
                final_descriptor=closing_descriptor,
            )
            raise

    def _transaction_paths(self, permit_authority: dict[str, Any]) -> tuple[Path, ...]:
        scenario_root = self.directories[3].reference.path
        declared_by_role = {
            "authorization": scenario_root / "AUTHORIZE-RELEASE.json",
            "permit-ready-staging": _path(
                permit_authority["permit_ready_staging_path"],
                label="H11 permit_ready_staging_path",
            ),
            "permit-ready": _path(
                permit_authority["permit_ready_path"],
                label="H11 permit_ready_path",
            ),
            "permit-staging": _path(
                permit_authority["permit_staging_path"],
                label="H11 permit_staging_path",
            ),
            "permit": _path(
                permit_authority["permit_path"],
                label="H11 permit_path",
            ),
            "permit-ledger-staging": _path(
                permit_authority["permit_ledger_staging_path"],
                label="H11 permit_ledger_staging_path",
            ),
            "permit-ledger": _path(
                permit_authority["permit_ledger_path"],
                label="H11 permit_ledger_path",
            ),
        }
        expected = tuple(
            scenario_root / leaf for _role, leaf in _H11_TRANSACTION_LAYOUT
        )
        declared = tuple(
            declared_by_role[role] for role, _leaf in _H11_TRANSACTION_LAYOUT
        )
        if declared != expected:
            _fail("H11 transaction paths differ from the exact seven-path layout")
        return expected

    def derive_closed_partition(self) -> H11RootClosedPartition:
        """Derive H11 coverage from retained manifest bytes, then check declarations."""

        self.revalidate(require_root=self.require_root)
        manifest = _decode_canonical_object(
            self.manifest_raw, label="retained H11 harness manifest"
        )
        output_values = manifest["outputs"]
        if type(output_values) is not list or len(output_values) != 12:
            _fail("H11 manifest outputs must contain exactly twelve role/path objects")
        output_by_role: dict[str, H11RootRolePath] = {}
        output_paths: set[Path] = set()
        input_root = self.directories[4].reference.path
        receipt_root = self.directories[5].reference.path
        for index, value in enumerate(output_values):
            item = H11RootRolePath.decode(
                value, label=f"H11 manifest outputs[{index}]"
            )
            if item.role in output_by_role:
                _fail("H11 manifest output role is duplicated")
            if item.path in output_paths:
                _fail("H11 manifest output path is duplicated")
            if item.path.parent not in {input_root, receipt_root}:
                _fail("H11 manifest output is outside its exact parent")
            output_by_role[item.role] = item
            output_paths.add(item.path)
        if set(output_by_role) != _H11_OUTPUT_ROLES:
            _fail("H11 manifest output roles differ from the exact closed set")

        present = tuple(output_by_role[role] for role in _H11_PRESENT_ROLES)
        root = self.directories[0].reference.path
        future = tuple(
            sorted(
                (
                    *(
                        item
                        for role, item in output_by_role.items()
                        if role not in _H11_PRESENT_ROLES
                    ),
                    H11RootRolePath("frozen-root", root / "frozen"),
                ),
                key=lambda item: item.role,
            )
        )
        present_roles = {item.role for item in present}
        future_roles = {item.role for item in future}
        if (
            len(present) != 2
            or len(future) != 11
            or present_roles & future_roles
            or present_roles | future_roles
            != _H11_OUTPUT_ROLES | {"frozen-root"}
        ):
            _fail("H11 present/future partition does not close the exact universe")

        permit_authority = manifest["permit_authority"]
        if type(permit_authority) is not dict:
            _fail("H11 permit_authority must be one exact object")
        declared_present = permit_authority["present_prerequisite_roles"]
        if (
            type(declared_present) is not list
            or any(type(role) is not str for role in declared_present)
            or declared_present != list(_H11_PRESENT_ROLES)
        ):
            _fail("H11 declared present prerequisites differ from the derived partition")
        declared_future_values = permit_authority["future_absence_inventory"]
        if type(declared_future_values) is not list:
            _fail("H11 declared future absence inventory must be one exact array")
        declared_future = tuple(
            H11RootRolePath.decode(
                value, label=f"H11 future_absence_inventory[{index}]"
            )
            for index, value in enumerate(declared_future_values)
        )
        if declared_future != future:
            _fail("H11 declared future absence inventory differs from the derived partition")

        transaction_paths = self._transaction_paths(permit_authority)
        path_authorities = [
            *((f"output:{item.role}", item.path) for item in output_by_role.values()),
            ("frozen-root", root / "frozen"),
            *(
                (f"transaction:{role}", path)
                for (role, _leaf), path in zip(
                    _H11_TRANSACTION_LAYOUT, transaction_paths
                )
            ),
            *(
                (f"commit-fifo:{item.role}", item.reference.path)
                for item in self.commit_fifos
            ),
            *(
                (f"directory:{item.reference.role}", item.reference.path)
                for item in self.directories
            ),
            ("source:harness-manifest", self.manifest_path),
            *((f"source:{item.label}", item.path) for item in self.bound_sources),
        ]
        seen_paths: dict[Path, str] = {}
        for label, path in path_authorities:
            previous = seen_paths.get(path)
            if previous is not None:
                _fail(f"H11 path authority aliases {previous} and {label}")
            seen_paths[path] = label

        regular_sources = (
            ("H11 harness manifest", self.manifest_source),
            *((item.label, item.source) for item in self.bound_sources),
        )
        seen_source_inodes: dict[tuple[str, str], str] = {}
        for label, source in regular_sources:
            identity = (source["device"], source["inode"])
            previous = seen_source_inodes.get(identity)
            if previous is not None:
                _fail(f"H11 retained regular source aliases {previous} and {label}")
            seen_source_inodes[identity] = label

        return H11RootClosedPartition(present, future)

    def validate_transaction_phase(
        self, phase: str
    ) -> tuple[H11RootTransactionState, ...]:
        if type(phase) is not str or phase not in _H11_TRANSACTION_PHASES:
            _fail("H11 transaction phase is outside the exact phase table")
        expected_states = _H11_TRANSACTION_PHASES[phase]
        self.revalidate(require_root=self.require_root)
        manifest = _decode_canonical_object(
            self.manifest_raw, label="retained H11 harness manifest"
        )
        permit_authority = manifest["permit_authority"]
        if type(permit_authority) is not dict:
            _fail("H11 permit_authority must be one exact object")
        paths = self._transaction_paths(permit_authority)
        scenario_directory = self.directories[3]
        source_identities = {
            (self.manifest_source["device"], self.manifest_source["inode"]),
            *(
                (source.source["device"], source.source["inode"])
                for source in self.bound_sources
            ),
        }
        present_identities: set[tuple[str, str]] = set()
        rows: list[H11RootTransactionState] = []
        for (role, leaf), path, expected_state in zip(
            _H11_TRANSACTION_LAYOUT, paths, expected_states
        ):
            try:
                info = os.stat(
                    leaf,
                    dir_fd=scenario_directory.descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                actual_state = "absent"
                info = None
            except OSError as exc:
                raise InstallerError(
                    f"cannot validate H11 transaction leaf {leaf}"
                ) from exc
            else:
                actual_state = "present"
            if actual_state != expected_state:
                _fail(
                    f"H11 transaction {role} state differs in phase {phase}"
                )
            if info is not None:
                expected_owner = (
                    (0, 0)
                    if self.require_root
                    else (
                        scenario_directory.reference.uid,
                        scenario_directory.reference.gid,
                    )
                )
                if (
                    not stat.S_ISREG(info.st_mode)
                    or stat.S_IMODE(info.st_mode) != 0o444
                    or (info.st_uid, info.st_gid) != expected_owner
                ):
                    _fail(
                        f"H11 transaction {role} type/mode/owner is invalid"
                    )
                identity = (str(info.st_dev), str(info.st_ino))
                if identity in source_identities:
                    _fail(f"H11 transaction {role} aliases a retained source")
                if identity in present_identities:
                    _fail("H11 present transaction inodes alias")
                present_identities.add(identity)
            rows.append(H11RootTransactionState(role, path, actual_state))
        return tuple(rows)

    def revalidate(self, *, require_root: bool) -> None:
        _revalidate_h11_source(
            self.manifest_descriptor,
            self.manifest_path,
            self.manifest_raw,
            self.manifest_source,
            label="H11 harness manifest",
        )
        for source in self.bound_sources:
            source.revalidate()
        for directory in self.directories:
            directory.revalidate(require_root=require_root)
        for fifo in self.commit_fifos:
            fifo.revalidate(require_root=require_root)

    def close(self) -> None:
        descriptor = self.manifest_descriptor
        self.manifest_descriptor = -1
        _close_h11_ownership(
            (
                *reversed(self.commit_fifos),
                *reversed(self.directories),
                *reversed(self.bound_sources),
            ),
            final_descriptor=descriptor,
        )


def _decode_h11_full_source_reference(
    value: Any, *, label: str, expected_mode: str
) -> tuple[Path, dict[str, Any]]:
    if type(value) is not dict:
        _fail(f"{label} must be one exact full source reference")
    _exact(
        value,
        {"path", "sha256", "device", "inode", "mode", "uid", "gid"},
        label=label,
    )
    path = _path(value["path"], label=f"{label}.path")
    if _HEX_RE.fullmatch(_text(value["sha256"], label=f"{label}.sha256")) is None:
        _fail(f"{label}.sha256 is not canonical")
    _uint(value["device"], label=f"{label}.device")
    _uint(value["inode"], label=f"{label}.inode")
    if value["mode"] != expected_mode:
        _fail(f"{label}.mode must be {expected_mode}")
    _uint(value["uid"], label=f"{label}.uid")
    _uint(value["gid"], label=f"{label}.gid")
    return path, value


def _decode_h11_hashed_path(
    value: Any, *, label: str
) -> tuple[Path, str]:
    if type(value) is not dict:
        _fail(f"{label} must be one exact hashed path")
    _exact(value, _H11_HASHED_PATH_KEYS, label=label)
    path = _path(value["path"], label=f"{label}.path")
    digest = _text(value["sha256"], label=f"{label}.sha256")
    if _HEX_RE.fullmatch(digest) is None:
        _fail(f"{label}.sha256 is not canonical")
    return path, digest


@dataclass
class H11RootAuthorizerSession:
    authorization: RetainedH11RootJsonSource
    authority: H11RootRetainedAuthority
    permit_ready: RetainedH11RootJsonSource
    run_armed: RetainedH11RootJsonSource
    authorization_manifest: dict[str, Any]
    ready_receipt: dict[str, Any]
    armed_receipt: dict[str, Any]

    @classmethod
    def open(
        cls,
        authorization_path: Path,
        *,
        require_root: bool = True,
    ) -> "H11RootAuthorizerSession":
        _require_root(require_root)
        authorization: RetainedH11RootJsonSource | None = None
        authority: H11RootRetainedAuthority | None = None
        permit_ready: RetainedH11RootJsonSource | None = None
        run_armed: RetainedH11RootJsonSource | None = None
        try:
            descriptor, plan, raw, source = _pin_h11_json_source(
                authorization_path,
                label="H11 authorization manifest",
                required_mode=0o444,
                require_root_owner=require_root,
            )
            authorization = RetainedH11RootJsonSource(
                descriptor,
                authorization_path,
                raw,
                source,
                "H11 authorization manifest",
            )
            _exact(plan, _H11_AUTHORIZATION_KEYS, label="H11 authorization manifest")
            if plan["schema"] != H11_AUTHORIZATION_SCHEMA:
                _fail("unexpected H11 authorization manifest schema")
            root = authorization_path.parents[3]
            scenario_root = root / "authority" / "harness" / "H11"
            if authorization_path != scenario_root / "AUTHORIZE-RELEASE.json":
                _fail("H11 authorization path differs from the exact root layout")
            if _path(plan["formal_root"], label="H11 formal_root") != root:
                _fail("H11 authorization formal root differs from its path authority")
            permit_path = _path(plan["permit_path"], label="H11 permit_path")
            if permit_path != scenario_root / "PERMIT.json":
                _fail("H11 authorization permit path differs from the exact layout")

            harness_path, harness_reference = _decode_h11_full_source_reference(
                plan["harness_manifest"],
                label="H11 harness_manifest",
                expected_mode="0444",
            )
            ready_path, ready_reference = _decode_h11_full_source_reference(
                plan["permit_ready"],
                label="H11 permit_ready",
                expected_mode="0444",
            )
            armed_path, armed_reference = _decode_h11_full_source_reference(
                plan["run_armed"],
                label="H11 run_armed",
                expected_mode="0600",
            )
            if harness_path != scenario_root / "MANIFEST.json":
                _fail("H11 harness manifest path differs from the exact layout")
            authority = H11RootRetainedAuthority.open(
                harness_path, require_root=require_root
            )
            permit_authority = authority.manifest["permit_authority"]
            authority_ready_path = _path(
                permit_authority["permit_ready_path"],
                label="H11 permit_authority.permit_ready_path",
            )
            if (
                ready_path != scenario_root / "PERMIT_READY.json"
                or ready_path != authority_ready_path
            ):
                _fail("H11 PERMIT_READY path differs from exact retained authority")
            if harness_reference != authority.manifest_source:
                _fail("H11 authorization harness reference differs from retained source")
            if authority.directories[0].reference.path != root:
                _fail("H11 retained authority formal root differs from authorization")
            if (
                armed_reference["uid"] != str(authority.fixture_uid)
                or armed_reference["gid"] != str(authority.fixture_gid)
            ):
                _fail("H11 run ARMED owner differs from retained fixture authority")
            manifest = _decode_canonical_object(
                authority.manifest_raw, label="retained H11 harness manifest"
            )

            acquisition_values = manifest["acquisitions"]
            if type(acquisition_values) is not list or len(acquisition_values) != 3:
                _fail("H11 acquisitions must be the exact three-role array")
            acquisitions: list[dict[str, Any]] = []
            seen_armed_paths: set[Path] = set()
            seen_fifo_paths: set[Path] = set()
            seen_fifo_identities: set[tuple[int, int]] = set()
            tree_by_path = {item.path: item for item in authority.validated_fifos}
            if len(tree_by_path) != len(authority.validated_fifos):
                _fail("H11 retained TREE FIFO inventory aliases one path")
            commit_paths = {item.reference.path for item in authority.commit_fifos}
            commit_identities = {
                (item.reference.device, item.reference.inode)
                for item in authority.commit_fifos
            }
            for index, (expected_role, value) in enumerate(
                zip(_H11_ACQUISITION_ROLES, acquisition_values)
            ):
                if type(value) is not dict:
                    _fail(f"H11 acquisitions[{index}] must be one exact object")
                _exact(
                    value,
                    {"role", "armed_receipt_path", "ready_fifo", "release_fifo"},
                    label=f"H11 acquisitions[{index}]",
                )
                role = _text(value["role"], label=f"H11 acquisitions[{index}].role")
                if role != expected_role:
                    _fail("H11 acquisition roles differ from the exact ordered tuple")
                armed_receipt_path = _path(
                    value["armed_receipt_path"],
                    label=f"H11 acquisitions[{index}].armed_receipt_path",
                )
                if armed_receipt_path in seen_armed_paths:
                    _fail("H11 acquisition ARMED paths alias")
                decoded = {
                    "role": role,
                    "armed_receipt_path": armed_receipt_path,
                }
                seen_armed_paths.add(armed_receipt_path)
                for fifo_key in ("ready_fifo", "release_fifo"):
                    fifo = value[fifo_key]
                    if type(fifo) is not dict:
                        _fail(f"H11 acquisition {fifo_key} must be one exact object")
                    _exact(
                        fifo,
                        {"path", "device", "inode"},
                        label=f"H11 acquisitions[{index}].{fifo_key}",
                    )
                    fifo_path = _path(
                        fifo["path"],
                        label=f"H11 acquisitions[{index}].{fifo_key}.path",
                    )
                    device = _uint(
                        fifo["device"],
                        label=f"H11 acquisitions[{index}].{fifo_key}.device",
                    )
                    inode = _uint(
                        fifo["inode"],
                        label=f"H11 acquisitions[{index}].{fifo_key}.inode",
                    )
                    tree_row = tree_by_path.get(fifo_path)
                    if (
                        tree_row is None
                        or tree_row.owner != "fixture"
                        or (tree_row.uid, tree_row.gid)
                        != (authority.fixture_uid, authority.fixture_gid)
                        or tree_row.mode != 0o600
                        or tree_row.acquisition_reference != fifo
                        or fifo_path in commit_paths
                        or (device, inode) in commit_identities
                        or fifo_path in seen_fifo_paths
                        or (device, inode) in seen_fifo_identities
                    ):
                        _fail(
                            "H11 acquisition FIFO differs from retained TREE authority"
                        )
                    decoded[fifo_key] = dict(fifo)
                    seen_fifo_paths.add(fifo_path)
                    seen_fifo_identities.add((device, inode))
                acquisitions.append(decoded)
            if len(seen_fifo_paths) != 6 or len(seen_fifo_identities) != 6:
                _fail("H11 acquisitions do not bind six distinct TREE FIFO rows")
            validated_fifo_paths = {
                item.path for item in authority.validated_fifos
            }
            if (
                len(authority.validated_fifos) != 8
                or len(validated_fifo_paths) != 8
                or validated_fifo_paths != seen_fifo_paths | commit_paths
            ):
                _fail(
                    "H11 TREE FIFO authority is not the exact six acquisitions "
                    "plus two commits"
                )
            run_main = acquisitions[0]
            if armed_path != run_main["armed_receipt_path"]:
                _fail("H11 authorization cannot select a different run ARMED path")

            static_values = manifest["static_roles"]
            if type(static_values) is not list or len(static_values) != 3:
                _fail("H11 static_roles must be the exact three-role array")
            closer_unit = _text(
                manifest["closer_unit"], label="H11 manifest closer_unit"
            )
            if _UNIT_RE.fullmatch(closer_unit) is None:
                _fail("H11 manifest closer_unit is not canonical")
            expected_static_roles = (
                (
                    "run-main",
                    manifest["run_unit"],
                    "adversary",
                    "h11-unbounded-hold",
                ),
                (
                    "exec-stop-post",
                    manifest["run_unit"],
                    "observer",
                    "exec-stop-post",
                ),
                ("closer", closer_unit, "observer", "closer"),
            )
            static_roles: list[dict[str, Any]] = []
            static_paths: set[Path] = set()
            for index, (expected_tuple, value) in enumerate(
                zip(expected_static_roles, static_values)
            ):
                if type(value) is not dict:
                    _fail(f"H11 static_roles[{index}] must be one exact object")
                _exact(
                    value,
                    _H11_STATIC_ROLE_KEYS,
                    label=f"H11 static_roles[{index}]",
                )
                role = _text(value["role"], label=f"H11 static_roles[{index}].role")
                unit = _text(value["unit"], label=f"H11 static_roles[{index}].unit")
                owner = _text(
                    value["owner"], label=f"H11 static_roles[{index}].owner"
                )
                mode = _text(value["mode"], label=f"H11 static_roles[{index}].mode")
                plan_path, plan_digest = _decode_h11_hashed_path(
                    value["plan"], label=f"H11 static_roles[{index}].plan"
                )
                program_path, program_digest = _decode_h11_hashed_path(
                    value["program"], label=f"H11 static_roles[{index}].program"
                )
                if (
                    (role, unit, owner, mode) != expected_tuple
                    or _UNIT_RE.fullmatch(unit) is None
                    or plan_path in static_paths
                    or program_path in static_paths
                    or plan_path == program_path
                ):
                    _fail("H11 static role tuple or path authority is invalid")
                static_paths.update((plan_path, program_path))
                static_roles.append(
                    {
                        "role": role,
                        "unit": unit,
                        "owner": owner,
                        "mode": mode,
                        "plan_path": plan_path,
                        "plan_sha256": plan_digest,
                        "program_path": program_path,
                        "program_sha256": program_digest,
                    }
                )
            run_static = static_roles[0]

            ready_descriptor, ready, ready_raw, ready_source = _pin_h11_json_source(
                ready_path,
                label="H11 PERMIT_READY",
                expected_reference=ready_reference,
                ownership_bound=True,
                required_mode=0o444,
                require_root_owner=require_root,
            )
            permit_ready = RetainedH11RootJsonSource(
                ready_descriptor,
                ready_path,
                ready_raw,
                ready_source,
                "H11 PERMIT_READY",
            )
            armed_descriptor, armed, armed_raw, armed_source = _pin_h11_json_source(
                armed_path,
                label="H11 run ARMED",
                expected_reference=armed_reference,
                ownership_bound=True,
                required_mode=0o600,
            )
            run_armed = RetainedH11RootJsonSource(
                armed_descriptor,
                armed_path,
                armed_raw,
                armed_source,
                "H11 run ARMED",
            )
            if (
                armed_source["uid"] != str(authority.fixture_uid)
                or armed_source["gid"] != str(authority.fixture_gid)
            ):
                _fail("H11 pinned run ARMED owner differs from fixture authority")

            _exact(ready, _H11_READY_KEYS, label="H11 PERMIT_READY")
            run_unit = _text(ready["run_unit"], label="H11 PERMIT_READY.run_unit")
            boot_id = _text(ready["boot_id"], label="H11 PERMIT_READY.boot_id")
            invocation_id = _text(
                ready["invocation_id"], label="H11 PERMIT_READY.invocation_id"
            )
            if (
                ready["schema"] != H11_PERMIT_READY_SCHEMA
                or ready["scenario"] != "H11"
                or ready["phase"] != "h11-permit-ready"
                or run_unit != manifest["run_unit"]
                or _UNIT_RE.fullmatch(run_unit) is None
                or _BOOT_RE.fullmatch(boot_id) is None
                or _INVOCATION_RE.fullmatch(invocation_id) is None
                or ready["harness_manifest"] != harness_reference
                or ready["run_armed"] != armed_reference
                or ready["permit_authority"] != permit_authority
                or type(ready["present_outputs"]) is not list
                or type(ready["absent_paths"]) is not list
            ):
                _fail("H11 PERMIT_READY tuple or source cross-binding is invalid")

            _exact(armed, _H11_ADVERSARY_ARMED_KEYS, label="H11 run ARMED")
            actor = armed["actor"]
            if type(actor) is not dict:
                _fail("H11 run ARMED actor must be one exact object")
            _exact(actor, _H11_ADVERSARY_ACTOR_KEYS, label="H11 run ARMED actor")
            unified_cgroup = _text(
                actor["unified_cgroup"], label="H11 run ARMED actor.unified_cgroup"
            )
            plan_path = _path(armed["plan_path"], label="H11 run ARMED.plan_path")
            request_path = _path(
                armed["request_path"], label="H11 run ARMED.request_path"
            )
            receipt_path = _path(
                armed["receipt_path"], label="H11 run ARMED.receipt_path"
            )
            plan_sha256 = _text(
                armed["plan_sha256"], label="H11 run ARMED.plan_sha256"
            )
            request_sha256 = _text(
                armed["request_sha256"], label="H11 run ARMED.request_sha256"
            )
            program = armed["program"]
            if type(program) is not dict:
                _fail("H11 run ARMED program must be one exact object")
            _exact(program, _H11_ARMED_PROGRAM_KEYS, label="H11 run ARMED program")
            program_path = _path(
                program["path"], label="H11 run ARMED program.path"
            )
            program_sha256 = _text(
                program["sha256"], label="H11 run ARMED program.sha256"
            )
            program_identity = program["identity"]
            if type(program_identity) is not dict:
                _fail("H11 run ARMED program.identity must be one exact object")
            _exact(
                program_identity,
                _H11_ARMED_PROGRAM_IDENTITY_KEYS,
                label="H11 run ARMED program.identity",
            )
            if any(
                type(program_identity[key]) is not int
                or program_identity[key] <= 0
                for key in ("device", "inode")
            ) or (
                type(program_identity["mode"]) is not int
                or program_identity["mode"] != 0o444
            ):
                _fail("H11 run ARMED program identity is not canonical")
            digests = (
                plan_sha256,
                request_sha256,
                program_sha256,
                _text(armed["ready_sha256"], label="H11 run ARMED.ready_sha256"),
                _text(
                    armed["release_sha256"],
                    label="H11 run ARMED.release_sha256",
                ),
            )
            if any(_HEX_RE.fullmatch(digest) is None for digest in digests):
                _fail("H11 run ARMED carries a noncanonical SHA-256 digest")
            if (
                armed["schema"]
                != "scion.generic_backend.systemd_adversary_armed.v1"
                or armed["scenario"] != "h11-unbounded-hold"
                or armed["unit"] != run_unit
                or actor["boot_id"] != boot_id
                or actor["invocation_id"] != invocation_id
                or type(actor["pid"]) is not int
                or actor["pid"] <= 0
                or type(actor["starttime"]) is not int
                or actor["starttime"] <= 0
                or type(actor["session_id"]) is not int
                or actor["session_id"] <= 0
                or not unified_cgroup.startswith("/")
                or unified_cgroup == "/"
                or "//" in unified_cgroup
                or any(
                    part in {"", ".", ".."}
                    for part in unified_cgroup.split("/")[1:]
                )
                or actor["proc_cgroup_raw"] != f"0::{unified_cgroup}\n"
                or actor["stop_selector_environment"] != {}
                or armed["ready_fifo"] != run_main["ready_fifo"]
                or armed["release_fifo"] != run_main["release_fifo"]
                or plan_path != run_static["plan_path"]
                or plan_sha256 != run_static["plan_sha256"]
                or program_path != run_static["program_path"]
                or program_sha256 != run_static["program_sha256"]
                or armed["ready_sha256"]
                != hashlib.sha256(H11_READY_BYTES).hexdigest()
                or armed["release_sha256"]
                != hashlib.sha256(H11_RELEASE_BYTES).hexdigest()
            ):
                _fail("H11 run ARMED tuple or FIFO authority is invalid")

            path_authorities: list[tuple[str, Path]] = [
                *(
                    (
                        f"output:{item.role}",
                        item.path,
                    )
                    for index, value in enumerate(manifest["outputs"])
                    for item in (
                        H11RootRolePath.decode(
                            value, label=f"H11 manifest outputs[{index}]"
                        ),
                    )
                ),
                ("frozen-root", root / "frozen"),
                *(
                    (f"transaction:{role}", path)
                    for (role, _leaf), path in zip(
                        _H11_TRANSACTION_LAYOUT,
                        authority._transaction_paths(permit_authority),
                    )
                ),
                *(
                    (f"directory:{item.reference.role}", item.reference.path)
                    for item in authority.directories
                ),
                ("source:harness-manifest", authority.manifest_path),
                *(
                    (f"source:{item.label}", item.path)
                    for item in authority.bound_sources
                ),
                *(
                    (f"TREE-FIFO:{item.role}", item.path)
                    for item in authority.validated_fifos
                ),
                *(
                    (f"ARMED:{item['role']}", item["armed_receipt_path"])
                    for item in acquisitions
                ),
                *(
                    (f"static-plan:{item['role']}", item["plan_path"])
                    for item in static_roles
                ),
                *(
                    (f"static-program:{item['role']}", item["program_path"])
                    for item in static_roles
                ),
                ("ARMED-request:run-main", request_path),
                ("ARMED-receipt:run-main", receipt_path),
            ]
            seen_paths: dict[Path, str] = {}
            for label, path in path_authorities:
                previous = seen_paths.get(path)
                if previous is not None:
                    _fail(f"H11 authorizer path authority aliases {previous} and {label}")
                seen_paths[path] = label

            regular_sources = (
                ("H11 authorization manifest", source),
                ("H11 harness manifest", authority.manifest_source),
                ("H11 PERMIT_READY", ready_source),
                ("H11 run ARMED", armed_source),
                *((item.label, item.source) for item in authority.bound_sources),
            )
            seen_source_inodes: dict[tuple[str, str], str] = {}
            for label, retained_source in regular_sources:
                identity = (
                    retained_source["device"],
                    retained_source["inode"],
                )
                previous = seen_source_inodes.get(identity)
                if previous is not None:
                    _fail(
                        f"H11 authorizer regular source aliases {previous} and {label}"
                    )
                seen_source_inodes[identity] = label

            result = cls(
                authorization,
                authority,
                permit_ready,
                run_armed,
                plan,
                ready,
                armed,
            )
            result.revalidate()
            return result
        except BaseException as exc:
            _close_h11_ownership(
                tuple(
                    owner
                    for owner in (
                        run_armed,
                        permit_ready,
                        authority,
                        authorization,
                    )
                    if owner is not None
                ),
                active_error=exc,
            )
            raise

    def revalidate(self) -> None:
        self.authorization.revalidate()
        self.authority.revalidate(require_root=self.authority.require_root)
        self.permit_ready.revalidate()
        self.run_armed.revalidate()

    def close(self) -> None:
        _close_h11_ownership(
            (
                self.run_armed,
                self.permit_ready,
                self.authority,
                self.authorization,
            )
        )


@dataclass
class RetainedH11RootPresentOutput:
    role: str
    path: Path
    parent: RetainedH11RootDirectory
    descriptor: int
    raw: bytes
    reference_items: tuple[tuple[str, str], ...]
    require_root: bool

    @property
    def reference(self) -> dict[str, str]:
        return dict(self.reference_items)

    @classmethod
    def pin(
        cls,
        value: Any,
        *,
        expected: H11RootRolePath,
        parent: RetainedH11RootDirectory,
        require_root: bool,
    ) -> "RetainedH11RootPresentOutput":
        label = f"H11 present output {expected.role}"
        if type(value) is not dict:
            _fail(f"{label} must be one exact full reference")
        _exact(
            value,
            {
                "role",
                "path",
                "sha256",
                "device",
                "inode",
                "mode",
                "uid",
                "gid",
            },
            label=label,
        )
        role = _text(value["role"], label=f"{label}.role")
        path = _path(value["path"], label=f"{label}.path")
        digest = _text(value["sha256"], label=f"{label}.sha256")
        if _HEX_RE.fullmatch(digest) is None:
            _fail(f"{label}.sha256 is not canonical")
        _uint(value["device"], label=f"{label}.device")
        _uint(value["inode"], label=f"{label}.inode")
        _uint(value["uid"], label=f"{label}.uid")
        _uint(value["gid"], label=f"{label}.gid")
        if (
            role != expected.role
            or path != expected.path
            or path.parent != parent.reference.path
            or value["mode"] != "0444"
        ):
            _fail(f"{label} role/path/mode differs from the derived authority")
        expected_owner = (
            (0, 0)
            if require_root
            else (parent.reference.uid, parent.reference.gid)
        )
        if (value["uid"], value["gid"]) != tuple(
            str(item) for item in expected_owner
        ):
            _fail(f"{label} owner differs from retained root authority")

        parent.revalidate(require_root=require_root)
        descriptor = -1
        try:
            before = os.stat(
                path.name,
                dir_fd=parent.descriptor,
                follow_symlinks=False,
            )
            descriptor = os.open(
                path.name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent.descriptor,
            )
            opened = os.fstat(descriptor)
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            raw = b"".join(chunks)
            after = os.fstat(descriptor)
            current = os.stat(
                path.name,
                dir_fd=parent.descriptor,
                follow_symlinks=False,
            )
            actual = {
                "role": role,
                "path": str(path),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "device": str(after.st_dev),
                "inode": str(after.st_ino),
                "mode": format(stat.S_IMODE(after.st_mode), "04o"),
                "uid": str(after.st_uid),
                "gid": str(after.st_gid),
            }
            observations = (before, opened, after, current)
            if (
                any(not stat.S_ISREG(info.st_mode) for info in observations)
                or any(
                    (info.st_dev, info.st_ino)
                    != (after.st_dev, after.st_ino)
                    for info in observations
                )
                or any(
                    stat.S_IMODE(info.st_mode) != 0o444
                    for info in observations
                )
                or any(
                    (info.st_uid, info.st_gid) != expected_owner
                    for info in observations
                )
                or after.st_size != len(raw)
                or after.st_mtime_ns != opened.st_mtime_ns
                or actual != value
            ):
                _fail(f"{label} bytes/identity/mode/owner drifted while pinning")
            os.lseek(descriptor, 0, os.SEEK_SET)
            return cls(
                role,
                path,
                parent,
                descriptor,
                raw,
                tuple((key, value[key]) for key in sorted(value)),
                require_root,
            )
        except InstallerError as exc:
            closing_descriptor = descriptor
            descriptor = -1
            _close_h11_ownership(
                (),
                active_error=exc,
                initial_descriptor=closing_descriptor,
            )
            raise
        except OSError as exc:
            error = InstallerError(f"cannot pin {label}")
            closing_descriptor = descriptor
            descriptor = -1
            _close_h11_ownership(
                (),
                active_error=error,
                initial_descriptor=closing_descriptor,
            )
            raise error from exc
        except BaseException as exc:
            closing_descriptor = descriptor
            descriptor = -1
            _close_h11_ownership(
                (),
                active_error=exc,
                initial_descriptor=closing_descriptor,
            )
            raise

    def revalidate(self) -> None:
        if self.descriptor < 0:
            _fail(f"H11 present output {self.role} closed before last use")
        self.parent.revalidate(require_root=self.require_root)
        try:
            opened = os.fstat(self.descriptor)
            os.lseek(self.descriptor, 0, os.SEEK_SET)
            chunks: list[bytes] = []
            while True:
                chunk = os.read(self.descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            reread = b"".join(chunks)
            os.lseek(self.descriptor, 0, os.SEEK_SET)
            current = os.stat(
                self.path.name,
                dir_fd=self.parent.descriptor,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise InstallerError(
                f"cannot revalidate H11 present output {self.role}"
            ) from exc
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
            or actual != self.reference
            or not stat.S_ISREG(current.st_mode)
            or (str(current.st_dev), str(current.st_ino))
            != (self.reference["device"], self.reference["inode"])
            or format(stat.S_IMODE(current.st_mode), "04o") != "0444"
            or (str(current.st_uid), str(current.st_gid))
            != (self.reference["uid"], self.reference["gid"])
        ):
            _fail(f"retained H11 present output {self.role} drifted")

    def close(self) -> None:
        if self.descriptor >= 0:
            descriptor = self.descriptor
            self.descriptor = -1
            os.close(descriptor)


def _bind_h11_authorizer_transaction_sources(
    session: H11RootAuthorizerSession,
    transaction_state: tuple[H11RootTransactionState, ...],
) -> None:
    if tuple(item.role for item in transaction_state) != tuple(
        role for role, _leaf in _H11_TRANSACTION_LAYOUT
    ):
        _fail("H11 authorizer transaction rows are not the exact ordered layout")
    scenario = session.authority.directories[3]
    by_role = {item.role: item for item in transaction_state}
    for role, leaf, source in (
        ("authorization", "AUTHORIZE-RELEASE.json", session.authorization),
        ("permit-ready", "PERMIT_READY.json", session.permit_ready),
    ):
        row = by_role[role]
        if row.state != "present" or row.path != source.path:
            _fail(f"H11 {role} transaction row differs from its retained source")
        try:
            current = os.stat(
                leaf,
                dir_fd=scenario.descriptor,
                follow_symlinks=False,
            )
            opened = os.fstat(source.descriptor)
        except OSError as exc:
            raise InstallerError(
                f"cannot bind H11 {role} transaction source"
            ) from exc
        expected = (source.source["device"], source.source["inode"])
        if (
            not stat.S_ISREG(current.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or (str(current.st_dev), str(current.st_ino)) != expected
            or (str(opened.st_dev), str(opened.st_ino)) != expected
            or format(stat.S_IMODE(current.st_mode), "04o")
            != source.source["mode"]
            or (str(current.st_uid), str(current.st_gid))
            != (source.source["uid"], source.source["gid"])
        ):
            _fail(f"H11 {role} leaf identity differs from its retained source")


@dataclass
class H11RootAuthorizerReadyClosure:
    session: H11RootAuthorizerSession
    ready_commit: H11RootCommitReceipt
    partition: H11RootClosedPartition
    present_sources: tuple[RetainedH11RootPresentOutput, ...]
    transaction_state: tuple[H11RootTransactionState, ...]
    present_outputs_sha256: str
    future_absence_sha256: str
    poisoned: bool = False
    closed: bool = False

    @property
    def present_outputs(self) -> list[dict[str, str]]:
        return [dict(item.reference) for item in self.present_sources]

    @property
    def future_absence_inventory(self) -> list[dict[str, str]]:
        return [
            item.reference for item in self.partition.future_absence_inventory
        ]

    @classmethod
    def consume(
        cls,
        session: H11RootAuthorizerSession,
    ) -> "H11RootAuthorizerReadyClosure":
        present_sources: list[RetainedH11RootPresentOutput] = []
        result: H11RootAuthorizerReadyClosure | None = None
        try:
            session.revalidate()
            ready_fifos = tuple(
                item
                for item in session.authority.commit_fifos
                if item.role == "h11-ready-commit"
            )
            if len(ready_fifos) != 1:
                _fail("H11 root authority lacks exactly one READY commit FIFO")
            ready_commit = ready_fifos[0].read_ready_commit(
                require_root=session.authority.require_root
            )
            session.revalidate()

            partition = session.authority.derive_closed_partition()
            ready_present = session.ready_receipt["present_outputs"]
            ready_absent = session.ready_receipt["absent_paths"]
            if type(ready_present) is not list or type(ready_absent) is not list:
                _fail("H11 READY partition must contain two exact arrays")
            if len(ready_present) != 2 or len(ready_absent) != 11:
                _fail("H11 READY partition is not the exact 2-present/11-future split")

            declared_present_role_paths: list[H11RootRolePath] = []
            for index, value in enumerate(ready_present):
                if type(value) is not dict:
                    _fail(f"H11 READY present_outputs[{index}] is not an object")
                declared_present_role_paths.append(
                    H11RootRolePath.decode(
                        {"role": value.get("role"), "path": value.get("path")},
                        label=f"H11 READY present_outputs[{index}] role/path",
                    )
                )
            declared_absent = tuple(
                H11RootRolePath.decode(
                    value,
                    label=f"H11 READY absent_paths[{index}]",
                )
                for index, value in enumerate(ready_absent)
            )
            if tuple(declared_present_role_paths) != partition.present_prerequisites:
                _fail("H11 READY present_outputs differ from the derived partition")
            if declared_absent != partition.future_absence_inventory:
                _fail("H11 READY absent_paths differ from the derived partition")

            input_parent = session.authority.directories[4]
            receipt_parent = session.authority.directories[5]
            for value, expected in zip(
                ready_present, partition.present_prerequisites
            ):
                if expected.path.parent == input_parent.reference.path:
                    parent = input_parent
                elif expected.path.parent == receipt_parent.reference.path:
                    parent = receipt_parent
                else:
                    _fail("H11 present output is outside both retained output roots")
                present_sources.append(
                    RetainedH11RootPresentOutput.pin(
                        value,
                        expected=expected,
                        parent=parent,
                        require_root=session.authority.require_root,
                    )
                )

            transaction_state = session.authority.validate_transaction_phase(
                "authorizer-input"
            )
            _bind_h11_authorizer_transaction_sources(session, transaction_state)

            occupied_identities = {
                (
                    session.authorization.source["device"],
                    session.authorization.source["inode"],
                ),
                (
                    session.authority.manifest_source["device"],
                    session.authority.manifest_source["inode"],
                ),
                (
                    session.permit_ready.source["device"],
                    session.permit_ready.source["inode"],
                ),
                (
                    session.run_armed.source["device"],
                    session.run_armed.source["inode"],
                ),
                *(
                    (item.source["device"], item.source["inode"])
                    for item in session.authority.bound_sources
                ),
                *(
                    (str(item.reference.device), str(item.reference.inode))
                    for item in session.authority.directories
                ),
                *(
                    (str(item.reference.device), str(item.reference.inode))
                    for item in session.authority.commit_fifos
                ),
                *(
                    (str(item.device), str(item.inode))
                    for item in session.authority.validated_fifos
                ),
            }
            present_identities = [
                (item.reference["device"], item.reference["inode"])
                for item in present_sources
            ]
            if (
                len(set(present_identities)) != 2
                or any(
                    identity in occupied_identities
                    for identity in present_identities
                )
            ):
                _fail("H11 present output identities alias retained authority")

            present_array = [dict(item.reference) for item in present_sources]
            future_array = [
                item.reference for item in partition.future_absence_inventory
            ]
            result = cls(
                session,
                ready_commit,
                partition,
                tuple(present_sources),
                transaction_state,
                hashlib.sha256(_canonical(present_array)).hexdigest(),
                hashlib.sha256(_canonical(future_array)).hexdigest(),
            )
            result.revalidate()
            return result
        except BaseException as exc:
            if result is not None:
                result.poisoned = True
                owners: tuple[Any, ...] = (result,)
            else:
                owners = (*reversed(present_sources), session)
            _close_h11_ownership(owners, active_error=exc)
            raise

    def _revalidate_retained_common(self) -> None:
        if self.poisoned or self.closed:
            _fail("H11 READY closure is poisoned or closed before last use")
        self.session.revalidate()
        partition = self.session.authority.derive_closed_partition()
        if partition != self.partition:
            _fail("H11 retained partition drifted after READY commit")
        for source in self.present_sources:
            source.revalidate()
        if (
            hashlib.sha256(_canonical(self.present_outputs)).hexdigest()
            != self.present_outputs_sha256
            or hashlib.sha256(
                _canonical(self.future_absence_inventory)
            ).hexdigest()
            != self.future_absence_sha256
        ):
            _fail("H11 READY closure canonical inventory digest drifted")

    def _validate_exact_transaction_phase(
        self, phase: str
    ) -> tuple[H11RootTransactionState, ...]:
        if phase not in {"authorizer-input", "permit-committed"}:
            _fail("H11 C2 transaction phase is outside the fixed literal pair")
        transaction_state = self.session.authority.validate_transaction_phase(
            phase
        )
        _bind_h11_authorizer_transaction_sources(self.session, transaction_state)
        return transaction_state

    def revalidate(self) -> None:
        self._revalidate_retained_common()
        transaction_state = self._validate_exact_transaction_phase(
            "authorizer-input"
        )
        if transaction_state != self.transaction_state:
            _fail("H11 authorizer-input transaction state drifted")

    def poison(self) -> None:
        self.poisoned = True
        self.close()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        _close_h11_ownership(
            (*reversed(self.present_sources), self.session)
        )


@dataclass
class RetainedH11RootPublication:
    parent: RetainedH11RootDirectory
    final_name: str
    descriptor: int
    raw: bytes
    reference: dict[str, str]
    require_root: bool

    def revalidate(self) -> None:
        if self.descriptor < 0:
            _fail("retained H11 publication descriptor closed before last use")
        self.parent.revalidate(require_root=self.require_root)
        try:
            opened = os.fstat(self.descriptor)
            current = os.stat(
                self.final_name,
                dir_fd=self.parent.descriptor,
                follow_symlinks=False,
            )
            os.lseek(self.descriptor, 0, os.SEEK_SET)
            chunks: list[bytes] = []
            while True:
                chunk = os.read(self.descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            reread = b"".join(chunks)
            os.lseek(self.descriptor, 0, os.SEEK_SET)
        except OSError as exc:
            raise InstallerError("cannot revalidate retained H11 publication") from exc
        actual_reference = {
            "path": str(self.parent.reference.path / self.final_name),
            "sha256": hashlib.sha256(reread).hexdigest(),
            "device": str(opened.st_dev),
            "inode": str(opened.st_ino),
            "mode": format(stat.S_IMODE(opened.st_mode), "04o"),
            "uid": str(opened.st_uid),
            "gid": str(opened.st_gid),
        }
        if (
            reread != self.raw
            or actual_reference != self.reference
            or not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
            or stat.S_IMODE(current.st_mode) != 0o444
            or (current.st_uid, current.st_gid) != (opened.st_uid, opened.st_gid)
        ):
            _fail("retained H11 publication drifted")

    def close(self) -> None:
        if self.descriptor >= 0:
            descriptor = self.descriptor
            self.descriptor = -1
            os.close(descriptor)


@dataclass(frozen=True, slots=True)
class H11RootNamedStagingPlan:
    parent: RetainedH11RootDirectory
    staging_name: str
    final_name: str
    raw: bytes
    expected_owner: tuple[int, int]
    require_root: bool
    test_failure: str | None


def _prepare_h11_named_staging(
    parent: RetainedH11RootDirectory,
    staging_name: str,
    final_name: str,
    payload: dict[str, Any],
    *,
    require_root: bool,
    _test_failure: str | None = None,
) -> H11RootNamedStagingPlan:
    if _test_failure is not None:
        if require_root:
            _fail("privileged H11 publication forbids test failure injection")
        if (
            type(_test_failure) is not str
            or _test_failure not in _H11_PUBLICATION_TEST_FAILURES
        ):
            _fail("H11 publication test failure is outside the closed enum")
    if (
        type(staging_name) is not str
        or type(final_name) is not str
        or _H11_PUBLICATION_PAIRS.get(staging_name) != final_name
    ):
        _fail("H11 publication leaf pair is outside the exact transaction layout")
    if type(payload) is not dict:
        _fail("H11 publication payload must be one exact object")
    if parent.reference.role != "scenario-root":
        _fail("H11 publication parent must be the retained scenario-root")
    parent.revalidate(require_root=require_root)
    return H11RootNamedStagingPlan(
        parent,
        staging_name,
        final_name,
        _canonical(payload),
        (
            (0, 0)
            if require_root
            else (parent.reference.uid, parent.reference.gid)
        ),
        require_root,
        _test_failure,
    )


def _open_h11_named_staging(plan: H11RootNamedStagingPlan) -> int:
    return os.open(
        plan.staging_name,
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | os.O_CLOEXEC,
        0o444,
        dir_fd=plan.parent.descriptor,
    )


def _complete_h11_named_staging(
    plan: H11RootNamedStagingPlan,
    descriptor: int,
) -> RetainedH11RootPublication:
    parent = plan.parent
    try:
        view = memoryview(plan.raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                _fail("H11 staged publication write made no progress")
            view = view[written:]
        os.fchmod(descriptor, 0o444)
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        reread = b"".join(chunks)
        os.lseek(descriptor, 0, os.SEEK_SET)
        opened = os.fstat(descriptor)
        if (
            reread != plan.raw
            or opened.st_size != len(plan.raw)
            or not stat.S_ISREG(opened.st_mode)
            or stat.S_IMODE(opened.st_mode) != 0o444
            or (opened.st_uid, opened.st_gid) != plan.expected_owner
        ):
            _fail("H11 staged publication readback or metadata is invalid")
        os.fsync(descriptor)
        if plan.test_failure == "pre-rename":
            _fail("injected H11 publication failure before rename")

        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        ctypes.set_errno(0)
        if (
            renameat2(
                parent.descriptor,
                plan.staging_name.encode("ascii"),
                parent.descriptor,
                plan.final_name.encode("ascii"),
                1,
            )
            != 0
        ):
            error = ctypes.get_errno()
            raise InstallerError(
                f"cannot publish no-replace H11 transaction: {os.strerror(error)}"
            )
        os.fsync(parent.descriptor)
        final_info = os.stat(
            plan.final_name,
            dir_fd=parent.descriptor,
            follow_symlinks=False,
        )
        retained_info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(final_info.st_mode)
            or (final_info.st_dev, final_info.st_ino)
            != (retained_info.st_dev, retained_info.st_ino)
            or stat.S_IMODE(final_info.st_mode) != 0o444
            or (final_info.st_uid, final_info.st_gid) != plan.expected_owner
        ):
            _fail("H11 publication final name differs from its retained inode")
        reference = {
            "path": str(parent.reference.path / plan.final_name),
            "sha256": hashlib.sha256(plan.raw).hexdigest(),
            "device": str(retained_info.st_dev),
            "inode": str(retained_info.st_ino),
            "mode": "0444",
            "uid": str(retained_info.st_uid),
            "gid": str(retained_info.st_gid),
        }
        result = RetainedH11RootPublication(
            parent,
            plan.final_name,
            descriptor,
            plan.raw,
            reference,
            plan.require_root,
        )
        result.revalidate()
        return result
    except BaseException as exc:
        closing_descriptor = descriptor
        descriptor = -1
        _close_h11_ownership(
            (),
            active_error=exc,
            initial_descriptor=closing_descriptor,
        )
        raise


def _publish_h11_named_staging(
    parent: RetainedH11RootDirectory,
    staging_name: str,
    final_name: str,
    payload: dict[str, Any],
    *,
    require_root: bool,
    _test_failure: str | None = None,
) -> RetainedH11RootPublication:
    plan = _prepare_h11_named_staging(
        parent,
        staging_name,
        final_name,
        payload,
        require_root=require_root,
        _test_failure=_test_failure,
    )
    descriptor = _open_h11_named_staging(plan)
    return _complete_h11_named_staging(plan, descriptor)


@dataclass(frozen=True, slots=True)
class H11RootPrePermitBarrier:
    directory_chain: tuple[H11RootDirectoryReference, ...]
    present_outputs_sha256: str
    future_absence_sha256: str
    transaction_state: tuple[H11RootTransactionState, ...]
    future_absence_inventory: tuple[H11RootRolePath, ...]

    @classmethod
    def capture(
        cls,
        closure: H11RootAuthorizerReadyClosure,
        plan: H11RootNamedStagingPlan,
    ) -> "H11RootPrePermitBarrier":
        if (
            plan.parent is not closure.session.authority.directories[3]
            or plan.staging_name != "PERMIT.pending"
            or plan.final_name != "PERMIT.json"
            or plan.test_failure is not None
        ):
            _fail("H11 pre-permit barrier plan is not the exact permit transaction")
        closure.revalidate()
        authority = closure.session.authority
        if len(closure.partition.future_absence_inventory) != 11:
            _fail("H11 pre-permit barrier lacks the exact future inventory")
        formal_parent = authority.directories[0]
        input_parent = authority.directories[4]
        receipt_parent = authority.directories[5]
        for item in closure.partition.future_absence_inventory:
            if item.role == "frozen-root":
                parent = formal_parent
            elif item.path.parent == input_parent.reference.path:
                parent = input_parent
            elif item.path.parent == receipt_parent.reference.path:
                parent = receipt_parent
            else:
                _fail("H11 future absence is outside its retained parent")
            try:
                os.stat(
                    item.path.name,
                    dir_fd=parent.descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise InstallerError(
                    f"cannot prove H11 future absence {item.role}"
                ) from exc
            else:
                _fail(f"H11 future output {item.role} exists before permit")
        result = cls(
            tuple(item.reference for item in authority.directories),
            closure.present_outputs_sha256,
            closure.future_absence_sha256,
            closure.transaction_state,
            closure.partition.future_absence_inventory,
        )
        try:
            os.stat(
                "PERMIT.pending",
                dir_fd=plan.parent.descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return result
        except OSError as exc:
            raise InstallerError(
                "cannot prove final H11 permit staging absence"
            ) from exc
        _fail("H11 permit staging exists at the final pre-publication barrier")


@dataclass
class H11RootAuthorizedPermit:
    closure: H11RootAuthorizerReadyClosure
    barrier: H11RootPrePermitBarrier
    publication: RetainedH11RootPublication
    transaction_state: tuple[H11RootTransactionState, ...]
    closed: bool = False
    poisoned: bool = False
    commit_started: bool = False

    @classmethod
    def publish(
        cls,
        closure: H11RootAuthorizerReadyClosure,
    ) -> "H11RootAuthorizedPermit":
        publication: RetainedH11RootPublication | None = None
        try:
            session = closure.session
            retained_ready = _decode_canonical_object(
                session.permit_ready.raw,
                label="retained H11 PERMIT_READY for permit publication",
            )
            payload = {
                "schema": H11_PERMIT_SCHEMA,
                "scenario": "H11",
                "run_unit": retained_ready["run_unit"],
                "boot_id": retained_ready["boot_id"],
                "invocation_id": retained_ready["invocation_id"],
                "authorization_manifest": dict(session.authorization.source),
                "harness_manifest": dict(session.authority.manifest_source),
                "permit_ready": dict(session.permit_ready.source),
                "run_armed": dict(session.run_armed.source),
                "ready_commit": closure.ready_commit.reference,
                "present_outputs_sha256": closure.present_outputs_sha256,
                "future_absence_sha256": closure.future_absence_sha256,
                "phase": "operator-release-authorized",
            }
            plan = _prepare_h11_named_staging(
                session.authority.directories[3],
                "PERMIT.pending",
                "PERMIT.json",
                payload,
                require_root=session.authority.require_root,
            )
            expected_transaction_state = tuple(
                H11RootTransactionState(item.role, item.path, state)
                for item, state in zip(
                    closure.transaction_state,
                    _H11_TRANSACTION_PHASES["permit-committed"],
                )
            )
            barrier = H11RootPrePermitBarrier.capture(closure, plan)
            descriptor = _open_h11_named_staging(plan)
            publication = _complete_h11_named_staging(plan, descriptor)
            result = cls(
                closure,
                barrier,
                publication,
                expected_transaction_state,
            )
            result.revalidate()
            return result
        except BaseException as exc:
            closure.poisoned = True
            _close_h11_ownership(
                (
                    (publication, closure)
                    if publication is not None
                    else (closure,)
                ),
                active_error=exc,
            )
            raise

    def revalidate(self) -> None:
        try:
            if self.closed or self.poisoned:
                _fail("H11 authorized permit is poisoned or closed before last use")
            self.closure._revalidate_retained_common()
            transaction_state = self.closure._validate_exact_transaction_phase(
                "permit-committed"
            )
            if transaction_state != self.transaction_state:
                _fail("H11 permit-committed transaction state drifted")
            self.publication.revalidate()
        except BaseException as exc:
            self.poisoned = True
            _close_h11_ownership((self,), active_error=exc)
            raise

    def poison(self) -> None:
        self.poisoned = True
        self.close()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        _close_h11_ownership((self.publication, self.closure))


def _commit_h11_authorized_permit(
    permit: H11RootAuthorizedPermit,
) -> H11RootCommitReceipt:
    descriptor = -1
    try:
        if permit.closed or permit.poisoned or permit.commit_started:
            _fail("H11 authorized permit cannot begin another commit handoff")
        permit.commit_started = True
        permit.revalidate()
        matches = tuple(
            item
            for item in permit.closure.session.authority.commit_fifos
            if item.role == "h11-permit-commit"
        )
        if len(matches) != 1:
            _fail("H11 root authority lacks exactly one PERMIT commit FIFO")
        fifo = matches[0]
        receipt = H11RootCommitReceipt.permit_committed(
            fifo,
            H11_PERMIT_COMMITTED_BYTES,
        )
        descriptor = fifo.open_permit_commit_writer(
            require_root=permit.closure.session.authority.require_root,
        )
        permit.revalidate()
        written = os.write(descriptor, H11_PERMIT_COMMITTED_BYTES)
        if written != len(H11_PERMIT_COMMITTED_BYTES):
            _fail("H11 PERMIT commit FIFO write was incomplete")
        closing_descriptor = descriptor
        descriptor = -1
        os.close(closing_descriptor)
        permit.close()
        return receipt
    except BaseException as exc:
        closing_descriptor = descriptor
        descriptor = -1
        permit.poisoned = True
        _close_h11_ownership(
            (permit,),
            active_error=exc,
            initial_descriptor=closing_descriptor,
        )
        raise


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


def authorize_h11_release(
    manifest_path: Path,
    *,
    require_root: bool = True,
) -> dict[str, Any]:
    """Publish and commit the one external operator permit."""

    owner: (
        H11RootAuthorizerSession
        | H11RootAuthorizerReadyClosure
        | H11RootAuthorizedPermit
        | None
    ) = None
    try:
        owner = H11RootAuthorizerSession.open(
            manifest_path,
            require_root=require_root,
        )
        owner = H11RootAuthorizerReadyClosure.consume(owner)
        owner = H11RootAuthorizedPermit.publish(owner)
        receipt = _commit_h11_authorized_permit(owner)
        owner = None
        return receipt.reference
    finally:
        if owner is not None:
            owner.close()


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
