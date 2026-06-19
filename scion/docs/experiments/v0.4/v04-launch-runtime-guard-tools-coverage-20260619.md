# v0.4 Launch Runtime Guard Tools Coverage

Date: 2026-06-19

## Purpose

Prepared roots must not launch with a manifest generated before changes to the
launcher, postrun rebuild, postrun readiness, or launch-readiness tools. Those
tools are part of the runtime/control-plane semantics for v0.4 follow-up runs,
so a prepared manifest that only guards `scion/scion` and problem assets can
miss meaningful drift in `scion/tools`.

## Change

`check_launch_readiness.py` now requires prepared contracts to declare runtime
guard coverage for `scion/tools`, exposed as
`runtime_guard_paths_cover_launch_tools`.

Both CVRP and warehouse agentic launchers now include `scion/tools` in
`GIT_RUNTIME_GUARD_PATHS`, so newly prepared roots fail closed if the checkout
changes in launcher/report/readiness tooling after prepare time.

## Boundary

This is launch-readiness and wrapper guard coverage only. It does not change
Decision, `DecisionFeatures`, Protocol gates, promotion, scheduler state,
proposal semantics, problem solvers, or experiment evidence.

## Verification

Local checkout:

```bash
python -m py_compile \
  scion/tools/check_launch_readiness.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py

PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py

PYTHONPATH=scion pytest -q \
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

Results: launch-readiness group `22 passed`; launcher group `23 passed`; full
v0.4 readiness/reporting group `89 passed`.

New regression coverage:

- launch readiness rejects a prepared root whose runtime guard paths omit
  `scion/tools`; and
- new CVRP/warehouse prepared manifests and `launch.env` files include
  `scion/tools` in runtime guard paths.
