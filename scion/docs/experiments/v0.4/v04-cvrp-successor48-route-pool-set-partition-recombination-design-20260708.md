# CVRP successor48 design: bounded route-pool set-partition recombination

Date: 2026-07-08

Mechanism id: `bounded_route_pool_set_partition_recombination`

Target boundary:

- Primary target: `policies/baseline_modules/route_pool_recombination.py`
- Minimal wiring: `policies/baseline_modules/scheduler.py`

## Purpose

Successor47 tested contiguous giant-tour split reconstruction. It was modular
and correctly target-bound, but direct split effect was nearly absent and
CMT2/CMT4 were negative. The next slot must not tune that route ordering or
repeat contiguous split DP.

Successor48 is a different CVRP-owned recombination path:

1. Build a small ephemeral route pool from complete feasible routes already
   seen inside the current run.
2. Select whole routes through a bounded exact-cover or beam set-partitioning
   subproblem.
3. Accept only a feasible route set that covers every customer exactly once,
   respects `max_routes`, and strictly improves final `total_distance`.

This is not persistent route memory. The pool is local to one solve call and
does not store cross-run state.

## Required Material Difference

The hypothesis must use exact `material_difference` keys:

- `changed_dimensions`
- `contrast`
- `evidence`

Required contrast:

- Not successor47 contiguous giant-tour split DP.
- Not `elite_route_memory_repair`, route skeleton regret repair, route
  fragment recombination repair, route-pair crossover, or route-pair overlap.
- Not construction seed selection, destroy/repair selector tuning,
  repair-placement tournament, acceptance guard, runtime allocation, or
  reviewed local-search swap/or-opt/3-opt/ejection-chain/two-for-one variants.
- Not unbounded large-instance two-opt fallback.

## Implementation Contract

The implementation must stay inside the CVRP solver-design subject.

- Add the mechanism in a new module, not as ad hoc code inside `scheduler.py`.
- Keep scheduler changes to minimal orchestration and route-snapshot feeding.
- Do not modify generic Scion core, protocol selection, DecisionFeatures,
  postrun acceptance, or measurement gates.
- Keep the route pool small and bounded by remaining time, route count, and
  customer count.
- Use only complete feasible routes from the current run; reject partial
  customer coverage, duplicate customer coverage, infeasible routes, and
  route-count regressions.
- Accept only strict `total_distance` improvement against the current best
  route set.

## Evidence Contract

Required telemetry:

- Activation iterations for
  `bounded_route_pool_set_partition_recombination`.
- Phase runtime for the mechanism.
- Route-pool size and source counts.
- Exact-cover candidate count.
- Attempted and accepted move counts.
- Rejected-no-cover, rejected-infeasible, rejected-route-count,
  rejected-no-improvement, and budget-stopped counts.
- Accepted set-partition `total_distance` delta.
- Feasibility and route-count preservation.
- CMT2/CMT4 priority-case outcome evidence.

If CMT2 or CMT4 activates the mechanism but loses, the postrun must treat that
as protected-case unsafe evidence, not as generic short-run noise.

## Launch Rule

Use a short server-local `claw` screening run first. Do not long-run unless
the short run has positive-at-MDE evidence or a defensible validation/frozen
path with protected-case safety.
