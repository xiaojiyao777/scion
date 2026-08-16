"""Discover host-visible source records for typed edit normalization."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scion.core.paths import normalize_relative_patch_path


def source_files_from_context(context: Mapping[str, Any] | None) -> dict[str, str]:
    """Return the frozen host-visible source text keyed by canonical path."""

    if not context:
        return {}
    source_context = context.get("editable_source_context")
    if not isinstance(source_context, Mapping):
        return {}
    if set(source_context) != {
        "approved_target",
        "sources",
        "target_api_guidance",
    }:
        raise ValueError("editable source context has unknown or missing keys")
    target = _canonical_path(source_context.get("approved_target"))
    if not isinstance(source_context.get("target_api_guidance"), str):
        raise ValueError("editable source target_api_guidance must be a string")
    sources = source_context.get("sources")
    if not isinstance(sources, list):
        raise ValueError("editable source context sources must be a list")
    records: dict[str, str] = {}
    seen: set[str] = set()
    for entry in sources:
        if not isinstance(entry, Mapping) or set(entry) != {"path", "content"}:
            raise ValueError("editable source entry has unknown or missing keys")
        path = _canonical_path(entry.get("path"))
        if path in seen:
            raise ValueError(f"duplicate editable source path: {path}")
        seen.add(path)
        content = entry.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError(f"editable source content must be text or null: {path}")
        if isinstance(content, str):
            records[path] = content
    if target not in seen:
        raise ValueError("editable source approved target is missing")
    return records


def _canonical_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"editable source path must be a string: {value!r}")
    try:
        path = normalize_relative_patch_path(value)
    except ValueError as exc:
        raise ValueError(f"invalid editable source path: {value!r}") from exc
    if path != value:
        raise ValueError(f"editable source path is not canonical: {value}")
    return path
