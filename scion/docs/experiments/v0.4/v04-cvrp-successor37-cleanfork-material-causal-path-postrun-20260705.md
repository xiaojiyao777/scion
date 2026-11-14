# CVRP successor37 clean-fork material causal path postrun

Date: 2026-07-05

## Run

Root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor37-cleanfork-material-causal-path-server-2r-gpt55-20260705T133809Z-claw`

Status:

- `status=finished`
- `run_validity_status=valid`
- `run_completeness_status=complete`
- `completed_requested_rounds=true`
- `campaign_exit_status=complete`
- `last_stop_reason=max_rounds_exhausted`
- `postrun_acceptance_status=ready`
- `wrapper_exit_status=0`

The run completed with two effective screening rows, no proposal-quality
blocks, no verification failures, no model/tool failures, and postrun
readiness ready. It is valid solver evidence.

## Evidence Summary

Successor37 was the first no-force clean fork after successor36b closed the
temporary seed-post target-intent binding.

| Row | Branch | Mechanism family | Decision | Median delta | CI | Effect/MDE |
|---|---|---|---|---:|---|---:|
| 1 | `19b6473b-50c2-4a2c-aa2b-b68d93f8af1e` | `edge_frequency_penalty_repair` | expand_screening | `2.5` | `[-7.5, 19.5]` | `0.252525` |
| 2 | `76221086-08bd-409f-ad2d-8dba23475033` | `route_angle_aware_2opt_star` | abandon | `-4.25` | `[-8.0, 0.0]` | `-0.429293` |

MDE interpretation:

- `mde_at_power_80=9.9`
- `positive_rows=1`
- `rows_at_or_above_mde=0`
- `max_median_delta=2.5`
- `max_effect_to_mde_ratio=0.252525`
- `interpretation=protocol_effects_below_mde_or_inconclusive`

Overall screening summary:

- `total_experiments=2`
- `screening_pass_rate=0.0`
- `screening_case_wins=5`
- `screening_case_losses=5`
- `screening_case_ties=6`
- `screening_pair_wins=21`
- `screening_pair_losses=29`
- `screening_pair_ties=14`
- `champion_promotions=0`

## Mechanism Pattern

`route_angle_aware_2opt_star` should be treated as reviewed/default-avoid for
unchanged repetition. It activated and recorded direct objective movement, but
the aggregate row was negative and most non-A cases were negative or tied.

`edge_frequency_penalty_repair` is weak-positive below MDE, not promotion
evidence. It added an edge-frequency penalty repair operator in
`policies/baseline_modules/destroy_repair.py`, wired it from
`policies/baseline_modules/scheduler.py`, and produced row-level median
`2.5`. The signal is case-selective:

- A-n64-k9: median `3.0`
- B-n63-k10: median `19.5`
- E-n101-k14: median `3.0`
- M-n200-k17: median `0.0`
- P-n65-k10: median `2.0`
- X-n110-k13: median `24.0`
- CMT2: median `-7.5`, all four seeds lost
- CMT4: median `-15.0`, all four seeds lost

The protected-case losses make unchanged expansion unsafe despite the weak
positive aggregate row.

## LLM and Candidate-Quality Audit

Detailed trace audit:
`scion/docs/experiments/v0.4/v04-cvrp-successor37-llm-mechanism-quality-root-cause-audit-20260705.md`

Successor37 used `gpt-5.5` successfully for all 11 LLM calls:

- 2 `hypothesis_target_intent`
- 2 `hypothesis`
- 5 `tool_selection`
- 2 `code`

The model calls were normal, and the run had no proposal-quality, verification,
model, tool, or postrun failure. The quality failure was in the proposal chain:
material-difference and protected-case requirements were available as narrative
guidance but were not hard proposal contracts at target-intent/hypothesis time.
`route_angle_aware_2opt_star` self-certified novelty while remaining close to
the existing `_two_opt_star` search basin, and `edge_frequency_penalty_repair`
claimed trajectory edge memory but implemented current partial-solution edge
counts with zero direct mechanism effect.

## Decision

Do not launch a long-round experiment yet. Successor37 is valid solver
evidence, but it is not promotion-grade and it is not a protected follow-up
signal.

Do not repeat unchanged `route_angle_aware_2opt_star`; it is negative
bounded-local-search evidence.

Do not repeat unchanged `edge_frequency_penalty_repair`; it is weak-positive
below MDE, direct-effect-zero, and CMT2/CMT4 unsafe. A same-mechanism protected
follow-up should not be the next default action unless a future proposal first
repairs proposal control and proves a materially different direct-effect
contract rather than merely tuning the edge-frequency penalty.

The next CVRP action is proposal-control/candidate-quality repair followed by a
new 2-round server-local clean fork only if target-intent and hypothesis name a
materially different CVRP-owned causal path, a direct mechanism-effect evidence
plan, and a CMT2/CMT4 protection plan before code generation.
