# Scheduler Reclaim 12R CVRP Branch Research Quality Analysis

Experiment:
`/home/clawd/research/scion-experiments/v04-scheduler-reclaim-verify-12r-gpt55-20260607T233323Z-12r-gpt55-20260607T233323Z-claw/campaign`

Report date: 2026-06-08

Required references read first:

- `scion/design/scion-architecture-v3.md`
- `scion/reports/architecture-audit-v0.4/remediation-status.md`
- `scion/reports/experiments/v04-scheduler-reclaim-verify-8r-gpt55-20260607T222206Z-analysis.md`
- `scion/reports/experiments/v04-scheduler-reclaim-verify-8r-gpt55-20260607T222206Z-framework-acceptance.md`

## Executive conclusion

This is a valid completed 12R CVRP campaign at the framework/accounting level:
`run_validity_status=valid`, `run_complete=true`,
`completed_requested_rounds=true`, `effective_rounds_completed=12`,
`formal_screened_candidates=12`, `protocol_evaluated_candidates=12`,
`protocol_stage_counts.screening=12`, and
`scheduler_active_slot_blocked_attempts=0`. The one extra proposal attempt is
properly isolated as a pre-Protocol quality block:
`proposal_attempts_total=13`, `quality_blocks=1`, caused by the
`staged_search_budget` code session failing algorithm smoke after three code
attempts. It did not count toward the 12 screened/formal budget.

Research-quality conclusion: the agent is doing real mechanism-level algorithm
research, not just reducing token/tool usage. It forms concrete hypotheses,
implements actual solver-design changes, receives Contract/Verification/Canary
and screening feedback, and sometimes follows branch-local evidence into a
mechanistically coherent next step. The best examples are the
`route_limit_aware_repair` lineage in rounds 5-7 and the acceptance/plateau
lineage in rounds 9-10.

The algorithmic signal is still weak. No candidate reached validation, no
candidate reached promotion, and no result supports a VRP quality claim beyond
screening weak positives. The clearest weak-positive trace is
`052ead3f` rounds 5-6: round 5 produced 1 case win, 1 case loss, 4/3/9 pair
W/L/T; round 6 improved to 1 case win, 0 case losses, 5/3/8 pair W/L/T. But
both have median delta 0.0, negative CI low, and win rate far below the
screening gate. Later acceptance variants produced only one pair-level win and
zero case wins. Round 11 produced balanced movement but non-positive CI and was
correctly abandoned.

Cross-branch propagation exists and is proposal-visible: every hypothesis
manifest includes `cross_branch_research_map`; later prompts include
`sibling_branches`; `campaign_summary.json` records
`policy=proposal_observability_only` and
`decision_input_policy=excluded_from_decision_features`. The agent clearly uses
some sibling lessons: after no-effect route-merge and route-limit branches, it
moves to acceptance, scheduler budget, cross-route reconnection, and seed
construction. However, the cross-branch research map is not yet strong enough:
it still allows repeated route-compaction/route-limit/local-search/VNS-adjacent
ideas, and `near_duplicate_count=1` plus several repeated runtime-saturation
signals show that the map is more descriptive than directive.

Recommendation: do not proceed directly to 20R as a research-quality gate. It
is safe to run longer from a framework stability perspective, but the next
engineering step should be to improve the cross-branch research map, branch
lesson propagation, and quality/scheduler gates before using 20R as a stronger
agent-research claim. If 20R is run immediately, treat it as framework stress
evidence, not as algorithm research acceptance.

## Evidence scope

Read-only evidence inspected:

| Evidence | Count / notes |
|---|---:|
| Required design/status/reports | 4 files |
| Run/accounting files | `status.json`, `campaign_summary.json`, `run_status.json`, `exit.txt` |
| SQLite tables | `branches`, `hypotheses`, `experiment_events`, `champions` |
| DB event rows | 63 total: 26 `agentic_proposal_session`, 12 `experiment`, 12 `decision`, 13 `scheduler_result` |
| Formal candidate index | 12 rows |
| Candidate artifacts | 12 `candidate.patch.json`, 12 `candidate.diff` |
| Candidate metrics | 12 formal screening metrics plus 24 replay metrics present |
| LLM traces | 92 files, all `gpt-5.5`, all `ok=true` |
| Agentic sessions | 26 sessions: 13 hypothesis sessions, 13 code sessions |
| Tool-selection traces | 46; all have prompt manifest refs and visibility ledgers |
| Replay identity | 12/12 formal candidates complete |

Top-level accounting:

| Field | Value |
|---|---:|
| `requested_rounds` | 12 |
| `effective_rounds_completed` | 12 |
| `formal_screened_candidates` | 12 |
| `protocol_evaluated_candidates` | 12 |
| `protocol_stage_counts.screening` | 12 |
| `protocol_stage_counts.validation` | 0 |
| `protocol_stage_counts.frozen` | 0 |
| `proposal_attempts_total` | 13 |
| `quality_blocks` | 1 |
| `scheduler_active_slot_blocked_attempts` | 0 |
| `lineage_integrity.status` | `complete` |
| `evidence_integrity.status` | `complete` |

Trace accounting:

| Request kind | Calls | Input tokens | Output tokens | Reasoning tokens | Model |
|---|---:|---:|---:|---:|---|
| `hypothesis_target_intent` | 13 | 404,785 | 2,343 | 0 | `gpt-5.5` |
| `hypothesis` | 13 | 548,382 | 11,397 | 0 | `gpt-5.5` |
| `tool_selection` | 46 | 589,033 | 1,907 | 0 | `gpt-5.5` |
| `code` | 20 | 599,970 | 55,740 | 0 | `gpt-5.5` |
| total | 92 | 2,142,170 | 71,387 | 0 | `gpt-5.5` |

## Candidate summary

| R | Branch | Candidate | Mechanism | Surface/files | Case W/L/T | Pair W/L/T | Median | CI | Decision |
|---:|---|---|---|---|---:|---:|---:|---|---|
| 1 | `860de988` | `e72554ee07941720` | `route_merge_local_search` | `local_search.py` | 0/0/8 | 0/0/16 | 0.0 | [0.0, 0.0] | `continue_explore` |
| 2 | `860de988` | `d5fcba1a02ca5df0` | slack-gated `route_merge_local_search` | `local_search.py` | 0/0/8 | 0/0/16 | 0.0 | [0.0, 0.0] | `continue_explore` |
| 3 | `fe3b564a` | `00902c22c1de0f65` | `route_limit_aware_repair` | `destroy_repair.py`, `scheduler.py` | 0/0/8 | 0/0/16 | 0.0 | [0.0, 0.0] | `continue_explore` |
| 4 | `fe3b564a` | `f4c4416f505cdf81` | `search_observability_bridge` | `telemetry_bridge.py`, `scheduler.py` | 0/0/12 | 0/1/23 | 0.0 | [0.0, 0.0] | `continue_explore` + park |
| 5 | `052ead3f` | `0f8a99e59c717d1e` | ejection-assist `route_limit_aware_repair` | `destroy_repair.py`, `scheduler.py` | 1/1/6 | 4/3/9 | 0.0 | [-1.0, 0.5] | `continue_explore` |
| 6 | `052ead3f` | `16f3f2c3389ac7b4` | route-risk scheduler integration | `scheduler.py` | 1/0/7 | 5/3/8 | 0.0 | [-3.0, 1.0] | `continue_explore` |
| 7 | `052ead3f` | `9423d6dbed0ea15a` | scarcity-gated scheduler integration | `scheduler.py` | 0/1/7 | 2/3/11 | 0.0 | [-2.0, 1.5] | `abandon` |
| 8 | `15acd613` | `1107470d8a5b0ca2` | `cost_plateau_reheating_acceptance` | `acceptance.py`, `scheduler.py` | 0/0/8 | 0/0/16 | 0.0 | [0.0, 0.0] | `continue_explore` |
| 9 | `ee4bfde3` | `f9bed97a1cd14b9a` | `diversified_acceptance_plateau_escape` | `acceptance.py`, `scheduler.py` | 0/0/8 | 1/0/15 | 0.0 | [0.0, 0.0] | `continue_explore` |
| 10 | `ee4bfde3` | `c911df1404367403` | `plateau_escape_vns_gating` | `scheduler.py` | 0/0/8 | 1/0/15 | 0.0 | [0.0, 0.0] | `continue_explore` |
| 11 | `f9b753e9` | `0d72e940f91c7968` | `cross_route_2opt_reconnect` | `local_search.py` | 0/0/8 | 3/3/10 | 0.0 | [-2.5, 0.0] | `abandon` |
| 12 | `2e6e8e5d` | `50e88b7a29172685` | `route_limit_seed_diversification` | `construction.py`, `scheduler.py` | 0/0/8 | 0/0/16 | 0.0 | [0.0, 0.0] | `continue_explore` |

All 12 candidates passed Contract, Verification, Canary, and formal screening
execution. All raw metrics are `stage=screening`, complete, with 0 failed
candidate/champion pairs.

## Candidate analysis by round

### Round 1: `860de988`, `route_merge_local_search`

Hypothesis: VNS has relocate, swap, Or-opt, and two-opt-star style moves, but
no deterministic whole-route absorption move. Add a bounded local-search
operator that tries to eliminate short/light routes by reinserting all source
customers into other feasible routes.

Code change: modified `policies/baseline_modules/local_search.py`; added
`_route_merge_local_search` and `_try_absorb_route`; registered the operator in
`_default_vns_operators`; emitted `context.record_iteration`,
`record_move`, and `record_phase` telemetry.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening was 8 cases / 16 pairs, all ties. Runtime evidence was high and
sufficient but only supporting/tie-break guidance, not standalone optimization
signal. Decision reason codes included `SCREENING_FAIL_WIN_RATE`,
`SCREENING_NEUTRAL_SIGNAL_CONTINUE`,
`SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`,
`SCREENING_RUNTIME_BUDGET_SATURATION`, and
`BOTH_RUNTIME_BUDGET_SATURATION`. Finalizer created a clean-fork path rather
than retaining this head as a quality candidate.

Assessment: mechanism and code match the hypothesis. It was a legitimate new
VNS neighborhood, but produced zero objective effect and runtime pressure.

### Round 2: `860de988`, slack-gated `route_merge_local_search`

Hypothesis: the round 1 route-merge activated but had no wins and wasted scans.
Refine the same operator by gating route absorption on aggregate spare capacity
and a cheap savings lower bound before attempting full greedy insertion.

Code change: again modified `local_search.py`; added `_route_merge_candidates`,
`_route_merge_gate`, and a destination-restricted `_try_absorb_route`; retained
the same mechanism id and telemetry.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening was again 0/0/8 cases and 0/0/16 pairs. Runtime confidence was
`low_cached_champion` and aggregate runtime was excluded. Decision reason codes
were `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`,
`TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`,
`SCREENING_RUNTIME_BUDGET_SATURATION`, and
`CANDIDATE_RUNTIME_BUDGET_SATURATION`. Finalizer released the active slot due
to repeated no-effect/zero-effect state.

Assessment: coherent same-branch follow-up, but scientifically negative. The
branch had enough evidence to stop same-mechanism route absorption.

### Round 3: `fe3b564a`, first `route_limit_aware_repair`

Hypothesis: route-merge local search is post hoc and no-effect; instead act
during ALNS repair, where greedy/regret repair can open routes that the
scheduler later rejects under max-route guards. Add route-limit-aware repair
that prefers existing-route reinsertion and bounded pair-assisted moves.

Code change: modified `destroy_repair.py` and `scheduler.py`; changed greedy
and regret insertion signatures to accept context; added
`_route_limit_aware_repair`, `_route_limit_tight`,
`_tight_customer_rank`, `_best_pair_assisted_move`, and supporting insertion
cost helpers; integrated the operator into scheduler repair choices.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening was all ties: 0/0/8 case and 0/0/16 pair. Runtime was
`low_cached_champion` and required fresh champion before runtime-tie use.
Decision continued exploration but did not identify an objective effect.

Assessment: good cross-branch use of the round 1-2 failure: it shifted from
postrepair route absorption to repair-time route-limit pressure. Result was
still no-effect.

### Round 4: `fe3b564a`, `search_observability_bridge`

Hypothesis: recent route-limit and route-merge attempts are tie-heavy with
low-confidence runtime evidence; before adding more high-cost search, create a
mechanism-scoped telemetry bridge for ALNS/VNS attribution.

Code change: created `telemetry_bridge.py` and modified `scheduler.py`; added
`_record_bridge_iteration` plus phase/move/iteration telemetry around ALNS/VNS
calls. The code session needed two guard-driven code retries: first a
`_regret3_insertion()` signature mismatch in algorithm smoke, then another
preview/smoke correction before the accepted patch.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening expanded to 12 cases / 24 pairs; result was 0/0/12 case and
0/1/23 pair, with a single loss on `A-n39-k5` seed 11. Runtime confidence was
low/cached but runtime pairs were present. Decision continued exploration, but
finalizer parked the lineage: `post_finalizer_actual_branch_action` was
`parked_lineage_released`, active-slot counting became false, and next policy
was `clean_fork_or_other_branch_required`.

Assessment: as an observability-only branch this was architecturally legal and
mechanistically clear, but it still changed scheduler code and produced a pair
loss. The park decision was reasonable: keep evidence/checkpoint, release
active slot, avoid further same-lineage churn.

### Round 5: `052ead3f`, ejection-assist `route_limit_aware_repair`

Hypothesis: route-limit repair is still plausible, but needs a better
implementation: when max routes are reached, use bounded ejection-assist
instead of creating a new route or failing ordinary insertion.

Code change: modified `destroy_repair.py` and `scheduler.py`; added
`_route_limit_aware_repair(solution, removed, rng, max_routes, context,
reserve)` and `_ejection_assist`; wired it into the scheduler repair operator
list.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening produced 1/1/6 case W/L/T and 4/3/9 pair W/L/T. Pair wins appeared
on `B-n31-k5` seed 29 (+2), `E-n101-k8` both seeds (+7, +11), and
`P-n101-k4` seed 11 (+1); losses were `B-n52-k7` both seeds (-1, -1) and
`P-n101-k4` seed 29 (-17). Runtime aggregate was excluded due low/cached
champion. Decision reason codes included `SCREENING_FAIL_WIN_RATE`,
`SCREENING_MARGINAL_SIGNAL_CONTINUE`, and runtime saturation codes.

Assessment: this is the first real weak-positive research signal in the run:
case and pair movement appeared, and the implementation directly matched the
hypothesis. It was not validation-worthy because losses were material and CI
low was negative.

### Round 6: `052ead3f`, route-risk scheduler integration

Hypothesis: the round 5 repair variant produced mixed gains because it was just
another equally weighted repair. Integrate it with a route-risk trigger so the
scheduler boosts it only when post-destroy state has route-limit risk.

Code change: modified `scheduler.py`; added `_route_limit_repair_risk`; changed
repair selection to force/boost `route_limit_aware_repair` when route risk is
detected and avoid it when ordinary repair is sufficient.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening improved to 1/0/7 case W/L/T and 5/3/8 pair W/L/T. Wins included
`B-n31-k5` seed 29 (+3), `B-n52-k7` seed 29 (+2), `E-n101-k8` both seeds
(+14, +12), and `P-n101-k4` seed 11 (+1). Losses remained on `B-n31-k5`
seed 11 (-3), `E-n33-k4` seed 11 (-6), and `P-n101-k4` seed 29 (-17).
Decision continued same branch via `refine_active`.

Assessment: this is the strongest branch-local research behavior in the run.
The hypothesis explicitly responded to round 5 evidence, changed activation
policy rather than repair internals, and reduced case-level loss from 1 to 0.
Still, pair losses and negative CI low block validation.

### Round 7: `052ead3f`, scarcity-gated scheduler integration

Hypothesis: previous route-limit attempts showed E-n101 gains but regressions
when dense repair was forced too often. Add a fit-count/slack-margin scarcity
gate so route-limit repair is forced only when ordinary regret repair cannot
fit removed customers without exceeding route budget.

Code change: modified `scheduler.py`; refined `_route_limit_repair_risk` and
added telemetry for route-limit repair trigger/selection.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening regressed to 0/1/7 case W/L/T and 2/3/11 pair W/L/T. Wins appeared
on `B-n31-k5` seed 29 (+3) and `P-n101-k4` seed 11 (+9); losses were
`B-n52-k7` both seeds (-1, -6) and `E-n101-k8` seed 11 (-4). Decision
abandoned. Finalizer recorded `soft_abandon`, terminal-state release, and
`same_branch_not_selected`.

Assessment: the branch had a coherent third step, but the evidence falsified
the scarcity-gated refinement. Abandon was correct. This lineage shows real
research but also illustrates why a 20R run without stronger branch map/gates
could spend more budget overfitting small weak signals.

### Round 8: `15acd613`, `cost_plateau_reheating_acceptance`

Hypothesis: if route-limit/local-search changes are weak, perhaps the missing
lever is acceptance pressure. Modify `_SimulatedAnnealing` to reheat after
no-best-improvement plateaus, bounded by decay and max reheats.

Code change: modified `acceptance.py` and `scheduler.py`; added plateau state,
`cool(best_improved=False, context=None, reserve=0.0, delta=0.0)`, reheat
telemetry, and scheduler calls to report best-improvement status.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening was all ties: 0/0/8 case and 0/0/16 pair. Runtime was
fresh-champion-required and excluded from DecisionFeatures. Decision continued
exploration.

Assessment: mechanism is distinct from route-limit and local-search families,
but broad reheating produced no objective effect. Follow-up was allowed because
acceptance was still underexplored.

### Quality-block attempt after round 8: `15acd613`, `staged_search_budget`

Hypothesis attempt: change scheduler budget allocation into staged VNS/ALNS
windows and gate embedded VNS on promising candidates.

Outcome: this did not reach Protocol. The code session
`3ad4ffad` made one tool-selection stop and four code calls; three code retry
failures were recorded. Algorithm smoke repeatedly failed with
`_SimulatedAnnealing.cool() got an unexpected keyword argument 'best_improved'`
plus telemetry activation diagnostics. The quality block ledger records
`attempt_kind=proposal_block`, `failure_stage=agent_quality_blocked`,
`failure_category=algorithm_smoke_failure`, `pre_protocol=true`, and
`counts_toward_max_rounds=false`.

Assessment: this is a useful quality gate. It prevented a bad scheduler patch
from becoming a formal candidate. Scientifically, the hypothesis was a
reasonable budget-allocation follow-up, but the implementation failed basic
integration.

### Round 9: `ee4bfde3`, `diversified_acceptance_plateau_escape`

Hypothesis: avoid global reheating; add a bounded near-neutral plateau escape
mode that accepts only very small cost increases under quota/cooldown.

Code change: modified `acceptance.py` and `scheduler.py`; added
`begin_segment`, plateau trigger/band/cooldown/quota state, plateau-streak
tracking, and telemetry for `diversified_acceptance_plateau_escape`.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening produced 0/0/8 case W/L/T and 1/0/15 pair W/L/T, one win on
`B-n31-k5` seed 29 (+3). Runtime required fresh champion and remained
proposal guidance only. Decision continued exploration, with reason codes
including `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` and
`TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`.

Assessment: this is a better acceptance follow-up than round 8 because it
narrows the intervention. The signal is weak: one pair win, zero case wins.

### Round 10: `ee4bfde3`, `plateau_escape_vns_gating`

Hypothesis: the near-neutral escape signal may need immediate exploitation.
Modify scheduler activation/composition so accepted plateau-escape states get
a reserve-guarded VNS polish before they become current.

Code change: modified `scheduler.py`; added plateau escape quota/cooldown,
current-from-escape state, immediate VNS polish, and telemetry for
`plateau_escape_vns_gating`. The code session needed two smoke/preview retries:
first `_SimulatedAnnealing` lacked `begin_segment`; later retries corrected
runtime/telemetry advisory issues.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening repeated the same weak result as round 9: 0/0/8 case, 1/0/15 pair,
single `B-n31-k5` seed 29 win (+3). Scheduler selected
`exploit_weak_positive` / `fresh_champion_runtime_replay_followup`, but no
validation or promotion occurred.

Assessment: coherent same-branch follow-up, but it failed to convert pair-level
near-neutral drift into case-level improvement. Good research process, weak
algorithm evidence.

### Round 11: `f9b753e9`, `cross_route_2opt_reconnect`

Hypothesis: after route-limit, route-merge, scheduler, and acceptance variants
were weak, try a distinct VNS neighborhood: exchange bounded interior
subsequences between two routes, optionally reversing orientation, accepting
only strict distance-improving feasible reconnections.

Code change: modified `local_search.py`; added `_cross_route_2opt_reconnect`;
registered it in default VNS; emitted direct telemetry. This code session had
six tool-selection calls and then code without an explicit `STOP` trace, the
only code session with no stop marker.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening produced 0/0/8 case W/L/T and 3/3/10 pair W/L/T. Wins were
`B-n52-k7` seed 29 (+1), `E-n101-k8` seed 29 (+12), and `P-n101-k4`
seed 11 (+3). Losses were `B-n52-k7` seed 11 (-6), `E-n101-k8` seed 11 (-2),
and `P-n101-k4` seed 29 (-18). Decision abandoned with
`SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`.

Assessment: differentiated enough from previous route absorption because it
exchanges interior segments, but still belongs to the route-edit/VNS family.
Balanced pair movement and non-positive CI justify abandon.

### Round 12: `2e6e8e5d`, `route_limit_seed_diversification`

Hypothesis: rather than changing repair, acceptance, or local-search, diversify
initial route-limit-compliant construction seeds by rotating sweep starts and
using distance-aware best-fit packing tie-breaks, then choose the best feasible
seed before ALNS/VNS.

Code change: modified `construction.py` and `scheduler.py`; added
`_route_limit_seed_diversification`, `_diversified_bins`,
`_sequential_capacity_bins`, `_best_fit_customer_order`, `_best_fit_bins`, and
`_ordered_routes`; integrated construction telemetry.

Gate/protocol/finalizer behavior: Contract/Verification/Canary passed.
Screening was all ties: 0/0/8 case and 0/0/16 pair. Runtime was
fresh-champion-required and excluded from DecisionFeatures. Decision continued
exploration only because budget ended at 12R.

Assessment: this is the most clearly differentiated surface in the final
round: construction/initial geometry rather than VNS, repair, scheduler, or
acceptance. The result was no-effect. It is a useful negative data point for
the cross-branch map.

## LLM call analysis

Every screened candidate used one hypothesis session
(`hypothesis_target_intent` then `hypothesis`) and one code session
(`tool_selection` loop then `code`). The failed `staged_search_budget` attempt
also used one hypothesis session and one code session, so the total is 13
hypothesis sessions and 13 code sessions.

Global observations:

- All 92 trace files are `gpt-5.5` and `ok=true`.
- All 46 tool-selection traces have prompt manifest refs and visibility
  ledgers.
- All 13 code sessions have non-empty `deterministic_prefetch_plan_id`.
- 12/13 code sessions have `default_triad_satisfied=true`; the first code
  session has a complete ledger but `default_triad_satisfied=false`.
- Schema retry count is 0 for every session.
- Code retry overhead is concentrated in three sessions:
  `c559234f` round 4 telemetry bridge: 2 retries;
  `3ad4ffad` quality-blocked staged budget: 3 retries and final failure;
  `1f7b1641` round 10 plateau VNS gating: 2 retries.
- Normal stop calls appear in 12 code sessions. Round 11 code session
  `4fcdfc1b` moved from six tool-selection calls directly to code without a
  `STOP` trace. This is minor trace/planner overhead, not a run-validity issue.
- Tool-selection response counts: `context.read_algorithm_file=17`,
  `STOP=12`, `context.read_branch_state=11`, `context.read_surface=5`,
  `feedback.query_screening=1`.

Compact per-round/session ledger:

| R | Session | Branch | Calls | Purpose/result |
|---:|---|---|---|---|
| 1H | `3a8e4a4e` | `860de988` | `hypothesis_target_intent`, `hypothesis` | Selected `route_merge_local_search`; cross-branch map small because this was the first branch. |
| 1C | `5b2d5e83` | `860de988` | tsel: branch state, surface, algorithm file, screening feedback, algorithm files, `STOP`; `code` | Read VNS context and generated accepted route-merge patch. |
| 2H | `e8fdd9b8` | `860de988` | target intent, hypothesis | Same-branch refinement: slack-gated route merge after no-effect runtime pressure. |
| 2C | `3ff23d83` | `860de988` | tsel: branch state, `STOP`; `code` | Minimal inspection used branch-local feedback; accepted patch. |
| 3H | `c57ca822` | `fe3b564a` | target intent, hypothesis | Clean-fork route-limit repair; used route-merge failure as sibling lesson. |
| 3C | `1babc464` | `fe3b564a` | tsel: algorithm file, branch state, `STOP`; `code` | Implemented repair-time route-limit mechanism. |
| 4H | `2f23cba0` | `fe3b564a` | target intent, hypothesis | Observability bridge after no-effect route-limit/route-merge attempts. |
| 4C | `c559234f` | `fe3b564a` | tsel: algorithm file, branch state, `STOP`; `code` x3 | Two smoke/preview retries, then accepted telemetry bridge. |
| 5H | `4f4befa7` | `052ead3f` | target intent, hypothesis | Clean fork required material difference; chose route-limit ejection-assist repair. |
| 5C | `73066b09` | `052ead3f` | tsel: two algorithm files, branch state, `STOP`; `code` | Implemented route-limit repair with ejection-assist. |
| 6H | `a0ac85cf` | `052ead3f` | target intent, hypothesis | Same-branch follow-up based on mixed E/B/P signals; moved to activation policy. |
| 6C | `b99469a6` | `052ead3f` | tsel: `STOP`; `code` | Branch/workspace context was sufficient; scheduler patch accepted. |
| 7H | `696189b9` | `052ead3f` | target intent, hypothesis | Further same-branch refinement using losses from round 6; proposed scarcity gate. |
| 7C | `bfb89d1b` | `052ead3f` | tsel: branch state, `STOP`; `code` | Implemented trigger refinement; later abandoned by screening. |
| 8H | `621244cf` | `15acd613` | target intent, hypothesis | Clean fork from route-limit/local-search failures to acceptance reheating. |
| 8C | `38272d82` | `15acd613` | tsel: branch state, surface, three algorithm files, `STOP`; `code` | Generated accepted acceptance/scheduler patch. |
| QB-H | `fabe0002` | `15acd613` | target intent, hypothesis | Proposed `staged_search_budget` scheduler follow-up after no-effect acceptance. |
| QB-C | `3ad4ffad` | `15acd613` | tsel: branch state, `STOP`; `code` x4 | Three smoke failures; quality-blocked before Protocol. |
| 9H | `e666cd9b` | `ee4bfde3` | target intent, hypothesis | Clean fork to narrower acceptance plateau escape after reheating no-effect. |
| 9C | `c9466ccb` | `ee4bfde3` | tsel: branch state, surface, two algorithm files, `STOP`; `code` | Implemented bounded near-neutral escape. |
| 10H | `0f47668a` | `ee4bfde3` | target intent, hypothesis | Same-branch weak-positive follow-up; convert escape into VNS polish. |
| 10C | `1f7b1641` | `ee4bfde3` | tsel: `STOP`; `code` x3 | Two smoke/telemetry retries, then accepted scheduler gating patch. |
| 11H | `f431831f` | `f9b753e9` | target intent, hypothesis | Clean fork to cross-route interior 2-opt after repeated no-effect/weak acceptance. |
| 11C | `4fcdfc1b` | `f9b753e9` | tsel: branch state, surface, four algorithm files; `code` | No explicit STOP; accepted cross-route reconnect patch. |
| 12H | `9c768fc0` | `2e6e8e5d` | target intent, hypothesis | Clean fork to construction seed diversification after scheduler/local-search/acceptance no-effect. |
| 12C | `3ce54541` | `2e6e8e5d` | tsel: branch state, surface, algorithm file, `STOP`; `code` | Implemented route-limit seed diversification. |

## Branch lineage analysis

### `860de988`: route merge local search

Path: round 1 route absorption VNS -> round 2 slack/savings-gated absorption.

This branch is a coherent two-step local-search lineage. The follow-up uses
round 1 evidence correctly: the operator activated but had no wins and added
runtime pressure, so round 2 adds a feasibility/savings gate. The code
implements the stated mechanism in both rounds. After two all-tie screenings,
the finalizer releases the active slot due repeated no-effect. This is a
proper rollback/abandon-equivalent outcome even though the branch state remains
`explore` with code discarded.

### `fe3b564a`: route-limit repair to observability bridge

Path: round 3 repair-time route-limit pressure -> round 4 telemetry bridge.

The first hypothesis is a good cross-branch pivot from route-merge failure:
change the construction/repair point where route-limit violations arise,
instead of trying to absorb routes later. The second step is less obviously an
algorithm-improvement hypothesis: it adds observability rather than improving
solutions. That can be justified by low-confidence runtime evidence, but the
screening loss and parked lineage show it did not advance solver quality.
Checkpoint retention and park were reasonable because it prevented more
active-slot consumption while preserving evidence.

### `052ead3f`: route-limit-aware repair deep branch

Path: round 5 ejection-assist repair -> round 6 route-risk scheduler trigger
-> round 7 scarcity gate.

This is the best branch in the run. It shows continuous research:

- round 5 implements the mechanism and creates real but mixed pair/case signal;
- round 6 uses that evidence and changes activation policy to preserve gains
  while reducing overuse;
- round 7 responds to remaining regressions with a stricter scarcity gate.

The branch did not succeed, but the abandon after round 7 is scientifically
sound: the third refinement reversed the case-level signal and pair losses
persisted. This is effective algorithm research process with weak results.

### `15acd613`: acceptance reheating and failed scheduler-budget follow-up

Path: round 8 bounded reheating -> quality-blocked staged search budget.

The clean fork away from route-limit/local-search variants is reasonable. The
acceptance reheating mechanism is distinct and implemented. Its all-tie result
does not support continued broad reheating. The follow-up hypothesis to change
phase budget allocation is plausible, but the code failed integration
repeatedly. The quality block was the correct outcome and prevented a bad
candidate from polluting screening.

### `ee4bfde3`: bounded plateau escape to VNS gating

Path: round 9 near-neutral plateau escape -> round 10 immediate VNS polish.

This branch uses both sibling and branch-local lessons well. It explicitly
distinguishes itself from broad reheating and from route-limit/route-merge
families, then uses the single pair win in round 9 to test whether downstream
VNS exploitation can convert near-neutral drift into objective improvement.
The follow-up is coherent, but the result stays at one pair win and zero case
wins. It is a weak-positive branch, not a validation candidate.

### `f9b753e9`: cross-route 2-opt reconnect

Path: single clean-fork VNS neighborhood.

The mechanism is distinct from route absorption because it exchanges bounded
interior subsequences, but it is still in the route-edit/VNS family. It
produced balanced movement and was abandoned correctly. As cross-branch
research, it shows the map can propose a new operator type, but also shows
continued gravitational pull toward local-search route compaction.

### `2e6e8e5d`: route-limit seed diversification

Path: single construction-surface clean fork.

This is the most differentiated late-stage branch. It changes initial
construction geometry rather than repair, acceptance, scheduler, or local
search. It produced no effect, but it is valuable as a negative signal because
it expands the explored mechanism family.

## Cross-branch information transfer and boundaries

Evidence that cross-branch information was visible:

- `campaign_summary.json` records
  `cross_branch_research_observability.policy=proposal_observability_only`.
- The same record sets
  `decision_input_policy=excluded_from_decision_features`.
- `observable_step_count=12`, `cross_branch_map_seen_count=12`,
  `near_duplicate_count=1`, `material_difference_requirement_count=1`,
  `novelty_pressure_seen_count=4`, and `same_branch_refinement_allowance_count=5`.
- Every hypothesis prompt manifest contains `cross_branch_research_map`; later
  manifests also contain larger `sibling_branches` sections. For example,
  round 3 hypothesis manifests had about 9.5k chars of cross-branch map and
  2.3k chars of sibling summary; rounds 10-13 had 25k-32k chars of
  cross-branch map and 4.3k-6.5k chars of sibling summary.
- Runtime evidence policies repeatedly mark runtime signals as
  `proposal_guidance_only=true` and `decision_features_excluded=true`.

Evidence that the agent used sibling lessons:

- Round 3 explicitly distinguishes repair-time route-limit pressure from the
  prior route-merge no-effect branch.
- Round 4 uses sibling route-limit/route-merge no-effect and low-confidence
  runtime evidence to propose an observability bridge.
- Round 8 moves from route-limit/local-search families to acceptance because
  ALNS/VNS neighborhoods already exist but screening remains tie-heavy.
- Round 9 narrows acceptance after broad reheating no-effect.
- Round 11 states that route-limit, route-merge, scheduler, and acceptance
  variants were weak before trying cross-route reconnection.
- Round 12 states that scheduler/local-search/acceptance variants either
  saturated runtime or had no effect before trying construction seed
  diversification.

Limitations:

- The cross-branch map appears more advisory than corrective. It does not
  strongly suppress near repeats: route-limit-aware repair appears across two
  branches and three refinements; local-search/VNS route compaction returns in
  rounds 1-2 and 11.
- The run still spends many rounds near route compaction, route-limit repair,
  and VNS/local-search families. The construction branch appears only at the
  end.
- `status.json` and `campaign_summary.json` expose slightly different
  cross-branch observability summaries: `campaign_summary.json` has the more
  complete step-history scope and near-duplicate/material-difference counters,
  while `status.json` shows a more limited branch-row/scheduler snapshot. This
  does not change the research conclusion, but future reports should prefer
  `campaign_summary.json` for final cross-branch accounting.

Boundary judgment: I found no evidence that sibling-branch text entered
DecisionFeatures. The information is visible to proposal, tainted, and
excluded from decision inputs, consistent with Architecture v3.

## Branch differentiation

Mechanism families explored:

- VNS/local-search route absorption: rounds 1-2.
- ALNS repair / route-limit pressure: rounds 3, 5-7.
- Observability/telemetry bridge: round 4.
- Acceptance schedule / plateau escape: rounds 8-10.
- Scheduler budget/composition: quality-blocked staged budget and round 10
  VNS gating.
- Cross-route interior reconnection: round 11.
- Construction seed diversification: round 12.

Differentiation is adequate for a 12R exploratory run but not strong enough
for a 20R research-quality gate. The most repetitive cluster is route
compaction under different names:

- all-or-nothing route absorption;
- route-limit repair that densifies existing routes;
- cross-route interior reconnect;
- route-limit seed packing.

These are not identical mechanisms, but they share a route-density/compaction
failure signature. The run only late-shifts into construction and never tests
parameter-weight optimization, instance-subgroup-adaptive operator choice, or a
clear acceptance/repair interaction with a stronger prior.

## Algorithm signal

Positive or weak-positive evidence:

- Round 5: 1/1/6 case W/L/T and 4/3/9 pair W/L/T; real movement but mixed.
- Round 6: 1/0/7 case W/L/T and 5/3/8 pair W/L/T; best signal in the run,
  but still median 0.0 and CI low -3.0.
- Round 9 and round 10: each had one pair-level win and zero losses, but zero
  case wins and CI [0.0, 0.0].
- Round 11: 3/3/10 pair movement, but balanced and CI low -2.5.

Negative/no-effect evidence:

- Rounds 1, 2, 3, 8, and 12 were all ties.
- Round 4 introduced a pair-level loss.
- Round 7 regressed the best branch to a case-level loss.
- No screening candidate reached the `win_rate >= 2/3` gate.
- No validation or frozen stage occurred.
- No champion promotion occurred.

Conclusion: the 12R run proves framework stability and demonstrates credible
research behavior. It does not prove effective VRP improvement. The right
claim is: Scion can run a 12-round branch-governed CVRP research loop with
complete evidence, but the tested mechanisms have weak and unstable solver
quality signal.

## 20R recommendation and next steps

Do not use this result to proceed directly to 20R as an algorithm-quality
claim. Proceeding to 20R is acceptable only as framework stress testing.

Before a research-quality 20R gate, improve:

1. Cross-branch research map: convert sibling lessons into stronger mechanism
   family pressure, not only descriptive summaries. Explicitly mark
   route-compaction/route-limit/local-search variants as saturated after
   repeated no-effect or mixed-signal outcomes.
2. Branch lesson propagation: require same-branch follow-ups to name the
   exact evidence they are preserving and the exact regression they are
   avoiding. Round 5-7 is the model to preserve.
3. Scheduler/quality gate: keep quality blocking as-is, but add stronger
   "do not spend another formal round" pressure for all-tie plus runtime
   saturation patterns, especially after two same-mechanism attempts.
4. Candidate selection: allocate earlier budget to truly different surfaces
   such as construction, parameter policy, subgroup-aware operator selection,
   and acceptance/repair interaction rather than repeated route-density moves.
5. Reporting: keep separating framework validity from algorithm signal. A
   valid 20R run without validation/promotion would still be a framework
   result, not a VRP improvement result.

Decision: first repair/strengthen the research-map and lesson-propagation
mechanisms, then run 20R. If 20R is launched immediately, label it
"framework stress / branch governance verification", not "algorithm
improvement validation".
