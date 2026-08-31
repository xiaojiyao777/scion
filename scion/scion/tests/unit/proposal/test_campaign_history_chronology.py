from __future__ import annotations

import pytest

from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    Branch,
    BranchState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    ProtocolResult,
    StepRecord,
)
from scion.proposal.context_manager.history_projection import (
    proposal_pre_protocol_observations,
    proposal_screening_history,
)
from scion.proposal.context_manager.manager import campaign_screening_history
from scion.proposal.hypothesis_research_corpus import (
    build_hypothesis_research_corpus,
    latest_live_failure_frontier_refs,
)


def _hypothesis(label: str) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=label,
        change_locus="generic",
        action="modify",
        target_file="operators/local_search.py",
    )


def _pre_protocol_step(round_num: int, branch_id: str, label: str) -> StepRecord:
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=_hypothesis(label),
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="hypothesis_contract",
        failure_detail=None,
        base_champion_version=1,
        base_source_ref="champion:v1",
        changed_files=(),
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code="HYPOTHESIS_CONTRACT_REJECTED",
            provenance={"stage": "hypothesis_contract"},
        ),
    )


def _screening_step(round_num: int, branch_id: str, label: str) -> StepRecord:
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=_hypothesis(label),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=0,
                wins=0,
                losses=0,
                ties=0,
                win_rate=0.0,
                median_delta=0.0,
                ci_low=0.0,
                ci_high=0.0,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL",),
            exposed_summary="screening failed",
            raw_metrics_ref="private/screening.json",
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
        base_champion_version=1,
        base_source_ref="champion:v1",
        changed_files=(),
    )


def _experiment_history_record(
    round_num: int,
    relation: str,
    gate_outcome: str,
) -> dict[str, object]:
    return {
        "latest_round": round_num,
        "relation": relation,
        "proposal_intent": {
            "hypothesis_text": f"{relation} round {round_num} {gate_outcome}"
        },
        "experiment_evidence": {
            "protocol_outcome": {"gate_outcome": gate_outcome}
        },
    }


def test_campaign_history_tool_index_follows_interleaved_step_rounds() -> None:
    current = Branch(
        branch_id="current-branch",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    first = _pre_protocol_step(1, current.branch_id, "current rejection")
    second = _screening_step(2, "sibling-branch", "sibling screening")
    third = _pre_protocol_step(3, "sibling-branch", "sibling rejection")

    pre_protocol = proposal_pre_protocol_observations(
        [first, second, third],
        current_branch_id=current.branch_id,
    )
    screening = proposal_screening_history(
        campaign_screening_history(current, [second])
    )
    context = {
        "prior_research_history": [
            {"hypothesis": {"text": "external line one"}},
            {"hypothesis": {"text": "external line two"}},
        ],
        "pre_protocol_observations": pre_protocol,
        "experiment_history": screening,
    }

    _sources, histories, _compact = build_hypothesis_research_corpus(context)

    assert [entry["ref"] for entry in histories] == [
        "history-0001",
        "history-0002",
        "history-0003",
        "history-0004",
        "history-0005",
    ]
    assert [entry["record"]["hypothesis"]["text"] for entry in histories[:2]] == [
        "external line one",
        "external line two",
    ]
    assert [entry["kind"] for entry in histories[2:]] == [
        "pre_protocol_observations",
        "experiment_history",
        "pre_protocol_observations",
    ]
    assert [entry["index"]["round_num"] for entry in histories[2:]] == [1, 2, 3]
    assert [entry["index"]["relation"] for entry in histories[2:]] == [
        "current",
        "sibling",
        "sibling",
    ]
    assert [entry["record"]["relation"] for entry in histories[2:]] == [
        "current",
        "sibling",
        "sibling",
    ]


def test_live_campaign_history_without_round_metadata_fails_closed() -> None:
    with pytest.raises(ValueError, match="complete positive round metadata"):
        build_hypothesis_research_corpus(
            {
                "prior_research_history": [
                    {"hypothesis": {"text": "external order is independent"}}
                ],
                "pre_protocol_observations": [
                    {"hypothesis": {"hypothesis_text": "missing round"}}
                ],
                "experiment_history": [
                    {
                        "latest_round": 2,
                        "proposal_intent": {"hypothesis_text": "complete"},
                    }
                ],
            }
        )


@pytest.mark.parametrize("relation", [None, "candidate", "CURRENT"])
def test_live_campaign_history_without_ordinary_relation_fails_closed(
    relation: object,
) -> None:
    with pytest.raises(ValueError, match="current/sibling relation"):
        build_hypothesis_research_corpus(
            {
                "experiment_history": [
                    {
                        "latest_round": 1,
                        "relation": relation,
                        "proposal_intent": {"hypothesis_text": "invalid relation"},
                        "experiment_evidence": {
                            "protocol_outcome": {"gate_outcome": "fail"}
                        },
                    }
                ]
            }
        )


def test_failure_frontier_refs_share_the_ordinary_history_chronology() -> None:
    context = {
        "prior_research_history": [
            {"hypothesis": {"text": "external history is not a live failure"}}
        ],
        "pre_protocol_observations": [
            {
                "round_num": 1,
                "relation": "current",
                "hypothesis": {"hypothesis_text": "earlier live failure"},
            },
            {
                "round_num": 3,
                "relation": "current",
                "hypothesis": {"hypothesis_text": "latest contract failure"},
            },
        ],
        "experiment_history": [
            {
                "latest_round": 3,
                "relation": "current",
                "proposal_intent": {"hypothesis_text": "latest measured failure"},
                "experiment_evidence": {"protocol_outcome": {"gate_outcome": "fail"}},
            }
        ],
    }

    _sources, histories, _compact = build_hypothesis_research_corpus(context)

    assert [
        (entry["ref"], entry["kind"], entry["index"].get("round_num"))
        for entry in histories
    ] == [
        ("history-0001", "prior_research_history", None),
        ("history-0002", "pre_protocol_observations", 1),
        ("history-0003", "pre_protocol_observations", 3),
        ("history-0004", "experiment_history", 3),
    ]
    assert latest_live_failure_frontier_refs(context) == (
        "history-0003",
        "history-0004",
    )


def test_newer_sibling_pass_does_not_hide_current_failure() -> None:
    context = {
        "experiment_history": [
            _experiment_history_record(1, "current", "fail"),
            _experiment_history_record(2, "sibling", "pass"),
        ]
    }

    assert latest_live_failure_frontier_refs(context) == ("history-0001",)


def test_newer_current_pass_does_not_hide_sibling_failure() -> None:
    context = {
        "experiment_history": [
            _experiment_history_record(1, "sibling", "fail"),
            _experiment_history_record(2, "current", "pass"),
        ]
    }

    assert latest_live_failure_frontier_refs(context) == ("history-0001",)


def test_later_pass_closes_an_older_failure_in_the_same_relation() -> None:
    context = {
        "experiment_history": [
            _experiment_history_record(1, "current", "fail"),
            _experiment_history_record(2, "current", "pass"),
        ]
    }

    assert latest_live_failure_frontier_refs(context) == ()
