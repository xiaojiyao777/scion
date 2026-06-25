from __future__ import annotations

import json
from pathlib import Path

from scion.postrun import (
    ANALYSIS_BRIEF_SCHEMA,
    REBUILD_SCHEMA,
    PostrunArtifactAcceptancePort,
)


def test_artifact_acceptance_checks_emit_legacy_ready_payloads(tmp_path: Path) -> None:
    root, report_dir, manifest, brief_path, brief = _write_ready_artifacts(tmp_path)
    port = PostrunArtifactAcceptancePort()
    inventory_path = port.artifact_json_path_from_manifest(
        manifest,
        report_dir,
        "inventory",
    )

    checks = port.summarize(
        root=root,
        report_dir=report_dir,
        rebuild_manifest=manifest,
        inventory_source="stored_postrun_inventory",
        inventory_path=inventory_path,
        analysis_brief_path=brief_path,
        analysis_brief=brief,
        postrun_counts={"inventory": 1},
    ).to_payloads()

    assert checks["inventory_loaded"]["status"] == "ok"
    assert checks["inventory_loaded"]["detail"]["source"] == "stored_postrun_inventory"
    assert checks["postrun_acceptance_present"]["status"] == "ok"
    assert checks["rebuild_manifest_schema"] == {
        "status": "ok",
        "required": True,
        "detail": REBUILD_SCHEMA,
    }
    assert checks["rebuild_manifest_run_identity"]["status"] == "ok"
    assert checks["rebuild_manifest_identity_boundary"]["status"] == "ok"
    assert checks["rebuild_manifest_complete"]["status"] == "ok"
    assert checks["rebuild_manifest_declared_outputs_present"]["status"] == "ok"
    assert checks["analysis_brief_schema"] == {
        "status": "ok",
        "required": True,
        "detail": ANALYSIS_BRIEF_SCHEMA,
    }
    assert checks["analysis_brief_run_identity"]["status"] == "ok"
    assert checks["analysis_brief_boundary"]["status"] == "ok"
    assert checks["inventory_artifact_present"]["status"] == "ok"


def test_artifact_acceptance_checks_reject_missing_and_out_of_scope_outputs(
    tmp_path: Path,
) -> None:
    root, report_dir, manifest, brief_path, brief = _write_ready_artifacts(tmp_path)
    external = tmp_path / "external-analysis.json"
    _write_json(external, brief)
    manifest["families"]["analysis_brief"]["outputs"] = [str(external)]
    manifest["families"]["analysis_brief"]["outputs_present"] = {
        str(external): True,
    }
    missing = "inventory/missing.json"
    manifest["families"]["inventory"]["outputs"].append(missing)
    manifest["families"]["inventory"]["outputs_present"][missing] = True

    checks = PostrunArtifactAcceptancePort().summarize(
        root=root,
        report_dir=report_dir,
        rebuild_manifest=manifest,
        inventory_source="stored_postrun_inventory",
        inventory_path=report_dir / "inventory" / "inventory.v1.json",
        analysis_brief_path=brief_path,
        analysis_brief=brief,
        postrun_counts={"inventory": 1},
    ).to_payloads()

    output_check = checks["rebuild_manifest_declared_outputs_present"]

    assert output_check["status"] == "failed"
    assert output_check["detail"]["missing_outputs"] == [
        {
            "family": "inventory",
            "path": str(report_dir / missing),
            "manifest_output": missing,
        }
    ]
    assert output_check["detail"]["out_of_scope_outputs"] == [
        {
            "family": "analysis_brief",
            "path": str(external),
            "manifest_output": str(external),
            "expected_directory": str(report_dir / "analysis_brief"),
            "reason": "manifest_output_outside_family_directory",
        }
    ]


def test_artifact_acceptance_checks_reject_boundary_drift(tmp_path: Path) -> None:
    root, report_dir, manifest, brief_path, brief = _write_ready_artifacts(tmp_path)
    manifest["quality_judgment"] = True
    brief["campaign_state_mutated"] = True

    checks = PostrunArtifactAcceptancePort().summarize(
        root=root,
        report_dir=report_dir,
        rebuild_manifest=manifest,
        inventory_source="stored_postrun_inventory",
        inventory_path=report_dir / "inventory" / "inventory.v1.json",
        analysis_brief_path=brief_path,
        analysis_brief=brief,
        postrun_counts={"inventory": 1},
    ).to_payloads()

    assert checks["rebuild_manifest_identity_boundary"]["status"] == "failed"
    assert checks["rebuild_manifest_identity_boundary"]["detail"]["failures"] == [
        {
            "reason": "manifest_boundary_flag_mismatch",
            "field": "quality_judgment",
            "expected": False,
            "actual": True,
        }
    ]
    assert checks["analysis_brief_boundary"]["status"] == "failed"
    assert checks["analysis_brief_boundary"]["detail"]["failures"] == [
        "analysis_brief_campaign_state_mutated_not_false"
    ]


def _write_ready_artifacts(
    tmp_path: Path,
) -> tuple[Path, Path, dict[str, object], Path, dict[str, object]]:
    root = tmp_path / "run"
    report_dir = root / "postrun_acceptance"
    (report_dir / "rebuild").mkdir(parents=True)
    (report_dir / "inventory").mkdir()
    (report_dir / "analysis_brief").mkdir()
    inventory_path = report_dir / "inventory" / "inventory.v1.json"
    brief_path = report_dir / "analysis_brief" / "brief.v1.json"
    _write_json(inventory_path, {"schema_version": "fixture.inventory.v1"})
    brief = {
        "schema_version": ANALYSIS_BRIEF_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "run_root": str(root),
    }
    _write_json(brief_path, brief)
    manifest = {
        "schema_version": REBUILD_SCHEMA,
        "artifact_kind": "postrun_acceptance_rebuild",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "run_root": str(root),
        "campaign_dir": str(root / "campaign"),
        "report_dir": str(report_dir),
        "complete": True,
        "families": {
            "inventory": {
                "status": "ok",
                "outputs": ["inventory/inventory.v1.json"],
                "outputs_present": {"inventory/inventory.v1.json": True},
            },
            "analysis_brief": {
                "status": "ok",
                "outputs": ["analysis_brief/brief.v1.json"],
                "outputs_present": {"analysis_brief/brief.v1.json": True},
            },
        },
    }
    _write_json(report_dir / "rebuild" / "rebuild_manifest.v1.json", manifest)
    return root, report_dir, manifest, brief_path, brief


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
