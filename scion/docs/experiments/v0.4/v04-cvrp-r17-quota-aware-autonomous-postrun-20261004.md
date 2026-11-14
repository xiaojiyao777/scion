# CVRP R17 read-only postrun and query-efficiency diagnosis

Operator-only analysis, 2026-10-04. Contains validation outcomes: **do not load
this report into H/C or append it wholesale to a research input**. The ordinary
screening-only history remains the research channel. This report does not
authorize a repair, rerun, new campaign, or a new scientific gate.

## Scope and terminal result

The October 4 request authorizes first committing/pushing the preceding work,
then explaining query efficiency and inspecting experiments. Existing work was
committed as `7e1fd7dc` and pushed to `origin/v0.4-dev` before this analysis.
That commit captures the previously frozen quota repair, tests, inputs and
launch handoff; it introduces no retrospective experiment intervention.

[Design](v04-cvrp-r17-quota-aware-autonomous-preregistration-20261003.md),
[status](/home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/status.json)
and [summary](/home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/campaign_summary.json):

- Started October 3 13:40:12 UTC; completed 23:24:56 UTC, or **October 4
  07:24:56 Asia/Shanghai**, about 9 h 45 m later.
- `completed / requested_rounds_completed`, valid, **12/12 evaluated stages**:
  eleven screening stages and one validation stage, seven distinct candidates.
- **178/178 valid pairs**: 166 screening and 12 validation. Zero pair failures,
  protected-objective regressions, formal algorithm errors or infeasible outputs.
- **69/600 physical calls**, all successful at attempt index zero: H38, C31.
  No provider retry, quota event, operational rejection or interrupted attempt.
  The campaign stopped because twelve stages were completed, not because its
  remaining 531 calls or 48-hour guard were exhausted.
- Champion remains v1 / weight revision zero. No promotion; frozen and retained
  stages unopened. The reused validation population is already operator-exposed,
  not independent final confirmation. No superiority over B0-fixed or B0 follows.

Runtime was `505dce03` plus the frozen quota classification change, now captured
in `7e1fd7dc`. Source and scientific gates were unchanged at launch. Injected
regressions, not this no-quota-event run, establish the quota-stop behavior.
The prelaunch suite remains 2554 passed / 1 skipped; it was not rerun here.
This audit reads JSON/JSONL, traces and ordinary source only: no original SQLite,
provider call, candidate execution, campaign mutation or historical-root scan.
No overlap with tests, solvers or maintenance is documented for this measurement;
that is not an exhaustive claim about all external host activity.

## Paired Protocol and recorded Decisions

Every stage compares its cumulative candidate against the unchanged R12-A-fixed
champion, not against its previous branch head. Effects below are medians of
case-level paired total-distance deltas, **champion minus candidate**; positive
means shorter routes, not a percentage. W/L/T counts cases. Initial screening
uses five cases × two seeds, expansion six × four, validation six × two.

| Stage | Candidate / change | Pairs | W/L/T | Median [CI] | Recorded action |
|---|---|---:|---|---|---|
| 1 | A1 incremental VNS kernels | 10 | 3/0/2 | 5 [0,223] | expand |
| 2 | A1 expanded | 24 | 2/0/4 | 0 [0,94.25] | continue, uncertain |
| 3 | B1 boundary-cluster destroy | 10 | 3/0/2 | 17.5 [0,112.5] | expand |
| 4 | B1 expanded | 24 | 2/1/3 | 0 [-34.5,9.5] | continue, quality fail |
| 5 | C1 exact-quota route fragments | 10 | 1/2/2 | 0 [-103,46] | continue |
| 6 | A2 adds exact pair-window DP | 10 | 3/1/1 | 3 [-28,81.5] | expand |
| 7 | A2 expanded | 24 | 4/1/1 | 1.75 [-13.25,106] | continue, uncertain |
| 8 | B2 adds route-diverse ejection chains | 10 | 1/2/2 | 0 [-80.5,18.5] | continue |
| 9 | C2 adds detachability/opportunity scoring | 10 | 1/2/2 | 0 [-72,109] | continue |
| 10 | A3 makes pair-window execution selective | 10 | 4/0/1 | 5 [0,69] | expand |
| 11 | A3 expanded | 24 | 5/0/1 | **15.25 [1.5,82]** | queue_validate |
| 12 | A3 validation | 12 | **2/3/1** | **-1.5 [-2933.75,824]** | abandon |

All twelve raw metric paths are linked by `steps[].protocol_result.raw_metrics_ref`
in the summary. The audit checks every pair's unique case/seed roster, complete
bilateral results, zero fleet violation, loaded/active valid solver, absolute
distance difference and case-median aggregate against those recorded values.
Observed limits are 60/90/120/180 seconds as declared by case dimension; no case
uses the unneeded 240-second tier. Screening seeds are 180001/180007, adding
180023/180043 at expansion; validation uses 180053/180071. Champion-first timing
is an inherited limitation, not a counterbalanced causal speed comparison.

All seven newly generated candidates pass Contract, Verification and canary.
Later expansion/validation rows legitimately reuse their verified source and
have null Contract/Verification fields; these are not failed checks. Recorded
actions agree with the typed Protocol gates, including mandatory expansion and
`VALIDATION_FAIL_CASE_QUALITY`. No Decision is recomputed or revised here, and
no explanatory provider prose is substituted for typed evidence.

## What the final positive screen does and does not show

[Expanded screening](/home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/metrics/fd76101c-cacf-43b0-b970-e4be2deb40ee.json)
has case medians B34 0, tai100a +27.5, X351 +112.5, A54 +1.5, X190 +82,
X513 +3. It is a real local screening pass, not a retained improvement.

[Validation](/home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/metrics/a4823782-7cd2-4758-9493-df07320c9c74.json)
does not reproduce that result:

| Case | Median distance gain | Interpretation |
|---|---:|---|
| B39 | 0 | tie |
| X106 | -59 | loss |
| tai385 | **-5808.5** | large loss in both seeds |
| A62 | -3 | loss |
| X228 | +1632.5 | win in both seeds |
| X627 | +15.5 | one tie, one small win |

For tai385, seeds 180053/180071 produce candidate/champion distances
44083/38881 and 44192/37777. Both sides perform **zero ALNS iterations**;
the candidate records **zero pair-window attempts**. Initial VNS occupies about
138.2 seconds in each candidate execution. Thus these losses cannot simply be
attributed to executed DP work or its new scheduler switch. Inherited incremental
kernels and time-limited initial-search trajectories need investigation, but
these artifacts do not establish whether the cause is an arithmetic/ordering
defect, shape-dependent overhead, or another timing-sensitive path difference.
No candidate is executed to settle that question in this read-only task.

X228 wins while candidate ALNS reaches only one iteration per seed (champion
zero), with zero accepted DP moves. On X351 all four expanded candidate seeds
still have zero ALNS and zero DP attempts; its positive case median therefore
cannot be credited to DP either. This is a cumulative-bundle result, not an
isolated efficacy estimate of the last edit.

The screening telemetry nevertheless supports useful, limited reasoning:

- A1 expanded: 9458 versus 7967 ALNS iterations, but aggregate ALNS best-update
  counts remain 42 versus 42. More iterations do not automatically improve quality.
- A2 expanded: 15207 DP pair attempts / 446 accepted moves, but only 4665 ALNS
  iterations versus champion 7922. Its extra neighborhood displaces other search.
- A3 expanded: 436 DP attempts / 9 accepted moves, 9243 ALNS iterations versus
  champion 7779, and 56 versus 37 best updates. Selective invocation plausibly
  improves the exploration/intensification balance on screening cases.

These are separately timed adaptive candidates with separately measured
comparators, not a paired A2/A3 ablation. Phase gains and accepted moves on
temporary solutions are not additive terminal-objective gains. Final screening
and validation median runtime ratios are approximately 0.99992 and 0.99983:
both use their allotted search time; the result is not a wall-clock speedup.

## H/C fidelity, source continuity and probe limitations

Seven H exports name concrete source mechanisms; C implements actual algorithm
changes rather than comments or scaffolding. A1 changes 2-opt, Or-opt and
2-opt-star scoring; A2 inserts a capacity-constrained, at-most-eight-customer
two-route DP after ordinary VNS/SWAP*; A3 wires `enable_pair_window` to
`repaired_new_best or full_scope`, retaining the initial default. B removes
frequency bookkeeping and substitutes boundary-cluster removal, then changes
complete ejection-chain selection. C changes whole-route overshoot into exact
quota fragments, then changes partial-fragment scoring. These are branch-local
cumulative changes, not automatically inherited improvements from siblings.

All **146 visible C source values across 31 turns** match their correct branch
bases. The champion's 100 non-cache files exactly equal the declared initial
[source](/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/candidate).
Surviving B and C heads each have 100 non-cache files and exactly match their
cumulative history values, with all other files unchanged:

- B: `candidate_workspaces/candidate-55czuk1d`, destroy_repair plus scheduler.
- C: `candidate_workspaces/candidate-3rqixu06`, destroy_repair only.

Paths are relative to the R17 root linked above. Existing bytecode caches are
excluded from ordinary source comparison and left untouched. A is abandoned;
`workspaces/` is empty and no complete A candidate tree survives. Its changed
file contents and successive base contexts remain in history/traces, but the
exact complete executed A stage tree is not independently reidentified here
(`UNIDENTIFIABLE` at that full-stage-source level). Preserve its recorded paired
outcomes while narrowing mechanism/source attribution; do not invent a missing
snapshot, recorder, identity or receipt chain. Earlier superseded stages likewise
do not acquire full snapshots merely because their source values remain visible.

Nine self-authored probes run: eight pass and one fails. Host checks pass on
eight test calls; B1's first test fails undefined-name checking despite its
passing custom probe, then C removes the stale reference and passes. There are
no final research rejections, but that does not imply flawless intermediate work.

Remaining research limitations are specific:

1. A1's probe verifies randomized 2-opt delta arithmetic and calls real modified
   operators for feasibility/cost consistency. It does **not** prove the promised
   old/new fixed-start move-sequence equivalence across Or-opt and 2-opt-star,
   directed cases, or timed large-shape performance. Feasible exact final costs
   alone cannot establish that no improving transition was accidentally skipped.
2. A2 tests real route objects and the real DP, and wraps the actual DP during a
   `_vns` call; however, it supplies an empty ordinary operator list. A3's
   [probe](/home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/llm_traces/20261003T210622132380_code_research_turn_a19ec26b.json)
   mocks both SWAP* and DP and never exercises the real scheduler. This proves
   local switch dispatch, not full-entry activation, performance, or the whole
   scheduler condition. Static source wiring exists; integration proof is weaker.
3. C2's [failed probe](/home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/llm_traces/20261003T202807168983_code_research_turn_c588957b.json)
   reports `assertion_error / call / line67`. That line expects total cost 13,
   after earlier assertions already establish remaining routes `(1,2)` and `(5,)`.
   Its own matrix gives `(10+1+1)+(1+1)=14`, so the expected scalar is wrong.
   C then changes actual scoring (a capped half-weight opportunity penalty) and
   replaces the probe with a different real-instance exact-saving case plus a
   719-customer deadline case. This is a genuinely new executable value, not a
   test-text-only bypass, but it does not demonstrate that the first algorithm
   was wrong or revalidate the original cross-route test. A self-authored oracle
   error can consume a research attempt even when host correctness checks pass.

The proposed next research support is stronger real-entry, mathematical-reference
and deadline falsification, not another mandatory mechanism or host-selected
solver patch. Public synthetic shapes must remain distinct from private formal
cases; validation details in this report must not become model training hints.

## What “query inefficiency” means

This refers to **research-tool actions that spend model calls without obtaining
the intended source evidence**, not database query latency or solver throughput.
The severe observation belongs to the
[Warehouse control](v04-r17-warehouse-quota-control-20261003.md), not CVRP R17.

| Warehouse C error | Count | Direct cause |
|---|---:|---|
| `source_not_visible` | 17 | 15 reads and 2 searches of `models.py`, absent from the C corpus |
| `command_field_invalid` | 11 | `search_source` explicitly supplies `path: ""`; whole-corpus search must omit `path` |
| `selector_not_found` | 2 | patch selector does not match current source; an editing error, not a query |

That is **28 failed query actions plus 2 edit errors among 43 C research turns**
(about 70% tool-error turns), not 30 database failures. There are 70 physical
calls overall, including 25 H, 43 C research and 2 C finalization calls. A failed
local action still consumes its provider turn; read/search-specific accounting
depends on whether command parsing succeeded.

Concrete evidence: the [empty-path search](/home/clawd/research/scion-experiments/v04-r17-warehouse-quota-control-20261003/llm_traces/20261003T132415143279_code_research_turn_ede522ac.json)
uses `{"action":"search_source","query":"get_max_pickups","path":""}`.
The [unavailable read](/home/clawd/research/scion-experiments/v04-r17-warehouse-quota-control-20261003/llm_traces/20261003T132411480046_code_research_turn_63553245.json)
asks for `models.py`. The inventory contains six editable operators and two
public test files, not `models.py`.

This has **both model-use and framework context-composition causes**:

- The model repeats unavailable requests and violates the declared nonempty
  optional-path schema. Valid whole-corpus searches later succeed when path is
  omitted. Two editing selectors also fail independently.
- The interface genuinely cannot supply the requested public dependency.
  Warehouse declares `models.py` in `development_workspace_paths`, permits its
  import and keeps it frozen for edits. Yet
  [`_build_editable_source_context`](../../../scion/proposal/context_manager/code_context.py)
  only collects editable, non-frozen surface files and public test text;
  [`research_files_from_context`](../../../scion/proposal/edit_protocol/source_discovery.py)
  combines precisely those two sets. The development sandbox having a file does
  not make it readable through C's query tool. Thus “only tell the agent to read
  models.py correctly” cannot solve this part.
- Error feedback is bounded but coarse: `command_field_invalid` does not identify
  the field or say to omit an optional path, and `source_not_visible` does not
  explain that a requested dependency is absent from the permitted corpus.

The earlier control verdict of no shared execution/scientific blocker remains
bounded to its exercised checks. It should **not** be read as proof that the
research interface has no context defect. This audit identifies that narrower
usability gap without changing the completed negative control outcomes.

CVRP R17 has only **one failed source query**: a search supplies directory
`policies/baseline_modules` where an exact listed file is required. Its other
tool error is a duplicate file path in one patch. All seven candidates still
finish research. The Warehouse error rate is therefore not the explanation for
CVRP's negative validation, and raising CVRP's 600-call cap would not address it.

## Verdict and next falsifiable work — proposed, not executed

**Framework execution:** R17 completes its declared funnel with complete valid
pairs and no observed provider failure or gate bypass. Source delivery matches
branch lineage. Separately, Warehouse exposes a public read-only dependency gap
and coarse query feedback; full A-stage source is unavailable after ordinary
abandonment. None of these facts authorizes rewriting historical Decisions.

**Research effectiveness:** concrete cumulative research and a positive local
screen, but negative validation and no retained improvement. Throughput,
activation and probe-oracle reasoning remain incomplete. CVRP/v0.4 stay open.

If subsequently authorized, first separate public read permission from edit
permission using problem-declared support sources, preserving frozen edit
protection and held-out exclusion. Improve bounded field/path correction
feedback, with source-continuation and leakage regression coverage and a fresh
Warehouse control. Do not expand access to arbitrary files or add quality gates.

For CVRP, strengthen optional real-entry and exact-reference test support so
Scion can investigate its own active initial-search kernels and cost tradeoffs.
Do not prescribe a particular search mechanism, loosen Protocol thresholds,
inject private validation details, manually merge A into the next source, or
equate extra iterations with improvement. Any later experiment needs its own
authorization, frozen inputs and fresh output; do not resume R16/R17/control.
