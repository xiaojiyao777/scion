from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.registry import LineageRegistry


SCION_DIR = Path(__file__).parents[2]
CHECK_PATH = SCION_DIR / "tools" / "check_postrun_acceptance.py"
REBUILD_PATH = SCION_DIR / "tools" / "rebuild_postrun_acceptance.py"

CHECK_SPEC = importlib.util.spec_from_file_location(
    "check_postrun_acceptance",
    CHECK_PATH,
)
assert CHECK_SPEC is not None
check_tool = importlib.util.module_from_spec(CHECK_SPEC)
assert CHECK_SPEC.loader is not None
CHECK_SPEC.loader.exec_module(check_tool)

REBUILD_SPEC = importlib.util.spec_from_file_location(
    "rebuild_postrun_acceptance",
    REBUILD_PATH,
)
assert REBUILD_SPEC is not None
rebuild_tool = importlib.util.module_from_spec(REBUILD_SPEC)
assert REBUILD_SPEC.loader is not None
REBUILD_SPEC.loader.exec_module(rebuild_tool)


def test_postrun_acceptance_readiness_accepts_complete_current_run(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "run-root")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )

    readiness = check_tool.build_readiness(run_root)
    markdown = check_tool.render_markdown(readiness)

    assert readiness["schema_version"] == "scion.postrun_acceptance_readiness.v1"
    assert readiness["report_only"] is True
    assert readiness["decision_features_excluded"] is True
    assert readiness["delegation_ready"] is True
    assert readiness["current_run_analysis_ready"] is True
    assert readiness["failed_required_checks"] == []
    assert readiness["checks"]["rebuild_manifest_complete"]["status"] == "ok"
    assert readiness["checks"]["current_run_evidence"]["status"] == "ok"
    assert readiness["checks"]["analysis_brief_current_run_evidence"]["status"] == "ok"
    assert readiness["checks"]["problem_summary_actionability"]["status"] == "skipped"
    assert readiness["checks"]["problem_summary_actionability"]["required"] is False
    assert "Current-run analysis ready: `True`" in markdown
    assert "Failed required checks: `[]`" in markdown
    assert check_tool.main([str(run_root), "--require-current-run-ready"]) == 0


def test_postrun_acceptance_infers_legacy_warehouse_run_family(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "legacy-run")
    (run_root / "run.log").write_text(
        "Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False)\n",
        encoding="utf-8",
    )
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="legacy_warehouse",
        observed_control_arm="on",
        control_pair_key="legacy-warehouse:rep01",
        strict=True,
    )

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert "problem_summary_actionability" in readiness["failed_required_checks"]
    assert problem_check["required"] is True
    assert problem_check["status"] == "failed"
    assert problem_check["detail"][0]["summary"] == "warehouse_followup_summary"
    assert problem_check["detail"][0]["problem_family"] == "warehouse_delivery"
    assert "warehouse_handoff_requirements_incomplete" in problem_check["detail"][0][
        "blocking_evidence_gaps"
    ]


def test_postrun_acceptance_readiness_rejects_prepared_only_root(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "prepared-root"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "scion.launcher_prepare.v1",
            "status": "prepared",
            "prepared_only": True,
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "problem_family": "cvrp",
            "execution": {"rounds": 1},
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "effective_rounds_completed": 4,
            "formal_screened_candidates": 4,
        },
    )
    rebuild_tool.rebuild_postrun_acceptance(run_root, report_stem="prepared")

    readiness = check_tool.build_readiness(run_root)

    assert readiness["delegation_ready"] is True
    assert readiness["current_run_analysis_ready"] is False
    assert "not_prepared_only" in readiness["failed_required_checks"]
    assert readiness["checks"]["rebuild_manifest_complete"]["status"] == "failed"
    assert readiness["checks"]["current_run_evidence"]["status"] == "failed"
    assert readiness["checks"]["not_prepared_only"]["status"] == "failed"
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_readiness_requires_expected_problem_summary(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "cvrp-run")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    _add_prompt_source_visibility_summary(brief)
    brief.pop("cvrp_large_twoopt_summary", None)
    brief_path.write_text(
        json.dumps(brief, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert readiness["failed_required_checks"] == ["problem_summary_actionability"]
    assert problem_check["required"] is True
    assert problem_check["status"] == "failed"
    assert problem_check["detail"]["reason"] == "missing_problem_specific_summary"
    assert problem_check["detail"]["expected_problem_family"] == "cvrp"
    assert problem_check["detail"]["expected_summary"] == "cvrp_large_twoopt_summary"
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_readiness_uses_manifest_bound_analysis_brief(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "cvrp-run-stale-brief")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    _add_prompt_source_visibility_summary(brief)
    brief.pop("cvrp_large_twoopt_summary", None)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    stale_brief = dict(brief)
    stale_brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "bounded_twoopt_review_ready",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    stale_path = (
        run_root
        / "postrun_acceptance"
        / "analysis_brief"
        / "zz_stale.postrun_analysis_brief.v1.json"
    )
    _write_json(stale_path, stale_brief)

    readiness = check_tool.build_readiness(run_root)
    brief_check = readiness["checks"]["analysis_brief_present"]
    problem_check = readiness["checks"]["problem_summary_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert brief_check["status"] == "ok"
    assert brief_check["detail"]["selected_from_rebuild_manifest"] == str(brief_path)
    assert str(stale_path) in brief_check["detail"]["available_artifacts"]
    assert problem_check["status"] == "failed"
    assert problem_check["detail"]["reason"] == "missing_problem_specific_summary"


def test_postrun_acceptance_rejects_analysis_brief_prepared_contract_drift(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-contract-drift")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    contract_check = readiness["checks"][
        "analysis_brief_prepared_contract_consistency"
    ]
    problem_check = readiness["checks"]["problem_summary_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert contract_check["required"] is True
    assert contract_check["status"] == "failed"
    assert "prepared_contract_problem_family_mismatch" in contract_check["detail"][
        "failures"
    ]
    assert contract_check["detail"]["brief_problem_family"] == "cvrp"
    assert contract_check["detail"]["inventory_problem_family"] == (
        "warehouse_delivery"
    )
    assert problem_check["detail"][0]["expected_problem_family"] == (
        "warehouse_delivery"
    )


def test_postrun_acceptance_readiness_rejects_missing_manifest_declared_output(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "run-missing-manifest-output")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    manifest_path = (
        run_root / "postrun_acceptance" / "rebuild" / "rebuild_manifest.v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared_output = Path(
        manifest["families"]["research_efficiency"]["outputs"][0]
    )
    declared_output.unlink()
    _write_json(
        declared_output.with_name("zz_stale.research_efficiency.v1.json"),
        {"schema_version": "stale.test", "stale": True},
    )

    readiness = check_tool.build_readiness(run_root)
    output_check = readiness["checks"]["rebuild_manifest_declared_outputs_present"]

    assert readiness["checks"]["current_run_report_families_present"]["status"] == "ok"
    assert readiness["current_run_analysis_ready"] is False
    assert output_check["status"] == "failed"
    assert output_check["required"] is True
    assert output_check["detail"]["missing_outputs"] == [
        {
            "family": "research_efficiency",
            "path": str(declared_output),
            "manifest_output": str(declared_output),
        }
    ]
    assert output_check["detail"]["inconsistent_outputs"] == [
        {
            "family": "research_efficiency",
            "path": str(declared_output),
            "manifest_output": str(declared_output),
            "manifest_outputs_present": True,
            "actual_present": False,
        }
    ]
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_readiness_rejects_unexpected_family_output(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "run-extra-manifest-output")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    extra_output = (
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "zz_stale.research_efficiency.v1.json"
    )
    _write_json(
        extra_output,
        {"schema_version": "stale.test", "stale": True},
    )

    readiness = check_tool.build_readiness(run_root)
    output_check = readiness["checks"]["rebuild_manifest_declared_outputs_present"]

    assert readiness["checks"]["current_run_report_families_present"]["status"] == "ok"
    assert readiness["current_run_analysis_ready"] is False
    assert output_check["status"] == "failed"
    assert output_check["required"] is True
    assert output_check["detail"]["missing_outputs"] == []
    assert output_check["detail"]["inconsistent_outputs"] == []
    assert output_check["detail"]["unexpected_outputs"] == [
        {
            "family": "research_efficiency",
            "path": str(extra_output),
            "reason": "undeclared_generated_output",
        }
    ]


def test_postrun_acceptance_rejects_manifest_output_outside_family_dir(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "run-external-manifest-output")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    manifest_path = (
        run_root / "postrun_acceptance" / "rebuild" / "rebuild_manifest.v1.json"
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
    external_brief = tmp_path / "external" / "stale.postrun_analysis_brief.v1.json"
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

    readiness = check_tool.build_readiness(run_root)
    output_check = readiness["checks"]["rebuild_manifest_declared_outputs_present"]

    assert readiness["current_run_analysis_ready"] is False
    assert readiness["checks"]["analysis_brief_present"]["status"] == "failed"
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
                run_root / "postrun_acceptance" / "analysis_brief"
            ),
            "reason": "manifest_output_outside_family_directory",
        }
    ]


def test_postrun_acceptance_rejects_dirty_rebuild_manifest_boundary(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "run-dirty-rebuild-manifest")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    manifest_path = (
        run_root / "postrun_acceptance" / "rebuild" / "rebuild_manifest.v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_kind"] = "stale_postrun_acceptance_rebuild"
    manifest["report_dir"] = str(tmp_path / "external-postrun-acceptance")
    manifest["report_only"] = False
    manifest["quality_judgment"] = True
    manifest["decision_features_excluded"] = False
    manifest["campaign_state_mutated"] = True
    manifest["scheduler_state_mutated"] = True
    manifest["promotion_state_mutated"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    boundary_check = readiness["checks"]["rebuild_manifest_identity_boundary"]

    assert readiness["current_run_analysis_ready"] is False
    assert boundary_check["status"] == "failed"
    assert boundary_check["required"] is True
    assert boundary_check["detail"]["failures"] == [
        {
            "reason": "manifest_identity_mismatch",
            "field": "artifact_kind",
            "expected": "postrun_acceptance_rebuild",
            "actual": "stale_postrun_acceptance_rebuild",
        },
        {
            "reason": "manifest_identity_mismatch",
            "field": "report_dir",
            "expected": str(run_root / "postrun_acceptance"),
            "actual": str(tmp_path / "external-postrun-acceptance"),
        },
        {
            "reason": "manifest_boundary_flag_mismatch",
            "field": "report_only",
            "expected": True,
            "actual": False,
        },
        {
            "reason": "manifest_boundary_flag_mismatch",
            "field": "quality_judgment",
            "expected": False,
            "actual": True,
        },
        {
            "reason": "manifest_boundary_flag_mismatch",
            "field": "decision_features_excluded",
            "expected": True,
            "actual": False,
        },
        {
            "reason": "manifest_boundary_flag_mismatch",
            "field": "campaign_state_mutated",
            "expected": False,
            "actual": True,
        },
        {
            "reason": "manifest_boundary_flag_mismatch",
            "field": "scheduler_state_mutated",
            "expected": False,
            "actual": True,
        },
        {
            "reason": "manifest_boundary_flag_mismatch",
            "field": "promotion_state_mutated",
            "expected": False,
            "actual": True,
        },
    ]
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_readiness_accepts_actionable_problem_summary(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]

    assert readiness["current_run_analysis_ready"] is True
    assert problem_check["required"] is True
    assert problem_check["status"] == "ok"
    assert problem_check["detail"][0]["summary"] == "warehouse_followup_summary"
    assert problem_check["detail"][0]["schema_current"] is True
    assert problem_check["detail"][0]["interpretation_supported"] is True
    assert problem_check["detail"][0]["blocking_evidence_gaps"] == []
    assert prompt_check["required"] is True
    assert prompt_check["status"] == "ok"
    branch_check = readiness["checks"]["branch_research_state_actionability"]
    assert branch_check["required"] is True
    assert branch_check["status"] == "ok"
    assert branch_check["detail"]["consistency_failures"] == []
    champion_check = readiness["checks"]["champion_progress_actionability"]
    assert champion_check["required"] is True
    assert champion_check["status"] == "ok"
    assert champion_check["detail"]["consistency_failures"] == []


def test_postrun_acceptance_requires_branch_research_state_actionability(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-missing-branch")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief.pop("branch_research_state_summary", None)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]
    context_check = readiness["checks"]["research_context_actionability"]
    branch_check = readiness["checks"]["branch_research_state_actionability"]
    champion_check = readiness["checks"]["champion_progress_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["status"] == "ok"
    assert prompt_check["status"] == "ok"
    assert context_check["status"] == "ok"
    assert champion_check["status"] == "ok"
    assert branch_check["required"] is True
    assert branch_check["status"] == "failed"
    assert "branch_research_state_schema_stale" in branch_check["detail"][
        "failures"
    ]
    assert "branch_research_state_not_current_run_evidence" in branch_check[
        "detail"
    ]["failures"]
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_rejects_stale_branch_research_state_summary(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-stale-branch")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    branch_summary = brief["branch_research_state_summary"]
    branch_summary["aggregate"] = dict(branch_summary["aggregate"])
    branch_summary["aggregate"]["branch_count"] = 0
    branch_summary["aggregate"]["events_by_decision"] = {}
    branch_summary["top_branches"] = []
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    branch_check = readiness["checks"]["branch_research_state_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert branch_check["required"] is True
    assert branch_check["status"] == "failed"
    failures = branch_check["detail"]["failures"]
    assert "branch_research_state_branch_count_mismatch" in failures
    assert "branch_research_state_events_by_decision_mismatch" in failures
    assert "branch_research_state_top_branches_mismatch" in failures
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_requires_champion_progress_actionability(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-missing-champion")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief.pop("champion_progress_summary", None)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]
    context_check = readiness["checks"]["research_context_actionability"]
    champion_check = readiness["checks"]["champion_progress_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["status"] == "ok"
    assert prompt_check["status"] == "ok"
    assert context_check["status"] == "ok"
    assert champion_check["required"] is True
    assert champion_check["status"] == "failed"
    assert "champion_progress_schema_stale" in champion_check["detail"]["failures"]
    assert "champion_progress_not_current_run_evidence" in champion_check["detail"][
        "failures"
    ]
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_rejects_stale_champion_progress_summary(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-stale-champion")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    champion_summary = brief["champion_progress_summary"]
    champion_summary["interpretation"] = "champion_version_gain_observed"
    champion_summary["current_champion_version"] = 9
    champion_summary["champion_count"] = 9
    champion_summary["champion_versions"] = [9]
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    champion_check = readiness["checks"]["champion_progress_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert champion_check["required"] is True
    assert champion_check["status"] == "failed"
    failures = champion_check["detail"]["failures"]
    assert "champion_progress_interpretation_mismatch" in failures
    assert "champion_progress_current_champion_version_mismatch" in failures
    assert "champion_progress_champion_count_mismatch" in failures
    assert "champion_progress_champion_versions_mismatch" in failures
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_rejects_stale_problem_summary_contract(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-stale-summary")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "plateau_review_ready_current_run_evidence",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["required"] is True
    assert problem_check["status"] == "failed"
    assert problem_check["detail"][0]["schema_current"] is False
    assert problem_check["detail"][0]["interpretation_supported"] is False
    assert problem_check["detail"][0]["summary_failures"] == [
        "stale_problem_summary_schema",
        "unsupported_problem_summary_interpretation",
    ]


def test_postrun_acceptance_rejects_problem_summary_boundary_gap(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-summary-boundary")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "report_only": False,
        "quality_judgment": True,
        "decision_features_excluded": False,
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    # Keep the problem summary itself dirty after the helper fills evidence.
    brief["warehouse_followup_summary"]["report_only"] = False
    brief["warehouse_followup_summary"]["quality_judgment"] = True
    brief["warehouse_followup_summary"]["decision_features_excluded"] = False
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["required"] is True
    assert problem_check["status"] == "failed"
    assert set(problem_check["detail"][0]["summary_failures"]) == {
        "problem_summary_not_report_only",
        "problem_summary_quality_judgment_not_false",
        "problem_summary_decision_features_not_excluded",
    }


def test_postrun_acceptance_rejects_problem_summary_family_mismatch(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-family-mismatch")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["required"] is True
    assert problem_check["status"] == "failed"
    assert problem_check["detail"][0]["expected_problem_family"] == (
        "warehouse_delivery"
    )
    assert problem_check["detail"][0]["problem_family"] == "cvrp"
    assert problem_check["detail"][0]["problem_family_matches_expected"] is False
    assert problem_check["detail"][0]["summary_failures"] == [
        "problem_summary_family_mismatch"
    ]


def test_postrun_acceptance_rejects_stale_launch_required_problem_summary_flag(
    tmp_path: Path,
) -> None:
    cases = (
        (
            "warehouse_delivery",
            "warehouse-run-stale-launch-required",
            "warehouse_followup_summary",
            "launch_required_before_plateau_conclusion",
            True,
            "protocol_evaluated_plateau_review_ready",
            [],
        ),
        (
            "cvrp",
            "cvrp-run-missing-launch-required",
            "cvrp_large_twoopt_summary",
            "launch_required_before_twoopt_conclusion",
            None,
            "protocol_evaluated_without_large_twoopt_signal",
            ["missing_large_twoopt_mechanism_signal"],
        ),
    )
    for (
        problem_family,
        root_name,
        summary_key,
        launch_required_field,
        launch_required_value,
        interpretation,
        evidence_gaps,
    ) in cases:
        run_root = _write_current_run_root(tmp_path / root_name)
        rebuild_tool.rebuild_postrun_acceptance(
            run_root,
            report_stem="fixture",
            observed_control_arm="on",
            control_pair_key="fixture:rep01",
            strict=True,
        )
        brief_path = _latest_analysis_brief_path(run_root)
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        brief["prepared_run_contract"]["problem_family"] = problem_family
        brief[summary_key] = {
            "schema_version": check_tool.PROBLEM_SUMMARY_SCHEMAS[summary_key],
            "available": True,
            "current_run_evidence": True,
            "evidence_gaps": evidence_gaps,
            "interpretation": interpretation,
            "problem_family": problem_family,
            "review_axes_actionability": "actionable_current_run_evidence_present",
        }
        if launch_required_value is not None:
            brief[summary_key][launch_required_field] = launch_required_value
        _add_prompt_source_visibility_summary(brief)
        if launch_required_value is None:
            brief[summary_key].pop(launch_required_field, None)
        brief_path.write_text(
            json.dumps(brief, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        readiness = check_tool.build_readiness(run_root)
        problem_check = readiness["checks"]["problem_summary_actionability"]

        assert readiness["current_run_analysis_ready"] is False
        assert problem_check["required"] is True
        assert problem_check["status"] == "failed"
        assert problem_check["detail"][0]["launch_required_field"] == (
            launch_required_field
        )
        assert (
            problem_check["detail"][0]["launch_required_before_conclusion"]
            is launch_required_value
        )
        assert "problem_summary_launch_required_flag_stale" in problem_check[
            "detail"
        ][0]["summary_failures"]
        assert (
            check_tool.main([str(run_root), "--require-current-run-ready"])
            == check_tool.UNREADY_EXIT
        )


def test_postrun_acceptance_readiness_rejects_missing_prompt_source_visibility(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-missing-prompts")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert prompt_check["required"] is True
    assert prompt_check["status"] == "failed"
    assert "prompt_context_visibility_summary_unavailable" in prompt_check["detail"][
        "failures"
    ]
    assert "prompt_context_trace_accounting_missing" in prompt_check["detail"][
        "failures"
    ]
    assert "prompt_source_visibility_trace_accounting_missing" in prompt_check[
        "detail"
    ]["failures"]
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_requires_research_context_actionability(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-missing-density")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    brief["prompt_context_visibility_summary"] = {
        "schema_version": "scion.postrun_prompt_context_visibility_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
        "raw_response_excluded": True,
        "patch_body_excluded": True,
        "available": True,
        "current_run_evidence": True,
        "aggregate": {
            "trace_count": 2,
            "source_visibility": {
                "schema_version": "scion.postrun_prompt_source_visibility_summary.v1",
                "report_only": True,
                "decision_features_excluded": True,
                "trace_count": 2,
                "code_trace_count": 1,
                "code_protected_source_visible_count": 1,
                "code_protected_source_missing_count": 0,
                "code_missing_required_source_trace_count": 0,
                "code_missing_required_source_path_counts": {},
                "hypothesis_target_source_trace_count": 1,
                "hypothesis_target_source_required_count": 1,
                "hypothesis_target_source_visible_count": 1,
                "hypothesis_target_source_not_visible_count": 0,
                "active_subject_code_constraints_trace_count": 1,
                "active_subject_code_constraints_required_count": 1,
                "active_subject_code_constraints_full_visible_count": 1,
            },
        },
    }
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]
    context_check = readiness["checks"]["research_context_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert prompt_check["status"] == "ok"
    assert context_check["required"] is True
    assert context_check["status"] == "failed"
    assert "research_context_actionability_unavailable" in context_check["detail"][
        "failures"
    ]
    assert "prompt_block_family_trace_accounting_missing" in context_check["detail"][
        "failures"
    ]
    assert "prompt_hypothesis_research_context_trace_missing" in context_check[
        "detail"
    ]["failures"]
    assert "prompt_signal_density_schema_stale" in context_check["detail"][
        "failures"
    ]
    assert "prompt_signal_density_token_accounting_missing" in context_check[
        "detail"
    ]["failures"]
    assert "research_context_actionability_no_evidence" in context_check["detail"][
        "failures"
    ]
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_rejects_code_only_research_context_trace(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-code-only-context")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": _warehouse_problem_evidence(),
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    aggregate = brief["prompt_context_visibility_summary"]["aggregate"]
    aggregate["call_kind_counts"] = {"code": 2}
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]
    context_check = readiness["checks"]["research_context_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert prompt_check["status"] == "ok"
    assert context_check["required"] is True
    assert context_check["status"] == "failed"
    assert "prompt_hypothesis_research_context_trace_missing" in context_check[
        "detail"
    ]["failures"]
    assert context_check["detail"]["call_kind_counts"] == {"code": 2}
    assert context_check["detail"]["hypothesis_generation_trace_count"] == 0


def test_postrun_acceptance_rejects_stale_research_context_actionability_projection(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-stale-context")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": _warehouse_problem_evidence(),
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    actionability = brief["research_context_actionability_summary"]
    indicators = actionability["indicators"]
    assert isinstance(actionability, dict)
    assert isinstance(indicators, dict)
    actionability["guidance_status"] = "context_actionability_review_required"
    actionability["actionability_gaps"] = ["stale_prompt_projection"]
    actionability["recommendations"] = ["stale recommendation"]
    indicators["same_mechanism_selected"] = 0
    indicators["same_mechanism_observed"] = 0
    indicators["research_signal_tokens"] = 0
    indicators["research_plus_source_to_governance_ratio"] = 0.0
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    context_check = readiness["checks"]["research_context_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert context_check["required"] is True
    assert context_check["status"] == "failed"
    failures = context_check["detail"]["failures"]
    assert "research_context_actionability_guidance_status_mismatch" in failures
    assert "research_context_actionability_gaps_mismatch" in failures
    assert "research_context_actionability_recommendations_mismatch" in failures
    assert "research_context_actionability_same_mechanism_selected_mismatch" in (
        failures
    )
    assert "research_context_actionability_same_mechanism_observed_mismatch" in (
        failures
    )
    assert "research_context_actionability_research_signal_tokens_mismatch" in (
        failures
    )
    assert (
        "research_context_actionability_research_plus_source_to_governance_ratio_mismatch"
        in failures
    )
    assert context_check["detail"]["consistency_failures"]


def test_postrun_acceptance_rejects_review_surface_boundary_marker_gaps(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-boundary-gaps")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    prompt_summary = brief["prompt_context_visibility_summary"]
    prompt_summary["schema_version"] = "stale.prompt.visibility"
    prompt_summary["report_only"] = False
    prompt_summary["quality_judgment"] = True
    prompt_summary["decision_features_excluded"] = False
    prompt_summary["raw_prompt_excluded"] = False
    prompt_summary["raw_response_excluded"] = False
    prompt_summary["patch_body_excluded"] = False
    source_visibility = prompt_summary["aggregate"]["source_visibility"]
    source_visibility["schema_version"] = "stale.source.visibility"
    source_visibility["report_only"] = False
    source_visibility["decision_features_excluded"] = False
    context_summary = brief["research_context_actionability_summary"]
    context_summary["report_only"] = False
    context_summary["quality_judgment"] = True
    context_summary["decision_features_excluded"] = False
    density = prompt_summary["aggregate"]["signal_density"]
    density["report_only"] = False
    density["decision_features_excluded"] = False
    taxonomy = brief["failure_taxonomy_summary"]
    taxonomy["report_only"] = False
    taxonomy["quality_judgment"] = True
    taxonomy["decision_features_excluded"] = False
    taxonomy["raw_logs_excluded"] = False
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]
    context_check = readiness["checks"]["research_context_actionability"]
    taxonomy_check = readiness["checks"]["failure_taxonomy_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert prompt_check["status"] == "failed"
    assert "prompt_context_visibility_schema_stale" in prompt_check["detail"][
        "failures"
    ]
    assert "prompt_context_visibility_not_report_only" in prompt_check["detail"][
        "failures"
    ]
    assert "prompt_context_visibility_quality_judgment_not_false" in prompt_check[
        "detail"
    ]["failures"]
    assert "prompt_context_visibility_decision_features_not_excluded" in prompt_check[
        "detail"
    ]["failures"]
    assert "prompt_context_visibility_raw_prompt_excluded_not_true" in prompt_check[
        "detail"
    ]["failures"]
    assert "prompt_source_visibility_schema_stale" in prompt_check["detail"][
        "failures"
    ]
    assert "prompt_source_visibility_not_report_only" in prompt_check["detail"][
        "failures"
    ]
    assert "prompt_source_visibility_decision_features_not_excluded" in prompt_check[
        "detail"
    ]["failures"]
    assert "research_context_actionability_not_report_only" in context_check[
        "detail"
    ]["failures"]
    assert "research_context_actionability_quality_judgment_not_false" in (
        context_check["detail"]["failures"]
    )
    assert "research_context_actionability_decision_features_not_excluded" in (
        context_check["detail"]["failures"]
    )
    assert "prompt_signal_density_not_report_only" in context_check["detail"][
        "failures"
    ]
    assert "prompt_signal_density_decision_features_not_excluded" in context_check[
        "detail"
    ]["failures"]
    assert "failure_taxonomy_not_report_only" in taxonomy_check["detail"][
        "failures"
    ]
    assert "failure_taxonomy_quality_judgment_not_false" in taxonomy_check[
        "detail"
    ]["failures"]
    assert "failure_taxonomy_decision_features_not_excluded" in taxonomy_check[
        "detail"
    ]["failures"]
    assert "failure_taxonomy_raw_logs_excluded_not_true" in taxonomy_check[
        "detail"
    ]["failures"]
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_requires_failure_taxonomy_actionability(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-missing-taxonomy")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief["failure_taxonomy_summary"] = {
        "schema_version": "scion.postrun_failure_taxonomy_summary.v1",
        "current_run_evidence": True,
        "available": False,
        "report_count": 0,
        "failure_report_count": 0,
        "aggregate": {},
        "entries": [],
    }
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]
    context_check = readiness["checks"]["research_context_actionability"]
    taxonomy_check = readiness["checks"]["failure_taxonomy_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["status"] == "ok"
    assert prompt_check["status"] == "ok"
    assert context_check["status"] == "ok"
    assert taxonomy_check["required"] is True
    assert taxonomy_check["status"] == "failed"
    assert "failure_taxonomy_unavailable" in taxonomy_check["detail"]["failures"]
    assert "failure_taxonomy_report_count_missing" in taxonomy_check["detail"][
        "failures"
    ]
    assert "failure_taxonomy_entry_missing" in taxonomy_check["detail"]["failures"]
    assert "failure_taxonomy_report_evidence_missing" in taxonomy_check["detail"][
        "failures"
    ]
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_requires_review_input_summaries_actionability(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(
        tmp_path / "warehouse-run-missing-input-summaries"
    )
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief["protocol_accounting_summary"] = {
        "schema_version": "scion.postrun_protocol_accounting_summary.v1",
        "current_run_evidence": True,
        "available": False,
        "report_count": 0,
        "accounting_report_count": 0,
    }
    brief["measurement_effect_summary"] = {
        "schema_version": "scion.postrun_measurement_effect_summary.v1",
        "current_run_evidence": True,
        "available": False,
        "report_count": 0,
        "effect_report_count": 0,
    }
    brief["runtime_feedback_summary"] = {
        "schema_version": "scion.postrun_runtime_feedback_summary.v1",
        "current_run_evidence": True,
        "available": False,
        "drain_status_complete": False,
        "review_ready": False,
        "report_count": 0,
        "runtime_report_count": 0,
    }
    brief["research_continuity_summary"] = {
        "schema_version": "scion.postrun_research_continuity_summary.v1",
        "current_run_evidence": True,
        "available": False,
        "report_count": 0,
        "continuity_report_count": 0,
    }
    _refresh_research_context_actionability_summary(brief)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]
    context_check = readiness["checks"]["research_context_actionability"]
    taxonomy_check = readiness["checks"]["failure_taxonomy_actionability"]
    input_check = readiness["checks"]["review_input_summaries_actionability"]
    failures_by_summary = {
        item["summary"]: item["failures"]
        for item in input_check["detail"]["summaries"]
    }

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["status"] == "ok"
    assert prompt_check["status"] == "ok"
    assert context_check["status"] == "ok"
    assert taxonomy_check["status"] == "ok"
    assert input_check["required"] is True
    assert input_check["status"] == "failed"
    assert "protocol_accounting_summary_unavailable" in failures_by_summary[
        "protocol_accounting_summary"
    ]
    assert (
        "measurement_effect_summary_effect_report_count_missing"
        in failures_by_summary["measurement_effect_summary"]
    )
    assert "runtime_feedback_summary_drain_status_incomplete" in failures_by_summary[
        "runtime_feedback_summary"
    ]
    assert (
        "research_continuity_summary_continuity_report_count_missing"
        in failures_by_summary["research_continuity_summary"]
    )
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_rejects_problem_summary_input_mismatch(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-summary-mismatch")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    protocol = brief["protocol_accounting_summary"]
    assert isinstance(protocol, dict)
    protocol["aggregate"] = {
        "formal_screened_candidates": 1,
        "formal_protocol_evaluated_candidates": 0,
        "protocol_rows": {
            "protocol_evaluated_candidates": 0,
            "protocol_metric_results": 0,
        },
    }
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    input_check = readiness["checks"]["review_input_summaries_actionability"]
    consistency_check = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["status"] == "ok"
    assert input_check["status"] == "ok"
    assert consistency_check["required"] is True
    assert consistency_check["status"] == "failed"
    assert "problem_summary_protocol_evaluated_mismatch" in consistency_check[
        "detail"
    ]["failures"]
    assert "review_input_protocol_evaluated_missing" in consistency_check[
        "detail"
    ]["failures"]
    assert consistency_check["detail"]["summary_protocol_evaluated_candidates"] == 1
    assert consistency_check["detail"]["input_protocol_evaluated_candidates"] == 0
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_rejects_stale_runtime_evidence_in_problem_summary(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-stale-runtime")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    evidence = _warehouse_problem_evidence()
    runtime_evidence = evidence["runtime"]
    assert isinstance(runtime_evidence, dict)
    runtime_evidence["available"] = False
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "available": True,
        "current_run_evidence": True,
        "evidence": evidence,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "launch_required_before_plateau_conclusion": False,
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    runtime_summary = brief["runtime_feedback_summary"]
    assert isinstance(runtime_summary, dict)
    aggregate = runtime_summary["aggregate"]
    assert isinstance(aggregate, dict)
    runtime_budget = {
        "source_count": 1,
        "diagnostic_count": 1,
        "code_counts": {"SCREENING_RUNTIME_BUDGET_SATURATION": 1},
        "severity_counts": {"info": 1},
        "stage_counts": {"screening": 1},
        "runtime_model_counts": {"budget_exhausting": 1},
        "top_diagnostics": [],
    }
    aggregate["runtime_budget_diagnostics"] = runtime_budget
    runtime_summary["runtime_budget_diagnostics"] = runtime_budget
    runtime_summary["budget_diagnostic_source_count"] = 1
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    input_check = readiness["checks"]["review_input_summaries_actionability"]
    consistency_check = readiness["checks"]["problem_summary_input_consistency"]
    failures = consistency_check["detail"]["failures"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["status"] == "ok"
    assert input_check["status"] == "ok"
    assert consistency_check["status"] == "failed"
    assert "problem_summary_runtime_raw_available_mismatch" in failures
    assert "problem_summary_runtime_model_counts_mismatch" in failures
    assert "problem_summary_runtime_budget_diagnostic_count_mismatch" in failures
    assert consistency_check["detail"]["summary_runtime_raw_available"] is False
    assert consistency_check["detail"]["input_runtime_raw_available"] is True
    assert consistency_check["detail"]["summary_runtime_model_counts"] == {}
    assert consistency_check["detail"]["input_runtime_model_counts"] == {
        "budget_exhausting": 1
    }
    assert consistency_check["detail"]["summary_runtime_budget_diagnostic_count"] == 0
    assert consistency_check["detail"]["input_runtime_budget_diagnostic_count"] == 1
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_requires_review_inputs_boundary_markers(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(
        tmp_path / "warehouse-run-input-boundary-missing"
    )
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    measurement = brief["measurement_effect_summary"]
    assert isinstance(measurement, dict)
    measurement["report_only"] = False
    measurement["quality_judgment"] = True
    measurement["decision_features_excluded"] = False
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    input_check = readiness["checks"]["review_input_summaries_actionability"]
    consistency_check = readiness["checks"]["problem_summary_input_consistency"]
    failures_by_summary = {
        item["summary"]: item["failures"]
        for item in input_check["detail"]["summaries"]
    }

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["status"] == "ok"
    assert consistency_check["status"] == "ok"
    assert input_check["required"] is True
    assert input_check["status"] == "failed"
    assert "measurement_effect_summary_not_report_only" in failures_by_summary[
        "measurement_effect_summary"
    ]
    assert (
        "measurement_effect_summary_quality_judgment_not_false"
        in failures_by_summary["measurement_effect_summary"]
    )
    assert (
        "measurement_effect_summary_decision_features_not_excluded"
        in failures_by_summary["measurement_effect_summary"]
    )
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_readiness_requires_target_source_visibility_trace(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-missing-target-source")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    brief["prompt_context_visibility_summary"] = {
        "available": True,
        "current_run_evidence": True,
        "aggregate": {
            "trace_count": 2,
            "source_visibility": {
                "trace_count": 2,
                "code_trace_count": 1,
                "hypothesis_target_source_trace_count": 0,
                "hypothesis_target_source_visible_count": 0,
            },
        },
    }
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert prompt_check["status"] == "failed"
    assert "hypothesis_target_source_visibility_trace_missing" in prompt_check[
        "detail"
    ]["failures"]
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_cvrp_postrun_acceptance_requires_code_constraint_prompt_trace(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "cvrp-run-missing-code-constraints")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": ["missing_large_twoopt_mechanism_signal"],
        "interpretation": "protocol_evaluated_without_large_twoopt_signal",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    brief["prompt_context_visibility_summary"] = {
        "schema_version": "scion.postrun_prompt_context_visibility_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
        "raw_response_excluded": True,
        "patch_body_excluded": True,
        "available": True,
        "current_run_evidence": True,
        "aggregate": {
            "trace_count": 2,
            "source_visibility": {
                "schema_version": "scion.postrun_prompt_source_visibility_summary.v1",
                "report_only": True,
                "decision_features_excluded": True,
                "trace_count": 2,
                "code_trace_count": 1,
                "code_protected_source_visible_count": 1,
                "code_protected_source_missing_count": 0,
                "code_missing_required_source_trace_count": 0,
                "code_missing_required_source_path_counts": {},
                "hypothesis_target_source_trace_count": 1,
                "hypothesis_target_source_required_count": 1,
                "hypothesis_target_source_visible_count": 1,
                "hypothesis_target_source_not_visible_count": 0,
                "active_subject_code_constraints_trace_count": 0,
                "active_subject_code_constraints_required_count": 0,
                "active_subject_code_constraints_full_visible_count": 0,
            },
        },
    }
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert prompt_check["required"] is True
    assert prompt_check["status"] == "failed"
    assert "cvrp_active_subject_code_constraints_trace_missing" in prompt_check[
        "detail"
    ]["failures"]
    assert "cvrp_active_subject_code_constraints_not_required" in prompt_check[
        "detail"
    ]["failures"]
    assert "cvrp_active_subject_code_constraints_not_full_visible" in prompt_check[
        "detail"
    ]["failures"]
    assert prompt_check["detail"]["code_trace_count"] == 1
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_warehouse_postrun_acceptance_requires_code_constraint_prompt_trace(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(
        tmp_path / "warehouse-run-missing-code-constraints"
    )
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    brief["prompt_context_visibility_summary"] = {
        "available": True,
        "current_run_evidence": True,
        "aggregate": {
            "trace_count": 2,
            "source_visibility": {
                "trace_count": 2,
                "code_trace_count": 1,
                "code_protected_source_visible_count": 1,
                "code_protected_source_missing_count": 0,
                "code_missing_required_source_trace_count": 0,
                "code_missing_required_source_path_counts": {},
                "hypothesis_target_source_trace_count": 1,
                "hypothesis_target_source_required_count": 1,
                "hypothesis_target_source_visible_count": 1,
                "hypothesis_target_source_not_visible_count": 0,
                "active_subject_code_constraints_trace_count": 0,
                "active_subject_code_constraints_required_count": 0,
                "active_subject_code_constraints_full_visible_count": 0,
            },
        },
    }
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert prompt_check["required"] is True
    assert prompt_check["status"] == "failed"
    assert "warehouse_active_subject_code_constraints_trace_missing" in prompt_check[
        "detail"
    ]["failures"]
    assert "warehouse_active_subject_code_constraints_not_required" in prompt_check[
        "detail"
    ]["failures"]
    assert "warehouse_active_subject_code_constraints_not_full_visible" in prompt_check[
        "detail"
    ]["failures"]
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_requires_all_required_target_source_visible(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(
        tmp_path / "warehouse-run-partial-target-source"
    )
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    brief["prompt_context_visibility_summary"] = {
        "available": True,
        "current_run_evidence": True,
        "aggregate": {
            "trace_count": 3,
            "source_visibility": {
                "trace_count": 3,
                "code_trace_count": 1,
                "code_protected_source_visible_count": 1,
                "code_protected_source_missing_count": 0,
                "code_missing_required_source_trace_count": 0,
                "code_missing_required_source_path_counts": {},
                "hypothesis_target_source_trace_count": 2,
                "hypothesis_target_source_required_count": 2,
                "hypothesis_target_source_visible_count": 1,
                "hypothesis_target_source_not_visible_count": 1,
                "active_subject_code_constraints_trace_count": 1,
                "active_subject_code_constraints_required_count": 1,
                "active_subject_code_constraints_full_visible_count": 1,
                "active_subject_code_constraints_not_full_visible_count": 0,
            },
        },
    }
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert prompt_check["required"] is True
    assert prompt_check["status"] == "failed"
    assert "hypothesis_target_required_source_not_fully_visible" in prompt_check[
        "detail"
    ]["failures"]
    assert prompt_check["detail"]["hypothesis_target_source_required_count"] == 2
    assert prompt_check["detail"]["hypothesis_target_source_visible_count"] == 1
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_requires_code_protected_source_visibility(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(
        tmp_path / "warehouse-run-missing-code-source"
    )
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    brief["prompt_context_visibility_summary"] = {
        "available": True,
        "current_run_evidence": True,
        "aggregate": {
            "trace_count": 2,
            "source_visibility": {
                "trace_count": 2,
                "code_trace_count": 1,
                "code_protected_source_visible_count": 0,
                "code_protected_source_missing_count": 1,
                "code_missing_required_source_trace_count": 1,
                "code_missing_required_source_path_counts": {
                    "scion/scion/problems/warehouse_delivery/adapter.py": 1
                },
                "hypothesis_target_source_trace_count": 1,
                "hypothesis_target_source_required_count": 1,
                "hypothesis_target_source_visible_count": 1,
                "hypothesis_target_source_not_visible_count": 0,
                "active_subject_code_constraints_trace_count": 1,
                "active_subject_code_constraints_required_count": 1,
                "active_subject_code_constraints_full_visible_count": 1,
                "active_subject_code_constraints_not_full_visible_count": 0,
            },
        },
    }
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert prompt_check["required"] is True
    assert prompt_check["status"] == "failed"
    assert "code_protected_source_visibility_not_full" in prompt_check["detail"][
        "failures"
    ]
    assert "code_missing_required_source_visibility" in prompt_check["detail"][
        "failures"
    ]
    assert prompt_check["detail"]["code_missing_required_source_path_counts"] == {
        "scion/scion/problems/warehouse_delivery/adapter.py": 1
    }
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_readiness_rejects_blocking_problem_summary_gaps(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-missing-inputs")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [
            "missing_runtime_feedback_summary",
            "warehouse_research_continuity_evidence_too_shallow",
        ],
        "interpretation": "protocol_evaluated_review_inputs_incomplete",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["required"] is True
    assert problem_check["status"] == "failed"
    assert prompt_check["status"] == "ok"
    assert problem_check["detail"][0]["blocking_evidence_gaps"] == [
        "missing_runtime_feedback_summary"
    ]
    assert (
        "warehouse_research_continuity_evidence_too_shallow"
        not in problem_check["detail"][0]["blocking_evidence_gaps"]
    )
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_accepts_warehouse_quality_blocked_no_protocol_conclusion(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-quality-blocked")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": _warehouse_quality_blocked_problem_evidence(),
        "evidence_gaps": [
            "quality_blocked_before_protocol_evaluation",
            "missing_measurement_effect_summary",
            "missing_runtime_feedback_summary",
            "missing_research_continuity_summary",
        ],
        "interpretation": "quality_blocked_no_protocol_plateau_conclusion",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    _apply_warehouse_quality_blocked_review_inputs(brief, quality_block_count=2)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    input_check = readiness["checks"]["review_input_summaries_actionability"]
    consistency_check = readiness["checks"]["problem_summary_input_consistency"]
    taxonomy_check = readiness["checks"]["failure_taxonomy_actionability"]
    required_by_summary = {
        item["summary"]: item["required_for_interpretation"]
        for item in input_check["detail"]["summaries"]
    }

    assert readiness["current_run_analysis_ready"] is True
    assert problem_check["status"] == "ok"
    assert problem_check["detail"][0]["blocking_evidence_gaps"] == []
    assert input_check["status"] == "ok"
    assert required_by_summary == {
        "protocol_accounting_summary": True,
        "measurement_effect_summary": False,
        "runtime_feedback_summary": False,
        "research_continuity_summary": False,
    }
    assert consistency_check["status"] == "ok"
    assert consistency_check["detail"]["summary_quality_block_signal"] == 2
    assert consistency_check["detail"]["input_quality_block_signal"] == 2
    assert taxonomy_check["status"] == "ok"
    assert check_tool.main([str(run_root), "--require-current-run-ready"]) == 0


def test_postrun_acceptance_rejects_warehouse_quality_blocked_without_taxonomy_signal(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(
        tmp_path / "warehouse-run-stale-quality-blocked"
    )
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": _warehouse_quality_blocked_problem_evidence(),
        "evidence_gaps": [
            "quality_blocked_before_protocol_evaluation",
            "missing_measurement_effect_summary",
            "missing_runtime_feedback_summary",
            "missing_research_continuity_summary",
        ],
        "interpretation": "quality_blocked_no_protocol_plateau_conclusion",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    _apply_warehouse_quality_blocked_review_inputs(brief, quality_block_count=0)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    input_check = readiness["checks"]["review_input_summaries_actionability"]
    consistency_check = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["status"] == "ok"
    assert input_check["status"] == "ok"
    assert consistency_check["status"] == "failed"
    assert "failure_taxonomy_quality_block_signal_missing" in consistency_check[
        "detail"
    ]["failures"]
    assert consistency_check["detail"]["summary_quality_block_signal"] == 2
    assert consistency_check["detail"]["input_quality_block_signal"] == 0
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_rejects_warehouse_quality_blocked_when_protocol_evaluated(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(
        tmp_path / "warehouse-run-quality-blocked-protocol-evaluated"
    )
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    evidence = _warehouse_quality_blocked_problem_evidence()
    protocol_evidence = evidence["protocol"]
    assert isinstance(protocol_evidence, dict)
    protocol_evidence["protocol_evaluated_candidates"] = 1
    protocol_evidence["protocol_metric_results"] = 1
    protocol_evidence["formal_candidate_artifact_rows"] = 1
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": evidence,
        "evidence_gaps": [
            "quality_blocked_before_protocol_evaluation",
            "missing_measurement_effect_summary",
            "missing_runtime_feedback_summary",
            "missing_research_continuity_summary",
        ],
        "interpretation": "quality_blocked_no_protocol_plateau_conclusion",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    _apply_warehouse_quality_blocked_review_inputs(brief, quality_block_count=2)
    _mark_protocol_accounting_evaluated(brief)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    consistency_check = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert consistency_check["status"] == "failed"
    assert (
        "quality_blocked_no_protocol_has_protocol_evaluated_candidates"
        in consistency_check["detail"]["failures"]
    )
    assert consistency_check["detail"]["summary_protocol_evaluated_candidates"] == 1
    assert consistency_check["detail"]["input_protocol_evaluated_candidates"] == 1
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_accepts_cvrp_quality_blocked_no_protocol_conclusion(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "cvrp-run-quality-blocked")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": _cvrp_quality_blocked_problem_evidence(),
        "evidence_gaps": [
            "quality_blocked_before_protocol_evaluation",
            "missing_measurement_effect_summary",
            "missing_runtime_feedback_summary",
            "missing_research_continuity_summary",
        ],
        "interpretation": "quality_blocked_no_protocol_twoopt_conclusion",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    _apply_cvrp_quality_blocked_review_inputs(brief, quality_block_count=2)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    input_check = readiness["checks"]["review_input_summaries_actionability"]
    consistency_check = readiness["checks"]["problem_summary_input_consistency"]
    required_by_summary = {
        item["summary"]: item["required_for_interpretation"]
        for item in input_check["detail"]["summaries"]
    }

    assert readiness["current_run_analysis_ready"] is True
    assert problem_check["status"] == "ok"
    assert problem_check["detail"][0]["blocking_evidence_gaps"] == []
    assert input_check["status"] == "ok"
    assert required_by_summary == {
        "protocol_accounting_summary": True,
        "measurement_effect_summary": False,
        "runtime_feedback_summary": False,
        "research_continuity_summary": False,
    }
    assert consistency_check["status"] == "ok"
    assert consistency_check["detail"]["summary_quality_block_signal"] == 2
    assert consistency_check["detail"]["input_quality_block_signal"] == 2
    assert check_tool.main([str(run_root), "--require-current-run-ready"]) == 0


def test_postrun_acceptance_rejects_cvrp_quality_blocked_without_taxonomy_signal(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "cvrp-run-stale-quality-blocked")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": _cvrp_quality_blocked_problem_evidence(),
        "evidence_gaps": [
            "quality_blocked_before_protocol_evaluation",
            "missing_measurement_effect_summary",
            "missing_runtime_feedback_summary",
            "missing_research_continuity_summary",
        ],
        "interpretation": "quality_blocked_no_protocol_twoopt_conclusion",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    _apply_cvrp_quality_blocked_review_inputs(brief, quality_block_count=0)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    consistency_check = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert consistency_check["status"] == "failed"
    assert "failure_taxonomy_quality_block_signal_missing" in consistency_check[
        "detail"
    ]["failures"]
    assert consistency_check["detail"]["summary_quality_block_signal"] == 2
    assert consistency_check["detail"]["input_quality_block_signal"] == 0
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_rejects_cvrp_quality_blocked_when_protocol_evaluated(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(
        tmp_path / "cvrp-run-quality-blocked-protocol-evaluated"
    )
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    evidence = _cvrp_quality_blocked_problem_evidence()
    protocol_evidence = evidence["protocol"]
    assert isinstance(protocol_evidence, dict)
    protocol_evidence["protocol_evaluated_candidates"] = 1
    protocol_evidence["protocol_metric_results"] = 1
    protocol_evidence["formal_candidate_artifact_rows"] = 1
    brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": evidence,
        "evidence_gaps": [
            "quality_blocked_before_protocol_evaluation",
            "missing_measurement_effect_summary",
            "missing_runtime_feedback_summary",
            "missing_research_continuity_summary",
        ],
        "interpretation": "quality_blocked_no_protocol_twoopt_conclusion",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    _apply_cvrp_quality_blocked_review_inputs(brief, quality_block_count=2)
    _mark_protocol_accounting_evaluated(brief)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    consistency_check = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert consistency_check["status"] == "failed"
    assert (
        "quality_blocked_no_protocol_has_protocol_evaluated_candidates"
        in consistency_check["detail"]["failures"]
    )
    assert consistency_check["detail"]["summary_protocol_evaluated_candidates"] == 1
    assert consistency_check["detail"]["input_protocol_evaluated_candidates"] == 1
    assert (
        check_tool.main([str(run_root), "--require-current-run-ready"])
        == check_tool.UNREADY_EXIT
    )


def test_postrun_acceptance_readiness_accepts_nonblocking_problem_summary_gaps(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "cvrp-run-no-twoopt-signal")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": ["missing_large_twoopt_mechanism_signal"],
        "interpretation": "protocol_evaluated_without_large_twoopt_signal",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]

    assert readiness["current_run_analysis_ready"] is True
    assert problem_check["required"] is True
    assert problem_check["status"] == "ok"
    assert problem_check["detail"][0]["blocking_evidence_gaps"] == []
    assert prompt_check["required"] is True
    assert prompt_check["status"] == "ok"


def test_postrun_acceptance_rejects_problem_summary_without_evidence_payload(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "cvrp-run-no-evidence-payload")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": ["missing_large_twoopt_mechanism_signal"],
        "interpretation": "protocol_evaluated_without_large_twoopt_signal",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief["cvrp_large_twoopt_summary"].pop("evidence", None)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]
    consistency_check = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["status"] == "failed"
    assert "problem_summary_evidence_missing" in problem_check["detail"][0][
        "summary_failures"
    ]
    assert consistency_check["status"] == "failed"
    assert "problem_summary_evidence_missing" in consistency_check["detail"][
        "failures"
    ]


def test_postrun_acceptance_accepts_cvrp_missing_direct_evidence_conclusion(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "cvrp-run-missing-direct-evidence")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": ["missing_large_twoopt_direct_evidence"],
        "interpretation": (
            "protocol_evaluated_without_large_twoopt_direct_evidence"
        ),
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]

    assert readiness["current_run_analysis_ready"] is True
    assert problem_check["required"] is True
    assert problem_check["status"] == "ok"
    assert problem_check["detail"][0]["interpretation_supported"] is True
    assert problem_check["detail"][0]["blocking_evidence_gaps"] == []


def test_postrun_acceptance_rejects_cvrp_ready_summary_without_input_twoopt_evidence(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "cvrp-run-stale-twoopt-ready")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    evidence = _cvrp_problem_evidence()
    evidence["large_twoopt_mechanism"] = {
        "available": True,
        "mechanism_family_available": True,
        "direct_evidence_ready": True,
        "direct_evidence": {
            "ready": True,
            "missing": [],
            "complete_direct_evidence_row_count": 1,
        },
        "families": ["bounded_large_twoopt"],
        "protocol_families": ["bounded_large_twoopt"],
        "rejected_protocol_families": [],
        "protocol_row_count": 1,
    }
    brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": evidence,
        "evidence_gaps": [],
        "interpretation": "bounded_twoopt_review_ready",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    consistency = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert consistency["status"] == "failed"
    failures = consistency["detail"]["failures"]
    assert "problem_summary_large_twoopt_available_mismatch" in failures
    assert "problem_summary_large_twoopt_mechanism_family_available_mismatch" in (
        failures
    )
    assert "problem_summary_large_twoopt_direct_evidence_ready_mismatch" in (
        failures
    )
    assert "problem_summary_large_twoopt_protocol_rows_mismatch" in failures
    assert "review_input_large_twoopt_direct_evidence_missing" in failures


def test_postrun_acceptance_rejects_cvrp_ready_summary_with_unrelated_mechanism_evidence(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(
        tmp_path / "cvrp-run-unrelated-twoopt-mechanism-evidence"
    )
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    evidence = _cvrp_problem_evidence()
    evidence["measurement_effect"].update(
        {
            "rows_at_or_above_mde": 1,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": 1.2,
            "interpretation_counts": {"above_mde": 1},
            "mechanism_family_mapped_row_count": 1,
            "mechanism_family_unmapped_row_count": 0,
        }
    )
    evidence["large_twoopt_mechanism"] = {
        "available": True,
        "mechanism_family_available": True,
        "direct_evidence_ready": True,
        "direct_evidence": {
            "ready": True,
            "missing": [],
            "complete_direct_evidence_row_count": 1,
        },
        "families": ["bounded_large_twoopt"],
        "protocol_families": ["bounded_large_twoopt"],
        "rejected_protocol_families": [],
        "protocol_row_count": 1,
    }
    brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": evidence,
        "evidence_gaps": [],
        "interpretation": "bounded_twoopt_review_ready",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    measurement = brief["measurement_effect_summary"]
    assert isinstance(measurement, dict)
    aggregate = measurement["aggregate"]
    assert isinstance(aggregate, dict)
    aggregate.update(
        {
            "interpretation_counts": {"above_mde": 1},
            "rows_at_or_above_mde": 1,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": 1.2,
        }
    )
    aggregate["protocol_effects_vs_mde"] = {
        "top_rows_by_effect_to_mde": [
            {
                "mechanism_family": "bounded_large_twoopt",
                "positive_effect_at_or_above_mde": True,
                "mechanism_evidence": {
                    "primary_mechanism": "unrelated_probe",
                    "primary_activation_status": "observed",
                    "primary_effect_status": "positive",
                    "activation_evidence_status": "activation_observed",
                    "objective_effect_status": "mixed_objective_effect",
                    "mechanisms": [
                        {
                            "mechanism": "unrelated_probe",
                            "activation_status": "observed",
                            "effect_status": "positive",
                        }
                    ],
                },
                "candidate_phase_telemetry_summary": {
                    "selected_surface": "solver_design",
                    "runtime_observed_pairs": 8,
                    "buckets": {"two_opt": {"weighted_sum_ms": 120.0}},
                },
            }
        ]
    }
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    consistency = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert consistency["status"] == "failed"
    failures = consistency["detail"]["failures"]
    assert "problem_summary_large_twoopt_direct_evidence_ready_mismatch" in failures
    assert "review_input_large_twoopt_direct_evidence_missing" in failures


def test_postrun_acceptance_rejects_cvrp_ready_summary_with_split_direct_evidence_rows(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(
        tmp_path / "cvrp-run-split-twoopt-direct-evidence"
    )
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    evidence = _cvrp_problem_evidence()
    evidence["measurement_effect"].update(
        {
            "rows_at_or_above_mde": 1,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": 1.2,
            "interpretation_counts": {"above_mde": 1},
            "mechanism_family_mapped_row_count": 2,
            "mechanism_family_unmapped_row_count": 0,
        }
    )
    evidence["large_twoopt_mechanism"] = {
        "available": True,
        "mechanism_family_available": True,
        "direct_evidence_ready": True,
        "direct_evidence": {
            "ready": True,
            "missing": [],
            "complete_direct_evidence_row_count": 1,
        },
        "families": ["bounded_large_twoopt"],
        "protocol_families": ["bounded_large_twoopt"],
        "rejected_protocol_families": [],
        "protocol_row_count": 2,
    }
    brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": evidence,
        "evidence_gaps": [],
        "interpretation": "bounded_twoopt_review_ready",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    measurement = brief["measurement_effect_summary"]
    assert isinstance(measurement, dict)
    aggregate = measurement["aggregate"]
    assert isinstance(aggregate, dict)
    aggregate.update(
        {
            "interpretation_counts": {"above_mde": 1},
            "rows_at_or_above_mde": 1,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": 1.2,
            "mechanism_family_effects": {
                "bounded_large_twoopt": {
                    "protocol_row_count": 2,
                    "rows_at_or_above_mde": 1,
                    "max_effect_to_mde_ratio": 1.2,
                }
            },
        }
    )
    measurement["entries"] = [
        {
            "protocol_effects_vs_mde": {
                "top_rows_by_effect_to_mde": [
                    {
                        "mechanism_family": "bounded_large_twoopt",
                        "positive_effect_at_or_above_mde": True,
                        "mechanism_evidence": {
                            "primary_mechanism": "bounded_large_twoopt",
                            "primary_activation_status": "observed",
                            "primary_effect_status": "positive",
                            "activation_evidence_status": "activation_observed",
                            "objective_effect_status": "mixed_objective_effect",
                        },
                    },
                    {
                        "mechanism_family": "bounded_large_twoopt",
                        "positive_effect_at_or_above_mde": False,
                        "mechanism_evidence": {
                            "primary_mechanism": "bounded_large_twoopt",
                            "primary_activation_status": "observed",
                            "primary_effect_status": "positive",
                            "activation_evidence_status": "activation_observed",
                            "objective_effect_status": "mixed_objective_effect",
                        },
                        "candidate_phase_telemetry_summary": {
                            "selected_surface": "solver_design",
                            "runtime_observed_pairs": 8,
                            "buckets": {"two_opt": {"weighted_sum_ms": 120.0}},
                        },
                    },
                ]
            }
        }
    ]
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    consistency = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert consistency["status"] == "failed"
    failures = consistency["detail"]["failures"]
    assert "problem_summary_large_twoopt_available_mismatch" in failures
    assert "problem_summary_large_twoopt_direct_evidence_ready_mismatch" in failures
    assert "problem_summary_large_twoopt_protocol_rows_mismatch" not in failures
    assert "review_input_large_twoopt_direct_evidence_missing" in failures


def test_postrun_acceptance_rejects_cvrp_ready_summary_with_seed_family_input(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "cvrp-run-seed-family-twoopt-ready"
    run_root = _write_current_run_root(run_root)
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "cvrp"
    seed_family = "large_instance_intra_route_two_opt_seed"
    evidence = _cvrp_problem_evidence()
    evidence["measurement_effect"].update(
        {
            "rows_at_or_above_mde": 1,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": 1.2,
            "interpretation_counts": {"above_mde": 1},
            "mechanism_family_mapped_row_count": 1,
            "mechanism_family_unmapped_row_count": 0,
        }
    )
    evidence["large_twoopt_mechanism"] = {
        "available": True,
        "mechanism_family_available": True,
        "direct_evidence_ready": True,
        "direct_evidence": {
            "ready": True,
            "missing": [],
            "complete_direct_evidence_row_count": 1,
        },
        "families": [seed_family],
        "protocol_families": [seed_family],
        "rejected_protocol_families": [],
        "protocol_row_count": 1,
    }
    brief["cvrp_large_twoopt_summary"] = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": evidence,
        "evidence_gaps": [],
        "interpretation": "bounded_twoopt_review_ready",
        "problem_family": "cvrp",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    measurement = brief["measurement_effect_summary"]
    assert isinstance(measurement, dict)
    aggregate = measurement["aggregate"]
    assert isinstance(aggregate, dict)
    aggregate.update(
        {
            "interpretation_counts": {"above_mde": 1},
            "rows_at_or_above_mde": 1,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": 1.2,
            "mechanism_family_effects": {
                seed_family: {
                    "protocol_row_count": 1,
                    "rows_at_or_above_mde": 1,
                    "max_effect_to_mde_ratio": 1.2,
                }
            },
        }
    )
    measurement["entries"] = [
        {
            "protocol_effects_vs_mde": {
                "top_rows_by_effect_to_mde": [
                    {
                        "mechanism_family": seed_family,
                        "positive_effect_at_or_above_mde": True,
                        "mechanism_evidence": {
                            "primary_mechanism": seed_family,
                            "primary_activation_status": "observed",
                            "primary_effect_status": "positive",
                            "activation_evidence_status": "activation_observed",
                            "objective_effect_status": "mixed_objective_effect",
                        },
                        "candidate_phase_telemetry_summary": {
                            "selected_surface": "solver_design",
                            "runtime_observed_pairs": 8,
                            "buckets": {
                                "two_opt": {"weighted_sum_ms": 120.0},
                            },
                        },
                    }
                ]
            }
        }
    ]
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    consistency = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert consistency["status"] == "failed"
    failures = consistency["detail"]["failures"]
    assert "problem_summary_large_twoopt_available_mismatch" in failures
    assert "problem_summary_large_twoopt_mechanism_family_available_mismatch" in (
        failures
    )
    assert "problem_summary_large_twoopt_direct_evidence_ready_mismatch" in failures
    assert "problem_summary_large_twoopt_protocol_rows_mismatch" in failures
    assert "review_input_large_twoopt_direct_evidence_missing" in failures
    assert (
        consistency["detail"]["input_large_twoopt_mechanism_family_available"]
        is False
    )


def test_postrun_acceptance_rejects_warehouse_ready_summary_without_realized_input_continuity(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-stale-plateau-ready")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    evidence = _warehouse_problem_evidence()
    evidence["research_continuity"] = {
        "available": True,
        "continuity_report_count": 1,
        "substantive": True,
        "max_branch_depth": 2,
        "same_mechanism_observed": 1,
        "same_mechanism_selected": 1,
        "branch_lessons_required": 2,
        "branch_lessons_satisfied": 1,
        "weak_positive_observed": 1,
        "weak_positive_accepted": 1,
    }
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "available": True,
        "current_run_evidence": True,
        "evidence": evidence,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    _add_prompt_source_visibility_summary(brief)
    brief["research_continuity_summary"]["aggregate"] = {
        "max_branch_depth": 1,
        "branch_depth_distribution": {"1": 1},
        "mechanism_family_counts": {"fixture_mechanism": 1},
        "active_shape_counts": {"unrealized_continuity_opportunity": 1},
    }
    brief["research_continuity_summary"]["entries"] = [
        {
            "report": "fixture.research_efficiency.v1.json",
            "same_mechanism_followup": {
                "observed_opportunity_count": 1,
                "selected_same_branch_refinement_count": 0,
            },
            "branch_lesson_usage": {
                "requirement_count": 2,
                "satisfied_count": 0,
                "semantic_gap_count": 2,
            },
            "weak_positive_transfer": {
                "observed_opportunity_count": 1,
                "accepted_count": 0,
            },
        }
    ]
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    consistency = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert consistency["status"] == "failed"
    failures = consistency["detail"]["failures"]
    assert "problem_summary_warehouse_continuity_substantive_mismatch" in failures
    assert "problem_summary_warehouse_continuity_max_branch_depth_mismatch" in (
        failures
    )
    assert "problem_summary_warehouse_continuity_same_mechanism_selected_mismatch" in (
        failures
    )
    assert "problem_summary_warehouse_continuity_branch_lessons_satisfied_mismatch" in (
        failures
    )
    assert "problem_summary_warehouse_continuity_weak_positive_accepted_mismatch" in (
        failures
    )
    assert "review_input_warehouse_continuity_not_substantive" in failures


def test_postrun_acceptance_rejects_warehouse_plateau_ready_with_positive_measurement_effect(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-positive-plateau")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    _add_prompt_source_visibility_summary(brief)
    evidence = _warehouse_problem_evidence()
    evidence["measurement_effect"].update(
        {
            "rows_at_or_above_mde": 1,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": 1.2,
            "interpretation_counts": {"above_mde": 1},
            "effect_signal": "positive_effect_at_or_above_mde",
            "positive_effect_at_or_above_mde": True,
            "plateau_consistent": False,
            "all_ci_high_below_mde": False,
        }
    )
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "available": True,
        "current_run_evidence": True,
        "evidence": evidence,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    brief["measurement_effect_summary"]["aggregate"].update(
        {
            "interpretation_counts": {"above_mde": 1},
            "rows_at_or_above_mde": 1,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": 1.2,
        }
    )
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    consistency = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert consistency["status"] == "failed"
    failures = consistency["detail"]["failures"]
    assert "review_input_warehouse_measurement_not_plateau_consistent" in failures
    assert "review_input_warehouse_positive_effect_not_plateau" in failures


def test_postrun_acceptance_rejects_warehouse_positive_ready_without_positive_measurement_effect(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-false-positive-ready")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    _add_prompt_source_visibility_summary(brief)
    evidence = _warehouse_problem_evidence()
    evidence["measurement_effect"].update(
        {
            "rows_at_or_above_mde": 1,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": 1.2,
            "interpretation_counts": {"above_mde": 1},
            "effect_signal": "positive_effect_at_or_above_mde",
            "positive_effect_at_or_above_mde": True,
            "plateau_consistent": False,
            "all_ci_high_below_mde": False,
        }
    )
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "available": True,
        "current_run_evidence": True,
        "evidence": evidence,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_positive_effect_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    consistency = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert consistency["status"] == "failed"
    failures = consistency["detail"]["failures"]
    assert "problem_summary_warehouse_measurement_effect_signal_mismatch" in failures
    assert (
        "problem_summary_warehouse_measurement_positive_effect_at_or_above_mde_mismatch"
        in failures
    )
    assert "review_input_warehouse_positive_effect_missing" in failures


def test_postrun_acceptance_rejects_warehouse_plateau_ready_with_inconclusive_measurement_effect(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "warehouse-run-inconclusive-plateau")
    rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )
    brief_path = _latest_analysis_brief_path(run_root)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["prepared_run_contract"]["problem_family"] = "warehouse_delivery"
    _add_prompt_source_visibility_summary(brief)
    evidence = _warehouse_problem_evidence()
    evidence["measurement_effect"].update(
        {
            "rows_at_or_above_mde": 0,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": 0.7,
            "interpretation_counts": {
                "protocol_effects_below_mde_or_inconclusive": 1
            },
            "effect_signal": "protocol_effects_below_mde_or_inconclusive",
            "positive_effect_at_or_above_mde": False,
            "plateau_consistent": False,
            "all_ci_high_below_mde": False,
        }
    )
    brief["warehouse_followup_summary"] = {
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "available": True,
        "current_run_evidence": True,
        "evidence": evidence,
        "evidence_gaps": [],
        "interpretation": "protocol_evaluated_plateau_review_ready",
        "problem_family": "warehouse_delivery",
        "review_axes_actionability": "actionable_current_run_evidence_present",
    }
    brief["measurement_effect_summary"]["aggregate"].update(
        {
            "interpretation_counts": {
                "protocol_effects_below_mde_or_inconclusive": 1
            },
            "rows_at_or_above_mde": 0,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": 0.7,
        }
    )
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    consistency = readiness["checks"]["problem_summary_input_consistency"]

    assert readiness["current_run_analysis_ready"] is False
    assert consistency["status"] == "failed"
    failures = consistency["detail"]["failures"]
    assert "review_input_warehouse_measurement_not_plateau_consistent" in failures
    assert "review_input_warehouse_positive_effect_not_plateau" not in failures


def test_postrun_acceptance_readiness_rejects_missing_bundle(
    tmp_path: Path,
) -> None:
    run_root = _write_current_run_root(tmp_path / "missing-bundle")

    readiness = check_tool.build_readiness(run_root)

    assert readiness["delegation_ready"] is False
    assert readiness["current_run_analysis_ready"] is False
    assert readiness["checks"]["postrun_acceptance_present"]["status"] == "failed"
    assert readiness["checks"]["analysis_brief_present"]["status"] == "failed"
    assert readiness["checks"]["rebuild_manifest_present"]["status"] == "failed"


def _write_current_run_root(run_root: Path) -> Path:
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_campaign_db(campaign_dir)
    fixture_problem_family = _fixture_problem_family(run_root)
    if fixture_problem_family is not None:
        _write_prepared_manifest_fixture(run_root, fixture_problem_family)
    _write_json(
        run_root / "run_status.json",
        {
            "run_name": "fixture-run",
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "last_stop_reason": "max_rounds_exhausted",
            "wrapper_exit_status": 0,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "campaign_id": "fixture-campaign",
            "requested_rounds": 2,
            "effective_rounds_completed": 2,
            "protocol_metric_results": 1,
            "formal_screened_candidates": 1,
            "screening_protocol_results": 1,
            "run_validity": {"status": "valid", "effective_rounds_completed": 2},
            "measurement_readiness": {
                "status": "ready",
                "mde_at_power_80": 9.9,
                "decision_features_excluded": True,
            },
        },
    )
    _write_json(
        campaign_dir / "status.json",
        {
            "effective_rounds_completed": 2,
            "formal_screened_candidates": 1,
            "proposal_attempts_total": 1,
        },
    )
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    formal_index.write_text('{"candidate_id":"cand-1"}\n', encoding="utf-8")
    return run_root


def _fixture_problem_family(run_root: Path) -> str | None:
    name = run_root.name.lower()
    if "warehouse" in name:
        return "warehouse_delivery"
    if "cvrp" in name:
        return "cvrp"
    return None


def _write_prepared_manifest_fixture(run_root: Path, problem_family: str) -> None:
    campaign_dir = run_root / "campaign"
    command = (
        "python -m scion.cli.main run "
        f"--campaign-dir {campaign_dir} "
        "--agentic-session-timeout-sec 3600 "
        "--agentic-tool-max-steps 240 "
        "--agentic-tool-max-calls 200 "
        "--agentic-code-tool-max-calls 200 "
        "--agentic-observation-max-chars 2000000 "
        "--disable-early-stop"
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
            "command": command,
            "problem_family": problem_family,
            "model": {
                "name": "gpt-5.5",
                "completion_preflight": True,
            },
            "report_metadata": {
                "control_pair_key": "fixture:rep01",
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
            "execution": {
                "rounds": 2,
                "time_limit_sec": 30,
                "agentic_session_timeout_sec": 3600,
                "agentic_tool_max_steps": 240,
                "agentic_tool_max_calls": 200,
                "agentic_code_tool_max_calls": 200,
                "agentic_observation_max_chars": 2000000,
                "measurement_governance": "on",
                "proposal_context_ablation": "full",
                "agentic_proposal": True,
                "disable_early_stop": True,
            },
            "config": {},
            "git": {},
        },
    )
    (run_root / "command.txt").write_text(
        (
            f"PREPARED_RUN_MANIFEST={run_root / 'prepared_run_manifest.v1.json'}\n"
            f"command:\n{command}\n"
        ),
        encoding="utf-8",
    )


def _write_campaign_db(campaign_dir: Path) -> None:
    registry = LineageRegistry(str(campaign_dir / "scion.db"))
    branch_store = BranchStore(registry)
    hypothesis_store = HypothesisStore(registry)
    branch_id = str(uuid.uuid4())
    hypothesis_id = str(uuid.uuid4())
    branch_store.save(
        Branch(
            branch_id=branch_id,
            state=BranchState.EXPLORE,
            base_champion_id=1,
            base_champion_hash="abc123",
        )
    )
    hypothesis_store.save(
        HypothesisRecord(
            hypothesis_id=hypothesis_id,
            branch_id=branch_id,
            change_locus="operator",
            action="modify",
            status="active",
            target_file="operators/move.py",
            hypothesis_text="Improve a test operator.",
        )
    )
    registry.record_event(
        {
            "branch_id": branch_id,
            "hypothesis_id": hypothesis_id,
            "contract_result": "passed",
            "verification_result": "passed",
            "decision": "continue_explore",
            "decision_reason": "test",
        }
    )


def _latest_analysis_brief_path(run_root: Path) -> Path:
    paths = sorted((run_root / "postrun_acceptance" / "analysis_brief").glob("*.json"))
    assert paths
    return paths[-1]


def _add_prompt_source_visibility_summary(brief: dict[str, object]) -> None:
    warehouse_summary = brief.get("warehouse_followup_summary")
    if isinstance(warehouse_summary, dict):
        _add_problem_summary_boundary_markers(warehouse_summary)
        warehouse_summary.setdefault("evidence", _warehouse_problem_evidence())
    cvrp_summary = brief.get("cvrp_large_twoopt_summary")
    if isinstance(cvrp_summary, dict):
        _add_problem_summary_boundary_markers(cvrp_summary)
        cvrp_summary.setdefault("evidence", _cvrp_problem_evidence())
    _add_champion_progress_summary(brief)
    brief["protocol_accounting_summary"] = {
        "schema_version": "scion.postrun_protocol_accounting_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "report_count": 1,
        "accounting_report_count": 1,
        "aggregate": {
            "formal_screened_candidates": 1,
            "formal_protocol_evaluated_candidates": 1,
            "protocol_rows": {
                "protocol_evaluated_candidates": 1,
                "protocol_metric_results": 1,
            },
        },
        "entries": [{"report": "fixture.research_efficiency.v1.json"}],
    }
    brief["measurement_effect_summary"] = {
        "schema_version": "scion.postrun_measurement_effect_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "report_count": 1,
        "effect_report_count": 1,
        "aggregate": {
            "measurement_readiness_status_counts": {"ready": 1},
            "interpretation_counts": {"below_mde": 1},
            "protocol_row_count": 1,
            "rows_at_or_above_mde": 0,
            "rows_with_ci_high_below_mde": 1,
            "max_effect_to_mde_ratio": 0.25,
        },
        "entries": [{"report": "fixture.research_efficiency.v1.json"}],
    }
    brief["runtime_feedback_summary"] = {
        "schema_version": "scion.postrun_runtime_feedback_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "drain_status_complete": True,
        "review_ready": True,
        "report_count": 1,
        "runtime_report_count": 1,
        "budget_diagnostic_source_count": 0,
        "aggregate": {
            "fresh_runtime_replay_drain": {
                "status_counts": {"complete": 1},
                "attempts": 1,
                "executed": 1,
            },
            "stage_transition_drain": {
                "status_counts": {"complete": 1},
                "attempts": 1,
                "executed": 1,
            },
            "runtime_budget_diagnostics": {
                "source_count": 0,
                "diagnostic_count": 0,
                "runtime_model_counts": {},
            },
        },
        "entries": [{"report": "fixture.research_efficiency.v1.json"}],
    }
    brief["research_continuity_summary"] = {
        "schema_version": "scion.postrun_research_continuity_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "report_count": 1,
        "continuity_report_count": 1,
        "aggregate": {
            "max_branch_depth": 2,
            "branch_depth_distribution": {"2": 1},
            "mechanism_family_counts": {"fixture_mechanism": 1},
            "active_shape_counts": {"continue": 1},
        },
        "entries": [
            {
                "report": "fixture.research_efficiency.v1.json",
                "same_mechanism_followup": {
                    "observed_opportunity_count": 1,
                    "selected_same_branch_refinement_count": 1,
                },
                "branch_lesson_usage": {
                    "requirement_count": 0,
                    "satisfied_count": 0,
                    "semantic_gap_count": 0,
                },
                "weak_positive_transfer": {
                    "observed_opportunity_count": 0,
                    "accepted_count": 0,
                },
            }
        ],
    }
    brief["prompt_context_visibility_summary"] = {
        "schema_version": "scion.postrun_prompt_context_visibility_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
        "raw_response_excluded": True,
        "patch_body_excluded": True,
        "available": True,
        "current_run_evidence": True,
        "aggregate": {
            "trace_count": 2,
            "block_family_trace_count": 2,
            "call_kind_counts": {"hypothesis": 1, "code": 1},
            "block_family_totals": {
                "research_signal": {
                    "trace_count": 2,
                    "char_count": 2000,
                    "token_estimate": 500,
                },
                "source_code": {
                    "trace_count": 1,
                    "char_count": 1200,
                    "token_estimate": 300,
                },
                "governance": {
                    "trace_count": 1,
                    "char_count": 400,
                    "token_estimate": 100,
                },
            },
            "source_visibility": {
                "schema_version": "scion.postrun_prompt_source_visibility_summary.v1",
                "report_only": True,
                "decision_features_excluded": True,
                "trace_count": 2,
                "code_trace_count": 1,
                "code_protected_source_visible_count": 1,
                "code_protected_source_missing_count": 0,
                "code_missing_required_source_trace_count": 0,
                "code_missing_required_source_path_counts": {},
                "hypothesis_target_source_trace_count": 1,
                "hypothesis_target_source_required_count": 1,
                "hypothesis_target_source_visible_count": 1,
                "hypothesis_target_source_not_visible_count": 0,
                "active_subject_code_constraints_trace_count": 1,
                "active_subject_code_constraints_required_count": 1,
                "active_subject_code_constraints_full_visible_count": 1,
                "active_subject_code_constraints_not_full_visible_count": 0,
                "active_subject_code_constraints_status_counts": {
                    "included": 1
                },
            },
            "signal_density": {
                "schema_version": "scion.postrun_prompt_signal_density.v1",
                "report_only": True,
                "decision_features_excluded": True,
                "total_token_estimate": 900,
                "research_signal_tokens": 500,
                "source_code_tokens": 300,
                "cross_branch_tokens": 0,
                "governance_tokens": 100,
                "research_signal_share": 0.5555555555555556,
                "source_code_share": 0.3333333333333333,
                "cross_branch_share": 0.0,
                "governance_share": 0.1111111111111111,
                "research_plus_source_to_governance_ratio": 8.0,
                "interpretation": "research_and_source_signal_at_least_governance",
            },
        },
    }
    brief["research_context_actionability_summary"] = {
        "schema_version": "scion.postrun_research_context_actionability_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "prompt_context_available": True,
        "research_continuity_available": True,
        "guidance_status": "no_continuity_opportunities_observed",
        "indicators": {
            "schema_version": "scion.research_context_actionability_indicators.v1",
            "same_mechanism_selected": 0,
            "same_mechanism_observed": 0,
            "same_mechanism_missed": 0,
            "branch_lessons_satisfied": 0,
            "branch_lessons_required": 0,
            "branch_lesson_semantic_gap_count": 0,
            "branch_lesson_semantic_failure_count": 0,
            "branch_lesson_semantic_failure_counts": {},
            "branch_lesson_semantic_block_count": 0,
            "branch_lesson_semantic_block_counts": {},
            "weak_positive_accepted": 0,
            "weak_positive_observed": 0,
            "weak_positive_missed": 0,
            "research_signal_tokens": 500,
            "source_code_tokens": 300,
            "cross_branch_tokens": 0,
            "governance_tokens": 100,
            "research_plus_source_to_governance_ratio": 8.0,
            "omitted_section_trace_count": 0,
            "truncated_section_trace_count": 0,
        },
        "actionability_gaps": [],
        "recommendations": [],
    }
    _refresh_research_context_actionability_summary(brief)
    brief["failure_taxonomy_summary"] = {
        "schema_version": "scion.postrun_failure_taxonomy_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_logs_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "report_count": 1,
        "failure_report_count": 1,
        "aggregate": {
            "failure_count_maxima": {},
            "failure_observation_counts": {},
            "failure_source_counts": {},
            "run_validity_status_counts": {"valid": 1},
            "stopped_reason_counts": {"requested_rounds_complete": 1},
            "proposal_quality": {
                "proposal_attempts_total": 1,
                "proposal_attempts_consumed": 1,
                "proposal_quality_blocks": 0,
                "quality_blocks": 0,
                "quality_block_ledger_count": 0,
                "reports_with_quality_blocks": 0,
                "quality_block_reason_counts": {},
            },
            "top_examples": [],
        },
        "entries": [
            {
                "report": "fixture.research_efficiency.v1.json",
                "path": "postrun_acceptance/research_efficiency/"
                "fixture.research_efficiency.v1.json",
                "proposal_quality": {
                    "proposal_attempts_total": 1,
                    "proposal_attempts_consumed": 1,
                    "proposal_quality_blocks": 0,
                    "quality_blocks": 0,
                    "quality_block_ledger_count": 0,
                },
                "failure_taxonomy": {},
                "failure_observations_total": 0,
                "top_failure_keys": [],
                "top_examples": [],
                "run_status": {
                    "run_validity_status": "valid",
                    "run_completeness_status": "complete",
                    "run_complete": True,
                },
            }
        ],
    }


def _add_champion_progress_summary(brief: dict[str, object]) -> None:
    if isinstance(brief.get("champion_progress_summary"), dict):
        return
    brief["champion_progress_summary"] = {
        "schema_version": "scion.postrun_champion_progress_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "current_run_evidence": True,
        "available": True,
        "interpretation": "no_promotion_signal_observed",
        "starting_champion_version": None,
        "current_champion_version": None,
        "champion_version_gain": None,
        "champion_table_present": False,
        "champion_count": 0,
        "champion_versions": [],
        "max_weight_revision": None,
        "promotion_experiment_count": 0,
        "promotion_dossier_count": 0,
        "promoted_at_count": 0,
        "latest_promotion_experiment_id": None,
        "latest_promotion_dossier_ref": None,
        "promoted_hypothesis_count": 0,
        "promotion_decision_count": 0,
    }


def _add_problem_summary_boundary_markers(summary: dict[str, object]) -> None:
    summary.setdefault("report_only", True)
    summary.setdefault("quality_judgment", False)
    summary.setdefault("decision_features_excluded", True)
    problem_family = summary.get("problem_family")
    schema_version = summary.get("schema_version")
    if (
        problem_family == "warehouse_delivery"
        or schema_version == "scion.postrun_warehouse_followup_summary.v1"
    ):
        summary.setdefault("launch_required_before_plateau_conclusion", False)
    if (
        problem_family == "cvrp"
        or schema_version == "scion.postrun_cvrp_large_twoopt_summary.v1"
    ):
        summary.setdefault("launch_required_before_twoopt_conclusion", False)


def _warehouse_quality_blocked_problem_evidence() -> dict[str, object]:
    return {
        "protocol": {
            "formal_screened_candidates": 0,
            "protocol_evaluated_candidates": 0,
            "protocol_metric_results": 0,
            "formal_candidate_artifact_rows": 0,
            "stage_rows": {},
        },
        "measurement_effect": {
            "available": False,
            "protocol_row_count": 0,
            "rows_at_or_above_mde": 0,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": None,
            "interpretation_counts": {},
        },
        "quality_blocks": {
            "proposal_quality_blocks": 2,
            "quality_blocks": 2,
            "quality_block_ledger_count": 2,
            "reports_with_quality_blocks": 1,
            "reason_counts": {"missing_direct_effect": 2},
        },
        "runtime": {
            "available": False,
            "review_ready": False,
            "drain_status_complete": False,
            "fresh_runtime_status_counts": {},
            "stage_transition_status_counts": {},
            "runtime_budget_diagnostic_count": 0,
        },
        "research_continuity": {
            "available": False,
            "continuity_report_count": 0,
            "substantive": False,
            "max_branch_depth": 0,
            "same_mechanism_observed": 0,
            "same_mechanism_selected": 0,
            "branch_lessons_required": 0,
            "branch_lessons_satisfied": 0,
            "weak_positive_observed": 0,
            "weak_positive_accepted": 0,
            "mechanism_family_counts": {},
            "active_shape_counts": {},
        },
    }


def _apply_warehouse_quality_blocked_review_inputs(
    brief: dict[str, object],
    *,
    quality_block_count: int,
) -> None:
    _apply_quality_blocked_review_inputs(
        brief,
        quality_block_count=quality_block_count,
    )


def _apply_cvrp_quality_blocked_review_inputs(
    brief: dict[str, object],
    *,
    quality_block_count: int,
) -> None:
    _apply_quality_blocked_review_inputs(
        brief,
        quality_block_count=quality_block_count,
    )


def _apply_quality_blocked_review_inputs(
    brief: dict[str, object],
    *,
    quality_block_count: int,
) -> None:
    protocol = brief["protocol_accounting_summary"]
    assert isinstance(protocol, dict)
    protocol["aggregate"] = {
        "formal_screened_candidates": 0,
        "formal_protocol_evaluated_candidates": 0,
        "protocol_rows": {
            "protocol_evaluated_candidates": 0,
            "protocol_metric_results": 0,
        },
    }
    _mark_measurement_effect_unavailable(brief["measurement_effect_summary"])
    _mark_runtime_feedback_unavailable(brief["runtime_feedback_summary"])
    _mark_research_continuity_unavailable(brief["research_continuity_summary"])
    _refresh_research_context_actionability_summary(brief)
    _set_failure_taxonomy_quality_blocks(brief, quality_block_count)


def _refresh_research_context_actionability_summary(brief: dict[str, object]) -> None:
    prompt_context = brief.get("prompt_context_visibility_summary")
    research_continuity = brief.get("research_continuity_summary")
    brief["research_context_actionability_summary"] = (
        check_tool._research_context_actionability_summary(
            prompt_context_visibility_summary=(
                prompt_context if isinstance(prompt_context, dict) else {}
            ),
            research_continuity_summary=(
                research_continuity if isinstance(research_continuity, dict) else {}
            ),
        )
    )


def _mark_protocol_accounting_evaluated(brief: dict[str, object]) -> None:
    protocol = brief["protocol_accounting_summary"]
    assert isinstance(protocol, dict)
    protocol["aggregate"] = {
        "formal_screened_candidates": 1,
        "formal_protocol_evaluated_candidates": 1,
        "protocol_rows": {
            "protocol_evaluated_candidates": 1,
            "protocol_metric_results": 1,
        },
    }


def _mark_measurement_effect_unavailable(summary: object) -> None:
    assert isinstance(summary, dict)
    summary.update(
        {
            "current_run_evidence": True,
            "available": False,
            "report_count": 0,
            "effect_report_count": 0,
            "aggregate": {
                "measurement_readiness_status_counts": {},
                "interpretation_counts": {},
                "protocol_row_count": 0,
                "rows_at_or_above_mde": 0,
                "rows_with_ci_high_below_mde": 0,
                "max_effect_to_mde_ratio": None,
            },
            "entries": [],
        }
    )


def _mark_runtime_feedback_unavailable(summary: object) -> None:
    assert isinstance(summary, dict)
    summary.update(
        {
            "current_run_evidence": True,
            "available": False,
            "drain_status_complete": False,
            "review_ready": False,
            "report_count": 0,
            "runtime_report_count": 0,
            "budget_diagnostic_source_count": 0,
            "aggregate": {
                "fresh_runtime_replay_drain": {
                    "status_counts": {},
                    "attempts": 0,
                    "executed": 0,
                },
                "stage_transition_drain": {
                    "status_counts": {},
                    "attempts": 0,
                    "executed": 0,
                },
                "runtime_budget_diagnostics": {
                    "source_count": 0,
                    "diagnostic_count": 0,
                    "runtime_model_counts": {},
                },
            },
            "entries": [],
        }
    )


def _mark_research_continuity_unavailable(summary: object) -> None:
    assert isinstance(summary, dict)
    summary.update(
        {
            "current_run_evidence": True,
            "available": False,
            "report_count": 0,
            "continuity_report_count": 0,
            "aggregate": {
                "max_branch_depth": 0,
                "branch_depth_distribution": {},
                "mechanism_family_counts": {},
                "active_shape_counts": {},
            },
            "entries": [],
        }
    )


def _set_failure_taxonomy_quality_blocks(
    brief: dict[str, object],
    quality_block_count: int,
) -> None:
    taxonomy = brief["failure_taxonomy_summary"]
    assert isinstance(taxonomy, dict)
    aggregate = taxonomy["aggregate"]
    assert isinstance(aggregate, dict)
    proposal_quality = aggregate["proposal_quality"]
    assert isinstance(proposal_quality, dict)
    proposal_quality.update(
        {
            "proposal_attempts_total": max(1, quality_block_count),
            "proposal_attempts_consumed": max(1, quality_block_count),
            "proposal_quality_blocks": quality_block_count,
            "quality_blocks": quality_block_count,
            "quality_block_ledger_count": quality_block_count,
            "reports_with_quality_blocks": 1 if quality_block_count else 0,
            "quality_block_reason_counts": (
                {"missing_direct_effect": quality_block_count}
                if quality_block_count
                else {}
            ),
        }
    )
    entries = taxonomy.get("entries")
    assert isinstance(entries, list)
    entry = entries[0]
    assert isinstance(entry, dict)
    entry_quality = entry["proposal_quality"]
    assert isinstance(entry_quality, dict)
    entry_quality.update(
        {
            "proposal_attempts_total": max(1, quality_block_count),
            "proposal_attempts_consumed": max(1, quality_block_count),
            "proposal_quality_blocks": quality_block_count,
            "quality_blocks": quality_block_count,
            "quality_block_ledger_count": quality_block_count,
        }
    )


def _warehouse_problem_evidence() -> dict[str, object]:
    return {
        "protocol": {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
            "protocol_metric_results": 1,
            "formal_candidate_artifact_rows": 1,
            "stage_rows": {},
        },
        "measurement_effect": {
            "available": True,
            "protocol_row_count": 1,
            "rows_at_or_above_mde": 0,
            "rows_with_ci_high_below_mde": 1,
            "max_effect_to_mde_ratio": 0.25,
            "interpretation_counts": {"below_mde": 1},
            "effect_signal": "ci_high_below_mde_plateau_consistent",
            "positive_effect_at_or_above_mde": False,
            "plateau_consistent": True,
            "all_ci_high_below_mde": True,
        },
        "quality_blocks": {
            "proposal_quality_blocks": 0,
            "quality_blocks": 0,
            "quality_block_ledger_count": 0,
            "reports_with_quality_blocks": 0,
            "reason_counts": {},
        },
        "runtime": {
            "available": True,
            "review_ready": True,
            "drain_status_complete": True,
            "fresh_runtime_status_counts": {"complete": 1},
            "stage_transition_status_counts": {"complete": 1},
            "runtime_budget_diagnostic_count": 0,
        },
        "research_continuity": {
            "available": True,
            "continuity_report_count": 1,
            "substantive": True,
            "max_branch_depth": 2,
            "same_mechanism_observed": 1,
            "same_mechanism_selected": 1,
            "branch_lessons_required": 0,
            "branch_lessons_satisfied": 0,
            "weak_positive_observed": 0,
            "weak_positive_accepted": 0,
            "mechanism_family_counts": {"fixture_mechanism": 1},
            "active_shape_counts": {"continue": 1},
        },
    }


def _cvrp_problem_evidence() -> dict[str, object]:
    return {
        "protocol": {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
            "protocol_metric_results": 1,
            "formal_candidate_artifact_rows": 1,
            "stage_rows": {},
        },
        "measurement_effect": {
            "available": True,
            "protocol_row_count": 1,
            "rows_at_or_above_mde": 0,
            "rows_with_ci_high_below_mde": 1,
            "max_effect_to_mde_ratio": 0.25,
            "interpretation_counts": {"below_mde": 1},
            "mechanism_family_mapped_row_count": 0,
            "mechanism_family_unmapped_row_count": 1,
        },
        "large_twoopt_mechanism": {
            "available": False,
            "mechanism_family_available": False,
            "direct_evidence_ready": False,
            "direct_evidence": {
                "ready": False,
                "missing": ["missing_positive_effect_at_or_above_mde"],
            },
            "families": [],
            "protocol_families": [],
            "rejected_protocol_families": [],
            "protocol_row_count": 0,
        },
        "quality_blocks": {
            "proposal_quality_blocks": 0,
            "quality_blocks": 0,
            "quality_block_ledger_count": 0,
            "reason_counts": {},
        },
        "runtime": {
            "available": True,
            "raw_available": True,
            "drain_status_complete": True,
            "runtime_budget_diagnostic_count": 0,
        },
        "research_continuity": {
            "available": True,
            "continuity_report_count": 1,
        },
    }


def _cvrp_quality_blocked_problem_evidence() -> dict[str, object]:
    return {
        "protocol": {
            "formal_screened_candidates": 0,
            "protocol_evaluated_candidates": 0,
            "protocol_metric_results": 0,
            "formal_candidate_artifact_rows": 0,
            "stage_rows": {},
        },
        "measurement_effect": {
            "available": False,
            "protocol_row_count": 0,
            "rows_at_or_above_mde": 0,
            "rows_with_ci_high_below_mde": 0,
            "max_effect_to_mde_ratio": None,
            "interpretation_counts": {},
            "mechanism_family_mapped_row_count": 0,
            "mechanism_family_unmapped_row_count": 0,
        },
        "large_twoopt_mechanism": {
            "available": False,
            "mechanism_family_available": False,
            "direct_evidence_ready": False,
            "direct_evidence": {
                "ready": False,
                "missing": ["no_protocol_evaluated_large_twoopt_row"],
            },
            "families": [],
            "protocol_families": [],
            "rejected_protocol_families": [],
            "protocol_row_count": 0,
        },
        "quality_blocks": {
            "proposal_quality_blocks": 2,
            "quality_blocks": 2,
            "quality_block_ledger_count": 2,
            "reason_counts": {"missing_direct_effect": 2},
        },
        "runtime": {
            "available": False,
            "raw_available": False,
            "drain_status_complete": False,
            "runtime_budget_diagnostic_count": 0,
        },
        "research_continuity": {
            "available": False,
            "continuity_report_count": 0,
        },
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
