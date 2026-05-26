from __future__ import annotations

from scion.tests.unit.agentic_session_test_support import *


def _policy_code_context(_hypothesis):
    return {
        "kind": "code",
        "target_file": "policies/search_policy.py",
        "target_file_code": _SEARCH_POLICY_SOURCE,
    }


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
    assert len(client.system_blocks[0]) == 1
    assert "allowed_tool_specs" in client.system_blocks[0][0]["text"]
    assert all(block.get("cache_control") for block in client.system_blocks[0])
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
    first_planner_context = creative.planner_contexts[0]

    assert output.status in {
        AgenticProposalStatus.COMPLETED,
        AgenticProposalStatus.FAILED,
        AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
    }
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


def test_solver_design_tool_selection_context_carries_active_fact_anchor(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_active_solver_design", "args": {}},
            {"stop": True},
        ]
    )
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file="policies/baseline_modules/local_search.py",
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-cvrp",
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

    anchors = [
        planner_context.get("active_algorithm_facts_anchor") or {}
        for planner_context in creative.planner_contexts
    ]

    assert output.status in {
        AgenticProposalStatus.COMPLETED,
        AgenticProposalStatus.FAILED,
        AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
    }
    assert any(anchor.get("fact_packet_digest") for anchor in anchors)
    assert any(
        "cvrp.local_search.or_opt_1_relocation" in anchor.get("fact_ids", ())
        for anchor in anchors
    )


def test_solver_design_planner_repeated_completed_required_tool_does_not_loop(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {
                "tool_name": "context.read_active_solver_design",
                "args": {
                    "surface": "solver_design",
                    "include_file_previews": False,
                },
            }
        ]
        * 12
    )
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file="policies/baseline_modules/local_search.py",
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_tool_calls=18, max_steps=24),
    )
    state = AgenticProposalSessionState(
        session_id="session-solver-design-repeat",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-cvrp",
        tool_loop_config=session._tool_loop_config.__dict__,
    )

    observations = session._run_initial_tool_loop(context, state)

    assert len(creative.planner_contexts) == 1
    assert state.loop_stop_reason in {
        "required_context_satisfied",
        "planner_stop",
    }
    assert any(
        event.metadata.get("tool_name") == "context.read_active_solver_design"
        and event.metadata.get("skip_reason") == "already_succeeded"
        for event in state.transcript
    )
    assert sum(
        1
        for observation in observations
        if observation.tool_name == "context.read_active_solver_design"
        and not observation.is_error
    ) == 1


def test_solver_design_planner_guidance_exposes_registry_and_slice_ids_after_map(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative([{"stop": True}])
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_tool_calls=16, max_steps=20),
    )
    state = AgenticProposalSessionState(
        session_id="session-map-guidance",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-cvrp",
        tool_loop_config=session._tool_loop_config.__dict__,
    )

    session._run_initial_tool_loop(context, state)
    guidance = creative.planner_contexts[0]["tool_arg_guidance"]
    step_events = [
        event.metadata for event in state.transcript if event.metadata.get("step_id")
    ]
    map_followups = [
        event
        for event in step_events
        if event["tool_name"]
        in {"context.read_operator_registry", "context.read_algorithm_slice"}
        and event["selection_source"] == "planner_map_followup_required"
    ]
    required_preface_registry_or_slice = [
        event
        for event in step_events
        if event["tool_name"]
        in {"context.read_operator_registry", "context.read_algorithm_slice"}
        and event["selection_source"] == "required_context_preface"
    ]
    ledger_followups = [
        entry
        for entry in state.observation_ledger
        if entry.get("tool_name")
        in {"context.read_operator_registry", "context.read_algorithm_slice"}
        and entry.get("selection_source") == "planner_map_followup_required"
    ]

    map_guidance = guidance["context.read_active_solver_map"]
    registry_guidance = guidance["context.read_operator_registry"]
    slice_guidance = guidance["context.read_algorithm_slice"]
    file_guidance = guidance["context.read_algorithm_file"]
    assert {event["tool_name"] for event in map_followups} == {
        "context.read_operator_registry",
        "context.read_algorithm_slice",
    }
    assert not required_preface_registry_or_slice
    assert {entry["tool_name"] for entry in ledger_followups} == {
        "context.read_operator_registry",
        "context.read_algorithm_slice",
    }
    assert "cvrp.registry.local_search_vns" in map_guidance["available_registry_ids"]
    assert "cvrp.slice.local_search.default_vns_operators" in (
        map_guidance["available_slice_ids"]
    )
    assert registry_guidance["recommended_args"]["registry_id"].startswith(
        "cvrp.registry."
    )
    assert slice_guidance["recommended_args"]["slice_id"].startswith("cvrp.slice.")
    assert "before broad full-file reads" in registry_guidance[
        "required_after_map_rule"
    ]
    assert "before context.read_algorithm_file" in slice_guidance[
        "required_after_map_rule"
    ]
    assert "read_operator_registry" in file_guidance["pre_full_read_rule"]
    assert "read_algorithm_slice" in file_guidance["pre_full_read_rule"]


def test_solver_design_planner_reads_registry_slice_before_broad_file(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_modules/local_search.py"
    creative = PlanningCreative(
        [
            {
                "tool_name": "context.read_algorithm_file",
                "args": {
                    "surface": "solver_design",
                    "file_path": target_file,
                    "max_chars": 4000,
                },
            },
            {"stop": True},
        ]
    )
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_tool_calls=16, max_steps=20),
    )
    state = AgenticProposalSessionState(
        session_id="session-map-before-file",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-cvrp",
        tool_loop_config=session._tool_loop_config.__dict__,
    )

    observations = session._run_initial_tool_loop(context, state)
    step_events = [
        event.metadata for event in state.transcript if event.metadata.get("step_id")
    ]
    tool_order = [event["tool_name"] for event in step_events]
    file_index = next(
        index
        for index, event in enumerate(step_events)
        if event["tool_name"] == "context.read_algorithm_file"
        and event["selection_source"] == "planner_selected"
    )
    registry_index = next(
        index
        for index, event in enumerate(step_events)
        if event["tool_name"] == "context.read_operator_registry"
    )
    slice_index = next(
        index
        for index, event in enumerate(step_events)
        if event["tool_name"] == "context.read_algorithm_slice"
    )

    assert "context.read_active_solver_map" in tool_order
    assert registry_index < file_index
    assert slice_index < file_index
    assert step_events[registry_index]["selection_source"] == (
        "planner_map_followup_required"
    )
    assert step_events[slice_index]["selection_source"] == (
        "planner_map_followup_required"
    )
    assert not [
        event
        for event in step_events
        if event["tool_name"]
        in {"context.read_operator_registry", "context.read_algorithm_slice"}
        and event["selection_source"] == "required_context_preface"
    ]
    assert any(
        entry.get("tool_name") == "context.read_operator_registry"
        and entry.get("selection_source") == "planner_map_followup_required"
        for entry in state.observation_ledger
    )
    assert any(
        entry.get("tool_name") == "context.read_algorithm_slice"
        and entry.get("selection_source") == "planner_map_followup_required"
        for entry in state.observation_ledger
    )
    assert any(
        observation.tool_name == "context.read_algorithm_slice"
        and observation.structured_payload["file_path"] == target_file
        for observation in observations
    )


def test_code_phase_targeted_read_context_carries_active_fact_anchor(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_modules/local_search.py"
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file=target_file,
    )
    original_code = (
        Path(context.champion.code_snapshot_path) / target_file
    ).read_text(encoding="utf-8")
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file=target_file,
            target_objectives=["total_distance"],
        )
    )
    creative = PlanningCreative(
        [
            {"stop": True},
            {
                "tool_name": "context.read_algorithm_symbol",
                "args": {
                    "surface": "solver_design",
                    "file_path": target_file,
                    "symbol": "_or_opt",
                    "max_chars": 4000,
                },
            },
            {"stop": True},
        ],
        hypothesis=hypothesis,
        patch=PatchProposal(
            file_path=target_file,
            action="modify",
            code_content=original_code,
        ),
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_tool_calls=16, max_steps=20),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-cvrp",
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

    code_phase_contexts = [
        planner_context
        for planner_context in creative.planner_contexts
        if planner_context.get("code_phase") is True
    ]
    anchors = [
        planner_context.get("active_algorithm_facts_anchor") or {}
        for planner_context in code_phase_contexts
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert anchors
    assert all(anchor.get("fact_packet_digest") for anchor in anchors)
    assert all(anchor.get("snapshot_digest") for anchor in anchors)
    assert all(anchor.get("provenance") for anchor in anchors)
    assert all(anchor.get("source_tool_call_id") for anchor in anchors)
    assert any(
        "cvrp.local_search.or_opt_1_relocation" in anchor.get("fact_ids", ())
        for anchor in anchors
    )
    assert any(
        event.metadata.get("tool_name") == "context.read_algorithm_symbol"
        and event.metadata.get("selection_source") == "code_phase_planner"
        for event in output.transcript
    )


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
