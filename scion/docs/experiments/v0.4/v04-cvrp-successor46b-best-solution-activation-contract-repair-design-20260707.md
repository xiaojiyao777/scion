# v0.4 CVRP successor46b best-solution activation contract repair design

Date: 2026-07-07

## Status

Prepared target intent for the next short validation run.

Successor46b mechanism id:

`best_solution_ruin_recreate_intensification_activation_repair`

Target boundary:

- Primary module: `scion/problems/cvrp/policies/baseline_modules/best_solution_intensification.py`
- Wiring only: `scion/problems/cvrp/policies/baseline_modules/scheduler.py`
- Generic core: no changes

## Why This Follow-Up Is Allowed

Successor46 was a valid target-bound run, not an infrastructure failure. The
hypothesis was coherent and the v3 boundary was right, but the generated
candidate did not satisfy the design contract:

- rejected attempts consumed the main RNG stream;
- the stagnation trigger was too sparse to evaluate;
- outcome telemetry did not separate reject causes;
- CMT2/CMT4 coverage was protocol-level only, not mechanism-level activation
  evidence.

This follow-up is therefore a contract/activation repair. It must not become a
general threshold-tuning exercise, a new destroy/repair selector, or a broader
solver rewrite. If it still shows zero final best-solution objective effect,
the best-solution ruin/recreate line is parked for v0.4.

## Required Behavior

Keep one coherent CVRP-owned module. Do not spread behavior across many helper
functions or generic layers.

The scheduler may call the module only when all of these are true:

- a feasible global-best incumbent exists;
- a bounded stagnation condition has occurred;
- enough wall-clock budget remains for one bounded attempt;
- the call cadence can be observed in short screening without case/seed
  hardcoding.

Each attempt must:

- copy the current global-best solution before mutation;
- use a child RNG or save and restore the main RNG state when the attempt is
  rejected;
- apply one bounded ruin/recreate attempt from the copied best solution;
- run downstream VNS when budget allows;
- accept only when the post-VNS candidate is feasible, route-count safe, and
  strictly improves the current global best `total_distance`;
- leave `current` and `best` unchanged on reject except for explicit telemetry.

## Required Evidence

The candidate must record mechanism-owned telemetry for:

- attempted attempts;
- accepted attempts;
- `rejected_no_improvement`;
- `rejected_infeasible`;
- `rejected_route_count`;
- `budget_stopped`;
- final post-VNS candidate-vs-best `total_distance` delta;
- accepted/new-best attribution;
- runtime phase and remaining-budget status;
- CMT2/CMT4 mechanism activation, or an explicit mechanism-level caveat.

Pre-VNS repair or local ruin/recreate deltas may be diagnostic only. They are
not promotion-grade solver evidence.

## Material Difference

`material_difference.changed_dimensions`:

- preserve successor46's best-incumbent ruin/recreate causal path;
- repair rejected-attempt RNG isolation;
- repair activation density enough to make the mechanism observable;
- repair outcome telemetry so zero effect can be interpreted;
- require mechanism-level CMT2/CMT4 activation evidence or an explicit caveat.

`material_difference.contrast`:

This is not a destroy-shadow selector, repair-placement tournament,
repair-operator selector, route-memory repair, route-skeleton repair,
local-search move, seed selector, acceptance gate, adaptive weighting change,
or runtime-allocation policy. It is also not an unchanged successor46 rerun.

`material_difference.evidence`:

Promotion discussion requires final per-case `total_distance` evidence,
post-VNS best-solution improvement evidence, rejected-attempt RNG isolation
evidence, outcome-cause telemetry, feasibility/route-count preservation, and
CMT2/CMT4 protected-case evidence.

## Validation Plan

Run a two-round server-local `gpt-5.5` screen first. Continue only if the
mechanism activates on measured cases, isolates rejected stochastic trajectory,
and produces nonzero final global-best objective effect without CMT2/CMT4
regression. Otherwise park this line and clean-fork to a materially different
CVRP-owned causal path.
