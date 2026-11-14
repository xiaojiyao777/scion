# v0.4 Launch Readiness Run-Script PYTHONPATH Guard

Date: 2026-06-19

## Purpose

WSL launches must import the Scion checkout that prepared the campaign root, not
a stale installed package from another checkout. Prepared roots already write
`PYTHONPATH` into `launch.env`; launch readiness now verifies that the generated
wrapper actually preserves that import boundary before campaign start.

## Change

`scion/tools/check_launch_readiness.py` now exposes
`run_script_pythonpath_enforced`.

The check requires:

- readable `launch.env`;
- a `PYTHONPATH` assignment in `launch.env`;
- if `SCION_DIR` is declared, `PYTHONPATH` contains that checkout path;
- `run.sh` sources `launch.env`;
- `run.sh` exports `PYTHONPATH` before the real `scion.cli.main run` command.

Logged `COMMAND:` lines are ignored when locating the real campaign command, as
with the completion-preflight ordering check.

## Boundary

This is a launch/readiness import-boundary guard only. It does not change
Decision, `DecisionFeatures`, Protocol gates, promotion, scheduler state,
proposal semantics, problem solvers, or experiment evidence.

## Verification

Local checkout `b9d0b3d1`:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py
# 37 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# 73 passed

python -m py_compile scion/tools/check_launch_readiness.py
git diff --check
```

WSL checkout `d14f395`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# 73 passed
```

## Current Prepared Roots

New prepare-only roots were generated from WSL checkout `d14f395` because
`scion/tools/check_launch_readiness.py` is part of the guarded launch/readiness
runtime surface.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-pythonpath-d14f395-6r-gpt55-20260619T092933Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-pythonpath-d14f395-1r-gpt55-20260619T092933Z-claw`

Both roots are prepare-only and not started.

## Readiness Evidence

Strict WSL launch readiness for both roots exits `64` and reports:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
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
static readiness.

## Acceptance

Accepted as the current prepared-root refresh after run-script PYTHONPATH
enforcement. It supersedes
`v04-launch-readiness-run-script-completion-preflight-20260619.md` as the
current prepared-root pointer. Do not launch either root until strict launch
readiness reports `launch_ready=true`.
