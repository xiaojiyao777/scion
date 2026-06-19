# v0.4 Warehouse Plateau Review Inputs Guard

Date: 2026-06-19

## Purpose

Warehouse v0.4 acceptance requires more than a protocol-evaluated candidate. A
post-v2 plateau conclusion must also inspect measurement effect, runtime
feedback, and research continuity so Scion does not confuse a no-effect row
with a reviewed continuous-improvement result.

## Change

- `warehouse_followup_summary.interpretation` now reports
  `protocol_evaluated_review_inputs_incomplete` when a warehouse run reaches
  protocol evaluation but lacks measurement-effect, runtime-feedback, or
  research-continuity summaries.
- `protocol_evaluated_plateau_review_ready` is now reserved for warehouse runs
  that have current-run protocol evaluation and all three review-input
  summaries.
- Existing evidence gaps continue to list exactly which review inputs are
  missing.

## Boundary Check

- This is report-only delegated-review evidence.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or warehouse solver semantics.

## Verification

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_analysis_brief.py
# 10 passed
```

## Acceptance

Accepted as a warehouse follow-up auditability repair. Once `gpt-5.5` auth is
restored and the warehouse v2 follow-up runs, delegated review cannot call the
run plateau-review-ready from protocol rows alone; it must also have
measurement, runtime, and research-continuity review inputs.
