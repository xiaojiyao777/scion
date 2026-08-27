"""Import-time dependency anchors for the private research-context schema."""

from __future__ import annotations

import json
import math
import re
import sys
from collections.abc import Mapping
from types import ModuleType
from typing import Any

from scion.core import paths as paths_module
from scion.core import research_history as research_history_module
from scion.core import research_input as research_input_module
from scion.proposal.context_manager import (
    history_projection as history_projection_module,
)

_INPUT_FUNCTION_NAMES = (
    "normalize_research_input",
    "_copy_json_value",
    "is_sensitive_research_key",
)
_INPUT_LITERAL_NAMES = (
    "MAX_RESEARCH_OBSERVATIONS",
    "MAX_RESEARCH_INPUT_BYTES",
    "MAX_RESEARCH_INPUT_DEPTH",
    "_SENSITIVE_INPUT_KEY",
)
_HISTORY_FUNCTION_NAMES = (
    "normalize_research_history_record",
    "_mapping",
    "_token",
    "_normalize_hypothesis",
    "_normalize_patch",
    "_normalize_outcome",
    "_normalize_protocol",
    "_normalize_decision",
    "_validate_record_relationships",
    "_validate_hypothesis_record",
    "_validate_safe_value",
    "_validate_open_keys",
    "_render",
)
_HISTORY_LITERAL_NAMES = (
    "RESEARCH_HISTORY_SCHEMA",
    "MAX_RESEARCH_HISTORY_RECORDS",
    "MAX_RESEARCH_HISTORY_LINE_BYTES",
    "MAX_RESEARCH_HISTORY_DEPTH",
    "_TOP",
    "_TOKEN",
    "_HYPOTHESIS",
    "_PATCH_CHANGE",
    "_OUTCOME",
    "_OUTCOME_REQUIRED",
    "_HELD_OUT",
    "_CHECK",
    "_DECISION",
    "_FORBIDDEN_KEY",
    "_CANONICAL_CASE_FEEDBACK_SEED_FIELDS",
    "_CASE_FEEDBACK_PATH",
    "_OPEN_FORBIDDEN",
    "_OPEN_COMPONENTS",
)
_PROJECTION_FUNCTION_NAMES = (
    "normalize_proposal_screening_observation",
    "_composition",
    "_full",
    "_canonical_json",
    "_select",
    "screening_eval_stats",
    "_case_feedback",
    "_plain",
    "_drop_empty",
)
_PROJECTION_LITERAL_NAMES = (
    "_SCREENING_OBSERVATION_FIELDS",
    "_COMPOSITION_FIELDS",
    "_AGGREGATION_FIELDS",
    "_SCREENING_EVAL_STAT_FIELDS",
)
_INPUT_BUILTIN_NAMES = (
    "isinstance",
    "TypeError",
    "ValueError",
    "str",
    "list",
    "len",
    "enumerate",
    "dict",
    "bool",
    "int",
    "float",
    "type",
)
_HISTORY_BUILTIN_NAMES = (
    "ValueError",
    "len",
    "isinstance",
    "TypeError",
    "set",
    "any",
    "str",
    "dict",
    "frozenset",
    "list",
    "enumerate",
    "bool",
    "int",
    "float",
)
_PROJECTION_BUILTIN_NAMES = (
    "isinstance",
    "set",
    "ValueError",
    "TypeError",
    "str",
    "frozenset",
    "sorted",
    "repr",
    "list",
    "tuple",
)
_PATH_BUILTIN_NAMES = ("isinstance", "str", "ValueError", "any")

_INPUT_FUNCTIONS = tuple(
    (name, vars(research_input_module)[name]) for name in _INPUT_FUNCTION_NAMES
)
_INPUT_LITERALS = tuple(
    (name, vars(research_input_module)[name]) for name in _INPUT_LITERAL_NAMES
)
_HISTORY_FUNCTIONS = tuple(
    (name, vars(research_history_module)[name]) for name in _HISTORY_FUNCTION_NAMES
)
_HISTORY_LITERALS = tuple(
    (name, vars(research_history_module)[name]) for name in _HISTORY_LITERAL_NAMES
)
_PROJECTION_FUNCTIONS = tuple(
    (name, vars(history_projection_module)[name]) for name in _PROJECTION_FUNCTION_NAMES
)
_PROJECTION_LITERALS = tuple(
    (name, vars(history_projection_module)[name]) for name in _PROJECTION_LITERAL_NAMES
)
_INPUT_MAPPING = vars(research_input_module)["Mapping"]
_INPUT_JSON = vars(research_input_module)["json"]
_INPUT_MATH = vars(research_input_module)["math"]
_INPUT_RE = vars(research_input_module)["re"]
_HISTORY_MAPPING = vars(research_history_module)["Mapping"]
_HISTORY_JSON = vars(research_history_module)["json"]
_HISTORY_MATH = vars(research_history_module)["math"]
_HISTORY_RE = vars(research_history_module)["re"]
_HISTORY_EXECUTION_OUTCOME = vars(research_history_module)["ExecutionOutcome"]
_HISTORY_RELATIVE_PATH = vars(research_history_module)["normalize_relative_patch_path"]
_HISTORY_SENSITIVE_KEY = vars(research_history_module)["is_sensitive_research_key"]
_HISTORY_PROTOCOL_NORMALIZER = vars(history_projection_module)[
    "normalize_proposal_screening_observation"
]
_PROJECTION_MAPPING = vars(history_projection_module)["Mapping"]
_PROJECTION_JSON = vars(history_projection_module)["json"]
_PATH_PURE_POSIX = vars(paths_module)["PurePosixPath"]
_JSON_DUMPS = json.dumps
_MATH_ISFINITE = math.isfinite
_RE_SUB = re.sub
_PATTERN_TYPE = type(re.compile(""))
_SYS_MODULES = sys.modules
_HISTORY_PROJECTION_MODULE_NAME = history_projection_module.__name__
_DIRECT_ANCHORS = (
    _INPUT_MAPPING,
    _INPUT_JSON,
    _INPUT_MATH,
    _INPUT_RE,
    _HISTORY_MAPPING,
    _HISTORY_JSON,
    _HISTORY_MATH,
    _HISTORY_RE,
    _HISTORY_EXECUTION_OUTCOME,
    _HISTORY_RELATIVE_PATH,
    _HISTORY_SENSITIVE_KEY,
    _HISTORY_PROTOCOL_NORMALIZER,
    _PROJECTION_MAPPING,
    _PROJECTION_JSON,
    _PATH_PURE_POSIX,
    _JSON_DUMPS,
    _MATH_ISFINITE,
    _RE_SUB,
)


def _module_storage(
    value: Any,
    module_type: type[ModuleType] = ModuleType,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    dict_type: Any = dict,
    str_type: Any = str,
    error_type: Any = TypeError,
) -> dict[str, Any]:
    if type_fn(value) is not module_type:
        raise error_type
    storage = vars_fn(value)
    if type_fn(storage) is not dict_type or any_fn(
        type_fn(key) is not str_type for key in storage
    ):
        raise error_type
    return storage


def _validate_function_anchors(
    storage: dict[str, Any],
    anchors: tuple[tuple[str, Any], ...],
    type_fn: Any = type,
    len_fn: Any = len,
    tuple_type: Any = tuple,
    str_type: Any = str,
    error_type: Any = TypeError,
) -> None:
    if type_fn(anchors) is not tuple_type:
        raise error_type
    for item in anchors:
        if (
            type_fn(item) is not tuple_type
            or len_fn(item) != 2
            or type_fn(item[0]) is not str_type
            or storage.get(item[0]) is not item[1]
        ):
            raise error_type


def _validate_literal_anchors(
    storage: dict[str, Any],
    anchors: tuple[tuple[str, Any], ...],
    pattern_type: type[Any] = _PATTERN_TYPE,
    type_fn: Any = type,
    len_fn: Any = len,
    any_fn: Any = any,
    int_type: Any = int,
    str_type: Any = str,
    frozenset_type: Any = frozenset,
    tuple_type: Any = tuple,
    error_type: Any = TypeError,
) -> None:
    if type_fn(anchors) is not tuple_type:
        raise error_type
    for item in anchors:
        if (
            type_fn(item) is not tuple_type
            or len_fn(item) != 2
            or type_fn(item[0]) is not str_type
        ):
            raise error_type
        current = storage.get(item[0])
        expected = item[1]
        if type_fn(current) is not type_fn(expected):
            raise error_type
        if type_fn(expected) in {int_type, str_type}:
            if current != expected:
                raise error_type
            continue
        if type_fn(expected) in {frozenset_type, tuple_type}:
            collection: Any = current
            if (
                any_fn(type_fn(value) is not str_type for value in collection)
                or collection != expected
            ):
                raise error_type
            continue
        if type_fn(expected) is pattern_type and current is expected:
            continue
        raise error_type


def _validate_absent_names(
    storage: dict[str, Any],
    names: tuple[str, ...],
    type_fn: Any = type,
    any_fn: Any = any,
    tuple_type: Any = tuple,
    str_type: Any = str,
    error_type: Any = TypeError,
) -> None:
    if type_fn(names) is not tuple_type or any_fn(
        type_fn(name) is not str_type for name in names
    ):
        raise error_type
    if any_fn(name in storage for name in names):
        raise error_type


def _validate_research_context_schema_dependencies(
    input_module: ModuleType = research_input_module,
    history_module: ModuleType = research_history_module,
    history_projection: ModuleType = history_projection_module,
    path_module: ModuleType = paths_module,
    sys_module: ModuleType = sys,
    sys_modules: dict[str, Any] = _SYS_MODULES,
    history_projection_module_name: str = _HISTORY_PROJECTION_MODULE_NAME,
    input_functions: tuple[tuple[str, Any], ...] = _INPUT_FUNCTIONS,
    input_literals: tuple[tuple[str, Any], ...] = _INPUT_LITERALS,
    history_functions: tuple[tuple[str, Any], ...] = _HISTORY_FUNCTIONS,
    history_literals: tuple[tuple[str, Any], ...] = _HISTORY_LITERALS,
    projection_functions: tuple[tuple[str, Any], ...] = _PROJECTION_FUNCTIONS,
    projection_literals: tuple[tuple[str, Any], ...] = _PROJECTION_LITERALS,
    input_builtin_names: tuple[str, ...] = _INPUT_BUILTIN_NAMES,
    history_builtin_names: tuple[str, ...] = _HISTORY_BUILTIN_NAMES,
    projection_builtin_names: tuple[str, ...] = _PROJECTION_BUILTIN_NAMES,
    path_builtin_names: tuple[str, ...] = _PATH_BUILTIN_NAMES,
    direct_anchors: tuple[Any, ...] = _DIRECT_ANCHORS,
    module_storage_fn: Any = _module_storage,
    function_anchor_fn: Any = _validate_function_anchors,
    literal_anchor_fn: Any = _validate_literal_anchors,
    absent_names_fn: Any = _validate_absent_names,
    type_fn: Any = type,
    len_fn: Any = len,
    vars_fn: Any = vars,
    tuple_type: Any = tuple,
    str_type: Any = str,
    dict_type: Any = dict,
    int_type: Any = int,
    mapping_type_anchor: Any = Mapping,
    error_type: Any = TypeError,
) -> int:
    """Validate the finite loaded dependency surface and return the input cap."""

    if type_fn(direct_anchors) is not tuple_type or len_fn(direct_anchors) != 18:
        raise error_type
    (
        input_mapping,
        input_json,
        input_math,
        input_re,
        history_mapping,
        history_json,
        history_math,
        history_re,
        history_execution_outcome,
        history_relative_path,
        history_sensitive_key,
        history_protocol_normalizer,
        projection_mapping,
        projection_json,
        path_pure_posix,
        json_dumps,
        math_isfinite,
        re_sub,
    ) = direct_anchors
    input_storage = module_storage_fn(input_module)
    history_storage = module_storage_fn(history_module)
    projection_storage = module_storage_fn(history_projection)
    path_storage = module_storage_fn(path_module)
    sys_storage = module_storage_fn(sys_module)
    function_anchor_fn(input_storage, input_functions)
    literal_anchor_fn(input_storage, input_literals)
    function_anchor_fn(history_storage, history_functions)
    literal_anchor_fn(history_storage, history_literals)
    function_anchor_fn(projection_storage, projection_functions)
    literal_anchor_fn(projection_storage, projection_literals)
    absent_names_fn(input_storage, input_builtin_names)
    absent_names_fn(history_storage, history_builtin_names)
    absent_names_fn(projection_storage, projection_builtin_names)
    absent_names_fn(path_storage, path_builtin_names)
    current_projection_name = projection_storage.get("__name__")
    if (
        type_fn(sys_modules) is not dict_type
        or type_fn(history_projection_module_name) is not str_type
        or type_fn(current_projection_name) is not str_type
        or sys_storage.get("modules") is not sys_modules
        or current_projection_name != history_projection_module_name
        or sys_modules.get(history_projection_module_name) is not history_projection
    ):
        raise error_type
    if (
        input_storage.get("Mapping") is not input_mapping
        or input_storage.get("json") is not input_json
        or input_storage.get("math") is not input_math
        or input_storage.get("re") is not input_re
        or history_storage.get("Mapping") is not history_mapping
        or history_storage.get("json") is not history_json
        or history_storage.get("math") is not history_math
        or history_storage.get("re") is not history_re
        or history_storage.get("ExecutionOutcome") is not history_execution_outcome
        or history_storage.get("normalize_relative_patch_path")
        is not history_relative_path
        or history_storage.get("is_sensitive_research_key") is not history_sensitive_key
        or projection_storage.get("normalize_proposal_screening_observation")
        is not history_protocol_normalizer
        or projection_storage.get("Mapping") is not projection_mapping
        or projection_storage.get("json") is not projection_json
        or path_storage.get("PurePosixPath") is not path_pure_posix
        or vars_fn(input_json).get("dumps") is not json_dumps
        or vars_fn(history_json).get("dumps") is not json_dumps
        or vars_fn(projection_json).get("dumps") is not json_dumps
        or vars_fn(input_math).get("isfinite") is not math_isfinite
        or vars_fn(history_math).get("isfinite") is not math_isfinite
        or vars_fn(input_re).get("sub") is not re_sub
        or vars_fn(history_re).get("sub") is not re_sub
        or input_mapping is not mapping_type_anchor
        or history_mapping is not mapping_type_anchor
    ):
        raise error_type
    cap = input_storage.get("MAX_RESEARCH_OBSERVATIONS")
    if type_fn(cap) is not int_type:
        raise error_type
    return cap


__all__ = []
