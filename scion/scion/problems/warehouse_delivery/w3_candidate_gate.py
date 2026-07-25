"""Problem-owned closure of one not-yet-installed Warehouse W3 candidate.

The gate consumes producer-owned exact wheel and environment receipt types.
``CandidateNamespaceFinalProbeRef`` is deliberately only a gate-local adapter:
it binds candidate and non-root namespace-final probes to the digest of their
external evidence without claiming that root relocation has happened. The sole final
canonical output owned here is ``CandidateGateReceipt``.

This module has no root, mount, D-Bus, cgroup mutation, nonce claim, or
StartUnit implementation.  Its final filesystem inspector is read-only and
the only inspector type accepted by the production gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Protocol

from scion.problems.warehouse_delivery.w3_composition import (
    EXPECTED_MANIFEST_NAME,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_NONCE_LEDGER_PARENT,
    EXPECTED_ROWS,
    EXPECTED_SOURCE_TREE_IDENTITY_SHA256,
    WarehouseW3LaunchReadyFact,
    inspect_w3_launch_readiness,
)
from scion.problems.warehouse_delivery.w3_environment_receipts import (
    EnvironmentProbeFact,
    NamespaceProbeExecutionFact,
    WarehouseEnvironmentContentReceipt,
    derive_final_environment_path,
    validate_environment_probe_fact,
)
from scion.problems.warehouse_delivery.w3_installation import (
    CandidateRootIdentity,
    CandidateVerificationReceipt,
    PreparedCandidate,
    derive_launch_id,
    verify_candidate,
)
from scion.problems.warehouse_delivery.w3_wheel import (
    OfflineDoubleWheelArtifact,
    OfflineDoubleWheelReceipt,
    verify_offline_double_wheel_artifact,
)
from scion.runtime.execution.environment_integrity import EnvironmentContentReceipt

EXPECTED_CANDIDATE_COMPOSITION_STATE = (
    "COMPOSITION_READY_EXTERNAL_INSTALLATION_REQUIRED"
)
EXPECTED_CELL_COUNT = 43
W3_WHEEL_LOGICAL_PATH = "artifacts/scion-w3-offline-double.whl"
W3_WHEEL_SEALED_PATH = "sealed/artifacts/scion-w3-offline-double.whl"
W3_WHEEL_RECEIPT_LOGICAL_PATH = "receipts/offline-double-wheel.v4.json"
W3_WHEEL_RECEIPT_SEALED_PATH = "sealed/receipts/offline-double-wheel.v4.json"

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_ABSENCE_ROLES = (
    "artifacts",
    "authority_entry",
    "cgroup",
    "close_unit_dropin",
    "close_unit_template",
    "control",
    "environment_root",
    "external_nonce_claim",
    "installation_entry",
    "invocation_nonce_claim",
    "process",
    "projection_root",
    "raw",
    "run_unit_dropin",
    "run_unit_template",
    "sealed_root",
    "terminal",
)
_PATH_ABSENCE_ROLES = frozenset(
    {
        "artifacts",
        "authority_entry",
        "control",
        "close_unit_dropin",
        "close_unit_template",
        "environment_root",
        "external_nonce_claim",
        "installation_entry",
        "invocation_nonce_claim",
        "projection_root",
        "raw",
        "run_unit_dropin",
        "run_unit_template",
        "sealed_root",
        "terminal",
        "cgroup",
    }
)
_SIMULATED_FINAL_SUFFIX = ("var", "lib", "scion", "environments", "w3")
_UINT64_MAX = (1 << 64) - 1


class WarehouseW3CandidateGateError(RuntimeError):
    """The candidate artifact, dry-root, or absence closure differs."""


def derive_namespace_probe_evidence_sha256(
    semantic_raw: bytes,
    candidate_probe_raw: bytes,
    namespace_probe_raw: bytes,
    namespace_execution_raw: bytes,
) -> str:
    """Derive the complete non-root namespace probe evidence identity."""

    if any(
        type(item) is not bytes or not item
        for item in (
            semantic_raw,
            candidate_probe_raw,
            namespace_probe_raw,
            namespace_execution_raw,
        )
    ):
        raise TypeError("namespace probe evidence inputs must be nonempty bytes")
    return hashlib.sha256(
        b"scion.w3-candidate-namespace-final-probe-evidence.v1\0"
        + semantic_raw
        + candidate_probe_raw
        + namespace_probe_raw
        + namespace_execution_raw
    ).hexdigest()


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
        raise WarehouseW3CandidateGateError(
            "candidate gate value is not canonical JSON data"
        ) from exc


def _decode_canonical(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError(f"{label} must be exact bytes")

    def mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains a duplicate field")
            result[key] = value
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
        raise WarehouseW3CandidateGateError(f"{label} is not canonical JSON") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3CandidateGateError(f"{label} bytes are not canonical")
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
        raise WarehouseW3CandidateGateError(f"{label} fields differ")
    return value


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3CandidateGateError(f"{field} is not one SHA-256 value")
    return value


def _uint(
    value: object,
    *,
    field: str,
    maximum: int = _UINT64_MAX,
) -> int:
    if type(value) is not int or value < 0 or value > maximum:
        raise WarehouseW3CandidateGateError(
            f"{field} is not one bounded unsigned integer"
        )
    return value


def _bounded_text(value: object, *, field: str, maximum: int = 4096) -> str:
    if type(value) is not str or not value:
        raise WarehouseW3CandidateGateError(f"{field} is not exact text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise WarehouseW3CandidateGateError(f"{field} is not UTF-8") from exc
    if len(encoded) > maximum or any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise WarehouseW3CandidateGateError(f"{field} is not bounded text")
    return value


def _absolute_path(value: object, *, field: str) -> str:
    text = _bounded_text(value, field=field)
    pure = PurePosixPath(text)
    if (
        not pure.is_absolute()
        or text == "/"
        or text.startswith("//")
        or str(pure) != text
        or any(part in {"", ".", ".."} for part in pure.parts[1:])
    ):
        raise WarehouseW3CandidateGateError(
            f"{field} is not one canonical absolute path"
        )
    return text


def _new(cls: type[object], fields: Mapping[str, object]) -> object:
    instance = object.__new__(cls)
    for name, value in fields.items():
        object.__setattr__(instance, name, value)
    return instance


def _false_controls(value: Mapping[str, object], *, label: str) -> None:
    if any(value.get(name) is not False for name in ("retry", "resume", "reuse")):
        raise WarehouseW3CandidateGateError(f"{label} enables retry, resume, or reuse")


def _candidate_root_identity(candidate_root: Path) -> CandidateRootIdentity:
    if not isinstance(candidate_root, Path):
        raise TypeError("candidate_root must be Path")
    text = _absolute_path(str(candidate_root), field="candidate_root")
    try:
        named = os.lstat(candidate_root)
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISDIR(named.st_mode)
            or str(candidate_root.resolve(strict=True)) != text
        ):
            raise WarehouseW3CandidateGateError(
                "candidate_root is not one canonical no-follow directory"
            )
        flags = os.O_RDONLY | os.O_CLOEXEC
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(candidate_root, flags)
        opened = os.fstat(descriptor)
    except WarehouseW3CandidateGateError:
        raise
    except OSError as exc:
        raise WarehouseW3CandidateGateError(
            "candidate_root cannot be reopened"
        ) from exc
    finally:
        if "descriptor" in locals():
            os.close(descriptor)
    if CandidateRootIdentity.from_stat_result(named) != (
        CandidateRootIdentity.from_stat_result(opened)
    ):
        raise WarehouseW3CandidateGateError("candidate_root changed while reopened")
    return CandidateRootIdentity.from_stat_result(opened)


def _bounded_root_identity(value: object) -> CandidateRootIdentity:
    identity = CandidateRootIdentity.from_mapping(value)
    for name in ("device", "inode", "uid", "gid", "nlink"):
        _uint(
            getattr(identity, name),
            field=f"root identity.{name}",
        )
    _uint(identity.mode, field="root identity.mode", maximum=0o7777)
    return identity


def _derived_absence_subjects(
    *,
    accepted_root: str,
    launch_id: str,
    nonce: str,
    authority_sha256: str,
    installation_sha256: str,
    environment_receipt_sha256: str,
) -> dict[str, str]:
    root = PurePosixPath(_absolute_path(accepted_root, field="absence accepted_root"))
    launch = _sha256(launch_id, field="absence launch_id")
    nonce_value = _sha256(nonce, field="absence nonce")
    installation = _sha256(
        installation_sha256,
        field="absence installation_sha256",
    )
    authority = _sha256(
        authority_sha256,
        field="absence authority_sha256",
    )
    environment = _sha256(
        environment_receipt_sha256,
        field="absence environment_receipt_sha256",
    )
    terminal = root / "control" / "invocation"
    run_unit = f"scion-w3@{launch}.service"
    close_unit = f"scion-w3-close@{launch}.service"
    return {
        "artifacts": str(terminal / "artifacts"),
        "authority_entry": (f"/var/lib/scion/authorities/w3/{authority}.json"),
        "cgroup": ("/sys/fs/cgroup/system.slice/" f"scion-w3@{launch}.service"),
        "close_unit_dropin": f"/etc/systemd/system/{close_unit}.d",
        "close_unit_template": "/etc/systemd/system/scion-w3-close@.service",
        "control": str(terminal / "control"),
        "environment_root": f"/var/lib/scion/environments/w3/{environment}",
        "external_nonce_claim": (
            f"{EXPECTED_NONCE_LEDGER_PARENT}/{nonce_value}.claim.json"
        ),
        "installation_entry": (f"/var/lib/scion/installations/w3/{launch}.json"),
        "invocation_nonce_claim": str(
            terminal / "control" / "invocation_claimed.v1.json"
        ),
        "process": (f"scion-w3@{launch}.service:" f"{nonce_value}:{installation}"),
        "projection_root": f"/var/lib/scion/projections/w3/{launch}",
        "raw": str(terminal / "raw"),
        "run_unit_dropin": f"/etc/systemd/system/{run_unit}.d",
        "run_unit_template": "/etc/systemd/system/scion-w3@.service",
        "sealed_root": (f"/var/lib/scion/sealed/w3/{EXPECTED_MANIFEST_SHA256}"),
        "terminal": str(terminal),
    }


def _absence_observation_sha256(
    *,
    role: str,
    subject: str,
    candidate_verification_sha256: str,
    double_wheel_receipt_sha256: str,
    semantic_environment_receipt_sha256: str,
    namespace_probe_ref_sha256: str,
) -> str:
    return hashlib.sha256(
        b"scion.w3-candidate-absence-observation.v2\0"
        + _canonical_json(
            {
                "role": role,
                "subject": subject,
                "state": "ABSENT",
                "candidate_verification_sha256": (candidate_verification_sha256),
                "double_wheel_receipt_sha256": (double_wheel_receipt_sha256),
                "semantic_environment_receipt_sha256": (
                    semantic_environment_receipt_sha256
                ),
                "namespace_probe_ref_sha256": (namespace_probe_ref_sha256),
            }
        )
    ).hexdigest()


def _readonly_tree_inventory(
    accepted_root: Path,
) -> tuple[CandidateRootIdentity, str, int]:
    root_text = _absolute_path(str(accepted_root), field="accepted_root")
    identity = _candidate_root_identity(accepted_root)

    def signature(value: os.stat_result) -> tuple[int, ...]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_uid,
            value.st_gid,
            value.st_nlink,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    def scan() -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        for directory, names, files in os.walk(
            accepted_root,
            topdown=True,
            followlinks=False,
        ):
            names.sort()
            files.sort()
            base = Path(directory)
            for child_name in (*names, *files):
                child = base / child_name
                metadata = os.lstat(child)
                relative = child.relative_to(accepted_root).as_posix()
                mode = stat.S_IMODE(metadata.st_mode)
                if stat.S_ISLNK(metadata.st_mode):
                    raise WarehouseW3CandidateGateError(
                        "accepted_root inventory contains a linked entry"
                    )
                if stat.S_ISDIR(metadata.st_mode):
                    kind = "directory"
                    size = 0
                    digest: str | None = None
                elif stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1:
                    kind = "regular"
                    size = metadata.st_size
                    digest_object = hashlib.sha256()
                    flags = os.O_RDONLY | os.O_CLOEXEC
                    if hasattr(os, "O_NOFOLLOW"):
                        flags |= os.O_NOFOLLOW
                    descriptor = os.open(child, flags)
                    try:
                        opened = os.fstat(descriptor)
                        if signature(opened) != signature(metadata):
                            raise WarehouseW3CandidateGateError(
                                "accepted_root file changed before read"
                            )
                        while True:
                            chunk = os.read(descriptor, 1024 * 1024)
                            if not chunk:
                                break
                            digest_object.update(chunk)
                        after = os.fstat(descriptor)
                    finally:
                        os.close(descriptor)
                    named_after = os.lstat(child)
                    if signature(after) != signature(metadata) or signature(
                        named_after
                    ) != signature(metadata):
                        raise WarehouseW3CandidateGateError(
                            "accepted_root file changed during read"
                        )
                    digest = digest_object.hexdigest()
                else:
                    raise WarehouseW3CandidateGateError(
                        "accepted_root contains a special or linked entry"
                    )
                entries.append(
                    {
                        "path": relative,
                        "kind": kind,
                        "mode": mode,
                        "size_bytes": size,
                        "sha256": digest,
                    }
                )
        return entries

    root_flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        root_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        root_flags |= os.O_NOFOLLOW
    root_fd = -1
    try:
        root_before = os.lstat(accepted_root)
        root_fd = os.open(accepted_root, root_flags)
        root_opened = os.fstat(root_fd)
        if signature(root_opened) != signature(root_before):
            raise WarehouseW3CandidateGateError(
                "accepted_root changed before read-only acquisition"
            )
        entries = scan()
        root_middle = os.lstat(accepted_root)
        reopened_entries = scan()
        root_after = os.lstat(accepted_root)
        root_final = os.fstat(root_fd)
        final_identity = _candidate_root_identity(accepted_root)
    except WarehouseW3CandidateGateError:
        raise
    except OSError as exc:
        raise WarehouseW3CandidateGateError(
            "accepted_root inventory cannot be acquired"
        ) from exc
    finally:
        if root_fd >= 0:
            os.close(root_fd)
    if (
        final_identity != identity
        or signature(root_opened) != signature(root_final)
        or signature(root_before) != signature(root_middle)
        or signature(root_middle) != signature(root_after)
        or entries != reopened_entries
    ):
        raise WarehouseW3CandidateGateError(
            "accepted_root identity or read-only acquisition changed"
        )
    aggregate = hashlib.sha256(
        b"scion.w3-candidate-accepted-root-inventory.v1\0"
        + root_text.encode("utf-8")
        + b"\0"
        + _canonical_json(entries)
    ).hexdigest()
    return identity, aggregate, len(entries)


def reverify_w3_accepted_root(
    accepted_root: Path,
) -> tuple[CandidateRootIdentity, str, int]:
    """Reacquire one stable read-only accepted-root identity and inventory."""

    if not isinstance(accepted_root, Path):
        raise TypeError("accepted_root must be Path")
    return _readonly_tree_inventory(accepted_root)


def _stable_regular_bytes(
    path: Path,
    *,
    label: str,
    maximum: int = 16 * 1024 * 1024,
) -> bytes:
    """Read one regular file through one pinned descriptor without mutation."""

    if not isinstance(path, Path):
        raise TypeError(f"{label} path must be Path")
    _absolute_path(str(path), field=f"{label}.path")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        named_before = os.lstat(path)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (
                opened.st_dev,
                opened.st_ino,
                opened.st_mode,
                opened.st_uid,
                opened.st_gid,
                opened.st_nlink,
                opened.st_size,
                opened.st_mtime_ns,
                opened.st_ctime_ns,
            )
            != (
                named_before.st_dev,
                named_before.st_ino,
                named_before.st_mode,
                named_before.st_uid,
                named_before.st_gid,
                named_before.st_nlink,
                named_before.st_size,
                named_before.st_mtime_ns,
                named_before.st_ctime_ns,
            )
        ):
            raise WarehouseW3CandidateGateError(f"{label} identity differs")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum:
                raise WarehouseW3CandidateGateError(f"{label} exceeds bound")
        opened_after = os.fstat(descriptor)
        named_after = os.lstat(path)
    except WarehouseW3CandidateGateError:
        raise
    except OSError as exc:
        raise WarehouseW3CandidateGateError(f"{label} cannot be read") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    signature = (
        opened.st_dev,
        opened.st_ino,
        opened.st_mode,
        opened.st_uid,
        opened.st_gid,
        opened.st_nlink,
        opened.st_size,
        opened.st_mtime_ns,
        opened.st_ctime_ns,
    )
    if (
        signature
        != (
            opened_after.st_dev,
            opened_after.st_ino,
            opened_after.st_mode,
            opened_after.st_uid,
            opened_after.st_gid,
            opened_after.st_nlink,
            opened_after.st_size,
            opened_after.st_mtime_ns,
            opened_after.st_ctime_ns,
        )
        or signature
        != (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_mode,
            named_after.st_uid,
            named_after.st_gid,
            named_after.st_nlink,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        or size != opened.st_size
    ):
        raise WarehouseW3CandidateGateError(f"{label} changed while read")
    return b"".join(chunks)


def _verify_candidate_wheel_bindings(
    prepared: PreparedCandidate,
    artifact: OfflineDoubleWheelArtifact,
) -> None:
    """Cross-bind the reopened candidate sealed store to the live wheel artifact."""

    receipt = artifact.receipt
    wheel_inputs = tuple(
        item
        for item in prepared.authority.inputs
        if item.logical_path.endswith(".whl") or item.sealed_path.endswith(".whl")
    )
    receipt_inputs = tuple(
        item
        for item in prepared.authority.inputs
        if item.logical_path == W3_WHEEL_RECEIPT_LOGICAL_PATH
        or item.sealed_path == W3_WHEEL_RECEIPT_SEALED_PATH
    )
    if (
        len(wheel_inputs) != 1
        or wheel_inputs[0].logical_path != W3_WHEEL_LOGICAL_PATH
        or wheel_inputs[0].sealed_path != W3_WHEEL_SEALED_PATH
        or wheel_inputs[0].sha256 != receipt.wheel_sha256
        or wheel_inputs[0].size_bytes != receipt.wheel_size_bytes
        or len(receipt_inputs) != 1
        or receipt_inputs[0].logical_path != W3_WHEEL_RECEIPT_LOGICAL_PATH
        or receipt_inputs[0].sealed_path != W3_WHEEL_RECEIPT_SEALED_PATH
        or receipt_inputs[0].sha256 != receipt.raw_sha256
        or receipt_inputs[0].size_bytes != len(receipt.raw)
    ):
        raise WarehouseW3CandidateGateError("candidate wheel authority inputs differ")
    inventory = {item.path: item for item in prepared.sealed_store_receipt.inventory}
    wheel_entry = inventory.get(W3_WHEEL_SEALED_PATH)
    receipt_entry = inventory.get(W3_WHEEL_RECEIPT_SEALED_PATH)
    if (
        wheel_entry is None
        or wheel_entry.kind != "regular"
        or wheel_entry.mode != 0o444
        or wheel_entry.sha256 != receipt.wheel_sha256
        or wheel_entry.size_bytes != receipt.wheel_size_bytes
        or receipt_entry is None
        or receipt_entry.kind != "regular"
        or receipt_entry.mode != 0o444
        or receipt_entry.sha256 != receipt.raw_sha256
        or receipt_entry.size_bytes != len(receipt.raw)
    ):
        raise WarehouseW3CandidateGateError("candidate sealed wheel inventory differs")
    store = prepared.candidate_root / "sealed-store"
    wheel_raw = _stable_regular_bytes(
        store / W3_WHEEL_SEALED_PATH,
        label="candidate sealed wheel",
        maximum=max(receipt.wheel_size_bytes, 1),
    )
    receipt_raw = _stable_regular_bytes(
        store / W3_WHEEL_RECEIPT_SEALED_PATH,
        label="candidate sealed wheel receipt",
        maximum=max(len(receipt.raw), 1),
    )
    if (
        len(wheel_raw) != receipt.wheel_size_bytes
        or hashlib.sha256(wheel_raw).hexdigest() != receipt.wheel_sha256
        or receipt_raw != receipt.raw
    ):
        raise WarehouseW3CandidateGateError("candidate sealed wheel bytes differ")


def _validate_probe(
    fact: EnvironmentProbeFact,
    *,
    phase: str,
    content: WarehouseEnvironmentContentReceipt,
    expected_root: Path,
) -> None:
    try:
        validate_environment_probe_fact(
            fact,
            phase=phase,
            root=expected_root,
            content=content,
        )
    except Exception as exc:
        raise WarehouseW3CandidateGateError(
            f"{phase} environment probe is not cross-bound"
        ) from exc


@dataclass(frozen=True, slots=True, init=False)
class CandidateNamespaceFinalProbeRef:
    """Gate-local binding for one non-root exact-future-path probe."""

    evidence_receipt_sha256: str
    selection_key: str
    launch_id: str
    authority_sha256: str
    installation_sha256: str
    semantic_environment_receipt_sha256: str
    environment_content_receipt_sha256: str
    candidate_probe_sha256: str
    namespace_final_probe_sha256: str
    namespace_probe_execution_sha256: str
    candidate_environment_root: str
    physical_environment_root: str
    visible_environment_root: str
    filesystem_mutated: bool
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "CandidateNamespaceFinalProbeRef":
        del cls
        raise TypeError(
            "CandidateNamespaceFinalProbeRef must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("CandidateNamespaceFinalProbeRef is final")

    @classmethod
    def create(
        cls,
        *,
        evidence_receipt_sha256: str,
        selection_key: str,
        launch_id: str,
        authority_sha256: str,
        installation_sha256: str,
        semantic_environment: WarehouseEnvironmentContentReceipt,
        candidate_probe: EnvironmentProbeFact,
        namespace_final_probe: EnvironmentProbeFact,
        namespace_probe_execution: NamespaceProbeExecutionFact,
    ) -> "CandidateNamespaceFinalProbeRef":
        if type(semantic_environment) is not WarehouseEnvironmentContentReceipt:
            raise TypeError(
                "semantic_environment must be exact "
                "WarehouseEnvironmentContentReceipt"
            )
        if (
            type(candidate_probe) is not EnvironmentProbeFact
            or type(namespace_final_probe) is not EnvironmentProbeFact
            or type(namespace_probe_execution) is not NamespaceProbeExecutionFact
        ):
            raise TypeError("namespace probe dependencies have inexact types")
        _validate_probe(
            candidate_probe,
            phase="candidate",
            content=semantic_environment,
            expected_root=Path(candidate_probe.environment_root),
        )
        _validate_probe(
            namespace_final_probe,
            phase="namespace_final",
            content=semantic_environment,
            expected_root=derive_final_environment_path(semantic_environment),
        )
        execution = NamespaceProbeExecutionFact.from_bytes(
            namespace_probe_execution.raw,
            environment_probe=namespace_final_probe,
        )
        if execution != namespace_probe_execution:
            raise WarehouseW3CandidateGateError(
                "namespace probe execution object differs"
            )
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": "scion.w3-candidate-namespace-final-probe-ref.v1",
                    "evidence_receipt_sha256": evidence_receipt_sha256,
                    "selection_key": selection_key,
                    "launch_id": launch_id,
                    "authority_sha256": authority_sha256,
                    "installation_sha256": installation_sha256,
                    "semantic_environment_receipt_sha256": (
                        semantic_environment.raw_sha256
                    ),
                    "environment_content_receipt_sha256": (
                        semantic_environment.generic_receipt_sha256
                    ),
                    "candidate_probe_sha256": candidate_probe.raw_sha256,
                    "namespace_final_probe_sha256": (namespace_final_probe.raw_sha256),
                    "namespace_probe_execution_sha256": (
                        namespace_probe_execution.raw_sha256
                    ),
                    "candidate_environment_root": (candidate_probe.environment_root),
                    "physical_environment_root": (
                        namespace_probe_execution.physical_environment_root
                    ),
                    "visible_environment_root": (
                        namespace_probe_execution.visible_environment_root
                    ),
                    "filesystem_mutated": False,
                }
            ),
            semantic_environment=semantic_environment,
        )

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        semantic_environment: WarehouseEnvironmentContentReceipt,
    ) -> "CandidateNamespaceFinalProbeRef":
        if type(semantic_environment) is not WarehouseEnvironmentContentReceipt:
            raise TypeError(
                "semantic_environment must be exact "
                "WarehouseEnvironmentContentReceipt"
            )
        value = _exact_fields(
            _decode_canonical(raw, label="candidate namespace-final reference"),
            frozenset(
                {
                    "schema",
                    "evidence_receipt_sha256",
                    "selection_key",
                    "launch_id",
                    "authority_sha256",
                    "installation_sha256",
                    "semantic_environment_receipt_sha256",
                    "environment_content_receipt_sha256",
                    "candidate_probe_sha256",
                    "namespace_final_probe_sha256",
                    "namespace_probe_execution_sha256",
                    "candidate_environment_root",
                    "physical_environment_root",
                    "visible_environment_root",
                    "filesystem_mutated",
                }
            ),
            label="candidate namespace-final reference",
        )
        if (
            value["schema"] != "scion.w3-candidate-namespace-final-probe-ref.v1"
            or value["filesystem_mutated"] is not False
        ):
            raise WarehouseW3CandidateGateError(
                "candidate namespace-final authority differs"
            )
        fields: dict[str, object] = {
            name: _sha256(value[name], field=f"namespace final.{name}")
            for name in (
                "evidence_receipt_sha256",
                "selection_key",
                "launch_id",
                "authority_sha256",
                "installation_sha256",
                "semantic_environment_receipt_sha256",
                "environment_content_receipt_sha256",
                "candidate_probe_sha256",
                "namespace_final_probe_sha256",
                "namespace_probe_execution_sha256",
            )
        }
        if (
            fields["semantic_environment_receipt_sha256"]
            != semantic_environment.raw_sha256
            or fields["environment_content_receipt_sha256"]
            != semantic_environment.generic_receipt_sha256
        ):
            raise WarehouseW3CandidateGateError(
                "candidate namespace-final environment binding differs"
            )
        candidate_root = _absolute_path(
            value["candidate_environment_root"],
            field="candidate environment root",
        )
        physical_root = _absolute_path(
            value["physical_environment_root"],
            field="namespace physical environment root",
        )
        visible_root = _absolute_path(
            value["visible_environment_root"],
            field="namespace visible environment root",
        )
        expected_visible = str(derive_final_environment_path(semantic_environment))
        if (
            candidate_root == physical_root
            or physical_root == visible_root
            or visible_root != expected_visible
        ):
            raise WarehouseW3CandidateGateError(
                "namespace-final physical or visible path differs"
            )
        fields.update(
            {
                "candidate_environment_root": candidate_root,
                "physical_environment_root": physical_root,
                "visible_environment_root": visible_root,
                "filesystem_mutated": False,
                "raw": raw,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        return _new(cls, fields)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class CandidateAbsenceObservation:
    role: str
    subject: str
    observation_sha256: str
    state: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("CandidateAbsenceObservation is final")

    @classmethod
    def from_mapping(cls, value: object) -> "CandidateAbsenceObservation":
        item = _exact_fields(
            value,
            frozenset({"role", "subject", "observation_sha256", "state"}),
            label="candidate absence observation",
        )
        role = item["role"]
        if role not in _ABSENCE_ROLES:
            raise WarehouseW3CandidateGateError(
                "candidate absence observation role differs"
            )
        subject = (
            _absolute_path(item["subject"], field=f"absence.{role}.subject")
            if role in _PATH_ABSENCE_ROLES
            else _bounded_text(item["subject"], field=f"absence.{role}.subject")
        )
        if item["state"] != "ABSENT":
            raise WarehouseW3CandidateGateError(
                "candidate absence observation is not absent"
            )
        return cls(
            role=role,
            subject=subject,
            observation_sha256=_sha256(
                item["observation_sha256"],
                field=f"absence.{role}.observation_sha256",
            ),
            state="ABSENT",
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "role": self.role,
            "subject": self.subject,
            "observation_sha256": self.observation_sha256,
            "state": self.state,
        }


@dataclass(frozen=True, slots=True, init=False)
class CandidateAbsenceFacts:
    selection_key: str
    launch_id: str
    nonce: str
    authority_sha256: str
    installation_sha256: str
    environment_receipt_sha256: str
    accepted_root: str
    candidate_verification_sha256: str
    double_wheel_receipt_sha256: str
    semantic_environment_receipt_sha256: str
    candidate_probe_sha256: str
    namespace_final_probe_sha256: str
    namespace_probe_ref_sha256: str
    namespace_probe_evidence_sha256: str
    observations: tuple[CandidateAbsenceObservation, ...]
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "CandidateAbsenceFacts":
        del cls
        raise TypeError("CandidateAbsenceFacts must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("CandidateAbsenceFacts is final")

    @classmethod
    def create(
        cls,
        *,
        selection_key: str,
        launch_id: str,
        nonce: str,
        authority_sha256: str,
        installation_sha256: str,
        environment_receipt_sha256: str,
        accepted_root: Path,
        candidate_verification_sha256: str,
        double_wheel_receipt_sha256: str,
        semantic_environment_receipt_sha256: str,
        candidate_probe_sha256: str,
        namespace_final_probe_sha256: str,
        namespace_probe_ref_sha256: str,
        namespace_probe_evidence_sha256: str,
        observations: tuple[CandidateAbsenceObservation, ...],
    ) -> "CandidateAbsenceFacts":
        if type(observations) is not tuple or any(
            type(item) is not CandidateAbsenceObservation for item in observations
        ):
            raise TypeError(
                "observations must be exact tuple of CandidateAbsenceObservation"
            )
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": "scion.w3-candidate-absence-facts.v2",
                    "selection_key": selection_key,
                    "launch_id": launch_id,
                    "nonce": nonce,
                    "authority_sha256": authority_sha256,
                    "installation_sha256": installation_sha256,
                    "environment_receipt_sha256": environment_receipt_sha256,
                    "accepted_root": str(accepted_root),
                    "candidate_verification_sha256": (candidate_verification_sha256),
                    "double_wheel_receipt_sha256": (double_wheel_receipt_sha256),
                    "semantic_environment_receipt_sha256": (
                        semantic_environment_receipt_sha256
                    ),
                    "candidate_probe_sha256": candidate_probe_sha256,
                    "namespace_final_probe_sha256": (namespace_final_probe_sha256),
                    "namespace_probe_ref_sha256": (namespace_probe_ref_sha256),
                    "namespace_probe_evidence_sha256": (
                        namespace_probe_evidence_sha256
                    ),
                    "observations": [item.to_mapping() for item in observations],
                }
            )
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CandidateAbsenceFacts":
        value = _exact_fields(
            _decode_canonical(raw, label="candidate absence facts"),
            frozenset(
                {
                    "schema",
                    "selection_key",
                    "launch_id",
                    "nonce",
                    "authority_sha256",
                    "installation_sha256",
                    "environment_receipt_sha256",
                    "accepted_root",
                    "candidate_verification_sha256",
                    "double_wheel_receipt_sha256",
                    "semantic_environment_receipt_sha256",
                    "candidate_probe_sha256",
                    "namespace_final_probe_sha256",
                    "namespace_probe_ref_sha256",
                    "namespace_probe_evidence_sha256",
                    "observations",
                }
            ),
            label="candidate absence facts",
        )
        if value["schema"] != "scion.w3-candidate-absence-facts.v2":
            raise WarehouseW3CandidateGateError(
                "candidate absence facts schema differs"
            )
        raw_observations = value["observations"]
        if type(raw_observations) is not list:
            raise WarehouseW3CandidateGateError(
                "candidate absence observations are not an array"
            )
        observations = tuple(
            CandidateAbsenceObservation.from_mapping(item) for item in raw_observations
        )
        if tuple(item.role for item in observations) != _ABSENCE_ROLES:
            raise WarehouseW3CandidateGateError(
                "candidate absence observation inventory differs"
            )
        accepted_root = _absolute_path(
            value["accepted_root"],
            field="absence accepted_root",
        )
        launch_id = _sha256(value["launch_id"], field="absence launch_id")
        nonce = _sha256(value["nonce"], field="absence nonce")
        installation = _sha256(
            value["installation_sha256"],
            field="absence installation_sha256",
        )
        authority = _sha256(
            value["authority_sha256"],
            field="absence authority_sha256",
        )
        environment = _sha256(
            value["environment_receipt_sha256"],
            field="absence environment_receipt_sha256",
        )
        bindings = {
            name: _sha256(value[name], field=f"absence {name}")
            for name in (
                "candidate_verification_sha256",
                "double_wheel_receipt_sha256",
                "semantic_environment_receipt_sha256",
                "candidate_probe_sha256",
                "namespace_final_probe_sha256",
                "namespace_probe_ref_sha256",
                "namespace_probe_evidence_sha256",
            )
        }
        subjects = _derived_absence_subjects(
            accepted_root=accepted_root,
            launch_id=launch_id,
            nonce=nonce,
            authority_sha256=authority,
            installation_sha256=installation,
            environment_receipt_sha256=environment,
        )
        for observation in observations:
            if observation.subject != subjects[
                observation.role
            ] or observation.observation_sha256 != _absence_observation_sha256(
                role=observation.role,
                subject=observation.subject,
                candidate_verification_sha256=bindings["candidate_verification_sha256"],
                double_wheel_receipt_sha256=bindings["double_wheel_receipt_sha256"],
                semantic_environment_receipt_sha256=bindings[
                    "semantic_environment_receipt_sha256"
                ],
                namespace_probe_ref_sha256=bindings["namespace_probe_ref_sha256"],
            ):
                raise WarehouseW3CandidateGateError(
                    "candidate absence observation is not mechanically derived"
                )
        return _new(
            cls,
            {
                "selection_key": _sha256(
                    value["selection_key"],
                    field="absence selection_key",
                ),
                "launch_id": launch_id,
                "nonce": nonce,
                "authority_sha256": authority,
                "installation_sha256": installation,
                "environment_receipt_sha256": environment,
                "accepted_root": accepted_root,
                **bindings,
                "observations": observations,
                "raw": raw,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
            },
        )  # type: ignore[return-value]


@dataclass(frozen=True, slots=True, init=False)
class CandidateCompositionInspection:
    """Closed result returned by the injected read-only inspector."""

    selection_key: str
    launch_id: str
    nonce: str
    authority_sha256: str
    installation_sha256: str
    accepted_root: str
    accepted_root_identity: CandidateRootIdentity
    accepted_root_read_only: bool
    accepted_root_inventory_sha256: str
    accepted_root_inventory_count: int
    candidate_verification_sha256: str
    double_wheel_receipt_sha256: str
    semantic_environment_receipt_sha256: str
    candidate_probe_sha256: str
    namespace_final_probe_sha256: str
    namespace_probe_ref_sha256: str
    namespace_probe_evidence_sha256: str
    manifest_sha256: str
    source_tree_identity_sha256: str
    state: str
    external_installation_required: bool
    cell_count: int
    job_count: int
    formal_jobs_started: int
    formal_execution_authorized: bool
    filesystem_mutated: bool
    absence_facts_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "CandidateCompositionInspection":
        del cls
        raise TypeError(
            "CandidateCompositionInspection must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("CandidateCompositionInspection is final")

    @classmethod
    def create(
        cls,
        *,
        selection_key: str,
        launch_id: str,
        nonce: str,
        authority_sha256: str,
        installation_sha256: str,
        accepted_root: Path,
        accepted_root_identity: CandidateRootIdentity,
        accepted_root_inventory_sha256: str,
        accepted_root_inventory_count: int,
        candidate_verification_sha256: str,
        double_wheel_receipt_sha256: str,
        semantic_environment_receipt_sha256: str,
        candidate_probe_sha256: str,
        namespace_final_probe_sha256: str,
        namespace_probe_ref_sha256: str,
        namespace_probe_evidence_sha256: str,
        manifest_sha256: str,
        source_tree_identity_sha256: str,
        state: str,
        external_installation_required: bool,
        cell_count: int,
        job_count: int,
        formal_jobs_started: int,
        formal_execution_authorized: bool,
        filesystem_mutated: bool,
        absence_facts: CandidateAbsenceFacts,
    ) -> "CandidateCompositionInspection":
        if not isinstance(accepted_root, Path):
            raise TypeError("accepted_root must be Path")
        if type(absence_facts) is not CandidateAbsenceFacts:
            raise TypeError("absence_facts must be exact CandidateAbsenceFacts")
        if type(accepted_root_identity) is not CandidateRootIdentity:
            raise TypeError(
                "accepted_root_identity must be exact CandidateRootIdentity"
            )
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": "scion.w3-candidate-composition-inspection.v2",
                    "selection_key": selection_key,
                    "launch_id": launch_id,
                    "nonce": nonce,
                    "authority_sha256": authority_sha256,
                    "installation_sha256": installation_sha256,
                    "accepted_root": str(accepted_root),
                    "accepted_root_identity": (accepted_root_identity.to_mapping()),
                    "accepted_root_read_only": True,
                    "accepted_root_inventory_sha256": (accepted_root_inventory_sha256),
                    "accepted_root_inventory_count": (accepted_root_inventory_count),
                    "candidate_verification_sha256": (candidate_verification_sha256),
                    "double_wheel_receipt_sha256": (double_wheel_receipt_sha256),
                    "semantic_environment_receipt_sha256": (
                        semantic_environment_receipt_sha256
                    ),
                    "candidate_probe_sha256": candidate_probe_sha256,
                    "namespace_final_probe_sha256": (namespace_final_probe_sha256),
                    "namespace_probe_ref_sha256": (namespace_probe_ref_sha256),
                    "namespace_probe_evidence_sha256": (
                        namespace_probe_evidence_sha256
                    ),
                    "manifest_sha256": manifest_sha256,
                    "source_tree_identity_sha256": source_tree_identity_sha256,
                    "state": state,
                    "external_installation_required": (external_installation_required),
                    "cell_count": cell_count,
                    "job_count": job_count,
                    "formal_jobs_started": formal_jobs_started,
                    "formal_execution_authorized": formal_execution_authorized,
                    "filesystem_mutated": filesystem_mutated,
                    "absence_facts_sha256": absence_facts.raw_sha256,
                }
            )
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CandidateCompositionInspection":
        value = _exact_fields(
            _decode_canonical(raw, label="candidate composition inspection"),
            frozenset(
                {
                    "schema",
                    "selection_key",
                    "launch_id",
                    "nonce",
                    "authority_sha256",
                    "installation_sha256",
                    "accepted_root",
                    "accepted_root_identity",
                    "accepted_root_read_only",
                    "accepted_root_inventory_sha256",
                    "accepted_root_inventory_count",
                    "candidate_verification_sha256",
                    "double_wheel_receipt_sha256",
                    "semantic_environment_receipt_sha256",
                    "candidate_probe_sha256",
                    "namespace_final_probe_sha256",
                    "namespace_probe_ref_sha256",
                    "namespace_probe_evidence_sha256",
                    "manifest_sha256",
                    "source_tree_identity_sha256",
                    "state",
                    "external_installation_required",
                    "cell_count",
                    "job_count",
                    "formal_jobs_started",
                    "formal_execution_authorized",
                    "filesystem_mutated",
                    "absence_facts_sha256",
                }
            ),
            label="candidate composition inspection",
        )
        if (
            value["schema"] != "scion.w3-candidate-composition-inspection.v2"
            or value["manifest_sha256"] != EXPECTED_MANIFEST_SHA256
            or value["source_tree_identity_sha256"]
            != EXPECTED_SOURCE_TREE_IDENTITY_SHA256
            or value["state"] != EXPECTED_CANDIDATE_COMPOSITION_STATE
            or value["external_installation_required"] is not True
            or type(value["cell_count"]) is not int
            or value["cell_count"] != EXPECTED_CELL_COUNT
            or type(value["job_count"]) is not int
            or value["job_count"] != EXPECTED_ROWS
            or type(value["formal_jobs_started"]) is not int
            or value["formal_jobs_started"] != 0
            or value["formal_execution_authorized"] is not False
            or value["filesystem_mutated"] is not False
            or value["accepted_root_read_only"] is not True
        ):
            raise WarehouseW3CandidateGateError(
                "candidate composition inspection state differs"
            )
        return _new(
            cls,
            {
                "selection_key": _sha256(
                    value["selection_key"],
                    field="inspection selection_key",
                ),
                "launch_id": _sha256(
                    value["launch_id"],
                    field="inspection launch_id",
                ),
                "nonce": _sha256(
                    value["nonce"],
                    field="inspection nonce",
                ),
                "authority_sha256": _sha256(
                    value["authority_sha256"],
                    field="inspection authority_sha256",
                ),
                "installation_sha256": _sha256(
                    value["installation_sha256"],
                    field="inspection installation_sha256",
                ),
                "accepted_root": _absolute_path(
                    value["accepted_root"],
                    field="inspection accepted_root",
                ),
                "accepted_root_identity": _bounded_root_identity(
                    value["accepted_root_identity"]
                ),
                "accepted_root_read_only": True,
                "accepted_root_inventory_sha256": _sha256(
                    value["accepted_root_inventory_sha256"],
                    field="inspection accepted_root_inventory_sha256",
                ),
                "accepted_root_inventory_count": _uint(
                    value["accepted_root_inventory_count"],
                    field="inspection accepted_root_inventory_count",
                ),
                **{
                    name: _sha256(value[name], field=f"inspection {name}")
                    for name in (
                        "candidate_verification_sha256",
                        "double_wheel_receipt_sha256",
                        "semantic_environment_receipt_sha256",
                        "candidate_probe_sha256",
                        "namespace_final_probe_sha256",
                        "namespace_probe_ref_sha256",
                        "namespace_probe_evidence_sha256",
                    )
                },
                "manifest_sha256": EXPECTED_MANIFEST_SHA256,
                "source_tree_identity_sha256": (EXPECTED_SOURCE_TREE_IDENTITY_SHA256),
                "state": EXPECTED_CANDIDATE_COMPOSITION_STATE,
                "external_installation_required": True,
                "cell_count": EXPECTED_CELL_COUNT,
                "job_count": EXPECTED_ROWS,
                "formal_jobs_started": 0,
                "formal_execution_authorized": False,
                "filesystem_mutated": False,
                "absence_facts_sha256": _sha256(
                    value["absence_facts_sha256"],
                    field="inspection absence_facts_sha256",
                ),
                "raw": raw,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
            },
        )  # type: ignore[return-value]


class CandidateCompositionInspector(Protocol):
    """Injectable read-only composition/dry-root/absence acquisition seam."""

    def inspect(
        self,
        *,
        accepted_root: Path,
        candidate_root: Path,
        nonce: str,
        manifest_sha256: str,
        prepared_candidate: PreparedCandidate,
        candidate_verification: CandidateVerificationReceipt,
        double_wheel: OfflineDoubleWheelReceipt,
        semantic_environment: WarehouseEnvironmentContentReceipt,
        candidate_probe: EnvironmentProbeFact,
        namespace_final_probe: EnvironmentProbeFact,
        namespace_probe_execution: NamespaceProbeExecutionFact,
        namespace_probe_ref: CandidateNamespaceFinalProbeRef,
    ) -> tuple[CandidateCompositionInspection, CandidateAbsenceFacts]:
        """Reacquire the exact candidate-state facts without mutation."""


class FilesystemCandidateCompositionInspector:
    """Final read-only filesystem/procfs inspector used by production closure."""

    __slots__ = ()

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("FilesystemCandidateCompositionInspector is final")

    def inspect(
        self,
        *,
        accepted_root: Path,
        candidate_root: Path,
        nonce: str,
        manifest_sha256: str,
        prepared_candidate: PreparedCandidate,
        candidate_verification: CandidateVerificationReceipt,
        double_wheel: OfflineDoubleWheelReceipt,
        semantic_environment: WarehouseEnvironmentContentReceipt,
        candidate_probe: EnvironmentProbeFact,
        namespace_final_probe: EnvironmentProbeFact,
        namespace_probe_ref: CandidateNamespaceFinalProbeRef,
    ) -> tuple[CandidateCompositionInspection, CandidateAbsenceFacts]:
        if (
            type(prepared_candidate) is not PreparedCandidate
            or prepared_candidate.candidate_root != candidate_root
            or prepared_candidate.verification_receipt != candidate_verification
        ):
            raise WarehouseW3CandidateGateError(
                "filesystem inspector prepared candidate differs"
            )
        if manifest_sha256 != EXPECTED_MANIFEST_SHA256:
            raise WarehouseW3CandidateGateError("filesystem inspector manifest differs")
        candidate_identity = _candidate_root_identity(candidate_root)
        sidecar_paths = (
            candidate_root / "authority.json",
            candidate_root / "installation.json",
            candidate_root / "units/scion-w3@.service",
            candidate_root / "units/scion-w3-close@.service",
        )
        sidecars = tuple(
            _stable_regular_bytes(path, label=f"candidate sidecar {path.name}")
            for path in sidecar_paths
        )
        if (
            sidecars[0] != prepared_candidate.authority.raw
            or sidecars[1] != prepared_candidate.installation.raw
        ):
            raise WarehouseW3CandidateGateError(
                "candidate authority or installation sidecar differs"
            )
        root_identity, inventory_sha, inventory_count = _readonly_tree_inventory(
            accepted_root
        )
        manifest_raw = _stable_regular_bytes(
            accepted_root / EXPECTED_MANIFEST_NAME,
            label="accepted W3 manifest",
        )
        try:
            manifest = json.loads(manifest_raw.decode("utf-8", "strict"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise WarehouseW3CandidateGateError(
                "accepted W3 manifest cannot be decoded"
            ) from exc
        if type(manifest) is not dict:
            raise WarehouseW3CandidateGateError("accepted W3 manifest is not a mapping")
        cells = manifest.get("cells")
        jobs = manifest.get("jobs")
        formal_jobs_started = manifest.get("formal_jobs_started")
        formal_execution_authorized = manifest.get("formal_execution_authorized")
        if (
            type(cells) is not list
            or type(jobs) is not list
            or type(formal_jobs_started) is not int
            or type(formal_execution_authorized) is not bool
        ):
            raise WarehouseW3CandidateGateError("accepted W3 manifest dry facts differ")
        readiness = inspect_w3_launch_readiness(
            accepted_root,
            sidecars[0],
            sidecars[1],
            sidecars[2],
            sidecars[3],
        )
        if type(readiness) is not WarehouseW3LaunchReadyFact:
            raise WarehouseW3CandidateGateError(
                "W3 launch-readiness verifier returned an ambiguous fact"
            )
        external_installation_paths = (
            Path(
                "/var/lib/scion/installations/w3/"
                f"{readiness.installation.launch_id}.json"
            ),
            Path(readiness.installation.authority_path),
            Path(readiness.installation.projection_root),
        )
        if any(os.path.lexists(path) for path in external_installation_paths):
            raise WarehouseW3CandidateGateError("external W3 installation is present")
        sidecars_after = tuple(
            _stable_regular_bytes(path, label=f"candidate sidecar {path.name}")
            for path in sidecar_paths
        )
        final_root_identity, final_inventory_sha, final_inventory_count = (
            _readonly_tree_inventory(accepted_root)
        )
        if (
            sidecars_after != sidecars
            or _candidate_root_identity(candidate_root) != candidate_identity
            or final_root_identity != root_identity
            or final_inventory_sha != inventory_sha
            or final_inventory_count != inventory_count
        ):
            raise WarehouseW3CandidateGateError(
                "candidate or accepted root changed during readiness inspection"
            )
        actual_manifest_sha256 = hashlib.sha256(manifest_raw).hexdigest()
        if (
            readiness.state != EXPECTED_CANDIDATE_COMPOSITION_STATE
            or readiness.external_installation_required is not True
            or readiness.authority != prepared_candidate.authority
            or readiness.installation != prepared_candidate.installation
            or readiness._authority_raw != sidecars[0]
            or readiness._installation_raw != sidecars[1]
            or readiness._run_template_raw != sidecars[2]
            or readiness._close_template_raw != sidecars[3]
            or readiness.source_tree_identity_sha256
            != EXPECTED_SOURCE_TREE_IDENTITY_SHA256
            or readiness.terminal_policy.expected_rows != len(jobs)
            or readiness.formal_execution_authorized is not False
            or readiness.filesystem_mutated is not False
            or actual_manifest_sha256 != manifest_sha256
            or len(cells) != EXPECTED_CELL_COUNT
            or len(jobs) != EXPECTED_ROWS
            or formal_jobs_started != 0
            or formal_execution_authorized is not False
        ):
            raise WarehouseW3CandidateGateError(
                "reacquired W3 launch-readiness facts differ"
            )
        subjects = _derived_absence_subjects(
            accepted_root=str(accepted_root),
            launch_id=namespace_probe_ref.launch_id,
            nonce=nonce,
            authority_sha256=candidate_verification.authority_sha256,
            installation_sha256=candidate_verification.installation_sha256,
            environment_receipt_sha256=(
                candidate_verification.environment_receipt_sha256
            ),
        )
        if (
            subjects["authority_entry"] != readiness.installation.authority_path
            or subjects["installation_entry"]
            != (
                "/var/lib/scion/installations/w3/"
                f"{readiness.installation.launch_id}.json"
            )
            or subjects["projection_root"] != readiness.installation.projection_root
            or subjects["sealed_root"] != readiness.installation.sealed_root
            or subjects["environment_root"] != readiness.installation.environment_root
            or subjects["terminal"] != readiness.installation.terminal_root
        ):
            raise WarehouseW3CandidateGateError(
                "external installation absence paths do not rederive"
            )
        for role in _PATH_ABSENCE_ROLES:
            if os.path.lexists(subjects[role]):
                raise WarehouseW3CandidateGateError(
                    f"candidate filesystem subject is present: {role}"
                )
        process_token = (f"scion-w3@{namespace_probe_ref.launch_id}.service").encode(
            "ascii"
        )
        try:
            process_entries = tuple(
                item
                for item in Path("/proc").iterdir()
                if item.name.isascii() and item.name.isdecimal()
            )
        except OSError as exc:
            raise WarehouseW3CandidateGateError(
                "procfs cannot be inspected read-only"
            ) from exc
        for process in process_entries:
            for name in ("cmdline", "cgroup"):
                try:
                    raw = (process / name).read_bytes()
                except (FileNotFoundError, ProcessLookupError, PermissionError):
                    continue
                except OSError as exc:
                    raise WarehouseW3CandidateGateError(
                        "procfs process fact is ambiguous"
                    ) from exc
                if len(raw) > 1024 * 1024:
                    raise WarehouseW3CandidateGateError(
                        "procfs process fact exceeds bound"
                    )
                if process_token in raw:
                    raise WarehouseW3CandidateGateError("candidate process is present")
        binding_values = {
            "candidate_verification_sha256": candidate_verification.raw_sha256,
            "double_wheel_receipt_sha256": double_wheel.raw_sha256,
            "semantic_environment_receipt_sha256": (semantic_environment.raw_sha256),
            "candidate_probe_sha256": candidate_probe.raw_sha256,
            "namespace_final_probe_sha256": (namespace_final_probe.raw_sha256),
            "namespace_probe_ref_sha256": namespace_probe_ref.raw_sha256,
            "namespace_probe_evidence_sha256": (
                namespace_probe_ref.evidence_receipt_sha256
            ),
        }
        observations = tuple(
            CandidateAbsenceObservation(
                role=role,
                subject=subjects[role],
                observation_sha256=_absence_observation_sha256(
                    role=role,
                    subject=subjects[role],
                    candidate_verification_sha256=binding_values[
                        "candidate_verification_sha256"
                    ],
                    double_wheel_receipt_sha256=binding_values[
                        "double_wheel_receipt_sha256"
                    ],
                    semantic_environment_receipt_sha256=binding_values[
                        "semantic_environment_receipt_sha256"
                    ],
                    namespace_probe_ref_sha256=binding_values[
                        "namespace_probe_ref_sha256"
                    ],
                ),
                state="ABSENT",
            )
            for role in _ABSENCE_ROLES
        )
        absence = CandidateAbsenceFacts.create(
            selection_key=candidate_verification.selection_key,
            launch_id=namespace_probe_ref.launch_id,
            nonce=nonce,
            authority_sha256=candidate_verification.authority_sha256,
            installation_sha256=candidate_verification.installation_sha256,
            environment_receipt_sha256=(
                candidate_verification.environment_receipt_sha256
            ),
            accepted_root=accepted_root,
            **binding_values,
            observations=observations,
        )
        inspection = CandidateCompositionInspection.create(
            selection_key=candidate_verification.selection_key,
            launch_id=namespace_probe_ref.launch_id,
            nonce=nonce,
            authority_sha256=candidate_verification.authority_sha256,
            installation_sha256=candidate_verification.installation_sha256,
            accepted_root=accepted_root,
            accepted_root_identity=root_identity,
            accepted_root_inventory_sha256=inventory_sha,
            accepted_root_inventory_count=inventory_count,
            **binding_values,
            manifest_sha256=actual_manifest_sha256,
            source_tree_identity_sha256=(readiness.source_tree_identity_sha256),
            state=readiness.state,
            external_installation_required=(readiness.external_installation_required),
            cell_count=len(cells),
            job_count=len(jobs),
            formal_jobs_started=formal_jobs_started,
            formal_execution_authorized=(readiness.formal_execution_authorized),
            filesystem_mutated=readiness.filesystem_mutated,
            absence_facts=absence,
        )
        return inspection, absence


@dataclass(frozen=True, slots=True, init=False)
class CandidateGateReceipt:
    """Canonical final acceptance of one installation-absent W3 candidate."""

    selection_key: str
    launch_id: str
    nonce: str
    authority_sha256: str
    installation_sha256: str
    source_acceptance_sha256: str
    source_receipt_sha256: str
    candidate_verification_sha256: str
    double_wheel_receipt_sha256: str
    semantic_environment_receipt_sha256: str
    environment_content_receipt_sha256: str
    candidate_probe_sha256: str
    namespace_final_probe_sha256: str
    namespace_probe_execution_sha256: str
    namespace_probe_ref_sha256: str
    namespace_probe_evidence_sha256: str
    candidate_root: str
    candidate_root_identity: CandidateRootIdentity
    accepted_root: str
    accepted_root_identity: CandidateRootIdentity
    accepted_root_read_only: bool
    accepted_root_inventory_sha256: str
    manifest_sha256: str
    source_tree_identity_sha256: str
    composition_inspection_sha256: str
    absence_facts_sha256: str
    state: str
    external_installation_required: bool
    cell_count: int
    job_count: int
    formal_jobs_started: int
    formal_execution_authorized: bool
    filesystem_mutated: bool
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "CandidateGateReceipt":
        del cls
        raise TypeError("CandidateGateReceipt must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("CandidateGateReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        candidate: CandidateVerificationReceipt,
        nonce: str,
        candidate_root: Path,
        candidate_root_identity: CandidateRootIdentity,
        double_wheel: OfflineDoubleWheelReceipt,
        semantic_environment: WarehouseEnvironmentContentReceipt,
        environment_content: EnvironmentContentReceipt,
        candidate_probe: EnvironmentProbeFact,
        namespace_final_probe: EnvironmentProbeFact,
        namespace_probe_execution: NamespaceProbeExecutionFact,
        namespace_probe_ref: CandidateNamespaceFinalProbeRef,
        inspection: CandidateCompositionInspection,
        absence_facts: CandidateAbsenceFacts,
    ) -> "CandidateGateReceipt":
        if (
            semantic_environment.generic_receipt != environment_content
            or namespace_probe_ref.semantic_environment_receipt_sha256
            != semantic_environment.raw_sha256
            or namespace_probe_ref.environment_content_receipt_sha256
            != semantic_environment.generic_receipt_sha256
            or namespace_probe_ref.environment_content_receipt_sha256
            != environment_content.raw_sha256
            or namespace_probe_ref.namespace_probe_execution_sha256
            != namespace_probe_execution.raw_sha256
        ):
            raise WarehouseW3CandidateGateError(
                "candidate gate environment relocation binding differs"
            )
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": "scion.w3-candidate-gate.v4",
                    "state": "CANDIDATE_ACCEPTED_INSTALLATION_ABSENT",
                    "selection_key": candidate.selection_key,
                    "launch_id": inspection.launch_id,
                    "nonce": nonce,
                    "authority_sha256": candidate.authority_sha256,
                    "installation_sha256": candidate.installation_sha256,
                    "source_acceptance_sha256": (candidate.source_acceptance_sha256),
                    "source_receipt_sha256": (candidate.source_receipt_sha256),
                    "candidate_verification_sha256": candidate.raw_sha256,
                    "double_wheel_receipt_sha256": double_wheel.raw_sha256,
                    "semantic_environment_receipt_sha256": (
                        semantic_environment.raw_sha256
                    ),
                    "environment_content_receipt_sha256": (
                        environment_content.raw_sha256
                    ),
                    "candidate_probe_sha256": candidate_probe.raw_sha256,
                    "namespace_final_probe_sha256": (namespace_final_probe.raw_sha256),
                    "namespace_probe_execution_sha256": (
                        namespace_probe_execution.raw_sha256
                    ),
                    "namespace_probe_ref_sha256": (namespace_probe_ref.raw_sha256),
                    "namespace_probe_evidence_sha256": (
                        namespace_probe_ref.evidence_receipt_sha256
                    ),
                    "candidate_root": str(candidate_root),
                    "candidate_root_identity": (candidate_root_identity.to_mapping()),
                    "accepted_root": inspection.accepted_root,
                    "accepted_root_identity": (
                        inspection.accepted_root_identity.to_mapping()
                    ),
                    "accepted_root_read_only": True,
                    "accepted_root_inventory_sha256": (
                        inspection.accepted_root_inventory_sha256
                    ),
                    "manifest_sha256": inspection.manifest_sha256,
                    "source_tree_identity_sha256": (
                        inspection.source_tree_identity_sha256
                    ),
                    "composition_inspection_sha256": inspection.raw_sha256,
                    "absence_facts_sha256": absence_facts.raw_sha256,
                    "external_installation_required": (
                        inspection.external_installation_required
                    ),
                    "cell_count": inspection.cell_count,
                    "job_count": inspection.job_count,
                    "formal_jobs_started": inspection.formal_jobs_started,
                    "formal_execution_authorized": (
                        inspection.formal_execution_authorized
                    ),
                    "filesystem_mutated": inspection.filesystem_mutated,
                    "retry": False,
                    "resume": False,
                    "reuse": False,
                }
            )
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CandidateGateReceipt":
        value = _exact_fields(
            _decode_canonical(raw, label="candidate gate receipt"),
            frozenset(
                {
                    "schema",
                    "state",
                    "selection_key",
                    "launch_id",
                    "nonce",
                    "authority_sha256",
                    "installation_sha256",
                    "source_acceptance_sha256",
                    "source_receipt_sha256",
                    "candidate_verification_sha256",
                    "double_wheel_receipt_sha256",
                    "semantic_environment_receipt_sha256",
                    "environment_content_receipt_sha256",
                    "candidate_probe_sha256",
                    "namespace_final_probe_sha256",
                    "namespace_probe_execution_sha256",
                    "namespace_probe_ref_sha256",
                    "namespace_probe_evidence_sha256",
                    "candidate_root",
                    "candidate_root_identity",
                    "accepted_root",
                    "accepted_root_identity",
                    "accepted_root_read_only",
                    "accepted_root_inventory_sha256",
                    "manifest_sha256",
                    "source_tree_identity_sha256",
                    "composition_inspection_sha256",
                    "absence_facts_sha256",
                    "external_installation_required",
                    "cell_count",
                    "job_count",
                    "formal_jobs_started",
                    "formal_execution_authorized",
                    "filesystem_mutated",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="candidate gate receipt",
        )
        _false_controls(value, label="candidate gate receipt")
        if (
            value["schema"] != "scion.w3-candidate-gate.v4"
            or value["state"] != "CANDIDATE_ACCEPTED_INSTALLATION_ABSENT"
            or value["manifest_sha256"] != EXPECTED_MANIFEST_SHA256
            or value["source_tree_identity_sha256"]
            != EXPECTED_SOURCE_TREE_IDENTITY_SHA256
            or value["external_installation_required"] is not True
            or type(value["cell_count"]) is not int
            or value["cell_count"] != EXPECTED_CELL_COUNT
            or type(value["job_count"]) is not int
            or value["job_count"] != EXPECTED_ROWS
            or type(value["formal_jobs_started"]) is not int
            or value["formal_jobs_started"] != 0
            or value["formal_execution_authorized"] is not False
            or value["filesystem_mutated"] is not False
            or value["accepted_root_read_only"] is not True
        ):
            raise WarehouseW3CandidateGateError("candidate gate state differs")
        fields: dict[str, object] = {
            name: _sha256(value[name], field=f"candidate gate.{name}")
            for name in (
                "selection_key",
                "launch_id",
                "nonce",
                "authority_sha256",
                "installation_sha256",
                "source_acceptance_sha256",
                "source_receipt_sha256",
                "candidate_verification_sha256",
                "double_wheel_receipt_sha256",
                "semantic_environment_receipt_sha256",
                "environment_content_receipt_sha256",
                "candidate_probe_sha256",
                "namespace_final_probe_sha256",
                "namespace_probe_execution_sha256",
                "namespace_probe_ref_sha256",
                "namespace_probe_evidence_sha256",
                "accepted_root_inventory_sha256",
                "manifest_sha256",
                "source_tree_identity_sha256",
                "composition_inspection_sha256",
                "absence_facts_sha256",
            )
        }
        fields.update(
            {
                "candidate_root": _absolute_path(
                    value["candidate_root"],
                    field="candidate gate candidate_root",
                ),
                "candidate_root_identity": _bounded_root_identity(
                    value["candidate_root_identity"]
                ),
                "accepted_root": _absolute_path(
                    value["accepted_root"],
                    field="candidate gate accepted_root",
                ),
                "accepted_root_identity": _bounded_root_identity(
                    value["accepted_root_identity"]
                ),
                "accepted_root_read_only": True,
                "state": "CANDIDATE_ACCEPTED_INSTALLATION_ABSENT",
                "external_installation_required": True,
                "cell_count": EXPECTED_CELL_COUNT,
                "job_count": EXPECTED_ROWS,
                "formal_jobs_started": 0,
                "formal_execution_authorized": False,
                "filesystem_mutated": False,
                "raw": raw,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        return _new(cls, fields)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True, init=False)
class CandidateGateClosureBundle:
    """Exact producer bundle required to carry one gate across privilege."""

    gate: CandidateGateReceipt
    candidate_verification: CandidateVerificationReceipt
    double_wheel: OfflineDoubleWheelReceipt
    semantic_environment: WarehouseEnvironmentContentReceipt
    environment_content: EnvironmentContentReceipt
    candidate_probe: EnvironmentProbeFact
    namespace_final_probe: EnvironmentProbeFact
    namespace_probe_execution: NamespaceProbeExecutionFact
    namespace_probe_ref: CandidateNamespaceFinalProbeRef
    inspection: CandidateCompositionInspection
    absence_facts: CandidateAbsenceFacts
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "CandidateGateClosureBundle":
        del cls
        raise TypeError("CandidateGateClosureBundle must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("CandidateGateClosureBundle is final")

    @classmethod
    def create(
        cls,
        *,
        gate: CandidateGateReceipt,
        candidate_verification: CandidateVerificationReceipt,
        double_wheel: OfflineDoubleWheelReceipt,
        semantic_environment: WarehouseEnvironmentContentReceipt,
        environment_content: EnvironmentContentReceipt,
        candidate_probe: EnvironmentProbeFact,
        namespace_final_probe: EnvironmentProbeFact,
        namespace_probe_execution: NamespaceProbeExecutionFact,
        namespace_probe_ref: CandidateNamespaceFinalProbeRef,
        inspection: CandidateCompositionInspection,
        absence_facts: CandidateAbsenceFacts,
    ) -> "CandidateGateClosureBundle":
        dependencies = (
            gate,
            candidate_verification,
            double_wheel,
            semantic_environment,
            environment_content,
            candidate_probe,
            namespace_final_probe,
            namespace_probe_execution,
            namespace_probe_ref,
            inspection,
            absence_facts,
        )
        if any(type(item.raw) is not bytes for item in dependencies):
            raise TypeError("candidate gate closure dependency raw bytes differ")
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": "scion.w3-candidate-gate-closure.v2",
                    "gate": gate.raw.decode("utf-8", "strict"),
                    "candidate_verification": (
                        candidate_verification.raw.decode("utf-8", "strict")
                    ),
                    "double_wheel": double_wheel.raw.decode("utf-8", "strict"),
                    "semantic_environment": (
                        semantic_environment.raw.decode("utf-8", "strict")
                    ),
                    "environment_content": (
                        environment_content.raw.decode("utf-8", "strict")
                    ),
                    "candidate_probe": candidate_probe.raw.decode("utf-8", "strict"),
                    "namespace_final_probe": (
                        namespace_final_probe.raw.decode("utf-8", "strict")
                    ),
                    "namespace_probe_execution": (
                        namespace_probe_execution.raw.decode("utf-8", "strict")
                    ),
                    "namespace_probe_ref": (
                        namespace_probe_ref.raw.decode("utf-8", "strict")
                    ),
                    "inspection": inspection.raw.decode("utf-8", "strict"),
                    "absence_facts": absence_facts.raw.decode("utf-8", "strict"),
                }
            )
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CandidateGateClosureBundle":
        value = _exact_fields(
            _decode_canonical(raw, label="candidate gate closure bundle"),
            frozenset(
                {
                    "schema",
                    "gate",
                    "candidate_verification",
                    "double_wheel",
                    "semantic_environment",
                    "environment_content",
                    "candidate_probe",
                    "namespace_final_probe",
                    "namespace_probe_execution",
                    "namespace_probe_ref",
                    "inspection",
                    "absence_facts",
                }
            ),
            label="candidate gate closure bundle",
        )
        if value["schema"] != "scion.w3-candidate-gate-closure.v2":
            raise WarehouseW3CandidateGateError("candidate gate closure schema differs")

        def nested(name: str) -> bytes:
            item = value[name]
            if type(item) is not str:
                raise WarehouseW3CandidateGateError(
                    f"candidate gate closure {name} is not exact text"
                )
            try:
                return item.encode("utf-8", "strict")
            except UnicodeError as exc:
                raise WarehouseW3CandidateGateError(
                    f"candidate gate closure {name} is not UTF-8"
                ) from exc

        gate = CandidateGateReceipt.from_bytes(nested("gate"))
        candidate = CandidateVerificationReceipt.from_bytes(
            nested("candidate_verification")
        )
        wheel = OfflineDoubleWheelReceipt.from_bytes(nested("double_wheel"))
        environment = EnvironmentContentReceipt.from_bytes(
            nested("environment_content")
        )
        semantic = WarehouseEnvironmentContentReceipt.from_bytes(
            nested("semantic_environment"),
            generic_receipt=environment,
            wheel_receipt=wheel,
        )
        candidate_probe = EnvironmentProbeFact.from_bytes(nested("candidate_probe"))
        namespace_probe = EnvironmentProbeFact.from_bytes(
            nested("namespace_final_probe")
        )
        namespace_execution = NamespaceProbeExecutionFact.from_bytes(
            nested("namespace_probe_execution"),
            environment_probe=namespace_probe,
        )
        relocation = CandidateNamespaceFinalProbeRef.from_bytes(
            nested("namespace_probe_ref"),
            semantic_environment=semantic,
        )
        _validate_probe(
            candidate_probe,
            phase="candidate",
            content=semantic,
            expected_root=Path(relocation.candidate_environment_root),
        )
        _validate_probe(
            namespace_probe,
            phase="namespace_final",
            content=semantic,
            expected_root=Path(relocation.visible_environment_root),
        )
        inspection = CandidateCompositionInspection.from_bytes(nested("inspection"))
        absence = CandidateAbsenceFacts.from_bytes(nested("absence_facts"))
        shared = (
            gate.selection_key,
            gate.launch_id,
            gate.authority_sha256,
            gate.installation_sha256,
        )
        bindings = {
            "candidate_verification_sha256": candidate.raw_sha256,
            "double_wheel_receipt_sha256": wheel.raw_sha256,
            "semantic_environment_receipt_sha256": semantic.raw_sha256,
            "candidate_probe_sha256": candidate_probe.raw_sha256,
            "namespace_final_probe_sha256": namespace_probe.raw_sha256,
            "namespace_probe_ref_sha256": relocation.raw_sha256,
            "namespace_probe_evidence_sha256": (relocation.evidence_receipt_sha256),
        }
        if (
            (
                candidate.selection_key,
                relocation.launch_id,
                candidate.authority_sha256,
                candidate.installation_sha256,
            )
            != shared
            or (
                relocation.selection_key,
                relocation.launch_id,
                relocation.authority_sha256,
                relocation.installation_sha256,
            )
            != shared
            or (
                inspection.selection_key,
                inspection.launch_id,
                inspection.authority_sha256,
                inspection.installation_sha256,
            )
            != shared
            or (
                absence.selection_key,
                absence.launch_id,
                absence.authority_sha256,
                absence.installation_sha256,
            )
            != shared
            or gate.nonce != inspection.nonce
            or gate.nonce != absence.nonce
            or derive_launch_id(candidate.authority_sha256, gate.nonce)
            != gate.launch_id
            or gate.source_receipt_sha256 != candidate.source_receipt_sha256
            or gate.source_acceptance_sha256 != candidate.source_acceptance_sha256
            or gate.candidate_root_identity != candidate.candidate_root_identity
            or gate.candidate_verification_sha256 != candidate.raw_sha256
            or gate.double_wheel_receipt_sha256 != wheel.raw_sha256
            or gate.semantic_environment_receipt_sha256 != semantic.raw_sha256
            or gate.environment_content_receipt_sha256 != environment.raw_sha256
            or gate.candidate_probe_sha256 != candidate_probe.raw_sha256
            or gate.namespace_final_probe_sha256 != namespace_probe.raw_sha256
            or gate.namespace_probe_execution_sha256 != namespace_execution.raw_sha256
            or gate.namespace_probe_ref_sha256 != relocation.raw_sha256
            or gate.namespace_probe_evidence_sha256
            != relocation.evidence_receipt_sha256
            or gate.composition_inspection_sha256 != inspection.raw_sha256
            or gate.absence_facts_sha256 != absence.raw_sha256
            or inspection.absence_facts_sha256 != absence.raw_sha256
            or gate.manifest_sha256 != inspection.manifest_sha256
            or gate.source_tree_identity_sha256
            != inspection.source_tree_identity_sha256
            or semantic.generic_receipt_sha256 != environment.raw_sha256
            or candidate.environment_receipt_sha256 != environment.raw_sha256
            or semantic.wheel_receipt_sha256 != wheel.raw_sha256
            or absence.environment_receipt_sha256 != environment.raw_sha256
            or relocation.semantic_environment_receipt_sha256 != semantic.raw_sha256
            or relocation.environment_content_receipt_sha256 != environment.raw_sha256
            or relocation.candidate_probe_sha256 != candidate_probe.raw_sha256
            or relocation.namespace_final_probe_sha256 != namespace_probe.raw_sha256
            or relocation.namespace_probe_execution_sha256
            != namespace_execution.raw_sha256
            or relocation.evidence_receipt_sha256
            != derive_namespace_probe_evidence_sha256(
                semantic.raw,
                candidate_probe.raw,
                namespace_probe.raw,
                namespace_execution.raw,
            )
            or relocation.physical_environment_root
            != namespace_execution.physical_environment_root
            or relocation.visible_environment_root
            != namespace_execution.visible_environment_root
            or candidate_probe.phase != "candidate"
            or namespace_probe.phase != "namespace_final"
            or candidate_probe.content_receipt_sha256 != semantic.raw_sha256
            or namespace_probe.content_receipt_sha256 != semantic.raw_sha256
            or any(
                getattr(inspection, name) != expected
                or getattr(absence, name) != expected
                for name, expected in bindings.items()
            )
            or gate.accepted_root != inspection.accepted_root
            or gate.accepted_root != absence.accepted_root
            or gate.accepted_root_identity != inspection.accepted_root_identity
            or gate.accepted_root_inventory_sha256
            != inspection.accepted_root_inventory_sha256
        ):
            raise WarehouseW3CandidateGateError(
                "candidate gate closure dependency binding differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("gate", gate),
            ("candidate_verification", candidate),
            ("double_wheel", wheel),
            ("semantic_environment", semantic),
            ("environment_content", environment),
            ("candidate_probe", candidate_probe),
            ("namespace_final_probe", namespace_probe),
            ("namespace_probe_execution", namespace_execution),
            ("namespace_probe_ref", relocation),
            ("inspection", inspection),
            ("absence_facts", absence),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


def _close_candidate_gate_closure(
    *,
    candidate_verification: CandidateVerificationReceipt,
    double_wheel_artifact: OfflineDoubleWheelArtifact,
    semantic_environment: WarehouseEnvironmentContentReceipt,
    environment_content: EnvironmentContentReceipt,
    candidate_probe: EnvironmentProbeFact,
    namespace_final_probe: EnvironmentProbeFact,
    namespace_probe_execution: NamespaceProbeExecutionFact,
    namespace_probe_ref: CandidateNamespaceFinalProbeRef,
    candidate_root: Path,
    accepted_root: Path,
    nonce: str,
    accepted_manifest_sha256: str,
    inspector: FilesystemCandidateCompositionInspector | None = None,
) -> CandidateGateClosureBundle:
    """Close one exact candidate while external installation remains absent."""

    exact_types = (
        (candidate_verification, CandidateVerificationReceipt, "candidate"),
        (
            double_wheel_artifact,
            OfflineDoubleWheelArtifact,
            "double_wheel_artifact",
        ),
        (
            semantic_environment,
            WarehouseEnvironmentContentReceipt,
            "semantic_environment",
        ),
        (environment_content, EnvironmentContentReceipt, "environment_content"),
        (candidate_probe, EnvironmentProbeFact, "candidate_probe"),
        (
            namespace_final_probe,
            EnvironmentProbeFact,
            "namespace_final_probe",
        ),
        (
            namespace_probe_execution,
            NamespaceProbeExecutionFact,
            "namespace_probe_execution",
        ),
        (
            namespace_probe_ref,
            CandidateNamespaceFinalProbeRef,
            "namespace_probe_ref",
        ),
    )
    for value, expected, label in exact_types:
        if type(value) is not expected:
            raise TypeError(f"{label} must be exact {expected.__name__}")
    if not isinstance(accepted_root, Path):
        raise TypeError("accepted_root must be Path")
    if not isinstance(candidate_root, Path):
        raise TypeError("candidate_root must be Path")
    selected_inspector = (
        FilesystemCandidateCompositionInspector() if inspector is None else inspector
    )
    if type(selected_inspector) is not FilesystemCandidateCompositionInspector:
        raise TypeError(
            "production gate requires exact FilesystemCandidateCompositionInspector"
        )
    method = selected_inspector.inspect

    try:
        double_wheel = verify_offline_double_wheel_artifact(double_wheel_artifact)
        parsed_candidate = CandidateVerificationReceipt.from_bytes(
            candidate_verification.raw
        )
        parsed_environment = EnvironmentContentReceipt.from_bytes(
            environment_content.raw
        )
        parsed_semantic = WarehouseEnvironmentContentReceipt.from_bytes(
            semantic_environment.raw,
            generic_receipt=environment_content,
            wheel_receipt=double_wheel,
        )
        parsed_relocation = CandidateNamespaceFinalProbeRef.from_bytes(
            namespace_probe_ref.raw,
            semantic_environment=parsed_semantic,
        )
        parsed_execution = NamespaceProbeExecutionFact.from_bytes(
            namespace_probe_execution.raw,
            environment_probe=namespace_final_probe,
        )
    except Exception as exc:
        raise WarehouseW3CandidateGateError(
            "candidate artifact receipt cannot be reopened"
        ) from exc
    if (
        parsed_candidate != candidate_verification
        or parsed_environment != environment_content
        or parsed_semantic != semantic_environment
        or parsed_execution != namespace_probe_execution
        or parsed_relocation != namespace_probe_ref
    ):
        raise WarehouseW3CandidateGateError("candidate artifact receipt object differs")

    manifest_sha = _sha256(
        accepted_manifest_sha256,
        field="accepted_manifest_sha256",
    )
    accepted_root_text = _absolute_path(str(accepted_root), field="accepted_root")
    candidate_root_text = _absolute_path(
        str(candidate_root),
        field="candidate_root",
    )
    nonce_value = _sha256(nonce, field="nonce")
    candidate_root_identity = _candidate_root_identity(candidate_root)
    if manifest_sha != EXPECTED_MANIFEST_SHA256:
        raise WarehouseW3CandidateGateError(
            "accepted dry-root manifest identity differs"
        )
    external_runtime_paths = tuple(
        Path(item.path)
        for item in semantic_environment.generic_receipt.external_runtime
    )
    try:
        prepared = verify_candidate(
            candidate_root,
            external_runtime_paths=external_runtime_paths,
        )
    except Exception as exc:
        raise WarehouseW3CandidateGateError(
            "candidate cannot be reopened and reverified"
        ) from exc
    if type(prepared) is not PreparedCandidate:
        raise WarehouseW3CandidateGateError(
            "candidate verifier returned an ambiguous value"
        )
    _verify_candidate_wheel_bindings(prepared, double_wheel_artifact)
    candidate = candidate_verification
    if (
        prepared.verification_receipt != candidate
        or prepared.candidate_root != candidate_root
        or prepared.source_receipt.raw_sha256 != candidate.source_receipt_sha256
        or prepared.environment_receipt != environment_content
        or prepared.authority.authority_sha256 != candidate.authority_sha256
        or prepared.installation.installation_sha256 != candidate.installation_sha256
        or prepared.authority.nonce != nonce_value
        or prepared.installation.run_root != accepted_root_text
        or candidate.candidate_root_identity != candidate_root_identity
        or double_wheel.source_receipt_sha256 != candidate.source_receipt_sha256
        or candidate.environment_receipt_sha256 != environment_content.raw_sha256
        or semantic_environment.generic_receipt_sha256 != environment_content.raw_sha256
        or semantic_environment.wheel_receipt_sha256 != double_wheel.raw_sha256
        or semantic_environment.wheel_sha256 != double_wheel.wheel_sha256
    ):
        raise WarehouseW3CandidateGateError(
            "candidate wheel or semantic environment binding differs"
        )
    _validate_probe(
        candidate_probe,
        phase="candidate",
        content=semantic_environment,
        expected_root=candidate_root / "environment",
    )
    _validate_probe(
        namespace_final_probe,
        phase="namespace_final",
        content=semantic_environment,
        expected_root=Path(namespace_probe_ref.visible_environment_root),
    )
    expected_launch_id = derive_launch_id(
        candidate.authority_sha256,
        nonce_value,
    )
    shared = (
        candidate.selection_key,
        namespace_probe_ref.launch_id,
        candidate.authority_sha256,
        candidate.installation_sha256,
    )
    if (
        (
            namespace_probe_ref.selection_key,
            namespace_probe_ref.launch_id,
            namespace_probe_ref.authority_sha256,
            namespace_probe_ref.installation_sha256,
        )
        != shared
        or namespace_probe_ref.launch_id != expected_launch_id
        or namespace_probe_ref.semantic_environment_receipt_sha256
        != semantic_environment.raw_sha256
        or namespace_probe_ref.environment_content_receipt_sha256
        != semantic_environment.generic_receipt_sha256
        or namespace_probe_ref.environment_content_receipt_sha256
        != environment_content.raw_sha256
        or namespace_probe_ref.candidate_probe_sha256 != candidate_probe.raw_sha256
        or namespace_probe_ref.namespace_final_probe_sha256
        != namespace_final_probe.raw_sha256
        or namespace_probe_ref.namespace_probe_execution_sha256
        != namespace_probe_execution.raw_sha256
        or namespace_probe_ref.candidate_environment_root
        != candidate_probe.environment_root
        or namespace_probe_ref.physical_environment_root
        != namespace_probe_execution.physical_environment_root
        or namespace_probe_ref.visible_environment_root
        != namespace_probe_execution.visible_environment_root
    ):
        raise WarehouseW3CandidateGateError("candidate namespace-final binding differs")

    try:
        inspected = method(
            accepted_root=accepted_root,
            candidate_root=candidate_root,
            nonce=nonce_value,
            manifest_sha256=manifest_sha,
            prepared_candidate=prepared,
            candidate_verification=candidate,
            double_wheel=double_wheel,
            semantic_environment=semantic_environment,
            candidate_probe=candidate_probe,
            namespace_final_probe=namespace_final_probe,
            namespace_probe_ref=namespace_probe_ref,
        )
    except Exception as exc:
        raise WarehouseW3CandidateGateError(
            "candidate composition inspection failed"
        ) from exc
    if (
        type(inspected) is not tuple
        or len(inspected) != 2
        or type(inspected[0]) is not CandidateCompositionInspection
        or type(inspected[1]) is not CandidateAbsenceFacts
    ):
        raise WarehouseW3CandidateGateError(
            "candidate inspector returned ambiguous facts"
        )
    inspection, absence = inspected
    if (
        CandidateCompositionInspection.from_bytes(inspection.raw) != inspection
        or CandidateAbsenceFacts.from_bytes(absence.raw) != absence
    ):
        raise WarehouseW3CandidateGateError(
            "candidate inspector facts differ from exact bytes"
        )
    if (
        (
            inspection.selection_key,
            inspection.launch_id,
            inspection.authority_sha256,
            inspection.installation_sha256,
        )
        != shared
        or inspection.nonce != nonce_value
        or inspection.accepted_root != accepted_root_text
        or inspection.accepted_root_identity != _candidate_root_identity(accepted_root)
        or inspection.accepted_root_read_only is not True
        or inspection.manifest_sha256 != manifest_sha
        or inspection.source_tree_identity_sha256
        != EXPECTED_SOURCE_TREE_IDENTITY_SHA256
        or inspection.state != EXPECTED_CANDIDATE_COMPOSITION_STATE
        or inspection.external_installation_required is not True
        or inspection.cell_count != EXPECTED_CELL_COUNT
        or inspection.job_count != EXPECTED_ROWS
        or inspection.formal_jobs_started != 0
        or inspection.formal_execution_authorized is not False
        or inspection.filesystem_mutated is not False
        or (
            absence.selection_key,
            absence.launch_id,
            absence.authority_sha256,
            absence.installation_sha256,
        )
        != shared
        or absence.nonce != nonce_value
        or absence.accepted_root != accepted_root_text
        or inspection.absence_facts_sha256 != absence.raw_sha256
    ):
        raise WarehouseW3CandidateGateError(
            "candidate dry-root, composition, or absence binding differs"
        )
    expected_bindings = {
        "candidate_verification_sha256": candidate.raw_sha256,
        "double_wheel_receipt_sha256": double_wheel.raw_sha256,
        "semantic_environment_receipt_sha256": semantic_environment.raw_sha256,
        "candidate_probe_sha256": candidate_probe.raw_sha256,
        "namespace_final_probe_sha256": namespace_final_probe.raw_sha256,
        "namespace_probe_ref_sha256": namespace_probe_ref.raw_sha256,
        "namespace_probe_evidence_sha256": (
            namespace_probe_ref.evidence_receipt_sha256
        ),
    }
    if any(
        getattr(inspection, name) != expected or getattr(absence, name) != expected
        for name, expected in expected_bindings.items()
    ):
        raise WarehouseW3CandidateGateError(
            "candidate inspection/absence replay binding differs"
        )
    try:
        final_prepared = verify_candidate(
            candidate_root,
            external_runtime_paths=external_runtime_paths,
        )
        _verify_candidate_wheel_bindings(
            final_prepared,
            double_wheel_artifact,
        )
    except Exception as exc:
        raise WarehouseW3CandidateGateError(
            "candidate changed during candidate gate closure"
        ) from exc
    if type(final_prepared) is not PreparedCandidate or final_prepared != prepared:
        raise WarehouseW3CandidateGateError(
            "candidate changed during candidate gate closure"
        )
    if _candidate_root_identity(candidate_root) != candidate_root_identity:
        raise WarehouseW3CandidateGateError(
            "candidate_root changed during candidate gate closure"
        )
    gate = CandidateGateReceipt.create(
        candidate=candidate,
        nonce=nonce_value,
        candidate_root=Path(candidate_root_text),
        candidate_root_identity=candidate_root_identity,
        double_wheel=double_wheel,
        semantic_environment=semantic_environment,
        environment_content=environment_content,
        candidate_probe=candidate_probe,
        namespace_final_probe=namespace_final_probe,
        namespace_probe_execution=namespace_probe_execution,
        namespace_probe_ref=namespace_probe_ref,
        inspection=inspection,
        absence_facts=absence,
    )
    return CandidateGateClosureBundle.create(
        gate=gate,
        candidate_verification=candidate,
        double_wheel=double_wheel,
        semantic_environment=semantic_environment,
        environment_content=environment_content,
        candidate_probe=candidate_probe,
        namespace_final_probe=namespace_final_probe,
        namespace_probe_execution=namespace_probe_execution,
        namespace_probe_ref=namespace_probe_ref,
        inspection=inspection,
        absence_facts=absence,
    )


def close_candidate_gate_closure(
    *,
    candidate_verification: CandidateVerificationReceipt,
    double_wheel_artifact: OfflineDoubleWheelArtifact,
    semantic_environment: WarehouseEnvironmentContentReceipt,
    environment_content: EnvironmentContentReceipt,
    candidate_probe: EnvironmentProbeFact,
    namespace_final_probe: EnvironmentProbeFact,
    namespace_probe_execution: NamespaceProbeExecutionFact,
    namespace_probe_ref: CandidateNamespaceFinalProbeRef,
    candidate_root: Path,
    accepted_root: Path,
    nonce: str,
    accepted_manifest_sha256: str,
    inspector: FilesystemCandidateCompositionInspector | None = None,
) -> CandidateGateClosureBundle:
    """Close and retain every exact producer required by privileged ingress."""

    return _close_candidate_gate_closure(
        candidate_verification=candidate_verification,
        double_wheel_artifact=double_wheel_artifact,
        semantic_environment=semantic_environment,
        environment_content=environment_content,
        candidate_probe=candidate_probe,
        namespace_final_probe=namespace_final_probe,
        namespace_probe_execution=namespace_probe_execution,
        namespace_probe_ref=namespace_probe_ref,
        candidate_root=candidate_root,
        accepted_root=accepted_root,
        nonce=nonce,
        accepted_manifest_sha256=accepted_manifest_sha256,
        inspector=inspector,
    )


def close_candidate_gate(
    *,
    candidate_verification: CandidateVerificationReceipt,
    double_wheel_artifact: OfflineDoubleWheelArtifact,
    semantic_environment: WarehouseEnvironmentContentReceipt,
    environment_content: EnvironmentContentReceipt,
    candidate_probe: EnvironmentProbeFact,
    namespace_final_probe: EnvironmentProbeFact,
    namespace_probe_execution: NamespaceProbeExecutionFact,
    namespace_probe_ref: CandidateNamespaceFinalProbeRef,
    candidate_root: Path,
    accepted_root: Path,
    nonce: str,
    accepted_manifest_sha256: str,
    inspector: FilesystemCandidateCompositionInspector | None = None,
) -> CandidateGateReceipt:
    """Compatibility view; privileged ingress requires the closure bundle."""

    return close_candidate_gate_closure(
        candidate_verification=candidate_verification,
        double_wheel_artifact=double_wheel_artifact,
        semantic_environment=semantic_environment,
        environment_content=environment_content,
        candidate_probe=candidate_probe,
        namespace_final_probe=namespace_final_probe,
        namespace_probe_execution=namespace_probe_execution,
        namespace_probe_ref=namespace_probe_ref,
        candidate_root=candidate_root,
        accepted_root=accepted_root,
        nonce=nonce,
        accepted_manifest_sha256=accepted_manifest_sha256,
        inspector=inspector,
    ).gate


__all__ = [
    "CandidateAbsenceFacts",
    "CandidateAbsenceObservation",
    "CandidateCompositionInspection",
    "CandidateCompositionInspector",
    "FilesystemCandidateCompositionInspector",
    "CandidateGateClosureBundle",
    "CandidateGateReceipt",
    "CandidateNamespaceFinalProbeRef",
    "EXPECTED_CANDIDATE_COMPOSITION_STATE",
    "EXPECTED_CELL_COUNT",
    "WarehouseW3CandidateGateError",
    "close_candidate_gate",
    "close_candidate_gate_closure",
    "reverify_w3_accepted_root",
]
