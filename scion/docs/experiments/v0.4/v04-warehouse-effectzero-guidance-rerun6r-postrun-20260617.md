# v0.4 Warehouse Effect-Zero Guidance Rerun 6R Postrun

Date: 2026-06-17

## Run

- Commit: `8688ac9`
- Cell: `rep01/on_compact`
- Run root:
  `/home/clawd/research/scion-experiments/v04-warehouse-effectzero-guidance-rerun6r-8688ac9-20260617T105940Z`
- Campaign:
  `/home/clawd/research/scion-experiments/v04-warehouse-effectzero-guidance-rerun6r-8688ac9-20260617T105940Z/rep01/on_compact/campaign`
- Model: `gpt-5.5`
- Context: `compact-measurement-diagnostics`
- Measurement governance: `on`
- Requested rounds: `6`
- Wrapper exit: `0`

## Outcome

This run field-accepts the targeted screening effect-zero guidance repair, but
rejects warehouse research-quality acceptance.

The targeted repair was narrow: nonblocking
`TELEMETRY_EFFECT_ZERO_DIAGNOSTIC` should not be collapsed into
`activation_missing_or_wiring_suspect` or force a telemetry-wiring repair path
when the telemetry guard passes and activation is observed. That behavior was
observed in the field: screening rows with `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`
continued through ordinary screening lifecycle, including `expand_screening`
and then `queue_validate`.

The final branch did end as `telemetry_wiring_suspect`, but for a different
and valid reason: the validation row had hard repairable telemetry codes
(`VALIDATION_TELEMETRY_REPAIRABLE`, `TELEMETRY_VALIDATION_REPAIRABLE`) because
`operator_diagnostics.swap_orders.accepted_moves` was present but all-zero on
validation. That is not the screening effect-zero overlabeling bug fixed by
`8688ac9`.

## Key Counts

- `run_validity.status`: `valid`
- `run_validity.reason`: `valid`
- `stopped_reason`: `max_rounds_exhausted`
- `effective_rounds_completed`: `6 / 6`
- `proposal_attempts`: `12`
- `proposal_attempts_total`: `12`
- `quality_blocks`: `6`
- `protocol_metric_results`: `7`
- `protocol_metric_stage_counts`: `screening=6`, `validation=1`,
  `frozen=0`
- `formal_candidate_count`: `8`
- `champion_version`: `1`
- active branches: `1`

Postrun summary:

- `screening_pass_rate`: `0.3333`
- `screening_gate_win_rate`: `0.15384615384615385`
- `screening_pair_wins/losses/ties`: `38 / 32 / 34`
- `screening_case_wins/losses/ties`: `8 / 7 / 37`
- `champion_promotions`: `0`
- verification failures: none

Decision counts:

- `abandon`: `3`
- `continue_explore`: `1`
- `expand_screening`: `1`
- `queue_validate`: `1`
- `validation_repair_required`: `1`

## Effect-Zero Field Acceptance

The final `swap_orders` branch shows the intended screening behavior:

- Initial screening decision: `expand_screening`
  - reason codes:
    `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`,
    `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`
  - telemetry guard: passed
  - activation: observed
  - effect: aggregate positive, with protected
    `operator_diagnostics.swap_orders.split_delta_sum` all-zero
- Expanded screening decision: `queue_validate`
  - reason codes:
    `SCREENING_EXPAND_EXHAUSTED_PAIR_SIGNAL_POLICY_PASS`,
    `SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE`,
    `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`
  - DecisionFeatures: W/L/T `4 / 1 / 9`, median delta `275.0`,
    CI `[-50.0, 500.0]`, pair W/L/T `15 / 7 / 6`
  - telemetry guard: passed
  - activation: observed
  - cost/effect counters: positive on screening
  - protected split counter: zero

This is the target acceptance signal: screening effect-zero diagnostics no
longer force a telemetry-wiring branch state before validation.

## Validation Failure

The validation row correctly failed:

- decision: `validation_repair_required`
- reason codes:
  `VALIDATION_TELEMETRY_REPAIRABLE`,
  `TELEMETRY_VALIDATION_REPAIRABLE`,
  `VALIDATION_TELEMETRY_DIAGNOSTIC_RETRY`,
  `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`
- DecisionFeatures: W/L/T `2 / 3 / 0`, median delta `-200.0`,
  CI `[-3600.0, 900.0]`, pair W/L/T `7 / 8 / 0`
- telemetry guard: failed
- hard failure:
  `TELEMETRY_ACTIVITY_FIELD_ALL_ZERO` on
  `operator_diagnostics.swap_orders.accepted_moves`
- effect fields:
  `cost_delta_sum`, `improving_move_count`, and `split_delta_sum` were all
  present but all-zero on validation.

This is evidence of a real validation-transfer failure, not a framework
overlabeling failure.

## Quality-Block Shape

The `6` proposal-quality blocks split into:

- `3` hypothesis-stage
  `warehouse_validation_transfer_quality_missing` blocks, all missing
  `validation_transfer_risk`.
- `2` code-stage
  `warehouse_validation_transfer_patch_quality_missing` blocks:
  one missing `bounded_candidate_policy`, one missing
  `screening_or_lexicographic_guard`.
- `1` hypothesis-stage
  `warehouse_operator_telemetry_identity_mismatch`, where a
  `change_vehicle_type.py` proposal declared the non-exported mechanism id
  `bounded_resize` instead of the registry/export key
  `change_vehicle_type`.

The `screening_or_lexicographic_guard` block happened on a multi-step
`change_vehicle_type.py` exact-replace patch whose output body is omitted in
the compact session output. It needs a separate replay/adapter-quality
inspection before classifying it as a true missing guard or a detector false
negative.

## Interpretation

Accepted:

- The effect-zero guidance repair works on real formal screening rows.
- Nonblocking screening effect-zero did not route the branch directly to
  telemetry wiring repair.
- The field run reached validation from a pair-level diagnostic screening
  signal without changing the generic Decision gate.

Rejected:

- Warehouse research quality is still insufficient: no promotion, no frozen
  evidence, and validation failed.
- Proposal quality remains unstable and consumed `6 / 12` attempts.
- The strongest remaining repeated blocker is not WSL/server resources; it is
  the agent's ability to satisfy problem-owned validation-transfer risk,
  telemetry identity, bounded candidate policy, and executable guard
  constraints.

## Next Step

Do not start a broad WSL warehouse matrix from this state.

The next task is a focused proposal-quality repair:

1. Analyze the blocked `change_vehicle_type.py` exact-replace session
   `f7851de0-0fee-4420-b20d-3c27df9bfd73` to classify the
   `screening_or_lexicographic_guard` block as true missing guard or detector
   false negative.
2. Convert repeated validation-transfer and telemetry-identity blocks into a
   shorter mandatory schema/patch skeleton in the problem-owned warehouse
   prompt/quality feedback path.
3. Preserve the v3 boundary: do not relax Decision gates, and do not treat the
   validation row as evidence of generalizable improvement.
