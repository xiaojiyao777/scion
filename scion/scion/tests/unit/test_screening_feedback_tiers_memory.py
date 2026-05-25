from __future__ import annotations

from scion.core.models import (
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    MechanismChange,
    PairwiseCaseFeedback,
    ProtocolResult,
    StepRecord,
)
from scion.proposal.context.feedback import _build_experiment_history
from scion.proposal.screening_feedback import screening_feedback_summary
from scion.proposal.search_memory import CampaignSearchMemory


def _stats(
    *,
    wins: int,
    losses: int,
    ties: int,
    median_delta: float = 0.0,
    runtime_delta_median_ms: float | None = None,
    runtime_ratio_median: float | None = None,
    runtime_regression_rate: float | None = None,
) -> EvalStats:
    n_cases = wins + losses + ties
    return EvalStats(
        n_cases=n_cases,
        wins=wins,
        losses=losses,
        ties=ties,
        win_rate=wins / n_cases if n_cases else 0.0,
        median_delta=median_delta,
        ci_low=0.0,
        ci_high=0.0,
        runtime_delta_median_ms=runtime_delta_median_ms,
        runtime_ratio_median=runtime_ratio_median,
        runtime_regression_rate=runtime_regression_rate,
        runtime_pairs=n_cases,
        total_pairs=n_cases,
        attempted_pairs=n_cases,
        valid_pairs=n_cases,
    )


def _pairs(wins: int, losses: int, ties: int) -> tuple[PairwiseCaseFeedback, ...]:
    comparisons = ["win"] * wins + ["loss"] * losses + ["tie"] * ties
    return tuple(
        PairwiseCaseFeedback(
            case_id=f"case-{idx}",
            seed=idx,
            comparison=comparison,
            delta=1.0 if comparison == "win" else -1.0 if comparison == "loss" else 0.0,
        )
        for idx, comparison in enumerate(comparisons)
    )


def _protocol(
    *,
    case_wins: int,
    case_losses: int,
    case_ties: int,
    pair_wins: int | None = None,
    pair_losses: int | None = None,
    pair_ties: int | None = None,
    median_delta: float = 0.0,
    runtime_delta_median_ms: float | None = None,
    runtime_ratio_median: float | None = None,
    candidate_operator_attempts: int = 1,
    candidate_surface_runtime_summary: dict | None = None,
) -> ProtocolResult:
    pair_wins = case_wins if pair_wins is None else pair_wins
    pair_losses = case_losses if pair_losses is None else pair_losses
    pair_ties = case_ties if pair_ties is None else pair_ties
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=_stats(
            wins=case_wins,
            losses=case_losses,
            ties=case_ties,
            median_delta=median_delta,
            runtime_delta_median_ms=runtime_delta_median_ms,
            runtime_ratio_median=runtime_ratio_median,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening aggregate summary",
        raw_metrics_ref="/SECRET/raw/screening_metrics.json",
        pair_feedback=_pairs(pair_wins, pair_losses, pair_ties),
        candidate_operator_attempts=candidate_operator_attempts,
        candidate_surface_runtime_summary=candidate_surface_runtime_summary or {},
    )


def _step(protocol: ProtocolResult) -> StepRecord:
    return StepRecord(
        round_num=3,
        branch_id="branch-tier",
        hypothesis=HypothesisProposal(
            hypothesis_text="Tune bounded late operator trigger.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_algorithm.py",
            mechanism_changes=(
                MechanismChange(id="late_operator_trigger", change_type="modify"),
            ),
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=protocol,
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )


def test_screening_feedback_tiers_classify_external_aps_patterns() -> None:
    assert screening_feedback_summary(
        _protocol(case_wins=2, case_losses=1, case_ties=5)
    ).tier == "weak_positive"

    assert screening_feedback_summary(
        _protocol(case_wins=0, case_losses=0, case_ties=8)
    ).tier == "no_effect"

    assert screening_feedback_summary(
        _protocol(
            case_wins=1,
            case_losses=1,
            case_ties=6,
            median_delta=-0.5,
            runtime_delta_median_ms=-33.0,
            runtime_ratio_median=0.85,
        )
    ).tier == "quality_regression"

    assert screening_feedback_summary(
        _protocol(
            case_wins=0,
            case_losses=0,
            case_ties=8,
            runtime_delta_median_ms=29.0,
            runtime_ratio_median=1.18,
        )
    ).tier == "runtime_regression"


def test_screening_feedback_treats_observed_activation_zero_effect_as_no_effect() -> None:
    summary = screening_feedback_summary(
        _protocol(
            case_wins=0,
            case_losses=0,
            case_ties=8,
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "telemetry_guard": {
                    "passed": True,
                    "warnings": [
                        {
                            "code": "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
                            "severity": "warn",
                            "category": "effect",
                            "diagnostic_type": (
                                "mechanism_executed_no_improvement"
                            ),
                            "telemetry_outcome": "no_effect",
                        }
                    ],
                    "mechanism_diagnostics": [
                        {
                            "mechanism": "late_operator_trigger",
                            "activation_status": "observed",
                            "effect_status": "zero",
                            "diagnostic_type": (
                                "mechanism_executed_no_improvement"
                            ),
                            "telemetry_outcome": "no_effect",
                            "activation_observed": True,
                        }
                    ],
                },
            },
        )
    )

    assert summary.tier == "no_effect"
    assert summary.activation_status == "observed"
    assert summary.effect_status == "no_objective_effect"
    assert summary.repeat_unchanged_allowed is False


def test_experiment_history_renders_tier_pair_and_case_feedback() -> None:
    step = _step(
        _protocol(
            case_wins=2,
            case_losses=1,
            case_ties=5,
            pair_wins=5,
            pair_losses=3,
            pair_ties=8,
        )
    )

    rendered = _build_experiment_history([step], step.branch_id)

    assert "screening_feedback.tier=weak_positive" in rendered
    assert "pair_wins=5" in rendered
    assert "case_wins=2" in rendered
    assert "why_not_promoted:" in rendered
    assert "weak_positive is not promotable" in rendered
    assert "allowed_followup_variants: trigger, schedule, threshold, composition" in rendered
    assert "SECRET" not in rendered
    assert "raw_metrics" not in rendered


def test_branch_local_memory_blocks_unchanged_weak_positive_repeat() -> None:
    memory = CampaignSearchMemory()
    step = _step(
        _protocol(
            case_wins=2,
            case_losses=1,
            case_ties=5,
            pair_wins=5,
            pair_losses=3,
            pair_ties=8,
            runtime_delta_median_ms=22.0,
            runtime_ratio_median=1.04,
        )
    )

    memory.update(step)
    entry = memory.branch_mechanism_memory["branch-tier"][-1]
    rendered = memory.render(view="hypothesis", branch_id="branch-tier")

    assert entry.mechanism_id == "late_operator_trigger"
    assert entry.tier == "weak_positive"
    assert entry.case_wins == 2
    assert entry.pair_wins == 5
    assert entry.repeat_unchanged_allowed is False
    assert entry.allowed_followup_variants == (
        "trigger",
        "schedule",
        "threshold",
        "composition",
    )
    assert "Near-Field Mechanism Memory" in rendered
    assert "why_not_promoted=" in rendered
    assert "repeat_unchanged_allowed=false" in rendered
    assert "allowed_followup_variants=trigger,schedule,threshold,composition" in rendered
    assert "raw_metrics" not in rendered
    assert "SECRET" not in rendered
