from __future__ import annotations

from scion.proposal.solver_design_smoke import _runtime_algorithm_smoke_preview

from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    AgenticProposalRequest,
    AgenticProposalSession,
    AgenticProposalSessionState,
    AgenticToolLoopConfig,
    CapturingToolClient,
    ChampionState,
    CreativeLayer,
    FakeCreative,
    HypothesisProposal,
    PatchProposal,
    Path,
    PlanningCreative,
    ProposalObservation,
    ProposalToolRegistry,
    RunResult,
    SeedLedgerConfig,
    SimpleNamespace,
    SplitManifest,
    _CVRP_ROOT,
    _algorithm_smoke_failure_detail,
    _code_observation_prompt_payload,
    _code_prompt_observations,
    _compact_algorithm_smoke_observation,
    _context,
    _cvrp_context,
    _cvrp_context_with_champion,
    _json_size,
    _latest_preview_failure_detail,
    _observation_prompt_payload,
    _resolve_smoke_instance_path,
    _solver_design_low_effort_issue,
    _solver_run_failure_detail,
    _tool_enabled_policy,
    _valid_hypothesis_payload,
    json,
    legacy_problem_spec_from_v1,
    pytest,
    replace,
    shutil,
)


def test_active_solver_design_snapshot_exposes_active_mechanisms(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call("context.read_active_solver_design", {}, context)

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["surface"] == "solver_design"
    assert payload["active_surface"]["entrypoint"] == (
        "policies/baseline_algorithm.py::solve"
    )
    assert payload["provenance"]["source"] == "champion_snapshot"
    assert payload["source_digest"]["snapshot_digest"]
    assert "policies/baseline_modules/scheduler.py" in payload["source_digest"]["files"]
    assert "_initial_solution" in rendered
    assert "alns_loop" in rendered
    assert "destroy_repair" in rendered
    assert "_shaw_removal" in rendered
    assert "seed-based related/proximity-cluster destroy operator" in rendered
    assert "distance" in rendered
    assert "demand" in rendered
    assert "original-route relatedness" in rendered
    assert "_AdaptiveWeights.update" in rendered
    assert "_SimulatedAnnealing.accept" in rendered
    assert "_or_opt_2" in rendered
    assert "_or_opt_3" in rendered
    assert "vns_embedded" in rendered
    assert "legacy_inactive_surface_exclusion" in payload
    assert "alns_vns_policy" in rendered
    assert "must not be used as active evidence" in rendered
    inactive_paths = {
        item["file_path"]
        for item in payload["inactive_files"]
        if item["role"] == "compatibility_hook_not_primary"
    }
    assert inactive_paths == {"policies/solver_algorithm.py"}


def test_solver_call_graph_marks_initial_solution_alns_vns_and_acceptance(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call("context.read_solver_call_graph", {}, context)

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["surface"] == "solver_design"
    assert "scheduler._ALNSVNSSolver._initial_solution" in rendered
    assert "ALNS destroy/repair loop" in rendered
    assert "_shaw_removal" in rendered
    assert "distance + demand + original-route relatedness" in rendered
    assert "local_search._vns" in rendered
    assert "_default_vns_operators" in rendered
    assert "_SimulatedAnnealing.accept" in rendered
    assert "_AdaptiveWeights" in rendered
    assert "legacy_inactive_surface_exclusion" in payload


def test_active_solver_algorithm_file_tools_are_allowlisted_with_provenance(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    listed = registry.call("context.list_algorithm_files", {}, context)
    read_file = registry.call(
        "context.read_algorithm_file",
        {
            "file_path": "policies/baseline_modules/scheduler.py",
            "max_chars": 24000,
        },
        context,
    )
    read_symbol = registry.call(
        "context.read_algorithm_symbol",
        {
            "file_path": "policies/baseline_modules/scheduler.py",
            "symbol": "_ALNSVNSSolver._initial_solution",
            "max_chars": 12000,
        },
        context,
    )
    denied = registry.call(
        "context.read_algorithm_file",
        {"file_path": "vrp/solver.py"},
        context,
    )

    files = listed.structured_payload["files"]
    by_path = {item["file_path"]: item for item in files}
    assert listed.is_error is False
    assert by_path["policies/baseline_algorithm.py"]["active"] is True
    assert by_path["policies/solver_algorithm.py"]["active"] is False
    assert by_path["policies/baseline_modules/scheduler.py"]["source"] == (
        "champion_snapshot"
    )
    assert by_path["policies/baseline_modules/scheduler.py"]["digest"]

    assert read_file.is_error is False
    file_payload = read_file.structured_payload
    assert file_payload["readable"] is True
    assert file_payload["provenance"]["source"] == "champion_snapshot"
    assert "class _ALNSVNSSolver" in file_payload["content_preview"]

    assert read_symbol.is_error is False
    symbol_payload = read_symbol.structured_payload
    assert symbol_payload["readable"] is True
    assert symbol_payload["symbol"] == "_ALNSVNSSolver._initial_solution"
    assert "_sweep_construction" in symbol_payload["content_preview"]
    assert "_nearest_neighbor" in symbol_payload["content_preview"]
    assert symbol_payload["digest"]

    assert denied.is_error is True
    denied_payload = denied.structured_payload
    assert denied_payload["readable"] is False
    assert denied_payload["path_rejected"] is True
    assert denied_payload["file_path"] == "<path_rejected>"
    assert denied_payload["reason"] == "file_path_not_allowed"
    assert "policies/baseline_algorithm.py" in denied_payload["allowed_files"]
    assert denied_payload["allowed_file_paths"] == denied_payload["allowed_files"]
    assert denied_payload["required_first_tool"] == "context.list_algorithm_files"
    assert denied_payload["file_path_source_tool"] == "context.list_algorithm_files"
    assert "vrp/solver.py" not in denied_payload["allowed_files"]


@pytest.mark.parametrize(
    "bad_path",
    (
        "<UNKNOWN>",
        "solver_design",
        "vrp/solver.py",
        "../policies/baseline_algorithm.py",
    ),
)
def test_active_solver_rejects_invalid_path_without_echoing_it(
    tmp_path: Path,
    bad_path: str,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    file_observation = registry.call(
        "context.read_algorithm_file",
        {"file_path": bad_path},
        context,
    )
    symbol_observation = registry.call(
        "context.read_algorithm_symbol",
        {"file_path": bad_path, "symbol": "solve"},
        context,
    )

    rendered = json.dumps(
        {
            "file_observation": file_observation,
            "file_prompt": _observation_prompt_payload(file_observation),
            "symbol_observation": symbol_observation,
            "symbol_prompt": _observation_prompt_payload(symbol_observation),
        },
        sort_keys=True,
        default=str,
    )
    assert file_observation.is_error is True
    assert symbol_observation.is_error is True
    for observation in (file_observation, symbol_observation):
        assert observation.structured_payload["readable"] is False
        assert observation.structured_payload["path_rejected"] is True
        assert observation.structured_payload["file_path"] == "<path_rejected>"
        assert observation.structured_payload["reason"] == "file_path_not_allowed"
        assert observation.structured_payload["required_first_tool"] == (
            "context.list_algorithm_files"
        )
        assert "policies/baseline_algorithm.py" in observation.structured_payload[
            "allowed_file_paths"
        ]
        assert "solver_design is a research surface id" in observation.structured_payload[
            "surface_id_rule"
        ]
        assert bad_path not in observation.summary
    if bad_path != "solver_design":
        assert bad_path not in rendered
    assert '"file_path": "' + bad_path + '"' not in rendered


def test_active_solver_rejects_absolute_path_without_echoing_it(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)
    absolute_path = str(tmp_path / "private" / "solver.py")

    file_observation = registry.call(
        "context.read_algorithm_file",
        {"file_path": absolute_path},
        context,
    )
    symbol_observation = registry.call(
        "context.read_algorithm_symbol",
        {"file_path": absolute_path, "symbol": "solve"},
        context,
    )

    payload = file_observation.structured_payload
    rendered = json.dumps(
        {
            "file_observation": file_observation,
            "file_prompt": _observation_prompt_payload(file_observation),
            "symbol_observation": symbol_observation,
            "symbol_prompt": _observation_prompt_payload(symbol_observation),
        },
        sort_keys=True,
        default=str,
    )
    assert file_observation.is_error is True
    assert symbol_observation.is_error is True
    for observation in (file_observation, symbol_observation):
        assert observation.structured_payload["readable"] is False
        assert observation.structured_payload["path_rejected"] is True
        assert observation.structured_payload["file_path"] == "<path_rejected>"
        assert observation.structured_payload["reason"] == "file_path_not_allowed"
        assert absolute_path not in observation.summary
        assert str(tmp_path) not in observation.summary
    assert absolute_path not in rendered
    assert str(tmp_path) not in rendered


def test_active_solver_provenance_payload_does_not_expose_absolute_paths(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observations = [
        registry.call("context.read_active_solver_design", {}, context),
        registry.call("context.read_solver_call_graph", {}, context),
        registry.call(
            "context.read_algorithm_file",
            {"file_path": "policies/baseline_algorithm.py"},
            context,
        ),
        registry.call(
            "context.read_algorithm_symbol",
            {
                "file_path": "policies/baseline_algorithm.py",
                "symbol": "solve",
            },
            context,
        ),
    ]
    payloads = [observation.structured_payload for observation in observations]
    forbidden_keys = {
        "source_root",
        "branch_workspace",
        "champion_code_snapshot_path",
    }

    def keys(value):
        if isinstance(value, dict):
            found = set(value)
            for child in value.values():
                found.update(keys(child))
            return found
        if isinstance(value, list):
            found = set()
            for child in value:
                found.update(keys(child))
            return found
        return set()

    rendered = json.dumps(payloads, sort_keys=True, default=str)
    assert all(observation.is_error is False for observation in observations)
    assert str(tmp_path) not in rendered
    assert forbidden_keys.isdisjoint(keys(payloads))


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


def test_algorithm_smoke_runs_tainted_synthetic_preview_without_promotion(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_algorithm.py",
            ),
            "patch": {
                "file_path": "policies/baseline_algorithm.py",
                "action": "modify",
                "code_content": (
                    "def solve(instance, rng, time_limit_sec, context):\n"
                    "    solution = context.make_solution(context.nearest_neighbor())\n"
                    "    context.record_iteration('seed', 1)\n"
                    "    context.record_move('seed', attempted=1, accepted=1)\n"
                    "    return solution\n"
                ),
            },
        },
        context,
    )

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    payload = observation.structured_payload
    assert observation.is_error is False
    assert payload["passed"] is True
    assert payload["non_promotional"] is True
    assert payload["tainted_debug"] is True
    assert payload["workspace_materialized"] is True
    assert payload["verification_run"] is False
    assert payload["protocol_run"] is False
    assert payload["decision_run"] is False
    assert payload["problem_preview"]["passed"] is True
    assert payload["runtime_smoke"]["passed"] is True
    assert payload["runtime_smoke"]["runtime_smoke_run"] is True
    assert payload["runtime_smoke"]["runtime"]["solver_algorithm_path"] == (
        "policies/baseline_algorithm.py"
    )
    assert payload["runtime_smoke"]["resolved_case_path"]
    assert payload["runtime_smoke"]["data_root"]
    assert payload["runtime_smoke"]["data_root_source"] in {
        "workspace",
        "base_workspace",
        "safe_data_root",
        "audited_problem_data_manifest",
    }
    assert payload["runtime_smoke"]["data_root_status"] in {
        "safe_root_relative",
        "audited_manifest_relative",
    }
    assert payload["runtime_smoke"]["provenance"]["absolute_paths_exposed"] is False
    assert str(tmp_path) not in json.dumps(payload["runtime_smoke"], sort_keys=True)
    assert after == before


def test_algorithm_smoke_normalizes_solver_algorithm_surface_alias(
    tmp_path: Path,
) -> None:
    context = _cvrp_context(tmp_path)
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

    payload = _runtime_algorithm_smoke_preview(
        context,
        patch,
        "solver_algorithm",
    )

    assert payload is not None
    assert payload["selected_surface"] == "solver_design"
    assert payload["runtime_smoke_run"] is True
    assert payload["resolved_case_path"]


def test_algorithm_smoke_runs_solver_design_module_patch_through_entrypoint(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    module_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "config.py"
    ).read_text(encoding="utf-8")

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_modules/config.py",
            ),
            "patch": {
                "file_path": "policies/baseline_modules/config.py",
                "action": "modify",
                "code_content": module_code,
            },
        },
        context,
    )

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    payload = observation.structured_payload
    assert observation.is_error is False
    assert payload["passed"] is True
    assert payload["workspace_materialized"] is True
    assert payload["problem_preview"]["passed"] is True
    assert payload["runtime_smoke"]["passed"] is True
    assert payload["runtime_smoke"]["runtime_smoke_run"] is True
    assert payload["runtime_smoke"]["runtime"]["solver_algorithm_path"] == (
        "policies/baseline_algorithm.py"
    )
    assert after == before


def test_algorithm_smoke_accepts_legacy_problem_v1_runtime_audit_spec(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    context = replace(
        context,
        problem_spec=legacy_problem_spec_from_v1(context.problem_spec),
    )
    module_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "config.py"
    ).read_text(encoding="utf-8")

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_modules/config.py",
            ),
            "patch": {
                "file_path": "policies/baseline_modules/config.py",
                "action": "modify",
                "code_content": module_code,
            },
        },
        context,
    )

    payload = observation.structured_payload
    assert observation.is_error is False
    assert payload["passed"] is True
    assert payload["runtime_smoke"]["passed"] is True


def test_algorithm_smoke_runs_multi_file_solver_design_patch(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    baseline_code = (_CVRP_ROOT / "policies" / "baseline_algorithm.py").read_text(
        encoding="utf-8"
    )
    baseline_code = baseline_code.replace(
        "from .baseline_modules.scheduler import _ALNSVNSSolver\n",
        "from .baseline_modules.scheduler import _ALNSVNSSolver\n"
        "from .baseline_modules.intensification import intensify\n",
        1,
    ).replace(
        "    context.set_stop_reason(solution.stop_reason)\n"
        "    return context.make_solution(solution.routes_as_tuples())\n",
        "    solution = intensify(solution, instance, context)\n"
        "    context.set_stop_reason(solution.stop_reason)\n"
        "    return context.make_solution(solution.routes_as_tuples())\n",
        1,
    )
    helper_code = (
        "def intensify(solution, instance, context):\n"
        "    context.record_phase('intensification', 0.0)\n"
        "    return solution\n"
    )

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                action="create_new",
                target_file="policies/baseline_modules/intensification.py",
            ),
            "patch": {
                "file_path": "policies/baseline_modules/intensification.py",
                "action": "create",
                "code_content": helper_code,
                "additional_changes": [
                    {
                        "file_path": "policies/baseline_algorithm.py",
                        "action": "modify",
                        "code_content": baseline_code,
                    }
                ],
            },
        },
        context,
    )

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    payload = observation.structured_payload
    patch_payload = payload["patch"]
    contract_checks = {
        check["name"]: check["passed"] for check in patch_payload["checks"]
    }

    assert observation.is_error is False
    assert payload["passed"] is True
    assert patch_payload["patch"]["additional_change_count"] == 1
    assert contract_checks["C4b_patch_action_target"] is True
    assert (
        contract_checks[
            "additional_changes[0].C4b_patch_action_target"
        ]
        is True
    )
    assert payload["runtime_smoke"]["passed"] is True
    assert payload["runtime_smoke"]["runtime_smoke_run"] is True
    assert after == before


def test_algorithm_smoke_materializes_readonly_champion_snapshot(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    champion_root = tmp_path / "readonly_cvrp_champion"
    shutil.copytree(
        _CVRP_ROOT,
        champion_root,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        ),
    )
    for path in sorted(champion_root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    champion_root.chmod(0o555)
    context = replace(
        context,
        champion=ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver-hash",
            code_snapshot_path=str(champion_root),
            code_snapshot_hash="code-hash",
        ),
    )

    try:
        observation = registry.call(
            "proposal.algorithm_smoke",
            {
                "hypothesis": _valid_hypothesis_payload(
                    change_locus="solver_design",
                    target_file="policies/baseline_algorithm.py",
                ),
                "patch": {
                    "file_path": "policies/baseline_algorithm.py",
                    "action": "modify",
                    "code_content": (
                        "def solve(instance, rng, time_limit_sec, context):\n"
                        "    solution = context.make_solution(context.nearest_neighbor())\n"
                        "    context.record_iteration('seed', 1)\n"
                        "    return solution\n"
                    ),
                },
            },
            context,
        )
    finally:
        for path in sorted(champion_root.rglob("*"), reverse=True):
            path.chmod(0o755 if path.is_dir() else 0o644)
        champion_root.chmod(0o755)

    payload = observation.structured_payload
    assert observation.is_error is False
    assert payload["passed"] is True
    assert payload["runtime_smoke"]["passed"] is True
    assert payload["runtime_smoke"]["runtime_smoke_run"] is True


def test_algorithm_smoke_rejects_solver_design_runtime_error(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_algorithm.py",
            ),
            "patch": {
                "file_path": "policies/baseline_algorithm.py",
                "action": "modify",
                "code_content": (
                    "def solve(instance, rng, time_limit_sec, context):\n"
                    "    solution = context.nearest_neighbor()\n"
                    "    if time_limit_sec < 4:\n"
                    "        raise RuntimeError('runtime smoke only')\n"
                    "    return solution\n"
                ),
            },
        },
        context,
    )

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["passed"] is False
    assert payload["workspace_materialized"] is True
    assert payload["runtime_smoke"]["passed"] is False
    assert "solver_algorithm_errors" in rendered
    assert "runtime smoke only" in rendered
    assert "policies/baseline_algorithm.py" in rendered


def test_algorithm_smoke_rejects_zero_search_solver_design_candidate(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_algorithm.py",
            ),
            "patch": {
                "file_path": "policies/baseline_algorithm.py",
                "action": "modify",
                "code_content": (
                    "def solve(instance, rng, time_limit_sec, context):\n"
                    "    return context.nearest_neighbor()\n"
                ),
            },
        },
        context,
    )

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["passed"] is False
    assert payload["runtime_smoke"]["passed"] is False
    assert "zero active search effort" in rendered
    assert "solver_algorithm_search_iterations=0" in rendered
    assert "solver_algorithm_move_attempts=0" in rendered


def test_solver_design_low_effort_issue_rejects_search_bearing_under_spend() -> None:
    patch = PatchProposal(
        file_path="policies/baseline_modules/construction.py",
        action="modify",
        code_content="def seed_pool(instance):\n    return []\n",
        additional_changes=(
            SimpleNamespace(
                file_path="policies/baseline_modules/scheduler.py",
                action="modify",
                code_content="class _ALNSVNSSolver:\n    def solve(self, instance, rng):\n        return instance\n",
            ),
        ),
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Improve ALNS/VNS search by changing construction seeds.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
    )
    runs = [
        {
            "case": "cvrplib/A/A-n32-k5.vrp",
            "seed": 11,
            "passed": True,
            "runtime": {
                "solver_algorithm_search_iterations": 4,
                "solver_algorithm_move_attempts": 24,
                "solver_algorithm_stop_reason": "no_improvement",
                "solver_algorithm_elapsed_ms": 120,
            },
            "run": {"elapsed_ms": 130},
        },
        {
            "case": "cvrplib/B/B-n31-k5.vrp",
            "seed": 11,
            "passed": True,
            "runtime": {
                "solver_algorithm_search_iterations": 1,
                "solver_algorithm_move_attempts": 6,
                "solver_algorithm_stop_reason": "no_improvement",
                "solver_algorithm_elapsed_ms": 90,
            },
            "run": {"elapsed_ms": 100},
        },
    ]
    micro_results = [
        {
            "case": "cvrplib/A/A-n32-k5.vrp",
            "seed": 11,
            "comparison": "tie",
            "candidate_elapsed_ms": 130,
            "champion_elapsed_ms": 3000,
        },
        {
            "case": "cvrplib/B/B-n31-k5.vrp",
            "seed": 11,
            "comparison": "loss",
            "candidate_elapsed_ms": 100,
            "champion_elapsed_ms": 3000,
        },
    ]

    issue = _solver_design_low_effort_issue(
        patch=patch,
        hypothesis=hypothesis,
        runs=runs,
        micro_results=micro_results,
    )

    assert issue is not None
    assert "low active search effort" in issue
    assert "no smoke micro-benchmark win" in issue
    assert "policies/baseline_modules/scheduler.py" in issue


def test_solver_design_low_effort_issue_allows_smoke_micro_win() -> None:
    patch = PatchProposal(
        file_path="policies/baseline_modules/construction.py",
        action="modify",
        code_content="def seed_pool(instance):\n    return []\n",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Improve ALNS search from better construction seeds.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
    )
    runs = [
        {
            "case": "cvrplib/A/A-n32-k5.vrp",
            "seed": 11,
            "passed": True,
            "runtime": {
                "solver_algorithm_search_iterations": 2,
                "solver_algorithm_move_attempts": 12,
                "solver_algorithm_stop_reason": "no_improvement",
            },
            "run": {"elapsed_ms": 100},
        },
        {
            "case": "cvrplib/B/B-n31-k5.vrp",
            "seed": 11,
            "passed": True,
            "runtime": {
                "solver_algorithm_search_iterations": 2,
                "solver_algorithm_move_attempts": 12,
                "solver_algorithm_stop_reason": "no_improvement",
            },
            "run": {"elapsed_ms": 100},
        },
    ]
    micro_results = [
        {
            "case": "cvrplib/A/A-n32-k5.vrp",
            "seed": 11,
            "comparison": "win",
            "candidate_elapsed_ms": 100,
            "champion_elapsed_ms": 3000,
        }
    ]

    assert (
        _solver_design_low_effort_issue(
            patch=patch,
            hypothesis=hypothesis,
            runs=runs,
            micro_results=micro_results,
        )
        is None
    )


def test_algorithm_smoke_runs_screening_case_preview(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_algorithm.py",
            ),
            "patch": {
                "file_path": "policies/baseline_algorithm.py",
                "action": "modify",
                "code_content": (
                    "def solve(instance, rng, time_limit_sec, context):\n"
                    "    if instance.customer_count > 4:\n"
                    "        raise RuntimeError('screening case only')\n"
                    "    solution = context.make_solution(context.nearest_neighbor())\n"
                    "    context.record_iteration('seed', 1)\n"
                    "    return solution\n"
                ),
            },
        },
        context,
    )

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["passed"] is False
    assert payload["workspace_materialized"] is True
    assert payload["runtime_smoke"]["case_count"] == 3
    assert "data/tiny_6.json" in rendered
    assert "screening case only" in rendered


def test_algorithm_smoke_uses_active_formal_split_over_workspace_tiny_split(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        split_manifest=SplitManifest(
            version="test-active-formal",
            canary=["controlled/data/synthetic_controlled_canary_5.vrp"],
            screening=[
                "controlled/data/synthetic_screening_micro_5.vrp",
                "controlled/data/synthetic_screening_split_6.vrp",
                "controlled/data/synthetic_validation_micro_5.vrp",
                "controlled/data/synthetic_validation_split_6.vrp",
                "controlled/data/synthetic_frozen_micro_5.vrp",
                "controlled/data/synthetic_frozen_split_6.vrp",
                "controlled/data/synthetic_final_micro_5.vrp",
                "controlled/data/synthetic_final_split_6.vrp",
            ],
        ),
        seed_ledger=SeedLedgerConfig(
            screening=[11, 29],
            validation=[47],
            frozen=[61],
            canary=[101],
        ),
    )

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_algorithm.py",
            ),
            "patch": {
                "file_path": "policies/baseline_algorithm.py",
                "action": "modify",
                "code_content": (
                    "def solve(instance, rng, time_limit_sec, context):\n"
                    "    solution = context.make_solution(context.nearest_neighbor())\n"
                    "    context.record_iteration('seed', 1)\n"
                    "    return solution\n"
                ),
            },
        },
        context,
    )

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["runtime_smoke"]["case_count"] == 5
    assert "controlled/data/synthetic_controlled_canary_5.vrp" in rendered
    assert "controlled/data/synthetic_screening_micro_5.vrp" in rendered
    assert "controlled/data/synthetic_validation_micro_5.vrp" in rendered
    assert "controlled/data/synthetic_frozen_split_6.vrp" in rendered
    assert "controlled/data/synthetic_final_split_6.vrp" in rendered
    assert "audited_problem_data_manifest" in rendered
    assert "data/tiny_6.json" not in rendered
    assert '"seed": 101' in rendered


def test_runtime_smoke_does_not_resolve_ambient_env_data_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    base_workspace = tmp_path / "base"
    data_root = tmp_path / "problem_data"
    workspace.mkdir()
    base_workspace.mkdir()
    case = data_root / "cvrplib" / "A" / "A-n32-k5.vrp"
    case.parent.mkdir(parents=True)
    case.write_text("NAME : A-n32-k5\n", encoding="utf-8")
    monkeypatch.setenv("SCION_PROBLEM_DATA_ROOT", str(data_root))

    resolved = _resolve_smoke_instance_path(
        workspace=workspace,
        base_workspace=base_workspace,
        case_rel="cvrplib/A/A-n32-k5.vrp",
    )

    assert resolved is None


def test_runtime_smoke_resolves_explicit_safe_data_root(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    base_workspace = tmp_path / "base"
    data_root = tmp_path / "problem_data"
    workspace.mkdir()
    base_workspace.mkdir()
    case = data_root / "cvrplib" / "A" / "A-n32-k5.vrp"
    case.parent.mkdir(parents=True)
    case.write_text("NAME : A-n32-k5\n", encoding="utf-8")

    resolved = _resolve_smoke_instance_path(
        workspace=workspace,
        base_workspace=base_workspace,
        case_rel="cvrplib/A/A-n32-k5.vrp",
        safe_data_roots=(data_root,),
    )

    assert resolved == case


def test_runtime_smoke_rejects_absolute_case_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    base_workspace = tmp_path / "base"
    workspace.mkdir()
    base_workspace.mkdir()
    case = tmp_path / "absolute.vrp"
    case.write_text("NAME : absolute\n", encoding="utf-8")

    resolved = _resolve_smoke_instance_path(
        workspace=workspace,
        base_workspace=base_workspace,
        case_rel=str(case),
        safe_data_roots=(tmp_path,),
    )

    assert resolved is None


def test_algorithm_smoke_rejects_preferred_solver_design_baseline_wrapper(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_algorithm.py",
            ),
            "patch": {
                "file_path": "policies/baseline_algorithm.py",
                "action": "modify",
                "code_content": (
                    "def solve(instance, rng, time_limit_sec, context):\n"
                    "    return context.baseline()\n"
                ),
            },
        },
        context,
    )

    rendered = json.dumps(observation.structured_payload, sort_keys=True)
    assert observation.is_error is False
    assert observation.structured_payload["passed"] is False
    assert "must not call context.baseline" in rendered


def test_solver_design_code_prompt_omits_duplicate_champion_policy_bundle() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)

    creative.generate_code(
        {
            "problem_summary": "CVRP.",
            "research_surface_name": "solver_design",
            "research_surface_kind": "solver_design",
            "change_locus": "solver_design",
            "hypothesis_detail": "Implement a direct solver body.",
            "operator_interface_spec": "def solve(instance, rng, time_limit_sec, context)",
            "import_whitelist": "math, random, time",
            "champion_operators_code": (
                "### policies/search_policy.py\n"
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.75\n"
            ),
            "target_file_code": (
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return None\n"
            ),
            "reference_operators": "",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "solver.py, adapter.py",
        }
    )

    rendered_system = json.dumps(client.system_blocks, sort_keys=True)
    rendered_prompt = "\n".join(client.prompts)

    assert "baseline_time_fraction" not in rendered_system
    assert "Target File" in rendered_prompt
    assert "def solve(instance, rng, time_limit_sec, context):" in rendered_prompt


def test_solver_design_code_prompt_enforces_compact_single_mechanism_scope() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)

    creative.generate_code(
        {
            "problem_summary": "CVRP.",
            "research_surface_name": "solver_design",
            "research_surface_kind": "solver_design",
            "change_locus": "solver_design",
            "code_generation_mode": "compact_timeout_retry",
            "hypothesis_detail": (
                "Implement a hybrid ALNS/VNS route-pool destroy-repair "
                "population portfolio."
            ),
            "agentic_code_scope_control": {
                "mode": "compact_timeout_retry",
                "detected_broad_terms": [
                    "hybrid",
                    "alns",
                    "destroy",
                    "repair",
                    "portfolio",
                ],
                "failure_detail": "code_generation_timeout",
            },
            "solver_design_api_manifest": (
                "Approved target_file: policies/baseline_modules/destroy_repair.py\n"
                "- policies/baseline_modules/construction.py: exports "
                "def _clarke_wright_savings(instance, target_routes); "
                "def _nearest_neighbor(instance)\n"
                "Target-specific rule for destroy_repair.py: scheduler.py "
                "may only import exact new symbols from .destroy_repair."
            ),
            "solver_design_branch_current_integration_files": (
                "### policies/baseline_algorithm.py\n"
                "Provenance: branch_workspace; readable=True\n"
                "```python\n"
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    solver = _ALNSVNSSolver(context=context)\n"
                "    return solver.solve(instance, rng)\n"
                "```\n"
                "### policies/baseline_modules/scheduler.py\n"
                "Provenance: branch_workspace; readable=True\n"
                "```python\n"
                "class _ALNSVNSSolver:\n"
                "    def solve(self, instance, rng):\n"
                "        return None\n"
                "```"
            ),
            "operator_interface_spec": "def solve(instance, rng, time_limit_sec, context)",
            "import_whitelist": "math, random, time",
            "champion_operators_code": "",
            "target_file_code": (
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return None\n"
            ),
            "reference_operators": "",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "solver.py, adapter.py",
        }
    )

    rendered_system = "\n".join(
        block["text"] for blocks in client.system_blocks for block in blocks
    )
    rendered_prompt = "\n".join(client.prompts)

    assert "Compact Solver-Design Implementation Scope" in rendered_system
    assert "one primary mechanism" in rendered_system
    assert "around 180 lines or less" in rendered_system
    assert (
        "Do not implement more than two move/neighborhood families" in rendered_system
    )
    assert "target file should own the mechanism" in rendered_system
    assert "stable runtime contract" in rendered_system
    assert "Approved Target File Full Current Content" in rendered_prompt
    assert "Branch-Current Integration Files" in rendered_prompt
    assert "branch_workspace" in rendered_prompt
    assert "smallest necessary wiring edits" in rendered_prompt
    assert "_ALNSVNSSolver(...).solve(instance, rng)" in rendered_system
    assert "scheduler as orchestration" in rendered_system
    assert "_ALNSVNSSolver.__init__(self, *" in rendered_system
    assert "_ALNSVNSSolver.solve(self, instance, rng)" in rendered_system
    assert "initial-state hooks inside scheduler methods" in rendered_system
    assert "zero iterations and zero move attempts" in rendered_system
    assert "_default_vns_operators()" in rendered_system
    assert "detached `_run`/`run`" in rendered_system
    assert "do not implement a full portfolio" in rendered_system
    assert "_Solution.routes" in rendered_system
    assert "not `list[list[int]]`" in rendered_system
    assert "from_public" in rendered_system
    assert "from_cvrp_solution" in rendered_system
    assert "context.make_solution(solution.routes_as_tuples())" in rendered_system
    assert "Do not edit `policies/baseline_modules/state.py`" in rendered_prompt
    assert "complete contents of the target algorithm module" in rendered_prompt
    assert "Solver-Design Module API Manifest" in rendered_prompt
    assert "_clarke_wright_savings" in rendered_prompt
    assert "may only import exact new symbols from .destroy_repair" in rendered_prompt


def test_latest_preview_failure_detail_uses_latest_preview_not_stale_smoke() -> None:
    smoke = ProposalObservation(
        observation_id="smoke-1",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="call-1",
        observation_type="tool_result",
        summary="Algorithm smoke failed.",
        structured_payload={
            "passed": False,
            "runtime_smoke": {
                "issues": ["old runtime failure"],
            },
        },
    )
    contract = ProposalObservation(
        observation_id="contract-1",
        session_id="session-1",
        tool_name="proposal.contract_preview",
        tool_call_id="call-2",
        observation_type="tool_result",
        summary="Contract preview failed.",
        structured_payload={
            "passed": False,
            "issue_summary": "new object model API misuse",
        },
    )

    detail = _latest_preview_failure_detail([smoke, contract])

    assert detail is not None
    assert "contract preview did not pass" in detail
    assert "new object model API misuse" in detail
    assert "old runtime failure" not in detail


def test_solver_run_failure_detail_includes_category_exit_and_stdout() -> None:
    detail = _solver_run_failure_detail(
        RunResult(
            success=False,
            exit_code=-9,
            stdout="last solver line",
            stderr="",
            elapsed_ms=12034,
            output_path=None,
            error_category="timeout",
        )
    )

    assert "solver run failed" in detail
    assert "exit_code=-9" in detail
    assert "error_category=timeout" in detail
    assert "elapsed_ms=12034" in detail
    assert "stdout=last solver line" in detail


def test_compact_algorithm_smoke_observation_preserves_pass_signal() -> None:
    observation = ProposalObservation(
        observation_id="smoke-1",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-10",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke passed on tainted synthetic preview.",
        structured_payload={
            "passed": True,
            "non_promotional": True,
            "tainted_debug": True,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
            "hypothesis": {
                "passed": True,
                "hypothesis_text": "x" * 8000,
                "contract": {"passed": True, "check_count": 6},
                "checks": [{"name": "C2_locus", "passed": True}],
            },
            "patch": {
                "passed": True,
                "code_content": "x" * 48000,
                "contract": {"passed": True, "check_count": 10},
                "checks": [{"name": "C7_interface", "passed": True}],
                "problem_preview": {
                    "passed": True,
                    "surface": "solver_design",
                    "checks": [{"name": "preview", "passed": True}],
                    "workspace_materialized": False,
                },
            },
            "problem_preview": {
                "passed": True,
                "surface": "solver_design",
                "checks": [{"name": "preview", "passed": True}],
                "workspace_materialized": False,
            },
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "workspace_materialized": True,
                "case": "controlled/data/canary.vrp",
                "seed": 77,
                "case_count": 1,
                "issues": ["runtime audit failed"],
                "runtime_audit_failure": {
                    "error_category": "solver_algorithm_errors",
                    "detail": "'_Route' object is not subscriptable",
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {"type": "error", "message": "'_Route' object is not subscriptable"}
                    ],
                },
                "runtime": {
                    "solver_algorithm_loaded": True,
                    "solver_algorithm_active": True,
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {"type": "error", "message": "'_Route' object is not subscriptable"}
                    ],
                },
                "micro_benchmark": {
                    "non_promotional": True,
                    "tainted_debug": True,
                    "comparable_cases": 1,
                    "wins": 0,
                    "losses": 1,
                    "ties": 0,
                    "results": [
                        {
                            "label": "canary",
                            "case": "controlled/data/canary.vrp",
                            "comparison": "loss",
                            "delta": -3.0,
                            "decisive_metric": "total_distance",
                            "runtime_delta_ms": -100,
                        }
                    ],
                },
                "run": {"success": True, "detail": "solver smoke completed"},
            },
        },
    )

    compact = _compact_algorithm_smoke_observation(observation)

    assert compact is not None
    assert compact.is_error is False
    assert _json_size(_observation_prompt_payload(compact)) < 2200
    assert compact.structured_payload["passed"] is True
    assert compact.structured_payload["patch"]["contract"]["check_count"] == 10
    assert compact.structured_payload["problem_preview"]["passed"] is True
    assert compact.structured_payload["runtime_smoke"]["runtime"][
        "solver_algorithm_errors"
    ] == 1
    assert "_Route" in compact.structured_payload["runtime_smoke"][
        "runtime_audit_failure"
    ]["detail"]
    assert compact.structured_payload["runtime_smoke"]["micro_benchmark"][
        "losses"
    ] == 1
    assert compact.structured_payload["compact_due_to_budget"] is True


def test_code_prompt_observation_payload_preserves_algorithm_smoke_runtime_detail() -> None:
    observation = ProposalObservation(
        observation_id="smoke-runtime",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-12",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke found issues.",
        structured_payload={
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "case": "controlled/data/canary.vrp",
                "issues": ["solver runtime audit reported solver_algorithm_errors=1"],
                "runtime_audit_failure": {
                    "detail": "solver runtime audit reported solver_algorithm_errors=1",
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {
                            "type": "error",
                            "message": "NameError: DESTROY_RATIO_LOW is not defined",
                        }
                    ],
                },
                "runtime": {
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {
                            "type": "error",
                            "message": "NameError: DESTROY_RATIO_LOW is not defined",
                        }
                    ],
                },
                "run": {
                    "success": True,
                    "detail": "solver smoke completed",
                    "stderr": "",
                },
            },
        },
    )

    selected = _code_prompt_observations([observation])
    compact = _code_observation_prompt_payload(selected[0])
    detail = _algorithm_smoke_failure_detail([observation])
    rendered = json.dumps(compact, sort_keys=True, default=str)

    assert selected == [observation]
    assert "DESTROY_RATIO_LOW" in rendered
    assert detail is not None
    assert "DESTROY_RATIO_LOW" in detail


def test_algorithm_smoke_failure_detail_includes_repair_guidance() -> None:
    observation = ProposalObservation(
        observation_id="smoke-runtime",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-12",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke found issues.",
        structured_payload={
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "issues": ["solver runtime audit reported solver_algorithm_errors=1"],
                "runtime": {
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {
                            "policy": "policies/baseline_algorithm.py",
                            "status": "error",
                            "detail": "solve failed: '_Solution' object has no attribute '_instance'",
                        }
                    ],
                },
                "repair_guidance": [
                    "Specific fix: replace solution._instance with solution.instance.",
                    "_Solution.routes contains _Route objects.",
                ],
            },
        },
    )

    detail = _algorithm_smoke_failure_detail([observation])

    assert detail is not None
    assert "_Solution" in detail
    assert "solution.instance" in detail


def test_algorithm_smoke_compacts_to_fit_remaining_observation_budget(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    config = AgenticToolLoopConfig(max_observation_chars=64000)
    state = AgenticProposalSessionState(
        session_id="session-smoke-budget",
        campaign_id="camp-1",
        branch_id="branch-1",
        observation_chars_used=62400,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    observation = ProposalObservation(
        observation_id="smoke-2",
        session_id=state.session_id,
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-11",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke passed on tainted synthetic preview.",
        structured_payload={
            "passed": True,
            "non_promotional": True,
            "tainted_debug": True,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
            "patch": {
                "passed": True,
                "code_content": "x" * 48000,
                "contract": {"passed": True, "check_count": 10},
                "problem_preview": {"passed": True, "surface": "solver_design"},
            },
            "problem_preview": {"passed": True, "surface": "solver_design"},
        },
    )

    compact = session._enforce_observation_budget(context, state, observation)

    assert compact.is_error is False
    assert compact.failure_code is None
    assert compact.structured_payload["passed"] is True
    assert compact.structured_payload["compact_due_to_budget"] is True
    assert _json_size(_observation_prompt_payload(compact)) <= (
        config.max_observation_chars - state.observation_chars_used
    )
