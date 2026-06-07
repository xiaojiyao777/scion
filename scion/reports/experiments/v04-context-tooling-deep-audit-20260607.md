# Scion v04 Context / Tooling Deep Audit

Run root: `/home/clawd/research/scion-experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-claw`

Reference reports:

- `/home/clawd/research/or-autoresearch-agent/scion/reports/experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-analysis.md`
- `/home/clawd/research/or-autoresearch-agent/scion/reports/experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-retry-quality-audit.md`

Design baseline:

- `/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/AGENT_ONBOARDING.md`

Audit date: 2026-06-07.

Scope: context and tool-selection mechanisms in the 4R `gpt-5.5` run. This audit does not treat "many tools" as a presumed defect. It asks whether current information channels help the agent conduct solver research, and where the mechanism turns information acquisition into excess control flow.

## Executive Conclusion

The tool design is broadly justified and aligned with Scion v3: the agent needs controlled access to problem mechanics, active solver facts, code, branch state, screening/runtime feedback, cross-branch memory, schema/permission/contract previews, and smoke feedback. These channels are not optional if the agent is expected to do actual algorithmic research rather than fill prompt fields.

The main cost is not that tools exist. The cost is that `tool_selection` repeatedly asks the LLM to rediscover a mostly fixed inspection sequence, and each selection call carries a large catalog/context prompt. In this run, `tool_selection` was 94/116 LLM calls and 1,454,342 input tokens. Many hypothesis sessions followed the same pattern: `memory.query -> feedback.query_screening -> feedback.query_runtime -> stop`. Those calls produced useful context in later rounds, but the choice itself was often deterministic enough to prefetch or ledger without LLM deliberation.

Context is heavy. Prompt manifests show hypothesis prompts with tens of thousands of estimated prompt tokens from active solver map receipts, full algorithm reads, tool observations, active facts, analysis rules, and negative-memory guidance. Code prompts also include extensive governance/edit-protocol constraints. Some of this is necessary v3 boundary control. Some should be profile-gated by phase/failure mode, especially repair guidance, repeated full algorithm reads, large active solver map receipts, and raw tool observations once compact active facts already exist.

Evidence that the model spent effort satisfying framework rules is real but narrow: two code sessions failed because repair still introduced/increased `alns` telemetry under a hypothesis whose protected mechanism id was `route_limit_repair_bias`. That supports a framework-guidance/repair-loop issue. It does not prove that tooling prevented research: the hypotheses clearly used runtime/screening feedback to shift from broad local search to narrower local search, repair, scheduler gating, and construction diversification.

## Run-Level Statistics

Structured evidence used:

- `campaign/status.json`
- `campaign/agentic_sessions/agentic_session_trace_index.json`
- `campaign/llm_traces/*.json`
- `campaign/agentic_sessions/*/transcript.json`
- `campaign/scion.db`

Run accounting:

| Field | Value | Evidence |
|---|---:|---|
| Requested rounds | 4 | `campaign/status.json.accounting_reconciliation.requested_rounds` |
| Effective rounds completed | 4 | `campaign/status.json.accounting_reconciliation.effective_rounds_completed` |
| Proposal attempts total | 8 | `campaign/status.json.accounting_reconciliation.proposal_attempts_total` |
| Screened experiments | 6 | `campaign/status.json.accounting_reconciliation.screened_experiments` |
| Screened but not effective | 2 | `campaign/status.json.accounting_reconciliation.screened_not_effective` |
| Formal screened candidates | 4 | `campaign/status.json.accounting_reconciliation.formal_screened_candidates` |
| Protocol evaluated candidates | 4 | `campaign/status.json.accounting_reconciliation.protocol_evaluated_candidates` |
| Quality blocks | 4 | `campaign/status.json.accounting_reconciliation.quality_blocks` |
| Model repair failures | 2 | `campaign/status.json.campaign_loop.failure_categories.model_repair_failed` |
| Agentic sessions | 14 | `campaign/agentic_sessions/agentic_session_trace_index.json.session_count` |
| LLM traces | 116 | `campaign/agentic_sessions/agentic_session_trace_index.json.trace_count` |

LLM call and token totals, computed with:

```bash
jq -s -r 'group_by(.request_kind)[] | [.[0].request_kind, length, (map(.llm_usage.input_tokens // 0)|add), (map(.llm_usage.output_tokens // 0)|add), (map(.llm_usage.cache_read_input_tokens // 0)|add)] | @tsv' campaign/llm_traces/*.json
```

| request_kind | Calls | Input tokens | Output tokens | Cache-read input tokens |
|---|---:|---:|---:|---:|
| `tool_selection` | 94 | 1,454,342 | 3,713 | 187,392 |
| `code` | 10 | 304,138 | 28,082 | 0 |
| `hypothesis` | 6 | 221,668 | 5,454 | 0 |
| `hypothesis_target_intent` | 6 | 165,358 | 1,059 | 0 |

Interpretation: `tool_selection` dominates call count and prompt input tokens. It is the largest context/tooling cost signal in this run.

## v3 Boundary Constraints That Must Be Preserved

The audit uses these as non-negotiable constraints, not optimization targets:

- Architecture v3 says the creative layer is tainted, Contract/Verification/Protocol gate evidence, and Decision reads only deterministic `DecisionFeatures`; see `scion/design/scion-architecture-v3.md:162-181` and `:184-210`.
- The v3 component table says Context Manager constructs exposure-controlled LLM context, while Safe Feature Extractor handles decision filtering; see `scion/design/scion-architecture-v3.md:147-159`.
- Onboarding says proposal text and proposal-tool observations are tainted and may guide later proposals, but do not directly decide promotions; see `scion/docs/AGENT_ONBOARDING.md:46-48`.
- Onboarding also says the research agent must be able to inspect declared problem object, allowed history, branch state, memory, and screening/runtime feedback within exposure policy; see `scion/docs/AGENT_ONBOARDING.md:28-33`.
- Active algorithm facts are adapter-owned, and planner/tool-selection context must carry a compact active-facts anchor; see `scion/docs/AGENT_ONBOARDING.md:84-104`.

Therefore: do not remove governance blocks, contract/schema previews, or adapter-owned active facts. Optimize when and how they are exposed.

## Tool Design Assessment

The current tool surface covers the necessary information channels:

| Channel | Evidence in run | Assessment |
|---|---|---|
| Problem mechanics | `context.read_problem`, problem object/solver execution sections in manifests | Necessary. The agent is changing solver behavior; feasibility/objective semantics must be visible. |
| Solver code | `context.list_algorithm_files`, `context.read_algorithm_file`, `context.read_algorithm_slice`, full target/source sections in code prompts | Necessary. Some reads are repetitive and should be deduped or narrowed. |
| Branch state | `context.read_branch_state`, branch dossier/follow-up policy sections | Necessary for same-branch repair and avoiding stale assumptions. |
| Screening/runtime feedback | `feedback.query_screening`, `feedback.query_runtime` in every session | Necessary; hypotheses used it to change direction. But empty/no-new feedback should be summarized deterministically. |
| Cross-branch memory | `memory.query`, `cross_branch_research_map`, compact cross-branch learning | Necessary but should be compact and profile-aware. |
| Contract/schema preview | `proposal.schema_preview`, `proposal.target_permission_preview`, `proposal.contract_preview` | Must keep. These are cheap compared with failed materialization/protocol and enforce v3 boundaries. |
| Algorithm smoke / runtime feedback | `proposal.algorithm_smoke`, smoke artifacts in code sessions | Useful diagnostic, explicitly non-promotional. Keep but inject its repair block only when relevant. |
| Active facts / active solver map | `context.read_active_solver_design`, `context.read_active_solver_map`, active facts prompt sections | Required by onboarding. The issue is volume and duplication, not existence. |

## Tool-Selection Ledger Summary

Important distinction: `tool_selection` traces are LLM calls that return `{intent, tool_name, args}`. Actual tool execution is recorded in transcripts as `Proposal tool observation: <tool>` with a `selection_source`.

Aggregate actual observations by source/tool:

| Source | Tool | Count | Interpretation |
|---|---|---:|---|
| `required_context_preface` | `context.list_surfaces`, `context.read_problem`, `context.list_algorithm_files`, `context.read_active_solver_design`, `context.read_solver_call_graph`, `context.read_active_solver_map` | 14 each | Deterministic preface. Not LLM-selected. Necessary but should not be counted as planner cleverness. |
| `required_context_preface` | `context.read_algorithm_file` | 26 | Full file grounding; high value but frequently repeated across sessions. |
| `planner_selected` | `memory.query`, `feedback.query_screening`, `feedback.query_runtime` | 14 each | LLM selected the same three tools in every session. Strong candidate for deterministic prefetch or one-call bundled feedback summary. |
| `planner_selected` | `context.read_algorithm_file` | 10 | Mixed. Some are useful target/integration reads; some duplicate files already visible in final code prompt. |
| `planner_selected` | `context.read_branch_state` | 5 | Useful in repair/code sessions, likely deterministic after branch divergence/retry. |
| `planner_selected` | `context.read_surface` | 2 | Useful when selecting/confirming target surface; often already enforced by required reads. |
| `planner_map_followup_required` | `context.read_operator_registry`, `context.read_algorithm_slice` | 8 each | Framework-required follow-up after active solver map; deterministic, not a planner decision. |
| `fallback_selected` | schema/permission previews | 14 each | Must keep; deterministic preflight. |
| `fallback_selected` | contract preview / algorithm smoke | 6 each | Code-stage checks; must keep as tainted diagnostics. |

Repeated `tool_selection` choices across traces:

| Selection | Count | Audit read |
|---|---:|---|
| `stop` | 22 total (`14` with `{}`, `8` with `null`) | Stop decisions are cheap output but expensive prompt calls. Multiple sessions had two stop calls. |
| `memory.query {"surface":"solver_design","max_chars":4000}` | 13 | Same default first planner call across almost all sessions. Deterministic candidate. |
| `feedback.query_runtime {"surface":"solver_design"}` | 12 | Same default. Deterministic candidate. |
| `feedback.query_screening {"surface":"solver_design"}` | 11 | Same default. Deterministic candidate. |
| `context.read_branch_state {}` | 9 | Common in code/repair; likely deterministic by phase/branch state. |
| `context.read_algorithm_file local_search.py` | 4 | Sometimes relevant, sometimes a repeated broad read. |
| `context.read_algorithm_file destroy_repair.py` | 3 | Sometimes relevant as integration/repair context. |

Per-session ledger:

| Session | Branch | Status/profile | Tool-selection count | LLM-selected sequence | Executed planner-selected tools | New-info assessment |
|---|---|---|---:|---|---|---|
| `6eed833b-3a81-4a16-bc37-996bab29f9cb` | `fd658eab...` | hypothesis / `algorithm` | 4 | `memory`, `screening`, `runtime`, `stop` | same 3 | First session; necessary, but empty feedback (`0 rows`, no runtime feedback) could have been deterministic summary. |
| `39a9b6a4-8ddf-4f72-85cf-f68080a5b758` | `fd658eab...` | code | 11 | `memory`, `branch_state`, `surface`, `baseline_algorithm.py`, `screening`, `runtime`, `stop`, `surface full`, `scheduler.py`, `state.py`, `stop` | 6 planner + 3 code-phase planner | Useful for code/integration, but two stop calls and extra full reads show planner overhead. |
| `4a576ee6-3958-4d28-983a-0a764c33452b` | `ade67163...` | hypothesis / `algorithm` | 4 | `memory`, `screening`, `runtime`, `stop` | same 3 | Prior fd658eab feedback was now useful; selection pattern still deterministic. |
| `248826e0-84d9-43a1-b9b7-b71c019471b2` | `ade67163...` | code | 7 | `memory`, `screening`, `runtime`, `local_search.py`, `branch_state`, `stop`, `stop` | 5 | Target file read and branch state useful; second stop is pure selection overhead. |
| `8e73f152-5546-48f5-a2bc-856fa0f773a6` | `ade67163...` | hypothesis / `algorithm` | 4 | `memory`, `screening`, `runtime`, `stop` | same 3 | Useful feedback drove shift to repair. Deterministic selection. |
| `c3b61158-74d2-4979-a2a4-ca3f9223cd10` | `ade67163...` | code | 6 | `memory`, `screening`, `runtime`, `stop`, `branch_state`, `stop` | 3 planner + 1 code-phase branch state | Branch state useful; first stop before later branch-state read suggests loop staging overhead. |
| `776585fe-6a28-4058-8ece-927ca2f45169` | `f5f5cbcd...` | hypothesis / `algorithm` | 4 | `memory`, `screening`, `runtime`, `stop` | same 3 | Useful cross-branch feedback; deterministic selection. |
| `1b8d18d9-59c5-4428-a496-091a78b93bb2` | `f5f5cbcd...` | code failed | 9 | `memory`, `screening`, `runtime`, `local_search.py`, `destroy_repair.py`, `branch_state`, `stop`, `surface full`, `stop` | 6 + code-phase surface | Some integration context useful; failure was telemetry identity, not missing code. |
| `295e2bc5-839c-48ca-a24a-c1b4244f0801` | `f5f5cbcd...` | retry code completed | 8 | `memory`, `screening`, `runtime`, `stop`, `branch_state`, `baseline_algorithm.py`, `state.py`, `stop` | 3 + code-phase reads | Repair retry needed state/branch context; default memory/feedback selection could be deterministic. |
| `120bf410-15db-40eb-a544-c332186d492f` | `f5f5cbcd...` | hypothesis / `repair` | 5 | `memory`, `screening`, `runtime`, `branch_state`, `stop` | 4 | Repair profile made branch state useful. This is a good example of profile-specific extra context. |
| `48c73d42-dec0-4329-a9eb-3da692441980` | `f5f5cbcd...` | code failed | 8 | `memory`, `screening`, `runtime`, `local_search.py`, `destroy_repair.py`, `stop`, `branch_state`, `stop` | 5 | Failed on same telemetry identity pattern; extra reads did not fix repair weakness. |
| `2d0469e6-306e-417c-b69b-845a1dd3066a` | `f5f5cbcd...` | retry code completed | 9 | `memory`, `screening`, `runtime`, `stop`, `branch_state`, `surface full`, `baseline_algorithm.py`, `state.py`, `stop` | 3 + code-phase reads | Useful for retry; still repeated default triad and two stops. |
| `f268ae96-2177-4ecd-b038-09e12e177234` | `79800905...` | hypothesis / `algorithm` | 4 | `memory`, `screening`, `runtime`, `stop` | same 3 | Feedback drove move to construction. Deterministic selection. |
| `68e399fe-65c9-4e99-942d-0a9c4c44dab1` | `79800905...` | code completed | 11 | `memory`, `screening`, `runtime`, `local_search.py`, `destroy_repair.py`, `scheduler.py`, `branch_state`, `surface compact`, `baseline_algorithm.py`, `stop`, `stop` | 9 | Some broad reads may help multi-file construction/scheduler wiring, but the target was `construction.py`; repeated non-target full reads are suspect. |

Conclusion: actual tool observations are useful, but the LLM selection loop is overused for default memory/feedback/stop sequencing. The code-phase planner also sometimes rereads broad algorithm files despite the final code prompt rendering mandatory target/integration source.

## Prompt / Context Block Classification

Relevant assembly code:

- `scion/scion/proposal/context_manager/manager.py:272-304` builds hypothesis context and explicitly includes problem summary, champion code, branch history, and blacklist while excluding validation/frozen/raw metrics.
- `scion/scion/proposal/context_manager/manager.py:671-688` builds code context with problem summary, hypothesis details, target file content, interface spec, import whitelist, and prior failure when present.
- `scion/scion/proposal/engine/tool_selection.py:32-75` splits tool-selection context into cacheable system blocks and dynamic user prompt.
- `scion/scion/proposal/engine/tool_selection.py:78-130` moves active facts, constraints, source context, and tool guidance into the cacheable planner prefix.
- `scion/scion/proposal/engine/tool_selection.py:174-213` sanitizes raw metrics, validation/frozen, holdout, code content, and target file code out of planner context.
- `scion/scion/proposal/engine/hypothesis_context_profiles.py:54-109` derives `algorithm` vs `repair` hypothesis profiles and removes repair-only keys outside repair mode.
- `scion/scion/proposal/engine/hypothesis_prompts.py:25-181` renders hypothesis system blocks, including problem mechanics, research surfaces, champion code, branch/cross-branch/feedback guidance.
- `scion/scion/proposal/engine/code_prompts.py:36-175` renders code system blocks and code-quality / feasibility / interface / import rules.
- `scion/scion/proposal/engine/code_prompts.py:237-305` renders source visibility ledger, target source, patch digests, branch integration files, prior failure, hypothesis details, and telemetry identity guidance.
- `scion/scion/proposal/engine/code_prompts.py:387-414` renders Telemetry Identity Rules.

Observed prompt size samples:

| Trace | Kind | System chars | User chars | Input tokens |
|---|---|---:|---:|---:|
| `20260607T062921460472_tool_selection_037ea9bdf0_641da385` | `tool_selection` | 79,050 | 6,954 | 19,725 |
| `20260607T062938983674_hypothesis_f8ec639d2b_b5ef9939` | `hypothesis` | 75,441 | 38,988 | 29,955 |
| `20260607T071937721031_code_51265b816e_d505ec1d` | `code` | 65,245 | 45,256 | 27,255 |

Prompt manifest examples:

- First hypothesis manifest `6eed833b.../scratch/api_visible_prompt_manifest_0002_hypothesis.json` had 38 visibility ledger entries: 24 full sections, 5 dedicated projections, 9 summaries. Major estimated token blocks included `solver_design_full_algorithm_file_reads` 7,642, `agentic_proposal_tool_observations` 5,892, `active_solver_map_receipts` 5,807, `active_algorithm_facts` 1,645.
- Repair hypothesis manifest `120bf410.../scratch/api_visible_prompt_manifest_0002_hypothesis.json` had 54 entries and estimated 40,375 section tokens plus 8,924 tool-result projection tokens.
- Final code manifest `68e399fe.../scratch/api_visible_prompt_manifest_0001_code.json` had large sections: `agentic_proposal_tool_observations` 5,323, `branch_current_integration_files` 4,786, `full_solver_algorithm_rules` 2,115, `constraints` 2,112, `compact_solver_design_implementation_scope` 1,768, `active_algorithm_facts` 1,568, `approved_target_file_current_content` 1,483.

Classification table:

| Block/category | Current default visibility | Necessary? | Recommendation |
|---|---|---|---|
| Problem summary/object/solver mechanics | Hypothesis + code | Yes | Keep; adapter-owned and needed for feasibility/objective semantics. |
| Research surfaces/interface spec | Hypothesis + code | Yes | Keep; v3 boundary. |
| Active algorithm facts | Hypothesis + code + planner anchor | Yes | Keep high-signal compact block before raw observations, per onboarding. |
| Active solver map receipts | Often full/large | Yes, but not always full | Keep digest/anchor always; render full receipts on demand or only when selecting mechanism owner/slice. |
| Full algorithm file reads | Frequently broad | Partly | Target/integration source required for code; hypothesis should prefer facts/slices, not full file bundles by default. Dedup repeated files across sessions. |
| Branch dossier/follow-up/state | Profile-dependent | Yes for branch/retry | Inject by branch state/profile, not always at full volume. |
| Cross-branch memory | Useful | Yes, compact | Keep compact lessons; avoid raw/raw-ish research maps unless novelty pressure is active. |
| Screening/runtime feedback | Useful | Yes | Deterministically summarize latest same-campaign feedback; LLM need not select query each session. |
| Material difference / duplicate risk | Context-dependent | Yes when same mechanism/near duplicate | Inject only when branch lineage or similarity provider says it is active. |
| Runtime/quality repair guidance | Repair-dependent | Yes in repair | Profile by failure category. Do not show telemetry repair blocks to unrelated new algorithm hypotheses. |
| Telemetry identity rules | Code phase and telemetry-changing hypotheses | Yes | Keep; gate is valid. Add clearer diff-level lint/repair view rather than relaxing. |
| Typed edit / exact_replace constraints | Code phase | Yes but large | Keep, but consider compact templates or schema-side enforcement with shorter prompt reminders. |
| Tool catalog | Every tool-selection call | Necessary for free-form planner | Too expensive for deterministic default triad. Use deterministic prefetch and only invoke LLM planner when a real choice remains. |
| Raw proposal-tool observations | Large | Audit/debug support | Prefer compact per-observation ledger; project full payloads only for selected evidence refs. |

## Evidence For / Against "Model Spends Effort Satisfying Framework Rules"

| Claim | Verdict | Evidence |
|---|---|---|
| The model sometimes spends nontrivial effort satisfying framework/telemetry rules instead of research. | Supported, narrow | Sessions `1b8d18d9...` and `48c73d42...` each produced two `code` traces and failed on `code_stage_telemetry_identity_mismatch`. Failure artifacts explicitly say generated telemetry used `alns` instead of protected `route_limit_repair_bias`. |
| The tool-selection loop itself caused the two proposal blocks. | Evidence insufficient | Failures were code-stage telemetry identity mismatches, not malformed tool choices or missing context. The agent had telemetry identity guidance; repair still failed. |
| Tool observations did not help research. | Refuted | Hypotheses mention prior runtime saturation/tie-dominated outcomes and shift mechanism surfaces: broad local-search segment exchange -> narrower route merge -> repair tie-break -> scheduler route-limit bias -> construction diversification. |
| Context overload diluted attention. | Supported as risk, not proven causal | Prompt manifests show very large blocks and `tool_selection` consumed 1.45M input tokens. But there is no direct attention metric proving overload caused bad hypotheses. |
| Governance/contract blocks should be removed to improve creativity. | Refuted | v3 requires tainted proposal isolation and deterministic gates. The telemetry identity blocks prevented misattribution of mechanism evidence. |
| Some tool-selection decisions are not worth LLM calls. | Supported | Every session selected `memory.query`, `feedback.query_screening`, and `feedback.query_runtime`; many hypothesis sessions were exactly that triad plus stop. |

## Four Problem Classes

| Class | What happened in this run | Action |
|---|---|---|
| Necessary information acquisition cost | Deterministic preface read problem/surface/active solver map/code; previews checked schema/permission/contract/smoke. | Keep. These enforce v3 and let the agent do real research. |
| Optimizable repeated tool-selection cost | 94 planner calls; repeated default memory/screening/runtime/stop sequence; 22 stop selections; repeated broad file choices. | P1/P2 optimize with deterministic prefetch, result dedup, and selection ledger. |
| Default context over-injection / attention dilution | Hypothesis/code manifests carried large active solver map receipts, full file reads, raw tool observations, rules, and repair guidance. | P1/P2 profile by phase/failure mode and compact raw observations. |
| v3 governance/contract boundary | Telemetry identity gate blocked two bad patches; Contract/schema/permission/smoke previews preserve taint boundary. | Preserve. Improve repair UX and observability, not the gate. |

## Conservative Optimization Plan

P1 now:

1. Add a tool-selection ledger artifact per session. Fields: planner_call_index, selected tool, args digest, executed yes/no, skip/defer reason, source (`planner_selected`, `required_context_preface`, etc.), result digest, result novelty (`new`, `duplicate`, `empty`, `summary_only`), prompt/input tokens, and whether the final prompt included the result.
2. Deterministically prefetch the default planner triad after required context: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, with canonical same-campaign `solver_design` scope. Let LLM planner run only after this prefetch when a non-default choice remains.
3. Dedup reusable tool results across a session and across retry sessions in the same branch/hypothesis. If the same file digest or feedback digest is already visible, expose a receipt instead of asking the model to select/read it again.
4. Record `stop` as a deterministic terminal condition when required context is satisfied and no non-default tool has been selected. Avoid a second LLM stop call.
5. For telemetry identity repair failures, inject a small diff-level lint table into the repair prompt: offending helper, mechanism id, protected ids, exact generated line, allowed replacement/removal instruction. Keep the gate.

P2 after next 4R observation:

1. Split context profiles beyond `algorithm`/`repair`: `new_branch_algorithm`, `same_branch_refine`, `code_retry_identity`, `code_retry_contract`, `runtime_failure_diagnostic`, `construction_target`, `local_search_target`.
2. Replace large active solver map receipts in ordinary hypothesis prompts with digest + owner/slice summary; expand only when the planner asks for a specific registry/slice.
3. Move some typed edit constraints from prose into schema/tool error messages with a shorter prompt summary. Keep exact_replace requirements but reduce repeated natural-language bulk.
4. Add a bundled "research feedback summary" tool/result that combines memory, screening, runtime, branch-local quality blocks, and negative facts into one compact tainted feedback packet.
5. Make final code prompt source projection explain which file sections are already mandatory-visible so planner can avoid rereading them.

P3 / experiment-only:

1. A/B compare LLM planner vs deterministic prefetch + planner-on-demand on identical 4R seeds.
2. Track whether hypothesis novelty and protocol outcomes change when raw tool observations are replaced by compact active facts plus selected evidence refs.
3. Measure prompt-cache economics after moving default triad out of LLM planner calls.

Do not do:

- Do not remove tools wholesale.
- Do not expose raw validation/frozen/holdout details to proposal agents.
- Do not move CVRP/ALNS/VNS semantics into generic core.
- Do not relax telemetry identity attribution in Decision/Protocol evidence.

## Next 4R Observability Fields

Add these fields before the next comparable 4R run:

| Field | Level | Purpose |
|---|---|---|
| `tool_selection_ledger[]` | session | One row per planner call with selected tool, args digest, token cost, executed/skipped/deferred, skip reason, result digest. |
| `tool_result_novelty` | observation | `new`, `duplicate_same_digest`, `empty`, `superseded_by_prefetch`, `summary_only`. |
| `deterministic_prefetch_plan_id` | session | Distinguish fixed framework context from LLM choices. |
| `result_in_final_prompt` | observation | Whether observation appears full, summary, dedicated projection, omitted, or truncated in final prompt manifest. |
| `prompt_block_profile` | trace/manifest | Context profile plus block inclusion reason (`always_v3`, `phase_required`, `failure_mode`, `planner_selected`, `debug_only`). |
| `prompt_block_token_estimate` | manifest section | Already partly present; make it first-class and aggregate by block family. |
| `repair_guidance_trigger` | trace/session | Which failure category caused repair guidance injection. |
| `identity_lint_offenders[]` | code self-check | Structured telemetry identity offenders with helper, mechanism id, protected ids, generated line, source patch pointer. |
| `tool_selection_default_triage_satisfied` | session | Whether memory/screening/runtime default packet was already present before planner. |
| `planner_choice_entropy_bucket` | session | Low/medium/high based on number of valid non-default choices; use to decide when LLM selection is worthwhile. |
| `feedback_rows_available` and `feedback_rows_returned` | feedback observation | Distinguish useful feedback from empty successful calls. |
| `file_read_digest_reused_from` | file observation | Shows repeated file reads that could be receipts. |

## Final Answer To The Audit Question

Current context/tooling helps the agent do research, but the current tool-selection mechanism is too expensive for the amount of choice it often delegates to the model. The best fix is not to cut tools. It is to make fixed information needs deterministic, deduplicate result exposure, and reserve LLM tool-selection for genuinely uncertain choices.

The context stack is also heavy. The high-risk blocks are not governance boundaries themselves; they are broad default projections of active solver map receipts, full algorithm reads, raw tool observations, and repair guidance outside the narrow failure mode. Use context profiles and explicit block inclusion reasons.

The evidence supports a narrow claim that the model sometimes spends effort satisfying Scion framework rules, especially telemetry identity/edit-protocol repair. It also provides a clear counterexample to the stronger claim that the framework prevented research: hypothesis outputs used feedback and changed algorithmic direction across branches. The conservative path is P1 observability + deterministic prefetch + dedup + targeted repair injection, followed by a next-run measurement rather than a broad simplification.
