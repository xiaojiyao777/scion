# Handoff Manifest Output Scope

Date: 2026-06-19

## Purpose

Prepared-handoff and postrun-acceptance readiness now reject rebuild manifest
outputs that point outside their declared report family directory.

The rebuild tools normally write outputs inside `prepared_handoff/<family>/` and
`postrun_acceptance/<family>/`. The risk was in the checker layer: a hand-edited
manifest could point a declared output at a stale artifact elsewhere. For
postrun analysis briefs, that could let delegated review consume an external
brief instead of the current run-root bundle.

This is artifact identity and report-bundle hygiene only. It does not change
Decision, `DecisionFeatures`, Protocol gates, promotion, scheduler state, or
solver behavior.

## Acceptance Evidence

- `check_postrun_acceptance.py` selects analysis briefs only from the manifest
  output path when that path is inside `postrun_acceptance/analysis_brief`.
- `check_postrun_acceptance.py` fails
  `rebuild_manifest_declared_outputs_present` when any declared output is
  outside its `postrun_acceptance/<family>` directory.
- `check_launch_readiness.py` fails
  `prepared_handoff_rebuild_declared_outputs_present` when any declared output
  is outside its `prepared_handoff/<family>` directory.
- New regression tests:
  - `test_postrun_acceptance_rejects_manifest_output_outside_family_dir`
  - `test_launch_readiness_rejects_prepared_handoff_manifest_output_outside_family_dir`

Verification:

- Local:
  - `python -m py_compile scion/tools/check_postrun_acceptance.py scion/tools/check_launch_readiness.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_launch_readiness.py`
  - `PYTHONPATH=scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py::test_postrun_acceptance_rejects_manifest_output_outside_family_dir scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_prepared_handoff_manifest_output_outside_family_dir`
  - `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `git diff --check`
- WSL:
  - `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile scion/tools/check_postrun_acceptance.py scion/tools/check_launch_readiness.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_launch_readiness.py`
  - `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_check_postrun_acceptance.py::test_postrun_acceptance_rejects_manifest_output_outside_family_dir scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_prepared_handoff_manifest_output_outside_family_dir`
  - `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `git diff --check`

## Result

Accepted as launch/postrun artifact-identity hardening. Because this touches
`scion/tools`, current WSL prepared roots were regenerated from WSL runtime
commit `709db42`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-familydirs-709db42-6r-gpt55-6r-gpt55-20260619T153549Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-familydirs-709db42-1r-gpt55-1r-gpt55-20260619T153550Z-claw`

Strict WSL launch readiness for both regenerated roots reports
`static_ready=true`, `git_runtime_consistent=ok`, and
`prepared_handoff_rebuild_declared_outputs_present=ok`, with no missing,
inconsistent, unexpected, or out-of-scope declared outputs.

Launch remains blocked only by the external `gpt-5.5` provider auth preflight:
HTTP `401` / `classification=not_authenticated` / `code=invalid_api_key`, with
auth pool `active=0`, `expired=1`, `refreshing=0`, `total=1`.
