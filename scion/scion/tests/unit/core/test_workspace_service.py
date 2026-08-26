from __future__ import annotations

import stat
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
    assert set(vars(applied)) == {"workspace", "source_digest"}


def test_branch_lease_cleans_return_to_owner_store_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, branch, _, materializer, workspaces, _, _ = _staging_service(tmp_path)
    service.discard_branch_workspace(branch.branch_id)
    create_workspace = materializer.create_branch_workspace

    def interrupt_after_materializer_return(
        branch_id: str,
        source_snapshot: str,
    ) -> str:
        workspace = create_workspace(branch_id, source_snapshot)
        assert Path(workspace).absolute() in materializer._inflight_branch_workspaces
        raise KeyboardInterrupt("materializer-return:branch")

    monkeypatch.setattr(
        materializer,
        "create_branch_workspace",
        interrupt_after_materializer_return,
    )

    with pytest.raises(KeyboardInterrupt, match="materializer-return:branch"):
        service.setup_workspace(branch)

    assert workspaces == {}
    assert not any((tmp_path / "campaign" / "workspaces").iterdir())
    assert materializer._inflight_branch_workspaces == set()


def test_candidate_lease_cleans_return_to_owner_store_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, _, materializer, _, _, base_workspace = _staging_service(tmp_path)
    create_candidate = materializer.create_candidate_workspace

    def interrupt_after_materializer_return(source_workspace: str) -> str:
        candidate = create_candidate(source_workspace)
        assert Path(candidate) in materializer._inflight_candidate_workspaces
        raise KeyboardInterrupt("materializer-return:candidate")

    monkeypatch.setattr(
        materializer,
        "create_candidate_workspace",
        interrupt_after_materializer_return,
    )

    with pytest.raises(KeyboardInterrupt, match="materializer-return:candidate"):
        service.apply_candidate_patch(base_workspace, _candidate_patch())

    assert Path(base_workspace).is_dir()
    assert not any((tmp_path / "campaign" / "candidate_workspaces").iterdir())
    assert materializer._inflight_candidate_workspaces == set()


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
    materializer.claim_branch_workspace("branch-1", branch_workspace)

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
def test_materializer_partial_copy_interrupt_cleans_lease_and_tree(
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
        materializer.claim_branch_workspace("branch-1", branch_workspace)
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

    assert materializer._inflight_branch_workspaces == set()
    assert materializer._inflight_candidate_workspaces == set()
    if kind == "branch":
        assert not (campaign / "workspaces" / "branch-2").exists()
    else:
        assert not any((campaign / "candidate_workspaces").iterdir())


def test_legacy_materializer_without_lease_api_preserves_workspace_lifecycle(
    tmp_path: Path,
) -> None:
    service, branch, controller, materializer, workspaces, _, base_workspace = (
        _staging_service(tmp_path)
    )

    class LegacyMaterializer:
        def create_branch_workspace(self, branch_id: str, source: str) -> str:
            return materializer.create_branch_workspace(branch_id, source)

        def create_candidate_workspace(self, source: str) -> str:
            return materializer.create_candidate_workspace(source)

        def apply_patch(self, workspace: str, patch: PatchProposal) -> str:
            return materializer.apply_patch(workspace, patch)

        def cleanup_candidate_workspace(self, workspace: str) -> None:
            materializer.cleanup_candidate_workspace(workspace)

        def freeze_snapshot(self, workspace: str) -> None:
            materializer.freeze_snapshot(workspace)

        def compute_code_hash(self, workspace: str) -> str:
            return materializer.compute_code_hash(workspace)

        def cleanup(self, workspace: str) -> None:
            materializer.cleanup(workspace)

    service.materializer = LegacyMaterializer()  # type: ignore[assignment]
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
