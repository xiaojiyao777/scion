# v0.4 Measurement Integration Real-Asset Coverage

Date: 2026-06-18

## Purpose

Close the Worker A acceptance gap for measurement integration by proving that
real CVRP and warehouse problem declarations are consumed by real protocol
configs, not only by synthetic fixtures.

## Change

- Added real-asset tests for CVRP formal `problem-v1.yaml` plus
  `formal/protocol.yaml`.
- Added real-asset tests for warehouse production `problem-v1.yaml` plus
  `protocol_prod.yaml`.
- Both tests call `ProtocolConfig.with_problem_measurement()` and assert the
  resulting config consumes problem-owned practical deltas, runtime model,
  pairing validity, and reduced measurement readiness.
- The tests also assert reduced readiness payloads do not expose calibration
  refs, pair evidence, or raw calibration rows.

No runtime behavior changed.

## Verification

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_config.py \
  scion/scion/tests/test_problem_bridge.py \
  scion/scion/tests/test_cvrp_formal_readiness.py \
  scion/scion/tests/test_models.py
```

Result: `57 passed in 0.82s`.

## Acceptance

Accepted as Worker A closure evidence. Formal CVRP and warehouse production
assets now have regression coverage proving problem-owned measurement
declarations feed deterministic protocol/runtime/pairing/readiness fields while
raw calibration diagnostics remain outside `DecisionFeatures`.
