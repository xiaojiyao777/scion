"""Generic problem-owned provider resolution helpers.

Framework layers use these helpers to dispatch to optional problem-owned hooks
without importing a concrete problem package.
"""

from __future__ import annotations

import importlib
from typing import Any, Protocol, Sequence


class ProblemProviderError(RuntimeError):
    """Raised when a declared problem provider cannot be loaded."""


class SolverDesignPromptProvider(Protocol):
    """Optional problem-owned solver-design prompt guidance."""

    def solver_design_hypothesis_guidance(self, context: Any) -> Sequence[str]:
        """Return problem-specific hypothesis-stage guidance lines."""

    def solver_design_code_rules(self, context: Any) -> Sequence[str]:
        """Return problem-specific code-stage system guidance lines."""

    def solver_design_scope_guidance(
        self,
        context: Any,
        *,
        mode: str,
        broad_terms: Sequence[str],
    ) -> Sequence[str]:
        """Return problem-specific compact-scope guidance lines."""

    def solver_design_user_constraints(self, context: Any) -> Sequence[str]:
        """Return problem-specific code-stage user constraints."""

    def solver_design_broad_scope_terms(self) -> Sequence[str]:
        """Return problem-specific terms that imply a broad implementation."""


class SolverDesignSmokeProvider(Protocol):
    """Optional problem-owned solver-design smoke interpretation."""

    def is_runtime_patch_path(self, path: str | None) -> bool:
        """Return whether a patch path can be smoke-run by this provider."""


def resolve_solver_design_prompt_provider(
    *,
    problem_spec: Any = None,
    adapter: Any = None,
) -> Any | None:
    """Return an optional problem-owned solver-design prompt provider."""

    return _resolve_provider(
        problem_spec=problem_spec,
        adapter=adapter,
        factory_names=(
            "solver_design_prompt_provider",
            "proposal_prompt_provider",
            "prompt_provider",
        ),
    )


def resolve_solver_design_smoke_provider(
    *,
    problem_spec: Any = None,
    adapter: Any = None,
) -> Any | None:
    """Return an optional problem-owned solver-design smoke provider."""

    return _resolve_provider(
        problem_spec=problem_spec,
        adapter=adapter,
        factory_names=(
            "solver_design_smoke_provider",
            "algorithm_smoke_provider",
            "smoke_provider",
        ),
    )


def _resolve_provider(
    *,
    problem_spec: Any = None,
    adapter: Any = None,
    factory_names: Sequence[str],
) -> Any | None:
    direct = _provider_from_factory(adapter, factory_names)
    if direct is not None:
        return direct
    direct = _provider_from_factory(problem_spec, factory_names)
    if direct is not None:
        return direct

    adapter_import_path = _adapter_import_path(problem_spec)
    if not adapter_import_path:
        return None
    loaded_adapter = _instantiate_adapter(adapter_import_path, problem_spec)
    return _provider_from_factory(loaded_adapter, factory_names)


def _provider_from_factory(owner: Any, factory_names: Sequence[str]) -> Any | None:
    if owner is None:
        return None
    for name in factory_names:
        factory = getattr(owner, name, None)
        if not callable(factory):
            continue
        provider = factory()
        if provider is not None:
            return provider
    return None


def _adapter_import_path(problem_spec: Any) -> str:
    direct = str(getattr(problem_spec, "adapter_import_path", "") or "").strip()
    if direct:
        return direct
    adapter_ref = getattr(problem_spec, "adapter", None)
    return str(getattr(adapter_ref, "import_path", "") or "").strip()


def _instantiate_adapter(import_path: str, problem_spec: Any) -> Any:
    if ":" not in import_path:
        raise ProblemProviderError(
            "adapter import path must use 'module:Class' format for problem "
            f"providers, got '{import_path}'"
        )
    module_path, class_name = import_path.rsplit(":", 1)
    if not module_path.startswith("scion.problems."):
        raise ProblemProviderError(
            "problem provider adapter module must live under 'scion.problems.*', "
            f"got '{module_path}'"
        )
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ProblemProviderError(
            f"cannot import adapter module '{module_path}': {exc}"
        ) from exc
    cls = getattr(module, class_name, None)
    if cls is None:
        raise ProblemProviderError(
            f"adapter module '{module_path}' has no attribute '{class_name}'"
        )
    try:
        return cls(problem_spec)
    except TypeError as exc:
        raise ProblemProviderError(
            f"failed to instantiate adapter '{import_path}' for providers: {exc}"
        ) from exc


__all__ = [
    "ProblemProviderError",
    "SolverDesignPromptProvider",
    "SolverDesignSmokeProvider",
    "resolve_solver_design_prompt_provider",
    "resolve_solver_design_smoke_provider",
]
