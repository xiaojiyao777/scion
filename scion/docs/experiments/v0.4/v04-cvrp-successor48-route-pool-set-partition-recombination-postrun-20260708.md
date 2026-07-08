# CVRP successor48 postrun: route-pool set-partition recombination

Date: 2026-07-08

## Run

- Label: `v04-cvrp-successor48-route-pool-set-partition-recombination-server-claw-2r-gpt55`
- Root: `/home/clawd/research/scion-experiments/v04-cvrp-successor48-route-pool-set-partition-recombination-server-claw-2r-gpt55-2r-gpt55-20260708T060446Z-claw`
- Runner: server-local `claw`
- Model: local `gpt-5.5`
- Resume source: successor47
- Requested/effective rounds: `2` / `2`
- Wrapper status: finished, complete, valid, postrun-ready

## Result

No promotion-grade solver evidence.

- Champion promotions: `0`
- Aggregate screening case W/L/T: `0/1/23`
- Aggregate screening pair W/L/T: `10/10/76`
- Protocol rows: `2`
- Row medians: `0.0`, `0.0`
- CI highs: `0.0`, `0.0`
- Rows at or above 9.9 MDE: `0`
- Effective priority cases included CMT2 and CMT4.

## Trace Audit

The run did not fail because of model access, target drift, generic protocol
state, or a v3 boundary breach.

- All 11 local `gpt-5.5` calls returned `ok`.
- Target-intent and hypothesis stayed on
  `bounded_route_pool_set_partition_recombination`.
- Code changes stayed problem-owned in `policies/baseline_modules/` with
  scheduler wiring only.
- Prompt manifests kept prepared obligations, solver rules, source context,
  and active algorithm facts visible. The only hypothesis truncation was the
  preflight echo; it did not break target binding.

## Mechanism Diagnosis

Both candidates implemented a bounded exact-cover route-pool idea, but the
actual mechanism was too conservative and under-attributed.

- Candidate 1 called the route-pool phase every fourth ALNS iteration.
- Candidate 2 called it more often but used a smaller current/best/candidate
  source pool.
- The mechanism had runtime/activation telemetry on almost all candidate runs.
- Positive route-pool best-delta appeared in only a small minority of runs:
  `8/48` for one row and `7/46` for the other.
- Most runs attempted route-pool recombination without direct route-pool
  improvement, leaving final evidence tie-dominated.
- The generated code did not record enough source-count, exact-cover count,
  reject-cause, budget-stop, or final scheduler-acceptance attribution to
  explain no-effect robustly.

## Decision

Park unchanged successor48 route-pool exact-cover recombination for v0.4.
Do not long-run, threshold-tune, or create a same-mechanism follow-up.

The next CVRP step should run the prepared route-first comparison object. That
experiment tests whether the current ALNS+VNS solver family itself has limited
easy headroom, without continuing the route-pool line or moving CVRP semantics
into generic Scion core.
