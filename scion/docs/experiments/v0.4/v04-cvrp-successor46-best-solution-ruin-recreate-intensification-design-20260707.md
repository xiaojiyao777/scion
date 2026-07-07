# v0.4 CVRP successor46 best-solution ruin/recreate intensification design

Date: 2026-07-07

## Status

Prepared target intent for the next short validation run.

Successor46 mechanism id: `best_solution_ruin_recreate_intensification`

Target boundary:

- Primary module: `scion/problems/cvrp/policies/baseline_modules/best_solution_intensification.py`
- Wiring only: `scion/problems/cvrp/policies/baseline_modules/scheduler.py`
- Generic core: no changes

## Design intent

Successor45 proved that local pre-VNS repair-placement gains can activate while
still degrading final protocol outcome. Successor46 changes the causal path: it
starts from the current global-best incumbent, not the current post-destroy
candidate, and it records effect only when a bounded ruin/recreate plus
downstream VNS attempt strictly improves the final global best `total_distance`.

This is a CVRP-owned intensification mechanism. It is not a destroy-shadow
selector, repair-operator selector, repair-placement tournament, removal rule,
route-memory repair, route-skeleton repair, local-search move, construction seed
selector, acceptance guard, adaptive-weighting change, or runtime-allocation
policy.

## Required behavior

The candidate implementation should be one coherent CVRP module with a small
typed interface used by the scheduler. Avoid spreading behavior across many
small helper functions or generic layers.

The scheduler may call the module only after all of these conditions are true:

- A feasible global-best incumbent exists.
- The search has stalled for a bounded number of iterations without global-best
  improvement.
- Enough wall-clock budget remains to run one bounded attempt and either run
  downstream VNS or explicitly record a budget stop.

Each attempt must:

- Copy the current global best before mutation.
- Remove a bounded number of customers using a CVRP-owned ruin rule.
- Reinsert all removed customers with an existing feasible repair path or a
  compact local policy inside the module.
- Run downstream VNS when budget allows.
- Accept the mechanism effect only if the post-VNS candidate is feasible,
  route-count safe, and strictly improves global-best `total_distance`.
- Preserve or restore the main stochastic trajectory for rejected alternate
  attempts, or emit an explicit RNG/trajectory caveat.

## Required evidence

The postrun must report:

- `best_solution_ruin_recreate_intensification` attempted count
- accepted count
- rejected or budget-stopped count
- final post-VNS global-best `total_distance` delta
- accepted/new-best attribution
- runtime budget fields
- feasibility and route-count preservation
- CMT2/CMT4 case-level deltas or explicit split caveat

Pre-VNS repair deltas are allowed only as diagnostics. They are not promotion
evidence for this mechanism.

## Material difference

`material_difference.changed_dimensions`:

- start from current global-best incumbent
- trigger after bounded stagnation
- evaluate after downstream VNS
- record only final global-best movement
- isolate rejected-attempt trajectory effects

`material_difference.contrast`:

The mechanism does not choose among destroy operators, repair operators, repair
placements, construction seeds, local-search moves, acceptance outcomes, or
runtime-allocation schedules. It creates one bounded best-incumbent
intensification attempt and only accepts a final best improvement.

`material_difference.evidence`:

Promotion discussion requires final per-case `total_distance` evidence,
protected CMT2/CMT4 evidence, feasibility/route-count evidence, and direct
attempt/accepted/new-best telemetry for the mechanism id.

## Validation plan

Run a two-round server-local gpt-5.5 screening first. Treat the result as noisy
screening evidence only. Continue to longer validation only if the mechanism is
valid, active, and shows final best-solution improvement without CMT2/CMT4
regression.
