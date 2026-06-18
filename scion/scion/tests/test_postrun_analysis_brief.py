from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


TOOL_PATH = Path(__file__).parents[2] / "tools" / "postrun_analysis_brief.py"
SPEC = importlib.util.spec_from_file_location("postrun_analysis_brief", TOOL_PATH)
assert SPEC is not None
brief_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(brief_tool)


def test_brief_json_and_markdown_from_inventory_inputs(tmp_path: Path) -> None:
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
            "requested_rounds": 1,
        },
    )
    (run_root / "run.log").write_text("POSTRUN_REPORT_DIR:/tmp/run\n", encoding="utf-8")
    (run_root / "exit.txt").write_text("WRAPPER_EXIT_STATUS:0\n", encoding="utf-8")
    (run_root / "command.txt").write_text("./run.sh\n", encoding="utf-8")
    (run_root / "launch.env").write_text("SCION_MODEL=gpt-5.5\n", encoding="utf-8")
    (run_root / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    _write_json(
        campaign_dir / "status.json",
        {"effective_rounds_completed": 1, "screened_experiments": 1},
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
            "sessions": [
                {
                    "session_id": "s-1",
                    "branch_id": "branch-1",
                    "traces": [
                        {"trace_id": "t-hyp", "request_kind": "hypothesis"},
                        {"trace_id": "t-code", "request_kind": "code"},
                        {
                            "trace_id": "t-target",
                            "request_kind": "target_intent",
                            "prompt_manifest_ref": "manifest-1",
                        },
                    ],
                }
            ]
        },
    )
    _write_json(
        sessions_dir / "agentic_session_index.json",
        {"sessions": [{"session_id": "s-1", "branch_id": "branch-1"}]},
    )
    _write_json(
        traces_dir / "20260618T000000_target_intent_branch_1.json",
        {
            "request_kind": "target_intent",
            "ok": True,
            "branch_id": "branch-1",
            "prompt_manifest_ref": "manifest-1",
        },
    )
    _write_json(
        traces_dir / "20260618T000001_hypothesis_branch_1.json",
        {"request_kind": "hypothesis", "ok": True, "branch_id": "branch-1"},
    )
    _write_json(
        traces_dir / "20260618T000002_code_branch_1.json",
        {"request_kind": "code", "ok": True, "branch_id": "branch-1"},
    )
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    formal_index.write_text('{"candidate_id":"cand-1"}\n', encoding="utf-8")
    _write_json(
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "normal.research_efficiency.v1.json",
        {
            "measurement_readiness": {"status": "ready"},
            "protocol_effects_vs_mde": {"mde_source": "readiness"},
            "fresh_runtime_replay_drain": {"attempts": 1},
        },
    )
    _write_json(
        run_root
        / "postrun_acceptance"
        / "manifests"
        / "normal.proposal_trajectory_manifest.v1.json",
        {
            "counts": {"prompt_manifest_loaded_count": 1},
            "branch_lesson_usage_accounting": {
                "field_counts": {"avoided_lessons": 1}
            },
            "sessions": [
                {
                    "trace_fingerprints": [
                        {"visibility_ledger_digest": "visibility-ledger-1"}
                    ]
                }
            ],
        },
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    assert brief["schema_version"] == "scion.postrun_analysis_brief.v1"
    assert brief["report_only"] is True
    assert brief["quality_judgment"] is False
    assert brief["decision_features_excluded"] is True
    assert brief["campaign_state_mutated"] is False
    assert brief["scheduler_state_mutated"] is False
    assert brief["promotion_state_mutated"] is False
    assert brief["branches"]["ids"] == ["branch-1"]
    assert brief["phase4_evidence_coverage"]["requirements"]["target_intent_trace"][
        "available"
    ] is True
    checklist = {item["name"]: item["present"] for item in brief["artifact_checklist"]}
    assert checklist["outer_command"] is True
    assert checklist["campaign_database"] is False
    assert checklist["prepared_run_manifest_json"] is False
    assert brief["prepared_run_contract"]["schema_version"] == (
        "scion.prepared_run_contract_inventory.v1"
    )
    assert brief["prepared_run_contract"]["report_only"] is True
    assert brief["prepared_run_contract"]["quality_judgment"] is False
    assert brief["prepared_run_contract"]["decision_features_excluded"] is True
    assert brief["prepared_run_contract"]["contract_complete"] is False
    assert brief["prepared_run_contract"]["acceptance_focus"] == []
    assert "## Minimum Delegated Analysis" in markdown
    assert "## Prepared Run Contract" in markdown
    assert "Acceptance focus" in markdown
    assert "DecisionFeatures" in markdown
    assert "| target_intent_trace | True | 1 | llm_traces or trace_index |" in markdown

    result = subprocess.run(
        [sys.executable, str(TOOL_PATH), str(run_root), "--format", "json"],
        text=True,
        capture_output=True,
        check=True,
    )
    cli_brief = json.loads(result.stdout)
    assert cli_brief["schema_version"] == "scion.postrun_analysis_brief.v1"


def test_brief_stop_conditions_for_invalid_infra_run(tmp_path: Path) -> None:
    run_root = tmp_path / "infra-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_validity_status": "invalid_infra_only",
            "invalid_infra_only": True,
            "requested_rounds": 1,
        },
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    assert any("INVALID INFRA-ONLY RUN" in item for item in brief["stop_conditions"])
    assert any("No effective rounds" in item for item in brief["stop_conditions"])
    assert "INVALID INFRA-ONLY RUN" in markdown
    assert "do not analyze as research behavior" in markdown


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
