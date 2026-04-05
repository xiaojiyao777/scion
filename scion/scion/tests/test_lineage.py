import pytest
import os
import uuid
from datetime import datetime
from scion.lineage.registry import LineageRegistry

def test_registry_record_and_query(tmp_path):
    db_path = str(tmp_path / "scion.db")
    registry = LineageRegistry(db_path)
    
    event_id = str(uuid.uuid4())
    branch_id = str(uuid.uuid4())
    
    event_data = {
        "event_id": event_id,
        "campaign_id": "test_camp",
        "branch_id": branch_id,
        "hypothesis_id": "hyp_1",
        "timestamp": datetime.now().isoformat(),
        "code_hash": "abc",
        "patch_action": "modify",
        "contract_result": "passed",
        "verification_result": "passed",
        "stage": "screening",
        "case_ids": "[]",
        "seed_set": "[]",
        "raw_metrics_ref": "ref_1"
    }
    
    registry.record_event(event_data)
    
    events = registry.query_by_branch(branch_id)
    assert len(events) == 1
    assert events[0]["event_id"] == event_id
    assert events[0]["campaign_id"] == "test_camp"

def test_registry_persistence(tmp_path):
    db_path = str(tmp_path / "scion.db")
    registry1 = LineageRegistry(db_path)
    
    branch_id = "br_1"
    registry1.record_event({
        "event_id": "ev_1", "campaign_id": "c1", "branch_id": branch_id,
        "hypothesis_id": "h1", "timestamp": "now", "code_hash": "a",
        "patch_action": "m", "contract_result": "p", "verification_result": "p"
    })
    
    # 重新加载
    registry2 = LineageRegistry(db_path)
    events = registry2.query_by_branch(branch_id)
    assert len(events) == 1
    assert events[0]["event_id"] == "ev_1"
