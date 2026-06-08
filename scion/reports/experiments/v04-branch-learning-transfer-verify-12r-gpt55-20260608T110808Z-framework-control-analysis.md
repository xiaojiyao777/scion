# Scion v0.4 CVRP 12R Framework Control Analysis

Experiment path:
`/home/clawd/research/scion-experiments/v04-branch-learning-transfer-verify-12r-gpt55-12r-gpt55-20260608T110808Z-claw/campaign`

Generated from read-only inspection of `run_status.json`, `status.json`, `campaign_summary.json`, `scion.db`, `agentic_sessions`, `llm_traces`, and metrics references. No source code was modified.

Architecture baseline: `/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md`. I apply the v3 boundary throughout: LLM outputs are tainted proposal material; Contract, Verification, Protocol, and Safe Feature extraction must mediate anything used for deterministic decisions; Decision may read only deterministic `DecisionFeatures`. Cross-branch proposal lessons are acceptable as tainted proposal visibility, but must remain excluded from Decision input.

## 1. Verdict

This 12R run is accounting-valid and mostly control-valid: requested/effective/screening rounds reconcile exactly, all 12 formal candidates passed Contract and Verification, no quality blocks or branch lifecycle policy blocks were counted, and no validation/frozen promotion path was reached.

The run is not yet a clean basis for 40R. There are no P0 blockers, but there are P1 issues before scaling:

1. `candidate_intent_counts` classifies all 12 candidates as `observability_candidate`, even though most were algorithmic solver changes. This is inconsistent with the actual hypotheses and can distort scheduler/lifecycle interpretation.
2. Runtime evidence is structurally weak: 11/12 low cached champion, 10/12 runtime aggregate excluded, 6/12 fresh champion required. The framework correctly excludes this from DecisionFeatures, but `fresh_runtime_replay_drain` executed 0 replays and ended `not_selected_no_pending`, so the run keeps accumulating runtime-pressure guidance without resolving it.
3. `last_result` still labels the terminal soft-abandon path as `attempt_kind=branch_lifecycle_policy` and `decision_layer_source=lifecycle_policy`. Evidence shows it did not create an extra counted lifecycle round, but the naming still looks like lifecycle policy is issuing decisions and should be clarified before larger runs.

Recommendation: continue to 20R only as a controlled framework-validation run with explicit monitoring of these P1s. Do not use 40R as a scientific search run until the intent classification and fresh runtime replay behavior are fixed or deliberately accepted with an audit note.

## 2. Run Validity And Accounting

Run wrapper:
- `campaign_exit_status=complete`
- `run_complete=true`
- `run_completeness_status=complete`
- `run_validity_status=valid`
- `wrapper_exit_status=0`
- `last_stop_reason=max_rounds_exhausted`
- started `2026-06-08T11:08:09Z`, ended `2026-06-08T12:24:53Z`

Accounting reconciliation:
- requested rounds: 12
- total rounds: 12
- campaign steps: 12
- counted experiment steps: 12
- effective rounds completed: 12
- screened rounds / screened experiments: 12
- formal screened candidates: 12
- protocol evaluated candidates: 12
- protocol stage counts: screening 12, validation 0, frozen 0
- proposal attempts total: 12
- proposal attempts consumed: 12
- quality blocks: 0
- quality block ledger count: 0
- branch lifecycle policy blocks: 0
- active slot blocked attempts: 0
- scheduler active slot blocked attempts: 0
- model repair attempts/failures: 0
- telemetry repair attempts: 0
- telemetry failed experiments: 0
- non-effective screening count: 0

`fresh_runtime_replay_drain`:
- attempts: 1
- executed: 0
- skipped: 1
- blocked_count: 0
- status: `not_selected_no_pending`
- stopped_reason: `no_fresh_runtime_replay_pending`
- counts_toward_max_rounds: false
- decision_features_excluded: true
- final skip reason: scheduler selected `create_new` / `explore_new` with reason `runtime_evidence_completeness_clean_fork`, not `replay_existing`

Interpretation: round accounting is correct. The replay drain did not corrupt accounting. The concern is semantic: six candidates were marked fresh-champion-required, but the drain did not perform a replay. That means runtime uncertainty stayed as proposal guidance/pressure rather than being resolved.

## 3. LLM Trace And Cache Summary

All 100 LLM traces use `model=gpt-5.5`; all are `ok=true`.

Trace counts:
- `hypothesis_target_intent`: 12
- `hypothesis`: 15
- `tool_selection`: 61
- `code`: 12

Extra hypothesis calls occurred in rounds 4, 8, and 11, where the proposal loop made two `hypothesis` calls before final approval. These were not counted as extra experiment rounds and did not affect proposal_attempts_total.

Token/cache summary from llm traces:
- total calls: 100
- total prompt tokens: 2,244,917
- total output tokens: 55,494
- cache read tokens: 76,032
- cache miss tokens: 2,168,885
- overall cache hit rate: about 3.39%
- by kind: code 12 calls / 341,586 prompt / 0 cache read; hypothesis 15 calls / 707,160 prompt / 3,456 cache read; tool_selection 61 calls / 796,266 prompt / 72,576 cache read; hypothesis_target_intent 12 calls / 399,905 prompt / 0 cache read

Cache usage was low. That is not a success criterion here; the important result is that all traces were gpt-5.5 and successful.

## 4. Context, Tooling, And Prompt Visibility

Agentic sessions:
- 24 sessions total: one hypothesis session and one code session per formal candidate.
- Hypothesis sessions are `partial_hypothesis_only` with `termination_reason=hypothesis_awaiting_approval`, which is expected because code generation is split into the following session.
- Code sessions are `completed`.
- Every code session has a non-null `deterministic_prefetch_plan_id`.

Tool observation ledger:
- Every session output has an `observation_ledger`.
- Observation counts range from 11 to 16 per session output.
- For all 24 session outputs, every observation in the ledger has `rendered_visibility_flag=true`.
- Transcripts show tool observations recorded for required preface, deterministic prefetch, planner-selected reads, schema/permission previews, contract preview, and algorithm smoke.
- Repeated source reads were mostly returned as compact read receipts rather than duplicating payloads. This is a good anti-overload behavior.

Prompt visibility ledger:
- Across 100 traces, visibility totals were: full 1426, truncated 13, omitted 0, summary 0.
- The 13 truncated entries were all in hypothesis traces; no prompt-visible entry was omitted.
- Code traces had 27-28 visible entries each, all full in the inspected code trace.

Context sufficiency and overload:
- Hypothesis context was rich: problem summary, active solver facts, surface/interface, algorithm files/slices, operator registry, memory, and screening/runtime feedback where applicable.
- Code context was sufficient and focused: approved hypothesis, target file, surface/interface, branch state, screening/runtime feedback, contract preview, and smoke preview.
- Some hypothesis traces had one truncated section, so context is near the upper bound. This is P2 unless truncation starts removing critical lesson/feedback content.

Skipped stop:
- I found expected `stop_reason=required_context_satisfied` markers in transcripts and expected skipped unit/regression checks because no test paths are configured.
- I did not find evidence of an abnormal skipped stop that caused a round to bypass code, contract, verification, or protocol.

## 5. Per-Round Framework Process

All 12 formal candidates were screening-stage candidates with `contract_passed=True`, `verification_passed=True`, telemetry guard not failed, complete replay identity, and runtime guard passed on `tiny_canary.json`. `V3_unit_tests` and `V4_regression_tests` were skipped in every round because no configured unit/regression test paths exist; the heavy adapter consistency, feasibility, and objective checks passed.

### Round 1

- Branch `554f27f5`, hypothesis `940a9b54`
- Mechanism: `route_count_penalized_repair`
- Action/file: modify `policies/baseline_modules/destroy_repair.py`
- LLM calls: target_intent 1, hypothesis 1, tool_selection 8, code 1
- Tool observations: hypothesis 27, code 26
- Code prefetch plan: `63c2bbbad6bed4bc`
- Code prefetch: `memory.query`, `context.read_branch_state`, `context.read_surface`, `context.read_algorithm_file`, `feedback.query_screening`
- Screening: 1 win / 0 losses / 7 ties, total 8; median_delta 0.0, CI [-0.25, 0.5]
- Runtime: 16/16 runtime pairs in DecisionFeatures; runtime guard passed, candidate/champion about 1.01x on canary
- Decision: `continue_explore`
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `BOTH_RUNTIME_BUDGET_SATURATION`
- Interpretation: valid marginal positive signal, not promotable. Same-branch exploration continued correctly.

### Round 2

- Branch `554f27f5`, hypothesis `27f02143`
- Mechanism: `route_count_penalized_repair`
- Action/file: modify `policies/baseline_modules/destroy_repair.py`
- LLM calls: target_intent 1, hypothesis 1, tool_selection 2, code 1
- Tool observations: hypothesis 29, code 24
- Code prefetch plan: `b277318da7066d5d`
- Code prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_branch_state`
- Screening: 1 win / 1 loss / 6 ties, total 8; median_delta 0.0, CI [0.0, 2.5]
- Runtime: runtime_pairs 0/16 in DecisionFeatures due runtime confidence/exclusion; runtime guard passed
- Decision: `continue_explore`
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`
- Interpretation: valid follow-up; evidence retained but runtime aggregate excluded. No framework block.

### Round 3

- Branch `554f27f5`, hypothesis `ec748698`
- Mechanism: `route_count_penalized_repair`
- Action/file: modify `policies/baseline_modules/destroy_repair.py`
- LLM calls: target_intent 1, hypothesis 1, tool_selection 2, code 1
- Tool observations: hypothesis 29, code 24
- Code prefetch plan: `7911d142fdedf20c`
- Code prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_branch_state`
- Screening: 1 win / 1 loss / 6 ties, total 8; median_delta 0.0, CI [0.0, 0.0]
- Runtime: runtime_pairs 0/16; runtime guard passed
- Decision: `continue_explore`
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`
- Interpretation: third same-mechanism pass produced no stronger evidence. Plateau/runtime pressure later pushed scheduler toward clean forks, which is reasonable.

### Round 4

- Branch `8d706f9c`, hypothesis `fab3a548`
- Mechanism: `route_merge_lookahead_vns`
- Action/file: modify `policies/baseline_modules/local_search.py`
- LLM calls: target_intent 1, hypothesis 2, tool_selection 3, code 1
- Tool observations: hypothesis 36, code 23
- Code prefetch plan: `585e3594caaca293`
- Code prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_algorithm_file`, `context.read_branch_state`
- Screening: 0 wins / 0 losses / 8 ties, total 8; median_delta 0.0, CI [0.0, 0.0]
- Runtime: runtime_pairs 0/16; runtime guard passed
- Decision: `continue_explore`
- Reason codes: `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`
- Interpretation: no objective signal. Framework did not promote or abandon; it marked fresh champion runtime need as proposal/audit guidance.

### Round 5

- Branch `992bc9d5`, hypothesis `bb75bb76`
- Mechanism: `stagnation_reheat_acceptance`
- Action/file: modify `policies/baseline_modules/acceptance.py`
- LLM calls: target_intent 1, hypothesis 1, tool_selection 4, code 1
- Tool observations: hypothesis 29, code 24
- Code prefetch plan: `efa2e6938f8dcaf6`
- Code prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_algorithm_file`, `context.read_branch_state`
- Screening: 0 wins / 0 losses / 8 ties, total 8; median_delta 0.0, CI [0.0, 0.0]
- Runtime: runtime_pairs 0/16; runtime guard passed
- Decision: `continue_explore`
- Reason codes: `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`
- Interpretation: no objective effect; runtime evidence not allowed to stand alone. Correct v3 boundary behavior.

### Round 6

- Branch `07efe6aa`, hypothesis `1fbaf846`
- Mechanism: `search_observability_bridge`
- Action/file: create `policies/baseline_modules/telemetry.py`
- LLM calls: target_intent 1, hypothesis 1, tool_selection 7, code 1
- Tool observations: hypothesis 21, code 26
- Code prefetch plan: `8bcd7d9e0b1204cc`
- Code prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_branch_state`, `context.read_surface`, `context.read_algorithm_file`
- Screening: 0 wins / 0 losses / 12 ties, total 12; median_delta 0.0, CI [0.0, 0.0]
- Runtime: runtime_pairs 16/24; runtime guard passed
- Decision: `continue_explore`
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `SCREENING_NEUTRAL_SIGNAL_CONTINUE`, `SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`, `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `BOTH_RUNTIME_BUDGET_SATURATION`
- Interpretation: behaviorally neutral observability candidate. It successfully preserved behavior but did not improve objective. This is the only round whose "observability_candidate" label clearly matches the hypothesis.

### Round 7

- Branch `c8153cba`, hypothesis `07ff07bc`
- Mechanism: `quota_repair_activation_bridge`
- Action/file: modify `policies/baseline_modules/scheduler.py`
- LLM calls: target_intent 1, hypothesis 1, tool_selection 6, code 1
- Tool observations: hypothesis 28, code 26
- Code prefetch plan: `4f329a5fc9a136d6`
- Code prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_branch_state`, `context.read_surface`, `context.read_algorithm_file`
- Screening: 0 wins / 0 losses / 8 ties, total 8; median_delta 0.0, CI [0.0, 0.0]
- Runtime: runtime_pairs 0/16; runtime guard passed
- Decision: `continue_explore`
- Reason codes: `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`
- Interpretation: no objective effect and explicit telemetry-zero diagnostic. Framework kept this diagnostic outside promotion.

### Round 8

- Branch `ed9c31c0`, hypothesis `92b11457`
- Mechanism: `route_limit_seed_diversification`
- Action/file: modify `policies/baseline_modules/construction.py`
- LLM calls: target_intent 1, hypothesis 2, tool_selection 6, code 1
- Tool observations: hypothesis 37, code 26
- Code prefetch plan: `6e4473e8a59aabaa`
- Code prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_branch_state`, `context.read_surface`, `context.read_algorithm_file`
- Screening: 0 wins / 0 losses / 8 ties, total 8; median_delta 0.0, CI [0.0, 0.0]
- Runtime: runtime_pairs 0/16; runtime guard passed
- Decision: `continue_explore`
- Reason codes: `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`
- Interpretation: no objective signal; second hypothesis call did not create an extra accounting attempt. Context/tool loop remained controlled.

### Round 9

- Branch `16fafdc4`, hypothesis `c8fbc083`
- Mechanism: `operator_effect_observability_bridge`
- Action/file: modify `policies/baseline_modules/scheduler.py`
- LLM calls: target_intent 1, hypothesis 1, tool_selection 5, code 1
- Tool observations: hypothesis 28, code 25
- Code prefetch plan: `0ac4d78119330b33`
- Code prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_branch_state`, `context.read_surface`, `context.read_algorithm_file`
- Screening: 0 wins / 0 losses / 8 ties, total 8; median_delta 0.0, CI [0.0, 0.0]
- Runtime: runtime_pairs 0/16; runtime guard passed
- Decision: `continue_explore`
- Reason codes: `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`
- Interpretation: observability-style scheduler bridge, no objective effect. Kept as exploration, not promoted.

### Round 10

- Branch `ee49d575`, hypothesis `dede182e`
- Mechanism: `three_route_ejection_chain_vns`
- Action/file: modify `policies/baseline_modules/local_search.py`
- LLM calls: target_intent 1, hypothesis 1, tool_selection 6, code 1
- Tool observations: hypothesis 28, code 26
- Code prefetch plan: `d1dd65e390ecc837`
- Code prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_branch_state`, `context.read_surface`, `context.read_algorithm_file`
- Screening: 0 wins / 1 loss / 7 ties, total 8; median_delta -0.75, CI [-3.0, 0.0]
- Runtime: runtime_pairs 0/16; runtime guard passed
- Decision: `abandon`
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`, `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`, `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`
- Interpretation: abandon is justified by negative screening. `abandon_accounting.kind=soft_lifecycle_archive` and `counts_toward_hard_abandon=false`, so this is lifecycle bookkeeping attached to the counted screening result, not a separate hard abandon round.

### Round 11

- Branch `3fb8782b`, hypothesis `3869cc5e`
- Mechanism: `demand_clustered_seed_construction`
- Action/file: modify `policies/baseline_modules/construction.py`
- LLM calls: target_intent 1, hypothesis 2, tool_selection 6, code 1
- Tool observations: hypothesis 37, code 27
- Code prefetch plan: `2e8667a6f1f0ebe5`
- Code prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_branch_state`, `context.read_surface`, `context.read_algorithm_file`
- Screening: 0 wins / 0 losses / 8 ties, total 8; median_delta 0.0, CI [0.0, 0.0]
- Runtime: runtime_pairs 0/16; runtime guard passed
- Decision: `continue_explore`
- Reason codes: `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`
- Interpretation: no effect but branch remains active. No abnormal block.

### Round 12

- Branch `3331f7c7`, hypothesis `15a58c1a`
- Mechanism: `bounded_slack_regret_repair`
- Action/file: modify `policies/baseline_modules/destroy_repair.py`
- LLM calls: target_intent 1, hypothesis 1, tool_selection 6, code 1
- Tool observations: hypothesis 29, code 26
- Code prefetch plan: `1732ffe1ea8ad8af`
- Code prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_branch_state`, `context.read_surface`, `context.read_algorithm_file`
- Screening: 0 wins / 2 losses / 6 ties, total 8; median_delta 0.0, CI [-10.0, 0.0]
- Runtime: runtime_pairs 0/16; runtime guard passed
- Decision: `abandon`
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`, `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`
- Interpretation: abandon is justified by case-level losses. This is the `last_result` and carries the lifecycle-policy naming concern described below.

## 6. Gate, Scheduler, And Lifecycle Behavior

Contract/verification:
- All formal candidates passed static contract and verification.
- `contract_diagnostics_json` was empty for inspected screening rows.
- Runtime guard passed every round.
- Unit/regression configured-test checks were skipped every round because no test paths were configured; adapter consistency, feasibility, objective, and runtime guard checks carried the main verification burden.

Quality gate:
- `quality_blocks=0`.
- `quality_block_ledger=[]`.
- No evidence that the quality gate blocked valid research.

Protocol:
- All 12 formal candidates reached screening protocol.
- No candidate reached validation or frozen because none passed screening enough to justify it.
- This is normal. There is no evidence of preview/contract/verification preventing a promising candidate from progressing.

Scheduler:
- Active-slot blocks: 0.
- Final active slots: max 3, used 2, available 1.
- Active branch ids: `554f27f5`, `3fb8782b`.
- Parked lineage ids: `07efe6aa`, `c8153cba`, `ed9c31c0`.
- Scheduler reasons were mostly `explore_new`, `refine_active`, or runtime-evidence-completeness clean forks.
- No evidence of scheduler deadlock or active-slot starvation.

Material difference:
- The scheduler pushed clean forks after repeated low/no-effect runtime-pressure signals.
- That is reasonable at 12R scale, but because all candidates were classified as observability candidates, material-difference/lifecycle statistics should not be treated as fully reliable until that classification bug is fixed.

## 7. Evidence Lifecycle And v3 Boundary

Runtime evidence policy:
- total runtime evidence policy records: 12
- runtime signal role: `tie_break_supporting_signal` 1, `audit_or_proposal_guidance_only` 11
- low cached champion: 11
- runtime aggregate excluded: 10
- fresh champion required: 6
- standalone optimization signal false: 12
- decision features excluded: 12

This is good v3 boundary behavior: weak runtime evidence did not drive promotion as a standalone deterministic signal. It remained audit/proposal guidance.

Observability value:
- applicable: 12/12
- observed: 12/12
- decision_features_excluded: 12

This shows the framework saw observability as available and prompt-visible, but it also exposes the candidate-intent bug: 12/12 candidates were labeled observability even when the proposed change was direct algorithm search logic.

Cross-branch proposal lessons:
- `last_result.proposal_session_ref.branch_lesson_records` uses `source=proposal_only`.
- Lesson records explicitly set `decision_input_policy=excluded_from_decision_features`.
- This matches v3: tainted cross-branch lessons can influence proposal visibility/novelty pressure but should not enter deterministic Decision.

## 8. Last Result Lifecycle Risk

`status.last_result` compact facts:
- `action=create_branch`
- `attempt_kind=branch_lifecycle_policy`
- `decision=abandon`
- `decision_layer_source=lifecycle_policy`
- `counts_toward_max_rounds=true`
- `formal_protocol_evaluated=true`
- `reason=soft_abandon: SCREENING_FAIL_WIN_RATE`
- decision reason codes include `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`, `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`
- diagnostic reason codes include runtime budget saturation only

What looks safe:
- Accounting shows `branch_lifecycle_policy_blocks=0`.
- `non_counted_lifecycle_steps=0`.
- The abandon happened on a formal screening result, not as an extra non-counted lifecycle step.
- `abandon_accounting.kind=soft_lifecycle_archive`.
- `counts_toward_hard_abandon=false` in lifecycle bookkeeping.

Residual risk:
- `decision_layer_source=lifecycle_policy` conflicts with the desired mental model that Decision owns decisions and lifecycle policy only records terminal bookkeeping.
- `action=create_branch` plus `decision=abandon` is semantically confusing.
- This is not evidence of a P0 double-decision in this run, but it is a P1/P2 observability/naming issue because future audits may not be able to distinguish a real lifecycle decision from post-decision bookkeeping.

## 9. Issues

### P0

None found.

No evidence of invalid run accounting, skipped counted rounds, model mismatch, failed Contract/Verification, promotion from tainted LLM text, runtime evidence entering DecisionFeatures as standalone promotion signal, or unaccounted lifecycle blocks.

### P1

1. Candidate intent classification is wrong or too broad.
   - Evidence: `candidate_intent_counts={"quality_candidate":0,"observability_candidate":12,"diagnostic_candidate":0,"unknown":0}`.
   - Actual rounds include route-count repair, VNS route merge, acceptance reheat, construction diversification, ejection chain, and slack regret repair. Only rounds 6 and 9 are clearly observability-centered.
   - Risk: scheduler/lifecycle/material-difference logic may be optimizing around the wrong candidate class.

2. Fresh runtime replay is not resolving fresh-champion-required pressure.
   - Evidence: `fresh_champion_required_count=6`, `runtime_aggregate_excluded_count=10`, `low_cached_champion_count=11`, but drain `executed=0`, `status=not_selected_no_pending`.
   - Risk: longer runs will accumulate proposal pressure from weak runtime evidence while never converting it into fresh comparable evidence.

3. Lifecycle/soft-abandon naming still resembles a second decision layer.
   - Evidence: `last_result.attempt_kind=branch_lifecycle_policy`, `decision_layer_source=lifecycle_policy`, `decision=abandon`.
   - In this run accounting remained correct, but the names blur v3 boundaries.

### P2

1. Hypothesis context is near capacity.
   - Evidence: 13 prompt visibility entries were truncated, all in hypothesis traces; omitted entries were 0.
   - Risk is low now because source and ledgers remained visible, but this should be monitored in 20R/40R.

2. Unit/regression checks are configured as skipped.
   - Evidence: every verification payload has `V3_unit_tests` and `V4_regression_tests` passed with details `skipped: no unit_test_path configured` and `skipped: no regression_test_path configured`.
   - Heavy adapter/objective/feasibility checks passed, so this is not a current blocker, but it weakens verification depth.

3. Runtime cache confidence dominates proposal guidance.
   - Evidence: runtime evidence is often low cached champion and aggregate-excluded.
   - This is partly expected from cached champion use, but it reduces the value of runtime-oriented guidance unless replay is fixed.

## 10. Continue Or Repair First

20R:
- Acceptable only as a controlled framework-validation continuation.
- Add explicit monitoring assertions for candidate intent distribution, fresh runtime replay pending/executed/closure counts, and `last_result` lifecycle fields.
- Treat search outcomes as exploratory, not as strong scientific evidence, until runtime replay semantics are resolved.

40R:
- Not recommended before P1 fixes.
- The control loop will probably remain accounting-valid, but the run would be expensive while carrying distorted candidate-intent labels and unresolved low-confidence runtime guidance.

Minimum before 40R:
1. Fix or document candidate intent classifier so algorithmic candidates are not all counted as observability candidates.
2. Decide whether fresh champion runtime replay should actually run when `fresh_champion_required` appears, or explicitly rename/adjust the policy so "required" means proposal-only pressure.
3. Rename or restructure `last_result` lifecycle fields so lifecycle archive bookkeeping is not presented as `decision_layer_source=lifecycle_policy`.
4. Add a regression assertion around accounting invariants: `proposal_attempts_total == effective_rounds_completed == screened_rounds` for this no-repair/no-block scenario, and lifecycle bookkeeping must not create extra counted rounds.

