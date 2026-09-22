# CVRP R7: completed autonomous continuation, improvement unconfirmed

Read-only analysis on 2026-09-22, using the Experiment Analysis profile and
the operations postrun method. The [prospective design](v04-cvrp-r7-autonomous-source-continuation-preregistration-20260921.md)
is unchanged. No campaign artifact, source, metric or historical Decision was
edited, and the original SQLite database was not opened.

## Scope and terminal

Runtime: main checkout `v0.4-dev`, implementation unchanged from `e405bfd2`;
R7 launched from `ffde7f66`, with the subsequent `75ce0265` documentation-only.
Problem: CVRP `solver_design`; provider: `gpt-5.6-sol`, reasoning high.

Evidence root:
`/home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921`.
Read [status](/home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/status.json),
[summary](/home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/campaign_summary.json),
and [ordinary history](/home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/research_history.jsonl).

- Started `2026-09-21T23:21:02Z`; terminal status updated
  `2026-09-22T03:23:30.659934+00:00` (about 4 h 2 min).
- `completed`, `requested_rounds_completed`, validity `valid`: 13 scheduled
  steps, 12 evaluated screening stages, one pre-evaluation research rejection.
  Eleven distinct candidates were formally screened; one was also expanded.
- No validation, frozen evaluation or promotion. Champion remains version 1,
  weight revision 0: the initial complete minus-2-for-1 source, not original B0.
- The dead tmux pane has no usable exit-status value. JSON establishes normal
  completion independently. No Scion solver or campaign process was live at audit.
- Two C requests hit the declared 300-second provider timeout; two charged
  redispatches of that request eventually succeeded. No solver failure is implied.
  There is no identified R7 cleanup overlap, but no contemporaneous host-load
  time series establishes a contention-free run.

## H/C research and source continuity

All 139 physical provider calls are traced: H 73, C 66. There were 12 H/C
attempts, each ending with H `finalize_hypothesis` and C `ready`; step 9 reused
the preceding candidate without another H/C. Call counts include the two failed
C dispatches, not hidden retries.

H inspected real scheduler, construction, repair and local-search source and
recent complete history. Its initial index offered three R4/R5/R6 observations
plus 65 older scientific records. No H action opened the three prior-observation
records (`history-0001` through `history-0003`); availability is not attention.
Later H sessions did read their branch's recent negative results and other
branches' screening results. In particular, step 13 read step 10's cumulative
branch result before removing the randomized repair arm. Do not introduce a
mandatory history-attention or mechanism-novelty gate in response.

The table gives the new H/C mechanism per attempt, not an isolated causal
contrast. Every Protocol comparison was with the fixed initial champion, while
C edited its own branch's latest verified provisional source.

| Step | Branch | H/C calls | New mechanism or action | Formal case W/L/T; median [CI] | Recorded outcome |
|---:|---|---:|---|---|---|
| 1 | A | 5/8 | Sparse stagnation-triggered SWAP*; LS helper and scheduler integration | not evaluated | Patch Contract rejection |
| 2 | B | 4/7 | Best-anchored ruin/recreate intensification | 0/1/2; 0 [-31,0] | continue |
| 3 | C | 7/3 | Cross-route assignment-opportunity worst removal | 1/1/1; 0 [-40,30] | continue |
| 4 | A | 7/3 | Route-distinct regret-2/3 insertion rankings | 1/1/1; 0 [-17,263] | continue |
| 5 | B | 7/5 | Replace preceding intensification with double-bridge kick and VNS | 0/1/2; 0 [-45,0] | continue |
| 6 | C | 7/8 | Add randomized-regret fourth repair arm | 0/2/1; -7 [-361.5,0] | continue |
| 7 | A | 6/5 | Bounded best-improvement relocate | 1/1/1; 0 [-16.5,539] | continue |
| 8 | B | 7/5 | Best/current route-transplant path relinking | 1/0/2; 0 [0,228.5] | expand initial quality |
| 9 | B | 0/0 | Exact step-8 candidate, expanded sample | 0/1/5; 0 [-19.75,0] | continue |
| 10 | C | 5/4 | Bounded two-hop ejection before creating a singleton route | 1/1/1; 0 [-74.5,267] | continue |
| 11 | A | 5/5 | Re-enable existing 2-for-1 in the default VNS registry | 1/1/1; 0 [-5,771.5] | continue |
| 12 | B | 7/9 | Route-pool recombination, including new ordinary helper module | 0/1/2; 0 [-293.5,0] | continue |
| 13 | C | 6/4 | Remove randomized-regret from the active repair portfolio | 2/0/1; 40 [0,608.5] | expand required; run target reached |

Branch IDs: A `a909cef4-bc15-4a18-9c7d-739270f49daf`, B
`ea8574d8-18dc-4126-bb85-a70b5c5a419d`, C
`8485adcb-706a-4d81-a2fd-29cee75c0aa3`.

For trace attribution, chronologically group `llm_traces/*.json` whenever H
follows C; the 12 groups correspond to steps 1–8 and 10–13. The final C trace
contains the exported draft and tool results. All final drafts had a passing
5/5 local patch test. Step 6 first had a failing local test and revised before
export; open-session revision is not a repair of a terminal attempt.

Step 1's approved H target was `scheduler.py`, but the exported primary change
was `local_search.py`, with scheduler as an additional change.
`C4b_patch_action_target` correctly rejected that structural mismatch before
Verification or Protocol. The passing local test was not Contract approval.
Later attempts were fresh H/C sessions; this rejected patch never became A's
research head. The CLI lineage/failure report's zero failures covers evaluated
lineage only and must not erase this summary step.

The other eleven exports passed Contract, Verification and canary. Their C
patches implement executable mechanisms, not scaffolding-only changes; this
does not mean every mechanism ran on every case. Step 13 faithfully removes
the active randomized arm but retains its unused helper and import. No cleanup
was applied to that exact evaluated source. Step 11's return to 2-for-1 was an
autonomous choice, not evidence overturning R5/R6.

The final complete source trees remain directly readable:

- A: `candidate_workspaces/candidate-qy4rpb5s`, 100 ordinary files.
- B: `candidate_workspaces/candidate-zja6m272`, 101 files including `route_pool.py`.
- C: `candidate_workspaces/candidate-3bsvzm8k`, 100 files.

These are `FULL_SOURCE_IDENTIFIED` for steps 11/12/13. Older stage workspaces
were normally disposed. For those stages, an in-memory compatibility check
applied final ordinary C drafts to the complete initial tree, retaining only
successful branch exports. Every initially visible C source matched its branch
base; the three resulting final trees matched every ordinary file in the
surviving complete snapshots. Earlier stages are `PATCH_FALLBACK_IDENTIFIED`,
not falsely described as independently retained stage snapshots. Nothing was
written back, and no recorder, hash authority or replay requirement was added.

## Paired science and attribution limits

Initial screening: B-n34-k5, tai100a, X-n351-k40, each at seeds 40009/40013.
Step 9 additionally used A-n54-k7, X-n190-k8, X-n513-k21 and seeds
40031/40037: six cases by four seeds. Budgets remained dimension-based
30/45/60/90/120 seconds. Positive distance delta means comparator minus
candidate, with fleet violation protected. Case deltas are medians over seeds;
the reported effect is the median over cases, not over all pairs.

All 90 formal pairs / 180 arms completed with valid solutions and no reported
solver errors, fleet regression or candidate/comparator/shared/bilateral
failure. Raw objective subtraction and all case medians reproduce the records.
Pair W/L/T totals are 23/17/50, accounting only: repeated adaptive candidates
and samples cannot be pooled into an effect estimate.

R7 used the ordinary autonomous Protocol path: champion first, candidate second.
Its raw pairs do not contain `paired_execution` order records. This is not the
explicit AB/BA counterbalancing used by the fixed-candidate driver; do not claim
AB/BA was verified for R7. The unchanged `stages.py` default path explains the
ordering. This matters for wall-clock-limited search and possible time drift.

Exact metric files under the evidence root's `metrics/`, in step order 2–13:

```text
58f87fd4-9c97-4f56-afde-e379c1d4a616.json
7612c1f0-8ade-47ef-b549-64fb4df48331.json
e8ebcf17-e6bf-4659-b7c8-354aa2e90f39.json
ef135722-fe48-4e80-9a34-a463f4e32f63.json
bd256b86-9bb7-40ee-902b-3a7f3e4cfc42.json
9d3c274b-091f-4386-af2f-9cd2698368c2.json
3365ae45-693e-485a-85d8-ae65e277d727.json
9aa0dffb-cf88-4700-9635-c63229796f4e.json
151c57cb-fb1b-4f1d-879a-af1efabb6f5a.json
d86e7700-558e-4b56-8242-637b68344da7.json
297a8172-0da2-419f-8dbc-82c326ad32c8.json
24ac3290-cb42-4a19-bcd4-46f36fe4fc65.json
```

Two observations prevent treating the final positive screen as confirmation:

1. Step 8's positive initial X-n351-k40 case median +228.5 became -39.5 in
   step 9's expanded sample, with no winning cases overall. The corresponding
   `SCREENING_FAIL_CASE_QUALITY` is preserved, not overruled by the initial CI.
2. Across all 26 X-n351-k40 pairs, both arms executed zero ALNS iterations.
   Construction plus initial VNS exhausted the algorithm-local budget (about
   69.84 seconds within the nominal 90-second subject limit). Step 13's only
   differences from the initial champion are repair code and an unused scheduler
   import; its construction and initial VNS are byte-identical. Its +917/+300
   seed deltas therefore do not demonstrate benefit from the changed ALNS
   mechanism. The identical comparator itself ranges 47,735–51,914 at seed
   40009 and 47,889–50,892 at seed 40013 over 12 evaluations per seed. Both
   step-13 comparator values are the worst of those repeats. This establishes
   timing-sensitive variability, not an identified host-load cause or fraud.

On tai100a, step 13 improves +38/+42, median +40. Candidate ALNS iterations are
13/18 versus comparator 23/21; B-n34-k5 ties with 508/492 versus 645/630.
Thus the changed portfolio is active on the small/medium cases, with fewer
iterations and a positive medium-case outcome. It is a useful candidate signal,
not proof of isolated removal/ejection causality or reproducibility.

## Independent verdicts and next action

Framework correctness: observed H/C, structural rejection, verified branch
continuation, exact expansion and deterministic gate outcomes are consistent
with the current boundaries. Provider timeouts stayed operational. No evidence
here warrants changing Contract, Verification, Decision or generic core.
Default fixed execution order is a measurement limitation, not evidence that
the framework promoted an unqualified candidate; there was no promotion.

Research effectiveness: meaningful autonomous source research and informative
negative expansion, but **no confirmed improvement**. Step 13 is a discovery
candidate with an unexecuted expansion request at a normal round-count stop.
The final C tree still warrants one bounded prospective check because tai100a
improved at both seeds. It does not warrant an immediate success claim, a
host-authored solver patch, or reopening the terminal campaign.

Next: [R8](v04-cvrp-r8-r7-final-b0-preregistration-20260922.md), a fresh,
provider-free exact-tree comparison with original B0, using fresh seeds and the
existing counterbalanced fixed funnel. Its screening cases are outcome-known
adaptive development. Validation/frozen/retained outcomes stay unopened unless
the unchanged preceding gates pass. This new B0 estimand does not backfill R7's
pending minus-2-for-1 expansion. Preserve all R7 source/traces/metrics unchanged.
