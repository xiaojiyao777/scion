"""Safe consumers for an immutable initial-screening research capsule."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any

import scion.core.initial_screening_research_context
import scion.core.initial_screening_research_context_capsule  # noqa: F401

if TYPE_CHECKING:
    from scion.core.initial_screening_research_context_capsule import (
        _InitialScreeningResearchContextInputs as _InputsType,
    )

_RESEARCH_MODULE_NAME = "scion.core.initial_screening_research_context"
_CAPSULE_MODULE_NAME = "scion.core.initial_screening_research_context_capsule"
if type(sys.modules) is not dict:
    raise TypeError
research_context_module = sys.modules.get(_RESEARCH_MODULE_NAME)
capsule_module = sys.modules.get(_CAPSULE_MODULE_NAME)
if (
    type(research_context_module) is not ModuleType
    or type(capsule_module) is not ModuleType
):
    raise TypeError
_research_storage = vars(research_context_module)
_capsule_storage = vars(capsule_module)
if any(
    type(storage) is not dict or any(type(key) is not str for key in storage)
    for storage in (_research_storage, _capsule_storage)
):
    raise TypeError
_current_research_name = _research_storage.get("__name__")
_current_capsule_name = _capsule_storage.get("__name__")
if (
    type(_current_research_name) is not str
    or type(_current_capsule_name) is not str
    or _current_research_name != _RESEARCH_MODULE_NAME
    or _current_capsule_name != _CAPSULE_MODULE_NAME
):
    raise TypeError

_ERROR = _research_storage["_ERROR"]
_RESEARCH_CONTEXT_ERROR = _research_storage["_InitialScreeningResearchContextError"]
_CANONICAL_RESEARCH_CONTEXT_PAYLOAD = _research_storage[
    "_canonical_research_context_payload"
]
_GENERATION = _capsule_storage["_GENERATION"]
_InitialScreeningFrozenLoadedHistoryAvailable = _capsule_storage[
    "_InitialScreeningFrozenLoadedHistoryAvailable"
]
_InitialScreeningFrozenLoadedHistoryUnavailable = _capsule_storage[
    "_InitialScreeningFrozenLoadedHistoryUnavailable"
]
_InitialScreeningResearchContextCapsule = _capsule_storage[
    "_InitialScreeningResearchContextCapsule"
]
_InitialScreeningResearchContextInputs = _capsule_storage[
    "_InitialScreeningResearchContextInputs"
]
_InitialScreeningResearchContextPublication = _capsule_storage[
    "_InitialScreeningResearchContextPublication"
]
_capsule_key = _capsule_storage["_capsule_key"]
_capsule_research_input_union = _capsule_storage["_capsule_research_input_union"]
_exact_storage = _capsule_storage["_exact_storage"]
_publication_key = _capsule_storage["_publication_key"]
_research_context_inputs_key_impl = _capsule_storage[
    "_research_context_inputs_key_impl"
]
_research_context_inputs_pristine_key = _capsule_storage[
    "_research_context_inputs_pristine_key"
]
_same_immutable_tree = _capsule_storage["_same_immutable_tree"]
_thaw_frozen_history = _capsule_storage["_thaw_frozen_history"]
_thaw_frozen_json = _capsule_storage["_thaw_frozen_json"]
_validate_capsule_dependencies = _capsule_storage["_validate_capsule_dependencies"]
_validate_frozen_history = _capsule_storage["_validate_frozen_history"]
_validate_optional_frozen_json = _capsule_storage["_validate_optional_frozen_json"]


def _research_context_capsule_pristine_key_impl(capsule: Any) -> tuple[Any, ...]:
    storage = _exact_storage(
        capsule,
        _InitialScreeningResearchContextCapsule,
        (
            "generation",
            "problem_id",
            "research_input",
            "provider_projection",
            "loaded_history",
        ),
    )
    generation = storage["generation"]
    problem_id = storage["problem_id"]
    research_input = storage["research_input"]
    provider_projection = storage["provider_projection"]
    history = storage["loaded_history"]
    if (
        type(generation) is not int
        or generation != _GENERATION
        or type(problem_id) is not str
        or not problem_id
        or (research_input is None) != (provider_projection is None)
    ):
        raise TypeError
    _validate_optional_frozen_json(research_input)
    _validate_optional_frozen_json(provider_projection)
    _validate_frozen_history(history)
    _CANONICAL_RESEARCH_CONTEXT_PAYLOAD(
        problem_id=problem_id,
        research_input=_capsule_research_input_union(capsule),
        loaded_history=_thaw_frozen_history(history),
    )
    return _capsule_key(capsule)


def _published_research_context_inputs_key_impl(inputs: Any) -> tuple[Any, ...]:
    return _research_context_inputs_key_impl(inputs, published=True)


def _bind_research_context_publication_impl(
    inputs: Any,
    publication: Any,
) -> _InputsType:
    before = _research_context_inputs_pristine_key(inputs)
    _publication_key(publication)
    storage = _exact_storage(
        inputs,
        _InitialScreeningResearchContextInputs,
        ("request_snapshot", "capsule", "payload_bytes", "publication"),
    )
    result = _InitialScreeningResearchContextInputs(
        request_snapshot=storage["request_snapshot"],
        capsule=storage["capsule"],
        payload_bytes=storage["payload_bytes"],
        publication=publication,
    )
    result_storage = _exact_storage(
        result,
        _InitialScreeningResearchContextInputs,
        ("request_snapshot", "capsule", "payload_bytes", "publication"),
    )
    if (
        result_storage["request_snapshot"] is not storage["request_snapshot"]
        or result_storage["capsule"] is not storage["capsule"]
        or result_storage["payload_bytes"] is not storage["payload_bytes"]
        or result_storage["publication"] is not publication
        or not _same_immutable_tree(
            _research_context_inputs_pristine_key(inputs), before
        )
    ):
        raise ValueError
    _published_research_context_inputs_key_impl(result)
    return result


def _research_context_capsule_h_fields_impl(capsule: Any) -> dict[str, Any]:
    before = _research_context_capsule_pristine_key_impl(capsule)
    storage = _exact_storage(
        capsule,
        _InitialScreeningResearchContextCapsule,
        (
            "generation",
            "problem_id",
            "research_input",
            "provider_projection",
            "loaded_history",
        ),
    )
    result: dict[str, Any] = {}
    projection_key = storage["provider_projection"]
    if projection_key is not None:
        projection = _thaw_frozen_json(projection_key)
        if type(projection) is not dict or set(projection) != {
            "research_question",
            "prior_research_observations",
        }:
            raise TypeError
        result["research_question"] = projection["research_question"]
        result["prior_research_observations"] = projection[
            "prior_research_observations"
        ]
    history = _thaw_frozen_history(storage["loaded_history"])
    if history.get("availability") == "available":
        records = history.get("records")
        if type(records) is not list:
            raise TypeError
        if records:
            projected_history: list[dict[str, Any]] = []
            for record in records:
                if type(record) is not dict:
                    raise TypeError
                schema_version = record.pop("schema_version")
                problem_id = record.pop("problem_id")
                if (
                    type(schema_version) is not str
                    or problem_id != storage["problem_id"]
                ):
                    raise ValueError
                projected_history.append(record)
            result["prior_research_history"] = projected_history
    elif history.get("availability") != "unavailable":
        raise ValueError
    if not _same_immutable_tree(
        _research_context_capsule_pristine_key_impl(capsule), before
    ):
        raise ValueError
    return result


_LOCAL_HELPER_NAMES = (
    "_research_context_capsule_pristine_key_impl",
    "_published_research_context_inputs_key_impl",
    "_bind_research_context_publication_impl",
    "_research_context_capsule_h_fields_impl",
)
_LOCAL_HELPERS = tuple((name, globals()[name]) for name in _LOCAL_HELPER_NAMES)
_CAPSULE_ALIAS_NAMES = (
    "_GENERATION",
    "_InitialScreeningFrozenLoadedHistoryAvailable",
    "_InitialScreeningFrozenLoadedHistoryUnavailable",
    "_InitialScreeningResearchContextCapsule",
    "_InitialScreeningResearchContextInputs",
    "_InitialScreeningResearchContextPublication",
    "_capsule_key",
    "_capsule_research_input_union",
    "_exact_storage",
    "_publication_key",
    "_research_context_inputs_key_impl",
    "_research_context_inputs_pristine_key",
    "_same_immutable_tree",
    "_thaw_frozen_history",
    "_thaw_frozen_json",
    "_validate_capsule_dependencies",
    "_validate_frozen_history",
    "_validate_optional_frozen_json",
)
_CAPSULE_ALIASES = tuple((name, globals()[name]) for name in _CAPSULE_ALIAS_NAMES)
_LOCAL_BUILTINS = (
    "BaseException",
    "TypeError",
    "ValueError",
    "any",
    "dict",
    "globals",
    "int",
    "len",
    "list",
    "set",
    "str",
    "tuple",
    "type",
    "vars",
)


def _validate_capsule_runtime_dependencies(
    capsule_aliases: tuple[tuple[str, Any], ...] = _CAPSULE_ALIASES,
    local_helpers: tuple[tuple[str, Any], ...] = _LOCAL_HELPERS,
    builtin_names: tuple[str, ...] = _LOCAL_BUILTINS,
    capsule_validator: Any = _validate_capsule_dependencies,
    canonical_anchor: Any = _CANONICAL_RESEARCH_CONTEXT_PAYLOAD,
    error_token: str = _ERROR,
    error_class: Any = _RESEARCH_CONTEXT_ERROR,
    self_module: ModuleType = sys.modules[__name__],
    self_name: str = __name__,
    capsule_module_anchor: ModuleType = capsule_module,
    capsule_module_name: str = _CAPSULE_MODULE_NAME,
    research_module_anchor: ModuleType = research_context_module,
    research_module_name: str = _RESEARCH_MODULE_NAME,
    sys_module: ModuleType = sys,
    sys_modules: dict[str, Any] = sys.modules,
    module_type: Any = ModuleType,
    class_type: Any = type,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    tuple_type: Any = tuple,
    dict_type: Any = dict,
    str_type: Any = str,
    error_type: Any = TypeError,
) -> None:
    modules = (self_module, capsule_module_anchor, research_module_anchor, sys_module)
    if any_fn(type_fn(module) is not module_type for module in modules):
        raise error_type
    self_storage = vars_fn(self_module)
    capsule_storage = vars_fn(capsule_module_anchor)
    research_storage = vars_fn(research_module_anchor)
    sys_storage = vars_fn(sys_module)
    storages = (self_storage, capsule_storage, research_storage, sys_storage)
    if any_fn(
        type_fn(storage) is not dict_type
        or any_fn(type_fn(key) is not str_type for key in storage)
        for storage in storages
    ):
        raise error_type
    current_capsule_name = capsule_storage.get("__name__")
    current_research_name = research_storage.get("__name__")
    current_self_name = self_storage.get("__name__")
    if (
        type_fn(self_name) is not str_type
        or type_fn(capsule_module_name) is not str_type
        or type_fn(research_module_name) is not str_type
        or type_fn(current_capsule_name) is not str_type
        or type_fn(current_research_name) is not str_type
        or type_fn(current_self_name) is not str_type
        or current_capsule_name != capsule_module_name
        or current_research_name != research_module_name
        or current_self_name != self_name
        or type_fn(sys_modules) is not dict_type
        or sys_storage.get("modules") is not sys_modules
        or sys_modules.get(self_name) is not self_module
        or sys_modules.get(capsule_module_name) is not capsule_module_anchor
        or sys_modules.get(research_module_name) is not research_module_anchor
        or self_storage.get("sys") is not sys_module
        or self_storage.get("ModuleType") is not module_type
        or self_storage.get("capsule_module") is not capsule_module_anchor
        or self_storage.get("research_context_module") is not research_module_anchor
        or self_storage.get("_CAPSULE_MODULE_NAME") is not capsule_module_name
        or self_storage.get("_RESEARCH_MODULE_NAME") is not research_module_name
        or type_fn(error_token) is not str_type
        or type_fn(error_class) is not class_type
        or self_storage.get("_ERROR") is not error_token
        or research_storage.get("_ERROR") is not error_token
        or self_storage.get("_RESEARCH_CONTEXT_ERROR") is not error_class
        or research_storage.get("_InitialScreeningResearchContextError")
        is not error_class
        or self_storage.get("_CANONICAL_RESEARCH_CONTEXT_PAYLOAD")
        is not canonical_anchor
        or research_storage.get("_canonical_research_context_payload")
        is not canonical_anchor
        or self_storage.get("_CAPSULE_ALIASES") is not capsule_aliases
        or self_storage.get("_LOCAL_HELPERS") is not local_helpers
        or self_storage.get("_LOCAL_BUILTINS") is not builtin_names
    ):
        raise error_type
    for value in (capsule_aliases, local_helpers, builtin_names):
        if type_fn(value) is not tuple_type:
            raise error_type
    for name, value in capsule_aliases:
        if (
            type_fn(name) is not str_type
            or self_storage.get(name) is not value
            or capsule_storage.get(name) is not value
        ):
            raise error_type
    for name, helper in local_helpers:
        if type_fn(name) is not str_type or self_storage.get(name) is not helper:
            raise error_type
    if any_fn(type_fn(name) is not str_type for name in builtin_names) or any_fn(
        name in self_storage for name in builtin_names
    ):
        raise error_type
    if capsule_storage.get("_validate_capsule_dependencies") is not capsule_validator:
        raise error_type
    capsule_validator()


def _research_context_capsule_pristine_key(
    capsule: Any,
    dependency_validator: Any = _validate_capsule_runtime_dependencies,
    implementation: Any = _research_context_capsule_pristine_key_impl,
    self_module: ModuleType = sys.modules[__name__],
    module_type: Any = ModuleType,
    type_fn: Any = type,
    vars_fn: Any = vars,
    dict_type: Any = dict,
    error_type: Any = TypeError,
) -> tuple[Any, ...]:
    if type_fn(self_module) is not module_type:
        raise error_type
    storage = vars_fn(self_module)
    if (
        type_fn(storage) is not dict_type
        or storage.get("_validate_capsule_runtime_dependencies")
        is not dependency_validator
        or storage.get("_research_context_capsule_pristine_key_impl")
        is not implementation
    ):
        raise error_type
    dependency_validator()
    return implementation(capsule)


def _published_research_context_inputs_key(
    inputs: Any,
    dependency_validator: Any = _validate_capsule_runtime_dependencies,
    implementation: Any = _published_research_context_inputs_key_impl,
) -> tuple[Any, ...]:
    dependency_validator()
    return implementation(inputs)


def _bind_research_context_publication(
    inputs: Any,
    publication: Any,
    dependency_validator: Any = _validate_capsule_runtime_dependencies,
    implementation: Any = _bind_research_context_publication_impl,
    error_class: Any = _RESEARCH_CONTEXT_ERROR,
    error_token: str = _ERROR,
    base_exception: Any = BaseException,
) -> _InputsType:
    failed = False
    result: _InputsType | None = None
    try:
        dependency_validator()
        result = implementation(inputs, publication)
    except base_exception:
        failed = True
    if failed or result is None:
        raise error_class(error_token)
    return result


def _research_context_capsule_h_fields(
    capsule: Any,
    dependency_validator: Any = _validate_capsule_runtime_dependencies,
    implementation: Any = _research_context_capsule_h_fields_impl,
    error_class: Any = _RESEARCH_CONTEXT_ERROR,
    error_token: str = _ERROR,
    base_exception: Any = BaseException,
) -> dict[str, Any]:
    failed = False
    result: dict[str, Any] | None = None
    try:
        dependency_validator()
        result = implementation(capsule)
    except base_exception:
        failed = True
    if failed or result is None:
        raise error_class(error_token)
    return result


__all__ = []
