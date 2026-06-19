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

Local checkout `5ddab100`:

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

WSL checkout `6fcfb05`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 67 passed
```

## Launch Impact

Prepared roots were regenerated from WSL runtime commit `6fcfb05` so the
postrun acceptance bundle in the next warehouse and CVRP launches includes
`champion_progress_summary`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-champprog-6fcfb05-6r-gpt55-20260619T121318Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-champprog-6fcfb05-1r-gpt55-20260619T121332Z-claw`

Strict launch readiness for both roots reports `static_ready=true`,
`git_runtime_consistent=ok`, and `launch_ready=false` because real GPT-5.5
completion preflight still returns HTTP `401`, `classification=not_authenticated`,
`code=invalid_api_key`.
