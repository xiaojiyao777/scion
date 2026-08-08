from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scion.cli.main import app
from scion.core.proposal_trajectory_artifacts import (
    COMPARISON_SCHEMA_VERSION,
    SCHEMA_VERSION,
    build_proposal_trajectory_comparison,
    build_proposal_trajectory_manifest,
)
from scion.core.public_refs import contains_absolute_path


runner = CliRunner()


def test_manifest_uses_direct_proposal_calls_and_formal_candidates(
    tmp_path: Path,
) -> None:
    campaign_dir = _write_direct_campaign(tmp_path / "campaign")

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-07-12T00:00:00+00:00",
    )

    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["report_only"] is True
    assert manifest["decision_features_excluded"] is True
    assert manifest["raw_prompt_excluded"] is True
    assert manifest["raw_response_excluded"] is True
    assert manifest["patch_body_excluded"] is True
    assert manifest["counts"] == {
        "attempt_count": 2,
        "proposal_trajectory_count": 2,
        "proposal_attempt_transition_count": 2,
        "proposal_attempt_invalid_row_count": 0,
        "formal_candidate_count": 1,
        "formal_candidate_replayable_count": 1,
        "formal_candidate_joined_attempt_count": 0,
        "zero_evaluated_attempt_count": 2,
    }
    assert manifest["call_kind_counts"] == {"code": 1, "hypothesis": 1}
    assert manifest["proposal_distributions"] == {
        "selected_surface": {"unknown": 2},
        "action": {"unknown": 2},
        "target_file": {"unknown": 2},
        "mechanism_id": {},
    }
    assert manifest["coverage"]["missing_join_count"] == 2
    assert manifest["source_indexes"] == {
        "formal_candidate_index_ref": "artifacts/formal_candidates/index.jsonl",
        "formal_candidate_index_status": "available",
        "proposal_attempt_db_ref": "scion.db",
        "proposal_attempt_db_status": "available",
        "unsupported_historical": [],
    }
    assert manifest["attempts"][1]["call_event_id"] == "event-call-code"
    assert manifest["attempts"][1]["terminal_phase"] == "code"
    assert manifest["attempts"][1]["replayability"]["formal_candidate_joined"] is False
    assert contains_absolute_path(manifest["attempts"]) is False


def test_manifest_preserves_zero_call_safety_and_source_attribution(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-07-12T00:00:00+00:00",
    )

    assert manifest["counts"]["attempt_count"] == 0
    assert manifest["counts"]["zero_evaluated_attempt_count"] == 0
    assert manifest["coverage"]["missing_join_count"] == 0
    assert manifest["source_indexes"]["proposal_attempt_db_status"] == "missing"
    assert manifest["source_indexes"]["proposal_attempt_db_ref"] == ""


def test_manifest_rejects_invalid_proposal_calls_without_leaking_bodies(
    tmp_path: Path,
) -> None:
    campaign_dir = _write_direct_campaign(tmp_path / "campaign")
    malformed = {
        "schema_version": "proposal-call.v0",
        "prompt": "RAW PROMPT SHOULD NOT LEAK",
    }
    _append_call(
        campaign_dir / "scion.db",
        event_id="event-malformed",
        payload=malformed,
    )

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-07-12T00:00:00+00:00",
    )

    assert manifest["counts"]["attempt_count"] == 2
    assert manifest["counts"]["proposal_attempt_invalid_row_count"] == 1
    rendered = json.dumps(manifest, sort_keys=True)
    assert "RAW PROMPT SHOULD NOT LEAK" not in rendered
    assert "prompt body" not in rendered
    assert "response body" not in rendered
    assert "patch body" not in rendered


@pytest.mark.parametrize(
    "control_pair_key",
    ["", "   ", "pair with space", "pair\nwith-newline", "pair/with/slash", "x" * 129],
)
def test_manifest_rejects_invalid_control_pair_keys(
    tmp_path: Path,
    control_pair_key: str,
) -> None:
    campaign_dir = _write_direct_campaign(tmp_path / "campaign")

    with pytest.raises(ValueError, match="control_pair_key"):
        build_proposal_trajectory_manifest(
            campaign_dir,
            observed_control_arm="on",
            control_pair_key=control_pair_key,
        )


def test_comparison_uses_direct_call_counts_and_matched_control_pair_key(
    tmp_path: Path,
) -> None:
    left = build_proposal_trajectory_manifest(
        _write_direct_campaign(tmp_path / "left"),
        observed_control_arm="on",
        control_pair_key="pair.v1:run-01",
        generated_at="2026-07-12T00:00:00+00:00",
    )
    right = build_proposal_trajectory_manifest(
        _write_direct_campaign(tmp_path / "right", phases=("hypothesis",)),
        observed_control_arm="record_only",
        control_pair_key="pair.v1:run-01",
        generated_at="2026-07-12T00:00:00+00:00",
    )

    comparison = build_proposal_trajectory_comparison(
        left,
        right,
        generated_at="2026-07-12T00:00:00+00:00",
    )

    assert comparison["schema_version"] == COMPARISON_SCHEMA_VERSION
    assert comparison["observational_only"] is False
    assert comparison["llm_deterministic_replay"] is False
    assert comparison["control_pair_key"] == "pair.v1:run-01"
    assert comparison["summary"]["left"] == {
        "attempt_count": 2,
        "proposal_trajectory_count": 2,
        "formal_candidate_count": 1,
    }
    assert comparison["summary"]["right"] == {
        "attempt_count": 1,
        "proposal_trajectory_count": 1,
        "formal_candidate_count": 1,
    }
    assert comparison["summary"]["delta"]["attempt_count"] == -1


def test_cli_writes_proposal_call_manifest_and_comparison(tmp_path: Path) -> None:
    left_campaign = _write_direct_campaign(tmp_path / "left")
    right_campaign = _write_direct_campaign(tmp_path / "right")
    left_manifest = tmp_path / "left-manifest.json"
    right_manifest = tmp_path / "right-manifest.json"
    comparison_path = tmp_path / "comparison.json"

    left_result = runner.invoke(
        app,
        [
            "report",
            "proposal-trajectory-manifest",
            "--campaign-dir",
            str(left_campaign),
            "--observed-control-arm",
            "on",
            "--output",
            str(left_manifest),
        ],
    )
    assert left_result.exit_code == 0, left_result.output
    left_summary = json.loads(left_result.output)
    assert left_summary["attempt_count"] == 2
    assert left_summary["proposal_attempt_transition_count"] == 2

    right_result = runner.invoke(
        app,
        [
            "report",
            "proposal-trajectory-manifest",
            "--campaign-dir",
            str(right_campaign),
            "--observed-control-arm",
            "record_only",
            "--output",
            str(right_manifest),
        ],
    )
    assert right_result.exit_code == 0, right_result.output

    compare_result = runner.invoke(
        app,
        [
            "report",
            "proposal-trajectory-compare",
            "--left",
            str(left_manifest),
            "--right",
            str(right_manifest),
            "--output",
            str(comparison_path),
        ],
    )
    assert compare_result.exit_code == 0, compare_result.output
    summary = json.loads(compare_result.output)
    assert summary["left_attempt_count"] == 2
    assert summary["right_attempt_count"] == 2


def test_cli_rejects_invalid_control_pair_key(tmp_path: Path) -> None:
    campaign_dir = _write_direct_campaign(tmp_path / "campaign")
    manifest_path = tmp_path / "manifest.json"

    result = runner.invoke(
        app,
        [
            "report",
            "proposal-trajectory-manifest",
            "--campaign-dir",
            str(campaign_dir),
            "--observed-control-arm",
            "on",
            "--control-pair-key",
            "not path safe",
            "--output",
            str(manifest_path),
        ],
    )

    assert result.exit_code == 1
    assert "control_pair_key" in result.output
    assert not manifest_path.exists()


def _write_direct_campaign(
    campaign_dir: Path,
    *,
    phases: tuple[str, ...] = ("hypothesis", "code"),
) -> Path:
    campaign_dir.mkdir()
    _write_call_db(campaign_dir / "scion.db", phases=phases)
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    formal_index.write_text(
        json.dumps(
            {
                "schema": "scion.formal_candidate_patch_artifact.v1",
                "candidate_id": "candidate-direct",
                "branch_id": "branch-direct",
                "hypothesis_id": "hypothesis-direct",
                "stage": "screening",
                "patch_digest": "patch-digest-code",
                "artifact_ref": "artifacts/formal_candidates/direct/candidate.patch.json",
                "artifact_status": "recorded",
                "replay_identity_status": "complete",
                "missing_replay_identity_keys": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return campaign_dir


def _write_call_db(path: Path, *, phases: tuple[str, ...]) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE experiment_events ("
            "event_id TEXT PRIMARY KEY, campaign_id TEXT, branch_id TEXT, "
            "hypothesis_id TEXT, event_kind TEXT, audit_payload_json TEXT)"
        )
        for phase in phases:
            _append_call(
                path,
                event_id=f"event-call-{phase}",
                phase=phase,
                conn=conn,
            )


def _append_call(
    path: Path,
    *,
    event_id: str,
    phase: str | None = None,
    payload: dict[str, object] | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    call_payload = payload or _proposal_call_payload(phase or "hypothesis")
    if conn is None:
        with sqlite3.connect(path) as writable_conn:
            _append_call(
                path,
                event_id=event_id,
                payload=call_payload,
                conn=writable_conn,
            )
        return
    conn.execute(
        "INSERT INTO experiment_events VALUES (?, ?, ?, ?, 'proposal_call', ?)",
        (
            event_id,
            "campaign-direct",
            "branch-direct",
            "hypothesis-direct",
            json.dumps(call_payload),
        ),
    )


def _proposal_call_payload(phase: str) -> dict[str, object]:
    trace_ref = f"artifacts/llm_traces/{phase}.json"
    return {
        "schema_version": "proposal-call.v1",
        "phase": phase,
        "status": "generated",
        "hypothesis_id": "hypothesis-direct",
        "receipt": {
            "request_kind": phase,
            "context_digest": f"context-{phase}",
            "prompt_hash": f"prompt-{phase}",
            "trace_ref": trace_ref,
            "prompt_manifest_ref": f"{trace_ref}#/prompt_manifest",
            "raw_response_ref": f"{trace_ref}#/response",
            "provider_ok": True,
            "ok": True,
            "error_category": None,
            "error_type": None,
            "trace_persistence_error": None,
        },
        "execution_outcome": None,
    }
