"""Focused tests split from test_research_surfaces_solver_design_integration.py."""

from .research_surfaces_solver_design_support import *  # noqa: F401,F403

_SCHEDULER_LOCAL_SEARCH_IMPORT = (
    "from .local_search import _default_vns_operators, _two_opt_intra_polish, _vns\n"
)


def test_contract_gate_allows_multimodule_scheduler_integration_edit(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    construction_target = champion / "policies" / "baseline_modules" / "construction.py"
    scheduler_target = champion / "policies" / "baseline_modules" / "scheduler.py"
    construction_target.parent.mkdir(parents=True)
    construction_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "construction.py"
    ).read_text(encoding="utf-8")
    scheduler_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py"
    ).read_text(encoding="utf-8")
    construction_target.write_text(construction_code, encoding="utf-8")
    scheduler_target.write_text(scheduler_code, encoding="utf-8")
    construction_code = (
        construction_code
        + "\n\n"
        "def _elite_seed_probe(instance):\n"
        "    return instance.customer_count\n"
    )
    scheduler_code = scheduler_code.replace(
        "    _nearest_neighbor,\n",
        "    _nearest_neighbor,\n"
        "    _elite_seed_probe,\n",
        1,
    ).replace(
        "        reserve = max(0.05, self.time_limit * EXIT_RESERVE_FRACTION)\n",
        "        reserve = max(0.05, self.time_limit * EXIT_RESERVE_FRACTION)\n"
        "        _elite_seed_probe(instance)\n",
        1,
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/construction.py",
            action="modify",
            code_content=construction_code,
            additional_changes=(
                SimpleNamespace(
                    file_path="policies/baseline_modules/scheduler.py",
                    action="modify",
                    code_content=scheduler_code,
                ),
            ),
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert c9e.passed


def test_contract_gate_allows_same_patch_recombination_relative_import(
    tmp_path: Path,
) -> None:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    recombination_path = "policies/baseline_modules/recombination.py"
    gate, codes = _gate_with_cvrp_champion(tmp_path, (scheduler_path,))
    recombination_code = (
        "class _ElitePool:\n"
        "    pass\n\n"
        "_MAX_CALLS = 1\n\n"
        "def _try_recombination(solution, instance, rng, elite_pool, max_calls):\n"
        "    return solution\n"
    )
    scheduler_code = codes[scheduler_path].replace(
        _SCHEDULER_LOCAL_SEARCH_IMPORT,
        _SCHEDULER_LOCAL_SEARCH_IMPORT +
        "from .recombination import _ElitePool, _try_recombination, _MAX_CALLS\n",
        1,
    ).replace(
        "        best = current.copy()\n",
        "        best = current.copy()\n"
        "        best = _try_recombination(\n"
        "            best, instance, rng, _ElitePool(), _MAX_CALLS\n"
        "        )\n",
        1,
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path=recombination_path,
            action="create",
            code_content=recombination_code,
            additional_changes=(
                SimpleNamespace(
                    file_path=scheduler_path,
                    action="modify",
                    code_content=scheduler_code,
                ),
            ),
        ),
        selected_surface="solver_design",
    )

    c8 = next(
        check
        for check in result.checks
        if check.name == "additional_changes[0].C8_import_whitelist"
    )
    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert c8.passed
    assert c9e.passed


def test_contract_gate_attributes_same_patch_missing_import_symbol_to_c9e(
    tmp_path: Path,
) -> None:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    recombination_path = "policies/baseline_modules/recombination.py"
    gate, codes = _gate_with_cvrp_champion(tmp_path, (scheduler_path,))
    scheduler_code = codes[scheduler_path].replace(
        _SCHEDULER_LOCAL_SEARCH_IMPORT,
        _SCHEDULER_LOCAL_SEARCH_IMPORT +
        "from .recombination import _missing_recombination\n",
        1,
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path=recombination_path,
            action="create",
            code_content="def _try_recombination(solution):\n    return solution\n",
            additional_changes=(
                SimpleNamespace(
                    file_path=scheduler_path,
                    action="modify",
                    code_content=scheduler_code,
                ),
            ),
        ),
        selected_surface="solver_design",
    )

    c8 = next(
        check
        for check in result.checks
        if check.name == "additional_changes[0].C8_import_whitelist"
    )
    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert c8.passed
    assert not c9e.passed
    assert "missing_import_symbols" in c9e.detail
    assert "_missing_recombination" in c9e.detail


def test_contract_gate_resolves_imports_against_branch_base_snapshot(
    tmp_path: Path,
) -> None:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    local_search_path = "policies/baseline_modules/local_search.py"
    gate, codes = _gate_with_cvrp_champion(tmp_path, (scheduler_path, local_search_path))
    branch = tmp_path / "branch"
    for rel_path in (scheduler_path, local_search_path):
        target = branch / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(codes[rel_path], encoding="utf-8")
    branch_local_search = (
        codes[local_search_path]
        + "\n\n"
        "def _double_bridge(solution, instance, rng):\n"
        "    return solution\n"
    )
    (branch / local_search_path).write_text(branch_local_search, encoding="utf-8")
    scheduler_code = codes[scheduler_path].replace(
        _SCHEDULER_LOCAL_SEARCH_IMPORT,
        (
            "from .local_search import _default_vns_operators, "
            "_two_opt_intra_polish, _vns, _double_bridge\n"
        ),
        1,
    ).replace(
        "        best = current.copy()\n",
        "        best = current.copy()\n"
        "        best = _double_bridge(best, instance, rng)\n",
        1,
    )
    patch = PatchProposal(
        file_path=scheduler_path,
        action="modify",
        code_content=scheduler_code,
    )

    champion_result = gate.validate_patch(patch, selected_surface="solver_design")
    branch_result = gate.validate_patch(
        patch,
        selected_surface="solver_design",
        base_snapshot_path=str(branch),
    )

    champion_c9e = next(
        check
        for check in champion_result.checks
        if check.name == "C9e_solver_design_integration"
    )
    branch_c9e = next(
        check
        for check in branch_result.checks
        if check.name == "C9e_solver_design_integration"
    )
    assert not champion_c9e.passed
    assert "_double_bridge" in champion_c9e.detail
    assert branch_c9e.passed


def test_contract_gate_allows_branch_owned_relative_import_from_base_snapshot(
    tmp_path: Path,
) -> None:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    helper_path = "policies/baseline_modules/route_shape_polish.py"
    gate, codes = _gate_with_cvrp_champion(tmp_path, (scheduler_path,))
    branch = tmp_path / "branch"
    scheduler_target = branch / scheduler_path
    helper_target = branch / helper_path
    scheduler_target.parent.mkdir(parents=True, exist_ok=True)
    scheduler_target.write_text(codes[scheduler_path], encoding="utf-8")
    helper_target.write_text(
        "def _route_shape_polish(solution, instance, rng):\n"
        "    return solution\n",
        encoding="utf-8",
    )
    scheduler_code = codes[scheduler_path].replace(
        _SCHEDULER_LOCAL_SEARCH_IMPORT,
        _SCHEDULER_LOCAL_SEARCH_IMPORT +
        "from .route_shape_polish import _route_shape_polish\n",
        1,
    ).replace(
        "        best = current.copy()\n",
        "        best = current.copy()\n"
        "        best = _route_shape_polish(best, instance, rng)\n",
        1,
    )
    patch = PatchProposal(
        file_path=scheduler_path,
        action="modify",
        code_content=scheduler_code,
    )

    champion_result = gate.validate_patch(patch, selected_surface="solver_design")
    branch_result = gate.validate_patch(
        patch,
        selected_surface="solver_design",
        base_snapshot_path=str(branch),
    )

    champion_c8 = next(
        check
        for check in champion_result.checks
        if check.name == "C8_import_whitelist"
    )
    branch_c8 = next(
        check for check in branch_result.checks if check.name == "C8_import_whitelist"
    )
    assert not champion_c8.passed
    assert "route_shape_polish" in champion_c8.detail
    assert branch_c8.passed


def test_contract_gate_allows_branch_current_source_override_relative_import(
    tmp_path: Path,
) -> None:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    helper_path = "policies/baseline_modules/route_sequence_dp.py"
    gate, codes = _gate_with_cvrp_champion(tmp_path, (scheduler_path,))
    helper_source = (
        "def _route_sequence_dp(solution, instance, rng):\n"
        "    return solution\n"
    )
    scheduler_code = codes[scheduler_path].replace(
        _SCHEDULER_LOCAL_SEARCH_IMPORT,
        _SCHEDULER_LOCAL_SEARCH_IMPORT +
        "from .route_sequence_dp import _route_sequence_dp\n",
        1,
    ).replace(
        "        best = current.copy()\n",
        "        best = current.copy()\n"
        "        best = _route_sequence_dp(best, instance, rng)\n",
        1,
    )
    patch = PatchProposal(
        file_path=scheduler_path,
        action="modify",
        code_content=scheduler_code,
    )

    champion_result = gate.validate_patch(patch, selected_surface="solver_design")
    branch_result = gate.validate_patch(
        patch,
        selected_surface="solver_design",
        base_file_overrides={helper_path: helper_source},
    )

    champion_c8 = next(
        check
        for check in champion_result.checks
        if check.name == "C8_import_whitelist"
    )
    branch_c8 = next(
        check for check in branch_result.checks if check.name == "C8_import_whitelist"
    )
    assert not champion_c8.passed
    assert "route_sequence_dp" in champion_c8.detail
    assert branch_c8.passed


def test_contract_gate_constructor_source_overrides_support_preview_context(
    tmp_path: Path,
) -> None:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    helper_path = "policies/baseline_modules/route_sequence_dp.py"
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    scheduler_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py"
    ).read_text(encoding="utf-8")
    scheduler_target = champion / scheduler_path
    scheduler_target.parent.mkdir(parents=True, exist_ok=True)
    scheduler_target.write_text(scheduler_code, encoding="utf-8")
    helper_source = (
        "def _route_sequence_dp(solution, instance, rng):\n"
        "    return solution\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
        source_overrides={helper_path: helper_source},
    )
    patch = PatchProposal(
        file_path=scheduler_path,
        action="modify",
        code_content=scheduler_code.replace(
            _SCHEDULER_LOCAL_SEARCH_IMPORT,
            _SCHEDULER_LOCAL_SEARCH_IMPORT +
            "from .route_sequence_dp import _route_sequence_dp\n",
            1,
        ).replace(
            "        best = current.copy()\n",
            "        best = current.copy()\n"
            "        best = _route_sequence_dp(best, instance, rng)\n",
            1,
        ),
    )

    result = gate.validate_patch(patch, selected_surface="solver_design")

    c8 = next(check for check in result.checks if check.name == "C8_import_whitelist")
    assert c8.passed
