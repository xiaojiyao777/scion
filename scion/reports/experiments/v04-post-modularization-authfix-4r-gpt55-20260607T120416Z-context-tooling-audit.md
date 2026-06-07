# Scion v04 Post-Modularization Authfix 4R Context / Tooling Audit

Run root: `/home/clawd/research/scion-experiments/v04-post-modularization-authfix-4r-gpt55-20260607T120416Z-claw`

Reference audit: `scion/reports/experiments/v04-context-tooling-deep-audit-20260607.md`

Audit date: 2026-06-07

Scope: context/tooling state in the next 4R run after the Rawls context/tooling audit. This report does not propose removing tools. It audits selection cost, default injection strategy, prompt observability, telemetry identity repair evidence, and readiness for a longer 8R run.

## Executive Conclusion

The Rawls ledger/observability follow-up worked as an audit instrument. This run now exposes `tool_selection_ledger`, `observation_ledger`, read receipts, active-fact anchors, prompt manifests, block profiles, inclusion reasons, block char/token estimates, and result-in-final-prompt status well enough to diagnose the context/tooling mechanism from artifacts alone.

The mechanism is still a bottleneck. `tool_selection` fell from Rawls's 94 calls / 1,454,342 input tokens to 47 calls / 688,585 input tokens, but the share barely moved: 79.7% of all LLM calls and 66.2% of all input tokens in this run versus 81.0% calls and about 67.8% input in Rawls. The absolute cost improved mostly because this run had fewer sessions and no repair failures; the default selection pattern remains.

The clearest finding is now stronger than in Rawls: all 8 sessions selected the default triad (`memory.query`, `feedback.query_screening`, `feedback.query_runtime`), 7/8 used it as the first three planner choices, all 8 ended with `default_triad_satisfied=true`, and `deterministic_prefetch_plan_id` was still `none`. There were also 12 LLM-selected `stop` entries, all skipped as terminal signals. Default triad plus stop accounts for 36/47 tool-selection calls. That is enough evidence to implement deterministic prefetch, deterministic stop, and a narrow planner-on-demand mode now.

The context stack remains heavy but better instrumented. Manifests show large repeat blocks from full algorithm reads, active solver map receipts, raw proposal-tool observations, cross-branch research maps, and code integration files. These blocks now have inclusion reasons and profiles, so the next change can be profile-gating and projection, not blind removal.

This run had no code repair failures, no telemetry failed experiments, no quality blocks, and no model repair failures. Code prompts still included `telemetry_identity_rules`, but structured `identity_lint_offenders[]` / `repair_guidance_trigger` fields did not appear in self-check artifacts. Because no telemetry identity failure occurred, the offender path was not exercised; the current evidence proves absence of failures, not correctness of offender telemetry.

## Evidence Read

- `campaign/llm_traces/*.json`: all 59 traces.
- `campaign/agentic_sessions/agentic_session_trace_index.json`: 8 sessions / 59 traces.
- Every session `output.json` and `transcript.json`: 8 outputs and 8 transcripts.
- Every session `scratch/api_visible_prompt_manifest_*.json`: 12 prompt manifests.
- `campaign/status.json` and `campaign/campaign_summary.json`.

Design baseline checked before interpreting evidence:

- `scion/design/scion-architecture-v3.md`: Context Manager constructs exposure-controlled context; tainted Creative Layer outputs do not become Decision inputs; Decision reads deterministic `DecisionFeatures`.
- `scion/docs/AGENT_ONBOARDING.md`: proposal text and proposal-tool observations are tainted; active facts anchor must be visible to planner/tool-selection; raw observations are audit/debug support and may be compacted.
- Rawls reference audit: especially Executive Conclusion, Tool-Selection Ledger Summary, and Next 4R Observability Fields.

## Run-Level Accounting

From `campaign/status.json` and `campaign/campaign_summary.json`:

| Field | Value |
|---|---:|
| Requested rounds | 4 |
| Effective rounds completed | 4 |
| Proposal attempts total | 4 |
| Screened experiments | 4 |
| Screened but not effective | 0 |
| Formal screened candidates | 4 |
| Protocol evaluated candidates | 4 |
| Quality blocks | 0 |
| Telemetry failed experiments | 0 |
| Telemetry repair attempts | 0 |
| Agentic sessions | 8 |
| LLM traces | 59 |

## LLM Request Statistics

Computed from all `campaign/llm_traces/*.json`.

| request_kind | Calls | Input tokens | Output tokens | Cache-read input tokens |
|---|---:|---:|---:|---:|
| `tool_selection` | 47 | 688,585 | 1,764 | 72,320 |
| `hypothesis_target_intent` | 4 | 107,253 | 640 | 0 |
| `hypothesis` | 4 | 137,222 | 3,652 | 0 |
| `code` | 4 | 106,494 | 9,132 | 0 |
| **Total** | **59** | **1,039,554** | **15,188** | **72,320** |

`tool_selection` share:

| Metric | Rawls 4R | Current 4R | Change |
|---|---:|---:|---:|
| `tool_selection` calls | 94 | 47 | -47 / 0.50x |
| All LLM calls | 116 | 59 | -57 / 0.51x |
| Call share | 81.0% | 79.7% | -1.3 pp |
| `tool_selection` input tokens | 1,454,342 | 688,585 | -765,757 / 0.47x |
| All input tokens | 2,145,506 | 1,039,554 | -1,105,952 / 0.48x |
| Input share | 67.8% | 66.2% | -1.6 pp |
| Avg input per `tool_selection` call | 15,472 | 14,651 | -821 |
| Cache-read share inside `tool_selection` | 12.9% | 10.5% | -2.4 pp |

Interpretation: the absolute token burn improved, but the relative bottleneck did not. The run is healthier because there were only 8 sessions and no repair loop, not because the selection mechanism stopped dominating the LLM budget.

## Tool-Selection Ledger Summary

Aggregate from the 8 session `output.json` files:

| Field | Value |
|---|---:|
| Ledger entries | 47 |
| Executed selections | 35 |
| Skipped selections | 12 |
| `stop` entries | 12 |
| `planner_stop` | 8 |
| `code_planner_stop` | 4 |
| Sessions with default triad present | 8/8 |
| Sessions with default triad as first 3 calls | 7/8 |
| Sessions with `default_triad_satisfied=true` | 8/8 |
| Sessions with deterministic prefetch plan | 0/8 (`none` in every session) |

Selected tools:

| Tool | Count | Read |
|---|---:|---|
| `memory.query` | 8 | Default triad, every session. |
| `feedback.query_screening` | 8 | Default triad, every session. |
| `feedback.query_runtime` | 8 | Default triad, every session. |
| `stop` | 12 | Terminal signals, all skipped. |
| `context.read_algorithm_file` | 6 | Mostly code-phase grounding; several became receipts. |
| `context.read_branch_state` | 4 | Code/branch context, useful but phase-deterministic. |
| `context.read_surface` | 1 | One code session selected it explicitly. |

Executed selection novelty:

| `tool_result_novelty` | Count |
|---|---:|
| `new` | 26 |
| `summary_only` | 5 |
| `empty` | 4 |

Prompt inclusion from ledger entries:

| `result_in_final_prompt_status` | Count |
|---|---:|
| `included` | 34 |
| `pending_prompt_manifest` | 1 |
| `none` | 12 |

The `none` values are the skipped `stop` entries. The single `pending_prompt_manifest` was an empty screening feedback entry in the first hypothesis session; the final manifest still had enough visibility ledger data to audit prompt content.

### Per-Session Ledger

| Session | Profile / target | Status | Tool-selection sequence | Stops / skips | Novelty | Empty feedback | Read/receipt notes |
|---|---|---|---|---:|---|---:|---|
| `6d89f26c...` | hypothesis, `local_search.py` | `partial_hypothesis_only` | `memory`, `screening`, `runtime`, `stop` | 1 / 1 | `new=1`, `empty=2` | 2 | Required preface read `destroy_repair.py`, `local_search.py`, `scheduler.py` as new full file context. |
| `d87626eb...` | code, `local_search.py` | `completed` | `memory`, `branch_state`, `surface`, `baseline_algorithm.py`, `screening`, `runtime`, `stop`, `stop` | 2 / 2 | `new=4`, `empty=2` | 2 | `baseline_algorithm.py` was new; `local_search.py` came back as `duplicate_same_digest` receipt. |
| `744c7c00...` | hypothesis, `local_search.py` | `partial_hypothesis_only` | `memory`, `screening`, `runtime`, `stop` | 1 / 1 | `new=3` | 0 | Required preface repeated the same three broad algorithm files as new for this new session. |
| `0c5864e5...` | code, `local_search.py` | `completed` | `memory`, `screening`, `runtime`, `local_search.py`, `destroy_repair.py`, `stop`, `branch_state`, `stop` | 2 / 2 | `new=4`, `summary_only=2` | 0 | Planner-selected `local_search.py` and `destroy_repair.py` returned compact duplicate receipts. |
| `f2150518...` | hypothesis, `destroy_repair.py` | `partial_hypothesis_only` | `memory`, `screening`, `runtime`, `stop` | 1 / 1 | `new=3` | 0 | Required preface read `destroy_repair.py`, `local_search.py`, `scheduler.py` as new full file context. |
| `9834335b...` | code, `destroy_repair.py` | `completed` | `memory`, `screening`, `runtime`, `local_search.py`, `branch_state`, `stop`, `stop` | 2 / 2 | `new=4`, `summary_only=1` | 0 | Planner `local_search.py` and required `destroy_repair.py` became duplicate receipts. |
| `b96a85ba...` | hypothesis, `route_compaction.py` | `partial_hypothesis_only` | `memory`, `screening`, `runtime`, `stop` | 1 / 1 | `new=3` | 0 | Required preface again read `destroy_repair.py`, `local_search.py`, `scheduler.py`; target was a new `route_compaction.py`. |
| `e0149e27...` | code, `route_compaction.py` | `completed` | `memory`, `screening`, `runtime`, `local_search.py`, `destroy_repair.py`, `branch_state`, `stop`, `stop` | 2 / 2 | `new=4`, `summary_only=2` | 0 | Planner `local_search.py` and `destroy_repair.py` became duplicate receipts; route-compaction surface reads were new. |

Conclusion: the actual tool observations are useful and now auditable. The selection loop is still spending LLM calls on a deterministic triad and terminal stop. The new ledger is sufficient evidence to stop waiting on this part.

## Observation Ledger And Receipt Reuse

Aggregate from `observation_ledger.observations`:

| Observation source | Tool | Count |
|---|---|---:|
| `required_context_preface` | `context.read_algorithm_file` | 12 |
| `required_context_preface` | `context.list_algorithm_files` | 8 |
| `required_context_preface` | `context.read_active_solver_design` | 8 |
| `required_context_preface` | `context.read_solver_call_graph` | 8 |
| `required_context_preface` | `context.read_active_solver_map` | 8 |
| `selected_surface_required` | `context.read_surface` | 7 |
| `planner_selected` | `context.read_algorithm_file` | 6 |
| `planner_selected` | `context.read_surface` | 1 |
| `planner_map_followup_required` | `context.read_operator_registry` | 4 |
| `planner_map_followup_required` | `context.read_algorithm_slice` | 4 |
| Other deterministic grounding | surface/slice/file reads | 10 |

Observation novelty:

| `tool_result_novelty` | Count |
|---|---:|
| `new` | 51 |
| `duplicate_same_digest` | 25 |

File/surface grounding:

| Class | `new` | `duplicate_same_digest` | Total |
|---|---:|---:|---:|
| `context.read_algorithm_file` | 13 | 7 | 20 |
| `context.read_surface` | 10 | 2 | 12 |

Read receipts are present and useful: 76 receipts total, including 20 algorithm-file receipts and 12 surface receipts. Duplicate full-file reads usually returned a compact receipt with the summary: already observed unchanged source, do not read the same file again for source, use branch-state or symbol/slice tools for different information.

This is a real improvement over Rawls. It reduces repeated payload exposure. It does not eliminate the LLM selection calls that asked for the duplicate reads.

## Prompt Manifest Audit

All 12 manifests use `api-visible-prompt-manifest.v3`:

| Manifest kind | Count |
|---|---:|
| `hypothesis_target_intent` | 4 |
| `hypothesis` | 4 |
| `code` | 4 |

Visibility status across manifests:

| Status | Count |
|---|---:|
| `full` | 332 |
| `summary` | 135 |
| `dedicated_projection` | 37 |
| `omitted` | 8 |
| `truncated` | 0 |

Tool-result visibility from manifest ledgers:

| `result_in_final_prompt_status` | Count |
|---|---:|
| `included` | 170 |
| `omitted` | 8 |

The manifests answer the main Rawls observability questions:

- `result_in_final_prompt` is available in both session ledger entries and manifest `tool_result_visibility_ledger`.
- `prompt_block_profile` is available on sections/visibility entries.
- Block `inclusion_reason` is available. Common values are `always`, `always_v3`, `phase_required`, and `dynamic_phase_context`.
- Section `char_count` is available. `visibility_ledger.entries` also include `token_estimate`, making token/char estimates usable.
- `prompt_section_truncation_count` is 0 in the audited manifests; bounded tool projections are distinguished from provider prompt truncation.

Largest observed blocks:

| Block | Kind/profile | Reason | Size |
|---|---|---|---:|
| `solver_design_full_algorithm_file_reads` | hypothesis + target intent / `algorithm` | `phase_required` | 30,568 chars / 7,642 token estimate |
| `active_solver_map_receipts` | hypothesis / `algorithm` | `always_v3` | up to 27,973 chars / 6,994 token estimate |
| `agentic_proposal_tool_observations` | hypothesis / `algorithm` | `dynamic_phase_context` | up to 25,506 chars / 6,377 token estimate |
| `cross_branch_research_map` | hypothesis + target intent / `algorithm` | `always` | 22,696 chars / 5,674 token estimate |
| `agentic_proposal_tool_observations` | code / code phase | `dynamic_phase_context` | up to 19,521 chars / 4,881 token estimate |
| `branch_current_integration_files` | code / code phase | `always` | about 19,145 chars / 4,786 token estimate |

Block family aggregate, approximate from manifest sections/visibility entries:

| Family | Approx tokens | Approx chars | Count |
|---|---:|---:|---:|
| `general` | 131,793 | 526,862 | 235 |
| `source_context` | 76,453 | 305,779 | 29 |
| `active_facts` | 65,733 | 262,900 | 24 |
| `tool_observation` | 64,307 | 257,208 | 12 |
| `feedback` | 5,619 | 22,461 | 9 |
| `governance` | 3,080 | 12,296 | 8 |

Interpretation: context observability is now good enough to identify oversized block families. The next context work should target projection/profile policy for full algorithm reads, active solver map receipts, cross-branch maps, and raw tool observations. It should not remove governance or active facts, because v3 and onboarding require those boundaries and anchors.

## Telemetry Identity And Repair Fields

Run-level telemetry status:

| Field | Value |
|---|---:|
| `telemetry_failed_experiments` | 0 |
| `telemetry_repair_attempts` | 0 |
| `quality_block_ledger_count` | 0 |
| `quality_blocks` | 0 |
| `campaign_loop.failure_categories` | `{}` |
| Code retry failures | 0 in every session |

Self-check artifacts:

| Artifact class | Count / result |
|---|---|
| `proposal.schema_preview` | 8, all passed |
| `proposal.target_permission_preview` | 8, all passed |
| `proposal.contract_preview` | 4, all passed |
| `proposal.algorithm_smoke` | 3 `passed`, 1 `diagnostic`, all `passed=true` |

Code prompt telemetry identity rules:

| Session | Block chars | Inclusion reason |
|---|---:|---|
| `0c5864e5...` | 1,069 | `dynamic_phase_context` |
| `9834335b...` | 1,074 | `dynamic_phase_context` |
| `d87626eb...` | 1,069 | `dynamic_phase_context` |
| `e0149e27...` | 1,078 | `dynamic_phase_context` |

Structured offender fields:

- `identity_lint_offenders[]`: not present in scanned `self_check_preview_full_*.json`.
- `repair_guidance_trigger`: not present in scanned `self_check_preview_full_*.json`.
- `telemetry_identity`: not present as a structured self-check field.

Interpretation: this run proves there were no code repair failures and that telemetry identity rules are still injected into code prompts. It does not validate offender-field behavior because no telemetry identity failure occurred. For the next run, offender fields should appear as empty arrays or explicit `not_applicable` records, not only when a failure fires; that will make absence auditable.

## Did The Rawls Observability Changes Provide Enough Evidence?

Yes for context/tool-selection cost and prompt inclusion:

- Session `tool_selection_ledger.entries[]` exposes tool, args digest, result digest, executed/skipped status, skip reason, result novelty, estimated input tokens, default-triad state, deterministic prefetch plan, and final prompt inclusion status.
- `observation_ledger` exposes active fact anchors, digests, source observations, selection source, novelty, prompt-visible chars, and read receipts.
- Prompt manifests expose result inclusion, section visibility, block profile, inclusion reason, char counts, token estimates, truncation diagnostics, and omitted sections.
- `status.json` and `campaign_summary.json` make repair/telemetry/quality-block absence easy to verify.

Still incomplete:

- `input_token_cost` in session ledger entries is `null`; it points to linked LLM traces. This is acceptable for audit but less convenient than a direct trace id/token field per entry.
- `planner_choice_entropy_bucket` is not present.
- `feedback_rows_available` / `feedback_rows_returned` are not first-class fields; they are inferable from summaries like `Returned 0 of 0 screening feedback row(s)`.
- `file_read_digest_reused_from` is not present as a named field; reuse is inferable from `duplicate_same_digest`, read receipts, and summaries.
- Identity offender fields did not appear in this no-failure run.

Net: the observability change is sufficient to justify P1 tooling changes. It is not yet sufficient to evaluate telemetry-offender repair quality.

## Is Context / Tool Selection Still The Bottleneck?

Yes.

The default triad is still LLM-selected in every session. Stop is still LLM-selected 12 times. Default triad plus stop is 36/47 `tool_selection` calls, or 76.6% of the selection loop. Those choices are framework control flow, not high-entropy research decisions.

Caching did not solve the bottleneck: current `tool_selection` still consumed 688,585 input tokens, and only 72,320 were cache-read tokens. Receipt reuse reduced repeated payloads, but the model still paid prompt/call overhead to ask for deterministic or duplicate reads.

The context bottleneck is also still visible in manifests. Full algorithm file reads, active solver map receipts, raw proposal-tool observations, and cross-branch maps are large. They may be necessary in some profiles, but they are now measurable enough to profile-gate.

## Action Judgment

| Candidate action | Do now? | Rationale |
|---|---|---|
| Deterministic prefetch of `memory.query`, `feedback.query_screening`, `feedback.query_runtime` | Yes | 8/8 current sessions and 14/14 Rawls sessions used this triad. This is no longer a hypothesis. Keep the tools; stop asking the LLM to rediscover them. |
| Deterministic stop | Yes | 12/47 current selections are `stop`, all skipped. Code sessions often have a second stop. This can be a terminal loop condition once required/default context is satisfied. |
| Planner-on-demand after default packet | Yes, narrow version now | Run the LLM planner only when non-default choices remain: branch-state, target file/slice, operator registry, or failure-specific diagnostics. Broader entropy policy can wait for 8R evidence. |
| File/source receipt reuse | Keep and tighten | Current duplicate receipts work. Add explicit `file_read_digest_reused_from` and make planner prompts aware when mandatory target/integration source is already visible. |
| Context block profile-gating | Start with measurement; change selectively | Manifests show large blocks, but quality impact needs longer evidence. For P1, profile active solver map receipts and raw observations by digest/summary first; do not remove active facts or governance. |
| Telemetry offender repair UX | Keep rules; add explicit empty/not-applicable fields | No failure occurred, so do not infer repair quality. Preserve the gate and make offender field absence auditable. |

## Next Experiment Metrics

For the next comparable run, keep the current ledgers and add/monitor:

| Metric | Why |
|---|---|
| `tool_selection` calls and input tokens per session | Primary cost target. |
| `tool_selection_default_triage_satisfied_before_planner` | Confirms deterministic prefetch happened before any planner call. |
| `deterministic_prefetch_plan_id` not `none` | Separates fixed context from LLM choices. |
| Planner calls saved by deterministic triad and deterministic stop | Direct ROI metric for P1. |
| `planner_choice_entropy_bucket` | Decides when LLM planner is actually warranted. |
| `feedback_rows_available` / `feedback_rows_returned` | Distinguishes empty successful feedback calls from useful feedback. |
| `tool_result_novelty` by tool and phase | Measures `new` vs `duplicate_same_digest` vs `summary_only` vs `empty`. |
| `file_read_digest_reused_from` and inherited session/phase | Makes receipt reuse first-class. |
| `result_in_final_prompt_status` by tool | Confirms prefetch/tool outputs actually reach final prompts. |
| Block-family tokens by profile/reason | Tracks full algorithm reads, active facts, raw observations, cross-branch maps, and code integration files. |
| `identity_lint_offenders[]` even when empty | Makes telemetry repair absence auditable. |
| Code repair failure count and root cause | Ensures deterministic tooling changes do not hide repair regressions. |
| Hypothesis novelty/provider rejection categories | Checks that lower selection cost does not reduce research quality. |
| Protocol outcomes and branch lifecycle state | Needed before using 8R/12R as quality evidence. |

## 8R Readiness

Do not run a longer 8R/12R with the same selection policy if the goal is to learn new context/tooling facts; this 4R already confirms the default-triad/stop bottleneck. A longer run would mostly multiply known overhead.

I support entering an 8R experiment after the P1 tooling changes above, or as an explicit A/B where one arm is current policy and the other is deterministic prefetch + deterministic stop + planner-on-demand. That 8R should measure whether reduced planner calls preserve hypothesis novelty, code correctness, prompt inclusion, and protocol outcomes.

If no code changes are allowed before the next experiment, an 8R is still valid as a solver-quality/control smoke, but it should be labeled as running with a known context/tool-selection bottleneck.
