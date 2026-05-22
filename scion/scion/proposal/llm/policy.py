"""Request policy resolution for LLMClient."""
from __future__ import annotations

from typing import Any, Dict

from .config import (
    _CODE_REQUEST_KINDS,
    _DEFAULT_CODE_MAX_RETRIES,
    _DEFAULT_CODE_TIMEOUT_SEC,
    _DEFAULT_TRANSIENT_PROVIDER_MAX_RETRIES,
    _env_float,
    _env_int,
    _normalize_request_kind,
    _request_kind_env_key,
)


class PolicyMixin:
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
        transient_max_retries = _env_int(
            "SCION_LLM_TRANSIENT_PROVIDER_MAX_RETRIES",
            _DEFAULT_TRANSIENT_PROVIDER_MAX_RETRIES,
        )

        return {
            "request_kind": normalized or "default",
            "timeout_sec": timeout_sec,
            "max_retries": max_retries,
            "transient_max_retries": transient_max_retries,
            "sdk_max_retries": self.sdk_max_retries,
            "max_tokens": self.max_tokens,
        }

