from __future__ import annotations

import importlib.util
import json
import os
import uuid
from pathlib import Path

from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.registry import LineageRegistry


TOOL_PATH = Path(__file__).parents[2] / "tools" / "rebuild_postrun_acceptance.py"
SPEC = importlib.util.spec_from_file_location("rebuild_postrun_acceptance", TOOL_PATH)
assert SPEC is not None
rebuild_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(rebuild_tool)


def test_family_result_preserves_complete_subprocess_output(tmp_path: Path) -> None:
    stdout = "stdout-start-" + ("x" * 3000) + "-stdout-end"
    stderr = "stderr-start-" + ("y" * 3000) + "-stderr-end"

    result = rebuild_tool._family_result(
        "fixture",
        status="failed",
        outputs=[tmp_path / "missing.json"],
        stdout=stdout,
        stderr=stderr,
    )

    assert result["stdout"] == stdout
    assert result["stderr"] == stderr
    assert "stdout_tail" not in result
    assert "stderr_tail" not in result


def test_rebuild_postrun_acceptance_writes_complete_bundle(tmp_path: Path) -> None:
    run_root = tmp_path / "run-root"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_campaign_db(campaign_dir)
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
            "steps": [
                {
                    "round": 1,
                    "branch_id": "branch-a",
                    "decision": "continue_explore",
                    "protocol_result": {
                        "stage": "screening",
                        "median_delta": 12.0,
                        "ci_high": 13.0,
                        "gate_outcome": "expand",
                    },
                }
            ],
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
    stale_manifest = (
        run_root
        / "postrun_acceptance"
        / "manifests"
        / "zz_stale.proposal_trajectory_manifest.v1.json"
    )
    stale_manifest.parent.mkdir(parents=True)
    _write_json(stale_manifest, {"schema_version": "stale.test"})
    stale_brief = (
        run_root
        / "postrun_acceptance"
        / "analysis_brief"
        / "zz_stale.postrun_analysis_brief.v1.json"
    )
    stale_brief.parent.mkdir(parents=True)
    _write_json(stale_brief, {"schema_version": "stale.test"})
    stale_brief_md = stale_brief.with_suffix(".md")
    stale_brief_md.write_text("stale", encoding="utf-8")

    manifest = rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )

    report_dir = run_root / "postrun_acceptance"
    assert manifest["schema_version"] == "scion.postrun_acceptance_rebuild.v1"
    assert manifest["report_only"] is True
    assert manifest["decision_features_excluded"] is True
    assert manifest["complete"] is True
    assert set(manifest["families"]) == {
        "summaries",
        "failures",
        "manifests",
        "analysis_brief",
        "inventory",
    }
    assert all(item["status"] == "ok" for item in manifest["families"].values())
    assert (
        report_dir / "summaries" / "fixture.summary.json"
    ).exists()
    assert (
        report_dir
        / "manifests"
        / "fixture.proposal_trajectory_manifest.v1.json"
    ).exists()
    assert (
        report_dir
        / "analysis_brief"
        / "fixture.postrun_analysis_brief.v1.json"
    ).exists()
    assert (
        report_dir
        / "inventory"
        / "fixture.postrun_artifact_inventory.v1.json"
    ).exists()
    assert not stale_manifest.exists()
    assert not stale_brief.exists()
    assert not stale_brief_md.exists()
    persisted = json.loads(
        (report_dir / "rebuild" / "rebuild_manifest.v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["complete"] is True
    inventory = json.loads(
        (
            report_dir
            / "inventory"
            / "fixture.postrun_artifact_inventory.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert inventory["postrun_reports"]["counts"]["analysis_brief"] == 1
    assert inventory["postrun_reports"]["counts"]["rebuild"] == 1
    assert inventory["postrun_reports"]["counts"]["manifests"] == 1


def test_rebuild_postrun_acceptance_skips_current_run_reports_for_prepared_only(
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
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "effective_rounds_completed": 9,
            "formal_screened_candidates": 9,
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "problem_family": "cvrp",
            "execution": {
                "measurement_governance": "on",
                "proposal_context_ablation": "full",
            },
        },
    )

    manifest = rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="prepared",
    )

    report_dir = run_root / "postrun_acceptance"
    assert manifest["prepared_only"] is True
    assert manifest["complete"] is False
    assert manifest["families"]["summaries"]["status"] == "skipped"
    assert manifest["families"]["analysis_brief"]["status"] == "ok"
    assert manifest["families"]["inventory"]["status"] == "ok"
    brief = json.loads(
        (
            report_dir
            / "analysis_brief"
            / "prepared.postrun_analysis_brief.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert brief["lifecycle"]["prepared_only"] is True
    assert brief["validity"]["run_validity_status"] == "prepared_only"
    assert brief["counters"]["effective_rounds_completed"] == 0


def test_rebuild_postrun_acceptance_skips_current_run_reports_after_preflight_failure(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "preflight-failed-root"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 64,
            "pre_campaign_completion_preflight": "failed",
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "problem_family": "warehouse_delivery",
            "execution": {
                "measurement_governance": "on",
                "proposal_context_ablation": "full",
                "rounds": 6,
            },
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "effective_rounds_completed": 9,
            "formal_screened_candidates": 9,
            "measurement_readiness": {"status": "ready"},
        },
    )
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    formal_index.write_text('{"candidate_id":"old-candidate"}\n', encoding="utf-8")

    manifest = rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="preflight_failed",
    )

    report_dir = run_root / "postrun_acceptance"
    assert manifest["prepared_only"] is False
    assert manifest["pre_campaign_completion_preflight_failed"] is True
    assert manifest["current_run_reports_skipped"] is True
    assert manifest["complete"] is False
    assert manifest["families"]["summaries"]["status"] == "skipped"
    assert manifest["families"]["manifests"]["status"] == "skipped"
    assert not (
        report_dir
        / "manifests"
        / "preflight_failed.proposal_trajectory_manifest.v1.json"
    ).exists()
    brief = json.loads(
        (
            report_dir
            / "analysis_brief"
            / "preflight_failed.postrun_analysis_brief.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert brief["validity"]["run_validity_status"] == "invalid_infra_only"
    assert brief["validity"]["last_stop_reason"] == (
        "pre_campaign_completion_preflight_failed"
    )
    assert brief["counters"]["effective_rounds_completed"] == 0
    assert brief["phase4_evidence_coverage"]["current_run_evidence"] is False
    assert any("INVALID INFRA-ONLY RUN" in item for item in brief["stop_conditions"])


def test_rebuild_postrun_acceptance_skips_current_run_reports_without_campaign_execution_artifacts(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "missing-campaign-execution-root"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_campaign_db(campaign_dir)
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
            "problem_family": "cvrp",
            "execution": {"rounds": 2},
        },
    )

    manifest = rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="missing_campaign_execution",
    )

    report_dir = run_root / "postrun_acceptance"
    assert manifest["current_run_evidence"] is False
    assert manifest["campaign_execution_artifacts_unavailable"] is True
    assert manifest["campaign_execution_failure_key"] == (
        "campaign_execution_artifacts_missing"
    )
    assert manifest["current_run_reports_skipped"] is True
    assert "campaign_execution_artifacts_unavailable" in manifest[
        "current_run_skip_reason"
    ]
    assert manifest["complete"] is False
    assert manifest["families"]["summaries"]["status"] == "skipped"
    assert manifest["families"]["manifests"]["status"] == "skipped"
    assert not (
        report_dir
        / "manifests"
        / "missing_campaign_execution.proposal_trajectory_manifest.v1.json"
    ).exists()
    brief = json.loads(
        (
            report_dir
            / "analysis_brief"
            / "missing_campaign_execution.postrun_analysis_brief.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert brief["validity"]["run_validity_status"] == "invalid_infra_only"
    assert brief["validity"]["last_stop_reason"] == (
        "campaign_execution_artifacts_missing"
    )
    assert brief["phase4_evidence_coverage"]["current_run_evidence"] is False
    try:
        rebuild_tool.rebuild_postrun_acceptance(
            run_root,
            report_stem="missing_campaign_execution_strict",
            strict=True,
        )
    except RuntimeError as exc:
        assert "postrun acceptance rebuild incomplete" in str(exc)
        assert "summaries" in str(exc)
    else:
        raise AssertionError("strict rebuild unexpectedly accepted missing campaign docs")


def test_rebuild_postrun_acceptance_skips_stale_resume_campaign_docs(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "stale-resume-campaign-docs-root"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_campaign_db(campaign_dir)
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
            "problem_family": "cvrp",
            "execution": {"rounds": 2},
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
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 3,
            "protocol_evaluated_candidates": 3,
        },
    )
    old_mtime = 1_700_000_000
    for path in (campaign_dir / "run_status.json", campaign_dir / "campaign_summary.json"):
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

    manifest = rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="stale_resume_docs",
    )

    report_dir = run_root / "postrun_acceptance"
    assert manifest["current_run_evidence"] is False
    assert manifest["campaign_execution_artifacts_unavailable"] is True
    assert manifest["campaign_execution_failure_key"] == (
        "campaign_execution_artifacts_stale_resume_snapshot"
    )
    assert manifest["current_run_reports_skipped"] is True
    assert manifest["complete"] is False
    assert manifest["families"]["summaries"]["status"] == "skipped"
    assert manifest["families"]["manifests"]["status"] == "skipped"
    brief = json.loads(
        (
            report_dir
            / "analysis_brief"
            / "stale_resume_docs.postrun_analysis_brief.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert brief["validity"]["last_stop_reason"] == (
        "campaign_execution_artifacts_stale_resume_snapshot"
    )
    assert brief["phase4_evidence_coverage"]["current_run_evidence"] is False
    try:
        rebuild_tool.rebuild_postrun_acceptance(
            run_root,
            report_stem="stale_resume_docs_strict",
            strict=True,
        )
    except RuntimeError as exc:
        assert "postrun acceptance rebuild incomplete" in str(exc)
        assert "summaries" in str(exc)
    else:
        raise AssertionError("strict rebuild unexpectedly accepted stale resume docs")


def test_rebuild_postrun_acceptance_skips_current_run_reports_after_runtime_guard_failure(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "runtime-guard-failed-root"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 64,
            "git_runtime_dirty": True,
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "problem_family": "cvrp",
            "execution": {
                "measurement_governance": "on",
                "proposal_context_ablation": "full",
                "rounds": 1,
            },
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "effective_rounds_completed": 9,
            "formal_screened_candidates": 9,
            "measurement_readiness": {"status": "ready"},
        },
    )
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    formal_index.write_text('{"candidate_id":"old-candidate"}\n', encoding="utf-8")

    manifest = rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="runtime_guard_failed",
    )

    report_dir = run_root / "postrun_acceptance"
    assert manifest["pre_campaign_infra_failed"] is True
    assert manifest["pre_campaign_infra_failure_keys"] == ["git_runtime_dirty"]
    assert manifest["current_run_reports_skipped"] is True
    assert manifest["complete"] is False
    assert manifest["families"]["summaries"]["status"] == "skipped"
    assert manifest["families"]["manifests"]["status"] == "skipped"
    assert "pre_campaign_infra_failure(git_runtime_dirty)" in (
        manifest["current_run_skip_reason"]
    )
    assert not (
        report_dir
        / "manifests"
        / "runtime_guard_failed.proposal_trajectory_manifest.v1.json"
    ).exists()
    brief = json.loads(
        (
            report_dir
            / "analysis_brief"
            / "runtime_guard_failed.postrun_analysis_brief.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert brief["validity"]["run_validity_status"] == "invalid_infra_only"
    assert brief["validity"]["last_stop_reason"] == "pre_campaign_git_runtime_dirty"
    assert brief["counters"]["effective_rounds_completed"] == 0
    assert brief["phase4_evidence_coverage"]["current_run_evidence"] is False
    assert any("INVALID INFRA-ONLY RUN" in item for item in brief["stop_conditions"])


def test_rebuild_postrun_acceptance_skips_current_run_reports_after_scion_dir_failure(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "scion-dir-failed-root"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 64,
            "scion_dir_missing": "/tmp/missing-scion",
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "problem_family": "warehouse",
            "execution": {
                "measurement_governance": "on",
                "proposal_context_ablation": "full",
                "rounds": 1,
            },
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "effective_rounds_completed": 3,
            "formal_screened_candidates": 3,
        },
    )

    manifest = rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="scion_dir_failed",
    )

    assert manifest["pre_campaign_infra_failed"] is True
    assert manifest["pre_campaign_infra_failure_keys"] == ["scion_dir_missing"]
    assert manifest["current_run_reports_skipped"] is True
    assert manifest["families"]["summaries"]["status"] == "skipped"
    assert "pre_campaign_infra_failure(scion_dir_missing)" in (
        manifest["current_run_skip_reason"]
    )
    brief = json.loads(
        (
            run_root
            / "postrun_acceptance"
            / "analysis_brief"
            / "scion_dir_failed.postrun_analysis_brief.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert brief["validity"]["last_stop_reason"] == "pre_campaign_scion_dir_missing"
    assert brief["phase4_evidence_coverage"]["current_run_evidence"] is False


def test_rebuild_postrun_acceptance_skips_current_run_reports_after_launch_env_failure(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "launch-env-failed-root"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 64,
            "launch_env_missing": str(run_root / "launch.env"),
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "problem_family": "warehouse",
            "execution": {
                "measurement_governance": "on",
                "proposal_context_ablation": "full",
                "rounds": 1,
            },
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "effective_rounds_completed": 4,
            "formal_screened_candidates": 4,
        },
    )

    manifest = rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="launch_env_failed",
    )

    assert manifest["pre_campaign_infra_failed"] is True
    assert manifest["pre_campaign_infra_failure_keys"] == ["launch_env_missing"]
    assert manifest["current_run_reports_skipped"] is True
    assert manifest["families"]["summaries"]["status"] == "skipped"
    assert "pre_campaign_infra_failure(launch_env_missing)" in (
        manifest["current_run_skip_reason"]
    )
    brief = json.loads(
        (
            run_root
            / "postrun_acceptance"
            / "analysis_brief"
            / "launch_env_failed.postrun_analysis_brief.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert brief["validity"]["last_stop_reason"] == "pre_campaign_launch_env_missing"
    assert brief["phase4_evidence_coverage"]["current_run_evidence"] is False


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


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
