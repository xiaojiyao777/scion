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
        _write_json(path, payload)


def _prompt_hash(system_blocks: "list[dict]", prompt: str) -> str:
    blob = json.dumps(
        {"system_blocks": system_blocks, "user_prompt": prompt},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


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
