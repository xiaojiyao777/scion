# v0.4 Phase 4 Protocol Stage Coverage Repair

Date: 2026-06-18

## Purpose

TASK Phase 4 asks whether repaired v0.4 can reach validation/frozen when
evidence justifies it, and requires postrun review to reconcile conclusions
against protocol metrics. Postrun analysis briefs already summarize protocol
accounting, but the Phase 4 artifact inventory did not expose a dedicated
coverage item for protocol row/candidate accounting or validation/frozen stage
accounting.

## Change

- `postrun_artifact_inventory.py` now adds report-only Phase 4 evidence
  requirements for:
  - `protocol_accounting`;
  - `validation_frozen_stage_accounting`.
- `protocol_accounting` is available when current-run research-efficiency
  reports expose protocol rows, formal candidate counters/artifacts, effective
  budget, or stage rows.
- `validation_frozen_stage_accounting` is available when the reports expose
  validation/frozen stage keys, even if their row counts are zero.

## Boundary Check

- This is postrun evidence coverage only.
- It is report-only and `decision_features_excluded`.
- It does not change Decision, `DecisionFeatures`, Protocol gates, scheduling,
  lifecycle, budgets, promotion, proposal context, or solver semantics.

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py
# 13 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_proposal_trajectory_artifacts.py
# 62 passed

ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 \
  xjy-ubuntu@127.0.0.1 'cd /home/xjy-ubuntu/research/or-autoresearch-agent && \
  PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_proposal_trajectory_artifacts.py'
# 62 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_artifact_inventory.py
```

## Acceptance

Accepted as a Phase 4 auditability repair. Delegated postrun review can now see
whether protocol/stage accounting is present before judging validation/frozen
reachability or protocol evidence completeness.
