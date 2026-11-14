# CVRP Successor31 Design Review - 2026-07-01

## Context

Successor30 completed valid/complete/postrun-ready, but the required
`bounded_cross_route_double_bridge_polish` mechanism was active zero-effect:
both formal screening rows had median delta `0.0`, CI `[0.0, 0.0]`, win rate
`0.0`, `rows_at_or_above_mde=0`, and direct effect-zero diagnostics showed
`candidate_present=64`, `candidate_positive=0`, `candidate_zero=64`.

The static quality block in successor30 was useful framework evidence: it
rejected a claimed cross-route double-bridge design whose patch looked
single-route. It is not solver evidence.

`continue_explore` in successor30 is lifecycle bookkeeping, not a v0.4
solver-positive signal. Unchanged `bounded_cross_route_double_bridge_polish`
should be treated as reviewed/default-avoid.

## Reviewed Lines

Do not spend successor31 on a renamed variant of these paths:

- route-segment exchange / local-search segment polish;
- scheduler q-size trajectory tweaks;
- insertion-cost lookahead repair;
- raw construction seed selection;
- short-horizon construction seed trajectory selection;
- route-pair-overlap removal and protected follow-up;
- adjacent boundary/spoke or endpoint destroy/repair clean forks;
- cross-route double-bridge or other small local-search fragment reshuffles.

## Candidate Directions

### A. More local search

Rejected for successor31 by default. Successor19/20 and successor30 already
showed active local-search mechanisms without promotion-grade effect. A new
local-search proposal would need a clearly different causal path, not another
two-route fragment reshuffle.

### B. Another destroy/repair fork

Rejected by default. Successor24, successor27, successor28, and successor29
covered enough destroy/repair variants that another branch-local operator is
unlikely to answer a new v0.4 question unless it changes the search regime
rather than the removed-customer pattern.

### C. Construction/restart portfolio

Possible but lower priority. Successor25 and successor26b showed that
construction seed improvements can disappear after full ALNS/VNS. A restart
portfolio would need same-run post-search restart telemetry, not only seed
telemetry, and may be too broad for the next short slot.

### D. Embedded VNS runtime allocation

Recommended successor31 direction.

The current scheduler runs embedded VNS after repaired candidates under broad
conditions, and default config keeps fixed every-iteration embedded VNS
enabled. That can over-spend the budget polishing each repaired candidate and
reduce ALNS exploration diversity. This is a different CVRP-owned causal path:
change the time allocation between ALNS exploration and VNS exploitation,
instead of adding another move operator.

Recommended mechanism id:
`adaptive_embedded_vns_runtime_allocation`

Recommended owner package:
`policies/baseline_modules/`

Recommended implementation boundary:

- keep generic core unchanged;
- prefer a small coherent policy module if multi-file edits are allowed, for
  example `baseline_modules/runtime_allocation.py`, with scheduler integration
  in `scheduler.py`;
- if the experiment launcher must force a single owner file, keep the
  scheduler change narrow and avoid adding unrelated helper functions;
- use existing config concepts for embedded VNS cadence/share caps rather than
  introducing a separate tuning framework.

Required telemetry:

- record direct phase/move evidence under
  `adaptive_embedded_vns_runtime_allocation`;
- record baseline-style versus adapted embedded VNS runtime share;
- record ALNS iteration count before/after allocation pressure;
- record repaired-candidate improvements accepted without immediate VNS;
- record best objective delta attributable after allocation changes.

Acceptance reading:

- A zero direct-effect row should park the mechanism quickly.
- Positive ALNS iteration/runtime-share telemetry is not enough; v0.4 needs
  objective effect against A/A MDE.
- CMT2/CMT4 losses remain explicit case-level blockers.

## Launch Recommendation

Do not launch successor31 as another same-mechanism local-search or
destroy/repair follow-up.

If launching the next short server-local run, force `solver_design` / `modify`
on the CVRP baseline package with required mechanism
`adaptive_embedded_vns_runtime_allocation`. Prefer allowing
`scheduler.py` plus a small problem-owned allocation module over growing a long
helper block inside `scheduler.py`.
