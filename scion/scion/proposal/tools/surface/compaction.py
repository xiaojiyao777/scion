"""Compaction helpers for surface tool payloads."""

from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.tools.surface.constants import (
    _COMPACT_SURFACE_LIST_ITEMS,
    _COMPACT_SURFACE_MAP_ITEMS,
    _COMPACT_SURFACE_TEXT_CHARS,
)
from scion.proposal.tools.utils import _limit_text, _model_payload


def _compact_text(value: Any, max_chars: int = _COMPACT_SURFACE_TEXT_CHARS) -> str:
    text = str(value).strip() if value is not None else ""
    return _limit_text(text, max_chars) if text else ""
def _coerce_compact_list(
    values: Any,
    *,
    max_items: int = _COMPACT_SURFACE_LIST_ITEMS,
) -> list[str]:
    if values is None:
        return []
    try:
        items = [str(value) for value in values if str(value)]
    except TypeError:
        return []
    return items[:max_items]
def _compact_mapping_payload(
    value: Any,
    *,
    max_items: int = _COMPACT_SURFACE_MAP_ITEMS,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact: dict[str, Any] = {}
    for idx, (key, item) in enumerate(
        sorted(value.items(), key=lambda pair: str(pair[0]))
    ):
        if idx >= max_items:
            break
        compact[str(key)] = _model_payload(item)
    return compact
def _drop_empty_items(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }

__all__ = [
    "_compact_text",
    "_coerce_compact_list",
    "_compact_mapping_payload",
    "_drop_empty_items",
]
