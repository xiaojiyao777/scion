"""Tests for WorkspaceMaterializer (T07)."""

from __future__ import annotations

import os
import json
import shutil
import stat
from pathlib import Path

import pytest

import scion.runtime.workspace as workspace_module
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


class TestCandidateWorkspace:
    @pytest.mark.parametrize("branch_id", [".", "..", "../escape", ".hidden"])
    def test_promotion_journal_rejects_unsafe_branch_ids(
        self,
        mat: WorkspaceMaterializer,
        branch_id: str,
    ):
        with pytest.raises(ValueError, match="branch_id is unsafe"):
            mat.finalize_candidate_promotion(branch_id)

    def test_multifile_candidate_isolated_until_atomic_promotion(
        self,
        mat: WorkspaceMaterializer,
        code_base: Path,
    ) -> None:
        durable = mat.create_branch_workspace("candidate-branch", str(code_base))
        candidate = mat.create_candidate_workspace("candidate-branch", durable)
        patch = PatchProposal(
            file_path="operators/swap.py",
            action="modify",
            code_content="class SwapOperator:\n    improved = True\n",
            additional_changes=(
                PatchFileChange(
                    file_path="operators/helper.py",
                    action="create",
                    code_content="VALUE = 1\n",
                ),
                PatchFileChange(
                    file_path="solver.py",
                    action="delete",
                    code_content="",
                ),
            ),
        )

        mat.apply_patch(candidate, patch)

        assert "improved" not in (Path(durable) / "operators" / "swap.py").read_text()
        assert not (Path(durable) / "operators" / "helper.py").exists()
        assert (Path(durable) / "solver.py").exists()
        assert "improved" in (Path(candidate) / "operators" / "swap.py").read_text()
        assert (Path(candidate) / "operators" / "helper.py").exists()
        assert not (Path(candidate) / "solver.py").exists()

        promoted = mat.promote_candidate_workspace(
            candidate,
            "candidate-branch",
            hypothesis_id="h-candidate-branch",
        )

        assert promoted == durable
        assert not Path(candidate).exists()
        assert "improved" in (Path(durable) / "operators" / "swap.py").read_text()
        assert (Path(durable) / "operators" / "helper.py").exists()
        assert not (Path(durable) / "solver.py").exists()

    def test_candidate_cleanup_preserves_durable_workspace(
        self,
        mat: WorkspaceMaterializer,
        code_base: Path,
    ) -> None:
        durable = mat.create_branch_workspace("rejected-branch", str(code_base))
        candidate = mat.create_candidate_workspace("rejected-branch", durable)
        (Path(candidate) / "operators" / "swap.py").write_text("broken = True\n")

        mat.cleanup_candidate_workspace(candidate)

        assert not Path(candidate).exists()
        assert "SwapOperator" in (Path(durable) / "operators" / "swap.py").read_text()

    def test_tampered_promotion_journal_path_fails_closed(
        self,
        mat: WorkspaceMaterializer,
        code_base: Path,
        campaign_dir: Path,
        tmp_path: Path,
    ):
        branch_id = "journal-owner"
        durable = mat.create_branch_workspace(branch_id, str(code_base))
        candidate = mat.create_candidate_workspace(branch_id, durable)
        mat.promote_candidate_workspace(
            candidate,
            branch_id,
            hypothesis_id="h-journal-owner",
        )
        journal = campaign_dir / "promotion_journals" / f"{branch_id}.json"
        payload = json.loads(journal.read_text())
        outside = tmp_path / "must-not-delete"
        outside.mkdir()
        payload["backup_workspace"] = str(outside)
        journal.write_text(json.dumps(payload))

        with pytest.raises(RuntimeError, match="path ownership mismatch"):
            mat.finalize_candidate_promotion(branch_id)

        assert outside.is_dir()

    @pytest.mark.parametrize(
        ("field", "malformed"),
        [
            ("terminalize_hypothesis_on_rollback", "false"),
            ("hypothesis_id", ""),
            ("promotion_kind", "reconcile"),
        ],
    )
    def test_malformed_promotion_journal_ownership_fails_closed(
        self,
        mat: WorkspaceMaterializer,
        code_base: Path,
        campaign_dir: Path,
        field: str,
        malformed: object,
    ) -> None:
        branch_id = f"malformed-{field}"
        durable = mat.create_branch_workspace(branch_id, str(code_base))
        candidate = mat.create_candidate_workspace(branch_id, durable)
        mat.promote_candidate_workspace(
            candidate,
            branch_id,
            hypothesis_id="h-malformed-journal",
        )
        journal = campaign_dir / "promotion_journals" / f"{branch_id}.json"
        payload = json.loads(journal.read_text())
        payload[field] = malformed
        journal.write_text(json.dumps(payload))

        with pytest.raises(RuntimeError, match="promotion journal is invalid"):
            mat.recover_candidate_promotion(
                branch_id,
                persisted_current_hash=None,
                persisted_last_clean_hash=None,
            )

    def test_failed_promoted_journal_write_restores_base_before_unlink(
        self,
        mat: WorkspaceMaterializer,
        code_base: Path,
        campaign_dir: Path,
        monkeypatch,
    ):
        branch_id = "journal-second-write"
        durable = mat.create_branch_workspace(branch_id, str(code_base))
        base_source = (Path(durable) / "operators" / "swap.py").read_text()
        candidate = mat.create_candidate_workspace(branch_id, durable)
        (Path(candidate) / "operators" / "swap.py").write_text("candidate = True\n")
        original_write = workspace_module._atomic_json_write
        calls = 0

        def fail_second_write(path, payload):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("promoted journal write unavailable")
            return original_write(path, payload)

        monkeypatch.setattr(workspace_module, "_atomic_json_write", fail_second_write)
        with pytest.raises(OSError, match="promoted journal write unavailable"):
            mat.promote_candidate_workspace(
                candidate,
                branch_id,
                hypothesis_id="h-second-write",
            )

        assert (Path(durable) / "operators" / "swap.py").read_text() == base_source
        assert not Path(candidate).exists()
        journal = campaign_dir / "promotion_journals" / f"{branch_id}.json"
        assert json.loads(journal.read_text())["status"] == "rolled_back"
        recovery = mat.recover_candidate_promotion(
            branch_id,
            persisted_current_hash=None,
            persisted_last_clean_hash=None,
        )
        assert recovery.status == "rolled_back"
        assert recovery.hypothesis_id == "h-second-write"
        mat.finalize_candidate_promotion(branch_id)
        assert not Path(candidate).exists()
        assert not journal.exists()

    @pytest.mark.parametrize(
        "crash_shape",
        ["after_durable_to_backup", "after_candidate_to_durable"],
    )
    def test_prepared_journal_recovers_both_rename_interruption_shapes(
        self,
        mat: WorkspaceMaterializer,
        code_base: Path,
        campaign_dir: Path,
        crash_shape: str,
    ):
        mat = WorkspaceMaterializer(
            str(campaign_dir),
            editable_patterns=("operators/*.py",),
        )
        branch_id = f"rename-shape-{crash_shape}"
        durable = Path(mat.create_branch_workspace(branch_id, str(code_base)))
        base_hash = mat.compute_code_hash(str(durable))
        base_source = (durable / "operators" / "swap.py").read_text()
        candidate = Path(mat.create_candidate_workspace(branch_id, str(durable)))
        (candidate / "operators" / "swap.py").write_text("candidate = True\n")
        candidate_hash = mat.compute_code_hash(str(candidate))
        backup = durable.parent / f".{branch_id}.verified-backup-interrupted"
        journal = campaign_dir / "promotion_journals" / f"{branch_id}.json"
        journal.write_text(
            json.dumps(
                {
                    "schema_version": "candidate-promotion-journal.v1",
                    "branch_id": branch_id,
                    "status": "prepared",
                    "candidate_workspace": str(candidate),
                    "durable_workspace": str(durable),
                    "backup_workspace": str(backup),
                    "base_code_hash": base_hash,
                    "base_physical_code_hash": base_hash,
                    "candidate_code_hash": candidate_hash,
                    "hypothesis_id": "h-rename-shape",
                    "terminalize_hypothesis_on_rollback": True,
                    "promotion_kind": "explore",
                }
            )
        )
        durable.rename(backup)
        if crash_shape == "after_candidate_to_durable":
            candidate.rename(durable)

        recovery = mat.recover_candidate_promotion(
            branch_id,
            persisted_current_hash=base_hash,
            persisted_last_clean_hash=base_hash,
        )

        assert recovery.status == "rolled_back"
        assert recovery.hypothesis_id == "h-rename-shape"
        assert (durable / "operators" / "swap.py").read_text() == base_source
        assert not candidate.exists()
        assert not backup.exists()
        assert json.loads(journal.read_text())["status"] == "rolled_back"
        mat.finalize_candidate_promotion(branch_id)
        assert not journal.exists()

    def test_recovery_rejects_tampered_backup_before_any_destructive_change(
        self,
        mat: WorkspaceMaterializer,
        code_base: Path,
        campaign_dir: Path,
    ) -> None:
        mat = WorkspaceMaterializer(
            str(campaign_dir),
            editable_patterns=("operators/*.py",),
        )
        branch_id = "tampered-backup"
        durable = Path(mat.create_branch_workspace(branch_id, str(code_base)))
        base_hash = mat.compute_code_hash(str(durable))
        candidate = Path(mat.create_candidate_workspace(branch_id, str(durable)))
        (candidate / "operators" / "swap.py").write_text("candidate = True\n")
        candidate_hash = mat.compute_code_hash(str(candidate))
        mat.promote_candidate_workspace(
            str(candidate),
            branch_id,
            base_code_hash=base_hash,
            hypothesis_id="h-tampered-backup",
        )
        journal = campaign_dir / "promotion_journals" / f"{branch_id}.json"
        payload = json.loads(journal.read_text())
        backup = Path(payload["backup_workspace"])
        (backup / "operators" / "swap.py").write_text("tampered = True\n")
        durable_before = (durable / "operators" / "swap.py").read_text()
        backup_before = (backup / "operators" / "swap.py").read_text()

        with pytest.raises(RuntimeError, match="rollback identity conflict"):
            mat.recover_candidate_promotion(
                branch_id,
                persisted_current_hash=base_hash,
                persisted_last_clean_hash=base_hash,
            )

        assert mat.compute_code_hash(str(durable)) == candidate_hash
        assert (durable / "operators" / "swap.py").read_text() == durable_before
        assert not candidate.exists()
        assert backup.is_dir()
        assert (backup / "operators" / "swap.py").read_text() == backup_before

    def test_recovery_rejects_missing_required_backup_without_deleting_candidate(
        self,
        mat: WorkspaceMaterializer,
        code_base: Path,
        campaign_dir: Path,
    ) -> None:
        mat = WorkspaceMaterializer(
            str(campaign_dir),
            editable_patterns=("operators/*.py",),
        )
        branch_id = "missing-required-backup"
        durable = Path(mat.create_branch_workspace(branch_id, str(code_base)))
        base_hash = mat.compute_code_hash(str(durable))
        candidate = Path(mat.create_candidate_workspace(branch_id, str(durable)))
        (candidate / "operators" / "swap.py").write_text("candidate = True\n")
        candidate_hash = mat.compute_code_hash(str(candidate))
        mat.promote_candidate_workspace(
            str(candidate),
            branch_id,
            base_code_hash=base_hash,
            hypothesis_id="h-missing-backup",
        )
        journal = campaign_dir / "promotion_journals" / f"{branch_id}.json"
        payload = json.loads(journal.read_text())
        backup = Path(payload["backup_workspace"])
        shutil.rmtree(backup)
        durable_before = (durable / "operators" / "swap.py").read_text()

        with pytest.raises(RuntimeError, match="rollback identity conflict"):
            mat.recover_candidate_promotion(
                branch_id,
                persisted_current_hash=base_hash,
                persisted_last_clean_hash=base_hash,
            )

        assert mat.compute_code_hash(str(durable)) == candidate_hash
        assert (durable / "operators" / "swap.py").read_text() == durable_before
        assert not candidate.exists()
        assert not backup.exists()


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

    def test_multi_file_preflight_failure_leaves_workspace_unchanged(
        self,
        campaign_dir: Path,
        code_base: Path,
    ):
        mat = WorkspaceMaterializer(
            str(campaign_dir),
            frozen_patterns=frozenset({"solver.py"}),
        )
        ws = mat.create_branch_workspace("b2-preflight", str(code_base))
        patch = PatchProposal(
            file_path="operators/swap.py",
            action="modify",
            code_content="changed = True\n",
            additional_changes=(
                PatchFileChange(
                    file_path="solver.py",
                    action="modify",
                    code_content="# forbidden\n",
                ),
            ),
        )

        with pytest.raises(FrozenFileError):
            mat.apply_patch(ws, patch)

        assert (Path(ws) / "operators" / "swap.py").read_text() == (
            "class SwapOperator:\n    pass\n"
        )
        assert (Path(ws) / "solver.py").read_text() == "# solver\n"

    def test_multi_file_staging_failure_rolls_back_all_changes(
        self,
        mat: WorkspaceMaterializer,
        code_base: Path,
        monkeypatch,
    ):
        ws = mat.create_branch_workspace("b2-rollback", str(code_base))
        original_apply = mat._apply_file_change
        calls = 0

        def fail_second(staged_ws, change):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated second write failure")
            return original_apply(staged_ws, change)

        monkeypatch.setattr(mat, "_apply_file_change", fail_second)
        patch = PatchProposal(
            file_path="operators/swap.py",
            action="modify",
            code_content="changed = True\n",
            additional_changes=(
                PatchFileChange(
                    file_path="policies/helper.py",
                    action="create",
                    code_content="VALUE = 1\n",
                ),
            ),
        )

        with pytest.raises(OSError, match="second write failure"):
            mat.apply_patch(ws, patch)

        assert (Path(ws) / "operators" / "swap.py").read_text() == (
            "class SwapOperator:\n    pass\n"
        )
        assert not (Path(ws) / "policies" / "helper.py").exists()
        assert not list(Path(ws).parent.glob(".b2-rollback.patch-*"))

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

    def test_frozen_file_rejected(self, campaign_dir: Path, code_base: Path):
        mat = WorkspaceMaterializer(
            str(campaign_dir),
            frozen_patterns=frozenset({"solver.py"}),
        )
        ws = mat.create_branch_workspace("b4", str(code_base))
        patch = PatchProposal(
            file_path="solver.py",
            action="modify",
            code_content="# hacked\n",
        )
        with pytest.raises(FrozenFileError):
            mat.apply_patch(ws, patch)

    def test_frozen_oracle_rejected(self, campaign_dir: Path, code_base: Path):
        mat = WorkspaceMaterializer(
            str(campaign_dir),
            frozen_patterns=frozenset({"oracle.py"}),
        )
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

    def test_hash_changes_on_new_content(self, campaign_dir: Path, code_base: Path):
        mat = WorkspaceMaterializer(
            str(campaign_dir),
            editable_patterns=("operators",),
        )
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

    def test_cleanup_nonexistent_is_noop(
        self, mat: WorkspaceMaterializer, tmp_path: Path
    ):
        mat.cleanup(str(tmp_path / "does_not_exist"))  # should not raise
