# CVRP R9: valid autonomous research, no promotion, unresolved time allocation

Read-only analysis on 2026-09-23 using the Experiment Analysis profile and the
operations postrun method. The [frozen design](v04-cvrp-r9-post-b0-autonomous-preregistration-20260922.md)
is preserved. No original source, metric, trace or campaign state was modified;
no candidate was rerun and the original SQLite database was not opened.

## Scope and terminal evidence

Root: `/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922`.
The [summary](/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/campaign_summary.json)
and [status](/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/status.json)
record `completed / requested_rounds_completed`, 12 evaluated screening stages,
8 distinct H/C candidates, 4 expansions, zero rejection/infra/interruption
outcomes and no validation, frozen stage or promotion. Started
`2026-09-22T23:22:20.486583+00:00`; final status timestamp
`2026-09-23T04:02:58.157595+00:00` (about 4 h 41 min). The dead tmux pane
does not establish these scientific facts; its exit-status field is empty.

All 144 executed formal pairs / 288 arms are valid: no recorded failures,
feasibility loss or fleet violation. Raw distance subtractions reproduce every
pair delta. Expansions execute their full matrices again; these 144 observations
must not be pooled as independent evidence for one candidate. Comparator is
R8's complete candidate, not original B0. Runtime remains the implementation
at `e405bfd2`, launched atop HEAD `39b03166` with documented uncommitted
docs/input/test changes. No identified solver/test/cleanup overlap occurred;
there is no continuous load series proving absence of external contention.
Autonomous order remains champion-first, not counterbalanced.

## H/C, source continuity and implementation fidelity

There were 92 physical calls: 46 H and 46 C, leaving 508 of the declared 600.
Two typed timeouts (C 300 s, H 180 s) each recovered on attempt index 1 with
identical structured context and user prompt. They are charged redispatches,
not new proposals or algorithm failures. Eight H exports and eight successful
Code `ready` exports correspond to the eight actual candidates.

H used 16 source reads, 13 history reads, one source search, seven ordinary
history reviews and eight finalizations. The source/history indexes and explicit
R8 nonconfirmation question were present. Actual history reads were R7's final
record and then R9's own records; none read the four separate R4/R5/R6/R8
observation bodies. Availability is not attention. Later H used preceding
negative/uncertain evidence, but sometimes treated intended H mechanisms as
implemented without checking the final source carefully enough.

C used 17 draft revisions, 10 test actions, eight source reads, two searches and
eight `ready` actions. Every ordinary visible C source checked at session start
matches the corresponding branch head. All three surviving complete trees have
100 ordinary files and equal their branch's accepted ordinary source changes;
the initial champion equals the R8 source. These final objects are
`FULL_SOURCE_IDENTIFIED`. Earlier overwritten stage trees are located through
ordinary full-file patch values and subsequent C contexts
(`PATCH_FALLBACK_IDENTIFIED`), not a restored campaign or a new authority record.

| New-candidate step / branch | Actual change and fidelity |
|---|---|
| 1 / A | Promise-tier embedded VNS allowance 5000/2500/1250. The source changes, but all limits exceed the seven default neighborhoods; improvement resets the counter and the loop exits after a seven-failure sweep. Thus this does **not** implement the predicted shorter descent under current defaults. |
| 3 / B | Broken-pairs novelty admission for non-improving repairs. Active gate is implemented, but all admitted categories also select full route scope, losing the previous restricted frontier for these calls. |
| 4 / C | Joint destroy/repair quality divided by square-root generation-cost EMA. Central selection mechanism is implemented. Forced coverage occurs only in the initial permutation, not repeatedly every bounded number of segments as proposed; the later roulette has a positive exploration floor. |
| 5 / A | Exact reassignment scoring after a deterministic top-16 removal-saving shortlist. The central cost reduction is implemented; no favorable case-level result. |
| 6 / B | Proposed VNS-yield learning is **not in the exported source**. Final patch only initializes an unused yield dictionary and resets the segment marker. Earlier controller drafts failed self-authored falsifiers; the final complete replacement draft omits that controller, passes public checks and exports. This is scaffolding-only for the stated learning mechanism, not evidence that a yield controller failed scientifically. |
| 8 / C | Adds decayed accepted-incumbent edge memory and frequency-guided removal to the joint pair selector. Core mechanism is present and selected on small/medium cases. Memory observes accepted incumbents, not guaranteed local optima; nearest-neighbor normalization is recomputed within each destroy call. |
| 10 / A | Two construction seeds, three-failure VNS probes, then continuation of the chosen seed. A tournament exists, but equal failure counts are not equal time slices: one operator can consume the shared remaining deadline before the other seed is meaningfully probed. The promised time allocation is only partial. |
| 11 / B | Post-sweep two-route rebuild with up to three route pairs, six pooled customers and beam width 24. Exact improving feasible state replacement is implemented. It activates on smaller cases but never on the two large cases, whose ordinary initial descent has not finished. |

The step-6 final [C context and export](/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/llm_traces/20260923T011905581241_code_research_turn_eca18204.json)
shows draft revisions 1/2 failing their falsifiers and revision 3 passing public
checks without a falsifier. Existing `revise` semantics replace the complete
draft against the original session source; they do not accumulate incremental
same-file edits. Source and export agree. This is an implementation-fidelity
failure, not evidence of host source corruption, and does not justify a new
novelty, telemetry or mechanism-quality gate. Preserve the original Decision.

Final sources: A
[`candidate-7p_ff976`](/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/candidate_workspaces/candidate-7p_ff976),
B
[`candidate-wjhivwnm`](/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/candidate_workspaces/candidate-wjhivwnm),
C
[`candidate-sm2ft2v2`](/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/candidate_workspaces/candidate-sm2ft2v2).

## Paired results and recorded decisions

Positive delta means local champion distance minus candidate distance, with
fleet protected. Each effect is the median of case-level seed medians.
Initial screening is 3 cases x 2 seeds; expanded is 6 x 4. Exact metric refs are
under each step's `protocol_result.raw_metrics_ref` in the summary.

| Step | Branch | Pairs | Case W/L/T | Median [CI] | Recorded outcome |
|---:|---|---:|---|---|---|
| 1 | A | 6 | 1/0/2 | 0 [0,14.5] | initial-quality expansion |
| 2 | A | 24 | 1/1/4 | 0 [-40.75,1.25] | fail case quality |
| 3 | B | 6 | 1/1/1 | 0 [-156,77] | fail case quality |
| 4 | C | 6 | 1/1/1 | 0 [-43.5,49] | fail case quality |
| 5 | A | 6 | 1/1/1 | 0 [-144.5,74] | fail case quality |
| 6 | B | 6 | 2/0/1 | 53 [0,60] | required expansion |
| 7 | B | 24 | 1/0/5 | 0 [0,7.25] | fail case quality |
| 8 | C | 6 | 2/0/1 | 62.5 [0,118] | required expansion |
| 9 | C | 24 | 2/0/4 | 0 [0,170.25] | expansion exhausted, case-level uncertain |
| 10 | A | 6 | 1/1/1 | 0 [-467.5,74] | fail case quality |
| 11 | B | 6 | 2/0/1 | 52.5 [0,949] | required expansion |
| 12 | B | 24 | 1/2/3 | 0 [-154,22.75] | fail case quality |

All expanded/failed stages return `CONTINUE_EXPLORE`; none promotes. Three
positive initial screens fail to establish a positive expanded median.

The final C [expanded metric](/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/metrics/8458fb2b-7cf5-4e34-930c-3f23daf567f7.json)
has case effects 0, +6.5, +334, 0, 0, 0 in declared order
(B-n34, tai100a, X-n351, A-n54, X-n190, X-n513). tai100a seed deltas are
187/-24/33/-20; frequency removal is selected 4/3/6/7 times and candidate
ALNS iterations are 28/23/25/31 versus 24/16/22/16. This is active but mixed
development evidence, not a reproducible isolated frequency-arm gain.

The final B [expanded metric](/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/metrics/c2d635b6-6196-44be-be4a-1a0220bd8701.json)
has case effects 0, +45.5, -305.5, 0, 0, -2.5. On B-n34, rebuild accepts
58–81 moves per seed while final distance stays 788 and candidate ALNS falls
to 441–460 versus 634–739. Accepted local moves do not establish final benefit.
Its large initial-screen gain reverses on expansion; rebuild attempts are zero
on both large cases, so those differences cannot be attributed to executed
rebuild moves.

## Budget diagnosis and next rung

Across all 48 large-case pairs, **both arms have zero ALNS iterations**.
The unchanged external 90 s limit is reduced by algorithm-owned 0.80 to 72 s,
then a 3% exit reserve leaves about 69.84 s for construction plus search.
Initial VNS shares that deadline with ALNS; it has no separate time quota.
An individual neighborhood can consume the remaining budget. Counts such as
5000/1250 or three failed neighborhoods are not wall-clock phase limits.

C's changed pair selector and frequency removal do not execute before initial
descent. Its +334 large-case median therefore cannot establish their benefit.
The unchanged champion's X-n351 results vary materially across repeated
same-seed evaluations (including 50128 versus 48073 at seed 80021 in later
stages), consistent with wall-clock sensitivity; without a load series its
cause is not identified. Do not select a mechanism based on that apparent gain.

Framework verdict: complete source continuation, typed transient recovery,
Contract/Verification, paired safety and recorded Decision are consistent in
the inspected evidence. Public correctness checks do not prove H/C scientific
fidelity; step 6 is a concrete limitation, not grounds to rewrite outcomes.

Research verdict: valid but unconfirmed local development, with several
implementation-fidelity weaknesses and unresolved initial-search dominance.
Neither original-B0 superiority nor CVRP/v0.4 completion is established.

Under the user's explicit approval to widen both arms equally, the next rung is
[R10](v04-cvrp-r10-wide-budget-b0-preregistration-20260923.md): prospectively
double every formal dimension-band time limit and compare the complete surviving
C source with original B0, using the existing counterbalanced fixed funnel.
C is selected as an ordinary exploratory value with a fully expanded 2/0/4
result and an active medium-case change, not as champion or a causal winner.
A's last screen is 1/1/1 with a large-case loss; B's expanded screen is 1/2/3.
No source is manually merged, repaired or retuned for this check. Existing
negative Decisions, source trees, gates and all unopened held-out populations
are preserved. A larger cap may still be consumed by initial descent; measure
that behavior rather than assume extra ALNS activity. Subsequent autonomous
research can use these implementation facts without a prescribed patch or
host-selected allocation policy.
