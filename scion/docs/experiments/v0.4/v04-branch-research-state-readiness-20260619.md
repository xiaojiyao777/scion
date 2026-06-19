# v0.4 Branch Research State Readiness

Date: 2026-06-19

## Purpose

Phase 4 requires branch-level research review: within-branch depth, hypothesis
and event coverage, rollback/checkpoint behavior, trace coverage, and whether
later review can inspect the actual research trajectory instead of inferring it
from final promotion or plateau status.

`postrun_analysis_brief` already produced
`branch_research_state_summary`, but postrun readiness did not require the
summary for warehouse/CVRP delegated review. A hand-written problem summary
could therefore be current-run ready while omitting the branch audit surface.

## Change

`postrun_analysis_brief` now marks `branch_research_state_summary` as
non-mutating report-only evidence:

- `campaign_state_mutated=false`;
- `scheduler_state_mutated=false`;
- `promotion_state_mutated=false`.

`check_postrun_acceptance` now adds
`branch_research_state_actionability` for warehouse/CVRP current-run review.
The check requires the current schema, report-only boundary markers, excluded
raw prompts/responses/patch bodies, current-run evidence, an aggregate object,
and a top-branches list.

The check does not require a positive result, a promotion, or even a nonzero
branch count. Zero branch rows remain reviewable when the rest of the run
evidence supports a quality-blocked or otherwise valid negative conclusion.

## Boundary

This is postrun delegated-review readiness only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion inputs, scheduler state,
campaign state, proposal generation, problem solvers, or runtime budgets.

## Verification

Local checkout with uncommitted change:

```bash
python -m py_compile \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/check_postrun_acceptance.py \
  scion/scion/tests/test_check_postrun_acceptance.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  -k 'branch_research_state or accepts_actionable_problem_summary or champion_progress'
# 3 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 68 passed
```
