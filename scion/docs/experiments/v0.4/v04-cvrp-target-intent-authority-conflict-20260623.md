# CVRP Target-Intent Authority Conflict

*Date: 2026-06-23*
*Scope: v0.4 generic proposal-control repair evidence, not solver evidence*

## Run

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-continuity-77f4abe7-postweakpressure-4r-gpt55-20260623T051921Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-continuity-77f4abe7-postweakpressure-4r-gpt55-20260623T051921Z-claw`
- WSL runtime commit: `77f4abe7`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-schedstatus-d0dded44-clean-missingprimary-4r-gpt55-20260623T025241Z-claw/campaign`
- Launch shape: 4 requested rounds, `gpt-5.5`, no forced surface/action/target.

## Outcome

The run is not accepted as solver evidence.

- `wrapper_exit_status=64`
- `postrun_acceptance_status=failed`
- `run_validity_status=invalid_no_effective_rounds`
- `run_completeness_status=interrupted_incomplete`
- `last_stop_reason=circuit_breaker`
- `effective_rounds_completed=0`
- `proposal_attempts_total=4`
- `proposal_attempts_consumed=3`
- `proposal_quality_blocks=3`
- `scheduler_active_slot_blocked_attempts=0`

## Positive Framework Signal

The previous weak-positive scheduler repair worked in a live resumed WSL run.
The first current scheduler result selected existing branch
`bba3d45f-a7d7-4485-905b-cb3777976c1e` with:

- `scheduler_slot=exploit_weak_positive`
- `scheduler_reason=weak_positive_signal_followup`

The branch card was generic and problem-neutral:

- `branch_scheduling_lane=weak_positive_followup`
- `branch_followup_policy=branch_local_followup_or_explicit_bridge`
- `protected_mechanism_ids=["route_pressure_acceptance"]`
- `evidence_tier=weak_positive`

This confirms the active-slot repair and weak-positive scheduler pressure repair
are no longer the immediate blocker for this path.

## Failure Mode

The run exposed a generic target-intent authority conflict.

Prepared launch focus required `large_instance_intra_route_two_opt_seed`.
The selected existing branch required branch-local continuation of protected
mechanism `route_pressure_acceptance`. Target-intent preflight froze the
prepared mechanism into `selected_target_intent`, while the same-mechanism
schema guard correctly forced formal hypotheses back to the branch-local
protected mechanism.

Observed failure loop:

1. Session `739f50c1-6aba-4803-a596-a7f6c7795664` selected target intent
   `large_instance_intra_route_two_opt_seed`.
2. First schema retry feedback was `same_mechanism_only_violation`.
3. The retry rewrote the formal hypothesis to `route_pressure_acceptance`.
4. Binding then failed:
   `target_intent_binding_mismatch`, selected
   `large_instance_intra_route_two_opt_seed`, formal
   `route_pressure_acceptance`.
5. Session `e35d016b-2b7d-4062-9aee-2bdab809065c` repeated the same loop.
6. Session `7520f3ff-5073-4c50-8b55-018d53b6556c` stayed with the prepared
   new mechanism and was blocked by the same-mechanism guard.

This is not a CVRP heuristic result. It is a proposal-control conflict between
prepared focus authority and existing-branch follow-up authority.

## Design Decision

Add a generic target-intent authority resolution layer before target-intent
preflight is consumed by final hypothesis generation.

The resolver must compare only problem-neutral fields:

- prepared `required_mechanism_ids`
- branch protected or allowed mechanism ids
- branch follow-up mode or same-mechanism hygiene
- selected target-intent action and mechanism id

Rules:

- Open exploration or create-new contexts may keep the prepared required
  mechanism binding.
- Existing branch follow-up with intersecting prepared/protected ids may bind
  the intersection.
- Existing branch follow-up with disjoint prepared/protected ids must defer the
  prepared focus or reroute to a clean-fork signal. It must not freeze a
  prepared new mechanism as the selected target intent for a same-mechanism
  branch.
- The resolver must write proposal-layer diagnostics showing which authority
  won, whether prepared focus was applied or deferred, and which ids were
  considered.

`DecisionFeatures`, scheduler promotion logic, Protocol results, and
problem-owned CVRP semantics remain unchanged.

## Acceptance

- Focused unit tests cover open exploration, disjoint existing-branch follow-up,
  intersecting follow-up, and no-required-focus cases.
- Existing launch-focus target-intent behavior remains valid for non-conflicting
  contexts.
- A WSL focused readiness check passes from a clean conda `scion` checkout
  before any relaunch.
- A follow-up CVRP continuity run may then resume from the same clean root to
  verify that `exploit_weak_positive` can reach formal hypothesis/code or a
  typed host-owned reroute, rather than cycling between binding and
  same-mechanism guard failures.
