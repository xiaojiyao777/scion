# v0.4 Phase 4 Code Source Visibility Coverage Repair

Date: 2026-06-18

## Purpose

TASK Phase 4 requires code-phase prompts to preserve direct visibility of the
champion/current-branch/target source needed to modify or judge the research
object. Postrun analysis briefs already summarize code-phase source visibility,
but the Phase 4 artifact inventory only had a broad `source_visibility`
coverage item. A run with a generic visibility ledger could therefore look
source-visible in the inventory even if no code-phase source guarantee was
available for delegated analysis.

## Change

- `postrun_artifact_inventory.py` now adds a separate report-only Phase 4
  evidence requirement: `code_source_visibility_guarantees`.
- The new requirement counts code-phase source visibility summaries from the
  proposal trajectory manifest, independent of generic visibility-ledger
  fingerprints.
- Existing `source_visibility` remains as the broad coverage signal; the new
  item answers the narrower code-phase question.

## Boundary Check

- This is postrun evidence coverage only.
- It is report-only and `decision_features_excluded`.
- It does not change prompt construction, Contract, Verification, Protocol,
  Decision, scheduling, lifecycle, budgets, promotion, or solver semantics.

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_proposal_trajectory_artifacts.py
# 28 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_analysis_brief.py
# 43 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_artifact_inventory.py
```

## Acceptance

Accepted as a Phase 4 auditability repair. Delegated postrun review can now see
whether code-phase source visibility was actually evidenced, rather than
inferring it from generic prompt visibility fingerprints.
