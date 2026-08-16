from __future__ import annotations

from dataclasses import replace

from scion.core.campaign_loop import CampaignRunResult
from scion.core.evidence_recording import EvidenceRecorder
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import StepRecord

from .evidence_recorder_test_support import _step


def _terminal_rejection() -> CampaignRunResult:
    base = CampaignRunResult.empty(2)
    counts = dict(base.execution_outcome_counts)
    counts[ExecutionOutcome.RESEARCH_REJECTED.value] = 1
    return replace(
        base,
        scheduled_calls=1,
        stop_reason="execution_research_rejected",
        execution_outcome_counts=counts,
        last_execution_outcome={
            "outcome": "research_rejected",
            "reason_code": "CANARY_FAILED",
            "stage": "canary",
        },
    )


def _state() -> dict[str, object]:
    return {
        "campaign_id": "camp-1",
        "proposal_runtime_mode": "direct_v3",
        "n_experiments": 0,
        "screened_experiments": 0,
        "n_steps": 1,
        "champion_version": 1,
        "branches": [],
    }


def test_status_and_summary_embed_the_same_explicit_run_projection(tmp_path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    projection = _terminal_rejection().to_projection()
    state = _state()

    status = recorder.write_status(state=state, run_result=projection)
    summary = recorder.write_campaign_summary(
        state=state,
        run_result=projection,
        step_history=[_step()],
    )

    assert status["run_result"] == projection
    assert summary["run_result"] == projection
    assert status["run_result"] == summary["run_result"]
    assert summary["steps"][0]["case_feedback_summary"] == [
        {
            "case_id": "case-1",
            "dominant_result": "win",
            "seed_pattern": "uniform",
            "decisive": "total_distance",
            "median_deltas": {"total_distance": 0.12},
        }
    ]
    for obsolete_alias in (
        "campaign_loop",
        "run_validity",
        "run_complete",
        "completed_requested_rounds",
        "last_stop_reason",
        "stopped_reason",
        "execution_outcome_counts",
        "proposal_accounting",
    ):
        assert obsolete_alias not in status
        assert obsolete_alias not in summary


def test_summary_does_not_reclassify_from_conflicting_step_rows(tmp_path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    projection = _terminal_rejection().to_projection()

    summary = recorder.write_campaign_summary(
        state=_state(),
        run_result=projection,
        step_history=[_step()],
    )

    assert summary["run_result"]["execution_outcome_counts"]["evaluated"] == 0
    assert summary["run_result"]["run_validity"] == {
        "status": "invalid",
        "reason": "invalid_no_evaluated_outcome",
        "valid": False,
    }


def test_recorder_owns_no_runtime_state_callbacks_or_loop_snapshot(tmp_path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)

    assert not hasattr(recorder, "state_provider")
    assert not hasattr(recorder, "campaign_loop_status")
    assert not hasattr(recorder, "last_status_result")
    assert not hasattr(recorder, "current_status_progress")
    assert not hasattr(recorder, "in_flight_protocol")


def test_protocol_progress_merge_is_pure_and_does_not_write_status(tmp_path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    original = {
        "stage": "screening",
        "case": "old-case",
        "completed_pairs": 2,
    }

    progress = recorder.record_protocol_progress(
        current_progress=original,
        stage="validation",
        case="new-case",
        completed_pairs=1,
    )

    assert original == {
        "stage": "screening",
        "case": "old-case",
        "completed_pairs": 2,
    }
    assert progress["stage"] == "validation"
    assert progress["case"] == "new-case"
    assert progress["completed_pairs"] == 1
    assert "last_case" not in progress
    assert "valid_pairs" not in progress
    assert "protocol_state" not in progress
    assert not (tmp_path / "status.json").exists()


def test_step_record_has_no_report_only_mirror_fields() -> None:
    fields = StepRecord.__dataclass_fields__

    assert "cache_stats" not in fields
    assert "verification_detail" not in fields
    assert "code_archive_ref" not in fields
