# v0.4 Launch Readiness Strict Postrun Readiness Guard

Date: 2026-06-19

## Purpose

Prepared roots should not pass static launch readiness if their `run.sh` can
generate postrun acceptance readiness without enforcing current-run analysis
readiness. The launcher templates now write `POSTRUN_READINESS_EXIT_STATUS`
from a strict `check_postrun_acceptance.py --require-current-run-ready` call,
but launch readiness also needs to reject stale prepared roots whose scripts do
not carry that strict marker path.

## Change

`scion/tools/check_launch_readiness.py` now requires
`run_script_strict_postrun_readiness=ok` before `static_ready=true`.

The check verifies that `run.sh` contains:

- `write_postrun_acceptance_reports() {`
- `tools/check_postrun_acceptance.py`
- `--require-current-run-ready`
- `POSTRUN_READINESS_EXIT_STATUS`

This makes launch readiness guard the runtime script, not only the generated
artifact family declarations.

## Boundary

This is a launch/readiness report guard only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, campaign
validity, or warehouse/CVRP solver behavior.

## Verification

Local checkout `f9f24810`:

```bash
python -m py_compile scion/tools/check_launch_readiness.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Results: focused launch/readiness group `44 passed`; full v0.4 group
`81 passed`.

WSL checkout `f1ee04e`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Result: `81 passed`.

## Current Prepared Roots

New prepare-only roots were generated from WSL checkout `f1ee04e` because the
launch-readiness guard now checks the generated `run.sh` strict postrun
readiness path.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-f1ee04e-6r-gpt55-20260619T025919Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-f1ee04e-1r-gpt55-20260619T025920Z-claw`

Strict launch readiness for both roots reports exit `64` with:

- `static_ready=true`
- `launch_ready=false`
- `run_script_strict_postrun_readiness=ok`
- `postrun_families_complete=ok`
- `prepared_analysis_brief_current=ok`
- `prompt_context_readiness_complete=ok`
- `problem_specific_prepared_handoff=ok`
- `git_runtime_consistent=ok`

The remaining blocker is external `gpt-5.5` auth, not Scion static readiness:
completion preflight returns HTTP `401`, `classification=not_authenticated`,
`code=invalid_api_key`, with auth pool `active=0`, `refreshing=1`, `total=1`.
