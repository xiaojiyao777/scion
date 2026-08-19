"""Focused tests split from test_campaign.py."""

import json
import sqlite3
from dataclasses import replace

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import BranchState
from scion.core.scheduler import Scheduler

from .campaign_test_support import *


class TestCodeFailureDirect:
    """Malformed proposal content ends one H/C and schedules a fresh H."""

    def _make_invalid_patch_then_succeed_llm(self):
        """Return one source-invalid C, then a valid C after a fresh H."""

        class _LLM:
            def __init__(self):
                self._code_calls = 0
                self.request_kinds = []

            def call(self, prompt, schema, model=None, system_blocks=None):
                required = set(schema.get("required", []))
                if "hypothesis_text" in required or "change_locus" in required:
                    return dict(_VALID_HYPOTHESIS)
                self._code_calls += 1
                if self._code_calls == 1:
                    return {
                        **_VALID_PATCH,
                        "old_string": "this source text is not present\n",
                    }
                return dict(_VALID_PATCH)

            def call_with_tool(
                self,
                prompt,
                tool,
                model=None,
                system_blocks=None,
                request_kind=None,
            ):
                self.request_kinds.append(request_kind)
                return self.call(
                    prompt, tool.get("input_schema", {}), model, system_blocks
                )

        return _LLM()

    def test_source_invalid_code_rejects_h_then_next_tick_starts_fresh_h_c(
        self,
        tmp_path,
    ):
        """A rejected C is never retried; a new scheduler tick starts at H."""
        llm = self._make_invalid_patch_then_succeed_llm()
        cm = _campaign(
            tmp_path,
            llm_client=llm,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        cm._scheduler = Scheduler(max_active_branches=1)
        cm._branch_step_runner.scheduler = cm._scheduler

        r1 = cm.run_one_step()
        assert r1.branch_id is not None
        bid = r1.branch_id
        assert r1.execution_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert r1.execution_outcome.reason_code == "PROPOSAL_RESPONSE_INVALID"
        assert not hasattr(r1, "attempt_disposition")
        assert r1.decision is None
        durable = cm._registry.query_execution_outcomes(branch_id=bid)
        assert len(durable) == 1
        assert durable[0]["outcome"] == "research_rejected"
        assert cm._branch_ctrl.get_branch(bid).state is not BranchState.BLOCKED_INFRA
        assert cm._branch_ctrl.get_branch(bid).hypothesis is None
        assert bid not in cm._branch_patches
        step = cm._step_history[-1]
        assert step.failure_stage == "proposal_code"
        assert step.hypothesis.hypothesis_text == (_VALID_HYPOTHESIS["hypothesis_text"])
        with sqlite3.connect(tmp_path / "campaign" / "scion.db") as conn:
            rejection = conn.execute(
                "SELECT execution_outcome_provenance_json FROM experiment_events "
                "WHERE event_kind = 'research_rejection'"
            ).fetchone()
        assert rejection is not None
        assert json.loads(rejection[0])["stage"] == "proposal_code"

        r2 = cm.run_one_step()

        assert r2.branch_id == bid
        assert r2.execution_outcome.outcome is ExecutionOutcome.EVALUATED
        assert llm.request_kinds == ["hypothesis", "code", "hypothesis", "code"]
        attempt_events = [
            event
            for event in cm._registry.query_by_branch(bid)
            if event["event_kind"] == "experiment"
            or event["execution_outcome"] is not None
        ]
        assert [event["event_kind"] for event in reversed(attempt_events)] == [
            "research_rejection",
            "experiment",
        ]
        assert attempt_events[0]["execution_outcome"] is None
        with sqlite3.connect(tmp_path / "campaign" / "scion.db") as conn:
            proposal_call_count = conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE event_kind = 'proposal_call'"
            ).fetchone()[0]
        assert proposal_call_count == 0

    def test_next_tick_does_not_build_code_continuation_context(self, tmp_path):
        """No prior code failure is injected into a hidden continuation."""
        from scion.proposal.context_manager import ContextManager

        captured_contexts = []
        original_build = ContextManager.build_code_context

        def capturing_build(
            self_ctx,
            branch,
            hypothesis,
            champion,
            problem_spec,
            branch_workspace=None,
            step_history=None,
            development_suites=(),
        ):
            ctx = original_build(
                self_ctx,
                branch=branch,
                hypothesis=hypothesis,
                champion=champion,
                problem_spec=problem_spec,
                branch_workspace=branch_workspace,
                step_history=step_history,
                development_suites=development_suites,
            )
            captured_contexts.append(ctx)
            return ctx

        llm = self._make_invalid_patch_then_succeed_llm()
        cm = _campaign(
            tmp_path,
            llm_client=llm,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        context_manager = cm._problem_runtime.ctx_manager
        context_manager.build_code_context = lambda **kw: capturing_build(
            context_manager, **kw
        )

        cm.run_one_step()
        assert captured_contexts
        assert all("prior_code_failure" not in context for context in captured_contexts)

        cm.run_one_step()
        assert llm.request_kinds == ["hypothesis", "code", "hypothesis", "code"]
        assert captured_contexts
        assert all("prior_code_failure" not in context for context in captured_contexts)

    def test_changed_h_input_is_an_ordinary_invalid_response_rejection(self, tmp_path):
        """There is no durable H-binding lookup outside direct response validation."""
        llm = self._make_invalid_patch_then_succeed_llm()
        cm = _campaign(tmp_path, llm_client=llm)

        def generate_changed_code(branch, hypothesis):
            changed = replace(
                hypothesis,
                hypothesis_text="different from the Contract-approved H",
            )
            return cm._proposal_pipeline.generate_code(branch, changed)

        cm._explore_step_pipeline.generate_code = generate_changed_code

        result = cm.run_one_step()

        assert result.execution_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert result.execution_outcome.reason_code == "PROPOSAL_RESPONSE_INVALID"
        assert "APPROVED_HYPOTHESIS_BINDING_MISSING" not in (
            result.execution_outcome.reason_code,
            *result.execution_outcome.provenance.values(),
        )
        assert llm.request_kinds == ["hypothesis", "code"]
        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert branch.state is not BranchState.BLOCKED_INFRA
        assert branch.hypothesis is None

    def test_successful_code_reaches_evaluation(self, tmp_path):
        """A successful direct H/C path reaches formal evaluation."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        result = cm.run_one_step()
        assert result.branch_id is not None
        assert result.execution_outcome.outcome is ExecutionOutcome.EVALUATED


def test_provider_auth_failure_blocks_branch_with_one_typed_outcome(tmp_path):
    from scion.proposal.llm_client import LLMAuthError

    class AuthFailureLLM:
        def call_with_tool(self, *_args, **_kwargs):
            raise LLMAuthError("invalid provider credentials")

    cm = _campaign(tmp_path, llm_client=AuthFailureLLM())

    result = cm.run_one_step()

    assert result.branch_id is not None
    record = result.execution_outcome
    assert record is not None
    assert record.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert record.reason_code == "PROVIDER_CALL_BLOCKED_INFRA"
    assert record.provenance["stage"] == "proposal_hypothesis"
    assert result.failure_stage == "proposal_hypothesis"
    assert result.failure_category == ExecutionOutcome.BLOCKED_INFRA.value
    assert result.decision is None
    assert result.protocol_result is None
    branch = cm._branch_ctrl.get_branch(result.branch_id)
    assert branch.state == BranchState.BLOCKED_INFRA
    outcomes = cm._registry.query_execution_outcomes(branch_id=result.branch_id)
    assert len(outcomes) == 1
    assert outcomes[0]["event_kind"] == "proposal_execution_outcome"
    assert outcomes[0]["stage"] == "proposal_hypothesis"
    assert outcomes[0]["outcome"] == ExecutionOutcome.BLOCKED_INFRA.value
    assert outcomes[0]["reason_code"] == "PROVIDER_CALL_BLOCKED_INFRA"
    assert cm._step_history == []


class TestMissingOrdinaryHypothesis:
    def test_missing_branch_hypothesis_is_a_typed_non_evaluation(self, tmp_path):
        """Evaluation cannot synthesize a hypothesis absent from branch state."""
        protocol = MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)]
        )
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        # Drive branch to EXPLORE → READY_VALIDATE (screening pass)
        r1 = cm.run_one_step()
        bid = r1.branch_id
        assert bid is not None

        branch = cm._branch_ctrl.get_branch(bid)
        branch.hypothesis = None

        # Run next step — the campaign will schedule READY_VALIDATE → VALIDATING
        # and call _run_eval_step, which must stop without synthesizing ABANDON.
        result = cm.run_one_step()
        assert result.branch_id == bid

        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state is BranchState.BLOCKED_INFRA
        assert result.decision is None
        assert result.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED
        assert result.execution_outcome.reason_code == "EVAL_HYPOTHESIS_MISSING"
        assert "EVAL_HYPOTHESIS_MISSING" in branch.failure_codes
        assert protocol.canary_call_count == 1
        assert protocol.experiment_call_count == 1


class TestProviderFailClosedTerminals:
    @staticmethod
    def _assert_blocked_once(cm, branch_id, reason_code):
        branch = cm._branch_ctrl.get_branch(branch_id)
        assert branch.state is BranchState.BLOCKED_INFRA
        outcomes = cm._registry.query_execution_outcomes(branch_id=branch_id)
        assert len(outcomes) == 1
        assert outcomes[0]["event_kind"] == "proposal_execution_outcome"
        assert outcomes[0]["reason_code"] == reason_code

    def test_unexpected_provider_exception_returns_one_typed_terminal(self, tmp_path):
        class UnexpectedFailureLLM:
            def call_with_tool(self, *_args, **_kwargs):
                raise RuntimeError("unexpected provider failure")

        cm = _campaign(tmp_path, llm_client=UnexpectedFailureLLM())
        result = cm.run_one_step()

        assert result.branch_id is not None
        assert result.execution_outcome is not None
        assert result.execution_outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
        assert result.execution_outcome.reason_code == "PROPOSAL_UNEXPECTED_FAILURE"
        assert result.decision is None
        assert result.protocol_result is None
        assert cm._step_history == []
        self._assert_blocked_once(
            cm,
            result.branch_id,
            "PROPOSAL_UNEXPECTED_FAILURE",
        )

    def test_keyboard_interrupt_reaches_outer_terminal_without_step_event(
        self,
        tmp_path,
    ):
        class InterruptedLLM:
            def call_with_tool(self, *_args, **_kwargs):
                raise KeyboardInterrupt()

        cm = _campaign(tmp_path, llm_client=InterruptedLLM())

        with pytest.raises(KeyboardInterrupt):
            cm.run_one_step()

        branches = cm._branch_ctrl.get_reportable_branches()
        assert len(branches) == 1
        branch = branches[0]
        assert branch.state is BranchState.EXPLORE
        assert cm._registry.query_execution_outcomes(branch_id=branch.branch_id) == []

    def test_code_interrupt_reaches_outer_terminal_without_step_event(self, tmp_path):
        class CodeInterruptedLLM(MockLLMClient):
            def call_with_tool(self, *args, request_kind=None, **kwargs):
                if request_kind == "code":
                    raise KeyboardInterrupt()
                return super().call_with_tool(
                    *args,
                    request_kind=request_kind,
                    **kwargs,
                )

        cm = _campaign(tmp_path, llm_client=CodeInterruptedLLM())

        with pytest.raises(KeyboardInterrupt):
            cm.run_one_step()

        branches = cm._branch_ctrl.get_reportable_branches()
        assert len(branches) == 1
        branch = branches[0]
        assert branch.state is BranchState.EXPLORE
        assert cm._registry.query_execution_outcomes(branch_id=branch.branch_id) == []
        assert branch.hypothesis is None
