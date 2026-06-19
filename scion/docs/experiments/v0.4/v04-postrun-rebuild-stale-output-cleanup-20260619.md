# Postrun Rebuild Stale Output Cleanup

Date: 2026-06-19

## Purpose

`rebuild_postrun_acceptance.py` now removes stale generated `.json` and `.md`
files from standard postrun family directories before writing a fresh bundle.
This keeps regenerated analysis briefs and inventories from aggregating old
`research_efficiency`, trajectory-manifest, analysis-brief, or inventory files
that happen to remain in `postrun_acceptance/`.

This is report-bundle hygiene only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, or solver
behavior.

## Acceptance Evidence

- Added a regression fixture that pre-creates stale generated postrun files
  before rebuild, then asserts the stale files are removed and the rebuilt
  inventory counts only the current bundle outputs.
- Local:
  - `python -m py_compile scion/tools/rebuild_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py`
  - `PYTHONPATH=scion pytest -q scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py`
- WSL:
  - `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile scion/tools/rebuild_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py`
  - `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_check_postrun_acceptance.py`

## Result

Accepted as a postrun acceptance hardening repair. After launch, warehouse and
CVRP delegated review should consume the freshly rebuilt postrun bundle rather
than stale generated files left by earlier rebuild attempts.

Because this repair touches `scion/tools`, the active prepared roots were
regenerated from WSL runtime commit `77d0254`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-staleclean-77d0254-6r-gpt55-6r-gpt55-20260619T143306Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-staleclean-77d0254-1r-gpt55-1r-gpt55-20260619T143306Z-claw`

Strict WSL launch readiness for both regenerated roots reports
`static_ready=true`, `launch_ready=false`; the remaining blocker is the external
`gpt-5.5` provider auth preflight returning HTTP `401` /
`classification=not_authenticated` / `code=invalid_api_key`.
