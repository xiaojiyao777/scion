from __future__ import annotations

from typing import Any

import pytest

from scion.core.code_research_limits import CodeResearchLimits
from scion.proposal.engine import CreativeLayer, ProposalValidationError
from scion.proposal.hypothesis_research_session import HypothesisResearchSession
from scion.tests.unit.proposal.test_hypothesis_research_session import (
    _basis,
    _hypothesis,
    _SequenceClient,
    _snapshot,
)


def _stage(slot: int, hypothesis: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": "stage_hypothesis_candidate",
        "slot": slot,
        "hypothesis": hypothesis,
        "research_basis": _basis("source-0001"),
    }


def test_accepted_stage_counts_before_safe_tool_result_cap_termination() -> None:
    events: list[str] = []
    client = _SequenceClient(
        [
            {"action": "read_source", "ref": "source-0001"},
            _stage(1, _hypothesis()),
        ]
    )
    session = HypothesisResearchSession(
        CreativeLayer(client),
        CodeResearchLimits(max_turns=4, max_hypothesis_candidates=2),
        record_candidate_completed=lambda: events.append("completed"),
        record_candidate_selected=lambda: events.append("selected"),
    )
    original_record_result = session._budget.record_result

    def terminate_after_accepted_stage(result: dict[str, Any]) -> None:
        if (
            result.get("action") == "stage_hypothesis_candidate"
            and result.get("ok") is True
        ):
            raise ProposalValidationError(
                "hypothesis research tool results exceed max_tool_result_chars"
            )
        original_record_result(result)

    session._budget.record_result = terminate_after_accepted_stage

    with pytest.raises(ProposalValidationError, match="tool results exceed"):
        session.run(_snapshot(include_history=False))

    assert events == ["completed"]
    assert session.provider_calls_used == 2
