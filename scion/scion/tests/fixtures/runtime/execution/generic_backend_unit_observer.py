#!/usr/bin/env python3
"""Tests-only raw receipt observer for the formal systemd-255 matrix.

The observer is deliberately acquisition-free with respect to systemd.  A
root-owned fixture binds already-acquired raw property and journal files in one
strict canonical request.  This process copies those bytes, records its own
kernel-visible identity and cgroup topology, and atomically publishes one
no-replace receipt.  It never treats journal data as authority.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, NoReturn


REQUEST_SCHEMA = "scion.generic_backend.systemd_observer_request.v1"
RECEIPT_SCHEMA = "scion.generic_backend.systemd_observer_receipt.v1"
PLAN_SCHEMA = "scion.generic_backend.systemd_observer_plan.v1"
ARMED_RECEIPT_SCHEMA = "scion.generic_backend.systemd_observer_armed.v1"
SOURCE_SELECTOR_SCHEMA = "scion.generic_backend.systemd_source_selector.v1"
RAW_QUERY_SCHEMA = "scion.generic_backend.systemd_raw_query.v1"
READY_BYTES = b"SCION_GENERIC_BACKEND_READY_V1\n"
RELEASE_BYTES = b"SCION_GENERIC_BACKEND_RELEASE_V1\n"

_UNIT_INTERFACE = "org.freedesktop.systemd1.Unit"
_SERVICE_INTERFACE = "org.freedesktop.systemd1.Service"
_SYSTEMD_PROPERTY_SIGNATURES = (
    (_UNIT_INTERFACE, "Id", "s"),
    (_UNIT_INTERFACE, "InvocationID", "ay"),
    (_UNIT_INTERFACE, "LoadState", "s"),
    (_UNIT_INTERFACE, "ActiveState", "s"),
    (_UNIT_INTERFACE, "SubState", "s"),
    (_UNIT_INTERFACE, "After", "as"),
    (_UNIT_INTERFACE, "CollectMode", "s"),
    (_UNIT_INTERFACE, "FragmentPath", "s"),
    (_UNIT_INTERFACE, "NeedDaemonReload", "b"),
    (_UNIT_INTERFACE, "OnSuccess", "as"),
    (_UNIT_INTERFACE, "OnFailure", "as"),
    (_SERVICE_INTERFACE, "ControlGroup", "s"),
    (_SERVICE_INTERFACE, "Delegate", "b"),
    (_SERVICE_INTERFACE, "DelegateControllers", "as"),
    (_SERVICE_INTERFACE, "DelegateSubgroup", "s"),
    (_SERVICE_INTERFACE, "ExecMainCode", "i"),
    (_SERVICE_INTERFACE, "ExecMainStatus", "i"),
    (_SERVICE_INTERFACE, "ExecStopPost", "a(sasbttttuii)"),
    (_SERVICE_INTERFACE, "Group", "s"),
    (_SERVICE_INTERFACE, "KillMode", "s"),
    (_SERVICE_INTERFACE, "MainPID", "u"),
    (_SERVICE_INTERFACE, "Restart", "s"),
    (_SERVICE_INTERFACE, "Result", "s"),
    (_SERVICE_INTERFACE, "TimeoutStartUSec", "t"),
    (_SERVICE_INTERFACE, "TimeoutStopUSec", "t"),
    (_SERVICE_INTERFACE, "User", "s"),
)
_RAW_QUERY_KEYS = frozenset(
    {
        "schema",
        "boot_id",
        "unit",
        "object_path",
        "manager_owner",
        "invocation_id",
        "properties",
        "normalization",
    }
)
_RAW_PROPERTY_KEYS = frozenset(
    {
        "destination_owner",
        "object_path",
        "interface",
        "property",
        "variant_signature",
        "value",
    }
)

_MODES = frozenset({"run-main", "exec-stop-post", "closer"})
_INPUT_KINDS = frozenset(
    {"systemd-properties-authority", "journal-corroboration"}
)
_QUERY_OWNERS = frozenset(
    {"system-manager-dbus", "invocation-filtered-journal-export"}
)
_LABEL_RE = re.compile(r"[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*\Z")
_UNIT_RE = re.compile(r"[A-Za-z0-9:_.@-]+\.service\Z")
_INVOCATION_RE = re.compile(r"[0-9a-f]{32}\Z")
_BOOT_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_TOKEN_RE = re.compile(r"[A-Za-z0-9_.+@:-]+\Z")
_UINT_RE = re.compile(r"0|[1-9][0-9]*\Z")
_INT_RE = re.compile(r"0|-?[1-9][0-9]*\Z")
_DBUS_OWNER_RE = re.compile(r":[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+\Z")
_DBUS_OBJECT_RE = re.compile(r"/(?:[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*)?\Z")
_REQUEST_KEYS = frozenset(
    {
        "schema",
        "mode",
        "output_path",
        "unit",
        "expected_invocation_id",
        "source_unit",
        "source_invocation_id",
        "cgroup_roots",
        "property_inputs",
    }
)
_PLAN_KEYS = frozenset(
    {
        "schema",
        "mode",
        "program_path",
        "program_sha256",
        "request_path",
        "output_path",
        "unit",
        "source_selector_path",
        "cgroup_roots",
        "property_inputs",
        "acquisition",
    }
)
_PLAN_PROPERTY_INPUT_KEYS = frozenset(
    {
        "label",
        "kind",
        "query_owner",
        "query_binding",
        "query_unit",
        "raw_authority_path",
    }
)
_ACQUISITION_KEYS = frozenset(
    {"armed_receipt_path", "ready_fifo", "release_fifo"}
)
_FIFO_KEYS = frozenset({"path", "device", "inode"})
_SOURCE_SELECTOR_KEYS = frozenset(
    {
        "schema",
        "boot_id",
        "source_unit",
        "source_invocation_id",
        "source_receipt_sha256",
    }
)
_CGROUP_ROOT_KEYS = frozenset({"label", "path"})
_PROPERTY_INPUT_KEYS = frozenset(
    {
        "label",
        "kind",
        "query_owner",
        "query_unit",
        "query_invocation_id",
        "raw_authority_path",
    }
)
_FORMAL_PLAN_BINDING_KEYS = frozenset(
    {
        "schema",
        "plan_path",
        "plan_sha256",
        "program",
        "acquisition",
        "source_selector",
        "materialized_request_sha256",
    }
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class ObserverError(RuntimeError):
    """The requested receipt could not be copied without ambiguity."""


def _fail(message: str) -> NoReturn:
    raise ObserverError(message)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ObserverError("value cannot be encoded as canonical JSON") from exc


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"JSON object contains duplicate key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    _fail(f"JSON contains forbidden non-finite constant {value!r}")


def _decode_json(raw: bytes, *, label: str) -> Any:
    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except ObserverError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ObserverError(f"{label} is not strict UTF-8 JSON") from exc
    _validate_json_tree(value, label=label)
    return value


def _validate_json_tree(value: Any, *, label: str) -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is list:
        for item in value:
            _validate_json_tree(item, label=label)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string object key")
            _validate_json_tree(item, label=label)
        return
    _fail(f"{label} contains a noncanonical JSON value")


def _require_exact_object(value: Any, keys: frozenset[str], *, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(f"{label} must be one exact JSON object")
    actual = frozenset(value)
    if actual != keys:
        _fail(
            f"{label} schema mismatch: "
            f"missing={sorted(keys - actual)!r}, unknown={sorted(actual - keys)!r}"
        )
    return value


def _require_string(value: Any, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be one nonempty exact string")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise ObserverError(f"{label} is not strict UTF-8") from exc
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        _fail(f"{label} contains a forbidden control character")
    return value


def _require_label(value: Any, *, label: str) -> str:
    result = _require_string(value, label=label)
    if _LABEL_RE.fullmatch(result) is None:
        _fail(f"{label} is not a canonical receipt label")
    return result


def _require_unit(value: Any, *, label: str) -> str:
    result = _require_string(value, label=label)
    try:
        result.encode("ascii", "strict")
    except UnicodeError as exc:
        raise ObserverError(f"{label} must be ASCII") from exc
    if _UNIT_RE.fullmatch(result) is None:
        _fail(f"{label} is not a canonical .service unit")
    return result


def _require_invocation(value: Any, *, label: str) -> str:
    result = _require_string(value, label=label)
    if _INVOCATION_RE.fullmatch(result) is None:
        _fail(f"{label} must be 32 lowercase hexadecimal characters")
    return result


def _require_sha256(value: Any, *, label: str) -> str:
    result = _require_string(value, label=label)
    if _SHA256_RE.fullmatch(result) is None:
        _fail(f"{label} must be 64 lowercase hexadecimal characters")
    return result


def _require_uint_text(value: Any, *, label: str, positive: bool = False) -> int:
    text = _require_string(value, label=label)
    return _uint(text, label=label, positive=positive)


def _require_optional(value: Any, decoder: Any, *, label: str) -> Any:
    if value is None:
        return None
    return decoder(value, label=label)


def _require_path(value: Any, *, label: str) -> Path:
    raw = _require_string(value, label=label)
    path = Path(raw)
    if not path.is_absolute() or str(path) != raw or any(part in {".", ".."} for part in path.parts):
        _fail(f"{label} must be a normalized absolute path")
    return path


def _read_all_fd(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _write_all_fd(descriptor: int, payload: bytes, *, label: str) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            _fail(f"{label} write made no progress")
        offset += written


def _read_regular(path: Path, *, label: str) -> tuple[bytes, dict[str, int]]:
    try:
        before = path.lstat()
    except OSError as exc:
        raise ObserverError(f"cannot stat {label}: {path}") from exc
    if not stat.S_ISREG(before.st_mode):
        _fail(f"{label} must be a regular non-symlink file: {path}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                _fail(f"{label} identity changed while opening: {path}")
            raw = _read_all_fd(descriptor)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
    except ObserverError:
        raise
    except OSError as exc:
        raise ObserverError(f"cannot read {label}: {path}") from exc
    if (
        (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
        or after.st_size != before.st_size
        or after.st_mtime_ns != before.st_mtime_ns
        or len(raw) != after.st_size
    ):
        _fail(f"{label} changed while being copied: {path}")
    try:
        final = path.lstat()
    except OSError as exc:
        raise ObserverError(f"{label} disappeared after being copied: {path}") from exc
    if (
        (final.st_dev, final.st_ino) != (before.st_dev, before.st_ino)
        or final.st_size != before.st_size
        or final.st_mtime_ns != before.st_mtime_ns
    ):
        _fail(f"{label} path identity changed while being copied: {path}")
    return raw, {
        "device": before.st_dev,
        "inode": before.st_ino,
        "mode": stat.S_IMODE(before.st_mode),
    }


def _decode_fifo(value: Any, *, label: str) -> dict[str, str]:
    item = _require_exact_object(value, _FIFO_KEYS, label=label)
    path = _require_path(item["path"], label=f"{label}.path")
    device = _require_uint_text(
        item["device"], label=f"{label}.device", positive=True
    )
    inode = _require_uint_text(
        item["inode"], label=f"{label}.inode", positive=True
    )
    return {
        "path": str(path),
        "device": str(device),
        "inode": str(inode),
    }


def _fifo_identity(value: dict[str, str]) -> tuple[int, int]:
    return int(value["device"], 10), int(value["inode"], 10)


def _open_fifo_pin(value: dict[str, str], *, label: str) -> int:
    path = Path(value["path"])
    expected = _fifo_identity(value)
    path_flag = getattr(os, "O_PATH", 0)
    if path_flag == 0:
        _fail("formal FIFO identity pinning requires Linux O_PATH")
    try:
        descriptor = os.open(
            path,
            path_flag
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
    except OSError as exc:
        raise ObserverError(f"cannot pin {label}: {path}") from exc
    try:
        opened = os.fstat(descriptor)
        current = path.lstat()
        if not stat.S_ISFIFO(opened.st_mode) or not stat.S_ISFIFO(current.st_mode):
            _fail(f"{label} is not one pre-created FIFO")
        if (opened.st_dev, opened.st_ino) != expected:
            _fail(f"{label} descriptor identity differs from the plan")
        if (current.st_dev, current.st_ino) != expected:
            _fail(f"{label} path identity differs from the plan")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _prove_fifo_descriptor(
    descriptor: int,
    pin_descriptor: int,
    expected: dict[str, str],
    *,
    label: str,
) -> None:
    live = os.fstat(descriptor)
    pinned = os.fstat(pin_descriptor)
    planned = _fifo_identity(expected)
    if not stat.S_ISFIFO(live.st_mode) or not stat.S_ISFIFO(pinned.st_mode):
        _fail(f"{label} descriptor is not one FIFO")
    if (live.st_dev, live.st_ino) != planned or (
        pinned.st_dev,
        pinned.st_ino,
    ) != planned:
        _fail(f"{label} descriptor identity differs from the retained pin")


def _revalidate_fifo_pin(
    descriptor: int, value: dict[str, str], *, label: str
) -> None:
    expected = _fifo_identity(value)
    pinned = os.fstat(descriptor)
    try:
        current = Path(value["path"]).lstat()
    except OSError as exc:
        raise ObserverError(f"{label} path disappeared after rendezvous") from exc
    if not stat.S_ISFIFO(pinned.st_mode) or not stat.S_ISFIFO(current.st_mode):
        _fail(f"{label} ceased to be one exact FIFO")
    if (pinned.st_dev, pinned.st_ino) != expected or (
        current.st_dev,
        current.st_ino,
    ) != expected:
        _fail(f"{label} identity drifted during rendezvous")


def _perform_acquisition(
    acquisition: dict[str, Any], *, armed_payload: dict[str, Any]
) -> None:
    ready = acquisition["ready_fifo"]
    release = acquisition["release_fifo"]
    ready_pin = _open_fifo_pin(ready, label="ready FIFO")
    release_pin = -1
    try:
        release_pin = _open_fifo_pin(release, label="release FIFO")
        _publish_no_replace(
            Path(acquisition["armed_receipt_path"]),
            armed_payload,
            starttime=armed_payload["process_identity"]["starttime"],
        )

        ready_descriptor = -1
        try:
            ready_descriptor = os.open(
                ready["path"],
                os.O_WRONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
            )
            _prove_fifo_descriptor(
                ready_descriptor, ready_pin, ready, label="ready FIFO"
            )
            _write_all_fd(ready_descriptor, READY_BYTES, label="ready FIFO")
        except ObserverError:
            raise
        except OSError as exc:
            raise ObserverError("cannot publish the ready FIFO token") from exc
        finally:
            if ready_descriptor >= 0:
                os.close(ready_descriptor)

        release_descriptor = -1
        try:
            release_descriptor = os.open(
                release["path"],
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
            )
            _prove_fifo_descriptor(
                release_descriptor, release_pin, release, label="release FIFO"
            )
            permit = _read_all_fd(release_descriptor)
        except ObserverError:
            raise
        except OSError as exc:
            raise ObserverError("cannot consume the release FIFO token") from exc
        finally:
            if release_descriptor >= 0:
                os.close(release_descriptor)
        if permit != RELEASE_BYTES:
            _fail("release FIFO did not carry the exact one-shot token and EOF")
        _revalidate_fifo_pin(ready_pin, ready, label="ready FIFO")
        _revalidate_fifo_pin(release_pin, release, label="release FIFO")
    finally:
        os.close(ready_pin)
        if release_pin >= 0:
            os.close(release_pin)


def _read_proc_text(path: Path, *, label: str) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            raw = _read_all_fd(descriptor)
        finally:
            os.close(descriptor)
        return raw.decode("ascii", "strict")
    except (OSError, UnicodeError) as exc:
        raise ObserverError(f"cannot read exact {label}: {path}") from exc


def _uint(value: str, *, label: str, positive: bool = False) -> int:
    if _UINT_RE.fullmatch(value) is None:
        _fail(f"{label} is not canonical unsigned decimal")
    result = int(value, 10)
    if result > (1 << 64) - 1 or (positive and result == 0):
        _fail(f"{label} is outside the accepted uint64 range")
    return result


def _process_starttime(pid: int) -> int:
    raw = _read_proc_text(Path(f"/proc/{pid}/stat"), label="process stat").rstrip("\n")
    close = raw.rfind(")")
    if close < 0 or close + 2 >= len(raw):
        _fail("process stat has no canonical command boundary")
    fields = raw[close + 2 :].split(" ")
    if len(fields) < 20 or any(field == "" for field in fields):
        _fail("process stat is missing the starttime field")
    return _uint(fields[19], label="process starttime", positive=True)


def _unified_cgroup(raw: str) -> str:
    lines = raw.splitlines()
    if len(lines) != 1 or not lines[0].startswith("0::"):
        _fail("/proc cgroup is not one unified cgroup-v2 entry")
    lineage = lines[0][3:]
    if not lineage.startswith("/") or "//" in lineage or any(
        part in {"", ".", ".."} for part in lineage.split("/")[1:]
    ):
        _fail("/proc cgroup contains a noncanonical unified lineage")
    return lineage


def _process_identity(mode: str, expected_invocation: str) -> dict[str, Any]:
    pid = os.getpid()
    starttime = _process_starttime(pid)
    proc_cgroup_raw = _read_proc_text(Path(f"/proc/{pid}/cgroup"), label="process cgroup")
    lineage = _unified_cgroup(proc_cgroup_raw)
    if mode == "run-main" and not lineage.endswith("/supervisor"):
        _fail("run-main is not executing in the delegated supervisor subgroup")
    if mode == "exec-stop-post" and not lineage.endswith("/.control"):
        _fail("exec-stop-post is not executing in the service .control subgroup")

    invocation = _require_invocation(
        os.environ.get("INVOCATION_ID"), label="environment INVOCATION_ID"
    )
    if invocation != expected_invocation:
        _fail("environment INVOCATION_ID does not match the bound request")
    boot_id = _read_proc_text(
        Path("/proc/sys/kernel/random/boot_id"), label="boot ID"
    ).strip()
    if _BOOT_RE.fullmatch(boot_id) is None:
        _fail("kernel boot ID is not canonical")
    return {
        "boot_id": boot_id,
        "invocation_id": invocation,
        "pid": pid,
        "proc_cgroup_raw": proc_cgroup_raw,
        "starttime": starttime,
        "unified_cgroup": lineage,
    }


def _stop_post_environment(mode: str) -> dict[str, str] | None:
    names = ("INVOCATION_ID", "SERVICE_RESULT", "EXIT_CODE", "EXIT_STATUS")
    if mode != "exec-stop-post":
        return None
    result: dict[str, str] = {}
    for name in names:
        value = _require_string(os.environ.get(name), label=f"environment {name}")
        try:
            value.encode("ascii", "strict")
        except UnicodeError as exc:
            raise ObserverError(f"environment {name} must be ASCII") from exc
        if name == "INVOCATION_ID":
            _require_invocation(value, label=f"environment {name}")
        elif _TOKEN_RE.fullmatch(value) is None:
            _fail(f"environment {name} is not one literal systemd token")
        result[name] = value
    return result


def _decode_line_mapping(raw: str, *, label: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in raw.splitlines():
        parts = line.split(" ")
        if len(parts) != 2 or not parts[0] or parts[0] in result:
            _fail(f"{label} is not an exact unique key/value receipt")
        result[parts[0]] = _uint(parts[1], label=f"{label}.{parts[0]}")
    if not result:
        _fail(f"{label} is empty")
    return result


def _decode_pid_lines(raw: str, *, label: str) -> list[int]:
    if raw == "":
        return []
    lines = raw.splitlines()
    if not lines or raw != "".join(f"{line}\n" for line in lines):
        _fail(f"{label} is not canonical newline-delimited PID data")
    return [_uint(line, label=label, positive=True) for line in lines]


def _cgroup_children(
    descriptor: int, *, label: str
) -> tuple[tuple[str, int, int], ...]:
    try:
        with os.scandir(descriptor) as entries:
            values = sorted(entries, key=lambda entry: entry.name)
    except OSError as exc:
        raise ObserverError(f"cannot enumerate cgroup directory {label}") from exc
    children: list[tuple[str, int, int]] = []
    for entry in values:
        try:
            identity = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise ObserverError(
                f"cannot stat cgroup inventory entry: {label}/{entry.name}"
            ) from exc
        if stat.S_ISLNK(identity.st_mode):
            _fail(f"cgroup inventory contains a symlink: {label}/{entry.name}")
        if stat.S_ISDIR(identity.st_mode):
            children.append((entry.name, identity.st_dev, identity.st_ino))
    return tuple(children)


def _read_cgroup_control(descriptor: int, name: str, *, label: str) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        control = os.open(name, flags, dir_fd=descriptor)
        try:
            opened = os.fstat(control)
            if not stat.S_ISREG(opened.st_mode):
                _fail(f"{label}/{name} is not a regular cgroup control file")
            return _read_all_fd(control).decode("ascii", "strict")
        finally:
            os.close(control)
    except ObserverError:
        raise
    except (OSError, UnicodeError) as exc:
        raise ObserverError(f"cannot read exact {label}/{name}") from exc


def _capture_cgroup_root(label: str, path: Path) -> dict[str, Any]:
    cgroup_mount = Path("/sys/fs/cgroup")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(cgroup_mount)
    except (OSError, ValueError) as exc:
        raise ObserverError(f"cgroup root is not under /sys/fs/cgroup: {path}") from exc
    if resolved != path or path.is_symlink() or not path.is_dir():
        _fail(f"cgroup root must be one canonical real directory: {path}")
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    held: list[dict[str, Any]] = []
    opened_descriptors: list[int] = []
    try:
        root_descriptor = os.open(path, directory_flags)
        opened_descriptors.append(root_descriptor)
        pending: list[tuple[int, str, int | None, str | None]] = [
            (root_descriptor, ".", None, None)
        ]
        while pending:
            descriptor, relative, parent_index, entry_name = pending.pop()
            identity = os.fstat(descriptor)
            if not stat.S_ISDIR(identity.st_mode):
                _fail(f"cgroup inventory entry is not a directory: {relative}")
            child_facts = _cgroup_children(descriptor, label=relative)
            children = tuple(child[0] for child in child_facts)
            events_raw = _read_cgroup_control(
                descriptor, "cgroup.events", label=relative
            )
            procs_raw = _read_cgroup_control(
                descriptor, "cgroup.procs", label=relative
            )
            index = len(held)
            held.append(
                {
                    "children": children,
                    "child_facts": child_facts,
                    "descriptor": descriptor,
                    "device": identity.st_dev,
                    "entry_name": entry_name,
                    "events": _decode_line_mapping(
                        events_raw, label=f"cgroup.events[{relative}]"
                    ),
                    "events_raw": events_raw,
                    "inode": identity.st_ino,
                    "parent_index": parent_index,
                    "path": relative,
                    "procs": _decode_pid_lines(
                        procs_raw, label=f"cgroup.procs[{relative}]"
                    ),
                    "procs_raw": procs_raw,
                }
            )
            opened_children: list[tuple[int, str, int, str]] = []
            for child, child_device, child_inode in child_facts:
                try:
                    child_descriptor = os.open(
                        child, directory_flags, dir_fd=descriptor
                    )
                    opened_descriptors.append(child_descriptor)
                except OSError as exc:
                    raise ObserverError(
                        f"cgroup child changed while being pinned: {relative}/{child}"
                    ) from exc
                opened_identity = os.fstat(child_descriptor)
                if (
                    not stat.S_ISDIR(opened_identity.st_mode)
                    or (opened_identity.st_dev, opened_identity.st_ino)
                    != (child_device, child_inode)
                ):
                    _fail(
                        f"cgroup child was replaced while being pinned: "
                        f"{relative}/{child}"
                    )
                child_relative = child if relative == "." else f"{relative}/{child}"
                opened_children.append((child_descriptor, child_relative, index, child))
            pending.extend(reversed(opened_children))

        root_identity = path.stat(follow_symlinks=False)
        for item in held:
            descriptor = item["descriptor"]
            identity = os.fstat(descriptor)
            expected = (item["device"], item["inode"])
            if (identity.st_dev, identity.st_ino) != expected:
                _fail(f"pinned cgroup identity drifted: {item['path']}")
            if _cgroup_children(descriptor, label=item["path"]) != item["child_facts"]:
                _fail(f"cgroup child inventory changed: {item['path']}")
            parent_index = item["parent_index"]
            if parent_index is None:
                if (root_identity.st_dev, root_identity.st_ino) != expected:
                    _fail("cgroup root path was replaced during inventory")
            else:
                parent_descriptor = held[parent_index]["descriptor"]
                child_identity = os.stat(
                    item["entry_name"],
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (
                    not stat.S_ISDIR(child_identity.st_mode)
                    or (child_identity.st_dev, child_identity.st_ino) != expected
                ):
                    _fail(f"cgroup child path was replaced: {item['path']}")

        inventory = []
        for item in sorted(held, key=lambda value: value["path"]):
            inventory.append(
                {
                    "children": list(item["children"]),
                    "device": item["device"],
                    "events": item["events"],
                    "events_raw": item["events_raw"],
                    "inode": item["inode"],
                    "path": item["path"],
                    "procs": item["procs"],
                    "procs_raw": item["procs_raw"],
                }
            )
        return {"label": label, "path": str(path), "inventory": inventory}
    except ObserverError:
        raise
    except OSError as exc:
        raise ObserverError(f"cgroup inventory failed for {path}") from exc
    finally:
        close_failed = False
        for descriptor in opened_descriptors:
            try:
                os.close(descriptor)
            except OSError:
                close_failed = True
        if close_failed:
            raise ObserverError("pinned cgroup directory close was uncertain")


def _decode_ndjson(raw: bytes, *, label: str) -> list[Any]:
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise ObserverError(f"{label} is not strict UTF-8 JSON text") from exc
    if text and not text.endswith("\n"):
        _fail(f"{label} must end at a complete JSON record boundary")
    records: list[Any] = []
    for index, line in enumerate(text.splitlines()):
        if not line:
            _fail(f"{label} contains an empty JSON record")
        decoded = _decode_json(line.encode("utf-8"), label=f"{label}[{index}]")
        if _canonical_bytes(decoded) != (line + "\n").encode("utf-8"):
            _fail(f"{label}[{index}] is not canonical JSON")
        records.append(decoded)
    return records


def _decode_tagged_dbus(value: Any, signature: str, *, label: str) -> Any:
    if signature == "s":
        tagged = _require_exact_object(
            value, frozenset({"signature", "kind", "value"}), label=label
        )
        if tagged["signature"] != "s" or tagged["kind"] != "text":
            _fail(f"{label} is not one tagged D-Bus string")
        text = tagged["value"]
        if type(text) is not str or "\0" in text:
            _fail(f"{label} contains an invalid D-Bus string")
        try:
            text.encode("utf-8", "strict")
        except UnicodeError as exc:
            raise ObserverError(f"{label} is not strict UTF-8") from exc
        return text
    if signature == "b":
        tagged = _require_exact_object(
            value, frozenset({"signature", "kind", "value"}), label=label
        )
        if (
            tagged["signature"] != "b"
            or tagged["kind"] != "boolean"
            or type(tagged["value"]) is not bool
        ):
            _fail(f"{label} is not one tagged D-Bus boolean")
        return tagged["value"]
    if signature in {"i", "u", "t"}:
        tagged = _require_exact_object(
            value, frozenset({"signature", "kind", "value"}), label=label
        )
        raw_integer = tagged["value"]
        pattern = _INT_RE if signature == "i" else _UINT_RE
        if (
            tagged["signature"] != signature
            or tagged["kind"] != "integer"
            or type(raw_integer) is not str
            or pattern.fullmatch(raw_integer) is None
        ):
            _fail(f"{label} is not one tagged D-Bus {signature} integer")
        integer = int(raw_integer, 10)
        lower, upper = {
            "i": (-(1 << 31), (1 << 31) - 1),
            "u": (0, (1 << 32) - 1),
            "t": (0, (1 << 64) - 1),
        }[signature]
        if integer < lower or integer > upper:
            _fail(f"{label} is outside the D-Bus {signature} range")
        return integer
    if signature == "ay":
        tagged = _require_exact_object(
            value,
            frozenset({"signature", "kind", "length", "base64", "sha256"}),
            label=label,
        )
        if tagged["signature"] != "ay" or tagged["kind"] != "binary":
            _fail(f"{label} is not one tagged D-Bus byte array")
        length = _require_uint_text(tagged["length"], label=f"{label}.length")
        digest = _require_sha256(tagged["sha256"], label=f"{label}.sha256")
        encoded = tagged["base64"]
        if type(encoded) is not str:
            _fail(f"{label}.base64 must be one exact string")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError, UnicodeError) as exc:
            raise ObserverError(f"{label}.base64 is invalid") from exc
        if (
            base64.b64encode(raw).decode("ascii") != encoded
            or len(raw) != length
            or hashlib.sha256(raw).hexdigest() != digest
        ):
            _fail(f"{label} byte length or digest drifted")
        return raw
    if signature == "as":
        tagged = _require_exact_object(
            value, frozenset({"signature", "kind", "items"}), label=label
        )
        items = tagged["items"]
        if (
            tagged["signature"] != "as"
            or tagged["kind"] != "array"
            or type(items) is not list
        ):
            _fail(f"{label} is not one tagged D-Bus string array")
        return [
            _decode_tagged_dbus(item, "s", label=f"{label}[{index}]")
            for index, item in enumerate(items)
        ]
    if signature == "(sasbttttuii)":
        tagged = _require_exact_object(
            value, frozenset({"signature", "kind", "items"}), label=label
        )
        items = tagged["items"]
        signatures = ("s", "as", "b", "t", "t", "t", "t", "u", "i", "i")
        if (
            tagged["signature"] != signature
            or tagged["kind"] != "struct"
            or type(items) is not list
            or len(items) != len(signatures)
        ):
            _fail(f"{label} is not one tagged ExecStopPost struct")
        return [
            _decode_tagged_dbus(item, item_signature, label=f"{label}[{index}]")
            for index, (item, item_signature) in enumerate(zip(items, signatures))
        ]
    if signature == "a(sasbttttuii)":
        tagged = _require_exact_object(
            value, frozenset({"signature", "kind", "items"}), label=label
        )
        items = tagged["items"]
        if (
            tagged["signature"] != signature
            or tagged["kind"] != "array"
            or type(items) is not list
        ):
            _fail(f"{label} is not one tagged ExecStopPost array")
        return [
            _decode_tagged_dbus(
                item, "(sasbttttuii)", label=f"{label}[{index}]"
            )
            for index, item in enumerate(items)
        ]
    _fail(f"{label} has unsupported frozen D-Bus signature {signature!r}")


def _decode_systemd_authority(
    value: Any,
    *,
    expected_boot_id: str,
    expected_unit: str,
    expected_invocation: str,
) -> dict[str, Any]:
    authority = _require_exact_object(
        value, _RAW_QUERY_KEYS, label="systemd raw authority"
    )
    if authority["schema"] != RAW_QUERY_SCHEMA:
        _fail("systemd raw authority schema is not supported")
    boot_id = _require_string(authority["boot_id"], label="raw authority boot_id")
    if _BOOT_RE.fullmatch(boot_id) is None or boot_id != expected_boot_id:
        _fail("systemd raw authority boot ID differs from the current actor")
    unit = _require_unit(authority["unit"], label="raw authority unit")
    if unit != expected_unit:
        _fail("systemd raw authority unit differs from the request binding")
    invocation = _require_invocation(
        authority["invocation_id"], label="raw authority invocation_id"
    )
    if invocation != expected_invocation:
        _fail("systemd raw authority invocation differs from the request binding")
    manager_owner = _require_string(
        authority["manager_owner"], label="raw authority manager_owner"
    )
    if _DBUS_OWNER_RE.fullmatch(manager_owner) is None:
        _fail("systemd raw authority manager owner is not one unique bus name")
    object_path = _require_string(
        authority["object_path"], label="raw authority object_path"
    )
    if (
        _DBUS_OBJECT_RE.fullmatch(object_path) is None
        or not object_path.startswith("/org/freedesktop/systemd1/unit/")
    ):
        _fail("systemd raw authority object path is not one unit object")
    if type(authority["normalization"]) is not dict:
        _fail("systemd raw authority normalization must be one object")
    properties = authority["properties"]
    if type(properties) is not list or len(properties) != len(
        _SYSTEMD_PROPERTY_SIGNATURES
    ):
        _fail("systemd raw authority property ledger is not exact")
    invocation_property: bytes | None = None
    id_property: str | None = None
    for index, (raw_property, expected) in enumerate(
        zip(properties, _SYSTEMD_PROPERTY_SIGNATURES)
    ):
        item = _require_exact_object(
            raw_property, _RAW_PROPERTY_KEYS, label=f"raw authority properties[{index}]"
        )
        interface, name, signature = expected
        if (
            item["destination_owner"] != manager_owner
            or item["object_path"] != object_path
        ):
            _fail("systemd raw authority manager owner or object path drifted")
        if (
            item["interface"] != interface
            or item["property"] != name
            or item["variant_signature"] != signature
        ):
            _fail("systemd raw authority property ledger order or signature drifted")
        decoded = _decode_tagged_dbus(
            item["value"], signature, label=f"raw authority {interface}.{name}"
        )
        if interface == _UNIT_INTERFACE and name == "Id":
            id_property = decoded
        if interface == _UNIT_INTERFACE and name == "InvocationID":
            invocation_property = decoded
    if id_property != unit:
        _fail("systemd raw authority Id property differs from its unit")
    if invocation_property is None or len(invocation_property) != 16:
        _fail("systemd raw authority InvocationID is not exactly 16 bytes")
    if invocation_property.hex() != invocation:
        _fail("systemd raw authority InvocationID property differs from its binding")
    return authority


def _capture_property_input(
    item: dict[str, Any], *, expected_boot_id: str
) -> dict[str, Any]:
    label = _require_label(item["label"], label="property input label")
    kind = _require_string(item["kind"], label=f"property input {label} kind")
    if kind not in _INPUT_KINDS:
        _fail(f"property input {label} has an unknown authority kind")
    query_owner = _require_string(
        item["query_owner"], label=f"property input {label} query_owner"
    )
    query_unit = _require_unit(
        item["query_unit"], label=f"property input {label} query_unit"
    )
    query_invocation = _require_invocation(
        item["query_invocation_id"],
        label=f"property input {label} query_invocation_id",
    )
    authority_path = _require_path(
        item["raw_authority_path"],
        label=f"property input {label} raw_authority_path",
    )
    authority_raw, authority_identity = _read_regular(
        authority_path, label=f"property input {label} raw authority"
    )
    if not authority_raw:
        _fail(f"property input {label} contains an empty raw authority")
    try:
        authority_text = authority_raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise ObserverError(f"property input {label} is not strict UTF-8") from exc
    if kind == "journal-corroboration":
        decoded = _decode_ndjson(
            authority_raw, label=f"property input {label} journal"
        )
        authoritative = False
    else:
        decoded = _decode_json(
            authority_raw, label=f"property input {label} authority"
        )
        if _canonical_bytes(decoded) != authority_raw:
            _fail(f"property input {label} raw authority is not canonical JSON")
        decoded = _decode_systemd_authority(
            decoded,
            expected_boot_id=expected_boot_id,
            expected_unit=query_unit,
            expected_invocation=query_invocation,
        )
        authoritative = True
    return {
        "authoritative": authoritative,
        "kind": kind,
        "label": label,
        "query_invocation_id": query_invocation,
        "query_owner": query_owner,
        "query_unit": query_unit,
        "raw_authority": {
            "decoded": decoded,
            "identity": authority_identity,
            "path": str(authority_path),
            "sha256": hashlib.sha256(authority_raw).hexdigest(),
            "size": len(authority_raw),
            "text": authority_text,
        },
    }


def _decode_request(path: Path) -> tuple[dict[str, Any], bytes]:
    raw, _ = _read_regular(path, label="observer request")
    request = _require_exact_object(
        _decode_json(raw, label="observer request"), _REQUEST_KEYS, label="observer request"
    )
    if _canonical_bytes(request) != raw:
        _fail("observer request is not exact canonical JSON")
    if request["schema"] != REQUEST_SCHEMA:
        _fail("observer request schema is not supported")
    mode = _require_string(request["mode"], label="observer mode")
    if mode not in _MODES:
        _fail("observer mode is not supported")
    _require_path(request["output_path"], label="output_path")
    _require_unit(request["unit"], label="unit")
    _require_invocation(request["expected_invocation_id"], label="expected_invocation_id")
    source_unit = _require_optional(request["source_unit"], _require_unit, label="source_unit")
    source_invocation = _require_optional(
        request["source_invocation_id"], _require_invocation, label="source_invocation_id"
    )
    if mode == "closer":
        if source_unit is None or source_invocation is None:
            _fail("closer request must bind a nonempty source unit and invocation")
        if source_unit == request["unit"]:
            _fail("closer source unit must differ from the closer unit")
    elif source_unit is not None or source_invocation is not None:
        _fail("only closer requests may bind a source unit and invocation")

    roots = request["cgroup_roots"]
    properties = request["property_inputs"]
    if type(roots) is not list or type(properties) is not list:
        _fail("cgroup_roots and property_inputs must be exact JSON arrays")
    if not roots:
        _fail("observer request must bind at least one complete cgroup root")
    root_labels: set[str] = set()
    root_paths: set[str] = set()
    for index, value in enumerate(roots):
        item = _require_exact_object(value, _CGROUP_ROOT_KEYS, label=f"cgroup_roots[{index}]")
        label = _require_label(item["label"], label=f"cgroup_roots[{index}].label")
        root_path = str(_require_path(item["path"], label=f"cgroup_roots[{index}].path"))
        if label in root_labels or root_path in root_paths:
            _fail("cgroup_roots contains a duplicate label or path")
        root_labels.add(label)
        root_paths.add(root_path)

    property_labels: set[str] = set()
    property_paths: set[str] = set()
    authority_count = 0
    authority_pairs: set[tuple[str, str]] = set()
    allowed_queries = {
        (request["unit"], request["expected_invocation_id"]),
    }
    if source_unit is not None and source_invocation is not None:
        allowed_queries.add((source_unit, source_invocation))
    for index, value in enumerate(properties):
        item = _require_exact_object(
            value, _PROPERTY_INPUT_KEYS, label=f"property_inputs[{index}]"
        )
        label = _require_label(item["label"], label=f"property_inputs[{index}].label")
        kind = _require_string(item["kind"], label=f"property_inputs[{index}].kind")
        if kind not in _INPUT_KINDS:
            _fail(f"property_inputs[{index}] has an unknown kind")
        query_owner = _require_string(
            item["query_owner"], label=f"property_inputs[{index}].query_owner"
        )
        if query_owner not in _QUERY_OWNERS:
            _fail(f"property_inputs[{index}] has an unknown outer query owner")
        if (
            kind == "systemd-properties-authority"
            and query_owner != "system-manager-dbus"
        ) or (
            kind == "journal-corroboration"
            and query_owner != "invocation-filtered-journal-export"
        ):
            _fail(f"property_inputs[{index}] kind and query owner disagree")
        query_pair = (
            _require_unit(
                item["query_unit"], label=f"property_inputs[{index}].query_unit"
            ),
            _require_invocation(
                item["query_invocation_id"],
                label=f"property_inputs[{index}].query_invocation_id",
            ),
        )
        if query_pair not in allowed_queries:
            _fail(f"property_inputs[{index}] is bound to an undeclared invocation")
        authority_count += int(kind == "systemd-properties-authority")
        if kind == "systemd-properties-authority":
            authority_pairs.add(query_pair)
        authority_path = str(
            _require_path(
                item["raw_authority_path"], label="raw_authority_path"
            )
        )
        if label in property_labels or authority_path in property_paths:
            _fail("property_inputs contains a duplicate label or raw path")
        property_labels.add(label)
        property_paths.add(authority_path)
    if authority_count == 0:
        _fail("observer request must bind at least one systemd property authority input")
    required_authority = (
        (source_unit, source_invocation)
        if mode == "closer"
        else (request["unit"], request["expected_invocation_id"])
    )
    if required_authority not in authority_pairs:
        _fail("observer request lacks the required invocation property authority")
    return request, raw


def _decode_acquisition(value: Any) -> dict[str, Any]:
    item = _require_exact_object(
        value, _ACQUISITION_KEYS, label="observer acquisition"
    )
    armed_path = _require_path(
        item["armed_receipt_path"], label="acquisition.armed_receipt_path"
    )
    ready = _decode_fifo(item["ready_fifo"], label="acquisition.ready_fifo")
    release = _decode_fifo(
        item["release_fifo"], label="acquisition.release_fifo"
    )
    if ready["path"] == release["path"] or _fifo_identity(ready) == _fifo_identity(
        release
    ):
        _fail("ready and release FIFOs must be distinct objects")
    if str(armed_path) in {ready["path"], release["path"]}:
        _fail("armed receipt path must differ from both FIFO paths")
    return {
        "armed_receipt_path": str(armed_path),
        "ready_fifo": ready,
        "release_fifo": release,
    }


def _decode_plan(path: Path) -> tuple[dict[str, Any], bytes]:
    raw, _ = _read_regular(path, label="observer plan")
    plan = _require_exact_object(
        _decode_json(raw, label="observer plan"), _PLAN_KEYS, label="observer plan"
    )
    if _canonical_bytes(plan) != raw:
        _fail("observer plan is not exact canonical JSON")
    if plan["schema"] != PLAN_SCHEMA:
        _fail("observer plan schema is not supported")
    mode = _require_string(plan["mode"], label="observer plan mode")
    if mode not in _MODES:
        _fail("observer plan mode is not supported")
    program_path = _require_path(plan["program_path"], label="program_path")
    program_sha256 = _require_sha256(
        plan["program_sha256"], label="program_sha256"
    )
    request_path = _require_path(plan["request_path"], label="request_path")
    output_path = _require_path(plan["output_path"], label="output_path")
    unit = _require_unit(plan["unit"], label="unit")
    source_selector_path = _require_optional(
        plan["source_selector_path"], _require_path, label="source_selector_path"
    )
    if mode == "closer":
        if source_selector_path is None:
            _fail("closer plan requires one root-sealed source selector")
    elif source_selector_path is not None:
        _fail("only closer plans may bind a source selector")

    acquisition = _decode_acquisition(plan["acquisition"])
    reserved_paths = {
        str(program_path),
        str(request_path),
        str(output_path),
        acquisition["armed_receipt_path"],
        acquisition["ready_fifo"]["path"],
        acquisition["release_fifo"]["path"],
    }
    if len(reserved_paths) != 6:
        _fail("observer plan program/request/output/acquisition paths must be distinct")
    if source_selector_path is not None and str(source_selector_path) in reserved_paths:
        _fail("source selector path overlaps an observer output or FIFO")
    if source_selector_path is not None:
        reserved_paths.add(str(source_selector_path))

    roots = plan["cgroup_roots"]
    properties = plan["property_inputs"]
    if type(roots) is not list or type(properties) is not list:
        _fail("plan cgroup_roots and property_inputs must be exact JSON arrays")
    if not roots:
        _fail("observer plan must bind at least one cgroup root")
    normalized_roots: list[dict[str, str]] = []
    root_labels: set[str] = set()
    root_paths: set[str] = set()
    for index, value in enumerate(roots):
        item = _require_exact_object(
            value, _CGROUP_ROOT_KEYS, label=f"cgroup_roots[{index}]"
        )
        label = _require_label(item["label"], label=f"cgroup_roots[{index}].label")
        root_path = str(
            _require_path(item["path"], label=f"cgroup_roots[{index}].path")
        )
        if label in root_labels or root_path in root_paths:
            _fail("plan cgroup_roots contains a duplicate label or path")
        root_labels.add(label)
        root_paths.add(root_path)
        normalized_roots.append({"label": label, "path": root_path})

    normalized_properties: list[dict[str, str]] = []
    property_labels: set[str] = set()
    property_paths: set[str] = set()
    authority_bindings: set[str] = set()
    for index, value in enumerate(properties):
        item = _require_exact_object(
            value,
            _PLAN_PROPERTY_INPUT_KEYS,
            label=f"property_inputs[{index}]",
        )
        label = _require_label(item["label"], label=f"property_inputs[{index}].label")
        kind = _require_string(item["kind"], label=f"property_inputs[{index}].kind")
        if kind not in _INPUT_KINDS:
            _fail(f"property_inputs[{index}] has an unknown kind")
        query_owner = _require_string(
            item["query_owner"], label=f"property_inputs[{index}].query_owner"
        )
        if query_owner not in _QUERY_OWNERS:
            _fail(f"property_inputs[{index}] has an unknown query owner")
        if (
            kind == "systemd-properties-authority"
            and query_owner != "system-manager-dbus"
        ) or (
            kind == "journal-corroboration"
            and query_owner != "invocation-filtered-journal-export"
        ):
            _fail(f"property_inputs[{index}] kind and query owner disagree")
        binding = _require_string(
            item["query_binding"], label=f"property_inputs[{index}].query_binding"
        )
        if binding not in {"current", "source"}:
            _fail(f"property_inputs[{index}] has an unknown query binding")
        if binding == "source" and mode != "closer":
            _fail("only closer plans may bind source property inputs")
        query_unit = _require_unit(
            item["query_unit"], label=f"property_inputs[{index}].query_unit"
        )
        if binding == "current" and query_unit != unit:
            _fail("current property input query unit differs from the plan unit")
        authority_path = str(
            _require_path(
                item["raw_authority_path"],
                label=f"property_inputs[{index}].raw_authority_path",
            )
        )
        if label in property_labels or authority_path in property_paths:
            _fail("plan property_inputs contains a duplicate label or raw path")
        if authority_path in reserved_paths:
            _fail("property input overlaps an observer output or FIFO")
        property_labels.add(label)
        property_paths.add(authority_path)
        if kind == "systemd-properties-authority":
            authority_bindings.add(binding)
        normalized_properties.append(
            {
                "label": label,
                "kind": kind,
                "query_owner": query_owner,
                "query_binding": binding,
                "query_unit": query_unit,
                "raw_authority_path": authority_path,
            }
        )
    required_binding = "source" if mode == "closer" else "current"
    if required_binding not in authority_bindings:
        _fail("observer plan lacks its required invocation property authority")
    if str(path) in reserved_paths or str(path) in property_paths:
        _fail("observer plan path overlaps one of its bound assets")

    return {
        "schema": PLAN_SCHEMA,
        "mode": mode,
        "program_path": str(program_path),
        "program_sha256": program_sha256,
        "request_path": str(request_path),
        "output_path": str(output_path),
        "unit": unit,
        "source_selector_path": (
            None if source_selector_path is None else str(source_selector_path)
        ),
        "cgroup_roots": normalized_roots,
        "property_inputs": normalized_properties,
        "acquisition": acquisition,
    }, raw


def _verify_program(plan: dict[str, Any]) -> dict[str, Any]:
    configured = Path(plan["program_path"])
    executed = Path(os.path.realpath(__file__))
    if configured != executed:
        _fail("executed observer program differs from the plan path")
    raw, identity = _read_regular(configured, label="observer program")
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != plan["program_sha256"]:
        _fail("executed observer program hash differs from the plan")
    if sys.version_info[:2] != (3, 12):
        _fail("formal observer plan requires Python 3.12")
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        _fail("formal observer plan requires Python -I -B")
    return {
        "path": str(executed),
        "sha256": actual_sha256,
        "identity": identity,
    }


def _decode_source_selector(
    path: Path,
    *,
    current_unit: str,
    current_identity: dict[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    raw, identity = _read_regular(path, label="source selector")
    selector = _require_exact_object(
        _decode_json(raw, label="source selector"),
        _SOURCE_SELECTOR_KEYS,
        label="source selector",
    )
    if _canonical_bytes(selector) != raw:
        _fail("source selector is not exact canonical JSON")
    if selector["schema"] != SOURCE_SELECTOR_SCHEMA:
        _fail("source selector schema is not supported")
    boot_id = _require_string(selector["boot_id"], label="source selector boot_id")
    if _BOOT_RE.fullmatch(boot_id) is None:
        _fail("source selector boot ID is not canonical")
    if boot_id != current_identity["boot_id"]:
        _fail("source selector belongs to a different boot")
    source_unit = _require_unit(
        selector["source_unit"], label="source selector source_unit"
    )
    source_invocation = _require_invocation(
        selector["source_invocation_id"],
        label="source selector source_invocation_id",
    )
    source_receipt_sha256 = _require_sha256(
        selector["source_receipt_sha256"],
        label="source selector source_receipt_sha256",
    )
    if source_unit == current_unit:
        _fail("closer source unit must differ from the closer unit")
    if source_invocation == current_identity["invocation_id"]:
        _fail("closer source invocation must differ from its current invocation")
    return {
        "schema": SOURCE_SELECTOR_SCHEMA,
        "boot_id": boot_id,
        "source_unit": source_unit,
        "source_invocation_id": source_invocation,
        "source_receipt_sha256": source_receipt_sha256,
    }, {
        **identity,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
    }


def _materialize_request(
    plan: dict[str, Any], identity: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    selector: dict[str, Any] | None = None
    if plan["mode"] == "closer":
        selector_path = Path(plan["source_selector_path"])
        selector_value, selector_identity = _decode_source_selector(
            selector_path,
            current_unit=plan["unit"],
            current_identity=identity,
        )
        selector = {
            "path": str(selector_path),
            "identity": selector_identity,
            "value": selector_value,
        }

    properties: list[dict[str, Any]] = []
    for item in plan["property_inputs"]:
        if item["query_binding"] == "current":
            query_unit = plan["unit"]
            query_invocation = identity["invocation_id"]
        else:
            if selector is None:
                _fail("source property input has no decoded selector")
            query_unit = selector["value"]["source_unit"]
            query_invocation = selector["value"]["source_invocation_id"]
            if item["query_unit"] != query_unit:
                _fail("source property query unit differs from the sealed selector")
        properties.append(
            {
                "label": item["label"],
                "kind": item["kind"],
                "query_owner": item["query_owner"],
                "query_unit": query_unit,
                "query_invocation_id": query_invocation,
                "raw_authority_path": item["raw_authority_path"],
            }
        )
    request = {
        "schema": REQUEST_SCHEMA,
        "mode": plan["mode"],
        "output_path": plan["output_path"],
        "unit": plan["unit"],
        "expected_invocation_id": identity["invocation_id"],
        "source_unit": (
            None if selector is None else selector["value"]["source_unit"]
        ),
        "source_invocation_id": (
            None
            if selector is None
            else selector["value"]["source_invocation_id"]
        ),
        "cgroup_roots": plan["cgroup_roots"],
        "property_inputs": properties,
    }
    return request, selector


def _validate_formal_plan_binding(
    request_path: Path,
    request: dict[str, Any],
    request_raw: bytes,
    identity: dict[str, Any],
    value: Any,
) -> None:
    binding = _require_exact_object(
        value, _FORMAL_PLAN_BINDING_KEYS, label="observer formal plan binding"
    )
    if binding["schema"] != PLAN_SCHEMA:
        _fail("observer formal plan binding schema is not supported")
    plan_path = _require_path(
        binding["plan_path"], label="observer formal plan binding plan_path"
    )
    plan_sha256 = _require_sha256(
        binding["plan_sha256"], label="observer formal plan binding plan_sha256"
    )
    plan, plan_raw = _decode_plan(plan_path)
    if hashlib.sha256(plan_raw).hexdigest() != plan_sha256:
        _fail("observer formal plan binding plan hash drifted")
    if str(request_path) != plan["request_path"]:
        _fail("observer materialized request path differs from its sealed plan")
    if request["output_path"] != plan["output_path"]:
        _fail("observer materialized output path differs from its sealed plan")
    expected_request, expected_selector = _materialize_request(plan, identity)
    if request != expected_request:
        _fail("observer materialized request differs from its sealed plan and actor")
    if binding["source_selector"] != expected_selector:
        _fail("observer source selector binding differs from its sealed plan")
    if binding["acquisition"] != plan["acquisition"]:
        _fail("observer acquisition binding differs from its sealed plan")
    if binding["program"] != _verify_program(plan):
        _fail("observer program binding differs from its sealed plan")
    request_sha256 = hashlib.sha256(request_raw).hexdigest()
    if (
        _require_sha256(
            binding["materialized_request_sha256"],
            label="observer materialized_request_sha256",
        )
        != request_sha256
    ):
        _fail("observer materialized request hash differs from its formal binding")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_no_replace(path: Path, payload: dict[str, Any], *, starttime: int) -> None:
    parent = path.parent
    try:
        resolved_parent = parent.resolve(strict=True)
    except OSError as exc:
        raise ObserverError(f"output parent does not exist: {parent}") from exc
    if resolved_parent != parent or parent.is_symlink() or not parent.is_dir():
        _fail("output parent must be one canonical real directory")
    temporary = parent / f".{path.name}.pending-{os.getpid()}-{starttime}"
    encoded = _canonical_bytes(payload)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, flags, 0o600)
        written = 0
        while written < len(encoded):
            count = os.write(descriptor, encoded[written:])
            if count <= 0:
                _fail("canonical receipt write made no progress")
            written += count
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        _fsync_directory(parent)
        os.link(temporary, path, follow_symlinks=False)
        _fsync_directory(parent)
        os.unlink(temporary)
        _fsync_directory(parent)
    except FileExistsError as exc:
        raise ObserverError(f"refusing to replace an existing receipt: {path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def run(
    request_path: Path, *, formal_plan_binding: dict[str, Any] | None = None
) -> None:
    request, request_raw = _decode_request(request_path)
    mode = request["mode"]
    identity = _process_identity(mode, request["expected_invocation_id"])
    stop_post = _stop_post_environment(mode)
    if stop_post is not None and stop_post["INVOCATION_ID"] != identity["invocation_id"]:
        _fail("stop-post selector and process invocation identities differ")
    if formal_plan_binding is not None:
        _validate_formal_plan_binding(
            request_path,
            request,
            request_raw,
            identity,
            formal_plan_binding,
        )

    cgroups = []
    for value in request["cgroup_roots"]:
        cgroups.append(
            _capture_cgroup_root(
                _require_label(value["label"], label="cgroup root label"),
                _require_path(value["path"], label="cgroup root path"),
            )
        )
    bindings = [
        _capture_property_input(value, expected_boot_id=identity["boot_id"])
        for value in request["property_inputs"]
    ]
    receipt = {
        "authority_policy": {
            "journal": "corroboration-only",
            "kernel_identity": "copied-raw-fact",
            "systemd_properties": "bound-raw-input",
        },
        "cgroup_roots": cgroups,
        "mode": mode,
        "process_identity": identity,
        "property_inputs": bindings,
        "request_path": str(request_path),
        "request_sha256": hashlib.sha256(request_raw).hexdigest(),
        "schema": RECEIPT_SCHEMA,
        "source_invocation_id": request["source_invocation_id"],
        "source_unit": request["source_unit"],
        "stop_post_environment": stop_post,
        "unit": request["unit"],
    }
    if formal_plan_binding is not None:
        receipt["formal_plan_binding"] = formal_plan_binding
    _publish_no_replace(
        _require_path(request["output_path"], label="output_path"),
        receipt,
        starttime=identity["starttime"],
    )


def _run_plan(plan_path: Path) -> None:
    plan, plan_raw = _decode_plan(plan_path)
    if str(plan_path) in {
        plan["program_path"],
        plan["request_path"],
        plan["output_path"],
        plan["acquisition"]["armed_receipt_path"],
        plan["acquisition"]["ready_fifo"]["path"],
        plan["acquisition"]["release_fifo"]["path"],
    }:
        _fail("observer plan path overlaps one of its bound assets")
    program = _verify_program(plan)
    invocation = _require_invocation(
        os.environ.get("INVOCATION_ID"), label="environment INVOCATION_ID"
    )
    identity = _process_identity(plan["mode"], invocation)
    stop_post = _stop_post_environment(plan["mode"])
    if stop_post is not None and stop_post["INVOCATION_ID"] != invocation:
        _fail("stop-post selector and current invocation differ before acquisition")
    plan_sha256 = hashlib.sha256(plan_raw).hexdigest()
    armed_payload = {
        "schema": ARMED_RECEIPT_SCHEMA,
        "mode": plan["mode"],
        "unit": plan["unit"],
        "process_identity": identity,
        "stop_post_environment": stop_post,
        "plan_path": str(plan_path),
        "plan_sha256": plan_sha256,
        "program": program,
        "request_path": plan["request_path"],
        "output_path": plan["output_path"],
        "source_selector_path": plan["source_selector_path"],
        "raw_authority_paths": [
            item["raw_authority_path"]
            for item in plan["property_inputs"]
            if item["kind"] == "systemd-properties-authority"
        ],
        "ready_fifo": plan["acquisition"]["ready_fifo"],
        "release_fifo": plan["acquisition"]["release_fifo"],
        "ready_sha256": hashlib.sha256(READY_BYTES).hexdigest(),
        "release_sha256": hashlib.sha256(RELEASE_BYTES).hexdigest(),
    }
    _perform_acquisition(plan["acquisition"], armed_payload=armed_payload)

    after_identity = _process_identity(plan["mode"], invocation)
    if after_identity != identity:
        _fail("observer process identity changed during acquisition")
    if _stop_post_environment(plan["mode"]) != stop_post:
        _fail("stop-post environment changed during acquisition")

    request, selector = _materialize_request(plan, identity)
    request_raw = _canonical_bytes(request)
    _publish_no_replace(
        Path(plan["request_path"]), request, starttime=identity["starttime"]
    )
    formal_plan_binding = {
        "schema": PLAN_SCHEMA,
        "plan_path": str(plan_path),
        "plan_sha256": plan_sha256,
        "program": program,
        "acquisition": plan["acquisition"],
        "source_selector": selector,
        "materialized_request_sha256": hashlib.sha256(request_raw).hexdigest(),
    }
    run(
        Path(plan["request_path"]), formal_plan_binding=formal_plan_binding
    )


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv if argv is None else argv
    if len(arguments) == 3 and arguments[1] == "--plan":
        _run_plan(_require_path(arguments[2], label="plan path"))
        return 0
    if len(arguments) != 2:
        raise SystemExit(
            "usage: generic_backend_unit_observer.py REQUEST.json or "
            "generic_backend_unit_observer.py --plan PLAN.json"
        )
    run(_require_path(arguments[1], label="request path"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ObserverError as exc:
        print(f"generic backend unit observer: {exc}", file=sys.stderr)
        raise SystemExit(125) from exc
