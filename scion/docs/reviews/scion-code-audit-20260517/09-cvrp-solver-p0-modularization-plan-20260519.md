# 09 - CVRP Solver P0 Modularization Plan 2026-05-19

## Scope

This is a planning document only. It analyzes:

- `scion/scion/problems/cvrp/solver.py` - 9340 lines.
- `scion/scion/tests/test_cvrp_solver_operator_runtime.py` - 4880 lines.

The implementation target is behavior-preserving modularization. It is not a
solver experiment, not a policy redesign, and not permission to edit original
external VRP algorithm files under `vrp/src`.

v3 remains the foundation: Scion core owns framework governance, protocol, and
deterministic decisions; CVRP owns route/capacity/demand/objective/runtime
semantics under `scion/scion/problems/cvrp/`.

## Current Solver Responsibility Map

`solver.py` currently combines executable CLI, problem semantics, research
surface policy loading, baseline bridging, local search, full solver-design
runtime, and audit assembly.

| Lines | Symbols / Region | Current responsibility |
| ---: | --- | --- |
| 1-371 | module docstring, imports, `_..._RELATIVE_PATH`, allowed values, limits, defaults | Global constants for every CVRP runtime surface. This mixes CLI paths, solver-design surface names, search budgets, main-search schema, mechanism-policy vocabularies, and acceptance/restart defaults. |
| 373-454 | `solve`, `_select_construction_customer` | Small-fixture capacity-aware construction and construction-mode semantics. |
| 455-626 | `solve_baseline` | Baseline orchestration: construction, baseline policy merge, ALNS/VNS overrides, data-root baseline detection, formal-required baseline fallback, external baseline call, and baseline audit composition. |
| 627-776 | `improve_with_registry_operators` | Registry-operator loading, portfolio scheduling, bounded post-baseline operator loop, acceptance, invalid-output handling, and operator audit fields. |
| 777-975 | `_main` | Public CLI/runtime orchestration. Loads instance, selected solver-design algorithm, legacy policies, baseline, main search, algorithm blueprint, registry operators, objective recomputation, and final JSON runtime merge. |
| 976-1108 | `_LoadedOperator`, `_load_registry_operators`, `_resolve_instance_path`, `_find_vrp_baseline_root`, `_baseline_required_for_instance`, `_configured_data_roots` | Operator registry parsing and workspace path checks, plus CVRP data-root and external baseline discovery. |
| 1109-1666 | `_load_construction_policy` through `_as_nonnegative_int` | Construction and baseline policy loading, defaults, normalization, scalar coercion, and event recording. |
| 1667-3405 | `_load_main_search_strategy` through `_record_main_search_event` | Main-search policy loading, huge default runtime shape, plan/schema normalization, instance profiling, component roles, fallback scheduling, baseline clamp evidence, and typed coercion. |
| 3406-4139 | `_load_algorithm_blueprint` through `_construct_with_main_search_strategy` | Legacy algorithm-blueprint surface loading/normalization and construction ensembles for algorithm blueprint and main search. |
| 4140-5108 | `improve_with_main_search_strategy` through `_merge_main_search_component_telemetry` | Main-search runtime engine: phase loop, component dispatch, perturbation/restart, phase-best vs recovery acceptance, component candidate choice, telemetry merge, and mechanism-policy application. |
| 5109-5215 | `improve_with_algorithm_blueprint` | Legacy algorithm-blueprint local-search runtime loop. |
| 5216-5774 | `_best_intra_route_2opt` through `_bounded_destroy_repair_subset_budget` | Local neighborhoods, route-pair candidate ranking, bounded destroy/repair move generation, destroy subset ranking and budgeting. |
| 5775-6162 | `_best_route_pool_recombination`, `_route_pool_sample_cap`, `_route_pool_sample_seed`, `_route_pool_recombination_from_solutions`, `_route_pool_polish_route_order` | Route-pool recombination, external baseline sampling for formal `.vrp` cases, route-set search, residual completion, branch-call limits, and route polishing. |
| 6163-6404 | `_remove_destroy_subset` through `_insertion_delta` | Destroy/repair mechanics, removal savings, repair selector dispatch, regret/cheapest insertion ranking, and repair budgets. |
| 6405-7148 | `_main_search_accepts` through `_mechanism_weight_mapping` | Acceptance comparison, plan reads, route-pool skip logic, perturbation, main-search telemetry recorders, objective tracing, phase timing, and generic mechanism-policy coercion. |
| 7149-7873 | `_load_alns_vns_policy` through `_record_acceptance_restart_event` | Mechanism policy loaders and schemas for ALNS/VNS, destroy/repair, route-pair candidate policy, and acceptance/restart policy. |
| 7874-8422 | `_load_neighborhood_portfolio` through `_call_policy_function` | Neighborhood portfolio and search-policy loaders, defaults, scalar coercion, dynamic policy module import, package module eviction, and workspace-root path handling. |
| 8435-8977 | `_load_solver_algorithm`, `_load_solver_algorithm_file`, `_ObjectiveValue`, `_SolverAlgorithmContext` | Solver-design runtime: preferred `baseline_algorithm.py` vs legacy `solver_algorithm.py`, selected-surface environment handling, generated algorithm execution, solution validation, objective comparison helper, context helper API, and solver-design telemetry. |
| 8978-9340 | `_record_policy_event` through `if __name__ == "__main__"` | External VRP baseline invocation, CVRP id mapping, registry portfolio filtering, operator instance loading, solution coercion, objective/feasibility helpers, time guards, event recording, and script entrypoint. |

The largest architectural issue is not one large function. It is that several
stable boundaries are co-located: public CLI facade, policy schema, policy
loading, algorithm runtime, local move semantics, telemetry schemas, and
external baseline bridging.

## Current Test Responsibility Map

`test_cvrp_solver_operator_runtime.py` is a single aggregate integration and
unit-test file. It tests multiple runtime modules that do not yet exist.

| Lines | Current responsibility |
| ---: | --- |
| 1-185 | Shared fixtures and helpers: `_Spec`, default algorithm body, subprocess runner, workspace copy, synthetic JSON/VRP writers, solver runner, artifact reconstruction. |
| 187-385 | Empty/missing registry behavior, registry operator improvement/no-op handling, workspace-local `CvrpSolution` coercion. |
| 386-514 | Required runtime fields for search, construction, and neighborhood portfolio surfaces. |
| 515-646 | Contract interface checks for default algorithm and baseline policies, baseline-policy required fields and invalid output. |
| 647-1043 | External VRP baseline integration, baseline-policy kwargs, ALNS/VNS policy overrides, ALNS/VNS audit, active main-search baseline budget policy. |
| 1060-1233 | Algorithm-blueprint required fields, active local search, invalid algorithm-blueprint output. |
| 1234-1354 | Main-search default required fields and inactive runtime-audit behavior. |
| 1355-1587 | Solver-design runtime fields, preferred `baseline_algorithm.py`, solver algorithm exceptions, legacy hook skip, context baseline/objective behavior. |
| 1635-2624 | Active main-search runtime, clamp details, component coverage, route-pair acceptance, perturbation, phase-best probing, recovery semantics, and bounded destroy/repair phase accept limits. |
| 2635-3613 | Route-pool recombination, baseline sample seeds/budgets, time reserve, residual completion, auto-add behavior, algorithm-body scope, phase ordering, construction pool, cleanup after recombination, route-pool telemetry. |
| 3628-4083 | Acceptance/restart recovery rejection, route-pair and destroy/repair mechanism-policy integration and activation. |
| 4084-4245 | Low-level destroy/repair selector, insertion, subset-budget, and fallback helper behavior. |
| 4246-4380 | Formal-like bounded destroy/repair budget and invalid main-search selected-surface runtime failure. |
| 4381-4690 | Safe CVRP instance API exposure plus search/construction/portfolio policy runtime error handling. |
| 4709-4880 | Operator invalid-output safety, operator exception reporting, and registry path escape rejection. |

The file also reaches into many private solver symbols. A migration must either
keep transitional re-exports from `solver.py` or split tests in lockstep with
runtime modules.

## Proposed Runtime Structure

Use a sibling implementation package while keeping `solver.py` as the
executable and import compatibility facade. The audit's logical `solver/*`
split is still the target shape, but a package named `solver/` next to
`solver.py` risks import ambiguity while `LocalSubprocessRunner` executes
`<workspace>/solver.py` directly. The low-risk P0 structure is:

```text
scion/scion/problems/cvrp/
  solver.py                         # thin CLI/import facade; executable script
  solver_runtime/
    __init__.py
    constants.py                    # path constants, limits, allowed values
    api.py                          # public solve(), solve_baseline() wrappers
    cli.py                          # argparse, runtime assembly, JSON output
    construction.py                 # construction modes and construction audit
    baseline.py                     # solve_baseline orchestration
    external_vrp.py                 # vrp/src discovery/import/id mapping only
    solution_ops.py                 # coercion, validity, objective, comparison
    timing.py                       # remaining-time and exit-reserve helpers
    policy_modules.py               # dynamic policy import, sys.path/module eviction
    policies/
      __init__.py
      search.py
      construction.py
      baseline.py
      neighborhood_portfolio.py
      algorithm_blueprint.py
      main_search.py                # plan schema/defaults/normalization only
      mechanisms.py                 # shared mechanism scalar/list coercion
      alns_vns.py
      destroy_repair.py
      route_pair.py
      acceptance_restart.py
    operators/
      __init__.py
      registry.py                   # registry.yaml loading and operator facade
      portfolio.py                  # registry operator portfolio scheduling
    algorithm_blueprint/
      __init__.py
      runtime.py                    # legacy algorithm_blueprint improvement loop
    main_search/
      __init__.py
      planning.py                   # component roles/order, phase component plan
      runtime.py                    # improve_with_main_search_strategy
      components.py                 # component dispatch and candidate choice
      telemetry.py                  # runtime field updates/objective trace
      acceptance.py                 # main-search acceptance/recovery semantics
    neighborhoods/
      __init__.py
      local.py                      # intra-route 2-opt, inter-route relocate
      route_pair.py                 # route-pair swap ranking and move execution
      destroy_repair.py             # BDR move, removal, repair, insertions
      route_pool.py                 # route-pool sampling/recombination/polish
    solver_design/
      __init__.py
      runtime.py                    # load preferred/legacy solver algorithm
      context.py                    # _SolverAlgorithmContext and _ObjectiveValue
      telemetry.py                  # solver_algorithm audit defaults/events/timing
```

Compatibility facade requirements:

- `solver.py` must remain runnable by `python solver.py ...` because
  `LocalSubprocessRunner` constructs that command.
- `from scion.problems.cvrp import solver as cvrp_solver` must keep working.
- `from scion.problems.cvrp.solver import solve` must keep working.
- During migration, private names used by tests or framework-adjacent unit tests
  should be re-exported from `solver.py` with explicit imports. Do not use a
  dynamic `globals()` export bucket.
- The facade should eventually contain only imports, `main()`, and
  `if __name__ == "__main__": main()`.
- After implementation, `problem-v1.yaml` should explicitly keep the new
  `solver_runtime/**/*.py` files frozen or otherwise outside editable research
  surfaces. Runtime internals are problem-owned but not candidate-owned.

## Migration Phases

Each phase must leave the existing CLI, imports, and tests runnable. The
default verification after each phase should be:

```bash
python -m compileall -q scion/scion/problems/cvrp scion/scion/tests
python -m pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/unit/test_research_surfaces_policy_runtime.py -q
```

Use narrower focused tests while editing, but run the aggregate file before
leaving each phase until the test split is complete.

### Phase 0 - Guardrails And Inventory

- Add no behavior.
- Confirm current import users of `scion.problems.cvrp.solver` and private
  helper imports.
- Decide the transitional re-export list in `solver.py`.
- Add `solver_runtime/` package scaffolding only if the first extraction lands
  in the same change.
- Do not touch `vrp/src`.

Stable state: `solver.py` still owns behavior and all tests are unchanged.

### Phase 1 - Extract Pure Utilities And Dynamic Policy Loading

Move the least coupled code first:

- `constants.py` for path names, limits, allowed values, and default scalar
  constants.
- `solution_ops.py` for `_coerce_solution`, `_solution_is_valid`,
  `_objective_for_solution`, `_lexicographic_improves`, `_objective_distance_delta`.
- `timing.py` for `_time_exhausted`, `_remaining_time_sec`,
  `_bounded_exit_reserve_sec`, `_main_search_time_exhausted`,
  `_route_pool_time_exhausted`.
- `policy_modules.py` for `_load_policy_module`, `_policy_module_name`,
  `_policy_workspace_root`, `_evict_module_tree`, `_call_policy_function`.

Keep all original names re-exported from `solver.py`. This slice reduces later
diff noise and isolates the helpers that most modules will import.

Stable state: no test moves required; existing aggregate tests still pass.

### Phase 2 - Extract Policy Schemas, Defaults, And Loaders

Move policy loading and normalization by surface:

- Search policy and neighborhood portfolio.
- Construction policy.
- Baseline policy.
- ALNS/VNS, destroy/repair, route-pair, acceptance/restart mechanism policies.
- Algorithm-blueprint policy.
- Main-search plan defaults and normalization.

Keep module boundaries strict: these modules normalize policy output and emit
audit dictionaries, but they do not run search loops.

Stable state: `solver.py` imports loaders from `solver_runtime.policies.*` and
re-exports private compatibility names. The big test file and
`unit/test_research_surfaces_policy_runtime.py` still pass.

### Phase 3 - Extract Neighborhood And Component Mechanics

Move search component implementations:

- `neighborhoods/local.py`: `_best_intra_route_2opt`, `_best_inter_route_relocate`.
- `neighborhoods/route_pair.py`: `_best_route_pair_swap`,
  `_rank_route_pair_swap_candidates`, `_rank_swap_positions`.
- `neighborhoods/destroy_repair.py`: `_best_bounded_destroy_repair`,
  removal ranking, subset budgeting, repair insertion helpers.
- `neighborhoods/route_pool.py`: route-pool sample cap/seed, baseline sampling,
  recombination search, residual completion, and route polishing.
- `main_search/components.py`: dispatch and candidate-choice logic that calls
  the neighborhood modules.

Stable state: main-search runtime still lives in `solver.py`, but component
logic has a clear package boundary. Re-export monkeypatch targets until tests
move.

### Phase 4 - Extract Main-Search Runtime And Telemetry

Move the main-search execution cluster:

- `main_search/planning.py` for phase/component order and component top-k.
- `main_search/runtime.py` for `improve_with_main_search_strategy`.
- `main_search/telemetry.py` for all `_record_main_search_*`,
  objective trace, coverage status, phase runtime, and repair-count merging.
- `main_search/acceptance.py` for acceptance/recovery logic and
  acceptance/restart policy application.

Do this after neighborhoods so `runtime.py` depends downward on focused
component modules. Do not let telemetry import protocol, Decision, APS, or
framework feedback code.

Stable state: `solver.py` still exposes `improve_with_main_search_strategy`;
existing runtime JSON keys remain byte-for-byte compatible where practical.

### Phase 5 - Extract Baseline, External VRP Bridge, And Algorithm Blueprint

Move:

- `baseline.py`: `solve_baseline` orchestration and baseline audit merge.
- `external_vrp.py`: `_find_vrp_baseline_root`,
  `_baseline_required_for_instance`, `_configured_data_roots`,
  `_solve_with_vrp_baseline`, `_map_vrp_customer_to_scion`.
- `construction.py`: construction helper and construction audit.
- `algorithm_blueprint/runtime.py`: construction ensemble and legacy local
  search improvement loop.

Keep original external VRP imports contained in `external_vrp.py`, and do not
modify external `vrp/src` files.

Stable state: CLI still runs through facade; baseline and algorithm-blueprint
tests remain in the aggregate test file.

### Phase 6 - Extract Solver-Design Runtime And CLI

Move:

- `solver_design/runtime.py`: preferred/legacy solver algorithm loading.
- `solver_design/context.py`: `_SolverAlgorithmContext` and `_ObjectiveValue`.
- `solver_design/telemetry.py`: solver_algorithm defaults, events, timing, and
  inactive-record cleanup.
- `cli.py`: `_main` body, argparse, sequencing, final runtime merge, JSON write.

`solver.py` becomes the real facade at this point. It should import explicit
public and transitional private names, expose `main`, and execute `main()` when
run as a script.

Stable state: subprocess runner still executes `solver.py`; selected
`solver_design` still prefers `policies/baseline_algorithm.py`; legacy
`policies/solver_algorithm.py` remains compatibility behavior only.

### Phase 7 - Split The Oversized Test File

Split tests after runtime modules are stable enough that import targets are
obvious. Keep the original test file as a tiny compatibility placeholder for
one release cycle if needed, but do not keep test logic there.

Stable state:

```bash
python -m pytest \
  scion/scion/tests/cvrp_solver_runtime_support.py \
  scion/scion/tests/test_cvrp_solver_*.py \
  scion/scion/tests/test_cvrp_main_search_*.py \
  scion/scion/tests/test_cvrp_route_pool.py \
  scion/scion/tests/test_cvrp_destroy_repair.py \
  scion/scion/tests/test_cvrp_route_pair.py \
  scion/scion/tests/test_cvrp_acceptance_restart.py \
  scion/scion/tests/test_cvrp_solver_operator_runtime.py \
  -q
```

## Test Split Map

Create one shared support module:

- `scion/scion/tests/cvrp_solver_runtime_support.py`
  - `_Spec`
  - `_default_algorithm_body`
  - `_runner`
  - `_workspace`
  - `_write_operator_case`
  - `_write_route_pair_swap_case`
  - `_write_synthetic_vrp`
  - `_run_solver`
  - `_artifact`

Then split the current tests as follows:

| New file | Source line ranges | Responsibility |
| --- | ---: | --- |
| `test_cvrp_solver_registry_runtime.py` | 187-385, 4584-4690, 4709-4880 | Registry operators, workspace-local solution coercion, portfolio scheduling through registry operators, invalid operator outputs, operator exceptions, path escape. |
| `test_cvrp_solver_policy_surfaces.py` | 386-514, 515-646, 4381-4583 | Search/construction/baseline/portfolio required fields, safe CVRP instance API, invalid construction/search/portfolio policy runtime failures. |
| `test_cvrp_solver_external_baseline.py` | 647-1043 | External VRP bridge, baseline-policy kwargs, ALNS/VNS policy override, ALNS/VNS audit finalization, formal-floor baseline budget policy. |
| `test_cvrp_algorithm_blueprint_runtime.py` | 515-533, 1060-1233 | Algorithm-blueprint contract interface, inactive defaults, active construction/local-search loop, invalid algorithm-blueprint output. |
| `test_cvrp_solver_design_runtime.py` | 1355-1587 | Solver-design required fields, preferred `baseline_algorithm.py`, legacy solver hook compatibility, solver algorithm exceptions, context baseline alias and objective comparison. |
| `test_cvrp_main_search_planning.py` | 1234-1354, 2904-3294, 3459-3530, 4331-4380 | Main-search defaults, required fields, plan normalization, route-pool auto-add, algorithm-body route-pool scope, explicit small route-pool, phase sequence, disabled route-pool role, invalid selected-surface plan. |
| `test_cvrp_main_search_runtime.py` | 1635-2624, 3352-3628, 4246-4330 | Active main-search loop, clamp evidence, coverage status, perturbation, phase-best vs recovery behavior, local cleanup after recombination, formal-like BDR budget. |
| `test_cvrp_route_pool.py` | 2635-2904, 2983-3458, 3530-3613 | Route-pool recombination, baseline sampling seeds and time budgets, exit reserve, residual completion, construction pool, route-pool telemetry. |
| `test_cvrp_route_pair.py` | 1951-2022, 3763-4010 | Route-pair swap acceptance/gating, route-pair candidate policy telemetry, route-pair policy default main-search activation. |
| `test_cvrp_destroy_repair.py` | 3809-3892, 4010-4245 | Bounded destroy/repair runtime telemetry, destroy/repair policy selectors, regret insertion ranking, fallback subset budgeting. |
| `test_cvrp_acceptance_restart.py` | 3628-3763 | Acceptance/restart policy recovery-only rejection and perturbation/restart plan application. |

The split should update monkeypatch targets to the new owner modules as each
runtime module moves. During transition, monkeypatching `cvrp_solver._...`
should still work through explicit facade bindings.

## Risks And Hidden Coupling Points

- `LocalSubprocessRunner` executes `<workspace>/solver.py` directly. Removing
  or renaming that file breaks all runtime protocol execution.
- `problem.yaml` and `problem-v1.yaml` still name `solver_path: solver.py`.
  The facade must remain the CLI entrypoint.
- `problem-v1.yaml`, `runtime/audit.py`, `protocol/experiment.py`, feedback
  tools, and tests depend on exact runtime field names such as
  `main_search_component_phase_delta_sum` and `solver_algorithm_active`.
- The final runtime merge in `_main` has override-sensitive ordering. Moving it
  to `cli.py` must preserve dict merge precedence.
- Tests and framework-adjacent units import private solver helpers. A clean
  split without transitional re-exports will create noisy, unrelated failures.
- Dynamic policy loading relies on package module names for
  `policies/baseline_modules/*` and evicts module trees to avoid stale branch
  imports. This is central to solver-design branch behavior.
- `_SolverAlgorithmContext.baseline()` still bridges to the external baseline
  for compatibility. Preferred `baseline_algorithm.py` candidates should not
  rely on it, but the runtime compatibility behavior must not silently change
  during modularization.
- `SCION_SELECTED_SURFACE=solver_design` changes runtime path selection by
  preferring `policies/baseline_algorithm.py`. That environment behavior is a
  protocol boundary, not a local implementation detail.
- `_main_search_construction_pool_solutions` is a private in-memory audit key
  consumed by route-pool recombination and removed before final audit output.
  Moving audit dictionaries across modules must preserve this hidden channel.
- External VRP baseline import uses generic `src.parser` and `src.solver`
  names. Keep sys.path and module cache interactions isolated and tested.
- Solution coercion accepts workspace-local `CvrpSolution` objects structurally.
  This protects branch workspaces where `models.py` is a different Python class
  object.
- `CvrpAdapter(object())` is used in helper validation paths. Replacing it with
  framework objects would be framework leakage and may create circular imports.
- Route-pool and bounded destroy/repair have time-budget and branch-call guards.
  Mechanical moves must not change reserve calculations or loop short-circuit
  points.
- New runtime modules must remain outside candidate-editable research surfaces.
  Otherwise modularization accidentally expands the research boundary from
  `policies/*` into solver internals.

## Recommended First Implementation Slice

Start with Phase 1 plus a very small compatibility facade update:

1. Add `solver_runtime/constants.py`, `solution_ops.py`, `timing.py`, and
   `policy_modules.py`.
2. Move only pure helpers and constants that do not call search loops.
3. Keep `solver.py` importing and re-exporting the moved private names
   explicitly.
4. Run the current aggregate tests before splitting tests.

This slice is low risk because it does not change solver sequencing, policy
schema, external baseline behavior, or selected solver-design runtime. It also
sets up stable dependencies for every later extraction.

Do not start by moving `_main` or `improve_with_main_search_strategy`; those
are the highest-coupling regions and should move only after their dependencies
are already separated.

## v3 Compliance Notes

- Problem-owned semantics: All proposed modules live under
  `scion/scion/problems/cvrp/`. Route, capacity, demand, objective comparison,
  feasibility, construction, local neighborhoods, ALNS/VNS bridge behavior,
  and solver-design context remain CVRP-owned.
- Framework boundary: The runtime modules should not import `scion.core`,
  `scion.contract`, `scion.proposal`, `scion.protocol`, or Decision-layer code.
  The solver emits problem-owned runtime evidence; framework layers consume it
  through declared schemas and protocol hooks.
- Protocol/decision separation: Modularization must not add promotion,
  validation, frozen-holdout, or threshold logic to CVRP runtime modules. The
  solver can record deterministic runtime facts, but Decision remains a
  framework layer that reads safe `DecisionFeatures`.
- No prompt-only rules: Any solver-design boundary rule needed at runtime should
  be represented by problem-owned executable checks, schemas, or audit fields,
  not only by comments or prompt text.
- No framework leakage: Generic Scion code should not gain CVRP route/demand,
  `_ALNSVNSSolver`, or baseline-module details as part of this split. If a
  framework layer needs CVRP behavior, it should call a CVRP adapter/provider
  hook.
- Original external VRP files remain untouched. The only allowed interaction is
  through the isolated CVRP `external_vrp.py` bridge that imports and calls
  them when data-root configuration requires it.
