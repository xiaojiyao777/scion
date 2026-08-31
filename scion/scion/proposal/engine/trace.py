"""Direct V3 prompt/response trace persistence."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, Mapping


class _TraceWriter:
    """Atomically persist one optional terminal provider diagnostic."""

    def __init__(self, trace_dir: str | None) -> None:
        self._trace_dir = trace_dir

    def write_terminal(
        self,
        *,
        request_kind: str,
        model: str,
        tool: Dict[str, Any],
        prompt: str,
        system_blocks: list[dict],
        context: Dict[str, Any],
        ok: bool,
        started_at: str,
        response: Dict[str, Any] | None = None,
        error: str | None = None,
        error_type: str | None = None,
        llm_usage: Dict[str, Any] | None = None,
        request_policy: Dict[str, Any] | None = None,
        provider_response_diagnostics: Mapping[str, Any] | None = None,
        attempt_index: int | None = None,
    ) -> str | None:
        if not self._trace_dir:
            return None
        os.makedirs(self._trace_dir, exist_ok=True)
        file_stem = (
            f"{datetime.now().strftime('%Y%m%dT%H%M%S%f')}_"
            f"{request_kind}_{uuid.uuid4().hex[:8]}"
        )
        path = os.path.join(self._trace_dir, f"{file_stem}.json")
        payload: Dict[str, Any] = {
            "request_kind": request_kind,
            "model": model,
            "tool_name": tool.get("name"),
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(),
            **({"branch_id": context["branch_id"]} if "branch_id" in context else {}),
            **(
                {"champion_version": context["champion_version"]}
                if "champion_version" in context
                else {}
            ),
            "structured_context": context,
            "system_blocks": system_blocks,
            "user_prompt": prompt,
            "tool_schema": tool.get("input_schema")
            or tool.get("function", {}).get("parameters"),
            "ok": ok,
        }
        if attempt_index is not None:
            payload["attempt_index"] = attempt_index
        if response is not None:
            payload["response"] = response
        if error is not None:
            payload["error"] = error
        if error_type is not None:
            payload["error_type"] = error_type
        if llm_usage is not None:
            payload["llm_usage"] = llm_usage
        if request_policy:
            payload["request_policy"] = dict(request_policy)
        if provider_response_diagnostics is not None:
            payload["provider_response_diagnostics"] = dict(
                provider_response_diagnostics
            )
        _write_json_atomic(path, payload)
        return path


def _write_json_atomic(path: str, payload: Dict[str, Any]) -> None:
    """Publish one complete JSON value without exposing a partial trace."""

    directory = os.path.dirname(path)
    fd, temporary_path = tempfile.mkstemp(
        dir=directory,
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


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
    "_write_json_atomic",
]
