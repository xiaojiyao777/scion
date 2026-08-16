# CVRP Successor20 Bounded Segment Refine In-Flight - 2026-06-29

## Purpose

Track the WSL follow-up run launched after successor19. This is an in-flight
record, not a postrun interpretation.

Superseded for interpretation by:

```text
scion/docs/experiments/v0.4/v04-cvrp-successor20-bounded-segment-refine-postrun-20260629.md
```

Successor19 was framework-positive but solver-negative/below-MDE. The active
branch for `bounded_route_segment_exchange` remained schedulable with marginal
evidence and allowed same-branch actions. Successor20 therefore continues that
branch rather than treating successor19 as v0.4 closeout evidence.

## Source Run

Server-local completed source root:

```text
/home/clawd/research/scion-experiments/v04-cvrp-successor19-cleanfork-local-2r-gpt55-20260629T133200Z-claw
```

The source root was mirrored to WSL before prepare:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor19-cleanfork-local-2r-gpt55-20260629T133200Z-claw
```

Resume source:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor19-cleanfork-local-2r-gpt55-20260629T133200Z-claw/campaign
```

## Prepared Root

WSL run root:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor20-bounded-segment-refine-2r-gpt55-20260629T150851Z-claw
```

Prepare command shape:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 2 \
  --label v04-cvrp-successor20-bounded-segment-refine \
  --model gpt-5.5 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --completion-preflight \
  --resume-from-campaign /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor19-cleanfork-local-2r-gpt55-20260629T133200Z-claw/campaign \
  --force-surface solver_design \
  --force-action modify \
  --force-target-file policies/baseline_modules/local_search.py \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments
```

Rationale for force constraints:

- `solver_design` keeps the task inside the problem-owned CVRP solver-design
  surface.
- `modify` is the valid hypothesis action for an existing target file.
- `policies/baseline_modules/local_search.py` keeps the follow-up on the
  successor19 mechanism target rather than drifting to an unrelated mechanism.

## Readiness

Strict launch readiness passed before launch:

- `launch_ready=true`
- `static_ready=true`
- `failed_required_checks=[]`
- `launch_blockers=[]`
- completion preflight `ok`
- HTTP 200
- completion classification `healthy`
- auth pool active `1/1`
- runtime guard status `ok`
- runtime guard worktree dirty entries `[]`
- prepared runtime commit `8bde8c82`

Prepared handoff checks included CVRP CMT case protection, resume continuity,
measurement/MDE handoff, protected cases in the screening split, and
problem-owned direct-effect rules.

## Launch

Launch time observed in wrapper log:

```text
2026-06-29T15:10:02Z
```

Launch PID:

```text
21775
```

Initial status:

- root `run_status.json`: `status=running`
- pre-campaign completion preflight passed with HTTP 200
- campaign execution marker written at `2026-06-29T15:10:04Z`
- campaign command includes:
  - `--rounds 2`
  - `--force-surface solver_design`
  - `--force-action modify`
  - `--force-target-file policies/baseline_modules/local_search.py`

Initial log note:

```text
Branch 7431c39c-2fe9-4d5c-bf79-b34d60d9f930: partial hypothesis idempotency_key mismatch ... starting fresh
```

This is not an immediate launch failure. The campaign continued after the
resume/fresh-hypothesis notice.

## Current Progress Snapshot

Observed at approximately `2026-06-29T15:18Z`:

- root status: `running`
- wrapper/campaign exit statuses: not set
- campaign accounting:
  - `proposal_attempts_total=1`
  - `proposal_quality_blocks=0`
  - `formal_screened_candidates=0`
  - `protocol_metric_results=0`
  - `effective_rounds_completed=0`
- current-run smoke metrics were written:
  - `campaign/metrics/v8_run1_4277ea40.json`
  - `campaign/metrics/v8_run2_4277ea40.json`
- current-run screening metrics in progress:
  - `campaign/metrics/b0f7c15a-660c-45ad-b6f5-742ccb3868f0.json`
  - `stage=screening`
  - `complete=false`
  - `valid_pairs=4`
  - `total_pairs=32`
  - `failed_pairs=0`
  - interim pair counts: `2 wins / 2 losses / 0 ties`
- `campaign/artifacts/formal_candidates/index.jsonl` was not yet written at
  the snapshot time.

The in-progress metrics file is not final evidence. Interpret only after the
campaign and postrun acceptance complete.

## Analysis Assignment

Hypatia is assigned read-only experiment analysis after launch. The requested
analysis scope is:

- proposal flow and mechanism id/target;
- quality blocks;
- protocol rows and screening outcomes;
- case-level wins/losses/ties;
- CMT2, CMT4, and CMT3 behavior;
- MDE and effect-to-MDE interpretation;
- postrun acceptance readiness;
- classification as solver-positive-at-MDE, weak-positive-below-MDE,
  no-effect, quality regression, inactive, or infra invalid.

## Interpretation Boundary

Do not interpret this run as solver evidence until postrun reports are ready.
The intended acceptance threshold remains unchanged: no promotion, freeze, or
v0.4 closeout claim without positive-at-or-above-MDE evidence and acceptable
protected-case behavior.
