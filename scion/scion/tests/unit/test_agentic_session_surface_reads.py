from __future__ import annotations

from scion.tests.unit.agentic_session_test_support import *

def test_forced_surface_session_uses_bounded_list_and_does_not_reread_surface(
    tmp_path: Path,
) -> None:
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file="policies/baseline_algorithm.py",
    )
    listed = ProposalToolRegistry.default_read_only().call(
        "context.list_surfaces",
        {},
        context,
    )
    rendered_list = json.dumps(listed.structured_payload, sort_keys=True, default=str)
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_algorithm.py",
            target_objectives=["total_distance"],
        )
    )
    creative = PlanningCreative(
        [
            {
                "tool_name": "context.read_surface",
                "args": {"surface": "solver_design"},
            },
            {"stop": True},
        ],
        hypothesis=hypothesis,
        patch=PatchProposal(
            file_path="policies/baseline_algorithm.py",
            action="modify",
            code_content=(
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    context.record_iteration('search', 1)\n"
                    "    return context.nearest_neighbor()\n"
            ),
        ),
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
        event.metadata for event in output.transcript if event.metadata.get("step_id")
    ]
    read_surface_events = [
        event for event in tool_events if event["tool_name"] == "context.read_surface"
    ]

    assert listed.is_error is False
    assert listed.structured_payload["surface_count"] == 1
    assert listed.structured_payload["total_declared_surface_count"] == 1
    assert listed.structured_payload["surfaces"][0]["name"] == "solver_design"
    assert len(rendered_list) < 12000
    assert output.status == AgenticProposalStatus.COMPLETED
    assert len(read_surface_events) == 2
    assert read_surface_events[0]["selection_source"] == "planner_selected"
    assert read_surface_events[1]["selection_source"] == "code_phase_required_compact"
    assert output.tool_budget_used["observation_chars"] <= (
        output.tool_loop_config["max_observation_chars"]
    )
    assert any(
        event.metadata.get("skip_reason") == "already_succeeded"
        and event.metadata.get("tool_name") == "context.read_surface"
        for event in output.transcript
    )
    code_observations = creative.code_contexts[0]["agentic_tool_observations"]
    assert any(
        observation["tool_name"] == "context.read_algorithm_file"
        and observation["structured_payload"]["file_path"]
        == "policies/baseline_algorithm.py"
        and observation["structured_payload"]["max_chars"] == 96000
        and "def solve" in observation["structured_payload"]["content_preview"]
        for observation in code_observations
    )
    assert any(
        observation["tool_name"] == "context.read_surface"
        and observation["structured_payload"]["detail"] == "compact"
        and observation["structured_payload"]["target_file"]
        == "policies/baseline_algorithm.py"
        for observation in code_observations
    )


def test_code_phase_solver_module_read_uses_target_preview_budget(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_modules/config.py"
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file=target_file,
    )
    target_path = Path(context.champion.code_snapshot_path) / target_file
    module_code = target_path.read_text(encoding="utf-8") + "\n" + "\n".join(
        f"# budget filler {idx}" for idx in range(700)
    )
    target_path.write_text(module_code, encoding="utf-8")
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file=target_file,
            target_objectives=["total_distance"],
        )
    )
    creative = PlanningCreative(
        [
            {
                "tool_name": "context.read_surface",
                "code_phase": True,
                "args": {
                    "surface": "solver_design",
                    "target_file": target_file,
                    "detail": "full",
                    "max_code_chars": 12000,
                },
            },
        ],
        hypothesis=hypothesis,
        patch=PatchProposal(
            file_path=target_file,
            action="modify",
            code_content=module_code,
        ),
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
        event.metadata for event in output.transcript if event.metadata.get("step_id")
    ]
    read_surface_events = [
        event for event in tool_events if event["tool_name"] == "context.read_surface"
    ]
    code_observations = creative.code_contexts[0]["agentic_tool_observations"]
    module_read = next(
        observation
        for observation in code_observations
        if observation["tool_name"] == "context.read_surface"
        and observation["structured_payload"].get("target_file") == target_file
    )
    payload = module_read["structured_payload"]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert any(
        event["selection_source"] == "code_phase_planner"
        for event in read_surface_events
    )
    assert not any(
        event["selection_source"] == "code_phase_required"
        for event in read_surface_events
    )
    assert payload["detail"] in {"compact", "full"}
    assert payload["target_file"] == target_file
    assert any(
        event["selection_source"] == "code_phase_required_compact"
        and event["tool_name"] == "context.read_surface"
        for event in read_surface_events
    )


def test_zero_code_tool_call_budget_does_not_disable_code_phase_planner(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_modules/config.py"
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file=target_file,
    )
    module_code = (
        Path(context.champion.code_snapshot_path) / target_file
    ).read_text(encoding="utf-8") + "\n" + "\n".join(
        f"# no cap filler {idx}" for idx in range(12)
    )
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file=target_file,
            target_objectives=["total_distance"],
        )
    )
    creative = PlanningCreative(
        [
            {
                "tool_name": "context.read_surface",
                "code_phase": True,
                "args": {
                    "surface": "solver_design",
                    "target_file": target_file,
                    "detail": "full",
                },
            },
            {"stop": True},
        ],
        hypothesis=hypothesis,
        patch=PatchProposal(
            file_path=target_file,
            action="modify",
            code_content=module_code,
        ),
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(
            max_steps=0,
            max_tool_calls=0,
            max_code_tool_calls=0,
            max_observation_chars=0,
            max_wall_time_sec=3600,
        ),
    )
    state = AgenticProposalSessionState(
        session_id="session-code-cap-disabled",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-cvrp",
    )

    observations = session._run_code_context_tool_loop(
        context,
        state,
        hypothesis,
        prior_observations=[],
        code_context={"kind": "code"},
    )
    read_surface_events = [
        event.metadata
        for event in state.transcript
        if event.metadata.get("tool_name") == "context.read_surface"
        and event.metadata.get("step_id")
    ]
    start_events = [
        event.metadata
        for event in state.transcript
        if event.metadata.get("max_code_tool_calls_enabled") is False
    ]

    assert any(
        observation.tool_name == "context.read_surface"
        for observation in observations
    )
    assert any(
        event["selection_source"] == "code_phase_planner"
        for event in read_surface_events
    )
    assert start_events
    assert any(
        context.get("max_code_tool_calls_enabled") is False
        and context.get("remaining_code_tool_calls", 0) > 0
        for context in creative.planner_contexts
    )
    assert any(
        context.get("max_code_tool_calls_enabled") is False
        and context.get("reserved_for_self_check", {}).get("enabled") is False
        and context.get("reserved_for_self_check", {}).get("tool_calls") == 0
        and context.get("reserved_for_self_check", {}).get("steps") == 0
        and context.get("reserved_for_self_check", {}).get("observation_chars") == 0
        for context in creative.planner_contexts
    )
    assert not any(
        event.metadata.get("skip_reason") == "code_tool_loop_limit_reached"
        for event in state.transcript
    )


def test_disabled_observation_budget_keeps_required_solver_surface_full(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_algorithm.py"
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file=target_file,
    )
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file=target_file,
            target_objectives=["total_distance"],
        )
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(
            max_steps=0,
            max_tool_calls=0,
            max_code_tool_calls=0,
            max_observation_chars=0,
            max_wall_time_sec=3600,
        ),
    )
    state = AgenticProposalSessionState(
        session_id="session-no-cap-required-surface",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-cvrp",
    )

    observations = session._run_code_context_fixed_tools(
        context,
        state,
        hypothesis,
        prior_observations=[],
        selection_source="code_phase_required",
    )
    algorithm_read = next(
        observation
        for observation in observations
        if observation.tool_name == "context.read_algorithm_file"
    )
    surface_read = next(
        observation
        for observation in observations
        if observation.tool_name == "context.read_surface"
    )
    surface_artifact = surface_read.structured_payload["current_artifact"]

    assert algorithm_read.structured_payload["file_path"] == target_file
    assert algorithm_read.structured_payload["max_chars"] == 96000
    assert surface_read.structured_payload["detail"] == "full"
    assert surface_read.structured_payload["target_file"] == target_file
    assert surface_artifact["max_chars"] == 96000
    assert surface_artifact["truncated"] is False
    assert not any(
        event.metadata.get("selection_source") == "code_phase_required_compact"
        for event in state.transcript
    )


def test_planner_nonexistent_surface_falls_back_and_generates_patch(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_surface", "args": {"surface": "main"}},
            {"tool_name": "context.read_surface", "args": {"surface": "main"}},
        ]
    )
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_repeated_tool_calls=1),
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

    rendered = json.dumps(output, default=str, sort_keys=True)
    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    rendered_artifact = json.dumps(artifact, default=str, sort_keys=True)
    read_surface_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("tool_name") == "context.read_surface"
        and event.metadata.get("step_id")
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.hypothesis is not None
    assert output.patch is not None
    assert output.termination_reason not in {
        AgenticTerminationReason.TOOL_LOOP_LIMIT,
        AgenticTerminationReason.REPEATED_TOOL_CALL,
    }
    assert len(read_surface_events) == 4
    assert any(event["error_code"] == "not_found" for event in read_surface_events)
    assert any(
        event["status"] == "ok"
        and event["selection_source"] == "selected_surface_required"
        for event in read_surface_events
    )
    assert any(
        event["status"] == "ok" and event["selection_source"] == "code_phase_required"
        for event in read_surface_events
    )
    assert any(
        context["tool_arg_guidance"]["context.read_surface"].get(
            "allowed_surface_ids"
        )
        == ["route_local", "search_policy"]
        for context in creative.planner_contexts
        if "tool_arg_guidance" in context
    )
    assert any(
        event.metadata.get("status") == "fallback_selected"
        and event.metadata.get("fallback") == "fixed_tool_plan"
        for event in output.transcript
    )
    assert "fallback_selected" in rendered_artifact
    assert "raw_metrics_ref" not in rendered
    assert "raw_metrics_ref" not in rendered_artifact
    assert "SECRET_VALIDATION" not in rendered
    assert "SECRET_VALIDATION" not in rendered_artifact
    assert "SECRET_FROZEN" not in rendered
    assert "SECRET_FROZEN" not in rendered_artifact
