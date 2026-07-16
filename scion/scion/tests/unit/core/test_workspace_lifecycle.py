from __future__ import annotations

import threading
from pathlib import Path

import pytest

from scion.core.branch import BranchController
from scion.core.models import (
    ChampionState,
    HypothesisProposal,
    OperatorConfig,
    PatchFileChange,
    PatchProposal,
)
from scion.core.workspace_lifecycle import WorkspaceLifecycleService
from scion.runtime.workspace import WorkspaceMaterializer


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

    def compute_code_hash(self, workspace: str) -> str:
        return "candidate-hash"


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


def test_setup_workspace_reuses_existing_verified_branch_workspace(
    tmp_path: Path,
) -> None:
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


def test_rejected_cumulative_candidate_restores_clean_durable_identity(
    tmp_path: Path,
) -> None:
    champion_dir = tmp_path / "champion"
    (champion_dir / "operators").mkdir(parents=True)
    (champion_dir / "operators" / "solver.py").write_text("VALUE = 0\n")
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path=str(champion_dir),
        code_snapshot_hash="champion",
    )
    controller = BranchController()
    branch = controller.create_branch(champion)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("operators/*.py",),
    )
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
    hypothesis = HypothesisProposal(
        hypothesis_text="Improve the solver.",
        change_locus="solver_design",
        action="modify",
        target_file="operators/solver.py",
    )
    durable = service.setup_workspace(branch)
    assert durable is not None
    first_patch = PatchProposal(
        file_path="operators/solver.py",
        action="modify",
        code_content="VALUE = 1\n",
        additional_changes=(
            PatchFileChange(
                file_path="operators/helper.py",
                action="create",
                code_content="HELPER = 1\n",
            ),
        ),
    )
    first = service.apply_candidate_patch(
        branch,
        durable,
        first_patch,
        hypothesis=hypothesis,
        remember_patch=True,
    )
    assert (Path(durable) / "operators" / "solver.py").read_text() == "VALUE = 0\n"
    durable = service.promote_verified_candidate(
        branch,
        first.code_hash,
        first.workspace,
        "h-first-candidate",
    )
    clean_hash = materializer.compute_code_hash(durable)
    assert clean_hash == branch.current_code_hash == branch.last_clean_code_hash
    assert patches[branch.branch_id] is first_patch

    rejected_patch = PatchProposal(
        file_path="operators/solver.py",
        action="modify",
        code_content="VALUE = missing_name\n",
        additional_changes=(
            PatchFileChange(
                file_path="operators/helper.py",
                action="delete",
                code_content="",
            ),
        ),
    )
    rejected = service.apply_candidate_patch(
        branch,
        durable,
        rejected_patch,
        hypothesis=hypothesis,
        remember_patch=True,
    )
    assert rejected.code_hash != clean_hash
    assert (Path(durable) / "operators" / "solver.py").read_text() == "VALUE = 1\n"

    service.reject_candidate(branch, rejected.workspace)

    assert not Path(rejected.workspace).exists()
    assert (Path(durable) / "operators" / "solver.py").read_text() == "VALUE = 1\n"
    assert (Path(durable) / "operators" / "helper.py").exists()
    assert materializer.compute_code_hash(durable) == clean_hash
    assert branch.current_code_hash == clean_hash
    assert branch.last_clean_code_hash == clean_hash
    assert patches[branch.branch_id] is first_patch


def test_reject_cleanup_failure_leaves_debris_but_clears_pending_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    champion_dir = tmp_path / "champion"
    (champion_dir / "operators").mkdir(parents=True)
    (champion_dir / "operators" / "solver.py").write_text("VALUE = 0\n")
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path=str(champion_dir),
        code_snapshot_hash="champion",
    )
    controller = BranchController()
    branch = controller.create_branch(champion)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("operators/*.py",),
    )
    service = WorkspaceLifecycleService(
        materializer=materializer,
        branch_controller=controller,
        branch_workspaces={},
        branch_patches={},
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
    )
    durable = service.setup_workspace(branch)
    assert durable is not None
    applied = service.apply_candidate_patch(
        branch,
        durable,
        PatchProposal(
            file_path="operators/solver.py",
            action="modify",
            code_content="VALUE = 1\n",
        ),
    )

    def fail_cleanup(_workspace: str) -> None:
        raise OSError("cleanup unavailable")

    monkeypatch.setattr(materializer, "cleanup_candidate_workspace", fail_cleanup)
    report = service.reject_candidate(branch, applied.workspace)

    assert report.cleaned is False
    assert report.cleanup_error == "OSError: cleanup unavailable"
    assert Path(applied.workspace).is_dir()
    assert service.pending_candidates == {}
    assert branch.current_code_hash is None
    assert branch.last_clean_code_hash is None
    assert branch.branch_code_status == "clean"
    next_applied = service.apply_candidate_patch(
        branch,
        durable,
        PatchProposal(
            file_path="operators/solver.py",
            action="modify",
            code_content="VALUE = 2\n",
        ),
    )
    assert next_applied.workspace != applied.workspace


def test_promotion_precommit_failure_rolls_back_pending_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    champion_dir = tmp_path / "champion"
    (champion_dir / "operators").mkdir(parents=True)
    source = champion_dir / "operators" / "solver.py"
    source.write_text("VALUE = 0\n")
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path=str(champion_dir),
        code_snapshot_hash="champion",
    )
    controller = BranchController()
    branch = controller.create_branch(champion)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("operators/*.py",),
    )
    service = WorkspaceLifecycleService(
        materializer=materializer,
        branch_controller=controller,
        branch_workspaces={},
        branch_patches={},
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
    )
    durable = service.setup_workspace(branch)
    assert durable is not None
    applied = service.apply_candidate_patch(
        branch,
        durable,
        PatchProposal(
            file_path="operators/solver.py",
            action="modify",
            code_content="VALUE = 1\n",
        ),
    )

    def fail_promotion(_candidate: str, _branch_id: str, **_kwargs) -> str:
        raise OSError("rename unavailable")

    monkeypatch.setattr(materializer, "promote_candidate_workspace", fail_promotion)
    with pytest.raises(OSError, match="rename unavailable"):
        service.promote_verified_candidate(
            branch,
            applied.code_hash,
            applied.workspace,
            "h-promotion-failure",
        )

    assert service.pending_candidates == {}
    assert branch.current_code_hash is None
    assert branch.last_clean_code_hash is None
    assert branch.branch_code_status == "clean"
    assert (Path(durable) / "operators" / "solver.py").read_text() == "VALUE = 0\n"
