# Scion v0.4 Current State

*Current as of: 2026-10-05*

Enter through [`../../../AGENTS.md`](../../../AGENTS.md), then read
[`../AGENT_ONBOARDING.md`](../AGENT_ONBOARDING.md) before this snapshot and
[`../../TASK.md`](../../TASK.md) after it. The sole architecture authority is
[`../../design/scion-architecture-v3.md`](../../design/scion-architecture-v3.md);
the direct-runtime addendum only narrows the current implementation. Historical
plans and experiment reports preserve evidence but do not define current runtime
authority or authorize another run.

## Checkout and verification snapshot

- Working branch: `v0.4-dev`.
- P1 and the R4/R5 documentation handoff were committed as `a112e60c`.
  P1b observation cleanup and R6 preparation were committed as `e405bfd2`.
  R6 launched from that clean revision; subsequent status edits are docs-only.
- P1b full suite: `2397 passed, 1 skipped, 0 failed` in 436.38
  seconds, with no live provider or formal campaign. From the repository root:
  `env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests`.
  The explicit import path avoids this machine's older editable installation.
- Focused continuation tests cover cold-process startup, H-only history, source
  isolation, rollback, same-file sibling drift and exact held-out reuse.
  Targeted Ruff (`F,E9`, excluding existing star-import rules `F403,F405`) and
  `git diff --check` pass. Calendar-dependent calibration diagnostics are tested
  at explicit fresh/stale dates; runtime age limits are unchanged.
- P1b focused observation/evidence/boundary tests: 103 passed; additional
  campaign/held-out regression tests: 48 passed. The previous P1 suite passed
  2393 tests. Protocol gates and Safe Features are unchanged.
- R4, R5 and R6 are terminal. R6 ended normally at expanded screening as
  `NOT_CONFIRMED`; its terminal file was written by `16:44:12.811Z` on September
  21. Its tmux pane is now dead with status zero. Raw terminal and
  metric evidence below establish completion independently of the carrier.
- R7 completed normally at `2026-09-22T03:23:30.659934+00:00` after 12 evaluated
  screening stages and one Contract rejection. No promotion or held-out stage.
  Its final positive initial screen requests expansion, but the terminal campaign
  must not resume. The pane is dead; JSON, not carrier status, establishes completion.
- R8 completed normally as `NOT_CONFIRMED` at expanded screening by
  `2026-09-22T15:20:22.070227352+00:00`; pane dead with status zero. Runtime
  was unchanged; frozen docs/inputs/tests were subsequently pushed as `39b03166`.
- R9 completed normally at `2026-09-23T04:02:58.157595+00:00`: 12 screening
  stages, eight distinct candidates, 144 valid pairs, no promotion/held-out stage.
  Its 92 physical calls include two recovered typed timeouts; the 600-call cap
  was not exhausted. The pane is now dead with exit status zero; terminal facts
  come from ordinary status/summary and metrics, not the carrier.
- R8–R10 docs/inputs/tests were committed and pushed as `841de42b` under
  the user's September 23 request, before the following new analysis/preparation.
- R10 is terminal: `completed_incomplete` /
  `INCOMPLETE_COMPARATOR_EVIDENCE` at validation, terminal written by
  `2026-09-23T16:38:14.659955255Z`; pane dead exit zero. Expanded screening
  passed: 24 valid pairs, W/L/T 3/0/3, median 19.75, CI [0,179]. Validation
  executed all 12 pairs but two failed in both arms at shared construction.
  No promotion, frozen or retained evidence. Both 100-file snapshots still
  equal their originals; all 36 formal pair orders/limits and valid deltas
  were checked. See the operator-only postrun and exact raw refs below.
- R11 completed normally at `2026-09-24T05:58:23.243135+00:00`, 12 screening
  stages / ten distinct candidates, 108 valid pairs, no promotion or held-out
  stage; pane dead exit zero. All 101 provider traces, raw pairs, visible C
  source values and three final complete trees were checked read-only.
  One typed H 502 recovered on the same frozen request; no cap exhaustion.
- R12 is terminal: final status `2026-09-24T18:01:02.790088+00:00`,
  `EVALUATION_CHAMPION_EVIDENCE_BLOCKED` at validation; pane dead exit 20.
  Nine screening stages / six candidates yielded 108 valid pairs; final A
  passed expanded screening +2.25 [0,11.25], 3/0/3. Validation attempted 12
  pairs, ten valid / two shared construction failures, no Decision/promotion.
  All 62 provider calls succeeded; 131 visible C source values and all three
  complete 100-file final trees match. No global resource cap was exhausted.
- September 26 user authorization: independent GPT-6-Astra constructor repair,
  concurrent remaining design, then a fresh run only after checks. The repair
  is problem-owned engineering, not autonomous Scion research: construction.py
  plus three caller files, preserving successful greedy paths and explicit
  failures. No core, adapter, Protocol or Decision implementation changes.
  Same minimal patch applied to fresh B0-fixed and R12-A-fixed complete copies;
  original B0/R10/R12 sources and evidence stay untouched. Independent checks:
  136 tests pass in 71.21 s, four complete-solver correctness diagnostics pass,
  exact same four-file repair in both 100-file copies, source scope and all
  37 inputs pass read-only preparation. See R13 and the engineering report.
  At R13 launch, prior R10–R12 and new R13 work were uncommitted atop pushed
  `841de42b`. The user's subsequent September 26 request authorizes committing
  and pushing this frozen change set; no running algorithm/input is changed.
- R10–R13 analysis/preparation and the common constructor repair were committed
  and pushed as `964a9622`; September 27 entry checks found a clean checkout.
- R13 completed normally as `NOT_CONFIRMED` at expanded screening, terminal
  written by `2026-09-26T02:22:17.944813+00:00`. All 24 pairs are valid,
  W/L/T 4/1/1, median +91.5, CI [-36,296.75], uncertain against B0-fixed.
  No validation/frozen/retained or promotion. Pane dead (no exit-status value);
  JSON establishes completion. Both 100-file snapshots match their sources;
  12 AB/12 BA, all limits, objective differences and runtime safety checked.
  The constructor repair has engineering evidence but R13 did not test the
  formerly failing formal validation matrix. See the bounded postrun below.
- R14 completed normally at `2026-09-27T08:44:52.323359+00:00`: twelve
  screening stages / ten evaluated candidates, 108 valid pairs, no promotion
  or held-out execution. All 120 provider calls succeed; 480 of 600 remain.
  One Code attempt abandoned after four opaque preflight rejections. All 302
  visible C source values and three complete final trees match branch history.
  Persistent research works, but C's missing preflight reasons and H's
  cumulative-source attribution need attention. See the postrun below.
  The subsequent status/diagnosis audit made no runtime edit or launch.
- September 27 follow-up explicitly authorizes subagents to repair research
  feedback and then launch fresh R15. Safe typed C preflight reasons and
  problem-neutral cumulative-source/comparator guidance are implemented;
  2471 tests pass / one skip, focused regressions and independent review pass.
  Warehouse r2 completes two valid negative H/C screening stages after the
  first input correctly failed public/formal-overlap checks before execution.
  R15 keeps R12-A-fixed as its complete starting tree, appends all R14 history,
  and prospectively broadens initial screening to five cases (including
  X190/X513), with strict six-case/four-seed expansion and unchanged gates.
  R15 started once at 13:54:37 UTC, PID 289227. All 100 initial files match;
  first actual H calls succeed with exact question, five observations and
  124 prior-history entries. The frozen R13–R15 set was committed/pushed as
  `f73e89e7`; no running runtime/input changed. Launch provenance is preserved.
- R15 completed normally at `2026-09-27T22:04:54.956555+00:00`: twelve
  evaluated stages (eleven screening, one validation), ten distinct evaluated
  candidates, 136 valid pairs and no promotion. All 125 calls succeed; 475 of
  600 remain. Ejection-chain expanded screening passes +11.5 [0,43.25], then
  complete validation fails -39.75 [-459.5,2.75], 1/4/1. Shared construction
  does not block this matrix. Final fresh SWAP* candidate is only initial
  +9 [-140,16], expansion pending at terminal stop. Frozen/retained unopened.
  All 374 visible C source values and three surviving 100-file trees match.
  Three A-branch candidates target an inactive >2000-customer path; one C
  revision calls unimplemented real methods hidden by a mock self-test and is
  correctly rejected by V5. R15 self-test failure feedback was opaque.
- The initial September 28 request was analysis only. The subsequent user approval
  authorizes safe self-test diagnostics and optional real-entry/integration
  support, followed by a fresh run, Git commit and push (TASK P12). Diagnostics and optional
  real-entry examples are implemented; full suite 2514 passed / 1 skipped
  (426.78 s), focused/security/input checks and exact H/C source/input
  projection pass. [R16 design](../experiments/v0.4/v04-cvrp-r16-probe-diagnostics-autonomous-preregistration-20260928.md)
  and [Warehouse control](../experiments/v0.4/v04-r16-warehouse-probe-control-20260928.md)
  were prospectively frozen and committed as `d67f9800` before measurement.
  Warehouse ended at 15:43:16 UTC as valid_incomplete: only 1/2 requested
  stages at its unchanged 80-call cap. One complete valid tie and actual safe
  failed-probe hint, 52 exact C source values, no framework blocker; 35
  source/schema tool errors remain a research-efficiency limitation. The
  incomplete control is not relabeled complete; its limited launch rationale
  is recorded. No control outcome enters CVRP H/C.
  R16 launched once at 15:48:59 UTC, PID 331499; [terminal status](/home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928/status.json).
  All 100 initial files match; actual H calls succeed with the exact question,
  136 prior-history plus five observation indexes and new guidance. No formal
  result at that launch snapshot. Runtime/inputs match d67f9800; the docs-only
  handoff was pushed as `505dce03`. October 3 entry found a clean checkout there.
- [R16 postrun](../experiments/v0.4/v04-cvrp-r16-probe-diagnostics-autonomous-postrun-20261003.md):
  stopped September 30 at 15:49:01 UTC, `OUTER_HARDWALL_EXCEEDED`,
  valid_incomplete, 7/12 stages and 86 valid pairs; no promotion. All formal
  metrics precede the September 28 20:38:49 account-quota 429. Fifty successful
  calls are followed by 196 failed dispatches (one quota 429, 195 synthetic
  no-usable-account 401s), 65 operational attempt rejections and a final
  interrupted attempt. 246/600 calls used, 354 remain: not call-cap exhaustion.
  The persistent outage lasts another 43 h 10 m until the 48-hour guard.
  Expanded +4.75 [0,16.75] passes, complete validation 0 [-12.5,1302.75]
  fails case quality (2/2/2); later outage does not invalidate those pairs.
  All 140 visible C source values and three surviving 100-file heads match.
  Both failed-probe hints reach C, but forced sweep activation (>1500 customer
  production threshold) and mock-only dispatch checks remain reasoning limits.
  Frozen/retained unopened. The initial October 3 inspection did not change
  runtime or relaunch. The subsequent follow-up now approves the proposed
  quota-stop fix and fresh R17 after checks, not Git commit/push or R16 resume.
- P13: explicit HTTP 429 usage quota exhaustion now follows the existing
  balance/resource terminal lane; ordinary transient faults keep bounded retry.
  No algorithm/gate/prompt change or outage/recovery state. Focused tests:
  163 provider/quota/client plus ten R16/R17 input tests pass. Full suite:
  2554 passed, 1 skipped in 434.47 s. [R17 preregistration](../experiments/v0.4/v04-cvrp-r17-quota-aware-autonomous-preregistration-20261003.md)
  and [independent Warehouse control](../experiments/v0.4/v04-r17-warehouse-quota-control-20261003.md)
  are executed. Warehouse completes 2/2 at 13:35:48 UTC, valid, pane exit0;
  70/80 successful calls, two valid ties, two research rejections, no framework
  blocker. All 406 source files and 45 visible C values match, including exact
  accepted-head continuation. Query inefficiency remains. CVRP R17 launches
  once at 13:40:12 UTC, PID 460131; [live status](/home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/status.json).
  Same R12-A-fixed source, unchanged scientific
  gates/budgets and all safe R16 history. Runtime is 505dce03 plus the frozen
  uncommitted transport/error repair. One bounded real inference succeeds at
  13:21 UTC; initial source/data/closure/production and exact H projection pass.
  No competing tests/solver/maintenance at either launch. Freeze all runtime
  and inputs until both measurements finish; only status docs may change.
  R17 startup checks pass: all 100 champion files equal the selected source;
  actual first H succeeds at attempt0 on gpt-5.6-sol with the exact 10,347-character
  question and 147-entry index (142 safe history rows, five observations).
  Those are launch-time facts, superseded by the terminal audit below.
- October 4 request: commit/push preceding work first, then read-only experiment
  analysis and query-efficiency diagnosis. `7e1fd7dc` is pushed to
  `origin/v0.4-dev`; it captures the frozen P13 runtime/tests/inputs and handoff.
  [R17 postrun](../experiments/v0.4/v04-cvrp-r17-quota-aware-autonomous-postrun-20261004.md):
  completed October 3 23:24:56 UTC (October 4 07:24:56 Asia/Shanghai), valid,
  12/12 stages, 178/178 valid pairs, seven candidates, 69/600 successful calls,
  zero research rejections, no quota event and no promotion. Final expanded
  screen +15.25 [1.5,82], 5/0/1; validation -1.5 [-2933.75,824], 2/3/1,
  VALIDATION_FAIL_CASE_QUALITY. Frozen/retained unopened. All 146 visible C
  source values match branch bases; champion and surviving B/C have complete
  100-file source matches. Abandoned A has no surviving full stage tree;
  changed values remain, but full-stage source attribution is limited.
  Real algorithm work exists; exact-kernel equivalence, real scheduler probes
  and self-authored test oracles remain research limitations. No rerun here.
- Query-efficiency diagnosis: Warehouse has 28 failed queries plus two patch
  selector errors in 43 C turns. Its frozen public `models.py` dependency is
  genuinely absent from the query corpus (context-composition gap), while eleven
  searches wrongly supply an empty path and the model repeats unavailable reads.
  Earlier "no framework blocker" refers to exercised execution/scientific gates,
  not a defect-free research interface. CVRP R17 has only one failed query plus
  one duplicate-file patch error; query waste does not explain its validation
  failure. Further repairs/control/experiments are proposed, not authorized by
  the October 4 inspection request; no runtime/input change has been made.

A new session must re-run the ordinary read-only `git` and tmux checks in
`AGENTS.md`. A commit label, tmux pane, summary, or this prose is not scientific
authority; read the exact terminal and metric artifacts linked below.

### Current authorized implementation

October 5 request authorizes terminal analysis, optimization and a fresh experiment,
prioritizing test reliability, actual execution paths and stable gains (TASK P15).
No new Git commit/push or historical resume is requested. Entry is at pushed
`484433ea`, preserving the three preceding R18 analysis/status edits; all carriers
were dead at entry. P14 runtime/inputs were pushed as `1596347c`; later pre-P15 changes are
documentation only.

[R18 terminal analysis](../experiments/v0.4/v04-cvrp-r18-research-context-autonomous-preregistration-20261004.md#terminal-analysis-october-5):
completed/valid October4 21:56:58 Beijing,12/12 screening stages, eight cumulative
candidates,176/176 valid pairs, no promotion/validation/frozen. All352 solver sides
are feasible with fleet_violation0 and empty errors. H40 successful; C49 includes
one recovered timeout;511/600 calls remain. A3's initial X351 +1712.5 does not
survive expansion: X351 -501.5, seed deltas +3791,+1537,-2714,-2540; complete
expanded W/L/T1/2/3, median0 [-255.5,0.25]. Last B3 initial2/1/2, median0
[-12.5,25] requests expansion but terminal R18 must not resume.

B3's true-displacement claim is not implemented: its materializer removes a
resident then requires that customer to remain in the source at the next step,
rejecting genuine multi-step chains. C identifies the bug but three repairs select
draft text against the original edit base and fail; ready retains draft1. Passing
host checks and activation counters do not establish that transition. This is
research-correctness debt, not an observed formal feasibility failure.

Terminal source audit checks299 editable C values,833 readonly values,98 public
tests across49 C contexts,40 H visible values and champion/A3/B3/C2 complete
100-file trees. Frozen public tests match `1596347c`, not the new P15 examples.
All raw pair deltas/case medians/aggregate medians reconcile. Five superseded
complete stage trees are absent; do not reconstruct executable historical
candidates or overclaim full-stage attribution. Raw R18/SQLite stay untouched.

P15 implemented and under verification: bounded no-tests-collected feedback,
independent expected-value/collection guidance, explicit full-draft replacement
against the original session source, optional rational reference and multishape/
seed real-entry examples preserving real collaborators and guards. No failed
exact-patch rule, host gate, solver algorithm or private-data boundary is relaxed.
Focused200 probe/development tests and92 revision/input tests pass (overlapping).
The complete optional example passes on unchanged selected R12-A-fixed source
within ten seconds. Full suite2659 passed / one skip in453.27 seconds; Ruff/diff
checks pass. Preflight validates100 CVRP files/25 cases, five Warehouse cases,
public/formal closure and exact13,556-character question with165 safe histories
plus five observations (170 entries). Warehouse starts once October5 14:21:18
Beijing, PID530783, after a successful bounded service inference, then stops at
14:37:22 with **0/2 evaluated stages**, invalid_no_evaluated_outcome, pane exit21.
All80 calls are used:37 successful,43 explicit upstream overloaded-server502
failures; no quota429 or local test failure. Eight operational attempt rejections
and a ninth call-cap stop produce no scientific history/metrics or accepted C
candidate. All34 bounded redispatches preserve their exact request.137 H visible
bodies,16 editable C values,144 readonly values,32 public tests and the unchanged
406-file champion match. Actual no-tests feedback, correction and formal gates
are not exercised; regression coverage is not completed live-control evidence.
CVRP has not launched and its output does not exist. After service recovery,
preregister a new complete control with fresh output/seeds before CVRP. Never
resume the exhausted control or silently enlarge its cap. Executed Warehouse
inputs retain their disclosed old descriptive version labels; after terminal,
unexecuted CVRP labels and one regression assertion are corrected only. Five
input tests pass again; no runtime, seed value, population or gate changes.

[Fresh R19 design](../experiments/v0.4/v04-cvrp-r19-reliable-probes-autonomous-preregistration-20261005.md)
and [Warehouse control](../experiments/v0.4/v04-r19-warehouse-reliable-probes-control-20261005.md)
record the prepared design and terminal service failure. R19 keeps the unchanged100-file R12-A-fixed starting tree and
all eighteen whole safe-history files, adding all twelve R18 screening records.
Initial five cases×four seeds and required six-case×six-seed expansion increase
sampling only; thresholds, per-solve limits, held-out populations,12 stages,
600 calls and48-hour cap remain unchanged. No candidate merge or host-selected
mechanism. Fresh two-stage/80-call Warehouse control on the same runtime must
precede CVRP launch and be audited honestly. Known readonly/import/query research
inefficiencies remain, and more seeds do not remove champion-first ordering,
adaptive known-case exposure or missing matched calibration.

The control's runtime/inputs stayed frozen through terminal; no tests, competing
solvers, maintenance or runtime/input edits overlapped measurement. No campaign
was running at that terminal audit. The fresh control below freezes its own
prospective inputs before dispatch. Keep negative science, invalid no-evaluation service
runs, incomplete coverage and retained improvement distinct. No new commit/push.

October5 follow-up selects gpt-6.1-sol high. The
[Sol Warehouse control](../experiments/v0.4/v04-r19-warehouse-reliable-probes-sol61-control-20261005.md)
completed/valid at16:36:07 Beijing:2/2 screens, four attempts,78/80 calls,
77 successes and one recovered H502. Two research attempts abandon on C8.
Both evaluated candidates pass public checks/final probes, Verification and
canary, then tie small_6/seed240007; elapsed715/385 and524/376 ms. No expansion,
held-out or promotion. All48 editable/432 readonly/96 public-test visible C
bodies match; surviving trees change only their operator and registry.yaml.
Original evidence/inputs remain unchanged. Service works in this run; neither
model retirement nor resource reallocation is established.

Latest approval permits continuing scoped optimization and a fresh experiment,
still without Git commit/push. P16 repairs a concrete shared-context gap: the
internal import whitelist did not reach final C rendering. Actual C8 absolute
roots now share one implementation with target guidance; optional rejection
source_line points into the submitted editable draft. Acceptance/import/API
rules are unchanged. Generic optional testing guidance separates forced wiring,
ordinary activation, completed transitions and improvement. No algorithm edit,
new quality gate, provider retry, cap expansion or private-data exposure.
197 focused regressions pass;42 additional context/import tests pass (overlap).
Full suite2678 passed / one skip in451.05 seconds;24 input tests, Ruff/diff and
source/data/context checks pass. Bounded model inference succeeds18:25:59 Beijing.
Runtime/inputs are frozen for the new
[import-feedback control](../experiments/v0.4/v04-r19-warehouse-import-feedback-control-20261005.md).
It starts once18:26:58 Beijing /10:26:58 UTC, PID543472; startup running0/2.
All406 champion files match; first two actual H calls succeed at attempt0 on
gpt-6.1-sol. Stored limits and unchanged production diff pass startup audit.
That fresh2-stage/80-call control uses primes above250000 and unchanged source,
populations/gates. CVRP R19 remains unlaunched; its prepared four-/six-seed
design, complete R12-A-fixed source and safe histories are unchanged, pending
the new runtime's complete control. No tests/solvers/maintenance or runtime/input
edits during measurement. Never resume either prior control.

Subsequent October5 request explicitly authorizes Git commit/push of this frozen
P15/P16 change set. The follow-up asks whether CVRP R19 can start; its existing
complete-control and nonoverlap conditions remain unchanged. Read-only inspection
at18:31 Beijing finds the import-feedback control still running,0/2 evaluated
stages, first Code research in progress. CVRP is not launched. Committing the
unchanged runtime/inputs does not change the control's launch-time provenance
(`484433ea` plus then-uncommitted P15/P16); no tests or competing solver are run.

## Current runtime truth

Scion is a problem-neutral research engine. Problem algorithms, objective and
feasibility semantics, research surfaces, checks, protocol inputs, and telemetry
meanings stay in problem-owned packages. Generic core only carries typed values
through this path:

```text
problem adapter + complete safe source/history
  -> agent H research -> tainted H -> Hypothesis Contract
  -> agent C research -> tainted C -> Patch Contract
  -> isolated complete candidate workspace -> Verification
  -> problem-owned Protocol -> Safe Features -> deterministic Decision
  -> exact stage reuse, branch continuation, or promotion
```

### Persistent algorithm research space

Within a live campaign, a branch's `current` value is a complete ordinary source
tree. After Contract and Verification pass and screening completes,
`CONTINUE_EXPLORE` retains that candidate as the branch's verified provisional
head even when the scientific screen fails. The next H receives the complete safe
screening evidence and the next C edits that complete source tree. Contract or
Verification failure falls back to the last clean branch source; held-out stages
reuse the exact candidate and cannot be bypassed.

This live-branch path gives the agent depth without a host mechanism selector.
When a champion change makes another branch stale, reconcile now copies that
branch's already materialized complete tree for isolated Verification and fresh
screening against the new champion. It does not replay accepted patches or merge
champion edits. Prior H/C records remain evidence. Missing source holds the
invocation rather than reconstructing code. Decision reanchors the comparator
and resets expansion counts; later held-out stages reuse the exact candidate.

CLI `--source-tree` explicitly selects an ordinary complete directory as a fresh
baseline; absent that option, the problem root is used. Campaign composition
copies the initial source into a read-only champion snapshot. CLI versions,
branches, stages and provider counters start fresh, with optional ordered H-only
`--research-history`. Status exposes `initial_source_tree`,
`champion_source_tree` and `branches[].source_tree` as ordinary paths.

P1b replaces the seven fixed operator/policy/construction/portfolio Protocol
counter attributes with `candidate_runtime_counters`, aggregated from existing
problem declarations and carried opaquely into evidence summaries. Scalar/event
raw observations no longer use an algorithm-prefix allowlist. The host no longer
infers failure from attempted-but-unaccepted moves; actual runtime audit and
Protocol/Decision gates are unchanged. Arbitrary problem counters are excluded
from held-out exposed summaries. Historical artifacts are not rewritten.

`OperatorConfig`, `ChampionState.operator_pool` and their legacy configuration
management remain separate debt. Core has no direct Warehouse/CVRP branch, but
these interfaces still assume an algorithm shape. Terminal or interrupted
campaign state itself must not be resumed.

The source-continuation slice adds no identities, digest authority, manifests, leases,
signing, registration, receipts or reconstruction lifecycle.
Do not add another operator/mechanism field to generic runtime.
Keep future configuration cleanup separate and test-bounded; do not make it a
new scientific gate.

### Provider and bounded-session semantics

- Provider SDK retries are zero. An explicit ResourceEnvelope may redispatch the
  same frozen request a finite number of times after typed transient failures;
  every physical dispatch is charged and best-effort traced.
- Exhausting transient redispatches or a local turn/result/transcript bound after a
  session has started rejects only that attempt and schedules a fresh H. These
  operational rows do not become algorithm-failure history.
- H/C transcript total characters are unbounded by default. If a user explicitly
  sets a bound that the complete initial H context cannot satisfy before the first
  dispatch, the invocation remains `RESOURCE_EXHAUSTED`; source/history must not be
  truncated, ranked, compacted, or summarized to fit.
- A passing Code draft exported with `ready` is terminal for that session and does
  not require a second provider confirmation or closure. If the turn loop ends with
  an already passing frozen draft but no `ready`, the one final decision is only
  `finalize_patch` or `abandon`.
- The local proxy's exact synthetic no-usable-account 401 is temporary provider
  unavailability. Real/non-exact authentication, balance, explicit global call cap,
  missing provider terminal response, invalid local context, missing typed outcome,
  and interruption remain terminal or hold outcomes.
- Explicit usage-quota 429 is balance/resource exhaustion, not ordinary rate
  throttling: stop after its charged trace, no redispatch/fresh H, no algorithm
  history. Recovery permits a new campaign only, never a terminal resume.

Contract, Verification, complete-pair Protocol, held-out isolation, feasibility,
protected objectives, and deterministic Decision remain necessary research
boundaries. Algorithm novelty, host mechanism preference, telemetry prose, and
incidental operational limits are not promotion gates.

## Accepted scientific state

Warehouse has demonstrated retained improvement: synthetic Scion promoted and
independently retained `v1 -> v2 -> v3`, and production-style Scion promoted and
independently retained `v1 -> v2`.

CVRP remains open:

- [`R3i`](../experiments/v0.4/v04-cvrp-r3i-long-run-adaptive-history-postrun-20260904.md)
  promoted cumulative v2 after complete expanded screening, validation, and frozen
  passes. The bundle combines dynamic perturbation frontier, post-repair
  admissibility/small-route consolidation, orientation-changing 2-opt-star, and
  inter-route 2-for-1. This is exact-bundle evidence, not component causality or
  retained superiority over original B0. R3i later stopped on provider/proxy
  infrastructure and is terminal, not resumable.
- [`R4 postrun`](../experiments/v0.4/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-postrun-20260905.md)
  compared exact v2 directly with original R3i B0 on a fresh effect population.
  It completed normally as `NOT_CONFIRMED` at expanded screening: 24/24 valid
  pairs, no failures or fleet regression, case W/L/T `1/0/5`, median distance
  delta `0`, CI `[0,130.5]`, and `SCREENING_FAIL_CASE_QUALITY`. The sole winning
  case reversed sign across seeds. R4 therefore found safe but sparse/unstable
  benefit and did not expose validation, frozen, or retained stages. See the
  [terminal](/home/clawd/research/scion-experiments/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904/terminal.json)
  and [metric](/home/clawd/research/scion-experiments/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904/metrics/ab7e221a-0d68-497c-a18e-87e80451cfe1.json).
- [`R5 postrun`](../experiments/v0.4/v04-cvrp-r5-v2-2for1-ablation-postrun-20260905.md)
  records a provider-free, case-conditioned diagnostic of exact full v2 versus an
  ordinary v2 copy with only the `_exchange_2_for_1` registry entry removed. It
  completed normally as `DIAGNOSTIC_COMPLETE`: 24/24 valid pairs, no failures or
  fleet regression, case W/L/T `0/2/4`, median `0`, CI `[-281.75,0]`, and
  essentially equal runtime. On this already outcome-known R4 population, the
  result does not support including 2-for-1 and is compatible with harm on two
  cases. It is diagnostic only and cannot promote either arm. See the
  [preregistration](/home/clawd/research/scion-experiment-inputs/v04-cvrp-r5-v2-2for1-ablation-20260904/PREREGISTRATION.md),
  [terminal](/home/clawd/research/scion-experiments/v04-cvrp-r5-v2-2for1-ablation-20260904/terminal.json),
  and [metric](/home/clawd/research/scion-experiments/v04-cvrp-r5-v2-2for1-ablation-20260904/metrics/72cbb5bf-1b86-4f12-aa7c-b4ba1d8e21b7.json).

- [R6 postrun](../experiments/v0.4/v04-cvrp-r6-minus-2for1-b0-postrun-20260921.md):
  exact minus-2-for-1 versus original B0 completed 24/24 valid pairs, with no
  failures or fleet regression. Case W/L/T `2/1/3`, median `0`, CI
  `[-258,97.75]`; `SCREENING_FAIL_CASE_QUALITY` / `CONTINUE_EXPLORE`, terminal
  `NOT_CONFIRMED`. Later stages stayed unopened. X-n351-k40 lost at all four
  seeds. Both arms on both large cases had zero ALNS iterations after initial
  VNS consumed the algorithm-local budget. This is observational, not component
  causality. Server cleanup overlapped R6; its performance estimates are
  exploratory because host resource contention cannot be bounded. The original
  negative Decision is preserved. Exact
  [terminal](/home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/terminal.json)
  and [metric](/home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/metrics/c9a5fe82-83d3-4897-8ea8-3b428b1c208b.json).

Neither v2 nor minus-2-for-1 is a confirmed retained-B0 improvement. Both are
ordinary complete source values. Selecting the latter as R7's fresh local
baseline does not confer that scientific status.

- [R7 postrun](../experiments/v0.4/v04-cvrp-r7-autonomous-source-continuation-postrun-20260922.md):
  139 provider dispatches, 12 H/C attempts, 11 distinct evaluated candidates,
  12 screening stages, 90/90 valid pairs and no fleet regression. One positive
  initial screen became negative on expansion. The final C-branch candidate
  (`candidate-3bsvzm8k`) instead finished at initial W/L/T `2/0/1`, median `40`,
  CI `[0,608.5]`, with `SCREENING_EXPAND_REQUIRED_FOR_PASS`; no promotion.
  All three surviving complete branch trees match ordinary C continuation.
  X-n351-k40 ran zero ALNS iterations in both arms across all 26 pairs, and
  identical-comparator repeats vary greatly. Its final positive delta cannot
  be attributed to the changed ALNS code; tai100a's +38/+42 is only a discovery
  signal. R7's default champion-first order was not counterbalanced. Exact
  [summary](/home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/campaign_summary.json)
  and [final metric](/home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/metrics/24ac3290-cb42-4a19-bcd4-46f36fe4fc65.json).

- [R8 postrun](../experiments/v0.4/v04-cvrp-r8-r7-final-b0-postrun-20260922.md):
  exact R7 final candidate versus original B0, 24/24 valid pairs, 12 AB/12 BA,
  no failures or fleet regression; case W/L/T `1/1/4`, median `0`, CI
  `[-159.5,71.75]`, `NOT_CONFIRMED` / `SCREENING_FAIL_CASE_QUALITY`. tai100a
  wins all four seeds (+143.5 case median), X-n351-k40 loses three (-319 median),
  four cases tie. Both large cases have zero ALNS iterations; X-n190-k8 has
  only 1–3 candidate iterations. These are whole-bundle observations, not
  component causality. Validation/frozen/retained stayed unopened. Exact
  [terminal](/home/clawd/research/scion-experiments/v04-cvrp-r8-r7-final-b0-20260922/terminal.json)
  and [metric](/home/clawd/research/scion-experiments/v04-cvrp-r8-r7-final-b0-20260922/metrics/78267022-b4e9-4e7d-be18-6d43be40f9d9.json).

R9 [postrun](../experiments/v0.4/v04-cvrp-r9-post-b0-autonomous-postrun-20260923.md):
the final C expanded result is 2/0/4, median 0, CI [0,170.25], uncertain;
final B is 1/2/3, median 0, CI [-154,22.75], failed case quality. Three positive
initial screens did not survive expansion. Both arms had zero ALNS iterations
on all 48 large-case pairs. Count-based VNS allowances are not time quotas;
one proposed yield controller was absent from its final exported source.
All three surviving complete branch trees are identified; no original-B0
improvement is established. Exact
[summary](/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/campaign_summary.json),
[C expanded metric](/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/metrics/8458fb2b-7cf5-4e34-930c-3f23daf567f7.json),
and [B expanded metric](/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/metrics/c2d635b6-6196-44be-be4a-1a0220bd8701.json).

R10 [postrun](../experiments/v0.4/v04-cvrp-r10-wide-budget-b0-postrun-20260923.md):
the equal wider-budget comparison establishes a screening pass, not retained
improvement. X-n513-k21 wins all four seeds by 198 despite zero candidate ALNS
iterations; X-n351-k40 has mixed signs and zero ALNS in both arms. Validation
is incomplete due to a shared construction failure; it is now operator-exposed,
not unopened. Its valid-subset effects must not replace the complete matrix.
Exact [terminal](/home/clawd/research/scion-experiments/v04-cvrp-r10-wide-budget-b0-20260923/terminal.json),
[screening](/home/clawd/research/scion-experiments/v04-cvrp-r10-wide-budget-b0-20260923/metrics/b749b312-cde2-4e05-8856-1898d0ab4bba.json)
and [operator-only validation](/home/clawd/research/scion-experiments/v04-cvrp-r10-wide-budget-b0-20260923/metrics/edac77fa-c07e-44c0-9f5d-5a25d0e2fa2c.json).
Frozen and the independent pre-R3 retained block remain unopened.

R11 [postrun](../experiments/v0.4/v04-cvrp-r11-wide-budget-autonomous-postrun-20260924.md):
final B expanded W/L/T 3/1/2, median +10, CI [-1,216.75], uncertain against
the local R10-candidate champion, not B0. Its tai100a and both large-case effects
are positive at every seed, with small-case regression. Final A has a large-case
-8557 median; final C ends negative. Early phase handoffs are guarded above
2000 customers and never activate on the <=512-customer screening population.
All X-n351 pairs and final-B X-n513 pairs still have zero ALNS. Increased
throughput alone did not guarantee better distance. Exact
[summary](/home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923/campaign_summary.json)
and [final B metric](/home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923/metrics/892458a5-2492-4162-a58e-7331266c898a.json).

R12 [postrun](../experiments/v0.4/v04-cvrp-r12-post-r11-autonomous-postrun-20260926.md):
final A expanded screening passes narrowly against R11 B, not original B0.
Both large screening cases still execute zero ALNS, so lazy worst removal
cannot receive credit for their effects. B/C variants are negative/uncertain;
C's two-pair cap hides an exhaustive opportunity-ranking scan. One multi-file
patch was correctly rejected for a primary-target mismatch and never entered
the branch head. Validation repeats the R10 constructor failure; valid-subset
effects include losses and cannot replace a full verdict. Exact
[status](/home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/status.json),
[A screening](/home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/metrics/182c2070-66b6-407b-997e-bf4a8269d8bf.json),
and [operator-only validation](/home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/metrics/4d029e0f-ec63-4525-b960-3b99bdc48e24.json).

## Active next work

1. Preserve R4–R13 postruns and original terminal/source roots. R10/R12 are
   scientifically incomplete; R11 completed without promotion. Never resume them.
2. P1 source continuation and P1b observation cleanup are implemented.
   Legacy configuration/pool terminology remains separate debt.
3. CVRP is open. The unchanged necessary held-out and runtime-audit gates
   must preserve the R10 comparator failure. Do not patch original B0, drop
   a failed validation case, leak held-out diagnostics to H/C or backfill evidence.
4. [R13 postrun](../experiments/v0.4/v04-cvrp-r13-constructor-fixed-b0-postrun-20260927.md)
   preserves broader positive but uncertain screening versus B0-fixed, not
   unchanged B0. X-n190 median -72 remains unstable; its 2–4 candidate ALNS
   iterations spend 57.786–64.337 seconds in embedded VNS. Both large cases
   still have zero candidate ALNS. These are bundle observations, not causal
   attribution. Exact [terminal](/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/terminal.json)
   and [metric](/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/metrics/361aae52-87e4-4628-84ca-fd921a6efa77.json).
5. [R14 postrun](../experiments/v0.4/v04-cvrp-r14-post-r13-autonomous-postrun-20260927.md)
   records valid non-promotion and two actionable gaps: preflight drops C8/C9
   rejection reasons before C sees them; the final one-hop proposal retains
   the preceding failed time quantum despite its alternative-method rationale.
   All X-n351 pairs have zero ALNS; later X-n190-focused proposals were only
   initial-screened without X-n190. Preserve these scope limits and Decisions.
   The user authorized bounded safe feedback repair and prospective
   cumulative-source/population design, then a fresh run. Do not resume R14.
   [R15 preregistration](../experiments/v0.4/v04-cvrp-r15-feedback-repair-autonomous-preregistration-20260927.md)
   and [independent Warehouse control](../experiments/v0.4/v04-r15-warehouse-feedback-control-20260927.md)
   are prepared. Full suite: 2471 passed, 1 skipped in 430.51 s. Warehouse
   first control startup correctly rejected public-test/formal case overlap,
   before provider/solver/output. The [input-only r2 correction](../experiments/v0.4/v04-r15-warehouse-feedback-control-r2-20260927.md)
   passes full closure checks and completed at 13:51:19 UTC: two valid
   negative stages, no framework blocker. Actual source fidelity is verified;
   sibling-inheritance wording remains a model reasoning limitation.
   R15 is now terminal; see the
   [read-only postrun](../experiments/v0.4/v04-cvrp-r15-feedback-repair-autonomous-postrun-20260928.md),
   [status](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/status.json),
   [expanded screen](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/metrics/1bb82728-0573-458e-b424-f52691e80f3e.json),
   [operator-only validation](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/metrics/4e5b9aba-3bd9-43d6-a1af-d07524fb040e.json)
   and [last initial screen](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/metrics/52df4158-65c7-4889-90b9-050cbcd5a1ae.json).
   Complete validation rejects the candidate on quality, not comparator failure.
   Preserve the localized X351 discovery separately from the last SWAP* signal.
   Authorized P12 support is implemented; R16 is now terminal valid_incomplete,
   with the partial Warehouse control caveat above. Its
   [read-only postrun](../experiments/v0.4/v04-cvrp-r16-probe-diagnostics-autonomous-postrun-20261003.md)
   separates completed negative validation from the subsequent quota outage.
   Safe hints work; production-path reasoning and probe coverage remain limited.
   October 3 follow-up approves the narrow quota-stop repair and fresh R17.
   Full tests, provider inference and independent Warehouse audit now pass;
   R17 subsequently completed all 12 stages; the October 4 request authorized
   commit/push (`7e1fd7dc`, done) and the linked read-only postrun, not a new run.
   Retain the negative validation and source/probe limitations. The subsequent
   approval authorizes P14; its source/feedback/probe repairs are implemented
   and pass full regression; pushed `1596347c` has completed its Warehouse control
   and started fresh R18 as linked above. Its ten-stage interim H/C/metric audit
   finds no confirmed improvement; next inspect its normal terminal evidence,
   including the still-running A3 expanded screen. Do not extrapolate its two-seed
   X351 gain into whole-population or retained improvement;
   preserve remaining C guidance limits instead of asserting all research issues
   are resolved. Do not modify the live runtime or scientific inputs.
   Do not inject private validation into H/C, choose
   the agent's algorithm, widen budgets or weaken gates to hide these issues.
   Do not resume R15 or the resource-stopped Warehouse control. Validation remains exposed;
   frozen/retained unopened. No B0-fixed/original-B0 superiority. R14 root:
   `/home/clawd/research/scion-experiments/v04-cvrp-r14-post-r13-autonomous-20260927`.

Current work excludes distribution, deployment, installation, packaging, build,
root/systemd, Trust/Hash authority, object identity, leases, signing, registration,
receipts, duplicate closure, host-selected autonomous research mechanisms, and
new incidental research-quality gates. The expressly authorized independent
constructor repair is separately labeled engineering, not Scion H/C evidence.
