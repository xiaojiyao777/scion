# CVRP Scheduler Iteration Telemetry Repair

Date: 2026-06-17

Commit under test: local working tree after `5476179`

## Purpose

The deep `initial_vns_disabled` WSL matrix rejected a simple initial-VNS
disable rule. Objective probes showed that disabling initial VNS mostly shifts
work into embedded VNS, so the next CVRP diagnostic needs scheduler-local
budget and iteration visibility rather than another broad mechanism guess.

This repair keeps all new fields in CVRP runtime/report artifacts. It does not
change generic `DecisionFeatures`, Protocol thresholds, validation/frozen
gates, or promotion semantics.

## Changes

- Fixed baseline scheduler phase accounting so `construction` records only the
  initial constructor/fallback work. Initial VNS is now timed only under
  `vns_initial` instead of also being included in `construction`.
- Added `alns_core` phase timing around destroy/repair, feasibility, and
  acceptance work, excluding embedded VNS and size70/two-opt polish.
- Added bounded `solver_algorithm_alns_iteration_trace` runtime diagnostics
  with per-iteration fields for iteration number, elapsed/remaining time before
  and after, destroy/repair operators, removal count `q`, post-repair and
  post-polish candidate distance, acceptance reason, and best-improvement flag.
- Preserved the new trace in CVRP mechanism-matrix `results.json`.
- Added summary CSV columns for `alns_iterations`,
  `alns_iteration_trace_count`, `alns_core_runtime_ms`,
  `vns_initial_runtime_ms`, `vns_embedded_runtime_ms`, and
  `vns_embedded_runtime_fraction`.

## Local Acceptance

Commands:

```bash
PYTHONPATH=$PWD/scion python -m py_compile \
  scion/scion/problems/cvrp/solver_runtime/algorithm_runtime.py \
  scion/scion/problems/cvrp/policies/baseline_modules/scheduler.py \
  scion/scion/problems/cvrp/evidence/mechanism_matrix.py \
  scion/tools/cvrp_mechanism_matrix.py

PYTHONPATH=$PWD/scion pytest -q \
  scion/scion/tests/test_cvrp_solver_algorithm_runtime.py \
  scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py
```

Result: `20 passed`; py_compile passed.

Smoke:

```bash
PYTHONPATH=$PWD/scion python scion/tools/cvrp_mechanism_matrix.py \
  --case-id P-n76-k4 \
  --case-limit 1 \
  --seed 1 \
  --mechanism canonical_alns_vns \
  --time-budget-sec 1 \
  --output-dir /tmp/scion-cvrp-instrumentation-smoke
```

The smoke completed `1/1` solver jobs and confirmed:

- raw runtime `solver_algorithm_alns_iteration_trace` length: `3`;
- phase runtime includes `construction`, `vns_initial`, `vns_embedded`, and
  `alns_core`;
- `results.json` preserves the trace;
- `summary.csv` writes ALNS iteration and phase-runtime columns.

## Next Diagnostic Gate

After commit and WSL synchronization, run a compact no-LLM instrumentation
matrix before any agentic CVRP campaign:

- cases: `P-n76-k4`, `CMT2`, `CMT4`, `M-n151-k12`;
- seeds: `1..5`;
- mechanisms: `canonical_alns_vns`, `embedded_vns_disabled`,
  `pure_alns_no_polish`;
- time budget: `3s` for comparability with the previous WSL diagnostics.

Acceptance for this gate is trace usefulness and mechanism diagnosis, not
promotion or solver-default change.
