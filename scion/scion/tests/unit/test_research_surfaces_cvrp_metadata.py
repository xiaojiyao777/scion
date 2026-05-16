from __future__ import annotations

from pathlib import Path

from scion.contract.gate import ContractGate
from scion.core.models import (
    HypothesisProposal,
    HypothesisRecord,
)
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)


def test_cvrp_problem_v1_exposes_policy_surfaces() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    legacy = legacy_problem_spec_from_v1(spec)

    assert legacy.operator_categories == [
        "route_local",
        "route_pair",
        "ruin_recreate",
        "search_policy",
        "baseline_policy",
        "construction_policy",
        "neighborhood_portfolio",
        "algorithm_blueprint",
        "solver_design",
        "main_search_strategy",
        "alns_vns_policy",
        "destroy_repair_policy",
        "route_pair_candidate_policy",
        "acceptance_restart_policy",
    ]
    assert "policies/*.py" in legacy.search_space.editable
    assert "solver.py" in legacy.search_space.frozen
    search_policy = next(
        surface
        for surface in spec.research_surfaces or []
        if surface.name == "search_policy"
    )
    assert search_policy.algorithm is not None
    assert search_policy.algorithm.role == "post_baseline_search_scheduling"
    assert search_policy.targets is not None
    assert search_policy.targets.singleton is True
    assert search_policy.interface is not None
    assert search_policy.interface.required_functions == [
        "baseline_time_fraction",
        "max_operator_rounds",
        "enable_post_baseline_operators",
    ]
    assert search_policy.interface.function_signatures == {
        "baseline_time_fraction": ["instance", "time_limit_sec"],
        "max_operator_rounds": ["instance", "time_limit_sec"],
        "enable_post_baseline_operators": ["instance", "time_limit_sec"],
    }
    assert search_policy.evidence is not None
    assert "policy_loaded" in search_policy.evidence.required_runtime_fields
    assert search_policy.novelty is not None
    assert search_policy.novelty.signature_fields == [
        "predicted_direction",
        "target_objectives",
    ]
    assert spec.runtime_failure_guidance
    no_accepted_guidance = spec.runtime_failure_guidance[0]
    assert no_accepted_guidance.failure_categories == ["no_accepted_moves"]
    assert no_accepted_guidance.applies_to_surface_kinds == ["operator"]
    assert no_accepted_guidance.recommended_surfaces == [
        "solver_design",
        "algorithm_blueprint",
        "baseline_policy",
        "construction_policy",
        "neighborhood_portfolio",
        "alns_vns_policy",
        "destroy_repair_policy",
        "route_pair_candidate_policy",
        "acceptance_restart_policy",
        "search_policy",
    ]
    assert "route_local" in no_accepted_guidance.discouraged_surfaces
    assert "accepted move rate" in no_accepted_guidance.guidance
    assert legacy.runtime_failure_guidance[0].failure_categories == [
        "no_accepted_moves"
    ]

    baseline_policy = next(
        surface
        for surface in spec.research_surfaces or []
        if surface.name == "baseline_policy"
    )
    assert baseline_policy.kind == "policy"
    assert baseline_policy.algorithm is not None
    assert baseline_policy.algorithm.role == "repo_local_baseline_main_search"
    assert baseline_policy.targets is not None
    assert baseline_policy.targets.files == ["policies/baseline_policy.py"]
    assert baseline_policy.targets.singleton is True
    assert baseline_policy.targets.create_new_allowed is False
    assert baseline_policy.targets.remove_allowed is False
    assert baseline_policy.interface is not None
    assert baseline_policy.interface.required_functions == ["baseline_params"]
    assert baseline_policy.interface.function_signatures == {
        "baseline_params": ["instance", "time_limit_sec"],
    }
    assert baseline_policy.bounds is not None
    assert baseline_policy.bounds.numeric_ranges["destroy_ratio"] == (0.01, 0.80)
    assert baseline_policy.bounds.numeric_ranges["max_destroy_customers"] == (1, 500)
    assert baseline_policy.evidence is not None
    assert baseline_policy.evidence.required_runtime_fields == [
        "baseline_policy_loaded",
        "baseline_policy_errors",
        "baseline_policy_params",
        "baseline_destroy_ratio",
        "baseline_segment_length",
        "baseline_reaction_factor",
        "baseline_use_vns",
        "baseline_vns_max_no_improve",
        "baseline_max_destroy_customers",
    ]
    assert baseline_policy.novelty is not None
    assert baseline_policy.novelty.signature_fields == [
        "predicted_direction",
        "target_objectives",
    ]

    construction_policy = next(
        surface
        for surface in spec.research_surfaces or []
        if surface.name == "construction_policy"
    )
    assert construction_policy.kind == "construction"
    assert construction_policy.algorithm is not None
    assert construction_policy.algorithm.role == "initial_solution_construction"
    assert construction_policy.targets is not None
    assert construction_policy.targets.files == ["policies/construction_policy.py"]
    assert construction_policy.targets.singleton is True
    assert construction_policy.targets.create_new_allowed is False
    assert construction_policy.targets.remove_allowed is False
    assert construction_policy.interface is not None
    assert construction_policy.interface.required_functions == [
        "construction_mode",
        "construction_bias",
    ]
    assert construction_policy.interface.function_signatures == {
        "construction_mode": ["instance", "time_limit_sec"],
        "construction_bias": ["instance", "time_limit_sec"],
    }
    assert construction_policy.bounds is not None
    assert "nearest_neighbor" in construction_policy.bounds.allowed_components
    assert construction_policy.evidence is not None
    assert construction_policy.evidence.required_runtime_fields == [
        "construction_surface_loaded",
        "construction_errors",
        "construction_mode",
        "construction_elapsed_ms",
        "construction_routes",
        "construction_distance",
        "construction_feasible",
    ]
    assert construction_policy.novelty is not None
    assert construction_policy.novelty.signature_fields == [
        "predicted_direction",
        "target_objectives",
    ]

    neighborhood_portfolio = next(
        surface
        for surface in spec.research_surfaces or []
        if surface.name == "neighborhood_portfolio"
    )
    assert neighborhood_portfolio.kind == "portfolio"
    assert neighborhood_portfolio.algorithm is not None
    assert neighborhood_portfolio.algorithm.role == "post_baseline_neighborhood_portfolio"
    assert neighborhood_portfolio.targets is not None
    assert neighborhood_portfolio.targets.files == [
        "policies/neighborhood_portfolio.py"
    ]
    assert neighborhood_portfolio.targets.singleton is True
    assert neighborhood_portfolio.targets.create_new_allowed is False
    assert neighborhood_portfolio.targets.remove_allowed is False
    assert neighborhood_portfolio.interface is not None
    assert neighborhood_portfolio.interface.required_functions == [
        "enabled_components",
        "component_weights",
        "candidate_limits",
    ]
    assert neighborhood_portfolio.interface.function_signatures == {
        "enabled_components": ["instance", "time_limit_sec"],
        "component_weights": ["instance", "time_limit_sec"],
        "candidate_limits": ["instance", "time_limit_sec"],
    }
    assert neighborhood_portfolio.bounds is not None
    assert neighborhood_portfolio.bounds.numeric_ranges["max_rounds"] == (0, 6)
    assert neighborhood_portfolio.bounds.numeric_ranges["top_k"] == (0, 32)
    assert neighborhood_portfolio.bounds.allowed_components == [
        "route_local",
        "route_pair",
        "ruin_recreate",
        "registry_operator",
    ]
    assert neighborhood_portfolio.evidence is not None
    assert neighborhood_portfolio.evidence.required_runtime_fields == [
        "portfolio_surface_loaded",
        "portfolio_errors",
        "enabled_components",
        "component_weights",
        "candidate_limits",
        "component_attempts",
        "component_accepted",
        "component_runtime_ms",
        "portfolio_stop_reason",
    ]
    assert neighborhood_portfolio.novelty is not None
    assert neighborhood_portfolio.novelty.signature_fields == [
        "predicted_direction",
        "target_objectives",
    ]

    algorithm_blueprint = next(
        surface
        for surface in spec.research_surfaces or []
        if surface.name == "algorithm_blueprint"
    )
    assert algorithm_blueprint.kind == "config"
    assert algorithm_blueprint.algorithm is not None
    assert algorithm_blueprint.algorithm.role == "top_level_algorithm_lifecycle"
    assert algorithm_blueprint.targets is not None
    assert algorithm_blueprint.targets.files == ["policies/algorithm_blueprint.py"]
    assert algorithm_blueprint.targets.singleton is True
    assert algorithm_blueprint.targets.create_new_allowed is False
    assert algorithm_blueprint.targets.remove_allowed is False
    assert algorithm_blueprint.interface is not None
    assert algorithm_blueprint.interface.required_functions == ["algorithm_plan"]
    assert algorithm_blueprint.interface.function_signatures == {
        "algorithm_plan": ["instance", "time_limit_sec"],
    }
    assert algorithm_blueprint.bounds is not None
    assert "intra_route_2opt" in algorithm_blueprint.bounds.allowed_components
    assert "inter_route_relocate" in algorithm_blueprint.bounds.allowed_components
    assert algorithm_blueprint.evidence is not None
    assert "algorithm_blueprint_errors" in (
        algorithm_blueprint.evidence.required_runtime_fields
    )
    assert "algorithm_local_search_components" in (
        algorithm_blueprint.evidence.required_runtime_fields
    )
    assert algorithm_blueprint.novelty is not None
    assert algorithm_blueprint.novelty.signature_fields == [
        "predicted_direction",
        "target_objectives",
    ]

    solver_design = next(
        surface
        for surface in spec.research_surfaces or []
        if surface.name == "solver_design"
    )
    assert solver_design.kind == "solver_design"
    assert solver_design.algorithm is not None
    assert solver_design.algorithm.role == "problem_object_solver_algorithm"
    assert solver_design.targets is not None
    assert solver_design.targets.files == [
        "policies/baseline_algorithm.py",
        "policies/solver_algorithm.py",
        "policies/baseline_modules/*.py",
    ]
    assert solver_design.targets.singleton is False
    assert solver_design.targets.create_new_allowed is True
    assert solver_design.targets.remove_allowed is True
    assert solver_design.interface is not None
    assert solver_design.interface.required_functions == ["solve"]
    assert solver_design.interface.function_signatures == {
        "solve": ["instance", "rng", "time_limit_sec", "context"],
    }
    assert solver_design.bounds is not None
    assert "local_search" in solver_design.bounds.allowed_components
    assert "destroy_repair" in solver_design.bounds.allowed_components
    assert solver_design.evidence is not None
    assert "solver_algorithm_errors" in (
        solver_design.evidence.required_runtime_fields
    )
    assert "solver_algorithm_active" in (
        solver_design.evidence.required_runtime_fields
    )
    assert "solver_algorithm_phase_runtime_ms" in (
        solver_design.evidence.required_runtime_fields
    )
    assert "solver_algorithm_total_distance" in (
        solver_design.evidence.required_runtime_fields
    )
    assert "solver_algorithm_move_attempts" in (
        solver_design.evidence.required_runtime_fields
    )
    assert "solver_algorithm_phase_delta_sum" in (
        solver_design.evidence.required_runtime_fields
    )
    main_search_strategy = next(
        surface
        for surface in spec.research_surfaces or []
        if surface.name == "main_search_strategy"
    )
    assert main_search_strategy.kind == "config"
    assert main_search_strategy.targets is not None
    assert main_search_strategy.targets.files == ["policies/main_search_strategy.py"]
    assert main_search_strategy.interface is not None
    assert main_search_strategy.interface.required_functions == ["main_search_plan"]
    assert solver_design.novelty is not None
    assert solver_design.novelty.signature_fields == [
        "predicted_direction",
        "target_objectives",
        "algorithm_family",
        "construction_strategy",
        "improvement_strategy",
        "acceptance_strategy",
        "runtime_budget_strategy",
    ]


def test_cvrp_semantic_signature_fields_are_contract_supported() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    unsupported: dict[str, set[str]] = {}
    for surface in spec.research_surfaces or []:
        novelty = surface.novelty
        if novelty is None or novelty.strategy != "semantic_signature":
            continue
        unsupported_fields = {
            field
            for field in novelty.signature_fields
            if not ContractGate.supports_semantic_signature_field(field)
        }
        if unsupported_fields:
            unsupported[surface.name] = unsupported_fields

    assert unsupported == {}


def test_cvrp_search_policy_semantic_signature_distinguishes_objective_identity() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    gate = ContractGate(legacy_problem_spec_from_v1(spec))
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="search_policy",
        action="modify",
        status="active",
        target_file="policies/search_policy.py",
        hypothesis_text="Spend more of the budget on operator rounds for distance.",
        predicted_direction="improve",
        target_objectives=("total_distance",),
    )
    different_identity = HypothesisProposal(
        hypothesis_text="Protect fleet comparability with a stricter policy.",
        change_locus="search_policy",
        action="modify",
        target_file="policies/search_policy.py",
        predicted_direction="improve",
        target_objectives=("fleet_violation",),
    )
    same_identity = HypothesisProposal(
        hypothesis_text="Use another distance-focused policy schedule.",
        change_locus="search_policy",
        action="modify",
        target_file="policies/search_policy.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
    )

    different_result = gate.validate_hypothesis(different_identity, [existing], [])
    same_result = gate.validate_hypothesis(same_identity, [existing], [])

    assert different_result.passed
    assert not same_result.passed
    assert "C10_novelty" in (same_result.failure_reason or "")


def test_cvrp_main_search_strategy_same_target_allows_distinct_semantic_signatures() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    gate = ContractGate(legacy_problem_spec_from_v1(spec))
    existing = [
        HypothesisRecord(
            hypothesis_id="h1",
            branch_id="b1",
            change_locus="solver_design",
            action="modify",
            status="active",
            target_file="policies/solver_algorithm.py",
            hypothesis_text="Use route-pair swap inside a direct solver algorithm.",
            predicted_direction="improve",
            target_objectives=("total_distance",),
            novelty_signature={
                "algorithm_family": "route_pair_local_search",
                "construction_strategy": "nearest_neighbor_seed_pool",
                "improvement_strategy": "bounded_route_pair_swap",
                "acceptance_strategy": "strict_distance_improvement",
                "runtime_budget_strategy": "reserve_exit_time",
            },
        ),
        HypothesisRecord(
            hypothesis_id="h2",
            branch_id="b2",
            change_locus="solver_design",
            action="modify",
            status="active",
            target_file="policies/solver_algorithm.py",
            hypothesis_text="Use bounded destroy repair inside a direct solver algorithm.",
            predicted_direction="improve",
            target_objectives=("fleet_violation",),
            novelty_signature={
                "algorithm_family": "destroy_repair_metaheuristic",
                "construction_strategy": "baseline_helper_seed",
                "improvement_strategy": "bounded_destroy_repair",
                "acceptance_strategy": "phase_best_recovery",
                "runtime_budget_strategy": "baseline_then_repair",
            },
        ),
    ]
    candidate = HypothesisProposal(
        hypothesis_text="Use two-opt and relocate inside a direct solver algorithm.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/solver_algorithm.py",
        predicted_direction="improve",
        target_objectives=("fleet_violation", "total_distance"),
        novelty_signature={
            "algorithm_family": "local_search_metaheuristic",
            "construction_strategy": "demand_seeded_nearest_neighbor",
            "improvement_strategy": "two_opt_relocate",
            "acceptance_strategy": "best_improvement",
            "runtime_budget_strategy": "bounded_passes",
        },
    )

    result = gate.validate_hypothesis(candidate, existing, [])

    assert result.passed


def test_cvrp_main_search_strategy_rejects_false_deep_component_identity() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    gate = ContractGate(legacy_problem_spec_from_v1(spec))
    candidate = HypothesisProposal(
        hypothesis_text="Use a shallow two-opt-only lifecycle.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/solver_algorithm.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
        novelty_signature={
            "algorithm_family": False,
            "construction_strategy": "nearest_neighbor",
            "improvement_strategy": "two_opt",
            "acceptance_strategy": "strict_improvement",
            "runtime_budget_strategy": "bounded_passes",
        },
    )

    result = gate.validate_hypothesis(candidate, [], [])

    assert not result.passed
    assert "C10_novelty" in (result.failure_reason or "")
    assert "algorithm_family" in (result.failure_reason or "")


def test_cvrp_main_search_strategy_identical_semantic_signature_fails_c10() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    gate = ContractGate(legacy_problem_spec_from_v1(spec))
    signature = {
        "algorithm_family": "route_pair_local_search",
        "construction_strategy": "nearest_neighbor_seed_pool",
        "improvement_strategy": "bounded_route_pair_swap",
        "acceptance_strategy": "strict_distance_improvement",
        "runtime_budget_strategy": "reserve_exit_time",
    }
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="solver_design",
        action="modify",
        status="active",
        target_file="policies/solver_algorithm.py",
        hypothesis_text="Use route-pair swap inside a direct solver algorithm.",
        predicted_direction="improve",
        target_objectives=("total_distance",),
        novelty_signature=signature,
    )
    candidate = HypothesisProposal(
        hypothesis_text="Same structured main search plan with different prose.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/solver_algorithm.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
        novelty_signature=dict(signature),
    )

    result = gate.validate_hypothesis(candidate, [existing], [])

    assert not result.passed
    assert "C10_novelty" in (result.failure_reason or "")
    c10 = next(check for check in result.checks if check.name == "C10_novelty")
    assert "duplicate structured novelty_signature" in c10.detail
