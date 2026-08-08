# Scion v0.4 V3 Research-Effectiveness Task

*Working branch: `codex/v04-v3-research-hotpath`*
*Accepted starting point: `origin/v0.4-dev` at `317fcb54`*
*Last updated: 2026-08-08*

This is the active task source.  `scion/design/scion-architecture-v3.md` is the
architecture authority; the direct-runtime addendum only narrows obsolete
retry, budget, and context examples.  `scion/docs/status/current-state.md`
records current evidence.  Long chronology belongs in experiment reports, not
here.

## Objective

Close v0.4 only when a Scion agent demonstrates useful research behavior on
both Warehouse and CVRP/VRP:

```text
complete problem facts + complete current source + prior safe evidence
  -> one Hypothesis provider call
  -> structural Hypothesis Contract
  -> one Code provider call bound to the approved H
  -> structural Patch Contract
  -> isolated Workspace
  -> executable Verification
  -> problem-owned comparative Protocol
  -> Safe Features
  -> deterministic Decision
  -> evidence-informed next research direction
```

The target is not a deployment system.  The target is an agent that proposes a
substantive algorithmic idea, implements it correctly, measures it against the
champion on real solver cases, interprets the trusted outcome through the
framework, and changes or deepens direction using prior structured evidence.

Framework tests are necessary but do not close this task.  A scientifically
valid negative candidate may prove effective research; a pile of passing
identity, packaging, or lifecycle tests does not.

## V3 boundary

The active research path retains only these hard boundaries:

1. LLM output is tainted and may propose only structured H and C objects.
2. Contract checks schema, editable source boundary, interface, approved-H
   binding, and forbidden APIs.  It does not grade novelty or research style.
3. Verification checks that the candidate imports, runs, preserves feasibility
   and objective semantics, and does not leak state.
4. Protocol owns case/seed comparison and statistical verdicts.
5. Decision reads only typed Safe Features, never provider prose.
6. Workspace isolation prevents candidate code from mutating the champion.
7. Minimal append-only lineage records H, C, verification, protocol, and
   decision so the research path can be inspected and replayed.
8. Warehouse and CVRP own their algorithm semantics, mechanism attribution,
   cases, metrics, and protocol interpretation.

Determinism is retained where it establishes scientific equivalence: exact
candidate source, exact case/seed set, champion/candidate pairing, and replayed
Protocol/Decision results.  A content digest may be used as a compact equality
check, but a digest is not authority and must not create another lifecycle.

## Explicitly out of scope

For the whole v0.4 research-effectiveness scope, including after the controls
pass, do not spend implementation or review time on:

- root-owned installation, `/var/lib/scion`, systemd, D-Bus, cgroups, service
  units, `StartUnit`, nonce ledgers, or loaded-manager acceptance;
- distribution, deployment, wheels, packaging, reproducible builds, release
  artifacts, or remote installation;
- fixed-source acceptance, Git mirrors, source-signing flows, review-closure
  ingestion, or root trust receipts;
- object identity graphs, revision leases, issue/claim/spend capabilities,
  signing or registration protocols, durable-owner authorities, or nested
  intent/commit/closure receipts for one local research fact;
- duplicate hashes of the same in-process object, hash chains, or repeated
  reopen proofs that do not protect a V3 scientific boundary;
- automatic provider retry, Scion prompt/token/file/session budgets,
  truncation, top-k context selection, novelty gates, blacklists, forced
  mechanisms, or host-selected target files in formal controls.

Existing deployment and authority prototypes remain historical branches.  They
are neither deleted as evidence nor imported into the active research path.
They do not block experiments and do not count toward v0.4 completion.

## What “effective research” means

A problem control is effective only when all applicable claims are supported:

- **Research process:** the provider makes substantive H/C changes, receives
  complete current source and prior safe observations, and visibly adapts its
  next H after a result.
- **Executable validity:** the patch crosses Contract and Verification and the
  real solver produces comparable results without framework noise.
- **Scientific validity:** Protocol uses the declared split/seeds and Decision
  matches its typed outcome.
- **Attribution:** the observed effect can be associated with a problem-owned
  mechanism or constraint, including a well-explained negative result.
- **Lineage:** the human-readable chain from H to C to measurement to decision
  is complete without requiring an authority graph to understand it.
- **Retained improvement:** claimed only after independent validation.  It is
  not required for a valid negative research-process result.

## Current obstacles

### O1. Trust machinery has displaced the research loop

The dormant/experimental owner stack contains object identities, capabilities,
leases, signed transitions, duplicated digests, and closure graphs.  Parts of
that stack are imported by Contract and proposal rendering even though the
normal direct-v3 path already has plain typed inputs.  This increases failure
surface and makes debugging provider or solver behavior harder.

**Required correction:** production composition must not import the dormant
authority graph.  Remove or quarantine unused owner/capability modules and
delete their production-facing adapters and tests.

### O2. Provider-call persistence is over-specified

The active proposal path wraps one H/C pair in attempt IDs, continuation IDs,
prompt receipts, transition records, formal-candidate bindings, and repeated
identity checks.  V3 requires one durable call and lineage, not a local PKI.

**Required correction:** one small append-only call record per H or C, with
phase, branch/H reference, provider outcome, and trace reference.  No lease,
issue/claim/spend state, capability, or nested closure.

### O3. Research rejection and code ancestry can obstruct iteration

A malformed or Verification-rejected C must remain evidence but must not
become the next executable source.  A completed pre-Protocol rejection should
allow a fresh H on the clean base without retrying the same provider call.
Protocol-negative code must follow typed problem-owned disposition: clean
pivot, exact evaluation reuse, or explicit provisional same-mechanism work.

**Required correction:** make clean/current/provisional candidate ownership
plain branch state and test it through behavior, not object authority.

### O4. Context correctness must serve research quality

H needs the full safe problem context, complete verified current source, and
every visible screening observation.  C needs the approved H and the complete
source it may edit.  Repeated source fingerprints, prompt-signing, or compact
owner projections must not replace the actual content.

**Required correction:** keep one transparent `ProposalContextSnapshot` and a
plain, complete `SourceLedger` file map.  Tests assert visible content and
source boundaries directly.

### O5. Launch and postrun tooling obscures the shortest real path

The direct CLI already constructs `LocalSubprocessRunner`, Verification,
Protocol, and `CampaignManager`.  Root/systemd W3 launch code is unnecessary.
Large prepared-handoff/report surfaces may remain optional diagnostics but
must not gate a fresh research run.

**Required correction:** provide and test one short non-root Warehouse command
and one short non-root CVRP command.  Both create a fresh campaign root and run
the real solver directly.

### O6. Tests can prove plumbing while research remains unknown

Mock tests and identity/reopen matrices cannot answer whether the agent forms a
useful hypothesis, implements it, learns from results, and improves its next
direction.

**Required correction:** after the minimal no-LLM control, run fresh generative
controls and review the H/C content, solver behavior, Protocol evidence, and
direction change as first-class artifacts.

### O7. Formal gates can imitate control while blocking research

The previous Contract mixed V3 boundaries with host preferences about solver
shape: forced loci/targets, fixed constructors, frozen scheduler loops,
forbidden internal bridge methods, helper reachability, static return-value
guesses, case-name syntax, and telemetry naming.  These checks can reject a
scientifically useful algorithm before it reaches the isolated Workspace.

**Required correction:** classify every gate as (A) a V3 structural/capability
boundary, (B) executable behavior owned by Verification or Protocol, or (C)
host steering to remove.  Contract keeps typed H/C structure, editable/frozen
paths, approved-H binding, syntax, real public entrypoints, import resolution,
dangerous capabilities, and injected RNG.  Feasibility, determinism,
case-identity robustness, mechanism activation, and performance are measured
after materialization.  Internal code shape is agent-owned.

## Modular execution plan

### M0 — Scope reset

- [x] Stop the W3 root/source-acceptance/systemd candidate path before launch.
- [x] Preserve its historical branch and root receipts as non-blocking evidence.
- [x] Create a clean simplification branch from accepted `origin/v0.4-dev`.
- [x] Make V3 research effectiveness, not deployment closure, the task owner.

### M1 — Remove authority machinery from the proposal/Contract hot path

- [x] Remove dormant hypothesis-generation authority imports and generated-
  capability APIs from `ContractGate`, prompt projection, context management,
  and provider-call code.
- [x] Remove dormant Campaign owner/lease/registry modules that have no active
  V3 research responsibility.
- [x] Keep ordinary typed H/Patch structural Contract behavior and focused
  tests green while removing authority coupling.
- [x] Prove production import closure contains no dormant authority, lease,
  signing, issue/claim/spend, root, systemd, packaging, or W3 installation
  module.

### M1B — Reduce Contract to the V3 boundary

- [x] Audit C0–C9 and classify each check as Contract, Verification/Protocol,
  or host steering.
- [x] Remove C0 forced governance, C9d case-identity syntax, C9e problem-shape
  steering, and C4b retry/repair metadata from the Contract path.
- [x] Allow additional helper modules, safe algorithm stdlib, declared runtime
  dependencies, ordinary reflection, multi-file edits, and internal scheduler
  or state-model redesign.
- [x] Retain C1–C6, loader-backed public entrypoint/signature checks, same-patch
  and branch-base import-symbol resolution, dangerous process/network/file/env/
  dynamic-import APIs, `context.baseline` prohibition, and static global-random
  rejection.
- [x] Put real import/execution, output/feasibility semantics, declared
  case/seed pairing, mechanism evidence, and comparative effect in
  Verification/Protocol.  Rename/permutation probes are required only when a
  problem declares that invariance; they are not a universal Contract gate.
- [x] Move problem-provider availability to campaign preflight without turning
  infrastructure failure into a candidate Patch rejection.
- [x] Make `target_file` mandatory for `create_new` H so every accepted H has
  the exact file binding required to build C's complete SourceLedger.

### M1C — Remove remaining host steering from the research interface

- [x] Delete the forced surface/action/target CLI, composition, context, prompt,
  and proposal-pipeline chain; open research sees every declared safe surface.
- [x] Remove problem-specific C9e/provider resolution from generic Contract;
  missing problem infrastructure is preflight failure, never Patch rejection.
- [x] Remove prompt-only novelty, digest/provenance, and ordinary-reflection
  prohibitions that disagree with the retained V3 Contract.
- [x] Replace telemetry/mechanism keyword filtering with typed safe-evidence
  projection; exclude raw validation/frozen/holdout evidence structurally.
- [x] Collapse duplicate CLI/Campaign/Verification preflights to one typed
  pre-H environment check without self-hash or exact-class parity gates.

### M2 — Simplify the active H/C lifecycle

- [x] Replace `DirectAttemptLifecycle` and transition-closure persistence with
  one minimal append-only H/C call record.
- [x] Keep exactly one H call and one approved-H-bound C call per normal
  evaluated attempt; provider retry remains zero.
- [x] Keep provider trace and error classification for diagnosis without making
  transport metadata a scientific gate.
- [x] Remove proposal-attempt identity from formal candidate and Decision
  surfaces.

### M3 — Make continuation and SourceLedger research-oriented

- [x] Represent candidate disposition as plain typed branch state.
- [x] Ensure rejected code cannot enter current source, promotion ancestry, or
  the next clean pivot.
- [x] Wire the existing typed disposition truth table into production: Protocol
  `fail` restores the clean code parent, while `unclear/continue` alone may
  retain an explicit provisional same-mechanism head.
- [x] Continue after a completed H/Contract/Patch/Verification rejection with a
  new H on the clean base, without retry or attempt budget.
- [x] Give H complete safe observations and C a complete transparent source
  ledger; add no compression, duplicate signature, or host steering.
- [x] Keep reopen outside the fresh v0.4 acceptance path.  A supported reopen
  may read only minimal branch/source/evidence state; ambiguous state stops and
  must not be reconstructed through an authority graph.

### M3B — Make scientific gates problem-owned and case-level

- [x] Screening and validation decisions use declared case-level win/loss,
  practical delta, and confidence rules; pair rows remain explanatory evidence.
- [x] Remove pair-level, marginal-delta, and generic runtime-tie shortcuts that
  can advance a candidate outside the problem's declared objective.
- [x] Use runtime only when the problem declares it as an objective or hard
  constraint; Warehouse must not be promoted or rejected by generic runtime.
- [x] Keep metamorphic probes problem-owned and add them only where semantics
  declare rename/permutation invariance.  Neither current formal problem
  declares such an invariant, so no universal probe was added.
- [x] Record mechanism activation in Protocol evidence without making missing
  telemetry or a canary non-trigger a candidate rejection.

### M4 — Minimal end-to-end control

- [x] Run focused Contract/proposal/workspace/verification/protocol/decision
  tests.
- [x] Run one real Warehouse no-LLM control through the production Campaign
  composition and real solver.
- [x] Assert the observable order `H -> H Contract -> C -> Patch Contract ->
  Workspace -> Verification -> Protocol -> Decision`.
- [x] Assert absence of root, systemd, packaging, capability, lease, signing,
  registration, or closure dependencies on that path.

### M5 — Fresh Warehouse generative control

- [x] Start one fresh non-root direct-v3 Warehouse root on the executed
  simplified working-tree snapshot, with no force surface/action/target and no
  resume.
- [x] Complete at least two formal Protocol observations.
- [x] Require at least one substantive problem-owned algorithm edit.
- [x] Verify the next H uses prior structured evidence and changes or deepens
  direction for a scientifically intelligible reason.
- [x] Independently review H/C quality, solver activation, Protocol correctness,
  attribution, and lineage.  A negative result is acceptable; framework noise
  is not.

### M6 — Fresh CVRP/VRP generative control

- [x] Start one fresh non-root direct-v3 CVRP root from the same runtime design,
  with no force surface/action/target and no resume.
- [x] Complete enough formal observations to demonstrate a real direction
  change or mechanism refinement; target four unless evidence justifies a
  smaller terminal result.
- [x] Exclude rejected ancestry.  If validation/frozen is queued, reuse the
  exact evaluated candidate without another H/C call; this negative control
  queued no such stage.
- [x] Inspect operator activation and solver allocation so objective effects
  are not attributed to inactive code.
- [x] Independently review research quality and scientific validity.

The exact campaign roots, per-round outcomes, attribution limits, independent
reviews, and claim boundary are recorded in
`docs/experiments/v0.4/v0.4-v3-lightweight-research-effectiveness-gpt56terra-20260808.md`.
Warehouse completed 3 formal observations with 44/44 valid pairs; CVRP
completed 4 with 128/128 valid pairs.  Both used `gpt-5.6-terra` through the
local Codex proxy.  Neither produced a validated improvement, and none is
claimed.

### M7 — Close v0.4

- [x] Run the full relevant Scion suite, compileall, formatting, and diff check.
- [x] Remove dead authority/deployment hot-path tests and update architecture
  docs to the actual smaller runtime.
- [x] Update `current-state.md` with exact Warehouse and CVRP evidence.
- [x] Close only when the completion matrix below is satisfied.

Closure evidence:

- the complete default suite runs without exclusions: `1946 passed, 1 skipped,
  0 failed`; all 144 changed/new Python files pass critical Ruff checks, the 14
  final research-hot-path files pass formatter check, the complete package
  passes `compileall`, and `git diff --check` is clean;
- the obsolete DecisionCompletion, promotion-journal/crash-recovery, and
  Decision/research-rejection receipt paths and their dedicated tests are gone;
- fresh post-correction Terra regressions are valid and complete at
  `/home/clawd/research/scion-experiments/v04-warehouse-v3-minimal-terra-1r-20260808T132138Z-claw/campaign`
  and
  `/home/clawd/research/scion-experiments/v04-cvrp-v3-minimal-terra-1r-20260808T132654Z-claw/campaign`;
  they completed 20/20 and 32/32 valid pairs respectively, with one
  replay-complete formal artifact and no candidate staging residue in each.

## Completion matrix

| Problem | Mandatory research-process claim | Mandatory scientific claim | Improvement claim |
|---|---|---|---|
| Warehouse | Fresh direct-v3 control completes at least two formal observations, makes a substantive problem-owned algorithm edit, and adapts direction from prior structured evidence without framework/gate noise. | The real solver and declared Protocol produce an attributable Warehouse mechanism or constraint result, even if negative. | Made only if an exact candidate receives independent validation support. |
| CVRP/VRP | Fresh multi-round control performs a substantive mechanism edit/refinement or pivot, excludes rejected ancestry, and is replayable from minimal lineage. | Allocation/activation evidence and independent Protocol support at least one useful or clearly negative mechanism conclusion. | Made only after independent validation. It is not required for a scientifically valid negative research-process result. |

Cross-problem completion additionally requires that both controls use the same
small V3 framework path and that neither depends on deployment or authority
machinery.

**Status: satisfied.**  The multi-round M5/M6 controls establish research
process and scientific validity; the final one-round controls establish that
the corrected smaller runtime still executes that same path on both problems.
Neither evidence set supports an improvement, validation, frozen-holdout,
deployment, packaging, or trust-system claim.

## Verification discipline

- Main development/test Python:
  `/home/clawd/miniconda3/envs/claw/bin/python`.
- Run focused affected tests first, then the relevant full suite, compileall,
  formatter, and `git diff --check`.
- Use fresh campaign roots.  Terminal historical roots remain read-only.
- Poll long experiments observationally at low frequency; polling cannot start
  another provider call.
- Preserve user-owned documents and unrelated worktree changes.
- The main session owns architecture, TASK/current-state, stage ordering, and
  final acceptance.  Subagents receive bounded implementation, test, review,
  or experiment-analysis tasks and may not expand scope.

## Pointers

- V3 authority: `scion/design/scion-architecture-v3.md`
- Direct-runtime interpretation:
  `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`
- Current state: `scion/docs/status/current-state.md`
- Current launch: `python -m scion.cli.main run`; arguments and control
  procedure: `scion/docs/operations/experiment-runbook.zh.md`
- Main research-effectiveness audit:
  `scion/reports/v04-v3-runtime-and-research-effectiveness-audit-20260712.md`
