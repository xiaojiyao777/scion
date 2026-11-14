# CVRP R16 read-only analysis: quota outage, valid incomplete research

*Inspected: 2026-10-03 UTC. Operator analysis; private validation facts below
must not be copied into H/C inputs.*

## Scope and terminal result

The user requested inspection after an account quota outage and reported that
quota is restored. This audit does not invoke a provider/solver, resume R16,
change runtime/inputs, or authorize another run. Experiment Analysis profile:
canonical entry, experiments index, operations runbook/handoff and
[R16 preregistration](v04-cvrp-r16-probe-diagnostics-autonomous-preregistration-20260928.md).
Checkout was clean at pushed `505dce03`; frozen runtime/inputs are `d67f9800`.

Root: `/home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928`.
[Status](/home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928/status.json)
and [summary](/home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928/campaign_summary.json)
agree: stopped, `OUTER_HARDWALL_EXCEEDED`, `valid_incomplete`, seven of twelve
evaluated stages (six screening, one validation), no promotion. Champion remains
v1 / weight revision zero; frozen and retained were not run. Terminal status was
written at **2026-09-30 15:49:01.133122 UTC**. Tmux is dead with exit 124;
this corroborates the operational stop, not the scientific verdict.

## Account quota versus campaign resource limits

- All first **50 calls succeeded**: 24 H turns, 26 C turns, five exported H/C
  candidates. Last success: September 28, 20:05:24 UTC.
- The last formal metric was written at 20:38:46 UTC, before the first provider
  failure at **20:38:49 UTC**. That
  [trace](/home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928/llm_traces/20260928T203849889372_hypothesis_research_turn_9b3c4c68.json)
  records HTTP 429: `All accounts exhausted (1 rate-limited)` and
  `The usage limit has been reached`.
- Another **195 calls** received the local proxy's exact synthetic no-usable-
  account 401, classified as temporary provider unavailability. There was no
  later successful call. These are not 195 real credential-rejection findings.
- The 196 failed dispatches comprise 65 exhausted three-dispatch H requests
  plus one dispatch in the last interrupted attempt. All 65 redispatch groups
  preserve identical context, prompts, schema and request policy, with attempt
  indexes 0/1/2. All 65 recorded rejections are
  `PROVIDER_TRANSIENT_RETRIES_EXHAUSTED`, not algorithm failures.
- Transport's existing synthetic-401 policy waits 20 minutes between retries;
  attempt exhaustion schedules fresh H. Persistent unavailability therefore
  consumes **43 hours 10 minutes** after the first failure until the predeclared
  48-hour outer guard. No solver result is produced in that period.
- **246/600 physical calls admitted; 354 remain.** The call cap was not exhausted.
  `balance_exhausted=false` does not contradict account quota exhaustion: this
  429 followed the rate-limit path, not the typed balance-error path.

Current quota restoration was not independently tested with a paid inference.
Restoration cannot restart this terminal campaign. Any later research needs a
fresh campaign, not a change to this stop or its ordinary artifacts.

## Completed comparative evidence

Five distinct exported candidates produced seven complete stages. The summary's
`formal_screened_candidates=6` counts screening evaluations, including expansion;
it is not six distinct source candidates. Positive distance delta favors the
candidate against unchanged R12-A-fixed champion, not original B0 or B0-fixed.

| Step | Algorithm / stage | Valid pairs | Case W/L/T | Median delta [CI] | Recorded decision |
|---|---|---:|---|---|---|
| 1 | A: workload-adaptive SWAP*, initial | 10 | 2/2/1 | 0 [-20.5,88.5] | continue_explore |
| 2 | B: sweep split DP, initial | 10 | 1/1/3 | 0 [-3,77.5] | continue_explore |
| 3 | C: capacity-filtered SWAP*, initial | 10 | 1/2/2 | 0 [-29.5,36.5] | continue_explore |
| 4 | A: per-customer workload refinement, initial | 10 | 2/1/2 | 0 [-25,16] | expand_screening |
| 5 | Exact step-4 candidate, expanded | 24 | 3/0/3 | +4.75 [0,16.75] | queue_validate |
| 6 | Same candidate, validation | 12 | 2/2/2 | 0 [-12.5,1302.75] | abandon |
| 7 | D: optional positive Clarke–Wright merges, initial | 10 | 1/1/3 | 0 [-13.5,103] | continue_explore |

All **86 pairs** (74 screening, 12 validation) are complete and valid: no arm
failure, invalid solution, solver error, fleet violation or protected-objective
regression. Read-only checks reproduce each raw distance difference, case median
and stage median, complete case/seed Cartesian roster, equal actual arm limits,
and recorded gate/reason-code correspondence. No Decision is rewritten.

Exact metrics, in step order:
`7c80fca6-39ef-43c1-aa64-329cb06be8b6.json`,
`0ccf6e84-f3e4-4cc3-a51a-afaf74a69646.json`,
`1ba21364-7bb5-4b00-9eb4-957660da48be.json`,
`b0c51a0c-6751-466f-bc0d-cfff2e83a484.json`,
[expanded](/home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928/metrics/a69f97ef-4abf-416b-817e-b2ae8104ed86.json),
[operator-only validation](/home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928/metrics/245a4c56-e1ba-43d5-aff1-415e8a267ec0.json),
and `99df7d8a-a23d-4129-b212-a426bb91c0ee.json`, all under the root's `metrics/`.

The expanded pass is small and does not survive validation's complete
`VALIDATION_FAIL_CASE_QUALITY` judgment. This is a quality rejection, not a
constructor/comparator failure or a consequence of the later quota outage.
Screening X513 gains 16 at all four seeds; X351 changes sign across seeds and
has median +9.5. Both arms still have zero ALNS iterations on both large cases.
The intended release of time for downstream ALNS is therefore not demonstrated
there. Champion-first, time-limited adaptive screening remains exploratory;
these effects are neither component causality nor independent retained evidence.

## H/C behavior and source fidelity

H completes five proposals using 12 source reads, four history reads and three
frontier reviews, without observed H tool errors. C uses twelve revise actions,
seven probes, two source reads and five immediate ready exports. Four local edit
errors (two selector_not_found, one duplicate_file_path, one patch_validation_failed)
are corrected within open sessions. All five exports pass recorded Contract,
Verification and canary; stage reuse creates no new H/C.

All **140 visible C source values** match the appropriate complete base: A's
second proposal continues A's accepted first head, while the other branches
start from champion. Champion's 100 files equal the declared R13 candidate
snapshot. Three surviving 100-file trees match ordinary history exactly:

- B: `candidate_workspaces/candidate-ghoyqora`, history row 2.
- C: `candidate_workspaces/candidate-t9n63fe3`, history row 3.
- D: `candidate_workspaces/candidate-rn8712tq`, history row 6.

These are `FULL_SOURCE_IDENTIFIED` surviving heads, not promoted algorithms.
Abandoned A's complete materialized tree is not retained among current candidate
workspaces; its full changed-file values remain in history rows 1/4/5 and actual
C traces. This audit compares those ordinary source values without rebuilding or
rerunning A, and does not claim a surviving full stage snapshot for it. Six
history rows contain screening only: validation and 65 operational rejections
have not become H-visible algorithm history.

Research-support observations are mixed:

- Both failed probes deliver the new bounded hint to C: step 1
  `call/attribute_error/line 50`, step 2 `call/assertion_error/line 28`.
  Revised executable drafts and revised probes subsequently pass. This verifies
  actual hint delivery and continued work, not a causal improvement in reasoning.
- Step 1 replaces a failing instance monkeypatch probe with real route/state
  helper checks and a forced bounded-path check. It does not prove unchanged
  production-entry reachability or the original large-state performance claim.
- B implements the split DP and scheduler passthrough, but production
  `CW_THRESHOLD=1500` selects sweep only above 1500 customers; initial screening
  has 33–512. Its passing probe sets `cw_threshold=0` and disables initial VNS.
  The implementation exists, but that forced helper/scheduler experiment does
  not establish activation in this formal population. Do not attribute B's
  X351 delta to the inactive DP.
- C's early capacity filter is implemented, but filtering before top-pair/link
  ranking changes the ranked shortlist. It is not established as a pure
  behavior-preserving acceleration; its probe covers a wholly infeasible pair.
- A's density refinement matches its code claim, but the passing probe replaces
  both pair-building helpers with empty-result mocks. It tests dispatch, not
  real collaborator behavior or final solution benefit.
- D's probe calls real `baseline_algorithm.solve`, wraps the real constructor,
  and verifies optional merges and customer/capacity preservation on a synthetic
  instance. This is useful integration evidence, not formal quality evidence;
  its initial screen still fails. The optional public example is present in C
  contexts, but receipt is not proof the agent used or understood it.

## Verdict and next action

**Framework/operations:** bounded feedback, source delivery and recorded formal
boundaries work in the inspected evidence; persistent quota outage prevents
completion. Repeated fresh attempts during long-lived unavailability are an
operational-efficiency problem, not 65 failed algorithms. A future authorized
repair should distinguish explicit exhausted usage quota from short transient
rate limits, preserving typed termination and all scientific gates.

**Research:** valid incomplete, with a completed negative validation and no
promotion. R16 is not wholly invalid and must not be discarded; it also cannot
demonstrate completed twelve-stage research or retained CVRP improvement.
Activation reasoning and test-claim fidelity remain unresolved.

Only analysis/handoff documentation changes in this inspection. No original DB
opened, provider call, solver/test rerun, evidence rewrite, commit or push.
If the user authorizes continuation, first verify actual inference availability
without exposing credentials, select and document an ordinary complete source
and safe history, and preregister a fresh run with unchanged necessary gates.
Do not resume R16, import private validation facts into H/C, enlarge budgets as
a substitute for quota handling, or silently treat a provisional head as champion.
