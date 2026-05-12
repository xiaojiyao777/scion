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

The next engineering slice is solver-lifecycle quality, not more boundary
control:

1. Keep `solver_design` as the top-level research target. Do not force a
   singleton component policy unless validating a new adapter or contract
   boundary.
2. Diagnose why current/recovery accepted moves do not refresh phase best.
3. Improve bounded destroy/repair so it does not mostly exhaust repair budget
   without phase-level improvement.
4. Make runtime feedback steer APS away from simply increasing repo-local
   baseline time fraction when that creates isolated wins with runtime
   regression and no median movement.
5. Run another short free-surface diagnostic only after the repair should be
   able to produce nonzero main-search phase-best movement.

## Current CVRP Implication

Stop forced `destroy_repair_policy` and `route_pair_candidate_policy`
diagnostics for now. The former has been exhausted; the latter would continue
the same incremental-hook pattern. The active-boundary control loop now keeps
CVRP on the problem-object `solver_design` boundary after both pre-screening
and screening failures. The next useful work is to make that boundary produce
real solver movement.
