"""Provider transport methods for LLMClient."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from .config import _is_deepseek_model, _is_openai_model, _normalize_request_kind
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
            self._cache_stats["calls"] += 1
            self._cache_stats["cache_read_tokens"] += cache_read
            self._cache_stats["cache_create_tokens"] += cache_create
            self._cache_stats["uncached_tokens"] += input_tokens

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
            )
        )

        usage = response.usage
        if usage:
            cache_read, cache_miss = self._openai_cache_usage(usage)
            uncached = cache_miss if cache_read or cache_miss else usage.prompt_tokens or 0
            self._cache_stats["calls"] += 1
            self._cache_stats["cache_read_tokens"] += cache_read
            self._cache_stats["uncached_tokens"] += uncached
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
        reasoning_effort = self._openai_reasoning_effort(model)
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        extra_body = self._openai_extra_body(model)
        if extra_body:
            kwargs["extra_body"] = extra_body
        return kwargs

    def _openai_reasoning_effort(self, model: str) -> str:
        if not _is_deepseek_model(str(model or "")):
            return ""
        effort = self.reasoning_effort
        if not effort:
            return ""
        normalized = effort.lower()
        if normalized == "xhigh":
            normalized = "max"
        elif normalized in {"low", "medium"}:
            normalized = "high"
        if normalized not in {"high", "max"}:
            return ""
        return normalized

    def _openai_extra_body(self, model: str) -> Dict[str, Any]:
        if not _is_deepseek_model(str(model or "")):
            return {}
        if not self._openai_reasoning_effort(model):
            return {}
        return {"thinking": {"type": "enabled"}}

    @staticmethod
    def _openai_cache_usage(usage: Any) -> tuple[int, int]:
        cache_read = int(getattr(usage, "prompt_cache_hit_tokens", 0) or 0)
        cache_miss = int(getattr(usage, "prompt_cache_miss_tokens", 0) or 0)
        return cache_read, cache_miss

    @staticmethod
    def _raise_classified(exc: Exception) -> None:
        """Classify a raw SDK exception and re-raise as the appropriate LLM* type."""
        err_str = str(exc).lower()
        if _is_timeout_error_text(err_str):
            raise LLMTimeoutError(f"Request timed out: {exc}") from exc
        if _is_transient_provider_error(err_str):
            raise LLMTransientProviderError(f"Transient provider error: {exc}") from exc
        if "429" in str(exc) or "rate_limit" in err_str or "ratelimit" in err_str:
            retry_after = _parse_retry_after(exc)
            raise LLMRateLimitError(f"Rate limited: {exc}", retry_after=retry_after) from exc
        if "403" in str(exc) and ("balance" in err_str or "insufficient" in err_str):
            raise LLMBalanceError(f"API balance exhausted: {exc}") from exc
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

