# CVRP Package Map

## Scope / Sources

Sources read: CVRP code/config under `scion/scion/problems/cvrp/` excluding raw instance contents under `data/` and `controlled/data/`; CVRP final evidence code under `scion/scion/evidence/cvrp_*`; checked-in CVRP formal/controlled config and manifests. Raw CVRPLIB benchmark files, run logs, and raw result CSVs were not read.

## Package Role

`scion/scion/problems/cvrp/` is a problem package. It owns CVRP semantics: route model, instance loading, solver wrapper, operator interface, search/construction/portfolio/main-search/algorithm-blueprint policy surfaces, controlled deep mechanism policy surfaces, objective recomputation, feasibility/consistency checks, and CVRP-specific final evidence builders.

Framework core should treat this package through `ProblemSpecV1`, `ProblemAdapter`, `Runner`, and objective metric specs.

## Adapter

`CvrpAdapter` in `scion/scion/problems/cvrp/adapter.py` implements `ProblemAdapter`.

Responsibilities:

- render CVRP problem summary for prompts;
- render a solver-level CVRP problem object for proposal contexts and APS
  `context.read_problem`;
- render solver mechanics, including baseline plus post-baseline operator loop;
- render operator interface and policy surface interface;
- load `.json` instances via `CvrpInstance.from_json()`;
- load `.vrp` instances via `cvrplib.py`;
- deserialize solver output into `SolverArtifact` with normalized `CvrpSolution`;
- check route/customer consistency;
- check capacity feasibility;
- recompute objective fields: `fleet_violation`, `total_distance`, and `routes`;
- expose no lower-bound estimate currently.

Adapter semantics are route-native. Routes use implicit-depot customer sequences, every customer must appear exactly once, route load must respect capacity, and objective is lexicographic: first `fleet_violation`, then `total_distance`.

## Models and CVRPLIB Parser

`models.py` defines:

- `CvrpNode`
- `CvrpInstance`
- `CvrpSolution`

`CvrpInstance` owns demand, distance, route load, and route distance calculations. It also carries optional `allowed_routes`, `bks`, and `bks_routes`.
For generated policy surfaces it exposes safe instance helpers:
`customer_ids`, `customer_count`, `demands`, `capacity`, and `distance`;
there is intentionally no `customers` alias.

`cvrplib.py` is the small parser owned by the CVRP boundary. It parses EUC_2D CVRPLIB `.vrp` files and optional `.sol` files, maps raw depot/customer ids into Scion's depot-first zero-based id space, and returns `CvrpInstance`. It is package code, not framework logic.

## Solver Wrapper

`solver.py` is the CVRP executable used by `LocalSubprocessRunner`. Its CLI contract is the generic Scion solver contract: instance path, seed, time limit, registry path, output path.

Solver flow:

1. Resolve instance path, including data-root-relative formal paths.
2. Load instance through `CvrpAdapter`.
3. Load `policies/solver_algorithm.py` first. If
   `solve(instance, rng, time_limit_sec, context)` returns a valid solution,
   the direct solver-design hook becomes the output path and the legacy
   baseline/lifecycle/operator layers are skipped.
4. If the direct solver hook is missing, inactive, or invalid, load
   `policies/main_search_strategy.py`,
   `policies/algorithm_blueprint.py`, `policies/search_policy.py`,
   `policies/baseline_policy.py`, `policies/construction_policy.py`,
   `policies/alns_vns_policy.py`, `policies/destroy_repair_policy.py`,
   `policies/route_pair_candidate_policy.py`, and
   `policies/acceptance_restart_policy.py` from the workspace when present,
   validating returns and recording runtime audit fields.
5. If the legacy `main_search_strategy.py` execution file returns an enabled
   valid `main_search_plan`, let it take over the older componentized CVRP
   main-search lifecycle: construction ensemble, repo-local baseline budget and
   sanitized baseline params, package-owned improvement loop, bounded
   acceptance/restart/perturbation knobs including explicit perturbation
   timing, and optional post-baseline registry-operator scheduling. Invalid
   enabled plans record `main_search_strategy_errors` and do not take over.
   If no main-search strategy is active but a deep mechanism policy surface is
   active (`destroy_repair_policy`, `route_pair_candidate_policy`, or
   `acceptance_restart_policy`), the solver activates a package-owned default
   main-search diagnostic plan so the selected mechanism surface can produce
   runtime evidence without also editing `main_search_strategy.py`.
6. If no main-search strategy is active and `algorithm_blueprint` returns an
   enabled valid plan, let it coordinate
   bounded construction ensemble, baseline time fraction, package-owned local
   search, restart knobs, and post-baseline registry-operator toggle/round
   limit. Invalid enabled plans record `algorithm_blueprint_errors` and do not
   take over.
7. Build a construction solution through either the bounded construction
   surface, the main-search construction ensemble, or the algorithm-blueprint
   construction ensemble, and use it as the JSON/synthetic fallback or
   required-baseline fallback.
8. Build baseline solution:
   - real `.vrp` formal runs can use repo-local `vrp/src` ALNS+VNS baseline when data root env is configured;
   - `baseline_policy` passes sanitized bounded ALNS+VNS kwargs into the
     repo-local baseline;
   - active `alns_vns_policy` overlays the same sanitized baseline kwargs and
     records ALNS/VNS component, segment, destroy-ratio, attempt, accepted,
     runtime, stop-reason, construction-start distance, returned baseline
     distance, baseline phase delta, and objective-delta telemetry;
   - active `solver_design` baseline params reuse the same sanitization path
     before passing kwargs into the repo-local baseline, and conservative
     no-op/clamp evidence is recorded as a non-empty JSON-safe runtime object;
   - smoke/synthetic/JSON paths use deterministic nearest-neighbor fallback.
8. Run the main-search improvement loop, when active, after baseline and before
   registry operators. The solver owns bounded primitives:
   `intra_route_2opt`, `inter_route_relocate`, `route_pair_swap`, and
   `bounded_destroy_repair`. Active `route_pair_candidate_policy`,
   `destroy_repair_policy`, and `acceptance_restart_policy` refine those owned
   primitives through bounded candidate ranking, destroy/repair subset and
   budget choices, recovery-only acceptance, restart triggers, and perturbation
   timing without allowing generated route-edit code to enter the solver. The
   main-search loop records selected,
   attempted, accepted, and skipped components, per-component skip reasons,
   best observed distance deltas, recovery-only accepted deltas/counts,
   phase-best deltas/counts, improvement counts, runtime, and destroy/repair
   removed/reinserted counts. It also records accepted-move delta sums,
   accepted best deltas, accepted positive counts, and an objective trace
   linking phase start objective, best objective, returned objective, phase
   delta, recovery-only delta, and accepted-but-zero-phase-delta diagnostics.
   `perturbation.schedule` may be `after_no_improvement` (legacy behavior),
   `before_first_round`, or `before_each_round`; the selected schedule is
   recorded as `main_search_perturbation_schedule`.
   It also emits a
   `main_search_component_coverage_status` summary and
   `main_search_deep_components_selected` so solver-level evidence can audit
   whether deep attribution hooks such as `route_pair_swap` and
   `bounded_destroy_repair` were selected and attempted without changing normal
   promotion semantics.
9. Run the algorithm-blueprint local-search phase, when active, after baseline
   and before registry operators. The solver owns the bounded primitives:
   `intra_route_2opt` and `inter_route_relocate`.
10. Load registry operators from workspace `registry.yaml`.
11. Load `policies/neighborhood_portfolio.py` from the workspace when present,
   validating returns and recording runtime audit fields.
12. Apply the portfolio surface to filter/sort bounded registry component
   families and enforce top-k, round, total-attempt, and per-component attempt
   limits.
13. Apply operators in portfolio-adjusted weight order inside a bounded
   post-baseline loop.
14. Accept an operator output only if it is valid, feasible, and lexicographically improves current objective.
15. Write JSON output with routes, feasible flag, objective, and runtime audit fields.

The solver treats exceptions, invalid outputs, infeasible outputs, invalid
policy/baseline-policy/portfolio/main-search/algorithm-blueprint returns, and
required-baseline failures as runtime audit failures. These are later promoted
to verification/evidence failures by `scion/scion/runtime/audit.py`.

## Operators and Registry

`operators/base.py` defines the CVRP operator interface:

`execute(self, solution: CvrpSolution, instance: CvrpInstance, rng: random.Random) -> CvrpSolution`

Operators are loaded from registry entries with name, file path, class name, and weight. The checked-in `registry.yaml` starts empty. Generated operators are expected under `operators/*.py`.

Operator outputs are structurally coerced to `CvrpSolution` when possible because generated code may import workspace-local `models.py`. Invalid structures fail closed through runtime audit.

## Policy Surfaces

`policies/search_policy.py` is a singleton policy research surface. Required functions:

- `baseline_time_fraction(instance, time_limit_sec)`
- `max_operator_rounds(instance, time_limit_sec)`
- `enable_post_baseline_operators(instance, time_limit_sec)`

The solver validates/clamps numeric policy returns and records policy errors as runtime audit failures. Policy functions must be deterministic and must not read external answers.

`problem-v1.yaml` declares this as a `policy` research surface with `modify` allowed and `create_new/remove` disallowed.

The adapter-rendered policy interfaces and `problem-v1.yaml` prompt guidance
for `search_policy`, `baseline_policy`, `construction_policy`,
`neighborhood_portfolio`, `solver_design`, `algorithm_blueprint`,
`alns_vns_policy`, `destroy_repair_policy`,
`route_pair_candidate_policy`, and `acceptance_restart_policy` explicitly
direct generated code to use
`instance.customer_ids`,
`instance.customer_count`, `instance.demands[customer_id]`,
`instance.capacity`, and `instance.distance(i, j)`, and to avoid
`instance.customers`. Adapter preview and runtime audit still fail reached uses
of the nonexistent `instance.customers` attribute.

`solver_design` is the current problem-owned CVRP solver-design research
surface. It is backed by `policies/solver_algorithm.py`. Required function:

- `solve(instance, rng, time_limit_sec, context)`

The default checked-in execution file returns `None` for champion stability,
but now includes an editable ALNS/VNS-style algorithm-body template. Active
candidates may implement construction, route-edit candidate generation, local
search, destroy/repair, recombination, perturbation, acceptance, and runtime
scheduling inside `solve(...)`. The adapter/solver remains authoritative for
objective recomputation, feasibility, parser behavior, seeds, protocol splits,
and Decision. The legacy `main_search_strategy` surface still exists for
regression coverage; it is not the preferred research object.

The model-facing interface and `problem-v1.yaml` require solver-design
hypotheses to populate semantic identity through fields such as
`algorithm_family`, `construction_strategy`, `improvement_strategy`,
`acceptance_strategy`, and `runtime_budget_strategy`. The
`novelty_signature` object is proposal metadata only; it must not be returned
from `solve(...)`.
`problem_adaptation.component_roles` can describe the whole lifecycle rather
than only selected improvement components. Accepted role targets include
construction modes, repo-local baseline/baseline params, strict-improvement
acceptance, restart, perturbation, post-baseline operator toggles, and the
package-owned main-search components. The solver preserves those roles in
`main_search_component_roles`, but only package-owned improvement components
participate in main-search scheduling and disabled-selected-component checks.
`problem_adaptation.fallback_order` remains limited to package-owned
improvement components. `problem_adaptation.evidence_targets` is checked
against the runtime audit fields the solver actually emits, including accepted
current moves, accepted positive counts, phase-improvement counts,
restart/perturbation counts, objective deltas by phase, and objective trace.
Unknown keys, missing
required keys for enabled plans, invalid baseline params, bad types,
non-finite values, unknown components, and out-of-range values increment
`main_search_strategy_errors`; invalid enabled plans do not take over the
solver lifecycle and selected-surface runtime audit fails closed.

The deep components are package-owned and audited. `route_pair_swap` ranks a
bounded set of route-pair/customer-swap candidates before applying `top_k`,
instead of relying on raw nested enumeration order. `bounded_destroy_repair`
uses policy-selected removal ranking (`worst_removal` or
`route_diverse_worst`) over bounded customer subsets and policy-selected repair
(`regret_2` or low-budget `cheapest`) with cheapest insertion candidates;
subset generation includes prefix, shifted, and route-diverse subsets so
controlled formal-like cases are less dependent on a single worst-removal
prefix. Its repair budget is split across pending customers instead of
allowing one customer to exhaust the whole `top_k` budget, and if a
multi-customer repair fails or produces no improvement it can spend remaining
budget on bounded smaller destroy subsets before giving up.
The current implementation ranks each customer's feasible insertion candidates
globally across routes before applying the bounded budget, instead of letting
earlier routes consume the budget. Fallback-enabled destroy/repair enumerates
prefix subsets for each fallback size before shifted/diverse variants, so
small 3/2/1-customer repairs are actually reached, and per-subset budgeting
reserves repair attempts for later smaller subsets.
When the current solution has been perturbed away from phase best, the
main-search loop probes the same component against both the current solution
and the phase-best baseline, then prefers a candidate that refreshes phase
best over a recovery-only current improvement. Recovery-only accepted moves do
not consume the phase-best accept limit and get a follow-up round from the
recovered current solution instead of stopping immediately. Runtime audit
records removed, reinserted, and repair-fallback counts, while skip reasons
distinguish budget exhaustion, infeasible insertion, below-threshold
candidates, and repairs that produced no improvement. Main-search audit
records per-component accepted delta totals/best deltas/positive counts,
recovery-only delta totals/best
deltas/counts, phase-best delta totals/best deltas/counts, and a phase
objective trace so proposal feedback can distinguish "component accepted
moves" from "current recovery" and "phase-level or final case benefit."
`route_pool_recombination` is the current whole-solution main-search
component. For formal `.vrp` runs it uses remaining time to collect short
repo-local baseline samples, keeps the incumbent phase-best routes, and solves
a bounded route-set recombination problem over the resulting pool. This gives
`solver_design` a package-owned way to recombine complete CVRP solution
objects instead of only tuning individual route-pair or destroy/repair knobs.
Runtime audit records source-solution count, route-pool size, branch calls,
and recombined route count. These fields are part of the `solver_design`
required-runtime contract, so screening metrics and APS feedback can
distinguish "route-pool was not exposed" from "route-pool built a pool but
found no accepted recombination."
Perturbation timing is an explicit surface dimension: the default
`after_no_improvement` schedule preserves legacy behavior, while
`before_first_round` and `before_each_round` let candidates implement a real
pre-improvement perturbation hypothesis instead of only describing it in
prose.
Main-search plans are now framed as solver-level CVRP designs. Deep component
coverage remains useful attribution evidence, but missing a particular
component is a diagnostic advisory rather than the research target itself. A
candidate should explain how construction, baseline budget, package-owned
components, restart/perturbation, and caps work together and which phase-best
objective and whole-solver runtime fields should move.
The latest short diagnostics validate that APS can keep this as the active
problem-object boundary, generate non-empty solver-design semantic identities,
carry lifecycle `problem_adaptation`, pass Contract preview, and reach
screening with `main_search_strategy_errors=0`. They do not validate solver
efficacy: screened candidates still have zero main-search phase-best movement.
The next engineering target is the package-owned execution semantics of the
main-search loop and primitives, not another exposure-only prompt repair.

`policies/alns_vns_policy.py` is a singleton deep mechanism research surface.
Required function:

- `alns_vns_plan(instance, time_limit_sec)`

The default checked-in policy is inactive. A valid enabled plan can select the
bounded ALNS/VNS component set (`alns`, `vns`), component weights, and the same
sanitized repo-local baseline parameters accepted by `baseline_policy`. The
solver overlays those params onto baseline kwargs and records surface load,
active/error status, normalized plan, components, weights, segment/destroy
schedules, attempts, accepted flag, construction-start distance, returned
baseline distance, objective deltas, phase delta sum, runtime, and stop reason.

`policies/destroy_repair_policy.py` is a singleton deep mechanism research
surface. Required function:

- `destroy_repair_plan(instance, time_limit_sec)`

The default checked-in policy is inactive. A valid enabled plan can choose from
bounded destroy selectors (`worst_removal`, `route_diverse_worst`), repair
selectors (`regret_2`, `cheapest`), subset strategy
(`prefix_shifted_route_diverse`, `single_worst`, `route_diverse`),
`max_destroy_customers`, per-customer repair budget, fallback-to-smaller-subsets
flag, and phase-best preference. The solver still owns removal and repair code,
but the selector fields now drive the bounded mechanism implementation instead
of only appearing in runtime audit. Runtime telemetry records subset,
removed/reinserted, budget, fallback, accepted, skip, delta, and runtime
fields.

The adapter-rendered interface for this surface lists the destroy selector,
repair selector, and subset-strategy enum sets separately. `single_worst` and
`route_diverse` are valid subset strategies, not valid `destroy_selectors`.

`policies/route_pair_candidate_policy.py` is a singleton deep mechanism
research surface. Required function:

- `route_pair_plan(instance, time_limit_sec)`

The default checked-in policy is inactive. A valid enabled plan can choose
route-pair scoring terms (`route_distance`, `removal_saving`, `load_gap`,
`distance_saving`), move families (`customer_swap`), and candidate limits
(`pair_cap`, `position_cap`). The solver still owns route-pair swap execution;
policy only controls bounded ranking and records generated/pruned candidates,
attempts, accepted counts, skip reasons, phase delta, and runtime.

`policies/acceptance_restart_policy.py` is a singleton deep mechanism research
surface. Required function:

- `acceptance_restart_plan(instance, time_limit_sec)`

The default checked-in policy is inactive. A valid enabled plan can set
`min_distance_improvement`, recovery-only policy (`allow`,
`reject_recovery_only`, `phase_best_preferred`), restart triggers, and
perturbation schedule/strength/count. This policy affects main-search
candidate acceptance and perturbation timing only; protocol Decision thresholds
and objective semantics remain unchanged.

`policies/baseline_policy.py` is a singleton policy research surface. Required
function:

- `baseline_params(instance, time_limit_sec)`

The solver accepts only known bounded repo-local baseline parameters:
`destroy_ratio`, `segment_length`, `reaction_factor`, `vns_max_no_improve`,
`use_vns`, `cw_threshold`, `vns_threshold`, `alns_threshold`, and
`max_destroy_customers`. Unknown keys, bad return types, non-finite values, and
out-of-range values increment `baseline_policy_errors`; sanitized defaults or
clamped values are the only values passed into `vrp/src`. The default
checked-in policy returns the existing `vrp/src` ALNS+VNS defaults.

`policies/construction_policy.py` is a singleton construction research surface.
Required functions:

- `construction_mode(instance, time_limit_sec)`
- `construction_bias(instance, time_limit_sec)`

The solver accepts only predeclared package-owned modes:
`nearest_neighbor`, `nearest_neighbor_demand_bias`, `demand_descending`, and
`sequential`. `construction_bias` is bounded to `[0.0, 1.0]`. Invalid modes,
bad return types, exceptions, and clamped bias values increment
`construction_errors` and are runtime audit failures. The default checked-in
policy returns `nearest_neighbor` and `0.0`, preserving the previous JSON and
synthetic construction semantics.

`policies/neighborhood_portfolio.py` is a singleton portfolio research surface.
Required functions:

- `enabled_components(instance, time_limit_sec)`
- `component_weights(instance, time_limit_sec)`
- `candidate_limits(instance, time_limit_sec)`

The solver accepts only predeclared component families: `route_local`,
`route_pair`, `ruin_recreate`, and `registry_operator`. Weight multipliers are
bounded to `[0.0, 5.0]`; round, top-k, total-attempt, and per-component attempt
limits are bounded integers. Unknown components, bad return types, non-finite
weights, and out-of-range limits increment `portfolio_errors` and are runtime
audit failures. The default checked-in policy enables all components at weight
`1.0` with high attempt/top-k caps, preserving previous post-baseline registry
operator behavior.

`policies/algorithm_blueprint.py` is a singleton top-level config research
surface. Required function:

- `algorithm_plan(instance, time_limit_sec)`

The default checked-in policy is inactive (`enabled=False`) and preserves the
existing solver lifecycle. An enabled candidate plan can only select bounded
package-owned components and knobs: construction methods from the declared
construction modes, baseline time fraction, post-baseline registry-operator
toggle and round cap, local-search components `intra_route_2opt` and
`inter_route_relocate`, and restart stagnation metadata. Unknown keys, missing
required keys for enabled plans, bad types, non-finite values, unknown
components, and out-of-range values increment `algorithm_blueprint_errors`;
invalid enabled plans do not take over the solver lifecycle.

## Problem Specs and Config

`problem-v1.yaml` is authoritative. It declares:

- editable files: `operators/*.py`, `policies/*.py`;
- frozen files: adapter/parser/models/solver/base/init files;
- import whitelist;
- operator interface signature: `execute(self, solution, instance, rng) -> CvrpSolution`;
- research surfaces: `route_local`, `route_pair`, `ruin_recreate`,
  `search_policy`, `baseline_policy`, `construction_policy`,
  `neighborhood_portfolio`, `algorithm_blueprint`, `solver_design`,
  `alns_vns_policy`, `destroy_repair_policy`,
  `route_pair_candidate_policy`, and `acceptance_restart_policy`;
- objective policy: lexicographic;
- objectives: `fleet_violation` priority 1, `total_distance` priority 2;
- family taxonomy and aliases;
- adapter import path.

`problem.yaml` is legacy CLI compatibility and should not be treated as the source of truth when `problem-v1.yaml` exists.

`protocol.yaml`, `split_manifest.yaml`, and `seed_ledger.yaml` provide smoke campaign settings. `controlled/` provides synthetic controlled campaign configs. `formal/` provides formal-readiness configs and manifests with data-root-relative case paths.

## Formal and Controlled Assets

`controlled/` contains smoke/controlled protocol, split, seed, budget, and manifest assets for small synthetic cases. Its raw `.vrp`/`.sol` data was not read for this map.

`formal/` contains:

- `protocol.yaml`, `split_manifest.yaml`, `seed_ledger.yaml`;
- `budgets.json`;
- `matrix.json`;
- `manifests/*.json`;
- README describing data-root expectations.

Formal paths are opaque strings such as `cvrplib/...`; runtime requires `SCION_PROBLEM_DATA_ROOT` to point at the repo-local `vrp` directory. BKS/gap/BKS route counts are final-report fields only. Promotion remains based on `fleet_violation` and `total_distance`.

## CVRP Evidence Modules

CVRP evidence helpers under `scion/scion/evidence/` are problem-specific, not campaign core:

- `cvrp_case_manifest.py`: builds fixed case manifests from typed CSV result rows; does not load instances or run solvers.
- `cvrp_final_evaluation.py`: runner-backed baseline-vs-candidate final evaluation using adapter checks.
- `cvrp_manifest_evaluation.py`: connects fixed manifests to final evaluation.
- `cvrp_package.py`: no-run package builder from CVRP result CSV artifacts.
- `final_quality.py`: generic final-quality package writer used by CVRP helpers.

These helpers feed final evidence refs and readiness summaries but do not make campaign promotion decisions.

## Runtime Audit Fields

CVRP solver runtime output includes baseline, baseline-policy, construction,
operator, portfolio, policy, main-search-strategy, algorithm-blueprint, and
deep mechanism policy audit fields.
`runtime/audit.py`
interprets:

- required baseline fallback/error as `baseline_runtime_error`;
- construction policy errors as `construction_runtime_error`;
- policy errors as `policy_runtime_error`;
- neighborhood portfolio errors as `portfolio_runtime_error`;
- operator exceptions/invalid outputs as `operator_runtime_error`.
- selected-surface required runtime field failures as
  `surface_runtime_contract_error` when a surface declares
  `evidence.required_runtime_fields` and verification receives that surface.

The `baseline_policy` surface declares required runtime fields covering
loaded/error status, normalized baseline params, destroy ratio, ALNS segment
length, adaptive reaction factor, VNS toggle/no-improvement limit, and max
destroyed customers. When `baseline_policy` is selected,
`ExperimentProtocol` preserves these required fields in candidate-side pair
metrics and campaign summaries through the generic selected-surface runtime
summary.

The `algorithm_blueprint` surface declares required runtime fields covering
load/active/error status, normalized plan, phases executed, construction
methods, baseline fraction, operator toggle/limit, local-search components,
rounds, attempts, accepted moves, restart knobs/count, phase deltas, phase
runtime, and stop reason. Selected-surface audit fails closed when
`algorithm_blueprint_errors` is positive or those fields are missing/empty.
When `algorithm_blueprint` is the selected surface, `ExperimentProtocol`
preserves these required `algorithm_*` fields in candidate-side pair metrics
and campaign summaries through the generic selected-surface runtime summary.

The `solver_design` surface declares required runtime fields covering
load/active/error status, normalized plan, phases executed, construction
methods, requested/effective baseline fraction and params, whether the formal
baseline quality guard and conservative baseline-param clamps were applied,
post-baseline registry toggle/limit,
improvement components, rounds/top-k, selected and attempted component lists,
component attempts/accepted/runtime, per-component skip reasons, best component
distance deltas, accepted local delta totals, recovery-only delta totals,
phase-best delta totals, accepted/recovery/phase-improvement counts, bounded
destroy/repair removed/reinserted counts and accept limit, global and
per-component acceptance thresholds, restart/perturbation knobs and counts,
phase objective deltas, phase runtime, elapsed runtime, whether the phase best
was returned, and stop reason.
The main-search improvement loop distinguishes component-local acceptance from
phase-best improvement: a move that improves the current perturbed solution but
does not refresh phase best is still audited as accepted, but it does not
reset stagnation or suppress bounded destroy/repair via the route-pair phase
gate. The phase-level audit fields
`main_search_component_phase_delta_sum`,
`main_search_component_phase_best_delta`, and
`main_search_component_phase_improvement_counts` expose that distinction to
proposal feedback without changing Decision inputs.
The recovery audit fields `main_search_component_recovery_delta_sum`,
`main_search_component_recovery_best_delta`, and
`main_search_component_recovery_counts` make accepted current-state recovery
explicit so APS does not treat all accepted deltas as phase-level
improvement.
`main_search_baseline_param_clamps` is always a non-empty JSON-safe evidence
object. In the no-clamp case it records `applied=false`,
`status=no_clamps`, `count=0`, and empty nested `fields`/`clamps`; when clamps
fire it records `applied=true`, `status=clamped`, a bounded field list, and
per-field requested/effective values such as `destroy_ratio` and
`max_destroy_customers`.
Selected-surface audit fails closed when
`main_search_strategy_errors` is positive or these fields are missing/empty.
When `solver_design` is the selected surface, `ExperimentProtocol`
preserves these required `main_search_*` fields through the generic
selected-surface runtime summary.

The deep mechanism surfaces declare required runtime fields for selected-surface
auditing:

- `alns_vns_policy`: load/active/error status, normalized plan, components,
  component weights, segment/destroy schedules, attempts, accepted count, phase
  delta sum, construction-start distance, returned baseline distance,
  objective deltas, runtime, and stop reason.
- `destroy_repair_policy`: load/active/error status, selectors, subset
  strategy, destroy/repair budgets, subset count, removed/reinserted counts,
  repair budget/fallback counters, accepted current/recovery/phase-best counts,
  phase delta, skip reasons, and runtime.
- `route_pair_candidate_policy`: load/active/error status, scoring terms, move
  families, candidate limits, generated/pruned candidates, attempts, accepted
  current/recovery/phase-best counts, phase delta, skip reasons, and runtime.
- `acceptance_restart_policy`: load/active/error status, normalized plan,
  acceptance threshold schedule, recovery-only policy, restart triggers/count,
  perturbation schedule/count, accepted current/recovery/phase-best counts,
  phase-best refresh count, phase delta, and runtime.

`ExperimentProtocol`, `VerificationGate`, and final evidence builders treat these as failed evidence rather than objective ties.
