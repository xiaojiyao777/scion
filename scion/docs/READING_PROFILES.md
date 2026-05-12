# Scion Reading Profiles

*Last updated: 2026-05-10*

Use this guide to keep new sessions small. Start with the base pack, choose one
profile, and stop reading when the next action is clear.

## Base Pack

Read these for every session:

1. [Agent onboarding](AGENT_ONBOARDING.md)
2. [v0.4 current state](status/current-state.md)

Do not read `status/v0.4-history.md`, old experiment docs, full engineering
references, raw run directories, or source trees unless the selected profile
requires them.

## Document Roles

- `status/current-state.md`: short current operating truth. Keep it small.
- `status/v0.4-history.md`: archived historical status log. Read only for
  chronology questions.
- `../design/`: design-source documents and accepted architecture contracts.
- `engineering/`: code ownership maps and implementation references.
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

For APS-backed runs, analyze both phases per round:

- hypothesis/research session;
- code/implementation session;
- tools called and context observed;
- selected surface and forced-surface constraints;
- hypothesis identity and `novelty_signature`;
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
3. [v0.4 design index](../design/v0.4/README.md), then only the relevant
   design source.

Common design docs:

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
3. [Framework code map](engineering/framework-code-map/README.md).
4. One or two relevant code-map sections:
   - campaign lifecycle: `01-core-campaign.md`;
   - proposal/context/APS: `02-proposal-context.md`;
   - gates/protocol/decision: `03-evaluation-decision.md`;
   - evidence/lineage: `04-evidence-lineage.md`;
   - adapter boundary: `05-problem-adapter-boundary.md`;
   - CVRP package: `06-cvrp-package-map.md`;
   - extension risks: `07-extension-points-and-risks.md`.
5. Source files only after the map identifies the likely owners.

Update:

- code and tests;
- relevant engineering map sections;
- `status/current-state.md` when the project state, validation result, or next
  bottleneck changes.

Verification:

- use focused tests first;
- use `/home/clawd/miniconda3/envs/claw/bin/python`;
- broaden to the full suite when touching shared governance, protocol,
  adapters, or campaign lifecycle.

## Profile: CVRP Surface Work

Read:

1. Base pack.
2. Algorithm design-space upgrade.
3. Problem/algorithm onboarding design.
4. CVRP package map.
5. CVRP problem spec or surface files only when implementing or verifying code.

Keep the boundary clear:

- Scion core may add generic surface/governance hooks.
- CVRP package owns solver hooks, allowed components, policy files, runtime
  field meanings, and controlled fixtures.
- `solver_design` is the top-level problem-object boundary. It is backed by
  `policies/main_search_strategy.py`, and component policies should support
  that solver-level hypothesis rather than define the research target. Current
  solver-design work should use `problem_adaptation` to declare strategy
  family, instance-profile intent, phase objective, component roles/order, and
  evidence targets for the whole CVRP problem object.

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

Do not let the LLM directly edit arbitrary solver internals during campaigns.
First make the solver into a Scion-native research object.

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
- Keep `status/current-state.md` under roughly a few hundred lines.
- Move historical status chronology to `status/v0.4-history.md`.
- Put experiment detail in `experiments/v0.4/`, not current-state.
- Put engineering implementation maps in `engineering/`, not design docs.
- Add index links when adding docs.

## What Not To Load By Default

- `/home/clawd/research/scion-experiments/` raw run directories.
- Raw protocol metrics JSON/CSV.
- Long run logs.
- CVRPLIB raw instances and `.sol` files.
- `archive/` and `../design/archive/`.
- `status/v0.4-history.md`.
- Full source trees before using code maps.

## Handoff Checklist

End each non-trivial task with:

- profile used and extra docs/source/raw artifacts read;
- changed files;
- tests or validation commands;
- docs updated;
- residual risks or next actions;
- commit hash if committed.
