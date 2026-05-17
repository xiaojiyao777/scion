from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scion.contract.gate import ContractGate
from scion.core.models import PatchProposal
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def test_contract_gate_allows_inherited_solver_module_identity_message(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "scheduler.py"
    target.parent.mkdir(parents=True)
    code = (_CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py").read_text(
        encoding="utf-8"
    )
    target.write_text(code, encoding="utf-8")
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

    c9d = next(
        check for check in result.checks if check.name == "C9d_surface_instance_identity"
    )
    assert c9d.passed


def test_contract_gate_uses_dynamic_champion_snapshot_provider(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "scheduler.py"
    target.parent.mkdir(parents=True)
    code = (_CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py").read_text(
        encoding="utf-8"
    )
    target.write_text(code, encoding="utf-8")
    current_champion = {"path": str(champion)}
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_provider=lambda: current_champion["path"],
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/scheduler.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9d = next(
        check for check in result.checks if check.name == "C9d_surface_instance_identity"
    )
    assert c9d.passed


def test_contract_gate_rejects_new_solver_module_identity_branch(
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
        "    def solve(self, instance, rng):\n",
        "    def solve(self, instance, rng):\n"
        "        if instance.name == 'case-a':\n"
        "            return self._initial_solution(instance, 0.05)\n",
        1,
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

    c9d = next(
        check for check in result.checks if check.name == "C9d_surface_instance_identity"
    )
    assert not c9d.passed
    assert "if instance.name == 'case-a'" in c9d.detail


def test_contract_gate_rejects_inert_solver_design_helper(
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
    code = (
        base_code
        + "\n\n"
        + "def _adaptive_vns(solution, operators, max_no_improve, context, reserve):\n"
        + "    return False\n"
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
    assert not c9e.passed
    assert "_adaptive_vns" in c9e.detail
    assert "additional_changes" in c9e.detail
    assert "_ALNSVNSSolver.solve" in c9e.detail


def test_contract_gate_rejects_inert_solver_design_class_method(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "acceptance.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "acceptance.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = (
        base_code
        + "\n\n"
        + "    def notify_segment_end(self):\n"
        + "        self.temperature = self.start_temp\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/acceptance.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "notify_segment_end" in c9e.detail
    assert "inert_helpers" in c9e.detail


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


def test_cvrp_preview_rejects_bad_scheduler_entrypoint_import_in_integration_edit() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    adapter = CvrpAdapter(spec)
    patch = PatchProposal(
        file_path="policies/baseline_modules/construction.py",
        action="modify",
        code_content="def unchanged_construction_helper():\n    return None\n",
        additional_changes=(
            SimpleNamespace(
                file_path="policies/baseline_algorithm.py",
                action="modify",
                code_content=(
                    "from .baseline_modules.scheduler import solve as scheduler_solve\n\n"
                    "def solve(instance, rng, time_limit_sec, context):\n"
                    "    return scheduler_solve(instance, rng)\n"
                ),
            ),
        ),
    )

    payload = adapter.preview_research_surface_patch(patch=patch)
    checks = {check["name"]: check["passed"] for check in payload["checks"]}

    assert payload["passed"] is False
    assert checks["baseline_algorithm_scheduler_entrypoint_api"] is False
    assert "_ALNSVNSSolver" in str(payload["issues"])


def test_cvrp_preview_rejects_context_nearest_neighbor_with_arguments() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    adapter = CvrpAdapter(spec)
    patch = PatchProposal(
        file_path="policies/baseline_modules/destroy_repair.py",
        action="modify",
        code_content=(
            "def bad_seed(context, rng):\n"
            "    return context.nearest_neighbor(rng)\n"
        ),
    )

    payload = adapter.preview_research_surface_patch(patch=patch)
    checks = {check["name"]: check["passed"] for check in payload["checks"]}

    assert payload["passed"] is False
    assert checks["solver_design_context_nearest_neighbor_no_args"] is False
    assert "takes no arguments" in str(payload["issues"])


def test_contract_gate_rejects_invented_solution_bridge_api(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "destroy_repair.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "destroy_repair.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = (
        "from .state import _Solution\n\n"
        "def _bad_repair(context):\n"
        "    return _Solution.from_public(context.nearest_neighbor())\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/destroy_repair.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "inventing _Solution bridge APIs" in c9e.detail
    assert "from_public" in c9e.detail
    assert "routes_as_tuples" in c9e.detail


def test_contract_gate_rejects_state_bridge_method_definition(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "state.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "state.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = base_code.replace(
        "    def routes_as_tuples(self):\n",
        "    def from_cvrp_solution(self, solution):\n"
        "        return self\n\n"
        "    def routes_as_tuples(self):\n",
        1,
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/state.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "forbidden_definitions" in c9e.detail
    assert "from_cvrp_solution" in c9e.detail


def test_contract_gate_rejects_invented_solution_to_public_bridge(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "local_search.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        (_CVRP_ROOT / "policies" / "baseline_modules" / "local_search.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    code = "def _bad_move(solution):\n    return solution.to_public()\n"
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
    assert not c9e.passed
    assert "inventing _Solution bridge APIs" in c9e.detail
    assert "to_public" in c9e.detail


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
