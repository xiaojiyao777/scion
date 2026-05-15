"""Tests for WorkspaceMaterializer (T07)."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from scion.runtime.workspace import FrozenFileError, WorkspaceMaterializer
from scion.core.models import ChampionState, PatchFileChange, PatchProposal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def campaign_dir(tmp_path: Path) -> Path:
    d = tmp_path / "campaign"
    d.mkdir()
    return d


@pytest.fixture()
def code_base(tmp_path: Path) -> Path:
    """Minimal code base with operators/ dir."""
    cb = tmp_path / "code_base"
    (cb / "operators").mkdir(parents=True)
    (cb / "operators" / "swap.py").write_text("class SwapOperator:\n    pass\n")
    (cb / "solver.py").write_text("# solver\n")
    return cb


@pytest.fixture()
def mat(campaign_dir: Path) -> WorkspaceMaterializer:
    return WorkspaceMaterializer(str(campaign_dir))


# ---------------------------------------------------------------------------
# create_branch_workspace
# ---------------------------------------------------------------------------


class TestCreateBranchWorkspace:
    def test_creates_workspace(self, mat: WorkspaceMaterializer, code_base: Path):
        ws = mat.create_branch_workspace("branch-1", str(code_base))
        assert Path(ws).exists()
        assert Path(ws).is_dir()

    def test_files_are_copied(self, mat: WorkspaceMaterializer, code_base: Path):
        ws = mat.create_branch_workspace("branch-1", str(code_base))
        assert (Path(ws) / "solver.py").exists()
        assert (Path(ws) / "operators" / "swap.py").exists()

    def test_missing_code_base_raises(self, mat: WorkspaceMaterializer, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            mat.create_branch_workspace("branch-1", str(tmp_path / "nonexistent"))

    def test_recreates_if_exists(self, mat: WorkspaceMaterializer, code_base: Path):
        ws1 = mat.create_branch_workspace("branch-1", str(code_base))
        # Write extra file into workspace
        (Path(ws1) / "extra.txt").write_text("extra")
        # Create again — old workspace should be replaced
        ws2 = mat.create_branch_workspace("branch-1", str(code_base))
        assert ws1 == ws2
        assert not (Path(ws2) / "extra.txt").exists()


# ---------------------------------------------------------------------------
# apply_patch
# ---------------------------------------------------------------------------


class TestApplyPatch:
    def test_modify_creates_file(self, mat: WorkspaceMaterializer, code_base: Path):
        ws = mat.create_branch_workspace("b1", str(code_base))
        patch = PatchProposal(
            file_path="operators/new_op.py",
            action="create",
            code_content="class NewOp:\n    pass\n",
        )
        new_hash = mat.apply_patch(ws, patch)
        assert (Path(ws) / "operators" / "new_op.py").exists()
        assert isinstance(new_hash, str) and len(new_hash) == 64

    def test_create_nested_dirs(self, mat: WorkspaceMaterializer, code_base: Path):
        ws = mat.create_branch_workspace("b2", str(code_base))
        patch = PatchProposal(
            file_path="operators/sub/deep_op.py",
            action="create",
            code_content="x = 1\n",
        )
        mat.apply_patch(ws, patch)
        assert (Path(ws) / "operators" / "sub" / "deep_op.py").exists()

    def test_multi_file_patch_applies_all_changes(
        self,
        mat: WorkspaceMaterializer,
        code_base: Path,
    ):
        ws = mat.create_branch_workspace("b2multi", str(code_base))
        patch = PatchProposal(
            file_path="operators/new_op.py",
            action="create",
            code_content="class NewOp:\n    pass\n",
            additional_changes=(
                PatchFileChange(
                    file_path="policies/helper.py",
                    action="create",
                    code_content="VALUE = 1\n",
                ),
            ),
        )

        mat.apply_patch(ws, patch)

        assert (Path(ws) / "operators" / "new_op.py").read_text(
            encoding="utf-8"
        ) == "class NewOp:\n    pass\n"
        assert (Path(ws) / "policies" / "helper.py").read_text(
            encoding="utf-8"
        ) == "VALUE = 1\n"

    def test_delete_removes_file(self, mat: WorkspaceMaterializer, code_base: Path):
        ws = mat.create_branch_workspace("b3", str(code_base))
        target = Path(ws) / "operators" / "swap.py"
        assert target.exists()
        patch = PatchProposal(
            file_path="operators/swap.py",
            action="delete",
            code_content="",
        )
        mat.apply_patch(ws, patch)
        assert not target.exists()

    def test_frozen_file_rejected(self, mat: WorkspaceMaterializer, code_base: Path):
        ws = mat.create_branch_workspace("b4", str(code_base))
        patch = PatchProposal(
            file_path="solver.py",
            action="modify",
            code_content="# hacked\n",
        )
        with pytest.raises(FrozenFileError):
            mat.apply_patch(ws, patch)

    def test_frozen_oracle_rejected(self, mat: WorkspaceMaterializer, code_base: Path):
        ws = mat.create_branch_workspace("b5", str(code_base))
        patch = PatchProposal(
            file_path="oracle.py",
            action="modify",
            code_content="# hacked\n",
        )
        with pytest.raises(FrozenFileError):
            mat.apply_patch(ws, patch)

    def test_path_traversal_rejected(self, mat: WorkspaceMaterializer, code_base: Path):
        ws = mat.create_branch_workspace("b-path", str(code_base))
        outside = Path(ws).parent / "escaped.py"
        patch = PatchProposal(
            file_path="../escaped.py",
            action="create",
            code_content="x = 1\n",
        )
        with pytest.raises(ValueError):
            mat.apply_patch(ws, patch)
        assert not outside.exists()

    def test_nested_path_traversal_rejected(
        self, mat: WorkspaceMaterializer, code_base: Path
    ):
        ws = mat.create_branch_workspace("b-path-nested", str(code_base))
        outside = Path(ws).parent / "escaped.py"
        patch = PatchProposal(
            file_path="operators/../../escaped.py",
            action="create",
            code_content="x = 1\n",
        )
        with pytest.raises(ValueError):
            mat.apply_patch(ws, patch)
        assert not outside.exists()

    def test_absolute_path_rejected(
        self, mat: WorkspaceMaterializer, code_base: Path, tmp_path: Path
    ):
        ws = mat.create_branch_workspace("b-absolute", str(code_base))
        outside = tmp_path / "outside.py"
        patch = PatchProposal(
            file_path=str(outside),
            action="create",
            code_content="x = 1\n",
        )
        with pytest.raises(ValueError):
            mat.apply_patch(ws, patch)
        assert not outside.exists()

    def test_hash_changes_on_new_content(
        self, mat: WorkspaceMaterializer, code_base: Path
    ):
        ws = mat.create_branch_workspace("b6", str(code_base))
        patch1 = PatchProposal(
            file_path="operators/op_a.py", action="create", code_content="x = 1\n"
        )
        patch2 = PatchProposal(
            file_path="operators/op_a.py", action="modify", code_content="x = 2\n"
        )
        h1 = mat.apply_patch(ws, patch1)
        h2 = mat.apply_patch(ws, patch2)
        assert h1 != h2


# ---------------------------------------------------------------------------
# compute_code_hash
# ---------------------------------------------------------------------------


class TestComputeCodeHash:
    def test_consistent_hash(self, mat: WorkspaceMaterializer, code_base: Path):
        ws = mat.create_branch_workspace("hash1", str(code_base))
        h1 = mat.compute_code_hash(ws)
        h2 = mat.compute_code_hash(ws)
        assert h1 == h2

    def test_hash_is_hex_64(self, mat: WorkspaceMaterializer, code_base: Path):
        ws = mat.create_branch_workspace("hash2", str(code_base))
        h = mat.compute_code_hash(ws)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_empty_operators_dir(self, mat: WorkspaceMaterializer, tmp_path: Path):
        cb = tmp_path / "empty_cb"
        cb.mkdir()
        (cb / "operators").mkdir()
        ws = mat.create_branch_workspace("hash3", str(cb))
        h = mat.compute_code_hash(ws)
        # Should return a consistent (empty) hash
        assert len(h) == 64

    def test_no_operators_dir(self, mat: WorkspaceMaterializer, tmp_path: Path):
        cb = tmp_path / "no_ops"
        cb.mkdir()
        ws = mat.create_branch_workspace("hash4", str(cb))
        h = mat.compute_code_hash(ws)
        assert len(h) == 64


# ---------------------------------------------------------------------------
# create_champion_snapshot (read-only)
# ---------------------------------------------------------------------------


class TestCreateChampionSnapshot:
    def test_snapshot_is_readonly(
        self, mat: WorkspaceMaterializer, code_base: Path, tmp_path: Path
    ):
        ws = mat.create_branch_workspace("champ1", str(code_base))
        champion = ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="abc",
            code_snapshot_path=ws,
            code_snapshot_hash="xyz",
        )
        snap_dir = str(tmp_path / "snaps")
        os.makedirs(snap_dir)
        snap = mat.create_champion_snapshot(champion, snap_dir)

        # At least one file should not be writable
        py_files = list(Path(snap).rglob("*.py"))
        assert py_files  # sanity
        for f in py_files:
            mode = f.stat().st_mode
            assert not (mode & stat.S_IWUSR), f"{f} should not be user-writable"

    def test_snapshot_path_contains_version(
        self, mat: WorkspaceMaterializer, code_base: Path, tmp_path: Path
    ):
        ws = mat.create_branch_workspace("champ2", str(code_base))
        champion = ChampionState(
            version=3,
            operator_pool={},
            solver_config_hash="abc",
            code_snapshot_path=ws,
            code_snapshot_hash="xyz",
        )
        snap = mat.create_champion_snapshot(champion, str(tmp_path / "s"))
        assert "champion_v3" in snap


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_cleanup_removes_workspace(
        self, mat: WorkspaceMaterializer, code_base: Path
    ):
        ws = mat.create_branch_workspace("del1", str(code_base))
        assert Path(ws).exists()
        mat.cleanup(ws)
        assert not Path(ws).exists()

    def test_cleanup_nonexistent_is_noop(self, mat: WorkspaceMaterializer, tmp_path: Path):
        mat.cleanup(str(tmp_path / "does_not_exist"))  # should not raise
