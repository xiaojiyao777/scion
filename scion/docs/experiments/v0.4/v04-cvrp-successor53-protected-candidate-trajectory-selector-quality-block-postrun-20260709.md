# CVRP successor53 protected candidate trajectory selector quality-block postrun - 2026-07-09

## Scope

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor53-post-successor52-protected-race-or-cleanfork-server-claw-2r-gpt55-20260709T032807Z-claw`

Successor53 was launched from commit `7683d05f` after successor52 guidance was
refreshed to prefer either a protected candidate-trajectory selector repair or
a materially different CVRP-owned clean fork.

## Status

- Wrapper status: finished with exit status `64`.
- Campaign status: incomplete.
- Run validity: `invalid_no_effective_rounds`.
- Completed requested rounds: `false`.
- Last stop reason: `repeated_quality_block_signature`.
- Effective rounds: `0`.
- Formal screened candidates: `0`.
- Protocol evaluated candidates: `0`.
- Model calls: eight successful local `gpt-5.5` calls, four target-intent and
  four hypothesis calls.
- Candidate intent accounting: four `repair_or_infra_candidate` attempts.
- Postrun acceptance: failed because no effective rounds existed.

This is not solver evidence. It is proposal/gate evidence.

## LLM And Gate Audit

All four target-intent calls stayed on the intended line:
`protected_candidate_trajectory_selector` in
`policies/baseline_modules/scheduler.py`, classified as
`destroy_repair_selection`.

The gate blocked all four formal hypotheses before code generation:

1. attempt 1 missed `branch_lesson_usage.clean_fork_diversity_claim` and
   `algorithmic_intervention_sufficiency`;
2. attempts 2-4 included CMT2/CMT4 `branch_lesson_usage` but still missed
   `algorithmic_intervention_sufficiency`;
3. attempts 2-4 repeated the same missing-field signature and stopped the run.

The hypotheses did describe a real algorithmic idea: preserve a canonical
baseline trajectory, use RNG-isolated alternates, select only a feasible
post-downstream winner, and attribute final total-distance effects. The problem
was that the gate looked for exact outcome-observation tokens. The hypotheses
used forms such as `move_attempts`, `accepted_moves`, `reject causes`, and
`budget_exhausted`; the gate recognized `accepted`/`budget` but was too brittle
around attempt/reject variants.

## Decision

Treat successor53 as invalid and not counted toward solver quality.

The successor52 protected repair direction remains plausible because the gate
blocked before code generation. However, relaunch should happen only after the
CVRP-owned hypothesis contract accepts legitimate attempt/accept/reject/budget
word variants and the prompt explicitly asks for an
`algorithmic_intervention` record.

## Fix Requirement

Before relaunch:

- keep the causal-path gate active;
- broaden the CVRP-owned algorithmic-intervention observation check to accept
  attempt/accept/reject/budget word families used by real telemetry names;
- update solver-design guidance to request
  `algorithmic_intervention.solve_trajectory_change`,
  `algorithmic_intervention.candidate_state_generation_or_selection`,
  `algorithmic_intervention.attempted_accepted_rejected_budget_evidence`, and
  `algorithmic_intervention.final_total_distance_attribution`;
- add a regression test based on the successor53 hypothesis shape;
- then relaunch the protected repair as a fresh run.
