from __future__ import annotations

import threading
from pathlib import Path

from scion.core.branch import BranchController
from scion.core.models import ChampionState, HypothesisProposal, OperatorConfig, PatchProposal
from scion.core.workspace_lifecycle import WorkspaceLifecycleService


class FakeMaterializer:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.cleaned: list[str] = []
        self.created: list[tuple[str, str]] = []
        self.applied: list[tuple[str, str]] = []

    def create_branch_workspace(self, branch_id: str, source_snapshot: str) -> str:
        workspace = self.tmp_path / f"ws-{len(self.created)}"
        workspace.mkdir()
        self.created.append((branch_id, source_snapshot))
        return str(workspace)

    def apply_patch(self, workspace: str, patch: PatchProposal) -> str:
        self.applied.append((workspace, patch.file_path))
        return f"hash-{len(self.applied)}"

    def cleanup(self, workspace: str) -> None:
        self.cleaned.append(workspace)


def _operator() -> OperatorConfig:
    return OperatorConfig(
        name="ls",
        file_path="operators/ls.py",
        category="local_search",
        weight=1.0,
        class_name="LocalSearch",
    )


def _champion(*, with_pool: bool = False) -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={"ls": _operator()} if with_pool else {},
        solver_config_hash="solver",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="hash",
    )


def _service(tmp_path: Path, *, champion: ChampionState | None = None):
    ctrl = BranchController()
    champion = champion or _champion()
    branch = ctrl.create_branch(champion)
    materializer = FakeMaterializer(tmp_path)
    workspaces: dict[str, str] = {}
    patches: dict[str, PatchProposal] = {}
    service = WorkspaceLifecycleService(
        materializer=materializer,
        branch_controller=ctrl,
        branch_workspaces=workspaces,
        branch_patches=patches,
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
    )
    return service, branch, ctrl, materializer, workspaces, patches


def test_setup_workspace_reuses_existing_verified_branch_workspace(tmp_path: Path) -> None:
    service, branch, ctrl, materializer, workspaces, _ = _service(tmp_path)
    existing = tmp_path / "existing"
    existing.mkdir()
    workspaces[branch.branch_id] = str(existing)
    ctrl.record_candidate_code(branch.branch_id, "candidate-hash")
    ctrl.record_verification_pass(branch.branch_id, "candidate-hash")

    workspace = service.setup_workspace(branch)

    assert workspace == str(existing)
    assert materializer.created == []
    assert materializer.cleaned == []


def test_setup_workspace_force_champion_discards_existing_workspace(tmp_path: Path) -> None:
    service, branch, _, materializer, workspaces, _ = _service(tmp_path)
    existing = tmp_path / "existing"
    existing.mkdir()
    workspaces[branch.branch_id] = str(existing)

    workspace = service.setup_workspace(branch, force_champion=True)

    assert workspace is not None
    assert workspace != str(existing)
    assert materializer.cleaned == [str(existing)]
    assert materializer.created == [(branch.branch_id, "/tmp/champion")]
    assert workspaces[branch.branch_id] == workspace


def test_setup_workspace_discards_suspect_workspace_even_when_hashes_match(
    tmp_path: Path,
) -> None:
    service, branch, ctrl, materializer, workspaces, _ = _service(tmp_path)
    existing = tmp_path / "existing"
    existing.mkdir()
    workspaces[branch.branch_id] = str(existing)
    ctrl.record_candidate_code(branch.branch_id, "candidate-hash")
    ctrl.record_verification_pass(branch.branch_id, "candidate-hash")
    branch.branch_code_status = "telemetry_wiring_suspect"
    branch.last_telemetry_outcome = "activation_missing_or_wiring_suspect"

    workspace = service.setup_workspace(branch)

    assert workspace is not None
    assert workspace != str(existing)
    assert materializer.cleaned == [str(existing)]
    assert materializer.created == [(branch.branch_id, "/tmp/champion")]
    assert workspaces[branch.branch_id] == workspace


def test_apply_patch_records_candidate_hash_without_clean_hash(tmp_path: Path) -> None:
    service, branch, ctrl, materializer, _, patches = _service(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    patch = PatchProposal(
        file_path="operators/new.py",
        action="create",
        code_content="class New: pass\n",
    )

    applied = service.apply_patch(
        branch,
        str(workspace),
        patch,
        remember_patch=True,
    )

    assert applied.code_hash == "hash-1"
    assert materializer.applied == [(str(workspace), "operators/new.py")]
    assert patches[branch.branch_id] is patch
    stored = ctrl.get_branch(branch.branch_id)
    assert stored.current_code_hash == "hash-1"
    assert stored.last_clean_code_hash is None


def test_regressed_followup_restore_recovers_checkpoint_workspace_and_patch(
    tmp_path: Path,
) -> None:
    service, branch, ctrl, materializer, workspaces, patches = _service(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    candidate_file = workspace / "operators" / "existing.py"
    candidate_file.parent.mkdir()
    candidate_file.write_text("# checkpoint\n", encoding="utf-8")
    workspaces[branch.branch_id] = str(workspace)
    ctrl.record_candidate_code(branch.branch_id, "checkpoint-hash")
    ctrl.record_verification_pass(branch.branch_id, "checkpoint-hash")
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.last_telemetry_outcome = "case_level_positive_signal"
    branch.branch_mechanism_ids = ("mechanism",)
    checkpoint_patch = PatchProposal(
        file_path="operators/existing.py",
        action="modify",
        code_content="# checkpoint\n",
    )
    patches[branch.branch_id] = checkpoint_patch
    followup_patch = PatchProposal(
        file_path="operators/existing.py",
        action="modify",
        code_content="# regressed\n",
    )

    service.apply_patch(
        branch,
        str(workspace),
        followup_patch,
        remember_patch=True,
    )
    checkpoint_records = service.branch_checkpoint_registry.records_for_lineage(
        branch.lineage_id or branch.branch_id
    )
    assert len(checkpoint_records) == 1
    checkpoint_record = checkpoint_records[0].record
    assert checkpoint_record.branch_id == branch.branch_id
    assert checkpoint_record.lineage_id == (branch.lineage_id or branch.branch_id)
    assert checkpoint_record.code_hash == "checkpoint-hash"
    assert checkpoint_record.branch_code_status == "active_weak_positive"
    assert checkpoint_record.screening_tier == "weak_positive"
    assert checkpoint_record.patch_digest is not None
    assert branch.best_quality_checkpoint_id == checkpoint_record.checkpoint_id
    assert branch.last_valid_checkpoint_id == checkpoint_record.checkpoint_id
    candidate_file.write_text("# regressed\n", encoding="utf-8")
    ctrl.record_verification_pass(branch.branch_id, "regressed-hash")

    restored = service.restore_branch_checkpoint(
        branch,
        reason="screening_regression",
        reason_codes=("quality_regression",),
    )

    stored = ctrl.get_branch(branch.branch_id)
    restored_file = Path(workspaces[branch.branch_id]) / "operators" / "existing.py"
    assert restored is True
    assert restored_file.read_text(encoding="utf-8") == "# checkpoint\n"
    assert stored.current_code_hash == "checkpoint-hash"
    assert stored.last_clean_code_hash == "checkpoint-hash"
    assert stored.branch_code_status == "active_weak_positive"
    assert stored.last_screening_feedback_tier == "weak_positive"
    assert stored.last_telemetry_outcome == "case_level_positive_signal"
    assert stored.branch_mechanism_ids == ("mechanism",)
    assert stored.rollback_count == 1
    assert stored.last_rollback_reason == "screening_regression"
    updated_record = service.branch_checkpoint_registry.records_for_lineage(
        branch.lineage_id or branch.branch_id
    )[0].record
    assert updated_record.counters.rollback_count == 1
    assert "quality_regression" in (
        updated_record.diagnostics.lifecycle_action_reason_codes
    )
    assert patches[branch.branch_id] is checkpoint_patch
    assert materializer.cleaned == [str(workspace)]
    assert Path(updated_record.workspace_ref).is_dir()


def test_last_valid_checkpoint_is_recorded_for_verified_branch(
    tmp_path: Path,
) -> None:
    service, branch, ctrl, _, workspaces, _ = _service(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "operators").mkdir()
    (workspace / "operators" / "existing.py").write_text(
        "# last valid\n",
        encoding="utf-8",
    )
    workspaces[branch.branch_id] = str(workspace)
    ctrl.record_candidate_code(branch.branch_id, "valid-hash")
    ctrl.record_verification_pass(branch.branch_id, "valid-hash")
    branch.branch_code_status = "clean"
    branch.last_screening_feedback_tier = None
    patch = PatchProposal(
        file_path="operators/existing.py",
        action="modify",
        code_content="# followup\n",
    )

    service.apply_patch(branch, str(workspace), patch, remember_patch=True)

    records = service.branch_checkpoint_registry.records_for_lineage(
        branch.lineage_id or branch.branch_id
    )
    assert len(records) == 1
    assert records[0].record.screening_tier == "last_valid"
    assert records[0].record.code_hash == "valid-hash"
    assert branch.last_valid_checkpoint_id == records[0].record.checkpoint_id


def test_checkpoint_registry_keeps_bounded_best_quality_and_last_valid(
    tmp_path: Path,
) -> None:
    service, branch, ctrl, _, workspaces, _ = _service(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "operators").mkdir()
    (workspace / "operators" / "existing.py").write_text(
        "# checkpoint\n",
        encoding="utf-8",
    )
    workspaces[branch.branch_id] = str(workspace)
    tiers = [
        ("weak_positive", "active_weak_positive", "hash-weak"),
        ("no_effect", "active_no_effect", "hash-no-effect"),
        ("marginal", "active_marginal", "hash-marginal"),
    ]

    for idx, (tier, status, code_hash) in enumerate(tiers):
        ctrl.record_candidate_code(branch.branch_id, code_hash)
        ctrl.record_verification_pass(branch.branch_id, code_hash)
        branch.last_screening_feedback_tier = tier
        branch.branch_code_status = status
        service.apply_patch(
            branch,
            str(workspace),
            PatchProposal(
                file_path="operators/existing.py",
                action="modify",
                code_content=f"# followup {idx}\n",
            ),
            remember_patch=True,
        )

    records = service.branch_checkpoint_registry.records_for_lineage(
        branch.lineage_id or branch.branch_id
    )
    assert len(records) == 2
    retained_tiers = {record.record.screening_tier for record in records}
    assert retained_tiers == {"weak_positive", "marginal"}
    summary = service.checkpoint_summary()[branch.lineage_id or branch.branch_id]
    assert summary["checkpoint_count"] == 2
    assert summary["best_quality_checkpoint_id"] == branch.best_quality_checkpoint_id
    assert summary["last_valid_checkpoint_id"] == branch.last_valid_checkpoint_id


def test_record_verification_pass_updates_clean_hash(tmp_path: Path) -> None:
    service, branch, ctrl, _, _, _ = _service(tmp_path)

    service.record_verification_pass(branch, "verified-hash")

    stored = ctrl.get_branch(branch.branch_id)
    assert stored.current_code_hash == "verified-hash"
    assert stored.last_clean_code_hash == "verified-hash"


def test_apply_patch_with_empty_champion_pool_skips_registry_sync(tmp_path: Path) -> None:
    service, branch, _, materializer, _, _ = _service(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    patch = PatchProposal("operators/new.py", "create", "class New: pass\n")
    hypothesis = HypothesisProposal(
        hypothesis_text="Add bounded move.",
        change_locus="local_search",
        action="create_new",
    )

    applied = service.apply_patch(
        branch,
        str(workspace),
        patch,
        hypothesis=hypothesis,
        sync_registry=True,
    )

    assert applied.code_hash == "hash-1"
    assert materializer.applied == [(str(workspace), "operators/new.py")]
