"""Text and identity helpers for algorithm-smoke agent feedback."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from scion.proposal.tools.utils import _limit_text, _strip_forbidden_value

_ALGORITHM_SMOKE_AGENT_SCHEMA = "scion.algorithm_smoke.agent_feedback.v1"
_ALGORITHM_SMOKE_AGENT_TEXT_CHARS = 900
_ALGORITHM_SMOKE_AGENT_TAIL_CHARS = 900
_ALGORITHM_SMOKE_AGENT_LIST_ITEMS = 8
_ALGORITHM_SMOKE_AGENT_COUNTER_ITEMS = 16


def _mapping_or_none(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _algorithm_smoke_digest(value: Any) -> str:
    rendered = json.dumps(
        _strip_forbidden_value(value),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]


def _first_mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, Mapping):
                return item
    return None


def _runtime_event_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    return _limit_text(
        json.dumps(_strip_forbidden_value(value), sort_keys=True, default=str),
        _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
    )


def _compact_agent_text_list(
    value: Any,
    *,
    limit: int = _ALGORITHM_SMOKE_AGENT_LIST_ITEMS,
) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Mapping):
        values = [
            json.dumps(_strip_forbidden_value(value), sort_keys=True, default=str)
        ]
    else:
        try:
            values = list(value)
        except TypeError:
            values = [value]
    compact: list[str] = []
    for item in values:
        text = _compact_agent_text(item)
        if text and text not in compact:
            compact.append(text)
        if len(compact) >= limit:
            break
    return compact


def _compact_agent_text(
    value: Any,
    *,
    max_chars: int = _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(_strip_forbidden_value(value), sort_keys=True, default=str)
    return _limit_text(text.strip(), max_chars)


def _tail_text(value: Any, *, max_chars: int = _ALGORITHM_SMOKE_AGENT_TAIL_CHARS) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return "[tail]\n" + text[-max_chars:]


__all__ = [
    "_ALGORITHM_SMOKE_AGENT_COUNTER_ITEMS",
    "_ALGORITHM_SMOKE_AGENT_LIST_ITEMS",
    "_ALGORITHM_SMOKE_AGENT_SCHEMA",
    "_ALGORITHM_SMOKE_AGENT_TEXT_CHARS",
    "_algorithm_smoke_digest",
    "_compact_agent_text",
    "_compact_agent_text_list",
    "_first_mapping",
    "_mapping_or_none",
    "_runtime_event_text",
    "_tail_text",
]
