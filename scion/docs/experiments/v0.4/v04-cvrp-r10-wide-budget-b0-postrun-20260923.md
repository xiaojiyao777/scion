# CVRP R10: screening pass, incomplete validation comparator evidence

## Result and authority

The exact R9 C bundle passed expanded screening against original B0 under the
equally doubled solver limits, but did **not** promote or establish retained
superiority. The unchanged funnel stopped at validation as
`completed_incomplete` / `INCOMPLETE_COMPARATOR_EVIDENCE`. Two pairs failed in
both arms at the same initial-construction step. Do not relabel this as a
candidate-only defeat, discard the failed case, or interpret the screening
pass as full confirmation. CVRP remains open; R10 is terminal, never resumable.

- [Frozen design](v04-cvrp-r10-wide-budget-b0-preregistration-20260923.md)
- [Terminal](/home/clawd/research/scion-experiments/v04-cvrp-r10-wide-budget-b0-20260923/terminal.json)
- [Input](/home/clawd/research/scion-experiments/v04-cvrp-r10-wide-budget-b0-20260923/input.json)
- [Screening raw metrics](/home/clawd/research/scion-experiments/v04-cvrp-r10-wide-budget-b0-20260923/metrics/b749b312-cde2-4e05-8856-1898d0ab4bba.json)
- [Validation raw metrics — operator-only, not proposal input](/home/clawd/research/scion-experiments/v04-cvrp-r10-wide-budget-b0-20260923/metrics/edac77fa-c07e-44c0-9f5d-5a25d0e2fa2c.json)

Process start: September 23, 15:02:15 UTC; terminal file written by
16:38:14.659955255 UTC. Tmux is dead with exit status zero, which is carrier
evidence only. There were zero provider/H/C calls, 74 solver subprocesses,
8,060 nominal / 10,280 guarded subject-seconds: one paired canary, 24 screening
pairs and 12 attempted validation pairs. The paired canary passed; its null
raw reference and generic `canary_veto_before_formal_protocol` diagnostic are
not a veto result and not comparative effect evidence.

## Source and measurement checks

Both ordinary 100-file input snapshots still equal their declared original
directories byte-for-byte, excluding Python caches. Only the three declared
files under `policies/baseline_modules/` differ between arms:
`destroy_repair.py`, `local_search.py`, `scheduler.py`. Construction and the
0.80 algorithm-local fraction / 3% exit reserve are unchanged and identical.
No host solver patch was added. Runtime is unchanged from `e405bfd2`; the
frozen R8–R10 docs/inputs/tests were committed and pushed as `841de42b` after
R10 terminated, under the user's new request.

All 36 attempted formal pairs used equal per-arm limits and their scheduled
orders: screening 12 AB / 12 BA, validation 6 AB / 6 BA, A=B0. The 34 valid
pairs have zero runtime errors, feasible outputs and zero fleet violation in
both arms. Their raw distance differences and all per-case medians were
recomputed. The two invalid pairs are retained, including both failing arms.
No overlapping maintenance, tests or other solver was identified; no continuous
host-load series exists, so absence of all external contention is not proven.

## Screening: whole-bundle positive evidence

All 24 planned pairs are valid. Case W/L/T is 3/0/3, median distance improvement
19.75, reported case bootstrap CI [0,179]; `SCREENING_PASS` / `queue_validate`.
Protected-objective regressions are empty. Positive delta means B0 minus
candidate. Seeds are 90001, 90007, 90011, 90017 in this order.

| Case | Four seed deltas | Case median | Candidate / B0 ALNS counts |
|---|---|---:|---|
| B-n34-k5 | 0, 0, 0, 0 | 0 | 1602/1568/1562/1572 vs 1578/1434/1425/1485 |
| tai100a | 204, 100, 116, 216 | 160 | 69/51/64/59 vs 25/31/33/27 |
| X-n351-k40 | 166, 158, -187, -79 | 39.5 | 0 throughout both arms |
| A-n54-k7 | 0, 0, 5, 0 | 0 | 329/292/306/285 vs 294/276/267/316 |
| X-n190-k8 | 0, 0, 0, 0 | 0 | 2/3/3/3 vs 2/2/2/3 |
| X-n513-k21 | 198, 198, 198, 198 | 198 | 0 throughout vs 1 throughout |

The observed win rate 0.5 does not contradict `SCREENING_PASS`: the active
case-level gates are median/practical delta, CI, net case score and case loss
rate, not an additional application of the legacy 0.6 win-rate field.
Runtime ratio median is 1.00005358, elapsed delta median +5.5 ms; the fraction
of positive runtime deltas (0.625) is not a 62.5% slowdown.

The wider 180-second band leaves about 139.68 seconds for algorithm search.
It still does not unlock candidate ALNS on either large screening case:

- X-n351-k40: initial VNS takes about 138.56–138.59 seconds after construction;
  both arms execute zero ALNS iterations. Two positive and two negative seed
  effects caution against treating its +39.5 median as stable mechanism evidence.
- X-n513-k21: candidate construction takes 2.65–2.86 seconds and initial VNS
  136.82–137.02 seconds. B0 initial VNS finishes in 97.23–100.36 seconds and
  executes one 36.24–39.46-second ALNS iteration. Every candidate objective is
  26,792 versus B0's 26,990; both post-initial objectives equal their finals.
  This supports a bundle-level difference, not the newly changed ALNS selector
  or frequency destroy. More ALNS iterations are not themselves a quality goal.
- tai100a has repeated active ALNS and four positive deltas. This does not
  isolate either R9 mechanism from the inherited bundle. X-n190-k8 still has
  only 2–3 candidate iterations and no distance change.

Candidate, seeds and comparison regime differ across R8/R9/R10. Do not pool
these contrasts or infer a causal dose response to doubling time.

## Validation: operator-only incomplete evidence

All 12 planned pairs executed, but only 10 are scientifically valid. Raw
`complete: true` means execution completed, not that comparator evidence is
complete. Reasons are `INCOMPLETE_EVIDENCE` and `CHAMPION_RUNTIME_FAILURE`;
there is no validation Decision. The counters report champion_failed_pairs=2,
shared_failed_pairs=2, candidate_failed_pairs=0, bilateral_failed_pairs=0.
Here candidate_failed_pairs counts candidate-only attribution: zero does **not**
mean no candidate arm failed. Both raw failures explicitly have side `both`.

On X-n627-k43, seeds 90019 and 90023, both arms load the intended solver then
raise `solve failed: unable to pack customer 624 into 43 routes`, at identical
`policies/baseline_modules/construction.py:135`. Each reports one algorithm
error, inactive solver and exception stop, followed by nearest-neighbor
fallback with 44 routes / fleet violation 1. Exit code zero and fallback
feasibility do not make these valid comparisons. The preserved runtime audit
correctly excludes their objective deltas and blocks the stage.

Static inspection locates the shared capacity-balanced greedy bin packing:
descending-demand customers are placed into the feasible bin with least
remaining capacity. Aggregate capacity sufficiency does not guarantee this
heuristic finds a packing. This is a shared problem-owned construction failure,
not evidence that the instance is infeasible, a provider error, or a reason to
relax the time limit. No failing solver was rerun and no original source changed.

For transparency only, the five complete case medians are B-n39-k5 +0.5,
X-n106-k14 -122, tai385 -5108, A-n62-k8 -0.5, X-n228-k23 +795. The valid-subset
W/L/T is 2/3/0, median -0.5 and CI [-5108,795]. These are not an estimate for
the full validation matrix, and missingness must not be erased to rejudge it.

Validation has now executed and is operator-exposed; it is no longer unopened.
Frozen and the independent pre-R3 retained block remain unopened. None of the
validation case names, outcomes, failure text, source location or remedy is
copied into R11's question/history. This entire report is operator-only context,
not an algorithm research input.

## Next falsifiable rung

[R11](v04-cvrp-r11-wide-budget-autonomous-preregistration-20260923.md) starts a
fresh autonomous campaign from the ordinary complete R10 candidate snapshot,
with the same wider budgets, unchanged gates, new seeds, all ordered R3–R3i/
R7/R9 scientific history and only safe screening facts. Source selection follows
the declared screening research signal, not a held-out repair prescription.
It can investigate improvement over that local source; it cannot claim a
retained-B0 result. H selects the mechanism; C owns implementation.

The known shared constructor limitation remains unresolved. If R11 reaches
the unchanged validation matrix, its initial champion can fail again even if
a new candidate changes construction. Preserve the resulting incomplete or
negative evidence; do not remove a case, edit original B0, weaken runtime audit,
or backfill R10. Comparator remediation and any future independent confirmation
need a separately stated prospective design, not a silent in-run fix.
