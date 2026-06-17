# v0.4 Warehouse Candidate-Filter Guard Rerun 6R Postrun

Date: 2026-06-17

## Run

- Commit: `2774afd`
- Cell: `rep01/on_compact`
- Run root:
  `/home/clawd/research/scion-experiments/v04-warehouse-candidatefilter-rerun6r-2774afd-20260617T100032Z`
- Campaign:
  `/home/clawd/research/scion-experiments/v04-warehouse-candidatefilter-rerun6r-2774afd-20260617T100032Z/rep01/on_compact/campaign`
- Model: `gpt-5.5`
- Context: `compact-measurement-diagnostics`
- Measurement governance: `on`
- Requested rounds: `6`
- Wrapper exit: `0`

## Outcome

This run field-accepts the candidate-filter guard detector repair and rejects
warehouse research-quality acceptance.

The repair goal was narrow: prove the previous
`screening_or_lexicographic_guard` false negative no longer blocks executable
candidate-loop `continue` guards before Protocol. That check passed. The only
code-stage patch-quality block was `missing=bounded_candidate_policy`, not
`missing=screening_or_lexicographic_guard`.

The run still did not reach validation or frozen and produced no champion
promotion.

## Key Counts

- `run_validity.status`: `valid`
- `run_validity.reason`: `valid`
- `stopped_reason`: `max_rounds_exhausted`
- `effective_rounds_completed`: `6 / 6`
- `proposal_attempts`: `13`
- `proposal_attempts_total`: `15`
- `quality_blocks`: `7`
- `protocol_metric_results`: `8`
- `protocol_metric_stage_counts`: `screening=8`, `validation=0`,
  `frozen=0`
- `formal_screened_candidates`: `6`
- `champion_version`: `1`
- active branches: `3`

Postrun summary:

- `screening_pass_rate`: `0.0`
- `screening_gate_win_rate`: `0.25675675675675674`
- `screening_pair_wins/losses/ties`: `59 / 43 / 46`
- `screening_case_wins/losses/ties`: `19 / 11 / 44`
- `champion_promotions`: `0`
- verification failures: none

## Quality-Block Shape

The `7` quality blocks split into:

- `4` hypothesis-stage
  `warehouse_validation_transfer_quality_missing` blocks, all missing
  `validation_transfer_risk`.
- `1` code-stage `warehouse_validation_transfer_patch_quality_missing` block,
  missing `bounded_candidate_policy`.
- `2` branch-lesson semantic mismatch blocks with missing structured linkage
  fields.

The targeted `screening_or_lexicographic_guard` false positive did not recur.

## Branch Findings

- `merge_vehicles`:
  - state: `explore`
  - lineage status: `diagnostic_repair`
  - current head status: `discarded`
  - evidence tier: `weak_positive`
  - W/L/T: `7 / 1 / 6`
  - median delta: `775.0`, CI `[0.0, 3200.0]`
  - runtime ratio median: `0.48995121752772974`
  - telemetry status: `activation_missing_or_wiring_suspect`
  - allowed next actions: `repair`, `telemetry_wiring`
- `category_cluster_downsize`:
  - state: `explore`
  - lineage status: `checkpoint_retained`
  - evidence tier: `inactive`
  - W/L/T: `0 / 0 / 6`
  - median delta: `0.0`
  - follow-up required with retained checkpoint evidence.
- One clean open branch remains without evidence yet.

## Interpretation

Accepted:

- The candidate-filter guard detector repair worked in the field: direct
  candidate-loop guard shapes no longer show up as
  `screening_or_lexicographic_guard` quality blocks.
- The run completed cleanly, reached Protocol rows, and produced replayable
  postrun artifacts.
- The framework preserved a concrete weak-positive branch for follow-up rather
  than losing it.

Rejected:

- Research quality is still insufficient: no validation, no frozen row, no
  promotion.
- The active weak-positive `merge_vehicles` branch is blocked by telemetry
  activation/wiring suspicion, not by the guard detector.
- Proposal quality remains unstable: transfer-risk claims, bounded candidate
  policy, and branch-lesson semantic linkage still consume attempts.

## Next Step

Do not launch a broad WSL warehouse matrix yet.

The next task is branch-level postrun analysis for this run, focused on the
weak-positive `merge_vehicles` lineage:

1. Inspect the code patch and runtime telemetry export path for the
   `activation_missing_or_wiring_suspect` diagnosis.
2. Determine whether this is an agent patch instrumentation bug, a warehouse
   adapter telemetry-consumption bug, or a protocol/branch-lifecycle
   interpretation issue.
3. Inspect prompt/context and branch-lesson usage for the four
   transfer-risk blocks and two branch-lesson semantic mismatch blocks.
4. Only after that analysis should the next repair be implemented.
