# v0.4 Postrun Readiness Prompt Source Visibility Guard

Date: 2026-06-19

## Purpose

Warehouse and CVRP delegated postrun review should not be called
`current_run_analysis_ready=true` solely because a problem-specific summary is
present and actionable. The reviewer must also have current-run prompt/source
visibility accounting, including hypothesis target-source visibility, so branch
transfer, target-source grounding, and code context visibility can be audited
instead of inferred from final status.

## Change

`check_postrun_acceptance.py` now adds
`prompt_source_visibility_actionability` for warehouse and CVRP current-run
analysis readiness. The check requires
`analysis_brief.prompt_context_visibility_summary` to be available, marked as
current-run evidence, and to include nonzero aggregate trace, source
visibility trace, and visible hypothesis target-source trace counts.

The check is skipped for non-warehouse/CVRP roots. Missing prompt/source
visibility evidence now keeps `current_run_analysis_ready=false`, even if the
problem-specific warehouse/CVRP summary is otherwise actionable.

## Boundary

This is a report-only delegated-analysis readiness guard. It does not inspect
raw prompts or raw responses, and it does not change Decision,
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

Results: focused postrun readiness group `9 passed`; full v0.4
readiness/reporting group `88 passed`.

New regression coverage:

- actionable warehouse summary without prompt/source visibility blocks
  `current_run_analysis_ready`;
- actionable warehouse and CVRP summaries pass when current-run prompt/source
  visibility and hypothesis target-source trace accounting are present;
- source visibility accounting without hypothesis target-source visibility
  blocks `current_run_analysis_ready`; and
- the check remains non-required for roots without an expected warehouse/CVRP
  problem family.
