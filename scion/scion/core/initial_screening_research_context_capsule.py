from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import Any

import scion.core.initial_screening_research_context  # noqa: F401

_RESEARCH_MODULE_NAME = "scion.core.initial_screening_research_context"
if type(sys.modules) is not dict:
    raise TypeError
research_context_module = sys.modules.get(_RESEARCH_MODULE_NAME)
if type(research_context_module) is not ModuleType:
    raise TypeError
_research_storage = vars(research_context_module)
if type(_research_storage) is not dict or any(
    type(key) is not str for key in _research_storage
):
    raise TypeError
_current_research_name = _research_storage.get("__name__")
if (
    type(_current_research_name) is not str
    or _current_research_name != _RESEARCH_MODULE_NAME
):
    raise TypeError
_MAX_JSON_DEPTH = _research_storage["_MAX_JSON_DEPTH"]
_MAX_LOADED_HISTORY_RECORDS = _research_storage["_MAX_LOADED_HISTORY_RECORDS"]
_HISTORY_UNAVAILABLE_REASON = _research_storage["_HISTORY_UNAVAILABLE_REASON"]
_CANONICAL_RESEARCH_CONTEXT_PAYLOAD = _research_storage[
    "_canonical_research_context_payload"
]
_VALIDATE_SCHEMA_ANCHORS = _research_storage["_validate_schema_anchors"]
_VALIDATE_SCHEMA_DEPENDENCIES = _research_storage["_validate_dependency_anchors"]
_MATH_ISFINITE = math.isfinite
_TYPE_GETATTRIBUTE = type.__getattribute__
_OBJECT_GETATTRIBUTE = object.__getattribute__
_GENERATION = 1


class _Redacted:
    def __repr__(self) -> str:
        return "_Redacted(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _InitialScreeningFrozenLoadedHistoryAvailable(_Redacted):
    records: tuple[tuple[Any, ...], ...]

    def __repr__(self) -> str:
        return "_InitialScreeningFrozenLoadedHistoryAvailable(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _InitialScreeningFrozenLoadedHistoryUnavailable(_Redacted):
    def __repr__(self) -> str:
        return "_InitialScreeningFrozenLoadedHistoryUnavailable(<redacted>)"

    __str__ = __repr__


_FrozenLoadedHistory = _InitialScreeningFrozenLoadedHistoryAvailable | _InitialScreeningFrozenLoadedHistoryUnavailable  # fmt: skip


@dataclass(frozen=True, repr=False)
class _InitialScreeningResearchContextRequestSnapshot(_Redacted):
    research_input: tuple[Any, ...] | None
    loaded_history: _FrozenLoadedHistory

    def __repr__(self) -> str:
        return "_InitialScreeningResearchContextRequestSnapshot(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _InitialScreeningResearchContextCapsule(_Redacted):
    generation: int
    problem_id: str
    research_input: tuple[Any, ...] | None
    provider_projection: tuple[Any, ...] | None
    loaded_history: _FrozenLoadedHistory

    def __repr__(self) -> str:
        return "_InitialScreeningResearchContextCapsule(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _InitialScreeningResearchContextPublication(_Redacted):
    campaign_dir: str
    directory_fingerprints: tuple[tuple[int, int], ...]
    leaf_fingerprint: tuple[int, int, int, int]

    def __repr__(self) -> str:
        return "_InitialScreeningResearchContextPublication(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _InitialScreeningResearchContextInputs(_Redacted):
    request_snapshot: _InitialScreeningResearchContextRequestSnapshot
    capsule: _InitialScreeningResearchContextCapsule
    payload_bytes: bytes
    publication: _InitialScreeningResearchContextPublication | None = None

    def __repr__(self) -> str:
        return "_InitialScreeningResearchContextInputs(<redacted>)"

    __str__ = __repr__


def _capture_class_surface(class_value: type[Any]) -> tuple[Any, ...]:
    storage = vars(class_value)
    field_map = storage.get("__dataclass_fields__")
    field_surfaces: tuple[Any, ...]
    if type(field_map) is dict:
        field_surfaces = tuple(
            (
                name,
                field,
                tuple(
                    _OBJECT_GETATTRIBUTE(field, attribute)
                    for attribute in (
                        "name",
                        "type",
                        "default",
                        "default_factory",
                        "init",
                        "repr",
                        "hash",
                        "compare",
                        "metadata",
                        "kw_only",
                        "_field_type",
                    )
                ),
            )
            for name, field in sorted(field_map.items())
        )
    else:
        field_surfaces = ()
    return (
        class_value,
        _TYPE_GETATTRIBUTE(class_value, "__mro__"),
        _TYPE_GETATTRIBUTE(class_value, "__name__"),
        _TYPE_GETATTRIBUTE(class_value, "__qualname__"),
        _TYPE_GETATTRIBUTE(class_value, "__module__"),
        tuple((name, storage[name]) for name in sorted(storage)),
        field_map,
        field_surfaces,
    )


_CAPSULE_CLASSES = (
    _Redacted,
    _InitialScreeningFrozenLoadedHistoryAvailable,
    _InitialScreeningFrozenLoadedHistoryUnavailable,
    _InitialScreeningResearchContextRequestSnapshot,
    _InitialScreeningResearchContextCapsule,
    _InitialScreeningResearchContextPublication,
    _InitialScreeningResearchContextInputs,
)
_CAPSULE_CLASS_SURFACES = tuple(
    _capture_class_surface(class_value) for class_value in _CAPSULE_CLASSES
)


def _research_context_inputs_key_impl(
    inputs: Any,
    *,
    published: bool,
) -> tuple[Any, ...]:
    if type(published) is not bool:
        raise TypeError
    storage = _exact_storage(
        inputs,
        _InitialScreeningResearchContextInputs,
        ("request_snapshot", "capsule", "payload_bytes", "publication"),
    )
    snapshot = storage["request_snapshot"]
    capsule = storage["capsule"]
    snapshot_storage = _exact_storage(
        snapshot,
        _InitialScreeningResearchContextRequestSnapshot,
        ("research_input", "loaded_history"),
    )
    capsule_storage = _exact_storage(
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
    if (
        type(capsule_storage["generation"]) is not int
        or capsule_storage["generation"] != _GENERATION
        or type(capsule_storage["problem_id"]) is not str
        or not capsule_storage["problem_id"]
        or type(storage["payload_bytes"]) is not bytes
    ):
        raise TypeError
    publication = storage["publication"]
    if published:
        publication_key: tuple[Any, ...] | None = _publication_key(publication)
    elif publication is None:
        publication_key = None
    else:
        raise TypeError
    _validate_optional_frozen_json(snapshot_storage["research_input"])
    _validate_optional_frozen_json(capsule_storage["research_input"])
    _validate_optional_frozen_json(capsule_storage["provider_projection"])
    _validate_frozen_history(snapshot_storage["loaded_history"])
    _validate_frozen_history(capsule_storage["loaded_history"])
    if not _same_optional_frozen_json(
        snapshot_storage["research_input"], capsule_storage["research_input"]
    ) or not _same_frozen_history(
        snapshot_storage["loaded_history"], capsule_storage["loaded_history"]
    ):
        raise ValueError
    if (capsule_storage["research_input"] is None) != (
        capsule_storage["provider_projection"] is None
    ):
        raise ValueError
    canonical = _CANONICAL_RESEARCH_CONTEXT_PAYLOAD(
        problem_id=capsule_storage["problem_id"],
        research_input=_capsule_research_input_union(capsule),
        loaded_history=_thaw_frozen_history(capsule_storage["loaded_history"]),
    )
    if canonical != storage["payload_bytes"]:
        raise ValueError
    return (
        "research_context_inputs",
        _request_snapshot_key(snapshot),
        _capsule_key(capsule),
        storage["payload_bytes"],
        publication_key,
    )


def _research_context_inputs_pristine_key_impl(inputs: Any) -> tuple[Any, ...]:
    return _research_context_inputs_key_impl(inputs, published=False)


def _publication_key(publication: Any) -> tuple[Any, ...]:
    storage = _exact_storage(
        publication,
        _InitialScreeningResearchContextPublication,
        ("campaign_dir", "directory_fingerprints", "leaf_fingerprint"),
    )
    campaign_dir = storage["campaign_dir"]
    directories = storage["directory_fingerprints"]
    leaf = storage["leaf_fingerprint"]
    if (
        type(campaign_dir) is not str
        or not campaign_dir
        or type(directories) is not tuple
        or not directories
        or type(leaf) is not tuple
        or len(leaf) != 4
        or any(type(value) is not int for value in leaf)
    ):
        raise TypeError
    for fingerprint in directories:
        if (
            type(fingerprint) is not tuple
            or len(fingerprint) != 2
            or any(type(value) is not int for value in fingerprint)
        ):
            raise TypeError
    return ("publication", campaign_dir, tuple(directories), tuple(leaf))


def _request_snapshot_key(snapshot: Any) -> tuple[Any, ...]:
    return (
        "request_snapshot",
        _clone_frozen_json(snapshot.research_input),
        _frozen_history_key(snapshot.loaded_history),
    )


def _capsule_key(capsule: Any) -> tuple[Any, ...]:
    return (
        "capsule",
        capsule.generation,
        capsule.problem_id,
        _clone_frozen_json(capsule.research_input),
        _clone_frozen_json(capsule.provider_projection),
        _frozen_history_key(capsule.loaded_history),
    )


def _capsule_research_input_union(capsule: Any) -> dict[str, Any]:
    if capsule.research_input is None:
        if capsule.provider_projection is not None:
            raise ValueError
        return {"availability": "absent"}
    if capsule.provider_projection is None:
        raise ValueError
    normalized_input = _thaw_frozen_json(capsule.research_input)
    provider_projection = _thaw_frozen_json(capsule.provider_projection)
    if type(normalized_input) is not dict or type(provider_projection) is not dict:
        raise TypeError
    return {
        "availability": "available",
        "normalized_input": normalized_input,
        "provider_projection": provider_projection,
    }


def _clone_frozen_history(value: _FrozenLoadedHistory) -> _FrozenLoadedHistory:
    if type(value) is _InitialScreeningFrozenLoadedHistoryUnavailable:
        _exact_storage(value, _InitialScreeningFrozenLoadedHistoryUnavailable, ())
        return _InitialScreeningFrozenLoadedHistoryUnavailable()
    if type(value) is _InitialScreeningFrozenLoadedHistoryAvailable:
        storage = _exact_storage(
            value,
            _InitialScreeningFrozenLoadedHistoryAvailable,
            ("records",),
        )
        records = storage["records"]
        if type(records) is not tuple:
            raise TypeError
        cloned_records: list[tuple[Any, ...]] = []
        for record in records:
            cloned = _clone_frozen_json(record)
            if type(cloned) is not tuple:
                raise TypeError
            cloned_records.append(cloned)
        return _InitialScreeningFrozenLoadedHistoryAvailable(
            records=tuple(cloned_records)
        )
    raise TypeError


def _thaw_frozen_history(value: Any) -> dict[str, Any]:
    if type(value) is _InitialScreeningFrozenLoadedHistoryUnavailable:
        _exact_storage(value, _InitialScreeningFrozenLoadedHistoryUnavailable, ())
        return {
            "availability": "unavailable",
            "reason": _HISTORY_UNAVAILABLE_REASON,
        }
    if type(value) is _InitialScreeningFrozenLoadedHistoryAvailable:
        storage = _exact_storage(
            value,
            _InitialScreeningFrozenLoadedHistoryAvailable,
            ("records",),
        )
        records = storage["records"]
        if type(records) is not tuple:
            raise TypeError
        thawed: list[dict[str, Any]] = []
        for record in records:
            item = _thaw_frozen_json(record)
            if type(item) is not dict:
                raise TypeError
            thawed.append(item)
        return {"availability": "available", "records": thawed}
    raise TypeError


def _validate_frozen_history(value: Any) -> None:
    if type(value) is _InitialScreeningFrozenLoadedHistoryUnavailable:
        _exact_storage(value, _InitialScreeningFrozenLoadedHistoryUnavailable, ())
        return
    if type(value) is not _InitialScreeningFrozenLoadedHistoryAvailable:
        raise TypeError
    storage = _exact_storage(
        value,
        _InitialScreeningFrozenLoadedHistoryAvailable,
        ("records",),
    )
    records = storage["records"]
    if type(records) is not tuple or len(records) > _MAX_LOADED_HISTORY_RECORDS:
        raise TypeError
    for record in records:
        _validate_frozen_json(record)
        if _frozen_json_tag(record) != "dict":
            raise TypeError


def _same_frozen_history(current: Any, expected: Any) -> bool:
    if type(current) is not type(expected):
        return False
    if type(expected) is _InitialScreeningFrozenLoadedHistoryUnavailable:
        return True
    if type(expected) is not _InitialScreeningFrozenLoadedHistoryAvailable:
        return False
    current_records = vars(current).get("records")
    expected_records = vars(expected).get("records")
    if type(current_records) is not tuple or type(expected_records) is not tuple:
        return False
    return len(current_records) == len(expected_records) and all(
        _same_frozen_json(current_record, expected_record)
        for current_record, expected_record in zip(current_records, expected_records)
    )


def _frozen_history_key(value: _FrozenLoadedHistory) -> tuple[Any, ...]:
    _validate_frozen_history(value)
    if type(value) is _InitialScreeningFrozenLoadedHistoryUnavailable:
        return ("unavailable",)
    storage = _exact_storage(
        value,
        _InitialScreeningFrozenLoadedHistoryAvailable,
        ("records",),
    )
    records = storage["records"]
    if type(records) is not tuple:
        raise TypeError
    cloned_records: list[tuple[Any, ...]] = []
    for record in records:
        cloned = _clone_frozen_json(record)
        if type(cloned) is not tuple:
            raise TypeError
        cloned_records.append(cloned)
    return (
        "available",
        tuple(cloned_records),
    )


def _freeze_exact_json(
    value: Any,
    *,
    depth: int = 0,
    active: set[int] | None = None,
) -> tuple[Any, ...]:
    if depth > _MAX_JSON_DEPTH:
        raise ValueError
    if value is None:
        return ("null",)
    if type(value) is bool:
        return ("bool", value)
    if type(value) is int:
        return ("int", value)
    if type(value) is float:
        if not _MATH_ISFINITE(value):
            raise ValueError
        return ("float", value)
    if type(value) is str:
        return ("str", value)
    if type(value) not in {dict, list}:
        raise TypeError
    stack = set() if active is None else active
    identity = id(value)
    if identity in stack:
        raise ValueError
    stack.add(identity)
    try:
        if type(value) is dict:
            keys = tuple(value)
            if any(type(key) is not str for key in keys):
                raise TypeError
            return (
                "dict",
                tuple(
                    (
                        key,
                        _freeze_exact_json(
                            value[key],
                            depth=depth + 1,
                            active=stack,
                        ),
                    )
                    for key in sorted(keys)
                ),
            )
        return (
            "list",
            tuple(
                _freeze_exact_json(item, depth=depth + 1, active=stack)
                for item in value
            ),
        )
    finally:
        stack.remove(identity)


def _thaw_frozen_json(value: Any) -> Any:
    _validate_frozen_json(value)
    tag = value[0]
    if tag == "null":
        return None
    if tag in {"bool", "int", "float", "str"}:
        return value[1]
    if tag == "dict":
        return {key: _thaw_frozen_json(child) for key, child in value[1]}
    return [_thaw_frozen_json(child) for child in value[1]]


def _clone_frozen_json(value: Any) -> tuple[Any, ...] | None:
    if value is None:
        return None
    return _freeze_exact_json(_thaw_frozen_json(value))


def _validate_optional_frozen_json(value: Any) -> None:
    if value is not None:
        _validate_frozen_json(value)


def _validate_frozen_json(value: Any, *, depth: int = 0) -> None:
    if depth > _MAX_JSON_DEPTH or type(value) is not tuple or not value:
        raise TypeError
    tag = value[0]
    if type(tag) is not str:
        raise TypeError
    if tag == "null":
        if len(value) != 1:
            raise TypeError
        return
    if tag == "float":
        if len(value) != 2 or type(value[1]) is not float:
            raise TypeError
        if not _MATH_ISFINITE(value[1]):
            raise ValueError
        return
    if tag in {"bool", "int", "str"}:
        expected_type = {"bool": bool, "int": int, "str": str}[tag]
        if len(value) != 2 or type(value[1]) is not expected_type:
            raise TypeError
        return
    if tag == "dict":
        if len(value) != 2 or type(value[1]) is not tuple:
            raise TypeError
        previous: str | None = None
        for pair in value[1]:
            if (
                type(pair) is not tuple
                or len(pair) != 2
                or type(pair[0]) is not str
                or (previous is not None and pair[0] <= previous)
            ):
                raise TypeError
            previous = pair[0]
            _validate_frozen_json(pair[1], depth=depth + 1)
        return
    if tag != "list" or len(value) != 2 or type(value[1]) is not tuple:
        raise TypeError
    for child in value[1]:
        _validate_frozen_json(child, depth=depth + 1)


def _frozen_json_tag(value: Any) -> str:
    _validate_frozen_json(value)
    tag = value[0]
    if type(tag) is not str:  # pragma: no cover - validated above
        raise TypeError
    return tag


def _same_optional_frozen_json(current: Any, expected: Any) -> bool:
    if current is None or expected is None:
        return current is expected
    return _same_frozen_json(current, expected)


def _same_frozen_json(current: Any, expected: Any) -> bool:
    if type(current) is not tuple or type(expected) is not tuple:
        return False
    if len(current) != len(expected) or not current or not expected:
        return False
    current_tag = current[0]
    expected_tag = expected[0]
    if type(current_tag) is not str or type(expected_tag) is not str:
        return False
    if current_tag != expected_tag:
        return False
    if expected_tag == "null":
        return len(expected) == 1
    if expected_tag == "float":
        return (
            len(current) == 2
            and type(current[1]) is float
            and type(expected[1]) is float
            and current[1].hex() == expected[1].hex()
        )
    if expected_tag in {"bool", "int", "str"}:
        expected_type = {"bool": bool, "int": int, "str": str}[expected_tag]
        return (
            len(current) == 2
            and type(current[1]) is expected_type
            and type(expected[1]) is expected_type
            and current[1] == expected[1]
        )
    if expected_tag == "dict":
        if (
            len(current) != 2
            or type(current[1]) is not tuple
            or type(expected[1]) is not tuple
            or len(current[1]) != len(expected[1])
        ):
            return False
        for current_pair, expected_pair in zip(current[1], expected[1]):
            if (
                type(current_pair) is not tuple
                or type(expected_pair) is not tuple
                or len(current_pair) != 2
                or len(expected_pair) != 2
                or type(current_pair[0]) is not str
                or type(expected_pair[0]) is not str
                or current_pair[0] != expected_pair[0]
                or not _same_frozen_json(current_pair[1], expected_pair[1])
            ):
                return False
        return True
    if expected_tag != "list":
        return False
    if (
        len(current) != 2
        or type(current[1]) is not tuple
        or type(expected[1]) is not tuple
        or len(current[1]) != len(expected[1])
    ):
        return False
    return all(
        _same_frozen_json(current_child, expected_child)
        for current_child, expected_child in zip(current[1], expected[1])
    )


def _same_immutable_tree(current: Any, expected: Any) -> bool:
    if type(current) is not type(expected):
        return False
    if type(expected) is tuple:
        return len(current) == len(expected) and all(
            _same_immutable_tree(current_item, expected_item)
            for current_item, expected_item in zip(current, expected)
        )
    if type(expected) is float:
        return current.hex() == expected.hex()
    if expected is None:
        return current is None
    if type(expected) in {str, bool, int, bytes}:
        return current == expected
    return current is expected


def _exact_storage(
    value: Any,
    expected_type: type[Any],
    expected_keys: tuple[str, ...],
) -> dict[str, Any]:
    if type(value) is not expected_type or type(expected_keys) is not tuple:
        raise TypeError
    storage = vars(value)
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or len(storage) != len(expected_keys)
        or any(key not in storage for key in expected_keys)
    ):
        raise TypeError
    return storage


_CAPSULE_HELPER_NAMES = (
    "_research_context_inputs_key_impl",
    "_research_context_inputs_pristine_key_impl",
    "_publication_key",
    "_request_snapshot_key",
    "_capsule_key",
    "_capsule_research_input_union",
    "_clone_frozen_history",
    "_thaw_frozen_history",
    "_validate_frozen_history",
    "_same_frozen_history",
    "_frozen_history_key",
    "_freeze_exact_json",
    "_thaw_frozen_json",
    "_clone_frozen_json",
    "_validate_optional_frozen_json",
    "_validate_frozen_json",
    "_frozen_json_tag",
    "_same_optional_frozen_json",
    "_same_frozen_json",
    "_same_immutable_tree",
    "_exact_storage",
    "_capture_class_surface",
)
_CAPSULE_HELPERS = tuple((name, globals()[name]) for name in _CAPSULE_HELPER_NAMES)
_CAPSULE_BUILTIN_NAMES = (
    "TypeError",
    "ValueError",
    "all",
    "any",
    "bool",
    "bytes",
    "dict",
    "float",
    "globals",
    "id",
    "int",
    "len",
    "list",
    "object",
    "set",
    "sorted",
    "str",
    "tuple",
    "type",
    "vars",
    "zip",
)


def _validate_capsule_dependencies(
    canonical_anchor: Any = _CANONICAL_RESEARCH_CONTEXT_PAYLOAD,
    schema_anchor_validator: Any = _VALIDATE_SCHEMA_ANCHORS,
    schema_dependency_validator: Any = _VALIDATE_SCHEMA_DEPENDENCIES,
    math_isfinite_anchor: Any = _MATH_ISFINITE,
    helper_anchors: tuple[tuple[str, Any], ...] = _CAPSULE_HELPERS,
    builtin_names_anchor: tuple[str, ...] = _CAPSULE_BUILTIN_NAMES,
    generation_anchor: int = _GENERATION,
    max_depth_anchor: int = _MAX_JSON_DEPTH,
    max_records_anchor: int = _MAX_LOADED_HISTORY_RECORDS,
    history_reason_anchor: str = _HISTORY_UNAVAILABLE_REASON,
    available_type_anchor: Any = _InitialScreeningFrozenLoadedHistoryAvailable,
    unavailable_type_anchor: Any = _InitialScreeningFrozenLoadedHistoryUnavailable,
    snapshot_type_anchor: Any = _InitialScreeningResearchContextRequestSnapshot,
    capsule_type_anchor: Any = _InitialScreeningResearchContextCapsule,
    publication_type_anchor: Any = _InitialScreeningResearchContextPublication,
    inputs_type_anchor: Any = _InitialScreeningResearchContextInputs,
    class_surfaces_anchor: tuple[tuple[Any, ...], ...] = _CAPSULE_CLASS_SURFACES,
    capsule_classes_anchor: tuple[type[Any], ...] = _CAPSULE_CLASSES,
    type_getattribute_anchor: Any = _TYPE_GETATTRIBUTE,
    object_getattribute_anchor: Any = _OBJECT_GETATTRIBUTE,
    self_module: ModuleType = sys.modules[__name__],
    self_name: str = __name__,
    module_anchor: ModuleType = research_context_module,
    module_name_anchor: str = _RESEARCH_MODULE_NAME,
    math_module_anchor: ModuleType = math,
    sys_module_anchor: ModuleType = sys,
    sys_modules_anchor: dict[str, Any] = sys.modules,
    module_type_anchor: Any = ModuleType,
    mapping_proxy_type_anchor: Any = MappingProxyType,
    object_type_anchor: Any = object,
    bool_type_anchor: Any = bool,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    len_fn: Any = len,
    tuple_type_anchor: Any = tuple,
    dict_type_anchor: Any = dict,
    str_type_anchor: Any = str,
    int_type_anchor: Any = int,
    class_type_anchor: Any = type,
    error_type: Any = TypeError,
) -> None:
    if any_fn(
        type_fn(module) is not module_type_anchor
        for module in (
            self_module,
            module_anchor,
            math_module_anchor,
            sys_module_anchor,
        )
    ):
        raise error_type
    self_storage = vars_fn(self_module)
    research_storage = vars_fn(module_anchor)
    math_storage = vars_fn(math_module_anchor)
    sys_storage = vars_fn(sys_module_anchor)
    if any_fn(
        type_fn(storage) is not dict_type_anchor
        or any_fn(type_fn(key) is not str_type_anchor for key in storage)
        for storage in (self_storage, research_storage, math_storage, sys_storage)
    ):
        raise error_type
    current_self_name = self_storage.get("__name__")
    current_module_name = research_storage.get("__name__")
    if (
        type_fn(self_name) is not str_type_anchor
        or type_fn(module_name_anchor) is not str_type_anchor
        or type_fn(current_self_name) is not str_type_anchor
        or type_fn(current_module_name) is not str_type_anchor
        or current_self_name != self_name
        or current_module_name != module_name_anchor
        or type_fn(sys_modules_anchor) is not dict_type_anchor
        or sys_storage.get("modules") is not sys_modules_anchor
        or sys_modules_anchor.get(self_name) is not self_module
        or sys_modules_anchor.get(module_name_anchor) is not module_anchor
        or type_fn(generation_anchor) is not int_type_anchor
        or generation_anchor != 1
        or type_fn(max_depth_anchor) is not int_type_anchor
        or type_fn(max_records_anchor) is not int_type_anchor
        or type_fn(history_reason_anchor) is not str_type_anchor
        or type_fn(self_storage.get("_GENERATION")) is not int_type_anchor
        or self_storage.get("_GENERATION") != generation_anchor
        or type_fn(self_storage.get("_MAX_JSON_DEPTH")) is not int_type_anchor
        or self_storage.get("_MAX_JSON_DEPTH") != max_depth_anchor
        or type_fn(self_storage.get("_MAX_LOADED_HISTORY_RECORDS"))
        is not int_type_anchor
        or self_storage.get("_MAX_LOADED_HISTORY_RECORDS") != max_records_anchor
        or self_storage.get("_HISTORY_UNAVAILABLE_REASON") is not history_reason_anchor
        or type_fn(research_storage.get("_MAX_JSON_DEPTH")) is not int_type_anchor
        or research_storage.get("_MAX_JSON_DEPTH") != max_depth_anchor
        or type_fn(research_storage.get("_MAX_LOADED_HISTORY_RECORDS"))
        is not int_type_anchor
        or research_storage.get("_MAX_LOADED_HISTORY_RECORDS") != max_records_anchor
        or research_storage.get("_HISTORY_UNAVAILABLE_REASON")
        is not history_reason_anchor
        or self_storage.get("_CANONICAL_RESEARCH_CONTEXT_PAYLOAD")
        is not canonical_anchor
        or research_storage.get("_canonical_research_context_payload")
        is not canonical_anchor
        or self_storage.get("_VALIDATE_SCHEMA_ANCHORS") is not schema_anchor_validator
        or research_storage.get("_validate_schema_anchors")
        is not schema_anchor_validator
        or self_storage.get("_VALIDATE_SCHEMA_DEPENDENCIES")
        is not schema_dependency_validator
        or research_storage.get("_validate_dependency_anchors")
        is not schema_dependency_validator
        or self_storage.get("_MATH_ISFINITE") is not math_isfinite_anchor
        or math_storage.get("isfinite") is not math_isfinite_anchor
        or self_storage.get("_TYPE_GETATTRIBUTE") is not type_getattribute_anchor
        or self_storage.get("_OBJECT_GETATTRIBUTE") is not object_getattribute_anchor
        or vars_fn(class_type_anchor).get("__getattribute__")
        is not type_getattribute_anchor
        or vars_fn(object_type_anchor).get("__getattribute__")
        is not object_getattribute_anchor
        or self_storage.get("research_context_module") is not module_anchor
        or self_storage.get("_RESEARCH_MODULE_NAME") is not module_name_anchor
        or self_storage.get("math") is not math_module_anchor
        or self_storage.get("sys") is not sys_module_anchor
        or self_storage.get("_InitialScreeningFrozenLoadedHistoryAvailable")
        is not available_type_anchor
        or self_storage.get("_InitialScreeningFrozenLoadedHistoryUnavailable")
        is not unavailable_type_anchor
        or self_storage.get("_InitialScreeningResearchContextRequestSnapshot")
        is not snapshot_type_anchor
        or self_storage.get("_InitialScreeningResearchContextCapsule")
        is not capsule_type_anchor
        or self_storage.get("_InitialScreeningResearchContextPublication")
        is not publication_type_anchor
        or self_storage.get("_InitialScreeningResearchContextInputs")
        is not inputs_type_anchor
        or type_fn(available_type_anchor) is not class_type_anchor
        or type_fn(unavailable_type_anchor) is not class_type_anchor
        or type_fn(snapshot_type_anchor) is not class_type_anchor
        or type_fn(capsule_type_anchor) is not class_type_anchor
        or type_fn(publication_type_anchor) is not class_type_anchor
        or type_fn(inputs_type_anchor) is not class_type_anchor
        or type_fn(helper_anchors) is not tuple_type_anchor
        or type_fn(builtin_names_anchor) is not tuple_type_anchor
        or type_fn(class_surfaces_anchor) is not tuple_type_anchor
        or type_fn(capsule_classes_anchor) is not tuple_type_anchor
        or self_storage.get("_CAPSULE_HELPERS") is not helper_anchors
        or self_storage.get("_CAPSULE_BUILTIN_NAMES") is not builtin_names_anchor
        or self_storage.get("_CAPSULE_CLASS_SURFACES") is not class_surfaces_anchor
        or self_storage.get("_CAPSULE_CLASSES") is not capsule_classes_anchor
    ):
        raise error_type
    if any_fn(
        type_fn(name) is not str_type_anchor for name in builtin_names_anchor
    ) or any_fn(name in self_storage for name in builtin_names_anchor):
        raise error_type
    for name, helper in helper_anchors:
        if type_fn(name) is not str_type_anchor or self_storage.get(name) is not helper:
            raise error_type
    if len_fn(class_surfaces_anchor) != len_fn(capsule_classes_anchor):
        raise error_type
    for class_value, expected_surface in zip(
        capsule_classes_anchor, class_surfaces_anchor
    ):
        if (
            type_fn(class_value) is not class_type_anchor
            or type_fn(expected_surface) is not tuple_type_anchor
            or len_fn(expected_surface) != 8
            or expected_surface[0] is not class_value
        ):
            raise error_type
        class_storage = vars_fn(class_value)
        mro = type_getattribute_anchor(class_value, "__mro__")
        current_name = type_getattribute_anchor(class_value, "__name__")
        current_qualname = type_getattribute_anchor(class_value, "__qualname__")
        current_module_name = type_getattribute_anchor(class_value, "__module__")
        expected_mro = expected_surface[1]
        expected_name = expected_surface[2]
        expected_qualname = expected_surface[3]
        expected_module_name = expected_surface[4]
        expected_items = expected_surface[5]
        expected_field_map = expected_surface[6]
        expected_fields = expected_surface[7]
        if (
            type_fn(class_storage) is not mapping_proxy_type_anchor
            or type_fn(mro) is not tuple_type_anchor
            or type_fn(expected_mro) is not tuple_type_anchor
            or type_fn(expected_name) is not str_type_anchor
            or type_fn(expected_qualname) is not str_type_anchor
            or type_fn(expected_module_name) is not str_type_anchor
            or type_fn(current_name) is not str_type_anchor
            or type_fn(current_qualname) is not str_type_anchor
            or type_fn(current_module_name) is not str_type_anchor
            or current_name != expected_name
            or current_qualname != expected_qualname
            or current_module_name != expected_module_name
            or len_fn(mro) != len_fn(expected_mro)
            or any_fn(
                current is not expected for current, expected in zip(mro, expected_mro)
            )
            or type_fn(expected_items) is not tuple_type_anchor
            or len_fn(class_storage) != len_fn(expected_items)
            or any_fn(
                type_fn(item) is not tuple_type_anchor
                or len_fn(item) != 2
                or type_fn(item[0]) is not str_type_anchor
                or class_storage.get(item[0]) is not item[1]
                for item in expected_items
            )
            or type_fn(expected_fields) is not tuple_type_anchor
        ):
            raise error_type
        field_map = class_storage.get("__dataclass_fields__")
        if field_map is not expected_field_map:
            raise error_type
        if expected_field_map is not None:
            if type_fn(field_map) is not dict_type_anchor or len_fn(
                field_map
            ) != len_fn(expected_fields):
                raise error_type
            for name, field, attributes in expected_fields:
                if (
                    type_fn(name) is not str_type_anchor
                    or field_map.get(name) is not field
                    or type_fn(attributes) is not tuple_type_anchor
                    or len_fn(attributes) != 11
                ):
                    raise error_type
                for attribute, expected in zip(
                    (
                        "name",
                        "type",
                        "default",
                        "default_factory",
                        "init",
                        "repr",
                        "hash",
                        "compare",
                        "metadata",
                        "kw_only",
                        "_field_type",
                    ),
                    attributes,
                ):
                    current = object_getattribute_anchor(field, attribute)
                    if type_fn(expected) in (
                        str_type_anchor,
                        int_type_anchor,
                        bool_type_anchor,
                    ):
                        if (
                            type_fn(current) is not type_fn(expected)
                            or current != expected
                        ):
                            raise error_type
                    elif current is not expected:
                        raise error_type
    schema_anchor_validator()
    schema_dependency_validator()


def _research_context_inputs_pristine_key(
    inputs: Any,
    dependency_validator: Any = _validate_capsule_dependencies,
    implementation: Any = _research_context_inputs_pristine_key_impl,
    self_module: ModuleType = sys.modules[__name__],
    module_type_anchor: Any = ModuleType,
    type_fn: Any = type,
    vars_fn: Any = vars,
    dict_type_anchor: Any = dict,
    error_type: Any = TypeError,
) -> tuple[Any, ...]:
    if type_fn(self_module) is not module_type_anchor:
        raise error_type
    storage = vars_fn(self_module)
    if (
        type_fn(storage) is not dict_type_anchor
        or storage.get("_validate_capsule_dependencies") is not dependency_validator
        or storage.get("_research_context_inputs_pristine_key_impl")
        is not implementation
    ):
        raise error_type
    dependency_validator()
    return implementation(inputs)
