# v0.4 A/A Calibration Runtime Budget-Hit Evidence

Date: 2026-06-18

## Purpose

Close the remaining Worker F evidence caveat: A/A calibration pair rows recorded
elapsed runtime and the solver time limit, but did not explicitly say whether a
champion or candidate replay saturated its runtime budget.

This matters for CVRP/VRP because budget-exhausting anytime solvers can produce
low-SNR objective evidence whose interpretation depends on whether the
calibration replay was budget-saturated.

## Change

- Each A/A `pair_evidence` row now includes:
  - `champion_runtime_budget_ratio`
  - `candidate_runtime_budget_ratio`
  - `champion_runtime_budget_hit`
  - `candidate_runtime_budget_hit`
- The hit flag is true when elapsed runtime reaches at least `0.98` of the
  resolved solver time limit.
- Missing elapsed runtime is represented as `null`, not as a false hit.

These fields remain problem-owned calibration diagnostics. They are not added
to `DecisionFeatures` and do not change protocol gates.

## Verification

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/test_aa_calibration.py \
  scion/scion/tests/unit/test_cli_data_roots.py \
  scion/scion/tests/test_cvrp_formal_readiness.py \
  scion/scion/tests/test_models.py
```

Local result: `44 passed in 0.65s`.

WSL result after fast-forwarding to the accepted runtime evidence commit:
`44 passed in 0.33s`.

## Acceptance

Accepted as Worker F residual-caveat closure.
