# CVRP R19 postrun: better probes and a screening-pass discovery

## Scope and terminal

Read-only Experiment Analysis profile, entry handoff/runbook, R19 preregistration,
status/summary, all twelve referenced metric JSON files, H/C traces and the three
surviving complete candidate trees. No original SQLite, terminal resume, source
reconstruction, provider call or extra solver run was used for this analysis.

Runtime/scientific inputs were frozen at6380a59e. Campaign started October6
09:31:21 UTC /17:31:21 Beijing and completed October7
02:19:30.476275 UTC /10:19:30 Beijing. Carrier is dead with exit0; the JSON
independently records valid completed12/12, requested_rounds_completed.
All320 formal pairs are valid. Seven H/C candidates, twelve screening stages,
zero validation/frozen, no promotion. The final branch is ready_validate, but
the requested-stage cap ended the campaign. This is not a provider-budget stop:
105/600 physical calls,61 H and44 C, all successful at attempt0 on
gpt-6.1-sol high. No quota/overload/research rejection is recorded.

Evidence root:
`/home/clawd/research/scion-experiments/v04-cvrp-r19-reliable-probes-autonomous-20261005`.
Use `status.json`, `campaign_summary.json`, `research_history.jsonl`, and the
explicit metric refs in each summary step. No known overlapping operator tests,
maintenance or competing solver was initiated; this does not rule out host noise.
Default autonomous pair order remains champion-first, not counterbalanced.

## Framework correctness and complete source

All seven new candidates pass Contract, Verification and canary. Expansion
reuses each exact evaluated candidate without another H/C generation. Metrics
contain complete pairs, zero failures, feasible active intended algorithms,
zero fleet violations and exact agreement between absolute-distance differences
and recorded deltas. Recomputed per-case medians agree with all twelve summaries.
Recorded Protocol outcomes and Decisions are retained, never postrun rejudged.

The100-file champion equals the selected R13 `input_snapshots/candidate`
(R12-A-fixed), not original B0 and not B0-fixed. The three terminal100-file
candidate trees have the same file set and differ from that champion only in
`policies/baseline_modules/local_search.py`:

| Branch | Surviving complete source | Mechanisms retained |
|---|---|---|
| A,88bfb89b | `candidate_workspaces/candidate-560r6jum` | exact SWAP* insertion cache; removal-saving supplemental exchanges; ordinary-swap demand-feasible enumeration |
| B,58ada312 | `candidate_workspaces/candidate-oreubqrr` | exact Or-opt destination-minimum cache; shared singleton relocate cache |
| C,4294501e | `candidate_workspaces/candidate-85cgofi9` | directed two-opt-star prefix costs; feasible prefix-demand cut intervals |

These terminal bundles are FULL_SOURCE_IDENTIFIED. Only these three complete
candidate directories survive. Earlier superseded bundles have H/C/patch and
metric records but no separately surviving complete tree; do not attribute their
science to a reconstructed executable or pretend all seven complete trees remain.
A3's final exact replacement also reproduces the surviving local_search bytes
from its actually delivered session edit base (in-memory comparison only).

No exercised framework execution/boundary defect was found. This verdict is
narrower than universal correctness and does not establish algorithm benefit.

## H and C research

H made30 read_source,10 read_history,8 search_source,6 history-frontier reviews
and7 finalizations. Later proposals consume whole safe screening feedback and
distinguish cumulative bundle evidence from component causality. All mechanisms
target the actual ordinary local-search implementation, with falsifiable exactness,
capacity/deadline and final-quality predictions. No host prescribed them.

One explicit grounding error remains: C-branch's first H (round4) claims to retain
the sibling Or-opt cache. It is a fresh champion:v1 branch; its actual H context
has no branch_current_code and its visible source lacks that cache. C receives
the correct champion source and implements only the two-opt-star change. Thus
the inheritance sentence is false, not a source-delivery/branch-isolation failure.
Later C-branch H explicitly observes that Or-opt/relocate caching is absent.
Relevant H trace: `llm_traces/20261006T134140902824_hypothesis_research_turn_2ee3f572.json`.

Seven C sessions use3/12/12/3/6/5/3 calls respectively. No tool result reports
an error. The Or-opt session revises its complete file twice before testing,
correcting two accidentally changed boundary endpoints and an undefined capacity
reference; draft2 replaces draft1 successfully against the original edit base.
Both submitted Or-opt probes test draft2. This is observed successful complete-draft
revision, not evidence that the failed-edit case from R18 cannot recur.

Eight submitted falsifiers contain37 collected-style test functions in total
(including overlapping probes, not37 independent experiments). Every final C
receives passed falsifier and D1/D1b/D2/D3/D4 feedback for its final draft. No
pytest-exit5 event or rejected-import correction occurs in this CVRP run; those
feedback branches are not claimed as live coverage here.

Probe strengths:

- Explicit hand-checked reference costs and independent full-route enumeration;
  exhaustive permutations compare accepted transition sequences, not merely a
  candidate helper against itself. Final ordinary-swap probe checks more than1000
  feasible state/frontier combinations and requires some accepted transitions.
- Demand boundaries, zero-demand customers, earliest-position ties, empty/singleton
  routes, stale-cache invalidation and interruption-before-commit are covered by
  candidate-specific probes. Wrappers generally call real collaborators.
- Small synthetic real solve entries keep normal construction/registry/guards and
  observe completed insertion/index calculations. A3's index is checked against
  independently enumerated feasible positions during the real entry.

Remaining limits:

- Real-entry examples are narrow synthetic fixtures, often a single small size and
  seed1703. Several assert entry/finished pricing but do not require an accepted
  improvement from that changed mechanism or its retention in the returned best.
- The719-customer/.2-second seed1709 checks feasibility/deadline behavior; it may
  finish its useful budget in construction. A3 separately calls the operator with
  an expiring context. Neither establishes completed large-instance solve-to-swap
  integration, nor formal-case activation/cost reduction.
- Some probe comments are stale (C2 says54/36 while executable independently
  computed assertions are66/48). Passing assertions do not validate all prose.
- Formal telemetry is family/phase level. It cannot isolate the exact helper's
  time saving or causally allocate cumulative gains to the latest edit.

P15/P16 support, different model and denser sampling are bundled interventions;
there is no randomized ablation attributing improved research behavior to one.

## Complete screening trajectory

Positive delta is R12-A-fixed distance minus the complete candidate distance.
Each row is a separate stage estimand; expanded screening reruns shared cells.
Do not pool320 observations as independent samples or merge stage confidence
intervals. Case median here means median of case-level paired medians.

| Rounds | Candidate change | Initial case W/L/T; median | Expanded case W/L/T; median [CI] | Outcome |
|---|---|---|---|---|
|1|A1 exact SWAP* insertion cache|1/1/3;0|—|fail|
|2–3|B1 Or-opt delta/cache|2/0/3;0|2/0/4;0 [0,71]|uncertain|
|4–5|C1 two-opt-star prefix pricing|2/0/3;0|2/1/3;0 [-2.5,17]|fail|
|6|A2 supplemental SWAP* removal savings|1/2/2;0|—|fail|
|7–8|B2 singleton relocate cache|2/0/3;0|2/0/4;0 [0,172.75]|uncertain|
|9–10|C2 feasible two-opt-star cut intervals|2/0/3;0|2/0/4;0 [0,67.25]|uncertain|
|11–12|A3 ordinary-swap demand enumeration|3/0/2;+35|4/0/2;+17.75 [0,5841.5]|SCREENING_PASS; queue_validate|

Final initial metric `metrics/82a222b8-75ca-46b6-ad18-b79cde64dea5.json`;
expanded metric `metrics/e82e647d-27bf-46b1-8902-187b1fa5a39e.json`.
Expanded seeds in order220009,220013,220019,220021,220057,220063:

| Case | Six paired distance deltas | Median |
|---|---|---:|
|B-n34-k5|0,0,0,0,0,0|0|
|tai100a|105,35,31,78,-43,-11|33|
|X-n351-k40|11664,11664,11636,11561,11683,11560|11650|
|A-n54-k7|0,5,-3,5,0,5|2.5|
|X-n190-k8|76,-52,76,-17,25,76|50.5|
|X-n513-k21|0,0,0,0,0,0|0|

Pair W/L/T17/5/14. Case-level4/0/2 hides five individual losses; smaller gains
are not uniformly stable. X351 candidate distance is31776 in every expanded
seed versus43336–43459 (about26.7–26.9% better). Initial four-seed results also
have31776, but overlap in seeds and discovery selection prevents treating them
as independent confirmation. X351 initial VNS takes102.005–107.693 seconds
versus138.173–138.548, leaving2–3 candidate ALNS iterations versus0. Final
post-initial objective stays31776; merely opening ALNS does not explain the gain.
X513 still has zero ALNS in both arms and all ties. X190 candidate stays17800
while its comparator varies; larger initial-VNS time and mixed pair signs remain.

Research verdict: materially stronger, test-supported **discovery screening
signal**, not validation, promotion, retained benefit, per-component causality or
superiority over B0-fixed/original B0. The final pending validation is solely a
stage-cap limitation; never resume or retroactively widen R19.

## Evidence-backed next action

Keep the discovered exact A3 bundle unchanged. No evidenced shared-core repair
or host-designed algorithm edit is justified before confirmation. Optimize the
next measurement design: fresh source-isolated fixed-candidate funnel, AB/BA
counterbalancing, eight screening seeds and four per later population, unchanged
gates and per-solve limits. Compare directly with the existing B0-fixed complete
source (R13 baseline), keeping its common constructor repair. This is a NEW
contrast, not a repeat of R19's R12-A-fixed contrast. Preserve all three changed
research files between those arms; no sibling merge or post-selection patch.

See [R20 prospective design](v04-cvrp-r20-r19-final-b0-fixed-preregistration-20261008.md).
Already exposed validation remains development evidence; frozen and independent
retained open only after all preceding passes. A retained result would concern
B0-fixed, not retroactively close unchanged-original-B0 superiority. Next
autonomous H/C must ground inheritance in its delivered current tree and keep
large real-path completion distinct from timeout-only probes; do not supply
private later-stage outcomes to it. No new Warehouse control is needed because
shared runtime, adapter and algorithms are unchanged.
