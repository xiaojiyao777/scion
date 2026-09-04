# Scion v0.4 Continuous Solver Research

*Working branch: `v0.4-dev`*

*Current as of: 2026-09-02*

## Goal and authority

[`design/scion-architecture-v3.md`](design/scion-architecture-v3.md) is the
sole architecture authority. The
[`direct-runtime addendum`](design/scion-architecture-v3-v0.4-direct-runtime-addendum.md)
narrows implementation details but does not add a second authority lifecycle.
Historical plans and experiment reports are evidence, not current work queues.

The project goal is retained solver improvement produced by Scion itself:

- Warehouse is accepted. The synthetic campaign promoted and independently
  retained `v1 -> v2 -> v3`; the production-style campaign promoted and
  independently retained `v1 -> v2`.
- CVRP is not accepted. No autonomous CVRP candidate has completed
  `screening -> validation -> frozen -> PROMOTE` and then beaten the original
  B0 in an independent, no-LLM retained evaluation without feasibility or fleet
  regression.

A valid negative run improves the research record but does not complete CVRP.

## Scion boundary

The problem enters through one adapter. Scion owns the research engine; it must
not contain CVRP or Warehouse mechanism selection logic.

```text
problem adapter + complete safe current source + optional ordered H-only history
  -> agent-controlled bounded source/history research
  -> one tainted structured H
  -> structural Hypothesis Contract
  -> agent-controlled bounded code research bound to that exact H
  -> one tainted structured C
  -> structural Patch Contract
  -> isolated candidate workspace
  -> executable Verification
  -> problem-owned paired Protocol
  -> Safe Features
  -> deterministic Decision
  -> exact candidate stage reuse, deeper branch research, or promotion
```

Required properties:

- H and C are tainted. They never author Protocol, Safe Features, Decision,
  scheduling or promotion.
- Contract checks structure, allowed files and interfaces. Verification checks
  executable correctness, determinism, feasibility and objective semantics.
- Protocol owns fixed cases, seeds, comparisons and statistical gates. Only
  typed Safe Features enter Decision.
- The scheduler has at most three active branches and is evidence-blind.
- A branch keeps its verified head across research rounds. An exact candidate,
  not a reconstructed carrier, progresses through later stages.
- Current-campaign screening history and explicitly loaded cross-campaign
  history are H-only ordinary evidence. The complete inventory is available to
  the agent; the host does not rank a nearest record or require a mechanism,
  file, action, history read or citation.
- If the agent cites history, it must have read that reference in the same
  bounded session. History never enters Safe Features or Decision.
- Scientific lineage is one minimal append-only factual path. Exact content
  equality is kept only where same-candidate reuse requires it; one digest may
  compact that comparison but grants no authority.
- Provider SDK retries remain disabled. An ordinary ResourceEnvelope may allow
  at most two `ProviderCaller` redispatches of the same frozen request for a
  typed timeout, transport fault or provider fault, with fixed bounded backoff
  of 5 seconds and then 20 seconds. Every physical dispatch consumes the shared
  cap and writes a terminal trace; a redispatch is not a new H/C turn and never
  enters history, Protocol or Decision. Multiple deliberate bounded research
  turns remain agent actions, not transport retry or response repair. This is a
  prospective ordinary boundary; old run artifacts retain their actual retry
  counts and attempt sequences.

Deletion boundary:

- No object identity/capability system, owner registry, lease, issue/claim/spend,
  signature, registration, nonce, receipt, manifest closure, freshness proof,
  repeated absence proof, candidate reconstruction or promotion dossier.
- No host top-N mechanism routing, forced nearest-history grounding, novelty
  gate, response repair, retry, partial resume or hidden held-out feedback.
- No distribution, deployment, installation, packaging, reproducible-build,
  root service, systemd, D-Bus, cgroup or native-spawn investment.

`Frozen Holdout`, fixed split/seed inputs, ordinary problem-owned operator
catalogues, fresh output directories, local subprocess limits and temporary
workspace cleanup are scientific or operational mechanisms, not authority
objects.

## Evidence checkpoint

Warehouse acceptance is recorded in:

- [synthetic continuous campaign](docs/experiments/v0.4/v0.4-warehouse-v3-continuity-synthetic-36stage-r8-postrun-20260808.md)
- [synthetic independent replay](docs/experiments/v0.4/v0.4-warehouse-v3-continuity-r8-heldout-replay-postrun-20260809.md)
- [production-style campaign](docs/experiments/v0.4/v0.4-warehouse-v3-production-transfer-prod12-24stage-r1-postrun-20260809.md)
- [production-style independent replay](docs/experiments/v0.4/v0.4-warehouse-prod12-independent-heldout-v1-postrun-20260809.md)

CVRP evidence is mixed:

- M7 reached a complete positive initial and expanded development screen, then
  failed during validation candidate construction. It is not a promotion.
- M23 completed 24/24 pairs with median delta `0` and was correctly rejected.
- M25 and M27 exposed candidate-only runtime timeouts.
- M30 made 25 provider calls, exported one formal candidate, completed 6/6
  initial pairs and failed quality with median delta `-5.5`.
- Earlier runs produced useful hypotheses and patches, including positive
  development screens, but no exact candidate survived the full held-out
  funnel. The detailed chronology remains under
  [`docs/experiments/v0.4/`](docs/experiments/v0.4/).

The current bottleneck is proposal yield plus CVRP algorithm robustness, not a
missing authority protocol and not evidence that Protocol should be weakened.

## Current implementation checkpoint

Completed in the current worktree:

- [x] Deleted the post-M32 S2c private controls/provider/problem/context capsule,
  study-root, study-manifest and safe-loader graph and its self-proof tests.
- [x] Deleted qualification-only/initial-only parking, retirement, carrier
  reconstruction, qualification CLI and audit paths.
- [x] Restored K=1 and K=2 to the ordinary three-branch campaign and complete
  `screening -> validation -> frozen -> PROMOTE` trajectory. K=2 still requires
  explicit provider-call and outer-hardwall caps.
- [x] Removed forced lexical nearest-history routing and mandatory history reads.
  The agent may search/read any visible history or ignore it; cited refs remain
  session-read checked.
- [x] Preserved complete within-campaign screening history with current/sibling
  relation and complete explicitly ordered cross-campaign history.
- [x] Replaced workspace leases/claims with ordinary fresh temporary candidates
  and local `try/finally` cleanup. Isolation, freeze and the one necessary
  candidate-content equality check remain.
- [x] Added provider/solver-free full-trajectory observations from ordinary
  status, summary, research history and traces. Stage progression is not counted
  as hypothesis replay; the report emits endpoint values, never a composite GO.
- [x] Made local development defaults `http://127.0.0.1:8080` and
  `gpt-5.6-sol`; explicit `SCION_*` values still override them.
- [x] Completed the five-block CVRP history-availability matched study in the
  fresh root
  `/home/clawd/research/scion-experiments/cvrp-history-matched-20260828-r5`.
  All ten arms completed their requested rounds and emitted ordinary status,
  summary, history and trace artifacts. The earlier `r2`, `r3` and `r4` roots
  remain excluded invalid-launch evidence.

The removed S2c authority chain and qualification-only K1/K2 study are
**cancelled**, not deferred. Git history preserves their historical record.

## Ordered active work

### R1 — Finish the problem-neutral runtime cut

- [x] Make the adapter the single Campaign/CLI problem entry point. Remove the
  caller-supplied duplicate legacy/V1 spec comparison and keep, at most, one
  clearly local compatibility projection while remaining code is migrated.
- [x] Verify real CVRP and Warehouse adapters, normal K1/K2 campaign composition,
  Contract, Verification, Protocol, Decision, history and workspace behavior.
- [x] Delete the obsolete qualification-only K1/K2 effectiveness scorer and its
  tests; retain the ordinary trajectory evaluator.
- [x] Run the full provider/solver-free suite, focused lint/import checks and
  `git diff --check` from the repository package root.

Acceptance: both problem packages construct only through their adapter; no
reachable runtime symbol reintroduces qualification parking, S2c manifests,
history routing or workspace leases.

### R2 — Measure whether history helps the agent

This is a causal development study, not a gate on whether Scion is allowed to
research.

- [x] Freeze five matched CVRP blocks. Within a block both arms use the same B0,
  `gpt-5.6-sol`, reasoning effort, research input, code/resource budgets,
  screening cases, seeds and time limits. Across blocks, use fresh disjoint
  development populations where the available corpus supports them.
- [x] Use K=1 in both arms so candidate-bank size is not a confound.
- [x] `history OFF` receives no prior research file. `history ON` receives the
  same complete ordered canonical H-only corpus. History remains optional to
  the agent; no read or citation is forced.
- [x] Counterbalance arm order (`ON/OFF` in three blocks, `OFF/ON` in two).
- [x] Each arm has exactly two formal screening-stage opportunities in a fresh
  campaign root. If the first result requests expansion, the second opportunity
  evaluates that exact candidate on the expanded screen; otherwise it may be a
  new formal hypothesis. Because the fixed protocol requires expanded screening
  before a pass, validation and frozen evidence remain unreachable in this
  proposal-effect study.
- [x] Record charged provider calls, formal proposal episodes, distinct H,
  distinct H+patch, explicit distinct-formal-H/charged-call throughput,
  Contract/Verification outcomes, fixed-slot screening gate/statistical
  indicators, median/CI and case/pair W/L/T, gate/statistical counts, pair
  attribution and completeness, protected-regression reasons,
  candidate-attributable failure
  classes and terminal execution completeness. Record all-deliberation history
  search/read actions separately from history refs/citations in the ordinary
  summary basis for the selected formal H; never attribute an unselected slot's
  basis to the executed H. Keep normal solver `time_limit` stops separate from
  failed-process `timeout`.

Blocks 01/03/05 ran ON->OFF and 02/04 ran OFF->ON. The prior existing-case
freeze is invalid:
the old full-result table covers 10,330 of 10,344 local CVRPLIB cases and all 14
remaining cases occur in the reference-validation failure table, so literal
fresh existing cases equal zero. The replacement is 30 fixed, cross-block
disjoint ordinary CVRP JSON inputs under
`scion_generated/cvrp_history_matched_v1`, produced by a deterministic
outcome-blind generator that reads no historical source or result. Uniform,
clustered and radial structures are predeclared; each block's positions 0/2/5
cover small/medium/large dimensions. Capacity is 80, every full ten-customer
constructive group has the fixed demand multiset `5 x (12, 4)`, an odd tail
uses demand 8, and `allowed_routes=ceil(customers/10)`. Thus both a direct
route witness and best-fit-decreasing packing meet the route cap, while the
total-demand capacity lower bound equals that cap. All BKS fields are null and
there are no solution sidecars. Exact byte regeneration, adapter loading and
the source counts are executable tests, not an identity or GO authority. All
30 screening cases resolve to the same 30-second solver limit;
dimension-based overrides are absent.

Primary observations:

- throughput: distinct formal H per charged provider call;
- development quality: initial expand/pass outcomes per formal proposal episode;
- safety guard: candidate-only timeout, invalid output and infeasibility rates
  must not worsen materially;
- utilization: all-deliberation search/read is a manipulation check; selected-H
  basis history refs/citations show that the exported H explicitly used those
  records, but neither measure proves benefit.

Compare endpoints block by block and in aggregate. Do not emit an aggregate
score or GO token. A non-positive result means the next long campaign runs
without loaded external history; it does not justify host routing or a more
complex history authority layer.

R2 result:

- The fresh `r5` root completed `10/10` arms and `20/20` requested evaluated
  screening steps. Contract and Verification passed every formal proposal;
  every arm was terminal `completed` and valid, with no unknown outcome,
  provider-cap exhaustion or infrastructure stop.
- ON produced formal-H counts `[1, 2, 2, 2, 2]` from charged-call counts
  `[7, 13, 13, 13, 16]`; OFF produced `[2, 2, 2, 2, 2]` from
  `[14, 16, 15, 15, 15]`. Mean distinct-formal-H/charged-call was about
  `0.1459` ON versus `0.1336` OFF, but this descriptive difference is not
  evidence that the external corpus helped.
- No selected ON hypothesis read or cited any of the additional 45 external
  records. The only selected-H history citations in ON were the immediately
  preceding current-campaign sibling in blocks 04 and 05. OFF likewise used
  only the common ordinary observations or its current-campaign sibling.
  Therefore external-history availability did not achieve attributable use and
  has no demonstrated benefit in this study. R3 will not load the external
  corpus. The 45 headline rows were nevertheless visible in ON prompts, so this
  result is an availability/index-exposure ITT rather than evidence that the
  external content had no effect whatsoever.
- ON used 62 charged calls and about 1.464 million prompt tokens; OFF used 75
  calls and about 1.321 million prompt tokens. Fewer calls therefore did not
  mean lower context or inference cost.
- Continuous local history was observably read and cited, and selected bases
  attributed later direction changes to the preceding sibling result, for
  example from joint operator-pair credit to initial/embedded-VNS budget
  allocation. Because both matched arms had local history, R2 does not estimate
  its causal effect or demonstrate benefit; it establishes attributable uptake
  and leaves that history path enabled.
- There were no invalid-output, infeasibility or protected-objective
  regressions. One block-04 ON second candidate had one candidate-only timeout
  among twelve attempted pairs and was correctly abandoned. No development
  candidate passed screening or promoted. Endpoint shifts remain descriptive;
  no aggregate score or GO was emitted.

### R3 — Run normal long CVRP research

- [x] Choose K=1 or K=2 from proposal-yield evidence without changing Contract,
  Verification, Protocol or Decision. K2 is an ordinary optional Creative
  strategy, not a separate campaign mode.
- [x] Start one fresh normal campaign through the local Codex proxy using
  `gpt-5.6-sol`, explicit provider-call cap, explicit outer hardwall, the fixed
  CVRP adapter/config and the history policy selected by R2.
- [x] Allow the scheduler to maintain up to three branches and continue for
  multiple proposal/evaluation rounds. Do not stop merely because the first
  hypothesis is negative.
- [x] Require automatic exact-candidate progression through screening,
  validation and frozen. Never reconstruct a candidate from summaries or
  history. The live run exercised exact initial-to-expanded screening reuse;
  no candidate earned validation.
- [x] If no candidate promotes, analyze proposal yield, distinct branches,
  Contract/Verification failures, stage reach, CVRP quality and runtime evidence
  separately, then freeze the next scientific change before another run.

Acceptance: a normal Scion campaign deterministically promotes an autonomous
CVRP candidate after the full declared funnel, with no hidden held-out input in
H, C, Safe Features or scheduling.

R3 freezes K=1. In r5, K1 produced a formal H at every opportunity not consumed
by exact-candidate screening expansion; the observed bottleneck was candidate
quality rather than formal-proposal yield. K2 would spend more provider budget
without matched evidence of a quality benefit. The normal run keeps the common
ordinary observations and within-campaign local history, loads no external
history file, caps provider dispatch at the mechanical K1 maximum of
`16 x 17 = 272`, and uses an explicit 60-hour outer hardwall.

R3 result:

- The one frozen launch at
  `/home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1`
  completed normally and is classified `VALID_16_STAGE_NO_PROMOTION`.
  It scheduled 21 research calls, completed 16/16 formal screening stages,
  recorded five typed research rejections, used 114/272 provider dispatches and
  finished with three ordinary branches and champion v1 unchanged.
- The campaign produced 16 distinct formal H episodes and 12 observed distinct
  H+patch pairs. Five exact candidates reached expanded screening. No candidate
  reached validation or frozen, so R3 does not meet its acceptance condition.
- The strongest candidate made incremental local-search deltas and passed
  expanded screening quality: case W/L/T `7/2/3`, pair W/L/T `56/19/21`, median
  `+3.75`, CI `[0,31.75]`. It also produced five repeatable candidate-only hard
  timeouts on `X-n716-k35`. Decision correctly overrode the Protocol quality
  pass with `CANDIDATE_RUNTIME_FAILURE` and abandoned it.
- Local history was attributably read and cited in eight selected H bases, and
  those bases explicitly tied several later direction changes to preceding
  branch evidence. This establishes uptake and dependence, not improvement
  benefit. After the runtime failure, however, rounds 17-21 made no successful
  history read despite the index exposing that failure and subsequent
  code/schema/Contract failures. Optional history therefore works as a
  capability but lacked a bounded responsibility to dispose of the immediate
  failure frontier.
- The final candidate completed 32/32 pairs with no runtime or protected
  failure, but all eight cases tied, median and CI were `[0,0]`, and its proposed
  reheating mechanism triggered zero times. Its self-authored falsifier had
  returned `failed`, yet the C session allowed `ready` because D1-D4 passed.
- Ordinary summary retained selected-H basis, while SQLite and research-history
  projections dropped it. Ordinary evaluated SQLite rows also left typed
  execution-outcome columns null. These are future lineage-write defects; the
  append-only R3 root will not be rewritten.

Full evidence is in
[`v04-cvrp-r3-normal-k1-sol-postrun-20260829.md`](docs/experiments/v0.4/v04-cvrp-r3-normal-k1-sol-postrun-20260829.md).

Before another normal campaign:

- [x] Make a failed self-authored falsifier a session-local veto on that exact
  patch value; an omitted or weaker later probe cannot reopen it.
- [x] Require an agent-authored disposition of explicit failures at the latest
  ordinary live round of `current` and `sibling` independently. A later pass
  closes an older failure only in the same relation; external and older history
  remain optional, with no host mechanism/ref selection.
- [x] Persist attempt-local selected-H basis and typed outcomes through ordinary
  StepRecord, SQLite, summary and research-history writes, including post-H
  rejection/infra and candidate-disposition failures. Keep validation/frozen
  evidence out of H-only history and leave old R3 rows unchanged.
- [x] Require an agent-authored exact-path activation falsifier and a separate
  public 719-customer large-shape deadline falsification for CVRP performance
  changes. These remain development diagnostics, never Safe Features, Decision
  inputs or core mechanism selectors.
- [x] Run the full provider-free, non-campaign regression and freeze a fresh R3b
  scientific question before spending new provider/solver budget. The frozen
  tree passed `2259` tests with one declared skip on 2026-08-29.

R3b result and R3c continuity:

- [x] Launch R3b once from B0 with the 21 complete R3 records available and the
  R2 heterogeneous corpus OFF. Its one complete initial screen was promising:
  32/32 valid, case W/L/T `6/0/2`, median `+6.5`, CI `[0,18]`, and Decision
  `expand_screening`. The agent did not search, read or cite external R3 history
  in this first H, so the result is not history uptake or benefit evidence.
- [x] Classify the vanished interactive process precisely. R3b stopped during
  the same candidate's expanded screen at 33 completed/valid pairs of 96,
  without an expanded metric, event or Decision. Preserve the root as
  `INTERRUPTED_UNFINALIZED_EXTERNAL_PROCESS_LOSS`; do not resume, retry, append
  a terminal artifact or infer a scientific result from partial counters.
- [x] Route SIGHUP through the existing typed CLI interruption path. This adds
  no service, owner, lease, signature, registry, receipt or hash closure.
- [x] Re-run the frozen launch gate after the SIGHUP change. The full
  provider-free, non-campaign regression passed `2260` tests with one declared
  skip in 439.42 seconds; the exact signal/resource/history/formal-readiness
  slice passed `107`, both histories load as 22 ordered `cvrp` records, and the
  R3c root remains absent.
- [x] Launch the freshly preregistered R3c campaign from B0 with the 21 complete
  R3 records followed by the one complete R3b record. Its first candidate
  completed a safe but tied 32/32 initial screen and returned
  `SCREENING_FAIL_CASE_QUALITY`; the next H turn then ended in a typed
  `LLMTimeoutError`, so the root stopped `valid_incomplete` with
  `PROVIDER_CALL_BLOCKED_INFRA` and no validation, frozen result or promotion.
- [x] Preserve R3c as terminal infrastructure evidence and do not resume it.
  Add only the minimal explicit transient boundary: zero SDK retry; at most one
  typed `ProviderCaller` redispatch; no 429/auth/format retry; each physical
  dispatch charged/traced; no identity, lease, request hash, receipt or retry
  state in H/history/Protocol/Decision.
- [x] Freeze R3d as a fresh-B0 experiment loading exactly 24 complete H-only
  records in R3 -> R3b -> R3c order. The post-repair full provider-free suite
  passed `2293` tests with one declared skip and zero failures; the fresh R3d
  root remained absent through prelaunch preparation.
- [x] Launch R3d once from fresh B0 with the 24 complete R3 -> R3b -> R3c
  records available. Its first candidate read and cited the R3b route-distinct
  result, changed only `destroy_repair.py`, passed Contract, Verification and
  canary, and completed a failure-free `32/32` initial screen with case W/L/T
  `4/0/4`, median `+2.25`, CI `[0,18]` and Decision `expand_screening`.
- [x] Classify R3d's vanished foreground process precisely. Expanded screening
  stopped after `35` attempted and `34` completed/valid pairs of `96`, without
  an expanded metric, event or Decision. Preserve the root as
  `INTERRUPTED_UNFINALIZED_EXTERNAL_PROCESS_LOSS`; do not resume, rewrite or
  infer an expanded result. Only its one complete initial-screen history row is
  eligible for future H context. See the
  [R3d interruption report](docs/experiments/v0.4/v04-cvrp-r3d-adaptive-history-k1-sol-interruption-20260830.md).
- [x] Separate and repair the two run-lifetime defects. The R3d tool PTY was
  never attached to the app terminal and later disappeared; independently, a
  caught signal could restore default handlers before typed finalization was
  durable. Keep handlers installed through `finalize_requested_stop`, suppress
  repeated handler re-entry, and require attach-before-start with a visible
  marker. Use `exec env` so the attached shell is replaced by Python. Add no
  service, background runner, distribution, deployment, build, process
  registry, identity, lease, receipt or hash closure.
- [x] Preregister R3e as a fresh-B0 campaign loading exactly 25 complete H-only
  records in R3 -> R3b -> R3c -> R3d order. Explicitly exclude R3d's status,
  SQLite, candidate workspace and partial expansion. The current repair gate
  has `1197` passing unit tests and `45` passing focused signal/finalization
  tests. See the
  [R3e preregistration](docs/experiments/v0.4/v04-cvrp-r3e-adaptive-history-k1-sol-preregistration-20260830.md).
- [x] Complete the fresh full provider-free, non-campaign regression: `2295
  passed, 1 skipped, 0 failed` from `2296` collected in 443.05 seconds (444.10
  seconds outer elapsed). The frozen launch block passes shell syntax, path,
  whitespace and diff checks; the R3e root remains absent.
- [x] Exhaust the attach-before-start path without launching. Two empty-shell
  requests across turns remained `queued` and unattached; no proxy, provider,
  solver or campaign action followed, the earlier empty shell is closed, and
  the R3e root remains absent. Freeze the sole fallback from the successful R3
  precedent: one result-blind ordinary non-TTY unified-exec foreground call.
  R3 completed exit `0` after `77359.3004` seconds, while the R3b/R3d PTYs
  disappeared after `4957.185`/`5039.302` seconds. Add no background, service,
  deployment, build, identity, lease, receipt or hash lifecycle.
- [x] Run the exact R3e block once through the frozen non-TTY unified-exec
  carrier. R3e completed one safe `32/32` initial screen with case W/L/T
  `3/1/4`, pair W/L/T `12/7/13`, median distance delta `0`, CI `[0,7]`, and
  Decision `expand_screening`. H read current source only and did not read or
  cite external history. This is uncertain adaptive-development evidence, not
  an expanded pass or promotion.
- [x] Classify R3e's second external process loss. The non-TTY carrier returned
  `failed/-1` after `7704.372878714` seconds; its last heartbeat reports `59`
  attempted and `58` completed/valid expanded pairs of `96`, with zero observed
  failures but no expanded metric, event or Decision. Preserve the root as
  `INTERRUPTED_UNFINALIZED_EXTERNAL_PROCESS_LOSS`; do not resume, rewrite or
  infer a result. See the
  [R3e interruption report](docs/experiments/v0.4/v04-cvrp-r3e-adaptive-history-k1-sol-interruption-20260831.md).
- [x] Freeze R3f as a fresh-B0 campaign loading exactly 26 complete H-only
  records in R3 -> R3b -> R3c -> R3d -> R3e order. Include only R3e's one
  completed initial-screen row and exclude its status, SQLite, candidate,
  workspace and `58/96` partial expansion. Keep all science inputs, thresholds,
  K1, three branches, 20 evaluated stages, 340 physical-dispatch cap, one typed
  transient redispatch and 96-hour hardwall unchanged. See the
  [R3f preregistration](docs/experiments/v0.4/v04-cvrp-r3f-adaptive-history-k1-sol-preregistration-20260831.md).
- [x] Replace the tool session as run owner with one verified local tmux
  carrier. Use exactly one lazy pane, set window-local `remain-on-exit`, and
  replace it once with the frozen foreground `exec env` command. The carrier
  probe survived its creating exec call and preserved exit status/signal. It is
  operational only: no service, distribution, deployment, build, PID registry,
  object identity, lease, receipt or hash authority is added, and only ordinary
  campaign artifacts establish the scientific result.
- [x] Complete the fresh exact-tree provider-free regression and record it in
  the R3f preregistration: `2296` collected, `2295 passed, 1 skipped, 0 failed`
  in 437.80 seconds (438.83 seconds outer), with focused Ruff `E9,F,I` and
  `git diff --check` green.
- [x] Run the frozen R3f campaign once through the exact tmux carrier. It
  completed exit `0` with terminal `completed / requested_rounds_completed /
  valid`, all `20/20` evaluated stages, 19 screening stages, one validation,
  zero frozen stages, 145/340 provider dispatches and champion v1 unchanged.
  Classify the run `VALID_20_STAGE_HORIZON_CENSORED`, not an interruption or
  promotion. See the
  [R3f postrun](docs/experiments/v0.4/v04-cvrp-r3f-adaptive-history-k1-sol-postrun-20260901.md).
- [x] Preserve R3f's stage-held-out validation result exactly. The cumulative
  pre-polish candidate passed initial and expanded screening, then validation
  attempted 96 pairs with 94 valid and two candidate-only `X-n401-k29`
  timeouts. Protocol returned `INCOMPLETE_EVIDENCE` and
  `CANDIDATE_RUNTIME_FAILURE`; Decision abandoned it. This is negative
  algorithm/runtime evidence, not root infrastructure or a validation pass,
  and the validation row remains excluded from H-only history.
- [x] Classify the final exact-relocate initial screen as a formal-horizon
  censor. It completed 32/32 valid pairs, case W/L/T `2/1/5`, median `0`, CI
  `[0,25]` and requested expansion at evaluated stage 20. No expanded-stage
  metric or Decision artifact exists. Do not resume or reconstruct this
  cumulative candidate.
- [x] Keep the scientific disposition bounded. Adaptive embedded-VNS scheduling
  is a strong negative; do not host-direct more pre-polish tournament or
  initial-VNS budget work. Exact inter-route evaluation remains only
  cumulative-candidate, association evidence. Retain V3 cumulative-depth
  semantics without rollback and report every result against its exact
  cumulative candidate.
- [x] Add the prospective R3g corrections without changing scientific
  authority: internal nested destroy/repair deadline polling and partial-local-
  candidate discard; captured ordinary before-source evidence for exact-stage
  proposal attribution after workspace cleanup; and explicit stage/child
  progress reset. Add no held-out exposure, host mechanism selection, object
  identity, lease, issuance, registration, signature, receipt, hash or repeated
  closure.
- [x] Freeze R3g as a fresh repaired-B0 campaign loading exactly
  `[21,1,2,1,1,22] = 48` strict H-only rows in R3 -> R3b -> R3c -> R3d -> R3e
  -> R3f order. R3f contributes 19 screening and three research-rejected rows,
  never its validation result or an executable candidate. Freeze the fresh
  root `v04-cvrp-r3g-normal-k1-sol-20260901-r1`, tmux session
  `scion-r3g-normal-k1-sol-20260901-r1`, and every repository-local launch path
  to the isolated repaired tree. See the
  [R3g preregistration](docs/experiments/v0.4/v04-cvrp-r3g-adaptive-history-k1-sol-preregistration-20260901.md).
- [x] Complete the full provider-free, non-campaign regression on the final
  combined tree: `2299` collected, `2298 passed, 1 skipped, 0 failed` in 432.87
  seconds. Ruff `E9,F,I` over all 18 changed Python files, with only the exact
  existing `F403/F405` ignores, and `git diff --check` pass. The temporary
  regression data symlink is removed and no pytest or solver process remains.
  Record the exact result in the R3g preregistration; all static gates are
  green.
- [x] Launch the frozen R3g wrapper once through its named tmux carrier. The
  first independently generated candidate read and cited R3f `history-0056`,
  changed only `local_search.py`, passed Contract, Verification and canary, and
  completed a failure-free `32/32` screen. Case W/L/T was `1/2/5`, pair W/L/T
  `4/6/22`, median distance delta `0`, CI `[-2,0]`; Protocol returned
  `SCREENING_FAIL_CASE_QUALITY` and Decision continued research.
- [x] Classify R3g's next H turn and terminal exactly. It read current source
  `source-0005`, then the same frozen request received two charged/traced 502
  `LLMProviderError` results at attempt indexes 0 and 1. No H or selected basis
  was exported. R3g stopped `valid_incomplete / execution_blocked_infra` after
  `1/20` evaluated stages and `10/340` provider dispatches, with champion v1
  unchanged. Its two closed strict history rows are one evaluated screen and
  one null-H `blocked_infra` row. Preserve the root as terminal and do not
  resume or reconstruct it. See the
  [R3g postrun](docs/experiments/v0.4/v04-cvrp-r3g-adaptive-history-k1-sol-postrun-20260902.md).
- [x] Keep the invocation-terminal gate and add only the prospective bounded
  provider repair for a fresh successor: SDK retries zero; at most two Scion
  redispatches of the same frozen request; fixed 5-second then 20-second
  backoff; every physical dispatch charged and traced; exhausted attempts still
  use the existing typed terminal path. Freeze provider ceilings at 180 seconds
  for default/H turns, 300 seconds for C turns and 240 seconds for C finalize.
  Add no scheduler-forward infra retry, identity, owner, lease, registration,
  receipt, request hash, history field or repeated closure, and do not rewrite
  R3d-R3g facts.
- [x] Freeze R3h as a fresh-B0 campaign loading exactly
  `[21,1,2,1,1,22,2] = 50` strict H-only rows in R3 -> R3b -> R3c -> R3d -> R3e
  -> R3f -> R3g order. Keep K1, three active branches, 20 evaluated stages,
  provider cap 340, 96-hour hardwall and all formal solver budgets/gates
  unchanged. Freeze fresh root
  `v04-cvrp-r3h-normal-k1-sol-20260902-r1`, tmux session
  `scion-r3h-normal-k1-sol-20260902-r1`, and the R3g-style one-respawn carrier.
  The [R3h preregistration](docs/experiments/v0.4/v04-cvrp-r3h-adaptive-history-k1-sol-preregistration-20260902.md)
  is ready for its one-shot background launch from clean detached worktree
  `/home/clawd/research/or-autoresearch-agent-r3h-dev` at code commit
  `44fff1356e253927e820fff88ad13ca701e87dbc`.
- [x] Complete and record the exact-tree full provider-free, non-campaign
  regression: `2301 passed, 1 skipped, 0 failed` in 475.77 seconds (478.81
  seconds outer wall). Focused provider/backoff/CLI/history tests, Ruff
  `E9,F,I`, diff check, production-loader 50-row check, formal readiness and
  frozen-wrapper syntax/path checks are green.
- [x] After every R3h launch gate became green, use the user's existing
  autonomous-launch authorization to create the frozen tmux carrier once and
  respawn its exact foreground `exec env` command once. If an in-pane
  precondition or proxy/model check fails, inspect the dead pane but do not
  respawn again under this preregistration. The one launch succeeded: first
  H/C closed with 11/340 all-successful attempt-0 provider traces, Contract,
  Verification and canary passed, and screening reached 2/32 valid pairs with
  zero failures under a healthy tmux/Python process.
- [x] Classify R3h's stop correctly: `valid_incomplete` after 11 evaluated
  stages, with 113/340 provider calls all successful. The terminal
  `HYPOTHESIS_RESEARCH_TRANSCRIPT_EXHAUSTED` was a proposal-local 1.5M
  character working-context limit, not global disk/provider/solver exhaustion.
  Preserve the 15-row history and do not resume the root. See the
  [R3h postrun](docs/experiments/v0.4/v04-cvrp-r3h-adaptive-history-k1-sol-postrun-20260903.md).
- [x] Remove long-run blockers without weakening scientific promotion: make
  started H/C local limits and exhausted typed transient/429 calls
  attempt-local; default transcript total unbounded; widen H/C timeouts and
  research actions; auto-enable default bounded H when a live failure frontier
  requires its tools; make output-history policy caps nonfatal; respect ignored
  SIGHUP; allow optional K2 cap/hardwall; and schedule forward after a cleaned
  stale explore attempt. Keep Auth/balance/operator-selected global boundaries
  and all Contract/Verification/Protocol gates.
- [x] Complete the combined regression on the long-run repair: `438 passed`
  focused; final full suite `2351 passed, 1 skipped, 0 failed` in 467.79
  seconds (469.59 seconds outer wall); changed-file Ruff `E9,F,I` and
  `git diff --check`
  pass. No real provider or campaign ran during tests.
- [x] Commit the exact repair/config/docs as `738d741e`, create the isolated
  R3i worktree, and launch the one-shot local tmux carrier for 40 evaluated
  stages with a generous 2,000-call / 14-day operator envelope. The first H/C
  closed with 11/2,000 all-successful attempt-0 provider calls; proposal
  Verification and formal canary passed; screening produced its first valid
  pair with zero failures while the tmux/Python process remained healthy.
- [x] Preserve R3i as terminal `valid_incomplete / execution_blocked_infra`,
  not resumable: 16/40 evaluated stages and 25 scheduled calls ended after a
  real 429 was followed by the local proxy's synthetic no-usable-account 401,
  which the transport misclassified as real authentication failure. The run
  used only 170/2,000 provider calls and had no H/C or solver timeout at the
  terminal. See the
  [R3i postrun](docs/experiments/v0.4/v04-cvrp-r3i-long-run-adaptive-history-postrun-20260904.md).
- [x] Record R3i's complete scientific subset: 16 complete metrics and 896/896
  valid pairs with no failures or protected regression; the cumulative v2
  bundle passed expanded screening `+2.5 [0,10.5]`, validation `+1 [0,14.5]`
  and frozen `+1.25 [0,6.5]`, then promoted. Keep bundle attribution explicit;
  stop current ejection-chain, always-on SWAP* and pure certificate/throughput
  directions, and do not claim retained-B0 improvement from R3i.
- [x] Finish the prospective post-R3i repair gate. The exact local-proxy 401 is
  now treated as retryable temporary unavailability without weakening real
  auth failure; malformed C wrappers receive bounded corrective feedback;
  successful `ready` avoids redundant final closure; operational rows are
  excluded from future algorithm context; and ordinary history input ceilings
  are widened. The stable full suite completed with `2383 passed`, `1 skipped`
  and `0 failed` in 478.87 seconds (480.61 seconds outer wall); targeted Ruff
  and diff check are green.

### R4 — Independent retained-B0 confirmation

- [x] Preregister and provider-/solver-free check the exact R3i v2 versus its
  starting B0 using ordinary read-only source/data copies. The deterministic
  36-case effect population has zero case or case-seed overlap with all 68
  R3-R3i metrics; the reused controlled canary is a non-estimand smoke check
  with a fresh seed. The retained stage uses the pre-R3 reserved 12-case final
  block and seeds `157,163`. The fixed-funnel check returned `PREPARED` for at
  most 85 pairs / 170 serial solver subprocesses; no live solver has started. See the
  [R4 preregistration](docs/experiments/v0.4/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-preregistration-20260904.md).
- [ ] After a promotion, run the reserved final population with no LLM calls,
  comparing the exact promoted snapshot directly to original CVRP B0.
- [ ] Require complete paired execution, feasibility, no fleet regression and a
  positive retained objective result under the frozen rule.
- [ ] Keep this final evidence unavailable to later proposal context.

Acceptance: the promoted CVRP algorithm truly retains an improvement over B0.

### R5 — Close v0.4 across problems

- [ ] Publish one compact cross-problem report separating framework correctness,
  research efficiency, algorithm quality and retained solver improvement.
- [ ] Mark v0.4 complete only when Warehouse and CVRP both satisfy retained
  improvement; otherwise leave CVRP open with the exact next falsifiable rung.

## Working discipline

- Main session owns architecture, experiment estimands and task ordering;
  bounded subagents implement modules and independently inspect evidence.
- Read V3 before changing runtime boundaries.
- Prefer subtraction. Historical compatibility is not a reason to keep dead
  authority code; historical evidence remains in Git and experiment reports.
- Use fresh output directories. Never overwrite a prior experiment root.
- Do not spend provider/solver budget until code, tests and scientific inputs
  for that run are frozen.
- Never infer a promotion from a positive screen, an interrupted run or a
  postrun reconstruction.
