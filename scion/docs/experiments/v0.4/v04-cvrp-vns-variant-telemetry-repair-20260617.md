# CVRP VNS Variant and Objective-Probe Telemetry Repair

Date: 2026-06-17

## Context

The focused 5-case matrix suggested a narrow `P-n76-k4` local-win pocket, but
the 20-seed deep diagnostic rejected that pocket as unstable. The remaining
useful signal is diagnostic: short-budget canonical ALNS+VNS can spend much of
the run inside VNS while the no-VNS/size70 probes run more ALNS iterations.

Before any CVRP LLM campaign, the next no-LLM matrix needs to separate initial
VNS, embedded VNS, size70/two-opt fallback, and pure ALNS/no-polish effects.

## Repair

This repair adds CVRP-owned diagnostic capability only:

- default mechanism matrices remain unchanged at the three existing mechanisms;
- explicit `--mechanism` selection can now use focused probes:
  `initial_vns_disabled`, `embedded_vns_disabled`, and
  `pure_alns_no_polish`;
- `SolverAlgorithmContext.record_objective_probe(...)` records bounded
  objective snapshots for phase attribution;
- the scheduler records initial objective and VNS before/after objective probes;
- `summarize_solver_output_for_job(...)` preserves these probes under
  `phase_telemetry.objective_probes`.

No generic `DecisionFeatures`, Protocol threshold, validation/frozen gate, or
canonical default mechanism set changed.

## Local Acceptance

Commands:

```bash
PYTHONPATH=$PWD/scion pytest -q \
  scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py

python -m py_compile \
  scion/scion/problems/cvrp/policies/baseline_modules/config.py \
  scion/scion/problems/cvrp/policies/baseline_modules/scheduler.py \
  scion/scion/problems/cvrp/solver_runtime/algorithm_runtime.py \
  scion/scion/problems/cvrp/evidence/mechanism_matrix.py \
  scion/tools/cvrp_mechanism_matrix.py
```

Result: `8 passed`; py_compile passed.

Smoke:

- default dry-run still produced `3` jobs;
- explicit local 3-second P-n76 smoke over canonical,
  `initial_vns_disabled`, `embedded_vns_disabled`, and `pure_alns_no_polish`
  completed `4/4`;
- canonical raw telemetry had `solver_algorithm_active=true`,
  `solver_algorithm_errors=0`, and objective probes including
  `initial_before_local_search`, `vns_initial_before`,
  `vns_initial_after`, and `vns_embedded_before`.

## Next Gate

Run a WSL no-LLM variant matrix on `P-n76-k4`, `CMT2`, `CMT4`, and
`M-n151-k12` with seeds `11`, `23`, `37`, and `47`, comparing canonical,
`initial_vns_disabled`, `embedded_vns_disabled`, current size70/two-opt
fallback, and `pure_alns_no_polish`.
