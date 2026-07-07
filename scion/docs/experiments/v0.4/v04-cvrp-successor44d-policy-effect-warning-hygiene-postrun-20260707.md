# CVRP Successor44d Policy Effect Warning Hygiene Postrun

Date: 2026-07-07

## Status

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor44d-policy-effect-warning-hygiene-server-claw-2r-gpt55-20260707T070106Z-claw`
- Launcher commit: `150ab7de`
- Runner: server-local `claw`, local `gpt-5.5`
- Completion preflight: passed.
- Outcome: valid and complete.
- Stop reason: `max_rounds_exhausted`.
- Effective protocol rows: 2 screening rows, 0 validation, 0 frozen.
- Formal candidate artifacts: 1. The two screening rows are the original
  screen and expanded screen for the same candidate, not two independent code
  hypotheses.
- LLM calls: 7 total: target-intent 1, hypothesis 1, tool-selection 4, code 1.
- Quality/model/telemetry/verification failures: 0.

## Hygiene Repair Verification

The CVRP-owned policy-evidence interpretation repair worked. The
`post_vns_best_anchor_acceptance_guard` mechanism now reaches
`policy_outcome_observed` when activation/runtime are observed,
`effect_observation_required=false`, and the direct mechanism effect fields are
intentionally absent.

The telemetry guard passed in both screening rows with no warnings or
failures. The mechanism diagnostic was:

- `diagnostic_type=policy_outcome_observed`
- `telemetry_outcome=policy_outcome_observed`
- `repairable=false`
- repair guidance: do not add direct effect telemetry for this policy mechanism.

The final branch card preserved that interpretation:

- `mechanism_contract_status=policy_outcome_observed`
- `mechanism_followup_required=false`
- `repair_mechanism_ids=[]`
- reason codes:
  `MECHANISM_CONTRACT_POLICY_OUTCOME_OBSERVED`,
  `MECHANISM_CONTRACT_NO_REPAIR_FOLLOWUP`

This fixes the successor44c guidance failure: the branch card no longer turns
no-direct-effect policy evidence into generic
`context.record_move(delta=...)` repair advice.

## Trace And Code Quality

The trace audit found no harmful context truncation. The only truncated item was
a hypothesis preflight section; the formal target binding and target source
were still visible. The seven LLM calls stayed bound to
`post_vns_best_anchor_acceptance_guard` and
`policies/baseline_modules/acceptance.py`.

The generated patch was a narrow successor44 follow-up:

- added `_post_vns_best_anchor_acceptance_guard` in `acceptance.py`;
- imported and called it from the simulated-annealing worse-candidate branch in
  `scheduler.py`;
- preserved new-best and current-improving paths;
- added only `record_iteration` and `record_phase` for the guard;
- did not add successor44 `context.record_move(..., delta=...)` direct-effect
  telemetry.

The main telemetry caveat is semantic, not a blocker: the helper records
`record_iteration` before checking `sa_accepted`, so that field means the guard
evaluation path ran, not that an SA-accepted worse candidate was actually
blocked. Explicit allow/reject counters would make a future same-line design
clearer.

## Screening Evidence

| row | pairs | runtime confidence | pair W/L/T | raw pair median | raw pair mean | branch summary | decision |
|---|---:|---|---:|---:|---:|---|---|
| original screen | 32/32 | high | 14/7/11 | 0.0 | 8.0 | weak positive / expanded | expand screening |
| expanded screen | 48/48 | low cached champion | 27/14/7 | 3.0 | 4.770833 | weak positive, CI [0.0, 7.25] | continue explore |

The run did not promote. The branch-card reason codes were
`SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE` and
`SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`.

The expanded row had mixed case-level evidence:

- Positive cases: A-n64 `4/0/0`, median `+19.5`; A-n80 `3/0/1`, median
  `+16.5`; E-n101-k14 `3/1/0`, median `+10.0`; P-n65 `4/0/0`, median `+3.5`;
  P-n76 `3/1/0`, median `+4.5`.
- Negative cases: B-n63 `1/3/0`, median `-3.0`; B-n67 `1/3/0`, median
  `-16.5`.
- Protected CMT cases: CMT2 `2/1/1`, median `+4.5`; CMT3 `2/2/0`, median
  `+2.5`; CMT4 `1/0/3`, median `0.0`.

This is real weak-positive screening evidence, but not a long-run or
promotion-grade result. The B-family losses and low cached champion runtime
confidence keep the signal noisy.

## Telemetry

Mechanism activation was observed in every candidate run:

- original screen: context-record iterations positive `32/32`, phase runtime
  nonzero `8/32`;
- expanded screen: context-record iterations positive `48/48`, phase runtime
  nonzero `11/48`.

Direct successor44 effect fields remained absent by design:
`solver_algorithm_phase_improvement_counts.post_vns_best_anchor_acceptance_guard`
and
`solver_algorithm_phase_best_delta.post_vns_best_anchor_acceptance_guard`
were missing, and this no longer created a repair obligation.

## Decision

Successor44d is accepted as a framework/context hygiene repair and as
weak-positive screening evidence for the acceptance-policy line. It is not a
promotion candidate.

Do not long-run unchanged successor44d. Do not add direct-effect
`record_move(delta=...)` telemetry to this policy mechanism.

The next CVRP step should be design-first. Either:

- design one explicit successor44 follow-up with guard allow/reject trajectory
  telemetry and a narrower causal claim, then run a short screen; or
- clean-fork to a materially different CVRP-owned causal path.

In both cases, keep CVRP semantics in problem-owned modules and preserve the v3
generic-core boundary.
