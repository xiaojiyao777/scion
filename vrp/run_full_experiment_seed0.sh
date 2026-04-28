#!/usr/bin/env bash
set -euo pipefail

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

cd /home/xjy-ubuntu/projects/vrp
mkdir -p results/logs results/analysis_full_seed0

date
python validate_solutions.py cvrplib --output results/reference_validation_bad.csv --bad-only
python run_full_experiment.py cvrplib \
  --output results/full_experiment_seed0_final.csv \
  --seed 0 \
  --workers 2 \
  --time-limit 0 \
  --bks-time-limit 1 \
  --large-time-limit 0 \
  --large-dimension 2001 \
  --cw-threshold 1000 \
  --vns-threshold 200 \
  --alns-threshold 1000 \
  --max-destroy-customers 80 \
  --vns-iterations 50 \
  --instance-timeout 20 \
  --timeout-slack 5 \
  --memory-mb 4096 \
  --progress-every 100 \
  --resume
python analyze_results.py results/full_experiment_seed0_final.csv \
  --validation-report results/reference_validation_bad.csv \
  --exclude-invalid-reference \
  --exclude-benchmark-infeasible \
  --output-dir results/analysis_full_seed0_final
date
