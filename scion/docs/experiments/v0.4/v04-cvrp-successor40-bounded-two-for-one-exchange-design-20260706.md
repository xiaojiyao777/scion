# CVRP successor40 bounded two-for-one exchange design

Date: 2026-07-06

Status: preregistered target-intent design; ready for a two-round server-local
screening launch.

## Decision

Use successor40 for a clean fork named `bounded_two_for_one_exchange` in
`policies/baseline_modules/local_search.py`.

The mechanism is a bounded two-route local-search customer-set exchange. One
route gives two individual, not necessarily contiguous, customers and the other
route gives one individual customer, or the reverse. Accept the move only when
both routes remain capacity-feasible, route count is preserved, and the
combined distance of the two routes strictly decreases.

Keep construction, destroy/repair choice, simulated-annealing acceptance,
adaptive weight scoring, and embedded-VNS runtime allocation unchanged.

## Why This Path

Successor39 activated `bounded_dual_repair_selector`, but stayed below MDE and
left CMT4/B/P-family losses. The repair-choice line should not be expanded
unchanged.

Successor40 stays in the problem-owned CVRP local-search layer but avoids the
reviewed mechanisms:

- not `bounded_2node_cross_exchange`: not a 1-for-1 customer swap;
- not `bounded_route_segment_exchange`: not a contiguous segment swap;
- not `_or_opt_1/_or_opt_2/_or_opt_3`: not one-way relocation;
- not `_two_opt_star`: not tail or suffix exchange;
- not `bounded_cross_route_double_bridge_polish`: not a cyclic bridge;
- not `bounded_ejection_chain_relocate`: no displaced-customer chain;
- not destroy/repair selection, construction seed selection, acceptance
  weighting, or runtime allocation.

## Required Implementation Shape

Keep the implementation narrow and auditable:

- Add one local-search operator and register it in the VNS operator list.
- Bound route-pair and customer-combination effort; stop cleanly on the
  existing reserve guard.
- Compare only route pairs whose capacities can make a 2-for-1 or 1-for-2
  exchange feasible.
- Record attempted and accepted counts under `bounded_two_for_one_exchange`.
- On accepted moves, record direct objective delta with `record_move(...,
  delta=..., best_improved=...)`.
- Preserve route count, feasibility, and route index consistency.
- Do not introduce a broad helper layer or move CVRP semantics into generic
  core code.

## Acceptance Criteria

The experiment may be considered valid only if:

- live target-intent and hypothesis use mechanism id
  `bounded_two_for_one_exchange`;
- target file is `policies/baseline_modules/local_search.py`;
- formal `required_mechanism_ids` remains empty; this is proposal-only target
  binding;
- two screening rows complete without quality, model-call, telemetry,
  verification, or postrun failures;
- direct accepted-move telemetry is present under the declared mechanism id;
- CMT2/CMT4 effects are reported or an explicit split-selection caveat is
  recorded.

Do not launch a long-run or same-mechanism follow-up unless successor40 shows
positive row-level movement with accepted move effect and no protected-case
collapse.
