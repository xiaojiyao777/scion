# CVRP successor44 telemetry hygiene and post-VNS acceptance guard design

Date: 2026-07-06

## Purpose

Successor43b completed the only protected destroy-shadow follow-up, repaired
RNG isolation and selected-operator attribution, and still failed as solver
evidence. The remaining lesson is not another threshold tune: local pre-VNS
selector deltas can look positive while final ALNS/VNS/SA trajectory quality is
negative or protected-case unsafe.

This design has two scoped goals before the next experiment:

- make that telemetry lesson visible to CVRP proposal/code generation without
  moving CVRP semantics into generic core;
- preregister successor44 as a materially different CVRP-owned solver path,
  `post_vns_best_anchor_acceptance_guard`, for a short server-local screen.

## Boundaries

- Generic `DecisionFeatures`, scheduler governance, and promotion gates remain
  problem-neutral.
- CVRP facts, protected-case obligations, and selector telemetry hygiene stay in
  `scion/scion/problems/cvrp/...`.
- `SolverRuntimeContext.record_move(...)` is not changed. It remains a generic
  CVRP solver telemetry aggregator; the misuse is candidate interpretation of
  pre-VNS local deltas as final trajectory proof.
- The destroy-shadow selector line is parked. Successor44 must not be another
  `bounded_destroy_operator_shadow_selector` threshold/gating follow-up.

## Telemetry Hygiene Design

The CVRP guidance and static smoke layer should distinguish three evidence
scopes:

- `pre_vns_local_delta`: useful diagnostic evidence for selector/filter
  candidate choice before downstream repair, VNS, route-cap guard, and
  acceptance.
- `post_downstream_total_distance_delta`: evidence after the candidate has gone
  through the downstream solver path that can absorb or reverse local gains.
- `final_trajectory_objective_effect`: evidence at the accepted/current/best
  trajectory boundary, suitable for promotion-grade interpretation.

Selector/filter mechanisms may record activation, phase runtime, and diagnostic
counters at selector time. They must not use
`record_move(..., delta=..., best_improved=...)` inside a pre-VNS selector module
as final best-improvement proof. If a selector design wants objective-effect
credit, it must either record the final accepted/current/best trajectory effect
after downstream processing or label local deltas as diagnostic only.

The static smoke repair is intentionally narrow: reject generated selector
modules such as `policies/baseline_modules/destroy_operator_selector.py` when a
selector/shadow/filter mechanism records `record_move` effect telemetry inside
that pre-VNS module. Do not add broad gates for all scheduler or acceptance
research.

## Successor44 Design

Mechanism id: `post_vns_best_anchor_acceptance_guard`

Primary target: `policies/baseline_modules/acceptance.py`

Secondary wiring: `policies/baseline_modules/scheduler.py`

Mechanism family: `acceptance_or_adaptive_weighting`

Successor44 works at the post-VNS acceptance/commit boundary, not in pre-VNS
destroy or repair selection. It should preserve normal acceptance for new best
and current-improving candidates, then add a bounded guard for worse candidates
that simulated annealing would otherwise accept. The guard should compare the
fully repaired and VNS-polished candidate against current/best trajectory state
and route-count feasibility, so the causal path is final trajectory drift
control rather than local selector preference.

Material contrast:

- not successor32 post-repair operator-credit weighting;
- not old rank-gap or route-pressure acceptance gates;
- not successor39/43/43b pre-VNS repair/destroy selector logic;
- not route memory, route skeleton, construction seed selection, local-search
  move design, or embedded-VNS runtime allocation.

Required telemetry:

- activation/decision counters and phase runtime under
  `post_vns_best_anchor_acceptance_guard`;
- per-iteration trace evidence showing whether the original SA acceptance would
  have accepted, whether the guard allowed/rejected, and the candidate/current/
  best distance relationship at that post-VNS boundary;
- final per-case `total_distance`, feasibility, route-count, and CMT2/CMT4
  results from formal screening.

Forbidden telemetry interpretation:

- do not record positive `record_move` deltas for rejected worse candidates;
- do not use ordinary ALNS best-improvement bookkeeping as direct mechanism
  effect;
- do not treat pre-VNS selector/filter local deltas as final solver proof.

`record_move(..., delta=..., best_improved=...)` is acceptable only when the
guard directly caused or preserved an accepted/current/best trajectory outcome
that can be attributed to the mechanism at the final acceptance boundary.

## Acceptance Criteria

- Typed and legacy CVRP research guidance expose the selector telemetry hygiene
  lesson and successor44 target-intent binding.
- Formal `required_mechanism_ids` remains empty; successor44 uses proposal-only
  `target_intent_required_mechanism_ids`.
- Static smoke rejects selector modules that record pre-VNS selector effect
  telemetry as direct final effect.
- Existing CVRP solver-design and launcher tests pass.
- Launch a fresh two-round server-local `claw` experiment with local `gpt-5.5`,
  completion preflight, and full prepared context before considering any
  long-run.
