from __future__ import annotations

from scion.tests.unit.agentic_session_test_support import *

def test_model_side_tool_selection_adapter_executes_allowed_tool(
    tmp_path: Path,
) -> None:
    client = ToolSelectionClient(
        [
            {"intent": "call_tool", "tool_name": "context.list_surfaces", "args": {}},
            {"intent": "call_tool", "tool_name": "context.read_problem", "args": {}},
            {"intent": "stop"},
        ]
    )
    creative = CreativeLayer(client, model="test-model")
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
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    planner_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("selection_source") == "planner_selected"
    ]
    assert output.status == AgenticProposalStatus.COMPLETED
    assert [event["tool_name"] for event in planner_events[:2]] == [
        "context.list_surfaces",
        "context.read_problem",
    ]
    assert client.tool_names[:2] == ["plan_proposal_tool_call"] * 2
    assert "allowed_tool_specs" in client.prompts[0]
    assert "raw_metrics_ref" not in client.prompts[0]


def test_model_side_planner_prompt_omits_empty_holdout_tool_names(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
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
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )
    first_planner_context = creative.planner_contexts[0]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert "" not in first_planner_context["allowed_tools"]
    assert (
        "feedback.query_holdout_summary" not in first_planner_context["allowed_tools"]
    )
    assert "proposal.schema_preview" not in first_planner_context["allowed_tools"]
    assert (
        "proposal.target_permission_preview"
        not in first_planner_context["allowed_tools"]
    )
    assert "proposal.contract_preview" not in first_planner_context["allowed_tools"]
    assert "proposal.algorithm_smoke" not in first_planner_context["allowed_tools"]
    assert all(spec.get("name") for spec in first_planner_context["allowed_tool_specs"])


def test_planner_schema_preview_error_does_not_pollute_authoritative_self_check() -> None:
    state = AgenticProposalSessionState(
        session_id="session-preview-filter",
        campaign_id="camp-1",
        branch_id="branch-1",
    )
    planner_error = ProposalObservation(
        observation_id="planner-schema-error",
        session_id=state.session_id,
        tool_name="proposal.schema_preview",
        tool_call_id="tool-0001",
        observation_type="tool_error",
        summary="Tool input failed schema validation.",
        structured_payload={"errors": [{"loc": ["hypothesis"]}]},
        is_error=True,
        failure_code=ProposalToolFailureCode.SCHEMA_ERROR,
    )
    schema_ok = ProposalObservation(
        observation_id="schema-ok",
        session_id=state.session_id,
        tool_name="proposal.schema_preview",
        tool_call_id="tool-0002",
        observation_type="schema_preview",
        summary="Schema preview passed.",
        structured_payload={"passed": True},
    )
    target_ok = ProposalObservation(
        observation_id="target-ok",
        session_id=state.session_id,
        tool_name="proposal.target_permission_preview",
        tool_call_id="tool-0003",
        observation_type="target_permission_preview",
        summary="Target preview passed.",
        structured_payload={"passed": True},
    )
    contract_ok = ProposalObservation(
        observation_id="contract-ok",
        session_id=state.session_id,
        tool_name="proposal.contract_preview",
        tool_call_id="tool-0004",
        observation_type="contract_preview",
        summary="Contract preview passed.",
        structured_payload={"passed": True},
    )
    state.note(
        AgenticProposalPhase.DIAGNOSE,
        "Planner preview error.",
        metadata={
            "tool_name": "proposal.schema_preview",
            "observation_id": planner_error.observation_id,
            "selection_source": "planner_selected",
        },
    )
    for observation in (schema_ok, target_ok, contract_ok):
        state.note(
            AgenticProposalPhase.SELF_CHECK,
            "Authoritative preview.",
            metadata={
                "tool_name": observation.tool_name,
                "observation_id": observation.observation_id,
                "selection_source": "fallback_selected",
            },
        )

    session = AgenticProposalSession(FakeCreative())
    self_check = session._self_check_from_authoritative_previews(
        [planner_error, schema_ok, target_ok, contract_ok],
        state,
    )

    assert self_check.schema_valid is True
    assert self_check.schema_preview_codes == ()
    assert self_check.contract_preview_passed is True


def test_planner_stop_after_problem_context_falls_back_to_feedback_and_surface_read(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
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
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )
    tool_events = [
        event.metadata for event in output.transcript if event.metadata.get("tool_name")
    ]
    tool_names = [event["tool_name"] for event in tool_events]
    code_observations = creative.code_contexts[0]["agentic_tool_observations"]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert (
        output.tool_budget_used["observation_chars"]
        <= output.tool_loop_config["max_observation_chars"]
    )
    assert (
        creative.planner_contexts[0]["tool_arg_guidance"]["context.read_surface"][
            "recommended_args"
        ]["max_code_chars"]
        == 800
    )
    assert any(
        event.metadata.get("error_code") == "planner_stopped_before_required_context"
        for event in output.transcript
    )
    for feedback_tool in _COMPACT_FEEDBACK_TOOL_NAMES:
        assert feedback_tool in tool_names
    assert any(
        event["tool_name"] == "context.read_surface"
        and event["selection_source"] == "selected_surface_required"
        for event in tool_events
    )
    assert any(
        observation["tool_name"] == "context.read_surface"
        and observation["structured_payload"]["surface"]["name"] == "search_policy"
        and observation["structured_payload"]["detail"] == "full"
        and observation["structured_payload"]["current_artifact"]["max_chars"] == 12000
        and observation["structured_payload"]["current_artifact"][
            "content_preview_omitted"
        ]
        and "content_preview"
        not in observation["structured_payload"]["current_artifact"]
        for observation in code_observations
    )
    hypothesis_observation_names = {
        observation["tool_name"]
        for observation in creative.hypothesis_contexts[0]["agentic_tool_observations"]
    }
    assert _COMPACT_FEEDBACK_TOOL_NAMES.issubset(hypothesis_observation_names)


def test_planner_memory_only_still_falls_back_for_screening_and_runtime_feedback(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
            {"tool_name": "memory.query", "args": {}},
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
            build_code_context=lambda _hypothesis: {"kind": "code"},
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
        if event.metadata.get("tool_name")
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert any(
        event.metadata.get("error_code") == "planner_stopped_before_required_context"
        and "feedback.query_screening" in event.metadata.get("detail", "")
        and "feedback.query_runtime" in event.metadata.get("detail", "")
        for event in output.transcript
    )
    assert "memory.query" in tool_names
    assert "feedback.query_screening" in tool_names
    assert "feedback.query_runtime" in tool_names


def test_code_phase_planner_can_query_memory_and_get_full_surface(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
            {"stop": True},
            {
                "tool_name": "memory.query",
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
            build_code_context=lambda _hypothesis: {"kind": "code"},
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
            build_code_context=lambda _hypothesis: {"kind": "code"},
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

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    invalid_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("error_code") == "invalid_tool_selection"
    ]
    forbidden_tool_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("tool_name") == "proposal.contract_preview"
    ]
    assert output.status == AgenticProposalStatus.COMPLETED
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

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={
                "raw_metrics_ref": "/SECRET/raw.json",
                "note": "safe line\nvalidation SECRET_HOLDOUT_SIGNAL",
            },
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    rendered_output = json.dumps(output, default=str, sort_keys=True)
    assert output.status == AgenticProposalStatus.COMPLETED
    assert any(
        event.metadata.get("error_code") == "planner_exception"
        for event in output.transcript
    )
    assert any(
        event.metadata.get("fallback") == "fixed_tool_plan"
        for event in output.transcript
    )
    assert "raw_metrics_ref" not in rendered_output
    assert "SECRET_HOLDOUT_SIGNAL" not in rendered_output
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
            build_code_context=lambda _hypothesis: {"kind": "code"},
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
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "memory.query", "args": {}},
            {
                "tool_name": "feedback.query_screening",
                "args": {"branch_id": "branch-1"},
            },
            {
                "tool_name": "feedback.query_runtime",
                "args": {"branch_id": "branch-1"},
            },
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
            build_code_context=lambda _hypothesis: {"kind": "code"},
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
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
            {"tool_name": "memory.query", "args": {}},
            {
                "tool_name": "feedback.query_screening",
                "args": {"branch_id": "branch-current"},
            },
            {
                "tool_name": "feedback.query_runtime",
                "args": {"branch_id": "branch-current"},
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
            build_code_context=lambda _hypothesis: {"kind": "code"},
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
    assert any("Returned 0 of 0" in summary for summary in screening_summaries)
    assert any("Returned 1 of 1" in summary for summary in screening_summaries)
    assert len(runtime_summaries) >= 2
    assert useful_screening


