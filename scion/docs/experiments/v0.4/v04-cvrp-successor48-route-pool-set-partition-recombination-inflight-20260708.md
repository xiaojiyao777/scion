# CVRP successor48 inflight: bounded route-pool set-partition recombination

Date: 2026-07-08

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor48-route-pool-set-partition-recombination-server-claw-2r-gpt55-2r-gpt55-20260708T060446Z-claw`

## Launch

- Launcher commit: `eba0c565`.
- Runner: server-local conda `claw`.
- Model: local `gpt-5.5`.
- Rounds: 2.
- Time limit: 30 seconds.
- Proposal context: full.
- Measurement governance: on.
- Resume source:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor47-bounded-giant-tour-split-recombination-server-claw-2r-gpt55-2r-gpt55-20260708T021541Z-claw`.
- Initial PID: `1742335`.
- Started UTC: `2026-07-08T06:04:48Z`.

## Startup Checks

- `run_status.json`: `status=running`, `prepared_only=false`.
- Completion preflight: `ok: true`.
- Auth pool: one active account; no banned, expired, quota-exhausted, or
  rate-limited entries at launch.
- Chat preflight: HTTP 200, `classification=healthy`, `code=ok`.
- Prepared target intent:
  `target_intent_required_mechanism_ids=["bounded_route_pool_set_partition_recombination"]`.
- Formal required mechanism ids: empty.
- Contract required mechanism:
  `bounded_route_pool_set_partition_recombination` with
  `hypothesis_mechanism_binding=target_intent_required`.
- Successor47 is present as
  `reviewed_marginal_below_mde_protected_case_unsafe`.

## Expected Evidence

The run should reject unchanged successor47-style contiguous giant-tour split
variants and bind to successor48:
`bounded_route_pool_set_partition_recombination` in
`policies/baseline_modules/route_pool_recombination.py`, with only minimal
`policies/baseline_modules/scheduler.py` orchestration.

Postrun analysis must check:

- route-pool size and source counts;
- exact-cover candidate count;
- attempted, accepted, rejected-no-cover, rejected-infeasible,
  rejected-route-count, rejected-no-improvement, and budget-stopped counts;
- accepted set-partition final `total_distance` delta;
- feasibility and route-count preservation;
- CMT2/CMT4 priority-case outcomes;
- whether any generated code crossed v3 boundaries into generic core,
  protocol selection, measurement gates, or DecisionFeatures.

## Next Check

After completion, inspect `run_status.json`, `campaign/status.json`,
`campaign/campaign_summary.json`, postrun acceptance summaries, formal metrics,
and all current-run LLM traces before deciding whether the result is real
solver signal or short-run noise.
