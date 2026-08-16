"""Provider transport methods for LLMClient."""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
from typing import Any, Dict

from .config import (
    _ANTHROPIC_REQUIRED_MAX_TOKENS,
    _is_deepseek_model,
    _is_gpt_codex_model,
    _is_openai_model,
    _normalize_request_kind,
)
from .errors import (
    LLMAuthError,
    LLMBalanceError,
    LLMError,
    LLMFormatError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransportError,
    _is_timeout_error_text,
    _is_transient_provider_error,
    _parse_retry_after,
)

logger = logging.getLogger(__name__)


def _serialized_argument_diagnostics(arguments: Any) -> tuple[int | None, bool]:
    """Describe an SDK-parsed argument value using one explicit encoding."""
    try:
        encoded = json.dumps(
            arguments,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except Exception:  # noqa: BLE001 - observation must not affect provider behavior
        return None, False
    return _utf8_size(encoded), True


def _utf8_size(value: str) -> int | None:
    try:
        return len(value.encode("utf-8"))
    except UnicodeError:
        return None


def _openai_argument_observations(arguments: Any) -> dict[str, Any]:
    observations: dict[str, Any] = {
        "arguments_value_type": type(arguments).__name__
    }
    if isinstance(arguments, str):
        observations["arguments_representation"] = "sdk_argument_string_utf8"
        arguments_bytes = _utf8_size(arguments)
    elif isinstance(arguments, bytes):
        observations["arguments_representation"] = "sdk_argument_bytes"
        arguments_bytes = len(arguments)
    elif isinstance(arguments, bytearray):
        observations["arguments_representation"] = "sdk_argument_bytearray"
        arguments_bytes = len(arguments)
    else:
        arguments_bytes = None
    if arguments_bytes is not None:
        observations["selected_arguments_bytes"] = arguments_bytes
    return observations


class TransportMixin:
    def close_provider_clients(self) -> None:
        """Close cached provider SDK clients and release their HTTP transports."""
        errors: list[Exception] = []
        for attr in ("_openai_client", "_anthropic_client"):
            client = getattr(self, attr, None)
            if client is None:
                continue
            try:
                self._close_provider_client(client)
            except Exception as exc:
                errors.append(exc)
            finally:
                setattr(self, attr, None)
        if errors:
            raise LLMError(
                "Failed to close one or more LLM provider clients"
            ) from errors[0]

    @staticmethod
    def _close_provider_client(client: Any) -> None:
        close = getattr(client, "close", None)
        if callable(close):
            close_result = close()
        else:
            aclose = getattr(client, "aclose", None)
            close_result = aclose() if callable(aclose) else None
        if inspect.isawaitable(close_result):
            asyncio.run(close_result)

    def _tool_call_once(
        self,
        prompt: str,
        tool: Dict[str, Any],
        model: str,
        system_blocks: "list[dict] | None",
        timeout_sec: float,
    ) -> Dict[str, Any]:
        """Execute one tool call and return the provider's typed payload."""
        if _is_openai_model(model):
            return self._tool_call_once_openai(
                prompt,
                tool,
                model,
                system_blocks,
                timeout_sec,
            )
        return self._tool_call_once_anthropic(
            prompt,
            tool,
            model,
            system_blocks,
            timeout_sec,
        )

    def _tool_call_once_anthropic(
        self, prompt, tool, model, system_blocks, timeout_sec,
    ) -> Dict[str, Any]:
        client = self._get_anthropic_client()
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": _ANTHROPIC_REQUIRED_MAX_TOKENS,
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": tool["name"]},
            "messages": [{"role": "user", "content": prompt}],
            "timeout": timeout_sec,
        }
        if system_blocks:
            kwargs["system"] = system_blocks

        response = client.messages.create(**kwargs)

        content = response.content
        tool_blocks = [
            block
            for block in content
            if hasattr(block, "type") and block.type == "tool_use"
        ]
        stop_reason = getattr(response, "stop_reason", None)
        response_diagnostics: dict[str, Any] = {
            "provider": "anthropic",
            "tool_call_count": len(tool_blocks),
            "tool_call_count_scope": "response.content[type=tool_use]",
        }
        if stop_reason is not None:
            response_diagnostics["stop_reason"] = str(stop_reason)
        self._last_response_diagnostics = response_diagnostics

        usage = getattr(response, "usage", None)
        if usage:
            self._record_anthropic_usage(
                usage,
                model=model,
                request_kind=_normalize_request_kind(tool=tool) or "tool_call",
            )

        for tool_call_index, block in enumerate(tool_blocks):
            if block.name == tool["name"]:
                arguments_bytes, arguments_json_valid = (
                    _serialized_argument_diagnostics(block.input)
                )
                response_diagnostics.update(
                    {
                        "selected_tool_call_index": tool_call_index,
                        "selected_tool_call_index_scope": (
                            "response.content[type=tool_use]"
                        ),
                        "selected_tool_name": str(block.name),
                        "selected_arguments_json_valid": arguments_json_valid,
                        "arguments_representation": (
                            "compact_json_utf8_from_sdk_parsed_input"
                        ),
                    }
                )
                if arguments_bytes is not None:
                    response_diagnostics["selected_arguments_bytes"] = arguments_bytes
                return block.input

        raise LLMFormatError(
            f"LLM did not call tool '{tool['name']}'. Stop reason: {stop_reason}"
        )

    def _tool_call_once_openai(
        self, prompt, tool, model, system_blocks, timeout_sec,
    ) -> Dict[str, Any]:
        client = self._get_openai_client()
        # Merge system blocks into user prompt to avoid incompatibility
        # (some models like minimax reject system messages + tool_use together)
        user_content = prompt
        if system_blocks:
            sys_parts = []
            for block in system_blocks:
                text = block.get("text", "") if isinstance(block, dict) else str(block)
                if text:
                    sys_parts.append(text)
            if sys_parts:
                user_content = "\n\n".join(sys_parts) + "\n\n---\n\n" + prompt
        messages: list[Dict[str, Any]] = [{"role": "user", "content": user_content}]

        tool_name = tool["name"]
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        }

        response = client.chat.completions.create(
            **self._openai_chat_kwargs(
                model=model,
                messages=messages,
                timeout_sec=timeout_sec,
                tools=[openai_tool],
                tool_choice={"type": "function", "function": {"name": tool_name}},
            )
        )

        choices = response.choices
        response_diagnostics: dict[str, Any] = {
            "provider": "openai_compatible",
            "choice_count": len(choices),
            "choice_count_scope": "response.choices",
        }
        self._last_response_diagnostics = response_diagnostics

        usage = response.usage
        if usage:
            self._record_openai_usage(
                usage,
                model=model,
                request_kind=_normalize_request_kind(tool=tool) or "tool_call",
            )

        choice = choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None)
        response_diagnostics.update(
            {
                "tool_call_count": len(tool_calls or ()),
                "tool_call_count_scope": "response.choices[0].message.tool_calls",
                "selected_choice_index": 0,
                "selected_choice_index_scope": "response.choices",
            }
        )
        if choice.finish_reason is not None:
            response_diagnostics["finish_reason"] = str(choice.finish_reason)
        if not tool_calls:
            raise LLMFormatError(
                f"LLM did not call tool '{tool_name}'. "
                f"Finish reason: {choice.finish_reason}"
            )
        selected_tool_call = tool_calls[0]
        arguments = selected_tool_call.function.arguments
        response_diagnostics.update(
            {
                "selected_tool_call_index": 0,
                "selected_tool_call_index_scope": (
                    "response.choices[0].message.tool_calls"
                ),
                **_openai_argument_observations(arguments),
            }
        )
        selected_tool_name = getattr(selected_tool_call.function, "name", None)
        if selected_tool_name is not None:
            response_diagnostics["selected_tool_name"] = str(selected_tool_name)
        try:
            result = json.loads(arguments)
        except (TypeError, json.JSONDecodeError) as exc:
            response_diagnostics["selected_arguments_json_valid"] = False
            raise LLMFormatError(
                f"LLM tool '{tool_name}' returned invalid JSON arguments. "
                f"Finish reason: {choice.finish_reason}"
            ) from exc
        response_diagnostics["selected_arguments_json_valid"] = True
        return result

    def _openai_chat_kwargs(
        self,
        *,
        model: str,
        messages: list[Dict[str, Any]],
        timeout_sec: float,
        tools: list[Dict[str, Any]] | None = None,
        tool_choice: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "timeout": timeout_sec,
        }
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None and not _is_deepseek_model(str(model or "")):
            kwargs["tool_choice"] = tool_choice
        reasoning_effort = self._openai_reasoning_effort(model)
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        extra_body = self._openai_extra_body(model)
        if extra_body:
            kwargs["extra_body"] = extra_body
        return kwargs

    def _openai_reasoning_effort(self, model: str) -> str:
        effort = self.reasoning_effort
        if not effort:
            return ""
        normalized = effort.lower()
        model_id = str(model or "")
        if _is_deepseek_model(model_id):
            if normalized == "xhigh":
                normalized = "max"
            elif normalized in {"low", "medium"}:
                normalized = "high"
            if normalized not in {"high", "max"}:
                return ""
            return normalized
        if _is_gpt_codex_model(model_id):
            if normalized not in {"low", "medium", "high", "xhigh"}:
                return ""
            return normalized
        return ""

    def _openai_extra_body(self, model: str) -> Dict[str, Any]:
        if not _is_deepseek_model(str(model or "")):
            return {}
        if not self._openai_reasoning_effort(model):
            return {}
        return {"thinking": {"type": "enabled"}}

    @staticmethod
    def _openai_cache_usage(usage: Any) -> tuple[int, int]:
        cache_read = TransportMixin._get_usage_int(usage, "prompt_cache_hit_tokens")
        cache_miss = TransportMixin._get_usage_int(usage, "prompt_cache_miss_tokens")
        nested_cached = TransportMixin._get_usage_int(
            usage,
            "cached_tokens",
            parent="prompt_tokens_details",
        )
        if nested_cached and not cache_read:
            cache_read = nested_cached
        if cache_read and not cache_miss:
            prompt_tokens = TransportMixin._get_usage_int(usage, "prompt_tokens")
            if prompt_tokens > cache_read:
                cache_miss = prompt_tokens - cache_read
        return cache_read, cache_miss

    @staticmethod
    def _get_usage_int(usage: Any, key: str, *, parent: str | None = None) -> int:
        source = usage
        if parent:
            if isinstance(source, dict):
                source = source.get(parent)
            else:
                source = getattr(source, parent, None)
        if source is None:
            return 0
        if isinstance(source, dict):
            value = source.get(key, 0)
        else:
            value = getattr(source, key, 0)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _record_anthropic_usage(
        self,
        usage: Any,
        *,
        model: str,
        request_kind: str,
    ) -> None:
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        cache_create = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        self._last_usage_metadata = {
            "provider": "anthropic",
            "model": model,
            "request_kind": request_kind,
            "cache_mode": "explicit_cache_control",
            "cache_accounting_mode": "anthropic_explicit_cache_tokens",
            "input_tokens": input_tokens,
            "prompt_tokens_total": input_tokens + cache_create + cache_read,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": cache_create,
            "cache_read_input_tokens": cache_read,
            "cache_miss_input_tokens": input_tokens,
        }

    def _record_openai_usage(
        self,
        usage: Any,
        *,
        model: str,
        request_kind: str,
    ) -> None:
        cache_read, cache_miss = self._openai_cache_usage(usage)
        prompt_tokens_total = self._get_usage_int(usage, "prompt_tokens")
        output_tokens = self._get_usage_int(usage, "completion_tokens")
        reasoning_tokens = self._get_usage_int(
            usage,
            "reasoning_tokens",
            parent="completion_tokens_details",
        )
        if cache_read and not cache_miss and prompt_tokens_total > cache_read:
            cache_miss = prompt_tokens_total - cache_read
        cache_mode = (
            "automatic_prefix_cache_observed"
            if cache_read or cache_miss
            else "automatic_prefix_cache_attempted"
        )
        self._last_usage_metadata = {
            "provider": "openai_compatible",
            "model": model,
            "request_kind": request_kind,
            "cache_mode": cache_mode,
            "cache_accounting_mode": "provider_prompt_tokens_include_cache_read",
            "input_tokens": prompt_tokens_total,
            "prompt_tokens_total": prompt_tokens_total,
            "output_tokens": output_tokens,
            "reasoning_output_tokens": reasoning_tokens,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": cache_read,
            "cache_miss_input_tokens": cache_miss,
            "prompt_cache_hit": bool(cache_read),
            "prompt_cache_miss": bool(cache_miss),
            "prompt_cache_hit_tokens": cache_read,
            "prompt_cache_miss_tokens": cache_miss,
        }
    @staticmethod
    def _raise_classified(exc: Exception) -> None:
        """Classify one raw SDK exception at the transport boundary."""
        if isinstance(exc, LLMError):
            raise exc
        raw_error = str(exc)
        err_str = raw_error.lower()
        status_code = _provider_status_code(exc, raw_error=raw_error)
        type_name = type(exc).__name__.lower()

        if (
            status_code == 408
            or isinstance(exc, TimeoutError)
            or "timeout" in type_name
            or _is_timeout_error_text(err_str)
        ):
            raise LLMTimeoutError(f"Request timed out: {exc}") from exc
        if status_code == 403 and _is_balance_error_text(err_str):
            raise LLMBalanceError(f"API balance exhausted: {exc}") from exc
        if status_code in {401, 403} or _is_auth_error_text(err_str):
            raise LLMAuthError(f"API authentication failed: {exc}") from exc
        if status_code == 429 or "rate_limit" in err_str or "ratelimit" in err_str:
            retry_after = _parse_retry_after(exc)
            raise LLMRateLimitError(f"Rate limited: {exc}", retry_after=retry_after) from exc
        if _is_transport_exception(exc, err_str=err_str, type_name=type_name):
            raise LLMTransportError(f"Provider transport failed: {exc}") from exc
        if (status_code is not None and 500 <= status_code <= 599) or (
            _is_transient_provider_error(err_str)
        ):
            raise LLMProviderError(f"Provider request failed: {exc}") from exc
        raise LLMError(f"API error: {exc}") from exc

    def _get_anthropic_client(self) -> Any:
        if self._anthropic_client is not None:
            return self._anthropic_client
        try:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                max_retries=0,
            )
            logger.info(
                "Anthropic client initialized: model=%s base_url=%s sdk_retries=disabled",
                self.model,
                self.base_url,
            )
            return self._anthropic_client
        except ImportError as exc:
            raise LLMError(
                "The 'anthropic' package is not installed. "
                "Use MockLLMClient for tests, or: pip install anthropic"
            ) from exc

    def _get_openai_client(self) -> Any:
        if self._openai_client is not None:
            return self._openai_client
        try:
            import openai
            base = self.base_url.rstrip("/")
            if "api.deepseek.com" in base:
                base = "https://api.deepseek.com" if base.endswith("/v1") else base
            elif not base.endswith("/v1"):
                base += "/v1"
            self._openai_client = openai.OpenAI(
                api_key=self.api_key,
                base_url=base,
                max_retries=0,
            )
            logger.info(
                "OpenAI client initialized: model=%s base_url=%s sdk_retries=disabled",
                self.model,
                base,
            )
            return self._openai_client
        except ImportError as exc:
            raise LLMError(
                "The 'openai' package is not installed. pip install openai"
            ) from exc


def _provider_status_code(exc: Exception, *, raw_error: str) -> int | None:
    value = getattr(exc, "status_code", None)
    if value is None:
        response = getattr(exc, "response", None)
        value = getattr(response, "status_code", None)
    if value is not None:
        try:
            return int(value)
        except (TypeError, ValueError):
            pass
    match = re.search(
        r"(?:error|status)\s+code\s*:\s*(\d{3})|\bhttp\s+(\d{3})\b",
        raw_error,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    return int(match.group(1) or match.group(2))


def _is_balance_error_text(err_str: str) -> bool:
    return any(
        marker in err_str
        for marker in (
            "insufficient balance",
            "balance is insufficient",
            "balance exhausted",
            "credit balance",
            "no credits",
            "please recharge",
        )
    )


def _is_auth_error_text(err_str: str) -> bool:
    return any(
        marker in err_str
        for marker in (
            "invalid api key",
            "invalid_api_key",
            "authentication failed",
            "authentication error",
            "unauthorized",
            "forbidden",
        )
    )


def _is_transport_exception(
    exc: Exception,
    *,
    err_str: str,
    type_name: str,
) -> bool:
    if isinstance(exc, (ConnectionError, OSError)):
        return True
    if any(
        marker in type_name
        for marker in ("connectionerror", "connecterror", "networkerror")
    ):
        return True
    return any(
        marker in err_str
        for marker in (
            "connection reset",
            "connection aborted",
            "connection error",
            "remote end closed connection",
            "server disconnected",
            "network is unreachable",
            "temporary failure in name resolution",
            "name or service not known",
        )
    )
