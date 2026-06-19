from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCION_DIR = Path(__file__).resolve().parents[2]
TOOL_PATH = SCION_DIR / "tools" / "check_launch_readiness.py"
SPEC = importlib.util.spec_from_file_location("check_launch_readiness", TOOL_PATH)
assert SPEC is not None
readiness_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(readiness_tool)


def test_launch_readiness_accepts_clean_prepared_root(tmp_path: Path) -> None:
    run_root = _write_prepared_root(tmp_path)

    report = readiness_tool.build_readiness(run_root)

    assert report["schema_version"] == "scion.launch_readiness.v1"
    assert report["report_only"] is True
    assert report["decision_features_excluded"] is True
    assert report["ready"] is True
    assert report["static_ready"] is True
    assert report["launch_ready"] is False
    assert report["checks"]["prepared_only_not_started"]["status"] == "ok"
    assert report["checks"]["prepared_contract_complete"]["status"] == "ok"
    assert report["checks"]["git_runtime_consistent"]["status"] == "ok"
    problem_specific = report["checks"]["problem_specific_prepared_handoff"]
    assert problem_specific["status"] == "ok"
    assert problem_specific["required"] is True
    assert (
        problem_specific["detail"]["checks"][
            "cvrp_large_twoopt_bounded_constraints_present"
        ]["passed"]
        is True
    )
    assert report["checks"]["prompt_context_readiness_complete"]["status"] == "ok"
    assert report["checks"]["prepared_analysis_brief_current"]["status"] == "ok"
    assert report["checks"]["run_script_preflight_failure_reports"]["status"] == "ok"
    assert report["checks"]["completion_preflight"]["status"] == "skipped"
    markdown = readiness_tool.render_markdown(report)
    assert markdown.startswith("# Launch Readiness:")
    assert "Launch only after rerunning this tool" in markdown


def test_launch_readiness_rejects_already_started_root(tmp_path: Path) -> None:
    run_root = _write_prepared_root(tmp_path)
    (run_root / "exit.txt").write_text("WRAPPER_EXIT_STATUS:64\n", encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["launch_ready"] is False
    assert report["checks"]["not_already_started"]["status"] == "failed"


def test_launch_readiness_rejects_preflight_failed_root(tmp_path: Path) -> None:
    run_root = _write_prepared_root(tmp_path)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 64,
            "pre_campaign_completion_preflight": "failed",
        },
    )
    (run_root / "postrun_acceptance" / "rebuild").mkdir(parents=True)

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["launch_ready"] is False
    assert report["checks"]["prepared_only_not_started"]["status"] == "failed"
    assert report["checks"]["zero_current_run_counters"]["status"] == "ok"
    assert report["checks"]["postrun_acceptance_not_present"]["status"] == "failed"


def test_launch_readiness_rejects_missing_cvrp_measurement_handoff(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path, include_research_focus=False)

    report = readiness_tool.build_readiness(run_root)
    inventory = readiness_tool.build_inventory(run_root)
    contract = inventory["launcher"]["prepared_run_contract"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["checks"]["prepared_contract_complete"]["status"] == "failed"
    problem_specific = report["checks"]["problem_specific_prepared_handoff"]
    assert problem_specific["status"] == "failed"
    assert "cvrp_measurement_handoff_present" in problem_specific["detail"][
        "failed_checks"
    ]
    assert "cvrp_large_twoopt_bounded_constraints_present" in problem_specific[
        "detail"
    ]["failed_checks"]
    assert contract["contract_complete"] is False
    assert contract["checks"]["cvrp_measurement_handoff_present"]["passed"] is False


def test_launch_readiness_problem_specific_helper_reports_warehouse_failures() -> None:
    status, detail, required = (
        readiness_tool._problem_specific_prepared_handoff_check(
            {
                "problem_family": "warehouse_delivery",
                "checks": {
                    "warehouse_followup_handoff_present": {
                        "passed": True,
                        "detail": "research_focus",
                    },
                    "warehouse_followup_v2_checkpoint_present": {
                        "passed": False,
                        "detail": {"missing": ["v2"]},
                    },
                    "git_runtime_consistent": {
                        "passed": True,
                        "detail": "not problem-specific",
                    },
                },
            }
        )
    )

    assert status == "failed"
    assert required is True
    assert detail["problem_family"] == "warehouse_delivery"
    assert detail["failed_checks"] == ["warehouse_followup_v2_checkpoint_present"]
    assert "git_runtime_consistent" not in detail["checks"]


def test_launch_readiness_problem_specific_helper_skips_generic_problem() -> None:
    status, detail, required = (
        readiness_tool._problem_specific_prepared_handoff_check(
            {
                "problem_family": "generic_problem",
                "checks": {},
            }
        )
    )

    assert status == "skipped"
    assert required is False
    assert detail["reason"] == "no_problem_specific_prepared_handoff_requirements"


def test_launch_readiness_rejects_missing_prompt_context_readiness(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path, include_prompt_context_readiness=False)

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert prompt_check["detail"]["failures"][0]["reason"] == (
        "missing_prompt_context_readiness"
    )


def test_launch_readiness_rejects_missing_prepared_analysis_brief(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path, include_analysis_brief=False)

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    brief_check = report["checks"]["prepared_analysis_brief_current"]
    assert brief_check["status"] == "failed"
    assert brief_check["detail"]["failures"][0]["reason"] == (
        "missing_prepared_analysis_brief"
    )


def test_launch_readiness_rejects_stale_prepared_analysis_brief_questions(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    brief_path = (
        run_root
        / "prepared_handoff"
        / "analysis_brief"
        / "cvrp_on_full.prepared_analysis_brief.v1.json"
    )
    payload = json.loads(brief_path.read_text(encoding="utf-8"))
    payload["required_questions"] = [
        "Did the agent perform effective research, or only satisfy framework controls?"
    ]
    payload["cvrp_large_twoopt_summary"].pop("deferred_review_axes")
    brief_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    brief_check = report["checks"]["prepared_analysis_brief_current"]
    assert brief_check["status"] == "failed"
    reasons = {
        failure["reason"]
        for failure in brief_check["detail"]["failures"]
    }
    assert "prepared_only_required_question_missing" in reasons
    assert "current_run_required_question_present" in reasons
    assert "problem_summary_deferred_review_axes_missing" in reasons


def test_launch_readiness_rejects_prepared_analysis_brief_contract_mismatch(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    brief_path = (
        run_root
        / "prepared_handoff"
        / "analysis_brief"
        / "cvrp_on_full.prepared_analysis_brief.v1.json"
    )
    payload = json.loads(brief_path.read_text(encoding="utf-8"))
    payload["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    payload["prepared_run_contract"]["git"]["commit"] = "stale123"
    brief_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    brief_check = report["checks"]["prepared_analysis_brief_current"]
    assert brief_check["status"] == "failed"
    mismatches = [
        failure
        for failure in brief_check["detail"]["failures"]
        if failure["reason"] == "prepared_run_contract_identity_mismatch"
    ]
    assert {item["field"] for item in mismatches} == {
        "git.commit",
        "problem_family",
    }


def test_launch_readiness_rejects_prompt_context_bridge_marker_gap(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(
        tmp_path,
        prompt_context_launch_markers=False,
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    reasons = {
        failure["reason"]
        for failure in prompt_check["detail"]["failures"]
    }
    assert "prepared_focus_bridge_launch_markers_missing" in reasons


def test_launch_readiness_rejects_stale_prompt_context_live_marker_gap(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    (run_root / "launch.env").unlink()

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == "live_prompt_bridge_markers_missing"
        and "launch_markers.launch_env_assignment" in failure["missing"]
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_prompt_context_artifact_identity_mismatch(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    artifact_path = (
        run_root
        / "prepared_handoff"
        / "prompt_context_readiness"
        / "cvrp_on_full.prepared_prompt_context_readiness.v1.json"
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["prepared_manifest_path"] = str(run_root / "other_manifest.json")
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == "artifact_identity_mismatch"
        and failure["field"] == "prepared_manifest_path"
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_keeps_static_ready_when_completion_preflight_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_root = _write_prepared_root(tmp_path)

    def fail_preflight(**_: object) -> tuple[str, object]:
        return "failed", {"chat": {"classification": "not_authenticated"}}

    monkeypatch.setattr(
        readiness_tool,
        "_completion_preflight_check",
        fail_preflight,
    )

    report = readiness_tool.build_readiness(run_root, completion_preflight=True)

    assert report["ready"] is False
    assert report["static_ready"] is True
    assert report["launch_ready"] is False
    assert report["checks"]["completion_preflight"]["status"] == "failed"


def test_launch_readiness_accepts_helper_preflight_failure_report_path(
    tmp_path: Path,
) -> None:
    run_sh = tmp_path / "run.sh"
    run_sh.write_text(
        """#!/usr/bin/env bash
write_postrun_acceptance_reports() {
  return 0
}
if [[ "${COMPLETION_PREFLIGHT:-0}" == "1" ]]; then
  "$PY" "$SCION_DIR/tools/write_completion_preflight_status.py" \
    --output "$RUN_ROOT/run_status.json" \
    --exit-code "$PREFLIGHT_STATUS" \
    --detail "$PREFLIGHT_DETAIL"
  write_postrun_acceptance_reports
  exit "$PREFLIGHT_STATUS"
fi
""",
        encoding="utf-8",
    )

    assert readiness_tool._run_sh_contains_preflight_failure_report_path(run_sh)


def test_completion_preflight_fetches_login_url_and_operator_action(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    captured: dict[str, object] = {}

    class Result:
        returncode = 64
        stdout = json.dumps(
            {
                "ok": False,
                "chat": {
                    "http_status": 401,
                    "classification": "auth_token_invalidated",
                    "message": "token has been invalidated",
                },
                "login_url": "http://127.0.0.1:8080/auth/login",
            }
        )
        stderr = ""

    def fake_run(command: list[str], **_: object) -> Result:
        captured["command"] = command
        return Result()

    monkeypatch.setattr(readiness_tool.subprocess, "run", fake_run)

    status, detail = readiness_tool._completion_preflight_check(
        prepared_contract={
            "manifest_path": str(run_root / "prepared_run_manifest.v1.json")
        },
        api_key=None,
        api_key_env=None,
        timeout_sec=20,
    )

    assert status == "failed"
    assert "--login-url-on-failure" in captured["command"]
    assert isinstance(detail, dict)
    assert detail["login_url"] == "http://127.0.0.1:8080/auth/login"
    assert detail["operator_action"]["classification"] == "auth_token_invalidated"
    assert detail["operator_action"]["login_url"] == (
        "http://127.0.0.1:8080/auth/login"
    )
    assert "launch_ready=true" in detail["operator_action"]["next_step"]


def test_launch_readiness_markdown_renders_completion_action(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_root = _write_prepared_root(tmp_path)

    def fail_preflight(**_: object) -> tuple[str, object]:
        return "failed", {
            "chat": {"classification": "not_authenticated"},
            "operator_action": {
                "classification": "not_authenticated",
                "next_step": "Refresh the local proxy login.",
                "login_url": "http://127.0.0.1:8080/auth/login",
                "rerun_command": (
                    "python scion/tools/check_launch_readiness.py <run_root> "
                    "--require-launch-ready --format json"
                ),
            },
        }

    monkeypatch.setattr(
        readiness_tool,
        "_completion_preflight_check",
        fail_preflight,
    )

    report = readiness_tool.build_readiness(run_root, completion_preflight=True)
    markdown = readiness_tool.render_markdown(report)

    assert "## Completion Preflight Action" in markdown
    assert "Classification: `not_authenticated`" in markdown
    assert "http://127.0.0.1:8080/auth/login" in markdown
    assert "--require-launch-ready --format json" in markdown


def test_launch_readiness_cli_json_returns_unready_exit(tmp_path: Path) -> None:
    run_root = _write_prepared_root(tmp_path)
    (run_root / "exit.txt").write_text("WRAPPER_EXIT_STATUS:64\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(TOOL_PATH), str(run_root), "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 64
    assert payload["ready"] is False
    assert payload["checks"]["not_already_started"]["status"] == "failed"


def test_launch_readiness_cli_require_launch_ready_implies_completion_preflight(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_root = _write_prepared_root(tmp_path)

    def fail_preflight(**_: object) -> tuple[str, object]:
        return "failed", {"chat": {"classification": "not_authenticated"}}

    monkeypatch.setattr(
        readiness_tool,
        "_completion_preflight_check",
        fail_preflight,
    )

    exit_code = readiness_tool.main(
        [str(run_root), "--require-launch-ready", "--format", "json"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 64
    assert payload["completion_preflight_required"] is True
    assert payload["static_ready"] is True
    assert payload["launch_ready"] is False
    assert payload["ready"] is False
    assert payload["checks"]["completion_preflight"]["status"] == "failed"


def test_launch_readiness_cli_require_launch_ready_accepts_real_preflight_success(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_root = _write_prepared_root(tmp_path)

    def pass_preflight(**_: object) -> tuple[str, object]:
        return "ok", {"chat": {"classification": "", "http_status": 200}}

    monkeypatch.setattr(
        readiness_tool,
        "_completion_preflight_check",
        pass_preflight,
    )

    exit_code = readiness_tool.main(
        [str(run_root), "--require-launch-ready", "--format", "json"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["completion_preflight_required"] is True
    assert payload["static_ready"] is True
    assert payload["launch_ready"] is True
    assert payload["ready"] is True
    assert payload["checks"]["completion_preflight"]["status"] == "ok"


def _write_prepared_root(
    tmp_path: Path,
    *,
    include_research_focus: bool = True,
    include_prompt_context_readiness: bool = True,
    include_analysis_brief: bool = True,
    prompt_context_launch_markers: bool = True,
) -> Path:
    run_root = tmp_path / "prepared-root"
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
        run_root / "run_status.json",
        {
            "schema": "scion.launcher_prepare.v1",
            "status": "prepared",
            "prepared_only": True,
            "run_root": str(run_root),
            "campaign_dir": str(campaign_dir),
            "copied_campaign_status_present": True,
            "copied_campaign_summary_present": True,
        },
    )
    manifest = {
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
        "analysis_intent": "Prepared launch readiness fixture.",
        "acceptance_focus": ["Stay report-only."],
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
            "control_pair_key": "cvrp.ready:rep01",
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
    }
    if include_research_focus:
        manifest["research_focus"] = _cvrp_research_focus()
    _write_json(run_root / "prepared_run_manifest.v1.json", manifest)
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
    (run_root / "launch.env").write_text(
        f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}\n",
        encoding="utf-8",
    )
    (run_root / "run.sh").write_text(
        f"""#!/usr/bin/env bash
set -uo pipefail
RUN_ROOT={run_root}
PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}
export RUN_ROOT PREPARED_RUN_MANIFEST
write_postrun_acceptance_reports() {{
  return 0
}}
if [[ "${{COMPLETION_PREFLIGHT:-0}}" == "1" ]]; then
  PREFLIGHT_STATUS=64
  if [[ "$PREFLIGHT_STATUS" -ne 0 ]]; then
    printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":%s,"pre_campaign_completion_preflight":"failed"}}\\n' "$PREFLIGHT_STATUS" > "$RUN_ROOT/run_status.json"
    write_postrun_acceptance_reports
    exit "$PREFLIGHT_STATUS"
  fi
fi
{sys.executable} -m scion.cli.main run --problem {config_dir / 'problem.yaml'} --protocol {config_dir / 'protocol.yaml'} --split {config_dir / 'split.yaml'} --seeds {config_dir / 'seeds.yaml'} --campaign-dir {campaign_dir} --rounds 1 --agentic-proposal
""",
        encoding="utf-8",
    )
    if include_prompt_context_readiness:
        _write_prompt_context_readiness(
            run_root,
            ready=include_research_focus,
            launch_markers=prompt_context_launch_markers,
        )
    if include_analysis_brief:
        _write_prepared_analysis_brief(run_root)
    return run_root


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
            "large_instance_intra_route_two_opt_seed",
            "acceptance_or_adaptive_weighting",
        ],
        "default_avoid_directions": [
            "unchanged broad VNS removal",
            "pure ALNS/no-polish",
            "simple initial-VNS disablement",
            "unbounded large-instance two-opt fallback without deadline or wall-clock evidence",
            "raw cadence-2",
            "tested share70 cap/rescue variants",
            "route-merge absorption",
            "demand-slack regret insertion",
            "cross-route 2-opt reconnect",
            "cluster-biased worst removal",
            "route-limit seed diversification",
        ],
        "large_instance_two_opt_constraints": _large_twoopt_constraints(),
        "route_merge_exception_rule": (
            "Only continue route_merge_repair when the proposal names a causal "
            "path beyond tested variants and defines direct activation-to-objective-effect evidence."
        ),
        "construction_seed_rule": (
            "Require same-run seed baseline or same-mechanism accepted delta "
            "for construction seed objective-effect claims."
        ),
        "decision_boundary": (
            "This focus must not enter DecisionFeatures, Protocol gates, "
            "promotion input, or scheduler state."
        ),
    }


def _large_twoopt_constraints() -> dict[str, object]:
    return {
        "schema_version": "scion.cvrp_large_instance_two_opt_constraints.v1",
        "scope": "proposal_only_prepared_handoff",
        "seed_report": (
            "scion/docs/experiments/v0.4/"
            "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md"
        ),
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "implementation_constraints": [
            "derive a deadline from the solver time_limit and monotonic start time",
            "check wall-clock remaining time before each route and sweep",
            "do not call unbounded two_opt_intra above the vns_threshold",
        ],
        "required_pair_evidence": [
            "total_distance delta by case and seed",
            "feasibility before and after",
            "route count before and after",
            "wall-clock elapsed status",
        ],
        "default_reject_directions": [
            "unbounded two_opt_intra fallback",
            "activation claims without wall-clock evidence",
        ],
    }


def _write_prepared_analysis_brief(run_root: Path) -> None:
    manifest = json.loads(
        (run_root / "prepared_run_manifest.v1.json").read_text(encoding="utf-8")
    )
    _write_json(
        run_root
        / "prepared_handoff"
        / "analysis_brief"
        / "cvrp_on_full.prepared_analysis_brief.v1.json",
        {
            "schema_version": "scion.postrun_analysis_brief.v1",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "campaign_state_mutated": False,
            "scheduler_state_mutated": False,
            "promotion_state_mutated": False,
            "run_root": str(run_root),
            "lifecycle": {
                "prepared_only": True,
                "current_run_evidence": False,
                "status": "prepared",
            },
            "validity": {
                "run_validity_status": "prepared_only",
                "run_completeness_status": "not_started",
            },
            "prepared_run_contract": {
                "schema_version": "scion.prepared_run_contract_inventory.v1",
                "manifest_path": str(run_root / "prepared_run_manifest.v1.json"),
                "contract_complete": True,
                "problem_family": manifest["problem_family"],
                "model": manifest["model"]["name"],
                "control_pair_key": manifest["report_metadata"]["control_pair_key"],
                "resume_from_campaign": manifest["resume_from_campaign"],
                "git": {"commit": manifest["git"]["commit"]},
            },
            "required_questions": [
                (
                    "Is this still a prepared-only launch root with zero "
                    "current-run counters and no postrun acceptance evidence?"
                ),
                (
                    "Is the next step launch-readiness recheck or launch, not "
                    "a research-quality or plateau/two-opt conclusion?"
                ),
                (
                    "For CVRP large-twoopt follow-up, did "
                    "cvrp_large_twoopt_summary distinguish prepared-only, "
                    "incomplete handoff, missing review inputs, missing "
                    "two-opt mechanism signal, and review-ready evidence?"
                ),
            ],
            "cvrp_large_twoopt_summary": {
                "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
                "available": True,
                "current_run_evidence": False,
                "interpretation": "prepared_only_launch_required",
                "launch_required_before_twoopt_conclusion": True,
                "evidence_gaps": [
                    "launch_required_before_bounded_twoopt_conclusion"
                ],
                "deferred_review_axes": [
                    "confirm_deadline_or_remaining_time_guard_in_solver_code",
                    (
                        "confirm_no_unbounded_two_opt_intra_or_vns_fallback_"
                        "above_large_threshold"
                    ),
                ],
                "review_axes_actionability": (
                    "not_actionable_before_launch_current_run_evidence_required"
                ),
            },
            "warehouse_followup_summary": {
                "available": False,
                "current_run_evidence": False,
            },
        },
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_prompt_context_readiness(
    run_root: Path,
    *,
    ready: bool,
    launch_markers: bool,
) -> None:
    missing_required = [] if ready else ["prepared_research_focus"]
    launch_marker_payload = {
        "launch_env_assignment": launch_markers,
        "prepared_manifest_exists": True,
        "run_sh_exports_manifest": launch_markers,
    }
    _write_json(
        run_root
        / "prepared_handoff"
        / "prompt_context_readiness"
        / "cvrp_on_full.prepared_prompt_context_readiness.v1.json",
        {
            "schema_version": "scion.prepared_prompt_context_readiness.v1",
            "artifact_kind": "prepared_prompt_context_readiness",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "campaign_state_mutated": False,
            "scheduler_state_mutated": False,
            "promotion_state_mutated": False,
            "raw_provider_prompt_rendered": False,
            "run_root": str(run_root),
            "prepared_manifest_path": str(
                run_root / "prepared_run_manifest.v1.json"
            ),
            "prepared_manifest_commit": _git_head_short(),
            "problem_family": "cvrp",
            "model": "gpt-5.5",
            "readiness": {
                "ready_for_launch_prompt_audit": ready,
                "missing_required": missing_required,
                "status": "ready" if ready else "missing_required_sources",
            },
            "signals": {
                "prepared_research_focus_prompt_bridge": {
                    "available": ready and launch_markers,
                    "detail": {
                        "launch_markers": launch_marker_payload,
                        "source_markers": {
                            "context_payload": True,
                            "manifest_env_reader": True,
                            "prompt_renderer": True,
                        },
                    },
                    "required": True,
                    "runtime_generated_after_launch": False,
                    "source": "fixture",
                }
            },
        },
    )


def _git_head_short() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()
