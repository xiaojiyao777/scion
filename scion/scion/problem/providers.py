"""Generic problem-owned provider resolution helpers.

Framework layers use these helpers to dispatch to optional problem-owned hooks
without importing a concrete problem package.
"""

from __future__ import annotations

import importlib
from typing import Any, Mapping, Protocol, Sequence

from scion.problem.loader import ProblemAdapterLoadError, load_problem_adapter


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


class ActiveSubjectTaxonomyProvider(Protocol):
    """Optional problem-owned active subject taxonomy and telemetry policy."""

    def active_subject_taxonomy(
        self,
        context: Any = None,
        *,
        surface: str | None = None,
        subject_id: str | None = None,
    ) -> Mapping[str, Any] | None:
        """Return active subject mechanism and telemetry taxonomy."""


class ActiveSubjectCodeConstraintProvider(Protocol):
    """Optional problem-owned active subject code/API constraints."""

    def active_subject_code_constraints(
        self,
        context: Any = None,
        *,
        surface: str | None = None,
        subject_id: str | None = None,
    ) -> Mapping[str, Any] | Sequence[str] | str | None:
        """Return provider-owned code-stage object-model/API constraints."""


class ProposalMechanismEvidenceProvider(Protocol):
    """Optional problem-owned projection of measured runtime mechanism facts."""

    def summarize_proposal_mechanism_evidence(
        self,
        *,
        stage: str,
        selected_surface: str | None,
        runtime_pairs: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        """Return a compact proposal-visible evidence payload."""


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
    strict: bool = False,
) -> dict[str, Any]:
    """Return a normalized active subject policy payload, or ``{}``."""

    try:
        provider = resolve_active_subject_policy_provider(
            problem_spec=problem_spec,
            adapter=adapter,
        )
    except ProblemProviderError:
        if strict:
            raise
        return {}
    return active_subject_policy_payload_from_provider(
        provider,
        context=context,
        surface=surface,
        subject_id=subject_id,
        strict=strict,
    )


def active_subject_policy_payload_from_provider(
    provider: Any | None,
    *,
    context: Any = None,
    surface: str | None = None,
    subject_id: str | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Materialize policy from an already-resolved provider.

    Contract uses this entry point so one capability owner resolves a provider
    once and every static check consumes the same immutable policy snapshot.
    """

    if provider is None:
        if strict:
            raise ProblemProviderError("active subject policy provider unavailable")
        return {}
    method = getattr(provider, "active_subject_policy", None)
    if not callable(method):
        if strict:
            raise ProblemProviderError(
                "active subject policy provider has no active_subject_policy method"
            )
        return {}
    try:
        try:
            raw = method(context, surface=surface, subject_id=subject_id)
        except TypeError:
            raw = method(surface=surface, subject_id=subject_id)
    except Exception as exc:
        if strict:
            raise ProblemProviderError(
                f"active subject policy provider failed: {exc}"
            ) from exc
        return {}
    if not isinstance(raw, Mapping):
        if strict:
            raise ProblemProviderError(
                "active subject policy provider returned non-mapping payload"
            )
        return {}
    normalized = _normalize_active_subject_policy(raw)
    if strict and not normalized:
        raise ProblemProviderError("active subject policy provider returned empty policy")
    return normalized


def active_subject_taxonomy_payload(
    *,
    context: Any = None,
    problem_spec: Any = None,
    adapter: Any = None,
    surface: str | None = None,
    subject_id: str | None = None,
) -> dict[str, Any]:
    """Return provider-declared active subject taxonomy, or ``{}``.

    Generic proposal/runtime code consumes these declarations without knowing
    concrete research-object phase or module names.
    """

    try:
        provider = resolve_active_subject_policy_provider(
            problem_spec=problem_spec,
            adapter=adapter,
        )
    except ProblemProviderError:
        return {}
    if provider is None:
        return {}
    method = getattr(provider, "active_subject_taxonomy", None)
    if callable(method):
        try:
            raw = method(context, surface=surface, subject_id=subject_id)
        except TypeError:
            raw = method(surface=surface, subject_id=subject_id)
        if isinstance(raw, Mapping):
            normalized = _normalize_active_subject_taxonomy(raw)
            if normalized:
                return normalized
    policy_method = getattr(provider, "active_subject_policy", None)
    if callable(policy_method):
        try:
            raw_policy = policy_method(context, surface=surface, subject_id=subject_id)
        except TypeError:
            raw_policy = policy_method(surface=surface, subject_id=subject_id)
        if isinstance(raw_policy, Mapping):
            return _normalize_active_subject_taxonomy(raw_policy)
    return {}


def active_subject_code_constraints_payload(
    *,
    context: Any = None,
    problem_spec: Any = None,
    adapter: Any = None,
    surface: str | None = None,
    subject_id: str | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Return provider-declared active subject code constraints, or ``{}``.

    Generic code-generation prompts consume this as opaque provider-owned
    facts. Concrete object models and API semantics remain in problem packages.
    """

    for provider in _active_subject_code_constraint_providers(
        problem_spec=problem_spec,
        adapter=adapter,
        strict=strict,
    ):
        method = getattr(provider, "active_subject_code_constraints", None)
        if not callable(method):
            continue
        try:
            raw = method(context, surface=surface, subject_id=subject_id)
        except TypeError:
            raw = method(surface=surface, subject_id=subject_id)
        normalized = _normalize_active_subject_code_constraints(raw)
        if normalized:
            return normalized
    return {}


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


def _active_subject_code_constraint_providers(
    *,
    problem_spec: Any = None,
    adapter: Any = None,
    strict: bool = False,
) -> tuple[Any, ...]:
    providers: list[Any] = []
    seen: set[int] = set()
    factory_groups = (
        ("active_subject_code_constraints_provider",),
        ("active_subject_policy_provider",),
        ("solver_design_prompt_provider",),
        ("proposal_prompt_provider",),
        ("prompt_provider",),
        ("contract_check_provider", "contract_checks_provider"),
    )
    owners = (adapter, problem_spec)
    _validate_adapter_identity(adapter=adapter, problem_spec=problem_spec)
    for owner in owners:
        for factory_names in factory_groups:
            provider = _provider_from_factory(owner, factory_names)
            if provider is None:
                continue
            marker = id(provider)
            if marker in seen:
                continue
            seen.add(marker)
            providers.append(provider)

    adapter_import_path = _adapter_import_path(problem_spec)
    if adapter_import_path and adapter is None:
        try:
            loaded_adapter = _instantiate_adapter(adapter_import_path, problem_spec)
        except ProblemProviderError:
            if strict:
                raise
            loaded_adapter = None
        if loaded_adapter is not None:
            for factory_names in factory_groups:
                provider = _provider_from_factory(loaded_adapter, factory_names)
                if provider is None:
                    continue
                marker = id(provider)
                if marker in seen:
                    continue
                seen.add(marker)
                providers.append(provider)
    return tuple(providers)


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


def resolve_proposal_mechanism_evidence_provider(
    *,
    problem_spec: Any = None,
    adapter: Any = None,
) -> Any | None:
    """Return an optional problem-owned runtime-to-proposal evidence provider."""

    return _resolve_provider(
        problem_spec=problem_spec,
        adapter=adapter,
        factory_names=("proposal_mechanism_evidence_provider",),
    )


def typed_research_question_payload(
    *,
    problem_spec: Any = None,
    adapter: Any = None,
) -> dict[str, str]:
    """Return only the current typed problem-owned research question."""

    provider = _resolve_provider(
        problem_spec=problem_spec,
        adapter=adapter,
        factory_names=("research_guidance_provider",),
    )
    if provider is None:
        return {}
    build = getattr(provider, "build_guidance_contract", None)
    if not callable(build):
        return {}
    from scion.research_guidance import (
        GuidanceContext,
        ResearchGuidanceContract,
        validate_research_guidance_contract,
    )

    problem_family = _problem_id(problem_spec)
    if not problem_family:
        return {}
    contract = build(GuidanceContext(problem_family=problem_family))
    if not isinstance(contract, ResearchGuidanceContract):
        raise ProblemProviderError(
            "research guidance provider returned an untyped contract"
        )
    validate_research_guidance_contract(contract)
    return {
        "schema_version": "scion.typed_research_question.v1",
        "problem_family": contract.problem_family,
        "current_question": contract.current_question,
    }


def _resolve_provider(
    *,
    problem_spec: Any = None,
    adapter: Any = None,
    factory_names: Sequence[str],
) -> Any | None:
    _validate_adapter_identity(adapter=adapter, problem_spec=problem_spec)
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


def _normalize_active_subject_taxonomy(raw: Mapping[str, Any]) -> dict[str, Any]:
    aliases = {
        "broad_mechanism_families": "mechanism_broad_family_ids",
        "broad_family_ids": "mechanism_broad_family_ids",
        "generic_mechanism_families": "mechanism_broad_family_ids",
        "structural_telemetry_phases": "telemetry_identity_allowlist",
        "allowed_telemetry_phases": "telemetry_identity_allowlist",
        "telemetry_structural_refs": "telemetry_activation_refs",
        "structural_telemetry_refs": "telemetry_activation_refs",
        "generic_telemetry_activation_refs": "telemetry_activation_refs",
    }
    policy = dict(raw)
    for source, target in aliases.items():
        if target not in policy and source in policy:
            policy[target] = policy[source]
    normalized = {
        "mechanism_broad_family_ids": _string_tuple(
            policy.get("mechanism_broad_family_ids")
        ),
        "telemetry_identity_allowlist": _string_tuple(
            policy.get("telemetry_identity_allowlist")
        ),
        "telemetry_activation_refs": _string_tuple(
            policy.get("telemetry_activation_refs")
        ),
        "target_module_examples": _string_tuple(
            policy.get("target_module_examples")
        ),
    }
    return {key: value for key, value in normalized.items() if value}


def _normalize_active_subject_code_constraints(raw: Any) -> dict[str, Any]:
    if raw in (None, "", (), [], {}):
        return {}
    if isinstance(raw, str):
        constraints = _string_tuple(raw.splitlines())
        return {"constraints": constraints} if constraints else {}
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        constraints = _string_tuple(raw)
        return {"constraints": constraints} if constraints else {}
    if not isinstance(raw, Mapping):
        return {}
    payload = dict(raw)
    aliases = {
        "code_constraints": "constraints",
        "constraint_lines": "constraints",
        "rules": "constraints",
        "hints": "object_model_hints",
        "api_hints": "api_contracts",
        "object_model": "object_model_hints",
        "text": "constraints",
    }
    for source, target in aliases.items():
        if target not in payload and source in payload:
            payload[target] = payload[source]
    normalized = {
        "surface": str(payload.get("surface") or "").strip(),
        "subject_id": str(payload.get("subject_id") or "").strip(),
        "version": str(payload.get("version") or "").strip(),
        "constraints": _constraint_items(payload.get("constraints")),
        "object_model_hints": _constraint_items(payload.get("object_model_hints")),
        "api_contracts": _constraint_items(payload.get("api_contracts")),
        "forbidden_patterns": _constraint_items(payload.get("forbidden_patterns")),
    }
    return {key: value for key, value in normalized.items() if value not in ("", ())}


def _constraint_items(value: Any) -> tuple[Any, ...]:
    if value in (None, "", (), [], {}):
        return ()
    if isinstance(value, str):
        return _string_tuple(value.splitlines())
    if isinstance(value, Mapping):
        return (dict(value),)
    try:
        items = tuple(value)
    except TypeError:
        return ()
    result: list[Any] = []
    for item in items:
        if isinstance(item, Mapping):
            result.append(dict(item))
        elif str(item).strip():
            result.append(str(item).strip())
    return tuple(result)


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
    problem_id = _problem_id(problem_spec)
    if problem_id:
        allowed_prefix = f"scion.problems.{problem_id}."
    else:
        allowed_prefix = "scion.problems."
    if not module_path.startswith(allowed_prefix):
        raise ProblemProviderError(
            f"problem provider adapter module must live under '{allowed_prefix}*', "
            f"got '{module_path}'"
        )
    spec_v1 = _problem_spec_v1(problem_spec)
    if spec_v1 is not None:
        declared_import_path = _adapter_import_path(spec_v1)
        if declared_import_path and declared_import_path != import_path:
            raise ProblemProviderError(
                "problem provider adapter import path does not match spec_v1: "
                f"legacy '{import_path}' vs v1 '{declared_import_path}'"
            )
        try:
            return load_problem_adapter(spec_v1)
        except ProblemAdapterLoadError as exc:
            raise ProblemProviderError(str(exc)) from exc
    if getattr(problem_spec, "requires_adapter_for_runtime", False):
        raise ProblemProviderError(
            "problem provider fallback for adapter-backed runtime requires a "
            "spec_v1 compatibility pointer"
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
        raise ProblemProviderError(
            "loaded problem adapter id does not match problem spec: "
            f"adapter '{adapter_id}' vs spec '{expected_id}'"
        )


__all__ = [
    "ActiveSubjectCodeConstraintProvider",
    "ActiveSubjectPolicyProvider",
    "ActiveSubjectTaxonomyProvider",
    "ProblemProviderError",
    "ProposalMechanismEvidenceProvider",
    "SolverDesignPromptProvider",
    "active_subject_policy_matches_path",
    "active_subject_code_constraints_payload",
    "active_subject_policy_payload",
    "active_subject_taxonomy_payload",
    "resolve_active_subject_policy_provider",
    "resolve_proposal_mechanism_evidence_provider",
    "resolve_solver_design_prompt_provider",
    "typed_research_question_payload",
]
