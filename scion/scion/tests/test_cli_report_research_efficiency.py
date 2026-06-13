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
        "protocol_metric_stage_counts": {
            "screening": 7,
            "validation": 1,
            "frozen": 0,
        },
        "steps": [
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
