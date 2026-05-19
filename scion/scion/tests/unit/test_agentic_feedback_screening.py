from __future__ import annotations

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
