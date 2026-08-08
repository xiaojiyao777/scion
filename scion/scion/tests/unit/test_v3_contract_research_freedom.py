"""V3 Contract keeps boundaries without steering algorithm internals."""
from __future__ import annotations

from scion.contract.gate import ContractGate
from scion.core.models import PatchProposal
from scion.problem.bridge import legacy_problem_spec_from_v1, load_problem_spec_v1_from_yaml
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def _gate() -> ContractGate:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    return ContractGate(legacy_problem_spec_from_v1(spec))


def test_solver_support_module_may_change_internal_architecture() -> None:
    result = _gate().validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/scheduler.py",
            action="modify",
            code_content=(
                "class AlternativeSearch:\n"
                "    def run(self, state, context):\n"
                "        while context.remaining_time() > 0:\n"
                "            break\n"
                "        return state\n"
            ),
        ),
        selected_surface="solver_design",
    )

    assert result.passed
    assert all(check.name != "C9e_solver_design_integration" for check in result.checks)


def test_declared_numpy_runtime_dependency_is_available_to_candidate() -> None:
    result = _gate().validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/local_search.py",
            action="modify",
            code_content=(
                "import numpy as np\n\n"
                "def rank_moves(values):\n"
                "    return np.argsort(values)\n"
            ),
        ),
        selected_surface="solver_design",
    )

    c8 = next(check for check in result.checks if check.name == "C8_import_whitelist")
    assert c8.passed
    assert result.passed


def test_public_entrypoint_signature_remains_a_contract_boundary() -> None:
    result = _gate().validate_patch(
        PatchProposal(
            file_path="policies/baseline_algorithm.py",
            action="modify",
            code_content="def run(instance, rng):\n    return instance\n",
        ),
        selected_surface="solver_design",
    )

    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "solve" in c7.detail


def test_candidate_cannot_call_control_baseline() -> None:
    result = _gate().validate_patch(
        PatchProposal(
            file_path="policies/baseline_algorithm.py",
            action="modify",
            code_content=(
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return context.baseline(time_limit_sec=time_limit_sec)\n"
            ),
        ),
        selected_surface="solver_design",
    )

    c9 = next(check for check in result.checks if check.name == "C9_sensitive_api")
    assert not c9.passed
    assert "context.baseline" in c9.detail
