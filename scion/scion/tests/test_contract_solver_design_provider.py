from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scion.contract.checks import solver_design_integration as generic_c9e
from scion.contract.checks.problem_integration import resolve_contract_check_provider
from scion.core.models import PatchProposal
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def test_solver_design_integration_dispatches_to_problem_owned_provider() -> None:
    calls: list[object] = []

    class Provider:
        def check_solver_design_integration(self, request):
            calls.append(request)
            return SimpleNamespace(passed=False, detail="provider blocked patch")

    class Spec:
        research_surfaces = (
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                targets=SimpleNamespace(files=("policies/algorithm.py",)),
            ),
        )

        def contract_check_provider(self):
            return Provider()

    patch = PatchProposal(
        file_path="policies/algorithm.py",
        action="modify",
        code_content="def solve(instance, rng, time_limit_sec, context):\n    return None\n",
    )

    result = generic_c9e.check_solver_design_integration(
        patch,
        problem_spec=Spec(),
        selected_surface="solver_design",
        champion_file_content=lambda file_rel: None,
    )

    assert not result.passed
    assert result.detail == "provider blocked patch"
    assert len(calls) == 1
    assert calls[0].patch is patch


def test_generic_solver_design_integration_facade_has_no_cvrp_solver_terms() -> None:
    source = Path(generic_c9e.__file__).read_text(encoding="utf-8")

    forbidden_terms = (
        "_ALNSVNSSolver",
        "baseline_modules",
        "baseline_algorithm.py",
        "_Solution",
        "from_routes",
        "max_routes",
        "customer",
        "route",
        "CVRP",
    )
    for term in forbidden_terms:
        assert term not in source


def test_cvrp_adapter_exposes_problem_owned_contract_provider(tmp_path: Path) -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    problem_spec = legacy_problem_spec_from_v1(spec_v1)
    provider = resolve_contract_check_provider(problem_spec)

    assert provider is not None
    assert provider.__class__.__module__.startswith(
        "scion.problems.cvrp.contract_checks"
    )

    champion = tmp_path / "champion"
    rel_path = "policies/baseline_modules/local_search.py"
    target = champion / rel_path
    target.parent.mkdir(parents=True)
    base_code = (_CVRP_ROOT / rel_path).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    patch = PatchProposal(
        file_path=rel_path,
        action="modify",
        code_content=(
            base_code
            + "\n\n"
            + "def _unused_cvrp_contract_probe(solution, context):\n"
            + "    return solution\n"
        ),
    )

    result = generic_c9e.check_solver_design_integration(
        patch,
        problem_spec=problem_spec,
        selected_surface="solver_design",
        champion_file_content=lambda file_rel: (
            (champion / file_rel).read_text(encoding="utf-8")
            if (champion / file_rel).is_file()
            else None
        ),
    )

    assert not result.passed
    assert "new solver_design helper functions are not integrated" in result.detail
    assert "_unused_cvrp_contract_probe" in result.detail


def test_cvrp_provider_entrypoint_delegates_to_focused_modules() -> None:
    from scion.problems.cvrp.contract_checks import solver_design_integration

    source = Path(solver_design_integration.__file__).read_text(encoding="utf-8")

    delegated_helpers = (
        "_solver_design_import_export_error",
        "_additional_wiring_edit_error",
        "_state_model_bridge_api_error",
        "ReachabilityState",
    )
    for helper in delegated_helpers:
        assert f"import {helper}" in source or helper in source
    assert "def _solver_design_import_export_error" not in source
    assert "def _state_model_bridge_api_error" not in source
    assert "def _module_call_references" not in source
