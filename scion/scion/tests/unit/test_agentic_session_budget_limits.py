from __future__ import annotations

from scion.tests.unit.agentic_session_test_support import *

def test_agentic_session_compacts_feedback_observations_for_internal_budget() -> None:
    screening = ProposalObservation(
        observation_id="screening-1",
        session_id="session-1",
        tool_name="feedback.query_screening",
        tool_call_id="tool-4",
        observation_type="screening_feedback",
        summary="Returned 4 of 4 screening feedback row(s).",
        structured_payload={
            "query_scope": {"campaign_id": "camp-1", "recent_first": True},
            "available_screening_step_count": 4,
            "matched_screening_step_count": 4,
            "screening_steps": [
                {
                    "round_num": 2,
                    "branch_id": "branch-1",
                    "surface": "solver_design",
                    "action": "modify",
                    "target_file": "policies/solver_algorithm.py",
                    "gate_outcome": "abandoned",
                    "reason_codes": ["SCREENING_FAIL_WIN_RATE"],
                    "stats": {
                        "wins": 1,
                        "losses": 0,
                        "ties": 15,
                        "win_rate": 0.0625,
                        "median_delta": 0.0,
                        "runtime_ratio_median": 0.9,
                    },
                    "candidate_surface_runtime_summary": {
                        "fields": {
                            f"solver_algorithm_phase_delta_sum_{idx}": {
                                "present": 16,
                                "numeric_summary": {
                                    "weighted_sum": idx,
                                    "values": ["x" * 500] * 8,
                                },
                            }
                            for idx in range(32)
                        }
                    },
                    "candidate_surface_runtime_attribution": {
                        "runtime_field_highlights": [
                            {
                                "field": f"solver_algorithm_move_attempts_{idx}",
                                "present": 16,
                                "numeric_summary": {"weighted_sum": idx},
                                "values": ["x" * 300] * 4,
                            }
                            for idx in range(16)
                        ]
                    },
                    "case_feedback": [
                        {"pair": idx, "detail": "x" * 1000} for idx in range(16)
                    ],
                }
                for _ in range(4)
            ],
        },
        exposure_level=ProposalExposureLevel.SCREENING_DETAIL,
    )
    runtime = ProposalObservation(
        observation_id="runtime-1",
        session_id="session-1",
        tool_name="feedback.query_runtime",
        tool_call_id="tool-5",
        observation_type="runtime_feedback",
        summary="Returned screening-derived runtime feedback.",
        structured_payload={
            "query_scope": {"campaign_id": "camp-1", "recent_first": True},
            "runtime_feedback": "runtime line\n" * 1000,
            "runtime_failure_guidance": "guidance line\n" * 1000,
            "screening_runtime_attribution": [
                {
                    "round_num": 2,
                    "surface": "solver_design",
                    "runtime_field_highlights": [
                        {
                            "field": f"solver_algorithm_phase_delta_sum_{idx}",
                            "numeric_summary": {"weighted_sum": idx},
                            "values": ["x" * 300] * 4,
                        }
                        for idx in range(16)
                    ],
                }
                for _ in range(4)
            ],
            "research_diagnosis": {
                "schema_version": "research-diagnosis.v1",
                "screening_only": True,
                "screening_step_count": 4,
                "reason_code_counts": {"SCREENING_FAIL_WIN_RATE": 4},
                "failure_mode_tags": ["screening_win_rate_failure"],
                "runtime_signal_rows": [
                    {"surface": "solver_design", "highlight_fields": ["x"] * 20}
                    for _ in range(8)
                ],
                "recent_screening_steps": [
                    {
                        "round_num": 2,
                        "surface": "solver_design",
                        "stats": {"win_rate": 0.0625, "median_delta": 0.0},
                    }
                    for _ in range(8)
                ],
                "next_hypothesis_requirements": ["change the algorithm"] * 8,
            },
            "screening_only": True,
            "metrics_file_refs_exposed": False,
        },
        exposure_level=ProposalExposureLevel.SCREENING_DETAIL,
    )

    compact_screening = _compact_feedback_observation_for_budget(screening)
    compact_runtime = _compact_feedback_observation_for_budget(runtime)

    assert _json_size(_observation_prompt_payload(compact_screening)) < _json_size(
        _observation_prompt_payload(screening)
    )
    assert _json_size(_observation_prompt_payload(compact_runtime)) < _json_size(
        _observation_prompt_payload(runtime)
    )
    assert _json_size(_observation_prompt_payload(compact_screening)) < 7000
    assert _json_size(_observation_prompt_payload(compact_runtime)) < 7000
    assert compact_screening.structured_payload["screening_steps"]
    assert (
        compact_runtime.structured_payload["research_diagnosis"]["screening_step_count"]
        == 4
    )
    rendered = json.dumps(
        [
            compact_screening.structured_payload,
            compact_runtime.structured_payload,
        ],
        sort_keys=True,
    )
    assert "solver_design" in rendered
    assert "case_feedback" not in rendered


def test_optional_read_surface_near_budget_returns_bounded_error(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    config = AgenticToolLoopConfig(max_observation_chars=24000)
    state = AgenticProposalSessionState(
        session_id="session-budget",
        campaign_id="camp-1",
        branch_id="branch-1",
        observation_chars_used=23000,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )

    observation = session._call_tool(
        context,
        state,
        AgenticProposalPhase.DIAGNOSE,
        "context.read_surface",
        {"surface": "search_policy"},
        selection_source="planner_selected",
    )

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.RESULT_TOO_LARGE
    assert observation.structured_payload["budget_action"] == "tool_denied"
    assert state.observation_chars_used <= config.max_observation_chars
    assert state.observation_chars_used - 23000 < 1000
    assert any(
        event.metadata.get("error_code") == "result_too_large"
        and event.metadata.get("selection_source") == "planner_selected"
        for event in state.transcript
    )


def test_optional_read_surface_preserves_self_check_observation_reserve(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    config = AgenticToolLoopConfig(max_observation_chars=48000)
    state = AgenticProposalSessionState(
        session_id="session-reserve",
        campaign_id="camp-1",
        branch_id="branch-1",
        observation_chars_used=36000,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )

    observation = session._call_tool(
        context,
        state,
        AgenticProposalPhase.DIAGNOSE,
        "context.read_surface",
        {"surface": "search_policy"},
        selection_source="planner_selected",
    )

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.RESULT_TOO_LARGE
    assert observation.structured_payload["budget_action"] == "tool_denied"
    assert state.observation_chars_used <= config.max_observation_chars


def test_agentic_session_preserves_preview_after_heavy_code_phase_surface_read(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    registry = ProposalToolRegistry.default_read_only()
    registry._tools["memory.query"] = LargeObservationTool(
        "memory.query",
        payload_chars=70000,
    )
    registry._tools["context.read_surface"] = _BudgetAwareReadSurfaceTool()
    config = AgenticToolLoopConfig(
        max_observation_chars=96000,
        max_code_repair_attempts=0,
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=registry,
        tool_loop_config=config,
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
    preview_events = [
        event
        for event in tool_events
        if event["tool_name"]
        in {"proposal.contract_preview", "proposal.algorithm_smoke"}
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.self_check.contract_preview_passed is True
    assert output.tool_budget_used["observation_chars"] <= (
        config.max_observation_chars - session._minimum_budgeted_observation_chars()
    )
    assert any(
        event["tool_name"] == "context.read_surface"
        and event["selection_source"] == "code_phase_required_compact"
        for event in tool_events
    )
    assert any(
        event["tool_name"] == "proposal.contract_preview"
        and event["status"] == "ok"
        for event in preview_events
    )
    assert any(
        event["tool_name"] == "proposal.algorithm_smoke"
        and event["status"] == "ok"
        for event in preview_events
    )
    assert not any(
        event["tool_name"] in {"proposal.contract_preview", "proposal.algorithm_smoke"}
        and event.get("observation_type") == "tool_skipped"
        for event in preview_events
    )


def test_agentic_session_wall_time_timeout_returns_typed_failure(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_wall_time_sec=0.0),
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

    assert output.status == AgenticProposalStatus.FAILED
    assert output.termination_reason == AgenticTerminationReason.SESSION_TIMEOUT
    assert output.hypothesis is None
    assert output.patch is None
    assert output.tool_budget_used["tool_calls"] == 0


def test_agentic_session_repeated_tool_call_fuse_falls_back(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.list_surfaces", "args": {}},
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
    error_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("error_code") == "repeated_tool_call_fuse"
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.termination_reason == AgenticTerminationReason.COMPLETED
    assert output.patch is not None
    assert error_events
    assert any(
        event.metadata.get("selection_source") == "fallback_selected"
        for event in output.transcript
    )


def test_agentic_idempotency_key_is_stable_and_anchor_config_sensitive(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    config = AgenticToolLoopConfig(max_tool_calls=4)
    request = AgenticProposalRequest(
        campaign_id="camp-1",
        branch=context.branch,
        champion=context.champion,
        hypothesis_context={},
        build_code_context=lambda _hypothesis: {"kind": "code"},
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
        tool_context=context,
    )
    same_request = AgenticProposalRequest(
        campaign_id="camp-1",
        branch=context.branch,
        champion=context.champion,
        hypothesis_context={"ignored_for_key": "different prompt text"},
        build_code_context=lambda _hypothesis: {"kind": "code"},
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
        tool_context=context,
    )
    changed_branch = Branch(
        branch_id=context.branch.branch_id,
        state=context.branch.state,
        base_champion_id=context.branch.base_champion_id,
        base_champion_hash="different-base",
    )
    changed_request = AgenticProposalRequest(
        campaign_id="camp-1",
        branch=changed_branch,
        champion=context.champion,
        hypothesis_context={},
        build_code_context=lambda _hypothesis: {"kind": "code"},
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
        tool_context=replace(context, branch=changed_branch),
    )

    key = compute_agentic_idempotency_key(request, config)
    assert key == compute_agentic_idempotency_key(same_request, config)
    assert key != compute_agentic_idempotency_key(
        request,
        AgenticToolLoopConfig(max_tool_calls=5),
    )
    assert key != compute_agentic_idempotency_key(changed_request, config)


def test_partial_hypothesis_idempotency_key_is_surface_sensitive(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    route_hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="route_local",
            action="modify",
            target_file="operators/local_a.py",
        )
    )
    policy_hypothesis = HypothesisProposal(**_valid_hypothesis_payload())
    request = AgenticProposalRequest(
        campaign_id="camp-1",
        branch=context.branch,
        champion=context.champion,
        hypothesis_context={},
        build_code_context=lambda _hypothesis: {"kind": "code"},
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
        tool_context=context,
    )

    route_output = AgenticProposalSession(
        FakeCreative(hypothesis=route_hypothesis),
        tool_registry=ProposalToolRegistry.default_read_only(),
    ).run(request)
    policy_output = AgenticProposalSession(
        FakeCreative(hypothesis=policy_hypothesis),
        tool_registry=ProposalToolRegistry.default_read_only(),
    ).run(request)

    assert route_output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert policy_output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert route_output.selected_surface == "route_local"
    assert policy_output.selected_surface == "search_policy"
    assert route_output.idempotency_key != policy_output.idempotency_key
    assert route_output.idempotency_key != compute_agentic_idempotency_key(
        request,
        AgenticToolLoopConfig(),
    )


def test_agentic_session_step_limit_fail_closes_missing_required_context(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_steps=1, max_tool_calls=4),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert "missing required proposal context tools" in (output.failure_detail or "")


def test_agentic_session_fallback_fixed_plan_still_works(tmp_path: Path) -> None:
    creative = FakeCreative()
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

    assert output.status == AgenticProposalStatus.COMPLETED
    assert any(
        event.metadata.get("fallback") == "fixed_tool_plan"
        for event in output.transcript
    )
    assert any(
        event.metadata.get("selection_source") == "fallback_selected"
        for event in output.transcript
        if event.metadata.get("tool_name")
    )
    assert creative.hypothesis_contexts


