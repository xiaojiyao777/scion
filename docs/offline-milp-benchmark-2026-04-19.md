# Offline MILP Benchmark Launch — 2026-04-19

## Purpose
Launch a long-running offline MILP benchmark sweep across both synthetic and production instance corpora.

## Scope
Two detached processes are used so synthetic and production families run independently:
- synthetic manifest: `scion/problems/warehouse_delivery/split_manifest.yaml`
- production manifest: `scion/problems/warehouse_delivery/split_manifest_prod.yaml`

## Runner
- Script: `surrogate/run_offline_milp_batch.py`
- Python env: `/home/clawd/miniconda3/envs/claw/bin/python`
- Solver: `HiGHS`
- Warm start: surrogate VNS, `max_iterations=200`, `random_seed=42`

## Output directory
- `/home/clawd/research/scion-experiments/offline-milp-benchmark/20260419-175407`

Subdirectories:
- `synthetic/`
- `production/`

Each instance emits one JSON record with at least:
- `milp_status`
- `milp_exact`
- `milp_verified`
- `milp_f1`, `milp_f2`
- `milp_lb_f1`, `milp_lb_f2`
- `phase1_gap`, `phase2_gap`
- `warm_start_f1`, `warm_start_f2`
- `champion_vs_milp_delta_f1`, `champion_vs_milp_delta_f2`
- `oracle_feasible`, `oracle_consistent`

Incremental summaries:
- `summary.partial.json`

Final summaries:
- `summary.json`

## Notes
- Small instances are given larger time budgets to maximize exact solves.
- Medium / large / xlarge instances are expected to often return incumbent + lower bound rather than exact solutions.
- This sweep is intended as an offline benchmark provider corpus, not as a Scion inner-loop evaluator.

## Launch metadata
- synthetic PID: `1159929`
- production PID: `1159930`
- launch time: `2026-04-19 17:54` Asia/Shanghai

## Environment issue encountered
Initial launch with system `python3` failed because the default environment lacked MILP deps:
- `ModuleNotFoundError: No module named 'pulp'`

Resolved by switching to the `claw` conda env.
