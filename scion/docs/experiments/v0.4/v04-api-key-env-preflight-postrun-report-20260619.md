# v0.4 API-Key-Env Preflight Postrun Report

Date: 2026-06-19

## Purpose

Launcher API-key environment validation happens before `scion.cli.main run`. If
that pre-campaign infrastructure check fails, the prepared root should still
leave the same report-only postrun/readiness bundle used by other infra-only
failures, rather than only `exit.txt` and `run_status.json`.

## Change

- `launch_warehouse_agentic_campaign.py` and
  `launch_cvrp_agentic_campaign.py` now define and call
  `write_postrun_acceptance_reports` for `SCION_API_KEY_ENV_MISSING` failures
  before wrapper exit.
- `check_launch_readiness.py` now requires
  `run_script_api_key_env_failure_reports=ok` whenever a prepared `run.sh`
  contains a `SCION_API_KEY_ENV_MISSING` branch.
- This is symmetric across warehouse and CVRP prepared roots. Warehouse still has
  the extra `run_script_data_root_failure_reports` path; CVRP reports that
  data-root path as not applicable when no warehouse data-root branch exists.

## Boundary

This is launcher/readiness/report-only infrastructure handling. It does not
change Decision, `DecisionFeatures`, Protocol gates, promotion, scheduler state,
proposal semantics, runtime budgets, or warehouse/CVRP solver behavior.

## Verification

Local checkout `a3697976`:

```bash
python -m py_compile \
  scion/tools/check_launch_readiness.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Results: targeted launcher/readiness group `50 passed`; full v0.4
readiness/reporting group `94 passed`.

WSL checkout `5e76640`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Result: full v0.4 readiness/reporting group `94 passed`.

## Current Prepared Roots

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-apikeyenvreport-ready-6r-gpt55-20260619T042350Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-apikeyenvreport-ready-1r-gpt55-20260619T042350Z-claw`

Static launch readiness for both roots reports `ready=true`,
`static_ready=true`, `launch_ready=false`, `git_runtime_consistent=ok`,
`runtime_guard_paths_cover_launch_tools=ok`,
`run_script_runtime_guard_enforced=ok`,
`run_script_postrun_reports_after_campaign=ok`,
`run_script_api_key_env_failure_reports=ok`,
`run_script_strict_postrun_readiness=ok`,
`prepared_analysis_brief_current=ok`, `prompt_context_readiness_complete=ok`,
`problem_specific_prepared_handoff=ok`, and `postrun_families_complete=ok`.
Warehouse also requires `run_script_data_root_failure_reports=ok`; CVRP reports
that check as not applicable under the same `ok` status.

Strict readiness with `--require-launch-ready` still fails only on external
`gpt-5.5` completion preflight: HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`, auth pool
`active=0`, `expired=0`, `refreshing=1`, `total=1`.
