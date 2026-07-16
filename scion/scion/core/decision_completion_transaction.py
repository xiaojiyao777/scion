"""Durable, replayable completion records for evaluated branch decisions.

The Protocol result already exists when this boundary is entered.  The store
therefore owns exactly the state that must become atomic before another
provider or Protocol call is allowed: the completed verified-candidate marker,
the post-decision branch row, and an optional terminal hypothesis status.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from scion.core.models import (
    Branch,
    BranchState,
    Decision,
    HypothesisRecord,
    ProtocolResult,
)


DECISION_COMPLETION_SCHEMA = "decision-completion-intent.v1"
LEGACY_TERMINAL_IDENTITY_SCHEMA = "legacy-terminal-candidate-identity.v1"
_VALID_STATUSES = frozenset({"prepared", "state_committed", "committed"})


@dataclass(frozen=True)
class DecisionCompletionIntent:
    transaction_id: str
    status: str
    payload: Mapping[str, Any]

    @property
    def branch_id(self) -> str:
        return str(self.payload["branch_id"])

    @property
    def hypothesis_id(self) -> str:
        return str(self.payload["hypothesis_id"])

    @property
    def decision(self) -> Decision:
        return Decision(str(self.payload["decision"]))

    @property
    def cleanup_action(self) -> str:
        return str(self.payload.get("cleanup_action") or "none")


class DecisionCompletionStore:
    """SQLite-backed typed intent store sharing Branch/H transaction scope."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        fault_hook: Callable[[str, DecisionCompletionIntent], None] | None = None,
    ) -> None:
        self.db_path = str(db_path)
        self.fault_hook = fault_hook
        self._ensure_table()

    def prepare(
        self,
        *,
        source_branch: Branch,
        target_branch: Branch,
        hypothesis_record: HypothesisRecord,
        target_hypothesis_status: str | None,
        decision: Decision,
        reason_codes: Iterable[str] | None,
        protocol_result: ProtocolResult | None,
        cleanup_action: str = "none",
    ) -> DecisionCompletionIntent:
        """Persist one immutable intent before Branch/H decision side effects."""

        if source_branch.branch_id != target_branch.branch_id:
            raise ValueError("decision completion branch identity changed")
        if cleanup_action not in {"none", "abandon_workspace"}:
            raise ValueError("unsupported decision completion cleanup action")
        hypothesis_id = hypothesis_record.hypothesis_id
        if hypothesis_record.branch_id != source_branch.branch_id:
            raise ValueError("decision completion hypothesis ownership changed")
        verified_identity = _verified_candidate_identity(
            source_branch,
            hypothesis_record,
        )
        source_payload = branch_to_payload(source_branch)
        target_payload = branch_to_payload(target_branch)
        source_hypothesis = hypothesis_to_payload(hypothesis_record)
        target_hypothesis = dict(source_hypothesis)
        if target_hypothesis_status:
            target_hypothesis["status"] = target_hypothesis_status
        protocol_identity = protocol_result_identity(protocol_result)
        payload: dict[str, Any] = {
            "schema_version": DECISION_COMPLETION_SCHEMA,
            "branch_id": source_branch.branch_id,
            "hypothesis_id": hypothesis_id,
            "verified_candidate_identity": verified_identity,
            "decision": decision.value,
            "reason_codes": _normalized_reason_codes(reason_codes),
            "protocol_identity": protocol_identity,
            "protocol_identity_sha256": _stable_digest(protocol_identity),
            "source_branch": source_payload,
            "source_branch_sha256": _stable_digest(source_payload),
            "target_branch": target_payload,
            "target_branch_sha256": _stable_digest(target_payload),
            "source_hypothesis": source_hypothesis,
            "source_hypothesis_sha256": _stable_digest(source_hypothesis),
            "target_hypothesis": target_hypothesis,
            "target_hypothesis_sha256": _stable_digest(target_hypothesis),
            "target_hypothesis_status": target_hypothesis_status,
            "cleanup_action": cleanup_action,
        }
        transaction_id = _transaction_id_for_payload(payload)
        intent_sha256 = _stable_digest(payload)
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            persisted = conn.execute(
                "SELECT * FROM branches WHERE branch_id = ?",
                (source_branch.branch_id,),
            ).fetchone()
            if (
                persisted is None
                or _stable_digest(_branch_payload_from_row(persisted))
                != payload["source_branch_sha256"]
            ):
                raise RuntimeError(
                    "decision completion source branch is not the persisted owner"
                )
            persisted_hypothesis = conn.execute(
                "SELECT * FROM hypotheses WHERE hypothesis_id = ?",
                (hypothesis_id,),
            ).fetchone()
            if (
                persisted_hypothesis is None
                or _stable_digest(_hypothesis_payload_from_row(persisted_hypothesis))
                != payload["source_hypothesis_sha256"]
            ):
                raise RuntimeError(
                    "decision completion source hypothesis is not the persisted owner"
                )
            conn.execute(
                """
                INSERT OR IGNORE INTO decision_completion_intents
                (transaction_id, schema_version, branch_id, hypothesis_id,
                 decision, intent_json, intent_sha256, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'prepared', ?, ?)
                """,
                (
                    transaction_id,
                    DECISION_COMPLETION_SCHEMA,
                    source_branch.branch_id,
                    hypothesis_id,
                    decision.value,
                    _canonical_json(payload),
                    intent_sha256,
                    now,
                    now,
                ),
            )
        intent = self.load(transaction_id)
        if intent is None or _stable_digest(intent.payload) != intent_sha256:
            raise RuntimeError("decision completion intent identity conflict")
        return intent

    def load(self, transaction_id: str) -> DecisionCompletionIntent | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM decision_completion_intents WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
        return _intent_from_row(row) if row is not None else None

    def pending(self) -> list[DecisionCompletionIntent]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM decision_completion_intents
                WHERE status != 'committed'
                ORDER BY created_at ASC, transaction_id ASC
                """
            ).fetchall()
        return [_intent_from_row(row) for row in rows]

    def verify_committed(self, transaction_id: str) -> bool:
        """Validate one current committed Decision owner without mutating it."""

        intent = self.load(transaction_id)
        if intent is None or intent.status != "committed":
            return False
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN")
            _validate_committed_state(conn, intent)
            conn.rollback()
        return True

    def commit_state(self, intent: DecisionCompletionIntent) -> None:
        """Atomically commit target Branch, terminal H status, and intent phase."""

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM decision_completion_intents WHERE transaction_id = ?",
                (intent.transaction_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("decision completion intent is unavailable")
            current = _intent_from_row(row)
            if current.payload != intent.payload:
                raise RuntimeError("decision completion intent changed")
            if current.status in {"state_committed", "committed"}:
                _validate_committed_state(conn, current)
                conn.commit()
                return
            target_branch = branch_from_payload(current.payload["target_branch"])
            source_digest = str(current.payload["source_branch_sha256"])
            target_digest = str(current.payload["target_branch_sha256"])
            branch_row = conn.execute(
                "SELECT * FROM branches WHERE branch_id = ?",
                (current.branch_id,),
            ).fetchone()
            if branch_row is None:
                raise RuntimeError("decision completion branch is unavailable")
            persisted_digest = _stable_digest(_branch_payload_from_row(branch_row))
            if persisted_digest not in {source_digest, target_digest}:
                raise RuntimeError("decision completion branch identity conflict")

            target_hypothesis_status = current.payload.get("target_hypothesis_status")
            hypothesis_row = conn.execute(
                "SELECT * FROM hypotheses WHERE hypothesis_id = ?",
                (current.hypothesis_id,),
            ).fetchone()
            if hypothesis_row is None:
                raise RuntimeError("decision completion hypothesis is unavailable")
            persisted_hypothesis_digest = _stable_digest(
                _hypothesis_payload_from_row(hypothesis_row)
            )
            if persisted_hypothesis_digest not in {
                current.payload["source_hypothesis_sha256"],
                current.payload["target_hypothesis_sha256"],
            }:
                raise RuntimeError("decision completion hypothesis identity conflict")
            if target_hypothesis_status:
                self._fault("before_hypothesis_update", current)
                conn.execute(
                    "UPDATE hypotheses SET status = ? WHERE hypothesis_id = ?",
                    (target_hypothesis_status, current.hypothesis_id),
                )
                self._fault("after_hypothesis_update", current)

            _upsert_branch(conn, target_branch)
            self._fault("after_branch_upsert", current)
            _record_typed_decision_lineage(conn, current)
            self._fault("after_typed_lineage", current)
            conn.execute(
                """
                UPDATE decision_completion_intents
                SET status = 'state_committed', updated_at = ?
                WHERE transaction_id = ?
                """,
                (datetime.now().isoformat(), current.transaction_id),
            )
            self._fault("before_state_commit", current)
            conn.commit()

    def mark_committed(self, intent: DecisionCompletionIntent) -> None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM decision_completion_intents WHERE transaction_id = ?",
                (intent.transaction_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("decision completion intent is unavailable")
            current = _intent_from_row(row)
            if current.payload != intent.payload:
                raise RuntimeError("decision completion intent changed")
            _validate_committed_state(conn, current)
            if current.status == "committed":
                return
            if current.status != "state_committed":
                raise RuntimeError("decision completion state is not committed")
            conn.execute(
                """
                UPDATE decision_completion_intents
                SET status = 'committed', updated_at = ?
                WHERE transaction_id = ?
                """,
                (datetime.now().isoformat(), intent.transaction_id),
            )

    def recover_pending(
        self,
        *,
        cleanup: Callable[[DecisionCompletionIntent], None],
    ) -> tuple[str, ...]:
        """Converge every unfinished decision before campaign branch restore."""

        recovered: list[str] = []
        for intent in self.pending():
            self.commit_state(intent)
            refreshed = self.load(intent.transaction_id)
            if refreshed is None:
                raise RuntimeError("decision completion intent disappeared")
            if refreshed.cleanup_action != "none":
                cleanup(refreshed)
            self.mark_committed(refreshed)
            recovered.append(intent.transaction_id)
        return tuple(recovered)

    def _fault(self, phase: str, intent: DecisionCompletionIntent) -> None:
        if self.fault_hook is not None:
            self.fault_hook(phase, intent)

    def _ensure_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_completion_intents (
                    transaction_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    branch_id TEXT NOT NULL,
                    hypothesis_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    intent_json TEXT NOT NULL,
                    intent_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_decision_completion_status
                ON decision_completion_intents(status, created_at)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn


def branch_to_payload(branch: Branch) -> dict[str, Any]:
    return {
        "branch_id": branch.branch_id,
        "state": branch.state.value,
        "base_champion_id": branch.base_champion_id,
        "base_champion_hash": branch.base_champion_hash,
        "lineage_id": branch.lineage_id or branch.branch_id,
        "current_code_hash": branch.current_code_hash,
        "last_clean_code_hash": branch.last_clean_code_hash,
        "screening_expand_count": branch.screening_expand_count,
        "validation_expand_count": branch.validation_expand_count,
        "failure_codes": list(branch.failure_codes or ()),
        "created_at": branch.created_at.isoformat(),
        "updated_at": branch.updated_at.isoformat(),
        "direction": branch.direction,
        "weight_revision": branch.weight_revision,
        "branch_code_status": branch.branch_code_status,
        "branch_evidence_summary": _jsonable(branch.branch_evidence_summary or {}),
        "infra_block_count": branch.infra_block_count,
    }


def branch_from_payload(payload: Mapping[str, Any]) -> Branch:
    return Branch(
        branch_id=str(payload["branch_id"]),
        state=BranchState(str(payload["state"])),
        base_champion_id=int(payload["base_champion_id"]),
        base_champion_hash=str(payload["base_champion_hash"]),
        lineage_id=str(payload.get("lineage_id") or payload["branch_id"]),
        current_code_hash=payload.get("current_code_hash"),
        last_clean_code_hash=payload.get("last_clean_code_hash"),
        screening_expand_count=int(payload.get("screening_expand_count") or 0),
        validation_expand_count=int(payload.get("validation_expand_count") or 0),
        failure_codes=list(payload.get("failure_codes") or ()),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
        direction=payload.get("direction"),
        weight_revision=int(payload.get("weight_revision") or 0),
        branch_code_status=str(payload.get("branch_code_status") or "clean"),
        branch_evidence_summary=dict(payload.get("branch_evidence_summary") or {}),
        infra_block_count=int(payload.get("infra_block_count") or 0),
    )


def hypothesis_to_payload(record: HypothesisRecord) -> dict[str, Any]:
    return {
        "hypothesis_id": record.hypothesis_id,
        "branch_id": record.branch_id,
        "change_locus": record.change_locus,
        "action": record.action,
        "status": record.status,
        "target_file": record.target_file,
        "parent_hypothesis_id": record.parent_hypothesis_id,
        "suggested_weight": record.suggested_weight,
        "hypothesis_text": record.hypothesis_text,
        "created_at": record.created_at.isoformat(),
        "base_champion_version": record.base_champion_version,
        "family_id": record.family_id,
        "family_source": record.family_source,
        "taxonomy_version": record.taxonomy_version,
        "predicted_direction": record.predicted_direction,
    }


def protocol_result_identity(
    protocol_result: ProtocolResult | None,
) -> dict[str, Any]:
    if protocol_result is None:
        return {"present": False}
    return {
        "present": True,
        "stage": _enum_value(getattr(protocol_result, "stage", "")),
        "gate_outcome": getattr(protocol_result, "gate_outcome", None),
        "reason_codes": list(getattr(protocol_result, "reason_codes", ()) or ()),
        "case_ids": list(getattr(protocol_result, "case_ids", ()) or ()),
        "seed_set": list(getattr(protocol_result, "seed_set", ()) or ()),
        "raw_metrics_ref": getattr(protocol_result, "raw_metrics_ref", None),
        "stats": _jsonable(getattr(protocol_result, "stats", None)),
    }


def _verified_candidate_identity(
    branch: Branch,
    hypothesis_record: HypothesisRecord,
) -> dict[str, Any]:
    summary = branch.branch_evidence_summary or {}
    if "verified_candidate_commit" not in summary:
        # Campaigns created before verified-candidate commits still need an
        # atomic H-terminal boundary.  Their strongest durable candidate
        # identity is the canonical H plus branch lineage and code hashes.
        # Keep all of those facts explicit; do not manufacture a typed commit.
        canonical_hypothesis = hypothesis_to_payload(hypothesis_record)
        candidate_hash = str(
            branch.current_code_hash or branch.last_clean_code_hash or ""
        )
        if not candidate_hash:
            raise RuntimeError(
                f"Branch {branch.branch_id}: legacy decision candidate hash is unavailable"
            )
        return {
            "schema_version": LEGACY_TERMINAL_IDENTITY_SCHEMA,
            "identity_kind": "legacy_branch_hypothesis",
            "hypothesis_id": hypothesis_record.hypothesis_id,
            "canonical_hypothesis_sha256": _stable_digest(canonical_hypothesis),
            "lineage_id": branch.lineage_id or branch.branch_id,
            "current_code_hash": branch.current_code_hash,
            "last_clean_code_hash": branch.last_clean_code_hash,
            # The typed lineage table has a generic code_hash column.  Project
            # the bound legacy candidate hash there without claiming a
            # verified-candidate artifact or executable snapshot exists.
            "verified_code_hash": candidate_hash,
        }
    marker = summary.get("verified_candidate_commit")
    if not isinstance(marker, Mapping):
        raise RuntimeError(
            f"Branch {branch.branch_id}: typed verified commit identity is malformed"
        )
    hypothesis_id = hypothesis_record.hypothesis_id
    if marker.get("hypothesis_id") != hypothesis_id:
        raise RuntimeError(
            f"Branch {branch.branch_id}: decision completion hypothesis mismatch"
        )
    required = (
        "schema_version",
        "artifact_ref",
        "artifact_sha256",
        "verified_code_hash",
        "executable_snapshot_hash",
        "patch_digest",
        "promotion_status",
        "evaluation_status",
    )
    identity = {key: marker.get(key) for key in required}
    if any(value in {None, ""} for value in identity.values()):
        raise RuntimeError(
            f"Branch {branch.branch_id}: verified commit identity is incomplete"
        )
    if identity["promotion_status"] != "committed":
        raise RuntimeError(
            f"Branch {branch.branch_id}: verified promotion is not committed"
        )
    if identity["evaluation_status"] not in {"pending", "completed"}:
        raise RuntimeError(
            f"Branch {branch.branch_id}: verified evaluation status is invalid"
        )
    return identity


def _upsert_branch(conn: sqlite3.Connection, branch: Branch) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO branches
        (branch_id, state, base_champion_id, base_champion_hash,
         lineage_id, current_code_hash, last_clean_code_hash,
         screening_expand_count, validation_expand_count,
         failure_codes, created_at, updated_at, direction,
         weight_revision, branch_code_status,
         branch_evidence_summary_json, infra_block_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            branch.branch_id,
            branch.state.value,
            branch.base_champion_id,
            branch.base_champion_hash,
            branch.lineage_id or branch.branch_id,
            branch.current_code_hash,
            branch.last_clean_code_hash,
            branch.screening_expand_count,
            branch.validation_expand_count,
            json.dumps(branch.failure_codes),
            branch.created_at.isoformat(),
            branch.updated_at.isoformat(),
            branch.direction,
            branch.weight_revision,
            branch.branch_code_status,
            json.dumps(dict(branch.branch_evidence_summary or {})),
            branch.infra_block_count,
        ),
    )


def _record_typed_decision_lineage(
    conn: sqlite3.Connection,
    intent: DecisionCompletionIntent,
) -> None:
    """Write the recovery-complete decision fact in the same Branch/H txn.

    Rich experiment lineage remains an append-only best-effort projection. This
    compact typed row guarantees that a crash after intent prepare cannot leave
    a completed decision with no durable lineage identity.
    """

    event_id = f"decision-completion:{intent.transaction_id}"
    protocol = intent.payload.get("protocol_identity") or {}
    verified = intent.payload["verified_candidate_identity"]
    reason_codes = list(intent.payload.get("reason_codes") or ())
    target_branch = intent.payload["target_branch"]
    target_summary = target_branch.get("branch_evidence_summary") or {}
    audit_payload = {
        "schema_version": DECISION_COMPLETION_SCHEMA,
        "transaction_id": intent.transaction_id,
        "intent_sha256": _stable_digest(intent.payload),
        "protocol_identity": protocol,
        "protocol_identity_sha256": intent.payload["protocol_identity_sha256"],
        "verified_candidate_identity": verified,
        "decision": intent.decision.value,
        "reason_codes": reason_codes,
        "target_branch": {
            "state": target_branch.get("state"),
            "sha256": intent.payload["target_branch_sha256"],
            "canonical_screening_history": target_summary.get(
                "canonical_screening_history",
                [],
            ),
        },
        "intent_ref": {
            "table": "decision_completion_intents",
            "transaction_id": intent.transaction_id,
        },
    }
    audit_payload_json = _canonical_json(audit_payload)
    values = {
        "event_id": event_id,
        "branch_id": intent.branch_id,
        "hypothesis_id": intent.hypothesis_id,
        "timestamp": datetime.now().isoformat(),
        "event_kind": "decision_completion",
        "code_hash": verified.get("verified_code_hash"),
        "stage": protocol.get("stage"),
        "case_ids": json.dumps(protocol.get("case_ids") or []),
        "seed_set": json.dumps(protocol.get("seed_set") or []),
        "raw_metrics_ref": protocol.get("raw_metrics_ref"),
        "decision": intent.decision.value,
        "decision_reason": json.dumps(reason_codes),
        "audit_payload_json": audit_payload_json,
    }
    existing = conn.execute(
        """
        SELECT branch_id, hypothesis_id, event_kind, code_hash, stage,
               decision, decision_reason, audit_payload_json
        FROM experiment_events WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone()
    if existing is not None:
        expected = (
            intent.branch_id,
            intent.hypothesis_id,
            "decision_completion",
            verified.get("verified_code_hash"),
            protocol.get("stage"),
            intent.decision.value,
            json.dumps(reason_codes),
            audit_payload_json,
        )
        if tuple(existing) != expected:
            raise RuntimeError("typed decision lineage identity conflict")
        return
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    conn.execute(
        f"INSERT INTO experiment_events ({columns}) VALUES ({placeholders})",
        tuple(values.values()),
    )


def _validate_committed_state(
    conn: sqlite3.Connection,
    intent: DecisionCompletionIntent,
) -> None:
    branch_row = conn.execute(
        "SELECT * FROM branches WHERE branch_id = ?",
        (intent.branch_id,),
    ).fetchone()
    if (
        branch_row is None
        or _stable_digest(_branch_payload_from_row(branch_row))
        != intent.payload["target_branch_sha256"]
    ):
        raise RuntimeError("committed decision branch identity conflict")
    hypothesis_row = conn.execute(
        "SELECT * FROM hypotheses WHERE hypothesis_id = ?",
        (intent.hypothesis_id,),
    ).fetchone()
    if (
        hypothesis_row is None
        or _stable_digest(_hypothesis_payload_from_row(hypothesis_row))
        != intent.payload["target_hypothesis_sha256"]
    ):
        raise RuntimeError("committed decision hypothesis identity conflict")
    event_id = f"decision-completion:{intent.transaction_id}"
    event = conn.execute(
        """
        SELECT branch_id, hypothesis_id, event_kind, code_hash, stage,
               decision, decision_reason, audit_payload_json
        FROM experiment_events WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone()
    if event is None:
        raise RuntimeError("committed typed decision lineage is unavailable")
    protocol = intent.payload["protocol_identity"]
    verified = intent.payload["verified_candidate_identity"]
    reason_codes = list(intent.payload.get("reason_codes") or ())
    target_branch = intent.payload["target_branch"]
    target_summary = target_branch.get("branch_evidence_summary") or {}
    expected_audit = _canonical_json(
        {
            "schema_version": DECISION_COMPLETION_SCHEMA,
            "transaction_id": intent.transaction_id,
            "intent_sha256": _stable_digest(intent.payload),
            "protocol_identity": protocol,
            "protocol_identity_sha256": intent.payload[
                "protocol_identity_sha256"
            ],
            "verified_candidate_identity": verified,
            "decision": intent.decision.value,
            "reason_codes": reason_codes,
            "target_branch": {
                "state": target_branch.get("state"),
                "sha256": intent.payload["target_branch_sha256"],
                "canonical_screening_history": target_summary.get(
                    "canonical_screening_history",
                    [],
                ),
            },
            "intent_ref": {
                "table": "decision_completion_intents",
                "transaction_id": intent.transaction_id,
            },
        }
    )
    expected = (
        intent.branch_id,
        intent.hypothesis_id,
        "decision_completion",
        verified.get("verified_code_hash"),
        protocol.get("stage"),
        intent.decision.value,
        json.dumps(reason_codes),
        expected_audit,
    )
    if tuple(event) != expected:
        raise RuntimeError("committed typed decision lineage identity conflict")


def _branch_payload_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return branch_to_payload(
        Branch(
            branch_id=row["branch_id"],
            state=BranchState(row["state"]),
            base_champion_id=row["base_champion_id"],
            base_champion_hash=row["base_champion_hash"],
            lineage_id=row["lineage_id"] or row["branch_id"],
            current_code_hash=row["current_code_hash"],
            last_clean_code_hash=row["last_clean_code_hash"],
            screening_expand_count=row["screening_expand_count"] or 0,
            validation_expand_count=row["validation_expand_count"] or 0,
            failure_codes=json.loads(row["failure_codes"] or "[]"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            direction=row["direction"],
            weight_revision=row["weight_revision"] or 0,
            branch_code_status=row["branch_code_status"] or "clean",
            branch_evidence_summary=json.loads(
                row["branch_evidence_summary_json"] or "{}"
            ),
            infra_block_count=row["infra_block_count"] or 0,
        )
    )


def _hypothesis_payload_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return hypothesis_to_payload(
        HypothesisRecord(
            hypothesis_id=row["hypothesis_id"],
            branch_id=row["branch_id"] or "",
            change_locus=row["change_locus"] or "",
            action=row["action"] or "modify",
            status=row["status"] or "active",
            target_file=row["target_file"],
            parent_hypothesis_id=row["parent_hypothesis_id"],
            suggested_weight=row["suggested_weight"],
            hypothesis_text=row["hypothesis_text"],
            created_at=datetime.fromisoformat(row["created_at"]),
            base_champion_version=row["base_champion_version"] or 0,
            family_id=row["family_id"],
            family_source=row["family_source"],
            taxonomy_version=row["taxonomy_version"],
            predicted_direction=row["predicted_direction"] or "exploratory",
        )
    )


def _intent_from_row(row: sqlite3.Row) -> DecisionCompletionIntent:
    payload = json.loads(row["intent_json"])
    if (
        row["schema_version"] != DECISION_COMPLETION_SCHEMA
        or not isinstance(payload, dict)
        or payload.get("schema_version") != DECISION_COMPLETION_SCHEMA
        or row["status"] not in _VALID_STATUSES
        or _stable_digest(payload) != row["intent_sha256"]
        or payload.get("branch_id") != row["branch_id"]
        or payload.get("hypothesis_id") != row["hypothesis_id"]
        or payload.get("decision") != row["decision"]
        or _stable_digest(payload.get("source_branch"))
        != payload.get("source_branch_sha256")
        or _stable_digest(payload.get("target_branch"))
        != payload.get("target_branch_sha256")
        or _stable_digest(payload.get("source_hypothesis"))
        != payload.get("source_hypothesis_sha256")
        or _stable_digest(payload.get("target_hypothesis"))
        != payload.get("target_hypothesis_sha256")
        or _stable_digest(payload.get("protocol_identity"))
        != payload.get("protocol_identity_sha256")
        or _transaction_id_for_payload(payload) != row["transaction_id"]
    ):
        raise RuntimeError("decision completion intent is invalid")
    return DecisionCompletionIntent(
        transaction_id=row["transaction_id"],
        status=row["status"],
        payload=payload,
    )


def _normalized_reason_codes(values: Iterable[str] | None) -> list[str]:
    return list(
        dict.fromkeys(str(value).strip() for value in (values or ()) if str(value).strip())
    )


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    return str(value)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))


def _stable_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _transaction_id_for_payload(payload: Mapping[str, Any]) -> str:
    verified = payload.get("verified_candidate_identity") or {}
    return _stable_digest(
        {
            "schema_version": DECISION_COMPLETION_SCHEMA,
            "branch_id": payload.get("branch_id"),
            "hypothesis_id": payload.get("hypothesis_id"),
            "source_hypothesis_sha256": payload.get("source_hypothesis_sha256"),
            "verified_artifact_sha256": verified.get("artifact_sha256"),
            "decision": payload.get("decision"),
            "protocol_identity_sha256": payload.get("protocol_identity_sha256"),
        }
    )
