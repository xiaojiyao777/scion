from __future__ import annotations

from scion.core.models import (
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    ProtocolResult,
    StepRecord,
)
from scion.core.runtime_budget_diagnostics import SCREENING_RUNTIME_BUDGET_SATURATION
from scion.proposal.context_manager.runtime import _build_runtime_feedback


def test_runtime_feedback_adds_generic_diversity_guidance_for_budget_saturation() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a bounded follow-up.",
        target_weakness="Prior attempts are tie dominated.",
        expected_effect="Improve objective.",
        change_locus="solver_design",
        target_file="policies/baseline_algorithm.py",
        action="modify",
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=8,
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            runtime_ratio_median=1.0,
            runtime_delta_median_ms=0.0,
            runtime_regression_rate=0.0,
            runtime_pairs=8,
        ),
        gate_outcome="fail",
        reason_codes=(SCREENING_RUNTIME_BUDGET_SATURATION,),
        exposed_summary="tie dominated",
        raw_metrics_ref="internal/metrics.json",
        candidate_surface_runtime_summary={
            "runtime_budget_diagnostic": {
                "code": SCREENING_RUNTIME_BUDGET_SATURATION,
                "stage": "screening",
                "total_pairs": 8,
            }
        },
    )
    step = StepRecord(
        round_num=3,
        branch_id="branch-1",
        hypothesis=hypothesis,
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=protocol,
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
    )

    feedback = _build_runtime_feedback([step])

    assert "Recent runtime budget saturation diagnostics" in feedback
    assert SCREENING_RUNTIME_BUDGET_SATURATION in feedback
    assert "Avoid stacking another homogeneous high-cost variant" in feedback
    assert "mechanism family" in feedback
    assert "trigger condition" in feedback
    assert "evaluation observability" in feedback


def test_runtime_feedback_escalates_repeated_budget_saturation() -> None:
    steps = []
    for round_num in range(1, 4):
        hypothesis = HypothesisProposal(
            hypothesis_text=f"Try bounded follow-up {round_num}.",
            target_weakness="Prior attempts are tie dominated.",
            expected_effect="Improve objective.",
            change_locus="algorithm_design",
            target_file=f"policies/policy_{round_num}.py",
            action="modify",
        )
        protocol = ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=8,
                wins=0,
                losses=0,
                ties=8,
                win_rate=0.0,
                median_delta=0.0,
                ci_low=0.0,
                ci_high=0.0,
                runtime_pairs=8,
            ),
            gate_outcome="fail",
            reason_codes=(SCREENING_RUNTIME_BUDGET_SATURATION,),
            exposed_summary="tie dominated",
            raw_metrics_ref="internal/metrics.json",
            candidate_surface_runtime_summary={
                "runtime_budget_diagnostic": {
                    "code": SCREENING_RUNTIME_BUDGET_SATURATION,
                    "stage": "screening",
                    "total_pairs": 8,
                }
            },
        )
        steps.append(
            StepRecord(
                round_num=round_num,
                branch_id="branch-1",
                hypothesis=hypothesis,
                patch=None,
                contract_passed=True,
                verification_passed=True,
                protocol_result=protocol,
                decision=Decision.CONTINUE_EXPLORE,
                failure_stage=None,
                failure_detail=None,
            )
        )

    feedback = _build_runtime_feedback(steps)

    assert "Runtime-saturated plateau control" in feedback
    assert "`runtime_budget_strategy`" in feedback
    assert "reduces candidate work" in feedback
    assert "changes the runtime-pressure pathway" in feedback
