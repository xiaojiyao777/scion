"""Focused tests split from test_campaign.py."""

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    branch_execution_hold,
    install_branch_execution_hold,
)
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
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

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
        assert r1.execution_outcome is ExecutionOutcome.RESEARCH_REJECTED
        assert r1.execution_outcome_reason_code == "PROPOSAL_RESPONSE_INVALID"
        assert r1.decision is None
        durable = cm._registry.query_execution_outcomes(branch_id=bid)
        assert len(durable) == 1
        assert durable[0]["outcome"] == "research_rejected"
        first_records = cm._hyp_store.get_by_branch(bid)
        assert len(first_records) == 1
        first_hypothesis_id = first_records[0].hypothesis_id
        assert first_records[0].status == "research_rejected"
        assert branch_execution_hold(cm._branch_ctrl.get_branch(bid)) is None
        assert bid not in cm._branch_patches
        assert cm._workspace_lifecycle.pending_candidates == {}

        r2 = cm.run_one_step()

        assert r2.branch_id == bid
        assert r2.execution_outcome is ExecutionOutcome.EVALUATED
        assert llm.request_kinds == ["hypothesis", "code", "hypothesis", "code"]
        records = cm._hyp_store.get_by_branch(bid)
        assert len(records) == 2
        assert records[0].hypothesis_id == first_hypothesis_id
        assert records[0].status == "research_rejected"
        assert records[1].hypothesis_id != first_hypothesis_id
        with sqlite3.connect(tmp_path / "campaign" / "scion.db") as conn:
            rows = conn.execute(
                "SELECT audit_payload_json FROM experiment_events "
                "WHERE event_kind = 'proposal_call' ORDER BY rowid"
            ).fetchall()
        transitions = [json.loads(row[0]) for row in rows]
        assert [item["phase"] for item in transitions] == [
            "hypothesis",
            "code",
            "hypothesis",
            "code",
        ]
        assert [item["status"] for item in transitions] == [
            "generated",
            "failed",
            "generated",
            "generated",
        ]
        code_hypothesis_ids = [
            item["hypothesis_id"]
            for item in transitions
            if item["phase"] == "code"
        ]
        assert code_hypothesis_ids == [
            first_hypothesis_id,
            records[1].hypothesis_id,
        ]

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
        ):
            ctx = original_build(self_ctx, branch=branch, hypothesis=hypothesis,
                                 champion=champion, problem_spec=problem_spec,
                                 branch_workspace=branch_workspace,
                                 step_history=step_history)
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
        cm._ctx_manager.build_code_context = lambda **kw: capturing_build(
            cm._ctx_manager, **kw
        )

        cm.run_one_step()
        assert captured_contexts
        assert all(
            "prior_code_failure" not in context
            for context in captured_contexts
        )

        cm.run_one_step()
        assert llm.request_kinds == ["hypothesis", "code", "hypothesis", "code"]
        assert captured_contexts
        assert all(
            "prior_code_failure" not in context
            for context in captured_contexts
        )

    def test_changed_h_binding_remains_not_evaluated_and_holds(self, tmp_path):
        """Local H/C binding faults stay fail-closed, unlike tainted C rejection."""
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

        assert result.execution_outcome is ExecutionOutcome.NOT_EVALUATED
        assert (
            result.execution_outcome_reason_code
            == "APPROVED_HYPOTHESIS_BINDING_MISSING"
        )
        assert llm.request_kinds == ["hypothesis"]
        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert branch_execution_hold(branch) is not None
        records = cm._hyp_store.get_by_branch(result.branch_id)
        assert len(records) == 1
        assert records[0].status == "not_evaluated"

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
        assert result.execution_outcome is ExecutionOutcome.EVALUATED


def test_provider_auth_failure_blocks_branch_with_one_typed_outcome(tmp_path):
    from scion.proposal.llm_client import LLMAuthError

    class AuthFailureLLM:
        def call_with_tool(self, *_args, **_kwargs):
            raise LLMAuthError("invalid provider credentials")

    cm = _campaign(tmp_path, llm_client=AuthFailureLLM())

    result = cm.run_one_step()

    assert result.execution_outcome is ExecutionOutcome.BLOCKED_INFRA
    assert result.decision is None
    branch = cm._branch_ctrl.get_branch(result.branch_id)
    assert branch.state == BranchState.BLOCKED_INFRA
    outcomes = cm._registry.query_execution_outcomes(branch_id=result.branch_id)
    assert len(outcomes) == 1
    assert outcomes[0]["outcome"] == "blocked_infra"
    step = cm._step_history[-1]
    assert step.protocol_result is None
    assert step.decision is None

    def test_direct_hypothesis_is_saved_once_with_original_champion_anchor(
        self,
        tmp_path,
    ):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        original_save = cm._hyp_store.save
        saved_ids = []

        def counting_save(record):
            saved_ids.append(record.hypothesis_id)
            original_save(record)

        cm._hyp_store.save = counting_save
        cm._explore_step_pipeline.get_champion = lambda: replace(
            cm._champion,
            version=2,
        )

        result = cm.run_one_step()

        records = cm._hyp_store.get_by_branch(result.branch_id)
        assert len(saved_ids) == 1
        assert len(records) == 1
        assert records[0].base_champion_version == 1
        with sqlite3.connect(tmp_path / "campaign" / "scion.db") as conn:
            row = conn.execute(
                "SELECT audit_payload_json FROM experiment_events "
                "WHERE event_kind = 'proposal_attempt_transition' "
                "AND stage = 'proposal_hypothesis' "
                "AND json_extract(audit_payload_json, '$.status') = 'generated' "
                "ORDER BY rowid LIMIT 1"
            ).fetchone()
        payload = json.loads(row[0])
        assert payload["anchors"]["champion_version"] == 1
        assert payload["hypothesis_id"] == records[0].hypothesis_id


class TestNoFakeHypothesisRecordFallback:
    def test_missing_canonical_record_holds_without_abandon(self, tmp_path):
        """Missing durable metadata is not converted into a research decision."""
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

        # Run next step — the campaign will schedule READY_VALIDATE → VALIDATING
        # and call _run_eval_step, which must stop without synthesizing ABANDON.
        result = cm.run_one_step()
        assert result.branch_id == bid

        from scion.core.models import BranchState
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state == BranchState.VALIDATING
        assert result.decision is None
        assert result.execution_outcome is ExecutionOutcome.NOT_EVALUATED
        assert branch.branch_evidence_summary["execution_hold"]["active"] is True
        assert protocol.canary_call_count == 1
        assert protocol.experiment_call_count == 1


class TestExecutionHoldResume:
    def test_branch_state_write_failure_is_not_silenced(
        self,
        tmp_path,
        monkeypatch,
    ):
        cm = _campaign(tmp_path)
        branch = cm._branch_ctrl.create_branch(cm._champion)

        def fail_save(_branch):
            raise RuntimeError("branch store unavailable")

        monkeypatch.setattr(cm._branch_store, "save", fail_save)
        with pytest.raises(RuntimeError, match="branch store unavailable"):
            cm._persist_branch_state(branch.branch_id)

    def test_resume_requires_durable_operator_event(self, tmp_path):
        cm = _campaign(tmp_path)
        branch = cm._branch_ctrl.create_branch(cm._champion)
        install_branch_execution_hold(
            branch,
            ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="PROVIDER_RESPONSE_INVALID",
            ),
        )
        cm._persist_branch_state(branch.branch_id)

        assert cm.operator_resume_execution_hold(
            branch.branch_id,
            operator_reason="provider response contract corrected",
            operator_ack="reviewed attempt evidence",
        )

        assert branch_execution_hold(branch) is None
        with sqlite3.connect(Path(cm._campaign_dir) / "scion.db") as conn:
            row = conn.execute(
                "SELECT event_kind, audit_payload_json "
                "FROM experiment_events WHERE branch_id = ? "
                "ORDER BY rowid DESC LIMIT 1",
                (branch.branch_id,),
            ).fetchone()
        assert row is not None
        assert row[0] == "operator_resume_execution_hold"
        assert json.loads(row[1])["operator_ack"] == "reviewed attempt evidence"
