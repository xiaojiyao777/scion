# v0.4 Budget-Exhausting Decision/Lifecycle Runtime Semantics Repair

Date: 2026-06-18

## Purpose

Close the remaining decision-layer gap after the protocol gate and prompt
feedback repair for budget-exhausting solvers.

CVRP declares `runtime_model=budget_exhausting`, so a high aggregate
`runtime_regression_rate` can reflect anytime-budget saturation rather than a
comparative runtime regression. That field should remain auditable, but it must
not by itself block low-SNR trajectory-divergent expansion or archive a branch
through lifecycle soft-abandon.

## Change

- `DecisionEngine` now treats aggregate `runtime_regression_rate` as actionable
  only when the protocol runtime model is not `budget_exhausting`.
- `BranchLifecyclePolicy` now receives a deterministic
  `runtime_regression_rate_actionable` flag derived from `ProtocolConfig`.
- Lifecycle soft-abandon and repeated-signal signatures ignore
  `runtime_regression_rate` when that flag is false.
- `DecisionFeatures` remains problem-neutral. No runtime model, raw report
  metadata, or problem-specific diagnostic is added to decision features.

Comparative runtime behavior remains conservative: high actionable aggregate
runtime regression can still block low-SNR expansion and soft-abandon a branch.
Timeouts, runtime guard failures, candidate runtime failures, negative quality
evidence, and median runtime ratio vetoes remain fail-closed.

## Verification

Local focused tests:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_decision_screening.py \
  scion/scion/tests/unit/core/test_branch_lifecycle_policy.py
```

Result: `78 passed in 0.64s`.

Local integrated runtime/decision tests:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_decision_screening.py \
  scion/scion/tests/unit/core/test_branch_lifecycle_policy.py \
  scion/scion/tests/test_protocol_stats_gates.py \
  scion/scion/tests/test_sprint_e2_context_runtime.py \
  scion/scion/tests/unit/core/test_runtime_budget_diagnostics.py \
  scion/scion/tests/test_decision_feature_extraction.py \
  scion/scion/tests/test_models.py
```

Result: `192 passed in 0.94s`.

## Acceptance

Accepted as a v0.4 runtime-semantics repair. It completes the narrow
budget-exhausting interpretation path across protocol gate, prompt feedback,
Decision, and lifecycle policy without adding new broad budgets, prompt
compression, generic gate tightening, or problem-specific decision features.
