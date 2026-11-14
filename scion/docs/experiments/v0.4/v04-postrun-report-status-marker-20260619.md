# v0.4 Postrun Report Status Marker

Date: 2026-06-19

## Purpose

Launcher postrun acceptance rebuilds are report-only and should not turn a
completed campaign into a solver/runtime failure. But their success or failure
must be visible in the run artifacts so delegated review can tell whether the
analysis bundle was actually rebuilt.

## Change

- CVRP and warehouse launcher `run.sh` templates now emit
  `POSTRUN_REPORTS_EXIT_STATUS:<code>` after calling
  `rebuild_postrun_acceptance.py`.
- `postrun_artifact_inventory.py` recognizes the marker under
  `launcher.run_log_markers`.
- The launcher still records postrun rebuild status without changing Decision,
  Protocol gates, promotion, scheduler state, or solver behavior.

## Boundary Check

- This is report-only auditability for launch/postrun artifacts.
- It does not add a budget, truncation, compression, generic gate, or runtime
  failure policy.
- CVRP and warehouse semantics remain in problem-owned handoff and postrun
  summaries.

## Current Prepared Roots

The current launch-prepared roots remain the `399db52` roots. Strict readiness
from WSL reports the checkout differs only outside runtime guard paths.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-399db52-6r-gpt55-20260619T015826Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-399db52-1r-gpt55-20260619T015826Z-claw`

## Readiness Evidence

Both roots still report:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- detail: `checkout differs, but runtime guard paths are unchanged`
- `prepared_analysis_brief_current=ok`
- completion preflight `failed`
- HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`

The current blocker remains external `gpt-5.5` auth, not Scion static readiness.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 75 passed
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 75 passed
```
