# v0.4 CVRP Target-Intent Authority Validation

Date: 2026-06-23

## Purpose

Validate Design G from `scion/design/v0.4-effective-research-repair-design.md`:
branch-local protected/allowed mechanism authority must outrank a disjoint
prepared required mechanism when the scheduler selects an existing branch for
same-mechanism follow-up. This is a generic proposal-control repair, not a
CVRP-specific solver change.

## Run

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-authority-542d1f99-postweakpressure-4r-gpt55-20260623T055230Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-authority-542d1f99-postweakpressure-4r-gpt55-20260623T055230Z-claw`
- Launch commit: WSL `542d1f99`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-schedstatus-d0dded44-clean-missingprimary-4r-gpt55-20260623T025241Z-claw/campaign`
- Command:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 4 \
  --label v04-cvrp-authority-542d1f99-postweakpressure \
  --completion-preflight \
  --resume-from-campaign /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-schedstatus-d0dded44-clean-missingprimary-4r-gpt55-20260623T025241Z-claw/campaign
```

## Acceptance

Accepted as framework validation:

- `wrapper_exit_status=0`
- `campaign_wrapper_exit_status=0`
- `postrun_acceptance_status=ready`
- `postrun_readiness_exit_status=0`
- `run_validity_status=valid`
- `run_completeness_status=complete`
- `last_stop_reason=max_rounds_exhausted`
- `effective_rounds_completed=4`
- `protocol_evaluated_candidates=4`
- `formal_screened_candidates=4`
- `proposal_attempts_total=4`
- `proposal_quality_blocks=0`
- `quality_blocks=0`
- `scheduler_active_slot_blocked_attempts=0`
- postrun acceptance failed required checks: `[]`
- postrun acceptance failed optional checks: `[]`

Focused tests also passed after the stricter local/WSL semantic tightening:
`121 passed` for the target-intent/proposal suite. The validation root itself
was launched from the pre-tightening WSL commit, so the root accepts the live
Design G behavior and the later focused tests accept the tighter authority
semantics.

## Current Campaign Rows

The resumed database contains older rows. Current-run evidence is scoped to
campaign id `4339ead0-23e8-42da-9a77-2d3f0efec1fa`.

| row | branch | cases | case W/L/T | pair W/L/T | median | CI | decision |
| --- | --- | ---: | --- | --- | ---: | --- | --- |
| 117 | `bba3d45f` | 8 | 1/4/3 | 9/15/8 | -0.75 | [-6.0, 1.0] | `abandon` |
| 122 | `ec052599` | 8 | 0/0/8 | 1/1/30 | 0.0 | [0.0, 0.0] | `expand_screening` |
| 127 | `e1f1b233` | 8 | 0/0/8 | 1/1/30 | 0.0 | [0.0, 0.0] | `expand_screening` |
| 130 | `e1f1b233` | 12 | 0/0/12 | 0/0/48 | 0.0 | [0.0, 0.0] | `continue_explore` |

Scheduler behavior in those rows:

- row 119: `exploit_weak_positive` / `weak_positive_signal_followup` on
  `bba3d45f`, followed by evidence-backed `soft_abandon`.
- row 124: `exploit_weak_positive` / `weak_positive_signal_followup` on
  `ec052599`, followed by inactive current-evidence slot release after
  expanded screening.
- row 129: `explore_new` / `new_exploration_slot_available` created
  `e1f1b233`.
- row 132: `exploit_weak_positive` / `weak_positive_signal_followup` continued
  `e1f1b233` on the same branch.

## Interpretation

This accepts Design G as a generic framework repair. The previous failure mode
was a loop between prepared target-intent binding and same-mechanism guards.
This run crosses the full live path instead: weak-positive branch selection,
branch-local target intent, formal hypothesis/code generation, canary/formal
evaluation, Protocol screening, screening expansion, and same-branch
continuation.

Independent read-only audit of the run artifacts found the expected authority
diagnostic shape: the root contains successful target-intent/binding artifacts,
`prepared_focus_deferred_for_branch_followup=1`, and
`decision_features_excluded=true`. That is the intended v3 boundary: the
resolver is proposal-control material and does not become Decision input.

This is not a solver improvement. Champion remained `v1`, there were 0
promotions, `protocol_effects_vs_mde.interpretation` was
`all_available_ci_high_below_mde`, and all 4 current rows had median effect at
or below 0 against CVRP `mde_at_power_80=9.9`.

The run nevertheless provides useful effective-research evidence: Scion can now
produce evidence-backed rejection (`abandon`), low-SNR expansion
(`expand_screening`), and continued same-branch investigation
(`continue_explore`) after a branch-local follow-up selection.

## Remaining Risks

- Research context still has actionability gaps: postrun research efficiency
  reports `same_mechanism_followup.selection_rate=0.75` and one same-mechanism
  opportunity not selected.
- Branch lesson usage is present but imperfect:
  `branch_lesson_usage.semantic_gap_count=1`.
- Evidence stops at screening. There are no validation or frozen rows in this
  root, so it should not be promoted into a solver-quality gate.
- Measurement readiness is sufficient for the current acceptance purpose, but
  still `summary_only` calibration / `low_power`; use the MDE conclusion to say
  no positive-at-MDE effect was observed, not to make a strong universal claim
  that the mechanism family is exhausted.
- Solver direction quality remains weak. This run explored
  `route_pressure_acceptance` and `large_instance_intra_route_two_opt_seed`,
  but all current effects were below MDE.
- The local/WSL tightened target-intent semantics were accepted by focused
  tests after launch; future launches should start from the synchronized
  tightened head.

## Next Actions

1. Treat scheduler-status and target-intent authority as accepted framework
   repairs unless a new run regresses these generic behaviors.
2. Audit research-context actionability around the one missed same-mechanism
   opportunity and the branch-lesson semantic gap before adding more core code.
3. Continue CVRP as a problem-owned solver-research run, interpreting effects
   against MDE and avoiding VRP-specific exceptions in scheduler, proposal
   authority, or projection code.
4. Keep warehouse as the simpler positive-control path and use it to verify
   that continuous-improvement behavior still recovers after the framework
   repairs.
