# CVRP Successor28 Route-Pair Overlap Protected Follow-Up Plan - 2026-07-01

## Purpose

Successor28 should test whether successor27's weak-positive
`route_pair_overlap_removal` signal can be made safer on CMT2/CMT4/P-family
loss modes without abandoning the useful A/B/X gains.

This is not an unchanged expansion. It is a protected same-mechanism follow-up.
A different non-seed clean fork is acceptable only if the live hypothesis
explicitly records why successor27's active marginal signal is being abandoned.

## Target

- Surface: `solver_design`
- Action: `modify`
- Primary owner file:
  `policies/baseline_modules/destroy_repair.py`
- Expected registration/telemetry owner:
  `policies/baseline_modules/scheduler.py`
- Mechanism id:
  `route_pair_overlap_removal_protected_followup`
- Runner: server-local `claw`
- Model: local `gpt-5.5`
- Rounds: `2`

If the operator grows beyond a narrow patch, the candidate should place the
route-pair-overlap logic behind a coherent problem-owned module boundary under
`policies/baseline_modules/` instead of adding helper sprawl to an oversized
file.

## Design Constraints

- Preserve the route-pair-overlap causal path from successor27.
- Do not hardcode CMT2, CMT4, P cases, BKS values, seeds, or split membership.
- Guard with problem-general route-pair signals such as:
  - low spare capacity or route-load imbalance;
  - route-count risk after removal/repair;
  - weak geometric overlap score;
  - excessive removal count relative to route sizes.
- Use bounded perturbation. Prefer fewer removed customers, boundary-biased
  choices, or one-side-per-route removal when risk is high.
- Keep feasibility and route-count evidence intact.
- Keep generic core, protocol, lifecycle, launcher, and `DecisionFeatures`
  unchanged.

## Required Evidence

- Live target-intent or hypothesis names
  `route_pair_overlap_removal_protected_followup`.
- It explains how the protection differs from successor27's unchanged
  `route_pair_overlap_removal`.
- It records direct mechanism telemetry under the declared id:
  `context.record_iteration`, `context.record_phase`, and
  `context.record_move(..., attempted=1, accepted=..., delta=...,
  best_improved=...)`.
- It preserves per-case `total_distance`, feasibility, route-count, and runtime
  budget evidence.
- Formal screening includes CMT2/CMT4 when available or records a case-selection
  caveat.
- The postrun analysis reports CMT2, CMT4, and P-family case medians separately
  from the aggregate median.

## Acceptance Reading

Successor28 is useful if it answers the loss-mode question, even if it remains
below MDE:

- Positive outcome: aggregate median remains positive and CMT2/CMT4/P losses
  shrink materially versus successor27, preferably without losing A/B/X gains.
- Inconclusive outcome: aggregate stays weak-positive below MDE but protected
  losses are mixed; continue only with a sharper diagnostic, not broad
  expansion.
- Reject outcome: aggregate effect turns nonpositive, direct telemetry is
  missing, or protected cases remain loss-heavy.

## Launch Gate

Before launch:

- guidance/adapter tests pass locally in `claw`;
- prepared manifest shows `route_pair_overlap_removal_protected_followup`,
  `SUCCESSOR27_WEAK_POSITIVE_BELOW_MDE`, and
  `CMT2_CMT4_P_LOSS_GUARD_REQUIRED`;
- completion preflight for local `gpt-5.5` is healthy.
