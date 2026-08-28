# ruff: noqa: I001
from __future__ import annotations

import sys
import weakref
from collections.abc import Callable
from dataclasses import dataclass, fields
from types import FunctionType, MappingProxyType, MethodType, ModuleType
from typing import Any, cast

import scion.core.initial_screening_research_context_capsule as capsule_module


def _source_bindings(module: Any, expected_name: str, names: Any) -> tuple[Any, ...]:
    if (
        type(module) is not ModuleType
        or type(expected_name) is not str
        or type(names) is not tuple
        or any(type(name) is not str for name in names)
    ):
        raise TypeError
    storage = vars(module)
    if (
        type(storage) is not dict
        or any(type(name) is not str for name in storage)
        or type(storage.get("__name__")) is not str
        or storage["__name__"] != expected_name
        or any(name not in storage for name in names)
    ):
        raise TypeError
    return tuple(storage[name] for name in names)


(
    _InitialScreeningResearchContextCapsule,
    _InitialScreeningResearchContextInputs,
    _InitialScreeningResearchContextPublication,
) = _source_bindings(
    capsule_module,
    "scion.core.initial_screening_research_context_capsule",
    (
        "_InitialScreeningResearchContextCapsule",
        "_InitialScreeningResearchContextInputs",
        "_InitialScreeningResearchContextPublication",
    ),
)

import scion.core.initial_screening_problem_spec_anchors as problem_anchors_module
import scion.core.initial_screening_research_context as research_context_boundary_module
from scion.core import (
    initial_screening_research_context_capsule_runtime as capsule_runtime_module,
)
import scion.core.initial_screening_research_context_integration as integration_module
import scion.core.initial_screening_research_context_io as research_context_io_module
import scion.core.initial_screening_study_controls as controls_boundary_module
import scion.core.initial_screening_study_controls_io as controls_io_module
from scion.core import (
    initial_screening_study_controls_run_validation as run_validation_module,
)
import scion.core.initial_screening_study_controls_shapes as controls_shapes_module
import scion.core.problem_runtime as problem_runtime_module
import scion.core.proposal_pipeline as proposal_pipeline_module
import scion.proposal.context_manager as context_manager_module


(_CONSUMER_DESCRIPTOR_ANCHORS, _CONSUMER_METHOD_ANCHORS) = _source_bindings(
    problem_anchors_module,
    "scion.core.initial_screening_problem_spec_anchors",
    ("_CONSUMER_DESCRIPTOR_ANCHORS", "_CONSUMER_METHOD_ANCHORS"),
)
(_ERROR, _FILENAME, _MAX_BYTES, _InitialScreeningResearchContextError) = (
    _source_bindings(
        research_context_boundary_module,
        "scion.core.initial_screening_research_context",
        ("_ERROR", "_FILENAME", "_MAX_BYTES", "_InitialScreeningResearchContextError"),
    )
)
(
    _published_research_context_inputs_key,
    _research_context_capsule_h_fields,
    _research_context_capsule_pristine_key,
    _validate_capsule_runtime_dependencies,
) = _source_bindings(
    capsule_runtime_module,
    "scion.core.initial_screening_research_context_capsule_runtime",
    (
        "_published_research_context_inputs_key",
        "_research_context_capsule_h_fields",
        "_research_context_capsule_pristine_key",
        "_validate_capsule_runtime_dependencies",
    ),
)
(_validate_fourth_control_publication,) = _source_bindings(
    research_context_io_module,
    "scion.core.initial_screening_research_context_io",
    ("_validate_fourth_control_publication",),
)
(_InitialScreeningRuntimeInputs,) = _source_bindings(
    controls_boundary_module,
    "scion.core.initial_screening_study_controls",
    ("_InitialScreeningRuntimeInputs",),
)
(_ControlsPublication,) = _source_bindings(
    controls_io_module,
    "scion.core.initial_screening_study_controls_io",
    ("_ControlsPublication",),
)
(_register_research_context_run_authority,) = _source_bindings(
    run_validation_module,
    "scion.core.initial_screening_study_controls_run_validation",
    ("_register_research_context_run_authority",),
)
(
    _make_research_validation_builtin_guard,
    _anchor_items,
    _same_anchor_items,
    _same_key,
    _class_surface,
    _is_exact_empty_tuple,
    _int_tuple,
    _directory_fingerprints,
) = _source_bindings(
    controls_shapes_module,
    "scion.core.initial_screening_study_controls_shapes",
    (
        "_make_research_validation_builtin_guard",
        "_research_validation_anchor_items",
        "_same_research_validation_anchor_items",
        "_same_research_validation_key",
        "_research_validation_class_surface",
        "_research_validation_is_empty_tuple",
        "_research_validation_int_tuple",
        "_research_validation_directory_fingerprints",
    ),
)
(_MATERIALIZE_H_FIELDS,) = _source_bindings(
    integration_module,
    "scion.core.initial_screening_research_context_integration",
    ("_materialize_research_context_h_fields",),
)
(_install_validation_authority,) = _source_bindings(
    sys.modules["scion.core.initial_screening_research_context_edges"],
    "scion.core.initial_screening_research_context_edges",
    ("_install_validation_authority",),
)
(ProblemRuntime,) = _source_bindings(
    problem_runtime_module,
    "scion.core.problem_runtime",
    ("ProblemRuntime",),
)
(ProposalPipeline,) = _source_bindings(
    proposal_pipeline_module,
    "scion.core.proposal_pipeline",
    ("ProposalPipeline",),
)
(ContextManager,) = _source_bindings(
    context_manager_module,
    "scion.proposal.context_manager",
    ("ContextManager",),
)


def _make_local_helper_anchor_guard() -> tuple[
    Callable[[Any], None], Callable[[Any], None]
]:
    anchors: tuple[tuple[str, Any], ...] | None = None

    def install(items: Any) -> None:
        nonlocal anchors
        if (
            anchors is not None
            or type(items) is not tuple
            or any(
                type(item) is not tuple or len(item) != 2 or type(item[0]) is not str
                for item in items
            )
        ):
            raise TypeError
        anchors = items

    def validate(storage: Any) -> None:
        current = anchors
        if (
            type(storage) is not dict
            or any(type(name) is not str for name in storage)
            or type(current) is not tuple
            or any(storage.get(name) is not value for name, value in current)
        ):
            raise TypeError

    return install, validate


_install_local_helper_anchors, _validate_local_helper_anchors = (
    _make_local_helper_anchor_guard()
)
del _make_local_helper_anchor_guard
_RESEARCH_CONTEXT_ERROR = _InitialScreeningResearchContextError
_CAPSULE_ATTRIBUTE = "_initial_screening_research_context_capsule"
_ACTIVE_ATTRIBUTE = "_initial_screening_research_context_active"
_INPUTS_ATTRIBUTE = "_initial_screening_research_context"
_PROBLEM_RUNTIME_KEYS = frozenset(
    {
        "_spec",
        "_adapter",
        "_split_manifest",
        "_seed_ledger",
        "_research_input",
        "_research_history",
        "_development_suites",
        "_ctx_manager",
        _CAPSULE_ATTRIBUTE,
    }
)
_CONTEXT_MANAGER_KEYS = frozenset(
    {
        "_adapter",
        "_research_input",
        "_prior_research_observations",
        "_research_history",
        _CAPSULE_ATTRIBUTE,
    }
)
_PROPOSAL_PIPELINE_KEYS = frozenset(
    {
        "creative",
        "problem_runtime",
        "branch_workspaces",
        "champion_lock",
        "get_champion",
        "step_history",
        "mark_balance_exhausted",
        "code_research_limits",
        "code_development_evaluator",
        "record_hypothesis_candidate_completed",
        "record_hypothesis_candidate_selected",
        "_hypothesis_rejection_counts",
        "_last_hypothesis_rejection_reason",
    }
)
_PROBLEM_RUNTIME_METHODS = (
    "build_hypothesis_context",
    "build_code_context",
    "hypothesis_research_public_sources",
    "hypothesis_research_source_prefixes",
)
_CONTEXT_MANAGER_METHODS = ("build_hypothesis_context", "build_code_context")
_PROPOSAL_PIPELINE_METHODS = ("generate_hypothesis", "generate_code")
_METHOD_ANCHOR_ITEMS = _anchor_items(_CONSUMER_METHOD_ANCHORS)
_DESCRIPTOR_ANCHOR_ITEMS = _anchor_items(_CONSUMER_DESCRIPTOR_ANCHORS)
if (
    type(sys.modules) is not dict
    or any(type(name) is not str for name in sys.modules)
    or type(__name__) is not str
):
    raise TypeError
_SELF_MODULE = cast(ModuleType, sys.modules.get(__name__))
_SELF_MODULE_NAME = "scion.core.initial_screening_research_context_validation"
_source_bindings(_SELF_MODULE, _SELF_MODULE_NAME, ())
_source_bindings(sys, "sys", ())
_validate_validation_builtin_guard = _make_research_validation_builtin_guard(
    _SELF_MODULE, sys, sys.modules
)
del _make_research_validation_builtin_guard


@dataclass(frozen=True, repr=False)
class _RegisteredResearchContextBaseline:
    inputs_ref: weakref.ReferenceType[Any]
    capsule_ref: weakref.ReferenceType[Any]
    problem_runtime_ref: weakref.ReferenceType[Any]
    context_manager_ref: weakref.ReferenceType[Any]
    proposal_pipeline_ref: weakref.ReferenceType[Any]
    inputs_key: tuple[Any, ...]
    capsule_key: tuple[Any, ...]
    payload_bytes: bytes
    campaign_dir: str
    directory_fingerprints: tuple[tuple[int, int], ...]
    leaf_fingerprint: tuple[int, int, int, int]

    def __repr__(self) -> str:
        return "_RegisteredResearchContextBaseline(<redacted>)"


@dataclass(frozen=True, repr=False)
class _ResearchContextRunState:
    inputs: Any
    baseline: _RegisteredResearchContextBaseline

    def __repr__(self) -> str:
        return "_ResearchContextRunState(<redacted>)"


_REGISTERED_OWNERS: Any = weakref.WeakKeyDictionary()
_VALIDATION_CLASS_SURFACES = tuple(
    _class_surface(value)
    for value in (_RegisteredResearchContextBaseline, _ResearchContextRunState)
)
_VALIDATION_ALIASES = (
    ("sys", sys),
    ("weakref", weakref),
    ("MappingProxyType", MappingProxyType),
    ("FunctionType", FunctionType),
    ("MethodType", MethodType),
    ("ModuleType", ModuleType),
    ("_ERROR", _ERROR),
    ("_FILENAME", _FILENAME),
    ("_MAX_BYTES", _MAX_BYTES),
    ("_RESEARCH_CONTEXT_ERROR", _RESEARCH_CONTEXT_ERROR),
    ("_CAPSULE_ATTRIBUTE", _CAPSULE_ATTRIBUTE),
    ("_ACTIVE_ATTRIBUTE", _ACTIVE_ATTRIBUTE),
    ("_INPUTS_ATTRIBUTE", _INPUTS_ATTRIBUTE),
    ("_PROBLEM_RUNTIME_KEYS", _PROBLEM_RUNTIME_KEYS),
    ("_CONTEXT_MANAGER_KEYS", _CONTEXT_MANAGER_KEYS),
    ("_PROPOSAL_PIPELINE_KEYS", _PROPOSAL_PIPELINE_KEYS),
    ("_PROBLEM_RUNTIME_METHODS", _PROBLEM_RUNTIME_METHODS),
    ("_CONTEXT_MANAGER_METHODS", _CONTEXT_MANAGER_METHODS),
    ("_PROPOSAL_PIPELINE_METHODS", _PROPOSAL_PIPELINE_METHODS),
    ("_validate_validation_builtin_guard", _validate_validation_builtin_guard),
    ("_REGISTERED_OWNERS", _REGISTERED_OWNERS),
    ("_MATERIALIZE_H_FIELDS", _MATERIALIZE_H_FIELDS),
    ("_validate_local_helper_anchors", _validate_local_helper_anchors),
    ("problem_anchors_module", problem_anchors_module),
    ("research_context_boundary_module", research_context_boundary_module),
    ("capsule_module", capsule_module),
    ("capsule_runtime_module", capsule_runtime_module),
    ("integration_module", integration_module),
    ("_CONSUMER_METHOD_ANCHORS", _CONSUMER_METHOD_ANCHORS),
    ("_CONSUMER_DESCRIPTOR_ANCHORS", _CONSUMER_DESCRIPTOR_ANCHORS),
    (
        "_InitialScreeningResearchContextCapsule",
        _InitialScreeningResearchContextCapsule,
    ),
    ("_InitialScreeningResearchContextInputs", _InitialScreeningResearchContextInputs),
    (
        "_InitialScreeningResearchContextPublication",
        _InitialScreeningResearchContextPublication,
    ),
    ("_published_research_context_inputs_key", _published_research_context_inputs_key),
    ("_research_context_capsule_pristine_key", _research_context_capsule_pristine_key),
    ("_research_context_capsule_h_fields", _research_context_capsule_h_fields),
    ("_validate_capsule_runtime_dependencies", _validate_capsule_runtime_dependencies),
    ("_validate_fourth_control_publication", _validate_fourth_control_publication),
    (
        "_register_research_context_run_authority",
        _register_research_context_run_authority,
    ),
    ("_InitialScreeningRuntimeInputs", _InitialScreeningRuntimeInputs),
    ("_ControlsPublication", _ControlsPublication),
    ("ProblemRuntime", ProblemRuntime),
    ("ProposalPipeline", ProposalPipeline),
    ("ContextManager", ContextManager),
)


def _validate_validation_dependencies(
    aliases: tuple[tuple[str, Any], ...] = _VALIDATION_ALIASES,
    class_surfaces: tuple[tuple[Any, ...], ...] = _VALIDATION_CLASS_SURFACES,
    method_items: tuple[tuple[Any, Any], ...] = _METHOD_ANCHOR_ITEMS,
    descriptor_items: tuple[tuple[Any, Any], ...] = _DESCRIPTOR_ANCHOR_ITEMS,
    runtime_validator: Any = _validate_capsule_runtime_dependencies,
    self_module: ModuleType = _SELF_MODULE,
    self_name: str = _SELF_MODULE_NAME,
    sys_module: ModuleType = sys,
    sys_name: str = "sys",
    sys_modules: dict[str, Any] = sys.modules,
    capsule_source: ModuleType = capsule_module,
    capsule_name: str = "scion.core.initial_screening_research_context_capsule",
    runtime_module: ModuleType = capsule_runtime_module,
    runtime_name: str = capsule_runtime_module.__name__,
    integration: ModuleType = integration_module,
    integration_name: str = "scion.core.initial_screening_research_context_integration",
    anchors_module: ModuleType = problem_anchors_module,
    anchors_name: str = "scion.core.initial_screening_problem_spec_anchors",
    local_helper_validator: Callable[[Any], None] = _validate_local_helper_anchors,
    same_anchor_items: Callable[[Any, Any], bool] = _same_anchor_items,
    builtin_guard: Callable[[], None] = _validate_validation_builtin_guard,
) -> None:
    builtin_guard()
    modules = (
        self_module,
        sys_module,
        capsule_source,
        runtime_module,
        integration,
        anchors_module,
    )
    if any(type(module) is not ModuleType for module in modules):
        raise TypeError
    module_storages = tuple(vars(module) for module in modules)
    if any(
        type(storage) is not dict or any(type(name) is not str for name in storage)
        for storage in module_storages
    ):
        raise TypeError
    (
        self_storage,
        sys_storage,
        capsule_storage,
        runtime_storage,
        integration_storage,
        anchors_storage,
    ) = module_storages
    names = (
        self_name,
        sys_name,
        capsule_name,
        runtime_name,
        integration_name,
        anchors_name,
    )
    if (
        type(sys_modules) is not dict
        or any(type(name) is not str for name in sys_modules)
        or sys_storage.get("modules") is not sys_modules
        or any(type(name) is not str for name in names)
        or any(
            sys_modules.get(name) is not module for name, module in zip(names, modules)
        )
        or any(type(storage.get("__name__")) is not str for storage in module_storages)
        or any(
            storage.get("__name__") != name
            for storage, name in zip(module_storages, names)
        )
        or self_storage.get("_VALIDATION_ALIASES") is not aliases
        or self_storage.get("_VALIDATION_CLASS_SURFACES") is not class_surfaces
        or self_storage.get("_METHOD_ANCHOR_ITEMS") is not method_items
        or self_storage.get("_DESCRIPTOR_ANCHOR_ITEMS") is not descriptor_items
        or any(self_storage.get(name) is not value for name, value in aliases)
        or self_storage.get("_validate_local_helper_anchors")
        is not local_helper_validator
        or type(_CONSUMER_METHOD_ANCHORS) is not dict
        or type(_CONSUMER_DESCRIPTOR_ANCHORS) is not dict
        or any(
            type(key) is not tuple
            or len(key) != 2
            or type(key[0]) is not type
            or type(key[1]) is not str
            for key in _CONSUMER_METHOD_ANCHORS
        )
        or any(
            type(key) is not tuple
            or len(key) != 2
            or type(key[0]) is not type
            or type(key[1]) is not str
            for key in _CONSUMER_DESCRIPTOR_ANCHORS
        )
        or anchors_storage.get("_CONSUMER_METHOD_ANCHORS")
        is not _CONSUMER_METHOD_ANCHORS
        or anchors_storage.get("_CONSUMER_DESCRIPTOR_ANCHORS")
        is not _CONSUMER_DESCRIPTOR_ANCHORS
        or capsule_storage.get("_InitialScreeningResearchContextCapsule")
        is not _InitialScreeningResearchContextCapsule
        or capsule_storage.get("_InitialScreeningResearchContextInputs")
        is not _InitialScreeningResearchContextInputs
        or capsule_storage.get("_InitialScreeningResearchContextPublication")
        is not _InitialScreeningResearchContextPublication
        or runtime_storage.get("_validate_capsule_runtime_dependencies")
        is not runtime_validator
        or runtime_storage.get("_research_context_capsule_h_fields")
        is not _research_context_capsule_h_fields
        or integration_storage.get("_materialize_research_context_h_fields")
        is not _MATERIALIZE_H_FIELDS
        or integration_storage.get("_CAPSULE_H_FIELDS")
        is not _research_context_capsule_h_fields
    ):
        raise TypeError
    local_helper_validator(self_storage)
    if not same_anchor_items(
        _CONSUMER_METHOD_ANCHORS, method_items
    ) or not same_anchor_items(_CONSUMER_DESCRIPTOR_ANCHORS, descriptor_items):
        raise TypeError
    for value, name, qualname, module_name, mro in class_surfaces:
        if type(value) is not type:
            raise TypeError
        storage = vars(value)
        if (
            type(storage) is not MappingProxyType
            or any(type(key) is not str for key in storage)
            or type(type.__getattribute__(value, "__name__")) is not str
            or type(type.__getattribute__(value, "__qualname__")) is not str
            or type(type.__getattribute__(value, "__module__")) is not str
            or type.__getattribute__(value, "__name__") != name
            or type.__getattribute__(value, "__qualname__") != qualname
            or type.__getattribute__(value, "__module__") != module_name
            or type.__getattribute__(value, "__mro__") is not mro
        ):
            raise TypeError
    cast(Callable[[], None], runtime_validator)()


def _register_initial_screening_research_context_owner(
    owner: Any,
    inputs: Any,
    dependency_validator: Any = _validate_validation_dependencies,
    error_type: Any = _RESEARCH_CONTEXT_ERROR,
    error_token: str = _ERROR,
    base_exception: Any = BaseException,
) -> None:
    baseline: _RegisteredResearchContextBaseline | None = None
    failed = False
    try:
        dependency_validator()
        from scion.core.campaign import CampaignManager

        if (
            type(owner) is not CampaignManager
            or type(inputs) is not _InitialScreeningResearchContextInputs
            or type(_REGISTERED_OWNERS) is not weakref.WeakKeyDictionary
            or weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, owner) is not None
        ):
            raise TypeError
        inputs = cast(Any, inputs)
        owner_storage = _exact_storage(owner)
        if (
            owner_storage.get(_ACTIVE_ATTRIBUTE) is not True
            or owner_storage.get(_INPUTS_ATTRIBUTE) is not inputs
        ):
            raise ValueError
        inputs_key = _published_research_context_inputs_key(inputs)
        capsule = _inputs_capsule(inputs)
        capsule_key = _research_context_capsule_pristine_key(capsule)
        publication = _inputs_publication(inputs)
        _validate_controls_publication_join(
            owner_storage.get("_initial_screening_study_controls"), publication
        )
        runtime, context, proposal = _installed_graph(owner_storage, capsule)
        baseline = _RegisteredResearchContextBaseline(
            inputs_ref=weakref.ref(inputs),
            capsule_ref=weakref.ref(capsule),
            problem_runtime_ref=weakref.ref(runtime),
            context_manager_ref=weakref.ref(context),
            proposal_pipeline_ref=weakref.ref(proposal),
            inputs_key=inputs_key,
            capsule_key=capsule_key,
            payload_bytes=vars(inputs)["payload_bytes"],
            campaign_dir=vars(publication)["campaign_dir"],
            directory_fingerprints=vars(publication)["directory_fingerprints"],
            leaf_fingerprint=vars(publication)["leaf_fingerprint"],
        )
        _validate_baseline_shape(baseline)
        weakref.WeakKeyDictionary.__setitem__(_REGISTERED_OWNERS, owner, baseline)
        _register_research_context_run_authority(
            owner,
            _SELF_MODULE,
            research_context_boundary_module,
            _prepare_research_context_run_validation,
            _validate_research_context_publication,
            _validate_research_context_installed_runtime,
            _RESEARCH_CONTEXT_ERROR,
            _ERROR,
            baseline,
        )
    except base_exception:
        try:
            current = weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, owner)
            if baseline is not None and current is baseline:
                weakref.WeakKeyDictionary.__delitem__(_REGISTERED_OWNERS, owner)
        except BaseException as ignored_cleanup_error:  # noqa: BLE001
            del ignored_cleanup_error
        failed = True
    if failed:
        raise error_type(error_token) from None


def _prepare_research_context_run_validation(
    owner: Any,
    owner_storage: dict[str, Any],
    dependency_validator: Any = _validate_validation_dependencies,
    error_type: Any = _RESEARCH_CONTEXT_ERROR,
    error_token: str = _ERROR,
    base_exception: Any = BaseException,
) -> _ResearchContextRunState | None:
    try:
        dependency_validator()
        return _prepare_research_context_run_validation_unchecked(owner, owner_storage)
    except base_exception:
        raise error_type(error_token) from None


def _prepare_research_context_run_validation_unchecked(
    owner: Any,
    owner_storage: dict[str, Any],
) -> _ResearchContextRunState | None:
    from scion.core.campaign import CampaignManager

    _validate_exact_string_keys(owner_storage)
    marker_names = {_ACTIVE_ATTRIBUTE, _INPUTS_ATTRIBUTE}
    present = marker_names & set(owner_storage)
    if not present:
        if _owner_identity_is_registered(owner):
            raise ValueError
        return None
    if present != marker_names or type(owner) is not CampaignManager:
        raise TypeError
    inputs = owner_storage[_INPUTS_ATTRIBUTE]
    if (
        owner_storage[_ACTIVE_ATTRIBUTE] is not True
        or type(inputs) is not _InitialScreeningResearchContextInputs
        or type(_REGISTERED_OWNERS) is not weakref.WeakKeyDictionary
    ):
        raise TypeError
    inputs_key = _published_research_context_inputs_key(inputs)
    capsule = _inputs_capsule(inputs)
    capsule_key = _research_context_capsule_pristine_key(capsule)
    publication = _inputs_publication(inputs)
    _validate_controls_publication_join(
        owner_storage.get("_initial_screening_study_controls"), publication
    )
    baseline = weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, owner)
    if type(baseline) is not _RegisteredResearchContextBaseline:
        raise TypeError
    baseline = cast(_RegisteredResearchContextBaseline, baseline)
    _validate_baseline_shape(baseline)
    runtime, context, proposal = _installed_graph(owner_storage, capsule)
    if (
        baseline.inputs_ref() is not inputs
        or baseline.capsule_ref() is not capsule
        or baseline.problem_runtime_ref() is not runtime
        or baseline.context_manager_ref() is not context
        or baseline.proposal_pipeline_ref() is not proposal
        or not _same_key(inputs_key, baseline.inputs_key)
        or not _same_key(capsule_key, baseline.capsule_key)
        or type(owner_storage.get("_campaign_dir")) is not str
        or owner_storage["_campaign_dir"] != baseline.campaign_dir
    ):
        raise ValueError
    return _ResearchContextRunState(inputs=inputs, baseline=baseline)


def _validate_research_context_publication(
    state: _ResearchContextRunState,
    controls_inputs: Any,
    provider_state: Any,
    problem_state: Any,
    dependency_validator: Any = _validate_validation_dependencies,
    error_type: Any = _RESEARCH_CONTEXT_ERROR,
    error_token: str = _ERROR,
    base_exception: Any = BaseException,
) -> None:
    try:
        dependency_validator()
        _validate_research_context_publication_unchecked(
            state, controls_inputs, provider_state, problem_state
        )
    except base_exception:
        raise error_type(error_token) from None


def _validate_research_context_publication_unchecked(
    state: _ResearchContextRunState,
    controls_inputs: Any,
    provider_state: Any,
    problem_state: Any,
) -> None:
    from scion.core.initial_screening_problem_spec import (
        _FILENAME as _PROBLEM_FILENAME,
    )
    from scion.core.initial_screening_study_controls import (
        _FILENAME as _CONTROLS_FILENAME,
    )
    from scion.core.initial_screening_study_provider_policy import (
        _FILENAME as _PROVIDER_FILENAME,
    )

    _validate_state(state)
    inputs = state.inputs
    baseline = state.baseline
    publication = _inputs_publication(inputs)
    controls_publication = _validate_controls_publication_join(
        controls_inputs, publication
    )
    provider_inputs = provider_state.runtime_inputs
    problem_inputs = problem_state.runtime_inputs
    if (
        vars(publication)["campaign_dir"] != baseline.campaign_dir
        or vars(publication)["directory_fingerprints"]
        != baseline.directory_fingerprints
        or vars(publication)["leaf_fingerprint"] != baseline.leaf_fingerprint
        or controls_publication.campaign_dir != baseline.campaign_dir
        or controls_publication.directory_fingerprints
        != baseline.directory_fingerprints
        or provider_inputs.publication.campaign_dir != baseline.campaign_dir
        or problem_inputs.publication.campaign_dir != baseline.campaign_dir
    ):
        raise ValueError
    _validate_fourth_control_publication(
        controls_publication,
        first_filename=_CONTROLS_FILENAME,
        first_payload=controls_inputs.payload_bytes,
        second_filename=_PROVIDER_FILENAME,
        second_payload=provider_inputs.payload_bytes,
        second_fingerprint=provider_state.baseline.leaf_fingerprint,
        third_filename=_PROBLEM_FILENAME,
        third_payload=problem_inputs.payload_bytes,
        third_fingerprint=problem_state.baseline.leaf_fingerprint,
        filename=_FILENAME,
        payload=baseline.payload_bytes,
        fingerprint=baseline.leaf_fingerprint,
        max_bytes=_MAX_BYTES,
        require_exact_names=False,
    )


def _validate_research_context_installed_runtime(
    state: _ResearchContextRunState,
    owner: Any,
    dependency_validator: Any = _validate_validation_dependencies,
    error_type: Any = _RESEARCH_CONTEXT_ERROR,
    error_token: str = _ERROR,
    base_exception: Any = BaseException,
) -> None:
    try:
        dependency_validator()
        from scion.core.campaign import CampaignManager

        if type(owner) is not CampaignManager:
            raise TypeError
        _validate_state(state)
        owner_storage = _exact_storage(owner)
        inputs = state.inputs
        capsule = _inputs_capsule(inputs)
        runtime, context, proposal = _installed_graph(owner_storage, capsule)
        baseline = state.baseline
        if (
            owner_storage.get(_ACTIVE_ATTRIBUTE) is not True
            or owner_storage.get(_INPUTS_ATTRIBUTE) is not inputs
            or baseline.inputs_ref() is not inputs
            or baseline.capsule_ref() is not capsule
            or baseline.problem_runtime_ref() is not runtime
            or baseline.context_manager_ref() is not context
            or baseline.proposal_pipeline_ref() is not proposal
            or not _same_key(
                _published_research_context_inputs_key(inputs),
                baseline.inputs_key,
            )
            or not _same_key(
                _research_context_capsule_pristine_key(capsule),
                baseline.capsule_key,
            )
        ):
            raise ValueError
    except base_exception:
        raise error_type(error_token) from None


def _installed_graph(
    owner_storage: dict[str, Any],
    capsule: Any,
) -> tuple[Any, Any, Any]:
    runtime = owner_storage.get("_problem_runtime")
    proposal = owner_storage.get("_proposal_pipeline")
    if type(runtime) is not ProblemRuntime or type(proposal) is not ProposalPipeline:
        raise TypeError
    runtime_storage = _exact_storage(runtime)
    proposal_storage = _exact_storage(proposal)
    if set(runtime_storage) != _PROBLEM_RUNTIME_KEYS:
        raise TypeError
    if set(proposal_storage) != _PROPOSAL_PIPELINE_KEYS:
        raise TypeError
    context = runtime_storage["_ctx_manager"]
    if type(context) is not ContextManager:
        raise TypeError
    context_storage = _exact_storage(context)
    if set(context_storage) != _CONTEXT_MANAGER_KEYS:
        raise TypeError
    if (
        runtime_storage[_CAPSULE_ATTRIBUTE] is not capsule
        or context_storage[_CAPSULE_ATTRIBUTE] is not capsule
        or proposal_storage["problem_runtime"] is not runtime
        or runtime_storage["_ctx_manager"] is not context
        or runtime_storage["_adapter"] is not context_storage["_adapter"]
        or runtime_storage["_research_input"] is not None
        or not _is_exact_empty_tuple(runtime_storage["_research_history"])
        or context_storage["_research_input"] is not None
        or not _is_exact_empty_tuple(context_storage["_prior_research_observations"])
        or not _is_exact_empty_tuple(context_storage["_research_history"])
        or not _has_exact_methods(runtime, ProblemRuntime, _PROBLEM_RUNTIME_METHODS)
        or not _has_exact_methods(context, ContextManager, _CONTEXT_MANAGER_METHODS)
        or not _has_exact_methods(
            proposal, ProposalPipeline, _PROPOSAL_PIPELINE_METHODS
        )
    ):
        raise ValueError
    _research_context_capsule_pristine_key(capsule)
    return runtime, context, proposal


def _inputs_capsule(inputs: Any) -> Any:
    if type(inputs) is not _InitialScreeningResearchContextInputs:
        raise TypeError
    storage = _exact_storage(inputs)
    if set(storage) != {"request_snapshot", "capsule", "payload_bytes", "publication"}:
        raise TypeError
    capsule = storage["capsule"]
    if type(capsule) is not _InitialScreeningResearchContextCapsule:
        raise TypeError
    return capsule


def _inputs_publication(inputs: Any) -> Any:
    _inputs_capsule(inputs)
    publication = vars(inputs)["publication"]
    if type(publication) is not _InitialScreeningResearchContextPublication:
        raise TypeError
    storage = _exact_storage(publication)
    if set(storage) != {
        "campaign_dir",
        "directory_fingerprints",
        "leaf_fingerprint",
    }:
        raise TypeError
    if (
        type(storage["campaign_dir"]) is not str
        or not _directory_fingerprints(storage["directory_fingerprints"])
        or not _int_tuple(storage["leaf_fingerprint"], 4)
    ):
        raise TypeError
    return publication


def _validate_controls_publication_join(
    controls_inputs: Any,
    research_publication: Any,
) -> Any:
    if (
        type(controls_inputs) is not _InitialScreeningRuntimeInputs
        or type(research_publication) is not _InitialScreeningResearchContextPublication
    ):
        raise TypeError
    controls_storage = _exact_storage(controls_inputs)
    if set(controls_storage) != {
        field.name for field in fields(_InitialScreeningRuntimeInputs)
    }:
        raise TypeError
    controls_publication = controls_storage["publication"]
    if type(controls_publication) is not _ControlsPublication:
        raise TypeError
    controls_publication_storage = _exact_storage(controls_publication)
    publication_keys = {
        "campaign_dir",
        "directory_fingerprints",
        "leaf_fingerprint",
    }
    if set(controls_publication_storage) != publication_keys:
        raise TypeError
    research_storage = _exact_storage(research_publication)
    if set(research_storage) != publication_keys:
        raise TypeError
    controls_directories = controls_publication_storage["directory_fingerprints"]
    research_directories = research_storage["directory_fingerprints"]
    if (
        type(controls_publication_storage["campaign_dir"]) is not str
        or not _directory_fingerprints(controls_directories)
        or not _int_tuple(controls_publication_storage["leaf_fingerprint"], 4)
        or type(research_storage.get("campaign_dir")) is not str
        or not _directory_fingerprints(research_directories)
        or not _int_tuple(research_storage.get("leaf_fingerprint"), 4)
        or controls_publication_storage["campaign_dir"]
        != research_storage["campaign_dir"]
        or controls_directories != research_directories
    ):
        raise ValueError
    return controls_publication


def _validate_state(state: Any) -> None:
    if type(state) is not _ResearchContextRunState:
        raise TypeError
    storage = _exact_storage(state)
    if set(storage) != {field.name for field in fields(_ResearchContextRunState)}:
        raise TypeError
    if (
        type(storage["inputs"]) is not _InitialScreeningResearchContextInputs
        or type(storage["baseline"]) is not _RegisteredResearchContextBaseline
    ):
        raise TypeError
    _validate_baseline_shape(storage["baseline"])


def _validate_baseline_shape(baseline: Any) -> None:
    if type(baseline) is not _RegisteredResearchContextBaseline:
        raise TypeError
    storage = _exact_storage(baseline)
    if set(storage) != {
        field.name for field in fields(_RegisteredResearchContextBaseline)
    }:
        raise TypeError
    references = (
        storage["inputs_ref"],
        storage["capsule_ref"],
        storage["problem_runtime_ref"],
        storage["context_manager_ref"],
        storage["proposal_pipeline_ref"],
    )
    if (
        any(type(reference) is not weakref.ReferenceType for reference in references)
        or type(storage["inputs_key"]) is not tuple
        or type(storage["capsule_key"]) is not tuple
        or type(storage["payload_bytes"]) is not bytes
        or type(storage["campaign_dir"]) is not str
        or not _directory_fingerprints(storage["directory_fingerprints"])
        or not _int_tuple(storage["leaf_fingerprint"], 4)
    ):
        raise TypeError


def _exact_storage(value: Any) -> dict[str, Any]:
    storage = vars(value)
    _validate_exact_string_keys(storage)
    return cast(dict[str, Any], storage)


def _validate_exact_string_keys(storage: Any) -> None:
    if type(storage) is not dict or any(type(key) is not str for key in storage):
        raise TypeError


def _owner_identity_is_registered(owner: Any) -> bool:
    if type(_REGISTERED_OWNERS) is not weakref.WeakKeyDictionary:
        raise TypeError
    references = weakref.WeakKeyDictionary.keyrefs(_REGISTERED_OWNERS)
    if type(references) is not list or any(
        type(reference) is not weakref.ReferenceType for reference in references
    ):
        raise TypeError
    return any(reference() is owner for reference in references)


def _has_exact_methods(value: Any, expected_type: type, names: tuple[str, ...]) -> bool:
    if (
        type(expected_type) is not type
        or type(value) is not expected_type
        or type(names) is not tuple
        or any(type(name) is not str for name in names)
    ):
        return False
    storage = vars(value)
    class_storage = vars(expected_type)
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or type(class_storage) is not MappingProxyType
        or any(type(key) is not str for key in class_storage)
        or (expected_type, "__init__") not in _CONSUMER_METHOD_ANCHORS
        or class_storage.get("__init__")
        is not _CONSUMER_METHOD_ANCHORS[(expected_type, "__init__")]
    ):
        return False
    if any(
        class_storage.get(name) is not descriptor
        for (owner_type, name), descriptor in _CONSUMER_DESCRIPTOR_ANCHORS.items()
        if owner_type is expected_type
    ):
        return False
    descriptors: list[FunctionType] = []
    for name in names:
        key = (expected_type, name)
        if key not in _CONSUMER_METHOD_ANCHORS:
            return False
        descriptor = _CONSUMER_METHOD_ANCHORS[key]
        if (
            type(descriptor) is not FunctionType
            or name in storage
            or name not in class_storage
            or class_storage[name] is not descriptor
        ):
            return False
        descriptors.append(descriptor)
    for descriptor in descriptors:
        actual = descriptor.__get__(value, expected_type)
        if (
            type(actual) is not MethodType
            or actual.__self__ is not value
            or actual.__func__ is not descriptor
        ):
            return False
    return True


_LOCAL_HELPER_NAMES = tuple(
    """_source_bindings _anchor_items _same_anchor_items _class_surface
    _validate_validation_dependencies _prepare_research_context_run_validation
    _register_initial_screening_research_context_owner
    _prepare_research_context_run_validation_unchecked
    _validate_research_context_publication
    _validate_research_context_publication_unchecked
    _validate_research_context_installed_runtime _installed_graph
    _inputs_capsule _inputs_publication _validate_controls_publication_join
    _validate_state _validate_baseline_shape _exact_storage
    _validate_exact_string_keys _is_exact_empty_tuple
    _directory_fingerprints _int_tuple _owner_identity_is_registered
    _same_key _has_exact_methods""".split()  # noqa: SIM905 - frozen names
)
_install_local_helper_anchors(
    tuple((name, vars(_SELF_MODULE)[name]) for name in _LOCAL_HELPER_NAMES)
)
del _LOCAL_HELPER_NAMES, _install_local_helper_anchors
_install_validation_authority(_SELF_MODULE)
