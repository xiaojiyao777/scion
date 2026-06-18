from __future__ import annotations

import json
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


runner = CliRunner()


def test_builds_manifest_with_trace_prompt_and_formal_candidate_joins(
    tmp_path: Path,
) -> None:
    campaign_dir = _write_campaign(tmp_path / "campaign", session_id="session-a")

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["report_only"] is True
    assert manifest["control_pair_key"] == ""
    assert manifest["decision_features_excluded"] is True
    assert manifest["comparison_is_decision_input"] is False
    assert manifest["campaign_state_mutated"] is False
    assert manifest["scheduler_state_mutated"] is False
    assert manifest["promotion_state_mutated"] is False
    assert manifest["raw_prompt_excluded"] is True
    assert manifest["raw_response_excluded"] is True
    assert manifest["patch_body_excluded"] is True
    assert manifest["counts"] == {
        "session_count": 1,
        "trace_count": 2,
        "formal_candidate_count": 1,
        "formal_candidate_replayable_count": 1,
        "formal_candidate_joined_session_count": 1,
        "prompt_manifest_ref_count": 2,
        "prompt_manifest_loaded_count": 2,
    }
    assert manifest["coverage"]["missing_join_count"] == 0
    assert manifest["context_arm_fingerprint"] == {
        "known_trace_count": 2,
        "mixed": False,
        "proposal_context_ablation": "full",
        "proposal_context_ablation_counts": {"full": 2},
        "source": "prompt_manifest.context_profile_metadata.proposal_context_ablation",
        "unknown_trace_count": 0,
    }
    assert manifest["call_kind_counts"] == {"code": 1, "hypothesis": 1}
    assert manifest["proposal_distributions"]["selected_surface"] == {"repair": 1}
    branch_usage_accounting = manifest["branch_lesson_usage_accounting"]
    assert branch_usage_accounting["report_only"] is True
    assert branch_usage_accounting["decision_features_excluded"] is True
    assert branch_usage_accounting["session_count"] == 1
    assert branch_usage_accounting["usage_present_count"] == 1
    assert branch_usage_accounting["usage_missing_count"] == 0
    assert branch_usage_accounting["semantic_projection_present_count"] == 1
    assert branch_usage_accounting["field_counts"] == {"avoided_lessons": 1}
    assert branch_usage_accounting["prompt_visibility_counts"] == {
        "branch_lesson_context_omitted_section_count": 2,
        "branch_lesson_context_omitted_trace_count": 2,
        "branch_lesson_context_truncated_section_count": 2,
        "branch_lesson_context_truncated_trace_count": 2,
    }

    session = manifest["sessions"][0]
    assert session["session_id"] == "session-a"
    assert session["problem_fingerprint"] == {
        "problem_id": "cvrp",
        "problem_spec_hash": "problem-hash-a",
        "seed_ledger_hash": "seed-hash-a",
        "split_manifest_hash": "split-hash-a",
    }
    proposal = session["proposal_fingerprint"]
    assert proposal["selected_surface"] == "repair"
    assert proposal["action"] == "modify"
    assert proposal["target_file"] == "solver.py"
    assert proposal["mechanism_ids"] == ["mechanism-a"]
    assert proposal["hypothesis_digest"]
    assert proposal["patch_digest"] == "patch-digest-a"
    assert proposal["formal_candidate_ref"].endswith("candidate.patch.json")
    assert proposal["formal_candidate_join_basis"] == "session_id"
    branch_usage = session["branch_lesson_usage_fingerprint"]
    assert branch_usage["present"] is True
    assert branch_usage["semantic_projection_present"] is True
    assert branch_usage["field_counts"] == {"avoided_lessons": 1}
    assert branch_usage["item_count"] == 1
    assert branch_usage["report_only"] is True
    assert branch_usage["decision_features_excluded"] is True
    assert session["trace_fingerprints"][0]["proposal_context_ablation"] == "full"
    assert session["replayability"]["summary"] == (
        "posthoc_audit_fingerprints_only_no_llm_replay"
    )

    trace = session["trace_fingerprints"][0]
    assert trace["prompt_hash"] == "prompt-hash-hypothesis"
    assert trace["visibility_ledger_digest"] == "ledger-hypothesis"
    hypothesis_source_visibility = trace["source_visibility_summary"][
        "hypothesis_target_source_visibility"
    ]
    assert hypothesis_source_visibility == {
        "schema_version": "hypothesis-target-source-visibility-ledger.v1",
        "target_source_required": True,
        "visibility_status": "full_dedicated_source_visible",
        "preflight_section_status": "included",
        "owner_source_visible": True,
    }
    assert trace["block_family_summary"]["families"]["research_signal"] == {
        "char_count": 40,
        "token_estimate": 10,
        "token_share": 0.5,
    }
    assert trace["omitted_sections"] == [
        "hidden_validation",
        "branch_lesson_usage_hidden_context",
    ]
    assert trace["truncated_sections"] == [
        "long_feedback",
        "branch_lesson_usage_context",
    ]
    code_trace = session["trace_fingerprints"][1]
    code_source_visibility = code_trace["source_visibility_summary"]
    assert code_source_visibility["code_phase_guarantees"] == {
        "schema_version": "code-phase-source-visibility-guarantees.v1",
        "target_source_visible": True,
        "required_integration_source_visible": True,
        "algorithm_file_read_source_visible": True,
        "protected_source_visible": True,
        "target_file_create_mode": False,
        "required_integration_source_count": 1,
        "algorithm_file_read_source_count": 1,
    }
    assert code_source_visibility["code_file_visibility"] == {
        "schema_version": "code-file-visibility-ledger.v1",
        "target_prompt_visibility_status": "full_current_source_visible",
        "target_source_status": "current_branch_source",
        "target_source_provenance": "branch_workspace",
        "target_full_content_visible": True,
        "integration_file_count": 1,
        "integration_files_full_content_visible_count": 1,
        "algorithm_file_read_count": 1,
        "algorithm_file_reads_full_content_visible_count": 1,
    }


def test_manifest_stores_sanitized_control_pair_key_only_at_top_level(
    tmp_path: Path,
) -> None:
    campaign_dir = _write_campaign(tmp_path / "campaign", session_id="session-a")

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        control_pair_key="  pair.v1:run-01  ",
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert manifest["control_pair_key"] == "pair.v1:run-01"
    assert manifest["report_only"] is True
    assert manifest["decision_features_excluded"] is True
    assert manifest["comparison_is_decision_input"] is False
    assert manifest["campaign_state_mutated"] is False
    assert manifest["scheduler_state_mutated"] is False
    assert manifest["promotion_state_mutated"] is False
    assert manifest["raw_prompt_excluded"] is True
    assert manifest["raw_response_excluded"] is True
    assert manifest["patch_body_excluded"] is True
    assert "control_pair_key" not in json.dumps(manifest["sessions"], sort_keys=True)
    assert "pair.v1:run-01" not in json.dumps(manifest["sessions"], sort_keys=True)


@pytest.mark.parametrize(
    "control_pair_key",
    [
        "",
        "   ",
        "pair with space",
        "pair\nwith-newline",
        "pair/with/slash",
        "x" * 129,
    ],
)
def test_manifest_rejects_invalid_control_pair_keys(
    tmp_path: Path,
    control_pair_key: str,
) -> None:
    campaign_dir = _write_campaign(tmp_path / "campaign", session_id="session-a")

    with pytest.raises(ValueError, match="control_pair_key"):
        build_proposal_trajectory_manifest(
            campaign_dir,
            observed_control_arm="on",
            control_pair_key=control_pair_key,
            generated_at="2026-06-12T00:00:00+00:00",
        )


def test_manifest_does_not_leak_raw_prompt_response_patch_or_measurements(
    tmp_path: Path,
) -> None:
    campaign_dir = _write_campaign(tmp_path / "campaign", session_id="session-a")

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="record_only",
        generated_at="2026-06-12T00:00:00+00:00",
    )

    rendered = json.dumps(manifest, sort_keys=True)
    for forbidden_key in (
        "code_content",
        "prompt_text",
        "user_prompt",
        "system_blocks",
        "response",
        "raw_measurement_diagnostics",
        "bks_gap",
        "aa_rows",
        "hypothesis_text",
    ):
        assert f'"{forbidden_key}"' not in rendered
    for forbidden_value in (
        "RAW PROMPT SHOULD NOT LEAK",
        "RAW RESPONSE SHOULD NOT LEAK",
        "FULL PATCH BODY SHOULD NOT LEAK",
        "RAW HYPOTHESIS SHOULD NOT LEAK",
        "RAW BRANCH LESSON RATIONALE SHOULD NOT LEAK",
    ):
        assert forbidden_value not in rendered


def test_manifest_only_joins_replayable_formal_candidate_rows(
    tmp_path: Path,
) -> None:
    campaign_dir = _write_campaign(
        tmp_path / "campaign",
        session_id="session-a",
        formal_overrides={
            "artifact_status": "skipped",
            "replay_identity_status": "missing",
            "missing_replay_identity_keys": ["base_workspace_ref"],
        },
    )

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert manifest["counts"]["formal_candidate_count"] == 1
    assert manifest["counts"]["formal_candidate_replayable_count"] == 0
    assert manifest["counts"]["formal_candidate_joined_session_count"] == 0
    assert manifest["coverage"]["missing_join_count"] == 1
    session = manifest["sessions"][0]
    assert "formal_candidate_ref" not in session["proposal_fingerprint"]
    assert session["replayability"]["formal_candidate_joined"] is False
    assert (
        session["replayability"]["formal_candidate_join_status"]
        == "missing_formal_candidate_join"
    )


def test_compares_distributions_and_labels_observational_only(tmp_path: Path) -> None:
    left_campaign = _write_campaign(
        tmp_path / "left",
        session_id="session-a",
        call_kinds=("hypothesis",),
        selected_surface="repair",
        action="modify",
        target_file="solver.py",
        mechanism_ids=("mechanism-a",),
        family_tokens={"research_signal": 10, "governance": 10},
    )
    right_campaign = _write_campaign(
        tmp_path / "right",
        session_id="session-b",
        request_id="request-b",
        branch_id="branch-b",
        call_kinds=("hypothesis", "code"),
        selected_surface="solver_design",
        action="create_new",
        target_file="operators/new.py",
        mechanism_ids=("mechanism-b", "mechanism-c"),
        family_tokens={"research_signal": 4, "feedback": 12},
    )
    left = build_proposal_trajectory_manifest(
        left_campaign,
        observed_control_arm="on",
        generated_at="2026-06-12T00:00:00+00:00",
    )
    right = build_proposal_trajectory_manifest(
        right_campaign,
        observed_control_arm="record_only",
        generated_at="2026-06-12T00:00:00+00:00",
    )

    comparison = build_proposal_trajectory_comparison(
        left,
        right,
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert comparison["schema_version"] == COMPARISON_SCHEMA_VERSION
    assert comparison["report_only"] is True
    assert comparison["observational_only"] is True
    assert comparison["llm_deterministic_replay"] is False
    assert comparison["control_pair_key"] == ""
    assert comparison["causal_replay_label"] == (
        "observational_only_not_causal_llm_trajectory_replay"
    )
    assert comparison["summary"]["left"] == {
        "session_count": 1,
        "trace_count": 1,
        "formal_candidate_count": 1,
    }
    assert comparison["summary"]["right"] == {
        "session_count": 1,
        "trace_count": 2,
        "formal_candidate_count": 1,
    }
    assert comparison["context_arm_fingerprints"]["left"][
        "proposal_context_ablation"
    ] == "full"
    assert comparison["context_arm_fingerprints"]["right"][
        "proposal_context_ablation"
    ] == "full"
    assert comparison["summary"]["delta"]["trace_count"] == 1
    assert comparison["call_kind_counts"]["delta"] == {"code": 1, "hypothesis": 0}
    assert comparison["proposal_distributions"]["selected_surface"]["left"] == {
        "repair": 1,
        "solver_design": 0,
    }
    assert comparison["proposal_distributions"]["selected_surface"]["right"] == {
        "repair": 0,
        "solver_design": 1,
    }
    assert comparison["proposal_distributions"]["mechanism_id"]["right"] == {
        "mechanism-a": 0,
        "mechanism-b": 1,
        "mechanism-c": 1,
    }
    shares = comparison["prompt_block_family_aggregate_shares"]["families"]
    assert shares["feedback"] == {"left": 0.0, "right": 0.75, "delta": 0.75}
    assert comparison["missing_joins"] == {"left": [], "right": []}


def test_comparison_reports_matched_control_pair_key_without_deterministic_label(
    tmp_path: Path,
) -> None:
    left_campaign = _write_campaign(tmp_path / "left", session_id="session-a")
    right_campaign = _write_campaign(
        tmp_path / "right",
        session_id="session-b",
        request_id="request-b",
        branch_id="branch-b",
    )
    left = build_proposal_trajectory_manifest(
        left_campaign,
        observed_control_arm="on",
        control_pair_key="pair.v1:matched-01",
        generated_at="2026-06-12T00:00:00+00:00",
    )
    right = build_proposal_trajectory_manifest(
        right_campaign,
        observed_control_arm="record_only",
        control_pair_key="pair.v1:matched-01",
        generated_at="2026-06-12T00:00:00+00:00",
    )

    comparison = build_proposal_trajectory_comparison(
        left,
        right,
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert comparison["observational_only"] is False
    assert comparison["llm_deterministic_replay"] is False
    assert comparison["comparison_is_decision_input"] is False
    assert comparison["control_pair_key"] == "pair.v1:matched-01"
    assert comparison["causal_replay_label"] == (
        "control_pair_key_matched_not_deterministic_llm_replay"
    )


def test_comparison_keeps_mismatched_control_pair_keys_observational_only(
    tmp_path: Path,
) -> None:
    left_campaign = _write_campaign(tmp_path / "left", session_id="session-a")
    right_campaign = _write_campaign(
        tmp_path / "right",
        session_id="session-b",
        request_id="request-b",
        branch_id="branch-b",
    )
    left = build_proposal_trajectory_manifest(
        left_campaign,
        observed_control_arm="on",
        control_pair_key="pair.v1:left",
        generated_at="2026-06-12T00:00:00+00:00",
    )
    right = build_proposal_trajectory_manifest(
        right_campaign,
        observed_control_arm="record_only",
        control_pair_key="pair.v1:right",
        generated_at="2026-06-12T00:00:00+00:00",
    )

    comparison = build_proposal_trajectory_comparison(
        left,
        right,
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert comparison["observational_only"] is True
    assert comparison["llm_deterministic_replay"] is False
    assert comparison["control_pair_key"] == ""
    assert comparison["causal_replay_label"] == (
        "observational_only_not_causal_llm_trajectory_replay"
    )


def test_manifest_falls_back_to_branch_code_sequence_for_agentic_pairs(
    tmp_path: Path,
) -> None:
    campaign_dir = _write_branch_sequence_campaign(tmp_path / "campaign")

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert manifest["counts"]["session_count"] == 4
    assert manifest["counts"]["formal_candidate_count"] == 2
    assert manifest["counts"]["formal_candidate_replayable_count"] == 2
    assert manifest["counts"]["formal_candidate_joined_session_count"] == 2
    assert manifest["coverage"]["missing_join_count"] == 2
    assert manifest["coverage"]["formal_candidate_join_basis_counts"] == {
        "branch_code_sequence": 2
    }

    sessions = manifest["sessions"]
    assert sessions[0]["replayability"]["formal_candidate_joined"] is False
    assert sessions[1]["proposal_fingerprint"]["formal_candidate_id"] == "candidate-a"
    assert (
        sessions[1]["proposal_fingerprint"]["formal_candidate_join_basis"]
        == "branch_code_sequence"
    )
    assert sessions[2]["replayability"]["formal_candidate_joined"] is False
    assert sessions[3]["proposal_fingerprint"]["formal_candidate_id"] == "candidate-b"
    assert (
        sessions[3]["proposal_fingerprint"]["formal_candidate_join_basis"]
        == "branch_code_sequence"
    )


def test_manifest_branch_code_sequence_prefers_activation_complete_duplicate(
    tmp_path: Path,
) -> None:
    campaign_dir = _write_activation_duplicate_branch_sequence_campaign(
        tmp_path / "campaign"
    )

    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm="on",
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert manifest["counts"]["session_count"] == 2
    assert manifest["counts"]["formal_candidate_count"] == 2
    assert manifest["counts"]["formal_candidate_replayable_count"] == 2
    assert manifest["counts"]["formal_candidate_joined_session_count"] == 1
    assert manifest["coverage"]["missing_join_count"] == 1
    assert manifest["coverage"]["missing_joins"] == [
        {
            "session_id": "hypothesis-only",
            "branch_id": "branch-activation",
            "reason": "missing_formal_candidate_join",
        }
    ]
    assert manifest["coverage"]["formal_candidate_join_basis_counts"] == {
        "branch_code_sequence": 1
    }

    sessions = manifest["sessions"]
    assert sessions[0]["replayability"]["formal_candidate_joined"] is False
    proposal = sessions[1]["proposal_fingerprint"]
    assert proposal["formal_candidate_id"] == "candidate-activation-complete"
    assert proposal["patch_digest"] == "patch-digest-activation-complete"
    assert proposal["formal_candidate_ref"].endswith(
        "activation-complete/candidate.patch.json"
    )
    assert proposal["formal_candidate_join_basis"] == "branch_code_sequence"


def test_cli_writes_manifest_and_comparison(tmp_path: Path) -> None:
    left_campaign = _write_campaign(tmp_path / "left", session_id="session-a")
    right_campaign = _write_campaign(
        tmp_path / "right",
        session_id="session-b",
        request_id="request-b",
        branch_id="branch-b",
        selected_surface="solver_design",
    )
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
            "--control-pair-key",
            "cli-pair.v1:run-01",
            "--output",
            str(left_manifest),
        ],
    )
    assert left_result.exit_code == 0, left_result.output
    left_summary = json.loads(left_result.output)
    assert left_summary["proposal_context_ablation"] == "full"
    assert left_summary["control_pair_key"] == "cli-pair.v1:run-01"
    left_payload = json.loads(left_manifest.read_text(encoding="utf-8"))
    assert left_payload["control_pair_key"] == "cli-pair.v1:run-01"
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
    assert summary["schema_version"] == COMPARISON_SCHEMA_VERSION
    assert summary["observational_only"] is True
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert comparison["summary"]["left"]["session_count"] == 1
    assert comparison["summary"]["right"]["session_count"] == 1


def test_cli_rejects_invalid_control_pair_key(tmp_path: Path) -> None:
    campaign_dir = _write_campaign(tmp_path / "campaign", session_id="session-a")
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
    assert "ERROR: failed to build proposal trajectory manifest" in result.output
    assert "control_pair_key" in result.output
    assert not manifest_path.exists()


def _write_campaign(
    campaign_dir: Path,
    *,
    session_id: str,
    request_id: str = "request-a",
    branch_id: str = "branch-a",
    call_kinds: tuple[str, ...] = ("hypothesis", "code"),
    selected_surface: str = "repair",
    action: str = "modify",
    target_file: str = "solver.py",
    mechanism_ids: tuple[str, ...] = ("mechanism-a",),
    family_tokens: dict[str, int] | None = None,
    formal_overrides: dict[str, object] | None = None,
) -> Path:
    agentic_dir = campaign_dir / "agentic_sessions"
    prompt_dir = agentic_dir / "prompt_manifests"
    prompt_dir.mkdir(parents=True)

    prompt_refs: list[str] = []
    traces: list[dict[str, object]] = []
    for index, call_kind in enumerate(call_kinds, start=1):
        prompt_ref = f"agentic_sessions/prompt_manifests/{call_kind}.json"
        prompt_refs.append(prompt_ref)
        prompt_hash = f"prompt-hash-{call_kind}"
        ledger_digest = f"ledger-{call_kind}"
        _write_prompt_manifest(
            campaign_dir / prompt_ref,
            call_kind=call_kind,
            prompt_hash=prompt_hash,
            ledger_digest=ledger_digest,
            family_tokens=family_tokens,
        )
        traces.append(
            {
                "trace_id": f"trace-{call_kind}",
                "call_kind": call_kind,
                "phase": f"{call_kind}-phase",
                "prompt_hash": prompt_hash,
                "prompt_manifest_artifact_ref": prompt_ref,
                "prompt_visibility_ledger_digest": ledger_digest,
                "response": "RAW RESPONSE SHOULD NOT LEAK",
            }
        )

    session_index = [
        {
            "schema_version": "agentic-session.v1",
            "session_id": session_id,
            "request_id": request_id,
            "branch_id": branch_id,
            "status": "completed",
            "termination_reason": "completed",
            "context_profile": "algorithm",
            "problem_id": "cvrp",
            "problem_spec_hash": "problem-hash-a",
            "split_manifest_hash": "split-hash-a",
            "seed_ledger_hash": "seed-hash-a",
            "selected_surface": selected_surface,
            "action": action,
            "target_file": target_file,
            "mechanism_ids": list(mechanism_ids),
            "hypothesis_summary": {
                "hypothesis_text": "RAW HYPOTHESIS SHOULD NOT LEAK",
                "target_file": target_file,
            },
            "prompt_manifest_required": True,
            "prompt_manifest_artifact_refs": prompt_refs,
            "prompt_text": "RAW PROMPT SHOULD NOT LEAK",
            "code_content": "FULL PATCH BODY SHOULD NOT LEAK",
        }
    ]
    (agentic_dir / "agentic_session_index.json").write_text(
        json.dumps(session_index, indent=2),
        encoding="utf-8",
    )
    output_dir = agentic_dir / session_id
    output_dir.mkdir()
    (output_dir / "output.json").write_text(
        json.dumps(
            {
                "schema_version": "agentic-proposal-session.v1",
                "artifact_kind": "agentic_proposal_output",
                "session_id": session_id,
                "hypothesis": {
                    "branch_lesson_usage": {
                        "avoided_lessons": [
                            {
                                "lesson_id": "lesson:avoid-duplicate",
                                "source_branch_ids": ["branch-source"],
                                "target_file": target_file,
                                "action": action,
                                "mechanism": mechanism_ids[0],
                                "risk_to_avoid": (
                                    "RAW BRANCH LESSON RATIONALE SHOULD NOT LEAK"
                                ),
                            }
                        ]
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    trace_index = {
        "schema_version": "agentic-session-trace-index.v1",
        "artifact_kind": "agentic_session_trace_index",
        "sessions": [
            {
                "session_id": session_id,
                "request_id": request_id,
                "branch_id": branch_id,
                "problem_id": "cvrp",
                "problem_spec_hash": "problem-hash-a",
                "split_manifest_hash": "split-hash-a",
                "seed_ledger_hash": "seed-hash-a",
                "traces": traces,
            }
        ],
    }
    (agentic_dir / "agentic_session_trace_index.json").write_text(
        json.dumps(trace_index, indent=2),
        encoding="utf-8",
    )
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    row = {
        "schema": "scion.formal_candidate_patch_artifact.v1",
        "candidate_id": f"candidate-{session_id}",
        "session_id": session_id,
        "request_id": request_id,
        "branch_id": branch_id,
        "stage": "screening",
        "patch_digest": "patch-digest-a",
        "artifact_ref": (
            "artifacts/formal_candidates/branch/candidate/candidate.patch.json"
        ),
        "artifact_status": "recorded",
        "replay_identity_status": "complete",
        "missing_replay_identity_keys": [],
        "raw_measurement_diagnostics": {
            "bks_gap": 1.2,
            "aa_rows": [{"case": "raw"}],
        },
    }
    row.update(formal_overrides or {})
    formal_index.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return campaign_dir


def _write_branch_sequence_campaign(campaign_dir: Path) -> Path:
    agentic_dir = campaign_dir / "agentic_sessions"
    agentic_dir.mkdir(parents=True)
    sessions: list[dict[str, object]] = []
    trace_sessions: list[dict[str, object]] = []
    branch_id = "branch-sequence"
    session_specs = [
        ("hypothesis-a", "partial_hypothesis_only", ("hypothesis",), "create_new"),
        ("code-a", "completed", ("tool_selection", "code"), "create_new"),
        ("hypothesis-b", "partial_hypothesis_only", ("hypothesis",), "modify"),
        ("code-b", "completed", ("tool_selection", "code"), "modify"),
    ]
    for index, (session_id, status, call_kinds, action) in enumerate(
        session_specs,
        start=1,
    ):
        prompt_refs: list[str] = []
        traces: list[dict[str, object]] = []
        for call_index, call_kind in enumerate(call_kinds, start=1):
            prompt_ref = (
                f"agentic_sessions/prompt_manifests/"
                f"{session_id}-{call_index}-{call_kind}.json"
            )
            prompt_refs.append(prompt_ref)
            _write_prompt_manifest(
                campaign_dir / prompt_ref,
                call_kind=call_kind,
                prompt_hash=f"prompt-{session_id}-{call_kind}",
                ledger_digest=f"ledger-{session_id}-{call_kind}",
                family_tokens=None,
            )
            traces.append(
                {
                    "trace_id": f"trace-{session_id}-{call_kind}",
                    "call_kind": call_kind,
                    "phase": call_kind,
                    "prompt_hash": f"prompt-{session_id}-{call_kind}",
                    "prompt_manifest_artifact_ref": prompt_ref,
                }
            )
        sessions.append(
            {
                "schema_version": "agentic-session.v1",
                "session_id": session_id,
                "request_id": session_id,
                "branch_id": branch_id,
                "created_at": f"2026-06-12T00:00:0{index}+00:00",
                "status": status,
                "termination_reason": status,
                "context_profile": "algorithm",
                "selected_surface": "vehicle_level",
                "action": action,
                "target_file": "operators/consolidate.py",
                "mechanism_ids": ["mechanism-sequence"],
                "hypothesis_summary": {
                    "target_file": "operators/consolidate.py",
                },
                "prompt_manifest_required": True,
                "prompt_manifest_artifact_refs": prompt_refs,
            }
        )
        trace_sessions.append(
            {
                "session_id": session_id,
                "request_id": session_id,
                "branch_id": branch_id,
                "traces": traces,
            }
        )

    (agentic_dir / "agentic_session_index.json").write_text(
        json.dumps(sessions, indent=2),
        encoding="utf-8",
    )
    (agentic_dir / "agentic_session_trace_index.json").write_text(
        json.dumps(
            {
                "schema_version": "agentic-session-trace-index.v1",
                "artifact_kind": "agentic_session_trace_index",
                "sessions": trace_sessions,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    rows = [
        {
            "schema": "scion.formal_candidate_patch_artifact.v1",
            "candidate_id": "candidate-a",
            "branch_id": branch_id,
            "hypothesis_id": "hypothesis-id-a",
            "stage": "screening",
            "patch_digest": "patch-digest-a",
            "artifact_ref": "artifacts/formal_candidates/branch/a/candidate.patch.json",
            "artifact_status": "recorded",
            "replay_identity_status": "complete",
            "missing_replay_identity_keys": [],
        },
        {
            "schema": "scion.formal_candidate_patch_artifact.v1",
            "candidate_id": "candidate-b",
            "branch_id": branch_id,
            "hypothesis_id": "hypothesis-id-b",
            "stage": "screening",
            "patch_digest": "patch-digest-b",
            "artifact_ref": "artifacts/formal_candidates/branch/b/candidate.patch.json",
            "artifact_status": "recorded",
            "replay_identity_status": "complete",
            "missing_replay_identity_keys": [],
        },
    ]
    formal_index.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return campaign_dir


def _write_activation_duplicate_branch_sequence_campaign(campaign_dir: Path) -> Path:
    agentic_dir = campaign_dir / "agentic_sessions"
    agentic_dir.mkdir(parents=True)
    branch_id = "branch-activation"
    session_specs = [
        ("hypothesis-only", "partial_hypothesis_only", ("hypothesis",), "create_new"),
        ("code-session", "completed", ("tool_selection", "code"), "create_new"),
    ]
    sessions: list[dict[str, object]] = []
    trace_sessions: list[dict[str, object]] = []
    for index, (session_id, status, call_kinds, action) in enumerate(
        session_specs,
        start=1,
    ):
        prompt_refs: list[str] = []
        traces: list[dict[str, object]] = []
        for call_index, call_kind in enumerate(call_kinds, start=1):
            prompt_ref = (
                f"agentic_sessions/prompt_manifests/"
                f"{session_id}-{call_index}-{call_kind}.json"
            )
            prompt_refs.append(prompt_ref)
            _write_prompt_manifest(
                campaign_dir / prompt_ref,
                call_kind=call_kind,
                prompt_hash=f"prompt-{session_id}-{call_kind}",
                ledger_digest=f"ledger-{session_id}-{call_kind}",
                family_tokens=None,
            )
            traces.append(
                {
                    "trace_id": f"trace-{session_id}-{call_kind}",
                    "call_kind": call_kind,
                    "phase": call_kind,
                    "prompt_hash": f"prompt-{session_id}-{call_kind}",
                    "prompt_manifest_artifact_ref": prompt_ref,
                }
            )
        sessions.append(
            {
                "schema_version": "agentic-session.v1",
                "session_id": session_id,
                "request_id": session_id,
                "branch_id": branch_id,
                "created_at": f"2026-06-12T00:00:0{index}+00:00",
                "status": status,
                "termination_reason": status,
                "context_profile": "algorithm",
                "selected_surface": "algorithm_surface",
                "action": action,
                "target_file": "components/operator.py",
                "mechanism_ids": ["mechanism-activation"],
                "hypothesis_summary": {
                    "target_file": "components/operator.py",
                },
                "prompt_manifest_required": True,
                "prompt_manifest_artifact_refs": prompt_refs,
            }
        )
        trace_sessions.append(
            {
                "session_id": session_id,
                "request_id": session_id,
                "branch_id": branch_id,
                "traces": traces,
            }
        )

    (agentic_dir / "agentic_session_index.json").write_text(
        json.dumps(sessions, indent=2),
        encoding="utf-8",
    )
    (agentic_dir / "agentic_session_trace_index.json").write_text(
        json.dumps(
            {
                "schema_version": "agentic-session-trace-index.v1",
                "artifact_kind": "agentic_session_trace_index",
                "sessions": trace_sessions,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    rows = [
        {
            "schema": "scion.formal_candidate_patch_artifact.v1",
            "candidate_id": "candidate-activation-less",
            "branch_id": branch_id,
            "hypothesis_id": "hypothesis-activation",
            "stage": "screening",
            "target_files": ["components/operator.py"],
            "proposal_target_files": ["components/operator.py"],
            "patch_digest": "patch-digest-activation-less",
            "artifact_ref": (
                "artifacts/formal_candidates/branch/activation-less/"
                "candidate.patch.json"
            ),
            "artifact_status": "recorded",
            "replay_identity_status": "complete",
            "missing_replay_identity_keys": [],
        },
        {
            "schema": "scion.formal_candidate_patch_artifact.v1",
            "candidate_id": "candidate-activation-complete",
            "branch_id": branch_id,
            "hypothesis_id": "hypothesis-activation",
            "stage": "screening",
            "target_files": [
                "components/operator.py",
                "config/activation_registry.yaml",
            ],
            "proposal_target_files": ["components/operator.py"],
            "activation_files": ["config/activation_registry.yaml"],
            "patch_digest": "patch-digest-activation-complete",
            "artifact_ref": (
                "artifacts/formal_candidates/branch/activation-complete/"
                "candidate.patch.json"
            ),
            "artifact_status": "recorded",
            "replay_identity_status": "complete",
            "missing_replay_identity_keys": [],
        },
    ]
    formal_index.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return campaign_dir


def _write_prompt_manifest(
    path: Path,
    *,
    call_kind: str,
    prompt_hash: str,
    ledger_digest: str,
    family_tokens: dict[str, int] | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tokens = family_tokens or {"research_signal": 10, "governance": 10}
    total_tokens = sum(tokens.values())
    families = {
        family: {
            "char_count": token_count * 4,
            "token_estimate": token_count,
            "token_share": round(token_count / total_tokens, 6),
        }
        for family, token_count in tokens.items()
    }
    payload = {
        "schema_version": "api-visible-prompt-manifest.v3",
        "artifact_kind": "api_visible_prompt_manifest",
        "call_kind": call_kind,
        "prompt_hash": prompt_hash,
        "context_profile_metadata": {
            "schema_version": "hypothesis_context_profile.v1",
            "profile": "algorithm",
            "proposal_context_ablation": "full",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "visibility_ledger_summary": {"ledger_digest": ledger_digest},
        "block_family_accounting": {
            "total_chars": total_tokens * 4,
            "total_token_estimate": total_tokens,
            "families": families,
        },
        "omitted_sections": [
            "hidden_validation",
            "branch_lesson_usage_hidden_context",
        ],
        "truncated_sections": [
            "long_feedback",
            "branch_lesson_usage_context",
        ],
        "prompt_text": "RAW PROMPT SHOULD NOT LEAK",
        "user_prompt": "RAW PROMPT SHOULD NOT LEAK",
        "system_blocks": [{"text": "RAW PROMPT SHOULD NOT LEAK"}],
    }
    if call_kind == "code":
        payload["code_phase_source_guarantees"] = {
            "schema_version": "code-phase-source-visibility-guarantees.v1",
            "target_source_visible": True,
            "required_integration_source_visible": True,
            "algorithm_file_read_source_visible": True,
            "protected_source_visible": True,
            "target_file_create_mode": False,
            "required_integration_source_count": 1,
            "algorithm_file_read_source_count": 1,
            "missing_required_source_paths": [],
        }
        payload["code_file_visibility_ledger"] = {
            "schema_version": "code-file-visibility-ledger.v1",
            "target_file": {
                "file_path": "solver.py",
                "source_status": "current_branch_source",
                "source_provenance": "branch_workspace",
                "prompt_visibility_status": "full_current_source_visible",
                "full_content_visible_in_rendered_prompt": True,
            },
            "integration_files": [
                {
                    "file_path": "policies/baseline_algorithm.py",
                    "full_content_visible_in_rendered_prompt": True,
                }
            ],
            "algorithm_file_reads": [
                {
                    "file_path": "policies/baseline_modules/scheduler.py",
                    "full_content_visible_in_rendered_prompt": True,
                }
            ],
        }
    if call_kind.startswith("hypothesis"):
        payload["hypothesis_target_source_visibility_ledger"] = {
            "schema_version": "hypothesis-target-source-visibility-ledger.v1",
            "target_source_required": True,
            "visibility_status": "full_dedicated_source_visible",
            "preflight_section_status": "included",
            "owner_source": {
                "full_content_visible_in_dedicated_source_section": True,
            },
        }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
