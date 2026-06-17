# Warehouse Validation-Transfer Acceptance Contract Repair

Date: 2026-06-17

## Context

The copied-config data-root fallback field gate reached validation but rejected
warehouse research quality. The `swap_orders` validation row failed with W/T/L
`8/1/6`, median delta `-200`, `VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`,
`split_delta_sum=0`, and about `1.025` median runtime ratio.

The follow-up audit classified this as real mechanism insufficiency, not
Contract, Verification, path-safety, telemetry, Decision, or Protocol failure.

## Repair

This repair strengthens warehouse problem-owned proposal/code guidance only.
It does not change generic Decision, Protocol thresholds, validation/frozen
gates, or `DecisionFeatures`.

Accepted warehouse order-level candidates now need an explicit
validation-transfer acceptance contract:

- prefer split-positive moves;
- if the mechanism is split-preserving cost-only, accept only computed
  `split_delta == 0` and `cost_delta > 0`;
- export the computed deltas through `self.validation_transfer_diagnostics`
  as `split_delta_sum` and `cost_delta_sum`;
- return the original solution otherwise;
- do not treat validation W/T/L or hypothesis text alone as sufficient.

The contract is surfaced in:

- `WarehouseDeliveryAdapter.active_subject_code_constraints(...)`;
- `WarehouseDeliveryAdapter.render_problem_measurement_diagnostics()`;
- warehouse validation-transfer prompt guidance;
- order-level `problem-v1.yaml` hypothesis/implementation/anti-pattern text.

## Local Acceptance

Commands:

```bash
PYTHONPATH=$PWD/scion pytest -q \
  scion/scion/tests/unit/test_warehouse_target_preview.py

python -m py_compile \
  scion/scion/problems/warehouse_delivery/adapter.py
```

Result: `42 passed`; py_compile passed.

## Next Gate

After committing this local repair, run one short warehouse agentic `6R` gate
when model/API conditions are healthy. This should be treated as proposal/code
behavior validation first, not warehouse efficacy proof. Acceptance should
require that quality blocks stop repeating missing validation-transfer risk,
bounded candidate policy, and split/cost guard failures; any validation row
must avoid the previous `split_delta_sum=0`, non-positive median, runtime
regression cost-only shape.
