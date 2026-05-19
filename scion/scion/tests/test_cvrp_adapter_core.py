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
    assert "Runtime evidence for problem-level hypotheses:" in rendered
    assert "`instance.customer_ids`" in rendered
    assert "`instance.allowed_routes`" in rendered
    assert "`instance.bks_routes`" in rendered
    assert "`instance.route_distance(route)`" in rendered
    assert "`CvrpSolution(routes=...)`" in rendered
    assert "fleet_violation first, then total_distance" in rendered
    assert "Capacity overload" in rendered
    assert "policies/baseline_algorithm.py" in rendered
    assert "policies/baseline_modules/*.py" in rendered
    assert "Legacy operator/component-policy" in rendered


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


def test_cvrp_solver_design_surface_interface_renders_safe_instance_api(
    cvrp_adapter: ProblemAdapter,
) -> None:
    rendered = cvrp_adapter.render_research_surface_interface("solver_design")

    assert "`instance.customer_ids`" in rendered
    assert "`instance.customer_count`" in rendered
    assert "`instance.demands[customer_id]`" in rendered
    assert "`instance.capacity`" in rendered
    assert "`instance.allowed_routes`" in rendered
    assert "`instance.bks_routes`" in rendered
    assert "`instance.distance(i, j)`" in rendered
    assert "fleet_violation = max(0, len(routes) - route_limit)" in rendered
    assert "context.record_phase(name, elapsed_ms)" in rendered
    assert "context.record_iteration(phase='search', count=1)" in rendered
    assert "Never use `instance.customers`" in rendered
    assert "context.record_move" in rendered
    assert "policies/baseline_modules/*.py" in rendered


@pytest.mark.parametrize(
    "surface_name",
    [
        "construction_policy",
        "search_policy",
        "baseline_policy",
        "neighborhood_portfolio",
        "algorithm_blueprint",
        "alns_vns_policy",
        "destroy_repair_policy",
        "route_pair_candidate_policy",
        "acceptance_restart_policy",
    ],
)
def test_cvrp_legacy_policy_surface_interfaces_are_removed(
    cvrp_adapter: ProblemAdapter,
    surface_name: str,
) -> None:
    rendered = cvrp_adapter.render_research_surface_interface(surface_name)

    assert "not an active CVRP research surface" in rendered
    assert "Use solver_design" in rendered
    assert "policies/baseline_algorithm.py" in rendered
