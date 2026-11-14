# v0.4 Postrun Review Surface Boundary Markers

Date: 2026-06-19

## Purpose

Warehouse and CVRP delegated review depends on prompt/source visibility,
research-context, signal-density, and failure-taxonomy summaries. These
summaries are review surfaces, not Decision input. Readiness must reject stale
or hand-written summaries that provide plausible counts but omit the report-only,
raw-excluded, or `DecisionFeatures`-excluded boundary markers.

## Change

`check_postrun_acceptance` now validates boundary markers on the remaining
warehouse/CVRP delegated-review surfaces:

- `prompt_context_visibility_summary` must use the current schema, remain
  report-only, avoid quality judgment, exclude `DecisionFeatures`, and mark raw
  prompts, raw responses, and patch bodies as excluded.
- nested `prompt_source_visibility` and prompt signal-density summaries must use
  current schemas and remain report-only/`DecisionFeatures`-excluded.
- `research_context_actionability_summary` must use the current schema and
  preserve report-only, non-quality-judgment, `DecisionFeatures`-excluded
  markers.
- `failure_taxonomy_summary` must use the current schema, preserve the same
  boundary markers, and mark raw logs as excluded.

The readiness detail now reports expected schema and boundary marker values so
review failures are auditable without exposing raw prompts, responses, patch
bodies, or logs.

## Boundary

This is postrun delegated-review readiness only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion inputs, scheduler state,
campaign state, proposal generation, problem solvers, runtime budgets, or
problem-specific solver semantics.

## Verification

Local checkout `2bcea61c`:

```bash
python -m py_compile \
  scion/tools/check_postrun_acceptance.py \
  scion/scion/tests/test_check_postrun_acceptance.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  -k 'prompt_source_visibility or research_context or failure_taxonomy or review_surface_boundary'
# 4 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py
# 31 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 71 passed
```

WSL checkout `865e0fb`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 71 passed
```

## Launch Impact

Because `scion/tools/check_postrun_acceptance.py` is part of the guarded runtime
surface, prepared roots were regenerated from WSL runtime commit `865e0fb`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-boundarymarkers-865e0fb-6r-gpt55-20260619T125317Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-boundarymarkers-865e0fb-1r-gpt55-20260619T125317Z-claw`

Strict launch readiness for both roots reports `static_ready=true`,
`git_runtime_consistent=ok`, and `launch_ready=false` because real GPT-5.5
completion preflight still returns HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`, with auth pool
`active=0`, `refreshing=1`, `total=1`.
