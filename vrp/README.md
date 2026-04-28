# CVRP Baseline

This directory contains the local CVRP baseline prepared for Scion v0.4.

The goal is not to provide a state-of-the-art CVRP solver. The goal is to provide
a strong enough, modular, reproducible baseline for Scion to improve with
agent-generated heuristic operators.

## Contents

```text
src/                         core CVRP solver modules
src/local_search/            VNS local-search operators
src/alns/                    ALNS destroy/repair/weight logic
main.py                      single-instance and simple batch CLI
benchmark.py                 batch benchmark helper
solve_instance.py            subprocess-safe single-instance runner
run_full_experiment.py       resumable full experiment runner
validate_solutions.py        reference .sol validation
analyze_results.py           CSV aggregation and reporting
docs/algorithm.md            algorithm design notes
docs/experiment_results_seed0.md
results/                     seed0 baseline evidence CSVs
```

`cvrplib/` contains local benchmark data and is intentionally ignored by git.

## Current Baseline Evidence

The seed0 full experiment is documented in:

- [docs/experiment_results_seed0.md](docs/experiment_results_seed0.md)

Primary artifacts:

```text
results/full_experiment_seed0_final.csv
results/reference_validation_bad.csv
results/analysis_full_seed0_final/summary_by_subset.csv
results/analysis_full_seed0_final/per_instance.csv
results/analysis_full_seed0_final/top_gaps.csv
```

High-level result:

```text
attempted EUC_2D instances = 10330
status=ok = 10330
timeout = 0
error = 0
CVRP feasible = 10330
benchmark_feasible = 10249
```

The A/B/P/E subsets are the most stable quick-regression candidates. X is the
most useful medium-scale optimization target because it still has meaningful
gap and room for improvement.

## Reproduce

From this directory:

```bash
bash run_full_experiment_seed0.sh
```

The script expects local CVRPLIB data under `cvrplib/`.
