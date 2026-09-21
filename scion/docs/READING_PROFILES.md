# Scion Reading Profiles

*Last updated: 2026-09-05*

This is a subordinate context router. Start with the canonical repository entry
[`../../AGENTS.md`](../../AGENTS.md), complete the current handoff it names,
then choose at most one profile below.

## Base Pack

Read the files in the exact order declared by
[`../../AGENTS.md`](../../AGENTS.md). Do not create a competing base-pack order
here.

Do not read `status/v0.4-history.md`, old experiment docs, full engineering
references, raw run directories, or source trees unless the selected profile or
current task requires them.

## Document Roles

- `../TASK.md`: current goal, boundary, accepted work, and next action.
- `status/current-state.md`: short current operating snapshot. Keep it small and
  replace stale conclusions instead of appending event history.
- `status/v0.4-history.md`: curated milestone index. Read only for provenance
  questions or when the current state points to a specific milestone.
- `../design/`: design-source documents and accepted architecture contracts.
- `engineering/`: historical code maps and implementation references. Treat
  them as locators and verify every claim against current source.
- `experiments/`: bounded post-run analysis. Prefer these over raw run
  artifacts.
- `audits/`: audit findings and governance reviews.
- `planning/`: task manifests, worklogs, phase closeouts, and readiness
  plans.
- `operations/`: runbooks and command references.
- `archive/` and `../design/archive/`: historical reference only.

## Profile: Experiment Analysis

Read:

1. Base pack.
2. [v0.4 experiments index](experiments/v0.4/README.md).
3. The specific experiment analysis document, if it already exists.
4. Raw run artifacts only through a bounded analysis task when the checked-in
   docs are insufficient.

For autonomous H/C runs, analyze both creative phases per attempt:

- hypothesis/research session;
- code/implementation session;
- tools called and context observed;
- the complete problem-owned algorithm object and any declared editable
  boundary; forced targets are diagnostic-only and cannot become formal
  research evidence;
- exact hypothesis content, declared locus/action and whether prior evidence was
  used without turning novelty into a gate;
- patch target and actual mechanism/strategy change;
- Contract, Verification, canary, Protocol, and Decision path;
- whether feedback/runtime observations reached final generation prompts.

Update:

- the relevant experiment doc under `experiments/v0.4/`;
- `status/current-state.md` when the run changes current interpretation;
- the experiment index when adding a new analysis doc.

## Profile: Design Discussion

Read:

1. Base pack.
2. [Scion architecture v3](../design/scion-architecture-v3.md) if the task
   touches governance boundaries or the user asks about Scion logic.
3. [Direct-runtime addendum](../design/scion-architecture-v3-v0.4-direct-runtime-addendum.md)
   for the smaller current implementation.
4. [v0.4 design index](../design/v0.4/README.md), then only a source explicitly
   relevant to the task. The index is historical/problem-design context, not a
   second authority.

Task-specific historical/problem design sources:

- Algorithm research surfaces and APS:
  [`v0.4-algorithm-design-space-upgrade.md`](../design/v0.4/v0.4-algorithm-design-space-upgrade.md)
- Problem/algorithm onboarding:
  [`v0.4-problem-algorithm-onboarding.md`](../design/v0.4/v0.4-problem-algorithm-onboarding.md)
- Agentic proposal session:
  [`v0.4-agentic-proposal-session-design.md`](../design/v0.4/v0.4-agentic-proposal-session-design.md)
- CVRP research surfaces:
  [`v0.4-cvrp-research-surface-design.md`](../design/v0.4/v0.4-cvrp-research-surface-design.md)

Update design docs only when an accepted architecture contract changes. Put
status movement in `status/current-state.md`, not in design sources.

## Profile: Code Repair Or Feature Work

Read:

1. Base pack.
2. The relevant design source only if the behavior is governed by a design
   contract.
3. Current source reached from the execution order in
   [Agent onboarding](AGENT_ONBOARDING.md).
4. Optionally use the [historical framework code map](engineering/framework-code-map/README.md)
   only as a locator, then verify the named files and symbols still exist:
   - campaign flow and branch state: `01-core-campaign.md`;
   - proposal/context (historical path labels): `02-proposal-context.md`;
   - gates/protocol/decision: `03-evaluation-decision.md`;
   - evidence/lineage: `04-evidence-lineage.md`;
   - adapter boundary: `05-problem-adapter-boundary.md`;
   - CVRP package: `06-cvrp-package-map.md`;
   - extension risks: `07-extension-points-and-risks.md`.
5. Read only the responsible current components and their focused tests.

Update:

- code and tests;
- relevant engineering map sections;
- `status/current-state.md` when the project state, validation result, or next
  bottleneck changes.

Verification:

- use focused tests first;
- use the Python path declared by the current handoff;
- broaden to the full suite when touching shared boundaries, protocol,
  adapters, or campaign flow.

## Profile: CVRP Surface Work

Read:

1. Base pack.
2. Algorithm design-space upgrade.
3. Problem/algorithm onboarding design.
4. CVRP package map.
5. CVRP problem spec or surface files only when implementing or verifying code.

Keep the boundary clear:

- Scion core owns only problem-neutral research, safety, scientific, and
  scheduling boundaries.
- CVRP package owns solver hooks, allowed components, policy files, runtime
  field meanings, and controlled fixtures.
- `solver_design` is the top-level problem-object boundary. It is backed by
  `policies/baseline_algorithm.py::solve(...)` plus focused branch-owned
  modules under `policies/baseline_modules/`; `policies/solver_algorithm.py`
  remains only as a compatibility hook.
  Component policies and the older `main_search_strategy` state table are
  legacy implementation/regression surfaces; they should not define the
  top-level research target for current CVRP optimization work.

## Profile: New Problem Or Solver Onboarding

Read:

1. Base pack.
2. Problem/algorithm onboarding design.
3. Adapter boundary code map.
4. Research-surface design docs relevant to the new solver.
5. Operations docs only when planning actual campaigns.

The output should name:

- objective and feasibility semantics;
- adapter responsibilities;
- candidate research surfaces;
- invocation points;
- allowed data exposure;
- runtime audit fields;
- smoke tests and formal split policy.

Expose a complete, runnable algorithm object through a problem-owned adapter and
an explicit editable boundary. Core must not learn the problem's mechanisms,
case names, solver structure, or telemetry meanings.

## Profile: Audit Or Governance Review

Read:

1. Base pack.
2. Relevant audit docs under `audits/v0.4/`.
3. Architecture v3 for governance invariants.
4. Engineering maps and source only for the audited boundary.

Update:

- the audit document;
- planning/backlog items for accepted findings;
- current state only when the active interpretation changes.

## Profile: Documentation Maintenance

Read:

1. Base pack.
2. [Docs index](README.md).
3. The specific target docs.

Rules:

- Keep `AGENT_ONBOARDING.md` short.
- Keep `status/current-state.md` short enough to be a resume point.
- Keep one canonical repository entry in `../../AGENTS.md`; other entry-like
  documents route to it rather than restating authority.
- Keep `status/v0.4-history.md` as a sparse milestone index, not a chronology.
- Put experiment detail in `experiments/v0.4/`, not current-state.
- Put engineering implementation maps in `engineering/`, not design docs.
- Add index links when adding docs.

## What Not To Load By Default

- External raw experiment/run directories.
- Raw protocol metrics JSON/CSV.
- Long run logs.
- CVRPLIB raw instances and `.sol` files.
- `archive/` and `../design/archive/`.
- `status/v0.4-history.md`.
- Full source trees before the task and current entry identify the responsible
  components.

## Handoff Checklist

End each non-trivial task with:

- profile used and extra docs/source/raw artifacts read;
- changed files;
- tests or validation commands;
- docs updated;
- residual risks or next actions;
- commit hash if committed.
