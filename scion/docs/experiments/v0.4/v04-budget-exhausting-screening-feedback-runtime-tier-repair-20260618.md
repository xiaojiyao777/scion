# Budget-Exhausting Screening Feedback Runtime Tier Repair

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`

## Purpose

Close the remaining proposal-feedback leak in the budget-exhausting runtime
semantics repair. Decision, lifecycle, and prompt runtime context already treat
aggregate `runtime_regression_rate` as report-only when the problem declares
`runtime_model=budget_exhausting`, but `screening_feedback_summary()` still had
independent tiering logic that could classify a zero-effect CVRP screening row
as `runtime_regression`.

For CVRP-style anytime ALNS/VNS runs, a high aggregate runtime-regression rate
near the time limit can be budget saturation or millisecond jitter rather than
an actionable comparative slowdown. The agent should still see the raw value
for audit, but it must not be steered toward meaningless runtime repair when
objective evidence is unchanged.

## Change

- `scion/scion/proposal/screening_feedback.py` now reads
  `candidate_surface_runtime_summary.runtime_budget_diagnostic.runtime_model`
  or the top-level `runtime_model`.
- Under `runtime_model=budget_exhausting`, aggregate runtime slowdown is not
  used to assign the `runtime_regression` screening feedback tier.
- Raw `runtime_regression_rate` remains visible in `runtime_summary`.
- Proposal-visible runtime evidence now marks
  `runtime_regression_rate_interpretation=not_applicable_budget_exhausting`.
- Comparative or unspecified runtime evidence keeps the existing
  `runtime_regression` behavior when sample confidence and slowdown thresholds
  are met.

## Boundary Check

- This is proposal feedback only. It does not modify `DecisionFeatures`,
  promotion gates, lifecycle transition rules, budgets, truncation, compression,
  or CVRP protocol parameters.
- The raw runtime metric remains reportable for audit and debugging.
- Problem semantics remain problem-owned through the declared runtime model;
  generic proposal feedback only consumes the deterministic declaration.

## Verification

Local focused verification passed:

```bash
python -m py_compile scion/scion/proposal/screening_feedback.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/test_screening_feedback_tiers_memory.py \
  scion/scion/tests/unit/test_agentic_feedback_screening.py \
  scion/scion/tests/test_sprint_e2_context_runtime.py
```

Result:

```text
24 passed
```

The new coverage confirms:

- budget-exhausting zero-effect rows with high aggregate
  `runtime_regression_rate` remain `no_effect`;
- the raw regression rate is still exposed with
  `not_applicable_budget_exhausting`;
- `feedback.query_screening` exposes the same interpretation to the agent;
- existing comparative/unspecified runtime regression tier behavior remains
  intact.

## Residual Risk

Live CVRP and warehouse campaigns are still blocked by the current `gpt-5.5`
authentication failure, so this repair is code/test verified but not yet
validated in a fresh agentic campaign. Launch prepared roots only after a real
`/v1/chat/completions` preflight succeeds with non-empty output.
