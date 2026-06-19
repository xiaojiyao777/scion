# Warehouse Positive-Effect vs Plateau Readiness

Date: 2026-06-19

## Purpose

Tighten warehouse follow-up postrun review so a protocol-evaluated positive
effect at or above MDE cannot be mislabeled as
`protocol_evaluated_plateau_review_ready`.

## Change

- `warehouse_followup_summary.evidence.measurement_effect` now includes a
  deterministic measurement signal:
  `effect_signal`, `positive_effect_at_or_above_mde`,
  `plateau_consistent`, and `all_ci_high_below_mde`.
- Warehouse plateau-ready interpretation requires measurement to be
  plateau-consistent.
- Positive at-or-above-MDE warehouse evidence routes to
  `protocol_evaluated_positive_effect_review_ready`.
- Postrun acceptance recomputes the warehouse measurement signal from
  `measurement_effect_summary.aggregate` and rejects summaries whose
  interpretation disagrees with the review inputs.

All signals remain report-only postrun readiness evidence. They do not enter
Decision, `DecisionFeatures`, promotion, scheduler state, or solver semantics.

## Verification

Local command:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
```

Result:

```text
73 passed in 33.15s
```

The broader launch-readiness test group was intentionally deferred until after
committing because launch readiness checks the runtime worktree cleanliness of
`scion/tools`.

## Current Launch Status

No prepared root was relaunched by this repair. The active warehouse and CVRP
prepared roots remain statically ready, but live launch is still blocked until
the WSL `gpt-5.5` completion preflight succeeds.
