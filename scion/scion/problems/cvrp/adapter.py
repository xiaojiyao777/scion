"""CVRP ProblemAdapter implementation for Scion v0.4."""
from __future__ import annotations

import ast
import math
from pathlib import Path
import random
import signal
import threading
import types
from typing import Any, Mapping, Sequence

from scion.core.models import patch_file_changes
from scion.problem.contracts import CheckReport, LowerBoundEstimate, SolverArtifact
from scion.problem.spec import ProblemSpecV1
from scion.problems.cvrp.cvrplib import load_cvrplib_instance
from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution


_POLICY_PREVIEW_TIME_LIMIT_SEC = 5.0
_POLICY_PREVIEW_EXEC_TIMEOUT_SEC = 2.0
_ALLOWED_CONSTRUCTION_MODES = frozenset(
    {
        "nearest_neighbor",
        "nearest_neighbor_demand_bias",
        "demand_descending",
        "sequential",
    }
)
_ALLOWED_PORTFOLIO_COMPONENTS = frozenset(
    {
        "route_local",
        "route_pair",
        "ruin_recreate",
        "registry_operator",
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
_ALLOWED_MAIN_SEARCH_PHASE_OBJECTIVES = frozenset(
    {
        "construction_distance",
        "baseline_distance",
        "phase_best_distance",
        "recovery_to_phase_best",
        "runtime_neutrality",
    }
)
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
_ALLOWED_ROUTE_POOL_ACTIVATIONS = frozenset(
    {"adaptive", "always", "medium_large_only", "disabled"}
)
_ALLOWED_MAIN_SEARCH_BASELINE_BUDGET_POLICIES = frozenset(
    {"declared", "formal_floor"}
)
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
_PORTFOLIO_LIMIT_RANGES = {
    "max_rounds": (0, 6),
    "top_k": (0, 32),
    "total_attempts": (0, 200),
    "per_component_attempts": (0, 80),
    "route_local": (0, 200),
    "route_pair": (0, 200),
    "ruin_recreate": (0, 200),
    "registry_operator": (0, 200),
}
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
    {*_MAIN_SEARCH_STRATEGY_REQUIRED_KEYS, "problem_adaptation"}
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
_BASELINE_POLICY_ALLOWED_KEYS = frozenset(
    {
        "destroy_ratio",
        "segment_length",
        "reaction_factor",
        "vns_max_no_improve",
        "use_vns",
        "cw_threshold",
        "vns_threshold",
        "alns_threshold",
        "max_destroy_customers",
    }
)
_ALNS_VNS_POLICY_ALLOWED_KEYS = frozenset(
    {"enabled", "components", "component_weights", "params"}
)
_ALNS_VNS_ALLOWED_COMPONENTS = frozenset({"alns", "vns"})
_DESTROY_REPAIR_POLICY_ALLOWED_KEYS = frozenset(
    {
        "enabled",
        "destroy_selectors",
        "repair_selectors",
        "subset_strategy",
        "max_destroy_customers",
        "repair_budget_per_customer",
        "fallback_to_smaller_subsets",
        "phase_best_preference",
    }
)
_DESTROY_REPAIR_ALLOWED_DESTROY_SELECTOR_VALUES = (
    "worst_removal",
    "route_diverse_worst",
)
_DESTROY_REPAIR_ALLOWED_DESTROY_SELECTORS = frozenset(
    _DESTROY_REPAIR_ALLOWED_DESTROY_SELECTOR_VALUES
)
_DESTROY_REPAIR_ALLOWED_REPAIR_SELECTOR_VALUES = ("regret_2", "cheapest")
_DESTROY_REPAIR_ALLOWED_REPAIR_SELECTORS = frozenset(
    _DESTROY_REPAIR_ALLOWED_REPAIR_SELECTOR_VALUES
)
_DESTROY_REPAIR_SUBSET_STRATEGY_VALUES = (
    "prefix_shifted_route_diverse",
    "single_worst",
    "route_diverse",
)
_DESTROY_REPAIR_SUBSET_STRATEGIES = frozenset(
    _DESTROY_REPAIR_SUBSET_STRATEGY_VALUES
)
_ROUTE_PAIR_POLICY_ALLOWED_KEYS = frozenset(
    {"enabled", "scoring_terms", "move_families", "candidate_limits"}
)
_ROUTE_PAIR_ALLOWED_SCORING_TERMS = frozenset(
    {"route_distance", "removal_saving", "load_gap", "distance_saving"}
)
_ROUTE_PAIR_ALLOWED_MOVE_FAMILIES = frozenset({"customer_swap"})
_ROUTE_PAIR_CANDIDATE_LIMIT_RANGES = {
    "pair_cap": (0, 500),
    "position_cap": (0, 32),
}
_ACCEPTANCE_RESTART_POLICY_ALLOWED_KEYS = frozenset(
    {
        "enabled",
        "min_distance_improvement",
        "recovery_only_policy",
        "restart",
        "perturbation",
    }
)
_ACCEPTANCE_RECOVERY_POLICIES = frozenset(
    {"allow", "reject_recovery_only", "phase_best_preferred"}
)
_POLICY_INSTANCE_API_TEXT = (
    "Safe CvrpInstance API for policy functions: use "
    "`instance.depot`, `instance.customer_ids`, `instance.customer_count`, "
    "`instance.demands[customer_id]`, `instance.capacity`, "
    "`instance.distance(i, j)`, `instance.route_load(route)`, and "
    "`instance.route_distance(route)`. `instance.demand(customer_id)` remains "
    "available for direct demand lookup. Never use `instance.customers`; that "
    "attribute is intentionally not defined and will fail synthetic preview or "
    "runtime audit when reached."
)


def _format_literal_values(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class CvrpAdapter:
    def __init__(self, spec: ProblemSpecV1) -> None:
        self._spec = spec

    @property
    def spec(self) -> ProblemSpecV1:
        return self._spec

    def mechanism_novelty_provider(self) -> Any:
        from scion.problems.cvrp.mechanism_novelty import (
            CvrpMechanismNoveltyProvider,
        )

        return CvrpMechanismNoveltyProvider()

    def stagnation_object_model_markers(self) -> tuple[str, ...]:
        return (
            "_solution",
            "_route",
            "from_public",
            "from_cvrp_solution",
            "from_routes",
            "to_public",
            "cannot be coerced to cvrpsolution",
            "solver_algorithm_errors=",
            "object model",
        )

    def render_problem_summary(self) -> str:
        return (
            "Capacitated Vehicle Routing Problem: build ordered vehicle routes "
            "from a depot to visit each customer exactly once while respecting "
            "vehicle capacity. Promotion objective is lexicographic: minimize "
            "fleet_violation first, then total_distance."
        )

    def render_problem_object(self) -> str:
        return (
            "CVRP problem object for solver-level research.\n\n"
            "Instance model:\n"
            "- One depot and a fixed set of customers with coordinates and "
            "integer demands.\n"
            "- Vehicle capacity is a hard route constraint; every non-depot "
            "customer must be served exactly once.\n"
            "- Safe structural APIs are `instance.customer_ids`, "
            "`instance.customer_count`, `instance.capacity`, "
            "`instance.demands[customer_id]`, `instance.demand(customer_id)`, "
            "`instance.distance(i, j)`, `instance.route_load(route)`, and "
            "`instance.route_distance(route)`. Do not use case identifiers or "
            "`instance.customers`.\n"
            "- Main size terms are customer_count, route_count, route_length, "
            "removed_customer_count, candidate_pair_count, and time_limit_sec.\n\n"
            "Solution model:\n"
            "- A solution is `CvrpSolution(routes=...)`; routes use implicit "
            "depot format and contain customer ids only.\n"
            "- A valid solution preserves the customer multiset exactly once, "
            "has no depot ids inside routes, respects capacity on every route, "
            "and reports a finite objective.\n"
            "- Objective recomputation is adapter-owned: fleet_violation is "
            "derived from route-count/reference-route constraints when "
            "available, and total_distance is recomputed from the route order.\n\n"
            "Objective policy:\n"
            "- Lexicographic minimization: fleet_violation first, then "
            "total_distance.\n"
            "- BKS/gap is diagnostic context only; it is not an acceptance "
            "criterion for generated research changes.\n\n"
            "Solver lifecycle:\n"
            "- Construct an initial route set, run the repo-local ALNS+VNS "
            "baseline when available, then run package-owned improvement "
            "phases and optional registry operators under the remaining time "
            "budget.\n"
            "- Candidate solutions are accepted only when feasible and strictly "
            "better under the lexicographic objective.\n"
            "- Recovery-only or current-state movements are not solver-quality "
            "evidence unless they create phase-best objective movement.\n\n"
            "Move/design grammar:\n"
            "- Useful designs should reason about route construction, route "
            "pair restructuring, bounded local search, ruin/recreate, "
            "acceptance/restart/perturbation, and baseline-budget allocation "
            "as parts of one solver lifecycle.\n"
            "- Component policies are implementation hooks. They should support "
            "a solver-level hypothesis, not become isolated research goals.\n"
            "- Any route edit must preserve customers, capacity, and implicit "
            "depot representation and must have explicit candidate caps.\n\n"
            "Runtime evidence for problem-level hypotheses:\n"
            "- Whole-solver fields: construction distance/routes, baseline "
            "mode/cost/routes/iterations, operator attempts/accepted/skipped, "
            "component phase deltas, objective deltas, stop reasons, runtime, "
            "and selected-surface load/active/error fields.\n"
            "- A useful proposal should predict which lifecycle phase changes, "
            "which objective field moves, and which runtime evidence should "
            "show nonzero accepted phase-best movement.\n"
            "- Do not claim success from active flags, attempts, or selector "
            "values alone."
        )

    def render_solver_mechanics(self) -> str:
        return (
            "The CVRP campaign solver first offers the active "
            "`solver_design` surface a direct full-algorithm hook. The "
            "preferred research target is "
            "`policies/baseline_algorithm.py::solve(instance, rng, "
            "time_limit_sec, context)`, a Scion-controlled copy of the "
            "baseline algorithm body. The older "
            "`policies/solver_algorithm.py` hook remains a compatibility "
            "target. A valid returned solution becomes the solver output and "
            "skips the legacy baseline, lifecycle config, and post-baseline "
            "operator layers. Under a selected `solver_design` run, returning "
            "None is an inactive-hook fallback, not a useful candidate "
            "algorithm; candidates should return a feasible solution from the "
            "branch-owned algorithm body.\n"
            "- For real CVRPLIB .vrp cases, the legacy path uses the "
            "repo-local vrp/src ALNS+VNS baseline when SCION_PROBLEM_DATA_ROOT "
            "or SCION_CVRP_DATA_ROOT points at the vrp directory; JSON and "
            "synthetic smoke fixtures use a deterministic nearest-neighbor "
            "fallback.\n"
            "- The `solver_design` research surface is backed primarily by "
            "`policies/baseline_algorithm.py`, not by a lifecycle/config "
            "table. It may implement construction, route-edit candidate "
            "generation, local search, destroy/repair, recombination, "
            "perturbation, acceptance, and runtime scheduling directly while "
            "the adapter keeps objective, feasibility, parser, seeds, "
            "protocol splits, and Decision rules fixed.\n"
            "- `context.baseline(...)` is a compatibility helper inside the "
            "older solver hook. It is not the research object. New "
            "`baseline_algorithm.py` candidates should modify the controlled "
            "algorithm body itself instead of calling `context.baseline(...)` "
            "and adding post-processing; do not call context.baseline from "
            "the preferred target.\n"
            "- The adapter/solver remains the authority for feasibility, "
            "objective recomputation, runtime limits, seeds, and protocol "
            "evaluation.\n"
            "- Legacy/componentized surfaces are retained only for forced "
            "diagnostics and regression compatibility, not as active "
            "solver-design research goals: `route_local`, `route_pair`, "
            "`ruin_recreate`, `search_policy`, `baseline_policy`, "
            "`construction_policy`, `neighborhood_portfolio`, "
            "`algorithm_blueprint`, `main_search_strategy`, "
            "`alns_vns_policy`, `destroy_repair_policy`, "
            "`route_pair_candidate_policy`, and "
            "`acceptance_restart_policy`.\n"
            "- If a legacy surface is explicitly forced for a diagnostic, treat "
            "it as inactive/legacy outside that forced run. Do not infer that "
            "a component policy is the current research object while "
            "`solver_design` is active.\n"
            "- Not-improving operator outputs are safe no-ops. Exceptions, "
            "infeasible outputs, malformed outputs, invalid solution structures, "
            "and invalid policy or construction-policy returns are runtime audit "
            "failures and cannot be treated as objective ties.\n"
            "- BKS/gap is not used for operator acceptance. Route-count "
            "comparability enters only through fleet_violation when an explicit "
            "allowed route count or reference route count is available."
        )

    def render_research_surface_interface(self, surface_name: str) -> str:
        if surface_name == "construction_policy":
            return (
                "policies/construction_policy.py is a module-level construction "
                "policy file; no class is required.\n\n"
                "Declared signatures:\n"
                "construction_mode(instance, time_limit_sec)\n"
                "construction_bias(instance, time_limit_sec)\n\n"
                "Required functions:\n"
                "def construction_mode(instance, time_limit_sec):\n"
                "    return one of 'nearest_neighbor', "
                "'nearest_neighbor_demand_bias', 'demand_descending', or "
                "'sequential'\n\n"
                "def construction_bias(instance, time_limit_sec):\n"
                "    return a finite numeric value in [0.0, 1.0]\n\n"
                + _POLICY_INSTANCE_API_TEXT
                + "\n\n"
                + "The solver clamps out-of-range bias values but records them as "
                "construction_errors. Unknown modes, exceptions, missing "
                "functions, and non-numeric bias values are runtime audit "
                "failures. Policy functions must be deterministic and must not "
                "read solver outputs, benchmark answers, or external files."
            )
        if surface_name == "search_policy":
            return (
                "policies/search_policy.py is a module-level policy file; no class "
                "is required.\n\n"
                "Declared signatures:\n"
                "baseline_time_fraction(instance, time_limit_sec)\n"
                "max_operator_rounds(instance, time_limit_sec)\n"
                "enable_post_baseline_operators(instance, time_limit_sec)\n\n"
                "Required functions:\n"
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return a numeric fraction in [0.2, 0.95]\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return an int in [0, 20]\n\n"
                "def enable_post_baseline_operators(instance, time_limit_sec):\n"
                "    return a bool\n\n"
                + _POLICY_INSTANCE_API_TEXT
                + "\n\n"
                + "The solver clamps out-of-range numeric values but records them as "
                "policy_errors. Exceptions, missing functions, non-numeric budget "
                "values, and non-bool enable flags are runtime audit failures. "
                "Policy functions must be deterministic and must not read solver "
                "outputs, benchmark answers, or external files."
            )
        if surface_name == "baseline_policy":
            return (
                "policies/baseline_policy.py is a module-level repo-local "
                "baseline policy file; no class is required.\n\n"
                "Declared signature:\n"
                "baseline_params(instance, time_limit_sec)\n\n"
                "Required function:\n"
                "def baseline_params(instance, time_limit_sec):\n"
                "    return a dict with optional bounded keys destroy_ratio, "
                "segment_length, reaction_factor, vns_max_no_improve, use_vns, "
                "cw_threshold, vns_threshold, alns_threshold, and "
                "max_destroy_customers\n\n"
                "Parameter contract:\n"
                "- destroy_ratio: pair of finite numbers in [0.01, 0.80] with "
                "lower <= upper.\n"
                "- segment_length: int in [1, 1000].\n"
                "- reaction_factor: finite number in [0.01, 1.0].\n"
                "- vns_max_no_improve: int in [0, 20000].\n"
                "- use_vns: bool.\n"
                "- cw_threshold, vns_threshold, alns_threshold: ints in "
                "[0, 10000].\n"
                "- max_destroy_customers: int in [1, 500].\n\n"
                + _POLICY_INSTANCE_API_TEXT
                + "\n\n"
                + "Omitted known keys use the vrp/src default values. Unknown "
                "keys, exceptions, non-finite numbers, non-bool toggles, and "
                "out-of-range values increment baseline_policy_errors. The "
                "solver only passes sanitized params into the repo-local "
                "ALNS+VNS baseline."
            )
        if surface_name == "neighborhood_portfolio":
            return (
                "policies/neighborhood_portfolio.py is a module-level portfolio "
                "policy file; no class is required.\n\n"
                "Declared signatures:\n"
                "enabled_components(instance, time_limit_sec)\n"
                "component_weights(instance, time_limit_sec)\n"
                "candidate_limits(instance, time_limit_sec)\n\n"
                "Required functions:\n"
                "def enabled_components(instance, time_limit_sec):\n"
                "    return a non-empty sequence drawn from 'route_local', "
                "'route_pair', 'ruin_recreate', and 'registry_operator'\n\n"
                "def component_weights(instance, time_limit_sec):\n"
                "    return a mapping from component name to a finite numeric "
                "weight multiplier in [0.0, 5.0]\n\n"
                "def candidate_limits(instance, time_limit_sec):\n"
                "    return a mapping with small optional integer keys max_rounds, "
                "top_k, total_attempts, per_component_attempts, or per-component "
                "attempt caps. Keep defaults small: max_rounds around 3, top_k "
                "around 16, and total attempts around 100.\n\n"
                + _POLICY_INSTANCE_API_TEXT
                + "\n\n"
                + "Unknown components, non-finite weights, non-integer limits, and "
                "out-of-range limits are portfolio_errors and runtime audit "
                "failures. The solver owns route moves and uses this policy only "
                "to schedule already-declared bounded components."
            )
        if surface_name in {"solver_design", "solver_algorithm"}:
            return (
                "policies/baseline_algorithm.py is the preferred CVRP "
                "problem-object research surface. It is a Scion-controlled "
                "module-level copy of the baseline algorithm body and a direct "
                "full algorithm hook; no class is required. "
                "policies/solver_algorithm.py remains available only as a "
                "compatibility hook.\n\n"
                "Declared signature:\n"
                "solve(instance, rng, time_limit_sec, context)\n\n"
                "Required function:\n"
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return a CvrpSolution, a structurally equivalent object "
                "with routes, or {'routes': [[customer_id, ...], ...]}.\n\n"
                "Research contract:\n"
                "- You may implement construction, local improvement, "
                "destroy/repair, recombination, perturbation, acceptance, and "
                "time allocation directly in Python.\n"
                "- You may use instance.depot, instance.customer_ids, "
                "instance.customer_count, instance.demands[customer_id], "
                "instance.capacity, "
                "instance.distance(i, j), instance.route_load(route), and "
                "instance.route_distance(route).\n"
                "- You may use context helpers: context.make_solution(routes), "
                "context.nearest_neighbor(), "
                "context.objective(solution), context.objective_key(solution), "
                "context.is_better(candidate, incumbent), "
                "context.is_valid(solution), context.remaining_time() "
                "(seconds), context.remaining_time_ms(), context.elapsed_ms(), "
                "context.record_phase(name, "
                "elapsed_ms), context.record_iteration(phase, count), "
                "context.record_move(phase, attempted=1, accepted=0, "
                "delta=0.0, best_improved=False), and "
                "context.set_stop_reason(reason).\n"
                "- Declare one stable lowercase snake_case mechanism id for "
                "the hypothesis and use that exact id as the phase/mechanism "
                "name passed to context.record_iteration, "
                "context.record_move, and context.record_phase. Runtime "
                "evidence then exposes "
                "solver_algorithm_context_records.{mechanism}_iterations and "
                "solver_algorithm_phase_runtime_ms.{mechanism} for "
                "activation, plus "
                "solver_algorithm_phase_improvement_counts.{mechanism} and "
                "solver_algorithm_phase_best_delta.{mechanism} for effect. "
                "Do not use different aliases for the same declared "
                "mechanism. In hypothesis expected_telemetry, place those "
                "declared runtime field names under activation/effect/budget/"
                "activity categories; never use suffixes such as best_delta, "
                "improvement_counts, phase_runtime, or runtime_ms as "
                "top-level categories.\n"
                "- context.objective returns a mapping with fleet_violation and "
                "total_distance. It also compares lexicographically as "
                "(fleet_violation, total_distance), but explicit field access "
                "or context.objective_key is preferred.\n"
                "- context.nearest_neighbor() returns a CvrpSolution, not "
                "route tuples. Use it directly as a candidate solution. "
                "context.make_solution accepts route iterables and is "
                "idempotent for an existing CvrpSolution or equivalent object.\n"
                "- When editing policies/baseline_modules/*, use the package "
                "object model declared by state.py. Existing construction.py "
                "helpers return internal _Solution objects. _Solution has "
                "copy(), rebuild_index(), remove_empty_routes(), is_feasible(), "
                "and routes_as_tuples(); it does not have from_routes, "
                "from_public, from_cvrp_solution, or to_public bridge methods. "
                "Do not add adapter bridges to state.py unless state.py itself "
                "is the approved target.\n"
                "- Accepted moves are not automatically improvements. Pass "
                "positive delta or best_improved=True to context.record_move "
                "only for objective-improving moves, so telemetry separates "
                "improving from neutral accepted moves.\n"
                "- Runtime is part of the algorithm objective. Use finite "
                "max_rounds/max_passes/top_k caps and poll "
                "context.remaining_time() in seconds or "
                "context.remaining_time_ms() in milliseconds; importing time "
                "is allowed only for "
                "monotonic timing, never for sleeps or external scheduling.\n"
                "- Prefer for-loops over range(max_rounds/max_passes/"
                "customer_count) for bounded search. If you use while, make "
                "the bound statically obvious: a counter compared with a "
                "max_* cap and incremented inside the loop, or a finite "
                "collection condition whose collection is visibly shrunk in "
                "the loop. Avoid while True unless it has a visible "
                "counter-bound break or directly shrinks a finite collection "
                "on each non-break iteration. A local helper such as "
                "within_budget() may guard a while loop only when its return "
                "expression directly references context.remaining_time() or "
                "context.elapsed_ms().\n"
                "- Implement a real algorithm body. For the preferred "
                "baseline_algorithm.py target, do not call context.baseline; "
                "study and change the controlled ALNS/VNS-style body in the "
                "file. A baseline-only wrapper or a baseline budget/params "
                "tweak is not a valid solver-design candidate.\n"
                "- The adapter/solver remains the authority for feasibility, "
                "objective recomputation, runtime limit, seeds, and protocol "
                "evaluation. The algorithm must not modify objectives, "
                "capacity constraints, parser behavior, benchmark data, "
                "protocols, or decision thresholds.\n"
                "- Prefer this surface over component policies or "
                "main_search_plan when the question is algorithm design. "
                "Telemetry may name phases, but phase names must not constrain "
                "the algorithm structure.\n\n"
                + _POLICY_INSTANCE_API_TEXT
                + "\n\n"
                + "Contract preview calls solve on a tiny synthetic instance "
                "and fails closed if the returned solution is malformed or "
                "infeasible. Runtime Verification recomputes the objective "
                "from the fixed adapter and fails selected-surface audit on "
                "exceptions, invalid output, timeout, or missing algorithm "
                "runtime fields."
            )
        if surface_name == "main_search_strategy":
            return (
                "policies/main_search_strategy.py is a module-level "
                "CVRP solver-design surface; no class is required.\n\n"
                "Declared signature:\n"
                "main_search_plan(instance, time_limit_sec)\n\n"
                "Required function:\n"
                "def main_search_plan(instance, time_limit_sec):\n"
                "    return a dict with exactly these top-level keys: enabled, "
                "problem_adaptation, algorithm_body, construction, baseline, "
                "improvement, acceptance, restart, perturbation, "
                "post_baseline_operators_enabled, and "
                "operator_round_limit. Do not return any other top-level key; "
                "`novelty_signature` belongs only to the approved hypothesis "
                "payload, not to code returned by main_search_plan.\n\n"
                "Plan contract:\n"
                "- enabled: bool. The default must be False. Only enabled=True "
                "and a valid plan lets this surface take over the CVRP "
                "algorithm lifecycle.\n"
                "- problem_adaptation: dict declaring how the whole CVRP "
                "problem object is being studied. strategy_family is one of "
                "'balanced_lifecycle', 'baseline_intensification', "
                "'construction_diversification', 'improvement_intensification', "
                "'destroy_repair_recovery', 'route_structure_repair', or "
                "'local_search_cleanup'. instance_profile is a bounded mapping "
                "using keys scale, route_pressure, demand_skew, "
                "distance_structure, route_count_hint, or customer_count. "
                "phase_objective is one of construction_distance, "
                "baseline_distance, phase_best_distance, recovery_to_phase_best, "
                "or runtime_neutrality. component_roles maps lifecycle role "
                "targets to primary/support/probe/disabled; role targets are "
                + _format_literal_values(sorted(_ALLOWED_MAIN_SEARCH_ROLE_TARGETS))
                + ". fallback_order orders only package-owned improvement "
                "components drawn from "
                + _format_literal_values(sorted(_ALLOWED_MAIN_SEARCH_COMPONENTS))
                + ". evidence_targets lists runtime fields expected to move "
                "and must be drawn from "
                + _format_literal_values(sorted(_ALLOWED_MAIN_SEARCH_EVIDENCE_TARGETS))
                + ".\n"
                "- algorithm_body: dict declaring the full algorithm body "
                "that the research process is studying. phase_sequence is a "
                "non-empty sequence drawn from 'construction', 'baseline', "
                "'global_recombination', 'route_structure_repair', "
                "'local_cleanup', 'perturbation', and 'restart'. "
                "baseline_budget_policy is one of declared or formal_floor; "
                "declared means the requested baseline.time_fraction is the "
                "actual formal-run budget, while formal_floor applies the "
                "legacy 0.75 floor. "
                "route_pool_activation is one of adaptive, always, "
                "medium_large_only, or disabled; route_pool_min_customers is "
                "an int in [0, 500]; route_pool_max_rounds is an int in "
                "[0, 8]; local_cleanup_after_recombination and "
                "adaptive_component_budget are bools. Do not rely on hidden "
                "defaults for the lifecycle in enabled solver_design plans.\n"
                "- construction: dict with methods, keep_top_k, and bias. "
                "methods is drawn from 'nearest_neighbor', "
                "'nearest_neighbor_demand_bias', 'demand_descending', and "
                "'sequential'; keep_top_k is an int in [1, 4]; bias is a finite "
                "number in [0.0, 1.0].\n"
                "- baseline: dict with time_fraction in [0.2, 0.95] and params "
                "mapping. params accepts the same sanitized bounded keys as "
                "baseline_policy.baseline_params. For formal-like .vrp runs, "
                "algorithm_body.baseline_budget_policy controls the effective "
                "baseline budget: declared uses this exact fraction, while "
                "formal_floor intentionally applies the legacy 0.75 floor.\n"
                "- improvement: dict with enabled_components, rounds, and top_k. "
                "enabled_components is drawn from 'intra_route_2opt', "
                "'inter_route_relocate', 'route_pair_swap', and "
                "'bounded_destroy_repair', and 'route_pool_recombination'; "
                "enabled plans must include at least one component, rounds in "
                "[1, 8], and top_k in [1, 128]. "
                "Computation time is part of the solver-design objective: "
                "choose baseline fraction, route_pool_max_rounds, rounds, "
                "top_k, activation scope, and adaptive_component_budget as "
                "runtime/quality tradeoff controls, and predict both "
                "phase/objective and runtime evidence they should move. "
                "route_pool_recombination is a solver-owned "
                "whole-solution route-set recombination step; it is intended "
                "for phase-best movement from complete CVRP solutions, not for "
                "single-policy diagnostics. Current formal evidence has already "
                "shown that route_pair_swap + bounded_destroy_repair without "
                "route_pool_recombination can accept recovery moves while still "
                "producing zero phase-best movement; for a whole-problem "
                "solver_design hypothesis, include route_pool_recombination "
                "unless the proposal explicitly tests why route-pool "
                "recombination should be disabled.\n"
                "- Proposal-only semantic identity is part of the hypothesis "
                "contract: `novelty_signature.selected_components` and "
                "`novelty_signature.deep_components_selected` must be "
                "non-empty JSON arrays of component names. Do not use false, "
                "null, or empty arrays for these fields. Never include "
                "`novelty_signature` in main_search_plan's returned dict.\n"
                "- acceptance: dict with min_distance_improvement finite number "
                "in [0.0, 10.0]. It may also include "
                "component_min_distance_improvement, "
                "bounded_destroy_repair_accept_limit in [0, 3], and "
                "recovery_only_policy drawn from allow, reject_recovery_only, "
                "or phase_best_preferred. bounded_destroy_repair keeps a "
                "1.0 default minimum distance-improvement floor except for "
                "destroy_repair_recovery plans or explicit per-component "
                "thresholds.\n"
                "- restart: dict with enabled bool, stagnation_rounds int in "
                "[0, 25], and max_restarts int in [0, 3].\n"
                "- perturbation: dict with enabled bool, strength int in "
                "[1, 8], and max_perturbations int in [0, 4].\n"
                "- post_baseline_operators_enabled: bool. Keep False by default "
                "for this surface unless the hypothesis explicitly needs "
                "registry operators after the owned main loop.\n"
                "- operator_round_limit: int in [0, 20].\n\n"
                + _POLICY_INSTANCE_API_TEXT
                + "\n\n"
                + "Unknown keys, missing required keys when enabled=True, "
                "unknown components, invalid baseline params, non-finite "
                "numbers, out-of-range values, exceptions, and use of "
                "instance.customers increment main_search_strategy_errors. The "
                "solver refuses takeover for invalid plans and selected-surface "
                "runtime audit fails closed."
            )
        if surface_name == "algorithm_blueprint":
            return (
                "policies/algorithm_blueprint.py is a module-level top-level "
                "algorithm lifecycle config surface; no class is required.\n\n"
                "Declared signature:\n"
                "algorithm_plan(instance, time_limit_sec)\n\n"
                "Required function:\n"
                "def algorithm_plan(instance, time_limit_sec):\n"
                "    return a dict with exactly these top-level keys: enabled, "
                "construction_methods, construction_keep_top_k, construction_bias, "
                "baseline_time_fraction, operator_round_limit, "
                "post_baseline_operators_enabled, local_search, and restart.\n\n"
                "Plan contract:\n"
                "- enabled: bool. The default must be False. Only enabled=True "
                "and a valid plan lets this surface take over the lifecycle.\n"
                "- construction_methods: sequence drawn from 'nearest_neighbor', "
                "'nearest_neighbor_demand_bias', 'demand_descending', and "
                "'sequential'.\n"
                "- construction_keep_top_k: int in [1, 4].\n"
                "- construction_bias: finite number in [0.0, 1.0].\n"
                "- baseline_time_fraction: finite number in [0.2, 0.95].\n"
                "- operator_round_limit: int in [0, 20].\n"
                "- post_baseline_operators_enabled: bool.\n"
                "- local_search: dict with enabled_components, rounds, and top_k. "
                "enabled_components is drawn from 'intra_route_2opt' and "
                "'inter_route_relocate'; rounds is an int in [0, 4]; top_k is "
                "an int in [0, 64].\n"
                "- restart: dict with enabled bool and stagnation_rounds int in "
                "[0, 25].\n\n"
                + _POLICY_INSTANCE_API_TEXT
                + "\n\n"
                + "Unknown keys, missing required keys when enabled=True, "
                "unknown components, non-finite numbers, out-of-range values, "
                "and exceptions increment algorithm_blueprint_errors. The "
                "solver then refuses lifecycle takeover and runtime audit fails "
                "closed for selected_surface=algorithm_blueprint."
            )
        if surface_name == "alns_vns_policy":
            return (
                "policies/alns_vns_policy.py is a module-level ALNS/VNS "
                "mechanism policy file; no class is required.\n\n"
                "Required function:\n"
                "def alns_vns_plan(instance, time_limit_sec):\n"
                "    return a dict with enabled bool, components drawn from "
                "'alns'/'vns', component_weights in [0.0, 5.0], and bounded "
                "baseline params.\n\n"
                "Runtime evidence records attempts, active baseline mode, "
                "initial distance, returned distance, objective delta, phase "
                "delta sum, runtime, and stop reason. A useful diagnostic "
                "should predict which before/after objective field changes, "
                "not only attempts or active flags.\n\n"
                + _POLICY_INSTANCE_API_TEXT
            )
        if surface_name == "destroy_repair_policy":
            return (
                "policies/destroy_repair_policy.py is a module-level "
                "destroy/repair mechanism policy file; no class is required.\n\n"
                "Required function:\n"
                "def destroy_repair_plan(instance, time_limit_sec):\n"
                "    return bounded destroy selectors, repair selectors, subset "
                "strategy, max_destroy_customers, repair_budget_per_customer, "
                "fallback flag, and phase_best_preference.\n\n"
                "Return contract:\n"
                "- enabled: bool\n"
                "- destroy_selectors: non-empty sequence containing only "
                + _format_literal_values(_DESTROY_REPAIR_ALLOWED_DESTROY_SELECTOR_VALUES)
                + ". These values select the customer-removal ranking.\n"
                "- repair_selectors: non-empty sequence containing only "
                + _format_literal_values(_DESTROY_REPAIR_ALLOWED_REPAIR_SELECTOR_VALUES)
                + ". These values select the reinsertion scoring path.\n"
                "- subset_strategy: one of "
                + _format_literal_values(_DESTROY_REPAIR_SUBSET_STRATEGY_VALUES)
                + ". This chooses the bounded subset extraction strategy.\n"
                "- max_destroy_customers: int in [1, 12]\n"
                "- repair_budget_per_customer: int in [1, 16]\n"
                "- fallback_to_smaller_subsets: bool\n"
                "- phase_best_preference: bool\n\n"
                "Do not put subset strategies such as 'single_worst' or "
                "'route_diverse' in destroy_selectors; unknown selector values "
                "fail selected-surface runtime audit.\n\n"
                + _POLICY_INSTANCE_API_TEXT
            )
        if surface_name == "route_pair_candidate_policy":
            return (
                "policies/route_pair_candidate_policy.py is a module-level "
                "route-pair candidate policy file; no class is required.\n\n"
                "Required function:\n"
                "def route_pair_plan(instance, time_limit_sec):\n"
                "    return scoring_terms, move_families, and candidate_limits "
                "for bounded route-pair candidate ranking.\n\n"
                + _POLICY_INSTANCE_API_TEXT
            )
        if surface_name == "acceptance_restart_policy":
            return (
                "policies/acceptance_restart_policy.py is a module-level "
                "acceptance/restart policy file; no class is required.\n\n"
                "Required function:\n"
                "def acceptance_restart_plan(instance, time_limit_sec):\n"
                "    return enabled bool, min_distance_improvement, "
                "recovery_only_policy, restart dict, and perturbation dict. "
                "This affects candidate search only; protocol and Decision "
                "thresholds remain unchanged.\n\n"
                + _POLICY_INSTANCE_API_TEXT
            )
        return self.render_operator_interface()

    def render_operator_interface(self) -> str:
        return (
            "class CvrpOperator:\n"
            "    def execute(self, solution: CvrpSolution, instance: CvrpInstance, "
            "rng: random.Random) -> CvrpSolution\n\n"
            "Routes use implicit depot format: each route lists customer ids only. "
            "Operators must preserve visit-once and capacity feasibility, and must "
            "use bounded route-local or route-pair neighborhoods.\n\n"
            "CvrpSolution API: solution.routes is a tuple[tuple[int, ...], ...]. "
            "Return CvrpSolution(routes=tuple_of_routes); do not mutate the input "
            "solution in place. Prefer solution.__class__(routes=...) when creating "
            "a new solution; workspace-local models.CvrpSolution is accepted only "
            "when it has the same routes structure. Start from "
            "`routes = [list(route) for route in solution.routes]`, edit only the "
            "copy, preserve every customer exactly once, check affected route "
            "loads with instance.route_load(route), and return the original route "
            "structure as a no-op when a move would break capacity or coverage.\n\n"
            "CvrpInstance API: instance.capacity, instance.depot, "
            "instance.customer_ids, instance.customer_count, instance.node_ids, "
            "instance.demands, instance.demand(customer_id), instance.distance(i, j), "
            "instance.route_load(route), and instance.route_distance(route). Use "
            "instance.demands[customer_id] for direct demand lookup. Never use "
            "instance.customers; do not use nonexistent attributes such as "
            "vehicle_capacity, distance_matrix, or num_customers."
        )

    def preview_research_surface_patch(
        self,
        *,
        patch: Any,
        surface: Any | None = None,
    ) -> Mapping[str, Any]:
        """Problem-owned cheap policy sanity preview for tainted patch drafts.

        This uses a synthetic in-memory instance and does not read CVRP data,
        results, logs, metrics, or benchmark files.  It is advisory preview
        only; ContractGate and VerificationGate remain authoritative.
        """

        surface_name = str(getattr(surface, "name", "") or "")
        if not surface_name:
            surface_name = _surface_name_from_policy_path(str(getattr(patch, "file_path", "")))
        if surface_name not in {
            "construction_policy",
            "search_policy",
            "baseline_policy",
            "neighborhood_portfolio",
            "solver_algorithm",
            "solver_design",
            "main_search_strategy",
            "algorithm_blueprint",
            "alns_vns_policy",
            "destroy_repair_policy",
            "route_pair_candidate_policy",
            "acceptance_restart_policy",
        }:
            return {
                "passed": True,
                "surface": surface_name or None,
                "checks": [],
                "issues": [],
                "skipped": True,
                "workspace_materialized": False,
            }

        patch_path = str(getattr(patch, "file_path", ""))
        if str(getattr(patch, "action", "modify")) == "delete":
            if surface_name == "solver_design" and _is_solver_design_module_path(
                patch_path
            ):
                return _policy_preview_result(
                    surface_name,
                    [],
                    [
                        {
                            "name": "solver_design_module_delete",
                            "passed": True,
                            "detail": (
                                "module delete deferred to workspace algorithm smoke"
                            ),
                        }
                    ],
                )
            return _policy_preview_result(
                surface_name,
                [f"{surface_name} cannot be sanity-previewed for delete action"],
                [],
            )

        issues: list[str] = []
        checks: list[dict[str, Any]] = []
        if surface_name in {"solver_design", "solver_algorithm"}:
            _preview_solver_design_patch_api_boundary(patch, issues, checks)
        try:
            module = _module_from_policy_code(
                str(getattr(patch, "file_path", "<policy>")),
                str(getattr(patch, "code_content", "")),
            )
        except Exception as exc:
            return _policy_preview_result(
                surface_name,
                [f"policy module import failed: {exc}"],
                checks,
            )

        instance = _synthetic_preview_instance()
        if surface_name == "construction_policy":
            _preview_construction_policy(module, instance, issues, checks)
        elif surface_name == "search_policy":
            _preview_search_policy(module, instance, issues, checks)
        elif surface_name == "baseline_policy":
            _preview_baseline_policy(module, instance, issues, checks)
        elif surface_name == "neighborhood_portfolio":
            _preview_neighborhood_portfolio(module, instance, issues, checks)
        elif surface_name in {"solver_design", "solver_algorithm"}:
            if _is_solver_design_module_path(str(getattr(patch, "file_path", ""))):
                checks.append(
                    {
                        "name": "solver_design_module_import",
                        "passed": True,
                        "detail": (
                            "solver_design support module imported; solve "
                            "entrypoint validation deferred to workspace smoke"
                        ),
                    }
                )
            elif _is_baseline_algorithm_path(str(getattr(patch, "file_path", ""))):
                _preview_baseline_algorithm_boundary(
                    str(getattr(patch, "code_content", "")),
                    issues,
                    checks,
                )
                _preview_solver_algorithm(module, instance, issues, checks)
            else:
                _preview_solver_algorithm(module, instance, issues, checks)
        elif surface_name == "main_search_strategy":
            _preview_main_search_strategy(module, instance, issues, checks)
        elif surface_name == "algorithm_blueprint":
            _preview_algorithm_blueprint(module, instance, issues, checks)
        elif surface_name == "alns_vns_policy":
            _preview_alns_vns_policy(module, instance, issues, checks)
        elif surface_name == "destroy_repair_policy":
            _preview_destroy_repair_policy(module, instance, issues, checks)
        elif surface_name == "route_pair_candidate_policy":
            _preview_route_pair_candidate_policy(module, instance, issues, checks)
        elif surface_name == "acceptance_restart_policy":
            _preview_acceptance_restart_policy(module, instance, issues, checks)
        return _policy_preview_result(surface_name, issues, checks)

    def load_instance(self, instance_path: str) -> Any:
        suffix = Path(instance_path).suffix.lower()
        if suffix == ".json":
            return CvrpInstance.from_json(instance_path)
        if suffix == ".vrp":
            return load_cvrplib_instance(instance_path)
        raise ValueError(f"unsupported CVRP instance file extension: {suffix or '<none>'}")

    def deserialize_solver_output(
        self,
        raw_output: Mapping[str, Any],
        instance: Any,
    ) -> SolverArtifact:
        payload = raw_output.get("solution", raw_output)
        if not isinstance(payload, Mapping):
            raise ValueError("solver output must be a mapping")
        raw_routes = payload.get("routes")
        if not isinstance(raw_routes, list):
            raise ValueError("solver output missing routes list")

        routes = tuple(
            _normalize_route(route, instance.depot)
            for route in raw_routes
        )
        solution = CvrpSolution(routes=routes)
        raw_objective = raw_output.get("objective", payload.get("objective", {}))
        if not isinstance(raw_objective, Mapping):
            raw_objective = {}
        objective = _extract_reported_objective(raw_objective)
        feasible = bool(raw_output.get("feasible", payload.get("feasible", False)))
        return SolverArtifact(
            raw_output=dict(raw_output),
            objective=objective,
            feasible=feasible,
            normalized_solution=solution,
        )

    def check_solution_consistency(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        sol = _as_solution(artifact)
        reasons: list[str] = []
        valid_customers = set(instance.customer_ids)
        valid_nodes = set(instance.node_ids)
        seen: dict[int, int] = {}

        if not sol.routes:
            reasons.append("solution has no routes")

        for route_idx, route in enumerate(sol.routes):
            if not route:
                reasons.append(f"route {route_idx} is empty")
            for customer in route:
                if customer == instance.depot:
                    reasons.append(f"route {route_idx} contains depot inside customer route")
                    continue
                if customer not in valid_nodes:
                    reasons.append(f"route {route_idx} contains unknown customer {customer}")
                    continue
                if customer not in valid_customers:
                    reasons.append(f"route {route_idx} contains non-customer node {customer}")
                    continue
                if customer in seen:
                    reasons.append(
                        f"customer {customer} appears in multiple routes: "
                        f"{seen[customer]} and {route_idx}"
                    )
                seen[customer] = route_idx

        missing = sorted(valid_customers - set(seen))
        if missing:
            reasons.append(f"missing customers: {missing}")

        for key in ("fleet_violation", "total_distance"):
            value = artifact.objective.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                reasons.append(f"objective field {key} missing or non-finite")

        return CheckReport(passed=not reasons, reasons=tuple(reasons))

    def check_feasibility(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        consistency = self.check_solution_consistency(artifact, instance)
        reasons = list(consistency.reasons)
        if consistency.passed:
            sol = _as_solution(artifact)
            for route_idx, route in enumerate(sol.routes):
                load = instance.route_load(route)
                if load > instance.capacity:
                    reasons.append(
                        f"route {route_idx} load {load} exceeds capacity {instance.capacity}"
                    )
        return CheckReport(passed=not reasons, reasons=tuple(reasons))

    def recompute_objective(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> Mapping[str, int | float]:
        sol = _as_solution(artifact)
        total_distance = sum(instance.route_distance(route) for route in sol.routes)
        routes = len(sol.routes)
        allowed_routes = instance.allowed_routes
        if allowed_routes is None:
            allowed_routes = instance.bks_routes
        fleet_violation = max(0, routes - allowed_routes) if allowed_routes is not None else 0
        return {
            "fleet_violation": int(fleet_violation),
            "total_distance": float(total_distance),
            "routes": int(routes),
        }

    def estimate_lower_bound(
        self,
        metric_name: str,
        instance_paths: Sequence[str],
    ) -> LowerBoundEstimate | None:
        return None


def _normalize_route(route: Any, depot: int) -> tuple[int, ...]:
    if not isinstance(route, list):
        raise ValueError("each route must be a list")
    customers = [int(item) for item in route]
    if customers and customers[0] == depot:
        customers = customers[1:]
    if customers and customers[-1] == depot:
        customers = customers[:-1]
    return tuple(customers)


def _extract_reported_objective(raw_objective: Mapping[str, Any]) -> dict[str, int | float]:
    result: dict[str, int | float] = {}
    if "cost" in raw_objective and "total_distance" not in raw_objective:
        result["total_distance"] = float(raw_objective["cost"])
    for key in ("fleet_violation", "total_distance", "routes", "route_gap"):
        if key not in raw_objective:
            continue
        value = raw_objective[key]
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            result[key] = value
    return result


def _as_solution(artifact: SolverArtifact) -> CvrpSolution:
    sol = artifact.normalized_solution
    if not isinstance(sol, CvrpSolution):
        raise TypeError("artifact.normalized_solution is not CvrpSolution")
    return sol


def _surface_name_from_policy_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    return {
        "policies/construction_policy.py": "construction_policy",
        "policies/search_policy.py": "search_policy",
        "policies/baseline_policy.py": "baseline_policy",
        "policies/neighborhood_portfolio.py": "neighborhood_portfolio",
        "policies/baseline_algorithm.py": "solver_design",
        "policies/solver_algorithm.py": "solver_design",
        "policies/main_search_strategy.py": "main_search_strategy",
        "policies/algorithm_blueprint.py": "algorithm_blueprint",
        "policies/alns_vns_policy.py": "alns_vns_policy",
        "policies/destroy_repair_policy.py": "destroy_repair_policy",
        "policies/route_pair_candidate_policy.py": "route_pair_candidate_policy",
        "policies/acceptance_restart_policy.py": "acceptance_restart_policy",
    }.get(normalized, "solver_design" if _is_solver_design_module_path(normalized) else "")


def _is_baseline_algorithm_path(path: str) -> bool:
    return path.replace("\\", "/").lstrip("/") == "policies/baseline_algorithm.py"


def _is_solver_design_module_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("/")
    return (
        normalized.startswith("policies/baseline_modules/")
        and normalized.endswith(".py")
        and "/__pycache__/" not in normalized
    )


def _preview_baseline_algorithm_boundary(
    code: str,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    baseline_calls = _context_baseline_call_count(code)
    passed = baseline_calls == 0
    detail = (
        "preferred solver_design target does not call context.baseline"
        if passed
        else (
            "policies/baseline_algorithm.py is the Scion-controlled algorithm "
            "body and must not call context.baseline; modify the editable "
            "construction/search/destroy-repair/VNS logic directly"
        )
    )
    checks.append(
        {
            "name": "baseline_algorithm_no_context_baseline",
            "passed": passed,
            "detail": detail,
        }
    )
    if not passed:
        issues.append(detail)

    mixed = _remaining_time_ms_mixed_comparisons(code)
    time_units_passed = not mixed
    time_units_detail = (
        "remaining_time unit usage is consistent"
        if time_units_passed
        else (
            "context.remaining_time() returns seconds; use "
            "context.remaining_time_ms() when comparing to millisecond-derived "
            f"variables: {mixed[:5]}"
        )
    )
    checks.append(
        {
            "name": "baseline_algorithm_remaining_time_units",
            "passed": time_units_passed,
            "detail": time_units_detail,
        }
    )
    if not time_units_passed:
        issues.append(time_units_detail)


def _preview_solver_design_patch_api_boundary(
    patch: Any,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    for change in patch_file_changes(patch):
        path = str(getattr(change, "file_path", "") or "")
        normalized = path.replace("\\", "/").lstrip("/")
        if not (
            _is_baseline_algorithm_path(normalized)
            or _is_solver_design_module_path(normalized)
            or normalized == "policies/solver_algorithm.py"
        ):
            continue
        code = str(getattr(change, "code_content", "") or "")
        if _is_baseline_algorithm_path(normalized):
            _preview_baseline_algorithm_scheduler_api(
                normalized,
                code,
                issues,
                checks,
            )
        _preview_solver_design_context_api(normalized, code, issues, checks)


def _preview_baseline_algorithm_scheduler_api(
    path: str,
    code: str,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    bad_names = _baseline_algorithm_scheduler_entrypoint_imports(code)
    passed = not bad_names
    detail = (
        "baseline_algorithm uses the stable scheduler class entrypoint"
        if passed
        else (
            f"{path} must keep scheduler integration through "
            "`_ALNSVNSSolver(...).solve(instance, rng)`; do not import "
            f"scheduler entrypoint names {bad_names}"
        )
    )
    checks.append(
        {
            "name": "baseline_algorithm_scheduler_entrypoint_api",
            "passed": passed,
            "detail": detail,
        }
    )
    if not passed:
        issues.append(detail)


def _baseline_algorithm_scheduler_entrypoint_imports(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = str(node.module or "")
        if not module.endswith("baseline_modules.scheduler"):
            continue
        for alias in node.names:
            name = str(alias.name or "")
            if name in {"solve", "run", "main", "_run", "_run_scheduler"}:
                bad.append(name)
    return sorted(set(bad))


def _preview_solver_design_context_api(
    path: str,
    code: str,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    bad_lines = _context_nearest_neighbor_argument_calls(code)
    passed = not bad_lines
    detail = (
        "solver_design context.nearest_neighbor() calls use the no-argument API"
        if passed
        else (
            f"{path} calls context.nearest_neighbor with arguments at lines "
            f"{bad_lines}; the API takes no arguments and returns CvrpSolution"
        )
    )
    checks.append(
        {
            "name": "solver_design_context_nearest_neighbor_no_args",
            "passed": passed,
            "detail": detail,
        }
    )
    if not passed:
        issues.append(detail)


def _context_nearest_neighbor_argument_calls(code: str) -> list[int]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "nearest_neighbor"
            and isinstance(func.value, ast.Name)
            and func.value.id == "context"
        ):
            continue
        if node.args or node.keywords:
            lines.append(int(getattr(node, "lineno", 0) or 0))
    return lines


def _context_baseline_call_count(code: str) -> int:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "baseline"
            and isinstance(func.value, ast.Name)
            and func.value.id == "context"
        ):
            count += 1
    return count


def _remaining_time_ms_mixed_comparisons(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    assignments: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                assignments[target.id] = node.value

    ms_names = {name for name in assignments if name.endswith("_ms")}
    changed = True
    while changed:
        changed = False
        for name, expr in assignments.items():
            if name in ms_names:
                continue
            if _expr_is_millisecond_derived(expr, ms_names):
                ms_names.add(name)
                changed = True

    mixed: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        parts = [node.left, *node.comparators]
        for left, right in zip(parts, parts[1:]):
            if _is_context_remaining_time_call(left) and _expr_references_ms_name(
                right, ms_names
            ):
                mixed.append(_format_compare_issue(right, ms_names))
            elif _is_context_remaining_time_call(right) and _expr_references_ms_name(
                left, ms_names
            ):
                mixed.append(_format_compare_issue(left, ms_names))
    return mixed


def _expr_is_millisecond_derived(expr: ast.AST, ms_names: set[str]) -> bool:
    if _expr_references_ms_name(expr, ms_names):
        return True
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Mult):
        return _is_1000_literal(expr.left) or _is_1000_literal(expr.right)
    return False


def _expr_references_ms_name(expr: ast.AST, ms_names: set[str]) -> bool:
    return any(
        isinstance(node, ast.Name) and node.id in ms_names
        for node in ast.walk(expr)
    )


def _is_1000_literal(expr: ast.AST) -> bool:
    return (
        isinstance(expr, ast.Constant)
        and isinstance(expr.value, (int, float))
        and expr.value == 1000
    )


def _is_context_remaining_time_call(expr: ast.AST) -> bool:
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Attribute)
        and expr.func.attr == "remaining_time"
        and isinstance(expr.func.value, ast.Name)
        and expr.func.value.id == "context"
    )


def _format_compare_issue(expr: ast.AST, ms_names: set[str]) -> str:
    names = sorted(
        {
            node.id
            for node in ast.walk(expr)
            if isinstance(node, ast.Name) and node.id in ms_names
        }
    )
    return ", ".join(names) if names else "millisecond expression"


def _module_from_policy_code(file_path: str, code: str) -> types.ModuleType:
    module = types.ModuleType(f"_scion_cvrp_policy_preview_{abs(hash(file_path))}")
    module.__dict__["__file__"] = f"<preview:{file_path}>"
    module.__dict__["__name__"] = module.__name__
    package = _preview_package_for_policy_path(file_path)
    if package:
        module.__dict__["__package__"] = package
    exec(compile(code, file_path, "exec"), module.__dict__)
    return module


def _preview_package_for_policy_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/").lstrip("/")
    if normalized == "policies/baseline_algorithm.py":
        return "scion.problems.cvrp.policies"
    if normalized.startswith("policies/baseline_modules/"):
        return "scion.problems.cvrp.policies.baseline_modules"
    return ""


def _synthetic_preview_instance() -> CvrpInstance:
    return CvrpInstance(
        name="synthetic_preview",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0.0, y=0.0, demand=0),
            CvrpNode(id=1, x=1.0, y=0.0, demand=3),
            CvrpNode(id=2, x=0.0, y=2.0, demand=4),
            CvrpNode(id=3, x=2.0, y=2.0, demand=2),
        ),
        allowed_routes=2,
        use_integer_cost=True,
    )


def _solver_algorithm_preview_instances(instance: CvrpInstance) -> tuple[CvrpInstance, ...]:
    return (
        instance,
        CvrpInstance(
            name="synthetic_preview_canary_5",
            capacity=8,
            depot=0,
            nodes=(
                CvrpNode(id=0, x=0.0, y=0.0, demand=0),
                CvrpNode(id=1, x=2.0, y=0.0, demand=2),
                CvrpNode(id=2, x=4.0, y=0.0, demand=2),
                CvrpNode(id=3, x=0.0, y=3.0, demand=3),
                CvrpNode(id=4, x=0.0, y=6.0, demand=3),
            ),
            bks=20.0,
            bks_routes=2,
            use_integer_cost=True,
        ),
        CvrpInstance(
            name="synthetic_preview_improvement_trap",
            capacity=99,
            depot=0,
            nodes=(
                CvrpNode(id=0, x=0.0, y=0.0, demand=0),
                CvrpNode(id=1, x=-4.0, y=5.0, demand=1),
                CvrpNode(id=2, x=7.0, y=7.0, demand=1),
                CvrpNode(id=3, x=5.0, y=2.0, demand=1),
                CvrpNode(id=4, x=10.0, y=-6.0, demand=1),
            ),
            allowed_routes=1,
            bks=43.0,
            bks_routes=1,
            use_integer_cost=True,
        ),
    )


def _policy_preview_result(
    surface: str,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "passed": not issues,
        "surface": surface,
        "checks": checks,
        "issues": issues,
        "synthetic_instance": {
            "name": "synthetic_preview",
            "customer_ids": [1, 2, 3],
            "customer_count": 3,
            "capacity": 10,
        },
        "workspace_materialized": False,
        "verification_run": False,
    }


def _preview_construction_policy(
    module: types.ModuleType,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    mode = _call_preview_function(module, "construction_mode", instance, issues, checks)
    if mode is not _PREVIEW_FAILED:
        if not isinstance(mode, str):
            issues.append(f"construction_mode returned non-string value {mode!r}")
        elif mode.strip() not in _ALLOWED_CONSTRUCTION_MODES:
            issues.append(f"construction_mode returned unknown mode {mode!r}")
    bias = _call_preview_function(module, "construction_bias", instance, issues, checks)
    if bias is not _PREVIEW_FAILED:
        _check_number(
            "construction_bias",
            bias,
            minimum=0.0,
            maximum=1.0,
            integral=False,
            issues=issues,
        )


def _preview_search_policy(
    module: types.ModuleType,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    baseline = _call_preview_function(module, "baseline_time_fraction", instance, issues, checks)
    if baseline is not _PREVIEW_FAILED:
        _check_number(
            "baseline_time_fraction",
            baseline,
            minimum=0.2,
            maximum=0.95,
            integral=False,
            issues=issues,
        )
    rounds = _call_preview_function(module, "max_operator_rounds", instance, issues, checks)
    if rounds is not _PREVIEW_FAILED:
        _check_number(
            "max_operator_rounds",
            rounds,
            minimum=0,
            maximum=20,
            integral=True,
            issues=issues,
        )
    enabled = _call_preview_function(
        module,
        "enable_post_baseline_operators",
        instance,
        issues,
        checks,
    )
    if enabled is not _PREVIEW_FAILED and not isinstance(enabled, bool):
        issues.append(
            f"enable_post_baseline_operators returned non-bool value {enabled!r}"
        )


def _preview_baseline_policy(
    module: types.ModuleType,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    params = _call_preview_function(module, "baseline_params", instance, issues, checks)
    if params is _PREVIEW_FAILED:
        return
    if not isinstance(params, Mapping):
        issues.append(f"baseline_params returned non-mapping value {params!r}")
        return

    unknown = sorted(str(key) for key in params if str(key) not in _BASELINE_POLICY_ALLOWED_KEYS)
    if unknown:
        issues.append(f"baseline_params returned unknown keys {unknown}")

    if "destroy_ratio" in params:
        _check_destroy_ratio(params["destroy_ratio"], issues)
    if "segment_length" in params:
        _check_number(
            "segment_length",
            params["segment_length"],
            minimum=1,
            maximum=1000,
            integral=True,
            issues=issues,
        )
    if "reaction_factor" in params:
        _check_number(
            "reaction_factor",
            params["reaction_factor"],
            minimum=0.01,
            maximum=1.0,
            integral=False,
            issues=issues,
        )
    if "vns_max_no_improve" in params:
        _check_number(
            "vns_max_no_improve",
            params["vns_max_no_improve"],
            minimum=0,
            maximum=20000,
            integral=True,
            issues=issues,
        )
    if "use_vns" in params and not isinstance(params["use_vns"], bool):
        issues.append(f"use_vns returned non-bool value {params['use_vns']!r}")
    for name in ("cw_threshold", "vns_threshold", "alns_threshold"):
        if name in params:
            _check_number(
                name,
                params[name],
                minimum=0,
                maximum=10000,
                integral=True,
                issues=issues,
            )
    if "max_destroy_customers" in params:
        _check_number(
            "max_destroy_customers",
            params["max_destroy_customers"],
            minimum=1,
            maximum=500,
            integral=True,
            issues=issues,
        )


def _preview_neighborhood_portfolio(
    module: types.ModuleType,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    components = _call_preview_function(module, "enabled_components", instance, issues, checks)
    if components is not _PREVIEW_FAILED:
        if isinstance(components, str) or not isinstance(components, (list, tuple, set, frozenset)):
            issues.append(f"enabled_components returned non-sequence value {components!r}")
        else:
            normalized = [str(item).strip() for item in components]
            bad = [item for item in normalized if item not in _ALLOWED_PORTFOLIO_COMPONENTS]
            if bad:
                issues.append(f"enabled_components returned unknown components {bad}")
            if not normalized:
                issues.append("enabled_components returned an empty sequence")

    weights = _call_preview_function(module, "component_weights", instance, issues, checks)
    if weights is not _PREVIEW_FAILED:
        if not isinstance(weights, Mapping):
            issues.append(f"component_weights returned non-mapping value {weights!r}")
        else:
            for key, value in weights.items():
                component = str(key).strip()
                if component not in _ALLOWED_PORTFOLIO_COMPONENTS:
                    issues.append(
                        f"component_weights returned unknown component {component!r}"
                    )
                    continue
                _check_number(
                    f"component_weights[{component}]",
                    value,
                    minimum=0.0,
                    maximum=5.0,
                    integral=False,
                    issues=issues,
                )

    limits = _call_preview_function(module, "candidate_limits", instance, issues, checks)
    if limits is not _PREVIEW_FAILED:
        if not isinstance(limits, Mapping):
            issues.append(f"candidate_limits returned non-mapping value {limits!r}")
        else:
            for key, value in limits.items():
                limit_name = str(key).strip()
                if limit_name not in _PORTFOLIO_LIMIT_RANGES:
                    issues.append(f"candidate_limits returned unknown key {limit_name!r}")
                    continue
                lo, hi = _PORTFOLIO_LIMIT_RANGES[limit_name]
                _check_number(
                    f"candidate_limits[{limit_name}]",
                    value,
                    minimum=lo,
                    maximum=hi,
                    integral=True,
                    issues=issues,
                )


def _preview_solver_algorithm(
    module: types.ModuleType,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    func = getattr(module, "solve", None)
    if not callable(func):
        issues.append("missing callable solve")
        checks.append({"name": "solve", "passed": False, "detail": "missing callable"})
        return
    for preview_instance in _solver_algorithm_preview_instances(instance):
        _preview_solver_algorithm_case(func, preview_instance, issues, checks)


def _preview_solver_algorithm_case(
    func: Any,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    rng = random.Random(0)
    context = _PreviewSolverAlgorithmContext(instance, rng)
    check_name = (
        "solve" if instance.name == "synthetic_preview" else f"solve:{instance.name}"
    )
    try:
        raw_solution = _call_solver_algorithm_preview(
            func,
            instance=instance,
            rng=rng,
            context=context,
        )
    except _PolicyPreviewTimeout:
        detail = (
            f"{instance.name}: solve timed out during synthetic preview; "
            "solver_design candidates "
            "must use explicit bounded loops and poll context.remaining_time()"
        )
        issues.append(detail)
        checks.append({"name": check_name, "passed": False, "detail": detail})
        return
    except Exception as exc:
        detail = f"{instance.name}: solve raised during synthetic preview: {exc}"
        issues.append(detail)
        checks.append({"name": check_name, "passed": False, "detail": detail})
        return
    if raw_solution is None:
        detail = f"{instance.name}: solve returned None; solver_algorithm would be inactive"
        issues.append(detail)
        checks.append({"name": check_name, "passed": False, "detail": detail})
        return
    solution = _coerce_preview_solution(raw_solution)
    if solution is None:
        detail = f"{instance.name}: solve returned non-solution value"
        issues.append(detail)
        checks.append(
            {
                "name": check_name,
                "passed": False,
                "detail": f"{detail}: returned {type(raw_solution).__name__}",
            }
        )
        return
    valid, reason = _preview_solution_is_valid(instance, solution)
    solution_distance = sum(instance.route_distance(route) for route in solution.routes)
    preview_baseline = context.nearest_neighbor()
    preview_baseline_distance = sum(
        instance.route_distance(route) for route in preview_baseline.routes
    )
    delta_vs_preview_baseline = preview_baseline_distance - solution_distance
    body_has_search = (
        context.move_attempts > 0
        or context.accepted_moves > 0
        or context.search_iterations > 0
    )
    if valid and context.baseline_calls > 0 and not body_has_search:
        valid = False
        reason = (
            "shallow baseline wrapper: solver_design candidates that call "
            "context.baseline must also run their own bounded candidate "
            "generation, route-edit/search loop, or acceptance decision and "
            "record it with context.record_move or context.record_iteration"
        )
    elif (
        valid
        and context.baseline_calls > 0
        and instance.name == "synthetic_preview_improvement_trap"
        and solution_distance >= preview_baseline_distance
    ):
        valid = False
        reason = (
            "solver_design micro-eval no-op: the preview baseline is "
            f"intentionally improvable on {instance.name} "
            f"(baseline_distance={preview_baseline_distance}, "
            f"returned_distance={solution_distance}), but solve returned no "
            "strict improvement. Baseline-seeded candidates must use the "
            "approved problem object to produce measurable phase-best movement, "
            "not only wrap context.baseline or add fixed overhead."
        )
    checks.append(
        {
            "name": check_name,
            "passed": valid,
            "detail": (
                f"{instance.name}: routes={len(solution.routes)} "
                f"distance={solution_distance} "
                f"preview_baseline_distance={preview_baseline_distance} "
                f"delta_vs_preview_baseline={delta_vs_preview_baseline} "
                f"baseline_calls={context.baseline_calls} "
                f"search_iterations={context.search_iterations} "
                f"move_attempts={context.move_attempts} "
                f"accepted_moves={context.accepted_moves}"
                if valid
                else f"{instance.name}: {reason}"
            ),
        }
    )
    if not valid:
        issues.append(
            f"{instance.name}: solve returned invalid synthetic solution: {reason}"
        )


class _PolicyPreviewTimeout(BaseException):
    pass


def _call_solver_algorithm_preview(
    func: Any,
    *,
    instance: CvrpInstance,
    rng: random.Random,
    context: "_PreviewSolverAlgorithmContext",
) -> Any:
    if (
        threading.current_thread() is not threading.main_thread()
        or not hasattr(signal, "SIGALRM")
        or not hasattr(signal, "setitimer")
    ):
        return func(instance, rng, _POLICY_PREVIEW_TIME_LIMIT_SEC, context)

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def _raise_timeout(_signum: int, _frame: Any) -> None:
        raise _PolicyPreviewTimeout()

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, _POLICY_PREVIEW_EXEC_TIMEOUT_SEC)
    try:
        return func(instance, rng, _POLICY_PREVIEW_TIME_LIMIT_SEC, context)
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


class _PreviewSolverAlgorithmContext:
    def __init__(self, instance: CvrpInstance, rng: random.Random) -> None:
        self.instance = instance
        self.rng = rng
        self.time_limit_sec = _POLICY_PREVIEW_TIME_LIMIT_SEC
        self._phase_runtime_ms: dict[str, int] = {}
        self._remaining_time_calls = 0
        self._baseline_calls = 0
        self._search_iterations = 0
        self._move_attempts = 0
        self._accepted_moves = 0
        self._stop_reason = ""

    @property
    def baseline_calls(self) -> int:
        return self._baseline_calls

    @property
    def search_iterations(self) -> int:
        return self._search_iterations

    @property
    def move_attempts(self) -> int:
        return self._move_attempts

    @property
    def accepted_moves(self) -> int:
        return self._accepted_moves

    def remaining_time(self) -> float:
        self._remaining_time_calls += 1
        return max(0.0, self.time_limit_sec - (0.05 * self._remaining_time_calls))

    def remaining_time_ms(self) -> int:
        return int(self.remaining_time() * 1000)

    def elapsed_ms(self) -> int:
        return 0

    def make_solution(self, routes: Any) -> CvrpSolution:
        existing = _coerce_preview_solution(routes)
        if existing is not None:
            return existing
        return _coerce_preview_solution({"routes": routes}) or CvrpSolution(routes=())

    def is_valid(self, solution: Any) -> bool:
        coerced = _coerce_preview_solution(solution)
        if coerced is None:
            return False
        valid, _reason = _preview_solution_is_valid(self.instance, coerced)
        return valid

    def objective(self, solution: Any) -> "_PreviewObjectiveValue":
        coerced = _coerce_preview_solution(solution)
        if coerced is None:
            raise ValueError("solution cannot be coerced to CvrpSolution")
        valid, reason = _preview_solution_is_valid(self.instance, coerced)
        if not valid:
            raise ValueError(reason)
        return _PreviewObjectiveValue(
            {
                "fleet_violation": 0.0,
                "total_distance": sum(
                    self.instance.route_distance(route) for route in coerced.routes
                ),
            }
        )

    def objective_key(self, solution: Any) -> tuple[float, float]:
        objective = self.objective(solution)
        return (float(objective[0]), float(objective[1]))

    def is_better(self, candidate: Any, incumbent: Any) -> bool:
        return self.objective_key(candidate) < self.objective_key(incumbent)

    def nearest_neighbor(
        self,
        *,
        construction_mode: str = "nearest_neighbor",
        construction_bias: float = 0.0,
    ) -> CvrpSolution:
        del construction_mode, construction_bias
        unvisited = set(self.instance.customer_ids)
        routes: list[tuple[int, ...]] = []
        while unvisited:
            route: list[int] = []
            load = 0
            current = self.instance.depot
            while True:
                feasible = [
                    customer
                    for customer in unvisited
                    if load + self.instance.demand(customer) <= self.instance.capacity
                ]
                if not feasible:
                    break
                nxt = min(
                    feasible,
                    key=lambda customer: self.instance.distance(current, customer),
                )
                unvisited.remove(nxt)
                route.append(nxt)
                load += self.instance.demand(nxt)
                current = nxt
            if not route:
                raise ValueError("remaining customer demand exceeds capacity")
            routes.append(tuple(route))
        return CvrpSolution(routes=tuple(routes))

    def baseline(
        self,
        initial_solution: Any | None = None,
        *,
        time_budget_sec: float | None = None,
        time_limit_sec: float | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> CvrpSolution:
        self._baseline_calls += 1
        del time_budget_sec, time_limit_sec, params
        if (
            isinstance(initial_solution, (int, float))
            and not isinstance(initial_solution, bool)
        ):
            initial_solution = None
        seed_solution = _coerce_preview_solution(initial_solution)
        if seed_solution is not None and self.is_valid(seed_solution):
            return seed_solution
        return self.nearest_neighbor()

    def record_phase(self, name: str, elapsed_ms: int | float) -> None:
        phase = str(name or "").strip() or "unnamed"
        self._phase_runtime_ms[phase] = self._phase_runtime_ms.get(phase, 0) + int(
            max(0, elapsed_ms)
        )

    def record_iteration(self, phase: str = "search", count: int = 1) -> None:
        del phase
        try:
            increment = int(count)
        except (TypeError, ValueError):
            increment = 1
        self._search_iterations += max(1, increment)

    def record_move(
        self,
        phase: str,
        *,
        attempted: int = 1,
        accepted: int = 0,
        delta: int | float = 0.0,
        best_improved: bool = False,
    ) -> None:
        del phase, delta, best_improved
        try:
            attempts = int(attempted)
        except (TypeError, ValueError):
            attempts = 1
        try:
            accepts = int(accepted)
        except (TypeError, ValueError):
            accepts = 0
        self._move_attempts += max(1, attempts)
        self._accepted_moves += max(0, accepts)

    def set_stop_reason(self, reason: str) -> None:
        self._stop_reason = str(reason or "").strip()


class _PreviewObjectiveValue(dict):
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


def _coerce_preview_solution(candidate: Any) -> CvrpSolution | None:
    if isinstance(candidate, CvrpSolution):
        return candidate
    routes = candidate.get("routes") if isinstance(candidate, Mapping) else getattr(
        candidate,
        "routes",
        None,
    )
    if routes is None:
        return None
    try:
        return CvrpSolution(
            routes=tuple(tuple(int(customer) for customer in route) for route in routes)
        )
    except (TypeError, ValueError):
        return None


def _preview_solution_is_valid(
    instance: CvrpInstance,
    solution: CvrpSolution,
) -> tuple[bool, str]:
    seen: list[int] = []
    allowed = set(instance.customer_ids)
    for route in solution.routes:
        if not route:
            return False, "empty route"
        if instance.route_load(route) > instance.capacity:
            return False, "route exceeds capacity"
        for customer in route:
            if customer not in allowed:
                return False, f"unknown customer {customer}"
            seen.append(customer)
    if sorted(seen) != sorted(allowed):
        return False, "routes must cover each customer exactly once"
    if instance.allowed_routes is not None and len(solution.routes) > instance.allowed_routes:
        return False, "route count exceeds allowed_routes"
    return True, ""


def _preview_main_search_strategy(
    module: types.ModuleType,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    plan = _call_preview_function(module, "main_search_plan", instance, issues, checks)
    if plan is _PREVIEW_FAILED:
        return
    if not isinstance(plan, Mapping):
        issues.append(f"main_search_plan returned non-mapping value {plan!r}")
        return

    unknown = sorted(str(key) for key in plan if str(key) not in _MAIN_SEARCH_STRATEGY_ALLOWED_KEYS)
    if unknown:
        issues.append(f"main_search_plan returned unknown keys {unknown}")
    enabled = plan.get("enabled", False)
    if not isinstance(enabled, bool):
        issues.append(f"main_search_plan enabled returned non-bool value {enabled!r}")
        enabled = False
    if enabled:
        missing = sorted(key for key in _MAIN_SEARCH_STRATEGY_REQUIRED_KEYS if key not in plan)
        if missing:
            issues.append(f"enabled main_search_plan missing required keys {missing}")

    problem_adaptation = _preview_mapping_section(
        "problem_adaptation",
        plan.get("problem_adaptation", {}),
        issues,
    )
    if problem_adaptation is not None:
        _preview_section_keys(
            "problem_adaptation",
            problem_adaptation,
            allowed=_MAIN_SEARCH_PROBLEM_ADAPTATION_ALLOWED_KEYS,
            required=_MAIN_SEARCH_PROBLEM_ADAPTATION_REQUIRED_KEYS,
            require_missing=bool(enabled and "problem_adaptation" in plan),
            issues=issues,
        )
        strategy_family = str(
            problem_adaptation.get("strategy_family", "balanced_lifecycle")
        ).strip()
        if strategy_family not in _ALLOWED_MAIN_SEARCH_STRATEGY_FAMILIES:
            issues.append(
                "problem_adaptation.strategy_family returned unknown value "
                f"{strategy_family!r}"
            )
        phase_objective = str(
            problem_adaptation.get("phase_objective", "phase_best_distance")
        ).strip()
        if phase_objective not in _ALLOWED_MAIN_SEARCH_PHASE_OBJECTIVES:
            issues.append(
                "problem_adaptation.phase_objective returned unknown value "
                f"{phase_objective!r}"
            )
        instance_profile = problem_adaptation.get("instance_profile", {})
        if not isinstance(instance_profile, Mapping):
            issues.append(
                "problem_adaptation.instance_profile returned non-mapping value "
                f"{instance_profile!r}"
            )
        else:
            unknown_profile = sorted(
                str(key)
                for key in instance_profile
                if str(key) not in _MAIN_SEARCH_ADAPTATION_PROFILE_KEYS
            )
            if unknown_profile:
                issues.append(
                    "problem_adaptation.instance_profile returned unknown keys "
                    f"{unknown_profile}"
                )
        component_roles = problem_adaptation.get("component_roles", {})
        if not isinstance(component_roles, Mapping):
            issues.append(
                "problem_adaptation.component_roles returned non-mapping value "
                f"{component_roles!r}"
            )
        else:
            for component, role in component_roles.items():
                if str(component) not in _ALLOWED_MAIN_SEARCH_ROLE_TARGETS:
                    issues.append(
                        "problem_adaptation.component_roles returned unknown "
                        f"role target {component!r}"
                    )
                if str(role) not in _ALLOWED_MAIN_SEARCH_COMPONENT_ROLES:
                    issues.append(
                        "problem_adaptation.component_roles returned unknown "
                        f"role {role!r}"
                    )
        _check_sequence_literals(
            "problem_adaptation.fallback_order",
            problem_adaptation.get("fallback_order", []),
            allowed=_ALLOWED_MAIN_SEARCH_COMPONENTS,
            allow_empty=True,
            issues=issues,
        )
        _check_sequence_literals(
            "problem_adaptation.evidence_targets",
            problem_adaptation.get(
                "evidence_targets",
                ["main_search_component_phase_delta_sum"],
            ),
            allowed=_ALLOWED_MAIN_SEARCH_EVIDENCE_TARGETS,
            allow_empty=False,
            issues=issues,
        )
    if enabled and "problem_adaptation" not in plan:
        checks.append(
            {
                "name": "main_search_problem_adaptation_declared",
                "passed": False,
                "severity": "diagnostic_warning",
                "guidance": (
                    "solver_design proposals should declare problem_adaptation "
                    "so the whole CVRP problem object, strategy family, "
                    "instance profile, component roles, fallback order, and "
                    "evidence targets are explicit."
                ),
            }
        )
    algorithm_body = (
        _preview_mapping_section(
            "algorithm_body",
            plan.get("algorithm_body", {}),
            issues,
        )
        if "algorithm_body" in plan
        else None
    )
    if algorithm_body is not None:
        _preview_section_keys(
            "algorithm_body",
            algorithm_body,
            allowed=_MAIN_SEARCH_ALGORITHM_BODY_ALLOWED_KEYS,
            required=frozenset(),
            require_missing=False,
            issues=issues,
        )
        _check_sequence_literals(
            "algorithm_body.phase_sequence",
            algorithm_body.get("phase_sequence", []),
            allowed=_ALLOWED_MAIN_SEARCH_ALGORITHM_PHASES,
            allow_empty=False,
            issues=issues,
        )
        baseline_budget_policy = str(
            algorithm_body.get("baseline_budget_policy", "declared")
        ).strip()
        if (
            baseline_budget_policy
            and baseline_budget_policy
            not in _ALLOWED_MAIN_SEARCH_BASELINE_BUDGET_POLICIES
        ):
            issues.append(
                "algorithm_body.baseline_budget_policy returned unknown value "
                f"{baseline_budget_policy!r}"
            )
        route_pool_activation = str(
            algorithm_body.get("route_pool_activation", "adaptive")
        ).strip()
        if route_pool_activation and route_pool_activation not in _ALLOWED_ROUTE_POOL_ACTIVATIONS:
            issues.append(
                "algorithm_body.route_pool_activation returned unknown value "
                f"{route_pool_activation!r}"
            )
        _check_number(
            "algorithm_body.route_pool_min_customers",
            algorithm_body.get("route_pool_min_customers", 80),
            minimum=0,
            maximum=500,
            integral=True,
            issues=issues,
        )
        _check_number(
            "algorithm_body.route_pool_max_rounds",
            algorithm_body.get("route_pool_max_rounds", 8),
            minimum=0,
            maximum=8,
            integral=True,
            issues=issues,
        )
        for bool_key in (
            "local_cleanup_after_recombination",
            "adaptive_component_budget",
        ):
            if bool_key in algorithm_body and not isinstance(
                algorithm_body.get(bool_key),
                bool,
            ):
                issues.append(
                    f"algorithm_body.{bool_key} returned non-bool value "
                    f"{algorithm_body.get(bool_key)!r}"
                )
    if enabled and "algorithm_body" not in plan:
        issues.append(
            "enabled main_search_plan missing required algorithm_body section"
        )
        checks.append(
            {
                "name": "main_search_algorithm_body_declared",
                "passed": False,
                "severity": "contract_error",
                "guidance": (
                    "solver_design proposals should declare algorithm_body so "
                    "the full CVRP lifecycle is explicit: phase sequence, "
                    "route-pool activation scope, route-pool invocation limit, "
                    "cleanup coupling, and adaptive component budget policy."
                ),
            }
        )

    construction = _preview_mapping_section("construction", plan.get("construction", {}), issues)
    if construction is not None:
        _preview_section_keys(
            "construction",
            construction,
            allowed=_MAIN_SEARCH_CONSTRUCTION_REQUIRED_KEYS,
            required=_MAIN_SEARCH_CONSTRUCTION_REQUIRED_KEYS,
            require_missing=enabled,
            issues=issues,
        )
        _check_sequence_literals(
            "construction.methods",
            construction.get("methods", ["nearest_neighbor"]),
            allowed=_ALLOWED_CONSTRUCTION_MODES,
            allow_empty=False,
            issues=issues,
        )
        _check_number(
            "construction.keep_top_k",
            construction.get("keep_top_k", 1),
            minimum=1,
            maximum=4,
            integral=True,
            issues=issues,
        )
        _check_number(
            "construction.bias",
            construction.get("bias", 0.0),
            minimum=0.0,
            maximum=1.0,
            integral=False,
            issues=issues,
        )

    baseline = _preview_mapping_section("baseline", plan.get("baseline", {}), issues)
    if baseline is not None:
        _preview_section_keys(
            "baseline",
            baseline,
            allowed=_MAIN_SEARCH_BASELINE_REQUIRED_KEYS,
            required=_MAIN_SEARCH_BASELINE_REQUIRED_KEYS,
            require_missing=enabled,
            issues=issues,
        )
        _check_number(
            "baseline.time_fraction",
            baseline.get("time_fraction", 0.8),
            minimum=0.2,
            maximum=0.95,
            integral=False,
            issues=issues,
        )
        params = baseline.get("params", {})
        if not isinstance(params, Mapping):
            issues.append(f"baseline.params returned non-mapping value {params!r}")
        else:
            _preview_baseline_params_mapping(params, issues)

    improvement = _preview_mapping_section("improvement", plan.get("improvement", {}), issues)
    if improvement is not None:
        _preview_section_keys(
            "improvement",
            improvement,
            allowed=_MAIN_SEARCH_IMPROVEMENT_REQUIRED_KEYS,
            required=_MAIN_SEARCH_IMPROVEMENT_REQUIRED_KEYS,
            require_missing=enabled,
            issues=issues,
        )
        components = improvement.get("enabled_components", [])
        _check_sequence_literals(
            "improvement.enabled_components",
            components,
            allowed=_ALLOWED_MAIN_SEARCH_COMPONENTS,
            allow_empty=not enabled,
            issues=issues,
        )
        _check_number(
            "improvement.rounds",
            improvement.get("rounds", 0),
            minimum=1 if enabled else 0,
            maximum=8,
            integral=True,
            issues=issues,
        )
        _check_number(
            "improvement.top_k",
            improvement.get("top_k", 16),
            minimum=1 if enabled else 0,
            maximum=128,
            integral=True,
            issues=issues,
        )
        if (
            enabled
            and isinstance(components, Sequence)
            and not isinstance(components, (str, bytes))
        ):
            selected = {str(component) for component in components}
            component_roles = (
                problem_adaptation.get("component_roles", {})
                if isinstance(problem_adaptation, Mapping)
                else {}
            )
            if isinstance(component_roles, Mapping):
                disabled_selected = sorted(
                    str(component)
                    for component in selected
                    if str(component_roles.get(component, "")) == "disabled"
                )
                if disabled_selected:
                    issues.append(
                        "problem_adaptation.component_roles marks selected "
                        f"components disabled: {disabled_selected}"
                    )
            missing_deep = sorted(
                _MAIN_SEARCH_DEEP_ATTRIBUTION_COMPONENTS - selected
            )
            checks.append(
                {
                    "name": "main_search_problem_object_evidence_alignment",
                    "passed": bool(selected & _MAIN_SEARCH_DEEP_ATTRIBUTION_COMPONENTS),
                    "severity": "diagnostic_warning",
                    "required_components": sorted(
                        _MAIN_SEARCH_DEEP_ATTRIBUTION_COMPONENTS
                    ),
                    "selected_components": sorted(selected),
                    "missing_components": missing_deep,
                    "guidance": (
                        "Main-search plans should be evaluated as solver-level "
                        "CVRP designs. Explain how selected components, baseline "
                        "budget, restart/perturbation, and caps work together; "
                        "predict phase-best objective movement and whole-solver "
                        "runtime fields. The preview reports which package-owned "
                        "problem-object components are selected because missing "
                        "components "
                        "are diagnostic only and do not make an otherwise valid "
                        "problem-level plan fail. Current screening evidence has "
                        "already falsified route_pair_swap + "
                        "bounded_destroy_repair-only plans as a path to "
                        "phase-best movement; use route_pool_recombination when "
                        "testing whole-solution CVRP adaptation."
                    ),
                }
            )

    acceptance = _preview_mapping_section("acceptance", plan.get("acceptance", {}), issues)
    if acceptance is not None:
        _preview_section_keys(
            "acceptance",
            acceptance,
            allowed=_MAIN_SEARCH_ACCEPTANCE_ALLOWED_KEYS,
            required=_MAIN_SEARCH_ACCEPTANCE_REQUIRED_KEYS,
            require_missing=enabled,
            issues=issues,
        )
        _check_number(
            "acceptance.min_distance_improvement",
            acceptance.get("min_distance_improvement", 0.0),
            minimum=0.0,
            maximum=10.0,
            integral=False,
            issues=issues,
        )
        component_thresholds = acceptance.get("component_min_distance_improvement", {})
        if not isinstance(component_thresholds, Mapping):
            issues.append(
                "acceptance.component_min_distance_improvement returned "
                f"non-mapping value {component_thresholds!r}"
            )
        else:
            for component, threshold in component_thresholds.items():
                if str(component) not in _ALLOWED_MAIN_SEARCH_COMPONENTS:
                    issues.append(
                        "acceptance.component_min_distance_improvement returned "
                        f"unknown component {component!r}"
                    )
                _check_number(
                    f"acceptance.component_min_distance_improvement.{component}",
                    threshold,
                    minimum=0.0,
                    maximum=10.0,
                    integral=False,
                    issues=issues,
                )
        _check_number(
            "acceptance.bounded_destroy_repair_accept_limit",
            acceptance.get("bounded_destroy_repair_accept_limit", 1),
            minimum=0,
            maximum=3,
            integral=True,
            issues=issues,
        )
        recovery_policy = str(acceptance.get("recovery_only_policy", "allow")).strip()
        if recovery_policy not in _ACCEPTANCE_RECOVERY_POLICIES:
            issues.append(
                f"acceptance.recovery_only_policy returned unknown value {recovery_policy!r}"
            )

    restart = _preview_mapping_section("restart", plan.get("restart", {}), issues)
    if restart is not None:
        _preview_section_keys(
            "restart",
            restart,
            allowed=_MAIN_SEARCH_RESTART_REQUIRED_KEYS,
            required=_MAIN_SEARCH_RESTART_REQUIRED_KEYS,
            require_missing=enabled,
            issues=issues,
        )
        restart_enabled = restart.get("enabled", False)
        if not isinstance(restart_enabled, bool):
            issues.append(f"restart.enabled returned non-bool value {restart_enabled!r}")
        _check_number(
            "restart.stagnation_rounds",
            restart.get("stagnation_rounds", 0),
            minimum=0,
            maximum=25,
            integral=True,
            issues=issues,
        )
        _check_number(
            "restart.max_restarts",
            restart.get("max_restarts", 0),
            minimum=0,
            maximum=3,
            integral=True,
            issues=issues,
        )

    perturbation = _preview_mapping_section("perturbation", plan.get("perturbation", {}), issues)
    if perturbation is not None:
        _preview_section_keys(
            "perturbation",
            perturbation,
            allowed=_MAIN_SEARCH_PERTURBATION_ALLOWED_KEYS,
            required=_MAIN_SEARCH_PERTURBATION_REQUIRED_KEYS,
            require_missing=enabled,
            issues=issues,
        )
        perturbation_enabled = perturbation.get("enabled", False)
        if not isinstance(perturbation_enabled, bool):
            issues.append(
                f"perturbation.enabled returned non-bool value {perturbation_enabled!r}"
            )
        _check_number(
            "perturbation.strength",
            perturbation.get("strength", 1),
            minimum=1,
            maximum=8,
            integral=True,
            issues=issues,
        )
        _check_number(
            "perturbation.max_perturbations",
            perturbation.get("max_perturbations", 0),
            minimum=0,
            maximum=4,
            integral=True,
            issues=issues,
        )
        schedule = str(perturbation.get("schedule", "after_no_improvement")).strip()
        if schedule not in _MAIN_SEARCH_PERTURBATION_SCHEDULES:
            issues.append(f"perturbation.schedule returned unknown value {schedule!r}")

    post_baseline = plan.get("post_baseline_operators_enabled", False)
    if not isinstance(post_baseline, bool):
        issues.append(
            "post_baseline_operators_enabled returned non-bool value "
            f"{post_baseline!r}"
        )
    _check_number(
        "operator_round_limit",
        plan.get("operator_round_limit", 0),
        minimum=0,
        maximum=20,
        integral=True,
        issues=issues,
    )


def _preview_alns_vns_policy(
    module: types.ModuleType,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    plan = _call_preview_function(module, "alns_vns_plan", instance, issues, checks)
    if plan is _PREVIEW_FAILED:
        return
    if not isinstance(plan, Mapping):
        issues.append(f"alns_vns_plan returned non-mapping value {plan!r}")
        return
    _preview_policy_keys(
        "alns_vns_plan",
        plan,
        allowed=_ALNS_VNS_POLICY_ALLOWED_KEYS,
        issues=issues,
    )
    enabled = plan.get("enabled", False)
    if not isinstance(enabled, bool):
        issues.append(f"alns_vns_plan enabled returned non-bool value {enabled!r}")
    _check_sequence_literals(
        "alns_vns.components",
        plan.get("components", ["alns", "vns"]),
        allowed=_ALNS_VNS_ALLOWED_COMPONENTS,
        allow_empty=False,
        issues=issues,
    )
    weights = plan.get("component_weights", {"alns": 1.0, "vns": 1.0})
    _preview_weight_mapping(
        "alns_vns.component_weights",
        weights,
        allowed=_ALNS_VNS_ALLOWED_COMPONENTS,
        issues=issues,
    )
    params = plan.get("params", {})
    if not isinstance(params, Mapping):
        issues.append(f"alns_vns.params returned non-mapping value {params!r}")
    else:
        _preview_baseline_params_mapping(params, issues)


def _preview_destroy_repair_policy(
    module: types.ModuleType,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    plan = _call_preview_function(module, "destroy_repair_plan", instance, issues, checks)
    if plan is _PREVIEW_FAILED:
        return
    if not isinstance(plan, Mapping):
        issues.append(f"destroy_repair_plan returned non-mapping value {plan!r}")
        return
    _preview_policy_keys(
        "destroy_repair_plan",
        plan,
        allowed=_DESTROY_REPAIR_POLICY_ALLOWED_KEYS,
        issues=issues,
    )
    enabled = plan.get("enabled", False)
    if not isinstance(enabled, bool):
        issues.append(f"destroy_repair_plan enabled returned non-bool value {enabled!r}")
    _check_sequence_literals(
        "destroy_selectors",
        plan.get("destroy_selectors", ["worst_removal"]),
        allowed=_DESTROY_REPAIR_ALLOWED_DESTROY_SELECTORS,
        allow_empty=False,
        issues=issues,
    )
    _check_sequence_literals(
        "repair_selectors",
        plan.get("repair_selectors", ["regret_2"]),
        allowed=_DESTROY_REPAIR_ALLOWED_REPAIR_SELECTORS,
        allow_empty=False,
        issues=issues,
    )
    subset_strategy = str(
        plan.get("subset_strategy", "prefix_shifted_route_diverse")
    ).strip()
    if subset_strategy not in _DESTROY_REPAIR_SUBSET_STRATEGIES:
        issues.append(f"subset_strategy returned unknown value {subset_strategy!r}")
    _check_number(
        "max_destroy_customers",
        plan.get("max_destroy_customers", 6),
        minimum=1,
        maximum=12,
        integral=True,
        issues=issues,
    )
    _check_number(
        "repair_budget_per_customer",
        plan.get("repair_budget_per_customer", 4),
        minimum=1,
        maximum=16,
        integral=True,
        issues=issues,
    )
    fallback = plan.get("fallback_to_smaller_subsets", True)
    if not isinstance(fallback, bool):
        issues.append(
            f"fallback_to_smaller_subsets returned non-bool value {fallback!r}"
        )
    phase_best = plan.get("phase_best_preference", True)
    if not isinstance(phase_best, bool):
        issues.append(f"phase_best_preference returned non-bool value {phase_best!r}")


def _preview_route_pair_candidate_policy(
    module: types.ModuleType,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    plan = _call_preview_function(module, "route_pair_plan", instance, issues, checks)
    if plan is _PREVIEW_FAILED:
        return
    if not isinstance(plan, Mapping):
        issues.append(f"route_pair_plan returned non-mapping value {plan!r}")
        return
    _preview_policy_keys(
        "route_pair_plan",
        plan,
        allowed=_ROUTE_PAIR_POLICY_ALLOWED_KEYS,
        issues=issues,
    )
    enabled = plan.get("enabled", False)
    if not isinstance(enabled, bool):
        issues.append(f"route_pair_plan enabled returned non-bool value {enabled!r}")
    _check_sequence_literals(
        "route_pair.scoring_terms",
        plan.get("scoring_terms", ["route_distance", "removal_saving", "distance_saving"]),
        allowed=_ROUTE_PAIR_ALLOWED_SCORING_TERMS,
        allow_empty=False,
        issues=issues,
    )
    _check_sequence_literals(
        "route_pair.move_families",
        plan.get("move_families", ["customer_swap"]),
        allowed=_ROUTE_PAIR_ALLOWED_MOVE_FAMILIES,
        allow_empty=False,
        issues=issues,
    )
    limits = plan.get("candidate_limits", {})
    if not isinstance(limits, Mapping):
        issues.append(f"route_pair.candidate_limits returned non-mapping value {limits!r}")
    else:
        _preview_limit_mapping(
            "route_pair.candidate_limits",
            limits,
            ranges=_ROUTE_PAIR_CANDIDATE_LIMIT_RANGES,
            issues=issues,
        )


def _preview_acceptance_restart_policy(
    module: types.ModuleType,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    plan = _call_preview_function(
        module,
        "acceptance_restart_plan",
        instance,
        issues,
        checks,
    )
    if plan is _PREVIEW_FAILED:
        return
    if not isinstance(plan, Mapping):
        issues.append(f"acceptance_restart_plan returned non-mapping value {plan!r}")
        return
    _preview_policy_keys(
        "acceptance_restart_plan",
        plan,
        allowed=_ACCEPTANCE_RESTART_POLICY_ALLOWED_KEYS,
        issues=issues,
    )
    enabled = plan.get("enabled", False)
    if not isinstance(enabled, bool):
        issues.append(
            f"acceptance_restart_plan enabled returned non-bool value {enabled!r}"
        )
    _check_number(
        "acceptance_restart.min_distance_improvement",
        plan.get("min_distance_improvement", 0.0),
        minimum=0.0,
        maximum=10.0,
        integral=False,
        issues=issues,
    )
    recovery_policy = str(plan.get("recovery_only_policy", "allow")).strip()
    if recovery_policy not in _ACCEPTANCE_RECOVERY_POLICIES:
        issues.append(
            f"recovery_only_policy returned unknown value {recovery_policy!r}"
        )

    restart = _preview_mapping_section("acceptance_restart.restart", plan.get("restart", {}), issues)
    if restart is not None:
        _preview_section_keys(
            "acceptance_restart.restart",
            restart,
            allowed=_MAIN_SEARCH_RESTART_REQUIRED_KEYS,
            required=_MAIN_SEARCH_RESTART_REQUIRED_KEYS,
            require_missing=False,
            issues=issues,
        )
        restart_enabled = restart.get("enabled", False)
        if not isinstance(restart_enabled, bool):
            issues.append(f"restart.enabled returned non-bool value {restart_enabled!r}")
        _check_number(
            "restart.stagnation_rounds",
            restart.get("stagnation_rounds", 0),
            minimum=0,
            maximum=25,
            integral=True,
            issues=issues,
        )
        _check_number(
            "restart.max_restarts",
            restart.get("max_restarts", 0),
            minimum=0,
            maximum=3,
            integral=True,
            issues=issues,
        )

    perturbation = _preview_mapping_section(
        "acceptance_restart.perturbation",
        plan.get("perturbation", {}),
        issues,
    )
    if perturbation is not None:
        _preview_section_keys(
            "acceptance_restart.perturbation",
            perturbation,
            allowed=_MAIN_SEARCH_PERTURBATION_ALLOWED_KEYS,
            required=_MAIN_SEARCH_PERTURBATION_REQUIRED_KEYS,
            require_missing=False,
            issues=issues,
        )
        perturbation_enabled = perturbation.get("enabled", False)
        if not isinstance(perturbation_enabled, bool):
            issues.append(
                f"perturbation.enabled returned non-bool value {perturbation_enabled!r}"
            )
        schedule = str(perturbation.get("schedule", "after_no_improvement")).strip()
        if schedule not in _MAIN_SEARCH_PERTURBATION_SCHEDULES:
            issues.append(f"perturbation.schedule returned unknown value {schedule!r}")
        _check_number(
            "perturbation.strength",
            perturbation.get("strength", 1),
            minimum=1,
            maximum=8,
            integral=True,
            issues=issues,
        )
        _check_number(
            "perturbation.max_perturbations",
            perturbation.get("max_perturbations", 0),
            minimum=0,
            maximum=4,
            integral=True,
            issues=issues,
        )


def _preview_mapping_section(
    name: str,
    value: Any,
    issues: list[str],
) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    issues.append(f"{name} returned non-mapping value {value!r}")
    return None


def _preview_section_keys(
    name: str,
    section: Mapping[str, Any],
    *,
    allowed: frozenset[str],
    required: frozenset[str],
    require_missing: bool,
    issues: list[str],
) -> None:
    unknown = sorted(str(key) for key in section if str(key) not in allowed)
    if unknown:
        issues.append(f"{name} returned unknown keys {unknown}")
    if require_missing:
        missing = sorted(key for key in required if key not in section)
        if missing:
            issues.append(f"enabled {name} missing required keys {missing}")


def _preview_policy_keys(
    name: str,
    plan: Mapping[str, Any],
    *,
    allowed: frozenset[str],
    issues: list[str],
) -> None:
    unknown = sorted(str(key) for key in plan if str(key) not in allowed)
    if unknown:
        issues.append(f"{name} returned unknown keys {unknown}")


def _preview_weight_mapping(
    name: str,
    value: Any,
    *,
    allowed: frozenset[str],
    issues: list[str],
) -> None:
    if not isinstance(value, Mapping):
        issues.append(f"{name} returned non-mapping value {value!r}")
        return
    for key, weight in value.items():
        item = str(key).strip()
        if item not in allowed:
            issues.append(f"{name} returned unknown key {item!r}")
            continue
        _check_number(
            f"{name}[{item}]",
            weight,
            minimum=0.0,
            maximum=5.0,
            integral=False,
            issues=issues,
        )


def _preview_limit_mapping(
    name: str,
    value: Mapping[str, Any],
    *,
    ranges: Mapping[str, tuple[int, int]],
    issues: list[str],
) -> None:
    for key, limit in value.items():
        item = str(key).strip()
        if item not in ranges:
            issues.append(f"{name} returned unknown key {item!r}")
            continue
        lo, hi = ranges[item]
        _check_number(
            f"{name}[{item}]",
            limit,
            minimum=lo,
            maximum=hi,
            integral=True,
            issues=issues,
        )


def _preview_baseline_params_mapping(
    params: Mapping[str, Any],
    issues: list[str],
) -> None:
    unknown = sorted(str(key) for key in params if str(key) not in _BASELINE_POLICY_ALLOWED_KEYS)
    if unknown:
        issues.append(f"baseline.params returned unknown keys {unknown}")
    if "destroy_ratio" in params:
        _check_destroy_ratio(params["destroy_ratio"], issues)
    if "segment_length" in params:
        _check_number(
            "baseline.params.segment_length",
            params["segment_length"],
            minimum=1,
            maximum=1000,
            integral=True,
            issues=issues,
        )
    if "reaction_factor" in params:
        _check_number(
            "baseline.params.reaction_factor",
            params["reaction_factor"],
            minimum=0.01,
            maximum=1.0,
            integral=False,
            issues=issues,
        )
    if "vns_max_no_improve" in params:
        _check_number(
            "baseline.params.vns_max_no_improve",
            params["vns_max_no_improve"],
            minimum=0,
            maximum=20000,
            integral=True,
            issues=issues,
        )
    if "use_vns" in params and not isinstance(params["use_vns"], bool):
        issues.append(f"baseline.params.use_vns returned non-bool value {params['use_vns']!r}")
    for name in ("cw_threshold", "vns_threshold", "alns_threshold"):
        if name in params:
            _check_number(
                f"baseline.params.{name}",
                params[name],
                minimum=0,
                maximum=10000,
                integral=True,
                issues=issues,
            )
    if "max_destroy_customers" in params:
        _check_number(
            "baseline.params.max_destroy_customers",
            params["max_destroy_customers"],
            minimum=1,
            maximum=500,
            integral=True,
            issues=issues,
        )


def _preview_algorithm_blueprint(
    module: types.ModuleType,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    plan = _call_preview_function(module, "algorithm_plan", instance, issues, checks)
    if plan is _PREVIEW_FAILED:
        return
    if not isinstance(plan, Mapping):
        issues.append(f"algorithm_plan returned non-mapping value {plan!r}")
        return

    unknown = sorted(str(key) for key in plan if str(key) not in _ALGORITHM_BLUEPRINT_REQUIRED_KEYS)
    if unknown:
        issues.append(f"algorithm_plan returned unknown keys {unknown}")
    enabled = plan.get("enabled", False)
    if not isinstance(enabled, bool):
        issues.append(f"algorithm_plan enabled returned non-bool value {enabled!r}")
        enabled = False
    if enabled:
        missing = sorted(key for key in _ALGORITHM_BLUEPRINT_REQUIRED_KEYS if key not in plan)
        if missing:
            issues.append(f"enabled algorithm_plan missing required keys {missing}")

    methods = plan.get("construction_methods", ["nearest_neighbor"])
    _check_sequence_literals(
        "construction_methods",
        methods,
        allowed=_ALLOWED_CONSTRUCTION_MODES,
        allow_empty=False,
        issues=issues,
    )
    _check_number(
        "construction_keep_top_k",
        plan.get("construction_keep_top_k", 1),
        minimum=1,
        maximum=4,
        integral=True,
        issues=issues,
    )
    _check_number(
        "construction_bias",
        plan.get("construction_bias", 0.0),
        minimum=0.0,
        maximum=1.0,
        integral=False,
        issues=issues,
    )
    _check_number(
        "baseline_time_fraction",
        plan.get("baseline_time_fraction", 0.8),
        minimum=0.2,
        maximum=0.95,
        integral=False,
        issues=issues,
    )
    _check_number(
        "operator_round_limit",
        plan.get("operator_round_limit", 20),
        minimum=0,
        maximum=20,
        integral=True,
        issues=issues,
    )
    post_baseline = plan.get("post_baseline_operators_enabled", True)
    if not isinstance(post_baseline, bool):
        issues.append(
            "post_baseline_operators_enabled returned non-bool value "
            f"{post_baseline!r}"
        )

    local_search = plan.get("local_search", {})
    if not isinstance(local_search, Mapping):
        issues.append(f"local_search returned non-mapping value {local_search!r}")
    else:
        unknown_local = sorted(
            str(key)
            for key in local_search
            if str(key) not in {"enabled_components", "rounds", "top_k"}
        )
        if unknown_local:
            issues.append(f"local_search returned unknown keys {unknown_local}")
        _check_sequence_literals(
            "local_search.enabled_components",
            local_search.get("enabled_components", []),
            allowed=_ALLOWED_BLUEPRINT_LOCAL_SEARCH_COMPONENTS,
            allow_empty=True,
            issues=issues,
        )
        _check_number(
            "local_search.rounds",
            local_search.get("rounds", 0),
            minimum=0,
            maximum=4,
            integral=True,
            issues=issues,
        )
        _check_number(
            "local_search.top_k",
            local_search.get("top_k", 16),
            minimum=0,
            maximum=64,
            integral=True,
            issues=issues,
        )

    restart = plan.get("restart", {})
    if not isinstance(restart, Mapping):
        issues.append(f"restart returned non-mapping value {restart!r}")
    else:
        unknown_restart = sorted(
            str(key)
            for key in restart
            if str(key) not in {"enabled", "stagnation_rounds"}
        )
        if unknown_restart:
            issues.append(f"restart returned unknown keys {unknown_restart}")
        restart_enabled = restart.get("enabled", False)
        if not isinstance(restart_enabled, bool):
            issues.append(f"restart.enabled returned non-bool value {restart_enabled!r}")
        _check_number(
            "restart.stagnation_rounds",
            restart.get("stagnation_rounds", 0),
            minimum=0,
            maximum=25,
            integral=True,
            issues=issues,
        )


def _check_sequence_literals(
    field: str,
    value: Any,
    *,
    allowed: frozenset[str],
    allow_empty: bool,
    issues: list[str],
) -> None:
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        issues.append(f"{field} returned non-sequence value {value!r}")
        return
    normalized = [str(item).strip() for item in value]
    bad = [item for item in normalized if item not in allowed]
    if bad:
        issues.append(f"{field} returned unknown values {bad}")
    if not normalized and not allow_empty:
        issues.append(f"{field} returned an empty sequence")


def _check_destroy_ratio(value: Any, issues: list[str]) -> None:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        issues.append(f"destroy_ratio returned non-pair value {value!r}")
        return
    if len(value) != 2:
        issues.append(f"destroy_ratio must contain exactly two values, got {value!r}")
        return
    before = len(issues)
    _check_number(
        "destroy_ratio[0]",
        value[0],
        minimum=0.01,
        maximum=0.80,
        integral=False,
        issues=issues,
    )
    _check_number(
        "destroy_ratio[1]",
        value[1],
        minimum=0.01,
        maximum=0.80,
        integral=False,
        issues=issues,
    )
    if len(issues) != before:
        return
    if float(value[0]) > float(value[1]):
        issues.append(
            f"destroy_ratio lower bound {value[0]!r} exceeds upper bound {value[1]!r}"
        )


_PREVIEW_FAILED = object()


def _call_preview_function(
    module: types.ModuleType,
    name: str,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> Any:
    func = getattr(module, name, None)
    if not callable(func):
        issues.append(f"missing callable {name}")
        checks.append({"name": name, "passed": False, "detail": "missing callable"})
        return _PREVIEW_FAILED
    try:
        value = func(instance, _POLICY_PREVIEW_TIME_LIMIT_SEC)
    except Exception as exc:
        issues.append(f"{name} raised during synthetic preview: {exc}")
        checks.append({"name": name, "passed": False, "detail": str(exc)})
        return _PREVIEW_FAILED
    checks.append({"name": name, "passed": True, "detail": repr(value)[:200]})
    return value


def _check_number(
    field: str,
    value: Any,
    *,
    minimum: float,
    maximum: float,
    integral: bool,
    issues: list[str],
) -> None:
    if isinstance(value, bool):
        issues.append(f"{field} returned bool where numeric value is required")
        return
    if integral:
        if not isinstance(value, int):
            issues.append(f"{field} returned non-integer value {value!r}")
            return
        numeric = float(value)
    else:
        if not isinstance(value, (int, float)):
            issues.append(f"{field} returned non-numeric value {value!r}")
            return
        numeric = float(value)
    if not math.isfinite(numeric):
        issues.append(f"{field} returned non-finite value {value!r}")
        return
    if numeric < minimum or numeric > maximum:
        issues.append(f"{field}={value!r} outside [{minimum}, {maximum}]")
