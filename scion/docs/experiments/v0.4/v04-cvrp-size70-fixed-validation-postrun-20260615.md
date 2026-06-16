# CVRP Size70 Fixed-Candidate Validation Postrun - 2026-06-15

## Boundary

This is a no-LLM, no-APS fixed-candidate replay. It is not a Scion campaign, not
promotion evidence, and not `DecisionFeatures` input. The diagnostics below are
problem-owned postrun evidence used to decide whether the size70 two-opt polish
mechanism may proceed to frozen fixed replay.

The v3 boundary is preserved: raw paired rows, measurement diagnostics,
runtime details, BKS/case behavior, and two-opt activation remain outside
generic Decision input.

## Inputs

- Launch report:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-fixed-validation-launch-20260615.md`
- Validation design:
  `scion/docs/planning/v0.4/v04-cvrp-size70-fixed-candidate-validation-design-20260615.md`
- Tier 1 Large-X postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-tier1-largeX-postrun-20260615.md`
- Full WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-fixed-validation-full-20260615T225148Z`
- Full server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-size70-fixed-validation-full-20260615T225148Z`

The full replay used the experiment-local inputs:

- `inputs/protocol.validation_all12.yaml`
- `inputs/split_manifest.validation_wsl.yaml`
- `inputs/full_validation_input_summary.json`

Input summary:

```json
{
  "expected_pairs_per_arm": 48,
  "validation_case_count": 12,
  "validation_expand_to": 12,
  "validation_n_cases": 12,
  "validation_seed_count": 4,
  "safe_data_roots": [
    "/home/xjy-ubuntu/research/or-autoresearch-agent/vrp"
  ]
}
```

## Completion

The first launch failed before Protocol because the formal split manifest lacked
the WSL data root. The first repaired relaunch was stopped as invalid-spec
shakedown because it used the formal `validation.n_cases=8` and therefore had
only `32` planned pairs per arm. Neither of those runs is accepted as
validation evidence.

Accepted full run:

- wrapper exit: `0`
- `stdout.log`: `error_count=0`, `row_count=2`, `candidate_count=1`
- `stderr.log`: empty
- comparison artifact:
  `fixed_candidate_replay_comparison.v1.json`
- schema: `scion.fixed_candidate_replay_comparison.v1`
- `row_count`: `2`
- replay arms: `on`, `record_only`
- row status: both `completed`
- row errors: none
- campaign, promotion, and scheduler state mutation flags: all `false`
- `decision_features_excluded=true`
- `measurement_diagnostics_excluded=true`
- `raw_paired_rows_excluded=true`

The comparison artifact does not include raw metric paths in
`source_raw_metrics_ref`, so postrun verification used the synced raw metric
files under `metrics/external-size70-twoopt-polish-20260615/validation/`.

## Pair Accounting

Both replay arms completed the full pre-registered validation set:

| Arm | Attempted | Valid | Failed | Planned | W/T/L | Mean delta | Median delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| `on` | 48 | 48 | 0 | 48 | `26/13/9` | `34.4167` | `4.0` |
| `record_only` | 48 | 48 | 0 | 48 | `27/13/8` | `34.5208` | `6.0` |

Deltas in the raw metric use the Protocol comparison convention: positive rows
are candidate wins, negative rows are candidate losses.

The paired outcomes are consistent across arms. `record_only` differs from
`on` by one `B-n66-k9 seed=53` pair: `on` recorded a `-2` loss while
`record_only` recorded a `+2` win. This is small relative to CVRP's known
noise floor and does not change the gate result.

## Gate Outcome

Both raw validation metrics report:

- `runtime_gate_visibility.gate_outcome="fail"`
- `objective_reason_codes=["VALIDATION_FAIL_NO_HIERARCHICAL_GAIN"]`
- `runtime_evidence_status="sufficient"`
- `runtime_confidence="high"`
- `fresh_champion_required=false`
- `formal_rerun_scheduled=false`
- `runtime_signal_role="tie_break_supporting_signal"`

The validation gate therefore fails. The size70 two-opt candidate must not
advance to frozen fixed replay, and it should not seed a short Scion CVRP
campaign as a mechanism-valid candidate.

## Case Behavior

The strongest positive rows are concentrated in `tai75c`, `X-n129-k18`,
`X-n157-k13`, and `X-n190-k8`. The weakest behavior remains unstable on
`tai150a` and mixed on `X-n120-k6`.

`on` per-case summary:

| Case | W/T/L | Median delta | Mean delta |
|---|---:|---:|---:|
| `A-n60-k9` | `0/4/0` | `0.0` | `0.0` |
| `B-n66-k9` | `0/3/1` | `0.0` | `-0.5` |
| `P-n70-k10` | `0/4/0` | `0.0` | `0.0` |
| `tai75c` | `4/0/0` | `15.5` | `14.5` |
| `tai75d` | `3/0/1` | `6.5` | `-3.0` |
| `tai150a` | `2/0/2` | `55.0` | `49.5` |
| `tai150b` | `2/1/1` | `0.5` | `0.75` |
| `F-n72-k4` | `2/1/1` | `7.0` | `7.0` |
| `X-n120-k6` | `2/0/2` | `44.0` | `14.25` |
| `X-n129-k18` | `4/0/0` | `65.0` | `65.0` |
| `X-n157-k13` | `3/0/1` | `104.0` | `121.5` |
| `X-n190-k8` | `4/0/0` | `144.0` | `144.0` |

The `record_only` per-case pattern is essentially the same; its aggregate is
`27/13/8` with median delta `6.0`.

## Feasibility, Routes, And Runtime

For both arms:

- candidate metric rows: `48/48`
- champion metric rows: `48/48`
- raw failures: `0`
- telemetry guard failures: `0`
- `candidate_telemetry_guard_summary.passed=true`
- `fleet_violation`: always `0`
- candidate route-count delta versus champion: always `0`

Runtime evidence is complete but not a separate win:

| Arm | Runtime status | Runtime confidence | Median runtime ratio | Runtime regression rate |
|---|---|---|---:|---:|
| `on` | `sufficient` | `high` | `0.9995` | `0.3958` |
| `record_only` | `sufficient` | `high` | `0.9998` | `0.4792` |

This matches the budget-exhausting CVRP runtime model: runtime is supporting
tie-break evidence, not standalone optimization evidence.

## Mechanism Activation

The size70 two-opt mechanism activated on eligible rows and did not trigger
route or fleet regressions.

Candidate phase telemetry:

| Arm | Initial two-opt improvements | Embedded two-opt improvements | Candidate ALNS improvements | Candidate best updates |
|---|---:|---:|---:|---:|
| `on` | 36 | 2465 | 468 | 468 |
| `record_only` | 36 | 2459 | 471 | 471 |

The prior Tier 1 Large-X replay showed phase-level construction/polish movement
without deeper ALNS incumbent-update leverage. Validation is slightly different:
best-update summaries are nonzero, but the final formal validation gate still
fails due missing hierarchical gain.

## Decision

The run is accepted as valid fixed-candidate validation evidence, but the
candidate fails the validation gate.

Do not launch frozen fixed replay for this size70 two-opt candidate.

Do not launch a seeded Scion CVRP campaign for this candidate as a validated
mechanism.

The useful result is diagnostic: the two-opt patch is mechanically active,
feasible, and directionally positive on several size70 validation cases, but it
does not clear the formal validation hierarchy. v0.4 should stop this
candidate here and move to the next pre-registered research gate, such as
broader no-LLM validation for the independent `regret4_repair` hypothesis or a
separate short warehouse debug, rather than extending size70 into frozen.
