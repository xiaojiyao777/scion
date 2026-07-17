"""Dormant connection-scoped owner for hypothesis-attempt durable semantics.

The participant owns START/terminal events, immutable generated-H bindings,
and the H-creation semantic authorizer lifecycle.  It deliberately owns
neither Campaign schema nor transaction/snapshot lifecycle, provider transport,
Branch/H stores, or production composition.  Sealed generation capabilities
live only in the leaf authority; durable owner receipts live in the generic
transaction ledger.
"""

from __future__ import annotations

import enum
import hashlib
import json
import re
import uuid
import weakref
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Final

from scion.core.proposal_pipeline.attempts import ProposalAttemptRecorder
from scion.lineage import owner_transaction as _owner
from scion.lineage import sqlite_connection as _sqlite
from scion.lineage.durable_owner import (
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
)
from scion.lineage.proposal_attempt_codec import (
    InvalidStartedHypothesisAttemptError,
    StartedHypothesisAttemptError,
    StoredProposalAttemptEvent,
    StoredProposalHypothesisBinding,
    _STARTED_EVENT_COLUMNS,
    _canonical_json_bytes,
    _decode_canonical_payload_json,
    _decode_stored_proposal_attempt_event,
    _decode_stored_proposal_hypothesis_binding,
    _EVENT_KIND,
    _EVENT_STAGE,
    _json_object,
    _raise_nonfinite_json,
    _required_digest,
    _required_exact_string,
    _required_sqlite_integer,
    proposal_hypothesis_transition_group_sha256,
)
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
    "StoredProposalHypothesisBinding",
    "TerminalAttemptReceipt",
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
_PROPOSAL_HYPOTHESIS_BINDING_INSERT_SQL: Final[str] = """
INSERT INTO proposal_hypothesis_attempt_bindings (
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
    created_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
_PROPOSAL_HYPOTHESIS_BINDING_SELECT_SQL: Final[str] = """
SELECT campaign_id,
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
       created_at
FROM proposal_hypothesis_attempt_bindings
WHERE campaign_id = ?
ORDER BY provider_attempt_id ASC
"""
_PROPOSAL_HYPOTHESIS_BINDING_SELECT_ONE_SQL: Final[str] = """
SELECT campaign_id,
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
       created_at
FROM proposal_hypothesis_attempt_bindings
WHERE campaign_id = ? AND provider_attempt_id = ?
"""
_PROPOSAL_BINDING_TABLE_PRESENT_SQL: Final[str] = """
SELECT COUNT(*) AS table_count
FROM sqlite_schema
WHERE type = 'table' AND name = 'proposal_hypothesis_attempt_bindings'
"""
_ACTIVE_EVALUATION_LEASE_PREFLIGHT_SQL: Final[str] = """
SELECT EXISTS (
    SELECT 1
    FROM candidate_evaluation_leases AS active_lease
    WHERE active_lease.state = 'active'
      AND (
          active_lease.branch_id = ?
          OR active_lease.source_hypothesis_id = ?
          OR active_lease.source_hypothesis_id IN (
              SELECT source_h.hypothesis_id
              FROM hypotheses AS source_h
              WHERE source_h.branch_id = ?
          )
      )
) AS lease_conflict
"""
_PROPOSAL_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "hypothesis_text",
        "change_locus",
        "action",
        "target_file",
        "predicted_direction",
        "target_weakness",
        "expected_effect",
        "suggested_weight",
    }
)
_OWNER_CONTEXT_SCHEMA: Final[str] = "hypothesis-owner-context-projection.v1"
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


class ProposalAttemptCommitClassification(enum.Enum):
    """Exact independent-snapshot classification for one attempted append."""

    EXPECTED = enum.auto()
    COMMITTED = enum.auto()
    MIXED = enum.auto()


class _AttemptGroupDisposition(enum.Enum):
    RESOLVED = enum.auto()
    UNRESOLVED = enum.auto()
    MALFORMED = enum.auto()


class _ProposalCreationPhase(enum.Enum):
    PENDING_AUTH = enum.auto()
    PENDING_WITNESS = enum.auto()
    STRONG_BOUND = enum.auto()
    SETTLED = enum.auto()
    DISCARDED = enum.auto()


@dataclass(frozen=True, slots=True)
class _HypothesisAttemptGroup:
    attempt_id: str
    branch_id: str
    events: tuple[StoredProposalAttemptEvent, ...]
    binding: StoredProposalHypothesisBinding | None
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


@dataclass(frozen=True, slots=True)
class _ProposalSemanticProjection:
    started: StoredProposalAttemptEvent
    generated: StoredProposalAttemptEvent | None
    binding: StoredProposalHypothesisBinding | None


@dataclass(frozen=True, slots=True)
class _PendingGeneratedCreation:
    creation_view: _generation.HypothesisCreationView | None
    result_projection: _generation._GeneratedResultProjection
    source_branch: RevisionedBranchRecord
    prior_head: RevisionedHypothesisRecord | None
    target: RevisionedHypothesisRecord


@dataclass(slots=True)
class _ProposalCreationState:
    authorization: _owner._OwnerCreationAuthorization
    transaction: _sqlite.ImmediateTransaction
    pending: _PendingGeneratedCreation | None
    expected: _ProposalSemanticProjection
    committed: _ProposalSemanticProjection
    phase: _ProposalCreationPhase = _ProposalCreationPhase.PENDING_AUTH
    witness: _owner.SemanticCreationOutcomeWitness | None = None
    classification: ProposalAttemptCommitClassification | None = None


@dataclass(frozen=True, slots=True)
class _ProposalCreationTombstone:
    phase: _ProposalCreationPhase
    witness_ref: (
        weakref.ReferenceType[_owner.SemanticCreationOutcomeWitness] | None
    ) = None


def _optional_digest(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _required_digest(value, field=field)


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
    if not _terminal_has_frozen_mapping(terminal, terminal_payload):
        return False
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


def _terminal_has_frozen_mapping(
    terminal: StoredProposalAttemptEvent,
    payload: dict[str, Any],
) -> bool:
    """Prove the fixed v1 generated/terminal semantic mapping at restore."""

    prompt = payload.get("prompt_call")
    if type(prompt) is not dict or prompt.get("request_kind") != "hypothesis":
        return False
    status = payload.get("status")
    reason = payload.get("transition_reason")
    lane = payload.get("failure_lane")
    refs = tuple(
        prompt.get(field)
        for field in ("trace_ref", "prompt_manifest_ref", "raw_response_ref")
    )
    if status == "generated":
        return (
            terminal.hypothesis_id is not None
            and reason == "generated"
            and lane is None
            and payload.get("hypothesis_id") == terminal.hypothesis_id
            and type(payload.get("hypothesis_digest")) is str
            and payload.get("patch_digest") is None
            and all(type(value) is str and value for value in refs)
            and prompt.get("provider_ok") is True
            and prompt.get("ok") is True
            and prompt.get("error_category") is None
            and prompt.get("error_type") is None
            and payload.get("tainted_artifact_refs") == []
            and "non_resumable" not in payload
        )
    if (
        terminal.hypothesis_id is not None
        or payload.get("hypothesis_id") is not None
        or payload.get("hypothesis_digest") is not None
        or payload.get("patch_digest") is not None
        or prompt.get("ok") is not False
        or type(prompt.get("error_category")) is not str
        or not prompt.get("error_category")
        or type(prompt.get("error_type")) is not str
        or not prompt.get("error_type")
    ):
        return False
    expected_refs: list[str] = []
    for value in refs:
        if value is not None:
            if type(value) is not str or not value:
                return False
            if value not in expected_refs:
                expected_refs.append(value)
    if payload.get("tainted_artifact_refs") != expected_refs:
        return False
    if reason == "provider_call_interrupted":
        return (
            status == "interrupted"
            and lane is None
            and type(prompt.get("provider_ok")) is bool
            and prompt.get("error_category") == "provider_call_interrupted"
            and refs[2] is None
            and payload.get("non_resumable") is True
        )
    if reason == "provider_call_failed":
        return (
            status == "failed"
            and lane == "infra"
            and prompt.get("provider_ok") in {None, False, True}
            and type(prompt.get("provider_ok")) in {type(None), bool}
            and "non_resumable" not in payload
        )
    if reason == "proposal_response_invalid":
        return (
            status == "failed"
            and lane == "invalid_response"
            and prompt.get("provider_ok") is True
            and all(type(value) is str and value for value in refs)
            and "non_resumable" not in payload
        )
    if reason == "hypothesis_contract_rejected":
        return (
            status == "failed"
            and lane == "invalid_response"
            and prompt.get("provider_ok") is True
            and prompt.get("error_category") == "hypothesis_contract_rejected"
            and prompt.get("error_type") == "HypothesisContractRejection"
            and all(type(value) is str and value for value in refs)
            and "non_resumable" not in payload
        )
    if reason == "provider_call_cancelled_before_transport":
        return (
            status == "failed"
            and lane == "infra"
            and refs == (None, None, None)
            and prompt.get("provider_ok") is None
            and prompt.get("error_category")
            == "provider_call_cancelled_before_transport"
            and prompt.get("error_type") == "AbortedHypothesisGeneration"
            and payload.get("tainted_artifact_refs") == []
            and "trace_persistence_error" not in payload
            and "non_resumable" not in payload
        )
    return False


def _binding_matches_generated_group(
    started: StoredProposalAttemptEvent,
    generated: StoredProposalAttemptEvent,
    binding: StoredProposalHypothesisBinding,
) -> bool:
    if (
        not _terminal_matches_start(started, generated)
        or generated.status != "generated"
        or generated.hypothesis_id is None
        or binding.campaign_id != started.campaign_id
        or binding.provider_attempt_id != started.attempt_id
        or binding.started_event_id != started.event_id
        or binding.generated_event_id != generated.event_id
        or binding.branch_id != started.branch_id
        or binding.hypothesis_id != generated.hypothesis_id
        or binding.created_at != generated.timestamp
    ):
        return False
    payload = _decode_canonical_payload_json(generated.audit_payload_json)
    proposal_digest = payload.get("hypothesis_digest")
    if binding.proposal_digest != proposal_digest:
        return False
    return binding.transition_group_sha256 == (
        proposal_hypothesis_transition_group_sha256(
            started_event_id=started.event_id,
            started_event_storage_sha256=started.storage_sha256,
            generated_event_id=generated.event_id,
            generated_event_storage_sha256=generated.storage_sha256,
        )
    )


def _build_hypothesis_attempt_inventory(
    rows: tuple[object, ...],
    *,
    authority_campaign_id: str,
    binding_rows: tuple[object, ...] | None = None,
) -> _HypothesisAttemptInventory:
    grouped: dict[str, list[StoredProposalAttemptEvent]] = {}
    bindings: dict[str, list[StoredProposalHypothesisBinding]] = {}
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

    if binding_rows is not None:
        for row in binding_rows:
            try:
                binding = _decode_stored_proposal_hypothesis_binding(
                    row,
                    authority_campaign_id=authority_campaign_id,
                )
            except InvalidStartedHypothesisAttemptError:
                try:
                    values = tuple(row)  # type: ignore[arg-type]
                    raw_campaign_id = values[0]
                    raw_branch_id = values[4]
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
            bindings.setdefault(binding.provider_attempt_id, []).append(binding)

    groups: list[_HypothesisAttemptGroup] = []
    for attempt_id in sorted(set(grouped) | set(bindings)):
        events = tuple(grouped.get(attempt_id, ()))
        attempt_bindings = tuple(bindings.get(attempt_id, ()))
        branches = {event.branch_id for event in events}
        branches.update(binding.branch_id for binding in attempt_bindings)
        selected_binding = (
            attempt_bindings[0] if len(attempt_bindings) == 1 else None
        )
        if len(branches) != 1:
            malformed_branches.update(branches)
            branch_id = sorted(branches)[0] if branches else ""
            disposition = _AttemptGroupDisposition.MALFORMED
        else:
            branch_id = next(iter(branches))
            started = tuple(event for event in events if event.status == "started")
            terminals = tuple(event for event in events if event.status != "started")
            if (
                len(started) == 1
                and len(terminals) == 0
                and len(events) == 1
                and not attempt_bindings
            ):
                disposition = _AttemptGroupDisposition.UNRESOLVED
            elif (
                len(started) == 1
                and len(terminals) == 1
                and len(events) == 2
                and _terminal_matches_start(started[0], terminals[0])
                and (
                    (
                        terminals[0].status == "generated"
                        and (
                            binding_rows is None
                            or (
                                selected_binding is not None
                                and _binding_matches_generated_group(
                                    started[0],
                                    terminals[0],
                                    selected_binding,
                                )
                            )
                        )
                    )
                    or (
                        terminals[0].status in {"failed", "interrupted"}
                        and not attempt_bindings
                    )
                )
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
                binding=selected_binding,
                disposition=disposition,
            )
        )
    return _HypothesisAttemptInventory(
        groups=tuple(groups),
        malformed_branch_ids=tuple(sorted(malformed_branches)),
        unattributed_malformed=unattributed_malformed,
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


def _append_proposal_hypothesis_binding_in(
    transaction: _sqlite.ImmediateTransaction,
    database_authority: _sqlite.CampaignDatabaseAuthority,
    *,
    started: StoredProposalAttemptEvent,
    generated: StoredProposalAttemptEvent,
    source_branch: RevisionedBranchRecord,
    parent: RevisionedHypothesisRecord | None,
    target: RevisionedHypothesisRecord,
    proposal_digest: str,
) -> StoredProposalHypothesisBinding:
    if not _terminal_matches_start(started, generated) or generated.status != "generated":
        raise InvalidStartedHypothesisAttemptError(
            "proposal binding requires one exact START/generated pair"
        )
    transition_digest = proposal_hypothesis_transition_group_sha256(
        started_event_id=started.event_id,
        started_event_storage_sha256=started.storage_sha256,
        generated_event_id=generated.event_id,
        generated_event_storage_sha256=generated.storage_sha256,
    )
    values: tuple[object, ...] = (
        started.campaign_id,
        started.attempt_id,
        started.event_id,
        generated.event_id,
        source_branch.branch_id,
        source_branch.owner_revision,
        source_branch.payload_sha256,
        target.hypothesis_id,
        None if parent is None else parent.hypothesis_id,
        None if parent is None else parent.owner_revision,
        None if parent is None else parent.payload_sha256,
        proposal_digest,
        target.payload_sha256,
        transition_digest,
        "proposal-h-binding.v1",
        generated.timestamp,
    )
    result = _sqlite._execute_participant(
        transaction,
        database_authority,
        _PROPOSAL_HYPOTHESIS_BINDING_INSERT_SQL,
        values,
    )
    if result.rowcount != 1:
        raise InvalidStartedHypothesisAttemptError(
            "proposal hypothesis binding INSERT did not change exactly one row"
        )
    reread = _sqlite._execute_participant(
        transaction,
        database_authority,
        _PROPOSAL_HYPOTHESIS_BINDING_SELECT_ONE_SQL,
        (started.campaign_id, started.attempt_id),
    )
    if _result_columns(reread) != tuple(
        StoredProposalHypothesisBinding.__dataclass_fields__
    ):
        raise InvalidStartedHypothesisAttemptError(
            "proposal hypothesis binding reread did not return frozen columns"
        )
    rows = reread.fetchall()
    if len(rows) != 1:
        raise InvalidStartedHypothesisAttemptError(
            "proposal hypothesis binding INSERT did not reread one exact row"
        )
    for column, stored_value, expected_value in zip(
        StoredProposalHypothesisBinding.__dataclass_fields__,
        tuple(rows[0]),
        values,
        strict=True,
    ):
        if type(stored_value) is not type(expected_value) or stored_value != expected_value:
            raise InvalidStartedHypothesisAttemptError(
                f"proposal hypothesis binding post-write storage differs: {column}"
            )
    binding = _decode_stored_proposal_hypothesis_binding(
        rows[0],
        authority_campaign_id=started.campaign_id,
    )
    if not _binding_matches_generated_group(started, generated, binding):
        raise InvalidStartedHypothesisAttemptError(
            "proposal hypothesis binding does not resolve its exact event group"
        )
    return binding


def _decode_generated_proposal(
    projection: _generation._GeneratedResultProjection,
) -> dict[str, Any]:
    if type(projection) is not _generation._GeneratedResultProjection:
        raise InvalidStartedHypothesisAttemptError(
            "generated H creation requires the sealed result projection"
        )
    if (
        projection.receipt is None
        or projection.provider_ok is not True
        or projection.ok is not True
        or projection.error_category is not None
        or projection.error_type is not None
    ):
        raise InvalidStartedHypothesisAttemptError(
            "generated result projection is not an exact successful receipt"
        )
    for value, field in (
        (projection.trace_ref, "trace reference"),
        (projection.prompt_manifest_ref, "prompt-manifest reference"),
        (projection.raw_response_ref, "raw-response reference"),
    ):
        _required_exact_string(value, field=field)
    raw = projection.proposal_canonical_bytes
    if type(raw) is not bytes or not raw:
        raise InvalidStartedHypothesisAttemptError(
            "generated proposal must be exact nonempty canonical bytes"
        )
    digest = _required_digest(projection.proposal_sha256, field="proposal digest")
    if hashlib.sha256(raw).hexdigest() != digest:
        raise InvalidStartedHypothesisAttemptError(
            "generated proposal bytes differ from their sealed digest"
        )
    try:
        decoded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=lambda constant: _raise_nonfinite_json(constant),
        )
    except InvalidStartedHypothesisAttemptError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "generated proposal canonical bytes are malformed"
        ) from exc
    proposal = _required_exact_object(
        decoded,
        fields=_PROPOSAL_FIELDS,
        label="generated proposal",
    )
    if _canonical_json_bytes(
        proposal,
        label="generated proposal",
        ensure_ascii=True,
    ) != raw:
        raise InvalidStartedHypothesisAttemptError(
            "generated proposal bytes are not in the frozen canonical form"
        )
    return proposal


def _generated_payload_from_exact_facts(
    started: StoredProposalAttemptEvent,
    projection: _generation._GeneratedResultProjection,
    target: RevisionedHypothesisRecord,
) -> dict[str, Any]:
    proposal = _decode_generated_proposal(projection)
    target_value = target.value()
    if target.owner_revision != 0:
        raise InvalidStartedHypothesisAttemptError(
            "generated hypothesis target must be revision zero"
        )
    if target_value.proposal_digest != projection.proposal_sha256:
        raise InvalidStartedHypothesisAttemptError(
            "target proposal digest differs from the sealed provider proposal"
        )
    for field in (
        "hypothesis_text",
        "change_locus",
        "action",
        "target_file",
        "predicted_direction",
        "suggested_weight",
    ):
        if getattr(target_value, field) != proposal[field]:
            raise InvalidStartedHypothesisAttemptError(
                f"generated target differs from sealed proposal: {field}"
            )
    start_payload = _decode_canonical_payload_json(started.audit_payload_json)
    payload: dict[str, Any] = {
        "schema_version": start_payload["schema_version"],
        "attempt_id": started.attempt_id,
        "campaign_id": started.campaign_id,
        "branch_id": started.branch_id,
        "runtime_mode": start_payload["runtime_mode"],
        "phase": start_payload["phase"],
        "status": "generated",
        "transition_reason": "generated",
        "failure_lane": None,
        "hypothesis_id": target.hypothesis_id,
        "hypothesis_digest": projection.proposal_sha256,
        "patch_digest": None,
        "attempt_kind": start_payload["attempt_kind"],
        "continuation_of_attempt_id": start_payload["continuation_of_attempt_id"],
        "prompt_call": {
            "request_kind": "hypothesis",
            "context_digest": started.context_digest,
            "prompt_hash": started.prompt_hash,
            "trace_ref": projection.trace_ref,
            "prompt_manifest_ref": projection.prompt_manifest_ref,
            "raw_response_ref": projection.raw_response_ref,
            "provider_ok": True,
            "ok": True,
            "error_category": None,
            "error_type": None,
        },
        "anchors": start_payload["anchors"],
        "tainted_artifact_refs": [],
    }
    try:
        ProposalAttemptRecorder.validate_transition(payload)
    except (TypeError, ValueError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "rebuilt generated event failed the complete v1 schema"
        ) from exc
    return payload


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
    elif kind == "hypothesis_contract_rejected":
        status = "failed"
        transition_reason = "hypothesis_contract_rejected"
        failure_lane = "invalid_response"
        if (
            projection.provider_ok is not True
            or projection.trace_ref is None
            or projection.prompt_manifest_ref is None
            or projection.raw_response_ref is None
            or projection.failure_category != "hypothesis_contract_rejected"
            or projection.failure_type != "HypothesisContractRejection"
            or projection.contract_result is None
        ):
            raise InvalidStartedHypothesisAttemptError(
                "Contract rejection requires its exact success and decision facts"
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
        "__creation_authorizer_authority",
        "__creation_states",
        "__creation_tombstones",
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
        self.__creation_authorizer_authority = (
            _owner._issue_hypothesis_creation_authorizer_authority(
                database_authority
            )
        )
        self.__creation_states: dict[
            _owner._OwnerCreationAuthorization,
            _ProposalCreationState,
        ] = {}
        self.__creation_tombstones: weakref.WeakKeyDictionary[
            _owner._OwnerCreationAuthorization,
            _ProposalCreationTombstone,
        ] = weakref.WeakKeyDictionary()
        self.__generation_authority: _generation._AuthorityHandle | None = None
        self.__pending_starts: dict[int, _PendingStartedProjection] = {}
        self.__started_events: dict[
            StartedHypothesisAttempt,
            StoredProposalAttemptEvent,
        ] = {}
        self.__terminal_events: dict[
            _generation.FailedHypothesisGeneration
            | _generation.AbortedHypothesisGeneration
            | _generation.HypothesisContractRejection,
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
        table_rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _PROPOSAL_BINDING_TABLE_PRESENT_SQL,
        )
        binding_rows: tuple[object, ...] | None = None
        if len(table_rows) != 1 or tuple(table_rows[0]) not in {(0,), (1,)}:
            raise InvalidStartedHypothesisAttemptError(
                "proposal binding table inventory is malformed"
            )
        if tuple(table_rows[0]) == (1,):
            binding_rows = _sqlite._execute_read_snapshot(
                snapshot,
                self.__database_authority,
                _PROPOSAL_HYPOTHESIS_BINDING_SELECT_SQL,
                (self.__authority_campaign_id,),
            )
        return _build_hypothesis_attempt_inventory(
            rows,
            authority_campaign_id=self.__authority_campaign_id,
            binding_rows=binding_rows,
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
        table_result = _sqlite._execute_participant(
            transaction,
            self.__database_authority,
            _PROPOSAL_BINDING_TABLE_PRESENT_SQL,
        )
        if _result_columns(table_result) != ("table_count",):
            raise InvalidStartedHypothesisAttemptError(
                "proposal binding table inventory returned unexpected columns"
            )
        table_rows = table_result.fetchall()
        if len(table_rows) != 1 or tuple(table_rows[0]) not in {(0,), (1,)}:
            raise InvalidStartedHypothesisAttemptError(
                "proposal binding table inventory is malformed"
            )
        binding_rows: tuple[object, ...] | None = None
        if tuple(table_rows[0]) == (1,):
            binding_result = _sqlite._execute_participant(
                transaction,
                self.__database_authority,
                _PROPOSAL_HYPOTHESIS_BINDING_SELECT_SQL,
                (self.__authority_campaign_id,),
            )
            if _result_columns(binding_result) != tuple(
                StoredProposalHypothesisBinding.__dataclass_fields__
            ):
                raise InvalidStartedHypothesisAttemptError(
                    "proposal binding inventory returned unexpected columns"
                )
            binding_rows = tuple(binding_result.fetchall())
        return _build_hypothesis_attempt_inventory(
            tuple(result.fetchall()),
            authority_campaign_id=self.__authority_campaign_id,
            binding_rows=binding_rows,
        )

    def _load_hypothesis_creation_inventory_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
    ) -> _HypothesisAttemptInventory:
        """Read only the fixed event/binding semantic projection."""

        event_rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _CAMPAIGN_HYPOTHESIS_EVENTS_SELECT_SQL,
            (self.__authority_campaign_id,),
        )
        binding_rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _PROPOSAL_HYPOTHESIS_BINDING_SELECT_SQL,
            (self.__authority_campaign_id,),
        )
        return _build_hypothesis_attempt_inventory(
            event_rows,
            authority_campaign_id=self.__authority_campaign_id,
            binding_rows=binding_rows,
        )

    def _load_hypothesis_creation_inventory_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
    ) -> _HypothesisAttemptInventory:
        """Read only fixed event/binding rows in the caller-owned transaction."""

        event_result = _sqlite._execute_participant(
            transaction,
            self.__database_authority,
            _CAMPAIGN_HYPOTHESIS_EVENTS_SELECT_SQL,
            (self.__authority_campaign_id,),
        )
        if _result_columns(event_result) != _STARTED_EVENT_COLUMNS:
            raise InvalidStartedHypothesisAttemptError(
                "proposal creation event inventory returned unexpected columns"
            )
        binding_result = _sqlite._execute_participant(
            transaction,
            self.__database_authority,
            _PROPOSAL_HYPOTHESIS_BINDING_SELECT_SQL,
            (self.__authority_campaign_id,),
        )
        if _result_columns(binding_result) != tuple(
            StoredProposalHypothesisBinding.__dataclass_fields__
        ):
            raise InvalidStartedHypothesisAttemptError(
                "proposal creation binding inventory returned unexpected columns"
            )
        return _build_hypothesis_attempt_inventory(
            tuple(event_result.fetchall()),
            authority_campaign_id=self.__authority_campaign_id,
            binding_rows=tuple(binding_result.fetchall()),
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

    def _require_generated_creation_preflight_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        *,
        started: StoredProposalAttemptEvent,
        target_hypothesis_id: str,
    ) -> None:
        inventory = self._load_hypothesis_creation_inventory_in(transaction)
        matching = tuple(
            group for group in inventory.groups if group.attempt_id == started.attempt_id
        )
        if (
            len(matching) != 1
            or matching[0].branch_id != started.branch_id
            or matching[0].disposition is not _AttemptGroupDisposition.UNRESOLVED
            or matching[0].events != (started,)
            or matching[0].binding is not None
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
                "generated creation requires one exact START and no terminal/binding"
            )
        lease_result = _sqlite._execute_participant(
            transaction,
            self.__database_authority,
            _ACTIVE_EVALUATION_LEASE_PREFLIGHT_SQL,
            (started.branch_id, target_hypothesis_id, started.branch_id),
        )
        if _result_columns(lease_result) != ("lease_conflict",):
            raise InvalidStartedHypothesisAttemptError(
                "evaluation-lease preflight returned unexpected columns"
            )
        rows = lease_result.fetchall()
        if (
            len(rows) != 1
            or type(rows[0][0]) is not int
            or rows[0][0] not in {0, 1}
        ):
            raise InvalidStartedHypothesisAttemptError(
                "evaluation-lease preflight returned a malformed fact"
            )
        if rows[0][0] == 1:
            raise InvalidStartedHypothesisAttemptError(
                "generated creation conflicts with an active evaluation lease"
            )

    def _register_generated_hypothesis_projection_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        ledger: _owner._OwnerReceiptLedger,
        *,
        result_projection: _generation._GeneratedResultProjection,
        source_branch: RevisionedBranchRecord,
        prior_head: RevisionedHypothesisRecord | None,
        target: RevisionedHypothesisRecord,
        creation_view: _generation.HypothesisCreationView | None = None,
    ) -> _owner._OwnerCreationAuthorization:
        """Validate semantic intent, then return its registered H authority."""

        if type(result_projection) is not _generation._GeneratedResultProjection:
            raise InvalidStartedHypothesisAttemptError(
                "generated creation requires the exact leaf result projection"
            )
        if type(source_branch) is not RevisionedBranchRecord:
            raise InvalidStartedHypothesisAttemptError(
                "generated creation requires an exact captured Branch"
            )
        if prior_head is not None and type(prior_head) is not RevisionedHypothesisRecord:
            raise InvalidStartedHypothesisAttemptError(
                "generated creation prior head must be exact or absent"
            )
        if type(target) is not RevisionedHypothesisRecord or target.owner_revision != 0:
            raise InvalidStartedHypothesisAttemptError(
                "generated creation target must be exact revision zero"
            )
        started_capability = result_projection.started_attempt
        if type(started_capability) is not StartedHypothesisAttempt:
            raise InvalidStartedHypothesisAttemptError(
                "generated result lacks its exact START authority"
            )
        started = self.__started_events.get(started_capability)
        if started is None:
            raise InvalidStartedHypothesisAttemptError(
                "generated result START was not issued by this ProposalAttemptOwner"
            )
        target_value = target.value()
        if (
            started.branch_id != source_branch.branch_id
            or target_value.branch_id != source_branch.branch_id
            or target_value.parent_hypothesis_id
            != (None if prior_head is None else prior_head.hypothesis_id)
            or (
                prior_head is not None
                and prior_head.value().branch_id != source_branch.branch_id
            )
        ):
            raise InvalidStartedHypothesisAttemptError(
                "generated Branch/parent/target projection is not exact"
            )
        _generated_payload_from_exact_facts(
            started,
            result_projection,
            target,
        )
        self._require_generated_creation_preflight_in(
            transaction,
            started=started,
            target_hypothesis_id=target.hypothesis_id,
        )
        authorization = _owner._register_hypothesis_creation_authorization(
            self.__creation_authorizer_authority,
            transaction,
            ledger,
            target.hypothesis_id,
            target.payload_sha256,
        )
        state = _ProposalCreationState(
            authorization=authorization,
            transaction=transaction,
            pending=_PendingGeneratedCreation(
                creation_view=creation_view,
                result_projection=result_projection,
                source_branch=source_branch,
                prior_head=prior_head,
                target=target,
            ),
            expected=_ProposalSemanticProjection(started, None, None),
            committed=_ProposalSemanticProjection(started, None, None),
        )
        self.__creation_states[authorization] = state
        self.__creation_tombstones[authorization] = _ProposalCreationTombstone(
            phase=_ProposalCreationPhase.PENDING_AUTH
        )
        return authorization

    def begin_generated_hypothesis_creation_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        ledger: _owner._OwnerReceiptLedger,
        creation_view: _generation.HypothesisCreationView,
        *,
        source_branch: RevisionedBranchRecord,
        prior_head: RevisionedHypothesisRecord | None,
        started_attempt: StartedHypothesisAttempt,
        target: RevisionedHypothesisRecord,
    ) -> _owner._OwnerCreationAuthorization:
        """Preflight durable facts, then claim result and register authority."""

        if type(source_branch) is not RevisionedBranchRecord or (
            prior_head is not None and type(prior_head) is not RevisionedHypothesisRecord
        ):
            raise InvalidStartedHypothesisAttemptError(
                "generated creation requires exact Branch/history tokens"
            )
        if type(started_attempt) is not StartedHypothesisAttempt:
            raise InvalidStartedHypothesisAttemptError(
                "generated creation preflight requires its exact START capability"
            )
        if type(target) is not RevisionedHypothesisRecord or target.owner_revision != 0:
            raise InvalidStartedHypothesisAttemptError(
                "generated creation preflight requires its exact revision-zero target"
            )
        stored_start = self.__started_events.get(started_attempt)
        target_value = target.value()
        if (
            stored_start is None
            or stored_start.branch_id != source_branch.branch_id
            or target_value.branch_id != source_branch.branch_id
            or target_value.parent_hypothesis_id
            != (None if prior_head is None else prior_head.hypothesis_id)
        ):
            raise InvalidStartedHypothesisAttemptError(
                "generated creation preflight facts are not exact"
            )
        self._require_generated_creation_preflight_in(
            transaction,
            started=stored_start,
            target_hypothesis_id=target.hypothesis_id,
        )
        projection = _generation._claim_generated_result_for_creation(
            self._require_hypothesis_generation_authority(),
            creation_view,
        )
        result_projection = projection.result_projection
        if type(result_projection) is not _generation._GeneratedResultProjection:
            raise InvalidStartedHypothesisAttemptError(
                "leaf creation view omitted its sealed generated-result projection"
            )
        claimed_target = projection.revision_zero_target
        if claimed_target is not target:
            raise InvalidStartedHypothesisAttemptError(
                "leaf creation view target differs from the preflight target"
            )
        if projection.started_attempt is not started_attempt:
            raise InvalidStartedHypothesisAttemptError(
                "leaf creation view START differs from the preflight START"
            )
        return self._register_generated_hypothesis_projection_in(
            transaction,
            ledger,
            result_projection=result_projection,
            source_branch=source_branch,
            prior_head=prior_head,
            target=target,
            creation_view=creation_view,
        )

    def append_generated_hypothesis_creation_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        authorization: _owner._OwnerCreationAuthorization,
    ) -> None:
        """Append exact event/binding facts for a caller-retained authority."""

        state = self.__creation_states.get(authorization)
        if (
            state is None
            or state.authorization is not authorization
            or state.transaction is not transaction
            or state.phase is not _ProposalCreationPhase.PENDING_AUTH
        ):
            raise InvalidStartedHypothesisAttemptError(
                "semantic append requires its exact pending transaction authority"
            )
        _sqlite.require_active_immediate_transaction(
            transaction,
            self.__database_authority,
        )
        pending = state.pending
        if pending is None:
            raise InvalidStartedHypothesisAttemptError(
                "semantic append lost its exact generated creation facts"
            )
        started = state.expected.started
        payload = _generated_payload_from_exact_facts(
            started,
            pending.result_projection,
            pending.target,
        )
        generated = _append_stored_proposal_attempt_event_in(
            transaction,
            self.__database_authority,
            payload,
        )
        binding = _append_proposal_hypothesis_binding_in(
            transaction,
            self.__database_authority,
            started=started,
            generated=generated,
            source_branch=pending.source_branch,
            parent=pending.prior_head,
            target=pending.target,
            proposal_digest=pending.result_projection.proposal_sha256,
        )
        state.committed = _ProposalSemanticProjection(started, generated, binding)
        state.pending = None
        state.phase = _ProposalCreationPhase.PENDING_WITNESS
        self.__creation_tombstones[authorization] = _ProposalCreationTombstone(
            phase=_ProposalCreationPhase.PENDING_WITNESS
        )

    def complete_generated_hypothesis_creation_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        ledger: _owner._OwnerReceiptLedger,
        authorization: _owner._OwnerCreationAuthorization,
        receipt: _owner.OwnerCreationReceipt,
    ) -> _owner.SemanticCreationOutcomeWitness:
        """Strong-bind exact semantic facts before completing generic H authority."""

        state = self.__creation_states.get(authorization)
        if (
            state is None
            or state.authorization is not authorization
            or state.transaction is not transaction
        ):
            raise InvalidStartedHypothesisAttemptError(
                "H creation authorization is unknown to this ProposalAttemptOwner"
            )
        if state.phase is not _ProposalCreationPhase.PENDING_WITNESS:
            raise InvalidStartedHypothesisAttemptError(
                "H creation authorization has no pending semantic witness"
            )
        inventory = self._load_hypothesis_creation_inventory_in(transaction)
        committed = state.committed
        matching = tuple(
            group
            for group in inventory.groups
            if group.attempt_id == committed.started.attempt_id
        )
        if (
            committed.generated is None
            or committed.binding is None
            or len(matching) != 1
            or matching[0].disposition is not _AttemptGroupDisposition.RESOLVED
            or matching[0].events != (committed.started, committed.generated)
            or matching[0].binding != committed.binding
            or inventory.unattributed_malformed
            or committed.started.branch_id in inventory.malformed_branch_ids
        ):
            raise InvalidStartedHypothesisAttemptError(
                "H creation semantic group differs before witness issuance"
            )
        witness = _owner._issue_hypothesis_semantic_creation_outcome_witness(
            self.__creation_authorizer_authority,
            transaction,
            ledger,
            authorization,
        )
        state.witness = witness
        state.phase = _ProposalCreationPhase.STRONG_BOUND
        self.__creation_tombstones[authorization] = _ProposalCreationTombstone(
            phase=_ProposalCreationPhase.STRONG_BOUND,
            witness_ref=weakref.ref(witness),
        )
        _owner._complete_hypothesis_creation_authorization(
            self.__creation_authorizer_authority,
            transaction,
            ledger,
            authorization,
            receipt,
            witness,
        )
        return witness

    def _require(
        self,
        witness: _owner.SemanticCreationOutcomeWitness,
        authorization: _owner._OwnerCreationAuthorization,
    ) -> None:
        state = self.__creation_states.get(authorization)
        if (
            type(witness) is not _owner.SemanticCreationOutcomeWitness
            or state is None
            or state.authorization is not authorization
            or state.phase is not _ProposalCreationPhase.STRONG_BOUND
            or state.witness is not witness
        ):
            raise InvalidStartedHypothesisAttemptError(
                "proposal semantic witness/authorization pair is not strongly bound"
            )

    def _classify(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        witness: _owner.SemanticCreationOutcomeWitness,
        authorization: _owner._OwnerCreationAuthorization,
    ) -> ProposalAttemptCommitClassification:
        self._require(witness, authorization)
        state = self.__creation_states[authorization]
        if state.classification is not None:
            return state.classification
        _sqlite._require_read_snapshot(snapshot, self.__database_authority)
        try:
            inventory = self._load_hypothesis_creation_inventory_from_snapshot(snapshot)
        except Exception:
            state.classification = ProposalAttemptCommitClassification.MIXED
            return state.classification
        expected = state.expected
        committed = state.committed
        matching = tuple(
            group
            for group in inventory.groups
            if group.attempt_id == expected.started.attempt_id
        )
        branch_is_well_formed = (
            not inventory.unattributed_malformed
            and expected.started.branch_id not in inventory.malformed_branch_ids
            and all(
                group in matching
                or group.branch_id != expected.started.branch_id
                or group.disposition is _AttemptGroupDisposition.RESOLVED
                for group in inventory.groups
            )
        )
        if (
            branch_is_well_formed
            and len(matching) == 1
            and matching[0].disposition is _AttemptGroupDisposition.UNRESOLVED
            and matching[0].events == (expected.started,)
            and matching[0].binding is None
        ):
            classification = ProposalAttemptCommitClassification.EXPECTED
        elif (
            branch_is_well_formed
            and committed.generated is not None
            and committed.binding is not None
            and len(matching) == 1
            and matching[0].disposition is _AttemptGroupDisposition.RESOLVED
            and matching[0].events == (committed.started, committed.generated)
            and matching[0].binding == committed.binding
        ):
            classification = ProposalAttemptCommitClassification.COMMITTED
        else:
            classification = ProposalAttemptCommitClassification.MIXED
        state.classification = classification
        return classification

    def _settle(
        self,
        witness: _owner.SemanticCreationOutcomeWitness,
        authorization: _owner._OwnerCreationAuthorization,
    ) -> None:
        tombstone = self.__creation_tombstones.get(authorization)
        state = self.__creation_states.get(authorization)
        if (
            state is not None
            and state.phase is _ProposalCreationPhase.SETTLED
            and state.witness is witness
            and tombstone is not None
            and tombstone.phase is _ProposalCreationPhase.SETTLED
            and tombstone.witness_ref is not None
            and tombstone.witness_ref() is witness
        ):
            self.__creation_states.pop(authorization, None)
            return
        if state is None:
            if (
                tombstone is not None
                and tombstone.phase is _ProposalCreationPhase.SETTLED
                and tombstone.witness_ref is not None
                and tombstone.witness_ref() is witness
            ):
                return
            raise InvalidStartedHypothesisAttemptError(
                "proposal semantic settlement uses an unknown or mismatched pair"
            )
        if (
            type(witness) is not _owner.SemanticCreationOutcomeWitness
            or state.authorization is not authorization
            or state.witness is not witness
            or state.phase is not _ProposalCreationPhase.STRONG_BOUND
            or state.classification
            not in {
                None,
                ProposalAttemptCommitClassification.EXPECTED,
                ProposalAttemptCommitClassification.COMMITTED,
            }
        ):
            raise InvalidStartedHypothesisAttemptError(
                "proposal semantic settlement requires one exact classified pair"
            )
        self.__creation_tombstones[authorization] = _ProposalCreationTombstone(
            phase=_ProposalCreationPhase.SETTLED,
            witness_ref=weakref.ref(witness),
        )
        state.phase = _ProposalCreationPhase.SETTLED
        self.__creation_states.pop(authorization, None)

    def _discard(
        self,
        authorization: _owner._OwnerCreationAuthorization,
    ) -> None:
        tombstone = self.__creation_tombstones.get(authorization)
        state = self.__creation_states.get(authorization)
        if (
            state is not None
            and state.phase is _ProposalCreationPhase.DISCARDED
            and tombstone is not None
            and tombstone.phase is _ProposalCreationPhase.DISCARDED
        ):
            self.__creation_states.pop(authorization, None)
            return
        if state is None:
            if (
                tombstone is not None
                and tombstone.phase is _ProposalCreationPhase.DISCARDED
            ):
                return
            raise InvalidStartedHypothesisAttemptError(
                "proposal semantic discard uses an unknown or settled authorization"
            )
        if (
            state.authorization is not authorization
            or state.phase in {
                _ProposalCreationPhase.SETTLED,
                _ProposalCreationPhase.DISCARDED,
            }
            or state.classification is ProposalAttemptCommitClassification.MIXED
        ):
            raise InvalidStartedHypothesisAttemptError(
                "proposal semantic authorization cannot be discarded"
            )
        self.__creation_tombstones[authorization] = _ProposalCreationTombstone(
            phase=_ProposalCreationPhase.DISCARDED
        )
        state.phase = _ProposalCreationPhase.DISCARDED
        self.__creation_states.pop(authorization, None)

    def _discard_pending_creation_view(
        self,
        creation_view: _generation.HypothesisCreationView,
    ) -> bool:
        """Discard an authorization hidden by a post-registration call fault."""

        if type(creation_view) is not _generation.HypothesisCreationView:
            raise InvalidStartedHypothesisAttemptError(
                "pending discard requires an exact creation view"
            )
        matching = tuple(
            authorization
            for authorization, state in self.__creation_states.items()
            if state.pending is not None
            and state.pending.creation_view is creation_view
        )
        if not matching:
            return False
        if len(matching) != 1:
            raise InvalidStartedHypothesisAttemptError(
                "creation view resolves multiple pending authorizations"
            )
        authorization = matching[0]
        state = self.__creation_states[authorization]
        if state.phase is not _ProposalCreationPhase.PENDING_AUTH:
            raise InvalidStartedHypothesisAttemptError(
                "creation-view discard found a non-pending authorization"
            )
        self._discard(authorization)
        self.__creation_tombstones.pop(authorization, None)
        return True

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
        | _generation.AbortedHypothesisGeneration
        | _generation.HypothesisContractRejection,
    ) -> None:
        """Consume one terminal outcome and append its strictly rebuilt event."""

        if type(started) is not StartedHypothesisAttempt:
            raise InvalidStartedHypothesisAttemptError(
                "terminal append requires an exact leaf START token"
            )
        if type(outcome) not in {
            _generation.FailedHypothesisGeneration,
            _generation.AbortedHypothesisGeneration,
            _generation.HypothesisContractRejection,
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
        | _generation.AbortedHypothesisGeneration
        | _generation.HypothesisContractRejection,
    ) -> tuple[
        ProposalAttemptCommitClassification,
        TerminalAttemptReceipt | None,
    ]:
        if type(outcome) not in {
            _generation.FailedHypothesisGeneration,
            _generation.AbortedHypothesisGeneration,
            _generation.HypothesisContractRejection,
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
