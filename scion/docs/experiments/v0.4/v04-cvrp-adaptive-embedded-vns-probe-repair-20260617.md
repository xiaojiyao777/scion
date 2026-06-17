# CVRP Adaptive Embedded VNS Probe Repair

Date: 2026-06-17

## Verdict

Accepted as a local no-LLM mechanism-probe repair. This change adds a narrow
CVRP-owned scheduler variant for evidence gathering:
`adaptive_embedded_vns_cadence4`.

It does not change generic Decision, Protocol gates, lifecycle policy, or
`DecisionFeatures`. Canonical behavior remains unchanged because the default
`EMBEDDED_VNS_CADENCE` is `1`.

## Rationale

The compact scheduler-instrumentation matrix from commit `875dc83` showed that
embedded VNS consumes most canonical runtime, but broad removal is not useful:

- canonical mean ALNS iterations: `4.0`;
- embedded-VNS-disabled mean ALNS iterations: `22.4`;
- embedded-VNS-disabled quality: `2/8/10` versus canonical, mean delta
  `+17.3`;
- pure ALNS/no-polish quality: `2/18/0`, mean delta `+35.6`;
- canonical mean embedded-VNS runtime fraction: `0.651`.

The next mechanism should therefore preserve VNS quality while reducing
low-value embedded VNS calls.

## Implementation

Files changed:

- `scion/scion/problems/cvrp/policies/baseline_modules/config.py`
- `scion/scion/problems/cvrp/policies/baseline_modules/scheduler.py`
- `scion/scion/problems/cvrp/evidence/mechanism_matrix.py`
- `scion/tools/cvrp_mechanism_matrix.py`
- `scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py`

New default config:

- `EMBEDDED_VNS_CADENCE = 1`
- `EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT = True`

New matrix mechanism:

- `adaptive_embedded_vns_cadence4`
- overlay: `config_adaptive_embedded_vns_cadence4`
- behavior: keep initial VNS enabled; run embedded VNS every fourth ALNS
  iteration, and also run it when the repaired candidate already improves the
  current or best solution before local polish.

## Local Acceptance

Commands:

```bash
PYTHONPATH=$PWD/scion python -m py_compile \
  scion/scion/problems/cvrp/policies/baseline_modules/config.py \
  scion/scion/problems/cvrp/policies/baseline_modules/scheduler.py \
  scion/scion/problems/cvrp/evidence/mechanism_matrix.py \
  scion/tools/cvrp_mechanism_matrix.py

PYTHONPATH=$PWD/scion pytest -q \
  scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py \
  scion/scion/tests/test_cvrp_solver_algorithm_runtime.py

PYTHONPATH=$PWD/scion pytest -q \
  scion/scion/tests/test_cvrp_solver_algorithm_runtime.py \
  scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py \
  scion/scion/tests/unit/test_cvrp_active_solver_map_provider.py \
  scion/scion/tests/unit/test_expected_telemetry_activation_contract.py

rm -rf /tmp/scion-cvrp-adaptive-vns-smoke &&
PYTHONPATH=$PWD/scion python scion/tools/cvrp_mechanism_matrix.py \
  --case-id P-n76-k4 --case-limit 1 --seed 1 \
  --mechanism canonical_alns_vns \
  --mechanism adaptive_embedded_vns_cadence4 \
  --time-budget-sec 1 \
  --output-dir /tmp/scion-cvrp-adaptive-vns-smoke
```

Results:

- py_compile passed.
- Focused runtime/matrix tests: `20 passed`.
- Broader related suite: `35 passed`.
- `git diff --check` passed for touched files.
- Smoke completed `2/2` jobs.

Smoke signal:

- Canonical: `total_distance=650`, `alns_iterations=3`,
  `vns_embedded_runtime_ms=601`, embedded VNS probes `3`.
- Adaptive cadence-4: `total_distance=650`, `alns_iterations=4`,
  `vns_embedded_runtime_ms=17`, embedded VNS probes `1`.

The smoke proves the overlay executes and reduces embedded VNS calls without
breaking output schema. It is not an efficacy claim.

## Next Gate

Run a WSL no-LLM canonical-vs-adaptive matrix before using this mechanism in an
agentic CVRP campaign:

- cases: `P-n76-k4`, `CMT2`, `CMT4`, `M-n151-k12`;
- seeds: `1..5`;
- mechanisms: `canonical_alns_vns`, `adaptive_embedded_vns_cadence4`;
- time budget: `3s`.

Accept the probe only if it preserves or improves paired quality while reducing
embedded-VNS runtime pressure. If it fails, the proposal-context direction
should be refined before any long agentic CVRP run.
