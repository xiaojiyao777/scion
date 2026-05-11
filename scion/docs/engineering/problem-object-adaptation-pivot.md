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
and it does not yet replace the current surface list with a cleaner top-level
solver-design boundary.

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

The next engineering slice should finish the whole-problem CVRP adaptation
surface before more experiments:

1. Define the CVRP problem object Scion should see: instance structure,
   solution representation, route/move affordances, objective semantics, and
   solver lifecycle.
2. Decide the top-level research target. Prefer a broad problem-owned
   solver-design surface over more singleton component policies.
3. Keep rendering the object through the adapter so proposal agents reason from
   the problem and solver lifecycle, not from a menu of disconnected hooks.
4. Make runtime evidence summarize whole-solver behavior and phase-level
   movement, with component details as attribution rather than the primary
   research target.
5. Only then run a short diagnostic campaign. It should not force one narrow
   policy unless the purpose is specifically to validate a new adapter or
   contract boundary.

## Current CVRP Implication

Stop forced `destroy_repair_policy` and `route_pair_candidate_policy`
diagnostics for now. The former has been exhausted; the latter would continue
the same incremental-hook pattern. The next useful work is to redesign CVRP's
problem-object exposure and top-level solver-design surface.
