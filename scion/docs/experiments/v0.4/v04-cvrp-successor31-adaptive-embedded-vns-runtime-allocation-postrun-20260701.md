# CVRP Successor31 Adaptive Embedded VNS Runtime Allocation Postrun

Date: 2026-07-01

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-server-2r-gpt55-20260701T111631Z-claw`

Runner: server-local `claw`

Model: local `gpt-5.5`

Runner commit: `9cfee8e3`

## Verdict

Successor31 is valid framework evidence and solver-negative CVRP evidence.
The run completed two requested screening rounds, postrun acceptance is ready,
and the required mechanism reached formal screening with direct phase runtime
telemetry. It did not produce objective improvement.

Treat unchanged `adaptive_embedded_vns_runtime_allocation` as
reviewed/default-avoid for v0.4. Do not continue it on `continue_explore`,
runtime-share
movement, or activation telemetry alone.

## Run Status

- Root wrapper status: `finished`
- Wrapper exit status: `0`
- Campaign exit status: `complete`
- Run validity: `valid`
- Run completeness: `complete`
- Postrun acceptance status: `ready`
- Stop reason: `max_rounds_exhausted`
- Started: `2026-07-01T11:19:38Z`
- Ended: `2026-07-01T12:34:24Z`

Campaign counters:

- `effective_rounds_completed=2`
- `effective_protocol_rounds=2`
- `protocol_metric_results=2`
- `screening_protocol_results=2`
- `proposal_attempts_total=2`
- `proposal_quality_blocks=0`
- `telemetry_failed_experiments=0`
- `verification_consumed_candidates=2`

LLM calls were normal: `gpt-5.5` handled one target-intent, one hypothesis, one
tool-selection, and one code call.

## Mechanism Continuity

The prepared run forced `solver_design` / `modify` /
`policies/baseline_modules/scheduler.py` and required
`adaptive_embedded_vns_runtime_allocation` in both the legacy research focus
and typed guidance contract.

Postrun proposal distributions show both proposal sessions used:

- selected surface: `solver_design`
- action: `modify`
- target file: `policies/baseline_modules/scheduler.py`
- mechanism id: `adaptive_embedded_vns_runtime_allocation`

The mechanism was not a wrong-target or wrong-mechanism run.

## Objective Evidence

Measurement readiness was usable but low-power:

- `measurement_readiness.status=ready`
- `mde_at_power_80=9.9`
- `noise_band_p90_abs=45.5`
- `signal_to_noise_tier=low_power`

Both screening rows stayed at exact zero aggregate effect:

| Row decision | Gate outcome | Median delta | CI high | Effect/MDE | Reason |
|---|---|---:|---:|---:|---|
| `expand_screening` | `expand` | `0.0` | `0.0` | `0.0` | `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT` |
| `continue_explore` | `fail` | `0.0` | `0.0` | `0.0` | `SCREENING_FAIL_WIN_RATE`, `SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL`, `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE` |

Protocol effect-vs-MDE summary:

- `positive_rows=0`
- `nonpositive_rows=2`
- `rows_at_or_above_mde=0`
- `rows_with_ci_high_below_mde=2`
- `max_median_delta=0.0`
- `max_effect_to_mde_ratio=0.0`
- interpretation: `all_available_ci_high_below_mde`

Summary counters also show no case-level screening wins: `0` wins, `0` losses,
and `20` ties at the case-gate level. Pair-level noise was small and mixed:
`4` wins, `5` losses, and `71` ties across `80` pairs.

## Case Notes

The first row covered CMT2 and CMT4 and both had median `0.0`. A-n64 had one
winning seed but median `0.0`; P-n65 had one win and one loss, also median
`0.0`.

The second row expanded coverage but remained flat. CMT4 had median `0.0`;
P-n101-k4 had median `-0.5`; the other observed case medians were `0.0`.

There is no hidden protected-case improvement and no A/B/X-style weak-positive
pattern like successor27. The result is not blocked by the promotion threshold;
the measured aggregate and case medians are effectively zero.

## Telemetry Interpretation

Direct phase telemetry was present:

- Row 1 observed `32 / 32` candidate pairs with runtime fields.
- Row 2 observed `48 / 48` candidate pairs with runtime fields.
- Row 1 recorded `adaptive_embedded_vns_runtime_allocation` weighted runtime
  `773654 ms`, with `vns_embedded` at `773639 ms`.
- Row 2 recorded `adaptive_embedded_vns_runtime_allocation` weighted runtime
  `1178050 ms`, with `vns_embedded` at `1178033 ms`.

Postrun mechanism evidence reports primary activation observed, but the same
rows report `objective_effect_status=zero_objective_effect`. Runtime share,
embedded-VNS time, or lifecycle `continue_explore` should not be read as
solver-positive evidence.

## Framework Reading

This is a clean effective-research attempt:

- launch readiness and local `gpt-5.5` completion preflight were healthy;
- no proposal-quality block occurred;
- no model, telemetry, verification, or postrun acceptance failure occurred;
- postrun readiness is report-only and excluded from DecisionFeatures;
- campaign, scheduler, and promotion state were not mutated by postrun analysis.

The framework did the right thing: it generated and evaluated a materially
different CVRP-owned causal path, surfaced activation/runtime evidence, and
left the result below promotion because the objective signal was zero.

## Next Direction

Do not launch an unchanged successor31 continuation. The next CVRP slot should
start with a successor32 design review and choose a materially different
problem-owned causal path. Another scheduler/runtime-share variant is only
worth spending a branch slot if the design names a new causal mechanism and
commits to direct same-run objective-effect attribution before formal
screening.

Keep the default posture from the v0.4 modularization principle: design the
module/package boundary first, then implement narrowly.
