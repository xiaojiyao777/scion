# CVRP successor36 seed-post selector activation design

Date: 2026-07-05

## Context

Successor35 completed valid/complete/postrun-ready but was solver-negative:
`capacity_tightness_removal` activated in both screening rows, yet medians were
`-6.0` and `-3.5`, with `rows_at_or_above_mde=0` and CMT2 negative in both
rows. Unchanged capacity-tight removal is now reviewed/default-avoid.

The remaining useful CVRP move is not to retune gates or repeat another
destroy/removal variant by inertia. The least stale open mechanism is
`seed_post_optimization_selector`: successor16/17 did not produce
evidence-complete negative solver results; they exposed inactive or missing
mechanism telemetry.

## Direction

Mechanism id:
`seed_post_optimization_selector`

Mechanism family:
`construction_seed_portfolio`

Primary new module:
`policies/baseline_modules/seed_selector.py`

Minimal integration file:
`policies/baseline_modules/scheduler.py`

Target launch shape:

- `--force-surface solver_design`
- `--force-action create_new`
- `--force-target-file policies/baseline_modules/seed_selector.py`

The code prompt supports this boundary: the new module can be created as the
top-level target, and existing scheduler wiring can appear as typed
`additional_changes` with small `exact_replace` edits.

## Causal Path

The mechanism is a post-construction selector, not a generic seed portfolio:

1. Build the normal baseline initial solution.
2. Build one or more bounded alternate initial or post-construction seeds using
   existing CVRP-owned construction operations.
3. Compare feasible candidate seeds against the baseline before downstream
   ALNS/VNS.
4. Select the best feasible candidate only when it improves initial total
   distance without violating route feasibility or route-count constraints.
5. Record the direct selected-seed-versus-baseline delta before downstream
   search can confound attribution.

The solver effect claim must be the pre-ALNS/VNS selector effect. Later ALNS or
embedded-VNS movement is downstream evidence, not the selector's direct
mechanism evidence.

## Module Boundary

`seed_selector.py` should own a cohesive operation such as:

```text
select_post_construction_seed(solution, instance, context, reserve, max_routes)
```

It may contain small local routines needed to rank candidate seeds, but should
not become a bag of unrelated construction helpers. Scheduler wiring should do
only the construction-boundary call and keep existing ALNS/VNS, q scheduling,
embedded-VNS runtime allocation, simulated-annealing acceptance, destroy/repair
operators, and operator-credit logic unchanged.

## Non-goals

- Do not repeat unchanged `granular_savings_seed_portfolio`.
- Do not repeat unchanged `cw_sweep_seed_baseline_selector`.
- Do not repeat unchanged `short_horizon_seed_trajectory_selector`.
- Do not change generic core, DecisionFeatures, protocol gates, promotion
  thresholds, or measurement declarations.
- Do not hardcode case ids, BKS values, seeds, split membership, CMT2/CMT4,
  or reference objectives.
- Do not claim activation alone as solver effect.

## Telemetry Contract

Required telemetry under `seed_post_optimization_selector`:

- `context.record_iteration("seed_post_optimization_selector", 1)`
- `context.record_phase("seed_post_optimization_selector", elapsed_ms)`
- `context.record_move("seed_post_optimization_selector", attempted=1,
  accepted=..., delta=selected_seed_vs_baseline_delta, best_improved=...)`

The direct delta is:

```text
selected_seed_vs_baseline_delta =
  baseline_initial_total_distance - selected_initial_total_distance
```

If no feasible alternate seed improves the baseline, record attempted
telemetry, `accepted=0`, and a nonpositive direct delta. A row with missing
mechanism activation/effect telemetry is an activation-repair failure, not a
solver-negative measurement.

## Acceptance Reading

Minimum evidence before interpretation:

- live target-intent and formal hypothesis name
  `seed_post_optimization_selector`;
- target action is `create_new` for `seed_selector.py`;
- scheduler edits are limited integration edits;
- formal screening completes without proposal quality, model, telemetry, or
  postrun readiness failures;
- direct pre-ALNS/VNS selected-seed-versus-baseline objective delta is present;
- per-case total_distance, feasibility, route count, and runtime evidence are
  visible;
- CMT2/CMT4 case deltas are visible in postrun interpretation.

Outcome classification:

- `solver-positive-at-MDE`: at least one formal row reaches MDE with no
  unresolved protected-case regression.
- `evidence-complete below-MDE`: activation and direct effect telemetry are
  present, but no row reaches MDE.
- `inactive repair failure`: mechanism id remains absent from activation or
  direct-effect telemetry.
- `quality regression`: aggregate or protected-case losses dominate.
- `infra invalid`: run validity or postrun readiness fails for infrastructure
  reasons.
