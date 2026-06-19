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
    assert readiness["checks"]["rebuild_manifest_complete"]["status"] == "ok"
    assert readiness["checks"]["current_run_evidence"]["status"] == "ok"
    assert readiness["checks"]["analysis_brief_current_run_evidence"]["status"] == "ok"
    assert readiness["checks"]["problem_summary_actionability"]["status"] == "skipped"
    assert readiness["checks"]["problem_summary_actionability"]["required"] is False
    assert "Current-run analysis ready: `True`" in markdown
    assert check_tool.main([str(run_root), "--require-current-run-ready"]) == 0


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
    brief_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")

    readiness = check_tool.build_readiness(run_root)
    problem_check = readiness["checks"]["problem_summary_actionability"]

    assert readiness["current_run_analysis_ready"] is False
    assert problem_check["required"] is True
    assert problem_check["status"] == "failed"
    assert problem_check["detail"]["reason"] == "missing_problem_specific_summary"
    assert problem_check["detail"]["expected_problem_family"] == "cvrp"
    assert problem_check["detail"]["expected_summary"] == "cvrp_large_twoopt_summary"
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
    prompt_check = readiness["checks"]["prompt_source_visibility_actionability"]

    assert readiness["current_run_analysis_ready"] is True
    assert problem_check["required"] is True
    assert problem_check["status"] == "ok"
    assert problem_check["detail"][0]["summary"] == "warehouse_followup_summary"
    assert problem_check["detail"][0]["blocking_evidence_gaps"] == []
    assert prompt_check["required"] is True
    assert prompt_check["status"] == "ok"


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
        "available": True,
        "current_run_evidence": True,
        "evidence_gaps": [],
        "interpretation": "plateau_review_ready_current_run_evidence",
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
    brief["prompt_context_visibility_summary"] = {
        "available": True,
        "current_run_evidence": True,
        "aggregate": {
            "trace_count": 2,
            "source_visibility": {
                "trace_count": 2,
                "code_trace_count": 1,
                "hypothesis_target_source_trace_count": 1,
            },
        },
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
