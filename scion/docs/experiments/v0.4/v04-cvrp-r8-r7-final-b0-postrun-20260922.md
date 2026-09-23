# CVRP R8: exact final R7 source not confirmed against B0

Read-only analysis on 2026-09-22 using the Experiment Analysis profile and
the operations postrun method. The [frozen design](v04-cvrp-r8-r7-final-b0-preregistration-20260922.md)
is unchanged. No raw source, metric or terminal artifact was modified; no
candidate was rerun and no original SQLite database was opened.

## Scope and terminal

Evidence root:
`/home/clawd/research/scion-experiments/v04-cvrp-r8-r7-final-b0-20260922`.
Read the [input](/home/clawd/research/scion-experiments/v04-cvrp-r8-r7-final-b0-20260922/input.json),
[terminal](/home/clawd/research/scion-experiments/v04-cvrp-r8-r7-final-b0-20260922/terminal.json)
and [raw screening metric](/home/clawd/research/scion-experiments/v04-cvrp-r8-r7-final-b0-20260922/metrics/78267022-b4e9-4e7d-be18-6d43be40f9d9.json).

R8 started `2026-09-22T14:45:38.550230+00:00`; `terminal.json` was written by
`2026-09-22T15:20:22.070227352+00:00` (about 34 min 44 s). It completed normally
as `NOT_CONFIRMED` at expanded screening, with `CONTINUE_EXPLORE` /
`SCREENING_FAIL_CASE_QUALITY`. The pane is dead with exit status zero. There
was no validation, frozen evaluation, promotion or retained comparison.

The run used the main checkout at launch HEAD `75ce0265` plus frozen prospective
docs/inputs/test changes, subsequently committed and pushed as `39b03166`.
Runtime implementation remained unchanged from `e405bfd2`. This was a
provider-free fixed comparison: no H/C export or provider call, and no invented
proposal Contract/Verification. Source/scope checks, strict canary, Protocol,
Safe Features and deterministic Decision were the existing fixed-driver path.

The strict canary completed one pair with both arms passing. Its raw metric
reference is absent; the existing canary details also contain the misleading
`raw_metrics_unavailable_reason=canary_veto_before_formal_protocol` label despite
`passed=true`. That diagnostic string is not evidence of a veto: formal
screening actually executed and the typed canary result is passing. No new
scientific judgment is derived from that label.

Actual resources: 50 solver subprocesses including canary, 2,660 nominal /
4,160 guarded subject-seconds. No subject/infra failure is recorded. Prelaunch
checks found no overlapping solver, tests or cleanup. The subsequent Git
commit/push was bookkeeping only; there is no identified heavy-maintenance
overlap, but no continuous host-load series establishes zero external contention.

## Complete source and creative attribution

Both `input_snapshots/baseline` and `input_snapshots/candidate` contain the same
100 ordinary files, excluding generated caches. Every file matches its declared
original directory. The baseline is original R3i B0 via R6's preserved snapshot;
the candidate is R7 step 13's complete branch-C tree (`candidate-3bsvzm8k`).
Both are `FULL_SOURCE_IDENTIFIED`; no patch reconstruction is needed.

Exactly three files differ from B0: `destroy_repair.py`, `local_search.py` and
`scheduler.py` under `policies/baseline_modules/`. The full candidate retains
R3i/R6 dynamic-frontier search, repair admissibility/consolidation and
orientation-changing 2-opt-star, plus R7 opportunity-based removal and bounded
ejection repair. The 2-for-1 operator and randomized-regret helper exist as
unused functions but are absent from their active default portfolios. Do not
silently clean these from the exact source.

The H/C source grounding and implementation fidelity belong to the
[R7 analysis](v04-cvrp-r7-autonomous-source-continuation-postrun-20260922.md).
R8 evaluates that whole ordinary value, not the isolated effect of its last
repair-arm removal and not a resumption of R7's pending expansion.

## Paired scientific result

Estimand: protected-fleet distance improvement of this exact candidate versus
original B0 on the six outcome-known R6/R7 screening cases, with fresh seeds
60013/60017/60029/60037. Positive delta is B0 distance minus candidate distance.
Each case uses the median of four seed deltas; the overall effect is the median
of six case effects. This is adaptive development, not an unseen-case claim.

| Case | Seed deltas, in declared order | Case median | Result |
|---|---|---:|---|
| B-n34-k5 | 0, 0, 0, 0 | 0 | tie |
| tai100a | 139, 246, 49, 148 | 143.5 | win |
| X-n351-k40 | -72, 93, -608, -566 | -319 | loss |
| A-n54-k7 | 0, 0, 0, 0 | 0 | tie |
| X-n190-k8 | 0, 0, 0, 0 | 0 | tie |
| X-n513-k21 | 0, 0, 0, 0 | 0 | tie |

All 24/24 pairs / 48 formal arms completed successfully, feasible, with exit
status zero, fleet violation zero and no bounded failure. All raw objective
subtractions and case medians reproduce the records. Scheduled and actual
orders agree on every pair: 12 AB, 12 BA, with A=B0 and B=candidate, following
the declared parity schedule. Limits are 30/45/90 seconds for the selected
small/medium/large cases, as preregistered.

Case W/L/T is **1/1/4**, overall median **0**, CI **[-159.5,71.75]**. Enumerating
the finite six-case resampling median distribution independently reproduces
these interval endpoints. Pair W/L/T is 5/3/16, which is not the case-level
effect unit. Net case score is zero; the unchanged case-quality gate correctly
does not qualify this candidate. The historical Decision is preserved.

Runtime ratio median is 1.000212, median elapsed difference +9 ms. The recorded
0.7083 runtime-regression fraction counts any positive elapsed difference; it
does not mean a material 70.8% slowdown. Both arms are budget-exhausting, with
essentially equal wall-clock consumption.

## Behavior, limits and next optimization

- tai100a improves at all four seeds. Candidate ALNS iterations are 21/27/26/28
  versus B0 15/12/20/13. The changed search bundle is active, but the experiment
  does not isolate which component caused those improvements. The earlier R7
  screen used a different comparator and seeds; do not pool its effects with R8.
- Both large cases run zero ALNS iterations in both arms at all four seeds
  (eight pairs). Initial VNS takes 66,585–68,782 ms across these arms, and every
  post-initial objective equals its final objective. The nominal 90-second
  subject limit contains an existing 0.8 algorithm time fraction and exit
  reserve, yielding about 69.84 seconds for construction plus initial VNS.
- Unlike R7's final contrast, R8's candidate and B0 have different local-search
  implementations. X-n351-k40's loss is therefore compatible with initial-search
  behavior/cost differences, but this is not an ablation proving that the
  orientation variant causes the loss. R7's added destroy/repair mechanisms
  do not execute there. The loss appears under both AB and BA orders.
- X-n190-k8 ties at every seed. Candidate ALNS iterations are 1/1/3/2 versus
  B0 2/2/3/3; candidate embedded VNS consumes 28,113–30,169 ms per arm. There
  is very little repeated destroy/repair exploration in the observed budget.
  This is an algorithm research observation, not a new activity/telemetry gate.

Framework verdict: no observed boundary or comparative-evidence failure in this
fixed funnel. Complete pairs, declared counterbalancing, exact source isolation,
negative Decision and unopened later stages are consistent. Canary diagnostic
wording is qualified above, not used to overturn executable facts.

Research verdict: **safe, valid, mixed performance; no confirmed B0 improvement**.
The positive medium-case result and the broader negative result both survive.
Neither CVRP nor v0.4 is complete.

Next: [R9 autonomous continuation](v04-cvrp-r9-post-b0-autonomous-preregistration-20260922.md)
from R8's complete candidate snapshot. Carry R3–R3i and R7 ordinary H-only
history in order, and append the distinct R8 fixed-comparison observation to
R4/R5/R6 observations. Make the unconfirmed B0 status explicit in the ordinary
current research question. Let H/C choose a mechanism and implementation;
do not prescribe a schedule, target, patch or mandatory history-read gate.
Keep complete source continuation, scientific gates, source/held-out isolation
and all original artifacts unchanged. Any later local promotion still needs
its own exact-candidate B0 evidence.
