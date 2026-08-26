"""WorkspaceMaterializer: create and manage branch workspaces."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import stat
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Iterable, Optional

from scion.core.models import (
    ChampionState,
    PatchFileChange,
    PatchProposal,
    patch_file_changes,
)
from scion.core.path_match import segment_glob_match
from scion.core.paths import normalize_relative_patch_path
from scion.core.research_surface_index import normalize_editable_patterns

# Generic runtime has no problem-specific frozen files by default.
_DEFAULT_FROZEN_PATTERNS = frozenset()
logger = logging.getLogger(__name__)


class FrozenFileError(Exception):
    """Raised when apply_patch attempts to modify a frozen file."""


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
        self._frozen_patterns = (
            _DEFAULT_FROZEN_PATTERNS if frozen_patterns is None else frozen_patterns
        )
        self._editable_patterns = (
            None
            if editable_patterns is None
            else normalize_editable_patterns(editable_patterns)
        )

        self._workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._candidate_workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._champions_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir = self._campaign_dir / "archive"
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        self._inflight_branch_workspaces: set[Path] = set()
        self._inflight_candidate_workspaces: set[Path] = set()

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
        leased_dest = Path(os.path.abspath(dest))
        workspace_root = Path(os.path.abspath(self._workspaces_dir))
        if leased_dest.parent != workspace_root:
            raise ValueError("refusing to create an invalid branch workspace")
        if dest.is_symlink():
            raise ValueError("refusing to replace a symlinked branch workspace")
        try:
            self._inflight_branch_workspaces.add(leased_dest)
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, symlinks=False)
            # Ensure workspace is writable even if copied from a read-only champion
            # snapshot.
            _make_tree_writable(dest)
        except BaseException:
            try:
                self._cleanup_leased_tree(
                    leased_dest,
                    leases=self._inflight_branch_workspaces,
                )
            except Exception:
                logger.exception("Failed to clean interrupted branch workspace")
            raise
        return str(dest)

    def create_candidate_workspace(
        self,
        source_workspace: str,
    ) -> str:
        """Copy a clean branch base into an isolated candidate workspace."""

        src = Path(source_workspace).resolve()
        if not src.is_dir():
            raise FileNotFoundError(
                f"candidate source workspace does not exist: {source_workspace}"
            )
        candidate = self._reserve_candidate_workspace()
        try:
            shutil.copytree(src, candidate, symlinks=False, dirs_exist_ok=True)
            _make_tree_writable(candidate)
        except BaseException:
            try:
                self._cleanup_leased_tree(
                    Path(os.path.abspath(candidate)),
                    leases=self._inflight_candidate_workspaces,
                )
            except Exception:
                logger.exception("Failed to clean interrupted candidate workspace")
            raise
        return str(candidate)

    def _reserve_candidate_workspace(self) -> Path:
        """Lease a random candidate path before its first filesystem mutation."""

        candidate_root = Path(os.path.abspath(self._candidate_workspaces_dir))
        while True:
            candidate = candidate_root / f"candidate-{uuid.uuid4().hex}"
            leased_candidate = Path(os.path.abspath(candidate))
            if leased_candidate in self._inflight_candidate_workspaces:
                continue
            try:
                self._inflight_candidate_workspaces.add(leased_candidate)
                candidate.mkdir(mode=0o700)
            except FileExistsError:
                self._inflight_candidate_workspaces.discard(leased_candidate)
                continue
            except BaseException:
                try:
                    self._cleanup_leased_tree(
                        leased_candidate,
                        leases=self._inflight_candidate_workspaces,
                    )
                except Exception:
                    logger.exception(
                        "Failed to clean interrupted candidate reservation"
                    )
                raise
            return candidate

    def claim_branch_workspace(self, branch_id: str, workspace: str) -> None:
        """Release a branch lease after its owner mapping is durable in memory."""

        expected = Path(os.path.abspath(self._workspaces_dir / branch_id))
        value = Path(os.path.abspath(workspace))
        if value != expected or value not in self._inflight_branch_workspaces:
            raise ValueError("branch workspace does not match an inflight lease")
        if not value.is_dir():
            raise FileNotFoundError("leased branch workspace is unavailable")
        self._inflight_branch_workspaces.remove(value)

    def claim_candidate_workspace(self, candidate_workspace: str) -> None:
        """Release a candidate lease only after Decision binds its workspace."""

        candidate = self._validated_candidate_path(candidate_workspace)
        if candidate not in self._inflight_candidate_workspaces:
            raise ValueError("candidate workspace does not match an inflight lease")
        if not candidate.is_dir():
            raise FileNotFoundError("leased candidate workspace is unavailable")
        self._inflight_candidate_workspaces.remove(candidate)

    def cleanup_inflight_workspaces(self) -> None:
        """Best-effort removal of every unclaimed workspace after interruption."""

        for candidate in tuple(self._inflight_candidate_workspaces):
            try:
                self._cleanup_leased_tree(
                    candidate,
                    leases=self._inflight_candidate_workspaces,
                )
            except Exception:
                logger.exception("Failed to clean inflight candidate workspace")
        for workspace in tuple(self._inflight_branch_workspaces):
            try:
                self._cleanup_leased_tree(
                    workspace,
                    leases=self._inflight_branch_workspaces,
                )
            except Exception:
                logger.exception("Failed to clean inflight branch workspace")

    def cleanup_branch_workspace(self, branch_id: str) -> None:
        """Remove one deterministic branch destination after interrupted setup."""

        dest = Path(os.path.abspath(self._workspaces_dir / branch_id))
        workspace_root = Path(os.path.abspath(self._workspaces_dir))
        if dest.parent != workspace_root:
            raise ValueError("refusing to clean an invalid branch workspace")
        self._cleanup_leased_tree(
            dest,
            leases=self._inflight_branch_workspaces,
        )

    def create_empty_candidate_workspace(self) -> str:
        """Create an empty isolated candidate for an explicit public closure."""

        return tempfile.mkdtemp(
            prefix="candidate-development-",
            dir=self._candidate_workspaces_dir,
        )

    def cleanup_candidate_workspace(self, candidate_workspace: str) -> None:
        """Delete an isolated candidate without touching its durable base."""

        candidate = self._validated_candidate_path(candidate_workspace)
        self._cleanup_leased_tree(
            candidate,
            leases=self._inflight_candidate_workspaces,
        )

    def _validated_candidate_path(self, candidate_workspace: str) -> Path:
        candidate = Path(os.path.abspath(candidate_workspace))
        candidate_root = Path(os.path.abspath(self._candidate_workspaces_dir))
        if candidate.parent != candidate_root:
            raise ValueError("refusing to clean a non-candidate workspace")
        return candidate

    @staticmethod
    def _cleanup_leased_tree(path: Path, *, leases: set[Path]) -> None:
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            _make_tree_writable(path)
            shutil.rmtree(path)
        leases.discard(path)

    def apply_patch(self, workspace: str, patch: PatchProposal) -> str:
        """Materialize every preflighted change in an isolated workspace.

        The file_path in patch is treated as relative to workspace root.

        Args:
            workspace: Absolute path to the branch workspace.
            patch: PatchProposal to apply.

        Returns:
            SHA-256 content digest of the declared editable files after patch.

        Raises:
            FrozenFileError: If the patch targets a frozen file.
        """
        self.apply_ephemeral_patch(workspace, patch)
        ws = Path(workspace).resolve()
        return self.compute_code_hash(str(ws))

    def apply_ephemeral_patch(self, workspace: str, patch: PatchProposal) -> None:
        """Apply a patch to disposable scratch without a post-apply digest."""

        ws = Path(workspace).resolve()
        if not ws.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {workspace}")
        changes = patch_file_changes(patch)
        self._preflight_file_changes(ws, changes)
        for change in changes:
            self._apply_file_change(ws, change)

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
        """Copy editable files into archive/<branch_id_short>/.

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
        files = self._editable_files(ws)
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

    def compute_code_hash(self, workspace: str) -> str:
        """Compute one content digest over the editable files.

        Args:
            workspace: Absolute path to the workspace.

        Returns:
            Hex-encoded SHA-256 string.
        """
        ws = Path(workspace)
        return _hash_files(ws, self._editable_files(ws))

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

    def _editable_files(self, ws: Path) -> list[Path]:
        if self._editable_patterns is None:
            return []
        return _explicit_editable_files(
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


def _hash_files(ws: Path, files: Iterable[Path]) -> str:
    h = hashlib.sha256()
    for file_path in _dedupe_sorted_paths(files, ws):
        rel = file_path.relative_to(ws)
        h.update(rel.as_posix().encode())
        h.update(file_path.read_bytes())
    return h.hexdigest()


def _explicit_editable_files(
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
            return _allowed_editable_files(
                (target,),
                ws=ws,
                resolved_ws=resolved_ws,
                is_frozen=is_frozen,
            )
        if target.is_dir():
            return _allowed_editable_files(
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
                _allowed_editable_files(
                    match.rglob("*"),
                    ws=ws,
                    resolved_ws=resolved_ws,
                    is_frozen=is_frozen,
                )
            )
        else:
            files.extend(
                _allowed_editable_files(
                    (match,),
                    ws=ws,
                    resolved_ws=resolved_ws,
                    is_frozen=is_frozen,
                    pattern=pattern,
                )
            )
    return files


def _allowed_editable_files(
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


def _make_tree_readonly(path: Path) -> None:
    """Recursively remove write permissions from path."""
    for root, dirs, files in os.walk(path):
        for name in files + dirs:
            fp = Path(root) / name
            current = fp.stat().st_mode
            fp.chmod(current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    current = path.stat().st_mode
    path.chmod(current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _make_tree_writable(path: Path) -> None:
    """Add owner write permission so a tree can be changed or deleted."""
    for root, dirs, files in os.walk(path):
        for name in files + dirs:
            fp = Path(root) / name
            current = fp.stat().st_mode
            fp.chmod(current | stat.S_IWUSR)
    current = path.stat().st_mode
    path.chmod(current | stat.S_IWUSR)
