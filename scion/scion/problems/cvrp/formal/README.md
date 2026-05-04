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
