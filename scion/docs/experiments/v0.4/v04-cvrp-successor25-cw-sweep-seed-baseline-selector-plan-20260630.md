# CVRP Successor25 CW/Sweep Seed Baseline Selector Plan - 2026-06-30

## Purpose

Define the next CVRP solver slot after successor24. This is a design and
task-distribution artifact, not a run log.

Successor24 validly tested `lookahead_insertion_cost_repair` and
`lookahead_insertion_cost_repair_v2`, but both rows stayed below MDE and the
v2 follow-up recorded direct-effect-zero telemetry. The next solver attempt
should not continue insertion-cost lookahead repair.

## Decision

Primary successor25 direction:

- implement `cw_sweep_seed_baseline_selector`;
- keep the primary target in
  `policies/baseline_modules/construction.py`;
- use `policies/baseline_modules/scheduler.py` only to call the selector from
  `_initial_solution` and record construction-phase telemetry;
- keep destroy/repair, local search, acceptance, adaptive ALNS weights,
  protocol, generic core, and `DecisionFeatures` unchanged;
- interpret the result as construction seed-selection evidence, not as
  scheduler q, repair-scoring, acceptance, or local-search evidence.

This is a clean fork because the causal path is initial feasible seed quality
with direct same-run baseline attribution before ALNS/VNS can blur the effect.

## Why This Is Different

Do not repeat unchanged reviewed paths. This design is not:

- successor21/22/23 scheduler destroy-size or q scheduling;
- successor24 insertion-cost lookahead repair;
- angular, radial, polar, fragment, adjacency, route-pair, timewarp, or
  load-complement destroy/repair;
- cross-exchange, Or-opt, 3-opt, ejection-chain, or route-segment local search;
- unchanged `granular_savings_seed_portfolio`;
- unchanged `seed_post_optimization_selector`;
- exact short-route polish after construction.

The mechanism chooses between existing feasible construction candidates such as
Clarke-Wright, sweep, and capacity-balanced fallback, then records the selected
seed's objective delta against a deterministic same-run baseline before any
downstream search.

## Causal Mechanism

The selector should:

1. build a bounded set of feasible construction candidates using existing
   construction functions;
2. choose a deterministic baseline seed, normally the current champion default
   path for the same instance and route cap;
3. select the best feasible candidate by lexicographic solver objective
   semantics: fleet feasibility first, then total distance;
4. record the selected seed versus baseline objective delta under
   `cw_sweep_seed_baseline_selector`;
5. return a normal `_Solution` for the existing ALNS/VNS pipeline.

The selector must not depend on case id, BKS, split membership, protected cases,
or seed-specific shortcuts. It should avoid adding a general portfolio package
inside the campaign patch; if construction selection grows beyond a narrow
operator, stop and design a focused construction package split first.

## Module Boundary

Preferred implementation boundary for the Scion campaign candidate:

- primary target:
  `policies/baseline_modules/construction.py`;
- minimal wiring:
  `policies/baseline_modules/scheduler.py`.

Implementation guidance:

- add one coherent construction selector function, for example
  `_cw_sweep_seed_baseline_selector(instance, max_routes=None)`;
- reuse `_clarke_wright_savings`, `_sweep_construction`,
  `_capacity_balanced_construction`, and `_nearest_neighbor`;
- keep any small candidate-ranking logic local to the selector;
- do not add generic helper modules, new local-search operators, new
  destroy/repair operators, or framework exceptions.

## Telemetry Contract

Required candidate-facing telemetry under `cw_sweep_seed_baseline_selector`:

- activation count when the selector is used:
  `context.record_iteration("cw_sweep_seed_baseline_selector", 1)`;
- phase/runtime budget for the construction selection:
  `context.record_phase("cw_sweep_seed_baseline_selector", elapsed_ms)`;
- direct same-run objective effect:
  `context.record_move("cw_sweep_seed_baseline_selector", attempted=1,
  accepted=..., delta=baseline_total_distance - selected_total_distance,
  best_improved=...)`.

The direct delta must be computed before initial VNS, size70 polish, ALNS, or
embedded VNS. If the selector only reports that a seed was selected, classify
it as activation/design evidence, not solver effect.

## Static Quality Risks

Known risks:

- activation-only construction telemetry is insufficient;
- selecting the current default seed without a material alternative is a no-op;
- using route count alone as the objective can hide distance regressions;
- expensive seed portfolios can consume the 30s screening budget before ALNS;
- CMT2/CMT4 regressions remain material caveats even if aggregate evidence
  improves.

## Acceptance Evidence

Minimum evidence before interpretation:

- live hypothesis names `cw_sweep_seed_baseline_selector`;
- `target_file` is `policies/baseline_modules/construction.py`;
- scheduler edits, if present, are limited to invocation and telemetry;
- no proposal, contract, verification, telemetry, or infra failure;
- formal screening rows are complete and interpreted against CVRP A/A MDE;
- direct selected-seed versus baseline delta is present before downstream
  search;
- CMT2/CMT4 case-level deltas are visible;
- at least one row is positive at or above MDE before any solver-positive
  claim.

Outcome classifications:

- `solver-positive-at-MDE`: at least one row reaches MDE without unresolved
  protected-case regression.
- `seed-effect-observed-below-MDE`: direct seed delta exists, but formal rows
  stay below MDE.
- `activation-only-seed-selector`: selector runs but lacks direct selected-seed
  versus baseline objective effect.
- `wrong-mechanism`: the candidate drifts to q scheduling, destroy/repair,
  acceptance tuning, local search, or exact route polish.
- `quality-regression`: aggregate or protected-case evidence regresses.

## Launch Shape

Use WSL for a two-round run after syncing this plan and the status docs:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 2 \
  --label v04-cvrp-successor25-cw-sweep-seed-baseline-selector \
  --model gpt-5.5 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --completion-preflight \
  --force-surface solver_design \
  --force-action modify \
  --force-target-file policies/baseline_modules/construction.py \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments \
  --launch
```

## Main Session Responsibilities

- Keep `scion-architecture-v3.md` boundaries intact.
- Keep this as a CVRP-owned solver-design task.
- Sync the plan and status docs to WSL before launch.
- Check fresh WSL connectivity and completion preflight before trusting the run.
- Interpret the result against MDE, direct seed-baseline telemetry, ALNS trace
  support, and CMT protected-case evidence.

## Campaign-Agent Responsibilities

- Produce a normal Scion proposal through Contract and Verification.
- Name `cw_sweep_seed_baseline_selector` as the mechanism id.
- Keep the primary code change in `construction.py`.
- Use scheduler only for minimal invocation and mechanism telemetry.
- Preserve feasibility, route-count constraints, seeded determinism, and runtime
  guards.
