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
  solver-design boundary while keeping `policies/main_search_strategy.py` and
  `main_search_plan()` as the execution hook.
- Adapter interface/preview logic treats `solver_design` as the
  main-search-plan surface.
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

The next engineering slice should validate the active-boundary whole-problem
CVRP adaptation surface with a short experiment:

1. Define the CVRP problem object Scion should see: instance structure,
   solution representation, route/move affordances, objective semantics, and
   solver lifecycle.
2. Use `solver_design` as the top-level research target. Do not force a
   singleton component policy.
3. Keep rendering the object through the adapter so proposal agents reason from
   the problem and solver lifecycle, not from a menu of disconnected hooks.
4. Make runtime evidence summarize whole-solver behavior and phase-level
   movement, with component details as attribution rather than the primary
   research target.
5. Run a short free-surface diagnostic. It should not force one narrow policy
   unless the purpose is specifically to validate a new adapter or contract
   boundary. If APS tries to select a component policy as the top-level
   `change_locus`, the proposal should fail closed before code evaluation.

## Current CVRP Implication

Stop forced `destroy_repair_policy` and `route_pair_candidate_policy`
diagnostics for now. The former has been exhausted; the latter would continue
the same incremental-hook pattern. The next useful work is to validate that
the active-boundary control loop keeps CVRP on the problem-object
`solver_design` boundary after both pre-screening and screening failures.
