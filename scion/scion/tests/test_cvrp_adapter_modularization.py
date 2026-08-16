from __future__ import annotations

from scion.tests.cvrp_adapter_test_support import *

from scion.problems.cvrp import solution_checks, surface_rendering


def test_cvrp_adapter_rendering_facade_delegates_to_surface_module(
    cvrp_adapter: ProblemAdapter,
) -> None:
    assert cvrp_adapter.render_problem_summary() == surface_rendering.render_problem_summary()
    assert cvrp_adapter.render_problem_object() == surface_rendering.render_problem_object()
    assert cvrp_adapter.render_solver_mechanics() == surface_rendering.render_solver_mechanics()
    assert (
        cvrp_adapter.render_operator_interface()
        == surface_rendering.render_operator_interface()
    )
    for surface_name in ("solver_design", "main_search_strategy", "unknown"):
        assert cvrp_adapter.render_research_surface_interface(
            surface_name
        ) == surface_rendering.render_research_surface_interface(surface_name)


def test_cvrp_solver_mechanics_prompts_smallest_causal_edit() -> None:
    rendered = surface_rendering.render_solver_mechanics()

    assert "smallest complete causal implementation" in rendered
    assert "preserve unrelated code" in rendered
    assert (
        "multiple owner files only when the same mechanism requires them" in rendered
    )


def test_cvrp_adapter_solution_checks_facade_delegates_to_solution_module(
    cvrp_adapter: ProblemAdapter,
) -> None:
    inst = cvrp_adapter.load_instance(str(TINY_5))
    raw = _raw([[0, 1, 2, 0], [0, 3, 4, 0]])

    facade_artifact = cvrp_adapter.deserialize_solver_output(raw, inst)
    direct_artifact = solution_checks.deserialize_solver_output(raw, inst)

    assert facade_artifact.normalized_solution == direct_artifact.normalized_solution
    assert cvrp_adapter.check_solution_consistency(
        facade_artifact,
        inst,
    ) == solution_checks.check_solution_consistency(direct_artifact, inst)
    assert cvrp_adapter.check_feasibility(
        facade_artifact,
        inst,
    ) == solution_checks.check_feasibility(direct_artifact, inst)
    assert cvrp_adapter.recompute_objective(
        facade_artifact,
        inst,
    ) == solution_checks.recompute_objective(direct_artifact, inst)


def test_solution_checks_own_private_solution_helpers() -> None:
    assert solution_checks._normalize_route([0, 1, 2, 0], 0) == (1, 2)
    assert solution_checks._extract_reported_objective(
        {"cost": 7.5, "fleet_violation": 1, "total_distance": 8.0}
    ) == {"fleet_violation": 1, "total_distance": 8.0}


def test_cvrp_adapter_does_not_expose_dead_preview_or_contract_providers(
    cvrp_adapter: ProblemAdapter,
) -> None:
    assert not hasattr(cvrp_adapter, "preview_research_surface_patch")
    assert not hasattr(cvrp_adapter, "contract_check_provider")
    assert not hasattr(cvrp_adapter, "active_subject_policy_provider")
    assert callable(getattr(cvrp_adapter, "solver_design_prompt_provider", None))
