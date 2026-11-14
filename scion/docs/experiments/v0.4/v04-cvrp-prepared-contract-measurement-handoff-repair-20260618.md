# v0.4 CVRP Prepared Contract Measurement Handoff Repair

Date: 2026-06-18

## Purpose

Ensure future CVRP prepared launch roots cannot silently omit the
measurement/opportunity handoff added for proposal and delegated analysis.

Before this repair, `launch_cvrp_agentic_campaign.py` wrote the CVRP MDE,
low-SNR, reason-code, and measurable-opportunity diagnostics into the prepared
manifest, brief, and inventory. The prepared contract carried those fields when
present, but static readiness did not fail if a later prepared root omitted
them.

## Change

- `postrun_artifact_inventory.py` now adds CVRP-only prepared contract checks
  for:
  - `research_focus.measurement_opportunity_diagnostics`;
  - report-only/proposal-only boundary flags;
  - positive `screening_mde_at_power_80` and `practical_screen_delta`;
  - required low-SNR/MDE reason codes;
  - the four current measurable opportunity classes.
- `check_launch_readiness.py` consumes the existing prepared contract result,
  so a CVRP root without this handoff is no longer statically ready.
- Warehouse prepared roots are unaffected because these checks apply only when
  `problem_family=cvrp`.

## Boundary Check

- This is launch/readiness metadata validation only.
- It remains report-only and `decision_features_excluded`.
- It does not change Decision, `DecisionFeatures`, Protocol gates, scheduling,
  lifecycle, budgets, promotion, or problem solver semantics.

## Verification

Local:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_analysis_brief.py
# 42 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/check_launch_readiness.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_launch_readiness.py
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_analysis_brief.py
# 42 passed

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/check_launch_readiness.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_launch_readiness.py
```

## Acceptance

Accepted as a Phase 4 launch/readiness repair. The current CVRP and warehouse
prepared roots should be regenerated from a commit containing this contract
check before the next launch-readiness snapshot.
