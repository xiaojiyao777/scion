from __future__ import annotations

from scion.tests.unit.agentic_solver_design_test_support import *

def test_hypothesis_planner_exposes_active_solver_tools_before_surface_fallback(
    tmp_path: Path,
) -> None:
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    creative = PlanningCreative([{"stop": True}])
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    session.run(
        AgenticProposalRequest(
            campaign_id="camp-cvrp",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    allowed_tools = creative.planner_contexts[0]["allowed_tools"]
    spec_names = [
        spec["name"]
        for spec in creative.planner_contexts[0]["allowed_tool_specs"]
    ]
    assert "context.read_active_solver_design" in allowed_tools
    assert "context.read_solver_call_graph" in allowed_tools
    assert "context.list_algorithm_files" in allowed_tools
    assert "context.read_algorithm_file" in allowed_tools
    assert "context.read_algorithm_symbol" in allowed_tools
    assert spec_names.index("context.read_active_solver_design") < spec_names.index(
        "context.read_surface"
    )
    file_guidance = creative.planner_contexts[0]["tool_arg_guidance"][
        "context.read_algorithm_file"
    ]
    assert file_guidance["required_first_tool"] == "context.list_algorithm_files"
    assert "policies/baseline_algorithm.py" in file_guidance["allowed_file_paths"]
    assert file_guidance["recommended_args"]["file_path"] in file_guidance[
        "allowed_file_paths"
    ]


def test_read_algorithm_tool_specs_expose_allowed_file_paths(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    specs = {
        spec["name"]: spec
        for spec in registry.allowed_tool_specs(context)
    }

    for tool_name in (
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
    ):
        spec = specs[tool_name]
        guidance = spec["structured_guidance"]
        file_path_schema = spec["input_schema"]["properties"]["file_path"]
        assert guidance["required_first_tool"] == "context.list_algorithm_files"
        assert "policies/baseline_algorithm.py" in guidance["allowed_file_paths"]
        assert file_path_schema["enum"] == guidance["allowed_file_paths"]
        assert "context.list_algorithm_files" in file_path_schema["description"]
        assert "solver_design is a surface id" in file_path_schema["description"]
        assert "solver_design" not in file_path_schema["enum"]


def test_code_phase_allowed_specs_include_active_solver_tools(tmp_path: Path) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    spec_names = {
        spec["name"] for spec in session._code_phase_allowed_tool_specs(context)
    }

    assert {
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
    }.issubset(spec_names)


def test_solver_design_fallback_plan_reads_active_snapshot_and_call_graph(
    tmp_path: Path,
) -> None:
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(change_locus="solver_design")
    )
    session = AgenticProposalSession(
        FakeCreative(hypothesis=hypothesis),
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-cvrp",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )
    tool_names = [
        event.metadata.get("tool_name")
        for event in output.transcript
        if event.metadata.get("selection_source") == "fallback_selected"
    ]

    assert "context.list_algorithm_files" in tool_names
    assert "context.read_active_solver_design" in tool_names
    assert "context.read_solver_call_graph" in tool_names
    assert tool_names.index("context.list_algorithm_files") < tool_names.index(
        "context.read_active_solver_design"
    )


def test_invalid_solver_design_file_path_fallback_lists_allowed_files_first(
    tmp_path: Path,
) -> None:
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    creative = PlanningCreative(
        [
            {
                "tool_name": "context.read_algorithm_file",
                "args": {
                    "surface": "solver_design",
                    "file_path": "solver_design",
                },
            }
        ],
        hypothesis=HypothesisProposal(
            **_valid_hypothesis_payload(change_locus="solver_design")
        ),
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )
    state = AgenticProposalSessionState(
        session_id="session-invalid-solver-design-path",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-cvrp",
    )

    observations = session._run_bounded_planner_tools(context, state)

    tool_names = [observation.tool_name for observation in observations]
    invalid_observation = observations[0]
    rendered = json.dumps(
        {
            "observations": observations,
            "planner_contexts": creative.planner_contexts,
            "transcript": state.transcript,
        },
        sort_keys=True,
        default=str,
    )
    assert invalid_observation.tool_name == "context.read_algorithm_file"
    assert invalid_observation.is_error is True
    assert invalid_observation.structured_payload["file_path"] == "<path_rejected>"
    assert invalid_observation.structured_payload["required_first_tool"] == (
        "context.list_algorithm_files"
    )
    assert "policies/baseline_algorithm.py" in invalid_observation.structured_payload[
        "allowed_file_paths"
    ]
    assert "context.list_algorithm_files" in tool_names
    assert tool_names.index("context.list_algorithm_files") < tool_names.index(
        "context.read_active_solver_design"
    )
    assert tool_names.index("context.list_algorithm_files") < tool_names.index(
        "context.read_solver_call_graph"
    )
    assert str(tmp_path) not in rendered


def test_solver_design_grounding_missing_fails_closed(tmp_path: Path) -> None:
    base_context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    context = replace(
        base_context,
        policy=replace(base_context.policy, allow_champion_code_read=False),
    )
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(change_locus="solver_design")
    )
    session = AgenticProposalSession(
        FakeCreative(hypothesis=hypothesis),
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-cvrp",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == "failed"
    assert output.failure_detail is not None
    assert "context.read_active_solver_design" in output.failure_detail
    assert "context.read_solver_call_graph" in output.failure_detail
