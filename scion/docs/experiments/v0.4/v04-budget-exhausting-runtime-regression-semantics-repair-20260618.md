# Budget-Exhausting Runtime Regression Semantics Repair

Date: 2026-06-18

## Context

The June 11 audits identified runtime governance as a v0.4 blocker for
anytime, budget-exhausting solvers. In that model, budget saturation and high
`runtime_regression_rate` are often artifacts of using the full configured time
budget, not standalone evidence that a solver-design branch is worse.

## Finding

Two paths still treated high runtime regression as actionable in
`budget_exhausting` mode:

- `protocol.gates._trajectory_divergent_low_snr_expand` blocked low-SNR
  trajectory-divergent screening expansion when `runtime_regression_rate >= 0.90`.
- hypothesis runtime feedback rendered `regression_rate=1.00` and could append
  strong runtime action guidance from that aggregate summary alone.

## Repair

- Low-SNR trajectory-divergent screening expansion now ignores
  `runtime_regression_rate` only when
  `config.runtime.runtime_model == "budget_exhausting"`.
- Prompt runtime feedback now renders
  `runtime_model=budget_exhausting` and
  `regression_rate=not_applicable_budget_exhausting`, and does not turn that
  aggregate runtime summary into strong runtime actionability by itself.

This preserves fail-closed behavior for candidate failures, negative objective
evidence, comparative runtime regressions, and runtime tie speedup checks.

## Boundary

The repair uses deterministic problem-declared runtime-model semantics. It does
not add LLM text, raw diagnostics, calibration refs, postrun metadata, or
proposal artifacts to `DecisionFeatures`. It is not a generic gate tightening,
budget cap, prompt truncation, or compression change.

## Verification

Local focused tests:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_protocol_stats_gates.py \
  scion/scion/tests/test_sprint_e2_context_runtime.py \
  scion/scion/tests/unit/core/test_runtime_budget_diagnostics.py
```

Result: `57 passed`.

Adjacent context/decision tests:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/test_decision_feature_extraction.py \
  scion/scion/tests/test_decision_screening.py
```

Result: `85 passed`.

## Remaining Caveat

No live campaign was launched for this repair because the WSL `gpt-5.5`
chat-completion route still returns HTTP `401`. The next CVRP follow-up should
confirm that budget-exhausting runtime feedback no longer pushes the agent
toward meaningless runtime-regression repair.
