# Scion 12R CVRP Framework Control / Evidence Closure Analysis

Run root:

`/home/clawd/research/scion-experiments/v04-branch-transfer-fresh-replay-verify-rerun-12r-gpt55-12r-gpt55-20260608T092404Z-claw`

Baseline: `scion/design/scion-architecture-v3.md`.

Scope: read-only analysis. No experiment was started. No source code was changed.

## Executive Summary

This run is formally valid as a 12/12 screening run: the wrapper finished cleanly, `run_validity.status=valid`, `effective_rounds_completed=12`, and all 12 screening experiment rows have verification passed, metrics refs, and complete replay identity.

The main framework-control issue is not formal accounting; it is evidence closure. The max-round drain did execute one fresh runtime replay attempt, but replay could not run because the selected weak-positive branch no longer had replayable runtime state: `branch_workspaces`, `branch_hypotheses`, and checkpoint state did not contain the candidate, even though DB hypothesis and patch artifacts existed. This is a persistence/recovery boundary problem, not a scheduler selection failure.

Recommendation: do not run 20R as the next evidence-quality run until P0/P1 below are fixed or consciously waived. 20R will likely produce more formal rows, but fresh-runtime-required branches can still end in unresolved replay closure, and lifecycle/scheduler observability will remain ambiguous.

## v3 Boundary Used

The v3 architecture makes the control-plane standard explicit:

- LLM output is tainted proposal data only.
- Contract, Verification, Protocol, Scheduler, Decision, Lineage, and Artifact persistence are deterministic framework responsibilities.
- Decision Layer should read only safe features, not free text or proposal-layer guidance.
- Artifact/Lineage must make hypothesis -> code -> verification -> protocol -> decision auditable and replayable.
- Runtime isolation requires a per-branch workspace, but evidence closure still needs durable references when a later scheduler action needs to replay.

These boundaries are the basis for the findings below.

## 1. Run Validity / Accounting

Verdict: valid 12/12 formal screening run, with accounting caveats in field naming.

Observed status:

- `run_status.json`: `campaign_exit_status=complete`, `completed_requested_rounds=true`, `last_stop_reason=max_rounds_exhausted`, `run_validity_status=valid`.
- `campaign/status.json`: `requested_rounds=12`, `effective_rounds_completed=12`, `screened_rounds=12`, `formal_screened_candidates=12`, `protocol_stage_counts.screening=12`, validation/frozen = 0.
- DB: 12 `experiment` rows with `stage=screening`; all have `verification_passed=True`, `telemetry_guard_failed=0`, `raw_metrics_ref` populated, and `audit_payload_json.replay_identity.status=complete`.
- DB: no proposal block or fresh replay is counted as a formal candidate.

Formal screening rows:

| row | branch | hypothesis | case W/L/T | pair W/L/T | decision |
|---:|---|---|---:|---:|---|
| 3 | `8e213e1b` | `3f3e4669` | 1/0/7 | 4/2/10 | continue |
| 10 | `8e213e1b` | `fa1e8a50` | 0/0/8 | 2/2/12 | continue |
| 15 | `8e213e1b` | `c0e946f4` | 0/1/7 | 2/3/11 | abandon |
| 20 | `e4b00114` | `97b53164` | 0/0/12 | 1/1/22 | continue |
| 28 | `e4b00114` | `625ba2ef` | 0/0/8 | 0/0/16 | continue |
| 33 | `e4b00114` | `872e39ee` | 1/0/7 | 3/1/12 | continue |
| 41 | `e4b00114` | `e4ea9fd2` | 0/1/7 | 3/3/10 | abandon |
| 46 | `da22cb9e` | `b5c23cc2` | 0/0/8 | 0/0/16 | continue |
| 54 | `c2d10bb6` | `b0c2006f` | 0/0/8 | 0/0/16 | continue |
| 59 | `c2d10bb6` | `b151baaa` | 0/0/8 | 0/0/16 | continue |
| 64 | `d3f1fa68` | `70280ba5` | 0/0/8 | 1/3/12 | abandon |
| 69 | `52a00dbd` | `0737548d` | 0/0/8 | 3/1/12 | continue |

Accounting reconciliation:

- `campaign_steps=16`.
- 12 counted formal screenings.
- 3 non-counted proposal quality blocks.
- 1 non-counted lifecycle/proposal reroute block in summary accounting.
- `proposal_attempts=15` / `proposal_attempts_consumed=15` corresponds to 12 formal candidates + 3 proposal blocks.
- `proposal_attempts_total=16` appears to mirror campaign step total, so the name is misleading because it includes a non-proposal lifecycle/scheduler step. This is observability debt, not a validity failure.

Conclusion: 12/12 formal is real and effective. The run is not a validation/frozen evidence run; it is a 12-screening campaign invocation.

## 2. Fresh Runtime Replay Root Cause

The final `last_result` is:

`attempt_kind=fresh_runtime_replay`, `action=replay`, `counts_toward_max_rounds=false`, `reason=fresh runtime replay missing workspace,hypothesis`, `failure_stage=fresh_runtime_replay`, `formal_protocol_evaluated=false`.

Selected branch:

`52a00dbd-63a1-4742-9f4f-507544f883f7`

The branch card and branch DB state show:

- `status=explore`
- `last_screening_feedback_tier=weak_positive`
- `branch_code_status=discarded`
- `candidate_code_retained=false`
- `best_quality_checkpoint_id=null`
- `last_valid_checkpoint_id=null`
- `fresh_runtime_required=true`
- `fresh_runtime_pending=false`
- `fresh_runtime_followup.closure_status=blocked_missing_candidate_state`
- `fresh_runtime_followup.detail=fresh runtime replay missing workspace,hypothesis`

The evidence did exist in durable partial form:

- Hypothesis row exists for `0737548d-00a2-4545-9312-b40213ed268a`.
- Formal candidate patch artifact exists:
  `artifacts/formal_candidates/52a00dbd/screening-0737548d-00a2-4545-9312-b40213ed268a-e09f6ae0fe3eef2f/candidate.patch.json`
- `artifacts/formal_candidates/index.jsonl` links the branch, hypothesis, patch digest, and artifact ref.
- Experiment row 69 has complete `replay_identity` with code hash, patch hash, problem spec hash, split hash, seed hash, protocol version, and raw metrics ref.

But executable replay state was missing:

- `campaign/workspaces/` only contains checkpoint workspaces for `8e213e1b` and `e4b00114`; no `52a00dbd` workspace or checkpoint exists.
- `campaign/archive/` has archived code for abandoned branches `8e213e1b`, `e4b00114`, and `d3f1fa68`; no `52a00dbd`.
- Source inspection of `run_fresh_runtime_replay_step()` shows replay only uses in-memory maps:
  - `self.branch_workspaces.get(bid)`
  - `self.branch_hypotheses.get(bid)`
  - `self.branch_current_hypothesis.get(bid)`
  - `self.branch_patches.get(bid)`
- If `workspace`, `hypothesis`, or `hypothesis_record` is missing, it closes the marker as `blocked_missing_candidate_state` and does not reconstruct from DB/artifacts.

Root cause classification:

- Not scheduler condition: scheduler selected `fresh_champion_runtime_replay_followup`.
- Not replay drain boundary: drain executed one accepted replay attempt.
- Not total lack of persistent evidence: DB hypothesis, metrics, replay identity, and patch artifact exist.
- Primary issue: replay requires volatile candidate state and has no recovery path from durable DB/artifacts.
- Secondary issue: candidate workspace/checkpoint retention policy discards weak-positive/no-promotion candidate code before replay closure, unless a checkpoint-retention condition fires.

## 3. Max-Round Drain / Status Observability

Fresh replay did run inside the max-round drain.

Evidence:

- Row 69: 12th formal screening, `continue_explore`.
- Row 71: scheduler result for row 69, `counts_toward_max_rounds=true`, action `create_branch`, reason `plateau_reroute_clean_fork`.
- Row 72: extra scheduler result, `attempt_kind=fresh_runtime_replay`, `counts_toward_max_rounds=false`, reason `fresh_champion_runtime_replay_followup`.
- `campaign_loop.fresh_runtime_replay_drain`: `attempts=2`, `executed=1`, `skipped=1`, `limit=4`, `stopped_reason=no_fresh_runtime_replay_pending`.

Why top-level fields looked absent:

- `campaign/status.json` has `campaign_loop.fresh_runtime_replay_drain*`.
- It does not have top-level `fresh_runtime_replay_drain_status`, `fresh_runtime_replay_drain_result`, or `fresh_runtime_replay_drain_last_result` fields.
- Top-level `last_result` is the failed replay result, while the drain summary's `last_result` is the subsequent skip result (`attempt_kind=other`, `action=skip`, `scheduler_reason=effect_diagnostic_followup`).

Observability problem:

- There are two "last result" surfaces with different meanings:
  - top-level `last_result`: last accepted replay step, failed due to missing candidate state.
  - `campaign_loop.fresh_runtime_replay_drain.last_result`: final drain attempt, skipped because no pending replay remained after marker closure.
- This is easy to misread as "no drain happened" or "drain succeeded by no-op".

Conclusion: drain executed, but status layout makes it hard to distinguish "executed and failed closure" from "no pending replay".

## 4. Lifecycle Policy / Secondary Decision Risk

Question checked: whether `last_result` or step records contain `decision_layer_source=lifecycle_policy` with `counts_toward=true`.

Finding:

- No `decision_layer_source=lifecycle_policy` was found in DB `experiment_events` or status JSON.
- Top-level `last_result`: `decision_layer_source=null`, `counts_toward_max_rounds=false`.
- However, scheduler_result rows still contain `attempt_kind=branch_lifecycle_policy` with `counts_toward_max_rounds=true` for three abandoned formal screenings:
  - row 17: `8e213e1b`, `soft_abandon: SCREENING_FAIL_WIN_RATE`
  - row 43: `e4b00114`, `soft_abandon: SCREENING_FAIL_WIN_RATE`
  - row 66: `d3f1fa68`, `soft_abandon: SCREENING_FAIL_WIN_RATE`
- There is also one `branch_lifecycle_policy` row with `counts_toward_max_rounds=false` for a proposal/schema block path.

Interpretation:

- The specific prior anti-pattern `decision_layer_source=lifecycle_policy + counts_toward=true` was not observed.
- But the framework still labels some counted scheduler_result records as `attempt_kind=branch_lifecycle_policy`, even when the counted thing is the underlying formal screening that was already evaluated by protocol/decision.
- The corresponding experiment/decision records do contain safe-feature decision outputs: `screened_experiment_effective=true`, gate reason codes, and lifecycle action reason codes.
- This is probably intended accounting, but the `attempt_kind` label is risky: it can imply lifecycle policy made a counted decision, when lifecycle should be finalizer/state-transition policy after deterministic Decision.

Recommendation: keep lifecycle reason codes in `decision_features_json.lifecycle_action_reason_codes`, but rename or split scheduler_result attempt kind:

- `attempt_kind=screening`, `finalizer_policy=branch_lifecycle_policy`, `counts_toward=true`, or
- `attempt_kind=branch_lifecycle_policy`, `counts_toward=false`, with a separate link to the counted screening row.

This matters for v3 because lifecycle policy must not look like a second Decision Layer.

## 5. Branch Lesson Usage / Quality Blocks

There were 3 quality blocks, all pre-protocol and non-counted.

1. `8e213e1b`, loop step 2:
   - Category: proposal / agent quality block.
   - Reason: `branch_lesson_usage_semantic_mismatch`.
   - The candidate included `branch_lesson_usage`, but it did not match required lesson ids, changed dimensions, or concrete target/action/mechanism linkage.
   - Assessment: reasonable gate. This protects cross-branch learning from becoming free-text or self-justifying rationale. It aligns with v3's "LLM text is tainted" boundary. It may still need better prompt repair because the failure message is long and schema-heavy.

2. `e4b00114`, loop step 6:
   - Category: contract boundary failure.
   - Reason: target-intent binding mismatch: selected mechanism `route_compaction_activation_schedule`, formal mechanism `route_compaction_postrepair`.
   - Assessment: reasonable gate. This prevents the proposal engine from silently changing the selected target between intent and formal hypothesis. It is a control-plane integrity check, not over-strict research gating.

3. `da22cb9e`, loop step 12:
   - Category: agent_quality_blocked.
   - Reason: algorithm smoke failure, `_SimulatedAnnealing` missing `observe_segment`, plus object-model misuse guidance.
   - Assessment: agent code quality problem. Gate is appropriate because it blocked a tainted candidate before formal protocol.

Across successful formal proposals:

- `branch_lesson_usage_present_count=12`.
- `branch_lesson_usage_satisfied_count=12`.
- `clean_fork_contrast_satisfied_count=12`.
- This suggests the gate is not generally impossible or overly tight. The block rate is acceptable for a 12R run.

Caveat:

- Status has two different cross-branch observability scopes: one copied summary under `status.json` reports `branch_lesson_usage_requirement_count=0` due to `status_step_history_not_available`, while `campaign_summary.json` reports the richer scope. This is another observability inconsistency, not a quality gate failure.

## 6. Priority Fixes Before 20R

### P0 - Fresh Replay Must Be Recoverable From Durable Evidence

Fresh runtime replay must not depend only on volatile in-memory candidate state.

Required behavior:

- Given branch id + hypothesis id + replay identity + formal candidate patch artifact, reconstruct or materialize a replay workspace.
- If reconstruction is impossible, report the precise missing durable artifact, not generic `workspace,hypothesis`.
- Persist the replay closure as `blocked_missing_replay_materialization` versus `blocked_missing_in_memory_state`.

Acceptance:

- A branch with `fresh_runtime_required=true` and complete `formal_candidate_patch_artifact_ref` can run replay after max-round drain even when the original live workspace was discarded.

### P0 - Checkpoint / Retention Policy for Fresh-Runtime-Required Branches

If a screening result sets `fresh_runtime_required=true`, do not discard the candidate workspace/hypothesis before replay closure, or immediately checkpoint it.

Acceptance:

- Branch card with `fresh_runtime_required=true` must have either:
  - live workspace + current hypothesis in runner state, or
  - checkpoint id / materializable artifact ref sufficient for replay.

### P1 - Split Drain Result Surfaces

Expose drain status at a stable top-level or explicitly document nesting.

Recommended fields:

- `fresh_runtime_replay_drain.status`
- `fresh_runtime_replay_drain.executed_count`
- `fresh_runtime_replay_drain.accepted_replay_last_result`
- `fresh_runtime_replay_drain.final_attempt_last_result`
- `fresh_runtime_replay_drain.unresolved_closures`

Acceptance:

- A user can tell from one status object whether replay was not selected, selected and succeeded, selected and failed, or selected then closed due to missing state.

### P1 - Clarify Lifecycle Accounting Labels

Avoid counted scheduler rows that appear to make lifecycle-policy decisions.

Acceptance:

- Counted formal screenings remain `attempt_kind=screening`.
- Lifecycle/finalizer action is represented as metadata, not as the counted attempt kind.
- Any lifecycle-only/proposal block remains `counts_toward_max_rounds=false`.

### P2 - Proposal Attempt Naming Cleanup

`proposal_attempts_total=16` is confusing because it matches campaign steps rather than `proposal_attempts_consumed=15`.

Acceptance:

- Rename or add fields:
  - `campaign_step_total`
  - `proposal_attempts_consumed`
  - `formal_candidate_attempts`
  - `non_counted_control_steps`

### P2 - Quality Block Repair UX

The quality blocks are mostly justified, but the branch lesson mismatch message is too large and policy-dense for efficient repair.

Acceptance:

- Each proposal block emits compact machine-readable reason codes plus a short actionable repair checklist.

## 7. 20R Decision

Do not treat these fixes as required for every exploratory run. But if the goal of 20R is framework acceptance or evidence-closure validation, P0 should be fixed first.

Rationale:

- 12/12 formal screening validity is already acceptable.
- The unresolved fresh runtime replay means runtime-related weak positives can still be left in a closed-but-not-replayed state.
- More rounds will likely increase the number of branches requiring fresh champion runtime evidence.
- Because replay cannot currently reconstruct from durable artifacts, 20R may amplify the same closure failure rather than prove the control plane.

Minimum acceptable waiver for running 20R now:

- Label it as search/proposal exploration only, not framework evidence-closure acceptance.
- Predefine that fresh runtime replay failures caused by `blocked_missing_candidate_state` are known invalid closure evidence.
- Do not use runtime weak-positive outcomes from such branches as promotion or validation rationale.

