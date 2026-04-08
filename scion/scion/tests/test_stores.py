import pytest
import os
import uuid
from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage.registry import LineageRegistry
from scion.lineage.branch_store import BranchStore, HypothesisStore

def test_branch_store_save_load(tmp_path):
    db_path = str(tmp_path / "scion.db")
    registry = LineageRegistry(db_path)
    store = BranchStore(registry)

    branch_id = str(uuid.uuid4())
    branch = Branch(
        branch_id=branch_id,
        state=BranchState.EXPLORE,
        base_champion_id=0,
        base_champion_hash="hash0"
    )

    store.save(branch)
    loaded = store.load(branch_id)

    assert loaded is not None
    assert loaded.branch_id == branch_id
    assert loaded.state == BranchState.EXPLORE
    assert loaded.base_champion_id == 0

def test_hypothesis_store_save(tmp_path):
    db_path = str(tmp_path / "scion.db")
    registry = LineageRegistry(db_path)
    store = HypothesisStore(registry)

    hyp = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="order_level",
        action="modify",
        status="active",
        target_file="op1.py"
    )

    store.save(hyp)
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT * FROM hypotheses WHERE hypothesis_id = 'h1'").fetchone()
        assert row is not None
        assert row[0] == "h1"


def test_hypothesis_store_mark_status(tmp_path):
    registry = LineageRegistry(str(tmp_path / "scion.db"))
    store = HypothesisStore(registry)

    hyp = HypothesisRecord(
        hypothesis_id="h2", branch_id="b1",
        change_locus="order_level", action="modify", status="active",
    )
    store.save(hyp)
    store.mark_status("h2", "rejected")

    result = store.get_one("h2")
    assert result is not None
    assert result.status == "rejected"


def test_hypothesis_store_get_by_status(tmp_path):
    registry = LineageRegistry(str(tmp_path / "scion.db"))
    store = HypothesisStore(registry)

    for i, status in enumerate(["active", "active", "rejected", "blacklisted"]):
        hyp = HypothesisRecord(
            hypothesis_id=f"h{i}", branch_id="b1",
            change_locus="order_level", action="modify", status=status,
        )
        store.save(hyp)

    active = store.get_by_status("active")
    assert len(active) == 2
    rejected = store.get_by_status("rejected")
    assert len(rejected) == 1
    blacklisted = store.get_by_status("blacklisted")
    assert len(blacklisted) == 1


def test_hypothesis_store_get_by_branch(tmp_path):
    registry = LineageRegistry(str(tmp_path / "scion.db"))
    store = HypothesisStore(registry)

    for i in range(3):
        store.save(HypothesisRecord(
            hypothesis_id=f"b1h{i}", branch_id="b1",
            change_locus="order_level", action="modify", status="active",
        ))
    store.save(HypothesisRecord(
        hypothesis_id="b2h0", branch_id="b2",
        change_locus="order_level", action="modify", status="active",
    ))

    assert len(store.get_by_branch("b1")) == 3
    assert len(store.get_by_branch("b2")) == 1
    assert len(store.get_by_branch("b999")) == 0


def test_hypothesis_store_get_structural_summary(tmp_path):
    registry = LineageRegistry(str(tmp_path / "scion.db"))
    store = HypothesisStore(registry)

    store.save(HypothesisRecord(
        hypothesis_id="h_active", branch_id="b1",
        change_locus="order_level", action="modify", status="active",
        hypothesis_text="active hyp"
    ))
    store.save(HypothesisRecord(
        hypothesis_id="h_bl", branch_id="b2",
        change_locus="vehicle_level", action="create_new", status="blacklisted",
        hypothesis_text="blacklisted hyp"
    ))

    summary = store.get_structural_summary("b1", include_global_blacklist=True)
    assert "branch_hypotheses" in summary
    assert "blacklisted" in summary
    assert len(summary["branch_hypotheses"]) == 1
    assert summary["branch_hypotheses"][0]["hypothesis_id"] == "h_active"
    assert len(summary["blacklisted"]) == 1
    assert summary["blacklisted"][0]["hypothesis_id"] == "h_bl"

    summary_no_bl = store.get_structural_summary("b1", include_global_blacklist=False)
    assert summary_no_bl["blacklisted"] == []


def test_hypothesis_store_hypothesis_text_persisted(tmp_path):
    registry = LineageRegistry(str(tmp_path / "scion.db"))
    store = HypothesisStore(registry)

    store.save(HypothesisRecord(
        hypothesis_id="h_txt", branch_id="b1",
        change_locus="order_level", action="modify", status="active",
        hypothesis_text="test hypothesis text"
    ))
    loaded = store.get_one("h_txt")
    assert loaded is not None
    assert loaded.hypothesis_text == "test hypothesis text"
