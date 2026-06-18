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
- Added a CLI ingress regression test proving `scion run` with a problem-v1
  package passes the resolved measurement-governed `ProtocolConfig` into
  `CampaignManager`; `--measurement-governance record-only` keeps readiness
  status visible while leaving behavior fields on protocol defaults.
- Replaced warehouse `problem-v1.yaml` hard-coded local absolute paths with
  relative `root_dir` and canary paths so the same assets resolve under both
  the local checkout and the WSL synchronized checkout.

No runtime decision behavior changed.

## Verification

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_config.py \
  scion/scion/tests/test_problem_bridge.py \
  scion/scion/tests/test_cvrp_formal_readiness.py \
  scion/scion/tests/test_models.py
```

Local result: `57 passed in 0.79s`.

WSL result after fast-forwarding to the accepted path-fix commit:
`57 passed in 0.40s`. The initial WSL run caught the absolute-path defect; the
rerun verifies the warehouse production/package specs now resolve the
repository-local `surrogate` calibration asset in the synchronized checkout.

CLI ingress follow-up:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_cli_run_options.py::test_run_problem_v1_measurement_declaration_governs_protocol_config \
  scion/scion/tests/test_config.py::test_cvrp_formal_protocol_consumes_problem_measurement_declaration \
  scion/scion/tests/test_config.py::test_warehouse_prod_protocol_consumes_problem_measurement_declaration
```

Local result: `4 passed in 0.62s`.

Adjacent regression sweep:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_cli_run_options.py \
  scion/scion/tests/test_config.py \
  scion/scion/tests/test_problem_bridge.py
```

Local result: `45 passed in 1.30s`.

## Acceptance

Accepted as Worker A closure evidence. Formal CVRP and warehouse production
assets, plus the `scion run` problem-v1 ingress path, now have regression
coverage proving problem-owned measurement declarations feed deterministic
protocol/runtime/pairing/readiness fields while raw calibration diagnostics
remain outside `DecisionFeatures`.
