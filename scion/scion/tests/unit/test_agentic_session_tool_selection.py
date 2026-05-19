from __future__ import annotations

from scion.tests.unit.agentic_session_test_support import *

def test_agentic_active_boundary_tool_guidance_is_not_forced_surface(
    tmp_path: Path,
) -> None:
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/solver_algorithm.py",
        )
    )
    creative = PlanningCreative(
        [{"stop": True}],
        hypothesis=hypothesis,
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
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    read_surface_guidance = creative.planner_contexts[0]["tool_arg_guidance"][
        "context.read_surface"
    ]
    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert read_surface_guidance["allowed_surface_ids"] == ["solver_design"]
    assert "active_problem_boundary_rule" in read_surface_guidance
    assert "forced_surface_rule" not in read_surface_guidance
    assert creative.planner_contexts[0]["tool_arg_guidance"][
        "feedback.query_screening"
    ]["recommended_args"] == {"surface": "solver_design"}
    assert creative.planner_contexts[0]["tool_arg_guidance"][
        "feedback.query_runtime"
    ]["recommended_args"] == {"surface": "solver_design"}


def test_feedback_query_args_use_single_active_boundary_without_forcing(
    tmp_path: Path,
) -> None:
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    multi_boundary_context = replace(
        context,
        active_problem_boundary_surfaces=("solver_design", "runtime_policy"),
    )
    forced_context = replace(
        multi_boundary_context,
        forced_surface="solver_design",
    )

    assert agentic_session_module._feedback_query_args(context) == {
        "surface": "solver_design"
    }
    assert agentic_session_module._feedback_query_args(multi_boundary_context) == {}
    assert agentic_session_module._feedback_query_args(forced_context) == {
        "surface": "solver_design"
    }


def test_tool_selection_helpers_filter_model_and_code_phase_allowlists(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    tool_names = (
        "",
        "feedback.query_holdout_summary",
        "proposal.schema_preview",
        "proposal.target_permission_preview",
        "proposal.algorithm_smoke",
        "proposal.contract_preview",
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
        "context.read_surface",
        "context.read_surface",
        "feedback.query_runtime",
    )

    model_facing = agentic_session_module._filter_model_facing_tool_names(
        tool_names,
        context,
    )
    code_phase = agentic_session_module._filter_code_phase_tool_names(
        tool_names,
        context,
    )

    assert model_facing == (
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
        "context.read_surface",
        "feedback.query_runtime",
    )
    assert set(code_phase) == {
        "context.list_algorithm_files",
        "context.read_active_solver_design",
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
        "context.read_solver_call_graph",
        "context.read_surface",
        "feedback.query_runtime",
    }


def test_algorithm_file_reusable_observations_are_scoped_by_path_and_budget() -> None:
    path = "policies/solver_algorithm.py"
    other_path = "policies/baseline_modules/local_search.py"
    observation = _algorithm_read_observation(
        "context.read_algorithm_file",
        _algorithm_file_payload(
            path,
            max_chars=12000,
            preview_chars=8000,
            size_chars=8000,
        ),
    )
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file=path,
        )
    )

    same_request = {
        "surface": "solver_design",
        "file_path": path,
        "max_chars": 12000,
    }
    smaller_request = {
        "surface": "solver_design",
        "file_path": path,
        "max_chars": 6000,
    }
    larger_request = {
        "surface": "solver_design",
        "file_path": path,
        "max_chars": 16000,
    }
    other_file_request = {
        "surface": "solver_design",
        "file_path": other_path,
        "max_chars": 12000,
    }

    assert agentic_session_module._has_successful_reusable_observation(
        [observation],
        "context.read_algorithm_file",
        same_request,
    )
    assert agentic_session_module._has_successful_reusable_observation(
        [observation],
        "context.read_algorithm_file",
        smaller_request,
    )
    assert agentic_session_module._has_successful_code_phase_reusable_observation(
        [observation],
        "context.read_algorithm_file",
        same_request,
        hypothesis=hypothesis,
    )
    assert not agentic_session_module._has_successful_reusable_observation(
        [observation],
        "context.read_algorithm_file",
        larger_request,
    )
    assert not agentic_session_module._has_successful_reusable_observation(
        [observation],
        "context.read_algorithm_file",
        other_file_request,
    )
    assert not agentic_session_module._has_successful_code_phase_reusable_observation(
        [observation],
        "context.read_algorithm_file",
        other_file_request,
        hypothesis=hypothesis,
    )


def test_algorithm_file_truncated_or_short_preview_is_not_reused() -> None:
    path = "policies/solver_algorithm.py"
    truncated = _algorithm_read_observation(
        "context.read_algorithm_file",
        _algorithm_file_payload(
            path,
            max_chars=12000,
            preview_chars=12000,
            size_chars=16000,
            truncated=True,
        ),
    )
    short_preview = _algorithm_read_observation(
        "context.read_algorithm_file",
        _algorithm_file_payload(
            path,
            max_chars=12000,
            preview_chars=100,
            size_chars=5000,
        ),
    )
    request = {
        "surface": "solver_design",
        "file_path": path,
        "max_chars": 6000,
    }

    assert not agentic_session_module._has_successful_reusable_observation(
        [truncated],
        "context.read_algorithm_file",
        request,
    )
    assert not agentic_session_module._has_successful_reusable_observation(
        [short_preview],
        "context.read_algorithm_file",
        request,
    )


def test_code_phase_solver_design_file_read_budget_keeps_target_available(
    tmp_path: Path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    target_file = "policies/baseline_modules/acceptance.py"
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file=target_file,
            target_objectives=["total_distance"],
        )
    )
    observations = [
        _algorithm_read_observation(
            "context.read_algorithm_file",
            _algorithm_file_payload(
                path,
                max_chars=12000,
                preview_chars=1000,
                size_chars=1000,
            ),
        )
        for path in (
            "policies/baseline_algorithm.py",
            "policies/baseline_modules/scheduler.py",
            "policies/baseline_modules/local_search.py",
        )
    ]

    assert agentic_session_module._solver_design_code_algorithm_file_read_budget_exhausted(
        context,
        observations,
        hypothesis=hypothesis,
        next_args={
            "surface": "solver_design",
            "file_path": "policies/baseline_modules/destroy_repair.py",
        },
    )
    assert not agentic_session_module._solver_design_code_algorithm_file_read_budget_exhausted(
        context,
        observations,
        hypothesis=hypothesis,
        next_args={
            "surface": "solver_design",
            "file_path": target_file,
        },
    )


def test_algorithm_symbol_reusable_observations_are_scoped_by_file_and_symbol() -> None:
    path = "policies/baseline_modules/local_search.py"
    other_path = "policies/solver_algorithm.py"
    symbol = "_inter_route_or_opt"
    observation = _algorithm_read_observation(
        "context.read_algorithm_symbol",
        _algorithm_symbol_payload(
            path,
            symbol,
            preview_chars=2000,
        ),
    )
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file=path,
        )
    )

    same_request = {
        "surface": "solver_design",
        "file_path": path,
        "symbol": symbol,
        "max_chars": 6000,
    }
    other_symbol_request = {
        "surface": "solver_design",
        "file_path": path,
        "symbol": "_two_opt",
        "max_chars": 6000,
    }
    other_file_request = {
        "surface": "solver_design",
        "file_path": other_path,
        "symbol": symbol,
        "max_chars": 6000,
    }

    assert agentic_session_module._has_successful_reusable_observation(
        [observation],
        "context.read_algorithm_symbol",
        same_request,
    )
    assert agentic_session_module._has_successful_code_phase_reusable_observation(
        [observation],
        "context.read_algorithm_symbol",
        same_request,
        hypothesis=hypothesis,
    )
    assert not agentic_session_module._has_successful_reusable_observation(
        [observation],
        "context.read_algorithm_symbol",
        other_symbol_request,
    )
    assert not agentic_session_module._has_successful_reusable_observation(
        [observation],
        "context.read_algorithm_symbol",
        other_file_request,
    )
    assert not agentic_session_module._has_successful_code_phase_reusable_observation(
        [observation],
        "context.read_algorithm_symbol",
        other_symbol_request,
        hypothesis=hypothesis,
    )


def test_planner_reads_distinct_algorithm_files_without_already_succeeded_skip(
    tmp_path: Path,
) -> None:
    target_file = "policies/solver_algorithm.py"
    support_file = "policies/baseline_modules/local_search.py"
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
    creative = PlanningCreative(
        [
            {
                "tool_name": "context.list_algorithm_files",
                "args": {"surface": "solver_design", "include_inactive": True},
            },
            {
                "tool_name": "context.read_algorithm_file",
                "args": {
                    "surface": "solver_design",
                    "file_path": target_file,
                    "max_chars": 4000,
                },
            },
            {
                "tool_name": "context.read_algorithm_file",
                "args": {
                    "surface": "solver_design",
                    "file_path": support_file,
                    "max_chars": 4000,
                },
            },
            {
                "tool_name": "context.read_active_solver_design",
                "args": {"surface": "solver_design"},
            },
            {
                "tool_name": "context.read_solver_call_graph",
                "args": {"surface": "solver_design"},
            },
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
            {"stop": True},
        ],
        hypothesis=hypothesis,
        patch=PatchProposal(
            file_path=target_file,
            action="modify",
            code_content=(
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return context.nearest_neighbor()\n"
            ),
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
    file_read_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("step_id")
        and event.metadata.get("tool_name") == "context.read_algorithm_file"
    ]
    step_events = [
        event.metadata for event in output.transcript if event.metadata.get("step_id")
    ]
    already_succeeded_file_skips = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("tool_name") == "context.read_algorithm_file"
        and event.metadata.get("skip_reason") == "already_succeeded"
    ]
    prompt_file_paths = {
        observation["structured_payload"]["file_path"]
        for observation in creative.hypothesis_contexts[0][
            "agentic_tool_observations"
        ]
        if observation["tool_name"] == "context.read_algorithm_file"
    }

    assert output.status == AgenticProposalStatus.COMPLETED
    assert [
        (event["tool_name"], event["selection_source"])
        for event in step_events[:5]
    ] == [
        ("context.list_surfaces", "required_context_preface"),
        ("context.read_problem", "required_context_preface"),
        ("context.list_algorithm_files", "required_context_preface"),
        ("context.read_active_solver_design", "required_context_preface"),
        ("context.read_solver_call_graph", "required_context_preface"),
    ]
    assert [event["status"] for event in file_read_events[:2]] == ["ok", "ok"]
    assert [event["selection_source"] for event in file_read_events[:2]] == [
        "planner_selected",
        "planner_selected",
    ]
    assert prompt_file_paths >= {target_file, support_file}
    assert not already_succeeded_file_skips


def test_solver_design_planner_does_not_default_read_full_algorithm_object(
    tmp_path: Path,
) -> None:
    files = [
        "policies/solver_algorithm.py",
        "policies/baseline_modules/local_search.py",
        "policies/baseline_modules/destroy_repair.py",
        "policies/baseline_modules/acceptance.py",
    ]
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file=files[0],
    )
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file=files[0],
            target_objectives=["total_distance"],
        )
    )
    creative = PlanningCreative(
        [
            {
                "tool_name": "context.read_algorithm_file",
                "args": {
                    "surface": "solver_design",
                    "file_path": file_path,
                    "max_chars": 24000,
                },
            }
            for file_path in files
        ],
        hypothesis=hypothesis,
        patch=PatchProposal(
            file_path=files[0],
            action="modify",
            code_content=(
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return context.nearest_neighbor()\n"
            ),
        ),
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_tool_calls=24, max_steps=30),
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
    file_read_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("step_id")
        and event.metadata.get("tool_name") == "context.read_algorithm_file"
    ]
    cap_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("skip_reason")
        == "solver_design_algorithm_file_read_budget_reserved"
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert len(file_read_events) == 3
    assert {event["status"] for event in file_read_events} == {"ok"}
    assert cap_events


def test_solver_design_file_reads_cannot_starve_required_surface_inventory(
    tmp_path: Path,
) -> None:
    target_file = "policies/solver_algorithm.py"
    support_file = "policies/baseline_modules/local_search.py"
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
    )
    creative = PlanningCreative(
        [
            {
                "tool_name": "context.read_algorithm_file",
                "args": {
                    "surface": "solver_design",
                    "file_path": target_file,
                    "max_chars": 24000,
                },
            },
            {
                "tool_name": "context.read_algorithm_file",
                "args": {
                    "surface": "solver_design",
                    "file_path": support_file,
                    "max_chars": 24000,
                },
            },
            {"stop": True},
        ]
    )
    config = AgenticToolLoopConfig(
        max_steps=12,
        max_tool_calls=12,
        max_observation_chars=96000,
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    state = AgenticProposalSessionState(
        session_id="session-preface-budget",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-1",
        tool_loop_config=config.__dict__,
    )

    observations = session._run_initial_tool_loop(context, state)

    assert session._missing_required_context_error(
        observations,
        context=context,
    ) is None
    assert [observation.tool_name for observation in observations[:5]] == [
        "context.list_surfaces",
        "context.read_problem",
        "context.list_algorithm_files",
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
    ]
    assert any(
        observation.tool_name == "context.read_algorithm_file"
        and observation.structured_payload.get("file_path") == target_file
        for observation in observations
    )
    assert not any(
        "missing required proposal context tools: context.list_surfaces"
        in event.metadata.get("detail", "")
        for event in state.transcript
    )


