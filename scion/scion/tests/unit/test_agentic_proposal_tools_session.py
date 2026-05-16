from __future__ import annotations

from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    AGENTIC_SESSION_SCHEMA_VERSION,
    AgenticProposalPhase,
    AgenticProposalRequest,
    AgenticProposalSession,
    AgenticProposalSessionState,
    AgenticProposalStatus,
    AgenticSessionStore,
    AgenticTerminationReason,
    AgenticToolLoopConfig,
    Branch,
    BranchState,
    CapturingToolClient,
    ContextExposurePolicy,
    CreativeLayer,
    FakeCreative,
    FileAgenticSessionArtifactStore,
    HangingContractPreviewTool,
    HypothesisProposal,
    LargeObservationTool,
    NonCallableRenderMemory,
    PatchProposal,
    Path,
    PlanningCreative,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolRegistry,
    SequentialPatchCreative,
    SimpleNamespace,
    TimeoutThenPatchCreative,
    ToolSelectionClient,
    UnsafeMemory,
    _COMPACT_FEEDBACK_TOOL_NAMES,
    _compact_feedback_observation_for_budget,
    _context,
    _cvrp_context_with_champion,
    _json_size,
    _observation_prompt_payload,
    _research_diagnosis_from_observations,
    _tool_enabled_policy,
    _valid_hypothesis_payload,
    _valid_policy_patch_payload,
    agentic_session_module,
    compute_agentic_idempotency_key,
    json,
    pytest,
    replace,
    resume_from_artifact,
    validate_agentic_session_artifact,
)


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


def test_agentic_session_records_tool_observations_in_evidence_and_transcript(
    tmp_path: Path,
) -> None:
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
            hypothesis_context={"seed": "hypothesis"},
            build_code_context=lambda hypothesis: {"approved": hypothesis.change_locus},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    transcript = [event.metadata for event in output.transcript]
    tool_names = [event["tool_name"] for event in transcript if "tool_name" in event]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.evidence_used
    assert "context.list_surfaces" in tool_names
    assert "context.read_problem" in tool_names
    assert "memory.query" in tool_names
    assert "feedback.query_screening" in tool_names
    assert "proposal.schema_preview" in tool_names
    assert "proposal.target_permission_preview" in tool_names
    assert "proposal.contract_preview" in tool_names
    assert "proposal.algorithm_smoke" in tool_names
    assert output.self_check.schema_valid is True
    assert output.self_check.contract_preview_passed is True
    assert creative.hypothesis_contexts[0]["agentic_tool_observations"]
    assert (
        creative.hypothesis_contexts[0]["agentic_research_diagnosis"]["schema_version"]
        == "agentic-research-diagnosis.v1"
    )
    assert (
        creative.code_contexts[0]["agentic_research_diagnosis"]["schema_version"]
        == "agentic-research-diagnosis.v1"
    )
    for event in output.transcript:
        if "tool_name" not in event.metadata:
            continue
        assert {
            "step_id",
            "tool_name",
            "status",
            "taint",
            "evidence_ref",
            "result_summary",
            "error_code",
        }.issubset(event.metadata)
        assert "structured_payload" not in event.metadata


def test_creative_layer_renders_agentic_observations_and_research_diagnosis() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)
    diagnosis = {
        "schema_version": "agentic-research-diagnosis.v1",
        "latest_runtime_diagnosis": {
            "failure_mode_tags": ["screening_win_rate_failure"],
            "next_hypothesis_requirements": [
                "State which declared surface evidence fields are expected to change."
            ],
        },
    }
    observations = [
        {
            "tool_name": "feedback.query_runtime",
            "summary": "Returned screening-derived runtime feedback.",
            "structured_payload": {
                "research_diagnosis": diagnosis,
                "metrics_file_refs_exposed": False,
            },
        }
    ]

    creative.generate_hypothesis(
        {
            "problem_summary": "Synthetic problem.",
            "research_surfaces": "surface: search_policy",
            "objective_policy_guidance": "Minimize distance.",
            "solver_mechanics": "",
            "champion_operators_code": "def baseline_time_fraction(...): ...",
            "champion_stats": "champion v1",
            "operator_categories": "search_policy",
            "available_actions": "modify",
            "targetable_files": "policies/search_policy.py",
            "agentic_research_diagnosis": diagnosis,
            "agentic_tool_observations": observations,
        }
    )

    rendered = json.dumps(client.system_blocks, sort_keys=True) + "\n".join(
        client.prompts
    )
    assert "## Agentic Research Diagnosis" in rendered
    assert "## Agentic Proposal Tool Observations" in rendered
    assert "feedback.query_runtime" in rendered
    assert "screening_win_rate_failure" in rendered


def test_creative_layer_renders_active_boundary_novelty_requirements() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)

    creative.generate_hypothesis(
        {
            "problem_summary": "CVRP.",
            "research_surfaces": "surface: solver_design",
            "objective_policy_guidance": "Minimize fleet_violation then distance.",
            "solver_mechanics": "",
            "champion_operators_code": "def solve(...): ...",
            "champion_stats": "champion v1",
            "operator_categories": "solver_design",
            "active_problem_boundary_surfaces": "solver_design",
            "available_actions": "modify",
            "targetable_files": "policies/solver_algorithm.py",
            "agentic_hypothesis_constraints": {
                "active_problem_boundary_surfaces": ("solver_design",),
                "novelty_signature_requirements": {
                    "solver_design": {
                        "strategy": "semantic_signature",
                        "required_fields": [
                            "predicted_direction",
                            "target_objectives",
                            "algorithm_family",
                            "runtime_budget_strategy",
                        ],
                    }
                },
            },
        }
    )

    rendered = json.dumps(client.system_blocks, sort_keys=True) + "\n".join(
        client.prompts
    )
    assert "active problem-object research boundary" in rendered
    assert "algorithm_family" in rendered
    assert "runtime_budget_strategy" in rendered
    assert "choose the target file by mechanism ownership" in rendered
    assert "target that concrete module" in rendered


def test_agentic_session_retries_code_generation_timeout_with_compact_scope(
    tmp_path: Path,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Implement a hybrid ALNS/VNS destroy-repair route-pool solver."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/solver_algorithm.py",
        target_weakness="The current hook is inactive.",
        expected_effect="Produce movement under solver_algorithm telemetry.",
        novelty_signature={
            "algorithm_family": "compact_timeout_retry",
            "construction_strategy": "nearest_seed",
            "improvement_strategy": "bounded_relocate",
            "acceptance_strategy": "strict_improvement",
            "runtime_budget_strategy": "time_checked_passes",
        },
    )
    patch = PatchProposal(
        file_path="policies/solver_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    return context.nearest_neighbor()\n"
        ),
    )
    creative = TimeoutThenPatchCreative(hypothesis=hypothesis, patch=patch)
    context = _context(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_loop_config=AgenticToolLoopConfig(
            max_code_generation_timeout_retries=1,
        ),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {
                "research_surface_name": "solver_design",
                "research_surface_kind": "solver_design",
                "target_file": "policies/solver_algorithm.py",
            },
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            approved_hypothesis=hypothesis,
        )
    )

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == patch
    assert len(creative.code_contexts) == 2
    assert creative.code_contexts[0]["code_generation_mode"] == "compact_solver_design"
    retry_context = creative.code_contexts[1]
    assert retry_context["code_generation_mode"] == "compact_timeout_retry"
    assert "code_generation_timeout" in retry_context["prior_code_failure"]
    assert (
        "one primary construction or seeding path"
        in retry_context["agentic_code_scope_control"]["required_shape"]
    )
    assert (
        "no more than two move families"
        in retry_context["agentic_code_scope_control"]["required_shape"]
    )
    assert any(
        event.message == "Retrying patch generation with compact timeout scope."
        for event in output.transcript
    )


def test_agentic_research_diagnosis_keeps_latest_nonempty_runtime_signal() -> None:
    observations = [
        ProposalObservation(
            observation_id="obs-1",
            session_id="session-1",
            tool_name="feedback.query_runtime",
            tool_call_id="tool-1",
            observation_type="runtime_feedback",
            summary="non-empty runtime diagnosis",
            structured_payload={
                "research_diagnosis": {
                    "schema_version": "research-diagnosis.v1",
                    "screening_step_count": 2,
                    "reason_code_counts": {"SCREENING_FAIL_WIN_RATE": 2},
                    "surface_counts": {"search_policy": 2},
                    "gate_outcome_counts": {"fail": 2},
                    "failure_mode_tags": ["screening_win_rate_failure"],
                    "runtime_signal_rows": [
                        {
                            "round_num": 2,
                            "surface": "search_policy",
                            "nonzero_numeric_fields": ["component_delta"],
                        }
                    ],
                }
            },
        ),
        ProposalObservation(
            observation_id="obs-2",
            session_id="session-1",
            tool_name="feedback.query_runtime",
            tool_call_id="tool-2",
            observation_type="runtime_feedback",
            summary="empty runtime diagnosis",
            structured_payload={"research_diagnosis": {}},
        ),
    ]

    diagnosis = _research_diagnosis_from_observations(observations)

    assert diagnosis["runtime_diagnosis_count"] == 2
    assert diagnosis["runtime_diagnoses_with_signal"] == 1
    assert diagnosis["latest_runtime_diagnosis"]["screening_step_count"] == 2
    assert diagnosis["aggregate_runtime_diagnosis"]["reason_code_counts"] == {
        "SCREENING_FAIL_WIN_RATE": 2
    }
    assert (
        "screening_win_rate_failure"
        in diagnosis["aggregate_runtime_diagnosis"]["failure_mode_tags"]
    )


def test_agentic_session_forced_surface_fails_closed_before_partial_finalize(
    tmp_path: Path,
) -> None:
    off_surface = HypothesisProposal(
        hypothesis_text="Try a route-local move.",
        change_locus="route_local",
        action="create_new",
        target_file="operators/local_new.py",
    )
    creative = FakeCreative(hypothesis=off_surface)
    context = replace(
        _context(tmp_path, policy=_tool_enabled_policy()),
        forced_surface="search_policy",
        forced_action="modify",
        forced_target_file="policies/search_policy.py",
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={
                "forced_surface": "search_policy",
                "forced_action": "modify",
                "forced_target_file": "policies/search_policy.py",
            },
            build_code_context=lambda _hypothesis: {"kind": "code"},
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert (
        output.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED
    )
    assert output.hypothesis is None
    assert output.patch is None
    assert "forced_surface_constraint" in (output.failure_detail or "")
    assert creative.code_contexts == []


def test_agentic_session_reads_cvrp_main_search_strategy_under_expanded_budget(
    tmp_path: Path,
) -> None:
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        search_memory=UnsafeMemory(),
    )
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/solver_algorithm.py",
            target_objectives=["total_distance"],
        )
    )
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
            {
                "tool_name": "context.read_surface",
                "args": {"surface": "solver_design"},
            },
            {"tool_name": "memory.query", "args": {}},
        ],
        hypothesis=hypothesis,
    )
    config = AgenticToolLoopConfig(max_observation_chars=48000)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
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
    tool_events = [
        event.metadata for event in output.transcript if event.metadata.get("tool_name")
    ]
    rendered_context = json.dumps(
        creative.hypothesis_contexts[0]["agentic_tool_observations"],
        sort_keys=True,
        default=str,
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.tool_budget_used["observation_chars"] <= config.max_observation_chars
    assert any(
        event["tool_name"] == "context.read_surface"
        and event["status"] == "ok"
        and event["selection_source"] == "planner_selected"
        for event in tool_events
    )
    assert not any(
        event.get("error_code") == "result_too_large" for event in tool_events
    )
    assert "solver_design" in rendered_context
    assert "raw_metrics_ref" not in rendered_context
    assert "SECRET_VALIDATION" not in rendered_context
    assert "SECRET_FROZEN" not in rendered_context


def test_agentic_session_tool_loop_limits_are_enforced(tmp_path: Path) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_steps=2, max_tool_calls=2),
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
        event for event in output.transcript if event.metadata.get("tool_name")
    ]
    stop_events = [
        event
        for event in output.transcript
        if event.metadata.get("stop_reason") == "tool_loop_limit"
    ]

    assert output.status == AgenticProposalStatus.FAILED
    assert output.failure_detail == "schema or target preview did not pass"
    assert [event.metadata["tool_name"] for event in tool_events] == [
        "context.list_surfaces",
        "context.read_problem",
    ]
    assert stop_events


def test_agentic_session_observation_budget_bounds_large_tool_results(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "test.huge_observation", "args": {}},
            {"tool_name": "test.huge_error", "args": {}},
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
        ]
    )
    context = _context(tmp_path, policy=_tool_enabled_policy())
    registry = ProposalToolRegistry.default_read_only()
    registry.register(
        LargeObservationTool(
            "test.huge_observation",
            payload_chars=20000,
        )
    )
    registry.register(
        LargeObservationTool(
            "test.huge_error",
            payload_chars=20000,
            is_error=True,
        )
    )
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    config = AgenticToolLoopConfig(
        max_steps=6,
        max_tool_calls=6,
        max_observation_chars=2000,
    )
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
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
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    huge_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("tool_name")
        in {"test.huge_observation", "test.huge_error"}
    ]

    assert output.tool_budget_used["observation_chars"] <= 2000
    assert artifact["tool_budget_used"]["observation_chars"] <= 2000
    assert validate_agentic_session_artifact(artifact).ok is True
    assert {event["tool_name"] for event in huge_events} == {
        "test.huge_observation",
        "test.huge_error",
    }
    assert all(event["error_code"] == "result_too_large" for event in huge_events)


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
    assert "proposal.algorithm_smoke" not in first_planner_context["allowed_tools"]
    assert all(spec.get("name") for spec in first_planner_context["allowed_tool_specs"])


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


def test_forced_surface_session_uses_bounded_list_and_does_not_reread_surface(
    tmp_path: Path,
) -> None:
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file="policies/solver_algorithm.py",
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
            target_file="policies/solver_algorithm.py",
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
            file_path="policies/solver_algorithm.py",
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
    assert listed.structured_payload["total_declared_surface_count"] > 1
    assert listed.structured_payload["surfaces"][0]["name"] == "solver_design"
    assert len(rendered_list) < 12000
    assert output.status == AgenticProposalStatus.COMPLETED
    assert len(read_surface_events) == 2
    assert read_surface_events[0]["selection_source"] == "planner_selected"
    assert read_surface_events[1]["selection_source"] == "code_phase_required"
    assert output.tool_budget_used["observation_chars"] <= (
        output.tool_loop_config["max_observation_chars"]
    )
    assert any(
        event.metadata.get("skip_reason") == "already_succeeded"
        and event.metadata.get("tool_name") == "context.read_surface"
        for event in output.transcript
    )
    assert any(
        observation["tool_name"] == "context.read_surface"
        and observation["structured_payload"]["detail"] == "full"
        and observation["structured_payload"]["current_artifact"]["max_chars"] == 12000
        for observation in creative.code_contexts[0]["agentic_tool_observations"]
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
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
            {
                "tool_name": "context.read_surface",
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
    )
    payload = module_read["structured_payload"]
    artifact = payload["current_artifact"]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert any(
        event["selection_source"] == "code_phase_planner"
        for event in read_surface_events
    )
    assert not any(
        event["selection_source"] == "code_phase_required"
        for event in read_surface_events
    )
    assert payload["detail"] == "full"
    assert payload["section"] == "target_preview"
    assert payload["target_file"] == target_file
    assert artifact["max_chars"] == 6000
    assert artifact["truncated"] is True
    assert artifact["content_preview_chars"] == 6000
    support_paths = {
        support["file_path"] for support in payload["support_artifacts"]
    }
    assert "policies/baseline_modules/state.py" in support_paths


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
    assert read_surface_events[0]["error_code"] == "not_found"
    assert any(
        event["status"] == "ok"
        and event["selection_source"] == "selected_surface_required"
        for event in read_surface_events
    )
    assert any(
        event["status"] == "ok" and event["selection_source"] == "code_phase_required"
        for event in read_surface_events
    )
    assert creative.planner_contexts[1]["tool_arg_guidance"]["context.read_surface"][
        "allowed_surface_ids"
    ] == ["route_local", "search_policy"]
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


def test_agentic_session_contract_preview_failure_fails_closed(
    tmp_path: Path,
) -> None:
    bad_patch = PatchProposal(
        file_path="operators/local_a.py",
        action="modify",
        code_content="class LocalA:\n    def execute(self, solution, rng):\n        return solution\n",
    )
    creative = FakeCreative(patch=bad_patch)
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

    assert output.status == AgenticProposalStatus.FAILED
    assert output.patch is None
    assert output.failure_detail is not None
    assert "contract preview did not pass" in output.failure_detail
    assert output.self_check.contract_preview_passed is False
    assert output.self_check.contract_preview_codes
    assert output.self_check.contract_preview_codes[0] in output.failure_detail


def test_agentic_session_repairs_two_contract_preview_failures(
    tmp_path: Path,
) -> None:
    missing_function = PatchProposal(
        **_valid_policy_patch_payload(
            code_content=(
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.35\n"
            )
        )
    )
    bad_import = PatchProposal(
        **_valid_policy_patch_payload(
            code_content=(
                "import os\n\n"
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.35\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 10\n"
            )
        )
    )
    good_patch = PatchProposal(**_valid_policy_patch_payload())
    creative = SequentialPatchCreative(
        [
            missing_function,
            bad_import,
            good_patch,
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

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == good_patch
    assert len(creative.code_contexts) == 3
    assert "agentic_preview_feedback" in creative.code_contexts[1]
    assert "agentic_preview_feedback" in creative.code_contexts[2]


def test_agentic_session_repairs_self_reported_unresolved_patch_issue(
    tmp_path: Path,
) -> None:
    bad_payload = _valid_policy_patch_payload(
        test_hint="This generated file has a syntax error that needs fixing."
    )
    good_payload = _valid_policy_patch_payload(test_hint=None)
    creative = SequentialPatchCreative(
        [
            PatchProposal(**bad_payload),
            PatchProposal(**good_payload),
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

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == PatchProposal(**good_payload)
    assert len(creative.code_contexts) == 2
    repair_context = creative.code_contexts[1]
    assert "agentic_code_self_check_feedback" in repair_context
    assert "syntax_error" in repair_context["prior_code_failure"]


def test_agentic_session_rejects_self_reported_unresolved_patch_after_repair(
    tmp_path: Path,
) -> None:
    first_bad = PatchProposal(
        **_valid_policy_patch_payload(
            test_hint="This generated file has a syntax error that needs fixing."
        )
    )
    second_bad = PatchProposal(
        **_valid_policy_patch_payload(
            test_hint="The replacement is still broken and needs fixing."
        )
    )
    creative = SequentialPatchCreative([first_bad, second_bad])
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

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.patch is None
    assert output.termination_reason == AgenticTerminationReason.CODE_GENERATION_FAILED
    assert output.failure_detail is not None
    assert "self-reported unresolved code issue" in output.failure_detail
    assert "needs_fixing" in output.failure_detail
    assert len(creative.code_contexts) == 2


def test_agentic_session_contract_preview_timeout_returns_tool_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    if not agentic_session_module._can_use_signal_timeout():
        pytest.skip("SIGALRM timeout is unavailable in this environment.")
    monkeypatch.setattr(
        agentic_session_module,
        "_CONTRACT_PREVIEW_TOOL_TIMEOUT_SEC",
        0.01,
    )
    context = _context(tmp_path, policy=_tool_enabled_policy())
    state = AgenticProposalSessionState(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch_id=context.branch.branch_id,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry([HangingContractPreviewTool()]),
    )

    observation = session._call_tool(
        context,
        state,
        AgenticProposalPhase.SELF_CHECK,
        "proposal.contract_preview",
        {},
    )

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.RUNTIME_EXCEPTION
    assert "timed out" in observation.summary
    assert observation.structured_payload["tool_name"] == "proposal.contract_preview"
    assert state.transcript[-1].metadata["status"] == "error"


def test_agentic_session_does_not_emit_raw_refs_in_artifacts(tmp_path: Path) -> None:
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
    rendered_prompt = json.dumps(
        creative.hypothesis_contexts, default=str, sort_keys=True
    )

    assert "raw_metrics_ref" not in rendered_output
    assert "SECRET_VALIDATION" not in rendered_output
    assert "SECRET_FROZEN" not in rendered_output
    assert "SECRET_HOLDOUT_SIGNAL" not in rendered_output
    assert "raw_metrics_ref" not in rendered_prompt
    assert "SECRET_HOLDOUT_SIGNAL" not in rendered_prompt
    for event in output.transcript:
        rendered_event = json.dumps(event.metadata, default=str, sort_keys=True)
        assert "raw_metrics_ref" not in rendered_event
        assert "SECRET_VALIDATION" not in rendered_event
        assert "SECRET_FROZEN" not in rendered_event


def test_agentic_session_artifact_schema_version_and_digest_exist(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
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

    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))

    assert artifact["schema_version"] == AGENTIC_SESSION_SCHEMA_VERSION
    assert artifact["session_id"] == output.session_id
    assert artifact["request_id"] == output.request_id
    assert artifact["idempotency_key"] == output.idempotency_key
    assert artifact["idempotency_key"].startswith("aps:")
    assert artifact["termination_reason"] == "completed"
    assert (
        artifact["tool_loop_config"]["max_tool_calls"]
        >= artifact["tool_budget_used"]["tool_calls"]
    )
    assert artifact["transcript_digest"] == output.transcript_digest
    assert artifact["tainted"] is True
    assert artifact["patch"]["patch_body_omitted"] is True
    assert "code_content" not in json.dumps(artifact, sort_keys=True)
    assert validate_agentic_session_artifact(artifact).ok is True


def test_agentic_session_store_indexes_output_and_loads_across_instances(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_dir = tmp_path / "aps-artifacts"
    session = AgenticProposalSession(
        creative,
        artifact_store=FileAgenticSessionArtifactStore(artifact_dir),
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

    store = AgenticSessionStore(artifact_dir)
    by_session = store.load_by_session_id(output.session_id)
    by_key = AgenticSessionStore(artifact_dir).find_by_idempotency_key(
        output.idempotency_key
    )

    assert store.index_path.exists()
    assert by_session is not None
    assert by_session.validation.ok is True
    assert by_session.entry.session_id == output.session_id
    assert by_session.entry.status == "completed"
    assert by_session.entry.transcript_digest == output.transcript_digest
    assert by_key is not None
    assert by_key.entry.session_id == output.session_id


def test_agentic_replay_validator_rejects_budget_duplicate_step_and_raw_marker(
    tmp_path: Path,
) -> None:
    artifact = {
        "schema_version": AGENTIC_SESSION_SCHEMA_VERSION,
        "session_id": "session-1",
        "request_id": "request-1",
        "termination_reason": "tool_loop_limit",
        "tool_loop_config": {
            "max_steps": 1,
            "max_tool_calls": 1,
            "max_observation_chars": 100,
        },
        "tool_budget_used": {
            "tool_steps": 2,
            "tool_calls": 1,
            "observation_chars": 10,
        },
        "transcript_digest": "wrong",
        "compact_transcript": [
            {
                "phase": "diagnose",
                "metadata": {
                    "step_id": "tool-0001",
                    "tool_name": "context.list_surfaces",
                    "status": "ok",
                    "result_summary": "safe",
                },
            },
            {
                "phase": "diagnose",
                "metadata": {
                    "step_id": "tool-0001",
                    "tool_name": "context.read_problem",
                    "status": "ok",
                    "result_summary": "raw_metrics_ref should reject",
                },
            },
        ],
    }

    result = validate_agentic_session_artifact(artifact)

    assert result.ok is False
    rendered_errors = " ".join(result.errors)
    assert "tool budget exceeded" in rendered_errors
    assert "duplicate step_id" in rendered_errors
    assert "raw ref marker" in rendered_errors


def test_resume_from_artifact_returns_sanitized_length_bounded_context(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
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
    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )

    resume_context = resume_from_artifact(output_ref, max_chars=600)
    rendered = json.dumps(resume_context, sort_keys=True)

    assert len(resume_context["summary"]) <= 600
    assert resume_context["session_id"] == output.session_id
    assert resume_context["transcript_digest"] == output.transcript_digest
    assert resume_context["tool_steps"]
    assert {
        "tool_name",
        "status",
        "error_code",
        "evidence_ref",
        "result_summary",
    }.issubset(resume_context["tool_steps"][0])
    assert "structured_payload" not in rendered
    assert "raw_metrics_ref" not in rendered
    assert "SECRET_VALIDATION" not in rendered
    assert "code_content" not in rendered


def test_agentic_session_tool_errors_are_controlled_or_fail_closed(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    nonfatal_context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=context.step_history,
        search_memory=NonCallableRenderMemory(),
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )
    creative = FakeCreative()
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    degraded = session.run(
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
            tool_context=nonfatal_context,
        )
    )
    failed_closed = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry(),
    ).run(
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

    memory_events = [
        event.metadata
        for event in degraded.transcript
        if event.metadata.get("tool_name") == "memory.query"
    ]
    assert degraded.status == AgenticProposalStatus.COMPLETED
    assert memory_events[0]["is_error"] is True
    assert failed_closed.status == AgenticProposalStatus.FAILED
    assert creative.hypothesis_contexts
