# Problem Object Adaptation Pivot

*Date: 2026-05-11*

## Correction

The recent CVRP work drifted into exposing and force-testing one narrow policy
hook at a time. Those forced diagnostics were useful for validating governance
plumbing, selected-surface audit, and adapter-rendered interfaces, but they are
not the right optimization target.

The next direction is not another forced `*_policy` run. Scion should receive a
coherent problem object through the problem adapter, then reason about the
solver design at the problem level. Individual components can remain
implementation details, but they should not define the research objective.

## Target Model

For a new or existing optimization problem, the adapter should expose enough of
the problem object for Scion to form solver-level hypotheses:

- instance model: entities, structural fields, safe aggregate APIs, and input
  size terms;
- solution model: representation, feasibility constraints, canonicalization,
  and objective recomputation;
- objective policy: metric priorities, directions, tolerances, and tradeoff
  rules;
- solver lifecycle: construction, improvement, acceptance, repair/recovery,
  stopping, and where a research change can legally enter;
- move/design grammar: the problem-owned operations that can transform a
  solution, described as solver design affordances rather than forced local
  policy knobs;
- runtime evidence: whole-run and phase-level evidence that attributes solver
  behavior without requiring a separate forced surface for every component;
- contract/verification hooks: adapter-backed feasibility, consistency,
  objective, nondeterminism, and selected-solver evidence checks.

The core framework should still stay problem-agnostic. The richer problem object
belongs in `ProblemSpecV1`, adapter rendering/preview, and the problem package's
solver wrapper.

## Implemented First Slice

As of 2026-05-11, CVRP has an initial problem-object exposure slice:

- `CvrpAdapter.render_problem_object()` describes the instance model, solution
  model, objective policy, solver lifecycle, move/design grammar, and
  whole-solver runtime evidence.
- `ContextManager` adds that object to hypothesis, code, and fix contexts.
- `CreativeLayer` renders it as a `Problem Object` section before surface
  details and solver mechanics.
- `context.read_problem` returns the adapter-rendered object for APS sessions.
- CVRP prompt metadata no longer asks for one deep mechanism policy at a time
  as the default short-diagnostic path.

This is an exposure/adaptation slice only. It does not prove solver efficacy,
but it now feeds a cleaner top-level solver-design boundary instead of leaving
the whole component surface list as the default research menu.

## Implemented Solver-Design Boundary

The next slice declares `solver_design` as the CVRP top-level research surface:

- `ProblemSpecV1` supports the generic `solver_design` surface kind.
- CVRP `problem-v1.yaml` names `solver_design` as the problem-owned
  solver-design boundary with `policies/baseline_algorithm.py::solve(...)` as
  the stable branch-owned entrypoint.
- Adapter interface/preview logic treats `solver_design` as a whole-solver
  algorithm surface, with `policies/solver_algorithm.py` retained only as a
  compatibility hook.
- APS diagnosis and `context.list_surfaces` prioritize the solver-design
  problem-object boundary before component policies when it is declared.

This still does not prove solver efficacy. It prepares the next short
diagnostic so Scion targets the problem-level solver design instead of forcing
one component policy.

## Implemented Boundary-Control Repair

The first free solver-design diagnostic selected `solver_design`, but one heavy
Verification failure caused APS to treat the surface as globally blacklisted
and fall back to component policies. The repair keeps that failure scoped to
the candidate implementation:

- Heavy Verification failures under a declared `solver_design` surface mark the
  failed hypothesis `rejected`, not globally `blacklisted`.
- Hypothesis context renders solver-design boundary-control guidance after a
  pre-screening candidate failure.
- APS feedback tools tag `solver_design_pre_protocol_failure` and recommend
  retrying the problem-object boundary with a different lifecycle
  implementation.

The next short diagnostic validated that pre-screening failure no longer caused
immediate blacklisting, but it exposed a second boundary leak: after two valid
`solver_design` candidates reached screening and failed with zero movement,
APS selected `baseline_policy` as the next top-level `change_locus`, and the
completed code session carried a failed self-check. The deeper repair now makes
the boundary active rather than advisory:

- Hypothesis context narrows `operator_categories` and targetable files to the
  declared `solver_design` boundary when no forced surface is active.
- APS `context.list_surfaces` lists only the active problem-object boundary in
  that mode while retaining the total declared-surface count for audit.
- APS and normal proposal validation reject hypotheses whose `change_locus`
  moves to a component policy outside the active boundary.
- `proposal.target_permission_preview` reports the active-boundary rule, and
  APS fails closed when schema/target/Contract preview self-checks fail or are
  skipped in real sessions.
- Screening failures under `solver_design` produce
  `solver_design_screening_failure` diagnosis, but the recommended next action
  remains another problem-level solver-design attempt with component policies
  used only as implementation hooks or attribution evidence.

This is still a control-loop repair, not solver-efficacy evidence. It needs a
new short free-surface diagnostic before any longer solver-quality run.

## Implemented Solver-Design Module Granularity

The next design correction was research-object granularity. The current
`solver_design` path correctly lets Scion target the algorithm body, but the
patch protocol still asks the agent to return complete file contents. In
practice, a one-operator change to `policies/baseline_algorithm.py` causes the
code agent to regenerate the entire algorithm file.

The original `vrp/` implementation is a better structural guide. It separates
the CVRP algorithm into data/state, construction, ALNS destroy/repair,
adaptive weights, local-search/VNS, acceptance, and solver scheduling modules.
Scion should preserve the same conceptual split inside the branch-owned
controlled subject:

- stable entrypoint: `policies/baseline_algorithm.py::solve(...)`;
- branch-owned algorithm modules: construction, destroy, repair, local search,
  acceptance, scheduler/runtime allocation, and telemetry;
- fixed adapter boundary: parsing, feasibility, objective recomputation, seed
  handling, protocol splits, and promotion decisions stay outside the research
  modules.

This does not require exposing raw `vrp/` files or modifying the original
implementation. The controlled CVRP package should own its copy of the
algorithm subject, while Scion audits a full candidate workspace after module
changes. Within that solver-design package, the agent may add, delete, or
modify algorithm modules. `PatchProposal` can still use complete file contents,
but the file should be a focused algorithm module rather than the whole solver
body, and the candidate workspace must be validated through the stable
`solve(...)` entrypoint.

Implemented on 2026-05-15:

- the checked-in solver-design subject is split into
  `policies/baseline_modules/config.py`, `state.py`, `construction.py`,
  `destroy_repair.py`, `local_search.py`, `acceptance.py`, and
  `scheduler.py`;
- `policies/baseline_algorithm.py` is now a small stable entrypoint that
  imports the branch-owned module package and returns a Scion-normalized
  solution through `context.make_solution(...)`;
- `problem-v1.yaml` declares `policies/baseline_modules/*.py` as editable
  `solver_design` targets with create/delete/modify allowed, while
  `policies/baseline_modules/__init__.py` remains frozen;
- Contract C7 treats support-module interface checks as deferred to workspace
  smoke, because only the package entrypoint must define `solve(...)`;
- CVRP preview and `proposal.algorithm_smoke` can apply a module patch in a
  temporary workspace and validate it by running the stable
  `baseline_algorithm.py::solve(...)` entrypoint on the configured canary.

## Implemented Semantic-Identity Guidance Repair

The next repair tightened the solver-design identity contract:

- `solver_design` novelty requirements are carried into hypothesis context, APS
  tool guidance, schema preview, and final hypothesis prompts.
- `novelty_signature.selected_components` and
  `novelty_signature.deep_components_selected` must be non-empty arrays of
  component names.
- Missing, false, empty-string, empty-object, and empty-array identity values
  fail closed before completed code is accepted.
- APS active-boundary tool guidance now renders an active problem-boundary rule
  with `allowed_surface_ids=["solver_design"]`; it no longer mislabels the
  default boundary as a forced-surface diagnostic.

The 2026-05-12 short diagnostic validated those controls. Four persisted
hypotheses stayed on `solver_design`, carried non-empty semantic identity, and
tried distinct solver-lifecycle patterns. Three reached screening, but still
failed quality thresholds; the only nonzero win-rate signal was `0.125` with
`median_delta=0.0` and runtime regression. Main-search phase-best movement
remained zero.

## Implemented Problem-Adaptation Contract Repair

The next short experiment exposed a codegen/Contract mismatch rather than a
research-quality failure: generated `main_search_plan()` code copied
proposal-only `novelty_signature` into the returned plan, used lifecycle
targets in `problem_adaptation.component_roles`, and named real runtime audit
fields in `evidence_targets` that the previous whitelist rejected. The repair
keeps these concerns separated:

- `novelty_signature` is rendered to code generation as
  `hypothesis_metadata_novelty_signature` and must not be copied into returned
  policy/config dictionaries unless a surface explicitly declares it.
- `main_search_plan()` has an exact top-level key contract and rejects extra
  keys such as `novelty_signature`.
- `problem_adaptation.component_roles` accepts lifecycle role targets:
  construction modes, repo-local baseline, strict-improvement acceptance,
  restart, perturbation, post-baseline operator toggles, and package-owned
  main-search components.
- `problem_adaptation.evidence_targets` accepts the runtime audit fields the
  solver actually emits, including accepted current moves, phase-improvement
  counts, restart/perturbation counts, objective deltas by phase, and objective
  trace.

The follow-up validation reached Contract, Verification, and screening twice
with declared problem adaptation and `main_search_strategy_errors=0`. Both
screened candidates still had `win_rate=0.0`, `median_delta=0.0`, and zero
main-search phase-best movement. This validates the problem-adaptation
contract and confirms that the next bottleneck is CVRP main-search execution
semantics.

## Implemented Main-Search Execution-Semantics Repair

The next code slice targets package-owned CVRP execution rather than more
prompt exposure. The latest failed screening candidates showed many
main-search attempts but no phase-best movement: route-pair moves were mostly
recovery-only after perturbation, and bounded destroy/repair was dominated by
`repair_budget_exhausted`.

The repair changes the owned mechanism semantics:

- repair insertion candidates are ranked globally across feasible routes before
  the bounded budget is applied;
- fallback-enabled destroy/repair reaches small fallback subsets before the
  shifted/diverse variants consume the subset cap;
- large destroy subsets reserve repair budget for later smaller fallback
  subsets;
- `fallback_to_smaller_subsets=False` now really disables smaller fallback
  subsets;
- recovery-only accepted moves do not consume the phase-best accept limit and
  do not immediately stop the improvement loop.

This is code-validated by focused CVRP runtime tests, but the follow-up live
screening still produced zero main-search phase-best movement. The repair made
the existing components execute cleanly, but it did not make them strong
enough to beat the repo-local phase best.

## Implemented Route-Pool Recombination Repair

The next slice adds a package-owned whole-solution primitive instead of
another policy knob. `route_pool_recombination` belongs to the
`solver_design` main-search component set. It keeps the incumbent phase-best
routes, uses remaining formal-run time to collect short repo-local baseline
samples, builds a feasible route pool, and solves a bounded route-set
recombination problem over complete CVRP solution objects.

This changes the research object from "which small component policy should
Scion tune" to "how should the solver lifecycle combine complete CVRP
solutions under the problem constraints." Runtime evidence records source
solution count, route-pool sample count, route-pool size, branch calls,
recombined route count, and normal phase-best component deltas.

Validation so far:

- focused route-pool and main-search runtime tests pass;
- related CVRP adapter/proposal subset passes;
- full Scion tests pass with `1593 passed, 1 skipped`;
- local formal probes show nonzero route-pool phase-best movement on
  P-n101-k4;
- the telemetry short diagnostic validated route-pool execution and feedback:
  runtime auto-added/selected `route_pool_recombination`, screening metrics
  preserved source-solution count, pool size, branch calls, and recombined
  route count on 16/16 pairs;
- the follow-up quality/boundary diagnostic produced the first formal positive
  route-pool signal: 16/16 valid pairs, 0 timeouts, 2 wins, 14 ties,
  `main_search_route_pool_recombined_routes=12`, and
  `main_search_component_phase_delta_sum.route_pool_recombination=5.0`.

The current result validates direction, not readiness. Route-pool is now a
useful internal whole-solution mechanism, but treating route-pool itself as
the research object would repeat the same incremental-hook anti-pattern at a
larger scale. The object Scion should study is the CVRP solver lifecycle and
algorithm body: construction, repo-local baseline sampling, complete-solution
pooling, route-set recombination, local repair, acceptance, restart, and
runtime tradeoff as a single problem-owned design.

## Implemented Algorithm-Body Exposure Repair

The next repair makes that algorithm body an explicit part of the
`solver_design` contract instead of an implicit solver default:

- enabled `main_search_plan()` proposals must return `algorithm_body` at the
  adapter/problem-spec contract;
- `algorithm_body.phase_sequence` declares which lifecycle phases the design is
  studying: construction, baseline, global recombination, route-structure
  repair, local cleanup, perturbation, and restart;
- route-pool behavior is now lifecycle-controlled through
  `route_pool_activation`, `route_pool_min_customers`, and
  `route_pool_max_rounds`, plus explicit cleanup/adaptive-budget booleans;
- runtime audits record `main_search_algorithm_body`,
  `main_search_algorithm_body_source`, `main_search_route_pool_auto_added`,
  `main_search_route_pool_invocations`, `main_search_route_pool_activation`,
  `main_search_route_pool_min_customers`, and
  `main_search_route_pool_max_rounds`;
- the execution path uses the declared body: adaptive auto-added
  `route_pool_recombination` is skipped on small formal `.vrp` cases below the
  declared customer threshold, while explicit `always`, `medium_large_only`, or
  `disabled` activation remains available for hypotheses that want to study
  that scope directly.

This repair addresses the latest direction correction: Scion should study the
whole CVRP algorithm body, not merely discover which component hook is exposed.
It is code-validated but still needs a short free-surface experiment to test
whether the new contract changes generated solver-design behavior and runtime
quality.

## Anti-Pattern

Do not keep expanding the design space by repeatedly adding or forcing tiny
singleton policies such as:

- one destroy selector policy;
- one repair budget policy;
- one route-pair candidate ranking policy;
- one acceptance/restart knob policy.

That pattern optimizes what is easy to expose, not what is important for the
problem. It also burns experiment budget proving that isolated knobs do not
move a mature baseline.

## Remaining Slice

The next slice is experimental validation and solver-lifecycle quality, not
more boundary, identity, or prompt exposure control:

1. Keep `solver_design` as the top-level research target. Do not force a
   singleton component policy unless validating a new adapter or contract
   boundary.
2. Verify that generated `solver_design` candidates now declare and use
   `algorithm_body` rather than relying on hidden defaults or forcing one
   component.
3. Use route-pool evidence as one feedback channel inside the lifecycle:
   `sample_count`, recombined routes, accepted route-pool moves, and
   route-pool phase-best delta should explain when complete-solution
   recombination is helping.
4. Make runtime feedback steer APS away from simply increasing repo-local
   baseline time fraction when that creates isolated wins with runtime
   regression and no median movement.
5. Run another short free-surface diagnostic from this explicit algorithm-body
   contract before considering longer CVRP validation.

## Current CVRP Implication

Stop forced `destroy_repair_policy` and `route_pair_candidate_policy`
diagnostics for now. The former has been exhausted; the latter would continue
the same incremental-hook pattern. The active-boundary control loop now keeps
CVRP on the problem-object `solver_design` boundary after both pre-screening
and screening failures. Route-pool quality now has formal positive signal, so
the next useful work is to verify whether explicit algorithm-body control makes
the whole boundary produce real solver movement.
