# v0.4 Warehouse Continuity Substance Postrun Guard

Date: 2026-06-19

## Purpose

Warehouse follow-up review needs to distinguish a real post-v2 plateau from
missed continuous-optimization opportunities. A current-run
`research_continuity` block is necessary, but its mere presence is not enough:
delegated review needs some evidence of branch depth, same-mechanism follow-up,
branch-lesson transfer, or weak-positive transfer before calling a
protocol-evaluated run plateau-review-ready.

Before this repair, `warehouse_followup_summary` could report
`protocol_evaluated_plateau_review_ready` when measurement-effect,
runtime-feedback, and research-continuity summaries existed, even if the
continuity summary was shallow.

## Change

`warehouse_followup_summary.evidence.research_continuity` now includes a
report-only `substantive` flag and supporting counters:

- `max_branch_depth`
- `same_mechanism_observed`
- `same_mechanism_selected`
- `branch_lessons_required`
- `branch_lessons_satisfied`
- `weak_positive_observed`
- `weak_positive_accepted`
- mechanism-family and active-shape counts

Warehouse plateau review readiness now requires substantive continuity. A
protocol-evaluated current run with only shallow continuity evidence is reported
as `protocol_evaluated_research_continuity_too_shallow` with evidence gap
`warehouse_research_continuity_evidence_too_shallow`.

## Boundary

This is a report-only delegated-analysis guard. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, campaign state,
proposal context, warehouse solver behavior, budgets, or launch readiness.

## Verification

Local checkout:

```bash
python -m py_compile scion/tools/postrun_analysis_brief.py

PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_analysis_brief.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Results: focused postrun analysis group `20 passed`; full v0.4
readiness/reporting group `84 passed`.

New regression coverage:

- preserves `protocol_evaluated_plateau_review_ready` when warehouse has
  protocol evidence plus substantive continuity signals; and
- rejects a protocol-evaluated run with shallow one-off continuity evidence as
  insufficient for plateau-review readiness.
