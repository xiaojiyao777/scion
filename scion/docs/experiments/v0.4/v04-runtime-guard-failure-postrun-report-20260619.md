# Runtime Guard Failure Postrun Reporting

Date: 2026-06-19

## Purpose

Warehouse and CVRP launch scripts now generate the report-only postrun
acceptance bundle when the runtime git guard fails before campaign start.
Launch readiness also requires this path through
`run_script_runtime_guard_failure_reports`. The same report-only infra-failure
path now also covers missing/unreadable `launch.env` and missing/inaccessible
`SCION_DIR` through `run_script_launch_env_failure_reports` and
`run_script_scion_dir_failure_reports`.

Before this repair, dirty runtime paths or a guarded commit mismatch could
write `run_status.json` and exit `64` without running postrun rebuild/readiness.
That left WSL sync drift as an infra-only black-box exit instead of an auditable
prepared/current-run boundary event.

This is launcher/reporting hygiene only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, or solver
behavior.

## Code Change

- `launch_warehouse_agentic_campaign.py` and
  `launch_cvrp_agentic_campaign.py` call
  `write_postrun_acceptance_reports` after writing `git_runtime_dirty` or
  `git_runtime_commit_mismatch` run status, before exiting.
- `check_launch_readiness.py` adds
  `run_script_runtime_guard_failure_reports`, requiring the runtime guard
  failure marker, matching run-status writer flag, postrun report call after
  that status writer, and postrun report call before the branch exit.
- `rebuild_postrun_acceptance.py` and `postrun_artifact_inventory.py` now treat
  pre-campaign infra failure keys (`api_key_env_missing`,
  `launch_env_missing`, `scion_dir_missing`, `warehouse_data_root_missing`,
  `git_runtime_dirty`, and `git_runtime_commit_mismatch`) as
  resume-snapshot-only evidence, so copied campaign artifacts cannot be rebuilt
  into current-run reports after a launch guard failure.
- Launch scripts also write `launch_env_missing` or `scion_dir_missing` status
  and run the same postrun acceptance bundle before exiting when the launch env
  cannot be read or `cd "$SCION_DIR"` fails.
- Regression coverage includes missing runtime-guard postrun calls,
  postrun-before-status ordering, comment-only postrun functions, skipped
  current-run reports after runtime-guard failure, and inventory lifecycle
  evidence for runtime-guard failure roots.

## Verification

Local:

- `python -m py_compile scion/tools/check_launch_readiness.py scion/tools/launch_warehouse_agentic_campaign.py scion/tools/launch_cvrp_agentic_campaign.py scion/scion/tests/test_launch_readiness.py`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py`
  - `68 passed`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py`
  - `23 passed`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_rebuild_postrun_acceptance.py::test_rebuild_postrun_acceptance_skips_current_run_reports_after_runtime_guard_failure scion/scion/tests/test_postrun_artifact_inventory.py::test_inventory_marks_runtime_guard_failure_resume_snapshot_not_current_run`
  - `2 passed`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `79 passed`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_postrun_analysis_brief.py`
  - `168 passed`
- `git diff --check`

WSL:

- `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile scion/tools/check_launch_readiness.py scion/tools/launch_warehouse_agentic_campaign.py scion/tools/launch_cvrp_agentic_campaign.py scion/scion/tests/test_launch_readiness.py`
- `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py`
  - `91 passed`
- `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_postrun_analysis_brief.py`
  - `79 passed`
- `git diff --check`

## Current Prepared Roots

Because later report tooling also touched `scion/tools`, current WSL prepared
roots were regenerated from WSL runtime commit `bea482de`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-noprotocol-bea482de-6r-gpt55-20260619T172019Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-noprotocol-bea482de-1r-gpt55-20260619T172019Z-claw`

Strict WSL launch readiness for both roots exits `64` and reports:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `run_script_runtime_guard_enforced=ok`
- `run_script_launch_env_failure_reports=ok`
- `run_script_runtime_guard_failure_reports=ok`
- `run_script_scion_dir_failure_reports=ok`
- `run_script_strict_postrun_rebuild=ok`
- `run_script_strict_postrun_readiness=ok`
- `prepared_handoff_rebuild_declared_outputs_present=ok`
- `problem_specific_prepared_handoff=ok`
- `prompt_context_readiness_complete=ok`
- no prepared-handoff manifest failures, missing outputs, unexpected outputs,
  inconsistent outputs, or out-of-scope outputs

The remaining blocker is still external `gpt-5.5` provider auth, not Scion
static readiness. Real chat completion preflight returns HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`, with auth pool
`active=0`, `total=1`, and no launch-usable account.
