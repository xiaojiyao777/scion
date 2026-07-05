# CVRP successor36b seed-post selector static-smoke repair postrun

Date: 2026-07-05

## Run

Root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor36b-seed-post-selector-static-smoke-repair-server-2r-gpt55-20260705T104029Z-claw`

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
blocks, no verification failures, no model/tool failure, and postrun readiness
ready. It is valid solver evidence.

## Evidence Summary

The successor36 static-smoke recognizer gap was repaired: both attempts reached
formal screening, and the previous
`cvrp_construction_seed_direct_effect_missing` quality block did not recur.

| Row | Branch | Mechanism | Decision | Median delta | CI | Win rate |
|---|---|---|---|---:|---|---:|
| 1 | `641490e8-92ca-4abe-a7a4-59fe92e3bf0e` | `seed_post_optimization_selector` | expand_screening | `0.0` | `[0.0, 0.0]` | `0.0` |
| 2 | `641490e8-92ca-4abe-a7a4-59fe92e3bf0e` | `seed_post_optimization_selector` | abandon | `0.0` | `[0.0, 0.0]` | `0.0` |

MDE interpretation:

- `mde_at_power_80=9.9`
- `positive_rows=0`
- `rows_at_or_above_mde=0`
- `rows_with_ci_high_below_mde=2`
- `max_median_delta=0.0`
- `max_effect_to_mde_ratio=0.0`
- `interpretation=all_available_ci_high_below_mde`

Overall screening summary:

- `total_experiments=2`
- `screening_pass_rate=0.0`
- `screening_case_wins=0`
- `screening_case_losses=1`
- `screening_case_ties=27`
- `screening_pair_wins=7`
- `screening_pair_losses=7`
- `screening_pair_ties=98`
- `champion_promotions=0`

## Mechanism and Telemetry

The generated candidate created
`policies/baseline_modules/seed_selector.py` and wired it into
`policies/baseline_modules/scheduler.py` immediately after construction and
before initial VNS/ALNS. Scheduler edits were construction-boundary wiring, not
a broader scheduler-policy change.

The mechanism activated and emitted runtime telemetry:

- row 1: `seed_post_optimization_selector` max runtime `296ms`, weighted sum
  `7032ms` over `48` candidate pairs;
- row 2: max runtime `538ms`, weighted sum `9544ms` over `64` candidate pairs.

Mechanism evidence was active:

- row 1: primary activation observed; primary effect positive, but aggregate
  objective effect status was `zero_objective_effect`;
- row 2: primary activation observed; primary effect positive; aggregate
  objective effect status was `positive`.

Despite that direct mechanism activity, the case-gate effect did not survive
as promotion-grade solver improvement. Most case medians were exact ties, and
the final branch was abandoned.

## Case Pattern

Row 1 had a small mixed B/X pattern but zero aggregate effect:

- `B-n67-k10`: median `-0.5`, with two losses and two wins;
- `X-n110-k13`: median `0.0`, with one win and three ties;
- all other reported case medians were `0.0`.

Row 2 added protected-case evidence and remained nonpositive:

- `CMT2`: median `-4.5`, with deltas `-29.0`, `0.0`, `+10.0`, `-9.0`;
- `CMT4`: median `0.0`, all ties;
- `B-n67-k10`: median `-0.5`, with two losses and two wins;
- `P-n101-k4`: median `0.0`, with one win and three ties;
- all remaining reported case medians were `0.0`.

The CMT2 loss means this line is not a protected-case-safe follow-up.

## Decision

Classify `seed_post_optimization_selector` activation repair as reviewed for
v0.4:

- the static recognizer repair worked;
- the mechanism activated and direct telemetry was visible;
- the run was valid, complete, and postrun-ready;
- there were no quality/model/telemetry/postrun failures;
- no row was positive at or above MDE;
- both aggregate medians were `0.0`;
- row 2 regressed CMT2.

Do not expand unchanged `seed_post_optimization_selector` in the next CVRP
slot. A future construction-seed revisit must name a materially different
causal path from raw seed-baseline selection, short-horizon trajectory
selection, and this post-construction seed micro-polish selector, and must
include CMT2/CMT4 protection evidence.

## Next Direction

Continue v0.4 with a clean fork to a different CVRP-owned causal path. The
reviewed/default-avoid set now includes unchanged seed-post optimization,
capacity-tight removal, frozen-safe neighbor-list filtering, post-repair effect
credit weighting, adaptive embedded-VNS runtime allocation, double-bridge
polish, route-pair-overlap follow-ups, insertion-cost lookahead, short-horizon
seed trajectory selectors, and raw construction seed-baseline selection.

The next successor should not be another unchanged construction seed selector.
