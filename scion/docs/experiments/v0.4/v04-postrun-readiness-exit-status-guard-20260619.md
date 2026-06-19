# v0.4 Postrun Readiness Exit-Status Guard

Date: 2026-06-19

## Purpose

`POSTRUN_READINESS_EXIT_STATUS` must indicate whether the generated postrun
readiness report says current-run delegated analysis is ready. Before this
repair, launchers generated readiness JSON without
`--require-current-run-ready`, so the marker could stay `0` even when the JSON
said `current_run_analysis_ready=false`.

## Change

CVRP and warehouse launchers now run:

```bash
check_postrun_acceptance.py "$RUN_ROOT" \
  --require-current-run-ready \
  --format json
```

The JSON is still written before the checker returns. The launcher captures the
exit status and records it as `POSTRUN_READINESS_EXIT_STATUS`.

Expected marker semantics:

- `0`: postrun bundle exists and current-run analysis is ready.
- `64`: postrun bundle exists, but current-run analysis is not ready.
- Other nonzero: checker/tool failure.

The Markdown readiness report remains non-strict for readable diagnostics.

## Boundary

This is a report/launcher marker fix only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, campaign
validity, or problem solver behavior.

## Verification

Local checkout `bff448db`:

```bash
python -m py_compile \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py \
  scion/tools/check_postrun_acceptance.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_launch_readiness.py

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

Results: focused launcher/readiness group `48 passed`; full v0.4 group
`80 passed`.

WSL checkout `7f21623`:

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

Result: `80 passed`.

## Current Prepared Roots

New prepare-only roots were generated from WSL checkout `7f21623` because the
launcher `run.sh` template changed.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-7f21623-6r-gpt55-20260619T025154Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-7f21623-1r-gpt55-20260619T025155Z-claw`

Strict launch readiness for both roots reports:

- `static_ready=true`
- `launch_ready=false`
- `postrun_families_complete=ok`
- `prepared_analysis_brief_current=ok`
- `prompt_context_readiness_complete=ok`
- `problem_specific_prepared_handoff=ok`
- `git_runtime_consistent=ok`
- `run.sh` contains `--require-current-run-ready`
- `run.sh` contains `POSTRUN_READINESS_EXIT_STATUS`

The remaining blocker is external `gpt-5.5` auth, not Scion static readiness:
completion preflight returns HTTP `401`, `classification=not_authenticated`,
`code=invalid_api_key`, with auth pool `active=0`, `total=1`.
