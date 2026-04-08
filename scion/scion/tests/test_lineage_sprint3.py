"""Tests for Sprint 3 lineage module: LineageRegistry, BranchStore, ChampionStore."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import pytest

from scion.core.models import (
    Branch, BranchState, ChampionState, HypothesisRecord, OperatorConfig,
)
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.champion_store import ChampionStore
from scion.lineage.registry import LineageRegistry


# ---------------------------------------------------------------------------
# LineageRegistry
# ---------------------------------------------------------------------------

class TestLineageRegistry:
    def test_record_and_query_by_branch(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = str(uuid.uuid4())
        eid = reg.record_event({
            "event_id": str(uuid.uuid4()),
            "branch_id": bid,
            "timestamp": datetime.now().isoformat(),
            "contract_result": "passed",
            "verification_result": "passed",
        })
        rows = reg.query_by_branch(bid)
        assert len(rows) == 1
        assert rows[0]["branch_id"] == bid

    def test_record_event_auto_event_id(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = "br_auto"
        eid = reg.record_event({"branch_id": bid, "timestamp": "t1"})
        assert eid is not None
        rows = reg.query_by_branch(bid)
        assert len(rows) == 1

    def test_record_event_append_only(self, tmp_path):
        """Multiple record_event calls create multiple rows, not overwrite."""
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = "br_append"
        reg.record_event({"branch_id": bid, "timestamp": "t1"})
        reg.record_event({"branch_id": bid, "timestamp": "t2"})
        rows = reg.query_by_branch(bid)
        assert len(rows) == 2

    def test_record_decision_appends_row(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = "br_dec"
        reg.record_decision(bid, '{"key": "val"}', "queue_validate", '["PASS"]')
        rows = reg.query_by_branch(bid)
        assert len(rows) == 1
        assert rows[0]["decision"] == "queue_validate"
        assert rows[0]["decision_reason"] == '["PASS"]'

    def test_record_decision_is_insert_not_update(self, tmp_path):
        """record_decision must INSERT (append), not UPDATE existing rows."""
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = "br_ins"
        # Insert a plain event first
        reg.record_event({"branch_id": bid, "timestamp": "t1"})
        # Then record a decision — should add a second row
        reg.record_decision(bid, "{}", "abandon", "[]")
        rows = reg.query_by_branch(bid)
        assert len(rows) == 2

    def test_query_failures_returns_failed_rows(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = "br_fail"
        reg.record_event({
            "branch_id": bid, "timestamp": "t1",
            "contract_result": "failed", "verification_result": "passed",
        })
        reg.record_event({
            "branch_id": bid, "timestamp": "t2",
            "contract_result": "passed", "verification_result": "passed",
        })
        failures = reg.query_failures()
        assert len(failures) == 1
        assert failures[0]["contract_result"] == "failed"

    def test_query_failures_with_category(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = "br_cat"
        reg.record_event({
            "branch_id": bid, "timestamp": "t1",
            "contract_result": "failed",
        })
        reg.record_event({
            "branch_id": bid, "timestamp": "t2",
            "verification_result": "failed",
        })
        # Only contract failures
        rows = reg.query_failures(category="failed")
        assert len(rows) == 2  # both have 'failed' in some field

    def test_get_campaign_summary_empty(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        summary = reg.get_campaign_summary()
        assert summary["total_events"] == 0
        assert summary["n_branches"] == 0
        assert summary["n_champions"] == 0

    def test_get_campaign_summary_counts(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        for i in range(3):
            reg.record_event({
                "branch_id": f"br_{i}",
                "timestamp": f"t{i}",
                "decision": "abandon" if i < 2 else "promote",
                "contract_result": "failed" if i == 0 else "passed",
            })
        summary = reg.get_campaign_summary()
        assert summary["total_events"] == 3
        assert summary["n_branches"] == 3
        assert summary["by_decision"]["abandon"] == 2
        assert summary["by_decision"]["promote"] == 1
        assert summary["contract_failures"] == 1

    def test_persistence_across_instances(self, tmp_path):
        db_path = str(tmp_path / "scion.db")
        r1 = LineageRegistry(db_path)
        r1.record_event({"branch_id": "b1", "timestamp": "t0"})
        r2 = LineageRegistry(db_path)
        rows = r2.query_by_branch("b1")
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# BranchStore
# ---------------------------------------------------------------------------

def _make_branch(branch_id: str = None) -> Branch:
    return Branch(
        branch_id=branch_id or str(uuid.uuid4()),
        state=BranchState.EXPLORE,
        base_champion_id=0,
        base_champion_hash="hash0",
    )


class TestBranchStore:
    def test_save_and_load(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        store = BranchStore(reg)
        b = _make_branch("br_save")
        store.save(b)
        loaded = store.load("br_save")
        assert loaded is not None
        assert loaded.branch_id == "br_save"
        assert loaded.state == BranchState.EXPLORE

    def test_load_missing_returns_none(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        store = BranchStore(reg)
        assert store.load("nonexistent") is None

    def test_save_updates_existing(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        store = BranchStore(reg)
        b = _make_branch("br_upd")
        store.save(b)
        b.state = BranchState.READY_VALIDATE
        b.retry_count = 2
        store.save(b)
        loaded = store.load("br_upd")
        assert loaded.state == BranchState.READY_VALIDATE
        assert loaded.retry_count == 2

    def test_load_all_active_excludes_terminal(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        store = BranchStore(reg)
        active = _make_branch("br_active")
        abandoned = _make_branch("br_abandoned")
        abandoned.state = BranchState.ABANDONED
        promoted = _make_branch("br_promoted")
        promoted.state = BranchState.PROMOTED
        for b in (active, abandoned, promoted):
            store.save(b)
        results = store.load_all_active()
        ids = {b.branch_id for b in results}
        assert "br_active" in ids
        assert "br_abandoned" not in ids
        assert "br_promoted" not in ids

    def test_failure_codes_roundtrip(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        store = BranchStore(reg)
        b = _make_branch("br_fc")
        b.failure_codes = ["CONTRACT", "VERIFICATION"]
        store.save(b)
        loaded = store.load("br_fc")
        assert loaded.failure_codes == ["CONTRACT", "VERIFICATION"]


# ---------------------------------------------------------------------------
# HypothesisStore
# ---------------------------------------------------------------------------

class TestHypothesisStore:
    def test_save_hypothesis(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        store = HypothesisStore(reg)
        hyp = HypothesisRecord(
            hypothesis_id="h1",
            branch_id="b1",
            change_locus="order_level",
            action="modify",
            status="pending",
            target_file="op1.py",
        )
        store.save(hyp)
        import sqlite3
        with sqlite3.connect(reg.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM hypotheses WHERE hypothesis_id = 'h1'"
            ).fetchone()
        assert row is not None
        assert row[0] == "h1"


# ---------------------------------------------------------------------------
# ChampionStore
# ---------------------------------------------------------------------------

def _make_champion_state(version: int = 1) -> ChampionState:
    return ChampionState(
        version=version,
        operator_pool={
            "ls": OperatorConfig(
                name="ls", file_path="ops/ls.py",
                category="local_search", weight=1.0, class_name="LS",
            )
        },
        solver_config_hash="cfg_hash",
        code_snapshot_path=f"/tmp/snap/v{version}",
        code_snapshot_hash=f"hash{version}",
        promoted_at=datetime.now().isoformat(),
    )


class TestChampionStore:
    def test_get_current_empty(self, tmp_path):
        store = ChampionStore(str(tmp_path / "scion.db"), str(tmp_path / "snaps"))
        assert store.get_current() is None

    def test_promote_and_get_current(self, tmp_path):
        store = ChampionStore(str(tmp_path / "scion.db"), str(tmp_path / "snaps"))
        champ = _make_champion_state(1)
        store.promote(champ)
        current = store.get_current()
        assert current is not None
        assert current.version == 1
        assert "ls" in current.operator_pool

    def test_get_history_ordered(self, tmp_path):
        store = ChampionStore(str(tmp_path / "scion.db"), str(tmp_path / "snaps"))
        for v in [1, 2, 3]:
            store.promote(_make_champion_state(v))
        history = store.get_history()
        assert [c.version for c in history] == [1, 2, 3]

    def test_promote_is_insert_only(self, tmp_path):
        """Promoting same version twice should raise (integrity error)."""
        store = ChampionStore(str(tmp_path / "scion.db"), str(tmp_path / "snaps"))
        store.promote(_make_champion_state(1))
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            store.promote(_make_champion_state(1))

    def test_get_by_version(self, tmp_path):
        store = ChampionStore(str(tmp_path / "scion.db"), str(tmp_path / "snaps"))
        for v in [1, 2]:
            store.promote(_make_champion_state(v))
        c = store.get_by_version(1)
        assert c is not None
        assert c.version == 1

    def test_operator_pool_roundtrip(self, tmp_path):
        store = ChampionStore(str(tmp_path / "scion.db"), str(tmp_path / "snaps"))
        champ = _make_champion_state(1)
        store.promote(champ)
        loaded = store.get_current()
        op = loaded.operator_pool["ls"]
        assert op.name == "ls"
        assert op.category == "local_search"
        assert op.weight == 1.0
