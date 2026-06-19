# v0.4 Launch Readiness Run-Script Model Route Guard

Date: 2026-06-19

## Purpose

v0.4 follow-up campaigns must run through the local GPT-5.5 route. Prepared
launch readiness must therefore reject roots whose live completion preflight
would check one model route while `run.sh` launches the campaign with another.

## Change

`scion/tools/check_launch_readiness.py` now exposes
`run_script_model_route_enforced`.

The check requires:

- `launch.env` declares `SCION_MODEL=gpt-5.5`;
- `launch.env` declares `SCION_BASE_URL`;
- `launch.env` model/base URL match `prepared_run_manifest.v1.json`;
- `run.sh` exports `SCION_MODEL` and `SCION_BASE_URL` before campaign start;
- the completion preflight calls `tools/check_gpt55_proxy.py` with
  `--model "$SCION_MODEL"` and `--base-url "$SCION_BASE_URL"` before campaign
  start.

Logged `COMMAND:` lines are ignored when locating the real campaign command.

## Boundary

This is a launch/readiness route-consistency guard only. It does not change
Decision, `DecisionFeatures`, Protocol gates, promotion, scheduler state,
proposal semantics, problem solvers, or experiment evidence.

## Verification

Local checkout `c092eacd`:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py
# 38 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# 74 passed

python -m py_compile scion/tools/check_launch_readiness.py
git diff --check
```

WSL checkout `9441806`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# 74 passed
```

## Current Prepared Roots

New prepare-only roots were generated from WSL checkout `9441806` because
`scion/tools/check_launch_readiness.py` is part of the guarded launch/readiness
runtime surface.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-modelroute-9441806-6r-gpt55-20260619T093736Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-modelroute-9441806-1r-gpt55-20260619T093736Z-claw`

Both roots are prepare-only and not started.

## Readiness Evidence

Strict WSL launch readiness for both roots exits `64` and reports:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `run_script_model_route_enforced=ok`
- `run_script_pythonpath_enforced=ok`
- `run_script_completion_preflight_enforced=ok`
- `run_script_runtime_guard_enforced=ok`
- `runtime_guard_paths_cover_launch_tools=ok`
- `runtime_guard_paths_cover_problem_runtime=ok`
- `prompt_context_readiness_complete=ok`
- `problem_specific_prepared_handoff=ok`
- completion preflight `failed`, HTTP `401`,
  `classification=not_authenticated`, `code=invalid_api_key`

The current blocker remains external GPT-5.5 proxy authentication, not Scion
static readiness or route consistency.

## Acceptance

Accepted as the current prepared-root refresh after GPT-5.5 model-route
enforcement. It supersedes
`v04-launch-readiness-run-script-pythonpath-20260619.md` as the current
prepared-root pointer. Do not launch either root until strict launch readiness
reports `launch_ready=true`.
