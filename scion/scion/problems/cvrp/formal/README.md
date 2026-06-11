# CVRP Formal Readiness Assets

These files define the first real-CVRP campaign readiness package for Scion
v0.4. They are generated from `vrp/results/full_experiment_seed0_final.csv` and
keep benchmark instance paths as data-root-relative opaque strings such as
`cvrplib/A/A-n32-k5.vrp`.

The files do not copy or read raw CVRPLIB instances. Runtime execution must set
`SCION_PROBLEM_DATA_ROOT` to the repo-local `vrp` directory so solver subprocesses
can resolve those case paths from campaign workspaces.

Files:

- `protocol.yaml`: campaign protocol thresholds and case counts.
- `split_manifest.yaml`: screening/validation/frozen case paths plus synthetic canary.
- `seed_ledger.yaml`: fixed evaluation seeds per stage.
- `budgets.json`: runtime budgets, matrix metadata, and final-evidence defaults.
- `matrix.json`: formal model/seed/round matrix declaration.
- `manifests/*.json`: fixed case manifests for screening, validation, frozen, and final evidence.

BKS, gap, and BKS route counts are final-report fields only. Promotion remains
lexicographic on `fleet_violation` and `total_distance`.

## 2026-06 Formal Split Redesign

Screening was rebuilt from the seed-0 final ALNS/VNS ledger so it has measurable
headroom. The 16 screening cases are all `benchmark_feasible=True`, reference
clean, `route_gap=0`, and in the 2.5% to 10% seed-0 BKS-gap band. A/B/E/P
provide the cheap base coverage; CMT/M/tai add medium structure; one small X
case (`X-n110-k13`) adds a cheap X-family signal without moving the harder X
holdout into screening.

Validation keeps a distinct 12-case mix: near-threshold A/B/P/tai rows, harder
tai and F rows, plus small-to-medium X rows. This keeps validation meaningful
without duplicating screening. Frozen is now a 12-case X-only holdout in the
roughly 3% to 9% seed-0 gap band, replacing the previous near-solved `X-n106`
and >10% `X-n237`/`X-n513` rows with route-clean medium/large X cases. Final
evidence remains a separate X holdout and is not part of promotion.

Stage seeds are deterministic odd-prime ledgers:

- screening: `11, 29, 43, 59`
- validation: `47, 53, 71, 83`
- frozen: `61, 67, 89`
- final evidence: `0, 1, 2`

Runtime budgets are staged by case scale:

- canary/smoke: `10s`
- screening: `30s`
- validation: `30s`
- frozen: `60s`
- final evidence: `60s`

The formal protocol declares these budgets in `protocol.yaml` so campaign
execution uses them instead of the CLI fallback time limit. The CLI
`--time-limit-sec` remains a fallback for stages that do not declare an
override.
