# CVRP Successor21 Adaptive Destroy-Size Plan - 2026-06-29

## Purpose

Define the next v0.4 CVRP successor attempt after successor20. This is a
design and task-distribution artifact, not a run log.

Successor19 and successor20 established that `bounded_route_segment_exchange`
is framework-useful but solver-negative for v0.4 closeout: the mechanism
activated, but current objective effect was zero and below MDE. The next run
should clean-fork to a different CVRP-owned causal path.

## Decision

Primary successor21 direction:

- implement `stagnation_adaptive_destroy_size_schedule`;
- keep the mechanism in the CVRP solver-design surface;
- change the actual ALNS search trajectory by adapting destroy size `q`;
- leave generic core, acceptance policy, adaptive operator weights, and
  baseline algorithm APIs unchanged;
- treat this as scheduler-policy evidence, not a new destroy operator or
  downstream-improvement attribution shortcut.

The seed-post selector repair remains a deferred diagnostic fallback. It is
not the primary successor21 path because successor21 should spend the next
slot on a materially different solver mechanism rather than an activation
repair branch.

## Why This Is Different

Do not repeat unchanged reviewed paths. This design is not:

- bounded local search or another `bounded_route_segment_exchange` refinement;
- route-pressure acceptance, rank-gap acceptance, or temperature tuning;
- adaptive operator weighting;
- a repeated removal or repair operator;
- `seed_post_optimization_selector` activation repair.

The intended mechanism changes destroy magnitude before the existing
destroy/repair operators execute. That creates a different bounded search
trajectory while preserving the existing operator set and acceptance surface.

## Causal Mechanism

The scheduler should maintain a small amount of problem-owned ALNS loop state:

1. best-improvement stagnation since the last new best solution;
2. recent infeasible, route-limit, or repair-error pressure;
3. current budget phase if already available inside the scheduler loop.

Use that state to adjust `q` within the existing `DESTROY_RATIO` and
`MAX_DESTROY_CUSTOMERS` guardrails:

- increase `q` after sustained feasible no-best-improvement stagnation, so the
  next destroy/repair step can escape shallow local basins;
- reduce or cap `q` after recent infeasible, route-limit, or repair-error
  pressure, so repair has a higher chance to produce feasible candidates;
- reset or relax the schedule after a new best solution;
- never exceed existing route, capacity, runtime, or destroy-size constraints.

This is intentionally a scheduler policy. It should not introduce CVRP case
ids, BKS thresholds, split membership, or protected-case exceptions into solver
code.

## Module Boundary

Preferred implementation boundary for the Scion campaign candidate:

- focused problem-owned support module if the rule needs more than a narrow
  block:
  `policies/baseline_modules/destroy_size_schedule.py`
- minimal wiring:
  `policies/baseline_modules/scheduler.py`

If the rule is only a compact local calculation, a scheduler-only patch is
acceptable. Do not add a helper forest. Do not modify
`policies/baseline_algorithm.py`, `policies/baseline_modules/acceptance.py`,
`policies/baseline_modules/state.py`, or generic framework modules unless a
fresh proposal gives a stronger boundary argument.

## Telemetry Contract

Required candidate-facing telemetry under
`stagnation_adaptive_destroy_size_schedule`:

- activation/decision count when the adaptive schedule is applied:
  `context.record_iteration("stagnation_adaptive_destroy_size_schedule", 1)`
- phase/runtime budget for the decision path:
  `context.record_phase("stagnation_adaptive_destroy_size_schedule", elapsed_ms)`

Do not call internal diagnostics such as `record_alns_iteration` from the
candidate-facing mechanism. Existing ALNS trace fields already record q,
operator, accepted status, candidate distance, best distance, and related loop
facts.

Only use `record_move` if the implementation creates a defensible direct
causal attribution for a specific q-schedule decision. Otherwise, avoid
claiming ordinary downstream ALNS improvements as direct mechanism moves. The
formal evidence should be interpreted through row-level paired objective
outcomes, q-distribution/trace changes, activation, and MDE comparison.

## Static Quality Risks

Known quality risks:

- A scheduler-only patch that changes only operator weights, phase order, or
  runtime allocation does not satisfy the causal target.
- Activation-only evidence is not enough if the q schedule never changes the
  destroy size seen by the existing destroy/repair operations.
- Telemetry must stay candidate-facing and problem-owned; do not add new
  calls to internal postrun diagnostics.
- The implementation must remain bounded and deterministic under the same
  seeded run conditions used by the baseline.

## Protected Cases

CMT2 and CMT4 must remain explicitly visible in postrun interpretation.

The solver must not hardcode those cases. The experiment/reporting layer must
verify:

- formal screening includes CMT2 and CMT4 when available in the split;
- case-level `total_distance` deltas are reported for CMT2 and CMT4;
- any CMT regression is treated as a caveat even if aggregate evidence is
  positive.

## Launch Shape

Recommended WSL launch after syncing this plan and the status docs:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 2 \
  --label v04-cvrp-successor21-adaptive-destroy-size \
  --model gpt-5.5 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --completion-preflight \
  --force-surface solver_design \
  --force-action modify \
  --force-target-file policies/baseline_modules/scheduler.py \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments
```

If launch review shows that the proposal needs a small owned module for the
schedule rule, allow `policies/baseline_modules/destroy_size_schedule.py` as
the supporting module while keeping scheduler wiring minimal.

## Main Session Responsibilities

- Keep `scion-architecture-v3.md` boundaries intact.
- Keep this as a problem-owned solver-design task.
- Sync the plan and status docs to WSL before launch.
- Check fresh launch readiness and completion preflight before backgrounding
  the run.
- Assign postrun analysis to a subagent once the run finishes.
- Interpret the result against MDE, q-trace evidence, and CMT protected-case
  evidence.

## Worker Or Campaign-Agent Responsibilities

- Produce a normal Scion proposal through Contract and Verification; do not
  hand-edit generic framework code.
- Name `stagnation_adaptive_destroy_size_schedule` as the mechanism id.
- Change actual destroy-size selection before existing destroy/repair
  operators run.
- Keep the implementation compact and problem-owned.
- Preserve feasibility, route-count constraints, and runtime guards.

## Acceptance Evidence

Minimum evidence before interpretation:

- live hypothesis names `stagnation_adaptive_destroy_size_schedule`;
- no proposal quality block;
- formal screening rows are complete;
- mechanism activation is observed;
- q distribution or trace evidence differs from unchanged fixed-ratio destroy
  behavior;
- CMT2/CMT4 case-level deltas are visible;
- feasibility and route count are preserved or caveated;
- effect-vs-MDE includes `rows_at_or_above_mde`, CI, and effect/MDE ratio;
- postrun acceptance readiness is ready.

Outcome classification:

- `solver-positive-at-MDE`: at least one formal row is positive at or above MDE
  and protected cases do not show unresolved regression.
- `evidence-complete below-MDE`: activation and q-trajectory evidence are
  present, but no row reaches MDE.
- `inactive schedule failure`: the mechanism id or q-change evidence is absent
  from formal artifacts.
- `quality regression`: protected-case or aggregate losses dominate, even if
  activation is present.
- `infra invalid`: run validity or postrun readiness fails for infrastructure
  reasons.
