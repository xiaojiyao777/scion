# Scion v0.4 Solver-Improvement Research Task

*Working branch: `v0.4-dev`*

*Last updated: 2026-08-17*

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
  regression.

A valid negative experiment is scientific evidence, not task completion.

## Scion boundary

The active research path is:

```text
complete safe problem facts + complete current branch source + prior safe evidence
  -> one structured Hypothesis call
  -> structural Hypothesis Contract
  -> one Code call using that same Contract-approved ordinary H value
  -> structural Patch Contract
  -> isolated Workspace
  -> executable Verification
  -> problem-owned paired Protocol
  -> Safe Features
  -> deterministic Decision
  -> exact stage reuse, branch iteration, or promotion
```

The following are required:

- LLM output remains tainted and cannot author Protocol, Decision, scheduling or
  promotion.
- Contract owns schema, the same-call H-to-C value boundary, editable/frozen paths, public
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
- [x] Keep one validated provider-visible context value, an ordinary complete
  path/content source mapping, the same-call ordinary H value, strict patch
  application and isolated candidate materialization.
- [x] Keep at most one optional terminal H/C trace as diagnostics; no second call
  event, public trace receipt or provider-call identity carrier remains, and a
  trace write failure cannot discard an otherwise valid provider result.
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
- [ ] Correct the problem-neutral CLI initialization order so its own metrics
  setup cannot violate the fresh-output invariant. Validate offline; any new
  live campaign requires a separately prepared carrier and authorization.
- [ ] After the development result, select any future formal population by a
  separately reviewed outcome-blind rule. Keep it unavailable to the Agent and
  require a new resource envelope and explicit authorization.
- [ ] Run real H and C, current Contract and Verification, problem Protocol,
  Safe Features and deterministic Decision. Provider retry, repair and hidden
  host steering remain zero.
- [ ] Assess separately whether the framework behaved correctly, whether the
  Agent used the evidence to conduct grounded research, and whether the solver
  actually improved.

Acceptance: at least one fresh autonomous attempt reaches a typed outcome with
the complete V3 decision chain and enough ordinary lineage to reconstruct what
H saw, proposed and changed. Promotion is not assumed; a valid rejection or
non-promotion remains evidence about Scion's research effectiveness.

Live provider/solver execution requires a separate explicit one-shot
authorization after the exact input, populations, budgets, stop conditions and
claim boundary are prepared.

### M10 - Close on solver evidence

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
unselected and unavailable to the Agent. No repair, retry, resume, replacement,
later development stage or formal rung is authorized.
