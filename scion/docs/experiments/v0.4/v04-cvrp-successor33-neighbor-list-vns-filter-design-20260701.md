# CVRP Successor33 Design Review - 2026-07-01

## Context

Successor32 completed valid/complete/postrun-ready after the target-intent
binding repair. Both live target-intent calls and both formal hypotheses stayed
bound to `post_repair_effect_credit_weighting`, so the control-plane blocker is
closed.

The solver evidence was still negative for v0.4 closeout: both formal
screening rows had median delta `0.0`, CI `[0.0, 0.0]`,
`rows_at_or_above_mde=0`, and `max_effect_to_mde_ratio=0.0`. The mechanism
activated and emitted internal post-repair effect telemetry, but postrun
summarized the objective effect as `zero_objective_effect`.

Treat unchanged `post_repair_effect_credit_weighting` as reviewed/default-avoid.
The next solver slot should not relaunch the operator-credit mechanism just
because it produced direct internal telemetry.

## Reviewed Lines

Do not spend successor33 on a renamed variant of these paths:

- route-pair-overlap removal or protected route-pair-overlap follow-up;
- boundary-spoke or edge-conflict endpoint removal;
- bounded cross-route double-bridge polish;
- adaptive embedded-VNS runtime allocation;
- post-repair operator-credit weighting;
- construction seed baseline or short-horizon seed trajectory selection;
- scheduler q/destroy-size variants;
- insertion-cost lookahead repair;
- another broad two-opt fallback without a deadline/window design.

## Candidate Directions

### A. Neighbor-list VNS candidate filtering

Recommended successor33 direction.

The current VNS operators enumerate broad route/customer combinations and stop
on the first improvement. With embedded VNS active on many repaired candidates,
that can spend most of the fixed budget on low-yield scans before ALNS has
enough diverse trials. A nearest-neighbor or route-neighbor candidate filter
changes the enumeration policy inside existing VNS neighborhoods so the same
time budget is spent on plausible improving moves first.

This is a different CVRP-owned causal path from the reviewed mechanisms: it
does not add a new route-pair-overlap, double-bridge, construction seed,
destroy/repair selection, q schedule, acceptance gate, operator-credit, or
runtime-allocation policy. It changes local-search candidate ordering and
filtering while preserving improvement-only move semantics.

Recommended mechanism id:
`neighbor_list_vns_filter`

Recommended mechanism family:
`bounded_local_search_variant`

Recommended owner files:

- primary: `policies/baseline_modules/local_search.py`
- narrow integration if needed: `policies/baseline_modules/scheduler.py`
- optional constants only if needed: `policies/baseline_modules/config.py`

Implementation boundary:

- keep generic core unchanged;
- keep the stable `baseline_algorithm.py` entrypoint unchanged;
- do not implement a new move family such as double-bridge, route-pair
  crossover, route-pair overlap, ejection chain, or route-segment exchange;
- filter or reorder candidate enumeration for existing VNS neighborhoods,
  especially relocate, swap, Or-opt, or two-opt-star;
- keep all moves feasibility-preserving and improvement-only;
- bound candidate lists by a small route/customer neighbor cap and remaining
  time checks;
- keep telemetry under the exact mechanism id, not only under generic `vns`.

Required telemetry:

- `context.record_iteration("neighbor_list_vns_filter", count)`
- `context.record_phase("neighbor_list_vns_filter", elapsed_ms)`
- `context.record_move("neighbor_list_vns_filter", attempted=..., accepted=...,
  delta=..., best_improved=...)`
- route count and feasibility through existing runtime fields;
- formal per-case and pair-level `total_distance` evidence;
- CMT2/CMT4/P-family case medians or explicit caveat.

Acceptance reading:

- Runtime movement or extra ALNS iterations are not enough.
- A valid result needs objective effect against A/A MDE and protected-case
  review.
- If the mechanism only changes scan time and produces `median_delta=0.0`,
  park it as runtime-only or zero-effect evidence.

Main risk:

The filter can become a runtime-only mechanism or miss long-range improving
moves if the candidate list is too narrow. The design should therefore prefer
a bounded near-neighbor first pass rather than deleting all fallback search
unless the formal hypothesis states why fallback removal is necessary.

### B. Retained annealing acceptance clamp

Rejected for successor33 by default.

This is materially different from post-repair operator credit, but it is too
close to the family of route-pressure/rank-gap acceptance gates that current
guidance already warns against. It also has weak direct-effect attribution:
rejecting a worse move can preserve a good state, but that is harder to prove
than a directly accepted improving local-search delta.

Consider it later only if a design names a non-rank-gap causal path and defines
clear accepted/rejected-worse objective attribution.

### C. Deadline-aware large-route two-opt window

Rejected for successor33 by default.

A deadline-aware, windowed intra-route two-opt could be valid in principle, but
v0.4 already has a large two-opt seed checklist and repeated local-search
zero-effect evidence. This path should wait unless the next design explicitly
reopens the large-instance two-opt question with a stricter deadline/window
contract and wall-clock evidence.

## Launch Recommendation

Do not launch successor33 as another same-mechanism follow-up. First update the
problem-owned CVRP guidance so target intent no longer binds successor32.

If launching the next short server-local run, force `solver_design` / `modify`
with target file `policies/baseline_modules/local_search.py` and proposal-only
target-intent binding for `neighbor_list_vns_filter`.
