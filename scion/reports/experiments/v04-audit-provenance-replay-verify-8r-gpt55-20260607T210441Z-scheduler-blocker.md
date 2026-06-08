# 8R Scheduler Active Slot Blocker Analysis

Experiment:
`/home/clawd/research/scion-experiments/v04-audit-provenance-replay-verify-8r-gpt55-20260607T210441Z-8r-gpt55-20260607T210441Z-claw/campaign`

Report date: 2026-06-07

## Executive Finding

The 8R run did not stop because of proposal quality or protocol failure. It
stopped after three consecutive scheduler-only `capacity_blocked` skips:
`requested_rounds=8`, `effective_rounds_completed=5`,
`formal_screened_candidates=5`, `protocol_evaluated_candidates=5`,
`quality_blocks=0`, `scheduler_active_slot_blocked_attempts=3`, and
`scheduler_active_slot_blocked_attempt_limit=3`.

Root cause: after the fifth formal screening candidate, the scheduler wanted a
clean fork (`runtime_evidence_completeness_clean_fork`) but all three active
slots were occupied by active research branches. The reclaim path identified
all three branches as reclaim candidates, but refused to park any of them
because none carried a Decision-origin park marker. The loop then retried the
same scheduler state three times and hit the hard active-slot blocked cap.

Judgment: this is primarily a framework defect in the scheduler/lifecycle
handoff, with a secondary configuration sensitivity (`max_active_branches=3`).
The resource governance rule is conceptually valid, but the current
implementation lets scheduler-owned clean-fork pressure deadlock behind a
Decision-origin marker requirement that no eligible active branch had reached.

## Required Design Context

Architecture v3 treats scheduler/resource governance as deterministic code, not
LLM choice: deterministic systems own "调度与决策", while LLM output remains
tainted proposal data. It also states that the Scheduler solves compute budget
and branch governance, not scientific truth
(`/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md:34-49`,
`:147-158`).

The remediation status for v0.4 explicitly separates
`scheduler_active_slot_blocked_attempts` from effective screened rounds and
describes active-slot capacity, same-mechanism follow-up, clean fork,
park/reclaim, and diagnostic repair as scheduler/lifecycle governance rather
than Decision-layer promotion/abandon decisions
(`/home/clawd/research/or-autoresearch-agent/scion/reports/architecture-audit-v0.4/remediation-status.md:8-27`).

This means the observed stop should be evaluated as a deterministic
resource/lifecycle failure mode, not as failed science and not as an LLM-quality
block.

## Run Accounting

From `status.json`:

- `stopped_reason=last_stop_reason=scheduler_active_slot_blocked`
- `run_validity_status=valid_partial_interrupted`
- `requested_rounds=8`
- `effective_rounds_completed=5`
- `formal_screened_candidates=5`
- `protocol_evaluated_candidates=5`
- `protocol_stage_counts.screening=5`
- `quality_blocks=0`
- `loop_steps=8`
- `proposal_attempts_consumed=5`
- `proposal_attempts_total=8`
- `scheduler_active_slot_blocked_attempts=3`
- `scheduler_active_slot_blocked_attempt_limit=3`

`run_validity.operator_action` correctly says this is scientifically useful
partial evidence, not completion of the requested 8R campaign.

## Concrete Trigger Contexts

The three blocked events are in `scion.db` as `scheduler_result` rows, all after
the fifth screening result:

| # | timestamp | scheduler_slot | scheduler_reason | result |
|---|---|---|---|---|
| 1 | 2026-06-07T21:38:54.158429 | `capacity_blocked` | `active_branch_limit_reached` | `skip`, non-counted |
| 2 | 2026-06-07T21:38:54.303186 | `capacity_blocked` | `active_branch_limit_reached` | `skip`, non-counted |
| 3 | 2026-06-07T21:38:54.442517 | `capacity_blocked` | `active_branch_limit_reached` | `skip`, non-counted |

Each event had identical active-slot hard-cap context:

- `active_slot_hard_cap.reason=active_slot_hard_cap_blocked`
- `active_slot_hard_cap.used=3`
- `active_slot_hard_cap.max_active_branches=3`
- active slot branch IDs:
  - `b4aa5b76-2959-48b1-8819-b177c6c10b65`
  - `8b8ce21b-ca6f-4433-8a76-2bd67989a1b3`
  - `981a9e0a-252d-450d-a6b2-b2ab02a8b757`

Each event also had identical reclaim context:

- `active_slot_reconciliation.mode=new_branch_reclaim`
- `before_used=3`, `after_used=3`, `max_active_branches=3`
- `candidate_branch_ids=[b4aa5b76, 981a9e0a, 8b8ce21b]`
- `parked_branch_ids=[]`
- `decision_origin_marker_required=true`
- `blocked_reason=decision_origin_lifecycle_marker_missing`
- `marker_missing_branch_ids=[b4aa5b76, 981a9e0a, 8b8ce21b]`

At final status, `campaign_summary.json` and `scion.db` agree on these active
branches:

| branch | DB state | code status | tier | slot status | policy markers |
|---|---|---|---|---|---|
| `b4aa5b76` | `explore` | `active_no_effect` | `no_effect` | `active_slot` | no lifecycle policy block, no park marker |
| `8b8ce21b` | `explore` | `active_weak_positive` | `weak_positive` | `active_slot` | no lifecycle policy block, no park marker |
| `981a9e0a` | `explore` | `active_no_effect` | `no_effect` | `active_slot` | no lifecycle policy block, no park marker |

The abandoned branch `9237ff13` was not part of active-slot pressure. It was
soft lifecycle archived after a quality-regression/no-positive-CI screening
result and had state `abandoned`.

## Branch-Level Evidence

### `b4aa5b76`

Mechanism: `route_merge_vns`.

Evidence summary:

- screening tier `no_effect`
- wins/losses/ties: `0/0/8`
- pair wins/losses/ties: `0/0/16`
- `median_delta=0.0`, `ci_low=0.0`, `ci_high=0.0`
- runtime evidence confidence `sufficient`
- runtime evidence pressure count `1`
- lifecycle action reason codes:
  `SCREENING_NEUTRAL_SIGNAL_CONTINUE`,
  `SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`
- branch card allowed next action: `clean_fork`
- `same_mechanism_followup_required=true`
- `clean_fork_policy=clean_fork_required_for_new_mechanism`
- `counts_toward_active_slots=true`
- `current_head_active_slot_release_reason=""`

Although scheduler audit earlier recognized it as a low-value release candidate
with `release_reason=retained_checkpoint_no_effect_current_head`, the active
slot release policy did not actually release it because lifecycle budget was not
exhausted.

### `8b8ce21b`

Mechanism: `phase_budgeted_alns_vns`.

Evidence summary:

- final screening tier `weak_positive`
- final case wins/losses/ties: `0/0/8`
- pair wins/losses/ties: `3/3/10`
- positive cases: `B-n52-k7`, `E-n101-k8`, `P-n101-k4`
- negative cases: `A-n32-k5`, `B-n31-k5`, `P-n40-k5`
- `median_delta=0.0`, `ci_low=-4.5`, `ci_high=3.0`
- runtime evidence confidence `low_cached_champion`
- runtime aggregate excluded due to cached/low-confidence champion runtime
- runtime evidence pressure count `2`
- lifecycle action reason codes:
  `SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL`,
  `SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`
- branch card says `followup_recommended=true`
- allowed next actions: `refine_checkpoint`, `tune`, `integrate`,
  `parameterize`
- `counts_toward_active_slots=true`
- no park/reclaim marker

Immediately before the block, this branch was the reason clean fork was chosen:
the fifth scheduler result suppressed weak-positive follow-up and selected
`runtime_evidence_completeness_clean_fork` because this branch had
`runtime_evidence_pressure_count=2`.

### `981a9e0a`

Mechanism: `route_pool_recombine`.

Evidence summary:

- screening tier `no_effect`
- wins/losses/ties: `0/0/12`
- pair wins/losses/ties: `0/0/24`
- `median_delta=0.0`, `ci_low=0.0`, `ci_high=0.0`
- runtime evidence confidence `low_cached_champion`
- runtime evidence pressure count `1`
- lifecycle action reason codes:
  `SCREENING_NEUTRAL_SIGNAL_CONTINUE`,
  `SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`
- branch card allowed next action: `clean_fork`
- `same_mechanism_followup_required=true`
- `clean_fork_policy=clean_fork_required_for_new_mechanism`
- `counts_toward_active_slots=true`
- no park/reclaim marker

This was the branch whose fifth formal screening result completed at
2026-06-07T21:38:53.919217. The following scheduler result selected clean fork
for runtime evidence completeness; the next three loop steps were blocked
without further protocol or proposal work.

## Source-Level Trigger Path

`BranchStepRunner.run_one_step` first reconciles active-slot overflow, then
calls `scheduler.select_next`. If the scheduler returns `at_capacity`, it calls
`reclaim_active_slot_for_new_branch`; only if that reconciliation changes state
does it re-read active branches and reselect. If it remains at capacity, it
returns `StepResult(action="skip", reason="max_active_branches reached",
counts_toward_max_rounds=False,
attempt_kind="scheduler_active_slot_blocked")`
(`/home/clawd/research/or-autoresearch-agent/scion/scion/core/branch_step_runner.py:98-163`).

`Scheduler.select_next` computes active-slot branches separately from
schedulable branches. It excludes retained no-effect heads and other low-value
or lifecycle-exhausted branches from `schedulable`, but those same branches may
still count toward active-slot capacity. When no eligible/preferred research
branch can be run and `active_for_slots` is at the cap, it returns
`SchedulerAction(action="at_capacity", reason="active_branch_limit_reached",
slot="capacity_blocked")`
(`/home/clawd/research/or-autoresearch-agent/scion/scion/core/scheduler.py:149-216`,
`:292-334`).

`active_slots.reclaim_active_slot_for_new_branch` tries to reduce used slots
from the cap to `limit - 1` before admitting a clean fork
(`/home/clawd/research/or-autoresearch-agent/scion/scion/core/scheduling/active_slots.py:221-247`).
However, `_reconcile_active_slots` will not park a candidate unless
`branch_has_decision_origin_park_marker(branch)` is true; otherwise it records
the branch in `marker_missing_branch_ids` and continues
(`/home/clawd/research/or-autoresearch-agent/scion/scion/core/scheduling/active_slots.py:336-365`).

The active-slot policy can also release scheduler-owned low-value slots, but
`scheduler_owned_active_slot_release_reason` explicitly withholds release for
`retained_checkpoint_no_effect_current_head` unless lifecycle budget is
exhausted
(`/home/clawd/research/or-autoresearch-agent/scion/scion/core/scheduling/signals.py:57-85`).
In this run, the two no-effect branches had retained checkpoints and clean-fork
guidance, but no lifecycle budget exhaustion and no Decision-origin park marker.

`CampaignLoop` then classifies the skip as `scheduler_active_slot_blocked` and
increments the non-counted active-slot blocked counter. The configured/default
limit is `max(2, min(3, requested_rounds))`; for `requested_rounds=8`, the cap
is `3`, so the third repeated skip sets `final_reason` to
`scheduler_active_slot_blocked`
(`/home/clawd/research/or-autoresearch-agent/scion/scion/core/campaign_loop.py:270-276`,
`:401-410`, `:593-600`).

## Why No Clean Fork Or Reclaim Happened

No clean fork happened after the fifth formal candidate because all three
active slots were occupied. The scheduler wanted a clean fork, but
`len(active_for_slots) < max_active_branches` was false.

No reclaim happened because the reclaim candidates lacked Decision-origin
park markers. This was not because the candidates were scientifically valuable
enough to force retention:

- two were no-effect branches with clean-fork-only next action;
- one was weak-positive but had low/cached runtime evidence pressure count `2`,
  which is exactly why clean fork was selected;
- none had pending retry, repair focus, telemetry repair mechanism IDs, or
  active lifecycle policy blocks;
- `last_branch_lifecycle_policy_block_json` was `{}` for all three active
  branches.

The system therefore reached a narrow handoff gap: scheduler evidence says a
clean fork is preferable and reclaim candidates exist, but the reclaim writer
requires a stronger lifecycle marker than the lifecycle policy had produced.

## Design Assessment

This is not a Decision Layer contamination problem in the strict sense. The
blocked state was produced by deterministic scheduler/lifecycle code and the
audit payloads explicitly mark runtime/low-value guidance as proposal-guidance
or audit-only where appropriate.

It is, however, a "second Decision Layer" risk if fixed incorrectly. If
scheduler-owned reclaim starts parking or abandoning branches using raw
proposal text, free-form summaries, or LLM-authored rationale, it would violate
Architecture v3. The correct fix must keep reclaim based on structured
branch-state/evidence fields and reason codes.

The current behavior conflicts with v3 operational intent because scheduler
resource governance blocked the agent from continuing effective research even
though the run still had three requested formal screening candidates remaining.
Resource governance should prevent unbounded slot growth, but it should not
turn a recoverable portfolio-saturation state into campaign termination when
the scheduler has structured evidence that clean fork/reclaim is the intended
next action.

Classification:

- Not reasonable as final behavior for an 8R verification gate: it prevented
  completion at 5/8 without a scientific or infrastructure failure.
- Not just configuration: increasing `max_active_branches` would mask the
  immediate failure but leave the reclaim-marker handoff gap.
- Framework defect: scheduler and lifecycle policy disagree on who may mark an
  active no-effect / runtime-pressure branch reclaimable.

## Minimal Design Recommendation

Do not remove the active-slot cap. Fix the handoff.

Recommended minimum design:

1. Add a structured scheduler-lifecycle reclaim marker, separate from
   promotion/abandon decisions, for branches that meet deterministic reclaim
   criteria.
   - Inputs must be structured fields only: branch state, screening tier,
     reason codes, runtime evidence policy status, active-slot status,
     checkpoint status, pending retry/repair flags, and lifecycle counters.
   - No LLM free text and no raw per-case metrics should drive the marker.

2. Let `reclaim_active_slot_for_new_branch` park exactly one eligible low-value
   or clean-fork-required branch when:
   - scheduler selected `explore_new` or `at_capacity` for clean-fork pressure;
   - active slots are full;
   - the branch is already in `eligible_new_branch_slot_reclaim`;
   - the branch has no pending retry, repair focus, or validation/frozen work;
   - the branch is no-effect / repeated low-value / runtime-pressure-only, or
     explicitly same-mechanism-ineligible.

3. Preserve a stricter rule for weak-positive branches:
   - weak-positive branches should not be reclaimed solely because a slot is
     full;
   - they may be reclaimed only when structured runtime-evidence pressure or
     plateau/reroute policy already says clean fork is preferred, and the audit
     explains why same-branch refinement is not selected.

4. Keep scheduler-active-slot blocks as non-counted, but change the terminal
   behavior:
   - first blocked event: persist detailed reclaim diagnostics;
   - if eligible reclaim candidates exist but marker is missing: emit
     `scheduler_lifecycle_handoff_blocked`, not generic
     `scheduler_active_slot_blocked`;
   - do not burn three identical loop iterations when no state changes;
   - surface the exact branch IDs and missing marker reason in
     `status.json` top-level counters/status.

5. Consider a separate resumable budget for active-slot pressure:
   - active-slot blocked should pause/resume or request lifecycle reconciliation
     rather than terminate the requested 8R budget;
   - if no eligible reclaim candidate exists, then terminating as capacity
     blocked is reasonable.

6. Keep `max_active_branches=3` as a useful stress setting after the fix.
   Raising it to 4 is acceptable only as a temporary experiment workaround.

## Status/Observability Recommendation

The final status is directionally correct but not sufficiently diagnostic for a
post-run reader. Add a top-level summary like:

- `active_slot_blocked_context.used/max`
- `active_slot_blocked_context.active_branch_ids`
- `active_slot_blocked_context.reclaim_candidate_branch_ids`
- `active_slot_blocked_context.marker_missing_branch_ids`
- `active_slot_blocked_context.clean_fork_pressure_reason`
- `active_slot_blocked_context.recommended_operator_action`

The current details are present in `last_result.scheduler_audit_metadata` and DB
audit payloads, but they are too buried for run triage.

## Next Step Recommendation

Do not treat this 8R as complete. Accept the 5 formal screened candidates as
valid partial evidence, but do not advance the v0.4 gate from this run alone.

Recommended next step: fix the scheduler/lifecycle reclaim handoff first, then
rerun 8R under the same `max_active_branches=3` stress condition. If a quick
continuity check is needed before fixing, rerun with `max_active_branches=4` as
a temporary workaround, but label that run as a capacity workaround rather than
proof that scheduler governance is correct.
