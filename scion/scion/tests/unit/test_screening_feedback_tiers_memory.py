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
from scion.core.branch_lifecycle_policy import (
    SCREENING_MARGINAL_SIGNAL_CONTINUE,
    SCREENING_NEUTRAL_SIGNAL_CONTINUE,
    SCREENING_WEAK_SIGNAL_CONTINUE,
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
    runtime_pairs: int | None = None,
    ci_low: float = 0.0,
    ci_high: float = 0.0,
) -> EvalStats:
    n_cases = wins + losses + ties
    resolved_runtime_pairs = n_cases if runtime_pairs is None else runtime_pairs
    return EvalStats(
        n_cases=n_cases,
        wins=wins,
        losses=losses,
        ties=ties,
        win_rate=wins / n_cases if n_cases else 0.0,
        median_delta=median_delta,
        ci_low=ci_low,
        ci_high=ci_high,
        runtime_delta_median_ms=runtime_delta_median_ms,
        runtime_ratio_median=runtime_ratio_median,
        runtime_regression_rate=runtime_regression_rate,
        runtime_pairs=resolved_runtime_pairs,
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
    runtime_regression_rate: float | None = None,
    runtime_pairs: int | None = None,
    ci_low: float = 0.0,
    ci_high: float = 0.0,
    candidate_operator_attempts: int = 1,
    candidate_surface_runtime_summary: dict | None = None,
    gate_outcome: str = "fail",
    reason_codes: tuple[str, ...] = ("SCREENING_FAIL_WIN_RATE",),
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
            runtime_regression_rate=runtime_regression_rate,
            runtime_pairs=runtime_pairs,
            ci_low=ci_low,
            ci_high=ci_high,
        ),
        gate_outcome=gate_outcome,
        reason_codes=reason_codes,
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

    marginal_pass = screening_feedback_summary(
        _protocol(
            case_wins=7,
            case_losses=1,
            case_ties=2,
            median_delta=0.0,
            gate_outcome="pass",
            reason_codes=("SCREENING_PASS_MARGINAL_DELTA",),
        ),
        decision_reason_codes=("SCREENING_PASS_MARGINAL_DELTA",),
    )
    assert marginal_pass.tier == "marginal"
    assert marginal_pass.repeat_unchanged_allowed is False
    assert marginal_pass.allowed_followup_variants == (
        "trigger",
        "schedule",
        "threshold",
        "composition",
    )
    assert "SCREENING_PASS_MARGINAL_DELTA" in marginal_pass.why_not_promoted
    assert marginal_pass.gate_observation_reason_codes == (
        "SCREENING_PASS_MARGINAL_DELTA",
    )

    stale_negative_marginal_pass = screening_feedback_summary(
        _protocol(
            case_wins=7,
            case_losses=1,
            case_ties=2,
            median_delta=-0.01,
            gate_outcome="pass",
            reason_codes=("SCREENING_PASS_MARGINAL_DELTA",),
        ),
        decision_reason_codes=("SCREENING_PASS_MARGINAL_DELTA",),
    )
    assert stale_negative_marginal_pass.tier == "quality_regression"

    weak_positive = screening_feedback_summary(
        _protocol(
            case_wins=4,
            case_losses=1,
            case_ties=7,
            ci_low=0.0,
            ci_high=4.0,
        ),
        decision_reason_codes=(
            "SCREENING_FAIL_WIN_RATE",
            SCREENING_WEAK_SIGNAL_CONTINUE,
        ),
    )
    assert weak_positive.tier == "weak_positive"
    assert weak_positive.gate_observation_reason_codes == (
        "SCREENING_FAIL_WIN_RATE",
    )
    assert weak_positive.lifecycle_action_reason_codes == (
        SCREENING_WEAK_SIGNAL_CONTINUE,
    )

    marginal = screening_feedback_summary(
        _protocol(
            case_wins=3,
            case_losses=3,
            case_ties=6,
            ci_low=-0.5,
            ci_high=0.5,
        ),
        decision_reason_codes=(
            "SCREENING_FAIL_WIN_RATE",
            SCREENING_MARGINAL_SIGNAL_CONTINUE,
        ),
    )
    assert marginal.tier == "marginal"
    assert "not a weak-positive exploit signal" in marginal.why_not_promoted
    assert marginal.gate_observation_reason_codes == ("SCREENING_FAIL_WIN_RATE",)
    assert marginal.lifecycle_action_reason_codes == (
        SCREENING_MARGINAL_SIGNAL_CONTINUE,
    )

    no_effect = screening_feedback_summary(
        _protocol(case_wins=0, case_losses=0, case_ties=8),
        decision_reason_codes=(
            "SCREENING_FAIL_WIN_RATE",
            SCREENING_NEUTRAL_SIGNAL_CONTINUE,
        ),
    )
    assert no_effect.tier == "no_effect"
    assert no_effect.gate_observation_reason_codes == ("SCREENING_FAIL_WIN_RATE",)
    assert no_effect.lifecycle_action_reason_codes == (
        SCREENING_NEUTRAL_SIGNAL_CONTINUE,
    )

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
            runtime_regression_rate=1.0,
        )
    ).tier == "runtime_regression"


def test_budget_exhausting_runtime_rate_does_not_drive_screening_tier() -> None:
    summary = screening_feedback_summary(
        _protocol(
            case_wins=0,
            case_losses=0,
            case_ties=8,
            runtime_delta_median_ms=29.0,
            runtime_ratio_median=1.18,
            runtime_regression_rate=1.0,
            candidate_surface_runtime_summary={
                "runtime_budget_diagnostic": {
                    "runtime_model": "budget_exhausting",
                    "severity": "info",
                },
            },
        )
    )

    assert summary.tier == "no_effect"
    runtime_summary = summary.runtime_summary_payload()
    assert runtime_summary["runtime_regression_rate"] == 1.0
    assert runtime_summary["runtime_model"] == "budget_exhausting"
    assert (
        runtime_summary["runtime_regression_rate_interpretation"]
        == "not_applicable_budget_exhausting"
    )
    assert summary.phase_causal_summary["runtime_evidence"]["runtime_model"] == (
        "budget_exhausting"
    )


def test_two_case_runtime_noise_is_low_confidence_not_runtime_regression() -> None:
    summary = screening_feedback_summary(
        _protocol(
            case_wins=0,
            case_losses=0,
            case_ties=2,
            runtime_delta_median_ms=29.0,
            runtime_ratio_median=1.18,
            runtime_regression_rate=1.0,
            runtime_pairs=2,
        )
    )

    assert summary.tier == "no_effect"
    assert summary.runtime_confidence == "low_sample_diagnostic"
    assert summary.opportunity_status == "opportunity_poor"
    assert any("tiny sample" in item for item in summary.opportunity_diagnostics)


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


def test_hook_activation_without_inner_mechanism_evidence_is_opportunity_diagnostic() -> None:
    summary = screening_feedback_summary(
        _protocol(
            case_wins=0,
            case_losses=0,
            case_ties=8,
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "telemetry_guard": {
                    "passed": True,
                    "mechanism_diagnostics": [
                        {
                            "mechanism": "scheduler_hook",
                            "activation_status": "observed",
                            "effect_status": "zero",
                        },
                        {
                            "mechanism": "route_pair_exchange",
                            "activation_status": "missing",
                            "effect_status": "unknown",
                            "diagnostic_kind": "not_evaluated/not_triggered",
                        },
                    ],
                    "mechanism_opportunity_diagnostics": [
                        {
                            "summary": (
                                "screening opportunity-poor for route-pair exchange"
                            ),
                        }
                    ],
                },
            },
        )
    )

    assert summary.tier == "no_effect"
    assert summary.activation_status == "observed"
    assert summary.mechanism_evidence["hook_activation_observed"] is True
    assert summary.mechanism_evidence["primary_mechanism"] == "route_pair_exchange"
    assert summary.opportunity_status == "opportunity_poor"
    assert any("route-pair" in item for item in summary.opportunity_diagnostics)
    assert any("primary mechanism" in item for item in summary.opportunity_diagnostics)


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
    assert "screening_gate_reason:" in rendered
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
    assert "screening_gate_reason=" in rendered
    assert "repeat_unchanged_allowed=false" in rendered
    assert "allowed_followup_variants=trigger,schedule,threshold,composition" in rendered
    assert "raw_metrics" not in rendered
    assert "SECRET" not in rendered


def test_branch_local_memory_keeps_marginal_diagnostic_pass() -> None:
    memory = CampaignSearchMemory()
    step = _step(
        _protocol(
            case_wins=7,
            case_losses=1,
            case_ties=2,
            pair_wins=7,
            pair_losses=1,
            pair_ties=2,
            median_delta=0.0,
            gate_outcome="pass",
            reason_codes=("SCREENING_PASS_MARGINAL_DELTA",),
        )
    )

    memory.update(step)
    entry = memory.branch_mechanism_memory["branch-tier"][-1]
    rendered = memory.render(view="hypothesis", branch_id="branch-tier")

    assert entry.tier == "marginal"
    assert entry.case_wins == 7
    assert entry.repeat_unchanged_allowed is False
    assert entry.allowed_followup_variants == (
        "trigger",
        "schedule",
        "threshold",
        "composition",
    )
    assert "SCREENING_PASS_MARGINAL_DELTA" in entry.why_not_promoted
    assert "screening_gate_reason=SCREENING_PASS_MARGINAL_DELTA" in rendered
