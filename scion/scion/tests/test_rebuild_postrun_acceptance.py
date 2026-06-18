from __future__ import annotations

import importlib.util
import json
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
        "research_efficiency",
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
        / "research_efficiency"
        / "fixture.research_efficiency.v1.json"
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
    assert inventory["postrun_reports"]["counts"]["research_efficiency"] == 1


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
    assert manifest["families"]["research_efficiency"]["status"] == "skipped"
    assert manifest["families"]["summaries"]["status"] == "skipped"
    assert manifest["families"]["analysis_brief"]["status"] == "ok"
    assert manifest["families"]["inventory"]["status"] == "ok"
    assert not (
        report_dir
        / "research_efficiency"
        / "prepared.research_efficiency.v1.json"
    ).exists()
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
