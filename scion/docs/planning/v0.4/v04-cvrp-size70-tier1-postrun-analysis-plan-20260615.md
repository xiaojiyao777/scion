# CVRP Size70 Tier 1 Postrun Analysis Plan - 2026-06-15

## Purpose

This plan defines the postrun acceptance check for the no-LLM size70 two-opt
Large-X completion diagnostic launched at:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z`

The synced server root is:

`/home/clawd/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z`

This is mechanism-validity evidence only. It is not a Scion campaign, not LLM
evidence, not Protocol promotion evidence, and not `DecisionFeatures` input.
Runtime, BKS gap, phase activation, and best-update diagnostics remain
problem-owned postrun/proposal material under the v3 boundary.

## Required Inputs

- Launch report:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-tier1-largeX-launch-20260615.md`
- Candidate prep:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-fixed-replay-prep-20260615.md`
- Validation design:
  `scion/docs/planning/v0.4/v04-cvrp-size70-fixed-candidate-validation-design-20260615.md`
- Champion comparison curve:
  `/home/clawd/research/scion-experiments/v04-cvrp-largeX-runtime-curve-20260615T150454Z/summary.json`
- Candidate Tier 1 run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z`

## Planned Key Set

The accepted key set is exactly:

- Cases: `X-n401-k29`, `X-n573-k30`, `X-n641-k35`, `X-n1001-k43`
- Seeds: `61`, `67`, `89`
- Multipliers: `1`, `2`, `4`
- Total keys: `36`

All `36` planned keys must be accounted before any formal validation replay is
launched.

## Data Sources

Do not rely only on the raw solver output files. The raw files contain final
solution and `runtime.solver_algorithm_*` diagnostics, but wrapper fields such
as `case`, `seed`, `multiplier`, `status`, `returncode`, `bks_gap_pct`, and
`wall_elapsed_sec` are emitted in the runtime-curve JSONL log and the final
`summary.json` / `summary.csv`.

Postrun analysis should parse, in order:

1. `results/candidate_size70_largeX_full/summary.json` if present.
2. `results/candidate_size70_largeX_full/summary.csv` if present.
3. `run.log` JSONL rows as a fallback while the run is still in progress.
4. Individual solver output JSON files for `runtime.solver_algorithm_*`
   activation/actionability details.

## Acceptance Checks

Required checks:

- Planned-key accounting: `36/36` keys represented as completed, resumed,
  failed, or timed out.
- Completeness: count completed/resumed versus failed/timeout rows and identify
  missing case/seed/multiplier keys.
- Feasibility: completed outputs are feasible and recomputable where the raw
  solver file exists.
- Broad regression: compare candidate `total_distance`, BKS gap, routes, and
  status against the champion Large-X curve on matching keys.
- Phase activation: inspect `runtime.solver_algorithm_actionability_summary`
  and phase stats for `two_opt_polish_initial` and
  `two_opt_polish_embedded`.
- Best-update leverage: inspect `solver_algorithm_best_update_count`,
  `solver_algorithm_best_update_summary`, and
  `solver_algorithm_best_update_trace`.
- Runtime behavior: identify systematic candidate-only timeouts, budget hits,
  and stop reasons.
- Evidence decision: either allow validation replay, require more no-LLM
  diagnosis, or stop the size70 candidate before formal validation.

## Pass / Stop Rules

Pass Tier 1 only if:

- all `36` keys are accounted;
- there is no broad candidate regression against the champion Large-X curve;
- timeout/failure rows are sparse and explainable rather than systematic;
- two-opt phases activate on eligible rows or the report gives a concrete
  no-activation reason;
- best-update/actionability diagnostics support a plausible large-X mechanism.

Stop before formal validation if:

- key accounting is incomplete without a resume plan;
- candidate has systematic large-X regressions or candidate-only timeouts;
- two-opt phases do not activate on the intended size class;
- activation occurs but produces no large-X objective movement and no
  best-update leverage across the completed key set.

## Subagent Brief Hook

If delegated, the postrun analyst must read
`scion/design/scion-architecture-v3.md` first, then this plan and the launch
report. The analyst should produce a report under `scion/docs/experiments/v0.4/`
and must not start formal validation unless the main thread accepts the Tier 1
postrun result.
