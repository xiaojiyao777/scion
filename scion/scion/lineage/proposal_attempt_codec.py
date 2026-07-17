"""Pure stored-row codecs for dormant hypothesis proposal attempts.

This module owns only exact stored values and their canonical encodings.  It
does not own SQL, transaction or snapshot lifecycle, durable classification,
attempt inventory, capability state, or semantic event construction.
``ProposalAttemptOwner`` is the sole production importer and remains the
semantic owner of proposal-attempt events and bindings.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Final

from scion.core.proposal_pipeline.attempts import ProposalAttemptRecorder


__all__ = (
    "InvalidStartedHypothesisAttemptError",
    "StartedHypothesisAttemptError",
    "StoredProposalAttemptEvent",
    "StoredProposalHypothesisBinding",
    "decode_stored_proposal_attempt_event",
    "decode_stored_proposal_hypothesis_binding",
    "proposal_hypothesis_transition_group_sha256",
)


_PROPOSAL_ATTEMPT_EVENT_COLUMNS: Final[tuple[str, ...]] = (
    "event_id",
    "campaign_id",
    "branch_id",
    "hypothesis_id",
    "timestamp",
    "event_kind",
    "stage",
    "audit_payload_json",
)
_PROPOSAL_HYPOTHESIS_BINDING_COLUMNS: Final[tuple[str, ...]] = (
    "campaign_id",
    "provider_attempt_id",
    "started_event_id",
    "generated_event_id",
    "branch_id",
    "branch_owner_revision",
    "branch_storage_sha256",
    "hypothesis_id",
    "parent_hypothesis_id",
    "parent_owner_revision",
    "parent_storage_sha256",
    "proposal_digest",
    "hypothesis_storage_sha256",
    "transition_group_sha256",
    "binding_protocol_generation",
    "created_at",
)
_EVENT_KIND: Final[str] = "proposal_attempt_transition"
_EVENT_STAGE: Final[str] = "proposal_hypothesis"
_EVENT_STORAGE_SCHEMA: Final[str] = "proposal-attempt-event-storage.v1"
_BINDING_PROTOCOL_GENERATION: Final[str] = "proposal-h-binding.v1"
_TRANSITION_GROUP_SCHEMA: Final[str] = "proposal-h-transition-group.v1"
_SQLITE_INTEGER_MAX: Final[int] = (1 << 63) - 1
_CANONICAL_UTC_RE: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"\.[0-9]{6}\+00:00$"
)


class StartedHypothesisAttemptError(RuntimeError):
    """Base error retained for ProposalAttemptOwner import compatibility."""


class InvalidStartedHypothesisAttemptError(
    TypeError,
    StartedHypothesisAttemptError,
):
    """A stored proposal-attempt fact is malformed or non-canonical."""


@dataclass(frozen=True, slots=True)
class StoredProposalAttemptEvent:
    """Strict value token for all eight stored proposal-event columns.

    This token is durable evidence, never authority.  Its digest includes the
    exact raw stored JSON text so byte-different rows cannot compare as the
    same storage fact merely because their decoded mappings are equal.
    """

    event_id: str
    campaign_id: str
    branch_id: str
    hypothesis_id: str | None
    timestamp: str
    event_kind: str
    stage: str
    audit_payload_json: str
    storage_sha256: str
    attempt_id: str
    status: str
    context_digest: str
    prompt_hash: str

    @property
    def canonical_payload_json(self) -> bytes:
        return self.audit_payload_json.encode("utf-8")


@dataclass(frozen=True, slots=True)
class StoredProposalHypothesisBinding:
    """Strict value token for one immutable attempt-to-hypothesis binding."""

    campaign_id: str
    provider_attempt_id: str
    started_event_id: str
    generated_event_id: str
    branch_id: str
    branch_owner_revision: int
    branch_storage_sha256: str
    hypothesis_id: str
    parent_hypothesis_id: str | None
    parent_owner_revision: int | None
    parent_storage_sha256: str | None
    proposal_digest: str
    hypothesis_storage_sha256: str
    transition_group_sha256: str
    binding_protocol_generation: str
    created_at: str


def _required_exact_string(value: object, *, field: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise InvalidStartedHypothesisAttemptError(
            f"proposal attempt codec requires exact {field}"
        )
    return value


def _required_digest(value: object, *, field: str) -> str:
    text = _required_exact_string(value, field=field)
    if len(text) != 64:
        raise InvalidStartedHypothesisAttemptError(
            f"proposal attempt codec requires SHA-256 {field}"
        )
    try:
        int(text, 16)
    except ValueError as exc:
        raise InvalidStartedHypothesisAttemptError(
            f"proposal attempt codec requires SHA-256 {field}"
        ) from exc
    if text != text.lower():
        raise InvalidStartedHypothesisAttemptError(
            f"proposal attempt codec requires lowercase SHA-256 {field}"
        )
    return text


def _required_sqlite_integer(value: object, *, field: str) -> int:
    if type(value) is not int or not 0 <= value <= _SQLITE_INTEGER_MAX:
        raise InvalidStartedHypothesisAttemptError(
            f"proposal attempt codec requires nonnegative SQLite integer {field}"
        )
    return value


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidStartedHypothesisAttemptError(
                "proposal attempt JSON contains a duplicate object key"
            )
        result[key] = value
    return result


def _canonical_json_bytes(
    value: object,
    *,
    label: str,
    ensure_ascii: bool = True,
) -> bytes:
    if type(ensure_ascii) is not bool:
        raise InvalidStartedHypothesisAttemptError(
            "canonical JSON ensure_ascii must be exact bool"
        )
    try:
        return json.dumps(
            value,
            ensure_ascii=ensure_ascii,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeEncodeError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            f"{label} cannot be canonically encoded"
        ) from exc


def _raise_nonfinite_json(value: str) -> None:
    raise InvalidStartedHypothesisAttemptError(
        f"proposal attempt JSON contains non-finite value {value}"
    )


def _decode_canonical_payload_json(value: object) -> dict[str, Any]:
    if type(value) is not str:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt payload must be exact SQLite TEXT"
        )
    try:
        decoded = json.loads(
            value,
            object_pairs_hook=_json_object,
            parse_constant=lambda constant: _raise_nonfinite_json(constant),
        )
    except InvalidStartedHypothesisAttemptError:
        raise
    except (TypeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt stored payload is malformed"
        ) from exc
    if type(decoded) is not dict:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt stored payload must be an exact object"
        )
    encoded = _canonical_json_bytes(decoded, label="proposal attempt payload")
    try:
        stored = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt payload is not UTF-8 encodable"
        ) from exc
    if encoded != stored:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt stored payload bytes are not canonical"
        )
    return decoded


def _canonical_utc_timestamp(value: object) -> str:
    if type(value) is not str or _CANONICAL_UTC_RE.fullmatch(value) is None:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt timestamp is not canonical UTC microsecond text"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt timestamp is invalid"
        ) from exc
    if (
        parsed.tzinfo != timezone.utc
        or parsed.isoformat(timespec="microseconds") != value
    ):
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt timestamp is not canonical UTC microsecond text"
        )
    return value


def _stored_event_storage_sha256(
    *,
    event_id: str,
    campaign_id: str,
    branch_id: str,
    hypothesis_id: str | None,
    timestamp: str,
    event_kind: str,
    stage: str,
    audit_payload_json: str,
) -> str:
    storage = {
        "schema_version": _EVENT_STORAGE_SCHEMA,
        "event_id": event_id,
        "campaign_id": campaign_id,
        "branch_id": branch_id,
        "hypothesis_id": hypothesis_id,
        "timestamp": timestamp,
        "event_kind": event_kind,
        "stage": stage,
        "audit_payload_json": audit_payload_json,
    }
    return hashlib.sha256(
        _canonical_json_bytes(storage, label="proposal attempt event storage")
    ).hexdigest()


def decode_stored_proposal_attempt_event(
    row: object,
    *,
    authority_campaign_id: str | None = None,
) -> StoredProposalAttemptEvent:
    """Decode one exact named SQLite row without applying lifecycle semantics."""

    try:
        columns = tuple(row.keys())  # type: ignore[attr-defined]
        values = tuple(row)  # type: ignore[arg-type]
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt event is not a named materialized SQLite row"
        ) from exc
    if columns != _PROPOSAL_ATTEMPT_EVENT_COLUMNS or len(values) != len(
        _PROPOSAL_ATTEMPT_EVENT_COLUMNS
    ):
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt event has incomplete or unexpected columns"
        )
    (
        event_id,
        campaign_id,
        branch_id,
        hypothesis_id,
        timestamp,
        event_kind,
        stage,
        audit_payload_json,
    ) = values
    stored_event_id = _required_exact_string(event_id, field="event_id")
    stored_campaign_id = _required_exact_string(campaign_id, field="campaign_id")
    stored_branch_id = _required_exact_string(branch_id, field="branch_id")
    stored_hypothesis_id = (
        None
        if hypothesis_id is None
        else _required_exact_string(hypothesis_id, field="hypothesis_id")
    )
    stored_timestamp = _canonical_utc_timestamp(timestamp)
    if event_kind != _EVENT_KIND:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt event_kind is not authoritative"
        )
    if stage != _EVENT_STAGE:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt stage is not authoritative"
        )
    if authority_campaign_id is not None:
        expected_campaign_id = _required_exact_string(
            authority_campaign_id,
            field="authority campaign_id",
        )
        if stored_campaign_id != expected_campaign_id:
            raise InvalidStartedHypothesisAttemptError(
                "proposal attempt event belongs to another campaign authority"
            )

    payload = _decode_canonical_payload_json(audit_payload_json)
    try:
        ProposalAttemptRecorder.validate_transition(payload)
    except (TypeError, ValueError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt event failed the complete v1 transition schema"
        ) from exc
    if payload.get("phase") != "hypothesis":
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt owner accepts hypothesis events only"
        )
    if (
        payload.get("attempt_kind") != "initial"
        or payload.get("continuation_of_attempt_id") is not None
    ):
        raise InvalidStartedHypothesisAttemptError(
            "hypothesis attempt must be an initial non-continuation"
        )
    if (
        payload.get("campaign_id") != stored_campaign_id
        or payload.get("branch_id") != stored_branch_id
        or payload.get("hypothesis_id") != stored_hypothesis_id
    ):
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt top-level and payload identities differ"
        )
    attempt_id = _required_exact_string(payload.get("attempt_id"), field="attempt_id")
    status = _required_exact_string(payload.get("status"), field="status")
    prompt_call = payload.get("prompt_call")
    if type(prompt_call) is not dict:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt prompt_call must be an exact object"
        )
    context_digest = _required_exact_string(
        prompt_call.get("context_digest"),
        field="prompt context_digest",
    )
    prompt_hash = _required_exact_string(
        prompt_call.get("prompt_hash"),
        field="prompt_hash",
    )
    if type(audit_payload_json) is not str:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt payload must be SQLite TEXT"
        )
    return StoredProposalAttemptEvent(
        event_id=stored_event_id,
        campaign_id=stored_campaign_id,
        branch_id=stored_branch_id,
        hypothesis_id=stored_hypothesis_id,
        timestamp=stored_timestamp,
        event_kind=event_kind,
        stage=stage,
        audit_payload_json=audit_payload_json,
        storage_sha256=_stored_event_storage_sha256(
            event_id=stored_event_id,
            campaign_id=stored_campaign_id,
            branch_id=stored_branch_id,
            hypothesis_id=stored_hypothesis_id,
            timestamp=stored_timestamp,
            event_kind=event_kind,
            stage=stage,
            audit_payload_json=audit_payload_json,
        ),
        attempt_id=attempt_id,
        status=status,
        context_digest=context_digest,
        prompt_hash=prompt_hash,
    )


def proposal_hypothesis_transition_group_sha256(
    *,
    started_event_id: str,
    started_event_storage_sha256: str,
    generated_event_id: str,
    generated_event_storage_sha256: str,
) -> str:
    """Digest the exact START/generated event IDs and complete stored bytes."""

    started_id = _required_exact_string(started_event_id, field="START event ID")
    generated_id = _required_exact_string(
        generated_event_id,
        field="generated event ID",
    )
    if started_id == generated_id:
        raise InvalidStartedHypothesisAttemptError(
            "proposal transition group requires distinct event IDs"
        )
    payload = {
        "binding_protocol_generation": _BINDING_PROTOCOL_GENERATION,
        "generated_event_id": generated_id,
        "generated_event_storage_sha256": _required_digest(
            generated_event_storage_sha256,
            field="generated event storage digest",
        ),
        "schema_version": _TRANSITION_GROUP_SCHEMA,
        "started_event_id": started_id,
        "started_event_storage_sha256": _required_digest(
            started_event_storage_sha256,
            field="START event storage digest",
        ),
    }
    return hashlib.sha256(
        _canonical_json_bytes(
            payload,
            label="proposal hypothesis transition group",
            ensure_ascii=False,
        )
    ).hexdigest()


def decode_stored_proposal_hypothesis_binding(
    row: object,
    *,
    authority_campaign_id: str | None = None,
) -> StoredProposalHypothesisBinding:
    """Decode one exact immutable proposal-attempt/H binding row."""

    try:
        columns = tuple(row.keys())  # type: ignore[attr-defined]
        values = tuple(row)  # type: ignore[arg-type]
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "proposal hypothesis binding is not a named materialized SQLite row"
        ) from exc
    if columns != _PROPOSAL_HYPOTHESIS_BINDING_COLUMNS or len(values) != len(
        _PROPOSAL_HYPOTHESIS_BINDING_COLUMNS
    ):
        raise InvalidStartedHypothesisAttemptError(
            "proposal hypothesis binding has incomplete or unexpected columns"
        )
    (
        campaign_id,
        provider_attempt_id,
        started_event_id,
        generated_event_id,
        branch_id,
        branch_owner_revision,
        branch_storage_sha256,
        hypothesis_id,
        parent_hypothesis_id,
        parent_owner_revision,
        parent_storage_sha256,
        proposal_digest,
        hypothesis_storage_sha256,
        transition_group_sha256,
        binding_protocol_generation,
        created_at,
    ) = values
    stored_campaign_id = _required_exact_string(campaign_id, field="campaign_id")
    if authority_campaign_id is not None:
        expected_campaign_id = _required_exact_string(
            authority_campaign_id,
            field="authority campaign_id",
        )
        if stored_campaign_id != expected_campaign_id:
            raise InvalidStartedHypothesisAttemptError(
                "proposal hypothesis binding belongs to another campaign authority"
            )
    started_id = _required_exact_string(started_event_id, field="START event ID")
    generated_id = _required_exact_string(
        generated_event_id,
        field="generated event ID",
    )
    if started_id == generated_id:
        raise InvalidStartedHypothesisAttemptError(
            "proposal hypothesis binding requires distinct event IDs"
        )
    if binding_protocol_generation != _BINDING_PROTOCOL_GENERATION:
        raise InvalidStartedHypothesisAttemptError(
            "proposal hypothesis binding protocol generation is unsupported"
        )

    if parent_hypothesis_id is None:
        if parent_owner_revision is not None or parent_storage_sha256 is not None:
            raise InvalidStartedHypothesisAttemptError(
                "proposal hypothesis binding has an incomplete parent triple"
            )
        parent_id = None
        parent_revision = None
        parent_digest = None
    else:
        if parent_owner_revision is None or parent_storage_sha256 is None:
            raise InvalidStartedHypothesisAttemptError(
                "proposal hypothesis binding has an incomplete parent triple"
            )
        parent_id = _required_exact_string(
            parent_hypothesis_id,
            field="parent hypothesis ID",
        )
        parent_revision = _required_sqlite_integer(
            parent_owner_revision,
            field="parent owner revision",
        )
        parent_digest = _required_digest(
            parent_storage_sha256,
            field="parent storage digest",
        )

    return StoredProposalHypothesisBinding(
        campaign_id=stored_campaign_id,
        provider_attempt_id=_required_exact_string(
            provider_attempt_id,
            field="provider attempt ID",
        ),
        started_event_id=started_id,
        generated_event_id=generated_id,
        branch_id=_required_exact_string(branch_id, field="Branch ID"),
        branch_owner_revision=_required_sqlite_integer(
            branch_owner_revision,
            field="Branch owner revision",
        ),
        branch_storage_sha256=_required_digest(
            branch_storage_sha256,
            field="Branch storage digest",
        ),
        hypothesis_id=_required_exact_string(
            hypothesis_id,
            field="hypothesis ID",
        ),
        parent_hypothesis_id=parent_id,
        parent_owner_revision=parent_revision,
        parent_storage_sha256=parent_digest,
        proposal_digest=_required_digest(proposal_digest, field="proposal digest"),
        hypothesis_storage_sha256=_required_digest(
            hypothesis_storage_sha256,
            field="hypothesis storage digest",
        ),
        transition_group_sha256=_required_digest(
            transition_group_sha256,
            field="transition-group digest",
        ),
        binding_protocol_generation=binding_protocol_generation,
        created_at=_canonical_utc_timestamp(created_at),
    )


# Private compatibility aliases are intentionally imported only by
# ProposalAttemptOwner.  They preserve the accepted checkpoint-A implementation
# while the public codec names remain explicit.
_STARTED_EVENT_COLUMNS = _PROPOSAL_ATTEMPT_EVENT_COLUMNS
_decode_stored_proposal_attempt_event = decode_stored_proposal_attempt_event
_decode_stored_proposal_hypothesis_binding = (
    decode_stored_proposal_hypothesis_binding
)
