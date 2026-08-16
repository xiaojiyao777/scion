# CVRP Successor21 Adaptive Destroy-Size In-Flight - 2026-06-29

## Status

Successor21 completed on WSL. This in-flight record is retained for launch
chronology; interpretation is superseded by
`scion/docs/experiments/v0.4/v04-cvrp-successor21-adaptive-destroy-size-postrun-20260629.md`.

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor21-adaptive-destroy-size-2r-gpt55-20260629T172740Z-claw`
- WSL runner repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629`
- Runner commit used by `run.sh`: `a27fa2ec`
- Wrapper pid: `43030` (exited)
- Started UTC: `2026-06-29T17:28:51Z`
- Model route: `gpt-5.5` via `http://127.0.0.1:8080`
- Launch readiness: `launch_ready=true`
- Completion preflight: `ok`, HTTP 200, authenticated local proxy

The earlier prepared root ending `20260629T172507Z-claw` was not launched
because its runtime guard detected dirty CVRP guidance files after sync. The
active root is the later `20260629T172740Z-claw` root.

## Purpose

Run a 2-round CVRP solver-design successor for
`stagnation_adaptive_destroy_size_schedule`.

The mechanism is a CVRP-owned scheduler policy that should change ALNS destroy
magnitude `q` before existing destroy/repair operators run. It is not a repeat
of bounded route-segment local search, seed-post activation repair, acceptance
tuning, adaptive operator weighting, or a new removal operator.

## Prepared Context

Before launch, the problem-owned CVRP guidance was updated so prepared context
matches the current v0.4 evidence:

- `bounded_route_segment_exchange` is reviewed as successor20 active
  zero-effect below-MDE evidence.
- `seed_post_optimization_selector` remains a deferred diagnostic fallback.
- `scheduler_destroy_size_policy` is the first successor opportunity family.
- `stagnation_adaptive_destroy_size_schedule` is the prepared current slot.
- Measurement diagnostics rank `scheduler_destroy_size_policy` first and point
  the top recipe at `policies/baseline_modules/scheduler.py`.

The WSL runner copy has a local commit, `a27fa2ec`, containing only the runtime
CVRP guidance changes needed to satisfy the launch runtime guard. Local source
changes remain uncommitted in the main checkout.

## Launch Command

Prepare command used from the WSL runner repo:

```bash
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

Launch readiness command:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/check_launch_readiness.py \
  /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor21-adaptive-destroy-size-2r-gpt55-20260629T172740Z-claw \
  --completion-preflight \
  --require-launch-ready
```

Background launch command:

```bash
cd /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor21-adaptive-destroy-size-2r-gpt55-20260629T172740Z-claw
nohup setsid bash run.sh > nohup.log 2>&1 &
```

## Acceptance Focus

Postrun analysis must check:

- live hypothesis names `stagnation_adaptive_destroy_size_schedule`;
- proposal is not a disguised acceptance/weight/local-search repeat;
- candidate changes actual destroy-size `q` before existing destroy/repair
  operators run;
- activation/decision telemetry is present under the mechanism id;
- q distribution or ALNS trace evidence differs from fixed-ratio behavior;
- formal rows are complete and interpreted against MDE;
- CMT2/CMT4 case-level deltas are visible;
- postrun acceptance readiness is ready.

If the run completes but no row reaches MDE, classify it as evidence-complete
below-MDE rather than solver-positive.
