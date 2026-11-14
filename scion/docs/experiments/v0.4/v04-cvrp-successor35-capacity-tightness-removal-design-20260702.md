# CVRP successor35 capacity-tightness removal design

Date: 2026-07-02

## Context

Successor34 completed valid/complete/postrun-ready and repaired the frozen
timeout blocker from successor33, but it did not preserve enough objective
signal:

- best screening row: median delta `0.25`, CI `[0.0, 3.25]`;
- current CVRP screening MDE: `9.9`;
- CMT2 remained negative with median `-11.0`;
- no promotion, validation, or frozen row followed.

Unchanged neighbor-list VNS filtering is therefore reviewed weak-positive below
MDE, not a current promotion path. The next slot should not add another
local-search helper block or a same-mechanism protection layer.

## Recommended Direction

Mechanism id:
`capacity_tightness_removal`

Mechanism family:
`destroy_repair_selection`

Owner file:
`policies/baseline_modules/destroy_repair.py`

Preferred module boundary if the implementation grows:
`policies/baseline_modules/capacity_tightness.py`

The mechanism should add a destroy/removal operator that preferentially removes
customers from capacity-tight routes where the current route has low remaining
slack and the removed customer is likely to open useful repair choices.

The causal path is a removal-choice change, not a seed, local-search, scheduler,
runtime-allocation, acceptance, or operator-credit change.

## Design Constraints

- Keep construction seeds unchanged.
- Keep VNS/local-search neighborhoods unchanged.
- Keep scheduler q policy and embedded-VNS runtime allocation unchanged.
- Keep simulated-annealing acceptance and operator credit unchanged.
- Do not hardcode case ids, BKS values, seeds, split names, or protected-case
  membership.
- Preserve feasibility through existing repair operators.
- Bound scoring effort by current route/customer counts; do not add broad
  all-pairs helper growth.

## Scoring Shape

A simple acceptable implementation shape:

- compute route slack as `capacity - route.load`;
- prioritize routes with low nonnegative slack or high load ratio;
- within selected routes, score customers by demand, marginal removal saving,
  and insertion-pressure proxy;
- remove up to the requested `q`, with stochastic tie-breaking from the
  existing RNG;
- fall back to existing removal behavior only when no capacity-tight candidates
  exist.

If a separate module is introduced, it should own only capacity-tight scoring
and candidate ranking. `destroy_repair.py` should remain the integration layer.

## Required Telemetry

Record under `capacity_tightness_removal`:

- removed customer count;
- source route load/slack summary;
- capacity-tight candidate count;
- fallback count when the operator cannot find eligible candidates;
- repair operator used after removal;
- `record_move` attempted/accepted/delta/best-improved status;
- per-case total_distance, feasibility, route count, and runtime status.

## Acceptance Reading

Useful evidence requires direct objective effect tied to the removal choice:

- screening median should be meaningfully above zero and not only one lucky
  seed;
- CMT2/CMT4 must be reported, or the run must record an explicit case-selection
  caveat;
- A/B/E gains are not enough if CMT2/CMT4 or P-family regressions dominate;
- activation without objective movement is a fail-closed telemetry result;
- a route-count or feasibility regression is a blocker, not a tradeoff.

## Launch Recommendation

Launch one server-local successor35 run with:

- `--force-surface solver_design`
- `--force-action modify`
- `--force-target-file policies/baseline_modules/destroy_repair.py`
- proposal-only target-intent binding to `capacity_tightness_removal`
- no hard `required_mechanism_ids`

This is a single run, so server-local `claw` is acceptable. Use WSL `scion` for
large concurrent follow-ups.
