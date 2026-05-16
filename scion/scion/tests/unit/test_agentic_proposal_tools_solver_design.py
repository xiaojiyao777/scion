from __future__ import annotations

from scion.tests.unit.test_agentic_proposal_tools_helpers import (
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
    assert after == before


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
    assert "data/tiny_6.json" not in rendered
    assert '"seed": 101' in rendered


def test_runtime_smoke_resolves_external_problem_data_root(
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

    assert resolved == case


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
