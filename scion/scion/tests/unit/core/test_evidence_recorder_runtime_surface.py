"""Focused tests split from test_evidence_recorder.py."""

from .evidence_recorder_test_support import *  # noqa: F401,F403

def test_campaign_summary_distinguishes_pair_and_case_screening_rates(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = _step()
    pair_results = (
        ["win"] * 2
        + ["tie"] * 12
        + ["loss"] * 2
    )
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=-0.01,
            ci_high=0.01,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="case-level gate failed",
        raw_metrics_ref="/tmp/r2-like-screening.json",
        pair_feedback=tuple(
            PairwiseCaseFeedback(
                case_id=f"case-{idx // 4}",
                seed=idx,
                comparison=result,
                delta=1.0 if result == "win" else -1.0 if result == "loss" else 0.0,
            )
            for idx, result in enumerate(pair_results)
        ),
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    protocol = summary["steps"][0]["protocol_result"]
    assert protocol["screening_win_rate"] == 0.0
    assert protocol["screening_win_rate_scope"] == "case_level_gate"
    assert protocol["screening_case_win_rate"] == 0.0
    assert protocol["screening_gate_win_rate"] == 0.0
    assert protocol["screening_pair_wins"] == 2
    assert protocol["screening_pair_losses"] == 2
    assert protocol["screening_pair_ties"] == 12
    assert protocol["screening_pair_total"] == 16
    assert protocol["screening_pair_win_rate"] == 0.125


def test_campaign_summary_exposes_bounded_runtime_failure_summary(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = _step()
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=step.protocol_result.stats,
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/private-runtime.json",
        candidate_runtime_failure_categories={
            "operator_error": 2,
            "invalid_output": 1,
        },
        candidate_first_runtime_failure={
            "category": "operator_error",
            "code": "operator_errors",
            "surface": "local_search",
            "component": "operator",
            "detail_summary": "solver runtime reported operator_errors=2",
        },
        candidate_operator_attempts=8,
        candidate_operator_accepted=0,
        candidate_operator_errors=2,
        candidate_operator_invalid_outputs=1,
        candidate_policy_errors=3,
        candidate_construction_errors=4,
        candidate_portfolio_errors=5,
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    protocol = summary["steps"][0]["protocol_result"]
    assert protocol["candidate_runtime_failure_categories"] == {
        "operator_error": 2,
        "invalid_output": 1,
    }
    assert protocol["candidate_first_runtime_failure"]["category"] == "operator_error"
    assert protocol["candidate_operator_attempts"] == 8
    assert protocol["candidate_operator_accepted"] == 0
    assert protocol["candidate_operator_errors"] == 2
    assert protocol["candidate_operator_invalid_outputs"] == 1
    assert protocol["candidate_policy_errors"] == 3
    assert protocol["candidate_construction_errors"] == 4
    assert protocol["candidate_portfolio_errors"] == 5


def test_campaign_summary_exposes_selected_surface_runtime_summary(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = _step()
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=step.protocol_result.stats,
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/algorithm-blueprint-runtime.json",
        selected_surface="algorithm_blueprint",
        candidate_surface_runtime_summary={
            "selected_surface": "algorithm_blueprint",
            "required_runtime_fields": [
                "algorithm_blueprint_loaded",
                "algorithm_plan",
            ],
            "candidate_pairs": 4,
            "runtime_observed_pairs": 4,
            "runtime_missing_pairs": 0,
            "fields": {
                "algorithm_blueprint_loaded": {
                    "present": 4,
                    "missing": 0,
                    "empty": 0,
                    "failed": 0,
                    "values": [{"value": "true", "count": 4}],
                },
                "algorithm_plan": {
                    "present": 4,
                    "missing": 0,
                    "empty": 0,
                    "failed": 0,
                    "values": [
                        {
                            "value": "{\"baseline_time_fraction\":0.75,\"enabled\":true}",
                            "count": 4,
                        }
                    ],
                },
            },
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    protocol = summary["steps"][0]["protocol_result"]
    assert protocol["selected_surface"] == "algorithm_blueprint"
    surface_summary = protocol["candidate_surface_runtime_summary"]
    assert surface_summary["candidate_pairs"] == 4
    assert "algorithm_plan" in surface_summary["required_runtime_fields"]
    assert surface_summary["fields"]["algorithm_plan"]["present"] == 4


def test_campaign_summary_family_coverage_uses_step_locus_for_ambiguous_text(
    tmp_path: Path,
) -> None:
    taxonomy = FamilyTaxonomySpec(
        families=["alpha", "beta"],
        aliases={
            "alpha": ["alpha move", "previous alpha"],
            "beta": ["beta move", "cross move"],
        },
    )
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        family_taxonomy=taxonomy,
    )
    alpha = _step()
    alpha.hypothesis.hypothesis_text = "Implement alpha move."
    alpha.hypothesis.change_locus = "alpha"
    beta = _step()
    beta.hypothesis.hypothesis_text = (
        "Implement cross move. Unlike the previous alpha move, this changes "
        "the active mechanism."
    )
    beta.hypothesis.change_locus = "beta"

    summary = recorder.write_campaign_summary(
        step_history=[alpha, beta],
        round_num=2,
        champion=_champion(),
    )

    assert summary["family_coverage"] == {"alpha": 1, "beta": 1}


def test_protocol_progress_status_uses_public_raw_metrics_ref(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {"campaign_id": "camp-1", "round": 4},
    )

    progress = recorder.record_protocol_progress(
        branch_id="branch-1",
        stage="screening",
        raw_metrics_ref="/tmp/progress-metrics.json",
        completed_cases=2,
    )

    status = json.loads((tmp_path / "status.json").read_text())
    assert progress["raw_metrics_ref"] != "/tmp/progress-metrics.json"
    assert not progress["raw_metrics_ref"].startswith("/")
    assert "progress-metrics.json" in progress["raw_metrics_ref"]
    assert progress["raw_metrics_ref_scope"] == "public_artifact_ref"
    assert progress["raw_metrics_internal_only"] is True
    assert status["current_progress"]["raw_metrics_ref"] == progress["raw_metrics_ref"]
    assert not status["current_progress"]["raw_metrics_ref"].startswith("/")
    assert status["current_progress"]["completed_cases"] == 2
    assert "last_progress_at" in status["current_progress"]
