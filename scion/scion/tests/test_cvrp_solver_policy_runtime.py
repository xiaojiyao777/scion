from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *

def test_default_algorithm_blueprint_policy_matches_contract_gate_interface() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(CVRP_DIR / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    policy_path = CVRP_DIR / "policies" / "algorithm_blueprint.py"
    gate = ContractGate(legacy_spec)

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/algorithm_blueprint.py",
            action="modify",
            code_content=policy_path.read_text(encoding="utf-8"),
        )
    )

    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert result.passed is True
    assert c7.passed is True


def test_default_baseline_policy_matches_contract_gate_interface() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(CVRP_DIR / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    policy_path = CVRP_DIR / "policies" / "baseline_policy.py"
    gate = ContractGate(legacy_spec)

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_policy.py",
            action="modify",
            code_content=policy_path.read_text(encoding="utf-8"),
        )
    )

    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert result.passed is True
    assert c7.passed is True


def test_baseline_policy_surface_declares_runtime_fields_and_defaults(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "baseline_policy"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert required_fields == (
        "baseline_policy_loaded",
        "baseline_policy_errors",
        "baseline_policy_params",
        "baseline_destroy_ratio",
        "baseline_segment_length",
        "baseline_reaction_factor",
        "baseline_use_vns",
        "baseline_vns_max_no_improve",
        "baseline_max_destroy_customers",
    )
    assert set(required_fields).issubset(runtime)
    assert runtime["baseline_policy_loaded"] is True
    assert runtime["baseline_policy_errors"] == 0
    assert runtime["baseline_policy_params"]["destroy_ratio"] == [0.1, 0.4]
    assert runtime["baseline_destroy_ratio"] == [0.1, 0.4]
    assert runtime["baseline_use_vns"] is True
    assert runtime["baseline_vns_max_no_improve"] == 5000
    assert runtime["baseline_max_destroy_customers"] == 200
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="baseline_policy",
        )
        is None
    )


def test_invalid_baseline_policy_output_is_runtime_audit_failure(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_policy.py").write_text(
        "\n".join(
            [
                "def baseline_params(instance, time_limit_sec):",
                "    return {",
                "        'destroy_ratio': (0.9, 0.1),",
                "        'segment_length': 0,",
                "        'use_vns': 'yes',",
                "        'unknown': 1,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="baseline_policy",
    )

    assert raw["runtime"]["baseline_policy_errors"] == 5
    assert raw["runtime"]["baseline_policy_params"]["destroy_ratio"] == [0.1, 0.4]
    assert raw["runtime"]["baseline_segment_length"] == 1
    assert raw["runtime"]["baseline_use_vns"] is True
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"
    assert "baseline_policy_errors" in issue["detail"]
    assert "unknown" in json.dumps(raw["runtime"]["baseline_policy_events"])


def test_modified_baseline_policy_changes_repo_local_baseline_kwargs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    fake_root = tmp_path / "fake_vrp"
    fake_src = fake_root / "src"
    fake_src.mkdir(parents=True)
    (fake_src / "__init__.py").write_text("", encoding="utf-8")
    (fake_src / "parser.py").write_text(
        "\n".join(
            [
                "from types import SimpleNamespace",
                "",
                "def parse_vrp(path):",
                "    return SimpleNamespace(depot=0, dimension=4)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    capture_path = tmp_path / "baseline_kwargs.json"
    (fake_src / "solver.py").write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "from types import SimpleNamespace",
                "",
                "def solve(instance, **kwargs):",
                "    capture = os.environ.get('SCION_FAKE_BASELINE_CAPTURE')",
                "    if capture:",
                "        with open(capture, 'w', encoding='utf-8') as f:",
                "            json.dump(kwargs, f, sort_keys=True)",
                "    route = SimpleNamespace(customers=[1, 2, 3])",
                "    solution = SimpleNamespace(routes=[route])",
                "    return SimpleNamespace(",
                "        solution=solution,",
                "        elapsed=0.01,",
                "        iterations=3,",
                "        best_cost=30.0,",
                "    )",
                "",
            ]
        ),
        encoding="utf-8",
    )
    case_dir = fake_root / "cases"
    case_dir.mkdir()
    instance_path = case_dir / "case.vrp"
    instance_path.write_text("", encoding="utf-8")
    (workspace / "policies" / "baseline_policy.py").write_text(
        "\n".join(
            [
                "def baseline_params(instance, time_limit_sec):",
                "    return {",
                "        'destroy_ratio': (0.05, 0.25),",
                "        'segment_length': 25,",
                "        'reaction_factor': 0.3,",
                "        'vns_max_no_improve': 17,",
                "        'use_vns': False,",
                "        'cw_threshold': 7,",
                "        'vns_threshold': 8,",
                "        'alns_threshold': 9,",
                "        'max_destroy_customers': 11,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    instance = CvrpInstance(
        name="fake_baseline_case",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=1),
            CvrpNode(id=2, x=2.0, y=0.0, demand=1),
            CvrpNode(id=3, x=3.0, y=0.0, demand=1),
        ),
        allowed_routes=1,
        use_integer_cost=True,
    )
    monkeypatch.setenv("SCION_CVRP_DATA_ROOT", str(fake_root))
    monkeypatch.setenv("SCION_FAKE_BASELINE_CAPTURE", str(capture_path))
    for module_name in ("src", "src.parser", "src.solver"):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    baseline_policy = cvrp_solver._load_baseline_policy(
        workspace_root=workspace,
        instance=instance,
        time_limit_sec=2.0,
    )
    solution, audit = cvrp_solver.solve_baseline(
        instance=instance,
        instance_path=str(instance_path),
        seed=5,
        rng=random.Random(5),
        time_limit_sec=2.0,
        baseline_time_fraction=0.5,
        baseline_policy=baseline_policy,
    )
    if str(fake_root) in sys.path:
        sys.path.remove(str(fake_root))

    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert solution.routes == ((1, 2, 3),)
    assert captured["time_limit"] == 1.0
    assert captured["seed"] == 5
    assert captured["max_routes"] == 1
    assert captured["destroy_ratio"] == [0.05, 0.25]
    assert captured["segment_length"] == 25
    assert captured["reaction_factor"] == 0.3
    assert captured["vns_max_no_improve"] == 17
    assert captured["use_vns"] is False
    assert captured["cw_threshold"] == 7
    assert captured["vns_threshold"] == 8
    assert captured["alns_threshold"] == 9
    assert captured["max_destroy_customers"] == 11
    assert audit["baseline_mode"] == "vrp_alns_vns"
    assert audit["baseline_policy_errors"] == 0
    assert audit["baseline_destroy_ratio"] == [0.05, 0.25]
    assert audit["baseline_use_vns"] is False


def test_alns_vns_policy_overrides_repo_local_baseline_kwargs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    fake_root = tmp_path / "fake_vrp"
    fake_src = fake_root / "src"
    fake_src.mkdir(parents=True)
    (fake_src / "__init__.py").write_text("", encoding="utf-8")
    (fake_src / "parser.py").write_text(
        "\n".join(
            [
                "from types import SimpleNamespace",
                "",
                "def parse_vrp(path):",
                "    return SimpleNamespace(depot=0, dimension=4)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    capture_path = tmp_path / "alns_vns_kwargs.json"
    (fake_src / "solver.py").write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "from types import SimpleNamespace",
                "",
                "def solve(instance, **kwargs):",
                "    capture = os.environ.get('SCION_FAKE_BASELINE_CAPTURE')",
                "    if capture:",
                "        with open(capture, 'w', encoding='utf-8') as f:",
                "            json.dump(kwargs, f, sort_keys=True)",
                "    route = SimpleNamespace(customers=[1, 2, 3])",
                "    solution = SimpleNamespace(routes=[route])",
                "    return SimpleNamespace(",
                "        solution=solution,",
                "        elapsed=0.02,",
                "        iterations=4,",
                "        best_cost=28.0,",
                "    )",
                "",
            ]
        ),
        encoding="utf-8",
    )
    case_dir = fake_root / "cases"
    case_dir.mkdir()
    instance_path = case_dir / "case.vrp"
    instance_path.write_text("", encoding="utf-8")
    (workspace / "policies" / "alns_vns_policy.py").write_text(
        "\n".join(
            [
                "def alns_vns_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'components': ['alns'],",
                "        'component_weights': {'alns': 2.5, 'vns': 0.5},",
                "        'params': {",
                "            'destroy_ratio': (0.12, 0.2),",
                "            'segment_length': 31,",
                "            'reaction_factor': 0.25,",
                "            'vns_max_no_improve': 19,",
                "            'use_vns': False,",
                "            'cw_threshold': 6,",
                "            'vns_threshold': 7,",
                "            'alns_threshold': 8,",
                "            'max_destroy_customers': 9,",
                "        },",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    instance = CvrpInstance(
        name="fake_alns_vns_case",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=1),
            CvrpNode(id=2, x=2.0, y=0.0, demand=1),
            CvrpNode(id=3, x=3.0, y=0.0, demand=1),
        ),
        allowed_routes=1,
        use_integer_cost=True,
    )
    monkeypatch.setenv("SCION_CVRP_DATA_ROOT", str(fake_root))
    monkeypatch.setenv("SCION_FAKE_BASELINE_CAPTURE", str(capture_path))
    for module_name in ("src", "src.parser", "src.solver"):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    alns_vns_policy = cvrp_solver._load_alns_vns_policy(
        workspace_root=workspace,
        instance=instance,
        time_limit_sec=2.0,
    )
    solution, audit = cvrp_solver.solve_baseline(
        instance=instance,
        instance_path=str(instance_path),
        seed=5,
        rng=random.Random(5),
        time_limit_sec=2.0,
        baseline_time_fraction=0.5,
        alns_vns_policy=alns_vns_policy,
    )
    if str(fake_root) in sys.path:
        sys.path.remove(str(fake_root))

    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert solution.routes == ((1, 2, 3),)
    assert captured["destroy_ratio"] == [0.12, 0.2]
    assert captured["segment_length"] == 31
    assert captured["reaction_factor"] == 0.25
    assert captured["vns_max_no_improve"] == 19
    assert captured["use_vns"] is False
    assert captured["cw_threshold"] == 6
    assert captured["vns_threshold"] == 7
    assert captured["alns_threshold"] == 8
    assert captured["max_destroy_customers"] == 9
    assert audit["baseline_policy_params"]["segment_length"] == 31
    assert audit["alns_vns_surface_loaded"] is True
    assert audit["alns_vns_active"] is True
    assert audit["alns_vns_errors"] == 0
    assert audit["alns_vns_components"] == ["alns"]
    assert audit["alns_vns_component_weights"] == {"alns": 2.5, "vns": 0.5}
    assert audit["alns_vns_attempts"] == 4
    assert audit["alns_vns_accepted"] == 1
    assert audit["alns_vns_initial_distance"] == 6.0
    assert audit["alns_vns_returned_distance"] == 28.0
    assert audit["alns_vns_phase_delta_sum"] == 0.0
    assert audit["alns_vns_objective_delta"] == {
        "baseline_phase": 0.0,
        "initial_distance": 6.0,
        "returned_distance": 28.0,
    }
    assert audit["alns_vns_runtime_ms"] == 20
    assert audit["alns_vns_stop_reason"] == "vrp_alns_vns"


def test_alns_vns_policy_audit_records_positive_baseline_phase_delta() -> None:
    policy = cvrp_solver._alns_vns_policy_defaults()
    policy["alns_vns_active"] = True

    audit = cvrp_solver._finalize_alns_vns_policy_audit(
        policy,
        {
            "baseline_mode": "vrp_alns_vns",
            "baseline_elapsed_s": 0.5,
            "baseline_iterations": 12,
            "baseline_cost": 90.0,
        },
        construction_audit={"construction_distance": 125.0},
    )

    assert audit["alns_vns_attempts"] == 12
    assert audit["alns_vns_accepted"] == 1
    assert audit["alns_vns_initial_distance"] == 125.0
    assert audit["alns_vns_returned_distance"] == 90.0
    assert audit["alns_vns_phase_delta_sum"] == 35.0
    assert audit["alns_vns_objective_delta"] == {
        "baseline_phase": 35.0,
        "initial_distance": 125.0,
        "returned_distance": 90.0,
    }


def test_active_main_search_declared_baseline_fraction_controls_formal_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    fake_root = tmp_path / "fake_vrp"
    fake_src = fake_root / "src"
    fake_src.mkdir(parents=True)
    (fake_src / "__init__.py").write_text("", encoding="utf-8")
    (fake_src / "parser.py").write_text(
        "from types import SimpleNamespace\n\n"
        "def parse_vrp(path):\n"
        "    return SimpleNamespace(depot=0, dimension=4)\n",
        encoding="utf-8",
    )
    capture_path = tmp_path / "baseline_kwargs.json"
    (fake_src / "solver.py").write_text(
        "import json\n"
        "import os\n"
        "from types import SimpleNamespace\n\n"
        "def solve(instance, **kwargs):\n"
        "    capture = os.environ.get('SCION_FAKE_BASELINE_CAPTURE')\n"
        "    if capture:\n"
        "        with open(capture, 'w', encoding='utf-8') as f:\n"
        "            json.dump(kwargs, f, sort_keys=True)\n"
        "    route = SimpleNamespace(customers=[1, 2, 3])\n"
        "    solution = SimpleNamespace(routes=[route])\n"
        "    return SimpleNamespace(solution=solution, elapsed=0.01, iterations=3, best_cost=30.0)\n",
        encoding="utf-8",
    )
    case_dir = fake_root / "cases"
    case_dir.mkdir()
    instance_path = case_dir / "case.vrp"
    instance_path.write_text("", encoding="utf-8")
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.2, 'params': {}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair'], 'rounds': 1, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    instance = CvrpInstance(
        name="fake_baseline_case",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=1),
            CvrpNode(id=2, x=2.0, y=0.0, demand=1),
            CvrpNode(id=3, x=3.0, y=0.0, demand=1),
        ),
        allowed_routes=1,
        use_integer_cost=True,
    )
    monkeypatch.setenv("SCION_CVRP_DATA_ROOT", str(fake_root))
    monkeypatch.setenv("SCION_FAKE_BASELINE_CAPTURE", str(capture_path))
    for module_name in ("src", "src.parser", "src.solver"):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    main_search_strategy = cvrp_solver._load_main_search_strategy(
        workspace_root=workspace,
        instance=instance,
        time_limit_sec=2.0,
    )
    solution, audit = cvrp_solver.solve_baseline(
        instance=instance,
        instance_path=str(instance_path),
        seed=5,
        rng=random.Random(5),
        time_limit_sec=2.0,
        baseline_time_fraction=main_search_strategy[
            "main_search_baseline_time_fraction"
        ],
        main_search_strategy=main_search_strategy,
    )
    if str(fake_root) in sys.path:
        sys.path.remove(str(fake_root))

    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert solution.routes == ((1, 2, 3),)
    assert main_search_strategy["main_search_baseline_time_fraction"] == 0.2
    assert main_search_strategy["main_search_baseline_budget_policy"] == "declared"
    assert captured["time_limit"] == 0.4
    assert audit["main_search_baseline_time_fraction_effective"] == 0.2
    assert audit["main_search_baseline_quality_guard_applied"] is False


def test_active_main_search_formal_floor_budget_policy_clamps_budget() -> None:
    main_search_strategy = {
        "main_search_strategy_active": True,
        "main_search_baseline_budget_policy": "formal_floor",
    }

    assert (
        cvrp_solver._effective_baseline_time_fraction(
            0.2,
            is_vrp=True,
            baseline_required=True,
            main_search_strategy=main_search_strategy,
        )
        == 0.75
    )


