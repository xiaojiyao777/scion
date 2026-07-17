"""SQL-free immutable values for revisioned Branch and hypothesis owners.

The public Branch and HypothesisRecord models are intentionally mutable.  A
durable owner token therefore stores only strict canonical JSON bytes, their
digest, the owner ID, and the expected SQLite revision.  ``value()`` decodes a
new detached public value on every call; no mutable object is retained inside a
token.

This module deliberately owns no SQL, transaction, lease, Campaign, or policy
behavior.  Persistence modules consume these values in the D2b.0b cutover.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from scion.core.models import Branch, BranchState, HypothesisRecord

_MAX_SQLITE_INTEGER = (1 << 63) - 1
_SHA256_RE = re.compile(r"[0-9a-f]{64}")

_BRANCH_STORAGE_KEYS = frozenset(
    {
        "branch_id",
        "state",
        "base_champion_id",
        "base_champion_hash",
        "lineage_id",
        "current_code_hash",
        "last_clean_code_hash",
        "screening_expand_count",
        "validation_expand_count",
        "failure_codes",
        "created_at",
        "updated_at",
        "direction",
        "weight_revision",
        "branch_code_status",
        "branch_evidence_summary",
        "infra_block_count",
    }
)

_HYPOTHESIS_STORAGE_KEYS = frozenset(
    {
        "hypothesis_id",
        "branch_id",
        "change_locus",
        "action",
        "status",
        "target_file",
        "parent_hypothesis_id",
        "suggested_weight",
        "hypothesis_text",
        "created_at",
        "base_champion_version",
        "family_id",
        "family_source",
        "taxonomy_version",
        "predicted_direction",
        "proposal_digest",
    }
)

_HYPOTHESIS_ACTIONS = frozenset({"modify", "create_new", "remove"})
_PREDICTED_DIRECTIONS = frozenset({"improve", "tradeoff", "exploratory"})
_GENERATED_HYPOTHESIS_UTC_MICROSECOND_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"\.[0-9]{6}\+00:00$"
)

__all__ = (
    "ActiveEvaluationLeaseConflict",
    "DurableOwnerError",
    "DurableOwnerIntegrityError",
    "OwnerAlreadyExists",
    "OwnerNotFound",
    "OwnerPayloadConflict",
    "OwnerRevisionConflict",
    "RevisionedBranchRecord",
    "RevisionedHypothesisRecord",
    "branch_storage_payload",
    "generated_hypothesis_storage_payload",
    "hypothesis_storage_payload",
)


class DurableOwnerError(RuntimeError):
    """Base error for the durable Branch/H owner protocol."""


class OwnerNotFound(DurableOwnerError):
    """The requested durable owner does not exist."""


class OwnerAlreadyExists(DurableOwnerError):
    """Insert-once creation found an existing owner ID."""


class OwnerRevisionConflict(DurableOwnerError):
    """The caller's expected durable revision is stale."""


class ActiveEvaluationLeaseConflict(DurableOwnerError):
    """An active evaluation lease excludes an ordinary owner mutation."""


class OwnerPayloadConflict(DurableOwnerError):
    """The requested target conflicts with the expected owner payload."""


class DurableOwnerIntegrityError(DurableOwnerError):
    """Durable owner bytes, metadata, or semantic fields are malformed."""


def branch_storage_payload(branch: Branch) -> dict[str, Any]:
    """Return the complete strict semantic storage projection for a Branch."""

    if not isinstance(branch, Branch):
        raise DurableOwnerIntegrityError("Branch owner value must be a Branch")
    branch_id = _required_text(branch.branch_id, "Branch ID")
    if not isinstance(branch.state, BranchState):
        raise DurableOwnerIntegrityError("Branch state must be a BranchState")
    lineage_id = (
        branch_id
        if branch.lineage_id is None
        else _required_text(branch.lineage_id, "Branch lineage ID")
    )
    return {
        "branch_id": branch_id,
        "state": branch.state.value,
        "base_champion_id": _nonnegative_integer(
            branch.base_champion_id,
            "Branch base champion ID",
        ),
        "base_champion_hash": _required_text(
            branch.base_champion_hash,
            "Branch base champion hash",
        ),
        "lineage_id": lineage_id,
        "current_code_hash": _optional_text(
            branch.current_code_hash,
            "Branch current code hash",
        ),
        "last_clean_code_hash": _optional_text(
            branch.last_clean_code_hash,
            "Branch last clean code hash",
        ),
        "screening_expand_count": _nonnegative_integer(
            branch.screening_expand_count,
            "Branch screening expansion count",
        ),
        "validation_expand_count": _nonnegative_integer(
            branch.validation_expand_count,
            "Branch validation expansion count",
        ),
        "failure_codes": _string_list(branch.failure_codes, "Branch failure codes"),
        "created_at": _datetime_text(branch.created_at, "Branch creation time"),
        "updated_at": _datetime_text(branch.updated_at, "Branch update time"),
        "direction": _optional_text(branch.direction, "Branch direction"),
        "weight_revision": _nonnegative_integer(
            branch.weight_revision,
            "Branch weight revision",
        ),
        "branch_code_status": _required_text(
            branch.branch_code_status,
            "Branch code status",
        ),
        "branch_evidence_summary": _primitive_mapping(
            branch.branch_evidence_summary,
            "Branch evidence summary",
        ),
        "infra_block_count": _nonnegative_integer(
            branch.infra_block_count,
            "Branch infrastructure block count",
        ),
    }


def hypothesis_storage_payload(record: HypothesisRecord) -> dict[str, Any]:
    """Return the complete strict semantic storage projection for one H."""

    if not isinstance(record, HypothesisRecord):
        raise DurableOwnerIntegrityError(
            "hypothesis owner value must be a HypothesisRecord"
        )
    action = _required_text(record.action, "hypothesis action")
    if action not in _HYPOTHESIS_ACTIONS:
        raise DurableOwnerIntegrityError("hypothesis action is invalid")
    predicted_direction = _required_text(
        record.predicted_direction,
        "hypothesis predicted direction",
    )
    if predicted_direction not in _PREDICTED_DIRECTIONS:
        raise DurableOwnerIntegrityError(
            "hypothesis predicted direction is invalid"
        )
    proposal_digest = _optional_text(
        record.proposal_digest,
        "hypothesis proposal digest",
    )
    if proposal_digest is not None and _SHA256_RE.fullmatch(proposal_digest) is None:
        raise DurableOwnerIntegrityError(
            "hypothesis proposal digest must be a lowercase full SHA-256"
        )
    return {
        "hypothesis_id": _required_text(record.hypothesis_id, "hypothesis ID"),
        "branch_id": _required_text(record.branch_id, "hypothesis Branch ID"),
        "change_locus": _required_text(
            record.change_locus,
            "hypothesis change locus",
        ),
        "action": action,
        "status": _required_text(record.status, "hypothesis status"),
        "target_file": _optional_text(record.target_file, "hypothesis target file"),
        "parent_hypothesis_id": _optional_text(
            record.parent_hypothesis_id,
            "hypothesis parent ID",
        ),
        "suggested_weight": _optional_finite_float(
            record.suggested_weight,
            "hypothesis suggested weight",
        ),
        "hypothesis_text": _optional_text(
            record.hypothesis_text,
            "hypothesis text",
        ),
        "created_at": _datetime_text(record.created_at, "hypothesis creation time"),
        "base_champion_version": _nonnegative_integer(
            record.base_champion_version,
            "hypothesis base champion version",
        ),
        "family_id": _optional_text(record.family_id, "hypothesis family ID"),
        "family_source": _optional_text(
            record.family_source,
            "hypothesis family source",
        ),
        "taxonomy_version": _optional_text(
            record.taxonomy_version,
            "hypothesis taxonomy version",
        ),
        "predicted_direction": predicted_direction,
        "proposal_digest": proposal_digest,
    }


def generated_hypothesis_storage_payload(
    record: HypothesisRecord,
) -> dict[str, Any]:
    """Return the Checkpoint-B generated-H projection.

    This deliberately differs from the generic owner projection only in its
    timestamp protocol: generated H records require UTC and always retain six
    fractional digits, including exact-second ``.000000`` values.
    """

    payload = hypothesis_storage_payload(record)
    payload["created_at"] = _generated_hypothesis_datetime_text(
        record.created_at,
        "generated hypothesis creation time",
    )
    return payload


@dataclass(frozen=True, slots=True)
class RevisionedBranchRecord:
    """Immutable expected owner for one durable Branch row."""

    branch_id: str
    owner_revision: int
    canonical_payload_json: bytes
    payload_sha256: str

    def __post_init__(self) -> None:
        token_id = _required_text(self.branch_id, "Branch token ID")
        _validate_revision(self.owner_revision)
        payload = _load_canonical_payload(
            self.canonical_payload_json,
            self.payload_sha256,
            _BRANCH_STORAGE_KEYS,
            "Branch",
        )
        validated = _validate_branch_payload(payload)
        if _canonical_json_bytes(validated) != self.canonical_payload_json:
            raise DurableOwnerIntegrityError(
                "Branch payload is not in canonical storage form"
            )
        if token_id != validated["branch_id"]:
            raise DurableOwnerIntegrityError(
                "Branch token ID does not match its canonical payload"
            )

    @classmethod
    def from_value(
        cls,
        branch: Branch,
        owner_revision: int,
    ) -> "RevisionedBranchRecord":
        payload = branch_storage_payload(branch)
        canonical = _canonical_json_bytes(payload)
        return cls(
            branch_id=payload["branch_id"],
            owner_revision=owner_revision,
            canonical_payload_json=canonical,
            payload_sha256=_sha256(canonical),
        )

    def value(self) -> Branch:
        payload = _load_canonical_payload(
            self.canonical_payload_json,
            self.payload_sha256,
            _BRANCH_STORAGE_KEYS,
            "Branch",
        )
        payload = _validate_branch_payload(payload)
        return Branch(
            branch_id=payload["branch_id"],
            state=BranchState(payload["state"]),
            base_champion_id=payload["base_champion_id"],
            base_champion_hash=payload["base_champion_hash"],
            lineage_id=payload["lineage_id"],
            current_code_hash=payload["current_code_hash"],
            last_clean_code_hash=payload["last_clean_code_hash"],
            screening_expand_count=payload["screening_expand_count"],
            validation_expand_count=payload["validation_expand_count"],
            failure_codes=list(payload["failure_codes"]),
            created_at=datetime.fromisoformat(payload["created_at"]),
            updated_at=datetime.fromisoformat(payload["updated_at"]),
            direction=payload["direction"],
            weight_revision=payload["weight_revision"],
            branch_code_status=payload["branch_code_status"],
            branch_evidence_summary=dict(payload["branch_evidence_summary"]),
            infra_block_count=payload["infra_block_count"],
        )


@dataclass(frozen=True, slots=True)
class RevisionedHypothesisRecord:
    """Immutable expected owner for one durable hypothesis row."""

    hypothesis_id: str
    owner_revision: int
    canonical_storage_payload_json: bytes
    payload_sha256: str

    def __post_init__(self) -> None:
        token_id = _required_text(self.hypothesis_id, "hypothesis token ID")
        _validate_revision(self.owner_revision)
        payload = _load_canonical_payload(
            self.canonical_storage_payload_json,
            self.payload_sha256,
            _HYPOTHESIS_STORAGE_KEYS,
            "hypothesis",
        )
        validated = _validate_hypothesis_token_payload(payload)
        if (
            _canonical_json_bytes(validated)
            != self.canonical_storage_payload_json
        ):
            raise DurableOwnerIntegrityError(
                "hypothesis payload is not in canonical storage form"
            )
        if token_id != validated["hypothesis_id"]:
            raise DurableOwnerIntegrityError(
                "hypothesis token ID does not match its canonical payload"
            )

    @classmethod
    def from_value(
        cls,
        hypothesis: HypothesisRecord,
        owner_revision: int,
    ) -> "RevisionedHypothesisRecord":
        payload = hypothesis_storage_payload(hypothesis)
        canonical = _canonical_json_bytes(payload)
        return cls(
            hypothesis_id=payload["hypothesis_id"],
            owner_revision=owner_revision,
            canonical_storage_payload_json=canonical,
            payload_sha256=_sha256(canonical),
        )

    @classmethod
    def from_generated_value(
        cls,
        hypothesis: HypothesisRecord,
        owner_revision: int,
    ) -> "RevisionedHypothesisRecord":
        """Capture one H under the strict generated-H timestamp protocol."""

        payload = generated_hypothesis_storage_payload(hypothesis)
        canonical = _canonical_json_bytes(payload)
        return cls(
            hypothesis_id=payload["hypothesis_id"],
            owner_revision=owner_revision,
            canonical_storage_payload_json=canonical,
            payload_sha256=_sha256(canonical),
        )

    def value(self) -> HypothesisRecord:
        payload = _load_canonical_payload(
            self.canonical_storage_payload_json,
            self.payload_sha256,
            _HYPOTHESIS_STORAGE_KEYS,
            "hypothesis",
        )
        payload = _validate_hypothesis_token_payload(payload)
        return HypothesisRecord(
            hypothesis_id=payload["hypothesis_id"],
            branch_id=payload["branch_id"],
            change_locus=payload["change_locus"],
            action=payload["action"],
            status=payload["status"],
            target_file=payload["target_file"],
            parent_hypothesis_id=payload["parent_hypothesis_id"],
            suggested_weight=payload["suggested_weight"],
            hypothesis_text=payload["hypothesis_text"],
            created_at=datetime.fromisoformat(payload["created_at"]),
            base_champion_version=payload["base_champion_version"],
            family_id=payload["family_id"],
            family_source=payload["family_source"],
            taxonomy_version=payload["taxonomy_version"],
            predicted_direction=payload["predicted_direction"],
            proposal_digest=payload["proposal_digest"],
        )


def _validate_branch_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        branch = Branch(
            branch_id=payload["branch_id"],
            state=BranchState(payload["state"]),
            base_champion_id=payload["base_champion_id"],
            base_champion_hash=payload["base_champion_hash"],
            lineage_id=payload["lineage_id"],
            current_code_hash=payload["current_code_hash"],
            last_clean_code_hash=payload["last_clean_code_hash"],
            screening_expand_count=payload["screening_expand_count"],
            validation_expand_count=payload["validation_expand_count"],
            failure_codes=payload["failure_codes"],
            created_at=_parse_canonical_datetime(
                payload["created_at"],
                "Branch creation time",
            ),
            updated_at=_parse_canonical_datetime(
                payload["updated_at"],
                "Branch update time",
            ),
            direction=payload["direction"],
            weight_revision=payload["weight_revision"],
            branch_code_status=payload["branch_code_status"],
            branch_evidence_summary=payload["branch_evidence_summary"],
            infra_block_count=payload["infra_block_count"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DurableOwnerIntegrityError("Branch canonical payload is invalid") from exc
    return branch_storage_payload(branch)


def _validate_hypothesis_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        hypothesis = HypothesisRecord(
            hypothesis_id=payload["hypothesis_id"],
            branch_id=payload["branch_id"],
            change_locus=payload["change_locus"],
            action=payload["action"],
            status=payload["status"],
            target_file=payload["target_file"],
            parent_hypothesis_id=payload["parent_hypothesis_id"],
            suggested_weight=payload["suggested_weight"],
            hypothesis_text=payload["hypothesis_text"],
            created_at=_parse_canonical_datetime(
                payload["created_at"],
                "hypothesis creation time",
            ),
            base_champion_version=payload["base_champion_version"],
            family_id=payload["family_id"],
            family_source=payload["family_source"],
            taxonomy_version=payload["taxonomy_version"],
            predicted_direction=payload["predicted_direction"],
            proposal_digest=payload["proposal_digest"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DurableOwnerIntegrityError(
            "hypothesis canonical payload is invalid"
        ) from exc
    return hypothesis_storage_payload(hypothesis)


def _validate_generated_hypothesis_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        hypothesis = HypothesisRecord(
            hypothesis_id=payload["hypothesis_id"],
            branch_id=payload["branch_id"],
            change_locus=payload["change_locus"],
            action=payload["action"],
            status=payload["status"],
            target_file=payload["target_file"],
            parent_hypothesis_id=payload["parent_hypothesis_id"],
            suggested_weight=payload["suggested_weight"],
            hypothesis_text=payload["hypothesis_text"],
            created_at=_parse_generated_hypothesis_datetime(
                payload["created_at"],
                "generated hypothesis creation time",
            ),
            base_champion_version=payload["base_champion_version"],
            family_id=payload["family_id"],
            family_source=payload["family_source"],
            taxonomy_version=payload["taxonomy_version"],
            predicted_direction=payload["predicted_direction"],
            proposal_digest=payload["proposal_digest"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DurableOwnerIntegrityError(
            "generated hypothesis canonical payload is invalid"
        ) from exc
    return generated_hypothesis_storage_payload(hypothesis)


def _validate_hypothesis_token_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        return _validate_hypothesis_payload(payload)
    except DurableOwnerIntegrityError as generic_error:
        try:
            return _validate_generated_hypothesis_payload(payload)
        except DurableOwnerIntegrityError:
            raise generic_error


def _load_canonical_payload(
    canonical: bytes,
    digest: str,
    expected_keys: frozenset[str],
    label: str,
) -> dict[str, Any]:
    if type(canonical) is not bytes:
        raise DurableOwnerIntegrityError(f"{label} canonical payload must be bytes")
    if type(digest) is not str or _SHA256_RE.fullmatch(digest) is None:
        raise DurableOwnerIntegrityError(f"{label} payload digest is invalid")
    if _sha256(canonical) != digest:
        raise DurableOwnerIntegrityError(f"{label} payload digest does not match")
    try:
        decoded = json.loads(canonical.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise DurableOwnerIntegrityError(
            f"{label} canonical payload is invalid JSON"
        ) from exc
    if not isinstance(decoded, dict):
        raise DurableOwnerIntegrityError(f"{label} canonical payload must be an object")
    if frozenset(decoded) != expected_keys:
        raise DurableOwnerIntegrityError(f"{label} canonical payload keys are invalid")
    normalized = _primitive_mapping(decoded, f"{label} canonical payload")
    if _canonical_json_bytes(normalized) != canonical:
        raise DurableOwnerIntegrityError(f"{label} payload JSON is not canonical")
    return normalized


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise DurableOwnerIntegrityError("owner payload is not canonical JSON") from exc


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_revision(value: Any) -> int:
    return _nonnegative_integer(value, "owner revision")


def _nonnegative_integer(value: Any, label: str) -> int:
    if type(value) is not int or value < 0 or value > _MAX_SQLITE_INTEGER:
        raise DurableOwnerIntegrityError(
            f"{label} must be a nonnegative SQLite integer"
        )
    return value


def _required_text(value: Any, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise DurableOwnerIntegrityError(f"{label} must be a non-empty string")
    return value


def _optional_text(value: Any, label: str) -> str | None:
    if value is not None and type(value) is not str:
        raise DurableOwnerIntegrityError(f"{label} must be a string or null")
    return value


def _datetime_text(value: Any, label: str) -> str:
    if not isinstance(value, datetime):
        raise DurableOwnerIntegrityError(f"{label} must be a datetime")
    result = value.isoformat()
    if type(result) is not str:
        raise DurableOwnerIntegrityError(f"{label} must encode as a string")
    return result


def _generated_hypothesis_datetime_text(value: Any, label: str) -> str:
    if not isinstance(value, datetime):
        raise DurableOwnerIntegrityError(f"{label} must be a datetime")
    if value.tzinfo != timezone.utc:
        raise DurableOwnerIntegrityError(f"{label} must use UTC")
    result = value.isoformat(timespec="microseconds")
    if _GENERATED_HYPOTHESIS_UTC_MICROSECOND_RE.fullmatch(result) is None:
        raise DurableOwnerIntegrityError(
            f"{label} must use canonical UTC microsecond text"
        )
    return result


def _parse_canonical_datetime(value: Any, label: str) -> datetime:
    if type(value) is not str:
        raise DurableOwnerIntegrityError(f"{label} must be a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise DurableOwnerIntegrityError(f"{label} is invalid") from exc
    if parsed.isoformat() != value:
        raise DurableOwnerIntegrityError(f"{label} is not canonical")
    return parsed


def _parse_generated_hypothesis_datetime(value: Any, label: str) -> datetime:
    if (
        type(value) is not str
        or _GENERATED_HYPOTHESIS_UTC_MICROSECOND_RE.fullmatch(value) is None
    ):
        raise DurableOwnerIntegrityError(
            f"{label} must use canonical UTC microsecond text"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise DurableOwnerIntegrityError(f"{label} is invalid") from exc
    if (
        parsed.tzinfo != timezone.utc
        or parsed.isoformat(timespec="microseconds") != value
    ):
        raise DurableOwnerIntegrityError(
            f"{label} must use canonical UTC microsecond text"
        )
    return parsed


def _optional_finite_float(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DurableOwnerIntegrityError(f"{label} must be a finite number or null")
    result = float(value)
    if not math.isfinite(result):
        raise DurableOwnerIntegrityError(f"{label} must be finite")
    # SQLite REAL normalizes negative zero on durable round-trip.
    return 0.0 if result == 0.0 else result


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(type(item) is not str for item in value):
        raise DurableOwnerIntegrityError(f"{label} must be a list of strings")
    return list(value)


def _primitive_mapping(value: Any, label: str) -> dict[str, Any]:
    try:
        if not isinstance(value, Mapping):
            raise DurableOwnerIntegrityError(f"{label} must be a mapping")
        result: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise DurableOwnerIntegrityError(f"{label} keys must be strings")
            result[key] = _primitive_value(item, f"{label}.{key}")
        return result
    except RecursionError as exc:
        raise DurableOwnerIntegrityError(
            f"{label} contains recursively nested values that cannot be processed"
        ) from exc


def _primitive_value(value: Any, label: str) -> Any:
    try:
        if value is None or type(value) in (str, bool):
            return value
        if type(value) is int:
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise DurableOwnerIntegrityError(f"{label} must be finite")
            return 0.0 if value == 0.0 else value
        if isinstance(value, Mapping):
            return _primitive_mapping(value, label)
        if isinstance(value, (list, tuple)):
            return [
                _primitive_value(item, f"{label}[{index}]")
                for index, item in enumerate(value)
            ]
        raise DurableOwnerIntegrityError(
            f"{label} must contain only JSON primitive values"
        )
    except RecursionError as exc:
        raise DurableOwnerIntegrityError(
            f"{label} contains recursively nested values that cannot be processed"
        ) from exc
