"""Focused tests split from test_campaign.py."""

from .campaign_test_support import *  # noqa: F401,F403

class TestCodeFailureRetry:
    """Tests for T20: hypothesis preserved on code gen failure and retried next round."""

    def _make_fail_then_succeed_llm(self):
        """LLM that fails the first code gen call but succeeds on retry."""
        from scion.proposal.llm_client import LLMRetryExhaustedError

        class _LLM:
            def __init__(self):
                self._code_calls = 0

            def call(self, prompt, schema, model=None, system_blocks=None):
                required = set(schema.get("required", []))
                if "hypothesis_text" in required or "change_locus" in required:
                    return dict(_VALID_HYPOTHESIS)
                self._code_calls += 1
                if self._code_calls == 1:
                    raise LLMRetryExhaustedError("simulated code gen failure")
                return dict(_VALID_PATCH)

            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        return _LLM()

    def _make_always_fail_code_llm(self):
        """LLM that always fails code gen calls."""
        from scion.proposal.llm_client import LLMRetryExhaustedError

        class _LLM:
            def call(self, prompt, schema, model=None, system_blocks=None):
                required = set(schema.get("required", []))
                if "hypothesis_text" in required or "change_locus" in required:
                    return dict(_VALID_HYPOTHESIS)
                raise LLMRetryExhaustedError("simulated code gen failure")

            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        return _LLM()

    def test_code_failure_triggers_retry_next_round(self, tmp_path):
        """Code gen failure adds hypothesis to pending; next round reuses it."""
        llm = self._make_fail_then_succeed_llm()
        cm = _campaign(
            tmp_path,
            llm_client=llm,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )

        # Step 1: creates branch, hypothesis succeeds, code gen fails
        r1 = cm.run_one_step()
        assert r1.branch_id is not None
        bid = r1.branch_id
        # The hypothesis should now be in pending (not discarded)
        assert bid in cm._pending_hypotheses, "hypothesis should be queued for retry"
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.pending_retry is True

        # Step 2: retries code gen with pending hypothesis — should succeed
        r2 = cm.run_one_step()
        assert r2.branch_id == bid
        # Pending entry consumed
        assert bid not in cm._pending_hypotheses, "pending hypothesis should be cleared on success"
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.pending_retry is False
        assert branch.consecutive_llm_retries == 0
        # Step 2 produced a valid decision (not just a failure skip)
        assert r2.decision is not None

    def test_code_retry_failure_marks_rejected(self, tmp_path):
        """Two consecutive code gen failures → hypothesis marked rejected, no more pending."""
        llm = self._make_always_fail_code_llm()
        cm = _campaign(tmp_path, llm_client=llm)

        # Step 1: code gen fails for the first time → pending
        r1 = cm.run_one_step()
        bid = r1.branch_id
        assert bid in cm._pending_hypotheses, "hypothesis should be queued after first failure"

        # Step 2: retry also fails → hypothesis rejected, no longer pending
        r2 = cm.run_one_step()
        assert r2.branch_id == bid
        assert bid not in cm._pending_hypotheses, "hypothesis must not be re-queued after retry failure"
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.pending_retry is False
        assert branch.consecutive_llm_retries == 0

        # The step history should reflect both failures
        code_fail_steps = [
            s for s in cm._step_history
            if s.branch_id == bid and s.failure_stage == "code_generation"
        ]
        assert len(code_fail_steps) == 2, "both attempts should be recorded in step history"

        # Second record should note it was the retry
        assert "retry" in (code_fail_steps[1].failure_detail or "").lower(), \
            "second failure detail should mention 'retry'"

    def test_code_retry_includes_failure_context(self, tmp_path):
        """On retry, build_code_context receives the prior failure detail."""
        from scion.proposal.context_manager import ContextManager

        captured_contexts = []
        original_build = ContextManager.build_code_context

        def capturing_build(self_ctx, branch, hypothesis, champion, problem_spec,
                            prior_failure=None):
            ctx = original_build(self_ctx, branch=branch, hypothesis=hypothesis,
                                 champion=champion, problem_spec=problem_spec,
                                 prior_failure=prior_failure)
            captured_contexts.append(ctx)
            return ctx

        llm = self._make_fail_then_succeed_llm()
        cm = _campaign(
            tmp_path,
            llm_client=llm,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        cm._ctx_manager.build_code_context = lambda **kw: capturing_build(
            cm._ctx_manager, **kw
        )

        cm.run_one_step()  # step 1: code gen fails
        cm.run_one_step()  # step 2: retry

        assert len(captured_contexts) >= 2, "build_code_context must be called for both attempts"
        # First attempt: no prior failure context
        assert "prior_code_failure" not in captured_contexts[0], \
            "first attempt must not have prior_code_failure"
        # Retry attempt: prior failure context present
        assert "prior_code_failure" in captured_contexts[1], \
            "retry attempt must include prior_code_failure in context"

    def test_successful_code_clears_pending(self, tmp_path):
        """A successful code gen round leaves no pending hypothesis."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        result = cm.run_one_step()
        assert result.branch_id is not None
        assert result.branch_id not in cm._pending_hypotheses, \
            "successful round must not leave a pending hypothesis"


class TestNoFakeHypothesisRecordFallback:
    def test_missing_canonical_record_raises_and_abandons(self, tmp_path):
        """If canonical h_record is absent when eval step runs, the branch is abandoned."""
        protocol = MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)]
        )
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        # Drive branch to EXPLORE → READY_VALIDATE (screening pass)
        r1 = cm.run_one_step()
        bid = r1.branch_id
        assert bid is not None

        # Manually delete the canonical hypothesis record to simulate the lost-record scenario
        cm._branch_current_hypothesis.pop(bid, None)
        budget_used_before = cm._budget.used

        # Run next step — the campaign will schedule READY_VALIDATE → VALIDATING
        # and call _run_eval_step, which should raise RuntimeError and abandon the branch
        result = cm.run_one_step()
        assert result.branch_id == bid

        from scion.core.models import BranchState
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state == BranchState.ABANDONED, (
            f"Expected ABANDONED but got {branch.state}; result={result}"
        )
        assert protocol.canary_call_count == 1
        assert protocol.experiment_call_count == 1
        assert cm._budget.used == budget_used_before
