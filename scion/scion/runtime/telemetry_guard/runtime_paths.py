"""Runtime telemetry path parsing and resolution."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _mechanism_field_summary_key(mechanism: str, field: str) -> str:
    return f"{mechanism}:{field}"


def _runtime_path_observation(
    runtime: Mapping[str, Any],
    field: str,
    *,
    mechanism: str | None,
) -> dict[str, Any]:
    path = str(field or "").strip()
    raw_path = path
    if mechanism:
        path = path.replace("{mechanism}", mechanism)
    if not path:
        return {"present": False, "value": None}

    if path in runtime:
        return _mechanism_scoped_observation(runtime[path], mechanism=mechanism)

    segments = _parse_runtime_path(path)
    scope_final_mapping = bool(
        mechanism
        and "{mechanism}" not in raw_path
        and mechanism not in segments
    )
    values = _resolve_runtime_path(
        runtime,
        segments,
        mechanism=mechanism if scope_final_mapping else None,
    )
    if not values:
        return {"present": False, "value": None}
    value: Any = values[0] if len(values) == 1 else values
    return {"present": True, "value": value}


def _mechanism_scoped_observation(
    value: Any,
    *,
    mechanism: str | None,
) -> dict[str, Any]:
    if mechanism and isinstance(value, Mapping):
        if mechanism not in value:
            return {"present": False, "value": None}
        return {"present": True, "value": value.get(mechanism)}
    return {"present": True, "value": value}


def _resolve_runtime_path(
    root: Any,
    segments: Sequence[str],
    *,
    mechanism: str | None,
) -> list[Any]:
    values = [root]
    for segment in segments:
        next_values: list[Any] = []
        key = mechanism if segment == "*" and mechanism else segment
        for value in values:
            if isinstance(value, Mapping):
                if key == "*" and not mechanism:
                    next_values.extend(value.values())
                elif key in value:
                    next_values.append(value.get(key))
            elif (
                isinstance(value, Sequence)
                and not isinstance(value, (bytes, bytearray, str))
                and str(key).isdigit()
            ):
                index = int(str(key))
                if 0 <= index < len(value):
                    next_values.append(value[index])
        values = next_values
        if not values:
            return []
    if mechanism:
        scoped: list[Any] = []
        for value in values:
            observation = _mechanism_scoped_observation(value, mechanism=mechanism)
            if observation["present"]:
                scoped.append(observation["value"])
        return scoped
    return values


def _parse_runtime_path(path: str) -> tuple[str, ...]:
    segments: list[str] = []
    current: list[str] = []
    bracket = False
    quote: str | None = None
    for char in path:
        if quote:
            if char == quote:
                quote = None
            else:
                current.append(char)
            continue
        if char in {"'", '"'} and bracket:
            quote = char
            continue
        if char == "[":
            if current:
                segments.append("".join(current).strip())
                current = []
            bracket = True
            continue
        if char == "]" and bracket:
            segments.append("".join(current).strip())
            current = []
            bracket = False
            continue
        if char == "." and not bracket:
            if current:
                segments.append("".join(current).strip())
                current = []
            continue
        current.append(char)
    if current:
        segments.append("".join(current).strip())
    return tuple(segment for segment in segments if segment)
