# v0.4 Phase 4 Research Continuity Subsignal Coverage Repair

Date: 2026-06-18

## Purpose

TASK Phase 4 requires evidence for specific research-loop behaviors: same
mechanism follow-up, branch lesson transfer, weak-positive transfer, and branch
depth. The postrun inventory already exposed a broad `research_continuity`
coverage item, but delegated review still had to inspect the report body to
know which Phase 4 signals were actually present.

## Change

- `postrun_artifact_inventory.py` now adds report-only Phase 4 evidence
  requirements for:
  - `same_mechanism_followup`;
  - `branch_lesson_usage`;
  - `weak_positive_transfer`;
  - `branch_research_shape`.
- The broad `research_continuity` coverage item remains for compatibility, but
  the narrower items make each effective-research signal independently
  auditable.

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
# 12 passed
```

## Acceptance

Accepted as a Phase 4 auditability repair. Delegated postrun analysis can now
distinguish "a continuity report exists" from the specific research-continuity
signals needed to judge whether v0.4 is supporting effective research.
