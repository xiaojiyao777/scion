"""Focused tests split from test_research_surfaces_solver_design_integration.py."""

from .research_surfaces_solver_design_support import *  # noqa: F401,F403

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
        "from .local_search import _default_vns_operators, _vns\n",
        "from .local_search import _default_vns_operators, _vns\n"
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
        "from .local_search import _default_vns_operators, _vns\n",
        "from .local_search import _default_vns_operators, _vns\n"
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
