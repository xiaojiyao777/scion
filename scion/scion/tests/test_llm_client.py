"""Tests for T16: LLMClient and MockLLMClient."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call
import pytest

from scion.proposal.llm_client import (
    LLMClient,
    LLMFormatError,
    LLMRateLimitError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
    _parse_retry_after,
)
from scion.proposal.engine import CreativeLayer
from scion.proposal.mock_client import MockLLMClient
from scion.proposal.schemas import HYPOTHESIS_PROPOSAL_SCHEMA, PATCH_PROPOSAL_SCHEMA


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
        assert "code_content" in result

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
        raw = json.dumps({"file_path": "x.py", "action": "modify"})  # missing code_content
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
                "action": "modify",
                "code_content": "def solve(instance, rng, time_limit_sec, context):\n    return []\n",
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
