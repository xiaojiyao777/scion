# v0.4 Postrun Quality-Blocked Readiness

Date: 2026-06-19

## Purpose

Repair delegated postrun readiness so valid negative conclusions are not
mistaken for missing plateau evidence.

Warehouse and CVRP problem summaries can report a quality-blocked no-protocol
conclusion when proposal quality blocks prevent protocol evaluation. That
conclusion is current-run-analysis-ready only when supported by current-run
failure-taxonomy evidence. Missing measurement-effect, runtime-feedback, and
research-continuity plateau inputs are nonblocking only for that
quality-blocked interpretation.

Protocol-evaluated plateau or mechanism conclusions still require their
measurement/runtime/continuity review inputs and recomputed consistency checks.

## Code Change

- `scion/tools/check_postrun_acceptance.py`
  - Makes problem-summary blocking gaps interpretation-specific.
  - Makes required review-input summaries interpretation-specific.
  - Keeps stale or unsupported quality-blocked claims blocked by
    `problem_summary_input_consistency`.
- `scion/scion/tests/test_check_postrun_acceptance.py`
  - Adds acceptance coverage for taxonomy-backed warehouse
    `quality_blocked_no_protocol_plateau_conclusion`.
  - Adds rejection coverage when the problem summary claims quality blocking
    without matching `failure_taxonomy_summary` signal.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py -k 'quality_blocked'
PYTHONPATH=scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py
```

Results:

- `2 passed, 32 deselected`
- `34 passed`
- `130 passed`

WSL runner:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_check_postrun_acceptance.py -k quality_blocked
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py
```

Results:

- `2 passed, 32 deselected`
- `130 passed`

## Prepared Root Refresh

Because `scion/tools/check_postrun_acceptance.py` and
`scion/tools/check_launch_readiness.py` are part of the prepared-root runtime
guard surface, the active warehouse/CVRP roots were regenerated after this
repair from WSL runtime commit `fb2a9b7`.

The launch-readiness prepared-contract consistency check also now normalizes
successful doc-only `git_runtime_consistent` detail drift. A docs-only status
update after preparing these roots must not make the prepared analysis brief
look stale when runtime guard paths are unchanged.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-qualityblock-fb2a9b7-6r-gpt55-6r-gpt55-20260619T134530Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-qualityblock-fb2a9b7-1r-gpt55-1r-gpt55-20260619T134530Z-claw`

Strict launch readiness with `SCION_API_KEY=pwd`:

- Warehouse: exit `64`, `static_ready=true`, `launch_ready=false`,
  `git_runtime_consistent=ok`.
- CVRP: exit `64`, `static_ready=true`, `launch_ready=false`,
  `git_runtime_consistent=ok`.
- The only launch blocker remains completion preflight auth:
  HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`,
  auth pool `active=0`, `expired=0`, `refreshing=1`, `total=1`.

## Boundary Check

This is report-only delegated-analysis readiness. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, or solver
behavior.
