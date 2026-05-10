# Scion Agent Onboarding

*Last updated: 2026-05-10*

This is the first document an agent or developer should read before working on
Scion. It explains what the project is, where the current truth lives, what is
done, what is pending, and how to work without damaging the framework/problem
boundary.

## One-Sentence Project Definition

Scion is a governed autoresearch framework for combinatorial optimization
algorithms: LLMs propose research changes, while deterministic Contract,
Verification, Protocol, and Decision layers decide whether evidence is strong
enough to continue, validate, freeze, promote, or abandon.

## Current Status Snapshot

- Active version: v0.4 on `v0.4-dev`.
- Foundational design: [Architecture v3](../design/scion-architecture-v3.md).
- Current state: [v0.4 current state](status/current-state.md).
- Active upgrade theme: move from operator-only optimization to
  problem-owned algorithm research surfaces.
- Current main research objects:
  - `surrogate` / warehouse delivery: original v0.3 research object.
  - CVRP / VRP: v0.4 second real problem class used to validate Scion's
    adapter and algorithm-surface generality.
- Current bottleneck: V2-V8 gate modernization is closed, CVRP policy-surface
  API guidance has been repaired, APS observation-budget/recovery is fixed
  enough to unblock proposal work, selected-surface reporting is validated in
  real formal CVRP artifacts, and the first `baseline_policy` diagnostic has
  completed. That diagnostic proved the problem-owned surface can be selected,
  patched, loaded, audited, and screened, with all declared runtime fields
  present for the evaluated candidate, but it did not produce solver-quality
  evidence. CVRP now has `main_search_strategy`, a problem-owned
  whole-algorithm surface in `policies/main_search_strategy.py`. The bottleneck
  remains CVRP algorithm-surface efficacy. The first tightly forced
  `main_search_strategy` diagnostic validated continuous forced-surface control
  and active whole-algorithm runtime audit, but only one candidate reached
  screening and it still failed `SCREENING_FAIL_WIN_RATE`. Do not run a long
  solver-quality validation. Singleton semantic novelty has a code-level
  repair, and APS surface reads now use compact `surface-contract.v1` payloads
  with a 48000-character default observation cap. The clean-worktree
  `main_search_strategy` diagnostic from commit `b98196b` validated those
  control repairs: all three candidates reached screening on the forced
  surface. It still did not produce solver-quality evidence; all three failed
  `SCREENING_FAIL_WIN_RATE`, and none selected `route_pair_swap` or
  `bounded_destroy_repair`. The current blocker is candidate use and efficacy
  of the deeper problem-owned main-search components.
- Design conclusion: problem/algorithm onboarding is a first-class Scion
  module, not incidental setup. See
  [v0.4 problem and algorithm onboarding](../design/v0.4/v0.4-problem-algorithm-onboarding.md).
  Version boundary: v0.4 should validate autoresearch on manually onboarded
  problem packages; v0.5 should own onboarding automation. See
  [v0.5 onboarding memo](roadmap/v0.5-onboarding-memo.md).

## Required Reading Order

For architecture or planning work:

1. This document.
2. [Architecture v3](../design/scion-architecture-v3.md).
3. [v0.4 current state](status/current-state.md).
4. [v0.4 algorithm design-space upgrade](../design/v0.4/v0.4-algorithm-design-space-upgrade.md).
5. [v0.4 problem and algorithm onboarding](../design/v0.4/v0.4-problem-algorithm-onboarding.md).
6. [Framework code map](engineering/framework-code-map/README.md).
7. [Extension points and risks](engineering/framework-code-map/07-extension-points-and-risks.md).

For implementation work delegated to a subagent:

1. Read the relevant engineering map section.
2. Read the relevant design source.
3. Inspect only the necessary code paths.
4. Update the matching engineering map after tests pass.

For experiment analysis:

1. Read [v0.4 current state](status/current-state.md).
2. Read the relevant post-run analysis under `experiments/`.
3. Analyze raw experiment artifacts only in a delegated subagent task.
4. For agentic-proposal runs, analyze every round's two APS phases:
   hypothesis/research session and code/implementation session. The analysis
   must identify tool calls, observed context, selected surface, hypothesis
   identity, patch target, actual strategy/operator change, and whether the
   agent used screening/runtime feedback or only surface text.
5. Connect proposal behavior to deterministic gates and protocol results:
   Contract, Verification, canary, screening/validation/frozen, Decision, and
   reason codes. A run-level W/L/T summary is not sufficient.
6. Summarize bounded findings back into `status/current-state.md` and the
   relevant experiment/audit document.

## Non-Negotiable Project Principles

1. Scion is the framework. Research-object semantics must not be hardcoded into
   framework core. Warehouse, CVRP, and future problems enter through
   problem packages, `ProblemSpecV1`, `ProblemAdapter`, declared research
   surfaces, solver wrappers, and problem-owned tests.
2. The main session should not read source code or raw experiment records by
   default. The main session owns architecture design, progress tracking,
   development acceptance, and experiment design. Concrete source inspection,
   implementation, and raw experiment analysis should be delegated to subagents.
3. Raw data should not be read directly in the main session. This includes test
   fixtures, VRP/CVRPLIB instances, raw solver outputs, run logs, raw metrics,
   and large experiment JSON/CSV artifacts.
4. The Python execution environment is the conda environment `claw`; use
   `/home/clawd/miniconda3/envs/claw/bin/python`.
5. When a subagent updates code and the change is accepted, it must also update
   the corresponding engineering documentation before the task is considered
   complete.

## What Is Already Done

- v3 architecture defines the controlling governance model: LLM output is
  tainted; decisions read only deterministic `DecisionFeatures`.
- v0.3 separated the original warehouse research object from Scion framework
  logic.
- v0.4 reinforced the adapter boundary with `ProblemSpecV1`, metric specs,
  objective policy, adapter-backed verification, and runtime-aware promotion
  governance.
- CVRP is integrated as a strict problem package with route-native adapter
  checks, objective recomputation, formal/controlled configs, and runtime audit
  fields.
- CVRP exposes multiple research surfaces:
  `route_local`, `route_pair`, `ruin_recreate`, `search_policy`,
  `baseline_policy`, `construction_policy`, `neighborhood_portfolio`,
  `algorithm_blueprint`, and `main_search_strategy`.
- `AgenticProposalSession` exists as a bounded Creative Layer path with proposal
  tools, exposure policy, compact session refs, and tainted artifacts.
- Selected research surface metadata now propagates through Verification,
  canary, and screening/validation/frozen candidate-side protocol runtime audit.
  Surface-declared `evidence.required_runtime_fields` fail closed outside
  verification as well as inside it.
- Protocol pair metrics and campaign summaries now preserve and summarize
  selected-surface required runtime fields with bounded representative values,
  without adding those tainted runtime values to DecisionFeatures.
- V2 interface validation shares the AST-only surface interface validator used
  by `ContractGate C7`; V5 disables the legacy assignment/vehicles fallback for
  bridged adapter-required `problem-v1` packages when an adapter is missing.
- V6/V7/V8 now also keep adapter-required `problem-v1` packages on
  adapter-backed verification paths, and successful V8 comparison mode is
  persisted as bounded `CheckResult` metadata rather than decision input.
- CVRP policy surfaces now expose safe problem-owned instance helpers
  (`customer_ids`, `customer_count`, `demands`, `capacity`, `distance`) and
  explicitly reject `instance.customers` as an undefined alias.
- APS planner mode now reads compact feedback when available, reads the selected
  surface before code generation/partial finalization, and uses compact static
  preview payloads that omit patch code.
- APS observation-budget/recovery behavior is compact-first: surface reads use
  a bounded `surface-contract.v1` section view by default, optional oversized
  reads fail closed, and the default observation cap is now 48000 chars so the
  normal list/problem/feedback/selected-surface sequence has room without
  exposing raw refs.
- Campaign orchestration has been decomposed; `CampaignManager` is mostly a
  facade over proposal, evaluation, promotion, evidence, failure lifecycle, and
  branch-step services.
- Documentation has been reorganized by purpose:
  design, status, engineering, planning, experiments, audits, evidence,
  operations, reference, roadmap, and archive.

## Current Pending Work

Gate modernization follow-up:

- V2/V5/V6/V7/V8 modernization is complete as of 2026-05-07.
- Keep remaining legacy verification fallbacks compatibility-only and keep the
  adapter-backed path authoritative for new problem-v1 packages.

Near-term CVRP research-space work:

- The post-repair Sonnet CVRP smoke has been analyzed:
  `/home/clawd/research/scion-experiments/v04-post-aps-cvrp-sonnet-20260507T083649Z`.
  The analysis is recorded in
  `docs/experiments/v0.4/v0.4-post-aps-cvrp-sonnet-20260507.md`.
- The forced `algorithm_blueprint` APS budget/recovery smoke has been analyzed:
  `/home/clawd/research/scion-experiments/v04-forced-blueprint-budget-sonnet-20260507T133711Z`.
  The analysis is recorded in
  `docs/experiments/v0.4/v0.4-forced-blueprint-budget-sonnet-smoke-20260507.md`.
- The post-reporting validation run has been analyzed:
  `/home/clawd/research/scion-experiments/v04-blueprint-reporting-sonnet-5r-20260507T141342Z`.
  The analysis is recorded in
  `docs/experiments/v0.4/v0.4-blueprint-reporting-sonnet-5r-20260507.md`.
  It validated that selected-surface `algorithm_*` runtime fields survive in
  real formal screening pair metrics and campaign summaries.
- The baseline-policy Sonnet diagnostic has been analyzed:
  `/home/clawd/research/scion-experiments/v04-baseline-policy-sonnet-3r-20260507T153355Z`.
  The analysis is recorded in
  `docs/experiments/v0.4/v0.4-baseline-policy-sonnet-3r-20260507.md`.
  It validated `baseline_policy` loading/runtime audit/parameter propagation,
  but did not show enough screening quality to justify long validation.
- CVRP now has a problem-owned whole-algorithm `main_search_strategy` surface.
  It is inactive by default; enabled plans can govern construction ensemble,
  repo-local baseline budget and sanitized params, package-owned improvement
  components including route-pair swap and bounded destroy/repair,
  acceptance/restart/perturbation, and optional post-baseline registry
  operators. `--force-surface` now persists across proposal rounds for clean
  diagnostic campaigns.
- Governance risk repair is complete for this slice: selected-surface
  `*_active` runtime fields must be truthy, common file-read APIs are blocked
  by ContractGate, non-operator/singleton surfaces cannot directly probe
  `instance.name`, and proposal interface preview runs only after full
  ContractGate success.
- The forced `main_search_strategy` diagnostic has been analyzed:
  `/home/clawd/research/scion-experiments/v04-main-search-strategy-sonnet-3r-20260508T133838Z`.
  The analysis is recorded in
  `docs/experiments/v0.4/v0.4-main-search-strategy-sonnet-3r-20260508.md`.
  It validated persistent force-surface behavior and complete active runtime
  audit for the selected surface, but only one candidate reached screening.
- Treat APS budget/recovery as unblocked. The budget headroom is low and may
  deserve later compaction, but the next work is not another compactness fix or
  a longer run.
- Improve CVRP surface efficacy before any long solver-quality validation. The
  latest baseline-policy diagnostic passed Contract, Verification, canary, and
  runtime audit for all evaluated candidates, but all candidates still failed
  screening with `SCREENING_FAIL_WIN_RATE`. The latest main-search diagnostic
  had one runtime-valid candidate fail screening and two later hypotheses fail
  C10 novelty. C10 now allows distinct singleton semantic identities through
  `novelty_signature`, and `context.read_surface(main_search_strategy)` is
  compact by default. The next experiment step is to rerun a tightly forced
  `main_search_strategy` diagnostic and check whether multiple candidates reach
  screening and exercise route-pair-swap / bounded destroy-repair components,
  not another generated post-baseline operator or a baseline-policy-only run.
- A clean-worktree forced `main_search_strategy` diagnostic has been analyzed:
  `/home/clawd/research/scion-experiments/v04-main-search-strategy-sonnet-3r-20260508T142513Z`.
  The analysis is recorded in
  `docs/experiments/v0.4/v0.4-main-search-strategy-clean-sonnet-3r-20260508.md`.
  It validated persistent forced-surface selection, C10 singleton novelty, APS
  compact selected-surface reads, and active runtime audit across three
  screened candidates.
- The problem/algorithm onboarding design has been captured in
  `design/v0.4/v0.4-problem-algorithm-onboarding.md`. Treat CVRP's manual
  adapter/surface/component work as a prototype of a future onboarding module
  that turns human-written solvers into Scion-native research objects.
- Add or refine bounded problem-owned surfaces only when the problem package can
  define invocation point, contract, runtime audit fields, and tests.
- Keep BKS/gap as final reporting evidence, not promotion evidence.

Documentation work:

- Keep [v0.4 current state](status/current-state.md) accurate after each
  development, experiment, or stage closeout.
- Keep `engineering/framework-code-map/` synchronized with code changes.
- Keep design-source docs in `../design/`, not mixed into `docs/` root.

## Development Workflow

Use a phase discipline inspired by production-grade agent-skill workflows:

1. Define the slice.
   State the surface, problem package owner, target files, solver invocation
   point, contract checks, runtime audit fields, prompt/context fields, and
   tests. If these cannot be named, the task is not implementation-ready.
2. Plan the smallest vertical change.
   Prefer thin slices that pass through spec, adapter/solver, gates, tests, and
   docs. Avoid broad refactors unless the design explicitly calls for them.
3. Implement through the right boundary.
   Problem semantics go into problem packages. Generic governance goes into
   framework core only when it applies across problems.
4. Verify with `claw`.
   Use focused tests first, then the relevant broader suite. Record exact
   commands and outcomes in the task handoff or docs.
5. Review the boundary.
   Check that no CVRP/warehouse/future problem semantics entered
   `DecisionEngine`, `SafeFeatureExtractor`, `ExperimentProtocol`,
   `CampaignLoop`, or `BranchStepRunner` unless the design explicitly changed a
   generic contract.
6. Update documentation.
   Update current state, engineering maps, design docs, planning docs, or
   experiment/audit docs depending on what changed.
7. Commit cleanly.
   Stage only files belonging to the slice. Do not include unrelated dirty
   source or experiment artifacts.

## Agent Behavior Norms

These norms combine lessons from two external development-skill collections
with Scion-specific constraints. The useful pattern is not to install those
skills directly, but to adapt their workflow discipline:

- `agent-skills` style: define explicit lifecycle workflows with trigger
  conditions, steps, verification, review axes, red flags, and go/no-go gates.
- `andrej-karpathy-skills` style: keep a small set of high-leverage behavior
  principles, repeat them consistently across docs, and explain them with
  concrete counterexamples.

- Treat skills as workflows, not reference prose. Every task should have
  explicit steps, verification, anti-patterns, and exit criteria.
- Load only the context needed for the current phase. Do not stuff a session
  with raw logs, source files, benchmark data, or stale analysis when an index
  or engineering map is enough.
- Think before editing. Identify assumptions and the boundary being changed
  before touching files.
- Be surgical. Make the smallest coherent change that moves the current slice
  forward; do not invent abstractions without a local reason.
- Verify the actual target result. A successful command is not enough if it did
  not exercise the changed boundary.
- Do not silently guess. If a fact can be discovered from docs or a delegated
  read-only audit, discover it. If it cannot and the assumption is risky, ask.
- Keep final answers and handoffs concrete: changed files, tests run, docs
  updated, residual risks.

## Scion Workflow Pattern

Use this pattern for non-trivial development and experiment work:

| Phase | Purpose | Scion-Specific Exit Criteria |
|---|---|---|
| Define | Clarify the requested slice and assumptions. | Surface/problem/gate/evidence impact is named, or the ambiguity is explicitly raised. |
| Plan | Build a read-only dependency map. | Owner boundary is clear: framework core vs problem package vs adapter vs docs. |
| Build | Implement the smallest coherent vertical change. | Every changed file is traceable to the slice. |
| Verify | Prove behavior with focused evidence. | Commands/artifacts show the changed boundary was exercised. |
| Review | Check correctness and Scion invariants. | No problem semantics leaked into core; tainted data does not reach Decision. |
| Ship | Update docs and commit only the slice. | Current-state/engineering docs are updated where needed; unrelated dirty files are not staged. |

For Scion, "vertical" usually means:

```text
ProblemSpecV1 / research surface metadata
-> adapter or solver runtime contract
-> Contract / Verification / Protocol / evidence handling
-> focused tests
-> engineering docs and current state
```

Do not convert this into ceremony for trivial edits. Single-file typo fixes or
obvious documentation corrections can be handled directly. Multi-file changes
touching core gates, protocol, adapters, evidence, or research surfaces should
follow the full workflow.

## Review Axes

Every implementation handoff should be reviewable on these axes:

- Correctness: does the code do the requested thing?
- Boundary isolation: does framework core remain problem-agnostic?
- Experiment governance: are Contract, Verification, Protocol, and Decision
  still separate?
- Evidence lineage: are runtime failures, raw metrics refs, decisions, and
  promotions auditable?
- Determinism and runtime: are seed/RNG, nondeterminism, timeout, and runtime
  failure paths handled?
- Maintainability: is the change local, understandable, and documented?

Every experiment-analysis handoff should be reviewable on these axes:

- APS behavior: did the hypothesis session and code session use the expected
  tools, selected surface, forced constraints, feedback, and memory?
- Actual change: did the candidate modify an operator, a policy/config surface,
  or a whole-algorithm strategy, and what bounded behavior changed?
- Gate causality: did the candidate fail because of agent surface drift,
  Contract, Verification, runtime audit, canary, protocol thresholds, or
  deterministic Decision vetoes?
- Evidence semantics: do runtime audit fields represent valid no-op states
  without creating false failures, and are component-local counters separated
  from final candidate-vs-champion benefit?
- Protocol interpretation: do pair wins survive seed/case aggregation, median
  delta, runtime governance, and stage thresholds?
- Next-action quality: does the analysis identify the boundary to repair
  next, rather than only reporting aggregate W/L/T or a generic "screening
  failed" outcome?

For each changed boundary, state why the change belongs there. Examples:

- Framework core: only for generic governance behavior shared across problems.
- Problem package: domain semantics, solver hooks, surface files, allowed modes
  or components, runtime field meanings.
- Adapter: solution normalization, feasibility, objective recomputation, prompt
  rendering, and semantic oracle behavior.
- Proposal tools: tainted observation/drafting/previews only.
- Protocol/Decision: deterministic evidence and stage rules only.

## Common Anti-Patterns

Avoid these Scion-specific failure modes:

- "This is only CVRP, so put it in core for now." Put problem semantics in the
  CVRP package or adapter; generic hooks can be added to core only when they
  apply beyond CVRP.
- "The solver says feasible, so trust it." Adapter-backed verification must
  recompute consistency, feasibility, and objective fields.
- "The proposal agent observed it, so Decision can use it." Proposal
  observations are tainted. Decision reads only `DecisionFeatures`.
- "Frozen/raw validation details would help the next proposal." Holdout detail
  must remain exposure-controlled; use aggregate summaries only where allowed.
- "A policy surface is just another operator." Non-operator surfaces need
  surface-declared interface, invocation point, bounds, runtime fields, and
  tests.
- "Runtime failure is a tie." Runtime failure, incomplete evidence, and missing
  required runtime fields must fail closed where the gate contract requires it.
- "The docs can wait." In this project, docs are part of the operating system
  for future agent sessions; accepted code changes require matching engineering
  docs.
- "One broad cleanup will make this easier." Prefer a small vertical slice that
  proves the boundary, then refactor only when the duplication or coupling is
  concrete.

## Main Session vs Subagent Responsibilities

Main session:

- Maintains architecture direction and project memory.
- Designs experiments and validates subagent outputs.
- Reads design/status/engineering docs.
- Avoids raw source and raw experiment data unless explicitly needed.
- Decides what should be delegated and integrates results.

Subagents:

- Inspect source for bounded questions.
- Implement scoped code changes.
- Analyze raw experiment artifacts when asked.
- Run tests and report exact commands.
- Update engineering docs for accepted code changes.

## Raw Data And Source Hygiene

Do not read these in the main session by default:

- `/home/clawd/research/scion-experiments/` raw run directories.
- CVRPLIB raw instance files and `.sol` files.
- Raw protocol metrics JSON/CSV.
- Long run logs.
- Full source trees when the engineering map can answer the question.

Allowed in the main session:

- Design docs.
- Status docs.
- Engineering maps.
- Bounded summaries produced by subagents.
- Checked-in config/manifest files when needed for planning.

## Required Documentation Updates

After code development:

- Update the relevant engineering map under
  `docs/engineering/framework-code-map/`.
- Update [v0.4 current state](status/current-state.md) if the project state,
  validation count, or next bottleneck changed.
- Update design docs only if the architecture or accepted design contract
  changed.

After experiment analysis:

- Add or update a document under `docs/experiments/v0.4/`.
- Update [v0.4 current state](status/current-state.md) with the run root,
  configuration, outcome, and interpretation.
- For APS-backed runs, include a per-round chain:
  hypothesis session behavior, code session behavior, actual patch/strategy
  content, gate/protocol path, and causal diagnosis.
- Keep raw metrics as refs; do not paste raw outputs into docs.

After audits:

- Add or update a document under `docs/audits/v0.4/`.
- Convert accepted audit findings into planning items or current-state backlog.

After phase closeout:

- Update the matching `docs/planning/v0.4/` closeout.
- Update [v0.4 current state](status/current-state.md).
- Update this document if onboarding rules, read order, or project principles
  changed.

## Quick Command Reference

Use the project Python:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
```

For focused tests, run from the repository root or `scion/` according to the
existing test path used in the relevant planning/engineering doc.

## Handoff Checklist

Before ending a task:

- State whether source code, docs, raw experiments, or only indexes were read.
- List files changed.
- List tests or validation commands run.
- State whether current-state and engineering docs were updated.
- State residual risks or known gaps.
- If committing, confirm unrelated dirty files were not staged.
