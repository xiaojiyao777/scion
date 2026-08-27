"""Import-time authorities for the private CVRP research-context composer."""

from __future__ import annotations

import sys
from types import MappingProxyType, ModuleType
from typing import Any, cast

import scion.core.initial_screening_problem_spec
import scion.core.initial_screening_research_context
import scion.core.initial_screening_research_context_capsule
import scion.core.initial_screening_study_controls
import scion.core.initial_screening_study_provider_policy
import scion.problem.providers
import scion.problems.cvrp.adapter
import scion.problems.cvrp.prior_research_observation  # noqa: F401

_MODULE_NAMES = (
    "scion.core.initial_screening_problem_spec",
    "scion.core.initial_screening_research_context",
    "scion.core.initial_screening_research_context_capsule",
    "scion.core.initial_screening_study_controls",
    "scion.core.initial_screening_study_provider_policy",
    "scion.problem.providers",
    "scion.problems.cvrp.adapter",
    "scion.problems.cvrp.prior_research_observation",
)
if type(sys.modules) is not dict:
    raise TypeError
_BOOTSTRAP_MODULES = cast(
    tuple[ModuleType, ...], tuple(sys.modules.get(name) for name in _MODULE_NAMES)
)
if any(type(module) is not ModuleType for module in _BOOTSTRAP_MODULES):
    raise TypeError
_BOOTSTRAP_STORAGES = tuple(vars(module) for module in _BOOTSTRAP_MODULES)
if any(
    type(storage) is not dict or any(type(key) is not str for key in storage)
    for storage in _BOOTSTRAP_STORAGES
):
    raise TypeError
for _name, _module, _storage in zip(
    _MODULE_NAMES, _BOOTSTRAP_MODULES, _BOOTSTRAP_STORAGES
):
    _current_name = _storage.get("__name__")
    if type(_current_name) is not str or _current_name != _name:
        raise TypeError
(
    problem_spec_module,
    research_context_module,
    capsule_module,
    controls_module,
    provider_policy_module,
    problem_providers_module,
    cvrp_adapter_module,
    cvrp_projection_module,
) = _BOOTSTRAP_MODULES
(
    _problem_storage,
    _research_storage,
    _capsule_storage,
    _controls_storage,
    _policy_storage,
    _providers_storage,
    _adapter_storage,
    _projection_storage,
) = _BOOTSTRAP_STORAGES

_ERROR = _research_storage["_ERROR"]
_MAX_BYTES = _research_storage["_MAX_BYTES"]
_MAX_LOADED_HISTORY_RECORDS = _research_storage["_MAX_LOADED_HISTORY_RECORDS"]
_MAX_OBSERVATIONS = 64
_MAX_INPUT_BYTES = 256 << 10
_MAX_INPUT_DEPTH = 16
_MAX_HISTORY_RECORD_BYTES = 1 << 20
_MAX_HISTORY_DEPTH = 24
_CANONICAL_RESEARCH_CONTEXT_PAYLOAD = _research_storage[
    "_canonical_research_context_payload"
]
_NORMALIZE_RESEARCH_INPUT = _research_storage["_NORMALIZE_RESEARCH_INPUT"]
_NORMALIZE_RESEARCH_HISTORY_RECORD = _research_storage[
    "_NORMALIZE_RESEARCH_HISTORY_RECORD"
]
_SCHEMA_LOCAL_HELPERS = _research_storage["_LOCAL_HELPER_ANCHORS"]
if type(_SCHEMA_LOCAL_HELPERS) is not tuple or len(_SCHEMA_LOCAL_HELPERS) != 14:
    raise TypeError
for _schema_helper in _SCHEMA_LOCAL_HELPERS:
    if (
        type(_schema_helper) is not tuple
        or len(_schema_helper) != 2
        or type(_schema_helper[0]) is not str
    ):
        raise TypeError
_VALIDATE_SCHEMA_ANCHORS = _SCHEMA_LOCAL_HELPERS[2][1]
_VALIDATE_SCHEMA_DEPENDENCIES = _SCHEMA_LOCAL_HELPERS[3][1]
_CANONICAL_FRAGMENT_SIZE = _SCHEMA_LOCAL_HELPERS[9][1]
_LOADED_HISTORY_RECORD_BUDGET = _SCHEMA_LOCAL_HELPERS[10][1]
_SCHEMA_JSON = _research_storage["json"]
if type(_SCHEMA_JSON) is not ModuleType:
    raise TypeError
_schema_json_storage = vars(_SCHEMA_JSON)
if type(_schema_json_storage) is not dict or any(
    type(key) is not str for key in _schema_json_storage
):
    raise TypeError
_schema_json_name = _schema_json_storage.get("__name__")
if (
    type(_schema_json_name) is not str
    or sys.modules.get(_schema_json_name) is not _SCHEMA_JSON
):
    raise TypeError
_SCHEMA_JSON_DUMPS = _schema_json_storage["dumps"]
_SCHEMA_JSON_ENCODER = _research_storage["_JSON_ENCODER"]
_REQUEST_TYPE = _research_storage["_InitialScreeningResearchContextRequest"]
_AVAILABLE_HISTORY_TYPE = _research_storage["_InitialScreeningLoadedHistoryAvailable"]
_UNAVAILABLE_HISTORY_TYPE = _research_storage[
    "_InitialScreeningLoadedHistoryUnavailable"
]
_RESEARCH_CONTEXT_ERROR = _research_storage["_InitialScreeningResearchContextError"]

_CONTROLS_REQUEST_TYPE = _controls_storage["_InitialScreeningStudyControlsRequest"]
_PROVIDER_REQUEST_TYPE = _policy_storage["_InitialScreeningProviderPolicyRequest"]
_PROBLEM_REQUEST_TYPE = _problem_storage["_InitialScreeningProblemSpecRequest"]
_PROBLEM_INPUTS_TYPE = _problem_storage["_InitialScreeningProblemSpecInputs"]
_PROBLEM_INPUTS_PRISTINE_KEY = _problem_storage["_problem_inputs_pristine_key"]
_SAME_PROBLEM_FROZEN_KEY = _problem_storage["_same_frozen_key"]

_RESOLVE_PRIOR_RESEARCH_PROVIDER = _providers_storage[
    "resolve_prior_research_observation_provider"
]
_PROJECT_PRIOR_RESEARCH_OBSERVATION = _providers_storage[
    "project_prior_research_observation"
]
_TYPE_GETATTRIBUTE = vars(type)["__getattribute__"]
_EXPECTED_ADAPTER_TYPE = _adapter_storage["CvrpAdapter"]
if type(_EXPECTED_ADAPTER_TYPE) is not type:
    raise TypeError
_EXPECTED_ADAPTER_FACTORY = vars(_EXPECTED_ADAPTER_TYPE)[
    "prior_research_observation_provider"
]
_EXPECTED_PROVIDER_TYPE = _projection_storage["CvrpPriorResearchObservationProvider"]
if type(_EXPECTED_PROVIDER_TYPE) is not type:
    raise TypeError
_EXPECTED_PROVIDER_PROJECT = vars(_EXPECTED_PROVIDER_TYPE)[
    "project_prior_research_observation"
]


def _class_surface(class_value: type[Any]) -> tuple[Any, ...]:
    return (
        class_value,
        _TYPE_GETATTRIBUTE(class_value, "__mro__"),
        _TYPE_GETATTRIBUTE(class_value, "__name__"),
        _TYPE_GETATTRIBUTE(class_value, "__qualname__"),
        _TYPE_GETATTRIBUTE(class_value, "__module__"),
        tuple(vars(class_value).items()),
    )


_EXPECTED_ADAPTER_CLASS_SURFACE = _class_surface(_EXPECTED_ADAPTER_TYPE)
_EXPECTED_PROVIDER_CLASS_SURFACE = _class_surface(_EXPECTED_PROVIDER_TYPE)

_CVRP_MATH = _projection_storage["math"]
if type(_CVRP_MATH) is not ModuleType:
    raise TypeError
_cvrp_math_storage = vars(_CVRP_MATH)
if type(_cvrp_math_storage) is not dict or any(
    type(key) is not str for key in _cvrp_math_storage
):
    raise TypeError
_cvrp_math_name = _cvrp_math_storage.get("__name__")
if (
    type(_cvrp_math_name) is not str
    or sys.modules.get(_cvrp_math_name) is not _CVRP_MATH
):
    raise TypeError
_CVRP_MATH_ISFINITE = _cvrp_math_storage["isfinite"]

_GENERATION = _capsule_storage["_GENERATION"]
_capsule_research_input_union = _capsule_storage["_capsule_research_input_union"]
_clone_frozen_history = _capsule_storage["_clone_frozen_history"]
_clone_frozen_json = _capsule_storage["_clone_frozen_json"]
_exact_storage = _capsule_storage["_exact_storage"]
_freeze_exact_json = _capsule_storage["_freeze_exact_json"]
_research_context_inputs_pristine_key = _capsule_storage[
    "_research_context_inputs_pristine_key"
]
_same_frozen_json = _capsule_storage["_same_frozen_json"]
_same_immutable_tree = _capsule_storage["_same_immutable_tree"]
_thaw_frozen_history = _capsule_storage["_thaw_frozen_history"]
_thaw_frozen_json = _capsule_storage["_thaw_frozen_json"]
_validate_capsule_dependencies = _capsule_storage["_validate_capsule_dependencies"]
_FrozenLoadedHistory = _capsule_storage["_FrozenLoadedHistory"]
_InitialScreeningFrozenLoadedHistoryAvailable = _capsule_storage[
    "_InitialScreeningFrozenLoadedHistoryAvailable"
]
_InitialScreeningFrozenLoadedHistoryUnavailable = _capsule_storage[
    "_InitialScreeningFrozenLoadedHistoryUnavailable"
]
_InitialScreeningResearchContextRequestSnapshot = _capsule_storage[
    "_InitialScreeningResearchContextRequestSnapshot"
]
_InitialScreeningResearchContextCapsule = _capsule_storage[
    "_InitialScreeningResearchContextCapsule"
]
_InitialScreeningResearchContextInputs = _capsule_storage[
    "_InitialScreeningResearchContextInputs"
]

_COMPOSITION_EXPORT_NAMES = (
    "_ERROR",
    "_MAX_BYTES",
    "_MAX_LOADED_HISTORY_RECORDS",
    "_MAX_OBSERVATIONS",
    "_MAX_INPUT_BYTES",
    "_MAX_INPUT_DEPTH",
    "_MAX_HISTORY_RECORD_BYTES",
    "_MAX_HISTORY_DEPTH",
    "_CANONICAL_RESEARCH_CONTEXT_PAYLOAD",
    "_NORMALIZE_RESEARCH_INPUT",
    "_NORMALIZE_RESEARCH_HISTORY_RECORD",
    "_VALIDATE_SCHEMA_ANCHORS",
    "_VALIDATE_SCHEMA_DEPENDENCIES",
    "_CANONICAL_FRAGMENT_SIZE",
    "_LOADED_HISTORY_RECORD_BUDGET",
    "_SCHEMA_JSON",
    "_SCHEMA_JSON_DUMPS",
    "_SCHEMA_JSON_ENCODER",
    "_REQUEST_TYPE",
    "_AVAILABLE_HISTORY_TYPE",
    "_UNAVAILABLE_HISTORY_TYPE",
    "_RESEARCH_CONTEXT_ERROR",
    "_CONTROLS_REQUEST_TYPE",
    "_PROVIDER_REQUEST_TYPE",
    "_PROBLEM_REQUEST_TYPE",
    "_PROBLEM_INPUTS_TYPE",
    "_PROBLEM_INPUTS_PRISTINE_KEY",
    "_SAME_PROBLEM_FROZEN_KEY",
    "_RESOLVE_PRIOR_RESEARCH_PROVIDER",
    "_PROJECT_PRIOR_RESEARCH_OBSERVATION",
    "_TYPE_GETATTRIBUTE",
    "_EXPECTED_ADAPTER_TYPE",
    "_EXPECTED_ADAPTER_FACTORY",
    "_EXPECTED_PROVIDER_TYPE",
    "_EXPECTED_PROVIDER_PROJECT",
    "_EXPECTED_ADAPTER_CLASS_SURFACE",
    "_EXPECTED_PROVIDER_CLASS_SURFACE",
    "_GENERATION",
    "_capsule_research_input_union",
    "_clone_frozen_history",
    "_clone_frozen_json",
    "_exact_storage",
    "_freeze_exact_json",
    "_research_context_inputs_pristine_key",
    "_same_frozen_json",
    "_same_immutable_tree",
    "_thaw_frozen_history",
    "_thaw_frozen_json",
    "_validate_capsule_dependencies",
    "_FrozenLoadedHistory",
    "_InitialScreeningFrozenLoadedHistoryAvailable",
    "_InitialScreeningFrozenLoadedHistoryUnavailable",
    "_InitialScreeningResearchContextRequestSnapshot",
    "_InitialScreeningResearchContextCapsule",
    "_InitialScreeningResearchContextInputs",
)
_COMPOSITION_EXPORTS = tuple(
    (name, globals()[name]) for name in _COMPOSITION_EXPORT_NAMES
)

_MODULE_BINDINGS = tuple(zip(_MODULE_NAMES, _BOOTSTRAP_MODULES)) + (
    (_schema_json_name, _SCHEMA_JSON),
    (_cvrp_math_name, _CVRP_MATH),
)
_SOURCE_IDENTITIES = (
    (research_context_module, "_ERROR", _ERROR),
    (
        research_context_module,
        "_canonical_research_context_payload",
        _CANONICAL_RESEARCH_CONTEXT_PAYLOAD,
    ),
    (research_context_module, "_NORMALIZE_RESEARCH_INPUT", _NORMALIZE_RESEARCH_INPUT),
    (
        research_context_module,
        "_NORMALIZE_RESEARCH_HISTORY_RECORD",
        _NORMALIZE_RESEARCH_HISTORY_RECORD,
    ),
    (research_context_module, "_validate_schema_anchors", _VALIDATE_SCHEMA_ANCHORS),
    (
        research_context_module,
        "_validate_dependency_anchors",
        _VALIDATE_SCHEMA_DEPENDENCIES,
    ),
    (research_context_module, "_canonical_fragment_size", _CANONICAL_FRAGMENT_SIZE),
    (
        research_context_module,
        "_loaded_history_record_budget",
        _LOADED_HISTORY_RECORD_BUDGET,
    ),
    (research_context_module, "json", _SCHEMA_JSON),
    (_SCHEMA_JSON, "dumps", _SCHEMA_JSON_DUMPS),
    (research_context_module, "_JSON_ENCODER", _SCHEMA_JSON_ENCODER),
    (research_context_module, "_InitialScreeningResearchContextRequest", _REQUEST_TYPE),
    (
        research_context_module,
        "_InitialScreeningLoadedHistoryAvailable",
        _AVAILABLE_HISTORY_TYPE,
    ),
    (
        research_context_module,
        "_InitialScreeningLoadedHistoryUnavailable",
        _UNAVAILABLE_HISTORY_TYPE,
    ),
    (
        research_context_module,
        "_InitialScreeningResearchContextError",
        _RESEARCH_CONTEXT_ERROR,
    ),
    (controls_module, "_InitialScreeningStudyControlsRequest", _CONTROLS_REQUEST_TYPE),
    (
        provider_policy_module,
        "_InitialScreeningProviderPolicyRequest",
        _PROVIDER_REQUEST_TYPE,
    ),
    (problem_spec_module, "_InitialScreeningProblemSpecRequest", _PROBLEM_REQUEST_TYPE),
    (problem_spec_module, "_InitialScreeningProblemSpecInputs", _PROBLEM_INPUTS_TYPE),
    (problem_spec_module, "_problem_inputs_pristine_key", _PROBLEM_INPUTS_PRISTINE_KEY),
    (problem_spec_module, "_same_frozen_key", _SAME_PROBLEM_FROZEN_KEY),
    (
        problem_providers_module,
        "resolve_prior_research_observation_provider",
        _RESOLVE_PRIOR_RESEARCH_PROVIDER,
    ),
    (
        problem_providers_module,
        "project_prior_research_observation",
        _PROJECT_PRIOR_RESEARCH_OBSERVATION,
    ),
    (cvrp_adapter_module, "CvrpAdapter", _EXPECTED_ADAPTER_TYPE),
    (
        cvrp_projection_module,
        "CvrpPriorResearchObservationProvider",
        _EXPECTED_PROVIDER_TYPE,
    ),
    (
        _CVRP_MATH,
        "isfinite",
        _CVRP_MATH_ISFINITE,
    ),
)
_SOURCE_VALUES = (
    (research_context_module, "_MAX_BYTES", _MAX_BYTES),
    (
        research_context_module,
        "_MAX_LOADED_HISTORY_RECORDS",
        _MAX_LOADED_HISTORY_RECORDS,
    ),
)
_PROVIDER_NAMES = (
    "resolve_prior_research_observation_provider",
    "project_prior_research_observation",
    "_resolve_provider",
    "_validate_adapter_consistency",
    "_provider_from_factory",
    "_adapter_import_path",
    "_instantiate_adapter",
    "_problem_spec_v1",
    "_problem_id",
    "Mapping",
    "Sequence",
    "deepcopy",
    "importlib",
    "load_problem_adapter",
    "ProblemAdapterLoadError",
    "ProblemProviderError",
)
_PROVIDER_SURFACE = tuple((name, _providers_storage[name]) for name in _PROVIDER_NAMES)
_PROVIDER_BUILTINS = ("callable", "dict", "getattr", "isinstance", "str", "tuple")
_CVRP_NAMES = (
    "_project_observation",
    "_project_stage",
    "_project_terminal",
    "_project_observed_outputs",
    "_project_claim_context",
    "_mapping",
    "_exact_fields",
    "_token",
    "_boolean",
    "_nonnegative_int",
    "_positive_int",
    "_number",
    "_diagnostic_value",
    "_INPUT_SCHEMA",
    "_OUTPUT_SCHEMA",
    "_TOKEN",
    "_MAX_COMPLETED_STAGES",
    "_MAX_DIAGNOSTICS",
    "_OBSERVATION_FIELDS",
    "_STAGE_FIELDS",
    "_CASE_OUTCOME_FIELDS",
    "_TERMINAL_FIELDS",
    "_FAILURE_FIELDS",
    "_DIAGNOSTIC_FIELDS",
    "_OBSERVED_OUTPUT_FIELDS",
    "_CLAIM_CONTEXT_FIELDS",
    "Mapping",
    "math",
    "re",
    "_InvalidObservation",
)
_CVRP_SURFACE = tuple((name, _projection_storage[name]) for name in _CVRP_NAMES)
_CVRP_BUILTINS = (
    "KeyError",
    "TypeError",
    "ValueError",
    "any",
    "bool",
    "dict",
    "float",
    "int",
    "isinstance",
    "len",
    "list",
    "set",
    "str",
    "type",
)
_CAPSULE_NAMES = tuple(
    name for name in _COMPOSITION_EXPORT_NAMES if name in _capsule_storage
)
_CAPSULE_SURFACE = tuple((name, _capsule_storage[name]) for name in _CAPSULE_NAMES)
_LOCAL_BUILTINS = (
    "TypeError",
    "any",
    "dict",
    "globals",
    "int",
    "len",
    "str",
    "tuple",
    "type",
    "vars",
    "zip",
)


def _validate_composition_external_dependencies(
    exports: tuple[tuple[str, Any], ...] = _COMPOSITION_EXPORTS,
    modules: tuple[tuple[str, ModuleType], ...] = _MODULE_BINDINGS,
    source_identities: tuple[tuple[ModuleType, str, Any], ...] = _SOURCE_IDENTITIES,
    source_values: tuple[tuple[ModuleType, str, Any], ...] = _SOURCE_VALUES,
    provider_surface: tuple[tuple[str, Any], ...] = _PROVIDER_SURFACE,
    provider_builtins: tuple[str, ...] = _PROVIDER_BUILTINS,
    cvrp_surface: tuple[tuple[str, Any], ...] = _CVRP_SURFACE,
    cvrp_builtins: tuple[str, ...] = _CVRP_BUILTINS,
    capsule_surface: tuple[tuple[str, Any], ...] = _CAPSULE_SURFACE,
    local_builtins: tuple[str, ...] = _LOCAL_BUILTINS,
    adapter_surface: tuple[Any, ...] = _EXPECTED_ADAPTER_CLASS_SURFACE,
    provider_class_surface: tuple[Any, ...] = _EXPECTED_PROVIDER_CLASS_SURFACE,
    capsule_validator: Any = _validate_capsule_dependencies,
    schema_validator: Any = _VALIDATE_SCHEMA_ANCHORS,
    schema_dependency_validator: Any = _VALIDATE_SCHEMA_DEPENDENCIES,
    max_observations: int = _MAX_OBSERVATIONS,
    max_input_bytes: int = _MAX_INPUT_BYTES,
    max_input_depth: int = _MAX_INPUT_DEPTH,
    max_history_record_bytes: int = _MAX_HISTORY_RECORD_BYTES,
    max_history_depth: int = _MAX_HISTORY_DEPTH,
    provider_module: ModuleType = problem_providers_module,
    projection_module: ModuleType = cvrp_projection_module,
    capsule_module_anchor: ModuleType = capsule_module,
    type_getattribute: Any = _TYPE_GETATTRIBUTE,
    self_module: ModuleType = sys.modules[__name__],
    self_name: str = __name__,
    sys_module: ModuleType = sys,
    sys_modules: dict[str, Any] = sys.modules,
    module_type: Any = ModuleType,
    mapping_proxy_type: Any = MappingProxyType,
    class_type: Any = type,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    len_fn: Any = len,
    zip_fn: Any = zip,
    tuple_type: Any = tuple,
    dict_type: Any = dict,
    str_type: Any = str,
    int_type: Any = int,
    error_type: Any = TypeError,
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
    if (
        type_fn(sys_modules) is not dict_type
        or sys_storage.get("modules") is not sys_modules
        or type_fn(self_name) is not str_type
        or type_fn(current_self_name) is not str_type
        or current_self_name != self_name
        or sys_modules.get(self_name) is not self_module
        or self_storage.get("sys") is not sys_module
        or self_storage.get("ModuleType") is not module_type
        or self_storage.get("MappingProxyType") is not mapping_proxy_type
        or self_storage.get("problem_providers_module") is not provider_module
        or self_storage.get("cvrp_projection_module") is not projection_module
        or self_storage.get("capsule_module") is not capsule_module_anchor
        or self_storage.get("_TYPE_GETATTRIBUTE") is not type_getattribute
        or vars_fn(class_type).get("__getattribute__") is not type_getattribute
        or self_storage.get("_COMPOSITION_EXPORTS") is not exports
        or self_storage.get("_MODULE_BINDINGS") is not modules
        or self_storage.get("_SOURCE_IDENTITIES") is not source_identities
        or self_storage.get("_SOURCE_VALUES") is not source_values
        or self_storage.get("_PROVIDER_SURFACE") is not provider_surface
        or self_storage.get("_PROVIDER_BUILTINS") is not provider_builtins
        or self_storage.get("_CVRP_SURFACE") is not cvrp_surface
        or self_storage.get("_CVRP_BUILTINS") is not cvrp_builtins
        or self_storage.get("_CAPSULE_SURFACE") is not capsule_surface
        or self_storage.get("_LOCAL_BUILTINS") is not local_builtins
        or self_storage.get("_EXPECTED_ADAPTER_CLASS_SURFACE") is not adapter_surface
        or self_storage.get("_EXPECTED_PROVIDER_CLASS_SURFACE")
        is not provider_class_surface
        or any_fn(type_fn(name) is not str_type for name in local_builtins)
        or any_fn(name in self_storage for name in local_builtins)
    ):
        raise error_type
    collections = (
        exports,
        modules,
        source_identities,
        source_values,
        provider_surface,
        provider_builtins,
        cvrp_surface,
        cvrp_builtins,
        capsule_surface,
        local_builtins,
    )
    if any_fn(type_fn(value) is not tuple_type for value in collections):
        raise error_type
    for name, value in exports:
        if type_fn(name) is not str_type or self_storage.get(name) is not value:
            raise error_type
    module_storages: dict[ModuleType, dict[str, Any]] = {}
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
        module_storages[module] = storage
    for module, name, value in source_identities:
        storage = module_storages.get(module)
        if (
            type_fn(name) is not str_type
            or storage is None
            or storage.get(name) is not value
        ):
            raise error_type
    for module, name, expected in source_values:
        storage = module_storages.get(module)
        if (
            type_fn(name) is not str_type
            or storage is None
            or type_fn(expected) is not int_type
            or type_fn(storage.get(name)) is not int_type
            or storage.get(name) != expected
        ):
            raise error_type
    provider_storage = module_storages[provider_module]
    projection_storage = module_storages[projection_module]
    capsule_storage = module_storages[capsule_module_anchor]
    for surface, storage in (
        (provider_surface, provider_storage),
        (cvrp_surface, projection_storage),
        (capsule_surface, capsule_storage),
    ):
        for name, value in surface:
            if type_fn(name) is not str_type or storage.get(name) is not value:
                raise error_type
    if (
        any_fn(type_fn(name) is not str_type for name in provider_builtins)
        or any_fn(type_fn(name) is not str_type for name in cvrp_builtins)
        or any_fn(name in provider_storage for name in provider_builtins)
        or any_fn(name in projection_storage for name in cvrp_builtins)
    ):
        raise error_type
    for class_surface in (adapter_surface, provider_class_surface):
        if type_fn(class_surface) is not tuple_type or len_fn(class_surface) != 6:
            raise error_type
        class_value, expected_mro, name, qualname, module_name, expected_items = (
            class_surface
        )
        if (
            type_fn(class_value) is not class_type
            or type_fn(expected_mro) is not tuple_type
            or type_fn(name) is not str_type
            or type_fn(qualname) is not str_type
            or type_fn(module_name) is not str_type
            or type_fn(expected_items) is not tuple_type
        ):
            raise error_type
        class_storage = vars_fn(class_value)
        current_mro = type_getattribute(class_value, "__mro__")
        current_name = type_getattribute(class_value, "__name__")
        current_qualname = type_getattribute(class_value, "__qualname__")
        current_module_name = type_getattribute(class_value, "__module__")
        if (
            type_fn(class_storage) is not mapping_proxy_type
            or type_fn(current_mro) is not tuple_type
            or type_fn(current_name) is not str_type
            or type_fn(current_qualname) is not str_type
            or type_fn(current_module_name) is not str_type
            or current_name != name
            or current_qualname != qualname
            or current_module_name != module_name
            or len_fn(current_mro) != len_fn(expected_mro)
            or any_fn(
                current is not expected
                for current, expected in zip_fn(current_mro, expected_mro)
            )
            or len_fn(class_storage) != len_fn(expected_items)
        ):
            raise error_type
        for current, expected in zip_fn(class_storage.items(), expected_items):
            if (
                type_fn(expected) is not tuple_type
                or len_fn(expected) != 2
                or type_fn(current[0]) is not str_type
                or type_fn(expected[0]) is not str_type
                or current[0] != expected[0]
                or current[1] is not expected[1]
            ):
                raise error_type
    capsule_validator()
    schema_validator()
    observation_cap = schema_dependency_validator()
    if (
        type_fn(max_observations) is not int_type
        or type_fn(max_input_bytes) is not int_type
        or type_fn(max_input_depth) is not int_type
        or type_fn(max_history_record_bytes) is not int_type
        or type_fn(max_history_depth) is not int_type
        or type_fn(observation_cap) is not int_type
        or observation_cap != max_observations
        or max_observations != 64
        or max_input_bytes != 256 << 10
        or max_input_depth != 16
        or max_history_record_bytes != 1 << 20
        or max_history_depth != 24
    ):
        raise error_type


_ANCHOR_HELPERS = (
    ("_class_surface", _class_surface),
    (
        "_validate_composition_external_dependencies",
        _validate_composition_external_dependencies,
    ),
)

__all__ = []
