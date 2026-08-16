# v0.4 Warehouse Calibration Provenance Resolution

Date: 2026-06-29

## Purpose

The current v0.4 task audit found that both warehouse `problem-v1.yaml` copies
referenced `calibration/aa_noise_floor.json`, but the corresponding checked-in
artifact appeared to be missing under the warehouse spec directories. That
interpretation used the YAML directory as the base path. Current runtime
semantics resolve `calibration_ref` under `problem-v1.root_dir`.

## Resolution

No duplicate package-local calibration artifact is required. Both warehouse
spec copies set `root_dir` to the repository `surrogate` package:

- `scion/problems/warehouse_delivery/problem-v1.yaml`
- `scion/scion/problems/warehouse_delivery/problem-v1.yaml`

Therefore their declared `calibration_ref: calibration/aa_noise_floor.json`
resolves to the canonical checked-in artifact:

`surrogate/calibration/aa_noise_floor.json`

That compact artifact records the Phase 1 warehouse modify A/A source artifact:

`/home/clawd/research/scion-experiments/v04-phase1-aa-warehouse-screening-modify-r3-defaultbudget-20260611T164426Z-claw/aa_noise_floor.json`

Source artifact SHA256 recorded inside the checked-in compact summary:

`5e34c863356bc74a9d2254dbde1d0a0945c88d56ca7201a4e033344b9718146f`

## Verification

Both warehouse spec copies resolve through `root_dir` as ready through
`measurement_readiness_status(..., as_of=2026-06-19)`:

- status: `ready`
- reason_code: `ok`
- n_pairs: `36`
- mde_at_power_80: `577.5`
- calibration_evidence_level: `summary_only`

The artifact remains problem-owned measurement diagnostics. It is readiness and
proposal-context evidence only, not promotion evidence and not
`DecisionFeatures` input.
