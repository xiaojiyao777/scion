# CPLEX Final Results Package

Created: 2026-04-26 13:05:01

## Contents

- `production/`: consolidated CPLEX production result JSONs (35 instances)
- `synthetic/`: consolidated CPLEX synthetic result JSONs (48 instances)
- `summary_all.json`: all CPLEX results with source provenance
- `comparison/cplex_vs_highs.csv`: per-instance comparison with HiGHS baseline
- `comparison/cplex_vs_highs_summary.json`: aggregate comparison metrics
- `sources/`: source summary files copied for auditability

## CPLEX Status Counts

- optimal: 68
- feasible: 9
- infeasible: 5
- timeout: 1

## HiGHS Status Counts

- optimal: 73
- infeasible: 5
- feasible: 4
- timeout: 1

## Objective Comparison

- same_objective: 62
- not_comparable_objective: 5
- cplex_better_f2: 9
- cplex_better_f1: 7

Interpretation: lower `f1` is better; if `f1` ties, lower `f2` is better.

## Status Transitions HiGHS -> CPLEX

- feasible->feasible: 1
- feasible->optimal: 3
- infeasible->infeasible: 5
- optimal->feasible: 7
- optimal->optimal: 65
- optimal->timeout: 1
- timeout->feasible: 1


## HiGHS Status Caveat

Historical HiGHS `milp_status=optimal` should be treated as a reported solver/API status, not as a strict optimality certificate. There are 16 matched instances where HiGHS reported `optimal` but CPLEX found a strictly better lexicographic objective (`f1`, then `f2`). Many HiGHS `optimal` rows also have phase runtimes at or above the configured phase limits, consistent with time-limit incumbents being promoted to `optimal` by the wrapper/status handling.

See `comparison/highs_status_audit.csv` and `comparison/highs_status_audit_summary.json` for the flagged rows.

## Main Findings

- Matched instances: 83.
- CPLEX has the same objective as HiGHS on 62 matched instances.
- Objective improvements by CPLEX: 16.
- Objective regressions vs HiGHS: 0.
- Cases where CPLEX verified a solution while HiGHS record was not verified: 1.

## Source Policy

Production uses `offline-milp-benchmark/cplex-production`, with day1/day2 overwritten by `offline-milp-benchmark/cplex-production-day-rerun` because the original CPLEX run had a file-interface naming bug.

Synthetic uses `offline-milp-benchmark/cplex-synthetic`, with xxx01/xxx02 added from `offline-milp-benchmark/cplex-synthetic-xxx-rerun`.

## Verification Improvements

- synthetic/instance_v4_fro_xxx02.json: HiGHS status=timeout, verified=False -> CPLEX status=feasible, verified=True; objective=(570, 1720900)

## Objective Differences

- production/instance_prod_fro_x02.json: not_comparable_objective, HiGHS=(None, None), CPLEX=(None, None)
- production/instance_prod_scr_m02.json: not_comparable_objective, HiGHS=(None, None), CPLEX=(None, None)
- production/instance_prod_scr_ml03.json: not_comparable_objective, HiGHS=(None, None), CPLEX=(None, None)
- production/instance_prod_scr_s04.json: cplex_better_f2, HiGHS=(0, 29000), CPLEX=(0, 28700)
- production/instance_prod_val_l03.json: not_comparable_objective, HiGHS=(None, None), CPLEX=(None, None)
- synthetic/instance_v3_scr_l01.json: cplex_better_f2, HiGHS=(10, 92400), CPLEX=(10, 75900)
- synthetic/instance_v3_scr_l02.json: cplex_better_f1, HiGHS=(33, 110400), CPLEX=(20, 97700)
- synthetic/instance_v3_scr_l03.json: cplex_better_f1, HiGHS=(50, 153300), CPLEX=(42, 122500)
- synthetic/instance_v3_scr_l04.json: cplex_better_f2, HiGHS=(46, 134700), CPLEX=(46, 109800)
- synthetic/instance_v3_scr_m02.json: cplex_better_f2, HiGHS=(12, 105600), CPLEX=(12, 79200)
- synthetic/instance_v3_scr_m04.json: cplex_better_f2, HiGHS=(17, 72600), CPLEX=(17, 66000)
- synthetic/instance_v3_scr_m05.json: cplex_better_f2, HiGHS=(14, 82800), CPLEX=(14, 64200)
- synthetic/instance_v3_scr_m06.json: cplex_better_f2, HiGHS=(10, 75900), CPLEX=(10, 59700)
- synthetic/instance_v3_val_l01.json: cplex_better_f1, HiGHS=(31, 75700), CPLEX=(11, 62700)
- synthetic/instance_v4_fro_m02.json: cplex_better_f2, HiGHS=(12, 66000), CPLEX=(12, 56100)
- synthetic/instance_v4_fro_x06.json: not_comparable_objective, HiGHS=(None, None), CPLEX=(None, None)
- synthetic/instance_v4_scr_ml01.json: cplex_better_f2, HiGHS=(7, 49500), CPLEX=(7, 43700)
- synthetic/instance_v4_scr_ml02.json: cplex_better_f1, HiGHS=(22, 77700), CPLEX=(12, 79200)
- synthetic/instance_v4_scr_ml03.json: cplex_better_f1, HiGHS=(33, 79200), CPLEX=(22, 77700)
- synthetic/instance_v4_scr_ml04.json: cplex_better_f1, HiGHS=(23, 73700), CPLEX=(15, 73200)
- synthetic/instance_v4_val_m02.json: cplex_better_f1, HiGHS=(26, 89900), CPLEX=(12, 86100)
