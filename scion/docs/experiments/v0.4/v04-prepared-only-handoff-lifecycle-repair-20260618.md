# V0.4 Prepared-Only Handoff Lifecycle Repair

Date: 2026-06-18

## Purpose

Prepared follow-up roots copy a resume campaign into `campaign/` before the
agentic run starts. The copied campaign can already contain `run_status.json`,
`campaign_summary.json`, and counters from the source run. The handoff brief and
artifact inventory must not interpret those copied artifacts as current-run
postrun evidence.

This repair makes prepare-time handoff artifacts explicitly distinguish a
prepared launch root with a copied resume snapshot from a launched postrun
campaign with current-run evidence.

## Boundary Check

- This is launcher/reporting infrastructure only.
- It does not change Proposal, Contract, Verification, Protocol, Decision,
  `DecisionFeatures`, scheduling, lifecycle policy, promotion, budgets, or
  problem semantics.
- The new lifecycle fields are report-only and remain outside
  `DecisionFeatures`.

## Changed Behavior

`postrun_artifact_inventory.py` now emits a report-only
`scion.launcher_lifecycle.v1` block. For prepare-only roots it reports:

- `prepared_only=True`
- `evidence_scope=prepared_launch_root_with_resume_snapshot`
- `run_validity_status=prepared_only`
- `run_completeness_status=not_started`
- `last_stop_reason=prepared_only_not_launched`
- zero current-run effective/protocol/proposal counters

`postrun_analysis_brief.py` renders prepared roots as
`Prepared Analysis Brief` and adds stop conditions that prevent copied campaign
artifacts from being used as current-run research evidence. Delegated analysis
for prepared-only roots should stop at launcher contract/readiness review until
the prepared root is actually launched and postrun reports are regenerated.

## Current Prepared Roots

Generated on WSL from commit `1471388`:

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-lifecycle-1r-gpt55-20260618T130518Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-lifecycle-6r-gpt55-20260618T130519Z-claw`

Both roots are mirrored locally under `/home/clawd/research/scion-experiments/`.

## Verification

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py
git diff --check
```

Result:

- `30 passed`
- `py_compile` passed
- `git diff --check` passed

WSL validation confirmed for both current prepared roots:

- `bash -n run.sh` passed.
- Prepared handoff markdown starts with `# Prepared Analysis Brief`.
- `lifecycle.prepared_only=True`.
- Validity is `prepared_only/not_started`.
- `effective_rounds_completed=0`.
- Stop conditions include `PREPARED-ONLY ROOT`.
- Prepared-run contract reports `contract_complete=True`.
- Git runtime consistency reports `checkout matches manifest commit`.
