from __future__ import annotations

from scion.core.models import MechanismChange
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
    assert "SECRET" not in rendered
    assert "raw_metrics_ref" not in rendered


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
