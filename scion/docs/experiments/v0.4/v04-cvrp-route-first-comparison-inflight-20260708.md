# CVRP route-first comparison inflight

Date: 2026-07-08

## Run

- Root: `/home/clawd/research/scion-experiments/v04-cvrp-route-first-comparison-server-claw-2r-gpt55-2r-gpt55-20260708T082843Z-claw`
- PID: `1759531`
- Runner: server-local `claw`
- Model: local `gpt-5.5`
- Launcher commit: `d7430150`
- Resume source: `/home/clawd/research/scion-experiments/v04-cvrp-successor48-route-pool-set-partition-recombination-server-claw-2r-gpt55-2r-gpt55-20260708T060446Z-claw`
- Rounds: `2`
- Time limit: `30s`
- Proposal context: `full`
- Measurement governance: `on`
- Completion preflight: `ok: true`

## Target

This is a comparison experiment for the prepared
`route_first_heuristic_baseline` research object. It should only enable the
existing default-off `route_first_heuristic` solver variant through
`policies/baseline_modules/config.py`.

It must not continue successor48 route-pool exact-cover recombination, recreate
giant-tour split recombination, or move CVRP solver semantics into generic
Scion core.

## Interpretation

Treat this as short screening evidence only.

- If route-first is clearly worse, current ALNS+VNS likely remains a strong
  baseline and recent failures are more about mechanism discovery/headroom.
- If route-first is competitive or positive, use it as a new CVRP-owned solver
  family research object.
- If evidence is noisy below MDE, inspect per-case structure before any
  long-run or follow-up decision.
