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
_FORCED_DIAGNOSTIC_MAIN_SEARCH_DEEP_COMPONENTS = frozenset(
    {
        "route_pair_swap",
        "bounded_destroy_repair",
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
_MAIN_SEARCH_CONSTRUCTION_REQUIRED_KEYS = frozenset(
    {"methods", "keep_top_k", "bias"}
)
_MAIN_SEARCH_BASELINE_REQUIRED_KEYS = frozenset({"time_fraction", "params"})
_MAIN_SEARCH_IMPROVEMENT_REQUIRED_KEYS = frozenset(
    {"enabled_components", "rounds", "top_k"}
)
_MAIN_SEARCH_ACCEPTANCE_REQUIRED_KEYS = frozenset({"min_distance_improvement"})
_MAIN_SEARCH_RESTART_REQUIRED_KEYS = frozenset(
    {"enabled", "stagnation_rounds", "max_restarts"}
)
_MAIN_SEARCH_PERTURBATION_REQUIRED_KEYS = frozenset(
    {"enabled", "strength", "max_perturbations"}
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
_POLICY_INSTANCE_API_TEXT = (
    "Safe CvrpInstance API for policy functions: use "
    "`instance.customer_ids`, `instance.customer_count`, "
    "`instance.demands[customer_id]`, `instance.capacity`, and "
    "`instance.distance(i, j)`. `instance.demand(customer_id)` remains "
    "available for direct demand lookup. Never use `instance.customers`; that "
    "attribute is intentionally not defined and will fail synthetic preview or "
    "runtime audit when reached."
)


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
            "- The `main_search_strategy` research surface is the current "
            "problem-owned whole-algorithm surface. It is inactive by default. "
            "When enabled with a valid plan, it takes over construction "
            "ensemble selection, repo-local baseline budget and sanitized "
            "baseline params, package-owned main improvement components "
            "including route-pair swap and bounded destroy/repair, bounded "
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
        if surface_name == "main_search_strategy":
            return (
                "policies/main_search_strategy.py is a module-level "
                "whole-algorithm strategy surface; no class is required.\n\n"
                "Declared signature:\n"
                "main_search_plan(instance, time_limit_sec)\n\n"
                "Required function:\n"
                "def main_search_plan(instance, time_limit_sec):\n"
                "    return a dict with exactly these top-level keys: enabled, "
                "construction, baseline, improvement, acceptance, restart, "
                "perturbation, post_baseline_operators_enabled, and "
                "operator_round_limit.\n\n"
                "Plan contract:\n"
                "- enabled: bool. The default must be False. Only enabled=True "
                "and a valid plan lets this surface take over the main CVRP "
                "algorithm lifecycle.\n"
                "- construction: dict with methods, keep_top_k, and bias. "
                "methods is drawn from 'nearest_neighbor', "
                "'nearest_neighbor_demand_bias', 'demand_descending', and "
                "'sequential'; keep_top_k is an int in [1, 4]; bias is a finite "
                "number in [0.0, 1.0].\n"
                "- baseline: dict with time_fraction in [0.2, 0.95] and params "
                "mapping. params accepts the same sanitized bounded keys as "
                "baseline_policy.baseline_params.\n"
                "- improvement: dict with enabled_components, rounds, and top_k. "
                "enabled_components is drawn from 'intra_route_2opt', "
                "'inter_route_relocate', 'route_pair_swap', and "
                "'bounded_destroy_repair'; enabled plans must include at least "
                "one component, rounds in [1, 8], and top_k in [1, 128].\n"
                "- acceptance: dict with min_distance_improvement finite number "
                "in [0.0, 10.0].\n"
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
            "main_search_strategy",
            "algorithm_blueprint",
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
        elif surface_name == "main_search_strategy":
            _preview_main_search_strategy(module, instance, issues, checks)
        elif surface_name == "algorithm_blueprint":
            _preview_algorithm_blueprint(module, instance, issues, checks)
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
        "policies/main_search_strategy.py": "main_search_strategy",
        "policies/algorithm_blueprint.py": "algorithm_blueprint",
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

    unknown = sorted(str(key) for key in plan if str(key) not in _MAIN_SEARCH_STRATEGY_REQUIRED_KEYS)
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
            missing_deep = sorted(
                _FORCED_DIAGNOSTIC_MAIN_SEARCH_DEEP_COMPONENTS - selected
            )
            checks.append(
                {
                    "name": "main_search_forced_diagnostic_deep_component_coverage",
                    "passed": not missing_deep,
                    "severity": "diagnostic_warning",
                    "required_components": sorted(
                        _FORCED_DIAGNOSTIC_MAIN_SEARCH_DEEP_COMPONENTS
                    ),
                    "selected_components": sorted(selected),
                    "missing_components": missing_deep,
                    "guidance": (
                        "Forced main_search_strategy diagnostics should select both "
                        "route_pair_swap and bounded_destroy_repair so runtime can "
                        "audit selected/attempted/deep-component coverage. This "
                        "preview advisory does not make an otherwise valid normal "
                        "promotion plan fail."
                    ),
                }
            )

    acceptance = _preview_mapping_section("acceptance", plan.get("acceptance", {}), issues)
    if acceptance is not None:
        _preview_section_keys(
            "acceptance",
            acceptance,
            allowed=_MAIN_SEARCH_ACCEPTANCE_REQUIRED_KEYS,
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
            allowed=_MAIN_SEARCH_PERTURBATION_REQUIRED_KEYS,
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
