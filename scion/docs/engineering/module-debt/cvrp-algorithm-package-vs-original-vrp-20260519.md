# CVRP Active Algorithm Package Vs Original `vrp/` 2026-05-19

## Read-Only Reference

The original `vrp/` tree was used only as a read-only reference:

- `vrp/docs/algorithm.md`
- `vrp/src/solver.py`
- `vrp/src/construction.py`
- `vrp/src/alns/destroy.py`
- `vrp/src/alns/repair.py`
- `vrp/src/alns/weights.py`
- `vrp/src/local_search/operators.py`
- `vrp/src/local_search/vns.py`
- `vrp/src/acceptance.py`
- `vrp/src/models.py`

No files under `vrp/` were modified.

## Coverage Mapping

| Original `vrp/` responsibility | Active Scion package owner | Status |
| --- | --- | --- |
| Solver lifecycle, ALNS/VNS loop, thresholds, route limits | `policies/baseline_algorithm.py`, `baseline_modules/scheduler.py` | Covered through `_ALNSVNSSolver.solve(...)` and Scion runtime context. |
| Clarke-Wright, nearest-neighbor, sweep, capacity-balanced construction | `baseline_modules/construction.py` | Covered. |
| Random, worst, Shaw, and route removal | `baseline_modules/destroy_repair.py` | Covered. |
| Greedy, regret-2, and regret-3 repair | `baseline_modules/destroy_repair.py` | Covered. |
| Adaptive ALNS operator weights | `baseline_modules/acceptance.py` | Covered. |
| Simulated annealing acceptance | `baseline_modules/acceptance.py` | Covered. |
| VNS/local search: 2-opt, relocate, Or-opt 1/2/3, swap, 2-opt* | `baseline_modules/local_search.py` | Covered. |
| Route and solution state models | `baseline_modules/state.py` | Covered with Scion `CvrpInstance` bridge and public-output conversion. |
| Runtime budget and telemetry | `baseline_modules/scheduler.py`, `solver_runtime/algorithm_runtime.py` | Covered through `context.remaining_time*`, `record_phase`, `record_iteration`, `record_move`, and stop reasons. |

## Intentional Differences

The Scion package does not import the original `vrp/` source tree. It uses the
same algorithm families but runs through Scion-owned problem models, adapter
validation, runtime budgets, and telemetry.

The legacy Scion component-policy surfaces are not equivalent to the original
algorithm. They were transitional knobs created while wiring experiments and
runtime audit. They are not needed once the active algorithm package owns the
full construction, destroy/repair, acceptance, VNS/local-search, state, and
scheduler stack.

## Cleanup Conclusion

The active package is complete enough to be the sole CVRP research object.
Therefore:

- `problem-v1.yaml` exposes only `solver_design`.
- `search_space.editable` is limited to `policies/baseline_algorithm.py` and
  `policies/baseline_modules/*.py`.
- Deleted legacy files should not be restored for compatibility experiments.
- Future CVRP algorithm work should compare against this active package, not
  against `solver.py` or old component-policy surfaces.

Validation after the final cleanup:

- `context.list_algorithm_files` exposes only active solver-design files.
- `context.read_surface` no longer returns deleted CVRP component surfaces.
- Full repository tests passed: `1800 passed, 1 skipped`.
