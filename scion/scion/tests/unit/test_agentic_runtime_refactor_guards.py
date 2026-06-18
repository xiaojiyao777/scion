from __future__ import annotations

from dataclasses import fields

import pytest
from pydantic import BaseModel

from scion.proposal.tools import (
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
    ProposalToolRegistry,
)
from scion.tests.unit.agentic_session_test_support import (
    AgenticProposalOutput,
    AgenticProposalPhase,
    AgenticProposalSessionState,
    AgenticToolLoopConfig,
    _context,
    _tool_enabled_policy,
)


def test_agentic_session_state_keeps_runtime_audit_fields() -> None:
    state_field_names = {field.name for field in fields(AgenticProposalSessionState)}

    assert {
        "session_id",
        "campaign_id",
        "branch_id",
        "transcript",
        "scratch_artifact_refs",
        "failure_ledger",
        "observation_ledger",
        "tool_selection_ledger",
        "tool_step_count",
        "tool_call_count",
        "tool_event_count",
        "preview_tool_step_count",
        "preview_tool_call_count",
        "observation_chars_used",
        "loop_stop_reason",
        "tool_loop_config",
        "wall_time_started_at",
        "tool_call_fuse_counts",
    }.issubset(state_field_names)


def test_state_note_remains_transcript_backed_runtime_event() -> None:
    config = AgenticToolLoopConfig()
    state = AgenticProposalSessionState(
        session_id="session-runtime-guard",
        campaign_id="campaign-runtime-guard",
        branch_id="branch-runtime-guard",
        tool_loop_config={
            "max_steps": config.max_steps,
            "max_tool_calls": config.max_tool_calls,
        },
    )

    state.note(
        AgenticProposalPhase.DIAGNOSE,
        "Proposal tool observation: context.read_problem",
        metadata={
            "tool_name": "context.read_problem",
            "status": "ok",
            "evidence_ref": "observation-runtime-guard",
        },
    )

    assert state.phase == AgenticProposalPhase.DIAGNOSE
    assert len(state.transcript) == 1
    event = state.transcript[0]
    assert event.phase == "diagnose"
    assert event.metadata["tool_name"] == "context.read_problem"
    assert event.metadata["status"] == "ok"
    assert event.metadata["evidence_ref"] == "observation-runtime-guard"


def test_agentic_output_does_not_grow_decision_or_scheduler_fields() -> None:
    output_field_names = {field.name for field in fields(AgenticProposalOutput)}

    assert {"hypothesis", "patch", "termination_reason", "tool_budget_used"}.issubset(
        output_field_names
    )
    assert {
        "decision",
        "decision_features",
        "promotion_decision",
        "scheduler_action",
        "validation_raw_metrics_ref",
        "frozen_raw_metrics_ref",
        "raw_metrics_ref",
    }.isdisjoint(output_field_names)


def test_phase_policy_keeps_preview_and_holdout_tools_framework_controlled(
    tmp_path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())

    projection = registry.phase_policy_projection(context, "diagnose")
    model_selectable = set(projection["model_selectable_tools"])
    framework_preview = set(projection["framework_preview_tools"])

    assert {
        "proposal.schema_preview",
        "proposal.target_permission_preview",
        "proposal.contract_preview",
        "proposal.algorithm_smoke",
    }.issubset(framework_preview)
    assert model_selectable.isdisjoint(framework_preview)
    assert "feedback.query_holdout_summary" not in model_selectable

    model_specs = registry.allowed_tool_specs_for_phase(context, "diagnose")
    model_spec_names = {str(spec["name"]) for spec in model_specs}

    assert model_spec_names.isdisjoint(framework_preview)
    assert "feedback.query_holdout_summary" not in model_spec_names
    assert "feedback.query_screening" in model_spec_names


def test_proposal_tool_registry_rejects_write_tools() -> None:
    class EmptyInput(BaseModel):
        pass

    class WriteScratchTool:
        name = "scratch.write"
        input_schema = EmptyInput
        permission = ProposalToolPermission.WRITE_SCRATCH
        read_only = False
        concurrency_safe = False
        max_result_chars = 1024

        def call(
            self,
            args: EmptyInput,
            context: ProposalToolContext,
        ) -> ProposalObservation:
            del args
            return ProposalObservation(
                observation_id="write-tool-should-not-run",
                session_id=context.session_id,
                tool_name=self.name,
                tool_call_id="",
                observation_type="write",
                summary="This write tool should never be registered.",
                structured_payload={},
                is_error=True,
                failure_code=ProposalToolFailureCode.UNSUPPORTED,
            )

    with pytest.raises(ValueError, match="read-only tools only"):
        ProposalToolRegistry([WriteScratchTool()])
