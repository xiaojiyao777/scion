"""Focused tests split from test_research_surfaces_solver_design_integration.py."""

from .research_surfaces_solver_design_support import *  # noqa: F401,F403

def test_contract_gate_rejects_scheduler_additional_change_added_time_budget_loop(
    tmp_path: Path,
) -> None:
    construction_path = "policies/baseline_modules/construction.py"
    scheduler_path = "policies/baseline_modules/scheduler.py"
    gate, codes = _gate_with_cvrp_champion(
        tmp_path,
        (construction_path, scheduler_path),
    )
    scheduler_code = codes[scheduler_path].replace(
        "        while self._within_budget(start_ms, reserve):\n",
        "        while self.context.remaining_time() > reserve:\n"
        "            break\n\n"
        "        while self._within_budget(start_ms, reserve):\n",
        1,
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path=construction_path,
            action="modify",
            code_content=codes[construction_path],
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

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "minimal wiring" in c9e.detail
    assert "added_while_loops" in c9e.detail
    assert (
        "make policies/baseline_modules/scheduler.py the approved target"
        in c9e.detail
    )


def test_contract_gate_rejects_scheduler_additional_change_added_uncapped_loop(
    tmp_path: Path,
) -> None:
    construction_path = "policies/baseline_modules/construction.py"
    scheduler_path = "policies/baseline_modules/scheduler.py"
    gate, codes = _gate_with_cvrp_champion(
        tmp_path,
        (construction_path, scheduler_path),
    )
    scheduler_code = codes[scheduler_path].replace(
        "        while self._within_budget(start_ms, reserve):\n",
        "        while True:\n"
        "            candidate = current.copy()\n"
        "            if candidate.is_feasible():\n"
        "                break\n\n"
        "        while self._within_budget(start_ms, reserve):\n",
        1,
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path=construction_path,
            action="modify",
            code_content=codes[construction_path],
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

    c9c = next(
        check
        for check in result.checks
        if check.name == "additional_changes[0].C9c_complexity_bound"
    )
    assert not c9c.passed
    assert "uncapped while loop" in c9c.detail


def test_contract_gate_rejects_scheduler_additional_change_replaced_solve_loop(
    tmp_path: Path,
) -> None:
    construction_path = "policies/baseline_modules/construction.py"
    scheduler_path = "policies/baseline_modules/scheduler.py"
    gate, codes = _gate_with_cvrp_champion(
        tmp_path,
        (construction_path, scheduler_path),
    )
    scheduler_code = codes[scheduler_path].replace(
        "        while self._within_budget(start_ms, reserve):\n",
        "        while self.context.remaining_time() > reserve:\n",
        1,
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path=construction_path,
            action="modify",
            code_content=codes[construction_path],
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

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "changed_while_condition" in c9e.detail
    assert "_ALNSVNSSolver.solve" in c9e.detail


def test_contract_gate_allows_scheduler_additional_change_operator_registration(
    tmp_path: Path,
) -> None:
    destroy_path = "policies/baseline_modules/destroy_repair.py"
    scheduler_path = "policies/baseline_modules/scheduler.py"
    gate, codes = _gate_with_cvrp_champion(tmp_path, (destroy_path, scheduler_path))
    destroy_code = (
        codes[destroy_path]
        + "\n\n"
        "def _route_fragment_removal(candidate, q, rng):\n"
        "    return _random_removal(candidate, q, rng)\n"
    )
    scheduler_code = codes[scheduler_path].replace(
        "    _random_removal,\n",
        "    _random_removal,\n"
        "    _route_fragment_removal,\n",
        1,
    ).replace(
        '            ("route", _route_removal),\n',
        '            ("route", _route_removal),\n'
        '            ("fragment", _route_fragment_removal),\n',
        1,
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path=destroy_path,
            action="modify",
            code_content=destroy_code,
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

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert c9e.passed


def test_contract_gate_allows_scheduler_primary_to_change_solve_loop_condition(
    tmp_path: Path,
) -> None:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    gate, codes = _gate_with_cvrp_champion(tmp_path, (scheduler_path,))
    scheduler_code = codes[scheduler_path].replace(
        "        while self._within_budget(start_ms, reserve):\n",
        "        while self.context.remaining_time() > reserve:\n",
        1,
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path=scheduler_path,
            action="modify",
            code_content=scheduler_code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert c9e.passed
    assert "minimal wiring" not in c9e.detail


def test_contract_gate_rejects_scheduler_integration_without_runtime_class(
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
    detached_scheduler = (
        "def run(instance, rng):\n"
        "    return instance\n"
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
                    code_content=detached_scheduler,
                ),
            ),
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "class-based solver runtime entrypoint" in c9e.detail
    assert "primary_target=policies/baseline_modules/construction.py" in c9e.detail
