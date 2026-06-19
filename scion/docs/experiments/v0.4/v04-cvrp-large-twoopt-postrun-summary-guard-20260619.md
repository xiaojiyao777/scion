# v0.4 CVRP Large Two-Opt Postrun Summary Guard

Date: 2026-06-19

## Purpose

The CVRP bounded large-instance two-opt prepared root carries strong handoff
constraints, but postrun review also needs a problem-specific summary. Protocol
rows alone should not make a bounded two-opt run review-ready if the root was
only prepared, if review inputs are missing, or if the evaluated mechanism does
not expose a large two-opt mechanism-family signal.

## Change

- Added report-only `cvrp_large_twoopt_summary` to
  `postrun_analysis_brief.py`.
- The summary classifies CVRP large-twoopt follow-up evidence as:
  `prepared_only_launch_required`,
  `quality_blocked_no_protocol_twoopt_conclusion`,
  `screened_without_protocol_evaluation`,
  `protocol_evaluated_review_inputs_incomplete`,
  `protocol_evaluated_without_large_twoopt_signal`,
  `bounded_twoopt_review_ready`, or
  `insufficient_current_run_evidence`.
- `bounded_twoopt_review_ready` requires current-run protocol evaluation,
  measurement-effect, runtime-feedback, research-continuity summaries, complete
  large-twoopt handoff coverage, and a large two-opt mechanism-family signal.
- Markdown briefs now render a `CVRP Large Two-Opt Summary` section with
  handoff requirements, evidence gaps, mechanism signal, and required review
  axes.

## Boundary Check

- This is report-only delegated-review evidence.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or CVRP solver semantics.

## Verification

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_launch_readiness.py
# 57 passed
```

## Acceptance

Accepted as a CVRP large-twoopt postrun auditability repair. Once `gpt-5.5`
auth is restored and the bounded large-twoopt root runs, delegated review must
separate missing review inputs, missing two-opt mechanism signal, and actual
bounded two-opt review-ready evidence before making any solver-improvement
claim.
