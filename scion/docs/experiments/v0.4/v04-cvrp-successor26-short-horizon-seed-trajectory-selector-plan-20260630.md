# CVRP Successor26 Short-Horizon Seed Trajectory Selector Plan - 2026-06-30

## Purpose

Define the next CVRP solver slot after successor25. This is a design and
task-distribution artifact, not a run log.

Successor25 validly tested `cw_sweep_seed_baseline_selector`: raw construction
seed selection activated, recorded runtime/effect telemetry, and completed
formal screening. The aggregate rows stayed below MDE with median delta `0.0`.
The run did observe direct seed gains on a small `B-n67-k10` subset, but those
gains were not preserved by downstream ALNS/VNS. The next attempt should not
repeat unchanged raw seed-baseline selection.

## Decision

Primary successor26 direction:

- implement `short_horizon_seed_trajectory_selector`;
- keep the primary target in `policies/baseline_modules/scheduler.py`;
- use `policies/baseline_modules/construction.py` only if an existing seed
  candidate needs narrow exposure;
- compare only a small set of existing construction candidates after a strictly
  bounded short-horizon trajectory;
- keep destroy/repair operators, ALNS weights, acceptance policy, protocol,
  generic core, and `DecisionFeatures` unchanged;
- interpret the result as construction seed trajectory evidence, not as
  scheduler q, repair-scoring, acceptance, or broad local-search evidence.

This is a clean fork because the causal path is not raw initial seed quality.
It asks whether a seed remains better after a short, bounded, pre-ALNS
trajectory before full downstream search can blur attribution.

## Why This Is Different

Do not repeat unchanged reviewed paths. This design is not:

- successor21/22/23 scheduler destroy-size or q scheduling;
- successor24 insertion-cost lookahead repair;
- successor25 raw CW/sweep seed-baseline selection;
- angular, radial, polar, fragment, adjacency, route-pair, timewarp, or
  load-complement destroy/repair;
- cross-exchange, Or-opt, 3-opt, ejection-chain, or route-segment local search;
- unchanged `granular_savings_seed_portfolio`;
- unchanged `seed_post_optimization_selector`;
- exact short-route polish after construction.

The mechanism keeps successor25's useful causal lesson: direct seed deltas are
not enough. It moves the evidence boundary one step downstream, but still
before full ALNS/VNS and without adding a broad multi-start solver.

## Causal Mechanism

The selector should:

1. build the normal baseline seed using the current champion path;
2. build at most two alternate feasible seeds from existing construction
   choices such as Clarke-Wright and sweep;
3. run each candidate through the same bounded short-horizon trajectory with
   strict remaining-time reserve and small no-improve caps;
4. select the feasible candidate with the best post-trajectory solver objective
   semantics: route-limit feasibility first, then total distance;
5. record baseline versus selected post-trajectory objective delta under
   `short_horizon_seed_trajectory_selector`;
6. return a normal `_Solution` for the existing downstream ALNS/VNS pipeline.

The selector must not depend on case id, BKS, split membership, protected cases,
or seed-specific shortcuts. It must not become a general multi-start package.
If the candidate needs more than a narrow scheduler-local routine plus optional
construction candidate exposure, stop and design a focused package split first.

## Module Boundary

Preferred implementation boundary for the Scion campaign candidate:

- primary target:
  `policies/baseline_modules/scheduler.py`;
- optional narrow exposure:
  `policies/baseline_modules/construction.py`.

Implementation guidance:

- keep the trajectory selector as one coherent scheduler-owned mechanism;
- reuse existing `_initial_solution`, `_vns`, and VNS operator wiring rather
  than adding a new local-search module;
- keep the candidate set fixed and small, preferably baseline plus one or two
  existing alternatives;
- use the scheduler's existing time-limit/start-time information to protect the
  formal 30s budget;
- do not add generic helpers, new destroy/repair operators, new acceptance
  logic, broad search orchestration, or framework exceptions.

## Telemetry Contract

Required candidate-facing telemetry under `short_horizon_seed_trajectory_selector`:

- activation count when the selector is used:
  `context.record_iteration("short_horizon_seed_trajectory_selector", 1)`;
- phase/runtime budget for the short-horizon selector:
  `context.record_phase("short_horizon_seed_trajectory_selector", elapsed_ms)`;
- direct same-run objective effect:
  `context.record_move("short_horizon_seed_trajectory_selector", attempted=1,
  accepted=..., delta=baseline_post_trajectory_distance -
  selected_post_trajectory_distance, best_improved=...)`.

The direct delta must be computed after the bounded short-horizon trajectory and
before full ALNS, destroy/repair adaptation, acceptance changes, or embedded
long VNS. Telemetry must also make feasibility, route count, candidate count,
and budget/reserve status visible enough for postrun interpretation.

## Static Quality Risks

Known risks:

- unbounded trajectory work can consume the 30s formal budget before ALNS;
- broad multi-start can masquerade as a seed selector;
- comparing raw construction distance repeats successor25 instead of testing a
  new causal path;
- comparing after full ALNS loses mechanism attribution;
- activation-only or candidate-count telemetry is insufficient;
- CMT2/CMT4 regressions remain material caveats even if aggregate evidence
  improves.

## Acceptance Evidence

Minimum evidence before interpretation:

- live hypothesis names `short_horizon_seed_trajectory_selector`;
- `target_file` is `policies/baseline_modules/scheduler.py`;
- construction edits, if present, are limited to narrow candidate exposure;
- no proposal, contract, verification, telemetry, or infra failure;
- formal screening rows are complete and interpreted against CVRP A/A MDE;
- direct baseline versus selected post-trajectory delta is present before full
  downstream ALNS/VNS;
- feasibility, route count, candidate count, and budget/reserve evidence are
  visible;
- CMT2/CMT4 case-level deltas are visible;
- at least one row is positive at or above MDE before any solver-positive
  claim.

Outcome classifications:

- `solver-positive-at-MDE`: at least one row reaches MDE without unresolved
  protected-case regression.
- `post-trajectory-effect-observed-below-MDE`: direct trajectory delta exists,
  but formal rows stay below MDE.
- `raw-seed-repeat`: candidate compares construction seeds before the bounded
  trajectory and repeats successor25.
- `activation-only-trajectory-selector`: selector runs but lacks direct
  baseline versus selected post-trajectory objective effect.
- `wrong-mechanism`: the candidate drifts to q scheduling, destroy/repair,
  acceptance tuning, broad local search, or exact route polish.
- `quality-regression`: aggregate or protected-case evidence regresses.

## Launch Shape

Use WSL for a two-round run after syncing this plan and the updated CVRP
guidance/tests:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 2 \
  --label v04-cvrp-successor26-short-horizon-seed-trajectory-selector \
  --model gpt-5.5 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --completion-preflight \
  --force-surface solver_design \
  --force-action modify \
  --force-target-file policies/baseline_modules/scheduler.py \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments \
  --launch
```

## Main Session Responsibilities

- Keep `scion-architecture-v3.md` boundaries intact.
- Keep this as a CVRP-owned solver-design task.
- Sync the plan, guidance, tests, and status docs to WSL before launch.
- Check fresh WSL connectivity, targeted tests, and completion preflight before
  trusting the run.
- Interpret the result against MDE, direct post-trajectory telemetry, ALNS trace
  support, and CMT protected-case evidence.

## Campaign-Agent Responsibilities

- Produce a normal Scion proposal through Contract and Verification.
- Name `short_horizon_seed_trajectory_selector` as the mechanism id.
- Keep the primary code change in `scheduler.py`.
- Use construction only for narrow seed candidate exposure if needed.
- Preserve feasibility, route-count constraints, seeded determinism, and runtime
  guards.
