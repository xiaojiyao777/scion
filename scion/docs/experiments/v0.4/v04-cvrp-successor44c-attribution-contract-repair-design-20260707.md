# Successor44c Attribution Contract Repair Design

Date: 2026-07-07

## Purpose

Successor44 showed weak-positive diagnostic evidence for a post-VNS acceptance
guard, but the follow-up path was distorted by the evidence contract. The CVRP
hypothesis gate required `expected_telemetry.effect`, which pushed candidates
to route ordinary ALNS/VNS current-improving or new-best bookkeeping through
`post_vns_best_anchor_acceptance_guard` and credit that as mechanism effect.

This repair changes the research contract before another run. It is not a
solver-mechanism change.

## Boundary

- Keep generic telemetry guard, DecisionFeatures, protocol, and decision logic
  unchanged.
- Keep successor44 semantics in CVRP-owned problem layers.
- Keep `target_intent_required_mechanism_ids` bound to
  `post_vns_best_anchor_acceptance_guard` for the short verification run.

## Contract Change

For `post_vns_best_anchor_acceptance_guard`, acceptable proposal telemetry is:

- activation/activity/budget under the mechanism id;
- guard allow/reject trajectory evidence;
- formal per-case `total_distance`, feasibility, route-count, CMT2, and CMT4
  outcomes as objective evidence.

The contract must not require broad-loop
`solver_algorithm_phase_best_delta.<mechanism>` or
`solver_algorithm_phase_improvement_counts.<mechanism>` fields for this policy
mechanism.

## Static Quality Change

Reject successor44 candidate code that records `record_move(..., delta=...,
best_improved=...)` from ordinary `candidate_improves_best`,
`candidate_improves_current`, `best_cost - candidate_cost`, or
`current_cost - candidate_cost` bookkeeping. Those improvements belong to the
ordinary downstream ALNS/VNS trajectory, not to the acceptance guard.

Activation counters and guard decision counters remain allowed.

## Acceptance Criteria

- Existing non-successor44 solver-design mechanisms still require direct effect
  telemetry at the CVRP hypothesis gate.
- Successor44 hypotheses can pass with activation/activity/budget telemetry and
  formal outcome evidence.
- Static smoke rejects successor44 ordinary-improver effect credit in
  `acceptance.py`.
- v3 boundary tests remain green.
- A short server-local run reaches normal proposal/code/telemetry execution
  without repeating the fake-effect attribution pattern.
