"""LLMClient — wraps LLM API calls with timeout + format-error retry logic.

Supports Claude models via aihubmix Anthropic-compatible endpoint.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Exponential backoff delays (seconds) between retries
_BACKOFF_DELAYS = (5.0, 15.0)

# Truncation recovery
MAX_TRUNCATION_RETRIES = 2
MAX_MAX_TOKENS = 16384

# Default config — aihubmix Anthropic endpoint
_DEFAULT_BASE_URL = "https://aihubmix.com"
_DEFAULT_MODEL = "claude-opus-4-6"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Base class for LLM-related errors."""


class LLMTimeoutError(LLMError):
    """API call timed out."""


class LLMFormatError(LLMError):
    """LLM response does not conform to the expected JSON schema."""


class LLMRateLimitError(LLMError):
    """HTTP 429 — Too Many Requests."""

    def __init__(self, message: str, retry_after: float = 60.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMRetryExhaustedError(LLMError):
    """All retry attempts exhausted."""


class LLMBalanceError(LLMError):
    """API balance/credits exhausted (HTTP 403 with insufficient-balance message)."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class LLMClient:
    """LLM API client with retry on timeout and format errors.

    Uses Anthropic SDK with configurable base_url for aihubmix proxy.

    Retry policy:
    - Timeout: exponential backoff (5 s, 15 s), max ``max_retries`` additional attempts.
    - Format error: append the error to the prompt, same retry budget.
    - 429 (rate limit): sleep for ``Retry-After`` seconds then try again
      (does *not* count against ``max_retries``).

    Config resolution (in order):
    1. Constructor arguments
    2. Environment variables: SCION_API_KEY, SCION_BASE_URL, SCION_MODEL
    3. Fallback env vars: ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL
    4. Defaults: aihubmix endpoint, claude-sonnet-4-6
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_sec: float = 60.0,
        max_retries: int = 2,
        max_tokens: int = 16384,
    ) -> None:
        self.model = (
            model
            or os.environ.get("SCION_MODEL")
            or os.environ.get("ANTHROPIC_MODEL")
            or _DEFAULT_MODEL
        )
        self.api_key = (
            api_key
            or os.environ.get("SCION_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("ANTHROPIC_API_KEY", "")
        )
        self.base_url = (
            base_url
            or os.environ.get("SCION_BASE_URL")
            or os.environ.get("ANTHROPIC_BASE_URL")
            or _DEFAULT_BASE_URL
        )
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.max_tokens = max_tokens
        self._cache_stats = {"calls": 0, "cache_read_tokens": 0, "cache_create_tokens": 0, "uncached_tokens": 0}
        self._client: Any = None  # lazy-initialised

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

        raise LLMRetryExhaustedError(
            f"LLM call failed after {self.max_retries + 1} attempt(s). "
            f"Last error: {last_error}"
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
    ) -> Dict[str, Any]:
        """Call LLM with tool_use and return the tool input dict directly.

        Uses tool_choice={"type": "tool", "name": tool["name"]} to force
        the model to call the specified tool.  The returned ``block.input``
        is already a parsed dict — no JSON decode needed.

        This is the same pattern Claude Code uses for FileWriteTool: the
        API's constrained decoding handles all JSON escaping of code content.
        """
        effective_model = model or self.model
        client = self._get_client()
        attempt = 0
        last_error: Exception | None = None
        current_max_tokens = self.max_tokens
        truncation_retries = 0

        while attempt <= self.max_retries:
            try:
                kwargs: Dict[str, Any] = {
                    "model": effective_model,
                    "max_tokens": current_max_tokens,
                    "tools": [tool],
                    "tool_choice": {"type": "tool", "name": tool["name"]},
                    "messages": [{"role": "user", "content": prompt}],
                    "timeout": self.timeout_sec,
                }
                if system_blocks:
                    kwargs["system"] = system_blocks

                response = client.messages.create(**kwargs)

                # Log cache performance
                usage = getattr(response, "usage", None)
                if usage:
                    cache_create = getattr(usage, "cache_creation_input_tokens", 0)
                    cache_read = getattr(usage, "cache_read_input_tokens", 0)
                    input_tokens = getattr(usage, "input_tokens", 0)
                    if cache_create or cache_read:
                        logger.info(
                            "Cache: created=%d read=%d uncached=%d",
                            cache_create, cache_read, input_tokens,
                        )
                    self._cache_stats["calls"] += 1
                    self._cache_stats["cache_read_tokens"] += cache_read
                    self._cache_stats["cache_create_tokens"] += cache_create
                    self._cache_stats["uncached_tokens"] += input_tokens

                # Extract tool_use block
                stop_reason = getattr(response, 'stop_reason', None)
                logger.debug(
                    "Response: stop_reason=%s blocks=%d types=%s",
                    stop_reason,
                    len(response.content),
                    [getattr(b, 'type', '?') for b in response.content],
                )

                # Truncation recovery: retry with doubled max_tokens
                if stop_reason in ("max_tokens", "length"):
                    if truncation_retries < MAX_TRUNCATION_RETRIES:
                        new_max = min(current_max_tokens * 2, MAX_MAX_TOKENS)
                        logger.warning(
                            "Response truncated (stop_reason=%s); retrying with max_tokens=%d→%d (truncation_retry %d/%d)",
                            stop_reason, current_max_tokens, new_max,
                            truncation_retries + 1, MAX_TRUNCATION_RETRIES,
                        )
                        current_max_tokens = new_max
                        truncation_retries += 1
                        continue
                    else:
                        logger.warning(
                            "Response still truncated after %d truncation retries; returning partial content",
                            MAX_TRUNCATION_RETRIES,
                        )

                for block in response.content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        if block.name == tool["name"]:
                            # block.input is already a dict, parsed by the API
                            result = block.input
                            # Validate required fields
                            required = tool.get("input_schema", {}).get("required", [])
                            missing = [k for k in required if k not in result]
                            if missing:
                                logger.warning(
                                    "Tool input keys present: %s; missing: %s",
                                    list(result.keys()), missing,
                                )
                                raise LLMFormatError(
                                    f"Tool input missing required fields: {missing}"
                                )
                            return result

                raise LLMFormatError(
                    f"LLM did not call tool '{tool['name']}'. "
                    f"Stop reason: {getattr(response, 'stop_reason', 'unknown')}"
                )

            except LLMFormatError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = _BACKOFF_DELAYS[min(attempt, len(_BACKOFF_DELAYS) - 1)]
                    logger.warning(
                        "Tool call format error (attempt %d/%d): %s",
                        attempt + 1, self.max_retries, exc,
                    )
                    time.sleep(delay)
                attempt += 1

            except LLMRateLimitError as exc:
                last_error = exc
                if priority == "background":
                    raise
                retry_after = exc.retry_after
                logger.warning("Rate limited; waiting %.1fs", retry_after)
                time.sleep(retry_after)
                # Don't consume retry count for rate limits

            except LLMTimeoutError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = _BACKOFF_DELAYS[min(attempt, len(_BACKOFF_DELAYS) - 1)]
                    logger.warning(
                        "Tool call timeout (attempt %d/%d); retrying in %.1fs",
                        attempt + 1, self.max_retries, delay,
                    )
                    time.sleep(delay)
                attempt += 1

            except Exception as exc:
                err_str = str(exc).lower()
                if "timeout" in err_str or "timed out" in err_str:
                    last_error = LLMTimeoutError(str(exc))
                elif "429" in str(exc) or "rate_limit" in err_str:
                    retry_after = _parse_retry_after(exc)
                    last_error = LLMRateLimitError(str(exc), retry_after=retry_after)
                    if priority == "background":
                        raise last_error from exc
                    time.sleep(retry_after)
                    continue  # Don't consume retry
                elif "403" in str(exc) and ("balance" in err_str or "insufficient" in err_str):
                    raise LLMBalanceError(f"API balance exhausted: {exc}") from exc
                else:
                    last_error = LLMError(str(exc))
                if attempt < self.max_retries:
                    delay = _BACKOFF_DELAYS[min(attempt, len(_BACKOFF_DELAYS) - 1)]
                    time.sleep(delay)
                attempt += 1

        raise LLMRetryExhaustedError(
            f"Tool call failed after {self.max_retries + 1} attempt(s). "
            f"Last error: {last_error}"
        ) from last_error

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_once(
        self,
        prompt: str,
        model: str,
        system_blocks: "list[dict] | None" = None,
    ) -> str:
        """Make one API call; return raw text.

        If *system_blocks* is provided, they are sent as structured system
        messages with cache_control for prompt caching.  The *prompt* is
        sent as the user message.
        """
        client = self._get_client()
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
            # Log cache performance
            usage = getattr(message, "usage", None)
            if usage:
                cache_create = getattr(usage, "cache_creation_input_tokens", 0)
                cache_read = getattr(usage, "cache_read_input_tokens", 0)
                input_tokens = getattr(usage, "input_tokens", 0)
                if cache_create or cache_read:
                    logger.info(
                        "Cache: created=%d read=%d uncached=%d",
                        cache_create, cache_read, input_tokens,
                    )
            return message.content[0].text
        except Exception as exc:
            err_str = str(exc).lower()
            if "timeout" in err_str or "timed out" in err_str or "read timed out" in err_str:
                raise LLMTimeoutError(f"Request timed out: {exc}") from exc
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
        except (LLMTimeoutError, LLMRateLimitError):
            raise
        except Exception as exc:
            raise LLMError(f"call_text failed: {exc}") from exc

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            logger.info("LLMClient initialized: model=%s base_url=%s", self.model, self.base_url)
            return self._client
        except ImportError as exc:
            raise LLMError(
                "The 'anthropic' package is not installed. "
                "Use MockLLMClient for tests, or: pip install anthropic"
            ) from exc

    def _parse_and_validate(
        self, raw: str, schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract JSON from raw text and check required fields."""
        text = raw.strip()

        # Strip markdown code fences if present
        if "```json" in text:
            try:
                start = text.index("```json") + 7
                end = text.index("```", start)
                text = text[start:end].strip()
            except ValueError:
                pass
        elif "```" in text:
            try:
                start = text.index("```") + 3
                end = text.index("```", start)
                text = text[start:end].strip()
            except ValueError:
                pass

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # LLM often puts raw newlines/tabs inside JSON string values
            # (e.g. code_content with actual line breaks). Try strict=False.
            try:
                data = json.loads(text, strict=False)
            except json.JSONDecodeError as exc:
                raise LLMFormatError(
                    f"Response is not valid JSON: {exc}. Preview: {raw[:300]!r}"
                ) from exc

        if not isinstance(data, dict):
            raise LLMFormatError(
                f"Expected a JSON object, got {type(data).__name__}: {raw[:200]!r}"
            )

        required = schema.get("required", [])
        missing = [k for k in required if k not in data]
        if missing:
            raise LLMFormatError(
                f"Response missing required fields {missing}. Got keys: {list(data.keys())}"
            )

        return data


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse_retry_after(exc: Exception) -> float:
    """Try to extract a numeric Retry-After value from a rate-limit exception."""
    try:
        headers = getattr(exc, "response", None)
        if headers is not None:
            headers = getattr(headers, "headers", {})
            ra = headers.get("Retry-After") or headers.get("retry-after")
            if ra is not None:
                return float(ra)
    except Exception:
        pass
    return 60.0
