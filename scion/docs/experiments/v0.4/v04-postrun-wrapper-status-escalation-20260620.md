# v0.4 Postrun Wrapper Status Escalation

Date: 2026-06-20

## Purpose

Close the launcher evidence gap where strict postrun acceptance readiness could
fail after a campaign finished, but the outer wrapper still exited with the
campaign status and left top-level status looking successful.

## Current Guarantee

Warehouse and CVRP launcher wrappers now:

- return nonzero when strict postrun report rebuild/readiness fails after a
  campaign run;
- annotate `exit.txt` with `POSTRUN_ACCEPTANCE_FAILED` and effective postrun
  exit markers;
- update top-level `run_status.json` with `postrun_acceptance_failed`,
  postrun report/readiness exit statuses, and the original campaign wrapper
  status.

This keeps current-run postrun acceptance as an operational gate instead of a
log-only advisory.

## Verification

Local verification:

```bash
python -m py_compile scion/tools/write_postrun_wrapper_status.py scion/tools/launch_warehouse_agentic_campaign.py scion/tools/launch_cvrp_agentic_campaign.py scion/tools/postrun_artifact_inventory.py
pytest -q scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py
pytest -q scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py
pytest -q scion/scion/tests/test_postrun_artifact_inventory.py -k 'launcher or status or inventory or preflight or runtime_guard'
```

Observed result: py_compile passed; launcher tests `25 passed`; postrun
acceptance tests `58 passed`; focused inventory tests `14 passed`.
