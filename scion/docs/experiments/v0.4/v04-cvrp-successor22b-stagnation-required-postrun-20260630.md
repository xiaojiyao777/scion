# CVRP Successor22b Stagnation Required Postrun - 2026-06-30

## Purpose

Summarize the completed WSL successor22b run and define the next CVRP action.
This report supersedes the successor22 in-flight record for interpretation.

Successor22b corrected successor22a's wrong-mechanism drift: the live
hypothesis, candidate patch, protocol rows, and postrun mechanism evidence all
name `stagnation_adaptive_destroy_size_schedule`. The run is valid and
postrun-ready. It is not solver-positive: the candidate produced no case-level
objective improvement and its aligned ALNS q trace was identical to the
champion trace.

## Run Root

Authoritative WSL run root:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor22b-stagnation-required-2r-gpt55-20260629T193044Z-claw
```

Runner repo:

```text
/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
```

Runner commit used by `run.sh`: `14a7f78c`.

## Run Status

Root `run_status.json`:

- `status=finished`
- `campaign_exit_status=complete`
- `wrapper_exit_status=0`
- `run_validity_status=valid`
- `run_completeness_status=complete`
- `run_complete=true`
- `completed_requested_rounds=true`
- `last_stop_reason=max_rounds_exhausted`
- `postrun_acceptance_status=ready`
- `postrun_acceptance_failed=false`
- Started: `2026-06-29T19:31:52Z`
- Ended: `2026-06-29T20:45:55Z`

Postrun readiness:

- `delegation_ready=true`
- `current_run_analysis_ready=true`
- `failed_required_checks=[]`

No proposal, verification, telemetry, or infra failure was recorded:

- `proposal_quality_blocks=0`
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
- Branch id: `d054cdda-f77c-4f63-9bd3-311031650b32`
- Protocol rows: `2`
- Screening rows: `2`
- Champion promotions: `0`
- Latest champion version: `1`

Formal candidate artifact:

- Candidate id: `dcb15f3908755648`
- Hypothesis id: `d2e6344b-af30-4340-9fb6-bfb2880e1059`
- Patch digest:
  `f2557c13ea80e05131cb15360750cd75d0660ec89702de37a1548f94cd11b70d`
- Artifact:
  `campaign/artifacts/formal_candidates/d054cdda/screening-d2e6344b-af30-4340-9fb6-bfb2880e1059-dcb15f3908755648/candidate.patch.json`

## Candidate Patch

The patch stayed narrow and problem-owned:

- only `policies/baseline_modules/scheduler.py` changed;
- no generic Scion core code changed;
- no acceptance, adaptive-weight, destroy/repair, construction, or local-search
  module changed;
- no new helper functions or helper modules were added.

The candidate added two local ALNS-loop state variables,
`stagnation_iterations` and `hard_rejection_pressure`, then multiplied the
baseline random q ratio by a bounded stagnation multiplier after the early
segment. It also recorded mechanism telemetry under
`stagnation_adaptive_destroy_size_schedule`.

## Protocol Accounting

From postrun research efficiency:

- Requested/effective rounds: `2 / 2`
- Protocol row count: `2`
- Screening rows: `2`
- Positive rows: `0`
- Nonpositive rows: `2`
- Rows at or above MDE: `0`
- Rows with CI high below MDE: `2`
- Max median delta: `0.0`
- Max effect/MDE ratio: `0.0`
- Interpretation: `all_available_ci_high_below_mde`

Postrun summary:

- Screening case counts: `0 wins / 0 losses / 20 ties`
- Screening pair counts: `3 wins / 0 losses / 77 ties`
- Screening pair win rate: `0.0375`

## Screening Row 1

Metrics artifact:

```text
campaign/metrics/d74db491-eae5-47c2-b251-ecc4f62a5e5b.json
```

Summary:

- Pairs: `32 / 32`
- Case counts: `0 wins / 0 losses / 8 ties`
- Pair counts: `1 win / 0 losses / 31 ties`
- Median delta: `0.0`
- CI: `[0.0, 0.0]`
- MDE: `9.9`
- Effect/MDE ratio: `0.0`
- Decision: `expand_screening`
- Gate outcome: `expand`
- Reason: `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`
- Mechanism activation: `activation_observed`

The only non-tie pair-level case was `P-n65-k10`; its case median still tied.

## Screening Row 2

Metrics artifact:

```text
campaign/metrics/db8a066f-c5bb-4c5b-9ea8-b3a07fd0e460.json
```

Summary:

- Pairs: `48 / 48`
- Case counts: `0 wins / 0 losses / 12 ties`
- Pair counts: `2 wins / 0 losses / 46 ties`
- Median delta: `0.0`
- CI: `[0.0, 0.0]`
- MDE: `9.9`
- Effect/MDE ratio: `0.0`
- Decision: `continue_explore`
- Gate outcome: `expand`
- Reasons:
  - `SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE`
  - `SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL`
  - `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE`
- Mechanism activation: `activation_observed`

The non-tie pair-level cases were `A-n64-k9` and `P-n65-k10`; both case
medians still tied.

Protected cases:

- `CMT2`: all paired comparisons tied, median delta `0.0`
- `CMT4`: all paired comparisons tied, median delta `0.0`

## q-Trajectory Audit

The mechanism id and telemetry were present, but the aligned ALNS q trajectory
did not differ from the champion:

| Row | Pairs | Aligned ALNS iterations | Pairs with q change | Iterations with q change | Median q delta |
|---|---:|---:|---:|---:|---:|
| 1 | 32 | 505 | 0 | 0 | 0.0 |
| 2 | 48 | 737 | 0 | 0 | 0.0 |

This matters more than the mechanism label. The implementation entered the
right scheduler location and recorded the declared mechanism, but under formal
screening it did not change q relative to champion execution. Treat the run as
an activation/trajectory no-op, not as evidence that a meaningful stagnation q
schedule was tested.

## MDE Interpretation

Measurement readiness:

- `status=ready`
- `reason_code=ok`
- `mde_at_power_80=9.9`
- `n_pairs=96`
- `noise_band_p90_abs=45.5`
- `signal_to_noise_tier=low_power`

Both rows had median delta `0.0` and CI `[0.0, 0.0]`. No row approached the
9.9 MDE, and no case-level win was observed.

## Interpretation

Outcome classification:

```text
inactive-q-trajectory / evidence-complete zero-effect for stagnation_adaptive_destroy_size_schedule
```

Do not treat successor22b as solver-positive. It is framework-positive because
target-intent control, hard required-mechanism guidance, contract,
verification, telemetry readiness, postrun readiness, and WSL execution all
worked. It is solver-negative because the candidate did not create a q
trajectory difference and did not improve case-level objective evidence.

## Next Action

The next CVRP slot should not repeat successor22b unchanged.

Use a design-first successor23 activation repair only if it explicitly fixes
the q-trajectory no-op:

- keep the change problem-owned and local to scheduler behavior;
- record or expose baseline q, adapted q, and q delta in the existing ALNS
  trace path;
- require at least one formal row with nonzero aligned q deltas before
  interpreting objective effect;
- keep acceptance, adaptive weights, destroy/repair operators, construction,
  local search, generic core, protocol, and DecisionFeatures unchanged.

If successor23 cannot make q materially differ under formal screening, park
this scheduler destroy-size branch and clean-fork to a different CVRP-owned
causal path.
