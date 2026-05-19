"""Focused tests split from test_research_surfaces_solver_design_integration.py."""

from .research_surfaces_solver_design_support import *  # noqa: F401,F403

def test_contract_gate_rejects_baseline_algorithm_integration_new_runtime_api(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    construction_target = champion / "policies" / "baseline_modules" / "construction.py"
    baseline_target = champion / "policies" / "baseline_algorithm.py"
    construction_target.parent.mkdir(parents=True)
    baseline_target.parent.mkdir(parents=True, exist_ok=True)
    construction_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "construction.py"
    ).read_text(encoding="utf-8")
    baseline_code = (
        _CVRP_ROOT / "policies" / "baseline_algorithm.py"
    ).read_text(encoding="utf-8")
    construction_target.write_text(construction_code, encoding="utf-8")
    baseline_target.write_text(baseline_code, encoding="utf-8")
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
                    file_path="policies/baseline_algorithm.py",
                    action="modify",
                    code_content=(
                        "from .baseline_modules.scheduler import _ALNSVNSSolver\n\n"
                        "def solve(instance, rng, time_limit_sec, context):\n"
                        "    solver = _ALNSVNSSolver()\n"
                        "    return solver.solve_with_context(\n"
                        "        instance, rng, time_limit_sec, context\n"
                        "    )\n"
                    ),
                ),
            ),
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "solve_with_context" in c9e.detail


def test_contract_gate_rejects_baseline_algorithm_integration_positional_solver_constructor(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    construction_target = champion / "policies" / "baseline_modules" / "construction.py"
    baseline_target = champion / "policies" / "baseline_algorithm.py"
    construction_target.parent.mkdir(parents=True)
    baseline_target.parent.mkdir(parents=True, exist_ok=True)
    construction_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "construction.py"
    ).read_text(encoding="utf-8")
    baseline_code = (
        _CVRP_ROOT / "policies" / "baseline_algorithm.py"
    ).read_text(encoding="utf-8")
    construction_target.write_text(construction_code, encoding="utf-8")
    baseline_target.write_text(baseline_code, encoding="utf-8")
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
                    file_path="policies/baseline_algorithm.py",
                    action="modify",
                    code_content=(
                        "from .baseline_modules.scheduler import _ALNSVNSSolver\n\n"
                        "def solve(instance, rng, time_limit_sec, context):\n"
                        "    solver = _ALNSVNSSolver(instance, rng, time_limit_sec, context)\n"
                        "    return solver.solve(instance, rng)\n"
                    ),
                ),
            ),
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "explicit stable keyword arguments" in c9e.detail


def test_contract_gate_rejects_baseline_algorithm_integration_extra_solve_kwargs(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    construction_target = champion / "policies" / "baseline_modules" / "construction.py"
    baseline_target = champion / "policies" / "baseline_algorithm.py"
    construction_target.parent.mkdir(parents=True)
    baseline_target.parent.mkdir(parents=True, exist_ok=True)
    construction_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "construction.py"
    ).read_text(encoding="utf-8")
    baseline_code = (
        _CVRP_ROOT / "policies" / "baseline_algorithm.py"
    ).read_text(encoding="utf-8")
    construction_target.write_text(construction_code, encoding="utf-8")
    baseline_target.write_text(baseline_code, encoding="utf-8")
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
                    file_path="policies/baseline_algorithm.py",
                    action="modify",
                    code_content=baseline_code.replace(
                        "solution = solver.solve(instance, rng)",
                        "solution = solver.solve(instance, rng, initial_solution=None)",
                    ),
                ),
            ),
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "solver.solve(instance, rng)" in c9e.detail
    assert "initial_solution" in c9e.detail


def test_contract_gate_rejects_scheduler_integration_constructor_api_change(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    acceptance_target = champion / "policies" / "baseline_modules" / "acceptance.py"
    scheduler_target = champion / "policies" / "baseline_modules" / "scheduler.py"
    acceptance_target.parent.mkdir(parents=True)
    acceptance_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "acceptance.py"
    ).read_text(encoding="utf-8")
    scheduler_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py"
    ).read_text(encoding="utf-8")
    acceptance_target.write_text(acceptance_code, encoding="utf-8")
    scheduler_target.write_text(scheduler_code, encoding="utf-8")
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/acceptance.py",
            action="modify",
            code_content=acceptance_code,
            additional_changes=(
                SimpleNamespace(
                    file_path="policies/baseline_modules/scheduler.py",
                    action="modify",
                    code_content=(
                        "class _ALNSVNSSolver:\n"
                        "    def __init__(self, time_limit_sec=30.0, context=None):\n"
                        "        self.time_limit_sec = time_limit_sec\n"
                        "        self.context = context\n\n"
                        "    def solve(self, instance, rng):\n"
                        "        return instance\n"
                    ),
                ),
            ),
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "constructor-compatible with baseline_algorithm.py" in c9e.detail
    assert "missing_keywords" in c9e.detail


def test_contract_gate_rejects_solver_design_missing_sibling_import_symbol(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    acceptance_target = champion / "policies" / "baseline_modules" / "acceptance.py"
    construction_target = champion / "policies" / "baseline_modules" / "construction.py"
    scheduler_target = champion / "policies" / "baseline_modules" / "scheduler.py"
    acceptance_target.parent.mkdir(parents=True)
    acceptance_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "acceptance.py"
    ).read_text(encoding="utf-8")
    construction_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "construction.py"
    ).read_text(encoding="utf-8")
    scheduler_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py"
    ).read_text(encoding="utf-8")
    acceptance_target.write_text(acceptance_code, encoding="utf-8")
    construction_target.write_text(construction_code, encoding="utf-8")
    scheduler_target.write_text(scheduler_code, encoding="utf-8")
    bad_scheduler = (
        "from .construction import _clarke_wright\n\n"
        "class _ALNSVNSSolver:\n"
        "    def __init__(\n"
        "        self,\n"
        "        *,\n"
        "        time_limit,\n"
        "        destroy_ratio,\n"
        "        segment_length,\n"
        "        reaction_factor,\n"
        "        vns_max_no_improve,\n"
        "        use_vns,\n"
        "        cw_threshold,\n"
        "        vns_threshold,\n"
        "        alns_threshold,\n"
        "        max_destroy_customers,\n"
        "        max_routes,\n"
        "        context,\n"
        "    ):\n"
        "        self.context = context\n\n"
        "    def solve(self, instance, rng):\n"
        "        return _clarke_wright(instance)\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/acceptance.py",
            action="modify",
            code_content=acceptance_code,
            additional_changes=(
                SimpleNamespace(
                    file_path="policies/baseline_modules/scheduler.py",
                    action="modify",
                    code_content=bad_scheduler,
                ),
            ),
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "missing_import_symbols" in c9e.detail
    assert "_clarke_wright" in c9e.detail
    assert "policies/baseline_modules/construction.py" in c9e.detail
    assert "available_exports" in c9e.detail
    assert "_clarke_wright_savings" in c9e.detail
