"""Public LLMClient orchestration and retry loops."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict

from .config import (
    _BACKOFF_DELAYS,
    _DEFAULT_BASE_URL,
    _DEFAULT_MAX_RETRIES,
    _DEFAULT_MAX_TOKENS,
    _DEFAULT_MODEL,
    _DEFAULT_SDK_MAX_RETRIES,
    _DEFAULT_TIMEOUT_SEC,
    MAX_MAX_TOKENS,
    MAX_TRUNCATION_RETRIES,
    _env_float,
    _env_int,
    _normalize_model_alias,
)
from .errors import (
    LLMBalanceError,
    LLMError,
    LLMFormatError,
    LLMRateLimitError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
    LLMTransientProviderError,
    _masked_hard_timeout_error,
    _retry_exhausted_failure_category,
    _transient_retry_exhausted_error,
)
from .parsing import ParsingMixin
from .policy import PolicyMixin
from .timeout import _llm_hard_timeout
from .transport import TransportMixin

logger = logging.getLogger(__name__)


class LLMClient(ParsingMixin, PolicyMixin, TransportMixin):
    """LLM API client with retry on timeout and format errors.

    Uses Anthropic SDK with configurable base_url for aihubmix proxy.

    Retry policy:
    - Timeout: exponential backoff (5 s, 15 s), max ``max_retries`` additional attempts.
    - Format error: append the error to the prompt, same retry budget.
    - 429 (rate limit): sleep for ``Retry-After`` seconds then try again
      (does *not* count against ``max_retries``).
    - Provider SDK retries are disabled by default so retries remain visible in
      Scion traces instead of being multiplied inside the SDK.
    - Code/fix tool calls default to a longer timeout and zero same-prompt
      LLMClient retries; APS owns semantic retry for code generation.

    Config resolution (in order):
    1. Constructor arguments
    2. Environment variables: SCION_API_KEY, SCION_BASE_URL, SCION_MODEL
    3. Timeout/retry env vars: SCION_LLM_TIMEOUT_SEC,
       SCION_LLM_MAX_RETRIES, SCION_LLM_CODE_TIMEOUT_SEC,
       SCION_LLM_CODE_MAX_RETRIES, SCION_LLM_FIX_TIMEOUT_SEC,
       SCION_LLM_FIX_MAX_RETRIES, SCION_SDK_MAX_RETRIES
    4. Fallback env vars: ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL
    5. Defaults: aihubmix endpoint, claude-sonnet-4-6
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_sec: float | None = None,
        max_retries: int | None = None,
        max_tokens: int | None = None,
        sdk_max_retries: int | None = None,
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
        self.max_retries = _env_int(
            "SCION_LLM_MAX_RETRIES",
            _DEFAULT_MAX_RETRIES if max_retries is None else max_retries,
        )
        self.max_tokens = _env_int(
            "SCION_LLM_MAX_TOKENS",
            _DEFAULT_MAX_TOKENS if max_tokens is None else max_tokens,
        )
        self.sdk_max_retries = _env_int(
            "SCION_SDK_MAX_RETRIES",
            _DEFAULT_SDK_MAX_RETRIES if sdk_max_retries is None else sdk_max_retries,
        )
        self._cache_stats = {"calls": 0, "cache_read_tokens": 0, "cache_create_tokens": 0, "uncached_tokens": 0}
        self._anthropic_client: Any = None
        self._openai_client: Any = None
        self._token_tracker: Any = None  # W13: set via set_token_tracker()

    def set_token_tracker(self, tracker) -> None:
        """W13: Attach a TokenUsageTracker for per-call recording."""
        self._token_tracker = tracker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        model: str | None = None,
        system_blocks: "list[dict] | None" = None,
        priority: str = "foreground",
    ) -> Dict[str, Any]:
        """Call the LLM and return a validated JSON dict.

        Args:
            prompt: The user message text.
            response_schema: Minimal JSON-schema dict (used for required-field
                             validation).
            model: Optional model override; falls back to ``self.model``.
            system_blocks: Optional structured system messages with
                           cache_control for prompt caching.

        Returns:
            Parsed response dict.

        Raises:
            LLMRetryExhaustedError: All attempts failed.
        """
        effective_model = model or self.model
        current_prompt = prompt
        last_error: Exception | None = None
        attempt = 0
        transient_max_retries = self.resolve_request_policy(
            request_kind="llm_call"
        )["transient_max_retries"]
        transient_attempt = 0

        while attempt <= self.max_retries:
            try:
                raw = self._call_once(current_prompt, effective_model, system_blocks)
                return self._parse_and_validate(raw, response_schema)

            except LLMRateLimitError as exc:
                last_error = exc
                if priority == "background":
                    raise
                logger.warning(
                    "LLM rate-limited (attempt %d); sleeping %.1fs", attempt, exc.retry_after
                )
                time.sleep(exc.retry_after)
                # Do NOT increment attempt — rate limit is not a user-error retry.

            except LLMFormatError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = _BACKOFF_DELAYS[min(attempt, len(_BACKOFF_DELAYS) - 1)]
                    logger.warning(
                        "LLM format error (attempt %d/%d): %s; retrying in %.1fs",
                        attempt + 1, self.max_retries, exc, delay,
                    )
                    current_prompt = (
                        f"{current_prompt}\n\n"
                        f"[ERROR: previous response had a format issue: {exc}. "
                        f"Respond only with a valid JSON object matching the schema.]"
                    )
                    time.sleep(delay)
                attempt += 1

            except LLMTimeoutError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = _BACKOFF_DELAYS[min(attempt, len(_BACKOFF_DELAYS) - 1)]
                    logger.warning(
                        "LLM timeout (attempt %d/%d); retrying in %.1fs",
                        attempt + 1, self.max_retries, delay,
                    )
                    time.sleep(delay)
                attempt += 1

            except LLMTransientProviderError as exc:
                last_error = exc
                if transient_attempt < transient_max_retries:
                    delay = _BACKOFF_DELAYS[
                        min(transient_attempt, len(_BACKOFF_DELAYS) - 1)
                    ]
                    logger.warning(
                        "LLM transient API error (attempt %d/%d); retrying in %.1fs: %s",
                        transient_attempt + 1,
                        transient_max_retries,
                        delay,
                        exc,
                    )
                    transient_attempt += 1
                    time.sleep(delay)
                    continue
                raise _transient_retry_exhausted_error(
                    request_label="LLM call",
                    total_attempts=transient_attempt + 1,
                    last_error=exc,
                ) from exc

        raise LLMRetryExhaustedError(
            f"LLM call failed after {self.max_retries + 1} attempt(s). "
            f"Last error: {last_error}",
            last_error=last_error,
            failure_category=_retry_exhausted_failure_category(last_error),
        ) from last_error

    # ------------------------------------------------------------------
    # Tool-use based calling (avoids JSON escape issues for code)
    # ------------------------------------------------------------------

    def call_with_tool(
        self,
        prompt: str,
        tool: Dict[str, Any],
        model: str | None = None,
        system_blocks: "list[dict] | None" = None,
        priority: str = "foreground",
        request_kind: str | None = None,
    ) -> Dict[str, Any]:
        """Call LLM with tool_use and return the tool input dict directly.

        Supports both Anthropic (Claude) and OpenAI (GPT) models.
        """
        effective_model = model or self.model
        policy = self.resolve_request_policy(request_kind=request_kind, tool=tool)
        max_retries = policy["max_retries"]
        timeout_sec = policy["timeout_sec"]
        transient_max_retries = policy["transient_max_retries"]
        attempt = 0
        transient_attempt = 0
        last_error: Exception | None = None
        current_max_tokens = self.max_tokens
        truncation_retries = 0

        while attempt <= max_retries:
            attempt_started_at: float | None = None
            try:
                attempt_started_at = time.monotonic()
                with _llm_hard_timeout(timeout_sec):
                    result, truncated = self._tool_call_once(
                        prompt,
                        tool,
                        effective_model,
                        system_blocks,
                        current_max_tokens,
                        timeout_sec,
                    )
                result = self._normalize_tool_call_result(
                    result,
                    tool=tool,
                    request_kind=request_kind,
                )
                if truncated:
                    if truncation_retries < MAX_TRUNCATION_RETRIES:
                        new_max = min(current_max_tokens * 2, MAX_MAX_TOKENS)
                        logger.warning(
                            "Response truncated; retrying with max_tokens=%d→%d",
                            current_max_tokens, new_max,
                        )
                        current_max_tokens = new_max
                        truncation_retries += 1
                        continue
                    logger.warning("Response still truncated after %d retries", MAX_TRUNCATION_RETRIES)
                    if not result:
                        raise LLMFormatError("Response truncated with no usable tool output")

                required = tool.get("input_schema", {}).get("required", [])
                if not required:
                    required = (
                        tool.get("function", {}).get("parameters", {}).get("required", [])
                    )
                missing = [k for k in required if k not in result]
                if missing:
                    raise LLMFormatError(
                        "Tool input missing required fields: "
                        f"{missing}. Got keys: {sorted(result)}"
                    )
                return result

            except LLMFormatError as exc:
                last_error = exc
                if attempt < max_retries:
                    delay = _BACKOFF_DELAYS[min(attempt, len(_BACKOFF_DELAYS) - 1)]
                    logger.warning("Tool call format error (attempt %d/%d): %s", attempt + 1, max_retries, exc)
                    time.sleep(delay)
                attempt += 1

            except LLMRateLimitError as exc:
                last_error = exc
                if priority == "background":
                    raise
                logger.warning("Rate limited; waiting %.1fs", exc.retry_after)
                time.sleep(exc.retry_after)

            except LLMTimeoutError as exc:
                last_error = exc
                if attempt < max_retries:
                    delay = _BACKOFF_DELAYS[min(attempt, len(_BACKOFF_DELAYS) - 1)]
                    logger.warning("Tool call timeout (attempt %d/%d)", attempt + 1, max_retries)
                    time.sleep(delay)
                attempt += 1

            except LLMTransientProviderError as exc:
                last_error = exc
                if transient_attempt < transient_max_retries:
                    delay = _BACKOFF_DELAYS[
                        min(transient_attempt, len(_BACKOFF_DELAYS) - 1)
                    ]
                    logger.warning(
                        "Transient provider error (attempt %d/%d); retrying in %.1fs: %s",
                        transient_attempt + 1,
                        transient_max_retries,
                        delay,
                        exc,
                    )
                    transient_attempt += 1
                    time.sleep(delay)
                    continue
                raise _transient_retry_exhausted_error(
                    request_label="Tool call",
                    total_attempts=transient_attempt + 1,
                    last_error=exc,
                ) from exc

            except (LLMBalanceError, LLMRetryExhaustedError):
                raise

            except Exception as exc:
                masked_timeout = _masked_hard_timeout_error(
                    exc,
                    attempt_started_at=attempt_started_at,
                    timeout_sec=timeout_sec,
                )
                if masked_timeout is not None:
                    last_error = masked_timeout
                    if attempt < max_retries:
                        delay = _BACKOFF_DELAYS[
                            min(attempt, len(_BACKOFF_DELAYS) - 1)
                        ]
                        logger.warning(
                            "Tool call timeout (attempt %d/%d)",
                            attempt + 1,
                            max_retries,
                        )
                        time.sleep(delay)
                    attempt += 1
                    continue
                try:
                    self._raise_classified(exc)
                except LLMRateLimitError as rle:
                    last_error = rle
                    if priority == "background":
                        raise
                    time.sleep(rle.retry_after)
                    continue
                except LLMTransientProviderError as tpe:
                    last_error = tpe
                    if transient_attempt < transient_max_retries:
                        delay = _BACKOFF_DELAYS[
                            min(transient_attempt, len(_BACKOFF_DELAYS) - 1)
                        ]
                        logger.warning(
                            "Transient provider error (attempt %d/%d); retrying in %.1fs: %s",
                            transient_attempt + 1,
                            transient_max_retries,
                            delay,
                            tpe,
                        )
                        transient_attempt += 1
                        time.sleep(delay)
                        continue
                    raise _transient_retry_exhausted_error(
                        request_label="Tool call",
                        total_attempts=transient_attempt + 1,
                        last_error=tpe,
                    ) from tpe
                except LLMBalanceError:
                    raise
                except LLMError as le:
                    last_error = le
                if attempt < max_retries:
                    delay = _BACKOFF_DELAYS[min(attempt, len(_BACKOFF_DELAYS) - 1)]
                    time.sleep(delay)
                attempt += 1

        raise LLMRetryExhaustedError(
            f"Tool call failed after {max_retries + 1} attempt(s). "
            f"Last error: {last_error}",
            last_error=last_error,
            failure_category=_retry_exhausted_failure_category(last_error),
        ) from last_error

