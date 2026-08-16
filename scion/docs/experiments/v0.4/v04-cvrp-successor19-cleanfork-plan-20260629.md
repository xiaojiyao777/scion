# CVRP Successor19 Clean-Fork Plan - 2026-06-29

## Purpose

Prepare the next v0.4 CVRP successor attempt after successor18b. This is a task
design and delegation artifact, not a run log.

Successor18b was framework-positive but solver-negative: the scheduler
mechanism-granular repair worked, but both evaluated mechanisms stayed below
promotion-grade evidence. The next slot should therefore test a materially
different CVRP-owned causal path rather than continue the reviewed/suppressed
mixed branch.

## Governing Evidence

- `scion/docs/experiments/v0.4/v04-cvrp-successor18b-postrun-20260629.md`
- `scion/scion/problems/cvrp/research_guidance.py`
- `scion/scion/problems/cvrp/successor_evidence_catalog.py`
- `scion/TASK.md`
- `scion/docs/status/current-state.md`

## Decision

Preferred successor19 direction:

- clean-fork to a materially different non-reviewed CVRP-owned causal path;
- prefer a new destroy/repair selection path around capacity tightness,
  residual-demand structure, or another non-reviewed removal/repair rule;
- assign a new mechanism id and mechanism family evidence distinct from
  reviewed/suppressed ids.

Allowed but not preferred:

- `seed_post_optimization_selector` activation repair, only if the explicit
  task is activation wiring rather than solver progress. This path requires
  pre-protocol activation proof before formal screening.

Do not repeat unchanged:

- `granular_savings_seed_portfolio`;
- `exact_short_route_polish`;
- `seed_post_optimization_selector` without explicit activation repair;
- reviewed bounded-local-search, destroy/repair, or construction paths listed
  in the CVRP successor evidence catalog.

## Main Session Responsibilities

- Keep v3 boundaries intact: CVRP facts remain problem-owned; Decision still
  reads deterministic `DecisionFeatures` only.
- Assign implementation or experiment-analysis tasks to subagents with narrow
  ownership.
- Review target intent, prepared handoff, launch readiness, postrun readiness,
  and final evidence interpretation.
- Decide whether evidence justifies continuation, rejection, parking, or a
  subsequent clean-fork. Do not promote/freeze without positive-at-MDE evidence.

## Worker/Subagent Responsibilities

Implementation worker:

- Use the current CVRP problem-owned guidance and avoid reviewed/suppressed
  mechanism ids.
- Produce a candidate through the normal Scion proposal/contract/verification
  path; do not hardcode CVRP exceptions into generic core.
- Do not add broad helper clusters to existing large files. If implementation
  needs more than a narrow local patch, first define a small problem-owned
  module/package boundary and route through that boundary.
- If selecting the activation-repair path, first prove mechanism activation
  before formal screening.

Analysis worker:

- Summarize current-run pair/case evidence, mechanism activation, feasibility,
  route count, runtime-budget status, MDE comparison, and protected-case
  behavior.
- Call out CMT2 and CMT4 explicitly.
- Classify the outcome as solver-positive-at-MDE, weak-positive-below-MDE,
  no-effect, quality regression, inactive, or infra invalid.

## Run Staging

Server:

- Use for launch preparation, static readiness, postrun report checks, and at
  most 1-2 small/smoke runs.
- Python/env: local conda `claw`.

WSL:

- Use for large or concurrent experiment batches.
- Recheck SSH and `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python` before
  assigning work there.
- Use local `gpt-5.5` model and preserve WSL-origin artifacts as authoritative
  when mirrored back to the server.

Recommended first run shape:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 2 \
  --label v04-cvrp-successor19-cleanfork \
  --model gpt-5.5 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --completion-preflight
```

Do not scale beyond a 2-round focused successor check until the first run shows
valid proposal, contract, verification, formal mechanism evidence, and postrun
readiness.

## Acceptance Evidence

Minimum evidence before interpretation:

- target intent or hypothesis names the new mechanism family;
- material causal-path difference from all reviewed/suppressed families is
  recorded;
- formal mechanism activation observed;
- mechanism-specific objective effect observed;
- pair-level and case-level `total_distance` deltas are available;
- feasibility and route count are preserved or caveated;
- runtime-budget status is valid under `runtime_model=budget_exhausting`;
- CMT2/CMT4 protected-case evidence is reported;
- MDE comparison includes rows-at-or-above-MDE, effect/MDE ratio, and CI.

Promotion/frozen gate:

- Do not promote, freeze, or treat continuation as solver-positive unless at
  least one formal row is positive at or above MDE and protected cases do not
  show unresolved regression evidence.
