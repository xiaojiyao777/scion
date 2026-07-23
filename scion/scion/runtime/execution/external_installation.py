"""Pure contracts for external root installation and first manager dispatch.

This module deliberately contains no concrete filesystem, mount, or D-Bus
transport.  It owns the canonical records and fail-closed classifiers used by
those external owners, plus narrow protocols that can be exercised with mocks.
Concrete privileged application belongs in a later adapter and must preserve
the contracts defined here.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Protocol

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SELECTION_KEY_RE = re.compile(r"[0-9a-f]{64}\Z")
_UNIT_RE = re.compile(r"[A-Za-z0-9:_.@-]+\.service\Z")
_UNIQUE_OWNER_RE = re.compile(r":[0-9]+\.[0-9]+\Z")
_OBJECT_PATH_RE = re.compile(r"/(?:[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*)?\Z")
_ERROR_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\Z")
_BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-" r"[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_UTC_RE = re.compile(
    r"(?:19|20)[0-9]{2}-(?:0[1-9]|1[0-2])-"
    r"(?:0[1-9]|[12][0-9]|3[01])T"
    r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z\Z"
)
_EMPTY_INVOCATION_ID = "0" * 32
_MOUNT_ESCAPE_RE = re.compile(r"\\([0-7]{3})")


class ExternalInstallationError(RuntimeError):
    """An external installation fact or transition is invalid."""


class CanonicalReceiptError(ExternalInstallationError):
    """Receipt bytes are not the one canonical representation."""


class ReceiptDagError(ExternalInstallationError):
    """The append-only root receipt graph is not a forward prefix."""


class MountInfoError(ExternalInstallationError):
    """A selected mountinfo row or mount identity is invalid."""


class ManagerAcceptanceError(ExternalInstallationError):
    """The narrow manager acquisition does not prove loaded acceptance."""


class StartPermitError(ExternalInstallationError):
    """A one-shot start permit cannot be issued or reused."""


class DefiniteStartError(RuntimeError):
    """A manager returned a definite, bounded D-Bus rejection."""

    def __init__(self, error_name: str, message: str) -> None:
        self.error_name = _error_name(error_name)
        self.message = _bounded_text(
            message,
            field="manager error message",
            maximum=512,
            allow_empty=True,
        )
        super().__init__(f"{self.error_name}: {self.message}")


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
        raise CanonicalReceiptError("receipt is not canonical JSON data") from exc


def _decode_canonical_json(raw: bytes, *, label: str) -> object:
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
        raise CanonicalReceiptError(f"{label} is not canonical JSON") from exc
    if _canonical_json(value) != raw:
        raise CanonicalReceiptError(f"{label} bytes are not canonical")
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
        raise CanonicalReceiptError(f"{label} fields differ")
    return value


def _text(value: object, *, field: str, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value):
        raise ExternalInstallationError(f"{field} must be exact text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise ExternalInstallationError(f"{field} is not UTF-8") from exc
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise ExternalInstallationError(f"{field} contains a control character")
    return value


def _bounded_text(
    value: object,
    *,
    field: str,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    text = _text(value, field=field, allow_empty=allow_empty)
    if len(text.encode("utf-8")) > maximum:
        raise ExternalInstallationError(f"{field} exceeds {maximum} bytes")
    return text


def _sha256(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _SHA256_RE.fullmatch(text) is None:
        raise ExternalInstallationError(f"{field} is not canonical SHA-256")
    return text


def _launch_id(value: object) -> str:
    return _sha256(value, field="launch_id")


def _selection_key(value: object) -> str:
    text = _text(value, field="selection_key")
    if _SELECTION_KEY_RE.fullmatch(text) is None:
        raise ExternalInstallationError("selection_key is not canonical")
    return text


def _unit(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if not text.isascii() or _UNIT_RE.fullmatch(text) is None:
        raise ExternalInstallationError(f"{field} is not a canonical service unit")
    return text


def _object_path(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if not text.isascii() or _OBJECT_PATH_RE.fullmatch(text) is None:
        raise ExternalInstallationError(f"{field} is not a canonical object path")
    return text


def _error_name(value: object) -> str:
    text = _bounded_text(value, field="manager error name", maximum=256)
    if not text.isascii() or _ERROR_NAME_RE.fullmatch(text) is None:
        raise ExternalInstallationError("manager error name is not canonical")
    return text


def _boot_id(value: object) -> str:
    text = _text(value, field="boot_id")
    if _BOOT_ID_RE.fullmatch(text) is None:
        raise ExternalInstallationError("boot_id is not canonical")
    return text


def _unique_owner(value: object) -> str:
    text = _text(value, field="manager unique owner")
    if _UNIQUE_OWNER_RE.fullmatch(text) is None:
        raise ExternalInstallationError("manager unique owner is not canonical")
    return text


def _manager_version(value: object) -> str:
    text = _bounded_text(value, field="manager version", maximum=256)
    if re.match(r"255(?:\D|$)", text) is None:
        raise ExternalInstallationError("manager major version is not 255")
    return text


def _utc(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _UTC_RE.fullmatch(text) is None:
        raise ExternalInstallationError(f"{field} is not canonical UTC")
    return text


def _positive_int(value: object, *, field: str, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        raise ExternalInstallationError(f"{field} is not an integer >= {minimum}")
    return value


def _path(value: object, *, field: str, allow_root: bool = True) -> str:
    text = _text(value, field=field)
    path = PurePosixPath(text)
    if (
        not path.is_absolute()
        or str(path) != text
        or text.startswith("//")
        or ".." in path.parts
        or (not allow_root and text == "/")
    ):
        raise ExternalInstallationError(f"{field} is not a canonical absolute path")
    return text


def _string_tuple(
    value: object, *, field: str, allow_empty: bool = True
) -> tuple[str, ...]:
    if type(value) is not list:
        raise CanonicalReceiptError(f"{field} is not an array")
    items = tuple(_text(item, field=field) for item in value)
    if not allow_empty and not items:
        raise CanonicalReceiptError(f"{field} is empty")
    if len(set(items)) != len(items):
        raise CanonicalReceiptError(f"{field} contains a duplicate")
    return items


class RootPhase(str, Enum):
    ROOT_STAGING_IMPORTED = "ROOT_STAGING_IMPORTED"
    CANDIDATE_SELECTED = "CANDIDATE_SELECTED"
    STORES_PUBLISHED = "STORES_PUBLISHED"
    AUTHORITY_PUBLISHED = "AUTHORITY_PUBLISHED"
    PROJECTION_MOUNTED = "PROJECTION_MOUNTED"
    UNITS_PUBLISHED = "UNITS_PUBLISHED"
    MANAGER_RELOADED = "MANAGER_RELOADED"
    INSTANCES_LOADED = "INSTANCES_LOADED"
    INSTALLATION_ACCEPTED = "INSTALLATION_ACCEPTED"


INSTALL_PHASES = tuple(RootPhase)
_PHASE_INDEX = {phase: index for index, phase in enumerate(INSTALL_PHASES)}


class RootInstallationState(str, Enum):
    ABSENT = "ABSENT"
    PARTIAL_HOLD = "PARTIAL_HOLD"
    ACCEPTED = "ACCEPTED"


@dataclass(frozen=True, slots=True, init=False)
class RootPhaseReceipt:
    launch_id: str
    phase: RootPhase
    predecessor_sha256: tuple[str, ...]
    effect_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "RootPhaseReceipt":
        del cls
        raise TypeError("RootPhaseReceipt must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("RootPhaseReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        launch_id: str,
        phase: RootPhase,
        predecessor_sha256: tuple[str, ...],
        effect_sha256: str,
    ) -> "RootPhaseReceipt":
        if type(phase) is not RootPhase:
            raise TypeError("phase must be exact RootPhase")
        if type(predecessor_sha256) is not tuple:
            raise TypeError("predecessor_sha256 must be an exact tuple")
        value = {
            "schema": "scion.external-root-phase.v1",
            "launch_id": _launch_id(launch_id),
            "phase": phase.value,
            "predecessor_sha256": [
                _sha256(item, field="predecessor_sha256") for item in predecessor_sha256
            ],
            "effect_sha256": _sha256(effect_sha256, field="effect_sha256"),
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "RootPhaseReceipt":
        value = _exact_fields(
            _decode_canonical_json(raw, label="root phase receipt"),
            frozenset(
                {
                    "schema",
                    "launch_id",
                    "phase",
                    "predecessor_sha256",
                    "effect_sha256",
                }
            ),
            label="root phase receipt",
        )
        if value["schema"] != "scion.external-root-phase.v1":
            raise CanonicalReceiptError("root phase receipt schema differs")
        try:
            phase = RootPhase(value["phase"])
        except (TypeError, ValueError) as exc:
            raise CanonicalReceiptError("root phase receipt phase differs") from exc
        predecessors = _string_tuple(
            value["predecessor_sha256"],
            field="predecessor_sha256",
        )
        predecessors = tuple(
            _sha256(item, field="predecessor_sha256") for item in predecessors
        )
        if len(set(predecessors)) != len(predecessors):
            raise CanonicalReceiptError("predecessor_sha256 contains a duplicate")
        instance = object.__new__(cls)
        object.__setattr__(instance, "launch_id", _launch_id(value["launch_id"]))
        object.__setattr__(instance, "phase", phase)
        object.__setattr__(instance, "predecessor_sha256", predecessors)
        object.__setattr__(
            instance,
            "effect_sha256",
            _sha256(value["effect_sha256"], field="effect_sha256"),
        )
        object.__setattr__(instance, "raw", raw)
        object.__setattr__(instance, "raw_sha256", hashlib.sha256(raw).hexdigest())
        if instance.raw_sha256 in predecessors:
            raise ReceiptDagError("root phase receipt references itself")
        return instance


def validate_forward_receipt_dag(
    receipts: tuple[RootPhaseReceipt, ...],
) -> tuple[RootPhaseReceipt, ...]:
    """Validate one exact no-gap, no-cycle installation prefix."""

    if type(receipts) is not tuple or any(
        type(receipt) is not RootPhaseReceipt for receipt in receipts
    ):
        raise TypeError("receipts must be an exact tuple of RootPhaseReceipt")
    if not receipts:
        return ()
    launch_id = receipts[0].launch_id
    by_phase: dict[RootPhase, RootPhaseReceipt] = {}
    by_sha: dict[str, RootPhaseReceipt] = {}
    for receipt in receipts:
        if receipt.launch_id != launch_id:
            raise ReceiptDagError("root receipt launch identity differs")
        if receipt.phase in by_phase or receipt.raw_sha256 in by_sha:
            raise ReceiptDagError("root receipt replacement or duplicate differs")
        by_phase[receipt.phase] = receipt
        by_sha[receipt.raw_sha256] = receipt
    ordered = tuple(sorted(receipts, key=lambda receipt: _PHASE_INDEX[receipt.phase]))
    expected_phases = INSTALL_PHASES[: len(ordered)]
    if tuple(receipt.phase for receipt in ordered) != expected_phases:
        raise ReceiptDagError("root receipts are not a forward prefix")
    for index, receipt in enumerate(ordered):
        expected_predecessors = () if index == 0 else (ordered[index - 1].raw_sha256,)
        if receipt.predecessor_sha256 != expected_predecessors:
            raise ReceiptDagError("root receipt predecessor differs")
    return ordered


def classify_root_installation(
    receipts: tuple[RootPhaseReceipt, ...],
) -> RootInstallationState:
    if not receipts:
        return RootInstallationState.ABSENT
    try:
        ordered = validate_forward_receipt_dag(receipts)
    except (ReceiptDagError, TypeError):
        return RootInstallationState.PARTIAL_HOLD
    if tuple(receipt.phase for receipt in ordered) == INSTALL_PHASES:
        return RootInstallationState.ACCEPTED
    return RootInstallationState.PARTIAL_HOLD


class NoReplaceReceiptSet:
    """A pure in-memory model of exact-name O_EXCL receipt publication."""

    __slots__ = ("_records",)

    def __init__(self) -> None:
        self._records: dict[str, bytes] = {}

    def write_no_replace(self, name: str, raw: bytes) -> None:
        key = _text(name, field="receipt name")
        if "/" in key or key in {".", ".."}:
            raise ExternalInstallationError("receipt name is not one leaf")
        if type(raw) is not bytes or not raw:
            raise TypeError("receipt raw must be nonempty exact bytes")
        if key in self._records:
            raise FileExistsError(key)
        self._records[key] = raw

    def read(self, name: str) -> bytes:
        return self._records[name]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._records))

    @property
    def write_order(self) -> tuple[str, ...]:
        return tuple(self._records)


@dataclass(frozen=True, slots=True)
class DirectorySnapshot:
    """Complete source directory identity pinned by a root selection."""

    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    nlink: int

    def __post_init__(self) -> None:
        _positive_int(self.device, field="directory snapshot device", allow_zero=True)
        _positive_int(self.inode, field="directory snapshot inode")
        mode = _positive_int(
            self.mode,
            field="directory snapshot mode",
            allow_zero=True,
        )
        if mode > 0o7777:
            raise ExternalInstallationError("directory snapshot mode differs")
        _positive_int(self.uid, field="directory snapshot uid", allow_zero=True)
        _positive_int(self.gid, field="directory snapshot gid", allow_zero=True)
        _positive_int(self.nlink, field="directory snapshot nlink")

    @classmethod
    def from_mapping(cls, value: object) -> "DirectorySnapshot":
        mapping = _exact_fields(
            value,
            frozenset({"device", "inode", "mode", "uid", "gid", "nlink"}),
            label="directory snapshot",
        )
        return cls(
            device=_positive_int(
                mapping["device"],
                field="directory snapshot device",
                allow_zero=True,
            ),
            inode=_positive_int(
                mapping["inode"],
                field="directory snapshot inode",
            ),
            mode=_positive_int(
                mapping["mode"],
                field="directory snapshot mode",
                allow_zero=True,
            ),
            uid=_positive_int(
                mapping["uid"],
                field="directory snapshot uid",
                allow_zero=True,
            ),
            gid=_positive_int(
                mapping["gid"],
                field="directory snapshot gid",
                allow_zero=True,
            ),
            nlink=_positive_int(
                mapping["nlink"],
                field="directory snapshot nlink",
            ),
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
class SelectionReceipt:
    selection_key: str
    launch_id: str
    nonce: str
    authority_sha256: str
    candidate_sha256: str
    preparation_intent_sha256: str
    preparation_commit_sha256: str
    import_receipt_sha256: str
    imported_staging_aggregate_sha256: str
    source_candidate_identity: "DirectorySnapshot"
    source_selection_identity: "DirectorySnapshot"
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "SelectionReceipt":
        del cls
        raise TypeError("SelectionReceipt must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SelectionReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        selection_key: str,
        launch_id: str,
        nonce: str,
        authority_sha256: str,
        candidate_sha256: str,
        preparation_intent_sha256: str,
        preparation_commit_sha256: str,
        import_receipt_sha256: str,
        imported_staging_aggregate_sha256: str,
        source_candidate_identity: "DirectorySnapshot",
        source_selection_identity: "DirectorySnapshot",
    ) -> "SelectionReceipt":
        if (
            type(source_candidate_identity) is not DirectorySnapshot
            or type(source_selection_identity) is not DirectorySnapshot
        ):
            raise TypeError("selection source identities must be DirectorySnapshot")
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": "scion.external-selection.v1",
                    "selection_key": _selection_key(selection_key),
                    "launch_id": _launch_id(launch_id),
                    "nonce": _sha256(nonce, field="nonce"),
                    "authority_sha256": _sha256(
                        authority_sha256,
                        field="authority_sha256",
                    ),
                    "candidate_sha256": _sha256(
                        candidate_sha256,
                        field="candidate_sha256",
                    ),
                    "preparation_intent_sha256": _sha256(
                        preparation_intent_sha256,
                        field="preparation_intent_sha256",
                    ),
                    "preparation_commit_sha256": _sha256(
                        preparation_commit_sha256,
                        field="preparation_commit_sha256",
                    ),
                    "import_receipt_sha256": _sha256(
                        import_receipt_sha256,
                        field="import_receipt_sha256",
                    ),
                    "imported_staging_aggregate_sha256": _sha256(
                        imported_staging_aggregate_sha256,
                        field="imported_staging_aggregate_sha256",
                    ),
                    "source_candidate_identity": (
                        source_candidate_identity.to_mapping()
                    ),
                    "source_selection_identity": (
                        source_selection_identity.to_mapping()
                    ),
                }
            )
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "SelectionReceipt":
        value = _exact_fields(
            _decode_canonical_json(raw, label="selection receipt"),
            frozenset(
                {
                    "schema",
                    "selection_key",
                    "launch_id",
                    "nonce",
                    "authority_sha256",
                    "candidate_sha256",
                    "preparation_intent_sha256",
                    "preparation_commit_sha256",
                    "import_receipt_sha256",
                    "imported_staging_aggregate_sha256",
                    "source_candidate_identity",
                    "source_selection_identity",
                }
            ),
            label="selection receipt",
        )
        if value["schema"] != "scion.external-selection.v1":
            raise CanonicalReceiptError("selection receipt schema differs")
        instance = object.__new__(cls)
        object.__setattr__(
            instance, "selection_key", _selection_key(value["selection_key"])
        )
        object.__setattr__(instance, "launch_id", _launch_id(value["launch_id"]))
        object.__setattr__(
            instance,
            "nonce",
            _sha256(value["nonce"], field="nonce"),
        )
        object.__setattr__(
            instance,
            "authority_sha256",
            _sha256(value["authority_sha256"], field="authority_sha256"),
        )
        object.__setattr__(
            instance,
            "candidate_sha256",
            _sha256(value["candidate_sha256"], field="candidate_sha256"),
        )
        object.__setattr__(
            instance,
            "preparation_intent_sha256",
            _sha256(
                value["preparation_intent_sha256"],
                field="preparation_intent_sha256",
            ),
        )
        object.__setattr__(
            instance,
            "preparation_commit_sha256",
            _sha256(
                value["preparation_commit_sha256"],
                field="preparation_commit_sha256",
            ),
        )
        object.__setattr__(
            instance,
            "import_receipt_sha256",
            _sha256(
                value["import_receipt_sha256"],
                field="import_receipt_sha256",
            ),
        )
        object.__setattr__(
            instance,
            "imported_staging_aggregate_sha256",
            _sha256(
                value["imported_staging_aggregate_sha256"],
                field="imported_staging_aggregate_sha256",
            ),
        )
        object.__setattr__(
            instance,
            "source_candidate_identity",
            DirectorySnapshot.from_mapping(value["source_candidate_identity"]),
        )
        object.__setattr__(
            instance,
            "source_selection_identity",
            DirectorySnapshot.from_mapping(value["source_selection_identity"]),
        )
        object.__setattr__(instance, "raw", raw)
        object.__setattr__(instance, "raw_sha256", hashlib.sha256(raw).hexdigest())
        return instance


@dataclass(frozen=True, slots=True, init=False)
class InstalledAcceptance:
    launch_id: str
    authority_sha256: str
    installation_sha256: str
    phase_receipt_sha256: tuple[str, ...]
    subordinate_receipt_sha256: tuple[tuple[str, str], ...]
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "InstalledAcceptance":
        del cls
        raise TypeError("InstalledAcceptance must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("InstalledAcceptance is final")

    @classmethod
    def create(
        cls,
        *,
        launch_id: str,
        authority_sha256: str,
        installation_sha256: str,
        phase_receipts: tuple[RootPhaseReceipt, ...],
        subordinate_receipt_sha256: Mapping[str, str],
    ) -> "InstalledAcceptance":
        ordered = validate_forward_receipt_dag(phase_receipts)
        normalized_launch_id = _launch_id(launch_id)
        if (
            len(ordered) != len(INSTALL_PHASES)
            or tuple(receipt.phase for receipt in ordered) != INSTALL_PHASES
            or any(receipt.launch_id != normalized_launch_id for receipt in ordered)
        ):
            raise ExternalInstallationError(
                "installed acceptance requires one complete exact phase DAG"
            )
        phases = tuple(receipt.raw_sha256 for receipt in ordered)
        required_subordinates = frozenset(
            {
                "root_selection",
                "sealed_store",
                "environment_content",
                "environment_relocation",
                "projection",
                "units",
                "loaded_manager",
                "dry_root",
                "prestart_absence",
            }
        )
        if (
            not isinstance(subordinate_receipt_sha256, Mapping)
            or frozenset(subordinate_receipt_sha256) != required_subordinates
            or any(type(name) is not str for name in subordinate_receipt_sha256)
        ):
            raise ExternalInstallationError(
                "installed acceptance subordinate inventory differs"
            )
        subordinates = {
            name: _sha256(
                subordinate_receipt_sha256[name],
                field=f"subordinate_receipt_sha256.{name}",
            )
            for name in sorted(required_subordinates)
        }
        value = {
            "schema": "scion.external-installed-acceptance.v1",
            "state": "INSTALLATION_ACCEPTED_NOT_STARTED",
            "formal_jobs_started": 0,
            "launch_id": normalized_launch_id,
            "authority_sha256": _sha256(
                authority_sha256,
                field="authority_sha256",
            ),
            "installation_sha256": _sha256(
                installation_sha256,
                field="installation_sha256",
            ),
            "phase_receipt_sha256": list(phases),
            "subordinate_receipt_sha256": subordinates,
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "InstalledAcceptance":
        value = _exact_fields(
            _decode_canonical_json(raw, label="installed acceptance"),
            frozenset(
                {
                    "schema",
                    "state",
                    "formal_jobs_started",
                    "launch_id",
                    "authority_sha256",
                    "installation_sha256",
                    "phase_receipt_sha256",
                    "subordinate_receipt_sha256",
                }
            ),
            label="installed acceptance",
        )
        if (
            value["schema"] != "scion.external-installed-acceptance.v1"
            or value["state"] != "INSTALLATION_ACCEPTED_NOT_STARTED"
            or type(value["formal_jobs_started"]) is not int
            or value["formal_jobs_started"] != 0
        ):
            raise CanonicalReceiptError("installed acceptance state differs")
        instance = object.__new__(cls)
        object.__setattr__(instance, "launch_id", _launch_id(value["launch_id"]))
        for field in (
            "authority_sha256",
            "installation_sha256",
        ):
            object.__setattr__(
                instance,
                field,
                _sha256(value[field], field=field),
            )
        raw_phases = value["phase_receipt_sha256"]
        if type(raw_phases) is not list:
            raise CanonicalReceiptError("installed acceptance phases are not an array")
        phases = tuple(
            _sha256(item, field="phase_receipt_sha256") for item in raw_phases
        )
        if len(phases) != len(INSTALL_PHASES) or len(set(phases)) != len(phases):
            raise CanonicalReceiptError("installed acceptance phase inventory differs")
        raw_subordinates = _exact_fields(
            value["subordinate_receipt_sha256"],
            frozenset(
                {
                    "root_selection",
                    "sealed_store",
                    "environment_content",
                    "environment_relocation",
                    "projection",
                    "units",
                    "loaded_manager",
                    "dry_root",
                    "prestart_absence",
                }
            ),
            label="installed acceptance subordinates",
        )
        subordinates = tuple(
            (
                name,
                _sha256(
                    raw_subordinates[name],
                    field=f"subordinate_receipt_sha256.{name}",
                ),
            )
            for name in sorted(raw_subordinates)
        )
        object.__setattr__(instance, "phase_receipt_sha256", phases)
        object.__setattr__(
            instance,
            "subordinate_receipt_sha256",
            subordinates,
        )
        object.__setattr__(instance, "raw", raw)
        object.__setattr__(instance, "raw_sha256", hashlib.sha256(raw).hexdigest())
        return instance

    def verify_phase_receipts(
        self,
        phase_receipts: tuple[RootPhaseReceipt, ...],
    ) -> tuple[RootPhaseReceipt, ...]:
        """Reopen the exact full forward DAG bound by this acceptance."""

        ordered = validate_forward_receipt_dag(phase_receipts)
        if (
            len(ordered) != len(INSTALL_PHASES)
            or tuple(receipt.phase for receipt in ordered) != INSTALL_PHASES
            or any(receipt.launch_id != self.launch_id for receipt in ordered)
            or tuple(receipt.raw_sha256 for receipt in ordered)
            != self.phase_receipt_sha256
        ):
            raise ReceiptDagError("installed acceptance phase DAG differs")
        return ordered


def _unescape_mount_token(token: str, *, field: str) -> str:
    if "\\" not in token:
        return token
    output: list[str] = []
    index = 0
    while index < len(token):
        if token[index] != "\\":
            output.append(token[index])
            index += 1
            continue
        match = _MOUNT_ESCAPE_RE.match(token, index)
        if match is None:
            raise MountInfoError(f"{field} contains a noncanonical escape")
        byte = int(match.group(1), 8)
        if byte not in {0x09, 0x0A, 0x20, 0x5C}:
            raise MountInfoError(f"{field} contains an unsupported escape")
        output.append(chr(byte))
        index = match.end()
    return "".join(output)


def _option_tuple(token: str, *, field: str) -> tuple[str, ...]:
    items = tuple(token.split(","))
    if not items or any(not item for item in items) or len(set(items)) != len(items):
        raise MountInfoError(f"{field} is not a unique nonempty option list")
    return items


@dataclass(frozen=True, slots=True, init=False)
class MountInfoRow:
    mount_id: int
    parent_id: int
    major: int
    minor: int
    root: str
    mount_point: str
    mount_options: tuple[str, ...]
    optional_fields: tuple[str, ...]
    filesystem_type: str
    mount_source: str
    super_options: tuple[str, ...]
    canonical: bytes
    canonical_sha256: str

    def __new__(cls) -> "MountInfoRow":
        del cls
        raise TypeError("MountInfoRow must be parsed from mountinfo")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("MountInfoRow is final")

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": "scion.mountinfo-selected-row.v1",
            "mount_id": self.mount_id,
            "parent_id": self.parent_id,
            "major": self.major,
            "minor": self.minor,
            "root": self.root,
            "mount_point": self.mount_point,
            "mount_options": list(self.mount_options),
            "optional_fields": list(self.optional_fields),
            "filesystem_type": self.filesystem_type,
            "mount_source": self.mount_source,
            "super_options": list(self.super_options),
        }

    @classmethod
    def from_mapping(cls, raw_value: object) -> "MountInfoRow":
        value = _exact_fields(
            raw_value,
            frozenset(
                {
                    "schema",
                    "mount_id",
                    "parent_id",
                    "major",
                    "minor",
                    "root",
                    "mount_point",
                    "mount_options",
                    "optional_fields",
                    "filesystem_type",
                    "mount_source",
                    "super_options",
                }
            ),
            label="selected mountinfo row",
        )
        if value["schema"] != "scion.mountinfo-selected-row.v1":
            raise MountInfoError("selected mountinfo row schema differs")
        mount_id = _positive_int(value["mount_id"], field="mount_id")
        parent_id = _positive_int(
            value["parent_id"],
            field="parent_id",
            allow_zero=True,
        )
        major = _positive_int(value["major"], field="major", allow_zero=True)
        minor = _positive_int(value["minor"], field="minor", allow_zero=True)
        root = _path(value["root"], field="mount root")
        mount_point = _path(value["mount_point"], field="mount point")
        mount_options = _string_tuple(
            value["mount_options"],
            field="mount options",
            allow_empty=False,
        )
        optional_fields = _string_tuple(
            value["optional_fields"],
            field="mount optional fields",
        )
        filesystem_type = _text(value["filesystem_type"], field="filesystem type")
        mount_source = _text(value["mount_source"], field="mount source")
        super_options = _string_tuple(
            value["super_options"],
            field="super options",
            allow_empty=False,
        )
        for items, field in (
            (mount_options, "mount options"),
            (optional_fields, "mount optional fields"),
            (super_options, "super options"),
        ):
            if any("," in item or " " in item for item in items):
                raise MountInfoError(f"{field} contains a noncanonical token")
        canonical = _canonical_json(
            {
                "schema": "scion.mountinfo-selected-row.v1",
                "mount_id": mount_id,
                "parent_id": parent_id,
                "major": major,
                "minor": minor,
                "root": root,
                "mount_point": mount_point,
                "mount_options": list(mount_options),
                "optional_fields": list(optional_fields),
                "filesystem_type": filesystem_type,
                "mount_source": mount_source,
                "super_options": list(super_options),
            }
        )
        instance = object.__new__(cls)
        for field, item in (
            ("mount_id", mount_id),
            ("parent_id", parent_id),
            ("major", major),
            ("minor", minor),
            ("root", root),
            ("mount_point", mount_point),
            ("mount_options", mount_options),
            ("optional_fields", optional_fields),
            ("filesystem_type", filesystem_type),
            ("mount_source", mount_source),
            ("super_options", super_options),
            ("canonical", canonical),
            ("canonical_sha256", hashlib.sha256(canonical).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance

    @classmethod
    def _from_line(cls, line: str) -> "MountInfoRow":
        if line.count(" - ") != 1:
            raise MountInfoError("mountinfo row does not contain one separator")
        left_text, right_text = line.split(" - ", 1)
        left = left_text.split(" ")
        right = right_text.split(" ")
        if len(left) < 6 or len(right) != 3 or any(not item for item in left + right):
            raise MountInfoError("mountinfo row shape differs")
        try:
            mount_id = int(left[0], 10)
            parent_id = int(left[1], 10)
            major_text, minor_text = left[2].split(":", 1)
            major = int(major_text, 10)
            minor = int(minor_text, 10)
        except (ValueError, TypeError) as exc:
            raise MountInfoError("mountinfo numeric identity differs") from exc
        for number, field, allow_zero in (
            (mount_id, "mount_id", False),
            (parent_id, "parent_id", True),
            (major, "major", True),
            (minor, "minor", True),
        ):
            _positive_int(number, field=field, allow_zero=allow_zero)
        root = _path(
            _unescape_mount_token(left[3], field="mount root"),
            field="mount root",
        )
        mount_point = _path(
            _unescape_mount_token(left[4], field="mount point"),
            field="mount point",
        )
        mount_options = _option_tuple(left[5], field="mount options")
        optional_fields = tuple(left[6:])
        if len(set(optional_fields)) != len(optional_fields):
            raise MountInfoError("mountinfo optional fields contain a duplicate")
        filesystem_type = _text(right[0], field="filesystem type")
        mount_source = _unescape_mount_token(right[1], field="mount source")
        _text(mount_source, field="mount source")
        super_options = _option_tuple(right[2], field="super options")
        value = {
            "schema": "scion.mountinfo-selected-row.v1",
            "mount_id": mount_id,
            "parent_id": parent_id,
            "major": major,
            "minor": minor,
            "root": root,
            "mount_point": mount_point,
            "mount_options": list(mount_options),
            "optional_fields": list(optional_fields),
            "filesystem_type": filesystem_type,
            "mount_source": mount_source,
            "super_options": list(super_options),
        }
        return cls.from_mapping(value)


def parse_selected_mountinfo(raw: bytes, *, mount_point: str) -> MountInfoRow:
    if type(raw) is not bytes:
        raise TypeError("mountinfo must be exact bytes")
    selected_point = _path(mount_point, field="selected mount point")
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise MountInfoError("mountinfo is not ASCII") from exc
    if not text.endswith("\n"):
        raise MountInfoError("mountinfo is not newline terminated")
    rows = tuple(
        MountInfoRow._from_line(line) for line in text[:-1].split("\n") if line
    )
    selected = tuple(row for row in rows if row.mount_point == selected_point)
    if len(selected) != 1:
        raise MountInfoError("selected mount point does not have exactly one row")
    return selected[0]


@dataclass(frozen=True, slots=True)
class DirectoryIdentity:
    device: int
    inode: int

    def __post_init__(self) -> None:
        _positive_int(self.device, field="directory device", allow_zero=True)
        _positive_int(self.inode, field="directory inode")


@dataclass(frozen=True, slots=True, init=False)
class MountBindingReceipt:
    mount_point: str
    source_identity: DirectoryIdentity
    destination_identity: DirectoryIdentity
    source_mount_id: int
    destination_mount_id: int
    read_only: bool
    filesystem_type: str
    mount_root: str
    selected_row: MountInfoRow
    selected_row_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "MountBindingReceipt":
        del cls
        raise TypeError("MountBindingReceipt must be derived from a selected row")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("MountBindingReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        row: MountInfoRow,
        source_identity: DirectoryIdentity,
        destination_identity: DirectoryIdentity,
        source_mount_id: int,
        read_only: bool,
        expected_filesystem_type: str,
        expected_mount_root: str,
    ) -> "MountBindingReceipt":
        if (
            type(row) is not MountInfoRow
            or type(source_identity) is not DirectoryIdentity
            or type(destination_identity) is not DirectoryIdentity
            or type(read_only) is not bool
        ):
            raise TypeError("mount binding inputs must be exact contract types")
        source_mount_id = _positive_int(source_mount_id, field="source_mount_id")
        if source_identity != destination_identity:
            raise MountInfoError("bind destination does not retain source identity")
        if row.mount_id == source_mount_id:
            raise MountInfoError("bind destination does not have a distinct mount ID")
        try:
            expected_major = os.major(destination_identity.device)
            expected_minor = os.minor(destination_identity.device)
        except (OverflowError, ValueError) as exc:
            raise MountInfoError("destination device is not a platform device") from exc
        if (row.major, row.minor) != (expected_major, expected_minor):
            raise MountInfoError("mountinfo device differs from destination identity")
        filesystem_type = _text(
            expected_filesystem_type,
            field="expected filesystem type",
        )
        mount_root = _path(expected_mount_root, field="expected mount root")
        if row.filesystem_type != filesystem_type or row.root != mount_root:
            raise MountInfoError("selected mount filesystem or root differs")
        forbidden_prefixes = ("shared:", "master:", "propagate_from:")
        if "unbindable" in row.optional_fields or any(
            item.startswith(forbidden_prefixes) for item in row.optional_fields
        ):
            raise MountInfoError("selected mount is not private")
        options = frozenset(row.mount_options)
        if read_only:
            if "ro" not in options or "rw" in options:
                raise MountInfoError("selected mount is not read-only")
        elif "rw" not in options or "ro" in options:
            raise MountInfoError("selected mount is not read-write")
        value = {
            "schema": "scion.mount-binding.v1",
            "mount_point": row.mount_point,
            "source_device": source_identity.device,
            "source_inode": source_identity.inode,
            "destination_device": destination_identity.device,
            "destination_inode": destination_identity.inode,
            "source_mount_id": source_mount_id,
            "destination_mount_id": row.mount_id,
            "read_only": read_only,
            "filesystem_type": filesystem_type,
            "mount_root": mount_root,
            "selected_row": row.to_mapping(),
            "selected_row_sha256": row.canonical_sha256,
        }
        raw = _canonical_json(value)
        instance = object.__new__(cls)
        for field, item in (
            ("mount_point", row.mount_point),
            ("source_identity", source_identity),
            ("destination_identity", destination_identity),
            ("source_mount_id", source_mount_id),
            ("destination_mount_id", row.mount_id),
            ("read_only", read_only),
            ("filesystem_type", filesystem_type),
            ("mount_root", mount_root),
            ("selected_row", row),
            ("selected_row_sha256", row.canonical_sha256),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance

    @classmethod
    def from_bytes(cls, raw: bytes) -> "MountBindingReceipt":
        value = _exact_fields(
            _decode_canonical_json(raw, label="mount binding receipt"),
            frozenset(
                {
                    "schema",
                    "mount_point",
                    "source_device",
                    "source_inode",
                    "destination_device",
                    "destination_inode",
                    "source_mount_id",
                    "destination_mount_id",
                    "read_only",
                    "filesystem_type",
                    "mount_root",
                    "selected_row",
                    "selected_row_sha256",
                }
            ),
            label="mount binding receipt",
        )
        if value["schema"] != "scion.mount-binding.v1":
            raise CanonicalReceiptError("mount binding receipt schema differs")
        row = MountInfoRow.from_mapping(value["selected_row"])
        if (
            value["mount_point"] != row.mount_point
            or value["destination_mount_id"] != row.mount_id
            or value["selected_row_sha256"] != row.canonical_sha256
        ):
            raise MountInfoError("mount binding selected row differs")
        rebuilt = cls.create(
            row=row,
            source_identity=DirectoryIdentity(
                device=_positive_int(
                    value["source_device"],
                    field="source device",
                    allow_zero=True,
                ),
                inode=_positive_int(value["source_inode"], field="source inode"),
            ),
            destination_identity=DirectoryIdentity(
                device=_positive_int(
                    value["destination_device"],
                    field="destination device",
                    allow_zero=True,
                ),
                inode=_positive_int(
                    value["destination_inode"],
                    field="destination inode",
                ),
            ),
            source_mount_id=_positive_int(
                value["source_mount_id"],
                field="source_mount_id",
            ),
            read_only=value["read_only"],
            expected_filesystem_type=value["filesystem_type"],
            expected_mount_root=value["mount_root"],
        )
        if rebuilt.raw != raw:
            raise CanonicalReceiptError("mount binding semantic bytes differ")
        return rebuilt


def _freeze_manager_value(value: object, *, field: str) -> object:
    if type(value) in {str, int, bool}:
        return value
    if type(value) in {tuple, list}:
        return tuple(_freeze_manager_value(item, field=field) for item in value)
    raise ManagerAcceptanceError(f"{field} contains unsupported {type(value).__name__}")


def _thaw_manager_value(value: object) -> object:
    if type(value) is tuple:
        return [_thaw_manager_value(item) for item in value]
    return value


def _manager_invocation_id(value: object, *, field: str) -> str:
    if type(value) not in {tuple, list} or len(value) != 16:
        raise ManagerAcceptanceError(f"{field} is not a 16-byte manager invocation ID")
    octets = bytearray()
    for item in value:
        if type(item) is not int or not 0 <= item <= 255:
            raise ManagerAcceptanceError(
                f"{field} is not a 16-byte manager invocation ID"
            )
        octets.append(item)
    return bytes(octets).hex()


_LOADED_REQUIRED_PROPERTIES = frozenset(
    {
        "Id",
        "FragmentPath",
        "DropInPaths",
        "LoadState",
        "ActiveState",
        "SubState",
        "Job",
        "InvocationID",
        "Transient",
    }
)


def _normalize_loaded_properties(
    source: Mapping[str, object],
    *,
    expected_inventory: frozenset[str],
    expected_unit: str,
    field: str,
    manager_wire: bool,
) -> tuple[tuple[str, object], ...]:
    if (
        not isinstance(source, Mapping)
        or frozenset(source) != expected_inventory
        or any(type(key) is not str for key in source)
        or not _LOADED_REQUIRED_PROPERTIES.issubset(expected_inventory)
    ):
        raise ManagerAcceptanceError(f"{field} property inventory differs")
    copied = {
        name: _freeze_manager_value(source[name], field=f"{field}.{name}")
        for name in sorted(expected_inventory)
    }
    if manager_wire:
        copied["InvocationID"] = _manager_invocation_id(
            source["InvocationID"],
            field=f"{field}.InvocationID",
        )
    else:
        invocation = _text(source["InvocationID"], field=f"{field}.InvocationID")
        if re.fullmatch(r"[0-9a-f]{32}", invocation) is None:
            raise ManagerAcceptanceError(
                f"{field}.InvocationID is not canonical hexadecimal"
            )
        copied["InvocationID"] = invocation
    if copied["Id"] != expected_unit:
        raise ManagerAcceptanceError(f"{field}.Id differs")
    fragment = _path(copied["FragmentPath"], field=f"{field}.FragmentPath")
    if fragment == "/":
        raise ManagerAcceptanceError(f"{field}.FragmentPath differs")
    copied["FragmentPath"] = fragment
    if copied["DropInPaths"] != ():
        raise ManagerAcceptanceError(f"{field}.DropInPaths is not empty")
    if copied["Transient"] is not False:
        raise ManagerAcceptanceError(f"{field}.Transient is not false")
    if (
        copied["LoadState"] != "loaded"
        or copied["ActiveState"] != "inactive"
        or copied["SubState"] != "dead"
        or copied["InvocationID"] != _EMPTY_INVOCATION_ID
    ):
        raise ManagerAcceptanceError(f"{field} is not loaded and inactive")
    job = copied["Job"]
    if (
        type(job) is not tuple
        or len(job) != 2
        or type(job[0]) is not int
        or job[0] != 0
        or job[1] != "/"
    ):
        raise ManagerAcceptanceError(f"{field}.Job is not empty")
    return tuple(sorted(copied.items()))


def _properties_mapping(
    properties: tuple[tuple[str, object], ...],
) -> dict[str, object]:
    return {name: _thaw_manager_value(value) for name, value in properties}


@dataclass(frozen=True, slots=True)
class ManagerIdentity:
    unique_owner: str
    boot_id: str
    version: str

    def __post_init__(self) -> None:
        _unique_owner(self.unique_owner)
        _boot_id(self.boot_id)
        _manager_version(self.version)


class NarrowInstallationManager(Protocol):
    """Only the manager methods permitted during loaded acquisition."""

    def reload(self) -> None: ...

    def get_unique_owner(self) -> str: ...

    def get_boot_id(self) -> str: ...

    def get_version(self) -> str: ...

    def ref_unit(self, unit: str) -> None: ...

    def unref_unit(self, unit: str) -> None: ...

    def load_unit(self, unit: str) -> str: ...

    def get_unit(self, unit: str) -> str: ...

    def read_properties(
        self,
        unit: str,
        names: tuple[str, ...],
    ) -> Mapping[str, object]: ...


class NarrowStartManager(Protocol):
    """Only the manager methods permitted during one first dispatch."""

    def get_unique_owner(self) -> str: ...

    def get_boot_id(self) -> str: ...

    def get_version(self) -> str: ...

    def ref_unit(self, unit: str) -> None: ...

    def unref_unit(self, unit: str) -> None: ...

    def start_unit(self, unit: str, mode: str) -> str: ...


class NoReplaceReceiptWriter(Protocol):
    """Durable adapters must implement one exact no-replace leaf write."""

    def write_no_replace(self, name: str, raw: bytes) -> None: ...


class PreStartReacquirer(Protocol):
    """Reacquire every live pre-start gate and return its canonical receipt."""

    def __call__(
        self,
        authorization: "StartAuthorizationReceipt",
        installed_acceptance: InstalledAcceptance,
    ) -> bytes: ...


class DurableReceiptDirectory:
    """Descriptor-pinned root-owned no-replace receipt publication."""

    __slots__ = ("_descriptor", "_path")

    def __init__(self, path: Path, *, require_root: bool = True) -> None:
        if not isinstance(path, Path):
            raise TypeError("receipt directory path must be Path")
        canonical = Path(_path(str(path), field="receipt directory", allow_root=False))
        if require_root:
            _require_root()
        flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            descriptor = os.open(canonical, flags)
            opened = os.fstat(descriptor)
            named = os.stat(canonical, follow_symlinks=False)
        except OSError as exc:
            if "descriptor" in locals():
                os.close(descriptor)
            raise ExternalInstallationError("cannot pin receipt directory") from exc
        if (
            not stat.S_ISDIR(opened.st_mode)
            or (
                opened.st_dev,
                opened.st_ino,
                opened.st_mode,
                opened.st_uid,
                opened.st_gid,
            )
            != (
                named.st_dev,
                named.st_ino,
                named.st_mode,
                named.st_uid,
                named.st_gid,
            )
            or (require_root and (opened.st_uid != 0 or opened.st_gid != 0))
        ):
            os.close(descriptor)
            raise ExternalInstallationError("receipt directory identity differs")
        self._descriptor = descriptor
        self._path = canonical

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("DurableReceiptDirectory is final")

    @staticmethod
    def _leaf(name: str) -> str:
        leaf = _text(name, field="receipt name")
        if "/" in leaf or leaf in {".", ".."}:
            raise ExternalInstallationError("receipt name is not one leaf")
        return leaf

    def _require_open(self) -> int:
        if self._descriptor < 0:
            raise ExternalInstallationError("receipt directory is closed")
        return self._descriptor

    def write_no_replace(self, name: str, raw: bytes) -> None:
        directory_fd = self._require_open()
        leaf = self._leaf(name)
        if type(raw) is not bytes or not raw:
            raise TypeError("receipt raw must be nonempty exact bytes")
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(leaf, flags, 0o444, dir_fd=directory_fd)
        try:
            os.fchmod(descriptor, 0o444)
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("receipt write made no progress")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(directory_fd)
        if self.read(leaf) != raw:
            raise ExternalInstallationError("durable receipt bytes differ")

    def read(self, name: str, *, maximum: int = 4 * 1024 * 1024) -> bytes:
        directory_fd = self._require_open()
        leaf = self._leaf(name)
        if type(maximum) is not int or maximum <= 0:
            raise TypeError("receipt maximum must be a positive exact integer")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(leaf, flags, dir_fd=directory_fd)
        chunks: list[bytes] = []
        total = 0
        try:
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or stat.S_IMODE(before.st_mode) != 0o444
                or before.st_nlink != 1
            ):
                raise ExternalInstallationError(
                    "receipt is not one immutable regular file"
                )
            while True:
                chunk = os.read(descriptor, min(64 * 1024, maximum + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > maximum:
                    raise ExternalInstallationError("receipt exceeds its bound")
            after = os.fstat(descriptor)
            named = os.stat(leaf, dir_fd=directory_fd, follow_symlinks=False)
        finally:
            os.close(descriptor)
        identity = lambda item: (
            item.st_dev,
            item.st_ino,
            item.st_mode,
            item.st_uid,
            item.st_gid,
            item.st_nlink,
            item.st_size,
            item.st_mtime_ns,
            item.st_ctime_ns,
        )
        if (
            identity(before) != identity(after)
            or identity(after) != identity(named)
            or total != after.st_size
        ):
            raise ExternalInstallationError("receipt changed while reopened")
        return b"".join(chunks)

    def close(self) -> None:
        if self._descriptor >= 0:
            os.close(self._descriptor)
            self._descriptor = -1

    def __enter__(self) -> "DurableReceiptDirectory":
        self._require_open()
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        del exc_type, exc, traceback
        self.close()


_SYSTEMD_DESTINATION = "org.freedesktop.systemd1"
_SYSTEMD_MANAGER_PATH = "/org/freedesktop/systemd1"
_SYSTEMD_MANAGER_INTERFACE = "org.freedesktop.systemd1.Manager"
_SYSTEMD_UNIT_INTERFACE = "org.freedesktop.systemd1.Unit"
_SYSTEMD_SERVICE_INTERFACE = "org.freedesktop.systemd1.Service"
_DBUS_PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
_DBUS_DAEMON_DESTINATION = "org.freedesktop.DBus"
_DBUS_DAEMON_PATH = "/org/freedesktop/DBus"
_DBUS_DAEMON_INTERFACE = "org.freedesktop.DBus"
_DBUS_INDEFINITE_ERROR_NAMES = frozenset(
    {
        "org.freedesktop.DBus.Error.Disconnected",
        "org.freedesktop.DBus.Error.NameHasNoOwner",
        "org.freedesktop.DBus.Error.NoNetwork",
        "org.freedesktop.DBus.Error.NoReply",
        "org.freedesktop.DBus.Error.NoServer",
        "org.freedesktop.DBus.Error.ServiceUnknown",
        "org.freedesktop.DBus.Error.Timeout",
        "org.freedesktop.DBus.Local.Disconnected",
    }
)
_SYSTEMD_UNIT_PROPERTIES = frozenset(
    {
        "Id",
        "FragmentPath",
        "DropInPaths",
        "LoadState",
        "ActiveState",
        "SubState",
        "Job",
        "InvocationID",
        "Transient",
        "CollectMode",
        "OnSuccess",
        "OnFailure",
        "After",
    }
)
_SYSTEMD_SERVICE_PROPERTIES = frozenset(
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
    }
)


class SystemdExternalManager:
    """Narrow systemd transport for install acquisition and one first start."""

    __slots__ = ("_bus", "_daemon", "_dbus", "_manager", "_owner")

    def __init__(self) -> None:
        _require_root()
        try:
            dbus = importlib.import_module("dbus")
            bus = dbus.SystemBus()
            daemon_object = bus.get_object(
                _DBUS_DAEMON_DESTINATION,
                _DBUS_DAEMON_PATH,
            )
            daemon = dbus.Interface(
                daemon_object,
                dbus_interface=_DBUS_DAEMON_INTERFACE,
            )
            owner = _unique_owner(str(daemon.GetNameOwner(_SYSTEMD_DESTINATION)))
            manager_object = bus.get_object(owner, _SYSTEMD_MANAGER_PATH)
            manager = dbus.Interface(
                manager_object,
                dbus_interface=_SYSTEMD_MANAGER_INTERFACE,
            )
        except Exception as exc:
            raise ManagerAcceptanceError(
                "cannot acquire narrow systemd manager transport"
            ) from exc
        self._dbus = dbus
        self._bus = bus
        self._daemon = daemon
        self._owner = owner
        self._manager = manager

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SystemdExternalManager is final")

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
        raise ManagerAcceptanceError(f"unsupported D-Bus value {type(value).__name__}")

    def get_unique_owner(self) -> str:
        try:
            return _unique_owner(str(self._daemon.GetNameOwner(_SYSTEMD_DESTINATION)))
        except Exception as exc:
            raise ManagerAcceptanceError(
                "cannot reacquire systemd unique owner"
            ) from exc

    def get_boot_id(self) -> str:
        try:
            raw = Path("/proc/sys/kernel/random/boot_id").read_bytes()
        except OSError as exc:
            raise ManagerAcceptanceError("cannot read boot identity") from exc
        try:
            text = raw.decode("ascii", "strict")
        except UnicodeError as exc:
            raise ManagerAcceptanceError("boot identity is not ASCII") from exc
        if not text.endswith("\n") or text.count("\n") != 1:
            raise ManagerAcceptanceError("boot identity bytes differ")
        return _boot_id(text[:-1])

    def get_version(self) -> str:
        try:
            manager_object = self._bus.get_object(
                self._owner,
                _SYSTEMD_MANAGER_PATH,
            )
            properties = self._dbus.Interface(
                manager_object,
                dbus_interface=_DBUS_PROPERTIES_INTERFACE,
            )
            value = self._decode(properties.Get(_SYSTEMD_MANAGER_INTERFACE, "Version"))
        except ManagerAcceptanceError:
            raise
        except Exception as exc:
            raise ManagerAcceptanceError("cannot read systemd manager version") from exc
        return _manager_version(value)

    def reload(self) -> None:
        self._manager.Reload()

    def ref_unit(self, unit: str) -> None:
        self._manager.RefUnit(_unit(unit, field="referenced unit"))

    def unref_unit(self, unit: str) -> None:
        self._manager.UnrefUnit(_unit(unit, field="unreferenced unit"))

    def load_unit(self, unit: str) -> str:
        return _object_path(
            str(self._manager.LoadUnit(_unit(unit, field="loaded unit"))),
            field="loaded unit object path",
        )

    def get_unit(self, unit: str) -> str:
        return _object_path(
            str(self._manager.GetUnit(_unit(unit, field="current unit"))),
            field="current unit object path",
        )

    def start_unit(self, unit: str, mode: str) -> str:
        unit_name = _unit(unit, field="started unit")
        if mode != "fail":
            raise StartPermitError("start mode differs")
        try:
            result = self._manager.StartUnit(unit_name, mode)
        except Exception as exc:
            dbus_exception = getattr(
                getattr(self._dbus, "exceptions", None),
                "DBusException",
                None,
            )
            if dbus_exception is not None and isinstance(exc, dbus_exception):
                try:
                    name = exc.get_dbus_name()
                    message = exc.get_dbus_message()
                except Exception:
                    raise
                if name in _DBUS_INDEFINITE_ERROR_NAMES:
                    raise
                raise DefiniteStartError(
                    str(name),
                    "" if message is None else str(message),
                ) from exc
            raise
        return _object_path(str(result), field="start job object path")

    def read_properties(
        self,
        unit: str,
        names: tuple[str, ...],
    ) -> Mapping[str, object]:
        unit_name = _unit(unit, field="property unit")
        if (
            type(names) is not tuple
            or not names
            or len(set(names)) != len(names)
            or any(
                type(name) is not str
                or name not in _SYSTEMD_UNIT_PROPERTIES | _SYSTEMD_SERVICE_PROPERTIES
                for name in names
            )
        ):
            raise ManagerAcceptanceError("property request inventory differs")
        try:
            object_path = self.get_unit(unit_name)
            unit_object = self._bus.get_object(self._owner, object_path)
            properties = self._dbus.Interface(
                unit_object,
                dbus_interface=_DBUS_PROPERTIES_INTERFACE,
            )
            copied: dict[str, object] = {}
            for name in names:
                interface = (
                    _SYSTEMD_UNIT_INTERFACE
                    if name in _SYSTEMD_UNIT_PROPERTIES
                    else _SYSTEMD_SERVICE_INTERFACE
                )
                copied[name] = self._decode(properties.Get(interface, name))
            return copied
        except ManagerAcceptanceError:
            raise
        except Exception as exc:
            raise ManagerAcceptanceError(
                f"manager property read failed for {unit_name}"
            ) from exc


def _read_manager_identity(manager: NarrowInstallationManager) -> ManagerIdentity:
    return ManagerIdentity(
        unique_owner=manager.get_unique_owner(),
        boot_id=manager.get_boot_id(),
        version=manager.get_version(),
    )


def _read_start_manager_identity(manager: NarrowStartManager) -> ManagerIdentity:
    return ManagerIdentity(
        unique_owner=manager.get_unique_owner(),
        boot_id=manager.get_boot_id(),
        version=manager.get_version(),
    )


@dataclass(frozen=True, slots=True, init=False)
class LoadedManagerReceipt:
    run_unit: str
    close_unit: str
    manager_identity: ManagerIdentity
    run_object_path: str
    close_object_path: str
    run_properties: tuple[tuple[str, object], ...]
    close_properties: tuple[tuple[str, object], ...]
    configured_pair_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "LoadedManagerReceipt":
        del cls
        raise TypeError("LoadedManagerReceipt must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("LoadedManagerReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        run_unit: str,
        close_unit: str,
        manager_identity: ManagerIdentity,
        run_object_path: str,
        close_object_path: str,
        run_properties: Mapping[str, object],
        close_properties: Mapping[str, object],
        expected_run_properties: Mapping[str, object],
        expected_close_properties: Mapping[str, object],
        configured_pair_sha256: str,
    ) -> "LoadedManagerReceipt":
        if type(manager_identity) is not ManagerIdentity:
            raise TypeError("manager_identity must be exact ManagerIdentity")
        run_name = _unit(run_unit, field="run_unit")
        close_name = _unit(close_unit, field="close_unit")
        if run_name == close_name:
            raise ManagerAcceptanceError("run and closer units must differ")
        run_path = _object_path(run_object_path, field="run object path")
        close_path = _object_path(close_object_path, field="closer object path")
        if run_path == close_path:
            raise ManagerAcceptanceError("run and closer object paths must differ")
        run_inventory = frozenset(expected_run_properties)
        close_inventory = frozenset(expected_close_properties)
        actual_run = _normalize_loaded_properties(
            run_properties,
            expected_inventory=run_inventory,
            expected_unit=run_name,
            field="run",
            manager_wire=True,
        )
        actual_close = _normalize_loaded_properties(
            close_properties,
            expected_inventory=close_inventory,
            expected_unit=close_name,
            field="closer",
            manager_wire=True,
        )
        expected_run = _normalize_loaded_properties(
            expected_run_properties,
            expected_inventory=run_inventory,
            expected_unit=run_name,
            field="expected run",
            manager_wire=True,
        )
        expected_close = _normalize_loaded_properties(
            expected_close_properties,
            expected_inventory=close_inventory,
            expected_unit=close_name,
            field="expected closer",
            manager_wire=True,
        )
        if actual_run != expected_run or actual_close != expected_close:
            raise ManagerAcceptanceError("loaded manager property mapping differs")
        value = {
            "schema": "scion.loaded-manager-acceptance.v1",
            "run_unit": run_name,
            "close_unit": close_name,
            "manager": {
                "unique_owner": manager_identity.unique_owner,
                "boot_id": manager_identity.boot_id,
                "version": manager_identity.version,
            },
            "run_object_path": run_path,
            "close_object_path": close_path,
            "run_properties": _properties_mapping(actual_run),
            "close_properties": _properties_mapping(actual_close),
            "configured_pair_sha256": _sha256(
                configured_pair_sha256,
                field="configured_pair_sha256",
            ),
        }
        return cls.from_bytes(
            _canonical_json(value),
            expected_run_properties=expected_run_properties,
            expected_close_properties=expected_close_properties,
            expected_configured_pair_sha256=configured_pair_sha256,
        )

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        expected_run_properties: Mapping[str, object],
        expected_close_properties: Mapping[str, object],
        expected_configured_pair_sha256: str,
    ) -> "LoadedManagerReceipt":
        value = _exact_fields(
            _decode_canonical_json(raw, label="loaded manager receipt"),
            frozenset(
                {
                    "schema",
                    "run_unit",
                    "close_unit",
                    "manager",
                    "run_object_path",
                    "close_object_path",
                    "run_properties",
                    "close_properties",
                    "configured_pair_sha256",
                }
            ),
            label="loaded manager receipt",
        )
        if value["schema"] != "scion.loaded-manager-acceptance.v1":
            raise CanonicalReceiptError("loaded manager receipt schema differs")
        manager_value = _exact_fields(
            value["manager"],
            frozenset({"unique_owner", "boot_id", "version"}),
            label="loaded manager identity",
        )
        identity = ManagerIdentity(
            unique_owner=manager_value["unique_owner"],
            boot_id=manager_value["boot_id"],
            version=manager_value["version"],
        )
        run_name = _unit(value["run_unit"], field="run_unit")
        close_name = _unit(value["close_unit"], field="close_unit")
        if run_name == close_name:
            raise ManagerAcceptanceError("run and closer units must differ")
        run_path = _object_path(value["run_object_path"], field="run object path")
        close_path = _object_path(
            value["close_object_path"],
            field="closer object path",
        )
        if run_path == close_path:
            raise ManagerAcceptanceError("run and closer object paths must differ")
        run_inventory = frozenset(expected_run_properties)
        close_inventory = frozenset(expected_close_properties)
        run_properties = _normalize_loaded_properties(
            value["run_properties"],
            expected_inventory=run_inventory,
            expected_unit=run_name,
            field="receipt run",
            manager_wire=False,
        )
        close_properties = _normalize_loaded_properties(
            value["close_properties"],
            expected_inventory=close_inventory,
            expected_unit=close_name,
            field="receipt closer",
            manager_wire=False,
        )
        expected_run = _normalize_loaded_properties(
            expected_run_properties,
            expected_inventory=run_inventory,
            expected_unit=run_name,
            field="expected run",
            manager_wire=True,
        )
        expected_close = _normalize_loaded_properties(
            expected_close_properties,
            expected_inventory=close_inventory,
            expected_unit=close_name,
            field="expected closer",
            manager_wire=True,
        )
        if run_properties != expected_run or close_properties != expected_close:
            raise ManagerAcceptanceError("loaded manager receipt properties differ")
        expected_pair_sha = _sha256(
            expected_configured_pair_sha256,
            field="expected_configured_pair_sha256",
        )
        if value["configured_pair_sha256"] != expected_pair_sha:
            raise ManagerAcceptanceError("configured pair digest differs")
        instance = object.__new__(cls)
        for field, item in (
            ("run_unit", run_name),
            ("close_unit", close_name),
            ("manager_identity", identity),
            (
                "run_object_path",
                run_path,
            ),
            (
                "close_object_path",
                close_path,
            ),
            ("run_properties", run_properties),
            ("close_properties", close_properties),
            ("configured_pair_sha256", expected_pair_sha),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


def _require_root() -> None:
    actual = os.geteuid()
    if type(actual) is not int or actual != 0:
        raise PermissionError("external manager mutation requires effective UID 0")


def acquire_loaded_manager_receipt(
    manager: NarrowInstallationManager,
    *,
    run_unit: str,
    close_unit: str,
    expected_run_properties: Mapping[str, object],
    expected_close_properties: Mapping[str, object],
    configured_pair_sha256: str,
    persist_and_reopen: Callable[[bytes], bytes],
) -> LoadedManagerReceipt:
    """Acquire one mocked/narrow loaded-manager receipt under one identity."""

    _require_root()
    if not callable(persist_and_reopen):
        raise TypeError("persist_and_reopen must be callable")
    run_name = _unit(run_unit, field="run_unit")
    close_name = _unit(close_unit, field="close_unit")
    if run_name == close_name:
        raise ManagerAcceptanceError("run and closer units must differ")
    run_inventory = frozenset(expected_run_properties)
    close_inventory = frozenset(expected_close_properties)
    if (
        not _LOADED_REQUIRED_PROPERTIES.issubset(run_inventory)
        or not _LOADED_REQUIRED_PROPERTIES.issubset(close_inventory)
        or any(type(name) is not str for name in run_inventory | close_inventory)
    ):
        raise ManagerAcceptanceError("expected loaded property inventory differs")
    run_names = tuple(sorted(run_inventory))
    close_names = tuple(sorted(close_inventory))
    manager.reload()
    identity = _read_manager_identity(manager)
    manager.ref_unit(run_name)
    run_referenced = True
    close_referenced = False
    try:
        manager.ref_unit(close_name)
        close_referenced = True
        run_loaded = _object_path(
            manager.load_unit(run_name),
            field="loaded run object path",
        )
        run_current = _object_path(
            manager.get_unit(run_name),
            field="current run object path",
        )
        close_loaded = _object_path(
            manager.load_unit(close_name),
            field="loaded closer object path",
        )
        close_current = _object_path(
            manager.get_unit(close_name),
            field="current closer object path",
        )
        if run_loaded != run_current or close_loaded != close_current:
            raise ManagerAcceptanceError("LoadUnit and GetUnit object paths differ")
        if _read_manager_identity(manager) != identity:
            raise ManagerAcceptanceError(
                "manager identity changed before property read"
            )
        run_properties = manager.read_properties(run_name, run_names)
        if _read_manager_identity(manager) != identity:
            raise ManagerAcceptanceError("manager identity changed across run read")
        close_properties = manager.read_properties(close_name, close_names)
        if _read_manager_identity(manager) != identity:
            raise ManagerAcceptanceError("manager identity changed across closer read")
        receipt = LoadedManagerReceipt.create(
            run_unit=run_name,
            close_unit=close_name,
            manager_identity=identity,
            run_object_path=run_loaded,
            close_object_path=close_loaded,
            run_properties=run_properties,
            close_properties=close_properties,
            expected_run_properties=expected_run_properties,
            expected_close_properties=expected_close_properties,
            configured_pair_sha256=configured_pair_sha256,
        )
        reopened_raw = persist_and_reopen(receipt.raw)
        reopened = LoadedManagerReceipt.from_bytes(
            reopened_raw,
            expected_run_properties=expected_run_properties,
            expected_close_properties=expected_close_properties,
            expected_configured_pair_sha256=configured_pair_sha256,
        )
        if reopened != receipt or _read_manager_identity(manager) != identity:
            raise ManagerAcceptanceError("durable manager receipt or identity differs")
        return reopened
    finally:
        try:
            if close_referenced:
                manager.unref_unit(close_name)
        finally:
            if run_referenced:
                manager.unref_unit(run_name)


class StartDispatchState(str, Enum):
    RETURNED = "RETURNED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True, init=False)
class StartAuthorizationReceipt:
    launch_id: str
    authority_sha256: str
    installation_sha256: str
    installed_acceptance_sha256: str
    prospective_intent_sha256: str
    plan_sha256: str
    selection_key: str
    preparation_commit_sha256: str
    root_selection_sha256: str
    user_statement: str
    task_event_identity: str
    recorded_at_utc: str
    unit: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "StartAuthorizationReceipt":
        del cls
        raise TypeError("StartAuthorizationReceipt must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("StartAuthorizationReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        launch_id: str,
        authority_sha256: str,
        installation_sha256: str,
        installed_acceptance_sha256: str,
        prospective_intent_sha256: str,
        plan_sha256: str,
        selection_key: str,
        preparation_commit_sha256: str,
        root_selection_sha256: str,
        user_statement: str,
        task_event_identity: str,
        recorded_at_utc: str,
        unit: str,
    ) -> "StartAuthorizationReceipt":
        value = {
            "schema": "scion.start-authorization.v1",
            "launch_id": _launch_id(launch_id),
            "authority_sha256": _sha256(
                authority_sha256,
                field="authority_sha256",
            ),
            "installation_sha256": _sha256(
                installation_sha256,
                field="installation_sha256",
            ),
            "installed_acceptance_sha256": _sha256(
                installed_acceptance_sha256,
                field="installed_acceptance_sha256",
            ),
            "prospective_intent_sha256": _sha256(
                prospective_intent_sha256,
                field="prospective_intent_sha256",
            ),
            "plan_sha256": _sha256(plan_sha256, field="plan_sha256"),
            "selection_key": _selection_key(selection_key),
            "preparation_commit_sha256": _sha256(
                preparation_commit_sha256,
                field="preparation_commit_sha256",
            ),
            "root_selection_sha256": _sha256(
                root_selection_sha256,
                field="root_selection_sha256",
            ),
            "user_statement": _bounded_text(
                user_statement,
                field="user_statement",
                maximum=4096,
            ),
            "task_event_identity": _bounded_text(
                task_event_identity,
                field="task_event_identity",
                maximum=256,
            ),
            "recorded_at_utc": _utc(
                recorded_at_utc,
                field="recorded_at_utc",
            ),
            "unit": _unit(unit, field="authorized unit"),
            "method": "StartUnit",
            "mode": "fail",
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "StartAuthorizationReceipt":
        value = _exact_fields(
            _decode_canonical_json(raw, label="start authorization"),
            frozenset(
                {
                    "schema",
                    "launch_id",
                    "authority_sha256",
                    "installation_sha256",
                    "installed_acceptance_sha256",
                    "prospective_intent_sha256",
                    "plan_sha256",
                    "selection_key",
                    "preparation_commit_sha256",
                    "root_selection_sha256",
                    "user_statement",
                    "task_event_identity",
                    "recorded_at_utc",
                    "unit",
                    "method",
                    "mode",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="start authorization",
        )
        if (
            value["schema"] != "scion.start-authorization.v1"
            or value["method"] != "StartUnit"
            or value["mode"] != "fail"
            or value["retry"] is not False
            or value["resume"] is not False
            or value["reuse"] is not False
        ):
            raise CanonicalReceiptError("start authorization action differs")
        fields = {
            "launch_id": _launch_id(value["launch_id"]),
            "authority_sha256": _sha256(
                value["authority_sha256"],
                field="authority_sha256",
            ),
            "installation_sha256": _sha256(
                value["installation_sha256"],
                field="installation_sha256",
            ),
            "installed_acceptance_sha256": _sha256(
                value["installed_acceptance_sha256"],
                field="installed_acceptance_sha256",
            ),
            "prospective_intent_sha256": _sha256(
                value["prospective_intent_sha256"],
                field="prospective_intent_sha256",
            ),
            "plan_sha256": _sha256(
                value["plan_sha256"],
                field="plan_sha256",
            ),
            "selection_key": _selection_key(value["selection_key"]),
            "preparation_commit_sha256": _sha256(
                value["preparation_commit_sha256"],
                field="preparation_commit_sha256",
            ),
            "root_selection_sha256": _sha256(
                value["root_selection_sha256"],
                field="root_selection_sha256",
            ),
            "user_statement": _bounded_text(
                value["user_statement"],
                field="user_statement",
                maximum=4096,
            ),
            "task_event_identity": _bounded_text(
                value["task_event_identity"],
                field="task_event_identity",
                maximum=256,
            ),
            "recorded_at_utc": _utc(
                value["recorded_at_utc"],
                field="recorded_at_utc",
            ),
            "unit": _unit(value["unit"], field="authorized unit"),
            "raw": raw,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        instance = object.__new__(cls)
        for field, item in fields.items():
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True, init=False)
class StartIssueReceipt:
    launch_id: str
    authorization_sha256: str
    installation_sha256: str
    installed_acceptance_sha256: str
    prestart_receipt_sha256: str
    manager_unique_owner: str
    boot_id: str
    manager_version: str
    unit: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "StartIssueReceipt":
        del cls
        raise TypeError("StartIssueReceipt must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("StartIssueReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        launch_id: str,
        authorization_sha256: str,
        installation_sha256: str,
        installed_acceptance_sha256: str,
        prestart_receipt_sha256: str,
        manager_unique_owner: str,
        boot_id: str,
        manager_version: str,
        unit: str,
    ) -> "StartIssueReceipt":
        value = {
            "schema": "scion.start-issued.v1",
            "launch_id": _launch_id(launch_id),
            "authorization_sha256": _sha256(
                authorization_sha256,
                field="authorization_sha256",
            ),
            "installation_sha256": _sha256(
                installation_sha256,
                field="installation_sha256",
            ),
            "installed_acceptance_sha256": _sha256(
                installed_acceptance_sha256,
                field="installed_acceptance_sha256",
            ),
            "prestart_receipt_sha256": _sha256(
                prestart_receipt_sha256,
                field="prestart_receipt_sha256",
            ),
            "manager_unique_owner": _unique_owner(manager_unique_owner),
            "boot_id": _boot_id(boot_id),
            "manager_version": _manager_version(manager_version),
            "unit": _unit(unit, field="start unit"),
            "method": "StartUnit",
            "mode": "fail",
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def create_authorized(
        cls,
        authorization: StartAuthorizationReceipt,
        *,
        prestart_receipt_sha256: str,
        manager_identity: ManagerIdentity,
    ) -> "StartIssueReceipt":
        if type(authorization) is not StartAuthorizationReceipt:
            raise TypeError("authorization must be exact StartAuthorizationReceipt")
        if type(manager_identity) is not ManagerIdentity:
            raise TypeError("manager_identity must be exact ManagerIdentity")
        return cls.create(
            launch_id=authorization.launch_id,
            authorization_sha256=authorization.raw_sha256,
            installation_sha256=authorization.installation_sha256,
            installed_acceptance_sha256=(authorization.installed_acceptance_sha256),
            prestart_receipt_sha256=prestart_receipt_sha256,
            manager_unique_owner=manager_identity.unique_owner,
            boot_id=manager_identity.boot_id,
            manager_version=manager_identity.version,
            unit=authorization.unit,
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "StartIssueReceipt":
        value = _exact_fields(
            _decode_canonical_json(raw, label="start issue receipt"),
            frozenset(
                {
                    "schema",
                    "launch_id",
                    "authorization_sha256",
                    "installation_sha256",
                    "installed_acceptance_sha256",
                    "prestart_receipt_sha256",
                    "manager_unique_owner",
                    "boot_id",
                    "manager_version",
                    "unit",
                    "method",
                    "mode",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="start issue receipt",
        )
        if (
            value["schema"] != "scion.start-issued.v1"
            or value["method"] != "StartUnit"
            or value["mode"] != "fail"
            or value["retry"] is not False
            or value["resume"] is not False
            or value["reuse"] is not False
        ):
            raise CanonicalReceiptError("start issue action differs")
        instance = object.__new__(cls)
        for field, item in (
            ("launch_id", _launch_id(value["launch_id"])),
            (
                "authorization_sha256",
                _sha256(value["authorization_sha256"], field="authorization_sha256"),
            ),
            (
                "installation_sha256",
                _sha256(
                    value["installation_sha256"],
                    field="installation_sha256",
                ),
            ),
            (
                "installed_acceptance_sha256",
                _sha256(
                    value["installed_acceptance_sha256"],
                    field="installed_acceptance_sha256",
                ),
            ),
            (
                "prestart_receipt_sha256",
                _sha256(
                    value["prestart_receipt_sha256"],
                    field="prestart_receipt_sha256",
                ),
            ),
            (
                "manager_unique_owner",
                _unique_owner(value["manager_unique_owner"]),
            ),
            ("boot_id", _boot_id(value["boot_id"])),
            ("manager_version", _manager_version(value["manager_version"])),
            ("unit", _unit(value["unit"], field="start unit")),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True, init=False)
class StartDispatchReceipt:
    issue_sha256: str
    state: StartDispatchState
    job_object_path: str | None
    error_name: str | None
    error_message: str | None
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "StartDispatchReceipt":
        del cls
        raise TypeError("StartDispatchReceipt must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("StartDispatchReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        issue_sha256: str,
        state: StartDispatchState,
        job_object_path: str | None = None,
        error_name: str | None = None,
        error_message: str | None = None,
    ) -> "StartDispatchReceipt":
        if type(state) is not StartDispatchState:
            raise TypeError("state must be exact StartDispatchState")
        if state is StartDispatchState.RETURNED:
            job = _object_path(job_object_path, field="start job object path")
            error_name_value = None
            error_message_value = None
            if error_name is not None or error_message is not None:
                raise StartPermitError("returned start cannot contain an error")
        elif state is StartDispatchState.REJECTED:
            if job_object_path is not None:
                raise StartPermitError("rejected start cannot contain a job path")
            job = None
            error_name_value = _error_name(error_name)
            error_message_value = _bounded_text(
                error_message,
                field="manager error message",
                maximum=512,
                allow_empty=True,
            )
        else:
            if (
                job_object_path is not None
                or error_name is not None
                or error_message is not None
            ):
                raise StartPermitError("unknown start cannot claim a result")
            job = None
            error_name_value = None
            error_message_value = None
        value = {
            "schema": "scion.start-dispatch.v1",
            "issue_sha256": _sha256(issue_sha256, field="issue_sha256"),
            "state": state.value,
            "job_object_path": job,
            "error_name": error_name_value,
            "error_message": error_message_value,
        }
        raw = _canonical_json(value)
        instance = object.__new__(cls)
        for field, item in (
            ("issue_sha256", value["issue_sha256"]),
            ("state", state),
            ("job_object_path", job),
            ("error_name", error_name_value),
            ("error_message", error_message_value),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance

    @classmethod
    def from_bytes(cls, raw: bytes) -> "StartDispatchReceipt":
        value = _exact_fields(
            _decode_canonical_json(raw, label="start dispatch receipt"),
            frozenset(
                {
                    "schema",
                    "issue_sha256",
                    "state",
                    "job_object_path",
                    "error_name",
                    "error_message",
                }
            ),
            label="start dispatch receipt",
        )
        if value["schema"] != "scion.start-dispatch.v1":
            raise CanonicalReceiptError("start dispatch schema differs")
        try:
            state = StartDispatchState(value["state"])
        except (TypeError, ValueError) as exc:
            raise CanonicalReceiptError("start dispatch state differs") from exc
        rebuilt = cls.create(
            issue_sha256=_sha256(value["issue_sha256"], field="issue_sha256"),
            state=state,
            job_object_path=value["job_object_path"],
            error_name=value["error_name"],
            error_message=value["error_message"],
        )
        if rebuilt.raw != raw:
            raise CanonicalReceiptError("start dispatch semantic bytes differ")
        return rebuilt


class StartPermitOwner:
    """One-use owner; fresh gates precede START_ISSUED and exact dispatch."""

    __slots__ = (
        "_authorization",
        "_installed_acceptance",
        "_issue",
        "_manager",
        "_reacquire_prestart",
        "_writer",
        "_spent",
    )

    def __init__(
        self,
        *,
        authorization: StartAuthorizationReceipt,
        installed_acceptance: InstalledAcceptance,
        phase_receipts: tuple[RootPhaseReceipt, ...],
        issue: StartIssueReceipt,
        manager: NarrowStartManager,
        reacquire_prestart: PreStartReacquirer,
        writer: NoReplaceReceiptWriter,
    ) -> None:
        if type(authorization) is not StartAuthorizationReceipt:
            raise TypeError("authorization must be exact StartAuthorizationReceipt")
        if type(installed_acceptance) is not InstalledAcceptance:
            raise TypeError("installed_acceptance must be exact InstalledAcceptance")
        installed_acceptance.verify_phase_receipts(phase_receipts)
        if type(issue) is not StartIssueReceipt:
            raise TypeError("issue must be exact StartIssueReceipt")
        if not callable(reacquire_prestart):
            raise TypeError("reacquire_prestart must be callable")
        if not callable(getattr(writer, "write_no_replace", None)):
            raise TypeError("writer lacks write_no_replace")
        if (
            authorization.raw_sha256 != issue.authorization_sha256
            or authorization.launch_id != issue.launch_id
            or authorization.installation_sha256 != issue.installation_sha256
            or authorization.installed_acceptance_sha256
            != issue.installed_acceptance_sha256
            or authorization.unit != issue.unit
            or installed_acceptance.raw_sha256
            != authorization.installed_acceptance_sha256
            or installed_acceptance.launch_id != authorization.launch_id
            or installed_acceptance.authority_sha256 != authorization.authority_sha256
            or installed_acceptance.installation_sha256
            != authorization.installation_sha256
        ):
            raise StartPermitError(
                "start authorization, installed acceptance, or issue differs"
            )
        self._authorization = authorization
        self._installed_acceptance = installed_acceptance
        self._issue = issue
        self._manager = manager
        self._reacquire_prestart = reacquire_prestart
        self._writer = writer
        self._spent = False

    def dispatch(self) -> StartDispatchReceipt:
        _require_root()
        if self._spent:
            raise StartPermitError("start permit is already spent")
        self._spent = True
        try:
            prestart_raw = self._reacquire_prestart(
                self._authorization,
                self._installed_acceptance,
            )
        except Exception as exc:
            raise StartPermitError(
                "fresh pre-start gates could not be reacquired"
            ) from exc
        if (
            type(prestart_raw) is not bytes
            or not prestart_raw
            or len(prestart_raw) > 4 * 1024 * 1024
            or hashlib.sha256(prestart_raw).hexdigest()
            != self._issue.prestart_receipt_sha256
        ):
            raise StartPermitError("fresh pre-start receipt differs from issue")
        if (
            type(
                _decode_canonical_json(
                    prestart_raw,
                    label="fresh pre-start receipt",
                )
            )
            is not dict
        ):
            raise StartPermitError("fresh pre-start receipt is not an object")
        expected_identity = ManagerIdentity(
            unique_owner=self._issue.manager_unique_owner,
            boot_id=self._issue.boot_id,
            version=self._issue.manager_version,
        )
        try:
            current_identity = _read_start_manager_identity(self._manager)
        except Exception as exc:
            raise StartPermitError(
                "manager identity could not be acquired before issue"
            ) from exc
        if current_identity != expected_identity:
            raise StartPermitError("manager identity differs before issue")
        self._writer.write_no_replace("START_ISSUED", self._issue.raw)
        referenced = False
        try:
            try:
                self._manager.ref_unit(self._issue.unit)
                referenced = True
                if _read_start_manager_identity(self._manager) != expected_identity:
                    raise ManagerAcceptanceError(
                        "manager identity changed before StartUnit"
                    )
            except Exception:
                receipt = StartDispatchReceipt.create(
                    issue_sha256=self._issue.raw_sha256,
                    state=StartDispatchState.UNKNOWN,
                )
            else:
                result_state: StartDispatchState
                job_path: str | None = None
                error_name: str | None = None
                error_message: str | None = None
                try:
                    job_path = self._manager.start_unit(self._issue.unit, "fail")
                    result_state = StartDispatchState.RETURNED
                except DefiniteStartError as exc:
                    result_state = StartDispatchState.REJECTED
                    error_name = exc.error_name
                    error_message = exc.message
                except Exception:
                    result_state = StartDispatchState.UNKNOWN
                try:
                    identity_stable = (
                        _read_start_manager_identity(self._manager) == expected_identity
                    )
                except Exception:
                    identity_stable = False
                if not identity_stable:
                    result_state = StartDispatchState.UNKNOWN
                    job_path = None
                    error_name = None
                    error_message = None
                try:
                    receipt = StartDispatchReceipt.create(
                        issue_sha256=self._issue.raw_sha256,
                        state=result_state,
                        job_object_path=job_path,
                        error_name=error_name,
                        error_message=error_message,
                    )
                except Exception:
                    receipt = StartDispatchReceipt.create(
                        issue_sha256=self._issue.raw_sha256,
                        state=StartDispatchState.UNKNOWN,
                    )
            outcome_name = (
                "START_DISPATCH_UNKNOWN"
                if receipt.state is StartDispatchState.UNKNOWN
                else f"START_{receipt.state.value}"
            )
            self._writer.write_no_replace(outcome_name, receipt.raw)
            return receipt
        finally:
            if referenced:
                try:
                    self._manager.unref_unit(self._issue.unit)
                except Exception:
                    pass


def classify_start_dispatch(
    issue: StartIssueReceipt | None,
    outcomes: tuple[StartDispatchReceipt, ...],
) -> StartDispatchState | None:
    """Classify a durable issue-only crash as UNKNOWN without authorizing retry."""

    if issue is not None and type(issue) is not StartIssueReceipt:
        raise TypeError("issue must be exact StartIssueReceipt or None")
    if type(outcomes) is not tuple or any(
        type(outcome) is not StartDispatchReceipt for outcome in outcomes
    ):
        raise TypeError("outcomes must be an exact tuple of StartDispatchReceipt")
    if issue is None:
        if outcomes:
            raise StartPermitError("start outcome exists without START_ISSUED")
        return None
    if len(outcomes) > 1:
        raise StartPermitError("multiple start outcomes differ")
    if not outcomes:
        return StartDispatchState.UNKNOWN
    outcome = outcomes[0]
    if outcome.issue_sha256 != issue.raw_sha256:
        raise StartPermitError("start outcome references another issue")
    return outcome.state


__all__ = [
    "CanonicalReceiptError",
    "DefiniteStartError",
    "DirectoryIdentity",
    "DirectorySnapshot",
    "DurableReceiptDirectory",
    "ExternalInstallationError",
    "INSTALL_PHASES",
    "InstalledAcceptance",
    "LoadedManagerReceipt",
    "ManagerAcceptanceError",
    "ManagerIdentity",
    "MountBindingReceipt",
    "MountInfoError",
    "MountInfoRow",
    "NarrowInstallationManager",
    "NarrowStartManager",
    "NoReplaceReceiptWriter",
    "NoReplaceReceiptSet",
    "PreStartReacquirer",
    "ReceiptDagError",
    "RootInstallationState",
    "RootPhase",
    "RootPhaseReceipt",
    "SelectionReceipt",
    "StartDispatchReceipt",
    "StartDispatchState",
    "StartAuthorizationReceipt",
    "StartIssueReceipt",
    "StartPermitError",
    "StartPermitOwner",
    "SystemdExternalManager",
    "acquire_loaded_manager_receipt",
    "classify_root_installation",
    "classify_start_dispatch",
    "parse_selected_mountinfo",
    "validate_forward_receipt_dag",
]
