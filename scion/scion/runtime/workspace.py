"""WorkspaceMaterializer: create and manage branch workspaces."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path
from typing import Optional

from scion.core.models import ChampionState, PatchProposal


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
    ) -> None:
        self._campaign_dir = Path(campaign_dir)
        self._workspaces_dir = self._campaign_dir / "workspaces"
        self._champions_dir = self._campaign_dir / "champions"
        self._frozen_patterns = frozen_patterns or _DEFAULT_FROZEN_PATTERNS

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
            SHA-256 hex string of operators/ directory after patch.

        Raises:
            FrozenFileError: If the patch targets a frozen file.
            ValueError: If patch.action is 'delete' (not yet supported here).
        """
        ws = Path(workspace)

        # Second-level frozen-file check (Contract Gate is the first)
        file_rel = patch.file_path.lstrip("/")
        if self._is_frozen(file_rel):
            raise FrozenFileError(
                f"apply_patch refused: '{patch.file_path}' matches frozen patterns"
            )

        target = ws / file_rel

        if patch.action == "delete":
            if target.exists():
                target.unlink()
        else:
            # "modify" or "create"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(patch.code_content, encoding="utf-8")

        # For new operator files, register them in registry.yaml so the solver picks them up
        if (
            patch.action == "create"
            and file_rel.startswith("operators/")
            and file_rel.endswith(".py")
        ):
            _update_registry(ws, file_rel, patch.code_content)

        return self.compute_code_hash(workspace)

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

    def archive_workspace(self, workspace: str, branch_id: str) -> None:
        """Copy the operators/ directory from workspace into archive/<branch_id_short>/.

        Called before cleanup on ABANDON so generated .py files are preserved
        for post-campaign analysis.

        Args:
            workspace: Absolute path to the branch workspace.
            branch_id: Branch ID used to name the archive sub-directory.
        """
        ws = Path(workspace)
        ops_src = ws / "operators"
        if not ops_src.exists():
            return

        # Use first 8 chars of branch_id for readability
        short_id = str(branch_id)[:8]
        archive_dest = self._archive_dir / short_id
        # If a prior archive exists for the same short id, append suffix
        if archive_dest.exists():
            suffix = 1
            while (self._archive_dir / f"{short_id}_{suffix}").exists():
                suffix += 1
            archive_dest = self._archive_dir / f"{short_id}_{suffix}"

        shutil.copytree(ops_src, archive_dest, symlinks=False)
        import logging as _logging
        _logging.getLogger(__name__).info(
            "Archived operators from branch %s → %s", branch_id, archive_dest
        )

    def compute_code_hash(self, workspace: str) -> str:
        """Compute SHA-256 of operators/ .py files (sorted by relative path).

        Args:
            workspace: Absolute path to the workspace.

        Returns:
            Hex-encoded SHA-256 string.
        """
        ops_dir = Path(workspace) / "operators"
        h = hashlib.sha256()

        if ops_dir.exists():
            py_files = sorted(ops_dir.rglob("*.py"), key=lambda p: str(p.relative_to(ops_dir)))
            for py_file in py_files:
                h.update(str(py_file.relative_to(ops_dir)).encode())
                h.update(py_file.read_bytes())

        return h.hexdigest()

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


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


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
