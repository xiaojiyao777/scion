# CVRP Solver Modularization 2026-05-19

## Current Decision

`scion/scion/problems/cvrp/solver.py` is no longer the CVRP research object. It
is a public facade and runtime shell: load an instance, load the active
algorithm package, validate the returned solution through the adapter, write
runtime audit fields, and emit a structurally valid fallback only when the
active package fails.

The active research object is:

```text
scion/scion/problems/cvrp/policies/baseline_algorithm.py
scion/scion/problems/cvrp/policies/baseline_modules/
```

All selectable/targetable CVRP research exposure now converges to
`solver_design`. The legacy component-policy and operator surfaces are not
long-term runtime objects and should not receive new algorithm work.

## Why `solver.py` Grew

`solver.py` became a monolith because it was the only executable CVRP boundary
while Scion was hardening protocol, adapter, preview, runtime audit, and
solver-design smoke behavior. Each compatibility or smoke fix landed where the
runner already executed, so unrelated responsibilities accumulated:

- CLI and JSON/CVRPLIB instance resolution.
- Construction fallback and solution/objective validation.
- Registry operators and route-local/route-pair/ruin-recreate surfaces.
- Component policy loaders for construction, baseline, search, main-search,
  ALNS/VNS, destroy/repair, route-pair candidates, and acceptance/restart.
- Main-search telemetry, route-pool/BDR/local-search runtime hooks, and legacy
  audit payloads.
- Full solver-design loading/context support for the active algorithm package.

That shape obscured the real research boundary. The cleanup direction is not to
keep every old surface alive in better-named helper files; it is to make the
active algorithm package complete and delete surfaces that are no longer part
of the research path.

## Active Package Boundary

The active package now owns the complete ALNS+VNS algorithm stack:

- `baseline_algorithm.py`: stable `solve(instance, rng, time_limit_sec,
  context)` entrypoint.
- `baseline_modules/config.py`: controlled parameters and thresholds.
- `baseline_modules/state.py`: internal `_Route` and `_Solution` bridge from
  the public `CvrpInstance`/`CvrpSolution` model.
- `baseline_modules/construction.py`: Clarke-Wright, nearest-neighbor, sweep,
  and capacity-balanced construction.
- `baseline_modules/scheduler.py`: ALNS+VNS lifecycle, runtime-budget checks,
  adaptive operator selection, phase timing, stop reasons, and telemetry calls.
- `baseline_modules/destroy_repair.py`: random, worst, Shaw, and route removal
  with greedy/regret repair.
- `baseline_modules/local_search.py`: VNS loop with 2-opt, relocate, Or-opt,
  swap, and 2-opt* neighborhoods.
- `baseline_modules/acceptance.py`: adaptive weights and simulated annealing.

`solver_runtime/algorithm_runtime.py` owns the shell-side loader and bounded
`SolverAlgorithmContext`: make/validate solutions, objective helpers,
remaining-time helpers, and `solver_algorithm_*` telemetry. These are runtime
services, not algorithm ownership.

## Removed Legacy Research Surfaces

The following files/surfaces were removed from the active package and from
CVRP-owned runtime/preview tests:

- `policies/acceptance_restart_policy.py`
- `policies/algorithm_blueprint.py`
- `policies/alns_vns_policy.py`
- `policies/baseline_policy.py`
- `policies/construction_policy.py`
- `policies/destroy_repair_policy.py`
- `policies/main_search_strategy.py`
- `policies/neighborhood_portfolio.py`
- `policies/route_pair_candidate_policy.py`
- `policies/search_policy.py`
- `policies/solver_algorithm.py`
- `operators/__init__.py`
- `operators/base.py`
- `registry.yaml`
- legacy runtime modules for neighborhood portfolio/operator registry and the
  route-pair/BDR/route-pool family created during earlier quarantine slices
- legacy preview modules for component policies and main-search/deep-policy
  checks

`problem-v1.yaml` now declares one active research surface:

```text
solver_design
```

Its editable targets are only:

```text
policies/baseline_algorithm.py
policies/baseline_modules/*.py
```

## Current `solver.py` Shape

`solver.py` is now a small runtime shell:

- Public `solve(...)` remains as a deterministic construction fallback for
  invalid active-branch output.
- CLI loads `policies/baseline_algorithm.py` through
  `solver_runtime/algorithm_runtime.py`.
- Returned solutions are adapter-normalized and adapter-objective recomputed.
- `--registry` is accepted for runner compatibility but ignored and audited as
  `registry_path_ignored`.
- Deleted legacy hooks are not loaded, selected, or audited as active behavior.

Line-count status after cleanup:

- `solver.py`: 191 lines.
- Largest active/runtime CVRP module in this slice:
  `solver_runtime/algorithm_runtime.py`, 510 lines.
- Largest active algorithm module:
  `policies/baseline_modules/local_search.py`, 275 lines.

## Remaining Debt

The main CVRP P0 solver monolith is closed as a line-count blocker. Follow-up
debt is now limited to keeping runtime shell services small:

- `solver_runtime/algorithm_runtime.py` should stay small. If more shell
  services are needed, split by responsibility: loader, context telemetry,
  objective/solution bridge, and fallback construction.
- Proposal/context tooling no longer exposes `policies/solver_algorithm.py` as
  an inactive compatibility hook. Active solver-design file tools return only
  `policies/baseline_algorithm.py` and `policies/baseline_modules/*.py`.

Do not add new research behavior to `solver.py`. New CVRP algorithm work belongs
in the active package under `policies/baseline_algorithm.py` and
`policies/baseline_modules/`.
