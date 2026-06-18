# V0.4 Prepared Run Manifest Launcher Repair

Date: 2026-06-18

## Purpose

The next CVRP and warehouse follow-up roots are launch-prepared while the
`gpt-5.5` route is blocked. The run roots already recorded `command.txt`,
`launch.env`, and `run_status.json`, but they did not provide a stable,
secret-free launch contract for main-session review and delegated postrun
analysis.

This repair makes both agentic launchers write:

- `prepared_run_manifest.v1.json`
- `prepared_run_manifest.md`

at prepare time.

## Boundary Check

- This is report-only launch/handoff metadata.
- It does not change Proposal, Contract, Verification, Protocol, Decision,
  `DecisionFeatures`, lifecycle, scheduling, promotion, or problem semantics.
- The manifest records run intent, config/protocol/split/seed paths, round
  budget, model/preflight settings, runtime guard paths, postrun acceptance
  families, and acceptance focus.
- It deliberately excludes API keys and any quality judgment.

## Changed Behavior

CVRP prepared roots now include a manifest intent focused on post-pivot
branch-continuation analysis: target-intent/hypothesis traces, branch lesson
transfer, protocol effect-vs-MDE, budget-exhausting runtime feedback, source
visibility, and material difference from rejected/default-avoid directions.

Warehouse prepared roots now include a manifest intent focused on champion `v2`
continuous-improvement analysis: promotion behavior, branch transfer, prompt
context, runtime/model explanation, and real plateau versus missed continuous
promotion.

The postrun analysis brief checklist and artifact inventory now also recognize
the prepared-run manifest artifacts.

## Verification

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py
python -m py_compile \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/postrun_analysis_brief.py
```

Result:

- `27 passed`
- `py_compile` passed

WSL prepared-root refresh on commit `ee43fa1` produced the current launch roots:

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-manifest-1r-gpt55-20260618T121407Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-manifest-6r-gpt55-20260618T121407Z-claw`

Both roots are mirrored locally under `/home/clawd/research/scion-experiments/`.
Validation confirmed top-level `prepared` status, completion preflight,
expected `control_pair_key`, `GIT_COMMIT=ee43fa1`, `bash -n` clean `run.sh`,
`PREPARED_RUN_MANIFEST=` in `command.txt`, secret-free manifest JSON, and
manifest visibility through both postrun analysis brief and artifact inventory.
