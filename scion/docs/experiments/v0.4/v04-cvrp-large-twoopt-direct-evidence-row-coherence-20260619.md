# v0.4 CVRP Large-Twoopt Direct Evidence Row Coherence

Date: 2026-06-19

## Purpose

CVRP large-twoopt delegated review must not call a follow-up
`bounded_twoopt_review_ready` by stitching together evidence from unrelated
top effect rows. The acceptance claim requires the same matching top effect row
to carry positive effect, mechanism activation, objective-effect telemetry, and
phase telemetry.

## Change

`scion/tools/postrun_analysis_brief.py` now tracks
`complete_direct_evidence_row_count` for CVRP large-twoopt direct evidence.
`direct_evidence_ready` is true only when at least one matching
large/bounded/intra two-opt top row contains all required direct evidence on
that row.

The summary still reports the individual counts for audit. If individual
signals exist but no row contains all of them together, the missing reason is
`missing_complete_direct_evidence_row`.

## Boundary

This is postrun delegated-review evidence accounting only. It does not change
Decision, `DecisionFeatures`, Protocol gates, promotion, scheduler state,
proposal semantics, solver code, or runtime behavior.

## Verification

Local verification:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_analysis_brief.py -k 'large_twoopt_summary'
# 11 passed, 14 deselected

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# 49 passed

python -m py_compile \
  scion/tools/postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_analysis_brief.py
git diff --check
```

## Acceptance

Accepted for the CVRP large-twoopt postrun-review readiness path. A protocol row
family signal plus scattered direct evidence is no longer enough to call the
follow-up `bounded_twoopt_review_ready`; at least one matching top effect row
must contain the full direct-evidence bundle.
