# CVRP successor39 bounded dual repair selector design

Date: 2026-07-06

Status: preregistered target-intent design; ready for a two-round server-local
screening launch.

## Decision

Use successor39 for a clean fork named `bounded_dual_repair_selector` in
`policies/baseline_modules/scheduler.py`.

The mechanism is an ALNS repair-choice intervention, not a local-search,
construction-seed, acceptance, or runtime-allocation follow-up. After a destroy
operator removes customers, run the normal selected repair and one bounded
alternate repair on copied post-destroy candidates, compare the repair result
before embedded VNS or size70 polish, and keep the feasible lower-distance
repair candidate. The selector must leave simulated-annealing acceptance,
adaptive weight scoring, construction, local-search operators, destroy
operators, and VNS runtime allocation unchanged.

## Why This Path

Successor37 and successor38 showed the remaining blocker is candidate quality,
not only prompt continuity. Local-search variants either went negative or
activated without accepted moves, while construction-seed changes produced seed
or pre-ALNS signals that downstream ALNS/VNS did not preserve. Successor32's
post-repair operator-credit path changed weighting but did not change the
candidate chosen in the current iteration. Successor39 instead changes the
actual repaired candidate before VNS runs, while giving direct pre-VNS
objective-effect evidence.

This is materially distinct from reviewed mechanisms:

- not `post_repair_effect_credit_weighting`: no adaptive score or acceptance
  update changes;
- not `lookahead_insertion_cost_repair` or v2: no customer-level insertion
  heuristic change;
- not route-pair or edge-frequency removal: destroy choice stays unchanged;
- not seed selection or local-search relink/filtering: construction and VNS
  operators stay unchanged;
- not adaptive embedded-VNS runtime allocation: VNS cadence and budget policy
  stay unchanged.

## Required Implementation Shape

Keep the implementation narrow and auditable:

- Own the selector at the scheduler repair-choice boundary.
- Avoid adding a broad utility/helper layer; if a new module is needed, it
  should be a small repair-selector module with one public selector entry.
- Compare only one alternate repair per ALNS iteration.
- Skip the alternate when remaining budget is below the existing reserve guard.
- Preserve feasibility and `max_routes`; if the alternate is infeasible, over
  route limit, or not better before VNS, keep the baseline repaired candidate.
- Record direct telemetry under `bounded_dual_repair_selector` before VNS:
  attempted selector count, accepted alternate count, default repair operator,
  alternate repair operator, default repair distance, alternate repair
  distance, selected repair operator, pre-VNS delta, route count, feasibility,
  and whether CMT2/CMT4 are present in formal coverage.

## Acceptance Criteria

The experiment may be considered valid only if:

- live target-intent and hypothesis use mechanism id
  `bounded_dual_repair_selector`;
- target file is `policies/baseline_modules/scheduler.py` or a small
  scheduler-owned repair-selector module wired from it;
- formal `required_mechanism_ids` remains empty; this is proposal-only target
  binding, not a DecisionFeatures or protocol gate;
- two screening rows complete without quality, model-call, telemetry,
  verification, or postrun failures;
- direct pre-VNS selector telemetry is present and distinguishes baseline
  repaired candidate from selected candidate;
- CMT2/CMT4 effects are reported or an explicit split-selection caveat is
  recorded.

Do not launch a long-run or same-mechanism follow-up unless successor39 shows
positive row-level movement with direct accepted selector effect and no
protected-case collapse.
