# v0.4 Postrun Prepared Contract Consistency

Date: 2026-06-19

## Purpose

Current-run delegated review uses the prepared problem family to decide which
warehouse/CVRP postrun summaries are required. The inventory/launcher prepared
contract is the authority for that routing. Before this repair,
`check_postrun_acceptance.py` checked that the analysis brief matched the run
root, but it did not reject an analysis brief whose `prepared_run_contract`
drifted from the inventory/launcher contract.

That left a narrow stale-artifact failure mode: a hand-written or stale brief
could claim the wrong problem family and steer readiness through the wrong
problem-specific summary path.

## Change

- Added required postrun acceptance check
  `analysis_brief_prepared_contract_consistency`.
- Added stable-field comparison between analysis-brief
  `prepared_run_contract` and the inventory/launcher prepared contract.
- Compared fields include schema/report-only markers, quality-judgment and
  `DecisionFeatures` exclusion markers, manifest and completion-preflight
  status, problem family, model, resume/control-pair identity, postrun report
  declarations, execution flags, and git identity.
- Problem-family routing in postrun acceptance now prefers the
  inventory/launcher prepared contract. The analysis brief value is a fallback,
  not the routing authority.

## Boundary

This is a report/readiness guard only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, solver code, or
runtime budgets. CVRP/warehouse semantics remain problem-owned; the generic
checker only verifies that prepared-contract identity did not drift between
current-run artifacts.

## Verification

Local checkout `6adb052a`:

```bash
python -m py_compile \
  scion/tools/check_postrun_acceptance.py \
  scion/scion/tests/test_check_postrun_acceptance.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  -k 'prepared_contract or accepts_actionable_problem_summary or cvrp_missing_direct or warehouse_ready_summary'
# 4 passed, 28 deselected

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py
# 32 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 72 passed
```

WSL checkout `15ef16c`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 72 passed in 17.59s
```

## Launch Impact

Prepare-only roots were regenerated from WSL runtime commit `15ef16c`:

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-contractconsistency-15ef16c-6r-gpt55-20260619T130229Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-contractconsistency-15ef16c-1r-gpt55-20260619T130228Z-claw`

Strict launch readiness for both roots reports `static_ready=true`,
`launch_ready=false`, exit `64`, and `git_runtime_consistent=ok` with
`checkout matches manifest commit`. The remaining blocker is external GPT-5.5
auth: completion preflight returns HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`; the latest auth
pool is `active=0`, `expired=1`, `refreshing=0`, `total=1`.

Do not launch either root until strict launch readiness reports
`launch_ready=true`.
