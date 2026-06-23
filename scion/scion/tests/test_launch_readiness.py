from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from scion.research_guidance import (
    legacy_research_focus_to_contract,
    research_guidance_contract_to_dict,
)


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
    assert report["ready_meaning"] == (
        "static readiness only; not operator launch approval"
    )
    assert report["readiness_scope"] == "static_only_completion_preflight_not_run"
    assert report["static_ready"] is True
    assert report["launch_ready"] is False
    assert report["launch_blockers"] == ["completion_preflight_not_run"]
    assert report["failed_required_checks"] == []
    assert report["failed_static_required_checks"] == []
    assert report["failed_optional_checks"] == []
    assert report["checks"]["prepared_only_not_started"]["status"] == "ok"
    assert report["checks"]["prepared_contract_complete"]["status"] == "ok"
    assert report["checks"]["git_runtime_consistent"]["status"] == "ok"
    assert report["checks"]["git_runtime_worktree_clean"]["status"] == "ok"
    assert (
        report["checks"]["runtime_guard_paths_cover_launch_tools"]["status"] == "ok"
    )
    assert (
        report["checks"]["run_script_runtime_guard_contract_consistency"]["status"]
        == "ok"
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
    assert (
        problem_specific["detail"]["checks"]["cvrp_cmt_case_protection_present"][
            "passed"
        ]
        is True
    )
    assert (
        problem_specific["detail"]["checks"]["cvrp_resume_continuity_present"][
            "passed"
        ]
        is True
    )
    split_check = problem_specific["detail"]["checks"][
        "cvrp_protected_cases_in_split"
    ]
    assert split_check["passed"] is True
    assert split_check["detail"]["stage_membership"] == {
        "CMT2": ["screening"],
        "CMT4": ["screening"],
    }
    assert split_check["detail"]["required_stage"] == "screening"
    assert (
        report["checks"]["prepared_handoff_rebuild_declared_outputs_present"][
            "status"
        ]
        == "ok"
    )
    assert report["checks"]["prompt_context_readiness_complete"]["status"] == "ok"
    prompt_detail = report["checks"]["prompt_context_readiness_complete"]["detail"]
    assert prompt_detail["provider_prompt_scope"] == (
        "prepared_renderer_summary_not_live_provider_prompt"
    )
    assert prompt_detail["raw_provider_prompt_rendered"] is False
    prompt_artifact_summary = prompt_detail["artifact_summaries"][0]
    assert prompt_artifact_summary["raw_provider_prompt_rendered"] is False
    focus_summary = prompt_artifact_summary["prepared_focus_prompt_summary"]
    assert focus_summary["missing_rendered_paths"] == []
    assert focus_summary["contract_present"] is True
    assert focus_summary["schema_valid"] is True
    assert focus_summary["guidance_text_digest_present"] is True
    code_summary = prompt_artifact_summary[
        "active_subject_code_constraints_summary"
    ]
    assert code_summary["available"] is True
    assert code_summary["constraint_ids_all_present"] is True
    assert code_summary["forbidden_patterns_all_present"] is True
    assert report["checks"]["prepared_analysis_brief_current"]["status"] == "ok"
    assert (
        report["checks"]["analysis_brief_prepared_contract_consistency"]["status"]
        == "ok"
    )
    markdown = readiness_tool.render_markdown(report)
    assert "readiness_scope=static_only_completion_preflight_not_run" in markdown
    assert "not launch approval" in markdown
    assert report["checks"]["run_script_preflight_failure_reports"]["status"] == "ok"
    assert (
        report["checks"]["run_script_completion_preflight_enforced"]["status"] == "ok"
    )
    assert report["checks"]["run_script_pythonpath_enforced"]["status"] == "ok"
    assert report["checks"]["run_script_model_route_enforced"]["status"] == "ok"
    assert (
        report["checks"]["run_script_campaign_contract_consistency"]["status"] == "ok"
    )
    assert report["checks"]["run_script_no_early_stop_enforced"]["status"] == "ok"
    assert (
        report["checks"]["run_script_proposal_headroom_enforced"]["status"] == "ok"
    )
    assert report["checks"]["run_script_strict_postrun_rebuild"]["status"] == "ok"
    assert report["checks"]["run_script_strict_postrun_readiness"]["status"] == "ok"
    assert (
        report["checks"]["run_script_postrun_reports_after_campaign"]["status"] == "ok"
    )
    assert (
        report["checks"]["run_script_runtime_guard_failure_reports"]["status"] == "ok"
    )
    assert report["checks"]["launch_env_secret_permissions"]["status"] == "ok"
    runtime_guard_detail = report["checks"]["git_runtime_guard_commit_consistent"][
        "detail"
    ]
    assert report["runtime_guard_status"] == "ok"
    assert report["runtime_guard_reason"] in {
        "runtime_guard_commit_matches",
        "runtime_guard_paths_unchanged_since_prepare",
    }
    assert report["prepared_runtime_commit"] == runtime_guard_detail[
        "prepared_commit"
    ]
    assert report["actual_runtime_commit"] == runtime_guard_detail.get(
        "actual_commit"
    )
    assert report["runtime_guard_paths"] == runtime_guard_detail[
        "runtime_guard_paths"
    ]
    assert report["launch_env_secret_permissions"] == "ok"
    assert report["launch_env_mode"] == "0o600"
    marker_summary = report["campaign_execution_marker_summary"]
    assert marker_summary["status"] == "ok"
    assert marker_summary["required"] is True
    assert marker_summary["ok"] is True
    assert marker_summary["failure_reasons"] == []
    assert report["campaign_execution_marker_status"] == "ok"
    assert report["campaign_execution_marker_ok"] is True
    assert report["campaign_execution_marker_failure_reasons"] == []
    assert isinstance(report["campaign_execution_marker_position"], int)
    assert isinstance(
        report["campaign_execution_marker_preflight_failure_exit_position"], int
    )
    assert isinstance(
        report["campaign_execution_marker_campaign_command_position"], int
    )
    assert (
        report["campaign_execution_marker_preflight_failure_exit_position"]
        < report["campaign_execution_marker_position"]
        < report["campaign_execution_marker_campaign_command_position"]
    )
    assert report["checks"]["run_script_data_root_failure_reports"]["status"] == "ok"
    assert report["checks"]["run_script_api_key_env_failure_reports"]["status"] == "ok"
    assert report["checks"]["completion_preflight"]["status"] == "skipped"
    assert report["completion_preflight_summary"] == {
        "status": "skipped",
        "required": False,
        "ok": False,
        "http_status": None,
        "classification": None,
        "code": None,
        "message": None,
        "auth_pool": None,
        "model": None,
        "base_url": None,
        "login_url": None,
    }
    assert report["completion_http_status"] is None
    assert report["completion_classification"] is None
    assert report["completion_code"] is None
    assert report["completion_auth_pool"] is None
    assert report["completion_login_url"] is None
    assert report["completion_next_step"] is None
    assert report["completion_operator_action"] is None
    markdown = readiness_tool.render_markdown(report)
    assert markdown.startswith("# Launch Readiness:")
    assert "Campaign execution marker: `ok`" in markdown
    assert "Launch only after rerunning this tool" in markdown


def test_launch_readiness_rejects_already_started_root(tmp_path: Path) -> None:
    run_root = _write_prepared_root(tmp_path)
    (run_root / "exit.txt").write_text("WRAPPER_EXIT_STATUS:64\n", encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["launch_ready"] is False
    assert "not_already_started" in report["failed_required_checks"]
    assert "not_already_started" in report["failed_static_required_checks"]
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


def test_launch_readiness_rejects_missing_warehouse_measurement_handoff(
    tmp_path: Path,
) -> None:
    research_focus = _warehouse_research_focus()
    research_focus.pop("measurement_opportunity_diagnostics")
    run_root = _write_prepared_root(
        tmp_path,
        problem_family="warehouse_delivery",
        research_focus=research_focus,
    )

    report = readiness_tool.build_readiness(run_root)
    inventory = readiness_tool.build_inventory(run_root)
    contract = inventory["launcher"]["prepared_run_contract"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["checks"]["prepared_contract_complete"]["status"] == "failed"
    problem_specific = report["checks"]["problem_specific_prepared_handoff"]
    assert problem_specific["status"] == "failed"
    assert "warehouse_measurement_handoff_present" in problem_specific["detail"][
        "failed_checks"
    ]
    assert contract["contract_complete"] is False
    assert (
        contract["checks"]["warehouse_measurement_handoff_present"]["passed"]
        is False
    )


def test_launch_readiness_rejects_hardcoded_warehouse_measurement_handoff(
    tmp_path: Path,
) -> None:
    research_focus = _warehouse_research_focus()
    measurement = research_focus["measurement_opportunity_diagnostics"]
    assert isinstance(measurement, dict)
    measurement.pop("source")
    measurement.pop("measurement_readiness")
    measurement.pop("calibration")
    run_root = _write_prepared_root(
        tmp_path,
        problem_family="warehouse_delivery",
        research_focus=research_focus,
    )

    report = readiness_tool.build_readiness(run_root)
    inventory = readiness_tool.build_inventory(run_root)
    contract = inventory["launcher"]["prepared_run_contract"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["checks"]["prepared_contract_complete"]["status"] == "failed"
    problem_specific = report["checks"]["problem_specific_prepared_handoff"]
    assert problem_specific["status"] == "failed"
    assert "warehouse_measurement_handoff_problem_owned_source" in problem_specific[
        "detail"
    ]["failed_checks"]
    assert contract["contract_complete"] is False
    assert (
        contract["checks"]["warehouse_measurement_handoff_problem_owned_source"][
            "passed"
        ]
        is False
    )


def test_launch_readiness_rejects_hardcoded_cvrp_measurement_handoff(
    tmp_path: Path,
) -> None:
    research_focus = _cvrp_research_focus()
    measurement = research_focus["measurement_opportunity_diagnostics"]
    assert isinstance(measurement, dict)
    measurement.pop("source")
    measurement.pop("measurement_readiness")
    measurement.pop("calibration")
    run_root = _write_prepared_root(tmp_path, research_focus=research_focus)

    report = readiness_tool.build_readiness(run_root)
    inventory = readiness_tool.build_inventory(run_root)
    contract = inventory["launcher"]["prepared_run_contract"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["checks"]["prepared_contract_complete"]["status"] == "failed"
    problem_specific = report["checks"]["problem_specific_prepared_handoff"]
    assert problem_specific["status"] == "failed"
    assert "cvrp_measurement_handoff_problem_owned_source" in problem_specific[
        "detail"
    ]["failed_checks"]
    assert contract["contract_complete"] is False
    assert (
        contract["checks"]["cvrp_measurement_handoff_problem_owned_source"]["passed"]
        is False
    )


def test_launch_readiness_rejects_missing_cvrp_cmt_case_protection(
    tmp_path: Path,
) -> None:
    research_focus = _cvrp_research_focus()
    research_focus.pop("case_protection_requirements")
    run_root = _write_prepared_root(tmp_path, research_focus=research_focus)

    report = readiness_tool.build_readiness(run_root)
    inventory = readiness_tool.build_inventory(run_root)
    contract = inventory["launcher"]["prepared_run_contract"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["checks"]["prepared_contract_complete"]["status"] == "failed"
    problem_specific = report["checks"]["problem_specific_prepared_handoff"]
    assert problem_specific["status"] == "failed"
    assert "cvrp_cmt_case_protection_present" in problem_specific["detail"][
        "failed_checks"
    ]
    assert contract["contract_complete"] is False
    assert contract["checks"]["cvrp_cmt_case_protection_present"]["passed"] is False


def test_launch_readiness_rejects_missing_cvrp_resume_continuity(
    tmp_path: Path,
) -> None:
    research_focus = _cvrp_research_focus()
    research_focus.pop("resume_continuity_requirements")
    run_root = _write_prepared_root(tmp_path, research_focus=research_focus)

    report = readiness_tool.build_readiness(run_root)
    inventory = readiness_tool.build_inventory(run_root)
    contract = inventory["launcher"]["prepared_run_contract"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["checks"]["prepared_contract_complete"]["status"] == "failed"
    problem_specific = report["checks"]["problem_specific_prepared_handoff"]
    assert problem_specific["status"] == "failed"
    assert "cvrp_resume_continuity_present" in problem_specific["detail"][
        "failed_checks"
    ]
    assert contract["contract_complete"] is False
    assert contract["checks"]["cvrp_resume_continuity_present"]["passed"] is False


def test_launch_readiness_rejects_cvrp_protected_cases_absent_from_split(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    (run_root / "config" / "split.yaml").write_text(
        "\n".join(
            [
                "version: fixture",
                "screening:",
                "- cvrplib/A/A-n64-k9.vrp",
                "validation: []",
                "frozen: []",
                "canary: []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_prepared_handoff_rebuild_manifest(run_root)

    report = readiness_tool.build_readiness(run_root)
    inventory = readiness_tool.build_inventory(run_root)
    contract = inventory["launcher"]["prepared_run_contract"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["checks"]["prepared_contract_complete"]["status"] == "failed"
    problem_specific = report["checks"]["problem_specific_prepared_handoff"]
    assert problem_specific["status"] == "failed"
    assert "cvrp_protected_cases_in_split" in problem_specific["detail"][
        "failed_checks"
    ]
    split_check = contract["checks"]["cvrp_protected_cases_in_split"]
    assert split_check["passed"] is False
    assert split_check["detail"]["missing_cases"] == ["CMT2", "CMT4"]
    assert split_check["detail"]["stage_membership"] == {
        "CMT2": [],
        "CMT4": [],
    }


def test_launch_readiness_rejects_cvrp_protected_cases_outside_screening(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    (run_root / "config" / "split.yaml").write_text(
        "\n".join(
            [
                "version: fixture",
                "screening:",
                "- cvrplib/A/A-n64-k9.vrp",
                "validation:",
                "- cvrplib/CMT/CMT2.vrp",
                "- cvrplib/CMT/CMT4.vrp",
                "frozen: []",
                "canary: []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_prepared_handoff_rebuild_manifest(run_root)

    report = readiness_tool.build_readiness(run_root)
    inventory = readiness_tool.build_inventory(run_root)
    contract = inventory["launcher"]["prepared_run_contract"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert report["checks"]["prepared_contract_complete"]["status"] == "failed"
    problem_specific = report["checks"]["problem_specific_prepared_handoff"]
    assert problem_specific["status"] == "failed"
    assert "cvrp_protected_cases_in_split" in problem_specific["detail"][
        "failed_checks"
    ]
    split_check = contract["checks"]["cvrp_protected_cases_in_split"]
    assert split_check["passed"] is False
    assert split_check["detail"]["missing_cases"] == []
    assert split_check["detail"]["missing_screening_cases"] == ["CMT2", "CMT4"]
    assert split_check["detail"]["stage_membership"] == {
        "CMT2": ["validation"],
        "CMT4": ["validation"],
    }
    assert split_check["detail"]["required_stage"] == "screening"


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


def test_launch_readiness_rejects_run_script_git_commit_contract_mismatch(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    run_sh.write_text(
        "\n".join(
            "GIT_COMMIT=deadbeef"
            if line.startswith("GIT_COMMIT=")
            else line
            for line in run_text.splitlines()
        )
        + "\n",
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    contract_check = report["checks"][
        "run_script_runtime_guard_contract_consistency"
    ]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert contract_check["status"] == "failed"
    assert {
        "reason": "run_script_git_commit_mismatch",
        "expected": _git_head_short(),
        "actual": "deadbeef",
    } in contract_check["detail"]["failures"]
    assert {
        "reason": "effective_git_commit_mismatch",
        "expected": _git_head_short(),
        "actual": "deadbeef",
        "source": "run_script",
    } in contract_check["detail"]["failures"]


def test_launch_readiness_rejects_run_script_runtime_guard_paths_contract_mismatch(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    run_sh.write_text(
        "\n".join(
            "GIT_RUNTIME_GUARD_PATHS=scion/tools"
            if line.startswith("GIT_RUNTIME_GUARD_PATHS=")
            else line
            for line in run_text.splitlines()
        )
        + "\n",
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    contract_check = report["checks"][
        "run_script_runtime_guard_contract_consistency"
    ]
    expected_paths = _default_runtime_guard_paths("cvrp")

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert contract_check["status"] == "failed"
    assert {
        "reason": "run_script_runtime_guard_paths_mismatch",
        "expected": expected_paths,
        "actual": "scion/tools",
    } in contract_check["detail"]["failures"]
    assert {
        "reason": "effective_runtime_guard_paths_mismatch",
        "expected": expected_paths,
        "actual": "scion/tools",
        "source": "run_script",
    } in contract_check["detail"]["failures"]


def test_launch_readiness_rejects_launch_env_runtime_guard_contract_mismatch(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    launch_env_text = launch_env.read_text(encoding="utf-8")
    launch_env.write_text(
        "\n".join(
            "GIT_RUNTIME_GUARD_PATHS=scion/tools"
            if line.startswith("GIT_RUNTIME_GUARD_PATHS=")
            else line
            for line in launch_env_text.splitlines()
        )
        + "\n",
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    contract_check = report["checks"][
        "run_script_runtime_guard_contract_consistency"
    ]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert contract_check["status"] == "failed"
    assert {
        "reason": "launch_env_runtime_guard_paths_mismatch",
        "expected": _default_runtime_guard_paths("cvrp"),
        "actual": "scion/tools",
    } in contract_check["detail"]["failures"]


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


def test_launch_readiness_rejects_runtime_guard_failure_without_postrun_reports(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    dirty_pos = run_text.index("GIT_RUNTIME_DIRTY:$GIT_RUNTIME_GUARD_PATHS")
    call_pos = run_text.index("  write_postrun_acceptance_reports\n", dirty_pos)
    run_sh.write_text(
        run_text[:call_pos]
        + run_text[call_pos + len("  write_postrun_acceptance_reports\n") :],
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    guard_failure_check = report["checks"][
        "run_script_runtime_guard_failure_reports"
    ]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert guard_failure_check["status"] == "failed"
    assert {
        "reason": "postrun_report_call_after_git_runtime_dirty_exit"
    } in guard_failure_check["detail"]["failures"]


def test_launch_readiness_rejects_runtime_guard_postrun_before_status_writer(
    tmp_path: Path,
) -> None:
    run_sh = tmp_path / "run.sh"
    run_sh.write_text(
        """#!/usr/bin/env bash
write_postrun_acceptance_reports() {
  return 0
}
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain -- "${_GIT_RUNTIME_GUARD_PATHS[@]}")" ]]; then
  echo "GIT_RUNTIME_DIRTY:$GIT_RUNTIME_GUARD_PATHS"
  write_postrun_acceptance_reports
  printf '{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":64,"git_runtime_dirty":true}\n' > "$RUN_ROOT/run_status.json"
  exit 64
fi
if [[ "$_ACTUAL_GIT_COMMIT" != "$GIT_COMMIT" ]]; then
  echo "GIT_COMMIT_MISMATCH:expected=$GIT_COMMIT actual=$_ACTUAL_GIT_COMMIT paths=$GIT_RUNTIME_GUARD_PATHS"
  printf '{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":64,"git_runtime_commit_mismatch":true}\n' > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit 64
fi
""",
        encoding="utf-8",
    )

    status, detail = readiness_tool._run_script_runtime_guard_failure_reports(
        run_sh
    )

    assert status == "failed"
    assert {
        "reason": "postrun_report_call_before_git_runtime_dirty_status_writer"
    } in detail["failures"]


def test_launch_readiness_rejects_scion_dir_failure_without_postrun_reports(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    start = run_text.index('if ! cd "$SCION_DIR"; then')
    end = run_text.index(
        'read -r -a _GIT_RUNTIME_GUARD_PATHS <<< "$GIT_RUNTIME_GUARD_PATHS"',
        start,
    )
    run_sh.write_text(
        run_text[:start] + 'cd "$SCION_DIR" || exit 1\n' + run_text[end:],
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    scion_dir_check = report["checks"]["run_script_scion_dir_failure_reports"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert scion_dir_check["status"] == "failed"
    assert {"reason": "scion_dir_failure_path_missing"} in scion_dir_check[
        "detail"
    ]["failures"]


def test_launch_readiness_rejects_launch_env_failure_without_postrun_reports(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    start = run_text.index('if [[ ! -r "$RUN_ROOT/launch.env" ]]; then')
    end = run_text.index('if ! cd "$SCION_DIR"; then', start)
    run_sh.write_text(run_text[:start] + run_text[end:], encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)
    launch_env_check = report["checks"]["run_script_launch_env_failure_reports"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert launch_env_check["status"] == "failed"
    assert {"reason": "launch_env_failure_path_missing"} in launch_env_check[
        "detail"
    ]["failures"]


def test_launch_readiness_rejects_group_readable_launch_env(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    launch_env.chmod(0o644)

    report = readiness_tool.build_readiness(run_root)
    permission_check = report["checks"]["launch_env_secret_permissions"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert "launch_env_secret_permissions" in report["failed_required_checks"]
    assert "launch_env_secret_permissions" in report["failed_static_required_checks"]
    assert permission_check["status"] == "failed"
    assert permission_check["detail"]["mode"] == "0o644"
    assert {
        "reason": "launch_env_has_group_or_other_permissions",
        "launch_env": str(launch_env),
        "mode": "0o644",
        "group_or_other_mode": "0o44",
        "expected": "no group/other permission bits",
    } in permission_check["detail"]["failures"]


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
    contract_check = report["checks"]["analysis_brief_prepared_contract_consistency"]
    assert contract_check["status"] == "failed"
    assert contract_check["detail"]["failures"][0]["reason"] == (
        "missing_prepared_analysis_brief"
    )
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


def test_launch_readiness_rejects_undeclared_prepared_handoff_output(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    extra_output = (
        run_root
        / "prepared_handoff"
        / "analysis_brief"
        / "zz_stale.prepared_analysis_brief.v1.json"
    )
    _write_json(extra_output, {"schema_version": "stale.test"})

    report = readiness_tool.build_readiness(run_root)
    output_check = report["checks"][
        "prepared_handoff_rebuild_declared_outputs_present"
    ]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert output_check["status"] == "failed"
    assert output_check["required"] is True
    assert output_check["detail"]["missing_outputs"] == []
    assert output_check["detail"]["inconsistent_outputs"] == []
    assert output_check["detail"]["unexpected_outputs"] == [
        {
            "family": "analysis_brief",
            "path": str(extra_output),
            "reason": "undeclared_generated_output",
        }
    ]


def test_launch_readiness_rejects_prepared_handoff_manifest_output_outside_family_dir(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    manifest_path = (
        run_root / "prepared_handoff" / "rebuild" / "prepared_handoff_rebuild.v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    analysis_family = manifest["families"]["analysis_brief"]
    declared_brief = Path(
        next(
            output
            for output in analysis_family["outputs"]
            if str(output).endswith(".json")
        )
    )
    external_brief = tmp_path / "external" / "stale.prepared_analysis_brief.v1.json"
    _write_json(
        external_brief,
        json.loads(declared_brief.read_text(encoding="utf-8")),
    )
    declared_brief.unlink()
    analysis_family["outputs"] = [
        str(external_brief) if output == str(declared_brief) else output
        for output in analysis_family["outputs"]
    ]
    analysis_family["outputs_present"].pop(str(declared_brief))
    analysis_family["outputs_present"][str(external_brief)] = True
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)
    output_check = report["checks"][
        "prepared_handoff_rebuild_declared_outputs_present"
    ]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert output_check["status"] == "failed"
    assert output_check["required"] is True
    assert output_check["detail"]["missing_outputs"] == []
    assert output_check["detail"]["inconsistent_outputs"] == []
    assert output_check["detail"]["out_of_scope_outputs"] == [
        {
            "family": "analysis_brief",
            "path": str(external_brief),
            "manifest_output": str(external_brief),
            "expected_directory": str(
                run_root / "prepared_handoff" / "analysis_brief"
            ),
            "reason": "manifest_output_outside_family_directory",
        }
    ]


def test_launch_readiness_rejects_prepared_handoff_rebuild_identity_mismatch(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    manifest_path = (
        run_root / "prepared_handoff" / "rebuild" / "prepared_handoff_rebuild.v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["run_root"] = str(tmp_path / "other-root")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)
    output_check = report["checks"][
        "prepared_handoff_rebuild_declared_outputs_present"
    ]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert output_check["status"] == "failed"
    assert {
        "reason": "manifest_identity_mismatch",
        "field": "run_root",
        "expected": str(run_root),
        "actual": str(tmp_path / "other-root"),
    } in output_check["detail"]["manifest_failures"]


def test_launch_readiness_rejects_prepared_handoff_rebuild_boundary_gap(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    manifest_path = (
        run_root / "prepared_handoff" / "rebuild" / "prepared_handoff_rebuild.v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["report_only"] = False
    manifest["complete"] = False
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)
    output_check = report["checks"][
        "prepared_handoff_rebuild_declared_outputs_present"
    ]
    failures = {
        (failure["reason"], failure["field"])
        for failure in output_check["detail"]["manifest_failures"]
    }

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert output_check["status"] == "failed"
    assert ("manifest_boundary_flag_mismatch", "report_only") in failures
    assert ("manifest_boundary_flag_mismatch", "complete") in failures


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
    contract_check = report["checks"]["analysis_brief_prepared_contract_consistency"]
    assert contract_check["status"] == "failed"
    contract_failures = {
        failure["reason"] for failure in contract_check["detail"]["failures"]
    }
    assert "prepared_contract_problem_family_mismatch" in contract_failures
    assert "prepared_contract_git_mismatch" in contract_failures
    mismatches = [
        failure
        for failure in brief_check["detail"]["failures"]
        if failure["reason"] == "prepared_run_contract_identity_mismatch"
    ]
    assert {item["field"] for item in mismatches} == {
        "git.commit",
        "problem_family",
    }


def test_launch_readiness_allows_doc_only_prepared_contract_check_drift() -> None:
    brief_contract = {
        "git": {
            "commit": "abc123",
            "manifest_commit": "abc123",
            "checkout_commit": "abc123",
            "runtime_guard_paths": "scion/tools",
            "consistent": True,
            "detail": "checkout matches manifest commit",
        },
        "checks": {
            "git_runtime_consistent": {
                "passed": True,
                "detail": "checkout matches manifest commit",
            },
            "model_is_gpt55": {"passed": True, "detail": "gpt-5.5"},
        },
    }
    inventory_contract = {
        "git": {
            "commit": "abc123",
            "manifest_commit": "abc123",
            "checkout_commit": "docs456",
            "runtime_guard_paths": "scion/tools",
            "consistent": True,
            "detail": "checkout differs, but runtime guard paths are unchanged",
        },
        "checks": {
            "git_runtime_consistent": {
                "passed": True,
                "detail": "checkout differs, but runtime guard paths are unchanged",
            },
            "model_is_gpt55": {"passed": True, "detail": "gpt-5.5"},
        },
    }

    assert (
        readiness_tool._prepared_contract_consistency_failures(
            brief_contract,
            inventory_contract,
        )
        == []
    )

    inventory_contract["checks"]["git_runtime_consistent"] = {
        "passed": False,
        "detail": "runtime path changed",
    }

    failures = readiness_tool._prepared_contract_consistency_failures(
        brief_contract,
        inventory_contract,
    )

    assert "prepared_contract_checks_mismatch" in {
        failure["reason"] for failure in failures
    }


def test_launch_readiness_rejects_dirty_runtime_guard_worktree(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    guarded = repo / "scion" / "tools" / "runtime.py"
    guarded.parent.mkdir(parents=True)
    guarded.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    guarded.write_text("value = 2\n", encoding="utf-8")

    original_repo_dir = readiness_tool.REPO_DIR
    readiness_tool.REPO_DIR = repo
    try:
        status, detail = readiness_tool._git_runtime_worktree_clean(
            {"git": {"runtime_guard_paths": "scion/tools"}}
        )
    finally:
        readiness_tool.REPO_DIR = original_repo_dir

    assert status == "failed"
    assert detail["reason"] == "runtime_guard_worktree_dirty"
    assert detail["dirty_entries"] == [" M scion/tools/runtime.py"]


def test_launch_readiness_rejects_committed_runtime_guard_drift(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    guarded = repo / "scion" / "tools" / "runtime.py"
    guarded.parent.mkdir(parents=True)
    guarded.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    prepared_commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    guarded.write_text("value = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "runtime change"], cwd=repo, check=True)

    original_repo_dir = readiness_tool.REPO_DIR
    readiness_tool.REPO_DIR = repo
    try:
        status, detail = readiness_tool._git_runtime_guard_commit_consistent(
            {
                "git": {
                    "commit": prepared_commit,
                    "runtime_guard_paths": "scion/tools",
                }
            }
        )
    finally:
        readiness_tool.REPO_DIR = original_repo_dir

    assert status == "failed"
    assert detail["reason"] == "runtime_guard_paths_changed_since_prepare"
    assert detail["prepared_commit"] == prepared_commit
    assert detail["actual_commit"] != prepared_commit
    assert detail["git_diff_exit_code"] == 1


def test_launch_readiness_allows_committed_docs_only_drift(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    guarded = repo / "scion" / "tools" / "runtime.py"
    docs = repo / "scion" / "docs" / "note.md"
    guarded.parent.mkdir(parents=True)
    docs.parent.mkdir(parents=True)
    guarded.write_text("value = 1\n", encoding="utf-8")
    docs.write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    prepared_commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    docs.write_text("after\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "docs change"], cwd=repo, check=True)

    original_repo_dir = readiness_tool.REPO_DIR
    readiness_tool.REPO_DIR = repo
    try:
        status, detail = readiness_tool._git_runtime_guard_commit_consistent(
            {
                "git": {
                    "commit": prepared_commit,
                    "runtime_guard_paths": "scion/tools",
                }
            }
        )
    finally:
        readiness_tool.REPO_DIR = original_repo_dir

    assert status == "ok"
    assert detail["reason"] == "runtime_guard_paths_unchanged_since_prepare"
    assert detail["prepared_commit"] == prepared_commit
    assert detail["actual_commit"] != prepared_commit
    assert detail["git_diff_exit_code"] == 0


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


def test_launch_readiness_rejects_stale_research_focus_projection(
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
    detail = payload["signals"]["prepared_research_focus_projection"]["detail"]
    removed_path = detail["rendered_paths"][0]
    detail["rendered_paths"] = [
        path for path in detail["rendered_paths"] if path != removed_path
    ]
    detail["rendered_path_count"] = len(detail["rendered_paths"])
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == "prepared_focus_projection_field_mismatch"
        and failure["field"] == "rendered_paths"
        and removed_path in failure["expected"]
        and removed_path not in failure["actual"]
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_stale_research_focus_nested_projection(
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
    detail = payload["signals"]["prepared_research_focus_projection"]["detail"]
    detail["rendered_path_count"] = 0
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == "prepared_focus_projection_field_mismatch"
        and failure["field"] == "rendered_path_count"
        and failure["expected"] > 0
        and failure["actual"] == 0
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_missing_research_focus_prompt_summary(
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
    payload["signals"]["prepared_research_focus_prompt_bridge"]["detail"].pop(
        "prompt_summary"
    )
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == "prepared_focus_prompt_summary_missing"
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_stale_research_focus_prompt_summary(
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
    summary = payload["signals"]["prepared_research_focus_prompt_bridge"][
        "detail"
    ]["prompt_summary"]
    summary["guidance_text_digest_present"] = False
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == "prepared_focus_prompt_summary_field_mismatch"
        and failure["field"] == "guidance_text_digest_present"
        and failure["expected"] is True
        and failure["actual"] is False
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_missing_calibration_provenance_prompt_summary(
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
    summary = payload["signals"]["prepared_research_focus_prompt_bridge"][
        "detail"
    ]["prompt_summary"]
    summary["contract_schema_present"] = False
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == "prepared_focus_prompt_summary_field_mismatch"
        and failure["field"] == "contract_schema_present"
        and failure["expected"] is True
        and failure["actual"] is False
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_key_only_warehouse_research_focus_evidence(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(
        tmp_path,
        problem_family="warehouse_delivery",
        research_focus=_warehouse_research_focus(),
    )
    artifact_path = (
        run_root
        / "prepared_handoff"
        / "prompt_context_readiness"
        / "cvrp_on_full.prepared_prompt_context_readiness.v1.json"
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    summary = payload["signals"]["prepared_research_focus_prompt_bridge"][
        "detail"
    ]["prompt_summary"]
    summary["schema_valid"] = False
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == "prepared_focus_prompt_summary_field_mismatch"
        and failure["field"] == "schema_valid"
        and failure["expected"] is True
        and failure["actual"] is False
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_key_only_cvrp_large_twoopt_pair_evidence(
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
    summary = payload["signals"]["prepared_research_focus_prompt_bridge"][
        "detail"
    ]["prompt_summary"]
    summary["rendered_required_path_count"] = 0
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == "prepared_focus_prompt_summary_field_mismatch"
        and failure["field"] == "rendered_required_path_count"
        and failure["expected"] > 0
        and failure["actual"] == 0
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_missing_campaign_execution_marker(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    marker_start = run_text.index("CAMPAIGN_EXECUTION_MARKER_STARTED_AT=")
    marker_end = run_text.index(f"{sys.executable} -m scion.cli.main run", marker_start)
    run_sh.write_text(
        run_text[:marker_start] + run_text[marker_end:],
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    marker_check = report["checks"]["run_script_campaign_execution_marker_enforced"]
    assert marker_check["status"] == "failed"
    assert report["campaign_execution_marker_status"] == "failed"
    assert report["campaign_execution_marker_ok"] is False
    reasons = {failure["reason"] for failure in marker_check["detail"]["failures"]}
    assert "campaign_execution_marker_file_write_missing" in reasons
    assert "campaign_execution_marker_schema_missing" in reasons
    assert "campaign_execution_marker_log_marker_missing" in reasons
    assert set(report["campaign_execution_marker_failure_reasons"]) >= {
        "campaign_execution_marker_file_write_missing",
        "campaign_execution_marker_schema_missing",
        "campaign_execution_marker_log_marker_missing",
    }


def test_launch_readiness_rejects_campaign_execution_marker_after_campaign(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    marker_start = run_text.index("CAMPAIGN_EXECUTION_MARKER_STARTED_AT=")
    campaign_start = run_text.index(f"{sys.executable} -m scion.cli.main run")
    marker_block = run_text[marker_start:campaign_start]
    run_text = run_text[:marker_start] + run_text[campaign_start:]
    run_text = run_text.replace("\nSTATUS=$?\n", "\n" + marker_block + "STATUS=$?\n", 1)
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    marker_check = report["checks"]["run_script_campaign_execution_marker_enforced"]
    assert marker_check["status"] == "failed"
    assert report["campaign_execution_marker_status"] == "failed"
    assert report["campaign_execution_marker_ok"] is False
    assert {"reason": "campaign_execution_marker_after_campaign"} in marker_check[
        "detail"
    ]["failures"]
    assert "campaign_execution_marker_after_campaign" in report[
        "campaign_execution_marker_failure_reasons"
    ]


def test_launch_readiness_rejects_campaign_execution_marker_before_preflight_exit(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    marker_start = run_text.index("CAMPAIGN_EXECUTION_MARKER_STARTED_AT=")
    campaign_start = run_text.index(f"{sys.executable} -m scion.cli.main run")
    marker_block = run_text[marker_start:campaign_start]
    run_text = run_text[:marker_start] + run_text[campaign_start:]
    insert_after = "    --json || PREFLIGHT_STATUS=$?\n"
    run_text = run_text.replace(insert_after, insert_after + marker_block, 1)
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    marker_check = report["checks"]["run_script_campaign_execution_marker_enforced"]
    assert marker_check["status"] == "failed"
    assert report["campaign_execution_marker_status"] == "failed"
    assert report["campaign_execution_marker_ok"] is False
    assert {
        "reason": "campaign_execution_marker_before_preflight_failure_exit"
    } in marker_check["detail"]["failures"]
    assert "campaign_execution_marker_before_preflight_failure_exit" in report[
        "campaign_execution_marker_failure_reasons"
    ]


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


def test_launch_readiness_rejects_missing_cvrp_code_constraint_provider_payload(
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
    payload["signals"]["cvrp_active_subject_code_constraints_prompt_bridge"][
        "detail"
    ].pop("provider_payload")
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"]
        == "cvrp_active_subject_code_constraints_bridge_provider_payload_missing"
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_stale_cvrp_code_constraint_provider_payload(
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
    provider_payload = payload["signals"][
        "cvrp_active_subject_code_constraints_prompt_bridge"
    ]["detail"]["provider_payload"]
    provider_payload["constraint_count"] = 0
    provider_payload["total_guidance_item_count"] = 11
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"]
        == "cvrp_active_subject_code_constraints_bridge_provider_payload_field_mismatch"
        and failure["field"] == "constraint_count"
        and failure["expected"] == 2
        and failure["actual"] == 0
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_missing_cvrp_code_constraint_prompt_summary(
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
    payload["signals"]["cvrp_active_subject_code_constraints_prompt_bridge"][
        "detail"
    ].pop("code_prompt_summary")
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"]
        == "cvrp_active_subject_code_constraints_bridge_code_prompt_summary_missing"
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_stale_cvrp_code_constraint_prompt_summary(
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
    code_summary = payload["signals"][
        "cvrp_active_subject_code_constraints_prompt_bridge"
    ]["detail"]["code_prompt_summary"]
    code_summary["large_twoopt_runtime_guard_present"] = False
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"]
        == "cvrp_active_subject_code_constraints_bridge_code_prompt_summary_field_mismatch"
        and failure["field"] == "large_twoopt_runtime_guard_present"
        and failure["expected"] is True
        and failure["actual"] is False
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_missing_cvrp_problem_measurement_diagnostics_bridge(
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
    payload["signals"].pop("cvrp_problem_measurement_diagnostics_prompt_bridge")
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"] == "cvrp_problem_measurement_diagnostics_bridge_missing"
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_stale_cvrp_problem_measurement_diagnostics_summary(
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
    diagnostic_summary = payload["signals"][
        "cvrp_problem_measurement_diagnostics_prompt_bridge"
    ]["detail"]["diagnostic_summary"]
    diagnostic_summary["mechanism_rank_count"] = 0
    diagnostic_summary["mechanism_effect_ranking_present"] = False
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"]
        == (
            "cvrp_problem_measurement_diagnostics_bridge_"
            "diagnostic_summary_field_mismatch"
        )
        and failure["field"] == "mechanism_rank_count"
        and failure["expected"] > 0
        and failure["actual"] == 0
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_missing_warehouse_problem_measurement_diagnostics_bridge(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(
        tmp_path,
        problem_family="warehouse_delivery",
        research_focus=_warehouse_research_focus(),
    )
    artifact_path = (
        run_root
        / "prepared_handoff"
        / "prompt_context_readiness"
        / "cvrp_on_full.prepared_prompt_context_readiness.v1.json"
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["signals"].pop("warehouse_problem_measurement_diagnostics_prompt_bridge")
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"]
        == "warehouse_problem_measurement_diagnostics_bridge_missing"
        for failure in prompt_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_stale_warehouse_problem_measurement_diagnostics_summary(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(
        tmp_path,
        problem_family="warehouse_delivery",
        research_focus=_warehouse_research_focus(),
    )
    artifact_path = (
        run_root
        / "prepared_handoff"
        / "prompt_context_readiness"
        / "cvrp_on_full.prepared_prompt_context_readiness.v1.json"
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    diagnostic_summary = payload["signals"][
        "warehouse_problem_measurement_diagnostics_prompt_bridge"
    ]["detail"]["diagnostic_summary"]
    diagnostic_summary["warehouse_plateau_guard_present"] = False
    diagnostic_summary["opportunity_diagnostic_count"] = 0
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    prompt_check = report["checks"]["prompt_context_readiness_complete"]
    assert prompt_check["status"] == "failed"
    assert any(
        failure["reason"]
        == (
            "warehouse_problem_measurement_diagnostics_bridge_"
            "diagnostic_summary_field_mismatch"
        )
        and failure["field"] == "warehouse_plateau_guard_present"
        and failure["expected"] is True
        and failure["actual"] is False
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
        return "failed", {
            "auth_status": {
                "authenticated": False,
                "pool": {"active": 0, "total": 1, "expired": 1},
            },
            "chat": {
                "http_status": 401,
                "classification": "not_authenticated",
                "code": "invalid_api_key",
                "message": "Not authenticated.",
            },
            "operator_action": {
                "classification": "not_authenticated",
                "model": "gpt-5.5",
                "base_url": "http://127.0.0.1:8080",
                "next_step": "Refresh the local proxy login.",
                "login_url": "http://127.0.0.1:8080/auth/login",
            },
        }

    monkeypatch.setattr(
        readiness_tool,
        "_completion_preflight_check",
        fail_preflight,
    )

    report = readiness_tool.build_readiness(run_root, completion_preflight=True)

    assert report["ready"] is False
    assert report["static_ready"] is True
    assert report["launch_ready"] is False
    assert report["failed_required_checks"] == ["completion_preflight"]
    assert report["failed_static_required_checks"] == []
    assert report["checks"]["completion_preflight"]["status"] == "failed"
    assert report["completion_preflight_summary"]["status"] == "failed"
    assert report["completion_preflight_summary"]["required"] is True
    assert report["completion_preflight_summary"]["ok"] is False
    assert report["completion_preflight_summary"]["http_status"] == 401
    assert report["completion_preflight_summary"]["classification"] == (
        "not_authenticated"
    )
    assert report["completion_preflight_summary"]["code"] == "invalid_api_key"
    assert report["completion_preflight_summary"]["auth_pool"] == {
        "active": 0,
        "total": 1,
        "expired": 1,
    }
    assert report["completion_http_status"] == 401
    assert report["completion_classification"] == "not_authenticated"
    assert report["completion_code"] == "invalid_api_key"
    assert report["completion_auth_pool"] == {
        "active": 0,
        "total": 1,
        "expired": 1,
    }
    assert report["completion_login_url"] == "http://127.0.0.1:8080/auth/login"
    assert report["completion_next_step"] == "Refresh the local proxy login."
    assert report["completion_operator_action"] == {
        "classification": "not_authenticated",
        "model": "gpt-5.5",
        "base_url": "http://127.0.0.1:8080",
        "next_step": "Refresh the local proxy login.",
        "login_url": "http://127.0.0.1:8080/auth/login",
    }


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
    rebuild_check = report["checks"]["run_script_strict_postrun_rebuild"]
    preflight_failure_check = report["checks"]["run_script_preflight_failure_reports"]
    runtime_failure_check = report["checks"][
        "run_script_runtime_guard_failure_reports"
    ]
    assert strict_check["status"] == "failed"
    assert rebuild_check["status"] == "failed"
    assert {"reason": "missing_postrun_report_function"} in strict_check["detail"][
        "failures"
    ]
    assert {"reason": "missing_postrun_report_function"} in rebuild_check["detail"][
        "failures"
    ]
    assert strict_check["detail"][
        "ignored_non_executable_function_definition_count"
    ] == 1
    assert rebuild_check["detail"][
        "ignored_non_executable_function_definition_count"
    ] == 1
    assert preflight_failure_check["status"] == "failed"
    assert {"reason": "missing_postrun_report_function"} in preflight_failure_check[
        "detail"
    ]["failures"]
    assert preflight_failure_check["detail"][
        "ignored_non_executable_function_definition_count"
    ] == 1
    assert runtime_failure_check["status"] == "failed"
    assert {"reason": "missing_postrun_report_function"} in (
        runtime_failure_check["detail"]["failures"]
    )


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


def test_launch_readiness_rejects_run_script_without_strict_postrun_rebuild(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            "    --strict >> \"$RUN_ROOT/run.log\" 2>&1 || POSTRUN_REBUILD_STATUS=$?\n",
            "",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    rebuild_check = report["checks"]["run_script_strict_postrun_rebuild"]
    assert rebuild_check["required"] is True
    assert rebuild_check["status"] == "failed"
    assert {"reason": "postrun_rebuild_strict_flag_missing"} in rebuild_check[
        "detail"
    ]["failures"]


def test_launch_readiness_rejects_comment_only_strict_postrun_rebuild(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    run_text = run_text.replace(
        "tools/rebuild_postrun_acceptance.py",
        "tools/rebuild_postrun_acceptance_disabled.py",
        1,
    )
    run_text = run_text.replace(
        "write_postrun_acceptance_reports() {\n",
        "write_postrun_acceptance_reports() {\n"
        "  # tools/rebuild_postrun_acceptance.py --strict\n",
        1,
    )
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    rebuild_check = report["checks"]["run_script_strict_postrun_rebuild"]
    assert rebuild_check["required"] is True
    assert rebuild_check["status"] == "failed"
    assert {"reason": "postrun_rebuild_command_missing"} in rebuild_check[
        "detail"
    ]["failures"]


def test_launch_readiness_rejects_postrun_rebuild_after_readiness(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_text = run_sh.read_text(encoding="utf-8")
    rebuild_start = run_text.index(
        '  "$PY" "$SCION_DIR/tools/rebuild_postrun_acceptance.py"'
    )
    rebuild_end = run_text.index(
        '  echo "POSTRUN_REPORTS_EXIT_STATUS:${POSTRUN_REBUILD_STATUS:-0}"',
        rebuild_start,
    )
    rebuild_end = run_text.index("\n", rebuild_end) + 1
    readiness_start = run_text.index(
        '  "$PY" "$SCION_DIR/tools/check_postrun_acceptance.py"'
    )
    readiness_end = run_text.index(
        '  echo "POSTRUN_READINESS_EXIT_STATUS:$POSTRUN_READINESS_STATUS"',
        readiness_start,
    )
    readiness_end = run_text.index("\n", readiness_end) + 1
    rebuild_block = run_text[rebuild_start:rebuild_end]
    readiness_block = run_text[readiness_start:readiness_end]
    run_text = (
        run_text[:rebuild_start]
        + readiness_block
        + rebuild_block
        + run_text[rebuild_end:readiness_start]
        + run_text[readiness_end:]
    )
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    rebuild_check = report["checks"]["run_script_strict_postrun_rebuild"]
    assert rebuild_check["required"] is True
    assert rebuild_check["status"] == "failed"
    assert {"reason": "postrun_rebuild_after_readiness"} in rebuild_check[
        "detail"
    ]["failures"]


def test_launch_readiness_rejects_postrun_status_marker_before_rebuild(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    marker = '  echo "POSTRUN_REPORTS_EXIT_STATUS:${POSTRUN_REBUILD_STATUS:-0}" >> "$RUN_ROOT/run.log"\n'
    run_text = run_sh.read_text(encoding="utf-8")
    run_text = run_text.replace(marker, "", 1)
    run_text = run_text.replace(
        "write_postrun_acceptance_reports() {\n",
        "write_postrun_acceptance_reports() {\n" + marker,
        1,
    )
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    rebuild_check = report["checks"]["run_script_strict_postrun_rebuild"]
    assert rebuild_check["required"] is True
    assert rebuild_check["status"] == "failed"
    assert {"reason": "postrun_reports_exit_status_before_rebuild"} in (
        rebuild_check["detail"]["failures"]
    )


def test_launch_readiness_rejects_postrun_readiness_marker_before_readiness(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    marker = (
        '    echo "POSTRUN_READINESS_EXIT_STATUS:$POSTRUN_READINESS_STATUS"\n'
    )
    run_text = run_sh.read_text(encoding="utf-8")
    run_text = run_text.replace(marker, "", 1)
    run_text = run_text.replace(
        "write_postrun_acceptance_reports() {\n",
        "write_postrun_acceptance_reports() {\n" + marker,
        1,
    )
    run_sh.write_text(run_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    strict_check = report["checks"]["run_script_strict_postrun_readiness"]
    assert strict_check["required"] is True
    assert strict_check["status"] == "failed"
    assert {"reason": "postrun_readiness_exit_status_before_readiness"} in (
        strict_check["detail"]["failures"]
    )


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
            "write_postrun_acceptance_reports || POSTRUN_ACCEPTANCE_STATUS=$?\n",
            "",
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


def test_launch_readiness_rejects_postrun_without_wrapper_status_writer(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            "tools/write_postrun_wrapper_status.py",
            "tools/write_postrun_wrapper_status_disabled.py",
            1,
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)
    postrun_check = report["checks"]["run_script_postrun_reports_after_campaign"]

    assert report["ready"] is False
    assert report["static_ready"] is False
    assert postrun_check["required"] is True
    assert postrun_check["status"] == "failed"
    assert {"reason": "missing_postrun_wrapper_status_writer"} in postrun_check[
        "detail"
    ]["failures"]


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


def test_launch_readiness_rejects_relative_scion_dir_pythonpath(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        launch_env.read_text(encoding="utf-8")
        .replace(f"SCION_DIR={SCION_DIR}", "SCION_DIR=scion")
        .replace(f"PYTHONPATH={SCION_DIR}", "PYTHONPATH=scion"),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    pythonpath_check = report["checks"]["run_script_pythonpath_enforced"]
    assert pythonpath_check["status"] == "failed"
    assert {
        "reason": "scion_dir_not_absolute",
        "launch_env": str(launch_env),
        "scion_dir": "scion",
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


def test_launch_readiness_rejects_launch_env_campaign_contract_mismatch(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    other_problem = run_root / "config" / "other_problem.yaml"
    other_problem.write_text("ok: false\n", encoding="utf-8")
    launch_env.write_text(
        launch_env.read_text(encoding="utf-8").replace(
            f"PROBLEM={run_root / 'config' / 'problem.yaml'}",
            f"PROBLEM={other_problem}",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    contract_check = report["checks"]["run_script_campaign_contract_consistency"]
    assert contract_check["status"] == "failed"
    assert {
        "reason": "problem_launch_env_manifest_mismatch",
        "expected": str(run_root / "config" / "problem.yaml"),
        "actual": str(other_problem),
    } in contract_check["detail"]["failures"]


def test_launch_readiness_rejects_run_script_campaign_option_drift(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    other_split = run_root / "config" / "other_split.yaml"
    other_split.write_text("ok: false\n", encoding="utf-8")
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            f"--split {run_root / 'config' / 'split.yaml'}",
            f"--split {other_split}",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    contract_check = report["checks"]["run_script_campaign_contract_consistency"]
    assert contract_check["status"] == "failed"
    failures = contract_check["detail"]["failures"]
    assert any(
        failure.get("reason") == "split_run_script_option_mismatch"
        and failure.get("actual") == str(other_split)
        for failure in failures
    )


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


def test_launch_readiness_rejects_missing_proposal_headroom_env(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        "\n".join(
            line
            for line in launch_env.read_text(encoding="utf-8").splitlines()
            if not line.startswith("PROPOSAL_ATTEMPT_LIMIT=")
        )
        + "\n",
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    headroom_check = report["checks"]["run_script_proposal_headroom_enforced"]
    assert headroom_check["status"] == "failed"
    assert {
        "reason": "proposal_attempt_limit_launch_env_missing_or_invalid",
        "field": "proposal_attempt_limit",
        "source": "launch_env",
        "expected_min": 64,
        "actual": None,
    } in headroom_check["detail"]["failures"]


def test_launch_readiness_rejects_missing_fresh_runtime_replay_drain_env(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        "\n".join(
            line
            for line in launch_env.read_text(encoding="utf-8").splitlines()
            if not line.startswith("SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT=")
        )
        + "\n",
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    headroom_check = report["checks"]["run_script_proposal_headroom_enforced"]
    assert headroom_check["status"] == "failed"
    assert {
        "reason": (
            "fresh_runtime_replay_drain_limit_launch_env_missing_or_invalid"
        ),
        "field": "fresh_runtime_replay_drain_limit",
        "source": "launch_env",
        "expected_min": 1,
        "actual": None,
    } in headroom_check["detail"]["failures"]


def test_launch_readiness_rejects_missing_stage_transition_drain_env(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        "\n".join(
            line
            for line in launch_env.read_text(encoding="utf-8").splitlines()
            if not line.startswith("SCION_STAGE_TRANSITION_DRAIN_LIMIT=")
        )
        + "\n",
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    headroom_check = report["checks"]["run_script_proposal_headroom_enforced"]
    assert headroom_check["status"] == "failed"
    assert {
        "reason": "stage_transition_drain_limit_launch_env_missing_or_invalid",
        "field": "stage_transition_drain_limit",
        "source": "launch_env",
        "expected_min": 1,
        "actual": None,
    } in headroom_check["detail"]["failures"]


def test_launch_readiness_rejects_low_manifest_proposal_headroom(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["execution"]["proposal_quality_loop_limit"] = 7
    manifest["command"] = manifest["command"].replace(
        "--proposal-quality-loop-limit 64",
        "--proposal-quality-loop-limit 7",
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    headroom_check = report["checks"]["run_script_proposal_headroom_enforced"]
    assert headroom_check["status"] == "failed"
    failures = headroom_check["detail"]["failures"]
    assert {
        "reason": "proposal_quality_loop_limit_manifest_execution_below_minimum",
        "field": "proposal_quality_loop_limit",
        "source": "manifest_execution",
        "recommended_min": 64,
        "actual": 7,
    } in failures
    assert {
        "reason": "proposal_quality_loop_limit_manifest_command_below_minimum",
        "field": "proposal_quality_loop_limit",
        "source": "manifest_command",
        "recommended_min": 64,
        "actual": 7,
    } in failures


def test_launch_readiness_accepts_disabled_proposal_headroom_caps(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["execution"]["proposal_attempt_limit"] = 0
    manifest["execution"]["proposal_quality_loop_limit"] = 0
    manifest["command"] = manifest["command"].replace(
        "--proposal-attempt-limit 64",
        "--proposal-attempt-limit 0",
    )
    manifest["command"] = manifest["command"].replace(
        "--proposal-quality-loop-limit 64",
        "--proposal-quality-loop-limit 0",
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        launch_env.read_text(encoding="utf-8")
        .replace("PROPOSAL_ATTEMPT_LIMIT=64", "PROPOSAL_ATTEMPT_LIMIT=0")
        .replace(
            "PROPOSAL_QUALITY_LOOP_LIMIT=64",
            "PROPOSAL_QUALITY_LOOP_LIMIT=0",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    headroom_check = report["checks"]["run_script_proposal_headroom_enforced"]
    assert headroom_check["status"] == "ok"
    assert headroom_check["detail"]["failures"] == []
    assert headroom_check["detail"]["warnings"] == []
    disabled = headroom_check["detail"]["disabled"]
    assert {
        "field": "proposal_attempt_limit",
        "source": "launch_env",
        "actual": 0,
        "semantic": "disabled",
    } in disabled
    assert {
        "field": "proposal_quality_loop_limit",
        "source": "manifest_execution",
        "actual": 0,
        "semantic": "disabled",
    } in disabled
    assert {
        "field": "fresh_runtime_replay_drain_limit",
        "source": "launch_env",
        "actual": 0,
        "semantic": "disabled",
    } in disabled


def test_launch_readiness_rejects_missing_agentic_tool_headroom_env(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    launch_env = run_root / "launch.env"
    launch_env.write_text(
        "\n".join(
            line
            for line in launch_env.read_text(encoding="utf-8").splitlines()
            if not line.startswith("AGENTIC_TOOL_MAX_CALLS=")
        )
        + "\n",
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    headroom_check = report["checks"]["run_script_proposal_headroom_enforced"]
    assert headroom_check["status"] == "failed"
    assert {
        "reason": "agentic_tool_max_calls_launch_env_missing_or_invalid",
        "field": "agentic_tool_max_calls",
        "source": "launch_env",
        "expected_min": 200,
        "actual": None,
    } in headroom_check["detail"]["failures"]


def test_launch_readiness_rejects_low_manifest_agentic_tool_headroom(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["execution"]["agentic_tool_max_steps"] = 24
    manifest["command"] = manifest["command"].replace(
        "--agentic-tool-max-steps 240",
        "--agentic-tool-max-steps 24",
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    headroom_check = report["checks"]["run_script_proposal_headroom_enforced"]
    assert headroom_check["status"] == "failed"
    failures = headroom_check["detail"]["failures"]
    assert {
        "reason": "agentic_tool_max_steps_manifest_execution_below_minimum",
        "field": "agentic_tool_max_steps",
        "source": "manifest_execution",
        "recommended_min": 240,
        "actual": 24,
    } in failures
    assert {
        "reason": "agentic_tool_max_steps_manifest_command_below_minimum",
        "field": "agentic_tool_max_steps",
        "source": "manifest_command",
        "recommended_min": 240,
        "actual": 24,
    } in failures


def test_launch_readiness_accepts_disabled_agentic_tool_headroom_caps(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    replacements = {
        "agentic_tool_max_steps": (
            "AGENTIC_TOOL_MAX_STEPS",
            "--agentic-tool-max-steps",
            "240",
        ),
        "agentic_tool_max_calls": (
            "AGENTIC_TOOL_MAX_CALLS",
            "--agentic-tool-max-calls",
            "200",
        ),
        "agentic_code_tool_max_calls": (
            "AGENTIC_CODE_TOOL_MAX_CALLS",
            "--agentic-code-tool-max-calls",
            "200",
        ),
        "agentic_observation_max_chars": (
            "AGENTIC_OBSERVATION_MAX_CHARS",
            "--agentic-observation-max-chars",
            "2000000",
        ),
    }
    launch_env_text = (run_root / "launch.env").read_text(encoding="utf-8")
    for field, (env_key, option, old_value) in replacements.items():
        manifest["execution"][field] = 0
        manifest["command"] = manifest["command"].replace(
            f"{option} {old_value}",
            f"{option} 0",
        )
        launch_env_text = launch_env_text.replace(
            f"{env_key}={old_value}",
            f"{env_key}=0",
        )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (run_root / "launch.env").write_text(launch_env_text, encoding="utf-8")

    report = readiness_tool.build_readiness(run_root)

    headroom_check = report["checks"]["run_script_proposal_headroom_enforced"]
    assert headroom_check["status"] == "ok"
    assert headroom_check["detail"]["failures"] == []
    assert headroom_check["detail"]["warnings"] == []
    disabled = headroom_check["detail"]["disabled"]
    assert {
        "field": "agentic_tool_max_steps",
        "source": "launch_env",
        "actual": 0,
        "semantic": "disabled",
    } in disabled
    assert {
        "field": "agentic_observation_max_chars",
        "source": "manifest_execution",
        "actual": 0,
        "semantic": "disabled",
    } in disabled


def test_launch_readiness_rejects_run_script_without_proposal_headroom_flags(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(tmp_path)
    run_sh = run_root / "run.sh"
    run_sh.write_text(
        run_sh.read_text(encoding="utf-8").replace(
            ' --proposal-attempt-limit "$PROPOSAL_ATTEMPT_LIMIT"'
            ' --proposal-quality-loop-limit "$PROPOSAL_QUALITY_LOOP_LIMIT"',
            "",
        ),
        encoding="utf-8",
    )

    report = readiness_tool.build_readiness(run_root)

    assert report["ready"] is False
    assert report["static_ready"] is False
    headroom_check = report["checks"]["run_script_proposal_headroom_enforced"]
    assert headroom_check["status"] == "failed"
    failures = headroom_check["detail"]["failures"]
    assert {
        "reason": "proposal_attempt_limit_run_script_campaign_command_missing_env",
        "field": "proposal_attempt_limit",
        "option": "--proposal-attempt-limit",
        "expected_env": "PROPOSAL_ATTEMPT_LIMIT",
        "run_script": str(run_sh),
    } in failures
    assert {
        "reason": "proposal_quality_loop_limit_run_script_campaign_command_missing_env",
        "field": "proposal_quality_loop_limit",
        "option": "--proposal-quality-loop-limit",
        "expected_env": "PROPOSAL_QUALITY_LOOP_LIMIT",
        "run_script": str(run_sh),
    } in failures


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


def test_launch_readiness_cli_uses_current_checkout_without_pythonpath(
    tmp_path: Path,
) -> None:
    run_root = _write_prepared_root(
        tmp_path,
        problem_family="warehouse_delivery",
        research_focus=_warehouse_research_focus(),
        runtime_guard_paths="scion/scion :(exclude)scion/scion/tests",
    )
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, str(TOOL_PATH), str(run_root), "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert result.returncode in (0, 64), result.stderr
    assert payload["checks"]["prompt_context_readiness_complete"]["status"] == "ok"


def test_launch_readiness_cli_require_launch_ready_implies_completion_preflight(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_root = _write_prepared_root(tmp_path)

    def fail_preflight(**_: object) -> tuple[str, object]:
        return "failed", {
            "chat": {
                "http_status": 401,
                "classification": "not_authenticated",
                "code": "invalid_api_key",
            },
            "auth_status": {"pool": {"active": 0, "total": 1}},
            "operator_action": {
                "classification": "not_authenticated",
                "next_step": "Refresh the local proxy login.",
                "login_url": "http://127.0.0.1:8080/auth/login",
            },
        }

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
    assert payload["readiness_scope"] == "launch_with_completion_preflight"
    assert payload["static_ready"] is True
    assert payload["launch_ready"] is False
    assert payload["ready"] is False
    assert payload["ready_meaning"] == (
        "launch readiness because completion preflight was required"
    )
    assert payload["launch_blockers"] == ["completion_preflight"]
    assert payload["failed_required_checks"] == ["completion_preflight"]
    assert payload["failed_static_required_checks"] == []
    assert payload["checks"]["completion_preflight"]["status"] == "failed"
    assert payload["completion_preflight_summary"]["http_status"] == 401
    assert payload["completion_preflight_summary"]["classification"] == (
        "not_authenticated"
    )
    assert payload["completion_preflight_summary"]["code"] == "invalid_api_key"
    assert payload["completion_preflight_summary"]["auth_pool"] == {
        "active": 0,
        "total": 1,
    }
    assert payload["completion_http_status"] == 401
    assert payload["completion_classification"] == "not_authenticated"
    assert payload["completion_code"] == "invalid_api_key"
    assert payload["completion_login_url"] == "http://127.0.0.1:8080/auth/login"
    assert payload["completion_next_step"] == "Refresh the local proxy login."
    assert payload["campaign_execution_marker_status"] == "ok"
    assert payload["campaign_execution_marker_ok"] is True
    assert payload["campaign_execution_marker_failure_reasons"] == []


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
    assert payload["readiness_scope"] == "launch_with_completion_preflight"
    assert payload["static_ready"] is True
    assert payload["launch_ready"] is True
    assert payload["ready"] is True
    assert payload["launch_blockers"] == []
    assert payload["checks"]["completion_preflight"]["status"] == "ok"
    assert payload["completion_preflight_summary"]["status"] == "ok"
    assert payload["completion_preflight_summary"]["ok"] is True
    assert payload["completion_http_status"] == 200
    assert payload["completion_login_url"] is None
    assert payload["completion_next_step"] is None
    assert payload["completion_operator_action"] is None


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

    command = (
        f"{sys.executable} -m scion.cli.main run "
        f"--problem {config_dir / 'problem.yaml'} "
        f"--protocol {config_dir / 'protocol.yaml'} "
        f"--split {config_dir / 'split.yaml'} "
        f"--seeds {config_dir / 'seeds.yaml'} "
        f"--campaign-dir {campaign_dir} --rounds 1 "
        "--time-limit-sec 30 "
        "--agentic-session-timeout-sec 3600 "
        "--agentic-tool-max-steps 240 "
        "--agentic-tool-max-calls 200 "
        "--agentic-code-tool-max-calls 200 "
        "--agentic-observation-max-chars 2000000 "
        "--proposal-attempt-limit 64 --proposal-quality-loop-limit 64 "
        "--fresh-runtime-replay-drain-limit 0 "
        "--stage-transition-drain-limit 4 "
        "--measurement-governance on --proposal-context-ablation full "
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
            "agentic_session_timeout_sec": 3600,
            "agentic_tool_max_steps": 240,
            "agentic_tool_max_calls": 200,
            "agentic_code_tool_max_calls": 200,
            "agentic_observation_max_chars": 2000000,
            "proposal_attempt_limit": 64,
            "proposal_quality_loop_limit": 64,
            "fresh_runtime_replay_drain_limit": 0,
            "stage_transition_drain_limit": 4,
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
        focus = research_focus if research_focus is not None else _cvrp_research_focus()
        manifest["research_focus"] = focus
        manifest["research_guidance_contract"] = research_guidance_contract_to_dict(
            legacy_research_focus_to_contract(
                focus,
                problem_family=problem_family,
            )
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
                f"RUN_ROOT={run_root}",
                f"CAMPAIGN_DIR={campaign_dir}",
                f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}",
                f"SCION_DIR={SCION_DIR}",
                f"PYTHONPATH={SCION_DIR}",
                "SCION_MODEL=gpt-5.5",
                "SCION_BASE_URL=http://127.0.0.1:8080",
                "COMPLETION_PREFLIGHT=1",
                f"PROBLEM={config_dir / 'problem.yaml'}",
                f"PROTOCOL={config_dir / 'protocol.yaml'}",
                f"SPLIT={config_dir / 'split.yaml'}",
                f"SEEDS={config_dir / 'seeds.yaml'}",
                "ROUNDS=1",
                "TIME_LIMIT_SEC=30",
                "MEASUREMENT_GOVERNANCE=on",
                "PROPOSAL_CONTEXT_ABLATION=full",
                "AGENTIC_SESSION_TIMEOUT_SEC=3600",
                "AGENTIC_TOOL_MAX_STEPS=240",
                "AGENTIC_TOOL_MAX_CALLS=200",
                "AGENTIC_CODE_TOOL_MAX_CALLS=200",
                "AGENTIC_OBSERVATION_MAX_CHARS=2000000",
                "PROPOSAL_ATTEMPT_LIMIT=64",
                "PROPOSAL_QUALITY_LOOP_LIMIT=64",
                "SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT=0",
                "SCION_STAGE_TRANSITION_DRAIN_LIMIT=4",
                "DISABLE_EARLY_STOP=1",
                f"GIT_COMMIT={_git_head_short()}",
                f"GIT_RUNTIME_GUARD_PATHS={json.dumps(runtime_guard_paths)}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (run_root / "launch.env").chmod(0o600)
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
  POSTRUN_REBUILD_STATUS=0
  POSTRUN_READINESS_STATUS=0
  "$PY" "$SCION_DIR/tools/rebuild_postrun_acceptance.py" "$RUN_ROOT" \
    --report-stem fixture \
    --strict >> "$RUN_ROOT/run.log" 2>&1 || POSTRUN_REBUILD_STATUS=$?
  echo "POSTRUN_REPORTS_EXIT_STATUS:${{POSTRUN_REBUILD_STATUS:-0}}" >> "$RUN_ROOT/run.log"
  "$PY" "$SCION_DIR/tools/check_postrun_acceptance.py" "$RUN_ROOT" \
    --require-current-run-ready \
    --format json \
    > "$RUN_ROOT/postrun_acceptance/readiness/fixture.postrun_acceptance_readiness.v1.json" \
    || POSTRUN_READINESS_STATUS=$?
  echo "POSTRUN_READINESS_EXIT_STATUS:$POSTRUN_READINESS_STATUS" >> "$RUN_ROOT/run.log"
  if [[ "$POSTRUN_REBUILD_STATUS" -ne 0 ]]; then
    return "$POSTRUN_REBUILD_STATUS"
  fi
  if [[ "$POSTRUN_READINESS_STATUS" -ne 0 ]]; then
    return "$POSTRUN_READINESS_STATUS"
  fi
  return 0
}}
if [[ ! -r "$RUN_ROOT/launch.env" ]]; then
  echo "LAUNCH_ENV_MISSING:$RUN_ROOT/launch.env"
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":64,"launch_env_missing":"%s"}}\\n' "$RUN_ROOT/launch.env" > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit 64
fi
if ! cd "$SCION_DIR"; then
  echo "SCION_DIR_MISSING:$SCION_DIR"
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":64,"scion_dir_missing":"%s"}}\\n' "$SCION_DIR" > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit 64
fi
read -r -a _GIT_RUNTIME_GUARD_PATHS <<< "$GIT_RUNTIME_GUARD_PATHS"
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain -- "${{_GIT_RUNTIME_GUARD_PATHS[@]}}")" ]]; then
  echo "GIT_RUNTIME_DIRTY:$GIT_RUNTIME_GUARD_PATHS"
  printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":64,"git_runtime_dirty":true}}\\n' > "$RUN_ROOT/run_status.json"
  write_postrun_acceptance_reports
  exit 64
fi
_ACTUAL_GIT_COMMIT="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
if [[ "$_ACTUAL_GIT_COMMIT" != "$GIT_COMMIT" ]]; then
  if git -C "$REPO_ROOT" diff --quiet "$GIT_COMMIT" HEAD -- "${{_GIT_RUNTIME_GUARD_PATHS[@]}}"; then
    echo "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED:expected=$GIT_COMMIT actual=$_ACTUAL_GIT_COMMIT paths=$GIT_RUNTIME_GUARD_PATHS"
  else
    echo "GIT_COMMIT_MISMATCH:expected=$GIT_COMMIT actual=$_ACTUAL_GIT_COMMIT paths=$GIT_RUNTIME_GUARD_PATHS"
    printf '{{"schema":"outer-wrapper.v1","status":"finished","wrapper_exit_status":64,"git_runtime_commit_mismatch":true}}\\n' > "$RUN_ROOT/run_status.json"
    write_postrun_acceptance_reports
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
CAMPAIGN_EXECUTION_MARKER_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '{{"schema":"scion.launcher_campaign_execution_marker.v1","started_at":"%s","run_root":"%s","campaign_dir":"%s"}}\n' \
  "$CAMPAIGN_EXECUTION_MARKER_STARTED_AT" "$RUN_ROOT" "$CAMPAIGN_DIR" \
  > "$RUN_ROOT/campaign_execution_marker.v1.json"
echo "CAMPAIGN_EXECUTION_MARKER:$RUN_ROOT/campaign_execution_marker.v1.json" >> "$RUN_ROOT/run.log"
{sys.executable} -m scion.cli.main run --problem {config_dir / 'problem.yaml'} --protocol {config_dir / 'protocol.yaml'} --split {config_dir / 'split.yaml'} --seeds {config_dir / 'seeds.yaml'} --campaign-dir {campaign_dir} --rounds 1 --time-limit-sec 30 --agentic-session-timeout-sec "$AGENTIC_SESSION_TIMEOUT_SEC" --agentic-tool-max-steps "$AGENTIC_TOOL_MAX_STEPS" --agentic-tool-max-calls "$AGENTIC_TOOL_MAX_CALLS" --agentic-code-tool-max-calls "$AGENTIC_CODE_TOOL_MAX_CALLS" --agentic-observation-max-chars "$AGENTIC_OBSERVATION_MAX_CHARS" --proposal-attempt-limit "$PROPOSAL_ATTEMPT_LIMIT" --proposal-quality-loop-limit "$PROPOSAL_QUALITY_LOOP_LIMIT" --fresh-runtime-replay-drain-limit "$SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT" --stage-transition-drain-limit "$SCION_STAGE_TRANSITION_DRAIN_LIMIT" --measurement-governance "$MEASUREMENT_GOVERNANCE" --proposal-context-ablation "$PROPOSAL_CONTEXT_ABLATION" --agentic-proposal --disable-early-stop
STATUS=$?
CAMPAIGN_STATUS=$STATUS
POSTRUN_ACCEPTANCE_STATUS=0
write_postrun_acceptance_reports || POSTRUN_ACCEPTANCE_STATUS=$?
if [[ "$POSTRUN_ACCEPTANCE_STATUS" -ne 0 ]]; then
  echo "POSTRUN_ACCEPTANCE_FAILED:$POSTRUN_ACCEPTANCE_STATUS" >> "$RUN_ROOT/exit.txt"
  if [[ "$STATUS" -eq 0 ]]; then
    STATUS="$POSTRUN_ACCEPTANCE_STATUS"
    echo "WRAPPER_EXIT_STATUS_EFFECTIVE:$STATUS" >> "$RUN_ROOT/exit.txt"
  fi
fi
"$PY" "$SCION_DIR/tools/write_postrun_wrapper_status.py" \
  --output "$RUN_ROOT/run_status.json" \
  --wrapper-exit-code "$STATUS" \
  --campaign-exit-code "$CAMPAIGN_STATUS" \
  --postrun-reports-exit-code "$POSTRUN_REBUILD_STATUS" \
  --postrun-readiness-exit-code "$POSTRUN_READINESS_STATUS" \
  --postrun-report-dir "$RUN_ROOT/postrun_acceptance" \
  --postrun-readiness-path "$RUN_ROOT/postrun_acceptance/readiness/fixture.postrun_acceptance_readiness.v1.json"
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
    _write_prepared_handoff_rebuild_manifest(run_root)
    return run_root


def _write_prepared_handoff_rebuild_manifest(run_root: Path) -> None:
    manifest = json.loads(
        (run_root / "prepared_run_manifest.v1.json").read_text(encoding="utf-8")
    )
    handoff_dir = run_root / "prepared_handoff"
    stem = _prepared_report_stem(str(manifest["problem_family"]))
    _write_json(
        handoff_dir
        / "inventory"
        / f"{stem}.prepared_artifact_inventory.v1.json",
        readiness_tool.build_inventory(run_root),
    )
    (
        handoff_dir
        / "inventory"
        / f"{stem}.prepared_artifact_inventory.md"
    ).write_text("# prepared inventory\n", encoding="utf-8")
    _write_json(
        handoff_dir
        / "launch_readiness"
        / f"{stem}.prepared_launch_readiness.v1.json",
        {"schema_version": "scion.launch_readiness.v1", "report_only": True},
    )
    (
        handoff_dir
        / "launch_readiness"
        / f"{stem}.prepared_launch_readiness.md"
    ).write_text("# launch readiness\n", encoding="utf-8")

    families = {}
    for family in (
        "analysis_brief",
        "inventory",
        "prompt_context_readiness",
        "launch_readiness",
    ):
        family_dir = handoff_dir / family
        outputs = []
        if family_dir.is_dir():
            outputs = [
                *sorted(family_dir.glob("*.json")),
                *sorted(family_dir.glob("*.md")),
            ]
        status = (
            "ok" if outputs and all(path.exists() for path in outputs) else "failed"
        )
        families[family] = {
            "status": status,
            "outputs": [str(path) for path in outputs],
            "outputs_present": {str(path): path.exists() for path in outputs},
        }

    _write_json(
        handoff_dir / "rebuild" / "prepared_handoff_rebuild.v1.json",
        {
            "schema_version": "scion.prepared_handoff_rebuild.v1",
            "artifact_kind": "prepared_handoff_rebuild",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "campaign_state_mutated": False,
            "scheduler_state_mutated": False,
            "promotion_state_mutated": False,
            "run_root": str(run_root),
            "prepared_handoff_dir": str(handoff_dir),
            "report_stem": stem,
            "problem_family": manifest["problem_family"],
            "prepared_manifest_commit": _git_head_short(),
            "checkout_commit": _git_head_short(),
            "families": families,
            "complete": all(item["status"] == "ok" for item in families.values()),
        },
    )


def _prepared_report_stem(problem_family: str) -> str:
    if problem_family == "warehouse_delivery":
        return "warehouse_on_full"
    return "cvrp_on_full"


def _default_runtime_guard_paths(problem_family: str) -> str:
    base = "scion/scion :(exclude)scion/scion/tests scion/tools"
    if problem_family == "warehouse_delivery":
        return f"{base} scion/problems/warehouse_delivery surrogate"
    return f"{base} scion/problems/cvrp vrp"


def _cvrp_research_focus() -> dict[str, object]:
    return {
        "schema_version": "scion.cvrp_research_focus.v1",
        "scope": "report_only_prepared_handoff",
        "next_required_direction": (
            "First attempt large_instance_intra_route_two_opt_seed."
        ),
        "required_mechanism_ids": [
            "large_instance_intra_route_two_opt_seed",
        ],
        "measurement_opportunity_diagnostics": {
            "schema_version": "cvrp_measurement_opportunity_handoff.v1",
            "source": "problem_v1.measurement.calibration_ref",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "metric": "total_distance",
            "unit": "raw_delta",
            "runtime_model": "budget_exhausting",
            "pairing_validity": "trajectory_divergent",
            "practical_screen_delta": 2.0,
            "practical_validate_delta": 1.0,
            "screening_mde_at_power_80": 9.9,
            "measurement_readiness": {
                "status": "ready",
                "reason_code": "ok",
                "calibration_age_days": 8,
                "calibration_max_age_days": 90,
                "n_pairs": 96,
                "mde_at_power_80": 9.9,
                "noise_band_p90_abs": 45.5,
                "effect_to_mde_ratio": 0.20202020202020202,
                "signal_to_noise_tier": "low_power",
                "decision_features_excluded": True,
                "calibration_ref": "formal/calibration/aa_noise_floor.json",
            },
            "calibration": {
                "schema": "scion.aa_noise_floor.v1",
                "ref": "formal/calibration/aa_noise_floor.json",
                "path": "/tmp/cvrp/formal/calibration/aa_noise_floor.json",
                "calibrated_at": "2026-06-11T22:03:16.746083+00:00",
                "n_pairs": 96,
                "decision_features_excluded": True,
                "source_artifact": {
                    "ref": "/tmp/cvrp/source-aa/aa_noise_floor.json",
                    "sha256": (
                        "bdba8272d4eb130200ad537b51ceaef7e50323f614ea3ae29a8247ed9a771684"
                    ),
                },
                "calibration_run": {
                    "decision_features_excluded": True,
                    "replicate_count": 3,
                    "selected_surface": "solver_design",
                    "selected_case_count": 8,
                    "selected_seed_count": 4,
                    "runtime_policy": {
                        "selected_policy": "protocol_time_limits",
                        "runner_timeout_sec": 45,
                        "uniform_time_limit_sec": 30,
                    },
                },
            },
            "opportunity_projection_source": (
                "problem_adapter.render_problem_measurement_diagnostics"
            ),
            "adapter_payload_schema": "cvrp_measurement_opportunity_diagnostic.v1",
            "screening_headroom": {
                "scope": "formal_screening_aggregate",
                "metric": "distance_gap_pct_to_reference",
                "case_count": 16,
                "gap_pct_min": 2.5,
                "gap_pct_max": 10.0,
                "case_count_gap_pct_at_least_3": 12,
                "case_details_omitted": True,
                "planning_use": "proposal-only screening headroom",
            },
            "measurable_opportunity_classes": [
                {
                    "mechanism_family": "large_instance_intra_route_two_opt_seed",
                    "required_evidence": "bounded direct objective-effect evidence",
                    "reason_codes": ["BOUNDED_DEADLINE_REQUIRED"],
                }
            ],
            "mechanism_effect_ranking": [
                {
                    "rank": 1,
                    "mechanism_family": "large_instance_intra_route_two_opt_seed",
                    "opportunity_status": "highest_current_followup",
                    "summary": "strongest current proposal seed",
                    "recommended_action": "use bounded deadline-aware two-opt",
                    "reason_codes": ["CVRP_LARGE_INSTANCE_TWO_OPT_SEED"],
                }
            ],
            "opportunity_diagnostics": [
                {
                    "diagnostic_type": "measurement_power",
                    "surface": "solver_design",
                    "mechanism_family": "all",
                    "metric": "total_distance",
                    "summary": "low-SNR proposal-only guidance",
                    "recommended_action": "prefer direct objective-effect evidence",
                    "confidence": "high",
                    "reason_codes": ["CVRP_MDE_EXCEEDS_PRACTICAL_DELTA"],
                }
            ],
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
        "case_protection_requirements": _cmt_case_protection_requirements(),
        "resume_continuity_requirements": _resume_continuity_requirements(),
        "route_merge_exception_rule": (
            "Only continue route_merge_repair when the proposal names a causal "
            "path beyond tested variants and defines direct activation-to-objective-effect evidence."
        ),
        "construction_seed_rule": (
            "Require same-run seed baseline or same-mechanism accepted delta "
            "for construction seed objective-effect claims."
        ),
        "missing_primary_telemetry_rule": (
            "If telemetry says the declared primary mechanism is "
            "not_evaluated/not_triggered or missing, treat weak_positive "
            "sparse two-opt feedback as missing primary mechanism telemetry; "
            "do not continue without active large_instance_intra_route_two_opt_seed "
            "evidence."
        ),
        "decision_boundary": (
            "This focus must not enter DecisionFeatures, Protocol gates, "
            "promotion input, or scheduler state."
        ),
    }


def _cmt_case_protection_requirements() -> dict[str, object]:
    return {
        "schema_version": "scion.cvrp_case_protection_requirements.v1",
        "scope": "proposal_only_prepared_handoff",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "protected_cases": ["CMT2", "CMT4"],
        "rules": [
            (
                "Target intent or hypothesis must name the CMT2/CMT4 "
                "protection plan before revisiting construction, route-merge, "
                "demand-slack, VNS, or share70-derived mechanisms."
            ),
            (
                "Same-branch follow-up should keep CMT2 and CMT4 in formal "
                "coverage when those cases are available."
            ),
            (
                "A materially different problem-owned solver mechanism must "
                "still explain how it avoids repeating the CMT2/CMT4 losses."
            ),
            "Do not hardcode case ids, BKS values, seeds, or split membership.",
        ],
        "required_evidence": [
            "live target-intent or hypothesis trace mentions CMT2/CMT4 protection",
            "formal screening includes CMT2 and CMT4 or records a case-selection caveat",
            "case-level total_distance deltas for CMT2 and CMT4",
        ],
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


def _resume_continuity_requirements() -> dict[str, object]:
    return {
        "schema_version": "scion.cvrp_resume_continuity_requirements.v1",
        "scope": "proposal_only_prepared_handoff",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "fallback_sources": [
            "prepared_research_focus",
            "copied_agentic_session_trace_index",
            "copied_target_intent_or_hypothesis_traces",
        ],
        "rules": [
            (
                "A sparse resume with zero branch cards must use copied "
                "target-intent or hypothesis traces before treating the run "
                "as empty."
            ),
            (
                "First CVRP branch must continue bounded large-instance "
                "two-opt with CMT2/CMT4 protection or name a different "
                "problem-owned causal path."
            ),
        ],
        "required_evidence": [
            (
                "live hypothesis references copied target-intent or "
                "hypothesis evidence when branch cards are absent"
            ),
            "branch-continuity caveat is recorded if copied branch cards remain absent",
        ],
    }


def _warehouse_research_focus() -> dict[str, object]:
    return {
        "schema_version": "scion.warehouse_research_focus.v1",
        "scope": "report_only_prepared_handoff",
        "measurement_opportunity_diagnostics": {
            "schema_version": "warehouse_measurement_runtime_handoff.v1",
            "source": "problem_v1.measurement.calibration_ref",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "metric": "total_cost",
            "unit": "raw_delta",
            "runtime_model": "comparative",
            "pairing_validity": "trajectory_divergent",
            "practical_screen_delta": 0.001,
            "practical_validate_delta": 0.001,
            "screening_mde_at_power_80": 577.5,
            "measurement_readiness": {
                "status": "ready",
                "reason_code": "ok",
                "calibration_age_days": 8,
                "calibration_max_age_days": 90,
                "n_pairs": 36,
                "mde_at_power_80": 577.5,
                "noise_band_p90_abs": 8500.0,
                "effect_to_mde_ratio": 1.7316017316017316e-06,
                "signal_to_noise_tier": "low_power",
                "decision_features_excluded": True,
                "calibration_ref": "calibration/aa_noise_floor.json",
            },
            "calibration": {
                "schema": "scion.aa_noise_floor.v1",
                "ref": "calibration/aa_noise_floor.json",
                "path": "/tmp/warehouse/calibration/aa_noise_floor.json",
                "calibrated_at": "2026-06-11T16:47:24.372634+00:00",
                "n_pairs": 36,
                "decision_features_excluded": True,
                "calibration_run_action": "modify",
                "source_artifact": {
                    "ref": "/tmp/warehouse/source-aa/aa_noise_floor.json",
                    "sha256": (
                        "5e34c863356bc74a9d2254dbde1d0a0945c88d56ca7201a4e033344b9718146f"
                    ),
                },
                "calibration_run": {
                    "action": "modify",
                    "decision_features_excluded": True,
                },
            },
            "reason_codes": [
                "WAREHOUSE_MDE_EXCEEDS_PRACTICAL_DELTA",
                "TRAJECTORY_DIVERGENT_LOW_SNR",
                "WAREHOUSE_COMPARATIVE_RUNTIME_REPORT_ONLY",
            ],
            "opportunity_projection_source": (
                "problem_adapter.render_problem_measurement_diagnostics"
            ),
            "adapter_payload_schema": "warehouse_validation_transfer_diagnostic.v1",
            "transfer_risk": {
                "risk_model": "screening-positive changes can miss validation transfer",
                "historical_pattern": "screening positive but no hierarchical gain",
                "latest_field_gate_pattern": "cost-only compression can regress holdout",
                "latest_formal_no_gain_pattern": "validation no-gain plateau caveat",
                "required_hypothesis_claims": [
                    "why the mechanism transfers beyond screening",
                    "what activation counter becomes positive",
                ],
            },
            "required_diagnostics": {
                "activation": [
                    "operator_invocations",
                    "eligible_vehicle_or_order_groups_seen",
                    "accepted_moves",
                ],
                "effect": [
                    "split_delta_sum",
                    "cost_delta_sum",
                    "improving_move_count",
                ],
            },
            "measurable_opportunity_classes": [
                {
                    "mechanism_family": "validation_transfer_continuation",
                    "required_evidence": (
                        "bounded operator activation/effect evidence before plateau"
                    ),
                }
            ],
            "opportunity_diagnostics": [
                {
                    "diagnostic_type": "post_promotion_followup",
                    "surface": "warehouse_operator",
                    "mechanism_family": "validation_transfer_continuation",
                    "metric": "lexicographic_objective",
                    "summary": "champion-v2 follow-up must test continuous improvement",
                    "recommended_action": (
                        "require protocol-evaluated split/cost, runtime-feedback, "
                        "and branch-continuity evidence before plateau"
                    ),
                    "confidence": "medium",
                    "reason_codes": [
                        "WAREHOUSE_V2_FOLLOWUP_CONTINUOUS_RESEARCH",
                        "PLATEAU_REQUIRES_PROTOCOL_EVIDENCE",
                        "SCREENING_ONLY_NOT_PLATEAU_EVIDENCE",
                    ],
                }
            ],
            "policy": (
                "Use these diagnostics to shape warehouse proposals before "
                "code generation; they are not DecisionFeatures."
            ),
            "recommended_min_seeds": 4,
            "related_calibrations": [
                {
                    "action": "create_new",
                    "n_pairs": 60,
                    "mde_at_power_80": 1725.0,
                }
            ],
        },
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
    prepared_contract = readiness_tool.build_inventory(run_root)["launcher"][
        "prepared_run_contract"
    ]
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
            "prepared_run_contract": prepared_contract,
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
    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    projection_summary = readiness_tool.research_focus_projection_summary(
        manifest_path=manifest_path,
        manifest=manifest,
    )
    prompt_summary = readiness_tool.research_focus_prompt_summary(
        manifest_path=manifest_path,
        manifest=manifest,
    )
    signals = {
        "prepared_research_focus_prompt_bridge": {
            "available": (
                ready
                and launch_markers
                and prompt_summary["available"] is True
            ),
            "detail": {
                "launch_markers": launch_marker_payload,
                "source_markers": {
                    "context_payload": True,
                    "manifest_env_reader": True,
                    "prompt_renderer": True,
                },
                "prompt_summary": prompt_summary,
            },
            "required": True,
            "runtime_generated_after_launch": False,
            "source": "fixture",
        },
        "prepared_research_focus_projection": {
            "available": ready and projection_summary["available"] is True,
            "detail": projection_summary,
            "required": True,
            "runtime_generated_after_launch": False,
            "source": "fixture",
        },
    }
    problem_v1 = None
    if problem_family in {"cvrp", "warehouse_delivery"}:
        problem_v1 = readiness_tool._resolve_problem_v1_path(
            root=run_root,
            manifest=manifest,
            problem_family=problem_family,
        )
        diagnostic_summary = (
            readiness_tool.problem_measurement_diagnostics_prompt_summary(
                problem_v1_path=problem_v1,
                problem_family=problem_family,
            )
        )
        diagnostic_signal_name = (
            "cvrp_problem_measurement_diagnostics_prompt_bridge"
            if problem_family == "cvrp"
            else "warehouse_problem_measurement_diagnostics_prompt_bridge"
        )
        diagnostic_markers = {
            "adapter_hook": True,
            "context_payload": True,
            "profile_projection": True,
            "prompt_renderer": True,
        }
        signals[diagnostic_signal_name] = {
            "available": diagnostic_summary["available"] is True,
            "detail": {
                "diagnostic_summary": diagnostic_summary,
                "source_markers": diagnostic_markers,
            },
            "required": True,
            "runtime_generated_after_launch": False,
            "source": "fixture",
        }
    if include_code_constraint_bridge:
        code_surface = {
            "cvrp": "solver_design",
            "warehouse_delivery": "order_level",
        }.get(problem_family, "")
        code_prompt_summary = (
            readiness_tool.active_subject_code_constraints_prompt_summary(
                problem_v1_path=problem_v1,
                problem_family=problem_family,
                surface=code_surface,
            )
        )
        if problem_family == "warehouse_delivery":
            signals["warehouse_active_subject_code_constraints_prompt_bridge"] = {
                "available": code_prompt_summary["available"] is True,
                "detail": {
                    "provider_payload": {
                        "schema_version": (
                            "scion.active_subject_code_constraints_provider_payload_summary.v1"
                        ),
                        "problem_family": "warehouse_delivery",
                        "surface": "order_level",
                        "problem_v1_path": "",
                        "report_only": True,
                        "quality_judgment": False,
                        "decision_features_excluded": True,
                        "raw_payload_excluded": True,
                        "available": True,
                        "reason": "ok",
                        "version": (
                            "warehouse_operator_validation_transfer_code_constraints.v1"
                        ),
                        "subject_id": (
                            "warehouse_delivery.operator.validation_transfer"
                        ),
                        "constraint_count": 5,
                        "object_model_hint_count": 0,
                        "api_contract_count": 0,
                        "forbidden_pattern_count": 5,
                        "total_guidance_item_count": 10,
                    },
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
                    "code_prompt_summary": code_prompt_summary,
                },
                "required": True,
                "runtime_generated_after_launch": False,
                "source": "fixture",
            }
        elif problem_family == "cvrp":
            signals["cvrp_active_subject_code_constraints_prompt_bridge"] = {
                "available": code_prompt_summary["available"] is True,
                "detail": {
                    "provider_payload": {
                        "schema_version": (
                            "scion.active_subject_code_constraints_provider_payload_summary.v1"
                        ),
                        "problem_family": "cvrp",
                        "surface": "solver_design",
                        "problem_v1_path": "",
                        "report_only": True,
                        "quality_judgment": False,
                        "decision_features_excluded": True,
                        "raw_payload_excluded": True,
                        "available": True,
                        "reason": "ok",
                        "version": "cvrp_solver_design_code_constraints.v1",
                        "subject_id": "cvrp.solver_design.active_baseline",
                        "constraint_count": 2,
                        "object_model_hint_count": 3,
                        "api_contract_count": 2,
                        "forbidden_pattern_count": 6,
                        "total_guidance_item_count": 13,
                    },
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
                    "code_prompt_summary": code_prompt_summary,
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
