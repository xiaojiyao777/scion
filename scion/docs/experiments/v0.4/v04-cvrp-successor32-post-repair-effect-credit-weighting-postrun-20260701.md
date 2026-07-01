# CVRP successor32 post-repair effect credit weighting postrun

Date: 2026-07-01

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-target-bound-2r-gpt55-20260701T142821Z-claw`

Runner: server-local `claw`

Model: local `gpt-5.5`

Runner commit: `76952d20`

## Question

Can `post_repair_effect_credit_weighting` improve CVRP `total_distance` by
crediting ALNS destroy/repair adaptive weights from post-repair pre-polish
objective effect, while keeping the operator set, acceptance behavior,
construction seeds, local-search moves, embedded-VNS allocation, and generic
core unchanged?

## Validity

- Root `run_status.json`: `status=finished`, `run_validity_status=valid`,
  `run_completeness_status=complete`, `completed_requested_rounds=true`,
  `last_stop_reason=max_rounds_exhausted`, `campaign_exit_status=complete`,
  `postrun_acceptance_status=ready`.
- Campaign status: `effective_rounds_completed=2`,
  `formal_screened_candidates=2`, `protocol_evaluated_candidates=2`,
  `protocol_metric_results=2`, `proposal_attempts_total=2`,
  `proposal_quality_blocks=0`, no failure categories, no in-flight protocol.
- Completion preflight was healthy; postrun readiness passed.
- LLM accounting: `gpt-5.5` for 8 traced requests: 2 target-intent, 2
  hypothesis, 2 code, and 2 tool-selection calls.

## Mechanism binding

The new proposal-only `target_intent_required_mechanism_ids` binding worked.
Both target-intent calls selected:

- `mechanism_id=post_repair_effect_credit_weighting`
- `mechanism_family=acceptance_or_adaptive_weighting`
- `target_file=policies/baseline_modules/scheduler.py`

Both formal hypothesis bindings were `bound` and carried
`post_repair_effect_credit_weighting` into the formal mechanism ids.
The prepared manifest kept hard `required_mechanism_ids=[]`, preserving
prepared-successor arbitration while pinning only target intent.

## Objective results

| Round | Branch | Code status | Gate | Pair result | Case result | Median delta | CI | Notable nonzero pair |
|---|---|---|---|---|---|---:|---|---|
| 1 | `94224fba` | `active_quality_regression` | fail | 0 wins / 1 loss / 31 ties | 0 wins / 0 losses / 8 ties | `0.0` | `[0.0, 0.0]` | `E-n101-k14`, seed 11, `-6.0` |
| 2 | `32716e6f` | `clean` | expand | 1 win / 0 losses / 31 ties | 0 wins / 0 losses / 8 ties | `0.0` | `[0.0, 0.0]` | `X-n110-k13`, seed 43, `+70.0` |

Postrun research-efficiency summary:

- `mde_at_power_80=9.9`
- `rows_at_or_above_mde=0`
- `rows_below_mde=2`
- `rows_with_ci_high_below_mde=2`
- `max_median_delta=0.0`
- `max_effect_to_mde_ratio=0.0`
- interpretation: `all_available_ci_high_below_mde`
- champion progress: `no_promotion_signal_observed`

## Mechanism telemetry

The mechanism was not missing or inactive. It activated and recorded direct
phase/effect telemetry in both rows:

- Round 1: iterations present/positive `32/32`; phase runtime positive `8/32`
  with `14 ms` weighted total; improvement-count positive `18/32`; best-delta
  positive `18/32`.
- Round 2: iterations present/positive `32/32`; phase runtime positive `32/32`
  with `1810 ms` weighted total; improvement-count positive `17/32`;
  best-delta positive `17/32`.
- Mechanism evidence: `primary_activation_status=observed`,
  `primary_effect_status=positive`, `objective_effect_status=zero_objective_effect`.
- CMT2/CMT4 protected cases were covered in both rows.

Runtime-budget diagnostics reported `SCREENING_RUNTIME_BUDGET_SATURATION` as
`info`. The generated guidance says to keep this for interpretation, not to
repair the candidate from budget saturation alone.

## Interpretation

This run resolves the control-plane blocker from the two earlier successor32
roots. Target intent and formal hypotheses stayed bound to the intended
mechanism, and both candidates reached formal screening without model,
proposal-quality, telemetry, or postrun failures.

The solver result is evidence-complete but not promotion-grade. The mechanism
can produce local post-repair credit/effect telemetry, but the effect does not
survive to case-level objective improvement after downstream search. The one
clean-row win on `X-n110-k13` is a single seed-level event, not a case-gate or
MDE-level signal, and the paired quality-regression row contains one small loss.

Do not expand unchanged `post_repair_effect_credit_weighting` for v0.4. Treat
it as reviewed/default-avoid unless a future proposal names a materially
different causal path that can connect operator credit to final objective
effect, not just internal scoring telemetry.

## Next design boundary

The next CVRP solver attempt should be a new design review, not an automatic
same-mechanism relaunch. It should avoid unchanged:

- route-pair-overlap removal/protected follow-up;
- bounded cross-route double-bridge polish;
- adaptive embedded-VNS runtime allocation;
- post-repair effect credit weighting;
- construction seed and short-horizon seed trajectory selectors;
- scheduler q/destroy-size and insertion-cost repair variants already reviewed.

The successor33 design should start from a materially different CVRP-owned
causal path with direct objective-effect telemetry and CMT2/CMT4/P-family
case protection.
