# Postrun Readiness Status Order

Date: 2026-06-19

## Purpose

Launch readiness now rejects run scripts where
`POSTRUN_READINESS_EXIT_STATUS` appears before the strict
`check_postrun_acceptance.py --require-current-run-ready` command.

The launcher-generated scripts already emitted the marker after the readiness
command. The risk was in the static checker: a hand-edited script could contain
the marker early, pass launch readiness, and later make postrun delegated-review
status look reported even though the marker was not tied to the actual
readiness check result.

This is launch/reporting hygiene only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, or solver
behavior.

## Code Change

- `scion/tools/check_launch_readiness.py` now fails
  `run_script_strict_postrun_readiness` with
  `postrun_readiness_exit_status_before_readiness` when the status marker
  precedes the strict postrun readiness command.
- Regression test:
  `test_launch_readiness_rejects_postrun_readiness_marker_before_readiness`.

## Verification

Local:

- `python -m py_compile scion/tools/check_launch_readiness.py scion/scion/tests/test_launch_readiness.py`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_postrun_readiness_marker_before_readiness`
  - `1 passed`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py`
  - `66 passed`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `129 passed`
- `git diff --check`

WSL:

- `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile scion/tools/check_launch_readiness.py scion/scion/tests/test_launch_readiness.py`
- `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_postrun_readiness_marker_before_readiness`
  - `1 passed`
- `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `129 passed`
- `git diff --check`

## Current Prepared Roots

Because this touched `scion/tools`, current WSL prepared roots were regenerated
from WSL runtime commit `2d1b93b`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-postreadiness-2d1b93b-6r-gpt55-6r-gpt55-20260619T155911Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-postreadiness-2d1b93b-1r-gpt55-1r-gpt55-20260619T155924Z-claw`

Both roots are prepare-only and have not been launched.

Strict WSL launch readiness for both roots exits `64` and reports:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `run_script_strict_postrun_readiness=ok`, with
  `POSTRUN_READINESS_EXIT_STATUS` after the strict readiness command
- `run_script_strict_postrun_rebuild=ok`, with
  `POSTRUN_REPORTS_EXIT_STATUS` after the strict rebuild command
- `prepared_handoff_rebuild_declared_outputs_present=ok`
- no prepared-handoff manifest identity/boundary failures
- no missing, inconsistent, unexpected, or out-of-scope prepared-handoff
  declared outputs
- `run_script_completion_preflight_enforced=ok`

## Launch Blocker

The remaining blocker is still external `gpt-5.5` provider auth, not Scion
static readiness. Strict readiness and direct proxy preflight with
`SCION_API_KEY=pwd` return:

- HTTP `401`
- `classification=not_authenticated`
- `code=invalid_api_key`
- auth pool `active=0`, `expired=1`, `refreshing=0`, `total=1`

Do not launch either prepared root until strict launch readiness reports
`launch_ready=true`.
