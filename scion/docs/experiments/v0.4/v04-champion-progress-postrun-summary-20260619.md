# v0.4 Champion Progress Postrun Summary

Date: 2026-06-19

## Purpose

Warehouse follow-up validation needs a machine-readable positive-progress
signal, not only guards against premature plateau conclusions. A run resumed
from warehouse Champion v2 should make it obvious whether the current campaign
advanced the champion table to a later version.

This also gives CVRP/VRP postrun review a consistent place to inspect promotion
progress without treating copied resume history as current-run evidence.

## Change

`postrun_artifact_inventory` now reports current-run `champions` table
inventory for launched campaigns and keeps copied resume DB champion counts
separate under `resume_snapshot`.

`postrun_analysis_brief` now emits
`champion_progress_summary`:

- schema `scion.postrun_champion_progress_summary.v1`;
- report-only and excluded from decision features;
- compares the prepared research focus starting champion version against the
  current-run champion table max version;
- reports hypothesis/event promotion counts as supporting signals only.

`check_postrun_acceptance` now requires this report-only summary to be
actionable for warehouse and CVRP runs. It does not require a promotion; it only
requires the summary contract to be current-run, report-only, non-mutating, and
interpretable.

## Boundary

This is postrun observability only. It does not change `DecisionFeatures`,
Protocol gates, promotion inputs, scheduler state, proposal semantics, campaign
state, solvers, or runtime budgets.

## Verification

Local checkout with uncommitted change:

```bash
python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 67 passed
```

## Launch Impact

Prepared roots must be regenerated after this repair so the postrun acceptance
bundle in the next warehouse and CVRP launches includes
`champion_progress_summary`.
