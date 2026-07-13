"""Campaign failure facade tests for direct typed outcomes."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scion.core.branch import BranchController
from scion.core.models import BranchState, ChampionState, FailureEvent
from scion.failure.router import FailureRouter


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="sc",
        code_snapshot_path="/tmp/snap",
        code_snapshot_hash="snap_hash",
    )


def _make_campaign_handle_failure():
    branch_ctrl = BranchController()

    class _Stub:
        def __init__(self):
            self._failure_router = FailureRouter()
            self._branch_ctrl = branch_ctrl
            self._branch_hypotheses = {}
            self._branch_patches = {}
            self._branch_store = MagicMock()
            self._registry = MagicMock()
            self._failure_streak = {}
            self._total_failures = {}
            self._campaign_id = "stub-campaign"

        from scion.core.campaign import CampaignManager
        _handle_failure = CampaignManager._handle_failure
        operator_resume_infra = CampaignManager.operator_resume_infra

    return _Stub(), branch_ctrl


def test_response_rejection_discards_current_candidate_without_retry_state() -> None:
    stub, ctrl = _make_campaign_handle_failure()
    branch = ctrl.create_branch(_champion())
    stub._branch_hypotheses[branch.branch_id] = MagicMock()
    stub._branch_patches[branch.branch_id] = MagicMock()

    stub._handle_failure(branch, FailureEvent(category="contract", detail="bad candidate"))

    assert branch.state is BranchState.EXPLORE
    assert branch.branch_id not in stub._branch_hypotheses
    assert branch.branch_id not in stub._branch_patches
    assert not hasattr(branch, "pending_retry")
    assert stub._failure_streak == {"contract": 1}


def test_infra_failure_blocks_and_preserves_candidate() -> None:
    stub, ctrl = _make_campaign_handle_failure()
    branch = ctrl.create_branch(_champion())
    hypothesis = MagicMock()
    patch = MagicMock()
    stub._branch_hypotheses[branch.branch_id] = hypothesis
    stub._branch_patches[branch.branch_id] = patch

    stub._handle_failure(branch, FailureEvent(category="infra", detail="runner down"))

    assert branch.state is BranchState.BLOCKED_INFRA
    assert stub._branch_hypotheses[branch.branch_id] is hypothesis
    assert stub._branch_patches[branch.branch_id] is patch


def test_explicit_operator_resume_is_the_only_infra_release() -> None:
    stub, ctrl = _make_campaign_handle_failure()
    branch = ctrl.create_branch(_champion())
    stub._handle_failure(branch, FailureEvent(category="infra", detail="runner down"))

    assert stub.operator_resume_infra(
        branch.branch_id,
        operator_reason="runner repaired",
        operator_ack="operator-confirmed",
    )
    assert branch.state is BranchState.EXPLORE
    events = [
        call.args[0]
        for call in stub._registry.record_event.call_args_list
        if call.args[0].get("event_kind") == "operator_resume_infra"
    ]
    assert len(events) == 1


def test_operator_resume_requires_ack() -> None:
    stub, ctrl = _make_campaign_handle_failure()
    branch = ctrl.create_branch(_champion())
    stub._handle_failure(branch, FailureEvent(category="infra", detail="runner down"))

    with pytest.raises(ValueError, match="operator_ack"):
        stub.operator_resume_infra(
            branch.branch_id,
            operator_reason="runner repaired",
            operator_ack="",
        )

    assert branch.state is BranchState.BLOCKED_INFRA
