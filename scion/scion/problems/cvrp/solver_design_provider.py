"""CVRP-owned solver-design prompt and smoke interpretation hooks."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from scion.core.models import HypothesisProposal, PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path

_LOW_EFFORT_MIN_CASES = 2
_LOW_EFFORT_MAX_ITERATIONS = 5
_LOW_EFFORT_MAX_ATTEMPTS = 30
_LOW_EFFORT_MAX_RUNTIME_RATIO = 0.35
_LOW_EFFORT_STOP_REASONS = frozenset(
    {
        "no_improvement",
        "early_exit",
        "construction_only",
        "no_search",
    }
)
_SMOKE_TIME_LIMIT_SEC = 3

_BROAD_SCOPE_TERMS = (
    "hybrid",
    "alns",
    "vns",
    "lns",
    "destroy",
    "repair",
    "recombination",
    "route-pool",
    "route pool",
    "population",
    "portfolio",
    "ensemble",
    "multi-operator",
    "multi operator",
    "restart",
    "perturb",
)

_ACTIVE_SOLVER_DESIGN_PACKAGE = (
    "`policies/baseline_algorithm.py` and `policies/baseline_modules/*.py`"
)

_SOLVER_DESIGN_API_MANIFEST_FILES = (
    "policies/baseline_algorithm.py",
    "policies/baseline_modules/scheduler.py",
    "policies/baseline_modules/construction.py",
    "policies/baseline_modules/destroy_repair.py",
    "policies/baseline_modules/local_search.py",
    "policies/baseline_modules/acceptance.py",
    "policies/baseline_modules/state.py",
    "policies/baseline_modules/config.py",
)

_SOLVER_DESIGN_INTEGRATION_FULL_FILES = (
    "policies/baseline_algorithm.py",
    "policies/baseline_modules/scheduler.py",
    "policies/baseline_modules/state.py",
)

_SOLVER_DESIGN_INTEGRATION_SUMMARY_FILES = (
    "policies/baseline_modules/construction.py",
    "policies/baseline_modules/destroy_repair.py",
    "policies/baseline_modules/local_search.py",
    "policies/baseline_modules/acceptance.py",
    "policies/baseline_modules/config.py",
)


class CvrpSolverDesignProvider:
    """Problem-owned guidance for CVRP solver-design proposal tooling."""

    def solver_design_broad_scope_terms(self) -> Sequence[str]:
        return _BROAD_SCOPE_TERMS

    def solver_design_api_manifest_files(self) -> Sequence[str]:
        return _SOLVER_DESIGN_API_MANIFEST_FILES

    def solver_design_integration_full_files(self) -> Sequence[str]:
        return _SOLVER_DESIGN_INTEGRATION_FULL_FILES

    def solver_design_integration_summary_files(self) -> Sequence[str]:
        return _SOLVER_DESIGN_INTEGRATION_SUMMARY_FILES

    def solver_design_target_api_guidance(self, target_file: str) -> str:
        normalized = str(target_file or "").replace("\\", "/").lstrip("/")
        if normalized == "policies/baseline_modules/destroy_repair.py":
            return (
                "Target-specific rule for destroy_repair.py: make destroy/repair "
                "operators the primary mechanism in this file. A scheduler.py "
                "additional_change may only import newly defined destroy/repair "
                "symbols from .destroy_repair and add them to destroy_ops or "
                "repair_ops. Do not add scheduler imports from construction.py "
                "while destroy_repair.py is the approved target, unless the same "
                "patch also changes construction.py and defines that exact symbol. "
                "Existing construction exports are _clarke_wright_savings, "
                "_nearest_neighbor, _sweep_construction, and "
                "_capacity_balanced_construction; names like _clarke_wright, "
                "_clarke_wright_solution, _nearest_neighbor_solution, "
                "_nearest_neighbor_construction, _savings_solution, and "
                "_savings_construction do not exist. Prefer bounded for-loops or "
                "while loops with a visibly incremented counter cap."
            )
        if normalized == "policies/baseline_modules/construction.py":
            return (
                "Target-specific rule for construction.py: construction helpers "
                "must return internal _Solution objects. Wire new seed helpers "
                "through scheduler.py only by importing the exact new symbol from "
                ".construction and calling it inside _ALNSVNSSolver methods."
            )
        if normalized == "policies/baseline_modules/local_search.py":
            return (
                "Target-specific rule for local_search.py: integrate new moves "
                "through _default_vns_operators() or the existing _vns(...) call "
                "path. Scheduler.py should keep calling _vns(candidate, "
                "_default_vns_operators(), ...)."
            )
        return ""

    def solver_design_hypothesis_guidance(self, context: Any) -> Sequence[str]:
        return (
            "For `solver_design`, choose the target file by mechanism ownership, "
            "not by convenience.",
            (
                "For `solver_design` expected_telemetry, use the selected surface "
                "evidence contract categories only: activity, activation, effect, "
                "and budget. Runtime field names from the adapter belong inside "
                "those categories, never as top-level expected_telemetry keys."
            ),
            (
                "Use `policies/baseline_modules/scheduler.py` mainly for "
                "orchestration or wiring. If the new mechanism is construction, "
                "destroy/repair, local improvement, or acceptance, target that "
                "concrete module and put any needed scheduler/entrypoint "
                "integration in `additional_changes`."
            ),
            (
                "The active solver_design research object is "
                f"{_ACTIVE_SOLVER_DESIGN_PACKAGE}. Deleted legacy hooks are "
                "not optimization targets."
            ),
            (
                "Old operator surfaces and legacy component-policy surfaces are "
                "not active research context; do not recommend them as "
                "solver_design optimization directions."
            ),
            (
                "After win-rate-zero scheduler variants, prefer a non-scheduler "
                "mechanism module or a stable-entrypoint algorithm-body change "
                "over another phase-order or weight tweak."
            ),
        )

    def solver_design_code_rules(self, context: Any) -> Sequence[str]:
        return (
            (
                "The active solver_design research object is "
                f"{_ACTIVE_SOLVER_DESIGN_PACKAGE}. Legacy component surfaces "
                "and deleted hooks are not optimization targets."
            ),
            (
                "For the active entrypoint target "
                "(`policies/baseline_algorithm.py`), implement a complete "
                "`solve(instance, rng, time_limit_sec, context)` algorithm body. "
                "Do not return a lifecycle/config dictionary."
            ),
            (
                "For targets under `policies/baseline_modules/`, implement the "
                "complete contents of that branch-owned algorithm module and "
                "integrate with the existing entrypoint; do not add a top-level "
                "`solve` unless the target module already owns one."
            ),
            (
                "Default to a compact replacement file: one coherent construction "
                "or seeding path, one bounded improvement/search loop, no more "
                "than two move families, and only the helper functions needed for "
                "that path."
            ),
            (
                "Do not preserve the inactive template merely to edit a few "
                "constants, and do not grow a helper forest for ALNS/VNS, "
                "route-pool, destroy/repair, and perturbation all at once. Select "
                "one vertical algorithm slice that can run and screen now; later "
                "rounds can add breadth after it proves movement."
            ),
            (
                "When the approved target is `policies/baseline_algorithm.py`, "
                "change the controlled algorithm body directly and do not call "
                "`context.baseline` there. When the approved target is under "
                "`policies/baseline_modules/`, keep that module as the primary "
                "research object and use scheduler/entrypoint edits only as "
                "minimal wiring into the branch-owned solver. Do not route "
                "new optimization work through deleted compatibility hooks or "
                "`context.baseline` wrappers."
            ),
            (
                "Do not route solver-design optimization through "
                "operator surfaces or legacy component-policy surfaces. If "
                "deleted-hook names appear in artifacts, treat them as legacy "
                "context rather than candidate research paths."
            ),
            (
                "Do not submit a shallow wrapper that changes baseline "
                "budget/params or adds a tiny post-baseline polish."
            ),
            (
                "If the target is `policies/baseline_modules/scheduler.py`, treat "
                "scheduler as orchestration. A scheduler-only patch must change "
                "an actual bounded search trajectory, not only operator weights, "
                "phase order, or runtime allocation. When the hypothesis needs "
                "new construction, destroy/repair, local-search, or acceptance "
                "behavior, put the concrete mechanism module in "
                "`additional_changes` and use scheduler only to call it."
            ),
            (
                "If the target is `policies/baseline_modules/local_search.py`, "
                "integrate new move operators through the existing "
                "`_default_vns_operators()` and `_vns(...)` path. Do not invent "
                "a detached scheduler `_run`/`run` entrypoint to call them."
            ),
            (
                "If the target is `policies/baseline_modules/destroy_repair.py`, "
                "make this file own the destroy/repair mechanism. Use scheduler.py "
                "only as a minimal operator-pool wiring edit: import exact new "
                "symbols from `.destroy_repair` and add them to `destroy_ops` or "
                "`repair_ops`. Do not add construction.py imports in scheduler.py "
                "for a destroy_repair target unless the same patch also modifies "
                "construction.py and defines that exact symbol."
            ),
            (
                "If `additional_changes` touches `policies/baseline_algorithm.py`, "
                "keep the stable entrypoint shape: import `_ALNSVNSSolver` from "
                "`.baseline_modules.scheduler`, instantiate it, and call "
                "`solver.solve(instance, rng)` with no extra "
                "seed/context/initial_solution arguments. The constructor must "
                "use the current explicit keyword API: `time_limit`, "
                "`destroy_ratio`, `segment_length`, `reaction_factor`, "
                "`vns_max_no_improve`, `use_vns`, `cw_threshold`, "
                "`vns_threshold`, `alns_threshold`, `max_destroy_customers`, "
                "`max_routes`, and `context`. Do not import `solve`, `run`, or "
                "`main` from scheduler. If a new seed or construction hook is "
                "needed, integrate it inside `baseline_modules/scheduler.py` "
                "while keeping this entrypoint call shape."
            ),
            (
                "If `additional_changes` touches "
                "`policies/baseline_modules/scheduler.py` or "
                "`policies/baseline_algorithm.py` while another file is the "
                "approved target, preserve the stable runtime contract: "
                "`baseline_algorithm.py` must keep "
                "`_ALNSVNSSolver(...).solve(instance, rng)`, and `scheduler.py` "
                "must keep the class-based `_ALNSVNSSolver.__init__(self, *, "
                "time_limit, destroy_ratio, segment_length, reaction_factor, "
                "vns_max_no_improve, use_vns, cw_threshold, vns_threshold, "
                "alns_threshold, max_destroy_customers, max_routes, context)` "
                "and `_ALNSVNSSolver.solve(self, instance, rng)` path without "
                "adding top-level `solve`, `run`, or `main` entrypoints. "
                "Multi-module algorithm integration is allowed when it stays "
                "inside that auditable call chain."
            ),
            (
                "A solver-design patch that claims or touches search-bearing "
                "code must record real algorithm effort on smoke cases. If every "
                "successful case reports `solver_algorithm_search_iterations=0` "
                "and `solver_algorithm_move_attempts=0`, algorithm smoke will "
                "reject it as a wrapper/constructor-only path. If every "
                "successful smoke case stops almost immediately with only a "
                "handful of iterations/move attempts, no smoke micro-benchmark "
                "win, and a `no_improvement`-style stop reason, algorithm smoke "
                "will reject it as low active search effort rather than treating "
                "the under-spend as a valid speedup."
            ),
            (
                "If the approved hypothesis declares `mechanism_changes` or "
                "`expected_telemetry`, use that exact mechanism id in the active "
                "runtime telemetry helpers. For activation, record a positive "
                "iteration or phase runtime for that mechanism on paths that "
                "execute it. For effect, record move/improvement evidence for "
                "that same mechanism when it improves the objective. Do not "
                "rename the mechanism or edit the hypothesis telemetry contract "
                "to silence algorithm smoke."
            ),
            (
                "The active package state model uses `_Solution.routes` as "
                "`_Route` objects, not `list[list[int]]`. A `_Route` exposes "
                "`.customers`, `.load`, `.cost`, `.can_insert(customer)`, "
                "`.cost_of_insert(...)`, `.cost_of_remove(...)`, `.insert(...)`, "
                "`.remove(...)`, and `.recalculate()`. A `_Solution` exposes "
                "`.copy()`, `.rebuild_index()`, `.remove_empty_routes()`, "
                "`.is_feasible()`, and `.routes_as_tuples()`. Do not slice, "
                "concatenate, or overwrite `solution.routes` as customer lists; "
                "edit `route.customers` or use route methods, then rebuild "
                "indexes when route membership changes."
            ),
            (
                "`_Solution` does not expose `from_routes`, `from_public`, "
                "`from_cvrp_solution`, or `to_public`. Do not add those bridge "
                "methods to `state.py` to compensate for API confusion. Existing "
                "construction helpers in `construction.py` already return "
                "internal `_Solution` objects. If you truly need to turn public "
                "route tuples into an internal solution, import `_Route` and "
                "`_Solution` from `.state` and construct `_Solution(instance, "
                "[_Route(instance, route) for route in routes])`; return public "
                "output with `context.make_solution(solution.routes_as_tuples())`."
            ),
            (
                "You may change algorithm strategy and runtime scheduling, but "
                "not problem objective semantics, feasibility constraints, "
                "parsing, seeds, protocol splits, Decision rules, or "
                "adapter/runtime files."
            ),
        )

    def solver_design_scope_guidance(
        self,
        context: Any,
        *,
        mode: str,
        broad_terms: Sequence[str],
    ) -> Sequence[str]:
        lines = [
            (
                "Scion controls the research boundary; the code agent should "
                "still write a real algorithm, but this patch must be small "
                "enough to generate, review, preview, and screen."
            ),
            (
                "Active solver-design work belongs in "
                f"{_ACTIVE_SOLVER_DESIGN_PACKAGE}. "
                "Deleted hooks, operator surfaces, and legacy component surfaces "
                "are not optimization directions."
            ),
            (
                "Implement one primary mechanism now. Prefer a direct "
                "seed/construction plus one bounded relocate/swap/2-opt-style "
                "improvement loop over a broad hybrid portfolio."
            ),
            (
                "The target file should own the mechanism. If the target is "
                "scheduler.py after win-rate-zero scheduler attempts, keep "
                "scheduler as the active `_ALNSVNSSolver.solve` orchestration "
                "path and place the concrete construction/destroy-repair/"
                "local-search/acceptance mechanism in the matching module via "
                "`additional_changes`."
            ),
            (
                "Hard size target: keep the replacement file around 180 lines "
                "or less and around six helper functions or fewer unless "
                "correctness clearly requires slightly more."
            ),
            (
                "Do not implement more than two move/neighborhood families in "
                "one patch; choose the smallest complete algorithm slice that "
                "can change screening evidence."
            ),
            (
                "For local-search targets, wire new move operators into the "
                "existing `_default_vns_operators()` list or existing `_vns(...)` "
                "call path; do not create detached `_run`/`run` scheduler "
                "entrypoints."
            ),
            (
                "If baseline_algorithm.py is only an integration edit, keep the "
                "stable scheduler class API: import `_ALNSVNSSolver`, instantiate "
                "it with the current explicit keywords (`time_limit`, "
                "`destroy_ratio`, `segment_length`, `reaction_factor`, "
                "`vns_max_no_improve`, `use_vns`, `cw_threshold`, "
                "`vns_threshold`, `alns_threshold`, `max_destroy_customers`, "
                "`max_routes`, `context`), and call `solver.solve(instance, rng)` "
                "with no extra arguments; do not import scheduler `solve`, "
                "`run`, or `main`."
            ),
            (
                "If scheduler.py or baseline_algorithm.py is only an integration "
                "edit, preserve the stable runtime contract: baseline_algorithm.py "
                "calls `_ALNSVNSSolver(...).solve(instance, rng)`, and scheduler.py "
                "keeps the class-based `_ALNSVNSSolver.__init__(self, *, "
                "time_limit, destroy_ratio, segment_length, reaction_factor, "
                "vns_max_no_improve, use_vns, cw_threshold, vns_threshold, "
                "alns_threshold, max_destroy_customers, max_routes, context)` "
                "plus `_ALNSVNSSolver.solve(self, instance, rng)` path without "
                "top-level `solve`, `run`, or `main` entrypoints. Multi-module "
                "changes are allowed when they remain inside this auditable call "
                "chain; put new construction seeds or initial-state hooks inside "
                "scheduler methods instead of changing the entrypoint call "
                "protocol."
            ),
            (
                "`context.nearest_neighbor()` takes no arguments and returns a "
                "public CvrpSolution; internal `_Solution.copy()` applies only "
                "to objects from baseline_modules/state.py."
            ),
            (
                "`_Solution` has no `from_routes`, `from_public`, "
                "`from_cvrp_solution`, or `to_public`. Do not add these bridge "
                "methods to state.py. Use construction.py helpers that already "
                "return internal `_Solution`, or construct `_Solution(instance, "
                "[_Route(instance, route) for route in routes])` and return via "
                "`context.make_solution(solution.routes_as_tuples())`."
            ),
            (
                "Do not use state.py as an additional-change adapter bridge "
                "unless it is the approved target; keep object-model edits "
                "explicit and auditable."
            ),
            (
                "Every search loop must have an explicit iteration/customer/route "
                "cap and should check `context.remaining_time()` (seconds), "
                "`context.remaining_time_ms()` (milliseconds), or "
                "`time_limit_sec` through the provided context. Do not compare "
                "`remaining_time()` directly to variables named or computed in "
                "milliseconds."
            ),
            (
                "Record movement evidence with `context.record_iteration`, "
                "`context.record_move`, phase timing, and "
                "`context.set_stop_reason` where the interface supports it. "
                "Search-bearing patches that produce zero iterations and zero "
                "move attempts on every smoke case will fail algorithm smoke."
            ),
            (
                "If the approved hypothesis declares mechanism telemetry, all "
                "activation/effect records must use the exact declared mechanism "
                "id. A telemetry-guard repair should add the missing record on "
                "the active path; it should not change the mechanism id or "
                "weaken the expected telemetry contract."
            ),
        ]
        if mode:
            lines.append(f"Current code-generation mode: `{mode}`.")
        if broad_terms:
            lines.append(
                "The approved hypothesis mentions broad mechanisms "
                f"({', '.join(dict.fromkeys(broad_terms))}). Reduce them to one "
                "executable path for this patch; do not implement a full "
                "portfolio."
            )
        scope = context.get("agentic_code_scope_control") if isinstance(context, Mapping) else None
        if isinstance(scope, Mapping) and scope.get("failure_detail"):
            lines.append(
                "Previous code generation timed out. Treat that as an instruction "
                "to shrink implementation breadth before adding algorithmic detail."
            )
        return tuple(lines)

    def solver_design_user_constraints(self, context: Any) -> Sequence[str]:
        return (
            (
                "For solver-design surfaces, return the complete contents of the "
                "target algorithm module. The active research object is "
                f"{_ACTIVE_SOLVER_DESIGN_PACKAGE}: use focused modules under "
                "`policies/baseline_modules/` for construction, destroy/repair, "
                "local search, acceptance, scheduler/runtime allocation, and "
                "telemetry, with `policies/baseline_algorithm.py::solve(...)` "
                "as the stable entrypoint."
            ),
            (
                "Deleted hooks, operator surfaces, and legacy component surfaces "
                "have been removed from the active research path. Do not select "
                "them as solver-design optimization targets."
            ),
            (
                "When the code-phase tool observations include support artifacts, "
                "use their `python_api_summary` and `content_preview` as the "
                "object model for sibling modules. In particular, read "
                "`policies/baseline_modules/state.py` before changing scheduler "
                "or local-search route edits."
            ),
            (
                "Use the `Solver-Design Module API Manifest` below as the exact "
                "branch-owned object model for sibling imports. If a name is not "
                "in that manifest and not defined by the same patch, do not "
                "import it."
            ),
            (
                "If the approved solver-design change requires more than one file "
                "to be executable, set the top-level `file_path` exactly to the "
                "approved `target_file` below and put scheduler/entrypoint/module "
                "integration edits in `additional_changes`. Do not make "
                "`policies/baseline_algorithm.py` the primary patch unless it is "
                "the approved target. Base each `additional_changes` file on the "
                "branch-current integration content provided below, and change "
                "only the minimal lines needed to call the approved mechanism. "
                "Do not leave a newly created helper or module inert."
            ),
            (
                "When adding class methods or helper functions, wire them into "
                "the active solver call path in the same patch. Static preview "
                "treats unreached methods and functions as inert, including "
                "methods added to helper classes such as acceptance schedules."
            ),
            "`additional_changes` must be a JSON array of objects, never a string containing JSON text.",
            (
                "Do not add new `instance.name`, `getattr(instance, 'name')`, or "
                "`hasattr(instance, 'name')` uses in solver-design code, even "
                "inside error messages. Use generic errors; case identity is "
                "outside the research surface boundary."
            ),
            (
                "Inside the `policies` package, use relative imports such as "
                "`from .baseline_modules.local_search import _vns` or "
                "`from .state import _Solution`. Do not import "
                "`policies.baseline_modules.*`; that path is outside the "
                "whitelist."
            ),
            (
                "`context.nearest_neighbor()` takes no arguments and returns a "
                "`CvrpSolution`; do not pass `rng` and do not call `.copy()` on "
                "that public solution. The internal `_Solution` type is separate "
                "and lives under `policies/baseline_modules/state.py`."
            ),
            (
                "Do not edit `policies/baseline_modules/state.py` as an "
                "`additional_changes` bridge unless it is the approved target; it "
                "is the branch object model, not an adapter escape hatch. Prefer "
                "using the construction/local_search/destroy_repair/scheduler "
                "APIs already declared by the support artifacts."
            ),
        )

    def is_runtime_patch_path(self, path: str | None) -> bool:
        normalized = str(path or "").replace("\\", "/").lstrip("/")
        return normalized == "policies/baseline_algorithm.py" or (
            normalized.startswith("policies/baseline_modules/")
            and normalized.endswith(".py")
        )

    def patch_claims_search_effort(
        self,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | None,
    ) -> bool:
        paths = set(_patch_paths(patch))
        if paths & {
            "policies/baseline_algorithm.py",
            "policies/baseline_modules/scheduler.py",
            "policies/baseline_modules/local_search.py",
            "policies/baseline_modules/destroy_repair.py",
            "policies/baseline_modules/acceptance.py",
        }:
            return True
        text_parts = []
        if hypothesis is not None:
            for name in (
                "hypothesis_text",
                "target_weakness",
                "expected_effect",
                "runtime_budget_strategy",
                "target_runtime_effect",
            ):
                value = getattr(hypothesis, name, None)
                if value:
                    text_parts.append(str(value))
        text = " ".join(text_parts).lower()
        if not text:
            return False
        search_terms = (
            "alns",
            "vns",
            "search",
            "local",
            "move",
            "operator",
            "destroy",
            "repair",
            "acceptance",
            "anneal",
            "scheduler",
        )
        return any(term in text for term in search_terms)

    def zero_effort_issue(
        self,
        *,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | None,
        runs: Sequence[Mapping[str, Any]],
    ) -> str | None:
        if not self.patch_claims_search_effort(patch, hypothesis):
            return None
        successful = [
            run
            for run in runs
            if run.get("passed") is True and isinstance(run.get("runtime"), Mapping)
        ]
        if not successful:
            return None
        zero_effort = []
        for run in successful:
            runtime = run.get("runtime")
            if not isinstance(runtime, Mapping):
                continue
            iterations = _nonnegative_int(
                runtime.get("solver_algorithm_search_iterations")
            )
            attempts = _nonnegative_int(runtime.get("solver_algorithm_move_attempts"))
            if iterations == 0 and attempts == 0:
                zero_effort.append(run)
        if len(zero_effort) != len(successful):
            return None
        targets = ", ".join(_patch_paths(patch))
        return (
            "solver_design smoke observed zero active search effort on all "
            f"{len(successful)} successful smoke case(s): "
            "solver_algorithm_search_iterations=0 and "
            "solver_algorithm_move_attempts=0. This candidate touches or claims "
            f"search-bearing solver code ({targets}) but behaves like a "
            "construction/wrapper-only path. Wire the changed mechanism into the "
            "active ALNS/VNS/search loop, record real iterations or moves, or "
            "retarget the hypothesis as a bounded construction-only algorithm "
            "with explicit telemetry."
        )

    def low_effort_issue(
        self,
        *,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | None,
        runs: Sequence[Mapping[str, Any]],
        micro_results: Sequence[Mapping[str, Any]],
    ) -> str | None:
        if not self.patch_claims_search_effort(patch, hypothesis):
            return None
        successful = [
            run
            for run in runs
            if run.get("passed") is True and isinstance(run.get("runtime"), Mapping)
        ]
        if len(successful) < _LOW_EFFORT_MIN_CASES:
            return None
        if any(result.get("comparison") == "win" for result in micro_results):
            return None

        micro_by_case_seed = {
            (str(result.get("case") or ""), _nonnegative_int(result.get("seed"))): result
            for result in micro_results
        }
        low_effort: list[dict[str, Any]] = []
        for run in successful:
            runtime = run.get("runtime")
            if not isinstance(runtime, Mapping):
                continue
            iterations = _nonnegative_int(
                runtime.get("solver_algorithm_search_iterations")
            )
            attempts = _nonnegative_int(runtime.get("solver_algorithm_move_attempts"))
            stop_reason = _runtime_stop_reason(
                runtime.get("solver_algorithm_stop_reason")
            )
            if iterations > _LOW_EFFORT_MAX_ITERATIONS:
                continue
            if attempts > _LOW_EFFORT_MAX_ATTEMPTS:
                continue
            if stop_reason not in _LOW_EFFORT_STOP_REASONS:
                continue
            if not _runtime_underspent(run, micro_by_case_seed=micro_by_case_seed):
                continue
            low_effort.append(
                {
                    "case": run.get("case"),
                    "seed": run.get("seed"),
                    "iterations": iterations,
                    "attempts": attempts,
                    "stop_reason": stop_reason,
                }
            )

        if len(low_effort) != len(successful):
            return None
        targets = ", ".join(_patch_paths(patch))
        return (
            "solver_design smoke observed low active search effort on all "
            f"{len(successful)} successful smoke case(s): each run stopped with "
            f"{sorted(_LOW_EFFORT_STOP_REASONS)} after at most "
            f"{_LOW_EFFORT_MAX_ITERATIONS} search iteration(s) and "
            f"{_LOW_EFFORT_MAX_ATTEMPTS} move attempt(s), while using only a "
            "small fraction of the smoke/champion runtime and producing no "
            "smoke micro-benchmark win. This candidate touches or claims "
            f"search-bearing solver code ({targets}) but appears to truncate "
            "the active ALNS/VNS/search loop. Keep real search budget and "
            "telemetry, or retarget the hypothesis as a bounded "
            "construction/runtime-speed change that does not claim search "
            "improvement."
        )

    def runtime_smoke_repair_guidance(
        self,
        audit_failure: Mapping[str, Any],
        *,
        runtime: Any,
        run_payload: Any,
    ) -> Sequence[str]:
        if audit_failure.get("error_category") != "solver_algorithm_runtime_error":
            return ()
        events = audit_failure.get("solver_algorithm_events")
        text = " ".join(
            str(part)
            for part in (
                audit_failure.get("detail"),
                audit_failure.get("error_category"),
                events,
                run_payload.get("detail") if isinstance(run_payload, Mapping) else None,
            )
            if part not in (None, "", [], {})
        )
        guidance = [
            "Failure occurred inside the candidate solver_design solve path during tainted algorithm smoke; repair the candidate algorithm code, not protocol or adapter files.",
            "Use the current CVRP object model: _Solution has .instance, .routes, .total_cost, .copy(), .rebuild_index(), .remove_empty_routes(), .is_feasible(), and .routes_as_tuples(); it does not expose ._instance.",
            "_Solution.routes contains _Route objects. A _Route has .customers, .load, .cost, .insert(), .remove(), .can_insert(), .cost_of_insert(), .cost_of_remove(), and .recalculate(); do not treat routes as plain customer lists unless you explicitly use route.customers.",
            "CvrpInstance.distance(i, j), demand(i), route_load(route), and route_distance(route) use integer node/customer ids; keep depot/customer ids explicit and rebuild solution indexes after direct route edits.",
        ]
        if "_Solution' object has no attribute '_instance'" in text:
            guidance.insert(
                1,
                "Specific fix: replace solution._instance with solution.instance; only _Route carries the private _instance slot.",
            )
        if "int' object has no attribute 'distance'" in text or '".distance"' in text:
            guidance.insert(
                1,
                "Specific fix: do not call .distance on an int, route, or customer id; call instance.distance(prev_id, next_id).",
            )
        if runtime in (None, {}, ""):
            guidance.append(
                "Runtime payload was missing or empty; first make solve(...) return a valid _Solution and context telemetry before adding new search breadth."
            )
        return tuple(guidance[:6])


def _runtime_underspent(
    run: Mapping[str, Any],
    *,
    micro_by_case_seed: Mapping[tuple[str, int], Mapping[str, Any]],
) -> bool:
    elapsed = _nonnegative_int((run.get("run") or {}).get("elapsed_ms"))
    runtime = run.get("runtime")
    solver_elapsed = 0
    if isinstance(runtime, Mapping):
        solver_elapsed = _nonnegative_int(runtime.get("solver_algorithm_elapsed_ms"))
    candidate_elapsed = elapsed or solver_elapsed
    if candidate_elapsed <= 0:
        return False

    key = (str(run.get("case") or ""), _nonnegative_int(run.get("seed")))
    micro = micro_by_case_seed.get(key)
    if isinstance(micro, Mapping):
        champion_elapsed = _nonnegative_int(micro.get("champion_elapsed_ms"))
        if champion_elapsed > 0:
            return candidate_elapsed / champion_elapsed <= _LOW_EFFORT_MAX_RUNTIME_RATIO
    return candidate_elapsed <= int(
        _SMOKE_TIME_LIMIT_SEC * 1000 * _LOW_EFFORT_MAX_RUNTIME_RATIO
    )


def _patch_paths(patch: PatchProposal) -> list[str]:
    paths: list[str] = []
    for change in patch_file_changes(patch):
        try:
            path = normalize_relative_patch_path(change.file_path)
        except ValueError:
            path = str(change.file_path or "")
        if path:
            paths.append(path)
    return paths


def _runtime_stop_reason(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text or "unknown"


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


__all__ = ["CvrpSolverDesignProvider"]
