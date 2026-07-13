"""Prompt manifest accounting helpers.

These helpers are intentionally policy-free: they count rendered provider
prompt text, summarize cacheable prompt blocks, and compute prompt hashes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

def _json_chars(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, default=str))


def _system_text_chars(system_blocks: tuple[Mapping[str, Any], ...]) -> int:
    total = 0
    for block in system_blocks:
        if isinstance(block, Mapping):
            total += len(str(block.get("text", "")))
        else:
            total += len(str(block))
    return total


def _system_block_records(
    system_blocks: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, block in enumerate(system_blocks, start=1):
        if isinstance(block, Mapping):
            text = str(block.get("text", ""))
            cache_control = block.get("cache_control")
        else:
            text = str(block)
            cache_control = None
        records.append(
            {
                "block_index": index,
                "char_count": len(text),
                "content_hash": _text_digest(text, length=16),
                "cacheable": bool(cache_control),
                "cache_control": (
                    dict(cache_control)
                    if isinstance(cache_control, Mapping)
                    else (str(cache_control) if cache_control else {})
                ),
            }
        )
    return records


def _cacheability_summary(
    *,
    system_block_records: list[Mapping[str, Any]],
    user_prompt_chars: int,
) -> dict[str, Any]:
    cacheable_system_chars = sum(
        int(record.get("char_count") or 0)
        for record in system_block_records
        if record.get("cacheable")
    )
    non_cache_system_chars = sum(
        int(record.get("char_count") or 0)
        for record in system_block_records
        if not record.get("cacheable")
    )
    return {
        "system_block_count": len(system_block_records),
        "cache_control_block_count": sum(
            1 for record in system_block_records if record.get("cacheable")
        ),
        "cacheable_system_chars": cacheable_system_chars,
        "non_cache_system_chars": non_cache_system_chars,
        "user_prompt_chars": user_prompt_chars,
        "estimated_cacheable_chars": cacheable_system_chars,
        "estimated_non_cache_chars": non_cache_system_chars + user_prompt_chars,
        "system_blocks": list(system_block_records),
    }


def _provider_prompt_hash(
    system_blocks: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    user_prompt: str,
) -> str:
    blob = json.dumps(
        {"system_blocks": list(system_blocks), "user_prompt": user_prompt},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _text_digest(value: str, *, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


__all__ = [
    "_cacheability_summary",
    "_json_chars",
    "_provider_prompt_hash",
    "_system_block_records",
    "_system_text_chars",
    "_text_digest",
]
