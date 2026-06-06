"""WorkspaceMaterializer: create and manage branch workspaces."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Optional

from scion.core.models import (
    ChampionState,
    PatchFileChange,
    PatchProposal,
    patch_file_changes,
)
from scion.core.path_match import normalize_relative_glob_pattern, segment_glob_match
from scion.core.paths import normalize_relative_patch_path


# Frozen file patterns that can never be written via apply_patch
_DEFAULT_FROZEN_PATTERNS = frozenset(
    {
        "solver.py",
        "vns.py",
        "pool.py",
        "models.py",
        "config.py",
        "oracle.py",
        "greedy_init.py",
        "operators/base.py",
        "operators/__init__.py",
    }
)

_LEGACY_RESEARCH_SURFACE_DIRS = ("operators", "policies")
_TRANSIENT_IDENTITY_DIRS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        "__pycache__",
        "archive",
        "artifacts",
        "champions",
        "metrics",
        "staging",
        "workspaces",
    }
)


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
            _DEFAULT_FROZEN_PATTERNS if frozen_patterns is None else frozen_patterns
        )
        self._editable_patterns = _normalize_editable_patterns(editable_patterns)

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
            SHA-256 hex string of editable research-surface files after patch.

        Raises:
            FrozenFileError: If the patch targets a frozen file.
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
        """Copy editable research-surface files into archive/<branch_id_short>/.

        Called before cleanup on ABANDON so generated files are preserved for
        post-campaign analysis.  Legacy workspaces without explicit editable
        patterns still archive the historical operators/ and policies/ trees.

        Args:
            workspace: Absolute path to the branch workspace.
            branch_id: Branch ID used to name the archive sub-directory.

        Returns:
            Absolute path to the archive directory, or None if no editable
            research-surface files are present.
        """
        ws = Path(workspace)
        if self._uses_legacy_surface_dirs():
            return self._archive_legacy_surface_dirs(ws, branch_id)

        surface_files = list(self._iter_identity_files(ws))
        if not surface_files:
            return None

        archive_dest = self._next_archive_dest(branch_id)
        archive_dest.mkdir(parents=True)
        for source in surface_files:
            rel = source.relative_to(ws)
            dest = archive_dest / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)

        import logging as _logging
        _logging.getLogger(__name__).info(
            "Archived research-surface files from branch %s → %s", branch_id, archive_dest
        )
        return str(archive_dest)

    def compute_code_hash(self, workspace: str) -> str:
        """Compute SHA-256 of editable research-surface identity files.

        Args:
            workspace: Absolute path to the workspace.

        Returns:
            Hex-encoded SHA-256 string.
        """
        return self._compute_identity_hash(workspace, include_registry=False)

    def compute_snapshot_hash(self, workspace: str) -> str:
        """Compute SHA-256 of research-surface identity files + registry.yaml.

        Includes registry.yaml so weight changes affect the champion hash.

        Args:
            workspace: Absolute path to the workspace.

        Returns:
            Hex-encoded SHA-256 string.
        """
        return self._compute_identity_hash(workspace, include_registry=True)

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

    def _compute_identity_hash(self, workspace: str, *, include_registry: bool) -> str:
        ws = Path(workspace)
        h = hashlib.sha256()
        seen: set[str] = set()
        for path in self._iter_identity_files(ws):
            rel = path.relative_to(ws).as_posix()
            if rel in seen:
                continue
            _hash_file(h, rel, path)
            seen.add(rel)

        registry_path = ws / "registry.yaml"
        if include_registry and registry_path.exists() and "registry.yaml" not in seen:
            _hash_file(h, "registry.yaml", registry_path)

        return h.hexdigest()

    def _iter_identity_files(self, ws: Path) -> tuple[Path, ...]:
        if self._editable_patterns:
            return tuple(
                _iter_pattern_matched_files(ws, self._editable_patterns, self._is_frozen)
            )
        return tuple(_iter_legacy_surface_python_files(ws))

    def _uses_legacy_surface_dirs(self) -> bool:
        return not self._editable_patterns

    def _archive_legacy_surface_dirs(self, ws: Path, branch_id: str) -> str | None:
        surface_sources = [
            source
            for source in (ws / "operators", ws / "policies")
            if source.exists()
        ]
        if not surface_sources:
            return None

        archive_dest = self._next_archive_dest(branch_id)
        archive_dest.mkdir(parents=True)
        for source in surface_sources:
            shutil.copytree(
                source,
                archive_dest / source.name,
                symlinks=False,
            )
        import logging as _logging
        _logging.getLogger(__name__).info(
            "Archived research surfaces from branch %s → %s", branch_id, archive_dest
        )
        return str(archive_dest)

    def _next_archive_dest(self, branch_id: str) -> Path:
        # Use first 8 chars of branch_id for readability
        short_id = str(branch_id)[:8]
        archive_dest = self._archive_dir / short_id
        # If a prior archive exists for the same short id, append suffix
        if archive_dest.exists():
            suffix = 1
            while (self._archive_dir / f"{short_id}_{suffix}").exists():
                suffix += 1
            archive_dest = self._archive_dir / f"{short_id}_{suffix}"
        return archive_dest

    def _is_frozen(self, file_rel: str) -> bool:
        """Return True if file_rel matches any frozen pattern."""
        for pattern in self._frozen_patterns:
            normalized = str(pattern or "").replace("\\", "/").lstrip("/").strip()
            if not normalized:
                continue
            if _segment_or_basename_match(file_rel, normalized):
                return True
        return False


# ---------------------------------------------------------------------------
# Problem-spec identity helpers
# ---------------------------------------------------------------------------


def editable_identity_patterns_from_problem_spec(problem_spec: object) -> tuple[str, ...]:
    """Return declared research-surface identity patterns for a problem spec.

    v0.4 workspaces should derive code identity from explicit research-surface
    target files.  Legacy/problem specs without surfaces fall back to
    ``search_space.editable``.  The broad non-frozen-source scan is intentionally
    avoided because real problem roots contain data, evidence, split manifests,
    and test fixtures that are not candidate code identity.
    """
    surface_patterns = _research_surface_target_patterns(problem_spec)
    if surface_patterns:
        return _normalize_editable_patterns(surface_patterns)
    search_space = getattr(problem_spec, "search_space", None)
    editable = getattr(search_space, "editable", None)
    return _normalize_editable_patterns(editable or ())


def _research_surface_target_patterns(problem_spec: object) -> tuple[str, ...]:
    patterns: list[str] = []
    for surface in getattr(problem_spec, "research_surfaces", ()) or ():
        targets = getattr(surface, "targets", None)
        files = getattr(targets, "files", None) if targets is not None else None
        if not files:
            files = getattr(surface, "target_files", None)
        for item in files or ():
            text = str(item or "").strip()
            if text:
                patterns.append(text)
    return tuple(dict.fromkeys(patterns))


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _normalize_editable_patterns(patterns: Optional[Iterable[str]]) -> tuple[str, ...]:
    if patterns is None:
        return ()
    normalized: list[str] = []
    for pattern in patterns:
        normalized.append(normalize_relative_glob_pattern(str(pattern)))
    return tuple(dict.fromkeys(normalized))


def _iter_pattern_matched_files(
    ws: Path,
    patterns: tuple[str, ...],
    is_frozen: Callable[[str], bool],
) -> list[Path]:
    files: list[Path] = []
    for path in _iter_workspace_files(ws):
        rel = path.relative_to(ws).as_posix()
        if is_frozen(rel):
            continue
        if any(_editable_pattern_matches(rel, pattern) for pattern in patterns):
            files.append(path)
    return files


def _iter_legacy_surface_python_files(ws: Path) -> list[Path]:
    files: list[Path] = []
    for surface_dir_name in _LEGACY_RESEARCH_SURFACE_DIRS:
        surface_dir = ws / surface_dir_name
        if not surface_dir.exists():
            continue
        files.extend(surface_dir.rglob("*.py"))
    return sorted(files, key=lambda p: p.relative_to(ws).as_posix())


def _iter_workspace_files(ws: Path) -> list[Path]:
    if not ws.exists():
        return []
    files: list[Path] = []
    for path in ws.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ws).parts
        if any(part in _TRANSIENT_IDENTITY_DIRS for part in rel_parts):
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(ws).as_posix())


def _editable_pattern_matches(file_rel: str, pattern: str) -> bool:
    if _segment_or_basename_match(file_rel, pattern):
        return True
    # Exact directory targets in problem specs should include all files below
    # that directory, even if the author omitted a trailing /** pattern.
    if not _pattern_has_glob(pattern) and file_rel.startswith(f"{pattern.rstrip('/')}/"):
        return True
    return False


def _segment_or_basename_match(file_rel: str, pattern: str) -> bool:
    if segment_glob_match(file_rel, pattern):
        return True
    return "/" not in pattern and segment_glob_match(Path(file_rel).name, pattern)


def _pattern_has_glob(pattern: str) -> bool:
    return any(char in pattern for char in "*?[")


def _hash_file(h: "hashlib._Hash", rel: str, path: Path) -> None:
    h.update(rel.encode())
    h.update(path.read_bytes())


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


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
