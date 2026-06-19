# v0.4 CVRP Large-Twoopt Readiness Input Consistency

Date: 2026-06-19

## Purpose

`cvrp_large_twoopt_summary` is the delegated-review conclusion for the focused
CVRP bounded large-twoopt follow-up. `check_postrun_acceptance.py` must not
accept a stale or hand-written `bounded_twoopt_review_ready` summary when the
review-input summaries do not contain the matching large-twoopt direct evidence.

## Change

`scion/tools/check_postrun_acceptance.py` now recomputes the CVRP
large-twoopt mechanism signal from `measurement_effect_summary` and
`research_continuity_summary` during problem-summary/input consistency checks.

For CVRP summaries it compares these fields against the problem summary:

- `large_twoopt_mechanism.available`;
- `large_twoopt_mechanism.mechanism_family_available`;
- `large_twoopt_mechanism.direct_evidence_ready`;
- `large_twoopt_mechanism.protocol_row_count`.

If the summary claims `bounded_twoopt_review_ready`, the checker additionally
requires the recomputed review-input signal to be available.

## Boundary

This is postrun readiness validation only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, proposal
semantics, solver code, or runtime behavior.

## Verification

Local verification:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  -k 'cvrp_ready_summary_without_input_twoopt_evidence or missing_direct_evidence_conclusion or nonblocking_problem_summary_gaps'
# 3 passed, 22 deselected

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# 51 passed

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

Accepted locally for the CVRP large-twoopt delegated-review readiness path. A
problem-specific summary can no longer claim `bounded_twoopt_review_ready` when
the review-input summaries lack the corresponding large-twoopt direct evidence.
