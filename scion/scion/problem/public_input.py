"""Strict, bounded JSON decoding and problem-neutral scalar checks."""
from __future__ import annotations

import json
import math
from typing import Any


class PublicInputError(ValueError):
    """Safe error: no input values or arbitrary object repr in diagnostics."""

    def __init__(self, reason_code: str, public_field_path: str = "$") -> None:
        self.reason_code = reason_code
        self.public_field_path = public_field_path
        super().__init__(f"{reason_code} at {public_field_path}")


def object_fields(
    value: Any, required: set[str], path: str = "$", *,
    optional: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    if type(value) is not dict:
        raise PublicInputError("OBJECT_REQUIRED", path)
    if not required <= value.keys() or value.keys() - required - optional:
        raise PublicInputError("FIELDS_INVALID", path)
    return value


def array(value: Any, path: str) -> list[Any]:
    if type(value) is not list:
        raise PublicInputError("ARRAY_REQUIRED", path)
    return value


def integer(value: Any, path: str, *, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        raise PublicInputError("INTEGER_INVALID", path)
    return value


def number(value: Any, path: str, *, minimum: float | None = None,
           positive: bool = False) -> int | float:
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if (not finite or (minimum is not None and value < minimum)
            or (positive and value <= 0)):
        raise PublicInputError("NUMBER_INVALID", path)
    return value


def text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise PublicInputError("TEXT_INVALID", path)
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise PublicInputError("TEXT_INVALID", path) from None
    return value


def boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise PublicInputError("BOOLEAN_INVALID", path)
    return value


def decode_public_json(
    raw: bytes, *, max_bytes: int, max_depth: int, max_collection_items: int,
) -> dict[str, Any]:
    """Bound bytes/depth before JSON allocation; reject ambiguous JSON.

    Collection item count is aggregate across lists and objects. It is checked
    after parsing; the byte/depth caps bound allocation during parsing itself.
    """
    for limit in (max_bytes, max_depth, max_collection_items):
        if type(limit) is not int or limit <= 0:
            raise ValueError("public JSON limits must be positive integers")
    if type(raw) is not bytes or len(raw) > max_bytes:
        raise PublicInputError("INPUT_SIZE_LIMIT")
    try:
        source = raw.decode("utf-8")
    except UnicodeError:
        raise PublicInputError("JSON_INVALID") from None
    depth = 0
    quoted = escaped = False
    for char in source:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > max_depth:
                raise PublicInputError("INPUT_DEPTH_LIMIT")
        elif char in "]}":
            depth -= 1

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise PublicInputError("JSON_DUPLICATE_KEY")
            result[key] = value
        return result

    def constant(_: str) -> Any:
        raise PublicInputError("JSON_NONFINITE")

    try:
        value = json.loads(source, object_pairs_hook=pairs, parse_constant=constant)
    except PublicInputError:
        raise
    except (ValueError, RecursionError):
        raise PublicInputError("JSON_INVALID") from None
    if type(value) is not dict:
        raise PublicInputError("OBJECT_REQUIRED")
    pending = [value]
    count = 0
    while pending:
        item = pending.pop()
        if type(item) in (dict, list):
            count += len(item)
            if count > max_collection_items:
                raise PublicInputError("INPUT_ITEMS_LIMIT")
            pending.extend(item.values() if type(item) is dict else item)
            if type(item) is dict:
                pending.extend(item.keys())
        elif type(item) is float and not math.isfinite(item):
            raise PublicInputError("JSON_NONFINITE")
        elif type(item) is str:
            try:
                item.encode("utf-8")
            except UnicodeError:
                raise PublicInputError("JSON_INVALID") from None
    return value
