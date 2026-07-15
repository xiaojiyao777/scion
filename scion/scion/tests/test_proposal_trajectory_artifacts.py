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


def test_manifest_uses_direct_attempts_and_formal_candidates_only(
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
        "proposal_attempt_transition_count": 4,
        "proposal_attempt_invalid_row_count": 0,
        "formal_candidate_count": 1,
        "formal_candidate_replayable_count": 1,
        "formal_candidate_joined_attempt_count": 1,
        "zero_evaluated_attempt_count": 1,
    }
    assert manifest["call_kind_counts"] == {"code": 1, "hypothesis": 1}
    assert manifest["proposal_distributions"] == {
        "selected_surface": {"solver_design": 2},
        "action": {"modify": 2},
        "target_file": {"policies/baseline_modules/scheduler.py": 2},
        "mechanism_id": {},
    }
    assert manifest["coverage"]["missing_join_count"] == 1
    assert manifest["source_indexes"] == {
        "formal_candidate_index_ref": "artifacts/formal_candidates/index.jsonl",
        "formal_candidate_index_status": "available",
        "proposal_attempt_db_ref": "scion.db",
        "proposal_attempt_db_status": "available",
        "unsupported_historical": [],
    }
    code_attempt = manifest["attempts"][1]
    assert code_attempt["attempt_id"] == "attempt-code"
    assert code_attempt["proposal_fingerprint"]["formal_candidate_id"] == (
        "candidate-direct"
    )
    assert code_attempt["proposal_fingerprint"][
        "formal_candidate_join_basis"
    ] == "proposal_attempt_id"
    assert code_attempt["replayability"]["formal_candidate_joined"] is True
    assert contains_absolute_path(manifest["attempts"]) is False


def test_manifest_preserves_zero_attempt_safety_and_source_attribution(
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


def test_manifest_only_joins_replayable_formal_candidate_rows(
    tmp_path: Path,
) -> None:
    campaign_dir = _write_direct_campaign(
        tmp_path / "campaign",
        formal_overrides={
            "artifact_status": "skipped",
            "replay_identity_status": "missing",
            "missing_replay_identity_keys": ["base_workspace_ref"],
        },
    )

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-07-12T00:00:00+00:00",
    )

    assert manifest["counts"]["formal_candidate_count"] == 1
    assert manifest["counts"]["formal_candidate_replayable_count"] == 0
    assert manifest["counts"]["formal_candidate_joined_attempt_count"] == 0
    assert manifest["counts"]["zero_evaluated_attempt_count"] == 2
    assert manifest["coverage"]["missing_join_count"] == 2


def test_manifest_rejects_invalid_rows_and_does_not_leak_bodies(
    tmp_path: Path,
) -> None:
    campaign_dir = _write_direct_campaign(tmp_path / "campaign")
    malformed = _attempt_payload(
        attempt_id="attempt-malformed",
        phase="hypothesis",
        hypothesis_id="hypothesis-malformed",
    )
    malformed["prompt"] = "RAW PROMPT SHOULD NOT LEAK"
    with sqlite3.connect(campaign_dir / "scion.db") as conn:
        conn.execute(
            "INSERT INTO experiment_events VALUES "
            "(?, 'proposal_attempt_transition', ?)",
            ("event-malformed", json.dumps(malformed)),
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


def test_manifest_classifies_started_only_attempt_without_forging_terminal(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    rows = _attempt_pair(
        attempt_id="attempt-hard-stop",
        phase="hypothesis",
        hypothesis_id="hypothesis-never-generated",
    )
    _write_attempt_db(campaign_dir / "scion.db", rows[:1])

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-07-12T00:00:00+00:00",
    )

    assert manifest["proposal_attempt_inventory"][
        "unrecovered_in_flight_count"
    ] == 1
    attempt = manifest["attempts"][0]
    assert attempt["terminal_status"] == "started"
    assert attempt["postrun_classification"] == "unrecovered_in_flight"
    assert [phase["status"] for phase in attempt["phases"]] == ["started"]


def test_manifest_keeps_old_v1_attempts_without_fingerprint_compatible(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    legacy_rows = []
    for event_id, raw in _attempt_pair(
        attempt_id="legacy-attempt",
        phase="hypothesis",
        hypothesis_id="legacy-hypothesis",
    ):
        payload = json.loads(raw)
        payload.pop("proposal_fingerprint", None)
        legacy_rows.append((event_id, json.dumps(payload)))
    _write_attempt_db(campaign_dir / "scion.db", legacy_rows)

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-07-12T00:00:00+00:00",
    )

    assert manifest["counts"]["attempt_count"] == 1
    assert manifest["proposal_distributions"]["selected_surface"] == {
        "unknown": 1
    }


def test_manifest_reports_missing_create_target_as_unknown_not_string_none(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    rows = []
    for event_id, raw in _attempt_pair(
        attempt_id="create-attempt",
        phase="hypothesis",
        hypothesis_id="create-hypothesis",
    ):
        payload = json.loads(raw)
        if "proposal_fingerprint" in payload:
            payload["proposal_fingerprint"].update(
                action="create_new",
                target_file=None,
            )
        rows.append((event_id, json.dumps(payload)))
    _write_attempt_db(campaign_dir / "scion.db", rows)

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-07-12T00:00:00+00:00",
    )

    assert manifest["proposal_distributions"]["action"] == {"create_new": 1}
    assert manifest["proposal_distributions"]["target_file"] == {"unknown": 1}
    assert "None" not in json.dumps(manifest["proposal_distributions"])


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


def test_comparison_uses_direct_counts_and_matched_control_pair_key(
    tmp_path: Path,
) -> None:
    left = build_proposal_trajectory_manifest(
        _write_direct_campaign(tmp_path / "left"),
        observed_control_arm="on",
        control_pair_key="pair.v1:run-01",
        generated_at="2026-07-12T00:00:00+00:00",
    )
    right_dir = tmp_path / "right"
    right_dir.mkdir()
    _write_attempt_db(
        right_dir / "scion.db",
        _attempt_pair(
            attempt_id="attempt-hypothesis-right",
            phase="hypothesis",
            hypothesis_id="hypothesis-right",
        ),
    )
    right = build_proposal_trajectory_manifest(
        right_dir,
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
        "formal_candidate_count": 0,
    }
    assert comparison["summary"]["delta"]["attempt_count"] == -1


def test_attempt_groups_enforce_lifecycle_identity_and_parentage(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    rows = _attempt_pair(
        attempt_id="attempt-parent-hypothesis",
        phase="hypothesis",
        hypothesis_id="hypothesis-parent",
    )
    rows.extend(
        _attempt_pair(
            attempt_id="attempt-parent-code",
            phase="code",
            hypothesis_id="hypothesis-parent",
            continuation_of_attempt_id="attempt-parent-hypothesis",
            terminal_status="failed",
        )
    )
    rows.extend(
        _attempt_pair(
            attempt_id="attempt-continuation",
            phase="code",
            hypothesis_id="hypothesis-parent",
            continuation_of_attempt_id="attempt-parent-code",
        )
    )
    rows.extend(
        _attempt_pair(
            attempt_id="attempt-missing-parent",
            phase="code",
            hypothesis_id="hypothesis-orphan",
            continuation_of_attempt_id="attempt-does-not-exist",
        )
    )
    _write_attempt_db(campaign_dir / "scion.db", rows)

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-07-12T00:00:00+00:00",
    )

    assert [attempt["attempt_id"] for attempt in manifest["attempts"]] == [
        "attempt-parent-hypothesis",
        "attempt-parent-code",
        "attempt-continuation",
    ]
    assert manifest["proposal_attempt_inventory"]["invalid_by_reason"] == {
        "missing_parent": 1
    }


def test_cli_writes_direct_manifest_and_comparison(tmp_path: Path) -> None:
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
    assert left_summary["proposal_attempt_transition_count"] == 4

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
    formal_overrides: dict[str, object] | None = None,
) -> Path:
    campaign_dir.mkdir()
    rows = _attempt_pair(
        attempt_id="attempt-hypothesis",
        phase="hypothesis",
        hypothesis_id="hypothesis-direct",
    )
    rows.extend(
        _attempt_pair(
            attempt_id="attempt-code",
            phase="code",
            hypothesis_id="hypothesis-direct",
            continuation_of_attempt_id="attempt-hypothesis",
        )
    )
    _write_attempt_db(campaign_dir / "scion.db", rows)
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    row: dict[str, object] = {
        "schema": "scion.formal_candidate_patch_artifact.v1",
        "candidate_id": "candidate-direct",
        "proposal_attempt_id": "attempt-code",
        "proposal_attempt_event_id": "event-attempt-code-terminal",
        "branch_id": "branch-direct",
        "hypothesis_id": "hypothesis-direct",
        "stage": "screening",
        "patch_digest": "patch-digest-code",
        "artifact_ref": "artifacts/formal_candidates/direct/candidate.patch.json",
        "artifact_status": "recorded",
        "replay_identity_status": "complete",
        "missing_replay_identity_keys": [],
    }
    row.update(formal_overrides or {})
    formal_index.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return campaign_dir


def _attempt_payload(
    *,
    attempt_id: str,
    phase: str,
    hypothesis_id: str,
) -> dict[str, object]:
    prompt_ref = f"artifacts/llm_traces/{attempt_id}-{phase}.json"
    return {
        "schema_version": "proposal-attempt-transition.v1",
        "attempt_id": attempt_id,
        "campaign_id": "campaign-direct",
        "branch_id": "branch-direct",
        "runtime_mode": "direct_v3",
        "attempt_kind": "initial",
        "phase": phase,
        "status": "generated",
        "transition_reason": "generated",
        "failure_lane": None,
        "hypothesis_id": hypothesis_id,
        "hypothesis_digest": f"hypothesis-digest-{hypothesis_id}",
        "patch_digest": "patch-digest-code" if phase == "code" else None,
        "proposal_fingerprint": {
            "selected_surface": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/scheduler.py",
        },
        "prompt_call": {
            "request_kind": phase,
            "context_digest": f"context-digest-{attempt_id}-{phase}",
            "prompt_hash": f"prompt-hash-{attempt_id}-{phase}",
            "trace_ref": prompt_ref,
            "prompt_manifest_ref": f"{prompt_ref}#/prompt_manifest",
            "raw_response_ref": f"{prompt_ref}#/response",
            "provider_ok": True,
            "ok": True,
            "error_category": None,
            "error_type": None,
        },
        "anchors": {
            "problem_id": "cvrp",
            "problem_spec_hash": "problem-hash",
            "split_manifest_hash": "split-hash",
            "seed_ledger_hash": "seed-hash",
            "champion_version": 1,
            "champion_weight_revision": 0,
            "champion_code_snapshot_hash": "champion-code-hash",
            "branch_base_champion_id": 1,
            "branch_base_champion_hash": "branch-base-hash",
        },
        "tainted_artifact_refs": [prompt_ref],
    }


def _attempt_pair(
    *,
    attempt_id: str,
    phase: str,
    hypothesis_id: str,
    continuation_of_attempt_id: str | None = None,
    terminal_status: str = "generated",
) -> list[tuple[str, str]]:
    terminal = _attempt_payload(
        attempt_id=attempt_id,
        phase=phase,
        hypothesis_id=hypothesis_id,
    )
    if phase == "code":
        if not continuation_of_attempt_id:
            raise ValueError("code attempt fixture requires continuation parent")
        terminal["attempt_kind"] = "approved_code_continuation"
        terminal["continuation_of_attempt_id"] = continuation_of_attempt_id
    if terminal_status == "failed":
        terminal.update(
            status="failed",
            transition_reason="response_parse_failed",
            failure_lane="invalid_response",
            patch_digest=None,
        )
        terminal["prompt_call"]["ok"] = False  # type: ignore[index]
    started = json.loads(json.dumps(terminal))
    started.update(
        status="started",
        transition_reason="provider_call_started",
        failure_lane=None,
        patch_digest=None,
        tainted_artifact_refs=[],
    )
    if phase == "hypothesis":
        started["hypothesis_id"] = None
        started["hypothesis_digest"] = None
        started.pop("proposal_fingerprint", None)
    started["prompt_call"].update(
        trace_ref=None,
        prompt_manifest_ref=None,
        raw_response_ref=None,
        provider_ok=None,
        ok=None,
        error_category=None,
        error_type=None,
    )
    return [
        (f"event-{attempt_id}-started", json.dumps(started)),
        (f"event-{attempt_id}-terminal", json.dumps(terminal)),
    ]


def _write_attempt_db(path: Path, rows: list[tuple[str, str]]) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE experiment_events ("
            "event_id TEXT PRIMARY KEY, event_kind TEXT, audit_payload_json TEXT)"
        )
        conn.executemany(
            "INSERT INTO experiment_events VALUES "
            "(?, 'proposal_attempt_transition', ?)",
            rows,
        )
