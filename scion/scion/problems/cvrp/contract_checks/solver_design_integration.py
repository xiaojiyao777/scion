"""CVRP-owned C9e solver-design integration check."""

from __future__ import annotations

import ast
from collections.abc import Callable

from scion.core.models import PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path
from scion.problems.cvrp.contract_checks.api_contracts import (
    _additional_wiring_edit_error,
    _scheduler_additional_solve_structure_error,
)
from scion.problems.cvrp.contract_checks.imports import (
    _solver_design_import_export_error,
)
from scion.problems.cvrp.contract_checks.paths import (
    _is_cvrp_solver_design_patch_path,
    _is_cvrp_solver_design_selection,
    _primary_patch_path,
)
from scion.problems.cvrp.contract_checks.reachability import ReachabilityState
from scion.problems.cvrp.contract_checks.result import SolverDesignIntegrationResult
from scion.problems.cvrp.contract_checks.state_bridge import (
    _state_model_bridge_api_error,
)


class CvrpContractCheckProvider:
    """CVRP problem-owned contract integration checks."""

    def check_solver_design_integration(
        self,
        request,
    ) -> SolverDesignIntegrationResult:
        return check_solver_design_integration(
            request.patch,
            selected_surface=request.selected_surface,
            selected_surface_is_solver_design=_is_cvrp_solver_design_selection,
            is_solver_design_patch_path=_is_cvrp_solver_design_patch_path,
            champion_file_content=request.champion_file_content,
        )


def check_solver_design_integration(
    patch: PatchProposal,
    *,
    selected_surface: str | None,
    selected_surface_is_solver_design: Callable[[str | None, PatchProposal], bool],
    is_solver_design_patch_path: Callable[[str], bool],
    champion_file_content: Callable[[str], str | None],
) -> SolverDesignIntegrationResult:
    if not selected_surface_is_solver_design(selected_surface, patch):
        return SolverDesignIntegrationResult(True, "not a solver_design patch")

    reachability = ReachabilityState()
    candidate_sources: dict[str, str] = {}
    primary_path = _primary_patch_path(patch)

    for change in patch_file_changes(patch):
        if change.action == "delete":
            continue
        try:
            file_rel = normalize_relative_patch_path(change.file_path)
        except ValueError as exc:
            return SolverDesignIntegrationResult(False, str(exc))
        if not is_solver_design_patch_path(file_rel):
            continue
        candidate_sources[file_rel] = change.code_content
        champion_code = champion_file_content(file_rel)
        wiring_error = _additional_wiring_edit_error(
            file_rel=file_rel,
            primary_path=primary_path,
            champion_code=champion_code,
            candidate_code=change.code_content,
        )
        if wiring_error is not None:
            return SolverDesignIntegrationResult(False, wiring_error)
        try:
            tree = ast.parse(change.code_content)
        except SyntaxError:
            return SolverDesignIntegrationResult(False, "unparseable code")
        state_model_error = _state_model_bridge_api_error(
            file_rel=file_rel,
            tree=tree,
        )
        if state_model_error is not None:
            return SolverDesignIntegrationResult(False, state_model_error)
        reachability.record_file(file_rel, tree, champion_code)

    import_error = _solver_design_import_export_error(
        candidate_sources,
        champion_file_content=champion_file_content,
        primary_path=primary_path,
    )
    if import_error is not None:
        return SolverDesignIntegrationResult(False, import_error)

    solve_structure_error = _scheduler_additional_solve_structure_error(
        candidate_sources,
        champion_file_content=champion_file_content,
        primary_path=primary_path,
    )
    if solve_structure_error is not None:
        return SolverDesignIntegrationResult(False, solve_structure_error)

    no_helper_detail = reachability.no_helper_detail()
    if no_helper_detail is not None:
        return SolverDesignIntegrationResult(True, no_helper_detail)

    inert_detail = reachability.inert_helper_detail()
    if inert_detail is not None:
        return SolverDesignIntegrationResult(False, inert_detail)

    return SolverDesignIntegrationResult(
        True,
        "new solver_design helper functions are integrated",
    )
