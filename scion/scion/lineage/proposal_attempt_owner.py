"""Dormant connection-scoped owner for hypothesis-attempt durable events.

The participant owns the strict stored-event codec plus START and non-success
terminal persistence.  It deliberately owns neither Campaign schema nor
transaction/snapshot lifecycle, provider transport, Branch/H stores, or
production composition.  Sealed lifecycle capabilities live only in the leaf
generation authority.
"""

from __future__ import annotations

import enum
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Final

from scion.core.proposal_pipeline.attempts import ProposalAttemptRecorder
from scion.lineage import sqlite_connection as _sqlite
from scion.proposal import hypothesis_generation_authority as _generation

StartedHypothesisAttempt = _generation.StartedHypothesisAttempt
TerminalAttemptReceipt = _generation.TerminalAttemptReceipt

__all__ = (
    "InvalidStartedHypothesisAttemptError",
    "ProposalAttemptCommitClassification",
    "ProposalAttemptOwner",
    "StartedHypothesisAttempt",
    "StartedHypothesisAttemptError",
    "StoredProposalAttemptEvent",
    "TerminalAttemptReceipt",
)

_STARTED_EVENT_COLUMNS: Final[tuple[str, ...]] = (
    "event_id",
    "campaign_id",
    "branch_id",
    "hypothesis_id",
    "timestamp",
    "event_kind",
    "stage",
    "audit_payload_json",
)
_STARTED_EVENT_INSERT_SQL: Final[str] = """
INSERT INTO experiment_events (
    event_id,
    campaign_id,
    branch_id,
    hypothesis_id,
    timestamp,
    event_kind,
    stage,
    audit_payload_json
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""
_STARTED_EVENT_SELECT_SQL: Final[str] = """
SELECT event_id,
       campaign_id,
       branch_id,
       hypothesis_id,
       timestamp,
       event_kind,
       stage,
       audit_payload_json
FROM experiment_events
WHERE event_id = ?
"""
_EVENT_KIND: Final[str] = "proposal_attempt_transition"
_EVENT_STAGE: Final[str] = "proposal_hypothesis"
_EVENT_STORAGE_SCHEMA: Final[str] = "proposal-attempt-event-storage.v1"
_CANONICAL_UTC_RE: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"\.[0-9]{6}\+00:00$"
)
_CAMPAIGN_HYPOTHESIS_EVENTS_SELECT_SQL: Final[str] = """
SELECT event_id,
       campaign_id,
       branch_id,
       hypothesis_id,
       timestamp,
       event_kind,
       stage,
       audit_payload_json
FROM experiment_events
WHERE campaign_id = ?
  AND event_kind = 'proposal_attempt_transition'
ORDER BY timestamp ASC, event_id ASC
"""
_OWNER_CONTEXT_SCHEMA: Final[str] = "hypothesis-owner-context-projection.v1"
_SQLITE_INTEGER_MAX: Final[int] = (1 << 63) - 1
_OWNER_CONTEXT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "campaign_id",
        "runtime_mode",
        "root_generation",
        "branch",
        "h_bundle",
        "prior_head",
        "anchors",
    }
)
_OWNER_BRANCH_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "branch_id",
        "owner_revision",
        "storage_sha256",
        "state",
        "branch_code_status",
        "current_code_hash",
        "last_clean_code_hash",
        "base_champion_id",
        "base_champion_hash",
        "base_champion_weight_revision",
    }
)
_OWNER_H_BUNDLE_FIELDS: Final[frozenset[str]] = frozenset(
    {"digest", "count", "items"}
)
_OWNER_H_ITEM_FIELDS: Final[frozenset[str]] = frozenset(
    {"hypothesis_id", "owner_revision", "storage_sha256"}
)
_ATTEMPT_ANCHOR_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "problem_id",
        "problem_spec_hash",
        "split_manifest_hash",
        "seed_ledger_hash",
        "champion_version",
        "champion_weight_revision",
        "champion_code_snapshot_hash",
        "branch_base_champion_id",
        "branch_base_champion_hash",
    }
)


class StartedHypothesisAttemptError(RuntimeError):
    """Base error for the dormant START owner and its sealed capability."""


class InvalidStartedHypothesisAttemptError(
    TypeError,
    StartedHypothesisAttemptError,
):
    """A START payload or capability is forged, malformed, or mismatched."""


class ProposalAttemptCommitClassification(enum.Enum):
    """Exact independent-snapshot classification for one attempted append."""

    EXPECTED = enum.auto()
    COMMITTED = enum.auto()
    MIXED = enum.auto()


class _AttemptGroupDisposition(enum.Enum):
    RESOLVED = enum.auto()
    UNRESOLVED = enum.auto()
    MALFORMED = enum.auto()


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
class _HypothesisAttemptGroup:
    attempt_id: str
    branch_id: str
    events: tuple[StoredProposalAttemptEvent, ...]
    disposition: _AttemptGroupDisposition


@dataclass(frozen=True, slots=True)
class _HypothesisAttemptInventory:
    groups: tuple[_HypothesisAttemptGroup, ...]
    malformed_branch_ids: tuple[str, ...]
    unattributed_malformed: bool

    def branch_is_clear(self, branch_id: str) -> bool:
        return (
            not self.unattributed_malformed
            and branch_id not in self.malformed_branch_ids
            and all(
                group.branch_id != branch_id
                or group.disposition is _AttemptGroupDisposition.RESOLVED
                for group in self.groups
            )
        )


@dataclass(frozen=True, slots=True)
class _OwnerStartProjection:
    campaign_id: str
    branch_id: str
    runtime_mode: str
    anchors: dict[str, object]


@dataclass(frozen=True, slots=True)
class _PendingStartedProjection:
    stored: StoredProposalAttemptEvent
    bound_prompt: _generation.BoundHypothesisPrompt


def _required_exact_string(value: object, *, field: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise InvalidStartedHypothesisAttemptError(
            f"started hypothesis attempt requires exact {field}"
        )
    return value


def _required_digest(value: object, *, field: str) -> str:
    text = _required_exact_string(value, field=field)
    if len(text) != 64:
        raise InvalidStartedHypothesisAttemptError(
            f"proposal attempt owner requires SHA-256 {field}"
        )
    try:
        int(text, 16)
    except ValueError as exc:
        raise InvalidStartedHypothesisAttemptError(
            f"proposal attempt owner requires SHA-256 {field}"
        ) from exc
    if text != text.lower():
        raise InvalidStartedHypothesisAttemptError(
            f"proposal attempt owner requires lowercase SHA-256 {field}"
        )
    return text


def _optional_digest(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _required_digest(value, field=field)


def _required_sqlite_integer(value: object, *, field: str) -> int:
    if type(value) is not int or not 0 <= value <= _SQLITE_INTEGER_MAX:
        raise InvalidStartedHypothesisAttemptError(
            f"proposal attempt owner requires nonnegative SQLite integer {field}"
        )
    return value


def _required_exact_object(
    value: object,
    *,
    fields: frozenset[str],
    label: str,
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise InvalidStartedHypothesisAttemptError(
            f"proposal attempt owner requires exact {label} object"
        )
    return value


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidStartedHypothesisAttemptError(
                "started hypothesis attempt JSON contains a duplicate object key"
            )
        result[key] = value
    return result


def _canonical_json_bytes(value: object, *, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeEncodeError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            f"{label} cannot be canonically encoded"
        ) from exc


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


def _decode_owner_start_projection(
    projection: _generation._BoundPromptProjection,
    *,
    authority_campaign_id: str,
) -> _OwnerStartProjection:
    """Decode and cross-check the exact owner spine carried by the leaf prompt."""

    if type(projection) is not _generation._BoundPromptProjection:
        raise InvalidStartedHypothesisAttemptError(
            "START requires the leaf bound-prompt projection"
        )
    raw = projection.owner_context_json
    if type(raw) is not bytes or not raw:
        raise InvalidStartedHypothesisAttemptError(
            "bound prompt owner context must be exact canonical bytes"
        )
    try:
        text = raw.decode("utf-8")
        decoded = json.loads(
            text,
            object_pairs_hook=_json_object,
            parse_constant=lambda constant: _raise_nonfinite_json(constant),
        )
    except InvalidStartedHypothesisAttemptError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "bound prompt owner context is malformed"
        ) from exc
    context = _required_exact_object(
        decoded,
        fields=_OWNER_CONTEXT_FIELDS,
        label="owner-context",
    )
    if _canonical_json_bytes(context, label="bound prompt owner context") != raw:
        raise InvalidStartedHypothesisAttemptError(
            "bound prompt owner-context bytes are not canonical"
        )
    if context["schema_version"] != _OWNER_CONTEXT_SCHEMA:
        raise InvalidStartedHypothesisAttemptError(
            "bound prompt owner-context schema is unsupported"
        )
    campaign_id = _required_exact_string(
        context["campaign_id"],
        field="owner campaign_id",
    )
    if campaign_id != authority_campaign_id:
        raise InvalidStartedHypothesisAttemptError(
            "bound prompt belongs to another campaign authority"
        )
    runtime_mode = _required_exact_string(
        context["runtime_mode"],
        field="owner runtime_mode",
    )
    if runtime_mode != "direct_v3":
        raise InvalidStartedHypothesisAttemptError(
            "bound prompt owner context requires direct_v3 runtime"
        )
    _required_sqlite_integer(
        context["root_generation"],
        field="root_generation",
    )

    branch = _required_exact_object(
        context["branch"],
        fields=_OWNER_BRANCH_FIELDS,
        label="owner Branch",
    )
    branch_id = _required_exact_string(branch["branch_id"], field="branch_id")
    _required_sqlite_integer(branch["owner_revision"], field="Branch owner_revision")
    _required_digest(branch["storage_sha256"], field="Branch storage digest")
    state = _required_exact_string(branch["state"], field="Branch state")
    code_status = _required_exact_string(
        branch["branch_code_status"],
        field="Branch code status",
    )
    current_code_hash = _optional_digest(
        branch["current_code_hash"],
        field="Branch current code hash",
    )
    last_clean_code_hash = _optional_digest(
        branch["last_clean_code_hash"],
        field="Branch last-clean code hash",
    )
    base_champion_id = _required_sqlite_integer(
        branch["base_champion_id"],
        field="base champion ID",
    )
    base_champion_hash = _required_digest(
        branch["base_champion_hash"],
        field="base champion hash",
    )
    base_weight_revision = _required_sqlite_integer(
        branch["base_champion_weight_revision"],
        field="base champion weight revision",
    )

    h_bundle = _required_exact_object(
        context["h_bundle"],
        fields=_OWNER_H_BUNDLE_FIELDS,
        label="H bundle",
    )
    bundle_digest = _required_digest(h_bundle["digest"], field="H-bundle digest")
    if bundle_digest != projection.h_bundle_digest:
        raise InvalidStartedHypothesisAttemptError(
            "owner-context H bundle differs from the leaf prompt binding"
        )
    bundle_count = _required_sqlite_integer(h_bundle["count"], field="H-bundle count")
    items = h_bundle["items"]
    if type(items) is not list or len(items) != bundle_count:
        raise InvalidStartedHypothesisAttemptError(
            "owner-context H-bundle count differs from its items"
        )
    normalized_items: list[dict[str, Any]] = []
    previous_hypothesis_id = ""
    for item in items:
        normalized = _required_exact_object(
            item,
            fields=_OWNER_H_ITEM_FIELDS,
            label="H-bundle item",
        )
        hypothesis_id = _required_exact_string(
            normalized["hypothesis_id"],
            field="H-bundle hypothesis_id",
        )
        if previous_hypothesis_id and hypothesis_id <= previous_hypothesis_id:
            raise InvalidStartedHypothesisAttemptError(
                "owner-context H-bundle items are not unique and sorted"
            )
        _required_sqlite_integer(
            normalized["owner_revision"],
            field="H-bundle owner_revision",
        )
        _required_digest(
            normalized["storage_sha256"],
            field="H-bundle storage digest",
        )
        normalized_items.append(normalized)
        previous_hypothesis_id = hypothesis_id
    prior_head = context["prior_head"]
    if prior_head is None and normalized_items:
        raise InvalidStartedHypothesisAttemptError(
            "nonempty owner-context H bundle requires its prior head"
        )
    if prior_head is not None:
        normalized_prior = _required_exact_object(
            prior_head,
            fields=_OWNER_H_ITEM_FIELDS,
            label="prior-head",
        )
        _required_exact_string(
            normalized_prior["hypothesis_id"],
            field="prior-head hypothesis_id",
        )
        _required_sqlite_integer(
            normalized_prior["owner_revision"],
            field="prior-head owner_revision",
        )
        _required_digest(
            normalized_prior["storage_sha256"],
            field="prior-head storage digest",
        )
        if normalized_prior not in normalized_items:
            raise InvalidStartedHypothesisAttemptError(
                "owner-context prior head is absent from its H bundle"
            )

    anchors = _required_exact_object(
        context["anchors"],
        fields=_ATTEMPT_ANCHOR_FIELDS,
        label="proposal-attempt anchors",
    )
    _required_exact_string(anchors["problem_id"], field="problem_id anchor")
    for field in (
        "problem_spec_hash",
        "split_manifest_hash",
        "seed_ledger_hash",
        "champion_code_snapshot_hash",
        "branch_base_champion_hash",
    ):
        _required_digest(anchors[field], field=f"{field} anchor")
    for field in (
        "champion_version",
        "champion_weight_revision",
        "branch_base_champion_id",
    ):
        _required_sqlite_integer(anchors[field], field=f"{field} anchor")
    if (
        anchors["champion_version"] != base_champion_id
        or anchors["champion_weight_revision"] != base_weight_revision
        or anchors["branch_base_champion_id"] != base_champion_id
        or anchors["branch_base_champion_hash"] != base_champion_hash
    ):
        raise InvalidStartedHypothesisAttemptError(
            "proposal-attempt anchors differ from their owner Branch"
        )

    source_kind = projection.source_kind
    selected_manifest_digest = _required_digest(
        projection.selected_manifest_digest,
        field="selected source manifest digest",
    )
    stale = state in {"stale", "stale_weight_update"}
    if stale or current_code_hash is None or last_clean_code_hash is None:
        expected_source_kind = "base_champion"
    elif (
        code_status == "clean"
        and current_code_hash == last_clean_code_hash
    ):
        expected_source_kind = "verified_branch_workspace"
    else:
        raise InvalidStartedHypothesisAttemptError(
            "owner Branch has no authoritative hypothesis code source"
        )
    if source_kind != expected_source_kind:
        raise InvalidStartedHypothesisAttemptError(
            "leaf prompt source differs from owner-context source selection"
        )
    if (
        projection.view_identity is None
        or projection.branch_owner is None
        or projection.code_source is None
        or projection.evidence is None
        or not _required_exact_string(
            projection.reservation_id,
            field="generation reservation ID",
        )
    ):
        raise InvalidStartedHypothesisAttemptError(
            "leaf prompt projection has incomplete authority identity"
        )
    return _OwnerStartProjection(
        campaign_id=campaign_id,
        branch_id=branch_id,
        runtime_mode=runtime_mode,
        anchors=dict(anchors),
    )


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


def _decode_stored_proposal_attempt_event(
    row: object,
    *,
    authority_campaign_id: str | None = None,
) -> StoredProposalAttemptEvent:
    try:
        columns = tuple(row.keys())  # type: ignore[attr-defined]
        values = tuple(row)  # type: ignore[arg-type]
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt event is not a named materialized SQLite row"
        ) from exc
    if columns != _STARTED_EVENT_COLUMNS or len(values) != len(
        _STARTED_EVENT_COLUMNS
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
    stored_campaign_id = _required_exact_string(
        campaign_id,
        field="campaign_id",
    )
    stored_branch_id = _required_exact_string(branch_id, field="branch_id")
    if hypothesis_id is not None:
        stored_hypothesis_id = _required_exact_string(
            hypothesis_id,
            field="hypothesis_id",
        )
    else:
        stored_hypothesis_id = None
    stored_timestamp = _canonical_utc_timestamp(timestamp)
    if event_kind != _EVENT_KIND:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt event_kind is not authoritative"
        )
    if stage != _EVENT_STAGE:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt stage is not authoritative"
        )
    if (
        authority_campaign_id is not None
        and stored_campaign_id != authority_campaign_id
    ):
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
    attempt_id = _required_exact_string(
        payload.get("attempt_id"),
        field="attempt_id",
    )
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
    raw_payload = audit_payload_json
    if type(raw_payload) is not str:
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
        audit_payload_json=raw_payload,
        storage_sha256=_stored_event_storage_sha256(
            event_id=stored_event_id,
            campaign_id=stored_campaign_id,
            branch_id=stored_branch_id,
            hypothesis_id=stored_hypothesis_id,
            timestamp=stored_timestamp,
            event_kind=event_kind,
            stage=stage,
            audit_payload_json=raw_payload,
        ),
        attempt_id=attempt_id,
        status=status,
        context_digest=context_digest,
        prompt_hash=prompt_hash,
    )


def _terminal_matches_start(
    started: StoredProposalAttemptEvent,
    terminal: StoredProposalAttemptEvent,
) -> bool:
    if (
        started.status != "started"
        or terminal.status not in {"generated", "failed", "interrupted"}
        or started.event_id == terminal.event_id
        or terminal.timestamp < started.timestamp
        or started.attempt_id != terminal.attempt_id
        or started.campaign_id != terminal.campaign_id
        or started.branch_id != terminal.branch_id
        or started.context_digest != terminal.context_digest
        or started.prompt_hash != terminal.prompt_hash
        or started.hypothesis_id is not None
        or (
            terminal.status in {"failed", "interrupted"}
            and terminal.hypothesis_id is not None
        )
    ):
        return False
    started_payload = _decode_canonical_payload_json(started.audit_payload_json)
    terminal_payload = _decode_canonical_payload_json(terminal.audit_payload_json)
    for field in (
        "schema_version",
        "attempt_id",
        "campaign_id",
        "branch_id",
        "runtime_mode",
        "phase",
        "attempt_kind",
        "continuation_of_attempt_id",
        "anchors",
    ):
        if started_payload.get(field) != terminal_payload.get(field):
            return False
    started_prompt = started_payload.get("prompt_call")
    terminal_prompt = terminal_payload.get("prompt_call")
    if type(started_prompt) is not dict or type(terminal_prompt) is not dict:
        return False
    return all(
        started_prompt.get(field) == terminal_prompt.get(field)
        for field in ("request_kind", "context_digest", "prompt_hash")
    )


def _build_hypothesis_attempt_inventory(
    rows: tuple[object, ...],
    *,
    authority_campaign_id: str,
) -> _HypothesisAttemptInventory:
    grouped: dict[str, list[StoredProposalAttemptEvent]] = {}
    malformed_branches: set[str] = set()
    unattributed_malformed = False
    for row in rows:
        try:
            event = _decode_stored_proposal_attempt_event(
                row,
                authority_campaign_id=authority_campaign_id,
            )
        except InvalidStartedHypothesisAttemptError:
            try:
                values = tuple(row)  # type: ignore[arg-type]
                raw_branch_id = values[2]
                raw_campaign_id = values[1]
            except (TypeError, ValueError, IndexError):
                unattributed_malformed = True
            else:
                if (
                    type(raw_campaign_id) is str
                    and raw_campaign_id == authority_campaign_id
                    and type(raw_branch_id) is str
                    and raw_branch_id
                    and raw_branch_id == raw_branch_id.strip()
                ):
                    malformed_branches.add(raw_branch_id)
                else:
                    unattributed_malformed = True
            continue
        grouped.setdefault(event.attempt_id, []).append(event)

    groups: list[_HypothesisAttemptGroup] = []
    for attempt_id in sorted(grouped):
        events = tuple(grouped[attempt_id])
        branches = {event.branch_id for event in events}
        if len(branches) != 1:
            malformed_branches.update(branches)
            branch_id = sorted(branches)[0] if branches else ""
            disposition = _AttemptGroupDisposition.MALFORMED
        else:
            branch_id = next(iter(branches))
            started = tuple(event for event in events if event.status == "started")
            terminals = tuple(event for event in events if event.status != "started")
            if len(started) == 1 and len(terminals) == 0 and len(events) == 1:
                disposition = _AttemptGroupDisposition.UNRESOLVED
            elif (
                len(started) == 1
                and len(terminals) == 1
                and len(events) == 2
                and _terminal_matches_start(started[0], terminals[0])
            ):
                disposition = _AttemptGroupDisposition.RESOLVED
            else:
                disposition = _AttemptGroupDisposition.MALFORMED
                malformed_branches.add(branch_id)
        groups.append(
            _HypothesisAttemptGroup(
                attempt_id=attempt_id,
                branch_id=branch_id,
                events=events,
                disposition=disposition,
            )
        )
    return _HypothesisAttemptInventory(
        groups=tuple(groups),
        malformed_branch_ids=tuple(sorted(malformed_branches)),
        unattributed_malformed=unattributed_malformed,
    )


def _raise_nonfinite_json(value: str) -> None:
    raise InvalidStartedHypothesisAttemptError(
        f"started hypothesis JSON contains non-finite value {value}"
    )


def _result_columns(result: _sqlite.ImmediateResult) -> tuple[str, ...]:
    description = result.description
    if description is None:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis SELECT has no row description"
        )
    try:
        return tuple(column[0] for column in description)
    except (IndexError, TypeError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis SELECT description is malformed"
        ) from exc


def _append_stored_proposal_attempt_event_in(
    transaction: _sqlite.ImmediateTransaction,
    database_authority: _sqlite.CampaignDatabaseAuthority,
    payload: dict[str, Any],
) -> StoredProposalAttemptEvent:
    """Append one owner-built payload and strictly reread all stored bytes."""

    authority_state = _sqlite._lookup_authority_state(database_authority)
    if type(payload) is not dict:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt append requires an owner-built exact payload"
        )
    canonical_payload = _canonical_json_bytes(
        payload,
        label="proposal attempt transition",
    )
    # Validate the same bytes that will be written; this also rejects nested
    # non-finite values and unsupported transition fields before INSERT.
    normalized = _decode_canonical_payload_json(canonical_payload.decode("utf-8"))
    try:
        ProposalAttemptRecorder.validate_transition(normalized)
    except (TypeError, ValueError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt append failed the complete v1 transition schema"
        ) from exc
    if normalized.get("campaign_id") != authority_state.campaign_id:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt append belongs to another campaign"
        )
    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    expected_values: tuple[object, ...] = (
        event_id,
        normalized["campaign_id"],
        normalized["branch_id"],
        normalized.get("hypothesis_id"),
        timestamp,
        _EVENT_KIND,
        _EVENT_STAGE,
        canonical_payload.decode("utf-8"),
    )
    result = _sqlite._execute_participant(
        transaction,
        database_authority,
        _STARTED_EVENT_INSERT_SQL,
        expected_values,
    )
    if result.rowcount != 1:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt INSERT did not change exactly one row"
        )
    reread = _sqlite._execute_participant(
        transaction,
        database_authority,
        _STARTED_EVENT_SELECT_SQL,
        (event_id,),
    )
    if _result_columns(reread) != _STARTED_EVENT_COLUMNS:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt reread did not return the frozen columns"
        )
    rows = reread.fetchall()
    if len(rows) != 1:
        raise InvalidStartedHypothesisAttemptError(
            "proposal attempt INSERT did not reread one exact event"
        )
    values = tuple(rows[0])
    for column, stored_value, expected_value in zip(
        _STARTED_EVENT_COLUMNS,
        values,
        expected_values,
        strict=True,
    ):
        if (
            type(stored_value) is not type(expected_value)
            or stored_value != expected_value
        ):
            raise InvalidStartedHypothesisAttemptError(
                f"proposal attempt post-write storage differs: {column}"
            )
    return _decode_stored_proposal_attempt_event(
        rows[0],
        authority_campaign_id=authority_state.campaign_id,
    )


def _trace_persistence_error_payload(
    projection: _generation._TerminalOutcomeProjection,
) -> dict[str, str] | None:
    encoded = projection.trace_persistence_error
    if encoded is not None:
        text = _required_exact_string(encoded, field="trace persistence error")
        match = re.fullmatch(r"trace_(start|finish)_failed:([^:]+)", text)
        if match is None:
            raise InvalidStartedHypothesisAttemptError(
                "terminal trace persistence error is not authoritative"
            )
        category_stage = {
            "trace_start_failed": "start",
            "trace_finish_failed": "finish",
        }.get(projection.failure_category)
        if category_stage is not None and category_stage != match.group(1):
            raise InvalidStartedHypothesisAttemptError(
                "terminal trace persistence facts contradict each other"
            )
        return {"stage": match.group(1), "error_type": match.group(2)}
    if projection.failure_category in {"trace_start_failed", "trace_finish_failed"}:
        return {
            "stage": projection.failure_category.removeprefix("trace_").removesuffix(
                "_failed"
            ),
            "error_type": projection.failure_type,
        }
    return None


def _terminal_payload_from_start(
    started: StoredProposalAttemptEvent,
    projection: _generation._TerminalOutcomeProjection,
) -> dict[str, Any]:
    """Reconstruct one truthful v1 terminal solely from START and leaf facts."""

    if type(projection) is not _generation._TerminalOutcomeProjection:
        raise InvalidStartedHypothesisAttemptError(
            "terminal append requires the leaf terminal-outcome projection"
        )
    start_payload = _decode_canonical_payload_json(started.audit_payload_json)
    if started.status != "started" or started.hypothesis_id is not None:
        raise InvalidStartedHypothesisAttemptError(
            "terminal append requires an exact stored START"
        )
    kind = projection.kind
    if kind == "provider_interruption":
        status = "interrupted"
        transition_reason = "provider_call_interrupted"
        failure_lane = None
        if (
            projection.failure_category != "provider_call_interrupted"
            or type(projection.provider_ok) is not bool
            or projection.raw_response_ref is not None
        ):
            raise InvalidStartedHypothesisAttemptError(
                "provider interruption facts are not authoritative"
            )
    elif kind == "provider_failure":
        status = "failed"
        transition_reason = "provider_call_failed"
        failure_lane = "infra"
    elif kind == "invalid_response":
        status = "failed"
        transition_reason = "proposal_response_invalid"
        failure_lane = "invalid_response"
        if (
            projection.provider_ok is not True
            or projection.trace_ref is None
            or projection.prompt_manifest_ref is None
            or projection.raw_response_ref is None
        ):
            raise InvalidStartedHypothesisAttemptError(
                "invalid response requires successful transport and durable refs"
            )
    elif kind == "aborted_before_transport":
        status = "failed"
        transition_reason = "provider_call_cancelled_before_transport"
        failure_lane = "infra"
        if (
            projection.receipt is not None
            or projection.trace_ref is not None
            or projection.prompt_manifest_ref is not None
            or projection.raw_response_ref is not None
            or projection.provider_ok is not None
            or projection.ok is not False
            or projection.failure_category
            != "provider_call_cancelled_before_transport"
            or projection.failure_type != "AbortedHypothesisGeneration"
            or projection.trace_persistence_error is not None
        ):
            raise InvalidStartedHypothesisAttemptError(
                "pre-transport abort facts are not authoritative"
            )
    else:
        raise InvalidStartedHypothesisAttemptError(
            "terminal outcome kind is unsupported"
        )
    if projection.ok is not False:
        raise InvalidStartedHypothesisAttemptError(
            "terminal outcome requires exact ok=false"
        )
    if kind != "aborted_before_transport" and projection.receipt is None:
        raise InvalidStartedHypothesisAttemptError(
            "provider terminal outcome requires its exact receipt identity"
        )
    category = _required_exact_string(
        projection.failure_category,
        field="terminal failure category",
    )
    error_type = _required_exact_string(
        projection.failure_type,
        field="terminal failure type",
    )
    refs: list[str] = []
    for value, field in (
        (projection.trace_ref, "trace_ref"),
        (projection.prompt_manifest_ref, "prompt_manifest_ref"),
        (projection.raw_response_ref, "raw_response_ref"),
    ):
        if value is not None:
            ref = _required_exact_string(value, field=field)
            if ref not in refs:
                refs.append(ref)
    payload: dict[str, Any] = {
        "schema_version": start_payload["schema_version"],
        "attempt_id": start_payload["attempt_id"],
        "campaign_id": start_payload["campaign_id"],
        "branch_id": start_payload["branch_id"],
        "runtime_mode": start_payload["runtime_mode"],
        "phase": start_payload["phase"],
        "status": status,
        "transition_reason": transition_reason,
        "failure_lane": failure_lane,
        "hypothesis_id": None,
        "hypothesis_digest": None,
        "patch_digest": None,
        "attempt_kind": start_payload["attempt_kind"],
        "continuation_of_attempt_id": start_payload[
            "continuation_of_attempt_id"
        ],
        "prompt_call": {
            "request_kind": "hypothesis",
            "context_digest": started.context_digest,
            "prompt_hash": started.prompt_hash,
            "trace_ref": projection.trace_ref,
            "prompt_manifest_ref": projection.prompt_manifest_ref,
            "raw_response_ref": projection.raw_response_ref,
            "provider_ok": projection.provider_ok,
            "ok": False,
            "error_category": category,
            "error_type": error_type,
        },
        "anchors": start_payload["anchors"],
        "tainted_artifact_refs": refs,
    }
    if status == "interrupted":
        payload["non_resumable"] = True
    trace_error = _trace_persistence_error_payload(projection)
    if trace_error is not None:
        payload["trace_persistence_error"] = trace_error
    try:
        ProposalAttemptRecorder.validate_transition(payload)
    except (TypeError, ValueError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "rebuilt terminal event failed the complete v1 schema"
        ) from exc
    return payload


class ProposalAttemptOwner:
    """Connection-scoped participant for hypothesis attempt persistence."""

    __slots__ = (
        "__authority_campaign_id",
        "__database_authority",
        "__generation_authority",
        "__pending_starts",
        "__started_events",
        "__terminal_events",
    )

    def __init__(
        self,
        database_authority: _sqlite.CampaignDatabaseAuthority,
    ) -> None:
        authority_state = _sqlite._lookup_authority_state(database_authority)
        self.__database_authority = database_authority
        self.__authority_campaign_id = authority_state.campaign_id
        self.__generation_authority: _generation._AuthorityHandle | None = None
        self.__pending_starts: dict[int, _PendingStartedProjection] = {}
        self.__started_events: dict[
            StartedHypothesisAttempt,
            StoredProposalAttemptEvent,
        ] = {}
        self.__terminal_events: dict[
            _generation.FailedHypothesisGeneration
            | _generation.AbortedHypothesisGeneration,
            tuple[StartedHypothesisAttempt, StoredProposalAttemptEvent],
        ] = {}

    def _install_hypothesis_generation_authority(
        self,
        authority: _generation._AuthorityHandle,
    ) -> None:
        """Install this exact owner's leaf authority once during composition."""

        if self.__generation_authority is not None:
            raise _generation.HypothesisGenerationLifecycleError(
                "ProposalAttemptOwner generation authority is already installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.PROPOSAL_OWNER,
            owner=self,
        )
        self.__generation_authority = authority

    def _require_hypothesis_generation_authority(
        self,
    ) -> _generation._AuthorityHandle:
        authority = self.__generation_authority
        if authority is None:
            raise _generation.InvalidHypothesisGenerationCapabilityError(
                "ProposalAttemptOwner generation authority is not installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.PROPOSAL_OWNER,
            owner=self,
        )
        return authority

    def _load_hypothesis_attempt_inventory_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
    ) -> _HypothesisAttemptInventory:
        """Strictly read every hypothesis attempt group in one Registry snapshot."""

        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _CAMPAIGN_HYPOTHESIS_EVENTS_SELECT_SQL,
            (self.__authority_campaign_id,),
        )
        return _build_hypothesis_attempt_inventory(
            rows,
            authority_campaign_id=self.__authority_campaign_id,
        )

    def _load_hypothesis_attempt_inventory_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
    ) -> _HypothesisAttemptInventory:
        result = _sqlite._execute_participant(
            transaction,
            self.__database_authority,
            _CAMPAIGN_HYPOTHESIS_EVENTS_SELECT_SQL,
            (self.__authority_campaign_id,),
        )
        if _result_columns(result) != _STARTED_EVENT_COLUMNS:
            raise InvalidStartedHypothesisAttemptError(
                "proposal attempt inventory SELECT did not return the frozen columns"
            )
        return _build_hypothesis_attempt_inventory(
            tuple(result.fetchall()),
            authority_campaign_id=self.__authority_campaign_id,
        )

    def _require_branch_clear_for_start_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        *,
        branch_id: str,
        attempt_id: str,
    ) -> None:
        """Close natural-key and Branch-open races inside ``BEGIN IMMEDIATE``."""

        owner_branch_id = _required_exact_string(branch_id, field="branch_id")
        owner_attempt_id = _required_exact_string(attempt_id, field="attempt_id")
        inventory = self._load_hypothesis_attempt_inventory_in(transaction)
        if inventory.unattributed_malformed:
            raise InvalidStartedHypothesisAttemptError(
                "proposal attempt inventory contains unattributed malformed storage"
            )
        if any(group.attempt_id == owner_attempt_id for group in inventory.groups):
            raise InvalidStartedHypothesisAttemptError(
                "hypothesis attempt natural key already exists"
            )
        if not inventory.branch_is_clear(owner_branch_id):
            raise InvalidStartedHypothesisAttemptError(
                "Branch has an unresolved or malformed hypothesis attempt"
            )

    def append_started_hypothesis_attempt_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        bound_prompt: _generation.BoundHypothesisPrompt,
    ) -> StoredProposalAttemptEvent:
        """Claim one bound prompt and append START without issuing authority."""

        authority = self._require_hypothesis_generation_authority()
        projection = _generation._claim_bound_prompt_for_start(
            authority,
            bound_prompt,
        )
        owner = _decode_owner_start_projection(
            projection,
            authority_campaign_id=self.__authority_campaign_id,
        )
        attempt_id = str(uuid.uuid4())
        payload: dict[str, Any] = {
            "schema_version": "proposal-attempt-transition.v1",
            "attempt_id": attempt_id,
            "campaign_id": owner.campaign_id,
            "branch_id": owner.branch_id,
            "runtime_mode": owner.runtime_mode,
            "phase": "hypothesis",
            "status": "started",
            "transition_reason": "provider_call_started",
            "failure_lane": None,
            "hypothesis_id": None,
            "hypothesis_digest": None,
            "patch_digest": None,
            "attempt_kind": "initial",
            "continuation_of_attempt_id": None,
            "prompt_call": {
                "request_kind": "hypothesis",
                "context_digest": projection.context_digest,
                "prompt_hash": projection.prompt_hash,
                "trace_ref": None,
                "prompt_manifest_ref": None,
                "raw_response_ref": None,
                "provider_ok": None,
                "ok": None,
                "error_category": None,
                "error_type": None,
            },
            "anchors": owner.anchors,
            "tainted_artifact_refs": [],
        }
        self._require_branch_clear_for_start_in(
            transaction,
            branch_id=owner.branch_id,
            attempt_id=attempt_id,
        )
        stored = _append_stored_proposal_attempt_event_in(
            transaction,
            self.__database_authority,
            payload,
        )
        if (
            stored.status != "started"
            or stored.hypothesis_id is not None
            or stored.attempt_id != attempt_id
            or stored.context_digest != projection.context_digest
            or stored.prompt_hash != projection.prompt_hash
        ):
            raise InvalidStartedHypothesisAttemptError(
                "strictly reread START differs from the claimed bound prompt"
            )
        self.__pending_starts[id(stored)] = _PendingStartedProjection(
            stored=stored,
            bound_prompt=bound_prompt,
        )
        return stored

    def _classify_started_attempt_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        *,
        expected: StoredProposalAttemptEvent,
    ) -> tuple[
        ProposalAttemptCommitClassification,
        StartedHypothesisAttempt | None,
    ]:
        if type(expected) is not StoredProposalAttemptEvent:
            raise InvalidStartedHypothesisAttemptError(
                "START classification requires an exact pending stored token"
            )
        pending = self.__pending_starts.get(id(expected))
        if pending is None or pending.stored is not expected:
            raise InvalidStartedHypothesisAttemptError(
                "START token was not retained by this ProposalAttemptOwner"
            )
        classification = self._classify_started_event_from_snapshot(
            snapshot,
            expected=expected,
        )
        if classification is not ProposalAttemptCommitClassification.COMMITTED:
            return classification, None
        authority = self._require_hypothesis_generation_authority()
        started = _generation._issue_started_attempt(
            authority,
            stored_event=expected,
            attempt_id=expected.attempt_id,
            started_event_id=expected.event_id,
            campaign_id=expected.campaign_id,
            branch_id=expected.branch_id,
            context_digest=expected.context_digest,
            prompt_hash=expected.prompt_hash,
            event_storage_sha256=expected.storage_sha256,
            bound_prompt=pending.bound_prompt,
        )
        self.__started_events[started] = expected
        del self.__pending_starts[id(expected)]
        return classification, started

    def _classify_started_event_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        *,
        expected: StoredProposalAttemptEvent,
    ) -> ProposalAttemptCommitClassification:
        if type(expected) is not StoredProposalAttemptEvent:
            raise InvalidStartedHypothesisAttemptError(
                "START classification requires an exact stored event token"
            )
        inventory = self._load_hypothesis_attempt_inventory_from_snapshot(snapshot)
        matching = tuple(
            group
            for group in inventory.groups
            if group.attempt_id == expected.attempt_id
        )
        if not matching:
            if inventory.branch_is_clear(expected.branch_id):
                return ProposalAttemptCommitClassification.EXPECTED
            return ProposalAttemptCommitClassification.MIXED
        if (
            len(matching) == 1
            and matching[0].branch_id == expected.branch_id
            and matching[0].disposition is _AttemptGroupDisposition.UNRESOLVED
            and matching[0].events == (expected,)
            and expected.status == "started"
            and expected.hypothesis_id is None
            and all(
                group is matching[0]
                or group.branch_id != expected.branch_id
                or group.disposition is _AttemptGroupDisposition.RESOLVED
                for group in inventory.groups
            )
            and expected.branch_id not in inventory.malformed_branch_ids
            and not inventory.unattributed_malformed
        ):
            return ProposalAttemptCommitClassification.COMMITTED
        return ProposalAttemptCommitClassification.MIXED

    def _require_exact_start_for_terminal_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        *,
        started: StoredProposalAttemptEvent,
    ) -> None:
        inventory = self._load_hypothesis_attempt_inventory_in(transaction)
        matching = tuple(
            group
            for group in inventory.groups
            if group.attempt_id == started.attempt_id
        )
        if (
            len(matching) != 1
            or matching[0].branch_id != started.branch_id
            or matching[0].disposition is not _AttemptGroupDisposition.UNRESOLVED
            or matching[0].events != (started,)
            or inventory.unattributed_malformed
            or started.branch_id in inventory.malformed_branch_ids
            or any(
                group is not matching[0]
                and group.branch_id == started.branch_id
                and group.disposition is not _AttemptGroupDisposition.RESOLVED
                for group in inventory.groups
            )
        ):
            raise InvalidStartedHypothesisAttemptError(
                "terminal transaction does not contain the exact sole open START"
            )

    def append_terminal_hypothesis_attempt_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        *,
        started: StartedHypothesisAttempt,
        bound_prompt: _generation.BoundHypothesisPrompt,
        outcome: _generation.FailedHypothesisGeneration
        | _generation.AbortedHypothesisGeneration,
    ) -> None:
        """Consume one terminal outcome and append its strictly rebuilt event."""

        if type(started) is not StartedHypothesisAttempt:
            raise InvalidStartedHypothesisAttemptError(
                "terminal append requires an exact leaf START token"
            )
        if type(outcome) not in {
            _generation.FailedHypothesisGeneration,
            _generation.AbortedHypothesisGeneration,
        }:
            raise InvalidStartedHypothesisAttemptError(
                "terminal append requires an exact leaf terminal outcome"
            )
        stored_start = self.__started_events.get(started)
        if stored_start is None:
            raise InvalidStartedHypothesisAttemptError(
                "START token was not issued by this ProposalAttemptOwner"
            )
        if outcome in self.__terminal_events:
            raise _generation.HypothesisGenerationLifecycleError(
                "terminal outcome is already pending classification"
            )
        self._require_exact_start_for_terminal_in(
            transaction,
            started=stored_start,
        )
        authority = self._require_hypothesis_generation_authority()
        projection = _generation._claim_terminal_outcome(
            authority,
            outcome,
            started_attempt=started,
            bound_prompt=bound_prompt,
        )
        payload = _terminal_payload_from_start(stored_start, projection)
        terminal = _append_stored_proposal_attempt_event_in(
            transaction,
            self.__database_authority,
            payload,
        )
        if not _terminal_matches_start(stored_start, terminal):
            raise InvalidStartedHypothesisAttemptError(
                "strictly reread terminal does not resolve its exact START"
            )
        self.__terminal_events[outcome] = (started, terminal)

    def _classify_terminal_attempt_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        *,
        outcome: _generation.FailedHypothesisGeneration
        | _generation.AbortedHypothesisGeneration,
    ) -> tuple[
        ProposalAttemptCommitClassification,
        TerminalAttemptReceipt | None,
    ]:
        if type(outcome) not in {
            _generation.FailedHypothesisGeneration,
            _generation.AbortedHypothesisGeneration,
        }:
            raise InvalidStartedHypothesisAttemptError(
                "terminal classification requires an exact leaf terminal outcome"
            )
        pending = self.__terminal_events.get(outcome)
        if pending is None:
            raise InvalidStartedHypothesisAttemptError(
                "terminal outcome has no strong participant projection"
            )
        started, terminal = pending
        stored_start = self.__started_events.get(started)
        if stored_start is None:
            raise InvalidStartedHypothesisAttemptError(
                "terminal outcome lost its exact START projection"
            )
        classification = self._classify_terminal_event_from_snapshot(
            snapshot,
            started=stored_start,
            expected_terminal=terminal,
        )
        if classification is not ProposalAttemptCommitClassification.COMMITTED:
            return classification, None
        receipt = _generation._issue_terminal_receipt(
            self._require_hypothesis_generation_authority(),
            terminal_event=terminal,
            terminal_event_storage_sha256=terminal.storage_sha256,
            outcome=outcome,
            started_attempt=started,
        )
        return classification, receipt

    def _classify_terminal_event_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        *,
        started: StoredProposalAttemptEvent,
        expected_terminal: StoredProposalAttemptEvent,
    ) -> ProposalAttemptCommitClassification:
        if (
            type(started) is not StoredProposalAttemptEvent
            or type(expected_terminal) is not StoredProposalAttemptEvent
            or not _terminal_matches_start(started, expected_terminal)
        ):
            raise InvalidStartedHypothesisAttemptError(
                "terminal classification requires its exact START and terminal"
            )
        inventory = self._load_hypothesis_attempt_inventory_from_snapshot(snapshot)
        matching = tuple(
            group
            for group in inventory.groups
            if group.attempt_id == started.attempt_id
        )
        if (
            len(matching) == 1
            and matching[0].disposition is _AttemptGroupDisposition.UNRESOLVED
            and matching[0].events == (started,)
            and all(
                group is matching[0]
                or group.branch_id != started.branch_id
                or group.disposition is _AttemptGroupDisposition.RESOLVED
                for group in inventory.groups
            )
            and started.branch_id not in inventory.malformed_branch_ids
            and not inventory.unattributed_malformed
        ):
            return ProposalAttemptCommitClassification.EXPECTED
        if (
            len(matching) == 1
            and matching[0].disposition is _AttemptGroupDisposition.RESOLVED
            and set(matching[0].events) == {started, expected_terminal}
            and all(
                group is matching[0]
                or group.branch_id != started.branch_id
                or group.disposition is _AttemptGroupDisposition.RESOLVED
                for group in inventory.groups
            )
            and started.branch_id not in inventory.malformed_branch_ids
            and not inventory.unattributed_malformed
        ):
            return ProposalAttemptCommitClassification.COMMITTED
        return ProposalAttemptCommitClassification.MIXED
