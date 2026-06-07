from __future__ import annotations

from scion.tests.unit.agentic_session_test_support import *


def _policy_code_context(_hypothesis):
    return {
        "kind": "code",
        "target_file": "policies/search_policy.py",
        "target_file_code": _SEARCH_POLICY_SOURCE,
    }


def test_code_phase_planner_can_query_memory_and_get_full_surface(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {
                "tool_name": "memory.query",
                "code_phase": True,
                "args": {
                    "surface": "search_policy",
                    "query": "implementation lessons for search_policy",
                },
            },
            {"stop": True},
        ]
    )
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
                build_code_context=_policy_code_context,
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    code_tool_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("selection_source", "").startswith("code_phase")
    ]
    code_observations = creative.code_contexts[0]["agentic_tool_observations"]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert any(
        context.get("code_phase") is True for context in creative.planner_contexts
    )
    assert any(
        event["tool_name"] == "memory.query"
        and event["selection_source"] == "code_phase_planner"
        for event in code_tool_events
    )
    assert any(
        observation["tool_name"] == "context.read_surface"
        and observation["structured_payload"]["detail"] == "full"
        and observation["structured_payload"]["current_artifact"]["max_chars"] == 12000
        and observation["structured_payload"]["current_artifact"][
            "content_preview_omitted"
        ]
        and "content_preview"
        not in observation["structured_payload"]["current_artifact"]
        for observation in code_observations
    )


def test_agentic_session_bounded_planner_rejects_forbidden_tool(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "proposal.contract_preview", "args": {}},
        ]
    )
    context = _context(tmp_path, policy=ContextExposurePolicy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
                build_code_context=_policy_code_context,
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    contract_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("tool_name") == "proposal.contract_preview"
    ]
    assert output.status == AgenticProposalStatus.COMPLETED
    assert contract_events
    assert contract_events[0]["status"] == "error"
    assert contract_events[0]["error_code"] == "invalid_tool_selection"
    assert contract_events[0]["fallback"] == "fixed_tool_plan"
    assert not any(
        event.get("selection_source") == "planner_selected" for event in contract_events
    )
    assert (
        "proposal.contract_preview" not in creative.planner_contexts[0]["allowed_tools"]
    )


def test_model_side_forbidden_tool_selection_is_rejected_before_execution(
    tmp_path: Path,
) -> None:
    client = ToolSelectionClient(
        [
            {
                "intent": "call_tool",
                "tool_name": "proposal.contract_preview",
                "args": {},
            }
        ]
    )
    creative = CreativeLayer(client, model="test-model")
    context = _context(tmp_path, policy=ContextExposurePolicy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )
    state = AgenticProposalSessionState(
        session_id="session-forbidden-tool",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-1",
    )
    session._run_bounded_planner_tools(context, state)

    invalid_events = [
        event.metadata
        for event in state.transcript
        if event.metadata.get("error_code") == "invalid_tool_selection"
    ]
    forbidden_tool_events = [
        event.metadata
        for event in state.transcript
        if event.metadata.get("tool_name") == "proposal.contract_preview"
    ]
    assert invalid_events
    assert invalid_events[0]["fallback"] == "fixed_tool_plan"
    assert not any(
        event.get("selection_source") == "planner_selected"
        for event in forbidden_tool_events
    )


def test_model_side_malformed_tool_selection_falls_back_without_raw_refs(
    tmp_path: Path,
) -> None:
    client = ToolSelectionClient(
        [
            {
                "intent": "call_tool",
                "tool_name": "context.list_surfaces",
                "args": "not-json-object",
            }
        ]
    )
    creative = CreativeLayer(client, model="test-model")
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )
    state = AgenticProposalSessionState(
        session_id="session-malformed-tool",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-1",
    )
    session._run_bounded_planner_tools(context, state)

    assert any(
        event.metadata.get("error_code") == "planner_exception"
        for event in state.transcript
    )
    assert any(
        event.metadata.get("fallback") == "fixed_tool_plan"
        for event in state.transcript
    )
    assert "raw_metrics_ref" not in client.prompts[0]
    assert "SECRET_HOLDOUT_SIGNAL" not in client.prompts[0]


def test_agentic_session_fallback_does_not_repeat_successful_required_tools(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_surface", "args": "bad-args"},
        ]
    )
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
                build_code_context=_policy_code_context,
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    tool_names = [
        event.metadata["tool_name"]
        for event in output.transcript
        if event.metadata.get("step_id")
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert tool_names.count("context.list_surfaces") == 1
    assert tool_names.count("context.read_problem") == 1
    assert "memory.query" in tool_names
    assert any(
        event.metadata.get("skip_reason") == "already_succeeded"
        for event in output.transcript
    )


def test_agentic_session_fallback_does_not_repeat_successful_feedback_tools(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.read_surface", "args": "bad-args"},
        ]
    )
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
                build_code_context=_policy_code_context,
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    tool_names = [
        event.metadata["tool_name"]
        for event in output.transcript
        if event.metadata.get("step_id")
    ]
    code_observation_names = {
        observation["tool_name"]
        for observation in creative.code_contexts[0]["agentic_tool_observations"]
    }

    assert output.status == AgenticProposalStatus.COMPLETED
    assert creative.code_contexts
    assert tool_names.count("context.list_surfaces") == 1
    assert tool_names.count("context.read_problem") == 1
    for feedback_tool in _COMPACT_FEEDBACK_TOOL_NAMES:
        assert tool_names.count(feedback_tool) == 1
        assert feedback_tool in code_observation_names
    assert any(
        event.metadata.get("fallback") == "fixed_tool_plan"
        and event.metadata.get("skip_reason") == "already_succeeded"
        for event in output.transcript
    )


def test_agentic_session_retries_empty_branch_scoped_feedback_campaign_wide(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {
                "tool_name": "feedback.query_screening",
                "args": {"branch_id": "branch-empty"},
            },
            {
                "tool_name": "feedback.query_runtime",
                "args": {"branch_id": "branch-empty"},
            },
            {"stop": True},
        ]
    )
    base_context = _context(tmp_path, policy=_tool_enabled_policy())
    current_branch = Branch(
        branch_id="branch-current",
        state=BranchState.EXPLORE,
        base_champion_id=7,
        base_champion_hash="code-hash",
    )
    context = replace(base_context, branch=current_branch)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
                build_code_context=_policy_code_context,
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    screening_summaries = [
        event.metadata.get("result_summary", "")
        for event in output.transcript
        if event.metadata.get("tool_name") == "feedback.query_screening"
    ]
    runtime_summaries = [
        event.metadata.get("result_summary", "")
        for event in output.transcript
        if event.metadata.get("tool_name") == "feedback.query_runtime"
    ]
    hypothesis_observations = creative.hypothesis_contexts[0][
        "agentic_tool_observations"
    ]
    useful_screening = [
        observation
        for observation in hypothesis_observations
        if observation["tool_name"] == "feedback.query_screening"
        and observation["structured_payload"]["screening_steps"]
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert any("Returned 1 of 1" in summary for summary in screening_summaries)
    assert len(runtime_summaries) >= 2
    assert useful_screening
    assert any(
        event.metadata.get("selection_source") == "deterministic_prefetch"
        and event.metadata.get("tool_name") == "feedback.query_screening"
        for event in output.transcript
    )
    assert any(
        event.metadata.get("selection_source") == "planner_selected"
        and event.metadata.get("skip_reason") == "equivalent_feedback_observation"
        for event in output.transcript
    )
