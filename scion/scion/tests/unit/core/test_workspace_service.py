from __future__ import annotations

import stat
import threading
from pathlib import Path

import pytest

from scion.core.branch import BranchController
from scion.core.models import (
    AcceptedBranchChange,
    AcceptedFileBeforeSource,
    ChampionState,
    HypothesisProposal,
    OperatorConfig,
    PatchFileChange,
    PatchProposal,
)
from scion.core.workspace_service import WorkspaceService
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
        code_snapshot_path="/tmp/champion",
    )


def _service(tmp_path: Path, *, champion: ChampionState | None = None):
    controller = BranchController()
    champion = champion or _champion()
    branch = controller.create_branch(champion)
    materializer = FakeMaterializer(tmp_path)
    workspaces: dict[str, str] = {}
    patches: dict[str, PatchProposal] = {}
    service = WorkspaceService(
        materializer=materializer,
        branch_controller=controller,
        branch_workspaces=workspaces,
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
    )
    return service, branch, controller, materializer, workspaces, patches


def _registry_service(tmp_path: Path):
    champion_dir = tmp_path / "champion"
    operators_dir = champion_dir / "operators"
    operators_dir.mkdir(parents=True)
    (operators_dir / "ls.py").write_text(
        "class LocalSearch:\n    version = 1\n",
        encoding="utf-8",
    )
    registry_bytes = (
        b"# preserve this operator note\n"
        b"operators:\n"
        b"  - name: ls\n"
        b"    file_path: operators/ls.py\n"
        b"    category: local_search\n"
        b"    weight: 1.00\n"
        b"    class_name: LocalSearch\n"
    )
    (champion_dir / "registry.yaml").write_bytes(registry_bytes)
    operator = OperatorConfig(
        name="ls",
        file_path="operators/ls.py",
        category="local_search",
        weight=1.0,
        class_name="LocalSearch",
    )
    champion = ChampionState(
        version=1,
        operator_pool={"ls": operator},
        code_snapshot_path=str(champion_dir),
    )
    controller = BranchController()
    branch = controller.create_branch(champion)
    workspaces: dict[str, str] = {}
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("operators/*.py",),
    )
    service = WorkspaceService(
        materializer=materializer,
        branch_controller=controller,
        branch_workspaces=workspaces,
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
    )
    durable = service.setup_workspace(branch)
    assert durable is not None
    return service, branch, Path(durable), registry_bytes


def test_setup_workspace_reuses_existing_verified_branch_workspace(
    tmp_path: Path,
) -> None:
    service, branch, controller, materializer, workspaces, _ = _service(tmp_path)
    existing = tmp_path / "existing"
    existing.mkdir()
    workspaces[branch.branch_id] = str(existing)
    controller.accept_verified_code(branch.branch_id, "candidate-hash")
    materializer.compute_code_hash = lambda _workspace: (_ for _ in ()).throw(
        AssertionError("accepted source reuse must not rehash")
    )
    assert service.setup_workspace(branch) == str(existing)
    assert materializer.created == []


def test_missing_verified_branch_workspace_refuses_champion_fallback(
    tmp_path: Path,
) -> None:
    service, branch, controller, materializer, workspaces, _ = _service(tmp_path)
    missing = tmp_path / "missing-verified-workspace"
    workspaces[branch.branch_id] = str(missing)
    controller.accept_verified_code(branch.branch_id, "candidate-hash")

    assert service.setup_workspace(branch) is None
    assert materializer.created == []
    assert materializer.cleaned == []


def test_modify_exports_candidate_registry_without_touching_source(
    tmp_path: Path,
) -> None:
    service, _branch, durable, registry_bytes = _registry_service(tmp_path)
    hypothesis = HypothesisProposal(
        hypothesis_text="Improve the existing local-search implementation.",
        change_locus="local_search",
        action="modify",
        target_file="operators/ls.py",
    )
    applied = service.apply_candidate_patch(
        str(durable),
        PatchProposal(
            file_path="operators/ls.py",
            action="modify",
            code_content="class LocalSearch:\n    version = 2\n",
        ),
        hypothesis=hypothesis,
        sync_registry=True,
    )

    from scion.runtime.pool_manager import read_registry

    pool = read_registry(str(Path(applied.workspace) / "registry.yaml"))
    assert set(pool) == {"ls"}
    assert applied.before_sources == (
        AcceptedFileBeforeSource(
            file_path="operators/ls.py",
            source="class LocalSearch:\n    version = 1\n",
        ),
    )
    assert applied.changed_files == ("operators/ls.py", "registry.yaml")
    assert (durable / "registry.yaml").read_bytes() == registry_bytes
    service.reject_candidate(applied)


def test_create_operator_uses_only_pool_registry_writer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service, _branch, durable, _ = _registry_service(tmp_path)
    from scion.runtime.pool_manager import PoolManager, read_registry

    export_calls: list[str] = []
    original_export = PoolManager.export_registry

    def count_export(self, pool, target_dir):
        export_calls.append(target_dir)
        return original_export(self, pool, target_dir)

    monkeypatch.setattr(PoolManager, "export_registry", count_export)
    hypothesis = HypothesisProposal(
        hypothesis_text="Add one complementary local-search operator.",
        change_locus="local_search",
        action="create_new",
        target_file="operators/new_move.py",
        suggested_weight=0.2,
    )
    applied = service.apply_candidate_patch(
        str(durable),
        PatchProposal(
            file_path="operators/new_move.py",
            action="create",
            code_content="class NewMove:\n    pass\n",
        ),
        hypothesis=hypothesis,
        sync_registry=True,
    )

    candidate = Path(applied.workspace)
    pool = read_registry(str(candidate / "registry.yaml"))
    assert export_calls == [applied.workspace]
    assert set(pool) == {"ls", "new_move"}
    assert sum(operator.weight for operator in pool.values()) == pytest.approx(1.0)
    assert applied.changed_files == (
        "operators/new_move.py",
        "registry.yaml",
    )
    registry_path = candidate / "registry.yaml"
    exact_registry = registry_path.read_bytes()
    assert service.verify_candidate(applied) == applied
    registry_path.write_bytes(exact_registry + b"\n")
    with pytest.raises(
        RuntimeError,
        match="candidate changed between Verification and Protocol",
    ):
        service.verify_candidate(applied)
    registry_path.write_bytes(exact_registry)
    assert service.verify_candidate(applied) == applied
    service.reject_candidate(applied)


def test_registry_export_failure_rejects_candidate_materialization(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service, _branch, durable, _ = _registry_service(tmp_path)
    from scion.runtime.pool_manager import PoolManager

    def fail_export(_self, _pool, _target_dir):
        raise OSError("registry export unavailable")

    monkeypatch.setattr(PoolManager, "export_registry", fail_export)
    hypothesis = HypothesisProposal(
        hypothesis_text="Modify the selected local-search implementation.",
        change_locus="local_search",
        action="modify",
        target_file="operators/ls.py",
    )

    with pytest.raises(OSError, match="registry export unavailable"):
        service.apply_candidate_patch(
            str(durable),
            PatchProposal(
                file_path="operators/ls.py",
                action="modify",
                code_content="class LocalSearch:\n    version = 2\n",
            ),
            hypothesis=hypothesis,
            sync_registry=True,
        )

    candidate_root = tmp_path / "campaign" / "candidate_workspaces"
    assert not any(candidate_root.iterdir())


def test_sequential_candidate_patches_preserve_created_operator_activation(
    tmp_path: Path,
) -> None:
    from scion.runtime.pool_manager import read_registry

    service, _branch, durable, _ = _registry_service(tmp_path)
    created = service.apply_candidate_patch(
        str(durable),
        PatchProposal(
            file_path="operators/new_move.py",
            action="create",
            code_content="class NewMove:\n    pass\n",
        ),
        hypothesis=HypothesisProposal(
            hypothesis_text="Add a new move.",
            change_locus="local_search",
            action="create_new",
            target_file="operators/new_move.py",
            suggested_weight=0.2,
        ),
        sync_registry=True,
    )
    # Continued work is grounded in the accepted candidate catalogue, not a
    # reconstructed or stale champion-side copy.
    service.get_champion().operator_pool.clear()

    modified = service.apply_candidate_patch(
        created.workspace,
        PatchProposal(
            file_path="operators/ls.py",
            action="modify",
            code_content="class RefinedLocalSearch:\n    version = 2\n",
        ),
        hypothesis=HypothesisProposal(
            hypothesis_text="Refine the existing move.",
            change_locus="local_search",
            action="modify",
            target_file="operators/ls.py",
        ),
        sync_registry=True,
    )

    pool = read_registry(str(Path(modified.workspace) / "registry.yaml"))
    assert set(pool) == {"ls", "new_move"}
    assert pool["ls"].class_name == "RefinedLocalSearch"
    assert pool["new_move"].class_name == "NewMove"
    assert created.changed_files == (
        "operators/new_move.py",
        "registry.yaml",
    )
    assert modified.changed_files == ("operators/ls.py", "registry.yaml")
    service.reject_candidate(modified)
    service.reject_candidate(created)


def test_candidate_captures_each_touched_file_before_source(tmp_path: Path) -> None:
    service, _branch, durable, _ = _registry_service(tmp_path)
    applied = service.apply_candidate_patch(
        str(durable),
        PatchProposal(
            file_path="operators/ls.py",
            action="modify",
            code_content="class LocalSearch:\n    version = 2\n",
            additional_changes=(
                PatchFileChange(
                    file_path="operators/new_move.py",
                    action="create",
                    code_content="class NewMove:\n    pass\n",
                ),
            ),
        ),
    )

    assert applied.before_sources == (
        AcceptedFileBeforeSource(
            file_path="operators/ls.py",
            source="class LocalSearch:\n    version = 1\n",
        ),
        AcceptedFileBeforeSource(
            file_path="operators/new_move.py",
            source=None,
        ),
    )
    service.reject_candidate(applied)


def test_reconcile_source_conflict_detects_same_file_sibling_drift(
    tmp_path: Path,
) -> None:
    service, _branch, durable, _ = _registry_service(tmp_path)
    staging = service.create_reconcile_workspace(str(durable))
    shared_file = Path(staging) / "operators" / "ls.py"
    shared_file.write_text(
        "class LocalSearch:\n    sibling_version = 7\n",
        encoding="utf-8",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Change the old local-search source.",
        change_locus="local_search",
        action="modify",
        target_file="operators/ls.py",
    )
    accepted_change = AcceptedBranchChange(
        hypothesis=hypothesis,
        patch=PatchProposal(
            file_path="operators/ls.py",
            action="modify",
            code_content="class LocalSearch:\n    branch_version = 2\n",
        ),
        before_sources=(
            AcceptedFileBeforeSource(
                file_path="operators/ls.py",
                source="class LocalSearch:\n    version = 1\n",
            ),
        ),
    )

    conflicts = service.reconcile_source_conflicts(staging, accepted_change)

    assert conflicts == ("operators/ls.py",)
    assert "sibling_version = 7" in shared_file.read_text(encoding="utf-8")
    service.discard_reconcile_workspace(staging)


def test_reconcile_create_then_modify_uses_one_workspace_and_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.runtime.pool_manager import read_registry

    service, _branch, durable, _ = _registry_service(tmp_path)
    staging = service.create_reconcile_workspace(str(durable))
    create_hypothesis = HypothesisProposal(
        hypothesis_text="Add a new move.",
        change_locus="local_search",
        action="create_new",
        target_file="operators/new_move.py",
        suggested_weight=0.2,
    )
    service.apply_reconcile_change(
        staging,
        PatchProposal(
            file_path="operators/new_move.py",
            action="create",
            code_content="class NewMove:\n    version = 1\n",
        ),
        hypothesis=create_hypothesis,
    )
    service.apply_reconcile_change(
        staging,
        PatchProposal(
            file_path="operators/new_move.py",
            action="modify",
            code_content="class NewMove:\n    version = 2\n",
        ),
        hypothesis=HypothesisProposal(
            hypothesis_text="Refine the new move.",
            change_locus="local_search",
            action="modify",
            target_file="operators/new_move.py",
        ),
    )

    pool = read_registry(str(Path(staging) / "registry.yaml"))
    assert set(pool) == {"ls", "new_move"}
    assert pool["new_move"].class_name == "NewMove"
    assert (Path(staging) / "operators" / "new_move.py").read_text(
        encoding="utf-8"
    ) == "class NewMove:\n    version = 2\n"
    digest_calls: list[str] = []
    compute_code_hash = service.materializer.compute_code_hash

    def count_digest(workspace: str) -> str:
        digest_calls.append(workspace)
        return compute_code_hash(workspace)

    monkeypatch.setattr(service.materializer, "compute_code_hash", count_digest)
    candidate = service.seal_reconcile_candidate(
        staging,
        base_workspace=str(durable),
        changed_files=("operators/new_move.py",),
    )
    service.verify_candidate(candidate)
    assert digest_calls == [staging, staging]
    assert candidate.changed_files == (
        "operators/new_move.py",
        "registry.yaml",
    )
    service.discard_reconcile_workspace(staging)


def test_rejected_created_operator_preserves_durable_registry_and_source(
    tmp_path: Path,
) -> None:
    service, _branch, durable, registry_bytes = _registry_service(tmp_path)
    hypothesis = HypothesisProposal(
        hypothesis_text="Try one new local-search operator.",
        change_locus="local_search",
        action="create_new",
        target_file="operators/rejected_move.py",
    )
    applied = service.apply_candidate_patch(
        str(durable),
        PatchProposal(
            file_path="operators/rejected_move.py",
            action="create",
            code_content="class RejectedMove:\n    pass\n",
        ),
        hypothesis=hypothesis,
        sync_registry=True,
    )
    assert (Path(applied.workspace) / "operators" / "rejected_move.py").is_file()

    service.reject_candidate(applied)

    assert (durable / "registry.yaml").read_bytes() == registry_bytes
    assert not (durable / "operators" / "rejected_move.py").exists()


def _staging_service(tmp_path: Path):
    champion_dir = tmp_path / "champion"
    (champion_dir / "operators").mkdir(parents=True)
    source = champion_dir / "operators" / "solver.py"
    source.write_text("VALUE = 0\n")
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(champion_dir),
    )
    controller = BranchController()
    branch = controller.create_branch(champion)
    workspaces: dict[str, str] = {}
    patches: dict[str, PatchProposal] = {}
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("operators/*.py",),
    )
    service = WorkspaceService(
        materializer=materializer,
        branch_controller=controller,
        branch_workspaces=workspaces,
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
    )
    base_workspace = service.setup_workspace(branch)
    assert base_workspace is not None
    return (
        service,
        branch,
        controller,
        materializer,
        workspaces,
        patches,
        base_workspace,
    )


def _candidate_patch(value: int = 1) -> PatchProposal:
    return PatchProposal(
        file_path="operators/solver.py",
        action="modify",
        code_content=f"VALUE = {value}\n",
    )


def test_staging_keeps_branch_and_durable_workspace_untouched(
    tmp_path: Path,
) -> None:
    service, branch, _, _, workspaces, _, base_workspace = _staging_service(tmp_path)

    applied = service.apply_candidate_patch(base_workspace, _candidate_patch())

    assert (
        Path(base_workspace) / "operators" / "solver.py"
    ).read_text() == "VALUE = 0\n"
    assert (
        Path(applied.workspace) / "operators" / "solver.py"
    ).read_text() == "VALUE = 1\n"
    assert workspaces[branch.branch_id] == base_workspace
    assert branch.current_code_hash is None
    assert service.setup_workspace(branch) == base_workspace
    assert set(vars(applied)) == {
        "workspace",
        "source_digest",
        "before_sources",
        "changed_files",
    }


def test_relative_campaign_preserves_branch_and_candidate_path_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = Path("champion")
    source.mkdir()
    (source / "solver.py").write_text("VALUE = 0\n", encoding="utf-8")
    materializer = WorkspaceMaterializer("relative-campaign")

    branch_workspace = materializer.create_branch_workspace("branch-1", str(source))
    assert branch_workspace == "relative-campaign/workspaces/branch-1"
    assert not Path(branch_workspace).is_absolute()

    candidate_workspace = materializer.create_candidate_workspace(branch_workspace)
    assert Path(candidate_workspace).is_absolute()
    assert Path(candidate_workspace).parent == (
        tmp_path / "relative-campaign" / "candidate_workspaces"
    )
    materializer.cleanup_candidate_workspace(candidate_workspace)


def test_branch_workspace_symlink_never_deletes_its_in_root_target(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    source = tmp_path / "champion"
    source.mkdir()
    (source / "solver.py").write_text("VALUE = 0\n", encoding="utf-8")
    materializer = WorkspaceMaterializer(str(campaign))
    target = campaign / "workspaces" / "branch-target"
    target.mkdir()
    marker = target / "target-marker.txt"
    marker.write_text("survive\n", encoding="utf-8")
    alias = campaign / "workspaces" / "branch-alias"
    alias.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="symlinked branch workspace"):
        materializer.create_branch_workspace("branch-alias", str(source))

    assert alias.is_symlink()
    assert marker.read_text(encoding="utf-8") == "survive\n"
    materializer.cleanup_branch_workspace("branch-alias")
    assert not alias.exists()
    assert marker.read_text(encoding="utf-8") == "survive\n"


@pytest.mark.parametrize("kind", ("branch", "candidate"))
def test_materializer_partial_copy_interrupt_cleans_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    campaign = tmp_path / "campaign"
    source = tmp_path / "champion"
    source.mkdir()
    (source / "solver.py").write_text("VALUE = 0\n", encoding="utf-8")
    materializer = WorkspaceMaterializer(str(campaign))
    if kind == "candidate":
        branch_workspace = materializer.create_branch_workspace(
            "branch-1",
            str(source),
        )
        source_path = branch_workspace
    else:
        source_path = str(source)

    def interrupt_copy(_src, destination, **_kwargs) -> None:
        dest = Path(destination)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "partial.txt").write_text("partial\n", encoding="utf-8")
        raise KeyboardInterrupt("copy interrupted")

    monkeypatch.setattr("scion.runtime.workspace.shutil.copytree", interrupt_copy)

    with pytest.raises(KeyboardInterrupt, match="copy interrupted"):
        if kind == "branch":
            materializer.create_branch_workspace("branch-2", source_path)
        else:
            materializer.create_candidate_workspace(source_path)

    if kind == "branch":
        assert not (campaign / "workspaces" / "branch-2").exists()
    else:
        assert not any((campaign / "candidate_workspaces").iterdir())


def test_candidate_patch_interrupt_cleans_staging_and_preserves_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, _, materializer, _, _, base_workspace = _staging_service(tmp_path)

    def interrupt_apply(workspace: str, _patch: PatchProposal) -> str:
        (Path(workspace) / "operators" / "partial.py").write_text(
            "PARTIAL = True\n",
            encoding="utf-8",
        )
        raise KeyboardInterrupt("patch interrupted")

    monkeypatch.setattr(materializer, "apply_ephemeral_patch", interrupt_apply)

    with pytest.raises(KeyboardInterrupt, match="patch interrupted"):
        service.apply_candidate_patch(base_workspace, _candidate_patch())

    assert Path(base_workspace).is_dir()
    assert not (Path(base_workspace) / "operators" / "partial.py").exists()
    candidate_root = tmp_path / "campaign" / "candidate_workspaces"
    assert not any(candidate_root.iterdir())


def test_plain_materializer_preserves_candidate_accept_and_reject_lifecycle(
    tmp_path: Path,
) -> None:
    service, branch, controller, materializer, workspaces, _, base_workspace = (
        _staging_service(tmp_path)
    )

    class PlainMaterializer:
        def create_branch_workspace(self, branch_id: str, source: str) -> str:
            return materializer.create_branch_workspace(branch_id, source)

        def create_candidate_workspace(self, source: str) -> str:
            return materializer.create_candidate_workspace(source)

        def apply_patch(self, workspace: str, patch: PatchProposal) -> str:
            return materializer.apply_patch(workspace, patch)

        def apply_ephemeral_patch(
            self,
            workspace: str,
            patch: PatchProposal,
        ) -> None:
            materializer.apply_ephemeral_patch(workspace, patch)

        def cleanup_candidate_workspace(self, workspace: str) -> None:
            materializer.cleanup_candidate_workspace(workspace)

        def freeze_snapshot(self, workspace: str) -> None:
            materializer.freeze_snapshot(workspace)

        def compute_code_hash(self, workspace: str) -> str:
            return materializer.compute_code_hash(workspace)

        def cleanup(self, workspace: str) -> None:
            materializer.cleanup(workspace)

    service.materializer = PlainMaterializer()  # type: ignore[assignment]
    rejected = service.apply_candidate_patch(base_workspace, _candidate_patch())
    service.reject_candidate(rejected)
    assert not Path(rejected.workspace).exists()

    accepted = service.apply_candidate_patch(base_workspace, _candidate_patch(2))
    assert service.verify_candidate(accepted) == accepted
    assert service.accept_candidate(branch, accepted) == accepted.workspace
    assert workspaces[branch.branch_id] == accepted.workspace
    assert controller.get_branch(branch.branch_id).current_code_hash == (
        accepted.source_digest
    )


def test_accept_candidate_binds_exact_staging_value_as_branch_source(
    tmp_path: Path,
) -> None:
    service, branch, _, _, workspaces, patches, base_workspace = _staging_service(
        tmp_path
    )
    patch = _candidate_patch()
    applied = service.apply_candidate_patch(
        base_workspace,
        patch,
    )

    assert branch.current_code_hash is None
    assert workspaces[branch.branch_id] == base_workspace
    assert service.verify_candidate(applied) == applied
    accepted = service.accept_candidate(branch, applied)

    assert accepted == applied.workspace
    assert workspaces[branch.branch_id] == applied.workspace
    assert Path(accepted).is_dir()
    assert (Path(accepted) / "operators" / "solver.py").read_text() == "VALUE = 1\n"
    assert not (
        (Path(accepted) / "operators" / "solver.py").stat().st_mode
        & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    )
    assert not Path(base_workspace).exists()
    assert patches == {}
    assert branch.current_code_hash == applied.source_digest


def test_reject_candidate_leaves_prior_branch_workspace_and_hash_untouched(
    tmp_path: Path,
) -> None:
    service, branch, controller, materializer, workspaces, _, base_workspace = (
        _staging_service(tmp_path)
    )
    controller.accept_verified_code(
        branch.branch_id,
        materializer.compute_code_hash(base_workspace),
    )
    parent_hash = branch.current_code_hash
    applied = service.apply_candidate_patch(base_workspace, _candidate_patch())

    service.reject_candidate(applied)

    assert workspaces[branch.branch_id] == base_workspace
    assert not Path(applied.workspace).exists()
    assert branch.current_code_hash == parent_hash
    assert (
        Path(base_workspace) / "operators" / "solver.py"
    ).read_text() == "VALUE = 0\n"


def test_freeze_failure_leaves_branch_and_source_mapping_untouched(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service, branch, controller, materializer, workspaces, _, base_workspace = (
        _staging_service(tmp_path)
    )
    controller.accept_verified_code(
        branch.branch_id,
        materializer.compute_code_hash(base_workspace),
    )
    parent_hash = branch.current_code_hash
    applied = service.apply_candidate_patch(base_workspace, _candidate_patch())

    def fail_freeze(_workspace: str) -> None:
        raise OSError("freeze unavailable")

    monkeypatch.setattr(materializer, "freeze_snapshot", fail_freeze)
    assert service.verify_candidate(applied) == applied
    with pytest.raises(OSError, match="freeze unavailable"):
        service.accept_candidate(branch, applied)

    assert workspaces[branch.branch_id] == base_workspace
    assert branch.current_code_hash == parent_hash
    assert (
        Path(base_workspace) / "operators" / "solver.py"
    ).read_text() == "VALUE = 0\n"


def test_accept_controller_failure_rolls_back_partial_candidate_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, branch, controller, materializer, workspaces, _, base_workspace = (
        _staging_service(tmp_path)
    )
    parent_hash = materializer.compute_code_hash(base_workspace)
    controller.accept_verified_code(branch.branch_id, parent_hash)
    applied = service.apply_candidate_patch(base_workspace, _candidate_patch())
    original_accept = controller.accept_verified_code

    def mutate_then_fail(branch_id: str, code_hash: str) -> None:
        original_accept(branch_id, code_hash)
        raise OSError("branch binding unavailable")

    monkeypatch.setattr(controller, "accept_verified_code", mutate_then_fail)

    with pytest.raises(OSError, match="branch binding unavailable"):
        service.accept_candidate(branch, applied)

    assert workspaces[branch.branch_id] == base_workspace
    assert branch.current_code_hash == parent_hash
    assert Path(base_workspace).is_dir()
    assert not Path(applied.workspace).exists()


def test_discard_failure_retains_durable_workspace_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, branch, _, materializer, workspaces, _, base_workspace = (
        _staging_service(tmp_path)
    )

    def fail_cleanup(_workspace: str) -> None:
        raise OSError("durable cleanup unavailable")

    monkeypatch.setattr(materializer, "cleanup", fail_cleanup)

    with pytest.raises(OSError, match="durable cleanup unavailable"):
        service.discard_branch_workspace(branch.branch_id)

    assert workspaces[branch.branch_id] == base_workspace
    assert Path(base_workspace).is_dir()


def test_setup_discard_failure_returns_none_and_clears_workspace_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, branch, _, materializer, workspaces, _, base_workspace = (
        _staging_service(tmp_path)
    )

    def fail_cleanup(_workspace: str) -> None:
        raise OSError("old branch cleanup unavailable")

    monkeypatch.setattr(materializer, "cleanup", fail_cleanup)

    assert service.setup_workspace(branch) is None
    assert branch.branch_id not in workspaces
    assert not Path(base_workspace).exists()


def test_verification_boundary_rejects_candidate_hash_drift(
    tmp_path: Path,
) -> None:
    service, branch, _, _, workspaces, _, base_workspace = _staging_service(tmp_path)
    applied = service.apply_candidate_patch(base_workspace, _candidate_patch())
    candidate_source = Path(applied.workspace) / "operators" / "solver.py"
    candidate_source.write_text("VALUE = 99\n")

    with pytest.raises(RuntimeError, match="between Verification and Protocol"):
        service.verify_candidate(applied)

    assert workspaces[branch.branch_id] == base_workspace
    assert branch.current_code_hash is None
    assert candidate_source.read_text() == "VALUE = 99\n"
    assert (
        Path(base_workspace) / "operators" / "solver.py"
    ).read_text() == "VALUE = 0\n"


def test_accept_does_not_rehash_after_verification(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service, branch, _, materializer, _, _, base_workspace = _staging_service(tmp_path)
    applied = service.apply_candidate_patch(base_workspace, _candidate_patch())
    assert service.verify_candidate(applied) == applied

    def unexpected_rehash(_workspace: str) -> str:
        raise AssertionError("Decision-time candidate rehash is forbidden")

    monkeypatch.setattr(materializer, "compute_code_hash", unexpected_rehash)
    accepted = service.accept_candidate(branch, applied)

    assert Path(accepted).is_dir()
    assert branch.current_code_hash == applied.source_digest


def test_reject_candidate_does_not_cleanup_champion_reconcile_source(
    tmp_path: Path,
) -> None:
    champion_dir = tmp_path / "champion"
    (champion_dir / "operators").mkdir(parents=True)
    source = champion_dir / "operators" / "solver.py"
    source.write_text("VALUE = 0\n")
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(champion_dir),
    )
    controller = BranchController()
    workspaces: dict[str, str] = {}
    service = WorkspaceService(
        materializer=WorkspaceMaterializer(
            str(tmp_path / "campaign"),
            editable_patterns=("operators/*.py",),
        ),
        branch_controller=controller,
        branch_workspaces=workspaces,
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
    )

    applied = service.apply_candidate_patch(str(champion_dir), _candidate_patch())
    service.reject_candidate(applied)

    assert source.read_text() == "VALUE = 0\n"
    assert workspaces == {}


def test_rejected_candidate_preserves_accepted_workspace(
    tmp_path: Path,
) -> None:
    champion_dir = tmp_path / "champion"
    (champion_dir / "operators").mkdir(parents=True)
    (champion_dir / "operators" / "solver.py").write_text("VALUE = 0\n")
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(champion_dir),
    )
    controller = BranchController()
    branch = controller.create_branch(champion)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("operators/*.py",),
    )
    workspaces: dict[str, str] = {}
    service = WorkspaceService(
        materializer=materializer,
        branch_controller=controller,
        branch_workspaces=workspaces,
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
        durable,
        first_patch,
        hypothesis=hypothesis,
    )
    assert (Path(durable) / "operators" / "solver.py").read_text() == "VALUE = 0\n"
    assert service.verify_candidate(first) == first
    durable = service.accept_candidate(branch, first)
    clean_hash = materializer.compute_code_hash(durable)
    assert clean_hash == branch.current_code_hash

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
        durable,
        rejected_patch,
        hypothesis=hypothesis,
    )
    assert rejected.source_digest != clean_hash
    assert (Path(durable) / "operators" / "solver.py").read_text() == "VALUE = 1\n"

    service.reject_candidate(rejected)

    assert not Path(rejected.workspace).exists()
    assert (Path(durable) / "operators" / "solver.py").read_text() == "VALUE = 1\n"
    assert (Path(durable) / "operators" / "helper.py").exists()
    assert materializer.compute_code_hash(durable) == clean_hash
    assert branch.current_code_hash == clean_hash


def test_reject_cleanup_failure_propagates_without_changing_branch_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    champion_dir = tmp_path / "champion"
    (champion_dir / "operators").mkdir(parents=True)
    (champion_dir / "operators" / "solver.py").write_text("VALUE = 0\n")
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(champion_dir),
    )
    controller = BranchController()
    branch = controller.create_branch(champion)
    workspaces: dict[str, str] = {}
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("operators/*.py",),
    )
    service = WorkspaceService(
        materializer=materializer,
        branch_controller=controller,
        branch_workspaces=workspaces,
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
    )
    durable = service.setup_workspace(branch)
    assert durable is not None
    applied = service.apply_candidate_patch(
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
    with pytest.raises(OSError, match="cleanup unavailable"):
        service.reject_candidate(applied)

    assert Path(applied.workspace).is_dir()
    assert workspaces[branch.branch_id] == durable
    assert branch.current_code_hash is None
    next_applied = service.apply_candidate_patch(
        durable,
        PatchProposal(
            file_path="operators/solver.py",
            action="modify",
            code_content="VALUE = 2\n",
        ),
    )
    assert next_applied.workspace != applied.workspace
