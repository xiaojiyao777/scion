# Prepared Handoff Output Cleanup

Date: 2026-06-19

## Purpose

`rebuild_prepared_handoff.py` now removes stale generated `.json` and `.md`
files from standard prepared-handoff family directories before writing a fresh
bundle.

`check_launch_readiness.py` now checks
`prepared_handoff/rebuild/prepared_handoff_rebuild.v1.json` and rejects missing,
inconsistent, or undeclared generated outputs in ok prepared-handoff families.
This keeps delegated launch review from consuming stale handoff files left by
older rebuild attempts.

It also validates the rebuild manifest identity and boundary flags before the
prepared bundle can be static-ready: schema, artifact kind, root path, handoff
directory, problem family, prepared manifest commit, report-only flags, state
mutation flags, and `complete=true`.

This is report-bundle hygiene only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, or solver
behavior.

## Acceptance Evidence

- Added a rebuild regression that pre-creates stale prepared-handoff generated
  files, rebuilds, then asserts the stale files are removed and the manifest
  records all declared outputs as present.
- Added a launch-readiness regression that leaves manifest-declared outputs
  intact but injects an undeclared stale generated file; launch readiness now
  fails with `unexpected_outputs`.
- Added launch-readiness regressions for rebuild-manifest identity mismatch and
  report-only/complete boundary gaps; launch readiness now fails with
  `manifest_failures`.
- Local:
  - `python -m py_compile scion/tools/rebuild_prepared_handoff.py scion/tools/check_launch_readiness.py scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_launch_readiness.py`
  - `PYTHONPATH=scion pytest -q scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_launch_readiness.py`
  - `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py`
  - `git diff --check`
- WSL:
  - `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile scion/tools/rebuild_prepared_handoff.py scion/tools/check_launch_readiness.py scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_launch_readiness.py`
  - `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_launch_readiness.py`
  - `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py`
  - `git diff --check`

## Result

Accepted as a prepared-launch handoff hardening repair. Because this touches
`scion/tools`, the active prepared roots were regenerated from WSL runtime
commit `ae757fe`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-handoffmanifest-ae757fe-6r-gpt55-6r-gpt55-20260619T150324Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-handoffmanifest-ae757fe-1r-gpt55-1r-gpt55-20260619T150324Z-claw`

Strict WSL launch readiness for both regenerated roots reports
`static_ready=true`, `prepared_handoff_rebuild_declared_outputs_present=ok`,
`manifest_failures=[]`, `family_failures=[]`, no missing/unexpected outputs,
and `launch_ready=false`. The remaining blocker is the external `gpt-5.5`
provider auth preflight returning HTTP `401` /
`classification=not_authenticated` / `code=invalid_api_key`, with auth pool
`active=0`, `expired=1`, `refreshing=0`, `total=1`.
