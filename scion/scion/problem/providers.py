"""Generic problem-owned provider resolution helpers.

Framework layers use these helpers to dispatch to optional problem-owned hooks
without importing a concrete problem package.
"""

from __future__ import annotations

import importlib
from typing import Any, Mapping, Protocol, Sequence


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

    def solver_design_api_manifest_files(self) -> Sequence[str]:
        """Return problem-owned files to summarize for code-stage imports."""

    def solver_design_integration_full_files(self) -> Sequence[str]:
        """Return problem-owned files to include fully for code-stage wiring."""

    def solver_design_integration_summary_files(self) -> Sequence[str]:
        """Return problem-owned sibling files to summarize for code-stage wiring."""

    def solver_design_target_api_guidance(self, target_file: str) -> str:
        """Return problem-owned target-specific code-stage API guidance."""

    def solver_design_expected_telemetry_preview(self, hypothesis: Any) -> Any:
        """Return optional problem-owned pre-code telemetry preview guidance."""


class SolverDesignSmokeProvider(Protocol):
    """Optional problem-owned solver-design smoke interpretation."""

    def is_runtime_patch_path(self, path: str | None) -> bool:
        """Return whether a patch path can be smoke-run by this provider."""

    def requires_smoke_effect_observation(self, hypothesis: Any = None) -> bool:
        """Return true when smoke must see positive effect, not just activation."""


class ActiveSolverDesignProvider(Protocol):
    """Optional problem-owned active solver-design facts for proposal tools."""

    def active_solver_algorithm_file_manifest(self, context: Any) -> Sequence[Any]:
        """Return problem-owned algorithm files and roles for active solver reads."""


class ActiveSolverMapProvider(Protocol):
    """Optional problem-owned active solver map for generic APS context tools."""

    def read_active_solver_map(
        self,
        context: Any,
        *,
        surface: str | None = None,
        subject_id: str | None = None,
    ) -> Any:
        """Return a problem-generic active solver map payload."""

    def read_operator_registry(
        self,
        context: Any,
        *,
        registry_id: str,
        surface: str | None = None,
        subject_id: str | None = None,
    ) -> Any:
        """Return a problem-generic operator registry read payload."""

    def read_algorithm_slice(
        self,
        context: Any,
        *,
        slice_id: str,
        surface: str | None = None,
        subject_id: str | None = None,
        max_chars: int | None = None,
    ) -> Any:
        """Return a bounded problem-generic algorithm slice payload."""


class ActiveSubjectPolicyProvider(Protocol):
    """Optional problem-owned active algorithm subject policy."""

    def active_subject_policy(
        self,
        context: Any = None,
        *,
        surface: str | None = None,
        subject_id: str | None = None,
    ) -> Mapping[str, Any] | None:
        """Return active subject paths, support globs, and call restrictions."""


def resolve_active_solver_map_provider(
    *,
    problem_spec: Any = None,
    adapter: Any = None,
) -> Any | None:
    """Return an optional problem-owned active solver map provider."""

    return _resolve_provider(
        problem_spec=problem_spec,
        adapter=adapter,
        factory_names=("active_solver_map_provider",),
    )


def resolve_active_subject_policy_provider(
    *,
    problem_spec: Any = None,
    adapter: Any = None,
) -> Any | None:
    """Return an optional problem-owned active subject policy provider."""

    return _resolve_provider(
        problem_spec=problem_spec,
        adapter=adapter,
        factory_names=(
            "active_subject_policy_provider",
            "contract_check_provider",
            "contract_checks_provider",
            "active_solver_map_provider",
            "active_solver_design_provider",
            "solver_design_provider",
        ),
    )


def active_subject_policy_payload(
    *,
    context: Any = None,
    problem_spec: Any = None,
    adapter: Any = None,
    surface: str | None = None,
    subject_id: str | None = None,
) -> dict[str, Any]:
    """Return a normalized active subject policy payload, or ``{}``."""

    try:
        provider = resolve_active_subject_policy_provider(
            problem_spec=problem_spec,
            adapter=adapter,
        )
    except ProblemProviderError:
        return {}
    if provider is None:
        return {}
    method = getattr(provider, "active_subject_policy", None)
    if not callable(method):
        return {}
    try:
        raw = method(context, surface=surface, subject_id=subject_id)
    except TypeError:
        raw = method(surface=surface, subject_id=subject_id)
    if not isinstance(raw, Mapping):
        return {}
    return _normalize_active_subject_policy(raw)


def active_subject_policy_matches_path(
    policy: Mapping[str, Any],
    file_path: str,
    *,
    include_entrypoints: bool = True,
    include_support: bool = True,
    include_compatibility: bool = True,
) -> bool:
    """Return whether a provider policy declares ``file_path`` active."""

    from scion.core.path_match import segment_glob_match
    from scion.core.paths import normalize_relative_patch_path

    try:
        normalized = normalize_relative_patch_path(file_path)
    except ValueError:
        normalized = str(file_path or "").replace("\\", "/").lstrip("/")
    exact_paths: set[str] = set()
    if include_entrypoints:
        exact_paths.update(_string_tuple(policy.get("entrypoint_paths")))
    if include_compatibility:
        exact_paths.update(_string_tuple(policy.get("compatibility_paths")))
    exact_paths.update(_string_tuple(policy.get("algorithm_paths")))
    if normalized in exact_paths:
        return True
    if include_support:
        for pattern in _string_tuple(policy.get("support_module_globs")):
            if segment_glob_match(normalized, pattern):
                return True
    return False


def resolve_active_solver_design_provider(
    *,
    problem_spec: Any = None,
    adapter: Any = None,
) -> Any | None:
    """Return an optional problem-owned active solver-design provider."""

    return _resolve_provider(
        problem_spec=problem_spec,
        adapter=adapter,
        factory_names=(
            "active_solver_design_provider",
            "solver_design_provider",
        ),
    )


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


def _normalize_active_subject_policy(raw: Mapping[str, Any]) -> dict[str, Any]:
    policy = dict(raw)
    aliases = {
        "entrypoints": "entrypoint_paths",
        "entrypoint_files": "entrypoint_paths",
        "support_globs": "support_module_globs",
        "support_files": "support_module_globs",
        "legacy_paths": "compatibility_paths",
    }
    for source, target in aliases.items():
        if target not in policy and source in policy:
            policy[target] = policy[source]
    normalized = {
        "surface": str(policy.get("surface") or "").strip(),
        "subject_id": str(policy.get("subject_id") or "").strip(),
        "entrypoint_paths": _string_tuple(policy.get("entrypoint_paths")),
        "algorithm_paths": _string_tuple(policy.get("algorithm_paths")),
        "support_module_globs": _string_tuple(policy.get("support_module_globs")),
        "compatibility_paths": _string_tuple(policy.get("compatibility_paths")),
        "forbidden_entrypoint_calls": tuple(
            dict(item)
            for item in policy.get("forbidden_entrypoint_calls", ()) or ()
            if isinstance(item, Mapping)
        ),
    }
    return {key: value for key, value in normalized.items() if value not in ("", ())}


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        items = (value,)
    else:
        try:
            items = tuple(value)
        except TypeError:
            items = ()
    return tuple(
        dict.fromkeys(str(item).replace("\\", "/").lstrip("/").strip() for item in items)
    )


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
    "ActiveSolverMapProvider",
    "ActiveSubjectPolicyProvider",
    "ActiveSolverDesignProvider",
    "ProblemProviderError",
    "SolverDesignPromptProvider",
    "SolverDesignSmokeProvider",
    "active_subject_policy_matches_path",
    "active_subject_policy_payload",
    "resolve_active_solver_map_provider",
    "resolve_active_subject_policy_provider",
    "resolve_active_solver_design_provider",
    "resolve_solver_design_prompt_provider",
    "resolve_solver_design_smoke_provider",
]
