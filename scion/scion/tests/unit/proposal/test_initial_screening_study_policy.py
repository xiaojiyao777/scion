"""Focused tests for the private initial-screening provider policy."""

from __future__ import annotations

import json
import os
import sys
from types import MethodType, SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scion.core.resource_envelope import ProviderCallBudget
from scion.proposal.engine.provider_call import PromptTurnSnapshot, ProviderCaller
from scion.proposal.llm.client import LLMClient
from scion.proposal.llm.study_policy import (
    _canonical_base_url,
    _effective_sdk_base_url,
    _freeze_initial_screening_study_policy,
    _install_initial_screening_study_policy,
    _uninstall_initial_screening_study_policy,
)

_REQUEST_SPECS = (
    ("hypothesis", "generate_hypothesis"),
    ("hypothesis_research_turn", "hypothesis_research_turn"),
    ("code", "generate_patch"),
    ("code_research_turn", "code_research_turn"),
    ("code_research_finalize", "finalize_code_research"),
)


def _snapshot(
    tool: dict[str, Any],
    *,
    render_kind: str = "code",
    system_blocks: tuple[dict[str, object], ...] = (),
) -> PromptTurnSnapshot:
    return PromptTurnSnapshot(
        render_kind=render_kind,
        system_blocks=system_blocks,
        user_prompt="synthetic prompt",
        provider_tool=tool,
        structured_context_json="{}",
    )


def _openai_response(tool_name: str, value: dict[str, object]) -> object:
    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            name=tool_name,
            arguments=json.dumps(value),
        )
    )
    return SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(tool_calls=[tool_call]),
            )
        ],
    )


class _BombEnvironment:
    def __init__(self, forbidden: frozenset[str]) -> None:
        self._source = dict(os.environ)
        self._forbidden = forbidden

    def get(self, key: str, default: object = None) -> object:
        if key in self._forbidden:
            raise AssertionError(f"post-freeze environment read: {key}")
        return self._source.get(key, default)

    def __getitem__(self, key: str) -> str:
        if key in self._forbidden:
            raise AssertionError(f"post-freeze environment read: {key}")
        return self._source[key]

    def __contains__(self, key: object) -> bool:
        if type(key) is str and key in self._forbidden:
            raise AssertionError(f"post-freeze environment read: {key}")
        return self._source.__contains__(key)


def test_frozen_provider_entry_is_shared_by_caller_trace_and_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCION_LLM_CODE_TIMEOUT_SEC", "241")
    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret-never-projected",
        base_url="https://proxy.example",
        timeout_sec=60,
    )
    same_client, capsule = _freeze_initial_screening_study_policy(client)
    assert same_client is client
    assert "secret-never-projected" not in json.dumps(capsule.to_projection())
    _install_initial_screening_study_policy(client, capsule)
    monkeypatch.setenv("SCION_LLM_CODE_TIMEOUT_SEC", "999")

    tool = {"name": "generate_patch", "input_schema": {"required": []}}
    sdk_client = MagicMock()
    sdk_client.chat.completions.create.return_value = _openai_response(
        "generate_patch",
        {"file_path": "x.py"},
    )
    fake_openai = MagicMock()
    fake_openai.OpenAI.return_value = sdk_client

    caller = ProviderCaller(client, client.model, trace_dir=None)
    with patch.dict(sys.modules, {"openai": fake_openai}):
        result = caller.call(
            request_kind="code",
            tool=tool,
            snapshot=_snapshot(tool),
        )

    assert result == {"file_path": "x.py"}
    assert fake_openai.OpenAI.call_args.kwargs == {
        "api_key": "secret-never-projected",
        "base_url": "https://proxy.example/v1",
        "max_retries": 0,
    }
    assert sdk_client.chat.completions.create.call_args.kwargs["timeout"] == 241.0


def test_legacy_client_with_nonexact_storage_keeps_env_policy_and_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hooks: list[str] = []

    class BombStorage(dict[str, Any]):
        def __iter__(self):
            hooks.append("iter")
            return super().__iter__()

        def __contains__(self, key: object) -> bool:
            hooks.append("contains")
            return super().__contains__(key)

        def get(self, key: str, default: Any = None) -> Any:
            hooks.append("get")
            return super().get(key, default)

        def items(self):
            hooks.append("items")
            return super().items()

    monkeypatch.setenv("SCION_LLM_CODE_TIMEOUT_SEC", "242")
    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="legacy-secret",
        base_url="https://proxy.example",
        timeout_sec=60,
    )
    object.__setattr__(client, "__dict__", BombStorage(vars(client)))
    tool = {"name": "generate_patch", "input_schema": {"required": []}}
    sdk_client = MagicMock()
    sdk_client.chat.completions.create.return_value = _openai_response(
        "generate_patch",
        {"file_path": "legacy.py"},
    )
    fake_openai = MagicMock()
    fake_openai.OpenAI.return_value = sdk_client

    with patch.dict(sys.modules, {"openai": fake_openai}):
        caller = ProviderCaller(client, client.model, trace_dir=None)
        assert caller.call(
            request_kind="code",
            tool=tool,
            snapshot=_snapshot(tool),
        ) == {"file_path": "legacy.py"}
        assert client.call_with_tool(
            "legacy prompt",
            tool,
            request_kind="code",
        ) == {"file_path": "legacy.py"}

    assert hooks == []
    assert sdk_client.chat.completions.create.call_count == 2
    assert all(
        call.kwargs["timeout"] == 242.0
        for call in sdk_client.chat.completions.create.call_args_list
    )


def test_legacy_overrides_with_old_private_signatures_remain_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.proposal.engine import provider_call as provider_call_module

    observed_policies: list[str] = []

    def old_policy_helper(
        _client: Any,
        *,
        request_kind: str,
        tool: dict[str, Any],
        model: str,
    ) -> dict[str, Any]:
        observed_policies.append(request_kind)
        return {"timeout_sec": 180.0, "provider": "openai_compatible"}

    monkeypatch.setattr(
        provider_call_module,
        "_client_request_policy",
        old_policy_helper,
    )

    class LegacyCaller(ProviderCaller):
        def _call_provider(  # type: ignore[override]
            self,
            *,
            request_kind: str,
            prompt: str,
            tool: dict[str, Any],
            system_blocks: list[dict[str, Any]],
        ) -> dict[str, Any]:
            return {"request_kind": request_kind, "prompt": prompt}

    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="legacy-secret",
        base_url="https://proxy.example",
        timeout_sec=60,
    )
    tool = {"name": "generate_patch", "input_schema": {"required": []}}
    caller = LegacyCaller(client, client.model, trace_dir=None)

    assert caller.call(
        request_kind="code",
        tool=tool,
        snapshot=_snapshot(tool),
    ) == {"request_kind": "code", "prompt": "synthetic prompt"}
    assert observed_policies == ["code"]


def test_legacy_transport_instance_shadows_keep_old_signatures() -> None:
    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="legacy-secret",
        base_url="https://proxy.example",
        timeout_sec=60,
    )
    client_type = type(client)

    def old_chat_kwargs(
        self: Any,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout_sec: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return client_type._openai_chat_kwargs(
            self,
            model=model,
            messages=messages,
            timeout_sec=timeout_sec,
            tools=tools,
            tool_choice=tool_choice,
        )

    def old_reasoning(self: Any, model: str) -> str:
        return client_type._openai_reasoning_effort(self, model)

    def old_extra_body(self: Any, model: str) -> dict[str, Any]:
        return client_type._openai_extra_body(self, model)

    object.__setattr__(
        client,
        "_openai_chat_kwargs",
        MethodType(old_chat_kwargs, client),
    )
    object.__setattr__(
        client,
        "_openai_reasoning_effort",
        MethodType(old_reasoning, client),
    )
    object.__setattr__(
        client,
        "_openai_extra_body",
        MethodType(old_extra_body, client),
    )
    sdk_client = MagicMock()
    sdk_client.chat.completions.create.return_value = _openai_response(
        "generate_patch",
        {"file_path": "legacy.py"},
    )
    fake_openai = MagicMock()
    fake_openai.OpenAI.return_value = sdk_client
    tool = {"name": "generate_patch", "input_schema": {"required": []}}

    with patch.dict(sys.modules, {"openai": fake_openai}):
        assert client.call_with_tool(
            "legacy prompt",
            tool,
            request_kind="code",
        ) == {"file_path": "legacy.py"}


def test_capsule_has_exact_five_kind_tool_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for request_kind, _tool_name in _REQUEST_SPECS:
        monkeypatch.delenv(
            f"SCION_LLM_{request_kind.upper()}_TIMEOUT_SEC",
            raising=False,
        )
    client = LLMClient(
        model="claude-opus-4-6",
        api_key="secret",
        base_url="https://proxy.example",
        timeout_sec=61,
    )

    _, capsule = _freeze_initial_screening_study_policy(client)

    assert (
        tuple(
            (entry.request_kind, entry.tool_name) for entry in capsule.request_policies
        )
        == _REQUEST_SPECS
    )
    assert tuple(entry.timeout_sec for entry in capsule.request_policies) == (
        61.0,
        61.0,
        180.0,
        180.0,
        180.0,
    )


def test_post_freeze_policy_resolution_never_rereads_configuration_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.proposal.llm import client as client_module
    from scion.proposal.llm import config, study_policy

    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://proxy.example",
        timeout_sec=62,
    )
    _, capsule = _freeze_initial_screening_study_policy(client)
    _install_initial_screening_study_policy(client, capsule)
    forbidden = frozenset(
        {
            "SCION_MODEL",
            "ANTHROPIC_MODEL",
            "SCION_BASE_URL",
            "ANTHROPIC_BASE_URL",
            "SCION_REASONING_EFFORT",
            "SCION_DEEPSEEK_REASONING_EFFORT",
            "SCION_LLM_TIMEOUT_SEC",
            "SCION_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            *(f"SCION_LLM_{kind.upper()}_TIMEOUT_SEC" for kind, _ in _REQUEST_SPECS),
        }
    )
    bomb_os = SimpleNamespace(environ=_BombEnvironment(forbidden))
    monkeypatch.setattr(study_policy, "os", bomb_os)
    monkeypatch.setattr(client_module, "os", bomb_os)
    monkeypatch.setattr(config, "os", bomb_os)

    for request_kind, tool_name in _REQUEST_SPECS:
        projection = client.resolve_request_policy(
            request_kind=request_kind,
            tool={"name": tool_name},
            model=client.model,
        )
        assert projection["request_kind"] == request_kind


@pytest.mark.parametrize(
    ("caller_model", "request_kind", "tool_name"),
    (
        ("gpt-5.6-terra", "code", "generate_patch"),
        ("gpt-5.6-sol", "unknown", "generate_patch"),
        ("gpt-5.6-sol", "code", "generate_hypothesis"),
    ),
)
def test_installed_client_rejects_unknown_or_mismatch_before_budget(
    caller_model: str,
    request_kind: str,
    tool_name: str,
) -> None:
    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://proxy.example",
        timeout_sec=60,
    )
    _, capsule = _freeze_initial_screening_study_policy(client)
    _install_initial_screening_study_policy(client, capsule)
    budget = ProviderCallBudget(1)
    caller = ProviderCaller(
        client,
        caller_model,
        trace_dir=None,
        provider_call_budget=budget,
    )
    tool = {"name": tool_name, "input_schema": {"required": []}}

    with pytest.raises(ValueError):
        caller.call(
            request_kind=request_kind,
            tool=tool,
            snapshot=_snapshot(tool),
        )

    assert client.get_last_usage_metadata() is None
    assert client.get_last_response_diagnostics() is None
    assert budget.used == 0


def test_callable_shadow_rejects_before_budget_or_observation_reset() -> None:
    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://proxy.example",
        timeout_sec=60,
    )
    _, capsule = _freeze_initial_screening_study_policy(client)
    _install_initial_screening_study_policy(client, capsule)
    client._last_usage_metadata = {"sentinel": 1}
    client._last_response_diagnostics = {"sentinel": 2}
    client.call_with_tool = lambda *_args, **_kwargs: {"unexpected": True}
    budget = ProviderCallBudget(1)
    caller = ProviderCaller(
        client,
        client.model,
        trace_dir=None,
        provider_call_budget=budget,
    )
    tool = {"name": "generate_patch", "input_schema": {"required": []}}

    with pytest.raises(TypeError):
        caller.call(request_kind="code", tool=tool, snapshot=_snapshot(tool))

    assert client._last_usage_metadata == {"sentinel": 1}
    assert client._last_response_diagnostics == {"sentinel": 2}
    assert budget.used == 0


def test_model_override_rejects_before_observation_reset() -> None:
    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://proxy.example",
        timeout_sec=60,
    )
    _, capsule = _freeze_initial_screening_study_policy(client)
    _install_initial_screening_study_policy(client, capsule)
    client._last_usage_metadata = {"sentinel": 1}
    client._last_response_diagnostics = {"sentinel": 2}
    tool = {"name": "generate_patch", "input_schema": {"required": []}}

    with pytest.raises(ValueError):
        client.call_with_tool(
            "prompt",
            tool,
            model="gpt-5.6-terra",
            request_kind="code",
            _initial_screening_study_policy_entry=capsule.request_policies[2],
        )

    assert client._last_usage_metadata == {"sentinel": 1}
    assert client._last_response_diagnostics == {"sentinel": 2}


def test_install_interrupt_after_setattr_rolls_back_exact_capsule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.proposal.llm import study_policy

    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://proxy.example",
        timeout_sec=60,
    )
    _, capsule = _freeze_initial_screening_study_policy(client)

    def interrupt_after_setattr(_client: object, _capsule: object) -> None:
        object.__setattr__(
            _client,
            "__dict__",
            type("HiddenStorage", (dict,), {})(vars(_client)),
        )
        raise KeyboardInterrupt

    monkeypatch.setattr(
        study_policy,
        "_validate_frozen_llm_client_shape",
        interrupt_after_setattr,
    )

    with pytest.raises(KeyboardInterrupt):
        _install_initial_screening_study_policy(client, capsule)

    assert study_policy._CAPSULE_ATTRIBUTE not in vars(client)


def test_uninstall_removes_exact_capsule_despite_unrelated_client_drift() -> None:
    from scion.proposal.llm import study_policy

    client = LLMClient(
        model="gpt-5.6-sol",
        api_key="secret",
        base_url="https://proxy.example",
        timeout_sec=60,
    )
    _, capsule = _freeze_initial_screening_study_policy(client)
    _install_initial_screening_study_policy(client, capsule)
    sentinel = object()
    client._openai_client = sentinel
    client._last_usage_metadata = {"sentinel": 1}
    client.model = "drifted-model"

    _uninstall_initial_screening_study_policy(client, capsule)

    assert study_policy._CAPSULE_ATTRIBUTE not in vars(client)
    assert client._openai_client is sentinel
    assert client._last_usage_metadata == {"sentinel": 1}
    assert client.model == "drifted-model"


def test_anthropic_actual_kwargs_match_frozen_capsule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCION_LLM_HYPOTHESIS_TIMEOUT_SEC", "73")
    client = LLMClient(
        model="claude-opus-4-6",
        api_key="secret",
        base_url="https://anthropic-proxy.example",
        timeout_sec=60,
    )
    _, capsule = _freeze_initial_screening_study_policy(client)
    _install_initial_screening_study_policy(client, capsule)
    block = SimpleNamespace(
        type="tool_use",
        name="generate_hypothesis",
        input={"answer": "ok"},
    )
    sdk_client = MagicMock()
    sdk_client.messages.create.return_value = SimpleNamespace(
        stop_reason="tool_use",
        content=[block],
        usage=None,
    )
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = sdk_client
    tool = {"name": "generate_hypothesis", "input_schema": {"required": []}}
    caller = ProviderCaller(client, client.model, trace_dir=None)

    with patch.dict(sys.modules, {"anthropic": fake_anthropic}):
        assert caller.call(
            request_kind="hypothesis",
            tool=tool,
            snapshot=_snapshot(
                tool,
                render_kind="hypothesis",
                system_blocks=({"type": "text", "text": "system"},),
            ),
        ) == {"answer": "ok"}

    assert fake_anthropic.Anthropic.call_args.kwargs == {
        "api_key": "secret",
        "base_url": capsule.effective_sdk_base_url,
        "max_retries": 0,
    }
    kwargs = sdk_client.messages.create.call_args.kwargs
    assert kwargs["timeout"] == 73.0
    assert kwargs["max_tokens"] == 16384
    assert kwargs["tool_choice"] == {
        "type": "tool",
        "name": "generate_hypothesis",
    }
    assert kwargs["system"] == [{"type": "text", "text": "system"}]
    assert {"temperature", "top_p", "seed", "stream"}.isdisjoint(kwargs)


@pytest.mark.parametrize(
    (
        "model",
        "base_url",
        "requested_reasoning",
        "effective_base_url",
        "effective_reasoning",
        "has_tool_choice",
        "extra_body",
    ),
    (
        (
            "gpt-5.6-sol",
            "https://openai-proxy.example",
            "xhigh",
            "https://openai-proxy.example/v1",
            "xhigh",
            True,
            None,
        ),
        (
            "deepseek-v4-pro",
            "https://api.deepseek.com/v1",
            "xhigh",
            "https://api.deepseek.com",
            "max",
            False,
            {"thinking": {"type": "enabled"}},
        ),
    ),
)
def test_openai_family_actual_kwargs_match_frozen_capsule(
    model: str,
    base_url: str,
    requested_reasoning: str,
    effective_base_url: str,
    effective_reasoning: str,
    has_tool_choice: bool,
    extra_body: dict[str, object] | None,
) -> None:
    client = LLMClient(
        model=model,
        api_key="secret",
        base_url=base_url,
        timeout_sec=64,
    )
    client.reasoning_effort = requested_reasoning
    _, capsule = _freeze_initial_screening_study_policy(client)
    _install_initial_screening_study_policy(client, capsule)
    sdk_client = MagicMock()
    sdk_client.chat.completions.create.return_value = _openai_response(
        "generate_patch",
        {"file_path": "x.py"},
    )
    fake_openai = MagicMock()
    fake_openai.OpenAI.return_value = sdk_client
    tool = {"name": "generate_patch", "input_schema": {"required": []}}

    with patch.dict(sys.modules, {"openai": fake_openai}):
        assert ProviderCaller(client, client.model, trace_dir=None).call(
            request_kind="code",
            tool=tool,
            snapshot=_snapshot(tool),
        ) == {"file_path": "x.py"}

    assert capsule.effective_sdk_base_url == effective_base_url
    assert fake_openai.OpenAI.call_args.kwargs == {
        "api_key": "secret",
        "base_url": effective_base_url,
        "max_retries": 0,
    }
    kwargs = sdk_client.chat.completions.create.call_args.kwargs
    assert kwargs["timeout"] == 180.0
    assert kwargs["reasoning_effort"] == effective_reasoning
    assert ("tool_choice" in kwargs) is has_tool_choice
    if extra_body is None:
        assert "extra_body" not in kwargs
    else:
        assert kwargs["extra_body"] == extra_body
    assert {"temperature", "top_p", "seed", "stream"}.isdisjoint(kwargs)


@pytest.mark.parametrize(
    "value",
    (
        "https://EXAMPLE.com",
        "http://[::1]:",
        "https://example.com/",
        "https://user@example.com",
        "https://example.com?query=1",
        "https://example.com#fragment",
        "https://example.com/a//b",
        "https://example.com/%2e%2e",
        "https://[0:0:0:0:0:0:0:1]",
        "https://127.000.000.001",
        "https://2130706433",
        "https://0x7f000001",
        "https://0x7f.0.0.1",
    ),
)
def test_study_base_url_rejects_noncanonical_or_ambiguous_values(value: str) -> None:
    with pytest.raises(ValueError):
        _canonical_base_url(value)


@pytest.mark.parametrize(
    "value",
    (
        "http://127.0.0.1",
        "http://127.0.0.2",
        "http://[::1]",
        "http://localhost",
    ),
)
def test_canonical_loopback_urls_are_accepted(value: str) -> None:
    assert _canonical_base_url(value) == value


def test_deepseek_hostname_substring_uses_ordinary_openai_route() -> None:
    configured = _canonical_base_url("https://api.deepseek.com.evil.example")

    assert configured == "https://api.deepseek.com.evil.example"
    assert (
        _effective_sdk_base_url(
            configured,
            provider="openai_compatible",
        )
        == "https://api.deepseek.com.evil.example/v1"
    )
