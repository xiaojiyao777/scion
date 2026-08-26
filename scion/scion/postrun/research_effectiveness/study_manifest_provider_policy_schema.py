"""Strict pure schema for the private M32 provider-policy manifest join."""

from __future__ import annotations

import ipaddress
import math
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import SplitResult, urlsplit

from .study_manifest_controls_schema import _canonical_json_bytes, _freeze_json
from .study_manifest_schema import (
    _normalize_study_manifest,
    _NormalizedStudyManifest,
)

_MANIFEST_SCHEMA_VERSION = (
    "scion.initial_screening_study_manifest."
    "config_subset_and_requested_provider_policy.v2"
)
_JOIN_SCHEMA_VERSION = (
    "scion.initial_screening_study_manifest_join."
    "config_subset_and_requested_provider_policy.v2"
)
_SCOPE = "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_ONLY"
_STATUS = "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOINED"
_ERROR = "STUDY_CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOIN_INVALID"
_MANIFEST_MAX_BYTES = 16 << 20
_PROVIDER_POLICY_MAX_BYTES = 65_536
_V1_MANIFEST_SCHEMA_VERSION = "scion.initial_screening_study_manifest.config_subset.v1"
_V1_SCOPE = "CONFIG_SUBSET_ONLY"
_PROVIDER_SCHEMA_VERSION = "scion.initial_screening_provider_policy.v1"
_PROVIDER_SCOPE = "REQUESTED_PROVIDER_POLICY_ONLY"
_CLIENT_TYPE = "scion.proposal.llm.client.LLMClient"
_REQUEST_SPECS = (
    ("hypothesis", "generate_hypothesis"),
    ("hypothesis_research_turn", "hypothesis_research_turn"),
    ("code", "generate_patch"),
    ("code_research_turn", "code_research_turn"),
    ("code_research_finalize", "finalize_code_research"),
)
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_PROVIDER_LIMITATIONS = (
    "PROVIDER_CREDENTIAL_AND_ACCOUNT_IDENTITY_UNVERIFIED",
    "PROVIDER_PROCESS_NETWORK_TLS_ENVIRONMENT_UNVERIFIED",
    "REMOTE_PROVIDER_BACKEND_IDENTITY_UNVERIFIED",
    "PROVIDER_REQUEST_CODE_CONSTANTS_UNVERIFIED",
    "PROVIDER_TIMEOUT_AND_SDK_RETRY_ENFORCEMENT_UNVERIFIED",
    "LLM_CLIENT_LIFETIME_FRESHNESS_UNVERIFIED",
    "STUDY_MANIFEST_UNVERIFIED",
    "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
    "MATCHED_RESULT_UNAUTHORIZED",
    "LIVE_EXECUTION_UNAUTHORIZED",
    "STUDY_GO_UNAUTHORIZED",
)
_JOIN_LIMITATIONS = (
    "SCIENTIFIC_ENDPOINTS_NOT_EVALUATED",
    "PROBLEM_SPEC_UNVERIFIED",
    "PROBLEM_ADAPTER_UNVERIFIED",
    "RESEARCH_INPUT_UNVERIFIED",
    "RUNTIME_RESEARCH_HISTORY_CONSUMPTION_UNVERIFIED",
    "VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED",
    "PROVIDER_CREDENTIAL_AND_ACCOUNT_IDENTITY_UNVERIFIED",
    "PROVIDER_PROCESS_NETWORK_TLS_ENVIRONMENT_UNVERIFIED",
    "REMOTE_PROVIDER_BACKEND_IDENTITY_UNVERIFIED",
    "PROVIDER_REQUEST_CODE_CONSTANTS_UNVERIFIED",
    "PROVIDER_TIMEOUT_AND_SDK_RETRY_ENFORCEMENT_UNVERIFIED",
    "LLM_CLIENT_LIFETIME_FRESHNESS_UNVERIFIED",
    "SOURCE_CARRIER_UNVERIFIED",
    "B0_CONTENT_UNVERIFIED",
    "STUDY_MANIFEST_UNVERIFIED",
    "MANIFEST_GIT_AND_PREOUTCOME_TIMING_UNVERIFIED",
    "POPULATION_FRESHNESS_UNVERIFIED",
    "ACTUAL_ARM_ROOT_LAUNCH_ORDER_UNVERIFIED",
    "EXTERNAL_HARDWALL_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_RUNNER_BACKEND_AND_RUNTIME_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_CODE_CONSTANTS_UNVERIFIED",
    "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
    "MATCHED_RESULT_UNAUTHORIZED",
    "LIVE_EXECUTION_UNAUTHORIZED",
    "STUDY_GO_UNAUTHORIZED",
)


class _StudyManifestProviderPolicySchemaError(ValueError):
    """Fixed, body-free failure at the private v2 schema boundary."""


@dataclass(frozen=True, repr=False)
class _NormalizedDeclaredProviderPolicy:
    """Detached full S2c3 leaf declared once for all ten arms."""

    canonical_bytes: bytes
    frozen: tuple[Any, ...]

    def __repr__(self) -> str:
        return "_NormalizedDeclaredProviderPolicy(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _NormalizedStudyManifestProviderPolicy:
    """One strict v2 manifest split into frozen v1 and provider authorities."""

    base_manifest: _NormalizedStudyManifest
    declared_provider_policy: _NormalizedDeclaredProviderPolicy

    def __repr__(self) -> str:
        return "_NormalizedStudyManifestProviderPolicy(<redacted>)"

    __str__ = __repr__


def _normalize_study_manifest_provider_policy(
    value: Any,
) -> _NormalizedStudyManifestProviderPolicy:
    """Normalize one strict v2 manifest without widening the v1 API."""

    failed = False
    result: _NormalizedStudyManifestProviderPolicy | None = None
    try:
        result = _normalize_study_manifest_provider_policy_unsafe(value)
    except Exception:  # noqa: BLE001 - sanitize the private schema boundary
        failed = True
    if failed or result is None:
        raise _StudyManifestProviderPolicySchemaError(_ERROR)
    return result


def _normalize_declared_provider_policy(
    value: Any,
) -> _NormalizedDeclaredProviderPolicy:
    """Normalize one complete common S2c3 policy at the v2 error boundary."""

    failed = False
    result: _NormalizedDeclaredProviderPolicy | None = None
    try:
        result = _normalize_declared_provider_policy_unsafe(value)
    except Exception:  # noqa: BLE001 - sanitize the private schema boundary
        failed = True
    if failed or result is None:
        raise _StudyManifestProviderPolicySchemaError(_ERROR)
    return result


def _config_and_requested_provider_policy_join_result() -> dict[str, Any]:
    """Return the sole validation-success payload authorized by v2."""

    return {
        "schema_version": _JOIN_SCHEMA_VERSION,
        "status": _STATUS,
        "validated_scope": _SCOPE,
        "blocks_checked": 5,
        "arms_checked": 10,
        "limitations": list(_JOIN_LIMITATIONS),
    }


def _normalize_study_manifest_provider_policy_unsafe(
    value: Any,
) -> _NormalizedStudyManifestProviderPolicy:
    _canonical_json_bytes(value, max_bytes=_MANIFEST_MAX_BYTES)
    manifest = _exact_dict(
        value,
        {
            "schema_version",
            "scope",
            "problem_id",
            "declared_provider_policy",
            "blocks",
        },
    )
    if (
        manifest["schema_version"] != _MANIFEST_SCHEMA_VERSION
        or manifest["scope"] != _SCOPE
    ):
        raise ValueError
    provider_policy = _normalize_declared_provider_policy_unsafe(
        manifest["declared_provider_policy"]
    )
    base_manifest = _normalize_study_manifest(
        {
            "schema_version": _V1_MANIFEST_SCHEMA_VERSION,
            "scope": _V1_SCOPE,
            "problem_id": manifest["problem_id"],
            "blocks": manifest["blocks"],
        }
    )
    return _NormalizedStudyManifestProviderPolicy(
        base_manifest=base_manifest,
        declared_provider_policy=provider_policy,
    )


def _normalize_declared_provider_policy_unsafe(
    value: Any,
) -> _NormalizedDeclaredProviderPolicy:
    canonical = _canonical_json_bytes(value, max_bytes=_PROVIDER_POLICY_MAX_BYTES)
    policy = _exact_dict(
        value,
        {"schema_version", "scope", "limitations", "client", "request_policies"},
    )
    if (
        policy["schema_version"] != _PROVIDER_SCHEMA_VERSION
        or policy["scope"] != _PROVIDER_SCOPE
        or tuple(_exact_list(policy["limitations"])) != _PROVIDER_LIMITATIONS
    ):
        raise ValueError
    client = _exact_dict(
        policy["client"],
        {
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
        },
    )
    _validate_client(client)
    _validate_request_policies(_exact_list(policy["request_policies"]), client)
    return _NormalizedDeclaredProviderPolicy(
        canonical_bytes=canonical,
        frozen=_freeze_json(value),
    )


def _validate_client(client: dict[str, Any]) -> None:
    string_fields = {
        "client_type",
        "requested_model",
        "configured_base_url",
        "effective_sdk_base_url",
        "provider_transport",
        "requested_reasoning_effort",
        "effective_reasoning_effort",
        "thinking_mode",
    }
    if any(type(client[field]) is not str for field in string_fields):
        raise TypeError
    model = client["requested_model"]
    _validate_model(model)
    provider = "anthropic" if model.startswith("claude-") else "openai_compatible"
    configured = _canonical_base_url(client["configured_base_url"])
    effective_reasoning, thinking = _reasoning_policy(
        model,
        client["requested_reasoning_effort"],
        provider=provider,
    )
    if (
        client["client_type"] != _CLIENT_TYPE
        or client["provider_transport"] != provider
        or client["effective_sdk_base_url"]
        != _effective_sdk_base_url(configured, provider=provider)
        or client["effective_reasoning_effort"] != effective_reasoning
        or client["thinking_mode"] != thinking
        or type(client["base_timeout_sec"]) is not float
        or not math.isfinite(client["base_timeout_sec"])
        or client["base_timeout_sec"] <= 0.0
        or type(client["sdk_max_retries_requested"]) is not int
        or client["sdk_max_retries_requested"] != 0
    ):
        raise ValueError
    body = _exact_dict(
        client["request_body_policy"],
        {"temperature", "top_p", "seed", "stream", "system_blocks", "tool_choice"},
    )
    if any(type(item) is not str for item in body.values()):
        raise TypeError
    if any(
        body[key] != "omitted" for key in ("temperature", "top_p", "seed", "stream")
    ):
        raise ValueError
    expected_system = (
        "native_system_blocks" if provider == "anthropic" else "merged_into_user_prompt"
    )
    expected_tool = (
        "required_named_tool"
        if provider == "anthropic"
        else "omitted"
        if model.startswith("deepseek-")
        else "required_named_function"
    )
    if body["system_blocks"] != expected_system or body["tool_choice"] != expected_tool:
        raise ValueError


def _validate_request_policies(
    values: list[Any],
    client: dict[str, Any],
) -> None:
    if len(values) != len(_REQUEST_SPECS):
        raise ValueError
    provider = client["provider_transport"]
    anthropic = provider == "anthropic"
    fields = {
        "request_kind",
        "tool_name",
        "timeout_sec",
        "provider",
        "output_token_policy",
        "output_token_parameter",
        "provider_transport_output_ceiling_tokens",
    }
    for value, (request_kind, tool_name) in zip(values, _REQUEST_SPECS):
        policy = _exact_dict(value, fields)
        if any(
            type(policy[field]) is not str
            for field in (
                "request_kind",
                "tool_name",
                "provider",
                "output_token_policy",
                "output_token_parameter",
            )
        ):
            raise TypeError
        ceiling = policy["provider_transport_output_ceiling_tokens"]
        if (
            type(policy["timeout_sec"]) is not float
            or not math.isfinite(policy["timeout_sec"])
            or policy["timeout_sec"] <= 0.0
            or policy["request_kind"] != request_kind
            or policy["tool_name"] != tool_name
            or policy["provider"] != provider
            or policy["output_token_policy"]
            != ("provider_native_required" if anthropic else "provider_managed")
            or policy["output_token_parameter"]
            != ("max_tokens" if anthropic else "omitted")
            or ceiling != (16_384 if anthropic else None)
            or (ceiling is not None and type(ceiling) is not int)
        ):
            raise ValueError


def _validate_model(value: Any) -> None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value.encode("utf-8")) > 256
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)
    ):
        raise ValueError


def _reasoning_policy(model: str, requested: Any, *, provider: str) -> tuple[str, str]:
    if (
        type(requested) is not str
        or requested != requested.strip()
        or requested != requested.lower()
        or len(requested.encode("utf-8")) > 64
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in requested)
    ):
        raise ValueError
    if provider == "anthropic":
        allowed = {""}
        effective = ""
    elif model.startswith("deepseek-"):
        allowed = {"", "low", "medium", "high", "xhigh", "max"}
        effective = {"low": "high", "medium": "high", "xhigh": "max"}.get(
            requested, requested
        )
    elif model.lower().startswith(("gpt-", "codex-")):
        allowed = {"", "low", "medium", "high", "xhigh"}
        effective = requested
    else:
        allowed = {""}
        effective = ""
    if requested not in allowed:
        raise ValueError
    thinking = (
        "enabled" if model.startswith("deepseek-") and bool(effective) else "disabled"
    )
    return effective, thinking


def _canonical_base_url(value: Any) -> str:
    _validate_base_url_text(value)
    parsed, host, port = _parse_base_url(value)
    canonical_netloc = _canonical_url_netloc(parsed.netloc, host, port)
    if parsed.scheme == "http" and not _is_loopback_host(host):
        raise ValueError
    if (
        (parsed.path and not parsed.path.startswith("/"))
        or "//" in parsed.path
        or any(part in {".", ".."} for part in parsed.path.split("/"))
        or (len(parsed.path) > 1 and parsed.path.endswith("/"))
    ):
        raise ValueError
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


def _parse_base_url(value: str) -> tuple[SplitResult, str, int | None]:
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
    if port is not None and not 1 <= port <= 65_535:
        raise ValueError
    canonical = f"[{host}]" if ":" in host else host
    if port is not None:
        canonical = f"{canonical}:{port}"
    if raw_netloc != canonical:
        raise ValueError
    return canonical


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
    labels = host.split(".")
    if (
        len(host) > 253
        or host.endswith(".")
        or not labels
        or any(_DNS_LABEL.fullmatch(label) is None for label in labels)
    ):
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
        return "https://api.deepseek.com" if parsed.path == "/v1" else configured
    return configured if configured.endswith("/v1") else f"{configured}/v1"


def _exact_dict(value: Any, fields: set[str] | frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise TypeError
    if set(value) != fields:
        raise TypeError
    return value


def _exact_list(value: Any) -> list[Any]:
    if type(value) is not list:
        raise TypeError
    return value


__all__: tuple[str, ...] = ()
