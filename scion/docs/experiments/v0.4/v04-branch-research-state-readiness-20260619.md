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

Local checkout `b9dd1d1f`:

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

WSL checkout `8f2fe87`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 68 passed
```

## Launch Impact

Prepared roots were regenerated from WSL runtime commit `8f2fe87` so the next
warehouse and CVRP launches use postrun readiness that requires
`branch_research_state_actionability`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-branchstate-8f2fe87-6r-gpt55-20260619T122315Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-branchstate-8f2fe87-1r-gpt55-20260619T122328Z-claw`

Strict launch readiness for both roots reports `static_ready=true`,
`git_runtime_consistent=ok`, and `launch_ready=false` because real GPT-5.5
completion preflight still returns HTTP `401`, `classification=not_authenticated`,
`code=invalid_api_key`.
