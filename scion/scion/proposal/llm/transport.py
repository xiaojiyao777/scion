"""Provider transport methods for LLMClient."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from .cache import gpt_prompt_cache_key
from .config import (
    _is_deepseek_model,
    _is_gpt_codex_model,
    _is_openai_model,
    _normalize_request_kind,
)
from .errors import (
    LLMBalanceError,
    LLMError,
    LLMFormatError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransientProviderError,
    _is_timeout_error_text,
    _is_transient_provider_error,
    _parse_retry_after,
)
from .timeout import _llm_hard_timeout

logger = logging.getLogger(__name__)


class TransportMixin:
    def _tool_call_once(
        self,
        prompt: str,
        tool: Dict[str, Any],
        model: str,
        system_blocks: "list[dict] | None",
        max_tokens: int,
        timeout_sec: float,
    ) -> tuple[Dict[str, Any], bool]:
        """Execute one tool call. Returns (result_dict, was_truncated)."""
        if _is_openai_model(model):
            return self._tool_call_once_openai(
                prompt,
                tool,
                model,
                system_blocks,
                max_tokens,
                timeout_sec,
            )
        return self._tool_call_once_anthropic(
            prompt,
            tool,
            model,
            system_blocks,
            max_tokens,
            timeout_sec,
        )

    def _tool_call_once_anthropic(
        self, prompt, tool, model, system_blocks, max_tokens, timeout_sec,
    ) -> tuple[Dict[str, Any], bool]:
        client = self._get_anthropic_client()
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": tool["name"]},
            "messages": [{"role": "user", "content": prompt}],
            "timeout": timeout_sec,
        }
        if system_blocks:
            kwargs["system"] = system_blocks

        response = client.messages.create(**kwargs)

        usage = getattr(response, "usage", None)
        if usage:
            cache_create = getattr(usage, "cache_creation_input_tokens", 0)
            cache_read = getattr(usage, "cache_read_input_tokens", 0)
            input_tokens = getattr(usage, "input_tokens", 0)
            output_tokens = getattr(usage, "output_tokens", 0)
            self._cache_stats["calls"] += 1
            self._cache_stats["cache_read_tokens"] += cache_read
            self._cache_stats["cache_create_tokens"] += cache_create
            self._cache_stats["uncached_tokens"] += input_tokens
            self._record_anthropic_usage(
                usage,
                model=model,
                request_kind=_normalize_request_kind(tool=tool) or "tool_call",
            )
            if self._token_tracker is not None:
                self._token_tracker.record(
                    request_kind=_normalize_request_kind(tool=tool) or "tool_call",
                    model_id=model,
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens,
                    cache_read_tokens=cache_read,
                    cache_create_tokens=cache_create,
                )

        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason in ("max_tokens", "length"):
            return {}, True

        for block in response.content:
            if hasattr(block, "type") and block.type == "tool_use":
                if block.name == tool["name"]:
                    return block.input, False

        raise LLMFormatError(
            f"LLM did not call tool '{tool['name']}'. Stop reason: {stop_reason}"
        )

    def _tool_call_once_openai(
        self, prompt, tool, model, system_blocks, max_tokens, timeout_sec,
    ) -> tuple[Dict[str, Any], bool]:
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
                max_tokens=max_tokens,
                messages=messages,
                timeout_sec=timeout_sec,
                tools=[openai_tool],
                tool_choice={"type": "function", "function": {"name": tool_name}},
                request_kind=_normalize_request_kind(tool=tool) or "tool_call",
                system_blocks=system_blocks,
            )
        )

        usage = response.usage
        if usage:
            cache_read, cache_miss = self._openai_cache_usage(usage)
            uncached = cache_miss if cache_read or cache_miss else usage.prompt_tokens or 0
            self._cache_stats["calls"] += 1
            self._cache_stats["cache_read_tokens"] += cache_read
            self._cache_stats["uncached_tokens"] += uncached
            self._record_openai_usage(
                usage,
                model=model,
                request_kind=_normalize_request_kind(tool=tool) or "tool_call",
                prompt_cache_key=self._last_prompt_cache_key,
            )
            if self._token_tracker is not None:
                self._token_tracker.record(
                    request_kind=_normalize_request_kind(tool=tool) or "llm_call",
                    model_id=model,
                    prompt_tokens=uncached,
                    completion_tokens=usage.completion_tokens or 0,
                    cache_read_tokens=cache_read,
                    cache_create_tokens=0,
                )

        choice = response.choices[0]
        if choice.finish_reason in ("length",):
            return {}, True

        tool_calls = getattr(choice.message, "tool_calls", None)
        if not tool_calls:
            raise LLMFormatError(
                f"LLM did not call tool '{tool_name}'. "
                f"Finish reason: {choice.finish_reason}"
            )

        result = json.loads(tool_calls[0].function.arguments)
        return result, False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_once(
        self,
        prompt: str,
        model: str,
        system_blocks: "list[dict] | None" = None,
    ) -> str:
        if _is_openai_model(model):
            return self._call_once_openai(prompt, model, system_blocks)
        return self._call_once_anthropic(prompt, model, system_blocks)

    def _call_once_anthropic(
        self,
        prompt: str,
        model: str,
        system_blocks: "list[dict] | None" = None,
    ) -> str:
        """Anthropic SDK path."""
        client = self._get_anthropic_client()
        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "timeout": self.timeout_sec,
            }
            if system_blocks:
                kwargs["system"] = system_blocks
            message = client.messages.create(**kwargs)
            usage = getattr(message, "usage", None)
            if usage:
                cache_create = getattr(usage, "cache_creation_input_tokens", 0)
                cache_read = getattr(usage, "cache_read_input_tokens", 0)
                input_tokens = getattr(usage, "input_tokens", 0)
                output_tokens = getattr(usage, "output_tokens", 0)
                self._record_anthropic_usage(
                    usage,
                    model=model,
                    request_kind="llm_call",
                )
                if cache_create or cache_read:
                    logger.info(
                        "Cache: created=%d read=%d uncached=%d",
                        cache_create, cache_read, input_tokens,
                    )
                if self._token_tracker is not None:
                    self._token_tracker.record(
                        request_kind="llm_call",
                        model_id=model,
                        prompt_tokens=input_tokens,
                        completion_tokens=output_tokens,
                        cache_read_tokens=cache_read,
                        cache_create_tokens=cache_create,
                    )
            return message.content[0].text
        except Exception as exc:
            self._raise_classified(exc)

    def _call_once_openai(
        self,
        prompt: str,
        model: str,
        system_blocks: "list[dict] | None" = None,
    ) -> str:
        """OpenAI SDK path (GPT models via aihubmix)."""
        client = self._get_openai_client()
        try:
            messages: list[Dict[str, Any]] = []
            if system_blocks:
                for block in system_blocks:
                    text = block.get("text", "") if isinstance(block, dict) else str(block)
                    messages.append({"role": "system", "content": text})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                **self._openai_chat_kwargs(
                    model=model,
                    max_tokens=self.max_tokens,
                    messages=messages,
                    timeout_sec=self.timeout_sec,
                    request_kind="llm_call",
                    system_blocks=system_blocks,
                )
            )
            usage = response.usage
            if usage:
                cache_read, cache_miss = self._openai_cache_usage(usage)
                input_tokens = (
                    cache_miss if cache_read or cache_miss else usage.prompt_tokens or 0
                )
                output_tokens = usage.completion_tokens or 0
                self._cache_stats["calls"] += 1
                self._cache_stats["cache_read_tokens"] += cache_read
                self._cache_stats["uncached_tokens"] += input_tokens
                self._record_openai_usage(
                    usage,
                    model=model,
                    request_kind="llm_call",
                    prompt_cache_key=self._last_prompt_cache_key,
                )
                if self._token_tracker is not None:
                    self._token_tracker.record(
                        request_kind="llm_call",
                        model_id=model,
                        prompt_tokens=input_tokens,
                        completion_tokens=output_tokens,
                        cache_read_tokens=cache_read,
                        cache_create_tokens=0,
                    )
            return response.choices[0].message.content
        except Exception as exc:
            self._raise_classified(exc)

    def _openai_chat_kwargs(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[Dict[str, Any]],
        timeout_sec: float,
        tools: list[Dict[str, Any]] | None = None,
        tool_choice: Dict[str, Any] | None = None,
        request_kind: str | None = None,
        system_blocks: list[dict] | None = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_completion_tokens": max_tokens,
            "messages": messages,
            "timeout": timeout_sec,
        }
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None and not _is_deepseek_model(str(model or "")):
            kwargs["tool_choice"] = tool_choice
        normalized_kind = _normalize_request_kind(
            request_kind=request_kind,
            tool=tools[0] if tools else None,
        ) or "llm_call"
        prompt_cache_key = gpt_prompt_cache_key(
            model=model,
            request_kind=normalized_kind,
            system_blocks=system_blocks,
            tool_schema=tools or {},
        )
        self._last_prompt_cache_key = prompt_cache_key
        if prompt_cache_key:
            kwargs["prompt_cache_key"] = prompt_cache_key
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
        prompt_cache_key: str | None = None,
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
        if prompt_cache_key:
            cache_mode = (
                "prompt_cache_key_observed"
                if cache_read or cache_miss
                else "prompt_cache_key_attempted"
            )
        else:
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
        if prompt_cache_key:
            self._last_usage_metadata["prompt_cache_key"] = prompt_cache_key
            self._last_usage_metadata["prompt_cache_key_digest"] = (
                prompt_cache_key.rsplit(":", 1)[-1]
            )

    @staticmethod
    def _raise_classified(exc: Exception) -> None:
        """Classify a raw SDK exception and re-raise as the appropriate LLM* type."""
        raw_error = str(exc)
        err_str = raw_error.lower()
        if _is_timeout_error_text(err_str):
            raise LLMTimeoutError(f"Request timed out: {exc}") from exc
        if "403" in err_str and ("balance" in err_str or "insufficient" in err_str):
            raise LLMBalanceError(f"API balance exhausted: {exc}") from exc
        if _is_transient_provider_error(err_str):
            raise LLMTransientProviderError(f"Transient provider error: {exc}") from exc
        if "429" in raw_error or "rate_limit" in err_str or "ratelimit" in err_str:
            retry_after = _parse_retry_after(exc)
            raise LLMRateLimitError(f"Rate limited: {exc}", retry_after=retry_after) from exc
        raise LLMError(f"API error: {exc}") from exc

    def get_cache_stats(self) -> dict:
        """Return cache hit statistics."""
        s = self._cache_stats
        total_in = s["cache_read_tokens"] + s["cache_create_tokens"] + s["uncached_tokens"]
        hit_rate = s["cache_read_tokens"] / total_in if total_in > 0 else 0
        return {"hit_rate": f"{hit_rate:.1%}", **s}

    def call_text(
        self,
        prompt: str,
        model: str | None = None,
    ) -> str:
        """Call LLM and return raw text response (no JSON parsing).

        Single attempt with timeout handling. Used by classifier and other
        lightweight calls that don't need structured output.
        """
        effective_model = model or self.model
        try:
            with _llm_hard_timeout(self.timeout_sec):
                return self._call_once(prompt, effective_model)
        except (LLMTimeoutError, LLMRateLimitError, LLMTransientProviderError):
            raise
        except Exception as exc:
            raise LLMError(f"call_text failed: {exc}") from exc

    def _get_anthropic_client(self) -> Any:
        if self._anthropic_client is not None:
            return self._anthropic_client
        try:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                max_retries=self.sdk_max_retries,
            )
            logger.info(
                "Anthropic client initialized: model=%s base_url=%s sdk_max_retries=%d",
                self.model,
                self.base_url,
                self.sdk_max_retries,
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
                max_retries=self.sdk_max_retries,
            )
            logger.info(
                "OpenAI client initialized: model=%s base_url=%s sdk_max_retries=%d",
                self.model,
                base,
                self.sdk_max_retries,
            )
            return self._openai_client
        except ImportError as exc:
            raise LLMError(
                "The 'openai' package is not installed. pip install openai"
            ) from exc
