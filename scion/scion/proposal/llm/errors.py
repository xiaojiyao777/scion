"""LLMClient error taxonomy and retry classification."""
from __future__ import annotations

import time

from .config import LLM_TRANSIENT_API_ERROR_CATEGORY


def _is_transient_provider_error(err_str: str) -> bool:
    """Return true for gateway failures that happen before model generation."""
    transient_markers = (
        "aihubmix_api_error",
        "new request failed",
        "bad gateway",
        "502 bad gateway",
        "service unavailable",
        "503 service unavailable",
        "gateway timeout",
        "504 gateway timeout",
        "error code: 500",
        "error code: 502",
        "error code: 503",
        "error code: 504",
        "status code: 500",
        "status code: 502",
        "status code: 503",
        "status code: 504",
        "http 500",
        "http 502",
        "http 503",
        "http 504",
        "internal server error",
        "temporarily unavailable",
        "upstream connect error",
        "<html",
        "<title>502",
        "connection reset",
        "connection aborted",
        "connection error",
        "remote end closed connection",
        "server disconnected",
        "network is unreachable",
        "temporary failure in name resolution",
    )
    return any(marker in err_str for marker in transient_markers)


def _is_timeout_error_text(err_str: str) -> bool:
    return (
        "timeout" in err_str
        or "timed out" in err_str
        or "read timed out" in err_str
    )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Base class for LLM-related errors."""


class LLMTimeoutError(LLMError):
    """API call timed out."""


class LLMTransientProviderError(LLMError):
    """Provider/gateway failed before a usable model response was produced."""


class LLMFormatError(LLMError):
    """LLM response does not conform to the expected JSON schema."""


class LLMRateLimitError(LLMError):
    """HTTP 429 — Too Many Requests."""

    def __init__(self, message: str, retry_after: float = 60.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMRetryExhaustedError(LLMError):
    """All retry attempts exhausted."""

    def __init__(
        self,
        message: str,
        *,
        last_error: Exception | None = None,
        failure_category: str | None = None,
    ) -> None:
        super().__init__(message)
        self.last_error = last_error
        self.failure_category = failure_category


class LLMBalanceError(LLMError):
    """API balance/credits exhausted (HTTP 403 with insufficient-balance message)."""


def is_llm_transient_api_error(exc: BaseException | None) -> bool:
    """Return true when an LLM error is transport/provider transient."""
    if exc is None:
        return False
    if isinstance(exc, (LLMTimeoutError, LLMTransientProviderError, LLMRateLimitError)):
        return True
    if isinstance(exc, LLMRetryExhaustedError):
        if exc.failure_category == LLM_TRANSIENT_API_ERROR_CATEGORY:
            return True
        if is_llm_transient_api_error(exc.last_error):
            return True
    err_str = str(exc).lower()
    return (
        _is_timeout_error_text(err_str)
        or _is_transient_provider_error(err_str)
        or "rate_limit" in err_str
        or "ratelimit" in err_str
        or "http 429" in err_str
        or "error code: 429" in err_str
    )



def _retry_exhausted_failure_category(
    last_error: Exception | None,
) -> str | None:
    if is_llm_transient_api_error(last_error):
        return LLM_TRANSIENT_API_ERROR_CATEGORY
    return None


def _masked_hard_timeout_error(
    exc: Exception,
    *,
    attempt_started_at: float | None,
    timeout_sec: float,
) -> LLMTimeoutError | None:
    """Return timeout when a provider masks our hard deadline as transport."""
    if attempt_started_at is None or timeout_sec <= 0:
        return None
    elapsed = time.monotonic() - attempt_started_at
    threshold = max(timeout_sec * 0.95, timeout_sec - 1.0)
    if elapsed < threshold:
        return None
    err_str = str(exc).lower()
    if (
        isinstance(exc, TimeoutError)
        or _is_timeout_error_text(err_str)
        or _is_transient_provider_error(err_str)
    ):
        return LLMTimeoutError(
            "LLM provider call exceeded hard timeout "
            f"{timeout_sec:.1f}s (elapsed {elapsed:.1f}s)"
        )
    return None


def _transient_retry_exhausted_error(
    *,
    request_label: str,
    total_attempts: int,
    last_error: Exception,
) -> LLMRetryExhaustedError:
    return LLMRetryExhaustedError(
        f"{request_label} failed after {total_attempts} transient API attempt(s). "
        f"Last error: {last_error}",
        last_error=last_error,
        failure_category=LLM_TRANSIENT_API_ERROR_CATEGORY,
    )


# ---------------------------------------------------------------------------
# Client
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

