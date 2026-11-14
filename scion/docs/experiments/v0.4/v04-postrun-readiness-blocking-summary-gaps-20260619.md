# v0.4 Postrun Readiness Blocking Summary Gaps

Date: 2026-06-19

## Purpose

`POSTRUN_READINESS_EXIT_STATUS` should report whether delegated current-run
analysis is actually ready. Problem-specific summaries can contain useful
negative conclusions, such as quality-blocked proposals or a CVRP run evaluated
without a large two-opt mechanism signal. Those should not block readiness.

However, summaries with missing review inputs, incomplete handoff, launch-only
state, infra-only state, or no protocol evidence should not make
`current_run_analysis_ready=true`.

## Change

`check_postrun_acceptance.py` now records
`blocking_evidence_gaps` for `problem_summary_actionability` and fails that
check when a required problem summary contains blocking gaps such as:

- missing measurement-effect, runtime-feedback, or research-continuity summaries
- incomplete warehouse/CVRP prepared handoff
- launch-required or infra-only status
- no protocol-evaluated candidates

Nonblocking evidence gaps remain valid delegated-analysis outcomes. For
example, `missing_large_twoopt_mechanism_signal` still allows readiness because
it is a current-run conclusion that the bounded two-opt mechanism did not reach
protocol/effect evidence.

## Boundary

This is a report-only readiness guard. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, campaign state,
proposal context, problem solvers, budgets, or launch readiness.

## Verification

Local checkout:

```bash
python -m py_compile scion/tools/check_postrun_acceptance.py

PYTHONPATH=scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py

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

Results: focused postrun readiness group `7 passed`; full v0.4
readiness/reporting group `86 passed`.

New regression coverage:

- missing runtime-feedback in a warehouse problem summary blocks
  `current_run_analysis_ready`;
- shallow warehouse continuity remains nonblocking for readiness, because it is
  a valid current-run analysis conclusion rather than a missing input; and
- missing CVRP large-twoopt mechanism signal remains nonblocking for readiness,
  because it is a valid negative mechanism conclusion.
