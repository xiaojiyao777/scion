"""Implementation package for LLMClient."""
from scion.proposal.llm.client import LLMClient
from scion.proposal.llm.config import LLM_TRANSIENT_API_ERROR_CATEGORY, MAX_MAX_TOKENS, MAX_TRUNCATION_RETRIES
from scion.proposal.llm.errors import (
    LLMBalanceError,
    LLMError,
    LLMFormatError,
    LLMRateLimitError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
    LLMTransientProviderError,
    is_llm_transient_api_error,
)

__all__ = [
    "LLMClient",
    "LLM_TRANSIENT_API_ERROR_CATEGORY",
    "MAX_MAX_TOKENS",
    "MAX_TRUNCATION_RETRIES",
    "LLMBalanceError",
    "LLMError",
    "LLMFormatError",
    "LLMRateLimitError",
    "LLMRetryExhaustedError",
    "LLMTimeoutError",
    "LLMTransientProviderError",
    "is_llm_transient_api_error",
]
