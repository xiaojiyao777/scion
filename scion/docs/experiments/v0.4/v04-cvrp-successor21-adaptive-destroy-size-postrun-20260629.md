# CVRP Successor21 Adaptive Destroy-Size Postrun - 2026-06-29

## Purpose

Summarize the completed WSL successor21 run and define the next CVRP action.
This report supersedes the successor21 in-flight record for interpretation.

Successor21 was intended to test `stagnation_adaptive_destroy_size_schedule`.
The run is valid and postrun-ready, but the actual generated mechanism was
`operator_pair_destroy_size_bands`, a destroy/repair-pair q-band scheduler.
That mechanism activated, changed q, and produced formal rows, but it did not
produce promotion-grade CVRP solver improvement.

## Run Root

Authoritative WSL run root:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor21-adaptive-destroy-size-2r-gpt55-20260629T172740Z-claw
```

Runner repo:

```text
/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
```

Runner commit used by `run.sh`: `a27fa2ec`.

## Run Status

Root `run_status.json`:

- `status=finished`
- `campaign_exit_status=complete`
- `campaign_wrapper_exit_status=0`
- `wrapper_exit_status=0`
- `run_validity_status=valid`
- `run_completeness_status=complete`
- `run_complete=true`
- `completed_requested_rounds=true`
- `last_stop_reason=max_rounds_exhausted`
- `postrun_acceptance_status=ready`
- `postrun_acceptance_failed=false`
- Started: `2026-06-29T17:28:53Z`
- Ended: `2026-06-29T18:34:53Z`

Postrun readiness:

- `delegation_ready=true`
- `current_run_analysis_ready=true`
- `failed_required_checks=[]`
- `failed_optional_checks=[]`

No proposal or infra failure was recorded:

- `proposal_quality_blocks=0`
- `model_repair_failures=0`
- `telemetry_failed_experiments=0`
- `verification_failure_consumed_candidates=0`
- `failures.total_failures=0`

Model accounting confirms normal local model use:

- provider: `openai_compatible`
- model: `gpt-5.5`
- calls: `4`
- request kinds: `hypothesis_target_intent`, `hypothesis`,
  `tool_selection`, `code`

## Proposal Flow

Run constraints:

- Surface: `solver_design`
- Action: `modify`
- Target file: `policies/baseline_modules/scheduler.py`
- Branch id: `30067252-cf8e-4047-98c4-06e95ce041cf`
- Protocol rows: `2`
- Screening rows: `2`

Formal candidate artifact:

- Candidate id: `0b15627145bf432d`
- Hypothesis id: `79abeb20-1ddb-4148-b953-60508a174d8c`
- Patch digest:
  `cc9c09a8c86df6d1c6844491ae45d952443f8a7d9900f5e828be3a0ecb1760d8`
- Artifact:
  `campaign/artifacts/formal_candidates/30067252/screening-79abeb20-1ddb-4148-b953-60508a174d8c-0b15627145bf432d/candidate.patch.json`

## Actual Mechanism

The generated patch did not implement a stagnation-based schedule. It added
`_operator_pair_destroy_size` to `policies/baseline_modules/scheduler.py` and
clamped q by selected destroy/repair operator pair:

- small bands for pairings such as `route+greedy`, `route+regret2`,
  `worst+greedy`, and `worst+regret2`;
- medium bands for pairings such as `random+greedy`, `random+regret2`,
  `route+regret3`, `worst+regret3`, and `shaw+greedy`;
- large bands for pairings such as `random+regret3`, `shaw+regret2`, and
  `shaw+regret3`.

It recorded candidate-facing telemetry under
`operator_pair_destroy_size_bands`.

This is a valid scheduler destroy-size mechanism, but it is not
`stagnation_adaptive_destroy_size_schedule`: it does not use no-improvement
streak, current-best progress, stagnation bins, or search-progress state.

## Protocol Accounting

From postrun research efficiency:

- Requested/effective rounds: `2 / 2`
- Protocol metric results: `2`
- Screening rows: `2`
- Validation rows: `0`
- Frozen rows: `0`
- Fresh-runtime replay rows: `0`
- Proposal attempts total/consumed: `2 / 2`
- Verification consumed candidates: `2`

Postrun summary:

- Champion promotions: `0`
- Latest champion version: `1`
- Screening case counts: `6 wins / 10 losses / 4 ties`
- Screening pair counts: `32 wins / 41 losses / 7 ties`

## Screening Row 1

Metrics artifact:

```text
campaign/metrics/713d1e3e-e367-4d4b-86c9-543a45feb844.json
```

Summary:

- Pairs: `32 / 32`
- Raw pair counts: `15 wins / 12 losses / 5 ties`
- Raw pair median: `0.0`
- Postrun row median delta: `0.25`
- CI: `[-6.0, 6.5]`
- MDE: `9.9`
- Effect/MDE ratio: `0.025253`
- Decision: `expand_screening`
- Gate outcome: `expand`
- Reason: `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`
- Mechanism activation: `activation_observed`
- Positive effect at or above MDE: `false`

Protected cases:

- `CMT2`: `2 wins / 1 loss / 1 tie`, median delta `6.5`
- `CMT4`: `1 win / 3 losses / 0 ties`, median delta `-1.0`

## Screening Row 2

Metrics artifact:

```text
campaign/metrics/8439080e-5139-4ef7-8fcd-94198b8edb64.json
```

Summary:

- Pairs: `48 / 48`
- Raw pair counts: `17 wins / 29 losses / 2 ties`
- Raw pair median: `-2.0`
- Postrun row median delta: `-5.5`
- CI: `[-8.0, 2.75]`
- MDE: `9.9`
- Effect/MDE ratio: `-0.555556`
- Decision: `continue_explore`
- Gate outcome: `fail`
- Reasons:
  - `SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA`
  - `SCREENING_BORDERLINE_POLICY_FAIL_CLOSED`
  - `BRANCH_LIFECYCLE_PARK_LINEAGE`
  - `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`
  - `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`
- Mechanism activation: `activation_observed`
- Positive effect at or above MDE: `false`

Protected cases:

- `CMT2`: `2 wins / 1 loss / 1 tie`, median delta `6.5`
- `CMT4`: `1 win / 3 losses / 0 ties`, median delta `-2.0`

## q-Trajectory Evidence

The final row's ALNS trace confirms the mechanism changed q relative to the
champion. Examples from median q by operator pair:

| Operator pair | Candidate median q | Champion median q |
|---|---:|---:|
| `random+greedy` | 8 | 21 |
| `route+regret2` | 4 | 19 |
| `shaw+regret3` | 13 | 21 |
| `worst+regret2` | 4 | 21 |

This verifies q was changed. It also explains why the branch should not be
interpreted as a missing-activation failure.

## MDE Interpretation

Measurement readiness:

- `status=ready`
- `reason_code=ok`
- `mde_at_power_80=9.9`
- `n_pairs=96`
- `noise_band_p90_abs=45.5`
- `signal_to_noise_tier=low_power`

Effect-vs-MDE:

- `protocol_row_count=2`
- `positive_rows=1`
- `nonpositive_rows=1`
- `rows_at_or_above_mde=0`
- `rows_below_mde=2`
- `rows_with_ci_high_below_mde=2`
- `max_median_delta=0.25`
- `max_effect_to_mde_ratio=0.025253`
- `interpretation=all_available_ci_high_below_mde`

Both rows have CI high below the 9.9 MDE. The first row was only a low-SNR
expand signal; the follow-up row was loss-heavy and failed closed.

## Interpretation

Outcome classification:

```text
quality-regression / evidence-complete below-MDE for operator_pair_destroy_size_bands
```

Do not count this as positive evidence for
`stagnation_adaptive_destroy_size_schedule`. The run proves that the repaired
framework can produce, evaluate, expand, and park a scheduler destroy-size
branch, but it does not solve the CVRP v0.4 solver-improvement blocker.

Problem-owned guidance should treat `operator_pair_destroy_size_bands` as
reviewed no-positive-at-MDE scheduler destroy-size evidence. It should not
block a materially different stagnation-based q schedule, but unchanged
operator-pair q bands should be default-avoided.

## Next Action

Prepare successor22 as a clean fork with stricter design acceptance:

- mechanism id must be `stagnation_adaptive_destroy_size_schedule`;
- q must depend on stagnation/search-progress state, not just operator pair;
- existing destroy/repair operators, acceptance, weights, and generic core
  remain unchanged;
- telemetry must record activation and q trajectory under the declared
  mechanism id;
- formal screening must include CMT2/CMT4 and report case-level deltas;
- if the next row is below MDE or CMT4 remains stably negative, park the branch
  and move to a different CVRP-owned causal path.
