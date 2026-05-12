# Scion Agent Onboarding

*Last updated: 2026-05-12*

This is the first document an agent or developer should read before working on
Scion. Keep it short. Its job is to establish the project model, the
non-negotiable boundaries, and where to read next.

## Minimal Start

Always read only these first:

1. This document.
2. [v0.4 current state](status/current-state.md).

Then choose a task-specific reading profile from
[Reading Profiles](READING_PROFILES.md). Do not automatically read all design
docs, all engineering docs, historical status logs, raw experiment records, or
source trees.

## Project Definition

Scion is a governed autoresearch framework for combinatorial optimization
algorithms. LLMs propose research changes, but deterministic layers decide
whether evidence is strong enough to continue, validate, freeze, promote, or
abandon.

The core loop is:

```text
Creative Layer proposal
  -> Contract
  -> Verification
  -> Protocol
  -> Decision
  -> evidence/docs update
```

Key idea: proposal text and proposal-tool observations are tainted. They may
guide later proposals, but they do not directly decide promotions. Decision
reads deterministic `DecisionFeatures`, not raw LLM reasoning.

## Scion Logic

- Scion core owns generic governance: campaign lifecycle, proposal orchestration,
  Contract, Verification, Protocol, Decision, evidence refs, and lineage.
- Problem packages own domain semantics: objective, feasibility, solver hooks,
  allowed research surfaces, runtime audit field meanings, prompt rendering,
  and problem-owned tests.
- A research surface is the declared object the agent may modify or tune:
  operator, policy, config, portfolio, construction, acceptance/restart, or a
  solver-design boundary.
- Runtime evidence is part of the contract. Missing, empty, or invalid required
  fields fail closed when the selected surface declares them.
- Frozen/holdout detail is exposure-controlled. Proposal agents should receive
  bounded aggregate feedback, not raw validation or benchmark records.

## Current Version

Active version: v0.4 on `v0.4-dev`.

Current work centers on CVRP as the second real problem class after the
warehouse/surrogate path. The current direction is a problem-object adaptation
pivot: Scion should receive a coherent CVRP problem object and solver-design
boundary through the adapter, rather than being driven through one forced
singleton policy at a time. The first exposure slice renders the CVRP problem
object into proposal contexts and `context.read_problem`; the second slice
declares `solver_design` as the top-level CVRP research boundary. The current
implementation now makes that boundary a problem-object adaptation contract,
not just a shallow component policy. `main_search_plan` can declare
`problem_adaptation` with strategy family, instance-profile intent, phase
objective, component roles/order, and evidence targets. It must now also
declare `algorithm_body` when enabled, making the lifecycle explicit:
phase sequence, route-pool activation scope, route-pool customer threshold,
route-pool invocation limit, cleanup coupling, and adaptive component-budget
policy. The solver audits the computed runtime instance profile and algorithm
body, uses the adaptation to order components, set bounded destroy/repair
defaults, and apply per-component thresholds, and uses the algorithm body to
avoid hidden route-pool behavior on small formal instances unless the plan
explicitly asks for it. Proposal context, APS tools, target preview, and
output validation still keep `change_locus` on `solver_design`, while component
policies remain
implementation hooks or attribution evidence. The latest repair fixed the live
codegen contract for this path: lifecycle role targets and actual runtime
evidence targets are accepted, and proposal-only `novelty_signature` metadata
is no longer allowed in returned plan dictionaries. The current blocker is now
CVRP main-search execution quality under this explicit algorithm-body boundary:
screened candidates still need to prove phase-best objective movement.

Important current interpretation:

- `solver_design` is the top-level CVRP research object. It is backed by the
  existing `policies/main_search_strategy.py` execution hook, but the required
  research object is the whole CVRP solver lifecycle. A valid candidate should
  declare `problem_adaptation` and `algorithm_body`, not merely force one
  component recipe.
- `algorithm_body` is now required for enabled `solver_design` plans at the
  adapter/problem-spec contract. It declares the phase sequence and route-pool
  lifecycle controls: activation mode (`adaptive`, `always`,
  `medium_large_only`, or `disabled`), minimum customer threshold, max
  invocations, cleanup coupling, and adaptive component-budget policy.
- `problem_adaptation` carries strategy family, instance-profile intent, phase
  objective, component roles/order, and evidence targets. Runtime now records
  `main_search_problem_adaptation`, `main_search_instance_profile`,
  `main_search_component_order`, `main_search_component_roles`, and related
  evidence fields.
- `problem_adaptation.component_roles` may describe lifecycle role targets,
  not only improvement components: construction modes, repo-local baseline,
  strict-improvement acceptance, restart, perturbation, post-baseline operator
  toggle, and package-owned main-search components. `fallback_order` remains
  limited to package-owned improvement components.
- `problem_adaptation.evidence_targets` must use actual runtime audit fields
  such as `main_search_component_accepted`,
  `main_search_component_phase_delta_sum`,
  `main_search_component_phase_improvement_counts`,
  `main_search_restart_count`, `main_search_perturbation_count`, and
  `main_search_objective_delta_by_phase`.
- `novelty_signature` is hypothesis identity metadata only. Do not copy it
  into `main_search_plan()` or other generated policy/config return
  dictionaries unless a surface interface explicitly declares that key.
- `deep_components_selected` now means selected package-owned problem-object
  components across all main-search components, not just route-pair swap and
  bounded destroy/repair. This fixes the prior false runtime-contract failure
  where local components produced an empty deep-component audit.
- A failed `solver_design` implementation should be retried with a different
  solver lifecycle; it should not make APS fall back to isolated component
  policy goals.
- A zero-movement `solver_design` screening failure is also a candidate design
  failure, not permission to switch the top-level research goal to a component
  policy.
- Active `solver_design` boundary control is now live-validated: free-surface
  APS sessions stayed on `solver_design` after heavy Verification and
  zero/low-movement screening failures.
- Active-boundary tool guidance is now live-validated as an active problem
  boundary, not a fake forced-surface diagnostic.
- The APS Contract-preview budget repair is now live-validated: completed code
  sessions retained terminal Contract-preview pass/fail evidence under the
  64k observation budget instead of failing as `result_too_large`.
- `solver_design` semantic identity is now fail-closed: required
  `novelty_signature.selected_components` and
  `novelty_signature.deep_components_selected` must be non-empty arrays.
- Latest short diagnostics validate forced-surface control, APS feedback,
  perturbation-schedule runtime evidence, selected-surface audit, and real
  `destroy_repair_policy` selector semantics.
- They do not yet validate solver efficacy. The latest short diagnostic has
  formal route-pool phase-best movement, but median movement remains zero and
  the screening candidate still abandoned on win-rate threshold.
- Do not spend more rounds on shallow solver-design knob reshuffles or
  prompt-only exposure repairs. The latest useful signal came from a
  code-level whole-solution route-pool quality repair inside `solver_design`,
  not from another exposed singleton policy.
- The main-search execution-semantics repair was necessary but insufficient:
  bounded destroy/repair now ranks repair insertions globally, preserves
  fallback budget, honors the fallback toggle, and lets recovery-only accepted
  moves continue without consuming the phase-best accept limit, but live
  screening still showed zero phase-best movement.
- Current code-level repair adds a stronger package-owned whole-solution
  primitive: `route_pool_recombination`. It builds a route pool from complete
  CVRP solutions and recombines routes under the `solver_design` boundary, so
  APS can study the problem object rather than another forced singleton
  policy. Runtime auto-adds it to old route-pair plus bounded-destroy/repair
  plans unless explicitly disabled, and screening feedback now preserves its
  source-solution, sample-count, route-pool size, branch-call, and
  recombined-route telemetry.
- The latest route-pool quality diagnostic produced the first formal positive
  route-pool signal: 16/16 valid screening pairs, 0 timeouts, 2 wins, 14 ties,
  `main_search_route_pool_recombined_routes=12`, and
  `main_search_component_phase_delta_sum.route_pool_recombination=5.0`.
  The run still abandoned on win-rate/median movement and later agentic
  proposals hit Contract-preview failures, so this is not long-validation
  evidence.
- Continue on the current direction, but do not shrink the research object to
  route-pool itself. Route-pool is now useful evidence inside the
  `solver_design` lifecycle; the next useful slice is exposing and improving
  the whole CVRP algorithm body so Scion can reason about construction,
  baseline sampling, complete-solution recombination, local repair,
  acceptance, restart, and runtime tradeoff together.
- The current engineering slice implements that missing algorithm-body
  exposure: enabled solver-design codegen must return `algorithm_body`, runtime
  records `main_search_algorithm_body*` and route-pool lifecycle controls, and
  adaptive auto-added route-pool is scoped out on small formal `.vrp` instances
  unless the plan explicitly declares `route_pool_activation="always"`.
- The latest forced `destroy_repair_policy` enum-interface rerun validates
  selector clarity but exhausts that surface for the current solver-owned
  mechanism: valid candidates still produced zero accepted movement.
- Do not start another forced single-policy diagnostic, including
  `route_pair_candidate_policy`, while whole-lifecycle quality under the
  problem-object/top-level `solver_design` boundary is still sparse.
- Do not run long CVRP solver-quality validation until short diagnostics show
  repeated solver-design improvement, not only isolated wins on one screening
  candidate.

Read [current-state.md](status/current-state.md) for the exact latest status.

## Hard Rules

- Keep framework core problem-agnostic. CVRP, warehouse, and future problem
  semantics belong in problem packages/adapters unless a generic design
  contract changes.
- Do not read raw experiment artifacts in the main session by default. Use
  bounded experiment docs or delegate raw-artifact analysis when needed.
- Do not read source code by default for design or experiment interpretation.
  Use engineering maps first, then inspect only relevant paths for code tasks.
- Use the project Python:
  `/home/clawd/miniconda3/envs/claw/bin/python`.
- Update docs as part of the work. Code changes usually require engineering
  map updates; experiment analysis requires an experiment doc and current-state
  update when the project state changes.
- Stage and commit only the files that belong to the current slice.

## Task Workflow

For non-trivial work:

1. Define the slice: problem, surface, gate, evidence, files, and expected
   result.
2. Read the smallest matching profile from [Reading Profiles](READING_PROFILES.md).
3. Implement or analyze through the right boundary.
4. Verify with focused evidence first; broaden tests only when the risk
   justifies it.
5. Review Scion invariants: no problem semantics leaked into core, tainted data
   does not enter Decision, runtime failures fail closed where required.
6. Update docs and commit cleanly when asked to ship.

## Required Handoff

Before ending a task, state:

- what docs/source/raw artifacts were read;
- files changed;
- tests or validation commands run;
- docs updated;
- residual risks or next action;
- whether the working tree was committed or left dirty.
