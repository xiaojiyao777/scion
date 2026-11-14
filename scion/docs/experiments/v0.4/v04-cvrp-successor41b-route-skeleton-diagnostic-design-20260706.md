# CVRP successor41b route skeleton diagnostic design

Date: 2026-07-06

## Purpose

Successor41 produced one negative and one marginal candidate for
`route_skeleton_regret_repair`. The marginal candidate had useful A/B signal
but systematic P and CMT4 losses. Successor41b is the only acceptable
same-mechanism follow-up. It is a diagnostic repair, not a long-run
promotion attempt.

## Design Boundary

Keep the mechanism id:

- `route_skeleton_regret_repair`

Keep the owner problem-local:

- primary integration: `policies/baseline_modules/scheduler.py`
- implementation module: `policies/baseline_modules/route_skeleton_repair.py`

The scheduler should only collect the same post-destroy/default-repair
inputs, call the module, and consume a typed result. Skeleton scoring,
candidate construction, no-op decisions, and structured diagnostic fields
belong in the new module. Do not add another cluster of private helper methods
to `scheduler.py`.

## Required Mechanism Change

Successor41 selected skeleton repair when it beat the default repair before
VNS. That was insufficient: pre-VNS wins could still damage downstream
trajectory.

Successor41b must therefore add a stability gate:

- compare default and skeleton candidates from the same post-destroy state;
- require feasible and route-count-compliant skeleton candidate;
- require a distance margin over the default candidate, not just epsilon;
- require skeleton continuity to be non-worse than the default candidate using
  a local route-adjacency continuity score computed from the pre-destroy
  incumbent;
- no-op to default when the skeleton candidate is marginal, unstable,
  infeasible, over route count, or near the time reserve;
- do not hardcode case ids, BKS values, seeds, or split membership.

The follow-up must preserve destroy operator choice, construction seeds,
local-search operators, simulated-annealing acceptance, embedded-VNS runtime
allocation, and generic core behavior.

## Telemetry Contract

Record one structured diagnostic event per attempted comparison, in addition
to existing phase/move counters:

- `attempted`
- `accepted`
- `default_distance`
- `skeleton_distance`
- `distance_margin`
- `default_continuity_score`
- `skeleton_continuity_score`
- `selected_label`
- `feasible`
- `route_count`
- `max_routes`
- `removed_count`
- `bounded_position_count`
- `budget_stop`
- `noop_reason`

`record_move("route_skeleton_regret_repair", ...)` must use truthful
semantics:

- `attempted=1` only when the alternate candidate was actually evaluated;
- `accepted=1` only when skeleton replaced the default candidate;
- `delta` is the accepted pre-VNS distance improvement over default;
- `best_improved` must not mean merely "skeleton accepted"; it should be true
  only if the selected candidate improves the current branch-local best, or be
  omitted/false if that cannot be computed truthfully.

If the skeleton candidate replaces the default repair, do not attribute that
selection as ordinary credit to the originally selected repair operator
without a separate diagnostic flag. The follow-up must not hide skeleton
selection behind the default repair operator name.

## Acceptance Criteria

Run only a small server-local experiment first.

Proceed no further unless the follow-up is valid, postrun-ready, and shows all
of the following:

- no proposal, model, telemetry, or postrun infrastructure failure;
- direct structured telemetry for all fields above;
- P-n65-k10 is not a 0W/4L case loss;
- CMT4 is not a 1W/3L or worse case loss;
- aggregate result improves over successor41 candidate 2's 13W/14L/5T and
  median `0.0`;
- no single case protection rule depends on case ids or BKS constants in
  solver code.

If these criteria fail, park `route_skeleton_regret_repair` for v0.4 and
clean-fork to a different problem-owned causal path.
