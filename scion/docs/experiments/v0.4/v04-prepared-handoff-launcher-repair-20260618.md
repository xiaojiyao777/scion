# V0.4 Prepared Handoff Launcher Repair

Date: 2026-06-18

## Purpose

Prepared CVRP and warehouse roots should be inspectable without manually running
postrun tooling or cross-reading `command.txt`, the prepared manifest, and
status files. This repair makes prepare-only roots write their delegated
analysis inputs immediately.

## Boundary Check

- This is launcher/reporting infrastructure only.
- It does not change Proposal, Contract, Verification, Protocol, Decision,
  `DecisionFeatures`, scheduling, lifecycle, promotion, budgets, or problem
  semantics.
- Generated prepared handoff artifacts are report-only, carry no research
  quality judgment, and remain outside `DecisionFeatures`.

## Changed Behavior

Both agentic launchers now write:

- `prepared_handoff/analysis_brief/*.prepared_analysis_brief.v1.json`
- `prepared_handoff/analysis_brief/*.prepared_analysis_brief.md`
- `prepared_handoff/inventory/*.prepared_artifact_inventory.v1.json`
- `prepared_handoff/inventory/*.prepared_artifact_inventory.md`

The prepared manifest records `report_metadata.prepared_handoff_dir` and
`report_metadata.prepared_handoff_families`; `command.txt` records
`PREPARED_HANDOFF_DIR=...`.

`postrun_artifact_inventory.py` now treats `prepared_handoff` as a launcher
artifact and records `database.read_error` when a copied or placeholder
`scion.db` is not readable, instead of failing the prepare step.

## Current Prepared Roots

Generated on WSL from commit `f1c578f`:

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-handoff-1r-gpt55-20260618T125046Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-handoff-6r-gpt55-20260618T125046Z-claw`

Both roots are mirrored locally under `/home/clawd/research/scion-experiments/`.

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
git diff --check
```

Result:

- `28 passed`
- `py_compile` passed
- `git diff --check` passed

WSL root validation confirmed for both prepared roots:

- `bash -n run.sh` passed.
- Manifest commit is `f1c578f`.
- `prepared_handoff` is present in launcher artifact inventory.
- Prepared analysis brief schema is `scion.postrun_analysis_brief.v1`.
- Prepared-run contract inventory reports `contract_complete=True`.
- Git runtime consistency reports `checkout matches manifest commit`.
