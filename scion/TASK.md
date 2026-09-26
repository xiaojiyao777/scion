# Scion v0.4 Continuous Solver Research

*Working branch: `v0.4-dev`*

*Current as of: 2026-09-26*

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
  The user now authorizes independent constructor remediation and a fresh
  common-repair comparison, not relabeling it as unchanged-B0 superiority.

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
- [ ] Analyze R13 terminal paired evidence before selecting another rung.

The user's subsequent September 26 request authorizes committing and pushing
the frozen R10–R13 work. This changes Git bookkeeping and handoff wording only;
R13's running algorithm and scientific inputs remain unchanged.

### v0.4 closeout

- [ ] Publish a compact cross-problem report separating framework correctness,
  research efficiency, algorithm quality, and retained improvement.
- [ ] Mark v0.4 complete only after CVRP also satisfies retained improvement;
  otherwise keep the exact next falsifiable rung open.

## Verification snapshot

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
