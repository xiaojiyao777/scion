"""Prepare one immutable, CVRP-local initial-screening research context."""

# ruff: noqa: F401 -- import-time aliases are consumed by the exact surface gate.

from __future__ import annotations

import sys
from types import MappingProxyType, ModuleType
from typing import Any

import scion.core.initial_screening_research_context_composition_anchors

_ANCHORS_NAME = "scion.core.initial_screening_research_context_composition_anchors"
if type(sys.modules) is not dict:
    raise TypeError
anchors_module = sys.modules.get(_ANCHORS_NAME)
if type(anchors_module) is not ModuleType:
    raise TypeError
_anchor_storage = vars(anchors_module)
if type(_anchor_storage) is not dict or any(
    type(key) is not str for key in _anchor_storage
):
    raise TypeError
_current_anchor_name = _anchor_storage.get("__name__")
if type(_current_anchor_name) is not str or _current_anchor_name != _ANCHORS_NAME:
    raise TypeError


def _raw_anchor(name: str) -> Any:
    if type(name) is not str:
        raise TypeError
    return _anchor_storage[name]


_AVAILABLE_HISTORY_TYPE = _raw_anchor("_AVAILABLE_HISTORY_TYPE")
_CANONICAL_FRAGMENT_SIZE = _raw_anchor("_CANONICAL_FRAGMENT_SIZE")
_CANONICAL_RESEARCH_CONTEXT_PAYLOAD = _raw_anchor("_CANONICAL_RESEARCH_CONTEXT_PAYLOAD")
_COMPOSITION_EXPORT_NAMES = _raw_anchor("_COMPOSITION_EXPORT_NAMES")
_COMPOSITION_EXPORTS = _raw_anchor("_COMPOSITION_EXPORTS")
_CONTROLS_REQUEST_TYPE = _raw_anchor("_CONTROLS_REQUEST_TYPE")
_ERROR = _raw_anchor("_ERROR")
_EXPECTED_ADAPTER_CLASS_SURFACE = _raw_anchor("_EXPECTED_ADAPTER_CLASS_SURFACE")
_EXPECTED_ADAPTER_FACTORY = _raw_anchor("_EXPECTED_ADAPTER_FACTORY")
_EXPECTED_ADAPTER_TYPE = _raw_anchor("_EXPECTED_ADAPTER_TYPE")
_EXPECTED_PROVIDER_CLASS_SURFACE = _raw_anchor("_EXPECTED_PROVIDER_CLASS_SURFACE")
_EXPECTED_PROVIDER_PROJECT = _raw_anchor("_EXPECTED_PROVIDER_PROJECT")
_EXPECTED_PROVIDER_TYPE = _raw_anchor("_EXPECTED_PROVIDER_TYPE")
_GENERATION = _raw_anchor("_GENERATION")
_LOADED_HISTORY_RECORD_BUDGET = _raw_anchor("_LOADED_HISTORY_RECORD_BUDGET")
_MAX_BYTES = _raw_anchor("_MAX_BYTES")
_MAX_LOADED_HISTORY_RECORDS = _raw_anchor("_MAX_LOADED_HISTORY_RECORDS")
_MAX_OBSERVATIONS = _raw_anchor("_MAX_OBSERVATIONS")
_MAX_INPUT_BYTES = _raw_anchor("_MAX_INPUT_BYTES")
_MAX_INPUT_DEPTH = _raw_anchor("_MAX_INPUT_DEPTH")
_MAX_HISTORY_RECORD_BYTES = _raw_anchor("_MAX_HISTORY_RECORD_BYTES")
_MAX_HISTORY_DEPTH = _raw_anchor("_MAX_HISTORY_DEPTH")
_NORMALIZE_RESEARCH_HISTORY_RECORD = _raw_anchor("_NORMALIZE_RESEARCH_HISTORY_RECORD")
_NORMALIZE_RESEARCH_INPUT = _raw_anchor("_NORMALIZE_RESEARCH_INPUT")
_PROBLEM_INPUTS_PRISTINE_KEY = _raw_anchor("_PROBLEM_INPUTS_PRISTINE_KEY")
_PROBLEM_INPUTS_TYPE = _raw_anchor("_PROBLEM_INPUTS_TYPE")
_PROBLEM_REQUEST_TYPE = _raw_anchor("_PROBLEM_REQUEST_TYPE")
_PROJECT_PRIOR_RESEARCH_OBSERVATION = _raw_anchor("_PROJECT_PRIOR_RESEARCH_OBSERVATION")
_PROVIDER_REQUEST_TYPE = _raw_anchor("_PROVIDER_REQUEST_TYPE")
_REQUEST_TYPE = _raw_anchor("_REQUEST_TYPE")
_RESEARCH_CONTEXT_ERROR = _raw_anchor("_RESEARCH_CONTEXT_ERROR")
_RESOLVE_PRIOR_RESEARCH_PROVIDER = _raw_anchor("_RESOLVE_PRIOR_RESEARCH_PROVIDER")
_SAME_PROBLEM_FROZEN_KEY = _raw_anchor("_SAME_PROBLEM_FROZEN_KEY")
_SCHEMA_JSON = _raw_anchor("_SCHEMA_JSON")
_SCHEMA_JSON_DUMPS = _raw_anchor("_SCHEMA_JSON_DUMPS")
_SCHEMA_JSON_ENCODER = _raw_anchor("_SCHEMA_JSON_ENCODER")
_TYPE_GETATTRIBUTE = _raw_anchor("_TYPE_GETATTRIBUTE")
_UNAVAILABLE_HISTORY_TYPE = _raw_anchor("_UNAVAILABLE_HISTORY_TYPE")
_VALIDATE_SCHEMA_ANCHORS = _raw_anchor("_VALIDATE_SCHEMA_ANCHORS")
_VALIDATE_SCHEMA_DEPENDENCIES = _raw_anchor("_VALIDATE_SCHEMA_DEPENDENCIES")
_capsule_research_input_union = _raw_anchor("_capsule_research_input_union")
_clone_frozen_history = _raw_anchor("_clone_frozen_history")
_clone_frozen_json = _raw_anchor("_clone_frozen_json")
_exact_storage = _raw_anchor("_exact_storage")
_freeze_exact_json = _raw_anchor("_freeze_exact_json")
_FrozenLoadedHistory = _raw_anchor("_FrozenLoadedHistory")
_InitialScreeningFrozenLoadedHistoryAvailable = _raw_anchor(
    "_InitialScreeningFrozenLoadedHistoryAvailable"
)
_InitialScreeningFrozenLoadedHistoryUnavailable = _raw_anchor(
    "_InitialScreeningFrozenLoadedHistoryUnavailable"
)
_InitialScreeningResearchContextCapsule = _raw_anchor(
    "_InitialScreeningResearchContextCapsule"
)
_InitialScreeningResearchContextInputs = _raw_anchor(
    "_InitialScreeningResearchContextInputs"
)
_InitialScreeningResearchContextRequestSnapshot = _raw_anchor(
    "_InitialScreeningResearchContextRequestSnapshot"
)
_research_context_inputs_pristine_key = _raw_anchor(
    "_research_context_inputs_pristine_key"
)
_same_frozen_json = _raw_anchor("_same_frozen_json")
_same_immutable_tree = _raw_anchor("_same_immutable_tree")
_thaw_frozen_history = _raw_anchor("_thaw_frozen_history")
_thaw_frozen_json = _raw_anchor("_thaw_frozen_json")
_validate_capsule_dependencies = _raw_anchor("_validate_capsule_dependencies")
_validate_composition_external_dependencies = _raw_anchor(
    "_validate_composition_external_dependencies"
)
if type(_COMPOSITION_EXPORT_NAMES) is not tuple or any(
    type(name) is not str for name in _COMPOSITION_EXPORT_NAMES
):
    raise TypeError
del _raw_anchor


def _phase_a_consume_bytes(budgets: tuple[list[int], ...], amount: int) -> None:
    if (
        type(budgets) is not tuple
        or not budgets
        or type(amount) is not int
        or amount < 0
    ):
        raise TypeError
    for budget in budgets:
        if type(budget) is not list or len(budget) != 1 or type(budget[0]) is not int:
            raise TypeError
        if budget[0] < amount:
            raise ValueError
    for budget in budgets:
        budget[0] -= amount


def _phase_a_consume_string(value: str, budgets: tuple[list[int], ...]) -> None:
    if type(value) is not str:
        raise TypeError
    _phase_a_consume_bytes(budgets, 0)
    if len(value) + 2 > min(budget[0] for budget in budgets):
        raise ValueError
    rendered = _SCHEMA_JSON_DUMPS(
        value,
        allow_nan=False,
        cls=_SCHEMA_JSON_ENCODER,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if type(rendered) is not str:
        raise TypeError
    _phase_a_consume_bytes(budgets, len(rendered.encode("utf-8")))


def _phase_a_freeze_json(
    value: Any,
    *,
    budgets: tuple[list[int], ...],
    max_depth: int,
    depth: int = 0,
    active: set[int] | None = None,
) -> tuple[Any, ...]:
    """Freeze exact JSON while charging every output byte before allocation."""

    if type(max_depth) is not int or depth > max_depth:
        raise ValueError
    _phase_a_consume_bytes(budgets, 0)
    if value is None:
        _phase_a_consume_bytes(budgets, 4)
        return ("null",)
    if type(value) is bool:
        _phase_a_consume_bytes(budgets, 4 if value else 5)
        return ("bool", value)
    if type(value) is int:
        remaining = min(budget[0] for budget in budgets)
        if value.bit_length() > (remaining + 1) * 4:
            raise ValueError
        rendered = str(value)
        _phase_a_consume_bytes(budgets, len(rendered))
        return ("int", value)
    if type(value) is float:
        frozen = _freeze_exact_json(value)
        rendered = _SCHEMA_JSON_DUMPS(
            value,
            allow_nan=False,
            cls=_SCHEMA_JSON_ENCODER,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        if type(rendered) is not str:
            raise TypeError
        _phase_a_consume_bytes(budgets, len(rendered))
        return frozen
    if type(value) is str:
        _phase_a_consume_string(value, budgets)
        return ("str", value)
    if type(value) not in {dict, list}:
        raise TypeError
    stack = set() if active is None else active
    identity = id(value)
    if identity in stack:
        raise ValueError
    stack.add(identity)
    _phase_a_consume_bytes(budgets, 2)
    frozen_items: list[Any] = []
    try:
        if type(value) is dict:
            for index, key in enumerate(value):
                if type(key) is not str:
                    raise TypeError
                if index:
                    _phase_a_consume_bytes(budgets, 1)
                _phase_a_consume_string(key, budgets)
                _phase_a_consume_bytes(budgets, 1)
                frozen_items.append(
                    (
                        key,
                        _phase_a_freeze_json(
                            value[key],
                            budgets=budgets,
                            max_depth=max_depth,
                            depth=depth + 1,
                            active=stack,
                        ),
                    )
                )
            return ("dict", tuple(sorted(frozen_items)))
        for index, item in enumerate(value):
            if index:
                _phase_a_consume_bytes(budgets, 1)
            frozen_items.append(
                _phase_a_freeze_json(
                    item,
                    budgets=budgets,
                    max_depth=max_depth,
                    depth=depth + 1,
                    active=stack,
                )
            )
        return ("list", tuple(frozen_items))
    finally:
        stack.remove(identity)


def _phase_a_request_key(request: Any) -> tuple[Any, ...]:
    """Freeze exact JSON syntax before equality, normalization, or projection."""

    storage = _exact_storage(
        request,
        _REQUEST_TYPE,
        ("research_input", "loaded_history"),
    )
    source_input = storage["research_input"]
    if source_input is None:
        input_key: tuple[Any, ...] = ("absent",)
    else:
        if type(source_input) is not dict:
            raise TypeError
        if len(source_input) != 2:
            raise TypeError
        input_keys = tuple(source_input)
        if (
            any(type(key) is not str for key in input_keys)
            or tuple(sorted(input_keys)) != ("current_question", "observations")
            or type(source_input["current_question"]) is not str
            or type(source_input["observations"]) is not list
            or len(source_input["observations"]) > _MAX_OBSERVATIONS
        ):
            raise TypeError
        input_key = (
            "available",
            _phase_a_freeze_json(
                source_input,
                budgets=([_MAX_INPUT_BYTES],),
                max_depth=_MAX_INPUT_DEPTH,
            ),
        )

    history = storage["loaded_history"]
    if type(history) is _AVAILABLE_HISTORY_TYPE:
        history_storage = _exact_storage(history, _AVAILABLE_HISTORY_TYPE, ("records",))
        records = history_storage["records"]
        if type(records) is not tuple:
            raise TypeError
        if len(records) > _MAX_LOADED_HISTORY_RECORDS:
            raise ValueError
        frozen_records: list[tuple[Any, ...]] = []
        history_budget = [_MAX_BYTES]
        _phase_a_consume_bytes((history_budget,), 2)
        for index, record in enumerate(records):
            if type(record) is not dict:
                raise TypeError
            if index:
                _phase_a_consume_bytes((history_budget,), 1)
            record_budget = [_MAX_HISTORY_RECORD_BYTES]
            _phase_a_consume_bytes((record_budget,), 1)
            frozen_record = _phase_a_freeze_json(
                record,
                budgets=(record_budget, history_budget),
                max_depth=_MAX_HISTORY_DEPTH,
            )
            frozen_records.append(frozen_record)
        history_key: tuple[Any, ...] = ("available", tuple(frozen_records))
    elif type(history) is _UNAVAILABLE_HISTORY_TYPE:
        _exact_storage(history, _UNAVAILABLE_HISTORY_TYPE, ())
        history_key = ("unavailable",)
    else:
        raise TypeError
    return ("request", input_key, history_key)


def _normalize_request_input(
    raw_request_key: tuple[Any, ...],
) -> tuple[Any, ...] | None:
    if (
        type(raw_request_key) is not tuple
        or len(raw_request_key) != 3
        or raw_request_key[0] != "request"
    ):
        raise TypeError
    raw_input_key = raw_request_key[1]
    if type(raw_input_key) is not tuple or not raw_input_key:
        raise TypeError
    if raw_input_key[0] == "absent":
        if len(raw_input_key) != 1:
            raise TypeError
        return None
    if raw_input_key[0] != "available" or len(raw_input_key) != 2:
        raise ValueError
    raw_input = _thaw_frozen_json(raw_input_key[1])
    if type(raw_input) is not dict or tuple(sorted(raw_input)) != (
        "current_question",
        "observations",
    ):
        raise ValueError
    normalized_input = _NORMALIZE_RESEARCH_INPUT(raw_input)
    normalized_input_key = _freeze_exact_json(normalized_input)
    if not _same_frozen_json(normalized_input_key, raw_input_key[1]):
        raise ValueError
    return normalized_input_key


def _normalize_loaded_history(
    raw_request_key: tuple[Any, ...],
    *,
    problem_id: str,
    record_budget: int,
) -> Any:
    if (
        type(raw_request_key) is not tuple
        or len(raw_request_key) != 3
        or raw_request_key[0] != "request"
        or type(problem_id) is not str
        or type(record_budget) is not int
        or record_budget < 0
    ):
        raise TypeError
    raw_history_key = raw_request_key[2]
    if type(raw_history_key) is not tuple or not raw_history_key:
        raise TypeError
    if raw_history_key[0] == "unavailable":
        if len(raw_history_key) != 1:
            raise TypeError
        return _InitialScreeningFrozenLoadedHistoryUnavailable()
    if (
        raw_history_key[0] != "available"
        or len(raw_history_key) != 2
        or type(raw_history_key[1]) is not tuple
    ):
        raise ValueError
    normalized_records: list[tuple[Any, ...]] = []
    encoded_record_bytes = 2
    for index, raw_record_key in enumerate(raw_history_key[1]):
        raw_record = _thaw_frozen_json(raw_record_key)
        if type(raw_record) is not dict:
            raise TypeError
        normalized_record = _NORMALIZE_RESEARCH_HISTORY_RECORD(
            raw_record,
            expected_problem_id=problem_id,
        )
        normalized_key = _freeze_exact_json(normalized_record)
        if not _same_frozen_json(normalized_key, raw_record_key):
            raise ValueError
        detached_record = _thaw_frozen_json(normalized_key)
        if type(detached_record) is not dict:
            raise TypeError
        encoded_record_bytes += _CANONICAL_FRAGMENT_SIZE(
            detached_record,
            json_dumps=_SCHEMA_JSON_DUMPS,
            json_encoder=_SCHEMA_JSON_ENCODER,
        )
        if index:
            encoded_record_bytes += 1
        if encoded_record_bytes > record_budget:
            raise ValueError
        normalized_records.append(normalized_key)
    return _InitialScreeningFrozenLoadedHistoryAvailable(
        records=tuple(normalized_records)
    )


def _capture_provider_projection(
    normalized_input_key: tuple[Any, ...] | None,
    *,
    adapter: Any,
    adapter_projection_key: tuple[Any, ...],
    dependency_validator: Any,
    request: Any,
    raw_request_key: tuple[Any, ...],
    problem_inputs: Any,
    problem_before: tuple[Any, ...],
    adapter_factory: Any = _EXPECTED_ADAPTER_FACTORY,
    provider_project: Any = _EXPECTED_PROVIDER_PROJECT,
) -> tuple[Any, ...] | None:
    if normalized_input_key is None:
        return None
    normalized_input = _thaw_frozen_json(normalized_input_key)
    if type(normalized_input) is not dict:
        raise TypeError
    question = normalized_input.get("current_question")
    observations = normalized_input.get("observations")
    if type(question) is not str or type(observations) is not list:
        raise TypeError
    projected: list[dict[str, Any]] = []
    if observations:
        provider = adapter_factory(adapter)
        dependency_validator()
        _validate_after_projection(
            request=request,
            raw_request_key=raw_request_key,
            problem_inputs=problem_inputs,
            problem_before=problem_before,
            adapter=adapter,
            spec_v1=adapter_projection_key[2],
            adapter_projection_key=adapter_projection_key,
            dependency_validator=dependency_validator,
        )
        provider_key = _provider_projection_authority_key(provider)
        for observation in observations:
            if type(observation) is not dict:
                raise TypeError
            value = provider_project(provider, observation=observation)
            dependency_validator()
            _validate_after_projection(
                request=request,
                raw_request_key=raw_request_key,
                problem_inputs=problem_inputs,
                problem_before=problem_before,
                adapter=adapter,
                spec_v1=adapter_projection_key[2],
                adapter_projection_key=adapter_projection_key,
                dependency_validator=dependency_validator,
            )
            current_provider_key = _provider_projection_authority_key(provider)
            if not _same_identity_key(current_provider_key, provider_key):
                raise ValueError
            if value is None:
                continue
            value_key = _freeze_exact_json(value)
            detached = _thaw_frozen_json(value_key)
            if type(detached) is not dict:
                raise TypeError
            projected.append(detached)
    bounded = _NORMALIZE_RESEARCH_INPUT(
        {"current_question": question, "observations": projected}
    )
    if type(bounded) is not dict:
        raise TypeError
    return _freeze_exact_json(
        {
            "research_question": {"current_question": question},
            "prior_research_observations": bounded["observations"],
        }
    )


def _validate_after_projection(
    *,
    request: Any,
    raw_request_key: tuple[Any, ...],
    problem_inputs: Any,
    problem_before: tuple[Any, ...],
    adapter: Any,
    spec_v1: Any,
    adapter_projection_key: tuple[Any, ...],
    dependency_validator: Any,
) -> None:
    dependency_validator()
    if not _same_immutable_tree(_phase_a_request_key(request), raw_request_key):
        raise ValueError
    current_problem = _PROBLEM_INPUTS_PRISTINE_KEY(problem_inputs)
    if not _SAME_PROBLEM_FROZEN_KEY(current_problem, problem_before):
        raise ValueError
    if vars(problem_inputs).get("adapter") is not adapter:
        raise ValueError
    if not _same_identity_key(
        _adapter_projection_authority_key(adapter, spec_v1),
        adapter_projection_key,
    ):
        raise ValueError


def _validate_opt_in_markers(
    controls_request: Any,
    provider_request: Any,
    problem_request: Any,
) -> None:
    controls = _exact_storage(
        controls_request,
        _CONTROLS_REQUEST_TYPE,
        ("requested_rounds",),
    )
    requested_rounds = controls["requested_rounds"]
    if type(requested_rounds) is not int or requested_rounds <= 0:
        raise TypeError
    _exact_storage(provider_request, _PROVIDER_REQUEST_TYPE, ())
    _exact_storage(problem_request, _PROBLEM_REQUEST_TYPE, ())


def _adapter_projection_authority_key(
    adapter: Any,
    spec_v1: Any,
) -> tuple[Any, ...]:
    adapter_type = type(adapter)
    if adapter_type is not _EXPECTED_ADAPTER_TYPE or type(adapter_type) is not type:
        raise TypeError
    expected_mro = _EXPECTED_ADAPTER_CLASS_SURFACE[1]
    expected_name = _EXPECTED_ADAPTER_CLASS_SURFACE[2]
    expected_qualname = _EXPECTED_ADAPTER_CLASS_SURFACE[3]
    expected_module_name = _EXPECTED_ADAPTER_CLASS_SURFACE[4]
    expected_items = _EXPECTED_ADAPTER_CLASS_SURFACE[5]
    class_storage = vars(adapter_type)
    instance_storage = vars(adapter)
    mro = _TYPE_GETATTRIBUTE(adapter_type, "__mro__")
    name = _TYPE_GETATTRIBUTE(adapter_type, "__name__")
    qualname = _TYPE_GETATTRIBUTE(adapter_type, "__qualname__")
    module_name = _TYPE_GETATTRIBUTE(adapter_type, "__module__")
    if (
        type(class_storage) is not MappingProxyType
        or type(instance_storage) is not dict
        or any(type(key) is not str for key in instance_storage)
        or set(instance_storage) != {"_spec"}
        or instance_storage["_spec"] is not spec_v1
        or "prior_research_observation_provider" in instance_storage
        or type(mro) is not tuple
        or type(name) is not str
        or type(qualname) is not str
        or type(module_name) is not str
        or name != expected_name
        or qualname != expected_qualname
        or module_name != expected_module_name
        or len(mro) != len(expected_mro)
        or any(current is not expected for current, expected in zip(mro, expected_mro))
        or len(class_storage) != len(expected_items)
    ):
        raise TypeError
    for current, expected in zip(class_storage.items(), expected_items):
        if (
            type(current[0]) is not str
            or type(expected[0]) is not str
            or current[0] != expected[0]
            or current[1] is not expected[1]
        ):
            raise TypeError
    factory = class_storage.get("prior_research_observation_provider")
    module = sys.modules.get(expected_module_name)
    if (
        factory is not _EXPECTED_ADAPTER_FACTORY
        or type(module) is not ModuleType
        or vars(module).get(expected_name) is not adapter_type
    ):
        raise TypeError
    return (adapter, adapter_type, spec_v1, module, factory, *mro)


def _provider_projection_authority_key(provider: Any) -> tuple[Any, ...]:
    provider_type = type(provider)
    if provider_type is not _EXPECTED_PROVIDER_TYPE or type(provider_type) is not type:
        raise TypeError
    expected_mro = _EXPECTED_PROVIDER_CLASS_SURFACE[1]
    expected_name = _EXPECTED_PROVIDER_CLASS_SURFACE[2]
    expected_qualname = _EXPECTED_PROVIDER_CLASS_SURFACE[3]
    expected_module_name = _EXPECTED_PROVIDER_CLASS_SURFACE[4]
    expected_items = _EXPECTED_PROVIDER_CLASS_SURFACE[5]
    class_storage = vars(provider_type)
    instance_storage = vars(provider)
    mro = _TYPE_GETATTRIBUTE(provider_type, "__mro__")
    name = _TYPE_GETATTRIBUTE(provider_type, "__name__")
    qualname = _TYPE_GETATTRIBUTE(provider_type, "__qualname__")
    module_name = _TYPE_GETATTRIBUTE(provider_type, "__module__")
    if (
        type(class_storage) is not MappingProxyType
        or type(instance_storage) is not dict
        or len(instance_storage) != 0
        or type(mro) is not tuple
        or type(name) is not str
        or type(qualname) is not str
        or type(module_name) is not str
        or name != expected_name
        or qualname != expected_qualname
        or module_name != expected_module_name
        or len(mro) != len(expected_mro)
        or any(current is not expected for current, expected in zip(mro, expected_mro))
        or len(class_storage) != len(expected_items)
    ):
        raise TypeError
    for current, expected in zip(class_storage.items(), expected_items):
        if (
            type(current[0]) is not str
            or type(expected[0]) is not str
            or current[0] != expected[0]
            or current[1] is not expected[1]
        ):
            raise TypeError
    method = class_storage.get("project_prior_research_observation")
    module = sys.modules.get(expected_module_name)
    if (
        method is not _EXPECTED_PROVIDER_PROJECT
        or type(module) is not ModuleType
        or vars(module).get(expected_name) is not provider_type
    ):
        raise TypeError
    return (provider, provider_type, module, method, *mro)


def _same_identity_key(current: Any, expected: Any) -> bool:
    return (
        type(current) is tuple
        and type(expected) is tuple
        and len(current) == len(expected)
        and all(
            current_item is expected_item
            for current_item, expected_item in zip(current, expected)
        )
    )


_LOCAL_HELPER_NAMES = (
    "_phase_a_consume_bytes",
    "_phase_a_consume_string",
    "_phase_a_freeze_json",
    "_phase_a_request_key",
    "_normalize_request_input",
    "_normalize_loaded_history",
    "_capture_provider_projection",
    "_validate_after_projection",
    "_validate_opt_in_markers",
    "_adapter_projection_authority_key",
    "_provider_projection_authority_key",
    "_same_identity_key",
)
_LOCAL_HELPERS = tuple((name, globals()[name]) for name in _LOCAL_HELPER_NAMES)
_EXTERNAL_ALIASES = tuple((name, globals()[name]) for name in _COMPOSITION_EXPORT_NAMES)
_LOCAL_BUILTIN_NAMES = (
    "BaseException",
    "TypeError",
    "ValueError",
    "all",
    "any",
    "bool",
    "bytes",
    "dict",
    "enumerate",
    "globals",
    "int",
    "len",
    "list",
    "min",
    "set",
    "sorted",
    "str",
    "tuple",
    "type",
    "vars",
    "zip",
)


def _validate_composition_dependencies(
    external_validator: Any = _validate_composition_external_dependencies,
    exports: tuple[tuple[str, Any], ...] = _COMPOSITION_EXPORTS,
    external_aliases: tuple[tuple[str, Any], ...] = _EXTERNAL_ALIASES,
    local_helpers: tuple[tuple[str, Any], ...] = _LOCAL_HELPERS,
    builtin_names: tuple[str, ...] = _LOCAL_BUILTIN_NAMES,
    anchors_module_anchor: ModuleType = anchors_module,
    anchors_name: str = _ANCHORS_NAME,
    self_module: ModuleType = sys.modules[__name__],
    self_name: str = __name__,
    sys_module: ModuleType = sys,
    sys_modules: dict[str, Any] = sys.modules,
    module_type: Any = ModuleType,
    mapping_proxy_type: Any = MappingProxyType,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    len_fn: Any = len,
    zip_fn: Any = zip,
    tuple_type: Any = tuple,
    dict_type: Any = dict,
    str_type: Any = str,
    error_type: Any = TypeError,
) -> None:
    if any_fn(
        type_fn(module) is not module_type
        for module in (self_module, anchors_module_anchor, sys_module)
    ):
        raise error_type
    self_storage = vars_fn(self_module)
    anchor_storage = vars_fn(anchors_module_anchor)
    sys_storage = vars_fn(sys_module)
    if (
        type_fn(self_storage) is not dict_type
        or type_fn(anchor_storage) is not dict_type
        or type_fn(sys_storage) is not dict_type
        or any_fn(
            type_fn(key) is not str_type
            for storage in (self_storage, anchor_storage, sys_storage)
            for key in storage
        )
    ):
        raise error_type
    current_anchor_name = anchor_storage.get("__name__")
    current_self_name = self_storage.get("__name__")
    if (
        type_fn(self_name) is not str_type
        or type_fn(anchors_name) is not str_type
        or type_fn(current_anchor_name) is not str_type
        or type_fn(current_self_name) is not str_type
        or current_anchor_name != anchors_name
        or current_self_name != self_name
        or type_fn(sys_modules) is not dict_type
        or sys_storage.get("modules") is not sys_modules
        or sys_modules.get(self_name) is not self_module
        or sys_modules.get(anchors_name) is not anchors_module_anchor
        or self_storage.get("sys") is not sys_module
        or self_storage.get("ModuleType") is not module_type
        or self_storage.get("MappingProxyType") is not mapping_proxy_type
        or self_storage.get("anchors_module") is not anchors_module_anchor
        or self_storage.get("_ANCHORS_NAME") is not anchors_name
        or self_storage.get("_COMPOSITION_EXPORTS") is not exports
        or self_storage.get("_EXTERNAL_ALIASES") is not external_aliases
        or self_storage.get("_LOCAL_HELPERS") is not local_helpers
        or self_storage.get("_LOCAL_BUILTIN_NAMES") is not builtin_names
        or anchor_storage.get("_validate_composition_external_dependencies")
        is not external_validator
        or self_storage.get("_validate_composition_external_dependencies")
        is not external_validator
    ):
        raise error_type
    for value in (exports, external_aliases, local_helpers, builtin_names):
        if type_fn(value) is not tuple_type:
            raise error_type
    if len_fn(exports) != len_fn(external_aliases):
        raise error_type
    for exported, local in zip_fn(exports, external_aliases):
        if (
            type_fn(exported) is not tuple_type
            or type_fn(local) is not tuple_type
            or len_fn(exported) != 2
            or len_fn(local) != 2
            or type_fn(exported[0]) is not str_type
            or type_fn(local[0]) is not str_type
            or exported[0] != local[0]
            or exported[1] is not local[1]
            or anchor_storage.get(exported[0]) is not exported[1]
            or self_storage.get(local[0]) is not local[1]
        ):
            raise error_type
    for name, helper in local_helpers:
        if type_fn(name) is not str_type or self_storage.get(name) is not helper:
            raise error_type
    if any_fn(type_fn(name) is not str_type for name in builtin_names) or any_fn(
        name in self_storage for name in builtin_names
    ):
        raise error_type
    external_validator()


def _prepare_initial_screening_research_context_unchecked(
    request: Any,
    controls_request: Any,
    provider_request: Any,
    problem_request: Any,
    problem_inputs: Any,
    *,
    research_input: Any,
    research_history: Any,
    dependency_validator: Any = _validate_composition_dependencies,
    self_module: ModuleType = sys.modules[__name__],
    module_type: Any = ModuleType,
    type_fn: Any = type,
    vars_fn: Any = vars,
    dict_type: Any = dict,
    error_type: Any = TypeError,
) -> Any:
    if type_fn(self_module) is not module_type:
        raise error_type
    self_storage = vars_fn(self_module)
    if (
        type_fn(self_storage) is not dict_type
        or self_storage.get("_validate_composition_dependencies")
        is not dependency_validator
    ):
        raise error_type
    dependency_validator()
    raw_request_key = _phase_a_request_key(request)
    _validate_opt_in_markers(controls_request, provider_request, problem_request)
    if research_input is not None or type(research_history) is not tuple:
        raise TypeError
    if len(research_history) != 0:
        raise ValueError

    problem_storage = _exact_storage(
        problem_inputs,
        _PROBLEM_INPUTS_TYPE,
        (
            "spec_v1",
            "problem_spec",
            "adapter",
            "metric_specs",
            "objective_policy",
            "operator_execute_signature",
            "payload_bytes",
            "root_dir",
            "adapter_class_fingerprint",
            "frozen_value_key",
            "publication",
        ),
    )
    problem_before = _PROBLEM_INPUTS_PRISTINE_KEY(problem_inputs)
    spec_v1 = problem_storage["spec_v1"]
    spec_storage = vars(spec_v1)
    if type(spec_storage) is not dict or any(
        type(key) is not str for key in spec_storage
    ):
        raise TypeError
    problem_id = spec_storage.get("id")
    if type(problem_id) is not str:
        raise TypeError
    adapter = problem_storage["adapter"]
    adapter_projection_key = _adapter_projection_authority_key(adapter, spec_v1)

    normalized_input_key = _normalize_request_input(raw_request_key)
    projection_key = _capture_provider_projection(
        normalized_input_key,
        adapter=adapter,
        adapter_projection_key=adapter_projection_key,
        dependency_validator=dependency_validator,
        request=request,
        raw_request_key=raw_request_key,
        problem_inputs=problem_inputs,
        problem_before=problem_before,
    )
    normalized_input_union: dict[str, Any]
    if normalized_input_key is None:
        normalized_input_union = {"availability": "absent"}
    else:
        if projection_key is None:
            raise TypeError
        normalized_input = _thaw_frozen_json(normalized_input_key)
        provider_projection = _thaw_frozen_json(projection_key)
        if type(normalized_input) is not dict or type(provider_projection) is not dict:
            raise TypeError
        normalized_input_union = {
            "availability": "available",
            "normalized_input": normalized_input,
            "provider_projection": provider_projection,
        }
    record_budget = _LOADED_HISTORY_RECORD_BUDGET(
        problem_id=problem_id,
        normalized_input=normalized_input_union,
        max_bytes=_MAX_BYTES,
        json_dumps=_SCHEMA_JSON_DUMPS,
        json_encoder=_SCHEMA_JSON_ENCODER,
    )
    normalized_history = _normalize_loaded_history(
        raw_request_key,
        problem_id=problem_id,
        record_budget=record_budget,
    )
    _validate_after_projection(
        request=request,
        raw_request_key=raw_request_key,
        problem_inputs=problem_inputs,
        problem_before=problem_before,
        adapter=adapter,
        spec_v1=spec_v1,
        adapter_projection_key=adapter_projection_key,
        dependency_validator=dependency_validator,
    )

    request_snapshot = _InitialScreeningResearchContextRequestSnapshot(
        research_input=_clone_frozen_json(normalized_input_key),
        loaded_history=_clone_frozen_history(normalized_history),
    )
    capsule = _InitialScreeningResearchContextCapsule(
        generation=_GENERATION,
        problem_id=problem_id,
        research_input=_clone_frozen_json(normalized_input_key),
        provider_projection=_clone_frozen_json(projection_key),
        loaded_history=_clone_frozen_history(normalized_history),
    )
    payload_bytes = _CANONICAL_RESEARCH_CONTEXT_PAYLOAD(
        problem_id=problem_id,
        research_input=_capsule_research_input_union(capsule),
        loaded_history=_thaw_frozen_history(capsule.loaded_history),
    )
    _validate_after_projection(
        request=request,
        raw_request_key=raw_request_key,
        problem_inputs=problem_inputs,
        problem_before=problem_before,
        adapter=adapter,
        spec_v1=spec_v1,
        adapter_projection_key=adapter_projection_key,
        dependency_validator=dependency_validator,
    )
    result = _InitialScreeningResearchContextInputs(
        request_snapshot=request_snapshot,
        capsule=capsule,
        payload_bytes=payload_bytes,
    )
    _research_context_inputs_pristine_key(result)
    return result


def _prepare_initial_screening_research_context(
    request: Any,
    controls_request: Any,
    provider_request: Any,
    problem_request: Any,
    problem_inputs: Any,
    *,
    research_input: Any,
    research_history: Any,
    dependency_validator: Any = _validate_composition_dependencies,
    unchecked: Any = _prepare_initial_screening_research_context_unchecked,
    error_type: Any = _RESEARCH_CONTEXT_ERROR,
    error_token: str = _ERROR,
    self_module: ModuleType = sys.modules[__name__],
    module_type: Any = ModuleType,
    type_fn: Any = type,
    vars_fn: Any = vars,
    dict_type: Any = dict,
    base_exception: Any = BaseException,
) -> Any:
    """Freeze one opted-in request before any campaign-root side effect."""

    if request is None:
        return None
    failed = False
    result: Any = None
    try:
        if type_fn(self_module) is not module_type:
            raise error_type(error_token)
        self_storage = vars_fn(self_module)
        if (
            type_fn(self_storage) is not dict_type
            or self_storage.get("_validate_composition_dependencies")
            is not dependency_validator
            or self_storage.get("_prepare_initial_screening_research_context_unchecked")
            is not unchecked
        ):
            raise error_type(error_token)
        dependency_validator()
        result = unchecked(
            request,
            controls_request,
            provider_request,
            problem_request,
            problem_inputs,
            research_input=research_input,
            research_history=research_history,
        )
    except base_exception:
        failed = True
    if failed or result is None:
        raise error_type(error_token)
    return result


__all__ = []
