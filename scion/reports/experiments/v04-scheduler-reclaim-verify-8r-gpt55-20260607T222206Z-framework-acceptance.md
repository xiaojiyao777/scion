# Scheduler Reclaim 8R Framework Acceptance Audit

Experiment:
`/home/clawd/research/scion-experiments/v04-scheduler-reclaim-verify-8r-gpt55-20260607T222206Z-8r-gpt55-20260607T222206Z-claw/campaign`

Report date: 2026-06-07

## Executive Finding

Framework acceptance passes for this 8R run. The run completed the requested
screened/formal budget with `run_validity_status=valid`,
`effective_rounds_completed=8`, `formal_screened_candidates=8`,
`protocol_evaluated_candidates=8`, and
`scheduler_active_slot_blocked_attempts=0`.

The scheduler reclaim fix is accepted for the 8R gate objective: this campaign
no longer ends as a partial run at the active-slot pressure point. However, I
did not find a scheduler-origin `reclaim` event in this campaign. The exact
`new_branch_reclaim` path remains covered by the focused scheduler tests cited
in the remediation status; this campaign proves the full 8R no longer degrades
to `scheduler_active_slot_blocked` under the same pressure-style setup.

Recommendation: proceed to 12R. No framework blocker requires source changes
before 12R, but keep active-slot/reclaim telemetry under review because the
campaign did not directly exercise a scheduler-origin reclaim event.

## Required Context Applied

Architecture v3 was used as the acceptance boundary: LLM output is tainted
proposal data, while scheduler/resource governance and promotion decisions are
deterministic framework responsibilities. The v0.4 remediation status defines
`--rounds` / `max_rounds` as the effective screened/formal candidate budget and
separates proposal attempts, formal screened candidates, protocol-evaluated
candidates, repair/lifecycle counters, and
`scheduler_active_slot_blocked_attempts`. The prior 8R blocker report was used
as the regression target: the old run stopped after 5/8 completed candidates
because active-slot reclaim did not release capacity.

## Acceptance Matrix

| Area | Result | Evidence |
|---|---|---|
| 1. Run validity/accounting | PASS | `status.json`, `campaign_summary.json`, and `run_status.json` agree on valid complete 8R: requested 8, effective 8, formal screened 8, protocol evaluated 8, screening stage 8, quality blocks 0, blocked attempts 0. DB has 8 screening experiment rows, 8 scheduler rows, 8 raw metrics refs, and 8 audit payloads. |
| 2. Model and LLM trace | PASS | 59 LLM traces, all `model=gpt-5.5`, all `ok=true`. Request kinds: `hypothesis_target_intent=8`, `hypothesis=8`, `tool_selection=33`, `code=10`. I found no trace-level error, retry count, quality block, repair block, or skipped-stop marker. |
| 3. Proposal/tooling provenance | PASS with minor observation | All 59 trace-index rows have `prompt_manifest_artifact_ref`, visibility ledger ref, and visibility ledger digest. All 33 tool-selection traces have a non-empty `deterministic_prefetch_plan_id`, `tool_selection_ledger_ref`, and `tool_selection_ledger_digest`. Session outputs contain deterministic prefetch plan ids and tool-selection ledgers. Minor observation: the tool-selection ledger/provenance does not expose an explicit top-level `audit_only=true`; audit-only semantics are instead shown by placement in APS/provenance artifacts and downstream `decision_features_excluded`/`proposal_guidance_only` flags where the signal is used. |
| 4. Candidate replay identity | PASS | 8/8 DB screening audit payloads and 8/8 `artifacts/formal_candidates/**/candidate.patch.json` files have complete replay identity. Required keys are present: `problem_spec_hash`, `split_manifest_hash`, `seed_ledger_hash`, `patch_digest`, `patch_hash`, `selected_surface`, `protocol_version`, and `raw_metrics_ref`, plus status/degradation metadata. DB and artifact join by `raw_metrics_ref` had 8 joins and 0 mismatches for branch, protocol version, status, degraded flag, missing-key count, patch digest/hash, and selected surface. |
| 5. Case-level gate aliases | PASS | DB alias fields match for all 8 screening rows: `screening_case_*` equals `screening_case_level_gate_*` for wins/losses/ties/total/win rate. Branch cards use `case_level_positive_cases` and `case_level_negative_cases` for concrete case lists, while aggregate wins/losses/ties remain in `generic_evidence_summary`; I found no naming collision with gate aggregate fields. |
| 6. Scheduler reclaim fix | PASS for 8R gate; exact reclaim path not exercised | `scheduler_active_slot_blocked_attempts=0`, `active_slot_blocked_attempts=0`, `blocked_attempts=0`, and stopped reason is `max_rounds_exhausted`. DB scheduler rows have no `capacity_blocked` and no `reclaim`-like payloads. One branch, `3a83f295`, ended `parked_lineage`, but the event was a post-finalizer lifecycle park from `repair_diagnostic`, not scheduler-origin reclaim. |
| 7. Runtime/fresh champion decision risk | PASS with watch item | Champion table still has only initial champion v1 and no `promotion_experiment_id`. DB decisions are only 5 `continue_explore` and 3 `abandon`; no promote or validation queue. Runtime/fresh champion evidence appears as gate/scheduler/proposal observation. Low/cached champion runtime is explicitly excluded from aggregate runtime evidence and marked `proposal_guidance_only` / `decision_features_excluded` in runtime evidence policy. Watch item: deterministic `DecisionFeatures` still include numeric `runtime_stats` and runtime reason codes, so future reports should keep checking that these remain structured guard/diagnostic inputs rather than standalone promotion evidence. |

## Accounting Details

`status.json`:

- `stopped_reason=max_rounds_exhausted`
- `last_stop_reason=max_rounds_exhausted`
- `run_validity_status=valid`
- `requested_rounds=8`
- `effective_rounds_completed=8`
- `formal_screened_candidates=8`
- `protocol_evaluated_candidates=8`
- `protocol_stage_counts.screening=8`
- `quality_blocks=0`
- `proposal_attempts_consumed=8`
- `proposal_attempts_total=8`
- `loop_steps=8`
- `scheduler_active_slot_blocked_attempts=0`

`campaign_summary.json` reports the same core values. `run_status.json`
reports `wrapper_exit_status=0`, `campaign_exit_status=complete`,
`run_complete=true`, `completed_requested_rounds=true`, and
`run_validity_status=valid`.

DB and raw metrics checks:

- DB `experiment_events`: 8 `experiment` rows at `stage=screening`.
- DB `experiment_events`: 8 `scheduler_result` rows, 0 `capacity_blocked`.
- DB raw metrics refs: 8/8 present on disk.
- Raw metrics: all 8 are `stage=screening` and `complete=true`.
- Raw metrics case/pair counts match DB totals:
  - seven rows are 8 cases / 16 pairs;
  - one expanded row is 12 cases / 24 pairs.

Counter semantics are correct for this run:

- `proposal_attempts_total=8` and `proposal_attempts_consumed=8` count the
  proposal/LLM attempts that produced the 8 formal screening attempts.
- `formal_screened_candidates=8` counts candidates that reached Protocol
  screening.
- `protocol_evaluated_candidates=8` counts Protocol-evaluated candidates, all
  in screening.
- `quality_blocks=0` means no proposal-quality rejection consumed the run.
- `scheduler_active_slot_blocked_attempts=0` means no non-counted active-slot
  capacity skip occurred.

## Scheduler Evidence

Scheduler rows:

| scheduler_slot | scheduler_reason | count |
|---|---|---:|
| `explore_new` | `new_exploration_slot_available` | 5 |
| `exploit_weak_positive` | `weak_positive_signal_followup` | 1 |
| `repair_diagnostic` | `same_branch_low_signal_observation_sample` | 1 |
| `exploit_weak_positive` | `fresh_champion_runtime_replay_followup` | 1 |

No row has `scheduler_slot=capacity_blocked`, and no scheduler audit payload
contains a reclaim-like active-slot reconciliation event. Status and summary
also report `active_slot_blocked_attempts=0`, `blocked_attempts=0`, and
`scheduler_active_slot_blocked_attempts=0`.

The only `parked_lineage` branch is
`3a83f295-bde4-44f7-bf49-c270a984537a`. Its DB branch row has
`branch_lifecycle_policy_blocks=1` and a `last_branch_lifecycle_policy_block`
with `reason=park_lineage`. The corresponding scheduler result is round 6:
`scheduler_slot=repair_diagnostic`,
`scheduler_reason=same_branch_low_signal_observation_sample`,
`post_finalizer_lifecycle_action=park_lineage`, and
`post_finalizer_active_slot_release_reason=parked_lineage`. This is lifecycle
release, not scheduler-origin reclaim.

## LLM Trace And Provenance

Trace counts:

| request_kind | count |
|---|---:|
| `hypothesis_target_intent` | 8 |
| `hypothesis` | 8 |
| `tool_selection` | 33 |
| `code` | 10 |

All 59 traces are `gpt-5.5` and `ok=true`. All trace-index entries have
prompt manifest refs and visibility ledger refs/digests. All tool-selection
traces carry `scion-tooling-audit-provenance.v1` with non-empty deterministic
prefetch plan id and tool-selection ledger digest/ref.

## Replay Identity

All candidate patch artifacts use `scion.formal_replay_identity.v1` with
`status=complete`, `identity_status=complete`, `identity_degraded=false`, and
empty missing-key lists. The DB audit payload uses the same identity values.
The join by `raw_metrics_ref` found 8/8 rows and 0 mismatches across:

- branch id
- protocol version
- identity status
- degraded flag
- missing-key count
- patch digest
- patch hash
- selected surface

All selected surfaces are `solver_design`; all protocol versions are
`0.4-cvrp-formal-readiness`.

## Decision Boundary

No candidate was promoted. The champions table contains only initial
champion v1, with no promotion experiment id. Decision rows are:

- `continue_explore`: 5
- `abandon`: 3
- `promote`: 0
- validation/frozen queue: 0

Runtime evidence did affect diagnostics and scheduler/lifecycle observations:
examples include `SCREENING_RUNTIME_BUDGET_SATURATION`,
`CANDIDATE_RUNTIME_BUDGET_SATURATION`,
`fresh_champion_runtime_replay_followup`, and low/cached champion runtime
exclusions. I did not find evidence that runtime or fresh-champion evidence
formed an independent second Decision/promotion path. The policy text in
status explicitly says low/cached runtime aggregate evidence is excluded and
kept as audit/proposal guidance.

## Final Judgment

Pass. This run is acceptable as the scheduler reclaim remediation 8R framework
gate. It validates that the previously blocking 8R scenario no longer ends in
`valid_partial_interrupted` due to `scheduler_active_slot_blocked`, and it keeps
the provenance, replay identity, accounting, case-gate naming, and decision
boundary checks intact.

Proceed to 12R. Do not require another source fix first. The only follow-up is
to keep monitoring for a real scheduler-origin reclaim event in longer runs,
because this 8R campaign did not directly exercise that exact path.
