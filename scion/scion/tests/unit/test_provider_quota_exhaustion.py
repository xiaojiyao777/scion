"""Explicit account quota is terminal; ordinary throttling remains transient."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from scion.core.campaign_loop import CampaignLoop
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import HypothesisProposal
from scion.core.resource_envelope import ProviderCallBudget
from scion.core.step_result import StepResult
from scion.proposal.engine import CreativeLayer
from scion.proposal.llm_client import (
    LLMAuthError,
    LLMBalanceError,
    LLMClient,
    LLMRateLimitError,
)
from scion.tests.unit.core.proposal_pipeline_test_support import _pipeline
from scion.tests.unit.test_provider_transient_retry import (
    _ClassifyingSequenceClient,
    _traces,
)


_R16_MESSAGE = (
    "All accounts exhausted (1 rate-limited). Codex API error (429): "
    "The usage limit has been reached"
)


def _fault(body, *, status=429, text="provider failure"):
    exc = Exception(text)
    exc.status_code = status
    exc.body = body
    exc.response = SimpleNamespace(headers={"Retry-After": "1200"})
    return exc


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize(
    "payload",
    [
        {"code": "insufficient_quota", "message": "quota exhausted"},
        {"type": "insufficient_quota", "message": "check billing"},
        {"code": "usage_limit_reached"},
        {"type": "usage_limit_reached"},
        {"code": "insufficient_quota", "message": "timeout retry cannot restore quota"},
        {"code": "rate_limit_exceeded", "message": _R16_MESSAGE},
        {"message": "The usage limit has been reached"},
        {"message": "The usage limit has been reached."},
    ],
)
def test_explicit_429_quota_is_terminal(payload, nested):
    raw = _fault({"error": payload} if nested else payload)
    with pytest.raises(LLMBalanceError) as raised:
        LLMClient._raise_classified(raw)
    assert raised.value.__cause__ is raw


@pytest.mark.parametrize(
    "body",
    [
        {"message": "Rate limit reached for tokens per minute"},
        {"message": "All accounts exhausted (1 rate-limited)"},
        {"message": "The usage limit has been reached for requests per minute"},
        {"message": "Not exhausted: The usage limit has been reached"},
        {"code": "rate_limit_exceeded"},
        {"code": "insufficient_quota_other"},
        {"metadata": {"code": "insufficient_quota"}},
        {"message": 123, "code": ["insufficient_quota"]},
        {"error": "insufficient_quota"},
        ["insufficient_quota"],
        {},
    ],
)
def test_ambiguous_or_malformed_quota_is_not_inferred_from_formatted_text(body):
    raw = _fault(body, text="Error code: 429 - {'code': 'insufficient_quota'}")
    with pytest.raises(LLMRateLimitError) as raised:
        LLMClient._raise_classified(raw)
    assert raised.value.retry_after == 1200


@pytest.mark.parametrize("status", [401, 403])
def test_quota_fields_do_not_override_real_auth_status(status):
    with pytest.raises(LLMAuthError):
        LLMClient._raise_classified(
            _fault({"code": "insufficient_quota"}, status=status)
        )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "error": {
                "message": _R16_MESSAGE,
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded",
            }
        },
        {"error": {"code": "insufficient_quota"}},
        {"type": "usage_limit_reached"},
    ],
)
def test_exact_sdk_formatted_error_without_body_is_terminal(payload):
    with pytest.raises(LLMBalanceError):
        LLMClient._raise_classified(Exception(f"Error code: 429 - {payload!r}"))


def test_real_sdk_rate_limit_error_carries_terminal_quota():
    import httpx
    import openai

    body = {"message": _R16_MESSAGE, "type": "rate_limit_error"}
    response = httpx.Response(
        429, request=httpx.Request("POST", "https://provider.invalid/v1/responses")
    )
    raw = openai.RateLimitError("usage quota unavailable", response=response, body=body)
    with pytest.raises(LLMBalanceError):
        LLMClient._raise_classified(raw)


@pytest.mark.parametrize("phase", ["hypothesis", "code"])
def test_quota_stops_outer_loop_after_one_charged_traced_dispatch(
    tmp_path, monkeypatch, phase
):
    import scion.proposal.engine.provider_call as provider_calls

    def no_sleep(_seconds):
        pytest.fail("exhausted quota must not back off or redispatch")

    monkeypatch.setattr(provider_calls, "_sleep", no_sleep)
    raw = _fault({"error": {"message": _R16_MESSAGE, "code": "rate_limit_exceeded"}})
    client = _ClassifyingSequenceClient([raw, {"unexpected": "fresh H"}])
    budget = ProviderCallBudget(600)
    creative = CreativeLayer(
        client,
        trace_dir=str(tmp_path / "traces"),
        provider_call_budget=budget,
        provider_transient_retries=2,
    )
    pipeline, branch, _runtime, balance = _pipeline(creative=creative)
    hypothesis = HypothesisProposal(
        hypothesis_text="Test one bounded move.",
        change_locus="local_search",
        action="create_new",
        target_file="operators/bounded.py",
        predicted_direction="improve",
        target_weakness="missing move",
        expected_effect="improve screening",
    )

    def step():
        attempt = (
            pipeline.generate_hypothesis(branch)
            if phase == "hypothesis"
            else pipeline.generate_code(branch, hypothesis)
        )
        assert attempt.proposal is None
        return StepResult(
            branch_id=branch.branch_id,
            action="explore",
            execution_outcome=attempt.execution_outcome,
        )

    terminal = []
    loop = CampaignLoop(
        write_status=lambda **_kwargs: None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda _reason: None,
        run_one_step=step,
        write_terminal_artifacts=terminal.append,
        get_final_wait_timeout=lambda: 0,
        wait_weight_opt_all=lambda _timeout: None,
    )
    result = loop.run(12)
    assert result.stop_reason == "execution_resource_exhausted"
    assert result.evaluated_rounds == 0 and result.scheduled_calls == 1
    assert result.last_execution_outcome == {
        "outcome": ExecutionOutcome.RESOURCE_EXHAUSTED.value,
        "reason_code": "PROVIDER_BALANCE_EXHAUSTED",
        "stage": f"proposal_{phase}",
    }
    assert result.execution_outcome_counts["research_rejected"] == 0
    assert terminal == [result] and balance["value"] is True
    assert pipeline.step_history == []
    assert len(client.calls) == budget.used == 1
    traces = _traces(tmp_path)
    assert len(traces) == 1 and traces[0]["attempt_index"] == 0
    assert traces[0]["error_type"] == "LLMBalanceError"
