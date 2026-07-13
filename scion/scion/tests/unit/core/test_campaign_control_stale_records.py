"""Focused tests split from test_campaign_control_boundaries.py."""

from .campaign_control_boundaries_test_support import *  # noqa: F401,F403
from scion.core.execution_outcome import ExecutionOutcome



class TestContractFailStepRecord:
    def test_contract_fail_step_record_has_no_decision(self, tmp_path):
        """StepRecord.decision must be None (not ABANDON) for contract failures."""
        cm = _campaign(tmp_path)

        # Make validate_hypothesis always fail
        cm._contract_gate.validate_hypothesis = lambda hyp, *, governance_envelope=None: ContractResult(
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

    def test_hypothesis_proposal_failure_writes_step_record(self, tmp_path):
        """Round-1 LLM/schema failures must appear in step history and summaries."""
        cm = _campaign(tmp_path, llm_client=MockLLMClient(mode="format_error"))

        result = cm.run_one_step()

        proposal_steps = [
            s for s in cm._step_history
            if s.failure_stage == "proposal_hypothesis"
        ]
        assert result.reason == "MockLLMClient: simulated format error"
        assert proposal_steps, "proposal failure should write a StepRecord"
        step = proposal_steps[0]
        assert step.round_num == 1
        assert step.decision is None
        assert step.protocol_result is None
        assert "simulated format error" in (step.failure_detail or "")
        assert step.hypothesis.change_locus == "proposal"
        events = cm._registry.query_by_branch(result.branch_id)
        assert any(
            e.get("event_kind") == "proposal_execution_outcome"
            for e in events
        )
