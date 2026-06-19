# v0.4 CVRP Phase 4 Four-Round Root Readiness

Date: 2026-06-19

## Purpose

The earlier CVRP bounded two-opt prepared root used one round. That was enough
for a target/patch diagnostic, but Phase 4 effective-research evidence needs at
least some room for branch continuity and follow-up behavior. This refresh
prepares a four-round CVRP root with the same bounded two-opt, source-headroom,
CMT2/CMT4 protection, measurement, and launch-readiness contracts.

## Prepared Root

WSL root:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-a46830e0-preflight-4r-gpt55-20260619T211538Z-claw`

Prepared from WSL checkout `a46830e0`. The current runtime-guard paths are clean
and unchanged by the docs-only commits after `cf8fb5a7`.

Command:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 4 \
  --label v04-cvrp-large-twoopt-phase4-a46830e0-preflight \
  --model gpt-5.5 \
  --base-url http://127.0.0.1:8080 \
  --completion-preflight \
  --python /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 3600 \
  --agentic-tool-max-steps 240 \
  --agentic-tool-max-calls 200 \
  --agentic-code-tool-max-calls 200 \
  --agentic-observation-max-chars 2000000 \
  --proposal-attempt-limit 64 \
  --proposal-quality-loop-limit 64 \
  --stage-transition-drain-limit 4 \
  --resume-from-campaign /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign \
  --measurement-governance on \
  --proposal-context-ablation full \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments
```

## Readiness

Strict readiness:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/check_launch_readiness.py \
  /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-a46830e0-preflight-4r-gpt55-20260619T211538Z-claw \
  --require-launch-ready \
  --format json
```

Result:

- `static_ready=true`
- `launch_ready=false`
- failed check: `completion_preflight`
- completion failure: HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`
- auth pool: `active=0`, `expired=1`, `total=1`
- manifest `rounds=4`
- APS headroom: `3600`/`240`/`200`/`200`/`2000000`
- proposal headroom: `64`/`64`
- bounded two-opt constraints present
- CMT case protection present for `CMT2` and `CMT4`

## Acceptance

Accepted as the current CVRP prepared root once provider auth is restored. It
does not close v0.4; it only gives the CVRP follow-up enough runway to inspect
bounded two-opt target intent, code behavior, branch continuity, effect-vs-MDE,
runtime behavior, and source visibility.
