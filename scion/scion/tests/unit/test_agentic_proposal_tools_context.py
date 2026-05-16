from __future__ import annotations

from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    AgenticToolLoopConfig,
    BaseModel,
    DecisionFeatures,
    Path,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalTaint,
    ProposalToolFailureCode,
    ProposalToolRegistry,
    _context,
    _cvrp_context,
    _cvrp_context_with_champion,
    _tool_enabled_policy,
    _valid_hypothesis_payload,
    _valid_policy_patch_payload,
    fields,
    json,
    replace,
)


def test_list_and_read_surfaces_return_v2_metadata_without_domain_hardcoding(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)

    listed = registry.call("context.list_surfaces", {}, context)
    read = registry.call(
        "context.read_surface",
        {"surface": "search_policy", "include_code": True},
        context,
    )

    surfaces = {s["name"]: s for s in listed.structured_payload["surfaces"]}
    assert surfaces["search_policy"]["algorithm"]["role"] == "search_budget_policy"
    assert surfaces["search_policy"]["bounds"]["allowed_components"] == [
        "baseline_budget",
        "round_limit",
    ]
    surface = read.structured_payload["surface"]
    assert surface["algorithm"]["invocation_point"] == "before_main_search"
    assert surface["interface"]["required_functions"] == [
        "baseline_time_fraction",
        "max_operator_rounds",
    ]
    assert read.structured_payload["current_artifact"]["readable"] is True


def test_list_surfaces_returns_compact_payload_for_large_surface_specs(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call("context.list_surfaces", {}, context)
    rendered = json.dumps(observation.structured_payload, sort_keys=True, default=str)
    surfaces = {
        surface["name"]: surface
        for surface in observation.structured_payload["surfaces"]
    }

    assert observation.is_error is False
    assert observation.structured_payload["detail"] == "compact"
    assert "algorithm_blueprint" in surfaces
    assert surfaces["algorithm_blueprint"]["algorithm"]["role"] == (
        "top_level_algorithm_lifecycle"
    )
    assert "solver_design" in surfaces
    assert surfaces["solver_design"]["kind"] == "solver_design"
    assert surfaces["solver_design"]["algorithm"]["role"] == (
        "problem_object_solver_algorithm"
    )
    assert "prompt" not in rendered
    assert len(rendered) < AgenticToolLoopConfig().max_observation_chars // 2


def test_read_surface_defaults_to_compact_code_payload(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    policy_file = (
        Path(context.champion.code_snapshot_path) / "policies" / "search_policy.py"
    )
    policy_file.write_text(
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    return 0.50\n\n"
        "def max_operator_rounds(instance, time_limit_sec):\n"
        "    return 12\n\n" + "\n".join(f"# filler {idx}" for idx in range(800)),
        encoding="utf-8",
    )

    observation = registry.call(
        "context.read_surface",
        {"surface": "search_policy"},
        context,
    )
    artifact = observation.structured_payload["current_artifact"]
    rendered = json.dumps(observation.structured_payload, sort_keys=True, default=str)

    assert observation.is_error is False
    assert observation.structured_payload["detail"] == "compact"
    assert artifact["readable"] is True
    assert artifact["truncated"] is True
    assert artifact["max_chars"] == 1200
    assert len(artifact["content_preview"]) <= 1200
    assert len(rendered) < AgenticToolLoopConfig().max_observation_chars // 2


def test_read_surface_full_and_explicit_max_code_chars(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    policy_file = (
        Path(context.champion.code_snapshot_path) / "policies" / "search_policy.py"
    )
    full_code = (
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    return 0.50\n\n"
        "def max_operator_rounds(instance, time_limit_sec):\n"
        "    return 12\n\n" + "\n".join(f"# full filler {idx}" for idx in range(240))
    )
    policy_file.write_text(full_code, encoding="utf-8")

    full = registry.call(
        "context.read_surface",
        {"surface": "search_policy", "detail": "full"},
        context,
    )
    capped = registry.call(
        "context.read_surface",
        {
            "surface": "search_policy",
            "detail": "full",
            "max_code_chars": 80,
        },
        context,
    )

    full_artifact = full.structured_payload["current_artifact"]
    capped_artifact = capped.structured_payload["current_artifact"]
    assert full.is_error is False
    assert full.structured_payload["detail"] == "full"
    assert full_artifact["max_chars"] == 12000
    assert full_artifact["truncated"] is False
    assert full_artifact["content_preview"] == full_code
    assert capped.is_error is False
    assert capped_artifact["max_chars"] == 80
    assert capped_artifact["truncated"] is True
    assert len(capped_artifact["content_preview"]) <= 80


def test_read_algorithm_blueprint_compact_payload_stays_below_session_budget(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    listed = registry.call("context.list_surfaces", {}, context)
    read = registry.call(
        "context.read_surface",
        {"surface": "algorithm_blueprint"},
        context,
    )
    rendered = json.dumps(
        [listed.structured_payload, read.structured_payload],
        sort_keys=True,
        default=str,
    )

    assert listed.is_error is False
    assert read.is_error is False
    assert read.structured_payload["detail"] == "compact"
    assert read.structured_payload["surface"]["name"] == "algorithm_blueprint"
    assert read.structured_payload["current_artifact"]["readable"] is True
    assert len(rendered) < AgenticToolLoopConfig().max_observation_chars


def test_read_main_search_strategy_default_returns_compact_contract_below_budget(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call(
        "context.read_surface",
        {"surface": "solver_design"},
        context,
    )
    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True, default=str)

    assert observation.is_error is False
    assert observation.failure_code is None
    assert payload["detail"] == "compact"
    assert payload["section"] == "all"
    assert payload["surface"]["name"] == "solver_design"
    assert payload["surface"]["interface"]["required_functions"] == ["solve"]
    assert payload["surface_contract"]["schema_version"] == "surface-contract.v1"
    assert payload["surface_contract"]["available_sections"] == [
        "summary",
        "interface",
        "bounds",
        "evidence",
        "novelty",
        "target_preview",
    ]
    assert (
        payload["surface_contract"]["target_preview"]["content_preview_chars"] <= 1200
    )
    support_paths = {
        artifact["file_path"] for artifact in payload["support_artifacts"]
    }
    assert "policies/baseline_modules/state.py" in support_paths
    assert "policies/baseline_modules/construction.py" in support_paths
    assert "policies/baseline_modules/scheduler.py" in support_paths
    state_artifact = next(
        artifact
        for artifact in payload["support_artifacts"]
        if artifact["file_path"] == "policies/baseline_modules/state.py"
    )
    assert "class _Route" in state_artifact["python_api_summary"]
    assert "class _Solution" in state_artifact["python_api_summary"]
    assert any(
        "class _ALNSVNSSolver" in artifact.get("content_preview", "")
        for artifact in payload["support_artifacts"]
    )
    assert "content_preview" not in payload["surface_contract"]["target_preview"]
    assert "prompt" not in payload["surface"]
    assert "raw_metrics_ref" not in rendered
    assert "SECRET_VALIDATION" not in rendered
    assert "SECRET_FROZEN" not in rendered
    assert len(rendered) < 24000


def test_read_solver_design_module_target_includes_state_support_context(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call(
        "context.read_surface",
        {
            "surface": "solver_design",
            "target_file": "policies/baseline_modules/scheduler.py",
            "section": "target_preview",
            "detail": "full",
            "max_code_chars": 6000,
        },
        context,
    )
    payload = observation.structured_payload
    support = {
        artifact["file_path"]: artifact
        for artifact in payload["support_artifacts"]
    }

    assert observation.is_error is False
    assert payload["target_file"] == "policies/baseline_modules/scheduler.py"
    assert "policies/baseline_modules/state.py" in support
    assert "policies/baseline_algorithm.py" in support
    assert "policies/baseline_modules/scheduler.py" not in support
    assert "class _Route" in support["policies/baseline_modules/state.py"][
        "python_api_summary"
    ]
    assert "def solve(instance, rng, time_limit_sec, context)" in support[
        "policies/baseline_algorithm.py"
    ]["python_api_summary"]


def test_read_surface_section_mode_returns_interface_slice(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call(
        "context.read_surface",
        {"surface": "solver_design", "section": "interface"},
        context,
    )
    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True, default=str)

    assert observation.is_error is False
    assert payload["section"] == "interface"
    assert payload["surface"] == {
        "name": "solver_design",
        "kind": "solver_design",
        "section": "interface",
        "interface": payload["surface"]["interface"],
    }
    assert payload["surface"]["interface"]["function_signatures"] == {
        "solve": ["instance", "rng", "time_limit_sec", "context"]
    }
    assert "bounds" not in payload["surface"]
    assert "evidence" not in payload["surface"]
    assert "prompt" not in payload["surface"]
    assert "component-policy or lifecycle-config table" not in rendered
    assert len(rendered) < 8000


def test_read_surface_target_not_declared_fails_permission(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)

    observation = registry.call(
        "context.read_surface",
        {"surface": "search_policy", "target_file": "secret/holdout_metrics.json"},
        context,
    )

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.PERMISSION_DENIED


def test_read_surface_wildcard_does_not_match_nested_path(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    archive = Path(context.champion.code_snapshot_path) / "operators" / "archive"
    archive.mkdir()
    (archive / "secret.py").write_text(
        "SECRET_NESTED_OPERATOR = True\n", encoding="utf-8"
    )

    observation = registry.call(
        "context.read_surface",
        {"surface": "route_local", "target_file": "operators/archive/secret.py"},
        context,
    )

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.PERMISSION_DENIED
    assert "SECRET_NESTED_OPERATOR" not in json.dumps(
        observation.structured_payload,
        sort_keys=True,
    )


def test_read_surface_rejects_parent_and_absolute_target_paths(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    absolute_target = str(
        Path(context.champion.code_snapshot_path) / "operators" / "local_a.py"
    )

    traversal = registry.call(
        "context.read_surface",
        {
            "surface": "route_local",
            "target_file": "operators/../policies/search_policy.py",
        },
        context,
    )
    absolute = registry.call(
        "context.read_surface",
        {"surface": "route_local", "target_file": absolute_target},
        context,
    )

    assert traversal.is_error is True
    assert traversal.failure_code == ProposalToolFailureCode.PERMISSION_DENIED
    assert absolute.is_error is True
    assert absolute.failure_code == ProposalToolFailureCode.PERMISSION_DENIED


def test_read_surface_declared_symlink_escape_is_not_read(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    outside = tmp_path / "SECRET_OUTSIDE.py"
    outside.write_text("SECRET_SYMLINK_ESCAPE = True\n", encoding="utf-8")
    link = Path(context.champion.code_snapshot_path) / "operators" / "leak.py"
    link.symlink_to(outside)

    observation = registry.call(
        "context.read_surface",
        {"surface": "route_local", "target_file": "operators/leak.py"},
        context,
    )

    assert observation.is_error is False
    artifact = observation.structured_payload["current_artifact"]
    assert artifact["readable"] is False
    assert artifact["reason"] == "symlink_not_allowed"
    assert "SECRET_SYMLINK_ESCAPE" not in json.dumps(
        observation.structured_payload,
        sort_keys=True,
    )


def test_read_surface_declared_in_snapshot_symlink_is_not_read(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    solver = Path(context.champion.code_snapshot_path) / "solver.py"
    solver.write_text("SECRET_SOLVER_CONTENT = True\n", encoding="utf-8")
    link = Path(context.champion.code_snapshot_path) / "operators" / "leak.py"
    link.symlink_to(Path("..") / "solver.py")

    observation = registry.call(
        "context.read_surface",
        {"surface": "route_local", "target_file": "operators/leak.py"},
        context,
    )

    assert observation.is_error is False
    artifact = observation.structured_payload["current_artifact"]
    assert artifact["file_path"] == "operators/leak.py"
    assert artifact["readable"] is False
    assert artifact["reason"] == "symlink_not_allowed"
    assert "SECRET_SOLVER_CONTENT" not in json.dumps(
        observation.structured_payload,
        sort_keys=True,
    )


def test_read_only_tools_do_not_write_workspace_files(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    registry.call("context.read_surface", {"surface": "search_policy"}, context)
    registry.call("feedback.query_screening", {}, context)
    registry.call("feedback.query_holdout_summary", {}, context)
    registry.call("feedback.query_runtime", {}, context)
    registry.call("memory.query", {}, context)

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert after == before


def test_aps3_tool_observations_remain_tainted_and_bounded(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    observations = [
        registry.call(
            "proposal.draft_hypothesis", _valid_hypothesis_payload(), context
        ),
        registry.call("proposal.draft_patch", _valid_policy_patch_payload(), context),
        registry.call(
            "proposal.contract_preview",
            {"patch": _valid_policy_patch_payload()},
            context,
        ),
    ]

    for observation in observations:
        tool = registry.get(observation.tool_name)
        rendered = json.dumps(
            observation.structured_payload, sort_keys=True, default=str
        )
        assert observation.taint == ProposalTaint.PROPOSAL
        assert len(rendered) <= tool.max_result_chars
    assert observations[0].exposure_level == ProposalExposureLevel.SCRATCH
    assert observations[1].exposure_level == ProposalExposureLevel.SCRATCH


def test_registry_rejects_non_read_only_tool() -> None:
    class WriteTool:
        name = "unsafe.write"
        input_schema = BaseModel
        permission = "write_scratch"
        read_only = False
        concurrency_safe = False
        max_result_chars = 32000

        def call(self, args, context):  # pragma: no cover - registration must fail.
            raise AssertionError("tool should not be callable")

    registry = ProposalToolRegistry()

    try:
        registry.register(WriteTool())
    except ValueError as exc:
        assert "read-only tools only" in str(exc)
    else:  # pragma: no cover - explicit failure branch for clarity.
        raise AssertionError("non-read-only proposal tool was registered")


def test_tool_result_size_guard_returns_error(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    tool = registry.get("context.read_problem")
    tool.max_result_chars = 10

    observation = registry.call("context.read_problem", {}, _context(tmp_path))

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.RESULT_TOO_LARGE
    assert observation.structured_payload["max_result_chars"] == 10


def test_read_problem_returns_adapter_problem_object(tmp_path: Path) -> None:
    class AdapterWithProblemObject:
        def render_problem_summary(self) -> str:
            return "Adapter-rendered problem summary."

        def render_problem_object(self) -> str:
            return "Problem object: solver lifecycle and move grammar."

        def render_solver_mechanics(self) -> str:
            return "Solver mechanics: direct solve hook and fixed objective."

    context = replace(_context(tmp_path), adapter=AdapterWithProblemObject())
    registry = ProposalToolRegistry.default_read_only()

    observation = registry.call("context.read_problem", {}, context)

    assert observation.is_error is False
    assert observation.structured_payload["summary"] == (
        "Adapter-rendered problem summary."
    )
    assert observation.structured_payload["problem_object"] == (
        "Problem object: solver lifecycle and move grammar."
    )
    assert observation.structured_payload["problem_object_truncated"] is False
    assert observation.structured_payload["solver_mechanics"] == (
        "Solver mechanics: direct solve hook and fixed objective."
    )
    assert observation.structured_payload["solver_mechanics_truncated"] is False


def test_tool_observation_fields_do_not_enter_decision_features() -> None:
    observation_fields = {field.name for field in fields(ProposalObservation)}
    decision_fields = {field.name for field in fields(DecisionFeatures)}

    assert observation_fields.isdisjoint(decision_fields)
