# CVRP Formal Research Assets

These files define the current real-CVRP research matrix for Scion v0.4. They
are derived from `vrp/results/full_experiment_seed0_final.csv` and
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

- screening mechanism stage: `11, 29, 43, 59`
- screening quality expansion: `11, 29, 43, 59, 73, 79, 97, 103`
- validation: `47, 53, 71, 83`
- frozen: `61, 67, 89`
- final evidence: `0, 1, 2`

The R2 screen uses paired per-case median `total_distance` direction with a
zero equivalence band.  Initial screening evaluates 8 cases x 4 seeds and can
only request the exact expansion.  Expanded screening evaluates 12 cases x 8
seeds and is the only screening result that can advance to validation.
Validation and frozen use all 12 declared cases with four and three seeds,
respectively.  Fleet regression remains a separate protected-objective veto.

R2 is deliberately marked uncalibrated.  The retained MDE=9.9 artifact used
the old 8-case x 4-seed pair-level estimator, while a later 8-seed A/A estimate
of 9.6 also used a different case population, estimator and runtime.  They are
historical low-power diagnostics, not R2 power claims.  In particular, neither
shows that an effect near the practical delta of 2 can be excluded.

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
