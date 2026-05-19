from __future__ import annotations

from scion.tests.unit.agentic_session_test_support import *

def test_generic_session_keeps_planner_owned_required_context(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
            {"stop": True},
        ]
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )
    state = AgenticProposalSessionState(
        session_id="session-generic-planner",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-1",
    )

    observations = session._run_initial_tool_loop(context, state)

    assert [observation.tool_name for observation in observations[:2]] == [
        "context.list_surfaces",
        "context.read_problem",
    ]
    tool_events = [
        event.metadata for event in state.transcript if event.metadata.get("step_id")
    ]
    assert [event["selection_source"] for event in tool_events[:2]] == [
        "planner_selected",
        "planner_selected",
    ]
    assert not any(
        event.metadata.get("selection_source") == "required_context_preface"
        for event in state.transcript
    )


def test_code_phase_required_surface_read_compacts_to_preserve_self_check_reserve(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    hypothesis = HypothesisProposal(**_valid_hypothesis_payload())
    config = AgenticToolLoopConfig(
        max_steps=8,
        max_tool_calls=8,
        max_observation_chars=48000,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    state = AgenticProposalSessionState(
        session_id="session-budget",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-1",
        observation_chars_used=40000,
        tool_loop_config=config.__dict__,
    )

    observations = session._run_code_context_fixed_tools(
        context,
        state,
        hypothesis,
        [],
        selection_source="code_phase_required",
    )

    assert [observation.tool_name for observation in observations] == [
        "context.read_surface"
    ]
    assert observations[0].is_error is False
    assert observations[0].structured_payload["detail"] == "compact"
    assert observations[0].structured_payload["target_file"] == hypothesis.target_file
    assert any(
        event.metadata.get("tool_name") == "context.read_branch_state"
        and event.metadata.get("skip_reason") == "code_self_check_budget_reserved"
        for event in state.transcript
    )
    assert any(
        event.metadata.get("tool_name") == "context.read_surface"
        and event.metadata.get("selection_source") == "code_phase_required_compact"
        for event in state.transcript
    )


def test_code_phase_prioritizes_solver_design_target_read_before_final_preview_slots(
    tmp_path: Path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
        )
    )
    config = AgenticToolLoopConfig(max_steps=8, max_tool_calls=8)
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    state = AgenticProposalSessionState(
        session_id="session-code-target",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-1",
        tool_step_count=5,
        tool_call_count=5,
        tool_loop_config=config.__dict__,
    )

    observations = session._run_code_context_fixed_tools(
        context,
        state,
        hypothesis,
        [],
        selection_source="code_phase_required",
    )

    assert [observation.tool_name for observation in observations] == [
        "context.read_algorithm_file"
    ]
    assert observations[0].is_error is False
    assert observations[0].structured_payload["file_path"] == hypothesis.target_file
    assert observations[0].structured_payload["source"] in {
        "branch_workspace",
        "champion_snapshot",
        "problem_spec_root",
    }
    assert any(
        event.metadata.get("tool_name") == "context.read_surface"
        and event.metadata.get("skip_reason")
        == "code_self_check_tool_slot_reserved"
        for event in state.transcript
    )


def test_solver_design_grounding_reads_file_list_and_target_file(
    tmp_path: Path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
        )
    )
    config = AgenticToolLoopConfig(max_steps=12, max_tool_calls=12)
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    state = AgenticProposalSessionState(
        session_id="session-grounding",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-1",
        tool_loop_config=config.__dict__,
    )

    observations = session._run_solver_design_grounding_tools(
        context,
        state,
        [],
        selection_source="solver_design_grounding_required",
        hypothesis=hypothesis,
    )

    tool_names = [observation.tool_name for observation in observations]
    assert "context.list_algorithm_files" in tool_names
    assert "context.read_active_solver_design" in tool_names
    assert "context.read_algorithm_file" in tool_names
    assert any(
        observation.structured_payload.get("file_path") == hypothesis.target_file
        for observation in observations
        if observation.tool_name == "context.read_algorithm_file"
    )
    assert (
        agentic_session_module._missing_solver_design_grounding_error(
            observations,
            hypothesis=hypothesis,
        )
        is None
    )


def test_solver_design_grounding_allows_declared_new_module_without_file_read(
    tmp_path: Path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            action="create_new",
            target_file="policies/baseline_modules/cross_route_lns.py",
        )
    )
    config = AgenticToolLoopConfig(max_steps=12, max_tool_calls=12)
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    state = AgenticProposalSessionState(
        session_id="session-grounding-create",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-1",
        tool_loop_config=config.__dict__,
    )

    observations = session._run_solver_design_grounding_tools(
        context,
        state,
        [],
        selection_source="solver_design_grounding_required",
        hypothesis=hypothesis,
    )

    tool_names = [observation.tool_name for observation in observations]
    assert "context.list_algorithm_files" in tool_names
    assert "context.read_active_solver_design" in tool_names
    assert agentic_session_module._has_successful_solver_call_graph_grounding(
        observations
    )
    assert not any(
        observation.tool_name == "context.read_algorithm_file"
        and observation.structured_payload.get("file_path") == hypothesis.target_file
        for observation in observations
    )
    assert (
        agentic_session_module._missing_solver_design_grounding_error(
            observations,
            hypothesis=hypothesis,
            context=context,
        )
        is None
    )

    off_boundary = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            action="create_new",
            target_file="policies/not_solver/new_module.py",
        )
    )
    error = agentic_session_module._missing_solver_design_grounding_error(
        observations,
        hypothesis=off_boundary,
        context=context,
    )
    assert error is not None
    assert "outside declared patch paths" in error


def test_budget_denial_does_not_apply_to_mandatory_code_surface_read(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    config = AgenticToolLoopConfig(max_observation_chars=48000)
    state = AgenticProposalSessionState(
        session_id="session-budget",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-1",
        observation_chars_used=47000,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )

    assert session._should_deny_optional_tool_for_budget(
        "context.read_surface",
        selection_source="planner_selected",
        state=state,
    )
    assert not session._should_deny_optional_tool_for_budget(
        "context.read_surface",
        selection_source="code_phase_required",
        state=state,
    )
    assert not session._should_deny_optional_tool_for_budget(
        "context.read_surface",
        selection_source="code_phase_required_compact",
        state=state,
    )


