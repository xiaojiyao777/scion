# Warehouse Cost-Compression Telemetry Interpretation Repair

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`

## Summary

Warehouse validation-transfer evidence accepted a split-preserving
cost-compression mechanism: `split_delta_sum == 0` with positive
`cost_delta_sum` and `improving_move_count`. The telemetry guard could preserve
the zero split field as a warning, but downstream diagnostic interpretation
could over-read that single declared field as a mechanism-level no-effect
signal.

This repair keeps field-level warnings visible while preserving the aggregate
mechanism effect when another declared/probed effect field is positive.

## Changes

- `summary_mechanisms.py` no longer rewrites a positive aggregate mechanism
  effect to `declared_field_warning` solely because one declared effect field is
  zero. It records `declared_field_warning_status` and keeps
  `effect_status == "positive"`.
- `telemetry_validation.py` suppresses `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC` for
  a warning/failure item when the corresponding mechanism diagnostic already
  has positive effect evidence.
- Runtime guard tests now cover the generic alternate-positive-effect shape.
- Warehouse target-preview tests now cover the real split-preserving
  cost-compression shape with explicit `split_delta_sum` and `cost_delta_sum`
  expected telemetry.

## Boundary Check

The repair is generic telemetry interpretation. Warehouse semantics remain in
the warehouse problem spec and test fixture. No CVRP/VRP/warehouse-specific
rules were added to generic core, and no `DecisionFeatures`, protocol gates,
budgets, scheduling, or lifecycle policy changed.

## Acceptance

Commands run from `/home/clawd/research/or-autoresearch-agent`:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_runtime_telemetry_guard_mechanism_diagnostics.py -k "declared_field_zero_with_alternate"
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_warehouse_target_preview.py -k "split_preserving_cost_compression"
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_runtime_telemetry_guard_mechanism_diagnostics.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_warehouse_target_preview.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core/test_evaluation_pipeline.py -k "effect_zero"
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py -k "effect_zero"
python -m py_compile scion/scion/runtime/telemetry_guard/summary_mechanisms.py scion/scion/core/telemetry_validation.py scion/scion/tests/unit/test_runtime_telemetry_guard_mechanism_diagnostics.py scion/scion/tests/unit/test_warehouse_target_preview.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core/test_evaluation_pipeline.py scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py
```

Results:

- runtime guard focused test: `1 passed`
- warehouse focused test: `1 passed`
- runtime guard file: `12 passed`
- warehouse target-preview file: `43 passed`
- focused core effect-zero checks: `1 passed` and `1 passed`
- py_compile: passed
- full core evaluation telemetry/pipeline files: `37 passed`

## Residual Risk

This repairs interpretation of already-observed split-preserving
cost-compression telemetry. It does not by itself prove warehouse has a
long-run continuous-promotion path after champion `v2`; that still requires a
later repeated warehouse campaign.
