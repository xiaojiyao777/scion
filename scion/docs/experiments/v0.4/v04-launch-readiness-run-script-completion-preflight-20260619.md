# v0.4 Launch Readiness Run-Script Completion Preflight Guard

Date: 2026-06-19

## Purpose

Prepared roots must not pass static launch readiness unless the generated launch
wrapper itself enforces the GPT-5.5 completion preflight before campaign start.
The readiness tool already performs a live completion preflight when requested,
but it also needs to reject stale or hand-edited prepared roots whose
`launch.env` disables `COMPLETION_PREFLIGHT` or whose `run.sh` would start
`scion.cli.main run` without first calling `tools/check_gpt55_proxy.py`.

## Change

`scion/tools/check_launch_readiness.py` now exposes
`run_script_completion_preflight_enforced`.

The check requires:

- readable `launch.env`;
- `COMPLETION_PREFLIGHT=1`;
- `run.sh` sources `launch.env`;
- `run.sh` contains the completion-preflight guard;
- `run.sh` calls `tools/check_gpt55_proxy.py` before the real
  `scion.cli.main run` campaign command.

Logged `COMMAND:` lines are ignored when locating the real campaign command, so
readiness checks ordering against the executable path rather than against a log
echo.

## Boundary

This is a launch/readiness wrapper guard only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, proposal
semantics, problem solvers, or experiment evidence. It prevents an unstarted
prepared root from bypassing the existing provider preflight.

## Verification

Local checkout `13ce8250`:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py
# 36 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# 72 passed

python -m py_compile scion/tools/check_launch_readiness.py
git diff --check
```

WSL checkout `5ba9d56`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# 72 passed
```

## Current Prepared Roots

New prepare-only roots were generated from WSL checkout `5ba9d56` because
`scion/tools/check_launch_readiness.py` is part of the guarded launch/readiness
runtime surface.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-preflightpos-5ba9d56-6r-gpt55-20260619T091903Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-preflightpos-5ba9d56-1r-gpt55-20260619T091903Z-claw`

Both roots are prepare-only and not started.

## Readiness Evidence

Strict WSL launch readiness for both roots exits `64` and reports:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `prepared_analysis_brief_current=ok`
- `prompt_context_readiness_complete=ok`
- `problem_specific_prepared_handoff=ok`
- `postrun_families_complete=ok`
- `run_script_strict_postrun_readiness=ok`
- `run_script_runtime_guard_enforced=ok`
- `run_script_postrun_reports_after_campaign=ok`
- `run_script_data_root_failure_reports=ok`
- `run_script_api_key_env_failure_reports=ok`
- `run_script_completion_preflight_enforced=ok`
- `runtime_guard_paths_cover_launch_tools=ok`
- `runtime_guard_paths_cover_problem_runtime=ok`
- completion preflight `failed`, HTTP `401`,
  `classification=not_authenticated`, `code=invalid_api_key`

The current blocker remains external GPT-5.5 proxy authentication, not Scion
static readiness.

## Acceptance

Accepted as the current launch-readiness root refresh after run-script
completion-preflight enforcement. It supersedes
`v04-prepared-root-refresh-after-postrun-summary-boundary-20260619.md` as the
current prepared-root pointer. Do not launch either root until strict launch
readiness reports `launch_ready=true`.
