"""Focused tests split from test_campaign.py."""

import json
import sqlite3
from dataclasses import replace

from scion.cli.commands.init_run import _completion_from_run_result
from scion.core.execution_outcome import (
    PROVIDER_TRANSIENT_RETRIES_EXHAUSTED,
    ExecutionOutcome,
    ExecutionOutcomeRecord,
)
from scion.core.models import BranchState
from scion.core.proposal_pipeline import ProposalAttempt
from scion.core.scheduler import Scheduler
from scion.proposal.llm_client import LLMTransportError

from .campaign_test_support import *


def _assert_canonical_hypothesis_failure_step(cm, *, reason_code):
    assert len(cm._step_history) == 1
    step = cm._step_history[0]
    assert step.hypothesis is None
    assert step.patch is None
    assert step.contract_passed is None
    assert step.verification_passed is None
    assert step.protocol_result is None
    assert step.decision is None
    assert step.failure_stage == "proposal_hypothesis"
    assert step.failure_detail == reason_code
    assert step.execution_outcome is not None
    assert step.execution_outcome.reason_code == reason_code
    assert step.execution_outcome.detail == ""
    assert step.execution_outcome.provenance == {
        "stage": "proposal_hypothesis"
    }


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
        direct_llm = self._make_invalid_patch_then_succeed_llm()
        cm, llm = _bounded_campaign(
            tmp_path,
            llm_client=direct_llm,
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
        assert r1.execution_outcome.reason_code == "PATCH_PROPOSAL_INVALID"
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
        assert llm.request_kinds == [
            "hypothesis_research_turn",
            "hypothesis_research_turn",
            "code_research_turn",
            "code_research_turn",
            "code_research_turn",
            "code_research_finalize",
            "hypothesis_research_turn",
            "hypothesis_research_turn",
            "code_research_turn",
            "code_research_turn",
            "code_research_turn",
        ]
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
        assert attempt_events[0]["execution_outcome"] == "evaluated"
        assert attempt_events[0]["execution_outcome_reason_code"] == (
            "EVALUATION_COMPLETED"
        )
        assert json.loads(
            attempt_events[0]["execution_outcome_provenance_json"]
        ) == {"stage": "screening"}
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

        direct_llm = self._make_invalid_patch_then_succeed_llm()
        cm, llm = _bounded_campaign(
            tmp_path,
            llm_client=direct_llm,
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
        assert llm.request_kinds == [
            "hypothesis_research_turn",
            "hypothesis_research_turn",
            "code_research_turn",
            "code_research_turn",
            "code_research_turn",
            "code_research_finalize",
            "hypothesis_research_turn",
            "hypothesis_research_turn",
            "code_research_turn",
            "code_research_turn",
            "code_research_turn",
        ]
        assert captured_contexts
        assert all("prior_code_failure" not in context for context in captured_contexts)

    def test_changed_h_input_is_a_typed_patch_proposal_rejection(self, tmp_path):
        """There is no durable H-binding lookup outside patch response validation."""
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
        assert result.execution_outcome.reason_code == "PATCH_PROPOSAL_INVALID"
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


@pytest.mark.parametrize(
    "failed_request_kind",
    ["hypothesis", "code"],
)
def test_transient_provider_failure_does_not_stop_campaign_or_pollute_history(
    tmp_path,
    failed_request_kind,
):
    class TransientOnceLLM:
        def __init__(self):
            self.failed = False
            self.request_kinds = []

        def call_with_tool(
            self,
            prompt,
            tool,
            model=None,
            system_blocks=None,
            request_kind=None,
        ):
            del prompt, model, system_blocks
            self.request_kinds.append(request_kind)
            if request_kind == failed_request_kind and not self.failed:
                self.failed = True
                raise LLMTransportError("PRIVATE transient transport detail")
            required = set(tool.get("input_schema", {}).get("required", []))
            if "hypothesis_text" in required or "change_locus" in required:
                return dict(_VALID_HYPOTHESIS)
            return dict(_VALID_PATCH)

    cm = _campaign(
        tmp_path,
        llm_client=TransientOnceLLM(),
        experiment_protocol=MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)]
        ),
    )
    cm._scheduler = Scheduler(max_active_branches=1)
    cm._branch_step_runner.scheduler = cm._scheduler

    terminal = cm.run(requested_rounds=1)

    assert terminal.completed
    assert terminal.stop_reason == "requested_rounds_completed"
    assert terminal.scheduled_calls == 2
    assert terminal.evaluated_rounds == 1
    assert terminal.execution_outcome_counts == {
        "evaluated": 1,
        "research_rejected": 1,
        "not_evaluated": 0,
        "blocked_infra": 0,
        "resource_exhausted": 0,
        "interrupted": 0,
    }
    assert len(cm._step_history) == 2
    first_outcome = cm._step_history[0].execution_outcome
    assert first_outcome is not None
    assert first_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
    assert first_outcome.reason_code == PROVIDER_TRANSIENT_RETRIES_EXHAUSTED
    branch = next(iter(cm._branch_ctrl._branches.values()))
    assert branch.state is not BranchState.BLOCKED_INFRA
    durable = cm._registry.query_execution_outcomes(branch_id=branch.branch_id)
    assert any(
        row["reason_code"] == PROVIDER_TRANSIENT_RETRIES_EXHAUSTED
        and row["outcome"] == ExecutionOutcome.RESEARCH_REJECTED.value
        for row in durable
    )
    history_rows = [
        json.loads(line)
        for line in (tmp_path / "campaign" / "research_history.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(history_rows) == 1
    assert history_rows[0]["outcome"]["outcome"] == "evaluated"
    assert PROVIDER_TRANSIENT_RETRIES_EXHAUSTED not in str(history_rows)
    assert "PRIVATE transient transport detail" not in str(history_rows)


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
    _assert_canonical_hypothesis_failure_step(
        cm,
        reason_code="PROVIDER_CALL_BLOCKED_INFRA",
    )


@pytest.mark.parametrize(
    ("outcome", "reason_code"),
    (
        (ExecutionOutcome.NOT_EVALUATED, "PROPOSAL_CONTEXT_INVALID"),
        (ExecutionOutcome.RESOURCE_EXHAUSTED, "PROVIDER_CALL_CAP_EXHAUSTED"),
    ),
)
def test_every_hypothesis_no_proposal_terminal_has_a_canonical_step(
    tmp_path,
    outcome,
    reason_code,
):
    cm = _campaign(tmp_path)
    cm._explore_step_pipeline.generate_hypothesis = lambda _branch: (
        ProposalAttempt.failure(
            ExecutionOutcomeRecord(
                outcome=outcome,
                reason_code=reason_code,
                detail="RAW_SENTINEL",
                provenance={
                    "stage": "proposal_hypothesis",
                    "exception_type": "RAW_SENTINEL",
                },
            )
        )
    )

    result = cm.run_one_step()

    assert result.execution_outcome.outcome is outcome
    assert result.execution_outcome.reason_code == reason_code
    _assert_canonical_hypothesis_failure_step(cm, reason_code=reason_code)


@pytest.mark.parametrize(
    ("builder_name", "failure_stage"),
    (
        ("build_hypothesis_context", "proposal_hypothesis"),
        ("build_code_context", "proposal_code"),
    ),
)
def test_unexpected_proposal_context_failure_is_typed_and_publicly_redacted(
    tmp_path,
    builder_name,
    failure_stage,
):
    sentinel = "RAW_CONTEXT_SENTINEL H_BASIS_SENTINEL RESERVED_SENTINEL"
    cm = _campaign(tmp_path)

    def fail_context(**_kwargs):
        raise RuntimeError(sentinel)

    setattr(cm._problem_runtime, builder_name, fail_context)

    terminal = cm.run(requested_rounds=1)

    assert terminal.scheduled_calls == 1
    assert terminal.evaluated_rounds == 0
    assert terminal.stop_reason == "execution_blocked_infra"
    assert terminal.execution_outcome_counts["blocked_infra"] == 1
    assert terminal.failure_categories == {"blocked_infra": 1}
    assert _completion_from_run_result(terminal) == (
        20,
        "incomplete_infra_stop:execution_blocked_infra",
    )
    assert terminal.last_execution_outcome == {
        "outcome": "blocked_infra",
        "reason_code": "PROPOSAL_UNEXPECTED_FAILURE",
        "stage": failure_stage,
    }
    state = cm.get_state(run_result=terminal)
    assert state["total_rounds"] == 1
    assert state["n_steps"] == 1
    step = cm._step_history[0]
    assert step.failure_stage == failure_stage
    assert (step.hypothesis is None) == (failure_stage == "proposal_hypothesis")

    campaign_dir = tmp_path / "campaign"
    status = json.loads((campaign_dir / "status.json").read_text(encoding="utf-8"))
    summary = json.loads(
        (campaign_dir / "campaign_summary.json").read_text(encoding="utf-8")
    )
    history_path = campaign_dir / "research_history.jsonl"
    history = (
        json.loads(history_path.read_text(encoding="utf-8"))
        if history_path.exists()
        else None
    )
    assert status["last_result"]["reason"] == "PROPOSAL_UNEXPECTED_FAILURE"
    assert summary["steps"][0]["failure_detail"] == (
        "PROPOSAL_UNEXPECTED_FAILURE"
    )
    assert summary["steps"][0]["execution_outcome"] == {
        "outcome": "blocked_infra",
        "reason_code": "PROPOSAL_UNEXPECTED_FAILURE",
        "detail": "",
        "provenance": {"stage": failure_stage},
    }
    assert history is None
    public_artifacts = json.dumps(
        {"status": status, "summary": summary, "history": history},
        sort_keys=True,
    )
    for marker in (*sentinel.split(), "RuntimeError"):
        assert marker not in public_artifacts


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
        recorded_step_count = len(cm._step_history)
        branch.hypothesis = None

        # Run next step — the campaign will schedule READY_VALIDATE → VALIDATING
        # and call _run_eval_step, which must stop without synthesizing ABANDON.
        result = cm.run_one_step()
        assert result.branch_id == bid

        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state is BranchState.BLOCKED_INFRA
        assert result.action == "validate"
        assert result.decision is None
        assert result.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED
        assert result.execution_outcome.reason_code == "EVAL_HYPOTHESIS_MISSING"
        assert "EVAL_HYPOTHESIS_MISSING" in branch.failure_codes
        assert len(cm._step_history) == recorded_step_count
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
        _assert_canonical_hypothesis_failure_step(
            cm,
            reason_code="PROPOSAL_UNEXPECTED_FAILURE",
        )
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


def test_hypothesis_abstention_is_one_redacted_durable_attempt(tmp_path):
    sentinel = (
        "RAW_SENTINEL H_BASIS_SENTINEL PROBE_SENTINEL RESERVED_SENTINEL"
    )
    cm = _campaign(
        tmp_path,
        experiment_protocol=MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)]
        ),
    )
    generate_hypothesis = cm._explore_step_pipeline.generate_hypothesis
    calls = 0

    def abstain_once(branch):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ProposalAttempt.failure(
                ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.RESEARCH_REJECTED,
                    reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
                    detail=sentinel,
                    provenance={
                        "stage": "proposal_hypothesis",
                        "phase": "hypothesis",
                        "provider_probe": sentinel,
                    },
                )
            )
        return generate_hypothesis(branch)

    cm._explore_step_pipeline.generate_hypothesis = abstain_once

    terminal = cm.run(requested_rounds=1)

    assert terminal.scheduled_calls == 2
    assert terminal.evaluated_rounds == 1
    assert terminal.execution_outcome_counts["research_rejected"] == 1
    assert terminal.execution_outcome_counts["evaluated"] == 1
    state = cm.get_state(run_result=terminal)
    assert state["total_rounds"] == 2
    assert state["n_steps"] == 2

    summary_path = tmp_path / "campaign" / "campaign_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert [step["round"] for step in summary["steps"]] == [1, 2]
    assert summary["steps"][0]["hypothesis"] is None
    assert summary["steps"][0]["failure_detail"] == (
        "HYPOTHESIS_RESEARCH_ABSTAINED"
    )
    assert summary["steps"][0]["execution_outcome"] == {
        "outcome": "research_rejected",
        "reason_code": "HYPOTHESIS_RESEARCH_ABSTAINED",
        "detail": "",
        "provenance": {"stage": "proposal_hypothesis"},
    }
    assert summary["action_locus_coverage"] == {"modify/local_search": 1}

    history_lines = (
        (tmp_path / "campaign" / "research_history.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(history_lines) == 2
    first_history = json.loads(history_lines[0])
    assert first_history["hypothesis"] is None
    assert first_history["patch"] is None
    assert first_history["protocol"] is None
    assert first_history["decision"] is None
    assert first_history["outcome"] == {
        "outcome": "research_rejected",
        "stage": "proposal_hypothesis",
        "reason_code": "HYPOTHESIS_RESEARCH_ABSTAINED",
    }

    public_artifacts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            tmp_path / "campaign" / "status.json",
            summary_path,
            tmp_path / "campaign" / "research_history.jsonl",
        )
    )
    for marker in sentinel.split():
        assert marker not in public_artifacts


def test_campaign_continues_after_research_history_record_limit(
    tmp_path,
    monkeypatch,
    caplog,
):
    import scion.core.research_history as history_module

    monkeypatch.setattr(history_module, "MAX_RESEARCH_HISTORY_RECORDS", 1)
    cm = _campaign(
        tmp_path,
        experiment_protocol=MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)]
        ),
    )
    generate_hypothesis = cm._explore_step_pipeline.generate_hypothesis
    calls = 0

    def abstain_once(branch):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ProposalAttempt.failure(
                ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.RESEARCH_REJECTED,
                    reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
                    provenance={"stage": "proposal_hypothesis"},
                )
            )
        return generate_hypothesis(branch)

    cm._explore_step_pipeline.generate_hypothesis = abstain_once

    terminal = cm.run(requested_rounds=1)

    assert terminal.completed
    assert terminal.stop_reason == "requested_rounds_completed"
    assert terminal.scheduled_calls == 2
    assert terminal.evaluated_rounds == 1
    assert len(cm._step_history) == 2
    summary = json.loads(
        (tmp_path / "campaign" / "campaign_summary.json").read_text(encoding="utf-8")
    )
    assert [step["round"] for step in summary["steps"]] == [1, 2]
    history_path = tmp_path / "campaign" / "research_history.jsonl"
    history_lines = history_path.read_text(encoding="utf-8").splitlines()
    assert len(history_lines) == 1
    assert json.loads(history_lines[0])["outcome"]["reason_code"] == (
        "HYPOTHESIS_RESEARCH_ABSTAINED"
    )
    assert "record limit 1 reached" in caplog.text
