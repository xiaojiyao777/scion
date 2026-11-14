# Successor55 bounded elite solution-pool design

Date: 2026-07-12

## Objective

Successor55 tests whether the current single-trajectory ALNS+VNS search state is
the limiting factor. The mechanism is `bounded_elite_solution_pool_search`: a
CVRP-owned bounded pool of feasible, diverse solution snapshots that can become
future search anchors after stagnation.

This is a materially different search-state clean fork. It is not a protected
race/selector follow-up, route-pool exact-cover continuation, seed selector,
destroy/removal rule, local-search move, route-first configuration flip, or a
contract/helper-only change.

## Architecture boundary

- Add `policies/baseline_modules/solution_pool.py` as the complete owner of pool
  entries, admission, capacity, diversity, anchor selection, and pool telemetry.
- Limit `policies/baseline_modules/scheduler.py` to pool initialization, offering
  accepted/current/best snapshots, and applying an anchor switch at a bounded
  stagnation or periodic decision point.
- Preserve `policies/baseline_algorithm.py` as orchestration unless a narrow
  import or result-field connection is required.
- Do not add CVRP, route, ALNS, VNS, or successor semantics to generic Scion
  core, Contract, Verification, Protocol, DecisionFeatures, or shared adapters.
- Do not grow scheduler with free functions that duplicate pool policy. The
  module boundary, rather than helper accumulation, is part of the experiment.

## Mechanism contract

Each pool entry is an immutable solution snapshot with objective value, route
count, and a canonical diversity signature. Admission must:

1. accept only feasible candidates within the configured max-route constraint;
2. reject exact duplicates;
3. require either elite objective quality or useful route/edge diversity;
4. keep a small fixed capacity and deterministically evict the weakest or most
   redundant entry; and
5. never replace or weaken the scheduler's global `best` solution.

Anchor selection must be bounded and trajectory-changing. On a stagnation or
periodic trigger with cooldown, it selects a feasible pool entry that balances
objective quality and diversity from `current`, then replaces only `current`
with a copied snapshot. Selection and tie-breaking should be deterministic, or
use an isolated mechanism RNG, so rejected pool decisions do not perturb the
main destroy/repair RNG stream.

The pool should remain intentionally small, normally four to six entries. A
candidate that only records solutions without an observed anchor switch is
`not_triggered`, not evidence of algorithmic effect.

## Required evidence

- admission attempted, accepted, and rejected counts;
- rejection causes, including infeasible, route-count, duplicate, quality,
  diversity, and capacity decisions;
- anchor-switch attempted, accepted, and rejected counts;
- pool size, capacity, and trigger/cooldown or budget-stop state;
- pre-switch current objective and selected-anchor objective;
- final `total_distance` attribution after downstream ALNS/VNS, separated from
  local pool-selection deltas;
- feasibility and max-route preservation;
- CMT2 and CMT4 case-level deltas or an explicit split-coverage caveat.

## Failure criteria

Reject the successor55 implementation before solver interpretation if it:

- places pool policy in scheduler helpers instead of the owned module;
- changes generic Scion boundaries or DecisionFeatures;
- admits infeasible or route-count-invalid solutions;
- consumes the main search RNG during rejected pool decisions;
- reports pre-switch or pre-VNS deltas as final trajectory gains;
- leaves the mechanism inert without reporting `not_triggered`; or
- increases runtime without a bounded pool and bounded trigger policy.

## Validation plan

Run two agentic rounds on the server-local `claw` environment with local
`gpt-5.5`. This is a short screening experiment, so its result is used to check
implementation quality, mechanism activation, direct telemetry, and directional
signal. It is not sufficient by itself for promotion or long-run claims.

Launch label:

`v04-cvrp-successor55-bounded-elite-solution-pool-search-server-claw`
