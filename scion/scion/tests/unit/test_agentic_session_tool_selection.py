from __future__ import annotations

import json

from scion.proposal.engine import _split_tool_selection_context
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
            target_file="policies/baseline_algorithm.py",
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


def test_code_phase_planner_receives_target_aware_visible_file_receipts(
    tmp_path: Path,
) -> None:
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    target_file = "policies/baseline_modules/local_search.py"
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file=target_file,
            mechanism_changes=[
                {"id": "same_route_reinsertion", "change_type": "add"}
            ],
        )
    )
    code_context = {
        "research_surface_name": "solver_design",
        "change_locus": "solver_design",
        "target_file": target_file,
        "target_file_code": "def local_search():\n    pass\n",
        "solver_design_branch_current_integration_files": (
            "### policies/baseline_algorithm.py\n```python\n"
            "def solve():\n    pass\n```\n"
            "### policies/baseline_modules/scheduler.py\n```python\n"
            "class _Scheduler:\n    pass\n```"
        ),
    }
    session = AgenticProposalSession(
        FakeCreative(hypothesis=hypothesis),
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    source_context = session._code_phase_source_visibility_context(
        hypothesis,
        [],
        code_context=code_context,
    )
    mandatory_paths = {
        item["file_path"] for item in source_context["mandatory_visible_files"]
    }
    assert target_file in mandatory_paths
    assert "policies/baseline_algorithm.py" in mandatory_paths
    assert "policies/baseline_modules/scheduler.py" in mandatory_paths
    guidance = session._code_tool_arg_guidance(
        context,
        hypothesis,
        [],
        code_context,
    )
    read_guidance = guidance["context.read_algorithm_file"]
    assert read_guidance["recommended_args"]["file_path"] == target_file
    assert target_file in read_guidance["target_aware_read_priority"]
    assert "duplicate_read_rule" in read_guidance


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


def test_tool_selection_prompt_splits_cacheable_catalog_from_dynamic_context() -> None:
    system_blocks, user_prompt = _split_tool_selection_context(
        {
            "phase": "inspect",
            "allowed_tools": ["context.read_surface"],
            "allowed_tool_specs": {
                "context.read_surface": {"description": "Read a declared surface."}
            },
            "remaining_tool_calls": 3,
            "observations": [{"tool_name": "context.list_surfaces"}],
        }
    )

    assert len(system_blocks) == 1
    assert all(block.get("cache_control") for block in system_blocks)
    assert "Tool Selection Catalog" in system_blocks[0]["text"]
    assert "context.read_surface" in system_blocks[0]["text"]
    assert "allowed_tool_specs" not in user_prompt
    assert "remaining_tool_calls" in user_prompt
    assert "context.list_surfaces" in user_prompt


def test_tool_selection_prompt_caches_stable_planner_context() -> None:
    base_context = {
        "phase": "inspect",
        "allowed_tools": ["context.read_active_solver_design"],
        "allowed_tool_specs": {
            "context.read_active_solver_design": {
                "description": "Read active solver facts."
            }
        },
        "active_algorithm_facts_anchor": {
            "fact_ids": ["cvrp.destroy_repair.random_removal_destroy"],
            "source_observation_id": "obs-a",
            "source_tool_call_id": "tool-a",
            "snapshot_digest": "solver-digest",
        },
        "hypothesis_constraints": {"forced_surface": "solver_design"},
        "tool_arg_guidance": {
            "context.read_algorithm_file": {
                "allowed_paths": ["policies/baseline_modules/scheduler.py"]
            }
        },
        "remaining_tool_calls": 3,
        "observations": [{"tool_name": "context.list_surfaces"}],
    }
    later_context = {
        **base_context,
        "remaining_tool_calls": 2,
        "observations": [
            {"tool_name": "context.list_surfaces"},
            {"tool_name": "context.read_active_solver_design"},
        ],
    }

    first_blocks, first_prompt = _split_tool_selection_context(base_context)
    later_blocks, later_prompt = _split_tool_selection_context(later_context)
    stable_json = first_blocks[0]["text"]
    stable_payload_start = stable_json.index(
        "{", stable_json.index("## Stable Tool Selection Context")
    )
    stable_payload = json.loads(
        stable_json[stable_payload_start:]
    )

    assert first_blocks[0]["text"] == later_blocks[0]["text"]
    assert "Stable Tool Selection Context" in first_blocks[0]["text"]
    assert "active_algorithm_facts_anchor" in first_blocks[0]["text"]
    assert "tool_arg_guidance" in first_blocks[0]["text"]
    assert "source_observation_id" not in first_blocks[0]["text"]
    assert stable_payload["active_algorithm_facts_anchor"]["snapshot_digest"] == (
        "solver-digest"
    )
    assert "active_algorithm_facts_anchor" not in first_prompt
    assert "tool_arg_guidance" not in first_prompt
    assert "remaining_tool_calls" in first_prompt
    assert "context.read_active_solver_design" in later_prompt


def test_algorithm_file_reusable_observations_are_scoped_by_path_and_budget() -> None:
    path = "policies/baseline_algorithm.py"
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
    path = "policies/baseline_algorithm.py"
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


def test_code_phase_solver_design_file_read_budget_keeps_active_manifest_available(
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
            "policies/baseline_modules/construction.py",
            "policies/baseline_modules/local_search.py",
            "policies/baseline_modules/destroy_repair.py",
        )
    ]

    assert not agentic_session_module._solver_design_code_algorithm_file_read_budget_exhausted(
        context,
        observations,
        hypothesis=hypothesis,
        next_args={
            "surface": "solver_design",
            "file_path": "policies/baseline_modules/config.py",
        },
    )
    assert not agentic_session_module._solver_design_code_algorithm_file_read_budget_exhausted(
        context,
        observations,
        hypothesis=hypothesis,
        next_args={
            "surface": "solver_design",
            "file_path": "policies/baseline_modules/state.py",
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
    assert agentic_session_module._solver_design_code_algorithm_file_read_budget_exhausted(
        context,
        observations,
        hypothesis=hypothesis,
        next_args={
            "surface": "solver_design",
            "file_path": "policies/experimental_solver.py",
        },
    )


def test_planner_solver_design_file_read_budget_keeps_target_and_dependencies_available(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_modules/acceptance.py"
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file=target_file,
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
            "policies/baseline_modules/local_search.py",
            "policies/baseline_modules/destroy_repair.py",
            "policies/baseline_modules/acceptance.py",
            "policies/baseline_modules/config.py",
            "policies/baseline_modules/construction.py",
            "policies/baseline_algorithm.py",
        )
    ]

    for file_path in (
        target_file,
        "policies/baseline_modules/scheduler.py",
        "policies/baseline_modules/state.py",
    ):
        assert not agentic_session_module._solver_design_planner_algorithm_file_read_budget_exhausted(
            context,
            observations,
            next_tool_name="context.read_algorithm_file",
            next_args={
                "surface": "solver_design",
                "file_path": file_path,
                "max_chars": 24000,
            },
        )
    assert agentic_session_module._solver_design_planner_algorithm_file_read_budget_exhausted(
        context,
        observations,
        next_tool_name="context.read_algorithm_file",
        next_args={
            "surface": "solver_design",
            "file_path": "policies/experimental_solver.py",
            "max_chars": 24000,
        },
    )


def test_solver_design_file_read_budget_ignores_inherited_read_receipts(
    tmp_path: Path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/acceptance.py",
            target_objectives=["total_distance"],
        )
    )
    observations = []
    for path in (
        "policies/baseline_algorithm.py",
        "policies/baseline_modules/scheduler.py",
        "policies/baseline_modules/construction.py",
        "policies/baseline_modules/local_search.py",
        "policies/baseline_modules/destroy_repair.py",
    ):
        observations.append(
            ProposalObservation(
                observation_id=f"receipt-{path}",
                session_id="session-receipts",
                tool_name="context.read_algorithm_file",
                tool_call_id="tool-receipt",
                observation_type="already_observed",
                summary="Already observed.",
                structured_payload={
                    "already_observed": True,
                    "file_path": path,
                    "readable": True,
                    "max_chars": 24000,
                    "coverage": {
                        "max_chars": 24000,
                        "content_preview_chars": 1000,
                        "size_chars": 1000,
                        "truncated": False,
                    },
                },
                exposure_level=ProposalExposureLevel.CHAMPION_CODE,
            )
        )

    assert not agentic_session_module._solver_design_code_algorithm_file_read_budget_exhausted(
        context,
        observations,
        hypothesis=hypothesis,
        next_args={
            "surface": "solver_design",
            "file_path": "policies/baseline_modules/config.py",
            "max_chars": 24000,
        },
    )


def test_algorithm_symbol_reusable_observations_are_scoped_by_file_and_symbol() -> None:
    path = "policies/baseline_modules/local_search.py"
    other_path = "policies/baseline_algorithm.py"
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
    target_file = "policies/baseline_algorithm.py"
    support_file = "policies/baseline_modules/local_search.py"
    second_support_file = "policies/baseline_modules/destroy_repair.py"
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
                "tool_name": "context.read_algorithm_file",
                "args": {
                    "surface": "solver_design",
                    "file_path": support_file,
                    "max_chars": 4000,
                },
            },
            {
                "tool_name": "context.read_algorithm_file",
                "args": {
                    "surface": "solver_design",
                    "file_path": second_support_file,
                    "max_chars": 4000,
                },
            },
            {"stop": True},
        ],
        hypothesis=hypothesis,
        patch=PatchProposal(
            file_path=target_file,
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
    planner_file_read_events = [
        event
        for event in file_read_events
        if event.get("selection_source") == "planner_selected"
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
    assert any(
        event["tool_name"] == "context.read_active_solver_map"
        and event["selection_source"] == "required_context_preface"
        for event in step_events
    )
    assert not [
        event
        for event in step_events
        if event["tool_name"]
        in {"context.read_operator_registry", "context.read_algorithm_slice"}
        and event["selection_source"] == "required_context_preface"
    ]
    assert {
        event["tool_name"]
        for event in step_events
        if event["tool_name"]
        in {"context.read_operator_registry", "context.read_algorithm_slice"}
        and event["selection_source"] == "planner_map_followup_required"
    } == {"context.read_operator_registry", "context.read_algorithm_slice"}
    assert [event["status"] for event in planner_file_read_events[:2]] == [
        "ok",
        "ok",
    ]
    assert prompt_file_paths >= {support_file, second_support_file}
    assert not [
        event
        for event in already_succeeded_file_skips
        if event.get("selection_source") == "planner_selected"
    ]


def test_solver_design_planner_can_read_full_active_algorithm_manifest(
    tmp_path: Path,
) -> None:
    files = [
        "policies/baseline_algorithm.py",
        "policies/baseline_modules/scheduler.py",
        "policies/baseline_modules/construction.py",
        "policies/baseline_modules/local_search.py",
        "policies/baseline_modules/destroy_repair.py",
        "policies/baseline_modules/acceptance.py",
        "policies/baseline_modules/config.py",
        "policies/baseline_modules/state.py",
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
                "    context.record_iteration('search', 1)\n"
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
    assert len(file_read_events) == len(files)
    assert {event["status"] for event in file_read_events} == {"ok"}
    assert not cap_events


def test_solver_design_file_reads_cannot_starve_required_surface_inventory(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_algorithm.py"
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
