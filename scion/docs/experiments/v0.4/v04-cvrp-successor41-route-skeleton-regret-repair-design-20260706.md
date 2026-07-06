# CVRP successor41 route skeleton regret repair design

Date: 2026-07-06

Status: preregistered target-intent design; ready for a two-round server-local
screening launch.

## Decision

Use successor41 for a clean fork named `route_skeleton_regret_repair` at the
ALNS repair boundary.

The mechanism changes repair construction, not destroy selection, local-search
moves, construction seeds, acceptance, adaptive weights, or embedded-VNS
runtime allocation. After a destroy operator removes customers, build the
normal repaired candidate and one bounded route-skeleton-biased regret repair
candidate from the same post-destroy state. Select the skeleton-biased
candidate only when it is feasible, respects `max_routes`, and is strictly
lower distance before embedded VNS or size70 polish.

The skeleton bias is a tie-break in regret insertion: when insertion deltas are
close, prefer placements that preserve same-run route adjacency from the
pre-destroy incumbent. The direct effect must be measured after repair and
before downstream VNS/polish.

## Why This Path

Successor39 changed repair choice by comparing an alternate repair operator,
but stayed below MDE. Successor40 changed local search with a two-route
set-exchange, activated, and stayed below MDE while the guarded follow-up
mostly became no-op. Both should be parked.

Successor41 stays in the problem-owned destroy/repair layer while targeting a
different causal path:

- not `bounded_dual_repair_selector`: it changes the repair rule itself rather
  than selecting between existing repair operators;
- not `lookahead_insertion_cost_repair` or v2: it is route-skeleton adjacency
  preservation under regret insertion, not insertion-cost lookahead scoring;
- not route-pair-overlap, capacity-tightness, angular/radial/string, or
  farthest-noise removal: destroy choice stays unchanged;
- not construction seed selection, post-construction micro-polish, or
  short-horizon seed trajectory selection;
- not local-search, two-for-one exchange, double-bridge, ejection-chain,
  radial relink, or neighbor-list filtering;
- not acceptance/adaptive weighting, destroy-size q scheduling, or VNS runtime
  allocation.

## Required Implementation Shape

Keep the implementation narrow and auditable:

- Own the comparison at the scheduler repair boundary.
- Add at most one repair operator/function in the CVRP baseline policy package;
  do not add generic core helpers.
- Use a bounded copy of the post-destroy candidate for the skeleton-biased
  repair.
- Preserve the baseline repaired candidate unless the skeleton-biased candidate
  is feasible, route-count compliant, and strictly lower distance before VNS.
- Record direct telemetry under `route_skeleton_regret_repair` after repair and
  before embedded VNS/polish: attempted count, accepted count, default repair
  distance, skeleton repair distance, selected repair label, pre-VNS delta,
  feasibility, route count, and bounded effort.
- Keep simulated-annealing acceptance, adaptive weight scoring, construction,
  destroy operator choice, local-search operators, and embedded-VNS runtime
  allocation unchanged.

## Acceptance Criteria

The experiment may be considered valid only if:

- live target-intent and hypothesis use mechanism id
  `route_skeleton_regret_repair`;
- target files are `policies/baseline_modules/scheduler.py` and, only if
  needed, `policies/baseline_modules/destroy_repair.py`;
- formal `required_mechanism_ids` remains empty; this is proposal-only target
  binding, not a DecisionFeatures or protocol gate;
- two screening rows complete without quality, model-call, telemetry,
  verification, or postrun failures;
- direct pre-VNS repair telemetry is present under the declared mechanism id;
- CMT2/CMT4 effects are reported or an explicit split-selection caveat is
  recorded.

Do not launch a long-run or same-mechanism follow-up unless successor41 shows
positive row-level movement with direct pre-VNS repair effect and no
protected-case collapse.
