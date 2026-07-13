from __future__ import annotations

from scion.proposal.llm import LLMClient, LLMTimeoutError


_UNIT_TOOL = {
    "name": "unit_tool",
    "input_schema": {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "string"}},
    },
}


class _TimeoutClient(LLMClient):
    def __init__(self) -> None:
        super().__init__(
            model="test-model",
            api_key="test-key",
            base_url="http://127.0.0.1:1",
            timeout_sec=1.0,
        )
        self.calls = 0

    def _tool_call_once(self, *args, **kwargs):
        del args, kwargs
        self.calls += 1
        raise LLMTimeoutError("simulated timeout")


def test_llm_tool_timeout_is_typed_and_single_attempt() -> None:
    client = _TimeoutClient()

    try:
        client.call_with_tool(
            "prompt",
            _UNIT_TOOL,
            request_kind="code",
        )
    except LLMTimeoutError as exc:
        assert str(exc) == "simulated timeout"
    else:  # pragma: no cover - assertion branch
        raise AssertionError("typed timeout was not raised")

    assert client.calls == 1
    assert not hasattr(client, "get_last_retry_events")
