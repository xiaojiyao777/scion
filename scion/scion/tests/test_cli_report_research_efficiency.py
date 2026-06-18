from __future__ import annotations

import json
from pathlib import Path

from .cli_test_support import _make_campaign, app, runner


def test_research_efficiency_report_separates_accounting_and_taxonomy(tmp_path):
    cell_dir, _ = _make_research_efficiency_fixture(tmp_path)

    result = runner.invoke(
        app,
        ["report", "research-efficiency", "--campaign-dir", str(cell_dir)],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["schema_version"] == "scion.research_efficiency_report.v1"
    assert data["report_only"] is True
    assert data["decision_features_excluded"] is True
    assert data["campaign_state_mutated"] is False
    assert data["scheduler_state_mutated"] is False
    assert data["promotion_state_mutated"] is False

    assert data["effective_budget"]["counter"] == "effective_rounds_completed"
    assert data["effective_budget"]["effective_rounds_completed"] == 8
    assert data["attempts"]["proposal_attempts_total"] == 10
    assert data["protocol_rows"]["protocol_metric_results"] == 7
    assert data["formal_candidates"]["formal_screened_candidates"] == 6
    assert data["formal_candidate_artifacts"]["row_count"] == 2
    assert data["stage_rows"] == {
        "screening": 7,
        "validation": 1,
        "frozen": 0,
        "fresh_runtime_replay": 1,
    }
    assert data["measurement_readiness"]["status"] == "ready"
    assert data["measurement_readiness_source"] == "summary_status"
    assert data["measurement_readiness"]["mde_at_power_80"] == 9.9
    assert "calibration_ref" not in data["measurement_readiness"]
    power = data["protocol_effects_vs_mde"]
    assert power["decision_features_excluded"] is True
    assert power["mde_at_power_80"] == 9.9
    assert power["interpretation"] == "has_positive_protocol_effect_at_or_above_mde"
    assert power["protocol_row_count"] == 3
    assert power["rows_at_or_above_mde"] == 1
    assert power["rows_with_ci_high_below_mde"] == 2
    assert power["max_effect_to_mde_ratio"] == 1.212121
    assert power["by_stage"]["screening"]["rows_at_or_above_mde"] == 1
    assert power["by_stage"]["validation"]["nonpositive_rows"] == 1
    assert power["top_rows_by_effect_to_mde"][0]["branch_id"] == "branch-a"
    assert "raw_metrics_ref" not in power["top_rows_by_effect_to_mde"][0]
    assert data["research_shape"]["decision_features_excluded"] is True
    assert data["research_shape"]["max_branch_depth"] == 3
    assert data["research_shape"]["branch_depth_distribution"] == {"1": 1, "3": 1}
    assert data["cross_branch_observability"]["observable_step_count"] == 5
    assert data["cross_branch_observability"][
        "preserved_same_branch_lesson_count"
    ] == 2
    assert data["cross_branch_observability"][
        "same_branch_refinement_allowance_count"
    ] == 1
    continuity = data["research_continuity"]
    assert continuity["decision_features_excluded"] is True
    assert continuity["same_mechanism_followup"] == {
        "selected_same_branch_refinement_count": 1,
        "not_selected_same_branch_refinement_count": 0,
        "observed_opportunity_count": 1,
        "selection_rate": 1.0,
        "interpretation": "all_observed_same_mechanism_followups_selected",
    }
    assert continuity["branch_lesson_usage"]["requirement_count"] == 2
    assert continuity["branch_lesson_usage"]["satisfied_count"] == 2
    assert continuity["branch_lesson_usage"]["satisfaction_rate"] == 1.0
    assert continuity["branch_lesson_usage"]["semantic_gap_count"] == 0
    assert continuity["weak_positive_transfer"]["acceptance_rate"] == 1.0
    assert continuity["lesson_action_counts"]["preserved_same_branch"] == 2
    assert continuity["research_shape_summary"]["max_branch_depth"] == 3
    assert continuity["research_shape_summary"]["mechanism_family_count"] == 2
    assert data["fresh_runtime_replay_drain"]["executed"] == 1
    assert data["fresh_runtime_replay_drain"]["skipped"] == 1
    assert data["proposal_quality"]["proposal_quality_blocks"] == 1

    taxonomy = data["failure_taxonomy"]
    assert taxonomy["verification_heavy"]["count"] == 1
    assert taxonomy["code_generation"]["count"] == 2
    assert taxonomy["agentic_proposal:code_generation_failed"]["count"] == 2
    assert taxonomy["old_string_not_found"]["count"] == 1
    assert taxonomy["stale_source"]["count"] == 1
    assert taxonomy["tool_timeout"]["count"] == 1
    assert taxonomy["abandon_fast_verification_heavy"]["count"] == 1
    assert data["failures"]["tool_timeout"]["count"] == 1
    assert data["run_status"]["run_validity"]["reason"] == "valid"
    assert data["run_status"]["stopped_reason"] == "max_rounds_exhausted"


def test_research_efficiency_report_write_to_file_from_campaign_dir(tmp_path):
    _, campaign_dir = _make_research_efficiency_fixture(tmp_path)
    output = tmp_path / "research-efficiency.json"

    result = runner.invoke(
        app,
        [
            "report",
            "research-efficiency",
            "--campaign-dir",
            str(campaign_dir),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Research-efficiency report written" in result.output
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["formal_candidate_artifacts"]["index_ref"] == (
        "artifacts/formal_candidates/index.jsonl"
    )
    assert data["source_files"]["run_log"].endswith("run.log")
    assert data["run_status"]["wrapper_exit_status"] == 0


def test_research_efficiency_report_falls_back_to_copied_calibration(tmp_path):
    campaign_dir = tmp_path / "campaign"
    calibration_dir = campaign_dir / "champions" / "champion_v1" / "formal" / "calibration"
    calibration_dir.mkdir(parents=True)
    (campaign_dir / "campaign_summary.json").write_text(
        json.dumps(
            {
                "campaign_id": "fallback-campaign",
                "steps": [
                    {
                        "round": 1,
                        "branch_id": "branch-cvrp",
                        "decision": "abandon",
                        "protocol_result": {
                            "stage": "screening",
                            "median_delta": 12.0,
                            "ci_high": 15.0,
                            "gate_outcome": "fail",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (campaign_dir / "champions" / "champion_v1" / "problem-v1.yaml").write_text(
        "\n".join(
            [
                'spec_version: "problem-v1"',
                "id: cvrp",
                "measurement:",
                "  runtime_model: budget_exhausting",
                "  pairing_validity: trajectory_divergent",
                "  effect_scale:",
                "    metric: total_distance",
                "    unit: raw_delta",
                "    practical_delta_screen: 2.0",
                "    practical_delta_validate: 1.0",
                "  calibration_ref: formal/calibration/aa_noise_floor.json",
                "  calibration_max_age_days: 9999",
            ]
        ),
        encoding="utf-8",
    )
    (calibration_dir / "aa_noise_floor.json").write_text(
        json.dumps(
            {
                "schema": "scion.aa_noise_floor.v1",
                "problem_id": "cvrp",
                "measurement_metric": "total_distance",
                "measurement_unit": "raw_delta",
                "calibrated_at": "2026-06-11T22:03:16+00:00",
                "n_pairs": 96,
                "decision_features_excluded": True,
                "protocol_power": {"mde_at_power_80": 9.9},
                "per_case": [{"delta_p90_abs": 14.0}],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["report", "research-efficiency", "--campaign-dir", str(campaign_dir)],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["measurement_readiness_source"] == "artifact_fallback"
    assert data["measurement_readiness"]["status"] == "ready"
    assert data["measurement_readiness"]["mde_at_power_80"] == 9.9
    assert data["measurement_readiness"]["signal_to_noise_tier"] == "low_power"
    assert "calibration_ref" not in data["measurement_readiness"]
    power = data["protocol_effects_vs_mde"]
    assert power["mde_source"] == "measurement_readiness.mde_at_power_80"
    assert power["rows_at_or_above_mde"] == 1
    assert power["max_effect_to_mde_ratio"] == 1.212121


def test_existing_failures_report_still_works(tmp_path):
    campaign_dir, _, _ = _make_campaign(tmp_path)

    result = runner.invoke(
        app,
        ["report", "failures", "--campaign-dir", str(campaign_dir)],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "total_failures" in data
    assert "by_type" in data


def _make_research_efficiency_fixture(tmp_path: Path) -> tuple[Path, Path]:
    cell_dir = tmp_path / "rep01" / "on_compact"
    campaign_dir = cell_dir / "campaign"
    formal_dir = campaign_dir / "artifacts" / "formal_candidates"
    formal_dir.mkdir(parents=True)

    summary = {
        "campaign_id": "fixture-campaign",
        "requested_rounds": 8,
        "max_rounds_budget_counter": "effective_rounds_completed",
        "effective_rounds_completed": 8,
        "completed_requested_rounds": True,
        "effective_protocol_rounds": 6,
        "protocol_metric_results": 7,
        "protocol_evaluated_candidates": 6,
        "formal_screened_candidates": 6,
        "screening_protocol_results": 7,
        "validation_protocol_results": 1,
        "frozen_protocol_results": 0,
        "fresh_runtime_replay_protocol_results": 1,
        "fresh_runtime_replay_drain_attempts": 2,
        "fresh_runtime_replay_drain_executed": 1,
        "fresh_runtime_replay_drain_skipped": 1,
        "fresh_runtime_replay_drain_blocked_count": 0,
        "fresh_runtime_replay_drain_stopped_reason": "no_pending_replay",
        "proposal_attempts_total": 10,
        "proposal_attempts_consumed": 10,
        "verification_consumed_candidates": 8,
        "verification_failure_consumed_candidates": 1,
        "proposal_quality_blocks": 1,
        "quality_blocks": 1,
        "quality_block_ledger_count": 1,
        "quality_block_ledger": [
            {
                "failure_reason": (
                    "agentic_proposal:code_generation_failed: /: "
                    "old_string_not_found in operators/merge_vehicles.py"
                )
            }
        ],
        "run_validity": {
            "status": "valid",
            "reason": "valid",
            "effective_rounds_completed": 8,
            "stopped_reason": "max_rounds_exhausted",
        },
        "run_validity_status": "valid",
        "stopped_reason": "max_rounds_exhausted",
        "run_complete": True,
        "run_completeness_status": "complete",
        "measurement_readiness": {
            "status": "ready",
            "reason_code": "ok",
            "calibration_age_days": 3,
            "calibration_max_age_days": 90,
            "n_pairs": 96,
            "mde_at_power_80": 9.9,
            "noise_band_p90_abs": 14.0,
            "effect_to_mde_ratio": 0.202,
            "signal_to_noise_tier": "low_power",
            "decision_features_excluded": True,
            "calibration_ref": "formal/calibration/aa_noise_floor.json",
        },
        "cross_branch_research_observability": {
            "schema_version": "cross_branch_research_observability.v1",
            "policy": "proposal_observability_only",
            "decision_input_policy": "excluded_from_decision_features",
            "source_counts": {
                "observable_step_count": 5,
                "branch_row_count": 2,
            },
            "observable_step_count": 5,
            "near_duplicate_count": 1,
            "saturated_signature_count": 0,
            "material_difference_requirement_count": 1,
            "branch_lesson_record_count": 3,
            "branch_lesson_usage_requirement_count": 2,
            "branch_lesson_usage_present_count": 2,
            "branch_lesson_usage_satisfied_count": 2,
            "branch_lesson_usage_missing_block_count": 0,
            "borrowed_lesson_count": 1,
            "avoided_lesson_count": 1,
            "contrasted_lesson_count": 1,
            "preserved_same_branch_lesson_count": 2,
            "clean_fork_contrast_satisfied_count": 1,
            "weak_positive_transfer_count": 1,
            "weak_positive_transfer_reject_count": 0,
            "same_branch_refinement_allowance_count": 1,
            "same_branch_refinement_not_selected_count": 0,
            "reason_code_counts": {"SCREENING_WEAK_SIGNAL_CONTINUE": 2},
            "research_shape_diagnostics": {
                "schema_version": "campaign_research_shape_diagnostics.v1",
                "policy": "summary_status_observability_only",
                "decision_features_excluded": True,
                "decision_input_policy": "excluded_from_decision_features",
                "source": {
                    "step_history": "campaign_summary_step_history",
                    "branch_depth_source": "step_history_branch_counts",
                },
                "branch_depth_distribution": {"1": 1, "3": 1},
                "branch_depth_by_branch": {"branch-a": 3, "branch-b": 1},
                "max_branch_depth": 3,
                "mean_branch_depth": 2.0,
                "active_research_shape_signal": {
                    "active_branch_count": 1,
                    "active_branch_ids": ["branch-a"],
                    "active_mechanism_family_count": 1,
                    "active_mechanism_families": ["regret_insertion"],
                    "shape": "deep_focused",
                },
                "mechanism_family_breadth": {
                    "family_count": 2,
                    "families": {
                        "regret_insertion": 3,
                        "route_merge": 1,
                    },
                },
            },
        },
        "protocol_metric_stage_counts": {
            "screening": 7,
            "validation": 1,
            "frozen": 0,
        },
        "steps": [
            {
                "round": 1,
                "branch_id": "branch-a",
                "decision": "queue_validate",
                "protocol_result": {
                    "stage": "screening",
                    "win_rate": 0.75,
                    "median_delta": 12.0,
                    "ci_low": 1.0,
                    "ci_high": 15.0,
                    "gate_outcome": "pass",
                    "effective_reason_codes": ["SCREENING_PASS"],
                    "raw_metrics_ref": "/tmp/internal-screening-a.json",
                },
            },
            {
                "round": 2,
                "branch_id": "branch-b",
                "decision": "abandon",
                "protocol_result": {
                    "stage": "screening",
                    "win_rate": 0.5,
                    "median_delta": 2.5,
                    "ci_low": -1.0,
                    "ci_high": 7.0,
                    "gate_outcome": "fail",
                    "reason_codes": ["SCREENING_WEAK_SIGNAL_CONTINUE"],
                },
            },
            {
                "round": 3,
                "branch_id": "branch-a",
                "decision": "abandon",
                "protocol_result": {
                    "stage": "validation",
                    "win_rate": 0.25,
                    "median_delta": -1.0,
                    "ci_low": -4.0,
                    "ci_high": 3.0,
                    "gate_outcome": "fail",
                    "reason_codes": ["VALIDATION_FAIL"],
                },
            },
            {
                "failure_stage": "verification",
                "failure_detail": "V9_perf_guard",
                "verification_detail": (
                    "severity=heavy  first_failure=V9_perf_guard\n"
                    "  [V9_perf_guard] (heavy) too slow"
                ),
            },
            {
                "failure_stage": "code_generation",
                "failure_detail": (
                    "agentic_proposal:code_generation_failed: /: "
                    "old_string_not_found in operators/merge_vehicles.py"
                ),
            },
            {
                "failure_stage": "code_generation",
                "failure_detail": (
                    "agentic_proposal:code_generation_failed: /: "
                    "stale_source for operators/merge_vehicles.py"
                ),
            },
        ],
    }
    (campaign_dir / "campaign_summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    (campaign_dir / "status.json").write_text(
        json.dumps({"run_validity": summary["run_validity"]}),
        encoding="utf-8",
    )
    (campaign_dir / "run_status.json").write_text(
        json.dumps(
            {
                "wrapper_exit_status": 0,
                "campaign_exit_status": "complete",
                "last_stop_reason": "max_rounds_exhausted",
            }
        ),
        encoding="utf-8",
    )
    (formal_dir / "index.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"candidate_id": "c1"}),
                json.dumps({"candidate_id": "c2"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (cell_dir / "run.log").write_text(
        "\n".join(
            [
                (
                    "Branch b1: agentic proposal session ended without patch: "
                    "agentic_proposal:code_generation_failed: /: "
                    "old_string_not_found in operators/merge_vehicles.py"
                ),
                (
                    "Branch b1: agentic proposal session ended without patch: "
                    "agentic_proposal:code_generation_failed: /: "
                    "stale_source for operators/merge_vehicles.py"
                ),
                "Tool call timeout (attempt 1/2)",
                "abandon_fast after 2 consecutive 'verification_heavy' failures",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return cell_dir, campaign_dir
