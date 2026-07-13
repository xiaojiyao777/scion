"""Direct typed classification tests for FailureRouter."""
from __future__ import annotations

import uuid

import pytest

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import Branch, BranchState, FailureEvent
from scion.failure.router import FailureRouter


def _branch() -> Branch:
    return Branch(
        branch_id=str(uuid.uuid4()),
        state=BranchState.EXPLORE,
        base_champion_id=0,
        base_champion_hash="hash0",
    )


@pytest.mark.parametrize(
    "category",
    ["proposal", "contract", "verification_light", "verification_heavy", "evaluation"],
)
def test_non_infra_failure_rejects_current_response(category: str) -> None:
    action = FailureRouter().route(
        FailureEvent(category=category, detail="rejected response"),
        _branch(),
    )

    assert action.action == "reject_response"
    assert action.execution_outcome is ExecutionOutcome.NOT_EVALUATED
    assert action.reason_code == "RESPONSE_REJECTED"


def test_infra_failure_blocks_until_explicit_resume() -> None:
    action = FailureRouter().route(
        FailureEvent(category="infra", detail="runner unavailable"),
        _branch(),
    )

    assert action.action == "block_infra"
    assert action.execution_outcome is ExecutionOutcome.BLOCKED_INFRA
    assert action.reason_code == "INFRA_BLOCKED"


def test_failure_action_has_no_retry_control_fields() -> None:
    action = FailureRouter().route(
        FailureEvent(category="contract", detail="bad candidate"),
        _branch(),
    )

    assert action.action == "reject_response"
    assert not hasattr(action, "retry_llm")
    assert not hasattr(action, "max_retries_remaining")
