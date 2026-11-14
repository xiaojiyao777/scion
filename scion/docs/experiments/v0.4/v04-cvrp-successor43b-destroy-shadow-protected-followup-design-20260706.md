# CVRP Successor43b Destroy-Shadow Protected Follow-Up Design

Date: 2026-07-06

Status: preregistered target-intent design; ready for a two-round server-local
screening launch after source guidance is committed.

## Decision

Run exactly one protected same-line follow-up:
`bounded_destroy_operator_shadow_selector_protected_followup`.

This is not a threshold-tuning rerun of successor43. It keeps the same
CVRP-owned causal path, but repairs the mechanism contract defects exposed by
successor43:

- no RNG contamination from rejected shadow trials;
- scheduler attribution matches the actually selected destroy operator;
- default-versus-alternate diagnostics are directly auditable;
- pre-VNS local selector deltas are treated as candidate-filter evidence, not
  final trajectory proof.

## Ownership Boundary

The mechanism remains owned by
`policies/baseline_modules/destroy_operator_selector.py`.

`policies/baseline_modules/scheduler.py` may only do minimal wiring:

- call the selector after the default destroy+repair candidate exists;
- unpack the selected candidate and selected destroy operator metadata;
- use the effective selected destroy index/name for adaptive weights and ALNS
  trace attribution.

Do not modify generic Scion scheduler, Decision, protocol, lifecycle,
measurement, or promotion code. Do not add case-id, BKS, seed, or split
hardcoding.

## Required Contract Repairs

1. RNG isolation:
   Shadow trials must use an isolated RNG copy or save/restore RNG state so
   rejected and no-op shadow work cannot perturb the default trajectory.

2. Effective operator attribution:
   The selector must return the effective selected destroy index/name. When the
   alternate is selected, scheduler trace rows and adaptive destroy-weight
   credit must refer to that alternate, not the default.

3. Diagnostics:
   Record default and alternate pre-VNS distance, route count, feasibility,
   selected flag, reject reason, budget-skip status, and selected destroy
   label. If `record_objective_probe` is not usable for all fields, use compact
   mechanism metadata already accepted by the CVRP telemetry surface.

4. Guard semantics:
   Keep feasibility, `max_routes`, and no-route-count-regression guards. Do not
   claim success from internal pre-VNS delta alone; postrun must still evaluate
   final per-case total-distance deltas, especially CMT2/CMT4 and B/P cases.

## Explicit Non-Goals

Do not add:

- new removal criteria;
- repair-side selectors;
- route memory;
- route skeleton repair;
- local-search moves;
- seed selectors;
- simulated-annealing acceptance changes;
- embedded-VNS runtime allocation changes;
- generic scheduler exceptions.

The point is to test whether the successor43 local signal survives after fixing
RNG and attribution. If protected cases remain unsafe, park the whole destroy
shadow selector line for v0.4.

## Acceptance Criteria

The run is valid only if:

- live target-intent and formal hypothesis use
  `bounded_destroy_operator_shadow_selector_protected_followup`;
- hard `required_mechanism_ids` remains empty and
  `target_intent_required_mechanism_ids` binds only the target-intent preflight;
- generated code stays within the selector module plus minimal scheduler
  wiring;
- the accepted hypothesis includes exact
  `material_difference.changed_dimensions`, `contrast`, and `evidence`;
- direct diagnostics show RNG-isolated shadow trials and actual selected
  destroy attribution;
- CMT2/CMT4 effective priority coverage is present or an explicit measurement
  caveat is recorded;
- two screening rows complete without quality, model-call, telemetry,
  verification, or postrun failure.

