# Scion Agent Onboarding

*Last updated: 2026-05-11*

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
singleton policy at a time. The first exposure slice now renders the CVRP
problem object into proposal contexts and `context.read_problem`; the second
slice declares `solver_design` as the top-level CVRP research boundary. The
latest repair makes solver-design candidate failures candidate-scoped instead
of globally blacklisting the problem-object boundary. The next step is a short
diagnostic that does not force a singleton component policy.

Important current interpretation:

- `solver_design` is the top-level CVRP research object. It is backed by the
  existing `policies/main_search_strategy.py` execution hook, but component
  policies are implementation details, not standalone research goals.
- A failed `solver_design` implementation should be retried with a different
  solver lifecycle; it should not make APS fall back to isolated component
  policy goals.
- Latest short diagnostics validate forced-surface control, APS feedback,
  perturbation-schedule runtime evidence, selected-surface audit, and real
  `destroy_repair_policy` selector semantics.
- They do not yet validate solver efficacy. Screened candidates still fail
  quality thresholds, and phase-best movement remains zero.
- The latest forced `destroy_repair_policy` enum-interface rerun validates
  selector clarity but exhausts that surface for the current solver-owned
  mechanism: valid candidates still produced zero accepted movement.
- Do not start another forced single-policy diagnostic, including
  `route_pair_candidate_policy`, while the problem-object/top-level
  solver-design adaptation is still being completed.
- Do not run long CVRP solver-quality validation until a short diagnostic shows
  nonzero phase-best improvement and screening-quality movement.

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
