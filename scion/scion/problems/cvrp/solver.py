"""CVRP solver wrapper used by Scion campaigns.

The wrapper owns the Scion operator boundary. For real CVRPLIB ``.vrp`` runs it
uses the repository CVRP baseline under ``vrp/src`` when available, then applies
generated Scion operators as a bounded post-baseline improvement layer. JSON
fixtures keep the small deterministic construction path used by tests.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Mapping

from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.models import CvrpInstance, CvrpSolution


_MAX_OPERATOR_ROUNDS = 20
_OBJECTIVE_TOLERANCE = 1e-9
_BASELINE_TIME_FRACTION = 0.8
_MIN_BASELINE_TIME_FRACTION = 0.2
_MAX_BASELINE_TIME_FRACTION = 0.95
_SEARCH_POLICY_RELATIVE_PATH = "policies/search_policy.py"
_BASELINE_POLICY_RELATIVE_PATH = "policies/baseline_policy.py"
_CONSTRUCTION_POLICY_RELATIVE_PATH = "policies/construction_policy.py"
_NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH = "policies/neighborhood_portfolio.py"
_ALGORITHM_BLUEPRINT_RELATIVE_PATH = "policies/algorithm_blueprint.py"
_MAIN_SEARCH_STRATEGY_RELATIVE_PATH = "policies/main_search_strategy.py"
_BASELINE_ALGORITHM_RELATIVE_PATH = "policies/baseline_algorithm.py"
_SOLVER_ALGORITHM_RELATIVE_PATH = "policies/solver_algorithm.py"
_SOLVER_ALGORITHM_RELATIVE_PATHS = (
    _BASELINE_ALGORITHM_RELATIVE_PATH,
    _SOLVER_ALGORITHM_RELATIVE_PATH,
)
_ALNS_VNS_POLICY_RELATIVE_PATH = "policies/alns_vns_policy.py"
_DESTROY_REPAIR_POLICY_RELATIVE_PATH = "policies/destroy_repair_policy.py"
_ROUTE_PAIR_CANDIDATE_POLICY_RELATIVE_PATH = "policies/route_pair_candidate_policy.py"
_ACCEPTANCE_RESTART_POLICY_RELATIVE_PATH = "policies/acceptance_restart_policy.py"
_DEFAULT_CONSTRUCTION_MODE = "nearest_neighbor"
_DEFAULT_CONSTRUCTION_BIAS = 0.0
_MIN_CONSTRUCTION_BIAS = 0.0
_MAX_CONSTRUCTION_BIAS = 1.0
_MAX_COMPONENT_WEIGHT = 5.0
_MAX_PORTFOLIO_TOP_K = 1000
_MAX_PORTFOLIO_ATTEMPTS = 1_000_000
_ALLOWED_PORTFOLIO_COMPONENTS = frozenset(
    {
        "route_local",
        "route_pair",
        "ruin_recreate",
        "registry_operator",
    }
)
_DEFAULT_ENABLED_COMPONENTS = tuple(sorted(_ALLOWED_PORTFOLIO_COMPONENTS))
_DEFAULT_COMPONENT_WEIGHTS = {
    component: 1.0 for component in _DEFAULT_ENABLED_COMPONENTS
}
_DEFAULT_CANDIDATE_LIMITS = {
    "max_rounds": _MAX_OPERATOR_ROUNDS,
    "top_k": _MAX_PORTFOLIO_TOP_K,
    "total_attempts": _MAX_PORTFOLIO_ATTEMPTS,
    "per_component_attempts": _MAX_PORTFOLIO_ATTEMPTS,
}
_ALLOWED_CONSTRUCTION_MODES = frozenset(
    {
        "nearest_neighbor",
        "nearest_neighbor_demand_bias",
        "demand_descending",
        "sequential",
    }
)
_ALLOWED_BLUEPRINT_LOCAL_SEARCH_COMPONENTS = frozenset(
    {
        "intra_route_2opt",
        "inter_route_relocate",
    }
)
_ALLOWED_MAIN_SEARCH_COMPONENTS = frozenset(
    {
        "intra_route_2opt",
        "inter_route_relocate",
        "route_pair_swap",
        "bounded_destroy_repair",
        "route_pool_recombination",
    }
)
_MAIN_SEARCH_DEEP_ATTRIBUTION_COMPONENTS = _ALLOWED_MAIN_SEARCH_COMPONENTS
_ALLOWED_MAIN_SEARCH_ROLE_TARGETS = (
    _ALLOWED_MAIN_SEARCH_COMPONENTS
    | _ALLOWED_CONSTRUCTION_MODES
    | frozenset(
        {
            "repo_local_baseline",
            "repo_local_baseline_params",
            "baseline_policy",
            "strict_improvement_acceptance",
            "restart_stagnation",
            "bounded_perturbation",
            "pre_improvement_perturbation",
            "post_baseline_operators",
            "post_baseline_operator_toggle",
        }
    )
)
_ALLOWED_MAIN_SEARCH_STRATEGY_FAMILIES = frozenset(
    {
        "balanced_lifecycle",
        "baseline_intensification",
        "construction_diversification",
        "improvement_intensification",
        "destroy_repair_recovery",
        "route_structure_repair",
        "local_search_cleanup",
    }
)
_DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY = "balanced_lifecycle"
_ALLOWED_MAIN_SEARCH_PHASE_OBJECTIVES = frozenset(
    {
        "construction_distance",
        "baseline_distance",
        "phase_best_distance",
        "recovery_to_phase_best",
        "runtime_neutrality",
    }
)
_DEFAULT_MAIN_SEARCH_PHASE_OBJECTIVE = "phase_best_distance"
_ALLOWED_MAIN_SEARCH_COMPONENT_ROLES = frozenset(
    {"primary", "support", "probe", "disabled"}
)
_ALLOWED_MAIN_SEARCH_ALGORITHM_PHASES = frozenset(
    {
        "construction",
        "baseline",
        "global_recombination",
        "route_structure_repair",
        "local_cleanup",
        "perturbation",
        "restart",
    }
)
_DEFAULT_MAIN_SEARCH_ALGORITHM_PHASES = (
    "construction",
    "baseline",
    "global_recombination",
    "route_structure_repair",
    "local_cleanup",
)
_ALLOWED_ROUTE_POOL_ACTIVATIONS = frozenset(
    {"adaptive", "always", "medium_large_only", "disabled"}
)
_DEFAULT_ROUTE_POOL_ACTIVATION = "adaptive"
_DEFAULT_ROUTE_POOL_MIN_CUSTOMERS = 80
_ALLOWED_MAIN_SEARCH_BASELINE_BUDGET_POLICIES = frozenset(
    {"declared", "formal_floor"}
)
_DEFAULT_MAIN_SEARCH_BASELINE_BUDGET_POLICY = "declared"
_MAIN_SEARCH_ADAPTATION_PROFILE_KEYS = frozenset(
    {
        "scale",
        "route_pressure",
        "demand_skew",
        "distance_structure",
        "route_count_hint",
        "customer_count",
    }
)
_ALLOWED_MAIN_SEARCH_EVIDENCE_TARGETS = frozenset(
    {
        "construction_distance",
        "baseline_cost",
        "main_search_component_attempts",
        "main_search_component_accepted",
        "main_search_component_accepted_delta_sum",
        "main_search_component_accepted_best_delta",
        "main_search_component_accepted_positive_counts",
        "main_search_component_recovery_delta_sum",
        "main_search_component_recovery_counts",
        "main_search_component_phase_delta_sum",
        "main_search_component_phase_improvement_counts",
        "main_search_route_pool_source_solutions",
        "main_search_route_pool_sample_count",
        "main_search_route_pool_size",
        "main_search_route_pool_branch_calls",
        "main_search_route_pool_recombined_routes",
        "main_search_restart_count",
        "main_search_perturbation_count",
        "main_search_objective_delta_by_phase",
        "main_search_objective_trace",
        "main_search_phase_runtime_ms",
        "main_search_elapsed_ms",
        "main_search_stop_reason",
    }
)
_DEFAULT_MAIN_SEARCH_EVIDENCE_TARGETS = (
    "main_search_component_phase_delta_sum",
    "main_search_objective_delta_by_phase",
)
_MAX_BLUEPRINT_CONSTRUCTION_METHODS = 4
_MAX_BLUEPRINT_LOCAL_SEARCH_ROUNDS = 4
_MAX_BLUEPRINT_LOCAL_SEARCH_TOP_K = 64
_MAX_BLUEPRINT_RESTART_STAGNATION_ROUNDS = 25
_MAX_MAIN_SEARCH_CONSTRUCTION_METHODS = 4
_MAX_MAIN_SEARCH_ROUNDS = 8
_MAX_MAIN_SEARCH_TOP_K = 128
_MAX_MAIN_SEARCH_RESTARTS = 3
_MAX_MAIN_SEARCH_RESTART_STAGNATION_ROUNDS = 25
_MAX_MAIN_SEARCH_PERTURBATIONS = 4
_MAX_MAIN_SEARCH_PERTURBATION_STRENGTH = 8
_MAX_MAIN_SEARCH_MIN_DISTANCE_IMPROVEMENT = 10.0
_MAIN_SEARCH_FORMAL_BASELINE_TIME_FLOOR = 0.75
_BOUNDED_DESTROY_REPAIR_MIN_DISTANCE_IMPROVEMENT = 1.0
_MAIN_SEARCH_BDR_ACCEPT_LIMIT = 1
_MAX_MAIN_SEARCH_BDR_ACCEPT_LIMIT = 3
_MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_FLOOR = 16
_MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_CEILING = 96
_MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_FRACTION = 0.12
_MAIN_SEARCH_EXIT_RESERVE_SEC = 0.75
_ROUTE_POOL_EXIT_RESERVE_SEC = 2.50
_MAX_EXIT_RESERVE_FRACTION = 0.15
_ROUTE_POOL_MIN_SAMPLE_BUDGET_SEC = 0.20
_ROUTE_POOL_MAX_SAMPLE_BUDGET_SEC = 2.50
_ALGORITHM_BLUEPRINT_REQUIRED_KEYS = frozenset(
    {
        "enabled",
        "construction_methods",
        "construction_keep_top_k",
        "construction_bias",
        "baseline_time_fraction",
        "operator_round_limit",
        "post_baseline_operators_enabled",
        "local_search",
        "restart",
    }
)
_ALGORITHM_BLUEPRINT_LOCAL_SEARCH_REQUIRED_KEYS = frozenset(
    {"enabled_components", "rounds", "top_k"}
)
_ALGORITHM_BLUEPRINT_RESTART_REQUIRED_KEYS = frozenset(
    {"enabled", "stagnation_rounds"}
)
_MAIN_SEARCH_STRATEGY_REQUIRED_KEYS = frozenset(
    {
        "enabled",
        "algorithm_body",
        "construction",
        "baseline",
        "improvement",
        "acceptance",
        "restart",
        "perturbation",
        "post_baseline_operators_enabled",
        "operator_round_limit",
    }
)
_MAIN_SEARCH_STRATEGY_ALLOWED_KEYS = frozenset(
    {*_MAIN_SEARCH_STRATEGY_REQUIRED_KEYS, "problem_adaptation", "algorithm_body"}
)
_MAIN_SEARCH_PROBLEM_ADAPTATION_REQUIRED_KEYS = frozenset(
    {
        "strategy_family",
        "instance_profile",
        "phase_objective",
        "component_roles",
        "fallback_order",
        "evidence_targets",
    }
)
_MAIN_SEARCH_PROBLEM_ADAPTATION_ALLOWED_KEYS = (
    _MAIN_SEARCH_PROBLEM_ADAPTATION_REQUIRED_KEYS
)
_MAIN_SEARCH_ALGORITHM_BODY_ALLOWED_KEYS = frozenset(
    {
        "phase_sequence",
        "baseline_budget_policy",
        "route_pool_activation",
        "route_pool_min_customers",
        "route_pool_max_rounds",
        "local_cleanup_after_recombination",
        "adaptive_component_budget",
    }
)
_MAIN_SEARCH_CONSTRUCTION_REQUIRED_KEYS = frozenset(
    {"methods", "keep_top_k", "bias"}
)
_MAIN_SEARCH_BASELINE_REQUIRED_KEYS = frozenset({"time_fraction", "params"})
_MAIN_SEARCH_IMPROVEMENT_REQUIRED_KEYS = frozenset(
    {"enabled_components", "rounds", "top_k"}
)
_MAIN_SEARCH_ACCEPTANCE_REQUIRED_KEYS = frozenset({"min_distance_improvement"})
_MAIN_SEARCH_ACCEPTANCE_ALLOWED_KEYS = frozenset(
    {
        "min_distance_improvement",
        "component_min_distance_improvement",
        "bounded_destroy_repair_accept_limit",
        "recovery_only_policy",
    }
)
_MAIN_SEARCH_RESTART_REQUIRED_KEYS = frozenset(
    {"enabled", "stagnation_rounds", "max_restarts"}
)
_MAIN_SEARCH_PERTURBATION_REQUIRED_KEYS = frozenset(
    {"enabled", "strength", "max_perturbations"}
)
_MAIN_SEARCH_PERTURBATION_ALLOWED_KEYS = frozenset(
    {*_MAIN_SEARCH_PERTURBATION_REQUIRED_KEYS, "schedule"}
)
_MAIN_SEARCH_PERTURBATION_SCHEDULES = frozenset(
    {
        "after_no_improvement",
        "before_first_round",
        "before_each_round",
    }
)
_DEFAULT_MAIN_SEARCH_PERTURBATION_SCHEDULE = "after_no_improvement"
_DEFAULT_BASELINE_POLICY_PARAMS = {
    "destroy_ratio": (0.10, 0.40),
    "segment_length": 100,
    "reaction_factor": 0.1,
    "vns_max_no_improve": 5000,
    "use_vns": True,
    "cw_threshold": 1500,
    "vns_threshold": 1200,
    "alns_threshold": 2000,
    "max_destroy_customers": 200,
}
_BASELINE_POLICY_ALLOWED_KEYS = frozenset(_DEFAULT_BASELINE_POLICY_PARAMS)
_ALNS_VNS_ALLOWED_COMPONENTS = frozenset({"alns", "vns"})
_ROUTE_PAIR_ALLOWED_SCORING_TERMS = frozenset(
    {
        "route_distance",
        "removal_saving",
        "load_gap",
        "distance_saving",
    }
)
_ROUTE_PAIR_ALLOWED_MOVE_FAMILIES = frozenset({"customer_swap"})
_DESTROY_REPAIR_ALLOWED_DESTROY_SELECTORS = frozenset(
    {
        "worst_removal",
        "route_diverse_worst",
    }
)
_DESTROY_REPAIR_ALLOWED_REPAIR_SELECTORS = frozenset(
    {
        "regret_2",
        "cheapest",
    }
)
_DESTROY_REPAIR_SUBSET_STRATEGIES = frozenset(
    {
        "prefix_shifted_route_diverse",
        "single_worst",
        "route_diverse",
    }
)
_ACCEPTANCE_RECOVERY_POLICIES = frozenset(
    {
        "allow",
        "reject_recovery_only",
        "phase_best_preferred",
    }
)


def solve(
    instance: CvrpInstance,
    rng: random.Random,
    *,
    construction_mode: str = _DEFAULT_CONSTRUCTION_MODE,
    construction_bias: float = _DEFAULT_CONSTRUCTION_BIAS,
) -> CvrpSolution:
    """Capacity-aware nearest-neighbor construction for small fixtures."""
    mode = construction_mode
    if mode not in _ALLOWED_CONSTRUCTION_MODES:
        mode = _DEFAULT_CONSTRUCTION_MODE
    bias = min(max(float(construction_bias), _MIN_CONSTRUCTION_BIAS), _MAX_CONSTRUCTION_BIAS)
    max_demand = max((instance.demand(c) for c in instance.customer_ids), default=1)
    unvisited = set(instance.customer_ids)
    routes: list[tuple[int, ...]] = []
    while unvisited:
        route: list[int] = []
        load = 0
        current = instance.depot
        while True:
            feasible = [
                c for c in unvisited
                if load + instance.demand(c) <= instance.capacity
            ]
            if not feasible:
                break
            nxt = _select_construction_customer(
                feasible,
                instance=instance,
                current=current,
                rng=rng,
                mode=mode,
                bias=bias,
                max_demand=max_demand,
            )
            unvisited.remove(nxt)
            route.append(nxt)
            load += instance.demand(nxt)
            current = nxt
        if not route:
            raise ValueError("remaining customer demand exceeds vehicle capacity")
        routes.append(tuple(route))
    return CvrpSolution(routes=tuple(routes))


def _select_construction_customer(
    feasible: list[int],
    *,
    instance: CvrpInstance,
    current: int,
    rng: random.Random,
    mode: str,
    bias: float,
    max_demand: int,
) -> int:
    if mode == "sequential":
        return min(feasible)
    if mode == "demand_descending":
        return min(
            feasible,
            key=lambda c: (
                -instance.demand(c),
                instance.distance(current, c),
                rng.random(),
            ),
        )
    if mode == "nearest_neighbor_demand_bias":
        demand_scale = max(float(max_demand), 1.0)
        return min(
            feasible,
            key=lambda c: (
                instance.distance(current, c)
                - bias * (float(instance.demand(c)) / demand_scale),
                rng.random(),
            ),
        )
    return min(
        feasible,
        key=lambda c: (instance.distance(current, c), rng.random()),
    )


def solve_baseline(
    *,
    instance: CvrpInstance,
    instance_path: str,
    seed: int,
    rng: random.Random,
    time_limit_sec: float,
    baseline_time_fraction: float = _BASELINE_TIME_FRACTION,
    construction_policy: dict[str, Any] | None = None,
    baseline_policy: dict[str, Any] | None = None,
    alns_vns_policy: dict[str, Any] | None = None,
    algorithm_blueprint: dict[str, Any] | None = None,
    main_search_strategy: dict[str, Any] | None = None,
) -> tuple[CvrpSolution, dict[str, Any]]:
    """Return a baseline solution plus audit metadata.

    Real formal CVRP campaigns are configured with a SCION data-root environment
    variable pointing at the repo-local ``vrp`` directory. In that case this
    wrapper uses the imported ALNS+VNS baseline. Synthetic fixtures and JSON
    smoke tests fall back to the deterministic Scion construction.
    """

    construction_solution, construction_audit = _construct_with_policy_audit(
        instance=instance,
        rng=rng,
        construction_policy=construction_policy,
        algorithm_blueprint=algorithm_blueprint,
        main_search_strategy=main_search_strategy,
    )
    baseline_policy_audit = _baseline_policy_defaults()
    if baseline_policy is not None:
        baseline_policy_audit.update(baseline_policy)
    baseline_policy_params = baseline_policy_audit.get("baseline_policy_params")
    if not isinstance(baseline_policy_params, Mapping):
        baseline_policy_params = dict(_DEFAULT_BASELINE_POLICY_PARAMS)
    if alns_vns_policy and alns_vns_policy.get("alns_vns_active"):
        alns_params = alns_vns_policy.get("alns_vns_baseline_params")
        if isinstance(alns_params, Mapping):
            baseline_policy_params = {**dict(baseline_policy_params), **dict(alns_params)}
            baseline_policy_audit["baseline_policy_params"] = dict(baseline_policy_params)
            baseline_policy_audit["baseline_destroy_ratio"] = list(
                baseline_policy_params["destroy_ratio"]
            )
            baseline_policy_audit["baseline_segment_length"] = baseline_policy_params[
                "segment_length"
            ]
            baseline_policy_audit["baseline_reaction_factor"] = baseline_policy_params[
                "reaction_factor"
            ]
            baseline_policy_audit["baseline_vns_max_no_improve"] = baseline_policy_params[
                "vns_max_no_improve"
            ]
            baseline_policy_audit["baseline_use_vns"] = baseline_policy_params["use_vns"]
            baseline_policy_audit["baseline_cw_threshold"] = baseline_policy_params[
                "cw_threshold"
            ]
            baseline_policy_audit["baseline_vns_threshold"] = baseline_policy_params[
                "vns_threshold"
            ]
            baseline_policy_audit["baseline_alns_threshold"] = baseline_policy_params[
                "alns_threshold"
            ]
            baseline_policy_audit["baseline_max_destroy_customers"] = baseline_policy_params[
                "max_destroy_customers"
            ]
    resolved = Path(instance_path).resolve(strict=False)
    is_vrp = resolved.suffix.lower() == ".vrp"
    baseline_root = _find_vrp_baseline_root()
    baseline_required = is_vrp and _baseline_required_for_instance(resolved)
    effective_baseline_time_fraction = _effective_baseline_time_fraction(
        baseline_time_fraction,
        is_vrp=is_vrp,
        baseline_required=baseline_required,
        main_search_strategy=main_search_strategy,
    )
    baseline_fraction_audit = {
        "main_search_baseline_time_fraction_effective": (
            effective_baseline_time_fraction
        ),
        "main_search_baseline_quality_guard_applied": (
            effective_baseline_time_fraction > float(baseline_time_fraction)
        ),
    }
    if is_vrp and baseline_required and baseline_root is not None:
        budget = _baseline_time_budget(time_limit_sec, effective_baseline_time_fraction)
        try:
            solution, audit = _solve_with_vrp_baseline(
                instance=instance,
                instance_path=resolved,
                seed=seed,
                time_limit_sec=budget,
                baseline_root=baseline_root,
                baseline_required=baseline_required,
                baseline_policy_params=baseline_policy_params,
            )
            alns_audit = _finalize_alns_vns_policy_audit(
                alns_vns_policy,
                audit,
                construction_audit=construction_audit,
            )
            return solution, {
                **construction_audit,
                **baseline_policy_audit,
                **alns_audit,
                **baseline_fraction_audit,
                **audit,
            }
        except Exception as exc:
            fallback = construction_solution
            baseline_error_audit = {
                "baseline_mode": "scion_nearest_neighbor_fallback",
                "baseline_required": baseline_required,
                "baseline_error": f"{type(exc).__name__}: {exc}",
                "baseline_budget_s": budget,
                "baseline_routes": len(fallback.routes),
                "baseline_cost": sum(instance.route_distance(r) for r in fallback.routes),
            }
            alns_audit = _finalize_alns_vns_policy_audit(
                alns_vns_policy,
                baseline_error_audit,
                construction_audit=construction_audit,
            )
            return fallback, {
                **construction_audit,
                **baseline_policy_audit,
                **alns_audit,
                **baseline_fraction_audit,
                **baseline_error_audit,
            }
    if is_vrp and baseline_required:
        fallback = construction_solution
        baseline_error_audit = {
            "baseline_mode": "scion_nearest_neighbor_fallback",
            "baseline_required": True,
            "baseline_error": "vrp/src baseline not available for configured CVRP data root",
            "baseline_routes": len(fallback.routes),
            "baseline_cost": sum(instance.route_distance(r) for r in fallback.routes),
        }
        alns_audit = _finalize_alns_vns_policy_audit(
            alns_vns_policy,
            baseline_error_audit,
            construction_audit=construction_audit,
        )
        return fallback, {
            **construction_audit,
            **baseline_policy_audit,
            **alns_audit,
            **baseline_fraction_audit,
            **baseline_error_audit,
        }

    fallback = construction_solution
    baseline_audit = {
        "baseline_mode": "scion_nearest_neighbor",
        "baseline_required": False,
        "baseline_routes": len(fallback.routes),
        "baseline_cost": sum(instance.route_distance(r) for r in fallback.routes),
    }
    alns_audit = _finalize_alns_vns_policy_audit(
        alns_vns_policy,
        baseline_audit,
        construction_audit=construction_audit,
    )
    return fallback, {
        **construction_audit,
        **baseline_policy_audit,
        **alns_audit,
        **baseline_fraction_audit,
        **baseline_audit,
    }


def improve_with_registry_operators(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    rng: random.Random,
    registry_path: str,
    workspace_root: str | Path,
    time_limit_sec: float,
    start_time: float,
    max_operator_rounds: int = _MAX_OPERATOR_ROUNDS,
    post_baseline_operators_enabled: bool = True,
    neighborhood_portfolio: dict[str, Any] | None = None,
) -> tuple[CvrpSolution, dict[str, Any]]:
    """Apply registry operators with bounded, auditable acceptance."""

    audit: dict[str, Any] = {
        "operator_registry_path": registry_path or "",
        "operator_loaded": 0,
        "operator_attempts": 0,
        "operator_accepted": 0,
        "operator_skipped": 0,
        "operator_errors": 0,
        "operator_invalid_outputs": 0,
        "operator_rounds": 0,
        "operator_no_improvement_rounds": 0,
        "operator_rounds_with_acceptance": 0,
        "operator_stop_reason": "",
        "operator_events": [],
    }
    portfolio_audit = _portfolio_audit_defaults(neighborhood_portfolio)
    audit.update(portfolio_audit)
    if not post_baseline_operators_enabled:
        audit["operator_stop_reason"] = "disabled_by_policy"
        audit["portfolio_stop_reason"] = "disabled_by_search_policy"
        return solution, audit

    operators = _load_registry_operators(
        registry_path=registry_path,
        workspace_root=workspace_root,
        audit=audit,
    )
    operators = _apply_neighborhood_portfolio(
        operators,
        audit=audit,
        max_operator_rounds=max_operator_rounds,
    )
    if not operators:
        if not audit["portfolio_stop_reason"]:
            if not registry_path or audit["operator_loaded"] == 0:
                audit["portfolio_stop_reason"] = "no_registry_operators"
            else:
                audit["portfolio_stop_reason"] = "no_enabled_components"
        return solution, audit

    current = solution
    current_objective = _objective_for_solution(adapter, instance, current)
    fatal_operator_failure = False
    max_operator_rounds = int(audit["portfolio_effective_round_limit"])
    for round_index in range(max_operator_rounds):
        if _time_exhausted(start_time, time_limit_sec):
            audit["operator_stop_reason"] = "time_limit"
            audit["portfolio_stop_reason"] = "time_limit"
            break
        round_accepted = 0
        round_completed = True
        audit["operator_rounds"] = round_index + 1
        for operator in operators:
            if _main_search_time_exhausted(start_time, time_limit_sec):
                audit["operator_stop_reason"] = "time_limit"
                audit["portfolio_stop_reason"] = "time_limit"
                round_completed = False
                break
            if _portfolio_attempt_limit_reached(audit, operator.component):
                audit["operator_stop_reason"] = "portfolio_attempt_limit"
                audit["portfolio_stop_reason"] = "attempt_limit"
                round_completed = False
                break
            audit["operator_attempts"] += 1
            component_attempts = audit["component_attempts"]
            component_attempts[operator.component] = (
                _as_nonnegative_int(component_attempts.get(operator.component)) + 1
            )
            op_start_ns = time.monotonic_ns()
            try:
                candidate = operator.instance.execute(current, instance, rng)
            except Exception as exc:
                _record_component_runtime(audit, operator.component, op_start_ns)
                audit["operator_errors"] += 1
                _record_event(audit, operator.name, "error", str(exc))
                fatal_operator_failure = True
                continue
            _record_component_runtime(audit, operator.component, op_start_ns)

            candidate_solution = _coerce_solution(candidate)
            if candidate_solution is None:
                audit["operator_skipped"] += 1
                audit["operator_errors"] += 1
                audit["operator_invalid_outputs"] += 1
                _record_event(audit, operator.name, "error", "returned invalid solution object")
                fatal_operator_failure = True
                continue

            valid, reason = _solution_is_valid(adapter, instance, candidate_solution)
            if not valid:
                audit["operator_skipped"] += 1
                audit["operator_errors"] += 1
                audit["operator_invalid_outputs"] += 1
                _record_event(audit, operator.name, "error", reason)
                fatal_operator_failure = True
                continue

            candidate_objective = _objective_for_solution(adapter, instance, candidate_solution)
            if _lexicographic_improves(candidate_objective, current_objective):
                current = candidate_solution
                current_objective = candidate_objective
                audit["operator_accepted"] += 1
                component_accepted = audit["component_accepted"]
                component_accepted[operator.component] = (
                    _as_nonnegative_int(component_accepted.get(operator.component)) + 1
                )
                round_accepted += 1
                _record_event(audit, operator.name, "accepted", "")
            else:
                audit["operator_skipped"] += 1
                _record_event(audit, operator.name, "skipped", "not an improvement")
        if round_accepted > 0:
            audit["operator_rounds_with_acceptance"] += 1
        elif round_completed and not fatal_operator_failure:
            audit["operator_no_improvement_rounds"] += 1
        if fatal_operator_failure:
            audit["operator_stop_reason"] = "fatal_operator_failure"
            audit["portfolio_stop_reason"] = "fatal_operator_failure"
            break
        if audit["operator_stop_reason"] == "time_limit":
            break
        if audit["operator_stop_reason"] == "portfolio_attempt_limit":
            break
        if round_completed and round_accepted == 0:
            audit["operator_stop_reason"] = "no_improvement_round"
            audit["portfolio_stop_reason"] = "no_improvement_round"
            break
    else:
        audit["operator_stop_reason"] = "max_operator_rounds"
        audit["portfolio_stop_reason"] = "max_operator_rounds"
    if not audit["portfolio_stop_reason"]:
        audit["portfolio_stop_reason"] = audit["operator_stop_reason"] or "completed"
    return current, audit


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--time-limit", type=float, default=30.0)
    parser.add_argument("--registry", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    start = time.perf_counter()

    class _Spec:
        pass

    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    instance_path = _resolve_instance_path(args.instance)
    instance = adapter.load_instance(instance_path)
    rng = random.Random(args.seed)
    solver_algorithm_solution, solver_algorithm = _load_solver_algorithm(
        workspace_root=Path.cwd(),
        instance=instance,
        instance_path=instance_path,
        seed=args.seed,
        rng=rng,
        time_limit_sec=args.time_limit,
        start_time=start,
        adapter=adapter,
    )
    if _solver_algorithm_active(solver_algorithm) and solver_algorithm_solution is not None:
        sol = solver_algorithm_solution
        search_policy = _search_policy_defaults()
        algorithm_blueprint = _algorithm_blueprint_defaults()
        construction_policy = _construction_policy_defaults()
        baseline_policy = _baseline_policy_defaults()
        alns_vns_policy = _alns_vns_policy_defaults()
        neighborhood_portfolio = _portfolio_audit_defaults()
        destroy_repair_policy = _destroy_repair_policy_defaults()
        route_pair_policy = _route_pair_policy_defaults()
        acceptance_restart_policy = _acceptance_restart_policy_defaults()
        main_search_strategy = _main_search_strategy_defaults()
        baseline_audit: dict[str, Any] = {}
        algorithm_audit: dict[str, Any] = {}
        main_search_audit: dict[str, Any] = {}
        operator_audit: dict[str, Any] = {}
    else:
        main_search_strategy = _load_main_search_strategy(
            workspace_root=Path.cwd(),
            instance=instance,
            time_limit_sec=args.time_limit,
        )
        algorithm_blueprint = _load_algorithm_blueprint(
            workspace_root=Path.cwd(),
            instance=instance,
            time_limit_sec=args.time_limit,
        )
        search_policy = _load_search_policy(
            workspace_root=Path.cwd(),
            instance=instance,
            time_limit_sec=args.time_limit,
        )
        if _main_search_strategy_active(main_search_strategy):
            _apply_main_search_strategy_search_policy(
                search_policy,
                main_search_strategy=main_search_strategy,
            )
        else:
            _apply_algorithm_blueprint_search_policy(
                search_policy,
                algorithm_blueprint=algorithm_blueprint,
            )
        construction_policy = _load_construction_policy(
            workspace_root=Path.cwd(),
            instance=instance,
            time_limit_sec=args.time_limit,
        )
        baseline_policy = _load_baseline_policy(
            workspace_root=Path.cwd(),
            instance=instance,
            time_limit_sec=args.time_limit,
        )
        alns_vns_policy = _load_alns_vns_policy(
            workspace_root=Path.cwd(),
            instance=instance,
            time_limit_sec=args.time_limit,
        )
        neighborhood_portfolio = _load_neighborhood_portfolio(
            workspace_root=Path.cwd(),
            instance=instance,
            time_limit_sec=args.time_limit,
        )
        destroy_repair_policy = _load_destroy_repair_policy(
            workspace_root=Path.cwd(),
            instance=instance,
            time_limit_sec=args.time_limit,
        )
        route_pair_policy = _load_route_pair_candidate_policy(
            workspace_root=Path.cwd(),
            instance=instance,
            time_limit_sec=args.time_limit,
        )
        acceptance_restart_policy = _load_acceptance_restart_policy(
            workspace_root=Path.cwd(),
            instance=instance,
            time_limit_sec=args.time_limit,
        )
        _activate_main_search_strategy_for_mechanism_policies(
            main_search_strategy,
            instance=instance,
            destroy_repair_policy=destroy_repair_policy,
            route_pair_policy=route_pair_policy,
            acceptance_restart_policy=acceptance_restart_policy,
        )
        if _main_search_strategy_active(main_search_strategy):
            _apply_main_search_strategy_baseline_policy(
                baseline_policy,
                main_search_strategy=main_search_strategy,
            )
        sol, baseline_audit = solve_baseline(
            instance=instance,
            instance_path=instance_path,
            seed=args.seed,
            rng=rng,
            time_limit_sec=args.time_limit,
            baseline_time_fraction=search_policy["baseline_time_fraction"],
            construction_policy=construction_policy,
            baseline_policy=baseline_policy,
            alns_vns_policy=alns_vns_policy,
            algorithm_blueprint=(
                None if _main_search_strategy_active(main_search_strategy) else algorithm_blueprint
            ),
            main_search_strategy=main_search_strategy,
        )
        main_search_audit = {}
        if _main_search_strategy_active(main_search_strategy):
            sol, main_search_audit = improve_with_main_search_strategy(
                sol,
                instance,
                adapter=adapter,
                rng=rng,
                time_limit_sec=args.time_limit,
                start_time=start,
                instance_path=instance_path,
                seed=args.seed,
                main_search_strategy=main_search_strategy,
                destroy_repair_policy=destroy_repair_policy,
                route_pair_policy=route_pair_policy,
                acceptance_restart_policy=acceptance_restart_policy,
            )
            algorithm_audit = {}
        else:
            sol, algorithm_audit = improve_with_algorithm_blueprint(
                sol,
                instance,
                adapter=adapter,
                rng=rng,
                time_limit_sec=args.time_limit,
                start_time=start,
                algorithm_blueprint=algorithm_blueprint,
            )
        sol, operator_audit = improve_with_registry_operators(
            sol,
            instance,
            adapter=adapter,
            rng=rng,
            registry_path=args.registry,
            workspace_root=Path.cwd(),
            time_limit_sec=args.time_limit,
            start_time=start,
            max_operator_rounds=search_policy["operator_round_limit"],
            post_baseline_operators_enabled=search_policy[
                "post_baseline_operators_enabled"
            ],
            neighborhood_portfolio=neighborhood_portfolio,
        )
    raw = {"routes": [list(route) for route in sol.routes], "feasible": True}
    artifact = adapter.deserialize_solver_output(raw, instance)
    objective = dict(adapter.recompute_objective(artifact, instance))
    raw["objective"] = objective
    raw["runtime"] = {
        "elapsed_s": time.perf_counter() - start,
        "time_limit_s": args.time_limit,
        **solver_algorithm,
        **search_policy,
        **construction_policy,
        **algorithm_blueprint,
        **algorithm_audit,
        **alns_vns_policy,
        **destroy_repair_policy,
        **route_pair_policy,
        **acceptance_restart_policy,
        **_finalize_main_search_audit(dict(main_search_strategy)),
        **main_search_audit,
        **baseline_audit,
        **operator_audit,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)


class _LoadedOperator:
    def __init__(
        self,
        name: str,
        weight: float,
        instance: Any,
        order: int,
        component: str,
    ) -> None:
        self.name = name
        self.weight = weight
        self.instance = instance
        self.order = order
        self.component = component


def _load_registry_operators(
    *,
    registry_path: str,
    workspace_root: str | Path,
    audit: dict[str, Any],
) -> tuple[_LoadedOperator, ...]:
    if not registry_path:
        return tuple()
    path = Path(registry_path)
    if not path.exists():
        return tuple()

    try:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        audit["operator_errors"] += 1
        _record_event(audit, "<registry>", "error", f"registry read failed: {exc}")
        return tuple()

    raw_operators = payload.get("operators", []) if isinstance(payload, Mapping) else []
    if not isinstance(raw_operators, list):
        audit["operator_errors"] += 1
        _record_event(audit, "<registry>", "error", "operators field is not a list")
        return tuple()

    workspace = Path(workspace_root).resolve()
    loaded: list[_LoadedOperator] = []
    for index, entry in enumerate(raw_operators):
        if not isinstance(entry, Mapping):
            audit["operator_skipped"] += 1
            _record_event(audit, f"entry-{index}", "skipped", "registry entry is not a mapping")
            continue
        name = str(entry.get("name") or f"operator-{index}")
        file_path = str(entry.get("file_path") or "").strip()
        class_name = str(entry.get("class_name") or "").strip()
        weight = _coerce_weight(entry.get("weight"))
        target = _operator_path(workspace, file_path)
        if target is None:
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", "operator path escapes workspace")
            continue
        if not class_name:
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", "missing class_name")
            continue
        if not target.is_file():
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", f"operator file not found: {file_path}")
            continue
        try:
            instance = _load_operator_instance(target, class_name, index)
        except Exception as exc:
            audit["operator_errors"] += 1
            _record_event(audit, name, "error", str(exc))
            continue
        if not hasattr(instance, "execute"):
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", "operator has no execute method")
            continue
        component = _operator_component(entry, instance)
        loaded.append(
            _LoadedOperator(
                name=name,
                weight=weight,
                instance=instance,
                order=index,
                component=component,
            )
        )

    loaded.sort(key=lambda op: (-op.weight, op.order))
    audit["operator_loaded"] = len(loaded)
    return tuple(loaded)


def _resolve_instance_path(instance_path: str) -> str:
    """Resolve formal-run case paths without copying benchmark data into workspaces."""

    path = Path(instance_path)
    if path.is_absolute() or path.exists():
        return str(path)

    for data_root in _configured_data_roots():
        candidate = data_root / path
        if candidate.exists():
            return str(candidate)
    return instance_path


def _find_vrp_baseline_root() -> Path | None:
    for candidate in _configured_data_roots():
        if (candidate / "src" / "solver.py").is_file():
            return candidate
    return None


def _baseline_required_for_instance(instance_path: Path) -> bool:
    for data_root in _configured_data_roots():
        try:
            instance_path.relative_to(data_root)
        except ValueError:
            continue
        return True
    return False


def _configured_data_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    for name in ("SCION_PROBLEM_DATA_ROOT", "SCION_CVRP_DATA_ROOT"):
        value = os.environ.get(name, "").strip()
        if value:
            roots.append(Path(value).expanduser().resolve(strict=False))
    return tuple(roots)


def _load_construction_policy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _construction_policy_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _CONSTRUCTION_POLICY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_construction_event(audit, "error", "construction policy path escapes workspace")
        audit["construction_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            f"construction policy load failed: {exc}",
        )
        return audit

    audit["construction_surface_loaded"] = True
    audit["construction_mode"] = _construction_mode(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["construction_bias"] = _construction_bias(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    return audit


def _construction_policy_defaults() -> dict[str, Any]:
    return {
        "construction_policy_path": _CONSTRUCTION_POLICY_RELATIVE_PATH,
        "construction_surface_loaded": False,
        "construction_errors": 0,
        "construction_events": [],
        "construction_mode": _DEFAULT_CONSTRUCTION_MODE,
        "construction_bias": _DEFAULT_CONSTRUCTION_BIAS,
    }


def _construct_with_policy_audit(
    *,
    instance: CvrpInstance,
    rng: random.Random,
    construction_policy: dict[str, Any] | None,
    algorithm_blueprint: dict[str, Any] | None = None,
    main_search_strategy: dict[str, Any] | None = None,
) -> tuple[CvrpSolution, dict[str, Any]]:
    audit = dict(construction_policy or {})
    if not audit:
        audit = {
            "construction_policy_path": _CONSTRUCTION_POLICY_RELATIVE_PATH,
            "construction_surface_loaded": False,
            "construction_errors": 0,
            "construction_events": [],
            "construction_mode": _DEFAULT_CONSTRUCTION_MODE,
            "construction_bias": _DEFAULT_CONSTRUCTION_BIAS,
        }
    audit.setdefault("construction_errors", 0)
    audit.setdefault("construction_events", [])
    audit.setdefault("construction_mode", _DEFAULT_CONSTRUCTION_MODE)
    audit.setdefault("construction_bias", _DEFAULT_CONSTRUCTION_BIAS)

    if _main_search_strategy_active(main_search_strategy):
        return _construct_with_main_search_strategy(
            instance=instance,
            rng=rng,
            construction_audit=audit,
            main_search_strategy=main_search_strategy or {},
        )

    if _algorithm_blueprint_active(algorithm_blueprint):
        return _construct_with_algorithm_blueprint(
            instance=instance,
            rng=rng,
            construction_audit=audit,
            algorithm_blueprint=algorithm_blueprint or {},
        )

    start_ns = time.monotonic_ns()
    try:
        solution = solve(
            instance,
            rng,
            construction_mode=str(audit["construction_mode"]),
            construction_bias=float(audit["construction_bias"]),
        )
    except Exception as exc:
        audit["construction_errors"] = _as_nonnegative_int(audit["construction_errors"]) + 1
        _record_construction_event(
            audit,
            "error",
            f"construction failed for mode={audit['construction_mode']!r}: {exc}",
        )
        if audit["construction_mode"] == _DEFAULT_CONSTRUCTION_MODE:
            raise
        solution = solve(instance, rng)

    audit["construction_elapsed_ms"] = int((time.monotonic_ns() - start_ns) / 1_000_000)
    audit["construction_routes"] = len(solution.routes)
    audit["construction_distance"] = sum(
        instance.route_distance(route) for route in solution.routes
    )
    feasible, reason = _solution_is_valid(CvrpAdapter(object()), instance, solution)
    audit["construction_feasible"] = feasible
    if not feasible:
        audit["construction_errors"] = _as_nonnegative_int(audit["construction_errors"]) + 1
        _record_construction_event(audit, "error", f"construction infeasible: {reason}")
    return solution, audit


def _construction_mode(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> str:
    try:
        value = _call_policy_function(module, "construction_mode", instance, time_limit_sec)
    except Exception as exc:
        audit["construction_errors"] += 1
        _record_construction_event(audit, "error", f"construction_mode failed: {exc}")
        return _DEFAULT_CONSTRUCTION_MODE
    if not isinstance(value, str):
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            f"construction_mode returned non-string value {value!r}",
        )
        return _DEFAULT_CONSTRUCTION_MODE
    mode = value.strip()
    if mode not in _ALLOWED_CONSTRUCTION_MODES:
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            f"construction_mode={mode!r} is not allowed",
        )
        return _DEFAULT_CONSTRUCTION_MODE
    return mode


def _construction_bias(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> float:
    try:
        value = _call_policy_function(module, "construction_bias", instance, time_limit_sec)
    except Exception as exc:
        audit["construction_errors"] += 1
        _record_construction_event(audit, "error", f"construction_bias failed: {exc}")
        return _DEFAULT_CONSTRUCTION_BIAS
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            f"construction_bias returned non-numeric value {value!r}",
        )
        return _DEFAULT_CONSTRUCTION_BIAS
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            f"construction_bias returned non-finite value {value!r}",
        )
        return _DEFAULT_CONSTRUCTION_BIAS
    clamped = min(max(numeric, _MIN_CONSTRUCTION_BIAS), _MAX_CONSTRUCTION_BIAS)
    if clamped != numeric:
        audit["construction_errors"] += 1
        _record_construction_event(
            audit,
            "error",
            "construction_bias="
            f"{numeric!r} outside [{_MIN_CONSTRUCTION_BIAS}, {_MAX_CONSTRUCTION_BIAS}], "
            "clamped",
        )
    return clamped


def _record_construction_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("construction_events", [])
    if len(events) >= 10:
        return
    events.append(
        {
            "policy": _CONSTRUCTION_POLICY_RELATIVE_PATH,
            "status": status,
            "detail": detail,
        }
    )


def _load_baseline_policy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _baseline_policy_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _BASELINE_POLICY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_baseline_policy_event(audit, "error", "baseline policy path escapes workspace")
        audit["baseline_policy_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(audit, "error", f"baseline policy load failed: {exc}")
        return audit

    audit["baseline_policy_loaded"] = True
    try:
        raw_params = _call_policy_function(
            module,
            "baseline_params",
            instance,
            time_limit_sec,
        )
    except Exception as exc:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(audit, "error", f"baseline_params failed: {exc}")
        return audit
    if not isinstance(raw_params, Mapping):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"baseline_params returned non-mapping value {raw_params!r}",
        )
        return audit

    _normalize_baseline_policy_params(dict(raw_params), audit=audit)
    return audit


def _baseline_policy_defaults() -> dict[str, Any]:
    params = dict(_DEFAULT_BASELINE_POLICY_PARAMS)
    return {
        "baseline_policy_path": _BASELINE_POLICY_RELATIVE_PATH,
        "baseline_policy_loaded": False,
        "baseline_policy_errors": 0,
        "baseline_policy_events": [],
        "baseline_policy_params": params,
        "baseline_destroy_ratio": list(params["destroy_ratio"]),
        "baseline_segment_length": params["segment_length"],
        "baseline_reaction_factor": params["reaction_factor"],
        "baseline_vns_max_no_improve": params["vns_max_no_improve"],
        "baseline_use_vns": params["use_vns"],
        "baseline_cw_threshold": params["cw_threshold"],
        "baseline_vns_threshold": params["vns_threshold"],
        "baseline_alns_threshold": params["alns_threshold"],
        "baseline_max_destroy_customers": params["max_destroy_customers"],
    }


def _normalize_baseline_policy_params(
    raw_params: dict[str, Any],
    *,
    audit: dict[str, Any],
) -> None:
    unknown = sorted(str(key) for key in raw_params if str(key) not in _BASELINE_POLICY_ALLOWED_KEYS)
    if unknown:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"baseline_params contains unknown keys {unknown}",
        )

    defaults = _DEFAULT_BASELINE_POLICY_PARAMS
    params = dict(defaults)
    params["destroy_ratio"] = _baseline_destroy_ratio(
        raw_params.get("destroy_ratio", defaults["destroy_ratio"]),
        audit=audit,
    )
    params["segment_length"] = _baseline_int(
        raw_params.get("segment_length", defaults["segment_length"]),
        minimum=1,
        maximum=1000,
        default=int(defaults["segment_length"]),
        field_name="segment_length",
        audit=audit,
    )
    params["reaction_factor"] = _baseline_float(
        raw_params.get("reaction_factor", defaults["reaction_factor"]),
        minimum=0.01,
        maximum=1.0,
        default=float(defaults["reaction_factor"]),
        field_name="reaction_factor",
        audit=audit,
    )
    params["vns_max_no_improve"] = _baseline_int(
        raw_params.get("vns_max_no_improve", defaults["vns_max_no_improve"]),
        minimum=0,
        maximum=20000,
        default=int(defaults["vns_max_no_improve"]),
        field_name="vns_max_no_improve",
        audit=audit,
    )
    params["use_vns"] = _baseline_bool(
        raw_params.get("use_vns", defaults["use_vns"]),
        default=bool(defaults["use_vns"]),
        field_name="use_vns",
        audit=audit,
    )
    params["cw_threshold"] = _baseline_int(
        raw_params.get("cw_threshold", defaults["cw_threshold"]),
        minimum=0,
        maximum=10000,
        default=int(defaults["cw_threshold"]),
        field_name="cw_threshold",
        audit=audit,
    )
    params["vns_threshold"] = _baseline_int(
        raw_params.get("vns_threshold", defaults["vns_threshold"]),
        minimum=0,
        maximum=10000,
        default=int(defaults["vns_threshold"]),
        field_name="vns_threshold",
        audit=audit,
    )
    params["alns_threshold"] = _baseline_int(
        raw_params.get("alns_threshold", defaults["alns_threshold"]),
        minimum=0,
        maximum=10000,
        default=int(defaults["alns_threshold"]),
        field_name="alns_threshold",
        audit=audit,
    )
    params["max_destroy_customers"] = _baseline_int(
        raw_params.get("max_destroy_customers", defaults["max_destroy_customers"]),
        minimum=1,
        maximum=500,
        default=int(defaults["max_destroy_customers"]),
        field_name="max_destroy_customers",
        audit=audit,
    )

    audit["baseline_policy_params"] = params
    audit["baseline_destroy_ratio"] = list(params["destroy_ratio"])
    audit["baseline_segment_length"] = params["segment_length"]
    audit["baseline_reaction_factor"] = params["reaction_factor"]
    audit["baseline_vns_max_no_improve"] = params["vns_max_no_improve"]
    audit["baseline_use_vns"] = params["use_vns"]
    audit["baseline_cw_threshold"] = params["cw_threshold"]
    audit["baseline_vns_threshold"] = params["vns_threshold"]
    audit["baseline_alns_threshold"] = params["alns_threshold"]
    audit["baseline_max_destroy_customers"] = params["max_destroy_customers"]


def _baseline_destroy_ratio(value: Any, *, audit: dict[str, Any]) -> tuple[float, float]:
    default = _DEFAULT_BASELINE_POLICY_PARAMS["destroy_ratio"]
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"destroy_ratio returned non-pair value {value!r}",
        )
        return default
    if len(value) != 2:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"destroy_ratio must contain exactly two values, got {value!r}",
        )
        return default
    low = _baseline_ratio_item(value[0], "destroy_ratio[0]", audit)
    high = _baseline_ratio_item(value[1], "destroy_ratio[1]", audit)
    if low is None or high is None:
        return default
    if low > high:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"destroy_ratio lower bound {low!r} exceeds upper bound {high!r}",
        )
        return default
    return (low, high)


def _baseline_ratio_item(value: Any, field_name: str, audit: dict[str, Any]) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name} returned non-numeric value {value!r}",
        )
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name} returned non-finite value {value!r}",
        )
        return None
    clamped = min(max(numeric, 0.01), 0.80)
    if clamped != numeric:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [0.01, 0.8], clamped",
        )
    return clamped


def _baseline_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    default: float,
    field_name: str,
    audit: dict[str, Any],
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name} returned non-numeric value {value!r}",
        )
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name} returned non-finite value {value!r}",
        )
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _baseline_int(
    value: Any,
    *,
    minimum: int,
    maximum: int,
    default: int,
    field_name: str,
    audit: dict[str, Any],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name} returned non-integer value {value!r}",
        )
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit["baseline_policy_errors"] += 1
        _record_baseline_policy_event(
            audit,
            "error",
            f"{field_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _baseline_bool(
    value: Any,
    *,
    default: bool,
    field_name: str,
    audit: dict[str, Any],
) -> bool:
    if isinstance(value, bool):
        return value
    audit["baseline_policy_errors"] += 1
    _record_baseline_policy_event(
        audit,
        "error",
        f"{field_name} returned non-bool value {value!r}",
    )
    return default


def _record_baseline_policy_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("baseline_policy_events", [])
    if len(events) >= 10:
        return
    events.append(
        {
            "policy": _BASELINE_POLICY_RELATIVE_PATH,
            "status": status,
            "detail": detail,
        }
    )


def _as_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _load_main_search_strategy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _main_search_strategy_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _MAIN_SEARCH_STRATEGY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_main_search_event(audit, "error", "main search strategy path escapes workspace")
        audit["main_search_strategy_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(audit, "error", f"main search strategy load failed: {exc}")
        return audit

    audit["main_search_strategy_loaded"] = True
    try:
        raw_plan = _call_policy_function(
            module,
            "main_search_plan",
            instance,
            time_limit_sec,
        )
    except Exception as exc:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(audit, "error", f"main_search_plan failed: {exc}")
        return audit
    if not isinstance(raw_plan, Mapping):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"main_search_plan returned non-mapping value {raw_plan!r}",
        )
        return audit

    _normalize_main_search_strategy_plan(dict(raw_plan), instance=instance, audit=audit)
    return audit


def _main_search_strategy_defaults() -> dict[str, Any]:
    params = dict(_DEFAULT_BASELINE_POLICY_PARAMS)
    return {
        "main_search_strategy_path": _MAIN_SEARCH_STRATEGY_RELATIVE_PATH,
        "main_search_strategy_loaded": False,
        "main_search_strategy_active": False,
        "main_search_strategy_errors": 0,
        "main_search_strategy_events": [],
        "main_search_plan": {
            "enabled": False,
            "problem_adaptation": {
                "strategy_family": _DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY,
                "instance_profile": {},
                "phase_objective": _DEFAULT_MAIN_SEARCH_PHASE_OBJECTIVE,
                "component_roles": {},
                "fallback_order": [],
                "evidence_targets": list(_DEFAULT_MAIN_SEARCH_EVIDENCE_TARGETS),
            },
            "algorithm_body": {
                "phase_sequence": list(_DEFAULT_MAIN_SEARCH_ALGORITHM_PHASES),
                "baseline_budget_policy": (
                    _DEFAULT_MAIN_SEARCH_BASELINE_BUDGET_POLICY
                ),
                "route_pool_activation": _DEFAULT_ROUTE_POOL_ACTIVATION,
                "route_pool_min_customers": _DEFAULT_ROUTE_POOL_MIN_CUSTOMERS,
                "route_pool_max_rounds": _MAX_MAIN_SEARCH_ROUNDS,
                "local_cleanup_after_recombination": False,
                "adaptive_component_budget": True,
            },
            "construction": {
                "methods": [_DEFAULT_CONSTRUCTION_MODE],
                "keep_top_k": 1,
                "bias": _DEFAULT_CONSTRUCTION_BIAS,
            },
            "baseline": {
                "time_fraction": _BASELINE_TIME_FRACTION,
                "params": {},
            },
            "improvement": {
                "enabled_components": [],
                "rounds": 0,
                "top_k": 16,
            },
            "acceptance": {
                "min_distance_improvement": 0.0,
                "component_min_distance_improvement": {},
                "bounded_destroy_repair_accept_limit": _MAIN_SEARCH_BDR_ACCEPT_LIMIT,
                "recovery_only_policy": "allow",
            },
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
                "schedule": _DEFAULT_MAIN_SEARCH_PERTURBATION_SCHEDULE,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        "main_search_phases": ["inactive"],
        "main_search_problem_adaptation": {
            "strategy_family": _DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY,
            "declared_instance_profile": {},
            "runtime_instance_profile": {},
            "phase_objective": _DEFAULT_MAIN_SEARCH_PHASE_OBJECTIVE,
            "component_roles": {},
            "fallback_order": [],
            "evidence_targets": list(_DEFAULT_MAIN_SEARCH_EVIDENCE_TARGETS),
            "source": "inactive_default",
        },
        "main_search_algorithm_body": {
            "phase_sequence": list(_DEFAULT_MAIN_SEARCH_ALGORITHM_PHASES),
            "baseline_budget_policy": _DEFAULT_MAIN_SEARCH_BASELINE_BUDGET_POLICY,
            "route_pool_activation": _DEFAULT_ROUTE_POOL_ACTIVATION,
            "route_pool_min_customers": _DEFAULT_ROUTE_POOL_MIN_CUSTOMERS,
            "route_pool_max_rounds": _MAX_MAIN_SEARCH_ROUNDS,
            "local_cleanup_after_recombination": False,
            "adaptive_component_budget": True,
        },
        "main_search_algorithm_body_source": "inactive_default",
        "main_search_strategy_family": _DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY,
        "main_search_declared_instance_profile": {},
        "main_search_instance_profile": {},
        "main_search_phase_objective": _DEFAULT_MAIN_SEARCH_PHASE_OBJECTIVE,
        "main_search_component_roles": {},
        "main_search_component_fallback_order": [],
        "main_search_evidence_targets": list(_DEFAULT_MAIN_SEARCH_EVIDENCE_TARGETS),
        "main_search_problem_adaptation_source": "inactive_default",
        "main_search_construction_methods": [_DEFAULT_CONSTRUCTION_MODE],
        "main_search_construction_keep_top_k": 1,
        "main_search_construction_bias": _DEFAULT_CONSTRUCTION_BIAS,
        "main_search_baseline_time_fraction": _BASELINE_TIME_FRACTION,
        "main_search_baseline_time_fraction_effective": _BASELINE_TIME_FRACTION,
        "main_search_baseline_budget_policy": (
            _DEFAULT_MAIN_SEARCH_BASELINE_BUDGET_POLICY
        ),
        "main_search_baseline_quality_guard_applied": False,
        "main_search_baseline_params": params,
        "main_search_baseline_params_clamped": False,
        "main_search_baseline_param_clamps": _main_search_baseline_clamp_evidence({}),
        "main_search_post_baseline_operators_enabled": False,
        "main_search_operator_round_limit": 0,
        "main_search_components": [],
        "main_search_component_order": [],
        "main_search_component_coverage_status": {
            "status": "inactive",
            "required_deep_components": sorted(
                _MAIN_SEARCH_DEEP_ATTRIBUTION_COMPONENTS
            ),
            "selected_deep_components": [],
            "missing_deep_components": sorted(
                _MAIN_SEARCH_DEEP_ATTRIBUTION_COMPONENTS
            ),
            "attempted_deep_components": [],
            "unattempted_deep_components": sorted(
                _MAIN_SEARCH_DEEP_ATTRIBUTION_COMPONENTS
            ),
        },
        "main_search_deep_components_selected": [],
        "main_search_rounds": 0,
        "main_search_top_k": 16,
        "main_search_selected_components": [],
        "main_search_attempted_components": [],
        "main_search_accepted_components": [],
        "main_search_skipped_components": [],
        "main_search_component_attempts": {},
        "main_search_component_accepted": {},
        "main_search_component_skip_reasons": {},
        "main_search_component_best_delta": {},
        "main_search_component_improvement_counts": {},
        "main_search_component_accepted_delta_sum": {},
        "main_search_component_accepted_best_delta": {},
        "main_search_component_accepted_positive_counts": {},
        "main_search_component_recovery_delta_sum": {},
        "main_search_component_recovery_best_delta": {},
        "main_search_component_recovery_counts": {},
        "main_search_component_phase_delta_sum": {},
        "main_search_component_phase_best_delta": {},
        "main_search_component_phase_improvement_counts": {},
        "main_search_component_removed_counts": {},
        "main_search_component_reinserted_counts": {},
        "main_search_component_repair_fallback_counts": {},
        "main_search_component_runtime_ms": {},
        "main_search_component_top_k_effective": {},
        "main_search_phase_component_order": {},
        "main_search_phase_unassigned_components": [],
        "main_search_construction_pool_size": 0,
        "main_search_construction_pool_distances": [],
        "main_search_route_pool_source_solutions": 0,
        "main_search_route_pool_sample_count": 0,
        "main_search_route_pool_size": 0,
        "main_search_route_pool_branch_calls": 0,
        "main_search_route_pool_recombined_routes": 0,
        "main_search_route_pool_auto_added": False,
        "main_search_route_pool_invocations": 0,
        "main_search_route_pool_activation": _DEFAULT_ROUTE_POOL_ACTIVATION,
        "main_search_route_pool_min_customers": _DEFAULT_ROUTE_POOL_MIN_CUSTOMERS,
        "main_search_route_pool_max_rounds": _MAX_MAIN_SEARCH_ROUNDS,
        "main_search_local_cleanup_after_recombination": False,
        "main_search_adaptive_component_budget": True,
        "main_search_acceptance_min_distance_improvement": 0.0,
        "recovery_only_policy": "allow",
        "main_search_component_min_distance_improvement": {},
        "main_search_bounded_destroy_repair_accept_limit": (
            _MAIN_SEARCH_BDR_ACCEPT_LIMIT
        ),
        "main_search_restart_enabled": False,
        "main_search_restart_stagnation_rounds": 0,
        "main_search_restart_count": 0,
        "main_search_perturbation_enabled": False,
        "main_search_perturbation_strength": 1,
        "main_search_perturbation_schedule": _DEFAULT_MAIN_SEARCH_PERTURBATION_SCHEDULE,
        "main_search_perturbation_count": 0,
        "main_search_objective_trace": {
            "status": "inactive",
            "phase_delta": 0.0,
            "accepted_but_zero_phase_delta": {},
        },
        "main_search_objective_delta_by_phase": {"inactive": 0.0},
        "main_search_phase_runtime_ms": {"inactive": 0},
        "main_search_elapsed_ms": 0,
        "main_search_best_returned": False,
        "main_search_stop_reason": "inactive",
    }


def _normalize_main_search_strategy_plan(
    plan: dict[str, Any],
    *,
    instance: CvrpInstance,
    audit: dict[str, Any],
) -> None:
    requested_active = _main_search_bool(
        plan.get("enabled", False),
        field_name="enabled",
        default=False,
        audit=audit,
    )
    _validate_main_search_plan_keys(plan, requested_active=requested_active, audit=audit)

    construction = _main_search_mapping_section(
        plan.get("construction", {}),
        field_name="construction",
        audit=audit,
    )
    baseline = _main_search_mapping_section(
        plan.get("baseline", {}),
        field_name="baseline",
        audit=audit,
    )
    improvement = _main_search_mapping_section(
        plan.get("improvement", {}),
        field_name="improvement",
        audit=audit,
    )
    acceptance = _main_search_mapping_section(
        plan.get("acceptance", {}),
        field_name="acceptance",
        audit=audit,
    )
    restart = _main_search_mapping_section(
        plan.get("restart", {}),
        field_name="restart",
        audit=audit,
    )
    perturbation = _main_search_mapping_section(
        plan.get("perturbation", {}),
        field_name="perturbation",
        audit=audit,
    )
    problem_adaptation = _main_search_mapping_section(
        plan.get("problem_adaptation", {}),
        field_name="problem_adaptation",
        audit=audit,
    )
    algorithm_body = _main_search_mapping_section(
        plan.get("algorithm_body", {}),
        field_name="algorithm_body",
        audit=audit,
    )
    strategy_family = _main_search_string_choice(
        problem_adaptation.get(
            "strategy_family",
            _DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY,
        ),
        allowed=_ALLOWED_MAIN_SEARCH_STRATEGY_FAMILIES,
        default=_DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY,
        field_name="problem_adaptation.strategy_family",
        audit=audit,
    )
    phase_objective = _main_search_string_choice(
        problem_adaptation.get(
            "phase_objective",
            _DEFAULT_MAIN_SEARCH_PHASE_OBJECTIVE,
        ),
        allowed=_ALLOWED_MAIN_SEARCH_PHASE_OBJECTIVES,
        default=_DEFAULT_MAIN_SEARCH_PHASE_OBJECTIVE,
        field_name="problem_adaptation.phase_objective",
        audit=audit,
    )
    declared_instance_profile = _main_search_declared_instance_profile(
        problem_adaptation.get("instance_profile", {}),
        audit=audit,
    )
    runtime_instance_profile = _main_search_instance_profile(instance)
    evidence_targets = _main_search_string_sequence(
        problem_adaptation.get(
            "evidence_targets",
            list(_DEFAULT_MAIN_SEARCH_EVIDENCE_TARGETS),
        ),
        allowed=_ALLOWED_MAIN_SEARCH_EVIDENCE_TARGETS,
        default=list(_DEFAULT_MAIN_SEARCH_EVIDENCE_TARGETS),
        max_items=len(_ALLOWED_MAIN_SEARCH_EVIDENCE_TARGETS),
        field_name="problem_adaptation.evidence_targets",
        audit=audit,
    )
    algorithm_phase_sequence = _main_search_string_sequence(
        algorithm_body.get(
            "phase_sequence",
            list(_DEFAULT_MAIN_SEARCH_ALGORITHM_PHASES),
        ),
        allowed=_ALLOWED_MAIN_SEARCH_ALGORITHM_PHASES,
        default=list(_DEFAULT_MAIN_SEARCH_ALGORITHM_PHASES),
        max_items=len(_ALLOWED_MAIN_SEARCH_ALGORITHM_PHASES),
        field_name="algorithm_body.phase_sequence",
        audit=audit,
        allow_empty=False,
    )
    baseline_budget_policy = _main_search_string_choice(
        algorithm_body.get(
            "baseline_budget_policy",
            _DEFAULT_MAIN_SEARCH_BASELINE_BUDGET_POLICY,
        ),
        allowed=_ALLOWED_MAIN_SEARCH_BASELINE_BUDGET_POLICIES,
        default=_DEFAULT_MAIN_SEARCH_BASELINE_BUDGET_POLICY,
        field_name="algorithm_body.baseline_budget_policy",
        audit=audit,
    )
    route_pool_activation = _main_search_string_choice(
        algorithm_body.get(
            "route_pool_activation",
            _DEFAULT_ROUTE_POOL_ACTIVATION,
        ),
        allowed=_ALLOWED_ROUTE_POOL_ACTIVATIONS,
        default=_DEFAULT_ROUTE_POOL_ACTIVATION,
        field_name="algorithm_body.route_pool_activation",
        audit=audit,
    )
    route_pool_min_customers = _main_search_int(
        algorithm_body.get(
            "route_pool_min_customers",
            _DEFAULT_ROUTE_POOL_MIN_CUSTOMERS,
        ),
        minimum=0,
        maximum=500,
        default=_DEFAULT_ROUTE_POOL_MIN_CUSTOMERS,
        field_name="algorithm_body.route_pool_min_customers",
        audit=audit,
    )
    route_pool_max_rounds = _main_search_int(
        algorithm_body.get("route_pool_max_rounds", _MAX_MAIN_SEARCH_ROUNDS),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_ROUNDS,
        default=_MAX_MAIN_SEARCH_ROUNDS,
        field_name="algorithm_body.route_pool_max_rounds",
        audit=audit,
    )
    local_cleanup_after_recombination = _main_search_bool(
        algorithm_body.get("local_cleanup_after_recombination", False),
        field_name="algorithm_body.local_cleanup_after_recombination",
        default=False,
        audit=audit,
    )
    adaptive_component_budget = _main_search_bool(
        algorithm_body.get("adaptive_component_budget", True),
        field_name="algorithm_body.adaptive_component_budget",
        default=True,
        audit=audit,
    )

    construction_methods = _main_search_string_sequence(
        construction.get("methods", [_DEFAULT_CONSTRUCTION_MODE]),
        allowed=_ALLOWED_CONSTRUCTION_MODES,
        default=[_DEFAULT_CONSTRUCTION_MODE],
        max_items=_MAX_MAIN_SEARCH_CONSTRUCTION_METHODS,
        field_name="construction.methods",
        audit=audit,
    )
    construction_keep_top_k = _main_search_int(
        construction.get("keep_top_k", 1),
        minimum=1,
        maximum=_MAX_MAIN_SEARCH_CONSTRUCTION_METHODS,
        default=1,
        field_name="construction.keep_top_k",
        audit=audit,
    )
    if (
        strategy_family == "construction_diversification"
        and len(construction_methods) > 1
    ):
        construction_keep_top_k = max(2, construction_keep_top_k)
    construction_bias = _main_search_float(
        construction.get("bias", _DEFAULT_CONSTRUCTION_BIAS),
        minimum=_MIN_CONSTRUCTION_BIAS,
        maximum=_MAX_CONSTRUCTION_BIAS,
        default=_DEFAULT_CONSTRUCTION_BIAS,
        field_name="construction.bias",
        audit=audit,
    )
    baseline_time_fraction = _main_search_float(
        baseline.get("time_fraction", _BASELINE_TIME_FRACTION),
        minimum=_MIN_BASELINE_TIME_FRACTION,
        maximum=_MAX_BASELINE_TIME_FRACTION,
        default=_BASELINE_TIME_FRACTION,
        field_name="baseline.time_fraction",
        audit=audit,
    )
    baseline_params = _main_search_baseline_params(
        baseline.get("params", {}),
        audit=audit,
    )
    if requested_active:
        baseline_params, baseline_param_clamps = _clamp_main_search_baseline_params(
            baseline_params,
            instance=instance,
        )
    else:
        baseline_param_clamps = {}
    if baseline_param_clamps:
        _record_main_search_event(
            audit,
            "info",
            f"baseline.params conservative clamp applied: {baseline_param_clamps}",
        )
    components = _main_search_string_sequence(
        improvement.get("enabled_components", []),
        allowed=_ALLOWED_MAIN_SEARCH_COMPONENTS,
        default=[],
        max_items=len(_ALLOWED_MAIN_SEARCH_COMPONENTS),
        field_name="improvement.enabled_components",
        audit=audit,
        allow_empty=not requested_active,
    )
    component_roles_raw = problem_adaptation.get("component_roles", {})
    route_pool_disabled = (
        isinstance(component_roles_raw, Mapping)
        and str(component_roles_raw.get("route_pool_recombination", "")).strip()
        == "disabled"
    )
    route_pool_auto_added = False
    if (
        requested_active
        and "route_pair_swap" in components
        and "bounded_destroy_repair" in components
        and "route_pool_recombination" not in components
        and not route_pool_disabled
    ):
        components.append("route_pool_recombination")
        _record_main_search_event(
            audit,
            "info",
            "route_pool_recombination auto-added for solver-level route-pair "
            "and bounded destroy/repair plan",
        )
        route_pool_auto_added = True
    component_roles = _main_search_component_roles(
        component_roles_raw,
        selected_components=components,
        audit=audit,
    )
    fallback_order = _main_search_string_sequence(
        problem_adaptation.get("fallback_order", []),
        allowed=_ALLOWED_MAIN_SEARCH_COMPONENTS,
        default=[],
        max_items=len(_ALLOWED_MAIN_SEARCH_COMPONENTS),
        field_name="problem_adaptation.fallback_order",
        audit=audit,
        allow_empty=True,
    )
    if route_pool_auto_added and "route_pool_recombination" not in fallback_order:
        fallback_order = ["route_pool_recombination", *fallback_order]
    components = _schedule_main_search_components(
        components,
        strategy_family=strategy_family,
        fallback_order=fallback_order,
        component_roles=component_roles,
    )
    effective_fallback_order = fallback_order or list(components)
    rounds = _main_search_int(
        improvement.get("rounds", 0),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_ROUNDS,
        default=0,
        field_name="improvement.rounds",
        audit=audit,
    )
    top_k = _main_search_int(
        improvement.get("top_k", 16),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_TOP_K,
        default=16,
        field_name="improvement.top_k",
        audit=audit,
    )
    if requested_active and rounds <= 0:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            "enabled main_search_plan requires improvement.rounds > 0",
        )
    if requested_active and top_k <= 0:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            "enabled main_search_plan requires improvement.top_k > 0",
        )

    min_distance_improvement = _main_search_float(
        acceptance.get("min_distance_improvement", 0.0),
        minimum=0.0,
        maximum=_MAX_MAIN_SEARCH_MIN_DISTANCE_IMPROVEMENT,
        default=0.0,
        field_name="acceptance.min_distance_improvement",
        audit=audit,
    )
    component_min_distance_improvement = _main_search_component_thresholds(
        components,
        acceptance.get("component_min_distance_improvement", {}),
        min_distance_improvement=min_distance_improvement,
        strategy_family=strategy_family,
        audit=audit,
    )
    recovery_only_policy = _main_search_string_choice(
        acceptance.get("recovery_only_policy", "allow"),
        allowed=_ACCEPTANCE_RECOVERY_POLICIES,
        default="allow",
        field_name="acceptance.recovery_only_policy",
        audit=audit,
    )
    bdr_accept_limit = _main_search_int(
        acceptance.get(
            "bounded_destroy_repair_accept_limit",
            _default_main_search_bdr_accept_limit(strategy_family),
        ),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_BDR_ACCEPT_LIMIT,
        default=_default_main_search_bdr_accept_limit(strategy_family),
        field_name="acceptance.bounded_destroy_repair_accept_limit",
        audit=audit,
    )
    restart_enabled = _main_search_bool(
        restart.get("enabled", False),
        field_name="restart.enabled",
        default=False,
        audit=audit,
    )
    restart_stagnation = _main_search_int(
        restart.get("stagnation_rounds", 0),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_RESTART_STAGNATION_ROUNDS,
        default=0,
        field_name="restart.stagnation_rounds",
        audit=audit,
    )
    max_restarts = _main_search_int(
        restart.get("max_restarts", 0),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_RESTARTS,
        default=0,
        field_name="restart.max_restarts",
        audit=audit,
    )
    perturbation_enabled = _main_search_bool(
        perturbation.get("enabled", False),
        field_name="perturbation.enabled",
        default=False,
        audit=audit,
    )
    perturbation_strength = _main_search_int(
        perturbation.get("strength", 1),
        minimum=1,
        maximum=_MAX_MAIN_SEARCH_PERTURBATION_STRENGTH,
        default=1,
        field_name="perturbation.strength",
        audit=audit,
    )
    max_perturbations = _main_search_int(
        perturbation.get("max_perturbations", 0),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_PERTURBATIONS,
        default=0,
        field_name="perturbation.max_perturbations",
        audit=audit,
    )
    perturbation_schedule = _main_search_string_choice(
        perturbation.get(
            "schedule",
            _DEFAULT_MAIN_SEARCH_PERTURBATION_SCHEDULE,
        ),
        allowed=_MAIN_SEARCH_PERTURBATION_SCHEDULES,
        default=_DEFAULT_MAIN_SEARCH_PERTURBATION_SCHEDULE,
        field_name="perturbation.schedule",
        audit=audit,
    )
    post_baseline_enabled = _main_search_bool(
        plan.get("post_baseline_operators_enabled", False),
        field_name="post_baseline_operators_enabled",
        default=False,
        audit=audit,
    )
    operator_round_limit = _main_search_int(
        plan.get("operator_round_limit", 0),
        minimum=0,
        maximum=_MAX_OPERATOR_ROUNDS,
        default=0,
        field_name="operator_round_limit",
        audit=audit,
    )
    active = requested_active and _as_nonnegative_int(
        audit["main_search_strategy_errors"]
    ) == 0

    normalized_plan = {
        "enabled": active,
        "problem_adaptation": {
            "strategy_family": strategy_family,
            "instance_profile": declared_instance_profile,
            "phase_objective": phase_objective,
            "component_roles": component_roles,
            "fallback_order": effective_fallback_order,
            "evidence_targets": evidence_targets,
        },
        "algorithm_body": {
            "phase_sequence": algorithm_phase_sequence,
            "baseline_budget_policy": baseline_budget_policy,
            "route_pool_activation": route_pool_activation,
            "route_pool_min_customers": route_pool_min_customers,
            "route_pool_max_rounds": route_pool_max_rounds,
            "local_cleanup_after_recombination": local_cleanup_after_recombination,
            "adaptive_component_budget": adaptive_component_budget,
        },
        "construction": {
            "methods": construction_methods,
            "keep_top_k": construction_keep_top_k,
            "bias": construction_bias,
        },
        "baseline": {
            "time_fraction": baseline_time_fraction,
            "params": baseline_params,
        },
        "improvement": {
            "enabled_components": components,
            "rounds": rounds,
            "top_k": top_k,
        },
        "acceptance": {
            "min_distance_improvement": min_distance_improvement,
            "component_min_distance_improvement": component_min_distance_improvement,
            "bounded_destroy_repair_accept_limit": bdr_accept_limit,
            "recovery_only_policy": recovery_only_policy,
        },
        "restart": {
            "enabled": restart_enabled,
            "stagnation_rounds": restart_stagnation,
            "max_restarts": max_restarts,
        },
        "perturbation": {
            "enabled": perturbation_enabled,
            "strength": perturbation_strength,
            "max_perturbations": max_perturbations,
            "schedule": perturbation_schedule,
        },
        "post_baseline_operators_enabled": post_baseline_enabled,
        "operator_round_limit": operator_round_limit,
    }
    audit["main_search_plan"] = normalized_plan
    audit["main_search_strategy_active"] = active
    adaptation_source = (
        "declared"
        if isinstance(plan.get("problem_adaptation"), Mapping)
        else "defaulted_missing_section"
    )
    audit["main_search_problem_adaptation"] = {
        "strategy_family": strategy_family,
        "declared_instance_profile": declared_instance_profile,
        "runtime_instance_profile": runtime_instance_profile,
        "phase_objective": phase_objective,
        "component_roles": component_roles,
        "fallback_order": effective_fallback_order,
        "evidence_targets": evidence_targets,
        "source": adaptation_source,
    }
    algorithm_body_source = (
        "declared"
        if isinstance(plan.get("algorithm_body"), Mapping)
        else "defaulted_missing_section"
    )
    audit["main_search_algorithm_body"] = normalized_plan["algorithm_body"]
    audit["main_search_algorithm_body_source"] = algorithm_body_source
    audit["main_search_strategy_family"] = strategy_family
    audit["main_search_declared_instance_profile"] = declared_instance_profile
    audit["main_search_instance_profile"] = runtime_instance_profile
    audit["main_search_phase_objective"] = phase_objective
    audit["main_search_component_roles"] = component_roles
    audit["main_search_component_fallback_order"] = effective_fallback_order
    audit["main_search_evidence_targets"] = evidence_targets
    audit["main_search_problem_adaptation_source"] = adaptation_source
    audit["main_search_construction_methods"] = construction_methods
    audit["main_search_construction_keep_top_k"] = construction_keep_top_k
    audit["main_search_construction_bias"] = construction_bias
    audit["main_search_baseline_time_fraction"] = baseline_time_fraction
    audit["main_search_baseline_time_fraction_effective"] = baseline_time_fraction
    audit["main_search_baseline_budget_policy"] = baseline_budget_policy
    audit["main_search_baseline_quality_guard_applied"] = False
    audit["main_search_baseline_params"] = baseline_params
    audit["main_search_baseline_params_clamped"] = bool(baseline_param_clamps)
    audit["main_search_baseline_param_clamps"] = (
        _main_search_baseline_clamp_evidence(baseline_param_clamps)
    )
    audit["main_search_post_baseline_operators_enabled"] = post_baseline_enabled
    audit["main_search_operator_round_limit"] = operator_round_limit
    audit["main_search_components"] = components
    audit["main_search_component_order"] = components
    audit["main_search_route_pool_auto_added"] = route_pool_auto_added
    audit["main_search_route_pool_invocations"] = 0
    audit["main_search_route_pool_activation"] = route_pool_activation
    audit["main_search_route_pool_min_customers"] = route_pool_min_customers
    audit["main_search_route_pool_max_rounds"] = route_pool_max_rounds
    audit["main_search_local_cleanup_after_recombination"] = (
        local_cleanup_after_recombination
    )
    audit["main_search_adaptive_component_budget"] = adaptive_component_budget
    _refresh_main_search_component_coverage_status(audit, components)
    audit["main_search_rounds"] = rounds
    audit["main_search_top_k"] = top_k
    audit["main_search_selected_components"] = list(components)
    audit["main_search_attempted_components"] = []
    audit["main_search_accepted_components"] = []
    audit["main_search_skipped_components"] = []
    audit["main_search_component_attempts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_accepted"] = {
        component: 0 for component in components
    }
    audit["main_search_component_skip_reasons"] = {
        component: {} for component in components
    }
    audit["main_search_component_best_delta"] = {
        component: 0.0 for component in components
    }
    audit["main_search_component_improvement_counts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_accepted_delta_sum"] = {
        component: 0.0 for component in components
    }
    audit["main_search_component_accepted_best_delta"] = {
        component: 0.0 for component in components
    }
    audit["main_search_component_accepted_positive_counts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_recovery_delta_sum"] = {
        component: 0.0 for component in components
    }
    audit["main_search_component_recovery_best_delta"] = {
        component: 0.0 for component in components
    }
    audit["main_search_component_recovery_counts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_phase_delta_sum"] = {
        component: 0.0 for component in components
    }
    audit["main_search_component_phase_best_delta"] = {
        component: 0.0 for component in components
    }
    audit["main_search_component_phase_improvement_counts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_removed_counts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_reinserted_counts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_repair_fallback_counts"] = {
        component: 0 for component in components
    }
    audit["main_search_component_runtime_ms"] = {
        component: 0 for component in components
    }
    audit["main_search_acceptance_min_distance_improvement"] = min_distance_improvement
    audit["recovery_only_policy"] = recovery_only_policy
    audit["main_search_component_min_distance_improvement"] = (
        component_min_distance_improvement
    )
    audit["main_search_bounded_destroy_repair_accept_limit"] = bdr_accept_limit
    audit["main_search_restart_enabled"] = restart_enabled
    audit["main_search_restart_stagnation_rounds"] = restart_stagnation
    audit["main_search_restart_count"] = 0
    audit["main_search_perturbation_enabled"] = perturbation_enabled
    audit["main_search_perturbation_strength"] = perturbation_strength
    audit["main_search_perturbation_schedule"] = perturbation_schedule
    audit["main_search_perturbation_count"] = 0
    if active:
        audit["main_search_phases"] = ["plan_loaded"]
        audit["main_search_objective_delta_by_phase"] = {"plan_loaded": 0.0}
        audit["main_search_objective_trace"] = {
            "status": "plan_loaded",
            "phase_delta": 0.0,
            "accepted_but_zero_phase_delta": {},
        }
        audit["main_search_phase_runtime_ms"] = {"plan_loaded": 0}
        audit["main_search_best_returned"] = False
        audit["main_search_stop_reason"] = "plan_loaded"
    elif requested_active:
        audit["main_search_phases"] = ["plan_invalid"]
        audit["main_search_objective_delta_by_phase"] = {"plan_invalid": 0.0}
        audit["main_search_objective_trace"] = {
            "status": "plan_invalid",
            "phase_delta": 0.0,
            "accepted_but_zero_phase_delta": {},
        }
        audit["main_search_phase_runtime_ms"] = {"plan_invalid": 0}
        audit["main_search_best_returned"] = False
        audit["main_search_stop_reason"] = "invalid_plan"


def _validate_main_search_plan_keys(
    plan: Mapping[str, Any],
    *,
    requested_active: bool,
    audit: dict[str, Any],
) -> None:
    _validate_main_search_section_keys(
        plan,
        allowed=_MAIN_SEARCH_STRATEGY_ALLOWED_KEYS,
        required=_MAIN_SEARCH_STRATEGY_REQUIRED_KEYS,
        requested_active=requested_active,
        field_name="main_search_plan",
        audit=audit,
    )
    section_specs = {
        "construction": _MAIN_SEARCH_CONSTRUCTION_REQUIRED_KEYS,
        "baseline": _MAIN_SEARCH_BASELINE_REQUIRED_KEYS,
        "improvement": _MAIN_SEARCH_IMPROVEMENT_REQUIRED_KEYS,
        "acceptance": (
            _MAIN_SEARCH_ACCEPTANCE_ALLOWED_KEYS,
            _MAIN_SEARCH_ACCEPTANCE_REQUIRED_KEYS,
        ),
        "restart": _MAIN_SEARCH_RESTART_REQUIRED_KEYS,
        "perturbation": (
            _MAIN_SEARCH_PERTURBATION_ALLOWED_KEYS,
            _MAIN_SEARCH_PERTURBATION_REQUIRED_KEYS,
        ),
        "problem_adaptation": (
            _MAIN_SEARCH_PROBLEM_ADAPTATION_ALLOWED_KEYS,
            frozenset(),
        ),
        "algorithm_body": (
            _MAIN_SEARCH_ALGORITHM_BODY_ALLOWED_KEYS,
            frozenset(),
        ),
    }
    for section_name, spec in section_specs.items():
        if isinstance(spec, tuple):
            allowed, required = spec
        else:
            allowed = required = spec
        section = plan.get(section_name)
        if isinstance(section, Mapping):
            _validate_main_search_section_keys(
                section,
                allowed=allowed,
                required=required,
                requested_active=requested_active,
                field_name=section_name,
                audit=audit,
            )


def _validate_main_search_section_keys(
    section: Mapping[str, Any],
    *,
    allowed: frozenset[str],
    required: frozenset[str],
    requested_active: bool,
    field_name: str,
    audit: dict[str, Any],
) -> None:
    unknown = sorted(str(key) for key in section if str(key) not in allowed)
    if unknown:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} contains unknown keys {unknown}",
        )
    if requested_active:
        missing = sorted(key for key in required if key not in section)
        if missing:
            audit["main_search_strategy_errors"] += 1
            _record_main_search_event(
                audit,
                "error",
                f"enabled {field_name} missing required keys {missing}",
            )


def _main_search_mapping_section(
    value: Any,
    *,
    field_name: str,
    audit: dict[str, Any],
) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    audit["main_search_strategy_errors"] += 1
    _record_main_search_event(
        audit,
        "error",
        f"{field_name} returned non-mapping value {value!r}",
    )
    return {}


def _main_search_baseline_params(
    value: Any,
    *,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"baseline.params returned non-mapping value {value!r}",
        )
        return dict(_DEFAULT_BASELINE_POLICY_PARAMS)
    baseline_audit = _baseline_policy_defaults()
    _normalize_baseline_policy_params(dict(value), audit=baseline_audit)
    for event in baseline_audit.get("baseline_policy_events", []):
        if isinstance(event, Mapping):
            detail = event.get("detail")
            if detail:
                _record_main_search_event(
                    audit,
                    "error",
                    f"baseline.params invalid: {detail}",
                )
    audit["main_search_strategy_errors"] += _as_nonnegative_int(
        baseline_audit.get("baseline_policy_errors")
    )
    params = baseline_audit.get("baseline_policy_params")
    if not isinstance(params, Mapping):
        return dict(_DEFAULT_BASELINE_POLICY_PARAMS)
    return dict(params)


def _clamp_main_search_baseline_params(
    params: Mapping[str, Any],
    *,
    instance: CvrpInstance,
) -> tuple[dict[str, Any], dict[str, Any]]:
    clamped = dict(params)
    changes: dict[str, Any] = {}

    destroy_ratio = clamped.get("destroy_ratio")
    if isinstance(destroy_ratio, (list, tuple)) and len(destroy_ratio) == 2:
        low = float(destroy_ratio[0])
        high = min(float(destroy_ratio[1]), 0.35)
        if high < low:
            high = low
        if (low, high) != (float(destroy_ratio[0]), float(destroy_ratio[1])):
            changes["destroy_ratio"] = {
                "requested": tuple(destroy_ratio),
                "effective": (low, high),
            }
        clamped["destroy_ratio"] = (low, high)

    segment_length = int(clamped.get("segment_length", 100))
    if segment_length > 200:
        changes["segment_length"] = {
            "requested": segment_length,
            "effective": 200,
        }
        clamped["segment_length"] = 200

    reaction_factor = float(clamped.get("reaction_factor", 0.1))
    if reaction_factor < 0.08:
        changes["reaction_factor"] = {
            "requested": reaction_factor,
            "effective": 0.08,
        }
        clamped["reaction_factor"] = 0.08

    vns_max_no_improve = int(clamped.get("vns_max_no_improve", 5000))
    if vns_max_no_improve > 7000:
        changes["vns_max_no_improve"] = {
            "requested": vns_max_no_improve,
            "effective": 7000,
        }
        clamped["vns_max_no_improve"] = 7000

    adaptive_destroy_cap = max(
        _MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_FLOOR,
        min(
            _MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_CEILING,
            int(
                math.ceil(
                    max(1, instance.customer_count)
                    * _MAIN_SEARCH_BASELINE_MAX_DESTROY_CUSTOMERS_FRACTION
                )
            ),
        ),
    )
    max_destroy_customers = int(clamped.get("max_destroy_customers", adaptive_destroy_cap))
    if max_destroy_customers > adaptive_destroy_cap:
        changes["max_destroy_customers"] = {
            "requested": max_destroy_customers,
            "effective": adaptive_destroy_cap,
        }
        clamped["max_destroy_customers"] = adaptive_destroy_cap

    return clamped, changes


def _main_search_baseline_clamp_evidence(
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    fields = sorted(str(field) for field in changes)
    return {
        "applied": bool(fields),
        "status": "clamped" if fields else "no_clamps",
        "count": len(fields),
        "fields": fields,
        "clamps": _json_safe_runtime_value(dict(changes)),
    }


def _json_safe_runtime_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe_runtime_value(nested)
            for key, nested in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe_runtime_value(nested) for nested in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _main_search_instance_profile(instance: CvrpInstance) -> dict[str, Any]:
    demands = [instance.demand(customer) for customer in instance.customer_ids]
    total_demand = sum(demands)
    mean_demand = float(total_demand) / max(1, len(demands))
    max_demand = max(demands, default=0)
    route_count_hint = int(math.ceil(float(total_demand) / max(1, instance.capacity)))
    customer_count = int(instance.customer_count)
    if customer_count <= 50:
        scale = "small"
    elif customer_count <= 120:
        scale = "medium"
    else:
        scale = "large"
    max_demand_fraction = float(max_demand) / max(1.0, float(instance.capacity))
    if max_demand_fraction >= 0.5:
        demand_skew = "high"
    elif max_demand_fraction >= 0.25:
        demand_skew = "medium"
    else:
        demand_skew = "low"
    route_pressure = "low"
    if route_count_hint >= max(2, customer_count // 8):
        route_pressure = "high"
    elif route_count_hint >= max(2, customer_count // 16):
        route_pressure = "medium"
    return {
        "customer_count": customer_count,
        "capacity": int(instance.capacity),
        "total_demand": int(total_demand),
        "mean_demand": round(mean_demand, 6),
        "max_demand": int(max_demand),
        "max_demand_fraction": round(max_demand_fraction, 6),
        "route_count_hint": route_count_hint,
        "scale": scale,
        "route_pressure": route_pressure,
        "demand_skew": demand_skew,
    }


def _main_search_declared_instance_profile(
    value: Any,
    *,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"problem_adaptation.instance_profile returned non-mapping value {value!r}",
        )
        return {}
    unknown = sorted(
        str(key)
        for key in value
        if str(key) not in _MAIN_SEARCH_ADAPTATION_PROFILE_KEYS
    )
    if unknown:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"problem_adaptation.instance_profile contains unknown keys {unknown}",
        )
    profile: dict[str, Any] = {}
    for key, raw in value.items():
        text_key = str(key)
        if text_key not in _MAIN_SEARCH_ADAPTATION_PROFILE_KEYS:
            continue
        safe = _json_safe_runtime_value(raw)
        if isinstance(safe, (str, int, float, bool)) or safe is None:
            profile[text_key] = safe
        else:
            profile[text_key] = str(safe)
    if not profile:
        profile["scale"] = "unspecified"
    return profile


def _main_search_component_roles(
    value: Any,
    *,
    selected_components: list[str],
    audit: dict[str, Any],
) -> dict[str, str]:
    if not isinstance(value, Mapping):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"problem_adaptation.component_roles returned non-mapping value {value!r}",
        )
        value = {}
    roles: dict[str, str] = {}
    selected = set(selected_components)
    for key, raw_role in value.items():
        component = str(key).strip()
        role = str(raw_role).strip()
        if component not in _ALLOWED_MAIN_SEARCH_ROLE_TARGETS:
            audit["main_search_strategy_errors"] += 1
            _record_main_search_event(
                audit,
                "error",
                "problem_adaptation.component_roles contains unknown role target "
                f"{component!r}",
            )
            continue
        if role not in _ALLOWED_MAIN_SEARCH_COMPONENT_ROLES:
            audit["main_search_strategy_errors"] += 1
            _record_main_search_event(
                audit,
                "error",
                f"problem_adaptation.component_roles contains unknown role {role!r}",
            )
            continue
        if component in selected and role == "disabled":
            audit["main_search_strategy_errors"] += 1
            _record_main_search_event(
                audit,
                "error",
                f"selected component {component!r} cannot have disabled role",
            )
            continue
        roles[component] = role
    for component in selected_components:
        roles.setdefault(component, "support")
    return roles


def _default_main_search_bdr_accept_limit(strategy_family: str) -> int:
    if strategy_family == "destroy_repair_recovery":
        return 2
    return _MAIN_SEARCH_BDR_ACCEPT_LIMIT


def _main_search_component_thresholds(
    components: list[str],
    value: Any,
    *,
    min_distance_improvement: float,
    strategy_family: str,
    audit: dict[str, Any],
) -> dict[str, float]:
    if not isinstance(value, Mapping):
        if value not in ({}, None):
            audit["main_search_strategy_errors"] += 1
            _record_main_search_event(
                audit,
                "error",
                "acceptance.component_min_distance_improvement returned "
                f"non-mapping value {value!r}",
            )
        value = {}
    unknown = sorted(
        str(key)
        for key in value
        if str(key) not in _ALLOWED_MAIN_SEARCH_COMPONENTS
    )
    if unknown:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"acceptance.component_min_distance_improvement contains unknown keys {unknown}",
        )
    thresholds: dict[str, float] = {}
    for component in components:
        default_threshold = _main_search_component_min_distance_improvement(
            component,
            min_distance_improvement,
            strategy_family=strategy_family,
        )
        if component in value:
            threshold = _main_search_float(
                value.get(component),
                minimum=0.0,
                maximum=_MAX_MAIN_SEARCH_MIN_DISTANCE_IMPROVEMENT,
                default=default_threshold,
                field_name=f"acceptance.component_min_distance_improvement.{component}",
                audit=audit,
            )
        else:
            threshold = default_threshold
        thresholds[component] = threshold
    return thresholds


def _schedule_main_search_components(
    components: list[str],
    *,
    strategy_family: str = _DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY,
    fallback_order: list[str] | None = None,
    component_roles: Mapping[str, str] | None = None,
) -> list[str]:
    components = [component for component in dict.fromkeys(components)]
    fallback_order = fallback_order or []
    component_roles = component_roles or {}
    if not fallback_order and strategy_family == _DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY:
        if not (
            "route_pair_swap" in components
            and "bounded_destroy_repair" in components
        ):
            return components
        legacy_priority = {"route_pair_swap": 0, "bounded_destroy_repair": 1}
        return sorted(
            components,
            key=lambda component: (
                legacy_priority.get(component, -1),
                components.index(component),
            ),
        )
    family_priorities = {
        "balanced_lifecycle": {
            "intra_route_2opt": 0,
            "inter_route_relocate": 1,
            "route_pair_swap": 2,
            "bounded_destroy_repair": 3,
            "route_pool_recombination": 4,
        },
        "baseline_intensification": {
            "route_pool_recombination": 0,
            "route_pair_swap": 1,
            "bounded_destroy_repair": 2,
            "inter_route_relocate": 3,
            "intra_route_2opt": 4,
        },
        "construction_diversification": {
            "intra_route_2opt": 0,
            "inter_route_relocate": 1,
            "route_pair_swap": 2,
            "bounded_destroy_repair": 3,
            "route_pool_recombination": 4,
        },
        "improvement_intensification": {
            "intra_route_2opt": 0,
            "inter_route_relocate": 1,
            "route_pair_swap": 2,
            "bounded_destroy_repair": 3,
            "route_pool_recombination": 4,
        },
        "destroy_repair_recovery": {
            "bounded_destroy_repair": 0,
            "inter_route_relocate": 1,
            "route_pair_swap": 2,
            "route_pool_recombination": 3,
            "intra_route_2opt": 4,
        },
        "route_structure_repair": {
            "route_pair_swap": 0,
            "inter_route_relocate": 1,
            "route_pool_recombination": 2,
            "bounded_destroy_repair": 3,
            "intra_route_2opt": 4,
        },
        "local_search_cleanup": {
            "intra_route_2opt": 0,
            "inter_route_relocate": 1,
            "route_pair_swap": 2,
            "bounded_destroy_repair": 3,
            "route_pool_recombination": 4,
        },
    }
    priority = family_priorities.get(
        strategy_family,
        family_priorities[_DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY],
    )
    role_priority = {"primary": 0, "support": 1, "probe": 2, "disabled": 3}
    fallback_position = {
        component: index for index, component in enumerate(fallback_order)
    }
    return sorted(
        components,
        key=lambda component: (
            fallback_position.get(component, len(fallback_position) + 1),
            role_priority.get(str(component_roles.get(component, "support")), 1),
            priority.get(component, 99),
            components.index(component),
        ),
    )


_MAIN_SEARCH_COMPONENT_EXECUTION_PHASES = {
    "route_pool_recombination": ("global_recombination",),
    "route_pair_swap": ("route_structure_repair",),
    "bounded_destroy_repair": ("route_structure_repair",),
    "inter_route_relocate": ("route_structure_repair", "local_cleanup"),
    "intra_route_2opt": ("local_cleanup",),
}


def _main_search_phase_component_order(
    audit: Mapping[str, Any],
    components: list[str],
) -> dict[str, list[str]]:
    algorithm_body = audit.get("main_search_algorithm_body")
    if not isinstance(algorithm_body, Mapping):
        algorithm_body = {}
    raw_phases = algorithm_body.get(
        "phase_sequence",
        _DEFAULT_MAIN_SEARCH_ALGORITHM_PHASES,
    )
    phases = [
        str(phase)
        for phase in raw_phases
        if str(phase)
        in {"global_recombination", "route_structure_repair", "local_cleanup"}
    ]
    order: dict[str, list[str]] = {phase: [] for phase in phases}
    for component in components:
        allowed = _MAIN_SEARCH_COMPONENT_EXECUTION_PHASES.get(component, ())
        target_phase = next((phase for phase in phases if phase in allowed), None)
        if target_phase is not None:
            order.setdefault(target_phase, []).append(component)
    return {
        phase: phase_components
        for phase, phase_components in order.items()
        if phase_components
    }


def _main_search_effective_component_top_k(
    audit: Mapping[str, Any],
    component: str,
    requested_top_k: int,
    instance: CvrpInstance,
) -> int:
    top_k = max(1, _as_nonnegative_int(requested_top_k))
    if not bool(audit.get("main_search_adaptive_component_budget")):
        return top_k
    customer_count = len(instance.customer_ids)
    if component == "route_pool_recombination":
        if customer_count < 60:
            return min(top_k, 24)
        if customer_count < 120:
            return min(top_k, 48)
        return min(top_k, 96)
    if component in {"intra_route_2opt", "inter_route_relocate"}:
        return min(top_k, 48)
    return top_k


def _record_main_search_effective_top_k(
    audit: dict[str, Any],
    component: str,
    top_k: int,
) -> None:
    values = audit.setdefault("main_search_component_top_k_effective", {})
    values[component] = max(
        _as_nonnegative_int(values.get(component)),
        _as_nonnegative_int(top_k),
    )


def _apply_main_search_strategy_search_policy(
    search_policy: dict[str, Any],
    *,
    main_search_strategy: dict[str, Any],
) -> None:
    if not _main_search_strategy_active(main_search_strategy):
        return
    search_policy["baseline_time_fraction"] = main_search_strategy[
        "main_search_baseline_time_fraction"
    ]
    search_policy["operator_round_limit"] = main_search_strategy[
        "main_search_operator_round_limit"
    ]
    search_policy["post_baseline_operators_enabled"] = main_search_strategy[
        "main_search_post_baseline_operators_enabled"
    ]


def _apply_main_search_strategy_baseline_policy(
    baseline_policy: dict[str, Any],
    *,
    main_search_strategy: dict[str, Any],
) -> None:
    if not _main_search_strategy_active(main_search_strategy):
        return
    params = dict(main_search_strategy.get("main_search_baseline_params") or {})
    baseline_policy["baseline_policy_params"] = params
    baseline_policy["baseline_destroy_ratio"] = list(params["destroy_ratio"])
    baseline_policy["baseline_segment_length"] = params["segment_length"]
    baseline_policy["baseline_reaction_factor"] = params["reaction_factor"]
    baseline_policy["baseline_vns_max_no_improve"] = params["vns_max_no_improve"]
    baseline_policy["baseline_use_vns"] = params["use_vns"]
    baseline_policy["baseline_cw_threshold"] = params["cw_threshold"]
    baseline_policy["baseline_vns_threshold"] = params["vns_threshold"]
    baseline_policy["baseline_alns_threshold"] = params["alns_threshold"]
    baseline_policy["baseline_max_destroy_customers"] = params["max_destroy_customers"]


def _main_search_strategy_active(main_search_strategy: Mapping[str, Any] | None) -> bool:
    return bool(
        main_search_strategy
        and main_search_strategy.get("main_search_strategy_active")
    )


def _activate_main_search_strategy_for_mechanism_policies(
    main_search_strategy: dict[str, Any],
    *,
    instance: CvrpInstance,
    destroy_repair_policy: Mapping[str, Any] | None,
    route_pair_policy: Mapping[str, Any] | None,
    acceptance_restart_policy: Mapping[str, Any] | None,
) -> None:
    if _main_search_strategy_active(main_search_strategy):
        return
    if _as_nonnegative_int(main_search_strategy.get("main_search_strategy_errors")):
        return

    active_mechanisms: list[str] = []
    components: list[str] = []
    if route_pair_policy and route_pair_policy.get("route_pair_active"):
        active_mechanisms.append("route_pair_candidate_policy")
        components.append("route_pair_swap")
    if destroy_repair_policy and destroy_repair_policy.get("destroy_repair_active"):
        active_mechanisms.append("destroy_repair_policy")
        components.append("bounded_destroy_repair")
    if (
        acceptance_restart_policy
        and acceptance_restart_policy.get("acceptance_restart_active")
    ):
        active_mechanisms.append("acceptance_restart_policy")
        components.extend(["route_pair_swap", "bounded_destroy_repair"])
    if not active_mechanisms:
        return

    components = _schedule_main_search_components(
        [component for component in dict.fromkeys(components)]
    )
    _normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": {
                "phase_sequence": list(_DEFAULT_MAIN_SEARCH_ALGORITHM_PHASES),
                "baseline_budget_policy": (
                    _DEFAULT_MAIN_SEARCH_BASELINE_BUDGET_POLICY
                ),
                "route_pool_activation": _DEFAULT_ROUTE_POOL_ACTIVATION,
                "route_pool_min_customers": _DEFAULT_ROUTE_POOL_MIN_CUSTOMERS,
                "route_pool_max_rounds": _MAX_MAIN_SEARCH_ROUNDS,
                "local_cleanup_after_recombination": False,
                "adaptive_component_budget": True,
            },
            "problem_adaptation": {
                "strategy_family": "route_structure_repair",
                "instance_profile": {},
                "phase_objective": "phase_best_distance",
                "component_roles": {
                    component: "primary" for component in components
                },
                "fallback_order": components,
                "evidence_targets": list(_DEFAULT_MAIN_SEARCH_EVIDENCE_TARGETS),
            },
            "construction": {
                "methods": [_DEFAULT_CONSTRUCTION_MODE],
                "keep_top_k": 1,
                "bias": _DEFAULT_CONSTRUCTION_BIAS,
            },
            "baseline": {
                "time_fraction": _MAIN_SEARCH_FORMAL_BASELINE_TIME_FLOOR,
                "params": {},
            },
            "improvement": {
                "enabled_components": components,
                "rounds": 5,
                "top_k": 64,
            },
            "acceptance": {
                "min_distance_improvement": 0.0,
                "component_min_distance_improvement": {},
                "bounded_destroy_repair_accept_limit": _MAIN_SEARCH_BDR_ACCEPT_LIMIT,
                "recovery_only_policy": "allow",
            },
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
                "schedule": _DEFAULT_MAIN_SEARCH_PERTURBATION_SCHEDULE,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=main_search_strategy,
    )
    _record_main_search_event(
        main_search_strategy,
        "info",
        (
            "default mechanism-surface main search activated for "
            f"{active_mechanisms}"
        ),
    )


def _main_search_bool(
    value: Any,
    *,
    field_name: str,
    default: bool,
    audit: dict[str, Any],
) -> bool:
    if isinstance(value, bool):
        return value
    audit["main_search_strategy_errors"] += 1
    _record_main_search_event(
        audit,
        "error",
        f"{field_name} returned non-bool value {value!r}",
    )
    return default


def _main_search_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    default: float,
    field_name: str,
    audit: dict[str, Any],
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} returned non-numeric value {value!r}",
        )
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} returned non-finite value {value!r}",
        )
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _main_search_int(
    value: Any,
    *,
    minimum: int,
    maximum: int,
    default: int,
    field_name: str,
    audit: dict[str, Any],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} returned non-integer value {value!r}",
        )
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _main_search_string_sequence(
    value: Any,
    *,
    allowed: frozenset[str],
    default: list[str],
    max_items: int,
    field_name: str,
    audit: dict[str, Any],
    allow_empty: bool = False,
) -> list[str]:
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} returned non-sequence value {value!r}",
        )
        return list(default)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if text not in allowed:
            audit["main_search_strategy_errors"] += 1
            _record_main_search_event(
                audit,
                "error",
                f"{field_name} contains unknown value {text!r}",
            )
            continue
        if text not in seen:
            seen.add(text)
            normalized.append(text)
        if len(normalized) >= max_items:
            break
    if not normalized and not allow_empty:
        audit["main_search_strategy_errors"] += 1
        _record_main_search_event(
            audit,
            "error",
            f"{field_name} produced no valid values",
        )
        return list(default)
    return normalized


def _main_search_string_choice(
    value: Any,
    *,
    allowed: frozenset[str],
    default: str,
    field_name: str,
    audit: dict[str, Any],
) -> str:
    text = str(value).strip() if value is not None else ""
    if text in allowed:
        return text
    audit["main_search_strategy_errors"] += 1
    _record_main_search_event(
        audit,
        "error",
        f"{field_name} contains unknown value {text!r}",
    )
    return default


def _record_main_search_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("main_search_strategy_events", [])
    if len(events) >= 10:
        return
    events.append(
        {
            "policy": _MAIN_SEARCH_STRATEGY_RELATIVE_PATH,
            "status": status,
            "detail": detail,
        }
    )


def _load_algorithm_blueprint(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _algorithm_blueprint_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _ALGORITHM_BLUEPRINT_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_algorithm_event(audit, "error", "algorithm blueprint path escapes workspace")
        audit["algorithm_blueprint_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(audit, "error", f"algorithm blueprint load failed: {exc}")
        return audit

    audit["algorithm_blueprint_loaded"] = True
    try:
        raw_plan = _call_policy_function(
            module,
            "algorithm_plan",
            instance,
            time_limit_sec,
        )
    except Exception as exc:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(audit, "error", f"algorithm_plan failed: {exc}")
        return audit
    if not isinstance(raw_plan, Mapping):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"algorithm_plan returned non-mapping value {raw_plan!r}",
        )
        return audit

    _normalize_algorithm_blueprint_plan(dict(raw_plan), audit=audit)
    return audit


def _algorithm_blueprint_defaults() -> dict[str, Any]:
    return {
        "algorithm_blueprint_path": _ALGORITHM_BLUEPRINT_RELATIVE_PATH,
        "algorithm_blueprint_loaded": False,
        "algorithm_blueprint_active": False,
        "algorithm_blueprint_errors": 0,
        "algorithm_blueprint_events": [],
        "algorithm_plan": {
            "enabled": False,
            "construction_methods": [_DEFAULT_CONSTRUCTION_MODE],
            "construction_keep_top_k": 1,
            "construction_bias": _DEFAULT_CONSTRUCTION_BIAS,
            "baseline_time_fraction": _BASELINE_TIME_FRACTION,
            "operator_round_limit": _MAX_OPERATOR_ROUNDS,
            "post_baseline_operators_enabled": True,
            "local_search": {
                "enabled_components": [],
                "rounds": 0,
                "top_k": 16,
            },
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
            },
        },
        "algorithm_phases_executed": ["inactive"],
        "algorithm_construction_methods": [_DEFAULT_CONSTRUCTION_MODE],
        "algorithm_construction_keep_top_k": 1,
        "algorithm_baseline_time_fraction": _BASELINE_TIME_FRACTION,
        "algorithm_operator_round_limit": _MAX_OPERATOR_ROUNDS,
        "algorithm_post_baseline_operators_enabled": True,
        "algorithm_local_search_components": [],
        "algorithm_local_search_rounds": 0,
        "algorithm_local_search_top_k": 16,
        "algorithm_local_search_attempts": 0,
        "algorithm_local_search_accepted": 0,
        "algorithm_restart_enabled": False,
        "algorithm_restart_stagnation_rounds": 0,
        "algorithm_restart_count": 0,
        "algorithm_best_delta_by_phase": {"inactive": 0.0},
        "algorithm_phase_runtime_ms": {"inactive": 0},
        "algorithm_stop_reason": "inactive",
    }


def _normalize_algorithm_blueprint_plan(
    plan: dict[str, Any],
    *,
    audit: dict[str, Any],
) -> None:
    requested_active = _algorithm_bool(
        plan.get("enabled", False),
        field_name="enabled",
        default=False,
        audit=audit,
    )
    _validate_algorithm_plan_keys(
        plan,
        requested_active=requested_active,
        audit=audit,
    )
    construction_methods = _algorithm_string_sequence(
        plan.get("construction_methods", [_DEFAULT_CONSTRUCTION_MODE]),
        allowed=_ALLOWED_CONSTRUCTION_MODES,
        default=[_DEFAULT_CONSTRUCTION_MODE],
        max_items=_MAX_BLUEPRINT_CONSTRUCTION_METHODS,
        field_name="construction_methods",
        audit=audit,
    )
    construction_keep_top_k = _algorithm_int(
        plan.get("construction_keep_top_k", 1),
        minimum=1,
        maximum=_MAX_BLUEPRINT_CONSTRUCTION_METHODS,
        default=1,
        field_name="construction_keep_top_k",
        audit=audit,
    )
    construction_bias = _algorithm_float(
        plan.get("construction_bias", _DEFAULT_CONSTRUCTION_BIAS),
        minimum=_MIN_CONSTRUCTION_BIAS,
        maximum=_MAX_CONSTRUCTION_BIAS,
        default=_DEFAULT_CONSTRUCTION_BIAS,
        field_name="construction_bias",
        audit=audit,
    )
    baseline_time_fraction = _algorithm_float(
        plan.get("baseline_time_fraction", _BASELINE_TIME_FRACTION),
        minimum=_MIN_BASELINE_TIME_FRACTION,
        maximum=_MAX_BASELINE_TIME_FRACTION,
        default=_BASELINE_TIME_FRACTION,
        field_name="baseline_time_fraction",
        audit=audit,
    )
    operator_round_limit = _algorithm_int(
        plan.get("operator_round_limit", _MAX_OPERATOR_ROUNDS),
        minimum=0,
        maximum=_MAX_OPERATOR_ROUNDS,
        default=_MAX_OPERATOR_ROUNDS,
        field_name="operator_round_limit",
        audit=audit,
    )
    post_baseline_enabled = _algorithm_bool(
        plan.get("post_baseline_operators_enabled", True),
        field_name="post_baseline_operators_enabled",
        default=True,
        audit=audit,
    )
    local_search = plan.get("local_search", {})
    if not isinstance(local_search, Mapping):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"local_search returned non-mapping value {local_search!r}",
        )
        local_search = {}
    local_components = _algorithm_string_sequence(
        local_search.get("enabled_components", []),
        allowed=_ALLOWED_BLUEPRINT_LOCAL_SEARCH_COMPONENTS,
        default=[],
        max_items=len(_ALLOWED_BLUEPRINT_LOCAL_SEARCH_COMPONENTS),
        field_name="local_search.enabled_components",
        audit=audit,
        allow_empty=True,
    )
    local_rounds = _algorithm_int(
        local_search.get("rounds", 0),
        minimum=0,
        maximum=_MAX_BLUEPRINT_LOCAL_SEARCH_ROUNDS,
        default=0,
        field_name="local_search.rounds",
        audit=audit,
    )
    local_top_k = _algorithm_int(
        local_search.get("top_k", 16),
        minimum=0,
        maximum=_MAX_BLUEPRINT_LOCAL_SEARCH_TOP_K,
        default=16,
        field_name="local_search.top_k",
        audit=audit,
    )
    restart = plan.get("restart", {})
    if not isinstance(restart, Mapping):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"restart returned non-mapping value {restart!r}",
        )
        restart = {}
    restart_enabled = _algorithm_bool(
        restart.get("enabled", False),
        field_name="restart.enabled",
        default=False,
        audit=audit,
    )
    restart_stagnation = _algorithm_int(
        restart.get("stagnation_rounds", 0),
        minimum=0,
        maximum=_MAX_BLUEPRINT_RESTART_STAGNATION_ROUNDS,
        default=0,
        field_name="restart.stagnation_rounds",
        audit=audit,
    )
    active = requested_active and _as_nonnegative_int(
        audit["algorithm_blueprint_errors"]
    ) == 0

    normalized_plan = {
        "enabled": active,
        "construction_methods": construction_methods,
        "construction_keep_top_k": construction_keep_top_k,
        "construction_bias": construction_bias,
        "baseline_time_fraction": baseline_time_fraction,
        "operator_round_limit": operator_round_limit,
        "post_baseline_operators_enabled": post_baseline_enabled,
        "local_search": {
            "enabled_components": local_components,
            "rounds": local_rounds,
            "top_k": local_top_k,
        },
        "restart": {
            "enabled": restart_enabled,
            "stagnation_rounds": restart_stagnation,
        },
    }
    audit["algorithm_plan"] = normalized_plan
    audit["algorithm_blueprint_active"] = active
    audit["algorithm_construction_methods"] = construction_methods
    audit["algorithm_construction_keep_top_k"] = construction_keep_top_k
    audit["algorithm_baseline_time_fraction"] = baseline_time_fraction
    audit["algorithm_operator_round_limit"] = operator_round_limit
    audit["algorithm_post_baseline_operators_enabled"] = post_baseline_enabled
    audit["algorithm_local_search_components"] = local_components
    audit["algorithm_local_search_rounds"] = local_rounds
    audit["algorithm_local_search_top_k"] = local_top_k
    audit["algorithm_restart_enabled"] = restart_enabled
    audit["algorithm_restart_stagnation_rounds"] = restart_stagnation
    if active:
        audit["algorithm_phases_executed"] = ["plan_loaded"]
        audit["algorithm_best_delta_by_phase"] = {"plan_loaded": 0.0}
        audit["algorithm_phase_runtime_ms"] = {"plan_loaded": 0}
        audit["algorithm_stop_reason"] = "plan_loaded"
    elif requested_active:
        audit["algorithm_phases_executed"] = ["plan_invalid"]
        audit["algorithm_best_delta_by_phase"] = {"plan_invalid": 0.0}
        audit["algorithm_phase_runtime_ms"] = {"plan_invalid": 0}
        audit["algorithm_stop_reason"] = "invalid_plan"


def _validate_algorithm_plan_keys(
    plan: Mapping[str, Any],
    *,
    requested_active: bool,
    audit: dict[str, Any],
) -> None:
    allowed_top = _ALGORITHM_BLUEPRINT_REQUIRED_KEYS
    unknown = sorted(str(key) for key in plan if str(key) not in allowed_top)
    if unknown:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"algorithm_plan contains unknown keys {unknown}",
        )
    if requested_active:
        missing = sorted(key for key in allowed_top if key not in plan)
        if missing:
            audit["algorithm_blueprint_errors"] += 1
            _record_algorithm_event(
                audit,
                "error",
                f"enabled algorithm_plan missing required keys {missing}",
            )
    local_search = plan.get("local_search")
    if isinstance(local_search, Mapping):
        local_unknown = sorted(
            str(key)
            for key in local_search
            if str(key) not in _ALGORITHM_BLUEPRINT_LOCAL_SEARCH_REQUIRED_KEYS
        )
        if local_unknown:
            audit["algorithm_blueprint_errors"] += 1
            _record_algorithm_event(
                audit,
                "error",
                f"local_search contains unknown keys {local_unknown}",
            )
        if requested_active:
            local_missing = sorted(
                key
                for key in _ALGORITHM_BLUEPRINT_LOCAL_SEARCH_REQUIRED_KEYS
                if key not in local_search
            )
            if local_missing:
                audit["algorithm_blueprint_errors"] += 1
                _record_algorithm_event(
                    audit,
                    "error",
                    f"enabled local_search missing required keys {local_missing}",
                )
    restart = plan.get("restart")
    if isinstance(restart, Mapping):
        restart_unknown = sorted(
            str(key)
            for key in restart
            if str(key) not in _ALGORITHM_BLUEPRINT_RESTART_REQUIRED_KEYS
        )
        if restart_unknown:
            audit["algorithm_blueprint_errors"] += 1
            _record_algorithm_event(
                audit,
                "error",
                f"restart contains unknown keys {restart_unknown}",
            )
        if requested_active:
            restart_missing = sorted(
                key
                for key in _ALGORITHM_BLUEPRINT_RESTART_REQUIRED_KEYS
                if key not in restart
            )
            if restart_missing:
                audit["algorithm_blueprint_errors"] += 1
                _record_algorithm_event(
                    audit,
                    "error",
                    f"enabled restart missing required keys {restart_missing}",
                )


def _apply_algorithm_blueprint_search_policy(
    search_policy: dict[str, Any],
    *,
    algorithm_blueprint: dict[str, Any],
) -> None:
    if not _algorithm_blueprint_active(algorithm_blueprint):
        return
    search_policy["baseline_time_fraction"] = algorithm_blueprint[
        "algorithm_baseline_time_fraction"
    ]
    search_policy["operator_round_limit"] = algorithm_blueprint[
        "algorithm_operator_round_limit"
    ]
    search_policy["post_baseline_operators_enabled"] = algorithm_blueprint[
        "algorithm_post_baseline_operators_enabled"
    ]


def _algorithm_blueprint_active(algorithm_blueprint: Mapping[str, Any] | None) -> bool:
    return bool(algorithm_blueprint and algorithm_blueprint.get("algorithm_blueprint_active"))


def _algorithm_bool(
    value: Any,
    *,
    field_name: str,
    default: bool,
    audit: dict[str, Any],
) -> bool:
    if isinstance(value, bool):
        return value
    audit["algorithm_blueprint_errors"] += 1
    _record_algorithm_event(
        audit,
        "error",
        f"{field_name} returned non-bool value {value!r}",
    )
    return default


def _algorithm_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    default: float,
    field_name: str,
    audit: dict[str, Any],
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name} returned non-numeric value {value!r}",
        )
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name} returned non-finite value {value!r}",
        )
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _algorithm_int(
    value: Any,
    *,
    minimum: int,
    maximum: int,
    default: int,
    field_name: str,
    audit: dict[str, Any],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name} returned non-integer value {value!r}",
        )
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _algorithm_string_sequence(
    value: Any,
    *,
    allowed: frozenset[str],
    default: list[str],
    max_items: int,
    field_name: str,
    audit: dict[str, Any],
    allow_empty: bool = False,
) -> list[str]:
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name} returned non-sequence value {value!r}",
        )
        return list(default)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if text not in allowed:
            audit["algorithm_blueprint_errors"] += 1
            _record_algorithm_event(
                audit,
                "error",
                f"{field_name} contains unknown value {text!r}",
            )
            continue
        if text not in seen:
            seen.add(text)
            normalized.append(text)
        if len(normalized) >= max_items:
            break
    if not normalized and not allow_empty:
        audit["algorithm_blueprint_errors"] += 1
        _record_algorithm_event(
            audit,
            "error",
            f"{field_name} produced no valid values",
        )
        return list(default)
    return normalized


def _record_algorithm_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("algorithm_blueprint_events", [])
    if len(events) >= 10:
        return
    events.append(
        {
            "policy": _ALGORITHM_BLUEPRINT_RELATIVE_PATH,
            "status": status,
            "detail": detail,
        }
    )


def _construct_with_algorithm_blueprint(
    *,
    instance: CvrpInstance,
    rng: random.Random,
    construction_audit: dict[str, Any],
    algorithm_blueprint: dict[str, Any],
) -> tuple[CvrpSolution, dict[str, Any]]:
    start_ns = time.monotonic_ns()
    methods = [
        method
        for method in algorithm_blueprint.get("algorithm_construction_methods", [])
        if method in _ALLOWED_CONSTRUCTION_MODES
    ]
    if not methods:
        methods = [_DEFAULT_CONSTRUCTION_MODE]
    keep_top_k = _as_nonnegative_int(
        algorithm_blueprint.get("algorithm_construction_keep_top_k", 1)
    )
    methods = methods[: max(1, min(keep_top_k, len(methods)))]
    bias = float(
        algorithm_blueprint.get("algorithm_plan", {}).get(
            "construction_bias",
            algorithm_blueprint.get("construction_bias", _DEFAULT_CONSTRUCTION_BIAS),
        )
    )

    adapter = CvrpAdapter(object())  # type: ignore[arg-type]
    best_solution: CvrpSolution | None = None
    best_objective: dict[str, int | float] | None = None
    first_objective: dict[str, int | float] | None = None
    tried: list[str] = []
    for method in methods:
        tried.append(method)
        try:
            candidate = solve(
                instance,
                rng,
                construction_mode=method,
                construction_bias=bias,
            )
        except Exception as exc:
            construction_audit["construction_errors"] = (
                _as_nonnegative_int(construction_audit["construction_errors"]) + 1
            )
            _record_construction_event(
                construction_audit,
                "error",
                f"algorithm construction failed for mode={method!r}: {exc}",
            )
            continue
        valid, reason = _solution_is_valid(adapter, instance, candidate)
        if not valid:
            construction_audit["construction_errors"] = (
                _as_nonnegative_int(construction_audit["construction_errors"]) + 1
            )
            _record_construction_event(
                construction_audit,
                "error",
                f"algorithm construction infeasible for mode={method!r}: {reason}",
            )
            continue
        objective = _objective_for_solution(adapter, instance, candidate)
        if first_objective is None:
            first_objective = objective
        if best_objective is None or _lexicographic_improves(objective, best_objective):
            best_solution = candidate
            best_objective = objective
            construction_audit["construction_mode"] = method

    if best_solution is None:
        construction_audit["construction_errors"] = (
            _as_nonnegative_int(construction_audit["construction_errors"]) + 1
        )
        _record_construction_event(
            construction_audit,
            "error",
            "algorithm construction ensemble produced no valid solution",
        )
        best_solution = solve(instance, rng)
        best_objective = _objective_for_solution(adapter, instance, best_solution)

    construction_audit["construction_elapsed_ms"] = int(
        (time.monotonic_ns() - start_ns) / 1_000_000
    )
    construction_audit["construction_routes"] = len(best_solution.routes)
    construction_audit["construction_distance"] = sum(
        instance.route_distance(route) for route in best_solution.routes
    )
    construction_audit["construction_feasible"] = True
    construction_audit["algorithm_construction_methods_tried"] = tried
    _append_algorithm_phase(algorithm_blueprint, "construction_ensemble")
    _set_algorithm_phase_runtime(
        algorithm_blueprint,
        "construction_ensemble",
        start_ns,
    )
    if first_objective is not None and best_objective is not None:
        algorithm_blueprint.setdefault("algorithm_best_delta_by_phase", {})[
            "construction_ensemble"
        ] = _objective_distance_delta(first_objective, best_objective)
    return best_solution, construction_audit


def _construct_with_main_search_strategy(
    *,
    instance: CvrpInstance,
    rng: random.Random,
    construction_audit: dict[str, Any],
    main_search_strategy: dict[str, Any],
) -> tuple[CvrpSolution, dict[str, Any]]:
    start_ns = time.monotonic_ns()
    methods = [
        method
        for method in main_search_strategy.get("main_search_construction_methods", [])
        if method in _ALLOWED_CONSTRUCTION_MODES
    ]
    if not methods:
        methods = [_DEFAULT_CONSTRUCTION_MODE]
    keep_top_k = max(
        1,
        min(
            _as_nonnegative_int(
                main_search_strategy.get("main_search_construction_keep_top_k", 1)
            ),
            len(methods),
        ),
    )
    bias = float(
        main_search_strategy.get(
            "main_search_construction_bias",
            _DEFAULT_CONSTRUCTION_BIAS,
        )
    )

    adapter = CvrpAdapter(object())  # type: ignore[arg-type]
    candidates: list[tuple[dict[str, int | float], CvrpSolution, str]] = []
    tried: list[str] = []
    for method in methods:
        tried.append(method)
        try:
            candidate = solve(
                instance,
                rng,
                construction_mode=method,
                construction_bias=bias,
            )
        except Exception as exc:
            construction_audit["construction_errors"] = (
                _as_nonnegative_int(construction_audit["construction_errors"]) + 1
            )
            _record_construction_event(
                construction_audit,
                "error",
                f"main search construction failed for mode={method!r}: {exc}",
            )
            continue
        valid, reason = _solution_is_valid(adapter, instance, candidate)
        if not valid:
            construction_audit["construction_errors"] = (
                _as_nonnegative_int(construction_audit["construction_errors"]) + 1
            )
            _record_construction_event(
                construction_audit,
                "error",
                f"main search construction infeasible for mode={method!r}: {reason}",
            )
            continue
        candidates.append((_objective_for_solution(adapter, instance, candidate), candidate, method))

    first_objective = candidates[0][0] if candidates else None
    if not candidates:
        construction_audit["construction_errors"] = (
            _as_nonnegative_int(construction_audit["construction_errors"]) + 1
        )
        _record_construction_event(
            construction_audit,
            "error",
            "main search construction ensemble produced no valid solution",
        )
        best_solution = solve(instance, rng)
        best_objective = _objective_for_solution(adapter, instance, best_solution)
        best_method = _DEFAULT_CONSTRUCTION_MODE
        main_search_strategy["_main_search_construction_pool_solutions"] = [
            best_solution
        ]
        main_search_strategy["main_search_construction_pool_size"] = 1
        main_search_strategy["main_search_construction_pool_distances"] = [
            round(float(best_objective.get("total_distance", 0.0)), 6)
        ]
    else:
        candidates.sort(
            key=lambda item: (
                float(item[0].get("fleet_violation", 0)),
                float(item[0].get("total_distance", 0.0)),
            )
        )
        kept = candidates[:keep_top_k]
        best_objective, best_solution, best_method = kept[0]
        main_search_strategy["_main_search_construction_pool_solutions"] = [
            candidate_solution for _objective, candidate_solution, _method in kept
        ]
        main_search_strategy["main_search_construction_pool_size"] = len(kept)
        main_search_strategy["main_search_construction_pool_distances"] = [
            round(float(objective.get("total_distance", 0.0)), 6)
            for objective, _solution, _method in kept
        ]

    construction_audit["construction_elapsed_ms"] = int(
        (time.monotonic_ns() - start_ns) / 1_000_000
    )
    construction_audit["construction_mode"] = best_method
    construction_audit["construction_routes"] = len(best_solution.routes)
    construction_audit["construction_distance"] = sum(
        instance.route_distance(route) for route in best_solution.routes
    )
    construction_audit["construction_feasible"] = True
    construction_audit["main_search_construction_methods_tried"] = tried
    _append_main_search_phase(main_search_strategy, "construction")
    _set_main_search_phase_runtime(main_search_strategy, "construction", start_ns)
    if first_objective is not None:
        main_search_strategy.setdefault("main_search_objective_delta_by_phase", {})[
            "construction"
        ] = _objective_distance_delta(first_objective, best_objective)
    return best_solution, construction_audit


def improve_with_main_search_strategy(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    rng: random.Random,
    time_limit_sec: float,
    start_time: float,
    instance_path: str | Path | None = None,
    seed: int | None = None,
    main_search_strategy: dict[str, Any] | None = None,
    destroy_repair_policy: dict[str, Any] | None = None,
    route_pair_policy: dict[str, Any] | None = None,
    acceptance_restart_policy: dict[str, Any] | None = None,
) -> tuple[CvrpSolution, dict[str, Any]]:
    if not _main_search_strategy_active(main_search_strategy):
        return solution, {}

    assert main_search_strategy is not None
    audit = dict(main_search_strategy)
    if destroy_repair_policy:
        audit.update(destroy_repair_policy)
    if route_pair_policy:
        audit.update(route_pair_policy)
    if acceptance_restart_policy:
        audit.update(acceptance_restart_policy)
    _apply_acceptance_restart_policy_to_main_search(audit)
    if _main_search_mechanism_policy_error_count(audit):
        audit["main_search_strategy_errors"] = _as_nonnegative_int(
            audit.get("main_search_strategy_errors")
        ) + _main_search_mechanism_policy_error_count(audit)
        audit["main_search_stop_reason"] = "invalid_mechanism_policy"
        return solution, _finalize_main_search_audit(audit)
    _append_main_search_phase(audit, "baseline")
    audit.setdefault("main_search_phase_runtime_ms", {}).setdefault("baseline", 0)

    components = [
        component
        for component in audit.get("main_search_components", [])
        if component in _ALLOWED_MAIN_SEARCH_COMPONENTS
    ]
    rounds = _as_nonnegative_int(audit.get("main_search_rounds", 0))
    top_k = _as_nonnegative_int(audit.get("main_search_top_k", 16))
    min_distance_improvement = float(
        audit.get("main_search_acceptance_min_distance_improvement", 0.0)
    )
    strategy_family = str(
        audit.get("main_search_strategy_family", _DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY)
    )
    component_min_distance_improvement = audit.get(
        "main_search_component_min_distance_improvement",
        {},
    )
    if not isinstance(component_min_distance_improvement, Mapping):
        component_min_distance_improvement = {}
    if not components or rounds <= 0 or top_k <= 0:
        audit["main_search_stop_reason"] = "improvement_loop_disabled"
        return solution, _finalize_main_search_audit(audit)

    phase_start_ns = time.monotonic_ns()
    initial_objective = _objective_for_solution(adapter, instance, solution)
    best_solution = solution
    best_objective = dict(initial_objective)
    current = solution
    current_objective = dict(initial_objective)
    no_improvement_rounds = 0
    stop_reason = "max_main_search_rounds"
    perturbation_schedule = str(
        audit.get(
            "main_search_perturbation_schedule",
            _DEFAULT_MAIN_SEARCH_PERTURBATION_SCHEDULE,
        )
    )
    perturb_limit = _main_search_plan_int(audit, "perturbation", "max_perturbations")
    phase_component_order = _main_search_phase_component_order(audit, components)
    audit["main_search_phase_component_order"] = {
        phase: list(phase_components)
        for phase, phase_components in phase_component_order.items()
    }
    assigned_components = {
        component
        for phase_components in phase_component_order.values()
        for component in phase_components
    }
    cleanup_coupled = bool(
        audit.get("main_search_local_cleanup_after_recombination")
    ) and "route_pool_recombination" in assigned_components
    unassigned_components = [
        component
        for component in components
        if component not in assigned_components
        and not (
            cleanup_coupled
            and component in {"inter_route_relocate", "intra_route_2opt"}
        )
    ]
    audit["main_search_phase_unassigned_components"] = unassigned_components
    for component in unassigned_components:
        _record_main_search_component_skip(
            audit,
            component,
            "algorithm_body_phase_not_enabled",
        )

    def run_component(
        component: str,
        *,
        phase_name: str,
        route_pair_phase_improved: bool,
    ) -> dict[str, bool]:
        nonlocal current, current_objective, best_solution, best_objective, stop_reason
        result = {
            "stopped": False,
            "phase_improved": False,
            "current_accepted": False,
            "route_pair_phase_improved": route_pair_phase_improved,
            "route_pool_accepted": False,
        }
        if _main_search_time_exhausted(start_time, time_limit_sec):
            stop_reason = "time_limit"
            result["stopped"] = True
            return result
        algorithm_skip_reason = _main_search_algorithm_body_skip_reason(
            audit,
            component,
            instance,
            instance_path=instance_path,
        )
        if algorithm_skip_reason:
            _record_main_search_component_attempted(audit, component)
            _record_main_search_component_skip(
                audit,
                component,
                algorithm_skip_reason,
            )
            return result
        if (
            component == "bounded_destroy_repair"
            and "route_pair_swap" in components
            and route_pair_phase_improved
        ):
            _record_main_search_component_skip(
                audit,
                component,
                "route_pair_phase_improved",
            )
            return result
        if (
            component == "bounded_destroy_repair"
            and _as_nonnegative_int(
                audit.get("main_search_component_phase_improvement_counts", {}).get(
                    "bounded_destroy_repair",
                    0,
                )
            )
            >= _as_nonnegative_int(
                audit.get(
                    "main_search_bounded_destroy_repair_accept_limit",
                    _MAIN_SEARCH_BDR_ACCEPT_LIMIT,
                )
            )
        ):
            _record_main_search_component_skip(
                audit,
                component,
                "bounded_destroy_repair_accept_limit_reached",
            )
            return result

        component_start_ns = time.monotonic_ns()
        _record_main_search_component_attempted(audit, component)
        if component == "route_pool_recombination":
            audit["main_search_route_pool_invocations"] = (
                _as_nonnegative_int(audit.get("main_search_route_pool_invocations")) + 1
            )
        effective_top_k = _main_search_effective_component_top_k(
            audit,
            component,
            top_k,
            instance,
        )
        _record_main_search_effective_top_k(audit, component, effective_top_k)
        choice_kwargs: dict[str, Any] = {
            "current_solution": current,
            "best_solution": best_solution,
            "adapter": adapter,
            "current_objective": current_objective,
            "best_objective": best_objective,
            "top_k": effective_top_k,
            "min_distance_improvement": float(
                component_min_distance_improvement.get(
                    component,
                    _main_search_component_min_distance_improvement(
                        component,
                        min_distance_improvement,
                        strategy_family=strategy_family,
                    ),
                )
            ),
            "mechanism_policies": audit,
        }
        if component == "route_pool_recombination":
            choice_kwargs.update(
                {
                    "rng": rng,
                    "time_limit_sec": time_limit_sec,
                    "start_time": start_time,
                    "instance_path": instance_path,
                    "seed": seed,
                }
            )
        (
            candidate,
            attempts,
            component_telemetry,
            candidate_context,
        ) = _main_search_component_candidate_choice(
            component,
            instance,
            **choice_kwargs,
        )
        _record_main_search_component_attempts(audit, component, attempts)
        _record_main_search_component_repair_counts(
            audit,
            component,
            component_telemetry,
        )
        _record_main_search_component_runtime(audit, component, component_start_ns)
        if candidate is None:
            _record_main_search_component_skip(
                audit,
                component,
                _main_search_skip_reason(component_telemetry, attempts),
            )
            return result

        candidate_objective = candidate_context["objective"]
        candidate_delta = float(candidate_context["accepted_delta"])
        phase_best_delta = float(candidate_context["phase_delta"])
        _record_main_search_component_candidate_delta(
            audit,
            component,
            candidate_delta,
        )
        valid, reason = _solution_is_valid(adapter, instance, candidate)
        if not valid:
            audit["main_search_strategy_errors"] = (
                _as_nonnegative_int(audit.get("main_search_strategy_errors")) + 1
            )
            _record_main_search_event(
                audit,
                "error",
                f"{component} produced invalid solution: {reason}",
            )
            _record_main_search_component_skip(
                audit,
                component,
                "invalid_component_output",
            )
            stop_reason = "invalid_component_output"
            result["stopped"] = True
            return result

        current = candidate
        current_objective = candidate_objective
        _record_main_search_component_accepted(audit, component)
        result["current_accepted"] = True
        result["route_pool_accepted"] = component == "route_pool_recombination"
        _record_main_search_component_accepted_delta(
            audit,
            component,
            candidate_delta,
        )
        if _lexicographic_improves(current_objective, best_objective):
            best_solution = current
            best_objective = dict(current_objective)
            _record_main_search_component_phase_improvement(
                audit,
                component,
                phase_best_delta,
            )
            result["phase_improved"] = True
            if component == "route_pair_swap":
                result["route_pair_phase_improved"] = True
            _record_mechanism_acceptance(
                audit,
                component,
                phase_delta=phase_best_delta,
                recovery_delta=0.0,
                phase_best=True,
            )
        else:
            _record_main_search_component_recovery(
                audit,
                component,
                candidate_delta,
            )
            _record_mechanism_acceptance(
                audit,
                component,
                phase_delta=0.0,
                recovery_delta=candidate_delta,
                phase_best=False,
            )
        if phase_name:
            _append_main_search_phase(audit, phase_name)
        return result

    if perturbation_schedule == "before_first_round" and perturb_limit > 0:
        perturbed = _try_main_search_perturbation(
            audit,
            best_solution,
            instance,
            adapter=adapter,
            rng=rng,
            phase_name="pre_improvement_perturbation",
        )
        if perturbed is None and audit.get("main_search_strategy_errors"):
            stop_reason = "invalid_perturbation"
        elif perturbed is not None:
            current = perturbed
            current_objective = _objective_for_solution(adapter, instance, current)

    _append_main_search_phase(audit, "improvement_loop")
    if stop_reason != "invalid_perturbation":
        for round_index in range(rounds):
            if _main_search_time_exhausted(start_time, time_limit_sec):
                stop_reason = "time_limit"
                break
            audit["main_search_rounds"] = round_index + 1
            if (
                perturbation_schedule == "before_each_round"
                and _as_nonnegative_int(audit.get("main_search_perturbation_count"))
                < perturb_limit
            ):
                perturbed = _try_main_search_perturbation(
                    audit,
                    best_solution,
                    instance,
                    adapter=adapter,
                    rng=rng,
                    phase_name="pre_round_perturbation",
                )
                if perturbed is None and audit.get("main_search_strategy_errors"):
                    stop_reason = "invalid_perturbation"
                    break
                if perturbed is not None:
                    current = perturbed
                    current_objective = _objective_for_solution(
                        adapter,
                        instance,
                        current,
                    )
            round_phase_improved = 0
            round_route_pair_phase_improved = False
            round_current_accepted = 0
            for phase_name, phase_components in phase_component_order.items():
                phase_runtime_start_ns = time.monotonic_ns()
                phase_initial_objective = dict(best_objective)
                _append_main_search_phase(audit, phase_name)
                for component in phase_components:
                    result = run_component(
                        component,
                        phase_name=phase_name,
                        route_pair_phase_improved=round_route_pair_phase_improved,
                    )
                    round_route_pair_phase_improved = result[
                        "route_pair_phase_improved"
                    ]
                    round_phase_improved += int(result["phase_improved"])
                    round_current_accepted += int(result["current_accepted"])
                    if result["route_pool_accepted"] and bool(
                        audit.get("main_search_local_cleanup_after_recombination")
                    ):
                        for cleanup_component in (
                            "inter_route_relocate",
                            "intra_route_2opt",
                        ):
                            if cleanup_component not in components:
                                continue
                            if cleanup_component in phase_components:
                                continue
                            cleanup_result = run_component(
                                cleanup_component,
                                phase_name="local_cleanup",
                                route_pair_phase_improved=round_route_pair_phase_improved,
                            )
                            round_phase_improved += int(
                                cleanup_result["phase_improved"]
                            )
                            round_current_accepted += int(
                                cleanup_result["current_accepted"]
                            )
                            if cleanup_result["stopped"]:
                                break
                    if result["stopped"]:
                        break
                phase_delta = _objective_distance_delta(
                    phase_initial_objective,
                    best_objective,
                )
                objective_delta = audit.setdefault(
                    "main_search_objective_delta_by_phase",
                    {},
                )
                objective_delta[phase_name] = round(
                    float(objective_delta.get(phase_name, 0.0) or 0.0)
                    + float(phase_delta),
                    6,
                )
                _set_main_search_phase_runtime(
                    audit,
                    phase_name,
                    phase_runtime_start_ns,
                )
                if stop_reason in {
                    "time_limit",
                    "invalid_component_output",
                    "invalid_perturbation",
                }:
                    break
            if stop_reason in {
                "time_limit",
                "invalid_component_output",
                "invalid_perturbation",
            }:
                break
            if round_phase_improved > 0:
                no_improvement_rounds = 0
                continue
            if round_current_accepted > 0:
                no_improvement_rounds += 1
                continue
            no_improvement_rounds += 1
            stagnation_limit = _as_nonnegative_int(
                audit.get("main_search_restart_stagnation_rounds", 0)
            )
            restart_limit = _main_search_plan_int(audit, "restart", "max_restarts")
            if (
                perturbation_schedule == "after_no_improvement"
                and bool(audit.get("main_search_perturbation_enabled"))
                and _as_nonnegative_int(audit.get("main_search_perturbation_count"))
                < perturb_limit
            ):
                perturbed = _try_main_search_perturbation(
                    audit,
                    best_solution,
                    instance,
                    adapter=adapter,
                    rng=rng,
                    phase_name="perturbation",
                )
                if perturbed is None and audit.get("main_search_strategy_errors"):
                    stop_reason = "invalid_perturbation"
                    break
                if perturbed is not None:
                    current = perturbed
                    current_objective = _objective_for_solution(
                        adapter,
                        instance,
                        current,
                    )
                    continue
            if (
                bool(audit.get("main_search_restart_enabled"))
                and stagnation_limit
                and no_improvement_rounds >= stagnation_limit
                and _as_nonnegative_int(audit.get("main_search_restart_count"))
                < restart_limit
            ):
                audit["main_search_restart_count"] = (
                    _as_nonnegative_int(audit.get("main_search_restart_count")) + 1
                )
                current = best_solution
                current_objective = dict(best_objective)
                _append_main_search_phase(audit, "restart")
                no_improvement_rounds = 0
                continue
            stop_reason = "no_main_search_improvement"
            break

    _set_main_search_phase_runtime(audit, "improvement_loop", phase_start_ns)
    phase_delta = _objective_distance_delta(initial_objective, best_objective)
    audit.setdefault("main_search_objective_delta_by_phase", {})[
        "improvement_loop"
    ] = phase_delta
    audit["main_search_elapsed_ms"] = sum(
        _as_nonnegative_int(value)
        for value in audit.get("main_search_phase_runtime_ms", {}).values()
    )
    audit["main_search_best_returned"] = True
    audit["main_search_stop_reason"] = stop_reason
    audit["main_search_objective_trace"] = _main_search_objective_trace(
        initial_objective=initial_objective,
        best_objective=best_objective,
        returned_objective=_objective_for_solution(adapter, instance, best_solution),
        phase_delta=phase_delta,
        audit=audit,
    )
    audit["restart_count"] = audit.get("main_search_restart_count", 0)
    audit["perturbation_count"] = audit.get("main_search_perturbation_count", 0)
    audit["acceptance_restart_phase_delta_sum"] = phase_delta
    audit["acceptance_restart_runtime_ms"] = audit.get("main_search_elapsed_ms", 0)
    return best_solution, _finalize_main_search_audit(audit)


def _main_search_mechanism_policy_error_count(audit: Mapping[str, Any]) -> int:
    return sum(
        _as_nonnegative_int(audit.get(field))
        for field in (
            "destroy_repair_errors",
            "route_pair_errors",
            "acceptance_restart_errors",
        )
    )


def _finalize_main_search_audit(audit: dict[str, Any]) -> dict[str, Any]:
    audit.pop("_main_search_construction_pool_solutions", None)
    return audit


def _apply_acceptance_restart_policy_to_main_search(audit: dict[str, Any]) -> None:
    if not bool(audit.get("acceptance_restart_active")):
        return
    plan = audit.get("acceptance_restart_plan")
    if not isinstance(plan, Mapping):
        return
    threshold = float(plan.get("min_distance_improvement", 0.0))
    audit["main_search_acceptance_min_distance_improvement"] = threshold
    strategy_family = str(
        audit.get("main_search_strategy_family", _DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY)
    )
    components = list(audit.get("main_search_components") or [])
    audit["main_search_component_min_distance_improvement"] = {
        component: _main_search_component_min_distance_improvement(
            component,
            threshold,
            strategy_family=strategy_family,
        )
        for component in components
    }
    restart = plan.get("restart")
    if isinstance(restart, Mapping):
        audit["main_search_restart_enabled"] = bool(restart.get("enabled", False))
        audit["main_search_restart_stagnation_rounds"] = _as_nonnegative_int(
            restart.get("stagnation_rounds")
        )
        main_plan = audit.get("main_search_plan")
        if isinstance(main_plan, dict) and isinstance(main_plan.get("restart"), dict):
            main_plan["restart"].update(
                {
                    "enabled": audit["main_search_restart_enabled"],
                    "stagnation_rounds": audit[
                        "main_search_restart_stagnation_rounds"
                    ],
                    "max_restarts": _as_nonnegative_int(restart.get("max_restarts")),
                }
            )
    perturbation = plan.get("perturbation")
    if isinstance(perturbation, Mapping):
        audit["main_search_perturbation_enabled"] = bool(
            perturbation.get("enabled", False)
        )
        audit["main_search_perturbation_schedule"] = str(
            perturbation.get("schedule", _DEFAULT_MAIN_SEARCH_PERTURBATION_SCHEDULE)
        )
        audit["main_search_perturbation_strength"] = _as_nonnegative_int(
            perturbation.get("strength")
        ) or 1
        main_plan = audit.get("main_search_plan")
        if isinstance(main_plan, dict) and isinstance(main_plan.get("perturbation"), dict):
            main_plan["perturbation"].update(
                {
                    "enabled": audit["main_search_perturbation_enabled"],
                    "schedule": audit["main_search_perturbation_schedule"],
                    "strength": audit["main_search_perturbation_strength"],
                    "max_perturbations": _as_nonnegative_int(
                        perturbation.get("max_perturbations")
                    ),
                }
            )


def _record_mechanism_acceptance(
    audit: dict[str, Any],
    component: str,
    *,
    phase_delta: float,
    recovery_delta: float,
    phase_best: bool,
) -> None:
    audit["accepted_current_count"] = _as_nonnegative_int(
        audit.get("accepted_current_count")
    ) + 1
    if phase_best:
        audit["accepted_phase_best_count"] = _as_nonnegative_int(
            audit.get("accepted_phase_best_count")
        ) + 1
        audit["phase_best_refresh_count"] = _as_nonnegative_int(
            audit.get("phase_best_refresh_count")
        ) + 1
        audit["acceptance_restart_phase_delta_sum"] = float(
            audit.get("acceptance_restart_phase_delta_sum", 0.0)
        ) + float(phase_delta)
    else:
        audit["accepted_recovery_only_count"] = _as_nonnegative_int(
            audit.get("accepted_recovery_only_count")
        ) + 1
    if component == "route_pair_swap":
        if phase_best:
            audit["route_pair_accepted_phase_best"] = _as_nonnegative_int(
                audit.get("route_pair_accepted_phase_best")
            ) + 1
            audit["route_pair_phase_delta_sum"] = float(
                audit.get("route_pair_phase_delta_sum", 0.0)
            ) + float(phase_delta)
        else:
            audit["route_pair_accepted_recovery_only"] = _as_nonnegative_int(
                audit.get("route_pair_accepted_recovery_only")
            ) + 1
        audit["route_pair_accepted_current"] = _as_nonnegative_int(
            audit.get("route_pair_accepted_current")
        ) + 1
    if component == "bounded_destroy_repair":
        if phase_best:
            audit["destroy_repair_accepted_phase_best"] = _as_nonnegative_int(
                audit.get("destroy_repair_accepted_phase_best")
            ) + 1
            audit["destroy_repair_phase_delta_sum"] = float(
                audit.get("destroy_repair_phase_delta_sum", 0.0)
            ) + float(phase_delta)
        else:
            audit["destroy_repair_accepted_recovery_only"] = _as_nonnegative_int(
                audit.get("destroy_repair_accepted_recovery_only")
            ) + 1
        audit["destroy_repair_accepted_current"] = _as_nonnegative_int(
            audit.get("destroy_repair_accepted_current")
        ) + 1
    del recovery_delta


def _try_main_search_perturbation(
    audit: dict[str, Any],
    best_solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    rng: random.Random,
    phase_name: str,
) -> CvrpSolution | None:
    if not bool(audit.get("main_search_perturbation_enabled")):
        return None
    perturbed = _perturb_solution(
        best_solution,
        instance,
        rng=rng,
        strength=_as_nonnegative_int(
            audit.get("main_search_perturbation_strength", 1)
        ),
    )
    if perturbed is None:
        return None
    valid, reason = _solution_is_valid(adapter, instance, perturbed)
    if not valid:
        audit["main_search_strategy_errors"] = (
            _as_nonnegative_int(audit.get("main_search_strategy_errors")) + 1
        )
        _record_main_search_event(
            audit,
            "error",
            f"perturbation produced invalid solution: {reason}",
        )
        return None
    audit["main_search_perturbation_count"] = (
        _as_nonnegative_int(audit.get("main_search_perturbation_count")) + 1
    )
    _append_main_search_phase(audit, phase_name)
    return perturbed


def _effective_baseline_time_fraction(
    baseline_time_fraction: float,
    *,
    is_vrp: bool,
    baseline_required: bool,
    main_search_strategy: Mapping[str, Any] | None,
) -> float:
    fraction = float(baseline_time_fraction)
    if not (
        is_vrp
        and baseline_required
        and _main_search_strategy_active(main_search_strategy)
    ):
        return fraction
    budget_policy = str(
        (main_search_strategy or {}).get(
            "main_search_baseline_budget_policy",
            _DEFAULT_MAIN_SEARCH_BASELINE_BUDGET_POLICY,
        )
    )
    if budget_policy == "formal_floor":
        return max(fraction, _MAIN_SEARCH_FORMAL_BASELINE_TIME_FLOOR)
    return fraction


def _main_search_component_min_distance_improvement(
    component: str,
    requested_min_distance_improvement: float,
    *,
    strategy_family: str = _DEFAULT_MAIN_SEARCH_STRATEGY_FAMILY,
) -> float:
    threshold = max(0.0, float(requested_min_distance_improvement))
    if component == "bounded_destroy_repair":
        if strategy_family == "destroy_repair_recovery":
            return threshold
        return max(threshold, _BOUNDED_DESTROY_REPAIR_MIN_DISTANCE_IMPROVEMENT)
    return threshold


def _main_search_component_candidate(
    component: str,
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
    mechanism_policies: Mapping[str, Any] | None = None,
    rng: random.Random | None = None,
    time_limit_sec: float | None = None,
    start_time: float | None = None,
    instance_path: str | Path | None = None,
    seed: int | None = None,
) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
    if component == "intra_route_2opt":
        candidate, attempts = _best_intra_route_2opt(
            solution,
            instance,
            adapter=adapter,
            current_objective=current_objective,
            top_k=top_k,
        )
        return candidate, attempts, {}
    if component == "inter_route_relocate":
        candidate, attempts = _best_inter_route_relocate(
            solution,
            instance,
            adapter=adapter,
            current_objective=current_objective,
            top_k=top_k,
        )
        return candidate, attempts, {}
    if component == "route_pair_swap":
        previous_generated = 0
        previous_pruned = 0
        if isinstance(mechanism_policies, Mapping):
            previous_generated = _as_nonnegative_int(
                mechanism_policies.get("route_pair_candidates_generated")
            )
            previous_pruned = _as_nonnegative_int(
                mechanism_policies.get("route_pair_candidates_pruned")
            )
        candidate, attempts = _best_route_pair_swap(
            solution,
            instance,
            adapter=adapter,
            current_objective=current_objective,
            top_k=top_k,
            route_pair_policy=mechanism_policies,
        )
        telemetry = {}
        if isinstance(mechanism_policies, Mapping):
            current_generated = _as_nonnegative_int(
                mechanism_policies.get("route_pair_candidates_generated")
            )
            current_pruned = _as_nonnegative_int(
                mechanism_policies.get("route_pair_candidates_pruned")
            )
            if isinstance(mechanism_policies, dict):
                mechanism_policies["route_pair_candidates_generated"] = previous_generated
                mechanism_policies["route_pair_candidates_pruned"] = previous_pruned
            telemetry = {
                "route_pair_candidates_generated": max(
                    0,
                    current_generated - previous_generated,
                ),
                "route_pair_candidates_pruned": max(
                    0,
                    current_pruned - previous_pruned,
                ),
            }
        return candidate, attempts, telemetry
    if component == "bounded_destroy_repair":
        return _best_bounded_destroy_repair(
            solution,
            instance,
            adapter=adapter,
            current_objective=current_objective,
            top_k=top_k,
            destroy_repair_policy=mechanism_policies,
        )
    if component == "route_pool_recombination":
        return _best_route_pool_recombination(
            solution,
            instance,
            adapter=adapter,
            current_objective=current_objective,
            top_k=top_k,
            mechanism_policies=mechanism_policies,
            rng=rng,
            time_limit_sec=time_limit_sec,
            start_time=start_time,
            instance_path=instance_path,
            seed=seed,
        )
    return None, 0, {"skip_reason": "unknown_component"}


def _main_search_component_candidate_choice(
    component: str,
    instance: CvrpInstance,
    *,
    current_solution: CvrpSolution,
    best_solution: CvrpSolution,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    best_objective: Mapping[str, int | float],
    top_k: int,
    min_distance_improvement: float,
    mechanism_policies: Mapping[str, Any] | None = None,
    rng: random.Random | None = None,
    time_limit_sec: float | None = None,
    start_time: float | None = None,
    instance_path: str | Path | None = None,
    seed: int | None = None,
) -> tuple[CvrpSolution | None, int, dict[str, Any], dict[str, Any]]:
    """Choose a component move, preferring phase-best improvements over recovery."""
    total_attempts = 0
    combined_telemetry: dict[str, Any] = {}
    options: list[dict[str, Any]] = []

    probes: list[tuple[str, CvrpSolution, Mapping[str, int | float]]] = [
        ("current", current_solution, current_objective)
    ]
    if best_solution.routes != current_solution.routes:
        probes.append(("phase_best", best_solution, best_objective))
    if component == "route_pool_recombination" and best_solution.routes != current_solution.routes:
        probes = [("phase_best", best_solution, best_objective)]

    saw_candidate = False
    for source, source_solution, source_objective in probes:
        candidate_kwargs: dict[str, Any] = {
            "adapter": adapter,
            "current_objective": source_objective,
            "top_k": top_k,
            "mechanism_policies": mechanism_policies,
        }
        if component == "route_pool_recombination":
            candidate_kwargs.update(
                {
                    "rng": rng,
                    "time_limit_sec": time_limit_sec,
                    "start_time": start_time,
                    "instance_path": instance_path,
                    "seed": seed,
                }
            )
        candidate, attempts, telemetry = _main_search_component_candidate(
            component,
            source_solution,
            instance,
            **candidate_kwargs,
        )
        total_attempts += attempts
        combined_telemetry = _merge_main_search_component_telemetry(
            combined_telemetry,
            telemetry,
        )
        if candidate is None:
            continue
        saw_candidate = True
        objective = _objective_for_solution(adapter, instance, candidate)
        source_delta = _objective_distance_delta(source_objective, objective)
        current_delta = _objective_distance_delta(current_objective, objective)
        phase_delta = _objective_distance_delta(best_objective, objective)
        improves_current = _main_search_accepts(
            objective,
            current_objective,
            min_distance_improvement=min_distance_improvement,
        )
        improves_phase = _main_search_accepts(
            objective,
            best_objective,
            min_distance_improvement=min_distance_improvement,
        )
        recovery_policy = ""
        if isinstance(mechanism_policies, Mapping):
            recovery_policy = str(mechanism_policies.get("recovery_only_policy") or "")
        if recovery_policy == "reject_recovery_only" and not improves_phase:
            combined_telemetry["skip_reason"] = "recovery_only_rejected"
            continue
        if not (improves_current or improves_phase):
            continue
        options.append(
            {
                "source": source,
                "candidate": candidate,
                "objective": objective,
                "accepted_delta": source_delta,
                "current_delta": current_delta,
                "phase_delta": phase_delta,
                "improves_phase": improves_phase,
            }
        )

    if not options:
        if saw_candidate and not combined_telemetry.get("skip_reason"):
            combined_telemetry["skip_reason"] = "candidate_below_acceptance_threshold"
        return None, total_attempts, combined_telemetry, {}

    options.sort(
        key=lambda option: (
            0 if option["improves_phase"] else 1,
            -float(
                option["phase_delta"]
                if option["improves_phase"]
                else option["current_delta"]
            ),
            0 if option["source"] == "phase_best" else 1,
        )
    )
    selected = options[0]
    return (
        selected["candidate"],
        total_attempts,
        combined_telemetry,
        selected,
    )


def _merge_main_search_component_telemetry(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    combined = dict(left)
    for key in (
        "removed_count",
        "reinserted_count",
        "repair_fallback_count",
        "destroy_subset_count",
        "route_pair_candidates_generated",
        "route_pair_candidates_pruned",
        "route_pool_source_solutions",
        "route_pool_size",
        "route_pool_branch_calls",
        "route_pool_recombined_routes",
        "route_pool_sample_count",
    ):
        combined[key] = _as_nonnegative_int(combined.get(key)) + _as_nonnegative_int(
            right.get(key) if isinstance(right, Mapping) else 0
        )
    if not combined.get("skip_reason") and isinstance(right, Mapping):
        reason = right.get("skip_reason")
        if isinstance(reason, str) and reason.strip():
            combined["skip_reason"] = reason.strip()
    return combined


def improve_with_algorithm_blueprint(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    rng: random.Random,
    time_limit_sec: float,
    start_time: float,
    algorithm_blueprint: dict[str, Any] | None = None,
) -> tuple[CvrpSolution, dict[str, Any]]:
    if not _algorithm_blueprint_active(algorithm_blueprint):
        return solution, {}

    assert algorithm_blueprint is not None
    audit = dict(algorithm_blueprint)
    _append_algorithm_phase(audit, "baseline")
    audit.setdefault("algorithm_phase_runtime_ms", {}).setdefault("baseline", 0)
    components = [
        component
        for component in audit.get("algorithm_local_search_components", [])
        if component in _ALLOWED_BLUEPRINT_LOCAL_SEARCH_COMPONENTS
    ]
    rounds = _as_nonnegative_int(audit.get("algorithm_local_search_rounds", 0))
    top_k = _as_nonnegative_int(audit.get("algorithm_local_search_top_k", 16))
    if not components or rounds <= 0 or top_k <= 0:
        audit["algorithm_stop_reason"] = "local_search_disabled"
        return solution, audit

    phase_start_ns = time.monotonic_ns()
    initial_objective = _objective_for_solution(adapter, instance, solution)
    current = solution
    current_objective = dict(initial_objective)
    no_improvement_rounds = 0
    stop_reason = "max_local_search_rounds"

    _append_algorithm_phase(audit, "local_search")
    for round_index in range(rounds):
        if _time_exhausted(start_time, time_limit_sec):
            stop_reason = "time_limit"
            break
        audit["algorithm_local_search_rounds"] = round_index + 1
        round_accepted = 0
        for component in components:
            if _time_exhausted(start_time, time_limit_sec):
                stop_reason = "time_limit"
                break
            component_start_ns = time.monotonic_ns()
            if component == "intra_route_2opt":
                candidate, attempts = _best_intra_route_2opt(
                    current,
                    instance,
                    adapter=adapter,
                    current_objective=current_objective,
                    top_k=top_k,
                )
            elif component == "inter_route_relocate":
                candidate, attempts = _best_inter_route_relocate(
                    current,
                    instance,
                    adapter=adapter,
                    current_objective=current_objective,
                    top_k=top_k,
                )
            else:
                candidate, attempts = None, 0
            audit["algorithm_local_search_attempts"] = (
                _as_nonnegative_int(audit.get("algorithm_local_search_attempts")) + attempts
            )
            _record_algorithm_component_runtime(audit, component, component_start_ns)
            if candidate is None:
                continue
            candidate_objective = _objective_for_solution(adapter, instance, candidate)
            if _lexicographic_improves(candidate_objective, current_objective):
                current = candidate
                current_objective = candidate_objective
                audit["algorithm_local_search_accepted"] = (
                    _as_nonnegative_int(audit.get("algorithm_local_search_accepted")) + 1
                )
                round_accepted += 1
        if stop_reason == "time_limit":
            break
        if round_accepted > 0:
            no_improvement_rounds = 0
            continue
        no_improvement_rounds += 1
        stagnation_limit = _as_nonnegative_int(
            audit.get("algorithm_restart_stagnation_rounds", 0)
        )
        if bool(audit.get("algorithm_restart_enabled")) and stagnation_limit:
            if no_improvement_rounds >= stagnation_limit:
                audit["algorithm_restart_count"] = (
                    _as_nonnegative_int(audit.get("algorithm_restart_count")) + 1
                )
                stop_reason = "restart_stagnation_limit"
                break
        else:
            stop_reason = "no_local_search_improvement"
            break

    _set_algorithm_phase_runtime(audit, "local_search", phase_start_ns)
    audit.setdefault("algorithm_best_delta_by_phase", {})[
        "local_search"
    ] = _objective_distance_delta(initial_objective, current_objective)
    audit["algorithm_stop_reason"] = stop_reason
    return current, audit


def _best_intra_route_2opt(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
) -> tuple[CvrpSolution | None, int]:
    routes = [list(route) for route in solution.routes]
    best_solution: CvrpSolution | None = None
    best_objective: Mapping[str, int | float] = current_objective
    attempts = 0
    for route_index, route in enumerate(routes):
        if len(route) < 2:
            continue
        for i in range(len(route) - 1):
            for j in range(i + 1, len(route)):
                if attempts >= top_k:
                    return best_solution, attempts
                attempts += 1
                candidate_routes = [list(item) for item in routes]
                candidate_routes[route_index] = (
                    route[:i] + list(reversed(route[i : j + 1])) + route[j + 1 :]
                )
                candidate = CvrpSolution(
                    routes=tuple(tuple(item) for item in candidate_routes if item)
                )
                objective = _objective_for_solution(adapter, instance, candidate)
                if _lexicographic_improves(objective, best_objective):
                    best_solution = candidate
                    best_objective = objective
    return best_solution, attempts


def _best_inter_route_relocate(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
) -> tuple[CvrpSolution | None, int]:
    routes = [list(route) for route in solution.routes]
    best_solution: CvrpSolution | None = None
    best_objective: Mapping[str, int | float] = current_objective
    attempts = 0
    for source_index, source_route in enumerate(routes):
        for customer_pos, customer in enumerate(source_route):
            for dest_index, dest_route in enumerate(routes):
                if dest_index == source_index:
                    continue
                for insert_pos in range(len(dest_route) + 1):
                    if attempts >= top_k:
                        return best_solution, attempts
                    attempts += 1
                    candidate_routes = [list(item) for item in routes]
                    moved = candidate_routes[source_index].pop(customer_pos)
                    candidate_routes[dest_index].insert(insert_pos, moved)
                    if instance.route_load(tuple(candidate_routes[dest_index])) > instance.capacity:
                        continue
                    normalized_routes = [
                        tuple(route) for route in candidate_routes if route
                    ]
                    candidate = CvrpSolution(routes=tuple(normalized_routes))
                    valid, _reason = _solution_is_valid(adapter, instance, candidate)
                    if not valid:
                        continue
                    objective = _objective_for_solution(adapter, instance, candidate)
                    if _lexicographic_improves(objective, best_objective):
                        best_solution = candidate
                        best_objective = objective
    return best_solution, attempts


def _best_route_pair_swap(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
    route_pair_policy: Mapping[str, Any] | None = None,
) -> tuple[CvrpSolution | None, int]:
    routes = [list(route) for route in solution.routes]
    ranked_swaps = _rank_route_pair_swap_candidates(
        routes,
        instance,
        top_k=top_k,
        route_pair_policy=route_pair_policy,
    )
    best_solution: CvrpSolution | None = None
    best_objective: Mapping[str, int | float] = current_objective
    attempts = 0
    for _estimated_delta, left_index, right_index, left_pos, right_pos in ranked_swaps:
        if attempts >= top_k:
            return best_solution, attempts
        attempts += 1
        candidate_routes = [list(item) for item in routes]
        (
            candidate_routes[left_index][left_pos],
            candidate_routes[right_index][right_pos],
        ) = (
            candidate_routes[right_index][right_pos],
            candidate_routes[left_index][left_pos],
        )
        if (
            instance.route_load(tuple(candidate_routes[left_index])) > instance.capacity
            or instance.route_load(tuple(candidate_routes[right_index]))
            > instance.capacity
        ):
            continue
        candidate = CvrpSolution(
            routes=tuple(tuple(route) for route in candidate_routes if route)
        )
        valid, _reason = _solution_is_valid(adapter, instance, candidate)
        if not valid:
            continue
        objective = _objective_for_solution(adapter, instance, candidate)
        if _lexicographic_improves(objective, best_objective):
            best_solution = candidate
            best_objective = objective
    return best_solution, attempts


def _best_bounded_destroy_repair(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
    destroy_repair_policy: Mapping[str, Any] | None = None,
) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
    routes = [list(route) for route in solution.routes]
    telemetry = {
        "removed_count": 0,
        "reinserted_count": 0,
        "repair_fallback_count": 0,
        "skip_reason": "",
    }
    customer_count = sum(len(route) for route in routes)
    if customer_count < 2 or top_k <= 0:
        telemetry["skip_reason"] = "insufficient_destroy_budget"
        return None, 0, telemetry

    destroy_count = _bounded_destroy_count(
        customer_count,
        top_k,
        destroy_repair_policy=destroy_repair_policy,
    )
    removable = _rank_destroy_repair_customers(
        routes,
        instance,
        destroy_repair_policy=destroy_repair_policy,
    )
    if len(removable) < destroy_count:
        telemetry["skip_reason"] = "insufficient_removal_candidates"
        return None, 0, telemetry

    total_attempts = 0
    best_solution: CvrpSolution | None = None
    best_objective: Mapping[str, int | float] = current_objective
    best_removed = 0
    best_reinserted = 0
    last_reason = ""

    subsets = _bounded_destroy_repair_subsets(
        removable,
        destroy_count,
        destroy_repair_policy=destroy_repair_policy,
    )
    telemetry["destroy_subset_count"] = len(subsets)
    for subset_index, selected in enumerate(subsets):
        remaining_budget = top_k - total_attempts
        if remaining_budget <= 0:
            if not last_reason:
                last_reason = "repair_budget_exhausted"
            break
        if total_attempts > 0:
            telemetry["repair_fallback_count"] += 1
        base_routes, removed_customers, removal_reason = _remove_destroy_subset(
            routes,
            selected,
        )
        if base_routes is None:
            telemetry["skip_reason"] = removal_reason
            return None, total_attempts, telemetry

        subset_budget = _bounded_destroy_repair_subset_budget(
            remaining_budget,
            selected_count=len(selected),
            remaining_subsets=len(subsets) - subset_index,
            destroy_repair_policy=destroy_repair_policy,
        )
        repaired_routes, attempts, reinserted_count, repair_reason = (
            _repair_destroyed_customers_with_policy(
                base_routes,
                removed_customers,
                instance,
                top_k=subset_budget,
                destroy_repair_policy=destroy_repair_policy,
            )
        )
        total_attempts += attempts
        if reinserted_count != len(removed_customers):
            last_reason = repair_reason or "incomplete_repair"
            best_removed = max(best_removed, len(removed_customers))
            best_reinserted = max(best_reinserted, reinserted_count)
            continue

        candidate = CvrpSolution(
            routes=tuple(tuple(route) for route in repaired_routes if route)
        )
        valid, _reason = _solution_is_valid(adapter, instance, candidate)
        if not valid:
            last_reason = "invalid_repair_solution"
            best_removed = max(best_removed, len(removed_customers))
            best_reinserted = max(best_reinserted, reinserted_count)
            continue
        objective = _objective_for_solution(adapter, instance, candidate)
        best_removed = max(best_removed, len(removed_customers))
        best_reinserted = max(best_reinserted, reinserted_count)
        if _lexicographic_improves(objective, best_objective):
            best_solution = candidate
            best_objective = objective
            telemetry["removed_count"] = len(removed_customers)
            telemetry["reinserted_count"] = reinserted_count
        else:
            last_reason = "repair_produced_no_improvement"

    if best_solution is not None:
        return best_solution, total_attempts, telemetry
    telemetry["removed_count"] = best_removed
    telemetry["reinserted_count"] = best_reinserted
    if (
        last_reason == "repair_budget_exhausted"
        and best_removed > 0
        and best_reinserted == best_removed
    ):
        last_reason = "repair_produced_no_improvement"
    telemetry["skip_reason"] = last_reason or "repair_produced_no_improvement"
    return None, total_attempts, telemetry


def _rank_route_pair_swap_candidates(
    routes: list[list[int]],
    instance: CvrpInstance,
    *,
    top_k: int,
    route_pair_policy: Mapping[str, Any] | None = None,
) -> list[tuple[float, int, int, int, int]]:
    if len(routes) < 2 or top_k <= 0:
        return []

    active_policy = bool(
        route_pair_policy and route_pair_policy.get("route_pair_active")
    )
    scoring_terms = (
        list(route_pair_policy.get("route_pair_scoring_terms", []))
        if active_policy and isinstance(route_pair_policy, Mapping)
        else ["route_distance", "removal_saving", "distance_saving"]
    )
    limits = (
        route_pair_policy.get("route_pair_candidate_limits", {})
        if active_policy and isinstance(route_pair_policy, Mapping)
        else {}
    )
    if not isinstance(limits, Mapping):
        limits = {}
    route_distances = [instance.route_distance(tuple(route)) for route in routes]
    route_loads = [instance.route_load(tuple(route)) for route in routes]
    route_worst_savings = [
        max(
            (_route_removal_saving(route, pos, instance) for pos in range(len(route))),
            default=0.0,
        )
        for route in routes
    ]
    route_pairs: list[tuple[float, int, int]] = []
    for left_index, left_route in enumerate(routes):
        if not left_route:
            continue
        for right_index in range(left_index + 1, len(routes)):
            if not routes[right_index]:
                continue
            score = 0.0
            if "route_distance" in scoring_terms:
                score += route_distances[left_index] + route_distances[right_index]
            if "removal_saving" in scoring_terms:
                score += route_worst_savings[left_index] + route_worst_savings[right_index]
            if "load_gap" in scoring_terms:
                score += abs(route_loads[left_index] - route_loads[right_index])
            route_pairs.append((float(score), left_index, right_index))
    route_pairs.sort(key=lambda item: (-item[0], item[1], item[2]))

    requested_pair_cap = _as_nonnegative_int(limits.get("pair_cap")) if limits else 0
    requested_position_cap = (
        _as_nonnegative_int(limits.get("position_cap")) if limits else 0
    )
    pair_cap = requested_pair_cap or max(1, min(len(route_pairs), max(8, top_k * 2)))
    pair_cap = max(1, min(len(route_pairs), pair_cap))
    position_cap = requested_position_cap or max(2, min(8, top_k + 1))
    position_cap = max(1, min(32, position_cap))
    ranked: list[tuple[float, int, int, int, int]] = []
    seen: set[tuple[int, int, int, int]] = set()
    pruned = 0
    for _score, left_index, right_index in route_pairs[:pair_cap]:
        left_route = routes[left_index]
        right_route = routes[right_index]
        left_positions = _rank_swap_positions(left_route, instance, position_cap)
        right_positions = _rank_swap_positions(right_route, instance, position_cap)
        before_distance = route_distances[left_index] + route_distances[right_index]
        for left_pos in left_positions:
            for right_pos in right_positions:
                key = (left_index, right_index, left_pos, right_pos)
                if key in seen:
                    continue
                seen.add(key)
                candidate_left = list(left_route)
                candidate_right = list(right_route)
                candidate_left[left_pos], candidate_right[right_pos] = (
                    candidate_right[right_pos],
                    candidate_left[left_pos],
                )
                if (
                    instance.route_load(tuple(candidate_left)) > instance.capacity
                    or instance.route_load(tuple(candidate_right)) > instance.capacity
                ):
                    pruned += 1
                    estimated_delta = float("-inf")
                else:
                    estimated_delta = 0.0
                    if "distance_saving" in scoring_terms:
                        after_distance = instance.route_distance(
                            tuple(candidate_left)
                        ) + instance.route_distance(tuple(candidate_right))
                        estimated_delta += float(before_distance - after_distance)
                    if "removal_saving" in scoring_terms:
                        estimated_delta += (
                            _route_removal_saving(left_route, left_pos, instance)
                            + _route_removal_saving(right_route, right_pos, instance)
                        )
                ranked.append(
                    (estimated_delta, left_index, right_index, left_pos, right_pos)
                )
    ranked.sort(key=lambda item: (-item[0], item[1], item[2], item[3], item[4]))
    if active_policy and isinstance(route_pair_policy, dict):
        route_pair_policy["route_pair_candidates_generated"] = (
            _as_nonnegative_int(route_pair_policy.get("route_pair_candidates_generated"))
            + len(ranked)
        )
        route_pair_policy["route_pair_candidates_pruned"] = (
            _as_nonnegative_int(route_pair_policy.get("route_pair_candidates_pruned"))
            + pruned
        )
    return ranked[: max(0, top_k)]


def _rank_swap_positions(
    route: list[int],
    instance: CvrpInstance,
    limit: int,
) -> list[int]:
    records = [
        (
            _route_removal_saving(route, pos, instance),
            pos == 0 or pos == len(route) - 1,
            -pos,
            pos,
        )
        for pos in range(len(route))
    ]
    records.sort(key=lambda item: (-item[0], not item[1], item[2]))
    return [pos for _saving, _is_endpoint, _neg_pos, pos in records[:limit]]


def _rank_worst_removal_customers(
    routes: list[list[int]],
    instance: CvrpInstance,
) -> list[tuple[float, int, int, int]]:
    removable: list[tuple[float, int, int, int]] = []
    for route_index, route in enumerate(routes):
        for pos, customer in enumerate(route):
            removable.append(
                (
                    _route_removal_saving(route, pos, instance),
                    route_index,
                    pos,
                    customer,
                )
            )
    removable.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    return removable


def _rank_destroy_repair_customers(
    routes: list[list[int]],
    instance: CvrpInstance,
    *,
    destroy_repair_policy: Mapping[str, Any] | None = None,
) -> list[tuple[float, int, int, int]]:
    worst_ranked = _rank_worst_removal_customers(routes, instance)
    selectors = _active_destroy_repair_selectors(
        destroy_repair_policy,
        key="destroy_selectors",
        default=("worst_removal",),
    )
    ranked: list[tuple[float, int, int, int]] = []
    seen_customers: set[int] = set()
    for selector in selectors:
        if selector == "route_diverse_worst":
            candidates = _rank_route_diverse_worst_customers(worst_ranked)
        else:
            candidates = worst_ranked
        for item in candidates:
            customer = item[3]
            if customer in seen_customers:
                continue
            seen_customers.add(customer)
            ranked.append(item)
    return ranked or worst_ranked


def _rank_route_diverse_worst_customers(
    worst_ranked: list[tuple[float, int, int, int]],
) -> list[tuple[float, int, int, int]]:
    by_route: dict[int, list[tuple[float, int, int, int]]] = {}
    for item in worst_ranked:
        by_route.setdefault(item[1], []).append(item)
    route_order = sorted(
        by_route,
        key=lambda route_index: (
            -by_route[route_index][0][0],
            route_index,
        ),
    )
    diverse: list[tuple[float, int, int, int]] = []
    depth = 0
    while True:
        added = False
        for route_index in route_order:
            route_items = by_route[route_index]
            if depth >= len(route_items):
                continue
            diverse.append(route_items[depth])
            added = True
        if not added:
            break
        depth += 1
    return diverse


def _bounded_destroy_repair_subsets(
    removable: list[tuple[float, int, int, int]],
    destroy_count: int,
    *,
    destroy_repair_policy: Mapping[str, Any] | None = None,
) -> list[list[tuple[float, int, int, int]]]:
    max_count = min(len(removable), destroy_count)
    if max_count <= 0:
        return []
    active_policy = bool(
        destroy_repair_policy and destroy_repair_policy.get("destroy_repair_active")
    )
    strategy = (
        str(destroy_repair_policy.get("destroy_subset_strategy"))
        if active_policy and isinstance(destroy_repair_policy, Mapping)
        else "prefix_shifted_route_diverse"
    )
    fallback_enabled = True
    if active_policy and isinstance(destroy_repair_policy, Mapping):
        fallback_enabled = bool(
            destroy_repair_policy.get("repair_fallback_enabled", True)
        )
    sizes = [max_count]
    if fallback_enabled:
        for size in (4, 3, 2, 1):
            if 0 < size < max_count and size not in sizes:
                sizes.append(size)

    subsets: list[list[tuple[float, int, int, int]]] = []
    seen: set[tuple[int, ...]] = set()

    def add_subset(items: list[tuple[float, int, int, int]]) -> None:
        if not items:
            return
        key = tuple(sorted(customer for _saving, _route, _pos, customer in items))
        if key in seen:
            return
        seen.add(key)
        subsets.append(items)

    for size in sizes:
        add_subset(removable[:size])
        if strategy == "single_worst":
            continue
    if strategy == "single_worst":
        return subsets[:8]

    for size in sizes:
        if len(removable) > size:
            add_subset(removable[1 : 1 + size])
        if len(removable) > size * 2:
            add_subset(removable[size : size * 2])

        route_diverse: list[tuple[float, int, int, int]] = []
        used_routes: set[int] = set()
        for item in removable:
            _saving, route_index, _pos, _customer = item
            if route_index in used_routes:
                continue
            route_diverse.append(item)
            used_routes.add(route_index)
            if len(route_diverse) >= size:
                break
        if strategy in {"prefix_shifted_route_diverse", "route_diverse"}:
            add_subset(route_diverse)

    return subsets[:8]


def _bounded_destroy_repair_subset_budget(
    remaining_budget: int,
    *,
    selected_count: int,
    remaining_subsets: int,
    destroy_repair_policy: Mapping[str, Any] | None = None,
) -> int:
    if remaining_budget <= 0:
        return 0
    if remaining_subsets <= 1:
        return remaining_budget
    fallback_enabled = True
    repair_budget = 4
    if destroy_repair_policy and destroy_repair_policy.get("destroy_repair_active"):
        fallback_enabled = bool(
            destroy_repair_policy.get("repair_fallback_enabled", True)
        )
        repair_budget = (
            _as_nonnegative_int(destroy_repair_policy.get("repair_budget_per_customer"))
            or repair_budget
        )
    if not fallback_enabled:
        return remaining_budget
    minimum_completion_budget = max(
        selected_count,
        selected_count * (selected_count + 1) // 2,
    )
    if remaining_budget <= minimum_completion_budget:
        return remaining_budget
    reserve_per_later_subset = max(1, min(8, repair_budget))
    reserve = min(
        remaining_budget - minimum_completion_budget,
        remaining_budget // 2,
        max(0, remaining_subsets - 1) * reserve_per_later_subset,
    )
    return max(minimum_completion_budget, remaining_budget - reserve)


def _best_route_pool_recombination(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
    mechanism_policies: Mapping[str, Any] | None = None,
    rng: random.Random | None = None,
    time_limit_sec: float | None = None,
    start_time: float | None = None,
    instance_path: str | Path | None = None,
    seed: int | None = None,
) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
    telemetry: dict[str, Any] = {
        "route_pool_source_solutions": 1,
        "route_pool_size": 0,
        "route_pool_branch_calls": 0,
        "route_pool_recombined_routes": 0,
        "route_pool_sample_count": 0,
        "skip_reason": "",
    }
    if top_k <= 0:
        telemetry["skip_reason"] = "route_pool_budget_exhausted"
        return None, 0, telemetry

    pool_solutions = [solution]
    if isinstance(mechanism_policies, Mapping):
        construction_pool = mechanism_policies.get(
            "_main_search_construction_pool_solutions"
        )
        if isinstance(construction_pool, list):
            for construction_solution in construction_pool:
                if not isinstance(construction_solution, CvrpSolution):
                    continue
                if any(
                    construction_solution.routes == existing.routes
                    for existing in pool_solutions
                ):
                    continue
                valid, _reason = _solution_is_valid(
                    adapter,
                    instance,
                    construction_solution,
                )
                if valid:
                    pool_solutions.append(construction_solution)
    sample_attempts = 0
    sample_rng = rng if rng is not None else random.Random(seed)
    baseline_root = _find_vrp_baseline_root()
    resolved_instance_path = (
        Path(instance_path).resolve(strict=False) if instance_path is not None else None
    )
    exit_reserve_sec = _bounded_exit_reserve_sec(
        time_limit_sec,
        _ROUTE_POOL_EXIT_RESERVE_SEC,
    )
    remaining_time = _remaining_time_sec(start_time, time_limit_sec)
    if (
        baseline_root is not None
        and resolved_instance_path is not None
        and resolved_instance_path.suffix.lower() == ".vrp"
        and remaining_time
        > exit_reserve_sec + _ROUTE_POOL_MIN_SAMPLE_BUDGET_SEC
    ):
        sample_cap = _route_pool_sample_cap(top_k)
        usable_time = max(0.0, remaining_time - exit_reserve_sec)
        per_sample_budget = min(
            _ROUTE_POOL_MAX_SAMPLE_BUDGET_SEC,
            usable_time / max(1.0, sample_cap + 0.5),
        )
        baseline_params = {}
        if isinstance(mechanism_policies, Mapping):
            raw_params = mechanism_policies.get("main_search_baseline_params")
            if isinstance(raw_params, Mapping):
                baseline_params = dict(raw_params)
        if per_sample_budget >= _ROUTE_POOL_MIN_SAMPLE_BUDGET_SEC:
            for sample_index in range(sample_cap):
                remaining = _remaining_time_sec(start_time, time_limit_sec)
                sample_budget = min(
                    per_sample_budget,
                    max(0.0, remaining - exit_reserve_sec),
                )
                if sample_budget < _ROUTE_POOL_MIN_SAMPLE_BUDGET_SEC:
                    break
                sample_seed = _route_pool_sample_seed(
                    seed,
                    sample_index,
                    sample_rng,
                )
                try:
                    sampled_solution, _sample_audit = _solve_with_vrp_baseline(
                        instance=instance,
                        instance_path=resolved_instance_path,
                        seed=sample_seed,
                        time_limit_sec=sample_budget,
                        baseline_root=baseline_root,
                        baseline_required=_baseline_required_for_instance(
                            resolved_instance_path
                        ),
                        baseline_policy_params=baseline_params,
                    )
                except Exception:
                    continue
                sample_attempts += 1
                valid, _reason = _solution_is_valid(adapter, instance, sampled_solution)
                if valid:
                    pool_solutions.append(sampled_solution)
    telemetry["route_pool_sample_count"] = sample_attempts

    candidate, branch_calls, pool_telemetry = _route_pool_recombination_from_solutions(
        solution,
        pool_solutions,
        instance,
        adapter=adapter,
        current_objective=current_objective,
        top_k=top_k,
        start_time=start_time,
        time_limit_sec=time_limit_sec,
        exit_reserve_sec=exit_reserve_sec,
    )
    telemetry.update(pool_telemetry)
    attempts = sample_attempts + branch_calls
    if candidate is None:
        if not telemetry.get("skip_reason"):
            telemetry["skip_reason"] = "route_pool_no_improvement"
        return None, attempts, telemetry
    return candidate, attempts, telemetry


def _route_pool_sample_cap(top_k: int) -> int:
    if top_k <= 0:
        return 0
    return max(4, min(8, max(4, top_k // 16)))


def _route_pool_sample_seed(
    seed: int | None,
    sample_index: int,
    sample_rng: random.Random,
) -> int:
    base_seed = _as_nonnegative_int(seed) if seed is not None else 0
    round_offset = sample_rng.randrange(1, 1_000_000)
    return base_seed + 1000 * (sample_index + 1) + round_offset


def _route_pool_recombination_from_solutions(
    solution: CvrpSolution,
    pool_solutions: list[CvrpSolution],
    instance: CvrpInstance,
    *,
    adapter: CvrpAdapter,
    current_objective: Mapping[str, int | float],
    top_k: int,
    start_time: float | None = None,
    time_limit_sec: float | None = None,
    exit_reserve_sec: float = _ROUTE_POOL_EXIT_RESERVE_SEC,
) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
    customers = frozenset(instance.customer_ids)
    route_by_customers: dict[frozenset[int], tuple[float, tuple[int, ...]]] = {}
    for pool_solution in pool_solutions:
        for route in pool_solution.routes:
            route_tuple = tuple(route)
            polished_route, _polish_attempts = _route_pool_polish_route_order(
                route_tuple,
                instance,
                max_attempts=max(16, min(256, max(1, top_k) * 8)),
            )
            route_variants = (route_tuple, polished_route)
            for variant in route_variants:
                route_customers = frozenset(variant)
                if (
                    not route_customers
                    or len(route_customers) != len(variant)
                    or not route_customers <= customers
                    or instance.route_load(variant) > instance.capacity
                ):
                    continue
                route_cost = float(instance.route_distance(variant))
                previous = route_by_customers.get(route_customers)
                if previous is None or route_cost < previous[0] - _OBJECTIVE_TOLERANCE:
                    route_by_customers[route_customers] = (route_cost, variant)

    route_entries = [
        (cost, route, route_customers)
        for route_customers, (cost, route) in route_by_customers.items()
    ]
    route_entries.sort(key=lambda item: (item[0] / len(item[2]), item[0], item[1]))
    telemetry: dict[str, Any] = {
        "route_pool_source_solutions": len(pool_solutions),
        "route_pool_size": len(route_entries),
        "route_pool_branch_calls": 0,
        "route_pool_recombined_routes": 0,
    }
    if not route_entries:
        telemetry["skip_reason"] = "route_pool_empty"
        return None, 0, telemetry
    if _route_pool_time_exhausted(
        start_time,
        time_limit_sec,
        exit_reserve_sec=exit_reserve_sec,
    ):
        telemetry["skip_reason"] = "route_pool_time_limit"
        return None, 0, telemetry

    allowed_routes = instance.allowed_routes
    if allowed_routes is None:
        allowed_routes = instance.bks_routes
    route_limit = allowed_routes if allowed_routes is not None else len(solution.routes)
    route_limit = max(1, route_limit)
    current_distance = float(current_objective.get("total_distance", 0.0))
    current_fleet = float(current_objective.get("fleet_violation", 0.0))
    best_solution: CvrpSolution | None = None
    best_objective: Mapping[str, int | float] = current_objective
    best_distance = current_distance

    by_customer: dict[int, list[int]] = {customer: [] for customer in customers}
    for index, (_cost, _route, route_customers) in enumerate(route_entries):
        for customer in route_customers:
            by_customer[customer].append(index)
    for indices in by_customer.values():
        indices.sort(
            key=lambda index: (
                route_entries[index][0] / len(route_entries[index][2]),
                route_entries[index][0],
                route_entries[index][1],
            )
        )

    branch_calls = 0
    branch_call_limit = max(1000, min(250_000, max(1, top_k) * 1000))
    option_cap = max(8, min(64, max(1, top_k)))

    def maybe_update_best(candidate: CvrpSolution) -> None:
        nonlocal best_solution, best_objective, best_distance
        valid, _reason = _solution_is_valid(adapter, instance, candidate)
        if not valid:
            return
        objective = _objective_for_solution(adapter, instance, candidate)
        if _lexicographic_improves(objective, best_objective):
            best_solution = candidate
            best_objective = objective
            best_distance = float(objective.get("total_distance", best_distance))

    def recombination_time_exhausted() -> bool:
        return _route_pool_time_exhausted(
            start_time,
            time_limit_sec,
            exit_reserve_sec=exit_reserve_sec,
        )

    def try_incumbent_residual_completion(chosen: list[int]) -> None:
        if not chosen:
            return
        covered: set[int] = set()
        candidate_routes: list[tuple[int, ...]] = []
        for index in chosen:
            _cost, route, route_customers = route_entries[index]
            if covered & route_customers:
                return
            covered.update(route_customers)
            candidate_routes.append(route)
        for route in solution.routes:
            residual = tuple(customer for customer in route if customer not in covered)
            if residual:
                candidate_routes.append(residual)
        if len(candidate_routes) > route_limit:
            return
        maybe_update_best(CvrpSolution(routes=tuple(candidate_routes)))

    injection_index_limit = min(len(route_entries), max(8, min(64, max(1, top_k) * 2)))
    injection_pair_limit = min(len(route_entries), max(8, min(40, max(1, top_k))))
    for left in range(injection_index_limit):
        if recombination_time_exhausted():
            break
        branch_calls += 1
        try_incumbent_residual_completion([left])
        if branch_calls >= branch_call_limit:
            break
    if branch_calls < branch_call_limit:
        for left in range(injection_pair_limit):
            if recombination_time_exhausted():
                break
            for right in range(left + 1, injection_pair_limit):
                if recombination_time_exhausted():
                    break
                branch_calls += 1
                try_incumbent_residual_completion([left, right])
                if branch_calls >= branch_call_limit:
                    break
            if branch_calls >= branch_call_limit:
                break

    def dfs(
        uncovered: frozenset[int],
        chosen: list[int],
        distance: float,
    ) -> None:
        nonlocal branch_calls, best_solution, best_objective, best_distance
        if recombination_time_exhausted():
            return
        if branch_calls >= branch_call_limit:
            return
        branch_calls += 1
        if current_fleet <= 0.0 and distance >= best_distance - _OBJECTIVE_TOLERANCE:
            return
        if len(chosen) > route_limit:
            return
        if not uncovered:
            candidate = CvrpSolution(
                routes=tuple(route_entries[index][1] for index in chosen)
            )
            maybe_update_best(candidate)
            return
        if len(chosen) >= route_limit:
            return

        def feasible_count(customer: int) -> int:
            return sum(
                1
                for index in by_customer.get(customer, [])
                if route_entries[index][2] <= uncovered
            )

        pivot = min(uncovered, key=lambda customer: (feasible_count(customer), customer))
        options = [
            index
            for index in by_customer.get(pivot, [])
            if route_entries[index][2] <= uncovered
        ][:option_cap]
        if not options:
            return
        for index in options:
            if recombination_time_exhausted():
                return
            cost, _route, route_customers = route_entries[index]
            dfs(uncovered - route_customers, [*chosen, index], distance + cost)
            if branch_calls >= branch_call_limit:
                return

    dfs(customers, [], 0.0)
    telemetry["route_pool_branch_calls"] = branch_calls
    if best_solution is None:
        telemetry["skip_reason"] = (
            "route_pool_time_limit"
            if recombination_time_exhausted()
            else "route_pool_no_improvement"
        )
        return None, branch_calls, telemetry
    telemetry["route_pool_recombined_routes"] = len(best_solution.routes)
    return best_solution, branch_calls, telemetry


def _route_pool_polish_route_order(
    route: tuple[int, ...],
    instance: CvrpInstance,
    *,
    max_attempts: int,
) -> tuple[tuple[int, ...], int]:
    if len(route) < 4 or max_attempts <= 0:
        return route, 0
    best = tuple(route)
    best_distance = float(instance.route_distance(best))
    attempts = 0
    improved = True
    while improved and attempts < max_attempts:
        improved = False
        for left in range(len(best) - 1):
            for right in range(left + 1, len(best)):
                attempts += 1
                candidate = (
                    best[:left]
                    + tuple(reversed(best[left : right + 1]))
                    + best[right + 1 :]
                )
                candidate_distance = float(instance.route_distance(candidate))
                if candidate_distance < best_distance - _OBJECTIVE_TOLERANCE:
                    best = candidate
                    best_distance = candidate_distance
                    improved = True
                    break
                if attempts >= max_attempts:
                    break
            if improved or attempts >= max_attempts:
                break
    return best, attempts


def _remove_destroy_subset(
    routes: list[list[int]],
    selected: list[tuple[float, int, int, int]],
) -> tuple[list[list[int]] | None, list[int], str]:
    base_routes = [list(route) for route in routes]
    removed_customers = [
        customer for _saving, _route_index, _pos, customer in selected
    ]
    for _saving, route_index, pos, customer in sorted(
        selected,
        key=lambda item: (item[1], item[2]),
        reverse=True,
    ):
        if route_index >= len(base_routes) or pos >= len(base_routes[route_index]):
            return None, removed_customers, "stale_removal_position"
        removed = base_routes[route_index].pop(pos)
        if removed != customer:
            return None, removed_customers, "stale_removal_customer"
    return base_routes, removed_customers, ""


def _route_removal_saving(
    route: list[int],
    pos: int,
    instance: CvrpInstance,
) -> float:
    customer = route[pos]
    prev_node = instance.depot if pos == 0 else route[pos - 1]
    next_node = instance.depot if pos == len(route) - 1 else route[pos + 1]
    return float(
        instance.distance(prev_node, customer)
        + instance.distance(customer, next_node)
        - instance.distance(prev_node, next_node)
    )


def _bounded_destroy_count(
    customer_count: int,
    top_k: int,
    *,
    destroy_repair_policy: Mapping[str, Any] | None = None,
) -> int:
    if customer_count <= 1:
        return customer_count
    budget_count = max(2, min(6, max(2, top_k // 4)))
    if destroy_repair_policy and destroy_repair_policy.get("destroy_repair_active"):
        budget_count = min(
            budget_count,
            _as_nonnegative_int(destroy_repair_policy.get("destroy_max_customers")) or budget_count,
        )
    return min(max(2, customer_count - 1), budget_count)


def _repair_destroyed_customers_with_policy(
    base_routes: list[list[int]],
    removed_customers: list[int],
    instance: CvrpInstance,
    *,
    top_k: int,
    destroy_repair_policy: Mapping[str, Any] | None = None,
) -> tuple[list[list[int]], int, int, str]:
    routes = [list(route) for route in base_routes]
    pending = list(removed_customers)
    attempts = 0
    reinserted_count = 0
    repair_selector = _active_destroy_repair_selectors(
        destroy_repair_policy,
        key="repair_selectors",
        default=("regret_2",),
    )[0]
    while pending:
        if attempts >= top_k:
            return routes, attempts, reinserted_count, "repair_budget_exhausted"
        remaining_budget = max(0, top_k - attempts)
        per_customer_budget = _repair_candidate_budget_per_customer(
            remaining_budget,
            len(pending),
            destroy_repair_policy=destroy_repair_policy,
        )
        if repair_selector == "cheapest":
            customer = pending[0]
            customer_budget = min(per_customer_budget, top_k - attempts)
            if customer_budget <= 0:
                return routes, attempts, reinserted_count, "repair_budget_exhausted"
            insertions = _bounded_regret_insertions(
                routes,
                customer,
                instance,
                remaining_budget=customer_budget,
            )
            attempts += len(insertions)
            if not insertions:
                reason = (
                    "repair_budget_exhausted"
                    if attempts >= top_k
                    else "no_feasible_insertion"
                )
                return routes, attempts, reinserted_count, reason
            insertion = insertions[0]
            if insertion.route_index == len(routes):
                routes.append([customer])
            else:
                routes[insertion.route_index].insert(insertion.insert_pos, customer)
            pending.remove(customer)
            reinserted_count += 1
            continue
        ranked_customers: list[
            tuple[float, float, int, _RepairInsertion, list[_RepairInsertion]]
        ] = []
        for customer in pending:
            customer_budget = min(per_customer_budget, top_k - attempts)
            if customer_budget <= 0:
                break
            insertions = _bounded_regret_insertions(
                routes,
                customer,
                instance,
                remaining_budget=customer_budget,
            )
            attempts += len(insertions)
            if not insertions:
                continue
            best = insertions[0]
            if len(insertions) >= 2:
                regret = insertions[1].delta - best.delta
            else:
                regret = float("inf")
            ranked_customers.append((regret, best.delta, customer, best, insertions))
        if not ranked_customers:
            reason = "repair_budget_exhausted" if attempts >= top_k else "no_feasible_insertion"
            return routes, attempts, reinserted_count, reason
        ranked_customers.sort(key=lambda item: (-item[0], item[1], item[2]))
        _regret, _best_delta, customer, insertion, _insertions = ranked_customers[0]
        if insertion.route_index == len(routes):
            routes.append([customer])
        else:
            routes[insertion.route_index].insert(insertion.insert_pos, customer)
        pending.remove(customer)
        reinserted_count += 1
    return routes, attempts, reinserted_count, ""


def _active_destroy_repair_selectors(
    destroy_repair_policy: Mapping[str, Any] | None,
    *,
    key: str,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    if not (
        destroy_repair_policy
        and destroy_repair_policy.get("destroy_repair_active")
        and isinstance(destroy_repair_policy, Mapping)
    ):
        return default
    raw = destroy_repair_policy.get(key)
    if not isinstance(raw, (list, tuple)):
        return default
    selectors = tuple(str(item).strip() for item in raw if str(item).strip())
    return selectors or default


def _repair_candidate_budget_per_customer(
    remaining_budget: int,
    pending_count: int,
    *,
    destroy_repair_policy: Mapping[str, Any] | None = None,
) -> int:
    if remaining_budget <= 0 or pending_count <= 0:
        return 0
    default_budget = max(1, min(4, remaining_budget // pending_count))
    if destroy_repair_policy and destroy_repair_policy.get("destroy_repair_active"):
        requested = _as_nonnegative_int(
            destroy_repair_policy.get("repair_budget_per_customer")
        )
        if requested:
            return max(1, min(requested, remaining_budget))
    completion_budget = pending_count * (pending_count + 1) // 2
    return max(1, min(default_budget, remaining_budget // max(1, completion_budget)))


class _RepairInsertion:
    def __init__(self, route_index: int, insert_pos: int, delta: float) -> None:
        self.route_index = route_index
        self.insert_pos = insert_pos
        self.delta = delta


def _bounded_regret_insertions(
    routes: list[list[int]],
    customer: int,
    instance: CvrpInstance,
    *,
    remaining_budget: int,
) -> list[_RepairInsertion]:
    if remaining_budget <= 0:
        return []
    records: list[_RepairInsertion] = []
    demand = instance.demand(customer)
    per_route_cap = max(1, min(8, remaining_budget))
    for route_index, route in enumerate(routes):
        if instance.route_load(tuple(route)) + demand > instance.capacity:
            continue
        route_records = [
            _RepairInsertion(
                route_index,
                insert_pos,
                _insertion_delta(route, customer, insert_pos, instance),
            )
            for insert_pos in range(len(route) + 1)
        ]
        route_records.sort(
            key=lambda item: (item.delta, -item.insert_pos, item.route_index)
        )
        take = min(per_route_cap, remaining_budget)
        records.extend(route_records[:take])
    if demand <= instance.capacity:
        records.append(
            _RepairInsertion(
                len(routes),
                0,
                instance.route_distance((customer,)),
            )
        )
    records.sort(key=lambda item: (item.delta, -item.insert_pos, item.route_index))
    return records[:remaining_budget]


def _insertion_delta(
    route: list[int],
    customer: int,
    insert_pos: int,
    instance: CvrpInstance,
) -> float:
    prev_node = instance.depot if insert_pos == 0 else route[insert_pos - 1]
    next_node = instance.depot if insert_pos == len(route) else route[insert_pos]
    return float(
        instance.distance(prev_node, customer)
        + instance.distance(customer, next_node)
        - instance.distance(prev_node, next_node)
    )


def _main_search_accepts(
    candidate: Mapping[str, int | float],
    current: Mapping[str, int | float],
    *,
    min_distance_improvement: float,
) -> bool:
    candidate_fleet = float(candidate.get("fleet_violation", 0))
    current_fleet = float(current.get("fleet_violation", 0))
    if candidate_fleet < current_fleet:
        return True
    if candidate_fleet > current_fleet:
        return False
    candidate_distance = float(candidate.get("total_distance", 0.0))
    current_distance = float(current.get("total_distance", 0.0))
    threshold = max(_OBJECTIVE_TOLERANCE, float(min_distance_improvement))
    return candidate_distance < current_distance - threshold


def _main_search_plan_int(
    audit: Mapping[str, Any],
    section_name: str,
    field_name: str,
) -> int:
    plan = audit.get("main_search_plan")
    if not isinstance(plan, Mapping):
        return 0
    section = plan.get(section_name)
    if not isinstance(section, Mapping):
        return 0
    return _as_nonnegative_int(section.get(field_name))


def _main_search_algorithm_body_skip_reason(
    audit: Mapping[str, Any],
    component: str,
    instance: CvrpInstance,
    *,
    instance_path: str | Path | None = None,
) -> str:
    if component != "route_pool_recombination":
        return ""
    activation = str(
        audit.get("main_search_route_pool_activation", _DEFAULT_ROUTE_POOL_ACTIVATION)
    )
    if activation == "disabled":
        return "algorithm_body_route_pool_disabled"
    if (
        _as_nonnegative_int(audit.get("main_search_route_pool_invocations"))
        >= _as_nonnegative_int(audit.get("main_search_route_pool_max_rounds"))
    ):
        return "algorithm_body_route_pool_round_limit"
    min_customers = _as_nonnegative_int(
        audit.get("main_search_route_pool_min_customers")
    )
    if min_customers <= 0:
        return ""
    customer_count = _as_nonnegative_int(getattr(instance, "customer_count", 0))
    if activation == "medium_large_only" and customer_count < min_customers:
        return "algorithm_body_route_pool_scope"
    if activation == "adaptive":
        if not bool(audit.get("main_search_route_pool_auto_added")):
            return ""
        if not _is_vrp_instance_path(instance_path):
            return ""
        if customer_count < min_customers:
            return "algorithm_body_route_pool_scope"
    return ""


def _is_vrp_instance_path(instance_path: str | Path | None) -> bool:
    if instance_path is None:
        return False
    return Path(instance_path).suffix.lower() == ".vrp"


def _perturb_solution(
    solution: CvrpSolution,
    instance: CvrpInstance,
    *,
    rng: random.Random,
    strength: int,
) -> CvrpSolution | None:
    routes = [list(route) for route in solution.routes]
    for _ in range(max(1, strength)):
        candidates = [
            index for index, route in enumerate(routes)
            if len(route) >= 2
        ]
        if not candidates:
            return None
        route_index = rng.choice(candidates)
        route = routes[route_index]
        left = rng.randrange(len(route))
        right = rng.randrange(len(route))
        if left == right:
            continue
        route[left], route[right] = route[right], route[left]
    candidate = CvrpSolution(routes=tuple(tuple(route) for route in routes if route))
    if all(instance.route_load(route) <= instance.capacity for route in candidate.routes):
        return candidate
    return None


def _record_main_search_component_attempts(
    audit: dict[str, Any],
    component: str,
    attempts: int,
) -> None:
    component_attempts = audit.setdefault("main_search_component_attempts", {})
    component_attempts[component] = (
        _as_nonnegative_int(component_attempts.get(component)) + attempts
    )
    if component == "route_pair_swap":
        audit["route_pair_attempts"] = _as_nonnegative_int(
            audit.get("route_pair_attempts")
        ) + attempts
    if component == "bounded_destroy_repair":
        audit["destroy_repair_attempts"] = _as_nonnegative_int(
            audit.get("destroy_repair_attempts")
        ) + attempts
        audit["repair_budget_used"] = _as_nonnegative_int(
            audit.get("repair_budget_used")
        ) + attempts


def _record_main_search_component_attempted(
    audit: dict[str, Any],
    component: str,
) -> None:
    attempted = audit.setdefault("main_search_attempted_components", [])
    if not isinstance(attempted, list):
        attempted = []
        audit["main_search_attempted_components"] = attempted
    if component not in attempted:
        attempted.append(component)
    _refresh_main_search_component_coverage_status(audit)


def _refresh_main_search_component_coverage_status(
    audit: dict[str, Any],
    selected_components: list[str] | None = None,
) -> None:
    selected = (
        list(selected_components)
        if selected_components is not None
        else list(audit.get("main_search_selected_components") or [])
    )
    attempted = list(audit.get("main_search_attempted_components") or [])
    required = sorted(_MAIN_SEARCH_DEEP_ATTRIBUTION_COMPONENTS)
    selected_deep = [
        component
        for component in selected
        if component in _MAIN_SEARCH_DEEP_ATTRIBUTION_COMPONENTS
    ]
    attempted_deep = [
        component
        for component in attempted
        if component in _MAIN_SEARCH_DEEP_ATTRIBUTION_COMPONENTS
    ]
    missing = [
        component
        for component in required
        if component not in set(selected_deep)
    ]
    unattempted = [
        component
        for component in selected_deep
        if component not in set(attempted_deep)
    ]
    active = bool(audit.get("main_search_strategy_active"))
    if not active:
        status = "inactive"
    elif not selected_deep:
        status = "no_problem_components_selected"
    elif unattempted:
        status = "selected_not_attempted"
    elif missing:
        status = "partial_problem_components_attempted"
    else:
        status = "problem_components_attempted"
    audit["main_search_deep_components_selected"] = selected_deep
    audit["main_search_component_coverage_status"] = {
        "status": status,
        "required_deep_components": required,
        "selected_deep_components": selected_deep,
        "missing_deep_components": missing,
        "attempted_deep_components": attempted_deep,
        "unattempted_deep_components": unattempted,
    }


def _record_main_search_component_accepted(
    audit: dict[str, Any],
    component: str,
) -> None:
    component_accepted = audit.setdefault("main_search_component_accepted", {})
    component_accepted[component] = (
        _as_nonnegative_int(component_accepted.get(component)) + 1
    )
    accepted = audit.setdefault("main_search_accepted_components", [])
    if not isinstance(accepted, list):
        accepted = []
        audit["main_search_accepted_components"] = accepted
    if component not in accepted:
        accepted.append(component)


def _record_main_search_component_accepted_delta(
    audit: dict[str, Any],
    component: str,
    delta: float,
) -> None:
    delta_sum = audit.setdefault("main_search_component_accepted_delta_sum", {})
    delta_sum[component] = round(float(delta_sum.get(component, 0.0) or 0.0) + delta, 6)
    best_delta = audit.setdefault("main_search_component_accepted_best_delta", {})
    best_delta[component] = max(
        float(best_delta.get(component, 0.0) or 0.0),
        round(float(delta), 6),
    )
    positive_counts = audit.setdefault(
        "main_search_component_accepted_positive_counts",
        {},
    )
    if delta > _OBJECTIVE_TOLERANCE:
        positive_counts[component] = (
            _as_nonnegative_int(positive_counts.get(component)) + 1
        )


def _record_main_search_component_phase_improvement(
    audit: dict[str, Any],
    component: str,
    delta: float,
) -> None:
    delta_sum = audit.setdefault("main_search_component_phase_delta_sum", {})
    delta_sum[component] = round(
        float(delta_sum.get(component, 0.0) or 0.0) + delta,
        6,
    )
    best_delta = audit.setdefault("main_search_component_phase_best_delta", {})
    best_delta[component] = max(
        float(best_delta.get(component, 0.0) or 0.0),
        round(float(delta), 6),
    )
    counts = audit.setdefault(
        "main_search_component_phase_improvement_counts",
        {},
    )
    if delta > _OBJECTIVE_TOLERANCE:
        counts[component] = _as_nonnegative_int(counts.get(component)) + 1


def _record_main_search_component_recovery(
    audit: dict[str, Any],
    component: str,
    delta: float,
) -> None:
    delta_sum = audit.setdefault("main_search_component_recovery_delta_sum", {})
    delta_sum[component] = round(
        float(delta_sum.get(component, 0.0) or 0.0) + delta,
        6,
    )
    best_delta = audit.setdefault("main_search_component_recovery_best_delta", {})
    best_delta[component] = max(
        float(best_delta.get(component, 0.0) or 0.0),
        round(float(delta), 6),
    )
    counts = audit.setdefault("main_search_component_recovery_counts", {})
    if delta > _OBJECTIVE_TOLERANCE:
        counts[component] = _as_nonnegative_int(counts.get(component)) + 1


def _main_search_objective_trace(
    *,
    initial_objective: Mapping[str, int | float],
    best_objective: Mapping[str, int | float],
    returned_objective: Mapping[str, int | float],
    phase_delta: float,
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    accepted = audit.get("main_search_component_accepted")
    if not isinstance(accepted, Mapping):
        accepted = {}
    accepted_delta_sum = audit.get("main_search_component_accepted_delta_sum")
    if not isinstance(accepted_delta_sum, Mapping):
        accepted_delta_sum = {}
    phase_delta_sum = audit.get("main_search_component_phase_delta_sum")
    if not isinstance(phase_delta_sum, Mapping):
        phase_delta_sum = {}
    phase_counts = audit.get("main_search_component_phase_improvement_counts")
    if not isinstance(phase_counts, Mapping):
        phase_counts = {}
    recovery_delta_sum = audit.get("main_search_component_recovery_delta_sum")
    if not isinstance(recovery_delta_sum, Mapping):
        recovery_delta_sum = {}
    recovery_counts = audit.get("main_search_component_recovery_counts")
    if not isinstance(recovery_counts, Mapping):
        recovery_counts = {}
    accepted_but_zero_phase_delta = {
        str(component): _as_nonnegative_int(count)
        for component, count in accepted.items()
        if _as_nonnegative_int(count) > 0
        and _as_nonnegative_int(phase_counts.get(component)) <= 0
    }
    return {
        "status": "returned_best",
        "initial_objective": _objective_audit_payload(initial_objective),
        "best_objective": _objective_audit_payload(best_objective),
        "returned_objective": _objective_audit_payload(returned_objective),
        "phase_delta": round(float(phase_delta), 6),
        "accepted_delta_sum_by_component": {
            str(component): round(float(value or 0.0), 6)
            for component, value in accepted_delta_sum.items()
        },
        "phase_delta_sum_by_component": {
            str(component): round(float(value or 0.0), 6)
            for component, value in phase_delta_sum.items()
        },
        "recovery_delta_sum_by_component": {
            str(component): round(float(value or 0.0), 6)
            for component, value in recovery_delta_sum.items()
        },
        "accepted_count_by_component": {
            str(component): _as_nonnegative_int(count)
            for component, count in accepted.items()
        },
        "phase_improvement_count_by_component": {
            str(component): _as_nonnegative_int(count)
            for component, count in phase_counts.items()
        },
        "recovery_count_by_component": {
            str(component): _as_nonnegative_int(count)
            for component, count in recovery_counts.items()
        },
        "accepted_but_zero_phase_delta": accepted_but_zero_phase_delta,
    }


def _objective_audit_payload(
    objective: Mapping[str, int | float],
) -> dict[str, int | float]:
    return {
        str(key): round(float(value), 6)
        for key, value in objective.items()
        if isinstance(value, (int, float))
    }


def _record_main_search_component_skip(
    audit: dict[str, Any],
    component: str,
    reason: str,
) -> None:
    normalized_reason = reason.strip() if reason else "skipped"
    skipped = audit.setdefault("main_search_skipped_components", [])
    if not isinstance(skipped, list):
        skipped = []
        audit["main_search_skipped_components"] = skipped
    if component not in skipped:
        skipped.append(component)
    all_reasons = audit.setdefault("main_search_component_skip_reasons", {})
    component_reasons = all_reasons.setdefault(component, {})
    if not isinstance(component_reasons, dict):
        component_reasons = {}
        all_reasons[component] = component_reasons
    component_reasons[normalized_reason] = (
        _as_nonnegative_int(component_reasons.get(normalized_reason)) + 1
    )
    if component == "route_pair_swap":
        route_pair_reasons = audit.setdefault("route_pair_skip_reasons", {})
        if route_pair_reasons == {"none": 0}:
            route_pair_reasons = {}
            audit["route_pair_skip_reasons"] = route_pair_reasons
        route_pair_reasons[normalized_reason] = (
            _as_nonnegative_int(route_pair_reasons.get(normalized_reason)) + 1
        )
    if component == "bounded_destroy_repair":
        destroy_repair_reasons = audit.setdefault("destroy_repair_skip_reasons", {})
        if destroy_repair_reasons == {"none": 0}:
            destroy_repair_reasons = {}
            audit["destroy_repair_skip_reasons"] = destroy_repair_reasons
        destroy_repair_reasons[normalized_reason] = (
            _as_nonnegative_int(destroy_repair_reasons.get(normalized_reason)) + 1
        )


def _main_search_skip_reason(
    telemetry: Mapping[str, Any],
    attempts: int,
) -> str:
    reason = telemetry.get("skip_reason") if isinstance(telemetry, Mapping) else None
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    if attempts <= 0:
        return "no_candidates"
    return "no_improving_candidate"


def _record_main_search_component_candidate_delta(
    audit: dict[str, Any],
    component: str,
    delta: float,
) -> None:
    best_delta = audit.setdefault("main_search_component_best_delta", {})
    current_best = float(best_delta.get(component, 0.0) or 0.0)
    if delta > current_best:
        best_delta[component] = float(delta)
    improvement_counts = audit.setdefault(
        "main_search_component_improvement_counts",
        {},
    )
    if delta > _OBJECTIVE_TOLERANCE:
        improvement_counts[component] = (
            _as_nonnegative_int(improvement_counts.get(component)) + 1
        )


def _record_main_search_component_repair_counts(
    audit: dict[str, Any],
    component: str,
    telemetry: Mapping[str, Any],
) -> None:
    removed = _as_nonnegative_int(telemetry.get("removed_count"))
    reinserted = _as_nonnegative_int(telemetry.get("reinserted_count"))
    fallback = _as_nonnegative_int(telemetry.get("repair_fallback_count"))
    if removed:
        removed_counts = audit.setdefault("main_search_component_removed_counts", {})
        removed_counts[component] = (
            _as_nonnegative_int(removed_counts.get(component)) + removed
        )
    if reinserted:
        reinserted_counts = audit.setdefault(
            "main_search_component_reinserted_counts",
            {},
        )
        reinserted_counts[component] = (
            _as_nonnegative_int(reinserted_counts.get(component)) + reinserted
        )
    if fallback:
        fallback_counts = audit.setdefault(
            "main_search_component_repair_fallback_counts",
            {},
        )
        fallback_counts[component] = (
            _as_nonnegative_int(fallback_counts.get(component)) + fallback
        )
    if component == "bounded_destroy_repair":
        audit["removed_customers"] = _as_nonnegative_int(
            audit.get("removed_customers")
        ) + removed
        audit["reinserted_customers"] = _as_nonnegative_int(
            audit.get("reinserted_customers")
        ) + reinserted
        audit["repair_fallback_counts"] = _as_nonnegative_int(
            audit.get("repair_fallback_counts")
        ) + fallback
        subset_count = _as_nonnegative_int(telemetry.get("destroy_subset_count"))
        audit["destroy_subset_count"] = _as_nonnegative_int(
            audit.get("destroy_subset_count")
        ) + subset_count
    if component == "route_pair_swap":
        audit["route_pair_candidates_generated"] = _as_nonnegative_int(
            audit.get("route_pair_candidates_generated")
        ) + _as_nonnegative_int(telemetry.get("route_pair_candidates_generated"))
        audit["route_pair_candidates_pruned"] = _as_nonnegative_int(
            audit.get("route_pair_candidates_pruned")
        ) + _as_nonnegative_int(telemetry.get("route_pair_candidates_pruned"))
    if component == "route_pool_recombination":
        audit["main_search_route_pool_source_solutions"] = _as_nonnegative_int(
            audit.get("main_search_route_pool_source_solutions")
        ) + _as_nonnegative_int(telemetry.get("route_pool_source_solutions"))
        audit["main_search_route_pool_sample_count"] = _as_nonnegative_int(
            audit.get("main_search_route_pool_sample_count")
        ) + _as_nonnegative_int(telemetry.get("route_pool_sample_count"))
        audit["main_search_route_pool_size"] = _as_nonnegative_int(
            audit.get("main_search_route_pool_size")
        ) + _as_nonnegative_int(telemetry.get("route_pool_size"))
        audit["main_search_route_pool_branch_calls"] = _as_nonnegative_int(
            audit.get("main_search_route_pool_branch_calls")
        ) + _as_nonnegative_int(telemetry.get("route_pool_branch_calls"))
        audit["main_search_route_pool_recombined_routes"] = _as_nonnegative_int(
            audit.get("main_search_route_pool_recombined_routes")
        ) + _as_nonnegative_int(telemetry.get("route_pool_recombined_routes"))


def _record_main_search_component_runtime(
    audit: dict[str, Any],
    component: str,
    start_ns: int,
) -> None:
    elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
    runtime = audit.setdefault("main_search_component_runtime_ms", {})
    runtime[component] = _as_nonnegative_int(runtime.get(component)) + int(
        elapsed_ms
    )
    if component == "route_pair_swap":
        audit["route_pair_runtime_ms"] = _as_nonnegative_int(
            audit.get("route_pair_runtime_ms")
        ) + elapsed_ms
    if component == "bounded_destroy_repair":
        audit["destroy_repair_runtime_ms"] = _as_nonnegative_int(
            audit.get("destroy_repair_runtime_ms")
        ) + elapsed_ms


def _append_main_search_phase(audit: dict[str, Any], phase: str) -> None:
    phases = audit.setdefault("main_search_phases", [])
    if not isinstance(phases, list):
        phases = []
        audit["main_search_phases"] = phases
    if phases == ["inactive"] or phases == ["plan_invalid"]:
        phases.clear()
    if phase not in phases:
        phases.append(phase)


def _set_main_search_phase_runtime(
    audit: dict[str, Any],
    phase: str,
    start_ns: int,
) -> None:
    runtime = audit.setdefault("main_search_phase_runtime_ms", {})
    runtime[phase] = _as_nonnegative_int(runtime.get(phase)) + int(
        (time.monotonic_ns() - start_ns) / 1_000_000
    )


def _record_algorithm_component_runtime(
    audit: dict[str, Any],
    component: str,
    start_ns: int,
) -> None:
    runtime = audit.setdefault("algorithm_component_runtime_ms", {})
    runtime[component] = _as_nonnegative_int(runtime.get(component)) + int(
        (time.monotonic_ns() - start_ns) / 1_000_000
    )


def _append_algorithm_phase(audit: dict[str, Any], phase: str) -> None:
    phases = audit.setdefault("algorithm_phases_executed", [])
    if not isinstance(phases, list):
        phases = []
        audit["algorithm_phases_executed"] = phases
    if phases == ["inactive"] or phases == ["plan_invalid"]:
        phases.clear()
    if phase not in phases:
        phases.append(phase)


def _set_algorithm_phase_runtime(
    audit: dict[str, Any],
    phase: str,
    start_ns: int,
) -> None:
    runtime = audit.setdefault("algorithm_phase_runtime_ms", {})
    runtime[phase] = _as_nonnegative_int(runtime.get(phase)) + int(
        (time.monotonic_ns() - start_ns) / 1_000_000
    )


def _objective_distance_delta(
    before: Mapping[str, int | float],
    after: Mapping[str, int | float],
) -> float:
    if float(after.get("fleet_violation", 0)) != float(before.get("fleet_violation", 0)):
        return float(before.get("fleet_violation", 0)) - float(
            after.get("fleet_violation", 0)
        )
    return float(before.get("total_distance", 0.0)) - float(
        after.get("total_distance", 0.0)
    )


def _record_mechanism_event(
    audit: dict[str, Any],
    *,
    event_key: str,
    policy_path: str,
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault(event_key, [])
    if len(events) >= 10:
        return
    events.append({"policy": policy_path, "status": status, "detail": detail})


def _mechanism_bool(
    value: Any,
    *,
    default: bool,
    field_name: str,
    error_key: str,
    event_recorder: Any,
    audit: dict[str, Any],
) -> bool:
    if isinstance(value, bool):
        return value
    audit[error_key] += 1
    event_recorder(audit, "error", f"{field_name} returned non-bool value {value!r}")
    return default


def _mechanism_int(
    value: Any,
    *,
    minimum: int,
    maximum: int,
    default: int,
    field_name: str,
    error_key: str,
    event_recorder: Any,
    audit: dict[str, Any],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        audit[error_key] += 1
        event_recorder(audit, "error", f"{field_name} returned non-integer value {value!r}")
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit[error_key] += 1
        event_recorder(
            audit,
            "error",
            f"{field_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _mechanism_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    default: float,
    field_name: str,
    error_key: str,
    event_recorder: Any,
    audit: dict[str, Any],
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit[error_key] += 1
        event_recorder(audit, "error", f"{field_name} returned non-numeric value {value!r}")
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit[error_key] += 1
        event_recorder(audit, "error", f"{field_name} returned non-finite value {value!r}")
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit[error_key] += 1
        event_recorder(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _mechanism_choice(
    value: Any,
    *,
    allowed: frozenset[str],
    default: str,
    field_name: str,
    error_key: str,
    event_recorder: Any,
    audit: dict[str, Any],
) -> str:
    text = str(value).strip() if value is not None else ""
    if text in allowed:
        return text
    audit[error_key] += 1
    event_recorder(audit, "error", f"{field_name} contains unknown value {text!r}")
    return default


def _mechanism_string_sequence(
    value: Any,
    *,
    allowed: frozenset[str],
    default: list[str],
    field_name: str,
    error_key: str,
    event_recorder: Any,
    audit: dict[str, Any],
) -> list[str]:
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        audit[error_key] += 1
        event_recorder(audit, "error", f"{field_name} returned non-sequence value {value!r}")
        return list(default)
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if text not in allowed:
            audit[error_key] += 1
            event_recorder(audit, "error", f"{field_name} contains unknown value {text!r}")
            continue
        if text not in seen:
            seen.add(text)
            result.append(text)
    if not result:
        audit[error_key] += 1
        event_recorder(audit, "error", f"{field_name} produced no valid values")
        return list(default)
    return result


def _mechanism_weight_mapping(
    value: Any,
    *,
    allowed: frozenset[str],
    default: dict[str, float],
    field_name: str,
    error_key: str,
    event_recorder: Any,
    audit: dict[str, Any],
) -> dict[str, float]:
    result = dict(default)
    if not isinstance(value, Mapping):
        audit[error_key] += 1
        event_recorder(audit, "error", f"{field_name} returned non-mapping value {value!r}")
        return result
    for raw_key, raw_weight in value.items():
        key = str(raw_key).strip()
        if key not in allowed:
            audit[error_key] += 1
            event_recorder(audit, "error", f"{field_name} contains unknown key {key!r}")
            continue
        result[key] = _mechanism_float(
            raw_weight,
            minimum=0.0,
            maximum=5.0,
            default=result.get(key, 1.0),
            field_name=f"{field_name}[{key}]",
            error_key=error_key,
            event_recorder=event_recorder,
            audit=audit,
        )
    return result


def _load_alns_vns_policy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _alns_vns_policy_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _ALNS_VNS_POLICY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_alns_vns_event(audit, "error", "ALNS/VNS policy path escapes workspace")
        audit["alns_vns_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit
    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["alns_vns_errors"] += 1
        _record_alns_vns_event(audit, "error", f"ALNS/VNS policy load failed: {exc}")
        return audit
    audit["alns_vns_surface_loaded"] = True
    try:
        raw_plan = _call_policy_function(module, "alns_vns_plan", instance, time_limit_sec)
    except Exception as exc:
        audit["alns_vns_errors"] += 1
        _record_alns_vns_event(audit, "error", f"alns_vns_plan failed: {exc}")
        return audit
    if not isinstance(raw_plan, Mapping):
        audit["alns_vns_errors"] += 1
        _record_alns_vns_event(
            audit,
            "error",
            f"alns_vns_plan returned non-mapping value {raw_plan!r}",
        )
        return audit
    _normalize_alns_vns_plan(dict(raw_plan), audit=audit)
    return audit


def _alns_vns_policy_defaults() -> dict[str, Any]:
    return {
        "alns_vns_policy_path": _ALNS_VNS_POLICY_RELATIVE_PATH,
        "alns_vns_surface_loaded": False,
        "alns_vns_active": False,
        "alns_vns_errors": 0,
        "alns_vns_events": [],
        "alns_vns_plan": {"enabled": False, "params": {}},
        "alns_vns_components": ["alns", "vns"],
        "alns_vns_component_weights": {"alns": 1.0, "vns": 1.0},
        "alns_vns_segment_schedule": {
            "segment_length": _DEFAULT_BASELINE_POLICY_PARAMS["segment_length"],
        },
        "alns_vns_destroy_schedule": {
            "destroy_ratio": list(_DEFAULT_BASELINE_POLICY_PARAMS["destroy_ratio"]),
        },
        "alns_vns_baseline_params": {},
        "alns_vns_attempts": 0,
        "alns_vns_accepted": 0,
        "alns_vns_initial_distance": 0.0,
        "alns_vns_returned_distance": 0.0,
        "alns_vns_objective_delta": {},
        "alns_vns_phase_delta_sum": 0.0,
        "alns_vns_runtime_ms": 0,
        "alns_vns_stop_reason": "inactive",
    }


def _normalize_alns_vns_plan(plan: dict[str, Any], *, audit: dict[str, Any]) -> None:
    enabled = _mechanism_bool(
        plan.get("enabled", False),
        default=False,
        field_name="alns_vns.enabled",
        error_key="alns_vns_errors",
        event_recorder=_record_alns_vns_event,
        audit=audit,
    )
    params = plan.get("params", {})
    if not isinstance(params, Mapping):
        audit["alns_vns_errors"] += 1
        _record_alns_vns_event(audit, "error", f"params returned non-mapping value {params!r}")
        params = {}
    baseline_audit = _baseline_policy_defaults()
    _normalize_baseline_policy_params(dict(params), audit=baseline_audit)
    for event in baseline_audit.get("baseline_policy_events", []):
        if isinstance(event, Mapping) and event.get("detail"):
            _record_alns_vns_event(audit, "error", f"params invalid: {event['detail']}")
    audit["alns_vns_errors"] += _as_nonnegative_int(
        baseline_audit.get("baseline_policy_errors")
    )
    normalized_params = dict(baseline_audit.get("baseline_policy_params") or {})
    components = _mechanism_string_sequence(
        plan.get("components", ["alns", "vns"]),
        allowed=_ALNS_VNS_ALLOWED_COMPONENTS,
        default=["alns", "vns"],
        field_name="alns_vns.components",
        error_key="alns_vns_errors",
        event_recorder=_record_alns_vns_event,
        audit=audit,
    )
    weights = _mechanism_weight_mapping(
        plan.get("component_weights", {"alns": 1.0, "vns": 1.0}),
        allowed=_ALNS_VNS_ALLOWED_COMPONENTS,
        default={"alns": 1.0, "vns": 1.0},
        field_name="alns_vns.component_weights",
        error_key="alns_vns_errors",
        event_recorder=_record_alns_vns_event,
        audit=audit,
    )
    active = enabled and _as_nonnegative_int(audit.get("alns_vns_errors")) == 0
    audit["alns_vns_active"] = active
    audit["alns_vns_plan"] = {
        "enabled": active,
        "components": components,
        "component_weights": weights,
        "params": normalized_params,
    }
    audit["alns_vns_components"] = components
    audit["alns_vns_component_weights"] = weights
    audit["alns_vns_segment_schedule"] = {
        "segment_length": int(normalized_params["segment_length"])
    }
    audit["alns_vns_destroy_schedule"] = {
        "destroy_ratio": list(normalized_params["destroy_ratio"])
    }
    audit["alns_vns_baseline_params"] = normalized_params if active else {}
    audit["alns_vns_stop_reason"] = "policy_loaded" if active else "inactive"


def _finalize_alns_vns_policy_audit(
    alns_vns_policy: Mapping[str, Any] | None,
    baseline_audit: Mapping[str, Any],
    *,
    construction_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    audit = dict(alns_vns_policy or _alns_vns_policy_defaults())
    if not bool(audit.get("alns_vns_active")):
        return audit
    mode = str(baseline_audit.get("baseline_mode") or "")
    elapsed = baseline_audit.get("baseline_elapsed_s")
    if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool):
        audit["alns_vns_runtime_ms"] = int(max(0.0, float(elapsed)) * 1000)
    audit["alns_vns_attempts"] = _as_nonnegative_int(
        baseline_audit.get("baseline_iterations")
    )
    audit["alns_vns_accepted"] = 1 if mode == "vrp_alns_vns" else 0
    start_distance = _coerce_optional_float(
        (construction_audit or {}).get("construction_distance")
    )
    returned_distance = _coerce_optional_float(baseline_audit.get("baseline_cost"))
    if start_distance is not None:
        audit["alns_vns_initial_distance"] = round(start_distance, 6)
    if returned_distance is not None:
        audit["alns_vns_returned_distance"] = round(returned_distance, 6)
    phase_delta = 0.0
    if mode == "vrp_alns_vns" and start_distance is not None and returned_distance is not None:
        phase_delta = max(0.0, start_distance - returned_distance)
    audit["alns_vns_phase_delta_sum"] = round(phase_delta, 6)
    audit["alns_vns_objective_delta"] = {
        "baseline_phase": round(phase_delta, 6),
        "initial_distance": (
            round(start_distance, 6) if start_distance is not None else None
        ),
        "returned_distance": (
            round(returned_distance, 6) if returned_distance is not None else None
        ),
    }
    audit["alns_vns_stop_reason"] = mode or "baseline_not_run"
    return audit


def _coerce_optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _record_alns_vns_event(audit: dict[str, Any], status: str, detail: str) -> None:
    _record_mechanism_event(
        audit,
        event_key="alns_vns_events",
        policy_path=_ALNS_VNS_POLICY_RELATIVE_PATH,
        status=status,
        detail=detail,
    )


def _load_destroy_repair_policy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _destroy_repair_policy_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _DESTROY_REPAIR_POLICY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_destroy_repair_event(audit, "error", "destroy/repair policy path escapes workspace")
        audit["destroy_repair_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit
    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["destroy_repair_errors"] += 1
        _record_destroy_repair_event(audit, "error", f"destroy/repair policy load failed: {exc}")
        return audit
    audit["destroy_repair_surface_loaded"] = True
    try:
        raw_plan = _call_policy_function(module, "destroy_repair_plan", instance, time_limit_sec)
    except Exception as exc:
        audit["destroy_repair_errors"] += 1
        _record_destroy_repair_event(audit, "error", f"destroy_repair_plan failed: {exc}")
        return audit
    if not isinstance(raw_plan, Mapping):
        audit["destroy_repair_errors"] += 1
        _record_destroy_repair_event(
            audit,
            "error",
            f"destroy_repair_plan returned non-mapping value {raw_plan!r}",
        )
        return audit
    _normalize_destroy_repair_plan(dict(raw_plan), audit=audit)
    return audit


def _destroy_repair_policy_defaults() -> dict[str, Any]:
    return {
        "destroy_repair_policy_path": _DESTROY_REPAIR_POLICY_RELATIVE_PATH,
        "destroy_repair_surface_loaded": False,
        "destroy_repair_active": False,
        "destroy_repair_errors": 0,
        "destroy_repair_events": [],
        "destroy_repair_plan": {"enabled": False},
        "destroy_selectors": ["worst_removal"],
        "repair_selectors": ["regret_2"],
        "destroy_subset_strategy": "prefix_shifted_route_diverse",
        "destroy_max_customers": 6,
        "repair_budget_per_customer": 4,
        "repair_fallback_enabled": True,
        "destroy_repair_phase_best_preference": True,
        "destroy_subset_count": 0,
        "removed_customers": 0,
        "reinserted_customers": 0,
        "repair_budget_used": 0,
        "repair_fallback_counts": 0,
        "destroy_repair_attempts": 0,
        "destroy_repair_accepted_current": 0,
        "destroy_repair_accepted_recovery_only": 0,
        "destroy_repair_accepted_phase_best": 0,
        "destroy_repair_phase_delta_sum": 0.0,
        "destroy_repair_skip_reasons": {"none": 0},
        "destroy_repair_runtime_ms": 0,
    }


def _normalize_destroy_repair_plan(plan: dict[str, Any], *, audit: dict[str, Any]) -> None:
    enabled = _mechanism_bool(
        plan.get("enabled", False),
        default=False,
        field_name="destroy_repair.enabled",
        error_key="destroy_repair_errors",
        event_recorder=_record_destroy_repair_event,
        audit=audit,
    )
    destroy_selectors = _mechanism_string_sequence(
        plan.get("destroy_selectors", ["worst_removal"]),
        allowed=_DESTROY_REPAIR_ALLOWED_DESTROY_SELECTORS,
        default=["worst_removal"],
        field_name="destroy_selectors",
        error_key="destroy_repair_errors",
        event_recorder=_record_destroy_repair_event,
        audit=audit,
    )
    repair_selectors = _mechanism_string_sequence(
        plan.get("repair_selectors", ["regret_2"]),
        allowed=_DESTROY_REPAIR_ALLOWED_REPAIR_SELECTORS,
        default=["regret_2"],
        field_name="repair_selectors",
        error_key="destroy_repair_errors",
        event_recorder=_record_destroy_repair_event,
        audit=audit,
    )
    subset_strategy = _mechanism_choice(
        plan.get("subset_strategy", "prefix_shifted_route_diverse"),
        allowed=_DESTROY_REPAIR_SUBSET_STRATEGIES,
        default="prefix_shifted_route_diverse",
        field_name="subset_strategy",
        error_key="destroy_repair_errors",
        event_recorder=_record_destroy_repair_event,
        audit=audit,
    )
    max_customers = _mechanism_int(
        plan.get("max_destroy_customers", 6),
        minimum=1,
        maximum=12,
        default=6,
        field_name="max_destroy_customers",
        error_key="destroy_repair_errors",
        event_recorder=_record_destroy_repair_event,
        audit=audit,
    )
    repair_budget = _mechanism_int(
        plan.get("repair_budget_per_customer", 4),
        minimum=1,
        maximum=16,
        default=4,
        field_name="repair_budget_per_customer",
        error_key="destroy_repair_errors",
        event_recorder=_record_destroy_repair_event,
        audit=audit,
    )
    fallback_enabled = _mechanism_bool(
        plan.get("fallback_to_smaller_subsets", True),
        default=True,
        field_name="fallback_to_smaller_subsets",
        error_key="destroy_repair_errors",
        event_recorder=_record_destroy_repair_event,
        audit=audit,
    )
    phase_best_preference = _mechanism_bool(
        plan.get("phase_best_preference", True),
        default=True,
        field_name="phase_best_preference",
        error_key="destroy_repair_errors",
        event_recorder=_record_destroy_repair_event,
        audit=audit,
    )
    active = enabled and _as_nonnegative_int(audit.get("destroy_repair_errors")) == 0
    audit["destroy_repair_active"] = active
    audit["destroy_repair_plan"] = {
        "enabled": active,
        "destroy_selectors": destroy_selectors,
        "repair_selectors": repair_selectors,
        "subset_strategy": subset_strategy,
        "max_destroy_customers": max_customers,
        "repair_budget_per_customer": repair_budget,
        "fallback_to_smaller_subsets": fallback_enabled,
        "phase_best_preference": phase_best_preference,
    }
    audit["destroy_selectors"] = destroy_selectors
    audit["repair_selectors"] = repair_selectors
    audit["destroy_subset_strategy"] = subset_strategy
    audit["destroy_max_customers"] = max_customers
    audit["repair_budget_per_customer"] = repair_budget
    audit["repair_fallback_enabled"] = fallback_enabled
    audit["destroy_repair_phase_best_preference"] = phase_best_preference


def _record_destroy_repair_event(audit: dict[str, Any], status: str, detail: str) -> None:
    _record_mechanism_event(
        audit,
        event_key="destroy_repair_events",
        policy_path=_DESTROY_REPAIR_POLICY_RELATIVE_PATH,
        status=status,
        detail=detail,
    )


def _load_route_pair_candidate_policy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _route_pair_policy_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _ROUTE_PAIR_CANDIDATE_POLICY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_route_pair_event(audit, "error", "route-pair policy path escapes workspace")
        audit["route_pair_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit
    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["route_pair_errors"] += 1
        _record_route_pair_event(audit, "error", f"route-pair policy load failed: {exc}")
        return audit
    audit["route_pair_surface_loaded"] = True
    try:
        raw_plan = _call_policy_function(module, "route_pair_plan", instance, time_limit_sec)
    except Exception as exc:
        audit["route_pair_errors"] += 1
        _record_route_pair_event(audit, "error", f"route_pair_plan failed: {exc}")
        return audit
    if not isinstance(raw_plan, Mapping):
        audit["route_pair_errors"] += 1
        _record_route_pair_event(
            audit,
            "error",
            f"route_pair_plan returned non-mapping value {raw_plan!r}",
        )
        return audit
    _normalize_route_pair_plan(dict(raw_plan), audit=audit)
    return audit


def _route_pair_policy_defaults() -> dict[str, Any]:
    return {
        "route_pair_policy_path": _ROUTE_PAIR_CANDIDATE_POLICY_RELATIVE_PATH,
        "route_pair_surface_loaded": False,
        "route_pair_active": False,
        "route_pair_errors": 0,
        "route_pair_events": [],
        "route_pair_plan": {"enabled": False},
        "route_pair_scoring_terms": ["route_distance", "removal_saving", "distance_saving"],
        "route_pair_move_families": ["customer_swap"],
        "route_pair_candidate_limits": {"pair_cap": 0, "position_cap": 0},
        "route_pair_candidates_generated": 0,
        "route_pair_candidates_pruned": 0,
        "route_pair_attempts": 0,
        "route_pair_accepted_current": 0,
        "route_pair_accepted_recovery_only": 0,
        "route_pair_accepted_phase_best": 0,
        "route_pair_phase_delta_sum": 0.0,
        "route_pair_skip_reasons": {"none": 0},
        "route_pair_runtime_ms": 0,
    }


def _normalize_route_pair_plan(plan: dict[str, Any], *, audit: dict[str, Any]) -> None:
    enabled = _mechanism_bool(
        plan.get("enabled", False),
        default=False,
        field_name="route_pair.enabled",
        error_key="route_pair_errors",
        event_recorder=_record_route_pair_event,
        audit=audit,
    )
    scoring_terms = _mechanism_string_sequence(
        plan.get("scoring_terms", ["route_distance", "removal_saving", "distance_saving"]),
        allowed=_ROUTE_PAIR_ALLOWED_SCORING_TERMS,
        default=["route_distance", "removal_saving", "distance_saving"],
        field_name="scoring_terms",
        error_key="route_pair_errors",
        event_recorder=_record_route_pair_event,
        audit=audit,
    )
    move_families = _mechanism_string_sequence(
        plan.get("move_families", ["customer_swap"]),
        allowed=_ROUTE_PAIR_ALLOWED_MOVE_FAMILIES,
        default=["customer_swap"],
        field_name="move_families",
        error_key="route_pair_errors",
        event_recorder=_record_route_pair_event,
        audit=audit,
    )
    limits = plan.get("candidate_limits", {})
    if not isinstance(limits, Mapping):
        audit["route_pair_errors"] += 1
        _record_route_pair_event(audit, "error", f"candidate_limits returned non-mapping value {limits!r}")
        limits = {}
    candidate_limits = {
        "pair_cap": _mechanism_int(
            limits.get("pair_cap", 0),
            minimum=0,
            maximum=500,
            default=0,
            field_name="candidate_limits.pair_cap",
            error_key="route_pair_errors",
            event_recorder=_record_route_pair_event,
            audit=audit,
        ),
        "position_cap": _mechanism_int(
            limits.get("position_cap", 0),
            minimum=0,
            maximum=32,
            default=0,
            field_name="candidate_limits.position_cap",
            error_key="route_pair_errors",
            event_recorder=_record_route_pair_event,
            audit=audit,
        ),
    }
    active = enabled and _as_nonnegative_int(audit.get("route_pair_errors")) == 0
    audit["route_pair_active"] = active
    audit["route_pair_plan"] = {
        "enabled": active,
        "scoring_terms": scoring_terms,
        "move_families": move_families,
        "candidate_limits": candidate_limits,
    }
    audit["route_pair_scoring_terms"] = scoring_terms
    audit["route_pair_move_families"] = move_families
    audit["route_pair_candidate_limits"] = candidate_limits


def _record_route_pair_event(audit: dict[str, Any], status: str, detail: str) -> None:
    _record_mechanism_event(
        audit,
        event_key="route_pair_events",
        policy_path=_ROUTE_PAIR_CANDIDATE_POLICY_RELATIVE_PATH,
        status=status,
        detail=detail,
    )


def _load_acceptance_restart_policy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _acceptance_restart_policy_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _ACCEPTANCE_RESTART_POLICY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_acceptance_restart_event(audit, "error", "acceptance/restart policy path escapes workspace")
        audit["acceptance_restart_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit
    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["acceptance_restart_errors"] += 1
        _record_acceptance_restart_event(audit, "error", f"acceptance/restart policy load failed: {exc}")
        return audit
    audit["acceptance_restart_surface_loaded"] = True
    try:
        raw_plan = _call_policy_function(module, "acceptance_restart_plan", instance, time_limit_sec)
    except Exception as exc:
        audit["acceptance_restart_errors"] += 1
        _record_acceptance_restart_event(audit, "error", f"acceptance_restart_plan failed: {exc}")
        return audit
    if not isinstance(raw_plan, Mapping):
        audit["acceptance_restart_errors"] += 1
        _record_acceptance_restart_event(
            audit,
            "error",
            f"acceptance_restart_plan returned non-mapping value {raw_plan!r}",
        )
        return audit
    _normalize_acceptance_restart_plan(dict(raw_plan), audit=audit)
    return audit


def _acceptance_restart_policy_defaults() -> dict[str, Any]:
    return {
        "acceptance_restart_policy_path": _ACCEPTANCE_RESTART_POLICY_RELATIVE_PATH,
        "acceptance_restart_surface_loaded": False,
        "acceptance_restart_active": False,
        "acceptance_restart_errors": 0,
        "acceptance_restart_events": [],
        "acceptance_restart_plan": {"enabled": False},
        "acceptance_threshold_schedule": {"min_distance_improvement": 0.0},
        "recovery_only_policy": "allow",
        "restart_triggers": {"enabled": False, "stagnation_rounds": 0, "max_restarts": 0},
        "restart_count": 0,
        "perturbation_schedule": {
            "enabled": False,
            "schedule": _DEFAULT_MAIN_SEARCH_PERTURBATION_SCHEDULE,
        },
        "perturbation_count": 0,
        "accepted_current_count": 0,
        "accepted_recovery_only_count": 0,
        "accepted_phase_best_count": 0,
        "phase_best_refresh_count": 0,
        "acceptance_restart_phase_delta_sum": 0.0,
        "acceptance_restart_runtime_ms": 0,
    }


def _normalize_acceptance_restart_plan(plan: dict[str, Any], *, audit: dict[str, Any]) -> None:
    enabled = _mechanism_bool(
        plan.get("enabled", False),
        default=False,
        field_name="acceptance_restart.enabled",
        error_key="acceptance_restart_errors",
        event_recorder=_record_acceptance_restart_event,
        audit=audit,
    )
    min_improvement = _mechanism_float(
        plan.get("min_distance_improvement", 0.0),
        minimum=0.0,
        maximum=_MAX_MAIN_SEARCH_MIN_DISTANCE_IMPROVEMENT,
        default=0.0,
        field_name="min_distance_improvement",
        error_key="acceptance_restart_errors",
        event_recorder=_record_acceptance_restart_event,
        audit=audit,
    )
    recovery_policy = _mechanism_choice(
        plan.get("recovery_only_policy", "allow"),
        allowed=_ACCEPTANCE_RECOVERY_POLICIES,
        default="allow",
        field_name="recovery_only_policy",
        error_key="acceptance_restart_errors",
        event_recorder=_record_acceptance_restart_event,
        audit=audit,
    )
    restart = plan.get("restart", {})
    if not isinstance(restart, Mapping):
        audit["acceptance_restart_errors"] += 1
        _record_acceptance_restart_event(audit, "error", f"restart returned non-mapping value {restart!r}")
        restart = {}
    restart_enabled = _mechanism_bool(
        restart.get("enabled", False),
        default=False,
        field_name="restart.enabled",
        error_key="acceptance_restart_errors",
        event_recorder=_record_acceptance_restart_event,
        audit=audit,
    )
    restart_stagnation = _mechanism_int(
        restart.get("stagnation_rounds", 0),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_RESTART_STAGNATION_ROUNDS,
        default=0,
        field_name="restart.stagnation_rounds",
        error_key="acceptance_restart_errors",
        event_recorder=_record_acceptance_restart_event,
        audit=audit,
    )
    restart_limit = _mechanism_int(
        restart.get("max_restarts", 0),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_RESTARTS,
        default=0,
        field_name="restart.max_restarts",
        error_key="acceptance_restart_errors",
        event_recorder=_record_acceptance_restart_event,
        audit=audit,
    )
    perturbation = plan.get("perturbation", {})
    if not isinstance(perturbation, Mapping):
        audit["acceptance_restart_errors"] += 1
        _record_acceptance_restart_event(audit, "error", f"perturbation returned non-mapping value {perturbation!r}")
        perturbation = {}
    perturbation_enabled = _mechanism_bool(
        perturbation.get("enabled", False),
        default=False,
        field_name="perturbation.enabled",
        error_key="acceptance_restart_errors",
        event_recorder=_record_acceptance_restart_event,
        audit=audit,
    )
    perturbation_schedule = _mechanism_choice(
        perturbation.get("schedule", _DEFAULT_MAIN_SEARCH_PERTURBATION_SCHEDULE),
        allowed=_MAIN_SEARCH_PERTURBATION_SCHEDULES,
        default=_DEFAULT_MAIN_SEARCH_PERTURBATION_SCHEDULE,
        field_name="perturbation.schedule",
        error_key="acceptance_restart_errors",
        event_recorder=_record_acceptance_restart_event,
        audit=audit,
    )
    perturbation_strength = _mechanism_int(
        perturbation.get("strength", 1),
        minimum=1,
        maximum=_MAX_MAIN_SEARCH_PERTURBATION_STRENGTH,
        default=1,
        field_name="perturbation.strength",
        error_key="acceptance_restart_errors",
        event_recorder=_record_acceptance_restart_event,
        audit=audit,
    )
    max_perturbations = _mechanism_int(
        perturbation.get("max_perturbations", 0),
        minimum=0,
        maximum=_MAX_MAIN_SEARCH_PERTURBATIONS,
        default=0,
        field_name="perturbation.max_perturbations",
        error_key="acceptance_restart_errors",
        event_recorder=_record_acceptance_restart_event,
        audit=audit,
    )
    active = enabled and _as_nonnegative_int(audit.get("acceptance_restart_errors")) == 0
    audit["acceptance_restart_active"] = active
    audit["acceptance_restart_plan"] = {
        "enabled": active,
        "min_distance_improvement": min_improvement,
        "recovery_only_policy": recovery_policy,
        "restart": {
            "enabled": restart_enabled,
            "stagnation_rounds": restart_stagnation,
            "max_restarts": restart_limit,
        },
        "perturbation": {
            "enabled": perturbation_enabled,
            "schedule": perturbation_schedule,
            "strength": perturbation_strength,
            "max_perturbations": max_perturbations,
        },
    }
    audit["acceptance_threshold_schedule"] = {"min_distance_improvement": min_improvement}
    audit["recovery_only_policy"] = recovery_policy
    audit["restart_triggers"] = {
        "enabled": restart_enabled,
        "stagnation_rounds": restart_stagnation,
        "max_restarts": restart_limit,
    }
    audit["perturbation_schedule"] = {
        "enabled": perturbation_enabled,
        "schedule": perturbation_schedule,
        "strength": perturbation_strength,
        "max_perturbations": max_perturbations,
    }


def _record_acceptance_restart_event(audit: dict[str, Any], status: str, detail: str) -> None:
    _record_mechanism_event(
        audit,
        event_key="acceptance_restart_events",
        policy_path=_ACCEPTANCE_RESTART_POLICY_RELATIVE_PATH,
        status=status,
        detail=detail,
    )


def _load_neighborhood_portfolio(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _portfolio_audit_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_portfolio_event(audit, "error", "portfolio policy path escapes workspace")
        audit["portfolio_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"portfolio policy load failed: {exc}")
        return audit

    audit["portfolio_surface_loaded"] = True
    audit["enabled_components"] = _portfolio_enabled_components(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["component_weights"] = _portfolio_component_weights(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["candidate_limits"] = _portfolio_candidate_limits(
        module=module,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    return audit


def _portfolio_audit_defaults(
    portfolio: dict[str, Any] | None = None,
) -> dict[str, Any]:
    audit = dict(portfolio or {})
    audit.setdefault("portfolio_policy_path", _NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH)
    audit.setdefault("portfolio_surface_loaded", False)
    audit.setdefault("portfolio_errors", 0)
    audit.setdefault("portfolio_events", [])
    audit.setdefault("enabled_components", list(_DEFAULT_ENABLED_COMPONENTS))
    audit.setdefault("component_weights", dict(_DEFAULT_COMPONENT_WEIGHTS))
    audit.setdefault("candidate_limits", dict(_DEFAULT_CANDIDATE_LIMITS))
    audit.setdefault(
        "component_attempts",
        {component: 0 for component in audit["enabled_components"]},
    )
    audit.setdefault(
        "component_accepted",
        {component: 0 for component in audit["enabled_components"]},
    )
    audit.setdefault(
        "component_runtime_ms",
        {component: 0 for component in audit["enabled_components"]},
    )
    audit.setdefault("portfolio_stop_reason", "")
    audit.setdefault(
        "portfolio_effective_round_limit",
        int(audit["candidate_limits"].get("max_rounds", _MAX_OPERATOR_ROUNDS))
        if isinstance(audit.get("candidate_limits"), Mapping)
        else _MAX_OPERATOR_ROUNDS,
    )
    return audit


def _portfolio_enabled_components(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> list[str]:
    try:
        value = _call_policy_function(module, "enabled_components", instance, time_limit_sec)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"enabled_components failed: {exc}")
        return list(_DEFAULT_ENABLED_COMPONENTS)
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"enabled_components returned non-sequence value {value!r}",
        )
        return list(_DEFAULT_ENABLED_COMPONENTS)

    enabled: list[str] = []
    seen: set[str] = set()
    for item in value:
        component = str(item).strip()
        if component not in _ALLOWED_PORTFOLIO_COMPONENTS:
            audit["portfolio_errors"] += 1
            _record_portfolio_event(
                audit,
                "error",
                f"enabled_components contains unknown component {component!r}",
            )
            continue
        if component not in seen:
            seen.add(component)
            enabled.append(component)
    if not enabled:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            "enabled_components produced no valid enabled components",
        )
        return list(_DEFAULT_ENABLED_COMPONENTS)
    return enabled


def _portfolio_component_weights(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> dict[str, float]:
    weights = dict(_DEFAULT_COMPONENT_WEIGHTS)
    try:
        value = _call_policy_function(module, "component_weights", instance, time_limit_sec)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"component_weights failed: {exc}")
        return weights
    if not isinstance(value, Mapping):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"component_weights returned non-mapping value {value!r}",
        )
        return weights

    for raw_component, raw_weight in value.items():
        component = str(raw_component).strip()
        if component not in _ALLOWED_PORTFOLIO_COMPONENTS:
            audit["portfolio_errors"] += 1
            _record_portfolio_event(
                audit,
                "error",
                f"component_weights contains unknown component {component!r}",
            )
            continue
        weight = _portfolio_float(
            raw_weight,
            default=weights[component],
            minimum=0.0,
            maximum=_MAX_COMPONENT_WEIGHT,
            field_name=f"component_weights[{component}]",
            audit=audit,
        )
        weights[component] = weight
    return weights


def _portfolio_candidate_limits(
    *,
    module: Any,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> dict[str, int]:
    limits = dict(_DEFAULT_CANDIDATE_LIMITS)
    try:
        value = _call_policy_function(module, "candidate_limits", instance, time_limit_sec)
    except Exception as exc:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(audit, "error", f"candidate_limits failed: {exc}")
        return limits
    if not isinstance(value, Mapping):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"candidate_limits returned non-mapping value {value!r}",
        )
        return limits

    known_limit_keys = {
        "max_rounds",
        "top_k",
        "total_attempts",
        "per_component_attempts",
    }
    for raw_key, raw_limit in value.items():
        key = str(raw_key).strip()
        if key in _ALLOWED_PORTFOLIO_COMPONENTS:
            limits[key] = _portfolio_int(
                raw_limit,
                default=limits.get(key, limits["per_component_attempts"]),
                minimum=0,
                maximum=_MAX_PORTFOLIO_ATTEMPTS,
                field_name=f"candidate_limits[{key}]",
                audit=audit,
            )
            continue
        if key not in known_limit_keys:
            audit["portfolio_errors"] += 1
            _record_portfolio_event(
                audit,
                "error",
                f"candidate_limits contains unknown key {key!r}",
            )
            continue
        maximum = _MAX_OPERATOR_ROUNDS if key == "max_rounds" else _MAX_PORTFOLIO_ATTEMPTS
        if key == "top_k":
            maximum = _MAX_PORTFOLIO_TOP_K
        limits[key] = _portfolio_int(
            raw_limit,
            default=limits[key],
            minimum=0,
            maximum=maximum,
            field_name=f"candidate_limits[{key}]",
            audit=audit,
        )
    return limits


def _portfolio_float(
    value: Any,
    *,
    default: float,
    minimum: float,
    maximum: float,
    field_name: str,
    audit: dict[str, Any],
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name} returned non-numeric value {value!r}",
        )
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name} returned non-finite value {value!r}",
        )
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _portfolio_int(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
    field_name: str,
    audit: dict[str, Any],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name} returned non-integer value {value!r}",
        )
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit["portfolio_errors"] += 1
        _record_portfolio_event(
            audit,
            "error",
            f"{field_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _record_portfolio_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("portfolio_events", [])
    if len(events) >= 10:
        return
    events.append(
        {
            "policy": _NEIGHBORHOOD_PORTFOLIO_RELATIVE_PATH,
            "status": status,
            "detail": detail,
        }
    )


def _load_search_policy(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> dict[str, Any]:
    audit = _search_policy_defaults()
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / _SEARCH_POLICY_RELATIVE_PATH).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_policy_event(audit, "error", "policy path escapes workspace")
        audit["policy_errors"] += 1
        return audit
    if not policy_path.is_file():
        return audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["policy_errors"] += 1
        _record_policy_event(audit, "error", f"policy load failed: {exc}")
        return audit

    audit["policy_loaded"] = True
    audit["baseline_time_fraction"] = _policy_float(
        module=module,
        function_name="baseline_time_fraction",
        default=_BASELINE_TIME_FRACTION,
        minimum=_MIN_BASELINE_TIME_FRACTION,
        maximum=_MAX_BASELINE_TIME_FRACTION,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["operator_round_limit"] = _policy_int(
        module=module,
        function_name="max_operator_rounds",
        default=_MAX_OPERATOR_ROUNDS,
        minimum=0,
        maximum=_MAX_OPERATOR_ROUNDS,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    audit["post_baseline_operators_enabled"] = _policy_bool(
        module=module,
        function_name="enable_post_baseline_operators",
        default=True,
        instance=instance,
        time_limit_sec=time_limit_sec,
        audit=audit,
    )
    return audit


def _search_policy_defaults() -> dict[str, Any]:
    return {
        "policy_path": _SEARCH_POLICY_RELATIVE_PATH,
        "policy_loaded": False,
        "policy_errors": 0,
        "policy_events": [],
        "baseline_time_fraction": _BASELINE_TIME_FRACTION,
        "operator_round_limit": _MAX_OPERATOR_ROUNDS,
        "post_baseline_operators_enabled": True,
    }


def _load_policy_module(path: Path) -> Any:
    module_name = f"_scion_cvrp_search_policy_{abs(hash(str(path)))}_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _policy_float(
    *,
    module: Any,
    function_name: str,
    default: float,
    minimum: float,
    maximum: float,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> float:
    try:
        value = _call_policy_function(module, function_name, instance, time_limit_sec)
    except Exception as exc:
        audit["policy_errors"] += 1
        _record_policy_event(audit, "error", f"{function_name} failed: {exc}")
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name} returned non-numeric value {value!r}",
        )
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name} returned non-finite value {value!r}",
        )
        return default
    clamped = min(max(numeric, minimum), maximum)
    if clamped != numeric:
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name}={numeric!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _policy_int(
    *,
    module: Any,
    function_name: str,
    default: int,
    minimum: int,
    maximum: int,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> int:
    try:
        value = _call_policy_function(module, function_name, instance, time_limit_sec)
    except Exception as exc:
        audit["policy_errors"] += 1
        _record_policy_event(audit, "error", f"{function_name} failed: {exc}")
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name} returned non-integer value {value!r}",
        )
        return default
    clamped = min(max(value, minimum), maximum)
    if clamped != value:
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name}={value!r} outside [{minimum}, {maximum}], clamped",
        )
    return clamped


def _policy_bool(
    *,
    module: Any,
    function_name: str,
    default: bool,
    instance: CvrpInstance,
    time_limit_sec: float,
    audit: dict[str, Any],
) -> bool:
    try:
        value = _call_policy_function(module, function_name, instance, time_limit_sec)
    except Exception as exc:
        audit["policy_errors"] += 1
        _record_policy_event(audit, "error", f"{function_name} failed: {exc}")
        return default
    if not isinstance(value, bool):
        audit["policy_errors"] += 1
        _record_policy_event(
            audit,
            "error",
            f"{function_name} returned non-bool value {value!r}",
        )
        return default
    return value


def _call_policy_function(
    module: Any,
    function_name: str,
    instance: CvrpInstance,
    time_limit_sec: float,
) -> Any:
    func = getattr(module, function_name, None)
    if not callable(func):
        raise ValueError(f"missing callable {function_name}")
    return func(instance, time_limit_sec)


def _load_solver_algorithm(
    *,
    workspace_root: str | Path,
    instance: CvrpInstance,
    instance_path: str,
    seed: int,
    rng: random.Random,
    time_limit_sec: float,
    start_time: float,
    adapter: CvrpAdapter,
) -> tuple[CvrpSolution | None, dict[str, Any]]:
    inactive_audit: dict[str, Any] | None = None
    for relative_path in _SOLVER_ALGORITHM_RELATIVE_PATHS:
        solution, audit = _load_solver_algorithm_file(
            workspace_root=workspace_root,
            relative_path=relative_path,
            instance=instance,
            instance_path=instance_path,
            seed=seed,
            rng=rng,
            time_limit_sec=time_limit_sec,
            start_time=start_time,
            adapter=adapter,
        )
        if _solver_algorithm_active(audit) or audit.get("solver_algorithm_errors"):
            return solution, audit
        if inactive_audit is None:
            inactive_audit = audit
    return None, inactive_audit or _solver_algorithm_defaults()


def _load_solver_algorithm_file(
    *,
    workspace_root: str | Path,
    relative_path: str,
    instance: CvrpInstance,
    instance_path: str,
    seed: int,
    rng: random.Random,
    time_limit_sec: float,
    start_time: float,
    adapter: CvrpAdapter,
) -> tuple[CvrpSolution | None, dict[str, Any]]:
    audit = _solver_algorithm_defaults(relative_path)
    workspace = Path(workspace_root).resolve()
    policy_path = (workspace / relative_path).resolve()
    try:
        policy_path.relative_to(workspace)
    except ValueError:
        _record_solver_algorithm_event(
            audit,
            "error",
            f"solver algorithm path escapes workspace: {relative_path}",
        )
        audit["solver_algorithm_errors"] += 1
        return None, audit
    if not policy_path.is_file():
        return None, audit

    try:
        module = _load_policy_module(policy_path)
    except Exception as exc:
        audit["solver_algorithm_errors"] += 1
        _record_solver_algorithm_event(
            audit,
            "error",
            f"solver algorithm load failed: {exc}",
        )
        return None, audit

    solve_fn = getattr(module, "solve", None)
    audit["solver_algorithm_loaded"] = True
    if not callable(solve_fn):
        audit["solver_algorithm_errors"] += 1
        _record_solver_algorithm_event(audit, "error", "missing callable solve")
        return None, audit

    context = _SolverAlgorithmContext(
        instance=instance,
        instance_path=instance_path,
        seed=seed,
        rng=rng,
        time_limit_sec=time_limit_sec,
        start_time=start_time,
        adapter=adapter,
        audit=audit,
    )
    call_start_ns = time.monotonic_ns()
    try:
        raw_solution = solve_fn(instance, rng, time_limit_sec, context)
    except Exception as exc:
        audit["solver_algorithm_errors"] += 1
        _record_solver_algorithm_event(audit, "error", f"solve failed: {exc}")
        _finalize_solver_algorithm_timing(audit, call_start_ns)
        return None, audit

    _finalize_solver_algorithm_timing(audit, call_start_ns)
    if raw_solution is None:
        audit["solver_algorithm_stop_reason"] = "inactive"
        _record_solver_algorithm_event(
            audit,
            "info",
            "solve returned None; solver_algorithm inactive",
        )
        return None, audit

    solution = _coerce_solution(raw_solution)
    if solution is None:
        audit["solver_algorithm_errors"] += 1
        audit["solver_algorithm_stop_reason"] = "invalid_output"
        _record_solver_algorithm_event(
            audit,
            "error",
            "solve returned a value that cannot be coerced to CvrpSolution",
        )
        return None, audit

    valid, reason = _solution_is_valid(adapter, instance, solution)
    if not valid:
        audit["solver_algorithm_errors"] += 1
        audit["solver_algorithm_stop_reason"] = "invalid_solution"
        _record_solver_algorithm_event(
            audit,
            "error",
            f"solve returned invalid solution: {reason}",
        )
        return None, audit

    objective = _objective_for_solution(adapter, instance, solution)
    audit["solver_algorithm_active"] = True
    audit["solver_algorithm_solution_valid"] = True
    audit["solver_algorithm_solution_routes"] = len(solution.routes)
    audit["solver_algorithm_objective"] = dict(objective)
    audit["solver_algorithm_total_distance"] = float(
        objective.get("total_distance", 0.0)
    )
    audit["solver_algorithm_fleet_violation"] = float(
        objective.get("fleet_violation", 0.0)
    )
    stop_reason = str(audit.get("solver_algorithm_stop_reason") or "").strip()
    audit["solver_algorithm_stop_reason"] = (
        "completed" if stop_reason in {"", "inactive"} else stop_reason
    )
    _drop_inactive_solver_algorithm_records(audit)
    if not audit.get("solver_algorithm_phase_runtime_ms"):
        audit["solver_algorithm_phase_runtime_ms"] = {
            "solve": audit["solver_algorithm_elapsed_ms"]
        }
    return solution, audit


def _solver_algorithm_defaults(
    relative_path: str = _BASELINE_ALGORITHM_RELATIVE_PATH,
) -> dict[str, Any]:
    return {
        "solver_algorithm_path": relative_path,
        "solver_algorithm_loaded": False,
        "solver_algorithm_active": False,
        "solver_algorithm_errors": 0,
        "solver_algorithm_events": [],
        "solver_algorithm_elapsed_ms": 0,
        "solver_algorithm_phase_runtime_ms": {"inactive": 0},
        "solver_algorithm_solution_valid": False,
        "solver_algorithm_solution_routes": 0,
        "solver_algorithm_objective": {"fleet_violation": 0.0, "total_distance": 0.0},
        "solver_algorithm_total_distance": 0.0,
        "solver_algorithm_fleet_violation": 0.0,
        "solver_algorithm_baseline_calls": 0,
        "solver_algorithm_construction_calls": 0,
        "solver_algorithm_search_iterations": 0,
        "solver_algorithm_move_attempts": 0,
        "solver_algorithm_accepted_moves": 0,
        "solver_algorithm_best_delta": 0.0,
        "solver_algorithm_phase_delta_sum": {"none": 0.0},
        "solver_algorithm_phase_best_delta": {"none": 0.0},
        "solver_algorithm_phase_improvement_counts": {"none": 0},
        "solver_algorithm_context_records": {"inactive": 0},
        "solver_algorithm_stop_reason": "inactive",
    }


def _solver_algorithm_active(audit: Mapping[str, Any] | None) -> bool:
    return bool(audit and audit.get("solver_algorithm_active"))


class _ObjectiveValue(dict):
    """Mapping objective value with lexicographic CVRP comparison helpers."""

    def _key(self) -> tuple[float, float]:
        return (
            float(self.get("fleet_violation", 0.0)),
            float(self.get("total_distance", 0.0)),
        )

    @staticmethod
    def _coerce_key(other: Any) -> tuple[float, float] | None:
        if isinstance(other, Mapping):
            return (
                float(other.get("fleet_violation", 0.0)),
                float(other.get("total_distance", 0.0)),
            )
        if isinstance(other, (list, tuple)) and len(other) >= 2:
            return (float(other[0]), float(other[1]))
        return None

    def __getitem__(self, key: Any) -> Any:
        if key == 0:
            return self.get("fleet_violation", 0.0)
        if key == 1:
            return self.get("total_distance", 0.0)
        return super().__getitem__(key)

    def __lt__(self, other: Any) -> bool:
        other_key = self._coerce_key(other)
        if other_key is None:
            return NotImplemented
        return self._key() < other_key

    def __le__(self, other: Any) -> bool:
        other_key = self._coerce_key(other)
        if other_key is None:
            return NotImplemented
        return self._key() <= other_key

    def __gt__(self, other: Any) -> bool:
        other_key = self._coerce_key(other)
        if other_key is None:
            return NotImplemented
        return self._key() > other_key

    def __ge__(self, other: Any) -> bool:
        other_key = self._coerce_key(other)
        if other_key is None:
            return NotImplemented
        return self._key() >= other_key


def _record_solver_algorithm_event(
    audit: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    events = audit.setdefault("solver_algorithm_events", [])
    if len(events) >= 20:
        return
    events.append(
        {
            "policy": _SOLVER_ALGORITHM_RELATIVE_PATH,
            "status": status,
            "detail": detail,
        }
    )


def _finalize_solver_algorithm_timing(
    audit: dict[str, Any],
    call_start_ns: int,
) -> None:
    elapsed_ms = int((time.monotonic_ns() - call_start_ns) / 1_000_000)
    audit["solver_algorithm_elapsed_ms"] = elapsed_ms
    phase_runtime = audit.get("solver_algorithm_phase_runtime_ms")
    if not isinstance(phase_runtime, dict) or not phase_runtime:
        audit["solver_algorithm_phase_runtime_ms"] = {"solve": elapsed_ms}


def _drop_inactive_solver_algorithm_records(audit: dict[str, Any]) -> None:
    for key in (
        "solver_algorithm_phase_runtime_ms",
        "solver_algorithm_context_records",
    ):
        values = audit.get(key)
        if isinstance(values, dict) and len(values) > 1:
            values.pop("inactive", None)


class _SolverAlgorithmContext:
    """Bounded helper API for generated full-algorithm CVRP solvers."""

    def __init__(
        self,
        *,
        instance: CvrpInstance,
        instance_path: str,
        seed: int,
        rng: random.Random,
        time_limit_sec: float,
        start_time: float,
        adapter: CvrpAdapter,
        audit: dict[str, Any],
    ) -> None:
        self.instance = instance
        self.instance_path = instance_path
        self.seed = seed
        self.rng = rng
        self.time_limit_sec = time_limit_sec
        self._start_time = start_time
        self._adapter = adapter
        self._audit = audit

    def remaining_time(self) -> float:
        return _remaining_time_sec(self._start_time, self.time_limit_sec)

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._start_time) * 1000)

    def make_solution(self, routes: Any) -> CvrpSolution:
        return CvrpSolution(
            routes=tuple(tuple(int(customer) for customer in route) for route in routes)
        )

    def is_valid(self, solution: Any) -> bool:
        coerced = _coerce_solution(solution)
        if coerced is None:
            return False
        valid, _reason = _solution_is_valid(self._adapter, self.instance, coerced)
        return valid

    def objective(self, solution: Any) -> _ObjectiveValue:
        coerced = _coerce_solution(solution)
        if coerced is None:
            raise ValueError("solution cannot be coerced to CvrpSolution")
        valid, reason = _solution_is_valid(self._adapter, self.instance, coerced)
        if not valid:
            raise ValueError(f"invalid solution: {reason}")
        return _ObjectiveValue(
            _objective_for_solution(self._adapter, self.instance, coerced)
        )

    def objective_key(self, solution: Any) -> tuple[float, float]:
        objective = self.objective(solution)
        return (float(objective[0]), float(objective[1]))

    def is_better(self, candidate: Any, incumbent: Any) -> bool:
        return self.objective_key(candidate) < self.objective_key(incumbent)

    def nearest_neighbor(
        self,
        *,
        construction_mode: str = _DEFAULT_CONSTRUCTION_MODE,
        construction_bias: float = _DEFAULT_CONSTRUCTION_BIAS,
    ) -> CvrpSolution:
        self._audit["solver_algorithm_construction_calls"] = _as_nonnegative_int(
            self._audit.get("solver_algorithm_construction_calls")
        ) + 1
        return solve(
            self.instance,
            self.rng,
            construction_mode=construction_mode,
            construction_bias=construction_bias,
        )

    def baseline(
        self,
        initial_solution: Any | None = None,
        *,
        time_budget_sec: float | None = None,
        time_limit_sec: float | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> CvrpSolution:
        self._audit["solver_algorithm_baseline_calls"] = _as_nonnegative_int(
            self._audit.get("solver_algorithm_baseline_calls")
        ) + 1
        if (
            time_budget_sec is None
            and time_limit_sec is None
            and isinstance(initial_solution, (int, float))
            and not isinstance(initial_solution, bool)
        ):
            time_budget_sec = float(initial_solution)
            initial_solution = None
        seed_solution = _coerce_solution(initial_solution)
        if time_budget_sec is None and time_limit_sec is not None:
            time_budget_sec = time_limit_sec
        budget = float(time_budget_sec) if time_budget_sec is not None else 0.0
        if budget <= 0:
            budget = max(0.05, self.remaining_time() * _BASELINE_TIME_FRACTION)
        budget = max(
            0.05,
            min(
                budget,
                max(0.05, self.remaining_time() - _bounded_exit_reserve_sec(
                    self.time_limit_sec,
                    _MAIN_SEARCH_EXIT_RESERVE_SEC,
                )),
            ),
        )
        path = Path(self.instance_path).resolve(strict=False)
        baseline_root = _find_vrp_baseline_root()
        if (
            path.suffix.lower() == ".vrp"
            and baseline_root is not None
            and _baseline_required_for_instance(path)
        ):
            try:
                solution, _audit = _solve_with_vrp_baseline(
                    instance=self.instance,
                    instance_path=path,
                    seed=self.seed,
                    time_limit_sec=budget,
                    baseline_root=baseline_root,
                    baseline_required=True,
                    baseline_policy_params=params,
                )
                return solution
            except Exception as exc:
                _record_solver_algorithm_event(
                    self._audit,
                    "warning",
                    f"context.baseline fallback to nearest_neighbor: {exc}",
                )
        if seed_solution is not None and self.is_valid(seed_solution):
            return seed_solution
        return self.nearest_neighbor()

    def record_phase(self, name: str, elapsed_ms: int | float) -> None:
        phase = str(name or "").strip() or "unnamed"
        runtime = self._audit.setdefault("solver_algorithm_phase_runtime_ms", {})
        if not isinstance(runtime, dict):
            runtime = {}
            self._audit["solver_algorithm_phase_runtime_ms"] = runtime
        runtime[phase] = _as_nonnegative_int(runtime.get(phase)) + _as_nonnegative_int(
            elapsed_ms
        )
        records = self._audit.setdefault("solver_algorithm_context_records", {})
        if not isinstance(records, dict):
            records = {}
            self._audit["solver_algorithm_context_records"] = records
        records[phase] = _as_nonnegative_int(records.get(phase)) + 1

    def record_iteration(self, phase: str = "search", count: int = 1) -> None:
        phase_name = str(phase or "").strip() or "search"
        increment = _as_nonnegative_int(count)
        if increment <= 0:
            increment = 1
        self._audit["solver_algorithm_search_iterations"] = _as_nonnegative_int(
            self._audit.get("solver_algorithm_search_iterations")
        ) + increment
        records = self._audit.setdefault("solver_algorithm_context_records", {})
        if not isinstance(records, dict):
            records = {}
            self._audit["solver_algorithm_context_records"] = records
        key = f"{phase_name}_iterations"
        records[key] = _as_nonnegative_int(records.get(key)) + increment

    def record_move(
        self,
        phase: str,
        *,
        attempted: int = 1,
        accepted: int = 0,
        delta: int | float = 0.0,
        best_improved: bool = False,
    ) -> None:
        phase_name = str(phase or "").strip() or "search"
        attempts = _as_nonnegative_int(attempted)
        accepts = _as_nonnegative_int(accepted)
        if attempts <= 0 and accepts <= 0:
            attempts = 1
        self._audit["solver_algorithm_move_attempts"] = _as_nonnegative_int(
            self._audit.get("solver_algorithm_move_attempts")
        ) + attempts
        self._audit["solver_algorithm_accepted_moves"] = _as_nonnegative_int(
            self._audit.get("solver_algorithm_accepted_moves")
        ) + accepts
        try:
            delta_value = max(0.0, float(delta))
        except (TypeError, ValueError):
            delta_value = 0.0
        phase_delta = self._audit.setdefault("solver_algorithm_phase_delta_sum", {})
        if not isinstance(phase_delta, dict):
            phase_delta = {}
            self._audit["solver_algorithm_phase_delta_sum"] = phase_delta
        phase_delta.pop("none", None)
        phase_delta[phase_name] = float(phase_delta.get(phase_name, 0.0)) + delta_value
        phase_best = self._audit.setdefault("solver_algorithm_phase_best_delta", {})
        if not isinstance(phase_best, dict):
            phase_best = {}
            self._audit["solver_algorithm_phase_best_delta"] = phase_best
        phase_best.pop("none", None)
        phase_best[phase_name] = max(float(phase_best.get(phase_name, 0.0)), delta_value)
        counts = self._audit.setdefault("solver_algorithm_phase_improvement_counts", {})
        if not isinstance(counts, dict):
            counts = {}
            self._audit["solver_algorithm_phase_improvement_counts"] = counts
        if attempts > 0 or accepts > 0:
            counts.pop("none", None)
            counts.setdefault(phase_name, 0)
        if accepts > 0 and (delta_value > 0.0 or best_improved):
            counts[phase_name] = _as_nonnegative_int(counts.get(phase_name)) + accepts
        self._audit["solver_algorithm_best_delta"] = max(
            float(self._audit.get("solver_algorithm_best_delta") or 0.0),
            delta_value,
        )

    def set_stop_reason(self, reason: str) -> None:
        value = str(reason or "").strip()
        if value:
            self._audit["solver_algorithm_stop_reason"] = value


def _record_policy_event(audit: dict[str, Any], status: str, detail: str) -> None:
    events = audit["policy_events"]
    if len(events) >= 10:
        return
    events.append({"policy": _SEARCH_POLICY_RELATIVE_PATH, "status": status, "detail": detail})


def _baseline_time_budget(
    time_limit_sec: float,
    baseline_time_fraction: float = _BASELINE_TIME_FRACTION,
) -> float:
    if time_limit_sec <= 0:
        return 0.0
    return max(0.05, float(time_limit_sec) * float(baseline_time_fraction))


def _solve_with_vrp_baseline(
    *,
    instance: CvrpInstance,
    instance_path: Path,
    seed: int,
    time_limit_sec: float,
    baseline_root: Path,
    baseline_required: bool,
    baseline_policy_params: Mapping[str, Any] | None = None,
) -> tuple[CvrpSolution, dict[str, Any]]:
    root = str(baseline_root)
    if root not in sys.path:
        sys.path.insert(0, root)

    from src.parser import parse_vrp  # type: ignore
    from src.solver import solve as solve_vrp  # type: ignore

    vrp_instance = parse_vrp(str(instance_path))
    allowed_routes = instance.allowed_routes
    if allowed_routes is None:
        allowed_routes = instance.bks_routes
    result = solve_vrp(
        vrp_instance,
        time_limit=time_limit_sec,
        seed=seed,
        max_routes=allowed_routes,
        **dict(baseline_policy_params or {}),
    )
    routes = tuple(
        tuple(
            _map_vrp_customer_to_scion(
                int(customer),
                vrp_instance.depot,
                vrp_instance.dimension,
            )
            for customer in route.customers
        )
        for route in result.solution.routes
        if route.customers
    )
    solution = CvrpSolution(routes=routes)
    audit = {
        "baseline_mode": "vrp_alns_vns",
        "baseline_required": baseline_required,
        "baseline_budget_s": time_limit_sec,
        "baseline_elapsed_s": result.elapsed,
        "baseline_iterations": result.iterations,
        "baseline_cost": result.best_cost,
        "baseline_routes": len(routes),
    }
    valid, reason = _solution_is_valid(CvrpAdapter(object()), instance, solution)
    if not valid:
        raise ValueError(f"vrp baseline produced invalid Scion solution: {reason}")
    return solution, audit


def _map_vrp_customer_to_scion(customer: int, depot: int, dimension: int) -> int:
    """Map vrp/src zero-based node ids to Scion's depot-first id space."""
    raw_id = customer + 1
    raw_depot_id = depot + 1
    if raw_id == raw_depot_id:
        return 0
    scion_id = 1
    for candidate_raw_id in range(1, dimension + 1):
        if candidate_raw_id == raw_depot_id:
            continue
        if candidate_raw_id == raw_id:
            return scion_id
        scion_id += 1
    raise ValueError(f"unknown vrp customer id {customer}")


def _apply_neighborhood_portfolio(
    operators: tuple[_LoadedOperator, ...],
    *,
    audit: dict[str, Any],
    max_operator_rounds: int,
) -> tuple[_LoadedOperator, ...]:
    enabled = {
        str(component)
        for component in audit.get("enabled_components", [])
        if str(component) in _ALLOWED_PORTFOLIO_COMPONENTS
    }
    component_weights = audit.get("component_weights")
    if not isinstance(component_weights, Mapping):
        component_weights = _DEFAULT_COMPONENT_WEIGHTS
    candidate_limits = audit.get("candidate_limits")
    if not isinstance(candidate_limits, Mapping):
        candidate_limits = _DEFAULT_CANDIDATE_LIMITS

    for component in enabled:
        audit["component_attempts"].setdefault(component, 0)
        audit["component_accepted"].setdefault(component, 0)
        audit["component_runtime_ms"].setdefault(component, 0)

    effective_rounds = min(
        max_operator_rounds,
        int(candidate_limits.get("max_rounds", _MAX_OPERATOR_ROUNDS)),
    )
    audit["portfolio_effective_round_limit"] = max(0, effective_rounds)
    top_k = max(0, int(candidate_limits.get("top_k", _MAX_PORTFOLIO_TOP_K)))

    filtered = [operator for operator in operators if operator.component in enabled]
    filtered.sort(
        key=lambda op: (
            -op.weight * float(component_weights.get(op.component, 1.0)),
            op.order,
        )
    )
    if top_k == 0:
        audit["operator_loaded"] = 0
        audit["portfolio_stop_reason"] = "top_k_zero"
        return tuple()
    scheduled = tuple(filtered[:top_k])
    audit["operator_loaded"] = len(scheduled)
    if operators and not scheduled and not audit["portfolio_stop_reason"]:
        audit["portfolio_stop_reason"] = "no_enabled_components"
    return scheduled


def _portfolio_attempt_limit_reached(
    audit: dict[str, Any],
    component: str,
) -> bool:
    candidate_limits = audit.get("candidate_limits")
    if not isinstance(candidate_limits, Mapping):
        return False
    component_attempts = audit.get("component_attempts")
    if not isinstance(component_attempts, Mapping):
        return False
    total_limit = int(candidate_limits.get("total_attempts", _MAX_PORTFOLIO_ATTEMPTS))
    total_attempts = sum(_as_nonnegative_int(value) for value in component_attempts.values())
    if total_attempts >= total_limit:
        return True
    component_limit = int(
        candidate_limits.get(
            component,
            candidate_limits.get("per_component_attempts", _MAX_PORTFOLIO_ATTEMPTS),
        )
    )
    return _as_nonnegative_int(component_attempts.get(component)) >= component_limit


def _record_component_runtime(
    audit: dict[str, Any],
    component: str,
    start_ns: int,
) -> None:
    elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
    runtime = audit["component_runtime_ms"]
    runtime[component] = _as_nonnegative_int(runtime.get(component)) + elapsed_ms


def _operator_component(entry: Mapping[str, Any], instance: Any) -> str:
    raw = entry.get("category")
    if not raw:
        raw = getattr(instance, "category", "")
    component = str(raw or "").strip()
    if component in _ALLOWED_PORTFOLIO_COMPONENTS:
        return component
    return "registry_operator"


def _operator_path(workspace: Path, file_path: str) -> Path | None:
    if not file_path:
        return None
    rel = Path(file_path)
    if rel.is_absolute():
        return None
    target = (workspace / rel).resolve()
    try:
        target.relative_to(workspace)
    except ValueError:
        return None
    return target


def _load_operator_instance(path: Path, class_name: str, index: int) -> Any:
    module_name = f"_scion_cvrp_operator_{index}_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    cls = getattr(module, class_name)
    return cls()


def _coerce_weight(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _coerce_solution(candidate: Any) -> CvrpSolution | None:
    """Accept canonical or structurally equivalent CvrpSolution objects.

    Generated operators commonly import ``CvrpSolution`` from workspace-local
    ``models.py`` while the solver imports the package model. Those are distinct
    class objects in Python, but the solution contract is structural: a routes
    tuple of customer-id sequences. Coercing here preserves the adapter boundary
    while still rejecting genuinely invalid outputs fail-closed.
    """

    if isinstance(candidate, CvrpSolution):
        return candidate
    if isinstance(candidate, Mapping):
        routes = candidate.get("routes")
        if routes is None:
            return None
        try:
            return CvrpSolution(
                routes=tuple(tuple(int(customer) for customer in route) for route in routes)
            )
        except (TypeError, ValueError):
            return None
    routes = getattr(candidate, "routes", None)
    if routes is None:
        return None
    try:
        normalized = tuple(
            tuple(int(customer) for customer in route)
            for route in routes
        )
    except (TypeError, ValueError):
        return None
    return CvrpSolution(routes=normalized)


def _solution_is_valid(
    adapter: CvrpAdapter,
    instance: CvrpInstance,
    solution: CvrpSolution,
) -> tuple[bool, str]:
    raw = {"routes": [list(route) for route in solution.routes], "feasible": True}
    try:
        artifact = adapter.deserialize_solver_output(raw, instance)
        raw["objective"] = dict(adapter.recompute_objective(artifact, instance))
        artifact = adapter.deserialize_solver_output(raw, instance)
        consistency = adapter.check_solution_consistency(artifact, instance)
        if not consistency.passed:
            return False, "; ".join(consistency.reasons[:3])
        feasibility = adapter.check_feasibility(artifact, instance)
        if not feasibility.passed:
            return False, "; ".join(feasibility.reasons[:3])
    except Exception as exc:
        return False, str(exc)
    return True, ""


def _objective_for_solution(
    adapter: CvrpAdapter,
    instance: CvrpInstance,
    solution: CvrpSolution,
) -> dict[str, int | float]:
    raw = {"routes": [list(route) for route in solution.routes], "feasible": True}
    artifact = adapter.deserialize_solver_output(raw, instance)
    return dict(adapter.recompute_objective(artifact, instance))


def _lexicographic_improves(
    candidate: Mapping[str, int | float],
    current: Mapping[str, int | float],
) -> bool:
    candidate_fleet = float(candidate.get("fleet_violation", 0))
    current_fleet = float(current.get("fleet_violation", 0))
    if candidate_fleet < current_fleet:
        return True
    if candidate_fleet > current_fleet:
        return False
    candidate_distance = float(candidate.get("total_distance", 0.0))
    current_distance = float(current.get("total_distance", 0.0))
    return candidate_distance < current_distance - _OBJECTIVE_TOLERANCE


def _time_exhausted(start_time: float, time_limit_sec: float) -> bool:
    if time_limit_sec <= 0:
        return False
    return time.perf_counter() - start_time >= time_limit_sec


def _remaining_time_sec(
    start_time: float | None,
    time_limit_sec: float | None,
) -> float:
    if start_time is None or time_limit_sec is None or time_limit_sec <= 0:
        return 0.0
    return max(0.0, float(time_limit_sec) - (time.perf_counter() - start_time))


def _bounded_exit_reserve_sec(
    time_limit_sec: float | None,
    requested_reserve_sec: float,
) -> float:
    requested = max(0.0, float(requested_reserve_sec))
    if time_limit_sec is None or time_limit_sec <= 0:
        return requested
    scaled_cap = max(0.05, float(time_limit_sec) * _MAX_EXIT_RESERVE_FRACTION)
    return min(requested, scaled_cap)


def _main_search_time_exhausted(start_time: float, time_limit_sec: float) -> bool:
    if time_limit_sec <= 0:
        return False
    return _remaining_time_sec(
        start_time,
        time_limit_sec,
    ) <= _bounded_exit_reserve_sec(time_limit_sec, _MAIN_SEARCH_EXIT_RESERVE_SEC)


def _route_pool_time_exhausted(
    start_time: float | None,
    time_limit_sec: float | None,
    *,
    exit_reserve_sec: float = _ROUTE_POOL_EXIT_RESERVE_SEC,
) -> bool:
    if start_time is None or time_limit_sec is None or time_limit_sec <= 0:
        return False
    return _remaining_time_sec(start_time, time_limit_sec) <= max(
        0.0,
        _bounded_exit_reserve_sec(time_limit_sec, exit_reserve_sec),
    )


def _record_event(
    audit: dict[str, Any],
    operator_name: str,
    status: str,
    detail: str,
) -> None:
    events = audit["operator_events"]
    if len(events) >= 20:
        return
    payload = {"operator": operator_name, "status": status}
    if detail:
        payload["detail"] = detail
    events.append(payload)


if __name__ == "__main__":
    _main()
