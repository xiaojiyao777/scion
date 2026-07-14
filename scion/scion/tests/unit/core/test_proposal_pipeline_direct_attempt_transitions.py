from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.contract.gate import ContractGate
from scion.core.campaign import CampaignManager
from scion.core.execution_outcome import (
    ExecutionOutcome,
    branch_has_execution_hold,
    clear_branch_execution_hold,
)
from scion.core.proposal_pipeline.attempts import ProposalAttemptRecorder
from scion.lineage.registry import LineageRegistry
from scion.proposal.engine import PromptCallReceipt, ProposalValidationError
from scion.proposal.llm_client import (
    LLMAuthError,
    LLMBalanceError,
    LLMFormatError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransportError,
)

from .proposal_pipeline_test_support import FakeCreative, MemoryLineageRegistry, _pipeline


def _receipt(
    phase: str,
    *,
    ok: bool = True,
    provider_ok: bool = True,
    error_category: str | None = None,
    error_type: str | None = None,
) -> PromptCallReceipt:
    trace_ref = f"artifacts/llm_traces/{phase}-trace.json"
    return PromptCallReceipt(
        request_kind=phase,
        trace_ref=trace_ref,
        prompt_manifest_ref=f"{trace_ref}#/prompt_manifest",
        raw_response_ref=f"{trace_ref}#/response",
        prompt_hash=f"{phase}-prompt-hash",
        context_digest=f"{phase}-context-digest",
        provider_ok=provider_ok,
        ok=ok,
        error_category=error_category,
        error_type=error_type,
    )


def _interruption_receipt(
    phase: str,
    error: BaseException,
) -> PromptCallReceipt:
    trace_ref = f"artifacts/llm_traces/{phase}-trace.json"
    return PromptCallReceipt(
        request_kind=phase,
        trace_ref=trace_ref,
        prompt_manifest_ref=f"{trace_ref}#/prompt_manifest",
        raw_response_ref=None,
        prompt_hash=f"{phase}-prompt-hash",
        context_digest=f"{phase}-context-digest",
        provider_ok=False,
        ok=False,
        error_category="provider_call_interrupted",
        error_type=type(error).__name__,
    )


class ReceiptCreative(FakeCreative):
    def __init__(
        self,
        *,
        hypothesis_error: Exception | None = None,
        code_error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.hypothesis_error = hypothesis_error
        self.direct_code_error = code_error

    def generate_hypothesis_with_receipt(self, context, snapshot):
        del snapshot
        self.hypothesis_calls += 1
        self.hypothesis_context = context
        if self.hypothesis_error is not None:
            raise self.hypothesis_error
        return self.hypothesis, _receipt("hypothesis")

    def generate_code_with_receipt(self, context, snapshot):
        del snapshot
        self.code_calls += 1
        self.code_context = context
        if self.direct_code_error is not None:
            raise self.direct_code_error
        return self.patch, _receipt("code")


class OrderedRegistry(MemoryLineageRegistry):
    def __init__(self, order: list[str], *, fail: bool = False) -> None:
        super().__init__()
        self.order = order
        self.fail = fail

    def record_event(self, event: dict):
        self.order.append("transition_commit")
        if self.fail:
            raise OSError("synthetic lineage outage")
        return super().record_event(event)


class FailNthRegistry(MemoryLineageRegistry):
    def __init__(self, *fail_calls: int) -> None:
        super().__init__()
        self.calls = 0
        self.fail_calls = set(fail_calls)

    def record_event(self, event: dict):
        self.calls += 1
        if self.calls in self.fail_calls:
            raise OSError("synthetic nth lineage outage")
        return super().record_event(event)


def _attach_receipt(
    error: BaseException,
    receipt: PromptCallReceipt,
) -> BaseException:
    setattr(error, "_scion_prompt_call_receipt", receipt)
    return error


def _attempt_payload(event: dict) -> dict:
    assert event["event_kind"] == "proposal_attempt_transition"
    return json.loads(event["audit_payload_json"])


def test_attempt_recorder_validates_schema_before_calling_registry(
    tmp_path: Path,
) -> None:
    registry = MemoryLineageRegistry()
    recorder = ProposalAttemptRecorder(registry)
    payload = {
        "schema_version": "proposal-attempt-transition.v1",
        "attempt_id": "attempt-1",
        "campaign_id": "campaign-1",
        "branch_id": "branch-1",
        "runtime_mode": "direct_v3",
        "phase": "hypothesis",
        "status": "generated",
        "transition_reason": "generated",
        "failure_lane": None,
        "hypothesis_id": "hypothesis-1",
        "hypothesis_digest": "digest-1",
        "patch_digest": None,
        "prompt_call": {
            "request_kind": "hypothesis",
            "context_digest": "context-digest",
            "prompt_hash": "prompt-hash",
            "trace_ref": "artifacts/llm_traces/hypothesis.json",
            "prompt_manifest_ref": (
                "artifacts/llm_traces/hypothesis.json#/prompt_manifest"
            ),
            "raw_response_ref": "artifacts/llm_traces/hypothesis.json#/response",
            "provider_ok": True,
            "ok": True,
            "error_category": None,
            "error_type": None,
        },
        "anchors": {
            "problem_id": "warehouse_delivery",
            "problem_spec_hash": "spec-hash",
            "split_manifest_hash": "split-hash",
            "seed_ledger_hash": "seed-hash",
            "champion_version": 1,
            "champion_weight_revision": 0,
            "champion_code_snapshot_hash": "champion-hash",
            "branch_base_champion_id": 1,
            "branch_base_champion_hash": "branch-champion-hash",
        },
        "tainted_artifact_refs": ["artifacts/llm_traces/hypothesis.json"],
    }

    event_id = recorder.record_transition(payload)

    assert event_id
    assert _attempt_payload(registry.events[0]) == payload

    with pytest.raises(ValueError, match="forbidden payload field"):
        recorder.record_transition({**payload, "hypothesis_text": "do not copy"})
    assert len(registry.events) == 1

    sqlite_registry = LineageRegistry(str(tmp_path / "scion.db"))
    sqlite_event_id = ProposalAttemptRecorder(sqlite_registry).record_transition(payload)
    stored = sqlite_registry.query_by_branch("branch-1")
    assert stored[0]["event_id"] == sqlite_event_id
    assert _attempt_payload(stored[0]) == payload


@pytest.mark.parametrize("problem_id", ["warehouse_delivery", "cvrp"])
def test_direct_success_records_one_durable_attempt_per_provider_call(
    problem_id: str,
) -> None:
    registry = MemoryLineageRegistry()
    creative = ReceiptCreative()
    pipeline, branch, runtime, failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
        split_manifest_hash="split-hash",
        seed_ledger_hash="seed-hash",
    )
    pipeline.problem_id = problem_id

    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None
    assert record is not None
    assert record.base_champion_version == 1
    contract_gate = ContractGate(runtime.spec)
    contract_calls = {"hypothesis": 0, "patch": 0}
    contract_calls["hypothesis"] += 1
    hypothesis_contract = contract_gate.validate_hypothesis(
        hypothesis,
        governance_envelope=pipeline.pop_governance_envelope(branch.branch_id),
    )
    assert hypothesis_contract.passed
    patch = pipeline.generate_code(branch, hypothesis)
    assert patch is not None
    contract_calls["patch"] += 1
    patch_contract = contract_gate.validate_patch(
        patch,
        approved_hypothesis=hypothesis,
    )

    assert patch is creative.patch
    assert patch_contract.passed
    assert contract_calls == {"hypothesis": 1, "patch": 1}
    assert failures == []
    payloads = [_attempt_payload(event) for event in registry.events]
    assert [payload["phase"] for payload in payloads] == [
        "hypothesis",
        "hypothesis",
        "code",
        "code",
    ]
    assert [payload["status"] for payload in payloads] == [
        "started",
        "generated",
        "started",
        "generated",
    ]
    hypothesis_started, hypothesis_terminal, code_started, code_terminal = payloads
    hypothesis_attempt_id = hypothesis_started["attempt_id"]
    code_attempt_id = code_started["attempt_id"]
    assert hypothesis_terminal["attempt_id"] == hypothesis_attempt_id
    assert code_terminal["attempt_id"] == code_attempt_id
    assert code_attempt_id != hypothesis_attempt_id
    assert code_started["continuation_of_attempt_id"] == hypothesis_attempt_id
    assert code_terminal["continuation_of_attempt_id"] == hypothesis_attempt_id
    assert hypothesis_started["hypothesis_id"] is None
    assert hypothesis_terminal["hypothesis_id"] == record.hypothesis_id
    assert code_started["hypothesis_id"] == record.hypothesis_id
    assert code_terminal["hypothesis_id"] == record.hypothesis_id
    assert hypothesis_started["patch_digest"] is None
    assert hypothesis_terminal["patch_digest"] is None
    assert code_started["patch_digest"] is None
    assert len(code_terminal["patch_digest"]) == 64
    assert hypothesis_started["runtime_mode"] == "direct_v3"
    assert hypothesis_started["anchors"]["problem_id"] == problem_id
    assert hypothesis_started["anchors"]["split_manifest_hash"] == "split-hash"
    assert hypothesis_started["anchors"]["seed_ledger_hash"] == "seed-hash"
    assert "hypothesis_text" not in hypothesis_terminal
    assert "code_content" not in code_terminal
    assert creative.attempt_audits["hypothesis"]["attempt_id"] == (
        hypothesis_attempt_id
    )
    assert creative.attempt_audits["code"]["attempt_id"] == code_attempt_id
    ref = pipeline.proposal_attempt_refs[branch.branch_id]
    assert ref["schema_version"] == "proposal-attempt-ref.v1"
    assert ref["attempt_id"] == code_attempt_id
    assert ref["phase"] == "code"
    assert ref["lineage_event_id"] == registry.events[3]["event_id"]
    assert ref["started_lineage_event_id"] == registry.events[2]["event_id"]
    assert ref["hypothesis_attempt_id"] == hypothesis_attempt_id
    assert ref["continuation_of_attempt_id"] == hypothesis_attempt_id
    assert ref["artifact_ref"] == "artifacts/llm_traces/code-trace.json"
    refs_by_id = pipeline._direct_attempts.state.attempt_refs_by_id
    assert refs_by_id[hypothesis_attempt_id]["phase"] == "hypothesis"
    assert refs_by_id[hypothesis_attempt_id]["status"] == "generated"
    assert refs_by_id[code_attempt_id] is ref
    phase_refs = pipeline._direct_attempts.state.phase_attempt_refs[branch.branch_id]
    assert phase_refs["hypothesis"] is refs_by_id[hypothesis_attempt_id]
    assert phase_refs["code"] is ref
    assert pipeline.pop_proposal_attempt_ref(branch.branch_id) is ref
    assert branch.branch_id not in pipeline.proposal_attempt_refs


@pytest.mark.parametrize(
    ("error", "expected_lane", "expected_reason"),
    [
        (
            _attach_receipt(
                LLMProviderError("provider unavailable"),
                _receipt(
                    "hypothesis",
                    ok=False,
                    provider_ok=False,
                    error_category="provider_call_failed",
                    error_type="LLMProviderError",
                ),
            ),
            "infra",
            "provider_call_failed",
        ),
        *[
            (
                _attach_receipt(
                    error,
                    _receipt(
                        "hypothesis",
                        ok=False,
                        provider_ok=False,
                        error_category="provider_call_failed",
                        error_type=type(error).__name__,
                    ),
                ),
                "infra",
                "provider_call_failed",
            )
            for error in (
                LLMAuthError("invalid credentials"),
                LLMTimeoutError("provider timeout"),
                LLMRateLimitError("rate limited", retry_after=60.0),
                LLMTransportError("connection reset"),
            )
        ],
        (
            _attach_receipt(
                ProposalValidationError("invalid structured response"),
                _receipt(
                    "hypothesis",
                    ok=False,
                    provider_ok=True,
                    error_category="response_parse_failed",
                    error_type="ProposalValidationError",
                ),
            ),
            "invalid_response",
            "response_parse_failed",
        ),
        (
            _attach_receipt(
                LLMFormatError("invalid provider format"),
                _receipt(
                    "hypothesis",
                    ok=False,
                    provider_ok=False,
                    error_category="provider_call_failed",
                    error_type="LLMFormatError",
                ),
            ),
            "invalid_response",
            "provider_call_failed",
        ),
    ],
)
def test_provider_and_parse_failure_commit_before_failure_routing(
    error: Exception,
    expected_lane: str,
    expected_reason: str,
) -> None:
    order: list[str] = []
    registry = OrderedRegistry(order)
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=ReceiptCreative(hypothesis_error=error),
        lineage_registry=registry,
    )
    pipeline.handle_failure = lambda _branch, _failure: order.append("handle_failure")

    assert pipeline.generate_hypothesis(branch) == (None, None)

    started, payload = [_attempt_payload(event) for event in registry.events]
    assert started["status"] == "started"
    assert payload["status"] == "failed"
    assert payload["attempt_id"] == started["attempt_id"]
    assert payload["failure_lane"] == expected_lane
    assert payload["transition_reason"] == expected_reason
    assert order[:2] == ["transition_commit", "transition_commit"]
    if expected_lane == "infra":
        assert order == [
            "transition_commit",
            "transition_commit",
            "handle_failure",
        ]
        outcome = pipeline.pop_execution_outcome(branch.branch_id)
        assert outcome is not None
        assert outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
    else:
        assert order == ["transition_commit", "transition_commit"]
        outcome = pipeline.pop_execution_outcome(branch.branch_id)
        assert outcome is not None
        assert outcome.outcome is ExecutionOutcome.NOT_EVALUATED
    failure_ref = pipeline.pop_proposal_attempt_ref(branch.branch_id)
    assert failure_ref is not None
    assert failure_ref["phase"] == "hypothesis"
    assert failure_ref["status"] == "failed"
    assert failure_ref["failure_lane"] == expected_lane


def test_three_structured_research_rejections_remain_invalid_responses() -> None:
    error = _attach_receipt(
        ProposalValidationError("invalid structured research response"),
        _receipt(
            "hypothesis",
            ok=False,
            provider_ok=True,
            error_category="response_parse_failed",
            error_type="ProposalValidationError",
        ),
    )
    registry = MemoryLineageRegistry()
    pipeline, branch, _runtime, failures, _balance = _pipeline(
        creative=ReceiptCreative(hypothesis_error=error),
        lineage_registry=registry,
    )

    for index in range(3):
        candidate_branch = replace(branch, branch_id=f"branch-reject-{index}")
        assert pipeline.generate_hypothesis(candidate_branch) == (None, None)

    assert len(registry.events) == 6
    assert failures == []
    payloads = [_attempt_payload(event) for event in registry.events]
    assert [payload["status"] for payload in payloads] == [
        "started",
        "failed",
    ] * 3
    assert all(
        payload["failure_lane"] == "invalid_response"
        for payload in payloads[1::2]
    )


def test_provider_balance_is_resource_exhausted_without_infra_failure_routing() -> None:
    error = _attach_receipt(
        LLMBalanceError("provider balance exhausted"),
        _receipt(
            "hypothesis",
            ok=False,
            provider_ok=False,
            error_category="provider_call_failed",
            error_type="LLMBalanceError",
        ),
    )
    registry = MemoryLineageRegistry()
    pipeline, branch, _runtime, failures, balance = _pipeline(
        creative=ReceiptCreative(hypothesis_error=error),
        lineage_registry=registry,
    )

    assert pipeline.generate_hypothesis(branch) == (None, None)

    outcome = pipeline.pop_execution_outcome(branch.branch_id)
    assert outcome is not None
    assert outcome.outcome is ExecutionOutcome.RESOURCE_EXHAUSTED
    assert outcome.reason_code == "PROVIDER_BALANCE_EXHAUSTED"
    assert balance["value"] is True
    assert failures == []
    assert branch.state.value == "explore"


def test_problem_quality_hook_is_not_a_pre_contract_gate() -> None:
    order: list[str] = []
    registry = OrderedRegistry(order)
    pipeline, branch, runtime, _failures, _balance = _pipeline(
        creative=ReceiptCreative(),
        lineage_registry=registry,
    )
    hook_calls = 0

    def reject_quality(**_kwargs):
        nonlocal hook_calls
        hook_calls += 1
        return {
            "allowed": False,
            "detail": "problem-owned quality rejection",
        }

    runtime.adapter = SimpleNamespace(validate_hypothesis_quality=reject_quality)
    pipeline.handle_failure = lambda _branch, _failure: order.append("handle_failure")

    for index in range(3):
        candidate_branch = replace(branch, branch_id=f"branch-quality-{index}")
        hypothesis, record = pipeline.generate_hypothesis(candidate_branch)
        assert hypothesis is not None
        assert record is not None

    assert hook_calls == 0
    assert len(registry.events) == 6
    assert [
        _attempt_payload(event)["status"] for event in registry.events
    ] == ["started", "generated"] * 3
    assert order == ["transition_commit"] * 6


def test_active_problem_boundary_is_deferred_to_outer_contract() -> None:
    order: list[str] = []
    registry = OrderedRegistry(order)
    problem_spec = SimpleNamespace(
        operator_categories=["local_search"],
        search_space=SimpleNamespace(
            editable=["policies/*.py"],
            frozen=[],
            import_whitelist=[],
        ),
        research_surfaces=[
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                target_files=["policies/*.py"],
                create_new_allowed=True,
                modify_allowed=True,
                remove_allowed=False,
            )
        ],
    )
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=ReceiptCreative(),
        lineage_registry=registry,
        problem_spec=problem_spec,
        forced_locus=None,
    )
    pipeline.handle_failure = lambda _branch, _failure: order.append("handle_failure")

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is not None
    assert record is not None
    payload = _attempt_payload(registry.events[1])
    assert payload["status"] == "generated"
    assert payload["transition_reason"] == "generated"
    assert pipeline.pop_governance_envelope(branch.branch_id) is not None
    assert order == ["transition_commit", "transition_commit"]


def test_patch_quality_hook_is_not_a_pre_contract_gate() -> None:
    order: list[str] = []
    registry = OrderedRegistry(order)
    pipeline, branch, runtime, _failures, _balance = _pipeline(
        creative=ReceiptCreative(),
        lineage_registry=registry,
    )
    runtime.adapter = SimpleNamespace(
        validate_hypothesis_quality=lambda **_kwargs: {"allowed": True},
        validate_patch_quality=lambda **_kwargs: {
            "allowed": False,
            "detail": "problem-owned patch quality rejection",
        },
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None
    order.clear()
    pipeline.handle_failure = lambda _branch, _failure: order.append("handle_failure")

    patch = pipeline.generate_code(branch, hypothesis)

    assert patch is not None
    payload = _attempt_payload(registry.events[3])
    assert payload["status"] == "generated"
    assert payload["transition_reason"] == "generated"
    assert payload["failure_lane"] is None
    assert len(payload["patch_digest"]) == 64
    assert order == ["transition_commit", "transition_commit"]


def test_code_failure_uses_new_attempt_and_commits_started_then_failed() -> None:
    order: list[str] = []
    registry = OrderedRegistry(order)
    code_error = _attach_receipt(
        ProposalValidationError("invalid patch response"),
        _receipt(
            "code",
            ok=False,
            provider_ok=True,
            error_category="response_parse_failed",
            error_type="ProposalValidationError",
        ),
    )
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=ReceiptCreative(code_error=code_error),
        lineage_registry=registry,
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None
    order.clear()
    pipeline.handle_failure = lambda _branch, _failure: order.append("handle_failure")

    assert pipeline.generate_code(branch, hypothesis) is None

    payloads = [_attempt_payload(event) for event in registry.events]
    hypothesis_attempt_id = payloads[0]["attempt_id"]
    code_started, code_failed = payloads[2:4]
    assert code_started["status"] == "started"
    assert code_failed["status"] == "failed"
    assert code_started["attempt_id"] == code_failed["attempt_id"]
    assert code_started["attempt_id"] != hypothesis_attempt_id
    assert code_started["continuation_of_attempt_id"] == hypothesis_attempt_id
    assert code_failed["failure_lane"] == "invalid_response"
    assert order == ["transition_commit", "transition_commit"]
    outcome = pipeline.pop_execution_outcome(branch.branch_id)
    assert outcome is not None
    assert outcome.outcome is ExecutionOutcome.NOT_EVALUATED
    failure_ref = pipeline.pop_proposal_attempt_ref(branch.branch_id)
    assert failure_ref is not None
    assert failure_ref["phase"] == "code"
    assert failure_ref["status"] == "failed"


@pytest.mark.parametrize("code_fails", [False, True])
def test_campaign_code_transition_invalidates_explore_ref_cache(
    code_fails: bool,
) -> None:
    code_error = None
    if code_fails:
        code_error = _attach_receipt(
            ProposalValidationError("invalid patch response"),
            _receipt(
                "code",
                ok=False,
                provider_ok=True,
                error_category="response_parse_failed",
                error_type="ProposalValidationError",
            ),
        )
    pipeline, branch, *_rest = _pipeline(
        creative=ReceiptCreative(code_error=code_error),
        lineage_registry=MemoryLineageRegistry(),
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None
    hypothesis_ref = pipeline.proposal_attempt_refs[branch.branch_id]
    explore = SimpleNamespace(
        _proposal_session_ref_cache={branch.branch_id: hypothesis_ref}
    )
    owner = SimpleNamespace(
        _proposal_pipeline=pipeline,
        _explore_step_pipeline=explore,
    )

    result = CampaignManager._round2_generate_code(owner, branch, hypothesis)

    assert (result is None) is code_fails
    assert branch.branch_id not in explore._proposal_session_ref_cache
    terminal_ref = pipeline.proposal_attempt_refs[branch.branch_id]
    assert terminal_ref["phase"] == "code"
    assert terminal_ref["status"] == ("failed" if code_fails else "generated")


def test_campaign_interruption_clears_attempt_ref_without_continuation() -> None:
    pipeline, branch, *_rest = _pipeline()
    hypothesis = pipeline.creative.hypothesis

    def interrupt_code(*_args, **_kwargs):
        raise KeyboardInterrupt("operator interrupt")

    owner = CampaignManager.__new__(CampaignManager)
    owner._proposal_pipeline = SimpleNamespace(
        generate_code=interrupt_code,
    )
    owner._explore_step_pipeline = SimpleNamespace(
        _proposal_session_ref_cache={branch.branch_id: {"status": "started"}}
    )

    with pytest.raises(KeyboardInterrupt):
        CampaignManager._round2_generate_code(owner, branch, hypothesis)

    assert branch.branch_id not in (
        owner._explore_step_pipeline._proposal_session_ref_cache
    )


def test_code_lineage_failure_clears_hypothesis_ref_and_explore_cache() -> None:
    order: list[str] = []
    registry = OrderedRegistry(order)
    pipeline, branch, *_rest = _pipeline(
        creative=ReceiptCreative(),
        lineage_registry=registry,
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None
    hypothesis_ref = pipeline.proposal_attempt_refs[branch.branch_id]
    registry.fail = True
    explore = SimpleNamespace(
        _proposal_session_ref_cache={branch.branch_id: hypothesis_ref}
    )
    owner = SimpleNamespace(
        _proposal_pipeline=pipeline,
        _explore_step_pipeline=explore,
    )

    assert CampaignManager._round2_generate_code(owner, branch, hypothesis) is None

    assert branch.branch_id not in pipeline.proposal_attempt_refs
    assert branch.branch_id not in explore._proposal_session_ref_cache
    surfaced_ref = pipeline.pop_proposal_attempt_ref(branch.branch_id)
    assert not (
        surfaced_ref
        and surfaced_ref.get("schema_version") == "proposal-attempt-ref.v1"
    )


def test_second_code_call_without_pending_attempt_fails_closed_before_provider() -> None:
    registry = MemoryLineageRegistry()
    creative = ReceiptCreative()
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None
    assert pipeline.generate_code(branch, hypothesis) is creative.patch
    routed: list[tuple[str, str]] = []
    pipeline.handle_failure = lambda _branch, failure: routed.append(
        (failure.category, failure.detail)
    )

    assert pipeline.generate_code(branch, hypothesis) is None

    assert creative.code_calls == 1
    assert len(registry.events) == 4
    assert routed == [
        ("infra", "approved_hypothesis_binding_missing_for_direct_code")
    ]


def test_failed_code_attempt_cannot_continue_without_new_hypothesis() -> None:
    registry = MemoryLineageRegistry()
    first_error = _attach_receipt(
        ProposalValidationError("first code response invalid"),
        _receipt(
            "code",
            ok=False,
            provider_ok=True,
            error_category="response_parse_failed",
            error_type="ProposalValidationError",
        ),
    )
    creative = ReceiptCreative(code_error=first_error)
    pipeline, branch, runtime, _failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None
    assert pipeline.generate_code(branch, hypothesis) is None
    creative.direct_code_error = None

    assert pipeline.generate_code(branch, hypothesis) is None
    assert creative.hypothesis_calls == 1
    assert creative.code_calls == 1
    assert "prior_failure" not in runtime.code_kwargs
    outcome = pipeline.pop_execution_outcome(branch.branch_id)
    assert outcome is not None
    assert outcome.reason_code == "PROPOSAL_INTEGRITY_BLOCKED"


def test_terminal_write_failure_cannot_restart_code_provider() -> None:
    registry = FailNthRegistry(4)
    creative = ReceiptCreative()
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None

    assert pipeline.generate_code(branch, hypothesis) is None

    first_code_started = _attempt_payload(registry.events[2])
    assert first_code_started["status"] == "started"
    assert creative.code_calls == 1

    assert pipeline.generate_code(branch, hypothesis) is None
    assert creative.code_calls == 1
    assert len(registry.events) == 3


def test_altered_approved_hypothesis_fails_before_code_provider_and_clears_ref() -> None:
    registry = MemoryLineageRegistry()
    creative = ReceiptCreative()
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None
    altered = replace(hypothesis, hypothesis_text="altered after approval")
    routed: list[tuple[str, str]] = []
    pipeline.handle_failure = lambda _branch, failure: routed.append(
        (failure.category, failure.detail)
    )

    assert pipeline.generate_code(branch, altered) is None

    assert creative.code_calls == 0
    assert len(registry.events) == 2
    assert branch.branch_id not in pipeline.proposal_attempt_refs
    assert branch.branch_id not in pipeline.approved_hypothesis_bindings
    assert pipeline.hypothesis_store.get_one(record.hypothesis_id).status == "rejected"
    assert routed == [
        ("infra", "approved_hypothesis_binding_mismatch_for_direct_code")
    ]


def test_started_lineage_failure_stops_before_provider_as_infra() -> None:
    order: list[str] = []
    registry = OrderedRegistry(order, fail=True)
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=ReceiptCreative(),
        lineage_registry=registry,
    )
    routed: list[str] = []
    pipeline.handle_failure = lambda _branch, failure: (
        order.append("handle_failure"),
        routed.append(failure.category),
    )

    assert pipeline.generate_hypothesis(branch) == (None, None)

    assert order == ["transition_commit", "handle_failure"]
    assert routed == ["infra"]
    outcome = pipeline.pop_execution_outcome(branch.branch_id)
    assert outcome is not None
    assert outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert outcome.reason_code == "PROPOSAL_LINEAGE_BLOCKED"
    assert pipeline.creative.hypothesis_calls == 0
    assert pipeline.proposal_attempt_refs == {}
    stored = pipeline.hypothesis_store.get_by_branch(branch.branch_id)
    assert stored == []


def test_hypothesis_keyboard_interrupt_is_terminal_non_resumable_and_new_call_gets_new_id() -> None:
    registry = MemoryLineageRegistry()
    interruption = KeyboardInterrupt("operator interrupt")
    creative = ReceiptCreative(
        hypothesis_error=_attach_receipt(
            interruption,
            _interruption_receipt("hypothesis", interruption),
        )
    )
    pipeline, branch, _runtime, failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )

    with pytest.raises(KeyboardInterrupt):
        pipeline.generate_hypothesis(branch)

    assert creative.hypothesis_calls == 1
    assert len(registry.events) == 2
    started, interrupted = [_attempt_payload(event) for event in registry.events]
    assert started["status"] == "started"
    assert interrupted["status"] == "interrupted"
    assert interrupted["attempt_id"] == started["attempt_id"]
    assert interrupted["transition_reason"] == "provider_call_interrupted"
    assert interrupted["failure_lane"] is None
    assert interrupted["non_resumable"] is True
    assert interrupted["prompt_call"]["raw_response_ref"] is None
    assert branch.branch_id not in pipeline.proposal_attempt_ids
    assert failures == []
    outcome = pipeline.pop_execution_outcome(branch.branch_id)
    assert outcome is not None
    assert outcome.outcome is ExecutionOutcome.INTERRUPTED
    assert outcome.reason_code == "PROPOSAL_PROVIDER_INTERRUPTED"
    assert outcome.provenance["attempt_id"] == started["attempt_id"]
    assert outcome.provenance["non_resumable"] is True
    assert branch_has_execution_hold(branch) is True
    ref = pipeline.proposal_attempt_refs[branch.branch_id]
    assert ref["attempt_id"] == started["attempt_id"]
    assert ref["status"] == "interrupted"
    assert ref["non_resumable"] is True

    clear_branch_execution_hold(branch)
    creative.hypothesis_error = None
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is creative.hypothesis
    assert record is not None
    restarted, generated = [
        _attempt_payload(event) for event in registry.events[2:4]
    ]
    assert restarted["attempt_id"] == generated["attempt_id"]
    assert restarted["attempt_id"] != started["attempt_id"]
    assert creative.hypothesis_calls == 2


def test_code_operator_cancellation_terminalizes_attempt_and_never_reuses_binding() -> None:
    class OperatorCancellation(KeyboardInterrupt):
        pass

    registry = MemoryLineageRegistry()
    cancellation = OperatorCancellation("signal:SIGTERM")
    creative = ReceiptCreative(
        code_error=_attach_receipt(
            cancellation,
            _interruption_receipt("code", cancellation),
        )
    )
    pipeline, branch, _runtime, failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None

    with pytest.raises(OperatorCancellation):
        pipeline.generate_code(branch, hypothesis)

    code_started, code_interrupted = [
        _attempt_payload(event) for event in registry.events[2:4]
    ]
    assert code_started["status"] == "started"
    assert code_interrupted["status"] == "interrupted"
    assert code_interrupted["attempt_id"] == code_started["attempt_id"]
    assert code_interrupted["continuation_of_attempt_id"] == _attempt_payload(
        registry.events[1]
    )["attempt_id"]
    assert code_interrupted["non_resumable"] is True
    assert creative.code_calls == 1
    assert failures == []
    assert branch.branch_id not in pipeline.approved_hypothesis_bindings
    preserved = pipeline.hypothesis_store.get_one(record.hypothesis_id)
    assert preserved is record
    assert preserved.status == "active"
    outcome = pipeline.pop_execution_outcome(branch.branch_id)
    assert outcome is not None
    assert outcome.outcome is ExecutionOutcome.INTERRUPTED
    assert branch_has_execution_hold(branch) is True

    clear_branch_execution_hold(branch)
    creative.direct_code_error = None
    new_hypothesis, new_record = pipeline.generate_hypothesis(branch)
    assert new_hypothesis is not None and new_record is not None
    assert pipeline.generate_code(branch, new_hypothesis) is creative.patch
    new_code_started = _attempt_payload(registry.events[6])
    assert new_code_started["status"] == "started"
    assert new_code_started["attempt_id"] != code_started["attempt_id"]
    assert creative.code_calls == 2


def test_interruption_outcome_is_durable_alongside_terminal_attempt(
    tmp_path: Path,
) -> None:
    registry = LineageRegistry(str(tmp_path / "scion.db"))
    interruption = KeyboardInterrupt("operator interrupt")
    creative = ReceiptCreative(
        hypothesis_error=_attach_receipt(
            interruption,
            _interruption_receipt("hypothesis", interruption),
        )
    )
    pipeline, branch, _runtime, failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )

    with pytest.raises(KeyboardInterrupt):
        pipeline.generate_hypothesis(branch)

    events = registry.query_by_branch(branch.branch_id)
    transitions = [
        _attempt_payload(event)
        for event in reversed(events)
        if event["event_kind"] == "proposal_attempt_transition"
    ]
    assert [item["status"] for item in transitions] == [
        "started",
        "interrupted",
    ]
    assert transitions[0]["attempt_id"] == transitions[1]["attempt_id"]
    durable = registry.get_latest_execution_outcome(
        branch_id=branch.branch_id,
        campaign_id=pipeline.campaign_id,
    )
    assert durable is not None
    assert durable["outcome"] == "interrupted"
    assert durable["reason_code"] == "PROPOSAL_PROVIDER_INTERRUPTED"
    assert durable["provenance"]["attempt_id"] == transitions[0]["attempt_id"]
    assert durable["provenance"]["non_resumable"] is True
    assert creative.hypothesis_calls == 1
    assert failures == []


def test_legacy_direct_creative_without_receipt_fails_closed_when_audited() -> None:
    class GenericReceiptOnlyCreative(FakeCreative):
        generate_direct_hypothesis_with_receipt = None
        generate_direct_code_with_receipt = None

    registry = MemoryLineageRegistry()
    creative = GenericReceiptOnlyCreative()
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )
    routed: list[tuple[str, str]] = []
    pipeline.handle_failure = lambda _branch, failure: routed.append(
        (failure.category, failure.detail)
    )

    assert pipeline.generate_hypothesis(branch) == (None, None)

    assert creative.hypothesis_calls == 0
    assert registry.events == []
    assert routed == [
        (
            "infra",
            "direct_hypothesis_receipt_api_required_for_lineage",
        )
    ]


def test_legacy_code_api_is_blocked_before_provider_when_lineage_is_enabled() -> None:
    class HypothesisReceiptOnlyCreative(FakeCreative):
        generate_direct_code_with_receipt = None

        def generate_hypothesis_with_receipt(self, context, snapshot):
            del snapshot
            self.hypothesis_calls += 1
            self.hypothesis_context = context
            return self.hypothesis, _receipt("hypothesis")

    registry = MemoryLineageRegistry()
    creative = HypothesisReceiptOnlyCreative()
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None
    routed: list[tuple[str, str]] = []
    pipeline.handle_failure = lambda _branch, failure: routed.append(
        (failure.category, failure.detail)
    )

    assert pipeline.generate_code(branch, hypothesis) is None

    assert creative.code_calls == 0
    assert len(registry.events) == 2
    assert routed == [
        ("infra", "direct_code_receipt_api_required_for_lineage")
    ]


def test_invalid_hypothesis_context_fails_before_attempt_or_provider() -> None:
    registry = MemoryLineageRegistry()
    creative = FakeCreative()
    pipeline, branch, runtime, _failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )
    runtime.build_hypothesis_context = lambda **_kwargs: {
        "problem_summary": "invalid authority fixture",
        "branch_id": branch.branch_id,
        "research_surfaces": "",
        "champion_operators_code": "",
        "champion_stats": {},
        "undeclared_context_fact": "must fail closed",
    }
    routed: list[tuple[str, str]] = []
    pipeline.handle_failure = lambda _branch, failure: routed.append(
        (failure.category, failure.detail)
    )

    assert pipeline.generate_hypothesis(branch) == (None, None)

    detail = pipeline.hypothesis_failure_details[branch.branch_id]
    assert detail.startswith("proposal_context_validation_failed:ValueError:")
    assert routed == [("infra", detail)]
    assert creative.hypothesis_calls == 0
    assert branch.branch_id not in pipeline.proposal_attempt_ids
    assert branch.branch_id not in pipeline.proposal_attempt_refs
    assert registry.events == []


def test_invalid_hypothesis_surface_binding_fails_before_attempt_or_provider() -> None:
    registry = MemoryLineageRegistry()
    creative = FakeCreative()
    pipeline, branch, runtime, _failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )
    runtime.build_hypothesis_context = lambda **_kwargs: {
        "problem_summary": "invalid surface binding fixture",
        "branch_id": branch.branch_id,
        "research_surfaces": "local_search",
        "champion_operators_code": "class Solver: pass",
        "champion_stats": {},
    }
    routed: list[tuple[str, str]] = []
    pipeline.handle_failure = lambda _branch, failure: routed.append(
        (failure.category, failure.detail)
    )

    assert pipeline.generate_hypothesis(branch) == (None, None)

    detail = pipeline.hypothesis_failure_details[branch.branch_id]
    assert detail.startswith("proposal_context_validation_failed:ValueError:")
    assert "non-empty research_surfaces" in detail
    assert routed == [("infra", detail)]
    assert creative.hypothesis_calls == 0
    assert branch.branch_id not in pipeline.proposal_attempt_ids
    assert branch.branch_id not in pipeline.proposal_attempt_refs
    assert registry.events == []


def test_invalid_code_context_clears_pending_but_preserves_approved_binding() -> None:
    registry = MemoryLineageRegistry()
    creative = ReceiptCreative()
    pipeline, branch, runtime, _failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None
    binding_before = dict(pipeline.approved_hypothesis_bindings[branch.branch_id])
    runtime.build_code_context = lambda **_kwargs: {
        "problem_summary": "invalid authority fixture",
        "branch_id": branch.branch_id,
        "hypothesis_detail": hypothesis.hypothesis_text,
        "target_file": hypothesis.target_file,
        "target_file_code": "",
        "operator_interface_spec": "",
        "editable_patterns": "operators/*.py",
        "frozen_patterns": "solver.py",
        "undeclared_context_fact": "must fail closed",
    }
    routed: list[tuple[str, str]] = []
    pipeline.handle_failure = lambda _branch, failure: routed.append(
        (failure.category, failure.detail)
    )

    assert pipeline.generate_code(branch, hypothesis) is None

    detail = pipeline.hypothesis_failure_details[branch.branch_id]
    assert detail.startswith("proposal_context_validation_failed:ValueError:")
    assert routed == [("infra", detail)]
    assert creative.code_calls == 0
    assert branch.branch_id not in pipeline.proposal_attempt_ids
    assert branch.branch_id not in pipeline.proposal_attempt_refs
    assert pipeline.approved_hypothesis_bindings[branch.branch_id] == binding_before
    assert len(registry.events) == 2


@pytest.mark.parametrize(
    ("error", "receipt", "expected_reason", "expected_trace_error"),
    [
        (
            OSError("trace start failed"),
            PromptCallReceipt(
                request_kind="hypothesis",
                trace_ref=None,
                prompt_manifest_ref=None,
                raw_response_ref=None,
                prompt_hash="hypothesis-prompt-hash",
                context_digest="hypothesis-context-digest",
                provider_ok=False,
                ok=False,
                error_category="trace_start_failed",
                error_type="OSError",
            ),
            "trace_start_failed",
            {"stage": "start", "error_type": "OSError"},
        ),
        (
            RuntimeError("non-standard provider failure"),
            PromptCallReceipt(
                request_kind="hypothesis",
                trace_ref="artifacts/llm_traces/hypothesis-trace.json",
                prompt_manifest_ref=(
                    "artifacts/llm_traces/hypothesis-trace.json#/prompt_manifest"
                ),
                raw_response_ref=None,
                prompt_hash="hypothesis-prompt-hash",
                context_digest="hypothesis-context-digest",
                provider_ok=False,
                ok=False,
                error_category="provider_call_failed",
                error_type="RuntimeError",
                trace_persistence_error="trace_finish_failed:PermissionError",
            ),
            "provider_call_failed",
            {"stage": "finish", "error_type": "PermissionError"},
        ),
        (
            OSError("trace finish failed"),
            PromptCallReceipt(
                request_kind="hypothesis",
                trace_ref="artifacts/llm_traces/hypothesis-trace.json",
                prompt_manifest_ref=(
                    "artifacts/llm_traces/hypothesis-trace.json#/prompt_manifest"
                ),
                raw_response_ref=None,
                prompt_hash="hypothesis-prompt-hash",
                context_digest="hypothesis-context-digest",
                provider_ok=True,
                ok=False,
                error_category="trace_finish_failed",
                error_type="OSError",
                trace_persistence_error="trace_finish_failed:OSError",
            ),
            "trace_finish_failed",
            {"stage": "finish", "error_type": "OSError"},
        ),
    ],
)
def test_receipt_bearing_nonstandard_failures_commit_infra_before_routing(
    error: Exception,
    receipt: PromptCallReceipt,
    expected_reason: str,
    expected_trace_error: dict[str, str],
) -> None:
    _attach_receipt(error, receipt)
    order: list[str] = []
    registry = OrderedRegistry(order)
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=ReceiptCreative(hypothesis_error=error),
        lineage_registry=registry,
    )
    pipeline.handle_failure = lambda _branch, failure: order.append(
        f"handle_failure:{failure.category}"
    )

    assert pipeline.generate_hypothesis(branch) == (None, None)

    payload = _attempt_payload(registry.events[1])
    assert payload["status"] == "failed"
    assert payload["failure_lane"] == "infra"
    assert payload["transition_reason"] == expected_reason
    assert payload["trace_persistence_error"] == expected_trace_error
    assert payload["prompt_call"]["provider_ok"] is receipt.provider_ok
    assert payload["prompt_call"]["error_category"] == receipt.error_category
    assert order == [
        "transition_commit",
        "transition_commit",
        "handle_failure:infra",
    ]
    outcome = pipeline.pop_execution_outcome(branch.branch_id)
    assert outcome is not None
    assert outcome.outcome is ExecutionOutcome.BLOCKED_INFRA


def test_classifier_exception_uses_single_post_provider_boundary() -> None:
    order: list[str] = []
    registry = OrderedRegistry(order)
    creative = ReceiptCreative()
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )

    def fail_classification(_text):
        raise RuntimeError("classifier failed after provider response")

    pipeline.classifier.classify = fail_classification
    pipeline.handle_failure = lambda _branch, failure: order.append(
        f"handle_failure:{failure.category}"
    )

    assert pipeline.generate_hypothesis(branch) == (None, None)

    payload = _attempt_payload(registry.events[1])
    assert creative.hypothesis_calls == 1
    assert len(registry.events) == 2
    assert payload["status"] == "failed"
    assert payload["failure_lane"] == "infra"
    assert payload["transition_reason"] == "post_provider_processing_failed"
    assert pipeline.proposal_attempt_ids == {}
    assert pipeline.hypothesis_store.get_by_branch(branch.branch_id) == []
    assert order == ["transition_commit", "transition_commit"]
    outcome = pipeline.pop_execution_outcome(branch.branch_id)
    assert outcome is not None
    assert outcome.outcome is ExecutionOutcome.NOT_EVALUATED


def test_code_trace_start_failure_commits_without_unbound_patch() -> None:
    trace_error = OSError("code trace start failed")
    _attach_receipt(
        trace_error,
        PromptCallReceipt(
            request_kind="code",
            trace_ref=None,
            prompt_manifest_ref=None,
            raw_response_ref=None,
            prompt_hash="code-prompt-hash",
            context_digest="code-context-digest",
            provider_ok=False,
            ok=False,
            error_category="trace_start_failed",
            error_type="OSError",
        ),
    )
    registry = MemoryLineageRegistry()
    creative = ReceiptCreative(code_error=trace_error)
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=creative,
        lineage_registry=registry,
    )
    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None and record is not None

    assert pipeline.generate_code(branch, hypothesis) is None

    code_started = _attempt_payload(registry.events[2])
    payload = _attempt_payload(registry.events[3])
    assert creative.code_calls == 1
    assert code_started["status"] == "started"
    assert code_started["attempt_id"] == payload["attempt_id"]
    assert payload["phase"] == "code"
    assert payload["status"] == "failed"
    assert payload["failure_lane"] == "infra"
    assert payload["transition_reason"] == "trace_start_failed"
    assert payload["patch_digest"] is None
    assert payload["trace_persistence_error"] == {
        "stage": "start",
        "error_type": "OSError",
    }


def test_hypothesis_store_failure_commits_failed_transition_without_id() -> None:
    order: list[str] = []
    registry = OrderedRegistry(order)
    pipeline, branch, _runtime, _failures, _balance = _pipeline(
        creative=ReceiptCreative(),
        lineage_registry=registry,
    )

    def fail_save(_record):
        raise OSError("hypothesis store unavailable")

    pipeline.hypothesis_store.save = fail_save
    pipeline.handle_failure = lambda _branch, failure: order.append(
        f"handle_failure:{failure.category}"
    )

    assert pipeline.generate_hypothesis(branch) == (None, None)

    started = _attempt_payload(registry.events[0])
    payload = _attempt_payload(registry.events[1])
    assert started["status"] == "started"
    assert started["attempt_id"] == payload["attempt_id"]
    assert payload["status"] == "failed"
    assert payload["failure_lane"] == "infra"
    assert payload["transition_reason"] == "hypothesis_store_write_failed"
    assert payload["hypothesis_id"] is None
    assert payload["hypothesis_digest"]
    assert order == [
        "transition_commit",
        "transition_commit",
        "handle_failure:infra",
    ]
