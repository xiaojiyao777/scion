# v0.4 Warehouse Data-Root Preflight Postrun Report

Date: 2026-06-19

## Purpose

Warehouse data-root validation happens before `scion.cli.main run`. If that
pre-campaign infrastructure check fails, the root should still leave the same
report-only postrun/readiness bundle used by other infra-only failures, rather
than only `exit.txt` and `run_status.json`.

## Change

- `launch_warehouse_agentic_campaign.py` now calls
  `write_postrun_acceptance_reports` after writing
  `warehouse_data_root_missing=true` and before exiting the wrapper.
- `check_launch_readiness.py` now requires
  `run_script_data_root_failure_reports=ok` whenever a prepared `run.sh`
  contains a `WAREHOUSE_DATA_ROOT_MISSING` branch.
- CVRP roots pass this check as not applicable because they have no warehouse
  data-root failure path.

## Boundary

This is launcher/readiness/report-only infrastructure handling. It does not
change Decision, `DecisionFeatures`, Protocol gates, promotion, scheduler state,
proposal semantics, runtime budgets, or warehouse/CVRP solver behavior.

## Verification

Local checkout `46cb1fdb`:

```bash
python -m py_compile \
  scion/tools/check_launch_readiness.py \
  scion/tools/launch_warehouse_agentic_campaign.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
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

Results: launch-readiness plus warehouse launcher group `34 passed`; full v0.4
readiness/reporting group `93 passed`.

WSL checkout `199154c`:

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

Result: full v0.4 readiness/reporting group `93 passed`.

## Current Prepared Roots

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-datarootreport-ready-6r-gpt55-20260619T041452Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-datarootreport-ready-1r-gpt55-20260619T041453Z-claw`

Strict launch readiness for both roots reports `static_ready=true`,
`run_script_data_root_failure_reports=ok`,
`run_script_postrun_reports_after_campaign=ok`,
`run_script_runtime_guard_enforced=ok`, `run_script_strict_postrun_readiness=ok`,
`prepared_analysis_brief_current=ok`, `prompt_context_readiness_complete=ok`,
`problem_specific_prepared_handoff=ok`, `postrun_families_complete=ok`, and
`runtime_guard_paths_cover_launch_tools=ok`.

Launch readiness remains blocked only by external `gpt-5.5` completion
preflight: HTTP `401`, `classification=not_authenticated`,
`code=invalid_api_key`, auth pool `active=0`, `expired=1`, `refreshing=0`,
`total=1`.
