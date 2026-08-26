"""Private frozen provider policy for the initial-screening study."""

from __future__ import annotations

import ipaddress
import math
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .config import (
    _ANTHROPIC_REQUIRED_MAX_TOKENS,
    _DEFAULT_CODE_TIMEOUT_SEC,
    _is_deepseek_model,
    _is_gpt_codex_model,
    _is_openai_model,
)

_CAPSULE_ATTRIBUTE = "_initial_screening_study_policy_capsule"
_PRISTINE_CLIENT_KEYS = frozenset(
    {
        "model",
        "reasoning_effort",
        "api_key",
        "base_url",
        "timeout_sec",
        "_last_usage_metadata",
        "_last_response_diagnostics",
        "_anthropic_client",
        "_openai_client",
    }
)
_REQUEST_SPECS = (
    ("hypothesis", "generate_hypothesis"),
    ("hypothesis_research_turn", "hypothesis_research_turn"),
    ("code", "generate_patch"),
    ("code_research_turn", "code_research_turn"),
    ("code_research_finalize", "finalize_code_research"),
)
_CODE_REQUEST_KINDS = frozenset(
    {"code", "code_research_turn", "code_research_finalize"}
)
_OMITTED = "omitted"
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


class _Redacted:
    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _FrozenRequestBodyPolicy(_Redacted):
    temperature: str
    top_p: str
    seed: str
    stream: str
    system_blocks: str
    tool_choice: str

    def to_projection(self) -> dict[str, str]:
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "seed": self.seed,
            "stream": self.stream,
            "system_blocks": self.system_blocks,
            "tool_choice": self.tool_choice,
        }


@dataclass(frozen=True, repr=False)
class _FrozenStudyRequestPolicy(_Redacted):
    request_kind: str
    tool_name: str
    timeout_sec: float
    provider: str
    output_token_policy: str
    output_token_parameter: str
    provider_transport_output_ceiling_tokens: int | None

    def to_projection(self) -> dict[str, Any]:
        return {
            "request_kind": self.request_kind,
            "tool_name": self.tool_name,
            "timeout_sec": self.timeout_sec,
            "provider": self.provider,
            "output_token_policy": self.output_token_policy,
            "output_token_parameter": self.output_token_parameter,
            "provider_transport_output_ceiling_tokens": (
                self.provider_transport_output_ceiling_tokens
            ),
        }


@dataclass(frozen=True, repr=False)
class _FrozenInitialScreeningStudyPolicy(_Redacted):
    client_type: str
    requested_model: str
    configured_base_url: str
    effective_sdk_base_url: str
    provider_transport: str
    requested_reasoning_effort: str
    effective_reasoning_effort: str
    thinking_mode: str
    base_timeout_sec: float
    sdk_max_retries_requested: int
    request_body_policy: _FrozenRequestBodyPolicy
    request_policies: tuple[_FrozenStudyRequestPolicy, ...]

    def to_projection(self) -> dict[str, Any]:
        return {
            "client_type": self.client_type,
            "requested_model": self.requested_model,
            "configured_base_url": self.configured_base_url,
            "effective_sdk_base_url": self.effective_sdk_base_url,
            "provider_transport": self.provider_transport,
            "requested_reasoning_effort": self.requested_reasoning_effort,
            "effective_reasoning_effort": self.effective_reasoning_effort,
            "thinking_mode": self.thinking_mode,
            "base_timeout_sec": self.base_timeout_sec,
            "sdk_max_retries_requested": self.sdk_max_retries_requested,
            "request_body_policy": self.request_body_policy.to_projection(),
        }


def _freeze_initial_screening_study_policy(
    client: Any,
) -> tuple[Any, _FrozenInitialScreeningStudyPolicy]:
    """Read the exact pristine client and five timeout overrides once."""

    storage = _validate_pristine_llm_client(client)
    model = storage["model"]
    reasoning = storage["reasoning_effort"]
    base_url = _canonical_base_url(storage["base_url"])
    provider = "openai_compatible" if _is_openai_model(model) else "anthropic"
    effective_reasoning, thinking_mode = _reasoning_policy(
        model,
        reasoning,
        provider=provider,
    )
    request_body_policy = _request_body_policy(
        model,
        provider=provider,
        thinking_mode=thinking_mode,
    )
    policies = tuple(
        _request_policy(
            request_kind=request_kind,
            tool_name=tool_name,
            base_timeout_sec=storage["timeout_sec"],
            provider=provider,
        )
        for request_kind, tool_name in _REQUEST_SPECS
    )
    capsule = _FrozenInitialScreeningStudyPolicy(
        client_type="scion.proposal.llm.client.LLMClient",
        requested_model=model,
        configured_base_url=base_url,
        effective_sdk_base_url=_effective_sdk_base_url(
            base_url,
            provider=provider,
        ),
        provider_transport=provider,
        requested_reasoning_effort=reasoning,
        effective_reasoning_effort=effective_reasoning,
        thinking_mode=thinking_mode,
        base_timeout_sec=storage["timeout_sec"],
        sdk_max_retries_requested=0,
        request_body_policy=request_body_policy,
        request_policies=policies,
    )
    _validate_frozen_study_provider_policy_shape(capsule)
    _validate_pristine_client_against_capsule(client, capsule)
    return client, capsule


def _install_initial_screening_study_policy(
    client: Any,
    capsule: Any,
) -> None:
    """Atomically attach one already-frozen capsule to its pristine client."""

    _validate_frozen_study_provider_policy_shape(capsule)
    _validate_pristine_client_against_capsule(client, capsule)
    try:
        setattr(client, _CAPSULE_ATTRIBUTE, capsule)
        _validate_frozen_llm_client_shape(client, capsule)
    except BaseException:  # noqa: BLE001 - roll back across async interruption
        try:
            present, installed = _literal_study_policy_capsule(client)
            if present and installed is capsule:
                object.__delattr__(client, _CAPSULE_ATTRIBUTE)
        finally:
            raise


def _uninstall_initial_screening_study_policy(
    client: Any,
    capsule: Any,
) -> None:
    """Remove only the exact capsule installed by the failed composition."""

    from .client import LLMClient

    if type(client) is not LLMClient:
        raise TypeError
    present, installed = _literal_study_policy_capsule(client)
    if not present or installed is not capsule:
        raise TypeError
    object.__delattr__(client, _CAPSULE_ATTRIBUTE)


def _validate_frozen_study_provider_policy_shape(capsule: Any) -> None:
    """Require the exact immutable capsule and independently derive its facts."""

    _validate_capsule_storage_and_leaf_types(capsule)
    if capsule.client_type != "scion.proposal.llm.client.LLMClient":
        raise ValueError
    _validate_model(capsule.requested_model)
    configured = _canonical_base_url(capsule.configured_base_url)
    provider = (
        "openai_compatible"
        if _is_openai_model(capsule.requested_model)
        else "anthropic"
    )
    effective_reasoning, thinking_mode = _reasoning_policy(
        capsule.requested_model,
        capsule.requested_reasoning_effort,
        provider=provider,
    )
    _validate_capsule_derived_values(
        capsule,
        configured=configured,
        provider=provider,
        effective_reasoning=effective_reasoning,
        thinking_mode=thinking_mode,
    )
    expected_body = _request_body_policy(
        capsule.requested_model,
        provider=provider,
        thinking_mode=thinking_mode,
    )
    _validate_request_body_policy(capsule.request_body_policy)
    if capsule.request_body_policy != expected_body:
        raise ValueError
    policies = capsule.request_policies
    if len(policies) != len(_REQUEST_SPECS):
        raise TypeError
    for entry, (request_kind, tool_name) in zip(policies, _REQUEST_SPECS):
        _validate_request_policy(entry)
        if entry.request_kind != request_kind or entry.tool_name != tool_name:
            raise ValueError
        if entry.provider != provider:
            raise ValueError


def _validate_capsule_storage_and_leaf_types(capsule: Any) -> None:
    if type(capsule) is not _FrozenInitialScreeningStudyPolicy:
        raise TypeError
    storage = vars(capsule)
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or set(storage)
        != {
            "client_type",
            "requested_model",
            "configured_base_url",
            "effective_sdk_base_url",
            "provider_transport",
            "requested_reasoning_effort",
            "effective_reasoning_effort",
            "thinking_mode",
            "base_timeout_sec",
            "sdk_max_retries_requested",
            "request_body_policy",
            "request_policies",
        }
    ):
        raise TypeError
    if (
        type(capsule.client_type) is not str
        or type(capsule.requested_model) is not str
        or type(capsule.configured_base_url) is not str
        or type(capsule.effective_sdk_base_url) is not str
        or type(capsule.provider_transport) is not str
        or type(capsule.requested_reasoning_effort) is not str
        or type(capsule.effective_reasoning_effort) is not str
        or type(capsule.thinking_mode) is not str
        or type(capsule.base_timeout_sec) is not float
        or type(capsule.sdk_max_retries_requested) is not int
        or type(capsule.request_body_policy) is not _FrozenRequestBodyPolicy
        or type(capsule.request_policies) is not tuple
    ):
        raise TypeError


def _validate_capsule_derived_values(
    capsule: _FrozenInitialScreeningStudyPolicy,
    *,
    configured: str,
    provider: str,
    effective_reasoning: str,
    thinking_mode: str,
) -> None:
    if (
        configured != capsule.configured_base_url
        or capsule.provider_transport != provider
        or capsule.effective_sdk_base_url
        != _effective_sdk_base_url(configured, provider=provider)
        or capsule.effective_reasoning_effort != effective_reasoning
        or capsule.thinking_mode != thinking_mode
        or not math.isfinite(capsule.base_timeout_sec)
        or capsule.base_timeout_sec <= 0.0
        or capsule.sdk_max_retries_requested != 0
    ):
        raise ValueError


def _validate_frozen_llm_client_shape(client: Any, capsule: Any) -> None:
    """Join the installed capsule to the same exact LLMClient instance."""

    _validate_frozen_study_provider_policy_shape(capsule)
    from .client import LLMClient

    if type(client) is not LLMClient:
        raise TypeError
    storage = vars(client)
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or set(storage) != set(_PRISTINE_CLIENT_KEYS) | {_CAPSULE_ATTRIBUTE}
    ):
        raise TypeError
    if storage[_CAPSULE_ATTRIBUTE] is not capsule:
        raise ValueError
    _validate_client_values(storage)
    _validate_client_values_against_capsule(storage, capsule)


def _resolve_initial_screening_study_policy_entry(
    client: Any,
    *,
    request_kind: Any,
    tool: Any,
    model: Any,
) -> _FrozenStudyRequestPolicy | None:
    """Return the installed typed entry, or ``None`` for a legacy caller."""

    from .client import LLMClient

    if type(client) is not LLMClient:
        return None
    if not _has_literal_initial_screening_study_policy_capsule(client):
        return None
    storage = vars(client)
    if type(storage) is not dict or any(type(key) is not str for key in storage):
        raise TypeError
    capsule = storage[_CAPSULE_ATTRIBUTE]
    _validate_installed_client_policy_config(client, capsule)
    if (
        type(request_kind) is not str
        or type(model) is not str
        or model != capsule.requested_model
        or type(tool) is not dict
    ):
        raise ValueError
    tool_name = tool.get("name")
    if type(tool_name) is not str:
        raise ValueError
    for entry in capsule.request_policies:
        if entry.request_kind == request_kind:
            if entry.tool_name != tool_name:
                raise ValueError
            return entry
    raise ValueError


def _has_installed_initial_screening_study_policy(client: Any) -> bool:
    """Report only the literal capsule attribute on an exact LLMClient."""

    return _has_literal_initial_screening_study_policy_capsule(client)


def _has_literal_initial_screening_study_policy_capsule(client: Any) -> bool:
    """Inspect only the literal raw key without invoking a mapping override."""

    present, _capsule = _literal_study_policy_capsule(client)
    return present


def _literal_study_policy_capsule(client: Any) -> tuple[bool, Any]:
    """Return the raw literal capsule entry without mapping dispatch."""

    from .client import LLMClient

    if type(client) is not LLMClient:
        return False, None
    storage = vars(client)
    if not isinstance(storage, dict):
        return False, None
    for key, value in dict.items(storage):
        if type(key) is str and key == _CAPSULE_ATTRIBUTE:
            return True, value
    return False, None


def _validate_initial_screening_study_policy_entry(
    client: Any,
    entry: Any,
    *,
    request_kind: Any,
    tool: Any,
    model: Any,
) -> _FrozenStudyRequestPolicy | None:
    """Require the caller to pass the exact installed entry on frozen runs."""

    expected = _resolve_initial_screening_study_policy_entry(
        client,
        request_kind=request_kind,
        tool=tool,
        model=model,
    )
    if expected is None:
        if entry is not None:
            raise ValueError
        return None
    if entry is not expected:
        raise ValueError
    return expected


def _installed_initial_screening_study_policy(client: Any, entry: Any) -> Any:
    """Return the exact installed capsule owning *entry*."""

    storage = vars(client)
    if type(storage) is not dict or any(type(key) is not str for key in storage):
        raise TypeError
    capsule = storage.get(_CAPSULE_ATTRIBUTE)
    if type(capsule) is not _FrozenInitialScreeningStudyPolicy:
        raise TypeError
    _validate_installed_client_policy_config(client, capsule)
    if type(entry) is not _FrozenStudyRequestPolicy or not any(
        item is entry for item in capsule.request_policies
    ):
        raise ValueError
    return capsule


def _validate_pristine_llm_client(client: Any) -> dict[str, Any]:
    from .client import LLMClient

    if type(client) is not LLMClient:
        raise TypeError
    storage = vars(client)
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or set(storage) != set(_PRISTINE_CLIENT_KEYS)
    ):
        raise TypeError
    _validate_client_values(storage)
    return storage


def _validate_client_values(storage: dict[str, Any]) -> None:
    _validate_client_config_values(storage)
    if (
        storage["_last_usage_metadata"] is not None
        or storage["_last_response_diagnostics"] is not None
        or storage["_anthropic_client"] is not None
        or storage["_openai_client"] is not None
    ):
        raise ValueError


def _validate_client_config_values(storage: dict[str, Any]) -> None:
    if (
        type(storage["model"]) is not str
        or type(storage["reasoning_effort"]) is not str
        or type(storage["api_key"]) is not str
        or type(storage["base_url"]) is not str
        or type(storage["timeout_sec"]) is not float
        or not storage["api_key"]
        or not math.isfinite(storage["timeout_sec"])
        or storage["timeout_sec"] <= 0.0
    ):
        raise ValueError
    _validate_model(storage["model"])
    _validate_reasoning_text(storage["reasoning_effort"])
    _canonical_base_url(storage["base_url"])


def _validate_installed_client_policy_config(client: Any, capsule: Any) -> None:
    from .client import LLMClient

    _validate_frozen_study_provider_policy_shape(capsule)
    if type(client) is not LLMClient:
        raise TypeError
    storage = vars(client)
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or set(storage) != set(_PRISTINE_CLIENT_KEYS) | {_CAPSULE_ATTRIBUTE}
        or storage[_CAPSULE_ATTRIBUTE] is not capsule
    ):
        raise TypeError
    _validate_client_config_values(storage)
    _validate_client_values_against_capsule(storage, capsule)


def _validate_pristine_client_against_capsule(client: Any, capsule: Any) -> None:
    storage = _validate_pristine_llm_client(client)
    _validate_client_values_against_capsule(storage, capsule)


def _validate_client_values_against_capsule(
    storage: dict[str, Any],
    capsule: _FrozenInitialScreeningStudyPolicy,
) -> None:
    if (
        storage["model"] != capsule.requested_model
        or _canonical_base_url(storage["base_url"]) != capsule.configured_base_url
        or storage["reasoning_effort"] != capsule.requested_reasoning_effort
        or storage["timeout_sec"] != capsule.base_timeout_sec
    ):
        raise ValueError


def _validate_model(model: Any) -> None:
    if (
        type(model) is not str
        or not model
        or model != model.strip()
        or len(model.encode("utf-8")) > 256
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in model)
    ):
        raise ValueError


def _validate_reasoning_text(reasoning: Any) -> None:
    if (
        type(reasoning) is not str
        or reasoning != reasoning.strip()
        or len(reasoning.encode("utf-8")) > 64
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in reasoning)
    ):
        raise ValueError


def _reasoning_policy(
    model: str,
    requested: Any,
    *,
    provider: str,
) -> tuple[str, str]:
    _validate_reasoning_text(requested)
    normalized = requested.lower()
    if requested != normalized:
        raise ValueError
    if provider == "anthropic":
        allowed = {""}
        effective = ""
    elif _is_deepseek_model(model):
        allowed = {"", "low", "medium", "high", "xhigh", "max"}
        if normalized in {"low", "medium"}:
            effective = "high"
        elif normalized == "xhigh":
            effective = "max"
        else:
            effective = normalized
    elif _is_gpt_codex_model(model):
        allowed = {"", "low", "medium", "high", "xhigh"}
        effective = normalized
    else:
        allowed = {""}
        effective = ""
    if normalized not in allowed:
        raise ValueError
    thinking = (
        "enabled" if _is_deepseek_model(model) and bool(effective) else "disabled"
    )
    return effective, thinking


def _request_body_policy(
    model: str,
    *,
    provider: str,
    thinking_mode: str,
) -> _FrozenRequestBodyPolicy:
    if provider == "anthropic":
        system_blocks = "native_system_blocks"
        tool_choice = "required_named_tool"
    else:
        system_blocks = "merged_into_user_prompt"
        tool_choice = (
            "omitted" if _is_deepseek_model(model) else "required_named_function"
        )
    if thinking_mode not in {"disabled", "enabled"}:
        raise ValueError
    return _FrozenRequestBodyPolicy(
        temperature=_OMITTED,
        top_p=_OMITTED,
        seed=_OMITTED,
        stream=_OMITTED,
        system_blocks=system_blocks,
        tool_choice=tool_choice,
    )


def _validate_request_body_policy(value: Any) -> None:
    storage = vars(value) if type(value) is _FrozenRequestBodyPolicy else None
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or set(storage)
        != {
            "temperature",
            "top_p",
            "seed",
            "stream",
            "system_blocks",
            "tool_choice",
        }
    ):
        raise TypeError
    if any(type(item) is not str for item in storage.values()):
        raise TypeError


def _request_policy(
    *,
    request_kind: str,
    tool_name: str,
    base_timeout_sec: float,
    provider: str,
) -> _FrozenStudyRequestPolicy:
    timeout = (
        max(base_timeout_sec, _DEFAULT_CODE_TIMEOUT_SEC)
        if request_kind in _CODE_REQUEST_KINDS
        else base_timeout_sec
    )
    env_name = f"SCION_LLM_{request_kind.upper()}_TIMEOUT_SEC"
    raw = os.environ.get(env_name)
    if raw is not None:
        if type(raw) is not str:
            raise TypeError
        if raw != "" and raw != raw.strip():
            raise ValueError
        if raw != "":
            try:
                timeout = float(raw)
            except ValueError as exc:
                raise ValueError from exc
            if not math.isfinite(timeout) or timeout <= 0.0:
                raise ValueError
    timeout = float(timeout)
    anthropic = provider == "anthropic"
    return _FrozenStudyRequestPolicy(
        request_kind=request_kind,
        tool_name=tool_name,
        timeout_sec=timeout,
        provider=provider,
        output_token_policy=(
            "provider_native_required" if anthropic else "provider_managed"
        ),
        output_token_parameter="max_tokens" if anthropic else "omitted",
        provider_transport_output_ceiling_tokens=(
            _ANTHROPIC_REQUIRED_MAX_TOKENS if anthropic else None
        ),
    )


def _validate_request_policy(value: Any) -> None:
    storage = vars(value) if type(value) is _FrozenStudyRequestPolicy else None
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or set(storage)
        != {
            "request_kind",
            "tool_name",
            "timeout_sec",
            "provider",
            "output_token_policy",
            "output_token_parameter",
            "provider_transport_output_ceiling_tokens",
        }
    ):
        raise TypeError
    if (
        type(value.request_kind) is not str
        or type(value.tool_name) is not str
        or type(value.timeout_sec) is not float
        or type(value.provider) is not str
        or type(value.output_token_policy) is not str
        or type(value.output_token_parameter) is not str
        or (
            value.provider_transport_output_ceiling_tokens is not None
            and type(value.provider_transport_output_ceiling_tokens) is not int
        )
    ):
        raise TypeError
    if (
        not math.isfinite(value.timeout_sec)
        or value.timeout_sec <= 0.0
        or value.provider not in {"anthropic", "openai_compatible"}
    ):
        raise ValueError
    anthropic = value.provider == "anthropic"
    if (
        value.output_token_policy
        != ("provider_native_required" if anthropic else "provider_managed")
        or value.output_token_parameter != ("max_tokens" if anthropic else "omitted")
        or value.provider_transport_output_ceiling_tokens
        != (_ANTHROPIC_REQUIRED_MAX_TOKENS if anthropic else None)
    ):
        raise ValueError


def _canonical_base_url(value: Any) -> str:
    _validate_base_url_text(value)
    parsed, host, port = _parse_base_url(value)
    canonical_netloc = _canonical_url_netloc(parsed.netloc, host, port)
    _validate_url_transport(parsed.scheme, host)
    _validate_url_path(parsed.path)
    canonical_path = "" if parsed.path == "/" else parsed.path
    canonical = f"{parsed.scheme}://{canonical_netloc}{canonical_path}"
    if value != canonical:
        raise ValueError
    return canonical


def _validate_base_url_text(value: Any) -> None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value.encode("utf-8")) > 2048
        or any(ord(char) > 0x7F for char in value)
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)
        or any(char.isspace() for char in value)
        or any(char in value for char in ("\\", "%", "?", "#"))
    ):
        raise ValueError


def _parse_base_url(value: str) -> tuple[Any, str, int | None]:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or "@" in parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.netloc.endswith(":")
    ):
        raise ValueError
    host = parsed.hostname
    if type(host) is not str or not host or host != host.lower():
        raise ValueError
    _validate_host(host)
    return parsed, host, port


def _canonical_url_netloc(raw_netloc: str, host: str, port: int | None) -> str:
    if port is not None and not 1 <= port <= 65535:
        raise ValueError
    canonical_netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        canonical_netloc = f"{canonical_netloc}:{port}"
    if raw_netloc != canonical_netloc:
        raise ValueError
    return canonical_netloc


def _validate_url_transport(scheme: str, host: str) -> None:
    if scheme == "http" and not _is_loopback_host(host):
        raise ValueError


def _validate_url_path(path: str) -> None:
    if path and not path.startswith("/"):
        raise ValueError
    if "//" in path or any(part in {".", ".."} for part in path.split("/")):
        raise ValueError
    if len(path) > 1 and path.endswith("/"):
        raise ValueError


def _validate_host(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if _is_numeric_looking_host(host):
            raise ValueError
    else:
        if host != address.compressed:
            raise ValueError
        return
    if len(host) > 253 or host.endswith("."):
        raise ValueError
    labels = host.split(".")
    if not labels or any(_DNS_LABEL.fullmatch(label) is None for label in labels):
        raise ValueError


def _is_numeric_looking_host(host: str) -> bool:
    parts = host.split(".")
    return bool(parts) and all(
        part.isdigit()
        or (
            part.startswith("0x")
            and len(part) > 2
            and all(character in "0123456789abcdef" for character in part[2:])
        )
        for part in parts
    )


def _is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _effective_sdk_base_url(configured: str, *, provider: str) -> str:
    if provider == "anthropic":
        return configured
    parsed = urlsplit(configured)
    if parsed.hostname == "api.deepseek.com":
        if parsed.path == "/v1":
            return "https://api.deepseek.com"
        return configured
    if configured.endswith("/v1"):
        return configured
    return f"{configured}/v1"


__all__ = []
