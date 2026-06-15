# CVRP Two-Opt Size70 Large-X Diagnostic Replay Launch - 2026-06-15

## Purpose

This no-LLM replay tests the `size70` two-opt polish variant on large-X cases
after it passed the follow-up smoke gate. The goal is mechanism diagnosis:
determine whether scale-gated `_two_opt_intra` polish under `USE_VNS=False`
creates large-X search leverage, or whether the smoke improvement is limited to
small/medium cases.

This is not Scion Protocol evidence and not promotion evidence.

## Roots

- Experiment root:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`
- WSL tmux session:
  `scion_cvrp_twoopt_size70_large_1848`
- Candidate workspace:
  `workspaces/candidate_twoopt_size70`

## Candidate

The candidate is the follow-up `size70` variant:

- `USE_VNS=False`
- run `_two_opt_intra` initial and embedded polish only when
  `instance.customer_count >= 70`

The gate is a diagnostic scale gate derived from the smoke: B rows with route
counts `6` and `9` regressed under ungated polish, while route-count `10` and
`17` rows improved. The large-X replay should not be used to claim the exact
`70` threshold is production-ready.

## Replay Shape

- Cases:
  - `cvrplib/X/X-n401-k29.vrp`
  - `cvrplib/X/X-n573-k30.vrp`
  - `cvrplib/X/X-n641-k35.vrp`
  - `cvrplib/X/X-n1001-k43.vrp`
- Seeds: `61`, `67`, `89`
- Multipliers: `1`, `4`
- Parallelism: `4`
- Timeout padding: `900s`
- Baseline summary:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-largeX-runtime-curve-20260615T150454Z/summary.csv`

Expected outputs:

- `results/candidate_size70_largeX/summary.csv`
- `results/candidate_size70_largeX/summary.json`
- `results/largeX_compare_size70.paired.csv`
- `results/largeX_compare_size70.summary.json`

## Acceptance

This replay is useful if it completes enough matched pairs to distinguish:

- objective improvement versus baseline on large-X rows;
- route/fleet regressions;
- timeout or runtime-completeness regressions;
- best-update density and two-opt activation on eligible large-X rows.

Even a positive result remains problem-owned diagnostic evidence. A later Scion
LLM campaign can use it only as a concise human-approved hypothesis seed, not
as a deterministic `DecisionFeatures` input.
