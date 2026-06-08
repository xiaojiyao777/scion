# Scion v0.4 framework observability audit

Experiment:
`/home/clawd/research/scion-experiments/v04-branch-lesson-refcache-verify-12r-gpt55-20260608T041237Z-claw/campaign`

Audit date: 2026-06-08

Scope: framework control flow, run accounting, quality block handling, cross-branch research observability, proposal context persistence, lifecycle decision semantics, and runtime/fresh-champion observability. Source code was read only for behavior interpretation. No source files were modified.

## Verdict

This run is valid and complete for a 12-round screening experiment. The framework is good enough to enter a 20R follow-up if the follow-up is explicitly treated as another screening/observability run, not as a promotion-readiness run.

Two mechanisms should still be fixed or tightened before longer promotion-oriented experiments:

- P1: runtime/fresh-champion replay pressure. `low_cached_champion` appears in 11/12 screened steps and `fresh_champion_required` in 8/12. This is not polluting DecisionFeatures, but it leaves many outcomes as runtime-advisory/unclear and creates pending follow-up pressure that will compound in 20R+.
- P2: terminal `status.json` cross-branch observability is misleading. `campaign_summary.json` has complete step-history observability, but final `status.json` reconstructs only a last-status/loop-accounting view and reports `branch_lesson_usage_present_count=0`, `satisfied_count=0`.
- P2: proposal retry guidance for the one quality block failed closed correctly, but the retry feedback path is internally inconsistent: the actual blocker was `existing_file_create_new_rejected`, while the stored retry feedback focused on `C11_expected_telemetry` and told the model to preserve action/target.

No evidence was found that branch lesson records leaked raw proposal text into the counted step summaries or contaminated `DecisionFeatures`.

## Primary artifacts

- Campaign summary: `campaign_summary.json`
- Final status snapshot: `status.json`
- Wrapper status: `run_status.json`
- Formal candidate ledger: `artifacts/formal_candidates/index.jsonl`
- Agentic session index: `agentic_sessions/agentic_session_index.json`
- Agentic trace index: `agentic_sessions/agentic_session_trace_index.json`
- Quality-block session: `agentic_sessions/b44a4072-69b6-45c8-b552-bd7f7befbc87/output.json`
- Quality-block transcript: `agentic_sessions/b44a4072-69b6-45c8-b552-bd7f7befbc87/transcript.json`

## 1. Run validity and round accounting

The run is valid:

- `campaign_summary.json`: `run_complete=true`, `run_completeness_status=complete`, `run_validity.status=valid`, `requested_rounds=12`, `effective_rounds_completed=12`, `completed_requested_rounds=true`.
- `campaign/run_status.json`: `status=finished`, `campaign_exit_status=complete`, `wrapper_exit_status=0`, `started_at=2026-06-08T04:12:38Z`, `ended_at=2026-06-08T05:28:19Z`.
- `artifacts/formal_candidates/index.jsonl`: 12 rows.

The `proposal_attempts=13` vs `formal_screened_candidates=12` difference is explained by one non-counted proposal quality block:

- `campaign_summary.json`: `total_rounds=13`, `proposal_attempts=13`, `proposal_attempts_consumed=13`, `formal_screened_candidates=12`, `protocol_evaluated_candidates=12`, `quality_blocks=1`.
- `accounting_reconciliation.max_rounds_semantics`: requested rounds limit `effective_rounds_completed`; proposal, repair, lifecycle, and scheduler attempts are reported separately.
- `quality_block_ledger[0]`: round/loop step 4, branch `2b3dbde6-e138-4715-9beb-ce8f5cdbd839`, `attempt_kind=proposal_block`, `failure_stage=proposal`, `counts_toward_max_rounds=false`.

Counted screened steps are 12:

| Round | Attempt kind | Branch | Session | Metrics |
|---:|---|---|---|---|
| 1 | screening | `2ac12b1d-8f54-47b1-a8c9-77a5282d221c` | `a3f91cc9-5e8f-4ebc-987d-70f79c38d4a5` | `metrics/eec6d0b6-cdb4-44c0-b09b-85d806821fb9.json` |
| 2 | screening | `4a1aafe0-65cd-4b2e-902e-6dfb7a784255` | `58bbd8af-b860-4192-b6ca-b66995d9fe09` | `metrics/0533fc1e-dc81-49ae-93eb-2fd4a2695d34.json` |
| 3 | branch_lifecycle_policy | `4a1aafe0-65cd-4b2e-902e-6dfb7a784255` | `ead2ebc0-1aab-4c83-b0bb-b4007be128a2` | `metrics/211e7f2e-9be3-47b0-910b-6c19d7fa99ce.json` |
| 5 | screening | `2b3dbde6-e138-4715-9beb-ce8f5cdbd839` | `3826197d-1172-4025-a81d-0380a3ff2117` | `metrics/8827a77f-f606-45ef-b4ce-1482ba7aad56.json` |
| 6 | screening | `2b3dbde6-e138-4715-9beb-ce8f5cdbd839` | `2d32643e-72b8-4f85-99be-c2f2624f0a53` | `metrics/efc5007a-03f7-439b-872e-87d703ab232b.json` |
| 7 | branch_lifecycle_policy | `886e3850-ca34-46c9-9ccb-2458463070c9` | `666fd97b-40f4-4b06-aa11-12ccf595b719` | `metrics/1708a1c4-65f0-4485-8a89-2e4a02eb1c76.json` |
| 8 | screening | `b80205c9-09e8-4e5e-8371-1a2a2f724365` | `9e43f25f-871e-4f83-8b3d-27ac8108dc41` | `metrics/46e75f8f-854d-4007-9335-de1b1d05c487.json` |
| 9 | screening | `b80205c9-09e8-4e5e-8371-1a2a2f724365` | `19acdc6c-0143-4a3a-8212-74349f515935` | `metrics/0de5474e-fff4-413c-a644-5865047bd8d0.json` |
| 10 | screening | `b80205c9-09e8-4e5e-8371-1a2a2f724365` | `b6c4629a-8fd0-4535-bec3-30b328a78edf` | `metrics/0b993c58-8a25-489c-b0c2-699cb1f8a41a.json` |
| 11 | screening | `b80205c9-09e8-4e5e-8371-1a2a2f724365` | `a2ce43cb-2efc-4727-bcfe-79277563654d` | `metrics/62f89cc3-e478-495d-85e9-12135a760fb5.json` |
| 12 | screening | `6a471676-774f-4ddf-bb9d-17009fa8ae6c` | `5abbe580-d8db-407f-93e6-cdd572c4f73c` | `metrics/06f3462a-4f23-4f61-b997-ded9c5e7ee0d.json` |
| 13 | screening | `44e902fd-d67e-4bc5-ab84-6f3bb21b16b5` | `91e58f54-7450-409c-93a7-765c9f5f06e8` | `metrics/783223ca-9cd8-493d-af9c-d5c0c1f6122c.json` |

Note: rounds 3 and 7 are `attempt_kind=branch_lifecycle_policy`, but both are also `screened_experiment=true`, `screened_experiment_effective=true`, and `counts_toward_max_rounds=true`; they are counted formal screening outcomes, not extra non-counted lifecycle attempts.

## 2. Quality/proposal block

The single proposal block is:

- Round/loop step: 4
- Branch: `2b3dbde6-e138-4715-9beb-ce8f5cdbd839`
- Session: `b44a4072-69b6-45c8-b552-bd7f7befbc87`
- Output: `agentic_sessions/b44a4072-69b6-45c8-b552-bd7f7befbc87/output.json`
- Transcript: `agentic_sessions/b44a4072-69b6-45c8-b552-bd7f7befbc87/transcript.json`
- Trace index entry: `agentic_sessions/agentic_session_trace_index.json`
- LLM traces:
  - `llm_traces/20260608T043348059448_hypothesis_target_intent_f9c57836b8_dbc14ae0.json`
  - `llm_traces/20260608T043353027041_hypothesis_a8050e8034_cc65981a.json`
  - `llm_traces/20260608T043414841203_hypothesis_c63fb3c420_267a0e08.json`

The proposal attempted:

- `action=create_new`
- `target_file=policies/baseline_modules/destroy_repair.py`
- mechanisms: `slack_seeded_repair`, `repair_portfolio_integration`

The block reason is correct and contract-safe:

- `output.json`: `status=failed`, `termination_reason=hypothesis_generation_failed`, `failure_category=contract_boundary_failure`.
- `self_check_preview_full_0003.json`: `proposal.schema_preview` failed with `target_action_guard.reason=existing_file_create_new_rejected`.
- `self_check_preview_full_0004.json`: `proposal.target_permission_preview` failed with the same issue.
- The permission preview explicitly says an existing file requires `modify exact_replace` with `source_digest`; `create_new` is only for genuinely new files.

This is a reasonable fail-closed Contract/proposal boundary. The tainted proposal never reached formal screening, did not produce a formal candidate artifact, and did not count toward max rounds.

There is, however, a P2 guidance defect in the retry path. The stored retry feedback artifact:

- `agentic_sessions/b44a4072-69b6-45c8-b552-bd7f7befbc87/scratch/hypothesis_schema_retry_feedback_0001.json`

records `failure_code=C11_expected_telemetry` and says this is a schema/accounting repair, with a retry constraint to preserve prior `action` and `target_file`. The actual self-check artifacts for both attempts show the decisive failure was `existing_file_create_new_rejected`. The model did receive target-action repair hints in the previews, but the named retry feedback channel emphasized the wrong failure class and preserved the invalid action. This likely contributed to the repeated `create_new` on an existing file.

Acceptance implication: fail-closed behavior is good; retry-feedback prioritization should be fixed so target/action violations override telemetry-only retry instructions.

## 3. Cross-branch observability: summary vs status

`campaign_summary.json` reports complete cross-branch research observability:

- `cross_branch_research_observability.observable_step_count=12`
- `source_counts.step_history_total=13`
- `source_counts.protocol_screening_steps=12`
- `source_counts.context_record_count=13`
- `branch_lesson_record_count=27`
- `branch_lesson_usage_requirement_count=12`
- `branch_lesson_usage_present_count=12`
- `branch_lesson_usage_satisfied_count=12`
- `branch_lesson_usage_missing_block_count=0`
- `cross_branch_map_seen_count=12`

`campaign/status.json` has a narrower final snapshot:

- `cross_branch_research_observability.status_scope=loop_accounting_inferred`
- `step_history_scope=none`
- `source_counts.step_history_total=0`
- `source_counts.context_record_count=1`
- `source_counts.status_loop_accounting_inferred_count=12`
- `observable_step_count=12`
- `cross_branch_map_seen_count=12`
- `branch_lesson_usage_requirement_count=1`
- `branch_lesson_usage_present_count=0`
- `branch_lesson_usage_satisfied_count=0`

Source inspection explains the difference:

- `scion/scion/core/evidence_recording/summary.py` builds summary observability from full `steps` plus `_proposal_context_records_from_steps(steps)`.
- `scion/scion/core/evidence_recording/status.py` builds status observability from branch rows, the last status result, current progress, and in-flight protocol only; if no observable steps are present, it infers `observable_step_count` and `cross_branch_map_seen_count` from completed loop counters.

Classification: not an evidence propagation defect in the durable summary, and not DecisionFeatures contamination. It is a final-status observability bug/scope leak: the status file advertises terminal cross-branch counters but cannot compute branch lesson usage from full step history, so it displays present/satisfied as zero. For operators, this is misleading because the final status looks like a failure while `campaign_summary.json` proves the 12 counted proposal contexts were satisfied.

Recommended fix: either have terminal `status.json` reuse the summary-grade step-history observability after completion, or mark branch lesson usage counters as `not_available` when `step_history_scope=none` instead of rendering zeros.

## 4. Proposal session refs and DecisionFeatures boundary

All 12 counted screened steps contain both `branch_lesson_records` and `branch_lesson_usage_requirement` under `proposal_session_ref`.

Per-counted-step persistence:

| Round | Attempt kind | Branch | Session | Lesson records | Requirement | Required for | Excluded from DecisionFeatures |
|---:|---|---|---|---:|---|---|---|
| 1 | screening | `2ac12b1d-8f54-47b1-a8c9-77a5282d221c` | `a3f91cc9-5e8f-4ebc-987d-70f79c38d4a5` | 1 | true | `sibling_nearby_attempt` | true |
| 2 | screening | `4a1aafe0-65cd-4b2e-902e-6dfb7a784255` | `58bbd8af-b860-4192-b6ca-b66995d9fe09` | 2 | true | `sibling_nearby_attempt` | true |
| 3 | branch_lifecycle_policy | `4a1aafe0-65cd-4b2e-902e-6dfb7a784255` | `ead2ebc0-1aab-4c83-b0bb-b4007be128a2` | 5 | true | `clean_fork_new_branch` | true |
| 5 | screening | `2b3dbde6-e138-4715-9beb-ce8f5cdbd839` | `3826197d-1172-4025-a81d-0380a3ff2117` | 5 | true | `clean_fork_new_branch` | true |
| 6 | screening | `2b3dbde6-e138-4715-9beb-ce8f5cdbd839` | `2d32643e-72b8-4f85-99be-c2f2624f0a53` | 8 | true | `clean_fork_new_branch` | true |
| 7 | branch_lifecycle_policy | `886e3850-ca34-46c9-9ccb-2458463070c9` | `666fd97b-40f4-4b06-aa11-12ccf595b719` | 8 | true | `clean_fork_new_branch` | true |
| 8 | screening | `b80205c9-09e8-4e5e-8371-1a2a2f724365` | `9e43f25f-871e-4f83-8b3d-27ac8108dc41` | 8 | true | `clean_fork_new_branch` | true |
| 9 | screening | `b80205c9-09e8-4e5e-8371-1a2a2f724365` | `19acdc6c-0143-4a3a-8212-74349f515935` | 8 | true | `clean_fork_new_branch` | true |
| 10 | screening | `b80205c9-09e8-4e5e-8371-1a2a2f724365` | `b6c4629a-8fd0-4535-bec3-30b328a78edf` | 8 | true | `clean_fork_new_branch` | true |
| 11 | screening | `b80205c9-09e8-4e5e-8371-1a2a2f724365` | `a2ce43cb-2efc-4727-bcfe-79277563654d` | 8 | true | `clean_fork_new_branch` | true |
| 12 | screening | `6a471676-774f-4ddf-bb9d-17009fa8ae6c` | `5abbe580-d8db-407f-93e6-cdd572c4f73c` | 8 | true | `clean_fork_new_branch` | true |
| 13 | screening | `44e902fd-d67e-4bc5-ab84-6f3bb21b16b5` | `91e58f54-7450-409c-93a7-765c9f5f06e8` | 8 | true | `clean_fork_new_branch` | true |

The branch lesson record keys across counted steps are limited to:

- `schema_version`, `lesson_id`, `source`, `decision_input_policy`, `scope`, `lesson_role`, `lesson_type`, `maturity`, `source_branch_ids`, `required_response`, `reason_codes`.

The usage requirement keys are limited to structured ids, digest, requirement source, required flags, candidate branch/lesson ids, candidate lesson roles/types, required contrast dimensions, and visibility policy.

Search over counted `branch_lesson_records` and `branch_lesson_usage_requirement` found zero strings matching raw/hypothesis/rationale/summary/free-text patterns. The fields are structured ids/enums/reason codes, not raw LLM text.

DecisionFeatures boundary check:

- `cross_branch_research_observability.decision_input_policy=excluded_from_decision_features`.
- All counted `branch_lesson_usage_requirement.decision_features_excluded=true`.
- The current `DecisionFeatures` dataclass fields do not include `branch_lesson_records`, `branch_lesson_usage_requirement`, `branch_lesson_usage_present_count`, or cross-branch map counters.

Conclusion: no raw text leakage or DecisionFeatures pollution was found in the counted screening records.

## 5. Lifecycle and Decision semantics

There are two counted `branch_lifecycle_policy` abandon outcomes:

| Round | Branch | Session | Decision | Metrics | Key reason codes |
|---:|---|---|---|---|---|
| 3 | `4a1aafe0-65cd-4b2e-902e-6dfb7a784255` | `ead2ebc0-1aab-4c83-b0bb-b4007be128a2` | abandon | `metrics/211e7f2e-9be3-47b0-910b-6c19d7fa99ce.json` | `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`, `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`, `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA` |
| 7 | `886e3850-ca34-46c9-9ccb-2458463070c9` | `666fd97b-40f4-4b06-aa11-12ccf595b719` | abandon | `metrics/1708a1c4-65f0-4485-8a89-2e4a02eb1c76.json` | `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN` |

Both are formal screening outcomes, not separate non-counted lifecycle side effects:

- `screened_experiment=true`
- `screened_experiment_effective=true`
- `counts_toward_max_rounds=true`
- `non_counted_lifecycle_steps=0`
- `branch_lifecycle_policy_blocks=0`

Round 3 had `win_rate=0.0`, `median_delta=-1.0`, `gate_outcome=fail`, and low cached champion runtime. Round 7 had `win_rate=0.0`, `median_delta=0.0`, `gate_outcome=fail`, and low cached champion runtime. Both abandon decisions followed objective failure/zero-win evidence and did not stop the run from continuing to 12 effective rounds.

Conclusion: this run does not show the earlier "second decision" risk as a blocking defect. The lifecycle policy is visible in `attempt_kind` and reason codes, and the outcomes count as their corresponding screening attempts. Remaining P2 risk is semantic clarity: `attempt_kind=branch_lifecycle_policy` can look like a separate lifecycle attempt even though it is part of the counted screening outcome.

## 6. Runtime and fresh champion

Runtime/fresh-champion observability is the main remaining mechanism issue.

Aggregate fields:

- `runtime_evidence_policy_total=12`
- `low_cached_champion_count=11`
- `runtime_aggregate_excluded_count=11`
- `fresh_champion_required_count=8`
- `standalone_optimization_signal_false_count=12`
- `decision_features_excluded_count=12`
- runtime signal roles: `audit_or_proposal_guidance_only=11`, `tie_break_supporting_signal=1`
- `runtime_budget_diagnostic_count=12`

Per-counted-step runtime roles:

- Round 1 is the only `tie_break_supporting_signal`; runtime evidence confidence is high/sufficient enough for supporting signal only.
- Rounds 2, 5, 6, 9, 10, 11, 12, and 13 require fresh champion runtime.
- Rounds 3, 7, and 8 are low/cached or incomplete but do not set fresh champion required.

This did not directly interfere with promotion in this run because there were no promotion-worthy candidates: gates were fail/unclear with no accepted experiments, and runtime policy was marked visibility/proposal guidance only. The policy correctly excludes runtime-only evidence from DecisionFeatures.

However, the mechanism is not ready for long promotion-oriented runs without improvement. In final branch cards:

- Branch `b80205c9-09e8-4e5e-8371-1a2a2f724365` has `fresh_runtime_pending=true`, `fresh_runtime_required=true`, `last_screening_feedback_tier=weak_positive`.
- Branch `6a471676-774f-4ddf-bb9d-17009fa8ae6c` has `fresh_runtime_pending=true`, `fresh_runtime_required=true`, `last_screening_feedback_tier=quality_regression`.
- Most current heads are `low_cached_champion` with reason codes including `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, `SCREENING_RUNTIME_BUDGET_SATURATION`, and `CANDIDATE_RUNTIME_BUDGET_SATURATION`.

Recommended mechanism work before long promotion runs:

- Batch or schedule fresh champion replay when repeated cached champion evidence makes runtime aggregates unusable.
- Separate "runtime advisory only" from "must refresh before next same-family proposal" in scheduler state, so the proposal loop does not keep accumulating unresolved runtime debt.
- Consider warming champion runtime for the screening seed/case set at campaign start or after champion/checkpoint changes.
- Keep the existing DecisionFeatures exclusion policy; the problem is replay/scheduling, not Decision contamination.

## Acceptance conclusion

Accepted for a 20R screening/observability experiment with caveats.

The framework controls core safety boundaries correctly in this run:

- Run validity is complete and internally reconciled.
- 13 proposal attempts vs 12 formal screenings is correctly explained by one pre-protocol proposal block.
- The quality block failed closed at the Contract/proposal preview boundary.
- Counted proposal contexts persist branch lesson records and usage requirements for all 12 screened steps.
- Branch lesson usage is excluded from DecisionFeatures and shows no raw text leakage in counted summaries.
- Lifecycle abandon outcomes are accounted as counted screening outcomes and did not block effective research progress.

Required before longer promotion-oriented experiments:

- P1: fix or automate fresh champion runtime replay/cache refresh so 20R+ does not drown in `low_cached_champion`/`fresh_champion_required` ambiguity.
- P2: fix terminal `status.json` observability counters or mark them unavailable when only loop-accounting inference is available.
- P2: fix proposal retry feedback prioritization so target/action permission failures are not hidden behind telemetry/schema retry feedback.
- P2: clarify reporting language for `branch_lifecycle_policy` counted screening outcomes to avoid confusing them with extra non-counted lifecycle decisions.
