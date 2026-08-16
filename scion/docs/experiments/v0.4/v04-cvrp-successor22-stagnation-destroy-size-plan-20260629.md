# CVRP Successor22 Stagnation Destroy-Size Plan - 2026-06-29

## Purpose

Define the successor22 clean fork after successor21. This is a design and
task-distribution artifact, not a run log.

Successor21 validly tested a scheduler destroy-size policy, but the generated
mechanism was `operator_pair_destroy_size_bands`, not the intended
`stagnation_adaptive_destroy_size_schedule`. It activated and changed q, but
remained below MDE and became loss-heavy on the expanded row. Successor22
should correct the mechanism target, not repeat the same operator-pair q-band
lineage.

## Decision

Primary successor22 direction:

- clean-fork to `stagnation_adaptive_destroy_size_schedule`;
- expose `stagnation_adaptive_destroy_size_schedule` as a hard
  `required_mechanism_ids` value in the prepared CVRP research focus;
- keep the target in the CVRP solver-design surface;
- change ALNS destroy magnitude `q` before existing destroy/repair operators
  run;
- derive q from stagnation/search-progress state, not from destroy/repair
  operator identity alone;
- leave generic core, protocol, DecisionFeatures, acceptance policy, adaptive
  operator weights, and baseline algorithm APIs unchanged.

This remains a problem-owned scheduler policy. It is not a destroy operator,
local search operator, acceptance tweak, adaptive-weighting experiment, or
construction-seed repair.

## Non-Repeat Rule

Do not repeat unchanged reviewed paths:

- `bounded_route_segment_exchange`;
- `operator_pair_destroy_size_bands`;
- `granular_savings_seed_portfolio`;
- `exact_short_route_polish`;
- `seed_post_optimization_selector`;
- reviewed bounded-local-search, destroy/repair, and construction mechanisms
  already listed in the CVRP successor evidence catalog.

The successor22 hypothesis must explicitly distinguish itself from
`operator_pair_destroy_size_bands`: operator-pair bands are already measured
below MDE and loss-heavy on follow-up. The new causal path is stagnation state.

## Successor22a Drift

The first prepared successor22 launch
`v04-cvrp-successor22-stagnation-destroy-size-2r-gpt55-20260629T192118Z-claw`
was stopped before formal screening after live target-intent/hypothesis drifted
to `bounded_repair_retry_on_reject`. That root is a wrong-mechanism diagnostic,
not solver evidence.

Successor22b must use the existing prepared-focus required-mechanism channel so
target-intent authority and hypothesis preview require exactly
`stagnation_adaptive_destroy_size_schedule`.

## Causal Mechanism

Use a compact policy inside `policies/baseline_modules/scheduler.py`, or a
single focused module only if the rule no longer fits cleanly in the scheduler
loop.

Required state inputs are local ALNS loop facts already available around q
selection:

1. iterations since the last new best solution;
2. whether the previous accepted move improved the best objective;
3. current best/candidate objective relation where already available;
4. remaining-time guard so the schedule cannot consume budget.

Expected behavior:

- start from the existing baseline q;
- keep q near baseline during early search or immediately after a new best;
- increase q after sustained no-best-improvement stagnation;
- cap q back down when remaining time is low or when q would exceed existing
  destroy-size guardrails;
- never hardcode case ids, BKS values, seed ids, split membership, or protected
  cases into solver code.

## Module Boundary

Preferred first implementation shape:

- `policies/baseline_modules/scheduler.py`

Allowed only if the policy becomes larger than a narrow local patch:

- `policies/baseline_modules/destroy_size_schedule.py`

Do not add a broad helper layer. If a supporting module is needed, it should
contain one coherent scheduler policy, with scheduler wiring kept small.

Do not modify:

- generic Scion core;
- protocol or DecisionFeatures;
- `policies/baseline_algorithm.py`;
- `policies/baseline_modules/acceptance.py`;
- adaptive operator weights;
- construction or local-search modules.

## Telemetry Contract

Required candidate-facing telemetry:

- `context.record_iteration("stagnation_adaptive_destroy_size_schedule", 1)`
  when the schedule changes or explicitly decides q;
- `context.record_phase("stagnation_adaptive_destroy_size_schedule", elapsed)`
  around the schedule decision;
- ALNS trace must expose enough q trajectory to compare base q and adapted q,
  or equivalent q-distribution evidence must be available in postrun metrics.

Do not claim ordinary downstream ALNS improvements as direct mechanism moves
unless the implementation creates defensible direct attribution for one
schedule decision. The main interpretation remains row-level paired
`total_distance`, MDE, q trajectory, and CMT2/CMT4 case deltas.

## Acceptance Evidence

Minimum evidence before interpretation:

- live hypothesis names `stagnation_adaptive_destroy_size_schedule`;
- `launch_payload.required_mechanism_ids` contains only
  `stagnation_adaptive_destroy_size_schedule`;
- generated code changes q from stagnation/search-progress state;
- no proposal quality block;
- formal screening rows complete;
- mechanism activation observed under the declared mechanism id;
- q trajectory differs from unchanged baseline and from operator-pair-only
  q bands;
- CMT2/CMT4 are present in formal screening or an unresolved coverage caveat
  is recorded;
- postrun readiness is ready;
- effect-vs-MDE reports CI, `rows_at_or_above_mde`, and effect/MDE ratio.

Outcome classification:

- `solver-positive-at-MDE`: at least one formal row is positive at or above MDE
  and protected cases do not show unresolved regression.
- `evidence-complete below-MDE`: activation and q-trajectory evidence are
  present, but no row reaches MDE.
- `wrong-mechanism drift`: generated mechanism is not stagnation based.
- `inactive schedule failure`: declared mechanism or q-change evidence is
  absent from formal artifacts.
- `quality regression`: protected-case or aggregate losses dominate.

## Launch Shape

Recommended WSL launch after syncing current guidance and this plan:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 2 \
  --label v04-cvrp-successor22b-stagnation-required \
  --model gpt-5.5 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --completion-preflight \
  --force-surface solver_design \
  --force-action modify \
  --force-target-file policies/baseline_modules/scheduler.py \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments
```

Use WSL for this run because the local server has only two cores and the last
2-round WSL CVRP run completed cleanly with local `gpt-5.5`.

## Main Session Responsibilities

- Keep architecture boundaries from `scion/design/scion-architecture-v3.md`.
- Keep this as problem-owned CVRP solver-design work.
- Sync only necessary source/docs to the WSL runner.
- Recheck launch readiness and completion preflight before backgrounding.
- After completion, analyze exact mechanism identity before interpreting
  effects.

## Campaign-Agent Responsibilities

- Produce a normal Scion proposal through contract and verification.
- Name `stagnation_adaptive_destroy_size_schedule`.
- Implement a compact stagnation-state q schedule.
- Preserve existing operators, repair, acceptance, feasibility, route-count
  constraints, and runtime guards.
