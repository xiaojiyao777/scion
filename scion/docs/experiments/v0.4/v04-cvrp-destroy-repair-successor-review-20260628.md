# CVRP Destroy/Repair Successor Review

Date: 2026-06-28

## Scope

This report records the local successor4 CVRP run after the construction
successor review repair. It validates that Scion can route away from reviewed
bounded-local-search and construction attempts into a problem-owned
destroy/repair successor, then reject it from direct evidence when the measured
solver effect is below MDE.

The change remains an experiment result only. No generic core, scheduler,
DecisionFeatures, Protocol gate, or promotion logic was changed.

## Run

- Root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor4-6a50fcba-local-2r-gpt55-20260628T142639Z-claw-2r-gpt55-20260628T142639Z-claw`
- Runtime commit: `6a50fcba`
- Model: `gpt-5.5`
- Resume source:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor3-b430c646-local-1r-gpt55-20260628T133031Z-claw/campaign`
- Wrapper status: valid/complete, wrapper exit `0`
- Postrun readiness after rebuild: `current_run_analysis_ready=true`,
  `delegation_ready=true`, no failed required or optional checks

Command used for the readiness recheck:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python \
  scion/tools/check_postrun_acceptance.py \
  /home/clawd/research/scion-experiments/v04-cvrp-successor4-6a50fcba-local-2r-gpt55-20260628T142639Z-claw-2r-gpt55-20260628T142639Z-claw \
  --require-current-run-ready --format json
```

## Result

The run selected the intended successor family:

- target file: `policies/baseline_modules/destroy_repair.py`
- mechanism id: `angular_sector_removal`
- mechanism family: `destroy_repair_selection`

Protocol evidence:

- 2/2 effective screening rows
- 2 formal candidate artifacts
- 2 proposal attempts
- 0 proposal quality blocks
- 0 active-slot blocks
- champion stayed `v1`
- promotions `0`
- rows at or above CVRP MDE `0`
- both rows had `ci_high_below_mde=true`

Effect rows:

| Mechanism | Win rate | Median delta | CI high | Effect/MDE | Positive at MDE |
|---|---:|---:|---:|---:|---|
| `angular_sector_removal` | 0.25 | -3.25 | 6.5 | -0.328283 | false |
| `angular_sector_removal` | 0.25 | 0.0 | 5.0 | 0.0 | false |

Protected-case evidence was present but negative: CMT2 and CMT4 were observed
in both rows, with median total-distance deltas below zero in both rows.

## Interpretation

This is effective research behavior, not solver progress. Scion followed the
prepared successor guidance away from reviewed bounded-local-search mechanisms
and the checklist-unproven construction seed path, selected a materially
different destroy/repair mechanism, produced two formal screening rows, and
proved the required activation/objective/phase/protected-case checklist.

The candidate itself should not be promoted or repeated unchanged:
`cvrp_successor_summary` marks `destroy_repair_selection` checklist `proven`
with outcome `measured_no_positive_at_mde`.

Next CVRP work should avoid repeating `angular_sector_removal`. A successor can
still stay in destroy/repair if it names a materially different removal/repair
causal path with direct objective-effect telemetry, or it can return to
construction only with same-run seed-baseline or accepted-delta evidence.
