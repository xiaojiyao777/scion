"""LineageRegistry — append-only experiment event storage.

Uses SQLite with WAL mode. experiment_events is INSERT-only (no UPDATE/DELETE).
record_decision writes decision info as a separate event row for the branch.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from scion.core.models import DecisionFeatures, DecisionOutcome, WeightOptimizationResult


class LineageRegistry:
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
                    screening_case_win_rate REAL,
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
                    model_id               TEXT,
                    protocol_version       TEXT,
                    prompt_tokens          INTEGER,
                    completion_tokens      INTEGER,
                    created_at             TEXT DEFAULT (datetime('now'))
                )
            """)
            # Migrate existing databases: add columns that may not exist yet
            self._ensure_columns(conn, "experiment_events", {
                "event_kind":        "TEXT DEFAULT 'experiment'",
                "model_id":          "TEXT",
                "protocol_version":  "TEXT",
                "prompt_tokens":     "INTEGER",
                "completion_tokens": "INTEGER",
                "audit_payload_json": "TEXT",
                "screening_win_rate_scope": "TEXT",
                "screening_case_wins": "INTEGER",
                "screening_case_losses": "INTEGER",
                "screening_case_ties": "INTEGER",
                "screening_case_win_rate": "REAL",
                "screening_gate_win_rate": "REAL",
                "screening_pair_wins": "INTEGER",
                "screening_pair_losses": "INTEGER",
                "screening_pair_ties": "INTEGER",
                "screening_pair_total": "INTEGER",
                "screening_pair_win_rate": "REAL",
            })
            conn.execute("""
                CREATE TABLE IF NOT EXISTS branches (
                    branch_id           TEXT PRIMARY KEY,
                    state               TEXT NOT NULL,
                    base_champion_id    INTEGER NOT NULL,
                    base_champion_hash  TEXT NOT NULL,
                    current_code_hash   TEXT,
                    last_clean_code_hash TEXT,
                    retry_count         INTEGER DEFAULT 0,
                    screening_expand_count INTEGER DEFAULT 0,
                    validation_expand_count INTEGER DEFAULT 0,
                    failure_codes       TEXT,
                    created_at          TEXT NOT NULL,
                    updated_at          TEXT NOT NULL,
                    direction           TEXT,
                    weight_revision     INTEGER DEFAULT 0,
                    pending_retry       INTEGER DEFAULT 0,
                    blocked_rounds      INTEGER DEFAULT 0,
                    consecutive_llm_retries INTEGER DEFAULT 0,
                    infra_block_count   INTEGER DEFAULT 0
                )
            """)
            self._ensure_columns(conn, "branches", {
                "screening_expand_count": "INTEGER DEFAULT 0",
                "validation_expand_count": "INTEGER DEFAULT 0",
                "direction": "TEXT",
                "weight_revision": "INTEGER DEFAULT 0",
                "pending_retry": "INTEGER DEFAULT 0",
                "blocked_rounds": "INTEGER DEFAULT 0",
                "consecutive_llm_retries": "INTEGER DEFAULT 0",
                "infra_block_count": "INTEGER DEFAULT 0",
            })
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
                    target_objectives_json TEXT,
                    protected_objectives_json TEXT,
                    novelty_signature_json TEXT,
                    mechanism_changes_json TEXT
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
                    promoted_at              TEXT,
                    PRIMARY KEY (version, weight_revision)
                )
            """)
            self._ensure_columns(conn, "champions", {
                "weight_revision": "INTEGER DEFAULT 0",
            })
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
            self._ensure_columns(conn, "hypotheses", {
                "base_champion_version": "INTEGER DEFAULT 0",
                "predicted_direction": "TEXT",
                "target_objectives_json": "TEXT",
                "protected_objectives_json": "TEXT",
                "novelty_signature_json": "TEXT",
                "mechanism_changes_json": "TEXT",
            })

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

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

    def record_contract_failure(
        self,
        campaign_id: str,
        branch_id: str,
        hypothesis_text: str,
        change_locus: str,
        action: str,
        target_file: Optional[str],
        failure_reason: str,
    ) -> None:
        """Record a C10/contract failure event so research_log can surface it."""
        event = {
            "campaign_id": campaign_id,
            "branch_id": branch_id,
            "timestamp": datetime.now().isoformat(),
            "event_kind": "contract_fail",
            "hypothesis_text": hypothesis_text[:500],
            "patch_action": action,
            "patch_file": target_file or "",
            "contract_result": "failed",
            "verification_result": "skipped",
            "canary_result": "skipped",
            "stage": "hypothesis_contract",
            "decision": "abandon",
        }
        try:
            self.record_event(event)
        except Exception:
            pass

    def record_decision(
        self,
        branch_id: str,
        features_json: str,
        decision: str,
        reason: str,
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

    def query_failures(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return events where contract_result or verification_result = 'failed'.

        If category is given, filter by that specific result field value.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if category is not None:
                cursor = conn.execute(
                    """
                    SELECT * FROM experiment_events
                    WHERE contract_result = ?
                       OR verification_result = ?
                    ORDER BY timestamp DESC
                    """,
                    (category, category),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM experiment_events
                    WHERE contract_result = 'failed'
                       OR verification_result = 'failed'
                    ORDER BY timestamp DESC
                    """
                )
            return [dict(row) for row in cursor.fetchall()]

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
            n_champions = conn.execute(
                "SELECT COUNT(*) FROM champions"
            ).fetchone()[0]
            contract_failures = conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE event_kind = 'experiment' AND contract_result = 'failed'"
            ).fetchone()[0]
            verification_failures = conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE event_kind = 'experiment' AND verification_result = 'failed'"
            ).fetchone()[0]
            screening = conn.execute("""
                SELECT
                    COALESCE(SUM(screening_n_cases), 0) AS case_total,
                    COALESCE(
                        SUM(
                            COALESCE(
                                screening_case_wins,
                                ROUND(screening_win_rate * screening_n_cases)
                            )
                        ),
                        0
                    ) AS case_wins,
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
            "n_champions": n_champions,
            "contract_failures": contract_failures,
            "verification_failures": verification_failures,
            "screening_win_rate": screening_case_win_rate,
            "screening_win_rate_scope": "case_level_gate",
            "screening_case_wins": screening_case_wins,
            "screening_case_losses": screening_case_losses,
            "screening_case_ties": screening_case_ties,
            "screening_case_total": screening_case_total,
            "screening_case_win_rate": screening_case_win_rate,
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
                "recent_failures": [last 10 failure events as dicts],
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
                    "total": row["total"], "failed": row["failed"],
                }

            recent = [dict(r) for r in conn.execute("""
                SELECT branch_id, hypothesis_id, contract_result, verification_result,
                       decision, timestamp
                FROM experiment_events
                WHERE event_kind = 'experiment'
                  AND (contract_result = 'failed' OR verification_result = 'failed')
                ORDER BY timestamp DESC
                LIMIT 10
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
