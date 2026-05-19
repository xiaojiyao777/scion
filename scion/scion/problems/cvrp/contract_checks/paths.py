"""CVRP solver-design target classification helpers."""

from __future__ import annotations

from scion.core.models import PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path


def _is_cvrp_solver_design_selection(
    selected_surface: str | None,
    patch: PatchProposal,
) -> bool:
    selected = str(selected_surface or "").strip()
    if selected == "solver_design":
        return True
    for change in patch_file_changes(patch):
        try:
            file_rel = normalize_relative_patch_path(change.file_path)
        except ValueError:
            continue
        if _is_cvrp_solver_design_patch_path(file_rel):
            return True
    return False


def _is_cvrp_solver_design_patch_path(file_rel: str) -> bool:
    normalized = str(file_rel or "").replace("\\", "/").lstrip("/")
    if normalized == "policies/baseline_algorithm.py":
        return True
    return normalized.startswith("policies/baseline_modules/") and normalized.endswith(
        ".py"
    )


def _primary_patch_path(patch: PatchProposal) -> str:
    for change in patch_file_changes(patch):
        try:
            return normalize_relative_patch_path(change.file_path)
        except ValueError:
            return str(change.file_path or "")
    return ""
