# Scion v0.4 Continuous Solver Research

*Working branch: `v0.4-dev`*

*Current as of: 2026-10-05*

Follow [`../AGENTS.md`](../AGENTS.md) and [`current-state.md`](docs/status/current-state.md) before acting on this board.

## Goal and authority

[`design/scion-architecture-v3.md`](design/scion-architecture-v3.md) is the sole
architecture authority. The
[`direct-runtime addendum`](design/scion-architecture-v3-v0.4-direct-runtime-addendum.md)
narrows the current implementation but adds no second authority lifecycle.
Historical plans, completed checklist chronology, and experiment reports are
evidence, not current work queues; Git preserves the superseded long task log.

The project goal is retained solver improvement produced by Scion itself:

- Warehouse is accepted. Synthetic Scion promoted and independently retained
  `v1 -> v2 -> v3`; production-style Scion promoted and independently retained
  `v1 -> v2`.
- CVRP remains open. R3i produced a promoted development bundle, but R4 did not
  confirm it against B0, R5 is diagnostic only, and R6 did not confirm the
  minus-2-for-1 bundle. R7 completed autonomous development without promotion;
  R8 did not confirm its final candidate against B0. R9 completed autonomous
  research without promotion. R10 passed wider-budget screening against B0,
  then stopped on incomplete shared validation evidence. R11 completed without
  promotion, leaving a modest uncertain B-branch signal. R12 passed a narrow
  local screen but stopped on the same shared validation construction failure.
  R13's common-repair comparison completed valid but uncertain screening
  (+91.5 [-36,296.75]) against B0-fixed, not unchanged B0. R14 and R15 are now
  terminal without promotion. R15 completes the repaired validation matrix but
  fails quality; its final fresh candidate remains an unexpanded initial signal.
  The September 28 follow-up authorizes the proposed bounded self-test feedback
  and real-entry/integration research support, then a fresh experiment, commit
  and push. Scientific gates and all terminal evidence remain unchanged.
  R16 subsequently stops at its 48-hour guard after persistent account-quota
  failure: 7/12 stages, 86 valid pairs, completed negative validation and no
  promotion. The October 3 follow-up now approves explicit quota-stop repair
  and fresh R17 after verification, not resuming R16 or Git commit/push.
  The October 4 request separately authorizes committing/pushing the preceding
  work (`7e1fd7dc`, done), then inspection. R17 completes 12/12 stages and 178
  valid pairs with no quota event or promotion: expanded +15.25 [1.5,82], then
  validation -1.5 [-2933.75,824], 2/3/1. The subsequent October 4 approval
  authorizes coordinated subagents to repair public read-only access/query
  feedback, strengthen optional real-entry/exact-reference research support,
  then commit/push and run fresh experiments after verification (P14 below).
  That work is pushed; R18 completes12/12 screening stages and176 valid pairs
  without promotion. October5 authorizes analysis, optimization and a fresh run,
  emphasizing test reliability, real paths and stable gains (P15). No new Git
  commit/push, host algorithm selection or terminal resume is requested.

A valid negative run improves the research record but does not complete CVRP.
v0.4 closes only when both problem packages have retained improvement under
their declared independent evidence.

## Scion boundary

Scion core is problem-neutral. A problem enters through one adapter; its
algorithm, objective, feasibility rules, research surfaces, checks, Protocol
inputs, and telemetry meanings remain problem-owned.

```text
problem adapter + complete safe current source + optional ordered H-only history
  -> agent-controlled bounded source/history research
  -> one tainted structured H -> Hypothesis Contract
  -> agent-controlled bounded code research bound to that H
  -> one tainted structured C -> Patch Contract
  -> isolated complete candidate workspace -> Verification
  -> problem-owned paired Protocol -> Safe Features
  -> deterministic Decision
  -> exact stage reuse, deeper branch research, or promotion
```

### Creative space and deterministic boundaries

- H/C are tainted and cannot author Protocol, Safe Features, Decision, scheduling,
  branch state, or promotion. H may inspect complete safe ordinary source/history;
  C receives its approved H and a complete path/content source map. The host does
  not rank history or select a mechanism.
- A live branch keeps a complete verified tree as its research head. Screening
  `CONTINUE_EXPLORE` may deepen it; Contract/Verification failure cannot enter it.
  Held-out stages reuse the exact candidate, and a provisional head is not champion.
- Contract protects structure/source boundaries; Verification protects executable
  correctness; Protocol owns paired comparative science; Safe Features are the
  only deterministic Decision input. Telemetry prose is never another gate.

### Provider/session boundary

- Every deliberate turn consumes the shared cap; provider SDK retries are zero.
  An explicit ResourceEnvelope may allow up to two charged/traced redispatches of
  one frozen request after typed transient/rate-limit/proxy-unavailable failures.
  Exhaustion rejects only that attempt and does not enter algorithm history.
- Explicit usage-quota exhaustion uses the existing balance/resource terminal
  lane, not transient retry or fresh H; ordinary rate limits remain transient.
- Real authentication, balance, global call cap, missing terminal/typed outcome,
  invalid initial context, and interruption remain terminal or hold outcomes.
- Transcript total characters are unbounded by default. A started explicit local
  limit is attempt-local; an oversized pre-dispatch H context stays resource-
  exhausted rather than being truncated, ranked, or summarized.
- Open-session invalid actions may be revised before export. Successful Code
  `ready` exports the latest passing patch immediately with no second closure.
  A terminal H/C is never repaired or partially resumed.

### Explicit exclusion boundary

Do not add problem mechanisms to generic core; Trust/Hash authority, identity,
registries, leases, signing, receipts, or duplicate closure; host ranking,
novelty/telemetry gates, response repair, hidden retry, compression, or partial
resume; or distribution, deployment, packaging, build, root/systemd, native-spawn,
or service work. Fresh directories, local limits, cleanup, held-out inputs, exact
candidate reuse, and one necessary local equality check remain ordinary scientific
or operational facts, not authority objects.

## Current implementation facts

- Direct V3 supports K=1/K=2 inside at most three continuous branches; K=2 is an
  H drafting strategy, not qualification. Parking, reconstruction, S2c capsules,
  forced routing, novelty scorers, leases, and old prepare/resume paths are absent.
- Screening and explicit cross-campaign history are complete ordered H-only facts;
  held-out facts never enter proposals. Workspaces are ordinary isolated trees.
- Typed outcomes, H basis, StepRecord, history, raw metrics, and minimal lineage are
  the evidence path. Reports, traces, and tmux carrier state are diagnostic only.

- Stale reconciliation now copies the complete accepted branch tree for isolated
  Verification and fresh screening against the new champion. It does not replay
  patches or merge champion edits. Decision resets the comparison's expansion
  counts; held-out stages retain exact candidate reuse.
- CLI `--source-tree` selects the complete source value for a fresh campaign.
  Initial source is copied into the campaign's read-only champion snapshot;
  optional ordered H-only history remains separate from branch/stage/provider
  state. Status reports ordinary paths for initial, champion and branch source.

P1b observation cleanup is implemented:

- Protocol results and summaries carry problem-declared `candidate_runtime_counters`
  instead of seven fixed algorithm-shaped fields. Raw scalar/event observations
  are opaque; generic no-accepted-moves inference is removed. Actual execution
  audits and scientific gates are unchanged; held-out exposure remains filtered.
- `OperatorConfig`, `ChampionState.operator_pool` and the legacy configuration
  management path remain separate debt. Do not extend their assumed algorithm shape.

## Scientific checkpoint

### Warehouse

- [synthetic continuous campaign](docs/experiments/v0.4/v0.4-warehouse-v3-continuity-synthetic-36stage-r8-postrun-20260808.md)
- [synthetic independent replay](docs/experiments/v0.4/v0.4-warehouse-v3-continuity-r8-heldout-replay-postrun-20260809.md)
- [production-style campaign](docs/experiments/v0.4/v0.4-warehouse-v3-production-transfer-prod12-24stage-r1-postrun-20260809.md)
- [production-style independent replay](docs/experiments/v0.4/v0.4-warehouse-prod12-independent-heldout-v1-postrun-20260809.md)

### CVRP R3i

[`R3i`](docs/experiments/v0.4/v04-cvrp-r3i-long-run-adaptive-history-postrun-20260904.md)
completed 16 formal stages before a provider/proxy infrastructure stop. Its
cumulative v2 passed expanded screening `+2.5 [0,10.5]`, validation
`+1 [0,14.5]`, and frozen `+1.25 [0,6.5]`, then promoted. The bundle combines
four changes, including inter-route 2-for-1; this is bundle-level development
evidence, not isolated causality or retained-B0 superiority. R3i is terminal and
must not be resumed.

### CVRP R4

The [R4 fixed-candidate confirmation](docs/experiments/v0.4/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-postrun-20260905.md)
completed normally as `NOT_CONFIRMED` at expanded screening. It produced 24/24
valid pairs, no feasibility/fleet/runtime failure, case W/L/T `1/0/5`, median
distance delta `0`, and CI `[0,130.5]`. Protocol returned
`SCREENING_FAIL_CASE_QUALITY`; validation, frozen, and retained evidence remained
unexposed. Exact v2 is therefore not independently confirmed better than B0.

### CVRP R5

The [R5 diagnostic](docs/experiments/v0.4/v04-cvrp-r5-v2-2for1-ablation-postrun-20260905.md)
compared exact full v2 with an ordinary complete v2 copy that differed only
by removing `_exchange_2_for_1` from the default operator registry. It completed
normally as `DIAGNOSTIC_COMPLETE`: 24/24 valid pairs, no safety/runtime failure,
case W/L/T `0/2/4`, median `0`, CI `[-281.75,0]`, and essentially equal runtime.
On this already outcome-known R4 population, inclusion was unsupported and
compatible with harm. R5 cannot promote either arm; v2-minus-2-for-1 is only the
next evidence-supported candidate.

### CVRP R6

The [R6 postrun](docs/experiments/v0.4/v04-cvrp-r6-minus-2for1-b0-postrun-20260921.md)
records normal `NOT_CONFIRMED`: 24/24 valid pairs, no failure/fleet regression,
case W/L/T `2/1/3`, median `0`, CI `[-258,97.75]` and unchanged
`SCREENING_FAIL_CASE_QUALITY`. X-n351-k40 lost at every seed. Both large cases
used their algorithm-local budget in initial VNS with zero subsequent ALNS
iterations in both arms. This is development evidence, not mechanism causality.
Cleanup overlapped the wall-clock-budgeted run, so performance interpretation
is exploratory; the original negative Decision remains unchanged. Later stages
and the final retained block stayed unopened.

Exact R4–R6 artifacts are linked by
[`current-state.md`](docs/status/current-state.md).

### CVRP R7

The [R7 postrun](docs/experiments/v0.4/v04-cvrp-r7-autonomous-source-continuation-postrun-20260922.md)
records normal completion after 12 screening stages / 11 distinct evaluated
candidates, 139 provider calls and one pre-evaluation Contract rejection.
All 90 formal pairs were valid with no fleet regression; no promotion or
held-out stage occurred. A positive initial screen turned negative on expansion.
The final candidate instead ends at W/L/T 2/0/1, median +40, CI [0,608.5],
with expansion pending at the requested-round stop. Its large-case gains occur
with zero ALNS iterations and a highly variable unchanged comparator; only
limited active-path medium-case evidence supports further checking. Complete
branch source continuity is verified. R7 is terminal, not resumable.

### CVRP R8

The [R8 postrun](docs/experiments/v0.4/v04-cvrp-r8-r7-final-b0-postrun-20260922.md)
records normal `NOT_CONFIRMED`: 24/24 valid, counterbalanced pairs, no failures
or fleet regression; case W/L/T 1/1/4, median 0, CI [-159.5,71.75]. tai100a
wins four seeds, X-n351-k40 loses three; both large cases run zero ALNS
iterations, and X-n190-k8 only 1–3 candidate iterations. All later populations
remain unopened. These are whole-bundle facts, not component-causal findings.

### CVRP R9

The [R9 postrun](docs/experiments/v0.4/v04-cvrp-r9-post-b0-autonomous-postrun-20260923.md)
records normal completion: eight H/C candidates, 12 screening stages, 144 valid
pairs, 92 physical calls with two recovered timeouts, no promotion/held-out
stage. Three positive initial screens failed to establish expanded benefit.
Final C: 2/0/4, median 0, CI [0,170.25], uncertain. Final B: 1/2/3, median 0,
CI [-154,22.75], failed case quality. All 48 large-case pairs have zero ALNS
iterations in both arms. Source review distinguishes ineffective count-based
depth allocation and an unimplemented yield-controller hypothesis from actual
algorithm changes. All final complete trees are identified; R9 is terminal.

### CVRP R10

The [R10 postrun](docs/experiments/v0.4/v04-cvrp-r10-wide-budget-b0-postrun-20260923.md)
records 24 valid screening pairs, W/L/T 3/0/3, median 19.75, CI [0,179],
SCREENING_PASS. Both large cases still have zero candidate ALNS iterations;
one wins all four seeds by 198. Validation attempted 12 pairs but two failed
in both arms at shared construction: `INCOMPLETE_COMPARATOR_EVIDENCE`, no
promotion, frozen or retained execution. Validation is now operator-exposed.
Do not remove failed pairs or feed held-out outcomes to research proposals.

### CVRP R11

The [R11 postrun](docs/experiments/v0.4/v04-cvrp-r11-wide-budget-autonomous-postrun-20260924.md)
records 12 screening stages / ten candidates, 108 valid pairs, 101 provider
calls with one recovered 502 and no promotion or held-out stage. Final B's
expanded +10 [-1,216.75] is modest and uncertain; A's final large-case median
is -8557, C ends negative. Both early phase handoffs are guarded above 2000
customers and never activate on this screening population. All three final
complete source trees are identified; throughput alone did not ensure quality.

## Ordered active work

### P0 — Close the completed evidence

- [x] Add compact [R4](docs/experiments/v0.4/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-postrun-20260905.md)
  and [R5](docs/experiments/v0.4/v04-cvrp-r5-v2-2for1-ablation-postrun-20260905.md)
  postrun analyses that link to exact raw artifacts.
- [x] Preserve both external roots unchanged. Do not backfill stages, relabel R5
  as confirmation, or turn either postrun into another closure authority.

### P1 — Give the agent a durable complete algorithm workspace

- [x] Design and implement the smallest problem-neutral representation of an
  ordinary complete algorithm workspace that survives as the research value.
- [x] Replace stale-branch accepted-patch replay with direct use of an already
  materialized complete source tree; preserve rollback and exact held-out reuse.
- [x] Allow an operator to select a complete source tree explicitly as the base
  of a fresh campaign, optionally with ordinary H-only history. Do not restore
  branch/champion/provider mutable state from a terminal campaign.
- [x] Keep this path source-value based. Add no identity, digest authority,
  registration, lease, receipt, signing, replay closure, or problem-specific
  mechanism to generic core.
- [x] Do not extend generic operator/policy/construction/portfolio taxonomy while
  implementing continuation.
- [x] Verify focused branch/reconcile/workspace/context tests first, then the full
  test suite without a live provider or campaign because this touches shared
  campaign flow.

Acceptance: a live branch can deepen one complete executable algorithm for an
arbitrarily long campaign, and a later fresh process can explicitly start from a
selected complete tree without replaying a patch chain or pretending to resume a
partial campaign.

### P1b — Separate vocabulary cleanup

- [x] In a focused slice, move existing generic operator/policy/construction/
  portfolio meanings behind problem-owned declarations or opaque observations,
  with focused tests and no new Decision/Protocol gate. Configuration/pool
  interfaces are explicitly outside this observation slice.

### P2 — Next CVRP evidence rung

- [x] After P0 and the required P1 boundary work, preregister a direct comparison
  of the complete v2-minus-2-for-1 candidate against original B0 on unseen cases
  and seeds: [R6](docs/experiments/v0.4/v04-cvrp-r6-minus-2for1-b0-preregistration-20260921.md).
- [x] Keep complete pairs, feasibility, fleet protection, practical-effect and
  uncertainty gates. Do not weaken `SCREENING_FAIL_CASE_QUALITY` merely because
  R4 or R5 was negative.
- [x] Under the user's explicit continuation request, freeze code and scientific
  inputs, complete regression/control, verify no experiment is active, and launch
  once into a fresh root. R6 started from clean `e405bfd2`; runtime is frozen.
- [x] Read R6's terminal and exact metric artifacts after completion, publish
  its bounded postrun, and leave CVRP open unless retained evidence supports it.

### P3 — Autonomous optimization after R6

- [x] Preregister [R7](docs/experiments/v0.4/v04-cvrp-r7-autonomous-source-continuation-preregistration-20260921.md)
  from the complete minus-2-for-1 source, with fresh campaign state, all ordered
  H-only scientific history and the distinct R4/R5/R6 screening observations.
- [x] Preserve existing gates and held-out isolation; declare R6 screening as
  adaptive development. Validate the new input projection and source/history
  continuation without prescribing a mechanism or changing generic core.
- [x] Freeze inputs and launch R7 once under the user's analysis/optimization
  request, with no overlapping cleanup, tests or solver job. Started at
  `2026-09-21T23:21:02Z` from clean `ffde7f66`; runtime/inputs are frozen.
- [x] Analyze actual H/C, verified source continuation and terminal paired
  evidence. R7 did not promote; the final active-path tai100a signal warrants
  one bounded prospective check, not an improvement claim or a solver rewrite.

### P4 — Test the exact R7 discovery candidate against B0

- [x] Preregister [R8](docs/experiments/v0.4/v04-cvrp-r8-r7-final-b0-preregistration-20260922.md)
  using the existing counterbalanced provider-free fixed funnel, unchanged
  complete source and scientific gates, fresh seeds, known screening cases
  and conditionally unopened validation/frozen/retained populations.
- [x] Verify source/scope, prospective inputs, full conditional resource matrix
  and read-only preparation; finish focused tests before measurement.
- [x] Launch once into a fresh output under the user's optimization request,
  with no overlapping solver, cleanup or tests. R8 started at
  `2026-09-22T14:45:38.550230+00:00`, driver PID 117138; R7 stays terminal.
- [x] Analyze R8's terminal, 24 raw pairs, complete source snapshots, AB/BA
  order and phase behavior. Preserve the negative Decision and keep CVRP open.

### P5 — Autonomous research after the R8 B0 check

- [x] Preregister [R9](docs/experiments/v0.4/v04-cvrp-r9-post-b0-autonomous-preregistration-20260922.md)
  from R8's complete candidate, adding R8's distinct observation and explicit
  unconfirmed-B0 question, with all ordered R3–R3i/R7 history and unchanged gates.
- [x] Verify source/input/CLI/history projection and focused regressions before
  provider or solver execution. No host-authored algorithm or generic-core change.
- [x] Launch once into the fresh R9 root with no overlapping maintenance,
  tests or solver. Started `2026-09-22T23:22:20.486583+00:00`, driver PID 126943.
  Initial source snapshot and actual H input/call success are verified without
  forcing reads; subsequent H/C and scientific outcomes remain to be analyzed.
- [x] Analyze R9 terminal H/C, source fidelity and paired evidence. Preserve
  negative/uncertain Decisions and all original artifacts. No local promotion
  or B0 improvement was established.

### P6 — Equal wider-budget comparison with original B0

- [x] Under the user's explicit budget-widening approval, preregister
  [R10](docs/experiments/v0.4/v04-cvrp-r10-wide-budget-b0-preregistration-20260923.md)
  using R9's ordinary complete C candidate and original B0. Double formal
  dimension-band solver limits for both arms; retain all science/safety gates,
  AB/BA order, fresh seeds and held-out isolation. No host solver patch.
- [x] Verify prospective inputs, source scope and the complete conditional
  resource matrix; focused regressions and provider-free read-only `--check`.
- [x] Launch once into fresh R10 output with no competing solver/tests/cleanup.
  Started `2026-09-23T15:02:15Z`, tmux `scion-r10-wide-budget-b0-20260923`,
  driver PID 154657. Both 100-file snapshots equal their originals; a real
  screening arm uses 60 s on B-n34-k5 / seed 90001. Runtime, scientific inputs
  and source values remained frozen during measurement.
- [x] Read exact terminal and paired evidence, including whether extra time
  actually allows ALNS on large cases. Do not infer that more time guarantees
  useful search or pool the new contrast with R8/R9. Any retained result is
  specific to the wider-budget regime.

### P7 — Autonomous research in the wider-budget regime

- [x] Preregister [R11](docs/experiments/v0.4/v04-cvrp-r11-wide-budget-autonomous-preregistration-20260923.md)
  from R10's ordinary complete candidate, with unchanged wide budgets/gates,
  fresh seeds, four prior observations, R10 screening-only question context
  and all ordered R3–R3i/R7/R9 scientific history. No host-selected mechanism.
- [x] Validate new input/projection and focused regressions: 208 passed in
  2.75 seconds. Preserve the known unresolved validation comparator limitation;
  neither drop the case nor leak its failure to H/C.
- [x] Finish source/history/data/provider/no-overlap checks and launch once
  into fresh R11 output at `2026-09-23T23:47:06Z`, driver PID 166821.
  Initial champion equals all 100 source files; first two real H calls succeed
  with the exact question and four-observation / 90-history index. No formal
  result yet. Freeze runtime/inputs throughout measurement.
- [x] Analyze actual H/C and terminal paired evidence: 108 valid pairs, no
  promotion, final B +10 [-1,216.75], uncertain. Two phase handoffs never
  activated because the imported threshold is 2000; no host repair/gate added.
  Local development is not B0 retained confirmation.

### P8 — Autonomous research after the R11 source/activation audit

- [x] Preregister [R12](docs/experiments/v0.4/v04-cvrp-r12-post-r11-autonomous-preregistration-20260924.md)
  from complete final B, with all R11 history, screening-only observations and
  source-grounded threshold facts, fresh seeds and unchanged budgets/gates.
  Do not merge siblings, prescribe an algorithm or leak held-out failure details.
- [x] Verify inputs/projection, complete source, all 25 case inputs, ordered
  125 raw / 102 scientific history records and focused regressions (211 passed).
- [x] Check provider and no-overlap/fresh-output state; launch once at
  `2026-09-24T11:48:32Z`, driver PID 195869. All 100 initial champion files
  match; first two actual H calls succeed with the exact question and
  four-observation / 102-history index. Freeze runtime/inputs during measurement.
  The known validation comparator issue remains; no formal R12 result yet.
- [x] Analyze actual H/C, terminal decisions, source fidelity and paired outcomes:
  [R12 postrun](docs/experiments/v0.4/v04-cvrp-r12-post-r11-autonomous-postrun-20260926.md).
  108 valid screening pairs; final A +2.25 [0,11.25] passes, then shared
  construction blocks validation (10/12 valid). No promotion. Preserve all evidence.

### P9 — Independent constructor repair and common-repair comparison

- [x] User explicitly authorizes a GPT-6-Astra repair subagent and concurrent
  remaining design, with a new experiment only after all checks pass.
- [x] Implement minimal problem-owned bounded packing recovery and remaining-
  time passthrough. Preserve successful greedy behavior, explicit failures,
  original B0/candidates and all historical incomplete/negative results.
- [x] Preregister [R13](docs/experiments/v0.4/v04-cvrp-r13-constructor-fixed-b0-preregistration-20260926.md):
  complete R12 A plus the same repair applied to new B0-fixed; equal budgets,
  counterbalancing, fresh seeds, unchanged gates, no sibling merge or additional
  host performance patch. This is not autonomous discovery or unchanged-B0 proof.
- [x] Finish independent repair review, full-solver correctness diagnostics,
  focused regressions, complete-source comparison and read-only preparation:
  [diagnostic](docs/experiments/v0.4/v04-cvrp-constructor-repair-diagnostic-20260926.md).
  136 tests pass; four complete solver checks pass; both 100-file trees have
  identical minimal repair; `--check` returns PREPARED without execution.
- [x] Freeze runtime/sources/inputs and launch once into fresh output, without
  overlapping tests/maintenance/solvers. Exposed validation is development;
  unopened frozen/retained evidence remains conditional. Do not resume R12.
  R13 started `2026-09-26T01:13:23Z`, PID 242261. Both 100-file snapshots
  equal the declared repaired sources; actual screening uses the correct 60 s.
  No formal result yet; only launch-status docs change after startup.
- [x] Analyze [R13 terminal paired evidence](docs/experiments/v0.4/v04-cvrp-r13-constructor-fixed-b0-postrun-20260927.md):
  24 valid pairs, 4/1/1, +91.5 [-36,296.75], uncertain; no later stages.
  Preserve original evidence and the distinction between engineering repair,
  B0-fixed comparisons and unchanged-original-B0 retained improvement.

The September 26 commit/push request completed as `964a9622`; no running
algorithm or scientific input changed. A subsequent September 27 request
authorizes committing and pushing the frozen R13–R15 change set without
changing the running R15 runtime or scientific inputs.

### P10 — Autonomous optimization after the repaired-comparator screen

- [x] Preregister [R14](docs/experiments/v0.4/v04-cvrp-r14-post-r13-autonomous-preregistration-20260927.md)
  from R13's complete candidate snapshot, all ordered R12 history and safe
  screening evidence, with fresh seeds and unchanged budgets/gates. H/C choose
  algorithms; preserve adverse results and exclude private regression details.
- [x] Verify prospective inputs, complete source/history projection and all 25
  data cases: 225 tests pass in 3.07 seconds, 100 source files parse, 135 raw /
  112 H-visible records and five observations project correctly. Ruff and diff
  checks pass. Final provider/fresh-output checks precede launch.
- [x] Freeze runtime/sources/inputs, verify provider/fresh output/no overlap and
  launch once at `2026-09-27T02:19:53Z`, PID 267274. All 100 initial files
  match; first actual H call succeeds with exact question and five-observation /
  112-history indexes. No formal result yet; do not resume R13 or claim B0 proof.
- [x] Analyze [R14 H/C, source continuity and paired evidence](docs/experiments/v0.4/v04-cvrp-r14-post-r13-autonomous-postrun-20260927.md):
  completed 08:44:52 UTC, 108 valid pairs, ten candidates, no promotion.
  120 successful calls, no global exhaustion; one Code abandonment. All 302
  visible C source values and three final trees match. Opaque preflight reasons,
  cumulative-source reasoning and hypothesis/population coverage need attention.
  The subsequent diagnosis preserved all evidence without a runtime edit.

### P11 — Repair research feedback, then a fresh autonomous experiment

- [x] September 27 user explicitly authorizes coordinated subagents to repair
  the diagnosed research-support gaps and then start another experiment.
- [x] Add safe typed development preflight feedback and cumulative-source /
  comparator interpretation guidance. Keep import/API rejection, test counts,
  complete source/history, held-out isolation and all scientific gates.
- [x] Preregister [R15](docs/experiments/v0.4/v04-cvrp-r15-feedback-repair-autonomous-preregistration-20260927.md)
  from the same complete R12-A-fixed tree, all ordered R14 history and fresh
  seeds. Initial five-case screening covers X190/X513; expansion still adds
  the sixth case and requires four seeds. No host algorithm change or merge.
- [x] Complete focused/full regressions and the independent
  [Warehouse control](docs/experiments/v0.4/v04-r15-warehouse-feedback-control-20260927.md)
  on the same frozen runtime, since shared research code changed. Full suite:
  2471 passed / 1 skipped; focused repair/context/input tests and independent
  review pass. The first control input correctly failed startup overlap checks;
  [r2](docs/experiments/v0.4/v04-r15-warehouse-feedback-control-r2-20260927.md)
  completes two valid negative stages, 48 successful calls, no framework blocker.
- [x] Freeze inputs/runtime, verify no overlapping work and launch R15 once
  at `2026-09-27T13:54:37Z`, PID 289227. All 100 source files match; first
  actual H calls succeed with exact question, five observations, 124 history
  entries and repaired guidance. Startup is not improved-reasoning/quality proof.
- [x] Analyze terminal H/C, preflight feedback use, source and paired evidence:
  [R15 postrun](docs/experiments/v0.4/v04-cvrp-r15-feedback-repair-autonomous-postrun-20260928.md).
  136 valid pairs, 125 successful calls, no promotion; expanded +11.5 passes,
  complete validation -39.75 fails. Final fresh initial +9 is unexpanded.
  Source fidelity holds; three candidates target an inactive path, one real
  implementation is incomplete behind a passing mock probe, and self-test
  diagnostics remain opaque. No live C8/C9 event tests the new preflight hint.
- [x] Obtain fresh authorization before implementing proposed research-support
  improvements or launching another run. Preserve scientific gates, private
  validation isolation and all original evidence; never resume terminal R15.

### P12 — Safe self-test hints and real-entry research support

- [x] September 28 user approves the proposed direction, a fresh experiment,
  and Git commit/push. No algorithm selection or budget expansion is implied.
- [x] Add bounded phase/exception-category/probe-line feedback without raw
  exceptions, paths, readiness changes or private-suite exposure.
- [x] Add optional problem-owned real-entry/real-collaborator examples and
  interpretation guidance; no mandatory style, mock ban or new quality gate.
- [x] Finish focused/adversarial tests and full suite (2514 passed / 1 skipped),
  then terminal-audit the independent Warehouse control. It is valid_incomplete:
  1/2 requested stages at the unchanged 80-call cap, one valid tie, actual safe
  failed-probe feedback and complete generic evaluation path; no framework
  blocker. Preserve its 35 source/schema tool errors and incomplete coverage.
- [x] Preregister and launch fresh R16 from unchanged complete R12-A-fixed
  algorithm source, fresh seeds and complete ordered safe H-only history.
  Launched once 2026-09-28 15:48:59 UTC, PID 331499, runtime/inputs d67f9800.
- [x] Verify real startup/source/context and update handoff: 100 source files,
  exact question, 136 ordinary-history plus five observation indexes, successful
  actual H calls. Startup is not scientific success. Implementation was
  committed before launch; following docs-only commit/push completes the
  user-authorized Git handoff (consult Git for the resulting tip).
- [x] October 3 read-only [R16 postrun](docs/experiments/v0.4/v04-cvrp-r16-probe-diagnostics-autonomous-postrun-20261003.md):
  seven complete stages / 86 valid pairs before quota outage, expanded +4.75
  passes and complete validation fails. Fifty successful calls then 196 failed
  dispatches; 246/600 used, no call-cap exhaustion. Outer guard stops September
  30 at 15:49:01 UTC. Safe hints reach C; inactive sweep and mock-only probes
  remain research limitations. Preserve original evidence; never resume R16.
- [x] October 3 follow-up authorizes the proposed explicit-quota handling fix
  and fresh experiment after verification. No terminal resume or Git action.

### P13 — Stop explicit quota exhaustion, then fresh R17

- [x] Classify explicit quota 429 as existing balance/resource exhaustion.
  Preserve ordinary rate-limit/timeout/proxy retry, real auth, charged traces,
  clean algorithm history and all scientific gates. No outage/recovery system.
- [x] Focused quota/provider/client tests: 163 pass, including actual SDK error
  shape and both H/C-to-campaign one-dispatch terminal behavior.
- [x] Preregister [R17](docs/experiments/v0.4/v04-cvrp-r17-quota-aware-autonomous-preregistration-20261003.md)
  from unchanged R12-A-fixed with all six R16 safe rows and fresh seeds.
  Ten R16/R17 input/seed/closure tests pass; no private later-stage injection.
- [x] Full suite: 2554 passed, 1 skipped in 434.47 s; read-only source/data/
  closure/production/exact H projection pass. Real provider inference recovers.
  Run the independent
  [Warehouse control](docs/experiments/v0.4/v04-r17-warehouse-quota-control-20261003.md)
  on the same frozen runtime: completed 2/2 at 13:35:48 UTC, 70 successful
  calls, two valid negative screens, exact source continuation, no framework
  blocker. Preserve query inefficiency and two research-rejected attempts.
- [x] Launch fresh R17 once at 13:40:12 UTC, PID 460131. All 100 champion
  files match, actual first H succeeds at attempt0 with the exact 10,347-character
  question, 142 safe history rows plus five observations (147 index entries).
  Keep source/runtime/inputs frozen; no overlapping tests/solvers/maintenance.
- [x] October 4 [R17 terminal audit](docs/experiments/v0.4/v04-cvrp-r17-quota-aware-autonomous-postrun-20261004.md):
  12/12 stages, 178 valid pairs, seven candidates, 69/600 successful calls,
  zero research rejections, no promotion. Expanded screening passes 5/0/1;
  complete validation fails 2/3/1. All 146 visible C sources and surviving
  complete B/C heads match; full abandoned A source is unavailable. Preserve
  operator-only validation and exact-reference/integration/oracle-test limits.
- [x] Commit and push prior completed work before analysis: `7e1fd7dc`.
- [x] Diagnose query inefficiency: Warehouse 28 query errors plus two editing
  errors / 43 C turns; frozen public dependency absent from C corpus, repeated
  invalid queries and coarse correction feedback. CVRP has only one query
  error plus one duplicate-file edit error; not its scientific bottleneck.
- [x] Follow-up authorized and transferred to P14: separate public dependencies from
  editable source and improve bounded field/path feedback; test frozen-edit,
  held-out, source-continuation boundaries and a fresh Warehouse control.
  Strengthen optional real-entry/exact-reference probe support without a
  prescribed algorithm, private validation hints or a new quality gate.
  No repair or new experiment is executed in this inspection. Never resume
  R16, R17 or their terminal controls; retained CVRP confirmation stays open.

### P14 — Public research sources, actionable query feedback and exact probes

- [x] October 4 user authorizes team implementation, Git commit/push and a
  fresh experiment following the R17 report. Entry selects Code Repair profile;
  V3/addendum and the runbook are read, Git/tmux/terminal state checked. Preserve
  the six uncommitted R17 analysis documents and all original experiment roots.
- [x] Expose explicitly declared public dependencies as read-only ordinary
  source, separate from editable files, on the exact current branch base.
  Preserve private-suite/data exclusion, frozen edits and source completeness.
- [x] Return bounded, problem-neutral query correction feedback without raw
  error/path leakage, command repair, new retries or increased local limits.
- [x] Strengthen optional public real-entry and independent exact-reference
  examples; test real collaborators and reference arithmetic without selecting
  an algorithm, replacing the model's mechanism or adding a quality gate.
- [x] Complete focused/adversarial checks, independent cross-review, full suite
  and prospective input/source/history projection. Freeze runtime and inputs,
  commit and push before new measurement.
  Frozen runtime/inputs: `1596347c`, pushed to origin before provider dispatch.
- [x] Run a fresh two-stage Warehouse control on that runtime; inspect actual
  source access/feedback and complete science before CVRP. Preserve any negative
  or incomplete result rather than resuming or silently widening its envelope.
  Completed valid2/2,48 calls all successful; both pairs tie. Exact sources and
  readonly protection pass; three query errors, three readonly-edit refusals and
  three import preflight failures preserve remaining research support limits.
- [x] Launch fresh CVRP R18 from unchanged complete R12-A-fixed source with all
  safe R17 history, fresh seeds and unchanged Protocol/budgets. Verify actual
  startup source/context. No private validation hints or R17 candidate merge.
  Started once at October4 12:04:15 Beijing /04:04:15 UTC, PID480652; all100
  source files and actual H's153 histories+five observations match.
- [x] Latest analysis-only request: inspect ten completed R18 stages / seven
  candidates at October4 21:05 Beijing. All142 pairs valid; no completed expanded
  screen passes, no validation/promotion. A3 initial X351 +1712.5 with four ties;
  round11 expansion running,21/24 pairs complete. Of77 calls,76 succeed and one
  bounded C timeout recovers; no quota exhaustion. Source delivery/current full
  trees and raw objective aggregation checks pass. Independent tiny exact probes
  improve, but mistaken expectations, mocked/uncollected scheduler probes and
  activation/generalization gaps remain. Detailed evidence is appended to the
  existing R18 design; only analysis/status docs changed, no tests or rerun.
- [x] Inspect R18 terminal/metrics and final H/C:12 stages,176 valid pairs,
  no promotion. A3 expanded X351 reverses to -501.5; B3 has a materializer defect
  and three unsuccessful draft-relative corrections. All current source/context
  comparisons pass. Preserve terminal evidence and the five missing historical
  full-stage source limits; do not resume or claim retained improvement.

### P15 — Reliable tests real paths and stable gains

- [x] October5 authorization: implement scoped research support after terminal
  analysis, verify and start a fresh experiment. No new commit/push requested.
- [x] Explain pytest exit5 as no tests collected with bounded optional feedback;
  preserve inconclusive/readiness and failed exact-patch semantics. Guide collected
  assertions and independent reference checks without new candidate gates.
- [x] Explain revise as complete-draft replacement against the original session
  source, not an edit over the staged draft. Regression checks rejected selectors,
  base reads and successful complete corrected replacement; no automatic repair.
- [x] Extend optional problem-owned rational arithmetic and multishape/seed real
  entry examples; preserve real constructors/operators/guards and independently
  recompute feasibility/cost. Mutation tests falsify actual stated faults.
- [x] Preregister [R19](docs/experiments/v0.4/v04-cvrp-r19-reliable-probes-autonomous-preregistration-20261005.md)
  with four initial and six expanded seeds, unchanged gates/solver limits/caps,
  complete R12-A-fixed source and all safe R18 history. No candidate merge or
  private validation hints. Five new input regressions pass.
- [x] Full regression2659 passed / one skip in453.27 seconds; Ruff/diff checks
  pass.100 CVRP source files/25 cases, five Warehouse cases, public/formal closure
  and exact H question/history projection pass (188 raw/165 safe rows +five
  observations,170 entries). No output/provider/solver created by preflight.
- [x] Freeze runtime/inputs; attempt and audit the fresh two-stage/80-call
  [Warehouse control](docs/experiments/v0.4/v04-r19-warehouse-reliable-probes-control-20261005.md).
  Stops October5 14:37:22 Beijing at80 calls with43 upstream overloaded-server502
  failures; **0/2 evaluated stages**, invalid_no_evaluated_outcome.37 calls succeed,
  no completed C candidate or scientific history/metrics. All recorded source
  payloads and34 frozen-request retries match. No overlapping tests/solvers or
  runtime/input edits; no extension/resume or completeness relabeling.
- [x] After service recovery, preregister a fresh complete Warehouse control with
  new output/seeds; inspect actual H/C/gates/science. R19 control is terminal and
  cannot serve as completed live validation. No larger budget is authorized here.
  October5 follow-up approves gpt-6.1-sol high after two successful bounded
  tool probes. [Fresh Sol control](docs/experiments/v0.4/v04-r19-warehouse-reliable-probes-sol61-control-20261005.md)
  starts once at15:42:59 Beijing, PID537412, new root and primes above240000,
  unchanged2 stages/80 calls;22 input regressions, preflight and bounded inference
  pass. Runtime/inputs stay frozen. CVRP's still-unexecuted invocation selects
  the same model, pending the complete terminal audit. No proxy
  restart, runtime/prompt change, budget expansion or new commit/push. Model
  and P15 effects are not separately identifiable; existing evidence is preserved.
  Interim15:59: first18 calls all succeed, but one C attempt is abandoned after
  four prohibited-oracle-import preflight failures. No public/self-test executes;
  control still0/2, fresh H active. Preserve this remaining research-efficiency
  limit. Successful transport is not a completed control or authority for CVRP.
  Terminal audit supersedes that interim: completed/valid16:36:07 Beijing,
  2/2 negative screens,78 calls (77 successes/one recovered502), two C8-related
  abandonments, no promotion. All48 editable/432 readonly/96 public-test C values
  and surviving complete source trees match. Preserve import-guidance omission
  and missing production-activation evidence; P16 addresses shared support next.
- [ ] Launch CVRP R19 once after that control; verify actual source, safe history,
  successful H and resource envelope. Later inspect accepted transitions and all
  seed patterns; startup and more samples do not demonstrate stable improvement.
  CVRP is not launched. After Warehouse terminal, only its unexecuted CVRP version
  labels and a label assertion are corrected; five input tests pass. Executed
  Warehouse inputs and runtime stay unchanged. No new Git commit/push.

### P16 — Visible import rules and precise draft feedback

- [x] Latest October5 approval permits scoped optimization and a fresh experiment;
  keep gpt-6.1-sol high. No Git action, terminal resume or proxy changes.
- [x] Expose actual effective C8 absolute roots through final direct/bounded C
  target guidance; distinguish read-only visibility from import permission.
  Reuse one checker policy, without extending its acceptance set.
- [x] Add optional one-based rejected-import source_line bound to submitted
  editable draft content. Keep raw checker/exception/private data out, failed
  exact-patch semantics and formal Contract/Verification rules unchanged.
- [x] Clarify optional testing interpretation: forced wiring is not ordinary
  activation; entry counts are not completed transitions/acceptance/improvement.
  Preserve P15 reference/real-entry support and four-/six-seed CVRP design.
- [x] Complete full regression, fresh input/source/context and provider checks;
  freeze runtime/inputs and launch the
  [import-feedback control](docs/experiments/v0.4/v04-r19-warehouse-import-feedback-control-20261005.md)
  once with fresh seeds/output and unchanged2 stages/80 calls.
  Started once18:26:58 Beijing /10:26:58 UTC, PID543472. All406 initial source
  files match; first two actual H calls succeed at attempt0; stored resource/C
  limits and frozen runtime diff match. Control running0/2; startup is not science.
- [ ] Audit its terminal H/C, source, tests/corrections and paired science before
  launching still-prospective CVRP R19 on the same runtime. Never send Warehouse
  outcomes/recipes to CVRP or relabel regression-only paths as live coverage.
- [x] Subsequent October5 request authorizes committing/pushing the frozen
  P15/P16 set. Read-only launch-readiness inspection at18:31 Beijing still finds
  the fresh control running0/2, first Code research in progress. Keep CVRP
  unlaunched pending the complete audit; no overlapping solver or runtime edit.

### v0.4 closeout

- [ ] Publish a compact cross-problem report separating framework correctness,
  research efficiency, algorithm quality, and retained improvement.
- [ ] Mark v0.4 complete only after CVRP also satisfies retained improvement;
  otherwise keep the exact next falsifiable rung open.

## Verification snapshot

- P16: full suite2678 passed / one skip in451.05 seconds;197 focused plus42
  context/import checks overlap.24 R16–R19 input regressions pass; Ruff/diff,
  source/data/public-formal closure and exact safe question/history checks pass.
  Single gpt-6.1-sol high tool inference succeeds18:25:59 Beijing,3.524 seconds.
  Freeze ordinary uncommitted runtime/inputs before fresh control dispatch.
- P15 / R19 preparation:2659 passed / one skip in453.27 seconds; focused200 and92
  groups overlap. Complete optional probe passes on both repository and selected
  R12-A-fixed source. All preflight/source/input checks pass. After the invalid
  service control terminates, five prospective input/label tests pass again.
  No scientific validation of P15 benefits yet; no CVRP R19 launch or commit/push.
- P14 / R18 prelaunch: full suite 2622 passed / one skip in 446.02 s;
  focused groups 132 / 113 / 51 (overlapping), 17 prompt/input checks and
  independent cross-review pass. Initial full run's two old-schema fixture
  failures were corrected without production edits or weakened assertions;
  the entire suite was rerun. Read-only input/source/history/public-formal
  projection passes for both fresh designs. Pushed runtime/inputs `1596347c`:
  Warehouse completed2/2 valid ties at12:00:17 Beijing with48 successful calls;
  readonly/source/feedback/science audits pass with remaining C guidance and
  repeated-query limits documented. CVRP R18 started at12:04:15 Beijing and
  actual initial source/H inputs pass startup audit; no improvement claim yet.
- P13 / R17: 2554 passed, 1 skipped in 434.47 s; 163 focused provider/quota
  tests and ten R16/R17 input tests pass. Independent Warehouse completes 2/2
  valid negative stages with 70 successful calls, correct source continuation
  and no observed execution/scientific blocker. R17 completes 12/12, with 178
  valid pairs and negative validation. Query context and research-test limits
  are detailed in the October 4 postrun. Frozen runtime is now committed/pushed
  as `7e1fd7dc`. No tests/provider/solver rerun or runtime change in this audit.
- Branch: `v0.4-dev`. P1 and the handoff were committed as `a112e60c`;
  P1b and prospective R6 inputs were committed as `e405bfd2` before launch.
- P1b full suite: `2397 passed, 1 skipped, 0 failed` in 436.38 seconds, with no
  live provider or formal campaign. The earlier P1 suite passed 2393 tests.
  Focused P1b tests: 103 observation/evidence/boundary tests and 48 campaign/
  held-out regression tests. Arbitrary counter values do not alter Decision.
- Targeted Ruff (`F,E9`, excluding existing `F403,F405` star-import rules) and
  `git diff --check` passed. Three older fixtures now separate source/output
  directories; calibration projection tests use explicit fresh/stale dates.
- R6 and the independent Warehouse A/A control passed read-only `--check`.
  R6 gates/stage counts match R4; its source and data copies were compared
  directly, and all 11 seeds are disjoint from R3–R5 ledgers.
- [Warehouse wiring controls](docs/experiments/v0.4/v04-p1b-warehouse-aa-control-postrun-20260921.md):
  preserve the first incomplete shared-infeasible result; the second completed
  4/4 valid ties and deterministic `CONTINUE_EXPLORE` on the same runtime.
- R6 completed normally at expanded screening; terminal, all 24 raw pairs,
  case medians, feasibility/fleet equality, AB/BA order and both 100-file source
  snapshots have been checked. Performance contamination is disclosed above.
- R7 preparation: 143 existing focused tests plus 2 prospective-input tests
  pass (`145 passed` in 2.39 s combined). All 24 cases parse, scientific gates match R6, source selection and
  fresh output validate, and all prior observations project to H in order.
  No runtime implementation changed; no new full-suite or Warehouse run needed.
- R7 is completed without promotion. All 139 H/C traces, 12 metric files,
  90 complete pairs and three final complete source trees were checked read-only;
  earlier source continuation matched visible C inputs and the surviving trees.
- R8 inputs and fixed-funnel/R7 tests passed 27 tests before launch; R8 is now
  terminal. Both 100-file snapshots match their originals; all 48 formal arms,
  raw deltas, case medians and 12 AB/12 BA orders have been checked read-only.
- R9 preparation: 138 focused continuation/source-CLI/history/redteam/input/
  fixed-funnel tests passed in 2.25 s. All 24 formal cases plus canary parse,
  four observations project losslessly, and 101 prior rows yield 78 scientific
  H-only records. Runtime is unchanged. R9 is now terminal; all 92 traces,
  12 metric files / 144 pairs, final source trees and C branch continuation
  were checked read-only. Its initial 100-file champion equals R8's candidate.
- R10 preparation: 106 fixed-funnel/source-continuation/source-CLI/Code-session/
  R7–R10 input tests passed in 1.83 s. Ruff F/E9 and formatting pass. Read-only
  `--check` validates all 37 case inputs, exact three-file source difference,
  equal doubled formal limits and the 170-subprocess maximum without creating
  output or invoking a solver/provider. R10 subsequently launched once with
  runtime/inputs frozen; startup source and actual solver-limit checks passed.
  R8–R10 docs/input/test-only changes were committed and pushed as `841de42b`
  before R10 postrun analysis and R11 preparation. No implementation changed.
- R11 preparation: 208 focused tests passed in 2.75 s; all 25 case inputs
  parse, 113 ordered prior rows yield 90 H-visible records, and the four
  observations/new question project correctly. Startup source and actual H
  contexts are checked. R11 is now terminal; all 108 raw pairs, 101 traces,
  284 visible C source entries and three final 100-file trees were checked.
- R12 preparation: 211 focused tests passed in 2.81 s; all 25 case inputs
  parse, 125 ordered rows yield 102 scientific H-visible records; the question,
  four unchanged observations and held-out exclusion checks pass. Ruff F/E9,
  formatting, CLI help and diff checks pass. Startup source/actual H contexts
  are verified. New R10–R12 analysis/preparation work was uncommitted at launch.
- R13 independent repair: 136 CVRP/fixed-funnel/input tests passed in 71.21 s;
  four complete-solver checks on the exposed failing case pass active-algorithm,
  zero-error, coverage/capacity/fleet and independent objective/runtime-audit
  checks. Both 100-file copies have the identical minimal four-file repair;
  all 37 inputs and the unchanged 170-subprocess envelope pass `--check`.
  No source/Protocol/Decision gates weakened. R13 launched once; startup source
  and actual solver-limit checks pass. Code/inputs are frozen for measurement.
- R4 and R5 tmux panes are dead with exit status zero; their terminal JSON files
  report `NOT_CONFIRMED` and `DIAGNOSTIC_COMPLETE`, respectively.

Documentation does not replace code verification. Use
`/home/clawd/miniconda3/envs/claw/bin/python` for later focused/full tests, with
`PYTHONPATH=scion:.` from the repository root so imports use this checkout.

## Working discipline

Latest R14 preparation: 225 focused tests passed in 3.07 seconds, Ruff F/E9,
formatting/CLI/diff checks pass; all 25 cases parse and source/input/history
projection checks pass. No core/adapter/algorithm implementation changed.
R14 is terminal without promotion. The subsequent user explicitly authorized
team repair and a fresh experiment; P11 records that scope. R15 read-only
preparation passes (100 source files, 25 cases, 147 raw / 124 H-visible rows,
five observations). Shared-runtime repair verification/control is complete:
2471 passed / 1 skipped, independent Warehouse r2 valid negative, no framework
blocker. Its first input startup failure is preserved; input-only correction
has seven passing regressions. R15 started at 13:54:37 UTC, PID 289227;
source and actual H startup checks pass. Runtime/inputs are frozen. Work
was uncommitted at launch; the subsequent September 27 user request authorizes
committing and pushing this frozen change set. Git records the resulting
revision; the launch-time checkout description remains historical evidence.
The set was committed/pushed as `f73e89e7`. R15 subsequently completed at
22:04:54 UTC without promotion. September 28 analysis checks all 136 raw pairs,
125 traces, 374 visible C source values and three final complete trees; no
solver/provider/test rerun or runtime/input mutation. P11 and its postrun
record the remaining research issues. The subsequent user approval authorizes
P12 implementation, fresh control/CVRP experiments, commit and push.

- Read V3 before changing runtime ownership; prefer subtraction and ordinary
  values over registries, identities, gates, manifests, or proof lifecycles.
- Keep problem semantics in problem packages and generic research capability in
  Scion core.
- Use fresh experiment roots and never overwrite, resume, or rewrite terminal
  evidence.
- Freeze code and scientific inputs before spending provider/solver budget.
- Distinguish framework correctness, process health, scientific validity, and
  algorithm improvement. None implies the next.
- Never infer promotion from a positive screen, interrupted run, diagnostic
  ablation, natural-language summary, or reconstructed candidate.
