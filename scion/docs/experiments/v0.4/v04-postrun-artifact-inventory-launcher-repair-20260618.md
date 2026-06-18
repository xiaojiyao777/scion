# V0.4 Postrun Artifact Inventory Launcher Repair

Date: 2026-06-18

## Purpose

The next CVRP and warehouse runs are launch-prepared but blocked on the
`gpt-5.5` completion route. Once the route is healthy, the postrun handoff
should immediately expose artifact/count coverage before main-thread or
subagent analysis begins.

`scion/tools/postrun_artifact_inventory.py` already provides that report-only
inventory, but the CVRP and warehouse launchers did not include it in the
default postrun acceptance bundle. This repair makes the default launcher bundle
write both JSON and Markdown inventory artifacts under
`postrun_acceptance/inventory/`, and extends the inventory with report-only
Phase 4 evidence coverage flags for the next CVRP/warehouse postrun handoff.

## Boundary Check

- This is report-only postrun bookkeeping.
- It does not change Proposal, Contract, Verification, Protocol, Decision,
  `DecisionFeatures`, lifecycle, scheduling, promotion, or problem semantics.
- The inventory lists artifacts, counters, validity, branches, events,
  hypotheses, LLM trace counts, and Phase 4 evidence-availability flags only.
  It does not judge research quality.
- The Phase 4 coverage block is deliberately outside `DecisionFeatures`; it is
  an analysis checklist for main-thread or subagent postrun review.

## Changed Behavior

The CVRP and warehouse launchers now generate, when `POSTRUN_REPORTS=1`:

- `postrun_acceptance/inventory/*.postrun_artifact_inventory.v1.json`
- `postrun_acceptance/inventory/*.postrun_artifact_inventory.md`

The inventory tool also counts the `inventory` report family when summarizing
the postrun acceptance bundle.

The inventory JSON/Markdown now includes `phase4_evidence_coverage` with
report-only availability/count fields for:

- target-intent, hypothesis, and code traces;
- formal candidate artifacts;
- proposal trajectory manifests and prompt-manifest loading evidence;
- research-efficiency reports;
- measurement readiness and protocol-effect-vs-MDE evidence;
- branch lesson transfer, runtime feedback, and source-visibility evidence.

## Verification

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py
```

Result:

- `25 passed`
- `py_compile` passed
- `git diff --check` passed

Launcher smoke generated prepared CVRP and warehouse roots in temporary
directories, `bash -n` passed for both `run.sh` files, and each generated script
contained the guarded inventory JSON/Markdown commands.

WSL prepared-root refresh on commit `85ff422` produced:

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-coverage-1r-gpt55-20260618T114826Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-coverage-6r-gpt55-20260618T114826Z-claw`

Both roots have top-level `prepared` status, completion preflight, the expected
`control_pair_key`, shared `check_gpt55_proxy.py`, inventory JSON/Markdown
commands, `bash -n` clean `run.sh`, and inventory JSON smoke coverage for the
`scion.postrun_phase4_evidence_coverage.v1` schema.
