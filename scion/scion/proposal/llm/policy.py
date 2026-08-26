"""Request policy resolution for LLMClient."""

from __future__ import annotations

from typing import Any, Dict

from .config import (
    _ANTHROPIC_REQUIRED_MAX_TOKENS,
    _CODE_REQUEST_KINDS,
    _DEFAULT_CODE_TIMEOUT_SEC,
    _env_float,
    _is_openai_model,
    _normalize_request_kind,
    _request_kind_env_key,
)

_PROVIDER_MANAGED_OUTPUT = "provider_managed"
_PROVIDER_NATIVE_REQUIRED_OUTPUT = "provider_native_required"


class PolicyMixin:
    model: str
    timeout_sec: float

    def resolve_request_policy(
        self,
        *,
        request_kind: str | None = None,
        tool: Dict[str, Any] | None = None,
        model: str | None = None,
    ) -> Dict[str, Any]:
        """Return the effective transport/output policy for one LLM request.

        Code-generation requests are long non-streaming tool calls.  By default
        they get a longer client timeout.  Every request is a single transport
        call; timeout is a process-safety boundary, never a retry trigger.

        OpenAI-compatible proposal calls leave output length to the provider.
        Anthropic's SDK requires ``max_tokens``; that provider-native transport
        requirement is reported explicitly and is not a Scion retry policy.
        """
        from .study_policy import (
            _has_installed_initial_screening_study_policy,
            _resolve_initial_screening_study_policy_entry,
        )

        if _has_installed_initial_screening_study_policy(self):
            if type(request_kind) is not str or type(tool) is not dict:
                raise ValueError
            entry = _resolve_initial_screening_study_policy_entry(
                self,
                request_kind=request_kind,
                tool=tool,
                model=self.model if model is None else model,
            )
            if entry is None:
                raise ValueError
            return entry.to_projection()
        normalized = _normalize_request_kind(request_kind=request_kind, tool=tool)
        timeout_sec = self.timeout_sec

        if normalized in _CODE_REQUEST_KINDS:
            timeout_sec = max(self.timeout_sec, _DEFAULT_CODE_TIMEOUT_SEC)

        env_key = _request_kind_env_key(normalized)
        if env_key:
            timeout_sec = _env_float(
                f"SCION_LLM_{env_key}_TIMEOUT_SEC",
                timeout_sec,
            )
        effective_model = str(model or self.model)
        provider_managed_output = _is_openai_model(effective_model)

        return {
            "request_kind": normalized or "default",
            "timeout_sec": timeout_sec,
            "provider": (
                "openai_compatible" if provider_managed_output else "anthropic"
            ),
            "output_token_policy": (
                _PROVIDER_MANAGED_OUTPUT
                if provider_managed_output
                else _PROVIDER_NATIVE_REQUIRED_OUTPUT
            ),
            "output_token_parameter": (
                "omitted" if provider_managed_output else "max_tokens"
            ),
            "provider_transport_output_ceiling_tokens": (
                None if provider_managed_output else _ANTHROPIC_REQUIRED_MAX_TOKENS
            ),
        }
