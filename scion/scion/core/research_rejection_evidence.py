"""Typed evidence projection for committed pre-Protocol research rejection."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Any

from scion.core.execution_outcome import ExecutionOutcomeRecord


RESEARCH_REJECTION_EVENT_SCHEMA = "research-rejection-completion-event.v1"


def upsert_and_validate_research_rejection_event(
    conn: sqlite3.Connection,
    intent: Any,
) -> None:
    """Write or audit the exact standard event projection for one intent."""

    outcome = ExecutionOutcomeRecord.from_primitive(
        intent.payload["typed_execution_outcome"]
    )
    event_id = f"research-rejection-completion:{intent.completion_id}"
    event_kind = (
        "verification_fail"
        if intent.rejection_phase == "verification"
        else "contract_fail"
    )
    candidate = intent.payload.get("rejected_candidate") or {}
    completion_payload = {
        "schema_version": RESEARCH_REJECTION_EVENT_SCHEMA,
        "completion_id": intent.completion_id,
        "intent_sha256": _stable_digest(intent.payload),
        "provider_attempt": intent.payload["provider_attempt"],
        "rejection_phase": intent.rejection_phase,
        "reason_code": intent.payload["reason_code"],
        "failed_check": intent.payload["failed_check"],
        "diagnostic_metadata": intent.payload["diagnostic_metadata"],
        "clean_code_parent": intent.payload["clean_code_parent"],
        "rejected_candidate": intent.payload["rejected_candidate"],
        "archive_ref": intent.payload["archive_ref"],
        "workspace_disposition": intent.workspace_disposition,
        "target_branch_state": intent.payload["target_branch_state"],
        "intent_ref": {
            "table": "research_rejection_completion_intents",
            "completion_id": intent.completion_id,
        },
    }
    audit_payload = {
        "schema": "execution-outcome-event.v1",
        "execution_outcome": outcome.to_primitive(),
        "research_rejection_completion": completion_payload,
    }
    proposal = intent.payload["diagnostic_metadata"].get("proposal") or {}
    contract_result = (
        "passed" if intent.rejection_phase == "verification" else "failed"
    )
    verification_result = (
        "failed" if intent.rejection_phase == "verification" else "skipped"
    )
    projected = (
        event_id,
        intent.campaign_id,
        intent.branch_id,
        intent.hypothesis_id,
        event_kind,
        candidate.get("code_hash"),
        str(proposal.get("hypothesis_text") or ""),
        str(proposal.get("action") or ""),
        str(proposal.get("target_file") or ""),
        contract_result,
        intent.rejection_phase,
        verification_result,
        "skipped",
        outcome.outcome.value,
        outcome.reason_code,
        outcome.detail,
        _canonical_json(outcome.provenance),
        _canonical_json(audit_payload),
    )
    existing = conn.execute(
        """
        SELECT event_id, campaign_id, branch_id, hypothesis_id, event_kind,
               code_hash, hypothesis_text, patch_action, patch_file,
               contract_result, stage, verification_result, canary_result,
               execution_outcome,
               execution_outcome_reason_code, execution_outcome_detail,
               execution_outcome_provenance_json, audit_payload_json
        FROM experiment_events WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone()
    if existing is not None:
        if tuple(existing) != projected:
            raise RuntimeError("typed research rejection event identity conflict")
        return
    conn.execute(
        """
        INSERT INTO experiment_events
        (event_id, campaign_id, branch_id, hypothesis_id, timestamp, event_kind,
         code_hash, hypothesis_text, patch_action, patch_file, contract_result,
         stage, verification_result, canary_result, execution_outcome,
         execution_outcome_reason_code, execution_outcome_detail,
         execution_outcome_provenance_json, audit_payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            projected[0],
            projected[1],
            projected[2],
            projected[3],
            datetime.now().isoformat(),
            *projected[4:],
        ),
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _stable_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


__all__ = [
    "RESEARCH_REJECTION_EVENT_SCHEMA",
    "upsert_and_validate_research_rejection_event",
]
