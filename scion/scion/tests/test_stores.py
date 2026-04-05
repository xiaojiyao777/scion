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
        status="pending",
        target_file="op1.py"
    )
    
    store.save(hyp)
    # Simple check that it doesn't crash and table is created
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT * FROM hypotheses WHERE hypothesis_id = 'h1'").fetchone()
        assert row is not None
        assert row[0] == "h1"
