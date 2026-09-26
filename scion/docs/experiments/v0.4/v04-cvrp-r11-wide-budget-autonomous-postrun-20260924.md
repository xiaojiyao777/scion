# CVRP R11: modest uncertain development gain, inactive phase handoffs

## Scope and result

R11 completed normally at `2026-09-24T05:58:23.243135+00:00` after 12
screening stages: ten H/C candidates and two exact-candidate expansions.
All 108 formal pairs are valid, with no runtime failure or fleet regression.
No candidate passed expanded screening; no validation, frozen or promotion
occurred. The best surviving development signal is branch B's expanded
W/L/T 3/1/2, median +10, CI [-1,216.75], still uncertain. This is against
R11's local initial champion (R10's candidate), not original B0.

- [Frozen design](v04-cvrp-r11-wide-budget-autonomous-preregistration-20260923.md)
- [Terminal status](/home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923/status.json)
- [Summary and exact step/metric refs](/home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923/campaign_summary.json)
- [Complete ordinary H/C history](/home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923/research_history.jsonl)
- [Final B expanded raw metrics](/home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923/metrics/892458a5-2492-4162-a58e-7331266c898a.json)

Started September 23 at 23:47:06 UTC; carrier now dead, exit zero. Runtime
remained unchanged from `e405bfd2`, checkout HEAD `841de42b`; the R10 analysis/
R11 preparation diff was docs/inputs/tests only and remains uncommitted.
No concurrent tests, cleanup or other solver was identified during measurement;
there is no continuous host-load record. Champion-first autonomous ordering
was preregistered, not AB/BA counterbalancing. Wall-clock variability remains
a limitation, especially for large-case effects.

## Framework and source checks

There are 101 physical provider traces: 55 H research calls, 45 C research
turns and one C finalization. One H call returned a typed 502 server overload;
the following attempt-index-1 call succeeded with identical frozen context
and prompt. No invocation cap was exhausted. One C session used its permitted
terminal `finalize_patch` after 12 turns; the other nine exported via `ready`.
This is normal bounded-session behavior, not a repaired terminal response.

H actions: 17 source reads, 18 history reads, nine frontier reviews, ten
hypothesis exports; the remaining physical call is the recovered failure.
C research actions: 15 revisions, 14 tests, five source reads, two searches,
nine `ready` exports, plus the separate finalizer. All ten candidates pass
Contract and Verification; expansion rows have no new H/C or repeated gates.
The summary's `formal_screened_candidates: 12` counts evaluated stages here,
not ten distinct source proposals.

Every actual H context retains the exact R11 screening-only question, with
four prior observations and the initial 90-record scientific history index.
H reads current and older scientific evidence; availability does not prove
attention to every observation. The first two H sessions read scheduler source
but did not resolve its imported threshold value before finalizing their
large-case diagnosis. C did receive the configuration dependency in its source
context. No held-out stage occurred and none is added to future research input.

All 46 C contexts were checked against the appropriate pre-attempt complete
branch value: 284 visible path/content entries match. Non-visible peer entries
remain indexed, not falsely described as inline content. The initial 100-file
champion equals R10's selected snapshot. The three surviving 100-file source
trees equal their recorded ordinary accepted changes and untouched files:

| Branch | Final complete source | Last stage |
|---|---|---:|
| A `e61a25f0…` | `candidate_workspaces/candidate-y5xzl0ff` | 12 |
| B `78a33ecb…` | `candidate_workspaces/candidate-mloc4e8_` | 10 |
| C `63776311…` | `candidate_workspaces/candidate-f2v99hs9` | 11 |

Paths are relative to the linked R11 root. Final trees are FULL_SOURCE_IDENTIFIED.
Earlier replaced branch heads are identifiable through their ordinary patches
and later C inputs, not claimed to remain separate complete snapshots. Expansion
pairs 5/6 and 9/10 reuse identical exported changes. No campaign state was restored,
no original SQLite opened and no solver rerun during analysis.

All 216 formal arms loaded the intended active algorithm, report zero errors,
valid solutions and zero fleet violation. Per-pair distance differences,
equal limits and per-case medians were independently checked. Runtime ratios
range from 0.99813 to 1.00371. Necessary scientific gates produced the recorded
negative/uncertain decisions; no analysis-based rejudgment is applied.

## H/C research fidelity and outcomes

Positive delta is local champion distance minus candidate distance. The table
summarizes actual code, not a new research qualification gate.

| Step / branch | H and actual C | Screening W/L/T; median [CI] |
|---|---|---|
| 1 / A | Initial-VNS 45% time share and bounded ALNS mode implemented, but guarded above 2000 customers: inactive on this population | 1/1/1; 0 [-31,66.5] |
| 2 / B | Gain-rate initial-VNS handoff plus 25% ALNS reserve implemented, same inactive threshold | 1/1/1; 0 [-19.5,82] |
| 3 / C | Directed prefix-load/cost screening for both two-opt-star variants, exact rescore before acceptance; faithful | 0/2/1; -25.5 [-78,0] |
| 4 / A | Post-sweep exact window DP (max 7 customers, 3 checks), ordinary-VNS restart; faithful, repeatedly callable after later exhausted sweeps | 1/1/1; 0 [-63,25.5] |
| 5–6 / B | O(1) boundary-delta swap screening with exact rescore; faithful | initial 2/0/1, +33; expanded 1/1/4, 0 [-11,166] |
| 7 / C | Directed Or-opt removal/insertion deltas, preserved destination search order and exact acceptance; faithful | 1/1/1; 0 [-35.5,16] |
| 8 / A | Window DP restricted to at most one active-frontier post-sweep call, disabled for full-scope VNS; faithful | 1/1/1; 0 [-7,264] |
| 9–10 / B | One post-sweep SWAP* pass: 10 route pairs, 24 customer links per pair, free reinsertion, capacity and exact cost checks; faithful core mechanism | initial 2/0/1, +15.5; expanded 3/1/2, +10 [-1,216.75] |
| 11 / C | Directed reversal-prefix deltas for intra-route 2-opt and polish, exact rescore; faithful | 0/2/1; -8.5 [-13.5,0] |
| 12 / A | Each ordinary neighborhood returns after one accepted move, allowing immediate VNS restart; faithful path change with major large-case harm | 1/1/1; 0 [-8557,8.5] |

The first two H diagnoses confuse a real threshold branch with its activation
on current instances. `config.py` sets ALNS_THRESHOLD=2000, passed unchanged
by `baseline_algorithm.py`; screening has at most 512 customers. Neither new
phase handoff can run. Zero ALNS on these cases reflects initial-search time
consumption, not the >2000 early-return condition. Their wall-clock objective
differences therefore cannot establish handoff efficacy. This is an H grounding/
activation problem, not missing source or a reason for another framework gate.

The SWAP* implementation ranks each eligible route pair using its four shortest
cross links and sorts candidate exchanges by estimated delta. It first enumerates
all customer links for route-pair ranking, so the later 10/24 shortlist does not
bound that up-front work to constant cost. It has no dedicated SWAP* activation
counter; code establishes reachability, not per-pair isolated causal contribution.
Existing safety checks passed, but throughput or accepted-move counts do not
prove a net objective gain. Step 12's large-case deltas -8533/-8581 demonstrate
that a plausible restart policy can strongly harm bounded-time solution quality.

## Final B's modest signal and remaining search behavior

Expanded seeds: 100003,100019,100043,100049. Same complete bundle in both its
initial and expanded stages; no fresh C before expansion.

| Case | Four seed effects | Median | Candidate / champion ALNS iterations |
|---|---|---:|---|
| B-n34-k5 | 0,0,0,0 | 0 | 1357/1379/1271/1310 vs 1377/1430/1517/1554 |
| tai100a | 47,14,62,3 | 30.5 | 54/56/48/52 vs 54/63/57/60 |
| X-n351-k40 | 246,604,560,246 | 403 | zero in both arms |
| A-n54-k7 | 0,0,-5,-4 | -2 | 319/353/341/344 vs 334/324/314/338 |
| X-n190-k8 | -53,0,0,178 | 0 | 3/4/3/3 vs 3/4/3/4 |
| X-n513-k21 | 20,20,20,20 | 20 | zero in both arms |

The final aggregate is uncertain because CI low is -1; a positive median alone
is insufficient. Runtime ratio median 0.999732, elapsed delta median -23.5 ms;
the 0.2917 runtime-regression fraction is not a 29% slowdown.

Across the full run, all 28 X-n351 pairs have zero ALNS in both arms. X-n513
appears in eight pairs: the step-6 swap-only candidate performs one ALNS iteration
per seed while the champion performs zero, but every distance effect is zero.
The final SWAP* bundle instead improves distance by 20 while performing zero
ALNS again. Its initial VNS consumes 136.53–136.84 seconds; X-n351 consumes
138.47–138.59 seconds. More iterations did not imply more improvement, and the
post-sweep intensifier may trade throughput for incumbent quality. The combined
bundle/clock interaction is observed; neither SWAP* nor swap speedup has isolated
causal confirmation. The inactive scheduler code must not receive credit.

## Verdict and next experiment

Framework: the inspected source flow, typed retry, accepted continuation,
complete-pair evidence and deterministic decisions support correct execution
within this run's declared scope. No new implementation repair is justified by
the research results. Research: several faithful algorithms were tested, but
only a modest uncertain signal remains; no local promotion or B0 confirmation.

[R12](v04-cvrp-r12-post-r11-autonomous-preregistration-20260924.md) selects the
complete B tree, not a merge of the three branches. Its final expanded signal
is preferable for further adaptive research to A's large loss and C's negative
initial screen; this is outcome-informed development selection, not superiority
proof. Add all 12 R11 history rows to the ordered H-only input, preserve prior
observations and R10 screening facts, and make the imported-threshold mismatch
an ordinary source-grounded fact. H/C still choose the mechanism and code.

Use fresh seeds and the same wider equal limits/gates. The known R10 shared
validation constructor limitation remains unresolved in B; do not silently
repair B0, replace its case, expose its private failure to H/C or bypass the
stage. R11 supplied no new held-out evidence. Frozen and independent retained
remain unopened; validation was already operator-exposed in R10. Local screening
development is useful but cannot close the retained-improvement objective.
