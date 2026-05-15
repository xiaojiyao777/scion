"""LLMClient — wraps LLM API calls with timeout + format-error retry logic.

Supports Claude models via Anthropic SDK and GPT/OpenAI models via OpenAI SDK,
both through aihubmix proxy.
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
_DEFAULT_TIMEOUT_SEC = 60.0
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_SDK_MAX_RETRIES = 0
_DEFAULT_MAX_TOKENS = 16384
_DEFAULT_CODE_TIMEOUT_SEC = 180.0
_DEFAULT_CODE_MAX_RETRIES = 0

_ANTHROPIC_MODEL_PREFIXES = ("claude-",)
_CODE_REQUEST_KINDS = {"code", "fix"}
_TOOL_REQUEST_KIND_BY_NAME = {
    "generate_patch": "code",
    "fix_patch": "fix",
    "generate_hypothesis": "hypothesis",
    "plan_proposal_tool_call": "tool_selection",
}


def _is_openai_model(model: str) -> bool:
    """Non-Anthropic models use the OpenAI-compatible API via aihubmix."""
    return not any(model.startswith(p) for p in _ANTHROPIC_MODEL_PREFIXES)


def _normalize_request_kind(
    *,
    request_kind: str | None = None,
    tool: Dict[str, Any] | None = None,
) -> str | None:
    if request_kind:
        return str(request_kind).strip().lower() or None
    if not tool:
        return None
    name = tool.get("name")
    if not name and isinstance(tool.get("function"), dict):
        name = tool["function"].get("name")
    if name is None:
        return None
    return _TOOL_REQUEST_KIND_BY_NAME.get(str(name), None)


def _request_kind_env_key(request_kind: str | None) -> str | None:
    if not request_kind:
        return None
    cleaned = "".join(
        char.upper() if char.isalnum() else "_"
        for char in str(request_kind)
    ).strip("_")
    return cleaned or None


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
        request_kind: str | None = None,
    ) -> Dict[str, Any]:
        """Call LLM with tool_use and return the tool input dict directly.

        Supports both Anthropic (Claude) and OpenAI (GPT) models.
        """
        effective_model = model or self.model
        policy = self.resolve_request_policy(request_kind=request_kind, tool=tool)
        max_retries = policy["max_retries"]
        timeout_sec = policy["timeout_sec"]
        attempt = 0
        last_error: Exception | None = None
        current_max_tokens = self.max_tokens
        truncation_retries = 0

        while attempt <= max_retries:
            try:
                result, truncated = self._tool_call_once(
                    prompt,
                    tool,
                    effective_model,
                    system_blocks,
                    current_max_tokens,
                    timeout_sec,
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
                    raise LLMFormatError(f"Tool input missing required fields: {missing}")
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

            except (LLMBalanceError, LLMRetryExhaustedError):
                raise

            except Exception as exc:
                try:
                    self._raise_classified(exc)
                except LLMRateLimitError as rle:
                    last_error = rle
                    if priority == "background":
                        raise
                    time.sleep(rle.retry_after)
                    continue
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
            f"Last error: {last_error}"
        ) from last_error

    def resolve_request_policy(
        self,
        *,
        request_kind: str | None = None,
        tool: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Return the effective timeout/retry policy for one LLM request.

        Code-generation requests are long non-streaming tool calls.  By default
        they get a longer client timeout and no same-prompt transport retry, so
        Scion does not abandon requests that often finish just after 60 seconds
        and then duplicate them in the provider backend.
        """
        normalized = _normalize_request_kind(request_kind=request_kind, tool=tool)
        timeout_sec = self.timeout_sec
        max_retries = self.max_retries

        if normalized in _CODE_REQUEST_KINDS:
            timeout_sec = max(self.timeout_sec, _DEFAULT_CODE_TIMEOUT_SEC)
            max_retries = _DEFAULT_CODE_MAX_RETRIES

        env_key = _request_kind_env_key(normalized)
        if env_key:
            timeout_sec = _env_float(
                f"SCION_LLM_{env_key}_TIMEOUT_SEC",
                timeout_sec,
            )
            max_retries = _env_int(
                f"SCION_LLM_{env_key}_MAX_RETRIES",
                max_retries,
            )

        return {
            "request_kind": normalized or "default",
            "timeout_sec": timeout_sec,
            "max_retries": max_retries,
            "sdk_max_retries": self.sdk_max_retries,
            "max_tokens": self.max_tokens,
        }

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
            model=model,
            max_completion_tokens=max_tokens,
            messages=messages,
            tools=[openai_tool],
            tool_choice={"type": "function", "function": {"name": tool_name}},
            timeout=timeout_sec,
        )

        usage = response.usage
        if usage:
            self._cache_stats["calls"] += 1
            self._cache_stats["uncached_tokens"] += usage.prompt_tokens or 0

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
                model=model,
                max_completion_tokens=self.max_tokens,
                messages=messages,
                timeout=self.timeout_sec,
            )
            usage = response.usage
            if usage:
                input_tokens = usage.prompt_tokens or 0
                output_tokens = usage.completion_tokens or 0
                self._cache_stats["calls"] += 1
                self._cache_stats["uncached_tokens"] += input_tokens
                if self._token_tracker is not None:
                    self._token_tracker.record(
                        request_kind="llm_call",
                        model_id=model,
                        prompt_tokens=input_tokens,
                        completion_tokens=output_tokens,
                        cache_read_tokens=0,
                        cache_create_tokens=0,
                    )
            return response.choices[0].message.content
        except Exception as exc:
            self._raise_classified(exc)

    @staticmethod
    def _raise_classified(exc: Exception) -> None:
        """Classify a raw SDK exception and re-raise as the appropriate LLM* type."""
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
            if not base.endswith("/v1"):
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


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return int(default)
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning("Ignoring invalid %s=%r; using %d", name, raw, default)
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return float(default)
    try:
        return max(0.001, float(raw))
    except ValueError:
        logger.warning("Ignoring invalid %s=%r; using %.3f", name, raw, default)
        return float(default)
