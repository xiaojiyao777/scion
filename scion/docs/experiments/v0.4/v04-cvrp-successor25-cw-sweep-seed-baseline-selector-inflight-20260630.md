# CVRP Successor25 CW/Sweep Seed Baseline Selector In-Flight - 2026-06-30

## Run Identity

- Run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-2r-gpt55-20260630T101601Z-claw`
- WSL runner repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629`
- Runner commit: `d501b900`
- Wrapper PID: `94489`
- Model route: `gpt-5.5` via `http://127.0.0.1:8080`
- Start: `2026-06-30T10:16:01Z`
- Completion preflight: enabled

## Launch Shape

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

## Prepared Focus

- Mechanism: `cw_sweep_seed_baseline_selector`
- Primary target:
  `policies/baseline_modules/construction.py`
- Minimal wiring:
  `policies/baseline_modules/scheduler.py`
- Required evidence: direct same-run selected-seed versus baseline
  `total_distance` delta before downstream ALNS/VNS.

## Current Status

The wrapper reported `status=running` after launch. Treat this as an active WSL
campaign until `run_status.json` reports completion and postrun acceptance is
ready.

## Next Check

Inspect:

- `run_status.json`
- `campaign/campaign_summary.json`
- `postrun_acceptance/readiness/cvrp_on_full.postrun_acceptance_readiness.v1.json`
- `postrun_acceptance/research_efficiency/cvrp_on_full.research_efficiency.v1.json`

Interpret against the successor25 plan:
`scion/docs/experiments/v0.4/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-plan-20260630.md`.
