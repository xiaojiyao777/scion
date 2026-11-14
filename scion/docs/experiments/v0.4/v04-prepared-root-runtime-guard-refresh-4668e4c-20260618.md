# v0.4 Prepared Root Runtime Guard Refresh 4668e4c

Date: 2026-06-18

## Purpose

The CVRP prepared-handoff measurement diagnostics repair changed launcher and
postrun handoff tooling under `scion/tools`. The previous `0078cac` prepared
roots are superseded because their prepared manifests and delegated handoffs do
not include the new CVRP MDE/low-SNR/opportunity diagnostics.

This refresh regenerates the CVRP and warehouse prepared launch roots from the
WSL checkout at commit `4668e4c`.

## Current Prepared Roots

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-4668e4c-1r-gpt55-1r-gpt55-20260618T182001Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-4668e4c-6r-gpt55-6r-gpt55-20260618T182001Z-claw`

Both roots are prepare-only and remain unstarted.

## Commands

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
export PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion
export SCION_API_KEY=pwd

/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 1 \
  --label v04-cvrp-postpivot-resume-ready-4668e4c-1r-gpt55 \
  --model gpt-5.5 \
  --base-url http://127.0.0.1:8080 \
  --api-key-env SCION_API_KEY \
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
  --label v04-warehouse-v2-followup-ready-4668e4c-6r-gpt55 \
  --model gpt-5.5 \
  --base-url http://127.0.0.1:8080 \
  --api-key-env SCION_API_KEY \
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
- current-run counters remain zero

The CVRP prepared manifest and prepared analysis brief include:

- `screening_mde_at_power_80=9.9`
- `CVRP_MDE_EXCEEDS_PRACTICAL_DELTA`
- `TRAJECTORY_DIVERGENT_LOW_SNR`
- `BUDGET_EXHAUSTING_RUNTIME_REPORT_ONLY`
- four measurable opportunity classes

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

The `0078cac` prepared roots are superseded by the two `4668e4c` roots above.
