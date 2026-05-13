# Scion Agent Onboarding

*Last updated: 2026-05-13*

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
warehouse/surrogate path. The current direction is no longer incremental
component exposure. `solver_design` is now the CVRP problem-object boundary
for the algorithm itself, backed by `policies/solver_algorithm.py`.
Candidates implement `solve(instance, rng, time_limit_sec, context)` and may
change construction, improvement, destroy/repair, recombination, acceptance,
restart/perturbation, and runtime scheduling inside that algorithm body.
The adapter/solver remains authoritative for parsing, feasibility, objective
recomputation, seeds, protocol splits, time limits, and Decision rules.

The older `policies/main_search_strategy.py` lifecycle table remains as a
legacy `main_search_strategy` config surface for regression coverage and
compatibility. It is not the preferred research object. Do not route new CVRP
optimization work through forced component-policy or lifecycle-table
diagnostics unless explicitly debugging that legacy surface.

Important current interpretation:

- `solver_design` targets `policies/solver_algorithm.py` and requires
  `solve(instance, rng, time_limit_sec, context)`. Returning `None` keeps the
  checked-in champion on the stable baseline path; an active candidate must
  return a feasible `CvrpSolution`, a routes object, or `{"routes": ...}`.
- The allowed algorithm API is explicit: use `instance.depot`,
  `instance.customer_ids`, `instance.customer_count`, `instance.demands`,
  `instance.capacity`, `instance.distance`, `instance.route_load`,
  `instance.route_distance`, and `context` helpers such as
  `nearest_neighbor`, `baseline`, `make_solution`, `objective`,
  `objective_key`, `is_better`, `is_valid`, `remaining_time`, `elapsed_ms`,
  `record_phase`, `record_iteration`, `record_move`, and `set_stop_reason`.
  `context.baseline` accepts an optional seed solution
  and either `time_budget_sec` or the compatibility alias `time_limit_sec`.
  `context.objective` is still a mapping, but now also compares
  lexicographically as `(fleet_violation, total_distance)`.
  The `time` module is whitelisted for monotonic timing; use context time
  helpers for budget decisions and never add sleeps.
- The boundary is fixed. Candidates may change the algorithm, but must not
  change objective semantics, capacity/fleet constraints, parser behavior,
  benchmark data, protocol splits, seeds, Decision thresholds, or solver/
  adapter internals.
- Runtime evidence for this boundary is `solver_algorithm_*`, including
  loaded/active/errors, elapsed time, phase runtime, solution validity,
  route count, objective, total distance, fleet violation, search iterations,
  move attempts, accepted moves, phase delta telemetry, and stop reason.
- `novelty_signature` for `solver_design` now describes algorithm identity:
  `algorithm_family`, `construction_strategy`, `improvement_strategy`,
  `acceptance_strategy`, and `runtime_budget_strategy`, alongside
  `predicted_direction` and `target_objectives`.
- A failed `solver_design` implementation should be retried with a different
  full-algorithm idea. A zero-movement screening failure is a candidate design
  failure, not permission to switch the top-level research goal to an isolated
  component policy.
- Active `solver_design` boundary control is now live-validated: free-surface
  APS sessions stayed on `solver_design` after heavy Verification and
  zero/low-movement screening failures.
- The first direct `solver_algorithm` launch also stayed on `solver_design`,
  but hit pre-evaluation framework friction: generated full-algorithm code
  used natural bounded `while` loops, `time` for timing, baseline seed/time
  aliases, and direct objective comparisons. Those are now supported without
  weakening the fixed objective/constraint boundary.
- Active-boundary tool guidance is now live-validated as an active problem
  boundary, not a fake forced-surface diagnostic.
- The APS Contract-preview budget repair is now live-validated: completed code
  sessions retained terminal Contract-preview pass/fail evidence under the
  64k observation budget instead of failing as `result_too_large`.
- `solver_design` semantic identity is now fail-closed on declared algorithm
  identity fields. Free-text rationale is not novelty identity.
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
- The current adapter repair goes deeper than prompt exposure: the checked-in
  `policies/solver_algorithm.py` remains inactive by default for champion
  stability, but it now carries an editable ALNS/VNS-style full-algorithm
  template. New candidates should materially rework or replace that algorithm
  body. A candidate that only wraps `context.baseline(...)`, changes baseline
  budget/params, or adds a tiny post-baseline polish is a design failure.
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
- The previous algorithm-body/lifecycle diagnostics showed a small positive
  route-pool signal but also proved the componentized lifecycle table was the
  wrong research object: candidates were still optimizing exposed knobs rather
  than studying the whole algorithm. The current engineering slice replaces
  that with a direct full-algorithm hook while keeping Scion's governance and
  objective/constraint boundaries intact.
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
