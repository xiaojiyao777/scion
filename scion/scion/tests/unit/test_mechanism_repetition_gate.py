from __future__ import annotations

from scion.core.models import (
    Branch,
    BranchState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    MechanismChange,
    ProtocolResult,
    StepRecord,
)
from scion.proposal.mechanism_novelty import MechanismNoveltyGate
from scion.proposal.tools import ProposalToolContext


def _hypothesis(
    mechanism_id: str,
    *,
    text: str = "Add targeted multi relocate to improve total_distance.",
) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness="Prior local search missed this relocation pattern.",
        expected_effect="Improve total_distance.",
        mechanism_changes=(MechanismChange(id=mechanism_id, change_type="add"),),
        novelty_signature={
            "algorithm_family": "targeted_multi_relocate",
            "improvement_strategy": mechanism_id,
            "acceptance_strategy": "preserve_existing_acceptance",
            "runtime_budget_strategy": "bounded_pairs",
        },
    )


def _screening_result(*, win_rate: float = 0.0) -> ProtocolResult:
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=16,
            wins=0,
            losses=0,
            ties=16,
            win_rate=win_rate,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/metrics.json",
    )


def _step(hypothesis: HypothesisProposal) -> StepRecord:
    return StepRecord(
        round_num=2,
        branch_id="branch-1",
        hypothesis=hypothesis,
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=_screening_result(),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
        decision_reason_codes=("SCREENING_FAIL_WIN_RATE",),
    )


def _context(*steps: StepRecord) -> ProposalToolContext:
    return ProposalToolContext(
        session_id="session",
        campaign_id="campaign",
        branch=Branch("branch-1", BranchState.EXPLORE, 1, "champ"),
        step_history=steps,
    )


def test_repeated_mechanism_id_is_blocked_before_code_generation() -> None:
    previous = _hypothesis("targeted_multi_relocate")
    candidate = _hypothesis("targeted_multi_relocate")

    result = MechanismNoveltyGate().evaluate(
        candidate,
        context=_context(_step(previous)),
    )

    assert result is not None
    assert result.premise_check == "duplicate"
    assert result.failure_category == "repeated_mechanism"
    assert result.mechanism == "targeted_multi_relocate"
    assert "SCREENING_FAIL_WIN_RATE" in result.reason


def test_materially_different_repeated_mechanism_is_allowed() -> None:
    previous = _hypothesis("acceptance_reheat")
    candidate = _hypothesis(
        "acceptance_reheat",
        text=(
            "Add acceptance reheat with a materially different trigger based on "
            "runtime budget under-spend rather than plateau length."
        ),
    )

    result = MechanismNoveltyGate().evaluate(
        candidate,
        context=_context(_step(previous)),
    )

    assert result is None
