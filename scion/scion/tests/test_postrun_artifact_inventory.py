from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


TOOL_PATH = Path(__file__).parents[2] / "tools" / "postrun_artifact_inventory.py"
SPEC = importlib.util.spec_from_file_location("postrun_artifact_inventory", TOOL_PATH)
assert SPEC is not None
inventory_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(inventory_tool)


def test_inventory_json_with_db_trace_index_and_traces(tmp_path: Path) -> None:
    run_root = tmp_path / "run-a"
    campaign_dir = run_root / "campaign"
    traces_dir = campaign_dir / "llm_traces"
    sessions_dir = campaign_dir / "agentic_sessions"
    traces_dir.mkdir(parents=True)
    sessions_dir.mkdir()

    _write_json(
        run_root / "run_status.json",
        {
            "run_name": "normal-run",
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "last_stop_reason": "max_rounds_exhausted",
            "wrapper_exit_status": 0,
            "requested_rounds": 2,
        },
    )
    (run_root / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (run_root / "launch.env").write_text("SCION_MODEL=gpt-5.5\n", encoding="utf-8")
    (run_root / "command.txt").write_text("./run.sh\n", encoding="utf-8")
    (run_root / "run.log").write_text(
        "\n".join(
            [
                "POSTRUN_REPORTS_STARTED_AT:2026-06-18T00:00:00Z",
                "POSTRUN_REPORT_DIR:/tmp/run-a/postrun_acceptance",
                "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED:expected=a actual=b paths=docs",
                "POSTRUN_REPORTS_FINISHED_AT:2026-06-18T00:01:00Z",
            ]
        ),
        encoding="utf-8",
    )
    (run_root / "exit.txt").write_text(
        "\n".join(
            [
                "WRAPPER_EXIT_STATUS:0",
                "POSTRUN_ACCEPTANCE_DIR:/tmp/run-a/postrun_acceptance",
            ]
        ),
        encoding="utf-8",
    )
    postrun_payloads = {
        ("summaries", "normal.summary.json"): {},
        ("failures", "normal.failures.json"): {},
        (
            "research_efficiency",
            "normal.research_efficiency.v1.json",
        ): {
            "measurement_readiness": {
                "status": "ready",
                "mde_at_power_80": 9.9,
            },
            "protocol_effects_vs_mde": {
                "mde_source": "measurement_readiness.mde_at_power_80",
            },
            "cross_branch_observability": {"branch_lesson_record_count": 1},
            "research_continuity": {
                "same_mechanism_followup": {"selection_rate": 1.0},
                "branch_lesson_usage": {"satisfaction_rate": 1.0},
                "weak_positive_transfer": {"acceptance_rate": 1.0},
            },
            "fresh_runtime_replay_drain": {"attempts": 1},
        },
        (
            "manifests",
            "normal.proposal_trajectory_manifest.v1.json",
        ): {
            "counts": {"prompt_manifest_loaded_count": 2},
            "branch_lesson_usage_accounting": {
                "field_counts": {"avoided_lessons": 1},
            },
            "sessions": [
                {
                    "trace_fingerprints": [
                        {"visibility_ledger_digest": "visibility-ledger-1"}
                    ],
                }
            ],
        },
        (
            "analysis_brief",
            "normal.postrun_analysis_brief.v1.json",
        ): {},
        ("inventory", "normal.postrun_artifact_inventory.v1.json"): {},
        ("rebuild", "rebuild_manifest.v1.json"): {},
    }
    for (subdir, filename), payload in postrun_payloads.items():
        _write_json(run_root / "postrun_acceptance" / subdir / filename, payload)
    _write_json(
        campaign_dir / "status.json",
        {
            "effective_rounds_completed": 2,
            "screened_experiments": 1,
            "proposal_attempts_total": 3,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
        },
    )
    _write_json(
        sessions_dir / "agentic_session_trace_index.json",
        {
            "session_count": 1,
            "trace_count": 4,
            "sessions": [
                {
                    "session_id": "s-1",
                    "branch_id": "branch-1",
                    "traces": [
                        {"trace_id": "t-tool", "request_kind": "tool_selection"},
                        {"trace_id": "t-hyp", "request_kind": "hypothesis"},
                        {
                            "trace_id": "t-target",
                            "request_kind": "target_intent",
                            "prompt_manifest_artifact_ref": "prompt-manifest-1",
                        },
                        {"trace_id": "t-code", "request_kind": "code"},
                    ],
                }
            ],
        },
    )
    _write_json(
        sessions_dir / "agentic_session_index.json",
        {
            "sessions": [
                {
                    "session_id": "s-1",
                    "branch_id": "branch-1",
                    "prompt_manifest_refs": ["prompt-manifest-1"],
                }
            ]
        },
    )
    _write_json(
        traces_dir / "20260606T000000_tool_selection_branch_1.json",
        {"request_kind": "tool_selection", "ok": True, "branch_id": "branch-1"},
    )
    _write_json(
        traces_dir / "20260606T000000_hypothesis_branch_1.json",
        {"request_kind": "hypothesis", "ok": True, "branch_id": "branch-1"},
    )
    _write_json(
        traces_dir / "20260606T000000_target_intent_branch_1.json",
        {
            "request_kind": "hypothesis",
            "ok": True,
            "branch_id": "branch-1",
            "target_intent": {"change_locus": "solver_design"},
            "prompt_manifest_ref": "prompt-manifest-1",
        },
    )
    _write_json(
        traces_dir / "20260606T000001_code_branch_1.json",
        {"trace_kind": "code", "status": "failed", "branch_id": "branch-1"},
    )
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    formal_index.write_text('{"candidate_id":"cand-1"}\n', encoding="utf-8")
    _write_db(campaign_dir / "scion.db")

    data = inventory_tool.build_inventory(run_root)
    markdown = inventory_tool.render_markdown(data)

    assert data["run_root"] == str(run_root)
    assert data["campaign_dir"] == str(campaign_dir)
    assert data["run_name"] == "normal-run"
    assert data["lifecycle"]["prepared_only"] is False
    assert data["lifecycle"]["evidence_scope"] == "postrun_campaign"
    assert data["validity"]["invalid_infra_only"] is False
    assert data["counters"]["requested_rounds"] == 2
    assert data["counters"]["effective_rounds_completed"] == 2
    assert data["counters"]["formal_screened_candidates"] == 1
    assert data["llm_traces"]["trace_count"] == 4
    assert data["llm_traces"]["by_kind"] == {
        "code": 1,
        "hypothesis": 1,
        "hypothesis_target_intent": 1,
        "tool_selection": 1,
    }
    assert data["llm_traces"]["by_status"] == {"failed": 1, "ok": 3}
    assert data["llm_traces"]["index_trace_count"] == 4
    assert data["llm_traces"]["index_session_count"] == 1
    assert data["launcher"]["artifacts"] == {
        "command.txt": True,
        "exit.txt": True,
        "launch.env": True,
        "prepared_handoff": False,
        "pre_campaign_completion_preflight.v1.json": False,
        "prepared_run_manifest.md": False,
        "prepared_run_manifest.v1.json": False,
        "run.log": True,
        "run.sh": True,
    }
    prepared_contract = data["launcher"]["prepared_run_contract"]
    assert prepared_contract["schema_version"] == (
        "scion.prepared_run_contract_inventory.v1"
    )
    assert prepared_contract["report_only"] is True
    assert prepared_contract["quality_judgment"] is False
    assert prepared_contract["decision_features_excluded"] is True
    assert prepared_contract["contract_complete"] is False
    assert prepared_contract["checks"]["manifest_present"]["passed"] is False
    assert data["launcher"]["status_fields"] == {"wrapper_exit_status": 0}
    assert data["launcher"]["run_log_markers"] == {
        "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED": 1,
        "POSTRUN_REPORT_DIR": 1,
        "POSTRUN_REPORTS_FINISHED_AT": 1,
        "POSTRUN_REPORTS_STARTED_AT": 1,
    }
    assert data["launcher"]["exit_markers"] == {
        "POSTRUN_ACCEPTANCE_DIR": 1,
        "WRAPPER_EXIT_STATUS": 1,
    }
    assert data["postrun_reports"]["exists"] is True
    assert data["postrun_reports"]["counts"] == {
        "analysis_brief": 1,
        "failures": 1,
        "inventory": 1,
        "manifests": 1,
        "rebuild": 1,
        "research_efficiency": 1,
        "summaries": 1,
    }
    assert data["analysis_handoff"] == (
        "scion/docs/operations/postrun-analysis-handoff.md"
    )
    phase4 = data["phase4_evidence_coverage"]
    assert phase4["report_only"] is True
    assert phase4["quality_judgment"] is False
    assert phase4["decision_features_excluded"] is True
    requirements = phase4["requirements"]
    for key in (
        "target_intent_trace",
        "hypothesis_trace",
        "code_trace",
        "formal_candidate_artifact",
        "proposal_trajectory_manifest",
        "prompt_manifest_loaded",
        "research_efficiency_report",
        "measurement_readiness",
        "protocol_effect_vs_mde",
        "branch_lesson_transfer",
        "research_continuity",
        "runtime_feedback",
        "source_visibility",
    ):
        assert requirements[key]["available"] is True
    assert requirements["target_intent_trace"]["count"] == 1
    assert requirements["formal_candidate_artifact"]["count"] == 1
    assert requirements["prompt_manifest_loaded"]["count"] == 2
    assert requirements["research_continuity"]["count"] == 1
    assert "## Phase 4 Evidence Coverage" in markdown
    assert "## Launcher Artifacts" in markdown
    assert "### Prepared Run Contract Checks" in markdown
    assert "| target_intent_trace | True | 1 | llm_traces or trace_index |" in markdown
    assert (
        "| research_continuity | True | 1 | "
        "research-efficiency research_continuity |"
    ) in markdown

    assert len(data["branches"]) == 1
    branch = data["branches"][0]
    assert branch["branch_id"] == "branch-1"
    assert branch["state"] == "ready_validate"
    assert branch["lineage_id"] == "lineage-1"
    assert branch["base_champion_hash"] == "basehash"
    assert branch["current_code_hash"] == "codehash"
    assert branch["best_quality_checkpoint_id"] == "checkpoint-best"
    assert branch["last_valid_checkpoint_id"] == "checkpoint-last"
    assert branch["rollback_count"] == 1
    assert branch["failure_codes"] == ["CONTRACT"]
    assert branch["hypothesis_count"] == 2
    assert branch["event_count"] == 3
    assert branch["session_count"] == 1
    assert branch["trace_count"] == 4
    assert data["events"]["by_kind"] == {"decision": 1, "experiment": 2}
    assert data["events"]["by_decision"] == {
        "continue_explore": 1,
        "queue_validate": 1,
    }
    assert data["events"]["by_stage"] == {"screening": 2}
    assert data["hypotheses"]["count"] == 2
    assert data["hypotheses"]["by_status"] == {"active": 1, "rejected": 1}
    assert data["hypotheses"]["by_action"] == {"create_new": 1, "modify": 1}
    assert data["hypotheses"]["by_change_locus"] == {"solver_design": 2}


def test_prepared_manifest_contract_accepts_mirrored_runner_paths(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "prepared-run"
    campaign_dir = run_root / "campaign"
    config_dir = run_root / "config"
    campaign_dir.mkdir(parents=True)
    config_dir.mkdir()
    for name in ("problem.yaml", "protocol.yaml", "split.yaml", "seeds.yaml"):
        (config_dir / name).write_text("ok: true\n", encoding="utf-8")

    remote_root = f"/home/xjy-ubuntu/research/scion-experiments/{run_root.name}"
    command = (
        "/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m scion.cli.main run "
        f"--problem {remote_root}/config/problem.yaml "
        f"--protocol {remote_root}/config/protocol.yaml "
        f"--split {remote_root}/config/split.yaml "
        f"--seeds {remote_root}/config/seeds.yaml "
        f"--campaign-dir {remote_root}/campaign "
        "--rounds 1 --agentic-proposal"
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "campaign_state_mutated": False,
            "scheduler_state_mutated": False,
            "promotion_state_mutated": False,
            "run_root": remote_root,
            "campaign_dir": f"{remote_root}/campaign",
            "problem_family": "cvrp",
            "analysis_intent": "Prepared CVRP analysis intent.",
            "acceptance_focus": [
                "Interpret evidence against A/A MDE.",
                "Keep manifest evidence out of DecisionFeatures.",
            ],
            "research_focus": _cvrp_research_focus(),
            "resume_from_campaign": f"{remote_root}/previous/campaign",
            "command": command,
            "model": {
                "name": "gpt-5.5",
                "base_url": "http://127.0.0.1:8080",
                "completion_preflight": True,
            },
            "git": {
                "commit": _git_head_short(),
                "runtime_guard_paths": "scion/scion :(exclude)scion/scion/tests",
            },
            "config": {
                "problem": f"{remote_root}/config/problem.yaml",
                "protocol": f"{remote_root}/config/protocol.yaml",
                "split": f"{remote_root}/config/split.yaml",
                "seeds": f"{remote_root}/config/seeds.yaml",
                "data_root": "/home/xjy-ubuntu/research/scion-data",
            },
            "report_metadata": {
                "control_pair_key": "cvrp.prepared:rep01",
                "postrun_reports": True,
                "postrun_acceptance_families": [
                    "summaries",
                    "failures",
                    "research_efficiency",
                    "manifests",
                    "analysis_brief",
                    "inventory",
                    "rebuild",
                ],
            },
        },
    )
    (run_root / "prepared_run_manifest.md").write_text("# prepared\n", encoding="utf-8")
    (run_root / "command.txt").write_text(
        "\n".join(
            [
                "environment:",
                "SCION_MODEL=gpt-5.5",
                "",
                "report_metadata:",
                f"PREPARED_RUN_MANIFEST={remote_root}/prepared_run_manifest.v1.json",
                "",
                "command:",
                command,
            ]
        ),
        encoding="utf-8",
    )

    data = inventory_tool.build_inventory(run_root)
    markdown = inventory_tool.render_markdown(data)

    contract = data["launcher"]["prepared_run_contract"]
    assert contract["contract_complete"] is True
    assert contract["problem_family"] == "cvrp"
    assert contract["model"] == "gpt-5.5"
    assert contract["control_pair_key"] == "cvrp.prepared:rep01"
    assert contract["analysis_intent"] == "Prepared CVRP analysis intent."
    assert contract["acceptance_focus"] == [
        "Interpret evidence against A/A MDE.",
        "Keep manifest evidence out of DecisionFeatures.",
    ]
    assert contract["resume_from_campaign"] == f"{remote_root}/previous/campaign"
    assert contract["research_focus"]["measurement_opportunity_diagnostics"][
        "screening_mde_at_power_80"
    ] == 9.9
    assert contract["checks"]["cvrp_measurement_handoff_present"]["passed"] is True
    assert (
        contract["checks"]["cvrp_measurement_handoff_reason_codes"]["passed"] is True
    )
    assert all(item["passed"] for item in contract["checks"].values())
    assert contract["git"]["consistent"] is True
    assert "- Prepared contract complete: True" in markdown
    assert "| config_paths_resolvable | True |  |" in markdown


def test_prepared_manifest_contract_requires_cvrp_measurement_handoff(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "prepared-run"
    campaign_dir = run_root / "campaign"
    config_dir = run_root / "config"
    campaign_dir.mkdir(parents=True)
    config_dir.mkdir()
    for name in ("problem.yaml", "protocol.yaml", "split.yaml", "seeds.yaml"):
        (config_dir / name).write_text("ok: true\n", encoding="utf-8")

    command = (
        f"{sys.executable} -m scion.cli.main run "
        f"--problem {config_dir / 'problem.yaml'} "
        f"--protocol {config_dir / 'protocol.yaml'} "
        f"--split {config_dir / 'split.yaml'} "
        f"--seeds {config_dir / 'seeds.yaml'} "
        f"--campaign-dir {campaign_dir} --rounds 1 --agentic-proposal"
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "campaign_state_mutated": False,
            "scheduler_state_mutated": False,
            "promotion_state_mutated": False,
            "run_root": str(run_root),
            "campaign_dir": str(campaign_dir),
            "problem_family": "cvrp",
            "analysis_intent": "Prepared CVRP analysis intent.",
            "acceptance_focus": [
                "Interpret evidence against A/A MDE.",
                "Keep manifest evidence out of DecisionFeatures.",
            ],
            "resume_from_campaign": "/tmp/source-campaign",
            "command": command,
            "model": {
                "name": "gpt-5.5",
                "base_url": "http://127.0.0.1:8080",
                "completion_preflight": True,
            },
            "git": {
                "commit": _git_head_short(),
                "runtime_guard_paths": "scion/tools",
            },
            "config": {
                "problem": str(config_dir / "problem.yaml"),
                "protocol": str(config_dir / "protocol.yaml"),
                "split": str(config_dir / "split.yaml"),
                "seeds": str(config_dir / "seeds.yaml"),
            },
            "report_metadata": {
                "control_pair_key": "cvrp.prepared:rep01",
                "postrun_reports": True,
                "postrun_acceptance_families": [
                    "summaries",
                    "failures",
                    "research_efficiency",
                    "manifests",
                    "analysis_brief",
                    "inventory",
                    "rebuild",
                ],
            },
        },
    )
    (run_root / "prepared_run_manifest.md").write_text("# prepared\n", encoding="utf-8")
    (run_root / "command.txt").write_text(
        "\n".join(
            [
                "report_metadata:",
                f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}",
                "",
                "command:",
                command,
            ]
        ),
        encoding="utf-8",
    )

    data = inventory_tool.build_inventory(run_root)

    contract = data["launcher"]["prepared_run_contract"]
    assert contract["contract_complete"] is False
    assert contract["checks"]["cvrp_measurement_handoff_present"]["passed"] is False
    assert (
        contract["checks"]["cvrp_measurement_handoff_reason_codes"]["passed"] is False
    )


def test_inventory_marks_prepared_only_resume_snapshot_not_current_run(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "prepared-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "scion.launcher_prepare.v1",
            "status": "prepared",
            "prepared_only": True,
            "resume_from_campaign": "/tmp/source-campaign",
            "copied_campaign_status_present": True,
            "copied_campaign_summary_present": True,
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "execution": {"rounds": 3},
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "run_status.json",
        {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "effective_rounds_completed": 7,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 7,
            "protocol_evaluated_candidates": 7,
        },
    )

    data = inventory_tool.build_inventory(run_root)
    markdown = inventory_tool.render_markdown(data)

    assert data["lifecycle"]["prepared_only"] is True
    assert data["lifecycle"]["evidence_scope"] == (
        "prepared_launch_root_with_resume_snapshot"
    )
    assert data["validity"]["run_validity_status"] == "prepared_only"
    assert data["validity"]["run_completeness_status"] == "not_started"
    assert data["validity"]["last_stop_reason"] == "prepared_only_not_launched"
    assert data["counters"] == {
        "requested_rounds": 3,
        "effective_rounds_completed": 0,
        "formal_screened_candidates": 0,
        "protocol_evaluated_candidates": 0,
        "screened_experiments": 0,
        "proposal_attempts_total": 0,
    }
    assert data["phase4_evidence_coverage"]["prepared_only"] is True
    assert "PREPARED-ONLY ROOT" in markdown
    assert "not current-run postrun evidence" in markdown


def test_inventory_marks_preflight_failed_resume_snapshot_not_current_run(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "preflight-failed-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 64,
            "pre_campaign_completion_preflight": "failed",
            "pre_campaign_completion_preflight_classification": (
                "not_authenticated"
            ),
            "pre_campaign_completion_preflight_detail_file": (
                "pre_campaign_completion_preflight.v1.json"
            ),
            "pre_campaign_completion_preflight_login_url_present": True,
            "pre_campaign_completion_preflight_operator_action": (
                "Refresh the local proxy login, then rerun launch readiness until "
                "launch_ready=true."
            ),
        },
    )
    _write_json(
        run_root / "pre_campaign_completion_preflight.v1.json",
        {
            "ok": False,
            "chat": {"classification": "not_authenticated"},
            "login_url": "https://auth.example.test/login",
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "execution": {"rounds": 5},
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "run_status.json",
        {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "effective_rounds_completed": 7,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 7,
            "measurement_readiness": {"status": "ready"},
        },
    )
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    formal_index.write_text('{"candidate_id":"old-candidate"}\n', encoding="utf-8")
    traces_dir = campaign_dir / "llm_traces"
    traces_dir.mkdir()
    _write_json(
        traces_dir / "20260606T000000_hypothesis_branch_1.json",
        {"request_kind": "hypothesis", "ok": True, "branch_id": "branch-1"},
    )
    _write_json(
        campaign_dir / "agentic_sessions" / "agentic_session_trace_index.json",
        {
            "session_count": 1,
            "trace_count": 1,
            "sessions": [
                {
                    "session_id": "s-1",
                    "branch_id": "branch-1",
                    "traces": [{"trace_id": "t-hyp", "request_kind": "hypothesis"}],
                }
            ],
        },
    )
    _write_db(campaign_dir / "scion.db")

    data = inventory_tool.build_inventory(run_root)
    markdown = inventory_tool.render_markdown(data)

    assert data["lifecycle"]["prepared_only"] is False
    assert data["lifecycle"]["pre_campaign_completion_preflight_failed"] is True
    assert data["lifecycle"]["current_run_evidence"] is False
    assert data["lifecycle"]["evidence_scope"] == (
        "pre_campaign_preflight_failed_with_resume_snapshot"
    )
    assert data["branches"] == []
    assert data["events"]["by_kind"] == {}
    assert data["hypotheses"]["count"] == 0
    assert data["llm_traces"]["trace_count"] == 0
    assert data["resume_snapshot"]["present"] is True
    assert data["resume_snapshot"]["current_run_evidence"] is False
    assert data["resume_snapshot"]["branch_count"] == 1
    assert data["resume_snapshot"]["llm_trace_count"] == 1
    assert data["resume_snapshot"]["hypothesis_count"] == 2
    assert data["resume_snapshot"]["events_by_kind"] == {
        "decision": 1,
        "experiment": 2,
    }
    assert data["launcher"]["artifacts"][
        "pre_campaign_completion_preflight.v1.json"
    ] is True
    assert data["launcher"]["status_fields"][
        "pre_campaign_completion_preflight_classification"
    ] == "not_authenticated"
    assert data["launcher"]["status_fields"][
        "pre_campaign_completion_preflight_login_url_present"
    ] is True
    assert "Refresh the local proxy login" in data["launcher"]["status_fields"][
        "pre_campaign_completion_preflight_operator_action"
    ]
    assert data["validity"] == {
        "run_validity_status": "invalid_infra_only",
        "run_completeness_status": "incomplete",
        "last_stop_reason": "pre_campaign_completion_preflight_failed",
        "invalid_infra_only": True,
    }
    assert data["counters"] == {
        "requested_rounds": 5,
        "effective_rounds_completed": 0,
        "formal_screened_candidates": 0,
        "protocol_evaluated_candidates": 0,
        "screened_experiments": 0,
        "proposal_attempts_total": 0,
    }
    phase4 = data["phase4_evidence_coverage"]
    assert phase4["current_run_evidence"] is False
    assert phase4["pre_campaign_completion_preflight_failed"] is True
    assert phase4["requirements"]["formal_candidate_artifact"]["available"] is False
    assert phase4["requirements"]["measurement_readiness"]["available"] is False
    assert phase4["requirements"]["research_continuity"]["available"] is False
    assert "PRE-CAMPAIGN PREFLIGHT FAILED" in markdown
    assert "## Resume Snapshot" in markdown
    assert "not current-run evidence" in markdown


def test_invalid_infra_only_markdown_without_db(tmp_path: Path) -> None:
    run_root = tmp_path / "infra-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_name": "infra-run",
            "run_validity_status": "invalid_infra_only",
            "run_completeness_status": "incomplete",
            "last_stop_reason": "provider_infra_balance_exhausted",
            "invalid_infra_only": True,
        },
    )

    data = inventory_tool.build_inventory(run_root)
    markdown = inventory_tool.render_markdown(data)

    assert data["validity"]["invalid_infra_only"] is True
    assert data["branches"] == []
    assert data["llm_traces"]["trace_count"] == 0
    assert "INVALID INFRA-ONLY RUN" in markdown
    assert "does not judge research quality" in markdown


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _cvrp_research_focus() -> dict[str, object]:
    return {
        "schema_version": "scion.cvrp_research_focus.v1",
        "scope": "report_only_prepared_handoff",
        "measurement_opportunity_diagnostics": {
            "schema_version": "cvrp_measurement_opportunity_handoff.v1",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "practical_screen_delta": 2.0,
            "screening_mde_at_power_80": 9.9,
            "reason_codes": [
                "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA",
                "TRAJECTORY_DIVERGENT_LOW_SNR",
                "BUDGET_EXHAUSTING_RUNTIME_REPORT_ONLY",
            ],
        },
        "measurable_opportunity_classes": [
            "construction_seed_portfolio",
            "destroy_repair_selection",
            "bounded_local_search_variant",
            "acceptance_or_adaptive_weighting",
        ],
    }


def _git_head_short() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()


def _write_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE branches (
                branch_id TEXT PRIMARY KEY,
                state TEXT,
                lineage_id TEXT,
                base_champion_hash TEXT,
                current_code_hash TEXT,
                best_quality_checkpoint_id TEXT,
                last_valid_checkpoint_id TEXT,
                rollback_count INTEGER,
                failure_codes TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE hypotheses (
                hypothesis_id TEXT PRIMARY KEY,
                branch_id TEXT,
                change_locus TEXT,
                action TEXT,
                status TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE experiment_events (
                event_id TEXT PRIMARY KEY,
                branch_id TEXT,
                event_kind TEXT,
                decision TEXT,
                stage TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO branches VALUES (
                'branch-1', 'ready_validate', 'lineage-1', 'basehash',
                'codehash', 'checkpoint-best', 'checkpoint-last', 1,
                '["CONTRACT"]'
            )
            """
        )
        conn.executemany(
            "INSERT INTO hypotheses VALUES (?, ?, ?, ?, ?)",
            [
                ("hyp-1", "branch-1", "solver_design", "modify", "active"),
                ("hyp-2", "branch-1", "solver_design", "create_new", "rejected"),
            ],
        )
        conn.executemany(
            "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?)",
            [
                ("event-1", "branch-1", "experiment", "continue_explore", "screening"),
                ("event-2", "branch-1", "experiment", "queue_validate", "screening"),
                ("event-3", "branch-1", "decision", None, None),
            ],
        )
