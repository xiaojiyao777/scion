"""Surface preview dispatch for the active CVRP solver-design package."""
from __future__ import annotations

from typing import Any, Mapping

from scion.problems.cvrp.preview.common import _policy_preview_result
from scion.problems.cvrp.preview.module_loading import _policy_preview_module
from scion.problems.cvrp.preview.paths import (
    _is_baseline_algorithm_path,
    _is_solver_design_module_path,
    _surface_name_from_policy_path,
)
from scion.problems.cvrp.preview.entrypoint import _preview_solver_entrypoint
from scion.problems.cvrp.preview.solver_design import (
    _preview_baseline_algorithm_boundary,
    _preview_solver_design_patch_api_boundary,
)


def preview_research_surface_patch(
    *,
    patch: Any,
    surface: Any | None = None,
    base_workspace: str | None = None,
) -> Mapping[str, Any]:
    """Problem-owned cheap sanity preview for solver-design patch drafts."""

    surface_name = str(getattr(surface, "name", "") or "")
    patch_path = str(getattr(patch, "file_path", ""))
    if not surface_name:
        surface_name = _surface_name_from_policy_path(patch_path)
    if surface_name != "solver_design":
        return _policy_preview_result(
            surface_name or "",
            [f"{surface_name or patch_path} is not an active CVRP research surface"],
            [],
        )

    if str(getattr(patch, "action", "modify")) == "delete":
        if _is_solver_design_module_path(patch_path):
            return _policy_preview_result(
                surface_name,
                [],
                [
                    {
                        "name": "solver_design_module_delete",
                        "passed": True,
                        "detail": "module delete deferred to workspace algorithm smoke",
                    }
                ],
            )
        return _policy_preview_result(
            surface_name,
            ["active solver_design entrypoint cannot be deleted in preview"],
            [],
        )

    issues: list[str] = []
    checks: list[dict[str, Any]] = []
    _preview_solver_design_patch_api_boundary(patch, issues, checks)
    try:
        with _policy_preview_module(
            file_path=str(getattr(patch, "file_path", "<policy>")),
            code=str(getattr(patch, "code_content", "")),
            patch=patch,
            base_workspace=base_workspace,
        ) as module:
            if _is_solver_design_module_path(
                patch_path
            ) and not _is_baseline_algorithm_path(patch_path):
                checks.append(
                    {
                        "name": "solver_design_module_import",
                        "passed": True,
                        "detail": (
                            "solver_design support module imported against the "
                            "candidate module graph; solve entrypoint validation "
                            "deferred to workspace smoke"
                        ),
                    }
                )
            elif _is_baseline_algorithm_path(patch_path):
                _preview_baseline_algorithm_boundary(
                    str(getattr(patch, "code_content", "")),
                    issues,
                    checks,
                )
                _preview_solver_entrypoint(module, issues, checks)
            else:
                issues.append(
                    "solver_design patches must target policies/baseline_algorithm.py "
                    "or policies/baseline_modules/*.py"
                )
    except Exception as exc:
        return _policy_preview_result(
            surface_name,
            [f"policy module import failed: {exc}"],
            checks,
        )
    return _policy_preview_result(surface_name, issues, checks)
