"""Provider transport cache-key helpers for LLMClient."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from .config import _is_gpt_codex_model

_PROMPT_CACHE_KEY_VERSION = "scion-prompt-cache-key.v1"
_PROMPT_CACHE_KEY_PREFIX = "scion:v3:gpt"


def gpt_prompt_cache_key(
    *,
    model: str,
    request_kind: str,
    system_blocks: list[dict] | None,
    tool_schema: Any,
) -> str | None:
    """Return a stable OpenAI-compatible GPT/Codex prompt cache key.

    The key is provider transport metadata. It intentionally excludes user
    prompt text, branch/session/trace ids, runtime feedback, hypothesis text,
    and problem-domain facts that are not already part of cacheable system
    blocks or the tool schema.
    """
    if not _is_gpt_codex_model(str(model or "")):
        return None
    kind = _normalize_request_kind_for_cache(request_kind)
    system_hash = cacheable_system_blocks_hash(system_blocks)
    schema_hash = tool_schema_hash(tool_schema)
    components = {
        "schema_version": _PROMPT_CACHE_KEY_VERSION,
        "request_kind": kind,
        "model_family": "gpt",
        "cacheable_system_blocks_hash": system_hash,
        "tool_schema_hash": schema_hash,
    }
    digest = hashlib.sha256(
        json.dumps(components, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    return f"{_PROMPT_CACHE_KEY_PREFIX}:{_kind_short(kind)}:{digest}"


def cacheable_system_blocks_hash(system_blocks: list[dict] | None) -> str:
    records: list[dict[str, str]] = []
    for block in system_blocks or []:
        if isinstance(block, Mapping):
            if not block.get("cache_control"):
                continue
            records.append(
                {
                    "type": str(block.get("type") or "text"),
                    "text": str(block.get("text") or ""),
                }
            )
    return _stable_hash(records)


def tool_schema_hash(tool_schema: Any) -> str:
    return _stable_hash(tool_schema or {})


def _stable_hash(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _normalize_request_kind_for_cache(request_kind: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", str(request_kind or "").lower()).strip("_")
    return cleaned or "default"


def _kind_short(request_kind: str) -> str:
    known = {
        "tool_call": "tool",
        "hypothesis": "hyp",
        "code": "code",
    }
    if request_kind in known:
        return known[request_kind]
    compact = re.sub(r"[^a-z0-9]+", "", request_kind.lower())
    return compact[:12] or "default"
