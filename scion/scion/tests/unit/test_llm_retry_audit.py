from __future__ import annotations

import json

from scion.proposal.engine import CreativeLayer
from scion.proposal.llm import LLMClient, LLMTimeoutError
import scion.proposal.llm.client as llm_client_module


_UNIT_TOOL = {
    "name": "unit_tool",
    "input_schema": {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "string"}},
    },
}


class _TimeoutThenSuccessClient(LLMClient):
    def __init__(self) -> None:
        super().__init__(
            model="test-model",
            api_key="test-key",
            base_url="http://127.0.0.1:1",
            timeout_sec=1.0,
            max_retries=1,
        )
        self.calls = 0

    def _tool_call_once(self, *args, **kwargs):
        del args, kwargs
        self.calls += 1
        if self.calls == 1:
            raise LLMTimeoutError("simulated timeout")
        return {"answer": "ok"}, False


def test_llm_tool_timeout_retry_event_is_structured_and_recovered(
    monkeypatch,
) -> None:
    monkeypatch.setattr(llm_client_module, "_BACKOFF_DELAYS", (0.0,))
    client = _TimeoutThenSuccessClient()

    result = client.call_with_tool(
        "prompt",
        _UNIT_TOOL,
        request_kind="tool_selection",
    )

    events = client.get_last_retry_events()
    assert result == {"answer": "ok"}
    assert client.calls == 2
    assert len(events) == 1
    event = events[0]
    assert event["phase"] == "tool_selection"
    assert event["tool_name"] == "unit_tool"
    assert event["call_name"] == "unit_tool"
    assert event["attempt"] == 1
    assert event["error_category"] == "llm_tool_timeout"
    assert event["will_retry"] is True
    assert event["recovered_success"] is True
    assert event["recovery_status"] == "recovered"
    assert event["timestamp"]
    assert event["finished_at"]


class _TraceRetryClient:
    model = "test-model"

    def call_with_tool(self, prompt, tool, model=None, system_blocks=None, **kwargs):
        del prompt, tool, model, system_blocks, kwargs
        return {"answer": "ok"}

    def resolve_request_policy(self, *, request_kind, tool):
        del request_kind, tool
        return {
            "max_retries": 1,
            "timeout_sec": 1.0,
            "transient_max_retries": 0,
        }

    def get_last_usage_metadata(self):
        return {"input_tokens": 10, "output_tokens": 2}

    def get_last_retry_events(self):
        return [
            {
                "schema_version": "llm-retry-event.v1",
                "phase": "tool_selection",
                "request_kind": "tool_selection",
                "tool_name": "unit_tool",
                "call_name": "unit_tool",
                "attempt": 1,
                "max_retries": 1,
                "max_attempts": 2,
                "timestamp": "2026-05-28T00:00:00Z",
                "error_category": "llm_tool_timeout",
                "will_retry": True,
                "recovered_success": True,
                "recovery_status": "recovered",
            }
        ]


def test_creative_trace_persists_llm_retry_events(tmp_path) -> None:
    trace_dir = tmp_path / "llm-traces"
    creative = CreativeLayer(_TraceRetryClient(), trace_dir=str(trace_dir))

    raw = creative._call_with_trace(
        request_kind="tool_selection",
        prompt="prompt",
        tool=_UNIT_TOOL,
        system_blocks=[],
        context={"branch_id": "branch-1"},
    )

    traces = list(trace_dir.glob("*.json"))
    assert raw == {"answer": "ok"}
    assert len(traces) == 1
    payload = json.loads(traces[0].read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["llm_retry_events"][0]["error_category"] == "llm_tool_timeout"
    assert payload["llm_retry_events"][0]["recovered_success"] is True
    assert payload["llm_retry_summary"] == {
        "event_count": 1,
        "recovered_event_count": 1,
        "error_categories": {"llm_tool_timeout": 1},
        "recovered_success": True,
    }
