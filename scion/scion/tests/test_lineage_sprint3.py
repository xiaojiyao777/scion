"""Tests for Sprint 3 lineage module: LineageRegistry, BranchStore, ChampionStore."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
    OperatorConfig,
    PatchProposal,
    ProtocolResult,
)
from scion.core.decision_finalizer import _sync_terminal_branch_evidence
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
        eid = reg.record_event(
            {
                "event_id": str(uuid.uuid4()),
                "branch_id": bid,
                "timestamp": datetime.now().isoformat(),
                "contract_result": "passed",
                "verification_result": "passed",
            }
        )
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

    def test_record_decision_persists_correlation_identity(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        reg.record_decision(
            "branch-1",
            "{}",
            "continue_explore",
            "[]",
            campaign_id="campaign-1",
            hypothesis_id="hypothesis-1",
            stage="screening",
        )

        row = reg.query_by_branch("branch-1")[0]

        assert row["campaign_id"] == "campaign-1"
        assert row["hypothesis_id"] == "hypothesis-1"
        assert row["stage"] == "screening"

    def test_query_failures_returns_failed_rows(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = "br_fail"
        reg.record_event(
            {
                "branch_id": bid,
                "timestamp": "t1",
                "contract_result": "failed",
                "verification_result": "passed",
            }
        )
        reg.record_event(
            {
                "branch_id": bid,
                "timestamp": "t2",
                "contract_result": "passed",
                "verification_result": "passed",
            }
        )
        failures = reg.query_failures()
        assert len(failures) == 1
        assert failures[0]["contract_result"] == "failed"

    def test_query_failures_with_category(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = "br_cat"
        reg.record_event(
            {
                "branch_id": bid,
                "timestamp": "t1",
                "contract_result": "failed",
            }
        )
        reg.record_event(
            {
                "branch_id": bid,
                "timestamp": "t2",
                "verification_result": "failed",
            }
        )
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
            reg.record_event(
                {
                    "branch_id": f"br_{i}",
                    "timestamp": f"t{i}",
                    "decision": "abandon" if i < 2 else "promote",
                    "contract_result": "failed" if i == 0 else "passed",
                }
            )
        summary = reg.get_campaign_summary()
        assert summary["total_events"] == 3
        assert summary["n_branches"] == 3
        assert summary["by_decision"]["abandon"] == 2
        assert summary["by_decision"]["promote"] == 1
        assert summary["contract_failures"] == 1

    def test_typed_verification_failure_is_in_failure_queries_and_summary(
        self,
        tmp_path,
    ):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        reg.record_execution_outcome(
            campaign_id="campaign-1",
            branch_id="branch-1",
            hypothesis_id="hypothesis-1",
            record=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="VERIFICATION_LIGHT_REJECTED",
                detail="verification rejected",
                provenance={
                    "owner": "verification_gate",
                    "stage": "verification",
                    "verification_checks": [
                        {"name": "V1_syntax", "passed": True},
                        {"name": "V1b_undefined_names", "passed": False},
                    ],
                },
            ),
            event_kind="verification_fail",
            stage="verification",
        )

        failures = reg.query_failures()
        assert len(failures) == 1
        assert failures[0]["verification_result"] == "failed"
        assert failures[0]["decision_reason"] is None
        assert failures[0]["failed_check"] == "V1b_undefined_names"
        assert failures[0]["failure_code"] == "V1b_undefined_names"
        assert failures[0]["failure_detail"] == "V1b_undefined_names"
        assert reg.query_failures(category="failed") == failures
        assert reg.query_failures(category="V1b_undefined_names") == failures

        summary = reg.get_campaign_summary()
        assert summary["total_events"] == 0
        assert summary["gate_outcome_events"] == 1
        assert summary["contract_gate_outcome_events"] == 1
        assert summary["verification_gate_outcome_events"] == 1
        assert summary["verification_failures"] == 1

    def test_typed_verification_failure_survives_malformed_provenance(
        self,
        tmp_path,
    ):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        with sqlite3.connect(reg.db_path) as conn:
            conn.execute(
                """
                INSERT INTO experiment_events (
                    event_id, branch_id, timestamp, event_kind,
                    execution_outcome, execution_outcome_reason_code,
                    execution_outcome_detail, execution_outcome_provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "event-1",
                    "branch-1",
                    "t1",
                    "verification_fail",
                    "research_rejected",
                    "VERIFICATION_LIGHT_REJECTED",
                    "V2_interface",
                    "{malformed",
                ),
            )

        failures = reg.query_failures()
        assert len(failures) == 1
        assert failures[0]["verification_result"] == "failed"
        assert failures[0]["decision_reason"] is None
        assert failures[0]["failed_check"] is None
        assert failures[0]["failure_code"] == "VERIFICATION_LIGHT_REJECTED"
        assert failures[0]["failure_detail"] == "V2_interface"

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
        store.save(b)
        loaded = store.load("br_upd")
        assert loaded.state == BranchState.READY_VALIDATE

    def test_load_all_active_excludes_terminal(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        store = BranchStore(reg)
        active = _make_branch("br_active")
        abandoned = _make_branch("br_abandoned")
        abandoned.state = BranchState.ABANDONED
        promoted = _make_branch("br_promoted")
        promoted.state = BranchState.PROMOTED
        parked = _make_branch("br_parked")
        parked.state = BranchState.PARKED_LINEAGE
        parked.branch_code_status = "parked_lineage"
        for b in (active, abandoned, promoted, parked):
            store.save(b)
        results = store.load_all_active()
        ids = {b.branch_id for b in results}
        assert "br_active" in ids
        assert "br_abandoned" not in ids
        assert "br_promoted" not in ids
        assert "br_parked" not in ids

    def test_load_all_includes_terminal_in_stable_creation_order(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        store = BranchStore(reg)
        later_active = _make_branch("br_later_active")
        later_active.created_at = datetime.fromisoformat("2026-01-02T00:00:00")
        earlier_terminal = _make_branch("br_earlier_terminal")
        earlier_terminal.created_at = datetime.fromisoformat("2026-01-01T00:00:00")
        earlier_terminal.state = BranchState.ABANDONED
        store.save(later_active)
        store.save(earlier_terminal)

        results = store.load_all()

        assert [branch.branch_id for branch in results] == [
            "br_earlier_terminal",
            "br_later_active",
        ]
        assert results[0].state == BranchState.ABANDONED

    @pytest.mark.parametrize(
        ("stored_json", "message"),
        (
            ("{not-json", "branch evidence summary JSON is invalid"),
            ("[]", "branch evidence summary JSON is not a mapping"),
        ),
    )
    def test_load_all_fails_closed_on_terminal_malformed_evidence(
        self,
        tmp_path,
        stored_json,
        message,
    ):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        store = BranchStore(reg)
        terminal = _make_branch("br_corrupt_terminal")
        terminal.state = BranchState.ABANDONED
        store.save(terminal)
        with sqlite3.connect(reg.db_path) as conn:
            conn.execute(
                "UPDATE branches SET branch_evidence_summary_json = ? "
                "WHERE branch_id = ?",
                (stored_json, terminal.branch_id),
            )

        # Historical single-row and scheduler reads retain their tolerant
        # decoder; the proposal-context all-branch read must not lose evidence.
        assert store.load(terminal.branch_id).branch_evidence_summary == {}
        assert store.load_all_active() == []
        with pytest.raises(ValueError, match=message):
            store.load_all()

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
                name="ls",
                file_path="ops/ls.py",
                category="local_search",
                weight=1.0,
                class_name="LS",
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
        """Promoting same version + same revision twice should raise."""
        store = ChampionStore(str(tmp_path / "scion.db"), str(tmp_path / "snaps"))
        store.promote(_make_champion_state(1))
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError):
            store.promote(_make_champion_state(1))

    def test_weight_revision_same_version_is_persisted(self, tmp_path):
        store = ChampionStore(str(tmp_path / "scion.db"), str(tmp_path / "snaps"))
        store.promote(_make_champion_state(2))
        revised = _make_champion_state(2)
        revised.weight_revision = 1
        revised.code_snapshot_path = "/tmp/snap/v2_r1"
        revised.code_snapshot_hash = "hash2_r1"
        store.promote(revised)

        current = store.get_current()
        assert current is not None
        assert current.version == 2
        assert current.weight_revision == 1

        history = store.get_history()
        assert [(c.version, c.weight_revision) for c in history] == [(2, 0), (2, 1)]
        assert store.get_by_version_revision(2, 0).weight_revision == 0

    def test_legacy_champions_table_migrates_to_weight_revision_pk(self, tmp_path):
        import sqlite3

        db_path = tmp_path / "scion.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE champions (
                    version INTEGER PRIMARY KEY,
                    operator_pool_json TEXT NOT NULL,
                    solver_config_hash TEXT NOT NULL,
                    code_snapshot_path TEXT NOT NULL,
                    code_snapshot_hash TEXT NOT NULL,
                    promotion_experiment_id TEXT,
                    promoted_at TEXT
                )
            """)
            conn.execute("""
                INSERT INTO champions (
                    version, operator_pool_json, solver_config_hash,
                    code_snapshot_path, code_snapshot_hash
                ) VALUES (1, '{}', 'cfg', '/tmp/snap/v1', 'hash1')
            """)

        store = ChampionStore(str(db_path), str(tmp_path / "snaps"))
        revised = _make_champion_state(1)
        revised.weight_revision = 1
        store.promote(revised)

        assert store.get_by_version_revision(1, 0) is not None
        assert store.get_by_version_revision(1, 1) is not None

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
