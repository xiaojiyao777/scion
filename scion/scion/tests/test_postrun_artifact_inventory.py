from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from scion.postrun.inventory.prepared_contract import prepared_contract_execution
from scion.postrun.handoff.resume_snapshot import build_resume_branch_summaries

TOOL_PATH = Path(__file__).parents[2] / "tools" / "postrun_artifact_inventory.py"
SPEC = importlib.util.spec_from_file_location("postrun_artifact_inventory", TOOL_PATH)
assert SPEC is not None
inventory_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(inventory_tool)


def test_resume_branch_summaries_preserve_every_branch_and_full_card_identity() -> None:
    branches = [
        {"branch_id": f"branch-{index:02d}", "event_count": index}
        for index in range(15)
    ]
    common_prefix = "x" * 80
    summary = {
        "branch_cards": [
            {
                "branch_id": "branch-00",
                "branch_card_text": common_prefix + "-first",
                "branch_next_action": "first-action",
            },
            {
                "branch_id": "branch-00",
                "branch_card_text": common_prefix + "-second",
                "branch_next_action": "second-action",
            },
        ]
    }

    rows = build_resume_branch_summaries(branches=branches, summary=summary)

    assert len(rows) == 15
    branch_zero = next(row for row in rows if row["branch_id"] == "branch-00")
    assert branch_zero["next_action"] == "second-action"


def test_prepared_contract_runtime_mode_accepts_exact_direct_only() -> None:
    direct = prepared_contract_execution({"proposal_runtime_mode": "direct_v3"})
    missing = prepared_contract_execution({})
    unknown = prepared_contract_execution({"proposal_runtime_mode": "unknown"})
    extra = prepared_contract_execution(
        {"proposal_runtime_mode": "direct_v3", "unexpected": True}
    )

    assert direct["proposal_runtime_mode"] == "direct_v3"
    assert missing["proposal_runtime_mode"] is None
    assert unknown["proposal_runtime_mode"] is None
    assert extra["proposal_runtime_mode"] is None


def test_phase4_coverage_separates_generic_and_code_source_visibility(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-source-coverage"
    campaign_dir = run_root / "campaign"
    traces_dir = campaign_dir / "llm_traces"
    traces_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_name": "source-coverage-run",
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
        },
    )
    _write_json(
        run_root
        / "postrun_acceptance"
        / "manifests"
        / "source_coverage.proposal_trajectory_manifest.v1.json",
        {
            "counts": {"prompt_manifest_loaded_count": 1},
            "sessions": [
                {
                    "trace_fingerprints": [
                        {"visibility_ledger_digest": "visibility-ledger-only"}
                    ]
                }
            ],
        },
    )
    _write_json(
        traces_dir / "20260606T000000_code_branch_1.json",
        {"trace_kind": "code", "status": "ok", "branch_id": "branch-1"},
    )
    _write_minimal_campaign_execution_docs(run_root)

    data = inventory_tool.build_inventory(run_root)

    requirements = data["phase4_evidence_coverage"]["requirements"]
    assert requirements["source_visibility"]["available"] is True
    assert requirements["source_visibility"]["count"] == 1
    assert requirements["code_trace"]["available"] is True
    assert requirements["prompt_signal_density"]["available"] is False
    assert requirements["prompt_signal_density"]["count"] == 0
    assert requirements["code_source_visibility_guarantees"]["available"] is False
    assert requirements["code_source_visibility_guarantees"]["count"] == 0


def test_direct_proposal_attempt_inventory_and_mode_neutral_coverage(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-direct-attempts"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_name": "direct-attempt-run",
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
        },
    )
    _write_minimal_campaign_execution_docs(run_root)
    hypothesis_started = _direct_attempt_payload(
        phase="hypothesis",
        status="started",
    )
    hypothesis = _direct_attempt_payload(
        phase="hypothesis",
        status="generated",
    )
    code_started = _direct_attempt_payload(
        phase="code",
        status="started",
    )
    code_failure = _direct_attempt_payload(
        phase="code",
        status="failed",
    )
    with sqlite3.connect(campaign_dir / "scion.db") as conn:
        conn.execute(
            "CREATE TABLE experiment_events ("
            "event_id TEXT PRIMARY KEY, event_kind TEXT, stage TEXT, "
            "audit_payload_json TEXT)"
        )
        conn.executemany(
            "INSERT INTO experiment_events VALUES (?, ?, ?, ?)",
            [
                (
                    "event-hypothesis-started",
                    "proposal_attempt_transition",
                    "proposal_hypothesis",
                    json.dumps(hypothesis_started),
                ),
                (
                    "event-hypothesis",
                    "proposal_attempt_transition",
                    "proposal_hypothesis",
                    json.dumps(hypothesis),
                ),
                (
                    "event-code-started",
                    "proposal_attempt_transition",
                    "proposal_code",
                    json.dumps(code_started),
                ),
                (
                    "event-code-failed",
                    "proposal_attempt_transition",
                    "proposal_code",
                    json.dumps(code_failure),
                ),
                (
                    "event-malformed",
                    "proposal_attempt_transition",
                    "proposal_code",
                    "{malformed",
                ),
            ],
        )

    data = inventory_tool.build_inventory(run_root)

    attempts = data["database"]["proposal_attempts"]
    assert attempts["row_count"] == 5
    assert attempts["valid_row_count"] == 4
    assert attempts["invalid_row_count"] == 1
    assert attempts["attempt_count"] == 2
    assert attempts["by_runtime_mode"] == {"direct_v3": 4}
    assert attempts["by_phase"] == {"code": 2, "hypothesis": 2}
    assert attempts["by_status"] == {
        "failed": 1,
        "generated": 1,
        "started": 2,
    }
    assert attempts["by_failure_lane"] == {"proposal_repair": 1}
    phase4 = data["phase4_evidence_coverage"]
    assert phase4["proposal_runtime_mode"] == "direct_v3"
    assert phase4["requirements"]["proposal_attempt_transition"]["count"] == 4
    assert phase4["requirements"]["hypothesis_trace"]["available"] is True
    assert phase4["requirements"]["code_trace"]["available"] is True


def test_resumed_inventory_keeps_cumulative_events_but_scopes_outcome_integrity(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "resumed-current-campaign"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_name": "resumed-current-campaign",
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
        },
    )
    _write_json(campaign_dir / "status.json", {"effective_rounds_completed": 1})
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "campaign_id": "current",
            "effective_rounds_completed": 1,
            "execution_outcome_counts": {
                "evaluated": 1,
                "research_rejected": 0,
                "not_evaluated": 0,
                "blocked_infra": 0,
                "resource_exhausted": 0,
                "interrupted": 0,
            },
            "steps": [
                {
                    "round": 1,
                    "branch_id": "branch-1",
                    "execution_outcome": "evaluated",
                }
            ],
        },
    )
    with sqlite3.connect(campaign_dir / "scion.db") as conn:
        conn.execute(
            "CREATE TABLE experiment_events ("
            "campaign_id TEXT, branch_id TEXT, hypothesis_id TEXT, "
            "event_kind TEXT, stage TEXT, decision TEXT, execution_outcome TEXT)"
        )
        conn.executemany(
            "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("old", "branch-1", "h1", "outcome", "screening", None, "evaluated"),
                ("old", "branch-1", "h2", "outcome", "screening", None, "evaluated"),
                (
                    "current",
                    "branch-1",
                    "h2",
                    "outcome",
                    "screening",
                    None,
                    "evaluated",
                ),
            ],
        )

    data = inventory_tool.build_inventory(run_root)

    assert data["events"]["scope_status"] == "database"
    assert data["events"]["by_execution_outcome"] == {"evaluated": 3}
    outcomes = data["execution_outcomes"]
    assert outcomes["lineage"]["scope_status"] == "campaign"
    assert outcomes["lineage"]["campaign_id"] == "current"
    assert outcomes["lineage"]["execution_outcome_counts"] == {"evaluated": 1}
    assert outcomes["summary_lineage_counts_comparable"] is True
    assert outcomes["summary_lineage_counts_consistent"] is True


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
        (config_dir / "split.yaml").write_text(
        "\n".join(
            [
                "version: fixture",
                "screening:",
                "- cvrplib/CMT/CMT2.vrp",
                "- cvrplib/CMT/CMT4.vrp",
                "validation: []",
                "frozen: []",
                "canary: []",
                "",
            ]
        ),
            encoding="utf-8",
        )
        (config_dir / "protocol.yaml").write_text(
            "\n".join(
                [
                    "screening:",
                    "  priority_case_ids:",
                    "  - cvrplib/CMT/CMT2.vrp",
                    "  - cvrplib/CMT/CMT4.vrp",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    remote_root = f"/home/xjy-ubuntu/research/scion-experiments/{run_root.name}"
    command = (
        "/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m scion.cli.main run "
        f"--problem {remote_root}/config/problem.yaml "
        f"--protocol {remote_root}/config/protocol.yaml "
        f"--split {remote_root}/config/split.yaml "
        f"--seeds {remote_root}/config/seeds.yaml "
        f"--campaign-dir {remote_root}/campaign "
        "--rounds 1 --time-limit-sec 30"
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
            "execution": {
                "rounds": 1,
                "time_limit_sec": 30,
                "proposal_runtime_mode": "direct_v3",
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
                    "readiness",
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
    assert contract["execution"]["rounds"] == 1
    assert contract["execution"]["proposal_runtime_mode"] == "direct_v3"
    assert contract["acceptance_focus"] == [
        "Interpret evidence against A/A MDE.",
        "Keep manifest evidence out of DecisionFeatures.",
    ]
    assert contract["resume_from_campaign"] == f"{remote_root}/previous/campaign"
    assert contract["checks"]["command_removed_runtime_controls_absent"]["passed"] is True
    assert all(item["passed"] for item in contract["checks"].values())
    assert contract["git"]["consistent"] is True
    assert contract["git"]["commit"] == contract["git"]["manifest_commit"]
    assert "- Prepared contract complete: True" in markdown
    assert "| config_paths_resolvable | True |  |" in markdown

    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["execution"]["disable_early_stop"] = True
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    failed_contract = inventory_tool.build_inventory(run_root)["launcher"][
        "prepared_run_contract"
    ]
    assert failed_contract["contract_complete"] is False
    assert failed_contract["checks"]["execution_proposal_runtime_mode_consistent"] == {
        "passed": False,
        "detail": (
            "prepared direct_v3 execution contains unsupported fields: "
            "disable_early_stop"
        ),
    }

    manifest["execution"].pop("disable_early_stop")
    manifest["command"] += " --disable-early-stop"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    failed_contract = inventory_tool.build_inventory(run_root)["launcher"][
        "prepared_run_contract"
    ]
    assert failed_contract["contract_complete"] is False
    assert failed_contract["checks"]["command_removed_runtime_controls_absent"] == {
        "passed": False,
        "detail": ["--disable-early-stop"],
    }


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
            "resume_snapshot_ref": "resume_snapshot/resume_source_manifest.v1.json",
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
    assert (
        data["lifecycle"]["resume_snapshot_ref"]
        == "resume_snapshot/resume_source_manifest.v1.json"
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


def test_inventory_marks_missing_or_invalid_root_status_not_current_run(
    tmp_path: Path,
) -> None:
    cases = (
        ("missing-root-status", None, "root_run_status_missing"),
        ("invalid-root-status", "{not-json", "root_run_status_invalid"),
    )
    for run_name, root_status_text, expected_failure_key in cases:
        run_root = tmp_path / run_name
        campaign_dir = run_root / "campaign"
        campaign_dir.mkdir(parents=True)
        if root_status_text is not None:
            (run_root / "run_status.json").write_text(
                root_status_text,
                encoding="utf-8",
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
        _write_db(campaign_dir / "scion.db")

        data = inventory_tool.build_inventory(run_root)
        markdown = inventory_tool.render_markdown(data)

        lifecycle = data["lifecycle"]
        assert lifecycle["launcher_status_unavailable"] is True
        assert lifecycle["launcher_status_failure_key"] == expected_failure_key
        assert lifecycle["current_run_evidence"] is False
        assert lifecycle["invalid_infra_only"] is True
        assert lifecycle["evidence_scope"] == (
            "launcher_status_unavailable_with_resume_snapshot"
        )
        assert data["validity"] == {
            "run_validity_status": "invalid_infra_only",
            "run_completeness_status": "incomplete",
            "last_stop_reason": expected_failure_key,
            "invalid_infra_only": True,
        }
        assert data["counters"] == {
            "requested_rounds": 3,
            "effective_rounds_completed": 0,
            "formal_screened_candidates": 0,
            "protocol_evaluated_candidates": 0,
            "screened_experiments": 0,
            "proposal_attempts_total": 0,
        }
        assert data["resume_snapshot"]["present"] is True
        assert data["resume_snapshot"]["current_run_evidence"] is False
        assert data["phase4_evidence_coverage"]["current_run_evidence"] is False
        assert data["phase4_evidence_coverage"]["launcher_status_unavailable"] is True
        assert (
            data["phase4_evidence_coverage"]["launcher_status_failure_key"]
            == expected_failure_key
        )
        assert "LAUNCHER STATUS UNAVAILABLE" in markdown
        assert "not current-run postrun evidence" in markdown


def test_inventory_marks_missing_or_unreadable_campaign_execution_artifacts_not_current_run(
    tmp_path: Path,
) -> None:
    cases = (
        ("missing-campaign-docs", (), "campaign_execution_artifacts_missing"),
        (
            "unreadable-campaign-docs",
            ("run_status.json", "status.json", "campaign_summary.json"),
            "campaign_execution_artifacts_unreadable",
        ),
    )
    for run_name, invalid_doc_names, expected_failure_key in cases:
        run_root = tmp_path / run_name
        campaign_dir = run_root / "campaign"
        campaign_dir.mkdir(parents=True)
        _write_json(
            run_root / "run_status.json",
            {
                "schema": "outer-wrapper.v1",
                "status": "finished",
                "wrapper_exit_status": 0,
                "campaign_wrapper_exit_status": 0,
            },
        )
        _write_json(
            run_root / "prepared_run_manifest.v1.json",
            {
                "schema_version": "scion.launcher_prepared_run_manifest.v1",
                "execution": {"rounds": 4},
                "resume_from_campaign": "/tmp/source-campaign",
            },
        )
        for doc_name in invalid_doc_names:
            (campaign_dir / doc_name).write_text("{not-json", encoding="utf-8")
        _write_db(campaign_dir / "scion.db")

        data = inventory_tool.build_inventory(run_root)
        markdown = inventory_tool.render_markdown(data)

        lifecycle = data["lifecycle"]
        assert lifecycle["current_run_evidence"] is False
        assert lifecycle["campaign_execution_artifacts_available"] is False
        assert lifecycle["campaign_execution_artifacts_unavailable"] is True
        assert lifecycle["campaign_execution_failure_key"] == expected_failure_key
        assert lifecycle["invalid_infra_only"] is True
        assert lifecycle["evidence_scope"] == (
            "campaign_execution_artifacts_unavailable_with_resume_snapshot"
        )
        assert data["validity"] == {
            "run_validity_status": "invalid_infra_only",
            "run_completeness_status": "incomplete",
            "last_stop_reason": expected_failure_key,
            "invalid_infra_only": True,
        }
        assert data["counters"] == {
            "requested_rounds": 4,
            "effective_rounds_completed": 0,
            "formal_screened_candidates": 0,
            "protocol_evaluated_candidates": 0,
            "screened_experiments": 0,
            "proposal_attempts_total": 0,
        }
        assert data["branches"] == []
        assert data["events"]["by_kind"] == {}
        assert data["hypotheses"]["count"] == 0
        assert data["champions"]["count"] == 0
        assert data["resume_snapshot"]["present"] is True
        assert data["resume_snapshot"]["current_run_evidence"] is False
        assert data["resume_snapshot"]["branch_count"] == 1
        assert data["phase4_evidence_coverage"]["current_run_evidence"] is False
        assert (
            data["phase4_evidence_coverage"]["campaign_execution_artifacts_unavailable"]
            is True
        )
        assert (
            data["phase4_evidence_coverage"]["campaign_execution_failure_key"]
            == expected_failure_key
        )
        assert "CAMPAIGN EXECUTION ARTIFACTS UNAVAILABLE" in markdown
        assert "resume snapshots" in markdown


def test_inventory_marks_stale_resume_campaign_docs_not_current_run(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "stale-resume-docs-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 1,
            "campaign_wrapper_exit_status": 1,
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "execution": {"rounds": 4},
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "run_status.json",
        {
            "schema": "scion.run_wrapper_audit.v1",
            "status": "finished",
            "started_at": "2026-06-20T10:00:00Z",
            "wrapper_exit_status": 0,
            "run_validity_status": "valid",
        },
    )
    _write_json(
        campaign_dir / "status.json",
        {
            "run_validity_status": "valid",
            "formal_screened_candidates": 7,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 7,
            "protocol_evaluated_candidates": 7,
        },
    )
    old_mtime = 1_700_000_000
    for path in (
        campaign_dir / "run_status.json",
        campaign_dir / "status.json",
        campaign_dir / "campaign_summary.json",
    ):
        os.utime(path, (old_mtime, old_mtime))
    _write_json(
        run_root / "campaign_execution_marker.v1.json",
        {
            "schema": "scion.launcher_campaign_execution_marker.v1",
            "started_at": "2026-06-20T11:00:00Z",
            "run_root": str(run_root),
            "campaign_dir": str(campaign_dir),
        },
    )
    marker_mtime = old_mtime + 3600
    os.utime(
        run_root / "campaign_execution_marker.v1.json",
        (marker_mtime, marker_mtime),
    )
    _write_db(campaign_dir / "scion.db")

    data = inventory_tool.build_inventory(run_root)
    markdown = inventory_tool.render_markdown(data)

    lifecycle = data["lifecycle"]
    artifact_state = lifecycle["campaign_execution_artifacts"]
    assert lifecycle["current_run_evidence"] is False
    assert lifecycle["campaign_execution_artifacts_available"] is False
    assert lifecycle["campaign_execution_artifacts_unavailable"] is True
    assert lifecycle["campaign_execution_failure_key"] == (
        "campaign_execution_artifacts_stale_resume_snapshot"
    )
    assert artifact_state["campaign_run_status"]["valid"] is True
    assert artifact_state["campaign_run_status"]["fresh"] is False
    assert data["validity"] == {
        "run_validity_status": "invalid_infra_only",
        "run_completeness_status": "incomplete",
        "last_stop_reason": "campaign_execution_artifacts_stale_resume_snapshot",
        "invalid_infra_only": True,
    }
    assert data["counters"] == {
        "requested_rounds": 4,
        "effective_rounds_completed": 0,
        "formal_screened_candidates": 0,
        "protocol_evaluated_candidates": 0,
        "screened_experiments": 0,
        "proposal_attempts_total": 0,
    }
    assert data["resume_snapshot"]["present"] is True
    assert data["resume_snapshot"]["current_run_evidence"] is False
    assert data["phase4_evidence_coverage"]["current_run_evidence"] is False
    assert "CAMPAIGN EXECUTION ARTIFACTS UNAVAILABLE" in markdown
    assert "resume snapshots" in markdown


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
            "pre_campaign_completion_preflight_classification": ("not_authenticated"),
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
            "resume_snapshot_ref": "resume_snapshot/resume_source_manifest.v1.json",
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
        run_root / "resume_snapshot" / "resume_source_manifest.v1.json",
        {
            "schema_version": "scion.resume_source_manifest.v1",
            "terminal_artifacts": [
                {
                    "original_ref": "campaign_summary.json",
                    "snapshot_ref": "resume_snapshot/campaign/campaign_summary.json",
                }
            ],
        },
    )
    _write_json(
        run_root / "resume_snapshot" / "campaign" / "campaign_summary.json",
        {
            "formal_screened_candidates": 7,
            "measurement_readiness": {"status": "ready"},
            "branch_cards": [
                {
                    "branch_id": "branch-1",
                    "branch_state": "explore_expand",
                    "lineage_id": "lineage-1",
                    "mechanism_ids": ["bounded_resume_probe"],
                    "branch_next_action": "refine_checkpoint",
                    "branch_scheduling_lane": "weak_positive_followup",
                    "followup_recommended": True,
                    "followup_required": False,
                    "branch_card_text": (
                        "branch_id=branch-1 status=explore_expand "
                        "mechanism_ids=bounded_resume_probe "
                        "followup_recommended=true "
                        "allowed_next_actions=refine_checkpoint"
                    ),
                }
            ],
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
    assert data["resume_snapshot"]["branches"][0]["branch_id"] == "branch-1"
    assert data["resume_snapshot"]["branches"][0]["state"] == "explore_expand"
    assert data["resume_snapshot"]["branches"][0]["mechanism_ids"] == [
        "bounded_resume_probe"
    ]
    assert data["resume_snapshot"]["branches"][0]["next_action"] == (
        "refine_checkpoint"
    )
    assert data["resume_snapshot"]["branches"][0]["followup_recommended"] is True
    assert (
        data["launcher"]["artifacts"]["pre_campaign_completion_preflight.v1.json"]
        is True
    )
    assert (
        data["launcher"]["status_fields"][
            "pre_campaign_completion_preflight_classification"
        ]
        == "not_authenticated"
    )
    assert (
        data["launcher"]["status_fields"][
            "pre_campaign_completion_preflight_login_url_present"
        ]
        is True
    )
    assert (
        "Refresh the local proxy login"
        in data["launcher"]["status_fields"][
            "pre_campaign_completion_preflight_operator_action"
        ]
    )
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
    assert "PRE-CAMPAIGN PREFLIGHT FAILED" in markdown
    assert "## Resume Snapshot" in markdown
    assert "### Resume Snapshot Branches" in markdown
    assert "bounded_resume_probe" in markdown
    assert "not current-run evidence" in markdown


def test_inventory_marks_runtime_guard_failure_resume_snapshot_not_current_run(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "runtime-guard-failed-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 64,
            "git_runtime_commit_mismatch": True,
            "resume_from_campaign": "/tmp/source-campaign",
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
            "measurement_readiness": {"status": "ready"},
        },
    )
    traces_dir = campaign_dir / "llm_traces"
    traces_dir.mkdir()
    _write_json(
        traces_dir / "20260606T000000_hypothesis_branch_1.json",
        {"request_kind": "hypothesis", "ok": True, "branch_id": "branch-1"},
    )
    _write_db(campaign_dir / "scion.db")

    data = inventory_tool.build_inventory(run_root)
    markdown = inventory_tool.render_markdown(data)

    assert data["lifecycle"]["pre_campaign_infra_failed"] is True
    assert data["lifecycle"]["pre_campaign_infra_failure_keys"] == [
        "git_runtime_commit_mismatch"
    ]
    assert data["lifecycle"]["current_run_evidence"] is False
    assert data["lifecycle"]["evidence_scope"] == (
        "pre_campaign_infra_failed_with_resume_snapshot"
    )
    assert data["validity"] == {
        "run_validity_status": "invalid_infra_only",
        "run_completeness_status": "incomplete",
        "last_stop_reason": "pre_campaign_git_runtime_commit_mismatch",
        "invalid_infra_only": True,
    }
    assert data["counters"] == {
        "requested_rounds": 3,
        "effective_rounds_completed": 0,
        "formal_screened_candidates": 0,
        "protocol_evaluated_candidates": 0,
        "screened_experiments": 0,
        "proposal_attempts_total": 0,
    }
    assert data["branches"] == []
    assert data["llm_traces"]["trace_count"] == 0
    assert data["resume_snapshot"]["present"] is True
    assert data["resume_snapshot"]["current_run_evidence"] is False
    assert data["resume_snapshot"]["branch_count"] == 1
    assert data["resume_snapshot"]["llm_trace_count"] == 1
    phase4 = data["phase4_evidence_coverage"]
    assert phase4["current_run_evidence"] is False
    assert phase4["pre_campaign_infra_failed"] is True
    assert phase4["pre_campaign_infra_failure_keys"] == ["git_runtime_commit_mismatch"]
    assert "PRE-CAMPAIGN INFRA FAILURE" in markdown
    assert "not current-run evidence" in markdown


def test_inventory_marks_scion_dir_failure_resume_snapshot_not_current_run(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "scion-dir-failed-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 64,
            "scion_dir_missing": "/tmp/missing-scion",
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "execution": {"rounds": 2},
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "effective_rounds_completed": 5,
            "formal_screened_candidates": 5,
        },
    )
    _write_db(campaign_dir / "scion.db")

    data = inventory_tool.build_inventory(run_root)
    markdown = inventory_tool.render_markdown(data)

    assert data["lifecycle"]["pre_campaign_infra_failed"] is True
    assert data["lifecycle"]["pre_campaign_infra_failure_keys"] == ["scion_dir_missing"]
    assert data["lifecycle"]["current_run_evidence"] is False
    assert data["validity"] == {
        "run_validity_status": "invalid_infra_only",
        "run_completeness_status": "incomplete",
        "last_stop_reason": "pre_campaign_scion_dir_missing",
        "invalid_infra_only": True,
    }
    assert data["counters"]["effective_rounds_completed"] == 0
    assert data["resume_snapshot"]["present"] is True
    assert data["resume_snapshot"]["current_run_evidence"] is False
    assert "PRE-CAMPAIGN INFRA FAILURE" in markdown
    assert "scion_dir_missing" in markdown


def test_inventory_marks_launch_env_failure_resume_snapshot_not_current_run(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "launch-env-failed-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 64,
            "launch_env_missing": str(run_root / "launch.env"),
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "execution": {"rounds": 2},
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "effective_rounds_completed": 5,
            "formal_screened_candidates": 5,
        },
    )
    _write_db(campaign_dir / "scion.db")

    data = inventory_tool.build_inventory(run_root)
    markdown = inventory_tool.render_markdown(data)

    assert data["lifecycle"]["pre_campaign_infra_failed"] is True
    assert data["lifecycle"]["pre_campaign_infra_failure_keys"] == [
        "launch_env_missing"
    ]
    assert data["lifecycle"]["current_run_evidence"] is False
    assert data["validity"] == {
        "run_validity_status": "invalid_infra_only",
        "run_completeness_status": "incomplete",
        "last_stop_reason": "pre_campaign_launch_env_missing",
        "invalid_infra_only": True,
    }
    assert data["counters"]["effective_rounds_completed"] == 0
    assert data["resume_snapshot"]["present"] is True
    assert data["resume_snapshot"]["current_run_evidence"] is False
    assert "PRE-CAMPAIGN INFRA FAILURE" in markdown
    assert "launch_env_missing" in markdown


def test_inventory_marks_invalid_infra_resume_snapshot_not_current_run(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "infra-failed-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 20,
            "run_validity_status": "invalid_infra_only",
            "run_completeness_status": "incomplete",
            "last_stop_reason": "provider_infra_balance_exhausted",
            "invalid_infra_only": True,
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "execution": {"rounds": 4},
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 6,
            "protocol_evaluated_candidates": 6,
            "measurement_readiness": {"status": "ready"},
        },
    )
    traces_dir = campaign_dir / "llm_traces"
    traces_dir.mkdir()
    _write_json(
        traces_dir / "20260606T000000_code_branch_1.json",
        {"request_kind": "code", "ok": True, "branch_id": "branch-1"},
    )
    _write_db(campaign_dir / "scion.db")

    data = inventory_tool.build_inventory(run_root)
    markdown = inventory_tool.render_markdown(data)

    assert data["lifecycle"]["invalid_infra_only"] is True
    assert data["lifecycle"]["current_run_evidence"] is False
    assert data["lifecycle"]["evidence_scope"] == (
        "invalid_infra_only_with_resume_snapshot"
    )
    assert data["validity"]["invalid_infra_only"] is True
    assert data["counters"]["effective_rounds_completed"] == 0
    assert data["branches"] == []
    assert data["llm_traces"]["trace_count"] == 0
    assert data["resume_snapshot"]["present"] is True
    assert data["resume_snapshot"]["current_run_evidence"] is False
    assert data["resume_snapshot"]["branch_count"] == 1
    assert data["resume_snapshot"]["llm_trace_count"] == 1
    assert data["resume_snapshot"]["hypothesis_count"] == 2
    phase4 = data["phase4_evidence_coverage"]
    assert phase4["current_run_evidence"] is False
    assert phase4["invalid_infra_only"] is True
    assert phase4["requirements"]["formal_candidate_artifact"]["available"] is False
    assert "INVALID INFRA-ONLY RUN" in markdown
    assert "## Resume Snapshot" in markdown


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


def _write_minimal_campaign_execution_docs(run_root: Path) -> None:
    campaign_dir = run_root / "campaign"
    _write_json(
        campaign_dir / "status.json",
        {
            "effective_rounds_completed": 1,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "effective_rounds_completed": 1,
        },
    )


def _git_head_short() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()


def _direct_attempt_payload(*, phase: str, status: str) -> dict[str, object]:
    prompt_ref = f"artifacts/llm_traces/direct-{phase}.json"
    failed = status == "failed"
    started = status == "started"
    payload: dict[str, object] = {
        "schema_version": "proposal-attempt-transition.v1",
        "attempt_id": f"attempt-direct-{phase}",
        "campaign_id": "campaign-direct",
        "branch_id": "branch-direct",
        "runtime_mode": "direct_v3",
        "attempt_kind": (
            "approved_code_continuation" if phase == "code" else "initial"
        ),
        "phase": phase,
        "status": status,
        "transition_reason": (
            "provider_call_started"
            if started
            else "response_parse_failed" if failed else "generated"
        ),
        "failure_lane": "proposal_repair" if failed else None,
        "hypothesis_id": (
            None if started and phase == "hypothesis" else "hypothesis-direct"
        ),
        "hypothesis_digest": (
            None if started and phase == "hypothesis" else "hypothesis-digest"
        ),
        "patch_digest": None,
        "prompt_call": {
            "request_kind": phase,
            "context_digest": f"context-digest-{phase}",
            "prompt_hash": f"prompt-hash-{phase}",
            "trace_ref": None if started else prompt_ref,
            "prompt_manifest_ref": (
                None if started else f"{prompt_ref}#/prompt_manifest"
            ),
            "raw_response_ref": None if started else f"{prompt_ref}#/response",
            "provider_ok": None if started else not failed,
            "ok": None if started else not failed,
            "error_category": (
                "response_parse_failed" if failed else None
            ),
            "error_type": "ProposalValidationError" if failed else None,
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
        "tainted_artifact_refs": [] if started else [prompt_ref],
    }
    if phase == "code":
        payload["continuation_of_attempt_id"] = "attempt-direct-hypothesis"
    return payload


def _write_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("""
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
            """)
        conn.execute("""
            CREATE TABLE hypotheses (
                hypothesis_id TEXT PRIMARY KEY,
                branch_id TEXT,
                change_locus TEXT,
                action TEXT,
                status TEXT
            )
            """)
        conn.execute("""
            CREATE TABLE experiment_events (
                event_id TEXT PRIMARY KEY,
                branch_id TEXT,
                event_kind TEXT,
                decision TEXT,
                stage TEXT
            )
            """)
        conn.execute("""
            CREATE TABLE champions (
                version INTEGER NOT NULL,
                weight_revision INTEGER NOT NULL DEFAULT 0,
                operator_pool_json TEXT NOT NULL,
                solver_config_hash TEXT NOT NULL,
                code_snapshot_path TEXT NOT NULL,
                code_snapshot_hash TEXT NOT NULL,
                promotion_experiment_id TEXT,
                promotion_dossier_ref TEXT,
                promoted_at TEXT,
                PRIMARY KEY (version, weight_revision)
            )
            """)
        conn.execute("""
            INSERT INTO branches VALUES (
                'branch-1', 'ready_validate', 'lineage-1', 'basehash',
                'codehash', 'checkpoint-best', 'checkpoint-last', 1,
                '["CONTRACT"]'
            )
            """)
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
        conn.executemany(
            """
            INSERT INTO champions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    0,
                    "{}",
                    "solver-hash-1",
                    "snapshots/champion-v1",
                    "code-hash-1",
                    None,
                    None,
                    None,
                ),
                (
                    2,
                    0,
                    "{}",
                    "solver-hash-2",
                    "snapshots/champion-v2",
                    "code-hash-2",
                    "exp-promote-2",
                    "dossier-2",
                    "2026-06-19T00:00:00Z",
                ),
            ],
        )
