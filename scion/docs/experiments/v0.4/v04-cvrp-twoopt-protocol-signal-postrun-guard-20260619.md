# v0.4 CVRP Two-Opt Protocol Signal Postrun Guard

Date: 2026-06-19

## Purpose

The CVRP large-instance two-opt follow-up should become review-ready only when
postrun evidence shows the bounded two-opt mechanism reached protocol/effect
rows. A continuity or research-shape family mention is useful context, but it
does not prove pair-level objective-effect evidence.

Before this repair, `cvrp_large_twoopt_summary` could treat a two-opt family
found only in research-continuity mechanism-family counts as a large-twoopt
mechanism signal.

## Change

`cvrp_large_twoopt_summary.evidence.large_twoopt_mechanism.available` now means:

- a large/two-opt family appears in measurement/protocol effect evidence; and
- the report has at least one protocol-effect row signal for that family.

Continuity family mentions are still preserved as
`continuity_families`, but they are context only. They do not satisfy the
bounded two-opt review-ready requirement.

Top effect rows can also provide the protocol signal when the aggregate
mechanism-family effect summary is absent, avoiding dependence on a single
aggregation shape.

## Boundary

This is a report-only delegated-analysis guard. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, campaign state,
proposal context, or CVRP solver behavior.

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

Results: focused postrun analysis group `19 passed`; full v0.4
readiness/reporting group `83 passed`.

New regression coverage:

- rejects continuity-only two-opt family mentions as insufficient for
  `bounded_twoopt_review_ready`;
- accepts top-row two-opt protocol-effect signals even when the aggregate
  family summary is absent; and
- preserves normal bounded two-opt review-ready behavior when measurement
  protocol rows and continuity context agree.
