from __future__ import annotations

from collections import Counter

import pytest

from scion.core.models import (
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    PairwiseCaseFeedback,
    ProtocolResult,
    StepRecord,
)
from scion.proposal.context_manager.manager import screening_record


def _screening_step(
    *,
    valid_pairs: int,
    candidate_failed_pairs: int,
    failed_pairs: int,
    champion_failed_pairs: int = 0,
    comparisons: tuple[str, ...],
) -> StepRecord:
    counts = Counter(comparisons)
    n_cases = len(comparisons)
    return StepRecord(
        round_num=1,
        branch_id="branch-1",
        hypothesis=HypothesisProposal(
            hypothesis_text="Exercise screening feedback accounting.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/solver.py",
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=n_cases,
                wins=counts["win"],
                losses=counts["loss"],
                ties=counts["tie"],
                win_rate=(counts["win"] / n_cases if n_cases else 0.0),
                median_delta=0.0,
                ci_low=-1.0,
                ci_high=1.0,
                total_pairs=valid_pairs + failed_pairs,
                attempted_pairs=valid_pairs + failed_pairs,
                valid_pairs=valid_pairs,
                failed_pairs=failed_pairs,
                candidate_failed_pairs=candidate_failed_pairs,
                champion_failed_pairs=champion_failed_pairs,
                pair_wins=counts["win"],
                pair_losses=counts["loss"],
                pair_ties=counts["tie"],
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL",),
            exposed_summary="screening feedback accounting",
            raw_metrics_ref="metrics/accounting.json",
            pair_feedback=tuple(
                PairwiseCaseFeedback(
                    case_id=f"case-{index}",
                    seed=index,
                    comparison=comparison,
                    delta=-1.0 if comparison == "loss" else 0.0,
                )
                for index, comparison in enumerate(comparisons, start=1)
            ),
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
        base_champion_version=1,
        base_source_ref="champion:v1",
        changed_files=(),
    )


@pytest.mark.parametrize(
    "step",
    (
        pytest.param(
            _screening_step(
                valid_pairs=2,
                candidate_failed_pairs=1,
                failed_pairs=1,
                comparisons=("win", "tie", "loss"),
            ),
            id="mixed-valid-and-candidate-failure",
        ),
        pytest.param(
            _screening_step(
                valid_pairs=0,
                candidate_failed_pairs=2,
                failed_pairs=2,
                comparisons=("loss", "loss"),
            ),
            id="candidate-failures-only",
        ),
        pytest.param(
            _screening_step(
                valid_pairs=0,
                candidate_failed_pairs=0,
                failed_pairs=2,
                champion_failed_pairs=1,
                comparisons=(),
            ),
            id="champion-shared-and-unknown-invalid-excluded",
        ),
    ),
)
def test_canonical_screening_projection_accepts_protocol_accounting(
    step: StepRecord,
) -> None:
    record = screening_record(step)

    case_outcomes = record["experiment_evidence"].get("case_outcomes", {})
    feedback = case_outcomes.get("pair_feedback", [])
    assert len(feedback) == (
        step.protocol_result.stats.valid_pairs
        + step.protocol_result.stats.candidate_failed_pairs
    )


def test_canonical_screening_projection_accepts_paired_candidate_failure_without_feedback() -> (
    None
):
    step = _screening_step(
        valid_pairs=3,
        candidate_failed_pairs=1,
        failed_pairs=1,
        comparisons=("tie", "tie", "tie"),
    )

    record = screening_record(step)

    feedback = record["experiment_evidence"]["case_outcomes"]["pair_feedback"]
    assert len(feedback) == step.protocol_result.stats.valid_pairs
    assert [item["comparison"] for item in feedback] == ["tie", "tie", "tie"]


def test_canonical_screening_projection_rejects_feedback_accounting_mismatch() -> None:
    step = _screening_step(
        valid_pairs=0,
        candidate_failed_pairs=0,
        failed_pairs=1,
        comparisons=("loss",),
    )

    with pytest.raises(
        ValueError,
        match=(
            "pair feedback cardinality conflicts with "
            "valid/candidate-failure pair counts"
        ),
    ):
        screening_record(step)
