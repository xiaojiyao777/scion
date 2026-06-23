from __future__ import annotations

from scion.core.branch_hygiene import branch_hygiene_context
from scion.core.models import Branch, BranchState
from scion.core.scheduler import branch_scheduling_status


def test_branch_card_active_slot_fields_use_scheduler_status() -> None:
    branch = Branch(
        branch_id="copied-weak-inactive-card",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
        branch_evidence_summary={
            "stage": "screening",
            "tier": "inactive",
            "activation_status": "inactive",
            "decision_features_excluded": True,
        },
    )

    scheduling_status = branch_scheduling_status(branch)
    payload = branch_hygiene_context(branch)

    assert scheduling_status.lineage_status == "inactive_current_head"
    assert scheduling_status.consumes_active_slot is False
    assert scheduling_status.release_reason == "inactive_current_evidence_slot_release"
    assert payload["lineage_status"] == scheduling_status.lineage_status
    assert payload["weak_positive_followup"] is False
    assert payload["active_slot_status"] == "released_active_slot"
    assert payload["counts_toward_active_slots"] is False
    assert payload["current_head_active_slot_release_reason"] == (
        scheduling_status.release_reason
    )
    assert payload["branch_scheduling_status"]["lane"] == scheduling_status.lane
    assert payload["branch_scheduling_status"]["promotion_boundary"] == (
        "not_a_promotion_or_validation_decision"
    )
    assert payload["branch_scheduling_status"]["decision_features_excluded"] is True
