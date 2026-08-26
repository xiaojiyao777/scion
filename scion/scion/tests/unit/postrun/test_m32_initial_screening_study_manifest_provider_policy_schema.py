from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scion.postrun.research_effectiveness import (
    study_manifest_provider_policy_schema as schema_module,
)
from scion.postrun.research_effectiveness.study_manifest_provider_policy_schema import (
    _ERROR,
    _JOIN_LIMITATIONS,
    _config_and_requested_provider_policy_join_result,
    _normalize_declared_provider_policy,
    _normalize_study_manifest_provider_policy,
    _StudyManifestProviderPolicySchemaError,
)
from scion.postrun.research_effectiveness.study_manifest_schema import (
    _config_subset_join_result,
    _normalize_study_manifest,
    _StudyManifestSchemaError,
)
from scion.tests.unit.postrun.test_m32_initial_screening_study_manifest_schema import (
    _manifest as _v1_manifest,
)

_MANIFEST_VERSION = (
    "scion.initial_screening_study_manifest."
    "config_subset_and_requested_provider_policy.v2"
)
_JOIN_VERSION = (
    "scion.initial_screening_study_manifest_join."
    "config_subset_and_requested_provider_policy.v2"
)
_SCOPE = "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_ONLY"
_STATUS = "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOINED"
_EXPECTED_PROVIDER_LIMITATIONS = (
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
_EXPECTED_JOIN_LIMITATIONS = (
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
_REQUEST_SPECS = (
    ("hypothesis", "generate_hypothesis"),
    ("hypothesis_research_turn", "hypothesis_research_turn"),
    ("code", "generate_patch"),
    ("code_research_turn", "code_research_turn"),
    ("code_research_finalize", "finalize_code_research"),
)


def _provider_policy() -> dict[str, Any]:
    policies = [
        {
            "request_kind": kind,
            "tool_name": tool,
            "timeout_sec": 60.0 + index,
            "provider": "openai_compatible",
            "output_token_policy": "provider_managed",
            "output_token_parameter": "omitted",
            "provider_transport_output_ceiling_tokens": None,
        }
        for index, (kind, tool) in enumerate(_REQUEST_SPECS)
    ]
    return {
        "schema_version": "scion.initial_screening_provider_policy.v1",
        "scope": "REQUESTED_PROVIDER_POLICY_ONLY",
        "limitations": list(_EXPECTED_PROVIDER_LIMITATIONS),
        "client": {
            "client_type": "scion.proposal.llm.client.LLMClient",
            "requested_model": "gpt-5.6-sol",
            "configured_base_url": "https://provider.example",
            "effective_sdk_base_url": "https://provider.example/v1",
            "provider_transport": "openai_compatible",
            "requested_reasoning_effort": "medium",
            "effective_reasoning_effort": "medium",
            "thinking_mode": "disabled",
            "base_timeout_sec": 60.0,
            "sdk_max_retries_requested": 0,
            "request_body_policy": {
                "temperature": "omitted",
                "top_p": "omitted",
                "seed": "omitted",
                "stream": "omitted",
                "system_blocks": "merged_into_user_prompt",
                "tool_choice": "required_named_function",
            },
        },
        "request_policies": policies,
    }


def _manifest() -> dict[str, Any]:
    value = _v1_manifest()
    value["schema_version"] = _MANIFEST_VERSION
    value["scope"] = _SCOPE
    value["declared_provider_policy"] = _provider_policy()
    return value


def _set_policy_family(
    policy: dict[str, Any],
    *,
    model: str,
    configured_url: str,
    effective_url: str,
    provider: str,
    requested_reasoning: str,
    effective_reasoning: str,
    thinking_mode: str,
    system_blocks: str,
    tool_choice: str,
) -> None:
    client = policy["client"]
    client.update(
        {
            "requested_model": model,
            "configured_base_url": configured_url,
            "effective_sdk_base_url": effective_url,
            "provider_transport": provider,
            "requested_reasoning_effort": requested_reasoning,
            "effective_reasoning_effort": effective_reasoning,
            "thinking_mode": thinking_mode,
        }
    )
    client["request_body_policy"].update(
        {"system_blocks": system_blocks, "tool_choice": tool_choice}
    )
    anthropic = provider == "anthropic"
    for item in policy["request_policies"]:
        item.update(
            {
                "provider": provider,
                "output_token_policy": (
                    "provider_native_required" if anthropic else "provider_managed"
                ),
                "output_token_parameter": "max_tokens" if anthropic else "omitted",
                "provider_transport_output_ceiling_tokens": (
                    16_384 if anthropic else None
                ),
            }
        )


def _fixed_error(call: Any) -> None:
    with pytest.raises(_StudyManifestProviderPolicySchemaError) as raised:
        call()
    error = raised.value
    assert str(error) == _ERROR
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_normalizes_v2_as_detached_v1_and_one_common_provider_policy() -> None:
    raw = _manifest()
    expected_policy_bytes = (
        json.dumps(
            raw["declared_provider_policy"],
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    normalized = _normalize_study_manifest_provider_policy(raw)
    assert normalized.base_manifest.problem_id == "cvrp"
    assert len(normalized.base_manifest.blocks) == 5
    assert normalized.declared_provider_policy.canonical_bytes == expected_policy_bytes
    assert repr(normalized) == "_NormalizedStudyManifestProviderPolicy(<redacted>)"
    assert (
        repr(normalized.declared_provider_policy)
        == "_NormalizedDeclaredProviderPolicy(<redacted>)"
    )

    raw["problem_id"] = "drift"
    raw["declared_provider_policy"]["client"]["requested_model"] = "secret-drift"
    assert normalized.base_manifest.problem_id == "cvrp"
    assert normalized.declared_provider_policy.canonical_bytes == expected_policy_bytes
    assert "secret-drift" not in repr(normalized)


def test_declared_policy_is_exact_producer_bytes_and_bounded() -> None:
    policy = _provider_policy()
    normalized = _normalize_declared_provider_policy(policy)
    assert len(normalized.canonical_bytes) <= 65_536
    assert normalized.canonical_bytes.endswith(b"\n")
    assert b'"api_key"' not in normalized.canonical_bytes
    assert b'"credential"' not in normalized.canonical_bytes


@pytest.mark.parametrize(
    (
        "model",
        "configured_url",
        "effective_url",
        "provider",
        "requested",
        "effective",
        "thinking",
        "system_blocks",
        "tool_choice",
    ),
    [
        (
            "claude-opus-4-6",
            "https://anthropic.example",
            "https://anthropic.example",
            "anthropic",
            "",
            "",
            "disabled",
            "native_system_blocks",
            "required_named_tool",
        ),
        (
            "deepseek-v4-pro",
            "https://api.deepseek.com/v1",
            "https://api.deepseek.com",
            "openai_compatible",
            "xhigh",
            "max",
            "enabled",
            "merged_into_user_prompt",
            "omitted",
        ),
        (
            "minimax-text-01",
            "https://provider.example",
            "https://provider.example/v1",
            "openai_compatible",
            "",
            "",
            "disabled",
            "merged_into_user_prompt",
            "required_named_function",
        ),
        (
            "minimax-text-01",
            "http://127.0.0.2",
            "http://127.0.0.2/v1",
            "openai_compatible",
            "",
            "",
            "disabled",
            "merged_into_user_prompt",
            "required_named_function",
        ),
    ],
)
def test_independent_schema_accepts_each_frozen_provider_family(
    model: str,
    configured_url: str,
    effective_url: str,
    provider: str,
    requested: str,
    effective: str,
    thinking: str,
    system_blocks: str,
    tool_choice: str,
) -> None:
    policy = _provider_policy()
    _set_policy_family(
        policy,
        model=model,
        configured_url=configured_url,
        effective_url=effective_url,
        provider=provider,
        requested_reasoning=requested,
        effective_reasoning=effective,
        thinking_mode=thinking,
        system_blocks=system_blocks,
        tool_choice=tool_choice,
    )
    assert _normalize_declared_provider_policy(policy).canonical_bytes.endswith(b"\n")


@pytest.mark.parametrize(
    "configured_url",
    [
        "HTTP://127.0.0.1",
        "http://127.0.00.1",
        "http://2130706433",
        "http://0x7f000001",
        "http://192.0.2.1",
        "https://User@provider.example",
        "https://provider.example?query=1",
        "https://provider.example#fragment",
        "https://provider.example/%2e",
        "https://provider.example/a//b",
        "https://provider.example/a/../b",
        "https://provider.example/v1/",
    ],
)
def test_independent_schema_rejects_noncanonical_or_unsafe_provider_url(
    configured_url: str,
) -> None:
    policy = _provider_policy()
    policy["client"]["configured_base_url"] = configured_url
    _fixed_error(lambda: _normalize_declared_provider_policy(policy))


def test_archived_policy_schema_does_not_call_live_producer_or_runtime_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_provider_policy as producer
    from scion.proposal.llm import study_policy as runtime

    calls = 0

    def bomb(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError

    monkeypatch.setattr(producer, "_provider_payload_bytes", bomb)
    monkeypatch.setattr(runtime, "_validate_frozen_study_provider_policy_shape", bomb)
    normalized = _normalize_study_manifest_provider_policy(_manifest())
    assert normalized.base_manifest.problem_id == "cvrp"
    assert calls == 0


def test_returns_only_the_fixed_v2_validation_result() -> None:
    assert _JOIN_LIMITATIONS == _EXPECTED_JOIN_LIMITATIONS
    assert _config_and_requested_provider_policy_join_result() == {
        "schema_version": _JOIN_VERSION,
        "status": _STATUS,
        "validated_scope": _SCOPE,
        "blocks_checked": 5,
        "arms_checked": 10,
        "limitations": list(_EXPECTED_JOIN_LIMITATIONS),
    }
    assert len(_JOIN_LIMITATIONS) == 25
    assert "PROVIDER_REQUEST_POLICY_UNVERIFIED" not in _JOIN_LIMITATIONS


def test_v1_and_v2_schema_entrypoints_remain_disjoint() -> None:
    v1 = _v1_manifest()
    assert _normalize_study_manifest(v1).problem_id == "cvrp"
    assert _config_subset_join_result()["status"] == "CONFIG_SUBSET_JOINED"
    _fixed_error(lambda: _normalize_study_manifest_provider_policy(v1))
    with pytest.raises(_StudyManifestSchemaError):
        _normalize_study_manifest(_manifest())


@pytest.mark.parametrize(
    "mutation",
    [
        "top_missing",
        "top_extra",
        "version",
        "scope",
        "policy_in_arm",
        "block_semantics",
    ],
)
def test_rejects_v2_manifest_shape_and_inherited_v1_semantics(mutation: str) -> None:
    raw = _manifest()
    if mutation == "top_missing":
        del raw["declared_provider_policy"]
    elif mutation == "top_extra":
        raw["provider_policy_override"] = None
    elif mutation == "version":
        raw["schema_version"] += ".drift"
    elif mutation == "scope":
        raw["scope"] = "CONFIG_SUBSET_ONLY"
    elif mutation == "policy_in_arm":
        raw["blocks"][0]["arms"][0]["declared_provider_policy"] = _provider_policy()
    else:
        raw["blocks"][0]["arms"][0]["declared_controls"]["campaign"][
            "requested_rounds"
        ] = 4
    _fixed_error(lambda: _normalize_study_manifest_provider_policy(raw))


@pytest.mark.parametrize(
    "mutation",
    [
        "top_extra",
        "version",
        "scope",
        "limitations",
        "api_key",
        "model_provider",
        "effective_url",
        "reasoning",
        "thinking",
        "body",
        "policy_count",
        "policy_order",
        "tool",
        "timeout_bool",
        "timeout_zero",
        "provider",
        "ceiling",
    ],
)
def test_rejects_nonproducer_declared_provider_policy(mutation: str) -> None:
    policy = copy.deepcopy(_provider_policy())
    if mutation == "top_extra":
        policy["credential"] = "secret"
    elif mutation == "version":
        policy["schema_version"] += ".drift"
    elif mutation == "scope":
        policy["scope"] = "CONFIG_SUBSET_ONLY"
    elif mutation == "limitations":
        policy["limitations"].reverse()
    elif mutation == "api_key":
        policy["client"]["api_key"] = "secret"
    elif mutation == "model_provider":
        policy["client"]["provider_transport"] = "anthropic"
    elif mutation == "effective_url":
        policy["client"]["effective_sdk_base_url"] += "/v1"
    elif mutation == "reasoning":
        policy["client"]["effective_reasoning_effort"] = "high"
    elif mutation == "thinking":
        policy["client"]["thinking_mode"] = "enabled"
    elif mutation == "body":
        policy["client"]["request_body_policy"]["tool_choice"] = "omitted"
    elif mutation == "policy_count":
        policy["request_policies"].pop()
    elif mutation == "policy_order":
        policy["request_policies"].reverse()
    elif mutation == "tool":
        policy["request_policies"][0]["tool_name"] = "generate_patch"
    elif mutation == "timeout_bool":
        policy["request_policies"][0]["timeout_sec"] = True
    elif mutation == "timeout_zero":
        policy["request_policies"][0]["timeout_sec"] = 0.0
    elif mutation == "provider":
        policy["request_policies"][0]["provider"] = "anthropic"
    else:
        policy["request_policies"][0]["provider_transport_output_ceiling_tokens"] = (
            16_384
        )
    _fixed_error(lambda: _normalize_declared_provider_policy(policy))


def test_rejects_container_subclass_without_running_hooks() -> None:
    hooks = 0

    class HookedDict(dict[str, Any]):
        def __iter__(self) -> Any:
            nonlocal hooks
            hooks += 1
            raise AssertionError

    raw = _manifest()
    raw["declared_provider_policy"] = HookedDict(raw["declared_provider_policy"])
    _fixed_error(lambda: _normalize_study_manifest_provider_policy(raw))
    assert hooks == 0


def test_fixed_error_and_repr_do_not_expose_provider_sentinel() -> None:
    raw = _manifest()
    sentinel = "https://secret-provider.invalid"
    raw["declared_provider_policy"]["client"]["configured_base_url"] = sentinel
    with pytest.raises(_StudyManifestProviderPolicySchemaError) as raised:
        _normalize_study_manifest_provider_policy(raw)
    assert str(raised.value) == _ERROR
    assert sentinel not in str(raised.value)
    assert sentinel not in repr(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_schema_module_has_no_path_loader_scoring_or_public_surface() -> None:
    source = Path(schema_module.__file__).read_text(encoding="utf-8")
    forbidden = (
        "manifest_path",
        "_decode_study_root",
        "calculate_research_effectiveness",
        "compare_five_block_research_effectiveness",
        "_compare_decoded_blocks",
        "os.open",
        "Path(",
        "initial_screening_study_provider_policy",
        "proposal.llm.study_policy",
    )
    assert not any(token in source for token in forbidden)
    assert schema_module.__all__ == ()
