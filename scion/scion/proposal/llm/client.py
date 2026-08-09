"""Public single-attempt LLM client orchestration."""
from __future__ import annotations

import os
import time
from typing import Any, Dict

from .config import (
    _DEFAULT_BASE_URL,
    _DEFAULT_MODEL,
    _DEFAULT_TIMEOUT_SEC,
    _env_float,
    _normalize_model_alias,
)
from .errors import (
    LLMError,
    LLMFormatError,
    _masked_hard_timeout_error,
)
from .policy import PolicyMixin
from .timeout import _llm_hard_timeout
from .transport import TransportMixin


class LLMClient(PolicyMixin, TransportMixin):
    """LLM API client where one public call owns one transport call.

    Uses Anthropic SDK with configurable base_url for aihubmix proxy.

    Provider SDK retries are unconditionally disabled.  Format, timeout, rate,
    transport, provider, authentication, and balance faults are returned as
    typed exceptions to the durable orchestration layer without sleeping or
    replaying the prompt.

    Config resolution (in order):
    1. Constructor arguments
    2. Environment variables: SCION_API_KEY, SCION_BASE_URL, SCION_MODEL
    3. Timeout env vars: SCION_LLM_TIMEOUT_SEC and request-kind timeout vars
    4. Fallback env vars: ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL
    5. Defaults: aihubmix endpoint, claude-sonnet-4-6
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_sec: float | None = None,
    ) -> None:
        raw_model = str(
            model
            or os.environ.get("SCION_MODEL")
            or os.environ.get("ANTHROPIC_MODEL")
            or _DEFAULT_MODEL
        ).strip()
        self.model, implied_reasoning_effort = _normalize_model_alias(raw_model)
        self.reasoning_effort = str(
            os.environ.get("SCION_REASONING_EFFORT")
            or os.environ.get("SCION_DEEPSEEK_REASONING_EFFORT")
            or implied_reasoning_effort
            or ""
        ).strip()
        self.api_key = str(
            api_key
            or os.environ.get("SCION_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("ANTHROPIC_API_KEY", "")
        ).strip()
        self.base_url = str(
            base_url
            or os.environ.get("SCION_BASE_URL")
            or os.environ.get("ANTHROPIC_BASE_URL")
            or _DEFAULT_BASE_URL
        ).strip()
        self.timeout_sec = _env_float(
            "SCION_LLM_TIMEOUT_SEC",
            _DEFAULT_TIMEOUT_SEC if timeout_sec is None else timeout_sec,
        )
        self._cache_stats = {"calls": 0, "cache_read_tokens": 0, "cache_create_tokens": 0, "uncached_tokens": 0}
        self._last_usage_metadata: dict[str, Any] | None = None
        self._last_response_diagnostics: dict[str, Any] | None = None
        self._last_prompt_cache_key: str | None = None
        self._anthropic_client: Any = None
        self._openai_client: Any = None
        self._token_tracker: Any = None  # W13: set via set_token_tracker()

    def set_token_tracker(self, tracker) -> None:
        """W13: Attach a TokenUsageTracker for per-call recording."""
        self._token_tracker = tracker

    def close(self) -> None:
        """Close cached provider SDK clients and their HTTP transports."""
        self.close_provider_clients()

    def get_last_usage_metadata(self) -> dict[str, Any] | None:
        """Return normalized provider usage for the most recent SDK response."""
        if self._last_usage_metadata is None:
            return None
        return dict(self._last_usage_metadata)

    def get_last_response_diagnostics(self) -> dict[str, Any] | None:
        """Return mechanical facts from the most recent SDK response."""
        if self._last_response_diagnostics is None:
            return None
        return dict(self._last_response_diagnostics)

    def reset_call_observations(self) -> None:
        """Start one public provider call without observations from its predecessor."""
        self._last_usage_metadata = None
        self._last_response_diagnostics = None
        self._last_prompt_cache_key = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call_with_tool(
        self,
        prompt: str,
        tool: Dict[str, Any],
        model: str | None = None,
        system_blocks: "list[dict] | None" = None,
        request_kind: str | None = None,
    ) -> Dict[str, Any]:
        """Execute one tool transport call and return its typed input dict.

        Supports both Anthropic (Claude) and OpenAI (GPT) models.
        """
        effective_model = model or self.model
        self.reset_call_observations()
        policy = self.resolve_request_policy(
            request_kind=request_kind,
            tool=tool,
            model=effective_model,
        )
        timeout_sec = policy["timeout_sec"]
        attempt_started_at = time.monotonic()
        try:
            with _llm_hard_timeout(timeout_sec):
                result = self._tool_call_once(
                    prompt,
                    tool,
                    effective_model,
                    system_blocks,
                    timeout_sec,
                )
            required = tool.get("input_schema", {}).get("required", [])
            if not required:
                required = tool.get("function", {}).get("parameters", {}).get(
                    "required",
                    [],
                )
            missing = [key for key in required if key not in result]
            if missing:
                raise LLMFormatError(
                    "Tool input missing required fields: "
                    f"{missing}. Got keys: {sorted(result)}"
                )
            return result
        except LLMError:
            raise
        except Exception as exc:
            self._raise_single_call_error(
                exc,
                attempt_started_at=attempt_started_at,
                timeout_sec=timeout_sec,
            )

    def _raise_single_call_error(
        self,
        exc: Exception,
        *,
        attempt_started_at: float,
        timeout_sec: float,
    ) -> None:
        masked_timeout = _masked_hard_timeout_error(
            exc,
            attempt_started_at=attempt_started_at,
            timeout_sec=timeout_sec,
        )
        if masked_timeout is not None:
            raise masked_timeout from exc
        self._raise_classified(exc)
