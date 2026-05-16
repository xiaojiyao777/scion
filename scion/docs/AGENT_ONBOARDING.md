# Scion Agent Onboarding

*Last updated: 2026-05-16*

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

Scion's job is boundary control, protocol control, auditability, and
traceability. The research core should still be a real agent doing algorithmic
research: it must be able to inspect the declared problem object, allowed
history, branch state, memory, and screening/runtime feedback inside Scion's
exposure policy. Do not turn Scion into prompt-only field exposure or a set of
forced component knobs.

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
for the algorithm itself, backed primarily by
`policies/baseline_algorithm.py` plus focused modules under
`policies/baseline_modules/`.
Candidates keep the stable `solve(instance, rng, time_limit_sec, context)`
entrypoint and may add, delete, or modify branch-owned modules for
construction, improvement, destroy/repair, recombination, acceptance,
restart/perturbation, telemetry, and runtime scheduling.
For multi-file solver-design edits, the primary patch path must match the
approved `target_file`; integration edits to the entrypoint, scheduler, or
sibling modules belong in `additional_changes`. New helper functions must be
called from the branch algorithm path in the same candidate patch. Scion should
reject inert helper drops before official screening.
The adapter/solver remains authoritative for parsing, feasibility, objective
recomputation, seeds, protocol splits, time limits, and Decision rules.
`policies/solver_algorithm.py` remains only as an older compatibility hook.

The older `policies/main_search_strategy.py` lifecycle table remains as a
legacy `main_search_strategy` config surface for regression coverage and
compatibility. It is not the preferred research object. Do not route new CVRP
optimization work through forced component-policy or lifecycle-table
diagnostics unless explicitly debugging that legacy surface.

Important current interpretation:

- `solver_design` targets `policies/baseline_algorithm.py` first, focused
  support modules under `policies/baseline_modules/*.py`, and
  `policies/solver_algorithm.py` only for compatibility. It requires the
  stable entrypoint
  `solve(instance, rng, time_limit_sec, context)`. When `solver_design` is
  selected, the subprocess runs the branch copy of
  `policies/baseline_algorithm.py`, which imports the branch-owned module
  package as the algorithm under research. Returning `None` is only a
  compatibility behavior for inactive hooks; a real solver-design candidate
  must return a feasible `CvrpSolution`, a routes object, or `{"routes": ...}`.
- The allowed algorithm API is explicit: use `instance.depot`,
  `instance.customer_ids`, `instance.customer_count`, `instance.demands`,
  `instance.capacity`, `instance.distance`, `instance.route_load`,
  `instance.route_distance`, and `context` helpers such as
  `nearest_neighbor`, `make_solution`, `objective`,
  `objective_key`, `is_better`, `is_valid`, `remaining_time`, `elapsed_ms`,
  `record_phase`, `record_iteration`, `record_move`, and `set_stop_reason`.
  `nearest_neighbor(...)` returns a `CvrpSolution`; use it directly as a
  candidate solution. `make_solution(...)` accepts route iterables and is
  idempotent for an existing solution object.
  `context.baseline` remains available only for the older compatibility hook;
  preferred `baseline_algorithm.py` candidates must study and modify the
  controlled algorithm body instead of calling `context.baseline`.
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
  move attempts, accepted moves, improving moves, neutral accepted moves,
  phase delta telemetry, and stop reason. `accepted_moves` is search activity,
  not proof of objective improvement.
- Runtime is an optimization signal under protocol control. A candidate that
  ties the lexicographic objective, has complete runtime evidence, has no
  runtime failures, and meets `runtime.tie_speedup_ratio` can progress through
  screening/validation/frozen with `*_PASS_RUNTIME_TIE_IMPROVEMENT`; it still
  cannot bypass the three-layer protocol.
- `context.remaining_time()` returns seconds. Use
  `context.remaining_time_ms()` for millisecond comparisons; Contract preview
  rejects preferred `baseline_algorithm.py` patches that compare seconds to
  millisecond-derived variables.
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
- The current adapter repair goes deeper than prompt exposure:
  `policies/baseline_algorithm.py` is the stable entrypoint for a
  branch-owned ALNS/VNS-style solver-design package. New candidates should
  materially rework the branch-owned modules under
  `policies/baseline_modules/` or, when needed, the entrypoint itself. A
  candidate that calls `context.baseline(...)` from this preferred target,
  changes only baseline budget/params, or adds a tiny post-baseline polish is
  a design failure.
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
- The latest direct full-solver short run validated the boundary but exposed a
  deeper APS issue: hypothesis/planning used proposal tools, while code
  generation was still a single static `generate_patch` call. Three screened
  candidates were valid but failed to beat the repo-local ALNS+VNS champion,
  and the next distinct population/recombination code attempt timed out on a
  large static prompt. This is both a framework interaction problem and an
  algorithm-quality problem.
- APS now has a code-phase tool loop after ContractGate-approved hypotheses.
  Code phase may use exposure-controlled reads for the full selected surface,
  problem/objective context, branch state, memory, and screening/runtime
  feedback before emitting the final `PatchProposal`. A failed Contract preview
  can be fed back into one bounded regeneration attempt. The proposal agent
  still cannot write workspaces, read validation/frozen raw metrics, or change
  objective/constraint semantics.
- Code phase also runs `proposal.algorithm_smoke` after a static Contract
  preview passes. This is tainted, non-promotional debug evidence. For
  approved `solver_design` patches to `policies/baseline_algorithm.py`,
  `policies/solver_algorithm.py`, or `policies/baseline_modules/*.py`, the
  smoke applies the patch in a temporary workspace and runs the configured
  canary case through the stable solver-design entrypoint before official
  evaluation. Its only purpose is debugging/repair; promotion evidence still
  comes exclusively from Contract, Verification, Protocol, and Decision.
- C9c complexity preview now recognizes a local helper such as
  `while within_budget():` only when that helper's return expression directly
  references runtime guards like `context.remaining_time()` or
  `context.elapsed_ms()`. True unbounded `while` loops and unbounded
  improvement-flag loops still fail closed. This is needed for complete
  algorithm-body work, where budget checks are often factored into helper
  functions.
- The latest 5-round exploratory `solver_design` run exposed a preview-time
  hang after successful code generation. Treat this as a boundary-control
  issue, not a reason to return to componentized policy exposure.
- Current preview repair: unbounded boolean-flag `while` loops fail C9c unless
  explicitly bounded, while route-construction `while True` loops are allowed
  only when they have a visible counter-bound break or directly shrink a finite
  collection on each non-break iteration. CVRP synthetic preview times out
  `solve(...)`, and APS turns a hung `proposal.contract_preview` into a
  controlled tool error. Run a 1-2 round smoke before any longer CVRP
  solver-quality validation.
- Latest C9c/smoke boundary repair: C9c now also accepts explicit bounded
  collection-size loops such as `while len(removed) < q` when the collection is
  visibly grown toward the bound and the bound is either directly bounded or
  assigned from `min(...)`/`max(...)` earlier in the same block. It still rejects
  true unbounded improvement-flag loops such as `while improved:`. Algorithm
  smoke also makes copied temporary smoke-workspace files writable before
  applying a patch, because champion snapshots are intentionally read-only.
- Research-object granularity repair: `PatchProposal` still carries complete
  file contents, but `solver_design` no longer forces every change through one
  monolithic `baseline_algorithm.py`. The branch-owned algorithm subject is
  split into controlled modules under `policies/baseline_modules/`, while
  `baseline_algorithm.py::solve(...)` stays the stable entrypoint. The agent
  may add, delete, or modify modules inside that declared solver-design package;
  `context.read_surface` returns bounded support-module previews so hypothesis
  and code phases can inspect the actual algorithm internals, not only the
  tiny entrypoint. Scion's hard boundary remains the fixed objective, constraints,
  adapter-owned parsing/feasibility/objective recomputation, seeds, protocol
  splits, and promotion.
- The preview-repair smoke itself did not reach preview: both rounds failed at
  final `generate_patch` after three provider timeouts. The important finding
  was duplicated code-phase context, not solver quality: the target file was
  present in `Target File` and again inside full surface-read observations,
  code phase repeated selected-surface reads, and planner sanitization turned
  `feedback.query_holdout_summary` into an empty model-facing tool name.
- Current prompt/tool-loop repair: code generation receives compact
  observation payloads that omit duplicated `content_preview` code, code-phase
  agentic context has a tighter cap, the code-phase planner stops after a
  successful full selected-surface read, holdout summary is filtered from
  model-facing planner specs while remaining callable directly, and timeout
  retries ask for one compact bounded algorithm body.
- A compact-prompt smoke from commit `7f7ef04` reached Contract,
  Verification, and screening in round 2, but round 1 still timed out at final
  `generate_patch`. Current repair is therefore stricter: final code prompts
  keep only code-relevant feedback plus the latest full selected-surface read
  metadata, and separately cap solver-design problem object, mechanics,
  interface, hypothesis, observation, and diagnosis text.
- A follow-up no-op-feedback smoke from commit `a653388` still did not reach
  Contract preview: both rounds timed out at final `generate_patch`. This is
  now treated as APS code-scope control, not missing problem exposure. Code
  phase reached the full `solver_design` target; the remaining failure was
  broad one-shot hybrid baseline/ILS/destroy-repair implementation scope.
- Current framework repair: solver-design code prompts default to a compact
  whole-algorithm body with one construction or seeding path plus one bounded
  improvement/search loop, allow the replacement file to be much shorter than
  the inactive template, and perform one in-session compact semantic retry
  after final `generate_patch` timeout.
- The latest 2-round code-scope smoke passed the first gate: final
  `generate_patch` returned in all three code traces, and round 1 reached
  Contract, Verification, and screening. It also exposed the next control
  issue: screening/runtime feedback consumed nearly all of the 64k APS
  observation budget, so round 2 could not retain terminal Contract-preview
  evidence and failed with `result_too_large`.
- Current APS repair compacts screening/runtime feedback before charging it
  to session observation budget, keeps self-check observation reserve through
  code phase, skips late feedback pulls when that reserve is at risk, and
  reuses successful same-session feedback instead of re-querying it.
- Current solver-design scope is stricter: one construction/seeding path, one
  bounded improvement loop, no more than two move families, and a hard target
  around 180 lines/six helpers for a generated target module. This still means
  algorithm code that participates in the branch-owned solver-design package,
  not a component knob or baseline-only wrapper.
- The latest Sonnet 1-round smoke validated the first gate: candidates target
  and modify `baseline_algorithm.py` as the algorithm body, pass Contract plus
  algorithm smoke, pass Verification, and run 16/16 formal screening pairs with
  required `solver_algorithm_*` telemetry. Solver quality remains weak, so the
  next step is an 8-round Sonnet validation, not promotion-quality claims.
- The latest 6-round solver-design validation reached official screening for
  three candidates and correctly abandoned all three on solver quality. The
  other three rounds exposed pre-screen control issues: C9e falsely rejected
  helpers called from solver class methods/runtime aliases, and C6 did not
  compile parsed code to catch repeated keyword arguments. C6 now parses and
  compiles patch code; C9e now treats the runtime solver class `solve(...)`
  call chain as an integration root while still rejecting helpers reachable
  only from detached classes.
- `ContractGate` is being decomposed incrementally. C9e now lives in
  `contract/checks/solver_design_integration.py`; `gate.py` remains the
  orchestrator that wraps focused checks into auditable `CheckResult`s. Use
  this pattern for future C7/C9b/C9c extraction instead of growing the
  monolithic gate file.
- Real-cost validation should use Sonnet by default
  (`SCION_MODEL=claude-sonnet-4-6`). Reserve Opus for explicitly chosen deep
  research attempts after the framework path is stable.
- Provider SDK retries are disabled by default through `SCION_SDK_MAX_RETRIES=0`
  semantics in `LLMClient`; Scion's own `SCION_LLM_MAX_RETRIES` controls the
  audited retry count. Do not multiply hidden SDK retries by Scion retries in
  experiment runs.

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
