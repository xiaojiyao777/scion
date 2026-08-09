"""LineageRegistry — append-only experiment event storage.

Uses SQLite with WAL mode. experiment_events is INSERT-only (no UPDATE/DELETE).
record_decision writes decision info as a separate event row for the branch.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
)
from scion.core.models import (
    DecisionFeatures,
    DecisionOutcome,
    WeightOptimizationResult,
)
from scion.core.research_rejection_feedback import (
    compact_research_rejection_from_event,
)


def _with_screening_case_level_gate_aliases(event: Dict[str, Any]) -> Dict[str, Any]:
    """Keep legacy screening_case_* fields and explicit gate aliases in sync."""
    aliases = (
        ("screening_case_wins", "screening_case_level_gate_wins"),
        ("screening_case_losses", "screening_case_level_gate_losses"),
        ("screening_case_ties", "screening_case_level_gate_ties"),
        ("screening_case_total", "screening_case_level_gate_total"),
        ("screening_case_win_rate", "screening_case_level_gate_win_rate"),
    )
    updates: Dict[str, Any] = {}
    for legacy, gate_alias in aliases:
        if legacy in event and gate_alias not in event:
            updates[gate_alias] = event[legacy]
        elif gate_alias in event and legacy not in event:
            updates[legacy] = event[gate_alias]
    merged = dict(event, **updates)
    if "screening_case_total" not in merged:
        counts = (
            merged.get("screening_case_wins"),
            merged.get("screening_case_losses"),
            merged.get("screening_case_ties"),
        )
        if all(count is not None for count in counts):
            updates["screening_case_total"] = sum(int(count or 0) for count in counts)
            updates["screening_case_level_gate_total"] = updates["screening_case_total"]
    return dict(event, **updates) if updates else event


class LineageRegistry:
    _EXECUTION_OUTCOME_COLUMNS = frozenset(
        {
            "execution_outcome",
            "execution_outcome_reason_code",
            "execution_outcome_detail",
            "execution_outcome_provenance_json",
        }
    )

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Schema init
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiment_events (
                    event_id               TEXT PRIMARY KEY,
                    campaign_id            TEXT,
                    branch_id              TEXT NOT NULL,
                    hypothesis_id          TEXT,
                    timestamp              TEXT NOT NULL,
                    event_kind             TEXT DEFAULT 'experiment',
                    code_hash              TEXT,
                    patch_action           TEXT,
                    patch_file             TEXT,
                    hypothesis_text        TEXT,
                    contract_passed        TEXT,
                    verification_passed    TEXT,
                    contract_result        TEXT,
                    verification_result    TEXT,
                    canary_result          TEXT,
                    stage                  TEXT,
                    case_ids               TEXT,
                    seed_set               TEXT,
                    raw_metrics_ref        TEXT,
                    screening_n_cases      INTEGER,
                    screening_win_rate     REAL,
                    screening_win_rate_scope TEXT,
                    screening_case_wins    INTEGER,
                    screening_case_losses  INTEGER,
                    screening_case_ties    INTEGER,
                    screening_case_total   INTEGER,
                    screening_case_win_rate REAL,
                    screening_case_level_gate_wins INTEGER,
                    screening_case_level_gate_losses INTEGER,
                    screening_case_level_gate_ties INTEGER,
                    screening_case_level_gate_total INTEGER,
                    screening_case_level_gate_win_rate REAL,
                    screening_gate_win_rate REAL,
                    screening_pair_wins    INTEGER,
                    screening_pair_losses  INTEGER,
                    screening_pair_ties    INTEGER,
                    screening_pair_total   INTEGER,
                    screening_pair_win_rate REAL,
                    screening_median_delta REAL,
                    screening_ci_low       REAL,
                    screening_ci_high      REAL,
                    decision_features_json TEXT,
                    decision               TEXT,
                    decision_reason        TEXT,
                    scheduler_slot         TEXT,
                    scheduler_reason       TEXT,
                    model_id               TEXT,
                    protocol_version       TEXT,
                    prompt_tokens          INTEGER,
                    completion_tokens      INTEGER,
                    execution_outcome      TEXT,
                    execution_outcome_reason_code TEXT,
                    execution_outcome_detail TEXT,
                    execution_outcome_provenance_json TEXT,
                    audit_payload_json     TEXT,
                    created_at             TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS campaign_identity (
                    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                    campaign_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
            """)
            # Migrate existing databases: add columns that may not exist yet
            self._ensure_columns(
                conn,
                "experiment_events",
                {
                    "event_kind": "TEXT DEFAULT 'experiment'",
                    "model_id": "TEXT",
                    "protocol_version": "TEXT",
                    "prompt_tokens": "INTEGER",
                    "completion_tokens": "INTEGER",
                    "audit_payload_json": "TEXT",
                    "execution_outcome": "TEXT",
                    "execution_outcome_reason_code": "TEXT",
                    "execution_outcome_detail": "TEXT",
                    "execution_outcome_provenance_json": "TEXT",
                    "contract_diagnostics_json": "TEXT",
                    "screening_win_rate_scope": "TEXT",
                    "screening_case_wins": "INTEGER",
                    "screening_case_losses": "INTEGER",
                    "screening_case_ties": "INTEGER",
                    "screening_case_total": "INTEGER",
                    "screening_case_win_rate": "REAL",
                    "screening_case_level_gate_wins": "INTEGER",
                    "screening_case_level_gate_losses": "INTEGER",
                    "screening_case_level_gate_ties": "INTEGER",
                    "screening_case_level_gate_total": "INTEGER",
                    "screening_case_level_gate_win_rate": "REAL",
                    "screening_gate_win_rate": "REAL",
                    "screening_pair_wins": "INTEGER",
                    "screening_pair_losses": "INTEGER",
                    "screening_pair_ties": "INTEGER",
                    "screening_pair_total": "INTEGER",
                    "screening_pair_win_rate": "REAL",
                    "scheduler_slot": "TEXT",
                    "scheduler_reason": "TEXT",
                },
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS branches (
                    branch_id           TEXT PRIMARY KEY,
                    state               TEXT NOT NULL,
                    base_champion_id    INTEGER NOT NULL,
                    base_champion_hash  TEXT NOT NULL,
                    lineage_id          TEXT,
                    current_code_hash   TEXT,
                    last_clean_code_hash TEXT,
                    screening_expand_count INTEGER DEFAULT 0,
                    validation_expand_count INTEGER DEFAULT 0,
                    failure_codes       TEXT,
                    created_at          TEXT NOT NULL,
                    updated_at          TEXT NOT NULL,
                    direction           TEXT,
                    weight_revision     INTEGER DEFAULT 0,
                    branch_code_status  TEXT DEFAULT 'clean',
                    branch_evidence_summary_json TEXT,
                    infra_block_count   INTEGER DEFAULT 0
                )
            """)
            self._ensure_columns(
                conn,
                "branches",
                {
                    "screening_expand_count": "INTEGER DEFAULT 0",
                    "validation_expand_count": "INTEGER DEFAULT 0",
                    "lineage_id": "TEXT",
                    "direction": "TEXT",
                    "weight_revision": "INTEGER DEFAULT 0",
                    "branch_code_status": "TEXT DEFAULT 'clean'",
                    "branch_evidence_summary_json": "TEXT",
                    "infra_block_count": "INTEGER DEFAULT 0",
                },
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hypotheses (
                    hypothesis_id        TEXT PRIMARY KEY,
                    branch_id            TEXT,
                    change_locus         TEXT,
                    action               TEXT,
                    status               TEXT,
                    target_file          TEXT,
                    parent_hypothesis_id TEXT,
                    suggested_weight     REAL,
                    hypothesis_text      TEXT,
                    created_at           TEXT,
                    base_champion_version INTEGER DEFAULT 0,
                    family_id            TEXT,
                    family_source        TEXT,
                    taxonomy_version     TEXT,
                    predicted_direction  TEXT,
                    proposal_digest      TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS champions (
                    version                  INTEGER NOT NULL,
                    weight_revision          INTEGER NOT NULL DEFAULT 0,
                    operator_pool_json       TEXT NOT NULL,
                    solver_config_hash       TEXT NOT NULL,
                    code_snapshot_path       TEXT NOT NULL,
                    code_snapshot_hash       TEXT NOT NULL,
                    promotion_experiment_id  TEXT,
                    promotion_dossier_ref     TEXT,
                    promoted_at              TEXT,
                    PRIMARY KEY (version, weight_revision)
                )
            """)
            self._ensure_columns(
                conn,
                "champions",
                {
                    "weight_revision": "INTEGER DEFAULT 0",
                    "promotion_dossier_ref": "TEXT",
                },
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS weight_optimizations (
                    optimization_id        TEXT PRIMARY KEY,
                    campaign_id            TEXT,
                    champion_version       INTEGER NOT NULL,
                    n_operators            INTEGER NOT NULL,
                    n_evaluations          INTEGER NOT NULL,
                    baseline_score         REAL,
                    best_score             REAL,
                    improved               INTEGER,
                    baseline_weights_json  TEXT,
                    best_weights_json      TEXT,
                    elapsed_seconds        REAL,
                    observations_ref       TEXT,
                    timestamp              TEXT NOT NULL
                )
            """)
            # Migrate hypotheses table
            self._ensure_columns(
                conn,
                "hypotheses",
                {
                    "base_champion_version": "INTEGER DEFAULT 0",
                    "predicted_direction": "TEXT",
                    "proposal_digest": "TEXT",
                },
            )

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def claim_campaign_id(self, proposed_campaign_id: str) -> str:
        """Claim the database's one durable campaign identity.

        Older databases did not own this singleton.  They may be adopted only
        when their event history has zero or one distinct non-empty campaign
        identity; multiple identities are an unrecoverable ownership conflict.
        """

        proposed = str(proposed_campaign_id or "").strip()
        if not proposed:
            raise ValueError("proposed campaign identity is required")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT campaign_id FROM campaign_identity WHERE singleton_id = 1"
            ).fetchone()
            if row is not None:
                campaign_id = str(row["campaign_id"] or "").strip()
                if not campaign_id:
                    raise RuntimeError("durable campaign identity is invalid")
                conn.commit()
                return campaign_id
            existing = [
                str(item[0])
                for item in conn.execute(
                    """
                    SELECT DISTINCT campaign_id FROM experiment_events
                    WHERE campaign_id IS NOT NULL AND TRIM(campaign_id) != ''
                    ORDER BY campaign_id ASC
                    """
                ).fetchall()
            ]
            if len(existing) > 1:
                raise RuntimeError("legacy campaign identity is ambiguous")
            claimed = existing[0] if existing else proposed
            conn.execute(
                """
                INSERT INTO campaign_identity
                (singleton_id, campaign_id, created_at) VALUES (1, ?, ?)
                """,
                (claimed, datetime.now().isoformat()),
            )
            conn.commit()
            return claimed

    @staticmethod
    def _ensure_columns(
        conn: sqlite3.Connection, table: str, columns: Dict[str, str]
    ) -> None:
        """Add missing columns to an existing table (SQLite ALTER TABLE ADD COLUMN)."""
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for col, col_def in columns.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")

    # ------------------------------------------------------------------
    # Write: experiment events (INSERT only)
    # ------------------------------------------------------------------

    def record_event(self, event: Dict[str, Any]) -> str:
        """Insert one experiment row into experiment_events. Returns event_id."""
        direct_outcome_fields = sorted(
            self._EXECUTION_OUTCOME_COLUMNS.intersection(event)
        )
        if direct_outcome_fields:
            raise ValueError(
                "typed execution outcomes must be written through "
                "record_execution_outcome: " + ", ".join(direct_outcome_fields)
            )
        return self._insert_event(event)

    def _insert_event(self, event: Dict[str, Any]) -> str:
        """Low-level append used by the typed single-owner writer."""
        event = _with_screening_case_level_gate_aliases(event)
        if "event_id" not in event:
            event = dict(event, event_id=str(uuid.uuid4()))
        if "timestamp" not in event:
            event = dict(event, timestamp=datetime.now().isoformat())
        # Always stamp experiment rows so they can be filtered from decision rows
        if "event_kind" not in event:
            event = dict(event, event_kind="experiment")
        cols = ", ".join(event.keys())
        placeholders = ", ".join(["?"] * len(event))
        sql = f"INSERT INTO experiment_events ({cols}) VALUES ({placeholders})"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, list(event.values()))
        return event["event_id"]

    def record_execution_outcome(
        self,
        *,
        campaign_id: str,
        branch_id: str,
        record: ExecutionOutcomeRecord,
        hypothesis_id: Optional[str] = None,
        event_kind: str = "execution_outcome",
        stage: str = "",
        extra_fields: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Append the authoritative typed outcome event for one attempt."""
        if not isinstance(record, ExecutionOutcomeRecord):
            raise TypeError("record must be an ExecutionOutcomeRecord")
        protected = {
            "event_id",
            "timestamp",
            "event_kind",
            "campaign_id",
            "branch_id",
            "hypothesis_id",
            "stage",
            "decision",
            "decision_features_json",
            "decision_reason",
            "execution_outcome",
            "execution_outcome_reason_code",
            "execution_outcome_detail",
            "execution_outcome_provenance_json",
            "audit_payload_json",
        }
        extras = dict(extra_fields or {})
        collisions = sorted(protected.intersection(extras))
        if collisions:
            raise ValueError(
                "execution outcome extra_fields cannot override: "
                + ", ".join(collisions)
            )
        primitive = record.to_primitive()
        audit_payload = {
            "schema": "execution-outcome-event.v1",
            "execution_outcome": primitive,
        }
        event: Dict[str, Any] = {
            "campaign_id": campaign_id,
            "branch_id": branch_id,
            "hypothesis_id": hypothesis_id,
            "event_kind": event_kind,
            "stage": stage,
            "execution_outcome": primitive["outcome"],
            "execution_outcome_reason_code": primitive["reason_code"],
            "execution_outcome_detail": primitive["detail"],
            "execution_outcome_provenance_json": json.dumps(
                primitive["provenance"], sort_keys=True
            ),
            "audit_payload_json": json.dumps(audit_payload, sort_keys=True),
        }
        event.update(extras)
        return self._insert_event(event)

    def record_contract_failure(
        self,
        campaign_id: str,
        branch_id: str,
        hypothesis_text: str,
        change_locus: str,
        action: str,
        target_file: Optional[str],
        failure_reason: str,
        *,
        hypothesis_id: Optional[str] = None,
        stage: str = "hypothesis_contract",
        reason_code: str = "CONTRACT_REJECTED",
        contract_checks: Optional[List[Mapping[str, Any]]] = None,
        provenance: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Record the outer Contract's sole typed research-rejection event."""
        outcome_provenance = {
            "owner": "outer_contract",
            "stage": stage,
            "change_locus": change_locus,
            "contract_checks": list(contract_checks or ()),
        }
        supplemental_provenance = dict(provenance or {})
        protected_provenance = {
            "owner",
            "stage",
            "contract_checks",
        }.intersection(supplemental_provenance)
        if protected_provenance:
            raise ValueError(
                "contract outcome provenance cannot override: "
                + ", ".join(sorted(protected_provenance))
            )
        outcome_provenance.update(supplemental_provenance)
        record = ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code=reason_code,
            detail=failure_reason,
            provenance=outcome_provenance,
        )
        return self.record_execution_outcome(
            campaign_id=campaign_id,
            branch_id=branch_id,
            hypothesis_id=hypothesis_id,
            record=record,
            event_kind="contract_fail",
            stage=stage,
            extra_fields={
                "hypothesis_text": hypothesis_text,
                "patch_action": action,
                "patch_file": target_file or "",
                "contract_result": "failed",
                "verification_result": "skipped",
                "canary_result": "skipped",
            },
        )

    def record_decision(
        self,
        branch_id: str,
        features_json: str,
        decision: str,
        reason: str,
        *,
        campaign_id: str = "",
        hypothesis_id: str = "",
        stage: str = "",
    ) -> None:
        """Append a decision event row (INSERT only — never UPDATE)."""
        event = {
            "event_id": str(uuid.uuid4()),
            "branch_id": branch_id,
            "timestamp": datetime.now().isoformat(),
            "event_kind": "decision",
            "decision_features_json": features_json,
            "decision": decision,
            "decision_reason": reason,
        }
        if campaign_id:
            event["campaign_id"] = campaign_id
        if hypothesis_id:
            event["hypothesis_id"] = hypothesis_id
        if stage:
            event["stage"] = stage
        cols = ", ".join(event.keys())
        placeholders = ", ".join(["?"] * len(event))
        sql = f"INSERT INTO experiment_events ({cols}) VALUES ({placeholders})"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, list(event.values()))

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query_by_branch(self, branch_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM experiment_events WHERE branch_id = ? ORDER BY timestamp DESC",
                (branch_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_research_rejection_feedback(
        self,
        *,
        campaign_id: str,
    ) -> Optional[Dict[str, str]]:
        """Return the latest compact pre-Protocol rejection for the campaign."""

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT rowid, * FROM experiment_events
                WHERE campaign_id = ?
                  AND event_kind = 'research_rejection_execution_outcome'
                  AND execution_outcome = ?
                  AND stage IN (
                      'hypothesis_contract', 'patch_contract', 'verification'
                  )
                ORDER BY timestamp DESC, rowid DESC
                LIMIT 1
                """,
                (campaign_id, ExecutionOutcome.RESEARCH_REJECTED.value),
            ).fetchone()
        if row is None:
            return None
        return compact_research_rejection_from_event(dict(row))

    @staticmethod
    def _execution_outcome_from_row(row: Mapping[str, Any]) -> Dict[str, Any]:
        provenance_json = row.get("execution_outcome_provenance_json") or "{}"
        record = ExecutionOutcomeRecord.from_primitive(
            {
                "outcome": row.get("execution_outcome"),
                "reason_code": row.get("execution_outcome_reason_code"),
                "detail": row.get("execution_outcome_detail") or "",
                "provenance": json.loads(provenance_json),
            }
        )
        return {
            "event_id": row.get("event_id"),
            "campaign_id": row.get("campaign_id"),
            "branch_id": row.get("branch_id"),
            "hypothesis_id": row.get("hypothesis_id"),
            "timestamp": row.get("timestamp"),
            "event_kind": row.get("event_kind"),
            "stage": row.get("stage"),
            **record.to_primitive(),
        }

    def get_latest_execution_outcome(
        self,
        *,
        branch_id: str,
        campaign_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the latest explicit outcome; historical NULL rows stay unknown."""
        clauses = ["branch_id = ?", "execution_outcome IS NOT NULL"]
        params: List[Any] = [branch_id]
        if campaign_id is not None:
            clauses.append("campaign_id = ?")
            params.append(campaign_id)
        sql = (
            "SELECT rowid, * FROM experiment_events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY timestamp DESC, rowid DESC LIMIT 1"
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(sql, params).fetchone()
        if row is None:
            return None
        return self._execution_outcome_from_row(dict(row))

    def query_execution_outcomes(
        self,
        *,
        campaign_id: Optional[str] = None,
        branch_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query explicit typed outcomes without interpreting historical rows."""
        clauses = ["execution_outcome IS NOT NULL"]
        params: List[Any] = []
        if campaign_id is not None:
            clauses.append("campaign_id = ?")
            params.append(campaign_id)
        if branch_id is not None:
            clauses.append("branch_id = ?")
            params.append(branch_id)
        sql = (
            "SELECT rowid, * FROM experiment_events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY timestamp DESC, rowid DESC"
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [self._execution_outcome_from_row(dict(row)) for row in rows]

    def rebuild_latest_execution_outcomes(
        self,
        *,
        campaign_id: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Rebuild the per-branch latest typed projection from append-only rows."""
        clauses = ["execution_outcome IS NOT NULL"]
        params: List[Any] = []
        if campaign_id is not None:
            clauses.append("campaign_id = ?")
            params.append(campaign_id)
        sql = (
            "SELECT rowid, * FROM experiment_events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY timestamp ASC, rowid ASC"
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        latest: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            projected = self._execution_outcome_from_row(dict(row))
            latest[str(projected["branch_id"])] = projected
        return latest

    def query_failures(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return legacy and typed Contract/Verification failure events.

        If category is given, filter after projecting typed failed-check codes.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM experiment_events
                WHERE contract_result = 'failed'
                   OR verification_result = 'failed'
                   OR event_kind IN ('contract_fail', 'verification_fail')
                ORDER BY timestamp DESC
                """)
            failures = [
                self._failure_event_from_row(dict(row)) for row in cursor.fetchall()
            ]
        if category is None:
            return failures
        return [
            row
            for row in failures
            if category
            in {
                row.get("contract_result"),
                row.get("verification_result"),
                row.get("failure_code"),
                row.get("failure_detail"),
            }
        ]

    @staticmethod
    def _failure_event_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """Project typed rejection rows onto explicit failure report fields."""

        event_kind = str(row.get("event_kind") or "")
        if event_kind == "verification_fail":
            row.setdefault("verification_result", None)
            row["verification_result"] = row["verification_result"] or "failed"
            failed_check = LineageRegistry._verification_failed_check(row)
            row["failed_check"] = failed_check or None
            row["failure_code"] = (
                failed_check
                or row.get("execution_outcome_reason_code")
                or "verification_failed"
            )
            row["failure_detail"] = (
                failed_check
                or row.get("execution_outcome_detail")
                or row["failure_code"]
            )
        elif event_kind == "contract_fail":
            row.setdefault("contract_result", None)
            row["contract_result"] = row["contract_result"] or "failed"
            row["failure_code"] = (
                row.get("execution_outcome_reason_code") or "contract_failed"
            )
            row["failure_detail"] = (
                row.get("execution_outcome_detail")
                or row["failure_code"]
            )
        else:
            row["failure_code"] = row.get("decision_reason") or "legacy_failure"
            row["failure_detail"] = row.get("decision_reason") or row["failure_code"]
        return row

    @staticmethod
    def _verification_failed_check(row: Mapping[str, Any]) -> str:
        """Return the first typed failed-check name, tolerating corrupt history."""

        provenance_json = row.get("execution_outcome_provenance_json") or "{}"
        try:
            provenance = json.loads(str(provenance_json))
        except (TypeError, ValueError, json.JSONDecodeError):
            provenance = {}
        if isinstance(provenance, Mapping):
            checks = provenance.get("verification_checks", ())
            if isinstance(checks, list):
                for check in checks:
                    if (
                        not isinstance(check, Mapping)
                        or check.get("passed") is not False
                    ):
                        continue
                    name = check.get("name")
                    if isinstance(name, str) and name.strip():
                        return name.strip()
        return ""

    def get_campaign_summary(self) -> Dict[str, Any]:
        """Return aggregate stats across all recorded events."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM experiment_events WHERE event_kind = 'experiment'"
            ).fetchone()[0]
            by_decision = {}
            for row in conn.execute(
                "SELECT decision, COUNT(*) FROM experiment_events "
                "WHERE event_kind = 'experiment' AND decision IS NOT NULL GROUP BY decision"
            ).fetchall():
                by_decision[row[0]] = row[1]
            n_branches = conn.execute(
                "SELECT COUNT(DISTINCT branch_id) FROM experiment_events "
                "WHERE event_kind = 'experiment'"
            ).fetchone()[0]
            n_champions = conn.execute("SELECT COUNT(*) FROM champions").fetchone()[0]
            contract_failures = conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE (event_kind = 'experiment' AND contract_result = 'failed') "
                "OR event_kind = 'contract_fail'"
            ).fetchone()[0]
            verification_failures = conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE (event_kind = 'experiment' AND verification_result = 'failed') "
                "OR event_kind = 'verification_fail'"
            ).fetchone()[0]
            gate_outcome_events = conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE event_kind IN ('experiment', 'contract_fail', 'verification_fail')"
            ).fetchone()[0]
            contract_gate_outcome_events = gate_outcome_events
            verification_gate_outcome_events = conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE event_kind = 'verification_fail' "
                "OR (event_kind = 'experiment' "
                "AND COALESCE(contract_result, '') != 'failed')"
            ).fetchone()[0]
            screening = conn.execute("""
                SELECT
                    COALESCE(
                        SUM(
                            COALESCE(
                                screening_case_level_gate_total,
                                screening_case_total,
                                screening_n_cases
                            )
                        ),
                        0
                    ) AS case_total,
                    COALESCE(
                        SUM(
                            COALESCE(
                                screening_case_level_gate_wins,
                                screening_case_wins,
                                ROUND(screening_win_rate * screening_n_cases)
                            )
                        ),
                        0
                    ) AS case_wins,
                    COALESCE(
                        SUM(
                            COALESCE(
                                screening_case_level_gate_losses,
                                screening_case_losses
                            )
                        ),
                        0
                    ) AS case_losses,
                    COALESCE(
                        SUM(
                            COALESCE(
                                screening_case_level_gate_ties,
                                screening_case_ties
                            )
                        ),
                        0
                    ) AS case_ties,
                    COALESCE(SUM(screening_pair_wins), 0) AS pair_wins,
                    COALESCE(SUM(screening_pair_losses), 0) AS pair_losses,
                    COALESCE(SUM(screening_pair_ties), 0) AS pair_ties,
                    COALESCE(SUM(screening_pair_total), 0) AS pair_total
                FROM experiment_events
                WHERE event_kind = 'experiment' AND stage = 'screening'
            """).fetchone()
            screening_case_total = int(screening[0] or 0)
            screening_case_wins = int(screening[1] or 0)
            screening_case_losses = int(screening[2] or 0)
            screening_case_ties = int(screening[3] or 0)
            screening_pair_wins = int(screening[4] or 0)
            screening_pair_losses = int(screening[5] or 0)
            screening_pair_ties = int(screening[6] or 0)
            screening_pair_total = int(screening[7] or 0)
            screening_case_win_rate = (
                screening_case_wins / screening_case_total
                if screening_case_total
                else 0.0
            )
            screening_pair_win_rate = (
                screening_pair_wins / screening_pair_total
                if screening_pair_total
                else 0.0
            )
        return {
            "total_events": total,
            "by_decision": by_decision,
            "n_branches": n_branches,
            "n_champions": n_champions,
            "contract_failures": contract_failures,
            "verification_failures": verification_failures,
            "gate_outcome_events": gate_outcome_events,
            "contract_gate_outcome_events": contract_gate_outcome_events,
            "verification_gate_outcome_events": verification_gate_outcome_events,
            "screening_win_rate": screening_case_win_rate,
            "screening_win_rate_scope": "case_level_gate",
            "screening_case_wins": screening_case_wins,
            "screening_case_losses": screening_case_losses,
            "screening_case_ties": screening_case_ties,
            "screening_case_total": screening_case_total,
            "screening_case_win_rate": screening_case_win_rate,
            "screening_case_level_gate_wins": screening_case_wins,
            "screening_case_level_gate_losses": screening_case_losses,
            "screening_case_level_gate_ties": screening_case_ties,
            "screening_case_level_gate_total": screening_case_total,
            "screening_case_level_gate_win_rate": screening_case_win_rate,
            "screening_gate_win_rate": screening_case_win_rate,
            "screening_pair_wins": screening_pair_wins,
            "screening_pair_losses": screening_pair_losses,
            "screening_pair_ties": screening_pair_ties,
            "screening_pair_total": screening_pair_total,
            "screening_pair_win_rate": screening_pair_win_rate,
        }

    # ------------------------------------------------------------------
    # W8: Lineage-derived failure summary v2
    # ------------------------------------------------------------------

    def get_failure_summary_v2(self) -> Dict[str, Any]:
        """Derive structured failure summary from lineage events.

        Returns:
            {
                "by_stage": {"contract": N, "verification": N, ...},
                "by_decision": {"abandon": N, "discard": N, ...},
                "by_family": {"family_id": {"total": N, "failed": N}, ...},
                "recent_failures": [all failure events as dicts, newest first],
            }
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            by_stage: Dict[str, int] = {}
            for row in conn.execute("""
                SELECT
                    CASE
                        WHEN contract_result = 'failed' THEN 'contract'
                        WHEN verification_result = 'failed' THEN 'verification'
                        ELSE 'other'
                    END as fail_stage,
                    COUNT(*) as cnt
                FROM experiment_events
                WHERE event_kind = 'experiment'
                  AND (contract_result = 'failed' OR verification_result = 'failed')
                GROUP BY 1
            """).fetchall():
                by_stage[row["fail_stage"]] = row["cnt"]

            by_decision: Dict[str, int] = {}
            for row in conn.execute("""
                SELECT decision, COUNT(*) as cnt
                FROM experiment_events
                WHERE event_kind = 'experiment' AND decision IS NOT NULL
                GROUP BY decision
            """).fetchall():
                by_decision[row["decision"]] = row["cnt"]

            # Family-level failure stats (joined with hypotheses table)
            by_family: Dict[str, Dict[str, int]] = {}
            for row in conn.execute("""
                SELECT
                    h.family_id,
                    COUNT(*) as total,
                    SUM(CASE WHEN h.status IN ('rejected', 'abandoned', 'blacklisted') THEN 1 ELSE 0 END) as failed
                FROM hypotheses h
                WHERE h.family_id IS NOT NULL
                GROUP BY h.family_id
            """).fetchall():
                by_family[row["family_id"]] = {
                    "total": row["total"],
                    "failed": row["failed"],
                }

            recent = [dict(r) for r in conn.execute("""
                SELECT branch_id, hypothesis_id, contract_result, verification_result,
                       decision, timestamp
                FROM experiment_events
                WHERE event_kind = 'experiment'
                  AND (contract_result = 'failed' OR verification_result = 'failed')
                ORDER BY timestamp DESC
            """).fetchall()]

        return {
            "by_stage": by_stage,
            "by_decision": by_decision,
            "by_family": by_family,
            "recent_failures": recent,
        }

    # ------------------------------------------------------------------
    # Weight optimization lineage (T17a)
    # ------------------------------------------------------------------

    def record_weight_optimization(
        self,
        campaign_id: str,
        champion_version: int,
        result: WeightOptimizationResult,
    ) -> str:
        """Record a weight optimization result. Returns optimization_id."""
        import json as _json

        opt_id = str(uuid.uuid4())
        row = {
            "optimization_id": opt_id,
            "campaign_id": campaign_id,
            "champion_version": champion_version,
            "n_operators": len(result.best_weights),
            "n_evaluations": result.n_evaluations,
            "baseline_score": result.baseline_score,
            "best_score": result.best_score,
            "improved": 1 if result.improved else 0,
            "baseline_weights_json": _json.dumps(result.baseline_weights),
            "best_weights_json": _json.dumps(result.best_weights),
            "elapsed_seconds": result.elapsed_seconds,
            "observations_ref": result.observations_ref,
            "timestamp": datetime.now().isoformat(),
        }
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        sql = f"INSERT INTO weight_optimizations ({cols}) VALUES ({placeholders})"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, list(row.values()))
        return opt_id

    def query_weight_optimizations(
        self,
        campaign_id: Optional[str] = None,
        champion_version: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query weight optimization records."""
        sql = "SELECT * FROM weight_optimizations WHERE 1=1"
        params: List[Any] = []
        if campaign_id:
            sql += " AND campaign_id = ?"
            params.append(campaign_id)
        if champion_version is not None:
            sql += " AND champion_version = ?"
            params.append(champion_version)
        sql += " ORDER BY timestamp"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
