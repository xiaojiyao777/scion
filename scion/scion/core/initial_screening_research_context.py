"""Private producer schema for one initial-screening research context."""

from __future__ import annotations

import json
import math
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from json import encoder as json_encoder_module
from types import MappingProxyType, ModuleType
from typing import Any

from scion.core import (
    initial_screening_research_context_anchors as research_context_anchors,
)
from scion.core import research_history as research_history_module
from scion.core import research_input as research_input_module

_ERROR = "INITIAL_SCREENING_RESEARCH_CONTEXT_UNAVAILABLE"
_FILENAME = "initial_screening_research_context.json"
_MAX_BYTES = 64 << 20
_MAX_JSON_DEPTH = 27
_MAX_LOADED_HISTORY_RECORDS = 256
_SCHEMA_VERSION = "scion.initial_screening_research_context.declaration.v1"
_SCOPE = "RESEARCH_CONTEXT_DECLARATION_ONLY"
_HISTORY_UNAVAILABLE_REASON = "HISTORY_REPLAY_BASIS_UNAVAILABLE"
_LIMITATIONS = (
    "PROBLEM_ADAPTER_UNVERIFIED",
    "RESEARCH_INPUT_UNVERIFIED",
    "RUNTIME_RESEARCH_HISTORY_CONSUMPTION_UNVERIFIED",
    "VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED",
    "SOURCE_CARRIER_UNVERIFIED",
    "B0_CONTENT_UNVERIFIED",
    "STUDY_MANIFEST_UNVERIFIED",
    "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
    "MATCHED_RESULT_UNAUTHORIZED",
    "LIVE_EXECUTION_UNAUTHORIZED",
    "STUDY_GO_UNAUTHORIZED",
)
_PROBLEM_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
_JSON_ENCODER = json.JSONEncoder
_JSON_ENCODER_CLASS_SURFACE = tuple(vars(_JSON_ENCODER).items())
_JSON_ENCODER_GLOBAL_NAMES = (
    "encode_basestring",
    "encode_basestring_ascii",
    "c_make_encoder",
    "_make_iterencode",
    "INFINITY",
)
_JSON_ENCODER_GLOBALS = tuple(
    (name, vars(json_encoder_module)[name]) for name in _JSON_ENCODER_GLOBAL_NAMES
)
_JSON_ENCODER_BUILTIN_NAMES = (
    "isinstance",
    "list",
    "str",
    "tuple",
    "float",
    "repr",
    "ValueError",
    "TypeError",
    "sorted",
)
_NORMALIZE_RESEARCH_INPUT = research_input_module.normalize_research_input
_NORMALIZE_RESEARCH_HISTORY_RECORD = (
    research_history_module.normalize_research_history_record
)
_VALIDATE_SCHEMA_DEPENDENCIES = (
    research_context_anchors._validate_research_context_schema_dependencies
)


class _Redacted:
    """Marker base for carriers with fixed, body-free representations."""


@dataclass(frozen=True, repr=False)
class _InitialScreeningLoadedHistoryAvailable(_Redacted):
    """Typed declaration that the ordered loaded-history basis is available."""

    records: tuple[Mapping[str, Any], ...]

    def __repr__(self) -> str:
        return "_InitialScreeningLoadedHistoryAvailable(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _InitialScreeningLoadedHistoryUnavailable(_Redacted):
    """Typed declaration that replay history is unavailable."""

    def __repr__(self) -> str:
        return "_InitialScreeningLoadedHistoryUnavailable(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _InitialScreeningResearchContextRequest(_Redacted):
    """Package-private research-input and loaded-history declaration request."""

    research_input: Mapping[str, Any] | None
    loaded_history: (
        _InitialScreeningLoadedHistoryAvailable
        | _InitialScreeningLoadedHistoryUnavailable
    )

    def __repr__(self) -> str:
        return "_InitialScreeningResearchContextRequest(<redacted>)"

    __str__ = __repr__


class _InitialScreeningResearchContextError(RuntimeError):
    """Fixed body-free error at the private research-context boundary."""


def _canonical_research_context_payload_impl(
    *,
    problem_id: Any,
    research_input: Any,
    loaded_history: Any,
) -> bytes:
    """Return one exact detached research-context declaration."""

    max_bytes, json_dumps, json_encoder = _validate_schema_anchors()
    observation_cap = _validate_dependency_anchors()
    normalized_problem_id = _normalize_problem_id(problem_id)
    normalized_input = _normalize_research_input_union(
        research_input,
        observation_cap=observation_cap,
    )
    record_budget = _loaded_history_record_budget(
        problem_id=normalized_problem_id,
        normalized_input=normalized_input,
        max_bytes=max_bytes,
        json_dumps=json_dumps,
        json_encoder=json_encoder,
    )
    normalized_history = _normalize_loaded_history_union(
        loaded_history,
        problem_id=normalized_problem_id,
        record_budget=record_budget,
        json_dumps=json_dumps,
        json_encoder=json_encoder,
    )
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "scope": _SCOPE,
        "limitations": list(_LIMITATIONS),
        "problem_id": normalized_problem_id,
        "research_input": normalized_input,
        "loaded_history": normalized_history,
    }
    _validate_json_value(payload, path="$", depth=0)
    try:
        encoded = (
            json_dumps(
                payload,
                allow_nan=False,
                cls=json_encoder,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
    except (OverflowError, TypeError, UnicodeEncodeError, ValueError) as error:
        raise TypeError from error
    if len(encoded) > max_bytes:
        raise ValueError
    return encoded


def _normalize_problem_id(value: Any) -> str:
    if type(value) is not str or _PROBLEM_ID.fullmatch(value) is None:
        raise ValueError
    return value


def _normalize_research_input_union(
    value: Any,
    *,
    observation_cap: int,
) -> dict[str, Any]:
    source = _exact_mapping(value)
    availability = source.get("availability")
    if type(availability) is not str:
        raise TypeError
    if availability == "absent":
        if set(source) != {"availability"}:
            raise ValueError
        return {"availability": "absent"}
    if availability != "available" or set(source) != {
        "availability",
        "normalized_input",
        "provider_projection",
    }:
        raise ValueError
    normalized_input = _normalize_exact_research_input(
        source["normalized_input"],
        observation_cap=observation_cap,
    )
    projection = _normalize_provider_projection(
        source["provider_projection"],
        current_question=normalized_input["current_question"],
        observation_cap=observation_cap,
    )
    return {
        "availability": "available",
        "normalized_input": normalized_input,
        "provider_projection": projection,
    }


def _normalize_exact_research_input(
    value: Any,
    *,
    observation_cap: int,
) -> dict[str, Any]:
    source = _exact_mapping(value)
    if set(source) != {"current_question", "observations"}:
        raise ValueError
    question = source["current_question"]
    observations = source["observations"]
    if type(question) is not str or not question.strip():
        raise ValueError
    if type(observations) is not list:
        raise TypeError
    if len(observations) > observation_cap:
        raise ValueError
    _validate_json_value(value, path="$.research_input.normalized_input", depth=2)
    normalized = _NORMALIZE_RESEARCH_INPUT(source)
    _validate_json_value(normalized, path="$.research_input.normalized_input", depth=2)
    if _freeze_json(normalized) != _freeze_json(source):
        raise ValueError
    return normalized


def _normalize_provider_projection(
    value: Any,
    *,
    current_question: str,
    observation_cap: int,
) -> dict[str, Any]:
    source = _exact_mapping(value)
    if set(source) != {"research_question", "prior_research_observations"}:
        raise ValueError
    question = _exact_mapping(source["research_question"])
    if (
        set(question) != {"current_question"}
        or type(question["current_question"]) is not str
        or question["current_question"] != current_question
    ):
        raise ValueError
    observations = source["prior_research_observations"]
    if type(observations) is not list:
        raise TypeError
    if len(observations) > observation_cap:
        raise ValueError
    _validate_json_value(value, path="$.research_input.provider_projection", depth=2)
    bounded = _NORMALIZE_RESEARCH_INPUT(
        {
            "current_question": current_question,
            "observations": observations,
        }
    )
    if _freeze_json(bounded["observations"]) != _freeze_json(observations):
        raise ValueError
    return {
        "research_question": {"current_question": current_question},
        "prior_research_observations": bounded["observations"],
    }


def _normalize_loaded_history_union(
    value: Any,
    *,
    problem_id: str,
    record_budget: int,
    json_dumps: Any,
    json_encoder: Any,
) -> dict[str, Any]:
    source = _exact_mapping(value)
    availability = source.get("availability")
    if type(availability) is not str:
        raise TypeError
    if availability == "unavailable":
        if set(source) != {"availability", "reason"}:
            raise ValueError
        reason = source.get("reason")
        if type(reason) is not str:
            raise TypeError
        if reason != _HISTORY_UNAVAILABLE_REASON:
            raise ValueError
        return {
            "availability": "unavailable",
            "reason": _HISTORY_UNAVAILABLE_REASON,
        }
    if availability != "available" or set(source) != {"availability", "records"}:
        raise ValueError
    records = source["records"]
    if type(records) is not list:
        raise TypeError
    if len(records) > _MAX_LOADED_HISTORY_RECORDS:
        raise ValueError
    normalized_records: list[dict[str, Any]] = []
    encoded_record_bytes = 2
    for index, record in enumerate(records):
        _validate_json_value(
            record,
            path=f"$.loaded_history.records[{index}]",
            depth=2,
        )
        normalized = _NORMALIZE_RESEARCH_HISTORY_RECORD(
            record,
            expected_problem_id=problem_id,
        )
        if _freeze_json(normalized) != _freeze_json(record):
            raise ValueError
        encoded_record_bytes += _canonical_fragment_size(
            normalized,
            json_dumps=json_dumps,
            json_encoder=json_encoder,
        )
        if index:
            encoded_record_bytes += 1
        if encoded_record_bytes > record_budget:
            raise ValueError
        normalized_records.append(normalized)
    return {"availability": "available", "records": normalized_records}


def _validate_dependency_anchors(
    input_anchor: Any = _NORMALIZE_RESEARCH_INPUT,
    history_anchor: Any = _NORMALIZE_RESEARCH_HISTORY_RECORD,
    dependency_anchor: Any = _VALIDATE_SCHEMA_DEPENDENCIES,
    anchors_module_anchor: Any = research_context_anchors,
    history_module_anchor: Any = research_history_module,
    input_module_anchor: Any = research_input_module,
    module_type_anchor: Any = ModuleType,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    dict_type_anchor: Any = dict,
    str_type_anchor: Any = str,
    int_type_anchor: Any = int,
    error_type: Any = TypeError,
) -> int:
    if (
        type_fn(research_context_anchors) is not module_type_anchor
        or type_fn(research_history_module) is not module_type_anchor
        or type_fn(research_input_module) is not module_type_anchor
        or research_context_anchors is not anchors_module_anchor
        or research_history_module is not history_module_anchor
        or research_input_module is not input_module_anchor
    ):
        raise error_type
    anchors_storage = vars_fn(anchors_module_anchor)
    history_storage = vars_fn(history_module_anchor)
    input_storage = vars_fn(input_module_anchor)
    if any_fn(
        type_fn(storage) is not dict_type_anchor
        or any_fn(type_fn(key) is not str_type_anchor for key in storage)
        for storage in (anchors_storage, history_storage, input_storage)
    ):
        raise error_type
    if (
        _VALIDATE_SCHEMA_DEPENDENCIES is not dependency_anchor
        or anchors_storage.get("_validate_research_context_schema_dependencies")
        is not dependency_anchor
    ):
        raise error_type
    observation_cap = dependency_anchor()
    record_cap = history_storage.get("MAX_RESEARCH_HISTORY_RECORDS")
    if (
        _NORMALIZE_RESEARCH_INPUT is not input_anchor
        or input_storage.get("normalize_research_input") is not input_anchor
        or _NORMALIZE_RESEARCH_HISTORY_RECORD is not history_anchor
        or history_storage.get("normalize_research_history_record")
        is not history_anchor
        or type_fn(record_cap) is not int_type_anchor
        or record_cap != _MAX_LOADED_HISTORY_RECORDS
        or type_fn(observation_cap) is not int_type_anchor
        or observation_cap != 64
    ):
        raise error_type
    return observation_cap


def _canonical_fragment_size(
    value: dict[str, Any],
    *,
    json_dumps: Any,
    json_encoder: Any,
) -> int:
    try:
        return len(
            json_dumps(
                value,
                allow_nan=False,
                cls=json_encoder,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
    except (OverflowError, TypeError, UnicodeEncodeError, ValueError) as error:
        raise TypeError from error


def _loaded_history_record_budget(
    *,
    problem_id: str,
    normalized_input: dict[str, Any],
    max_bytes: int,
    json_dumps: Any,
    json_encoder: Any,
) -> int:
    empty_payload = {
        "schema_version": _SCHEMA_VERSION,
        "scope": _SCOPE,
        "limitations": list(_LIMITATIONS),
        "problem_id": problem_id,
        "research_input": normalized_input,
        "loaded_history": {"availability": "available", "records": []},
    }
    empty_size = (
        _canonical_fragment_size(
            empty_payload,
            json_dumps=json_dumps,
            json_encoder=json_encoder,
        )
        + 1
    )
    if empty_size > max_bytes:
        raise ValueError
    return max_bytes - empty_size + 2


def _validate_json_encoder_anchors(
    json_module_anchor: Any = json,
    encoder_module_anchor: Any = json_encoder_module,
    encoder_class_anchor: Any = _JSON_ENCODER,
    class_surface_anchor: tuple[tuple[str, Any], ...] = _JSON_ENCODER_CLASS_SURFACE,
    global_surface_anchor: tuple[tuple[str, Any], ...] = _JSON_ENCODER_GLOBALS,
    builtin_names_anchor: tuple[str, ...] = _JSON_ENCODER_BUILTIN_NAMES,
    module_type_anchor: Any = ModuleType,
    mapping_proxy_type_anchor: Any = MappingProxyType,
    class_type_anchor: Any = type,
    type_fn: Any = type,
    vars_fn: Any = vars,
    len_fn: Any = len,
    any_fn: Any = any,
    zip_fn: Any = zip,
    tuple_type_anchor: Any = tuple,
    dict_type_anchor: Any = dict,
    str_type_anchor: Any = str,
    error_type: Any = TypeError,
) -> Any:
    if (
        type_fn(json_module_anchor) is not module_type_anchor
        or type_fn(encoder_module_anchor) is not module_type_anchor
        or type_fn(encoder_class_anchor) is not class_type_anchor
        or type_fn(class_surface_anchor) is not tuple_type_anchor
        or type_fn(global_surface_anchor) is not tuple_type_anchor
        or type_fn(builtin_names_anchor) is not tuple_type_anchor
    ):
        raise error_type
    json_storage = vars_fn(json_module_anchor)
    encoder_storage = vars_fn(encoder_module_anchor)
    class_storage = vars_fn(encoder_class_anchor)
    if (
        type_fn(json_storage) is not dict_type_anchor
        or type_fn(encoder_storage) is not dict_type_anchor
        or type_fn(class_storage) is not mapping_proxy_type_anchor
        or any_fn(
            type_fn(key) is not str_type_anchor
            for storage in (json_storage, encoder_storage, class_storage)
            for key in storage
        )
        or json_storage.get("JSONEncoder") is not encoder_class_anchor
        or json_storage.get("encoder") is not encoder_module_anchor
    ):
        raise error_type
    if len_fn(class_storage) != len_fn(class_surface_anchor):
        raise error_type
    for current, expected in zip_fn(class_storage.items(), class_surface_anchor):
        if (
            type_fn(expected) is not tuple_type_anchor
            or len_fn(expected) != 2
            or type_fn(expected[0]) is not str_type_anchor
            or current[0] != expected[0]
            or current[1] is not expected[1]
        ):
            raise error_type
    for item in global_surface_anchor:
        if (
            type_fn(item) is not tuple_type_anchor
            or len_fn(item) != 2
            or type_fn(item[0]) is not str_type_anchor
            or encoder_storage.get(item[0]) is not item[1]
        ):
            raise error_type
    if any_fn(
        type_fn(name) is not str_type_anchor for name in builtin_names_anchor
    ) or any_fn(name in encoder_storage for name in builtin_names_anchor):
        raise error_type
    return encoder_class_anchor


def _validate_schema_anchors(
    error_anchor: Any = _ERROR,
    filename_anchor: Any = _FILENAME,
    max_bytes_anchor: Any = _MAX_BYTES,
    max_depth_anchor: Any = _MAX_JSON_DEPTH,
    max_records_anchor: Any = _MAX_LOADED_HISTORY_RECORDS,
    schema_anchor: Any = _SCHEMA_VERSION,
    scope_anchor: Any = _SCOPE,
    history_reason_anchor: Any = _HISTORY_UNAVAILABLE_REASON,
    limitations_anchor: Any = _LIMITATIONS,
    problem_id_anchor: Any = _PROBLEM_ID,
    json_anchor: Any = json,
    json_dumps_anchor: Any = json.dumps,
    math_anchor: Any = math,
    math_isfinite_anchor: Any = math.isfinite,
    re_anchor: Any = re,
    pattern_type_anchor: Any = re.Pattern,
    anchors_module_anchor: Any = research_context_anchors,
    history_module_anchor: Any = research_history_module,
    input_module_anchor: Any = research_input_module,
    json_encoder_validator: Any = _validate_json_encoder_anchors,
    module_type_anchor: Any = ModuleType,
    type_fn: Any = type,
    vars_fn: Any = vars,
    error_type: Any = TypeError,
) -> tuple[int, Any, Any]:
    if (
        type_fn(json) is not module_type_anchor
        or type_fn(math) is not module_type_anchor
        or type_fn(re) is not module_type_anchor
        or type_fn(research_context_anchors) is not module_type_anchor
        or type_fn(research_history_module) is not module_type_anchor
        or type_fn(research_input_module) is not module_type_anchor
        or type_fn(_ERROR) is not type_fn(error_anchor)
        or type_fn(_FILENAME) is not type_fn(filename_anchor)
        or type_fn(_MAX_BYTES) is not type_fn(max_bytes_anchor)
        or type_fn(_MAX_JSON_DEPTH) is not type_fn(max_depth_anchor)
        or type_fn(_MAX_LOADED_HISTORY_RECORDS) is not type_fn(max_records_anchor)
        or type_fn(_SCHEMA_VERSION) is not type_fn(schema_anchor)
        or type_fn(_SCOPE) is not type_fn(scope_anchor)
        or type_fn(_HISTORY_UNAVAILABLE_REASON) is not type_fn(history_reason_anchor)
        or type_fn(_LIMITATIONS) is not type_fn(limitations_anchor)
        or type_fn(_PROBLEM_ID) is not pattern_type_anchor
    ):
        raise error_type
    if (
        json is not json_anchor
        or vars_fn(json).get("dumps") is not json_dumps_anchor
        or math is not math_anchor
        or vars_fn(math).get("isfinite") is not math_isfinite_anchor
        or re is not re_anchor
        or vars_fn(re).get("Pattern") is not pattern_type_anchor
        or research_context_anchors is not anchors_module_anchor
        or research_history_module is not history_module_anchor
        or research_input_module is not input_module_anchor
        or _ERROR is not error_anchor
        or _FILENAME is not filename_anchor
        or _MAX_BYTES != max_bytes_anchor
        or _MAX_JSON_DEPTH != max_depth_anchor
        or _MAX_LOADED_HISTORY_RECORDS != max_records_anchor
        or _SCHEMA_VERSION is not schema_anchor
        or _SCOPE is not scope_anchor
        or _HISTORY_UNAVAILABLE_REASON is not history_reason_anchor
        or _LIMITATIONS is not limitations_anchor
        or _PROBLEM_ID is not problem_id_anchor
    ):
        raise error_type
    json_encoder = json_encoder_validator()
    return max_bytes_anchor, json_dumps_anchor, json_encoder


def _exact_mapping(value: Any) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise TypeError
    return value


def _validate_json_value(value: Any, *, path: str, depth: int) -> None:
    if depth > _MAX_JSON_DEPTH:
        raise ValueError
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError
        return
    if type(value) is list:
        for index, child in enumerate(value):
            _validate_json_value(child, path=f"{path}[{index}]", depth=depth + 1)
        return
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise TypeError
            _validate_json_value(child, path=f"{path}.{key}", depth=depth + 1)
        return
    raise TypeError


def _freeze_json(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ("null",)
    if type(value) is bool:
        return ("bool", value)
    if type(value) is int:
        return ("int", value)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError
        return ("float", value.hex())
    if type(value) is str:
        return ("str", value)
    if type(value) is list:
        return ("list", tuple(_freeze_json(item) for item in value))
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError
        return (
            "dict",
            tuple((key, _freeze_json(value[key])) for key in sorted(value)),
        )
    raise TypeError


_LOCAL_HELPER_ANCHORS = (
    (
        "_canonical_research_context_payload_impl",
        _canonical_research_context_payload_impl,
    ),
    ("_validate_json_encoder_anchors", _validate_json_encoder_anchors),
    ("_validate_schema_anchors", _validate_schema_anchors),
    ("_validate_dependency_anchors", _validate_dependency_anchors),
    ("_normalize_problem_id", _normalize_problem_id),
    ("_normalize_research_input_union", _normalize_research_input_union),
    ("_normalize_exact_research_input", _normalize_exact_research_input),
    ("_normalize_provider_projection", _normalize_provider_projection),
    ("_normalize_loaded_history_union", _normalize_loaded_history_union),
    ("_canonical_fragment_size", _canonical_fragment_size),
    ("_loaded_history_record_budget", _loaded_history_record_budget),
    ("_exact_mapping", _exact_mapping),
    ("_validate_json_value", _validate_json_value),
    ("_freeze_json", _freeze_json),
)
_LOCAL_BUILTIN_NAMES = (
    "OverflowError",
    "TypeError",
    "UnicodeEncodeError",
    "ValueError",
    "any",
    "bool",
    "dict",
    "enumerate",
    "float",
    "int",
    "len",
    "list",
    "set",
    "sorted",
    "str",
    "tuple",
    "type",
)
_THIS_MODULE = sys.modules[__name__]


def _canonical_research_context_payload(
    *,
    problem_id: Any,
    research_input: Any,
    loaded_history: Any,
    implementation_anchor: Any = _canonical_research_context_payload_impl,
    helper_anchors: tuple[tuple[str, Any], ...] = _LOCAL_HELPER_ANCHORS,
    builtin_names: tuple[str, ...] = _LOCAL_BUILTIN_NAMES,
    module_anchor: ModuleType = _THIS_MODULE,
    module_type_anchor: Any = ModuleType,
    type_anchor: Any = type,
    vars_anchor: Any = vars,
    len_anchor: Any = len,
    any_anchor: Any = any,
    tuple_type_anchor: Any = tuple,
    dict_type_anchor: Any = dict,
    str_type_anchor: Any = str,
    error_type: Any = TypeError,
) -> bytes:
    """Validate the loaded local surface, then build one exact declaration."""

    if type_anchor(module_anchor) is not module_type_anchor:
        raise error_type
    storage = vars_anchor(module_anchor)
    if (
        type_anchor(storage) is not dict_type_anchor
        or type_anchor(helper_anchors) is not tuple_type_anchor
        or type_anchor(builtin_names) is not tuple_type_anchor
        or any_anchor(
            type_anchor(name) is not str_type_anchor for name in builtin_names
        )
        or any_anchor(name in storage for name in builtin_names)
    ):
        raise error_type
    for item in helper_anchors:
        if (
            type_anchor(item) is not tuple_type_anchor
            or len_anchor(item) != 2
            or type_anchor(item[0]) is not str_type_anchor
            or storage.get(item[0]) is not item[1]
        ):
            raise error_type
    if implementation_anchor is not _canonical_research_context_payload_impl:
        raise error_type
    return implementation_anchor(
        problem_id=problem_id,
        research_input=research_input,
        loaded_history=loaded_history,
    )


__all__ = []
