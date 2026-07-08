# CVRP comparison postrun: route-first heuristic

Date: 2026-07-08

## Run

- Label: `v04-cvrp-route-first-comparison-server-claw-2r-gpt55`
- Root: `/home/clawd/research/scion-experiments/v04-cvrp-route-first-comparison-server-claw-2r-gpt55-2r-gpt55-20260708T082843Z-claw`
- Runner: server-local `claw`
- Model: local `gpt-5.5`
- Requested/effective rounds: `2` / `2`
- Wrapper status: finished, complete, valid, postrun-ready

## Result

No promotion-grade solver evidence.

- Champion promotions: `0`
- Protocol rows: `2`, both screening
- Decisions: `abandon`, `abandon`
- Aggregate screening case W/L/T: `0/16/0`
- Aggregate screening pair W/L/T: `0/64/0`
- Row medians: `-24.5`, `-24.5`
- Row CI: `[-116.5, -15.0]`, `[-116.5, -15.0]`
- Rows at or above 9.9 MDE: `0`
- Effect/MDE ratio: `-2.474747`

The result is not short-run positive noise hidden by conservative gates. Every
measured case and every measured pair lost on `total_distance`.

## Candidate Shape

Both formal candidates were the same activation patch:

```diff
-SOLVER_VARIANT = "alns_vns"
+SOLVER_VARIANT = "route_first_heuristic"
```

The generated patches did not alter the route-first modules or add another
solver mechanism. This was consistent with the comparison design, but it also
means the run tested the already implemented route-first family as-is.

## Algorithm Diagnosis

The route-first solver actually ran. Metrics recorded
`route_first_heuristic` candidate telemetry with 32 candidate/runtime pairs in
each row. The comparison therefore did not fail because the variant was
inactive, infeasible, or uninstrumented.

The algorithmic result was clear:

- Fleet-violation deltas were `0.0` in the case summaries.
- CMT2 lost all measured seeds, median `-116.5`.
- CMT4 lost all measured seeds, median `-64.0`.
- X-n110 lost all measured seeds, median `-259.0`.
- The smaller/easier cases also lost: A `-16.5`, B `-27.0`, E `-15.0`,
  M `-2.0`, P `-22.0`.

This route-first family is faster and bounded, but its deterministic
construction plus first-improvement cleanup is not competitive with the current
ALNS+VNS champion on the formal CVRP surface. Treat it as a failed comparison
object, not as a long-run candidate.

## Trace Audit

A delegated read-only audit inspected all current-run LLM calls and prompt
manifests.

- LLM calls were normal: 15 local `gpt-5.5` calls, with request kinds
  `hypothesis_target_intent=5`, `hypothesis=6`, `tool_selection=2`,
  `code=2`.
- Proposal attempts consumed: `5`.
- Proposal quality blocks: `3`, all from the CVRP solver-design causal-path
  contract.
- Block reasons were missing `material_difference`, missing
  `clean_fork_diversity_claim`, and missing `expected_telemetry.effect`.
- Every prompt manifest reported
  `material_difference_requirement_visible=false`.
- Every hypothesis prompt had the `hypothesis_target_intent_preflight` section
  truncated.
- The formal mechanism id was `route_first_heuristic_baseline`, while runtime
  telemetry used `route_first_heuristic`.

The model was not unavailable, and the code-generation phase had enough source
visibility to apply the requested config change. The quality issue was that
the proposal surface still made schema completion easier than strong algorithm
intervention, and the route-first mechanism identity was split between a
formal id and the runtime phase id.

## Interpretation

This experiment answers the comparison question narrowly:

- It does not show an easy replacement-family headroom over ALNS+VNS.
- It does show that the simple route-first baseline is dominated by the current
  ALNS+VNS champion on the measured CVRP cases.
- It does not prove Scion has solved candidate quality. The duplicate
  activation-only candidates, invisible material-difference requirement, and
  mechanism-id mismatch are proposal/contract issues that must be repaired
  before another solver-design line.

## Decision

Park unchanged `route_first_heuristic` comparison for v0.4. Do not long-run,
threshold-tune, or relaunch the same config-flip comparison.

Before the next CVRP solver-design experiment, do the deferred CVRP-owned
contract/context repair:

- align the route-first formal mechanism identity with runtime
  `route_first_heuristic`;
- expose material-difference and target-intent requirements as explicit,
  non-truncated prompt contract sections;
- add an algorithmic-intervention sufficiency check for CVRP solver-design
  hypotheses: where the candidate changes the solve trajectory, what new
  solution states it can generate, how attempts/accepts/rejects are observed,
  and what direct objective attribution it must expose;
- keep those semantics in CVRP-owned guidance/contracts and preserve v3
  generic-core boundaries.
