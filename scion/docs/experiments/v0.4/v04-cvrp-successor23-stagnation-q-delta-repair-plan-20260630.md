# CVRP Successor23 Stagnation q-Delta Repair Plan - 2026-06-30

## Purpose

Define the next CVRP action after successor22b. This is a design and
task-distribution artifact, not a run log.

Successor22b corrected wrong-mechanism drift and generated a compact
`stagnation_adaptive_destroy_size_schedule` patch, but formal q traces showed
zero aligned q difference versus champion:

- row 1: `0 / 505` aligned ALNS iterations changed q;
- row 2: `0 / 737` aligned ALNS iterations changed q;
- both rows had median delta `0.0`, CI `[0.0, 0.0]`, and no case-level wins.

Successor23 is therefore an activation repair for the q trajectory, not a broad
new optimizer.

## Decision

Primary successor23 direction:

- keep the same problem-owned scheduler policy family;
- repair `stagnation_adaptive_destroy_size_schedule` so it creates observable
  nonzero q deltas under formal screening;
- keep implementation local to `policies/baseline_modules/scheduler.py`;
- do not add helper-function layers or generic framework behavior;
- do not change acceptance policy, adaptive operator weights, destroy/repair
  operators, construction, local search, protocol, promotion, or
  `DecisionFeatures`.

This is allowed as a same-branch refinement only because successor22b was a
q-trajectory no-op. If the next run still has zero q deltas, park the scheduler
destroy-size branch.

## Required Mechanism Shape

Use a compact local schedule around the existing q selection:

1. compute and retain `baseline_q` from the current random destroy ratio;
2. compute a bounded `adapted_q` from stagnation/search-progress state;
3. assign `q = adapted_q`;
4. record `baseline_q`, `adapted_q`, and `q_delta` in the existing ALNS
   iteration trace path, or an equally direct candidate-facing runtime field;
5. keep all q values within existing feasibility and `max_destroy_customers`
   guardrails.

The schedule must create an actual q difference after sustained no-best
stagnation or repeated hard rejection. It must not depend on case id, BKS,
split membership, protected cases, or seed-specific conditions.

## Module Boundary

Preferred implementation shape:

- one narrow patch in `policies/baseline_modules/scheduler.py`;
- a small extension of the existing `_record_alns_iteration_trace` payload is
  acceptable if it records q audit fields directly.

Do not add:

- generic postrun/protocol/runtime helpers;
- CVRP exceptions in core;
- a new helper module unless the scheduler patch becomes too large to audit;
- new acceptance, weight, construction, local-search, or destroy/repair
  behavior.

If a separate module becomes necessary, it must be a single coherent
problem-owned scheduler policy module, not a bag of utilities.

## Telemetry Contract

Required evidence before objective interpretation:

- `mechanism_evidence.primary_mechanism` is
  `stagnation_adaptive_destroy_size_schedule`;
- `activation_evidence_status=activation_observed`;
- aligned candidate/champion ALNS traces show `q_delta != 0` on at least one
  formal screening pair;
- postrun summarizes q-change coverage: pairs with q change, changed
  iterations, median q delta, min/max q delta;
- row-level paired total-distance evidence still reports MDE, CI, CMT2, and
  CMT4.

If q changes but objective remains below MDE, classify the branch as
evidence-complete below-MDE rather than solver-positive.

## Acceptance Evidence

Minimum postrun checks:

- run status valid/complete/postrun-ready;
- no proposal, verification, telemetry, or infra failure;
- compact scheduler-only diff;
- q-change coverage is nonzero;
- no protected-case regression in CMT2/CMT4;
- at least one row positive at or above MDE before any solver-positive claim.

Outcome classifications:

- `activation-repaired-but-below-MDE`: q deltas are present, but no row reaches
  MDE.
- `inactive-q-trajectory-repeat`: q deltas are still zero; park the scheduler
  destroy-size branch.
- `quality-regression`: q deltas are present but aggregate/protected cases
  regress.
- `solver-positive-at-MDE`: at least one row reaches MDE without unresolved
  protected-case regression.

## Launch Shape

Use WSL for a two-round run after syncing the local design/guidance update and
passing launch readiness:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 2 \
  --label v04-cvrp-successor23-stagnation-q-delta-repair \
  --model gpt-5.5 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --completion-preflight \
  --force-surface solver_design \
  --force-action modify \
  --force-target-file policies/baseline_modules/scheduler.py \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments
```

Historical launch constraint: the prepared guidance had to state that
successor23 was a q-delta activation repair and must not repeat successor22b's
zero-q-delta trajectory before launch.

## Launch Status

Completed WSL run root from runner commit `b0adf692`:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor23-stagnation-q-delta-repair-2r-gpt55-20260630T020559Z-claw`

Status:

- campaign started at `2026-06-30T02:06:31Z`;
- wrapper pid: `63815`;
- campaign pid: `63837`;
- pre-campaign completion preflight passed against local `gpt-5.5` at
  `http://127.0.0.1:8080`, HTTP 200;
- final campaign status is valid/complete/postrun-ready;
- stop reason: `max_rounds_exhausted`;
- objective evidence: two screening rows, `rows_at_or_above_mde=0`,
  `positive_rows=0`, `max_median_delta=0.0`;
- q trajectory changed versus champion in aligned ALNS traces, but explicit
  `baseline_q`, `adapted_q`, and `q_delta` runtime fields were not emitted;
- final interpretation:
  `activation-repaired-but-below-MDE` with
  `quality-regression-parked` and `explicit-q-delta-telemetry-missing`
  caveats;
- postrun report:
  `scion/docs/experiments/v0.4/v04-cvrp-successor23-stagnation-q-delta-repair-postrun-20260630.md`;
- prepared manifest requires
  `stagnation_adaptive_destroy_size_schedule`;
- prepared manifest requires baseline/adapted/q-delta evidence and nonzero
  aligned candidate/champion q deltas before objective interpretation.

The first prepared root,
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor23-stagnation-q-delta-repair-2r-gpt55-20260630T014819Z-claw`,
failed before campaign start because pre-campaign completion preflight received
HTTP 502 from a TLS handshake EOF. It is a launch-path transient, not CVRP
experiment evidence.
