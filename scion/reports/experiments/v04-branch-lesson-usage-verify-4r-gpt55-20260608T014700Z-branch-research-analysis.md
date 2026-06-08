# v0.4 Branch Lesson Usage 4R GPT-5.5 Experiment Analysis

Experiment:
`/home/clawd/research/scion-experiments/v04-branch-lesson-usage-verify-4r-gpt55-4r-gpt55-20260608T014700Z-claw/campaign`

Report date: 2026-06-08

Primary design reference:
`/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md`

## Executive Conclusion

This 4R run is a valid completed post-P1 smoke at the campaign/accounting level:
`exit.txt` reports `CAMPAIGN_EXIT_STATUS:complete`,
`RUN_VALIDITY_STATUS:valid`, `RUN_COMPLETE:True`,
`COMPLETED_REQUESTED_ROUNDS:True`, and `LAST_STOP_REASON:max_rounds_exhausted`.
`campaign_summary.json` agrees: `total_rounds=4`, `proposal_attempts=4`,
`screened_rounds=4`, `effective_rounds_completed=4`,
`screened_experiments=4`, `telemetry_failed_experiments=0`, and
`lineage_integrity.status=complete`.

Research-quality conclusion: the run shows real branch lesson usage in the LLM
hypothesis outputs, not just a schema field. R2 explicitly avoided R1's costly
cross-route local-search path and moved pressure into ALNS repair. R3 preserved
R2's pair-level weak positive but changed the activation path into scheduler
selective route-guarding. R4 borrowed the idea of mechanism-specific telemetry
while creating a clean-fork local-search route-absorption mechanism. This is
material algorithm research, not a token-reduction exercise.

The result is not an algorithmic success. All four formal candidates failed the
case-level screening gate: 0 case wins in every round, median delta 0.0 in every
round, no validation/frozen stages, no promotion, and two quality-regression
terminal branches. R2 and R3 produced weak pair-level positives, but those did
not become case-level wins and were correctly kept out of promotion decisions.

Post-P1 smoke verdict: pass with caveats. The new `branch_lesson_usage` schema
is visible in all four hypothesis outputs, and the global counters detect
borrow/avoid/contrast/preserve patterns. However, the durable lesson record path
is not clean: `cross_branch_research_observability.branch_lesson_record_count=0`
while `branch_lesson_usage_satisfied_count=4`; every
`steps[].step_visibility_audit.cross_branch_research_visibility` is
`status=missing`. This means the LLM-facing map works, but step-level persisted
evidence is not yet strong enough to treat the counters as fully auditable.

Recommendation: do not use this 4R as an algorithm-quality green light. It is
reasonable to run an 8R framework smoke after fixing the observability issues
below, or to run 8R immediately only if it is explicitly framed as a continued
branch-lesson observability stress test. Before an 8R research-quality claim,
fix durable `branch_lesson.v1` recording/counting consistency and reduce
truncation in `branch_lesson_usage_context`.

## Evidence Scope

Read-only evidence inspected:

| Evidence | Files / fields |
|---|---|
| Run status | `exit.txt`, `status.json`, `run_status.json` |
| Campaign summary | `campaign_summary.json` |
| Formal candidate index | `artifacts/formal_candidates/index.jsonl` |
| Candidate diffs | 4 `candidate.diff` files under `artifacts/formal_candidates/*/` |
| Agent sessions | `agentic_sessions/agentic_session_trace_index.json`, `agentic_session_index.json`, 8 `output.json` files |
| Prompt manifests | hypothesis target intent, hypothesis, tool-selection, and code manifests |
| Trace accounting | `llm_traces/*.json`, summarized by `campaign_summary.cache_stats` |
| DB state | `scion.db` tables: `branches`, `hypotheses`, `experiment_events` |
| v3 boundary | `scion/design/scion-architecture-v3.md` sections 1.3, 4.1-4.2 |

Top-level accounting:

| Field | Value |
|---|---:|
| `total_rounds` | 4 |
| `proposal_attempts` / `proposal_attempts_consumed` | 4 / 4 |
| `screened_rounds` | 4 |
| `effective_rounds_completed` | 4 |
| `formal_screened_candidates` | 4 |
| `protocol_stage_counts.screening` | 4 |
| `protocol_stage_counts.validation` / `frozen` | 0 / 0 |
| `quality_blocks` | 0 |
| `telemetry_failed_experiments` | 0 |
| `scheduler_active_slot_blocked_attempts` | 0 |
| `lineage_integrity.status` | `complete` |
| `evidence_integrity.status` | `complete` |

LLM accounting from `campaign_summary.cache_stats`:

| Request kind | Calls | Prompt tokens | Output tokens | Cache read |
|---|---:|---:|---:|---:|
| `hypothesis_target_intent` | 4 | 110,485 | 725 | 0 |
| `hypothesis` | 4 | 148,469 | 4,386 | 0 |
| `tool_selection` | 18 | 232,867 | 798 | 13,824 |
| `code` | 5 | 146,676 | 13,624 | 0 |
| total | 31 | 638,497 | 19,533 | 13,824 |

The low overall cache hit rate, `0.0217`, is not a research-quality failure, but
it indicates operational overhead. Repeated cache-key diagnostics appear for
several tool-selection groups and one code retry group.

## Candidate Summary

| R | Branch | Hypothesis | Candidate | Mechanism | File | Case W/L/T | Pair W/L/T | Median / CI | Decision |
|---:|---|---|---|---|---|---:|---:|---|---|
| 1 | `e5810a4d` | `e91b7900` | `e2d973a5c69d41d9` | `cross_route_2opt_reconnect` | `local_search.py` | 0/0/8 | 1/2/13 | 0.0 / [-0.25, 0.0] | `abandon` |
| 2 | `82627cc0` | `ba96d4ad` | `d05a750f9b6511bc` | `route_count_guarded_insertion` | `destroy_repair.py` | 0/0/8 | 2/0/14 | 0.0 / [0.0, 0.75] | `continue_explore` |
| 3 | `82627cc0` | `b8e060b5` | `4e2dbb70ad74a12e` | `route_guard_activation_schedule` | `scheduler.py` | 0/0/8 | 3/2/11 | 0.0 / [-1.5, 1.25] | `continue_explore` + park |
| 4 | `d2e23122` | `b3724d68` | `002991d5bbbe9444` | `route_merge_ejection_chain` | `local_search.py` | 0/0/8 | 0/2/14 | 0.0 / [-1.5, 0.0] | `abandon` |

Formal candidate refs:

- R1: `artifacts/formal_candidates/e5810a4d/screening-e91b7900-f844-414d-80ed-f20e3baeaef9-e2d973a5c69d41d9/candidate.diff`
- R2: `artifacts/formal_candidates/82627cc0/screening-ba96d4ad-6f0e-4f99-81bb-212fc57868fc-d05a750f9b6511bc/candidate.diff`
- R3: `artifacts/formal_candidates/82627cc0/screening-b8e060b5-3f49-4da9-bc71-736a41d90620-4e2dbb70ad74a12e/candidate.diff`
- R4: `artifacts/formal_candidates/d2e23122/screening-b3724d68-525d-487c-9b5e-b68bc98ad7e5-002991d5bbbe9444/candidate.diff`

## Round-by-Round Analysis

### R1: `e5810a4d`, `cross_route_2opt_reconnect`

Scheduler/branch state: scheduler chose `explore_new` with reason
`new_exploration_slot_available`. Finalizer action was
`explore_new_clean_fork`; after screening the branch became
`abandoned` / `discarded`. DB `branches` records
`last_screening_feedback_tier=quality_regression` and mechanism
`["cross_route_2opt_reconnect"]`.

Hypothesis: add a bounded VNS cross-route 2-opt reconnection operator in
`policies/baseline_modules/local_search.py`. The proposal targeted residual
`total_distance` after feasible construction/ALNS/VNS, contrasting against
existing relocate/swap/Or-opt/two-opt-star operators.

Branch lesson usage: the hypothesis output includes
`hypothesis.branch_lesson_usage.contrasted_lessons` with
`lesson:f0900e5e1c864023`, claiming a contrast along mechanism family, target
file, effect path, activation path, and runtime budget strategy. Because this is
R1, this is weaker than later records: it appears to contrast against map memory
for the same branch id before this run's first formal candidate, not against a
prior observed step in this 4R.

Code implementation: the diff adds `_cross_route_2opt_reconnect` to
`_default_vns_operators()` in `local_search.py`. The operator enumerates route
pairs and cut positions, tries reversed suffix reconnections, rejects capacity
overload, enforces a check limit, polls `context.remaining_time()`, and records
`context.record_iteration`, `record_move`, and `record_phase` for the mechanism.
The code session completed with `code_retry_failure_count=0`, schema preview
passed, contract preview passed, and smoke evidence
`algorithm_smoke_execution_evidence_0001.json` passed.

Protocol/screening: Contract and Verification passed. Screening was case
0/0/8, pair 1/2/13, median delta 0.0, CI [-0.25, 0.0]. Fleet violation stayed
tied. Mechanism telemetry was observed and positive at phase level, but
`phase_causal_summary.classification=phase_positive_final_objective_loss`.
Runtime was high confidence and fresh enough, but only
`tie_break_supporting_signal`; `runtime_evidence_policy` states
`proposal_guidance_only=true` and `decision_features_excluded=true`.

Framework decision: `abandon` from `lifecycle_policy`, with reason codes
`SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
`SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`,
`SCREENING_RUNTIME_BUDGET_SATURATION`, and `BOTH_RUNTIME_BUDGET_SATURATION`.
This is the right decision: the operator activated, but produced no case wins,
two pair losses, and both candidate/champion runtime saturation.

### R2: `82627cc0`, `route_count_guarded_insertion`

Scheduler/branch state: scheduler again chose `explore_new` /
`new_exploration_slot_available`, creating a clean fork. After screening the
branch remained available for exploration with `decision=continue_explore`.

Hypothesis: shift improvement pressure away from R1's costly cross-route VNS
operator and into ALNS repair. The proposal modifies insertion repair helpers
so greedy/regret insertion can run in a route-count-guarded mode: when already
at max routes, new-route fallback is unavailable and repair must insert removed
customers into existing capacity-feasible routes or abort.

Branch lesson usage: this is a substantive cross-branch reaction. The hypothesis
output includes `avoided_lessons` referencing `lesson:9f7a779bfd0dee4f` from
`e5810a4d`, with contrast
`destroy_repair_early_abort_not_cross_route_local_search`. It also includes a
`contrasted_lessons` record for `route_limit_repair_guard`. The text explicitly
says the previous local-search cross-route mechanism consumed saturated runtime
while producing tie-dominated outcomes.

Code implementation: `candidate.diff` modifies
`policies/baseline_modules/destroy_repair.py`. It changes
`_greedy_insertion`, `_regret2_insertion`, `_regret3_insertion`, and
`_regret_insertion` to accept `max_routes` and `context`; adds guarded
new-route blocking, telemetry around `route_count_guarded_insertion`, and abort
behavior when no existing-route insertion is feasible. The code session
completed with no code retry, schema and contract preview passed, and smoke
passed.

Protocol/screening: Contract and Verification passed. Screening was case
0/0/8, pair 2/0/14, median delta 0.0, CI [0.0, 0.75]. This is a weak positive
at pair level but not a case-level win. Runtime evidence was
`low_cached_champion`, `fresh_champion_required`, and
`runtime_aggregate_excluded=true`; runtime could only be used as audit/proposal
guidance. Candidate runtime saturated: max candidate elapsed 9,651 ms with
`CANDIDATE_RUNTIME_BUDGET_SATURATION`.

Framework decision: `continue_explore` from `stage_decision`, with reason codes
`RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, `SCREENING_RUNTIME_BUDGET_SATURATION`,
and `CANDIDATE_RUNTIME_BUDGET_SATURATION`. This is reasonable: it preserved a
weak pair signal but did not promote or validate.

### R3: `82627cc0`, `route_guard_activation_schedule`

Scheduler/branch state: scheduler chose `exploit_weak_positive` with reason
`fresh_champion_runtime_replay_followup`, selecting the same `82627cc0` branch.
After screening, finalizer action was `parked_lineage_released` and next policy
`clean_fork_or_other_branch_required`. DB `branches` records
`state=parked_lineage`, `branch_code_status=parked_lineage`,
mechanisms `["route_count_guarded_insertion", "route_guard_activation_schedule"]`,
and `branch_lifecycle_policy_blocks=1`.

Hypothesis: preserve R2's weak pair-positive route-count idea, but move the
guarded behavior out of always-on repair internals into scheduler selective
activation. The scheduler should pay guarded-repair cost only when already at
max routes and when the destroy context is likely useful, such as route removal
or high-saving worst removal.

Branch lesson usage: this is the best example of useful same-branch depth. The
hypothesis output includes `preserved_same_branch_lesson` with
`preserved_signal=weak_pair_positive` and
`tested_failure=always_on_guarded_repair_no_case_wins`; it also avoids the
high-cost cross-route VNS lesson and contrasts `repair_internal_always_on`
against `scheduler_selective_at_limit`.

Code implementation: `candidate.diff` modifies
`policies/baseline_modules/scheduler.py`. It imports `_best_insertions` and
`_insert_existing`, adds `_use_route_guard()` and `_guarded_repair()`, gates
guarded repair to route/worst destroy contexts while at max routes, and records
`route_guard_activation_schedule` telemetry. This code session required one
retry: `code_retry_failure_detail_0001.json` shows the first smoke failed
because `_regret3_insertion()` received unexpected keyword `max_routes`.
The second smoke evidence passed.

Protocol/screening: Contract and Verification passed. Screening was case
0/0/8, pair 3/2/11, median delta 0.0, CI [-1.5, 1.25]. Mechanism activation was
observed and pair-level positive, but final objective evidence still failed:
`phase_causal_summary.classification=phase_positive_final_objective_loss`.
Runtime aggregate was excluded due to cached/low-confidence champion evidence.

Framework decision: `continue_explore` from `stage_decision`, but lifecycle
parked the lineage with `BRANCH_LIFECYCLE_PARK_LINEAGE` and
`SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_EXHAUSTED`. This is the correct
research lifecycle outcome: R3 improved pair wins from 2 to 3 but introduced 2
pair losses and no case wins, so retaining a checkpoint while forcing a clean
fork is more defensible than another same-branch refinement.

### R4: `d2e23122`, `route_merge_ejection_chain`

Scheduler/branch state: scheduler returned to `explore_new` with
`new_exploration_slot_available`. Finalizer selected
`explore_new_clean_fork`. After screening the branch was `abandoned` /
`discarded`, with `last_screening_feedback_tier=quality_regression`.

Hypothesis: add a bounded route-merge/ejection-chain VNS neighborhood in
`local_search.py`, selecting the smallest or sparsest routes, trying to absorb
their customers into nearby capacity-feasible routes, and allowing one bounded
ejection when direct insertion is blocked.

Branch lesson usage: R4 shows both useful and questionable cross-branch use.
The hypothesis avoids `lesson:9f7a779bfd0dee4f`
(`not_generic_cross_route_reconnect`), borrows `lesson:d4dac8c01d7d1c18`
(`bridge_with_mechanism_specific_effect_telemetry`), and contrasts against
destroy-repair / route-guard work. That is explicit cross-branch reasoning.
However, it still returns to a local-search route-absorption family shortly
after R1's local-search cost/regression, so the diversity claim is only partly
convincing.

Code implementation: `candidate.diff` modifies
`policies/baseline_modules/local_search.py`, adding
`_route_merge_ejection_chain` to VNS plus helper functions
`_absorb_pending_customers`, `_insert_direct_near`, and
`_insert_with_one_ejection`. The implementation is bounded by source route
caps, pending step caps, nearby route filtering, depth-one ejection, and
remaining-time checks. The code session completed without retry and smoke
passed.

Protocol/screening: Contract and Verification passed. Screening was case
0/0/8, pair 0/2/14, median delta 0.0, CI [-1.5, 0.0]. Candidate runtime
saturated: max elapsed 10,192 ms with `CANDIDATE_RUNTIME_BUDGET_SATURATION`.
Mechanism telemetry activated, but final objective signal was negative.

Framework decision: `abandon` from `lifecycle_policy`, with reason codes
`SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
`SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`,
`SCREENING_RUNTIME_BUDGET_SATURATION`, and
`CANDIDATE_RUNTIME_BUDGET_SATURATION`. This branch should not be continued
without a materially cheaper and more targeted route-absorption gate.

## LLM Call Analysis

Trace order from `agentic_session_trace_index.json`:

| Time | Branch | Kind | Session | Notes |
|---|---|---|---|---|
| 01:47:01 | `e5810a4d` | `hypothesis_target_intent` | `852e3825` | R1 target intent |
| 01:47:08 | `e5810a4d` | `hypothesis` | `852e3825` | R1 hypothesis with `branch_lesson_usage` |
| 01:47:31-01:47:49 | `e5810a4d` | 7 tool-selection + 1 code | `1eb89bf6` | R1 code |
| 01:54:58 | `82627cc0` | `hypothesis_target_intent` | `54c7dba7` | R2 target intent |
| 01:55:04 | `82627cc0` | `hypothesis` | `54c7dba7` | R2 hypothesis with avoid/contrast |
| 01:55:25-01:55:31 | `82627cc0` | 3 tool-selection + 1 code | `26610857` | R2 code |
| 02:00:31 | `82627cc0` | `hypothesis_target_intent` | `6116c346` | R3 target intent |
| 02:00:37 | `82627cc0` | `hypothesis` | `6116c346` | R3 hypothesis with preserve/avoid/contrast |
| 02:01:00-02:01:38 | `82627cc0` | 3 tool-selection + 2 code | `06622b53` | R3 code + retry |
| 02:06:35 | `d2e23122` | `hypothesis_target_intent` | `c3e81fa0` | R4 target intent |
| 02:06:41 | `d2e23122` | `hypothesis` | `c3e81fa0` | R4 hypothesis with borrow/avoid/contrast |
| 02:07:09-02:07:24 | `d2e23122` | 5 tool-selection + 1 code | `9085fed2` | R4 code |

Context completeness:

- All four hypothesis manifests include `cross_branch_research_map` and
  `branch_lesson_usage_context`. The hypothesis manifest section sizes grow
  from 4,303 / 2,853 chars in R1 to 20,057 / 6,176 chars in R4.
- All four hypothesis manifests include `sibling_branches`, but that section is
  only about 50 chars. The actionable sibling signal mostly comes from the
  cross-branch map and branch lesson usage context, not the sibling summary.
- R3 and R4 `branch_lesson_usage_context` sections are marked
  `truncated=true`; R1/R2 are not. This did not prevent useful usage, but it is
  a context-risk signal before scaling to 8R.
- Code manifests include `full_solver_algorithm_rules`,
  `active_algorithm_facts`, `approved_target_file_current_content`, and
  `branch_current_integration_files`. They do not need cross-branch lesson text
  as strongly as hypothesis generation, because code should implement the
  approved hypothesis against current source.
- Hypothesis outputs use the new schema field:
  R1 `contrasted_lessons`; R2 `avoided_lessons` and `contrasted_lessons`;
  R3 `avoided_lessons`, `contrasted_lessons`, and
  `preserved_same_branch_lesson`; R4 `avoided_lessons`, `borrowed_lessons`,
  `clean_fork_diversity_claim`, and `contrasted_lessons`.

Tool selection quality:

- Hypothesis sessions used deterministic prefetch well: R1 used
  `memory.query`; R2-R4 also prefetch `feedback.query_screening` and
  `feedback.query_runtime`, matching accumulated evidence.
- Code sessions had enough context and mostly avoided waste by returning
  `summary_only` for already observed files.
- There is still avoidable overhead. R1 made 7 tool-selection calls and queried
  empty screening feedback. R4 made three repeated `context.read_algorithm_file`
  calls that returned `summary_only`. Summary-only reads are cheap relative to
  full file reads, but they still consumed planner calls and prompt cache
  opportunities.
- The R3 code retry was legitimate, not waste: smoke found an interface
  mismatch in inherited branch code (`_regret3_insertion()` unexpected
  `max_routes`), and the retry fixed it.

## Branch-Level Research Analysis

### Branch `e5810a4d`

Research line: local-search cross-route reconnection.

Hypothesis chain: one formal hypothesis, `cross_route_2opt_reconnect`, aiming
at residual distance after feasible construction and ALNS/VNS.

Code chain: one `local_search.py` VNS operator. It is well-bounded and
instrumented, and it uses source-aware constraints such as capacity, route
nonemptiness, time reserve, and strict cost improvement.

Evidence chain: mechanism activated with phase-positive telemetry, but final
objective evidence was regression/tie-dominated: case 0/0/8, pair 1/2/13,
median 0.0, CI high 0.0. Runtime saturated on both candidate and champion.

Lifecycle result: abandoned/discarded. This is the right branch outcome. It
generated a useful negative lesson for later branches: avoid broad cross-route
local-search enumeration under saturated runtime unless the trigger is much
more selective.

### Branch `82627cc0`

Research line: route-count pressure during repair and scheduler composition.

Hypothesis chain:

1. `route_count_guarded_insertion` moved route-limit handling earlier, from
   final rejection into repair-time insertion.
2. `route_guard_activation_schedule` preserved the weak pair-positive signal
   but changed the activation path from always-on repair internals to selective
   scheduler gating.

Code chain:

1. R2 modified `destroy_repair.py` signatures and behavior for greedy/regret
   insertion under max-route constraints.
2. R3 modified `scheduler.py` to decide when to use guarded repair and to record
   separate mechanism telemetry.

Evidence chain: R2 produced case 0/0/8 and pair 2/0/14 with CI [0.0, 0.75].
R3 produced case 0/0/8 and pair 3/2/11 with CI [-1.5, 1.25]. The pair signal
improved in raw wins but also gained losses and remained case-neutral.
Runtime evidence was low/cached and excluded from aggregate decision features.

Lifecycle result: parked lineage. This is the most reasonable deep branch in
the run. The agent did not blindly repeat the same mechanism; it used the R2
lesson to alter trigger/composition. But after two formal candidates and no
case wins, the park/clean-fork policy is justified.

### Branch `d2e23122`

Research line: clean-fork local route absorption with ejection.

Hypothesis chain: one hypothesis, `route_merge_ejection_chain`, trying to
coordinate whole-route absorption rather than single cross-route arc moves.

Code chain: one `local_search.py` VNS operator with bounded small-route source
selection, direct insertion, depth-one ejection, and telemetry.

Evidence chain: case 0/0/8, pair 0/2/14, median 0.0, CI [-1.5, 0.0], candidate
runtime saturation, and phase-positive but final-objective-loss classification.

Lifecycle result: abandoned/discarded. The clean-fork diversity claim is
partially valid, because this is not the same as R1's 2-opt reconnection or
R2/R3 repair guard. But it still re-enters local-search route absorption and
recreates runtime pressure. This is a useful negative lesson for future search:
route absorption needs a sharper opportunity detector before code generation.

## Cross-Branch Information Transfer

Observed behavior:

- Borrow: R4 borrows a mechanism-specific telemetry lesson
  (`lesson:d4dac8c01d7d1c18`) and uses it to require direct
  `route_merge_ejection_chain` telemetry.
- Avoid: R2 avoids R1's high-cost cross-route local-search path; R3 again avoids
  high-cost cross-route VNS; R4 avoids generic cross-route reconnect.
- Contrast: all four hypotheses contain contrast records; R2 contrasts
  destroy-repair early abort against local-search VNS, R3 contrasts scheduler
  selective-at-limit against always-on repair, and R4 contrasts local-search
  route absorption against route guard / destroy-repair.
- Preserve: R3 explicitly preserves R2's same-branch weak pair-positive lesson
  while changing the activation path.

New counters:

`campaign_summary.cross_branch_research_observability` reports:

- `policy=proposal_observability_only`
- `decision_input_policy=excluded_from_decision_features`
- `observable_step_count=4`
- `cross_branch_map_seen_count=4`
- `branch_lesson_usage_satisfied_count=4`
- `borrowed_lesson_count=1`
- `avoided_lesson_count=3`
- `contrasted_lesson_count=6`
- `preserved_same_branch_lesson_count=1`
- `clean_fork_contrast_satisfied_count=4`
- `weak_positive_transfer_count=1`
- `same_branch_refinement_allowance_count=1`

These counters are directionally credible because they match the hypothesis
outputs. They are not fully auditable yet because the same block reports
`branch_lesson_record_count=0` and `branch_lesson_usage_requirement_count=0`,
and each step's `step_visibility_audit.cross_branch_research_visibility` says
`status=missing`. In other words, the summary-level detector is seeing lesson
usage in proposal artifacts, but durable per-step `branch_lesson.v1` records
are absent or not connected to the step visibility audit.

Did sibling lessons change choices? Yes for R2 and R3, partly for R4.

- R2's mechanism choice changed because of R1: from broad local-search
  reconnection to repair-time route-limit handling.
- R3 changed because of R2: it kept the route-count idea but moved it into
  selective scheduler activation.
- R4 changed in telemetry discipline but remained in a nearby local-search
  route-absorption family, so the lesson effect was weaker.

Is usage merely formalized filling? No. The mechanism choices and code locations
change in response to the lesson text. The weakness is not formalism in the LLM
output; it is the durability/audit layer and some repeated local-search
attraction despite negative runtime evidence.

## Scion v3 Boundary Check

The run is aligned with the v3 decision boundary:

- `scion-architecture-v3.md` states that LLM output is tainted, must pass
  Contract -> Verification -> Protocol -> Safe Feature Extractor, and Decision
  reads only `DecisionFeatures`.
- `campaign_summary.observability_value_counts.decision_features_excluded_count=4`.
- `campaign_summary.runtime_evidence_policy_counts.decision_features_excluded_count=4`.
- Every runtime policy inspected sets `proposal_guidance_only=true` and
  `decision_features_excluded=true`.
- `cross_branch_research_observability.policy=proposal_observability_only` and
  `decision_input_policy=excluded_from_decision_features`.
- Candidate intent visibility is also proposal-only and decision-excluded.
- Decisions are consistent with deterministic protocol metrics: no promotion
  from LLM claims, phase telemetry, branch lesson text, or runtime-only signals.

The generic core / problem boundary is also acceptable in this run. The
candidate code changes are all inside experiment candidate policy files:
`policies/baseline_modules/local_search.py`,
`policies/baseline_modules/destroy_repair.py`, and
`policies/baseline_modules/scheduler.py` under the campaign artifacts. There is
no evidence that CVRP/ALNS/VNS semantics were pushed into Scion generic core.
Cross-branch lessons were used as proposal visibility and quality guidance, not
as Decision inputs.

## Research Quality Assessment

Context quality is sufficient for small-scope algorithm research:

- Hypothesis prompts saw problem semantics, research surfaces, active solver
  facts, active solver map receipts, current champion code, search memory,
  cross-branch map, branch lesson context, and accumulated feedback.
- Code prompts saw current target files, active algorithm facts, integration
  files, and rules. They produced mechanically plausible patches that passed
  contract/verification/smoke.
- The research is not conservative in the bad sense. The agent created four
  nontrivial solver-design mechanisms, including one same-branch refinement and
  two clean-fork local-search mechanisms. The new gate did not collapse behavior
  into pure compliance.

Research weaknesses:

- The agent still gravitates back to local-search route manipulation after R1
  showed runtime saturation and no case wins. R4 is different enough to pass a
  diversity check, but not different enough to erase the underlying runtime
  risk.
- `branch_lesson_usage_context` truncation appears by R3/R4. At 8R, this may
  reduce the quality of sibling lesson use or bias the model toward recent /
  high-surface lessons.
- Runtime evidence is repeatedly low/cached or saturated. The framework handles
  this correctly as proposal guidance only, but the research loop still spends
  candidate effort on mechanisms that create runtime pressure.
- Case-level signal remains absent. Pair-level weak positives are useful for
  branch-local exploration, not for quality claims.

## Must-Fix and Should-Fix

Must-fix before treating an 8R run as research-quality evidence:

1. Make `branch_lesson.v1` durability auditable. The summary currently reports
   `branch_lesson_record_count=0` while counting usage as satisfied. Persist the
   records or rename/scope the counter so it does not imply durable records that
   are absent.
2. Connect per-step visibility audit to the global counters. It is inconsistent
   for all `steps[].step_visibility_audit.cross_branch_research_visibility` to
   be `missing` while global `cross_branch_map_seen_count=4` and lesson usage
   counts are nonzero.
3. Prevent or summarize `branch_lesson_usage_context` truncation before 8R.
   R3/R4 already show truncation at 4R; 8R will amplify this.

Should-fix before a larger research run:

1. Add a sharper route-absorption/local-search saturation lesson that pushes the
   agent toward opportunity detectors or cheaper trigger predicates before
   generating another local-search route-merge mechanism.
2. Reduce repeated summary-only file-read planner calls. They are not severe,
   but R4's repeated already-observed reads and low cache hit rate show
   avoidable overhead.
3. Consider surfacing case-level positive/negative examples more compactly in
   the branch lesson context. R3's branch card has useful case-level detail
   (`A-n54-k7`, `E-n101-k8`, `P-n101-k4`), but the model should get that signal
   without expanding the lesson context until it truncates.

## 8R Recommendation

Recommended next step: fix the durable lesson observability issues first, then
run 8R.

If the team needs a quick continuation, run 8R as a framework smoke/stress test,
not as algorithm research acceptance. Acceptance criteria for that 8R should be:

- `branch_lesson_record_count` is nonzero when lesson usage is counted, or the
  report clearly distinguishes prompt-visible lesson usage from durable records.
- Step-level visibility audit records cross-branch lesson visibility for every
  counted step where the map was visible.
- No `branch_lesson_usage_context` truncation, or a compacted lesson summary
  with explicit truncation-safe semantics.
- Pair-level weak positives can drive one same-branch refinement, but two
  same-branch no-case-win candidates should park or fork, as happened here.
- No Decision input contains cross-branch lesson text; all such data remains
  proposal-only and decision-excluded.

Bottom line: this 4R passes the post-P1 smoke for proposal-level usage and v3
Decision boundary preservation. It does not yet pass as a fully auditable
branch-lesson observability implementation because durable lesson records and
step-level visibility audits disagree with the summary counters. Fix that before
using 8R as stronger evidence.
