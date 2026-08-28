from __future__ import annotations

import sys
from types import MappingProxyType, MethodType, ModuleType
from typing import Any, cast

from scion.core import campaign as campaign_module
from scion.core import campaign_composition as campaign_composition_module
from scion.core import (
    initial_screening_problem_spec as problem_spec_module,
)
from scion.core import (
    initial_screening_problem_spec_anchors as problem_anchors_module,
)
from scion.core import (
    initial_screening_research_context as research_context_module,
)
from scion.core import (
    initial_screening_research_context_capsule as capsule_module,
)
from scion.core import (
    initial_screening_research_context_capsule_runtime as capsule_runtime_module,
)
from scion.core import (
    initial_screening_research_context_composition as composition_module,
)
from scion.core import (
    initial_screening_research_context_edges as edges_module,
)
from scion.core import initial_screening_research_context_io as context_io_module
from scion.core import initial_screening_study_controls as controls_module
from scion.core import (
    initial_screening_study_provider_policy as provider_policy_module,
)
from scion.core import problem_runtime as problem_runtime_module
from scion.core import proposal_pipeline as proposal_pipeline_module
from scion.proposal import context_manager as context_manager_module

_MODULE_NAMES = (
    "scion.core.campaign",
    "scion.core.campaign_composition",
    "scion.core.initial_screening_problem_spec",
    "scion.core.initial_screening_problem_spec_anchors",
    "scion.core.initial_screening_research_context",
    "scion.core.initial_screening_research_context_capsule",
    "scion.core.initial_screening_research_context_capsule_runtime",
    "scion.core.initial_screening_research_context_composition",
    "scion.core.initial_screening_research_context_edges",
    "scion.core.initial_screening_research_context_io",
    "scion.core.initial_screening_study_controls",
    "scion.core.initial_screening_study_provider_policy",
    "scion.core.problem_runtime",
    "scion.core.proposal_pipeline",
    "scion.proposal.context_manager",
)
_SOURCE_MODULES = (
    campaign_module,
    campaign_composition_module,
    problem_spec_module,
    problem_anchors_module,
    research_context_module,
    capsule_module,
    capsule_runtime_module,
    composition_module,
    edges_module,
    context_io_module,
    controls_module,
    provider_policy_module,
    problem_runtime_module,
    proposal_pipeline_module,
    context_manager_module,
)
if (
    type(sys.modules) is not dict
    or any(type(name) is not str for name in sys.modules)
    or any(type(module) is not ModuleType for module in _SOURCE_MODULES)
):
    raise TypeError
_SOURCE_STORAGES = tuple(vars(module) for module in _SOURCE_MODULES)
if any(
    type(storage) is not dict or any(type(key) is not str for key in storage)
    for storage in _SOURCE_STORAGES
):
    raise TypeError
for _module_name, _module, _storage in zip(
    _MODULE_NAMES,
    _SOURCE_MODULES,
    _SOURCE_STORAGES,
    strict=True,
):
    _current_name = _storage.get("__name__")
    if (
        type(_current_name) is not str
        or _current_name != _module_name
        or sys.modules.get(_module_name) is not _module
    ):
        raise TypeError
_SELF_MODULE = cast(ModuleType, sys.modules[__name__])

(
    _campaign_storage,
    _campaign_composition_storage,
    _problem_storage,
    _problem_anchors_storage,
    _research_storage,
    _capsule_storage,
    _capsule_runtime_storage,
    _composition_storage,
    _edges_storage,
    _context_io_storage,
    _controls_storage,
    _provider_storage,
    _problem_runtime_storage,
    _proposal_storage,
    _context_manager_storage,
) = _SOURCE_STORAGES

_INPUTS_PRISTINE_KEY = _capsule_storage["_research_context_inputs_pristine_key"]
_PUBLICATION_TYPE = _capsule_storage["_InitialScreeningResearchContextPublication"]
_INPUTS_TYPE = _capsule_storage["_InitialScreeningResearchContextInputs"]
_BIND_PUBLICATION = _capsule_runtime_storage["_bind_research_context_publication"]
_PUBLISHED_INPUTS_KEY = _capsule_runtime_storage[
    "_published_research_context_inputs_key"
]
_CAPSULE_H_FIELDS = _capsule_runtime_storage["_research_context_capsule_h_fields"]
_CAPSULE_PRISTINE_KEY = _capsule_runtime_storage[
    "_research_context_capsule_pristine_key"
]
_PREPARE_RESEARCH_CONTEXT = _composition_storage[
    "_prepare_initial_screening_research_context"
]
_CAMPAIGN_CONSTRUCTION_EDGE = _edges_storage[
    "_compose_initial_screening_research_context_campaign"
]
_MATERIALIZER_RESOLUTION_EDGE = _edges_storage[
    "_validated_research_context_materializer_edge"
]
_INSTALL_INTEGRATION_AUTHORITIES = _edges_storage[
    "_install_research_context_integration_authorities"
]
_PUBLISH_FOURTH = _context_io_storage["_publish_fourth_control"]

_ERROR = _research_storage["_ERROR"]
_RESEARCH_CONTEXT_ERROR = _research_storage["_InitialScreeningResearchContextError"]
_FILENAME = _research_storage["_FILENAME"]
_MAX_BYTES = _research_storage["_MAX_BYTES"]
_CONTROLS_FILENAME = _controls_storage["_FILENAME"]
_CONTROLS_INPUTS_TYPE = _controls_storage["_InitialScreeningRuntimeInputs"]
_PROVIDER_FILENAME = _provider_storage["_FILENAME"]
_PROBLEM_FILENAME = _problem_storage["_FILENAME"]
_PROVIDER_INPUTS_TYPE = _provider_storage["_InitialScreeningProviderPolicyInputs"]
_PROBLEM_INPUTS_TYPE = _problem_storage["_InitialScreeningProblemSpecInputs"]

CampaignManager = _campaign_storage["CampaignManager"]
_InitialScreeningControlsSetup = _campaign_composition_storage[
    "_InitialScreeningControlsSetup"
]
ProposalPipeline = _proposal_storage["ProposalPipeline"]
ProblemRuntime = _problem_runtime_storage["ProblemRuntime"]
ContextManager = _context_manager_storage["ContextManager"]
_CONSUMER_METHOD_ANCHORS = _problem_anchors_storage["_CONSUMER_METHOD_ANCHORS"]
_CONSUMER_DESCRIPTOR_ANCHORS = _problem_anchors_storage["_CONSUMER_DESCRIPTOR_ANCHORS"]
if (
    type(_CONSUMER_METHOD_ANCHORS) is not dict
    or type(_CONSUMER_DESCRIPTOR_ANCHORS) is not dict
):
    raise TypeError
_METHOD_ANCHOR_ITEMS = tuple(_CONSUMER_METHOD_ANCHORS.items())
_DESCRIPTOR_ANCHOR_ITEMS = tuple(_CONSUMER_DESCRIPTOR_ANCHORS.items())

_CAPSULE_ATTRIBUTE = "_initial_screening_research_context_capsule"
_OWNER_ACTIVE_ATTRIBUTE = "_initial_screening_research_context_active"
_OWNER_INPUTS_ATTRIBUTE = "_initial_screening_research_context"
_PROBLEM_RUNTIME_KEYS = (
    "_spec",
    "_adapter",
    "_split_manifest",
    "_seed_ledger",
    "_research_input",
    "_research_history",
    "_development_suites",
    "_ctx_manager",
)
_CONTEXT_MANAGER_KEYS = (
    "_adapter",
    "_research_input",
    "_prior_research_observations",
    "_research_history",
)
_PROBLEM_RUNTIME_METHODS = (
    "build_hypothesis_context",
    "build_code_context",
    "hypothesis_research_public_sources",
    "hypothesis_research_source_prefixes",
)
_CONTEXT_MANAGER_METHODS = ("build_hypothesis_context", "build_code_context")

_SOURCE_BINDINGS = (
    (capsule_module, "_research_context_inputs_pristine_key", _INPUTS_PRISTINE_KEY),
    (capsule_module, "_InitialScreeningResearchContextPublication", _PUBLICATION_TYPE),
    (capsule_module, "_InitialScreeningResearchContextInputs", _INPUTS_TYPE),
    (
        capsule_runtime_module,
        "_bind_research_context_publication",
        _BIND_PUBLICATION,
    ),
    (
        capsule_runtime_module,
        "_published_research_context_inputs_key",
        _PUBLISHED_INPUTS_KEY,
    ),
    (
        capsule_runtime_module,
        "_research_context_capsule_h_fields",
        _CAPSULE_H_FIELDS,
    ),
    (
        capsule_runtime_module,
        "_research_context_capsule_pristine_key",
        _CAPSULE_PRISTINE_KEY,
    ),
    (
        composition_module,
        "_prepare_initial_screening_research_context",
        _PREPARE_RESEARCH_CONTEXT,
    ),
    (
        edges_module,
        "_compose_initial_screening_research_context_campaign",
        _CAMPAIGN_CONSTRUCTION_EDGE,
    ),
    (
        edges_module,
        "_validated_research_context_materializer_edge",
        _MATERIALIZER_RESOLUTION_EDGE,
    ),
    (
        edges_module,
        "_install_research_context_integration_authorities",
        _INSTALL_INTEGRATION_AUTHORITIES,
    ),
    (context_io_module, "_publish_fourth_control", _PUBLISH_FOURTH),
    (research_context_module, "_ERROR", _ERROR),
    (
        research_context_module,
        "_InitialScreeningResearchContextError",
        _RESEARCH_CONTEXT_ERROR,
    ),
    (research_context_module, "_FILENAME", _FILENAME),
    (research_context_module, "_MAX_BYTES", _MAX_BYTES),
    (controls_module, "_FILENAME", _CONTROLS_FILENAME),
    (controls_module, "_InitialScreeningRuntimeInputs", _CONTROLS_INPUTS_TYPE),
    (provider_policy_module, "_FILENAME", _PROVIDER_FILENAME),
    (
        provider_policy_module,
        "_InitialScreeningProviderPolicyInputs",
        _PROVIDER_INPUTS_TYPE,
    ),
    (problem_spec_module, "_FILENAME", _PROBLEM_FILENAME),
    (
        problem_spec_module,
        "_InitialScreeningProblemSpecInputs",
        _PROBLEM_INPUTS_TYPE,
    ),
    (campaign_module, "CampaignManager", CampaignManager),
    (
        campaign_composition_module,
        "_InitialScreeningControlsSetup",
        _InitialScreeningControlsSetup,
    ),
    (proposal_pipeline_module, "ProposalPipeline", ProposalPipeline),
    (problem_runtime_module, "ProblemRuntime", ProblemRuntime),
    (context_manager_module, "ContextManager", ContextManager),
    (
        problem_anchors_module,
        "_CONSUMER_METHOD_ANCHORS",
        _CONSUMER_METHOD_ANCHORS,
    ),
    (
        problem_anchors_module,
        "_CONSUMER_DESCRIPTOR_ANCHORS",
        _CONSUMER_DESCRIPTOR_ANCHORS,
    ),
)
_LOCAL_SOURCE_ALIASES = (
    ("edges_module", edges_module),
    ("_INPUTS_PRISTINE_KEY", _INPUTS_PRISTINE_KEY),
    ("_PUBLICATION_TYPE", _PUBLICATION_TYPE),
    ("_INPUTS_TYPE", _INPUTS_TYPE),
    ("_BIND_PUBLICATION", _BIND_PUBLICATION),
    ("_PUBLISHED_INPUTS_KEY", _PUBLISHED_INPUTS_KEY),
    ("_CAPSULE_H_FIELDS", _CAPSULE_H_FIELDS),
    ("_CAPSULE_PRISTINE_KEY", _CAPSULE_PRISTINE_KEY),
    ("_PREPARE_RESEARCH_CONTEXT", _PREPARE_RESEARCH_CONTEXT),
    ("_CAMPAIGN_CONSTRUCTION_EDGE", _CAMPAIGN_CONSTRUCTION_EDGE),
    ("_MATERIALIZER_RESOLUTION_EDGE", _MATERIALIZER_RESOLUTION_EDGE),
    ("_INSTALL_INTEGRATION_AUTHORITIES", _INSTALL_INTEGRATION_AUTHORITIES),
    ("_PUBLISH_FOURTH", _PUBLISH_FOURTH),
    ("_ERROR", _ERROR),
    ("_RESEARCH_CONTEXT_ERROR", _RESEARCH_CONTEXT_ERROR),
    ("_FILENAME", _FILENAME),
    ("_MAX_BYTES", _MAX_BYTES),
    ("_CONTROLS_FILENAME", _CONTROLS_FILENAME),
    ("_CONTROLS_INPUTS_TYPE", _CONTROLS_INPUTS_TYPE),
    ("_PROVIDER_FILENAME", _PROVIDER_FILENAME),
    ("_PROBLEM_FILENAME", _PROBLEM_FILENAME),
    ("_PROVIDER_INPUTS_TYPE", _PROVIDER_INPUTS_TYPE),
    ("_PROBLEM_INPUTS_TYPE", _PROBLEM_INPUTS_TYPE),
    ("CampaignManager", CampaignManager),
    ("_InitialScreeningControlsSetup", _InitialScreeningControlsSetup),
    ("ProposalPipeline", ProposalPipeline),
    ("ProblemRuntime", ProblemRuntime),
    ("ContextManager", ContextManager),
    ("_CONSUMER_METHOD_ANCHORS", _CONSUMER_METHOD_ANCHORS),
    ("_CONSUMER_DESCRIPTOR_ANCHORS", _CONSUMER_DESCRIPTOR_ANCHORS),
)
_MODULE_BINDINGS = tuple(zip(_MODULE_NAMES, _SOURCE_MODULES, strict=True))
_LOCAL_FUNCTION_NAMES = (
    "_has_exact_methods",
    "_is_exact_empty_tuple",
    "_fixed_error",
    "_prepare_research_context_integration",
    "_install_research_context_runtime_capsule",
    "_publish_research_context_integration",
    "_install_published_research_context_owner",
    "_materialize_research_context_h_fields",
)
_LOCAL_FUNCTION_HOLDER: list[Any] = [None]
_VALIDATOR_BINDING_HOLDER: list[Any] = [None]
_LOCAL_BUILTINS = tuple(
    (  # noqa: SIM905 - immutable finite builtin-name surface
        "BaseException TypeError ValueError any dict getattr len list object set "
        "str tuple type vars zip"
    ).split()
)


def _has_exact_methods(
    value: Any,
    expected_type: type,
    names: tuple[str, ...],
    object_getattribute: Any = object.__getattribute__,
) -> bool:
    if type(expected_type) is not type or type(value) is not expected_type:
        return False
    class_storage = vars(expected_type)
    if type(class_storage) is not MappingProxyType or any(
        type(key) is not str for key in class_storage
    ):
        return False
    storage = vars(value)
    if type(storage) is not dict or any(type(key) is not str for key in storage):
        return False
    if class_storage.get("__init__") is not dict.get(
        _CONSUMER_METHOD_ANCHORS,
        (expected_type, "__init__"),
    ):
        return False
    for (owner_type, name), descriptor in _CONSUMER_DESCRIPTOR_ANCHORS.items():
        if owner_type is expected_type and (
            name in storage or class_storage.get(name) is not descriptor
        ):
            return False
    expected_methods: list[tuple[str, Any]] = []
    for name in names:
        expected = dict.get(_CONSUMER_METHOD_ANCHORS, (expected_type, name))
        if (
            type(name) is not str
            or name in storage
            or class_storage.get(name) is not expected
        ):
            return False
        expected_methods.append((name, expected))
    for name, expected in expected_methods:
        actual = object_getattribute(value, name)
        if (
            type(actual) is not MethodType
            or actual.__self__ is not value
            or actual.__func__ is not expected
        ):
            return False
    return True


def _is_exact_empty_tuple(value: Any) -> bool:
    return type(value) is tuple and len(value) == 0


def _fixed_error(
    error_class: Any = _RESEARCH_CONTEXT_ERROR,
    error_token: str = _ERROR,
) -> BaseException:
    return error_class(error_token)


def _validated_integration_module_storages(
    modules: Any,
    source_bindings: Any,
    local_aliases: Any,
    self_storage: Any,
    sys_modules: Any,
    operations: Any,
) -> dict[ModuleType, dict[str, Any]]:
    type_fn, vars_fn, any_fn, module_type, dict_type, str_type, error_type = operations
    result: dict[ModuleType, dict[str, Any]] = {}
    for name, module in modules:
        if (
            type_fn(name) is not str_type
            or type_fn(module) is not module_type
            or sys_modules.get(name) is not module
        ):
            raise error_type
        storage = vars_fn(module)
        if type_fn(storage) is not dict_type or any_fn(
            type_fn(key) is not str_type for key in storage
        ):
            raise error_type
        current_name = storage.get("__name__")
        if type_fn(current_name) is not str_type or current_name != name:
            raise error_type
        result[module] = storage
    for module, name, value in source_bindings:
        storage = result.get(module)
        if (
            type_fn(name) is not str_type
            or storage is None
            or storage.get(name) is not value
        ):
            raise error_type
    for name, value in local_aliases:
        if type_fn(name) is not str_type or self_storage.get(name) is not value:
            raise error_type
    return result


def _validate_integration_anchor_collections(
    anchor_pairs: Any,
    holders: Any,
    local_function_names: Any,
    self_storage: Any,
    builtin_names: Any,
    operations: Any,
) -> None:
    type_fn, any_fn, len_fn, zip_fn, *exact_types = operations
    tuple_type, list_type, dict_type, str_type, class_type, error_type = exact_types
    for anchors, expected_items in anchor_pairs:
        if type_fn(anchors) is not dict_type or len_fn(anchors) != len_fn(
            expected_items
        ):
            raise error_type
        for current, expected in zip_fn(anchors.items(), expected_items):
            if (
                type_fn(current) is not tuple_type
                or len_fn(current) != 2
                or type_fn(expected) is not tuple_type
                or len_fn(expected) != 2
            ):
                raise error_type
            current_key, current_value = current
            expected_key, expected_value = expected
            if (
                type_fn(current_key) is not tuple_type
                or len_fn(current_key) != 2
                or type_fn(expected_key) is not tuple_type
                or len_fn(expected_key) != 2
                or type_fn(current_key[0]) is not class_type
                or type_fn(current_key[1]) is not str_type
                or current_key[0] is not expected_key[0]
                or current_key[1] != expected_key[1]
                or current_value is not expected_value
            ):
                raise error_type
    local_function_holder, validator_binding_holder = holders
    if any_fn(
        type_fn(holder) is not list_type or len_fn(holder) != 1 for holder in holders
    ):
        raise error_type
    local_functions = local_function_holder[0]
    validator_binding = validator_binding_holder[0]
    entry_bindings = self_storage.get("_INTEGRATION_ENTRY_BINDINGS")
    if (
        type_fn(local_functions) is not tuple_type
        or self_storage.get("_LOCAL_FUNCTIONS") is not local_functions
        or len_fn(local_functions) != len_fn(local_function_names)
        or type_fn(validator_binding) is not tuple_type
        or len_fn(validator_binding) != 2
        or validator_binding[0] != "_validate_integration_dependencies"
        or self_storage.get("_INTEGRATION_VALIDATOR_BINDING") is not validator_binding
        or self_storage.get(validator_binding[0]) is not validator_binding[1]
        or type_fn(entry_bindings) is not tuple_type
        or len_fn(entry_bindings) != len_fn(local_functions) - 3
    ):
        raise error_type
    for expected_name, item in zip_fn(local_function_names, local_functions):
        if (
            type_fn(expected_name) is not str_type
            or type_fn(item) is not tuple_type
            or len_fn(item) != 2
            or item[0] != expected_name
            or self_storage.get(expected_name) is not item[1]
        ):
            raise error_type
    for entry, expected in zip_fn(entry_bindings, local_functions[3:]):
        if (
            type_fn(entry) is not tuple_type
            or len_fn(entry) != 2
            or entry[0] != expected[0]
            or entry[1] is not expected[1]
        ):
            raise error_type
    if any_fn(type_fn(name) is not str_type for name in builtin_names) or any_fn(
        name in self_storage for name in builtin_names
    ):
        raise error_type


def _validate_integration_dependencies(
    modules: tuple[tuple[str, ModuleType], ...] = _MODULE_BINDINGS,
    source_bindings: tuple[tuple[ModuleType, str, Any], ...] = _SOURCE_BINDINGS,
    local_aliases: tuple[tuple[str, Any], ...] = _LOCAL_SOURCE_ALIASES,
    method_items: tuple[tuple[Any, Any], ...] = _METHOD_ANCHOR_ITEMS,
    descriptor_items: tuple[tuple[Any, Any], ...] = _DESCRIPTOR_ANCHOR_ITEMS,
    local_function_names: tuple[str, ...] = _LOCAL_FUNCTION_NAMES,
    local_function_holder: list[Any] = _LOCAL_FUNCTION_HOLDER,
    validator_binding_holder: list[Any] = _VALIDATOR_BINDING_HOLDER,
    builtin_names: tuple[str, ...] = _LOCAL_BUILTINS,
    capsule_attribute: str = _CAPSULE_ATTRIBUTE,
    owner_active_attribute: str = _OWNER_ACTIVE_ATTRIBUTE,
    owner_inputs_attribute: str = _OWNER_INPUTS_ATTRIBUTE,
    runtime_keys: tuple[str, ...] = _PROBLEM_RUNTIME_KEYS,
    context_keys: tuple[str, ...] = _CONTEXT_MANAGER_KEYS,
    runtime_methods: tuple[str, ...] = _PROBLEM_RUNTIME_METHODS,
    context_methods: tuple[str, ...] = _CONTEXT_MANAGER_METHODS,
    method_anchors: dict[tuple[type, str], Any] = _CONSUMER_METHOD_ANCHORS,
    descriptor_anchors: dict[tuple[type, str], Any] = (_CONSUMER_DESCRIPTOR_ANCHORS),
    self_module: ModuleType = _SELF_MODULE,
    self_name: str = __name__,
    sys_module: ModuleType = sys,
    sys_modules: dict[str, Any] = sys.modules,
    module_type: Any = ModuleType,
    mapping_proxy_type: Any = MappingProxyType,
    method_type: Any = MethodType,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    len_fn: Any = len,
    zip_fn: Any = zip,
    tuple_type: Any = tuple,
    list_type: Any = list,
    dict_type: Any = dict,
    str_type: Any = str,
    int_type: Any = int,
    class_type: Any = type,
    error_type: Any = TypeError,
    module_storage_validator: Any = _validated_integration_module_storages,
    anchor_collections_validator: Any = _validate_integration_anchor_collections,
) -> None:
    if (
        type_fn(self_module) is not module_type
        or type_fn(sys_module) is not module_type
    ):
        raise error_type
    self_storage = vars_fn(self_module)
    sys_storage = vars_fn(sys_module)
    if (
        type_fn(self_storage) is not dict_type
        or type_fn(sys_storage) is not dict_type
        or any_fn(type_fn(key) is not str_type for key in self_storage)
        or any_fn(type_fn(key) is not str_type for key in sys_storage)
    ):
        raise error_type
    current_self_name = self_storage.get("__name__")
    collections = (
        modules,
        source_bindings,
        local_aliases,
        method_items,
        descriptor_items,
        local_function_names,
        builtin_names,
        runtime_keys,
        context_keys,
        runtime_methods,
        context_methods,
    )
    if (
        type_fn(sys_modules) is not dict_type
        or any_fn(type_fn(key) is not str_type for key in sys_modules)
        or sys_storage.get("modules") is not sys_modules
        or type_fn(self_name) is not str_type
        or type_fn(current_self_name) is not str_type
        or current_self_name != self_name
        or sys_modules.get(self_name) is not self_module
        or self_storage.get("sys") is not sys_module
        or self_storage.get("ModuleType") is not module_type
        or self_storage.get("MappingProxyType") is not mapping_proxy_type
        or self_storage.get("MethodType") is not method_type
        or self_storage.get("_MODULE_BINDINGS") is not modules
        or self_storage.get("_SOURCE_BINDINGS") is not source_bindings
        or self_storage.get("_LOCAL_SOURCE_ALIASES") is not local_aliases
        or self_storage.get("_METHOD_ANCHOR_ITEMS") is not method_items
        or self_storage.get("_DESCRIPTOR_ANCHOR_ITEMS") is not descriptor_items
        or self_storage.get("_LOCAL_FUNCTION_NAMES") is not local_function_names
        or self_storage.get("_LOCAL_FUNCTION_HOLDER") is not local_function_holder
        or self_storage.get("_VALIDATOR_BINDING_HOLDER") is not validator_binding_holder
        or self_storage.get("_LOCAL_BUILTINS") is not builtin_names
        or self_storage.get("_CAPSULE_ATTRIBUTE") is not capsule_attribute
        or self_storage.get("_OWNER_ACTIVE_ATTRIBUTE") is not owner_active_attribute
        or self_storage.get("_OWNER_INPUTS_ATTRIBUTE") is not owner_inputs_attribute
        or self_storage.get("_PROBLEM_RUNTIME_KEYS") is not runtime_keys
        or self_storage.get("_CONTEXT_MANAGER_KEYS") is not context_keys
        or self_storage.get("_PROBLEM_RUNTIME_METHODS") is not runtime_methods
        or self_storage.get("_CONTEXT_MANAGER_METHODS") is not context_methods
        or self_storage.get("_CONSUMER_METHOD_ANCHORS") is not method_anchors
        or self_storage.get("_CONSUMER_DESCRIPTOR_ANCHORS") is not descriptor_anchors
        or any_fn(type_fn(value) is not tuple_type for value in collections)
    ):
        raise error_type
    if (
        type_fn(capsule_attribute) is not str_type
        or capsule_attribute != "_initial_screening_research_context_capsule"
        or type_fn(owner_active_attribute) is not str_type
        or owner_active_attribute != "_initial_screening_research_context_active"
        or type_fn(owner_inputs_attribute) is not str_type
        or owner_inputs_attribute != "_initial_screening_research_context"
        or runtime_keys
        != (
            "_spec",
            "_adapter",
            "_split_manifest",
            "_seed_ledger",
            "_research_input",
            "_research_history",
            "_development_suites",
            "_ctx_manager",
        )
        or context_keys
        != (
            "_adapter",
            "_research_input",
            "_prior_research_observations",
            "_research_history",
        )
        or runtime_methods
        != (
            "build_hypothesis_context",
            "build_code_context",
            "hypothesis_research_public_sources",
            "hypothesis_research_source_prefixes",
        )
        or context_methods != ("build_hypothesis_context", "build_code_context")
        or any_fn(
            type_fn(name) is not str_type
            for names in (
                runtime_keys,
                context_keys,
                runtime_methods,
                context_methods,
            )
            for name in names
        )
    ):
        raise error_type
    module_storage_validator(
        modules,
        source_bindings,
        local_aliases,
        self_storage,
        sys_modules,
        (type_fn, vars_fn, any_fn, module_type, dict_type, str_type, error_type),
    )
    if (
        type_fn(_ERROR) is not str_type
        or type_fn(_FILENAME) is not str_type
        or type_fn(_CONTROLS_FILENAME) is not str_type
        or type_fn(_PROVIDER_FILENAME) is not str_type
        or type_fn(_PROBLEM_FILENAME) is not str_type
        or type_fn(_MAX_BYTES) is not int_type
        or _MAX_BYTES <= 0
        or type_fn(_RESEARCH_CONTEXT_ERROR) is not class_type
        or type_fn(_PUBLICATION_TYPE) is not class_type
        or type_fn(_INPUTS_TYPE) is not class_type
        or type_fn(_CONTROLS_INPUTS_TYPE) is not class_type
        or type_fn(_PROVIDER_INPUTS_TYPE) is not class_type
        or type_fn(_PROBLEM_INPUTS_TYPE) is not class_type
        or type_fn(CampaignManager) is not class_type
        or type_fn(_InitialScreeningControlsSetup) is not class_type
        or type_fn(ProposalPipeline) is not class_type
        or type_fn(ProblemRuntime) is not class_type
        or type_fn(ContextManager) is not class_type
    ):
        raise error_type
    anchor_collections_validator(
        ((method_anchors, method_items), (descriptor_anchors, descriptor_items)),
        (local_function_holder, validator_binding_holder),
        local_function_names,
        self_storage,
        builtin_names,
        (type_fn, any_fn, len_fn, zip_fn, tuple_type, list_type)
        + (dict_type, str_type, class_type, error_type),
    )


del _validated_integration_module_storages, _validate_integration_anchor_collections


def _prepare_research_context_integration(
    request: Any,
    controls_request: Any,
    provider_request: Any,
    problem_request: Any,
    problem_inputs: Any,
    *,
    research_input: Any,
    research_history: Any,
    dependency_validator: Any = _validate_integration_dependencies,
    fixed_error: Any = _fixed_error,
    base_exception: Any = BaseException,
) -> Any:
    failed = False
    result = None
    try:
        dependency_validator()
        result = _PREPARE_RESEARCH_CONTEXT(
            request,
            controls_request,
            provider_request,
            problem_request,
            problem_inputs,
            research_input=research_input,
            research_history=research_history,
        )
        if result is None:
            raise TypeError
        _INPUTS_PRISTINE_KEY(result)
    except base_exception:  # fixed private boundary
        failed = True
    if failed or result is None:
        raise fixed_error()
    return result


def _install_research_context_runtime_capsule(
    inputs: Any,
    problem_runtime: Any,
    dependency_validator: Any = _validate_integration_dependencies,
    fixed_error: Any = _fixed_error,
    base_exception: Any = BaseException,
) -> None:
    failed = False
    try:
        dependency_validator()
        _INPUTS_PRISTINE_KEY(inputs)
        if type(problem_runtime) is not ProblemRuntime:
            raise TypeError
        runtime_storage = vars(problem_runtime)
        if (
            type(runtime_storage) is not dict
            or set(runtime_storage) != set(_PROBLEM_RUNTIME_KEYS)
            or any(type(key) is not str for key in runtime_storage)
            or not _has_exact_methods(
                problem_runtime,
                ProblemRuntime,
                _PROBLEM_RUNTIME_METHODS,
            )
        ):
            raise TypeError
        context_manager = runtime_storage.get("_ctx_manager")
        if type(context_manager) is not ContextManager:
            raise TypeError
        context_storage = vars(context_manager)
        if (
            type(context_storage) is not dict
            or set(context_storage) != set(_CONTEXT_MANAGER_KEYS)
            or any(type(key) is not str for key in context_storage)
            or not _has_exact_methods(
                context_manager,
                ContextManager,
                _CONTEXT_MANAGER_METHODS,
            )
            or runtime_storage.get("_research_input") is not None
            or not _is_exact_empty_tuple(runtime_storage.get("_research_history"))
            or context_storage.get("_research_input") is not None
            or not _is_exact_empty_tuple(
                context_storage.get("_prior_research_observations")
            )
            or not _is_exact_empty_tuple(context_storage.get("_research_history"))
            or runtime_storage.get("_adapter") is not context_storage.get("_adapter")
        ):
            raise ValueError
        capsule = vars(inputs).get("capsule")
        _CAPSULE_PRISTINE_KEY(capsule)
        runtime_storage[_CAPSULE_ATTRIBUTE] = capsule
        context_storage[_CAPSULE_ATTRIBUTE] = capsule
        if (
            set(runtime_storage) != set(_PROBLEM_RUNTIME_KEYS) | {_CAPSULE_ATTRIBUTE}
            or set(context_storage) != set(_CONTEXT_MANAGER_KEYS) | {_CAPSULE_ATTRIBUTE}
            or runtime_storage.get(_CAPSULE_ATTRIBUTE) is not capsule
            or context_storage.get(_CAPSULE_ATTRIBUTE) is not capsule
            or not _has_exact_methods(
                problem_runtime,
                ProblemRuntime,
                _PROBLEM_RUNTIME_METHODS,
            )
            or not _has_exact_methods(
                context_manager,
                ContextManager,
                _CONTEXT_MANAGER_METHODS,
            )
        ):
            raise ValueError
        _CAPSULE_PRISTINE_KEY(capsule)
    except base_exception:  # fixed private boundary
        failed = True
    if failed:
        raise fixed_error()


def _publish_research_context_integration(
    inputs: Any,
    controls_setup: Any,
    provider_inputs: Any,
    problem_inputs: Any,
    dependency_validator: Any = _validate_integration_dependencies,
    fixed_error: Any = _fixed_error,
    base_exception: Any = BaseException,
) -> Any:
    failed = False
    result = None
    try:
        dependency_validator()
        _INPUTS_PRISTINE_KEY(inputs)
        if (
            type(inputs) is not _INPUTS_TYPE
            or type(controls_setup) is not _InitialScreeningControlsSetup
            or type(provider_inputs) is not _PROVIDER_INPUTS_TYPE
            or type(problem_inputs) is not _PROBLEM_INPUTS_TYPE
        ):
            raise TypeError
        controls_inputs = vars(controls_setup).get("runtime_inputs")
        if type(controls_inputs) is not _CONTROLS_INPUTS_TYPE:
            raise TypeError
        controls_publication = vars(controls_inputs).get("publication")
        provider_publication = vars(provider_inputs).get("publication")
        problem_publication = vars(problem_inputs).get("publication")
        fingerprint = _PUBLISH_FOURTH(
            controls_publication,
            first_filename=_CONTROLS_FILENAME,
            first_payload=vars(controls_inputs).get("payload_bytes"),
            second_filename=_PROVIDER_FILENAME,
            second_payload=vars(provider_inputs).get("payload_bytes"),
            second_fingerprint=vars(provider_publication).get("leaf_fingerprint"),
            third_filename=_PROBLEM_FILENAME,
            third_payload=vars(problem_inputs).get("payload_bytes"),
            third_fingerprint=vars(problem_publication).get("leaf_fingerprint"),
            filename=_FILENAME,
            payload=vars(inputs).get("payload_bytes"),
            max_bytes=_MAX_BYTES,
        )
        publication = _PUBLICATION_TYPE(
            campaign_dir=vars(controls_publication).get("campaign_dir"),
            directory_fingerprints=vars(controls_publication).get(
                "directory_fingerprints"
            ),
            leaf_fingerprint=fingerprint,
        )
        result = _BIND_PUBLICATION(inputs, publication)
        _PUBLISHED_INPUTS_KEY(result)
        if vars(result).get("capsule") is not vars(inputs).get("capsule"):
            raise ValueError
    except base_exception:  # fixed private boundary
        failed = True
    if failed or result is None:
        raise fixed_error()
    return result


def _install_published_research_context_owner(
    owner: Any,
    inputs: Any,
    dependency_validator: Any = _validate_integration_dependencies,
    fixed_error: Any = _fixed_error,
    base_exception: Any = BaseException,
) -> None:
    failed = False
    try:
        dependency_validator()
        _PUBLISHED_INPUTS_KEY(inputs)
        if type(owner) is not CampaignManager:
            raise TypeError
        owner_storage = vars(owner)
        problem_runtime = owner_storage.get("_problem_runtime")
        if type(problem_runtime) is not ProblemRuntime:
            raise TypeError
        runtime_storage = vars(problem_runtime)
        context_manager = runtime_storage.get("_ctx_manager")
        if type(context_manager) is not ContextManager:
            raise TypeError
        context_storage = vars(context_manager)
        proposal_pipeline = owner_storage.get("_proposal_pipeline")
        if type(proposal_pipeline) is not ProposalPipeline:
            raise TypeError
        proposal_storage = vars(proposal_pipeline)
        capsule = vars(inputs).get("capsule")
        if (
            type(owner_storage) is not dict
            or any(type(key) is not str for key in owner_storage)
            or type(runtime_storage) is not dict
            or set(runtime_storage) != set(_PROBLEM_RUNTIME_KEYS) | {_CAPSULE_ATTRIBUTE}
            or type(context_storage) is not dict
            or set(context_storage) != set(_CONTEXT_MANAGER_KEYS) | {_CAPSULE_ATTRIBUTE}
            or type(proposal_storage) is not dict
            or any(type(key) is not str for key in proposal_storage)
            or _OWNER_ACTIVE_ATTRIBUTE in owner_storage
            or _OWNER_INPUTS_ATTRIBUTE in owner_storage
            or runtime_storage.get(_CAPSULE_ATTRIBUTE) is not capsule
            or context_storage.get(_CAPSULE_ATTRIBUTE) is not capsule
            or proposal_storage.get("problem_runtime") is not problem_runtime
            or not _has_exact_methods(
                problem_runtime,
                ProblemRuntime,
                _PROBLEM_RUNTIME_METHODS,
            )
            or not _has_exact_methods(
                context_manager,
                ContextManager,
                _CONTEXT_MANAGER_METHODS,
            )
        ):
            raise ValueError
        _CAPSULE_PRISTINE_KEY(capsule)
        owner_storage[_OWNER_ACTIVE_ATTRIBUTE] = True
        owner_storage[_OWNER_INPUTS_ATTRIBUTE] = inputs
        if (
            owner_storage.get(_OWNER_ACTIVE_ATTRIBUTE) is not True
            or owner_storage.get(_OWNER_INPUTS_ATTRIBUTE) is not inputs
            or proposal_storage.get("problem_runtime") is not problem_runtime
            or runtime_storage.get(_CAPSULE_ATTRIBUTE) is not capsule
            or context_storage.get(_CAPSULE_ATTRIBUTE) is not capsule
        ):
            raise ValueError
        _PUBLISHED_INPUTS_KEY(inputs)
        _CAPSULE_PRISTINE_KEY(capsule)
    except base_exception:  # fixed private boundary
        failed = True
    if failed:
        raise fixed_error()


def _materialize_research_context_h_fields(
    capsule: Any,
    materializer: Any = _CAPSULE_H_FIELDS,
    dependency_validator: Any = _validate_integration_dependencies,
    fixed_error: Any = _fixed_error,
    base_exception: Any = BaseException,
) -> dict[str, Any]:
    failed = False
    result: dict[str, Any] | None = None
    try:
        dependency_validator()
        if materializer is not _CAPSULE_H_FIELDS:
            raise TypeError
        result = materializer(capsule)
        if type(result) is not dict or any(type(key) is not str for key in result):
            raise TypeError
    except base_exception:  # fixed private boundary
        failed = True
    if failed or result is None:
        raise fixed_error()
    return result


_LOCAL_FUNCTIONS = tuple(
    (name, vars(_SELF_MODULE)[name]) for name in _LOCAL_FUNCTION_NAMES
)
_LOCAL_FUNCTION_HOLDER[0] = _LOCAL_FUNCTIONS
_INTEGRATION_VALIDATOR_BINDING = (
    "_validate_integration_dependencies",
    _validate_integration_dependencies,
)
_VALIDATOR_BINDING_HOLDER[0] = _INTEGRATION_VALIDATOR_BINDING
_INTEGRATION_ENTRY_BINDINGS = tuple(_LOCAL_FUNCTIONS[3:])
__all__ = []
_INSTALL_INTEGRATION_AUTHORITIES(
    _SELF_MODULE,
    _INTEGRATION_VALIDATOR_BINDING,
    _INTEGRATION_ENTRY_BINDINGS,
)
from scion.core import initial_screening_research_context_validation as _validation

del _validation
