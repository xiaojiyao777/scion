"""Prompt/response tracing helpers for the proposal engine."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Mapping


class _TraceWriter:
    """Persist prompt/response artifacts for experiment auditability."""

    def __init__(self, trace_dir: str | None) -> None:
        self._trace_dir = trace_dir

    def write_start(
        self,
        *,
        request_kind: str,
        model: str,
        tool: Dict[str, Any],
        prompt: str,
        system_blocks: "list[dict]",
        context: Dict[str, Any],
        request_policy: Dict[str, Any] | None = None,
    ) -> str | None:
        if not self._trace_dir:
            return None
        os.makedirs(self._trace_dir, exist_ok=True)
        digest = _prompt_hash(system_blocks, prompt)
        trace_id = (
            f"{datetime.now().strftime('%Y%m%dT%H%M%S%f')}_"
            f"{request_kind}_{digest[:10]}_{uuid.uuid4().hex[:8]}"
        )
        path = os.path.join(self._trace_dir, f"{trace_id}.json")
        payload = {
            "trace_id": trace_id,
            "request_kind": request_kind,
            "model": model,
            "tool_name": tool.get("name"),
            "prompt_hash": digest,
            "prompt_cache_audit": _prompt_cache_audit(
                system_blocks=system_blocks,
                user_prompt=prompt,
                tool_schema=tool.get("input_schema")
                or tool.get("function", {}).get("parameters"),
            ),
            "created_at": datetime.now().isoformat(),
            "branch_id": context.get("branch_id"),
            "champion_version": context.get("champion_version"),
            "system_blocks": system_blocks,
            "user_prompt": prompt,
            "tool_schema": tool.get("input_schema")
            or tool.get("function", {}).get("parameters"),
            "ok": None,
        }
        if request_policy:
            payload["request_policy"] = request_policy
        _write_json(path, payload)
        return path

    def write_finish(
        self,
        path: str | None,
        *,
        ok: bool,
        response: Dict[str, Any] | None = None,
        error: str | None = None,
        llm_usage: Dict[str, Any] | None = None,
    ) -> None:
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            payload = {}
        payload.update(
            {
                "finished_at": datetime.now().isoformat(),
                "ok": ok,
            }
        )
        if response is not None:
            payload["response"] = response
        if error is not None:
            payload["error"] = error
        if llm_usage is not None:
            payload["llm_usage"] = llm_usage
        _write_json(path, payload)


def _prompt_hash(system_blocks: "list[dict]", prompt: str) -> str:
    blob = json.dumps(
        {"system_blocks": system_blocks, "user_prompt": prompt},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _prompt_cache_audit(
    *,
    system_blocks: "list[dict]",
    user_prompt: str,
    tool_schema: Any,
) -> Dict[str, Any]:
    schema_blob = json.dumps(tool_schema or {}, sort_keys=True, default=str)
    block_records: list[dict[str, Any]] = []
    cacheable_chars = 0
    for index, block in enumerate(system_blocks or [], start=1):
        text = block.get("text", "") if isinstance(block, Mapping) else str(block)
        cache_control = (
            dict(block.get("cache_control") or {})
            if isinstance(block, Mapping)
            else {}
        )
        cacheable = bool(cache_control)
        if cacheable:
            cacheable_chars += len(text)
        block_records.append(
            {
                "block_index": index,
                "chars": len(text),
                "hash": _short_hash(text),
                "cacheable": cacheable,
                "cache_control": cache_control,
            }
        )
    cacheable_blocks = [record for record in block_records if record["cacheable"]]
    return {
        "system_block_count": len(block_records),
        "cache_control_block_count": len(cacheable_blocks),
        "cacheable_system_chars": cacheable_chars,
        "system_blocks": block_records,
        "cacheable_system_blocks_hash": _short_hash(
            json.dumps(cacheable_blocks, sort_keys=True, default=str)
        ),
        "system_blocks_hash": _short_hash(
            json.dumps(block_records, sort_keys=True, default=str)
        ),
        "tool_schema_chars": len(schema_blob),
        "tool_schema_hash": _short_hash(schema_blob),
        "user_prompt_chars": len(user_prompt or ""),
        "user_prompt_hash": _short_hash(user_prompt or ""),
        "cache_prefix_order": "tools -> system -> messages",
        "cache_strategy_note": (
            "Anthropic prompt caching matches the stable prefix through explicit "
            "cache_control breakpoints; dynamic user prompt content is outside "
            "the cacheable system blocks."
        ),
    }


def _short_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)


def _client_request_policy(
    client: Any,
    *,
    request_kind: str,
    tool: Dict[str, Any],
) -> Dict[str, Any] | None:
    resolver = getattr(client, "resolve_request_policy", None)
    if resolver is None:
        return None
    try:
        policy = resolver(request_kind=request_kind, tool=tool)
    except Exception:
        return None
    return dict(policy) if isinstance(policy, Mapping) else None
