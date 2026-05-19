# CVRP Solver Modularization 2026-05-19

## Purpose

`scion/scion/problems/cvrp/solver.py` remains the public executable and import
facade for CVRP runtime compatibility, but it should no longer be the owner of
every CVRP solving concern. The modularization target is a set of CVRP-owned
runtime modules with stable responsibility boundaries:

- `solver.py`: public `solve`, CLI, top-level baseline/search orchestration, and
  compatibility re-exports for existing private imports during migration.
- `solver_runtime/policy_modules.py`: dynamic loading and eviction for
  branch/workspace policy modules.
- `solver_runtime/solution_ops.py`: solution coercion, feasibility/objective
  recomputation, and lexicographic objective helpers.
- `solver_runtime/timing.py`: bounded time-budget and exit-reserve helpers.
- `solver_runtime/neighborhood_portfolio.py`: neighborhood portfolio policy
  schema/loading plus portfolio scheduling counters and limits.
- `solver_runtime/operator_registry.py`: registry YAML parsing, workspace path
  isolation, generated operator instantiation, operator metadata, and operator
  audit events.

This keeps CVRP-specific behavior under `scion/problems/cvrp/` and avoids
moving route/capacity/ALNS/VNS semantics into generic Scion framework modules.

## First Slice Completed

This slice moved a cohesive post-baseline operator boundary out of `solver.py`:

- Neighborhood portfolio constants, defaults, policy loader, validation, event
  recording, component scheduling, attempt limits, and component runtime
  counters moved to `solver_runtime/neighborhood_portfolio.py`.
- Registry operator metadata, registry loading, operator path validation,
  generated class instantiation, weight coercion, component classification, and
  operator audit event recording moved to `solver_runtime/operator_registry.py`.
- `solver.py` imports these names explicitly and continues to expose the old
  private helper names, so existing tests and downstream imports through
  `scion.problems.cvrp.solver` remain valid.
- No contract, proposal, context, preview, adapter, or generic framework files
  were changed.

The split is intentionally behavior-preserving: runtime payload keys, default
values, scheduling order, clamping behavior, workspace path rejection, and
operator event shapes are unchanged.

## Remaining Debt

`solver.py` is still oversized and still owns several unrelated responsibilities:

- CLI and instance/root resolution.
- Construction policy loading and construction heuristics.
- Baseline policy schema, normalization, and repo-local baseline integration.
- Algorithm blueprint and legacy component-policy loading.
- Main-search strategy schema, planning, execution, recovery, and telemetry.
- Neighborhood implementations for 2-opt, relocate, route-pair swap, bounded
  destroy/repair, route-pool recombination, and route order polishing.
- `solver_algorithm` / `solver_design` runtime loading, bounded context API,
  timing, objective comparison, and telemetry.

The current facade shape is temporary. New behavior should land in the owning
submodule, not back into `solver.py`, unless it is only public orchestration or
compatibility wiring.

## Next Phase Order

1. Move construction/search/baseline policy schema and loading into focused
   `solver_runtime/*_policy.py` modules while preserving existing private
   re-exports from `solver.py`.
2. Move solver-design algorithm runtime into `solver_runtime/algorithm_runtime.py`:
   `_load_solver_algorithm*`, `_ObjectiveValue`, `_SolverAlgorithmContext`, and
   solver-algorithm audit helpers.
3. Split main-search into planning, execution, and telemetry modules before
   touching algorithm behavior.
4. Split neighborhood families into route-local, route-pair, bounded
   destroy/repair, and route-pool modules. These should depend on solution and
   timing helpers, not on `solver.py`.
5. Leave CLI and top-level `solve_baseline`/`improve_with_*` orchestration in
   the facade until the deeper runtime modules are stable, then shrink the
   facade further.

## Verification Expectations

Each slice should run at minimum:

- `python -m compileall -q scion/scion/problems/cvrp scion/scion/tests`
- `python -m pytest scion/scion/tests/test_cvrp_*_runtime.py scion/scion/tests/test_cvrp_solver_operator_runtime.py -q`
- adapter smoke coverage such as `python -m pytest scion/scion/tests/test_cvrp_adapter*.py -q`
- `git diff --check`
