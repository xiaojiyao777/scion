# v0.4 Branch Research State Input Consistency

Date: 2026-06-19

## Purpose

Warehouse/CVRP delegated review now requires
`branch_research_state_summary`, but the readiness check also has to prove that
the summary matches the current-run inventory. Otherwise a hand-written or stale
branch summary could satisfy the schema and boundary markers while disagreeing
with the branch, hypothesis, event, session, and trace evidence.

## Change

`check_postrun_acceptance` now recomputes the expected
`branch_research_state_summary` from `postrun_artifact_inventory` and compares
the analysis brief summary against it.

The consistency guard checks:

- `current_run_evidence` and `available`;
- branch count, lineage count, branch state counts, rollback counts, and failure
  code counts;
- branches with hypotheses, events, sessions, and traces;
- hypothesis count and status/action/change-locus counts;
- event kind/decision/stage counts;
- `top_branches`.

The check remains report-only. It does not require a positive research result,
branch depth, promotion, or nonzero branch count.

## Boundary

This is delegated-review input consistency only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion inputs, scheduler state,
campaign state, proposal generation, problem solvers, or runtime budgets.

## Verification

Local checkout `1507c0e2`:

```bash
python -m py_compile \
  scion/tools/check_postrun_acceptance.py \
  scion/scion/tests/test_check_postrun_acceptance.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  -k 'branch_research_state or accepts_actionable_problem_summary'
# 3 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 69 passed
```

WSL checkout `f12c3d8`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 69 passed
```

## Launch Impact

Prepared roots were regenerated from WSL runtime commit `f12c3d8` so the next
warehouse and CVRP launches use postrun readiness that checks branch research
state summaries against current-run inventory.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-branchconsistency-f12c3d8-6r-gpt55-20260619T123134Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-branchconsistency-f12c3d8-1r-gpt55-20260619T123146Z-claw`

Strict launch readiness for both roots reports `static_ready=true`,
`git_runtime_consistent=ok`, and `launch_ready=false` because real GPT-5.5
completion preflight still returns HTTP `401`, `classification=not_authenticated`,
`code=invalid_api_key`.
