#!/usr/bin/env python3
"""Narrow tests-only adversary for formal generic-backend systemd cases.

The formal case reaches this file only through the accepted native exec path or
names it directly in a static run/stop-post/closer unit command.  Fixed scenario
modes either publish one immutable receipt and terminate in the requested way,
or block until an explicit FIFO permit arrives.  Only the two descendant
scenarios create processes.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, NoReturn


REQUEST_SCHEMA = "scion.generic_backend.systemd_adversary_request.v1"
RECEIPT_SCHEMA = "scion.generic_backend.systemd_adversary_receipt.v1"
PLAN_SCHEMA = "scion.generic_backend.systemd_adversary_plan.v1"
ARMED_RECEIPT_SCHEMA = "scion.generic_backend.systemd_adversary_armed.v1"
READY_BYTES = b"SCION_GENERIC_BACKEND_READY_V1\n"
RELEASE_BYTES = b"SCION_GENERIC_BACKEND_RELEASE_V1\n"

_SCENARIOS = frozenset(
    {
        "h2-main-nonzero",
        "h3-main-signal",
        "h4-stoppost-failure",
        "h6-setsid-descendant",
        "h7-guardian-hold",
        "h8-extra-topology-hold",
        "h9-failed-closer",
        "h10-gc-negative",
        "h11-unbounded-hold",
        "b7-double-fork-closed-stdio",
    }
)
_NATIVE_HOLD_SCENARIOS = frozenset(
    {"h6-setsid-descendant", "b7-double-fork-closed-stdio"}
)
_REQUEST_KEYS = frozenset(
    {
        "schema",
        "scenario",
        "unit",
        "expected_invocation_id",
        "expected_job_name",
        "expected_job_cgroup",
        "receipt_path",
        "hold_release_fifo",
    }
)
_PLAN_KEYS = frozenset(
    {
        "schema",
        "scenario",
        "unit",
        "expected_job_name",
        "program_path",
        "program_sha256",
        "request_path",
        "receipt_path",
        "acquisition",
        "hold_release_fifo",
    }
)
_ACQUISITION_KEYS = frozenset(
    {"armed_receipt_path", "ready_fifo", "release_fifo"}
)
_FIFO_KEYS = frozenset({"path", "device", "inode"})
_FORMAL_PLAN_BINDING_KEYS = frozenset(
    {
        "schema",
        "scenario",
        "unit",
        "expected_job_name",
        "plan_path",
        "plan_sha256",
        "program",
        "acquisition",
        "hold_release_fifo",
        "materialized_request_sha256",
    }
)
_ACQUISITION_SCENARIOS = frozenset(
    {
        "h2-main-nonzero",
        "h3-main-signal",
        "h4-stoppost-failure",
        "h7-guardian-hold",
        "h8-extra-topology-hold",
        "h9-failed-closer",
        "h10-gc-negative",
        "h11-unbounded-hold",
    }
)
_PRE_ACQUISITION_RECEIPT_SCENARIOS = _ACQUISITION_SCENARIOS - frozenset(
    {"h9-failed-closer"}
)
_INVOCATION_RE = re.compile(r"[0-9a-f]{32}\Z")
_JOB_NAME_RE = re.compile(r"job-(0|[1-9][0-9]{0,19})-[0-9a-f]{16}\Z")
_UNIT_RE = re.compile(r"[A-Za-z0-9:_.@-]+\.service\Z")
_BOOT_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_TOKEN_RE = re.compile(r"[A-Za-z0-9_.+@:-]+\Z")
_UINT_RE = re.compile(r"0|[1-9][0-9]*\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class AdversaryError(RuntimeError):
    """A formal adversary mode could not establish its exact evidence."""


def _fail(message: str) -> NoReturn:
    raise AdversaryError(message)


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
        raise AdversaryError("value cannot be encoded as canonical JSON") from exc


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
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except AdversaryError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AdversaryError(f"{label} is not strict UTF-8 JSON") from exc
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


def _require_exact_object(
    value: Any, keys: frozenset[str], *, label: str
) -> dict[str, Any]:
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
        raise AdversaryError(f"{label} is not strict UTF-8") from exc
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        _fail(f"{label} contains a forbidden control character")
    return value


def _require_sha256(value: Any, *, label: str) -> str:
    result = _require_string(value, label=label)
    if _SHA256_RE.fullmatch(result) is None:
        _fail(f"{label} must be 64 lowercase hexadecimal characters")
    return result


def _require_unit(value: Any, *, label: str) -> str:
    result = _require_string(value, label=label)
    try:
        result.encode("ascii", "strict")
    except UnicodeError as exc:
        raise AdversaryError(f"{label} must be ASCII") from exc
    if _UNIT_RE.fullmatch(result) is None:
        _fail(f"{label} is not a canonical .service unit")
    return result


def _require_job_name(value: Any, *, label: str) -> str:
    result = _require_string(value, label=label)
    match = _JOB_NAME_RE.fullmatch(result)
    if match is None:
        _fail(f"{label} is not one canonical production job cgroup name")
    _uint(match.group(1), label=f"{label} ordinal")
    return result


def _require_cgroup(value: Any, *, label: str) -> str:
    result = _require_string(value, label=label)
    try:
        result.encode("ascii", "strict")
    except UnicodeError as exc:
        raise AdversaryError(f"{label} must be ASCII") from exc
    if not result.startswith("/") or "//" in result or any(
        part in {"", ".", ".."} for part in result.split("/")[1:]
    ):
        _fail(f"{label} must be one canonical absolute cgroup-v2 lineage")
    return result


def _require_uint_text(value: Any, *, label: str, positive: bool = False) -> int:
    text = _require_string(value, label=label)
    return _uint(text, label=label, positive=positive)


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


def _read_regular(path: Path, *, label: str) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        raise AdversaryError(f"cannot stat {label}: {path}") from exc
    if not stat.S_ISREG(before.st_mode):
        _fail(f"{label} must be a regular non-symlink file")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                _fail(f"{label} identity changed while opening")
            raw = _read_all_fd(descriptor)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
    except AdversaryError:
        raise
    except OSError as exc:
        raise AdversaryError(f"cannot read {label}: {path}") from exc
    if (
        (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
        or after.st_size != before.st_size
        or after.st_mtime_ns != before.st_mtime_ns
        or len(raw) != after.st_size
    ):
        _fail(f"{label} changed while being copied")
    try:
        final = path.lstat()
    except OSError as exc:
        raise AdversaryError(f"{label} disappeared after being copied") from exc
    if (
        (final.st_dev, final.st_ino) != (before.st_dev, before.st_ino)
        or final.st_size != before.st_size
        or final.st_mtime_ns != before.st_mtime_ns
    ):
        _fail(f"{label} path identity changed while being copied")
    return raw


def _read_proc_text(path: Path, *, label: str) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            return _read_all_fd(descriptor).decode("ascii", "strict")
        finally:
            os.close(descriptor)
    except (OSError, UnicodeError) as exc:
        raise AdversaryError(f"cannot read exact {label}: {path}") from exc


def _uint(value: str, *, label: str, positive: bool = False) -> int:
    if _UINT_RE.fullmatch(value) is None:
        _fail(f"{label} is not canonical unsigned decimal")
    result = int(value, 10)
    if result > (1 << 64) - 1 or (positive and result == 0):
        _fail(f"{label} is outside the accepted uint64 range")
    return result


def _starttime(pid: int) -> int:
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
        _fail("process does not have one unified cgroup-v2 lineage")
    lineage = lines[0][3:]
    if not lineage.startswith("/") or "//" in lineage or any(
        part in {"", ".", ".."} for part in lineage.split("/")[1:]
    ):
        _fail("process unified cgroup lineage is not canonical")
    return lineage


def _validate_unit_lineage(
    *,
    scenario: str,
    unit: str,
    lineage: str,
    expected_job_name: str | None = None,
    expected_job_cgroup: str | None = None,
) -> None:
    if scenario in _NATIVE_HOLD_SCENARIOS:
        if expected_job_name is None:
            _fail("native descendant adversary lacks its planned job cgroup name")
        job_name = _require_job_name(
            expected_job_name, label="expected_job_name"
        )
        suffix = f"/{unit}/{job_name}"
        if expected_job_cgroup is not None:
            job_cgroup = _require_cgroup(
                expected_job_cgroup, label="expected_job_cgroup"
            )
            if not job_cgroup.endswith(suffix):
                _fail("materialized job cgroup does not match the planned job name")
            if lineage != job_cgroup:
                _fail("native descendant adversary is outside the materialized job cgroup")
        elif not lineage.endswith(suffix):
            _fail("native descendant adversary is outside the planned job cgroup")
        return
    if expected_job_name is not None or expected_job_cgroup is not None:
        _fail("non-native adversary must not bind a job cgroup")
    if scenario == "h4-stoppost-failure":
        expected = f"/{unit}/.control"
        if not lineage.endswith(expected):
            _fail("H4 stop-post adversary is not in the planned unit .control")
        return
    if scenario in {"h9-failed-closer", "h10-gc-negative"}:
        if not lineage.endswith(f"/{unit}"):
            _fail("non-delegated adversary is not in the planned unit")
        return
    if not lineage.endswith(f"/{unit}/supervisor"):
        _fail("main adversary is not in the planned run service supervisor")


def _identity(
    *,
    require_stop_selector: bool = False,
    unit: str | None = None,
    scenario: str | None = None,
    expected_job_name: str | None = None,
    expected_job_cgroup: str | None = None,
) -> dict[str, Any]:
    pid = os.getpid()
    invocation = os.environ.get("INVOCATION_ID")
    if type(invocation) is not str or _INVOCATION_RE.fullmatch(invocation) is None:
        _fail("environment INVOCATION_ID is not canonical")
    environment: dict[str, str] = {}
    for name in ("SERVICE_RESULT", "EXIT_CODE", "EXIT_STATUS"):
        value = os.environ.get(name)
        if value is None:
            if require_stop_selector:
                _fail(f"stop-post scenario lacks environment {name}")
            continue
        decoded = _require_string(value, label=f"environment {name}")
        try:
            decoded.encode("ascii", "strict")
        except UnicodeError as exc:
            raise AdversaryError(f"environment {name} must be ASCII") from exc
        if _TOKEN_RE.fullmatch(decoded) is None:
            _fail(f"environment {name} is not one literal systemd token")
        environment[name] = decoded
    proc_cgroup_raw = _read_proc_text(
        Path(f"/proc/{pid}/cgroup"), label="process cgroup"
    )
    lineage = _unified_cgroup(proc_cgroup_raw)
    if require_stop_selector and not lineage.endswith("/.control"):
        _fail("H4 stop-post adversary is not executing in .control")
    if (unit is None) != (scenario is None):
        _fail("unit and scenario lineage bindings must be supplied together")
    if unit is not None and scenario is not None:
        _validate_unit_lineage(
            scenario=scenario,
            unit=unit,
            lineage=lineage,
            expected_job_name=expected_job_name,
            expected_job_cgroup=expected_job_cgroup,
        )
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
        "session_id": os.getsid(0),
        "starttime": _starttime(pid),
        "stop_selector_environment": environment,
        "unified_cgroup": lineage,
    }


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
        raise AdversaryError(f"receipt parent does not exist: {parent}") from exc
    if resolved_parent != parent or parent.is_symlink() or not parent.is_dir():
        _fail("receipt parent must be one canonical real directory")
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
        raise AdversaryError(f"refusing to replace an existing receipt: {path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _validate_fifo(path: Path) -> tuple[int, int]:
    try:
        identity = path.lstat()
    except OSError as exc:
        raise AdversaryError(f"cannot stat release FIFO: {path}") from exc
    if not stat.S_ISFIFO(identity.st_mode):
        _fail("release path must be one pre-created non-symlink FIFO")
    return identity.st_dev, identity.st_ino


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
        raise AdversaryError(f"cannot pin {label}: {path}") from exc
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
        raise AdversaryError(f"{label} path disappeared after rendezvous") from exc
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
            starttime=armed_payload["actor"]["starttime"],
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
        except AdversaryError:
            raise
        except OSError as exc:
            raise AdversaryError("cannot publish the ready FIFO token") from exc
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
        except AdversaryError:
            raise
        except OSError as exc:
            raise AdversaryError("cannot consume the release FIFO token") from exc
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


def _hold_for_release(path: Path, expected: tuple[int, int]) -> None:
    if _validate_fifo(path) != expected:
        _fail("release FIFO identity differs from the frozen receipt")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != expected or not stat.S_ISFIFO(opened.st_mode):
                _fail("release FIFO identity changed while opening")
            permit = _read_all_fd(descriptor)
        finally:
            os.close(descriptor)
    except AdversaryError:
        raise
    except OSError as exc:
        raise AdversaryError("cannot consume release FIFO permit") from exc
    if permit != RELEASE_BYTES:
        _fail("release FIFO did not carry the exact one-shot permit")


def _decode_request(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = _read_regular(path, label="adversary request")
    value = _decode_json(raw, label="adversary request")
    if type(value) is not dict or frozenset(value) != _REQUEST_KEYS:
        actual = frozenset(value) if type(value) is dict else frozenset()
        _fail(
            "adversary request schema mismatch: "
            f"missing={sorted(_REQUEST_KEYS - actual)!r}, "
            f"unknown={sorted(actual - _REQUEST_KEYS)!r}"
        )
    if _canonical_bytes(value) != raw:
        _fail("adversary request is not exact canonical JSON")
    if value["schema"] != REQUEST_SCHEMA:
        _fail("adversary request schema is not supported")
    scenario = _require_string(value["scenario"], label="scenario")
    if scenario not in _SCENARIOS:
        _fail("adversary scenario is not supported")
    _require_unit(value["unit"], label="unit")
    expected_invocation = _require_string(
        value["expected_invocation_id"], label="expected_invocation_id"
    )
    if _INVOCATION_RE.fullmatch(expected_invocation) is None:
        _fail("expected_invocation_id must be 32 lowercase hexadecimal characters")
    _require_path(value["receipt_path"], label="receipt_path")
    expected_job_name = value["expected_job_name"]
    expected_job_cgroup = value["expected_job_cgroup"]
    if scenario in _NATIVE_HOLD_SCENARIOS:
        job_name = _require_job_name(
            expected_job_name, label="expected_job_name"
        )
        job_cgroup = _require_cgroup(
            expected_job_cgroup, label="expected_job_cgroup"
        )
        if not job_cgroup.endswith(f"/{value['unit']}/{job_name}"):
            _fail("expected_job_cgroup does not match the request unit/job name")
    elif expected_job_name is not None or expected_job_cgroup is not None:
        _fail("non-native adversary request must not bind a job cgroup")
    fifo_value = value["hold_release_fifo"]
    if fifo_value is not None:
        if scenario not in _NATIVE_HOLD_SCENARIOS:
            _fail("only native descendant scenarios may bind a hold release FIFO")
        fifo = _decode_fifo(fifo_value, label="hold_release_fifo")
        if _validate_fifo(Path(fifo["path"])) != _fifo_identity(fifo):
            _fail("hold release FIFO identity differs from the materialized request")
    elif scenario in _NATIVE_HOLD_SCENARIOS:
        _fail("native descendant scenario requires its complete hold release FIFO")
    return value, raw


def _decode_acquisition(value: Any) -> dict[str, Any]:
    item = _require_exact_object(
        value, _ACQUISITION_KEYS, label="adversary acquisition"
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
    raw = _read_regular(path, label="adversary plan")
    plan = _require_exact_object(
        _decode_json(raw, label="adversary plan"), _PLAN_KEYS, label="adversary plan"
    )
    if _canonical_bytes(plan) != raw:
        _fail("adversary plan is not exact canonical JSON")
    if plan["schema"] != PLAN_SCHEMA:
        _fail("adversary plan schema is not supported")
    scenario = _require_string(plan["scenario"], label="scenario")
    if scenario not in _SCENARIOS:
        _fail("adversary plan scenario is not supported")
    unit = _require_unit(plan["unit"], label="unit")
    expected_job_name = plan["expected_job_name"]
    if scenario in _NATIVE_HOLD_SCENARIOS:
        expected_job_name = _require_job_name(
            expected_job_name, label="expected_job_name"
        )
    elif expected_job_name is not None:
        _fail("non-native adversary plan must not bind a job cgroup name")
    program_path = _require_path(plan["program_path"], label="program_path")
    program_sha256 = _require_sha256(
        plan["program_sha256"], label="program_sha256"
    )
    request_path = _require_path(plan["request_path"], label="request_path")
    receipt_path = _require_path(plan["receipt_path"], label="receipt_path")
    acquisition = (
        None if plan["acquisition"] is None else _decode_acquisition(plan["acquisition"])
    )
    hold_release = (
        None
        if plan["hold_release_fifo"] is None
        else _decode_fifo(plan["hold_release_fifo"], label="hold_release_fifo")
    )
    if scenario in _ACQUISITION_SCENARIOS:
        if acquisition is None or hold_release is not None:
            _fail("direct unit adversary requires acquisition and forbids hold FIFO")
    elif scenario in _NATIVE_HOLD_SCENARIOS:
        if acquisition is not None or hold_release is None:
            _fail("native descendant requires only its fixed hold release FIFO")
    elif acquisition is not None or hold_release is not None:
        _fail("non-handshake scenario must not bind a FIFO")

    reserved = {str(program_path), str(request_path), str(receipt_path)}
    if len(reserved) != 3:
        _fail("adversary program, request and receipt paths must be distinct")
    if acquisition is not None:
        acquisition_paths = {
            acquisition["armed_receipt_path"],
            acquisition["ready_fifo"]["path"],
            acquisition["release_fifo"]["path"],
        }
        if len(acquisition_paths) != 3 or reserved.intersection(acquisition_paths):
            _fail("adversary acquisition paths overlap another bound asset")
        reserved.update(acquisition_paths)
    if hold_release is not None:
        if hold_release["path"] in reserved:
            _fail("hold release FIFO path overlaps another bound asset")
        if acquisition is not None and _fifo_identity(hold_release) in {
            _fifo_identity(acquisition["ready_fifo"]),
            _fifo_identity(acquisition["release_fifo"]),
        }:
            _fail("hold and acquisition FIFO identities must not overlap")
        reserved.add(hold_release["path"])
    if str(path) in reserved:
        _fail("adversary plan path overlaps one of its bound assets")

    return {
        "schema": PLAN_SCHEMA,
        "scenario": scenario,
        "unit": unit,
        "expected_job_name": expected_job_name,
        "program_path": str(program_path),
        "program_sha256": program_sha256,
        "request_path": str(request_path),
        "receipt_path": str(receipt_path),
        "acquisition": acquisition,
        "hold_release_fifo": hold_release,
    }, raw


def _verify_program(plan: dict[str, Any]) -> dict[str, Any]:
    configured = Path(plan["program_path"])
    executed = Path(os.path.realpath(__file__))
    if configured != executed:
        _fail("executed adversary program differs from the plan path")
    raw = _read_regular(configured, label="adversary program")
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != plan["program_sha256"]:
        _fail("executed adversary program hash differs from the plan")
    identity = configured.lstat()
    if sys.version_info[:2] != (3, 12):
        _fail("formal adversary plan requires Python 3.12")
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        _fail("formal adversary plan requires Python -I -B")
    return {
        "path": str(executed),
        "sha256": actual_sha256,
        "identity": {
            "device": identity.st_dev,
            "inode": identity.st_ino,
            "mode": stat.S_IMODE(identity.st_mode),
        },
    }


def _materialize_request(
    plan: dict[str, Any], actor: dict[str, Any]
) -> dict[str, Any]:
    expected_job_name = plan["expected_job_name"]
    expected_job_cgroup: str | None = None
    if plan["scenario"] in _NATIVE_HOLD_SCENARIOS:
        _validate_unit_lineage(
            scenario=plan["scenario"],
            unit=plan["unit"],
            lineage=actor["unified_cgroup"],
            expected_job_name=expected_job_name,
        )
        expected_job_cgroup = actor["unified_cgroup"]
    elif expected_job_name is not None:
        _fail("non-native adversary plan must not materialize a job cgroup")
    return {
        "schema": REQUEST_SCHEMA,
        "scenario": plan["scenario"],
        "unit": plan["unit"],
        "expected_invocation_id": actor["invocation_id"],
        "expected_job_name": expected_job_name,
        "expected_job_cgroup": expected_job_cgroup,
        "receipt_path": plan["receipt_path"],
        "hold_release_fifo": plan["hold_release_fifo"],
    }


def _validate_formal_plan_binding(
    request_path: Path,
    request: dict[str, Any],
    request_raw: bytes,
    actor: dict[str, Any],
    acquisition: dict[str, Any] | None,
    value: Any,
) -> None:
    binding = _require_exact_object(
        value, _FORMAL_PLAN_BINDING_KEYS, label="adversary formal plan binding"
    )
    if binding["schema"] != PLAN_SCHEMA:
        _fail("adversary formal plan binding schema is not supported")
    plan_path = _require_path(
        binding["plan_path"], label="adversary formal plan binding plan_path"
    )
    plan_sha256 = _require_sha256(
        binding["plan_sha256"], label="adversary formal plan binding plan_sha256"
    )
    plan, plan_raw = _decode_plan(plan_path)
    if hashlib.sha256(plan_raw).hexdigest() != plan_sha256:
        _fail("adversary formal plan binding plan hash drifted")
    if str(request_path) != plan["request_path"]:
        _fail("adversary materialized request path differs from its sealed plan")
    if request["receipt_path"] != plan["receipt_path"]:
        _fail("adversary receipt path differs from its sealed plan")
    if request != _materialize_request(plan, actor):
        _fail("adversary materialized request differs from its sealed plan and actor")
    request_sha256 = hashlib.sha256(request_raw).hexdigest()
    expected_binding = {
        "schema": PLAN_SCHEMA,
        "scenario": plan["scenario"],
        "unit": plan["unit"],
        "expected_job_name": plan["expected_job_name"],
        "plan_path": str(plan_path),
        "plan_sha256": plan_sha256,
        "program": _verify_program(plan),
        "acquisition": plan["acquisition"],
        "hold_release_fifo": plan["hold_release_fifo"],
        "materialized_request_sha256": request_sha256,
    }
    if acquisition != plan["acquisition"] or binding != expected_binding:
        _fail("adversary formal binding differs from its plan/request/FIFO authority")


def _base_receipt(
    request: dict[str, Any],
    request_raw: bytes,
    request_path: Path,
    actor: dict[str, Any],
    release_handshake: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "actor": actor,
        "expected_invocation_id": request["expected_invocation_id"],
        "expected_job_name": request["expected_job_name"],
        "expected_job_cgroup": request["expected_job_cgroup"],
        "hold_release_fifo": request["hold_release_fifo"],
        "release_handshake": release_handshake,
        "request_path": str(request_path),
        "request_sha256": hashlib.sha256(request_raw).hexdigest(),
        "scenario": request["scenario"],
        "schema": RECEIPT_SCHEMA,
        "unit": request["unit"],
    }


def _after_acquisition_release(scenario: str) -> int:
    if scenario == "h7-guardian-hold":
        _fail("H7 must terminate through StopUnit; FIFO release is forbidden")
    if scenario == "h2-main-nonzero":
        return 23
    if scenario == "h3-main-signal":
        os.abort()
    if scenario == "h4-stoppost-failure":
        return 47
    if scenario == "h8-extra-topology-hold":
        return 0
    if scenario == "h9-failed-closer":
        return 61
    if scenario == "h10-gc-negative":
        return 29
    if scenario == "h11-unbounded-hold":
        return 0
    _fail("scenario has no released acquisition outcome")


def _write_pipe_json(descriptor: int, payload: dict[str, Any]) -> None:
    encoded = _canonical_bytes(payload)
    written = 0
    while written < len(encoded):
        count = os.write(descriptor, encoded[written:])
        if count <= 0:
            _fail("descendant fact pipe write made no progress")
        written += count


def _read_pipe_json(descriptor: int) -> dict[str, Any]:
    raw = _read_all_fd(descriptor)
    value = _decode_json(raw, label="descendant fact pipe")
    if type(value) is not dict or _canonical_bytes(value) != raw:
        _fail("descendant fact pipe is not one canonical object")
    if frozenset(value) != frozenset({"ok", "actor"}) or value["ok"] is not True:
        _fail("descendant did not establish its exact actor facts")
    actor = value["actor"]
    if type(actor) is not dict:
        _fail("descendant actor facts are not one object")
    return actor


def _child_report_and_hold(
    write_fd: int,
    fifo_path: Path,
    fifo_identity: tuple[int, int],
    *,
    close_stdio: bool,
    scenario: str,
    unit: str,
    expected_job_name: str,
    expected_job_cgroup: str,
) -> NoReturn:
    try:
        if close_stdio:
            for descriptor in (0, 1, 2):
                os.close(descriptor)
        actor = _identity(
            unit=unit,
            scenario=scenario,
            expected_job_name=expected_job_name,
            expected_job_cgroup=expected_job_cgroup,
        )
        _write_pipe_json(write_fd, {"actor": actor, "ok": True})
        os.close(write_fd)
        _hold_for_release(fifo_path, fifo_identity)
        os._exit(0)
    except BaseException:
        try:
            os.close(write_fd)
        except OSError:
            pass
        os._exit(125)


def _setsid_descendant(
    fifo_path: Path,
    fifo_identity: tuple[int, int],
    *,
    scenario: str,
    unit: str,
    expected_job_name: str,
    expected_job_cgroup: str,
) -> dict[str, Any]:
    read_fd, write_fd = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(read_fd)
        try:
            os.setsid()
        except BaseException:
            os.close(write_fd)
            os._exit(125)
        _child_report_and_hold(
            write_fd,
            fifo_path,
            fifo_identity,
            close_stdio=False,
            scenario=scenario,
            unit=unit,
            expected_job_name=expected_job_name,
            expected_job_cgroup=expected_job_cgroup,
        )
    os.close(write_fd)
    try:
        actor = _read_pipe_json(read_fd)
    finally:
        os.close(read_fd)
    if actor.get("pid") != child:
        _fail("setsid descendant facts do not match the returned child PID")
    return actor


def _double_fork_descendant(
    fifo_path: Path,
    fifo_identity: tuple[int, int],
    *,
    scenario: str,
    unit: str,
    expected_job_name: str,
    expected_job_cgroup: str,
) -> dict[str, Any]:
    read_fd, write_fd = os.pipe()
    intermediate = os.fork()
    if intermediate == 0:
        os.close(read_fd)
        try:
            os.setsid()
            grandchild = os.fork()
        except BaseException:
            os.close(write_fd)
            os._exit(125)
        if grandchild != 0:
            os.close(write_fd)
            os._exit(0)
        _child_report_and_hold(
            write_fd,
            fifo_path,
            fifo_identity,
            close_stdio=True,
            scenario=scenario,
            unit=unit,
            expected_job_name=expected_job_name,
            expected_job_cgroup=expected_job_cgroup,
        )
    os.close(write_fd)
    try:
        actor = _read_pipe_json(read_fd)
    finally:
        os.close(read_fd)
    if actor.get("pid") in {None, intermediate}:
        _fail("double-fork facts do not identify the independent grandchild")
    return actor


def run(
    request_path: Path,
    *,
    acquisition: dict[str, Any] | None = None,
    formal_plan_binding: dict[str, Any] | None = None,
    expected_release_identity: tuple[int, int] | None = None,
    expected_actor: dict[str, Any] | None = None,
    expected_unit: str | None = None,
) -> int:
    request, request_raw = _decode_request(request_path)
    scenario = request["scenario"]
    receipt_path = _require_path(request["receipt_path"], label="receipt_path")
    request_hold = request["hold_release_fifo"]
    fifo_path = None if request_hold is None else Path(request_hold["path"])
    release_handshake: dict[str, Any] | None = None
    fifo_identity: tuple[int, int] | None = None
    if fifo_path is not None:
        fifo_identity = _validate_fifo(fifo_path)
        if fifo_identity != _fifo_identity(request_hold):
            _fail("hold release FIFO identity differs from the request")
        if (
            expected_release_identity is not None
            and fifo_identity != expected_release_identity
        ):
            _fail("hold release FIFO identity differs from the formal plan")
        fifo_device, fifo_inode = fifo_identity
        release_handshake = {
            "device": fifo_device,
            "inode": fifo_inode,
            "path": str(fifo_path),
            "permit_sha256": hashlib.sha256(RELEASE_BYTES).hexdigest(),
        }
    actor = _identity(
        require_stop_selector=scenario == "h4-stoppost-failure",
        unit=request["unit"],
        scenario=scenario,
        expected_job_name=request["expected_job_name"],
        expected_job_cgroup=request["expected_job_cgroup"],
    )
    if actor["invocation_id"] != request["expected_invocation_id"]:
        _fail("adversary invocation differs from the materialized request")
    if expected_unit is not None and request["unit"] != expected_unit:
        _fail("adversary request unit differs from the formal plan")
    if expected_actor is not None and actor != expected_actor:
        _fail("adversary process identity changed after request materialization")
    if formal_plan_binding is not None:
        _validate_formal_plan_binding(
            request_path,
            request,
            request_raw,
            actor,
            acquisition,
            formal_plan_binding,
        )
    receipt = _base_receipt(
        request, request_raw, request_path, actor, release_handshake
    )
    if formal_plan_binding is not None:
        receipt["formal_plan_binding"] = formal_plan_binding

    if scenario == "h6-setsid-descendant":
        if fifo_path is None:
            _fail("setsid descendant scenario lost its release FIFO binding")
        if fifo_identity is None:
            _fail("setsid descendant scenario lost its release FIFO identity")
        receipt["descendant"] = _setsid_descendant(
            fifo_path,
            fifo_identity,
            scenario=scenario,
            unit=request["unit"],
            expected_job_name=request["expected_job_name"],
            expected_job_cgroup=request["expected_job_cgroup"],
        )
    elif scenario == "b7-double-fork-closed-stdio":
        if fifo_path is None:
            _fail("double-fork scenario lost its release FIFO binding")
        if fifo_identity is None:
            _fail("double-fork scenario lost its release FIFO identity")
        receipt["descendant"] = _double_fork_descendant(
            fifo_path,
            fifo_identity,
            scenario=scenario,
            unit=request["unit"],
            expected_job_name=request["expected_job_name"],
            expected_job_cgroup=request["expected_job_cgroup"],
        )
    else:
        receipt["descendant"] = None

    descendant = receipt["descendant"]
    if descendant is not None:
        if descendant.get("invocation_id") != request["expected_invocation_id"]:
            _fail("descendant invocation differs from the materialized request")
        if descendant.get("unified_cgroup") != request["expected_job_cgroup"]:
            _fail("descendant cgroup differs from the materialized request")

    published = False
    if acquisition is not None:
        if scenario not in _ACQUISITION_SCENARIOS:
            _fail("scenario may not execute the acquisition handshake")
        if expected_unit is None or formal_plan_binding is None:
            _fail("formal acquisition lacks its exact unit/plan binding")
        if (
            formal_plan_binding.get("unit") != expected_unit
            or formal_plan_binding.get("scenario") != scenario
        ):
            _fail("formal acquisition scenario/unit differs from its plan binding")
        if scenario in _PRE_ACQUISITION_RECEIPT_SCENARIOS:
            _publish_no_replace(receipt_path, receipt, starttime=actor["starttime"])
            published = True
        armed_payload = {
            "schema": ARMED_RECEIPT_SCHEMA,
            "scenario": scenario,
            "unit": expected_unit,
            "actor": actor,
            "plan_path": formal_plan_binding["plan_path"],
            "plan_sha256": formal_plan_binding["plan_sha256"],
            "program": formal_plan_binding["program"],
            "request_path": str(request_path),
            "request_sha256": hashlib.sha256(request_raw).hexdigest(),
            "receipt_path": str(receipt_path),
            "ready_fifo": acquisition["ready_fifo"],
            "release_fifo": acquisition["release_fifo"],
            "ready_sha256": hashlib.sha256(READY_BYTES).hexdigest(),
            "release_sha256": hashlib.sha256(RELEASE_BYTES).hexdigest(),
        }
        _perform_acquisition(acquisition, armed_payload=armed_payload)
        if _identity(
            require_stop_selector=scenario == "h4-stoppost-failure",
            unit=expected_unit,
            scenario=scenario,
            expected_job_name=request["expected_job_name"],
            expected_job_cgroup=request["expected_job_cgroup"],
        ) != actor:
            _fail("adversary process identity changed during acquisition")
        if scenario == "h9-failed-closer":
            _publish_no_replace(receipt_path, receipt, starttime=actor["starttime"])
            published = True
        return _after_acquisition_release(scenario)
    if not published:
        _publish_no_replace(receipt_path, receipt, starttime=actor["starttime"])

    if scenario == "h2-main-nonzero":
        return 23
    if scenario == "h3-main-signal":
        os.abort()
    if scenario == "h4-stoppost-failure":
        return 47
    if scenario == "h9-failed-closer":
        return 61
    if scenario == "h10-gc-negative":
        return 29
    if scenario in {"h6-setsid-descendant", "b7-double-fork-closed-stdio"}:
        return 0
    if fifo_path is None:
        _fail("hold scenario lost its release FIFO binding")
    if fifo_identity is None:
        _fail("hold scenario lost its release FIFO identity")
    _hold_for_release(fifo_path, fifo_identity)
    return 0


def _run_plan(plan_path: Path) -> int:
    plan, plan_raw = _decode_plan(plan_path)
    bound_paths = {
        plan["program_path"],
        plan["request_path"],
        plan["receipt_path"],
    }
    if plan["acquisition"] is not None:
        bound_paths.update(
            {
                plan["acquisition"]["armed_receipt_path"],
                plan["acquisition"]["ready_fifo"]["path"],
                plan["acquisition"]["release_fifo"]["path"],
            }
        )
    if plan["hold_release_fifo"] is not None:
        bound_paths.add(plan["hold_release_fifo"]["path"])
    if str(plan_path) in bound_paths:
        _fail("adversary plan path overlaps one of its bound assets")

    program = _verify_program(plan)
    hold_pin = -1
    hold_identity: tuple[int, int] | None = None
    try:
        if plan["hold_release_fifo"] is not None:
            hold_pin = _open_fifo_pin(
                plan["hold_release_fifo"], label="hold release FIFO"
            )
            hold_identity = _fifo_identity(plan["hold_release_fifo"])
        actor = _identity(
            require_stop_selector=plan["scenario"] == "h4-stoppost-failure",
            unit=plan["unit"],
            scenario=plan["scenario"],
            expected_job_name=plan["expected_job_name"],
        )
        request = _materialize_request(plan, actor)
        request_raw = _canonical_bytes(request)
        _publish_no_replace(
            Path(plan["request_path"]), request, starttime=actor["starttime"]
        )
        formal_plan_binding = {
            "schema": PLAN_SCHEMA,
            "scenario": plan["scenario"],
            "unit": plan["unit"],
            "expected_job_name": plan["expected_job_name"],
            "plan_path": str(plan_path),
            "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
            "program": program,
            "acquisition": plan["acquisition"],
            "hold_release_fifo": plan["hold_release_fifo"],
            "materialized_request_sha256": hashlib.sha256(request_raw).hexdigest(),
        }
        result = run(
            Path(plan["request_path"]),
            acquisition=plan["acquisition"],
            formal_plan_binding=formal_plan_binding,
            expected_release_identity=hold_identity,
            expected_actor=actor,
            expected_unit=plan["unit"],
        )
        if hold_pin >= 0:
            _revalidate_fifo_pin(
                hold_pin, plan["hold_release_fifo"], label="hold release FIFO"
            )
        return result
    finally:
        if hold_pin >= 0:
            os.close(hold_pin)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv if argv is None else argv
    if len(arguments) == 3 and arguments[1] == "--plan":
        return _run_plan(_require_path(arguments[2], label="plan path"))
    if len(arguments) != 2:
        raise SystemExit(
            "usage: generic_backend_adversary.py REQUEST.json or "
            "generic_backend_adversary.py --plan PLAN.json"
        )
    return run(_require_path(arguments[1], label="request path"))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AdversaryError as exc:
        print(f"generic backend adversary: {exc}", file=sys.stderr)
        raise SystemExit(125) from exc
