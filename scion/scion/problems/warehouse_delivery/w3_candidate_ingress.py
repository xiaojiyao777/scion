"""Fixed non-privileged ingress for one closed Warehouse W3 candidate gate.

The immutable candidate cannot contain its final gate: closing that gate
reopens and verifies the already frozen candidate.  This module publishes the
gate beside, rather than inside, the candidate under one mechanically derived
selection-key path.  Root application therefore needs only the candidate root;
it never accepts an injected gate or receipt path.

This owner has no root, mount, manager, nonce, or launch capability.  A
publication failure is a permanent preparation hold.  It never removes,
replaces, repairs, resumes, or reuses a gate ingress.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath

from scion.problems.warehouse_delivery.w3_candidate_gate import (
    CandidateGateClosureBundle,
    CandidateGateReceipt,
)
from scion.problems.warehouse_delivery.w3_installation import (
    CandidateRootIdentity,
    derive_candidate_paths,
)
from scion.runtime.execution.external_linux import (
    FileIdentity,
    PinnedDirectory,
    pin_absolute_directory,
)

_SELECTION_KEY_RE = re.compile(r"[0-9a-f]{64}\Z")
_CANDIDATE_PREFIX = "v04-w3-launch-"
_CANDIDATE_SUFFIX = "-claw"
_INGRESS_PARENT = ".scion-w3-candidate-gates"
_INGRESS_INTENT_LEAF = "intent.v1.json"
_INGRESS_LEAF = "candidate-gate.v2.json"
_INGRESS_CLOSURE_LEAF = "candidate-gate-closure.v1.json"
_INGRESS_INVENTORY = tuple(
    sorted(
        (_INGRESS_CLOSURE_LEAF, _INGRESS_LEAF, _INGRESS_INTENT_LEAF),
        key=os.fsencode,
    )
)
_MAX_GATE_BYTES = 4 * 1024 * 1024
_MAX_CLOSURE_BYTES = 32 * 1024 * 1024
_MAX_INTENT_BYTES = 64 * 1024


class WarehouseW3CandidateIngressError(RuntimeError):
    """A fixed candidate-gate ingress is absent, invalid, or already spent."""


class WarehouseW3CandidateIngressHold(WarehouseW3CandidateIngressError):
    """A gate ingress mutation began but did not close durably."""


class WarehouseW3CandidateIngressAlreadyPublished(WarehouseW3CandidateIngressError):
    """The fixed ingress is already complete and cannot be reused."""


class CandidateGateIngressState(str, Enum):
    ABSENT = "ABSENT"
    PARTIAL_HOLD = "PARTIAL_HOLD"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class CandidateGateIngressPaths:
    """The only candidate-gate ingress paths for one selection key."""

    experiment_parent: Path
    ingress_parent: Path
    ingress_directory: Path
    gate_path: Path
    closure_path: Path


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
        raise WarehouseW3CandidateIngressError(
            "candidate gate ingress value is not canonical JSON"
        ) from exc


def _decode_canonical(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError(f"{label} must be exact bytes")

    def mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"{label} contains a duplicate field")
            value[key] = item
        return value

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
        raise WarehouseW3CandidateIngressError(
            f"{label} is not canonical JSON"
        ) from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3CandidateIngressError(f"{label} bytes are not canonical")
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
        raise WarehouseW3CandidateIngressError(f"{label} fields differ")
    return value


def _absolute_path(value: object, *, field: str) -> Path:
    if type(value) is not str or not value:
        raise WarehouseW3CandidateIngressError(f"{field} is not exact text")
    parsed = PurePosixPath(value)
    if (
        not parsed.is_absolute()
        or value == "/"
        or value.startswith("//")
        or parsed.as_posix() != value
        or any(part in {"", ".", ".."} for part in parsed.parts[1:])
    ):
        raise WarehouseW3CandidateIngressError(
            f"{field} is not a canonical absolute path"
        )
    return Path(value)


def _selection_key(value: object) -> str:
    if type(value) is not str or _SELECTION_KEY_RE.fullmatch(value) is None:
        raise WarehouseW3CandidateIngressError("selection_key is not canonical SHA-256")
    return value


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SELECTION_KEY_RE.fullmatch(value) is None:
        raise WarehouseW3CandidateIngressError(f"{field} is not canonical SHA-256")
    return value


def _candidate_key(candidate_root: Path) -> str:
    if not isinstance(candidate_root, Path):
        raise TypeError("candidate_root must be Path")
    root = _absolute_path(str(candidate_root), field="candidate_root")
    name = root.name
    if not name.startswith(_CANDIDATE_PREFIX) or not name.endswith(_CANDIDATE_SUFFIX):
        raise WarehouseW3CandidateIngressError(
            "candidate root basename is not mechanically derived"
        )
    key = _selection_key(name[len(_CANDIDATE_PREFIX) : -len(_CANDIDATE_SUFFIX)])
    if derive_candidate_paths(root.parent, key).candidate_root != root:
        raise WarehouseW3CandidateIngressError(
            "candidate root path is not mechanically derived"
        )
    return key


def derive_candidate_gate_ingress_paths(
    candidate_root: Path,
    selection_key: str,
) -> CandidateGateIngressPaths:
    """Derive the sole sidecar location without resolving a user-owned path."""

    key = _selection_key(selection_key)
    root = _absolute_path(str(candidate_root), field="candidate_root")
    if _candidate_key(root) != key:
        raise WarehouseW3CandidateIngressError(
            "candidate root and selection key differ"
        )
    ingress_parent = root.parent / _INGRESS_PARENT
    ingress_directory = ingress_parent / key
    return CandidateGateIngressPaths(
        experiment_parent=root.parent,
        ingress_parent=ingress_parent,
        ingress_directory=ingress_directory,
        gate_path=ingress_directory / _INGRESS_LEAF,
        closure_path=ingress_directory / _INGRESS_CLOSURE_LEAF,
    )


@dataclass(frozen=True, slots=True, init=False)
class CandidateGateIngressIntent:
    selection_key: str
    candidate_root: str
    gate_sha256: str
    closure_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "CandidateGateIngressIntent":
        del cls
        raise TypeError("CandidateGateIngressIntent must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("CandidateGateIngressIntent is final")

    @classmethod
    def create(
        cls,
        *,
        candidate_root: Path,
        selection_key: str,
        gate_sha256: str,
        closure_sha256: str,
    ) -> "CandidateGateIngressIntent":
        paths = derive_candidate_gate_ingress_paths(
            candidate_root,
            selection_key,
        )
        value = {
            "schema": "scion.w3-candidate-gate-ingress-intent.v1",
            "selection_key": _selection_key(selection_key),
            "candidate_root": str(
                _absolute_path(str(candidate_root), field="candidate_root")
            ),
            "ingress_path": str(paths.gate_path),
            "closure_path": str(paths.closure_path),
            "gate_sha256": _sha256(
                gate_sha256,
                field="gate_sha256",
            ),
            "closure_sha256": _sha256(
                closure_sha256,
                field="closure_sha256",
            ),
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CandidateGateIngressIntent":
        value = _exact_fields(
            _decode_canonical(raw, label="candidate gate ingress intent"),
            frozenset(
                {
                    "schema",
                    "selection_key",
                    "candidate_root",
                    "ingress_path",
                    "closure_path",
                    "gate_sha256",
                    "closure_sha256",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="candidate gate ingress intent",
        )
        if value["schema"] != "scion.w3-candidate-gate-ingress-intent.v1" or any(
            value[name] is not False for name in ("retry", "resume", "reuse")
        ):
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress intent state differs"
            )
        key = _selection_key(value["selection_key"])
        root = _absolute_path(value["candidate_root"], field="candidate_root")
        paths = derive_candidate_gate_ingress_paths(root, key)
        if value["ingress_path"] != str(paths.gate_path):
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress intent path differs"
            )
        if value["closure_path"] != str(paths.closure_path):
            raise WarehouseW3CandidateIngressError(
                "candidate gate closure ingress intent path differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("selection_key", key),
            ("candidate_root", str(root)),
            ("gate_sha256", _sha256(value["gate_sha256"], field="gate_sha256")),
            (
                "closure_sha256",
                _sha256(value["closure_sha256"], field="closure_sha256"),
            ),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True, init=False)
class CandidateGateIngressFact:
    selection_key: str
    candidate_root: str
    ingress_directory: str
    experiment_parent_identity: FileIdentity
    ingress_parent_identity: FileIdentity
    candidate_identity: FileIdentity
    ingress_identity: FileIdentity
    intent_identity: FileIdentity
    gate_identity: FileIdentity
    closure_identity: FileIdentity
    intent_sha256: str
    gate_sha256: str
    gate_receipt_sha256: str
    closure_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "CandidateGateIngressFact":
        del cls
        raise TypeError("CandidateGateIngressFact must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("CandidateGateIngressFact is final")

    @classmethod
    def create(
        cls,
        *,
        candidate_root: Path,
        selection_key: str,
        experiment_parent_identity: FileIdentity,
        ingress_parent_identity: FileIdentity,
        candidate_identity: FileIdentity,
        ingress_identity: FileIdentity,
        intent_identity: FileIdentity,
        gate_identity: FileIdentity,
        closure_identity: FileIdentity,
        intent_sha256: str,
        gate_sha256: str,
        gate_receipt_sha256: str,
        closure_sha256: str,
    ) -> "CandidateGateIngressFact":
        paths = derive_candidate_gate_ingress_paths(candidate_root, selection_key)
        identities = (
            experiment_parent_identity,
            ingress_parent_identity,
            candidate_identity,
            ingress_identity,
            intent_identity,
            gate_identity,
            closure_identity,
        )
        if any(type(item) is not FileIdentity for item in identities):
            raise TypeError("candidate gate ingress identities must be exact")
        if (
            not stat.S_ISDIR(candidate_identity.mode)
            or stat.S_IMODE(candidate_identity.mode) != 0o555
            or not stat.S_ISDIR(experiment_parent_identity.mode)
            or not stat.S_ISDIR(ingress_parent_identity.mode)
            or stat.S_IMODE(ingress_parent_identity.mode) != 0o755
            or not stat.S_ISDIR(ingress_identity.mode)
            or stat.S_IMODE(ingress_identity.mode) != 0o555
            or any(
                not stat.S_ISREG(item.mode)
                or stat.S_IMODE(item.mode) != 0o444
                or item.link_count != 1
                for item in (intent_identity, gate_identity, closure_identity)
            )
            or len({item.uid for item in identities}) != 1
            or len({item.gid for item in identities}) != 1
        ):
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress fact identity differs"
            )
        value = {
            "schema": "scion.w3-candidate-gate-ingress-fact.v1",
            "selection_key": _selection_key(selection_key),
            "candidate_root": str(candidate_root),
            "ingress_directory": str(paths.ingress_directory),
            "experiment_parent_identity": experiment_parent_identity.to_mapping(),
            "ingress_parent_identity": ingress_parent_identity.to_mapping(),
            "candidate_identity": candidate_identity.to_mapping(),
            "ingress_identity": ingress_identity.to_mapping(),
            "intent_identity": intent_identity.to_mapping(),
            "gate_identity": gate_identity.to_mapping(),
            "closure_identity": closure_identity.to_mapping(),
            "intent_sha256": _sha256(
                intent_sha256,
                field="intent_sha256",
            ),
            "gate_sha256": _sha256(gate_sha256, field="gate_sha256"),
            "gate_receipt_sha256": _sha256(
                gate_receipt_sha256,
                field="gate_receipt_sha256",
            ),
            "closure_sha256": _sha256(
                closure_sha256,
                field="closure_sha256",
            ),
        }
        if value["gate_sha256"] != value["gate_receipt_sha256"]:
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress fact gate hashes differ"
            )
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CandidateGateIngressFact":
        value = _exact_fields(
            _decode_canonical(raw, label="candidate gate ingress fact"),
            frozenset(
                {
                    "schema",
                    "selection_key",
                    "candidate_root",
                    "ingress_directory",
                    "experiment_parent_identity",
                    "ingress_parent_identity",
                    "candidate_identity",
                    "ingress_identity",
                    "intent_identity",
                    "gate_identity",
                    "closure_identity",
                    "intent_sha256",
                    "gate_sha256",
                    "gate_receipt_sha256",
                    "closure_sha256",
                }
            ),
            label="candidate gate ingress fact",
        )
        if value["schema"] != "scion.w3-candidate-gate-ingress-fact.v1":
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress fact schema differs"
            )
        key = _selection_key(value["selection_key"])
        root = _absolute_path(value["candidate_root"], field="candidate_root")
        paths = derive_candidate_gate_ingress_paths(root, key)
        if value["ingress_directory"] != str(paths.ingress_directory):
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress fact path differs"
            )
        experiment_parent = FileIdentity.from_mapping(
            value["experiment_parent_identity"],
            label="candidate ingress experiment parent identity",
        )
        ingress_parent = FileIdentity.from_mapping(
            value["ingress_parent_identity"],
            label="candidate ingress parent identity",
        )
        candidate = FileIdentity.from_mapping(
            value["candidate_identity"],
            label="candidate ingress source identity",
        )
        ingress = FileIdentity.from_mapping(
            value["ingress_identity"],
            label="candidate ingress directory identity",
        )
        intent = FileIdentity.from_mapping(
            value["intent_identity"],
            label="candidate ingress intent identity",
        )
        gate = FileIdentity.from_mapping(
            value["gate_identity"],
            label="candidate ingress gate identity",
        )
        closure = FileIdentity.from_mapping(
            value["closure_identity"],
            label="candidate ingress closure identity",
        )
        intent_sha = _sha256(value["intent_sha256"], field="intent_sha256")
        gate_sha = _sha256(value["gate_sha256"], field="gate_sha256")
        receipt_sha = _sha256(
            value["gate_receipt_sha256"],
            field="gate_receipt_sha256",
        )
        closure_sha = _sha256(
            value["closure_sha256"],
            field="closure_sha256",
        )
        if gate_sha != receipt_sha:
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress fact gate hashes differ"
            )
        identities = (
            experiment_parent,
            ingress_parent,
            candidate,
            ingress,
            intent,
            gate,
            closure,
        )
        if (
            not stat.S_ISDIR(experiment_parent.mode)
            or not stat.S_ISDIR(ingress_parent.mode)
            or stat.S_IMODE(ingress_parent.mode) != 0o755
            or not stat.S_ISDIR(candidate.mode)
            or stat.S_IMODE(candidate.mode) != 0o555
            or not stat.S_ISDIR(ingress.mode)
            or stat.S_IMODE(ingress.mode) != 0o555
            or any(
                not stat.S_ISREG(item.mode)
                or stat.S_IMODE(item.mode) != 0o444
                or item.link_count != 1
                for item in (intent, gate, closure)
            )
            or len({item.uid for item in identities}) != 1
            or len({item.gid for item in identities}) != 1
        ):
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress fact identity differs"
            )
        expected = {
            "schema": "scion.w3-candidate-gate-ingress-fact.v1",
            "selection_key": key,
            "candidate_root": str(root),
            "ingress_directory": str(paths.ingress_directory),
            "experiment_parent_identity": experiment_parent.to_mapping(),
            "ingress_parent_identity": ingress_parent.to_mapping(),
            "candidate_identity": candidate.to_mapping(),
            "ingress_identity": ingress.to_mapping(),
            "intent_identity": intent.to_mapping(),
            "gate_identity": gate.to_mapping(),
            "closure_identity": closure.to_mapping(),
            "intent_sha256": intent_sha,
            "gate_sha256": gate_sha,
            "gate_receipt_sha256": receipt_sha,
            "closure_sha256": closure_sha,
        }
        if _canonical_json(expected) != raw:
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress fact semantic bytes differ"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("selection_key", key),
            ("candidate_root", str(root)),
            ("ingress_directory", str(paths.ingress_directory)),
            ("experiment_parent_identity", experiment_parent),
            ("ingress_parent_identity", ingress_parent),
            ("candidate_identity", candidate),
            ("ingress_identity", ingress),
            ("intent_identity", intent),
            ("gate_identity", gate),
            ("closure_identity", closure),
            ("intent_sha256", intent_sha),
            ("gate_sha256", gate_sha),
            ("gate_receipt_sha256", receipt_sha),
            ("closure_sha256", closure_sha),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


def _identity_from_fd(descriptor: int) -> CandidateRootIdentity:
    return CandidateRootIdentity.from_stat_result(os.fstat(descriptor))


def _identity_tuple(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _open_directory_at(parent_fd: int, leaf: str) -> int:
    return os.open(
        leaf,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=parent_fd,
    )


def _require_directory(
    descriptor: int,
    *,
    parent_fd: int,
    leaf: str,
    mode: int,
    uid: int,
    gid: int,
    label: str,
) -> os.stat_result:
    opened = os.fstat(descriptor)
    named = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
    if (
        _identity_tuple(opened) != _identity_tuple(named)
        or not stat.S_ISDIR(opened.st_mode)
        or stat.S_IMODE(opened.st_mode) != mode
        or opened.st_uid != uid
        or opened.st_gid != gid
    ):
        raise WarehouseW3CandidateIngressError(f"{label} identity differs")
    return opened


def _read_regular_at(
    directory_fd: int,
    *,
    leaf: str,
    maximum: int,
    label: str,
    expected_uid: int,
    expected_gid: int,
) -> bytes:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(leaf, flags, dir_fd=directory_fd)
    chunks: list[bytes] = []
    total = 0
    try:
        before = os.fstat(descriptor)
        named_before = os.stat(
            leaf,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if (
            _identity_tuple(before) != _identity_tuple(named_before)
            or not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o444
            or before.st_uid != expected_uid
            or before.st_gid != expected_gid
            or before.st_nlink != 1
            or before.st_size < 1
            or before.st_size > maximum
        ):
            raise WarehouseW3CandidateIngressError(
                f"candidate gate ingress {label} file identity differs"
            )
        while True:
            remaining = maximum + 1 - total
            if remaining <= 0:
                raise WarehouseW3CandidateIngressError(
                    f"candidate gate ingress {label} exceeds its bound"
                )
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
        named_after = os.stat(
            leaf,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if (
            _identity_tuple(before) != _identity_tuple(after)
            or _identity_tuple(after) != _identity_tuple(named_after)
            or total != after.st_size
        ):
            raise WarehouseW3CandidateIngressError(
                f"candidate gate ingress {label} changed while reopened"
            )
        return b"".join(chunks)
    finally:
        os.close(descriptor)


class _PinnedRegular:
    __slots__ = (
        "_descriptor",
        "_directory",
        "_identity",
        "_leaf",
        "_maximum",
        "_raw",
        "_signature",
    )

    def __init__(
        self,
        directory: PinnedDirectory,
        *,
        leaf: str,
        maximum: int,
        expected_uid: int,
        expected_gid: int,
    ) -> None:
        if type(directory) is not PinnedDirectory:
            raise TypeError("pinned regular directory must be exact PinnedDirectory")
        if type(maximum) is not int or maximum < 1:
            raise TypeError("pinned regular maximum must be positive")
        directory.revalidate()
        descriptor = os.open(
            leaf,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=directory.fd,
        )
        self._descriptor = descriptor
        self._directory = directory
        self._leaf = leaf
        self._maximum = maximum
        try:
            raw, metadata = self._read_current()
            named = os.stat(
                leaf,
                dir_fd=directory.fd,
                follow_symlinks=False,
            )
            if (
                _identity_tuple(metadata) != _identity_tuple(named)
                or not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o444
                or metadata.st_uid != expected_uid
                or metadata.st_gid != expected_gid
                or metadata.st_nlink != 1
            ):
                raise WarehouseW3CandidateIngressError(
                    f"candidate gate ingress {leaf} identity differs"
                )
            self._identity = FileIdentity.from_stat(metadata)
            self._raw = raw
            self._signature = _identity_tuple(metadata)
        except Exception:
            os.close(descriptor)
            self._descriptor = -1
            raise

    def _read_current(self) -> tuple[bytes, os.stat_result]:
        os.lseek(self._descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        total = 0
        before = os.fstat(self._descriptor)
        while True:
            remaining = self._maximum + 1 - total
            if remaining <= 0:
                raise WarehouseW3CandidateIngressError(
                    f"candidate gate ingress {self._leaf} exceeds its bound"
                )
            chunk = os.read(self._descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(self._descriptor)
        if (
            _identity_tuple(before) != _identity_tuple(after)
            or total != after.st_size
            or total < 1
        ):
            raise WarehouseW3CandidateIngressError(
                f"candidate gate ingress {self._leaf} changed while read"
            )
        return b"".join(chunks), after

    @property
    def raw(self) -> bytes:
        return self._raw

    @property
    def identity(self) -> FileIdentity:
        return self._identity

    def revalidate(self) -> None:
        if self._descriptor < 0:
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress regular is closed"
            )
        self._directory.revalidate()
        raw, metadata = self._read_current()
        named = os.stat(
            self._leaf,
            dir_fd=self._directory.fd,
            follow_symlinks=False,
        )
        if (
            _identity_tuple(metadata) != self._signature
            or _identity_tuple(named) != self._signature
            or raw != self._raw
            or FileIdentity.from_stat(metadata) != self._identity
        ):
            raise WarehouseW3CandidateIngressError(
                f"candidate gate ingress {self._leaf} drifted"
            )

    def close(self) -> None:
        if self._descriptor >= 0:
            os.close(self._descriptor)
            self._descriptor = -1


class PinnedCandidateGateIngress:
    """Retain candidate, ingress, gate, and closure FDs through root import."""

    __slots__ = (
        "_candidate",
        "_closed",
        "_closure",
        "_closure_file",
        "_fact",
        "_gate",
        "_gate_file",
        "_ingress_directory",
        "_ingress_parent",
        "_intent",
        "_intent_file",
        "_parent",
    )

    def __new__(cls) -> "PinnedCandidateGateIngress":
        del cls
        raise TypeError("PinnedCandidateGateIngress must be opened")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("PinnedCandidateGateIngress is final")

    @classmethod
    def open(cls, candidate_root: Path) -> "PinnedCandidateGateIngress":
        key = _candidate_key(candidate_root)
        root = _absolute_path(str(candidate_root), field="candidate_root")
        paths = derive_candidate_gate_ingress_paths(root, key)
        parent = pin_absolute_directory(str(paths.experiment_parent))
        candidate: PinnedDirectory | None = None
        ingress_parent: PinnedDirectory | None = None
        ingress_directory: PinnedDirectory | None = None
        intent_file: _PinnedRegular | None = None
        gate_file: _PinnedRegular | None = None
        closure_file: _PinnedRegular | None = None
        try:
            candidate = parent.open_child_directory(root.name)
            candidate_identity = FileIdentity.from_stat(os.fstat(candidate.fd))
            ingress_parent = parent.open_child_directory(_INGRESS_PARENT)
            ingress_parent_identity = FileIdentity.from_stat(
                os.fstat(ingress_parent.fd)
            )
            ingress_directory = ingress_parent.open_child_directory(key)
            ingress_identity = FileIdentity.from_stat(os.fstat(ingress_directory.fd))
            if (
                not stat.S_ISDIR(candidate_identity.mode)
                or stat.S_IMODE(candidate_identity.mode) != 0o555
                or not stat.S_ISDIR(ingress_parent_identity.mode)
                or stat.S_IMODE(ingress_parent_identity.mode) != 0o755
                or not stat.S_ISDIR(ingress_identity.mode)
                or stat.S_IMODE(ingress_identity.mode) != 0o555
                or len(
                    {
                        candidate_identity.uid,
                        ingress_parent_identity.uid,
                        ingress_identity.uid,
                    }
                )
                != 1
                or len(
                    {
                        candidate_identity.gid,
                        ingress_parent_identity.gid,
                        ingress_identity.gid,
                    }
                )
                != 1
            ):
                raise WarehouseW3CandidateIngressError(
                    "candidate gate ingress directory ownership differs"
                )
            if tuple(sorted(os.listdir(ingress_directory.fd), key=os.fsencode)) != (
                _INGRESS_INVENTORY
            ):
                raise WarehouseW3CandidateIngressError(
                    "candidate gate ingress inventory differs"
                )
            intent_file = _PinnedRegular(
                ingress_directory,
                leaf=_INGRESS_INTENT_LEAF,
                maximum=_MAX_INTENT_BYTES,
                expected_uid=candidate_identity.uid,
                expected_gid=candidate_identity.gid,
            )
            gate_file = _PinnedRegular(
                ingress_directory,
                leaf=_INGRESS_LEAF,
                maximum=_MAX_GATE_BYTES,
                expected_uid=candidate_identity.uid,
                expected_gid=candidate_identity.gid,
            )
            closure_file = _PinnedRegular(
                ingress_directory,
                leaf=_INGRESS_CLOSURE_LEAF,
                maximum=_MAX_CLOSURE_BYTES,
                expected_uid=candidate_identity.uid,
                expected_gid=candidate_identity.gid,
            )
            intent = CandidateGateIngressIntent.from_bytes(intent_file.raw)
            gate = CandidateGateReceipt.from_bytes(gate_file.raw)
            closure = CandidateGateClosureBundle.from_bytes(closure_file.raw)
            candidate_root_identity = CandidateRootIdentity.from_stat_result(
                os.fstat(candidate.fd)
            )
            _require_gate_binding(
                gate,
                candidate_root=root,
                candidate_identity=candidate_root_identity,
                selection_key=key,
            )
            if (
                intent.selection_key != key
                or intent.candidate_root != str(root)
                or intent.gate_sha256 != gate.raw_sha256
                or intent.closure_sha256 != closure.raw_sha256
                or closure.gate != gate
                or hashlib.sha256(gate_file.raw).hexdigest() != gate.raw_sha256
                or hashlib.sha256(closure_file.raw).hexdigest() != closure.raw_sha256
            ):
                raise WarehouseW3CandidateIngressError(
                    "candidate gate ingress intent differs from committed gate"
                )
            fact = CandidateGateIngressFact.create(
                candidate_root=root,
                selection_key=key,
                experiment_parent_identity=FileIdentity.from_stat(os.fstat(parent.fd)),
                ingress_parent_identity=ingress_parent_identity,
                candidate_identity=candidate_identity,
                ingress_identity=ingress_identity,
                intent_identity=intent_file.identity,
                gate_identity=gate_file.identity,
                closure_identity=closure_file.identity,
                intent_sha256=intent.raw_sha256,
                gate_sha256=hashlib.sha256(gate_file.raw).hexdigest(),
                gate_receipt_sha256=gate.raw_sha256,
                closure_sha256=hashlib.sha256(closure_file.raw).hexdigest(),
            )
            instance = object.__new__(cls)
            instance._candidate = candidate
            instance._closed = False
            instance._closure = closure
            instance._closure_file = closure_file
            instance._fact = fact
            instance._gate = gate
            instance._gate_file = gate_file
            instance._ingress_directory = ingress_directory
            instance._ingress_parent = ingress_parent
            instance._intent = intent
            instance._intent_file = intent_file
            instance._parent = parent
            instance.revalidate()
            return instance
        except Exception:
            if closure_file is not None:
                closure_file.close()
            if gate_file is not None:
                gate_file.close()
            if intent_file is not None:
                intent_file.close()
            for directory in (
                ingress_directory,
                ingress_parent,
                candidate,
                parent,
            ):
                if directory is not None:
                    try:
                        directory.close()
                    except OSError:
                        pass
            raise

    @property
    def candidate(self) -> PinnedDirectory:
        self._require_open()
        return self._candidate

    @property
    def gate(self) -> CandidateGateReceipt:
        self._require_open()
        return self._gate

    @property
    def closure(self) -> CandidateGateClosureBundle:
        self._require_open()
        return self._closure

    @property
    def intent(self) -> CandidateGateIngressIntent:
        self._require_open()
        return self._intent

    @property
    def fact(self) -> CandidateGateIngressFact:
        self._require_open()
        return self._fact

    def _require_open(self) -> None:
        if self._closed:
            raise WarehouseW3CandidateIngressError("candidate gate ingress is closed")

    def revalidate(self) -> None:
        try:
            self._revalidate_exact()
        except WarehouseW3CandidateIngressError:
            raise
        except Exception as exc:
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress retained identity drifted"
            ) from exc

    def _revalidate_exact(self) -> None:
        self._require_open()
        for directory in (
            self._parent,
            self._candidate,
            self._ingress_parent,
            self._ingress_directory,
        ):
            directory.revalidate()
        if tuple(sorted(os.listdir(self._ingress_directory.fd), key=os.fsencode)) != (
            _INGRESS_INVENTORY
        ):
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress inventory drifted"
            )
        self._intent_file.revalidate()
        self._gate_file.revalidate()
        self._closure_file.revalidate()
        if (
            CandidateGateIngressIntent.from_bytes(self._intent_file.raw) != self._intent
            or CandidateGateReceipt.from_bytes(self._gate_file.raw) != self._gate
            or CandidateGateClosureBundle.from_bytes(self._closure_file.raw)
            != self._closure
            or self._closure.gate != self._gate
        ):
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress object drifted"
            )
        current_fact = CandidateGateIngressFact.create(
            candidate_root=Path(self._fact.candidate_root),
            selection_key=self._fact.selection_key,
            experiment_parent_identity=FileIdentity.from_stat(
                os.fstat(self._parent.fd)
            ),
            ingress_parent_identity=FileIdentity.from_stat(
                os.fstat(self._ingress_parent.fd)
            ),
            candidate_identity=FileIdentity.from_stat(os.fstat(self._candidate.fd)),
            ingress_identity=FileIdentity.from_stat(
                os.fstat(self._ingress_directory.fd)
            ),
            intent_identity=self._intent_file.identity,
            gate_identity=self._gate_file.identity,
            closure_identity=self._closure_file.identity,
            intent_sha256=self._intent.raw_sha256,
            gate_sha256=hashlib.sha256(self._gate_file.raw).hexdigest(),
            gate_receipt_sha256=self._gate.raw_sha256,
            closure_sha256=hashlib.sha256(self._closure_file.raw).hexdigest(),
        )
        if current_fact != self._fact:
            raise WarehouseW3CandidateIngressError(
                "candidate gate ingress fact drifted"
            )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._closure_file.close()
        self._gate_file.close()
        self._intent_file.close()
        first_error: OSError | None = None
        for directory in (
            self._ingress_directory,
            self._ingress_parent,
            self._candidate,
            self._parent,
        ):
            try:
                directory.close()
            except OSError as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    def __enter__(self) -> "PinnedCandidateGateIngress":
        self.revalidate()
        return self

    def __exit__(self, *args: object) -> None:
        del args
        self.close()


def _write_regular_noreplace(
    directory_fd: int,
    *,
    leaf: str,
    raw: bytes,
) -> None:
    descriptor = os.open(
        leaf,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
        dir_fd=directory_fd,
    )
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("candidate gate ingress write made no progress")
            view = view[written:]
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory_fd)


def classify_candidate_gate_ingress(
    candidate_root: Path,
) -> CandidateGateIngressState:
    """Classify one fixed ingress without authorizing repair or publication."""

    key = _candidate_key(candidate_root)
    root = _absolute_path(str(candidate_root), field="candidate_root")
    paths = derive_candidate_gate_ingress_paths(root, key)
    try:
        with pin_absolute_directory(str(paths.experiment_parent)) as parent:
            try:
                ingress_parent = parent.open_child_directory(_INGRESS_PARENT)
            except FileNotFoundError:
                return CandidateGateIngressState.ABSENT
            except OSError:
                return CandidateGateIngressState.PARTIAL_HOLD
            try:
                parent_identity = FileIdentity.from_stat(os.fstat(ingress_parent.fd))
                candidate_identity = FileIdentity.from_stat(
                    os.stat(
                        root.name,
                        dir_fd=parent.fd,
                        follow_symlinks=False,
                    )
                )
                if (
                    not stat.S_ISDIR(parent_identity.mode)
                    or stat.S_IMODE(parent_identity.mode) != 0o755
                    or parent_identity.uid != candidate_identity.uid
                    or parent_identity.gid != candidate_identity.gid
                ):
                    return CandidateGateIngressState.PARTIAL_HOLD
                try:
                    os.stat(
                        key,
                        dir_fd=ingress_parent.fd,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    return CandidateGateIngressState.ABSENT
                except OSError:
                    return CandidateGateIngressState.PARTIAL_HOLD
            finally:
                ingress_parent.close()
    except Exception:
        return CandidateGateIngressState.PARTIAL_HOLD
    try:
        with PinnedCandidateGateIngress.open(root):
            return CandidateGateIngressState.CLOSED
    except Exception:
        return CandidateGateIngressState.PARTIAL_HOLD


def _require_gate_binding(
    gate: CandidateGateReceipt,
    *,
    candidate_root: Path,
    candidate_identity: CandidateRootIdentity,
    selection_key: str,
) -> None:
    if (
        gate.selection_key != selection_key
        or gate.candidate_root != str(candidate_root)
        or gate.candidate_root_identity != candidate_identity
    ):
        raise WarehouseW3CandidateIngressError("candidate gate ingress binding differs")


def publish_candidate_gate_ingress(
    closure_bundle: CandidateGateClosureBundle,
) -> Path:
    """Publish one exact gate closure at its fixed sidecar path, exactly once."""

    if type(closure_bundle) is not CandidateGateClosureBundle:
        raise TypeError("closure_bundle must be exact CandidateGateClosureBundle")
    current_uid = os.geteuid()
    current_gid = os.getegid()
    if (
        type(current_uid) is not int
        or current_uid < 0
        or type(current_gid) is not int
        or current_gid < 0
    ):
        raise TypeError("effective uid and gid must be nonnegative exact integers")
    if current_uid == 0:
        raise PermissionError("candidate gate ingress refuses effective UID 0")
    reopened_closure = CandidateGateClosureBundle.from_bytes(closure_bundle.raw)
    if reopened_closure != closure_bundle:
        raise WarehouseW3CandidateIngressError(
            "candidate gate closure object differs from exact bytes"
        )
    candidate_gate = closure_bundle.gate
    if (
        len(candidate_gate.raw) > _MAX_GATE_BYTES
        or len(closure_bundle.raw) > _MAX_CLOSURE_BYTES
    ):
        raise WarehouseW3CandidateIngressError(
            "candidate gate closure exceeds ingress bounds"
        )
    candidate_root = _absolute_path(
        candidate_gate.candidate_root,
        field="candidate_root",
    )
    paths = derive_candidate_gate_ingress_paths(
        candidate_root,
        candidate_gate.selection_key,
    )
    state = classify_candidate_gate_ingress(candidate_root)
    if state is CandidateGateIngressState.CLOSED:
        raise WarehouseW3CandidateIngressAlreadyPublished(
            "candidate gate ingress is already accepted"
        )
    if state is CandidateGateIngressState.PARTIAL_HOLD:
        raise WarehouseW3CandidateIngressHold(
            "candidate gate ingress is already a permanent partial hold"
        )
    intent = CandidateGateIngressIntent.create(
        candidate_root=candidate_root,
        selection_key=candidate_gate.selection_key,
        gate_sha256=candidate_gate.raw_sha256,
        closure_sha256=closure_bundle.raw_sha256,
    )
    started = False
    candidate_fd = -1
    key_fd = -1
    ingress_parent_fd = -1
    with pin_absolute_directory(str(paths.experiment_parent)) as parent:
        try:
            candidate_fd = _open_directory_at(parent.fd, candidate_root.name)
            candidate_metadata = _require_directory(
                candidate_fd,
                parent_fd=parent.fd,
                leaf=candidate_root.name,
                mode=0o555,
                uid=current_uid,
                gid=current_gid,
                label="candidate root",
            )
            candidate_identity = CandidateRootIdentity.from_stat_result(
                candidate_metadata
            )
            _require_gate_binding(
                candidate_gate,
                candidate_root=candidate_root,
                candidate_identity=candidate_identity,
                selection_key=candidate_gate.selection_key,
            )
            created_ingress_parent = False
            try:
                os.mkdir(_INGRESS_PARENT, 0o700, dir_fd=parent.fd)
                started = True
                os.fsync(parent.fd)
                created_ingress_parent = True
            except FileExistsError:
                pass
            ingress_parent_fd = _open_directory_at(parent.fd, _INGRESS_PARENT)
            if created_ingress_parent:
                os.fchmod(ingress_parent_fd, 0o755)
                os.fsync(ingress_parent_fd)
                os.fsync(parent.fd)
            _require_directory(
                ingress_parent_fd,
                parent_fd=parent.fd,
                leaf=_INGRESS_PARENT,
                mode=0o755,
                uid=current_uid,
                gid=current_gid,
                label="candidate gate ingress parent",
            )
            started = True
            os.mkdir(
                candidate_gate.selection_key,
                0o700,
                dir_fd=ingress_parent_fd,
            )
            os.fsync(ingress_parent_fd)
            key_fd = _open_directory_at(
                ingress_parent_fd,
                candidate_gate.selection_key,
            )
            _require_directory(
                key_fd,
                parent_fd=ingress_parent_fd,
                leaf=candidate_gate.selection_key,
                mode=0o700,
                uid=current_uid,
                gid=current_gid,
                label="candidate gate ingress directory",
            )
            _write_regular_noreplace(
                key_fd,
                leaf=_INGRESS_INTENT_LEAF,
                raw=intent.raw,
            )
            _write_regular_noreplace(
                key_fd,
                leaf=_INGRESS_LEAF,
                raw=candidate_gate.raw,
            )
            _write_regular_noreplace(
                key_fd,
                leaf=_INGRESS_CLOSURE_LEAF,
                raw=closure_bundle.raw,
            )
            if (
                _read_regular_at(
                    key_fd,
                    leaf=_INGRESS_LEAF,
                    maximum=_MAX_GATE_BYTES,
                    label="gate",
                    expected_uid=current_uid,
                    expected_gid=current_gid,
                )
                != candidate_gate.raw
                or _read_regular_at(
                    key_fd,
                    leaf=_INGRESS_CLOSURE_LEAF,
                    maximum=_MAX_CLOSURE_BYTES,
                    label="closure",
                    expected_uid=current_uid,
                    expected_gid=current_gid,
                )
                != closure_bundle.raw
            ):
                raise WarehouseW3CandidateIngressError(
                    "candidate gate closure ingress bytes differ after reopen"
                )
            os.fchmod(key_fd, 0o555)
            os.fsync(key_fd)
            os.fsync(ingress_parent_fd)
            _require_directory(
                key_fd,
                parent_fd=ingress_parent_fd,
                leaf=candidate_gate.selection_key,
                mode=0o555,
                uid=current_uid,
                gid=current_gid,
                label="candidate gate ingress directory",
            )
            final_candidate = _require_directory(
                candidate_fd,
                parent_fd=parent.fd,
                leaf=candidate_root.name,
                mode=0o555,
                uid=current_uid,
                gid=current_gid,
                label="candidate root",
            )
            if _identity_tuple(final_candidate) != _identity_tuple(candidate_metadata):
                raise WarehouseW3CandidateIngressError(
                    "candidate root changed during gate publication"
                )
            parent.revalidate_mutable_leaf()
            with PinnedCandidateGateIngress.open(candidate_root) as pinned:
                if (
                    pinned.gate != candidate_gate
                    or pinned.closure != closure_bundle
                    or pinned.intent != intent
                ):
                    raise WarehouseW3CandidateIngressError(
                        "candidate gate ingress final object differs"
                    )
        except Exception as exc:
            if started:
                raise WarehouseW3CandidateIngressHold(
                    "candidate gate ingress is a permanent partial hold"
                ) from exc
            raise
        finally:
            if key_fd >= 0:
                os.close(key_fd)
            if ingress_parent_fd >= 0:
                os.close(ingress_parent_fd)
            if candidate_fd >= 0:
                os.close(candidate_fd)
    return paths.gate_path


def reopen_candidate_gate_ingress(
    candidate_root: Path,
) -> CandidateGateClosureBundle:
    """Reopen the sole fixed closure and bind it to the pinned candidate."""

    with PinnedCandidateGateIngress.open(candidate_root) as pinned:
        pinned.revalidate()
        return pinned.closure


def pin_candidate_gate_ingress(
    candidate_root: Path,
) -> PinnedCandidateGateIngress:
    """Return the retained-FD authority required by root staging import."""

    return PinnedCandidateGateIngress.open(candidate_root)


__all__ = [
    "CandidateGateIngressFact",
    "CandidateGateIngressIntent",
    "CandidateGateIngressPaths",
    "CandidateGateIngressState",
    "PinnedCandidateGateIngress",
    "WarehouseW3CandidateIngressAlreadyPublished",
    "WarehouseW3CandidateIngressError",
    "WarehouseW3CandidateIngressHold",
    "classify_candidate_gate_ingress",
    "derive_candidate_gate_ingress_paths",
    "pin_candidate_gate_ingress",
    "publish_candidate_gate_ingress",
    "reopen_candidate_gate_ingress",
]
