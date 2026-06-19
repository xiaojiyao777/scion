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
    assert (
        report["checks"]["runtime_guard_paths_cover_launch_tools"]["status"] == "ok"
    )
    assert report["checks"]["run_script_runtime_guard_enforced"]["status"] == "ok"
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
    assert (
        report["checks"]["run_script_completion_preflight_enforced"]["status"] == "ok"
    )
    assert report["checks"]["run_script_pythonpath_enforced"]["status"] == "ok"
    assert report["checks"]["run_script_model_route_enforced"]["status"] == "ok"
    assert report["checks"]["run_script_no_early_stop_enforced"]["status"] == "ok"
    assert report["checks"]["run_script_strict_postrun_readiness"]["status"] == "ok"
    assert (
        report["checks"]["run_script_postrun_reports_after_campaign"]["status"] == "ok"
    )
    assert report["checks"]["run_script_data_root_failure_reports"]["status"] == "ok"
    assert report["checks"]["run_script_api_key_env_failure_reports"]["status"] == "ok"
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


def test_launch_readiness_rejects_runtime_guard_without_launch_tools(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(
        tmp_path,
        runtime_guard_paths="scion/scion :(exclude)scion/scion/tests",
    )

    report = readiness_tool.build_readiness(run_root)
    guard_check = report["checks"]["runtime_guard_paths_cover_launch_tools"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert guard_check["status"] == "failed"
    assert guard_check["detail"]["missing_required_paths"] == ["scion/tools"]


def test_launch_readiness_rejects_runtime_guard_without_postrun_core(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path, runtime_guard_paths="scion/tools")

    report = readiness_tool.build_readiness(run_root)
    guard_check = report["checks"]["runtime_guard_paths_cover_launch_tools"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert guard_check["status"] == "failed"
    assert guard_check["detail"]["missing_required_paths"] == [
        "scion/scion/cli",
        "scion/scion/core",
        "scion/scion/lineage",
    ]


def test_launch_readiness_rejects_runtime_guard_excluding_required_core(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(
        tmp_path,
        runtime_guard_paths=(
            "scion/scion :(exclude)scion/scion/core "
            "scion/tools scion/problems/cvrp vrp"
        ),
    )

    report = readiness_tool.build_readiness(run_root)
    guard_check = report["checks"]["runtime_guard_paths_cover_launch_tools"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert guard_check["status"] == "failed"
    assert guard_check["detail"]["missing_required_paths"] == ["scion/scion/core"]


def test_launch_readiness_rejects_cvrp_runtime_guard_without_problem_paths(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(
        tmp_path,
        runtime_guard_paths="scion/scion :(exclude)scion/scion/tests scion/tools",
    )

    report = readiness_tool.build_readiness(run_root)
    guard_check = report["checks"]["runtime_guard_paths_cover_problem_runtime"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert guard_check["status"] == "failed"
    assert guard_check["detail"]["missing_required_paths"] == [
        "scion/problems/cvrp",
        "vrp",
    ]


def test_launch_readiness_rejects_warehouse_runtime_guard_without_problem_paths(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(
        tmp_path,
        problem_family="warehouse_delivery",
        research_focus=_warehouse_research_focus(),
        runtime_guard_paths="scion/scion :(exclude)scion/scion/tests scion/tools",
    )

    report = readiness_tool.build_readiness(run_root)
    guard_check = report["checks"]["runtime_guard_paths_cover_problem_runtime"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert guard_check["status"] == "failed"
    assert guard_check["detail"]["missing_required_paths"] == [
        "scion/problems/warehouse_delivery",
        "surrogate",
    ]


def test_launch_readiness_rejects_run_script_without_runtime_guard(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            "GIT_RUNTIME_DIRTY",
            "GIT_RUNTIME_CLEAN",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    guard_check = report["checks"]["run_script_runtime_guard_enforced"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert guard_check["status"] == "failed"
    assert "dirty_failure_marker" in guard_check["detail"]["missing_markers"]


def test_launch_readiness_rejects_run_script_guard_after_campaign_command(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            "GIT_COMMIT_MISMATCH",
            "GIT_COMMIT_SKIP",
            1,
        )
        + '\necho "GIT_COMMIT_MISMATCH"\n',
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    guard_check = report["checks"]["run_script_runtime_guard_enforced"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert guard_check["status"] == "failed"
    assert guard_check["detail"]["markers_after_campaign_command"] == [
        "commit_mismatch_failure_marker"
    ]


def test_launch_readiness_ignores_comment_only_runtime_guard_marker(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    run_text = run_text.replace(
        'git -C "$REPO_ROOT" status --porcelain -- "${_GIT_RUNTIME_GUARD_PATHS[@]}"',
        'git -C "$REPO_ROOT" status --short -- "${_GIT_RUNTIME_GUARD_PATHS[@]}"',
    )
    run_text = run_text.replace(
        "unset _ACTUAL_GIT_COMMIT _GIT_RUNTIME_GUARD_PATHS",
        '# git -C "$REPO_ROOT" status --porcelain -- "${_GIT_RUNTIME_GUARD_PATHS[@]}"\n'
        "unset _ACTUAL_GIT_COMMIT _GIT_RUNTIME_GUARD_PATHS",
    )
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)
    guard_check = report["checks"]["run_script_runtime_guard_enforced"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert guard_check["status"] == "failed"
    assert "dirty_status_check" in guard_check["detail"]["missing_markers"]
    assert guard_check["detail"]["ignored_non_executable_marker_counts"][
        "dirty_status_check"
    ] == 1


def test_launch_readiness_rejects_echo_only_runtime_guard_command_marker(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    run_text = run_text.replace(
        'git -C "$REPO_ROOT" rev-parse --short HEAD',
        'git -C "$REPO_ROOT" rev-parse --verify HEAD',
    )
    run_text = run_text.replace(
        "unset _ACTUAL_GIT_COMMIT _GIT_RUNTIME_GUARD_PATHS",
        'echo \'git -C "$REPO_ROOT" rev-parse --short HEAD\'\n'
        "unset _ACTUAL_GIT_COMMIT _GIT_RUNTIME_GUARD_PATHS",
    )
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)
    guard_check = report["checks"]["run_script_runtime_guard_enforced"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert guard_check["status"] == "failed"
    assert "actual_commit_read" in guard_check["detail"]["missing_markers"]
    assert guard_check["detail"]["ignored_non_executable_marker_counts"][
        "actual_commit_read"
    ] == 1


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


def test_launch_readiness_rejects_missing_matching_prepared_problem_summary(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(
        tmp_path,
        problem_family="warehouse_delivery",
        research_focus=_warehouse_research_focus(),
    )
    brief_path = (
        run_root
        / "prepared_handoff"
        / "analysis_brief"
        / "warehouse_on_full.prepared_analysis_brief.v1.json"
    )
    payload = json.loads(brief_path.read_text(encoding="utf-8"))
    payload["warehouse_followup_summary"]["available"] = False
    payload["cvrp_large_twoopt_summary"] = _prepared_cvrp_summary()
    brief_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    brief_check = report["checks"]["prepared_analysis_brief_current"]
    assert brief_check["status"] == "failed"
    assert any(
        failure["reason"] == "problem_summary_missing_for_problem_family"
        and failure["problem_family"] == "warehouse_delivery"
        and failure["expected_summary"] == "warehouse_followup_summary"
        for failure in brief_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_prepared_problem_summary_boundary_gap(
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
    summary = payload["cvrp_large_twoopt_summary"]
    summary["schema_version"] = "stale.schema"
    summary["report_only"] = False
    summary["quality_judgment"] = True
    summary["decision_features_excluded"] = False
    brief_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    brief_check = report["checks"]["prepared_analysis_brief_current"]
    assert brief_check["status"] == "failed"
    failures = brief_check["detail"]["failures"]
    assert any(
        failure["reason"] == "problem_summary_schema_mismatch"
        and failure["summary"] == "cvrp_large_twoopt_summary"
        for failure in failures
    )
    boundary_failures = {
        failure["field"]
        for failure in failures
        if failure["reason"] == "problem_summary_boundary_flag_mismatch"
    }
    assert boundary_failures == {
        "report_only",
        "quality_judgment",
        "decision_features_excluded",
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


def test_launch_readiness_rejects_missing_cvrp_code_constraint_bridge(
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
    payload["signals"].pop("cvrp_active_subject_code_constraints_prompt_bridge")
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == (
            "cvrp_active_subject_code_constraints_bridge_missing"
        )
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_missing_warehouse_code_constraint_bridge(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(
        tmp_path,
        problem_family="warehouse_delivery",
        research_focus=_warehouse_research_focus(),
        include_code_constraint_bridge=False,
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert (
        report["checks"]["problem_specific_prepared_handoff"]["status"] == "ok"
    )
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == (
            "warehouse_active_subject_code_constraints_bridge_missing"
        )
        for failure in prompt_check["detail"]["failures"]
    )
    live_markers = prompt_check["detail"]["live_markers"][
        "warehouse_active_subject_code_constraint_source_markers"
    ]
    assert live_markers == {
        "bounded_scan_guard": True,
        "code_prompt_renderer": True,
        "context_key": True,
        "context_provider_payload": True,
        "diagnostics_contract": True,
        "lexicographic_guard": True,
        "provider_hook": True,
    }


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
  if [[ "$PREFLIGHT_STATUS" -ne 0 ]]; then
    "$PY" "$SCION_DIR/tools/write_completion_preflight_status.py" \
      --output "$RUN_ROOT/run_status.json" \
      --exit-code "$PREFLIGHT_STATUS" \
      --detail "$PREFLIGHT_DETAIL"
    write_postrun_acceptance_reports
    exit "$PREFLIGHT_STATUS"
  fi
fi
""",
        encoding="utf-8",
    )

    assert readiness_tool._run_sh_contains_preflight_failure_report_path(run_sh)
    status, detail = readiness_tool._run_script_preflight_failure_reports(run_sh)
    assert status == "ok"
    assert detail["preflight_status_writer_kind"] == "helper"
    assert detail["failures"] == []


def test_launch_readiness_rejects_comment_only_preflight_failure_report_path(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    run_text = run_text.replace(
        '"pre_campaign_completion_preflight":"failed"',
        '"pre_campaign_completion_preflight_disabled":"failed"',
    )
    run_text = run_text.replace(
        '    write_postrun_acceptance_reports\n',
        '    # "pre_campaign_completion_preflight":"failed"\n'
        '    write_postrun_acceptance_reports\n',
    )
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    preflight_failure_check = report["checks"]["run_script_preflight_failure_reports"]
    assert preflight_failure_check["required"] is True
    assert preflight_failure_check["status"] == "failed"
    assert {"reason": "preflight_failure_status_writer_missing"} in (
        preflight_failure_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_preflight_postrun_call_before_status_writer(
    tmp_path: Path,
) -> None:
    run_sh = tmp_path / "run.sh"
    run_sh.write_text(
        """#!/usr/bin/env bash
write_postrun_acceptance_reports() {
  return 0
}
if [[ "$PREFLIGHT_STATUS" -ne 0 ]]; then
  write_postrun_acceptance_reports
  "$PY" "$SCION_DIR/tools/write_completion_preflight_status.py" \
    --output "$RUN_ROOT/run_status.json" \
    --exit-code "$PREFLIGHT_STATUS" \
    --detail "$PREFLIGHT_DETAIL"
  exit "$PREFLIGHT_STATUS"
fi
""",
        encoding="utf-8",
    )

    status, detail = readiness_tool._run_script_preflight_failure_reports(run_sh)

    assert status == "failed"
    assert {"reason": "postrun_report_call_before_preflight_status_writer"} in detail[
        "failures"
    ]


def test_launch_readiness_rejects_comment_only_postrun_report_function(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    run_text = run_text.replace(
        "write_postrun_acceptance_reports() {",
        "# write_postrun_acceptance_reports() {\n"
        "write_postrun_acceptance_reports_disabled() {",
        1,
    )
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    strict_check = report["checks"]["run_script_strict_postrun_readiness"]
    preflight_failure_check = report["checks"]["run_script_preflight_failure_reports"]
    assert strict_check["status"] == "failed"
    assert {"reason": "missing_postrun_report_function"} in strict_check["detail"][
        "failures"
    ]
    assert strict_check["detail"][
        "ignored_non_executable_function_definition_count"
    ] == 1
    assert preflight_failure_check["status"] == "failed"
    assert {"reason": "missing_postrun_report_function"} in preflight_failure_check[
        "detail"
    ]["failures"]
    assert preflight_failure_check["detail"][
        "ignored_non_executable_function_definition_count"
    ] == 1


def test_launch_readiness_rejects_run_script_without_strict_postrun_readiness(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            "--require-current-run-ready",
            "",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    strict_check = report["checks"]["run_script_strict_postrun_readiness"]
    assert strict_check["required"] is True
    assert strict_check["status"] == "failed"
    assert {"reason": "postrun_acceptance_strict_flag_missing"} in strict_check[
        "detail"
    ]["failures"]


def test_launch_readiness_rejects_comment_only_strict_postrun_readiness(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    run_text = run_text.replace(
        "tools/check_postrun_acceptance.py",
        "tools/check_postrun_acceptance_disabled.py",
    )
    run_text = run_text.replace(
        "write_postrun_acceptance_reports() {\n",
        "write_postrun_acceptance_reports() {\n  # tools/check_postrun_acceptance.py --require-current-run-ready\n",
    )
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    strict_check = report["checks"]["run_script_strict_postrun_readiness"]
    assert strict_check["required"] is True
    assert strict_check["status"] == "failed"
    assert {"reason": "postrun_acceptance_command_missing"} in strict_check[
        "detail"
    ]["failures"]


def test_launch_readiness_rejects_prefixed_strict_postrun_readiness_flag(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            "--require-current-run-ready",
            "--require-current-run-readyish",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    strict_check = report["checks"]["run_script_strict_postrun_readiness"]
    assert strict_check["required"] is True
    assert strict_check["status"] == "failed"
    assert {"reason": "postrun_acceptance_strict_flag_missing"} in strict_check[
        "detail"
    ]["failures"]


def test_launch_readiness_rejects_run_script_without_postrun_call_after_campaign(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            'STATUS=$?\nwrite_postrun_acceptance_reports\nexit "$STATUS"',
            'STATUS=$?\nexit "$STATUS"',
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    postrun_check = report["checks"]["run_script_postrun_reports_after_campaign"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert postrun_check["required"] is True
    assert postrun_check["status"] == "failed"
    assert postrun_check["detail"]["failures"] == [
        {"reason": "missing_postrun_report_call_after_campaign"}
    ]


def test_launch_readiness_rejects_disabled_run_script_completion_preflight(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        launch_env.read_text(encoding="utf-8").replace(
            "COMPLETION_PREFLIGHT=1",
            "COMPLETION_PREFLIGHT=0",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    preflight_check = report["checks"]["run_script_completion_preflight_enforced"]
    assert preflight_check["status"] == "failed"
    assert preflight_check["detail"]["failures"] == [
        {
            "reason": "completion_preflight_not_enabled",
            "launch_env": str(launch_env),
            "actual": "0",
        }
    ]


def test_launch_readiness_rejects_comment_only_completion_preflight_proxy(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    run_text = run_text.replace(
        "tools/check_gpt55_proxy.py",
        "tools/check_gpt55_proxy_disabled.py",
    )
    run_text = run_text.replace(
        "  PREFLIGHT_STATUS=64\n",
        "  PREFLIGHT_STATUS=64\n  # tools/check_gpt55_proxy.py\n",
    )
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    preflight_check = report["checks"]["run_script_completion_preflight_enforced"]
    assert preflight_check["status"] == "failed"
    assert {"reason": "completion_preflight_proxy_call_missing"} in preflight_check[
        "detail"
    ]["failures"]


def test_launch_readiness_rejects_comment_only_launch_env_source(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    run_text = run_text.replace(
        'source "$RUN_ROOT/launch.env"',
        '# source "$RUN_ROOT/launch.env"\n'
        'echo \'source "$RUN_ROOT/launch.env"\'',
    )
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    preflight_check = report["checks"]["run_script_completion_preflight_enforced"]
    pythonpath_check = report["checks"]["run_script_pythonpath_enforced"]
    assert {"reason": "run_script_does_not_source_launch_env"} in preflight_check[
        "detail"
    ]["failures"]
    assert {"reason": "run_script_does_not_source_launch_env"} in pythonpath_check[
        "detail"
    ]["failures"]
    assert preflight_check["detail"]["launch_env_source_position"] == -1
    assert pythonpath_check["detail"]["launch_env_source_position"] == -1


def test_launch_readiness_rejects_missing_pythonpath(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        "\n".join(
            line
            for line in launch_env.read_text(encoding="utf-8").splitlines()
            if not line.startswith("PYTHONPATH=")
        )
        + "\n",
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    pythonpath_check = report["checks"]["run_script_pythonpath_enforced"]
    assert pythonpath_check["status"] == "failed"
    assert {
        "reason": "pythonpath_missing",
        "launch_env": str(launch_env),
    } in pythonpath_check["detail"]["failures"]


def test_launch_readiness_rejects_non_gpt55_model(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        launch_env.read_text(encoding="utf-8").replace(
            "SCION_MODEL=gpt-5.5",
            "SCION_MODEL=gpt-5.4",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    model_check = report["checks"]["run_script_model_route_enforced"]
    assert model_check["status"] == "failed"
    failures = model_check["detail"]["failures"]
    assert {
        "reason": "scion_model_not_gpt55",
        "launch_env": str(launch_env),
        "expected": "gpt-5.5",
        "actual": "gpt-5.4",
    } in failures
    assert {
        "reason": "scion_model_manifest_mismatch",
        "launch_env": str(launch_env),
        "manifest_model": "gpt-5.5",
        "env_model": "gpt-5.4",
    } in failures


def test_launch_readiness_rejects_prefixed_proxy_model_route_env_tokens(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8")
        .replace('--model "$SCION_MODEL"', '--model "$SCION_MODEL"extra')
        .replace('--base-url "$SCION_BASE_URL"', '--base-url "$SCION_BASE_URL"extra'),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    model_check = report["checks"]["run_script_model_route_enforced"]
    assert model_check["status"] == "failed"
    failures = model_check["detail"]["failures"]
    assert {"reason": "completion_preflight_model_env_missing"} in failures
    assert {"reason": "completion_preflight_base_url_env_missing"} in failures


def test_launch_readiness_rejects_disabled_early_stop(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        launch_env.read_text(encoding="utf-8").replace(
            "DISABLE_EARLY_STOP=1",
            "DISABLE_EARLY_STOP=0",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    early_stop_check = report["checks"]["run_script_no_early_stop_enforced"]
    assert early_stop_check["status"] == "failed"
    assert early_stop_check["detail"]["failures"] == [
        {
            "reason": "disable_early_stop_not_enabled",
            "launch_env": str(launch_env),
            "actual": "0",
        }
    ]


def test_launch_readiness_accepts_multiline_disable_early_stop_command(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    single_line = next(
        line
        for line in run_text.splitlines()
        if "-m scion.cli.main run --problem" in line
    )
    multiline = (
        single_line.replace(" --problem ", " \\\n  --problem ")
        .replace(" --protocol ", " \\\n  --protocol ")
        .replace(" --split ", " \\\n  --split ")
        .replace(" --seeds ", " \\\n  --seeds ")
        .replace(" --campaign-dir ", " \\\n  --campaign-dir ")
        .replace(" --rounds ", " \\\n  --rounds ")
        .replace(" --agentic-proposal ", " \\\n  --agentic-proposal ")
        .replace(" --disable-early-stop", " \\\n  --disable-early-stop")
    )
    run_sh.write_text(run_text.replace(single_line, multiline), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is True
    assert report["static_ready"] is True
    assert report["checks"]["run_script_no_early_stop_enforced"]["status"] == "ok"


def test_launch_readiness_rejects_run_script_without_disable_early_stop(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            " --disable-early-stop\nSTATUS=$?",
            "\nSTATUS=$?",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    early_stop_check = report["checks"]["run_script_no_early_stop_enforced"]
    assert early_stop_check["status"] == "failed"
    assert {
        "reason": "run_script_campaign_command_missing_disable_early_stop",
        "run_script": str(run_sh),
    } in early_stop_check["detail"]["failures"]


def test_launch_readiness_rejects_manifest_disable_early_stop_prefix_only(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["command"] = manifest["command"].replace(
        "--disable-early-stop",
        "--disable-early-stopper",
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    early_stop_check = report["checks"]["run_script_no_early_stop_enforced"]
    assert early_stop_check["status"] == "failed"
    assert {
        "reason": "manifest_command_missing_disable_early_stop",
        "manifest_path": str(manifest_path),
    } in early_stop_check["detail"]["failures"]


def test_launch_readiness_rejects_run_script_disable_early_stop_prefix_only(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            " --disable-early-stop\nSTATUS=$?",
            " --disable-early-stopper\nSTATUS=$?",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    early_stop_check = report["checks"]["run_script_no_early_stop_enforced"]
    assert early_stop_check["status"] == "failed"
    assert {
        "reason": "run_script_campaign_command_missing_disable_early_stop",
        "run_script": str(run_sh),
    } in early_stop_check["detail"]["failures"]


def test_launch_readiness_rejects_data_root_failure_without_postrun_call(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            "if [[ \"${COMPLETION_PREFLIGHT:-0}\" == \"1\" ]]; then",
            """if [[ ! -d "$SCION_WAREHOUSE_DATA_ROOT/production/generated" ]]; then
  echo "WAREHOUSE_DATA_ROOT_MISSING:$SCION_WAREHOUSE_DATA_ROOT"
  exit 64
fi
if [[ "${COMPLETION_PREFLIGHT:-0}" == "1" ]]; then""",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    data_root_check = report["checks"]["run_script_data_root_failure_reports"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert data_root_check["required"] is True
    assert data_root_check["status"] == "failed"
    assert data_root_check["detail"]["failures"] == [
        {"reason": "postrun_report_call_after_data_root_exit"}
    ]


def test_launch_readiness_ignores_comment_only_data_root_failure_marker(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            "if [[ \"${COMPLETION_PREFLIGHT:-0}\" == \"1\" ]]; then",
            """# WAREHOUSE_DATA_ROOT_MISSING:$SCION_WAREHOUSE_DATA_ROOT
if [[ "${COMPLETION_PREFLIGHT:-0}" == "1" ]]; then""",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    data_root_check = report["checks"]["run_script_data_root_failure_reports"]

    assert data_root_check["status"] == "ok"
    assert data_root_check["detail"] == {
        "run_script": str(run_sh),
        "required": False,
        "reason": "no_data_root_failure_path",
        "ignored_non_executable_marker_count": 1,
    }


def test_launch_readiness_rejects_api_key_env_failure_without_postrun_call(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            "if [[ \"${COMPLETION_PREFLIGHT:-0}\" == \"1\" ]]; then",
            """if [[ -z "${SCION_MISSING_TEST_KEY:-}" ]]; then
  echo "SCION_API_KEY_ENV_MISSING:SCION_MISSING_TEST_KEY"
  exit 64
fi
if [[ "${COMPLETION_PREFLIGHT:-0}" == "1" ]]; then""",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    api_key_check = report["checks"]["run_script_api_key_env_failure_reports"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert api_key_check["required"] is True
    assert api_key_check["status"] == "failed"
    assert api_key_check["detail"]["failures"] == [
        {"reason": "postrun_report_call_after_api_key_env_exit"}
    ]


def test_launch_readiness_ignores_comment_only_api_key_env_failure_marker(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            "if [[ \"${COMPLETION_PREFLIGHT:-0}\" == \"1\" ]]; then",
            """# SCION_API_KEY_ENV_MISSING:SCION_MISSING_TEST_KEY
if [[ "${COMPLETION_PREFLIGHT:-0}" == "1" ]]; then""",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    api_key_check = report["checks"]["run_script_api_key_env_failure_reports"]

    assert api_key_check["status"] == "ok"
    assert api_key_check["detail"] == {
        "run_script": str(run_sh),
        "required": False,
        "reason": "failure_marker_not_present",
        "failure_marker": "SCION_API_KEY_ENV_MISSING",
        "ignored_non_executable_marker_count": 1,
    }


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
    runtime_guard_paths: str | None = None,
    problem_family: str = "cvrp",
    research_focus: dict[str, object] | None = None,
    include_code_constraint_bridge: bool = True,
) -> Path:
    if runtime_guard_paths is None:
        runtime_guard_paths = _default_runtime_guard_paths(problem_family)
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
        f"--campaign-dir {campaign_dir} --rounds 1 "
        f"--agentic-proposal --disable-early-stop"
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
        "problem_family": problem_family,
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
            "runtime_guard_paths": runtime_guard_paths,
        },
        "config": {
            "problem": str(config_dir / "problem.yaml"),
            "protocol": str(config_dir / "protocol.yaml"),
            "split": str(config_dir / "split.yaml"),
            "seeds": str(config_dir / "seeds.yaml"),
        },
        "execution": {
            "rounds": 1,
            "time_limit_sec": 30,
            "agentic_session_timeout_sec": 900,
            "measurement_governance": "on",
            "proposal_context_ablation": "full",
            "agentic_proposal": True,
            "disable_early_stop": True,
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
        manifest["research_focus"] = (
            research_focus if research_focus is not None else _cvrp_research_focus()
        )
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
        "\n".join(
            [
                f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}",
                f"SCION_DIR={SCION_DIR}",
                f"PYTHONPATH={SCION_DIR}",
                "SCION_MODEL=gpt-5.5",
                "SCION_BASE_URL=http://127.0.0.1:8080",
                "COMPLETION_PREFLIGHT=1",
                "DISABLE_EARLY_STOP=1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (run_root / "run.sh").write_text(
        f"""#!/usr/bin/env bash
set -uo pipefail
RUN_ROOT={run_root}
source "$RUN_ROOT/launch.env"
REPO_ROOT={SCION_DIR.parent}
SCION_DIR={SCION_DIR}
PY={sys.executable}
GIT_COMMIT={_git_head_short()}
GIT_RUNTIME_GUARD_PATHS={json.dumps(runtime_guard_paths)}
PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}
export RUN_ROOT REPO_ROOT SCION_DIR PY PYTHONPATH SCION_MODEL SCION_BASE_URL GIT_COMMIT GIT_RUNTIME_GUARD_PATHS PREPARED_RUN_MANIFEST
write_postrun_acceptance_reports() {{
  POSTRUN_READINESS_STATUS=0
  "$PY" "$SCION_DIR/tools/check_postrun_acceptance.py" "$RUN_ROOT" \
    --require-current-run-ready \
    --format json \
    > "$RUN_ROOT/postrun_acceptance/readiness/fixture.postrun_acceptance_readiness.v1.json" \
    || POSTRUN_READINESS_STATUS=$?
  echo "POSTRUN_READINESS_EXIT_STATUS:$POSTRUN_READINESS_STATUS" >> "$RUN_ROOT/run.log"
}}
read -r -a _GIT_RUNTIME_GUARD_PATHS <<< "$GIT_RUNTIME_GUARD_PATHS"
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain -- "${{_GIT_RUNTIME_GUARD_PATHS[@]}}")" ]]; then
  echo "GIT_RUNTIME_DIRTY:$GIT_RUNTIME_GUARD_PATHS"
  exit 64
fi
_ACTUAL_GIT_COMMIT="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
if [[ "$_ACTUAL_GIT_COMMIT" != "$GIT_COMMIT" ]]; then
  if git -C "$REPO_ROOT" diff --quiet "$GIT_COMMIT" HEAD -- "${{_GIT_RUNTIME_GUARD_PATHS[@]}}"; then
    echo "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED:expected=$GIT_COMMIT actual=$_ACTUAL_GIT_COMMIT paths=$GIT_RUNTIME_GUARD_PATHS"
  else
    echo "GIT_COMMIT_MISMATCH:expected=$GIT_COMMIT actual=$_ACTUAL_GIT_COMMIT paths=$GIT_RUNTIME_GUARD_PATHS"
    exit 64
  fi
fi
unset _ACTUAL_GIT_COMMIT _GIT_RUNTIME_GUARD_PATHS
if [[ "${{COMPLETION_PREFLIGHT:-0}}" == "1" ]]; then
  PREFLIGHT_STATUS=64
  "$PY" "$SCION_DIR/tools/check_gpt55_proxy.py" \
    --base-url "$SCION_BASE_URL" \
    --model "$SCION_MODEL" \
    --json || PREFLIGHT_STATUS=$?
  if [[ "$PREFLIGHT_STATUS" -ne 0 ]]; then
    printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":%s,"pre_campaign_completion_preflight":"failed"}}\\n' "$PREFLIGHT_STATUS" > "$RUN_ROOT/run_status.json"
    write_postrun_acceptance_reports
    exit "$PREFLIGHT_STATUS"
  fi
fi
{sys.executable} -m scion.cli.main run --problem {config_dir / 'problem.yaml'} --protocol {config_dir / 'protocol.yaml'} --split {config_dir / 'split.yaml'} --seeds {config_dir / 'seeds.yaml'} --campaign-dir {campaign_dir} --rounds 1 --agentic-proposal --disable-early-stop
STATUS=$?
write_postrun_acceptance_reports
exit "$STATUS"
""",
        encoding="utf-8",
    )
    if include_prompt_context_readiness:
        _write_prompt_context_readiness(
            run_root,
            ready=include_research_focus,
            launch_markers=prompt_context_launch_markers,
            problem_family=problem_family,
            include_code_constraint_bridge=include_code_constraint_bridge,
        )
    if include_analysis_brief:
        _write_prepared_analysis_brief(run_root)
    return run_root


def _default_runtime_guard_paths(problem_family: str) -> str:
    base = "scion/scion :(exclude)scion/scion/tests scion/tools"
    if problem_family == "warehouse_delivery":
        return f"{base} scion/problems/warehouse_delivery surrogate"
    return f"{base} scion/problems/cvrp vrp"


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


def _warehouse_research_focus() -> dict[str, object]:
    return {
        "scope": "report_only_prepared_handoff",
        "accepted_checkpoint": "Champion v2 promoted.",
        "current_question": (
            "Can warehouse v2 plateau be advanced with one bounded follow-up?"
        ),
        "required_evidence": [
            "preserve promotion behavior",
            "branch transfer evidence",
            "quality-blocked and protocol-evaluated branches separated",
            "cost_delta and split_delta diagnostics exported",
            "fast completion runtime retained",
        ],
        "default_avoid_directions": [
            "restart from baseline",
            "proposal-quality only claims",
            "fast completion without current-run evidence",
            "accept split_delta_sum==0 as success",
            "broad warehouse matrix before v2 follow-up",
        ],
        "decision_boundary": (
            "Keep warehouse follow-up evidence out of DecisionFeatures, Protocol, "
            "promotion, and scheduler state."
        ),
    }


def _write_prepared_analysis_brief(run_root: Path) -> None:
    manifest = json.loads(
        (run_root / "prepared_run_manifest.v1.json").read_text(encoding="utf-8")
    )
    problem_family = str(manifest["problem_family"])
    if problem_family == "warehouse_delivery":
        filename = "warehouse_on_full.prepared_analysis_brief.v1.json"
        cvrp_summary = {"available": False, "current_run_evidence": False}
        warehouse_summary = _prepared_warehouse_summary()
    else:
        filename = "cvrp_on_full.prepared_analysis_brief.v1.json"
        cvrp_summary = _prepared_cvrp_summary()
        warehouse_summary = {"available": False, "current_run_evidence": False}
    _write_json(
        run_root
        / "prepared_handoff"
        / "analysis_brief"
        / filename,
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
            "cvrp_large_twoopt_summary": cvrp_summary,
            "warehouse_followup_summary": warehouse_summary,
        },
    )


def _prepared_cvrp_summary() -> dict[str, object]:
    return {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "available": True,
        "current_run_evidence": False,
        "interpretation": "prepared_only_launch_required",
        "launch_required_before_twoopt_conclusion": True,
        "evidence_gaps": [
            "launch_required_before_bounded_twoopt_conclusion",
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
    }


def _prepared_warehouse_summary() -> dict[str, object]:
    return {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "available": True,
        "current_run_evidence": False,
        "interpretation": "prepared_only_launch_required",
        "launch_required_before_plateau_conclusion": True,
        "evidence_gaps": [
            "launch_required_before_plateau_conclusion",
        ],
        "deferred_review_axes": [
            "confirm_protocol_evaluated_current_run_evidence",
            "confirm_measurement_runtime_and_continuity_review_inputs",
        ],
        "review_axes_actionability": (
            "not_actionable_before_launch_current_run_evidence_required"
        ),
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_prompt_context_readiness(
    run_root: Path,
    *,
    ready: bool,
    launch_markers: bool,
    problem_family: str,
    include_code_constraint_bridge: bool,
) -> None:
    missing_required = [] if ready else ["prepared_research_focus"]
    launch_marker_payload = {
        "launch_env_assignment": launch_markers,
        "prepared_manifest_exists": True,
        "run_sh_exports_manifest": launch_markers,
    }
    signals = {
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
        },
    }
    if include_code_constraint_bridge:
        if problem_family == "warehouse_delivery":
            signals["warehouse_active_subject_code_constraints_prompt_bridge"] = {
                "available": True,
                "detail": {
                    "provider_markers": {
                        "bounded_scan_guard": True,
                        "diagnostics_contract": True,
                        "lexicographic_guard": True,
                        "provider_hook": True,
                    },
                    "source_markers": {
                        "code_prompt_renderer": True,
                        "context_key": True,
                        "context_provider_payload": True,
                    },
                },
                "required": True,
                "runtime_generated_after_launch": False,
                "source": "fixture",
            }
        elif problem_family == "cvrp":
            signals["cvrp_active_subject_code_constraints_prompt_bridge"] = {
                "available": True,
                "detail": {
                    "provider_markers": {
                        "large_twoopt_runtime_guard": True,
                        "provider_hook": True,
                        "unbounded_twoopt_reject": True,
                    },
                    "source_markers": {
                        "code_prompt_renderer": True,
                        "context_key": True,
                        "context_provider_payload": True,
                    },
                },
                "required": True,
                "runtime_generated_after_launch": False,
                "source": "fixture",
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
            "problem_family": problem_family,
            "model": "gpt-5.5",
            "readiness": {
                "ready_for_launch_prompt_audit": ready,
                "missing_required": missing_required,
                "status": "ready" if ready else "missing_required_sources",
            },
            "signals": signals,
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
