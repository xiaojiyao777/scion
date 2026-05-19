"""Focused tests split from test_research_surfaces_solver_design_integration.py."""

from .research_surfaces_solver_design_support import *  # noqa: F401,F403

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
