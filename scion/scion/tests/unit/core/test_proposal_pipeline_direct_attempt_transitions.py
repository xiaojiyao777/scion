"""Focused direct-V3 proposal-call behavior without attempt identities."""

from __future__ import annotations

import pytest
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import BranchState, HypothesisProposal, StepRecord
from scion.core.resource_envelope import ProviderCallCapExhausted
from scion.proposal.engine import ProposalValidationError
from scion.proposal.llm_client import LLMFormatError, LLMTransportError

from .proposal_pipeline_test_support import FakeCreative, _pipeline


class _HypothesisSequenceCreative(FakeCreative):
    def __init__(self, responses: list[Exception | None]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.hypothesis_contexts: list[dict[str, object]] = []

    def generate_direct_hypothesis(self, snapshot):
        self.hypothesis_calls += 1
        self.hypothesis_contexts.append(snapshot.structured_context)
        response = self.responses.pop(0)
        if response is not None:
            raise response
        return self.hypothesis


class _AbstainingResearchCreative(FakeCreative):
    def __init__(self) -> None:
        super().__init__()
        self.hypothesis_contexts: list[dict[str, object]] = []

    def call_hypothesis_research_turn(self, snapshot):
        self.hypothesis_contexts.append(snapshot.structured_context)
        return {"action": "abstain", "reason": "UNTRUSTED_DETAIL"}


class _ManyRejectionsCreative(FakeCreative):
    def __init__(self, rejection_count: int) -> None:
        super().__init__()
        self.rejection_count = rejection_count
        self.summary_sizes: list[int] = []
        self.final_context: dict[str, object] | None = None

    def generate_direct_hypothesis(self, snapshot):
        self.hypothesis_calls += 1
        summary = snapshot.structured_context.get("hypothesis_rejection_summary")
        if self.hypothesis_calls > 1000 and summary is not None:
            self.summary_sizes.append(len(str(summary)))
        if self.hypothesis_calls <= self.rejection_count:
            raise ProposalValidationError("repeated invalid response")
        self.final_context = snapshot.structured_context
        return self.hypothesis


def test_fresh_sibling_h_does_not_use_rejection_as_repair_steering() -> None:
    pipeline, fresh_branch, runtime, _balance = _pipeline()
    pipeline.step_history.append(
        StepRecord(
            round_num=1,
            branch_id="rejected-sibling",
            hypothesis=HypothesisProposal(
                hypothesis_text="Rejected mechanism",
                change_locus="local_search",
                action="modify",
                target_file="operators/local_search.py",
            ),
            patch=None,
            contract_passed=True,
            verification_passed=False,
            protocol_result=None,
            decision=None,
            failure_stage="verification",
            failure_detail="V5_solution_consistency",
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="VERIFICATION_HEAVY_REJECTED",
                detail="FORBIDDEN_PROVIDER_PROSE",
                provenance={
                    "stage": "verification",
                    "verification_checks": [
                        {
                            "name": "V5_solution_consistency",
                            "passed": False,
                            "detail": "FORBIDDEN_RAW_TRACEBACK",
                            "metadata": {
                                "failing_symbol": "_SimulatedAnnealing.cool",
                                "callsite": (
                                    "policies/baseline_modules/scheduler.py:229"
                                ),
                            },
                        }
                    ],
                },
            ),
        )
    )

    attempt = pipeline.generate_hypothesis(fresh_branch)

    assert isinstance(attempt.proposal, HypothesisProposal)
    assert attempt.execution_outcome is None
    assert fresh_branch.branch_id != "rejected-sibling"
    assert "last_research_rejection" not in runtime.hypothesis_kwargs
    assert pipeline.step_history[-1].execution_outcome is not None
    assert (
        pipeline.step_history[-1].execution_outcome.outcome
        is ExecutionOutcome.RESEARCH_REJECTED
    )


def test_normal_h_c_path_passes_same_proposal_and_calls_each_provider_once() -> None:
    creative = FakeCreative()
    pipeline, branch, runtime, _balance = _pipeline(creative=creative)

    hypothesis_attempt = pipeline.generate_hypothesis(branch)
    hypothesis = hypothesis_attempt.proposal
    assert hypothesis is not None
    patch_attempt = pipeline.generate_code(branch, hypothesis)

    assert patch_attempt.proposal is not None
    assert patch_attempt.execution_outcome is None
    assert creative.hypothesis_calls == 1
    assert creative.code_calls == 1
    assert runtime.code_kwargs["hypothesis"] is hypothesis


def test_each_h_call_returns_one_typed_success_attempt() -> None:
    pipeline, branch, _runtime, _balance = _pipeline()

    first_h = pipeline.generate_hypothesis(branch)
    second_h = pipeline.generate_hypothesis(branch)

    assert isinstance(first_h.proposal, HypothesisProposal)
    assert first_h.execution_outcome is None
    assert isinstance(second_h.proposal, HypothesisProposal)
    assert second_h.execution_outcome is None


def test_next_h_sees_only_sanitized_terminal_rejection_enum() -> None:
    creative = _HypothesisSequenceCreative(
        [ProposalValidationError("invalid research basis: UNTRUSTED_DETAIL"), None]
    )
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)

    rejected = pipeline.generate_hypothesis(branch)
    accepted = pipeline.generate_hypothesis(branch)

    assert rejected.proposal is None
    assert rejected.execution_outcome is not None
    assert rejected.execution_outcome.reason_code == "HYPOTHESIS_PROPOSAL_INVALID"
    assert accepted.proposal is creative.hypothesis
    assert "hypothesis_rejection_summary" not in creative.hypothesis_contexts[0]
    assert creative.hypothesis_contexts[1]["hypothesis_rejection_summary"] == {
        "reason_counts": {"HYPOTHESIS_PROPOSAL_INVALID": 1},
        "last_reason": "HYPOTHESIS_PROPOSAL_INVALID",
    }
    assert "UNTRUSTED_DETAIL" not in str(creative.hypothesis_contexts[1])


def test_h_rejection_summary_aggregates_repeated_reason_counts() -> None:
    creative = _HypothesisSequenceCreative(
        [
            ProposalValidationError("first invalid response"),
            ProposalValidationError("second invalid response"),
            None,
        ]
    )
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)

    pipeline.generate_hypothesis(branch)
    pipeline.generate_hypothesis(branch)
    accepted = pipeline.generate_hypothesis(branch)

    assert accepted.proposal is creative.hypothesis
    assert creative.hypothesis_contexts[2]["hypothesis_rejection_summary"] == {
        "reason_counts": {"HYPOTHESIS_PROPOSAL_INVALID": 2},
        "last_reason": "HYPOTHESIS_PROPOSAL_INVALID",
    }


def test_thousand_repeated_h_rejections_keep_fixed_summary_shape() -> None:
    creative = _ManyRejectionsCreative(rejection_count=1001)
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)

    for _ in range(1001):
        rejected = pipeline.generate_hypothesis(branch)
        assert rejected.execution_outcome is not None
    accepted = pipeline.generate_hypothesis(branch)

    assert accepted.proposal is creative.hypothesis
    assert pipeline._hypothesis_rejection_counts == {"HYPOTHESIS_PROPOSAL_INVALID": 99}
    assert creative.final_context is not None
    summary = creative.final_context["hypothesis_rejection_summary"]
    assert summary == {
        "reason_counts": {"HYPOTHESIS_PROPOSAL_INVALID": 99},
        "last_reason": "HYPOTHESIS_PROPOSAL_INVALID",
    }
    assert len(pipeline._hypothesis_rejection_counts) == 1
    assert len(creative.summary_sizes) == 2
    assert creative.summary_sizes[0] == creative.summary_sizes[1]


def test_h_rejection_summary_is_not_reloaded_by_a_new_pipeline() -> None:
    rejected_creative = _HypothesisSequenceCreative(
        [ProposalValidationError("invalid research basis")]
    )
    first_pipeline, first_branch, _runtime, _balance = _pipeline(
        creative=rejected_creative
    )
    first_pipeline.generate_hypothesis(first_branch)

    fresh_creative = _HypothesisSequenceCreative([None])
    fresh_pipeline, fresh_branch, _runtime, _balance = _pipeline(
        creative=fresh_creative
    )
    accepted = fresh_pipeline.generate_hypothesis(fresh_branch)

    assert accepted.proposal is fresh_creative.hypothesis
    assert "hypothesis_rejection_summary" not in fresh_creative.hypothesis_contexts[0]


def test_next_bounded_h_sees_sanitized_abstention() -> None:
    creative = _AbstainingResearchCreative()
    pipeline, branch, runtime, _balance = _pipeline(creative=creative)
    runtime.hypothesis_research_public_sources = lambda: ()
    runtime.hypothesis_research_source_prefixes = lambda: ()
    pipeline.code_research_limits = CodeResearchLimits(max_turns=1)

    first = pipeline.generate_hypothesis(branch)
    second = pipeline.generate_hypothesis(branch)

    assert first.execution_outcome is not None
    assert first.execution_outcome.reason_code == "HYPOTHESIS_RESEARCH_ABSTAINED"
    assert second.execution_outcome is not None
    assert creative.hypothesis_contexts[1]["hypothesis_rejection_summary"] == {
        "reason_counts": {"HYPOTHESIS_RESEARCH_ABSTAINED": 1},
        "last_reason": "HYPOTHESIS_RESEARCH_ABSTAINED",
    }
    assert "UNTRUSTED_DETAIL" not in str(creative.hypothesis_contexts[1])


@pytest.mark.parametrize(
    ("error", "reason_code"),
    [
        (
            ProposalValidationError(
                "transcript exceeds max_transcript_chars before dispatch"
            ),
            "HYPOTHESIS_RESEARCH_TRANSCRIPT_EXHAUSTED",
        ),
        (
            ProposalValidationError("turn cap exhausted without finalize"),
            "HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED",
        ),
        (
            ProposalValidationError("tool results exceed limit"),
            "HYPOTHESIS_RESEARCH_RESULT_CAP_EXHAUSTED",
        ),
    ],
)
def test_h_research_limits_are_terminal_resources_not_observations(
    error: Exception,
    reason_code: str,
) -> None:
    creative = _HypothesisSequenceCreative([error, None])
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)

    exhausted = pipeline.generate_hypothesis(branch)
    manual_followup = pipeline.generate_hypothesis(branch)

    assert exhausted.execution_outcome is not None
    assert exhausted.execution_outcome.outcome is ExecutionOutcome.RESOURCE_EXHAUSTED
    assert exhausted.execution_outcome.reason_code == reason_code
    assert manual_followup.proposal is creative.hypothesis
    assert "hypothesis_rejection_summary" not in creative.hypothesis_contexts[1]


def test_bounded_h_transcript_exhaustion_stops_before_provider_dispatch() -> None:
    creative = _AbstainingResearchCreative()
    pipeline, branch, runtime, _balance = _pipeline(creative=creative)
    original_builder = runtime.build_hypothesis_context
    paths = [f"operators/item_{index:04d}.py" for index in range(200)]

    def build_large_context(**kwargs):
        context = original_builder(**kwargs)
        context["existing_target_files"] = paths
        context["champion_operators_code"] = "\n\n".join(
            f"### {path}\n```python\ndef item():\n    return 1\n```" for path in paths
        )
        return context

    runtime.build_hypothesis_context = build_large_context
    runtime.hypothesis_research_public_sources = lambda: ()
    runtime.hypothesis_research_source_prefixes = lambda: ()
    pipeline.code_research_limits = CodeResearchLimits(
        max_turns=1,
        max_transcript_chars=2_000,
    )

    exhausted = pipeline.generate_hypothesis(branch)

    assert exhausted.execution_outcome is not None
    assert exhausted.execution_outcome.outcome is ExecutionOutcome.RESOURCE_EXHAUSTED
    assert exhausted.execution_outcome.reason_code == (
        "HYPOTHESIS_RESEARCH_TRANSCRIPT_EXHAUSTED"
    )
    assert creative.hypothesis_contexts == []
    assert pipeline._hypothesis_rejection_counts == {}


@pytest.mark.parametrize(
    "error",
    [
        ProviderCallCapExhausted(
            cap=1,
            used=1,
            request_kind="hypothesis_research_turn",
        ),
        LLMTransportError("UNTRUSTED_INFRA_DETAIL"),
    ],
    ids=("resource", "infra"),
)
def test_resource_and_infra_failures_do_not_enter_h_research_observations(
    error: Exception,
) -> None:
    creative = _HypothesisSequenceCreative([error, None])
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)

    rejected = pipeline.generate_hypothesis(branch)
    accepted = pipeline.generate_hypothesis(branch)

    assert rejected.execution_outcome is not None
    assert rejected.execution_outcome.outcome in {
        ExecutionOutcome.BLOCKED_INFRA,
        ExecutionOutcome.RESOURCE_EXHAUSTED,
    }
    assert accepted.proposal is creative.hypothesis
    assert "hypothesis_rejection_summary" not in creative.hypothesis_contexts[1]


def test_not_evaluated_context_failure_does_not_enter_h_observations() -> None:
    creative = _HypothesisSequenceCreative([None])
    pipeline, branch, runtime, _balance = _pipeline(creative=creative)
    original_builder = runtime.build_hypothesis_context
    first = True

    def build_context(**kwargs):
        nonlocal first
        context = original_builder(**kwargs)
        if first:
            first = False
            context["unsupported_context_value"] = "UNTRUSTED_CONTEXT_DETAIL"
        return context

    runtime.build_hypothesis_context = build_context

    rejected = pipeline.generate_hypothesis(branch)
    accepted = pipeline.generate_hypothesis(branch)

    assert rejected.execution_outcome is not None
    assert rejected.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED
    assert accepted.proposal is creative.hypothesis
    assert "hypothesis_rejection_summary" not in creative.hypothesis_contexts[0]


def test_problem_runtime_cannot_spoof_pipeline_owned_h_rejection_summary() -> None:
    creative = _HypothesisSequenceCreative([None])
    pipeline, branch, runtime, _balance = _pipeline(creative=creative)
    original_builder = runtime.build_hypothesis_context

    def build_spoofed_context(**kwargs):
        context = original_builder(**kwargs)
        context["hypothesis_rejection_summary"] = {
            "reason_counts": {"UNTRUSTED_REASON": 1},
            "last_reason": "UNTRUSTED_DETAIL",
        }
        return context

    runtime.build_hypothesis_context = build_spoofed_context

    rejected = pipeline.generate_hypothesis(branch)

    assert rejected.execution_outcome is not None
    assert rejected.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED
    assert creative.hypothesis_contexts == []


def test_h_enters_one_direct_code_call() -> None:
    creative = FakeCreative()
    pipeline, branch, runtime, _balance = _pipeline(creative=creative)
    hypothesis = pipeline.generate_hypothesis(branch).proposal
    assert hypothesis is not None

    code_attempt = pipeline.generate_code(branch, hypothesis)
    assert code_attempt.proposal is not None
    assert code_attempt.execution_outcome is None
    assert creative.code_calls == 1
    assert runtime.code_kwargs["hypothesis"] is hypothesis


def test_h_rejection_summary_does_not_enter_code_context() -> None:
    creative = _HypothesisSequenceCreative(
        [ProposalValidationError("invalid research basis"), None]
    )
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)
    pipeline.generate_hypothesis(branch)
    hypothesis = pipeline.generate_hypothesis(branch).proposal
    assert hypothesis is not None

    code_attempt = pipeline.generate_code(branch, hypothesis)

    assert code_attempt.proposal is creative.patch
    assert creative.code_context is not None
    assert "hypothesis_rejection_summary" not in creative.code_context


def test_code_generation_uses_the_supplied_proposal_directly() -> None:
    creative = FakeCreative()
    pipeline, branch, runtime, _balance = _pipeline(creative=creative)
    hypothesis = pipeline.generate_hypothesis(branch).proposal
    assert hypothesis is not None
    changed = HypothesisProposal(
        **{
            **hypothesis.__dict__,
            "hypothesis_text": "Use a different unapproved mechanism.",
        }
    )

    code_attempt = pipeline.generate_code(branch, changed)
    assert code_attempt.proposal is not None
    assert code_attempt.execution_outcome is None
    assert creative.code_calls == 1
    assert runtime.code_kwargs["hypothesis"] is changed


@pytest.mark.parametrize(
    "error",
    [
        LLMFormatError("invalid patch payload"),
        ProposalValidationError("old_string_not_found in operators/bounded.py"),
    ],
    ids=("provider-format", "proposal-validation"),
)
def test_invalid_code_response_is_research_rejected_after_one_call(
    error: Exception,
) -> None:
    creative = FakeCreative(code_error=error)
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)
    hypothesis = pipeline.generate_hypothesis(branch).proposal
    assert hypothesis is not None

    code_attempt = pipeline.generate_code(branch, hypothesis)
    assert code_attempt.proposal is None
    assert creative.code_calls == 1
    outcome = code_attempt.execution_outcome
    assert outcome is not None
    assert outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
    assert branch.state is not BranchState.BLOCKED_INFRA
    if isinstance(error, ProposalValidationError):
        assert outcome.reason_code == "PATCH_PROPOSAL_INVALID"
    else:
        assert outcome.reason_code == "PROPOSAL_RESPONSE_INVALID"


def test_keyboard_interrupt_propagates_without_a_side_channel_outcome() -> None:
    creative = FakeCreative(code_error=KeyboardInterrupt("operator stop"))  # type: ignore[arg-type]
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)
    hypothesis = pipeline.generate_hypothesis(branch).proposal
    assert hypothesis is not None

    with pytest.raises(KeyboardInterrupt, match="operator stop"):
        pipeline.generate_code(branch, hypothesis)

    assert not hasattr(pipeline, "_execution_outcomes")
