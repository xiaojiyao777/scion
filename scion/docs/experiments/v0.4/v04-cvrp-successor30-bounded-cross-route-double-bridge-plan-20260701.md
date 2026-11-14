# CVRP Successor30 Bounded Cross-Route Double-Bridge Plan - 2026-07-01

## Purpose

Successor30 is the next CVRP solver slot after successor29 closed the
route-pair-overlap follow-up question. Successor27's
`route_pair_overlap_removal` was weak-positive but below MDE; successor28
tested adjacent destroy/repair clean forks and failed; successor29 forced the
true protected `route_pair_overlap_removal_protected_followup` mechanism and
also failed with negative aggregate medians.

The route-pair-overlap line is therefore parked for v0.4. Successor30 should
move to a materially different non-seed CVRP-owned mechanism, preferably a
bounded local-search mechanism rather than another destroy/repair clean fork
or scheduler telemetry repair.

## Target

- Surface: `solver_design`
- Action: `modify`
- Primary owner file:
  `policies/baseline_modules/local_search.py`
- Mechanism id to require for a focused launch:
  `bounded_cross_route_double_bridge_polish`
- Runner: server-local `claw` for a two-round small run
- Model: local `gpt-5.5`
- Rounds: `2`
- Time limit: `30s`

If the implementation grows beyond a narrow local patch, split the behavior
into a coherent problem-owned local-search module under
`policies/baseline_modules/` rather than adding a string of small helpers to an
oversized file.

## Mechanism Sketch

`bounded_cross_route_double_bridge_polish` should be a bounded local-search
operator that performs a route-level cyclic reconnection over internal
fragments from three or four routes:

- choose a small bounded set of route tuples;
- choose short internal fragments, initially length `1` or `2`;
- reconnect fragments cyclically across routes;
- keep all customers assigned exactly once;
- preserve route count where possible and avoid route-count pressure;
- check capacity before evaluating a candidate;
- evaluate total route-distance delta before mutation;
- accept only strict improving moves;
- stop on the existing `context.remaining_time() > reserve` budget guard.

The mechanism must not call destroy/repair removal/reinsertion, must not use
case ids, BKS values, seeds, split membership, or protected-case thresholds,
and must not add CVRP exceptions to generic core, lifecycle, scheduler policy,
protocol, launcher, or `DecisionFeatures`.

## Difference From Reviewed Paths

This mechanism is only acceptable if the hypothesis and patch keep the causal
path distinct from reviewed/default-avoid local-search mechanisms:

- not `bounded_2node_cross_exchange`: no two-customer swap mechanism;
- not `intra_route_or_opt_reinsert`: not same-route or ordinary Or-opt
  reinsertion;
- not `bounded_intra_route_3opt`: not a single-route 3-opt rewrite;
- not `bounded_ejection_chain_relocate`: not a sequential displacement chain;
- not `bounded_route_segment_exchange` or
  `cmt_slack_aware_segment_swap`: not a two-route segment swap and not a
  CMT-specific slack rule;
- not `bounded_interroute_2opt_bridge`: not a two-route suffix/tail exchange
  equivalent to `_two_opt_star`.

The approved implementation should use internal fragments and a three- or
four-route cyclic bridge. If the hypothesis says "cross-route double bridge",
the code must genuinely operate across routes; a single-route double bridge is
semantic drift and should fail static quality checks.

## Required Evidence

- Target-intent and hypothesis mechanism changes include
  `bounded_cross_route_double_bridge_polish`.
- Direct mechanism telemetry is recorded under that id, including attempted
  tuples, capacity skips, evaluated candidates, accepted moves, and objective
  delta.
- Formal screening reports total_distance, feasibility, route count, and
  budget evidence.
- Postrun analysis separates aggregate median from A/B/X, CMT2/CMT4, and
  P-family case medians.
- Effect-vs-MDE interpretation uses the current CVRP A/A MDE (`9.9`).

## Acceptance Reading

- Positive: aggregate median is positive, at least one row approaches or
  exceeds the MDE threshold, and CMT2/CMT4/P-family losses are not materially
  worse than recent route-pair and seed-selector failures.
- Inconclusive: aggregate stays weak-positive below MDE with mixed protected
  cases; do not continue without a sharper same-mechanism diagnostic.
- Reject: aggregate turns nonpositive, telemetry is missing, or formal rows
  show only VNS aggregate telemetry without the declared mechanism id. In that
  case, park the mechanism rather than micro-tuning the same family.

## Launch Gate

Before launch:

- prepare with the standard CVRP launcher;
- force `solver_design` / `modify` /
  `policies/baseline_modules/local_search.py`;
- patch only that run root's prepared manifest so both
  `research_focus.required_mechanism_ids` and typed
  `research_guidance_contract.required_mechanisms` require
  `bounded_cross_route_double_bridge_polish`;
- regenerate `prepared_run_manifest.md` and prepared handoff artifacts;
- verify `launch_research_guidance_payload(...).required_mechanism_ids` returns
  `["bounded_cross_route_double_bridge_polish"]`;
- completion preflight for local `gpt-5.5` must pass.
