from __future__ import annotations

from scion.core.models import MechanismChange
from scion.proposal.screening_feedback import screening_feedback_summary
from scion.proposal.context.feedback import _build_experiment_history
from scion.tests.unit.agentic_feedback_test_support import *

def test_feedback_query_screening_distinguishes_pair_and_case_win_rates(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    pair_results = ["win"] * 2 + ["tie"] * 12 + ["loss"] * 2
    r2_like_step = replace(
        context.step_history[0],
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(n_cases=4, wins=0, losses=0, ties=4, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="case-level gate failed",
            raw_metrics_ref="/SECRET/raw/r2-like.json",
            champion_cache_hits=1,
            champion_cache_misses=2,
            champion_cached_runtime_pairs=3,
            runtime_confidence="low_cached_champion",
            opportunity_status="opportunity_poor",
            opportunity_diagnostics=("primary mechanism did not trigger",),
            mechanism_evidence={
                "primary_mechanism": "candidate_list",
                "primary_activation_status": "missing",
            },
            pair_feedback=tuple(
                PairwiseCaseFeedback(
                    case_id=f"case-{idx // 4}",
                    seed=idx,
                    comparison=result,
                    delta=(
                        1.0
                        if result == "win"
                        else -1.0
                        if result == "loss"
                        else 0.0
                    ),
                )
                for idx, result in enumerate(pair_results)
            ),
        ),
    )
    context = replace(context, step_history=(r2_like_step,))

    observation = registry.call("feedback.query_screening", {}, context)
    rendered = json.dumps(observation.structured_payload, sort_keys=True)
    row = observation.structured_payload["screening_steps"][0]

    assert row["screening_case_win_rate"] == 0.0
    assert row["screening_gate_win_rate"] == 0.0
    assert row["screening_win_rate_scope"] == "case_level_gate"
    assert row["screening_pair_wins"] == 2
    assert row["screening_pair_losses"] == 2
    assert row["screening_pair_ties"] == 12
    assert row["screening_pair_win_rate"] == 0.125
    assert row["screening_feedback_tier"] == "weak_positive"
    assert row["screening_feedback"]["tier"] == "weak_positive"
    assert row["case_feedback_summary"] == {
        "wins": 0,
        "losses": 0,
        "ties": 4,
        "total": 4,
    }
    assert row["pair_feedback_summary"] == {
        "wins": 2,
        "losses": 2,
        "ties": 12,
        "total": 16,
    }
    assert row["champion_result_cache"] == {
        "hits": 1,
        "misses": 2,
        "cached_runtime_pairs": 3,
    }
    assert row["runtime_confidence"] == "low_cached_champion"
    assert row["opportunity_status"] == "opportunity_poor"
    assert row["opportunity_diagnostics"] == ["primary mechanism did not trigger"]
    assert row["mechanism_evidence"]["primary_mechanism"] == "candidate_list"
    assert row["screening_feedback"]["runtime_confidence"] == "low_cached_champion"
    assert row["screening_feedback"]["repeat_unchanged_allowed"] is False
    assert "weak_positive is not promotable" in row["screening_feedback"][
        "why_not_promoted"
    ]
    assert "SECRET" not in rendered
    assert "raw_metrics_ref" not in rendered


def test_feedback_query_screening_marks_budget_exhausting_runtime_as_report_only(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    budget_exhausting_step = replace(
        context.step_history[0],
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(
                n_cases=8,
                wins=0,
                losses=0,
                ties=8,
                win_rate=0.0,
                median_delta=0.0,
                runtime_ratio_median=1.18,
                runtime_delta_median_ms=29.0,
                runtime_regression_rate=1.0,
                runtime_pairs=8,
                total_pairs=8,
                attempted_pairs=8,
                valid_pairs=8,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="case-level gate failed",
            raw_metrics_ref="/SECRET/raw/budget.json",
            candidate_surface_runtime_summary={
                "runtime_budget_diagnostic": {
                    "runtime_model": "budget_exhausting",
                    "severity": "info",
                },
            },
            pair_feedback=tuple(
                PairwiseCaseFeedback(
                    case_id=f"case-{idx}",
                    seed=idx,
                    comparison="tie",
                    delta=0.0,
                )
                for idx in range(8)
            ),
        ),
    )
    context = replace(context, step_history=(budget_exhausting_step,))

    summary = screening_feedback_summary(budget_exhausting_step.protocol_result)
    observation = registry.call("feedback.query_screening", {}, context)
    row = observation.structured_payload["screening_steps"][0]
    runtime_summary = row["screening_feedback"]["runtime_summary"]
    runtime_evidence = row["screening_feedback"]["phase_causal_summary"][
        "runtime_evidence"
    ]

    assert summary.tier == "no_effect"
    assert row["screening_feedback_tier"] == "no_effect"
    assert runtime_summary["runtime_regression_rate"] == 1.0
    assert runtime_summary["runtime_model"] == "budget_exhausting"
    assert (
        runtime_summary["runtime_regression_rate_interpretation"]
        == "not_applicable_budget_exhausting"
    )
    assert runtime_evidence["runtime_model"] == "budget_exhausting"
    assert (
        runtime_evidence["runtime_regression_rate_interpretation"]
        == "not_applicable_budget_exhausting"
    )


def test_screening_feedback_exposes_bounded_phase_causal_summary(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    positive_guard = {
        "telemetry_guard": {
            "passed": True,
            "mechanism_diagnostics": [
                {
                    "mechanism": "generic_phase",
                    "activation_status": "observed",
                    "runtime_status": "observed",
                    "effect_status": "observed",
                }
            ],
        }
    }
    pair_win_case_tie = replace(
        context.step_history[0],
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(
                n_cases=4,
                wins=0,
                losses=0,
                ties=4,
                win_rate=0.0,
                median_delta=0.0,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="case-level gate failed",
            raw_metrics_ref="/SECRET/raw/pair-win.json",
            candidate_surface_runtime_summary=positive_guard,
            pair_feedback=(
                PairwiseCaseFeedback("case-a", 1, "win", 1.0),
                PairwiseCaseFeedback("case-a", 2, "tie", 0.0),
            ),
        ),
    )
    final_loss = replace(
        context.step_history[0],
        round_num=2,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(
                n_cases=2,
                wins=0,
                losses=1,
                ties=1,
                win_rate=0.0,
                median_delta=-1.0,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="loss signal",
            raw_metrics_ref="/SECRET/raw/loss.json",
            candidate_surface_runtime_summary=positive_guard,
            pair_feedback=(
                PairwiseCaseFeedback("case-b", 1, "loss", -1.0),
            ),
        ),
    )
    zero_effect = replace(
        context.step_history[0],
        round_num=3,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(
                n_cases=2,
                wins=0,
                losses=0,
                ties=2,
                win_rate=0.0,
                median_delta=0.0,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="zero effect",
            raw_metrics_ref="/SECRET/raw/zero.json",
            candidate_surface_runtime_summary=positive_guard,
            pair_feedback=(
                PairwiseCaseFeedback("case-c", 1, "tie", 0.0),
            ),
        ),
    )
    context = replace(
        context,
        step_history=(pair_win_case_tie, final_loss, zero_effect),
    )

    pair_summary = screening_feedback_summary(pair_win_case_tie.protocol_result)
    loss_summary = screening_feedback_summary(final_loss.protocol_result)
    zero_summary = screening_feedback_summary(zero_effect.protocol_result)

    assert pair_summary.phase_causal_summary["classification"] == (
        "phase_positive_pair_win_case_tie"
    )
    assert "case-level evidence remained tied" in (
        pair_summary.phase_causal_summary["summary"]
    )
    assert loss_summary.phase_causal_summary["classification"] == (
        "phase_positive_final_objective_loss"
    )
    assert "final objective evidence had a loss signal" in (
        loss_summary.phase_causal_summary["summary"]
    )
    assert zero_summary.phase_causal_summary["classification"] == (
        "zero_effect_activation"
    )
    assert zero_summary.phase_causal_summary["decision_features_excluded"] is True

    screening_observation = registry.call("feedback.query_screening", {}, context)
    row_summary = screening_observation.structured_payload["screening_steps"][0][
        "screening_feedback"
    ]["phase_causal_summary"]
    assert row_summary["classification"] == "zero_effect_activation"
    assert row_summary["proposal_visibility_only"] is True
    assert "SECRET" not in json.dumps(
        screening_observation.structured_payload,
        sort_keys=True,
    )

    runtime_observation = registry.call("feedback.query_runtime", {}, context)
    runtime_rows = runtime_observation.structured_payload[
        "screening_phase_causal_summaries"
    ]
    assert runtime_rows[0]["phase_causal_summary"]["classification"] == (
        "zero_effect_activation"
    )
    assert runtime_observation.structured_payload["runtime_observation_status"][
        "active_phase_causal_summary_count"
    ] == 3


def test_feedback_query_screening_exposes_typed_telemetry_details(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    telemetry_step = replace(
        context.step_history[0],
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(n_cases=4, wins=0, losses=0, ties=4, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("SCREENING_TELEMETRY_FAILED", "SCREENING_FAIL_WIN_RATE"),
            exposed_summary="typed telemetry guard failed",
            raw_metrics_ref="/SECRET/raw/telemetry.json",
            candidate_surface_runtime_summary={
                "selected_surface": "generic_surface",
                "telemetry_guard": {
                    "passed": False,
                    "declaration_source_digest": "guard-digest-feedback",
                    "failures": [
                        {
                            "code": "TELEMETRY_ACTIVITY_NOT_OBSERVED",
                            "severity": "fail",
                            "category": "activity",
                            "mechanism": "activity_probe",
                            "field": "activity_counter",
                            "runtime_role": "activity",
                            "candidate_present": 4,
                            "candidate_positive": 0,
                        }
                    ],
                },
            },
        ),
    )
    context = replace(context, step_history=(telemetry_step,))

    observation = registry.call("feedback.query_screening", {}, context)
    row = observation.structured_payload["screening_steps"][0]
    detail = row["telemetry_failure_details"][0]

    assert row["telemetry_guard_failed"] is True
    assert row["telemetry_failure_categories"] == ["activity"]
    assert detail["schema"] == "scion.telemetry_decision_detail.v1"
    assert detail["mechanism_id"] == "activity_probe"
    assert detail["surface_field_id"] == "activity_counter"
    assert detail["runtime_role"] == "activity"
    assert detail["declaration_source_digest"] == "guard-digest-feedback"
    rendered = json.dumps(observation.structured_payload, sort_keys=True)
    assert "raw_metrics_ref" not in rendered
    assert "SECRET" not in rendered


def test_feedback_query_runtime_exposes_false_active_surface_failure(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    runtime_step = replace(
        context.step_history[0],
        hypothesis=_hyp("solver_algorithm"),
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(n_cases=4, wins=0, losses=4, ties=0, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("CANDIDATE_RUNTIME_FAILURE",),
            exposed_summary="candidate runtime failed",
            raw_metrics_ref="/SECRET/raw/runtime.json",
            candidate_surface_runtime_summary={
                "selected_surface": "solver_algorithm",
                "fields": {
                    "solver_algorithm_active": {
                        "present": 4,
                        "missing": 0,
                        "empty": 0,
                        "failed": 4,
                        "numeric_summary": {},
                        "values": [{"value": "false", "count": 4}],
                    }
                },
            },
        ),
    )
    context = replace(context, step_history=(runtime_step,))

    observation = registry.call(
        "feedback.query_runtime",
        {"surface": "solver_algorithm"},
        context,
    )

    assert observation.is_error is False
    attribution = observation.structured_payload["screening_runtime_attribution"][0]
    highlight = attribution["runtime_field_highlights"][0]
    assert highlight["field"] == "solver_algorithm_active"
    assert highlight["failed"] == 4
    rendered = json.dumps(observation.structured_payload, sort_keys=True)
    assert "raw_metrics_ref" not in rendered
    assert "SECRET" not in rendered


def test_experiment_history_marks_stable_objectives_and_no_effect_mechanisms(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    no_effect_step = replace(
        context.step_history[0],
        hypothesis=HypothesisProposal(
            hypothesis_text=(
                "Add merge cleanup as a new bounded mechanism after search."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_algorithm.py",
            target_objectives=("secondary_cost",),
            protected_objectives=("primary_quality",),
            mechanism_changes=(
                MechanismChange(id="merge_cleanup", change_type="add"),
            ),
        ),
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(
                n_cases=4,
                wins=0,
                losses=0,
                ties=4,
                win_rate=0.0,
                median_delta=0.0,
                total_pairs=4,
                attempted_pairs=4,
                valid_pairs=4,
            ),
            gate_outcome="fail",
            reason_codes=(
                "SCREENING_FAIL_WIN_RATE",
                "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
            ),
            exposed_summary="screening safe summary",
            raw_metrics_ref="/SECRET/raw/metrics.json",
            case_feedback=(
                CaseAggregateFeedback(
                    case_id="case-a",
                    n_pairs=2,
                    wins=0,
                    losses=0,
                    ties=2,
                    win_rate=0.0,
                    dominant_result="tie",
                    decisive_metric="tie",
                    median_deltas={
                        "primary_quality": 0.0,
                        "secondary_cost": 0.0,
                    },
                    seed_consistency=1.0,
                ),
                CaseAggregateFeedback(
                    case_id="case-b",
                    n_pairs=2,
                    wins=0,
                    losses=0,
                    ties=2,
                    win_rate=0.0,
                    dominant_result="tie",
                    decisive_metric="tie",
                    median_deltas={
                        "primary_quality": 0.0,
                        "secondary_cost": 0.0,
                    },
                    seed_consistency=1.0,
                ),
            ),
        ),
    )

    history = _build_experiment_history([no_effect_step], no_effect_step.branch_id)

    assert "Feedback Grounding Summary" in history
    assert "Active bottleneck" in history
    assert "SCREENING_FAIL_WIN_RATE" in history
    assert "decision_primary_reason: SCREENING_FAIL_WIN_RATE" in history
    assert "protocol_auxiliary_warnings" in history
    assert "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED" in history
    assert "stable/tie-dominated" in history
    assert "avoid unless new evidence" in history
    assert "merge_cleanup" in history
    assert "no observed objective effect" in history
    assert "SECRET" not in history
