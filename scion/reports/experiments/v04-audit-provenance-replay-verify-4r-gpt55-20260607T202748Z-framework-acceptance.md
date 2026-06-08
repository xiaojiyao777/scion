# Fresh 4R Framework Acceptance Audit

Experiment:
`/home/clawd/research/scion-experiments/v04-audit-provenance-replay-verify-4r-gpt55-20260607T202748Z-4r-gpt55-20260607T202748Z-claw/campaign`

Audit date: 2026-06-07

Scope: independent read-only audit of the fresh 4R framework acceptance surface. Source code and tests were not modified.

Required design references read first:

- `/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md`
- `/home/clawd/research/or-autoresearch-agent/scion/reports/architecture-audit-v0.4/remediation-status.md`

Architecture baseline used for judgment: LLM outputs are tainted proposal data; Contract, Verification, Protocol, Safe Feature Extractor, and deterministic Decision boundaries must remain auditable and must not let proposal/tooling/runtime text directly decide promotion.

## Verdict

Overall result: PASS for fresh 4R framework acceptance.

Recommendation: proceed to 8R. No must-fix blocker was found in the inspected acceptance surfaces. The only caveat is representational: `agentic_session_trace_index.json` stores prompt manifest refs per trace under `sessions[].traces[]`, while tooling provenance digest/ref is carried in LLM trace audit provenance and session-level provenance rather than flattened onto each trace-index trace row.

## Acceptance Results

| Item | Result | Evidence summary |
|---|---|---|
| 1. Run validity/accounting | PASS | Wrapper exit 0; `run_status.json`, `status.json`, and `campaign_summary.json` all report `run_validity_status=valid`, complete requested rounds, `effective_rounds_completed=4`, `proposal_attempts_total=4`, `proposal_attempts_consumed=4`, `formal_screened_candidates=4`, `protocol_evaluated_candidates=4`, `quality_blocks=0`, and `protocol_stage_counts.screening=4`. DB has 4 formal `experiment` rows at `stage=screening`; the 4 `raw_metrics_ref` files exist and are all `stage=screening`, `selected_surface=solver_design`, with 72 total valid pairs and 0 failed pairs. |
| 2. Model and LLM trace | PASS | 30 LLM traces were found, all with `model=gpt-5.5`. Request-kind distribution: `tool_selection=17`, `hypothesis=5`, `hypothesis_target_intent=4`, `code=4`. The extra hypothesis call is one schema retry in session `21cd038b...`; session outputs show `schema_retry_feedback_count_total=1` and `code_retry_failure_count_total=0`. `quality_blocks=0`; no repair block or skipped stop evidence was found. |
| 3. Proposal/tooling provenance | PASS | All 17 tool-selection LLM traces have `prompt_manifest.artifact_ref` and complete `scion_audit_provenance` with non-empty `deterministic_prefetch_plan_id`, `tool_selection_ledger_digest`, and `tool_selection_ledger_ref`. `agentic_session_trace_index.json` has 30 trace rows and every trace row has `prompt_manifest_artifact_ref`. Session outputs carry non-`none` deterministic prefetch plan IDs in their `tool_selection_ledger`. Provenance IDs were not present in the model-visible selector prompt/system/tool-schema fields, supporting audit-only provenance. |
| 4. Candidate replay identity | PASS | All 4 screening audit payloads and all 4 `artifacts/formal_candidates/**/candidate.patch.json` artifacts have complete replay identity. Required keys are present: `problem_spec_hash`, `split_manifest_hash`, `seed_ledger_hash`, `patch_digest`, `patch_hash`, `selected_surface`, `protocol_version`, and `raw_metrics_ref`. Identity status is `complete`, `identity_degraded=false`, missing-key arrays are empty. Event payloads and candidate artifacts match on all required keys; `patch_digest == patch_hash`; raw metrics refs exist and selected surface matches `solver_design`. |
| 5. Case-level gate naming aliases | PASS | DB experiment rows preserve both legacy `screening_case_*` fields and explicit `screening_case_level_gate_*` aliases; all 4 rows match exactly. Observed case tuples: `(0,0,8,8)`, `(1,0,11,12)`, `(0,0,8,8)`, `(0,1,7,8)`. Pair aggregates remain distinct: `(0,0,16,16)`, `(4,1,19,24)`, `(0,0,16,16)`, `(3,4,9,16)`. Branch cards in `status.json` and `campaign_summary.json` render concrete lists as `case_level_positive_cases` / `case_level_negative_cases`; the abandoned branch correctly names `B-n31-k5.vrp` positive and `B-n52-k7.vrp` negative, without confusing them with gate aggregates. |
| 6. Fresh-runtime/runtime evidence decision influence | PASS | Runtime/fresh-champion evidence is visible as proposal/scheduler/gate observation metadata, not as a second promotion Decision. Raw metrics mark runtime evidence as `proposal_visibility_only=true` and `decision_features_excluded=true`. The fresh-champion case on branch `850a66e3` reports `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` and continues exploration rather than promoting. The only abandon decision is explained by objective/lifecycle/telemetry reason codes: `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`, `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`, and runtime diagnostic codes. No promotion occurred. |

## Accounting Notes

`proposal_attempts_total=4` is semantically correct as the number of consumed proposal/LLM candidate attempts that led to formal screened candidates. `formal_screened_candidates=4` and `protocol_evaluated_candidates=4` are also correct because all formal candidates reached Protocol at screening stage and no validation/frozen candidates appeared. `quality_blocks=0` is consistent with empty quality-block ledgers and with the DB/session evidence.

The DB event split is also internally coherent:

- `agentic_proposal_session`: 8 rows
- `experiment`: 4 rows, all screening
- `decision`: 4 rows
- `scheduler_result`: 4 rows

## Trace Notes

The 8 agentic sessions split into 4 `partial_hypothesis_only` pre-approval sessions and 4 completed code sessions. This matches the governed flow where a hypothesis is produced, awaits Contract approval, and then proceeds to code generation in a subsequent session.

The single schema retry did not consume a quality block and did not create a code repair retry. Completed code sessions all show `code_retry_failure_count=0`.

## Runtime/Decision Notes

Decision features contain structured runtime fields (`runtime_stats`, `runtime_guard_passed`, `runtime_guard_elapsed_ms`) and reason-code namespaces (`auxiliary_protocol_reason_codes`, `gate_observation_reason_codes`, `lifecycle_action_reason_codes`). The inspected decisions remain deterministic and reason-code based:

- `9eea8eca`: `continue_explore`, neutral/no-effect screening with runtime diagnostics.
- `850a66e3`: first `continue_explore` on weak signal; later `continue_explore` on fresh-champion-required runtime tie.
- `01006eff`: `abandon`, tied to screening failure and lifecycle archive codes, not a runtime-only secondary decision.

## Final Recommendation

Proceed to 8R. The fresh 4R run validates the accounting, model trace, provenance, replay identity, case-level naming, and runtime/decision separation surfaces required before a longer run.
