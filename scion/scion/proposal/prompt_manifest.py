"""Immutable audit manifest for the exact direct-V3 provider prompt."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from scion.proposal.prompt_manifest_accounting import _provider_prompt_hash


MANIFEST_SCHEMA_VERSION = "api-visible-prompt-manifest.v4"


def stable_digest(value: Any, *, length: int = 16) -> str:
    """Digest the complete value without prompt filtering or compaction."""

    rendered = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_json_default,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:length]


def build_api_visible_prompt_manifest(
    *,
    session_id: str,
    phase: str,
    call_kind: str,
    prompt_context: Mapping[str, Any],
    observations: tuple[Any, ...] | list[Any],
    call_index: int,
    system_blocks: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] | None = None,
    user_prompt: str | None = None,
    render_error: str | None = None,
    context_digest_override: str | None = None,
    authoritative_context_ref: str | None = None,
) -> dict[str, Any]:
    """Record identity and exact byte-size facts for one provider call."""

    rendered_system_blocks = tuple(system_blocks or ())
    system_texts = tuple(
        str(block.get("text") or "")
        if isinstance(block, Mapping)
        else str(block)
        for block in rendered_system_blocks
    )
    rendered_user_prompt = "" if user_prompt is None else str(user_prompt)
    rendered_available = user_prompt is not None and render_error is None
    context_digest = context_digest_override or stable_digest(
        prompt_context,
        length=64,
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifact_kind": "api_visible_prompt_manifest",
        "session_id": str(session_id),
        "phase": str(phase),
        "call_kind": str(call_kind),
        "call_index": int(call_index),
        "authoritative_context_ref": authoritative_context_ref,
        "context_digest": context_digest,
        "context_keys": sorted(str(key) for key in prompt_context),
        "prompt_hash": _provider_prompt_hash(
            rendered_system_blocks,
            rendered_user_prompt,
        ),
        "rendered_prompt_available": rendered_available,
        "render_error": str(render_error or ""),
        "provider_visible_size": {
            "system_block_count": len(rendered_system_blocks),
            "system_text_chars": sum(len(text) for text in system_texts),
            "user_prompt_chars": len(rendered_user_prompt),
            "total_chars": (
                sum(len(text) for text in system_texts)
                + len(rendered_user_prompt)
            ),
        },
        "observation_count": len(observations),
        "projection": "direct_v3_lossless",
    }


def _json_default(value: Any) -> Any:
    primitive = getattr(value, "to_primitive", None)
    if callable(primitive):
        return primitive()
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    state = getattr(value, "__dict__", None)
    if isinstance(state, Mapping):
        return dict(state)
    return str(value)


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "build_api_visible_prompt_manifest",
    "stable_digest",
]
