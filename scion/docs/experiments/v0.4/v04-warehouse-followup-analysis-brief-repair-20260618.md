# v0.4 Warehouse Follow-Up Analysis Brief Repair

Date: 2026-06-18

## Purpose

R5 requires warehouse to have a reproducibility/stagnation analysis, not just a
single promotion anecdote. The prepared warehouse manifest already carries the
champion-v2 follow-up question, but the delegated postrun analysis brief did
not summarize whether a root was only prepared, quality-blocked before protocol
evaluation, protocol-evaluated, or ready for plateau review.

## Change

- `postrun_analysis_brief.py` now emits
  `warehouse_followup_summary` for warehouse roots.
- The summary combines prepared handoff coverage with current-run protocol,
  measurement-effect, runtime-feedback, failure-taxonomy, and
  research-continuity summaries.
- The summary classifies warehouse follow-up evidence as:
  `prepared_only_launch_required`,
  `quality_blocked_no_protocol_plateau_conclusion`,
  `screened_without_protocol_evaluation`,
  `protocol_evaluated_plateau_review_ready`, or
  `insufficient_current_run_evidence`.
- Markdown briefs now include a `Warehouse Follow-up Summary` section with
  handoff requirements, evidence gaps, quality-block signal, protocol-evaluated
  counts, runtime feedback, and continuity availability.
- A required delegated-analysis question now explicitly asks whether warehouse
  follow-up distinguished prepared-only, quality-blocked, protocol-evaluated,
  and plateau-review-ready evidence.

This is report-only. It does not change Decision, `DecisionFeatures`, Protocol
gates, lifecycle, scheduler, promotion, proposal selection, or warehouse solver
semantics.

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py
# 6 passed in 0.19s

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py
# 10 passed in 0.13s

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 8 passed in 1.02s
```

## Acceptance

Accepted as an R5 auditability repair. Warehouse postrun briefs now separate
launch readiness, quality-blocked proposal behavior, and protocol-evaluated
stagnation evidence before any reviewer can call the post-v2 behavior a real
plateau. Because `postrun_analysis_brief.py` is part of the prepared-root
runtime guard set, existing prepared roots must be refreshed after this commit.
