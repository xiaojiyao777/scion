# Successor44d Policy-Effect Warning Hygiene Design

Date: 2026-07-07

## Purpose

Successor44c repaired the CVRP attribution contract for
`post_vns_best_anchor_acceptance_guard`: activation/activity/budget telemetry
plus formal per-case outcomes are valid evidence for this acceptance-policy
mechanism, and direct `record_move(delta=...)` effect telemetry must not be
fabricated from ordinary ALNS/VNS current/best improvements.

The remaining issue is summary hygiene. Generic telemetry guard diagnostics
still convert activated policy evidence with no direct effect field into
`effect_attribution_missing` and generic repair guidance to add
`context.record_move(...)`. Branch cards then mark same-mechanism follow-up as
required. That is correct for many direct-effect mechanisms, but wrong for this
CVRP policy mechanism.

## Boundary

- Keep v3 DecisionFeatures, promotion gates, protocol gates, and scheduler
  decisions problem-neutral.
- Do not put CVRP or successor44 names in generic telemetry guard, branch cards,
  scheduler, or decision code.
- Add a small generic problem-provider port for mechanism-evidence
  interpretation. Default behavior remains exactly the current generic
  behavior.
- Put successor44-specific policy interpretation in a CVRP-owned module.

## Contract

Introduce a problem-neutral diagnostic/status:
`policy_outcome_observed`.

Meaning:

- the declared mechanism activated or evaluated;
- direct move-effect telemetry is not required for this mechanism in this
  stage;
- problem-owned evidence policy accepts formal outcome evidence and
  mechanism-local activation/activity/budget as the right causal contract;
- no branch-local telemetry repair follow-up is required solely to add
  `record_move(delta=...)`.

Generic code may consume this status, but only a problem-owned provider may
decide when to set it.

## Implementation Shape

1. Add an optional `MechanismEvidencePolicyProvider` resolver in
   `scion.problem.providers`.
2. Add a telemetry-guard policy application point after the generic summary is
   built. It passes the summary and compact context to the provider, if present.
3. Add `scion.problems.cvrp.mechanism_evidence_policy` with one policy class.
   It only rewrites diagnostics for
   `post_vns_best_anchor_acceptance_guard` when:
   - `effect_observation_required` is false;
   - activation is observed;
   - effect status is missing/zero/not-declared;
   - the generic diagnostic was activated/no-positive-effect or missing effect.
4. The CVRP policy rewrites mechanism diagnostics to
   `policy_outcome_observed`, sets `repairable=false`, removes the harmful
   `TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED` warning for that mechanism, and
   replaces repair guidance with "do not add direct effect telemetry; use
   formal outcome evidence and guard allow/reject telemetry".
5. Update `CvrpAdapter` to expose the policy provider.
6. Extend the generic mechanism-evidence contract to map
   `policy_outcome_observed` to no required follow-up.

## Acceptance Criteria

- Existing generic telemetry guard behavior remains unchanged without a policy
  provider.
- CVRP successor44 policy summaries do not contain a harmful generic
  `record_move(delta=...)` repair instruction.
- Branch hygiene for successor44 policy evidence does not mark
  same-mechanism telemetry repair follow-up as required solely because direct
  effect fields are absent.
- Non-successor44 CVRP mechanisms still use the generic missing-effect
  diagnostic and follow-up behavior.
- v3 boundary tests remain green.
- A short server-local experiment reaches normal proposal/code/protocol
  execution and its branch/card summaries no longer demand fake direct-effect
  telemetry for successor44.
