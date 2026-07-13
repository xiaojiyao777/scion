from __future__ import annotations

from scion.core.branch_cards import branch_card_context
from scion.core.models import Branch, BranchState
from scion.core.scheduler import branch_scheduling_status


def test_branch_card_active_slot_fields_use_scheduler_status() -> None:
    branch = Branch(
        branch_id="copied-weak-inactive-card",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_evidence_summary={
            "stage": "screening",
            "tier": "inactive",
            "activation_status": "inactive",
            "decision_features_excluded": True,
        },
    )

    scheduling_status = branch_scheduling_status(branch)
    payload = branch_card_context(branch)

    assert scheduling_status.consumes_active_slot is True
    assert scheduling_status.schedulable is True
    assert scheduling_status.lane == "explore"
    assert payload["scheduling_status"] == scheduling_status.as_dict()
    assert payload["evidence_summary"] == branch.branch_evidence_summary
