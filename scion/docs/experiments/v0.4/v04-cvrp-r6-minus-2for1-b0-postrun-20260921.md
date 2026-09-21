# CVRP R6: complete minus-2-for-1 versus B0, not confirmed

## Scope and terminal evidence

The [prospective design](v04-cvrp-r6-minus-2for1-b0-preregistration-20260921.md)
compared the complete R5 minus-2-for-1 source with original R3i B0. Runtime was
frozen at `e405bfd2`; `55c0d3de` only recorded launch status. This provider-free
fixed funnel exported no H/C and made zero provider calls.

- [Input](/home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/input.json)
- [Terminal](/home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/terminal.json)
- [Screening metric](/home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/metrics/c9a5fe82-83d3-4897-8ea8-3b428b1c208b.json)

Launch was `2026-09-21T16:09:27Z`. The terminal file's modification time is
`16:44:12.811Z` (filesystem timing, not a recorded scientific timestamp).
Terminal reports `completed / NOT_CONFIRMED`, stopping at expanded screening.
Canary passed. Exactly 50 solver subprocesses ran: one canary pair plus 24
screening pairs, 2,660 nominal and 4,160 guarded subject-seconds. No validation,
frozen, retained comparison, or promotion ran. The dead tmux pane has no usable
exit-status value; terminal and metrics, not the pane, establish completion.

Operator contamination must be disclosed: user-authorized cache and old-worktree
cleanup overlapped R6 on this server. The ordinary
[cleanup record](/home/clawd/research/server-cleanup-20260921.md) preserves its
scope. Source, data, configuration, and experiment artifacts were not removed or
edited; cache/filesystem work could nevertheless contend for CPU or I/O during
wall-clock-budgeted search. There is no per-pair host-load record sufficient to
bound that influence. Preserve the recorded negative Decision, but treat these
performance estimates as exploratory rather than clean independent confirmation.

## Framework correctness

`FULL_SOURCE_IDENTIFIED`: both output-local snapshots contain 100 files and are
byte-equal to their respective declared input trees. Relative to B0, the complete
candidate differs only in `destroy_repair.py`, `local_search.py`, and
`scheduler.py` under `policies/baseline_modules/`. No patch-chain reconstruction.

As preregistered, the fixed driver checks ordinary source/scope and canary;
it does not invent H/C or re-execute their Contract/Verification. All 24 formal
pairs contain two successful, feasible, exit-zero arms. Candidate, comparator,
shared, bilateral, timeout and invalid-output failure counts are zero; protected
fleet regressions are absent. Actual AB/BA orders match scheduled orders,
12 each. Each case has all four declared seeds and its correct 30/45/90-second
limit. Later populations remained unopened after the negative gate.

Protocol recorded `SCREENING_FAIL_CASE_QUALITY`; deterministic Decision recorded
`continue_explore`. The fixed one-candidate funnel then ended `NOT_CONFIRMED`.
These are consistent: a live research branch could explore further, but this
fixed experiment neither edits nor promotes the tested candidate. No observed
runtime/control failure explains away its scientific nonconfirmation.

## Research effectiveness

Distance delta is B0 minus candidate, so positive favors the candidate. The
primary unit is the within-case median of paired seed effects, not 24 independent
case replicates. Seed columns below are 20011, 20021, 20023, 20029.

| Screening case | Four paired distance deltas | Case median | Case result |
|---|---|---:|---|
| B-n34-k5 | 0, 0, 0, 0 | 0 | tie |
| tai100a | 211, 249, 147, -69 | 179 | win |
| X-n351-k40 | -824, -737, -295, -102 | -516 | loss |
| A-n54-k7 | 0, 0, 3, 0 | 0 | tie |
| X-n190-k8 | 33, 0, 75, 0 | 16.5 | win |
| X-n513-k21 | 0, 0, 0, 0 | 0 | tie |

Case W/L/T is **2/1/3**; pair W/L/T is **6/5/13**. Case-median effect is **0**,
bootstrap CI **[-258, 97.75]**. Net case score is `(2-1)/6 = 1/6`, below the
unchanged 0.25 gate; the median and lower confidence bound also do not establish
the required practical improvement. The recorded first reason code is preserved,
not replaced with post-hoc thresholds. The runtime ratio median is 0.9999147 and
elapsed delta -4 ms: effectively equal allotted-runtime use, not a speedup claim.

The source and problem-owned raw observations expose a useful development issue:

- On X-n351-k40 and X-n513-k21, **both arms at all four seeds have zero ALNS
  iterations**. Initial VNS consumes about 65.9–68.8 seconds after construction;
  each whole process takes about 70.2 seconds of its nominal 90-second limit.
- This is consistent with existing algorithm code, not a Protocol timeout:
  `baseline_algorithm.py` gives the solver 0.80 of the nominal budget, and
  `scheduler.py::_initial_solution` passes the same context/reserve to initial
  `_vns`; there is no separate initial-polish allocation. `solve` only enters
  the ALNS loop afterwards. The common exit reserve consumes another 0.03 of
  the algorithm-local budget. Neither arm failed or hit its subprocess guard.
- The candidate's X-n351-k40 losses are already present at the post-initial-VNS
  solution boundary. Its later repair admissibility and active-route frontier
  cannot explain those pairs through ALNS execution, because that loop did not
  execute. The changed initial local-search trajectory and time allocation are
  plausible research questions; no individual mechanism's causal effect is
  established by this bundled, potentially resource-contaminated comparison.
- On tai100a the candidate has 32/34/39/34 ALNS iterations versus B0's
  11/12/11/21, but one seed still loses. More iterations do not themselves imply
  better quality. On X-n190-k8 both arms have only 1–3 iterations.
- B-n34-k5 finishes at distance 788 for every arm/seed, with zero post-initial
  best updates despite many accepted moves. Accepted-move counts must not be
  confused with final-objective improvement or made into a new generic gate.

R6 therefore does not confirm that deleting 2-for-1 is sufficient for retained
improvement over B0. R4, R5 and R6 use different contrasts/populations and cannot
be pooled as one effect trajectory. The complete minus-2-for-1 source remains an
ordinary development starting value, not an independently accepted champion.
CVRP and v0.4 remain open.

## Evidence-backed continuation

Preserve every R4–R6 terminal and source tree. Do not rerun R6 until it passes,
alter its thresholds, or open its later stages after failure. The user's new
request authorizes a fresh autonomous development campaign after this analysis.

Continue from the complete minus-2-for-1 tree with ordered H-only historical
facts and explicit R4/R5/R6 screening observations. Give the agent the observed
mixed quality and phase behavior, not a mandated mechanism, file, schedule or
patch. Reuse the now-known R6 screening cases explicitly as adaptive development;
its unexecuted validation/frozen populations remain held out. A new local
promotion relative to this starting tree still needs a separate exact-candidate
comparison with original B0 on the reserved retained block before any closeout.
No cache cleanup, large test suite, or parallel solver job should overlap it.
