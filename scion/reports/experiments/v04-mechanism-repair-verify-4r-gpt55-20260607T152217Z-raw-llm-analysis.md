# Scion Raw LLM/Agentic Trace Audit

Run root: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw`

Report date: 2026-06-07

## 1. Run-Level Confirmation

### Requested configuration

The wrapper records the requested configuration in:

- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/command.txt`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/launch.env`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/run.log`

Confirmed launch facts:

| Item | Actual recorded value |
|---|---|
| Model env | `SCION_MODEL=gpt-5.5` |
| Endpoint env | `SCION_BASE_URL=http://127.0.0.1:8080` |
| Problem | `scion/problems/cvrp/problem.yaml` |
| Protocol/split/seeds | `scion/problems/cvrp/formal/{protocol.yaml,split_manifest.yaml,seed_ledger.yaml}` |
| Requested rounds | `--rounds 4`, `ROUNDS=4` |
| Time limit | `--time-limit-sec 10` |
| Proposal mode | `--agentic-proposal`, `AGENTIC_PROPOSAL=1` |
| Early stop | `--disable-early-stop`, `DISABLE_EARLY_STOP=1` |
| Agentic timeout | `--agentic-session-timeout-sec 900` |
| Git commit recorded by wrapper | `5c15532` |

The raw LLM trace files in `campaign/llm_traces/*.json` all record `model: "gpt-5.5"`, so the model field seen by Scion's LLM client matches the launch env.

### Completion status

The run did not complete the requested 4 rounds. The authoritative status files are:

- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/run_status.json`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/run_status.json`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/status.json`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/campaign_summary.json`

Key recorded status:

| Field | Value |
|---|---|
| `wrapper_exit_status` | `0` |
| `campaign_exit_status` | `incomplete` |
| `run_complete` | `false` |
| `completed_requested_rounds` | `false` |
| `run_validity_status` | `invalid_no_effective_rounds` |
| `run_completeness_status` | `interrupted_incomplete` |
| `last_stop_reason` | `circuit_breaker` |
| Start/end | `2026-06-07T15:22:19Z` to `2026-06-07T15:24:22Z` |
| Effective rounds completed | `0` |
| Formal screened candidates | `0` |
| Protocol evaluated candidates | `0` |
| Promoted/accepted experiments | `0` |

`run.log` gives the direct reason: after 3 consecutive agentic proposal failures, the campaign stopped with the circuit breaker. The repeated short error was `Invalid proxy API key`.

There is a minor accounting ambiguity in `campaign/status.json`: `attempt_breakdown.proposal_attempts_total` is `4` and `campaign_steps` is `4`, while `proposal_attempts`, `proposal_attempts_consumed`, `total_rounds`, and the actual agentic session count are `3`. For raw-trace interpretation, the durable artifact count is decisive: there are 3 failed agentic sessions and 6 failed LLM calls.

## 2. Raw Artifact Inventory

Main raw artifacts read:

- LLM traces: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/llm_traces/*.json`
- Agentic session index: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/agentic_sessions/agentic_session_index.json`
- Agentic trace index: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/agentic_sessions/agentic_session_trace_index.json`
- Per-session outputs: `campaign/agentic_sessions/{session_id}/output.json`
- Prompt manifests: `campaign/agentic_sessions/{session_id}/scratch/api_visible_prompt_manifest_*.json`
- Target-intent artifacts: `campaign/agentic_sessions/{session_id}/scratch/hypothesis_target_intent_0001.json`
- Session transcripts: `campaign/agentic_sessions/{session_id}/transcript.json`
- DB: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/scion.db`

Durable counts:

| Artifact kind | Count |
|---|---:|
| Agentic proposal sessions | 3 |
| LLM traces | 6 |
| `hypothesis_target_intent` calls | 3 |
| `hypothesis` calls | 3 |
| Code calls | 0 |
| Patch artifacts | 0 |
| Contract/verification/protocol artifacts | 0 |
| Smoke/preview evidence artifacts | 0 |
| DB `hypotheses` rows | 0 |

Every session stopped at `draft_hypothesis` / `hypothesis_generation_failed`, before formal hypothesis, code generation, patch preview, Contract, Verification, Canary, screening, validation, frozen, or promotion.

## 3. Cross-Attempt Failure Pattern

All 6 LLM calls failed with the same provider/API error:

`Error code: 401` with short message `Invalid proxy API key`.

The request policy for every trace was:

- `timeout_sec=60.0`
- `max_retries=2`
- `transient_max_retries=1`
- `sdk_max_retries=0`
- `max_tokens=16384`

Each trace records `llm_retry_summary.event_count=2`, `recovered_success=false`, and `error_categories={"LLMError": 2}`. The final visible error says the tool call failed after 3 attempts, which is consistent with the initial attempt plus 2 retries.

This is an endpoint/auth failure, not an algorithmic, schema, Contract, or proposal-quality failure.

## 4. Attempt 1: Session `29747e7a-1d9e-44b5-bdc2-94668109eace`

### Trace files

- Target-intent trace: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/llm_traces/20260607T152219574722_hypothesis_target_intent_7fc7f2ddaf_fbc20897.json`
- Hypothesis trace: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/llm_traces/20260607T152241047749_hypothesis_18024391ee_e8b867a2.json`
- Output: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/agentic_sessions/29747e7a-1d9e-44b5-bdc2-94668109eace/output.json`
- Prompt manifests:
  - `.../29747e7a-1d9e-44b5-bdc2-94668109eace/scratch/api_visible_prompt_manifest_0001_hypothesis_target_intent.json`
  - `.../29747e7a-1d9e-44b5-bdc2-94668109eace/scratch/api_visible_prompt_manifest_0002_hypothesis.json`

### Context quality

The prompt context was strong and exposure-controlled. The prompt visibility ledger reports no omitted or truncated sections:

- target-intent manifest: 31 entries, status counts `dedicated_projection=4`, `full=19`, `summary=8`, `truncated=0`, `omitted=0`
- hypothesis manifest: 34 entries, status counts `dedicated_projection=4`, `full=22`, `summary=8`, `truncated=0`, `omitted=0`

The first prompt included the necessary problem/surface/champion context:

- CVRP problem semantics and lexicographic objective policy.
- Only one active research surface: `solver_design`.
- Current champion entrypoint: `policies/baseline_algorithm.py::solve(...)`.
- Active algorithm facts with packet digest `2cfe98de174b5f615c07da173aa7843631621ccc807a46d0c47bdba320a8f531`.
- Active solver map receipts.
- Full visible reads for:
  - `policies/baseline_modules/destroy_repair.py`
  - `policies/baseline_modules/local_search.py`
  - `policies/baseline_modules/scheduler.py`
- Bounded scheduler slice: `cvrp.slice.scheduler.solve`.
- Tool observations from `context.list_surfaces`, `context.read_problem`, active solver design/map/call graph, operator registry, scheduler slice, and `memory.query`.

The prompt had no previous failure to include yet. There was no apparent missing branch/champion/surface/problem context.

### Agentic tool observations

`output.json` records 12 proposal tool steps and `124270` observation chars. The deterministic preface gathered:

- `context.list_surfaces`
- `context.read_problem`
- `context.list_algorithm_files`
- `context.read_active_solver_design`
- `context.read_solver_call_graph`
- `context.read_active_solver_map`
- 3 file reads for destroy/repair, local search, scheduler
- `context.read_operator_registry`
- `context.read_algorithm_slice`
- `memory.query`

The tool loop stopped with `required_context_satisfied`.

### LLM outcome and hypothesis output

The target-intent preflight failed with the 401 error, produced `hypothesis_target_intent_0001.json` with `status=fallback`, `fallback_to_current_flow=true`, and an empty `intent`.

The subsequent `hypothesis` call also failed with the same 401 error.

No hypothesis was produced:

- `hypothesis=null`
- `patch=null`
- `selected_surface=null`
- `target_file=null`
- `mechanism_ids=[]`
- `self_check.schema_valid=false`
- `self_check.contract_preview_passed=null`

### Framework action

DB `experiment_events` recorded:

- `agentic_proposal_session` with `status=failed`
- `proposal_fail` with `contract_result=skipped`, `verification_result=skipped`, `stage=proposal`
- `scheduler_result` with `result_action=create_branch`, `scheduler_slot=explore_new`, `scheduler_reason=new_exploration_slot_available`

The failure was stored as `contract_boundary_failure` / `schema_or_target_preview_failed`, even though the root cause was provider auth.

## 5. Attempt 2: Session `09c9feb8-fb05-4f7d-ba1c-d66aeac57b03`

### Trace files

- Target-intent trace: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/llm_traces/20260607T152301883451_hypothesis_target_intent_40c6784b4b_47bfe1c7.json`
- Hypothesis trace: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/llm_traces/20260607T152322016298_hypothesis_d60969f528_708a3ecf.json`
- Output: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/agentic_sessions/09c9feb8-fb05-4f7d-ba1c-d66aeac57b03/output.json`

### Context quality

This was a `context_profile=repair` session, but the context was again complete for algorithmic proposal work. The visibility ledger reports:

- target-intent manifest: 32 entries, `truncated=0`, `omitted=0`
- hypothesis manifest: 41 entries, `truncated=0`, `omitted=0`

Compared with attempt 1, repair-specific context was added:

- `agentic_resume_context`
- `campaign_search_memory`
- `exploration_coverage`
- `strategy_guidance`
- `agent_quality_feedback`
- `experiment_history_this_branch`
- `solver_design_boundary_control`
- `analysis_steps_follow_in_order`
- `do_not_claim_missing_near_field_mechanism_memory`

The raw prompt includes the previous failure summary under `previous_failure`, including the short 401 message. It also includes a warning that the campaign has failed proposal generation once and suggests checking output format requirements.

### Context pollution / misleading feedback

This attempt exposes the main framework defect in the run. The previous failure was a provider/auth failure, but repair context framed it as:

- `structured_output_retry_exhausted`
- `schema_or_target_preview_failed`
- `contract_boundary_failure`
- "Common causes: malformed JSON, schema violations"

That would mislead a functioning model toward schema repair even though no model response was ever received. It also pollutes proposal-only portfolio guidance by counting an endpoint failure as proposal/action history.

### Agentic tool observations

The agentic session again gathered 12 tools, `124424` observation chars, and stopped at `required_context_satisfied`. It also records "Loaded inherited APS observation ledger."

The active fact anchor remained stable:

- fact packet digest: `2cfe98de174b5f615c07da173aa7843631621ccc807a46d0c47bdba320a8f531`
- snapshot digest: `703914d3edaf27a46f3adb7d419a6dcd5cc7154ae6fd01c66ae8e50cf9842761`
- source tool: `context.read_active_solver_map`

### LLM outcome and hypothesis output

Both LLM calls failed with the same 401 error.

The target-intent artifact again has:

- `status=fallback`
- `fallback_to_current_flow=true`
- `intent={}`
- `decision_input=false`

The final session output again has:

- `hypothesis=null`
- `patch=null`
- `selected_surface=null`
- `target_file=null`
- `self_check.schema_valid=false`
- `contract_preview_passed=null`

### Framework action

DB events recorded a failed session, proposal failure, then scheduler result:

- `scheduler_slot=repair_diagnostic`
- `scheduler_reason=pending_retry_diagnostic_followup`
- `result_action=explore`
- `post_finalizer_actual_branch_action=continue_same_branch`
- `same_branch_refinement_selected=true`

This is reasonable if the failure is a proposal-quality issue, but harmful for endpoint/auth failures: retrying the same proposal path cannot repair the API key.

## 6. Attempt 3: Session `a8968fd0-b8a4-43f9-96cc-f7e9e3100f64`

### Trace files

- Target-intent trace: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/llm_traces/20260607T152342465801_hypothesis_target_intent_0b8017b1db_e3b79f6f.json`
- Hypothesis trace: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/llm_traces/20260607T152402604111_hypothesis_23a72f84f5_44fc4f9d.json`
- Output: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/agentic_sessions/a8968fd0-b8a4-43f9-96cc-f7e9e3100f64/output.json`

### Context quality

This was another `context_profile=repair` session. Prompt manifests report:

- target-intent manifest: 32 entries, `truncated=0`, `omitted=0`
- hypothesis manifest: 43 entries, `truncated=0`, `omitted=0`

The context included the same core algorithm facts and files as attempts 1-2, plus stronger repair guidance:

- `failure_pattern_warning`
- `failure_pattern_warning_2`
- larger `agent_quality_feedback`
- longer `experiment_history_this_branch`
- `cross_branch_research_map` with more pre-protocol failure summary

The prompt now carried two previous failed sessions. The `agent_quality_feedback` section listed both attempts as `schema_or_target_preview_failed` and repeated the 401 error.

### Context pollution / misleading feedback

The misclassification worsened in attempt 3:

- The prompt said there were 2 consecutive proposal failures and again suggested malformed JSON/schema as common causes.
- `Cross-Branch Research Map` listed pre-protocol failures as weak planning context.
- `Exploration Coverage` treated `NEW_FAMILY/create_new/proposal` as overused and suggested `modify`, despite no real hypothesis/action ever being generated by the model.
- `Portfolio guidance` pushed diversification away from an action/locus that was never actually proposed.

This is proposal-context pollution. It remains tainted and excluded from DecisionFeatures, but it can still degrade future research behavior once the endpoint works.

### Agentic tool observations

The session again gathered 12 tools and `124424` observation chars, with the same stable active fact packet and no truncation. The tool loop stopped at `required_context_satisfied`.

### LLM outcome and hypothesis output

Both LLM calls failed with 401. There was no hypothesis or patch.

The final target-intent artifact again records a fallback, not a formal proposal. `output.json` again records `self_check.schema_valid=false`, but that is a consequence of no structured LLM output, not a model schema mistake.

### Framework action

DB events recorded the failed session and proposal failure, then:

- `scheduler_slot=repair_diagnostic`
- `scheduler_reason=pending_retry_diagnostic_followup`
- `result_action=explore`
- `post_finalizer_actual_branch_action=continue_same_branch`

After this third consecutive LLM failure, `run.log` records the circuit breaker stop.

## 7. Experiment Result Summary

| Attempt | Session | Context profile | LLM calls | Result | Framework state/action |
|---:|---|---|---:|---|---|
| 1 | `29747e7a...` | `algorithm` | 2 failed | no hypothesis, no patch | proposal fail; scheduler selected new exploration branch |
| 2 | `09c9feb8...` | `repair` | 2 failed | no hypothesis, no patch | proposal fail; same branch diagnostic retry |
| 3 | `a8968fd0...` | `repair` | 2 failed | no hypothesis, no patch | proposal fail; same branch diagnostic retry; circuit breaker |

Final campaign state:

- One branch: `525d63a1-1a3c-460b-8b6d-83173bc006b1`
- Branch state: `explore`
- Branch code status: `clean`
- Failure codes: `["PROPOSAL", "PROPOSAL", "PROPOSAL"]`
- Mechanism ids: `[]`
- Evidence summary: `{}`
- Active slots: used `1` / max `3`

No candidate reached:

- formal hypothesis persistence
- code generation
- patch preview
- Contract
- Verification
- Canary
- screening
- validation
- frozen/holdout
- protocol decision
- promotion

This run is therefore invalid as a solver-quality experiment. Its value is exclusively runtime/LLM plumbing and context auditing.

## 8. Framework Defects and Optimization Points

### P0: Endpoint/auth failures must be classified as infrastructure, not proposal quality

The root cause is `401 Invalid proxy API key`. Scion persisted the failure as `contract_boundary_failure` and `schema_or_target_preview_failed`. This violates the operational meaning of those categories and pollutes later proposal feedback.

Recommended fix:

- Detect provider auth/connectivity/rate-limit categories before proposal self-check classification.
- Persist them as `infra_blocked:llm_auth` or equivalent.
- Do not count them as proposal/schema/Contract quality blocks.
- Do not render them as "malformed JSON/schema" repair guidance.

### P0: Preflight health check before expensive context/tool gathering

Each failed session still gathered 12 proposal tools and around 124k observation chars before making LLM calls. When the endpoint key is invalid, all that context work is wasted and can pollute branch state.

Recommended fix:

- Before agentic proposal sessions, perform a cheap LLM health probe against the configured `SCION_BASE_URL` and `SCION_MODEL`.
- Fail closed before tool gathering if auth fails.
- Record the probe artifact in run root/campaign status so the failure is immediately attributable.

### P0: Circuit breaker should stop on infrastructure class without creating repair attempts

The circuit breaker did stop after 3 consecutive LLM failures, but attempts 2 and 3 were framed as repair diagnostics. For auth failures, repair diagnostics cannot help.

Recommended fix:

- If failure class is provider auth, stop immediately or after one confirmation retry.
- Mark run as `invalid_infra_llm_auth` rather than consuming proposal attempts.
- Keep branch failure codes free of `PROPOSAL` for this class.

### P1: Proposal feedback should not learn portfolio/action lessons from no-output infra failures

Attempt 3's context showed "overuse create_new" and suggested `modify`, even though there was no hypothesis/action from the model. This can distort future search once LLM access is restored.

Recommended fix:

- Exclude no-output infra failures from `Cross-Branch Research Map`, `Exploration Coverage`, and portfolio diversification guidance.
- Only count action/locus coverage when a structured hypothesis exists, or clearly tag as host-selected pre-proposal path rather than model research action.

### P1: Separate transcript artifact is empty

All three `transcript.json` files contain `event_count=0` and `events=[]`, while the useful session timeline is in `output.json.compact_transcript`.

Recommended fix:

- Either write compact transcript events into `transcript.json`, or rename/mark the artifact as intentionally empty.
- The current state makes `transcript_artifact_ref` misleading for raw-trace audit.

### P1: Accounting fields are confusing around circuit-breaker termination

`campaign/status.json` reports `proposal_attempts_total=4` and `campaign_steps=4`, while durable sessions and consumed attempts are 3. This may be explainable by budget accounting, but it is not audit-obvious.

Recommended fix:

- Add explicit fields for `requested_rounds`, `effective_rounds_completed`, `agentic_sessions_started`, `llm_failure_streak`, `circuit_breaker_threshold`, and `round_budget_not_consumed_due_to_infra_stop`.
- Avoid names that imply a fourth actual proposal session when none exists.

### P2: Retry summary lacks enough provider-level detail

The traces preserve the final 401 error, but `llm_retry_events` summarize attempts without per-attempt error text. For auth failures this is less damaging, but for mixed transient failures it would slow audit.

Recommended fix:

- Store per-attempt provider status class and short error digest/category.
- Keep full sensitive payload redacted, but include enough structured classification for diagnosis.

## 9. Context Completeness Assessment

Despite the endpoint failure, Scion's prompt construction looked substantially better than older context-starvation patterns:

- Problem semantics were explicit.
- The active `solver_design` surface was explicit.
- Champion entrypoint and branch-owned algorithm boundary were explicit.
- Active solver facts were included as primary context, with digest/provenance.
- Full algorithm file reads for destroy/repair, local search, and scheduler were visible.
- Tool observations were bounded and separately projected.
- Repair attempts included previous session/failure context.
- Prompt visibility ledgers reported `truncated=0` and `omitted=0`.

Main caveat: the context was complete but misleading after the first failed call because infrastructure failure was converted into proposal/schema feedback.

## 10. Recommendation on Longer Runs

Do not start a longer round-count experiment from this configuration yet.

Minimum prerequisite fixes/config checks:

1. Fix or validate the OpenAI-compatible proxy credentials for `http://127.0.0.1:8080`.
2. Add a cheap pre-run LLM health probe that confirms the configured model can return a minimal structured tool response.
3. Reclassify provider auth/connectivity failures as infrastructure failures, not proposal/schema/Contract quality blocks.
4. Exclude no-output infra failures from proposal portfolio learning and agent-quality repair hints.
5. Make transcript artifacts non-empty or clearly deprecated in favor of `output.json.compact_transcript`.
6. Rerun a short 1R or 2R smoke first and require at least one complete path through hypothesis and code generation before any 4R/longer experiment.

After these are fixed, a 4R verification rerun is appropriate. A longer run should wait until a short rerun demonstrates:

- successful LLM calls,
- at least one formal hypothesis,
- code generation,
- Contract and Verification execution,
- and clear, non-polluted feedback propagation into the next attempt.

