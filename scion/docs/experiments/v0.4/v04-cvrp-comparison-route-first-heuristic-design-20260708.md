# CVRP comparison design: route-first heuristic research object

Date: 2026-07-08

## Purpose

Recent CVRP successors have mostly changed local pieces of the active
ALNS+VNS solver and have not produced promotion-grade objective effect. This
comparison asks a different question:

Is the current ALNS+VNS baseline already close enough on the formal CVRP
surface that small operator changes have limited headroom, or is Scion failing
to find useful mechanisms inside a still-improvable solver family?

The comparison should add a separate CVRP-owned solver variant, not replace the
current champion by default.

## Boundary

This is a problem-owned CVRP solver-design comparison.

- Do not modify generic Scion core, protocol selection, measurement gates,
  DecisionFeatures, postrun acceptance, or `solver.py`.
- Keep the stable active algorithm entrypoint:
  `policies/baseline_algorithm.py::solve(instance, rng, time_limit_sec, context)`.
- Add behavior only under `policies/baseline_modules/`.
- Default runtime behavior must remain the current ALNS+VNS solver.

## Proposed Mechanism

Mechanism id: `route_first_heuristic_baseline`

Variant id: `route_first_heuristic`

The variant should be a complete alternative heuristic, not an ALNS+VNS
threshold tweak:

1. Generate route-first constructive starts from Clarke-Wright, sweep, and
   bounded rotated sweeps.
2. Repair route count through existing capacity-balanced construction when
   needed.
3. Apply deterministic bounded local improvement directly to each start,
   using time-guarded two-opt, relocate, swap, or or-opt primitives.
4. Choose the best feasible route set under the same CVRP objective and route
   cap.

The variant may reuse existing `state`, `construction`, and local-search
primitives, but it must not instantiate `_ALNSVNSSolver` or use ALNS adaptive
weights/simulated annealing as its main search.

## Minimal Code Shape

Recommended files:

- `policies/baseline_modules/config.py`
  - add `SOLVER_VARIANT = "alns_vns"` as the default;
  - add only a small number of route-first constants.
- `policies/baseline_algorithm.py`
  - dispatch on `SOLVER_VARIANT`;
  - default remains `_ALNSVNSSolver`.
- `policies/baseline_modules/route_first_heuristic.py`
  - own the solver object and orchestration.
- `policies/baseline_modules/route_first_seeding.py`
  - own construction starts: Clarke-Wright, rotated polar sweeps, capacity
    splits, and existing capacity/nearest-neighbor fallbacks.
- `policies/baseline_modules/route_first_improvement.py`
  - own bounded deterministic cleanup: two-opt, cross-route relocate, and
    cross-route swap under explicit pass/check budgets.

This keeps the comparison disabled in the champion while making it easy for a
Scion candidate patch to switch `SOLVER_VARIANT` to `route_first_heuristic`.
That candidate can then be evaluated against the existing ALNS+VNS champion by
the normal protocol.

Actual implementation status:

- Default `SOLVER_VARIANT = "alns_vns"` preserves the current champion.
- `route_first_heuristic` is implemented as the three-module package above and
  does not instantiate `_ALNSVNSSolver`, use ALNS adaptive weights, or call the
  embedded VNS controller.
- The prepared target-intent contract is problem-owned in
  `scion/problems/cvrp/research_guidance_route_first.py` and binds the next
  comparison to `route_first_heuristic_baseline`.
- The candidate comparison should only enable the existing variant through
  `policies/baseline_modules/config.py`; it should not generate another
  alternative algorithm unless this smoke path fails.

## Evidence Contract

Required runtime evidence for a candidate enabling this variant:

- `solver_algorithm_phase_runtime_ms.route_first_heuristic`
- `solver_algorithm_context_records.route_first_heuristic_iterations`
- `solver_algorithm_phase_move_attempts.route_first_heuristic`
- `solver_algorithm_phase_accepted_moves.route_first_heuristic`
- `solver_algorithm_phase_best_delta.route_first_heuristic`
- `solver_algorithm_phase_improvement_counts.route_first_heuristic`
- final `solver_algorithm_total_distance`
- final `solver_algorithm_solution_routes`
- `solver_algorithm_solution_progress`

The run must preserve feasibility and the route cap. CMT2/CMT4 outcomes remain
required protected-case evidence before any long-run interpretation.

## Experiment Rule

This is a comparison experiment, not a promotion shortcut.

First run a short server-local `claw` screening campaign where the live target
is enabling `route_first_heuristic_baseline`. Interpret outcomes as:

- If the route-first variant is clearly worse, that supports the idea that the
  current ALNS+VNS baseline is a strong local research object and the issue is
  mechanism discovery, not algorithm-family weakness.
- If the route-first variant is competitive or positive, it justifies a
  second-stage Scion research object around the route-first family.
- If the variant is noisy below MDE, inspect per-case structure before deciding
  whether the signal is algorithm-family headroom or short-run noise.

## Pre-Protocol Smoke

Direct local smoke is not protocol evidence. It only verifies that the
comparison variant is feasible, instrumented, and bounded before spending a
Scion campaign slot.

Observed smoke on 2026-07-08:

- Tiny workspace: default ALNS+VNS and route-first both returned feasible
  2-route solutions with total distance `8.0`; route-first emitted
  `route_first_heuristic` phase telemetry.
- Informal 5-second route-first runs were feasible and bounded on
  `P/P-n16-k8`, `A/A-n32-k5`, and `CMT/CMT2`.
- The same informal check showed route-first worse than ALNS+VNS on
  `A/A-n32-k5` and `CMT/CMT2`. Treat that as smoke context only, not a
  promotion or rejection decision.
