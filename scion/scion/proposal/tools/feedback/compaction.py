"""Feedback payload compaction and memory sanitization helpers."""

from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.tools.feedback.constants import (
    _COMPACT_FEEDBACK_LIST_ITEMS,
    _COMPACT_FEEDBACK_MAP_ITEMS,
    _COMPACT_FEEDBACK_PAYLOAD_CHARS,
    _COMPACT_FEEDBACK_STRING_CHARS,
)
from scion.proposal.tools.utils import _json_size, _limit_text, _strip_forbidden_value


def _bound_compact_feedback_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    estimated = _json_size(payload)
    if estimated <= _COMPACT_FEEDBACK_PAYLOAD_CHARS:
        bounded = dict(payload)
        bounded.setdefault("payload_truncated", False)
        return bounded
    compact = _compact_feedback_value(payload)
    compact_estimated = _json_size(compact)
    if (
        isinstance(compact, Mapping)
        and compact_estimated <= _COMPACT_FEEDBACK_PAYLOAD_CHARS
    ):
        bounded = dict(compact)
        bounded["payload_truncated"] = True
        bounded["original_estimated_chars"] = estimated
        return bounded
    return {
        "payload_truncated": True,
        "original_estimated_chars": estimated,
        "compacted_estimated_chars": compact_estimated,
        "available_keys": sorted(str(key) for key in payload.keys()),
        "summary": "Compact feedback payload exceeded budget and was summarized.",
    }
def _compact_feedback_value(value: Any, *, depth: int = 0) -> Any:
    if isinstance(value, Mapping):
        compact: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _COMPACT_FEEDBACK_MAP_ITEMS:
                compact["omitted_mapping_items"] = len(value) - index
                break
            compact[str(key)] = _compact_feedback_value(item, depth=depth + 1)
        return compact
    if isinstance(value, tuple):
        return _compact_feedback_value(list(value), depth=depth)
    if isinstance(value, list):
        compact_list = [
            _compact_feedback_value(item, depth=depth + 1)
            for item in value[:_COMPACT_FEEDBACK_LIST_ITEMS]
        ]
        if len(value) > _COMPACT_FEEDBACK_LIST_ITEMS:
            compact_list.append(
                {"omitted_items": len(value) - _COMPACT_FEEDBACK_LIST_ITEMS}
            )
        return compact_list
    if isinstance(value, str):
        limit = max(
            200,
            _COMPACT_FEEDBACK_STRING_CHARS // max(1, min(depth, 4)),
        )
        return _limit_text(value, limit)
    return _strip_forbidden_value(value)
def _sanitize_memory_text(text: str) -> str:
    if not text:
        return ""
    forbidden_terms = (
        "champion_evolution",
        "champion evolution",
        "promotion",
        "promoted",
        "promote",
        "validation",
        "frozen",
        "holdout",
        "raw_metrics",
        "raw metrics",
    )
    safe_lines = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(term in lowered for term in forbidden_terms):
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines)

__all__ = [
    "_bound_compact_feedback_payload",
    "_compact_feedback_value",
    "_sanitize_memory_text",
]
