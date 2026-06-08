# Scheduler Reclaim 12R Framework And Quality-Block Acceptance Audit

Experiment:
`/home/clawd/research/scion-experiments/v04-scheduler-reclaim-verify-12r-gpt55-20260607T233323Z-12r-gpt55-20260607T233323Z-claw/campaign`

Report date: 2026-06-08

## Executive Finding

Framework acceptance passes for this 12R run. The run completed the requested
screened/formal budget with `run_validity_status=valid`,
`effective_rounds_completed=12`, `formal_screened_candidates=12`,
`protocol_evaluated_candidates=12`, and
`scheduler_active_slot_blocked_attempts=0`.

The one quality block is correctly accounted as a non-counted proposal attempt:
`proposal_attempts_total=13` / `proposal_attempts_consumed=13` produced 12
formal screening candidates plus 1 `proposal_block` scheduler result with
`counts_toward_max_rounds=false`. The block was reasonable quality governance,
not an over-strict research-flow blocker: the blocked proposal failed algorithm
smoke after three code repair attempts with solver runtime errors and missing
declared-mechanism activation instrumentation. It never became a formal
candidate and did not prevent the campaign from reaching 12/12 formal
screening.

Recommendation: proceed to 20R. No must-fix framework blocker is exposed by
this 12R campaign. Keep the same two watch items in the 20R report: whether a
real scheduler-origin `scheduler_active_slot_reclaim` event appears, and
whether runtime/fresh-champion evidence remains structured diagnostic input
rather than an independent promotion path.

## Required Context Applied

Architecture v3 was used as the acceptance boundary: LLM output is tainted
proposal data; Contract, Verification, Protocol, scheduler/resource governance,
and Decision are deterministic framework responsibilities; Decision must only
read structured `DecisionFeatures`, not LLM free text.

The v0.4 remediation status defines `--rounds` / `max_rounds` as the effective
screened/formal candidate budget and separates formal screened candidates from
proposal attempts, repair attempts, quality/lifecycle blocks, and
`scheduler_active_slot_blocked_attempts`.

The prior 8R framework acceptance report is the immediate regression baseline:
the fixed 8R run completed valid with 8/8 formal candidates, no quality blocks,
no active-slot blocked attempts, complete tool provenance, complete replay
identity, and no campaign-level scheduler-origin reclaim event.

## Acceptance Matrix

| Area | Result | Evidence |
|---|---|---|
| 1. Run validity/accounting | PASS | `status.json`, `campaign_summary.json`, and `run_status.json` agree on valid complete 12R: requested 12, effective 12, formal screened 12, protocol evaluated 12, screening stage 12, quality blocks 1, proposal attempts 13, loop steps 13, scheduler active-slot blocked attempts 0. DB has 12 screening experiment rows, 13 scheduler rows, 26 agentic proposal session rows, and 12 raw metrics refs present on disk. |
| 2. Model and LLM trace | PASS | 92 trace files and 92 trace-index entries, all `model=gpt-5.5`, all `ok=true`. Request kinds: `hypothesis_target_intent=13`, `hypothesis=13`, `tool_selection=46`, `code=20`. Schema retry count is 0. Code retry occurred in three code sessions: two completed after 2 retries each; the blocked session failed after 3 retries. Tool-loop skipped rows are ordinary skipped tool executions after required context was satisfied, not trace errors. |
| 3. Quality block | PASS | The blocked proposal is branch `15acd613-b878-4b67-9358-d6f7b90f7d2d`, hypothesis `2fe0b93e-fc9f-45aa-b26a-90886b1f309c`, session `3ad4ffad-3271-40da-889a-e24ac6579521`, mechanism `staged_search_budget`, target `policies/baseline_modules/scheduler.py`. Scheduler row 9 records `attempt_kind=proposal_block`, `counts_toward_max_rounds=false`, and `result_reason=agent_quality_blocked`. The proposal failed algorithm smoke with `_SimulatedAnnealing.cool()` signature errors and missing activation instrumentation for declared mechanism `staged_search_budget`. |
| 4. Proposal/tooling provenance | PASS | All 26 session-index rows require and carry prompt manifest refs. All 92 trace-index rows carry prompt manifest refs plus visibility ledger refs/digests. All 46 tool-selection traces carry `scion-tooling-audit-provenance.v1` with non-empty `deterministic_prefetch_plan_id`, `tool_selection_ledger_ref`, and `tool_selection_ledger_digest`. All 12 completed outputs have tool-selection ledgers. The provenance is audit-only by placement in trace/index/output audit fields and by separation from provider-visible user prompts; no explicit top-level `audit_only=true` field is present. |
| 5. Replay identity and artifact | PASS | 12/12 DB screening audit payloads and 12/12 `artifacts/formal_candidates/**/candidate.patch.json` files have complete replay identity. Required keys are present: `problem_spec_hash`, `split_manifest_hash`, `seed_ledger_hash`, `patch_digest`, `patch_hash`, `selected_surface`, `protocol_version`, and `raw_metrics_ref`. DB and artifact join by `raw_metrics_ref` has 12 joins and 0 mismatches. `artifacts/formal_candidates/index.jsonl` has 12 rows. |
| 6. Case-level gate aliases | PASS | All 12 DB screening rows have matching legacy and explicit alias fields: `screening_case_*` equals `screening_case_level_gate_*` for wins, losses, ties, total, and win rate. Raw metrics case/pair totals also match DB totals: 11 candidates have 8 cases / 16 pairs; 1 expanded candidate has 12 cases / 24 pairs. |
| 7. Scheduler reclaim and active-slot | PASS for 12R completion; exact reclaim path not campaign-exercised | `scheduler_active_slot_blocked_attempts=0`, `active_slot_blocked_attempts=0`, and no scheduler DB payload contains `capacity_blocked` or `reclaim`. Scheduler rows include active-slot releases through finalizer/lifecycle paths, but no scheduler-origin `scheduler_active_slot_reclaim`. As in the 8R report, the exact reclaim path remains validated by focused scheduler tests cited in remediation status; this campaign proves the 12R run is not partial and not active-slot blocked. |
| 8. Runtime/fresh champion/Decision boundary | PASS with watch item | Champions table has only initial champion v1, with no `promotion_experiment_id`. Decision rows are 10 `continue_explore` and 2 `abandon`; no promote, validation queue, or frozen stage appears. Runtime/fresh-champion reason codes appear in structured decision reasons and runtime policy artifacts, but runtime policies mark low/cached or incomplete runtime evidence as `decision_features_excluded=true` and `proposal_guidance_only=true`. `DecisionFeatures` contain structured numeric/enumerated runtime fields and no long free-text fields. |

## Accounting Details

`status.json` and `campaign_summary.json` agree on the core counters:

- `stopped_reason=max_rounds_exhausted`
- `run_validity_status=valid`
- `requested_rounds=12`
- `effective_rounds_completed=12`
- `formal_screened_candidates=12`
- `protocol_evaluated_candidates=12`
- `protocol_stage_counts.screening=12`
- `quality_blocks=1`
- `proposal_attempts_consumed=13`
- `proposal_attempts_total=13`
- `loop_steps=13`
- `scheduler_active_slot_blocked_attempts=0`
- `active_slot_blocked_attempts=0`
- `blocked_attempts=1`

`run_status.json` reports `wrapper_exit_status=0`,
`campaign_exit_status=complete`, `run_complete=true`,
`completed_requested_rounds=true`, and `run_validity_status=valid`.

DB and raw metrics checks:

- DB `experiment_events`: 12 `experiment` rows at `stage=screening`.
- DB `experiment_events`: 13 `scheduler_result` rows.
- DB `experiment_events`: 26 `agentic_proposal_session` rows.
- DB raw metrics refs: 12/12 present on disk.
- Raw metrics: all 12 are `stage=screening` and `complete=true`.
- Raw metrics case/pair totals match DB totals: 11 rows are 8 cases / 16
  pairs; 1 expanded row is 12 cases / 24 pairs.

Counter semantics are correct for this run:

- `formal_screened_candidates=12` counts only candidates that reached Protocol
  screening.
- `protocol_evaluated_candidates=12` counts Protocol-evaluated candidates, all
  in screening.
- `proposal_attempts_total=13` counts all proposal attempts consumed by the
  loop: 12 formal screening candidates plus the one proposal-quality block.
- `quality_blocks=1` and `blocked_attempts=1` refer to the same non-counted
  proposal block.
- `scheduler_active_slot_blocked_attempts=0` means the active-slot capacity
  failure from the earlier partial 8R attempt did not recur.

## Quality-Block Special Analysis

The quality block occurred after the eighth formal screening candidate and
before the ninth. Scheduler row 9 is:

- timestamp: `2026-06-08T00:29:38.028450`
- branch: `15acd613-b878-4b67-9358-d6f7b90f7d2d`
- hypothesis: `2fe0b93e-fc9f-45aa-b26a-90886b1f309c`
- scheduler slot: `repair_diagnostic`
- scheduler reason: `same_branch_low_signal_observation_sample`
- audit `attempt_kind=proposal_block`
- audit `counts_toward_max_rounds=false`
- result reason: `agent_quality_blocked`

The blocked proposal session is
`3ad4ffad-3271-40da-889a-e24ac6579521`. Its hypothesis was a
`staged_search_budget` change on `policies/baseline_modules/scheduler.py`,
intended to modify VNS/ALNS budget staging and activation triggers.

The block reason is concrete and framework-relevant:

- session status: `failed`
- termination reason: `code_generation_failed`
- failure category: `algorithm_smoke_failure`
- code retry failure count: 3
- schema retry feedback count: 0
- smoke evidence files: 4 failed smoke evidence artifacts
- smoke failure code: `algorithm_smoke_runtime_failure`
- runtime audit failure: `solver_algorithm_errors=1`
- concrete runtime errors:
  `_SimulatedAnnealing.cool() got an unexpected keyword argument
  'best_improved'` and `_SimulatedAnnealing.cool() takes 1 positional argument
  but 5 were given`
- telemetry diagnostic: declared mechanism `staged_search_budget` lacked
  direct activation instrumentation via `context.record_iteration(...)` or
  equivalent mechanism activation evidence.

This is not over-strict quality governance. The candidate had a real runtime
interface error in solver execution, and the declared mechanism lacked required
activation observability. Allowing it into formal screening would have polluted
Protocol with a fallback/error path rather than a valid candidate algorithm.

The block did not disrupt branch or cross-branch research flow. It did not
increment the formal-screened budget, did not create a candidate patch artifact,
and did not introduce a raw metrics ref. The next formal candidate was produced
on branch `ee4bfde3-3fed-4bde-b25f-1c0c97c7c1de` at
`2026-06-08T00:34:59.535038`, and the campaign continued to 12/12 formal
screening.

## LLM Trace And Retry Details

Trace distribution:

| request_kind | count |
|---|---:|
| `hypothesis_target_intent` | 13 |
| `hypothesis` | 13 |
| `tool_selection` | 46 |
| `code` | 20 |

All 92 traces are `gpt-5.5` and `ok=true`.

Session-level retry summary:

- `schema_retry_feedback_count`: 0 total.
- Code retry total: 7 retry failures across three code sessions.
- Two sessions completed after code repair:
  - `c559234f-54cb-4e3d-a114-08cf8e16954a`, branch `fe3b564a...`,
    `search_observability_bridge`, 2 retries, completed.
  - `1f7b1641-3208-4c6a-be99-ead81d5c4527`, branch `ee4bfde3...`,
    `plateau_escape_vns_gating`, 2 retries, completed.
- One session failed after code repair:
  - `3ad4ffad-3271-40da-889a-e24ac6579521`, branch `15acd613...`,
    `staged_search_budget`, 3 retries, blocked.

Tool-loop stop/skip observations:

- Stop reasons found in outputs: `required_context_satisfied=52` and
  `code_planner_stop=12`.
- Skipped tool rows are normal `status=skipped` entries for optional/redundant
  tool calls after required context was satisfied. I found no trace-level error
  and no skipped-stop condition that changed run validity.

## Proposal And Tooling Provenance

Trace/index provenance is complete:

- 26/26 session-index rows have required prompt manifest refs.
- 92/92 trace-index rows have `prompt_manifest_artifact_ref`,
  `prompt_visibility_ledger_ref`, and `prompt_visibility_ledger_digest`.
- 46/46 tool-selection trace-index rows have provenance schema
  `scion-tooling-audit-provenance.v1`.
- 46/46 tool-selection rows have non-empty
  `deterministic_prefetch_plan_id`, `tool_selection_ledger_ref`, and
  `tool_selection_ledger_digest`.
- 12/12 completed agentic proposal outputs have a `tool_selection_ledger`.

Audit-only status: the run does not expose an explicit top-level
`audit_only=true` boolean. The audit-only boundary is nevertheless preserved by
where the data lives: tool-selection provenance is stored in trace/index/output
audit fields, and the deterministic prefetch plan id / tool-selection ledger
digest were absent from provider-visible user prompts in all 46 tool-selection
trace files checked. I also found no DecisionFeatures field sourced from
tool-selection provenance.

## Replay Identity And Case Aliases

All 12 candidate patch artifacts use complete formal replay identity. The DB
audit payload and artifact identity agree for each `raw_metrics_ref` on:

- `problem_spec_hash`
- `split_manifest_hash`
- `seed_ledger_hash`
- `patch_digest`
- `patch_hash`
- `selected_surface`
- `protocol_version`
- `raw_metrics_ref`

There are 12/12 DB-to-artifact joins and 0 mismatches. The formal candidate
index has 12 rows.

Case-level gate aliases are consistent for all 12 screening rows:

- `screening_case_wins == screening_case_level_gate_wins`
- `screening_case_losses == screening_case_level_gate_losses`
- `screening_case_ties == screening_case_level_gate_ties`
- `screening_case_total == screening_case_level_gate_total`
- `screening_case_win_rate == screening_case_level_gate_win_rate`

## Scheduler Reclaim And Active Slot

Scheduler rows:

| scheduler_slot | scheduler_reason | count |
|---|---|---:|
| `explore_new` | `new_exploration_slot_available` | 4 |
| `explore_new` | `plateau_reroute_clean_fork` | 3 |
| `repair_diagnostic` | `same_branch_low_signal_observation_sample` | 2 |
| `repair_diagnostic` | `runtime_diagnostic_followup` | 1 |
| `refine_active` | `same_branch_low_signal_observation_sample` | 1 |
| `refine_active` | `plateau_gate_same_branch_diagnostic_refinement` | 1 |
| `exploit_weak_positive` | `fresh_champion_runtime_replay_followup` | 1 |

No scheduler row has `capacity_blocked`, and no scheduler audit payload
contains `reclaim` or `scheduler_active_slot_reclaim`. The run still completed
valid with `scheduler_active_slot_blocked_attempts=0`.

Several rows show active-slot release through finalizer/lifecycle governance,
for example `repeated_no_effect_zero_effect_slot_release`,
`parked_lineage`, and `terminal_state`. These are not scheduler-origin reclaim
events. Therefore the exact `new_branch_reclaim` path remains campaign-unseen
in this 12R run. Per remediation status, that exact path is covered by focused
scheduler reclaim tests and broader scheduler/core tests; this campaign adds
end-to-end evidence that 12R no longer becomes partial under the post-fix
scheduler/accounting setup.

## Runtime, Fresh Champion, And Decision Boundary

No candidate was promoted. The champions table contains only initial champion
v1 and no `promotion_experiment_id`.

Decision rows:

- `continue_explore`: 10
- `abandon`: 2
- `promote`: 0
- validation queue: 0
- frozen stage: 0

Runtime and fresh-champion signals are visible, but they remain structured
diagnostic/proposal inputs:

- Runtime/fresh-champion reason codes appear in decision reasons, including
  `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`,
  `SCREENING_RUNTIME_BUDGET_SATURATION`, and
  `CANDIDATE_RUNTIME_BUDGET_SATURATION`.
- Runtime evidence policy marks low/cached or incomplete runtime evidence as
  `decision_features_excluded=true`, `proposal_guidance_only=true`, and
  `standalone_optimization_signal=false`.
- Runtime gate visibility similarly uses `proposal_visibility_only=true`.
- `DecisionFeatures` contain structured numeric/enumerated fields such as
  `runtime_stats`, `runtime_guard_passed`, `runtime_guard_elapsed_ms`,
  `decision_reason_codes`, and `gate_observation_reason_codes`; I found no
  long free-text fields in `DecisionFeatures`.

This is consistent with the architecture boundary. Runtime evidence can inform
guarding, diagnostics, and follow-up scheduling, but I found no second Decision
Layer and no runtime/fresh-champion path that bypassed structured evidence for
promotion or validation.

## Final Judgment

Pass. The 12R run is framework-valid and quality-governed:

- Complete valid 12/12 formal screening.
- Correct 13 proposal attempts = 12 formal candidates + 1 non-counted quality
  block.
- All LLM traces are `gpt-5.5` and successful at the trace level.
- Tool-selection provenance and prompt manifest coverage are complete.
- Replay identity is complete for DB audit payloads and candidate artifacts.
- Case-level gate aliases are consistent.
- Active-slot blocked attempts remain zero.
- Decision boundary remains structured and deterministic.

Proceed to 20R. No source or test repair is required before the next run. The
20R report should continue to watch for a campaign-observed
`scheduler_active_slot_reclaim` event and for any drift in runtime/fresh
champion Decision boundary semantics.
