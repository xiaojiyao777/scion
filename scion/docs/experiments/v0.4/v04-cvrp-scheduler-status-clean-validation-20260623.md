# CVRP Scheduler-Status Clean Validation

Date: 2026-06-23

## Run

- Root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-schedstatus-d0dded44-clean-missingprimary-4r-gpt55-20260623T025241Z-claw`
- Launch commit: WSL `d0dded44`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-missingprimary-8d28bc30-narrowavoid-4r-gpt55-20260622T171659Z-claw/campaign`
- Model: `gpt-5.5`
- Purpose: validate the generic scheduling-status repair against the prior
  missing-primary active-slot failure shape. This was not a new CVRP heuristic
  experiment.

## Acceptance

Postrun acceptance command:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/check_postrun_acceptance.py \
  /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-schedstatus-d0dded44-clean-missingprimary-4r-gpt55-20260623T025241Z-claw \
  --require-current-run-ready --format json
```

Result: exit `0`, `current_run_analysis_ready=true`,
`delegation_ready=true`, and no required or optional postrun acceptance
failures.

Campaign counters:

- `effective_rounds_completed=4`
- `effective_protocol_rounds=4`
- `requested_rounds=4`
- `proposal_attempts_total=4`
- `proposal_attempts_consumed=4`
- `scheduler_active_slot_blocked_attempts=0`
- `active_slot_blocked_attempts=0`
- `protocol_evaluated_candidates=4`
- `formal_screened_candidates=4`
- `quality_blocks=0`
- `proposal_quality_blocks=0`
- `last_stop_reason=max_rounds_exhausted`
- `champion_version=1`

## Interpretation

The Design A scheduling-status repair is accepted for the prior active-slot
blocker: the clean run reached the requested four effective rounds and stopped
by `max_rounds_exhausted`, not `scheduler_active_slot_blocked`.

This is framework validation, not solver progress. Postrun research-efficiency
reported `protocol_effects_vs_mde.interpretation=all_available_ci_high_below_mde`;
all four screening rows were below MDE with non-positive median deltas, and
there were no promotions. Research continuity still needs follow-up:
`same_mechanism_followup.selection_rate=0.25` with three observed same-mechanism
opportunities not selected.

After the run completed, the latest local repair commits were applied to WSL
with `git am`; WSL head became `84799ba6`. WSL conda validation passed:

- `38 passed` for focused campaign/lifecycle/proposal tests.
- `115 passed` for `scion/scion/tests/test_launch_readiness.py`.

## Boundary

The accepted repair remains generic Scion framework behavior:

- scheduler status and active-slot accounting are problem-neutral;
- CVRP mechanism ids, CMT case details, BKS/gap facts, and MDE diagnostics
  remain problem-owned or report-only;
- no new solver-specific scheduler exception was introduced.
