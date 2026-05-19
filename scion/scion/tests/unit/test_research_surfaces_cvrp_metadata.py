from __future__ import annotations

from pathlib import Path

from scion.contract.gate import ContractGate
from scion.core.models import HypothesisProposal, PatchProposal
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)


CVRP_SPEC = Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"


def test_cvrp_problem_v1_exposes_only_solver_design_surface() -> None:
    spec = load_problem_spec_v1_from_yaml(CVRP_SPEC)
    legacy = legacy_problem_spec_from_v1(spec)

    assert legacy.operator_categories == ["solver_design"]
    assert legacy.search_space.editable == [
        "policies/baseline_algorithm.py",
        "policies/baseline_modules/*.py",
    ]
    assert [surface.name for surface in spec.research_surfaces or []] == [
        "solver_design"
    ]


def test_cvrp_solver_design_surface_targets_active_algorithm_package() -> None:
    spec = load_problem_spec_v1_from_yaml(CVRP_SPEC)
    surface = next(surface for surface in spec.research_surfaces or [])

    assert surface.name == "solver_design"
    assert surface.kind == "solver_design"
    assert surface.targets is not None
    assert surface.targets.files == [
        "policies/baseline_algorithm.py",
        "policies/baseline_modules/*.py",
    ]
    assert surface.interface is not None
    assert surface.interface.required_functions == ["solve"]
    assert surface.interface.function_signatures == {
        "solve": ["instance", "rng", "time_limit_sec", "context"]
    }
    assert surface.evidence is not None
    assert "solver_algorithm_loaded" in surface.evidence.required_runtime_fields
    assert "solver_algorithm_active" in surface.evidence.required_runtime_fields
    assert "solver_algorithm_errors" in surface.evidence.required_runtime_fields
    assert "solver_algorithm_search_iterations" in (
        surface.evidence.required_runtime_fields
    )
    assert surface.bounds is not None
    assert "construction" in surface.bounds.allowed_components
    assert "destroy_repair" in surface.bounds.allowed_components
    assert "vns_local_search" in surface.bounds.allowed_components


def test_cvrp_contract_accepts_active_baseline_algorithm_patch() -> None:
    spec = load_problem_spec_v1_from_yaml(CVRP_SPEC)
    gate = ContractGate(legacy_problem_spec_from_v1(spec))
    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_algorithm.py",
            action="modify",
            code_content=(
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    solution = context.nearest_neighbor()\n"
                "    context.record_iteration('contract_probe', 1)\n"
                "    context.record_move('contract_probe', attempted=1, accepted=0)\n"
                "    return solution\n"
            ),
        ),
        hypothesis=HypothesisProposal(
            hypothesis_text="Probe active solver design contract.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_algorithm.py",
            predicted_direction="preserve",
            target_objectives=["total_distance"],
            protected_objectives=["fleet_violation"],
            novelty_signature={
                "algorithm_family": "contract_probe",
                "construction_strategy": "nearest_neighbor",
                "improvement_strategy": "bounded_probe",
                "acceptance_strategy": "none",
                "runtime_budget_strategy": "constant",
            },
        ),
    )

    assert result.passed, [check.detail for check in result.checks if not check.passed]


def test_cvrp_contract_rejects_deleted_legacy_surface_target() -> None:
    spec = load_problem_spec_v1_from_yaml(CVRP_SPEC)
    gate = ContractGate(legacy_problem_spec_from_v1(spec))
    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content="def baseline_time_fraction(instance, time_limit_sec):\n    return 0.5\n",
        ),
        hypothesis=HypothesisProposal(
            hypothesis_text="Try a deleted legacy surface.",
            change_locus="search_policy",
            action="modify",
            target_file="policies/search_policy.py",
            predicted_direction="preserve",
            target_objectives=["total_distance"],
            protected_objectives=["fleet_violation"],
        ),
    )

    assert result.passed is False
    assert any("research surface" in check.detail for check in result.checks)
