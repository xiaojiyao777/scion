from __future__ import annotations

import inspect

from scion.core.models import (
    Branch,
    BranchState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    MechanismChange,
    PairwiseCaseFeedback,
    ProtocolResult,
    StepRecord,
)
from scion.proposal.context import branch_dossier as branch_dossier_module
from scion.proposal.context.branch_dossier import (
    build_branch_dossier,
    render_branch_dossier,
)


def _step(round_num: int, *, wins: int, pair_wins: int = 0) -> StepRecord:
    stats = EvalStats(
        n_cases=4,
        wins=wins,
        losses=0,
        ties=4 - wins,
        win_rate=wins / 4,
        median_delta=0.1 if wins else 0.0,
        ci_low=0.0,
        ci_high=0.1,
        runtime_ratio_median=1.0,
        runtime_delta_median_ms=0.0,
        runtime_regression_rate=0.0,
        runtime_pairs=4,
    )
    return StepRecord(
        round_num=round_num,
        branch_id="branch-a",
        hypothesis=HypothesisProposal(
            hypothesis_text="Tune a bounded assignment refinement.",
            change_locus="assignment_policy",
            action="modify",
            target_file="policies/assignment.py",
            mechanism_changes=(
                MechanismChange(id="bounded_assignment_refine", change_type="modify"),
            ),
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=stats,
            gate_outcome="continue",
            reason_codes=(
                "SCREENING_WEAK_SIGNAL_CONTINUE",
                "SCREENING_RUNTIME_BUDGET_SATURATION",
                "SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
            ),
            exposed_summary="screening summary",
            raw_metrics_ref="/redacted/internal.json",
            pair_feedback=tuple(
                PairwiseCaseFeedback(
                    case_id=f"case-{idx}",
                    seed=idx,
                    comparison="win" if idx < pair_wins else "tie",
                    delta=0.01 if idx < pair_wins else 0.0,
                )
                for idx in range(4)
            ),
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
        decision_reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
    )


def test_branch_dossier_is_generic_tainted_feedback() -> None:
    branch = Branch(
        branch_id="branch-a",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash",
        direction="assignment_policy: bounded assignment refinement",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
        last_telemetry_outcome="evaluated_no_effect",
        branch_mechanism_ids=("bounded_assignment_refine",),
    )

    dossier = build_branch_dossier(branch, [_step(1, wins=1, pair_wins=2)])
    rendered = render_branch_dossier(dossier)

    assert dossier["taint"] == "proposal_research_feedback"
    assert dossier["decision_input_policy"] == "excluded_from_decision_features"
    assert dossier["branch_id"] == "branch-a"
    assert dossier["mechanisms"] == ["bounded_assignment_refine"]
    assert dossier["best_screening_signal"]["case_summary"]["wins"] == 1
    assert dossier["runtime_budget_diagnostics"]
    assert dossier["telemetry_diagnostics"]
    assert "Which observed signal should this follow-up preserve?" in rendered
    assert "What minimal refinement should test the branch-local explanation?" in rendered

    forbidden = ("cvrp", "route", "alns", "vns", "capacity", "demand", "fleet")
    lowered = rendered.lower()
    for term in forbidden:
        assert term not in lowered


def test_branch_dossier_module_has_no_problem_specific_control_terms() -> None:
    source = inspect.getsource(branch_dossier_module).lower()

    for term in ("cvrp", "route", "alns", "vns", "capacity", "demand", "fleet"):
        assert term not in source
