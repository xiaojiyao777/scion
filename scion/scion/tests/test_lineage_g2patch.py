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

    def test_campaign_summary_counts_only_experiment_rows(self, tmp_path):
        reg = _reg(tmp_path)
        # Completed experiments are represented by one event each.
        reg.record_event({"branch_id": "b1", "timestamp": datetime.now().isoformat()})
        reg.record_event({"branch_id": "b1", "timestamp": datetime.now().isoformat()})
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
        for col in (
            "event_kind",
            "model_id",
            "protocol_version",
            "prompt_tokens",
            "completion_tokens",
        ):
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
