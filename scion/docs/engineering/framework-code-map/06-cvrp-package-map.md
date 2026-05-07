# CVRP Package Map

## Scope / Sources

Sources read: CVRP code/config under `scion/scion/problems/cvrp/` excluding raw instance contents under `data/` and `controlled/data/`; CVRP final evidence code under `scion/scion/evidence/cvrp_*`; checked-in CVRP formal/controlled config and manifests. Raw CVRPLIB benchmark files, run logs, and raw result CSVs were not read.

## Package Role

`scion/scion/problems/cvrp/` is a problem package. It owns CVRP semantics: route model, instance loading, solver wrapper, operator interface, search/construction/portfolio/algorithm-blueprint policy surfaces, objective recomputation, feasibility/consistency checks, and CVRP-specific final evidence builders.

Framework core should treat this package through `ProblemSpecV1`, `ProblemAdapter`, `Runner`, and objective metric specs.

## Adapter

`CvrpAdapter` in `scion/scion/problems/cvrp/adapter.py` implements `ProblemAdapter`.

Responsibilities:

- render CVRP problem summary for prompts;
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
3. Load `policies/algorithm_blueprint.py`, `policies/search_policy.py`, and
   `policies/construction_policy.py` from the workspace when present,
   validating returns and recording runtime audit fields.
4. If `algorithm_blueprint` returns an enabled valid plan, let it coordinate
   bounded construction ensemble, baseline time fraction, package-owned local
   search, restart knobs, and post-baseline registry-operator toggle/round
   limit. Invalid enabled plans record `algorithm_blueprint_errors` and do not
   take over.
5. Build a construction solution through either the bounded construction
   surface or the algorithm-blueprint construction ensemble, and use it as the
   JSON/synthetic fallback or required-baseline fallback.
6. Build baseline solution:
   - real `.vrp` formal runs can use repo-local `vrp/src` ALNS+VNS baseline when data root env is configured;
   - smoke/synthetic/JSON paths use deterministic nearest-neighbor fallback.
7. Run the algorithm-blueprint local-search phase, when active, after baseline
   and before registry operators. The solver owns the bounded primitives:
   `intra_route_2opt` and `inter_route_relocate`.
8. Load registry operators from workspace `registry.yaml`.
9. Load `policies/neighborhood_portfolio.py` from the workspace when present,
   validating returns and recording runtime audit fields.
10. Apply the portfolio surface to filter/sort bounded registry component
   families and enforce top-k, round, total-attempt, and per-component attempt
   limits.
11. Apply operators in portfolio-adjusted weight order inside a bounded
   post-baseline loop.
12. Accept an operator output only if it is valid, feasible, and lexicographically improves current objective.
13. Write JSON output with routes, feasible flag, objective, and runtime audit fields.

The solver treats exceptions, invalid outputs, infeasible outputs, invalid
policy/portfolio/algorithm-blueprint returns, and required-baseline failures as
runtime audit failures. These are later promoted to verification/evidence
failures by `scion/scion/runtime/audit.py`.

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
for `search_policy`, `construction_policy`, `neighborhood_portfolio`, and
`algorithm_blueprint` explicitly direct generated code to use
`instance.customer_ids`,
`instance.customer_count`, `instance.demands[customer_id]`,
`instance.capacity`, and `instance.distance(i, j)`, and to avoid
`instance.customers`. Adapter preview and runtime audit still fail reached uses
of the nonexistent `instance.customers` attribute.

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
  `search_policy`, `construction_policy`, `neighborhood_portfolio`,
  `algorithm_blueprint`;
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

CVRP solver runtime output includes baseline, construction, operator,
portfolio, policy, and algorithm-blueprint audit fields. `runtime/audit.py`
interprets:

- required baseline fallback/error as `baseline_runtime_error`;
- construction policy errors as `construction_runtime_error`;
- policy errors as `policy_runtime_error`;
- neighborhood portfolio errors as `portfolio_runtime_error`;
- operator exceptions/invalid outputs as `operator_runtime_error`.
- selected-surface required runtime field failures as
  `surface_runtime_contract_error` when a surface declares
  `evidence.required_runtime_fields` and verification receives that surface.

The `algorithm_blueprint` surface declares required runtime fields covering
load/active/error status, normalized plan, phases executed, construction
methods, baseline fraction, operator toggle/limit, local-search components,
rounds, attempts, accepted moves, restart knobs/count, phase deltas, phase
runtime, and stop reason. Selected-surface audit fails closed when
`algorithm_blueprint_errors` is positive or those fields are missing/empty.

`ExperimentProtocol`, `VerificationGate`, and final evidence builders treat these as failed evidence rather than objective ties.
