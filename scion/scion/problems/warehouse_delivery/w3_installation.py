"""Non-privileged Warehouse W3 candidate and launch-source preparation.

This module deliberately has no root, mount, systemd-manager, start, or nonce
claim capability.  It builds canonical preparation receipts, acquires exact Git
objects through a narrow injectable command runner, and adapts those facts to
the accepted generic authority and installation schemas.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Protocol

from scion.problems.warehouse_delivery.w3_composition import (
    EXPECTED_ARTIFACT_NAMES,
    EXPECTED_CORRECTION_DESIGN_SHA256,
    EXPECTED_MANIFEST_NAME,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_NATIVE_ACCEPTANCE_CONTRACT_SHA256,
    EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256,
    EXPECTED_NONCE_LEDGER_PARENT,
    EXPECTED_ROWS,
    EXPECTED_SCIENTIFIC_DESIGN_SHA256,
    configured_pair_for_installation,
)
from scion.runtime.execution.launch_authority import (
    AcceptedLaunchAuthority,
    InstallationRecord,
)
from scion.runtime.execution.environment_integrity import (
    EnvironmentContentReceipt,
    EnvironmentIntegrityError,
    EnvironmentInventoryEntry,
    verify_environment_content,
)
from scion.runtime.execution.systemd_acquisition import parse_unit_template

ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256 = (
    "49196769c0c70f56714791a80e6c683d31d547c5f4e47cc7216ea1b5fda81eb6"
)

W3_COMPOSITION_LOGICAL_PATH = "scion/problems/warehouse_delivery/w3_composition.py"
W3_TOOL_LOGICAL_PATH = "scion/tools/scion_w3_tool.py"
W3_RUN_TEMPLATE_LOGICAL_PATH = (
    "scion/problems/warehouse_delivery/systemd/scion-w3@.service"
)
W3_CLOSE_TEMPLATE_LOGICAL_PATH = (
    "scion/problems/warehouse_delivery/systemd/scion-w3-close@.service"
)
W3_NATIVE_RECORD_LOGICAL_PATH = "external/native-acceptance-record.v1.json"

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OID_RE = re.compile(r"[0-9a-f]{40}\Z")
_REMOTE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_TASK_EVENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}\Z")
_REF_RE = re.compile(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]{0,511}\Z")
_MAX_GIT_TEXT_BYTES = 1024 * 1024
_MAX_GIT_BLOB_BYTES = 32 * 1024 * 1024
_SELECTION_KEY_SCHEMA = "scion.w3-candidate-selection-key.v1"
_SELECTION_INTENT_SCHEMA = "scion.w3-candidate-selection-intent.v1"
_SELECTION_COMMIT_SCHEMA = "scion.w3-candidate-selection-committed.v1"
_SOURCE_RECEIPT_SCHEMA = "scion.w3-git-source.v1"
_SEALED_STORE_SCHEMA = "scion.w3-sealed-store-content.v1"
_CANDIDATE_SCHEMA = "scion.w3-candidate.v1"
_CANDIDATE_VERIFICATION_SCHEMA = "scion.w3-candidate-verification.v1"
_DIRECTORY_MODE = 0o555
_REGULAR_MODES = frozenset({0o444, 0o555})
_READ_SIZE = 1024 * 1024
_CANDIDATE_INVENTORY = (
    "candidate.v1.json",
    "authority.json",
    "installation.json",
    "sealed-store",
    "environment",
    "units/scion-w3@.service",
    "units/scion-w3-close@.service",
    "receipts/source.v1.json",
    "receipts/sealed-store.v1.json",
    "receipts/environment.v1.json",
    "receipts/candidate-verification.v1.json",
    "receipts/selection-intent.v1.json",
    "receipts/selection-committed.v1.json",
)
_CANDIDATE_TAIL_PATHS = (
    "candidate.v1.json",
    "receipts/candidate-verification.v1.json",
)
_CANDIDATE_CONTENT_PATHS = tuple(
    item for item in _CANDIDATE_INVENTORY if item not in _CANDIDATE_TAIL_PATHS
)


class WarehouseW3InstallationError(RuntimeError):
    """A non-privileged W3 candidate or source fact is invalid."""


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
        raise WarehouseW3InstallationError("value is not canonical JSON") from exc


def _decode_canonical(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError(f"{label} must be exact bytes")
    try:
        text = raw.decode("utf-8", "strict")

        def mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"{label} contains a duplicate field")
                result[key] = value
            return result

        value = json.loads(
            text,
            object_pairs_hook=mapping,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"{label} contains {token}")
            ),
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise WarehouseW3InstallationError(f"{label} is not canonical JSON") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3InstallationError(f"{label} bytes are not canonical")
    return value


def _exact_keys(
    value: Mapping[str, object],
    expected: frozenset[str],
    *,
    label: str,
) -> None:
    if frozenset(value) != expected or any(type(key) is not str for key in value):
        raise WarehouseW3InstallationError(f"{label} fields differ")


def _false_controls(value: Mapping[str, object], *, label: str) -> None:
    if any(value.get(name) is not False for name in ("retry", "resume", "reuse")):
        raise WarehouseW3InstallationError(f"{label} enables retry, resume, or reuse")


def _sha256_text(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3InstallationError(f"{field} is not one SHA-256 value")
    return value


def _git_oid(value: object, *, field: str) -> str:
    if (
        type(value) is not str
        or _GIT_OID_RE.fullmatch(value) is None
        or len(set(value)) == 1
    ):
        raise WarehouseW3InstallationError(
            f"{field} is not one real 40-hex Git object id"
        )
    return value


def _task_event(value: object) -> str:
    if type(value) is not str or _TASK_EVENT_RE.fullmatch(value) is None:
        raise WarehouseW3InstallationError(
            "task_event_identity is not one canonical token"
        )
    return value


def _relative_path(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise WarehouseW3InstallationError(f"{field} is not exact text")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or value in {"", "."}
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise WarehouseW3InstallationError(f"{field} is not a canonical relative path")
    return value


def _absolute_path(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise WarehouseW3InstallationError(f"{field} is not exact text")
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or path.as_posix() != value
        or value == "/"
        or any(part in {"", ".", ".."} for part in path.parts[1:])
    ):
        raise WarehouseW3InstallationError(f"{field} is not a canonical absolute path")
    return value


def _remote_name(value: object) -> str:
    if type(value) is not str or _REMOTE_RE.fullmatch(value) is None:
        raise WarehouseW3InstallationError("remote_name is not canonical")
    return value


def _full_branch_ref(value: object) -> str:
    if type(value) is not str or _REF_RE.fullmatch(value) is None:
        raise WarehouseW3InstallationError(
            "remote_ref is not one full refs/heads reference"
        )
    suffix = value.removeprefix("refs/heads/")
    parts = suffix.split("/")
    if (
        any(part in {"", ".", ".."} or part.endswith(".lock") for part in parts)
        or "@{" in value
        or value.endswith((".", "/"))
        or ".." in value
    ):
        raise WarehouseW3InstallationError("remote_ref is not canonical")
    return value


def _positive_int(value: object, *, field: str, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        raise WarehouseW3InstallationError(
            f"{field} is not an integer greater than or equal to {minimum}"
        )
    return value


def _new(cls: type[object], fields: Mapping[str, object]) -> object:
    instance = object.__new__(cls)
    for name, value in fields.items():
        object.__setattr__(instance, name, value)
    return instance


def derive_launch_id(authority_sha256: str, nonce: str) -> str:
    """Derive the fixed launch id without publishing or claiming the nonce."""

    authority = _sha256_text(authority_sha256, field="authority_sha256")
    nonce_value = _sha256_text(nonce, field="nonce")
    return hashlib.sha256(
        b"scion.w3-launch-id.v1\0"
        + authority.encode("ascii")
        + b"\0"
        + nonce_value.encode("ascii")
    ).hexdigest()


def derive_selection_key(
    *,
    task_event_identity: str,
    launch_commit: str,
    launch_tree: str,
    dry_root_manifest_sha256: str,
    native_record_sha256: str,
) -> str:
    """Derive the one plan-bound candidate preparation key."""

    event = _task_event(task_event_identity)
    commit = _git_oid(launch_commit, field="launch_commit")
    tree = _git_oid(launch_tree, field="launch_tree")
    manifest = _sha256_text(
        dry_root_manifest_sha256,
        field="dry_root_manifest_sha256",
    )
    native = _sha256_text(native_record_sha256, field="native_record_sha256")
    if manifest != EXPECTED_MANIFEST_SHA256:
        raise WarehouseW3InstallationError(
            "dry-root manifest is not the accepted Warehouse W3 manifest"
        )
    if native != EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256:
        raise WarehouseW3InstallationError(
            "native record is not the accepted Warehouse W3 record"
        )
    inputs = {
        "schema": _SELECTION_KEY_SCHEMA,
        "task_event_identity": event,
        "fixed_plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
        "launch_commit": commit,
        "launch_tree": tree,
        "dry_root_manifest_sha256": manifest,
        "native_record_sha256": native,
    }
    return hashlib.sha256(
        b"scion.w3-candidate-selection-key.v1\0" + _canonical_json(inputs)
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class CandidatePaths:
    """The only user-owned preparation paths for one selection key."""

    experiment_parent: Path
    selection_directory: Path
    candidate_root: Path
    intent_path: Path
    committed_path: Path


def derive_candidate_paths(
    experiment_parent: Path,
    selection_key: str,
) -> CandidatePaths:
    if not isinstance(experiment_parent, Path):
        raise TypeError("experiment_parent must be a Path")
    parent = Path(_absolute_path(str(experiment_parent), field="experiment_parent"))
    key = _sha256_text(selection_key, field="selection_key")
    selection = parent / ".scion-w3-selections" / key
    candidate = parent / f"v04-w3-launch-{key}-claw"
    return CandidatePaths(
        experiment_parent=parent,
        selection_directory=selection,
        candidate_root=candidate,
        intent_path=selection / "intent.v1.json",
        committed_path=selection / "committed.v1.json",
    )


@dataclass(frozen=True, slots=True, init=False)
class CandidateSelectionIntent:
    selection_key: str
    task_event_identity: str
    launch_commit: str
    launch_tree: str
    dry_root_manifest_sha256: str
    native_record_sha256: str
    experiment_parent: str
    selection_directory: str
    candidate_root: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "CandidateSelectionIntent":
        del cls
        raise TypeError("CandidateSelectionIntent must be parsed from exact bytes")

    @classmethod
    def create(
        cls,
        *,
        experiment_parent: Path,
        task_event_identity: str,
        launch_commit: str,
        launch_tree: str,
        dry_root_manifest_sha256: str = EXPECTED_MANIFEST_SHA256,
        native_record_sha256: str = EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256,
    ) -> "CandidateSelectionIntent":
        key = derive_selection_key(
            task_event_identity=task_event_identity,
            launch_commit=launch_commit,
            launch_tree=launch_tree,
            dry_root_manifest_sha256=dry_root_manifest_sha256,
            native_record_sha256=native_record_sha256,
        )
        paths = derive_candidate_paths(experiment_parent, key)
        value = {
            "schema": _SELECTION_INTENT_SCHEMA,
            "selection_key": key,
            "task_event_identity": task_event_identity,
            "fixed_plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "launch_commit": launch_commit,
            "launch_tree": launch_tree,
            "dry_root_manifest_sha256": dry_root_manifest_sha256,
            "native_record_sha256": native_record_sha256,
            "experiment_parent": str(paths.experiment_parent),
            "selection_directory": str(paths.selection_directory),
            "candidate_root": str(paths.candidate_root),
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CandidateSelectionIntent":
        value = _decode_canonical(raw, label="candidate selection intent")
        _exact_keys(
            value,
            frozenset(
                {
                    "schema",
                    "selection_key",
                    "task_event_identity",
                    "fixed_plan_sha256",
                    "launch_commit",
                    "launch_tree",
                    "dry_root_manifest_sha256",
                    "native_record_sha256",
                    "experiment_parent",
                    "selection_directory",
                    "candidate_root",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="candidate selection intent",
        )
        if value["schema"] != _SELECTION_INTENT_SCHEMA:
            raise WarehouseW3InstallationError("selection intent schema differs")
        _false_controls(value, label="candidate selection intent")
        if (
            _sha256_text(
                value["fixed_plan_sha256"],
                field="fixed_plan_sha256",
            )
            != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
        ):
            raise WarehouseW3InstallationError("selection intent plan differs")
        event = _task_event(value["task_event_identity"])
        commit = _git_oid(value["launch_commit"], field="launch_commit")
        tree = _git_oid(value["launch_tree"], field="launch_tree")
        manifest = _sha256_text(
            value["dry_root_manifest_sha256"],
            field="dry_root_manifest_sha256",
        )
        native = _sha256_text(
            value["native_record_sha256"],
            field="native_record_sha256",
        )
        key = derive_selection_key(
            task_event_identity=event,
            launch_commit=commit,
            launch_tree=tree,
            dry_root_manifest_sha256=manifest,
            native_record_sha256=native,
        )
        if _sha256_text(value["selection_key"], field="selection_key") != key:
            raise WarehouseW3InstallationError("selection intent key differs")
        parent = Path(
            _absolute_path(value["experiment_parent"], field="experiment_parent")
        )
        paths = derive_candidate_paths(parent, key)
        if _absolute_path(
            value["selection_directory"],
            field="selection_directory",
        ) != str(paths.selection_directory) or _absolute_path(
            value["candidate_root"], field="candidate_root"
        ) != str(
            paths.candidate_root
        ):
            raise WarehouseW3InstallationError(
                "selection intent paths are not mechanically derived"
            )
        fields = {
            "selection_key": key,
            "task_event_identity": event,
            "launch_commit": commit,
            "launch_tree": tree,
            "dry_root_manifest_sha256": manifest,
            "native_record_sha256": native,
            "experiment_parent": str(parent),
            "selection_directory": str(paths.selection_directory),
            "candidate_root": str(paths.candidate_root),
            "raw": raw,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        return _new(cls, fields)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class CandidateRootIdentity:
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    nlink: int

    @classmethod
    def capture(cls, candidate_root: Path) -> "CandidateRootIdentity":
        if not isinstance(candidate_root, Path):
            raise TypeError("candidate_root must be a Path")
        metadata = os.stat(candidate_root, follow_symlinks=False)
        return cls.from_stat_result(metadata)

    @classmethod
    def capture_descriptor(cls, descriptor: int) -> "CandidateRootIdentity":
        if type(descriptor) is not int or descriptor < 0:
            raise TypeError("candidate root descriptor must be nonnegative int")
        try:
            metadata = os.fstat(descriptor)
        except OSError as exc:
            raise WarehouseW3InstallationError(
                "candidate root descriptor cannot be inspected"
            ) from exc
        return cls.from_stat_result(metadata)

    @classmethod
    def from_stat_result(cls, metadata: os.stat_result) -> "CandidateRootIdentity":
        if not isinstance(metadata, os.stat_result):
            raise TypeError("candidate root metadata must be os.stat_result")
        if not stat.S_ISDIR(metadata.st_mode):
            raise WarehouseW3InstallationError("candidate root is not a directory")
        return cls(
            device=metadata.st_dev,
            inode=metadata.st_ino,
            mode=stat.S_IMODE(metadata.st_mode),
            uid=metadata.st_uid,
            gid=metadata.st_gid,
            nlink=metadata.st_nlink,
        )

    @classmethod
    def from_mapping(cls, value: object) -> "CandidateRootIdentity":
        if type(value) is not dict:
            raise WarehouseW3InstallationError(
                "candidate root identity is not a mapping"
            )
        _exact_keys(
            value,
            frozenset({"device", "inode", "mode", "uid", "gid", "nlink"}),
            label="candidate root identity",
        )
        mode = _positive_int(
            value["mode"], field="candidate_root.mode", allow_zero=True
        )
        if mode > 0o7777:
            raise WarehouseW3InstallationError("candidate_root.mode is invalid")
        return cls(
            device=_positive_int(value["device"], field="candidate_root.device"),
            inode=_positive_int(value["inode"], field="candidate_root.inode"),
            mode=mode,
            uid=_positive_int(
                value["uid"], field="candidate_root.uid", allow_zero=True
            ),
            gid=_positive_int(
                value["gid"], field="candidate_root.gid", allow_zero=True
            ),
            nlink=_positive_int(value["nlink"], field="candidate_root.nlink"),
        )

    def to_mapping(self) -> dict[str, int]:
        return {
            "device": self.device,
            "inode": self.inode,
            "mode": self.mode,
            "uid": self.uid,
            "gid": self.gid,
            "nlink": self.nlink,
        }


@dataclass(frozen=True, slots=True, init=False)
class CandidateSelectionCommit:
    selection_key: str
    intent_sha256: str
    candidate_root: str
    candidate_root_identity: CandidateRootIdentity
    nonce: str
    authority_sha256: str
    launch_id: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "CandidateSelectionCommit":
        del cls
        raise TypeError("CandidateSelectionCommit must be parsed from exact bytes")

    @classmethod
    def create(
        cls,
        *,
        intent: CandidateSelectionIntent,
        candidate_root_identity: CandidateRootIdentity,
        nonce: str,
        authority_sha256: str,
    ) -> "CandidateSelectionCommit":
        if type(intent) is not CandidateSelectionIntent:
            raise TypeError("intent must be exact CandidateSelectionIntent")
        if type(candidate_root_identity) is not CandidateRootIdentity:
            raise TypeError(
                "candidate_root_identity must be exact CandidateRootIdentity"
            )
        nonce_value = _sha256_text(nonce, field="nonce")
        authority = _sha256_text(authority_sha256, field="authority_sha256")
        value = {
            "schema": _SELECTION_COMMIT_SCHEMA,
            "selection_key": intent.selection_key,
            "intent_sha256": intent.raw_sha256,
            "candidate_root": intent.candidate_root,
            "candidate_root_identity": candidate_root_identity.to_mapping(),
            "nonce": nonce_value,
            "authority_sha256": authority,
            "launch_id": derive_launch_id(authority, nonce_value),
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(_canonical_json(value), intent)

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        intent: CandidateSelectionIntent,
    ) -> "CandidateSelectionCommit":
        if type(intent) is not CandidateSelectionIntent:
            raise TypeError("intent must be exact CandidateSelectionIntent")
        value = _decode_canonical(raw, label="candidate selection commit")
        _exact_keys(
            value,
            frozenset(
                {
                    "schema",
                    "selection_key",
                    "intent_sha256",
                    "candidate_root",
                    "candidate_root_identity",
                    "nonce",
                    "authority_sha256",
                    "launch_id",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="candidate selection commit",
        )
        if value["schema"] != _SELECTION_COMMIT_SCHEMA:
            raise WarehouseW3InstallationError("selection commit schema differs")
        _false_controls(value, label="candidate selection commit")
        key = _sha256_text(value["selection_key"], field="selection_key")
        intent_sha = _sha256_text(value["intent_sha256"], field="intent_sha256")
        candidate_root = _absolute_path(
            value["candidate_root"],
            field="candidate_root",
        )
        if (
            key != intent.selection_key
            or intent_sha != intent.raw_sha256
            or candidate_root != intent.candidate_root
        ):
            raise WarehouseW3InstallationError("selection commit differs from intent")
        identity = CandidateRootIdentity.from_mapping(value["candidate_root_identity"])
        nonce = _sha256_text(value["nonce"], field="nonce")
        authority = _sha256_text(value["authority_sha256"], field="authority_sha256")
        launch_id = _sha256_text(value["launch_id"], field="launch_id")
        if launch_id != derive_launch_id(authority, nonce):
            raise WarehouseW3InstallationError("selection commit launch id differs")
        fields = {
            "selection_key": key,
            "intent_sha256": intent_sha,
            "candidate_root": candidate_root,
            "candidate_root_identity": identity,
            "nonce": nonce,
            "authority_sha256": authority,
            "launch_id": launch_id,
            "raw": raw,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        return _new(cls, fields)  # type: ignore[return-value]


def _require_nonroot() -> int:
    actual = os.geteuid()
    if type(actual) is not int or actual < 0:
        raise TypeError("effective uid must be one nonnegative integer")
    if actual == 0:
        raise WarehouseW3InstallationError(
            "candidate preparation refuses effective uid zero"
        )
    return actual


def _opened_directory(path: Path, *, label: str) -> tuple[int, os.stat_result]:
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        named = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        if "descriptor" in locals():
            os.close(descriptor)
        raise WarehouseW3InstallationError(f"cannot pin {label}") from exc
    if not stat.S_ISDIR(opened.st_mode) or (
        opened.st_dev,
        opened.st_ino,
        opened.st_mode,
        opened.st_uid,
        opened.st_gid,
        opened.st_nlink,
    ) != (
        named.st_dev,
        named.st_ino,
        named.st_mode,
        named.st_uid,
        named.st_gid,
        named.st_nlink,
    ):
        os.close(descriptor)
        raise WarehouseW3InstallationError(f"{label} identity differs")
    return descriptor, opened


def _opened_child_directory(
    parent_fd: int,
    name: str,
    *,
    label: str,
) -> tuple[int, os.stat_result]:
    if "/" in name or name in {"", ".", ".."}:
        raise TypeError(f"{label} leaf differs")
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
        opened = os.fstat(descriptor)
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        if "descriptor" in locals():
            os.close(descriptor)
        raise WarehouseW3InstallationError(f"cannot pin {label}") from exc
    if not stat.S_ISDIR(opened.st_mode) or (
        opened.st_dev,
        opened.st_ino,
        opened.st_mode,
        opened.st_uid,
        opened.st_gid,
        opened.st_nlink,
    ) != (
        named.st_dev,
        named.st_ino,
        named.st_mode,
        named.st_uid,
        named.st_gid,
        named.st_nlink,
    ):
        os.close(descriptor)
        raise WarehouseW3InstallationError(f"{label} identity differs")
    return descriptor, opened


def _write_no_replace(
    directory_fd: int,
    name: str,
    raw: bytes,
    *,
    label: str,
) -> None:
    if "/" in name or name in {"", ".", ".."} or type(raw) is not bytes:
        raise TypeError(f"{label} publication arguments differ")
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(name, flags, 0o444, dir_fd=directory_fd)
    except OSError as exc:
        raise WarehouseW3InstallationError(
            f"{label} already exists or cannot open"
        ) from exc
    try:
        os.fchmod(descriptor, 0o444)
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short zero-length receipt write")
            view = view[written:]
        os.fsync(descriptor)
    except OSError as exc:
        raise WarehouseW3InstallationError(
            f"{label} publication is a partial hold"
        ) from exc
    finally:
        os.close(descriptor)
    try:
        os.fsync(directory_fd)
    except OSError as exc:
        raise WarehouseW3InstallationError(
            f"{label} directory fsync is a partial hold"
        ) from exc


def _read_exact_receipt_at(
    directory_fd: int,
    name: str,
    *,
    maximum: int = 256 * 1024,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise WarehouseW3InstallationError(f"cannot reopen {name}") from exc
    chunks: list[bytes] = []
    total = 0
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode) != 0o444:
            raise WarehouseW3InstallationError(f"{name} is not immutable regular")
        while True:
            chunk = os.read(descriptor, min(64 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise WarehouseW3InstallationError(f"{name} exceeds its bound")
        after = os.fstat(descriptor)
        named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError as exc:
        raise WarehouseW3InstallationError(f"cannot read {name}") from exc
    finally:
        os.close(descriptor)
    if (
        (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        or (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        != (
            named.st_dev,
            named.st_ino,
            named.st_mode,
            named.st_nlink,
            named.st_size,
            named.st_mtime_ns,
            named.st_ctime_ns,
        )
        or total != after.st_size
    ):
        raise WarehouseW3InstallationError(f"{name} changed while reopened")
    return b"".join(chunks)


class CandidateSelectionOwner:
    """One-process non-root owner for the no-replace selection pair."""

    __slots__ = (
        "_intent",
        "_paths",
        "_selection_fd",
        "_selections_fd",
        "_state",
        "_effective_uid",
    )

    def __init__(
        self,
        intent: CandidateSelectionIntent,
    ) -> None:
        if type(intent) is not CandidateSelectionIntent:
            raise TypeError("intent must be exact CandidateSelectionIntent")
        self._intent = intent
        self._paths = derive_candidate_paths(
            Path(intent.experiment_parent),
            intent.selection_key,
        )
        self._selection_fd = -1
        self._selections_fd = -1
        self._state = "NEW"
        self._effective_uid = _require_nonroot()

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("CandidateSelectionOwner is final")

    @property
    def state(self) -> str:
        return self._state

    def publish_intent(self) -> CandidateSelectionIntent:
        if self._state != "NEW":
            raise WarehouseW3InstallationError("selection intent owner is already used")
        parent = self._paths.experiment_parent
        try:
            if parent.resolve(strict=True) != parent:
                raise WarehouseW3InstallationError(
                    "experiment parent is not one direct canonical directory"
                )
            if os.path.lexists(self._paths.candidate_root):
                raise WarehouseW3InstallationError("candidate root already exists")
            parent_fd, parent_stat = _opened_directory(
                parent,
                label="experiment parent",
            )
        except OSError as exc:
            raise WarehouseW3InstallationError(
                "candidate preparation parent cannot be inspected"
            ) from exc
        if parent_stat.st_uid != os.geteuid():
            os.close(parent_fd)
            raise WarehouseW3InstallationError(
                "experiment parent is not owned by the current user"
            )
        try:
            try:
                os.mkdir(".scion-w3-selections", 0o700, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except FileExistsError:
                pass
            selections_fd, selections_stat = _opened_child_directory(
                parent_fd,
                ".scion-w3-selections",
                label="selection parent",
            )
            self._selections_fd = selections_fd
            if (
                selections_stat.st_uid != os.geteuid()
                or stat.S_IMODE(selections_stat.st_mode) != 0o700
            ):
                raise WarehouseW3InstallationError(
                    "selection parent ownership or mode differs"
                )
            try:
                os.mkdir(self._intent.selection_key, 0o700, dir_fd=selections_fd)
            except OSError as exc:
                raise WarehouseW3InstallationError(
                    "selection key already exists or cannot be created"
                ) from exc
            os.fsync(selections_fd)
            selection_fd, selection_stat = _opened_child_directory(
                selections_fd,
                self._intent.selection_key,
                label="selection directory",
            )
            self._selection_fd = selection_fd
            if (
                selection_stat.st_uid != os.geteuid()
                or stat.S_IMODE(selection_stat.st_mode) != 0o700
                or os.listdir(selection_fd)
            ):
                raise WarehouseW3InstallationError(
                    "fresh selection directory identity differs"
                )
            _write_no_replace(
                selection_fd,
                "intent.v1.json",
                self._intent.raw,
                label="selection intent",
            )
            reopened = CandidateSelectionIntent.from_bytes(
                _read_exact_receipt_at(selection_fd, "intent.v1.json")
            )
            if reopened != self._intent:
                raise WarehouseW3InstallationError("durable selection intent differs")
            self._state = "INTENT_PUBLISHED"
            return reopened
        except BaseException:
            self.close()
            raise
        finally:
            os.close(parent_fd)

    def commit(
        self,
        *,
        nonce: str,
        authority_sha256: str,
    ) -> CandidateSelectionCommit:
        if self._state != "INTENT_PUBLISHED" or self._selection_fd < 0:
            raise WarehouseW3InstallationError(
                "selection intent is not live for commit"
            )
        if (
            self._paths.candidate_root.resolve(strict=True)
            != self._paths.candidate_root
        ):
            raise WarehouseW3InstallationError(
                "candidate root is not one direct canonical directory"
            )
        identity = CandidateRootIdentity.capture(self._paths.candidate_root)
        if (
            identity.mode != 0o555
            or identity.uid != os.geteuid()
            or identity.gid != os.getegid()
        ):
            raise WarehouseW3InstallationError(
                "candidate root is not immutable and current-user owned"
            )
        if tuple(sorted(os.listdir(self._selection_fd))) != ("intent.v1.json",):
            raise WarehouseW3InstallationError(
                "selection directory inventory differs before commit"
            )
        committed = CandidateSelectionCommit.create(
            intent=self._intent,
            candidate_root_identity=identity,
            nonce=nonce,
            authority_sha256=authority_sha256,
        )
        try:
            _write_no_replace(
                self._selection_fd,
                "committed.v1.json",
                committed.raw,
                label="selection commit",
            )
            reopened = CandidateSelectionCommit.from_bytes(
                _read_exact_receipt_at(
                    self._selection_fd,
                    "committed.v1.json",
                ),
                self._intent,
            )
            if reopened != committed:
                raise WarehouseW3InstallationError("durable selection commit differs")
            if tuple(sorted(os.listdir(self._selection_fd))) != (
                "committed.v1.json",
                "intent.v1.json",
            ):
                raise WarehouseW3InstallationError("closed selection inventory differs")
            os.fchmod(self._selection_fd, 0o555)
            os.fsync(self._selection_fd)
            os.fsync(self._selections_fd)
            self._state = "COMMITTED"
            self.close()
            return reopened
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self._selection_fd >= 0:
            os.close(self._selection_fd)
            self._selection_fd = -1
        if self._selections_fd >= 0:
            os.close(self._selections_fd)
            self._selections_fd = -1
        if self._state not in {"COMMITTED", "CLOSED"}:
            self._state = "CLOSED"


class GitRunner(Protocol):
    """Narrow subprocess seam used by the source acquirer."""

    def run(self, argv: tuple[str, ...], *, cwd: Path) -> bytes:
        """Run one exact argv without a shell and return stdout bytes."""


class SubprocessGitRunner:
    """Non-interactive Git runner; tests use a fake and never access a remote."""

    __slots__ = ()

    def run(self, argv: tuple[str, ...], *, cwd: Path) -> bytes:
        if (
            type(argv) is not tuple
            or not argv
            or argv[0] != "git"
            or any(type(item) is not str or not item for item in argv)
        ):
            raise TypeError("Git argv is not one fixed exact tuple")
        environment = dict(os.environ)
        for name in tuple(environment):
            if name.startswith("GIT_"):
                del environment[name]
        environment.update(
            {
                "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_TERMINAL_PROMPT": "0",
                "LANG": "C",
                "LC_ALL": "C",
            }
        )
        try:
            completed = subprocess.run(
                argv,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                shell=False,
                env=environment,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise WarehouseW3InstallationError(
                f"Git command could not run: {argv[1]}"
            ) from exc
        if completed.returncode != 0:
            error = completed.stderr[:4096].decode("utf-8", "replace").strip()
            raise WarehouseW3InstallationError(
                f"Git command failed: {argv[1]}: {error}"
            )
        return bytes(completed.stdout)


def _git_blob_oid(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def _one_ascii_line(
    raw: bytes,
    *,
    label: str,
    allow_tab: bool = False,
) -> str:
    if (
        type(raw) is not bytes
        or len(raw) > _MAX_GIT_TEXT_BYTES
        or not raw.endswith(b"\n")
        or raw.count(b"\n") != 1
    ):
        raise WarehouseW3InstallationError(f"{label} is not one exact line")
    try:
        value = raw[:-1].decode("ascii", "strict")
    except UnicodeError as exc:
        raise WarehouseW3InstallationError(f"{label} is not ASCII") from exc
    if not value or any(
        ord(character) < 0x20 and not (allow_tab and character == "\t")
        for character in value
    ):
        raise WarehouseW3InstallationError(f"{label} contains invalid text")
    return value


@dataclass(frozen=True, slots=True)
class GitBlobIdentity:
    logical_path: str
    mode: str
    blob_oid: str
    sha256: str
    size_bytes: int

    @classmethod
    def from_mapping(cls, value: object) -> "GitBlobIdentity":
        if type(value) is not dict:
            raise WarehouseW3InstallationError("Git blob identity is not a mapping")
        _exact_keys(
            value,
            frozenset({"logical_path", "mode", "blob_oid", "sha256", "size_bytes"}),
            label="Git blob identity",
        )
        mode = value["mode"]
        if mode not in {"100644", "100755"}:
            raise WarehouseW3InstallationError("Git blob mode is not a regular file")
        return cls(
            logical_path=_relative_path(
                value["logical_path"],
                field="logical_path",
            ),
            mode=mode,
            blob_oid=_git_oid(value["blob_oid"], field="blob_oid"),
            sha256=_sha256_text(value["sha256"], field="blob.sha256"),
            size_bytes=_positive_int(
                value["size_bytes"],
                field="blob.size_bytes",
                allow_zero=True,
            ),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "logical_path": self.logical_path,
            "mode": self.mode,
            "blob_oid": self.blob_oid,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class GitBlobFact:
    source_commit: str
    source_tree: str
    identity: GitBlobIdentity
    raw: bytes

    def __post_init__(self) -> None:
        _git_oid(self.source_commit, field="source_commit")
        _git_oid(self.source_tree, field="source_tree")
        if type(self.identity) is not GitBlobIdentity or type(self.raw) is not bytes:
            raise TypeError("GitBlobFact fields are not exact")
        if (
            self.identity.size_bytes != len(self.raw)
            or self.identity.sha256 != hashlib.sha256(self.raw).hexdigest()
            or self.identity.blob_oid != _git_blob_oid(self.raw)
        ):
            raise WarehouseW3InstallationError("Git blob bytes differ from identity")

    @property
    def logical_path(self) -> str:
        return self.identity.logical_path

    @property
    def blob_oid(self) -> str:
        return self.identity.blob_oid

    @property
    def sha256(self) -> str:
        return self.identity.sha256

    @property
    def size_bytes(self) -> int:
        return self.identity.size_bytes


@dataclass(frozen=True, slots=True, init=False)
class GitSourceReceipt:
    source_commit: str
    source_tree: str
    remote_name: str
    remote_url: str
    remote_ref: str
    remote_tracking_ref: str
    remote_observed_sha: str
    blobs: tuple[GitBlobIdentity, ...]
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "GitSourceReceipt":
        del cls
        raise TypeError("GitSourceReceipt must be parsed from exact bytes")

    @classmethod
    def create(
        cls,
        *,
        source_commit: str,
        source_tree: str,
        remote_name: str,
        remote_url: str,
        remote_ref: str,
        remote_tracking_ref: str,
        blobs: tuple[GitBlobIdentity, ...],
    ) -> "GitSourceReceipt":
        value = {
            "schema": _SOURCE_RECEIPT_SCHEMA,
            "source_commit": source_commit,
            "source_tree": source_tree,
            "remote_name": remote_name,
            "remote_url": remote_url,
            "remote_ref": remote_ref,
            "remote_tracking_ref": remote_tracking_ref,
            "remote_observed_sha": source_commit,
            "blobs": [item.to_mapping() for item in blobs],
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "GitSourceReceipt":
        value = _decode_canonical(raw, label="Git source receipt")
        _exact_keys(
            value,
            frozenset(
                {
                    "schema",
                    "source_commit",
                    "source_tree",
                    "remote_name",
                    "remote_url",
                    "remote_ref",
                    "remote_tracking_ref",
                    "remote_observed_sha",
                    "blobs",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="Git source receipt",
        )
        if value["schema"] != _SOURCE_RECEIPT_SCHEMA:
            raise WarehouseW3InstallationError("Git source receipt schema differs")
        _false_controls(value, label="Git source receipt")
        commit = _git_oid(value["source_commit"], field="source_commit")
        tree = _git_oid(value["source_tree"], field="source_tree")
        remote = _remote_name(value["remote_name"])
        remote_ref = _full_branch_ref(value["remote_ref"])
        expected_tracking = (
            f"refs/remotes/{remote}/{remote_ref.removeprefix('refs/heads/')}"
        )
        if value["remote_tracking_ref"] != expected_tracking:
            raise WarehouseW3InstallationError("Git source remote-tracking ref differs")
        if (
            _git_oid(
                value["remote_observed_sha"],
                field="remote_observed_sha",
            )
            != commit
        ):
            raise WarehouseW3InstallationError("Git source remote observation differs")
        remote_url = value["remote_url"]
        if (
            type(remote_url) is not str
            or not remote_url
            or any(ord(character) < 0x20 for character in remote_url)
        ):
            raise WarehouseW3InstallationError("Git source remote URL differs")
        raw_blobs = value["blobs"]
        if type(raw_blobs) is not list or not raw_blobs:
            raise WarehouseW3InstallationError("Git source blob inventory is empty")
        blobs = tuple(GitBlobIdentity.from_mapping(item) for item in raw_blobs)
        paths = tuple(item.logical_path for item in blobs)
        if paths != tuple(sorted(paths, key=lambda item: item.encode("utf-8"))) or len(
            set(paths)
        ) != len(paths):
            raise WarehouseW3InstallationError(
                "Git source blob inventory is not sorted and unique"
            )
        fields = {
            "source_commit": commit,
            "source_tree": tree,
            "remote_name": remote,
            "remote_url": remote_url,
            "remote_ref": remote_ref,
            "remote_tracking_ref": expected_tracking,
            "remote_observed_sha": commit,
            "blobs": blobs,
            "raw": raw,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        return _new(cls, fields)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class GitSourceSnapshot:
    receipt: GitSourceReceipt
    blobs: tuple[GitBlobFact, ...]

    def __post_init__(self) -> None:
        if type(self.receipt) is not GitSourceReceipt:
            raise TypeError("receipt must be exact GitSourceReceipt")
        if type(self.blobs) is not tuple or any(
            type(item) is not GitBlobFact for item in self.blobs
        ):
            raise TypeError("blobs must be an exact GitBlobFact tuple")
        if tuple(item.identity for item in self.blobs) != self.receipt.blobs:
            raise WarehouseW3InstallationError(
                "Git source snapshot differs from receipt"
            )


class GitSourceAcquirer:
    """Acquire one clean, pushed commit and exact Git blob set."""

    __slots__ = ("_repo_root", "_runner")

    def __init__(
        self,
        repo_root: Path,
        *,
        runner: GitRunner | None = None,
    ) -> None:
        if not isinstance(repo_root, Path):
            raise TypeError("repo_root must be a Path")
        root = Path(_absolute_path(str(repo_root), field="repo_root"))
        if not root.is_dir():
            raise WarehouseW3InstallationError("repo_root is not a directory")
        selected_runner: GitRunner = SubprocessGitRunner() if runner is None else runner
        if not callable(getattr(selected_runner, "run", None)):
            raise TypeError("runner lacks run")
        self._repo_root = root
        self._runner = selected_runner

    def _run(
        self,
        argv: tuple[str, ...],
        *,
        maximum: int = _MAX_GIT_TEXT_BYTES,
    ) -> bytes:
        try:
            output = self._runner.run(argv, cwd=self._repo_root)
        except WarehouseW3InstallationError:
            raise
        except Exception as exc:
            raise WarehouseW3InstallationError(
                f"Git runner failed for {argv[1]}"
            ) from exc
        if type(output) is not bytes or len(output) > maximum:
            raise WarehouseW3InstallationError(
                f"Git output for {argv[1]} exceeds its exact bound"
            )
        return output

    def acquire(
        self,
        *,
        launch_commit: str,
        remote_name: str,
        remote_ref: str,
        logical_paths: tuple[str, ...],
    ) -> GitSourceSnapshot:
        commit = _git_oid(launch_commit, field="launch_commit")
        remote = _remote_name(remote_name)
        full_ref = _full_branch_ref(remote_ref)
        if type(logical_paths) is not tuple or not logical_paths:
            raise TypeError("logical_paths must be one nonempty exact tuple")
        paths = tuple(
            sorted(
                (_relative_path(item, field="logical_path") for item in logical_paths),
                key=lambda item: item.encode("utf-8"),
            )
        )
        if len(set(paths)) != len(paths):
            raise WarehouseW3InstallationError("logical_paths contains a duplicate")

        head = _git_oid(
            _one_ascii_line(
                self._run(("git", "rev-parse", "--verify", "HEAD^{commit}")),
                label="Git HEAD",
            ),
            field="Git HEAD",
        )
        resolved = _git_oid(
            _one_ascii_line(
                self._run(("git", "rev-parse", "--verify", f"{commit}^{{commit}}")),
                label="Git launch commit",
            ),
            field="Git launch commit",
        )
        tree = _git_oid(
            _one_ascii_line(
                self._run(("git", "rev-parse", "--verify", f"{commit}^{{tree}}")),
                label="Git launch tree",
            ),
            field="Git launch tree",
        )
        if head != commit or resolved != commit:
            raise WarehouseW3InstallationError(
                "Git HEAD is not the exact launch commit"
            )
        if (
            self._run(("git", "status", "--porcelain=v1", "--untracked-files=all"))
            != b""
        ):
            raise WarehouseW3InstallationError("Git working tree is not clean")

        remote_url = _one_ascii_line(
            self._run(("git", "remote", "get-url", remote)),
            label="Git remote URL",
        )
        branch = full_ref.removeprefix("refs/heads/")
        tracking_ref = f"refs/remotes/{remote}/{branch}"
        tracking = _git_oid(
            _one_ascii_line(
                self._run(
                    (
                        "git",
                        "rev-parse",
                        "--verify",
                        f"{tracking_ref}^{{commit}}",
                    )
                ),
                label="Git remote-tracking commit",
            ),
            field="Git remote-tracking commit",
        )
        if tracking != commit:
            raise WarehouseW3InstallationError("Git remote-tracking commit differs")
        remote_line = _one_ascii_line(
            self._run(
                (
                    "git",
                    "ls-remote",
                    "--exit-code",
                    remote,
                    full_ref,
                )
            ),
            label="Git ls-remote observation",
            allow_tab=True,
        )
        if remote_line != f"{commit}\t{full_ref}":
            raise WarehouseW3InstallationError("Git ls-remote observation differs")

        facts: list[GitBlobFact] = []
        for logical_path in paths:
            entry_raw = self._run(
                (
                    "git",
                    "ls-tree",
                    "-z",
                    "--full-tree",
                    commit,
                    "--",
                    logical_path,
                )
            )
            if not entry_raw.endswith(b"\0") or entry_raw.count(b"\0") != 1:
                raise WarehouseW3InstallationError(
                    f"Git tree path is not one exact entry: {logical_path}"
                )
            entry = entry_raw[:-1]
            try:
                header, encoded_path = entry.split(b"\t", 1)
                mode_raw, kind_raw, oid_raw = header.split(b" ", 2)
                actual_path = encoded_path.decode("utf-8", "strict")
                mode = mode_raw.decode("ascii", "strict")
                kind = kind_raw.decode("ascii", "strict")
                oid = oid_raw.decode("ascii", "strict")
            except (ValueError, UnicodeError) as exc:
                raise WarehouseW3InstallationError(
                    f"Git tree entry is malformed: {logical_path}"
                ) from exc
            if (
                actual_path != logical_path
                or kind != "blob"
                or mode
                not in {
                    "100644",
                    "100755",
                }
            ):
                raise WarehouseW3InstallationError(
                    f"Git tree entry differs: {logical_path}"
                )
            blob_oid = _git_oid(oid, field=f"{logical_path}.blob_oid")
            size_line = _one_ascii_line(
                self._run(("git", "cat-file", "-s", blob_oid)),
                label=f"{logical_path} Git blob size",
            )
            try:
                declared_size = int(size_line, 10)
            except ValueError as exc:
                raise WarehouseW3InstallationError(
                    f"Git blob size is invalid: {logical_path}"
                ) from exc
            if not 0 <= declared_size <= _MAX_GIT_BLOB_BYTES:
                raise WarehouseW3InstallationError(
                    f"Git blob size is outside the bound: {logical_path}"
                )
            raw = self._run(
                ("git", "cat-file", "blob", blob_oid),
                maximum=_MAX_GIT_BLOB_BYTES,
            )
            if len(raw) != declared_size or _git_blob_oid(raw) != blob_oid:
                raise WarehouseW3InstallationError(
                    f"Git blob bytes differ from object id: {logical_path}"
                )
            identity = GitBlobIdentity(
                logical_path=logical_path,
                mode=mode,
                blob_oid=blob_oid,
                sha256=hashlib.sha256(raw).hexdigest(),
                size_bytes=len(raw),
            )
            facts.append(
                GitBlobFact(
                    source_commit=commit,
                    source_tree=tree,
                    identity=identity,
                    raw=raw,
                )
            )
        blobs = tuple(facts)
        receipt = GitSourceReceipt.create(
            source_commit=commit,
            source_tree=tree,
            remote_name=remote,
            remote_url=remote_url,
            remote_ref=full_ref,
            remote_tracking_ref=tracking_ref,
            blobs=tuple(item.identity for item in blobs),
        )
        return GitSourceSnapshot(receipt=receipt, blobs=blobs)


@dataclass(frozen=True, slots=True)
class AuthorityInputAdapter:
    """One exact mapping for the accepted generic authority input schema."""

    logical_path: str
    sealed_path: str
    sha256: str
    size_bytes: int
    provenance: tuple[tuple[str, object], ...]

    @classmethod
    def from_git_blob(
        cls,
        blob: GitBlobFact,
        *,
        sealed_path: str | None = None,
    ) -> "AuthorityInputAdapter":
        if type(blob) is not GitBlobFact:
            raise TypeError("blob must be exact GitBlobFact")
        destination = (
            f"sealed/{blob.logical_path}" if sealed_path is None else sealed_path
        )
        return cls(
            logical_path=_relative_path(blob.logical_path, field="logical_path"),
            sealed_path=_relative_path(destination, field="sealed_path"),
            sha256=blob.sha256,
            size_bytes=blob.size_bytes,
            provenance=(
                ("blob_oid", blob.blob_oid),
                ("commit", blob.source_commit),
                ("kind", "git_blob"),
                ("path", blob.logical_path),
            ),
        )

    @classmethod
    def external_evidence(
        cls,
        *,
        logical_path: str,
        sealed_path: str,
        sha256: str,
        size_bytes: int,
        source_path: Path,
        device: int,
        inode: int,
    ) -> "AuthorityInputAdapter":
        if not isinstance(source_path, Path):
            raise TypeError("source_path must be a Path")
        return cls(
            logical_path=_relative_path(logical_path, field="logical_path"),
            sealed_path=_relative_path(sealed_path, field="sealed_path"),
            sha256=_sha256_text(sha256, field="input.sha256"),
            size_bytes=_positive_int(
                size_bytes,
                field="input.size_bytes",
                allow_zero=True,
            ),
            provenance=(
                ("device", _positive_int(device, field="input.device")),
                ("inode", _positive_int(inode, field="input.inode")),
                ("kind", "external_evidence"),
                (
                    "source_path",
                    _absolute_path(str(source_path), field="input.source_path"),
                ),
            ),
        )

    @classmethod
    def generated(
        cls,
        *,
        logical_path: str,
        sealed_path: str,
        raw: bytes,
        generator_sha256: str,
        input_sha256: tuple[str, ...],
        rule_sha256: str,
    ) -> "AuthorityInputAdapter":
        if type(raw) is not bytes:
            raise TypeError("generated input raw must be exact bytes")
        if (
            type(input_sha256) is not tuple
            or not input_sha256
            or any(type(item) is not str for item in input_sha256)
        ):
            raise TypeError("generated input_sha256 must be one nonempty exact tuple")
        inputs = tuple(
            sorted(
                (
                    _sha256_text(item, field="generated.input_sha256")
                    for item in input_sha256
                ),
                key=lambda item: item.encode("ascii"),
            )
        )
        if len(set(inputs)) != len(inputs):
            raise WarehouseW3InstallationError(
                "generated input_sha256 contains a duplicate"
            )
        return cls(
            logical_path=_relative_path(logical_path, field="logical_path"),
            sealed_path=_relative_path(sealed_path, field="sealed_path"),
            sha256=hashlib.sha256(raw).hexdigest(),
            size_bytes=len(raw),
            provenance=(
                (
                    "generator_sha256",
                    _sha256_text(
                        generator_sha256,
                        field="generated.generator_sha256",
                    ),
                ),
                ("input_sha256", inputs),
                ("kind", "generated"),
                (
                    "rule_sha256",
                    _sha256_text(
                        rule_sha256,
                        field="generated.rule_sha256",
                    ),
                ),
            ),
        )

    def __post_init__(self) -> None:
        _relative_path(self.logical_path, field="logical_path")
        sealed = _relative_path(self.sealed_path, field="sealed_path")
        if not sealed.startswith("sealed/"):
            raise WarehouseW3InstallationError("sealed_path must be below sealed/")
        _sha256_text(self.sha256, field="input.sha256")
        _positive_int(self.size_bytes, field="input.size_bytes", allow_zero=True)
        if type(self.provenance) is not tuple:
            raise TypeError("provenance must be an exact tuple")

    def to_mapping(self) -> dict[str, object]:
        return {
            "logical_path": self.logical_path,
            "sealed_path": self.sealed_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "provenance": dict(self.provenance),
        }


def _source_fact(
    source: GitSourceSnapshot,
    logical_path: str,
) -> GitBlobFact:
    matches = [item for item in source.blobs if item.logical_path == logical_path]
    if len(matches) != 1:
        raise WarehouseW3InstallationError(
            f"launch source lacks one exact {logical_path}"
        )
    return matches[0]


def build_warehouse_launch_authority(
    source: GitSourceSnapshot,
    *,
    manifest_input: AuthorityInputAdapter,
    native_record_input: AuthorityInputAdapter,
    root_basename: str,
    nonce: str,
    sealed_store_aggregate_sha256: str,
    environment_receipt_sha256: str,
    extra_inputs: tuple[AuthorityInputAdapter, ...] = (),
) -> AcceptedLaunchAuthority:
    """Build and parse the one Warehouse-owned generic launch authority."""

    if type(source) is not GitSourceSnapshot:
        raise TypeError("source must be exact GitSourceSnapshot")
    if type(manifest_input) is not AuthorityInputAdapter:
        raise TypeError("manifest_input must be exact AuthorityInputAdapter")
    if type(native_record_input) is not AuthorityInputAdapter:
        raise TypeError("native_record_input must be exact AuthorityInputAdapter")
    if type(extra_inputs) is not tuple or any(
        type(item) is not AuthorityInputAdapter for item in extra_inputs
    ):
        raise TypeError("extra_inputs must be an exact AuthorityInputAdapter tuple")
    if (
        manifest_input.logical_path != EXPECTED_MANIFEST_NAME
        or manifest_input.sealed_path != f"sealed/{EXPECTED_MANIFEST_NAME}"
        or manifest_input.sha256 != EXPECTED_MANIFEST_SHA256
        or dict(manifest_input.provenance).get("kind") != "external_evidence"
    ):
        raise WarehouseW3InstallationError(
            "manifest input is not the accepted external evidence"
        )
    if (
        native_record_input.logical_path != W3_NATIVE_RECORD_LOGICAL_PATH
        or native_record_input.sealed_path != f"sealed/{W3_NATIVE_RECORD_LOGICAL_PATH}"
        or native_record_input.sha256 != EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256
        or dict(native_record_input.provenance).get("kind") != "external_evidence"
    ):
        raise WarehouseW3InstallationError(
            "native record input is not the accepted external evidence"
        )

    composition = _source_fact(source, W3_COMPOSITION_LOGICAL_PATH)
    tool = _source_fact(source, W3_TOOL_LOGICAL_PATH)
    run_template = _source_fact(source, W3_RUN_TEMPLATE_LOGICAL_PATH)
    close_template = _source_fact(source, W3_CLOSE_TEMPLATE_LOGICAL_PATH)
    adapters = (
        tuple(AuthorityInputAdapter.from_git_blob(item) for item in source.blobs)
        + (manifest_input, native_record_input)
        + extra_inputs
    )
    logical_paths = tuple(item.logical_path for item in adapters)
    sealed_paths = tuple(item.sealed_path for item in adapters)
    if len(set(logical_paths)) != len(logical_paths) or len(set(sealed_paths)) != len(
        sealed_paths
    ):
        raise WarehouseW3InstallationError(
            "authority input adapters contain a duplicate path"
        )
    mappings = [
        item.to_mapping()
        for item in sorted(
            adapters,
            key=lambda item: item.sealed_path.encode("utf-8"),
        )
    ]
    value = {
        "schema": "scion.generic-launch-authority.v1",
        "problem_kind": "warehouse-w3",
        "source_commit": source.receipt.source_commit,
        "source_tree": source.receipt.source_tree,
        "manifest": {
            "path": manifest_input.logical_path,
            "sha256": manifest_input.sha256,
            "size_bytes": manifest_input.size_bytes,
        },
        "root_basename": root_basename,
        "nonce": _sha256_text(nonce, field="nonce"),
        "nonce_ledger_parent": EXPECTED_NONCE_LEDGER_PARENT,
        "expected_rows": EXPECTED_ROWS,
        "artifact_names": list(EXPECTED_ARTIFACT_NAMES),
        "scientific_design_sha256": EXPECTED_SCIENTIFIC_DESIGN_SHA256,
        "correction_design_sha256": EXPECTED_CORRECTION_DESIGN_SHA256,
        "native_acceptance_contract_sha256": (
            EXPECTED_NATIVE_ACCEPTANCE_CONTRACT_SHA256
        ),
        "native_acceptance_record_sha256": (EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256),
        "sealed_store_aggregate_sha256": _sha256_text(
            sealed_store_aggregate_sha256,
            field="sealed_store_aggregate_sha256",
        ),
        "environment_receipt_sha256": _sha256_text(
            environment_receipt_sha256,
            field="environment_receipt_sha256",
        ),
        "run_template_sha256": run_template.sha256,
        "close_template_sha256": close_template.sha256,
        "guardian_source_sha256": composition.sha256,
        "thin_tool_source_sha256": tool.sha256,
        "closer_source_sha256": composition.sha256,
        "inputs": mappings,
        "retry": False,
        "resume": False,
        "reuse": False,
    }
    try:
        return AcceptedLaunchAuthority.from_bytes(_canonical_json(value))
    except Exception as exc:
        raise WarehouseW3InstallationError(
            "Warehouse launch authority could not be built"
        ) from exc


def build_warehouse_installation(
    authority: AcceptedLaunchAuthority,
    *,
    run_root: Path,
    run_template_raw: bytes,
    close_template_raw: bytes,
) -> InstallationRecord:
    """Build one acyclic installation record without touching any target path."""

    if type(authority) is not AcceptedLaunchAuthority:
        raise TypeError("authority must be exact AcceptedLaunchAuthority")
    if not isinstance(run_root, Path):
        raise TypeError("run_root must be a Path")
    if type(run_template_raw) is not bytes or type(close_template_raw) is not bytes:
        raise TypeError("unit templates must be exact bytes")
    root = _absolute_path(str(run_root), field="run_root")
    if PurePosixPath(root).name != authority.root_basename:
        raise WarehouseW3InstallationError("run_root basename differs from authority")
    if (
        hashlib.sha256(run_template_raw).hexdigest() != authority.run_template_sha256
        or hashlib.sha256(close_template_raw).hexdigest()
        != authority.close_template_sha256
    ):
        raise WarehouseW3InstallationError("unit template bytes differ from authority")
    try:
        run_template = parse_unit_template(run_template_raw)
        close_template = parse_unit_template(close_template_raw)
        launch_id = derive_launch_id(
            authority.authority_sha256,
            authority.nonce,
        )
        configured_pair = configured_pair_for_installation(
            launch_id,
            run_template,
            close_template,
        )
        value = {
            "schema": "scion.generic-launch-installation.v1",
            "launch_id": launch_id,
            "authority_sha256": authority.authority_sha256,
            "authority_path": (
                "/var/lib/scion/authorities/w3/" f"{authority.authority_sha256}.json"
            ),
            "problem_kind": authority.problem_kind,
            "manifest_sha256": authority.manifest_sha256,
            "run_root": root,
            "terminal_root": f"{root}/control/invocation",
            "nonce": authority.nonce,
            "nonce_ledger_parent": EXPECTED_NONCE_LEDGER_PARENT,
            "sealed_root": (f"/var/lib/scion/sealed/w3/{authority.manifest_sha256}"),
            "sealed_store_aggregate_sha256": (authority.sealed_store_aggregate_sha256),
            "environment_root": (
                "/var/lib/scion/environments/w3/"
                f"{authority.environment_receipt_sha256}"
            ),
            "environment_receipt_sha256": authority.environment_receipt_sha256,
            "projection_root": f"/var/lib/scion/projections/w3/{launch_id}",
            "run_template_sha256": authority.run_template_sha256,
            "close_template_sha256": authority.close_template_sha256,
            "run_unit": f"scion-w3@{launch_id}.service",
            "close_unit": f"scion-w3-close@{launch_id}.service",
            "configured_pair": configured_pair.to_mapping(),
            "configured_pair_sha256": configured_pair.configured_pair_sha256,
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return InstallationRecord.from_bytes(_canonical_json(value), authority)
    except WarehouseW3InstallationError:
        raise
    except Exception as exc:
        raise WarehouseW3InstallationError(
            "Warehouse installation could not be built"
        ) from exc


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
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


def _read_open_regular(
    descriptor: int,
    *,
    named: os.stat_result | None,
    maximum: int,
    label: str,
) -> tuple[bytes, os.stat_result]:
    chunks: list[bytes] = []
    total = 0
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) not in _REGULAR_MODES
        ):
            raise WarehouseW3InstallationError(
                f"{label} is not one immutable single-link regular file"
            )
        if named is not None and _stat_signature(before) != _stat_signature(named):
            raise WarehouseW3InstallationError(f"{label} opened identity differs")
        while True:
            chunk = os.read(descriptor, min(_READ_SIZE, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise WarehouseW3InstallationError(f"{label} exceeds its bound")
        after = os.fstat(descriptor)
    except OSError as exc:
        raise WarehouseW3InstallationError(f"cannot read {label}") from exc
    if _stat_signature(before) != _stat_signature(after) or total != after.st_size:
        raise WarehouseW3InstallationError(f"{label} changed while read")
    return b"".join(chunks), after


def _read_external_regular(path: Path, *, label: str) -> tuple[bytes, os.stat_result]:
    if not isinstance(path, Path):
        raise TypeError(f"{label} path must be Path")
    _absolute_path(str(path), field=f"{label}.path")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        named_before = os.stat(path, follow_symlinks=False)
        descriptor = os.open(path, flags)
    except OSError as exc:
        if "descriptor" in locals():
            os.close(descriptor)
        raise WarehouseW3InstallationError(f"cannot open {label}") from exc
    try:
        raw, opened = _read_open_regular(
            descriptor,
            named=named_before,
            maximum=_MAX_GIT_BLOB_BYTES,
            label=label,
        )
    finally:
        os.close(descriptor)
    try:
        named_after = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise WarehouseW3InstallationError(f"cannot reopen {label}") from exc
    if _stat_signature(opened) != _stat_signature(named_after):
        raise WarehouseW3InstallationError(f"{label} named identity changed")
    return raw, opened


@dataclass(frozen=True, slots=True)
class SealedStoreObject:
    """One acquired regular-file byte object for the candidate sealed store."""

    adapter: AuthorityInputAdapter
    raw: bytes
    mode: int

    def __post_init__(self) -> None:
        if (
            type(self.adapter) is not AuthorityInputAdapter
            or type(self.raw) is not bytes
        ):
            raise TypeError("sealed-store object fields are not exact")
        if self.mode not in _REGULAR_MODES:
            raise WarehouseW3InstallationError("sealed-store object mode differs")
        if (
            len(self.raw) != self.adapter.size_bytes
            or hashlib.sha256(self.raw).hexdigest() != self.adapter.sha256
        ):
            raise WarehouseW3InstallationError(
                "sealed-store object bytes differ from adapter"
            )

    @classmethod
    def from_git_blob(cls, blob: GitBlobFact) -> "SealedStoreObject":
        if type(blob) is not GitBlobFact:
            raise TypeError("blob must be exact GitBlobFact")
        return cls(
            adapter=AuthorityInputAdapter.from_git_blob(blob),
            raw=blob.raw,
            mode=0o555 if blob.identity.mode == "100755" else 0o444,
        )

    @classmethod
    def external_evidence(
        cls,
        *,
        logical_path: str,
        sealed_path: str,
        source_path: Path,
        executable: bool = False,
    ) -> "SealedStoreObject":
        if type(executable) is not bool:
            raise TypeError("executable must be exact bool")
        raw, identity = _read_external_regular(
            source_path,
            label="external evidence",
        )
        adapter = AuthorityInputAdapter.external_evidence(
            logical_path=logical_path,
            sealed_path=sealed_path,
            sha256=hashlib.sha256(raw).hexdigest(),
            size_bytes=len(raw),
            source_path=source_path,
            device=identity.st_dev,
            inode=identity.st_ino,
        )
        return cls(adapter=adapter, raw=raw, mode=0o555 if executable else 0o444)

    @classmethod
    def generated(
        cls,
        *,
        logical_path: str,
        sealed_path: str,
        raw: bytes,
        generator_sha256: str,
        input_sha256: tuple[str, ...],
        rule_sha256: str,
        executable: bool = False,
    ) -> "SealedStoreObject":
        if type(executable) is not bool:
            raise TypeError("executable must be exact bool")
        adapter = AuthorityInputAdapter.generated(
            logical_path=logical_path,
            sealed_path=sealed_path,
            raw=raw,
            generator_sha256=generator_sha256,
            input_sha256=input_sha256,
            rule_sha256=rule_sha256,
        )
        return cls(adapter=adapter, raw=raw, mode=0o555 if executable else 0o444)


@dataclass(frozen=True, slots=True)
class SealedStoreInventoryEntry:
    path: str
    kind: str
    mode: int
    size_bytes: int
    sha256: str | None
    provenance: tuple[tuple[str, object], ...] | None

    @classmethod
    def from_mapping(cls, value: object) -> "SealedStoreInventoryEntry":
        if type(value) is not dict:
            raise WarehouseW3InstallationError(
                "sealed-store inventory entry is not a mapping"
            )
        _exact_keys(
            value,
            frozenset(
                {
                    "path",
                    "kind",
                    "mode",
                    "size_bytes",
                    "sha256",
                    "provenance",
                }
            ),
            label="sealed-store inventory entry",
        )
        raw_path = value["path"]
        path = (
            "."
            if raw_path == "."
            else _relative_path(raw_path, field="sealed-store.path")
        )
        kind = value["kind"]
        if kind not in {"directory", "regular"}:
            raise WarehouseW3InstallationError("sealed-store entry kind differs")
        mode = _positive_int(
            value["mode"],
            field="sealed-store.mode",
            allow_zero=True,
        )
        size = _positive_int(
            value["size_bytes"],
            field="sealed-store.size_bytes",
            allow_zero=True,
        )
        if kind == "directory":
            if (
                mode != _DIRECTORY_MODE
                or size != 0
                or value["sha256"] is not None
                or value["provenance"] is not None
            ):
                raise WarehouseW3InstallationError(
                    "sealed-store directory facts differ"
                )
            sha256 = None
            provenance = None
        else:
            if path == "." or mode not in _REGULAR_MODES:
                raise WarehouseW3InstallationError(
                    "sealed-store regular-file facts differ"
                )
            sha256 = _sha256_text(value["sha256"], field="sealed-store.sha256")
            raw_provenance = value["provenance"]
            if type(raw_provenance) is not dict or not raw_provenance:
                raise WarehouseW3InstallationError("sealed-store provenance differs")
            if any(type(key) is not str for key in raw_provenance):
                raise WarehouseW3InstallationError(
                    "sealed-store provenance key differs"
                )
            _canonical_json(raw_provenance)
            provenance = tuple(
                (
                    key,
                    tuple(item) if type(item) is list else item,
                )
                for key, item in sorted(
                    raw_provenance.items(),
                    key=lambda pair: pair[0].encode("utf-8"),
                )
            )
        return cls(
            path=path,
            kind=kind,
            mode=mode,
            size_bytes=size,
            sha256=sha256,
            provenance=provenance,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "mode": self.mode,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "provenance": (
                None
                if self.provenance is None
                else {
                    key: list(item) if type(item) is tuple else item
                    for key, item in self.provenance
                }
            ),
        }


def _sealed_store_aggregate(
    inventory: tuple[SealedStoreInventoryEntry, ...],
) -> str:
    return hashlib.sha256(
        b"scion.w3-sealed-store-content.v1\0"
        + _canonical_json({"inventory": [item.to_mapping() for item in inventory]})
    ).hexdigest()


@dataclass(frozen=True, slots=True, init=False)
class SealedStoreReceipt:
    inventory: tuple[SealedStoreInventoryEntry, ...]
    aggregate_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "SealedStoreReceipt":
        del cls
        raise TypeError("SealedStoreReceipt must be parsed from exact bytes")

    @classmethod
    def create(
        cls,
        objects: tuple[SealedStoreObject, ...],
    ) -> "SealedStoreReceipt":
        if (
            type(objects) is not tuple
            or not objects
            or any(type(item) is not SealedStoreObject for item in objects)
        ):
            raise TypeError("objects must be one nonempty exact tuple")
        sealed_paths = tuple(item.adapter.sealed_path for item in objects)
        logical_paths = tuple(item.adapter.logical_path for item in objects)
        if len(set(sealed_paths)) != len(objects) or len(set(logical_paths)) != len(
            objects
        ):
            raise WarehouseW3InstallationError(
                "sealed-store objects contain a duplicate path"
            )
        directories = {"."}
        for path in sealed_paths:
            parent = PurePosixPath(path).parent
            while str(parent) != ".":
                directories.add(str(parent))
                parent = parent.parent
        entries: list[SealedStoreInventoryEntry] = [
            SealedStoreInventoryEntry(
                path=path,
                kind="directory",
                mode=_DIRECTORY_MODE,
                size_bytes=0,
                sha256=None,
                provenance=None,
            )
            for path in directories
        ]
        entries.extend(
            SealedStoreInventoryEntry(
                path=item.adapter.sealed_path,
                kind="regular",
                mode=item.mode,
                size_bytes=len(item.raw),
                sha256=hashlib.sha256(item.raw).hexdigest(),
                provenance=tuple(
                    sorted(
                        item.adapter.provenance,
                        key=lambda pair: pair[0].encode("utf-8"),
                    )
                ),
            )
            for item in objects
        )
        inventory = tuple(sorted(entries, key=lambda item: item.path.encode("utf-8")))
        value = {
            "schema": _SEALED_STORE_SCHEMA,
            "inventory": [item.to_mapping() for item in inventory],
            "aggregate_sha256": _sealed_store_aggregate(inventory),
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "SealedStoreReceipt":
        value = _decode_canonical(raw, label="sealed-store receipt")
        _exact_keys(
            value,
            frozenset(
                {
                    "schema",
                    "inventory",
                    "aggregate_sha256",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="sealed-store receipt",
        )
        if value["schema"] != _SEALED_STORE_SCHEMA:
            raise WarehouseW3InstallationError("sealed-store receipt schema differs")
        _false_controls(value, label="sealed-store receipt")
        raw_inventory = value["inventory"]
        if type(raw_inventory) is not list or not raw_inventory:
            raise WarehouseW3InstallationError("sealed-store inventory is empty")
        inventory = tuple(
            SealedStoreInventoryEntry.from_mapping(item) for item in raw_inventory
        )
        paths = tuple(item.path for item in inventory)
        if (
            paths != tuple(sorted(paths, key=lambda item: item.encode("utf-8")))
            or len(set(paths)) != len(paths)
            or inventory[0].path != "."
        ):
            raise WarehouseW3InstallationError(
                "sealed-store inventory order or paths differ"
            )
        by_path = {item.path: item for item in inventory}
        for item in inventory[1:]:
            parent = str(PurePosixPath(item.path).parent)
            parent_entry = by_path.get(parent)
            if parent_entry is None or parent_entry.kind != "directory":
                raise WarehouseW3InstallationError(
                    "sealed-store inventory parent closure differs"
                )
        aggregate = _sha256_text(
            value["aggregate_sha256"],
            field="sealed-store.aggregate_sha256",
        )
        if aggregate != _sealed_store_aggregate(inventory):
            raise WarehouseW3InstallationError(
                "sealed-store aggregate differs from inventory"
            )
        return _new(
            cls,
            {
                "inventory": inventory,
                "aggregate_sha256": aggregate,
                "raw": raw,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
            },
        )  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class CandidateContentEntry:
    path: str
    kind: str
    mode: int
    size_bytes: int
    sha256: str | None

    @classmethod
    def from_mapping(cls, value: object) -> "CandidateContentEntry":
        if type(value) is not dict:
            raise WarehouseW3InstallationError(
                "candidate content entry is not a mapping"
            )
        _exact_keys(
            value,
            frozenset({"path", "kind", "mode", "size_bytes", "sha256"}),
            label="candidate content entry",
        )
        path = _relative_path(value["path"], field="candidate content path")
        kind = value["kind"]
        if kind not in {"directory", "regular"}:
            raise WarehouseW3InstallationError("candidate content kind differs")
        mode = _positive_int(
            value["mode"],
            field="candidate content mode",
            allow_zero=True,
        )
        size = _positive_int(
            value["size_bytes"],
            field="candidate content size",
            allow_zero=True,
        )
        if kind == "directory":
            if mode != _DIRECTORY_MODE or size != 0 or value["sha256"] is not None:
                raise WarehouseW3InstallationError(
                    "candidate content directory facts differ"
                )
            sha256 = None
        else:
            if mode not in _REGULAR_MODES:
                raise WarehouseW3InstallationError(
                    "candidate content regular-file mode differs"
                )
            sha256 = _sha256_text(
                value["sha256"],
                field="candidate content sha256",
            )
        return cls(
            path=path,
            kind=kind,
            mode=mode,
            size_bytes=size,
            sha256=sha256,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "mode": self.mode,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


def _candidate_content_aggregate(
    *,
    content_inventory: tuple[CandidateContentEntry, ...],
    sealed_store_aggregate_sha256: str,
    environment_receipt_sha256: str,
) -> str:
    value = {
        "content_inventory": [item.to_mapping() for item in content_inventory],
        "sealed_store_aggregate_sha256": sealed_store_aggregate_sha256,
        "environment_receipt_sha256": environment_receipt_sha256,
    }
    return hashlib.sha256(
        b"scion.w3-candidate-content.v1\0" + _canonical_json(value)
    ).hexdigest()


@dataclass(frozen=True, slots=True, init=False)
class CandidateReceipt:
    selection_key: str
    candidate_root: str
    inventory: tuple[str, ...]
    content_inventory: tuple[CandidateContentEntry, ...]
    tail_paths: tuple[str, ...]
    content_aggregate_sha256: str
    sealed_store_aggregate_sha256: str
    environment_receipt_sha256: str
    authority_sha256: str
    installation_sha256: str
    selection_commit_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "CandidateReceipt":
        del cls
        raise TypeError("CandidateReceipt must be parsed from exact bytes")

    @classmethod
    def create(
        cls,
        *,
        intent: CandidateSelectionIntent,
        content_inventory: tuple[CandidateContentEntry, ...],
        sealed_store_receipt: SealedStoreReceipt,
        environment_receipt: EnvironmentContentReceipt,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        selection_commit: CandidateSelectionCommit,
    ) -> "CandidateReceipt":
        value = {
            "schema": _CANDIDATE_SCHEMA,
            "fixed_plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "selection_key": intent.selection_key,
            "candidate_root": intent.candidate_root,
            "inventory": list(_CANDIDATE_INVENTORY),
            "content_inventory": [item.to_mapping() for item in content_inventory],
            "tail_paths": list(_CANDIDATE_TAIL_PATHS),
            "content_aggregate_sha256": _candidate_content_aggregate(
                content_inventory=content_inventory,
                sealed_store_aggregate_sha256=(sealed_store_receipt.aggregate_sha256),
                environment_receipt_sha256=environment_receipt.raw_sha256,
            ),
            "sealed_store_aggregate_sha256": (sealed_store_receipt.aggregate_sha256),
            "environment_receipt_sha256": environment_receipt.raw_sha256,
            "authority_sha256": authority.authority_sha256,
            "installation_sha256": installation.installation_sha256,
            "selection_commit_sha256": selection_commit.raw_sha256,
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CandidateReceipt":
        value = _decode_canonical(raw, label="candidate receipt")
        _exact_keys(
            value,
            frozenset(
                {
                    "schema",
                    "fixed_plan_sha256",
                    "selection_key",
                    "candidate_root",
                    "inventory",
                    "content_inventory",
                    "tail_paths",
                    "content_aggregate_sha256",
                    "sealed_store_aggregate_sha256",
                    "environment_receipt_sha256",
                    "authority_sha256",
                    "installation_sha256",
                    "selection_commit_sha256",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="candidate receipt",
        )
        if value["schema"] != _CANDIDATE_SCHEMA:
            raise WarehouseW3InstallationError("candidate receipt schema differs")
        _false_controls(value, label="candidate receipt")
        if (
            _sha256_text(
                value["fixed_plan_sha256"],
                field="candidate.fixed_plan_sha256",
            )
            != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
        ):
            raise WarehouseW3InstallationError("candidate receipt plan differs")
        raw_inventory = value["inventory"]
        raw_tail = value["tail_paths"]
        if (
            type(raw_inventory) is not list
            or tuple(raw_inventory) != _CANDIDATE_INVENTORY
            or type(raw_tail) is not list
            or tuple(raw_tail) != _CANDIDATE_TAIL_PATHS
        ):
            raise WarehouseW3InstallationError(
                "candidate fixed inventory or tail differs"
            )
        raw_content = value["content_inventory"]
        if type(raw_content) is not list:
            raise WarehouseW3InstallationError("candidate content inventory differs")
        content = tuple(
            CandidateContentEntry.from_mapping(item) for item in raw_content
        )
        if tuple(item.path for item in content) != _CANDIDATE_CONTENT_PATHS:
            raise WarehouseW3InstallationError(
                "candidate content inventory paths differ"
            )
        sealed = _sha256_text(
            value["sealed_store_aggregate_sha256"],
            field="candidate.sealed_store_aggregate_sha256",
        )
        environment = _sha256_text(
            value["environment_receipt_sha256"],
            field="candidate.environment_receipt_sha256",
        )
        aggregate = _sha256_text(
            value["content_aggregate_sha256"],
            field="candidate.content_aggregate_sha256",
        )
        if aggregate != _candidate_content_aggregate(
            content_inventory=content,
            sealed_store_aggregate_sha256=sealed,
            environment_receipt_sha256=environment,
        ):
            raise WarehouseW3InstallationError("candidate content aggregate differs")
        return _new(
            cls,
            {
                "selection_key": _sha256_text(
                    value["selection_key"],
                    field="candidate.selection_key",
                ),
                "candidate_root": _absolute_path(
                    value["candidate_root"],
                    field="candidate.candidate_root",
                ),
                "inventory": _CANDIDATE_INVENTORY,
                "content_inventory": content,
                "tail_paths": _CANDIDATE_TAIL_PATHS,
                "content_aggregate_sha256": aggregate,
                "sealed_store_aggregate_sha256": sealed,
                "environment_receipt_sha256": environment,
                "authority_sha256": _sha256_text(
                    value["authority_sha256"],
                    field="candidate.authority_sha256",
                ),
                "installation_sha256": _sha256_text(
                    value["installation_sha256"],
                    field="candidate.installation_sha256",
                ),
                "selection_commit_sha256": _sha256_text(
                    value["selection_commit_sha256"],
                    field="candidate.selection_commit_sha256",
                ),
                "raw": raw,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
            },
        )  # type: ignore[return-value]


@dataclass(frozen=True, slots=True, init=False)
class CandidateVerificationReceipt:
    selection_key: str
    candidate_root_identity: CandidateRootIdentity
    candidate_receipt_sha256: str
    content_aggregate_sha256: str
    source_receipt_sha256: str
    sealed_store_receipt_sha256: str
    environment_receipt_sha256: str
    authority_sha256: str
    installation_sha256: str
    selection_intent_sha256: str
    selection_commit_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "CandidateVerificationReceipt":
        del cls
        raise TypeError("CandidateVerificationReceipt must be parsed from exact bytes")

    @classmethod
    def create(
        cls,
        *,
        intent: CandidateSelectionIntent,
        selection_commit: CandidateSelectionCommit,
        source_receipt: GitSourceReceipt,
        sealed_store_receipt: SealedStoreReceipt,
        environment_receipt: EnvironmentContentReceipt,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        candidate_receipt: CandidateReceipt,
    ) -> "CandidateVerificationReceipt":
        value = {
            "schema": _CANDIDATE_VERIFICATION_SCHEMA,
            "fixed_plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "selection_key": intent.selection_key,
            "candidate_root_identity": (
                selection_commit.candidate_root_identity.to_mapping()
            ),
            "candidate_receipt_sha256": candidate_receipt.raw_sha256,
            "content_aggregate_sha256": (candidate_receipt.content_aggregate_sha256),
            "source_receipt_sha256": source_receipt.raw_sha256,
            "sealed_store_receipt_sha256": sealed_store_receipt.raw_sha256,
            "environment_receipt_sha256": environment_receipt.raw_sha256,
            "authority_sha256": authority.authority_sha256,
            "installation_sha256": installation.installation_sha256,
            "selection_intent_sha256": intent.raw_sha256,
            "selection_commit_sha256": selection_commit.raw_sha256,
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CandidateVerificationReceipt":
        value = _decode_canonical(raw, label="candidate verification receipt")
        _exact_keys(
            value,
            frozenset(
                {
                    "schema",
                    "fixed_plan_sha256",
                    "selection_key",
                    "candidate_root_identity",
                    "candidate_receipt_sha256",
                    "content_aggregate_sha256",
                    "source_receipt_sha256",
                    "sealed_store_receipt_sha256",
                    "environment_receipt_sha256",
                    "authority_sha256",
                    "installation_sha256",
                    "selection_intent_sha256",
                    "selection_commit_sha256",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="candidate verification receipt",
        )
        if value["schema"] != _CANDIDATE_VERIFICATION_SCHEMA:
            raise WarehouseW3InstallationError("candidate verification schema differs")
        _false_controls(value, label="candidate verification receipt")
        if (
            _sha256_text(
                value["fixed_plan_sha256"],
                field="candidate verification plan",
            )
            != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
        ):
            raise WarehouseW3InstallationError("candidate verification plan differs")
        return _new(
            cls,
            {
                "selection_key": _sha256_text(
                    value["selection_key"],
                    field="candidate verification selection_key",
                ),
                "candidate_root_identity": CandidateRootIdentity.from_mapping(
                    value["candidate_root_identity"]
                ),
                "candidate_receipt_sha256": _sha256_text(
                    value["candidate_receipt_sha256"],
                    field="candidate verification candidate_receipt_sha256",
                ),
                "content_aggregate_sha256": _sha256_text(
                    value["content_aggregate_sha256"],
                    field="candidate verification content_aggregate_sha256",
                ),
                "source_receipt_sha256": _sha256_text(
                    value["source_receipt_sha256"],
                    field="candidate verification source_receipt_sha256",
                ),
                "sealed_store_receipt_sha256": _sha256_text(
                    value["sealed_store_receipt_sha256"],
                    field="candidate verification sealed_store_receipt_sha256",
                ),
                "environment_receipt_sha256": _sha256_text(
                    value["environment_receipt_sha256"],
                    field="candidate verification environment_receipt_sha256",
                ),
                "authority_sha256": _sha256_text(
                    value["authority_sha256"],
                    field="candidate verification authority_sha256",
                ),
                "installation_sha256": _sha256_text(
                    value["installation_sha256"],
                    field="candidate verification installation_sha256",
                ),
                "selection_intent_sha256": _sha256_text(
                    value["selection_intent_sha256"],
                    field="candidate verification selection_intent_sha256",
                ),
                "selection_commit_sha256": _sha256_text(
                    value["selection_commit_sha256"],
                    field="candidate verification selection_commit_sha256",
                ),
                "raw": raw,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
            },
        )  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class _TreeFact:
    path: str
    kind: str
    mode: int
    size_bytes: int
    sha256: str | None


def _read_regular_at(
    directory_fd: int,
    name: str,
    *,
    maximum: int = _MAX_GIT_BLOB_BYTES,
    label: str,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        descriptor = os.open(name, flags, dir_fd=directory_fd)
    except OSError as exc:
        if "descriptor" in locals():
            os.close(descriptor)
        raise WarehouseW3InstallationError(f"cannot open {label}") from exc
    try:
        raw, opened = _read_open_regular(
            descriptor,
            named=named,
            maximum=maximum,
            label=label,
        )
    finally:
        os.close(descriptor)
    try:
        named_after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError as exc:
        raise WarehouseW3InstallationError(f"cannot reopen {label}") from exc
    if _stat_signature(opened) != _stat_signature(named_after):
        raise WarehouseW3InstallationError(f"{label} named identity changed")
    return raw


def _open_relative_parent(
    root_fd: int,
    path: str,
    *,
    label: str,
) -> tuple[int, str]:
    relative = _relative_path(path, field=f"{label}.path")
    parts = PurePosixPath(relative).parts
    descriptor = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child, _identity = _opened_child_directory(
                descriptor,
                part,
                label=f"{label} parent",
            )
            os.close(descriptor)
            descriptor = child
        return descriptor, parts[-1]
    except BaseException:
        os.close(descriptor)
        raise


def _read_relative_regular(
    root_fd: int,
    path: str,
    *,
    maximum: int = _MAX_GIT_BLOB_BYTES,
) -> bytes:
    parent_fd, leaf = _open_relative_parent(root_fd, path, label=path)
    try:
        return _read_regular_at(
            parent_fd,
            leaf,
            maximum=maximum,
            label=path,
        )
    finally:
        os.close(parent_fd)


def _mkdir_relative_no_replace(root_fd: int, path: str) -> None:
    parent_fd, leaf = _open_relative_parent(root_fd, path, label=path)
    try:
        os.mkdir(leaf, 0o755, dir_fd=parent_fd)
        os.fsync(parent_fd)
    except OSError as exc:
        raise WarehouseW3InstallationError(
            f"candidate directory already exists or cannot create: {path}"
        ) from exc
    finally:
        os.close(parent_fd)


def _reserve_relative_file(root_fd: int, path: str, *, mode: int) -> int:
    if mode not in _REGULAR_MODES:
        raise TypeError("reserved regular-file mode differs")
    parent_fd, leaf = _open_relative_parent(root_fd, path, label=path)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(leaf, flags, mode, dir_fd=parent_fd)
        os.fchmod(descriptor, mode)
        os.fsync(parent_fd)
        return descriptor
    except OSError as exc:
        if "descriptor" in locals():
            os.close(descriptor)
        raise WarehouseW3InstallationError(
            f"candidate file already exists or cannot create: {path}"
        ) from exc
    finally:
        os.close(parent_fd)


def _finish_reserved_file(descriptor: int, raw: bytes, *, label: str) -> None:
    if type(raw) is not bytes:
        raise TypeError(f"{label} raw must be exact bytes")
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("zero-length reserved-file write")
            view = view[written:]
        os.fsync(descriptor)
    except OSError as exc:
        raise WarehouseW3InstallationError(f"{label} is a partial hold") from exc
    finally:
        os.close(descriptor)


def _write_relative_no_replace(
    root_fd: int,
    path: str,
    raw: bytes,
    *,
    mode: int,
) -> None:
    descriptor = _reserve_relative_file(root_fd, path, mode=mode)
    _finish_reserved_file(descriptor, raw, label=path)


def _open_relative_directory(root_fd: int, path: str) -> int:
    if path == ".":
        return os.dup(root_fd)
    relative = _relative_path(path, field="directory path")
    descriptor = os.dup(root_fd)
    try:
        for part in PurePosixPath(relative).parts:
            child, _identity = _opened_child_directory(
                descriptor,
                part,
                label=path,
            )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _chmod_directories(
    root_fd: int,
    directories: tuple[str, ...],
) -> None:
    for path in sorted(
        directories,
        key=lambda item: (len(PurePosixPath(item).parts), item.encode("utf-8")),
        reverse=True,
    ):
        descriptor = _open_relative_directory(root_fd, path)
        try:
            os.fchmod(descriptor, _DIRECTORY_MODE)
            os.fsync(descriptor)
        except OSError as exc:
            raise WarehouseW3InstallationError(
                f"cannot freeze candidate directory: {path}"
            ) from exc
        finally:
            os.close(descriptor)


def _scan_tree_at(root_fd: int) -> tuple[_TreeFact, ...]:
    facts: list[_TreeFact] = []

    def walk(directory_fd: int, relative: str) -> None:
        before = os.fstat(directory_fd)
        if not stat.S_ISDIR(before.st_mode):
            raise WarehouseW3InstallationError(
                f"candidate tree directory differs: {relative}"
            )
        facts.append(
            _TreeFact(
                path=relative,
                kind="directory",
                mode=stat.S_IMODE(before.st_mode),
                size_bytes=0,
                sha256=None,
            )
        )
        try:
            names = tuple(sorted(os.listdir(directory_fd), key=os.fsencode))
        except OSError as exc:
            raise WarehouseW3InstallationError(
                f"cannot scan candidate tree: {relative}"
            ) from exc
        for name in names:
            path = name if relative == "." else f"{relative}/{name}"
            _relative_path(path, field="candidate tree path")
            try:
                named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError as exc:
                raise WarehouseW3InstallationError(
                    f"cannot inspect candidate tree entry: {path}"
                ) from exc
            if stat.S_ISDIR(named.st_mode):
                child, opened = _opened_child_directory(
                    directory_fd,
                    name,
                    label=path,
                )
                try:
                    if _stat_signature(named) != _stat_signature(opened):
                        raise WarehouseW3InstallationError(
                            f"candidate directory identity differs: {path}"
                        )
                    walk(child, path)
                finally:
                    os.close(child)
            elif stat.S_ISREG(named.st_mode):
                raw = _read_regular_at(
                    directory_fd,
                    name,
                    label=path,
                )
                facts.append(
                    _TreeFact(
                        path=path,
                        kind="regular",
                        mode=stat.S_IMODE(named.st_mode),
                        size_bytes=len(raw),
                        sha256=hashlib.sha256(raw).hexdigest(),
                    )
                )
            else:
                raise WarehouseW3InstallationError(
                    f"candidate tree contains a symlink or special file: {path}"
                )
        after = os.fstat(directory_fd)
        if _stat_signature(before) != _stat_signature(after):
            raise WarehouseW3InstallationError(
                f"candidate directory changed while scanned: {relative}"
            )

    duplicate = os.dup(root_fd)
    try:
        walk(duplicate, ".")
    finally:
        os.close(duplicate)
    return tuple(sorted(facts, key=lambda item: item.path.encode("utf-8")))


def _materialize_sealed_store(
    store_fd: int,
    *,
    receipt: SealedStoreReceipt,
    objects: tuple[SealedStoreObject, ...],
) -> None:
    directories = tuple(
        item.path
        for item in receipt.inventory
        if item.kind == "directory" and item.path != "."
    )
    for path in sorted(
        directories,
        key=lambda item: (len(PurePosixPath(item).parts), item.encode("utf-8")),
    ):
        _mkdir_relative_no_replace(store_fd, path)
    by_path = {item.adapter.sealed_path: item for item in objects}
    for entry in receipt.inventory:
        if entry.kind != "regular":
            continue
        item = by_path.get(entry.path)
        if item is None:
            raise WarehouseW3InstallationError(
                "sealed-store receipt lacks one byte object"
            )
        _write_relative_no_replace(
            store_fd,
            entry.path,
            item.raw,
            mode=item.mode,
        )
    _chmod_directories(store_fd, tuple([".", *directories]))


def _materialize_environment(
    target_fd: int,
    *,
    source_root: Path,
    receipt: EnvironmentContentReceipt,
) -> None:
    directories = tuple(
        item.path
        for item in receipt.environment_inventory
        if item.kind == "directory" and item.path != "."
    )
    for path in sorted(
        directories,
        key=lambda item: (len(PurePosixPath(item).parts), item.encode("utf-8")),
    ):
        _mkdir_relative_no_replace(target_fd, path)
    for entry in receipt.environment_inventory:
        if entry.kind != "regular":
            continue
        raw, _identity = _read_external_regular(
            source_root / entry.path,
            label=f"built environment {entry.path}",
        )
        if (
            len(raw) != entry.size_bytes
            or hashlib.sha256(raw).hexdigest() != entry.sha256
        ):
            raise WarehouseW3InstallationError(
                f"built environment bytes differ: {entry.path}"
            )
        _write_relative_no_replace(
            target_fd,
            entry.path,
            raw,
            mode=entry.mode,
        )
    _chmod_directories(target_fd, tuple([".", *directories]))


def _verify_sealed_store(
    store_fd: int,
    receipt: SealedStoreReceipt,
) -> None:
    actual = _scan_tree_at(store_fd)
    expected = tuple(
        _TreeFact(
            path=item.path,
            kind=item.kind,
            mode=item.mode,
            size_bytes=item.size_bytes,
            sha256=item.sha256,
        )
        for item in receipt.inventory
    )
    if actual != expected:
        raise WarehouseW3InstallationError(
            "sealed-store live inventory differs from receipt"
        )


def reverify_sealed_store(
    sealed_root: Path,
    receipt: SealedStoreReceipt,
) -> None:
    """Reopen one published sealed store and verify its complete inventory."""

    if not isinstance(sealed_root, Path):
        raise TypeError("sealed_root must be Path")
    if type(receipt) is not SealedStoreReceipt:
        raise TypeError("receipt must be exact SealedStoreReceipt")
    root = Path(_absolute_path(str(sealed_root), field="sealed_root"))
    descriptor, opened = _opened_directory(root, label="sealed root")
    try:
        if (
            stat.S_IMODE(opened.st_mode) != _DIRECTORY_MODE
            or opened.st_uid != 0
            or opened.st_gid != 0
        ):
            raise WarehouseW3InstallationError(
                "published sealed root ownership or mode differs"
            )
        _verify_sealed_store(descriptor, receipt)
    finally:
        os.close(descriptor)


def _candidate_content_inventory(root_fd: int) -> tuple[CandidateContentEntry, ...]:
    facts = {item.path: item for item in _scan_tree_at(root_fd)}
    entries: list[CandidateContentEntry] = []
    for path in _CANDIDATE_CONTENT_PATHS:
        fact = facts.get(path)
        if fact is None:
            raise WarehouseW3InstallationError(
                f"candidate content path is absent: {path}"
            )
        entries.append(
            CandidateContentEntry(
                path=path,
                kind=fact.kind,
                mode=fact.mode,
                size_bytes=fact.size_bytes,
                sha256=fact.sha256,
            )
        )
    return tuple(entries)


def _candidate_fixed_inventory(root_fd: int) -> None:
    expected_root = (
        "authority.json",
        "candidate.v1.json",
        "environment",
        "installation.json",
        "receipts",
        "sealed-store",
        "units",
    )
    if tuple(sorted(os.listdir(root_fd), key=os.fsencode)) != expected_root:
        raise WarehouseW3InstallationError("candidate root inventory differs")
    units_fd = _open_relative_directory(root_fd, "units")
    receipts_fd = _open_relative_directory(root_fd, "receipts")
    try:
        if tuple(sorted(os.listdir(units_fd), key=os.fsencode)) != (
            "scion-w3-close@.service",
            "scion-w3@.service",
        ):
            raise WarehouseW3InstallationError("candidate unit inventory differs")
        if tuple(sorted(os.listdir(receipts_fd), key=os.fsencode)) != (
            "candidate-verification.v1.json",
            "environment.v1.json",
            "sealed-store.v1.json",
            "selection-committed.v1.json",
            "selection-intent.v1.json",
            "source.v1.json",
        ):
            raise WarehouseW3InstallationError("candidate receipt inventory differs")
    finally:
        os.close(receipts_fd)
        os.close(units_fd)


def _adapter_from_sealed_entry(
    entry: SealedStoreInventoryEntry,
    *,
    logical_path: str,
) -> AuthorityInputAdapter:
    if entry.kind != "regular" or entry.provenance is None or entry.sha256 is None:
        raise WarehouseW3InstallationError(
            "authority input is not one sealed regular file"
        )
    return AuthorityInputAdapter(
        logical_path=logical_path,
        sealed_path=entry.path,
        sha256=entry.sha256,
        size_bytes=entry.size_bytes,
        provenance=entry.provenance,
    )


@dataclass(frozen=True, slots=True)
class PreparedCandidate:
    candidate_root: Path
    intent: CandidateSelectionIntent
    selection_commit: CandidateSelectionCommit
    source_receipt: GitSourceReceipt
    sealed_store_receipt: SealedStoreReceipt
    environment_receipt: EnvironmentContentReceipt
    authority: AcceptedLaunchAuthority
    installation: InstallationRecord
    candidate_receipt: CandidateReceipt
    verification_receipt: CandidateVerificationReceipt


def _prepare_inputs(
    *,
    intent: CandidateSelectionIntent,
    source: GitSourceSnapshot,
    sealed_objects: tuple[SealedStoreObject, ...],
    environment_root: Path,
    environment_receipt: EnvironmentContentReceipt,
    external_runtime_paths: tuple[Path, ...],
    run_root: Path,
    nonce: str,
) -> tuple[
    SealedStoreReceipt,
    AcceptedLaunchAuthority,
    InstallationRecord,
    bytes,
    bytes,
]:
    if type(intent) is not CandidateSelectionIntent:
        raise TypeError("intent must be exact CandidateSelectionIntent")
    if type(source) is not GitSourceSnapshot:
        raise TypeError("source must be exact GitSourceSnapshot")
    if (
        source.receipt.source_commit != intent.launch_commit
        or source.receipt.source_tree != intent.launch_tree
    ):
        raise WarehouseW3InstallationError("launch source differs from intent")
    if type(environment_receipt) is not EnvironmentContentReceipt:
        raise TypeError("environment_receipt must be exact EnvironmentContentReceipt")
    if not isinstance(environment_root, Path) or not isinstance(run_root, Path):
        raise TypeError("environment_root and run_root must be Paths")
    paths = derive_candidate_paths(
        Path(intent.experiment_parent),
        intent.selection_key,
    )
    try:
        verify_environment_content(
            environment_root,
            environment_receipt,
            external_runtime_paths=external_runtime_paths,
            candidate_root=paths.candidate_root,
            selection_root=paths.selection_directory,
        )
    except EnvironmentIntegrityError as exc:
        raise WarehouseW3InstallationError(
            "built environment differs from its input receipt"
        ) from exc
    receipt = SealedStoreReceipt.create(sealed_objects)
    adapters = tuple(item.adapter for item in sealed_objects)
    expected_source = tuple(
        AuthorityInputAdapter.from_git_blob(item) for item in source.blobs
    )
    for expected in expected_source:
        if adapters.count(expected) != 1:
            raise WarehouseW3InstallationError(
                "sealed-store source objects differ from Git acquisition"
            )
    manifest_matches = [
        item for item in adapters if item.logical_path == EXPECTED_MANIFEST_NAME
    ]
    native_matches = [
        item for item in adapters if item.logical_path == W3_NATIVE_RECORD_LOGICAL_PATH
    ]
    if len(manifest_matches) != 1 or len(native_matches) != 1:
        raise WarehouseW3InstallationError(
            "sealed store lacks exact manifest or native record"
        )
    excluded = {
        *(item.logical_path for item in expected_source),
        EXPECTED_MANIFEST_NAME,
        W3_NATIVE_RECORD_LOGICAL_PATH,
    }
    extras = tuple(item for item in adapters if item.logical_path not in excluded)
    authority = build_warehouse_launch_authority(
        source,
        manifest_input=manifest_matches[0],
        native_record_input=native_matches[0],
        root_basename=run_root.name,
        nonce=nonce,
        sealed_store_aggregate_sha256=receipt.aggregate_sha256,
        environment_receipt_sha256=environment_receipt.raw_sha256,
        extra_inputs=extras,
    )
    run_raw = _source_fact(source, W3_RUN_TEMPLATE_LOGICAL_PATH).raw
    close_raw = _source_fact(source, W3_CLOSE_TEMPLATE_LOGICAL_PATH).raw
    installation = build_warehouse_installation(
        authority,
        run_root=run_root,
        run_template_raw=run_raw,
        close_template_raw=close_raw,
    )
    return receipt, authority, installation, run_raw, close_raw


def prepare_candidate(
    intent: CandidateSelectionIntent,
    *,
    source: GitSourceSnapshot,
    sealed_objects: tuple[SealedStoreObject, ...],
    environment_root: Path,
    environment_receipt: EnvironmentContentReceipt,
    external_runtime_paths: tuple[Path, ...],
    run_root: Path,
    nonce: str | None = None,
) -> PreparedCandidate:
    """Build one complete immutable non-privileged candidate, no-replace."""

    _require_nonroot()
    nonce_value = (
        os.urandom(32).hex() if nonce is None else _sha256_text(nonce, field="nonce")
    )
    sealed_receipt, authority, installation, run_raw, close_raw = _prepare_inputs(
        intent=intent,
        source=source,
        sealed_objects=sealed_objects,
        environment_root=environment_root,
        environment_receipt=environment_receipt,
        external_runtime_paths=external_runtime_paths,
        run_root=run_root,
        nonce=nonce_value,
    )
    paths = derive_candidate_paths(
        Path(intent.experiment_parent),
        intent.selection_key,
    )
    owner = CandidateSelectionOwner(intent)
    root_fd = -1
    reserved: dict[str, int] = {}
    try:
        owner.publish_intent()
        parent_fd, _parent_identity = _opened_directory(
            paths.experiment_parent,
            label="experiment parent",
        )
        try:
            try:
                os.mkdir(paths.candidate_root.name, 0o755, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except OSError as exc:
                raise WarehouseW3InstallationError(
                    "candidate root already exists or cannot create"
                ) from exc
            root_fd, root_identity = _opened_child_directory(
                parent_fd,
                paths.candidate_root.name,
                label="candidate root",
            )
        finally:
            os.close(parent_fd)
        if (
            root_identity.st_uid != os.geteuid()
            or root_identity.st_gid != os.getegid()
            or os.listdir(root_fd)
        ):
            raise WarehouseW3InstallationError("fresh candidate root identity differs")
        for directory in ("environment", "receipts", "sealed-store", "units"):
            try:
                os.mkdir(directory, 0o755, dir_fd=root_fd)
            except OSError as exc:
                raise WarehouseW3InstallationError(
                    f"candidate directory cannot be created: {directory}"
                ) from exc
        os.fsync(root_fd)

        for path in _CANDIDATE_TAIL_PATHS + ("receipts/selection-committed.v1.json",):
            reserved[path] = _reserve_relative_file(root_fd, path, mode=0o444)

        store_fd = _open_relative_directory(root_fd, "sealed-store")
        environment_fd = _open_relative_directory(root_fd, "environment")
        try:
            _materialize_sealed_store(
                store_fd,
                receipt=sealed_receipt,
                objects=sealed_objects,
            )
            _materialize_environment(
                environment_fd,
                source_root=environment_root,
                receipt=environment_receipt,
            )
        finally:
            os.close(environment_fd)
            os.close(store_fd)

        publications = (
            ("authority.json", authority.raw),
            ("installation.json", installation.raw),
            ("units/scion-w3@.service", run_raw),
            ("units/scion-w3-close@.service", close_raw),
            ("receipts/source.v1.json", source.receipt.raw),
            ("receipts/sealed-store.v1.json", sealed_receipt.raw),
            ("receipts/environment.v1.json", environment_receipt.raw),
            ("receipts/selection-intent.v1.json", intent.raw),
        )
        for path, raw in publications:
            _write_relative_no_replace(root_fd, path, raw, mode=0o444)

        _chmod_directories(root_fd, ("units", "receipts"))
        os.fchmod(root_fd, _DIRECTORY_MODE)
        os.fsync(root_fd)

        selection_commit = owner.commit(
            nonce=nonce_value,
            authority_sha256=authority.authority_sha256,
        )
        _finish_reserved_file(
            reserved.pop("receipts/selection-committed.v1.json"),
            selection_commit.raw,
            label="candidate selection commit copy",
        )
        content_inventory = _candidate_content_inventory(root_fd)
        candidate_receipt = CandidateReceipt.create(
            intent=intent,
            content_inventory=content_inventory,
            sealed_store_receipt=sealed_receipt,
            environment_receipt=environment_receipt,
            authority=authority,
            installation=installation,
            selection_commit=selection_commit,
        )
        _finish_reserved_file(
            reserved.pop("candidate.v1.json"),
            candidate_receipt.raw,
            label="candidate receipt",
        )
        verification = CandidateVerificationReceipt.create(
            intent=intent,
            selection_commit=selection_commit,
            source_receipt=source.receipt,
            sealed_store_receipt=sealed_receipt,
            environment_receipt=environment_receipt,
            authority=authority,
            installation=installation,
            candidate_receipt=candidate_receipt,
        )
        _finish_reserved_file(
            reserved.pop("receipts/candidate-verification.v1.json"),
            verification.raw,
            label="candidate verification receipt",
        )
        os.fsync(root_fd)
    except BaseException:
        owner.close()
        for descriptor in reserved.values():
            os.close(descriptor)
        raise
    finally:
        if root_fd >= 0:
            os.close(root_fd)

    prepared = verify_candidate(
        paths.candidate_root,
        external_runtime_paths=external_runtime_paths,
    )
    if (
        prepared.intent != intent
        or prepared.selection_commit != selection_commit
        or prepared.candidate_receipt != candidate_receipt
        or prepared.verification_receipt != verification
    ):
        raise WarehouseW3InstallationError(
            "durable prepared candidate differs from construction"
        )
    return prepared


def verify_candidate(
    candidate_root: Path,
    *,
    external_runtime_paths: tuple[Path, ...],
) -> PreparedCandidate:
    """Reopen and rehash one complete immutable non-privileged candidate."""

    _require_nonroot()
    if not isinstance(candidate_root, Path):
        raise TypeError("candidate_root must be Path")
    root = Path(_absolute_path(str(candidate_root), field="candidate_root"))
    try:
        if root.resolve(strict=True) != root:
            raise WarehouseW3InstallationError(
                "candidate root is not one direct canonical directory"
            )
    except OSError as exc:
        raise WarehouseW3InstallationError("candidate root cannot be resolved") from exc
    root_fd, root_stat = _opened_directory(root, label="candidate root")
    try:
        if (
            stat.S_IMODE(root_stat.st_mode) != _DIRECTORY_MODE
            or root_stat.st_uid != os.geteuid()
            or root_stat.st_gid != os.getegid()
        ):
            raise WarehouseW3InstallationError(
                "candidate root ownership or mode differs"
            )
        _candidate_fixed_inventory(root_fd)
        candidate_receipt = CandidateReceipt.from_bytes(
            _read_relative_regular(root_fd, "candidate.v1.json")
        )
        intent = CandidateSelectionIntent.from_bytes(
            _read_relative_regular(
                root_fd,
                "receipts/selection-intent.v1.json",
            )
        )
        if (
            candidate_receipt.selection_key != intent.selection_key
            or candidate_receipt.candidate_root != str(root)
            or intent.candidate_root != str(root)
        ):
            raise WarehouseW3InstallationError(
                "candidate header differs from selection intent"
            )
        selection_commit = CandidateSelectionCommit.from_bytes(
            _read_relative_regular(
                root_fd,
                "receipts/selection-committed.v1.json",
            ),
            intent,
        )
        current_identity = CandidateRootIdentity.capture_descriptor(root_fd)
        if current_identity != selection_commit.candidate_root_identity:
            raise WarehouseW3InstallationError(
                "candidate root differs from selection commit"
            )

        source_receipt = GitSourceReceipt.from_bytes(
            _read_relative_regular(root_fd, "receipts/source.v1.json")
        )
        sealed_receipt = SealedStoreReceipt.from_bytes(
            _read_relative_regular(root_fd, "receipts/sealed-store.v1.json")
        )
        try:
            environment_receipt = EnvironmentContentReceipt.from_bytes(
                _read_relative_regular(
                    root_fd,
                    "receipts/environment.v1.json",
                )
            )
        except EnvironmentIntegrityError as exc:
            raise WarehouseW3InstallationError(
                "candidate environment receipt differs"
            ) from exc

        store_fd = _open_relative_directory(root_fd, "sealed-store")
        try:
            _verify_sealed_store(store_fd, sealed_receipt)
            sealed_by_path = {item.path: item for item in sealed_receipt.inventory}
            facts: list[GitBlobFact] = []
            for identity in source_receipt.blobs:
                path = f"sealed/{identity.logical_path}"
                entry = sealed_by_path.get(path)
                if (
                    entry is None
                    or entry.sha256 != identity.sha256
                    or entry.size_bytes != identity.size_bytes
                ):
                    raise WarehouseW3InstallationError(
                        "sealed Git source identity differs"
                    )
                facts.append(
                    GitBlobFact(
                        source_commit=source_receipt.source_commit,
                        source_tree=source_receipt.source_tree,
                        identity=identity,
                        raw=_read_relative_regular(store_fd, path),
                    )
                )
        finally:
            os.close(store_fd)
        source = GitSourceSnapshot(receipt=source_receipt, blobs=tuple(facts))

        environment_path = root / "environment"
        try:
            verify_environment_content(
                environment_path,
                environment_receipt,
                external_runtime_paths=external_runtime_paths,
                candidate_root=root,
                selection_root=Path(intent.selection_directory),
            )
        except EnvironmentIntegrityError as exc:
            raise WarehouseW3InstallationError(
                "candidate environment content differs"
            ) from exc

        try:
            authority = AcceptedLaunchAuthority.from_bytes(
                _read_relative_regular(root_fd, "authority.json")
            )
        except Exception as exc:
            raise WarehouseW3InstallationError("candidate authority differs") from exc
        authority_adapters = tuple(
            AuthorityInputAdapter(
                logical_path=item.logical_path,
                sealed_path=item.sealed_path,
                sha256=item.sha256,
                size_bytes=item.size_bytes,
                provenance=item.provenance,
            )
            for item in authority.inputs
        )
        for adapter in authority_adapters:
            entry = sealed_by_path.get(adapter.sealed_path)
            if (
                entry is None
                or _adapter_from_sealed_entry(
                    entry,
                    logical_path=adapter.logical_path,
                )
                != adapter
            ):
                raise WarehouseW3InstallationError(
                    "authority input differs from sealed-store receipt"
                )
        source_logical = {item.logical_path for item in source.blobs}
        manifest = [
            item
            for item in authority_adapters
            if item.logical_path == EXPECTED_MANIFEST_NAME
        ]
        native = [
            item
            for item in authority_adapters
            if item.logical_path == W3_NATIVE_RECORD_LOGICAL_PATH
        ]
        if len(manifest) != 1 or len(native) != 1:
            raise WarehouseW3InstallationError(
                "authority manifest or native record differs"
            )
        extras = tuple(
            item
            for item in authority_adapters
            if item.logical_path
            not in {
                *source_logical,
                EXPECTED_MANIFEST_NAME,
                W3_NATIVE_RECORD_LOGICAL_PATH,
            }
        )
        rebuilt_authority = build_warehouse_launch_authority(
            source,
            manifest_input=manifest[0],
            native_record_input=native[0],
            root_basename=authority.root_basename,
            nonce=authority.nonce,
            sealed_store_aggregate_sha256=sealed_receipt.aggregate_sha256,
            environment_receipt_sha256=environment_receipt.raw_sha256,
            extra_inputs=extras,
        )
        if rebuilt_authority.raw != authority.raw:
            raise WarehouseW3InstallationError(
                "candidate authority does not exactly rederive"
            )

        try:
            installation = InstallationRecord.from_bytes(
                _read_relative_regular(root_fd, "installation.json"),
                authority,
            )
        except Exception as exc:
            raise WarehouseW3InstallationError(
                "candidate installation differs"
            ) from exc
        run_raw = _read_relative_regular(root_fd, "units/scion-w3@.service")
        close_raw = _read_relative_regular(
            root_fd,
            "units/scion-w3-close@.service",
        )
        rebuilt_installation = build_warehouse_installation(
            authority,
            run_root=Path(installation.run_root),
            run_template_raw=run_raw,
            close_template_raw=close_raw,
        )
        if rebuilt_installation.raw != installation.raw:
            raise WarehouseW3InstallationError(
                "candidate installation does not exactly rederive"
            )

        content = _candidate_content_inventory(root_fd)
        expected_candidate = CandidateReceipt.create(
            intent=intent,
            content_inventory=content,
            sealed_store_receipt=sealed_receipt,
            environment_receipt=environment_receipt,
            authority=authority,
            installation=installation,
            selection_commit=selection_commit,
        )
        if expected_candidate != candidate_receipt:
            raise WarehouseW3InstallationError(
                "candidate receipt does not exactly rederive"
            )
        verification = CandidateVerificationReceipt.from_bytes(
            _read_relative_regular(
                root_fd,
                "receipts/candidate-verification.v1.json",
            )
        )
        expected_verification = CandidateVerificationReceipt.create(
            intent=intent,
            selection_commit=selection_commit,
            source_receipt=source_receipt,
            sealed_store_receipt=sealed_receipt,
            environment_receipt=environment_receipt,
            authority=authority,
            installation=installation,
            candidate_receipt=candidate_receipt,
        )
        if verification != expected_verification:
            raise WarehouseW3InstallationError(
                "candidate verification receipt does not exactly rederive"
            )

        selection_path = Path(intent.selection_directory)
        try:
            if selection_path.resolve(strict=True) != selection_path:
                raise WarehouseW3InstallationError(
                    "selection directory is not one direct canonical directory"
                )
        except OSError as exc:
            raise WarehouseW3InstallationError(
                "selection directory cannot be resolved"
            ) from exc
        selection_fd, selection_stat = _opened_directory(
            selection_path,
            label="selection directory",
        )
        try:
            if (
                stat.S_IMODE(selection_stat.st_mode) != _DIRECTORY_MODE
                or tuple(sorted(os.listdir(selection_fd), key=os.fsencode))
                != ("committed.v1.json", "intent.v1.json")
                or _read_exact_receipt_at(selection_fd, "intent.v1.json") != intent.raw
                or _read_exact_receipt_at(selection_fd, "committed.v1.json")
                != selection_commit.raw
            ):
                raise WarehouseW3InstallationError(
                    "durable selection pair differs from candidate copies"
                )
            selection_after = os.fstat(selection_fd)
            selection_named = os.stat(selection_path, follow_symlinks=False)
            if _stat_signature(selection_stat) != _stat_signature(
                selection_after
            ) or _stat_signature(selection_after) != _stat_signature(selection_named):
                raise WarehouseW3InstallationError(
                    "selection directory changed while verified"
                )
        finally:
            os.close(selection_fd)
        root_after = os.fstat(root_fd)
        root_named = os.stat(root, follow_symlinks=False)
        if _stat_signature(root_stat) != _stat_signature(root_after) or _stat_signature(
            root_after
        ) != _stat_signature(root_named):
            raise WarehouseW3InstallationError("candidate root changed while verified")
    finally:
        os.close(root_fd)
    return PreparedCandidate(
        candidate_root=root,
        intent=intent,
        selection_commit=selection_commit,
        source_receipt=source_receipt,
        sealed_store_receipt=sealed_receipt,
        environment_receipt=environment_receipt,
        authority=authority,
        installation=installation,
        candidate_receipt=candidate_receipt,
        verification_receipt=verification,
    )


__all__ = [
    "ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256",
    "AuthorityInputAdapter",
    "CandidateContentEntry",
    "CandidatePaths",
    "CandidateReceipt",
    "CandidateRootIdentity",
    "CandidateSelectionCommit",
    "CandidateSelectionIntent",
    "CandidateSelectionOwner",
    "CandidateVerificationReceipt",
    "EnvironmentContentReceipt",
    "GitBlobFact",
    "GitBlobIdentity",
    "GitRunner",
    "GitSourceAcquirer",
    "GitSourceReceipt",
    "GitSourceSnapshot",
    "PreparedCandidate",
    "SealedStoreInventoryEntry",
    "SealedStoreObject",
    "SealedStoreReceipt",
    "SubprocessGitRunner",
    "W3_CLOSE_TEMPLATE_LOGICAL_PATH",
    "W3_COMPOSITION_LOGICAL_PATH",
    "W3_NATIVE_RECORD_LOGICAL_PATH",
    "W3_RUN_TEMPLATE_LOGICAL_PATH",
    "W3_TOOL_LOGICAL_PATH",
    "WarehouseW3InstallationError",
    "build_warehouse_installation",
    "build_warehouse_launch_authority",
    "derive_candidate_paths",
    "derive_launch_id",
    "derive_selection_key",
    "prepare_candidate",
    "reverify_sealed_store",
    "verify_candidate",
]
