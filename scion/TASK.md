# Scion v0.4 Solver-Improvement Research Task

*Working branch: `v0.4-dev`*

*Last updated: 2026-08-25*

## Authority and objective

[`design/scion-architecture-v3.md`](design/scion-architecture-v3.md) is the
sole Scion architecture authority. The direct-runtime addendum may narrow an
implementation example, but it cannot introduce another authority, identity or
proof lifecycle. Historical plans, experiment reports and Git history preserve
context; they do not create current work.

The active objective is retained solver improvement:

- Warehouse is complete: one uninterrupted synthetic campaign reached
  `v1 -> v2 -> v3`, the two promotion steps and cumulative gain survived the
  declared held-out replay, and production-style Warehouse promoted and retained
  `v1 -> v2`.
- CVRP is incomplete: no exact candidate has yet completed screening,
  validation and frozen holdout, received deterministic `PROMOTE`, and then
  independently retained an improvement over B0 without feasibility or fleet
  regression. Scion has produced testable CVRP hypotheses, patches and several
  complete initial or expanded development screens, but it has not yet
  demonstrated effective CVRP research under that acceptance standard: no
  autonomous candidate has completed and survived the held-out funnel, recent
  qualification attempts have not produced a new candidate eligible to
  enter it, and too much proposal budget is still spent on repeated, rejected
  or unfinalized directions per formal candidate.

A valid negative experiment is scientific evidence, not task completion.

## Scion boundary

The active research path is:

```text
complete safe problem facts + complete current branch source
+ explicit safe prior evidence
  -> optional finite Hypothesis research actions, or the direct one-shot path
  -> at most one tainted structured H
  -> structural Hypothesis Contract
  -> optional finite Code research actions bound to that exact approved H,
     or the direct one-shot path
  -> at most one tainted structured C
  -> structural Patch Contract
  -> isolated Workspace
  -> executable Verification
  -> problem-owned paired Protocol
  -> Safe Features
  -> deterministic Decision
  -> exact stage reuse, branch iteration, or promotion
```

A bounded Creative session may use several deliberate provider turns, all
charged to the declared shared provider/resource envelope. These turns are
internal Creative-Layer research actions, not provider retries. One branch
attempt exports at most one H and, only after Hypothesis Contract approval, at
most one C. A provider turn without a terminal response stops the session; an
exported, rejected, finalized, abandoned or abstained H/C is never repaired,
replayed, resumed or regenerated.

Creative drafts and `research_basis` remain tainted. Public-development
results, explicit research history and problem-owned mechanism-family
association are proposal context only. They cannot replace Contract or
Verification, alter a Protocol gate, enter Safe Features or Decision, or
select the next mechanism. The host may expose complete ordinary
source/history indexes and problem-owned association observations; it may not
rank, select or require a mechanism, surface, action, target file or patch.

The following are required:

- LLM output remains tainted and cannot author Protocol, Decision, scheduling or
  promotion.
- Contract owns schema, the same-attempt exact approved-H binding,
  editable/frozen paths, public
  interface, import/API and dangerous-capability boundaries. It does not grade
  novelty, style, mechanism taste, activation or expected quality.
- Verification owns executable correctness, feasibility, objective semantics,
  deterministic behavior and state isolation.
- Protocol owns fixed case/seed comparisons and statistical gates. Decision
  consumes typed Safe Features only.
- Branch, H, C, experiment and case identifiers are ordinary references. One
  transition function/transaction updates each mutable state boundary.
- Scientific lineage is a minimal append-only record linking H/C, base source,
  patch, Verification, declared stage inputs, raw metrics, Protocol and Decision.
- Exact source equality, fixed case/seed selection and exact stage reuse remain
  where scientific equivalence needs them. Direct byte equality is preferred;
  one content digest may compact the same comparison but confers no authority.
- Runtime isolation remains the V3 minimum: subprocess/workspace isolation,
  read-only scientific inputs, resource limits, clean environment, temporary
  directory isolation and cache cleanup.

The following are outside Scion and are deletion targets, not deferred work:

- object identities, owner tokens/registries, capabilities, durable leases,
  issuer/claim/spend protocols, registration and nonce ledgers;
- nested intent/commit/completion/closure graphs, activation/reopen/recovery
  proof, source acceptance and repeated absence proof;
- prompt/context/source identity, self-hashing manifests, receipt chains,
  formal-candidate identity, promotion dossiers and readiness closure;
- duplicate hashes, tree hashes, fixed-hash review gates or digests used to
  authorize, sign, lease, register, accept or attest an object;
- preauthorization/refreeze/sentinel/launch-ready state machines inside Scion;
- distribution, deployment, installation, packaging, reproducible-build work,
  root/systemd/D-Bus/cgroup/native-spawn infrastructure and H11 watch authority;
- provider retry, response repair, partial resume, top-k/truncation, forced
  mechanisms/surfaces/actions/targets, novelty gates and host-authored
  algorithm-quality gates.

Scientific `Frozen Holdout`, split manifests, seed ledgers, ordinary source
references, problem-owned operator registries, output-directory collision
protection and subprocess cleanup are not authority lifecycles and remain.
Explicit operator permission is an external action boundary; it must not be
reimplemented as a self-proving Scion object graph.

## Accepted evidence checkpoint

- Warehouse acceptance and its exact replay results are recorded in the
  [synthetic R8 postrun](docs/experiments/v0.4/v0.4-warehouse-v3-continuity-synthetic-36stage-r8-postrun-20260808.md),
  [synthetic held-out replay](docs/experiments/v0.4/v0.4-warehouse-v3-continuity-r8-heldout-replay-postrun-20260809.md),
  [production campaign](docs/experiments/v0.4/v0.4-warehouse-v3-production-transfer-prod12-24stage-r1-postrun-20260809.md)
  and [production held-out replay](docs/experiments/v0.4/v0.4-warehouse-prod12-independent-heldout-v1-postrun-20260809.md).
- CVRP R3 retained a complete positive quality screen but was interrupted during
  validation; it is valid partial science, not a promotion and not a resumable
  candidate. Later diagnostics and short runs remain in their experiment
  reports and the
  [longitudinal mechanism audit](docs/experiments/v0.4/v0.4-cvrp-longitudinal-mechanism-reopen-audit-20260815.md).
- R67 is terminal `PREP_INVALID / AUTHORIZED_PREFLIGHT_LIVE_CONTROL_ROOT_COLLISION / KNOWN_ZERO_BEFORE_SCIENTIFIC_DELEGATION`: solver, provider, Protocol and Decision observations are zero, the one-shot was consumed, and it supplies no candidate-quality evidence; see its
  [historical preregistration and terminal record](docs/experiments/v0.4/v0.4-cvrp-r67-provider-free-r3-cumulative-exact-source-full-funnel-confirmation-preregistration-20260815.md).

Detailed chronology belongs in experiment reports and Git history, not in this
prospective task.

## Ordered modules

Later modules begin only after the preceding module's acceptance evidence is
recorded. Each code module first resolves exact imports, callers, tests and
retained scientific evidence; obsolete code may then be deleted without a
compatibility layer.

### M0 - Normalize the active documentation boundary

- [x] Replace cumulative TASK/current-state experiment logs with prospective
  modules and a compact current-state resume point.
- [x] Reduce the latest one-shot preflight in active docs to its single terminal
  scientific fact while
  preserving the full historical experiment record unchanged.
- [x] Mark D2/D2b, fresh-activation, W3/H11, old runtime-identity and related
  fixed-hash plans superseded by V3 and this task.
- [x] Remove stale identity/ledger terminology from onboarding, reading profiles
  and the current runbook.

Acceptance: no default-read document presents self-proof lifecycle work as an
active, frozen or pending Scion requirement.

### M1 - Resolve reachable self-proof code

- [x] Classify every relevant source, schema, fixture and test as
  `KEEP_SCIENCE`, `DELETE_DEAD`, `REPLACE_REACHABLE` or `ARCHIVE_EVIDENCE`.
- [x] Trace production imports, composition, CLI entry points, callers and tests
  before each deletion. The classification is a temporary review aid, not a new
  manifest, registry or receipt system.
- [x] Preserve experiment outputs and scientific reports; do not preserve dead
  implementation merely because an old plan called it accepted.

Acceptance: every deletion target has a bounded module, known dependants and a
V3 replacement or proof that it is unreachable.

### M2 - Remove platform and activation infrastructure

- [x] Delete dormant root/systemd/cgroup/native-build/install/source-acceptance,
  D2 activation and W3/H11 authority code, schemas, fixtures, tests and exports.
- [x] Keep only ordinary local subprocess isolation, timeout/resource handling,
  environment cleanup and safe output-directory creation.
- [x] Add no compatibility shim, alternate backend or deployment investment.

Acceptance: production imports and CLI expose no platform/activation authority
path, while LocalSubprocessRunner behavior remains covered.

### M3 - Simplify mutable state and lineage

- [x] Delete authority tokens, capability graphs, lease/revision authorities,
  owner registries, issuer/claim/spend APIs and reopen/closure state.
- [x] Keep ordinary IDs, one in-process `CandidateWorkspace` value, one direct
  transition per mutable boundary and one minimal append-only scientific event
  path; no candidate-evaluation marker or durable candidate owner remains.
- [x] Keep summaries and status files as projections that cannot drive or reopen
  runtime state.

Acceptance: completed screening retains the verified provisional branch head;
Contract/Verification rejection returns to the clean source; Protocol and
Decision semantics are unchanged.

### M4 - Simplify proposal, source and candidate evidence

- [x] Remove prompt/context/source identity, owner maps used as authority,
  prompt manifests/hash receipts, duplicate digest reconciliation,
  formal-candidate recorder, promotion dossier and readiness closure.
- [x] Keep one validated ordinary source/history corpus and one immutable
  provider-visible projection per deliberate turn, plus the same-attempt exact
  approved-H binding, strict patch application and isolated candidate
  materialization.
- [x] Keep at most one optional terminal trace per deliberate provider turn as
  best-effort diagnostics; no public trace receipt or provider-call identity
  carrier remains, and trace failure cannot change a valid provider result.
- [x] Complete the minimal failure-only nondeterminism record: successful
  same-seed checks write no sidecar; a mismatch writes one bounded diagnostic;
  diagnostic write failure cannot change Verification.

Acceptance: the direct multi-file H/C path remains complete and source-bound,
with no second identity or receipt graph around it.

### M5 - Simplify experiment execution

- [x] Use the normal direct CLI, or a small fixed-candidate scientific driver
  when no H/C is part of the estimand.
- [x] Record ordinary source revision/worktree state, scientific config,
  cases/seeds/order/budgets, claim boundary, run status and terminal result.
- [x] Limit preflight to real prerequisites: config/schema, dependencies,
  permissions, input readability and non-overwriting output creation.
- [x] Delete reusable authorization manifests, refreeze steps, sentinels,
  whole-tree/code-receipt closures, live-root absence tests and control-root
  ownership proof.

Acceptance: an experiment can start once from a new output directory and write
a typed terminal without registering or certifying itself. `--check` is
read-only and cannot conflict with the launcher's own acquired state.

### M6 - Verify V3 behavior after subtraction

- [x] Run focused Contract, proposal, workspace, Verification, Protocol,
  Decision, branch-state, lineage and subprocess-isolation tests.
- [x] Delete tests whose sole assertion is obsolete identity/hash/receipt/
  closure topology; retain behavioral and scientific-boundary tests.
- [x] Run the full relevant suite, focused formatter/linter, compile/import
  checks and `git diff --check`.
- [x] Perform one offline reachability search for forbidden lifecycle modules;
  this is review evidence, not a runtime gate.

Acceptance: all V3 behavior remains green and no active import or default-read
document points back to the removed lifecycle.

### M7 - Resume the CVRP scientific task

- [x] Decide the next scientific rung only after M0-M6 close. M7-FC1 is a new
  fixed-candidate comparison; the terminal R67 preflight attempt is not fixed,
  retried, resumed or renamed.
- [x] Prepare a new ordinary experiment record that freezes only scientific
  inputs: exact source, comparator, cases, seeds, order, budgets, Protocol and
  claim boundary. The carrier is commit
  `cd1fcd7ad2a953c505c59ea339c2ff7d27af7fb3`; its read-only check and 19
  provider-/solver-free tests pass.
- [x] Run the existing V3 path without a self-proof launch bundle. The
  explicitly authorized M7-FC1 one-shot completed initial and expanded
  screening, then stopped fail-closed in validation with
  `CANDIDATE_SUBJECT_VETO` on candidate `X-n200-k36`, seed 2069. The one-shot is
  consumed: there is no repair, retry, resume or automatic next rung. This
  negative result is prior evidence for a later autonomous Scion research
  campaign, not a host-authored gate or VRP repair.

CVRP acceptance remains:

- one exact candidate completes all declared pairs without feasibility, fleet,
  candidate-runtime or champion-runtime failure;
- the declared Protocol passes screening, validation and frozen without
  outcome-adaptive threshold, case, seed or budget changes;
- deterministic Decision promotes to champion v2 or later;
- an independent final comparison against original B0 confirms retained
  distance improvement and states its exact population scope.

### M8 - Add problem-neutral research-evidence continuity

- [x] Add one optional ordered ordinary prior-research input to the normal
  `scion run` path. Record it once; do not create an identity, registry,
  receipt, hash chain, reopen or authorization lifecycle around it.
- [x] Let an optional problem-adapter provider project domain-shaped evidence
  into a bounded safe H context. Generic Scion code must contain no CVRP,
  Warehouse, route, fleet, case-specific or repair-specific fields or branches.
- [x] Keep Agent ownership complete: the host does not force action, surface,
  target file, mechanism, patch or fix. C sees the same Contract-approved H
  value and editable source, not the raw prior observation.
- [x] Derive any within-campaign research observations from the existing typed
  step/outcome path. Do not restore a special rejection-feedback ledger or
  duplicated branch evidence state.
- [x] Prove with provider-/solver-free tests that evidence is exposed once to H,
  private/current holdout facts do not leak, rejected candidates leave the
  verified source clean, and differently shaped or absent problem evidence uses
  the same core path.

Acceptance: Scion can transport problem-owned prior research evidence into the
normal V3 research loop without learning domain semantics or constraining the
Agent's proposal.

The exact design and claim boundary are in the
[autonomous prior-evidence research design](docs/experiments/v0.4/v04-scion-autonomous-prior-evidence-research-design-20260817.md).

### M9 - Run an autonomous CVRP research-effectiveness campaign

- [x] Add problem-neutral invocation limits to normal `scion run`: one shared
  H/C provider-call cap and one outer hardwall. Cap exhaustion and hardwall
  expiry are typed terminal outcomes; configured limits are written once as an
  ordinary run input, without a registry, receipt, hash or reopen lifecycle.
- [x] Prepare a fresh normal `scion run` input that supplies the safe M7-FC1
  terminal facts through the CVRP adapter, while specifying no patch, target
  file, action, surface, repair or algorithm mechanism.
- [x] Freeze one new development population whose screening, reserved
  validation and reserved frozen cases/seeds are disjoint from every M7 fact
  exposed to H, the R67 plan and current package inputs.
- [x] Invoke the reviewed M9 carrier once under explicit authorization. The
  normal CLI stopped before `mgr.run` because `ExperimentProtocol` created
  `metrics/` before the fresh-output check, so the one-shot produced no H/C or
  scientific observation and is consumed.
- [x] Correct the problem-neutral CLI initialization order so Protocol
  construction cannot create `metrics/` before the fresh-output check. The
  strict check is unchanged; absent, existing-empty and existing-nonempty
  roots, direct Protocol metrics creation and provider-zero rejection are
  covered offline.
- [x] Commit and independently verify the clean fix carrier, then execute the
  single rerun explicitly authorized by the user on the fresh `rerun1` root
  under the unchanged M9 scientific/resource/stop/claim envelope. Any fix or
  preflight failure stops; no third attempt is authorized.
- **SUPERSEDED BY LATER POPULATION-SPECIFIC PREREGISTRATION:** the M9
  future-population placeholder is no longer a live task or authority.
  M17-M25 and M30 used their own reviewed fresh/frozen or outcome-blind rules;
  M26-M28 deliberately reused outcome-exposed development banks under
  separately frozen seen-bank claim boundaries. Every later formal population
  remains governed by its own reviewed rule, resource envelope and explicit
  authorization; no M9 population authority remains live.
- [x] Run real H and C, current Contract and Verification, problem Protocol,
  Safe Features and deterministic Decision. Provider retry, repair and hidden
  host steering remain zero.
- [x] Assess separately whether the framework behaved correctly, whether the
  Agent used the evidence to conduct grounded research, and whether the solver
  actually improved.

Acceptance: at least one fresh autonomous attempt reaches a typed outcome with
the complete V3 decision chain and enough ordinary lineage to reconstruct what
H saw, proposed and changed. Promotion is not assumed; a valid rejection or
non-promotion remains evidence about Scion's research effectiveness.

Live provider/solver execution requires a separate explicit one-shot
authorization after the exact input, populations, budgets, stop conditions and
claim boundary are prepared.

### M10 - Test continuous cross-campaign CVRP research

- [x] Correct pair-local Protocol failure attribution so a shared or bilateral
  runtime incident is not flattened into a candidate-only failure.
- [x] Expose safe current-campaign Contract and Verification rejections to the
  next H without paths, raw detail, identities or host repair instructions.
- [x] Add a finite C research session with source read/search, typed revision,
  sandboxed public development tests, retest and independent finalize/abandon.
- [x] Add explicit H-only cross-campaign `research_history.jsonl` carrying
  ordinary H, patch, rejection, screening Protocol and Decision values; do not
  discover or read old summary/database state at runtime.
- [x] Select C context from the current target, transitive local dependencies,
  callers and public tests; keep peers inventoried and problem runtime/support
  host-only, with no CVRP/Warehouse branches in generic core.
- [x] Prepare one bounded longitudinal CVRP development continuation from the
  two M9 history records. Reuse the outcome-known M9 screen only to measure
  repair continuity; reserve all unseen/generalization claims for a later rung.
- [x] Commit and independently verify the clean M10 carrier, then require one
  explicit authorization naming the exact carrier and complete one-shot
  envelope before any provider or solver execution.
- [x] Run the one-shot M10 carrier. It consumed all 18 provider calls across
  five H/C attempts, produced four code-research rejections and one typed
  resource stop, and reached zero formal candidates or solver calls. Classify
  this as negative framework-continuity evidence, not algorithm evidence.
- [x] Classify framework
  continuity, research effectiveness and algorithm evidence separately.

Acceptance: a current candidate uses explicit prior history and the bounded
code-research loop, reruns formal Contract and Verification, and reaches a
typed Protocol/Decision outcome. Failure remains a valid negative result;
development repair never becomes an unseen-population improvement claim.

The exact design, resource arithmetic and stopping boundary are in the
[M10 preregistration](docs/experiments/v0.4/v04-cvrp-m10-continuous-research-m9-history-development-preregistration-20260820.md).

### M11 - Make bounded C failures actionable and continue once

- [x] Convert invalid patch drafts into bounded correction observations rather
  than aborting the C session; retain strict source and patch bounds.
- [x] Return only host-enumerated development failure reasons and already-public
  test paths; continue to exclude child stdout, stderr and traceback.
- [x] Count actual provider-wire transcript bytes without adding trace-only
  structured metadata a second time.
- [x] Mechanically project the five M10 attempts, including the two D4 failures
  and their draft source, into ordinary H-only research history.
- [x] Execute one fresh two-stage development continuation under provider cap
  30, solver cap 64 and a 13,500-second outer hardwall. It terminated at the
  provider cap after three C rejections and reached zero formal candidates.
- [x] Diagnose the repeated D4 result: the public development scratch omitted
  two frozen package markers, so `policies` became a namespace package and the
  test failed before candidate execution. Both retained M11 drafts pass D1-D4
  after the problem-owned closure correction.

Acceptance: at least one bounded C candidate reaches current Patch Contract,
Verification, screening Protocol, Safe Features and Decision. Development
failure remains a valid negative result and cannot become a generalization
claim.

The exact design is in the
[M11 preregistration](docs/experiments/v0.4/v04-cvrp-m11-actionable-code-research-continuation-preregistration-20260820.md).

### M12 - Continue once with the corrected public closure

- [x] Declare the frozen CVRP package markers as read-only development
  workspace support; do not change generic core or CVRP algorithm source.
- [x] Copy the three-record M11 terminal history as an ordinary H-only input.
- [x] Execute one fresh continuation with the same population, provider cap 30,
  solver cap 64 and 13,500-second hardwall. The third autonomous candidate
  completed Verification, canary and all 12 screening pairs, but terminal
  history persistence rejected the canonical `seed_pattern` aggregate and the
  run stopped as an unhandled framework exception before the StepRecord and
  typed execution outcome were durably recorded. The ordinary experiment event
  does retain `continue_explore` and its two reason codes. M12 is terminal and
  is not retried.

Acceptance remains one current candidate reaching formal Patch Contract,
Verification, screening Protocol, Safe Features and Decision. Replaying a
draft through development checks alone is not positive evidence.

The exact design is in the
[M12 preregistration](docs/experiments/v0.4/v04-cvrp-m12-corrected-development-closure-continuation-preregistration-20260820.md).

### M13 - Close on solver evidence

- [x] Correct the generic history boundary so canonical screening
  `seed_pattern`/`seed_consistency` aggregates persist without permitting raw
  seed values in open problem evidence.
- [x] Remove the redundant mandatory `ready` turn: a latest unchanged draft
  whose bounded public development checks passed is eligible for the separate
  finalize/abandon decision; any later revision clears that eligibility.
- [x] Prepare and execute one fresh bounded continuation that imports the M12
  attempts and complete screening result as ordinary H-only history. Do not
  reuse the M12 output root or reinterpret its framework exception as a valid
  completed run. M13 completed validly with two evaluated screening candidates,
  two durable history records and no candidate-only runtime failures. Both
  gates failed case quality; the second mechanism was mixed rather than
  uniformly negative.
- [x] Continue in one independently frozen M14 campaign using the two native
  M13 history records. M14 completed validly with two typed C rejections and
  two evaluated candidates. The second candidate exposed a missing public
  customer-conservation invariant and was correctly abandoned after two
  candidate-only X195 runtime failures; no M13/M14 root was reused and the
  host selected no mechanism or patch.
- [x] Continue in one independently frozen M15 campaign using the four native
  M14 history records and the new problem-owned customer-conservation test.
  Two candidates passed every development/formal gate; the first reached
  `SCREENING_EXPAND_INITIAL_QUALITY` with two wins and no losses, while the
  second refinement was mixed. Shared X256 baseline failures kept Decision in
  exploration, so no expansion or later stage ran.
- [x] Continue in one independently frozen M16 campaign using the two native
  M15 records. Both autonomous candidates passed current development and
  formal gates. The second exact directed `_or_opt` delta produced two case
  wins, zero losses and three ties with CI `[0, 244]` and
  `SCREENING_EXPAND_INITIAL_QUALITY`; two shared X256 failures kept Decision in
  exploration, so no later stage ran.
- [x] Confirm the strongest autonomous positive candidate on one freshly
  selected outcome-blind population before any further adaptive H/C campaign.
  Treat this as fixed-candidate confirmation: no new provider call, patch or
  repair, and no promotion claim unless the newly declared Protocol completes.
  M17 stopped after its canary and before any formal pair because its equal
  initial/expanded case counts violated the Protocol shape. Preserve that root
  and use a new label for the mechanical shape correction; candidate,
  population, resources and claim boundary must remain unchanged. M18 is
  prepared with exactly that correction and an added solver-free preflight
  assertion for the strict expanded shape. M18 completed all 24 new-population
  pairs. The candidate had zero candidate-only failures and one case win, but
  four shared construction failures left only 20 valid pairs; the quality gate
  failed and measured runtime was effectively unchanged. The fixed candidate
  is therefore not confirmed, and no validation, frozen or promotion claim is
  available.
- [x] Feed the ordinary M18 confirmation observation into a new autonomous
  campaign through the CVRP problem adapter, without adding CVRP semantics to
  generic Scion. Use a fresh development population and let H choose whether
  to address construction completeness, refine local search or pivot; do not
  host-select a target, patch or repair mechanism. M19 is prepared with both
  the M18 problem-owned observation and M16's two native history records, a
  metadata-selected fresh development split, two evaluated-stage maximum and
  the unchanged bounded code-research chain. M19 completed validly: both
  candidates passed all gates and produced three wins, zero losses and two
  ties on the fresh screen, with only shared X429 construction failures. But
  the two byte-distinct patches were semantically equivalent `_or_opt`
  implementations, so the run also exposes inadequate research-frontier
  novelty after a current-campaign result.
- [x] Add one problem-neutral H frontier instruction: current-campaign
  experiment evidence is an already evaluated mechanism, so a repeated target
  must identify a materially new algorithmic delta or H should pivot. Do not
  ban same-file refinement, score novelty with a second model, or encode a CVRP
  target. Validate the change on a new fresh development population.
  The generic instruction and prompt-boundary tests are implemented in
  `06aefa81`. M20's first H made a real `_or_opt` -> `_swap` mechanism advance;
  its candidate passed all gates and produced three wins, zero losses and three
  ties on a 12/12-valid fresh screen. Expanded confirmation did not run because
  the config declared equal initial/expanded case counts. Preserve the terminal
  root and reject this shape before provider/solver work in every future
  multi-round normal run.
- [x] Continue from M20's native ordinary history on a new fresh population
  whose initial screen is a strict subset of its expanded screen. Allow two
  evaluated stages: either initial -> expanded for the same branch, or a second
  autonomous H after a terminal initial result. Host selects no mechanism,
  target or patch; no validation/frozen/promotion claim follows from this
  development continuation.
  M21 ran from the generic preflight fix and exact M20 history. One candidate
  completed a 6/6-valid all-tie initial screen; the next H pivoted to
  deadline-based annealing but its C session stopped on an upstream 504 after
  a valid draft revision. No expansion or later stage ran.
- [x] Continue from M21's three native records under a new label and fresh
  population. Preserve the strict nested expansion shape and the no-retry
  provider boundary. Treat invalid C draft feedback as tool-usability evidence,
  not algorithm evidence; host still selects no mechanism, target or patch.
  M22 completed validly with one typed C rejection and two 6/6-valid formal
  initial screens. The construction-portfolio candidate tied every case; the
  2-for-2 exchange candidate tied two cases and lost one by 10 distance units.
  Both gates failed case quality, so expanded and later stages remained zero.
  M21's provider request was neither resumed nor retried.

### M23 - Freeze bounded research and resume solver evidence

- [x] Freeze optional bounded H and C research sessions: finite internal
  actions, at most one exported tainted H and one exported tainted C per
  attempt, with every provider turn charged to the shared resource envelope.
- [x] Keep explicit ordered `research_history.jsonl` as H-only ordinary
  evidence. Exclude validation, frozen/holdout, private/raw state and automatic
  campaign discovery or reopen.
- [x] Expose complete ordinary source/history indexes to H with bounded
  read/search, dependency/caller and declared public-test organization, and a
  required tainted `research_basis`. Do not add a host mechanism ranker.
- [x] Keep CVRP mechanism-family observations problem-owned,
  association-only and available only from complete paired observations. They
  are not exact activation, causal proof, a Protocol gate or Decision input.
- [x] Consolidate provider-free fixed-candidate evaluation into one funnel with
  private read-only source snapshots and the existing
  Protocol -> Safe Features -> Decision chain. Distinguish candidate-negative
  evidence from comparator-incomplete evidence at canary, every formal stage
  and retained comparison.
- [x] Complete focused provider-/solver-free regression and independent review.
  Do no distribution, packaging, build, deployment, root/systemd or Trust/Hash
  lifecycle work.
- [x] **COMPLETED / NOT_CONFIRMED:** run one ordinary provider-free full-funnel
  confirmation of the preserved M20 candidate on the frozen outcome-unseen
  population in the
  [M23 preregistration](docs/experiments/v0.4/v04-cvrp-m23-m20-swap-provider-free-full-funnel-preregistration-20260821.md).
  Canary passed and expanded screening completed 24/24 valid pairs with zero
  failures, two wins, four ties and no losses. Median delta `0.0` and CI
  `[0.0, 66.75]` left the aggregate gate `unclear`; Decision returned
  `continue_explore`, so validation, frozen, promotion and retained remained
  zero. No provider call, replacement candidate, repair, retry or resume path
  was created.
- [x] **TERMINAL / RESOURCE_EXHAUSTED:** run one serial bounded autonomous
  campaign in which H performs the direction research and the host supplies
  only ordinary source/history access, resource limits and the V3 gates. M24
  stopped at 34/34 provider calls after nine H drafts all failed the same
  unread-nearest-history basis check; no valid H, C, Contract, Verification,
  solver or formal Protocol stage was reached. This is a bounded H-feedback
  failure and supplies zero algorithm evidence. The exact population, resource
  boundary and terminal record are preserved in the
  [M24 preregistration](docs/experiments/v0.4/v04-cvrp-m24-autonomous-direction-research-development-preregistration-20260821.md).
- [x] Make invalid H-finalization evidence binding a bounded, enumerated
  in-session observation, constrain finalize-basis ref enums to refs actually
  read, and validate the repair without a provider or solver before designing
  another autonomous experiment. Finalize now requires current-source and
  history reads when those corpora are available, a cited nearest prior and an
  explicit falsification condition. Recognized invalid finalize feedback is
  fixed-enum and same-campaign rejection memory is bounded; local/global
  resource caps remain hard stops. Provider-/solver-free real-context replay
  and independent review passed.
- [x] **TERMINAL / COMPLETED VALID / SCREENING ABANDON:** execute the M25
  evidence-grounded autonomous continuous-research one-shot on the
  carried-forward unopened M24 population. H read current source and ordinary
  history and finalized in three provider calls; C publicly tested and
  finalized the aligned directed intra-route 2-opt delta patch in four. The
  unchanged gates passed Contract, Verification and canary. Initial screening
  completed 6/6 valid pairs and expanded. Exact-branch expanded screening
  attempted 12/12 pairs, completed 11 valid pairs and recorded one
  candidate-only timeout; Protocol failed case quality and Decision abandoned
  for `CANDIDATE_RUNTIME_FAILURE`. Total use was seven provider calls, 42
  serial solver subprocesses and about 1,458 seconds. Validation, frozen,
  promotion and retained remained zero. The framework result is positive, the
  research direction was grounded and testable, and the exact algorithm result
  is negative/mixed development evidence. See the
  [M25 preregistration and terminal result](docs/experiments/v0.4/v04-cvrp-m25-evidence-grounded-autonomous-continuous-research-preregistration-20260821.md).
- [x] **TERMINAL / COMPLETED VALID / TWO NEGATIVE INITIAL SCREENS:** execute
  M26 once on M25's outcome-exposed development bank. Fifteen provider calls
  comprised seven H turns, six C turns and two independent C final decisions.
  Both candidates passed Contract, Verification and canary and completed 6/6
  valid formal pairs, but each lost one of three cases: case win/loss/tie
  `0/1/2`, with pair counts
  `1/1/4` and `0/2/4`, median delta `0.0`, and CIs `[-61.5, 0.0]` and
  `[-90.5, 0.0]`. Both Protocol results were
  `fail / SCREENING_FAIL_CASE_QUALITY`; both Decisions continued exploration.
  The two ordered C-authored probes were fully observed: 3,272 characters
  projected `failed`, then 326 projected `passed`, while ordinary host checks
  passed 5/5 both times and each session went directly to ready without a
  post-probe revision. This establishes adoption and bounded framework
  execution, not a causal probe effect. H1 reimplemented historical work; H2
  read same-campaign `history-0041` and pivoted, but reproduced unread failed
  `history-0034` byte for byte. Exactly 32 serial solver subprocesses ran; no
  expansion, validation, frozen, promotion or retained stage ran. The root is
  preserved and consumed without retry, resume or automatic M27. See the
  [M26 preregistration and terminal result](docs/experiments/v0.4/v04-cvrp-m26-embedded-falsifier-autonomous-continuation-preregistration-20260821.md).
- [x] Add a problem-neutral nearest-history audit to bounded H finalization.
  For each otherwise valid candidate, a pure headline-only ranker scans the
  complete current index and routes the lexical top-1 among usable headline-
  bearing ordinary refs. H must read it and cite
  it in both basis arrays; a candidate change recomputes the ref. The fixed
  feedback contains only the required ref, not candidate/match text or a score.
  Preemptive exact-ref reads remain valid. The ranker does not judge novelty,
  choose a mechanism/target/patch or reach C, Contract, Protocol or Decision.
  Direct-H behavior without research limits is unchanged.
- [x] **TERMINAL / COMPLETED VALID / EXPANDED SCREENING ABANDON:** execute M27
  once on the M25/M26 outcome-exposed development bank. One accepted H used
  four turns over the 43-entry index: source read, audit trigger for
  `history-0030`, required history read, then acceptance with that ref cited in
  both basis arrays. Coverage was accepted 1/1 and incomplete zero; the read
  was not preemptive. The candidate changed after the trigger but retained the
  same top-1. Its self-described pivot/refinement label was `not_observable`,
  and exact structured-H and complete ordered-patch replay counts were both
  zero. C used `revise -> test_patch -> ready -> finalize_patch`; its
  1,199-character falsifier projected `passed`, all 5/5 host checks passed and
  no post-probe revision occurred. Eight provider calls and 42 serial solver subprocesses
  completed initial 6/6 screening and an expanded screen with 10/12 valid pairs
  plus two candidate-only timeouts. Initial evidence expanded; expanded
  Protocol failed case quality and Decision abandoned for runtime failure.
  Validation and frozen remained zero. The preserved root is consumed without
  retry, resume or automatic M28. Audit/probe observations are non-causal, and
  the result is negative/mixed evidence only on the seen bank. See the
  [M27 preregistration and terminal result](docs/experiments/v0.4/v04-cvrp-m27-nearest-history-audit-autonomous-continuation-preregistration-20260821.md).
- [x] **TERMINAL / STOPPED RESOURCE_EXHAUSTED / VALID_INCOMPLETE / NOT
  QUALIFIED:** execute M28 exactly once under its frozen seen-bank
  [preregistration](docs/experiments/v0.4/v04-cvrp-m28-seen-bank-qualification-autonomous-continuation-preregistration-20260824.md).
  The invocation exited 21 at 34/34 provider calls: 25 H turns, eight C
  research turns and one C final decision. Four attempts yielded one evaluated
  screening, two research rejections and a final
  `PROVIDER_CALL_CAP_EXHAUSTED` at `proposal_code`; only one of two requested
  formal rounds completed. The sole evaluated candidate passed Contract,
  Verification and canary and completed initial screening `6/6` valid with
  zero failures, but case win/loss/tie `1/1/1`, median delta `0.0` and CI
  `[-2.5, 206.0]` failed case quality; Decision continued exploration. A later
  C ended `PATCH_PROPOSAL_INVALID`, and the last accepted H reached the shared
  cap before C dispatch. The terminal counters contain two research
  rejections, while the three ordinary steps/history rows durably contain only
  one rejected row; the missing H-abstention reason is a live safe-public
  observation, not terminal-only reconstruction. Exactly 16 solver
  subprocesses ran serially: two Verification, two canary and twelve formal;
  observed concurrency was one. Expanded screening, validation, frozen,
  promotion and retained comparison were zero, and no branch was
  `READY_VALIDATE`. The frozen carrier audit's assertion that total branch
  records must equal active branches and both equal one is a P1 structural
  false-negative defect, but it did not affect this nonqualification: the
  scientific predicate had already failed and no eligible carrier existed.
  The conditional M29 selector expired unmaterialized; there is no M29 prep,
  launch, retry or resume authority.
- [x] Repair the M28 postrun-carrier false-negative and provider-safe null-H
  durability boundaries, then add a bounded qualification-only campaign mode.
  The reviewed runtime now counts EXPLORE H/C proposal attempts, distinct
  Verification-passing chains and initial/expanded screening stages
  independently; legal cap exhaustion is a completed valid negative, while
  infra/resource/hardwall terminals remain incomplete. Nonqualifying verified
  chains are durably recorded before their mutable workspace/H/patch/hash is
  cleared and the lineage is parked; a positive branch stops before validation
  as `ready_for_postrun_qualification_audit`, not as already qualified.
- [x] Freeze M30 as the next CVRP
  qualification attempt on a metadata-selected fresh-at-start development
  bank. Its first H receives eight ordinary observations plus 42 native history
  rows; six H/C proposal attempts, two verified chains, four screening stages,
  60 provider calls and a 28,000-second hardwall are independent explicit
  limits. The runtime/source base is exact
  `5d282ea8e9133e0146c47588f2310c9bd2493e50`. A tracked strict expectation JSON
  supplies M30 facts to the sole public, problem-neutral postrun auditor; only
  its exact `QUALIFIED_FOR_NEW_FIXED_CANDIDATE_FUNNEL` token after terminal
  boundary, scientific join and B0/full-byte carrier checks can unlock a
  successor. The exact selector, controls, resource arithmetic, three-layer
  claim boundary and mechanical prelaunch/postrun commands are preserved in the
  [M30 preregistration](docs/experiments/v0.4/v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-preregistration-20260824.md).
  M31 exists only as a conditional outcome-blind rule and count-only
  feasibility proof; no M31 case/seed identity is materialized.
- [x] **TERMINAL / STOPPED RESOURCE_EXHAUSTED / VALID_INCOMPLETE / NOT
  QUALIFIED:** execute M30 exactly once from its frozen carrier. It used three
  proposal attempts, one Verification-passing chain and one formal initial
  screen. The sole candidate passed Contract, Verification and canary and
  completed `6/6` valid initial pairs with zero failed-pair classes, but case
  win/loss/tie `0/2/1`, pair win/loss/tie `1/3/2`, median delta `-5.5` and CI
  `[-6.5, 0.0]` failed case quality; Decision continued exploration and
  qualification-only parking
  removed its executable branch authority. The second H abstained, and the
  third stopped at its eight-turn H-session cap as
  `HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED`. The invocation exited `21` after
  25/60 provider calls and 16 serial solver subprocesses; expanded screening,
  validation, frozen, promotion and retained comparison were all zero. The
  frozen postrun auditor returned `QUALIFICATION_CARRIER_UNAVAILABLE`, so the
  conditional M31 rule expired without identity, preparation, launch, retry or
  resume authority. A post-terminal monitoring mistake opened SQLite in
  readonly mode; the only observed metadata change was to `scion.db-shm` after
  the frozen audit. Cached metadata showed no post-terminal mtime change to the
  main database or WAL, and the scientific JSON/JSONL/metrics were untouched.
  No database hash was taken, and nothing was repaired or rerun.

Acceptance: an enabled attempt may spend finite Creative turns but exports at
most one H and one C. Contract, Verification, Protocol, Safe Features and
Decision retain their existing authority. History and family association may
inform a later H without host mechanism selection or Decision influence.
At canary or a main-chain formal stage, comparator-incomplete evidence never
advances and never reaches Decision. After a complete frozen-stage promotion,
retained comparator incompleteness terminates
`completed_incomplete / INCOMPLETE_COMPARATOR_EVIDENCE` at
`stop_stage=retained`; it is not sent to Decision and is never reported as
`PROMOTED_NOT_RETAINED`.

### M32 - Improve CVRP proposal research effectiveness before another qualification

The next CVRP task is not another qualification run and not a broad multi-agent
rewrite. M10-M30 show that the deterministic Contract, Verification, Protocol,
Decision and evidence boundaries can execute and fail closed, while autonomous
proposal research still yields too few distinct, implementable formal
candidates per provider call. M32 therefore improves the tainted Creative
research boundary first and leaves every downstream scientific authority
unchanged.

The provider-/solver-free metric contract, M30 calibration row, future
five-block matched-study gate, freshness rule and claim boundary are frozen in
the [M32 design](docs/experiments/v0.4/v04-cvrp-m32-hypothesis-candidate-bank-research-effectiveness-design-20260825.md).
The default-off K=2 implementation, count-only attempt telemetry and pure
single-arm offline scorer now exist, but no population selection, matched-study
result or live authority exists. Carrier `25b78037` implements the private
ordinal K=2 H bank under the existing shared session budget and exports only
the provider-selected H. Carrier `b0d81ddb` adds body-free attempt lifecycle,
provider-delta and H/C boundary counts. Carrier `bda346e9` adds a pure
provider-/solver-free single-arm scorer that closes current-history, replay,
formal-quality and paired-effect accounting without emitting H, patch, path,
identity or hash material. These are implementation and synthetic-audit
results, not evidence that K=2 improves CVRP research.

- [x] Close the M30 terminal documentation and monitoring-incident record on a
  clean docs-only commit before changing research behavior. Preserve the M30
  root as consumed; do not retry, resume or reinterpret its incomplete result.
- [x] Correct proposal telemetry so bounded H/C research is not reported as
  `direct_v3`, and durably project safe attempt-level provider-turn,
  H-candidate and selected-candidate counts without exposing draft bodies.
- [x] Freeze baseline research-throughput and candidate-quality measures before
  implementation:
  finalized H per provider call, history- and within-arm-exact-distinct H per
  attempt, C-ready rate, exact-distinct formal candidate per attempt/provider
  call, separate loaded-history/within-block/cross-block exact H/patch replay
  guards, initial gate/expand rate, the median-of-candidate-medians
  paired-effect guard and candidate-only runtime-failure rate. The exact
  throughput and quality endpoints and their repeated-block acceptance rule
  must be fixed before outcomes. These are development diagnostics, never
  promotion features or Decision inputs.
- [x] Add bounded session-local H candidate slots and safe counters without a
  new durable ledger, identity, hash, receipt or authority. All slots share the
  existing turn/read/search/transcript and campaign provider budgets; creating
  a second slot may not reset or multiply any allowance. Public artifacts may
  expose only bounded counts and the single exported H.
- [x] Complete the strict optional configuration contract
  `max_hypothesis_candidates`. Missing or explicit `1` preserves the bounded
  K=1 path; within qualification-only composition with its bounded
  proposal-attempt limit and explicit shared provider-call and outer hardwall
  caps, explicit `2` enables K=2 and remains the hard maximum; every other value
  fails closed.
- [x] Implement the `K=2` H draft bank inside one
  `HypothesisResearchSession`. The provider may stage two complete structured H
  values in session-local ordinal slots and either choose one existing slot or
  abstain. Only a chosen slot can export H. The host may validate structure and
  exact slot equality but may not rank
  mechanisms, targets or expected quality. Only the chosen H is exported to
  formal Hypothesis Contract. Every unselected staged H, including both slots
  after an abstention, disappears with the tainted session and never enters
  StepRecord, lineage, research history, workspace or candidate authority.
- [x] Add provider-/solver-free red-team coverage for shared-budget accounting,
  slot immutability, deterministic ordering, unchosen-draft non-persistence,
  transport/resource interruption and zero validation/frozen leakage. Defaults
  must preserve the current direct and bounded paths byte-for-byte where their
  public schema is unchanged.
- [x] Implement a pure single-arm postrun scorer that joins terminal status,
  summary, normalized current history, explicit loaded-history availability,
  count-only attempt telemetry and ordinal-only initial cells. It must keep
  physical counts separate from replay-adjusted `D_H/F/G/T/Q/E`, preserve the
  M30 incomplete/history-unavailable calibration boundary, and emit no
  hypothesis, patch, path, identity, hash, case or seed material.
- [ ] Implement and independently red-team the pure offline exact-five-block
  matched comparator. It must call the same single-arm oracle for all ten arms,
  compute the five frozen joint signs plus cross-block H/pair replay and `U_F`
  inside one private in-memory boundary, and return only aggregate counts,
  ratios, signs and fixed availability codes. It creates no GO token, command,
  population or launch authority.
- [ ] Preregister repeated matched `K=1` versus `K=2` development comparisons
  under the same total provider, attempt, solver and hardwall envelopes. Use
  outcome-blind ordinary development populations and hold the current
  cross-attempt feedback behavior constant. K=2 advances only after repeated
  matched blocks improve distinct formal-candidate yield per unit budget and
  meet the predeclared candidate-quality rule without increasing replay or
  candidate-only failure. One favorable candidate or throughput uplift alone
  is not an advance and cannot produce a validation, generalization or CVRP
  acceptance claim.

Acceptance: the minimal successful M32 result is a provider-/solver-free
audited, default-off K=2 H session plus repeated preregistered matched-control
development evidence under the same total resource envelope as K=1 that
improves both distinct formal-candidate yield per provider call and the frozen
development-quality endpoint without hidden host selection, draft persistence
or held-out leakage. Throughput-only uplift is research-throughput evidence,
not effective-research evidence. A completed valid comparison without
repeatable joint uplift is a valid negative and blocks the next architectural
rung; an incomplete comparison is inconclusive and also cannot advance. A
repeated joint uplift is bounded development research-effectiveness evidence
only.
CVRP acceptance still requires a later exact autonomous candidate to complete
screening, validation and frozen holdout, receive deterministic `PROMOTE`, and
survive an independent retained-B0 comparison without feasibility or fleet
regression.

### Conditional CVRP research path after M32

These are later conditional modules, not M32 completion tasks and not current
launch authority:

- **M33 - Cross-attempt typed reflection:** only after M32 passes, replace the
  provider-authored C abandonment prose available to later H with a small
  closed set of hypothesis-level obstruction codes. The current attempt still
  terminates; the next H is a new attempt. Compare default-off reflection
  against the K=2 baseline in repeated matched blocks with the same resources,
  measuring obstruction recurrence, C-ready/formal yield and the same frozen
  quality endpoints. No same-attempt retry or repair is permitted.
- **M34 - One bounded same-attempt `H -> C -> H` edge:** consider only if M33
  improves both efficiency and quality and remaining failures are specifically
  attributable to H/C implementability mismatch rather than weak algorithms.
  First amend the architecture authority to distinguish provisional drafts
  from exported H/C, permit at most one typed revision request, discard the old
  C draft, rerun H binding from a clean snapshot and charge all H/C work to one
  cumulative budget. It may not be introduced as an internal retry loop.
- **M35 - Multi-agent role ablation:** consider researcher/critic/implementer
  roles only if M32, M33 and a controlled M34 experiment each demonstrate their
  preregistered joint benefit, yet their proposed candidates remain materially
  correlated. A failed or no-uplift earlier rung blocks M35. Every output
  remains tainted, no agent sees
  validation/frozen/held-out evidence, any Creative selector may choose only a
  session-local ordinal without rewriting its candidate, and Contract,
  Verification, Protocol, Safe Features and Decision remain deterministic host
  authorities.
- **M36 - New CVRP qualification:** prepare only after a prior rung demonstrates
  repeatable joint research-effectiveness uplift without budget multiplication
  or evidence leakage. It requires a new label, fresh outcome-blind selector,
  independent reviews and separate explicit one-shot authorization; M31 and
  all expired M29/M30 conditional authority remain unusable.

- [ ] Publish the final full regression record.
- [ ] Write one cross-problem report separating framework behavior,
  mechanism-level evidence, formal promotion and independent replay.
- [ ] Mark v0.4 complete only when both Warehouse and CVRP acceptance are
  satisfied.

## Working discipline

- Main Python: `/home/clawd/miniconda3/envs/claw/bin/python`.
- Model experiments, when separately authorized, use `gpt-5.6-terra` through
  the local Codex proxy with provider SDK retry zero.
- Do not change framework source while an experiment is running.
- Long scientific runs are serial and observationally monitored; polling never
  launches, retries or mutates a campaign.
- Preserve terminal experiment roots, scientific reports and unrelated user
  worktree changes.
- Subtraction modules are reviewed independently and land without distribution,
  deployment or build work.

## Status

M7-FC1 is terminal. The
`v04-cvrp-m7-fc1-r3-cumulative-new-population-full-funnel-20260816` one-shot
completed initial and expanded screening, then stopped in validation with
`CANDIDATE_SUBJECT_VETO` on candidate `X-n200-k36`, seed 2069. At termination it
had used 311 solver subprocesses and 15,225 nominal subject-seconds; no frozen,
promotion or retained-B0 stage ran. The complete design and terminal record are
preserved in its
[preregistration](docs/experiments/v0.4/v04-cvrp-m7-fc1-r3-cumulative-new-population-full-funnel-preregistration-20260816.md).
CVRP acceptance remains unmet. M8 is complete: normal `scion run` now accepts
one bounded ordinary `--research-input`; the problem adapter projects ordered
observations into H only, while C continues from the Contract-approved H and
editable source. Generic Scion contains no CVRP/Warehouse evidence schema, and
the input creates no registry, hash, receipt or reopen lifecycle. Normal runs
also accept explicit `--provider-call-cap` and `--outer-hardwall-sec`; the
problem-neutral implementation is commit `9ae49b21`. M9's ordinary
six-case/two-seed development screen, reserved later development splits,
provider/process envelope, one-stage stopping rule and three-layer claim
boundary are now frozen in its
[preregistration](docs/experiments/v0.4/v04-cvrp-m9-autonomous-m7-prior-development-screen-preregistration-20260817.md).
The authorized M9 invocation is terminal
`PRE_MGR_RUN_FRESH_OUTPUT_SELF_COLLISION / ONE_SHOT_CONSUMED`: CLI Protocol
construction created an empty `metrics/` directory before `CampaignManager`
checked output freshness, so the complete V3 chain never started. Provider
generation, solver, H/C, Contract, Verification, Protocol, Safe Features and
Decision observations are all zero. The future formal population remains
unselected and unavailable to the Agent. The generic initialization fix is now
implemented and validated offline without weakening the fresh-output boundary.
The user has explicitly authorized exactly one rerun after a clean fix carrier
passes independent checks. It must use a new `rerun1` root and the unchanged
M9 envelope; the original root remains preserved and no third attempt, later
development stage or formal rung is authorized.

That rerun is now terminal `completed / valid / requested_rounds_completed`.
Two autonomous candidates used four provider calls. The first passed Contract
but was rejected by Verification unit tests. The second passed Contract,
Verification and canary, then completed all 12 development-screen pairs.
Protocol returned `fail / SCREENING_FAIL_CASE_QUALITY`; Safe Features exposed
candidate runtime failures and Decision returned
`abandon / CANDIDATE_RUNTIME_FAILURE`. Champion remains v1; validation,
frozen, promotion and a third candidate are all zero. This demonstrates the
bounded autonomous V3 research chain, but the research result is negative/mixed
and supplies no algorithm-improvement or generalization claim.

M10-M27 then established continuous cross-campaign ordinary history, bounded H
and C research, an optional sandboxed C falsifier and several valid
negative/mixed CVRP screens. M25 reached an expanded screen but its exact
candidate had one candidate-only timeout and was abandoned. M26 completed two
valid initial screens; both failed case quality. Its first direction
reimplemented historical work, while its second used same-campaign evidence but
exactly replayed an unread failed prior patch. Validation, frozen, promotion and
retained evidence remain zero; the roots are preserved and consumed.

The generic nearest-history audit now scans every current ordinary index entry,
ranks only usable hypothesis headlines and requires the candidate-specific
top-1 ref to be read and cited before H acceptance. M27 exercised that path in
four H turns over a 43-entry inventory, then used the same accepted H and patch
for initial and expanded screening. Initial screening expanded, but two
candidate-only expanded-stage timeouts left 10/12 valid pairs; Protocol failed
case quality and Decision abandoned for runtime failure. The run is terminal
`completed / valid / requested_rounds_completed`, with validation and frozen
zero. Its audit and probe observations establish bounded framework behavior,
not causal research improvement; its paired result is negative/mixed seen-bank
development evidence.

M28 is now terminal `stopped / execution_resource_exhausted / valid_incomplete`
after its sole authorized invocation. It spent 34/34 provider calls and
completed only one of two formal rounds. The sole screened candidate completed
`6/6` valid initial pairs but failed case quality and returned to exploration;
later attempts ended one C rejection and then provider-cap exhaustion. No
expanded, validation, frozen, promotion or retained stage ran, and no branch
reached `READY_VALIDATE`. The candidate-independent M29 selector therefore
expired without materialization and supplies no launch authority. CVRP
acceptance remains unmet; the M28 root is preserved and consumed.

M30 is also terminal `stopped / execution_resource_exhausted /
valid_incomplete` after its sole authorized qualification-only invocation. It
used 25/60 provider calls across three proposal attempts but produced only one
verified formal candidate. That candidate completed a clean `6/6` initial
screen and failed case quality; no expanded or held-out stage ran. One later H
abstained and the final H exhausted its eight-turn session budget. The public
postrun audit returned `QUALIFICATION_CARRIER_UNAVAILABLE`, and M31 expired
without materialization. The result strengthens the framework accounting and
fail-closed evidence, but it does not establish effective CVRP research: Scion
has not yet produced an autonomous CVRP candidate that qualifies for, let
alone passes and survives, the validation/frozen/retained acceptance chain.
