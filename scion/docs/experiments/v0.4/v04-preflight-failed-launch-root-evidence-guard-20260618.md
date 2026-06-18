# Preflight-Failed Launch Root Evidence Guard

Date: 2026-06-18

## Purpose

Close an evidence-scope gap for prepared follow-up roots. If a prepared root is
started while the `gpt-5.5` completion preflight is still failing, the run must
remain auditable as an infrastructure failure and must not treat copied resume
campaign artifacts as current-run Scion evidence.

## Change

- `postrun_artifact_inventory.py` now recognizes prepared roots whose outer
  wrapper stopped at `pre_campaign_completion_preflight=failed`.
- Such roots are marked with evidence scope
  `pre_campaign_preflight_failed_with_resume_snapshot`,
  `current_run_evidence=false`, validity `invalid_infra_only`, and zero
  effective/formal/protocol/proposal counters.
- Phase 4 evidence coverage is zeroed for those roots because copied campaign
  artifacts are resume input, not current-run postrun evidence.
- `rebuild_postrun_acceptance.py` skips current-run report families for those
  roots while still writing report-only analysis brief, inventory, and rebuild
  manifest artifacts.
- CVRP and warehouse launcher `run.sh` templates now call the rebuild entry
  before exiting on completion-preflight failure, so accidental launches leave
  a delegated-analysis bundle instead of only `exit.txt`.

## Boundary Check

This is report-only launcher and postrun evidence handling. It does not change
Decision, `DecisionFeatures`, Protocol gates, budgets, lifecycle policy, or
CVRP/warehouse problem semantics. Copied resume artifacts remain launch input
until a current campaign actually runs.

## Verification

Focused local verification:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Result: `34 passed`.

Compile check:

```bash
python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/rebuild_postrun_acceptance.py \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py
```

Result: passed.

## Residual

Live CVRP/warehouse campaigns remain blocked until the WSL `gpt-5.5`
completion preflight returns a real non-empty chat completion.
