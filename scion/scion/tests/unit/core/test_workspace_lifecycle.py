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
