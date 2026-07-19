#!/usr/bin/python3.12
"""Tests-only delegated integration driver for the generic spawn backend.

The system-unit fixture executes this file with an installed Python 3.12
wheel using ``-I -B``.  Target processes are executed only through
``SpawnBackend`` and the accepted native blocked-child implementation.  This
file deliberately contains no alternate process launcher and no product wait
policy.

One invocation executes one B0--B8 case/variant from an exact JSON config.  A
receipt is canonical JSON created with no-replace semantics.  Cases whose
expected outcome is process fail-stop first create a separate armed receipt;
the outer system-unit observer owns the final fail-stop evidence.
"""

from __future__ import annotations

import base64
import errno
import fcntl
import hashlib
import inspect
import json
import os
import re
import signal
import stat
import struct
import sys
import termios
from enum import Enum
from types import ModuleType
from typing import Mapping, NoReturn, Sequence


_PLAN_SCHEMA = "scion.generic-backend.formal-plan.v1"
_PLAN_ROLE = "formal-case"
_SCHEMA = "scion.generic-backend-formal-case.v2"
_RECEIPT_SCHEMA = "scion.generic-backend-formal-receipt.v1"
_FORMAL_ARMED_SCHEMA = "scion.generic_backend.formal_run_armed.v1"
_FORMAL_ACTION_ARMED_SCHEMA = "scion.generic_backend.formal_action_armed.v1"
_B6_ARMED_SCHEMA = "scion.generic_backend.b6_armed.v1"
_B6_OPERATION_SCHEMA = "scion.generic-backend.b6-operation.v1"
_READY_BYTES = b"SCION_GENERIC_BACKEND_READY_V1\n"
_RELEASE_BYTES = b"SCION_GENERIC_BACKEND_RELEASE_V1\n"
_ACCEPTED_SPAWN_BACKEND_SHA256 = (
    "9c25defcf383046b39e0638f6f3841fca9c47572506a5cd4c3a9fb9c3232f938"
)
_EXPECTED_EXTENSION_SHA256 = (
    "3d747973bc2eb3b0f6fda68f288987c7b988820eb24df2ff617aa567071803fc"
)
_EXPECTED_PROBE_SHA256 = (
    "8e653a076dfd86d513f3ef4493058e124bde8af61b1c5afd4879ae07cc47c936"
)
_PLAN_FIELDS = frozenset(
    {
        "schema",
        "role",
        "fixture_uid",
        "fixture_gid",
        "case_id",
        "variant",
        "run_unit",
        "close_unit",
        "receipt_directory",
        "receipt_name",
        "armed_receipt_name",
        "capture_directory",
        "scratch_directory",
        "final_config_path",
        "boot_id_file",
        "run_configured_directives",
        "run_expanded_properties",
        "invocation_nonce",
        "ordinal",
        "formal_program",
        "case_script",
        "adversary_script",
        "accepted_probe",
        "accepted_extension",
        "accepted_spawn_backend",
        "systemd_acquisition",
        "descendant_adversary_plan",
        "control_fifo",
        "b6",
    }
)
_CONFIG_FIELDS = frozenset(
    {
        "schema",
        "case_id",
        "variant",
        "receipt_directory",
        "receipt_name",
        "armed_receipt_name",
        "capture_directory",
        "scratch_directory",
        "directory_authorities",
        "control_fifo",
        "run_unit",
        "close_unit",
        "run_configured_directives",
        "run_expanded_properties",
        "invocation_lineage",
        "invocation_nonce",
        "ordinal",
        "case_script",
        "adversary_script",
        "adversary_sha256",
        "accepted_probe",
        "accepted_extension",
        "accepted_probe_sha256",
        "accepted_extension_sha256",
        "accepted_spawn_backend_sha256",
        "systemd_acquisition",
        "systemd_armed_receipt_sha256",
        "descendant_adversary_plan",
        "plan_sha256",
        "b6",
    }
)
_DIRECTORY_AUTHORITY_NAMES = frozenset(
    {"receipt_directory", "capture_directory", "scratch_directory"}
)
_DIRECTORY_AUTHORITY_FIELDS = frozenset(
    {"path", "device", "inode", "mode", "uid", "gid"}
)
_FIFO_FIELDS = frozenset({"path", "device", "inode"})
_ACQUISITION_FIELDS = frozenset(
    {"armed_receipt_path", "ready_fifo", "release_fifo"}
)
_B6_ACQUISITION_FIELDS = _ACQUISITION_FIELDS | {"operation_receipt_path"}
_DESCENDANT_PLAN_FIELDS = frozenset(
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
_DESCENDANT_PLAN_SCHEMA = "scion.generic_backend.systemd_adversary_plan.v1"
_DESCENDANT_REQUEST_SCHEMA = "scion.generic_backend.systemd_adversary_request.v1"
_DESCENDANT_RECEIPT_SCHEMA = "scion.generic_backend.systemd_adversary_receipt.v1"
_DESCENDANT_REQUEST_FIELDS = frozenset(
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
_DESCENDANT_RECEIPT_FIELDS = frozenset(
    {
        "schema",
        "scenario",
        "unit",
        "actor",
        "expected_invocation_id",
        "expected_job_name",
        "expected_job_cgroup",
        "hold_release_fifo",
        "release_handshake",
        "request_path",
        "request_sha256",
        "descendant",
        "formal_plan_binding",
    }
)
_DESCENDANT_IDENTITY_FIELDS = frozenset(
    {
        "boot_id",
        "invocation_id",
        "pid",
        "proc_cgroup_raw",
        "session_id",
        "starttime",
        "stop_selector_environment",
        "unified_cgroup",
    }
)
_DESCENDANT_BINDING_FIELDS = frozenset(
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
_PROGRAM_RECEIPT_FIELDS = frozenset({"path", "sha256", "identity"})
_PROGRAM_IDENTITY_FIELDS = frozenset({"device", "inode", "mode"})
_EXTERNAL_B7_VARIANTS = frozenset(
    {
        "cgroup-inode-drift",
        "unexpected-sibling",
        "unexpected-nested",
        "supervisor-extra-task",
    }
)
_INTERNAL_B7_VARIANTS = frozenset(
    {"tmpfile-unsupported", "tmpfile-allocation", "tmpfile-open"}
)
_CASE_VARIANTS = {
    "B0": frozenset({"blocked-sentinel"}),
    "B1": frozenset({"clean", "nonzero", "signal", "core"}),
    "B2": frozenset({"wrong-executable", "wrong-cwd"}),
    "B3": frozenset({"dual-binary"}),
    "B4": frozenset({"release-after-job-kill"}),
    "B5": frozenset({"setsid-retain-stdio", "double-fork-close-stdio"}),
    "B6": frozenset(
        {
            "issuer-blocked",
            "issuer-just-released",
            "issuer-leader-terminal",
            "issuer-reaped-populated",
            "issuer-empty-before-eof",
            "storage-blocked",
            "storage-just-released",
            "storage-leader-terminal",
            "storage-reaped-populated",
            "storage-empty-before-eof",
            "close-blocked",
            "close-just-released",
            "close-leader-terminal",
            "close-reaped-populated",
            "close-empty-before-eof",
            "issuer-backend-open",
            "issuer-capture-prepare",
            "issuer-job-created-pre-native",
            "issuer-native-no-handle",
        }
    ),
    "B7": frozenset(
        {
            "tmpfile-unsupported",
            "tmpfile-allocation",
            "tmpfile-open",
            "cgroup-inode-drift",
            "unexpected-sibling",
            "unexpected-nested",
            "supervisor-extra-task",
        }
    ),
    "B8": frozenset({"final-inventory"}),
}

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_INVOCATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
_BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_UINT64_MAX = (1 << 64) - 1

_B6_PHASE_VARIANT = {
    "blocked": "blocked",
    "just-released": "just-released",
    "leader-terminal": "leader-terminal",
    "reaped-but-populated": "reaped-populated",
    "empty-before-eof": "empty-before-eof",
}
_B6_LIFECYCLE_EXPECTED_PHASE = {
    "blocked": "BLOCKED",
    "just-released": "RELEASED_DRAINING",
    "leader-terminal": "LEADER_TERMINAL",
    "reaped-but-populated": "LEADER_REAPED_DRAINING",
    "empty-before-eof": "LEADER_REAPED_DRAINING",
}
_B6_PREHANDLE_ABI = {
    "issuer-backend-open": {
        "fault": "issuer-signal",
        "phase": "backend-open",
        "hook": "service-consume",
        "target_operation": "ServiceCgroup._consume",
        "operation_ordinal": "1",
        "expected_fact_type": "BackendOpenFailure",
        "expected_phase": "SERVICE_CONSUME",
        "expected_reason": "ISSUER_INTERRUPTED",
    },
    "issuer-capture-prepare": {
        "fault": "issuer-signal",
        "phase": "capture-prepare",
        "hook": "capture-spool-open",
        "target_operation": "os.open(O_TMPFILE)",
        "operation_ordinal": "1",
        "expected_fact_type": "PreHandleFailure",
        "expected_phase": "CAPTURE_PREPARE",
        "expected_reason": "ISSUER_INTERRUPTED_PRE_HANDLE",
    },
    "issuer-job-created-pre-native": {
        "fault": "issuer-signal",
        "phase": "job-created-pre-native",
        "hook": "pre-native-borrow",
        "target_operation": "_JobCgroup._consume_spawn_dirfd_borrow",
        "operation_ordinal": "1",
        "expected_fact_type": "PreHandleFailure",
        "expected_phase": "PRE_NATIVE_READY",
        "expected_reason": "ISSUER_INTERRUPTED_PRE_HANDLE",
    },
    "issuer-native-no-handle": {
        "fault": "issuer-signal",
        "phase": "native-no-handle",
        "hook": "unobservable-source-seam",
        "target_operation": "native.spawn_blocked",
        "operation_ordinal": "1",
        "expected_fact_type": "PreHandleFailure",
        "expected_phase": "NATIVE_NO_HANDLE",
        "expected_reason": "ISSUER_INTERRUPTED_PRE_HANDLE",
    },
}


def _b6_lifecycle_abi() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    fault_specs = {
        "issuer": (
            "issuer-signal",
            "ISSUER_INTERRUPTED",
            "ContainedSpawnFailure",
        ),
        "storage": (
            "capture-storage",
            "CAPTURE_FAILED",
            "ContainedSpawnFailure",
        ),
        "close": (
            "authority-close",
            "AUTHORITY_CLOSE_UNCERTAIN",
            "FAILSTOP",
        ),
    }
    hook_by_fault_phase = {
        ("issuer", "blocked"): ("guard-restore", "_IssuerSignalGuard.restore", "10"),
        ("issuer", "just-released"): (
            "guard-restore",
            "_IssuerSignalGuard.restore",
            "11",
        ),
        ("issuer", "leader-terminal"): (
            "terminal-fact",
            "WaitFact.from_native",
            "1",
        ),
        ("issuer", "reaped-but-populated"): (
            "reaped-pidfd-close",
            "_close_exact(poll_pidfd)",
            "1",
        ),
        ("storage", "just-released"): (
            "capture-write",
            "_write_spool",
            "1",
        ),
    }
    for prefix, (fault, reason, fact_type) in fault_specs.items():
        for phase, variant_phase in _B6_PHASE_VARIANT.items():
            hook = hook_by_fault_phase.get((prefix, phase))
            if hook is None:
                hook = (
                    "unobservable-source-seam",
                    f"{fault}:{phase}",
                    "1",
                )
            hook_id, operation, ordinal = hook
            result[f"{prefix}-{variant_phase}"] = {
                "fault": fault,
                "phase": phase,
                "hook": hook_id,
                "target_operation": operation,
                "operation_ordinal": ordinal,
                "expected_fact_type": fact_type,
                "expected_phase": _B6_LIFECYCLE_EXPECTED_PHASE[phase],
                "expected_reason": reason,
            }
    return result


_B6_ABI = {**_B6_PREHANDLE_ABI, **_b6_lifecycle_abi()}
_B6_INSTALLABLE_HOOKS = frozenset(
    {
        "guard-restore",
        "service-consume",
        "capture-spool-open",
        "pre-native-borrow",
        "terminal-fact",
        "reaped-pidfd-close",
        "capture-write",
    }
)


class FixtureError(RuntimeError):
    """The tests-only fixture input or observed outcome is not acceptable."""


class RequirementMissing(FixtureError):
    """A required external static fixture is absent or not hash-pinned."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _duplicate_rejecting_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise FixtureError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise FixtureError(f"config contains non-finite JSON constant: {value!r}")


def _read_all(fd: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        try:
            chunk = os.read(fd, 64 * 1024)
        except InterruptedError:
            continue
        if chunk == b"":
            return b"".join(chunks)
        chunks.append(chunk)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        try:
            written = os.write(fd, view[offset:])
        except InterruptedError:
            continue
        if written <= 0:
            raise FixtureError("write made no progress")
        offset += written


def _open_regular_readonly(path: str) -> tuple[int, os.stat_result]:
    if type(path) is not str or not path.startswith("/"):
        raise FixtureError("fixture file path must be exact absolute text")
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    fd = -1
    try:
        fd = os.open(path, flags)
        status = os.fstat(fd)
    except OSError as exc:
        if fd >= 0:
            os.close(fd)
        raise FixtureError(f"cannot open exact fixture file: {path!r}") from exc
    if not stat.S_ISREG(status.st_mode):
        os.close(fd)
        raise FixtureError(f"fixture input is not regular: {path!r}")
    return fd, status


def _load_json_object(path: str, *, label: str) -> tuple[dict[str, object], bytes]:
    fd, _ = _open_regular_readonly(path)
    try:
        raw = _read_all(fd)
    finally:
        os.close(fd)
    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_json_constant,
        )
    except FixtureError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FixtureError(f"{label} must be exact UTF-8 JSON") from exc
    if type(value) is not dict:
        raise FixtureError(f"{label} root must be an exact object")
    if _canonical_json(value) != raw:
        raise FixtureError(f"{label} must be canonical JSON")
    return value, raw


def _load_config(path: str) -> tuple[dict[str, object], str]:
    _canonical_absolute_value(path, label="config path")
    value, raw = _load_json_object(path, label="config")
    actual = frozenset(value)
    if actual != _CONFIG_FIELDS:
        raise FixtureError(
            "config fields mismatch: "
            f"missing={sorted(_CONFIG_FIELDS - actual)!r}, "
            f"unknown={sorted(actual - _CONFIG_FIELDS)!r}"
        )
    _validate_config(value)
    return value, hashlib.sha256(raw).hexdigest()


def _exact_keys(value: object, expected: frozenset[str], *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise FixtureError(f"{label} must be an exact object")
    actual = frozenset(value)
    if actual != expected:
        raise FixtureError(
            f"{label} fields mismatch: missing={sorted(expected - actual)!r}, "
            f"unknown={sorted(actual - expected)!r}"
        )
    return value


def _text_value(value: object, *, label: str, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and value == ""):
        raise FixtureError(f"{label} must be exact nonempty text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise FixtureError(f"{label} must be strict UTF-8") from exc
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise FixtureError(f"{label} contains a forbidden control character")
    return value


def _canonical_absolute_value(value: object, *, label: str) -> str:
    path = _text_value(value, label=label)
    if (
        not path.startswith("/")
        or path == "/"
        or os.path.normpath(path) != path
        or "//" in path
    ):
        raise FixtureError(f"{label} must be one canonical non-root absolute path")
    return path


def _sha_value(value: object, *, label: str) -> str:
    text = _text_value(value, label=label)
    if _SHA256_RE.fullmatch(text) is None:
        raise FixtureError(f"{label} must be lowercase SHA-256")
    return text


def _uint_text_value(value: object, *, label: str, positive: bool = False) -> str:
    text = _text_value(value, label=label)
    if text == "0":
        number = 0
    elif text[0] in "123456789" and text.isascii() and text.isdecimal():
        number = int(text, 10)
    else:
        raise FixtureError(f"{label} must be canonical unsigned decimal")
    if number > _UINT64_MAX or (positive and number == 0):
        raise FixtureError(f"{label} is outside the accepted uint64 range")
    return text


def _static_reference(value: object, *, label: str) -> dict[str, object]:
    result = _exact_keys(value, frozenset({"path", "sha256"}), label=label)
    _canonical_absolute_value(result["path"], label=f"{label}.path")
    _sha_value(result["sha256"], label=f"{label}.sha256")
    return result


def _identity_reference(value: object, *, label: str) -> dict[str, object]:
    result = _exact_keys(
        value,
        frozenset({"path", "device", "inode"}),
        label=label,
    )
    _canonical_absolute_value(result["path"], label=f"{label}.path")
    _uint_text_value(result["device"], label=f"{label}.device", positive=True)
    _uint_text_value(result["inode"], label=f"{label}.inode", positive=True)
    return result


def _fifo_reference(value: object, *, label: str) -> dict[str, object]:
    result = _identity_reference(value, label=label)
    path = _canonical_absolute_value(result["path"], label=f"{label}.path")
    try:
        status = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise RequirementMissing("STATIC_FIFO", f"cannot stat {label}") from exc
    expected = (
        int(_uint_text_value(result["device"], label=f"{label}.device"), 10),
        int(_uint_text_value(result["inode"], label=f"{label}.inode"), 10),
    )
    if not stat.S_ISFIFO(status.st_mode) or (status.st_dev, status.st_ino) != expected:
        raise RequirementMissing("STATIC_FIFO_IDENTITY", f"{label} identity is not frozen FIFO")
    return result


def _require_sealed_fifo_authority(
    reference: Mapping[str, object],
    *,
    fixture_uid: int,
    fixture_gid: int,
    label: str,
) -> None:
    path = _canonical_absolute_value(reference["path"], label=f"{label}.path")
    try:
        status = os.stat(path, follow_symlinks=False)
        parent = os.stat(os.path.dirname(path), follow_symlinks=False)
    except OSError as exc:
        raise RequirementMissing(
            "SEALED_FIFO_AUTHORITY", f"cannot prove {label} ownership"
        ) from exc
    if (
        not stat.S_ISFIFO(status.st_mode)
        or stat.S_IMODE(status.st_mode) != 0o600
        or status.st_uid != fixture_uid
        or status.st_gid != fixture_gid
    ):
        raise RequirementMissing(
            "SEALED_FIFO_AUTHORITY",
            f"{label} must be mode 0600 and owned by the fixture credentials",
        )
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0:
        raise RequirementMissing(
            "SEALED_FIFO_PARENT", f"{label} parent must be one root-owned directory"
        )


def _validate_fifo_authorities(
    *,
    systemd_acquisition: Mapping[str, object],
    b6: object,
    control_fifo: Mapping[str, object] | None,
    fixture_uid: int,
    fixture_gid: int,
) -> None:
    references = [
        ("systemd_acquisition.ready_fifo", systemd_acquisition["ready_fifo"]),
        ("systemd_acquisition.release_fifo", systemd_acquisition["release_fifo"]),
    ]
    if control_fifo is not None:
        references.append(("control_fifo", control_fifo))
    if type(b6) is dict:
        acquisition = b6["acquisition"]
        references.extend(
            (
                ("b6.acquisition.ready_fifo", acquisition["ready_fifo"]),
                ("b6.acquisition.release_fifo", acquisition["release_fifo"]),
            )
        )
    for label, reference in references:
        _require_sealed_fifo_authority(
            reference,
            fixture_uid=fixture_uid,
            fixture_gid=fixture_gid,
            label=label,
        )


def _acquisition_reference(
    value: object,
    *,
    label: str,
    b6: bool = False,
) -> dict[str, object]:
    expected = _B6_ACQUISITION_FIELDS if b6 else _ACQUISITION_FIELDS
    result = _exact_keys(value, expected, label=label)
    armed = _canonical_absolute_value(
        result["armed_receipt_path"], label=f"{label}.armed_receipt_path"
    )
    ready = _fifo_reference(result["ready_fifo"], label=f"{label}.ready_fifo")
    release = _fifo_reference(
        result["release_fifo"], label=f"{label}.release_fifo"
    )
    paths = {armed, str(ready["path"]), str(release["path"])}
    if len(paths) != 3 or (ready["device"], ready["inode"]) == (
        release["device"],
        release["inode"],
    ):
        raise FixtureError(f"{label} paths and FIFO identities must be distinct")
    if b6:
        operation = _canonical_absolute_value(
            result["operation_receipt_path"],
            label=f"{label}.operation_receipt_path",
        )
        if operation in paths:
            raise FixtureError(f"{label} operation receipt overlaps another asset")
    return result


def _control_required(case_id: str, variant: str) -> bool:
    return (
        case_id in {"B4", "B5"}
        or (case_id == "B7" and variant in _EXTERNAL_B7_VARIANTS)
        or (case_id == "B6" and variant == "issuer-reaped-populated")
    )


def _descendant_required(case_id: str, variant: str) -> bool:
    return case_id == "B5" or (
        case_id == "B6" and variant == "issuer-reaped-populated"
    )


def _expected_descendant_scenario(case_id: str, variant: str) -> str:
    if case_id == "B5":
        return {
            "setsid-retain-stdio": "h6-setsid-descendant",
            "double-fork-close-stdio": "b7-double-fork-closed-stdio",
        }[variant]
    if case_id == "B6" and variant == "issuer-reaped-populated":
        return "b7-double-fork-closed-stdio"
    raise FixtureError("case/variant has no descendant adversary")


def _decode_descendant_plan_reference(
    value: object,
    *,
    case_id: str,
    variant: str,
    run_unit: str,
    invocation_nonce: str,
    ordinal: int,
    adversary: Mapping[str, object],
    control_fifo: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if not _descendant_required(case_id, variant):
        if value is not None:
            raise FixtureError("non-descendant case must set descendant_adversary_plan null")
        return None
    reference = _static_reference(value, label="descendant_adversary_plan")
    path = str(reference["path"])
    plan, raw = _load_json_object(path, label="descendant adversary plan")
    if hashlib.sha256(raw).hexdigest() != reference["sha256"]:
        raise RequirementMissing(
            "DESCENDANT_PLAN_HASH",
            "descendant adversary plan differs from its frozen hash",
        )
    _exact_keys(plan, _DESCENDANT_PLAN_FIELDS, label="descendant adversary plan")
    if plan["schema"] != _DESCENDANT_PLAN_SCHEMA:
        raise FixtureError("descendant adversary plan schema is not frozen")
    if plan["scenario"] != _expected_descendant_scenario(case_id, variant):
        raise FixtureError("descendant adversary scenario differs from case/variant")
    if plan["unit"] != run_unit:
        raise FixtureError("descendant adversary unit differs from formal run unit")
    expected_job_name = f"job-{ordinal}-{invocation_nonce[:16]}"
    if plan["expected_job_name"] != expected_job_name:
        raise FixtureError("descendant adversary job name differs from the frozen job key")
    if (
        plan["program_path"] != adversary["path"]
        or plan["program_sha256"] != adversary["sha256"]
    ):
        raise FixtureError("descendant adversary program binding drifted")
    for name in ("request_path", "receipt_path"):
        _canonical_absolute_value(plan[name], label=f"descendant adversary {name}")
    if plan["request_path"] == plan["receipt_path"]:
        raise FixtureError("descendant adversary request and receipt paths overlap")
    if plan["acquisition"] is not None:
        raise FixtureError("native descendant adversary must not own an acquisition")
    if control_fifo is None:
        raise FixtureError("descendant adversary lost its hold FIFO authority")
    hold = _fifo_reference(
        plan["hold_release_fifo"], label="descendant adversary hold_release_fifo"
    )
    if hold != dict(control_fifo):
        raise FixtureError("descendant adversary hold FIFO differs from formal authority")
    return reference


def _validate_asset_non_aliasing(
    *,
    receipt_directory: str,
    receipt_name: str,
    final_config_path: str | None,
    systemd_acquisition: Mapping[str, object],
    b6: object,
    control_fifo: Mapping[str, object] | None,
    action_armed_path: str | None,
    descendant_adversary_plan: object,
    plan_path: str | None = None,
    static_inputs: Mapping[str, str] | None = None,
    boot_id_file: Mapping[str, object] | None = None,
    authority_directories: Mapping[str, str] | None = None,
    require_outputs_absent: bool = False,
) -> None:
    paths: dict[str, str] = {}
    identities: dict[tuple[int, int], str] = {}
    input_paths: dict[str, str] = {}
    directory_paths: dict[str, str] = {}
    output_paths: dict[str, str] = {}

    def add_path(
        label: str, value: object, *, identity_label: str | None = None
    ) -> None:
        path = _canonical_absolute_value(value, label=label)
        previous = paths.get(path)
        if previous is not None:
            raise FixtureError(
                f"formal asset paths overlap: {previous} and {label}"
            )
        paths[path] = label
        if os.path.lexists(path):
            add_existing_identity(identity_label or label, path)

    def add_existing_identity(label: str, path: str) -> None:
        status = os.lstat(path)
        identity = (status.st_dev, status.st_ino)
        previous = identities.get(identity)
        if previous is not None:
            raise FixtureError(
                f"formal asset identities overlap: {previous} and {label}"
            )
        identities[identity] = label

    def add_input(label: str, value: object) -> None:
        path = _canonical_absolute_value(value, label=label)
        add_path(label, path)
        input_paths[label] = path

    def add_directory(label: str, value: object) -> None:
        path = _canonical_absolute_value(value, label=label)
        add_path(label, path)
        directory_paths[label] = path

    def add_output(label: str, value: object) -> None:
        path = _canonical_absolute_value(value, label=label)
        add_path(label, path)
        output_paths[label] = path

    def add_fifo(label: str, value: object) -> None:
        reference = _fifo_reference(value, label=label)
        add_path(f"{label}.path", reference["path"], identity_label=label)
        identity = (int(str(reference["device"]), 10), int(str(reference["inode"]), 10))
        previous = identities.get(identity)
        if previous is not None and previous != label:
            raise FixtureError(
                f"formal asset identities overlap: {previous} and {label}"
            )
        identities[identity] = label

    if plan_path is not None:
        add_input("formal plan", plan_path)
    if static_inputs is not None:
        for label, path in static_inputs.items():
            add_input(label, path)
    if boot_id_file is not None:
        boot = _identity_reference(boot_id_file, label="boot_id_file")
        add_input("boot_id_file", boot["path"])
    if authority_directories is not None:
        for label, path in authority_directories.items():
            add_directory(label, path)

    add_output("final receipt", os.path.join(receipt_directory, receipt_name))
    if final_config_path is not None:
        add_output("final_config_path", final_config_path)
    add_output(
        "systemd_acquisition.armed_receipt_path",
        systemd_acquisition["armed_receipt_path"],
    )
    add_fifo("systemd_acquisition.ready_fifo", systemd_acquisition["ready_fifo"])
    add_fifo(
        "systemd_acquisition.release_fifo", systemd_acquisition["release_fifo"]
    )
    if action_armed_path is not None:
        add_output("formal action armed receipt", action_armed_path)
    if control_fifo is not None:
        add_fifo("control_fifo", control_fifo)
    if type(b6) is dict:
        acquisition = b6["acquisition"]
        add_output(
            "b6.acquisition.armed_receipt_path", acquisition["armed_receipt_path"]
        )
        add_output(
            "b6.acquisition.operation_receipt_path",
            acquisition["operation_receipt_path"],
        )
        add_fifo("b6.acquisition.ready_fifo", acquisition["ready_fifo"])
        add_fifo("b6.acquisition.release_fifo", acquisition["release_fifo"])
    if descendant_adversary_plan is not None:
        reference = _static_reference(
            descendant_adversary_plan, label="descendant_adversary_plan"
        )
        add_input("descendant adversary plan", reference["path"])
        plan, _ = _load_json_object(
            str(reference["path"]), label="descendant adversary plan"
        )
        _exact_keys(plan, _DESCENDANT_PLAN_FIELDS, label="descendant adversary plan")
        add_output("descendant adversary request", plan["request_path"])
        add_output("descendant adversary receipt", plan["receipt_path"])

    def nested(first: str, second: str) -> bool:
        common = os.path.commonpath((first, second))
        return common == first or common == second

    directory_items = tuple(directory_paths.items())
    for index, (first_label, first_path) in enumerate(directory_items):
        for second_label, second_path in directory_items[index + 1 :]:
            if nested(first_path, second_path):
                raise FixtureError(
                    "formal authority directories are nested: "
                    f"{first_label} and {second_label}"
                )
    for input_label, input_path in input_paths.items():
        for directory_label, directory_path in directory_items:
            if nested(input_path, directory_path):
                raise FixtureError(
                    "formal static/input asset and authority directory are nested: "
                    f"{input_label} and {directory_label}"
                )
    if require_outputs_absent:
        for label, path in output_paths.items():
            if os.path.lexists(path):
                raise FixtureError(
                    f"formal dynamic output exists before acquisition: {label}"
                )


def _property_object(value: object, *, label: str) -> dict[str, object]:
    result = value if type(value) is dict else None
    if result is None:
        raise FixtureError(f"{label} must be an exact object")
    for key, item in result.items():
        _text_value(key, label=f"{label} key")
        _text_value(item, label=f"{label}.{key}", allow_empty=True)
    return result


def _validate_b6_plan(
    value: object,
    *,
    case_id: str,
    variant: str,
) -> dict[str, object] | None:
    if case_id != "B6":
        if value is not None:
            raise FixtureError("non-B6 plan must set b6 to null")
        return None
    b6 = _exact_keys(
        value,
        frozenset(
            {
                "fault",
                "phase",
                "hook",
                "target_operation",
                "operation_ordinal",
                "expected_fact_type",
                "expected_phase",
                "expected_reason",
                "acquisition",
            }
        ),
        label="b6",
    )
    expected = _B6_ABI.get(variant)
    if expected is None:
        raise FixtureError("B6 variant has no frozen fault/phase ABI")
    for key, expected_value in expected.items():
        if _text_value(b6[key], label=f"b6.{key}") != expected_value:
            raise FixtureError(f"b6.{key} differs from the frozen ABI")
    _uint_text_value(b6["operation_ordinal"], label="b6.operation_ordinal", positive=True)
    _acquisition_reference(b6["acquisition"], label="b6.acquisition", b6=True)
    return b6


def _exact_text(config: Mapping[str, object], name: str, *, nonempty: bool = True) -> str:
    value = config[name]
    if type(value) is not str or (nonempty and value == ""):
        raise FixtureError(f"{name} must be exact nonempty text")
    if "\x00" in value:
        raise FixtureError(f"{name} contains NUL")
    return value


def _absolute_text(config: Mapping[str, object], name: str) -> str:
    value = _exact_text(config, name)
    return _canonical_absolute_value(value, label=name)


def _lower_sha(config: Mapping[str, object], name: str) -> str:
    value = _exact_text(config, name)
    return _sha_value(value, label=name)


def _receipt_component(config: Mapping[str, object], name: str) -> str:
    value = _exact_text(config, name)
    if value in {".", ".."} or "/" in value or not value.endswith(".json"):
        raise FixtureError(f"{name} must be one .json name component")
    return value


def _string_pairs(config: Mapping[str, object], name: str) -> tuple[tuple[str, str], ...]:
    value = config[name]
    if type(value) is not dict:
        raise FixtureError(f"{name} must be an exact object")
    pairs: list[tuple[str, str]] = []
    for key, item in value.items():
        if type(key) is not str or type(item) is not str:
            raise FixtureError(f"{name} keys and values must be exact text")
        pairs.append((key, item))
    return tuple(pairs)


def _validate_config(config: Mapping[str, object]) -> None:
    if _exact_text(config, "schema") != _SCHEMA:
        raise FixtureError("unknown config schema")
    case_id = _exact_text(config, "case_id")
    variant = _exact_text(config, "variant")
    if case_id not in _CASE_VARIANTS or variant not in _CASE_VARIANTS[case_id]:
        raise FixtureError("case_id/variant is outside the frozen B0-B8 matrix")
    for name in (
        "receipt_directory",
        "capture_directory",
        "scratch_directory",
        "case_script",
        "adversary_script",
        "accepted_probe",
        "accepted_extension",
    ):
        _absolute_text(config, name)
    _revalidate_directory_authorities(config)
    systemd_acquisition = _acquisition_reference(
        config["systemd_acquisition"], label="systemd_acquisition"
    )
    _sha_value(
        config["systemd_armed_receipt_sha256"],
        label="systemd_armed_receipt_sha256",
    )
    control_fifo = config["control_fifo"]
    if control_fifo is not None:
        control_fifo = _fifo_reference(control_fifo, label="control_fifo")
    _receipt_component(config, "receipt_name")
    _receipt_component(config, "armed_receipt_name")
    if config["receipt_name"] == config["armed_receipt_name"]:
        raise FixtureError("final and armed receipt names must differ")
    for name in (
        "invocation_nonce",
        "adversary_sha256",
        "accepted_probe_sha256",
        "accepted_extension_sha256",
        "accepted_spawn_backend_sha256",
        "plan_sha256",
    ):
        _lower_sha(config, name)
    if config["accepted_probe_sha256"] != _EXPECTED_PROBE_SHA256:
        raise FixtureError("config does not name the frozen accepted probe hash")
    if config["accepted_extension_sha256"] != _EXPECTED_EXTENSION_SHA256:
        raise FixtureError("config does not name the frozen accepted extension hash")
    if config["accepted_spawn_backend_sha256"] != _ACCEPTED_SPAWN_BACKEND_SHA256:
        raise FixtureError("config does not name the frozen accepted backend source hash")
    ordinal = config["ordinal"]
    if type(ordinal) is not int or not 0 <= ordinal <= (1 << 64) - 1:
        raise FixtureError("ordinal must be an exact uint64")
    for name in (
        "run_unit",
        "close_unit",
    ):
        _exact_text(config, name)
    _string_pairs(config, "run_configured_directives")
    _string_pairs(config, "run_expanded_properties")
    _string_pairs(config, "invocation_lineage")
    _validate_b6_plan(
        config["b6"],
        case_id=case_id,
        variant=variant,
    )
    if _control_required(case_id, variant) != (control_fifo is not None):
        raise FixtureError("control_fifo presence differs from case ownership")
    adversary = {
        "path": _absolute_text(config, "adversary_script"),
        "sha256": _lower_sha(config, "adversary_sha256"),
    }
    _decode_descendant_plan_reference(
        config["descendant_adversary_plan"],
        case_id=case_id,
        variant=variant,
        run_unit=_exact_text(config, "run_unit"),
        invocation_nonce=_lower_sha(config, "invocation_nonce"),
        ordinal=ordinal,
        adversary=adversary,
        control_fifo=control_fifo,
    )
    _validate_asset_non_aliasing(
        receipt_directory=_absolute_text(config, "receipt_directory"),
        receipt_name=_receipt_component(config, "receipt_name"),
        final_config_path=None,
        systemd_acquisition=systemd_acquisition,
        b6=config["b6"],
        control_fifo=control_fifo,
        action_armed_path=(
            os.path.join(
                _absolute_text(config, "receipt_directory"),
                _receipt_component(config, "armed_receipt_name"),
            )
            if case_id == "B4"
            or (case_id == "B7" and variant in _EXTERNAL_B7_VARIANTS)
            else None
        ),
        descendant_adversary_plan=config["descendant_adversary_plan"],
    )
    case_output_paths = [
        os.path.join(
            _absolute_text(config, "receipt_directory"),
            _receipt_component(config, "receipt_name"),
        )
    ]
    if case_id == "B4" or (case_id == "B7" and variant in _EXTERNAL_B7_VARIANTS):
        case_output_paths.append(
            os.path.join(
                _absolute_text(config, "receipt_directory"),
                _receipt_component(config, "armed_receipt_name"),
            )
        )
    if type(config["b6"]) is dict:
        acquisition = config["b6"]["acquisition"]
        case_output_paths.extend(
            (
                str(acquisition["armed_receipt_path"]),
                str(acquisition["operation_receipt_path"]),
            )
        )
    if config["descendant_adversary_plan"] is not None:
        reference = _static_reference(
            config["descendant_adversary_plan"], label="descendant_adversary_plan"
        )
        descendant_plan, _ = _load_json_object(
            str(reference["path"]), label="descendant adversary plan"
        )
        case_output_paths.extend(
            (str(descendant_plan["request_path"]), str(descendant_plan["receipt_path"]))
        )
    for path in case_output_paths:
        _assert_absent(path)
    _validate_fifo_authorities(
        systemd_acquisition=systemd_acquisition,
        b6=config["b6"],
        control_fifo=control_fifo,
        fixture_uid=os.getuid(),
        fixture_gid=os.getgid(),
    )


def _validate_plan(plan: Mapping[str, object], *, plan_path: str | None = None) -> None:
    if frozenset(plan) != _PLAN_FIELDS:
        actual = frozenset(plan)
        raise FixtureError(
            "plan fields mismatch: "
            f"missing={sorted(_PLAN_FIELDS - actual)!r}, "
            f"unknown={sorted(actual - _PLAN_FIELDS)!r}"
        )
    if _text_value(plan["schema"], label="schema") != _PLAN_SCHEMA:
        raise FixtureError("unknown formal plan schema")
    if _text_value(plan["role"], label="role") != _PLAN_ROLE:
        raise FixtureError("formal plan role is not formal-case")
    uid = int(_uint_text_value(plan["fixture_uid"], label="fixture_uid"), 10)
    gid = int(_uint_text_value(plan["fixture_gid"], label="fixture_gid"), 10)
    if uid != os.getuid() or gid != os.getgid():
        raise RequirementMissing(
            "FIXTURE_CREDENTIALS",
            "formal plan fixture uid/gid differ from the current same-PID actor",
        )
    case_id = _text_value(plan["case_id"], label="case_id")
    variant = _text_value(plan["variant"], label="variant")
    if case_id not in _CASE_VARIANTS or variant not in _CASE_VARIANTS[case_id]:
        raise FixtureError("plan case_id/variant is outside the frozen B0-B8 matrix")
    for name in (
        "run_unit",
        "close_unit",
        "receipt_name",
        "armed_receipt_name",
    ):
        _text_value(plan[name], label=name)
    if plan["run_unit"] == plan["close_unit"]:
        raise FixtureError("run_unit and close_unit must differ")
    if plan["receipt_name"] == plan["armed_receipt_name"]:
        raise FixtureError("final and armed receipt names must differ")
    for name in ("receipt_name", "armed_receipt_name"):
        value = _text_value(plan[name], label=name)
        if value in {".", ".."} or "/" in value or not value.endswith(".json"):
            raise FixtureError(f"{name} must be one .json name component")
    for name in (
        "receipt_directory",
        "capture_directory",
        "scratch_directory",
        "final_config_path",
    ):
        _canonical_absolute_value(plan[name], label=name)
    _freeze_directory_authorities(plan)
    _sha_value(plan["invocation_nonce"], label="invocation_nonce")
    _uint_text_value(plan["ordinal"], label="ordinal")
    _property_object(plan["run_configured_directives"], label="run_configured_directives")
    _property_object(plan["run_expanded_properties"], label="run_expanded_properties")
    from scion.runtime.execution import ConfiguredUnitProperties, UnitRole

    ConfiguredUnitProperties.from_receipts(
        UnitRole.RUN,
        plan["run_configured_directives"],
        plan["run_expanded_properties"],
        expected_unit=str(plan["run_unit"]),
        expected_peer=str(plan["close_unit"]),
    )
    static = {
        name: _static_reference(plan[name], label=name)
        for name in (
            "formal_program",
            "case_script",
            "adversary_script",
            "accepted_probe",
            "accepted_extension",
            "accepted_spawn_backend",
        )
    }
    if static["formal_program"] != static["case_script"]:
        raise FixtureError("formal_program and case_script must name one exact program")
    if static["formal_program"]["path"] != os.path.realpath(__file__):
        raise FixtureError("formal plan does not name the executing program")
    if static["accepted_probe"]["sha256"] != _EXPECTED_PROBE_SHA256:
        raise FixtureError("plan accepted probe hash is not frozen")
    if static["accepted_extension"]["sha256"] != _EXPECTED_EXTENSION_SHA256:
        raise FixtureError("plan accepted extension hash is not frozen")
    if static["accepted_spawn_backend"]["sha256"] != _ACCEPTED_SPAWN_BACKEND_SHA256:
        raise FixtureError("plan accepted backend source hash is not frozen")
    for name, reference in static.items():
        path = str(reference["path"])
        if _sha256_file(path) != reference["sha256"]:
            raise RequirementMissing(
                "STATIC_HASH_MISMATCH",
                f"{name} does not match its frozen static hash",
            )
    boot = _identity_reference(plan["boot_id_file"], label="boot_id_file")
    boot_path = str(boot["path"])
    boot_fd, boot_status = _open_regular_readonly(boot_path)
    os.close(boot_fd)
    if (str(boot_status.st_dev), str(boot_status.st_ino)) != (
        boot["device"],
        boot["inode"],
    ):
        raise RequirementMissing("BOOT_ID_IDENTITY", "boot-id file identity drifted")
    systemd_acquisition = _acquisition_reference(
        plan["systemd_acquisition"], label="systemd_acquisition"
    )
    control = plan["control_fifo"]
    if control is not None:
        control = _fifo_reference(control, label="control_fifo")
    if _control_required(case_id, variant) != (control is not None):
        raise FixtureError("control_fifo presence differs from case ownership")
    _validate_b6_plan(
        plan["b6"],
        case_id=case_id,
        variant=variant,
    )
    _decode_descendant_plan_reference(
        plan["descendant_adversary_plan"],
        case_id=case_id,
        variant=variant,
        run_unit=str(plan["run_unit"]),
        invocation_nonce=str(plan["invocation_nonce"]),
        ordinal=int(str(plan["ordinal"]), 10),
        adversary=static["adversary_script"],
        control_fifo=control,
    )
    _validate_asset_non_aliasing(
        receipt_directory=str(plan["receipt_directory"]),
        receipt_name=str(plan["receipt_name"]),
        final_config_path=str(plan["final_config_path"]),
        systemd_acquisition=systemd_acquisition,
        b6=plan["b6"],
        control_fifo=control,
        action_armed_path=(
            os.path.join(
                str(plan["receipt_directory"]), str(plan["armed_receipt_name"])
            )
            if case_id == "B4"
            or (case_id == "B7" and variant in _EXTERNAL_B7_VARIANTS)
            else None
        ),
        descendant_adversary_plan=plan["descendant_adversary_plan"],
        plan_path=plan_path,
        static_inputs={
            "formal_program/case_script": str(static["formal_program"]["path"]),
            "adversary_script": str(static["adversary_script"]["path"]),
            "accepted_probe": str(static["accepted_probe"]["path"]),
            "accepted_extension": str(static["accepted_extension"]["path"]),
            "accepted_spawn_backend": str(static["accepted_spawn_backend"]["path"]),
        },
        boot_id_file=boot,
        authority_directories={
            "receipt_directory": str(plan["receipt_directory"]),
            "capture_directory": str(plan["capture_directory"]),
            "scratch_directory": str(plan["scratch_directory"]),
        },
        require_outputs_absent=True,
    )
    _validate_fifo_authorities(
        systemd_acquisition=systemd_acquisition,
        b6=plan["b6"],
        control_fifo=control,
        fixture_uid=uid,
        fixture_gid=gid,
    )
    final_config = str(plan["final_config_path"])
    if os.path.dirname(final_config) != str(plan["scratch_directory"]):
        raise FixtureError("final_config_path must be directly owned by scratch_directory")


def _load_plan(path: str) -> tuple[dict[str, object], str]:
    _canonical_absolute_value(path, label="plan path")
    value, raw = _load_json_object(path, label="formal plan")
    _validate_plan(value, plan_path=path)
    return value, hashlib.sha256(raw).hexdigest()


def _sha256_file(path: str) -> str:
    fd, _ = _open_regular_readonly(path)
    digest = hashlib.sha256()
    try:
        while True:
            try:
                chunk = os.read(fd, 1024 * 1024)
            except InterruptedError:
                continue
            if chunk == b"":
                return digest.hexdigest()
            digest.update(chunk)
    finally:
        os.close(fd)


def _require_directory(path: str) -> os.stat_result:
    status = os.stat(path, follow_symlinks=False)
    if not stat.S_ISDIR(status.st_mode):
        raise FixtureError(f"required directory is not exact directory: {path!r}")
    return status


def _freeze_directory_authorities(
    values: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for name in sorted(_DIRECTORY_AUTHORITY_NAMES):
        path = _canonical_absolute_value(values[name], label=name)
        status = _require_directory(path)
        result[name] = {
            "path": path,
            "device": status.st_dev,
            "inode": status.st_ino,
            "mode": stat.S_IMODE(status.st_mode),
            "uid": status.st_uid,
            "gid": status.st_gid,
        }
    return result


def _revalidate_directory_authorities(
    values: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    raw = values.get("directory_authorities")
    authorities = _exact_keys(
        raw, _DIRECTORY_AUTHORITY_NAMES, label="directory_authorities"
    )
    result: dict[str, dict[str, object]] = {}
    for name in sorted(_DIRECTORY_AUTHORITY_NAMES):
        authority = _exact_keys(
            authorities[name],
            _DIRECTORY_AUTHORITY_FIELDS,
            label=f"directory_authorities.{name}",
        )
        path = _canonical_absolute_value(authority["path"], label=f"{name}.path")
        if path != _canonical_absolute_value(values[name], label=name):
            raise FixtureError(f"{name} path differs from its frozen authority")
        for field in ("device", "inode", "mode", "uid", "gid"):
            if type(authority[field]) is not int or authority[field] < 0:
                raise FixtureError(f"{name}.{field} must be one nonnegative integer")
        status = _require_directory(path)
        observed = {
            "path": path,
            "device": status.st_dev,
            "inode": status.st_ino,
            "mode": stat.S_IMODE(status.st_mode),
            "uid": status.st_uid,
            "gid": status.st_gid,
        }
        if authority != observed:
            raise FixtureError(f"{name} identity/mode/ownership drifted")
        result[name] = observed
    return result


def _encode_json(value: object) -> object:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is bytes:
        return {
            "encoding": "base64",
            "sha256": hashlib.sha256(value).hexdigest(),
            "byte_length": len(value),
            "data": base64.b64encode(value).decode("ascii"),
        }
    if isinstance(value, Enum):
        return value.value
    if type(value) in (tuple, list):
        return [_encode_json(item) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise FixtureError("receipt mapping has a non-text key")
        return {key: _encode_json(item) for key, item in value.items()}
    mapper = getattr(value, "to_mapping", None)
    if callable(mapper):
        return {
            "fact_type": type(value).__name__,
            "fields": _encode_json(mapper()),
        }
    raise FixtureError(f"receipt cannot encode {type(value).__name__}")


def _canonical_json(value: Mapping[str, object]) -> bytes:
    encoded = _encode_json(dict(value))
    return (
        json.dumps(
            encoded,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


def _publish_bytes_no_replace(directory: str, name: str, raw: bytes) -> str:
    if not name or name in {".", ".."} or "/" in name:
        raise FixtureError("published name must be one exact component")
    directory_fd = os.open(
        directory,
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
    )
    fd = -1
    temporary = f".{name}.pending-{os.getpid()}-{_proc_starttime(os.getpid())}"
    try:
        fd = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_fd,
        )
        _write_all(fd, raw)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.fsync(directory_fd)
        os.link(
            temporary,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        os.fsync(directory_fd)
        os.unlink(temporary, dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        os.close(directory_fd)
    return hashlib.sha256(raw).hexdigest()


def _write_receipt(directory: str, name: str, receipt: Mapping[str, object]) -> str:
    raw = _canonical_json(receipt)
    digest = _publish_bytes_no_replace(directory, name, raw)
    _write_all(1, f"SCION_FORMAL_RECEIPT {name} {digest}\n".encode("ascii"))
    return digest


def _write_static_json_no_replace(path: str, value: Mapping[str, object]) -> str:
    parent, name = os.path.split(path)
    if not parent or not name or name in {".", ".."}:
        raise FixtureError("static JSON path must contain one absolute leaf name")
    raw = _canonical_json(value)
    return _publish_bytes_no_replace(parent, name, raw)


def _proc_starttime(pid: int) -> int:
    with open(f"/proc/{pid}/stat", "rb", buffering=0) as source:
        raw = source.read()
    marker = raw.rfind(b")")
    fields = raw[marker + 2 :].split()
    if marker < 0 or len(fields) <= 19 or not fields[19].isdigit():
        raise FixtureError("malformed /proc stat")
    return int(fields[19], 10)


def _current_invocation_id() -> str:
    value = os.environ.get("INVOCATION_ID")
    if type(value) is not str or _INVOCATION_ID_RE.fullmatch(value) is None:
        raise RequirementMissing(
            "CURRENT_INVOCATION_ID",
            "same-PID formal entry lacks one canonical INVOCATION_ID",
        )
    return value


def _read_pinned_boot_id(plan: Mapping[str, object]) -> str:
    reference = _identity_reference(plan["boot_id_file"], label="boot_id_file")
    fd, status = _open_regular_readonly(str(reference["path"]))
    try:
        raw = _read_all(fd)
    finally:
        os.close(fd)
    if (str(status.st_dev), str(status.st_ino)) != (
        reference["device"],
        reference["inode"],
    ):
        raise RequirementMissing("BOOT_ID_IDENTITY", "boot-id identity changed")
    try:
        value = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise FixtureError("boot-id file is not canonical ASCII") from exc
    if not value.endswith("\n") or value.count("\n") != 1:
        raise FixtureError("boot-id file must contain one newline-terminated UUID")
    boot_id = value[:-1]
    if _BOOT_ID_RE.fullmatch(boot_id) is None:
        raise FixtureError("boot-id file does not contain a canonical lowercase UUID")
    return boot_id


def _derive_same_pid_lineage(plan: Mapping[str, object]) -> dict[str, str]:
    pid = os.getpid()
    before_starttime = _proc_starttime(pid)
    invocation_id = _current_invocation_id()
    raw = _read_bytes("/proc/self/cgroup")
    matches = [line[3:] for line in raw.splitlines() if line.startswith(b"0::")]
    if len(matches) != 1:
        raise FixtureError("formal entry lacks one unified cgroup lineage")
    try:
        current = matches[0].decode("ascii", "strict")
    except UnicodeError as exc:
        raise FixtureError("current cgroup lineage is not canonical ASCII") from exc
    components = current.split("/")[1:]
    if (
        not current.startswith("/")
        or current.endswith("/")
        or len(components) < 2
        or components[-1] != "supervisor"
        or any(not item or item in {".", ".."} or "/" in item for item in components)
    ):
        raise RequirementMissing(
            "CURRENT_DELEGATED_LINEAGE",
            "formal entry is not the same-PID actor in a supervisor leaf",
        )
    service_control_group = "/" + "/".join(components[:-1])
    if components[-2] != plan["run_unit"]:
        raise FixtureError("current service cgroup leaf differs from run_unit")
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0)
    )
    root_fd = cursor_fd = service_fd = supervisor_fd = -1
    try:
        root_fd = os.open("/sys/fs/cgroup", flags)
        cursor_fd = root_fd
        for component in components[:-1]:
            next_fd = os.open(component, flags, dir_fd=cursor_fd)
            if cursor_fd != root_fd:
                os.close(cursor_fd)
            cursor_fd = next_fd
        service_fd = cursor_fd
        cursor_fd = -1
        supervisor_fd = os.open("supervisor", flags, dir_fd=service_fd)
        service_status = os.fstat(service_fd)
        supervisor_status = os.fstat(supervisor_fd)
    except OSError as exc:
        raise RequirementMissing(
            "CURRENT_CGROUP_AUTHORITY",
            "cannot pin current service/supervisor cgroup identities",
        ) from exc
    finally:
        if supervisor_fd >= 0:
            os.close(supervisor_fd)
        if service_fd >= 0:
            os.close(service_fd)
        if cursor_fd >= 0 and cursor_fd != root_fd:
            os.close(cursor_fd)
        if root_fd >= 0:
            os.close(root_fd)
    after_starttime = _proc_starttime(pid)
    if before_starttime != after_starttime or invocation_id != _current_invocation_id():
        raise FixtureError("same-PID dynamic identity changed during materialization")
    return {
        "BootID": _read_pinned_boot_id(plan),
        "Id": str(plan["run_unit"]),
        "InvocationID": invocation_id,
        "ControlGroup": service_control_group,
        "ServiceDevice": str(service_status.st_dev),
        "ServiceInode": str(service_status.st_ino),
        "SupervisorDevice": str(supervisor_status.st_dev),
        "SupervisorInode": str(supervisor_status.st_ino),
        "MainPID": str(pid),
        "MainStartTime": str(before_starttime),
    }


def _formal_process_identity(
    plan: Mapping[str, object], lineage: Mapping[str, str]
) -> dict[str, object]:
    raw = _read_bytes("/proc/self/cgroup")
    try:
        proc_cgroup_raw = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise FixtureError("formal /proc/self/cgroup is not exact ASCII") from exc
    matches = [line[3:] for line in proc_cgroup_raw.splitlines() if line.startswith("0::")]
    if matches != [str(lineage["ControlGroup"]) + "/supervisor"]:
        raise FixtureError("formal actor cgroup differs from materialized lineage")
    return {
        "boot_id": str(lineage["BootID"]),
        "invocation_id": str(lineage["InvocationID"]),
        "pid": int(lineage["MainPID"], 10),
        "proc_cgroup_raw": proc_cgroup_raw,
        "starttime": int(lineage["MainStartTime"], 10),
        "unified_cgroup": matches[0],
        "service_control_group": str(lineage["ControlGroup"]),
        "service_device": int(lineage["ServiceDevice"], 10),
        "service_inode": int(lineage["ServiceInode"], 10),
        "supervisor_device": int(lineage["SupervisorDevice"], 10),
        "supervisor_inode": int(lineage["SupervisorInode"], 10),
    }


def _program_receipt(reference: Mapping[str, object]) -> dict[str, object]:
    path = str(reference["path"])
    fd, status = _open_regular_readonly(path)
    os.close(fd)
    if _sha256_file(path) != reference["sha256"]:
        raise RequirementMissing(
            "FORMAL_PROGRAM_HASH", "executing formal program hash drifted"
        )
    return {
        "path": path,
        "sha256": str(reference["sha256"]),
        "identity": {
            "device": status.st_dev,
            "inode": status.st_ino,
            "mode": stat.S_IMODE(status.st_mode),
        },
    }


def _perform_systemd_acquisition(
    plan: Mapping[str, object],
    *,
    plan_path: str,
    plan_sha256: str,
    lineage: Mapping[str, str],
) -> str:
    acquisition = _acquisition_reference(
        plan["systemd_acquisition"], label="systemd_acquisition"
    )
    before = _formal_process_identity(plan, lineage)
    program = _program_receipt(
        _static_reference(plan["formal_program"], label="formal_program")
    )
    receipt = {
        "schema": _FORMAL_ARMED_SCHEMA,
        "case_id": str(plan["case_id"]),
        "variant": str(plan["variant"]),
        "unit": str(plan["run_unit"]),
        "process_identity": before,
        "plan_path": plan_path,
        "plan_sha256": plan_sha256,
        "program": program,
        "final_config_path": str(plan["final_config_path"]),
        "ready_fifo": acquisition["ready_fifo"],
        "release_fifo": acquisition["release_fifo"],
        "ready_sha256": hashlib.sha256(_READY_BYTES).hexdigest(),
        "release_sha256": hashlib.sha256(_RELEASE_BYTES).hexdigest(),
    }
    armed_sha256 = _write_static_json_no_replace(
        str(acquisition["armed_receipt_path"]), receipt
    )
    ready_path, ready_identity = _fifo_tuple(acquisition["ready_fifo"])
    ready_fd = os.open(
        ready_path,
        os.O_WRONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        _require_open_fifo_identity(ready_fd, ready_identity, label="formal ready FIFO")
        _write_all(ready_fd, _READY_BYTES)
    finally:
        os.close(ready_fd)
    release_path, release_identity = _fifo_tuple(acquisition["release_fifo"])
    release_fd = os.open(
        release_path,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        _require_open_fifo_identity(
            release_fd, release_identity, label="formal release FIFO"
        )
        release = _read_all(release_fd)
    finally:
        os.close(release_fd)
    if release != _RELEASE_BYTES:
        raise FixtureError("formal release FIFO lacks exact permit followed by EOF")
    after_lineage = _derive_same_pid_lineage(plan)
    after = _formal_process_identity(plan, after_lineage)
    if after_lineage != dict(lineage) or after != before:
        raise FixtureError("formal same-PID authority changed across outer acquisition")
    _acquisition_reference(plan["systemd_acquisition"], label="systemd_acquisition")
    if _sha256_file(plan_path) != plan_sha256:
        raise FixtureError("formal plan hash changed across outer acquisition")
    if _program_receipt(
        _static_reference(plan["formal_program"], label="formal_program")
    ) != program:
        raise FixtureError("formal program identity changed across outer acquisition")
    return armed_sha256


def _materialized_config(
    plan: Mapping[str, object],
    *,
    plan_sha256: str,
    invocation_lineage: Mapping[str, str],
    systemd_armed_receipt_sha256: str,
    directory_authorities: Mapping[str, object] | None = None,
) -> dict[str, object]:
    static = {
        name: _static_reference(plan[name], label=name)
        for name in (
            "case_script",
            "adversary_script",
            "accepted_probe",
            "accepted_extension",
            "accepted_spawn_backend",
        )
    }
    control = plan["control_fifo"]
    frozen_directories = (
        _freeze_directory_authorities(plan)
        if directory_authorities is None
        else dict(directory_authorities)
    )
    return {
        "accepted_extension": static["accepted_extension"]["path"],
        "accepted_extension_sha256": static["accepted_extension"]["sha256"],
        "accepted_probe": static["accepted_probe"]["path"],
        "accepted_probe_sha256": static["accepted_probe"]["sha256"],
        "accepted_spawn_backend_sha256": static["accepted_spawn_backend"]["sha256"],
        "adversary_script": static["adversary_script"]["path"],
        "adversary_sha256": static["adversary_script"]["sha256"],
        "armed_receipt_name": plan["armed_receipt_name"],
        "b6": plan["b6"],
        "capture_directory": plan["capture_directory"],
        "case_id": plan["case_id"],
        "case_script": static["case_script"]["path"],
        "close_unit": plan["close_unit"],
        "control_fifo": dict(control) if type(control) is dict else None,
        "descendant_adversary_plan": (
            dict(plan["descendant_adversary_plan"])
            if type(plan["descendant_adversary_plan"]) is dict
            else None
        ),
        "directory_authorities": frozen_directories,
        "invocation_lineage": dict(invocation_lineage),
        "invocation_nonce": plan["invocation_nonce"],
        "ordinal": int(str(plan["ordinal"]), 10),
        "plan_sha256": plan_sha256,
        "receipt_directory": plan["receipt_directory"],
        "receipt_name": plan["receipt_name"],
        "run_configured_directives": dict(plan["run_configured_directives"]),
        "run_expanded_properties": dict(plan["run_expanded_properties"]),
        "run_unit": plan["run_unit"],
        "schema": _SCHEMA,
        "scratch_directory": plan["scratch_directory"],
        "systemd_acquisition": dict(plan["systemd_acquisition"]),
        "systemd_armed_receipt_sha256": systemd_armed_receipt_sha256,
        "variant": plan["variant"],
    }


def _execute_plan(plan_path: str) -> int:
    plan, plan_sha256 = _load_plan(plan_path)
    directory_authorities = _freeze_directory_authorities(plan)
    lineage = _derive_same_pid_lineage(plan)
    _revalidate_directory_authorities(
        {**plan, "directory_authorities": directory_authorities}
    )
    systemd_armed_receipt_sha256 = _perform_systemd_acquisition(
        plan,
        plan_path=plan_path,
        plan_sha256=plan_sha256,
        lineage=lineage,
    )
    _revalidate_directory_authorities(
        {**plan, "directory_authorities": directory_authorities}
    )
    config = _materialized_config(
        plan,
        plan_sha256=plan_sha256,
        invocation_lineage=lineage,
        systemd_armed_receipt_sha256=systemd_armed_receipt_sha256,
        directory_authorities=directory_authorities,
    )
    _validate_config(config)
    config_path = str(plan["final_config_path"])
    config_sha256 = _write_static_json_no_replace(config_path, config)
    if _sha256_file(config_path) != config_sha256:
        raise FixtureError("materialized config hash changed after publication")
    if (
        int(lineage["MainPID"], 10) != os.getpid()
        or int(lineage["MainStartTime"], 10) != _proc_starttime(os.getpid())
        or lineage["InvocationID"] != _current_invocation_id()
    ):
        raise FixtureError("same-PID dynamic identity changed before B entry")
    return _execute_case(config_path)


def _fd_inventory() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for name in sorted(os.listdir("/proc/self/fd"), key=int):
        fd = int(name, 10)
        try:
            status = os.fstat(fd)
            descriptor_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
            status_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            target = os.readlink(f"/proc/self/fd/{fd}")
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                continue
            raise
        result.append(
            {
                "fd": fd,
                "fd_flags": descriptor_flags,
                "status_flags": status_flags,
                "device": status.st_dev,
                "inode": status.st_ino,
                "mode": status.st_mode,
                "target": target,
            }
        )
    return result


def _task_inventory() -> list[dict[str, int]]:
    result = []
    for name in sorted(os.listdir("/proc/self/task"), key=int):
        task = int(name, 10)
        result.append({"tid": task, "starttime": _proc_starttime(task)})
    return result


def _read_bytes(path: str) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0))
    try:
        return _read_all(fd)
    finally:
        os.close(fd)


def _current_unified_cgroup() -> str:
    lines = _read_bytes("/proc/self/cgroup").splitlines()
    matches = [line[3:] for line in lines if line.startswith(b"0::")]
    if len(matches) != 1:
        raise FixtureError("current process lacks one unified cgroup")
    return matches[0].decode("ascii", "strict")


def _cgroup_inventory(control_group: str) -> dict[str, object]:
    root = "/sys/fs/cgroup" + control_group
    directories: list[dict[str, object]] = []
    pending = [root]
    while pending:
        current = pending.pop()
        status = os.stat(current, follow_symlinks=False)
        children = []
        with os.scandir(current) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    children.append(entry.name)
        children.sort()
        pending.extend(os.path.join(current, child) for child in reversed(children))
        item: dict[str, object] = {
            "relative": current.removeprefix(root) or ".",
            "device": status.st_dev,
            "inode": status.st_ino,
            "children": children,
        }
        for control in ("cgroup.procs", "cgroup.events", "cgroup.controllers"):
            candidate = os.path.join(current, control)
            try:
                item[control] = _read_bytes(candidate)
            except FileNotFoundError:
                item[control] = None
        directories.append(item)
    directories.sort(key=lambda item: str(item["relative"]))
    return {"control_group": control_group, "directories": directories}


def _inventory(control_group: str) -> dict[str, object]:
    return {
        "fds": _fd_inventory(),
        "tasks": _task_inventory(),
        "current_unified_cgroup": _current_unified_cgroup(),
        "cgroups": _cgroup_inventory(control_group),
    }


def _require_final_inventory(
    execution: ModuleType,
    baseline: Mapping[str, object],
    final: Mapping[str, object],
    result: Mapping[str, object],
) -> dict[str, object]:
    fd_returned = final["fds"] == baseline["fds"]
    task_returned = final["tasks"] == baseline["tasks"]
    if not fd_returned or not task_returned:
        raise FixtureError("final FD/task inventory did not return to baseline")

    failure = result.get("failure")
    if type(failure) is execution.ContainedSpawnFailure:
        identity = failure.cgroup_identity
        baseline_tree = baseline["cgroups"]
        final_tree = final["cgroups"]
        if type(baseline_tree) is not dict or type(final_tree) is not dict:
            raise FixtureError("cgroup inventory is not exact mapping evidence")
        baseline_directories = baseline_tree["directories"]
        final_directories = final_tree["directories"]
        baseline_root = next(
            item for item in baseline_directories if item["relative"] == "."
        )
        final_root = next(item for item in final_directories if item["relative"] == ".")
        expected_children = sorted([*baseline_root["children"], identity.job_name])
        if final_root["children"] != expected_children:
            raise FixtureError("failed job is not the sole retained cgroup")
        job_relative = "/" + identity.job_name
        matches = [
            item for item in final_directories if item["relative"] == job_relative
        ]
        if len(matches) != 1:
            raise FixtureError("retained failed-job cgroup is absent or duplicated")
        job = matches[0]
        if (
            job["device"] != identity.job_device
            or job["inode"] != identity.job_inode
            or job["children"] != []
            or job["cgroup.procs"] != b""
        ):
            raise FixtureError("retained failed-job cgroup identity/topology mismatch")
        events = execution.CgroupEventsFact.decode(job["cgroup.events"])
        if events.populated != 0 or events.frozen != 0:
            raise FixtureError("retained failed-job cgroup is not empty and thawed")
        cgroup_proof = {
            "kind": "EXACT_RETAINED_FAILED_JOB",
            "identity": identity,
            "events": events,
        }
    else:
        if final["cgroups"] != baseline["cgroups"]:
            raise FixtureError("non-contained final cgroup inventory differs from baseline")
        cgroup_proof = {"kind": "RETURNED_TO_BASELINE"}
    return {
        "fd_returned_to_baseline": fd_returned,
        "task_returned_to_baseline": task_returned,
        "cgroup_proof": cgroup_proof,
    }


def _fixture_identity(config: Mapping[str, object], config_sha256: str) -> dict[str, object]:
    script = os.path.realpath(__file__)
    configured_script = _absolute_text(config, "case_script")
    if script != configured_script:
        raise FixtureError("executed case script identity differs from config")
    if sys.version_info[:2] != (3, 12):
        raise FixtureError("formal case requires Python 3.12")
    if sys.flags.isolated != 1 or sys.flags.dont_write_bytecode != 1:
        raise FixtureError("formal case requires Python -I -B")
    probe = _absolute_text(config, "accepted_probe")
    probe_sha256 = _sha256_file(probe)
    if probe_sha256 != _EXPECTED_PROBE_SHA256:
        raise FixtureError("accepted native probe hash mismatch")

    from scion.runtime.native import _spawn_into_cgroup as native_extension
    from scion.runtime.execution import spawn_backend as backend_implementation

    extension_path = os.path.realpath(str(native_extension.__file__))
    configured_extension = _absolute_text(config, "accepted_extension")
    if extension_path != configured_extension:
        raise FixtureError("imported native extension path differs from config")
    extension_sha256 = _sha256_file(extension_path)
    if extension_sha256 != _EXPECTED_EXTENSION_SHA256:
        raise FixtureError("accepted native extension hash mismatch")
    backend_path = os.path.realpath(str(backend_implementation.__file__))
    backend_sha256 = _sha256_file(backend_path)
    if backend_sha256 != _ACCEPTED_SPAWN_BACKEND_SHA256:
        raise FixtureError("accepted spawn backend source hash mismatch")
    return {
        "config_sha256": config_sha256,
        "case_script": script,
        "case_script_sha256": _sha256_file(script),
        "python_executable": os.path.realpath(sys.executable),
        "python_version": list(sys.version_info[:3]),
        "isolated": sys.flags.isolated,
        "dont_write_bytecode": sys.flags.dont_write_bytecode,
        "native_extension": extension_path,
        "native_extension_sha256": extension_sha256,
        "spawn_backend": backend_path,
        "spawn_backend_sha256": backend_sha256,
        "accepted_probe": probe,
        "accepted_probe_sha256": probe_sha256,
    }


def _helper_argv(config: Mapping[str, object], mode: str, *arguments: str) -> tuple[bytes, ...]:
    executable = os.fsencode(os.path.realpath(sys.executable))
    script = os.fsencode(_absolute_text(config, "case_script"))
    return (
        executable,
        b"-I",
        b"-B",
        script,
        b"--helper",
        mode.encode("ascii"),
        *(os.fsencode(argument) for argument in arguments),
    )


def _descendant_adversary_argv(
    config: Mapping[str, object], expected_scenario: str
) -> tuple[tuple[bytes, ...], dict[str, object], str, str]:
    script = _absolute_text(config, "adversary_script")
    try:
        actual = _sha256_file(script)
    except FixtureError as exc:
        raise RequirementMissing(
            "STATIC_ADVERSARY_ASSET",
            "generic_backend_adversary.py is required as one static regular file"
        ) from exc
    expected = _lower_sha(config, "adversary_sha256")
    if actual != expected:
        raise RequirementMissing(
            "STATIC_ADVERSARY_HASH",
            "generic_backend_adversary.py is required with the configured exact hash"
        )
    reference = config["descendant_adversary_plan"]
    if type(reference) is not dict:
        raise FixtureError("descendant case lacks its sealed adversary plan")
    plan, raw = _load_json_object(
        _canonical_absolute_value(reference["path"], label="descendant_adversary_plan.path"),
        label="descendant adversary plan",
    )
    _exact_keys(plan, _DESCENDANT_PLAN_FIELDS, label="descendant adversary plan")
    plan_sha256 = hashlib.sha256(raw).hexdigest()
    if plan_sha256 != _sha_value(
        reference["sha256"], label="descendant_adversary_plan.sha256"
    ):
        raise RequirementMissing(
            "DESCENDANT_PLAN_HASH", "sealed descendant adversary plan hash drifted"
        )
    expected_job_name = (
        f"job-{config['ordinal']}-{_lower_sha(config, 'invocation_nonce')[:16]}"
    )
    if (
        plan["schema"] != _DESCENDANT_PLAN_SCHEMA
        or plan["scenario"] != expected_scenario
        or plan["unit"] != config["run_unit"]
        or plan["expected_job_name"] != expected_job_name
        or plan["program_path"] != script
        or plan["program_sha256"] != expected
        or plan["acquisition"] is not None
        or plan["hold_release_fifo"] != config["control_fifo"]
    ):
        raise FixtureError("sealed descendant adversary plan binding drifted")
    request_path = _canonical_absolute_value(
        plan["request_path"], label="descendant adversary request_path"
    )
    receipt_path = _canonical_absolute_value(
        plan["receipt_path"], label="descendant adversary receipt_path"
    )
    if request_path == receipt_path:
        raise FixtureError("descendant adversary request and receipt paths overlap")
    for path in (request_path, receipt_path):
        _assert_absent(path)
    executable = os.fsencode(os.path.realpath(sys.executable))
    return (
        (
            executable,
            b"-I",
            b"-B",
            os.fsencode(script),
            b"--plan",
            os.fsencode(str(reference["path"])),
        ),
        plan,
        receipt_path,
        plan_sha256,
    )


def _validate_descendant_identity(
    value: object,
    *,
    label: str,
    boot_id: str,
    invocation_id: str,
    expected_job_cgroup: str,
) -> dict[str, object]:
    identity = _exact_keys(value, _DESCENDANT_IDENTITY_FIELDS, label=label)
    if (
        identity["boot_id"] != boot_id
        or identity["invocation_id"] != invocation_id
        or identity["unified_cgroup"] != expected_job_cgroup
        or identity["proc_cgroup_raw"] != f"0::{expected_job_cgroup}\n"
        or identity["stop_selector_environment"] != {}
    ):
        raise FixtureError(f"{label} is outside the exact invocation/job cgroup")
    for name in ("pid", "session_id", "starttime"):
        value = identity[name]
        if type(value) is not int or value <= 0 or value > (1 << 64) - 1:
            raise FixtureError(f"{label}.{name} must be a positive uint64")
    return identity


def _validate_descendant_receipt(
    config: Mapping[str, object],
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    receipt_path: str,
    invocation_id: str,
    boot_id: str,
    blocked_process: Mapping[str, int],
    expected_job_cgroup: str,
    process_spec_sha256: str,
    process_spec: Mapping[str, object],
    require_live_descendant: bool,
) -> dict[str, object]:
    request, request_raw = _load_json_object(
        str(plan["request_path"]), label="descendant adversary request"
    )
    receipt, receipt_raw = _load_json_object(
        receipt_path, label="descendant adversary receipt"
    )
    _exact_keys(request, _DESCENDANT_REQUEST_FIELDS, label="descendant adversary request")
    _exact_keys(receipt, _DESCENDANT_RECEIPT_FIELDS, label="descendant adversary receipt")
    request_sha256 = hashlib.sha256(request_raw).hexdigest()
    control = _control_fifo_reference(config)
    expected_job_name = expected_job_cgroup.rsplit("/", 1)[-1]
    if expected_job_name != plan["expected_job_name"]:
        raise FixtureError("blocked job cgroup name differs from sealed adversary plan")
    expected_request = {
        "schema": _DESCENDANT_REQUEST_SCHEMA,
        "scenario": plan["scenario"],
        "unit": plan["unit"],
        "expected_invocation_id": invocation_id,
        "expected_job_name": expected_job_name,
        "expected_job_cgroup": expected_job_cgroup,
        "receipt_path": plan["receipt_path"],
        "hold_release_fifo": control,
    }
    if request != expected_request:
        raise FixtureError("materialized descendant request differs from sealed authority")
    if (
        receipt["schema"] != _DESCENDANT_RECEIPT_SCHEMA
        or receipt["scenario"] != plan["scenario"]
        or receipt["unit"] != plan["unit"]
        or receipt["expected_invocation_id"] != invocation_id
        or receipt["expected_job_name"] != expected_job_name
        or receipt["expected_job_cgroup"] != expected_job_cgroup
        or receipt["hold_release_fifo"] != control
        or receipt["request_path"] != plan["request_path"]
        or receipt["request_sha256"] != request_sha256
    ):
        raise FixtureError("descendant adversary receipt is not bound to its request")
    binding = _exact_keys(
        receipt["formal_plan_binding"],
        _DESCENDANT_BINDING_FIELDS,
        label="descendant formal plan binding",
    )
    program = _exact_keys(
        binding["program"], _PROGRAM_RECEIPT_FIELDS, label="descendant program"
    )
    program_identity = _exact_keys(
        program["identity"],
        _PROGRAM_IDENTITY_FIELDS,
        label="descendant program identity",
    )
    program_status = os.lstat(str(plan["program_path"]))
    expected_program_identity = {
        "device": program_status.st_dev,
        "inode": program_status.st_ino,
        "mode": stat.S_IMODE(program_status.st_mode),
    }
    if program_identity != expected_program_identity or program != {
        "path": plan["program_path"],
        "sha256": plan["program_sha256"],
        "identity": expected_program_identity,
    }:
        raise FixtureError("descendant executed program identity differs from plan")
    expected_binding = {
        "schema": _DESCENDANT_PLAN_SCHEMA,
        "scenario": plan["scenario"],
        "unit": plan["unit"],
        "expected_job_name": expected_job_name,
        "plan_path": config["descendant_adversary_plan"]["path"],
        "plan_sha256": plan_sha256,
        "program": program,
        "acquisition": None,
        "hold_release_fifo": control,
        "materialized_request_sha256": request_sha256,
    }
    if binding != expected_binding:
        raise FixtureError("descendant formal plan binding is incomplete")
    actor = _validate_descendant_identity(
        receipt["actor"],
        label="descendant leader actor",
        boot_id=boot_id,
        invocation_id=invocation_id,
        expected_job_cgroup=expected_job_cgroup,
    )
    if (
        actor["pid"] != blocked_process["pid"]
        or actor["starttime"] != blocked_process["starttime"]
    ):
        raise FixtureError("descendant leader actor is not the blocked native process")
    descendant = _validate_descendant_identity(
        receipt["descendant"],
        label="descendant actor",
        boot_id=boot_id,
        invocation_id=invocation_id,
        expected_job_cgroup=expected_job_cgroup,
    )
    if descendant["pid"] == actor["pid"]:
        raise FixtureError("descendant actor aliases the blocked native leader")
    if require_live_descendant:
        try:
            descendant_pid = int(descendant["pid"])
            live_starttime = _proc_starttime(descendant_pid)
            live_cgroup = _child_cgroup(descendant_pid)
            live_session_id = os.getsid(descendant_pid)
        except (FileNotFoundError, ProcessLookupError) as exc:
            raise RequirementMissing(
                "B6_DESCENDANT_LIVENESS",
                "reaped-populated descendant is not live at the guarded seam",
            ) from exc
        if (
            live_starttime != descendant["starttime"]
            or live_cgroup != expected_job_cgroup
            or live_session_id != descendant["session_id"]
        ):
            raise RequirementMissing(
                "B6_DESCENDANT_IDENTITY",
                "reaped-populated descendant identity/session/cgroup drifted",
            )
        try:
            live_program_sha256 = _sha256_file(str(plan["program_path"]))
        except FixtureError as exc:
            raise RequirementMissing(
                "B6_DESCENDANT_PROGRAM",
                "reaped-populated descendant program is no longer readable",
            ) from exc
        if live_program_sha256 != plan["program_sha256"]:
            raise RequirementMissing(
                "B6_DESCENDANT_PROGRAM",
                "reaped-populated descendant program hash drifted",
            )
    handshake = _exact_keys(
        receipt["release_handshake"],
        frozenset({"device", "inode", "path", "permit_sha256"}),
        label="descendant release handshake",
    )
    if handshake != {
        "device": int(str(control["device"]), 10),
        "inode": int(str(control["inode"]), 10),
        "path": control["path"],
        "permit_sha256": hashlib.sha256(_RELEASE_BYTES).hexdigest(),
    }:
        raise FixtureError("descendant hold receipt differs from control FIFO authority")
    if (
        _sha_value(process_spec_sha256, label="process_spec_sha256")
        != process_spec.get("spec_sha256")
        or tuple(process_spec.get("environment", ()))
        != tuple(
            sorted((b"INVOCATION_ID=" + invocation_id.encode("ascii"), b"LC_ALL=C"))
        )
    ):
        raise FixtureError("descendant GenericProcessSpec binding is incomplete")
    return {
        "plan_path": config["descendant_adversary_plan"]["path"],
        "plan_sha256": plan_sha256,
        "request_path": plan["request_path"],
        "request_sha256": hashlib.sha256(request_raw).hexdigest(),
        "receipt_path": receipt_path,
        "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "actor": actor,
        "descendant": descendant,
        "hold_release_fifo": control,
        "expected_job_name": expected_job_name,
        "expected_job_cgroup": expected_job_cgroup,
        "process_spec": dict(process_spec),
        "process_spec_sha256": process_spec_sha256,
    }


def _new_spec(
    execution: ModuleType,
    config: Mapping[str, object],
    argv: tuple[bytes, ...],
    *,
    executable: bytes | None = None,
    cwd: bytes | None = None,
    environment: tuple[bytes, ...] = (b"LC_ALL=C",),
) -> object:
    exact_executable = argv[0] if executable is None else executable
    if argv[0] != exact_executable:
        argv = (exact_executable, *argv[1:])
    return execution.GenericProcessSpec.create(
        opaque_job_key=f"formal-{config['case_id']}-{config['variant']}",
        executable=exact_executable,
        argv=argv,
        environment=environment,
        cwd=os.fsencode(_absolute_text(config, "scratch_directory")) if cwd is None else cwd,
    )


def _open_backend(
    execution: ModuleType,
    config: Mapping[str, object],
    *,
    allow_open_failure: bool = False,
) -> tuple[object, object]:
    properties = execution.ConfiguredUnitProperties.from_receipts(
        execution.UnitRole.RUN,
        _string_pairs(config, "run_configured_directives"),
        _string_pairs(config, "run_expanded_properties"),
        expected_unit=_exact_text(config, "run_unit"),
        expected_peer=_exact_text(config, "close_unit"),
    )
    lineage = execution.InvocationLineage.from_properties(
        _string_pairs(config, "invocation_lineage")
    )
    service = execution.ServiceCgroup.open_current(properties, lineage)
    capture_fd = os.open(
        _absolute_text(config, "capture_directory"),
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        backend = execution.SpawnBackend.open(service, capture_fd)
    finally:
        os.close(capture_fd)
    if type(backend) is execution.BackendOpenFailure:
        if allow_open_failure:
            return backend, lineage
        raise FixtureError(f"backend open returned typed failure: {backend!r}")
    if type(backend) is not execution.SpawnBackend:
        raise FixtureError("backend open returned an unknown type")
    return backend, lineage


def _job_key(execution: ModuleType, config: Mapping[str, object]) -> object:
    return execution.JobCgroupKey.create(
        ordinal=config["ordinal"],
        invocation_nonce=_lower_sha(config, "invocation_nonce"),
    )


def _start(
    execution: ModuleType,
    backend: object,
    config: Mapping[str, object],
    spec: object,
) -> object:
    result = backend.start_blocked(_job_key(execution, config), spec)
    return result


def _positive_cleanup(execution: ModuleType, backend: object, settled: object) -> object:
    if type(settled) is not execution.SettledJob:
        raise FixtureError(f"expected SettledJob, got {type(settled).__name__}")
    observation = settled.observation
    from scion.runtime.execution import spawn_backend as backend_implementation

    permit = backend_implementation._issue_cleanup_permit_for_tests(
        settled._cleanup_identity()
    )
    backend.remove_after_durable_cleanup(settled, permit)
    backend.close_idle()
    return observation


def _child_cgroup(pid: int) -> str:
    raw = _read_bytes(f"/proc/{pid}/cgroup")
    matches = [line[3:] for line in raw.splitlines() if line.startswith(b"0::")]
    if len(matches) != 1:
        raise FixtureError("blocked child lacks one unified cgroup")
    return matches[0].decode("ascii", "strict")


def _scratch_sentinel(config: Mapping[str, object]) -> str:
    return os.path.join(
        _absolute_text(config, "scratch_directory"),
        f"{config['case_id']}-{config['variant']}.sentinel",
    )


def _assert_absent(path: str) -> None:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return
    raise FixtureError(f"fixture path already exists: {path!r}")


def _base_receipt(
    config: Mapping[str, object], identity: Mapping[str, object]
) -> dict[str, object]:
    return {
        "schema": _RECEIPT_SCHEMA,
        "case_id": config["case_id"],
        "variant": config["variant"],
        "fixture_identity": dict(identity),
    }


def _case_b0(
    execution: ModuleType,
    config: Mapping[str, object],
    backend: object,
    lineage: object,
) -> dict[str, object]:
    sentinel = _scratch_sentinel(config)
    _assert_absent(sentinel)
    spec = _new_spec(execution, config, _helper_argv(config, "sentinel", sentinel))
    blocked = _start(execution, backend, config, spec)
    if type(blocked) is not execution.BlockedSpawn:
        raise FixtureError("B0 did not return BlockedSpawn")
    expected_cgroup = (
        lineage.control_group + "/" + blocked.cgroup_identity.job_name
    )
    blocked_fact = {
        "process_identity": blocked.process_identity,
        "cgroup_identity": blocked.cgroup_identity,
        "observed_child_cgroup": _child_cgroup(blocked.process_identity.pid),
        "expected_child_cgroup": expected_cgroup,
        "sentinel_absent": not os.path.exists(sentinel),
    }
    if (
        blocked_fact["observed_child_cgroup"] != expected_cgroup
        or blocked_fact["sentinel_absent"] is not True
    ):
        raise FixtureError("B0 blocked sentinel/cgroup proof failed")
    settled = backend.release_and_collect(blocked)
    observation = _positive_cleanup(execution, backend, settled)
    sentinel_bytes = _read_bytes(sentinel)
    if sentinel_bytes != b"executed\n":
        raise FixtureError("B0 sentinel bytes mismatch")
    if observation.stdout.data != b"" or observation.stderr.data != b"":
        raise FixtureError("B0 helper unexpectedly produced process output")
    return {
        "outcome": "PASS",
        "blocked": blocked_fact,
        "observation": observation,
        "sentinel": sentinel_bytes,
    }


def _case_b1(
    execution: ModuleType,
    config: Mapping[str, object],
    backend: object,
) -> dict[str, object]:
    variant = str(config["variant"])
    if variant == "clean":
        argv = _helper_argv(config, "exit", "0")
        expected = (0, 0, 0)
    elif variant == "nonzero":
        argv = _helper_argv(config, "exit", "23")
        expected = (23, 0, 0)
    elif variant == "signal":
        argv = _helper_argv(config, "signal", str(int(signal.SIGTERM)))
        expected = (-int(signal.SIGTERM), int(signal.SIGTERM), 0)
    else:
        argv = _helper_argv(config, "core")
        expected = (-int(signal.SIGABRT), int(signal.SIGABRT), None)
    spec = _new_spec(execution, config, argv)
    blocked = _start(execution, backend, config, spec)
    if type(blocked) is not execution.BlockedSpawn:
        raise FixtureError("B1 did not return BlockedSpawn")
    settled = backend.release_and_collect(blocked)
    observation = _positive_cleanup(execution, backend, settled)
    fact = observation.wait_fact
    if fact.return_code != expected[0] or fact.signal != expected[1]:
        raise FixtureError("B1 wait fact return/signal mismatch")
    if expected[2] is not None and fact.core_dumped != expected[2]:
        raise FixtureError("B1 core flag mismatch")
    if variant == "core" and fact.core_dumped not in (0, 1):
        raise FixtureError("B1 core flag is noncanonical")
    if variant in {"clean", "nonzero"} and (
        fact.si_code != os.CLD_EXITED or fact.si_status != fact.return_code
    ):
        raise FixtureError("B1 exited wait tuple is not exact")
    if variant == "signal" and (
        fact.si_code != os.CLD_KILLED
        or fact.si_status != int(signal.SIGTERM)
        or fact.core_dumped
    ):
        raise FixtureError("B1 signal wait tuple is not exact")
    if variant == "core" and (
        fact.si_code not in (os.CLD_KILLED, os.CLD_DUMPED)
        or fact.si_status != int(signal.SIGABRT)
        or fact.core_dumped != (fact.si_code == os.CLD_DUMPED)
    ):
        raise FixtureError("B1 core wait tuple is not exact")
    return {"outcome": "PASS", "observation": observation}


def _case_b2(
    execution: ModuleType,
    config: Mapping[str, object],
    backend: object,
) -> dict[str, object]:
    argv = _helper_argv(config, "exit", "0")
    if config["variant"] == "wrong-executable":
        absent = os.fsencode(
            os.path.join(_absolute_text(config, "scratch_directory"), "absent-executable")
        )
        spec = _new_spec(execution, config, argv, executable=absent)
        expected_stage = 13
    else:
        absent = os.fsencode(
            os.path.join(_absolute_text(config, "scratch_directory"), "absent-cwd")
        )
        spec = _new_spec(execution, config, argv, cwd=absent)
        expected_stage = 12
    if os.path.exists(os.fsdecode(absent)):
        raise FixtureError("B2 negative-control path unexpectedly exists")
    result = _start(execution, backend, config, spec)
    if type(result) is execution.BlockedSpawn:
        result = backend.release_and_collect(result)
    if type(result) is not execution.ContainedSpawnFailure:
        raise FixtureError("B2 did not produce ContainedSpawnFailure")
    if result.reason is not execution.ContainedSpawnReason.EXEC_FAILED:
        raise FixtureError("B2 failure reason is not EXEC_FAILED")
    if (
        result.exec_error is None
        or result.exec_error.byte_length != 12
        or result.wait_fact.return_code != 127
        or result.exec_error_stage != expected_stage
        or result.exec_error_errno != errno.ENOENT
    ):
        raise FixtureError("B2 lacks exact exec record and exit-127 fact")
    return {"outcome": "PASS", "failure": result}


def _binary_blocks() -> tuple[bytes, bytes]:
    stdout = bytes(index % 251 for index in range(4096))
    stderr = bytes(255 - (index % 251) for index in range(4096))
    return stdout, stderr


def _expanded_block(block: bytes, count: int) -> bytes:
    return (block * ((count + len(block) - 1) // len(block)))[:count]


def _case_b3(
    execution: ModuleType,
    config: Mapping[str, object],
    backend: object,
) -> dict[str, object]:
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
    try:
        observed_pipe_size = fcntl.fcntl(read_fd, fcntl.F_GETPIPE_SZ)
    finally:
        os.close(read_fd)
        os.close(write_fd)
    count = observed_pipe_size + 4097
    spec = _new_spec(
        execution,
        config,
        _helper_argv(config, "emit", str(count)),
    )
    blocked = _start(execution, backend, config, spec)
    if type(blocked) is not execution.BlockedSpawn:
        raise FixtureError("B3 did not return BlockedSpawn")
    observation = _positive_cleanup(
        execution, backend, backend.release_and_collect(blocked)
    )
    stdout_block, stderr_block = _binary_blocks()
    expected_stdout = _expanded_block(stdout_block, count)
    expected_stderr = _expanded_block(stderr_block, count)
    if observation.stdout.data != expected_stdout:
        raise FixtureError("B3 stdout is not byte-identical")
    if observation.stderr.data != expected_stderr:
        raise FixtureError("B3 stderr is not byte-identical")
    return {
        "outcome": "PASS",
        "observed_pipe_size": observed_pipe_size,
        "emitted_each_stream": count,
        "observation": observation,
    }


def _control_fifo_reference(config: Mapping[str, object]) -> dict[str, object]:
    value = config["control_fifo"]
    if type(value) is not dict:
        raise RequirementMissing(
            "FORMAL_CONTROL_FIFO", "case requires one complete control FIFO authority"
        )
    return _fifo_reference(value, label="control_fifo")


class _ControlFifoPin:
    def __init__(self, config: Mapping[str, object]) -> None:
        self.reference = _control_fifo_reference(config)
        self.path, self.identity = _fifo_tuple(self.reference)
        self.fd = os.open(
            self.path,
            getattr(os, "O_PATH", os.O_RDONLY)
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0),
        )
        _require_open_fifo_identity(self.fd, self.identity, label="control FIFO pin")
        self.closed = False

    def revalidate(self) -> None:
        if self.closed:
            raise FixtureError("control FIFO authority was already closed")
        _require_open_fifo_identity(self.fd, self.identity, label="control FIFO pin")
        if _fifo_reference(self.reference, label="control_fifo") != self.reference:
            raise FixtureError("control FIFO authority changed")

    def read_expected(self, expected: bytes) -> bytes:
        self.revalidate()
        fd = os.open(
            self.path,
            os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            _require_open_fifo_identity(fd, self.identity, label="control FIFO reader")
            token = _read_all(fd)
        finally:
            os.close(fd)
        if token != expected:
            raise FixtureError("formal control FIFO token mismatch")
        self.revalidate()
        return token

    def close(self) -> None:
        if self.closed:
            raise FixtureError("control FIFO authority closed twice")
        self.revalidate()
        os.close(self.fd)
        self.fd = -1
        self.closed = True


def _write_armed(
    config: Mapping[str, object],
    identity: Mapping[str, object],
    blocked: object,
    *,
    action_id: str,
    expected_permit: bytes,
) -> str:
    receipt = {
        "schema": _FORMAL_ACTION_ARMED_SCHEMA,
        "action_id": action_id,
        "case_id": config["case_id"],
        "variant": config["variant"],
        "unit": config["run_unit"],
        "process_identity": blocked.process_identity.to_mapping(),
        "cgroup_identity": blocked.cgroup_identity.to_mapping(),
        "control_fifo": _control_fifo_reference(config),
        "systemd_armed_receipt_sha256": config["systemd_armed_receipt_sha256"],
        "plan_sha256": config["plan_sha256"],
        "expected_permit_sha256": hashlib.sha256(expected_permit).hexdigest(),
    }
    return _write_receipt(
        _absolute_text(config, "receipt_directory"),
        _receipt_component(config, "armed_receipt_name"),
        receipt,
    )


def _b6_sigusr1_handler(_signum: int, _frame: object) -> NoReturn:
    raise KeyboardInterrupt


def _signal_set_fact(values: object) -> list[int]:
    return sorted(int(value) for value in values)


def _disposition_fact(value: object) -> dict[str, object]:
    if value is signal.SIG_DFL:
        return {"kind": "SIG_DFL"}
    if value is signal.SIG_IGN:
        return {"kind": "SIG_IGN"}
    return {
        "kind": "CALLABLE",
        "module": getattr(value, "__module__", None),
        "qualname": getattr(value, "__qualname__", None),
    }


class _B6SignalContext:
    def __init__(self) -> None:
        self.original_mask = frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set()))
        self.original_pending = frozenset(signal.sigpending())
        if signal.SIGUSR1 in self.original_mask:
            raise RequirementMissing(
                "SIGUSR1_CALLER_MASK",
                "B6 issuer signal is already blocked by the caller",
            )
        if signal.SIGUSR1 in self.original_pending:
            raise RequirementMissing(
                "SIGUSR1_CALLER_PENDING",
                "B6 issuer signal is already pending at entry",
            )
        self.original_disposition = signal.getsignal(signal.SIGUSR1)
        source = inspect.getsource(_b6_sigusr1_handler).encode("utf-8", "strict")
        self.handler_sha256 = hashlib.sha256(source).hexdigest()
        previous = signal.signal(signal.SIGUSR1, _b6_sigusr1_handler)
        if previous is not self.original_disposition:
            raise FixtureError("SIGUSR1 disposition changed during handler install")
        if signal.getsignal(signal.SIGUSR1) is not _b6_sigusr1_handler:
            raise FixtureError("fixed SIGUSR1 handler did not install exactly")
        self.restored = False

    def entry_fact(self) -> dict[str, object]:
        return {
            "signal": int(signal.SIGUSR1),
            "original_mask": _signal_set_fact(self.original_mask),
            "original_pending": _signal_set_fact(self.original_pending),
            "original_disposition": _disposition_fact(self.original_disposition),
            "fixed_disposition": _disposition_fact(_b6_sigusr1_handler),
            "handler_source_sha256": self.handler_sha256,
        }

    def restore(self) -> dict[str, object]:
        if self.restored:
            raise FixtureError("B6 SIGUSR1 disposition restored twice")
        if frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set())) != self.original_mask:
            raise FixtureError("production guard did not restore the original signal mask")
        current_pending = frozenset(signal.sigpending())
        if current_pending != self.original_pending:
            raise FixtureError("B6 SIGUSR1 pending state did not return to entry state")
        previous = signal.signal(signal.SIGUSR1, self.original_disposition)
        if previous is not _b6_sigusr1_handler:
            raise FixtureError("fixed SIGUSR1 handler authority changed before restore")
        if signal.getsignal(signal.SIGUSR1) is not self.original_disposition:
            raise FixtureError("original SIGUSR1 disposition did not restore exactly")
        self.restored = True
        return {
            "restored_mask": _signal_set_fact(self.original_mask),
            "restored_pending": _signal_set_fact(current_pending),
            "restored_disposition": _disposition_fact(self.original_disposition),
        }


def _fifo_tuple(reference: Mapping[str, object]) -> tuple[str, tuple[int, int]]:
    path = _canonical_absolute_value(reference["path"], label="FIFO path")
    return path, (int(str(reference["device"]), 10), int(str(reference["inode"]), 10))


def _require_open_fifo_identity(fd: int, expected: tuple[int, int], *, label: str) -> None:
    status = os.fstat(fd)
    if not stat.S_ISFIFO(status.st_mode) or (status.st_dev, status.st_ino) != expected:
        raise FixtureError(f"{label} live descriptor identity changed")


class _B6OpenProxy:
    def __init__(self, wrapped: ModuleType, controller: "_B6FaultController") -> None:
        self._wrapped = wrapped
        self._controller = controller

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)

    def open(self, path: object, flags: int, *args: object, **kwargs: object) -> int:
        if path == "." and flags & getattr(os, "O_TMPFILE", 0):
            return self._controller.invoke(self._wrapped.open, path, flags, *args, **kwargs)
        return self._wrapped.open(path, flags, *args, **kwargs)


class _B6FaultController:
    def __init__(
        self,
        config: Mapping[str, object],
        identity: Mapping[str, object],
        signal_context: _B6SignalContext | None,
    ) -> None:
        plan = config["b6"]
        if type(plan) is not dict:
            raise FixtureError("B6 controller requires an exact ABI plan")
        self.config = config
        self.identity = identity
        self.plan = plan
        self.signal_context = signal_context
        self.operation_ordinal = int(str(plan["operation_ordinal"]), 10)
        self.calls = 0
        self.triggered = False
        self.armed_sha256: str | None = None
        self.before_fact: dict[str, object] | None = None
        self.after_fact: dict[str, object] | None = None
        self.backend: object | None = None
        self.blocked: object | None = None
        self.blocked_fact: dict[str, object] | None = None
        self.poll_pidfd: int | None = None
        self.poll_pidfd_identity: tuple[int, int] | None = None
        self.operation_receipt_sha256: str | None = None
        self.injection_count = 0
        self.descendant_binding: dict[str, object] | None = None
        self.control_pin: _ControlFifoPin | None = None
        self._patches: list[tuple[object, str, object]] = []

    def bind_backend(self, backend: object) -> None:
        self.backend = backend

    def bind_blocked(self, blocked: object) -> None:
        poll_pidfd = blocked._poll_pidfd
        if type(poll_pidfd) is not int or poll_pidfd < 0:
            raise FixtureError("B6 blocked spawn lacks one live poll pidfd")
        poll_status = os.fstat(poll_pidfd)
        self.blocked = blocked
        self.poll_pidfd = poll_pidfd
        self.poll_pidfd_identity = (poll_status.st_dev, poll_status.st_ino)
        self.blocked_fact = {
            "process_identity": blocked.process_identity.to_mapping(),
            "cgroup_identity": blocked.cgroup_identity.to_mapping(),
            "process_spec_sha256": blocked.process_spec_sha256,
            "poll_pidfd": poll_pidfd,
            "poll_pidfd_device": poll_status.st_dev,
            "poll_pidfd_inode": poll_status.st_ino,
        }

    def bind_descendant(
        self,
        *,
        binding: Mapping[str, object],
        control_pin: _ControlFifoPin,
    ) -> None:
        if self.descendant_binding is not None or self.control_pin is not None:
            raise FixtureError("B6 descendant authority bound twice")
        self.descendant_binding = dict(binding)
        self.control_pin = control_pin

    def _lifecycle_fact(self) -> dict[str, object]:
        fact: dict[str, object] = {
            "pid": os.getpid(),
            "starttime": _proc_starttime(os.getpid()),
            "hook": self.plan["hook"],
            "target_operation": self.plan["target_operation"],
            "operation_call_count": self.calls,
        }
        if self.backend is not None:
            fact["backend_state"] = self.backend.state
        if self.blocked is not None:
            if self.blocked_fact is None:
                raise FixtureError("B6 blocked evidence was not frozen before consumption")
            fact.update(self.blocked_fact)
            fact["native_child_state"] = self.blocked._child.state
        if self.descendant_binding is not None:
            fact["descendant_binding"] = self.descendant_binding
        return fact

    def _prove_reaped_populated(self) -> None:
        if self.blocked is None or self.blocked_fact is None:
            raise FixtureError("B6 reaped-populated seam lacks blocked authority")
        if self.control_pin is None:
            raise FixtureError("B6 reaped-populated seam lacks control FIFO pin")
        self.control_pin.revalidate()
        if self.blocked._child.state != "REAPED":
            raise RequirementMissing(
                "B6_LEADER_REAPED", "native leader is not reaped at pidfd-close seam"
            )
        leader_pid = int(self.blocked_fact["process_identity"]["pid"])
        try:
            os.lstat(f"/proc/{leader_pid}")
        except FileNotFoundError:
            pass
        else:
            raise RequirementMissing(
                "B6_LEADER_PROC", "reaped native leader still has a /proc identity"
            )
        events = self.blocked._job._read_events()
        if events.populated != 1 or events.frozen != 0:
            raise RequirementMissing(
                "B6_REAPED_POPULATED_EVENTS",
                "job cgroup is not populated=1/frozen=0 at pidfd-close seam",
            )
        binding = self.descendant_binding
        if type(binding) is not dict or binding.get("validated") is not False:
            raise FixtureError("B6 descendant validation binding is absent or reused")
        validated = _validate_descendant_receipt(
            self.config,
            plan=binding["plan"],
            plan_sha256=str(binding["plan_sha256"]),
            receipt_path=str(binding["receipt_path"]),
            invocation_id=str(binding["invocation_id"]),
            boot_id=str(binding["boot_id"]),
            blocked_process=binding["blocked_process"],
            expected_job_cgroup=str(binding["expected_job_cgroup"]),
            process_spec_sha256=str(binding["process_spec_sha256"]),
            process_spec=binding["process_spec"],
            require_live_descendant=True,
        )
        validated["cgroup_events"] = events
        self.descendant_binding = {"validated": True, "evidence": validated}

    def _arm_and_wait(self) -> None:
        if self.triggered:
            raise RequirementMissing("B6_EXTRA_INJECTION", "B6 hook attempted a second injection")
        issuer = self.plan["fault"] == "issuer-signal"
        guarded_mask = frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set()))
        pending_before = frozenset(signal.sigpending())
        if issuer:
            if self.signal_context is None:
                raise FixtureError("issuer hook lacks fixed signal context")
            if signal.SIGUSR1 not in guarded_mask or signal.SIGUSR1 in pending_before:
                raise RequirementMissing(
                    "B6_UNGUARDED_SEAM",
                    "B6 issuer hook was not entered inside the production signal guard",
                )
        acquisition = self.plan["acquisition"]
        if type(acquisition) is not dict:
            raise FixtureError("B6 acquisition is not an exact object")
        before = self._lifecycle_fact()
        before.update(
            {
                "guarded_mask": _signal_set_fact(guarded_mask),
                "pending_before": _signal_set_fact(pending_before),
            }
        )
        receipt = {
            "schema": _B6_ARMED_SCHEMA,
            "case_id": self.config["case_id"],
            "variant": self.config["variant"],
            "unit": self.config["run_unit"],
            "fault": self.plan["fault"],
            "declared_phase": self.plan["phase"],
            "hook": self.plan["hook"],
            "target_operation": self.plan["target_operation"],
            "planned_ordinal": self.operation_ordinal,
            "process_identity": _formal_process_identity(
                {}, self.config["invocation_lineage"]
            ),
            "plan_sha256": self.config["plan_sha256"],
            "systemd_armed_receipt_sha256": self.config[
                "systemd_armed_receipt_sha256"
            ],
            "before_fact": before,
            "ready_fifo": acquisition["ready_fifo"],
            "release_fifo": acquisition["release_fifo"],
            "operation_receipt_path": acquisition["operation_receipt_path"],
            "ready_sha256": hashlib.sha256(_READY_BYTES).hexdigest(),
            "release_sha256": hashlib.sha256(_RELEASE_BYTES).hexdigest(),
            "signal_context": (
                self.signal_context.entry_fact()
                if self.signal_context is not None
                else None
            ),
        }
        armed_path = str(acquisition["armed_receipt_path"])
        self.armed_sha256 = _write_static_json_no_replace(armed_path, receipt)
        ready_path, ready_identity = _fifo_tuple(acquisition["ready_fifo"])
        ready_fd = os.open(
            ready_path,
            os.O_WRONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            _require_open_fifo_identity(ready_fd, ready_identity, label="B6 ready FIFO")
            _write_all(ready_fd, _READY_BYTES)
        finally:
            os.close(ready_fd)
        release_path, release_identity = _fifo_tuple(acquisition["release_fifo"])
        release_fd = os.open(
            release_path,
            os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            _require_open_fifo_identity(
                release_fd, release_identity, label="B6 release FIFO"
            )
            release = _read_all(release_fd)
        finally:
            os.close(release_fd)
        if release != _RELEASE_BYTES:
            raise FixtureError("B6 release FIFO lacks exact bytes followed by EOF")
        pending_after = frozenset(signal.sigpending())
        guarded_after = frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set()))
        if issuer and (
            signal.SIGUSR1 not in pending_after or signal.SIGUSR1 not in guarded_after
        ):
            raise RequirementMissing(
                "B6_SEND_BEFORE_RELEASE",
                "SIGUSR1 was not pending and blocked after the one release permit",
            )
        if os.getpid() != before["pid"] or _proc_starttime(os.getpid()) != before["starttime"]:
            raise FixtureError("B6 same-PID identity changed across FIFO rendezvous")
        _fifo_reference(acquisition["ready_fifo"], label="b6.acquisition.ready_fifo")
        _fifo_reference(acquisition["release_fifo"], label="b6.acquisition.release_fifo")
        self.before_fact = before
        self.after_fact = {
            "pending_after_release": _signal_set_fact(pending_after),
            "guarded_mask_after_release": _signal_set_fact(guarded_after),
            "release_sha256": hashlib.sha256(release).hexdigest(),
        }
        self.triggered = True

    @staticmethod
    def _type_name(value: object) -> str:
        value_type = type(value)
        return f"{value_type.__module__}.{value_type.__qualname__}"

    def _publish_operation(
        self,
        *,
        operation_state: str,
        effect_state: str,
        return_value: object | None,
        exception: BaseException | None,
        postcondition: str,
    ) -> None:
        if self.operation_receipt_sha256 is not None:
            raise RequirementMissing(
                "B6_EXTRA_OPERATION_RECEIPT",
                "B6 operation receipt attempted a second publication",
            )
        if self.armed_sha256 is None or self.before_fact is None or self.after_fact is None:
            raise FixtureError("B6 operation reached without durable acquisition evidence")
        self.injection_count += 1
        if self.injection_count != 1:
            raise RequirementMissing("B6_EXTRA_INJECTION", "B6 injected more than once")
        exception_errno = getattr(exception, "errno", None)
        if type(exception_errno) is not int:
            exception_errno = None
        receipt = {
            "schema": _B6_OPERATION_SCHEMA,
            "case_id": self.config["case_id"],
            "variant": self.config["variant"],
            "fault": self.plan["fault"],
            "declared_phase": self.plan["phase"],
            "hook": self.plan["hook"],
            "target_operation": self.plan["target_operation"],
            "planned_ordinal": self.operation_ordinal,
            "observed_ordinal": self.calls,
            "injection_count": self.injection_count,
            "armed_receipt_sha256": self.armed_sha256,
            "actor_pid": os.getpid(),
            "actor_starttime": _proc_starttime(os.getpid()),
            "before_fact_sha256": hashlib.sha256(
                _canonical_json(self.before_fact)
            ).hexdigest(),
            "release_permit_sha256": self.after_fact["release_sha256"],
            "operation_state": operation_state,
            "effect_state": effect_state,
            "return_type": (
                None
                if operation_state == "RAISED"
                else self._type_name(return_value)
            ),
            "exception_type": (
                None if exception is None else self._type_name(exception)
            ),
            "errno": exception_errno,
            "postcondition": postcondition,
        }
        acquisition = self.plan["acquisition"]
        self.operation_receipt_sha256 = _write_static_json_no_replace(
            str(acquisition["operation_receipt_path"]), receipt
        )

    def invoke(self, operation: object, *args: object, **kwargs: object) -> object:
        self.calls += 1
        if self.calls != self.operation_ordinal:
            return operation(*args, **kwargs)
        self._arm_and_wait()
        if self.plan["fault"] == "capture-storage":
            result = False
            self._publish_operation(
                operation_state="INJECTED_RETURN",
                effect_state="ORIGINAL_STORAGE_WRITE_NOT_CALLED",
                return_value=result,
                exception=None,
                postcondition="capture storage became unavailable after one injected false",
            )
            return result
        if self.plan["fault"] == "authority-close":
            operation(*args, **kwargs)
            error = OSError(errno.EIO, "injected post-close uncertainty")
            self._publish_operation(
                operation_state="POST_COMMIT_UNCERTAINTY",
                effect_state="CLOSE_COMMITTED_THEN_EIO",
                return_value=None,
                exception=error,
                postcondition="close committed before injected EIO",
            )
            raise error
        try:
            result = operation(*args, **kwargs)
        except BaseException as exc:
            self._publish_operation(
                operation_state="RAISED",
                effect_state=(
                    "MASK_RESTORED_HANDLER_RAISED"
                    if self.plan["hook"] == "guard-restore"
                    else "TARGET_OPERATION_RAISED"
                ),
                return_value=None,
                exception=exc,
                postcondition="issuer delivery reached the exact guarded operation",
            )
            raise
        effect = {
            "service-consume": "AUTHORITY_MOVED",
            "capture-spool-open": "FD_ACQUIRED",
            "pre-native-borrow": "PINNED_BORROW_RETURNED",
            "guard-restore": "MASK_RESTORED_HANDLER_DELIVERED",
            "terminal-fact": "WAIT_FACT_RETURNED",
            "reaped-pidfd-close": "PIDFD_CLOSED",
            "capture-write": "STORAGE_WRITE_RETURNED",
        }[str(self.plan["hook"])]
        if self.plan["hook"] == "guard-restore" and result is not True:
            raise FixtureError(
                "production guard restore did not absorb fixed handler delivery"
            )
        self._publish_operation(
            operation_state="RETURNED",
            effect_state=effect,
            return_value=result,
            exception=None,
            postcondition=(
                "fixed handler raised inside production restore and guard recovery returned true"
                if self.plan["hook"] == "guard-restore"
                else "exact target operation completed once"
            ),
        )
        return result

    def _patch(self, owner: object, name: str, replacement: object) -> None:
        original = vars(owner)[name]
        self._patches.append((owner, name, original))
        setattr(owner, name, replacement)

    def install(self, backend_implementation: ModuleType) -> None:
        hook = self.plan["hook"]
        if hook == "unobservable-source-seam" or hook == "native-spawn-no-handle":
            raise RequirementMissing(
                "B6_EXACT_GUARDED_SEAM",
                "accepted source exposes no honest exact guarded seam for this B6 plan",
            )
        if hook == "guard-restore":
            original = backend_implementation._IssuerSignalGuard.restore

            def restore(guard: object) -> bool:
                return self.invoke(original, guard)

            self._patch(backend_implementation._IssuerSignalGuard, "restore", restore)
            return
        if hook == "service-consume":
            from scion.runtime.execution import cgroup_v2

            original = cgroup_v2.ServiceCgroup._consume

            def consume(service: object) -> object:
                return self.invoke(original, service)

            self._patch(cgroup_v2.ServiceCgroup, "_consume", consume)
            return
        if hook == "capture-spool-open":
            original_os = backend_implementation.os
            self._patches.append((backend_implementation, "os", original_os))
            backend_implementation.os = _B6OpenProxy(original_os, self)
            return
        if hook == "pre-native-borrow":
            from scion.runtime.execution import cgroup_v2

            original = cgroup_v2._JobCgroup._consume_spawn_dirfd_borrow

            def borrow(job: object) -> int:
                return self.invoke(original, job)

            self._patch(cgroup_v2._JobCgroup, "_consume_spawn_dirfd_borrow", borrow)
            return
        if hook == "terminal-fact":
            original = backend_implementation.WaitFact.from_native

            def from_native(cls: type, native_fact: object) -> object:
                del cls
                return self.invoke(original, native_fact)

            self._patch(
                backend_implementation.WaitFact,
                "from_native",
                classmethod(from_native),
            )
            return
        if hook == "reaped-pidfd-close":
            original = backend_implementation._close_exact

            def close_exact(fd: int) -> None:
                if self.poll_pidfd is None or fd != self.poll_pidfd:
                    return original(fd)
                status = os.fstat(fd)
                if (status.st_dev, status.st_ino) != self.poll_pidfd_identity:
                    raise RequirementMissing(
                        "B6_PIDFD_IDENTITY",
                        "the frozen poll pidfd identity drifted before close",
                    )
                self._prove_reaped_populated()
                self.invoke(original, fd)

            self._patch(backend_implementation, "_close_exact", close_exact)
            return
        if hook == "capture-write":
            original = backend_implementation._write_spool

            def write_spool(spool: object, data: bytes) -> bool:
                return self.invoke(original, spool, data)

            self._patch(backend_implementation, "_write_spool", write_spool)
            return
        if hook in _B6_INSTALLABLE_HOOKS:
            raise FixtureError("fixed B6 hook lacks its install implementation")
        raise RequirementMissing(
            "B6_EXACT_GUARDED_SEAM",
            "B6 hook is not executable against the accepted source hash",
        )

    def uninstall(self) -> None:
        while self._patches:
            owner, name, original = self._patches.pop()
            setattr(owner, name, original)
        if self.control_pin is not None:
            self.control_pin.revalidate()
            self.control_pin.close()
            self.control_pin = None

    def receipt_fact(self) -> dict[str, object]:
        if (
            not self.triggered
            or self.calls < self.operation_ordinal
            or self.operation_receipt_sha256 is None
            or self.injection_count != 1
        ):
            raise RequirementMissing(
                "B6_PHASE_NOT_REACHED",
                "the exact B6 operation ordinal lacks one durable operation receipt",
            )
        return {
            "armed_receipt_sha256": self.armed_sha256,
            "operation_receipt_sha256": self.operation_receipt_sha256,
            "injection_count": self.injection_count,
            "operation_call_count": self.calls,
            "operation_ordinal": self.operation_ordinal,
            "before": self.before_fact,
            "after_release": self.after_fact,
        }


def _case_b4(
    execution: ModuleType,
    config: Mapping[str, object],
    backend: object,
    identity: Mapping[str, object],
) -> dict[str, object]:
    control = _ControlFifoPin(config)
    try:
        spec = _new_spec(execution, config, _helper_argv(config, "exit", "0"))
        blocked = _start(execution, backend, config, spec)
        if type(blocked) is not execution.BlockedSpawn:
            raise FixtureError("B4 did not return BlockedSpawn")
        armed_sha256 = _write_armed(
            config,
            identity,
            blocked,
            action_id="b4-kill-before-release",
            expected_permit=b"JOB_CGROUP_KILLED\n",
        )
        token = control.read_expected(b"JOB_CGROUP_KILLED\n")
        result = backend.release_and_collect(blocked)
        control.revalidate()
        if type(result) is not execution.ContainedSpawnFailure:
            raise FixtureError("B4 did not produce ContainedSpawnFailure")
        if result.reason is not execution.ContainedSpawnReason.RELEASE_UNCERTAIN:
            raise FixtureError("B4 did not preserve RELEASE_UNCERTAIN")
        return {
            "outcome": "PASS",
            "armed_receipt_sha256": armed_sha256,
            "control_permit": token,
            "control_fifo": control.reference,
            "failure": result,
        }
    finally:
        control.close()


def _case_b5(
    execution: ModuleType,
    config: Mapping[str, object],
    backend: object,
    lineage: object,
) -> dict[str, object]:
    mode = str(config["variant"])
    scenario = _expected_descendant_scenario("B5", mode)
    control = _ControlFifoPin(config)
    try:
        argv, adversary_plan, receipt_path, adversary_plan_sha256 = (
            _descendant_adversary_argv(config, scenario)
        )
        invocation = lineage.invocation_id
        if invocation != _current_invocation_id():
            raise FixtureError("B5 lineage and current INVOCATION_ID differ")
        environment = tuple(
            sorted((b"INVOCATION_ID=" + invocation.encode("ascii"), b"LC_ALL=C"))
        )
        spec = _new_spec(execution, config, argv, environment=environment)
        blocked = _start(execution, backend, config, spec)
        if type(blocked) is not execution.BlockedSpawn:
            raise FixtureError("B5 did not return BlockedSpawn")
        blocked_process = {
            "pid": blocked.process_identity.pid,
            "starttime": blocked.process_identity.proc_starttime_ticks,
        }
        expected_job_cgroup = (
            lineage.control_group + "/" + blocked.cgroup_identity.job_name
        )
        process_spec_sha256 = blocked.process_spec_sha256
        result = backend.release_and_collect(blocked)
        control.revalidate()
        if type(result) is not execution.ContainedSpawnFailure:
            raise FixtureError("B5 returned a positive observation")
        if result.reason is not execution.ContainedSpawnReason.DESCENDANT_SURVIVED:
            raise FixtureError("B5 did not detect descendant survival")
        if result.process_spec_sha256 != process_spec_sha256:
            raise FixtureError("B5 process spec digest changed across containment")
        descendant = _validate_descendant_receipt(
            config,
            plan=adversary_plan,
            plan_sha256=adversary_plan_sha256,
            receipt_path=receipt_path,
            invocation_id=invocation,
            boot_id=lineage.boot_id,
            blocked_process=blocked_process,
            expected_job_cgroup=expected_job_cgroup,
            process_spec_sha256=process_spec_sha256,
            process_spec=spec.to_mapping(),
            require_live_descendant=False,
        )
        return {
            "outcome": "PASS",
            "failure": result,
            "descendant_binding": descendant,
            "transported_environment": environment,
        }
    finally:
        control.close()


def _case_b6(
    execution: ModuleType,
    config: Mapping[str, object],
    backend: object,
    controller: _B6FaultController,
    lineage: object,
) -> dict[str, object]:
    observed_pipe_size: int | None = None
    emitted_each_stream: int | None = None
    if config["variant"] == "issuer-reaped-populated":
        control: _ControlFifoPin | None = _ControlFifoPin(config)
        try:
            argv, adversary_plan, receipt_path, adversary_plan_sha256 = (
                _descendant_adversary_argv(
                    config, _expected_descendant_scenario("B6", str(config["variant"]))
                )
            )
            invocation = lineage.invocation_id
            if invocation != _current_invocation_id():
                raise FixtureError("B6 lineage and current INVOCATION_ID differ")
            environment = tuple(
                sorted(
                    (b"INVOCATION_ID=" + invocation.encode("ascii"), b"LC_ALL=C")
                )
            )
            spec = _new_spec(execution, config, argv, environment=environment)
            result = _start(execution, backend, config, spec)
            if type(result) is not execution.BlockedSpawn:
                raise FixtureError("B6 reaped-populated did not return BlockedSpawn")
            controller.bind_blocked(result)
            expected_job_cgroup = (
                lineage.control_group + "/" + result.cgroup_identity.job_name
            )
            if result.cgroup_identity.job_name != adversary_plan["expected_job_name"]:
                raise FixtureError("B6 blocked job name differs from adversary plan")
            controller.bind_descendant(
                binding={
                    "validated": False,
                    "plan": adversary_plan,
                    "plan_sha256": adversary_plan_sha256,
                    "receipt_path": receipt_path,
                    "invocation_id": invocation,
                    "boot_id": lineage.boot_id,
                    "blocked_process": {
                        "pid": result.process_identity.pid,
                        "starttime": result.process_identity.proc_starttime_ticks,
                    },
                    "expected_job_cgroup": expected_job_cgroup,
                    "process_spec": spec.to_mapping(),
                    "process_spec_sha256": result.process_spec_sha256,
                },
                control_pin=control,
            )
            control = None
        finally:
            if control is not None:
                control.close()
    else:
        read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
        try:
            observed_pipe_size = fcntl.fcntl(read_fd, fcntl.F_GETPIPE_SZ)
        finally:
            os.close(read_fd)
            os.close(write_fd)
        emitted_each_stream = observed_pipe_size + 4097
        spec = _new_spec(
            execution,
            config,
            _helper_argv(config, "emit", str(emitted_each_stream)),
        )
        result = _start(execution, backend, config, spec)
    if type(result) is execution.BlockedSpawn:
        if controller.blocked is None:
            controller.bind_blocked(result)
        result = backend.release_and_collect(result)
    receipt = _b6_result(controller, result)
    receipt.update(
        {
            "observed_pipe_size": observed_pipe_size,
            "emitted_each_stream": emitted_each_stream,
        }
    )
    return receipt


def _b6_result(
    controller: _B6FaultController,
    result: object,
) -> dict[str, object]:
    expected_type = str(controller.plan["expected_fact_type"])
    if type(result).__name__ != expected_type:
        raise FixtureError(
            f"B6 expected {expected_type}, got {type(result).__name__}"
        )
    phase = getattr(getattr(result, "phase", None), "value", None)
    reason = getattr(getattr(result, "reason", None), "value", None)
    if phase != controller.plan["expected_phase"]:
        raise FixtureError("B6 result phase differs from the frozen ABI")
    if reason != controller.plan["expected_reason"]:
        raise FixtureError("B6 result reason differs from the frozen ABI")
    return {
        "outcome": "PASS",
        "failure": result,
        "fault_ledger": controller.receipt_fact(),
    }


class _OpenFaultProxy:
    def __init__(self, wrapped: ModuleType, injected_errno: int) -> None:
        self._wrapped = wrapped
        self._errno = injected_errno
        self.injected = False

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)

    def open(self, path: object, flags: int, *args: object, **kwargs: object) -> int:
        if path == "." and flags & getattr(os, "O_TMPFILE", 0):
            self.injected = True
            raise OSError(self._errno, "injected unnamed-spool open error")
        return self._wrapped.open(path, flags, *args, **kwargs)


def _case_b7(
    execution: ModuleType,
    config: Mapping[str, object],
    backend: object,
    identity: Mapping[str, object],
) -> dict[str, object]:
    from scion.runtime.execution import spawn_backend as backend_implementation

    variant = str(config["variant"])
    if variant in _INTERNAL_B7_VARIANTS:
        injected_errno = {
            "tmpfile-unsupported": errno.EOPNOTSUPP,
            "tmpfile-allocation": errno.ENOSPC,
            "tmpfile-open": errno.EACCES,
        }[variant]
        proxy = _OpenFaultProxy(backend_implementation.os, injected_errno)
        native_calls = 0
        accepted_native = backend_implementation.native.spawn_blocked

        def counted_native(*args: object) -> object:
            nonlocal native_calls
            native_calls += 1
            return accepted_native(*args)

        original_os = backend_implementation.os
        original_native = backend_implementation.native.spawn_blocked
        try:
            backend_implementation.os = proxy
            backend_implementation.native.spawn_blocked = counted_native
            spec = _new_spec(execution, config, _helper_argv(config, "exit", "0"))
            result = _start(execution, backend, config, spec)
        finally:
            backend_implementation.native.spawn_blocked = original_native
            backend_implementation.os = original_os
        if (
            backend_implementation.os is not original_os
            or backend_implementation.native.spawn_blocked is not original_native
        ):
            raise FixtureError("B7 internal fault proxy did not uninstall exactly")
        if type(result) is not execution.PreHandleFailure:
            raise FixtureError("B7 unnamed-spool error did not return PreHandleFailure")
        expected_reason = {
            "tmpfile-unsupported": execution.PreHandleReason.CAPTURE_TMPFILE_UNSUPPORTED,
            "tmpfile-allocation": execution.PreHandleReason.CAPTURE_ALLOCATION_FAILED,
            "tmpfile-open": execution.PreHandleReason.CAPTURE_OPEN_FAILED,
        }[variant]
        if result.reason is not expected_reason or native_calls != 0 or not proxy.injected:
            raise FixtureError("B7 unnamed-spool failure facts/counter mismatch")
        return {
            "outcome": "PASS",
            "action_owner": "formal-case",
            "control_fifo": None,
            "injected_errno": injected_errno,
            "native_spawn_call_count": native_calls,
            "failure": result,
        }

    if variant not in _EXTERNAL_B7_VARIANTS:
        raise FixtureError("B7 variant has no frozen action owner")
    control = _ControlFifoPin(config)
    try:
        spec = _new_spec(execution, config, _helper_argv(config, "exit", "0"))
        blocked = _start(execution, backend, config, spec)
        if type(blocked) is not execution.BlockedSpawn:
            raise FixtureError("B7 drift case did not return BlockedSpawn")
        _write_armed(
            config,
            identity,
            blocked,
            action_id=f"b7-{variant}",
            expected_permit=b"DRIFT_APPLIED\n",
        )
        control.read_expected(b"DRIFT_APPLIED\n")
        backend.release_and_collect(blocked)
        raise FixtureError("B7 topology drift returned ordinary control")
    finally:
        control.close()


def _case_b8(backend: object) -> dict[str, object]:
    backend.close_idle()
    return {"outcome": "PASS", "hashes_verified": True}


def _requirement_receipt(
    config: Mapping[str, object],
    identity: Mapping[str, object],
    config_sha256: str,
    error: RequirementMissing,
) -> None:
    receipt = _base_receipt(config, identity)
    receipt.update(
        {
            "outcome": "REQUIREMENT_MISSING",
            "config_sha256": config_sha256,
            "requirement_code": error.code,
            "requirement": str(error),
        }
    )
    _write_receipt(
        _absolute_text(config, "receipt_directory"),
        _receipt_component(config, "receipt_name"),
        receipt,
    )


def _execute_case(config_path: str) -> int:
    config, config_sha256 = _load_config(config_path)
    _revalidate_directory_authorities(config)
    identity = _fixture_identity(config, config_sha256)

    import scion.runtime.execution as execution

    expected_lineage = execution.InvocationLineage.from_properties(
        _string_pairs(config, "invocation_lineage")
    )
    baseline = _inventory(expected_lineage.control_group)
    case_id = str(config["case_id"])
    backend: object | None = None
    controller: _B6FaultController | None = None
    signal_context: _B6SignalContext | None = None
    from scion.runtime.execution import spawn_backend as backend_implementation

    try:
        if case_id == "B6":
            b6 = config["b6"]
            if type(b6) is not dict:
                raise FixtureError("B6 config lost its exact ABI")
            if b6["fault"] == "issuer-signal":
                signal_context = _B6SignalContext()
            controller = _B6FaultController(config, identity, signal_context)
            controller.install(backend_implementation)

        opened, lineage = _open_backend(
            execution,
            config,
            allow_open_failure=case_id == "B6",
        )
        if lineage != expected_lineage:
            raise FixtureError("backend lineage differs from pre-open decoded lineage")
        backend_open = _inventory(lineage.control_group)
        _revalidate_directory_authorities(config)
        if type(opened) is execution.BackendOpenFailure:
            if case_id != "B6" or controller is None:
                raise FixtureError("unexpected backend-open typed failure")
            result = _b6_result(controller, opened)
        else:
            backend = opened
            if controller is not None:
                controller.bind_backend(backend)
            if case_id == "B0":
                result = _case_b0(execution, config, backend, lineage)
            elif case_id == "B1":
                result = _case_b1(execution, config, backend)
            elif case_id == "B2":
                result = _case_b2(execution, config, backend)
            elif case_id == "B3":
                result = _case_b3(execution, config, backend)
            elif case_id == "B4":
                result = _case_b4(execution, config, backend, identity)
            elif case_id == "B5":
                result = _case_b5(execution, config, backend, lineage)
            elif case_id == "B6":
                if controller is None:
                    raise FixtureError("B6 controller was not installed")
                result = _case_b6(execution, config, backend, controller, lineage)
            elif case_id == "B7":
                result = _case_b7(execution, config, backend, identity)
            elif case_id == "B8":
                result = _case_b8(backend)
            else:
                raise FixtureError("unreachable case id")
        _revalidate_directory_authorities(config)
    except RequirementMissing as exc:
        if controller is not None:
            controller.uninstall()
        if signal_context is not None and not signal_context.restored:
            signal_context.restore()
        if backend is not None and backend.state == "IDLE":
            backend.close_idle()
        _revalidate_directory_authorities(config)
        _requirement_receipt(config, identity, config_sha256, exc)
        return 78

    if controller is not None:
        controller.uninstall()
    if signal_context is not None:
        restored = signal_context.restore()
        ledger = result.get("fault_ledger")
        if type(ledger) is not dict:
            raise FixtureError("B6 issuer result lacks its exact fault ledger")
        ledger["signal_restore"] = restored

    after = _inventory(lineage.control_group)
    _revalidate_directory_authorities(config)
    final_inventory_proof = _require_final_inventory(
        execution, baseline, after, result
    )
    receipt = _base_receipt(config, identity)
    receipt.update(
        {
            "outcome": result.pop("outcome"),
            "baseline_inventory": baseline,
            "backend_open_inventory": backend_open,
            "after_inventory": after,
            "final_inventory_proof": final_inventory_proof,
            "case_result": result,
        }
    )
    _revalidate_directory_authorities(config)
    _write_receipt(
        _absolute_text(config, "receipt_directory"),
        _receipt_component(config, "receipt_name"),
        receipt,
    )
    return 0


def _helper_sentinel(path: str) -> int:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0)
    )
    fd = os.open(path, flags, 0o600)
    try:
        _write_all(fd, b"executed\n")
        os.fsync(fd)
    finally:
        os.close(fd)
    return 0


def _helper_emit(count_text: str) -> int:
    if not count_text.isascii() or not count_text.isdecimal():
        return 64
    count = int(count_text, 10)
    stdout_block, stderr_block = _binary_blocks()
    offset = 0
    while offset < count:
        length = min(len(stdout_block), count - offset)
        _write_all(1, stdout_block[:length])
        _write_all(2, stderr_block[:length])
        offset += length
    return 0


def _execute_helper(arguments: Sequence[str]) -> int:
    if not arguments:
        return 64
    mode = arguments[0]
    values = arguments[1:]
    if mode == "sentinel" and len(values) == 1:
        return _helper_sentinel(values[0])
    if mode == "exit" and len(values) == 1 and values[0].isascii() and values[0].isdecimal():
        code = int(values[0], 10)
        return code if 0 <= code <= 255 else 64
    if mode == "signal" and len(values) == 1 and values[0].isascii() and values[0].isdecimal():
        number = int(values[0], 10)
        if number not in {int(item) for item in signal.valid_signals()}:
            return 64
        signal.raise_signal(number)
        return 65
    if mode == "core" and not values:
        os.abort()
    if mode == "emit" and len(values) == 1:
        return _helper_emit(values[0])
    return 64


def _self_check() -> int:
    stdout, stderr = _binary_blocks()
    if len(stdout) != 4096 or len(stderr) != 4096:
        raise FixtureError("deterministic binary block length mismatch")
    if b"\x00" not in stdout or b"\xff" not in stderr:
        raise FixtureError("deterministic binary blocks lack binary edge bytes")
    if frozenset(_CASE_VARIANTS) != frozenset(f"B{index}" for index in range(9)):
        raise FixtureError("B0-B8 matrix is incomplete")
    if _CASE_VARIANTS["B6"] != frozenset(_B6_ABI):
        raise FixtureError("B6 variant set and frozen ABI differ")
    receipt = {
        "schema": _RECEIPT_SCHEMA,
        "outcome": "SELF_CHECK_PASS",
        "case_variants": {
            key: sorted(value) for key, value in sorted(_CASE_VARIANTS.items())
        },
        "b6_abi": _B6_ABI,
        "accepted_spawn_backend_sha256": _ACCEPTED_SPAWN_BACKEND_SHA256,
    }
    _write_all(1, _canonical_json(receipt))
    return 0


def main(arguments: Sequence[str]) -> int:
    if tuple(arguments) == ("--self-check",):
        return _self_check()
    if len(arguments) == 2 and arguments[0] == "--config":
        return _execute_case(arguments[1])
    if len(arguments) == 2 and arguments[0] == "--plan":
        return _execute_plan(arguments[1])
    if len(arguments) >= 1 and arguments[0] == "--helper":
        return _execute_helper(arguments[1:])
    raise FixtureError(
        "usage: generic_backend_formal_case.py --plan ABSOLUTE_JSON, "
        "--config ABSOLUTE_JSON, "
        "--helper MODE ..., or --self-check"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except FixtureError as error:
        _write_all(2, f"FORMAL_FIXTURE_ERROR: {error}\n".encode("utf-8", "strict"))
        raise SystemExit(70)
