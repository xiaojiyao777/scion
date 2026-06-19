# v0.4 Champion Progress Input Consistency

Date: 2026-06-19

## Purpose

Warehouse follow-up depends on knowing whether a run resumed from Champion v2
actually advanced the current-run champion table. `champion_progress_summary`
made that progress visible, but readiness also needs to reject a stale or
hand-written summary that disagrees with the current inventory.

## Change

`check_postrun_acceptance` now recomputes the expected
`champion_progress_summary` from `postrun_artifact_inventory` and compares the
analysis brief summary against it for warehouse/CVRP current-run review.

The consistency guard checks:

- current-run evidence, availability, and interpretation;
- starting/current champion version and champion version gain;
- champion table presence, count, versions, max weight revision, and promotion
  metadata counts;
- latest promotion experiment/dossier refs;
- promoted hypothesis and promotion decision counts.

The check remains report-only. It does not require a promotion or a positive
result.

## Boundary

This is delegated-review input consistency only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion inputs, scheduler state,
campaign state, proposal generation, problem solvers, or runtime budgets.

## Verification

Local checkout with uncommitted change:

```bash
python -m py_compile \
  scion/tools/check_postrun_acceptance.py \
  scion/scion/tests/test_check_postrun_acceptance.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  -k 'champion_progress or accepts_actionable_problem_summary'
# 3 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 70 passed
```
