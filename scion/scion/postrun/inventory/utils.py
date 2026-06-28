"""Shared low-level helpers for postrun inventory loading."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


def _normalize_problem_family(value: Any) -> str:
    return str(value or "").strip().lower()


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _contains_key_fragment(value: Any, fragments: tuple[str, ...]) -> bool:
    lowered_fragments = tuple(fragment.lower() for fragment in fragments)
    if isinstance(value, dict):
        for key, item in value.items():
            lowered_key = str(key).lower()
            if any(fragment in lowered_key for fragment in lowered_fragments):
                return True
            if _contains_key_fragment(item, fragments):
                return True
    elif isinstance(value, list):
        return any(_contains_key_fragment(item, fragments) for item in value)
    return False


def _status_fields(run_status: Any, keys: Sequence[str]) -> dict[str, Any]:
    if not isinstance(run_status, dict):
        return {}
    return {key: run_status[key] for key in keys if key in run_status}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _marker_counts(text: str, markers: tuple[str, ...]) -> dict[str, int]:
    marker_set = set(markers)
    counts: Counter[str] = Counter()
    for raw_line in text.splitlines():
        key = raw_line.split(":", 1)[0].strip()
        if key in marker_set:
            counts[key] += 1
    return dict(sorted(counts.items()))


def _max_counter(left: Counter[str], right: Counter[str]) -> Counter[str]:
    merged: Counter[str] = Counter()
    for key in set(left) | set(right):
        merged[key] = max(left.get(key, 0), right.get(key, 0))
    return merged


def _first_string(*docs: Any, keys: tuple[str, ...]) -> str | None:
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        for key in keys:
            value = doc.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def _first_int(*docs: Any, keys: tuple[str, ...]) -> int | None:
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        value = _nested_int(doc, keys)
        if value is not None:
            return value
    return None


def _nested_int(doc: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    value = _nested_first(doc, keys)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _nested_first(doc: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in doc:
            return doc[key]
    for value in doc.values():
        if isinstance(value, dict):
            nested = _nested_first(value, keys)
            if nested is not None:
                return nested
    return None


def _branch_id(doc: Any) -> str | None:
    if not isinstance(doc, dict):
        return None
    value = _nested_first(doc, ("branch_id", "branch"))
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return [part.strip() for part in text.split(",") if part.strip()]
        return _string_list(parsed)
    return [str(value)]


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
