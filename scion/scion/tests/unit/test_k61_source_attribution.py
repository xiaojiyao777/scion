from __future__ import annotations

import json
from pathlib import Path

import pytest

from scion.core.branch import BranchController
from scion.core.fixed_candidate_replay import (
    build_fixed_candidate_replay_manifest,
    materialize_candidate_workspace,
)
from scion.core.formal_candidate_artifacts import (
    FormalCandidatePatchArtifactRecorder,
)
from scion.core.models import (
    CanaryResult,
    ChampionState,
    ContractResult,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
    PatchFileChange,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.proposal.edit_protocol.source_discovery import (
    source_digest_for_content,
    source_records_from_context,
)
from scion.proposal.engine.parsing import _parse_patch
from scion.runtime.workspace import WorkspaceMaterializer


def _editable_sources(primary: str, integration: str) -> dict[str, object]:
    return {
        "approved_target": "solver.py",
        "sources": [
            {
                "path": "solver.py",
                "content": primary,
            },
            {
                "path": "scheduler.py",
                "content": integration,
            },
        ],
        "target_api_guidance": "",
    }


def _multi_file_patch(primary: str, integration: str):
    return _parse_patch(
        {
            "file_path": "solver.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": source_digest_for_content(primary),
            "old_string": "def solve():",
            "new_string": "def solve(value=0):",
            "replace_all": False,
            "content_after": None,
            "full_file_reason": "",
            "evidence_refs": [],
            "additional_changes": [
                {
                    "file_path": "solver.py",
                    "action": "modify",
                    "edit_intent": "exact_replace",
                    "source_digest": source_digest_for_content(primary),
                    "old_string": "def solve(value=0):\n    return 1",
                    "new_string": "def solve(value=0):\n    return 2",
                    "replace_all": False,
                    "content_after": None,
                    "full_file_reason": "",
                    "evidence_refs": [],
                },
                {
                    "file_path": "scheduler.py",
                    "action": "modify",
                    "edit_intent": "exact_replace",
                    "source_digest": source_digest_for_content(integration),
                    "old_string": "def schedule():",
                    "new_string": "def schedule(value=0):",
                    "replace_all": False,
                    "content_after": None,
                    "full_file_reason": "",
                    "evidence_refs": [],
                },
                {
                    "file_path": "scheduler.py",
                    "action": "modify",
                    "edit_intent": "exact_replace",
                    "source_digest": source_digest_for_content(integration),
                    "old_string": "def schedule(value=0):\n    return 1",
                    "new_string": "def schedule(value=0):\n    return 3",
                    "replace_all": False,
                    "content_after": None,
                    "full_file_reason": "",
                    "evidence_refs": [],
                },
            ],
            "test_hint": None,
        },
        context={"editable_source_context": _editable_sources(primary, integration)},
    )


def test_editable_source_context_requires_unique_canonical_paths() -> None:
    primary = "def solve():\n    return 1\n"
    integration = "def schedule():\n    return 1\n"
    source_context = _editable_sources(primary, integration)
    records = source_records_from_context({"editable_source_context": source_context})
    assert {path: record.content for path, record in records.items()} == {
        "solver.py": primary,
        "scheduler.py": integration,
    }

    sources = source_context["sources"]
    assert isinstance(sources, list)
    sources.append({"path": "solver.py", "content": primary})
    with pytest.raises(ValueError, match="duplicate editable source path"):
        source_records_from_context({"editable_source_context": source_context})


def test_direct_multi_file_edit_survives_artifact_and_fixed_replay(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    base_workspace = campaign_dir / "champions" / "champion_v1"
    candidate_workspace = campaign_dir / "workspaces" / "candidate"
    base_workspace.mkdir(parents=True)
    candidate_workspace.mkdir(parents=True)
    primary = "def solve():\n    return 1\n"
    integration = "def schedule():\n    return 1\n"
    (base_workspace / "solver.py").write_text(primary, encoding="utf-8")
    (base_workspace / "scheduler.py").write_text(integration, encoding="utf-8")
    patch = _multi_file_patch(primary, integration)
    patch.repair_attribution = (
        *patch.repair_attribution,
        {
            "repair_kind": "typed_edit_noop_dropped",
            "file_path": "scheduler.py",
            "reason": "exact_replace_noop",
        },
    )
    (candidate_workspace / "solver.py").write_text(
        patch.code_content,
        encoding="utf-8",
    )
    (candidate_workspace / "scheduler.py").write_text(
        patch.additional_changes[0].code_content,
        encoding="utf-8",
    )

    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver-hash",
            code_snapshot_path=str(base_workspace),
            code_snapshot_hash="champion-hash",
        )
    )
    branch.current_code_hash = "candidate-code-hash"
    hypothesis = HypothesisProposal(
        hypothesis_text="Coordinate construction and scheduling.",
        change_locus="solver_design",
        action="modify",
        target_file="solver.py",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-multi-file",
        branch_id=branch.branch_id,
        change_locus="solver_design",
        action="modify",
        status="running",
        target_file="solver.py",
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
        exposed_summary="multi-file screening",
        raw_metrics_ref="metrics/screening.json",
    )
    recorder = FormalCandidatePatchArtifactRecorder(
        campaign_dir,
        protocol_version="protocol-v3",
        problem_spec_hash="problem-hash",
        split_manifest_hash="split-hash",
        seed_ledger_hash="seed-hash",
    )
    artifact_ref = recorder.record(
        branch=branch,
        hypothesis=hypothesis,
        h_record=h_record,
        patch=patch,
        protocol_result=protocol_result,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        decision=Decision.EXPAND_SCREENING,
        decision_reason_codes=("SCREENING_EXPAND",),
        workspace=str(candidate_workspace),
        base_workspace=str(base_workspace),
    )

    assert artifact_ref
    artifact_path = campaign_dir / artifact_ref
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["schema"] == "scion.formal_candidate_patch_artifact.v2"
    normalization_events = artifact["patch"]["normalization_events"]
    assert {event["repair_kind"] for event in normalization_events} == {
        "typed_edit_normalization",
        "typed_edit_noop_dropped",
    }
    serial_events = [
        event
        for event in normalization_events
        if event.get("action") == "composed_serial_exact_replace_changes"
    ]
    assert {event["file_path"] for event in serial_events} == {
        "solver.py",
        "scheduler.py",
    }
    assert not any(
        event.get("repair_kind") == "patch_set_composition"
        for event in normalization_events
    )
    assert any(
        event
        == {
            "repair_kind": "typed_edit_noop_dropped",
            "file_path": "scheduler.py",
            "reason": "exact_replace_noop",
        }
        for event in normalization_events
    )
    files = {item["file_path"]: item for item in artifact["patch"]["files"]}
    assert "source_attribution" not in files["solver.py"]
    assert "source_attribution" not in files["scheduler.py"]

    manifest = build_fixed_candidate_replay_manifest(
        campaign_dir,
        source_arm="on",
        comparison_id="multi-file-source-attribution",
        generated_at="2026-07-13T00:00:00+00:00",
    )
    candidate = manifest["candidates"][0]
    assert candidate["target_files"] == ["solver.py", "scheduler.py"]

    replay_workspace = materialize_candidate_workspace(
        candidate=candidate,
        candidate_patch=artifact,
        source_campaign_dir=campaign_dir,
        output_dir=tmp_path / "replay",
        arm="on",
    )
    assert (replay_workspace / "solver.py").read_text(encoding="utf-8") == (
        patch.code_content
    )
    assert (replay_workspace / "scheduler.py").read_text(encoding="utf-8") == (
        patch.additional_changes[0].code_content
    )


def test_v3_replay_materializes_cumulative_branch_from_champion(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    base_workspace = campaign_dir / "champions" / "champion_v1"
    base_workspace.mkdir(parents=True)
    base_contents = {
        "a.py": "A = 'base'\n",
        "b.py": "B = 'base'\n",
        "c.py": "C = 'base'\n",
    }
    for file_path, content in base_contents.items():
        (base_workspace / file_path).write_text(content, encoding="utf-8")

    materializer = WorkspaceMaterializer(
        str(campaign_dir),
        editable_patterns=("*.py",),
    )
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver-hash",
            code_snapshot_path=str(base_workspace),
            code_snapshot_hash="champion-hash",
        )
    )
    candidate_workspace = Path(
        materializer.create_branch_workspace(branch.branch_id, str(base_workspace))
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
        exposed_summary="cumulative replay screening",
        raw_metrics_ref="metrics/screening.json",
    )
    gates = {
        "canary_result": CanaryResult(passed=True),
        "contract_result": ContractResult(passed=True, checks=()),
        "verification_result": VerificationResult(passed=True, checks=()),
        "decision": Decision.EXPAND_SCREENING,
        "decision_reason_codes": ("SCREENING_EXPAND",),
    }

    r1_patch = PatchProposal(
        file_path="a.py",
        action="modify",
        code_content="A = 'r1'\n",
        additional_changes=(
            PatchFileChange(
                file_path="b.py",
                action="modify",
                code_content="B = 'r1'\n",
            ),
        ),
    )
    branch.current_code_hash = materializer.apply_patch(
        str(candidate_workspace),
        r1_patch,
    )
    branch.last_clean_code_hash = branch.current_code_hash
    r1_record = HypothesisRecord(
        hypothesis_id="h-r1",
        branch_id=branch.branch_id,
        change_locus="solver_design",
        action="modify",
        status="running",
        target_file="a.py",
    )
    r1_ref = recorder.record(
        branch=branch,
        hypothesis=HypothesisProposal(
            hypothesis_text="R1 changes two files.",
            change_locus="solver_design",
            action="modify",
            target_file="a.py",
        ),
        h_record=r1_record,
        patch=r1_patch,
        protocol_result=protocol_result,
        workspace=str(candidate_workspace),
        base_workspace=str(base_workspace),
        **gates,
    )
    assert r1_ref

    r2_patch = PatchProposal(
        file_path="c.py",
        action="modify",
        code_content="C = 'r2'\n",
    )
    branch.current_code_hash = materializer.apply_patch(
        str(candidate_workspace),
        r2_patch,
    )
    branch.last_clean_code_hash = branch.current_code_hash
    r2_record = HypothesisRecord(
        hypothesis_id="h-r2",
        parent_hypothesis_id="h-r1",
        branch_id=branch.branch_id,
        change_locus="solver_design",
        action="modify",
        status="running",
        target_file="c.py",
    )
    r2_ref = recorder.record(
        branch=branch,
        hypothesis=HypothesisProposal(
            hypothesis_text="R2 changes only the third file.",
            change_locus="solver_design",
            action="modify",
            target_file="c.py",
        ),
        h_record=r2_record,
        patch=r2_patch,
        protocol_result=protocol_result,
        workspace=str(candidate_workspace),
        base_workspace=str(base_workspace),
        **gates,
    )
    assert r2_ref

    r1_artifact = json.loads((campaign_dir / r1_ref).read_text(encoding="utf-8"))
    r2_artifact = json.loads((campaign_dir / r2_ref).read_text(encoding="utf-8"))
    assert r1_artifact["schema"] == "scion.formal_candidate_patch_artifact.v3"
    assert [entry["file_path"] for entry in r1_artifact["patch"]["files"]] == [
        "a.py",
        "b.py",
    ]
    assert [
        entry["file_path"] for entry in r1_artifact["replay_materialization"]["files"]
    ] == ["a.py", "b.py"]

    assert r2_artifact["lineage_id"] == branch.lineage_id
    assert r2_artifact["parent_hypothesis_id"] == "h-r1"
    assert r2_artifact["proposal_target_files"] == ["c.py"]
    assert [entry["file_path"] for entry in r2_artifact["patch"]["files"]] == ["c.py"]
    assert r2_artifact["target_files"] == ["a.py", "b.py", "c.py"]
    assert r2_artifact["inherited_files"] == ["a.py", "b.py"]
    assert r2_artifact["activation_files"] == []
    assert r2_artifact["proposal_patch_digest"] == r2_artifact["patch"]["patch_digest"]
    assert (
        r2_artifact["formal_patch_digest"]
        == r2_artifact["replay_materialization"]["patch_digest"]
    )
    assert (
        r2_artifact["replay_identity"]["patch_digest"]
        == r2_artifact["formal_patch_digest"]
    )
    assert r2_artifact["proposal_patch_digest"] != r2_artifact["formal_patch_digest"]
    assert (
        r2_artifact["replay_materialization"]["candidate_identity_manifest"][
            "code_hash"
        ]
        == branch.current_code_hash
    )

    closure_files = {
        entry["file_path"]: entry
        for entry in r2_artifact["replay_materialization"]["files"]
    }
    for inherited_path in ("a.py", "b.py"):
        assert closure_files[inherited_path]["candidate_attribution"]["scope"] == (
            "inherited_verified"
        )
        assert "source_attribution" not in closure_files[inherited_path]
    assert closure_files["c.py"]["candidate_attribution"]["scope"] == (
        "current_proposal"
    )

    manifest = build_fixed_candidate_replay_manifest(
        campaign_dir,
        source_arm="on",
        comparison_id="cumulative-r1-r2",
        generated_at="2026-07-15T00:00:00+00:00",
    )
    r2_candidate = next(
        candidate
        for candidate in manifest["candidates"]
        if candidate["hypothesis_id"] == "h-r2"
    )
    assert r2_candidate["target_files"] == ["a.py", "b.py", "c.py"]
    replay_workspace = materialize_candidate_workspace(
        candidate=r2_candidate,
        candidate_patch=r2_artifact,
        source_campaign_dir=campaign_dir,
        output_dir=tmp_path / "replay-v3",
        arm="on",
    )
    for file_path in ("a.py", "b.py", "c.py"):
        assert (replay_workspace / file_path).read_bytes() == (
            candidate_workspace / file_path
        ).read_bytes()
    assert materializer.compute_code_hash(str(replay_workspace)) == (
        branch.current_code_hash
    )
