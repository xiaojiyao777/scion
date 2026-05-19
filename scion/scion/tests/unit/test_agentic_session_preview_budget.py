from __future__ import annotations

from scion.tests.unit.agentic_session_test_support import *

def test_agentic_session_wall_time_reserve_stops_smoke_repair_before_code_llm(
    tmp_path: Path,
    monkeypatch,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    registry = ProposalToolRegistry.default_read_only()
    registry._tools["proposal.algorithm_smoke"] = _FailingAlgorithmSmokeTool()

    def reserve_after_initial_code(self, state):
        del self, state
        return len(creative.code_contexts) > 0

    monkeypatch.setattr(
        AgenticProposalSession,
        "_code_phase_wall_time_reserved",
        reserve_after_initial_code,
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=registry,
        tool_loop_config=AgenticToolLoopConfig(max_code_repair_attempts=2),
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

    reserve_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("skip_reason") == "preview_repair_wall_time_reserved"
    ]

    assert output.status == AgenticProposalStatus.FAILED
    assert output.failure_category == "algorithm_smoke_failure"
    assert output.failure_detail is not None
    assert "algorithm smoke did not pass" in output.failure_detail
    assert len(creative.code_contexts) == 1
    assert reserve_events
    assert reserve_events[-1]["tool_name"] == "proposal.algorithm_smoke"
    assert output.failure_ledger["entries"][0]["tool_name"] == (
        "proposal.algorithm_smoke"
    )


def test_agentic_session_algorithm_smoke_repair_feedback_keeps_runtime_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_algorithm.py",
        )
    )
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    solution = context.make_solution(context.nearest_neighbor())\n"
            "    context.record_iteration('seed', 1)\n"
            "    context.record_move('seed', attempted=1, accepted=1)\n"
            "    return solution\n"
        ),
    )
    huge_stderr = "FULL_STDERR_BEGIN\n" + ("traceback line\n" * 9000) + (
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED missing_probe"
    )

    def fake_runtime_smoke(context, patch, selected_surface, hypothesis):
        del context, patch, selected_surface, hypothesis
        return {
            "passed": False,
            "runtime_smoke_run": True,
            "workspace_materialized": True,
            "selected_surface": "solver_design",
            "case": "controlled/data/canary.vrp",
            "case_count": 1,
            "issues": [
                "telemetry guard failed: "
                "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED"
            ],
            "run": {
                "success": False,
                "exit_code": 1,
                "elapsed_ms": 99,
                "error_category": "runtime_exception",
                "detail": "solver run failed after telemetry guard",
                "stderr": huge_stderr,
            },
            "runtime": {
                "solver_algorithm_errors": 1,
                "solver_algorithm_events": [
                    {
                        "message": (
                            "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED "
                            "missing_probe"
                        )
                    }
                ]
                * 1000,
            },
            "telemetry_guard": {
                "passed": False,
                "selected_surface": "solver_design",
                "candidate_runs": 1,
                "champion_runs": 1,
                "expected_telemetry_present": True,
                "declared_mechanisms": ["missing_probe"],
                "failures": [
                    {
                        "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                        "severity": "fail",
                        "mechanism": "missing_probe",
                        "category": "activation",
                        "field": "solver_algorithm_events",
                        "candidate_positive": 0,
                        "candidate_present": 1,
                        "candidate_missing": 0,
                        "champion_positive": 1,
                    }
                ],
            },
        }

    monkeypatch.setattr(
        preview_tools,
        "_runtime_algorithm_smoke_preview",
        fake_runtime_smoke,
    )
    creative = SequentialPatchCreative([patch, patch], hypothesis=hypothesis)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_code_repair_attempts=1),
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

    assert output.failure_category == "algorithm_smoke_failure"
    assert len(creative.code_contexts) >= 2
    repair_context = creative.code_contexts[1]
    prior_failure = repair_context["prior_code_failure"]
    preview_feedback = repair_context["agentic_preview_feedback"]
    assert "result exceeded observation budget" not in prior_failure
    assert "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED" in prior_failure
    assert "missing_probe" in prior_failure
    assert preview_feedback["structured_payload"]["agent_summary"][
        "primary_issue"
    ].startswith("telemetry guard failed")


def test_agentic_session_runs_algorithm_smoke_with_independent_preview_budget(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(
            max_tool_calls=9,
            max_code_repair_attempts=0,
        ),
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

    smoke_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("tool_name") == "proposal.algorithm_smoke"
        and event.metadata.get("observation_type")
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.is_completed is True
    assert output.failure_category is None
    assert output.tool_budget_used["tool_calls"] <= 9
    assert output.tool_budget_used["preview_tool_calls"] >= 4
    assert smoke_events
    assert smoke_events[-1]["status"] == "ok"
    assert smoke_events[-1]["observation_type"] == "algorithm_smoke"
    assert smoke_events[-1]["selection_source"] == "fallback_selected"
    assert not any(
        event.get("observation_type") == "tool_skipped" for event in smoke_events
    )


def test_agentic_session_runs_contract_preview_with_independent_preview_budget(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(
            max_tool_calls=8,
            max_code_repair_attempts=0,
        ),
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
        and event.metadata.get("observation_type")
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.is_completed is True
    assert output.failure_category is None
    assert output.self_check.contract_preview_passed is True
    assert output.tool_budget_used["tool_calls"] <= 8
    assert output.tool_budget_used["preview_tool_calls"] >= 4
    assert contract_events
    assert contract_events[-1]["status"] == "ok"
    assert contract_events[-1]["observation_type"] == "contract_preview"
    assert contract_events[-1]["selection_source"] == "fallback_selected"
    assert not any(
        event.get("observation_type") == "tool_skipped" for event in contract_events
    )


def test_agentic_session_default_budget_completes_with_empty_failure_ledger(
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
    assert output.is_completed is True
    assert output.failure_category is None
    assert output.failure_ledger["entry_count"] == 0
    assert output.failure_ledger["entries"] == []
    assert output.failure_ledger["first_root_cause"] is None
    assert output.failure_ledger["latest_failure"] is None


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
    config = AgenticToolLoopConfig(max_observation_chars=96000)
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
    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.tool_budget_used["tool_calls"] <= 2
    assert output.tool_budget_used["preview_tool_calls"] >= 4
    assert [event.metadata["tool_name"] for event in tool_events[:2]] == [
        "context.list_surfaces",
        "context.read_problem",
    ]
    assert any(
        event.metadata.get("tool_name") == "proposal.contract_preview"
        and event.metadata.get("status") == "ok"
        for event in tool_events
    )
    assert any(
        event.metadata.get("tool_name") == "proposal.algorithm_smoke"
        and event.metadata.get("status") == "ok"
        for event in tool_events
    )


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


