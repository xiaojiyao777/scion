# CVRP Candidate Large-X Replay Launch

Date: 2026-06-15

Purpose: replay the two Phase C ALNS-only validation-positive candidates on
large-X holdout cases with direct no-LLM solver calls. This checks whether the
validation signal survives the frozen-stage scale/budget shift, and whether
candidate mechanisms produce any best-update activity under larger budgets.

This is problem-owned postrun diagnostics. BKS gap, best-update traces,
candidate mechanism labels, and runtime curves must remain outside
`DecisionFeatures`.

## Targets

Primary replay targets:

- `rep01/alns_only`, branch `4504a238-304c-4414-9246-43c6f9c576a4`,
  hypothesis `f1bb98a7-4e4f-4f83-bb01-309fa3698e02`, formal artifact
  `34438fdef36ae405`. Mechanism: route-limit-aware regret repair. Phase C
  validation had median delta `51.0`, MDE `4.65`, effect-to-MDE `10.97`, then
  collapsed at frozen with median delta `4.0` and effect-to-MDE `0.86`.
- `rep02/alns_only`, branch `cc6f489c-68a0-434a-a804-1a97afbb61a6`,
  hypothesis `af2561e4-8d2e-4cee-9b7f-9cfdffc52a7f`, formal artifact
  `3da65bbd98a7b22b`. Mechanism: adaptive destroy-size schedule plus
  lexicographic SA acceptance guard. Phase C validation had median delta
  `20.75`, MDE `4.65`, effect-to-MDE `4.46`, then collapsed at frozen with
  median delta `0.0`.

## Design

- Runner: `scion/tools/cvrp_runtime_curve.py`.
- Model/API: none; direct solver replay only.
- Cases: `X-n401-k29`, `X-n573-k30`, `X-n641-k35`, `X-n1001-k43`.
- Seeds: `61`, `89`.
- Budget multipliers: `1`, `4` over nominal large-X budgets.
- Parallelism: `2` solver subprocesses.
- Timeout padding: `900s`.
- Selected surface: `solver_design`.
- Comparison baseline:
  `/home/clawd/research/scion-experiments/v04-cvrp-largeX-runtime-curve-20260615T150454Z/summary.csv`.

This first pass is `32` solver jobs total. It deliberately avoids a new LLM
campaign; it should decide whether the next CVRP work is a targeted mechanism
debug/fix or a further campaign.

## Artifacts

- Server root:
  `/home/clawd/research/scion-experiments/v04-cvrp-candidate-largeX-replay-20260615T164410Z`
- Runner script:
  `/home/clawd/research/scion-experiments/v04-cvrp-candidate-largeX-replay-20260615T164410Z/run_candidate_replay.sh`
- tmux session:
  `scion_cvrp_candidate_replay_164410`
- Status:
  `/home/clawd/research/scion-experiments/v04-cvrp-candidate-largeX-replay-20260615T164410Z/status.txt`
- Log:
  `/home/clawd/research/scion-experiments/v04-cvrp-candidate-largeX-replay-20260615T164410Z/supervisor_tmux.log`
- Planned comparison output:
  `/home/clawd/research/scion-experiments/v04-cvrp-candidate-largeX-replay-20260615T164410Z/candidate_vs_champion_largeX.csv`

The first `nohup` launch did not persist under the Codex exec process wrapper.
A foreground smoke for `rep01` on `X-n401/seed61/90s` completed successfully:
total distance `68673`, BKS gap `3.8078%`, `best_update_count=0`, matching the
champion large-X result. The full replay was restarted in `tmux` at
`2026-06-15T16:49:33Z`.

## Pending Analysis

After completion, compare candidate and champion rows by:

- `case`, `seed`, `multiplier`
- `candidate_status` versus `baseline_status`
- `delta_distance_candidate_minus_baseline`
- `candidate_bks_gap_pct` versus `baseline_bks_gap_pct`
- `candidate_best_update_count`
- `candidate_best_delta`
- `candidate_iterations`
- `candidate_runtime_budget_hit`
- `candidate_stop_reason`

If candidate total distance is unchanged and `best_update_count=0`, the Phase C
validation positives likely do not transfer to large-X search leverage. If a
candidate improves distance or produces meaningful update density, follow with
a candidate-specific replay/report before any new long CVRP LLM campaign.
