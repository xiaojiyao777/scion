from __future__ import annotations

from scion.tests.cvrp_adapter_test_support import *
from scion.core.models import HypothesisProposal, MechanismChange
from scion.core.proposal_pipeline.problem_quality import validate_problem_patch_quality


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


def test_cvrp_adapter_patch_quality_blocks_construction_seed_activation_only(
    cvrp_adapter: ProblemAdapter,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a construction seed selection portfolio that chooses a "
            "Clarke-Wright savings seed before ALNS."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
        novelty_signature={"mechanism_family": "construction_seed_portfolio"},
        mechanism_changes=(
            MechanismChange(id="savings_seed_selection_probe", change_type="add"),
        ),
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/construction.py",
        action="modify",
        code_content=(
            "def _savings_seed_selection_probe(instance, rng, context=None):\n"
            "    if context:\n"
            "        context.record_iteration('savings_seed_selection_probe', 1)\n"
            "        context.record_phase('savings_seed_selection_probe', 1)\n"
            "    return _construct_initial_solution(instance, rng)\n"
        ),
    )

    check = validate_problem_patch_quality(
        SimpleNamespace(adapter=cvrp_adapter),
        SimpleNamespace(branch_id="branch-1"),
        hypothesis,
        patch,
    )

    assert check.allowed is False
    assert "cvrp_construction_seed_direct_effect_missing" in check.detail
    assert "agent_quality_blocked" in check.detail
    assert check.structured_rejection["gate_name"] == "cvrp_solver_design_static_quality"
    assert (
        check.structured_rejection["failure_code"]
        == "agent_quality_blocked:cvrp_construction_seed_direct_effect_missing"
    )
    assert check.structured_rejection["agent_block_reason"] == "agent_quality_blocked"
    assert "construction_seed_direct_effect_record_move" in (
        check.structured_rejection["missing_code_elements"]
    )


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
