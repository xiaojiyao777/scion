import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Any, Dict
from dataclasses import asdict
from scion.core.models import DecisionFeatures, DecisionOutcome

class LineageRegistry:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            # Create core tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiment_events (
                    event_id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    branch_id TEXT NOT NULL,
                    hypothesis_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    patch_action TEXT NOT NULL,
                    contract_result TEXT NOT NULL,
                    verification_result TEXT NOT NULL,
                    canary_result TEXT,
                    stage TEXT,
                    case_ids TEXT,
                    seed_set TEXT,
                    raw_metrics_ref TEXT,
                    decision_features_json TEXT,
                    decision TEXT,
                    decision_reason TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS branches (
                    branch_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    base_champion_id INTEGER NOT NULL,
                    base_champion_hash TEXT NOT NULL,
                    current_code_hash TEXT,
                    last_clean_code_hash TEXT,
                    retry_count INTEGER DEFAULT 0,
                    failure_codes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS champions (
                    version INTEGER PRIMARY KEY,
                    operator_pool_json TEXT NOT NULL,
                    solver_config_hash TEXT NOT NULL,
                    code_snapshot_path TEXT NOT NULL,
                    code_snapshot_hash TEXT NOT NULL,
                    promotion_experiment_id TEXT,
                    promoted_at TEXT
                )
            """)

    def record_event(self, event: Dict[str, Any]):
        """
        Record an experiment event.
        We use a dictionary for now to be flexible before all components are stable.
        """
        cols = ", ".join(event.keys())
        placeholders = ", ".join(["?"] * len(event))
        sql = f"INSERT INTO experiment_events ({cols}) VALUES ({placeholders})"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, list(event.values()))

    def record_decision(self, branch_id: str, features: DecisionFeatures, 
                        outcome: DecisionOutcome):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE experiment_events 
                SET decision_features_json = ?, 
                    decision = ?, 
                    decision_reason = ?
                WHERE branch_id = ? 
                AND event_id = (SELECT MAX(event_id) FROM experiment_events WHERE branch_id = ?)
            """, (
                json.dumps(asdict(features)),
                outcome.decision.value,
                json.dumps(outcome.reason_codes),
                branch_id,
                branch_id
            ))

    def query_by_branch(self, branch_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM experiment_events WHERE branch_id = ? ORDER BY timestamp DESC", (branch_id,))
            return [dict(row) for row in cursor.fetchall()]
