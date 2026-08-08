from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import threading
from typing import Iterable

import pytest

from scion.core.branch import BranchController
from scion.core.fixed_candidate_replay import (
    build_fixed_candidate_replay_manifest,
    materialize_candidate_workspace,
)
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
    OperatorConfig,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.core.workspace_lifecycle import WorkspaceLifecycleService
from scion.runtime.workspace import WorkspaceMaterializer


class _FormalV3Harness:
    def __init__(
        self,
        tmp_path: Path,
        *,
        base_files: dict[str, str],
        editable_patterns: Iterable[str] = ("*.py",),
        operator_pool: dict[str, OperatorConfig] | None = None,
    ) -> None:
        self.campaign_dir = tmp_path / "campaign"
        self.base_workspace = self.campaign_dir / "champions" / "champion_v1"
        self.base_workspace.mkdir(parents=True)
        for relative_path, content in base_files.items():
            target = self.base_workspace / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        self.materializer = WorkspaceMaterializer(
            str(self.campaign_dir),
            editable_patterns=editable_patterns,
        )
        self.champion = ChampionState(
            version=1,
            operator_pool=operator_pool or {},
            solver_config_hash="solver-hash",
            code_snapshot_path=str(self.base_workspace),
            code_snapshot_hash="champion-hash",
        )
        self.branch_controller = BranchController()
        self.branch = self.branch_controller.create_branch(self.champion)
        self.workspace = Path(
            self.materializer.create_branch_workspace(
                self.branch.branch_id,
                str(self.base_workspace),
            )
        )
        self.lifecycle = WorkspaceLifecycleService(
            materializer=self.materializer,
            branch_controller=self.branch_controller,
            branch_workspaces={self.branch.branch_id: str(self.workspace)},
            branch_patches={},
            champion_lock=threading.Lock(),
            get_champion=lambda: self.champion,
        )
        self.recorder = FormalCandidatePatchArtifactRecorder(
            self.campaign_dir,
            protocol_version="protocol-v3",
            problem_spec_hash="problem-hash",
            split_manifest_hash="split-hash",
            seed_ledger_hash="seed-hash",
            identity_manifest_for=self.materializer.editable_identity_manifest,
        )
        self.protocol_result = ProtocolResult(
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
            exposed_summary="formal v3 boundary test",
            raw_metrics_ref="metrics/screening.json",
        )

    def record(
        self,
        patch: PatchProposal,
        *,
        hypothesis_id: str,
        parent_hypothesis_id: str | None = None,
    ) -> dict[str, object]:
        hypothesis = HypothesisProposal(
            hypothesis_text=f"Boundary test {hypothesis_id}.",
            change_locus="solver_design",
            action=(
                "remove"
                if patch.action == "delete"
                else "create_new"
                if patch.action == "create"
                else "modify"
            ),
            target_file=patch.file_path,
        )
        applied = self.lifecycle.apply_patch(
            self.branch,
            str(self.workspace),
            patch,
            hypothesis=hypothesis,
            sync_registry=bool(self.champion.operator_pool),
        )
        self.branch.current_code_hash = applied.code_hash
        self.branch.last_clean_code_hash = self.branch.current_code_hash
        target_file = patch.file_path
        artifact_ref = self.recorder.record(
            branch=self.branch,
            hypothesis=hypothesis,
            h_record=HypothesisRecord(
                hypothesis_id=hypothesis_id,
                parent_hypothesis_id=parent_hypothesis_id,
                branch_id=self.branch.branch_id,
                change_locus="solver_design",
                action=patch.action,
                status="running",
                target_file=target_file,
            ),
            patch=patch,
            protocol_result=self.protocol_result,
            canary_result=CanaryResult(passed=True),
            contract_result=ContractResult(passed=True, checks=()),
            verification_result=VerificationResult(passed=True, checks=()),
            decision=Decision.EXPAND_SCREENING,
            decision_reason_codes=("SCREENING_EXPAND",),
            workspace=str(self.workspace),
            base_workspace=str(self.base_workspace),
        )
        assert artifact_ref
        return json.loads(
            (self.campaign_dir / artifact_ref).read_text(encoding="utf-8")
        )

    def materialize(
        self,
        artifact: dict[str, object],
        *,
        output_name: str,
    ) -> Path:
        return materialize_candidate_workspace(
            candidate={
                "candidate_id": artifact["candidate_id"],
                "hypothesis_id": artifact["hypothesis_id"],
                "branch_id": artifact["branch_id"],
            },
            candidate_patch=artifact,
            source_campaign_dir=self.campaign_dir,
            output_dir=self.campaign_dir / output_name,
            arm="on",
        )


def test_v3_two_rounds_modifying_same_file_replays_latest_content(
    tmp_path: Path,
) -> None:
    harness = _FormalV3Harness(tmp_path, base_files={"solver.py": "VALUE = 0\n"})
    harness.record(
        PatchProposal("solver.py", "modify", "VALUE = 1\n"),
        hypothesis_id="h-r1",
    )
    artifact = harness.record(
        PatchProposal("solver.py", "modify", "VALUE = 2\n"),
        hypothesis_id="h-r2",
        parent_hypothesis_id="h-r1",
    )

    assert artifact["proposal_target_files"] == ["solver.py"]
    assert artifact["inherited_files"] == []
    closure = artifact["replay_materialization"]
    assert isinstance(closure, dict)
    assert [entry["file_path"] for entry in closure["files"]] == ["solver.py"]
    assert closure["files"][0]["code_content"] == "VALUE = 2\n"
    replay = harness.materialize(artifact, output_name="same-file-replay")
    assert (replay / "solver.py").read_text(encoding="utf-8") == "VALUE = 2\n"


def test_v3_idempotent_record_restores_missing_proposal_diff_and_rejects_drift(
    tmp_path: Path,
) -> None:
    harness = _FormalV3Harness(tmp_path, base_files={"solver.py": "VALUE = 0\n"})
    patch = PatchProposal("solver.py", "modify", "VALUE = 1\n")
    harness.record(patch, hypothesis_id="h-idempotent")
    metadata_path = next(
        harness.campaign_dir.glob(
            "artifacts/formal_candidates/*/*/candidate.patch.json"
        )
    )
    proposal_diff = metadata_path.with_name("proposal.diff")
    candidate_diff = metadata_path.with_name("candidate.diff")

    proposal_diff.unlink()
    index_path = (
        harness.campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    )
    index_path.unlink()
    harness.record(patch, hypothesis_id="h-idempotent")
    assert proposal_diff.is_file()
    index_rows = [
        json.loads(line)
        for line in index_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(index_rows) == 1

    original_metadata = metadata_path.read_text(encoding="utf-8")
    tampered_metadata = json.loads(original_metadata)
    tampered_metadata["replay_materialization"]["files"][0]["code_content"] = (
        "VALUE = 999\n"
    )
    metadata_path.write_text(
        json.dumps(tampered_metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError,
        match="existing formal candidate metadata conflicts with record",
    ):
        harness.record(patch, hypothesis_id="h-idempotent")
    metadata_path.write_text(original_metadata, encoding="utf-8")

    candidate_diff.write_text("corrupted diff\n", encoding="utf-8")
    with pytest.raises(
        ValueError,
        match="formal candidate artifact content mismatch: candidate.diff",
    ):
        harness.record(patch, hypothesis_id="h-idempotent")


def test_v3_repeat_screening_with_new_metrics_ref_gets_distinct_artifact(
    tmp_path: Path,
) -> None:
    harness = _FormalV3Harness(tmp_path, base_files={"solver.py": "VALUE = 0\n"})
    patch = PatchProposal("solver.py", "modify", "VALUE = 1\n")
    first = harness.record(patch, hypothesis_id="h-repeat")
    harness.protocol_result = replace(
        harness.protocol_result,
        raw_metrics_ref="metrics/screening-repeat.json",
    )
    second = harness.record(patch, hypothesis_id="h-repeat")

    assert first["candidate_id"] != second["candidate_id"]
    assert first["experiment_ref"] == "metrics/screening.json"
    assert second["experiment_ref"] == "metrics/screening-repeat.json"
    assert (
        len(
            list(
                harness.campaign_dir.glob(
                    "artifacts/formal_candidates/*/*/candidate.patch.json"
                )
            )
        )
        == 2
    )


def test_v3_create_delete_then_revert_to_champion_has_empty_closure(
    tmp_path: Path,
) -> None:
    harness = _FormalV3Harness(
        tmp_path,
        base_files={"existing.py": "VALUE = 'base'\n"},
    )
    r1 = harness.record(
        PatchProposal(
            file_path="created.py",
            action="create",
            code_content="VALUE = 'created'\n",
            additional_changes=(
                {
                    "file_path": "existing.py",
                    "action": "delete",
                    "code_content": "",
                },
            ),
        ),
        hypothesis_id="h-r1",
    )
    r1_files = {
        entry["file_path"]: entry for entry in r1["replay_materialization"]["files"]
    }
    assert r1_files["created.py"]["action"] == "create"
    assert r1_files["existing.py"]["action"] == "delete"
    r1_replay = harness.materialize(r1, output_name="create-delete-replay")
    assert (r1_replay / "created.py").is_file()
    assert not (r1_replay / "existing.py").exists()

    created_source_sha = hashlib.sha256(b"VALUE = 'created'\n").hexdigest()
    r2 = harness.record(
        PatchProposal(
            file_path="created.py",
            action="delete",
            code_content="",
            additional_changes=(
                {
                    "file_path": "existing.py",
                    "action": "create",
                    "code_content": "VALUE = 'base'\n",
                },
            ),
            repair_attribution=(
                {
                    "repair_kind": "typed_edit_normalization",
                    "file_path": "created.py",
                    "source_owner": "branch_helper",
                    "source_provenance": "branch_workspace",
                    "source_record_digest": created_source_sha,
                },
            ),
        ),
        hypothesis_id="h-r2",
        parent_hypothesis_id="h-r1",
    )
    assert r2["proposal_target_files"] == ["created.py", "existing.py"]
    assert r2["target_files"] == []
    assert r2["inherited_files"] == []
    assert r2["activation_files"] == []
    assert r2["replay_materialization"]["files"] == []
    manifest = build_fixed_candidate_replay_manifest(
        harness.campaign_dir,
        source_arm="on",
        comparison_id="empty-closure",
        generated_at="2026-07-15T00:00:00+00:00",
    )
    candidate = next(
        item for item in manifest["candidates"] if item["hypothesis_id"] == "h-r2"
    )
    assert candidate["target_files"] == []
    replay = harness.materialize(r2, output_name="empty-closure-replay")
    assert not (replay / "created.py").exists()
    assert (replay / "existing.py").read_text(encoding="utf-8") == ("VALUE = 'base'\n")
    assert harness.materializer.compute_code_hash(str(replay)) == (
        harness.branch.current_code_hash
    )


def test_v3_activation_file_is_separate_from_proposal_and_inherited_scope(
    tmp_path: Path,
) -> None:
    harness = _FormalV3Harness(
        tmp_path,
        base_files={
            "operators/seed.py": "class Seed:\n    pass\n",
            "registry.yaml": (
                "operators:\n"
                "  - name: seed\n"
                "    file_path: operators/seed.py\n"
                "    category: solver_design\n"
                "    weight: 1.0\n"
                "    class_name: Seed\n"
            ),
        },
        editable_patterns=("operators/*.py",),
        operator_pool={
            "seed": OperatorConfig(
                name="seed",
                file_path="operators/seed.py",
                category="solver_design",
                weight=1.0,
                class_name="Seed",
            )
        },
    )
    artifact = harness.record(
        PatchProposal(
            file_path="operators/new_move.py",
            action="create",
            code_content="class NewMove:\n    pass\n",
        ),
        hypothesis_id="h-activation",
    )

    assert artifact["proposal_target_files"] == ["operators/new_move.py"]
    assert artifact["activation_files"] == ["registry.yaml"]
    assert artifact["inherited_files"] == []
    closure_files = {
        entry["file_path"]: entry
        for entry in artifact["replay_materialization"]["files"]
    }
    registry = closure_files["registry.yaml"]
    assert registry["candidate_attribution"]["scope"] == "runtime_activation"
    assert registry["source_attribution"]["origin"] == "runtime_activation"
    replay = harness.materialize(artifact, output_name="activation-replay")
    assert (replay / "registry.yaml").read_bytes() == (
        harness.workspace / "registry.yaml"
    ).read_bytes()


def test_v3_materialization_ignores_legacy_identity_manifests_and_hashes(
    tmp_path: Path,
) -> None:
    harness = _FormalV3Harness(tmp_path, base_files={"solver.py": "VALUE = 0\n"})
    artifact = harness.record(
        PatchProposal("solver.py", "modify", "VALUE = 1\n"),
        hypothesis_id="h-tamper",
    )
    closure = artifact["replay_materialization"]
    assert isinstance(closure, dict)
    closure["patch_digest"] = "not-used"
    closure["base_identity_manifest"] = {"invalid": True}
    closure["candidate_identity_manifest"] = {"invalid": True}
    artifact["replay_identity"] = {"identity_status": "degraded"}
    replay = harness.materialize(artifact, output_name="identity-noise")
    assert (replay / "solver.py").read_text(encoding="utf-8") == "VALUE = 1\n"
