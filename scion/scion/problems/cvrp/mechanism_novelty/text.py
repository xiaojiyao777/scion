"""Text and payload helpers for CVRP mechanism novelty checks."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        strings: list[str] = []
        for key, child in value.items():
            strings.append(str(key))
            strings.extend(_flatten_strings(child))
        return strings
    if isinstance(value, (list, tuple, set)):
        strings = []
        for child in value:
            strings.extend(_flatten_strings(child))
        return strings
    if value is None:
        return []
    return [str(value)]


def _flatten_leaf_strings(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        strings: list[str] = []
        for child in value.values():
            strings.extend(_flatten_leaf_strings(child))
        return strings
    if isinstance(value, (list, tuple, set)):
        strings = []
        for child in value:
            strings.extend(_flatten_leaf_strings(child))
        return strings
    if value is None:
        return []
    return [str(value)]


def _evidence(value: Any, *, fallback: tuple[str, ...]) -> tuple[str, ...]:
    strings = [
        item
        for item in _flatten_strings(value)
        if item and len(item) <= 220 and item.lower() not in {"true", "false"}
    ]
    result = tuple(dict.fromkeys(strings[:8]))
    return result or fallback


def _snapshot_digest(snapshot: Mapping[str, Any]) -> str | None:
    source_digest = snapshot.get("source_digest")
    if isinstance(source_digest, Mapping):
        digest = source_digest.get("snapshot_digest")
        if digest:
            return str(digest)
    digest = snapshot.get("snapshot_digest")
    return str(digest) if digest else None


def _normalized_join(values: Sequence[str]) -> str:
    return _normalize_text(" ".join(values))


def _normalize_text(text: str) -> str:
    normalized = str(text or "").lower()
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"[-/]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return f" {normalized.strip()} "


def _has_any(text: str, needles: Sequence[str]) -> bool:
    return any(needle in text for needle in needles)
