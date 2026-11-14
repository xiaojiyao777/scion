# v0.4 Warehouse MergeVehicles Branch Analysis

Date: 2026-06-17

## Scope

This note analyzes the weak-positive `merge_vehicles` lineage from the local
warehouse `6R` rerun:

- Run root:
  `/home/clawd/research/scion-experiments/v04-warehouse-candidatefilter-rerun6r-2774afd-20260617T100032Z`
- Campaign:
  `/home/clawd/research/scion-experiments/v04-warehouse-candidatefilter-rerun6r-2774afd-20260617T100032Z/rep01/on_compact/campaign`
- Branch: `8d43c608-e442-4ab1-8d74-1e157f0b4e04`
- Final hypothesis: `4f5c1974-2086-45f7-9d52-29f397ca438f`
- Final metrics:
  `metrics/0adec3ee-93f7-4006-ad78-34a5a09cdb3d.json`
- Formal candidate:
  `artifacts/formal_candidates/8d43c608/screening-4f5c1974-2086-45f7-9d52-29f397ca438f-f084edc67b85ad38/candidate.patch.json`

## Branch Evidence

The branch has real but low-SNR screening evidence, not a telemetry export
failure:

- Final screening W/L/T: `7 / 1 / 6`
- Final pair W/L/T: `17 / 4 / 7`
- Median delta: `775.0`, CI `[0.0, 3200.0]`
- Positive cases: `instance_prod_scr_s02.json`,
  `instance_prod_scr_s03.json`, `instance_prod_scr_ms01.json`,
  `instance_prod_scr_ms03.json`, `instance_prod_scr_m03.json`
- Negative case: `instance_prod_scr_s04.json`
- Runtime ratio median: `0.48995121752772974`, with low cached champion
  confidence and proposal-only runtime guidance

The objective movement is cost-only. In the final metrics, every nonzero
candidate/champion delta is decided by `total_cost`; `subcategory_splits` is
`0.0` for both wins and losses.

## Telemetry Finding

The final candidate exports the expected warehouse runtime diagnostics. The
candidate patch initializes `self.validation_transfer_diagnostics` in
`operators/merge_vehicles.py` and updates the standard keys:

- `operator_invocations`
- `eligible_vehicle_or_order_groups_seen`
- `accepted_moves`
- `split_delta_sum`
- `cost_delta_sum`
- `improving_move_count`

The raw metrics confirm those fields are present under both
`candidate_runtime.operator_diagnostics.merge_vehicles` and
`candidate_runtime.validation_transfer_diagnostics.merge_vehicles`.

The final telemetry guard passed:

- `candidate_runs=28`
- activation fields present and positive in all candidate runs
- `cost_delta_sum` present and positive in all candidate runs
- `improving_move_count` present and positive in all candidate runs
- `split_delta_sum` present but zero in all candidate runs

The remaining warning is specifically:

- `TELEMETRY_EFFECT_NOT_OBSERVED` on
  `operator_diagnostics.merge_vehicles.split_delta_sum`

This is not an agent instrumentation bug and not a warehouse adapter
telemetry-consumption bug. The mechanism is doing split-preserving cost
compression, while the interpretation path still treats the declared split
effect field as if its zero value means no mechanism effect.

## Source Interpretation

Current deterministic interpretation creates a misleading branch label:

- `scion/scion/core/telemetry_validation.py` emits
  `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC` when a declared effect field is present
  but has no positive candidate values.
- `scion/scion/core/decision_finalizer.py` maps the repairable telemetry path
  to `branch_code_status=telemetry_wiring_suspect` and
  `last_telemetry_outcome=activation_missing_or_wiring_suspect`.
- Branch cards then expose allowed next actions `repair` /
  `telemetry_wiring`, even though the actual final evidence is activation
  observed plus positive cost effect and protected split preservation.

The next repair should therefore be branch-lifecycle/protocol interpretation,
with a prompt-guidance follow-up. It should not start by changing the
candidate operator or warehouse telemetry export path.

## Quality-Block Pattern

The `7` proposal-quality blocks split into:

- `4` hypothesis-stage
  `warehouse_validation_transfer_quality_missing` blocks, each missing
  `validation_transfer_risk`
- `1` code-stage
  `warehouse_validation_transfer_patch_quality_missing` block, missing
  `bounded_candidate_policy`
- `2` branch-lesson semantic mismatch blocks

The first two categories are doing useful pressure work: they forced later
proposals to name transfer risk, bounded candidate policy, and split-vs-cost
effect scope. The branch-lesson mismatch pattern is a prompt/context quality
issue, but it is secondary to the deterministic interpretation issue above.

## Repair Decision

Next repair: protocol/lifecycle interpretation, then prompt/branch-lesson
guidance.

Concrete target:

1. Distinguish `cost_effect_with_protected_split_preserved` from
   `telemetry_effect_zero` when:
   - activation fields are observed,
   - at least one declared non-protected effect field is positive,
   - a protected higher-priority field is present and zero because the
     objective is preserved, and
   - objective deltas show the same protected-field tie plus lower-priority
     improvement pattern.
2. Do not label that state as `activation_missing_or_wiring_suspect`.
3. Branch cards should surface same-branch refinement, parameterization, or
   clean cost-generalization follow-up before `telemetry_wiring` for this
   pattern.
4. Prompt guidance should tell APS that same-branch weak-positive reuse may
   preserve the split-protection lesson and target cost-generalization, instead
   of treating zero `split_delta_sum` as instrumentation repair.

## Acceptance Criteria For The Next Code Repair

- Unit coverage proves a telemetry guard with positive `cost_delta_sum` and
  zero protected `split_delta_sum` does not become
  `activation_missing_or_wiring_suspect`.
- Branch evidence/cards retain the weak-positive evidence and show a
  cost-effect/preserved-split outcome.
- The old true-no-effect case still produces telemetry diagnostic pressure.
- The old true-missing-activation or all-zero activity case still requires
  telemetry repair.
- No validation/frozen raw detail is exposed to APS or Decision.

Do not launch a broad WSL warehouse matrix until this interpretation repair is
implemented and covered by focused unit tests.
