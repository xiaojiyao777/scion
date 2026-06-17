# v0.4 Warehouse Helper-Guard Rerun 6R Postrun

Date: 2026-06-17

## Run

- Commit: `a1dba41`
- Cell: `rep01/on_compact`
- Run root:
  `/home/clawd/research/scion-experiments/v04-warehouse-helperguard-rerun6r-a1dba41-20260617T083245Z`
- Campaign:
  `/home/clawd/research/scion-experiments/v04-warehouse-helperguard-rerun6r-a1dba41-20260617T083245Z/rep01/on_compact/campaign`
- Model: `gpt-5.5`
- Context: `compact-measurement-diagnostics`
- Measurement governance: `on`
- Requested rounds: `6`
- Wrapper exit: `0`

## Outcome

This run is accepted as useful partial field evidence and rejected as
research-quality acceptance.

The repair goal was to verify that the warehouse problem-owned code-quality
gate no longer blocks executable helper-based split/cost guards before any
Protocol rows are produced. That narrow framework check passed: unlike the
stopped `bbb80db` diagnostic run, this rerun reached formal screening artifacts
and Protocol metrics.

It did not validate warehouse research quality. The run stopped at
`proposal_attempt_limit_exhausted` with no validation or frozen rows and no
promotion.

## Key Counts

- `run_validity.status`: `valid`
- `run_validity.reason`: `valid_partial_interrupted`
- `stopped_reason`: `proposal_attempt_limit_exhausted`
- `effective_rounds_completed`: `5 / 6`
- `proposal_attempts`: `18`
- `proposal_attempts_total`: `23`
- `quality_blocks`: `13`
- `protocol_metric_results`: `10`
- `protocol_metric_stage_counts`: `screening=10`, `validation=0`, `frozen=0`
- `formal_screened_candidates`: `5`
- `champion_version`: `1`
- `active_slots.used`: `0`
- `parked_lineages`: `3`

Postrun summary:

- `screening_pass_rate`: `0.0`
- `screening_case_win_rate`: `0.1388888888888889`
- `screening_pair_win_rate`: `0.24305555555555555`
- `champion_promotions`: `0`
- decisions: `continue_explore=8`, `expand_screening=1`, `abandon=1`
- verification failures: none

## Branch Findings

Three main lineages were parked:

- `merge_vehicles`: quality regression, `wins=0`, `losses=4`, `ties=2`,
  median delta `-4575.0`. Reason codes include
  `SCREENING_FAIL_WIN_RATE`, `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`,
  `TELEMETRY_ACTIVITY_FIELD_ALL_ZERO`, and `TELEMETRY_GUARD_FAILED`.
- `move_order`: marginal, `wins=1`, `losses=2`, `ties=3`, median delta `0.0`.
  The lineage was parked after loss-heavy follow-up and repeated code-quality
  blocks.
- `destroy_rebuild`: marginal, `wins=1`, `losses=2`, `ties=3`, median delta
  `0.0`. A checkpoint was retained, but the lineage still parked before
  validation because screening remained below gate and telemetry/effect
  diagnostics remained weak.

The run also created an abandoned `residual_tail_pack` branch with `no_effect`
evidence (`wins=0`, `losses=0`, `ties=6`) and missing telemetry activation.

## Quality-Block Shape

The `13` quality blocks split into:

- `4` hypothesis-stage blocks:
  `warehouse_validation_transfer_quality_missing`, mainly missing
  `validation_transfer_risk` or `runtime_bounded_acceptance`.
- `9` code-stage blocks:
  `warehouse_validation_transfer_patch_quality_missing`, all missing
  `screening_or_lexicographic_guard`.

The code-stage failures were not a recurrence of the earlier
`merge_vehicles.py` helper-based guard false positive. The new run reached
Protocol rows after `a1dba41`. Follow-up trace analysis showed that the later
blocks were primarily another detector false negative: blocked patches used
executable candidate-loop split/cost filters with `continue` and then returned
the original solution when no candidate was accepted. The previous static
detector accepted direct `return solution` guards and helper `return None`
guards, but missed direct candidate-filter guards such as `split_delta < 0`,
`split_delta == 0 and cost_delta <= 0`, and split-preserving cost-only forms.

## Interpretation

The framework repair is directionally useful but not sufficient for v0.4
warehouse research acceptance.

Accepted:

- The stale zero-Protocol-row failure from `bbb80db` is fixed.
- Prior quality blocks, repair templates, and missing-code-element feedback are
  visible in later prompts.
- Branch experience is retained and used: failed `subcategory_bin_repack`
  quality feedback appears in later hypothesis prompts, and lineages are parked
  with retained evidence rather than silently lost.

Rejected:

- Warehouse did not reproduce the v0.3-style repeated promotion behavior.
- The run did not reach validation or frozen.
- The problem-owned static detector still missed a legitimate executable guard
  shape and therefore consumed proposal attempts before Protocol.
- Most evidence remained screening-only, with low win rates and weak or failed
  telemetry effect signals.

## Next Step

The narrow code-stage behavior analysis is complete. The follow-up repair
belongs in `WarehouseDeliveryAdapter`: accept executable direct candidate-loop
`continue` guard shapes when the enclosing function also has a no-accepted-
candidate `return solution`, while preserving rejection of split-only,
string/comment-only, local-only, and missing-diagnostics patches.

After that repair is committed, run one short local warehouse `6R` acceptance
check on the server. Do not start a broad WSL warehouse matrix from this state.
