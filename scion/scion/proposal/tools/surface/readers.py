"""Guarded code-file readers for surface tools."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import Any

from scion.core.models import ChampionState
from scion.proposal.tools.models import ProposalToolContext
from scion.proposal.tools.utils import _limit_text, _normalize_rel_path


def _read_champion_file(
    champion: ChampionState,
    target_file: str,
    *,
    max_chars: int,
) -> dict[str, Any]:
    return _read_code_file_from_root(
        champion.code_snapshot_path,
        target_file,
        max_chars=max_chars,
        source_kind="champion_snapshot",
    )
def _surface_code_read_root(context: ProposalToolContext) -> tuple[str | Path, str]:
    branch_workspace = str(context.branch_workspace or "").strip()
    if branch_workspace and os.path.isdir(branch_workspace):
        return branch_workspace, "branch_workspace"
    if context.champion is None:
        return "", "missing_snapshot"
    return context.champion.code_snapshot_path, "champion_snapshot"
def _read_code_file_from_root(
    root_path: str | Path,
    target_file: str,
    *,
    max_chars: int,
    source_kind: str,
) -> dict[str, Any]:
    normalized = _normalize_rel_path(target_file)
    if normalized is None:
        return {
            "file_path": target_file,
            "readable": False,
            "reason": "unsafe_relative_path",
            "source": source_kind,
        }
    if not root_path:
        return {
            "file_path": normalized,
            "readable": False,
            "reason": "not_found",
            "source": source_kind,
        }
    root = Path(root_path).expanduser().resolve()
    unresolved_path = root / normalized
    if _path_has_symlink_component(root, normalized):
        return {
            "file_path": normalized,
            "readable": False,
            "reason": "symlink_not_allowed",
            "source": source_kind,
        }
    path = unresolved_path.resolve()
    if path != root and root not in path.parents:
        return {
            "file_path": normalized,
            "readable": False,
            "reason": "path_escapes_snapshot",
            "source": source_kind,
        }
    if not path.is_file():
        return {
            "file_path": normalized,
            "readable": False,
            "reason": "not_found",
            "source": source_kind,
        }
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "file_path": normalized,
            "readable": False,
            "reason": f"unreadable:{exc}",
            "source": source_kind,
        }
    return {
        "file_path": normalized,
        "readable": True,
        "source": source_kind,
        "content_preview": _limit_text(content, max_chars),
        "truncated": len(content) > max_chars,
        "size_chars": len(content),
        "max_chars": max_chars,
    }
def _path_has_symlink_component(root: Path, normalized_rel_path: str) -> bool:
    current = root
    for part in PurePosixPath(normalized_rel_path).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False

__all__ = [
    "_read_champion_file",
    "_surface_code_read_root",
    "_read_code_file_from_root",
    "_path_has_symlink_component",
]
