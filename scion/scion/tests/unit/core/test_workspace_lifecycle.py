from __future__ import annotations

import threading
from pathlib import Path

from scion.core.branch import BranchController
from scion.core.models import ChampionState, OperatorConfig, PatchProposal
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


def _champion(*, with_pool: bool = False) -> ChampionState:
    operator = OperatorConfig(
        name="ls",
        file_path="operators/ls.py",
        category="local_search",
        weight=1.0,
        class_name="LocalSearch",
    )
    return ChampionState(
        version=1,
        operator_pool={"ls": operator} if with_pool else {},
        solver_config_hash="solver",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="hash",
    )


def _service(tmp_path: Path, *, champion: ChampionState | None = None):
    controller = BranchController()
    champion = champion or _champion()
    branch = controller.create_branch(champion)
    materializer = FakeMaterializer(tmp_path)
    workspaces: dict[str, str] = {}
    patches: dict[str, PatchProposal] = {}
    service = WorkspaceLifecycleService(
        materializer=materializer,
        branch_controller=controller,
        branch_workspaces=workspaces,
        branch_patches=patches,
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
    )
    return service, branch, controller, materializer, workspaces, patches


def test_setup_workspace_reuses_existing_verified_branch_workspace(tmp_path: Path) -> None:
    service, branch, controller, materializer, workspaces, _ = _service(tmp_path)
    existing = tmp_path / "existing"
    existing.mkdir()
    workspaces[branch.branch_id] = str(existing)
    controller.record_verification_pass(branch.branch_id, "candidate-hash")
    assert service.setup_workspace(branch) == str(existing)
    assert materializer.created == []


def test_missing_verified_branch_workspace_refuses_champion_fallback(
    tmp_path: Path,
) -> None:
    service, branch, controller, materializer, workspaces, _ = _service(tmp_path)
    missing = tmp_path / "missing-verified-workspace"
    workspaces[branch.branch_id] = str(missing)
    controller.record_verification_pass(branch.branch_id, "candidate-hash")

    assert service.setup_workspace(branch) is None
    assert materializer.created == []
    assert materializer.cleaned == []


def test_force_champion_discards_existing_workspace(tmp_path: Path) -> None:
    service, branch, _, materializer, workspaces, _ = _service(tmp_path)
    existing = tmp_path / "existing"
    existing.mkdir()
    workspaces[branch.branch_id] = str(existing)
    workspace = service.setup_workspace(branch, force_champion=True)
    assert workspace != str(existing)
    assert materializer.cleaned == [str(existing)]
    assert materializer.created == [(branch.branch_id, "/tmp/champion")]


def test_apply_patch_records_candidate_hash_and_optional_patch(tmp_path: Path) -> None:
    service, branch, controller, materializer, _, patches = _service(tmp_path)
    patch = PatchProposal(
        file_path="operators/new.py",
        action="create",
        code_content="class New: pass\n",
    )
    applied = service.apply_patch(branch, str(tmp_path), patch, remember_patch=True)
    assert applied.code_hash == "hash-1"
    assert patches[branch.branch_id] is patch
    stored = controller.get_branch(branch.branch_id)
    assert stored.current_code_hash == "hash-1"
    assert stored.last_clean_code_hash is None


def test_record_verification_pass_updates_clean_hash(tmp_path: Path) -> None:
    service, branch, controller, *_ = _service(tmp_path)
    service.record_verification_pass(branch, "verified")
    stored = controller.get_branch(branch.branch_id)
    assert stored.current_code_hash == "verified"
    assert stored.last_clean_code_hash == "verified"
