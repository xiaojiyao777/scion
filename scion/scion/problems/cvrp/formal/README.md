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

## 2026-08 R3 Formal Split

Quality screening, validation and frozen each contain 12 outcome-blind cases
with family, dimension and seed-0 headroom coverage. The three blocks are
mutually exclusive. A fourth disjoint 12-case block is reserved for a manual
post-campaign comparison against original B0 and is not available to proposal
or campaign search context. The JSON manifests and YAML split are the exact
case authorities; this overview does not override them.

Stage seeds are deterministic odd-prime ledgers:

- screening mechanism stage: `11, 29, 43, 59`
- screening quality expansion: `11, 29, 43, 59, 73, 79, 97, 103`
- validation: `47, 53, 71, 83, 107, 109, 113, 127`
- frozen: `61, 67, 89, 131, 137, 139, 149, 151`
- final evidence: `157, 163, 167, 173, 179, 181, 191, 193`

R3 uses the median paired `total_distance` effect within each case and a zero
equivalence band. Initial screening evaluates the first 8 quality cases x 4
seeds and can only request the exact expansion. Expanded quality screening
evaluates 12 cases x 8 seeds and is the only screening result that can advance.
Quality, validation and frozen require case net score `(W-L)/12 >= 0.25`, case
loss rate `L/12 <= 0.20`, the declared practical median effect and CI low
`>= 0`. Fleet regression remains a separate protected-objective veto.

Historical MDE values 9.9 and 9.6 used incompatible pair-level estimators and
remain low-power diagnostics. R3 ran three provider-free same-seed A/A
diagnostics; each observed rule was false and each fixed 12-case/two-seed stage
population had 0/2,000 label-swap null passes. This is not a matched MDE or
power estimate and does not show that an effect near the practical delta of 2
can be excluded.

Runtime budgets are staged by case scale:

- canary/smoke: `10s`
- dimensions through 100: `30s`
- dimensions 101-200: `45s`
- dimensions 201-350: `60s`
- dimensions 351-700: `90s`
- dimensions 701-1001: `120s`

The formal protocol declares these budgets in `protocol.yaml` so campaign
execution uses them instead of the CLI fallback time limit. The CLI
`--time-limit-sec` remains a fallback for stages that do not declare an
override. `CMT3` and `CMT4` have fixed 45-second aliases because their names do
not encode dimension; `CMT2` uses the 30-second default.
