from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.main import get_command
from typer.testing import CliRunner

import scion.proposal.engine.provider_call as provider_call_module
from scion.cli.app import app
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.resource_envelope import (
    ProviderCallBudget,
    ProviderCallCapExhausted,
    ResourceEnvelope,
    normalize_resource_envelope,
    write_resource_envelope,
)
from scion.proposal.engine import CreativeLayer
from scion.proposal.engine.provider_call import (
    PromptTurnSnapshot,
    ProviderCaller,
    ProviderResponseSizeExceeded,
)
from scion.proposal.llm.errors import (
    LLMAuthError,
    LLMBalanceError,
    LLMError,
    LLMFormatError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransportError,
)
from scion.proposal.llm_client import LLMClient
from scion.tests.unit.core.proposal_pipeline_test_support import _pipeline


class _SequenceClient:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []
        self.policy_calls = 0
        self.reset_calls = 0

    def resolve_request_policy(self, **_kwargs) -> dict[str, object]:
        self.policy_calls += 1
        return {"sdk_retries": 0}

    def reset_call_observations(self) -> None:
        self.reset_calls += 1

    def call_with_tool(
        self,
        prompt,
        tool,
        model,
        *,
        system_blocks,
        request_kind,
    ):
        self.calls.append(
            {
                "prompt": prompt,
                "tool": json.loads(json.dumps(tool)),
                "model": model,
                "system_blocks": json.loads(json.dumps(system_blocks)),
                "request_kind": request_kind,
            }
        )
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _snapshot() -> PromptTurnSnapshot:
    return PromptTurnSnapshot(
        render_kind="hypothesis",
        system_blocks=({"type": "text", "text": "frozen system"},),
        user_prompt="frozen prompt",
        provider_tool={"name": "generate", "input_schema": {"type": "object"}},
        structured_context_json=json.dumps({"branch_id": "branch-retry"}),
    )


def _call(
    tmp_path: Path,
    client: _SequenceClient,
    *,
    budget: ProviderCallBudget | None = None,
    retries: int = 1,
) -> dict[str, object]:
    caller = ProviderCaller(
        client,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
        provider_call_budget=budget,
        provider_transient_retries=retries,
    )
    return caller.call(
        request_kind="hypothesis",
        tool=dict(_snapshot().provider_tool),
        snapshot=_snapshot(),
    )


def _traces(tmp_path: Path) -> list[dict[str, object]]:
    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (tmp_path / "traces").glob("*.json")
    ]
    return sorted(payloads, key=lambda payload: payload["attempt_index"])


@pytest.fixture(autouse=True)
def _skip_real_redispatch_backoff(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []
    monkeypatch.setattr(
        provider_call_module,
        "_sleep",
        lambda seconds: delays.append(float(seconds)),
    )
    return delays


@pytest.mark.parametrize(
    "error",
    [
        LLMTimeoutError("timed out"),
        LLMTransportError("connection reset"),
        LLMProviderError("typed provider failure"),
    ],
)
def test_one_explicit_retry_for_each_eligible_typed_failure(
    tmp_path: Path,
    error: Exception,
) -> None:
    client = _SequenceClient([error, {"ok": True}])
    budget = ProviderCallBudget(2)

    assert _call(tmp_path, client, budget=budget) == {"ok": True}

    assert len(client.calls) == 2
    assert client.calls[0] == client.calls[1]
    assert client.policy_calls == 1
    assert budget.used == 2
    traces = _traces(tmp_path)
    assert [trace["ok"] for trace in traces] == [False, True]
    assert [trace["attempt_index"] for trace in traces] == [0, 1]
    assert all("retryable" not in trace for trace in traces)
    assert all("retry_planned" not in trace for trace in traces)
    assert all("retry_after_sec" not in trace for trace in traces)


@pytest.mark.parametrize(
    "error",
    [
        LLMFormatError("invalid JSON"),
        LLMAuthError("unauthorized"),
        LLMBalanceError("no credits"),
        LLMRateLimitError("rate limited", retry_after=60.0),
        LLMError("generic LLM failure"),
        RuntimeError("generic runtime failure"),
    ],
)
def test_ineligible_failures_never_retry(
    tmp_path: Path,
    error: Exception,
) -> None:
    client = _SequenceClient([error, {"would": "hide an invalid retry"}])

    with pytest.raises(type(error)) as raised:
        _call(tmp_path, client)

    assert raised.value is error
    assert len(client.calls) == 1
    trace = _traces(tmp_path)[0]
    assert trace["attempt_index"] == 0
    assert "retryable" not in trace
    assert "retry_planned" not in trace
    assert "retry_after_sec" not in trace


def test_keyboard_interrupt_never_retries(tmp_path: Path) -> None:
    error = KeyboardInterrupt("operator stop")
    client = _SequenceClient([error, {"would": "hide an invalid retry"}])

    with pytest.raises(KeyboardInterrupt) as raised:
        _call(tmp_path, client)

    assert raised.value is error
    assert len(client.calls) == 1
    trace = _traces(tmp_path)[0]
    assert trace["error"] == "provider_call_interrupted"
    assert trace["attempt_index"] == 0


def test_response_bound_failure_never_retries(tmp_path: Path) -> None:
    client = _SequenceClient([{"oversized": "x" * 100}, {"ok": True}])
    caller = ProviderCaller(
        client,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
        provider_transient_retries=1,
    )

    with pytest.raises(ProviderResponseSizeExceeded):
        caller.call(
            request_kind="hypothesis",
            tool=dict(_snapshot().provider_tool),
            snapshot=_snapshot(),
            max_response_bytes=10,
        )

    assert len(client.calls) == 1
    assert _traces(tmp_path)[0]["attempt_index"] == 0


def test_second_dispatch_is_blocked_when_its_independent_budget_consume_fails(
    tmp_path: Path,
) -> None:
    client = _SequenceClient([LLMTimeoutError("timed out"), {"ok": True}])
    budget = ProviderCallBudget(1)

    with pytest.raises(ProviderCallCapExhausted):
        _call(tmp_path, client, budget=budget)

    assert budget.used == 1
    assert len(client.calls) == 1
    traces = _traces(tmp_path)
    assert len(traces) == 1
    assert traces[0]["attempt_index"] == 0


def test_third_dispatch_is_blocked_without_trace_when_cap_is_two(
    tmp_path: Path,
) -> None:
    client = _SequenceClient(
        [
            LLMProviderError("overloaded once"),
            LLMTransportError("gateway still unavailable"),
            {"would": "exceed the cap"},
        ]
    )
    budget = ProviderCallBudget(2)

    with pytest.raises(ProviderCallCapExhausted):
        _call(tmp_path, client, budget=budget, retries=2)

    assert budget.used == 2
    assert len(client.calls) == 2
    traces = _traces(tmp_path)
    assert [trace["attempt_index"] for trace in traces] == [0, 1]
    assert [trace["ok"] for trace in traces] == [False, False]


def test_second_transient_failure_is_terminal_after_one_retry(tmp_path: Path) -> None:
    first = LLMTransportError("connection reset")
    second = LLMTimeoutError("timed out again")
    client = _SequenceClient([first, second, {"would": "be third dispatch"}])

    with pytest.raises(LLMTimeoutError) as raised:
        _call(tmp_path, client)

    assert raised.value is second
    assert len(client.calls) == 2
    traces = _traces(tmp_path)
    assert [trace["attempt_index"] for trace in traces] == [0, 1]


def test_two_bounded_redispatches_use_deterministic_short_backoff(
    tmp_path: Path,
    _skip_real_redispatch_backoff: list[float],
) -> None:
    client = _SequenceClient(
        [
            LLMProviderError("overloaded once"),
            LLMTransportError("gateway still unavailable"),
            {"ok": True},
        ]
    )
    budget = ProviderCallBudget(3)

    assert _call(tmp_path, client, budget=budget, retries=2) == {"ok": True}

    assert len(client.calls) == 3
    assert client.calls[0] == client.calls[1] == client.calls[2]
    assert budget.used == 3
    assert _skip_real_redispatch_backoff == [5.0, 20.0]
    traces = _traces(tmp_path)
    assert [trace["ok"] for trace in traces] == [False, False, True]
    assert [trace["attempt_index"] for trace in traces] == [0, 1, 2]


def test_signal_during_backoff_prevents_budget_charge_dispatch_and_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _SequenceClient(
        [LLMProviderError("overloaded"), {"would": "run after signal"}]
    )
    budget = ProviderCallBudget(2)
    delays: list[float] = []

    def interrupt(seconds: float) -> None:
        delays.append(seconds)
        raise KeyboardInterrupt("operator signal")

    monkeypatch.setattr(provider_call_module, "_sleep", interrupt)

    with pytest.raises(KeyboardInterrupt, match="operator signal"):
        _call(tmp_path, client, budget=budget, retries=2)

    assert delays == [5.0]
    assert len(client.calls) == 1
    assert budget.used == 1
    traces = _traces(tmp_path)
    assert len(traces) == 1
    assert traces[0]["attempt_index"] == 0
    assert traces[0]["ok"] is False


@pytest.mark.parametrize("value", [True, -1, 3, 1.5, "1", None])
def test_retry_configuration_accepts_only_integer_zero_to_two(value) -> None:
    with pytest.raises((TypeError, ValueError)):
        ProviderCaller(
            _SequenceClient([]),
            "test-model",
            trace_dir=None,
            provider_transient_retries=value,  # type: ignore[arg-type]
        )
    with pytest.raises((TypeError, ValueError)):
        normalize_resource_envelope({"provider_transient_retries": value})


def test_retry_configuration_is_explicit_and_defaults_off() -> None:
    assert ResourceEnvelope().to_primitive() == {}
    assert ResourceEnvelope(provider_transient_retries=1).to_primitive() == {
        "provider_transient_retries": 1
    }
    assert ResourceEnvelope(provider_transient_retries=2).to_primitive() == {
        "provider_transient_retries": 2
    }

    run_command = get_command(app).commands["run"]
    option = next(
        parameter
        for parameter in run_command.params
        if parameter.name == "provider_transient_retries"
    )
    assert option.opts == ["--provider-transient-retries"]
    assert option.default == 0
    assert option.type.min == 0
    assert option.type.max == 2
    runner = CliRunner()
    invalid = runner.invoke(
        app,
        [
            "run",
            "--problem",
            "not-used.yaml",
            "--provider-transient-retries",
            "3",
        ],
    )
    assert invalid.exit_code == 2


def test_retry_configuration_is_written_in_the_ordinary_resource_artifact(
    tmp_path: Path,
) -> None:
    path = write_resource_envelope(
        str(tmp_path),
        ResourceEnvelope(
            provider_call_cap=2,
            outer_hardwall_sec=60,
            provider_transient_retries=2,
        ),
    )

    assert path is not None
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "outer_hardwall_sec": 60,
        "provider_call_cap": 2,
        "provider_transient_retries": 2,
    }


def test_each_dispatch_gets_a_fresh_copy_of_the_frozen_tool_and_system(
    tmp_path: Path,
) -> None:
    class _MutatingClient(_SequenceClient):
        def call_with_tool(self, prompt, tool, model, *, system_blocks, request_kind):
            result = super().call_with_tool(
                prompt,
                tool,
                model,
                system_blocks=system_blocks,
                request_kind=request_kind,
            )
            tool["mutated"] = True
            system_blocks.append({"text": "mutated"})
            return result

    class _MutatingThenTimeout(_MutatingClient):
        def call_with_tool(self, prompt, tool, model, *, system_blocks, request_kind):
            self.calls.append(
                {
                    "prompt": prompt,
                    "tool": json.loads(json.dumps(tool)),
                    "model": model,
                    "system_blocks": json.loads(json.dumps(system_blocks)),
                    "request_kind": request_kind,
                }
            )
            outcome = self._outcomes.pop(0)
            tool["mutated"] = True
            system_blocks.append({"text": "mutated"})
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

    client = _MutatingThenTimeout(
        [LLMTimeoutError("first timeout"), {"ok": True}]
    )

    assert _call(tmp_path, client) == {"ok": True}
    assert client.calls[0] == client.calls[1]


def test_default_zero_keeps_one_dispatch_and_one_budget_charge(
    tmp_path: Path,
) -> None:
    error = LLMTimeoutError("timed out")
    client = _SequenceClient([error, {"would": "be retried"}])
    budget = ProviderCallBudget(2)
    caller = ProviderCaller(
        client,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
        provider_call_budget=budget,
    )

    with pytest.raises(LLMTimeoutError) as raised:
        caller.call(
            request_kind="hypothesis",
            tool=dict(_snapshot().provider_tool),
            snapshot=_snapshot(),
        )

    assert raised.value is error
    assert len(client.calls) == 1
    assert budget.used == 1
    assert _traces(tmp_path)[0]["attempt_index"] == 0


@pytest.mark.parametrize(
    ("raw_error", "expected_type"),
    [
        (Exception("HTTP 409 conflict"), LLMProviderError),
        (Exception("status code: 500"), LLMProviderError),
        (Exception("HTTP 599 upstream failure"), LLMProviderError),
        (Exception("bad gateway without status"), LLMProviderError),
        (Exception("HTTP 404 bad gateway"), LLMError),
    ],
)
def test_transport_provider_classification_is_status_bounded(
    raw_error: Exception,
    expected_type: type[Exception],
) -> None:
    with pytest.raises(expected_type) as raised:
        LLMClient._raise_classified(raw_error)
    if expected_type is LLMError:
        assert type(raised.value) is LLMError


@pytest.mark.parametrize(
    ("module_name", "constructor_name", "getter_name"),
    [
        ("openai", "OpenAI", "_get_openai_client"),
        ("anthropic", "Anthropic", "_get_anthropic_client"),
    ],
)
def test_provider_sdk_retries_remain_zero(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    constructor_name: str,
    getter_name: str,
) -> None:
    captured: dict[str, object] = {}
    sentinel = SimpleNamespace()

    def construct(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setitem(
        sys.modules,
        module_name,
        SimpleNamespace(**{constructor_name: construct}),
    )
    client = LLMClient(
        api_key="test-key",
        base_url="https://provider.invalid",
        model=("gpt-5.6-sol" if module_name == "openai" else "claude-test"),
    )

    assert getattr(client, getter_name)() is sentinel
    assert captured["max_retries"] == 0


_VALID_HYPOTHESIS_RESPONSE = {
    "hypothesis_text": "Try one bounded local improvement move.",
    "change_locus": "local_search",
    "action": "create_new",
    "target_file": "operators/bounded.py",
    "predicted_direction": "improve",
    "target_weakness": "The control lacks this bounded move.",
    "expected_effect": "Improve screening without changing feasibility.",
}


def test_cross_layer_successful_retry_creates_no_failure_outcome_or_history(
    tmp_path: Path,
) -> None:
    client = _SequenceClient(
        [LLMTimeoutError("first dispatch timed out"), _VALID_HYPOTHESIS_RESPONSE]
    )
    budget = ProviderCallBudget(2)
    creative = CreativeLayer(
        client,
        trace_dir=str(tmp_path / "traces"),
        provider_call_budget=budget,
        provider_transient_retries=1,
    )
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)

    attempt = pipeline.generate_hypothesis(branch)

    assert attempt.proposal is not None
    assert attempt.execution_outcome is None
    assert pipeline.step_history == []
    assert pipeline._hypothesis_rejection_counts == {}
    assert len(client.calls) == 2
    assert budget.used == 2


def test_cross_layer_double_transient_failure_is_one_blocked_outcome(
    tmp_path: Path,
) -> None:
    client = _SequenceClient(
        [LLMTimeoutError("first timeout"), LLMTransportError("second transport")]
    )
    budget = ProviderCallBudget(2)
    creative = CreativeLayer(
        client,
        trace_dir=str(tmp_path / "traces"),
        provider_call_budget=budget,
        provider_transient_retries=1,
    )
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)

    attempt = pipeline.generate_hypothesis(branch)

    assert attempt.proposal is None
    assert attempt.execution_outcome is not None
    assert attempt.execution_outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert attempt.execution_outcome.reason_code == "PROVIDER_CALL_BLOCKED_INFRA"
    assert pipeline.step_history == []
    assert pipeline._hypothesis_rejection_counts == {}
    assert len(client.calls) == 2
    assert budget.used == 2


def test_cross_layer_cap_blocks_retry_as_resource_without_second_dispatch(
    tmp_path: Path,
) -> None:
    client = _SequenceClient(
        [LLMTimeoutError("first timeout"), _VALID_HYPOTHESIS_RESPONSE]
    )
    budget = ProviderCallBudget(1)
    creative = CreativeLayer(
        client,
        trace_dir=str(tmp_path / "traces"),
        provider_call_budget=budget,
        provider_transient_retries=1,
    )
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)

    attempt = pipeline.generate_hypothesis(branch)

    assert attempt.proposal is None
    assert attempt.execution_outcome is not None
    assert attempt.execution_outcome.outcome is ExecutionOutcome.RESOURCE_EXHAUSTED
    assert attempt.execution_outcome.reason_code == "PROVIDER_CALL_CAP_EXHAUSTED"
    assert len(client.calls) == 1
    assert budget.used == 1
