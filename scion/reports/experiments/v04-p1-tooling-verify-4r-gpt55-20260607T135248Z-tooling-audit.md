# v0.4 P1 Tooling Audit: 4R GPT-5.5

Date: 2026-06-07

Current run:
`/home/clawd/research/scion-experiments/v04-p1-tooling-verify-4r-gpt55-20260607T135248Z-claw`

Baseline run:
`/home/clawd/research/scion-experiments/v04-post-modularization-authfix-4r-gpt55-20260607T120416Z-claw`

Scope: read-only audit of `campaign/status.json`, `campaign/campaign_summary.json`,
`agentic_sessions/*/output.json`, `agentic_sessions/*/scratch/api_visible_prompt_manifest_*.json`,
and `llm_traces/*.json`.

## Executive conclusion

P1 context/tool-selection optimization worked on the intended cost path:
`tool_selection` LLM calls dropped from 47 to 18, and `tool_selection` input tokens
dropped from 688,585 to 232,381. That is a 61.7% call reduction and a 66.3%
input-token reduction.

The prior skipped `stop` behavior is effectively gone in this run: current
ledger has 0 `stop` selections and 0 skipped entries, compared with 12 skipped
`stop` entries in baseline.

The deterministic prefetch control flow is present and is not being routed
through the LLM planner: every current session has a non-empty
`deterministic_prefetch_plan_id`, every ledger entry has a non-empty plan id,
and 20 of 34 current ledger entries have `source == "deterministic_prefetch"`.

One audit gap remains: deterministic prefetch observations are preserved in
`compact_transcript`, `evidence_used`, and final prompt visibility, but they are
not present in `observation_ledger.observations` or `observation_ledger.read_receipts`.
This does not indicate the information channel was deleted, because all 20
deterministic prefetch result ids are in prompt manifests, but it does mean the
observation-ledger persistence contract is not fully satisfied.

Recommendation: keep the P1 deterministic control flow and do not move these
prefetches back behind the LLM planner. Fix or explicitly waive the
`observation_ledger` persistence gap before treating an 8R run as formally
auditable. If the next 8R is exploratory, it can proceed with this known
telemetry caveat; for a formal 8R gate, fix ledger persistence first.

## 1. Tool-selection calls and tokens

`status.json` only carries request-kind counts; it has no `cache_stats` or
`llm_usage` fields. `campaign_summary.json` and direct `llm_traces` aggregation
agree exactly.

| Source | tool_selection calls | input tokens | cache read tokens | cache miss tokens | cache create tokens | output tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| current `status.json` | 18 | n/a | n/a | n/a | n/a | n/a |
| current `campaign_summary.json` | 18 | 232,381 | 6,912 | 225,469 | 0 | 750 |
| current direct `llm_traces` sum | 18 | 232,381 | 6,912 | 225,469 | 0 | 750 |
| baseline `campaign_summary.json` | 47 | 688,585 | 72,320 | 616,265 | 0 | 1,764 |
| baseline direct `llm_traces` sum | 47 | 688,585 | 72,320 | 616,265 | 0 | 1,764 |

Reduction versus baseline:

| Metric | Baseline | Current | Reduction |
| --- | ---: | ---: | ---: |
| Calls | 47 | 18 | 61.7% |
| Input tokens | 688,585 | 232,381 | 66.3% |
| Cache read tokens | 72,320 | 6,912 | 90.4% |
| Cache miss tokens | 616,265 | 225,469 | 63.4% |
| Output tokens | 1,764 | 750 | 57.5% |

Additional context: total run input tokens dropped from 1,039,554 to 593,518
(-42.9%). `tool_selection` fell from 66.2% of baseline input tokens to 39.2% of
current input tokens.

## 2. Deterministic prefetch plan ids

Current aggregate:

- Sessions: 8
- Top-level `deterministic_prefetch_plan_id == none/null/empty`: 0
- Top-level non-empty plan ids: 8
- Ledger entries: 34
- Ledger entries with none/null/empty plan id: 0
- Ledger entries with non-empty plan id: 34
- Ledger entries with `source == "deterministic_prefetch"`: 20

Baseline aggregate:

- Sessions: 8
- Top-level non-empty plan ids: 0
- Ledger entries with non-empty plan id: 0
- Ledger entries with `source == "deterministic_prefetch"`: 0

Current per-session ledger check:

| Session | Plan id | Entries | deterministic_prefetch | Other planner entries | Sources | Tool sequence |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `4b04ec1d-be97-4b7a-9445-f88d2bb4f83e` | `f5b62a93494ab4d4` | 3 | 3 | 0 | `deterministic_prefetch:3` | `memory.query`, `feedback.query_screening`, `feedback.query_runtime` |
| `4b3b6b28-a143-48e7-9232-5716fefbd5a4` | `4d35a4e7f1bf33e3` | 1 | 1 | 0 | `deterministic_prefetch:1` | `memory.query` |
| `70201afa-de10-44bd-b814-660abc113472` | `63830e032ebeb897` | 5 | 3 | 2 | `code_phase_planner:1`, `deterministic_prefetch:3`, `planner_selected:1` | `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_algorithm_file`, `context.read_branch_state` |
| `83cab56e-7809-4f2d-99a0-b6ce88a92ffb` | `300c196913a003d2` | 6 | 3 | 3 | `code_phase_planner:1`, `deterministic_prefetch:3`, `planner_selected:2` | `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_algorithm_file`, `context.read_algorithm_file`, `context.read_branch_state` |
| `86d19388-38ad-4552-8505-ee3317bfa7ce` | `4fa1eba68c81b8f7` | 5 | 3 | 2 | `code_phase_planner:1`, `deterministic_prefetch:3`, `planner_selected:1` | `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, `context.read_algorithm_file`, `context.read_branch_state` |
| `b55a9609-825b-4761-a655-0e7e00912aee` | `68459af041db06e6` | 3 | 3 | 0 | `deterministic_prefetch:3` | `memory.query`, `feedback.query_screening`, `feedback.query_runtime` |
| `d38029f4-44a5-4256-bab8-41f2d38d48d3` | `ca5e449dfaea4806` | 8 | 1 | 7 | `code_phase_planner:4`, `deterministic_prefetch:1`, `planner_selected:3` | `memory.query`, `context.read_branch_state`, `context.read_surface`, `context.read_algorithm_file`, `context.read_algorithm_file`, `context.read_algorithm_file`, `feedback.query_screening`, `feedback.query_runtime` |
| `db23b3fb-fac4-4b00-8274-00c7b5933c2c` | `7a9e2c5e08218199` | 3 | 3 | 0 | `deterministic_prefetch:3` | `memory.query`, `feedback.query_screening`, `feedback.query_runtime` |

Interpretation: deterministic prefetch is real and recorded. It removed default
feedback/memory prefetches from planner control, while still allowing planner
selection for genuinely variable follow-up reads.

## 3. Skipped stop behavior

Current aggregate:

- Ledger entries: 34
- `selected_tool/tool_name == "stop"`: 0
- skipped `stop`: 0
- skipped entries, any tool: 0

Baseline aggregate:

- Ledger entries: 47
- `selected_tool/tool_name == "stop"`: 12
- skipped `stop`: 12
- skipped entries, any tool: 12
- skip reasons: `planner_stop` = 8, `code_planner_stop` = 4

Conclusion: the prior skipped `stop` pattern is gone in current artifacts.

## 4. Observation and final prompt visibility

For the 20 current deterministic prefetch entries:

| Check | Count |
| --- | ---: |
| Deterministic prefetch ledger entries | 20 |
| Executed entries | 20 |
| `result_in_final_prompt == true` in ledger | 20 |
| Present in `compact_transcript` as deterministic prefetch observations | 20 |
| Present in `evidence_used` | 20 |
| Present in final prompt manifest `included_observation_ids` | 20 |
| Present in final prompt tool-result visibility entries | 20 |
| Present in `observation_ledger.observations` | 0 |
| Present in `observation_ledger.read_receipts` | 0 |

Prompt visibility statuses for deterministic prefetch entries:

- `summary`: 18
- `truncated`: 2
- `omitted`: 0
- `dedicated_projection`: 0

This means P1 did not remove the information from the final prompt path. The
safe conclusion is narrower: final prompt visibility is preserved, while the
`observation_ledger` object is incomplete for deterministic prefetch entries.

## 5. Negative-behavior audit

Run-level health comparison:

| Metric | Baseline | Current | Assessment |
| --- | ---: | ---: | --- |
| `run_complete` | true | true | unchanged |
| `run_validity_status` | valid | valid | unchanged |
| `run_completeness_status` | complete | complete | unchanged |
| `proposal_attempts_total` | 4 | 4 | no increase |
| `proposal_attempts_consumed` | 4 | 4 | no increase |
| `formal_screened_candidates` | 4 | 4 | no decline |
| `protocol_evaluated_candidates` | 4 | 4 | no decline |
| `quality_blocks` | 0 | 0 | no regression |
| `quality_block_ledger_count` | 0 | 0 | no regression |
| `telemetry_failed_experiments` | 0 | 0 | no regression |
| `telemetry_repair_attempts` | 0 | 0 | no regression |
| `telemetry_diagnostic_attempts` | 0 | 0 | no regression |
| `failure_categories` | `{}` | `{}` | no regression |
| Session `code_retry_failure_count` sum | 0 | 0 | no code repair failure increase |
| Session `schema_retry_feedback_count` sum | 0 | 0 | no schema retry increase |

Prompt/context visibility comparison:

- Current prompt manifests: 12 files.
- Render errors: 0.
- `rendered_prompt_available != true`: 0.
- Omitted sections: none.
- Section truncation count: 0.
- Visibility-ledger omitted entries: 8, all code-phase
  `proposal.schema_preview` / `proposal.target_permission_preview`; baseline has
  the same 8 omitted entries.
- Current visibility status counts across manifests:
  `full` 341, `dedicated_projection` 39, `summary` 133, `truncated` 3,
  `omitted` 8.
- Baseline visibility status counts:
  `full` 332, `dedicated_projection` 37, `summary` 135, `truncated` 0,
  `omitted` 8.

Required source/surface checks:

- Hypothesis source visibility:
  - create-new route compaction: `create_new_placeholder_visible`, preflight
    section included.
  - modify `local_search.py`, `acceptance.py`, `destroy_repair.py`:
    `full_dedicated_source_visible`, preflight section included.
- Code manifests:
  - `route_compaction.py` new file target has placeholder visible and section
    included.
  - `acceptance.py`, `local_search.py`, `destroy_repair.py` targets have full
    current source visible.
  - Each code manifest has 3 integration files and all integration file content
    is visible in the rendered prompt.

Decision/proposal boundary checks:

- All 8 hypothesis-target/hypothesis manifests have
  `context_profile_metadata.decision_features_excluded == true`.
- All 8 hypothesis-target/hypothesis manifests have
  `proposal_visibility_only == true`.
- Runtime/observability summaries carry `decision_features_excluded_count == 4`.
- This supports the intended boundary: proposal/tool observations remain
  tainted proposal visibility; Decision should continue reading only
  `DecisionFeatures`. Do not move cross-branch/proposal text into Decision to
  compensate for tooling.

Other observed differences:

- Baseline candidate mix: 4 quality candidates, 0 observability candidates.
- Current candidate mix: 1 quality candidate, 3 observability candidates.
- Current run has 8 `telemetry_effect_zero_diagnostics`; baseline has 0.
  These are diagnostics, not failed telemetry experiments, and the run remains
  valid/complete with 4 formal screened candidates. Treat this as a campaign
  outcome to monitor in 8R, not evidence that planner-call reduction removed
  required context.

## 6. 8R readiness

P1 meets the main optimization target: deterministic, default context/tooling
prefetch no longer burns LLM planner calls, and skipped `stop` is eliminated.
The artifacts do not show the negative behaviors requested in this audit:
proposal attempts did not increase, formal screened candidates did not drop,
quality blocks stayed at zero, telemetry failures stayed at zero, and code
repair/schema retry failures stayed at zero.

The remaining issue is not tool choice and should not be solved by sending
deterministic control flow back through the LLM planner. It is an audit-ledger
persistence issue: deterministic prefetch results must be first-class in
`observation_ledger.observations`/`read_receipts`, matching their presence in
`compact_transcript`, `evidence_used`, and prompt manifests.

Decision: P1 tooling behavior is effective enough for the next experimental
scale step, but a formally auditable 8R should either first fix this
`observation_ledger` persistence gap or include an explicit gate/waiver that
checks deterministic prefetch ids via prompt manifests and `evidence_used`.
