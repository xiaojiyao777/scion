# v0.4 Launch Runtime Guard Tools Coverage

Date: 2026-06-19

## Purpose

Prepared roots must not launch with a manifest generated before changes to the
launcher, postrun rebuild, postrun readiness, or launch-readiness tools. Those
tools are part of the runtime/control-plane semantics for v0.4 follow-up runs,
so a prepared manifest that only guards `scion/scion` and problem assets can
miss meaningful drift in `scion/tools`. The launch check must also verify that
the prepared `run.sh` actually executes the declared git guard before starting
the campaign.

## Change

`check_launch_readiness.py` now requires prepared contracts to declare runtime
guard coverage for `scion/tools`, exposed as
`runtime_guard_paths_cover_launch_tools`.

Both CVRP and warehouse agentic launchers now include `scion/tools` in
`GIT_RUNTIME_GUARD_PATHS`, so newly prepared roots fail closed if the checkout
changes in launcher/report/readiness tooling after prepare time.

`check_launch_readiness.py` also requires
`run_script_runtime_guard_enforced=ok`: the prepared `run.sh` must contain the
git dirty check, HEAD mismatch check, doc-only mismatch allowance, and failure
markers before `scion.cli.main run`.

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

Results: launch-readiness group `25 passed`; full v0.4 readiness/reporting
group `92 passed`.

WSL checkout after sync:

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

Result: full v0.4 readiness/reporting group `92 passed`.

Old prepared roots from WSL checkout `f1ee04e` now fail static readiness with
`runtime_guard_paths_cover_launch_tools=failed` because their manifests omit
`scion/tools`.

Prepared roots from WSL checkout `49edd77` are also superseded because the
run-script guard enforcement check changed `scion/tools`; current launch roots
were later replaced again after the campaign-exit postrun report call check
changed `scion/tools`.

Replacement prepared roots:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-postruncall-ready-6r-gpt55-20260619T040458Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-postruncall-ready-1r-gpt55-20260619T040458Z-claw`

Strict launch readiness for both replacements reports `static_ready=true`,
`git_runtime_consistent=ok`, `runtime_guard_paths_cover_launch_tools=ok`,
`prepared_analysis_brief_current=ok`, `prompt_context_readiness_complete=ok`,
`problem_specific_prepared_handoff=ok`, `postrun_families_complete=ok`, and
`run_script_strict_postrun_readiness=ok`,
`run_script_runtime_guard_enforced=ok`,
`run_script_postrun_reports_after_campaign=ok`. Launch readiness remains blocked
only by the external `gpt-5.5` completion preflight: HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`, auth pool
`active=0`, `expired=0`, `refreshing=1`, `total=1`.

New regression coverage:

- launch readiness rejects a prepared root whose runtime guard paths omit
  `scion/tools`;
- launch readiness rejects a prepared root whose `run.sh` omits runtime guard
  markers or places them after the campaign command; and
- launch readiness rejects a prepared root whose normal campaign-exit path does
  not call `write_postrun_acceptance_reports` before `exit "$STATUS"`; and
- new CVRP/warehouse prepared manifests and `launch.env` files include
  `scion/tools` in runtime guard paths.
