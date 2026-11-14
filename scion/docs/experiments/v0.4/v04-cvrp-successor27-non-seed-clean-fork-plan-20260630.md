# CVRP Successor27 Non-Seed Clean Fork Plan - 2026-06-30

## Purpose

Successor27 is the next small CVRP solver experiment after successor26b
validly screened the short-horizon construction seed trajectory selector below
MDE. It should not continue construction seed-baseline or seed-trajectory
selection.

The goal is to spend the next branch slot only on a materially different
CVRP-owned causal path, with direct per-case `total_distance` evidence before
any positive solver conclusion.

## Target

- Surface: `solver_design`
- Action: `modify`
- Primary owner file for this launch:
  `policies/baseline_modules/destroy_repair.py`
- Acceptable same-branch secondary owner, only if needed by the proposed
  mechanism:
  `policies/baseline_modules/local_search.py`
- Runner: server-local `claw`
- Model: local `gpt-5.5`
- Rounds: `2`

This is small enough for the server. Use WSL `scion` only for larger or
concurrent batches, after a fresh completion preflight.

## Design Constraints

- Do not repeat unchanged:
  `short_horizon_seed_trajectory_selector`,
  `short_horizon_seed_trajectory_selector_v2`,
  `cw_sweep_seed_baseline_selector`,
  `lookahead_insertion_cost_repair`,
  `lookahead_insertion_cost_repair_v2`,
  `stagnation_adaptive_destroy_size_schedule`,
  `operator_pair_destroy_size_bands`, or any reviewed destroy/repair removal
  variant.
- Keep CVRP/VRP semantics in problem-owned solver files.
- Do not add CVRP-specific behavior to generic core, protocol, scheduler,
  launcher, or `DecisionFeatures`.
- Prefer a compact mechanism implementation over broad helpers. If behavior
  grows beyond a narrow patch, split it by a clear problem-owned module/package
  boundary before adding more code.
- A candidate must name its mechanism id and show how its causal path differs
  from reviewed destroy/repair and construction seed paths before code work.

## Required Evidence

- Primary mechanism id appears in `mechanism_evidence.primary_mechanism`.
- Pair-level and case-level `total_distance` deltas are tied to the changed
  destroy/repair or bounded-local-search choice.
- Feasibility and route-count evidence are preserved.
- CMT2/CMT4 case effects are reported or an explicit caveat is recorded.
- Effect-vs-MDE interpretation uses the current CVRP A/A MDE (`9.9`).

## Launch Intent

Launch as a two-round server-local run after the successor26b guidance/catalog
commit. Force `solver_design` / `modify` /
`policies/baseline_modules/destroy_repair.py` so the agent starts outside the
parked construction seed trajectory path.
