# v0.4 Postrun Problem-Summary Readiness Guard

Date: 2026-06-19

## Purpose

Postrun acceptance readiness must not report a warehouse or CVRP current run as
delegated-review ready when the problem-specific postrun summary is missing.

Generic runs may still skip problem-specific summary checks. Runs whose
prepared contract or analysis brief declares `problem_family=cvrp` or
`problem_family=warehouse_delivery` now require the matching summary:

- CVRP: `cvrp_large_twoopt_summary`
- Warehouse: `warehouse_followup_summary`

The summary must report `current_run_evidence=true` and
`review_axes_actionability=actionable_current_run_evidence_present` before
`current_run_analysis_ready=true`.

## Boundary

This is a delegated-review readiness guard only.

- It does not change Decision, `DecisionFeatures`, Protocol gates, promotion,
  scheduler state, or solver behavior.
- It does not add broad budgets, truncation, compression, or generic gate
  tightening.
- Warehouse and CVRP semantics remain in problem-owned postrun summaries.

## Verification

Local checkout `dd9cc623`:

```bash
python -m py_compile scion/tools/check_postrun_acceptance.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py

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

Results: focused postrun group `36 passed`; full v0.4 group `80 passed`.

WSL checkout `deb1158`:

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

New prepare-only roots were generated from WSL checkout `deb1158` because
`scion/tools/check_postrun_acceptance.py` is part of the guarded runtime tool
surface.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-deb1158-6r-gpt55-20260619T024307Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-deb1158-1r-gpt55-20260619T024308Z-claw`

Strict launch readiness for both roots reports:

- `static_ready=true`
- `launch_ready=false`
- `postrun_families_complete=ok`
- `prepared_analysis_brief_current=ok`
- `prompt_context_readiness_complete=ok`
- `problem_specific_prepared_handoff=ok`
- `git_runtime_consistent=ok`
- `run.sh` contains `tools/check_postrun_acceptance.py`
- `run.sh` contains `POSTRUN_READINESS_EXIT_STATUS`

The remaining blocker is external `gpt-5.5` auth, not Scion static readiness:
completion preflight returns HTTP `401`, `classification=not_authenticated`,
`code=invalid_api_key`, with auth pool `active=0`, `total=1`.
