from __future__ import annotations

from scion.core.models import Branch, BranchState, ChampionState
from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.problem.contracts import ProblemAdapter
from scion.problem.spec import ProblemSpecV1
from scion.proposal.context_manager import ContextManager
from scion.tests.cvrp_adapter_test_support import *

_LEGACY_SURFACES = {
    "route_local",
    "route_pair",
    "ruin_recreate",
    "search_policy",
    "construction_policy",
    "baseline_policy",
    "neighborhood_portfolio",
    "algorithm_blueprint",
    "main_search_strategy",
    "alns_vns_policy",
    "destroy_repair_policy",
    "route_pair_candidate_policy",
    "acceptance_restart_policy",
    "solver_algorithm",
}


def test_cvrp_adapter_declares_only_solver_design_active(
    cvrp_spec: ProblemSpecV1,
    cvrp_adapter: ProblemAdapter,
) -> None:
    declared_names = {surface.name for surface in cvrp_spec.research_surfaces or []}

    assert declared_names == {"solver_design"}
    assert cvrp_adapter.active_research_surface_names() == ("solver_design",)
    assert cvrp_adapter.legacy_research_surface_names() == ()
    assert [surface.name for surface in cvrp_adapter.active_research_surfaces()] == [
        "solver_design"
    ]
    for surface_name in _LEGACY_SURFACES:
        assert surface_name not in declared_names
        assert cvrp_adapter.is_active_research_surface(surface_name) is False
        assert cvrp_adapter.is_legacy_research_surface(surface_name) is False


def test_cvrp_hypothesis_context_exposes_only_solver_design_as_active_surface(
    cvrp_spec: ProblemSpecV1,
    cvrp_adapter: ProblemAdapter,
) -> None:
    legacy = legacy_problem_spec_from_v1(cvrp_spec)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(CVRP_DIR),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b-active-cvrp-surface",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )

    ctx = ContextManager(adapter=cvrp_adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
    )

    assert ctx["active_problem_boundary_surfaces"] == "solver_design"
    assert ctx["operator_categories"] == "solver_design"
    assert "solver_design [solver_design]" in ctx["research_surfaces"]
    for surface_name in _LEGACY_SURFACES:
        assert f"{surface_name} [" not in ctx["research_surfaces"]
    assert "policies/baseline_algorithm.py" in ctx["targetable_files"]
    assert "policies/baseline_modules/*.py" in ctx["targetable_files"]
    assert "policies/baseline_policy.py" not in ctx["targetable_files"]
    assert "policies/main_search_strategy.py" not in ctx["targetable_files"]
