# v0.4 Prepared Root Runtime Guard Refresh f481f15

Date: 2026-06-18

## Purpose

The research-continuity report metrics repair changed
`scion/scion/core/research_efficiency_report.py`, which is covered by the
prepared-root runtime guard path `scion/scion`. Existing `bd3e0d7` prepared
roots therefore failed launch-readiness static checks with
`git_runtime_consistent=failed`.

This refresh regenerates the CVRP and warehouse prepared launch roots from the
WSL checkout at commit `f481f15`.

## Current Prepared Roots

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-f481f15-1r-gpt55-1r-gpt55-20260618T162746Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-f481f15-6r-gpt55-6r-gpt55-20260618T162746Z-claw`

Both roots are prepare-only and remain unstarted.

## Commands

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
export PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion
export SCION_API_KEY=pwd

/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 1 \
  --label v04-cvrp-postpivot-resume-ready-f481f15-1r-gpt55 \
  --model gpt-5.5 \
  --base-url http://127.0.0.1:8080 \
  --completion-preflight \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 900 \
  --stage-transition-drain-limit 4 \
  --control-pair-key cvrp.postpivot-resume:rep01 \
  --resume-from-campaign /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments

/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_warehouse_agentic_campaign.py \
  --rounds 6 \
  --label v04-warehouse-v2-followup-ready-f481f15-6r-gpt55 \
  --model gpt-5.5 \
  --base-url http://127.0.0.1:8080 \
  --completion-preflight \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 900 \
  --warehouse-data-root /home/xjy-ubuntu/research/scion-data \
  --control-pair-key warehouse.v2-followup:rep01 \
  --resume-from-campaign /home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments
```

## Readiness Result

Static readiness passed for both roots:

- `static_ready=true`
- `git_runtime_consistent=ok`
- `prepared_contract_complete=ok`
- `prepared_only_not_started=ok`
- `zero_current_run_counters=ok`
- `postrun_acceptance_not_present=ok`

Completion preflight still fails for infrastructure/auth only:

- HTTP status: `401`
- classification: `not_authenticated`
- code: `invalid_api_key`
- `authenticated=false`
- pool: `active=0`, `expired=1`, `refreshing=0`
- readiness includes `operator_action.login_url`

Do not start either root until
`scion/tools/check_launch_readiness.py <root> --completion-preflight --format json`
returns `launch_ready=true`.

## Superseded Prepared Roots

The `bd3e0d7` prepared roots are superseded by the two `f481f15` roots above.
An intermediate `20260618T162645Z` refresh was also superseded before launch
because it omitted the report-only `control_pair_key` metadata required by the
prepared contract check.
