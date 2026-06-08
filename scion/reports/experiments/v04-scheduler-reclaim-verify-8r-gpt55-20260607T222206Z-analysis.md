# Scheduler Reclaim Fix 8R CVRP Experiment Analysis

Experiment:
`/home/clawd/research/scion-experiments/v04-scheduler-reclaim-verify-8r-gpt55-20260607T222206Z-8r-gpt55-20260607T222206Z-claw/campaign`

Report date: 2026-06-07

Required references read:

- `scion/design/scion-architecture-v3.md`
- `scion/reports/architecture-audit-v0.4/remediation-status.md`
- `scion/reports/experiments/v04-audit-provenance-replay-verify-8r-gpt55-20260607T210441Z-analysis.md`
- `scion/reports/experiments/v04-audit-provenance-replay-verify-8r-gpt55-20260607T210441Z-scheduler-blocker.md`

## Executive Conclusion

This run is a valid completed 8R CVRP campaign after the scheduler reclaim fix:
`run_validity_status=valid`, `run_complete=true`,
`completed_requested_rounds=true`, `effective_rounds_completed=8`,
`formal_screened_candidates=8`, `protocol_evaluated_candidates=8`,
`quality_blocks=0`, and `scheduler_active_slot_blocked_attempts=0`.
It improves the previous partial 8R run at the framework stability level: the
earlier run stopped after 5/8 candidates with three repeated
`scheduler_active_slot_blocked` skips; this run reached all eight requested
formal screening candidates and stopped normally with `max_rounds_exhausted`.

Important limitation: this successful 8R run did not actually emit a
`scheduler_active_slot_reclaim` or `new_branch_reclaim` audit event. The run
does validate that the repaired scheduler no longer blocks this 8R workload
under the same active-branch pressure profile, but it does not directly execute
the exact scheduler-origin reclaim marker path. That exact reclaim path remains
covered primarily by the focused scheduler reclaim unit tests described in the
remediation notes.

Research-quality verdict: the agent is doing real algorithm research, but the
algorithmic signal remains weak. The hypotheses target concrete mechanisms
inside ALNS repair, VNS route editing, route merge, scheduler operator
selection, and acceptance/VNS scheduling; code changes implement those
mechanisms and telemetry confirms activation. However, no candidate reached
validation, most candidates tied at case level, and the two candidates with
stronger pair movement also showed balancing losses or negative median effect.
This is enough to continue framework-scale testing, not enough to claim solver
quality improvement.

Architecture verdict: the run is consistent with Scion v3 boundaries. LLM
outputs remained proposal/patch artifacts; Contract, Verification, Canary, and
Protocol produced structured evidence; Decision read structured features and
reason codes. Cross-branch observability is explicitly
`proposal_observability_only` and `excluded_from_decision_features`. I found no
evidence that CVRP-specific semantics leaked into generic Scion core artifacts;
CVRP content stayed in problem/solver surfaces, metrics, traces, and candidate
workspace code.

Recommendation: proceed to a 12R run if the purpose is framework stability and
agent-loop validation, while explicitly tracking two caveats: exact
scheduler-origin reclaim event coverage still comes from unit tests, and
research signal remains weak. I do not see a framework defect that blocks 12R.
I would not promote or freeze any algorithm candidate from this run.

## Evidence Scope

Read-only evidence inspected:

| Evidence | Count / file |
|---|---:|
| Status/summary files | `status.json`, `campaign_summary.json`, `run_status.json` |
| SQLite tables | `branches` 5 rows, `hypotheses` 8 rows, `experiment_events` 40 rows |
| Formal candidates | 8 entries in `artifacts/formal_candidates/index.jsonl` |
| Candidate patch artifacts | 8 `candidate.patch.json`, 8 `candidate.diff` |
| Candidate metrics | 8 screening metrics referenced by DB events |
| LLM traces | 59 files, all `gpt-5.5` |
| Agentic sessions | 16 sessions: 8 hypothesis sessions, 8 code sessions |

Replay/provenance completeness:

- 8/8 formal candidate patch artifacts have `replay_identity.status=complete`.
- 8/8 include `problem_spec_hash`, `split_manifest_hash`,
  `seed_ledger_hash`, `patch_digest`, `patch_hash`, `selected_surface`,
  `protocol_version`, and `raw_metrics_ref`.
- Tool-selection prompt manifests/provenance are present in trace/session
  indexes. Code sessions carry `deterministic_prefetch_plan_id` and
  prefetch tool names.

## Run-Level Accounting

| Field | Value |
|---|---:|
| `run_validity_status` | `valid` |
| `run_complete` | `true` |
| `completed_requested_rounds` | `true` |
| `stopped_reason` / `last_stop_reason` | `max_rounds_exhausted` |
| `requested_rounds` | 8 |
| `effective_rounds_completed` | 8 |
| `formal_screened_candidates` | 8 |
| `protocol_evaluated_candidates` | 8 |
| `protocol_stage_counts.screening` | 8 |
| `protocol_stage_counts.validation` | 0 |
| `protocol_stage_counts.frozen` | 0 |
| `quality_blocks` | 0 |
| `scheduler_active_slot_blocked_attempts` | 0 |
| `lineage_integrity.status` | `complete` |
| `evidence_integrity.status` | `complete` |
| `formal_readiness.status` | `non_formal_final_evidence_closed` |

The final evidence closure is non-formal because the campaign ended normally
without a formal final evidence package. That is not a run-validity failure for
this 8R screening verification.

LLM trace accounting:

| Request kind | Calls | Input tokens | Output tokens | Reasoning tokens | Model |
|---|---:|---:|---:|---:|---|
| `hypothesis_target_intent` | 8 | 232,064 | 1,442 | 0 | `gpt-5.5` |
| `hypothesis` | 8 | 309,974 | 7,332 | 0 | `gpt-5.5` |
| `tool_selection` | 33 | 429,997 | 1,410 | 0 | `gpt-5.5` |
| `code` | 10 | 288,038 | 26,574 | 6,664 | `gpt-5.5` |
| total | 59 | 1,260,073 | 36,758 | 6,664 | `gpt-5.5` |

All 59 traces completed with `ok=true`. There were 8 normal tool-selection
`stop` responses, one at the end of each code-session inspection loop. The
only code retry overhead occurred in round 8: two failed code attempts before
the final accepted patch. The failures were useful guard feedback, not schema
parse failures: first `code_stage_telemetry_identity_mismatch` for introducing
`alns` telemetry outside the approved mechanism id, then a contract preview
failure involving forbidden telemetry claims and an import mismatch for
`_RankBufferAcceptance`.

## Candidate Summary

| Round | Branch | Candidate | Mechanism | Target surface/files | Case W/L/T | Pair W/L/T | Median delta | CI | Decision |
|---:|---|---|---|---|---:|---:|---:|---|---|
| 1 | `2d1ac121` | `973a8c997dadc917` | `demand_slack_regret_repair` | `destroy_repair.py`, `scheduler.py` | 0/1/7 | 1/3/12 | 0.0 | [-3.0, 0.0] | `abandon` |
| 2 | `a31b7096` | `f0e9762d3d3c2071` | `cross_route_2opt_reconnect` | `local_search.py` | 0/1/7 | 1/2/13 | 0.0 | [0.0, 0.0] | `abandon` |
| 3 | `ca2204f8` | `aa037c1cc4e54cab` | `savings_route_merge_postrepair` | `route_merge.py`, `scheduler.py` | 0/0/12 | 1/0/23 | 0.0 | [0.0, 0.0] | `continue_explore` |
| 4 | `ca2204f8` | `9cc66f1344d04eb7` | `savings_route_merge_postrepair` refinement | `route_merge.py` | 0/0/8 | 0/0/16 | 0.0 | [0.0, 0.0] | `continue_explore` |
| 5 | `3a83f295` | `15a2c3adc2a67b0b` | `telemetry_guided_operator_phase_bridge` | `scheduler.py` | 0/0/8 | 0/0/16 | 0.0 | [0.0, 0.0] | `continue_explore` |
| 6 | `3a83f295` | `1ce968394619b280` | `slack_weighted_regret_repair` | `destroy_repair.py`, `scheduler.py` | 0/0/8 | 3/3/10 | 0.0 | [-2.0, 0.75] | `continue_explore` + park lineage |
| 7 | `3239c6f5` | `5b8102b6e595f08a` | `rank_buffer_acceptance` | `acceptance.py`, `scheduler.py` | 0/0/8 | 1/1/14 | 0.0 | [0.0, 0.0] | `continue_explore` |
| 8 | `3239c6f5` | `2e4ee5aa9b6e55f3` | `rank_buffer_schedule_bridge` | `scheduler.py` | 2/1/5 | 5/5/6 | -0.25 | [-2.0, 2.5] | `abandon` |

All 8 candidates passed Contract, Verification, and Canary. All screening
metrics had complete evidence and zero failed candidate/champion pairs.

## Candidate Analysis By Round

### Round 1: `2d1ac121`, `demand_slack_regret_repair`

Hypothesis: ALNS repair currently optimizes insertion cost/regret after destroy
and can consume scarce capacity slack too cheaply, later forcing poor geometry
or new routes. Add a repair variant that preserves slack while still protecting
fleet feasibility.

Code change:

- Added `_demand_slack_regret_repair` in `destroy_repair.py`.
- Added `_slack_adjusted_insertions` to penalize tight post-insertion residual
  capacity while preserving the underlying insertion-cost ranking.
- Wired the repair operator through `scheduler.py` and recorded
  `demand_slack_regret_repair` iteration, phase runtime, and move telemetry.

Gate/protocol/finalizer behavior:

- Contract, Verification, Canary: passed.
- Screening: 8 cases, 16 valid pairs.
- Result: 0/1/7 case W/L/T, 1/3/12 pair W/L/T, median 0.0, CI [-3.0, 0.0].
- Non-tie pairs: one `B-n31-k5` win (+3.0), two `B-n52-k7` losses (-2.0,
  -4.0), one `E-n101-k8` loss (-7.0).
- Runtime evidence was high/sufficient and not aggregate-excluded, but runtime
  was supporting/tie-break evidence only and excluded from decision features.
- Decision: `abandon`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`,
  `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`,
  `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`,
  `SCREENING_RUNTIME_BUDGET_SATURATION`,
  `BOTH_RUNTIME_BUDGET_SATURATION`.

Assessment: mechanism and implementation match. The negative result is real:
capacity-aware repair produced pair movement, but losses dominated and the CI
was non-positive. Abandon was correct.

### Round 2: `a31b7096`, `cross_route_2opt_reconnect`

Hypothesis: previous destroy/repair changes remained winless, while
fleet-violation stayed stable. Add a bounded cross-route 2-opt reconnection
neighborhood that covers segment reconnections beyond the existing suffix-only
move and accepts only strict cost improvements.

Code change:

- Added `_cross_route_2opt_reconnect` in `local_search.py`.
- Enumerated bounded route pairs and segment cuts under capacity and reserve
  guards.
- Accepted the first strict total-distance improvement and recorded
  `cross_route_2opt_reconnect` telemetry.

Gate/protocol/finalizer behavior:

- Contract, Verification, Canary: passed.
- Screening: 8 cases, 16 valid pairs.
- Result: 0/1/7 case W/L/T, 1/2/13 pair W/L/T, median 0.0, CI [0.0, 0.0].
- Non-tie pairs: `B-n31-k5` win (+3.0), `B-n52-k7` losses (-1.0, -4.0).
- Runtime aggregate excluded due `low_cached_champion`; runtime was
  audit/proposal-guidance only.
- Decision: `abandon`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`,
  `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`,
  `SCREENING_RUNTIME_BUDGET_SATURATION`,
  `CANDIDATE_RUNTIME_BUDGET_SATURATION`.

Assessment: this was a materially different mechanism from round 1 and was
reasonable after repair-regret failure. It generated narrow pair-level movement
but still produced a case-level loss and no validation-worthy signal.

### Round 3: `ca2204f8`, first `savings_route_merge_postrepair`

Hypothesis: recent attempts targeted repair scoring and cross-route local
search but remained tie-heavy. Add a bounded whole-route merge phase after
construction/repair/VNS cleanup to pursue total-distance improvement without a
new broad VNS neighborhood.

Code change:

- Created `route_merge.py` with `_savings_route_merge_postrepair`.
- Ranked capacity-feasible route pairs by endpoint merge savings with
  reversal variants.
- Applied strict improving whole-route merges and wired the phase into
  `scheduler.py`.
- Recorded `savings_route_merge_postrepair` activation, phase runtime, and move
  telemetry.

Gate/protocol/finalizer behavior:

- Contract, Verification, Canary: passed.
- Screening: 12 cases, 24 valid pairs.
- Result: 0/0/12 case W/L/T, 1/0/23 pair W/L/T, median 0.0, CI [0.0, 0.0].
- Non-tie pair: `A-n39-k5` seed 11 win (+2.0).
- Runtime confidence was `low_cached_champion`, but aggregate runtime was not
  excluded because runtime pairs were present; runtime remained
  audit/proposal guidance only.
- Decision: `continue_explore`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`,
  `SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL`,
  `SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`,
  `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE`,
  `SCREENING_RUNTIME_BUDGET_SATURATION`,
  `CANDIDATE_RUNTIME_BUDGET_SATURATION`.

Assessment: this is a legitimate clean-fork experiment. The mechanism is
clear, distinct, and implemented. Evidence was weak but not harmful: one
pair-level win and no case-level losses justified a same-branch refinement.

### Round 4: `ca2204f8`, refined `savings_route_merge_postrepair`

Hypothesis: the first route-merge variant showed one pair-level `A-n39-k5`
distance gain but no case wins, likely because it accepted only immediately
negative endpoint concatenations. Add bounded intra-merge cleanup so a feasible
merge can become beneficial after small internal reordering.

Code change:

- Modified `route_merge.py` candidate ranking to run `_clean_merged_route`.
- Added a bounded two-pass, first-improvement 2-opt cleanup for merged route
  candidates.
- Reduced candidate cap and retained strict capacity/improvement checks.

Gate/protocol/finalizer behavior:

- Contract, Verification, Canary: passed.
- Screening: 8 cases, 16 valid pairs.
- Result: 0/0/8 case W/L/T, 0/0/16 pair W/L/T, median 0.0, CI [0.0, 0.0].
- Runtime aggregate excluded due `low_cached_champion`; fresh champion was
  required for the runtime tie signal but not scheduled as formal rerun.
- Decision: `continue_explore`.
- Reason codes: `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`,
  `SCREENING_RUNTIME_BUDGET_SATURATION`,
  `CANDIDATE_RUNTIME_BUDGET_SATURATION`.

Assessment: this follow-up used branch-local feedback correctly, but the
mechanism lost even the prior single pair-level gain. The finalizer retained
evidence but discarded the current head. This branch ends as no-effect,
diagnostic-repair status rather than a promotion candidate.

### Round 5: `3a83f295`, `telemetry_guided_operator_phase_bridge`

Hypothesis: repeated route-edit and repair changes activated but rarely moved
objective results. Modify scheduler operator-pair selection to attribute
destroy/repair pair outcomes and suppress repeatedly unproductive pairings
after warm-up.

Code change:

- Added local pair statistics inside `scheduler.py`.
- Added `_choose_operator_pair` to keep normal exploration early, then bias away
  from pairings with repeated no-accept/no-delta observations.
- Added `_record_pair_outcome`.
- Recorded `telemetry_guided_operator_phase_bridge` telemetry and maintained
  existing feasibility and route-limit guards.

Gate/protocol/finalizer behavior:

- Contract, Verification, Canary: passed.
- Screening: 8 cases, 16 valid pairs.
- Result: 0/0/8 case W/L/T, 0/0/16 pair W/L/T, median 0.0, CI [0.0, 0.0].
- Runtime aggregate excluded due `low_cached_champion`; fresh champion required
  for runtime tie.
- Decision: `continue_explore`.
- Reason codes: `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`,
  `SCREENING_RUNTIME_BUDGET_SATURATION`,
  `CANDIDATE_RUNTIME_BUDGET_SATURATION`.

Assessment: this is mechanism-real but mostly diagnostic. It changes selection
pressure, not the candidate construction objective, and the zero objective
effect supports a follow-up that changes actual repair behavior rather than
only operator selection.

### Round 6: `3a83f295`, `slack_weighted_regret_repair`

Hypothesis: the previous scheduler-only operator-pair bridge activated without
objective movement. Change actual post-destroy reconstruction by adding a
slack-weighted regret repair variant instead of only changing selection.

Code change:

- Added `_slack_weighted_regret_repair` in `destroy_repair.py`.
- The score combines regret, new-route gap, and slack-fit pressure.
- Kept the previous telemetry-guided scheduler bridge in the branch workspace
  and integrated the repair operator.

Gate/protocol/finalizer behavior:

- Contract, Verification, Canary: passed.
- Screening: 8 cases, 16 valid pairs.
- Result: 0/0/8 case W/L/T, 3/3/10 pair W/L/T, median 0.0, CI [-2.0, 0.75].
- Non-tie pairs: wins on `B-n31-k5` (+3.0), `E-n101-k8` seed 11 (+15.0),
  `P-n101-k4` seed 11 (+1.0); losses on `B-n52-k7` (-4.0),
  `E-n101-k8` seed 29 (-7.0), `P-n101-k4` seed 29 (-16.0).
- Runtime aggregate excluded due `low_cached_champion`.
- Decision: `continue_explore`, but finalizer/lifecycle parked the lineage.
- Reason codes: `SCREENING_FAIL_WIN_RATE`,
  `BRANCH_LIFECYCLE_PARK_LINEAGE`,
  `SCREENING_RUNTIME_SATURATION_REROUTE`,
  `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_EXHAUSTED`,
  `SCREENING_RUNTIME_BUDGET_SATURATION`,
  `CANDIDATE_RUNTIME_BUDGET_SATURATION`.
- Scheduler result after finalizer: `post_finalizer_actual_branch_action` was
  `parked_lineage_released`, `counts_toward_active_slots=false`,
  `post_finalizer_next_proposal_policy=clean_fork_or_other_branch_required`.

Assessment: this is the cleanest example of branch-local learning in the run:
the agent recognized that a selection-only diagnostic did not change objective
behavior and moved to a reconstruction mechanism. The evidence was still mixed
and not validation-worthy. The lifecycle park was important for scheduler
stability: it released the active slot and allowed later clean fork without
capacity deadlock.

### Round 7: `3239c6f5`, `rank_buffer_acceptance`

Hypothesis: ALNS often produced little direct best delta while VNS generated
most improvement. Current simulated annealing may accept weak lateral states or
cool without preserving near-elite diversity. Add rank-buffer acceptance so
non-improving ALNS candidates must be near a rolling feasible-cost band.

Code change:

- Added `_RankBufferAcceptance` in `acceptance.py`.
- Maintains a small rolling cost buffer, warm-up threshold, quantile, and slack
  ratio.
- Wired scheduler acceptance through the rank-buffer criterion and recorded
  `rank_buffer_acceptance` telemetry.

Gate/protocol/finalizer behavior:

- Contract, Verification, Canary: passed.
- Screening: 8 cases, 16 valid pairs.
- Result: 0/0/8 case W/L/T, 1/1/14 pair W/L/T, median 0.0, CI [0.0, 0.0].
- Non-tie pairs: `B-n31-k5` win (+3.0), `B-n52-k7` loss (-2.0).
- Runtime aggregate excluded due `low_cached_champion`; fresh champion required
  for runtime tie.
- Decision: `continue_explore`.
- Reason codes: `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`,
  `SCREENING_RUNTIME_BUDGET_SATURATION`,
  `CANDIDATE_RUNTIME_BUDGET_SATURATION`.

Assessment: the hypothesis is plausible and mechanistic. The implementation is
real and telemetry-active, but the result is effectively neutral with one
balanced win/loss. A same-branch follow-up was reasonable only as a diagnostic
refinement, not as a quality improvement.

### Round 8: `3239c6f5`, `rank_buffer_schedule_bridge`

Hypothesis: rank-buffer acceptance showed weak pair signal but no stable case
effect. Modify scheduler timing so accepted near-elite non-improving states
trigger embedded VNS more selectively, aiming to turn rank-buffer diversity
into objective improvement.

Code change:

- Modified `scheduler.py` to inline rank-buffer cost tracking and add
  `_rank_buffer_schedule_bridge`.
- The bridge decides whether accepted candidates should trigger embedded VNS
  based on rank band, improvement status, segment checkpoint, customer count,
  and remaining reserve.
- Recorded `rank_buffer_schedule_bridge` telemetry and retained
  `rank_buffer_acceptance` phase telemetry.

Gate/protocol/finalizer behavior:

- Contract, Verification, Canary: passed.
- Screening: 8 cases, 16 valid pairs.
- Result: 2/1/5 case W/L/T, 5/5/6 pair W/L/T, median -0.25, CI [-2.0, 2.5].
- Non-tie pairs: major losses on `A-n32-k5` both seeds (-43.0, -43.0);
  wins on `E-n101-k8` both seeds (+18.0, +12.0), `P-n101-k4` both seeds
  (+4.0, +1.0), and `B-n31-k5` seed 29 (+3.0); losses on `B-n31-k5` seed 11
  (-4.0), `B-n52-k7` seed 29 (-2.0), and `P-n40-k5` seed 11 (-4.0).
- Runtime aggregate excluded due `low_cached_champion`.
- Decision: `abandon`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`,
  `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`,
  `SCREENING_RUNTIME_BUDGET_SATURATION`,
  `CANDIDATE_RUNTIME_BUDGET_SATURATION`.
- Code session had two guarded retries before success:
  telemetry identity mismatch on undeclared `alns` telemetry, then contract
  preview/import failure. Final patch passed all gates.

Assessment: this was a substantive refinement, not a token-saving artifact. It
produced the strongest movement in the run, but it also produced clear damage
on `A-n32-k5` and a negative median. The abandon decision was correct.

## LLM Call Analysis

Every round used two agentic sessions: one hypothesis session and one code
session. Hypothesis sessions made exactly two calls:
`hypothesis_target_intent` then `hypothesis`. Code sessions used
`tool_selection` calls to inspect branch state, surfaces, files, and feedback,
then a `code` call. The final round needed three `code` calls because guard
feedback rejected the first two patch drafts.

| Round | Session | Call | Phase | Request | Tool/result | Purpose/result | Tokens in/out |
|---:|---|---:|---|---|---|---|---:|
| 1 | `4d27a286` | 1 | draft_hypothesis | `hypothesis_target_intent` | `demand_slack_regret_repair -> destroy_repair.py` | select target intent/mechanism | 23993/180 |
| 1 | `4d27a286` | 2 | draft_hypothesis | `hypothesis` | `destroy_repair.py` | draft structured hypothesis | 31105/906 |
| 1 | `039c3749` | 1 | diagnose | `tool_selection` | `context.read_branch_state` | inspect current branch/champion context | 11071/34 |
| 1 | `039c3749` | 2 | diagnose | `tool_selection` | `context.read_surface` | inspect solver-design surface | 11183/56 |
| 1 | `039c3749` | 3 | diagnose | `tool_selection` | `context.read_algorithm_file:baseline_algorithm.py` | inspect orchestration entry point | 11391/54 |
| 1 | `039c3749` | 4 | inspect_interface | `tool_selection` | `context.read_algorithm_file:scheduler.py` | inspect repair integration point | 13522/56 |
| 1 | `039c3749` | 5 | inspect_interface | `tool_selection` | `context.read_algorithm_file:state.py` | inspect route/state helpers | 13867/55 |
| 1 | `039c3749` | 6 | inspect_interface | `tool_selection` | `feedback.query_screening` | inspect prior screening feedback | 14189/70 |
| 1 | `039c3749` | 7 | inspect_interface | `tool_selection` | `feedback.query_runtime` | inspect runtime pressure | 14340/41 |
| 1 | `039c3749` | 8 | inspect_interface | `tool_selection` | `context.read_surface` | full target preview | 14487/72 |
| 1 | `039c3749` | 9 | inspect_interface | `tool_selection` | `STOP` | stop inspection; proceed to code | 14626/21 |
| 1 | `039c3749` | 10 | draft_patch | `code` | `destroy_repair.py` | generate accepted patch | 29221/3189 |
| 2 | `c1ae94f8` | 1 | draft_hypothesis | `hypothesis_target_intent` | `cross_route_2opt_reconnect -> local_search.py` | select target intent/mechanism | 25526/160 |
| 2 | `c1ae94f8` | 2 | draft_hypothesis | `hypothesis` | `local_search.py` | draft structured hypothesis | 32535/938 |
| 2 | `de7561c3` | 1 | diagnose | `tool_selection` | `context.read_algorithm_file:destroy_repair.py` | inspect prior repair implementation | 11415/58 |
| 2 | `de7561c3` | 2 | inspect_interface | `tool_selection` | `context.read_branch_state` | inspect branch state and feedback | 13592/34 |
| 2 | `de7561c3` | 3 | inspect_interface | `tool_selection` | `STOP` | stop inspection; proceed to code | 13733/21 |
| 2 | `de7561c3` | 4 | draft_patch | `code` | `local_search.py` | generate accepted patch | 27212/2251 |
| 3 | `da291abf` | 1 | draft_hypothesis | `hypothesis_target_intent` | `savings_route_merge_postrepair -> route_merge.py` | select target intent/mechanism | 27648/180 |
| 3 | `da291abf` | 2 | draft_hypothesis | `hypothesis` | `route_merge.py` | draft structured hypothesis | 34497/911 |
| 3 | `53f4bbc5` | 1 | diagnose | `tool_selection` | `context.read_algorithm_file:destroy_repair.py` | inspect repair context | 11507/58 |
| 3 | `53f4bbc5` | 2 | diagnose | `tool_selection` | `context.read_algorithm_file:local_search.py` | inspect VNS/local-search context | 11660/56 |
| 3 | `53f4bbc5` | 3 | inspect_interface | `tool_selection` | `context.read_branch_state` | inspect branch feedback | 13938/34 |
| 3 | `53f4bbc5` | 4 | inspect_interface | `tool_selection` | `STOP` | stop inspection; proceed to code | 14084/21 |
| 3 | `53f4bbc5` | 5 | draft_patch | `code` | `route_merge.py` | generate accepted patch | 25543/2393 |
| 4 | `a992f750` | 1 | draft_hypothesis | `hypothesis_target_intent` | `savings_route_merge_postrepair -> route_merge.py` | select same-branch refinement target | 29893/177 |
| 4 | `a992f750` | 2 | draft_hypothesis | `hypothesis` | `route_merge.py` | draft refinement hypothesis | 42280/872 |
| 4 | `01c45793` | 1 | diagnose | `tool_selection` | `context.read_algorithm_file:destroy_repair.py` | inspect related repair context | 12166/58 |
| 4 | `01c45793` | 2 | diagnose | `tool_selection` | `context.read_algorithm_file:local_search.py` | inspect local-search context | 12313/56 |
| 4 | `01c45793` | 3 | inspect_interface | `tool_selection` | `context.read_branch_state` | inspect branch-local route-merge feedback | 14408/34 |
| 4 | `01c45793` | 4 | inspect_interface | `tool_selection` | `STOP` | stop inspection; proceed to code | 14551/21 |
| 4 | `01c45793` | 5 | draft_patch | `code` | `route_merge.py` | generate accepted patch | 28532/2089 |
| 5 | `c920e626` | 1 | draft_hypothesis | `hypothesis_target_intent` | `telemetry_guided_operator_phase_bridge -> scheduler.py` | select scheduler mechanism | 29682/194 |
| 5 | `c920e626` | 2 | draft_hypothesis | `hypothesis` | `scheduler.py` | draft scheduler-selection hypothesis | 39368/897 |
| 5 | `81f449ef` | 1 | diagnose | `tool_selection` | `context.read_algorithm_file:destroy_repair.py` | inspect operator inputs | 11492/58 |
| 5 | `81f449ef` | 2 | diagnose | `tool_selection` | `context.read_algorithm_file:local_search.py` | inspect local-search effects | 11645/56 |
| 5 | `81f449ef` | 3 | inspect_interface | `tool_selection` | `context.read_branch_state` | inspect cross-branch/branch feedback | 13723/34 |
| 5 | `81f449ef` | 4 | inspect_interface | `tool_selection` | `STOP` | stop inspection; proceed to code | 13875/21 |
| 5 | `81f449ef` | 5 | draft_patch | `code` | `scheduler.py` | generate accepted patch | 26836/3323 |
| 6 | `06a73430` | 1 | draft_hypothesis | `hypothesis_target_intent` | `slack_weighted_regret_repair -> destroy_repair.py` | select repair follow-up | 31759/187 |
| 6 | `06a73430` | 2 | draft_hypothesis | `hypothesis` | `destroy_repair.py` | draft branch-local follow-up hypothesis | 43513/930 |
| 6 | `0e4c4e04` | 1 | inspect_interface | `tool_selection` | `context.read_branch_state` | inspect prior scheduler-only feedback | 13705/34 |
| 6 | `0e4c4e04` | 2 | inspect_interface | `tool_selection` | `STOP` | stop inspection; proceed to code | 13854/21 |
| 6 | `0e4c4e04` | 3 | draft_patch | `code` | `destroy_repair.py` | generate accepted patch | 29549/1894 |
| 7 | `aebc55e1` | 1 | draft_hypothesis | `hypothesis_target_intent` | `rank_buffer_acceptance -> acceptance.py` | select acceptance mechanism | 30861/184 |
| 7 | `aebc55e1` | 2 | draft_hypothesis | `hypothesis` | `acceptance.py` | draft acceptance hypothesis | 43673/944 |
| 7 | `9a32b326` | 1 | diagnose | `tool_selection` | `context.read_branch_state` | inspect branch/cross-branch status | 11360/34 |
| 7 | `9a32b326` | 2 | diagnose | `tool_selection` | `context.read_surface` | inspect solver-design surface | 11479/56 |
| 7 | `9a32b326` | 3 | diagnose | `tool_selection` | `context.read_algorithm_file:baseline_algorithm.py` | inspect solver entry point | 11689/54 |
| 7 | `9a32b326` | 4 | inspect_interface | `tool_selection` | `context.read_algorithm_file:scheduler.py` | inspect acceptance integration | 13733/56 |
| 7 | `9a32b326` | 5 | inspect_interface | `tool_selection` | `STOP` | stop inspection; proceed to code | 14075/21 |
| 7 | `9a32b326` | 6 | draft_patch | `code` | `acceptance.py` | generate accepted patch | 26632/2884 |
| 8 | `84e4df68` | 1 | draft_hypothesis | `hypothesis_target_intent` | `rank_buffer_schedule_bridge -> scheduler.py` | select same-branch schedule bridge | 32702/180 |
| 8 | `84e4df68` | 2 | draft_hypothesis | `hypothesis` | `scheduler.py` | draft refinement hypothesis | 43003/934 |
| 8 | `1e9efe08` | 1 | inspect_interface | `tool_selection` | `context.read_branch_state` | inspect rank-buffer feedback | 13586/34 |
| 8 | `1e9efe08` | 2 | inspect_interface | `tool_selection` | `STOP` | stop inspection; proceed to code | 13738/21 |
| 8 | `1e9efe08` | 3 | draft_patch | `code` | `scheduler.py` | rejected: telemetry identity mismatch | 28743/3425 |
| 8 | `1e9efe08` | 4 | draft_patch | `code` | `scheduler.py` | rejected: contract preview/import failure | 31797/2275 |
| 8 | `1e9efe08` | 5 | draft_patch | `code` | `scheduler.py` | final accepted patch | 33973/2851 |

Tool-selection provenance assessment:

- The deterministic prefetch plans were present for all code sessions.
- Prefetch commonly included `memory.query`, `feedback.query_screening`,
  `feedback.query_runtime`, `context.read_branch_state`, and selected
  `context.read_algorithm_file` calls.
- The LLM did not write during tool selection; tool selection only chose
  read-only inspection tools or `STOP`.
- The eight `STOP` calls are not skipped/invalid planner overhead; they are the
  explicit end of inspection before code generation.
- There were no schema retries in hypothesis/tool-selection traces and no
  failed LLM trace status.
- Round 8 code retry was productive guard-driven repair. It is the only
  material planner/code overhead.

## Branch-Level Research Trajectory

### Branch `2d1ac121`: demand-slack repair

The branch hypothesis was reasonable: change repair scoring to preserve slack
and avoid downstream poor insertions. Code implemented the hypothesis directly.
Feedback did not support further work: one pair win was outweighed by three
pair losses and a case-level regression. Soft lifecycle archive was correct.

### Branch `a31b7096`: cross-route 2-opt reconnect

This was a clean fork with a different mechanism: route-level VNS neighborhood
rather than repair scoring. It was a reasonable diversification after round 1.
The implementation was bounded and strict-improvement only. The result again
showed a small `B-n31-k5` win but `B-n52-k7` damage, so abandoning was correct.

### Branch `ca2204f8`: route merge postrepair

This branch shows coherent follow-up. Round 3 introduced whole-route
savings-merge postrepair and produced one pair-level win with no losses. Round
4 refined the same mechanism using intra-merge cleanup, explicitly based on the
round 3 feedback that endpoint-only merge was too restrictive. The follow-up
was scientifically coherent, but it regressed to all ties, so the branch did
not remain a strong research direction.

### Branch `3a83f295`: scheduler operator phase bridge to repair change

This branch is the strongest evidence of adaptive research behavior. Round 5
tested whether telemetry-guided pair suppression could make operator selection
less wasteful; it activated but produced no objective movement. Round 6 then
changed the actual repair mechanism with `slack_weighted_regret_repair`, using
the previous diagnostic result as motivation. The follow-up produced real
movement, but wins and losses balanced. The lifecycle park after round 6
prevented active-slot pressure from deadlocking the run.

### Branch `3239c6f5`: rank-buffer acceptance and schedule bridge

This branch used the prior observation that VNS generated most improvement and
ALNS acceptance mostly controlled which states reached VNS. Round 7 added a
rank-buffer acceptance criterion; round 8 changed VNS scheduling for
rank-buffer-selected states. This is coherent same-mechanism follow-up. The
second candidate generated the largest signal but with major `A-n32-k5` damage
and negative median delta, so abandon was correct.

Cross-branch behavior was acceptable. The agent did not merely repeat the same
patch: it moved across repair scoring, route reconnection, route merge,
scheduler pair selection, acceptance, and VNS scheduling. Later branches used
prior weak/no-effect feedback as proposal visibility, but Decision outcomes
remained structured.

## Effective Algorithm Research Assessment

Positive evidence:

- Hypotheses were mechanism-specific rather than generic token/tool
  optimization.
- Candidate code implemented the stated mechanism in each round.
- Telemetry guard passed for all candidates and declared mechanisms were
  observed.
- Follow-ups were based on branch-local feedback: route merge refinement,
  scheduler bridge to repair change, and rank-buffer acceptance to scheduler
  bridge.
- Contract/Verification/Canary/Protocol remained active on every candidate.

Weaknesses:

- No candidate reached validation or frozen stages.
- Most results were tie-heavy at case level.
- Pair-level wins were often isolated and balanced by losses.
- Runtime evidence was frequently low/cached or excluded from decision features,
  so runtime observations were mostly proposal guidance.
- The strongest moving candidate, round 8, had a negative median delta and
  major losses on `A-n32-k5`.

Verdict: the agent is doing effective research process, but not yet effective
algorithm improvement. It is learning and testing real mechanisms; the tested
mechanisms did not produce robust solver quality gains.

## Scion v3 Boundary Check

Decision boundary:

- LLM-generated hypotheses and patches remained tainted proposal artifacts.
- Candidate decisions were recorded as structured Decision outcomes with reason
  codes.
- Runtime evidence policies explicitly set `standalone_optimization_signal=false`
  and `decision_features_excluded=true` where appropriate.
- Cross-branch observability is recorded as `proposal_observability_only` and
  `decision_input_policy=excluded_from_decision_features`.

Evidence path:

- All candidates passed Contract, Verification, and Canary before Protocol.
- Protocol metrics used declared lexicographic objective semantics.
- Metrics resolved CVRP case paths under the safe data root.
- Replay identity fields were complete for every formal candidate.

Generic-core contamination check:

- Candidate changes were in solver-design subject files inside campaign
  workspaces/artifacts: `destroy_repair.py`, `local_search.py`,
  `route_merge.py`, `scheduler.py`, and `acceptance.py`.
- CVRP-specific behavior stayed in problem/solver artifacts and metrics.
- The inspected run artifacts did not show CVRP-specific concepts being used as
  generic scheduler/Decision criteria.

Verdict: no v3 architecture boundary violation found in this run.

## Comparison With Previous Partial 8R

Previous partial 8R:

- `run_validity_status=valid_partial_interrupted`.
- Completed only 5/8 formal screening candidates.
- Had `scheduler_active_slot_blocked_attempts=3`.
- Stopped with `scheduler_active_slot_blocked`.
- Root cause was clean-fork pressure at active slot capacity with reclaim
  candidates present but no Decision-origin park marker.

Current successful 8R:

- `run_validity_status=valid`.
- Completed 8/8 formal screening candidates.
- Had `scheduler_active_slot_blocked_attempts=0`.
- Stopped normally with `max_rounds_exhausted`.
- After round 6, lifecycle parked `3a83f295` and released its active slot, then
  round 7 clean-forked `3239c6f5`.

Improvement:

- Framework stability clearly improved for this workload.
- Counter semantics are coherent across status, summary, DB, metrics, and
  candidate artifacts.
- Tool-selection provenance and replay identity remain complete.

No direct proof:

- No `scheduler_active_slot_reclaim` event appeared in this run.
- The exact scheduler-origin reclaim path was not exercised by campaign
  artifacts; its evidence still comes from unit tests.

Research quality compared to partial 8R:

- Research quality is broadly similar: real mechanisms, weak solver signal.
- This run has more branch variety and completes enough rounds to expose
  branch-local follow-up behavior after the previous failure point.
- It does not produce stronger algorithmic acceptance evidence than the partial
  run; it produces stronger framework-run evidence.

## 12R Readiness

I do not see a blocking framework defect for 12R. The repaired scheduler is
good enough to attempt 12R because this run completed the requested 8 formal
screening rounds with zero active-slot blocked attempts, complete lineage,
complete replay identities, and complete trace/provenance surfaces.

Recommended 12R conditions:

- Keep the active-branch pressure condition enabled so scheduler lifecycle and
  reclaim behavior remain observable.
- Add an explicit post-run check for whether `scheduler_active_slot_reclaim`
  occurs; if not, state that reclaim-path coverage remains unit-test-only.
- Track runtime evidence pressure separately from algorithm quality, because
  runtime remains proposal guidance rather than Decision input.
- Treat any validation/frozen transition as a higher-risk gate and inspect
  replay identity plus structured DecisionFeatures before acceptance.

No source fix is required before 12R based on this run. The main optimization
opportunity is analytical: require future reports to separate "scheduler
stability proven by completed run" from "scheduler-origin reclaim path
exercised by campaign event".
