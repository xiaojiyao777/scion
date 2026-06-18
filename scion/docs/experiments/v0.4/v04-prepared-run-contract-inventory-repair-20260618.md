# V0.4 Prepared Run Contract Inventory Repair

Date: 2026-06-18

## Purpose

The current CVRP and warehouse follow-up roots are prepared while the
`gpt-5.5` route is blocked. The prepared-run manifest records launch intent, but
postrun handoff still required manual comparison across `command.txt`, manifest
fields, config paths, model/preflight settings, and report families.

This repair adds report-only prepared-run contract checks to:

- `scion/tools/postrun_artifact_inventory.py`
- `scion/tools/postrun_analysis_brief.py`

## Boundary Check

- This is launch/handoff metadata validation only.
- It does not change Proposal, Contract, Verification, Protocol, Decision,
  `DecisionFeatures`, lifecycle, scheduling, promotion, runtime, or problem
  semantics.
- The new `scion.prepared_run_contract_inventory.v1` block is explicitly
  report-only, carries no quality judgment, and is excluded from
  `DecisionFeatures`.

## Changed Behavior

The artifact inventory now emits `launcher.prepared_run_contract` with checks
for:

- prepared manifest presence, schema, report-only flags, and secret absence;
- mirrored local/WSL run-root and campaign-dir identity;
- `command.txt` command and `PREPARED_RUN_MANIFEST` consistency;
- `gpt-5.5` model and completion-preflight requirement;
- `control_pair_key` and postrun report family completeness;
- config path resolvability, including local mirrors of WSL absolute paths.

The analysis brief renders the same block so delegated postrun review can start
from one artifact instead of manually diffing launcher files.

## Verification

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py
python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/postrun_analysis_brief.py
git diff --check
```

Result:

- `5 passed`
- `py_compile` passed
- `git diff --check` passed

Smoke checks against the current local mirrors showed `contract_complete=True`
for both prepared roots:

- `/home/clawd/research/scion-experiments/v04-cvrp-postpivot-resume-ready-manifest-1r-gpt55-20260618T121407Z-claw`
- `/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-ready-manifest-6r-gpt55-20260618T121407Z-claw`
