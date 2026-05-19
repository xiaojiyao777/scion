# CVRP Adapter Modularization 2026-05-19

## Boundary Target

`CvrpAdapter` remains the public compatibility facade for the Scion
`ProblemAdapter` contract. CVRP semantics stay under `scion/problems/cvrp/`:
surface prompt text, policy schemas, synthetic preview behavior, solver output
normalization, solution consistency, feasibility, objective recomputation, and
problem-owned provider hooks.

Framework modules should continue to call the adapter facade. New CVRP adapter
behavior should land in a focused CVRP-owned module first, with facade methods
delegating only when public compatibility requires it.

## Phase 1 Slice

This slice is deliberately low risk and behavior preserving:

- Added `scion/problems/cvrp/surface_schema.py` for CVRP research-surface
  constants, allowed literals, numeric ranges, preview time limits, and safe
  policy instance API text.
- Added `scion/problems/cvrp/surface_rendering.py` for problem summary,
  problem-object prose, solver mechanics prose, research-surface interface
  prose, and operator interface prose.
- Added `scion/problems/cvrp/solution_checks.py` for solver output
  deserialization, route normalization, reported-objective extraction,
  solution consistency checks, feasibility checks, and objective recomputation.
- Kept `CvrpAdapter` methods and import path stable. Existing calls to
  `render_*`, `deserialize_solver_output`, `check_solution_consistency`,
  `check_feasibility`, and `recompute_objective` still go through the facade.
- Preserved transitional private helper imports from
  `scion.problems.cvrp.adapter` for `_normalize_route`,
  `_extract_reported_objective`, and `_as_solution`.

This removes surface prose and solution-check ownership from `adapter.py`
without changing solver runtime, Contract providers, proposal/context builders,
or CVRP solver modules.

## Still In Adapter

After phase 2, `adapter.py` keeps only facade responsibilities:

- public `ProblemAdapter` methods;
- problem-owned provider registration methods, including
  `solver_design_prompt_provider()` and `solver_design_smoke_provider()`;
- active research-surface exposure policy accessors;
- compatibility re-exports for old private adapter helper names;
- preview timeout monkeypatch compatibility before dispatching to the preview
  package.

The remaining adapter-adjacent debt is no longer concentrated in the facade:

- provider registration should eventually become a typed provider-set method
  instead of several optional facade methods;
- preview modules can be refined further if individual surfaces grow, but all
  preview files are currently below the preferred 800-line threshold;
- CVRP solver-design prompt/smoke/provider migration remains active outside
  this adapter file.

## Active Surface Contraction

The CVRP active research object is now explicitly the solver-design algorithm
package only:

- `CvrpAdapter.active_research_surface_names()` returns only
  `("solver_design",)`.
- `CvrpAdapter.active_research_surfaces()` filters the declared
  `problem-v1.yaml` surfaces down to `solver_design`.
- `route_local`, `route_pair`, `ruin_recreate`, `search_policy`,
  `construction_policy`, `baseline_policy`, `neighborhood_portfolio`,
  `algorithm_blueprint`, `main_search_strategy`, `alns_vns_policy`,
  `destroy_repair_policy`, `route_pair_candidate_policy`,
  `acceptance_restart_policy`, and the `solver_algorithm` compatibility name
  are marked legacy/test-only by `surface_policy.py`.
- Preview payloads now expose `active_research_surface`, `legacy_surface`, and
  `preview_scope`. Legacy previews still run for compatibility tests and
  forced diagnostics, but their scope is `legacy_compatibility`; they are not
  active hypothesis-selection targets.
- The existing hypothesis context path already constrains visible CVRP
  research surfaces to the solver-design boundary when no forced diagnostic
  surface is active. This slice does not modify `proposal/context`; it adds
  CVRP-owned policy and tests that lock the behavior.

The large `problem-v1.yaml` still declares legacy surfaces because deleting
those sections would invalidate current forced-diagnostic and regression tests.
Next cleanup should remove or archive those declarations after the tests that
exercise them are explicitly reclassified as legacy compatibility coverage.

## Phase 2 Slice

This slice moved the adapter preview responsibility as one complete domain:

- Added `scion/problems/cvrp/preview/dispatch.py` for surface preview dispatch.
- Added `preview/paths.py` and `preview/module_loading.py` for path-to-surface
  helpers and synthetic module loading.
- Added `preview/solver_design.py` for static solver-design AST/API checks:
  baseline-algorithm wrapper bans, scheduler entrypoint import checks,
  `context.nearest_neighbor()` API checks, and remaining-time unit checks.
- Added `preview/synthetic.py` for synthetic instances, preview timeout
  execution, `PreviewSolverAlgorithmContext`, preview objective comparison,
  and preview solution validation.
- Added `preview/solver_algorithm.py` for solver-algorithm synthetic execution
  preview.
- Added `preview/policies.py`, `preview/main_search.py`, and
  `preview/deep_policies.py` for policy-family validators.
- Kept `CvrpAdapter.preview_research_surface_patch(...)` as the public facade
  method. Existing tests that monkeypatch
  `scion.problems.cvrp.adapter._POLICY_PREVIEW_EXEC_TIMEOUT_SEC` still work:
  the facade syncs those compatibility constants into the preview package
  before delegating.
- Kept Kierkegaard's `solver_design_prompt_provider()` and
  `solver_design_smoke_provider()` registrations intact.

## Next Phase

Recommended next slices:

1. Introduce a typed provider-set method once generic provider protocols are
   stable, then make `CvrpAdapter` expose one provider bundle instead of
   optional one-off provider methods.
2. Move any future CVRP solver-design smoke implementation behind the
   problem-owned provider; do not put smoke semantics back in adapter.
3. Keep new preview behavior in the owning `preview/*` module, not in the
   facade.
4. If a single preview module grows above 800 lines, split by surface family
   rather than creating a new shared catch-all file.
5. Delete or archive legacy non-`solver_design` surface declarations from
   `problem-v1.yaml` after compatibility tests no longer depend on them.

## Verification Notes

Initial focused verification after this slice:

- `python -m compileall -q scion/scion/problems/cvrp/adapter.py scion/scion/problems/cvrp/surface_schema.py scion/scion/problems/cvrp/surface_rendering.py scion/scion/problems/cvrp/solution_checks.py`
- `python -m pytest scion/scion/tests/test_cvrp_adapter_modularization.py scion/scion/tests/test_cvrp_adapter_core.py scion/scion/tests/test_cvrp_adapter_solution_checks.py -q`
  passed with 29 tests.

Broader verification after this slice:

- `python -m compileall -q scion/scion/problems/cvrp scion/scion/tests`
- `python -m pytest scion/scion/tests/test_cvrp_adapter*.py scion/scion/tests/test_cvrp_cvrplib_adapter.py scion/scion/tests/test_problem_adapter.py -q`
  passed with 102 tests.
- `git diff --check`

A broader CVRP plus research-surface-context run initially passed with 217
tests during this slice. A later rerun in the shared dirty worktree failed with
211 passed / 6 failed after concurrent `proposal/engine.py` changes introduced
missing `_solver_design_code_rules_section` and
`_solver_design_hypothesis_guidance` names. That failure is outside this CVRP
adapter write scope and was not repaired here.

Post-slice line counts:

- After phase 1, `adapter.py`: 2464 lines, down from 3381.
- After phase 2, `adapter.py`: 213 lines, down from 2464.
- Largest new module after phase 2: `surface_rendering.py` at 612 lines.
- Largest preview module after phase 2: `preview/main_search.py` at 535 lines.

Phase 2 focused verification:

- `python -m compileall -q scion/scion/problems/cvrp/adapter.py scion/scion/problems/cvrp/preview`
- `python -m pytest scion/scion/tests/test_cvrp_adapter_policy_preview.py scion/scion/tests/test_cvrp_adapter_deep_policy_preview.py scion/scion/tests/test_cvrp_adapter_main_search_preview.py -q`
  passed with 19 tests.
- `python -m pytest scion/scion/tests/test_cvrp_adapter*.py scion/scion/tests/test_cvrp_cvrplib_adapter.py scion/scion/tests/test_problem_adapter.py scion/scion/tests/test_contract_solver_design_provider.py scion/scion/tests/unit/test_cvrp_solver_design_provider.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py -q`
  passed with 122 tests.
- `python -m pytest scion/scion/tests/test_cvrp_*.py scion/scion/tests/test_problem_adapter.py scion/scion/tests/unit/test_cvrp_solver_design_provider.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py -q`
  passed with 227 tests.
- `git diff --check`

Active-surface contraction verification:

- `python -m pytest scion/scion/tests/test_cvrp_active_surface_exposure.py scion/scion/tests/test_cvrp_adapter_modularization.py -q`
  passed with 8 tests.
