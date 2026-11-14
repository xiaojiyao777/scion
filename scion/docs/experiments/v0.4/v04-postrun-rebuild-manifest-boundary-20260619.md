# Postrun Rebuild Manifest Boundary

Date: 2026-06-19

## Purpose

Postrun acceptance readiness now rejects rebuild manifests whose identity or
report-only boundary flags drift. This closes the remaining checker-layer gap
after output-scope validation: a hand-edited or stale
`postrun_acceptance/rebuild/rebuild_manifest.v1.json` can no longer keep the
declared output bundle while claiming the wrong artifact kind, report directory,
or state-mutation boundary.

This is delegated-review artifact hygiene only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, or solver
behavior.

## Code Change

- `scion/tools/check_postrun_acceptance.py` adds required check
  `rebuild_manifest_identity_boundary`.
- The check validates:
  - `artifact_kind=postrun_acceptance_rebuild`
  - `run_root`, `campaign_dir`, and `report_dir`
  - `report_only=true`
  - `quality_judgment=false`
  - `decision_features_excluded=true`
  - no campaign, scheduler, or promotion state mutation
- Regression test:
  `test_postrun_acceptance_rejects_dirty_rebuild_manifest_boundary`.

## Verification

Local:

- `python -m py_compile scion/tools/check_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py::test_postrun_acceptance_rejects_dirty_rebuild_manifest_boundary`
  - `1 passed`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py`
  - `37 passed`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `128 passed`
- `git diff --check`

WSL:

- `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile scion/tools/check_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
- `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_check_postrun_acceptance.py::test_postrun_acceptance_rejects_dirty_rebuild_manifest_boundary`
  - `1 passed`
- `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `128 passed`
- `git diff --check`

## Current Prepared Roots

Because this touched `scion/tools`, current WSL prepared roots were regenerated
from WSL runtime commit `bd11336`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-postboundary-bd11336-6r-gpt55-6r-gpt55-20260619T155053Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-postboundary-bd11336-1r-gpt55-1r-gpt55-20260619T155107Z-claw`

Both roots are prepare-only and have not been launched.

Strict WSL launch readiness for both roots exits `64` and reports:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `prepared_handoff_rebuild_declared_outputs_present=ok`
- no prepared-handoff manifest identity/boundary failures
- no missing, inconsistent, unexpected, or out-of-scope prepared-handoff
  declared outputs
- `run_script_strict_postrun_rebuild=ok`
- `run_script_completion_preflight_enforced=ok`
- `runtime_guard_paths_cover_launch_tools=ok`

Prepare-only roots do not yet have current-run postrun acceptance bundles. The
new postrun rebuild manifest check is enforced after `run.sh` rebuilds the
postrun bundle at campaign exit and before postrun delegated-readiness can pass.

## Launch Blocker

The remaining blocker is still external `gpt-5.5` provider auth, not Scion
static readiness. Direct WSL proxy preflight with `SCION_API_KEY=pwd` returns:

- HTTP `401`
- `classification=not_authenticated`
- `code=invalid_api_key`
- auth pool `active=0`, `expired=1`, `refreshing=0`, `total=1`

Do not launch either prepared root until strict launch readiness reports
`launch_ready=true`.
