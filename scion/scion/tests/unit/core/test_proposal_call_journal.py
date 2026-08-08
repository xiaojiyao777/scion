from __future__ import annotations

import json

from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.proposal_pipeline.call_journal import ProposalCallJournal
from scion.proposal.engine import PromptCallReceipt


class MemoryRegistry:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record_event(self, event: dict) -> str:
        self.events.append(dict(event))
        return f"event-{len(self.events)}"


def _receipt(kind: str, *, ok: bool = True) -> PromptCallReceipt:
    trace_ref = f"artifacts/llm_traces/{kind}.json"
    return PromptCallReceipt(
        request_kind=kind,
        trace_ref=trace_ref,
        prompt_manifest_ref=f"{trace_ref}#/prompt_manifest",
        raw_response_ref=f"{trace_ref}#/response" if ok else None,
        prompt_hash=f"{kind}-prompt",
        context_digest=f"{kind}-context",
        provider_ok=ok,
        ok=ok,
        error_category=None if ok else "response_parse_failed",
        error_type=None if ok else "ProposalValidationError",
    )


def test_append_records_one_complete_call_without_attempt_identity() -> None:
    registry = MemoryRegistry()
    journal = ProposalCallJournal(registry, "campaign-1")
    receipt = _receipt("code")

    ref = journal.append(
        branch_id="branch-1",
        phase="code",
        status="generated",
        hypothesis_id="hypothesis-1",
        receipt=receipt,
    )

    assert len(registry.events) == 1
    event = registry.events[0]
    assert event["event_kind"] == "proposal_call"
    assert event["stage"] == "proposal_code"
    payload = json.loads(event["audit_payload_json"])
    assert payload["receipt"] == {
        "request_kind": "code",
        "context_digest": "code-context",
        "prompt_hash": "code-prompt",
        "trace_ref": "artifacts/llm_traces/code.json",
        "prompt_manifest_ref": (
            "artifacts/llm_traces/code.json#/prompt_manifest"
        ),
        "raw_response_ref": "artifacts/llm_traces/code.json#/response",
        "provider_ok": True,
        "ok": True,
        "error_category": None,
        "error_type": None,
        "trace_persistence_error": None,
    }
    assert ref == {
        "schema_version": "proposal-call-ref.v1",
        "lineage_event_id": "event-1",
        "phase": "code",
        "status": "generated",
        "hypothesis_id": "hypothesis-1",
        "artifact_ref": "artifacts/llm_traces/code.json",
        "prompt_manifest_ref": (
            "artifacts/llm_traces/code.json#/prompt_manifest"
        ),
    }
    serialized = json.dumps({"event": event, "ref": ref})
    for forbidden in ("attempt_id", "continuation", "capability", "permit", "lease"):
        assert forbidden not in serialized


def test_failure_outcome_is_in_the_same_single_call_event() -> None:
    registry = MemoryRegistry()
    journal = ProposalCallJournal(registry, "campaign-1")
    outcome = ExecutionOutcomeRecord(
        outcome=ExecutionOutcome.NOT_EVALUATED,
        reason_code="PROPOSAL_RESPONSE_INVALID",
        detail="patch response did not satisfy schema",
        provenance={"stage": "proposal_code"},
    )

    ref = journal.append(
        branch_id="branch-1",
        phase="code",
        status="failed",
        hypothesis_id="hypothesis-1",
        receipt=_receipt("code", ok=False),
        execution_outcome=outcome,
    )

    assert len(registry.events) == 1
    payload = json.loads(registry.events[0]["audit_payload_json"])
    assert payload["execution_outcome"] == outcome.to_primitive()
    assert ref["failure_code"] == "PROPOSAL_RESPONSE_INVALID"
    assert ref["primary_failure"]["detail"] == outcome.detail
