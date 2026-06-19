# v0.4 Warehouse Readiness Input Consistency

Date: 2026-06-19

## Purpose

`warehouse_followup_summary` is the delegated-review conclusion for judging
continuous follow-on improvement versus a real post-v2 plateau. Postrun
acceptance must not accept a stale or hand-written
`protocol_evaluated_plateau_review_ready` summary when the review-input
`research_continuity_summary` does not contain realized continuity evidence.

## Change

`scion/tools/check_postrun_acceptance.py` now recomputes warehouse follow-up
continuity from `research_continuity_summary` during problem-summary/input
consistency checks.

For warehouse summaries it compares:

- `substantive`;
- `max_branch_depth`;
- `same_mechanism_selected` and `same_mechanism_observed`;
- `branch_lessons_satisfied` and `branch_lessons_required`;
- `weak_positive_accepted` and `weak_positive_observed`.

If the summary claims `protocol_evaluated_plateau_review_ready`, the checker
also requires the recomputed review-input continuity signal to be substantive.

## Boundary

This is postrun readiness validation only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, proposal
semantics, warehouse solver behavior, or runtime behavior.

## Verification

Local verification:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  -k 'accepts_actionable_problem_summary or review_inputs_boundary_markers or warehouse_ready_summary_without_realized_input_continuity'
# 3 passed, 23 deselected

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# 52 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_postrun_artifact_inventory.py
# 14 passed

python -m py_compile \
  scion/tools/check_postrun_acceptance.py \
  scion/scion/tests/test_check_postrun_acceptance.py
git diff --check
```

## Acceptance

Accepted locally for the warehouse follow-up delegated-review readiness path. A
problem-specific summary can no longer claim
`protocol_evaluated_plateau_review_ready` when the review-input summaries lack
realized continuity evidence.
