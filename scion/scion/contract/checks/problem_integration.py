"""Problem-owned contract integration hook dispatch."""
from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from scion.contract.surface_access import SurfaceAccess
from scion.core.models import PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path


class ProblemIntegrationProviderError(RuntimeError):
    """Raised when a declared problem-owned contract provider cannot be loaded."""


@dataclass(frozen=True)
class ProblemIntegrationCheckRequest:
    """Inputs generic Contract may pass to a problem-owned integration check."""

    problem_spec: Any
    patch: PatchProposal
    selected_surface: str | None
    champion_file_content: Callable[[str], str | None]


def resolve_contract_check_provider(problem_spec: Any) -> Any | None:
    """Return a problem-owned contract-check provider, if one is declared."""

    direct = _provider_from_factory(problem_spec)
    if direct is not None:
        return direct

    adapter_import_path = str(getattr(problem_spec, "adapter_import_path", "") or "")
    if not adapter_import_path:
        return None
    adapter = _instantiate_adapter(adapter_import_path, problem_spec)
    return _provider_from_factory(adapter)


def is_declared_solver_design_patch(
    problem_spec: Any,
    patch: PatchProposal,
    *,
    selected_surface: str | None,
) -> bool:
    """Return whether metadata declares this patch as a solver-design boundary."""

    access = SurfaceAccess(problem_spec)
    if _surface_name_is_solver_design(selected_surface):
        return True
    if selected_surface:
        if _surface_is_solver_design(access.surface_by_name(selected_surface)):
            return True

    for change in patch_file_changes(patch):
        try:
            file_rel = normalize_relative_patch_path(change.file_path)
        except ValueError:
            continue
        if _surface_is_solver_design(access.surface_for_patch_path(file_rel)):
            return True
    return False


def _provider_from_factory(owner: Any) -> Any | None:
    for name in (
        "contract_check_provider",
        "contract_checks_provider",
        "contract_integration_check_provider",
    ):
        factory = getattr(owner, name, None)
        if not callable(factory):
            continue
        provider = factory()
        if provider is not None:
            return provider
    return None


def _instantiate_adapter(import_path: str, problem_spec: Any) -> Any:
    if ":" not in import_path:
        raise ProblemIntegrationProviderError(
            "adapter_import_path must use 'module:Class' format for contract "
            f"check providers, got '{import_path}'"
        )
    module_path, class_name = import_path.rsplit(":", 1)
    if not module_path.startswith("scion.problems."):
        raise ProblemIntegrationProviderError(
            "adapter module for contract check provider must live under "
            f"'scion.problems.*', got '{module_path}'"
        )
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ProblemIntegrationProviderError(
            f"cannot import adapter module '{module_path}': {exc}"
        ) from exc
    cls = getattr(module, class_name, None)
    if cls is None:
        raise ProblemIntegrationProviderError(
            f"adapter module '{module_path}' has no attribute '{class_name}'"
        )
    try:
        return cls(problem_spec)
    except TypeError as exc:
        raise ProblemIntegrationProviderError(
            f"failed to instantiate adapter '{import_path}' for contract checks: {exc}"
        ) from exc


def _surface_name_is_solver_design(name: str | None) -> bool:
    return str(name or "").strip() in {"solver_design", "solver_algorithm"}


def _surface_is_solver_design(surface: Any | None) -> bool:
    if surface is None:
        return False
    name = str(getattr(surface, "name", "") or "").strip()
    kind = str(getattr(surface, "kind", "") or "").strip()
    role = str(getattr(getattr(surface, "algorithm", None), "role", "") or "").strip()
    return (
        _surface_name_is_solver_design(name)
        or kind in {"solver_design", "solver_algorithm"}
        or role in {"solver_design", "solver_algorithm", "problem_object_solver_algorithm"}
    )
