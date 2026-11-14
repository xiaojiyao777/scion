# v0.4 Prepared Root Runtime Guard Refresh 317cacb

Date: 2026-06-18

## Purpose

The CVRP prepared-contract measurement handoff repair changed
`scion/tools/postrun_artifact_inventory.py`. The previous `4668e4c` prepared
roots are superseded because their prepared handoff carried the CVRP
measurement diagnostics, but their prepared contract did not require those
fields for static readiness.

This refresh regenerates the CVRP and warehouse prepared launch roots from the
WSL checkout at commit `317cacb`.

## Current Prepared Roots

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-317cacb-1r-gpt55-1r-gpt55-20260618T183304Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-317cacb-6r-gpt55-6r-gpt55-20260618T183318Z-claw`

Both roots are prepare-only and remain unstarted.

## Readiness Result

Static readiness passed for both roots:

- `static_ready=true`
- `git_runtime_consistent=ok`
- `prepared_contract_complete=ok`
- `prepared_only_not_started=ok`
- current-run counters remain zero

The CVRP prepared contract now also passes the CVRP-only measurement handoff
checks:

- `cvrp_measurement_handoff_present=true`
- `cvrp_measurement_handoff_report_only=true`
- `cvrp_measurement_handoff_mde_present=true`
- `cvrp_measurement_handoff_reason_codes=true`
- `cvrp_measurable_opportunity_classes_present=true`

The CVRP prepared manifest records:

- `git.commit=317cacb`
- `screening_mde_at_power_80=9.9`
- `practical_screen_delta=2.0`
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

## Verification

WSL checkout:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
export PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion

/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_analysis_brief.py
# 42 passed
```

## Superseded Prepared Roots

The `4668e4c` prepared roots are superseded by the two `317cacb` roots above.
