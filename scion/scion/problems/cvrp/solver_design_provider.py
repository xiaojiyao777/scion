"""CVRP-owned solver-design prompt and smoke interpretation hooks."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from scion.core.models import HypothesisProposal, PatchProposal
from scion.problems.cvrp.solver_design.manifest import (
    ACTIVE_SOLVER_DESIGN_PACKAGE,
    BROAD_SCOPE_TERMS,
    SOLVER_DESIGN_API_MANIFEST_FILES,
    SOLVER_DESIGN_INTEGRATION_FULL_FILES,
    SOLVER_DESIGN_INTEGRATION_SUMMARY_FILES,
)
from scion.problems.cvrp.solver_design.smoke import (
    is_runtime_patch_path as _is_runtime_patch_path,
    low_effort_issue as _low_effort_issue,
    patch_claims_search_effort as _patch_claims_search_effort,
    runtime_smoke_repair_guidance as _runtime_smoke_repair_guidance,
    static_smoke_issue as _static_smoke_issue,
    zero_effort_issue as _zero_effort_issue,
)


class CvrpSolverDesignProvider:
    """Problem-owned guidance for CVRP solver-design proposal tooling."""

    def solver_design_broad_scope_terms(self) -> Sequence[str]:
        return BROAD_SCOPE_TERMS

    def solver_design_api_manifest_files(self) -> Sequence[str]:
        return SOLVER_DESIGN_API_MANIFEST_FILES

    def solver_design_integration_full_files(self) -> Sequence[str]:
        return SOLVER_DESIGN_INTEGRATION_FULL_FILES

    def solver_design_integration_summary_files(self) -> Sequence[str]:
        return SOLVER_DESIGN_INTEGRATION_SUMMARY_FILES

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
                "those categories, never as top-level expected_telemetry keys. "
                "Values must be exact runtime field strings, not explanations."
            ),
            (
                "When declaring mechanism id `m`, use these concrete telemetry "
                "templates with `m` substituted by default: activation includes "
                "`solver_algorithm_context_records.m_iterations` and "
                "`solver_algorithm_phase_runtime_ms.m`; budget may include "
                "`solver_algorithm_phase_runtime_ms.m`; activity/context "
                "evidence may use the same mechanism-specific context record. "
                "Declare effect fields such as "
                "`solver_algorithm_phase_improvement_counts.m` or "
                "`solver_algorithm_phase_best_delta.m` only when `m` directly "
                "records an accepted or improving move. In code, create "
                "`solver_algorithm_context_records.m_iterations` with "
                "`context.record_iteration('m', count)`, not a "
                "`record_context` helper."
            ),
            (
                "For scheduler-policy or acceptance-temperature mechanisms, "
                "do not claim ordinary ALNS best-improvement bookkeeping as a "
                "direct mechanism effect. Prefer activation/budget/decision "
                "evidence under the declared mechanism id, such as a mechanism "
                "context-record counter and phase runtime, and declare "
                "delta-valued effect fields only when the mechanism records a "
                "directly attributable accepted or improving decision."
            ),
            (
                "If the hypothesis modifies an existing ALNS/VNS phase rather "
                "than adding a brand-new operator, still declare the changed "
                "lever as a specific mechanism id such as "
                "`adaptive_destroy_schedule` or `vns_operator_scheduler`, then "
                "use that same id in expected_telemetry. Do not declare one id "
                "and point activation/effect/budget at generic `.alns` or "
                "`.vns` phase buckets."
            ),
            (
                "Active solver invariant: initial construction is route-limit "
                "guarded (`_capacity_balanced_construction` is used when the "
                "route cap is exceeded, and `_initial_solution` fails closed if "
                "routes still exceed `max_routes`). The ALNS loop also rejects "
                "route-cap-violating candidates before they become current "
                "search state. Do not target construction/ALNS fleet_violation "
                "repair or route-limit excess as the default bottleneck unless "
                "prior screening/runtime feedback explicitly shows positive "
                "fleet_violation or route-limit excess."
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
                f"{ACTIVE_SOLVER_DESIGN_PACKAGE}. Deleted legacy hooks are "
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

    def solver_design_expected_telemetry_preview(
        self,
        hypothesis: HypothesisProposal,
    ) -> Mapping[str, Any] | None:
        """Return CVRP-specific expected-telemetry preview guidance."""
        mechanisms = _mechanism_ids(hypothesis)
        if not mechanisms:
            return None
        expected = getattr(hypothesis, "expected_telemetry", {}) or {}
        if not isinstance(expected, Mapping):
            return None
        effect_fields = tuple(
            str(field or "").strip()
            for field in expected.get("effect", ()) or ()
            if str(field or "").strip()
        )
        if not effect_fields:
            return None
        issues: list[Mapping[str, Any]] = []
        for mechanism in mechanisms:
            if not _is_indirect_policy_mechanism(hypothesis, mechanism):
                continue
            offending = [
                field
                for field in effect_fields
                if mechanism in field and _is_broad_loop_objective_effect_field(field)
            ]
            if not offending:
                continue
            issues.append(
                {
                    "failure_code": "C11_expected_telemetry",
                    "mechanism_id": mechanism,
                    "offending_fields": offending[:4],
                    "allowed_repair_shape": (
                        "Declare activation, budget, or decision/context "
                        "evidence under the same mechanism id."
                    ),
                    "forbidden_repair_shape": (
                        "Do not claim ordinary ALNS best-improvement, "
                        "best_delta, or improvement_counts bookkeeping as a "
                        "direct effect of this policy mechanism."
                    ),
                }
            )
        if not issues:
            return None
        first = issues[0]
        return {
            "passed": False,
            "failure_code": "C11_expected_telemetry",
            "reason": (
                "C11_expected_telemetry: indirect acceptance/temperature/"
                "stagnation policy telemetry must use decision, activation, "
                "or budget evidence instead of broad-loop objective effect."
            ),
            "issues": issues,
            "repair_hint": (
                "Redraft the same hypothesis before code: keep target_file and "
                "mechanism_changes ids unchanged, remove the offending effect "
                "field(s), and use mechanism-specific decision/context, "
                "activation, or budget telemetry."
            ),
            "mechanism_id": first.get("mechanism_id"),
            "offending_fields": first.get("offending_fields"),
            "allowed_repair_shape": first.get("allowed_repair_shape"),
            "forbidden_repair_shape": first.get("forbidden_repair_shape"),
        }

    def solver_design_code_rules(self, context: Any) -> Sequence[str]:
        return (
            (
                "The active solver_design research object is "
                f"{ACTIVE_SOLVER_DESIGN_PACKAGE}. Legacy component surfaces "
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
                "branch-owned algorithm-module change with typed edits and "
                "integrate with the existing entrypoint; do not add a top-level "
                "`solve` unless the target module already owns one."
            ),
            (
                "The internal `_Solution` and `_Route` classes use `__slots__`; "
                "do not attach temporary attributes such as `solution._cache` or "
                "`route._memo`. Keep caches in local variables, pass them through "
                "helper arguments, or make an explicit approved state-model "
                "change."
            ),
            (
                "Default to a compact target-file change: one coherent construction "
                "or seeding path, one bounded improvement/search loop, no more "
                "than two move families, and only the helper functions needed for "
                "that path."
            ),
            (
                "Typed edit advisory: for existing files, prefer function-level "
                "or small block `exact_replace` edits. If a broad change is "
                "needed, create focused helpers and wire them with small "
                "integration edits instead of replacing most of a source file."
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
                "a detached scheduler `_run`/`run` entrypoint to call them, and "
                "do not store temporary search state on `_Solution` with "
                "private dynamic attributes."
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
                "For scheduler-policy and acceptance-temperature mechanisms, "
                "record decision/activation counters with "
                "`context.record_iteration('<mechanism>', count)` plus "
                "`context.record_phase('<mechanism>', elapsed_ms)`. These calls "
                "populate `solver_algorithm_context_records.<mechanism>_iterations` "
                "and `solver_algorithm_phase_runtime_ms.<mechanism>`; there is "
                "no `context.record_context` API. Only call "
                "`context.record_move('<mechanism>', delta=..., best_improved=1)` "
                "when that mechanism directly caused an accepted or improving "
                "candidate; ordinary scheduler best-improvement bookkeeping is "
                "not causal acceptance effect evidence."
            ),
            (
                "For ALNS/VNS phase modifications, instrument the declared "
                "mechanism id for the modified lever, not the broad phase name. "
                "For example, if the mechanism id is `vns_operator_scheduler`, "
                "record `context.record_phase('vns_operator_scheduler', ...)` "
                "or matching context records; do not rely on an existing `vns` "
                "or `alns` aggregate phase bucket to satisfy that declaration."
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
                f"{ACTIVE_SOLVER_DESIGN_PACKAGE}. "
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
                "Hard size target: keep the target-file change around 180 lines "
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
                "`_Solution` and `_Route` use `__slots__`; do not add dynamic "
                "private attributes like `solution._nn_lists`. Keep temporary "
                "candidate lists, route caches, and telemetry state in local "
                "variables or pass them as helper parameters."
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
                "`context.record_phase(name, elapsed_ms)` expects a duration "
                "delta for that phase. Do not pass cumulative "
                "`context.elapsed_ms()` directly inside repeated helper calls; "
                "use `phase_start = context.elapsed_ms()` and record "
                "`context.elapsed_ms() - phase_start`."
            ),
            (
                "Use the exact telemetry helper signatures: "
                "`context.record_phase(name, elapsed_ms)`, "
                "`context.record_iteration(phase='search', count=1)`, and "
                "`context.record_move(phase='search', attempted=1, accepted=0, "
                "delta=None, best_improved=0)`. Do not pass arbitrary keyword "
                "arguments such as `extra=...`."
            ),
            (
                "If the approved hypothesis declares mechanism telemetry, all "
                "activation/effect records must use the exact declared mechanism "
                "id. A telemetry-guard repair should add the missing record on "
                "the active path while preserving records that already passed; "
                "it should not change the mechanism id, replace activation with "
                "effect evidence, or weaken the expected telemetry contract."
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
        if isinstance(scope, Mapping) and scope.get("telemetry_obligation_rule"):
            lines.append(str(scope["telemetry_obligation_rule"]))
        if isinstance(scope, Mapping) and scope.get("failure_detail"):
            lines.append(
                "Previous code generation timed out. Treat that as an instruction "
                "to shrink implementation breadth before adding algorithmic detail."
            )
        return tuple(lines)

    def solver_design_user_constraints(self, context: Any) -> Sequence[str]:
        return (
            (
                "For solver-design surfaces, keep the primary patch on the "
                "target algorithm module and default existing-file changes to "
                "typed `exact_replace` edits. The active research object is "
                f"{ACTIVE_SOLVER_DESIGN_PACKAGE}: use focused modules under "
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
                "`_Solution` and `_Route` are slotted state objects. Do not "
                "write private dynamic attributes such as `solution._cache`, "
                "`solution._nn_lists`, or `route._memo`; use function parameters "
                "or local variables for temporary search state."
            ),
            (
                "`context.record_phase(name, elapsed_ms)` records a per-phase "
                "duration delta. Never pass raw cumulative `context.elapsed_ms()` "
                "as the second argument in a loop or helper; compute a delta "
                "from a local phase_start."
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
        return _is_runtime_patch_path(path)

    def patch_claims_search_effort(
        self,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | None,
    ) -> bool:
        return _patch_claims_search_effort(patch, hypothesis)

    def solver_design_static_smoke_issue(
        self,
        *,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | None,
    ) -> str | None:
        return _static_smoke_issue(patch=patch, hypothesis=hypothesis)

    def zero_effort_issue(
        self,
        *,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | None,
        runs: Sequence[Mapping[str, Any]],
    ) -> str | None:
        return _zero_effort_issue(
            patch=patch,
            hypothesis=hypothesis,
            runs=runs,
        )

    def low_effort_issue(
        self,
        *,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | None,
        runs: Sequence[Mapping[str, Any]],
        micro_results: Sequence[Mapping[str, Any]],
    ) -> str | None:
        return _low_effort_issue(
            patch=patch,
            hypothesis=hypothesis,
            runs=runs,
            micro_results=micro_results,
        )

    def runtime_smoke_repair_guidance(
        self,
        audit_failure: Mapping[str, Any],
        *,
        runtime: Any,
        run_payload: Any,
    ) -> Sequence[str]:
        return _runtime_smoke_repair_guidance(
            audit_failure,
            runtime=runtime,
            run_payload=run_payload,
        )


def _mechanism_ids(hypothesis: HypothesisProposal | None) -> tuple[str, ...]:
    if hypothesis is None:
        return ()
    result: list[str] = []
    for change in getattr(hypothesis, "mechanism_changes", ()) or ():
        value = str(getattr(change, "id", "") or "").strip()
        if value:
            result.append(value)
    return tuple(dict.fromkeys(result))


def _is_indirect_policy_mechanism(
    hypothesis: HypothesisProposal,
    mechanism: str,
) -> bool:
    mechanism_text = _normalize_text(mechanism)
    target = str(getattr(hypothesis, "target_file", "") or "").replace("\\", "/")
    if target.endswith(
        (
            "policies/baseline_modules/local_search.py",
            "policies/baseline_modules/destroy_repair.py",
        )
    ) and not _has_any(
        mechanism_text,
        (
            " accept ",
            " acceptance ",
            " temperature ",
            " anneal ",
            " simulated annealing ",
            " reheat ",
            " cooling ",
        ),
    ):
        return False
    novelty_signature = getattr(hypothesis, "novelty_signature", {}) or {}
    acceptance_strategy = ""
    if isinstance(novelty_signature, Mapping):
        acceptance_strategy = str(novelty_signature.get("acceptance_strategy") or "")
    if _is_preserve_existing_strategy(acceptance_strategy):
        acceptance_strategy = ""
    text = _normalize_text(
        " ".join(
            (
                mechanism,
                str(getattr(hypothesis, "target_file", "") or ""),
                str(getattr(hypothesis, "target_weakness", "") or ""),
                str(getattr(hypothesis, "target_runtime_effect", "") or ""),
                str(getattr(hypothesis, "runtime_budget_strategy", "") or ""),
                acceptance_strategy,
            )
        )
    )
    if _has_any(
        text,
        (
            " accept ",
            " acceptance ",
            " temperature ",
            " anneal ",
            " simulated annealing ",
            " reheat ",
            " cooling ",
        ),
    ):
        return True
    return _has_any(
        text,
        (
            " conditional policy ",
            " condition policy ",
            " stagnation policy ",
            " triggered policy ",
        ),
    )


def _is_preserve_existing_strategy(value: str) -> bool:
    text = _normalize_text(value)
    if not text:
        return True
    preserve_tokens = (
        " preserve ",
        " existing ",
        " unchanged ",
        " no change ",
        " keep ",
        " reuse ",
    )
    return _has_any(text, preserve_tokens) and not _has_any(
        text,
        (
            " reheat ",
            " cooling ",
            " temperature ",
            " anneal ",
            " simulated annealing ",
        ),
    )


def _is_broad_loop_objective_effect_field(field: str) -> bool:
    text = _normalize_text(field)
    return _has_any(
        text,
        (
            " best delta ",
            " phase best delta ",
            " improvement counts ",
            " delta sum ",
            " objective delta ",
        ),
    )


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _normalize_text(value: Any) -> str:
    text = str(value or "").lower().replace("_", " ")
    text = re.sub(r"[-./]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return f" {text} "


__all__ = ["CvrpSolverDesignProvider"]
