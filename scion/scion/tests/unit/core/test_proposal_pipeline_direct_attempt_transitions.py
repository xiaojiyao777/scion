"""Focused direct-V3 proposal-call behavior without attempt identities."""

from __future__ import annotations

import pytest
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import BranchState, HypothesisProposal, StepRecord
from scion.proposal.engine import ProposalValidationError
from scion.proposal.llm_client import LLMFormatError

from .proposal_pipeline_test_support import FakeCreative, _pipeline


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
