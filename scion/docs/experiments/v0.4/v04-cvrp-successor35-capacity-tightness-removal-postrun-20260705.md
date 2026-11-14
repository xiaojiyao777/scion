# CVRP successor35 capacity-tightness removal postrun

Date: 2026-07-05

## Run

Root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor35-capacity-tightness-removal-server-2r-gpt55-20260702T004158Z-claw`

Status:

- `status=finished`
- `run_validity_status=valid`
- `run_completeness_status=complete`
- `completed_requested_rounds=true`
- `campaign_exit_status=complete`
- `last_stop_reason=max_rounds_exhausted`
- `postrun_acceptance_status=ready`
- `wrapper_exit_status=0`

Postrun readiness reported no required or optional failures, and
`current_run_analysis_ready=true`.

## Evidence Summary

The run produced two effective formal screening rows. There were no proposal
quality blocks, no code-generation failures, no stale-source failures, no
verification-heavy failures, and no model/tool failure taxonomy entries.

| Row | Branch | Mechanism | Decision | Median delta | CI | Win rate |
|---|---|---|---|---:|---|---:|
| 1 | `7033beb6-c98c-41dc-a2aa-baf16a9e02a6` | `capacity_tightness_removal` | abandon | `-6.0` | `[-8.25, 0.0]` | `0.125` |
| 2 | `4cfcec6c-9c5a-40c0-b376-a4131d18a959` | `capacity_tightness_removal` | abandon | `-3.5` | `[-6.0, 0.5]` | `0.125` |

MDE interpretation:

- `mde_at_power_80=9.9`
- `positive_rows=0`
- `rows_at_or_above_mde=0`
- `rows_with_ci_high_below_mde=2`
- `max_median_delta=-3.5`
- `max_effect_to_mde_ratio=-0.353535`
- `interpretation=all_available_ci_high_below_mde`

Both candidates activated the required mechanism and recorded phase runtime
under `capacity_tightness_removal`, so the result is solver-negative rather
than inactive.

## Case Pattern

Row 1 improved A-n64 but regressed most of the protected and broad screening
surface:

- A-n64: `+17.0`
- B-n63: `-10.5`
- CMT2: `-6.0`
- CMT4: `-17.0`
- E-n101: `-6.0`
- M-n200: `0.0`
- P-n65: `-6.0`
- X-n110: `0.0`

Row 2 preserved the A-n64 gain and made CMT4 slightly positive, but aggregate
evidence remained loss-heavy:

- A-n64: `+12.5`
- B-n63: `-3.0`
- CMT2: `-5.5`
- CMT4: `+1.0`
- E-n101: `-9.5`
- M-n200: `0.0`
- P-n65: `-4.0`
- X-n110: `-6.0`

## Candidate Reading

Both formal candidates targeted `policies/baseline_modules/destroy_repair.py`
and added or modified a `capacity_tightness_removal` destroy/removal operator.
The only scheduler changes were minimal operator-pool wiring and telemetry
registration for the new operator. There was no intended q-policy,
acceptance-policy, construction-seed, VNS-local-search, or runtime-allocation
change.

Both formal candidate patches were recorded and discarded:

- `49375150d9152f8f`, patch digest
  `7a9ea78f71e5434ebd3156e4b29452832420059e37849f7144e50be0abc532a7`
- `fdf4ba863209e42d`, patch digest
  `0305058d4fe019d40383d23d98c66bba164a5ff7db32f5a49dea60c0f8cc53ba`

## Decision

Classify `capacity_tightness_removal` as reviewed/default-avoid for v0.4:

- mechanism-active;
- direct effect telemetry present;
- no infrastructure or model-call blocker;
- no promotion-grade row;
- loss-heavy aggregate medians;
- CMT2 stayed negative in both rows;
- B/E/P/X losses outweighed the A-n64 gain.

Do not expand the unchanged capacity-tight removal mechanism. A future
destroy/repair revisit must name a materially different causal path and must
not treat this result as a weak-positive same-mechanism base.

## Next Direction

Promote the deferred `seed_post_optimization_selector` activation repair to the
next CVRP slot, now successor36.

Rationale:

- capacity-tight removal is measured negative;
- route-pair-overlap, insertion lookahead, double-bridge, adaptive runtime
  allocation, operator-credit weighting, and frozen-safe neighbor-list filtering
  are all reviewed or parked for v0.4;
- `seed_post_optimization_selector` is suppressed for unchanged repetition but
  not evidence-complete no-positive-at-MDE, because successor16/17 failed by
  missing activation;
- the existing deferred plan has a cleaner module boundary:
  `policies/baseline_modules/seed_selector.py` plus minimal scheduler wiring.
