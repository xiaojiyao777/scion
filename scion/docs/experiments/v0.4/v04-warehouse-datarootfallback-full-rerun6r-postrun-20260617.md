# Warehouse Data-Root Fallback Full 6R Postrun

Date: 2026-06-17
Commit: `5630697`
Branch: `codex/v04-evidence-repair-plan`

## Run

Run root:
`/home/clawd/research/scion-experiments/v04-warehouse-datarootfallback-full-rerun6r-5630697-20260617T132912Z`

Campaign:
`/home/clawd/research/scion-experiments/v04-warehouse-datarootfallback-full-rerun6r-5630697-20260617T132912Z/rep01/on_full/campaign`

Wrapper:

- `WRAPPER_EXIT_STATUS:0`
- `run_status.status=finished`
- `run_status.run_validity_status=valid`
- `last_stop_reason=max_rounds_exhausted`

Launch shape:

- copied production `problem.yaml`, `protocol_prod.yaml`,
  `split_manifest_prod.yaml`, and `seed_ledger.yaml`
- `SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-data`
- `SCION_WAREHOUSE_DATA_ROOT=/home/clawd/research/scion-data`
- `--rounds 6`
- `--time-limit-sec 30`
- `--measurement-governance on`
- `--proposal-context-ablation full`
- `--disable-early-stop`
- `--agentic-proposal`
- model `gpt-5.5`

The launch `launch.env` contains a recording-only shell quoting bug in the
human-readable stage-drain policy line, but the command log confirms
`SCION_STAGE_TRANSITION_DRAIN_LIMIT:<unset>` and the campaign started normally.

## Verdict

Framework field acceptance:

- The copied-config data-root fallback is field-accepted. The prior
  `invalid_no_protocol_rows` / `CANARY_CONFIG_ERROR` shape did not recur.
- All inspected formal metric rows resolved production cases with
  `resolved_safe_data_root` under `/home/clawd/research/scion-data`.
- The run reached formal Protocol, produced screening rows, and reached one
  validation row.

Research-quality acceptance:

- Rejected. The run produced no frozen row and no champion promotion.
- Champion stayed `v1`.
- The single validation candidate failed the validation gate with
  `VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`.

## Accounting

From `campaign_summary.json` / `status.json`:

- `run_validity.status=valid`
- `effective_rounds_completed=6/6`
- `campaign_steps=15`
- `proposal_attempts=11`
- `proposal_quality_blocks=5`
- `protocol_metric_results=10`
- stage counts: `screening=9`, `validation=1`, `frozen=0`
- `fresh_runtime_replay_protocol_results=0`
- `verification_failure_consumed_candidates=0`
- `formal_candidate_artifact_count=10`
- `formal_screened_candidates=5`
- `validation_protocol_results=1`
- `champion_version=1`

Status reconciliation caveat: the nested `run_validity` payload in
`campaign_summary.json` still reports `protocol_metric_results=6`, while the
top-level summary and final `status.json` report `10`. Use the final status
and explicit stage counts for postrun accounting; the run-validity status and
stage counts agree that the run is complete and valid.

## Protocol Rows

The run wrote 10 metric JSON rows:

| Stage | Mechanism | W/T/L | Median delta | Telemetry | Path safety |
| --- | --- | ---: | ---: | --- | --- |
| screening | `merge_vehicles` | `0/4/8` | `-3200.0` | `TELEMETRY_ACTIVITY_FIELD_ALL_ZERO` | safe |
| screening | `merge_vehicles` | `0/4/8` | `-3200.0` | `TELEMETRY_ACTIVITY_FIELD_ALL_ZERO` | safe |
| screening | `merge_vehicles` | `0/4/8` | `-3200.0` | `TELEMETRY_ACTIVITY_FIELD_ALL_ZERO` | safe |
| screening | `move_order` | `2/4/6` | `-450.0` | warning only | safe |
| screening | `cluster_cost_repack` | `7/3/10` | `-150.0` | warning only | safe |
| screening | `fill_tail_cost_compress` | `7/5/8` | `0.0` | `TELEMETRY_ACTIVITY_FIELD_ALL_ZERO` | safe |
| screening | `fill_tail_cost_compress` | `0/12/0` | `0.0` | `TELEMETRY_ACTIVITY_NOT_OBSERVED` | safe |
| screening | `swap_orders` | `6/3/3` | `150.0` | warning only | safe |
| screening | `swap_orders` | `15/6/7` | `300.0` | warning only | safe |
| validation | `swap_orders` | `8/1/6` | `-200.0` | warning only | safe |

The validation row had complete runtime evidence and no hard telemetry guard
failure. `swap_orders` activation/effect counters were present:
`operator_invocations` was positive in `15/15` runs, `accepted_moves` and
cost/effect counters were positive in `7/15` runs, and
`split_delta_sum` stayed zero. The gate failed because the objective evidence
did not show stable hierarchical gain, and runtime was slightly slower
(`runtime_ratio_median=1.025`, regression rate `0.733`).

## Quality Blocks

There were 5 proposal/code quality blocks:

- 3 `warehouse_validation_transfer_quality_missing` blocks with
  `missing=validation_transfer_risk`
- 1 `warehouse_validation_transfer_patch_quality_missing` block with
  `missing=bounded_candidate_policy`
- 1 `warehouse_validation_transfer_patch_quality_missing` block with
  `missing=screening_or_lexicographic_guard`

The `screening_or_lexicographic_guard` block was session
`549918fe-964b-46b7-b2ed-05bb041cea73` on a new
`vacate_subcategory_tail` operator. Scratch evidence also reported missing
effect telemetry for that generated patch. Treat this as a likely true quality
block or at minimum an item for targeted trace review, not as field proof that
the sequential split/cost detector regressed.

## Interpretation

This run accepts the copied-config data-root fallback and confirms that the
latest warehouse repair stack can again reach validation under production copied
configs. It also confirms that the framework can distinguish a measured but
insufficient candidate from telemetry/path failures: the validation candidate
was evaluated, had visible mechanism telemetry, and then failed closed on
objective evidence.

It does not prove warehouse effective research is restored. The campaign still
did not reach frozen or promotion, repeated true proposal-quality failures
remain, and the best validation candidate failed `VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`.

## Next Step

Do not launch a broad warehouse matrix from this evidence. The next warehouse
work should be a focused branch/trace analysis of:

- why the `swap_orders` branch reached validation but lost hierarchical gain;
- whether validation-positive cost-only wins need stronger split-positive
  proposal guidance;
- whether the remaining quality blocks are true blocks or narrow detector
  misses, starting with session `549918fe-964b-46b7-b2ed-05bb041cea73`.
