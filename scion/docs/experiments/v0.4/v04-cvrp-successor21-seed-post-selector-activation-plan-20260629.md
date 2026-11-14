# CVRP Deferred Seed-Post Selector Activation Plan - 2026-06-29

Status: deferred fallback after successor21 direction review. The current
primary successor21 plan is
`v04-cvrp-successor21-adaptive-destroy-size-plan-20260629.md`.

## Purpose

Define the next v0.4 CVRP successor attempt after successor20. This is a
design and task-distribution artifact, not a run log.

Successor19 and successor20 established that `bounded_route_segment_exchange`
is framework-useful but solver-negative for v0.4 closeout: the mechanism
activated, but current objective effect was zero and below MDE. The next run
should not spend another slot on same-branch bounded segment refinement.

## Decision

Deferred fallback direction:

- repair `seed_post_optimization_selector` activation and direct objective
  effect attribution;
- keep the mechanism in the CVRP solver-design surface;
- treat this as a construction/post-construction selector repair, not a generic
  scheduler or Decision change;
- require same-run selected-seed-vs-baseline objective evidence before any
  downstream ALNS/VNS effect can be claimed.

This direction remains allowed as a later diagnostic repair because
`seed_post_optimization_selector` is
suppressed for unchanged repetition after successor16/17, but it is not
reviewed as evidence-complete no-positive-at-MDE. The prior failure mode was
inactive/missing activation, not measured negative solver effect.

## Why Not Continue Bounded Segment Exchange

Successor20 showed:

- `bounded_route_segment_exchange` activation observed;
- phase telemetry observed on both rows;
- `median_delta=0.0`;
- CI `[0.0, 0.0]`;
- `rows_at_or_above_mde=0`;
- `objective_effect_status=zero_objective_effect`.

That means the failure is not missing activation. Another same-branch
refinement would need a new design that explains why the zero-median operator
can cross the `mde_at_power_80=9.9` threshold. No such design is currently
available.

## Causal Mechanism

The intended mechanism is a small post-construction selector:

1. Build the existing default initial solution path as the baseline.
2. Build one or more bounded alternate construction/post-construction seeds
   using already available CVRP problem-owned construction operations.
3. Compare each candidate seed against the baseline before downstream ALNS/VNS.
4. Select the best feasible candidate only if it improves total distance while
   preserving route feasibility and route-count constraints.
5. Record activation, runtime, and selected-seed-vs-baseline objective effect
   under the concrete mechanism id `seed_post_optimization_selector`.

Non-goals:

- Do not claim downstream ALNS/VNS gains as the selector effect.
- Do not repeat unchanged `granular_savings_seed_portfolio`.
- Do not add case ids, BKS values, split membership, or protected-case
  thresholds to solver code.
- Do not add CVRP-specific exceptions to generic core, protocol, Decision, or
  scheduler policy outside the CVRP solver-design subject.

## Module Boundary

Preferred implementation boundary for the Scion campaign candidate:

- New problem-owned module:
  `policies/baseline_modules/seed_selector.py`
- Minimal wiring:
  `policies/baseline_modules/scheduler.py`
- Optional constants only if needed:
  `policies/baseline_modules/config.py`

The new module should expose one cohesive operation such as
`select_post_construction_seed(solution, instance, context, reserve, max_routes)`.
It should not become a pile of unrelated helper functions. Scheduler wiring
should only call the selector at the construction boundary and keep existing
ALNS/VNS logic unchanged.

## Telemetry Contract

Required telemetry under `seed_post_optimization_selector`:

- activation:
  `context.record_iteration("seed_post_optimization_selector", 1)`
- phase runtime:
  `context.record_phase("seed_post_optimization_selector", elapsed_ms)`
- direct objective effect:
  `context.record_move("seed_post_optimization_selector", attempted=1,
  accepted=..., delta=selected_seed_vs_baseline_delta, best_improved=...)`

The delta must be computed before downstream VNS/ALNS:

```text
selected_seed_vs_baseline_delta =
  baseline_initial_total_distance - selected_initial_total_distance
```

If no alternate seed improves the baseline, record `attempted=1`,
`accepted=0`, and no positive delta.

This is the key difference from successor16/17: a row is not acceptable if the
mechanism id is merely declared but absent from formal telemetry.

## Static Quality Risks

Known pre-protocol risks:

- Construction seed mechanisms are blocked if they only record activation,
  phase time, seed-pool size, or fallback usage.
- Direct effect must be recorded with `context.record_move` under the declared
  mechanism id.
- Destroy-only telemetry rules do not apply unless the candidate introduces a
  destroy/removal mechanism; this deferred repair should not do that.
- Acceptance/temperature telemetry rules do not apply unless the candidate
  changes acceptance logic; this deferred repair should not do that.

The implementation should therefore keep `seed_post_optimization_selector` away
from broad ALNS bookkeeping and record only same-run seed-selection effect.

## Protected Cases

CMT2 and CMT4 must remain explicitly visible in postrun interpretation.

The solver must not hardcode those cases. The experiment/reporting layer must
verify:

- formal screening includes CMT2 and CMT4 when available in the split;
- case-level `total_distance` deltas are reported for CMT2 and CMT4;
- any CMT regression is treated as a caveat even if aggregate evidence is
  positive.

## Launch Shape

Deferred launch shape if this repair is promoted later after the adaptive
destroy-size branch is interpreted:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 2 \
  --label v04-cvrp-successor21-seed-post-selector-activation \
  --model gpt-5.5 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --completion-preflight \
  --force-surface solver_design \
  --force-action modify \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments
```

Do not force a single target file unless a launch review shows the proposal
keeps drifting away from activation repair. The preferred modular boundary
needs both scheduler wiring and a problem-owned support module.

## Main Session Responsibilities

- Keep `scion-architecture-v3.md` boundaries intact.
- Keep this as a problem-owned solver-design task.
- Sync the plan and status docs to WSL before launch.
- Check prepared launch readiness and completion preflight on the fresh root.
- Assign postrun analysis to a subagent once the run finishes.
- Interpret the result against MDE and CMT protected-case evidence.

## Worker Or Campaign-Agent Responsibilities

- Produce a normal Scion proposal through Contract and Verification; do not
  hand-edit generic framework code.
- Name `seed_post_optimization_selector` as the mechanism id if repairing that
  path.
- Implement a coherent problem-owned module boundary instead of adding broad
  helpers to scheduler or construction.
- Provide same-run selected-seed-vs-baseline effect telemetry.
- Preserve feasibility, route count constraints, and runtime guards.

## Acceptance Evidence

Minimum evidence before interpretation:

- live hypothesis names `seed_post_optimization_selector`;
- no proposal quality block;
- formal screening rows are complete;
- mechanism activation is observed;
- direct objective effect telemetry is observed under the mechanism id;
- CMT2/CMT4 case-level deltas are visible;
- feasibility and route count are preserved or caveated;
- effect-vs-MDE includes `rows_at_or_above_mde`, CI, and effect/MDE ratio;
- postrun acceptance readiness is ready.

Outcome classification:

- `solver-positive-at-MDE`: at least one formal row is positive at or above MDE
  and protected cases do not show unresolved regression.
- `evidence-complete below-MDE`: activation and direct effect telemetry are
  present, but no row reaches MDE.
- `inactive repair failure`: the mechanism id is still absent from formal
  activation/effect telemetry.
- `quality regression`: protected-case or aggregate losses dominate, even if
  activation is present.
- `infra invalid`: run validity or postrun readiness fails for infrastructure
  reasons.

## Fallback Direction

If this deferred repair is eventually promoted and is quality-blocked before
protocol or repeats missing activation, do not immediately relaunch the same
instruction. Move to a fresh documented design instead of spending another slot
on unchanged seed-post activation repair.
