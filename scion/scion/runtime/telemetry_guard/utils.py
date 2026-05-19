"""Small shared helpers for telemetry guard modules."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _field(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _string_list(value: Any) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        result: list[str] = []
        for item in value.values():
            result.extend(_string_list(item))
        return result
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        result = []
        for item in value:
            text = str(item or "").strip()
            if text:
                result.append(text)
        return result
    text = str(value or "").strip()
    return [text] if text else []


def _append_fields(target: list[str], value: Any) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _append_fields(target, item)
        return
    if isinstance(value, str):
        _append_field(target, value)
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        for item in value:
            _append_fields(target, item)
        return
    _append_field(target, value)


def _append_field(target: list[str], value: Any) -> None:
    text = str(value or "").strip()
    if not text or text in target:
        return
    target.append(text)


def _freeze_claims(claims: Mapping[str, list[str]]) -> dict[str, tuple[str, ...]]:
    return {str(category): tuple(fields) for category, fields in sorted(claims.items())}


def _fields_with_suffix(fields: Sequence[str], suffixes: Sequence[str]) -> list[str]:
    return [
        field
        for field in fields
        if any(str(field).endswith(suffix) for suffix in suffixes)
    ]
