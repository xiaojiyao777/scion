"""Focused tests split from test_research_surfaces_solver_design_integration.py."""

from .research_surfaces_solver_design_support import *  # noqa: F401,F403

def test_contract_gate_allows_integrated_solver_design_helper(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "local_search.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "local_search.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = base_code.replace(
        "def _vns(solution, operators, max_no_improve, context, reserve):\n",
        "def _vns(solution, operators, max_no_improve, context, reserve):\n"
        "    _adaptive_vns(solution, operators, max_no_improve, context, reserve)\n",
        1,
    )
    code += (
        "\n\n"
        "def _adaptive_vns(solution, operators, max_no_improve, context, reserve):\n"
        "    return False\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/local_search.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert c9e.passed


def test_contract_gate_allows_solver_design_helper_referenced_as_vns_operator(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "local_search.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "local_search.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = base_code.replace(
        "        _two_opt_star,\n",
        "        _two_opt_star,\n"
        "        _or_opt_intra_1,\n",
        1,
    )
    code += (
        "\n\n"
        "def _or_opt_intra_1(solution, context, reserve):\n"
        "    return False\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/local_search.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert c9e.passed


def test_contract_gate_allows_solver_design_helper_called_from_solver_class(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "scheduler.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = base_code.replace(
        "    def _initial_solution(self, instance, reserve):\n",
        "    def _initial_solution(self, instance, reserve):\n"
        "        _construction_probe(instance)\n",
        1,
    )
    code += (
        "\n\n"
        "def _construction_probe(instance):\n"
        "    return instance.customer_count\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/scheduler.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert c9e.passed


def test_contract_gate_allows_solver_design_helper_called_from_runtime_class_alias(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "scheduler.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = (
        "def _build_initial_pool(instance):\n"
        "    return [instance]\n\n"
        "class _PBIGSolver:\n"
        "    def solve(self, instance, rng):\n"
        "        return _build_initial_pool(instance)[0]\n\n"
        "_ALNSVNSSolver = _PBIGSolver\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/scheduler.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert c9e.passed


def test_contract_gate_rejects_solver_design_helper_only_called_from_detached_class(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "scheduler.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = (
        "def _detached_pool(instance):\n"
        "    return [instance]\n\n"
        "class _DetachedSolver:\n"
        "    def solve(self, instance, rng):\n"
        "        return _detached_pool(instance)[0]\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/scheduler.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "_detached_pool" in c9e.detail
