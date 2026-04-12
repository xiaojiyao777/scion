"""Tests for T2: event_kind distinction and schema additions in LineageRegistry."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

import pytest

from scion.lineage.registry import LineageRegistry


def _reg(tmp_path) -> LineageRegistry:
    return LineageRegistry(str(tmp_path / "scion.db"))


# ---------------------------------------------------------------------------
# T2a: event_kind stamping
# ---------------------------------------------------------------------------

class TestEventKind:
    def test_record_event_stamps_experiment(self, tmp_path):
        reg = _reg(tmp_path)
        eid = reg.record_event({
            "branch_id": "b1",
            "timestamp": datetime.now().isoformat(),
        })
        with sqlite3.connect(str(tmp_path / "scion.db")) as conn:
            row = conn.execute(
                "SELECT event_kind FROM experiment_events WHERE event_id = ?", (eid,)
            ).fetchone()
        assert row is not None
        assert row[0] == "experiment"

    def test_record_decision_stamps_decision(self, tmp_path):
        reg = _reg(tmp_path)
        reg.record_decision("b1", "{}", "continue_explore", "[]")
        with sqlite3.connect(str(tmp_path / "scion.db")) as conn:
            rows = conn.execute(
                "SELECT event_kind FROM experiment_events WHERE branch_id = 'b1'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "decision"

    def test_campaign_summary_counts_only_experiment_rows(self, tmp_path):
        reg = _reg(tmp_path)
        # 2 experiment events
        reg.record_event({"branch_id": "b1", "timestamp": datetime.now().isoformat()})
        reg.record_event({"branch_id": "b1", "timestamp": datetime.now().isoformat()})
        # 1 decision event — must NOT be counted in total_events
        reg.record_decision("b1", "{}", "continue_explore", "[]")
        summary = reg.get_campaign_summary()
        assert summary["total_events"] == 2

    def test_existing_record_event_preserves_explicit_event_kind(self, tmp_path):
        """Caller can override event_kind if needed."""
        reg = _reg(tmp_path)
        eid = reg.record_event({
            "branch_id": "b1",
            "timestamp": datetime.now().isoformat(),
            "event_kind": "custom",
        })
        with sqlite3.connect(str(tmp_path / "scion.db")) as conn:
            row = conn.execute(
                "SELECT event_kind FROM experiment_events WHERE event_id = ?", (eid,)
            ).fetchone()
        assert row[0] == "custom"


# ---------------------------------------------------------------------------
# T2b: new audit columns present and writable
# ---------------------------------------------------------------------------

class TestAuditColumns:
    def test_new_columns_exist(self, tmp_path):
        _reg(tmp_path)  # init creates the table
        with sqlite3.connect(str(tmp_path / "scion.db")) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(experiment_events)")}
        for col in ("event_kind", "model_id", "protocol_version", "prompt_tokens", "completion_tokens"):
            assert col in cols, f"Missing column: {col}"

    def test_audit_columns_are_writable(self, tmp_path):
        reg = _reg(tmp_path)
        eid = reg.record_event({
            "branch_id": "b1",
            "timestamp": datetime.now().isoformat(),
            "model_id": "claude-sonnet-4-6",
            "protocol_version": "v2",
            "prompt_tokens": 1234,
            "completion_tokens": 567,
        })
        with sqlite3.connect(str(tmp_path / "scion.db")) as conn:
            row = conn.execute(
                "SELECT model_id, protocol_version, prompt_tokens, completion_tokens "
                "FROM experiment_events WHERE event_id = ?",
                (eid,),
            ).fetchone()
        assert row == ("claude-sonnet-4-6", "v2", 1234, 567)

    def test_legacy_db_upgrade_adds_columns(self, tmp_path):
        """Opening an old DB (missing new columns) should add them without error."""
        db_path = str(tmp_path / "legacy.db")
        # Create a bare-bones old schema without the new columns
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE experiment_events (
                    event_id   TEXT PRIMARY KEY,
                    branch_id  TEXT NOT NULL,
                    timestamp  TEXT NOT NULL,
                    decision   TEXT
                )
            """)
            conn.execute(
                "INSERT INTO experiment_events VALUES (?, ?, ?, ?)",
                ("old-ev", "b-old", "2025-01-01", None),
            )
        # Re-open via LineageRegistry — should migrate without exception
        reg = LineageRegistry(db_path)
        with sqlite3.connect(db_path) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(experiment_events)")}
        for col in ("event_kind", "model_id", "protocol_version", "prompt_tokens", "completion_tokens"):
            assert col in cols, f"Migration missed column: {col}"
        # Old data must still be queryable
        events = reg.query_by_branch("b-old")
        assert len(events) == 1
