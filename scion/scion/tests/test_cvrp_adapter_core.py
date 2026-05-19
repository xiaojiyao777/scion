from __future__ import annotations

from scion.tests.cvrp_adapter_test_support import *

def test_cvrp_problem_spec_loads(cvrp_spec: ProblemSpecV1, cvrp_adapter: ProblemAdapter) -> None:
    assert cvrp_spec.id == "cvrp"
    assert [o.name for o in cvrp_spec.objectives] == ["fleet_violation", "total_distance"]
    assert "fleet_violation" in cvrp_adapter.render_problem_summary()
    assert "implicit depot" in cvrp_adapter.render_operator_interface()


def test_cvrp_adapter_renders_problem_object_for_solver_level_research(
    cvrp_adapter: ProblemAdapter,
) -> None:
    rendered = cvrp_adapter.render_problem_object()

    assert "Instance model:" in rendered
    assert "Solution model:" in rendered
    assert "Objective policy:" in rendered
    assert "Solver lifecycle:" in rendered
    assert "Move/design grammar:" in rendered
    assert "Runtime evidence for problem-level hypotheses:" in rendered
    assert "`instance.customer_ids`" in rendered
    assert "`instance.route_distance(route)`" in rendered
    assert "`CvrpSolution(routes=...)`" in rendered
    assert "fleet_violation first, then total_distance" in rendered
    assert "Component policies are implementation hooks" in rendered
    assert "Do not claim success from active flags" in rendered


def test_cvrp_instance_exposes_safe_policy_api_without_customers_alias() -> None:
    inst = CvrpInstance(
        name="api_smoke",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=3),
            CvrpNode(id=2, x=0.0, y=1.0, demand=4),
        ),
    )

    assert inst.customer_ids == (1, 2)
    assert inst.customer_count == len(inst.customer_ids) == 2
    assert inst.demands == {0: 0, 1: 3, 2: 4}
    assert inst.demands[1] == inst.demand(1)
    assert not hasattr(inst, "customers")
    with pytest.raises(AttributeError):
        getattr(inst, "customers")


@pytest.mark.parametrize(
    "surface_name",
    [
        "construction_policy",
        "search_policy",
        "baseline_policy",
        "neighborhood_portfolio",
        "algorithm_blueprint",
        "solver_design",
        "alns_vns_policy",
        "destroy_repair_policy",
        "route_pair_candidate_policy",
        "acceptance_restart_policy",
    ],
)
def test_cvrp_policy_surface_interfaces_render_safe_instance_api(
    cvrp_adapter: ProblemAdapter,
    surface_name: str,
) -> None:
    rendered = cvrp_adapter.render_research_surface_interface(surface_name)

    assert "`instance.customer_ids`" in rendered
    assert "`instance.customer_count`" in rendered
    assert "`instance.demands[customer_id]`" in rendered
    assert "`instance.capacity`" in rendered
    assert "`instance.distance(i, j)`" in rendered
    assert "Never use `instance.customers`" in rendered


def test_cvrp_destroy_repair_policy_interface_lists_disjoint_selector_enums(
    cvrp_adapter: ProblemAdapter,
) -> None:
    rendered = cvrp_adapter.render_research_surface_interface("destroy_repair_policy")

    assert (
        "destroy_selectors: non-empty sequence containing only 'worst_removal', "
        "'route_diverse_worst'"
    ) in rendered
    assert (
        "repair_selectors: non-empty sequence containing only 'regret_2', "
        "'cheapest'"
    ) in rendered
    assert (
        "subset_strategy: one of 'prefix_shifted_route_diverse', 'single_worst', "
        "'route_diverse'"
    ) in rendered
    assert (
        "Do not put subset strategies such as 'single_worst' or 'route_diverse' "
        "in destroy_selectors"
    ) in rendered
