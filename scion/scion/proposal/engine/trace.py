"""Direct V3 prompt/response trace persistence."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Mapping

from scion.proposal.prompt_manifest_accounting import _provider_prompt_hash


class _TraceWriter:
    """Persist the exact provider request and its terminal response."""

    def __init__(self, trace_dir: str | None) -> None:
        self._trace_dir = trace_dir

    def write_start(
        self,
        *,
        request_kind: str,
        model: str,
        tool: Dict[str, Any],
        prompt: str,
        system_blocks: list[dict],
        context: Dict[str, Any],
        request_policy: Dict[str, Any] | None = None,
        provider_call_attempt: Mapping[str, Any] | None = None,
    ) -> str | None:
        if not self._trace_dir:
            return None
        os.makedirs(self._trace_dir, exist_ok=True)
        prompt_hash = _prompt_hash(system_blocks, prompt)
        trace_id = (
            f"{datetime.now().strftime('%Y%m%dT%H%M%S%f')}_"
            f"{request_kind}_{prompt_hash[:10]}_{uuid.uuid4().hex[:8]}"
        )
        path = os.path.join(self._trace_dir, f"{trace_id}.json")
        prompt_manifest = context.get("_scion_prompt_manifest")
        payload: Dict[str, Any] = {
            "trace_id": trace_id,
            "request_kind": request_kind,
            "model": model,
            "tool_name": tool.get("name"),
            "prompt_hash": prompt_hash,
            "created_at": datetime.now().isoformat(),
            "branch_id": context.get("branch_id"),
            "champion_version": context.get("champion_version"),
            "system_blocks": system_blocks,
            "user_prompt": prompt,
            "tool_schema": tool.get("input_schema")
            or tool.get("function", {}).get("parameters"),
            "ok": None,
        }
        if isinstance(prompt_manifest, Mapping):
            payload["prompt_manifest"] = dict(prompt_manifest)
        if request_policy:
            payload["request_policy"] = dict(request_policy)
        if provider_call_attempt:
            payload["provider_call_attempt"] = dict(provider_call_attempt)
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
        payload.update({"finished_at": datetime.now().isoformat(), "ok": ok})
        if response is not None:
            payload["response"] = response
        if error is not None:
            payload["error"] = error
        if llm_usage is not None:
            payload["llm_usage"] = llm_usage
        _write_json(path, payload)


def _prompt_hash(system_blocks: list[dict], prompt: str) -> str:
    return _provider_prompt_hash(system_blocks, prompt)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)


def _client_request_policy(
    client: Any,
    *,
    request_kind: str,
    tool: Dict[str, Any],
    model: str,
) -> Dict[str, Any]:
    resolver = getattr(client, "resolve_request_policy", None)
    if not callable(resolver):
        return {}
    policy = resolver(request_kind=request_kind, tool=tool, model=model)
    return dict(policy) if isinstance(policy, Mapping) else {}


__all__ = [
    "_TraceWriter",
    "_client_request_policy",
    "_prompt_hash",
    "_write_json",
]
