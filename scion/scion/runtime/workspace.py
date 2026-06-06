"""WorkspaceMaterializer: create and manage branch workspaces."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
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
from scion.core.research_surface_index import normalize_editable_identity_patterns


# Generic runtime has no problem-specific frozen files by default.
_DEFAULT_FROZEN_PATTERNS = frozenset()


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
        self._champions_dir = self._campaign_dir / "champions"
        self._frozen_patterns = (
            _DEFAULT_FROZEN_PATTERNS
            if frozen_patterns is None
            else frozen_patterns
        )
        self._editable_patterns = (
            None
            if editable_patterns is None
            else normalize_editable_identity_patterns(editable_patterns)
        )

        self._workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._champions_dir.mkdir(parents=True, exist_ok=True)
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

    def apply_patch(self, workspace: str, patch: PatchProposal) -> str:
        """Write patch content into the workspace, return updated code hash.

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

        for change in patch_file_changes(patch):
            self._apply_file_change(ws, change)

        return self.compute_code_hash(workspace)

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

    def compute_code_hash(self, workspace: str) -> str:
        """Compute SHA-256 of editable identity files.

        Args:
            workspace: Absolute path to the workspace.

        Returns:
            Hex-encoded SHA-256 string.
        """
        ws = Path(workspace)
        return _hash_files(ws, self._identity_files(ws))

    def compute_snapshot_hash(self, workspace: str) -> str:
        """Compute SHA-256 of editable identity files + registry.yaml.

        Includes registry.yaml so weight changes affect the champion hash.

        Args:
            workspace: Absolute path to the workspace.

        Returns:
            Hex-encoded SHA-256 string.
        """
        ws = Path(workspace)
        files = self._identity_files(ws)

        registry_path = ws / "registry.yaml"
        if registry_path.exists():
            files = _dedupe_sorted_paths([*files, registry_path], ws)

        return _hash_files(ws, files)

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


def _hash_files(ws: Path, files: Iterable[Path]) -> str:
    h = hashlib.sha256()
    for file_path in _dedupe_sorted_paths(files, ws):
        rel = file_path.relative_to(ws)
        h.update(rel.as_posix().encode())
        h.update(file_path.read_bytes())
    return h.hexdigest()


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
