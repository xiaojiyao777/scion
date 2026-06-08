"""Problem-owned contract integration hook dispatch."""
from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from scion.contract.surface_access import SurfaceAccess
from scion.core.models import PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path
from scion.problem.loader import ProblemAdapterLoadError, load_problem_adapter


class ProblemIntegrationProviderError(RuntimeError):
    """Raised when a declared problem-owned contract provider cannot be loaded."""


@dataclass(frozen=True)
class ProblemIntegrationCheckRequest:
    """Inputs generic Contract may pass to a problem-owned integration check."""

    problem_spec: Any
    patch: PatchProposal
    selected_surface: str | None
    champion_file_content: Callable[[str], str | None]


def resolve_contract_check_provider(
    problem_spec: Any,
    *,
    adapter: Any = None,
) -> Any | None:
    """Return a problem-owned contract-check provider, if one is declared."""

    _validate_adapter_identity(adapter=adapter, problem_spec=problem_spec)
    direct = _provider_from_factory(adapter)
    if direct is not None:
        return direct
    direct = _provider_from_factory(problem_spec)
    if direct is not None:
        return direct

    adapter_import_path = _adapter_import_path(problem_spec)
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
    problem_id = _problem_id(problem_spec)
    if problem_id:
        allowed_prefix = f"scion.problems.{problem_id}."
    else:
        allowed_prefix = "scion.problems."
    if not module_path.startswith(allowed_prefix):
        raise ProblemIntegrationProviderError(
            "adapter module for contract check provider must live under "
            f"'{allowed_prefix}*', got '{module_path}'"
        )
    spec_v1 = _problem_spec_v1(problem_spec)
    if spec_v1 is not None:
        declared_import_path = _adapter_import_path(spec_v1)
        if declared_import_path and declared_import_path != import_path:
            raise ProblemIntegrationProviderError(
                "contract check adapter import path does not match spec_v1: "
                f"legacy '{import_path}' vs v1 '{declared_import_path}'"
            )
        try:
            return load_problem_adapter(spec_v1)
        except ProblemAdapterLoadError as exc:
            raise ProblemIntegrationProviderError(str(exc)) from exc
    if getattr(problem_spec, "requires_adapter_for_runtime", False):
        raise ProblemIntegrationProviderError(
            "contract check provider fallback for adapter-backed runtime requires "
            "a spec_v1 compatibility pointer"
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


def _adapter_import_path(problem_spec: Any) -> str:
    direct = str(getattr(problem_spec, "adapter_import_path", "") or "").strip()
    if direct:
        return direct
    adapter_ref = getattr(problem_spec, "adapter", None)
    return str(getattr(adapter_ref, "import_path", "") or "").strip()


def _problem_spec_v1(problem_spec: Any) -> Any | None:
    spec_v1 = getattr(problem_spec, "spec_v1", None)
    if spec_v1 is not None:
        return spec_v1
    adapter_ref = getattr(problem_spec, "adapter", None)
    if getattr(problem_spec, "id", None) and getattr(adapter_ref, "import_path", None):
        return problem_spec
    return None


def _problem_id(problem_spec: Any) -> str:
    spec_v1 = _problem_spec_v1(problem_spec)
    for owner in (spec_v1, problem_spec):
        value = str(
            getattr(owner, "id", None)
            or getattr(owner, "problem_id", None)
            or getattr(owner, "name", "")
            or ""
        ).strip()
        if value:
            return value
    return ""


def _validate_adapter_identity(
    *,
    adapter: Any = None,
    problem_spec: Any = None,
) -> None:
    if adapter is None or problem_spec is None:
        return
    expected_id = _problem_id(problem_spec)
    adapter_spec = getattr(adapter, "spec", None) or getattr(adapter, "_spec", None)
    adapter_id = str(getattr(adapter_spec, "id", "") or "").strip()
    if expected_id and adapter_id and adapter_id != expected_id:
        raise ProblemIntegrationProviderError(
            "loaded contract adapter id does not match problem spec: "
            f"adapter '{adapter_id}' vs spec '{expected_id}'"
        )
    expected_import_path = _adapter_import_path(problem_spec)
    adapter_import_path = _adapter_import_path(adapter_spec)
    if (
        expected_import_path
        and adapter_import_path
        and adapter_import_path != expected_import_path
    ):
        raise ProblemIntegrationProviderError(
            "loaded contract adapter import path does not match problem spec: "
            f"adapter '{adapter_import_path}' vs spec '{expected_import_path}'"
        )


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
