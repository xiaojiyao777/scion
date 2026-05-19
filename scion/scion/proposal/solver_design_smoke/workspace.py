"""Workspace materialization and patch path safety for runtime smoke."""

from __future__ import annotations

import stat
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scion.core.models import PatchFileChange, PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path

from .utils import _attr

if TYPE_CHECKING:
    from scion.proposal.tools import ProposalToolContext
else:
    ProposalToolContext = Any


def _runtime_smoke_base_workspace(context: ProposalToolContext) -> Path | None:
    champion_path = _attr(context.champion, "code_snapshot_path")
    if champion_path:
        path = Path(str(champion_path)).expanduser().resolve(strict=False)
        if path.is_dir() and (path / "solver.py").is_file():
            return path
    root_dir = _attr(context.problem_spec, "root_dir")
    if root_dir:
        path = Path(str(root_dir)).expanduser().resolve(strict=False)
        if path.is_dir() and (path / "solver.py").is_file():
            return path
    return None


def _is_solver_design_runtime_patch_path(
    path: str | None,
    *,
    provider: Any | None = None,
) -> bool:
    checker = getattr(provider, "is_runtime_patch_path", None)
    if callable(checker):
        return bool(checker(path))
    return False


def _apply_patch_to_runtime_smoke_workspace(
    workspace: Path,
    patch: PatchProposal,
) -> None:
    for change in patch_file_changes(patch):
        _apply_file_change_to_runtime_smoke_workspace(workspace, change)


def _apply_file_change_to_runtime_smoke_workspace(
    workspace: Path,
    change: PatchFileChange,
) -> None:
    rel = normalize_relative_patch_path(change.file_path)
    target = (workspace / rel).resolve(strict=False)
    target.relative_to(workspace.resolve(strict=False))
    action = str(change.action or "modify")
    if action in {"modify", "add", "create", "create_new"}:
        _ensure_runtime_smoke_path_writable(target.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        _ensure_runtime_smoke_path_writable(target)
        target.write_text(str(change.code_content or ""), encoding="utf-8")
    elif action in {"remove", "delete"}:
        if target.exists():
            _ensure_runtime_smoke_path_writable(target.parent)
            _ensure_runtime_smoke_path_writable(target)
            target.unlink()
    else:
        raise ValueError(f"unsupported patch action for smoke: {action}")


def _ensure_runtime_smoke_path_writable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return
    writable_mode = mode | stat.S_IWUSR
    if path.is_dir():
        writable_mode |= stat.S_IXUSR
    if writable_mode != mode:
        path.chmod(writable_mode)
