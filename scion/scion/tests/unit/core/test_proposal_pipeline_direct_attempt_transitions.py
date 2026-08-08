"""Focused direct-V3 proposal-call behavior without attempt identities."""
from __future__ import annotations

import json

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import HypothesisProposal
from scion.proposal.llm_client import LLMFormatError

from .proposal_pipeline_test_support import FakeCreative, _pipeline


def test_normal_h_c_path_calls_provider_once_and_appends_one_event_each() -> None:
    creative = FakeCreative()
    pipeline, branch, _runtime, _failures, _balance = _pipeline(creative=creative)

    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None
    assert record is not None
    patch = pipeline.generate_code(branch, hypothesis)

    assert patch is not None
    assert creative.hypothesis_calls == 1
    assert creative.code_calls == 1
    events = pipeline.lineage_registry.events
    assert [event["stage"] for event in events] == [
        "proposal_hypothesis",
        "proposal_code",
    ]
    assert all(event["event_kind"] == "proposal_call" for event in events)
    serialized = json.dumps(events)
    for forbidden in ("attempt_id", "continuation", "capability", "lease"):
        assert forbidden not in serialized


def test_approved_h_is_consumed_before_the_single_code_call() -> None:
    creative = FakeCreative()
    pipeline, branch, _runtime, _failures, _balance = _pipeline(creative=creative)
    hypothesis, _record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None

    assert pipeline.generate_code(branch, hypothesis) is not None
    assert pipeline.generate_code(branch, hypothesis) is None
    assert creative.code_calls == 1
    outcome = pipeline.pop_execution_outcome(branch.branch_id)
    assert outcome is not None
    assert outcome.outcome is ExecutionOutcome.NOT_EVALUATED
    assert outcome.reason_code == "CODE_CALL_ALREADY_CONSUMED"


def test_changed_h_is_rejected_before_the_code_provider() -> None:
    creative = FakeCreative()
    pipeline, branch, _runtime, _failures, _balance = _pipeline(creative=creative)
    hypothesis, _record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None
    changed = HypothesisProposal(
        **{
            **hypothesis.__dict__,
            "hypothesis_text": "Use a different unapproved mechanism.",
        }
    )

    assert pipeline.generate_code(branch, changed) is None
    assert creative.code_calls == 0
    outcome = pipeline.pop_execution_outcome(branch.branch_id)
    assert outcome is not None
    assert outcome.reason_code == "APPROVED_HYPOTHESIS_BINDING_MISSING"


def test_invalid_code_response_is_one_call_event_with_typed_outcome() -> None:
    creative = FakeCreative(code_error=LLMFormatError("invalid patch payload"))
    pipeline, branch, _runtime, _failures, _balance = _pipeline(creative=creative)
    hypothesis, _record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None

    assert pipeline.generate_code(branch, hypothesis) is None
    assert creative.code_calls == 1
    assert len(pipeline.lineage_registry.events) == 2
    event = pipeline.lineage_registry.events[-1]
    payload = json.loads(event["audit_payload_json"])
    assert payload["phase"] == "code"
    assert payload["status"] == "failed"
    assert payload["execution_outcome"]["outcome"] == "not_evaluated"
    assert (
        payload["execution_outcome"]["reason_code"]
        == "PROPOSAL_RESPONSE_INVALID"
    )
