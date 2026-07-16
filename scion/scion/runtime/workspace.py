"""WorkspaceMaterializer: create and manage branch workspaces."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Optional

from scion.core.models import (
    ChampionState,
    PatchFileChange,
    PatchProposal,
    patch_file_changes,
)
from scion.core.path_match import segment_glob_match
from scion.core.paths import normalize_relative_patch_path
from scion.core.research_surface_index import normalize_editable_identity_patterns

# Generic runtime has no problem-specific frozen files by default.
_DEFAULT_FROZEN_PATTERNS = frozenset()


class FrozenFileError(Exception):
    """Raised when apply_patch attempts to modify a frozen file."""


@dataclass(frozen=True)
class CandidatePromotionRecovery:
    status: Literal["none", "rolled_back", "candidate_committed"]
    hypothesis_id: str | None = None
    terminalize_hypothesis_on_rollback: bool = True
    promotion_kind: str = "explore"


class WorkspaceMaterializer:
    """Manages filesystem workspaces for Scion branch experiments.

    Directory layout under campaign_dir::

        campaign_dir/
            workspaces/
                <branch_id>/   ← created by create_branch_workspace
            champions/
                v<N>/          ← created by create_champion_snapshot
    """

    def __init__(
        self,
        campaign_dir: str,
        frozen_patterns: Optional[frozenset[str]] = None,
        editable_patterns: Optional[Iterable[str]] = None,
    ) -> None:
        self._campaign_dir = Path(campaign_dir)
        self._workspaces_dir = self._campaign_dir / "workspaces"
        self._candidate_workspaces_dir = self._campaign_dir / "candidate_workspaces"
        self._champions_dir = self._campaign_dir / "champions"
        self._promotion_journals_dir = self._campaign_dir / "promotion_journals"
        self._frozen_patterns = (
            _DEFAULT_FROZEN_PATTERNS if frozen_patterns is None else frozen_patterns
        )
        self._editable_patterns = (
            None
            if editable_patterns is None
            else normalize_editable_identity_patterns(editable_patterns)
        )

        self._workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._candidate_workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._champions_dir.mkdir(parents=True, exist_ok=True)
        self._promotion_journals_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir = self._campaign_dir / "archive"
        self._archive_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_branch_workspace(self, branch_id: str, code_base: str) -> str:
        """Copy code_base into a fresh branch workspace.

        Args:
            branch_id: Unique identifier for the branch.
            code_base: Path to the source code directory to copy.

        Returns:
            Absolute path to the new workspace directory.

        Raises:
            FileNotFoundError: If code_base does not exist.
        """
        src = Path(code_base)
        if not src.exists():
            raise FileNotFoundError(f"code_base does not exist: {code_base}")

        dest = self._workspaces_dir / branch_id
        if dest.exists():
            shutil.rmtree(dest)

        shutil.copytree(src, dest, symlinks=False)
        # Ensure workspace is writable even if copied from a read-only champion snapshot
        _make_tree_writable(dest)
        return str(dest)

    def create_candidate_workspace(
        self,
        branch_id: str,
        source_workspace: str,
    ) -> str:
        """Copy a clean branch base into an isolated candidate workspace."""

        src = Path(source_workspace).resolve()
        if not src.is_dir():
            raise FileNotFoundError(
                f"candidate source workspace does not exist: {source_workspace}"
            )
        branch_dir = self._candidate_workspaces_dir / branch_id
        branch_dir.mkdir(parents=True, exist_ok=True)
        candidate = branch_dir / uuid.uuid4().hex
        shutil.copytree(src, candidate, symlinks=False)
        _make_tree_writable(candidate)
        return str(candidate)

    def promote_candidate_workspace(
        self,
        candidate_workspace: str,
        branch_id: str,
        *,
        base_code_hash: str | None = None,
        hypothesis_id: str | None = None,
        terminalize_hypothesis_on_rollback: bool = True,
        promotion_kind: str = "explore",
    ) -> str:
        """Promote a candidate while retaining a rollback journal and backup."""

        if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
            raise ValueError("candidate promotion hypothesis_id is required")
        if not isinstance(terminalize_hypothesis_on_rollback, bool):
            raise TypeError(
                "terminalize_hypothesis_on_rollback must be bool"
            )
        if promotion_kind not in {"explore", "reconcile"}:
            raise ValueError("candidate promotion kind is invalid")
        if terminalize_hypothesis_on_rollback != (promotion_kind == "explore"):
            raise ValueError("candidate promotion rollback ownership is invalid")
        journal_path = self._promotion_journal_path(branch_id)
        candidate = Path(candidate_workspace).resolve()
        expected_parent = (self._candidate_workspaces_dir / branch_id).resolve()
        if candidate.parent != expected_parent or not candidate.is_dir():
            raise ValueError("candidate workspace is not owned by the requested branch")

        durable = self._workspaces_dir / branch_id
        backup = (
            self._workspaces_dir / f".{branch_id}.verified-backup-{uuid.uuid4().hex}"
        )
        if backup.exists():  # pragma: no cover - UUID collision guard
            raise FileExistsError(f"candidate promotion backup exists: {backup}")

        if journal_path.exists():
            raise RuntimeError(f"candidate promotion journal already exists: {branch_id}")
        journal = {
            "schema_version": "candidate-promotion-journal.v1",
            "branch_id": branch_id,
            "status": "prepared",
            "candidate_workspace": str(candidate),
            "durable_workspace": str(durable.resolve()),
            "backup_workspace": str(backup.resolve()),
            "base_code_hash": base_code_hash,
            "base_physical_code_hash": (
                self.compute_code_hash(str(durable)) if durable.is_dir() else None
            ),
            "candidate_code_hash": self.compute_code_hash(str(candidate)),
            "hypothesis_id": hypothesis_id.strip(),
            "terminalize_hypothesis_on_rollback": bool(
                terminalize_hypothesis_on_rollback
            ),
            "promotion_kind": promotion_kind,
        }
        _atomic_json_write(journal_path, journal)

        try:
            if durable.exists():
                durable.rename(backup)
            candidate.rename(durable)
            journal["status"] = "promoted"
            _atomic_json_write(journal_path, journal)
        except BaseException:
            try:
                if durable.exists() and not candidate.exists():
                    durable.rename(candidate)
                if backup.exists():
                    if durable.exists():
                        raise RuntimeError(
                            "durable workspace still exists during promotion rollback"
                        )
                    backup.rename(durable)
                if candidate.exists():
                    _make_tree_writable(candidate)
                    shutil.rmtree(candidate)
            except BaseException as rollback_exc:
                raise RuntimeError(
                    "candidate promotion failed and rollback is incomplete; "
                    "prepared journal retained"
                ) from rollback_exc
            journal["status"] = "rolled_back"
            _atomic_json_write(journal_path, journal)
            raise
        _prune_empty_candidate_parent(expected_parent, self._candidate_workspaces_dir)
        return str(durable)

    def finalize_candidate_promotion(self, branch_id: str) -> None:
        """Release a retained backup after branch/artifact state is committed."""

        journal_path = self._promotion_journal_path(branch_id)
        journal = _read_promotion_journal(journal_path, branch_id)
        if journal is None:
            return
        _, backup, _ = self._validated_promotion_paths(journal, branch_id)
        if backup.exists():
            _make_tree_writable(backup)
            shutil.rmtree(backup)
        journal_path.unlink(missing_ok=True)

    def recover_candidate_promotion(
        self,
        branch_id: str,
        *,
        persisted_current_hash: str | None,
        persisted_last_clean_hash: str | None,
    ) -> CandidatePromotionRecovery:
        """Resolve a promotion journal against persisted and physical identity."""

        journal_path = self._promotion_journal_path(branch_id)
        journal = _read_promotion_journal(journal_path, branch_id)
        if journal is None:
            return CandidatePromotionRecovery(status="none")
        durable, backup, candidate = self._validated_promotion_paths(
            journal,
            branch_id,
        )
        candidate_hash = str(journal.get("candidate_code_hash") or "")
        hypothesis_id = str(journal.get("hypothesis_id") or "") or None
        terminalize_hypothesis_on_rollback = journal[
            "terminalize_hypothesis_on_rollback"
        ]
        promotion_kind = str(journal["promotion_kind"])
        base_hash = journal.get("base_code_hash")
        persisted_is_candidate = (
            persisted_current_hash == candidate_hash
            and persisted_last_clean_hash == candidate_hash
        )
        persisted_is_base = (
            persisted_current_hash == base_hash
            and persisted_last_clean_hash == base_hash
        )
        durable_hash = self.compute_code_hash(str(durable)) if durable.is_dir() else None
        if journal.get("status") == "rolled_back":
            if (
                not persisted_is_base
                or durable_hash != journal.get("base_physical_code_hash")
                or backup.exists()
                or candidate.exists()
            ):
                raise RuntimeError(
                    f"Branch {branch_id}: rolled-back promotion identity conflict"
                )
            return CandidatePromotionRecovery(
                status="rolled_back",
                hypothesis_id=hypothesis_id,
                terminalize_hypothesis_on_rollback=(
                    terminalize_hypothesis_on_rollback
                ),
                promotion_kind=promotion_kind,
            )
        if persisted_is_candidate and durable_hash == candidate_hash:
            return CandidatePromotionRecovery(
                status="candidate_committed",
                hypothesis_id=hypothesis_id,
                terminalize_hypothesis_on_rollback=(
                    terminalize_hypothesis_on_rollback
                ),
                promotion_kind=promotion_kind,
            )
        if not persisted_is_base:
            raise RuntimeError(
                f"Branch {branch_id}: candidate promotion journal identity conflict"
            )

        # Roll back every pre-commit physical shape, including a crash between
        # durable->backup and candidate->durable renames.
        base_physical_hash = journal.get("base_physical_code_hash")
        backup_exists = backup.exists()
        candidate_exists = candidate.exists()
        if (backup_exists and not backup.is_dir()) or (
            candidate_exists and not candidate.is_dir()
        ):
            raise RuntimeError(
                f"Branch {branch_id}: candidate promotion rollback identity conflict"
            )
        backup_hash = (
            self.compute_code_hash(str(backup)) if backup.is_dir() else None
        )
        candidate_physical_hash = (
            self.compute_code_hash(str(candidate)) if candidate.is_dir() else None
        )
        if candidate_exists and candidate_physical_hash != candidate_hash:
            raise RuntimeError(
                f"Branch {branch_id}: candidate promotion rollback identity conflict"
            )
        if backup_exists:
            if (
                not isinstance(base_physical_hash, str)
                or not base_physical_hash
                or backup_hash != base_physical_hash
                or durable_hash not in {None, candidate_hash}
                or (durable_hash is None) == (not candidate_exists)
            ):
                raise RuntimeError(
                    f"Branch {branch_id}: candidate promotion rollback identity conflict"
                )
        elif base_physical_hash is not None:
            # With an old durable base, a missing backup is safe only before
            # the first rename: durable is still the base and staging is whole.
            if durable_hash != base_physical_hash or not candidate_exists:
                raise RuntimeError(
                    f"Branch {branch_id}: candidate promotion rollback identity conflict"
                )
        elif not (
            (durable_hash is None and candidate_exists)
            or (durable_hash == candidate_hash and not candidate_exists)
        ):
            raise RuntimeError(
                f"Branch {branch_id}: candidate promotion rollback identity conflict"
            )

        if backup_exists:
            if durable.exists():
                _make_tree_writable(durable)
                shutil.rmtree(durable)
            backup.rename(durable)
        elif base_physical_hash is None and durable_hash == candidate_hash:
            _make_tree_writable(durable)
            shutil.rmtree(durable)
        if candidate.exists():
            _make_tree_writable(candidate)
            shutil.rmtree(candidate)
        journal["status"] = "rolled_back"
        _atomic_json_write(journal_path, journal)
        return CandidatePromotionRecovery(
            status="rolled_back",
            hypothesis_id=hypothesis_id,
            terminalize_hypothesis_on_rollback=(
                terminalize_hypothesis_on_rollback
            ),
            promotion_kind=promotion_kind,
        )

    def _promotion_journal_path(self, branch_id: str) -> Path:
        if not re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?",
            str(branch_id or ""),
        ):
            raise ValueError("candidate promotion branch_id is unsafe")
        return self._promotion_journals_dir / f"{branch_id}.json"

    def _validated_promotion_paths(
        self,
        journal: dict[str, object],
        branch_id: str,
    ) -> tuple[Path, Path, Path]:
        durable = Path(str(journal.get("durable_workspace") or "")).resolve()
        backup = Path(str(journal.get("backup_workspace") or "")).resolve()
        candidate = Path(str(journal.get("candidate_workspace") or "")).resolve()
        workspaces_root = self._workspaces_dir.resolve()
        candidate_parent = (self._candidate_workspaces_dir / branch_id).resolve()
        expected_durable = (self._workspaces_dir / branch_id).resolve()
        if (
            durable != expected_durable
            or backup.parent != workspaces_root
            or not backup.name.startswith(f".{branch_id}.verified-backup-")
            or candidate.parent != candidate_parent
        ):
            raise RuntimeError(
                f"Branch {branch_id}: candidate promotion journal path ownership mismatch"
            )
        return durable, backup, candidate

    def cleanup_candidate_workspace(self, candidate_workspace: str) -> None:
        """Delete an isolated candidate without touching its durable base."""

        candidate = Path(candidate_workspace).resolve()
        candidate_root = self._candidate_workspaces_dir.resolve()
        if (
            not _is_relative_to(candidate, candidate_root)
            or candidate == candidate_root
        ):
            raise ValueError("refusing to clean a non-candidate workspace")
        if candidate.exists():
            _make_tree_writable(candidate)
            shutil.rmtree(candidate)
        _prune_empty_candidate_parent(candidate.parent, candidate_root)

    def apply_patch(self, workspace: str, patch: PatchProposal) -> str:
        """Atomically materialize every declared file change.

        The file_path in patch is treated as relative to workspace root.

        Args:
            workspace: Absolute path to the branch workspace.
            patch: PatchProposal to apply.

        Returns:
            SHA-256 hex string of declared editable identity files after patch.

        Raises:
            FrozenFileError: If the patch targets a frozen file.
            ValueError: If patch.action is 'delete' (not yet supported here).
        """
        ws = Path(workspace).resolve()
        if not ws.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {workspace}")
        changes = patch_file_changes(patch)
        self._preflight_file_changes(ws, changes)

        transaction_id = uuid.uuid4().hex
        staged = ws.parent / f".{ws.name}.patch-stage-{transaction_id}"
        backup = ws.parent / f".{ws.name}.patch-backup-{transaction_id}"
        try:
            shutil.copytree(ws, staged, symlinks=False)
            _make_tree_writable(staged)
            for change in changes:
                self._apply_file_change(staged, change)
            code_hash = self.compute_code_hash(str(staged))

            ws.rename(backup)
            try:
                staged.rename(ws)
            except BaseException:
                backup.rename(ws)
                raise
            try:
                shutil.rmtree(backup)
            except OSError:
                # The committed workspace is authoritative. A stale backup is
                # cleanup debris, not a reason to report a failed materialization.
                pass
            return code_hash
        finally:
            if staged.exists():
                shutil.rmtree(staged, ignore_errors=True)

    def _preflight_file_changes(
        self,
        ws: Path,
        changes: Iterable[PatchFileChange],
    ) -> None:
        seen: set[str] = set()
        for change in changes:
            file_rel = normalize_relative_patch_path(change.file_path)
            if file_rel in seen:
                raise ValueError(f"patch repeats file_path: {file_rel}")
            seen.add(file_rel)
            if self._is_frozen(file_rel):
                raise FrozenFileError(
                    f"apply_patch refused: '{change.file_path}' matches frozen patterns"
                )
            target = (ws / file_rel).resolve()
            if not _is_relative_to(target, ws):
                raise ValueError(
                    f"patch file_path escapes workspace: {change.file_path}"
                )
            if change.action not in {"modify", "create", "delete"}:
                raise ValueError(f"unsupported patch action: {change.action}")
            if change.action != "delete" and not isinstance(
                change.code_content,
                str,
            ):
                raise TypeError(
                    f"patch code_content must be a string: {change.file_path}"
                )

    def _apply_file_change(self, ws: Path, change: PatchFileChange) -> None:
        # Second-level frozen-file check (Contract Gate is the first)
        file_rel = normalize_relative_patch_path(change.file_path)
        if self._is_frozen(file_rel):
            raise FrozenFileError(
                f"apply_patch refused: '{change.file_path}' matches frozen patterns"
            )

        target = (ws / file_rel).resolve()
        if not _is_relative_to(target, ws):
            raise ValueError(f"patch file_path escapes workspace: {change.file_path}")

        if change.action == "delete":
            if target.exists():
                target.unlink()
        else:
            # "modify" or "create"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(change.code_content, encoding="utf-8")

        # For new operator files, register them in registry.yaml so the solver picks them up
        if (
            change.action == "create"
            and file_rel.startswith("operators/")
            and file_rel.endswith(".py")
        ):
            _update_registry(ws, file_rel, change.code_content)

    def create_champion_snapshot(
        self,
        champion: ChampionState,
        target_dir: str,
    ) -> str:
        """Create a read-only snapshot of the champion workspace.

        Args:
            champion: Champion state containing code_snapshot_path.
            target_dir: Parent directory under which the snapshot is placed.

        Returns:
            Absolute path to the snapshot directory.
        """
        src = Path(champion.code_snapshot_path)
        dest = Path(target_dir) / f"champion_v{champion.version}"

        if dest.exists():
            # Make writable first so we can remove it
            _make_tree_writable(dest)
            shutil.rmtree(dest)

        shutil.copytree(src, dest, symlinks=False)

        # Make the whole tree read-only
        _make_tree_readonly(dest)

        return str(dest)

    def cleanup(self, workspace: str) -> None:
        """Remove the workspace directory (best-effort).

        Args:
            workspace: Absolute path to the branch workspace to delete.
        """
        ws = Path(workspace)
        if ws.exists():
            # Ensure writable before removal
            _make_tree_writable(ws)
            shutil.rmtree(ws)

    def archive_workspace(self, workspace: str, branch_id: str) -> str | None:
        """Copy editable identity files into archive/<branch_id_short>/.

        Called before cleanup on ABANDON so generated research-surface files are
        preserved for post-campaign analysis.

        Args:
            workspace: Absolute path to the branch workspace.
            branch_id: Branch ID used to name the archive sub-directory.

        Returns:
            Absolute path to the archive directory, or None if no editable
            research-surface directories are present.
        """
        ws = Path(workspace)
        files = self._identity_files(ws)
        if not files:
            return None

        # Use first 8 chars of branch_id for readability
        short_id = str(branch_id)[:8]
        archive_dest = self._archive_dir / short_id
        # If a prior archive exists for the same short id, append suffix
        if archive_dest.exists():
            suffix = 1
            while (self._archive_dir / f"{short_id}_{suffix}").exists():
                suffix += 1
            archive_dest = self._archive_dir / f"{short_id}_{suffix}"

        archive_dest.mkdir(parents=True)
        for source in files:
            rel = source.relative_to(ws)
            dest = archive_dest / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest, follow_symlinks=False)
        import logging as _logging

        _logging.getLogger(__name__).info(
            "Archived research surfaces from branch %s → %s", branch_id, archive_dest
        )
        return str(archive_dest)

    def archive_decision_workspace(
        self,
        workspace: str,
        branch_id: str,
        transaction_id: str,
        *,
        expected_code_hash: str,
        expected_snapshot_hash: str | None = None,
    ) -> str:
        """Idempotently archive one ABANDON transaction's editable identity.

        The deterministic destination is also the durable cleanup receipt.  A
        startup retry may therefore distinguish "archive completed, cleanup
        crashed" from a missing source instead of creating ``_1`` archives or
        silently accepting evidence loss.
        """

        if re.fullmatch(r"[0-9a-f]{64}", str(transaction_id or "")) is None:
            raise ValueError("decision archive transaction identity is invalid")
        if re.fullmatch(r"[0-9a-f]{64}", str(expected_code_hash or "")) is None:
            raise ValueError("decision archive code identity is invalid")
        safe_branch = re.sub(r"[^A-Za-z0-9_.-]", "_", str(branch_id or ""))
        if not safe_branch:
            raise ValueError("decision archive branch identity is invalid")
        branch_digest = hashlib.sha256(str(branch_id).encode("utf-8")).hexdigest()[:8]
        archive_dest = self._archive_dir / (
            f"{safe_branch[:40]}-{branch_digest}-decision-{transaction_id[:16]}"
        )
        receipt_path = self._archive_dir / f".{transaction_id}.receipt.json"
        ws = Path(workspace).resolve()
        expected_ws = (self._workspaces_dir / str(branch_id)).resolve()
        if ws != expected_ws:
            raise ValueError("decision archive workspace ownership mismatch")

        receipt = _read_decision_archive_receipt(receipt_path)
        expected_receipt = {
            "schema_version": "decision-archive-receipt.v1",
            "transaction_id": transaction_id,
            "branch_id": str(branch_id),
            "archive_name": archive_dest.name,
            "code_hash": expected_code_hash,
            "snapshot_hash": str(expected_snapshot_hash or ""),
        }
        if receipt is not None:
            if receipt != expected_receipt:
                raise RuntimeError("decision archive receipt identity conflict")
            if not archive_dest.is_dir():
                raise RuntimeError("decision archive receipt has no archive")
            if self.compute_code_hash(str(archive_dest)) != expected_code_hash:
                raise RuntimeError("decision archive code identity conflict")
            return str(archive_dest)
        if archive_dest.exists() and not archive_dest.is_dir():
            raise RuntimeError("decision archive destination is not a directory")
        if not ws.is_dir():
            raise RuntimeError(
                "decision workspace is missing without a verified archive receipt"
            )
        if self.compute_code_hash(str(ws)) != expected_code_hash:
            raise RuntimeError("decision workspace code identity conflict")
        if (
            expected_snapshot_hash
            and self.compute_snapshot_hash(str(ws)) != expected_snapshot_hash
        ):
            raise RuntimeError("decision workspace executable identity conflict")

        if not archive_dest.is_dir():
            temporary = self._archive_dir / (
                f".{archive_dest.name}.tmp-{uuid.uuid4().hex}"
            )
            try:
                temporary.mkdir(parents=False)
                for source in self._identity_files(ws):
                    rel = source.relative_to(ws)
                    dest = temporary / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest, follow_symlinks=False)
                if self.compute_code_hash(str(temporary)) != expected_code_hash:
                    raise RuntimeError("decision archive copy identity conflict")
                os.replace(temporary, archive_dest)
                directory_fd = os.open(
                    self._archive_dir,
                    os.O_RDONLY | os.O_DIRECTORY,
                )
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if temporary.exists():
                    _make_tree_writable(temporary)
                    shutil.rmtree(temporary)
        elif self.compute_code_hash(str(archive_dest)) != expected_code_hash:
            raise RuntimeError("decision archive code identity conflict")
        _atomic_json_write(receipt_path, expected_receipt)
        return str(archive_dest)

    def validate_research_rejection_ownership(
        self,
        payload: dict[str, object],
        *,
        require_cleanup_receipt: bool,
    ) -> None:
        """Validate the physical clean parent and rejected-candidate owner."""

        completion_id = str(payload.get("completion_id") or "")
        branch_id = str(payload.get("branch_id") or "")
        clean_parent = payload.get("clean_code_parent")
        candidate = payload.get("rejected_candidate")
        archive_ref = payload.get("archive_ref")
        if not isinstance(clean_parent, dict):
            raise RuntimeError("research rejection clean parent is invalid")
        clean = self._resolve_campaign_ref(
            str(clean_parent.get("ref") or ""),
            allowed_roots={"workspaces", "champions"},
        )
        if not clean.is_dir():
            raise RuntimeError("research rejection clean parent is unavailable")
        if self.compute_code_hash(str(clean)) != clean_parent.get("code_hash"):
            raise RuntimeError("research rejection clean parent code identity conflict")
        if self.compute_snapshot_hash(str(clean)) != clean_parent.get("snapshot_hash"):
            raise RuntimeError(
                "research rejection clean parent snapshot identity conflict"
            )
        if candidate is None:
            if archive_ref is not None:
                raise RuntimeError("contract rejection unexpectedly owns an archive")
            return
        if not isinstance(candidate, dict):
            raise RuntimeError("research rejection candidate identity is invalid")
        candidate_path = self._resolve_campaign_ref(
            str(candidate.get("workspace_ref") or ""),
            allowed_roots={"candidate_workspaces"},
        )
        expected_parent = (self._candidate_workspaces_dir / branch_id).resolve()
        if candidate_path.parent != expected_parent:
            raise RuntimeError("research rejection candidate ownership mismatch")
        receipt, archive = self._research_rejection_receipt(
            completion_id=completion_id,
            branch_id=branch_id,
            candidate=candidate,
            archive_ref=str(archive_ref or ""),
        )
        if receipt is not None:
            self._validate_research_rejection_archive(archive, candidate)
            if candidate_path.exists():
                self._validate_research_rejection_candidate(candidate_path, candidate)
            if require_cleanup_receipt and candidate_path.exists():
                raise RuntimeError("committed rejected candidate was not cleaned")
            return
        if require_cleanup_receipt:
            raise RuntimeError("research rejection cleanup receipt is unavailable")
        self._validate_research_rejection_candidate(candidate_path, candidate)

    def validate_research_rejection_sources(
        self,
        *,
        branch_id: str,
        clean_parent: dict[str, object],
        candidate: dict[str, object] | None,
    ) -> None:
        """Validate physical identities during the SQLite prepare transaction."""

        clean = self._resolve_campaign_ref(
            str(clean_parent.get("ref") or ""),
            allowed_roots={"workspaces", "champions"},
        )
        if not clean.is_dir():
            raise RuntimeError("research rejection clean parent is unavailable")
        if self.compute_code_hash(str(clean)) != clean_parent.get("code_hash"):
            raise RuntimeError("research rejection clean parent code identity conflict")
        if self.compute_snapshot_hash(str(clean)) != clean_parent.get("snapshot_hash"):
            raise RuntimeError(
                "research rejection clean parent snapshot identity conflict"
            )
        if candidate is None:
            return
        candidate_path = self._resolve_campaign_ref(
            str(candidate.get("workspace_ref") or ""),
            allowed_roots={"candidate_workspaces"},
        )
        if candidate_path.parent != (
            self._candidate_workspaces_dir / str(branch_id)
        ).resolve():
            raise RuntimeError("research rejection candidate ownership mismatch")
        self._validate_research_rejection_candidate(candidate_path, candidate)

    def validate_research_rejection_archive_receipt(
        self,
        payload: dict[str, object],
    ) -> None:
        """Validate immutable cleanup evidence without reusing a mutable base."""

        candidate = payload.get("rejected_candidate")
        if candidate is None:
            if payload.get("archive_ref") is not None:
                raise RuntimeError("contract rejection unexpectedly owns an archive")
            return
        if not isinstance(candidate, dict):
            raise RuntimeError("research rejection candidate identity is invalid")
        receipt, archive = self._research_rejection_receipt(
            completion_id=str(payload.get("completion_id") or ""),
            branch_id=str(payload.get("branch_id") or ""),
            candidate=candidate,
            archive_ref=str(payload.get("archive_ref") or ""),
        )
        if receipt is None:
            raise RuntimeError("research rejection cleanup receipt is unavailable")
        self._validate_research_rejection_archive(archive, candidate)

    def archive_research_rejection_candidate(
        self,
        payload: dict[str, object],
    ) -> str:
        """Archive and remove one exact candidate using a deterministic receipt."""

        self.validate_research_rejection_ownership(
            payload,
            require_cleanup_receipt=False,
        )
        completion_id = str(payload["completion_id"])
        branch_id = str(payload["branch_id"])
        candidate = payload["rejected_candidate"]
        if not isinstance(candidate, dict):
            raise RuntimeError("verification rejection candidate is unavailable")
        candidate_path = self._resolve_campaign_ref(
            str(candidate["workspace_ref"]),
            allowed_roots={"candidate_workspaces"},
        )
        receipt, archive = self._research_rejection_receipt(
            completion_id=completion_id,
            branch_id=branch_id,
            candidate=candidate,
            archive_ref=str(payload["archive_ref"]),
        )
        if receipt is None:
            if not archive.exists():
                temporary = self._archive_dir / f".{archive.name}.tmp-{uuid.uuid4().hex}"
                try:
                    temporary.mkdir(parents=False)
                    files = list(self._identity_files(candidate_path))
                    registry_path = candidate_path / "registry.yaml"
                    if registry_path.is_file():
                        files.append(registry_path)
                    for source in _dedupe_sorted_paths(files, candidate_path):
                        rel = source.relative_to(candidate_path)
                        destination = temporary / rel
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, destination, follow_symlinks=False)
                    self._validate_research_rejection_archive(temporary, candidate)
                    os.replace(temporary, archive)
                    directory_fd = os.open(
                        self._archive_dir,
                        os.O_RDONLY | os.O_DIRECTORY,
                    )
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                finally:
                    if temporary.exists():
                        _make_tree_writable(temporary)
                        shutil.rmtree(temporary)
            else:
                self._validate_research_rejection_archive(archive, candidate)
            receipt_path = self._archive_dir / (
                f".research-rejection-{completion_id}.receipt.json"
            )
            _atomic_json_write(
                receipt_path,
                self._research_rejection_receipt_payload(
                    completion_id=completion_id,
                    branch_id=branch_id,
                    candidate=candidate,
                    archive_ref=str(payload["archive_ref"]),
                ),
            )
        if candidate_path.exists():
            self._validate_research_rejection_candidate(candidate_path, candidate)
            self.cleanup_candidate_workspace(str(candidate_path))
        self.validate_research_rejection_ownership(
            payload,
            require_cleanup_receipt=True,
        )
        return str(archive)

    def _research_rejection_receipt(
        self,
        *,
        completion_id: str,
        branch_id: str,
        candidate: dict[str, object],
        archive_ref: str,
    ) -> tuple[dict[str, object] | None, Path]:
        if re.fullmatch(r"[0-9a-f]{64}", completion_id) is None:
            raise RuntimeError("research rejection completion identity is invalid")
        archive = self._resolve_campaign_ref(
            archive_ref,
            allowed_roots={"archive"},
        )
        expected_archive = (
            self._archive_dir / f"research-rejection-{completion_id}"
        ).resolve()
        if archive != expected_archive:
            raise RuntimeError("research rejection archive ownership mismatch")
        receipt_path = self._archive_dir / (
            f".research-rejection-{completion_id}.receipt.json"
        )
        receipt = _read_decision_archive_receipt(receipt_path)
        if receipt is not None and receipt != self._research_rejection_receipt_payload(
            completion_id=completion_id,
            branch_id=branch_id,
            candidate=candidate,
            archive_ref=archive_ref,
        ):
            raise RuntimeError("research rejection receipt identity conflict")
        if receipt is None and archive.exists():
            self._validate_research_rejection_archive(archive, candidate)
        return receipt, archive

    @staticmethod
    def _research_rejection_receipt_payload(
        *,
        completion_id: str,
        branch_id: str,
        candidate: dict[str, object],
        archive_ref: str,
    ) -> dict[str, object]:
        return {
            "schema_version": "research-rejection-archive-receipt.v1",
            "completion_id": completion_id,
            "branch_id": branch_id,
            "candidate_workspace_ref": candidate["workspace_ref"],
            "archive_ref": archive_ref,
            "code_hash": candidate["code_hash"],
            "snapshot_hash": candidate["snapshot_hash"],
            "patch_digest": candidate["patch_digest"],
            "hypothesis_id": candidate["hypothesis_id"],
        }

    def _validate_research_rejection_candidate(
        self,
        candidate_path: Path,
        candidate: dict[str, object],
    ) -> None:
        if not candidate_path.is_dir():
            raise RuntimeError("research rejection candidate is unavailable")
        if self.compute_code_hash(str(candidate_path)) != candidate["code_hash"]:
            raise RuntimeError("research rejection candidate code identity conflict")
        if self.compute_snapshot_hash(str(candidate_path)) != candidate["snapshot_hash"]:
            raise RuntimeError(
                "research rejection candidate snapshot identity conflict"
            )

    def _validate_research_rejection_archive(
        self,
        archive: Path,
        candidate: dict[str, object],
    ) -> None:
        if not archive.is_dir():
            raise RuntimeError("research rejection archive is unavailable")
        if self.compute_code_hash(str(archive)) != candidate["code_hash"]:
            raise RuntimeError("research rejection archive code identity conflict")
        if self.compute_snapshot_hash(str(archive)) != candidate["snapshot_hash"]:
            raise RuntimeError("research rejection archive snapshot identity conflict")

    def _resolve_campaign_ref(
        self,
        ref: str,
        *,
        allowed_roots: set[str],
    ) -> Path:
        if not ref or Path(ref).is_absolute():
            raise RuntimeError("research rejection artifact ref is invalid")
        parts = Path(ref).parts
        if not parts or parts[0] not in allowed_roots or ".." in parts:
            raise RuntimeError("research rejection artifact ref is invalid")
        resolved = (self._campaign_dir / ref).resolve()
        if not _is_relative_to(resolved, self._campaign_dir.resolve()):
            raise RuntimeError("research rejection artifact ref escapes campaign")
        return resolved

    def compute_code_hash(self, workspace: str) -> str:
        """Compute SHA-256 of editable identity files.

        Args:
            workspace: Absolute path to the workspace.

        Returns:
            Hex-encoded SHA-256 string.
        """
        ws = Path(workspace)
        return _hash_files(ws, self._identity_files(ws))

    def editable_identity_manifest(self, workspace: str) -> dict[str, object]:
        """Return the exact editable-file identity used by ``compute_code_hash``.

        Formal replay artifacts use this manifest to describe a cumulative
        candidate without reimplementing research-surface path selection.
        File contents remain in the replay materialization artifact; this
        manifest carries only canonical paths, per-file hashes, and the tree
        hash used by branch verification.
        """

        ws = Path(workspace).resolve()
        if not ws.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {workspace}")
        files = _dedupe_sorted_paths(self._identity_files(ws), ws)
        return {
            "schema_version": "scion.editable_identity_manifest.v1",
            "files": [
                {
                    "file_path": path.relative_to(ws).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for path in files
            ],
            "code_hash": _hash_files(ws, files),
        }

    def compute_snapshot_hash(self, workspace: str) -> str:
        """Compute SHA-256 of editable identity files + registry.yaml.

        Includes registry.yaml so weight changes affect the champion hash.

        Args:
            workspace: Absolute path to the workspace.

        Returns:
            Hex-encoded SHA-256 string.
        """
        ws = Path(workspace)
        return compute_snapshot_hash_for_files(ws, self._identity_files(ws))

    def create_mutable_staging(self, source_workspace: str) -> str:
        """Create a writable staging copy of source_workspace.

        Used in the promote + weight-optimization flow so that weight writes
        land on a mutable copy before the snapshot is frozen.

        Args:
            source_workspace: Path to copy from (may be read-only).

        Returns:
            Absolute path to the new writable staging directory.
        """
        import time as _time

        src = Path(source_workspace)
        staging_dir = self._campaign_dir / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)

        staging = staging_dir / f"staging_{int(_time.time() * 1000)}"
        if staging.exists():
            _make_tree_writable(staging)
            shutil.rmtree(staging)

        shutil.copytree(src, staging, symlinks=False)
        _make_tree_writable(staging)
        return str(staging)

    def freeze_snapshot(self, path: str) -> None:
        """Recursively make path and its contents read-only.

        Args:
            path: Absolute path to the directory to freeze.
        """
        _make_tree_readonly(Path(path))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_frozen(self, file_rel: str) -> bool:
        """Return True if file_rel matches any frozen pattern."""
        import fnmatch

        for pattern in self._frozen_patterns:
            if fnmatch.fnmatch(file_rel, pattern):
                return True
            # Also check basename match for flat patterns without '/'
            if "/" not in pattern and fnmatch.fnmatch(Path(file_rel).name, pattern):
                return True
        return False

    def _identity_files(self, ws: Path) -> list[Path]:
        if self._editable_patterns is None:
            return []
        return _explicit_identity_files(
            ws,
            patterns=self._editable_patterns,
            is_frozen=self._is_frozen,
        )


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _prune_empty_candidate_parent(path: Path, candidate_root: Path) -> None:
    """Remove empty per-branch candidate directories, never the shared root."""

    if path == candidate_root or not _is_relative_to(path, candidate_root):
        return
    try:
        path.rmdir()
    except OSError:
        pass


def _atomic_json_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.tmp-{uuid.uuid4().hex}"
    try:
        content = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _read_promotion_journal(path: Path, branch_id: str) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Branch {branch_id}: candidate promotion journal is invalid"
        ) from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != "candidate-promotion-journal.v1"
        or payload.get("branch_id") != branch_id
        or payload.get("status") not in {"prepared", "promoted", "rolled_back"}
        or not isinstance(payload.get("hypothesis_id"), str)
        or not str(payload.get("hypothesis_id")).strip()
        or not isinstance(
            payload.get("terminalize_hypothesis_on_rollback"),
            bool,
        )
        or payload.get("promotion_kind") not in {"explore", "reconcile"}
        or payload.get("terminalize_hypothesis_on_rollback")
        != (payload.get("promotion_kind") == "explore")
    ):
        raise RuntimeError(
            f"Branch {branch_id}: candidate promotion journal is invalid"
        )
    return payload


def _read_decision_archive_receipt(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise RuntimeError("decision archive receipt is invalid")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("decision archive receipt is invalid") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("decision archive receipt is invalid")
    return payload


def _hash_files(ws: Path, files: Iterable[Path]) -> str:
    h = hashlib.sha256()
    for file_path in _dedupe_sorted_paths(files, ws):
        rel = file_path.relative_to(ws)
        h.update(rel.as_posix().encode())
        h.update(file_path.read_bytes())
    return h.hexdigest()


def compute_snapshot_hash_for_files(
    workspace: str | Path,
    identity_files: Iterable[Path],
) -> str:
    """Hash one canonical editable identity plus optional ``registry.yaml``."""

    ws = Path(workspace)
    files = list(identity_files)
    registry_path = ws / "registry.yaml"
    if registry_path.exists():
        files.append(registry_path)
    return _hash_files(ws, files)


def _explicit_identity_files(
    ws: Path,
    *,
    patterns: Iterable[str],
    is_frozen: Callable[[str], bool],
) -> list[Path]:
    files: list[Path] = []
    resolved_ws = ws.resolve()
    for pattern in patterns:
        files.extend(
            _files_for_editable_pattern(
                ws=ws,
                resolved_ws=resolved_ws,
                pattern=pattern,
                is_frozen=is_frozen,
            )
        )
    return _dedupe_sorted_paths(files, ws)


def _files_for_editable_pattern(
    *,
    ws: Path,
    resolved_ws: Path,
    pattern: str,
    is_frozen: Callable[[str], bool],
) -> list[Path]:
    target = ws / pattern
    if not _contains_glob(pattern):
        if target.is_file():
            return _allowed_identity_files(
                (target,),
                ws=ws,
                resolved_ws=resolved_ws,
                is_frozen=is_frozen,
            )
        if target.is_dir():
            return _allowed_identity_files(
                target.rglob("*"),
                ws=ws,
                resolved_ws=resolved_ws,
                is_frozen=is_frozen,
            )
        return []

    files: list[Path] = []
    for match in ws.glob(pattern):
        if match.is_dir():
            files.extend(
                _allowed_identity_files(
                    match.rglob("*"),
                    ws=ws,
                    resolved_ws=resolved_ws,
                    is_frozen=is_frozen,
                )
            )
        else:
            files.extend(
                _allowed_identity_files(
                    (match,),
                    ws=ws,
                    resolved_ws=resolved_ws,
                    is_frozen=is_frozen,
                    pattern=pattern,
                )
            )
    return files


def _allowed_identity_files(
    candidates: Iterable[Path],
    *,
    ws: Path,
    resolved_ws: Path,
    is_frozen: Callable[[str], bool],
    pattern: str | None = None,
) -> list[Path]:
    files: list[Path] = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if not _is_relative_to(candidate.resolve(), resolved_ws):
            continue
        rel = candidate.relative_to(ws).as_posix()
        if pattern is not None and not segment_glob_match(rel, pattern):
            continue
        if is_frozen(rel):
            continue
        files.append(candidate)
    return files


def _dedupe_sorted_paths(paths: Iterable[Path], ws: Path) -> list[Path]:
    by_rel: dict[str, Path] = {}
    for path in paths:
        if not path.is_file():
            continue
        rel = path.relative_to(ws).as_posix()
        by_rel.setdefault(rel, path)
    return [by_rel[rel] for rel in sorted(by_rel)]


def _contains_glob(path: str) -> bool:
    return any(char in path for char in "*?[")


def _update_registry(ws: Path, file_rel: str, code_content: str) -> None:
    """Append a new operator entry to registry.yaml in the workspace.

    Called by apply_patch when a new operator file is created. Skips silently
    if registry.yaml is absent, the class cannot be detected, or the operator
    name is already registered.
    """
    import re

    import yaml

    registry_path = ws / "registry.yaml"
    if not registry_path.exists():
        return

    # Extract the first class definition from the generated code
    m = re.search(r"^class\s+(\w+)", code_content, re.MULTILINE)
    if not m:
        return
    class_name = m.group(1)

    op_name = Path(file_rel).stem  # e.g. "smart_move_order"

    with open(registry_path, encoding="utf-8") as f:
        registry = yaml.safe_load(f) or {}

    existing = {entry["name"] for entry in registry.get("operators", [])}
    if op_name in existing:
        return

    registry.setdefault("operators", []).append(
        {
            "name": op_name,
            "file_path": file_rel,
            "class_name": class_name,
            "weight": 0.10,
        }
    )

    with open(registry_path, "w", encoding="utf-8") as f:
        yaml.dump(registry, f, default_flow_style=False, allow_unicode=True)


def _make_tree_readonly(path: Path) -> None:
    """Recursively remove write permissions from path."""
    for root, dirs, files in os.walk(path):
        for name in files + dirs:
            fp = Path(root) / name
            try:
                current = fp.stat().st_mode
                fp.chmod(current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            except OSError:
                pass
    # Also the root itself
    try:
        current = path.stat().st_mode
        path.chmod(current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    except OSError:
        pass


def _make_tree_writable(path: Path) -> None:
    """Recursively restore write permissions so the tree can be deleted."""
    for root, dirs, files in os.walk(path):
        for name in files + dirs:
            fp = Path(root) / name
            try:
                current = fp.stat().st_mode
                fp.chmod(current | stat.S_IWUSR)
            except OSError:
                pass
    try:
        current = path.stat().st_mode
        path.chmod(current | stat.S_IWUSR)
    except OSError:
        pass
