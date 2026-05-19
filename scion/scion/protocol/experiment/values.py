from __future__ import annotations

import json
from typing import Any


def _bounded_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _increment_category(
    categories: dict[str, int],
    category: str,
    count: int = 1,
) -> None:
    category = str(category or "runtime_error").strip() or "runtime_error"
    categories[category] = categories.get(category, 0) + max(0, int(count))


def _is_json_scalar(value: object) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def _bounded_json_value(value: Any, *, max_items: int = 20, max_chars: int = 500) -> Any:
    if _is_json_scalar(value):
        if isinstance(value, str) and len(value) > max_chars:
            return value[: max(0, max_chars - 3)] + "..."
        return value
    if isinstance(value, (list, tuple)):
        return [
            _bounded_json_value(item, max_items=max_items, max_chars=max_chars)
            for item in list(value)[:max_items]
        ]
    if isinstance(value, dict):
        bounded: dict[str, Any] = {}
        for key in sorted(value, key=str)[:max_items]:
            bounded[str(key)] = _bounded_json_value(
                value[key],
                max_items=max_items,
                max_chars=max_chars,
            )
        return bounded
    return _bounded_text(value, max_chars)


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _round_runtime_number(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _parse_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _as_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


__all__ = [
    "_as_int",
    "_as_truthy",
    "_bounded_json_value",
    "_bounded_text",
    "_coerce_number",
    "_increment_category",
    "_is_json_scalar",
    "_parse_int",
    "_round_runtime_number",
    "_safe_int",
]
