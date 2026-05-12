"""CVRP ProblemAdapter implementation for Scion v0.4."""
from __future__ import annotations

import math
from pathlib import Path
import types
from typing import Any, Mapping, Sequence

from scion.problem.contracts import CheckReport, LowerBoundEstimate, SolverArtifact
from scion.problem.spec import ProblemSpecV1
from scion.problems.cvrp.cvrplib import load_cvrplib_instance
from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution


_POLICY_PREVIEW_TIME_LIMIT_SEC = 1.0
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
    }
)
_MAIN_SEARCH_DEEP_ATTRIBUTION_COMPONENTS = _ALLOWED_MAIN_SEARCH_COMPONENTS
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
        "main_search_component_accepted_delta_sum",
        "main_search_component_recovery_delta_sum",
        "main_search_component_phase_delta_sum",
        "main_search_objective_delta_by_phase",
        "main_search_objective_trace",
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
    "`instance.customer_ids`, `instance.customer_count`, "
    "`instance.demands[customer_id]`, `instance.capacity`, and "
    "`instance.distance(i, j)`. `instance.demand(customer_id)` remains "
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
            "The CVRP campaign solver first builds a baseline solution. For real "
            "CVRPLIB .vrp cases, it uses the repo-local vrp/src ALNS+VNS baseline "
            "when SCION_PROBLEM_DATA_ROOT or SCION_CVRP_DATA_ROOT points at the vrp directory; JSON and "
            "synthetic smoke fixtures use a deterministic nearest-neighbor fallback.\n"
            "- The `construction_policy` research surface may select a bounded "
            "package-owned construction mode and numeric demand bias before the "
            "baseline/operator phase.\n"
            "- The `search_policy` research surface may tune the baseline time "
            "fraction, post-baseline operator round limit, and whether "
            "post-baseline operators run at all.\n"
            "- The `baseline_policy` research surface may tune bounded "
            "repo-local vrp/src ALNS+VNS main-search knobs such as destroy "
            "ratio, ALNS segment length, adaptive reaction factor, VNS usage, "
            "VNS no-improvement limit, threshold gates, and max destroyed "
            "customers. Invalid returns are sanitized to defaults or clamped "
            "and recorded as runtime audit failures.\n"
            "- The `neighborhood_portfolio` research surface may select "
            "predeclared registry component families, apply component weight "
            "multipliers, and bound rounds, top-k scheduled operators, and "
            "component attempt limits before the post-baseline operator loop.\n"
            "- The `algorithm_blueprint` research surface is inactive by "
            "default. When a candidate returns an enabled valid plan, it "
            "coordinates the top-level CVRP algorithm lifecycle: bounded "
            "construction ensemble, baseline budget, package-owned local "
            "search, restart knobs, and post-baseline registry-operator "
            "toggle/round limit.\n"
            "- The `solver_design` research surface is the problem-owned "
            "solver-design boundary. It is backed by "
            "`policies/main_search_strategy.py` and inactive by default. When "
            "enabled with a valid plan, it takes over the problem-object "
            "adaptation layer: instance-profile intent, solver strategy family, "
            "construction ensemble selection, repo-local baseline budget and "
            "sanitized baseline params, package-owned main improvement "
            "components, component roles/order, bounded per-component "
            "acceptance/restart/perturbation knobs, and the optional "
            "post-baseline registry-operator toggle. Registry operators are "
            "disabled by default for this surface unless explicitly enabled.\n"
            "- The algorithm blueprint can only select package-owned bounded "
            "local-search components (`intra_route_2opt` and "
            "`inter_route_relocate`); it cannot inject route-editing code into "
            "the solver.\n"
            "- Operator research surfaces are applied after the baseline in a "
            "bounded improvement loop, up to the policy-controlled round limit "
            "or until the solver time budget is exhausted.\n"
            "- In each operator round, loaded operators are tried in registry "
            "weight order. A returned solution is accepted only if it is feasible "
            "and strictly improves the lexicographic objective.\n"
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
        if surface_name in {"solver_design", "main_search_strategy"}:
            return (
                "policies/main_search_strategy.py is a module-level "
                "CVRP solver-design surface; no class is required.\n\n"
                "Declared signature:\n"
                "main_search_plan(instance, time_limit_sec)\n\n"
                "Required function:\n"
                "def main_search_plan(instance, time_limit_sec):\n"
                "    return a dict with exactly these top-level keys: enabled, "
                "problem_adaptation, construction, baseline, improvement, "
                "acceptance, restart, perturbation, "
                "post_baseline_operators_enabled, and "
                "operator_round_limit.\n\n"
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
                "or runtime_neutrality. component_roles maps allowed "
                "components to primary/support/probe/disabled, fallback_order "
                "orders allowed components, and evidence_targets lists runtime "
                "fields expected to move.\n"
                "- construction: dict with methods, keep_top_k, and bias. "
                "methods is drawn from 'nearest_neighbor', "
                "'nearest_neighbor_demand_bias', 'demand_descending', and "
                "'sequential'; keep_top_k is an int in [1, 4]; bias is a finite "
                "number in [0.0, 1.0].\n"
                "- baseline: dict with time_fraction in [0.2, 0.95] and params "
                "mapping. params accepts the same sanitized bounded keys as "
                "baseline_policy.baseline_params. For formal-like .vrp runs, "
                "the solver applies a bounded quality guard so active "
                "solver_design uses an effective baseline fraction of "
                "at least 0.75.\n"
                "- improvement: dict with enabled_components, rounds, and top_k. "
                "enabled_components is drawn from 'intra_route_2opt', "
                "'inter_route_relocate', 'route_pair_swap', and "
                "'bounded_destroy_repair'; enabled plans must include at least "
                "one component, rounds in [1, 8], and top_k in [1, 128]. "
                "Choose top_k and component caps as part of the solver-level "
                "hypothesis, and predict the phase/objective evidence they "
                "should move.\n"
                "- Solver-design semantic identity is part of the proposal "
                "contract: `novelty_signature.selected_components` and "
                "`novelty_signature.deep_components_selected` must be "
                "non-empty JSON arrays of component names. Do not use false, "
                "null, or empty arrays for these fields.\n"
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

        if str(getattr(patch, "action", "modify")) == "delete":
            return _policy_preview_result(
                surface_name,
                [f"{surface_name} cannot be sanity-previewed for delete action"],
                [],
            )

        issues: list[str] = []
        checks: list[dict[str, Any]] = []
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
        elif surface_name in {"solver_design", "main_search_strategy"}:
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
        "policies/main_search_strategy.py": "solver_design",
        "policies/algorithm_blueprint.py": "algorithm_blueprint",
        "policies/alns_vns_policy.py": "alns_vns_policy",
        "policies/destroy_repair_policy.py": "destroy_repair_policy",
        "policies/route_pair_candidate_policy.py": "route_pair_candidate_policy",
        "policies/acceptance_restart_policy.py": "acceptance_restart_policy",
    }.get(normalized, "")


def _module_from_policy_code(file_path: str, code: str) -> types.ModuleType:
    module = types.ModuleType(f"_scion_cvrp_policy_preview_{abs(hash(file_path))}")
    module.__dict__["__file__"] = f"<preview:{file_path}>"
    module.__dict__["__name__"] = module.__name__
    exec(compile(code, file_path, "exec"), module.__dict__)
    return module


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
                if str(component) not in _ALLOWED_MAIN_SEARCH_COMPONENTS:
                    issues.append(
                        "problem_adaptation.component_roles returned unknown "
                        f"component {component!r}"
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
                        "problem-level plan fail."
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
