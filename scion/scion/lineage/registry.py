"""LineageRegistry — append-only experiment event storage.

Uses SQLite with WAL mode. experiment_events is INSERT-only (no UPDATE/DELETE).
Each completed experiment stores its Decision in the same ordinary event row.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional

from scion.core.execution_outcome import (
    ExecutionOutcomeRecord,
)
from scion.core.models import WeightOptimizationResult

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
                    timestamp              TEXT NOT NULL,
                    event_kind             TEXT DEFAULT 'experiment',
                    code_hash              TEXT,
                    patch_action           TEXT,
                    patch_file             TEXT,
                    hypothesis_text        TEXT,
                    contract_result        TEXT,
                    contract_diagnostics_json TEXT,
                    verification_result    TEXT,
                    canary_result          TEXT,
                    stage                  TEXT,
                    case_ids               TEXT,
                    seed_set               TEXT,
                    raw_metrics_ref        TEXT,
                    screening_n_cases      INTEGER,
                    screening_case_wins    INTEGER,
                    screening_case_losses  INTEGER,
                    screening_case_ties    INTEGER,
                    screening_case_total   INTEGER,
                    screening_case_win_rate REAL,
                    screening_pair_wins    INTEGER,
                    screening_pair_losses  INTEGER,
                    screening_pair_ties    INTEGER,
                    screening_pair_total   INTEGER,
                    screening_pair_win_rate REAL,
                    screening_median_delta REAL,
                    screening_ci_low       REAL,
                    screening_ci_high      REAL,
                    decision               TEXT,
                    decision_reason        TEXT,
                    model_id               TEXT,
                    protocol_version       TEXT,
                    prompt_tokens          INTEGER,
                    completion_tokens      INTEGER,
                    execution_outcome      TEXT,
                    execution_outcome_reason_code TEXT,
                    execution_outcome_detail TEXT,
                    execution_outcome_provenance_json TEXT,
                    created_at             TEXT DEFAULT (datetime('now'))
                )
            """)
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
            "stage",
            "decision",
            "decision_reason",
            "execution_outcome",
            "execution_outcome_reason_code",
            "execution_outcome_detail",
            "execution_outcome_provenance_json",
        }
        extras = dict(extra_fields or {})
        collisions = sorted(protected.intersection(extras))
        if collisions:
            raise ValueError(
                "execution outcome extra_fields cannot override: "
                + ", ".join(collisions)
            )
        primitive = record.to_primitive()
        event: Dict[str, Any] = {
            "campaign_id": campaign_id,
            "branch_id": branch_id,
            "event_kind": event_kind,
            "stage": stage,
            "execution_outcome": primitive["outcome"],
            "execution_outcome_reason_code": primitive["reason_code"],
            "execution_outcome_detail": primitive["detail"],
            "execution_outcome_provenance_json": json.dumps(
                primitive["provenance"], sort_keys=True
            ),
        }
        event.update(extras)
        return self._insert_event(event)

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
            "timestamp": row.get("timestamp"),
            "event_kind": row.get("event_kind"),
            "stage": row.get("stage"),
            **record.to_primitive(),
        }

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

    def query_failures(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return current typed Contract/Verification rejection events."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM experiment_events
                WHERE execution_outcome IS NOT NULL
                  AND event_kind IN ('contract_fail', 'verification_fail')
                ORDER BY timestamp DESC
                """)
            failures = [
                self._execution_outcome_from_row(dict(row))
                for row in cursor.fetchall()
            ]
        if category is None:
            return failures
        return [
            row
            for row in failures
            if category
            in {
                row.get("event_kind"),
                row.get("stage"),
                row.get("outcome"),
                row.get("reason_code"),
            }
        ]

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
            contract_failures = conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE event_kind = 'contract_fail'"
            ).fetchone()[0]
            verification_failures = conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE event_kind = 'verification_fail'"
            ).fetchone()[0]
            gate_outcome_events = conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE event_kind IN ('experiment', 'contract_fail', 'verification_fail')"
            ).fetchone()[0]
            contract_gate_outcome_events = gate_outcome_events
            verification_gate_outcome_events = conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE event_kind = 'verification_fail' "
                "OR event_kind = 'experiment'"
            ).fetchone()[0]
            screening = conn.execute("""
                SELECT
                    COALESCE(SUM(screening_case_total), 0) AS case_total,
                    COALESCE(SUM(screening_case_wins), 0) AS case_wins,
                    COALESCE(SUM(screening_case_losses), 0) AS case_losses,
                    COALESCE(SUM(screening_case_ties), 0) AS case_ties,
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
            "contract_failures": contract_failures,
            "verification_failures": verification_failures,
            "gate_outcome_events": gate_outcome_events,
            "contract_gate_outcome_events": contract_gate_outcome_events,
            "verification_gate_outcome_events": verification_gate_outcome_events,
            "screening_case_wins": screening_case_wins,
            "screening_case_losses": screening_case_losses,
            "screening_case_ties": screening_case_ties,
            "screening_case_total": screening_case_total,
            "screening_case_win_rate": screening_case_win_rate,
            "screening_pair_wins": screening_pair_wins,
            "screening_pair_losses": screening_pair_losses,
            "screening_pair_ties": screening_pair_ties,
            "screening_pair_total": screening_pair_total,
            "screening_pair_win_rate": screening_pair_win_rate,
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
