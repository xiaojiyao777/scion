"""Tests for T16: LLMClient and MockLLMClient."""
from __future__ import annotations

import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
import pytest

from scion.proposal.llm_client import (
    LLMClient,
    LLM_TRANSIENT_API_ERROR_CATEGORY,
    LLMBalanceError,
    LLMFormatError,
    LLMRateLimitError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
    LLMTransientProviderError,
    _parse_retry_after,
    is_llm_transient_api_error,
)
from scion.proposal.engine import CreativeLayer
from scion.proposal.mock_client import MockLLMClient
from scion.proposal.schemas import (
    HYPOTHESIS_PROPOSAL_SCHEMA,
    PATCH_PROPOSAL_SCHEMA,
    TOOL_SELECTION_SCHEMA,
)


# ---------------------------------------------------------------------------
# MockLLMClient tests
# ---------------------------------------------------------------------------

class TestMockLLMClient:
    def test_success_returns_hypothesis(self):
        client = MockLLMClient(mode="success")
        result = client.call("test prompt", HYPOTHESIS_PROPOSAL_SCHEMA)
        assert "hypothesis_text" in result
        assert "change_locus" in result
        assert result["action"] in ("modify", "create_new", "remove")

    def test_success_returns_patch(self):
        client = MockLLMClient(mode="success")
        result = client.call("test prompt", PATCH_PROPOSAL_SCHEMA)
        assert "file_path" in result
        assert "action" in result
        assert result["edit_intent"] == "exact_replace"
        assert "source_digest" in result
        assert "old_string" in result
        assert "new_string" in result

    def test_success_picks_hypothesis_schema(self):
        client = MockLLMClient(mode="success")
        result = client.call("prompt", HYPOTHESIS_PROPOSAL_SCHEMA)
        # Should return hypothesis (has hypothesis_text)
        assert "hypothesis_text" in result

    def test_success_picks_patch_schema(self):
        client = MockLLMClient(mode="success")
        result = client.call("prompt", PATCH_PROPOSAL_SCHEMA)
        # Should return patch (has file_path, not hypothesis_text)
        assert "file_path" in result

    def test_format_error_mode(self):
        client = MockLLMClient(mode="format_error")
        with pytest.raises(LLMFormatError):
            client.call("prompt", PATCH_PROPOSAL_SCHEMA)

    def test_timeout_mode(self):
        client = MockLLMClient(mode="timeout")
        with pytest.raises(LLMTimeoutError):
            client.call("prompt", PATCH_PROPOSAL_SCHEMA)

    def test_exhausted_mode(self):
        client = MockLLMClient(mode="exhausted")
        with pytest.raises(LLMRetryExhaustedError):
            client.call("prompt", PATCH_PROPOSAL_SCHEMA)

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
        result = client.call("prompt", HYPOTHESIS_PROPOSAL_SCHEMA)
        assert result["hypothesis_text"] == "Custom hypothesis"
        assert result["change_locus"] == "custom_op"

    def test_call_count_increments(self):
        client = MockLLMClient(mode="success")
        assert client.call_count == 0
        client.call("p", PATCH_PROPOSAL_SCHEMA)
        assert client.call_count == 1
        client.call("p", PATCH_PROPOSAL_SCHEMA)
        assert client.call_count == 2

    def test_mode_sequence(self):
        client = MockLLMClient(mode_sequence=["success", "timeout", "success"])
        # First call: success
        result = client.call("p", PATCH_PROPOSAL_SCHEMA)
        assert "file_path" in result
        # Second call: timeout
        with pytest.raises(LLMTimeoutError):
            client.call("p", PATCH_PROPOSAL_SCHEMA)
        # Third call: success again
        result = client.call("p", PATCH_PROPOSAL_SCHEMA)
        assert "file_path" in result


# ---------------------------------------------------------------------------
# LLMClient._parse_and_validate tests
# ---------------------------------------------------------------------------

class TestLLMClientParse:
    """Test the JSON-extraction and validation logic without making real API calls."""

    def _client(self) -> LLMClient:
        return LLMClient()

    def test_plain_json(self):
        client = self._client()
        raw = json.dumps({"file_path": "x.py", "action": "modify", "code_content": "x=1"})
        result = client._parse_and_validate(raw, PATCH_PROPOSAL_SCHEMA)
        assert result["file_path"] == "x.py"

    def test_json_in_markdown_fence(self):
        client = self._client()
        raw = "```json\n{\"file_path\": \"x.py\", \"action\": \"modify\", \"code_content\": \"x=1\"}\n```"
        result = client._parse_and_validate(raw, PATCH_PROPOSAL_SCHEMA)
        assert result["file_path"] == "x.py"

    def test_json_in_plain_fence(self):
        client = self._client()
        raw = "```\n{\"file_path\": \"x.py\", \"action\": \"modify\", \"code_content\": \"x=1\"}\n```"
        result = client._parse_and_validate(raw, PATCH_PROPOSAL_SCHEMA)
        assert result["file_path"] == "x.py"

    def test_invalid_json_raises_format_error(self):
        client = self._client()
        with pytest.raises(LLMFormatError, match="not valid JSON"):
            client._parse_and_validate("not json at all", PATCH_PROPOSAL_SCHEMA)

    def test_array_json_raises_format_error(self):
        client = self._client()
        with pytest.raises(LLMFormatError, match="JSON object"):
            client._parse_and_validate("[1, 2, 3]", PATCH_PROPOSAL_SCHEMA)

    def test_missing_required_field_raises(self):
        client = self._client()
        raw = json.dumps({"file_path": "x.py"})  # missing action
        with pytest.raises(LLMFormatError, match="missing required"):
            client._parse_and_validate(raw, PATCH_PROPOSAL_SCHEMA)

    def test_all_required_fields_present(self):
        client = self._client()
        raw = json.dumps({
            "hypothesis_text": "h",
            "change_locus": "c",
            "action": "modify",
        })
        result = client._parse_and_validate(raw, HYPOTHESIS_PROPOSAL_SCHEMA)
        assert result["hypothesis_text"] == "h"


# ---------------------------------------------------------------------------
# LLMClient retry logic (mock _call_once)
# ---------------------------------------------------------------------------

class TestLLMClientRetry:
    """Test retry behaviour without any real API calls."""

    def _client(self, max_retries: int = 2) -> LLMClient:
        c = LLMClient(max_retries=max_retries)
        return c

    def test_success_first_try(self):
        client = self._client()
        good_response = json.dumps({"file_path": "x.py", "action": "modify", "code_content": "x=1"})
        with patch.object(client, "_call_once", return_value=good_response) as mock_call:
            result = client.call("prompt", PATCH_PROPOSAL_SCHEMA)
        assert result["file_path"] == "x.py"
        mock_call.assert_called_once()

    def test_timeout_retries_then_exhausted(self):
        client = self._client(max_retries=2)
        with patch.object(client, "_call_once", side_effect=LLMTimeoutError("timeout")):
            with patch("scion.proposal.llm_client.time.sleep"):  # don't actually sleep
                with pytest.raises(LLMRetryExhaustedError):
                    client.call("prompt", PATCH_PROPOSAL_SCHEMA)

    def test_timeout_then_success(self):
        client = self._client(max_retries=2)
        good = json.dumps({"file_path": "x.py", "action": "modify", "code_content": "x=1"})
        side_effects = [LLMTimeoutError("t"), good]
        with patch.object(client, "_call_once", side_effect=side_effects):
            with patch("scion.proposal.llm_client.time.sleep"):
                result = client.call("prompt", PATCH_PROPOSAL_SCHEMA)
        assert result["file_path"] == "x.py"

    def test_format_error_retries_and_appends_error(self):
        client = self._client(max_retries=2)
        good = json.dumps({"file_path": "x.py", "action": "modify", "code_content": "x=1"})

        call_prompts = []

        def mock_call(prompt, model, system_blocks=None):
            call_prompts.append(prompt)
            if len(call_prompts) == 1:
                return "not-json"  # will cause format error
            return good

        with patch.object(client, "_call_once", side_effect=mock_call):
            with patch("scion.proposal.llm_client.time.sleep"):
                result = client.call("original prompt", PATCH_PROPOSAL_SCHEMA)

        assert result["file_path"] == "x.py"
        assert len(call_prompts) == 2
        # Second call should include error context
        assert "Format error" in call_prompts[1] or "format issue" in call_prompts[1]

    def test_format_error_exhausted(self):
        client = self._client(max_retries=1)
        with patch.object(client, "_call_once", return_value="not-json"):
            with patch("scion.proposal.llm_client.time.sleep"):
                with pytest.raises(LLMRetryExhaustedError):
                    client.call("prompt", PATCH_PROPOSAL_SCHEMA)

    def test_rate_limit_does_not_consume_retry_budget(self):
        client = self._client(max_retries=1)
        good = json.dumps({"file_path": "x.py", "action": "modify", "code_content": "x=1"})
        # rate limit once, then success
        side_effects = [LLMRateLimitError("429", retry_after=0.001), good]
        with patch.object(client, "_call_once", side_effect=side_effects):
            with patch("scion.proposal.llm_client.time.sleep"):
                result = client.call("prompt", PATCH_PROPOSAL_SCHEMA)
        assert result["file_path"] == "x.py"

    def test_two_timeouts_then_exhausted_with_max_retries_1(self):
        client = self._client(max_retries=1)
        with patch.object(client, "_call_once", side_effect=LLMTimeoutError("t")):
            with patch("scion.proposal.llm_client.time.sleep"):
                with pytest.raises(LLMRetryExhaustedError):
                    client.call("prompt", PATCH_PROPOSAL_SCHEMA)


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


def test_provider_sdk_retries_are_disabled_by_default():
    client = LLMClient()
    assert client.sdk_max_retries == 0


def test_provider_sdk_retries_can_be_overridden_by_env(monkeypatch):
    monkeypatch.setenv("SCION_SDK_MAX_RETRIES", "1")
    client = LLMClient()
    assert client.sdk_max_retries == 1


def test_anthropic_client_receives_sdk_retry_limit():
    client = LLMClient(sdk_max_retries=0)
    fake_anthropic = MagicMock()
    with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        client._get_anthropic_client()
    fake_anthropic.Anthropic.assert_called_once()
    assert fake_anthropic.Anthropic.call_args.kwargs["max_retries"] == 0


def test_openai_client_receives_sdk_retry_limit():
    client = LLMClient(sdk_max_retries=0)
    fake_openai = MagicMock()
    with patch.dict("sys.modules", {"openai": fake_openai}):
        client._get_openai_client()
    fake_openai.OpenAI.assert_called_once()
    assert fake_openai.OpenAI.call_args.kwargs["max_retries"] == 0


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
    client = LLMClient(sdk_max_retries=0)
    fake_openai = MagicMock()

    with patch.dict("sys.modules", {"openai": fake_openai}):
        client._get_openai_client()

    assert fake_openai.OpenAI.call_args.kwargs["base_url"] == "https://api.deepseek.com"


def test_deepseek_chat_kwargs_include_thinking_and_max_effort(monkeypatch):
    monkeypatch.setenv("SCION_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("SCION_REASONING_EFFORT", "max")
    client = LLMClient()

    kwargs = client._openai_chat_kwargs(
        model=client.model,
        max_tokens=128,
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
        max_tokens=128,
        messages=[{"role": "user", "content": "hi"}],
        timeout_sec=10,
        tools=[{"type": "function", "function": {"name": "x", "parameters": {}}}],
        tool_choice={"type": "function", "function": {"name": "x"}},
    )

    assert "tool_choice" not in kwargs
    assert kwargs["reasoning_effort"] == "max"


def test_tool_selection_tool_call_defaults_missing_intent() -> None:
    client = LLMClient(max_retries=0)
    client._tool_call_once = MagicMock(  # type: ignore[method-assign]
        return_value=(
            {"tool_name": "context.read_problem", "args": {}},
            False,
        )
    )

    result = client.call_with_tool(
        "choose",
        {
            "name": "plan_proposal_tool_call",
            "input_schema": TOOL_SELECTION_SCHEMA,
        },
        request_kind="tool_selection",
    )

    assert result == {
        "intent": "call_tool",
        "tool_name": "context.read_problem",
        "args": {},
    }


def test_tool_selection_tool_call_normalizes_common_aliases() -> None:
    client = LLMClient(max_retries=0)
    client._tool_call_once = MagicMock(  # type: ignore[method-assign]
        return_value=(
            {"name": "context.read_problem", "input": {"detail": "compact"}},
            False,
        )
    )

    result = client.call_with_tool(
        "choose",
        {
            "name": "plan_proposal_tool_call",
            "input_schema": TOOL_SELECTION_SCHEMA,
        },
        request_kind="tool_selection",
    )

    assert result["intent"] == "call_tool"
    assert result["tool_name"] == "context.read_problem"
    assert result["args"] == {"detail": "compact"}
    assert "required" not in TOOL_SELECTION_SCHEMA


def test_tool_call_hard_timeout_interrupts_blocking_provider_call() -> None:
    client = LLMClient(timeout_sec=0.05, max_retries=0)

    def _slow_tool_call(*args, **kwargs):
        time.sleep(1.0)
        return {"result": "late"}, False

    client._tool_call_once = MagicMock(side_effect=_slow_tool_call)  # type: ignore[method-assign]

    with pytest.raises(LLMRetryExhaustedError) as exc_info:
        client.call_with_tool(
            "prompt",
            {"name": "x", "input_schema": {"required": ["result"]}},
        )

    assert isinstance(exc_info.value.last_error, LLMTimeoutError)


def test_tool_call_masks_connection_error_at_hard_timeout_as_timeout() -> None:
    client = LLMClient(timeout_sec=0.05, max_retries=0)

    def _masked_timeout(*args, **kwargs):
        try:
            time.sleep(1.0)
        except LLMTimeoutError as exc:
            raise RuntimeError("Connection error.") from exc
        return {"result": "late"}, False

    client._tool_call_once = MagicMock(side_effect=_masked_timeout)  # type: ignore[method-assign]

    with pytest.raises(LLMRetryExhaustedError) as exc_info:
        client.call_with_tool(
            "prompt",
            {"name": "x", "input_schema": {"required": ["result"]}},
        )

    assert isinstance(exc_info.value.last_error, LLMTimeoutError)
    assert "hard timeout" in str(exc_info.value.last_error)


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
    client = LLMClient(timeout_sec=60, max_retries=0)
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
    client = LLMClient(model="gpt-test", timeout_sec=60, max_retries=0)
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
    assert usage["cache_mode"] == "automatic_prefix_cache_observed"
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


def test_openai_tool_call_records_codex_proxy_usage_metadata() -> None:
    client = LLMClient(model="gpt-5.5", timeout_sec=60, max_retries=0)
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


def test_code_tool_policy_defaults_to_long_timeout_without_internal_retry(monkeypatch):
    monkeypatch.delenv("SCION_LLM_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("SCION_LLM_MAX_RETRIES", raising=False)
    monkeypatch.delenv("SCION_LLM_CODE_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("SCION_LLM_CODE_MAX_RETRIES", raising=False)

    client = LLMClient(timeout_sec=60, max_retries=2)
    policy = client.resolve_request_policy(
        tool={"name": "generate_patch", "input_schema": {"required": []}},
    )

    assert policy["request_kind"] == "code"
    assert policy["timeout_sec"] == 180.0
    assert policy["max_retries"] == 0


def test_code_tool_policy_respects_kind_specific_env(monkeypatch):
    monkeypatch.delenv("SCION_LLM_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("SCION_LLM_MAX_RETRIES", raising=False)
    monkeypatch.setenv("SCION_LLM_CODE_TIMEOUT_SEC", "240")
    monkeypatch.setenv("SCION_LLM_CODE_MAX_RETRIES", "1")

    client = LLMClient(timeout_sec=60, max_retries=2)
    policy = client.resolve_request_policy(request_kind="code")

    assert policy["timeout_sec"] == 240.0
    assert policy["max_retries"] == 1


def test_code_tool_timeout_does_not_duplicate_same_prompt_by_default(monkeypatch):
    monkeypatch.delenv("SCION_LLM_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("SCION_LLM_MAX_RETRIES", raising=False)
    monkeypatch.delenv("SCION_LLM_CODE_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("SCION_LLM_CODE_MAX_RETRIES", raising=False)

    client = LLMClient(timeout_sec=60, max_retries=2)
    tool = {"name": "generate_patch", "input_schema": {"required": []}}
    fake_anthropic_client = MagicMock()
    fake_anthropic_client.messages.create.side_effect = LLMTimeoutError("slow")

    with patch.object(client, "_get_anthropic_client", return_value=fake_anthropic_client):
        with patch("scion.proposal.llm_client.time.sleep") as mock_sleep:
            with pytest.raises(LLMRetryExhaustedError) as exc_info:
                client.call_with_tool("prompt", tool)

    assert "1 attempt(s)" in str(exc_info.value)
    assert fake_anthropic_client.messages.create.call_count == 1
    assert fake_anthropic_client.messages.create.call_args.kwargs["timeout"] == 180.0
    mock_sleep.assert_not_called()


def test_code_tool_retries_transient_provider_error_once(monkeypatch):
    monkeypatch.delenv("SCION_LLM_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("SCION_LLM_MAX_RETRIES", raising=False)
    monkeypatch.delenv("SCION_LLM_CODE_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("SCION_LLM_CODE_MAX_RETRIES", raising=False)
    monkeypatch.delenv("SCION_LLM_TRANSIENT_PROVIDER_MAX_RETRIES", raising=False)

    client = LLMClient(timeout_sec=60, max_retries=2)
    tool = {
        "name": "generate_patch",
        "input_schema": {"required": ["file_path", "action", "code_content"]},
    }
    provider_error = Exception(
        "Error code: 500 - {'error': {'type': 'Aihubmix_api_error', "
        "'message': 'new request failed: parse \" https://aws-example\": first "
        "path segment in URL cannot contain colon'}}"
    )
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "generate_patch"
    tool_block.input = {
        "file_path": "policies/baseline_algorithm.py",
        "action": "modify",
        "code_content": "def solve(instance, rng, time_limit_sec, context):\n    return []\n",
    }
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_block]
    response.usage = None
    fake_anthropic_client = MagicMock()
    fake_anthropic_client.messages.create.side_effect = [provider_error, response]

    with patch.object(client, "_get_anthropic_client", return_value=fake_anthropic_client):
        with patch("scion.proposal.llm_client.time.sleep") as mock_sleep:
            result = client.call_with_tool("prompt", tool)

    assert result["file_path"] == "policies/baseline_algorithm.py"
    assert fake_anthropic_client.messages.create.call_count == 2
    mock_sleep.assert_called_once_with(5.0)


def test_code_tool_exhausted_502_html_is_transient_api_failure(monkeypatch):
    monkeypatch.delenv("SCION_LLM_CODE_MAX_RETRIES", raising=False)
    monkeypatch.setenv("SCION_LLM_TRANSIENT_PROVIDER_MAX_RETRIES", "1")

    client = LLMClient(timeout_sec=60, max_retries=2)
    tool = {
        "name": "generate_patch",
        "input_schema": {"required": ["file_path", "action", "code_content"]},
    }
    gateway_error = Exception(
        "HTTP 502 Bad Gateway\n<html><title>502 Bad Gateway</title>"
        "<body>nginx upstream temporarily unavailable</body></html>"
    )
    fake_anthropic_client = MagicMock()
    fake_anthropic_client.messages.create.side_effect = [gateway_error, gateway_error]

    with patch.object(client, "_get_anthropic_client", return_value=fake_anthropic_client):
        with patch("scion.proposal.llm_client.time.sleep") as mock_sleep:
            with pytest.raises(LLMRetryExhaustedError) as exc_info:
                client.call_with_tool("prompt", tool)

    exc = exc_info.value
    assert fake_anthropic_client.messages.create.call_count == 2
    mock_sleep.assert_called_once_with(5.0)
    assert exc.failure_category == LLM_TRANSIENT_API_ERROR_CATEGORY
    assert isinstance(exc.last_error, LLMTransientProviderError)
    assert is_llm_transient_api_error(exc)


def test_403_insufficient_balance_classifies_before_transient_provider() -> None:
    provider_error = Exception(
        "Error code: 403 - {'error': {'type': 'Aihubmix_api_error', "
        "'message': 'Your account balance is insufficient. Please recharge "
        "your account.'}}"
    )

    with pytest.raises(LLMBalanceError) as exc_info:
        LLMClient._raise_classified(provider_error)

    assert "balance exhausted" in str(exc_info.value)


def test_no_available_accounts_is_transient_provider_error() -> None:
    exc = Exception(
        "codex-proxy returned 503 service error: no_available_accounts"
    )

    assert is_llm_transient_api_error(exc)


def test_creative_trace_records_llm_request_policy(tmp_path):
    class PolicyClient:
        def resolve_request_policy(self, *, request_kind=None, tool=None):
            return {
                "request_kind": request_kind,
                "timeout_sec": 180.0,
                "max_retries": 0,
                "sdk_max_retries": 0,
            }

        def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
            return {
                "file_path": "policies/baseline_algorithm.py",
                "action": "create",
                "code_content": "def solve(instance, rng, time_limit_sec, context):\n    return []\n",
            }

        def get_last_usage_metadata(self):
            return {
                "provider": "anthropic",
                "input_tokens": 11,
                "output_tokens": 7,
                "cache_creation_input_tokens": 5,
                "cache_read_input_tokens": 3,
            }

    creative = CreativeLayer(
        PolicyClient(),
        model="claude-test",
        trace_dir=str(tmp_path),
    )

    creative.generate_code({"change_locus": "solver_design"})

    traces = list(tmp_path.glob("*.json"))
    assert len(traces) == 1
    payload = json.loads(traces[0].read_text())
    assert payload["request_kind"] == "code"
    assert payload["request_policy"]["timeout_sec"] == 180.0
    assert payload["request_policy"]["max_retries"] == 0
    assert payload["llm_usage"]["cache_creation_input_tokens"] == 5
    assert payload["llm_usage"]["cache_read_input_tokens"] == 3
    assert payload["prompt_cache_audit"]["user_prompt_chars"] > 0
    assert payload["prompt_cache_audit"]["provider"] == "anthropic"
    assert payload["prompt_cache_audit"]["cache_mode"] == "explicit_cache_control"
    assert payload["prompt_cache_audit"]["cache_control_forwarded_to_provider"] is True
    assert payload["prompt_cache_audit"]["tool_schema_hash"]
    assert payload["prompt_cache_audit"]["system_blocks"]
    assert payload["prompt_cache_audit"]["cache_prefix_order"] == (
        "tools -> system -> messages"
    )


def test_creative_trace_marks_openai_cache_as_automatic_prefix(tmp_path):
    class PolicyClient:
        def resolve_request_policy(self, *, request_kind=None, tool=None):
            return {"request_kind": request_kind, "timeout_sec": 180.0, "max_retries": 0}

        def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
            return {
                "file_path": "policies/baseline_algorithm.py",
                "action": "create",
                "code_content": "def solve(instance, rng, time_limit_sec, context):\n    return []\n",
            }

        def get_last_usage_metadata(self):
            return {
                "provider": "openai_compatible",
                "cache_mode": "automatic_prefix_cache_observed",
                "cache_accounting_mode": "provider_prompt_tokens_include_cache_read",
                "input_tokens": 120,
                "prompt_tokens_total": 120,
                "output_tokens": 7,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 80,
                "cache_miss_input_tokens": 40,
            }

    creative = CreativeLayer(
        PolicyClient(),
        model="gpt-5.5",
        trace_dir=str(tmp_path),
    )

    creative.generate_code({"change_locus": "solver_design"})

    payload = json.loads(next(tmp_path.glob("*.json")).read_text())
    audit = payload["prompt_cache_audit"]
    assert audit["provider"] == "openai_compatible"
    assert audit["cache_mode"] == "automatic_prefix_cache_attempted"
    assert audit["cache_accounting_mode"] == "provider_prompt_tokens_include_cache_read"
    assert audit["cache_control_forwarded_to_provider"] is False
    assert all(
        block["cache_control_forwarded_to_provider"] is False
        for block in audit["system_blocks"]
    )
    assert "do not forward Anthropic cache_control" in audit["cache_strategy_note"]
