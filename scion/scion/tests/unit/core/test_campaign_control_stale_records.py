"""Focused tests split from test_campaign_control_boundaries.py."""

from .campaign_control_boundaries_test_support import *  # noqa: F401,F403
from scion.core.execution_outcome import ExecutionOutcome


class TestContractFailStepRecord:
    def test_contract_fail_step_record_has_no_decision(self, tmp_path):
        """StepRecord.decision must be None (not ABANDON) for contract failures."""
        cm = _campaign(tmp_path)

        # Make validate_hypothesis always fail
        cm._contract_gate.validate_hypothesis = lambda hyp, **_kwargs: ContractResult(
            passed=False, checks=(), failure_reason="forced contract failure"
        )

        cm.run_one_step()

        contract_fail_steps = [
            s for s in cm._step_history
            if s.failure_stage == "hypothesis_contract"
        ]
        assert contract_fail_steps, "should have a hypothesis_contract failure step"
        for step in contract_fail_steps:
            assert step.decision is None, (
                f"StepRecord.decision should be None for contract failure, "
                f"but got {step.decision!r}"
            )

    def test_hypothesis_proposal_failure_has_redacted_attempt_record(self, tmp_path):
        """A failed H call is durable without a fabricated scientific H."""
        cm = _campaign(tmp_path, llm_client=MockLLMClient(mode="format_error"))

        result = cm.run_one_step()

        assert result.reason == "MockLLMClient: simulated format error"
        assert result.failure_stage == "proposal_hypothesis"
        assert result.execution_outcome is not None
        assert len(cm._step_history) == 1
        step = cm._step_history[0]
        assert step.hypothesis is None
        assert step.failure_stage == "proposal_hypothesis"
        assert step.failure_detail == result.execution_outcome.reason_code
        assert step.execution_outcome.detail == ""
        assert step.execution_outcome.provenance == {
            "stage": "proposal_hypothesis"
        }
        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert branch.state is not BranchState.BLOCKED_INFRA
        events = cm._registry.query_by_branch(result.branch_id)
        outcomes = [
            event
            for event in events
            if event.get("event_kind") == "proposal_execution_outcome"
        ]
        assert len(outcomes) == 1
        assert outcomes[0]["execution_outcome"] == (
            ExecutionOutcome.RESEARCH_REJECTED.value
        )
