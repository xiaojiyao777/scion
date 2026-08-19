"""Provider calls with one best-effort terminal trace for direct V3."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

from scion.core.resource_envelope import ProviderCallBudget
from scion.proposal.llm.errors import LLMFormatError

from .trace import _client_request_policy, _TraceWriter


class ProviderResponseSizeExceeded(LLMFormatError):
    """Raised before tracing a provider value beyond an explicit call bound."""


@dataclass(frozen=True)
class PromptTurnSnapshot:
    """One immutable rendering shared by trace and provider call."""

    render_kind: str
    system_blocks: tuple[Mapping[str, Any], ...]
    user_prompt: str
    provider_tool: Mapping[str, Any]
    structured_context_json: str
    allowed_change_loci: tuple[str, ...] = ()

    @property
    def structured_context(self) -> dict[str, Any]:
        """Return the one frozen structured input used by trace and parsing."""

        value = json.loads(self.structured_context_json)
        if not isinstance(value, dict):
            raise TypeError("prompt turn context is not a mapping")
        return value


class ProviderCaller:
    """Perform one provider request while preserving request/response traces."""

    def __init__(
        self,
        client: Any,
        model: str,
        *,
        trace_dir: str | None,
        provider_call_budget: ProviderCallBudget | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._trace_dir = trace_dir
        self._provider_call_budget = provider_call_budget

    def call(
        self,
        *,
        request_kind: str,
        tool: Dict[str, Any],
        snapshot: PromptTurnSnapshot,
        max_response_bytes: int | None = None,
    ) -> Dict[str, Any]:
        """Call once, write one terminal trace, and return the provider value."""

        if max_response_bytes is not None and (
            isinstance(max_response_bytes, bool)
            or not isinstance(max_response_bytes, int)
            or max_response_bytes <= 0
        ):
            raise ValueError("max_response_bytes must be a positive integer or null")
        if self._provider_call_budget is not None:
            self._provider_call_budget.consume(request_kind=request_kind)
        _reset_client_call_observations(self._client)
        structured_context = snapshot.structured_context

        rendered_system_blocks = [dict(block) for block in snapshot.system_blocks]
        trace = _TraceWriter(self._trace_dir)
        request_policy = _client_request_policy(
            self._client,
            request_kind=request_kind,
            tool=tool,
            model=self._model,
        )
        started_at = datetime.now().isoformat()
        try:
            raw = self._call_provider(
                request_kind=request_kind,
                prompt=snapshot.user_prompt,
                tool=tool,
                system_blocks=rendered_system_blocks,
            )
        except KeyboardInterrupt as exc:
            response_diagnostics = _client_response_diagnostics(self._client)
            _write_terminal_trace_best_effort(
                trace,
                request_kind=request_kind,
                model=self._model,
                tool=tool,
                prompt=snapshot.user_prompt,
                system_blocks=rendered_system_blocks,
                context=structured_context,
                started_at=started_at,
                client=self._client,
                ok=False,
                error="provider_call_interrupted",
                error_type=type(exc).__name__,
                request_policy=request_policy,
                provider_response_diagnostics=response_diagnostics,
            )
            raise
        except Exception as exc:
            response_diagnostics = _client_response_diagnostics(self._client)
            _write_terminal_trace_best_effort(
                trace,
                request_kind=request_kind,
                model=self._model,
                tool=tool,
                prompt=snapshot.user_prompt,
                system_blocks=rendered_system_blocks,
                context=structured_context,
                started_at=started_at,
                client=self._client,
                ok=False,
                error=str(exc),
                error_type=type(exc).__name__,
                request_policy=request_policy,
                provider_response_diagnostics=response_diagnostics,
            )
            raise

        if max_response_bytes is not None and _json_size_exceeds(
            raw, max_response_bytes
        ):
            error = ProviderResponseSizeExceeded(
                "provider response exceeds explicit byte bound: "
                f"max_response_bytes={max_response_bytes}"
            )
            _write_terminal_trace_best_effort(
                trace,
                request_kind=request_kind,
                model=self._model,
                tool=tool,
                prompt=snapshot.user_prompt,
                system_blocks=rendered_system_blocks,
                context=structured_context,
                started_at=started_at,
                client=self._client,
                ok=False,
                error=str(error),
                error_type=type(error).__name__,
                request_policy=request_policy,
                provider_response_diagnostics=None,
            )
            raise error

        response_diagnostics = _client_response_diagnostics(self._client)
        _write_terminal_trace_best_effort(
            trace,
            request_kind=request_kind,
            model=self._model,
            tool=tool,
            prompt=snapshot.user_prompt,
            system_blocks=rendered_system_blocks,
            context=structured_context,
            started_at=started_at,
            client=self._client,
            ok=True,
            response=raw,
            request_policy=request_policy,
            provider_response_diagnostics=response_diagnostics,
        )
        return raw

    def _call_provider(
        self,
        *,
        request_kind: str,
        prompt: str,
        tool: Dict[str, Any],
        system_blocks: list[dict[str, Any]],
    ) -> Dict[str, Any]:
        return self._client.call_with_tool(
            prompt,
            tool,
            self._model,
            system_blocks=system_blocks,
            request_kind=request_kind,
        )


def _write_terminal_trace_best_effort(
    trace: _TraceWriter,
    *,
    request_kind: str,
    model: str,
    tool: Dict[str, Any],
    prompt: str,
    system_blocks: list[dict[str, Any]],
    context: Dict[str, Any],
    started_at: str,
    client: Any,
    ok: bool,
    response: Dict[str, Any] | None = None,
    error: str | None = None,
    error_type: str | None = None,
    request_policy: Dict[str, Any] | None = None,
    provider_response_diagnostics: Mapping[str, Any] | None,
) -> None:
    try:
        trace.write_terminal(
            request_kind=request_kind,
            model=model,
            tool=tool,
            prompt=prompt,
            system_blocks=system_blocks,
            context=context,
            ok=ok,
            started_at=started_at,
            response=response,
            error=error,
            error_type=error_type,
            llm_usage=_client_usage_metadata(client),
            request_policy=request_policy,
            provider_response_diagnostics=provider_response_diagnostics,
        )
    except BaseException:  # tracing must not change the provider result
        return


def _client_usage_metadata(client: Any) -> Dict[str, Any] | None:
    getter = getattr(client, "get_last_usage_metadata", None)
    if not callable(getter):
        return None
    try:
        usage = getter()
    except Exception:
        return None
    return dict(usage) if isinstance(usage, dict) else None


def _reset_client_call_observations(client: Any) -> None:
    reset = getattr(client, "reset_call_observations", None)
    if not callable(reset):
        return
    try:
        reset()
    except Exception:  # noqa: BLE001 - observations must not affect provider behavior
        return


def _client_response_diagnostics(client: Any) -> dict[str, Any] | None:
    getter = getattr(client, "get_last_response_diagnostics", None)
    if not callable(getter):
        return None
    try:
        diagnostics = getter()
    except Exception:  # noqa: BLE001 - diagnostics must not affect provider behavior
        return None
    return dict(diagnostics) if isinstance(diagnostics, Mapping) else None


def _json_size_exceeds(value: Any, maximum: int) -> bool:
    """Return early when a JSON-compatible value exceeds an encoded bound."""

    total = 0
    stack = [value]
    seen_containers: set[int] = set()
    while stack:
        item = stack.pop()
        if item is None:
            total += 4
        elif item is True:
            total += 4
        elif item is False:
            total += 5
        elif isinstance(item, str):
            total += _json_string_size(item)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            total += len(str(item).encode("utf-8"))
        elif isinstance(item, Mapping):
            item_id = id(item)
            if item_id in seen_containers:
                return True
            seen_containers.add(item_id)
            total += 2 + max(0, len(item) - 1)
            for key, child in item.items():
                if not isinstance(key, str):
                    return True
                total += _json_string_size(key) + 1
                stack.append(child)
        elif isinstance(item, (list, tuple)):
            item_id = id(item)
            if item_id in seen_containers:
                return True
            seen_containers.add(item_id)
            total += 2 + max(0, len(item) - 1)
            stack.extend(item)
        else:
            return True
        if total > maximum:
            return True
    return False


def _json_string_size(value: str) -> int:
    size = 2
    for char in value:
        codepoint = ord(char)
        if char in {'"', "\\"}:
            size += 2
        elif codepoint < 0x20:
            size += 6
        elif codepoint <= 0x7F:
            size += 1
        elif codepoint <= 0xFFFF:
            size += 6
        else:
            size += 12
    return size


__all__ = [
    "PromptTurnSnapshot",
    "ProviderCaller",
    "ProviderResponseSizeExceeded",
]
