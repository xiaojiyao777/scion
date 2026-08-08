"""Tests for T16: LLMClient and MockLLMClient."""
from __future__ import annotations

import json
import inspect
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
import pytest

from scion.proposal.llm_client import (
    LLMClient,
    LLMAuthError,
    LLMBalanceError,
    LLMError,
    LLMFormatError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransportError,
    _parse_retry_after,
)
from scion.proposal.engine import CreativeLayer
from scion.proposal.mock_client import MockLLMClient
from scion.proposal.llm.cache import _kind_short
from scion.proposal.schemas import (
    HYPOTHESIS_TOOL,
    PATCH_TOOL,
)


# ---------------------------------------------------------------------------
# MockLLMClient tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("removed_kind", "removed_alias"),
    (
        ("hypothesis_target_intent", "hti"),
        ("tool_selection", "tsel"),
        ("llm_call", "call"),
    ),
)
def test_prompt_cache_removed_request_kinds_use_generic_shortening(
    removed_kind: str,
    removed_alias: str,
) -> None:
    assert _kind_short(removed_kind) != removed_alias


def test_prompt_cache_has_no_raw_or_fix_kind_aliases() -> None:
    source = inspect.getsource(_kind_short)
    assert '"llm_call":' not in source
    assert '"fix":' not in source

class TestMockLLMClient:
    def test_success_returns_hypothesis(self):
        client = MockLLMClient(mode="success")
        result = client.call_with_tool("test prompt", HYPOTHESIS_TOOL)
        assert "hypothesis_text" in result
        assert "change_locus" in result
        assert result["action"] in ("modify", "create_new", "remove")

    def test_success_returns_patch(self):
        client = MockLLMClient(mode="success")
        result = client.call_with_tool("test prompt", PATCH_TOOL)
        assert "file_path" in result
        assert "action" in result
        assert result["edit_intent"] == "exact_replace"
        assert "source_digest" not in result
        assert "old_string" in result
        assert "new_string" in result

    def test_success_picks_hypothesis_schema(self):
        client = MockLLMClient(mode="success")
        result = client.call_with_tool("prompt", HYPOTHESIS_TOOL)
        # Should return hypothesis (has hypothesis_text)
        assert "hypothesis_text" in result

    def test_success_picks_patch_schema(self):
        client = MockLLMClient(mode="success")
        result = client.call_with_tool("prompt", PATCH_TOOL)
        # Should return patch (has file_path, not hypothesis_text)
        assert "file_path" in result

    def test_format_error_mode(self):
        client = MockLLMClient(mode="format_error")
        with pytest.raises(LLMFormatError):
            client.call_with_tool("prompt", PATCH_TOOL)

    def test_timeout_mode(self):
        client = MockLLMClient(mode="timeout")
        with pytest.raises(LLMTimeoutError):
            client.call_with_tool("prompt", PATCH_TOOL)

    def test_custom_hypothesis_response(self):
        custom = {
            "hypothesis_text": "Custom hypothesis",
            "change_locus": "custom_op",
            "action": "create_new",
            "target_file": None,
            "predicted_direction": "improve",
            "target_weakness": "weakness",
            "expected_effect": "effect",
            "suggested_weight": 0.5,
        }
        client = MockLLMClient(mode="success", hypothesis_response=custom)
        result = client.call_with_tool("prompt", HYPOTHESIS_TOOL)
        assert result["hypothesis_text"] == "Custom hypothesis"
        assert result["change_locus"] == "custom_op"

    def test_call_count_increments(self):
        client = MockLLMClient(mode="success")
        assert client.call_count == 0
        client.call_with_tool("p", PATCH_TOOL)
        assert client.call_count == 1
        client.call_with_tool("p", PATCH_TOOL)
        assert client.call_count == 2

    def test_mode_sequence(self):
        client = MockLLMClient(mode_sequence=["success", "timeout", "success"])
        # First call: success
        result = client.call_with_tool("p", PATCH_TOOL)
        assert "file_path" in result
        # Second call: timeout
        with pytest.raises(LLMTimeoutError):
            client.call_with_tool("p", PATCH_TOOL)
        # Third call: success again
        result = client.call_with_tool("p", PATCH_TOOL)
        assert "file_path" in result


class TestLLMClientSingleAttempt:
    """Every public typed-tool call executes one transport call."""

    @pytest.mark.parametrize(
        ("raw_fault", "expected_type"),
        [
            (TimeoutError("read timed out"), LLMTimeoutError),
            (ConnectionError("connection reset"), LLMTransportError),
            (Exception("HTTP 429 rate_limit"), LLMRateLimitError),
            (Exception("HTTP 503 service unavailable"), LLMProviderError),
            (Exception("Error code: 401 - invalid api key"), LLMAuthError),
            (Exception("Error code: 403 - insufficient balance"), LLMBalanceError),
            (Exception("unclassified provider response"), LLMError),
        ],
    )
    def test_raw_tool_fault_is_classified_after_one_call_without_sleep(
        self,
        raw_fault,
        expected_type,
    ):
        client = LLMClient()
        tool = {"name": "unit_tool", "input_schema": {"required": []}}
        with patch.object(client, "_tool_call_once", side_effect=raw_fault) as call_once:
            with patch("scion.proposal.llm.client.time.sleep") as mock_sleep:
                with pytest.raises(expected_type):
                    client.call_with_tool("prompt", tool)
        call_once.assert_called_once()
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# _parse_retry_after helper
# ---------------------------------------------------------------------------

def test_parse_retry_after_no_response():
    exc = Exception("rate limit")
    assert _parse_retry_after(exc) == 60.0


def test_parse_retry_after_with_header():
    mock_exc = MagicMock()
    mock_exc.response.headers = {"Retry-After": "30"}
    assert _parse_retry_after(mock_exc) == 30.0


def test_provider_sdk_retries_cannot_be_reenabled_by_env(monkeypatch):
    monkeypatch.setenv("SCION_SDK_MAX_RETRIES", "1")
    client = LLMClient()
    fake_openai = MagicMock()
    with patch.dict("sys.modules", {"openai": fake_openai}):
        client._get_openai_client()
    assert fake_openai.OpenAI.call_args.kwargs["max_retries"] == 0
    assert not hasattr(client, "sdk_max_retries")


def test_llm_client_has_no_retry_constructor_controls() -> None:
    parameters = inspect.signature(LLMClient).parameters
    assert "max_retries" not in parameters
    assert "sdk_max_retries" not in parameters


def test_anthropic_client_receives_sdk_retry_limit():
    client = LLMClient()
    fake_anthropic = MagicMock()
    with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        client._get_anthropic_client()
    fake_anthropic.Anthropic.assert_called_once()
    assert fake_anthropic.Anthropic.call_args.kwargs["max_retries"] == 0


def test_openai_client_receives_sdk_retry_limit():
    client = LLMClient()
    fake_openai = MagicMock()
    with patch.dict("sys.modules", {"openai": fake_openai}):
        client._get_openai_client()
    fake_openai.OpenAI.assert_called_once()
    assert fake_openai.OpenAI.call_args.kwargs["max_retries"] == 0


def test_llm_client_close_releases_cached_provider_clients():
    client = LLMClient()
    openai_client = MagicMock()
    anthropic_client = MagicMock()
    client._openai_client = openai_client
    client._anthropic_client = anthropic_client

    client.close()
    client.close()

    openai_client.close.assert_called_once()
    anthropic_client.close.assert_called_once()
    assert client._openai_client is None
    assert client._anthropic_client is None


def test_llm_client_strips_config_values(monkeypatch):
    monkeypatch.setenv("SCION_MODEL", " claude-sonnet-4-6 ")
    monkeypatch.setenv("SCION_API_KEY", " sk-test ")
    monkeypatch.setenv("SCION_BASE_URL", " https://aihubmix.com ")

    client = LLMClient()

    assert client.model == "claude-sonnet-4-6"
    assert client.api_key == "sk-test"
    assert client.base_url == "https://aihubmix.com"


def test_deepseek_v4pro_max_alias_sets_reasoning_effort(monkeypatch):
    monkeypatch.setenv("SCION_MODEL", "v4pro-max")
    monkeypatch.delenv("SCION_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("SCION_DEEPSEEK_REASONING_EFFORT", raising=False)

    client = LLMClient()

    assert client.model == "deepseek-v4-pro"
    assert client.reasoning_effort == "max"
    assert client._openai_reasoning_effort(client.model) == "max"
    assert client._openai_extra_body(client.model) == {"thinking": {"type": "enabled"}}


def test_deepseek_reasoning_effort_env_is_normalized(monkeypatch):
    monkeypatch.setenv("SCION_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("SCION_REASONING_EFFORT", "xhigh")

    client = LLMClient()

    assert client._openai_reasoning_effort(client.model) == "max"


def test_gpt_codex_reasoning_effort_env_is_forwarded(monkeypatch):
    monkeypatch.setenv("SCION_MODEL", "gpt-5.5")
    monkeypatch.setenv("SCION_REASONING_EFFORT", "xhigh")

    client = LLMClient()

    assert client._openai_reasoning_effort(client.model) == "xhigh"
    assert client._openai_extra_body(client.model) == {}


def test_gpt_codex_reasoning_effort_rejects_unknown_values(monkeypatch):
    monkeypatch.setenv("SCION_MODEL", "gpt-5.3-codex")
    monkeypatch.setenv("SCION_REASONING_EFFORT", "max")

    client = LLMClient()

    assert client._openai_reasoning_effort(client.model) == ""


def test_deepseek_openai_base_url_does_not_append_v1(monkeypatch):
    monkeypatch.setenv("SCION_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("SCION_BASE_URL", "https://api.deepseek.com")
    client = LLMClient()
    fake_openai = MagicMock()

    with patch.dict("sys.modules", {"openai": fake_openai}):
        client._get_openai_client()

    assert fake_openai.OpenAI.call_args.kwargs["base_url"] == "https://api.deepseek.com"


def test_terra_uses_explicit_scion_local_proxy_configuration(monkeypatch):
    monkeypatch.setenv("SCION_MODEL", "gpt-5.6-terra")
    monkeypatch.setenv("SCION_API_KEY", "pwd")
    monkeypatch.setenv("SCION_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-should-not-be-used")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "wrong-token")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://wrong.example")

    tool = {"name": "generate_patch", "input_schema": {"required": ["file_path"]}}
    tool_call = SimpleNamespace(
        function=SimpleNamespace(arguments=json.dumps({"file_path": "x.py"}))
    )
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2),
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(tool_calls=[tool_call]),
            )
        ],
    )
    provider_client = MagicMock()
    provider_client.chat.completions.create.return_value = response
    fake_openai = MagicMock()
    fake_openai.OpenAI.return_value = provider_client

    with patch.dict("sys.modules", {"openai": fake_openai}):
        client = LLMClient(timeout_sec=60)
        result = client.call_with_tool("prompt", tool)

    assert result == {"file_path": "x.py"}
    assert client.model == "gpt-5.6-terra"
    fake_openai.OpenAI.assert_called_once_with(
        api_key="pwd",
        base_url="http://127.0.0.1:8080/v1",
        max_retries=0,
    )
    request = provider_client.chat.completions.create.call_args.kwargs
    assert request["model"] == "gpt-5.6-terra"
    assert client.get_last_usage_metadata()["model"] == "gpt-5.6-terra"


def test_deepseek_chat_kwargs_include_thinking_and_max_effort(monkeypatch):
    monkeypatch.setenv("SCION_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("SCION_REASONING_EFFORT", "max")
    client = LLMClient()

    kwargs = client._openai_chat_kwargs(
        model=client.model,
        messages=[{"role": "user", "content": "hi"}],
        timeout_sec=10,
    )

    assert kwargs["reasoning_effort"] == "max"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}


def test_deepseek_tool_call_kwargs_omit_named_tool_choice(monkeypatch):
    monkeypatch.setenv("SCION_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("SCION_REASONING_EFFORT", "max")
    client = LLMClient()

    kwargs = client._openai_chat_kwargs(
        model=client.model,
        messages=[{"role": "user", "content": "hi"}],
        timeout_sec=10,
        tools=[{"type": "function", "function": {"name": "x", "parameters": {}}}],
        tool_choice={"type": "function", "function": {"name": "x"}},
    )

    assert "tool_choice" not in kwargs
    assert kwargs["reasoning_effort"] == "max"


def test_gpt_codex_chat_kwargs_include_prompt_cache_key_without_retention() -> None:
    client = LLMClient(model="gpt-5.5")
    tool = {
        "type": "function",
        "function": {
            "name": "generate_patch",
            "parameters": {"type": "object", "required": ["file_path"]},
        },
    }

    kwargs = client._openai_chat_kwargs(
        model=client.model,
        messages=[{"role": "user", "content": "branch=session user prompt"}],
        timeout_sec=10,
        tools=[tool],
        request_kind="code",
        system_blocks=[
            {
                "type": "text",
                "text": "stable code-generation system context",
                "cache_control": {"type": "ephemeral"},
            }
        ],
    )

    assert kwargs["prompt_cache_key"].startswith("scion:v3:gpt:code:")
    assert "prompt_cache_retention" not in kwargs


def test_prompt_cache_key_omitted_for_deepseek_chat_kwargs() -> None:
    client = LLMClient(model="deepseek-v4-pro")

    kwargs = client._openai_chat_kwargs(
        model=client.model,
        messages=[{"role": "user", "content": "hi"}],
        timeout_sec=10,
        request_kind="code",
        system_blocks=[
            {
                "type": "text",
                "text": "stable system context",
                "cache_control": {"type": "ephemeral"},
            }
        ],
    )

    assert "prompt_cache_key" not in kwargs
    assert "prompt_cache_retention" not in kwargs


def test_prompt_cache_key_omitted_for_anthropic_tool_call() -> None:
    client = LLMClient(model="claude-test", timeout_sec=60)
    tool = {"name": "generate_patch", "input_schema": {"required": ["file_path"]}}
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "generate_patch"
    tool_block.input = {"file_path": "x.py"}
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_block]
    response.usage = None
    fake_anthropic_client = MagicMock()
    fake_anthropic_client.messages.create.return_value = response

    with patch.object(client, "_get_anthropic_client", return_value=fake_anthropic_client):
        client.call_with_tool(
            "prompt",
            tool,
            model="claude-test",
            system_blocks=[
                {
                    "type": "text",
                    "text": "stable system context",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        )

    kwargs = fake_anthropic_client.messages.create.call_args.kwargs
    assert "prompt_cache_key" not in kwargs
    assert "prompt_cache_retention" not in kwargs


def test_prompt_cache_key_ignores_user_prompt_branch_and_session() -> None:
    client = LLMClient(model="gpt-5.5")
    system_blocks = [
        {
            "type": "text",
            "text": "stable planner context",
            "cache_control": {"type": "ephemeral"},
        }
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "plan_proposal_tool_call",
                "parameters": {"type": "object", "required": ["tool_name"]},
            },
        }
    ]

    first = client._openai_chat_kwargs(
        model=client.model,
        messages=[
            {"role": "user", "content": "branch_id=a session_id=a choose tool"}
        ],
        timeout_sec=10,
        tools=tools,
        request_kind="code",
        system_blocks=system_blocks,
    )["prompt_cache_key"]
    second = client._openai_chat_kwargs(
        model=client.model,
        messages=[
            {
                "role": "user",
                "content": "branch_id=b session_id=b different hypothesis prompt",
            }
        ],
        timeout_sec=10,
        tools=tools,
        request_kind="code",
        system_blocks=system_blocks,
    )["prompt_cache_key"]

    assert first == second


def test_prompt_cache_key_changes_when_cacheable_system_or_tool_schema_changes() -> None:
    client = LLMClient(model="gpt-5.5")
    base_system = [
        {
            "type": "text",
            "text": "stable system context",
            "cache_control": {"type": "ephemeral"},
        }
    ]
    changed_system = [
        {
            "type": "text",
            "text": "changed stable system context",
            "cache_control": {"type": "ephemeral"},
        }
    ]
    base_tool = [
        {
            "type": "function",
            "function": {
                "name": "generate_patch",
                "parameters": {"type": "object", "required": ["file_path"]},
            },
        }
    ]
    changed_tool = [
        {
            "type": "function",
            "function": {
                "name": "generate_patch",
                "parameters": {
                    "type": "object",
                    "required": ["file_path", "action"],
                },
            },
        }
    ]

    base_key = client._openai_chat_kwargs(
        model=client.model,
        messages=[{"role": "user", "content": "same prompt"}],
        timeout_sec=10,
        tools=base_tool,
        request_kind="code",
        system_blocks=base_system,
    )["prompt_cache_key"]
    system_key = client._openai_chat_kwargs(
        model=client.model,
        messages=[{"role": "user", "content": "same prompt"}],
        timeout_sec=10,
        tools=base_tool,
        request_kind="code",
        system_blocks=changed_system,
    )["prompt_cache_key"]
    tool_key = client._openai_chat_kwargs(
        model=client.model,
        messages=[{"role": "user", "content": "same prompt"}],
        timeout_sec=10,
        tools=changed_tool,
        request_kind="code",
        system_blocks=base_system,
    )["prompt_cache_key"]

    assert system_key != base_key
    assert tool_key != base_key


def test_tool_call_hard_timeout_interrupts_blocking_provider_call() -> None:
    client = LLMClient(timeout_sec=0.05)

    def _slow_tool_call(*args, **kwargs):
        time.sleep(1.0)
        return {"result": "late"}

    client._tool_call_once = MagicMock(side_effect=_slow_tool_call)  # type: ignore[method-assign]

    with pytest.raises(LLMTimeoutError):
        client.call_with_tool(
            "prompt",
            {"name": "x", "input_schema": {"required": ["result"]}},
        )

    assert client._tool_call_once.call_count == 1


def test_tool_call_masks_connection_error_at_hard_timeout_as_timeout() -> None:
    client = LLMClient(timeout_sec=0.05)

    def _masked_timeout(*args, **kwargs):
        try:
            time.sleep(1.0)
        except LLMTimeoutError as exc:
            raise RuntimeError("Connection error.") from exc
        return {"result": "late"}

    client._tool_call_once = MagicMock(side_effect=_masked_timeout)  # type: ignore[method-assign]

    with pytest.raises(LLMTimeoutError) as exc_info:
        client.call_with_tool(
            "prompt",
            {"name": "x", "input_schema": {"required": ["result"]}},
        )

    assert "hard timeout" in str(exc_info.value)
    assert client._tool_call_once.call_count == 1


def test_openai_cache_usage_reads_deepseek_cache_fields() -> None:
    usage = SimpleNamespace(prompt_cache_hit_tokens=25, prompt_cache_miss_tokens=75)

    assert LLMClient._openai_cache_usage(usage) == (25, 75)


def test_openai_cache_usage_reads_codex_proxy_nested_cache_fields() -> None:
    usage = SimpleNamespace(
        prompt_tokens=120,
        prompt_tokens_details=SimpleNamespace(cached_tokens=80),
    )

    assert LLMClient._openai_cache_usage(usage) == (80, 40)


def test_openai_cache_usage_reads_dict_nested_cache_fields() -> None:
    usage = {
        "prompt_tokens": 90,
        "prompt_tokens_details": {"cached_tokens": 30},
    }

    assert LLMClient._openai_cache_usage(usage) == (30, 60)


def test_anthropic_tool_call_records_last_usage_metadata() -> None:
    client = LLMClient(timeout_sec=60)
    tool = {"name": "generate_patch", "input_schema": {"required": ["file_path"]}}
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "generate_patch"
    tool_block.input = {"file_path": "policies/baseline_algorithm.py"}
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_block]
    response.usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=20,
        cache_creation_input_tokens=70,
        cache_read_input_tokens=30,
    )
    fake_anthropic_client = MagicMock()
    fake_anthropic_client.messages.create.return_value = response

    with patch.object(client, "_get_anthropic_client", return_value=fake_anthropic_client):
        client.call_with_tool("prompt", tool, model="claude-test")

    usage = client.get_last_usage_metadata()
    assert usage["provider"] == "anthropic"
    assert usage["model"] == "claude-test"
    assert usage["request_kind"] == "code"
    assert usage["cache_mode"] == "explicit_cache_control"
    assert usage["cache_accounting_mode"] == "anthropic_explicit_cache_tokens"
    assert usage["input_tokens"] == 100
    assert usage["prompt_tokens_total"] == 200
    assert usage["output_tokens"] == 20
    assert usage["cache_creation_input_tokens"] == 70
    assert usage["cache_read_input_tokens"] == 30
    assert usage["cache_miss_input_tokens"] == 100


def test_openai_tool_call_records_prompt_cache_usage_metadata() -> None:
    client = LLMClient(model="gpt-test", timeout_sec=60)
    tool = {"name": "generate_patch", "input_schema": {"required": ["file_path"]}}
    tool_call = SimpleNamespace(
        function=SimpleNamespace(arguments=json.dumps({"file_path": "x.py"}))
    )
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=12,
            prompt_cache_hit_tokens=80,
            prompt_cache_miss_tokens=40,
        ),
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(tool_calls=[tool_call]),
            )
        ],
    )
    fake_openai_client = MagicMock()
    fake_openai_client.chat.completions.create.return_value = response

    with patch.object(client, "_get_openai_client", return_value=fake_openai_client):
        client.call_with_tool("prompt", tool, model="gpt-test")

    usage = client.get_last_usage_metadata()
    assert usage["provider"] == "openai_compatible"
    assert usage["cache_mode"] == "prompt_cache_key_observed"
    assert usage["cache_accounting_mode"] == "provider_prompt_tokens_include_cache_read"
    assert usage["input_tokens"] == 120
    assert usage["prompt_tokens_total"] == 120
    assert usage["output_tokens"] == 12
    assert usage["cache_read_input_tokens"] == 80
    assert usage["cache_miss_input_tokens"] == 40
    assert usage["cache_creation_input_tokens"] == 0
    assert usage["prompt_cache_hit"] is True
    assert usage["prompt_cache_miss"] is True
    assert usage["prompt_cache_hit_tokens"] == 80
    assert usage["prompt_cache_miss_tokens"] == 40
    assert usage["prompt_cache_key"].startswith("scion:v3:gpt:code:")
    assert usage["prompt_cache_key_digest"] == usage["prompt_cache_key"].rsplit(":", 1)[-1]


def test_openai_provider_managed_output_omits_max_completion_tokens() -> None:
    client = LLMClient(
        model="gpt-5.6-sol",
        timeout_sec=60,
    )
    tool = {"name": "generate_patch", "input_schema": {"required": ["file_path"]}}
    tool_call = SimpleNamespace(
        function=SimpleNamespace(arguments=json.dumps({"file_path": "x.py"}))
    )
    response = SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(tool_calls=[tool_call]),
            )
        ],
    )
    fake_openai_client = MagicMock()
    fake_openai_client.chat.completions.create.return_value = response

    with patch.object(client, "_get_openai_client", return_value=fake_openai_client):
        result = client.call_with_tool(
            "prompt",
            tool,
            model="gpt-5.6-sol",
            request_kind="code",
        )

    assert result == {"file_path": "x.py"}
    request = fake_openai_client.chat.completions.create.call_args.kwargs
    assert "max_completion_tokens" not in request
    assert "max_tokens" not in request


def test_openai_default_output_policy_is_provider_managed_without_cap() -> None:
    client = LLMClient(model="gpt-5.6-sol")

    policy = client.resolve_request_policy(
        model="gpt-5.6-sol",
        request_kind="code",
    )

    assert policy["output_token_policy"] == "provider_managed"
    assert policy["output_token_parameter"] == "omitted"
    assert policy["provider_transport_output_ceiling_tokens"] is None
    assert "max_tokens" not in policy
    assert "truncation_retries" not in policy


def test_anthropic_transport_keeps_provider_native_required_max_tokens() -> None:
    client = LLMClient(model="claude-test")
    tool = {"name": "generate_patch", "input_schema": {"required": []}}
    block = SimpleNamespace(
        type="tool_use",
        name="generate_patch",
        input={"file_path": "x.py"},
    )
    response = SimpleNamespace(
        stop_reason="tool_use",
        content=[block],
        usage=None,
    )
    fake_anthropic_client = MagicMock()
    fake_anthropic_client.messages.create.return_value = response

    with patch.object(
        client,
        "_get_anthropic_client",
        return_value=fake_anthropic_client,
    ):
        result = client._tool_call_once_anthropic(
            "prompt",
            tool,
            "claude-test",
            None,
            60.0,
        )

    assert result == {"file_path": "x.py"}
    request = fake_anthropic_client.messages.create.call_args.kwargs
    assert request["max_tokens"] == 16384
    policy = client.resolve_request_policy(model="claude-test", request_kind="code")
    assert policy["output_token_policy"] == "provider_native_required"
    assert policy["output_token_parameter"] == "max_tokens"
    assert policy["provider_transport_output_ceiling_tokens"] == 16384
    assert "truncation_retries" not in policy


def test_openai_length_finish_with_tool_payload_is_a_real_response() -> None:
    client = LLMClient(model="gpt-5.6-sol")
    tool = {"name": "generate_patch", "input_schema": {"required": ["file_path"]}}
    tool_call = SimpleNamespace(
        function=SimpleNamespace(arguments=json.dumps({"file_path": "x.py"}))
    )
    response = SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                finish_reason="length",
                message=SimpleNamespace(tool_calls=[tool_call]),
            )
        ],
    )
    fake_openai_client = MagicMock()
    fake_openai_client.chat.completions.create.return_value = response

    with patch.object(client, "_get_openai_client", return_value=fake_openai_client):
        result = client.call_with_tool("prompt", tool, request_kind="code")

    assert result == {"file_path": "x.py"}
    assert fake_openai_client.chat.completions.create.call_count == 1


def test_openai_length_finish_invalid_tool_payload_is_format_failure() -> None:
    client = LLMClient(model="gpt-5.6-sol")
    tool = {"name": "generate_patch", "input_schema": {"required": ["file_path"]}}
    tool_call = SimpleNamespace(
        function=SimpleNamespace(arguments='{"file_path":')
    )
    response = SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                finish_reason="length",
                message=SimpleNamespace(tool_calls=[tool_call]),
            )
        ],
    )
    fake_openai_client = MagicMock()
    fake_openai_client.chat.completions.create.return_value = response

    with patch.object(client, "_get_openai_client", return_value=fake_openai_client):
        with pytest.raises(LLMFormatError) as caught:
            client.call_with_tool("prompt", tool, request_kind="code")

    assert "invalid JSON arguments" in str(caught.value)
    assert fake_openai_client.chat.completions.create.call_count == 1


def test_openai_tool_call_records_codex_proxy_usage_metadata() -> None:
    client = LLMClient(model="gpt-5.5", timeout_sec=60)
    tool = {"name": "generate_patch", "input_schema": {"required": ["file_path"]}}
    tool_call = SimpleNamespace(
        function=SimpleNamespace(arguments=json.dumps({"file_path": "x.py"}))
    )
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=44,
            prompt_tokens_details=SimpleNamespace(cached_tokens=80),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=32),
        ),
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(tool_calls=[tool_call]),
            )
        ],
    )
    fake_openai_client = MagicMock()
    fake_openai_client.chat.completions.create.return_value = response

    with patch.object(client, "_get_openai_client", return_value=fake_openai_client):
        client.call_with_tool("prompt", tool, model="gpt-5.5")

    usage = client.get_last_usage_metadata()
    assert usage["cache_read_input_tokens"] == 80
    assert usage["cache_miss_input_tokens"] == 40
    assert usage["prompt_tokens_total"] == 120
    assert usage["prompt_cache_miss_tokens"] == 40
    assert usage["reasoning_output_tokens"] == 32


def test_code_tool_policy_contains_only_transport_and_output_facts(monkeypatch):
    monkeypatch.delenv("SCION_LLM_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("SCION_LLM_CODE_TIMEOUT_SEC", raising=False)

    client = LLMClient(timeout_sec=60)
    policy = client.resolve_request_policy(
        tool={"name": "generate_patch", "input_schema": {"required": []}},
    )

    assert policy["request_kind"] == "code"
    assert policy["timeout_sec"] == 180.0
    assert policy["provider"] == "anthropic"
    assert policy["output_token_policy"] == "provider_native_required"
    assert not any("retri" in key for key in policy)


def test_code_tool_policy_ignores_removed_retry_env(monkeypatch):
    monkeypatch.delenv("SCION_LLM_TIMEOUT_SEC", raising=False)
    monkeypatch.setenv("SCION_LLM_CODE_TIMEOUT_SEC", "240")
    monkeypatch.setenv("SCION_LLM_CODE_MAX_RETRIES", "1")
    monkeypatch.setenv("SCION_LLM_TRANSIENT_PROVIDER_MAX_RETRIES", "9")

    client = LLMClient(timeout_sec=60)
    policy = client.resolve_request_policy(request_kind="code")

    assert policy["timeout_sec"] == 240.0
    assert not any("retri" in key for key in policy)


def test_code_tool_timeout_is_typed_and_does_not_duplicate_prompt():
    client = LLMClient(timeout_sec=60)
    tool = {"name": "generate_patch", "input_schema": {"required": []}}
    fake_anthropic_client = MagicMock()
    fake_anthropic_client.messages.create.side_effect = LLMTimeoutError("slow")

    with patch.object(client, "_get_anthropic_client", return_value=fake_anthropic_client):
        with patch("scion.proposal.llm.client.time.sleep") as mock_sleep:
            with pytest.raises(LLMTimeoutError):
                client.call_with_tool("prompt", tool)

    assert fake_anthropic_client.messages.create.call_count == 1
    assert fake_anthropic_client.messages.create.call_args.kwargs["timeout"] == 180.0
    mock_sleep.assert_not_called()


def test_code_tool_provider_error_is_typed_after_one_call_without_sleep():
    client = LLMClient(timeout_sec=60)
    tool = {
        "name": "generate_patch",
        "input_schema": {"required": ["file_path", "action", "code_content"]},
    }
    provider_error = Exception(
        "Error code: 500 - {'error': {'type': 'Aihubmix_api_error', "
        "'message': 'new request failed: parse \" https://aws-example\": first "
        "path segment in URL cannot contain colon'}}"
    )
    fake_anthropic_client = MagicMock()
    fake_anthropic_client.messages.create.side_effect = provider_error

    with patch.object(client, "_get_anthropic_client", return_value=fake_anthropic_client):
        with patch("scion.proposal.llm.client.time.sleep") as mock_sleep:
            with pytest.raises(LLMProviderError):
                client.call_with_tool("prompt", tool)

    assert fake_anthropic_client.messages.create.call_count == 1
    mock_sleep.assert_not_called()


def test_code_tool_502_html_is_provider_fault_after_one_call():
    client = LLMClient(timeout_sec=60)
    tool = {
        "name": "generate_patch",
        "input_schema": {"required": ["file_path", "action", "code_content"]},
    }
    gateway_error = Exception(
        "HTTP 502 Bad Gateway\n<html><title>502 Bad Gateway</title>"
        "<body>nginx upstream temporarily unavailable</body></html>"
    )
    fake_anthropic_client = MagicMock()
    fake_anthropic_client.messages.create.side_effect = gateway_error

    with patch.object(client, "_get_anthropic_client", return_value=fake_anthropic_client):
        with patch("scion.proposal.llm.client.time.sleep") as mock_sleep:
            with pytest.raises(LLMProviderError):
                client.call_with_tool("prompt", tool)

    assert fake_anthropic_client.messages.create.call_count == 1
    mock_sleep.assert_not_called()


def test_403_insufficient_balance_classifies_before_transient_provider() -> None:
    provider_error = Exception(
        "Error code: 403 - {'error': {'type': 'Aihubmix_api_error', "
        "'message': 'Your account balance is insufficient. Please recharge "
        "your account.'}}"
    )

    with pytest.raises(LLMBalanceError) as exc_info:
        LLMClient._raise_classified(provider_error)

    assert "balance exhausted" in str(exc_info.value)


def test_no_available_accounts_is_typed_provider_error() -> None:
    exc = Exception(
        "codex-proxy returned 503 service error: no_available_accounts"
    )

    with pytest.raises(LLMProviderError):
        LLMClient._raise_classified(exc)


def test_ordinary_403_is_typed_auth_error() -> None:
    with pytest.raises(LLMAuthError):
        LLMClient._raise_classified(Exception("Error code: 403 - forbidden"))


def test_connection_failure_is_typed_transport_error() -> None:
    with pytest.raises(LLMTransportError):
        LLMClient._raise_classified(ConnectionError("connection reset"))


def test_direct_trace_records_request_policy_without_retry_fields(tmp_path):
    from scion.proposal.engine.trace import _TraceWriter

    writer = _TraceWriter(str(tmp_path))
    path = writer.write_start(
        request_kind="code",
        model="claude-test",
        tool={"name": "generate_patch", "input_schema": {"type": "object"}},
        prompt="generate one patch",
        system_blocks=[{"type": "text", "text": "system"}],
        context={"branch_id": "branch-policy"},
        request_policy={
            "request_kind": "code",
            "timeout_sec": 180.0,
            "provider": "anthropic",
            "output_token_policy": "provider_native_required",
        },
    )
    writer.write_finish(path, ok=True, response={"file_path": "x.py"})

    payload = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert payload["request_kind"] == "code"
    assert payload["request_policy"]["timeout_sec"] == 180.0
    assert payload["request_policy"]["provider"] == "anthropic"
    assert not any("retri" in key for key in payload["request_policy"])
    assert payload["response"] == {"file_path": "x.py"}
