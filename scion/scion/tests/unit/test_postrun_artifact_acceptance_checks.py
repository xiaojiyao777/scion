from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from scion.core.branch import BranchController
from scion.core.formal_candidate_artifacts import FormalCandidatePatchArtifactRecorder
from scion.core.models import (
    CanaryResult,
    ChampionState,
    ContractResult,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.postrun import (
    ANALYSIS_BRIEF_SCHEMA,
    REBUILD_SCHEMA,
    PostrunArtifactAcceptancePort,
)
from scion.runtime.workspace import WorkspaceMaterializer


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


def test_artifact_acceptance_materializes_v3_and_fails_closed_on_tampering(
    tmp_path: Path,
) -> None:
    root, report_dir, manifest, brief_path, brief = _write_ready_artifacts(tmp_path)
    artifact_path, artifact = _write_v3_formal_candidate(root)

    valid_checks = _summarize_artifact_checks(
        root=root,
        report_dir=report_dir,
        manifest=manifest,
        brief_path=brief_path,
        brief=brief,
    )
    valid = valid_checks["formal_candidate_diff_integrity"]
    assert valid["status"] == "ok"
    validation = valid["detail"]["validations"][0]
    assert validation["diff_ref"] == artifact["replay_materialization"]["diff_ref"]
    assert validation["diff_ref"] != artifact["patch"]["diff_ref"]
    assert validation["materialization_status"] == "ok"
    assert validation["materialization_model"] == (
        "champion_base_plus_cumulative_replay_materialization"
    )

    for corruption in ("closure", "content", "base_identity", "final_hash"):
        corrupted = deepcopy(artifact)
        closure = corrupted["replay_materialization"]
        if corruption == "closure":
            closure["files"] = []
        elif corruption == "content":
            closure["files"][0]["code_content"] = "VALUE = 999\n"
        elif corruption == "base_identity":
            closure["base_identity_manifest"]["files"][0]["sha256"] = "0" * 64
        else:
            wrong_hash = "0" * 64
            closure["candidate_identity_manifest"]["code_hash"] = wrong_hash
            corrupted["current"]["current_code_hash"] = wrong_hash
            corrupted["replay_identity"]["code_hash"] = wrong_hash
        _write_json(artifact_path, corrupted)

        checks = _summarize_artifact_checks(
            root=root,
            report_dir=report_dir,
            manifest=manifest,
            brief_path=brief_path,
            brief=brief,
        )
        formal = checks["formal_candidate_diff_integrity"]
        assert formal["status"] == "failed", corruption
        assert any(
            failure["reason"] == "candidate_replay_materialization_invalid"
            for failure in formal["detail"]["failures"]
        ), corruption

    _write_json(artifact_path, artifact)


def test_artifact_acceptance_allows_v3_empty_cumulative_closure(
    tmp_path: Path,
) -> None:
    root, report_dir, manifest, brief_path, brief = _write_ready_artifacts(tmp_path)
    _, artifact = _write_v3_formal_candidate(root, revert_to_champion=True)

    assert artifact["replay_materialization"]["files"] == []
    checks = _summarize_artifact_checks(
        root=root,
        report_dir=report_dir,
        manifest=manifest,
        brief_path=brief_path,
        brief=brief,
    )
    formal = checks["formal_candidate_diff_integrity"]
    assert formal["status"] == "ok"
    assert {
        validation["validation_mode"]
        for validation in formal["detail"]["validations"]
    } == {"apply_check", "empty_cumulative_closure"}
    assert all(
        validation["materialization_status"] == "ok"
        for validation in formal["detail"]["validations"]
    )


def test_artifact_acceptance_binds_v3_candidate_and_proposal_diffs(
    tmp_path: Path,
) -> None:
    root, report_dir, manifest, brief_path, brief = _write_ready_artifacts(tmp_path)
    artifact_path, artifact = _write_v3_formal_candidate(root)
    campaign_dir = root / "campaign"
    candidate_diff = campaign_dir / artifact["replay_materialization"]["diff_ref"]
    proposal_diff = campaign_dir / artifact["patch"]["diff_ref"]

    original_candidate_diff = candidate_diff.read_text(encoding="utf-8")
    candidate_diff.write_text(
        original_candidate_diff.replace("+VALUE = 1", "+VALUE = 2"),
        encoding="utf-8",
    )
    checks = _summarize_artifact_checks(
        root=root,
        report_dir=report_dir,
        manifest=manifest,
        brief_path=brief_path,
        brief=brief,
    )
    failures = checks["formal_candidate_diff_integrity"]["detail"]["failures"]
    assert any(
        failure["reason"] == "candidate_diff_content_mismatch"
        for failure in failures
    )

    candidate_diff.write_text(original_candidate_diff, encoding="utf-8")
    proposal_diff.unlink()
    checks = _summarize_artifact_checks(
        root=root,
        report_dir=report_dir,
        manifest=manifest,
        brief_path=brief_path,
        brief=brief,
    )
    failures = checks["formal_candidate_diff_integrity"]["detail"]["failures"]
    assert any(failure["reason"] == "proposal_diff_missing" for failure in failures)


def test_artifact_acceptance_rejects_orphan_formal_candidate_without_index(
    tmp_path: Path,
) -> None:
    root, report_dir, manifest, brief_path, brief = _write_ready_artifacts(tmp_path)
    orphan = (
        root
        / "campaign"
        / "artifacts"
        / "formal_candidates"
        / "orphan"
        / "candidate.patch.json"
    )
    orphan.parent.mkdir(parents=True)
    _write_json(orphan, {"schema": "scion.formal_candidate_patch_artifact.v3"})

    checks = _summarize_artifact_checks(
        root=root,
        report_dir=report_dir,
        manifest=manifest,
        brief_path=brief_path,
        brief=brief,
    )
    formal = checks["formal_candidate_diff_integrity"]
    assert formal["status"] == "failed"
    assert formal["detail"]["reason"] == (
        "formal_candidate_index_absent_with_orphan_artifacts"
    )
    assert formal["detail"]["orphan_artifacts"] == [str(orphan)]


def test_artifact_acceptance_rejects_unindexed_candidate_when_index_exists(
    tmp_path: Path,
) -> None:
    root, report_dir, manifest, brief_path, brief = _write_ready_artifacts(tmp_path)
    indexed_artifact, _ = _write_v3_formal_candidate(root)
    orphan = indexed_artifact.parent.parent / "orphan" / "candidate.patch.json"
    orphan.parent.mkdir(parents=True)
    _write_json(orphan, {"schema": "scion.formal_candidate_patch_artifact.v3"})

    checks = _summarize_artifact_checks(
        root=root,
        report_dir=report_dir,
        manifest=manifest,
        brief_path=brief_path,
        brief=brief,
    )
    formal = checks["formal_candidate_diff_integrity"]
    assert formal["status"] == "failed"
    assert formal["detail"]["checked_candidates"] == 1
    assert formal["detail"]["orphan_artifacts"] == [str(orphan)]
    assert {
        failure["reason"] for failure in formal["detail"]["failures"]
    } == {"candidate_metadata_not_indexed"}


def test_artifact_acceptance_binds_quarantined_resume_index_as_inherited(
    tmp_path: Path,
) -> None:
    root, report_dir, manifest, brief_path, brief = _write_ready_artifacts(tmp_path)
    indexed_artifact, _ = _write_v3_formal_candidate(root)
    live_index = (
        root / "campaign" / "artifacts" / "formal_candidates" / "index.jsonl"
    )
    snapshot_index = (
        root
        / "resume_snapshot"
        / "campaign"
        / "artifacts"
        / "formal_candidates"
        / "index.jsonl"
    )
    snapshot_index.parent.mkdir(parents=True)
    live_index.replace(snapshot_index)
    snapshot_index.write_text(
        snapshot_index.read_text(encoding="utf-8")
        + json.dumps(
            {
                "candidate_id": "omitted-inherited-candidate",
                "artifact_status": "omitted",
                "artifact_ref": None,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    snapshot_manifest = root / "resume_snapshot" / "resume_source_manifest.v1.json"
    _write_json(
        snapshot_manifest,
        {
            "schema_version": "scion.launcher_resume_preparation.v1",
            "terminal_artifacts": [
                {
                    "original_ref": "artifacts/formal_candidates/index.jsonl",
                    "snapshot_ref": (
                        "resume_snapshot/campaign/artifacts/formal_candidates/"
                        "index.jsonl"
                    ),
                    "size_bytes": snapshot_index.stat().st_size,
                    "sha256": sha256(snapshot_index.read_bytes()).hexdigest(),
                }
            ],
        },
    )
    _write_json(
        root / "prepared_run_manifest.v1.json",
        {"resume_snapshot_ref": "resume_snapshot/resume_source_manifest.v1.json"},
    )

    checks = _summarize_artifact_checks(
        root=root,
        report_dir=report_dir,
        manifest=manifest,
        brief_path=brief_path,
        brief=brief,
    )
    formal = checks["formal_candidate_diff_integrity"]
    assert formal["status"] == "ok"
    assert formal["detail"]["reason"] == (
        "formal_candidate_index_absent_with_inherited_artifacts"
    )
    assert formal["detail"]["inherited_candidates"] == 1
    assert formal["detail"]["checked_candidates"] == 0
    assert formal["detail"]["orphan_artifacts"] == []

    orphan = indexed_artifact.parent.parent / "orphan" / "candidate.patch.json"
    orphan.parent.mkdir(parents=True)
    _write_json(orphan, {"schema": "scion.formal_candidate_patch_artifact.v3"})
    checks = _summarize_artifact_checks(
        root=root,
        report_dir=report_dir,
        manifest=manifest,
        brief_path=brief_path,
        brief=brief,
    )
    formal = checks["formal_candidate_diff_integrity"]
    assert formal["status"] == "failed"
    assert formal["detail"]["orphan_artifacts"] == [str(orphan)]
    assert formal["detail"]["failures"] == [
        {
            "reason": "candidate_metadata_not_indexed",
            "orphan_artifacts": [str(orphan)],
        }
    ]

    snapshot_index.write_text(
        snapshot_index.read_text(encoding="utf-8")
        + json.dumps(
            {
                "candidate_id": "forged-inherited-candidate",
                "artifact_status": "recorded",
                "artifact_ref": orphan.relative_to(root / "campaign").as_posix(),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    checks = _summarize_artifact_checks(
        root=root,
        report_dir=report_dir,
        manifest=manifest,
        brief_path=brief_path,
        brief=brief,
    )
    formal = checks["formal_candidate_diff_integrity"]
    assert formal["status"] == "failed"
    assert formal["detail"]["inherited_candidates"] == 0
    assert formal["detail"]["failures"][0]["reason"] == (
        "resume_candidate_index_snapshot_integrity_mismatch"
    )


def test_artifact_acceptance_rejects_missing_inherited_candidate_metadata(
    tmp_path: Path,
) -> None:
    root, report_dir, manifest, brief_path, brief = _write_ready_artifacts(tmp_path)
    indexed_artifact, _ = _write_v3_formal_candidate(root)
    live_index = (
        root / "campaign" / "artifacts" / "formal_candidates" / "index.jsonl"
    )
    snapshot_index = (
        root
        / "resume_snapshot"
        / "campaign"
        / "artifacts"
        / "formal_candidates"
        / "index.jsonl"
    )
    snapshot_index.parent.mkdir(parents=True)
    live_index.replace(snapshot_index)
    snapshot_manifest = root / "resume_snapshot" / "resume_source_manifest.v1.json"
    _write_json(
        snapshot_manifest,
        {
            "schema_version": "scion.launcher_resume_preparation.v1",
            "terminal_artifacts": [
                {
                    "original_ref": "artifacts/formal_candidates/index.jsonl",
                    "snapshot_ref": (
                        "resume_snapshot/campaign/artifacts/formal_candidates/"
                        "index.jsonl"
                    ),
                    "size_bytes": snapshot_index.stat().st_size,
                    "sha256": sha256(snapshot_index.read_bytes()).hexdigest(),
                }
            ],
        },
    )
    _write_json(
        root / "prepared_run_manifest.v1.json",
        {"resume_snapshot_ref": "resume_snapshot/resume_source_manifest.v1.json"},
    )
    indexed_artifact.unlink()

    checks = _summarize_artifact_checks(
        root=root,
        report_dir=report_dir,
        manifest=manifest,
        brief_path=brief_path,
        brief=brief,
    )
    formal = checks["formal_candidate_diff_integrity"]
    assert formal["status"] == "failed"
    assert formal["detail"]["inherited_candidates"] == 0
    assert formal["detail"]["failures"][0]["reason"] == (
        "resume_candidate_index_metadata_missing"
    )


def _summarize_artifact_checks(
    *,
    root: Path,
    report_dir: Path,
    manifest: dict[str, object],
    brief_path: Path,
    brief: dict[str, object],
) -> dict[str, dict[str, object]]:
    return PostrunArtifactAcceptancePort().summarize(
        root=root,
        report_dir=report_dir,
        rebuild_manifest=manifest,
        inventory_source="stored_postrun_inventory",
        inventory_path=report_dir / "inventory" / "inventory.v1.json",
        analysis_brief_path=brief_path,
        analysis_brief=brief,
        postrun_counts={"inventory": 1},
    ).to_payloads()


def _write_v3_formal_candidate(
    root: Path,
    *,
    revert_to_champion: bool = False,
) -> tuple[Path, dict[str, object]]:
    campaign_dir = root / "campaign"
    base_workspace = campaign_dir / "champions" / "v1"
    base_workspace.mkdir(parents=True)
    (base_workspace / "solver.py").write_text("VALUE = 0\n", encoding="utf-8")
    materializer = WorkspaceMaterializer(
        str(campaign_dir),
        editable_patterns=("*.py",),
    )
    branch = BranchController().create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver-hash",
            code_snapshot_path=str(base_workspace),
            code_snapshot_hash="champion-hash",
        )
    )
    workspace = materializer.create_branch_workspace(
        branch.branch_id,
        str(base_workspace),
    )
    recorder = FormalCandidatePatchArtifactRecorder(
        campaign_dir,
        protocol_version="protocol-v3",
        problem_spec_hash="problem-hash",
        split_manifest_hash="split-hash",
        seed_ledger_hash="seed-hash",
        identity_manifest_for=materializer.editable_identity_manifest,
    )
    protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=2,
            wins=1,
            losses=0,
            ties=1,
            win_rate=0.5,
            median_delta=1.0,
            ci_low=0.0,
            ci_high=2.0,
        ),
        gate_outcome="expand",
        reason_codes=("SCREENING_EXPAND",),
        exposed_summary="postrun v3",
        raw_metrics_ref="metrics/screening.json",
    )

    def record_patch(
        patch: PatchProposal,
        *,
        hypothesis_id: str,
        parent_hypothesis_id: str | None = None,
    ) -> str:
        branch.current_code_hash = materializer.apply_patch(workspace, patch)
        branch.last_clean_code_hash = branch.current_code_hash
        artifact_ref = recorder.record(
            branch=branch,
            hypothesis=HypothesisProposal(
                hypothesis_text="Postrun v3 materialization acceptance.",
                change_locus="solver_design",
                action="modify",
                target_file="solver.py",
            ),
            h_record=HypothesisRecord(
                hypothesis_id=hypothesis_id,
                parent_hypothesis_id=parent_hypothesis_id,
                branch_id=branch.branch_id,
                change_locus="solver_design",
                action="modify",
                status="running",
                target_file="solver.py",
            ),
            patch=patch,
            protocol_result=protocol_result,
            canary_result=CanaryResult(passed=True),
            contract_result=ContractResult(passed=True, checks=()),
            verification_result=VerificationResult(passed=True, checks=()),
            decision=Decision.EXPAND_SCREENING,
            decision_reason_codes=("SCREENING_EXPAND",),
            workspace=workspace,
            base_workspace=str(base_workspace),
        )
        assert artifact_ref
        return artifact_ref

    artifact_ref = record_patch(
        PatchProposal("solver.py", "modify", "VALUE = 1\n"),
        hypothesis_id="h-postrun-v3-r1",
    )
    if revert_to_champion:
        artifact_ref = record_patch(
            PatchProposal("solver.py", "modify", "VALUE = 0\n"),
            hypothesis_id="h-postrun-v3-r2",
            parent_hypothesis_id="h-postrun-v3-r1",
        )
    assert artifact_ref
    artifact_path = campaign_dir / artifact_ref
    return artifact_path, json.loads(artifact_path.read_text(encoding="utf-8"))


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
