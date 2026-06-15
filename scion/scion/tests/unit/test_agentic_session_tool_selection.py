from __future__ import annotations

import hashlib
import json

from scion.proposal.engine import _split_tool_selection_context
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest
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
    guidance = session._tool_arg_guidance(context, [])

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

    read_surface_guidance = guidance["context.read_surface"]
    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert read_surface_guidance["allowed_surface_ids"] == ["solver_design"]
    assert "active_problem_boundary_rule" in read_surface_guidance
    assert "forced_surface_rule" not in read_surface_guidance
    assert guidance["feedback.query_screening"]["recommended_args"] == {
        "surface": "solver_design"
    }
    assert guidance["feedback.query_runtime"]["recommended_args"] == {
        "surface": "solver_design"
    }
    assert not [
        context
        for context in creative.planner_contexts
        if context.get("code_phase") is not True
    ]


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
    assert "do not reread broad context only to restate them" in first_blocks[0]["text"]
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


def test_tool_selection_cacheable_context_strips_volatile_receipt_ids() -> None:
    base_context = {
        "phase": "inspect",
        "allowed_tools": ["context.read_algorithm_file"],
        "allowed_tool_specs": {
            "context.read_algorithm_file": {
                "description": "Read a declared source file."
            }
        },
        "active_algorithm_facts_anchor": {
            "fact_ids": ["fact.alpha"],
            "snapshot_digest": "snapshot-digest",
            "source_observation_id": "obs-a",
            "source_tool_call_id": "tool-a",
        },
        "tool_arg_guidance": {
            "context.read_algorithm_file": {
                "allowed_paths": ["policies/baseline_algorithm.py"],
                "receipt": {
                    "artifact_id": "artifact-a",
                    "artifact_ref": "proposal-artifact://session-a/artifact-a",
                    "observation_id": "obs-a",
                    "observation_tool_call_id": "tool-a",
                    "request_id": "request-a",
                    "session_id": "session-a",
                    "source_digest": "source-digest",
                    "source_observation_id": "obs-a",
                    "source_tool_call_id": "tool-a",
                    "trace_id": "trace-a",
                    "tool_call_id": "tool-a",
                },
            }
        },
        "remaining_tool_calls": 2,
        "observations": [
            {
                "tool_name": "context.read_algorithm_file",
                "observation_id": "obs-a",
                "session_id": "session-a",
                "source_tool_call_id": "tool-a",
            }
        ],
    }
    later_context = {
        **base_context,
        "active_algorithm_facts_anchor": {
            **base_context["active_algorithm_facts_anchor"],
            "source_observation_id": "obs-b",
            "source_tool_call_id": "tool-b",
        },
        "tool_arg_guidance": {
            "context.read_algorithm_file": {
                "allowed_paths": ["policies/baseline_algorithm.py"],
                "receipt": {
                    **base_context["tool_arg_guidance"][
                        "context.read_algorithm_file"
                    ]["receipt"],
                    "artifact_id": "artifact-b",
                    "artifact_ref": "proposal-artifact://session-b/artifact-b",
                    "observation_id": "obs-b",
                    "observation_tool_call_id": "tool-b",
                    "request_id": "request-b",
                    "session_id": "session-b",
                    "source_observation_id": "obs-b",
                    "source_tool_call_id": "tool-b",
                    "trace_id": "trace-b",
                    "tool_call_id": "tool-b",
                },
            }
        },
        "observations": [
            {
                "tool_name": "context.read_algorithm_file",
                "observation_id": "obs-b",
                "session_id": "session-b",
                "source_tool_call_id": "tool-b",
            }
        ],
    }

    first_blocks, first_prompt = _split_tool_selection_context(base_context)
    later_blocks, later_prompt = _split_tool_selection_context(later_context)
    first_stable_text = first_blocks[0]["text"]
    later_stable_text = later_blocks[0]["text"]

    assert first_stable_text == later_stable_text
    assert hashlib.sha256(first_stable_text.encode()).hexdigest() == hashlib.sha256(
        later_stable_text.encode()
    ).hexdigest()
    assert "source-digest" in first_stable_text
    assert "policies/baseline_algorithm.py" in first_stable_text
    for volatile_value in (
        "artifact-a",
        "artifact-b",
        "obs-a",
        "obs-b",
        "request-a",
        "request-b",
        "session-a",
        "session-b",
        "tool-a",
        "tool-b",
        "trace-a",
        "trace-b",
    ):
        assert volatile_value not in first_stable_text
        assert volatile_value not in later_stable_text
    assert "obs-a" in first_prompt
    assert "session-a" in first_prompt
    assert "tool-a" in first_prompt
    assert "obs-b" in later_prompt
    assert "session-b" in later_prompt
    assert "tool-b" in later_prompt


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


def test_solver_design_satisfied_context_skips_optional_hypothesis_file_reads(
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
    assert planner_file_read_events == []
    assert support_file not in prompt_file_paths
    assert second_support_file not in prompt_file_paths
    assert not [
        context
        for context in creative.planner_contexts
        if context.get("code_phase") is not True
    ]
    assert not [
        event
        for event in already_succeeded_file_skips
        if event.get("selection_source") == "planner_selected"
    ]


def test_solver_design_satisfied_context_does_not_read_full_manifest_via_planner(
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
        [{"stop": True}],
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
    assert len(file_read_events) == 1
    assert file_read_events[0]["selection_source"] == "required_context_preface"
    assert file_read_events[0]["status"] == "ok"
    assert file_read_events[0]["tool_name"] == "context.read_algorithm_file"
    assert {event["status"] for event in file_read_events} == {"ok"}
    assert not [
        context
        for context in creative.planner_contexts
        if context.get("code_phase") is not True
    ]
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


def test_tool_selection_ledger_records_hypothesis_session_calls(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    hypothesis = HypothesisProposal(**_valid_hypothesis_payload())
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
            {"stop": True},
        ],
        hypothesis=hypothesis,
    )
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        artifact_store=artifact_store,
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

    ledger = output.tool_selection_ledger
    entries = ledger["entries"]
    by_tool = {entry["selected_tool"]: entry for entry in entries}
    output_artifact_path = next(
        Path(ref) for ref in output.tainted_artifact_refs if Path(ref).name == "output.json"
    )
    transcript_artifact_path = next(
        Path(ref)
        for ref in output.tainted_artifact_refs
        if Path(ref).name == "transcript.json"
    )
    output_artifact = json.loads(output_artifact_path.read_text(encoding="utf-8"))
    transcript_artifact = json.loads(
        transcript_artifact_path.read_text(encoding="utf-8")
    )

    assert ledger["schema_version"] == "agentic-tool-selection-ledger.v1"
    assert ledger["deterministic_prefetch_plan_id"] != "none"
    assert ledger["default_triad_satisfied"] is True
    assert [entry["index"] for entry in entries] == list(range(1, len(entries) + 1))
    assert by_tool["memory.query"]["source"] == "deterministic_prefetch"
    assert by_tool["feedback.query_screening"]["source"] == "deterministic_prefetch"
    assert by_tool["feedback.query_runtime"]["source"] == "deterministic_prefetch"
    assert by_tool["feedback.query_runtime"]["deterministic_prefetch_plan_id"] != "none"
    assert by_tool["memory.query"]["status"] == "executed"
    assert by_tool["feedback.query_screening"]["result_novelty"] == "new"
    assert by_tool["feedback.query_runtime"]["result_novelty"] == "new"
    assert by_tool["feedback.query_runtime"]["input_token_cost"] is None
    assert by_tool["feedback.query_runtime"]["estimated_input_tokens"] is None
    assert "stop" not in by_tool
    assert "result_in_final_prompt" in by_tool["feedback.query_runtime"]
    deterministic_observation_ids = {
        entry["result_observation_id"]
        for entry in entries
        if entry.get("source") == "deterministic_prefetch"
        and entry.get("result_observation_id")
    }
    ledger_observation_ids = {
        entry["observation_id"]
        for entry in output.observation_ledger["observations"]
        if entry.get("selection_source") == "deterministic_prefetch"
    }
    ledger_read_receipt_ids = {
        receipt["observation_id"]
        for receipt in output.observation_ledger["read_receipts"]
        if receipt.get("selection_source") == "deterministic_prefetch"
    }
    assert deterministic_observation_ids == ledger_observation_ids
    assert deterministic_observation_ids == ledger_read_receipt_ids
    assert {
        entry["tool_name"]
        for entry in output.observation_ledger["observations"]
        if entry.get("selection_source") == "deterministic_prefetch"
    } == {
        "memory.query",
        "feedback.query_screening",
        "feedback.query_runtime",
    }
    assert all(
        not entry.get("reusable_by_phases")
        for entry in output.observation_ledger["observations"]
        if entry.get("selection_source") == "deterministic_prefetch"
    )
    assert output_artifact["tool_selection_ledger"]["entry_count"] == len(entries)
    assert output_artifact["tool_selection_ledger"][
        "deterministic_prefetch_plan_id"
    ] == ledger["deterministic_prefetch_plan_id"]
    assert transcript_artifact["tool_selection_ledger"][
        "deterministic_prefetch_plan_id"
    ] == ledger["deterministic_prefetch_plan_id"]
    assert transcript_artifact["tool_selection_ledger"]["entry_count"] == len(entries)
    artifact_ledger_observation_ids = {
        entry["observation_id"]
        for entry in output_artifact["observation_ledger"]["observations"]
        if entry.get("selection_source") == "deterministic_prefetch"
    }
    artifact_ledger_read_receipt_ids = {
        receipt["observation_id"]
        for receipt in output_artifact["observation_ledger"]["read_receipts"]
        if receipt.get("selection_source") == "deterministic_prefetch"
    }
    assert deterministic_observation_ids == artifact_ledger_observation_ids
    assert deterministic_observation_ids == artifact_ledger_read_receipt_ids


def test_tool_selection_trace_records_manifest_ref_and_audit_provenance(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    trace_dir = campaign_dir / "llm_traces"
    artifact_store = FileAgenticSessionArtifactStore(campaign_dir / "agentic_sessions")
    client = ToolSelectionClient(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"intent": "stop"},
        ]
    )

    class PendingToolSelectionCreative(CreativeLayer):
        def has_pending_hypothesis_tool_plan(self, **_kwargs) -> bool:
            return True

    creative = PendingToolSelectionCreative(client, trace_dir=str(trace_dir))
    context = _context(tmp_path, policy=_tool_enabled_policy())

    output = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        artifact_store=artifact_store,
    ).run(
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

    trace_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in trace_dir.glob("*.json")
    ]
    tool_selection_trace = next(
        payload
        for payload in trace_payloads
        if payload["request_kind"] == "tool_selection"
    )
    manifest_ref = tool_selection_trace["prompt_manifest"]["artifact_ref"]
    manifest_path = Path(manifest_ref)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provenance = tool_selection_trace["agentic_session"]["provenance"]
    index_path = campaign_dir / "agentic_sessions" / "agentic_session_trace_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    session_entry = next(
        item for item in index["sessions"] if item["session_id"] == output.session_id
    )
    index_trace = next(
        trace
        for trace in session_entry["traces"]
        if trace["request_kind"] == "tool_selection"
    )

    assert output.tool_selection_ledger["deterministic_prefetch_plan_id"] != "none"
    assert "api_visible_prompt_manifest" in manifest_ref
    assert manifest["call_kind"] == "tool_selection"
    assert manifest["raw_context_audit"]["provenance"][
        "deterministic_prefetch_plan_id"
    ] == output.tool_selection_ledger["deterministic_prefetch_plan_id"]
    assert provenance["deterministic_prefetch_plan_id"] == (
        output.tool_selection_ledger["deterministic_prefetch_plan_id"]
    )
    assert provenance["prefetch_tool_names"] == [
        "memory.query",
        "feedback.query_screening",
        "feedback.query_runtime",
    ]
    assert provenance["tool_selection_ledger_digest"]
    assert index_trace["prompt_manifest_artifact_ref"].endswith(".json")
    assert index_trace["prompt_visibility_ledger_digest"]
    assert index_trace["provenance"]["deterministic_prefetch_plan_id"] == (
        provenance["deterministic_prefetch_plan_id"]
    )
    assert session_entry["provenance"]["tool_selection_ledger_digest"] == (
        provenance["tool_selection_ledger_digest"]
    )


def test_code_phase_tool_selection_ledger_records_trace_context(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    hypothesis = HypothesisProposal(**_valid_hypothesis_payload())
    creative = PlanningCreative(
        [
            {"tool_name": "context.read_branch_state", "args": {}},
            {"stop": True},
        ]
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )
    state = AgenticProposalSessionState(
        session_id="session-code-ledger",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-1",
    )

    observations = session._run_code_context_tool_loop(
        context,
        state,
        hypothesis,
        [],
        {"kind": "code", "target_file": "policies/search_policy.py"},
    )

    entries = list(state.tool_selection_ledger)
    by_tool = {entry["selected_tool"]: entry for entry in entries}
    assert observations
    assert entries[0]["source"] == "code_phase_deterministic_prefetch"
    assert entries[0]["deterministic_prefetch_plan_id"] != "none"
    assert by_tool["feedback.query_runtime"]["source"] == (
        "code_phase_deterministic_prefetch"
    )
    assert by_tool["context.read_branch_state"]["source"] == "code_phase_planner"
    assert by_tool["context.read_branch_state"]["status"] == "executed"
    assert by_tool["context.read_branch_state"]["result_novelty"] == "new"
    assert "stop" not in by_tool
    assert creative.planner_contexts[0]["_scion_trace_context"]["session_id"] == (
        "session-code-ledger"
    )
    assert creative.planner_contexts[0]["_scion_trace_context"]["phase"] == (
        AgenticProposalPhase.INSPECT_INTERFACE.value
    )


def test_prompt_manifest_sections_record_block_profile_and_reason() -> None:
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

    manifest = build_api_visible_prompt_manifest(
        session_id="session-manifest-block-profile",
        phase="diagnose",
        call_kind="tool_selection",
        prompt_context={},
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )
    catalog = manifest["section_statuses"]["tool_selection_catalog"]
    dynamic = manifest["section_statuses"]["dynamic_tool_selection_context"]

    assert catalog["block_family"] == "tool_selection"
    assert catalog["prompt_block_profile"] == "tool_selection"
    assert catalog["inclusion_reason"] == "planner_selected"
    assert dynamic["block_family"] == "tool_selection"
    assert dynamic["inclusion_reason"] == "dynamic_phase_context"


def test_prompt_manifest_records_block_family_token_accounting() -> None:
    system_blocks = [
        {
            "text": (
                "## Runtime Feedback\n"
                "screening signal is sparse\n"
                "## Solver Design Full Algorithm File Reads\n"
                "def improve():\n"
                "    return True\n"
            ),
            "cache_control": {"type": "ephemeral"},
        }
    ]
    user_prompt = (
        "## Agentic Proposal Tool Observations\n"
        "[observation:obs-1 payload_digest=abc123]\n"
        "compact visible observation\n"
    )

    manifest = build_api_visible_prompt_manifest(
        session_id="session-manifest-accounting",
        phase="diagnose",
        call_kind="hypothesis",
        prompt_context={},
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )
    accounting = manifest["block_family_accounting"]
    tokens = manifest["token_accounting"]

    assert accounting["decision_features_excluded"] is True
    assert accounting["families"]["feedback"]["section_count"] == 1
    assert accounting["families"]["source_context"]["section_count"] == 1
    assert accounting["families"]["tool_observation"]["section_count"] == 1
    assert manifest["char_budget"]["block_families"] == accounting["families"]
    assert tokens["method"] == "char_count_div_4_ceil_estimate"
    assert tokens["provider_visible_token_estimate"] == (
        accounting["total_token_estimate"]
    )
    assert tokens["block_family_token_estimates"]["feedback"] == (
        accounting["families"]["feedback"]["token_estimate"]
    )
