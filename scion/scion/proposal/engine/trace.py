"""Direct V3 prompt/response trace persistence."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Mapping


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
        provider_call_context: Mapping[str, Any] | None = None,
    ) -> str | None:
        if not self._trace_dir:
            return None
        os.makedirs(self._trace_dir, exist_ok=True)
        trace_id = (
            f"{datetime.now().strftime('%Y%m%dT%H%M%S%f')}_"
            f"{request_kind}_{uuid.uuid4().hex[:8]}"
        )
        path = os.path.join(self._trace_dir, f"{trace_id}.json")
        payload: Dict[str, Any] = {
            "trace_id": trace_id,
            "request_kind": request_kind,
            "model": model,
            "tool_name": tool.get("name"),
            "created_at": datetime.now().isoformat(),
            "branch_id": context.get("branch_id"),
            "champion_version": context.get("champion_version"),
            "structured_context": context,
            "system_blocks": system_blocks,
            "user_prompt": prompt,
            "tool_schema": tool.get("input_schema")
            or tool.get("function", {}).get("parameters"),
            "ok": None,
        }
        if request_policy:
            payload["request_policy"] = dict(request_policy)
        if provider_call_context:
            payload["provider_call_context"] = dict(provider_call_context)
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
        provider_response_diagnostics: Mapping[str, Any] | None = None,
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
        if provider_response_diagnostics is not None:
            payload["provider_response_diagnostics"] = dict(
                provider_response_diagnostics
            )
        _write_json(path, payload)


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
    "_write_json",
]
