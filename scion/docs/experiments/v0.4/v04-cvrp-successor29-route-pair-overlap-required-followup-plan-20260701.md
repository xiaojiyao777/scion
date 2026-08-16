# CVRP Successor29 Required Route-Pair Overlap Follow-Up Plan - 2026-07-01

## Purpose

Successor29 closes the unanswered successor27 question that successor28 did
not test. Successor27's `route_pair_overlap_removal` was the strongest recent
CVRP solver signal, but it stayed below MDE and lost on CMT2/CMT4/P-family
cases. Successor28 was valid negative evidence for two alternative clean forks,
not a protected route-pair-overlap continuation.

This run therefore uses a single-run prepared-focus hard binding:
`route_pair_overlap_removal_protected_followup` must appear in the live
hypothesis mechanism changes. A different destroy/repair mechanism is not an
answer to this run's question.

## Target

- Surface: `solver_design`
- Action: `modify`
- Primary target file:
  `policies/baseline_modules/destroy_repair.py`
- Mechanism id required by prepared manifest:
  `route_pair_overlap_removal_protected_followup`
- Runner: server-local `claw`
- Model: local `gpt-5.5`
- Rounds: `2`
- Time limit: `30s`

The hard binding is a run-root prepared-manifest override, not a permanent
change to CVRP's default research guidance provider. The CVRP provider remains
proposal-only with empty default `required_mechanism_ids`.

## Design Constraints

- Preserve the successor27 route-pair-overlap causal path.
- Do not select an adjacent clean fork such as endpoint conflict, spoke
  outlier, generic boundary removal, or unrelated geometric removal.
- Add a protection policy before broader removal:
  - reject weak route-pair overlap scores;
  - downweight or skip pairs with low spare capacity or high load imbalance;
  - cap removed customers relative to route sizes;
  - avoid route-count pressure and infeasible reinsertion risk;
  - keep case-agnostic logic with no case id, seed, BKS, or split membership
    checks.
- If the implementation grows beyond a narrow patch, introduce a coherent
  problem-owned module boundary under `policies/baseline_modules/` instead of
  accumulating small helpers in an oversized file.
- Keep generic core, scheduler policy, protocol, lifecycle, launcher, and
  `DecisionFeatures` unchanged unless a minimal registration/telemetry call is
  required by the existing solver interface.

## Required Evidence

- Target-intent and hypothesis mechanism changes include exactly the prepared
  mechanism id `route_pair_overlap_removal_protected_followup`.
- The hypothesis explains how the protection differs from unchanged
  `route_pair_overlap_removal`.
- Direct mechanism telemetry is recorded under the declared id, including
  selection/skip/removal evidence and objective-effect fields.
- Formal screening preserves total_distance, feasibility, route count, and
  budget evidence.
- Postrun analysis separates aggregate median from CMT2, CMT4, P-family, and
  A/B/X case medians.

## Acceptance Reading

- Positive: aggregate median remains positive, A/B/X gains are not erased, and
  CMT2/CMT4/P-family losses shrink materially.
- Inconclusive: aggregate stays weak-positive below MDE but protected cases are
  mixed; do not broaden until a sharper diagnostic is designed.
- Reject: aggregate turns nonpositive, telemetry is missing, or protected-case
  losses remain similar to successor27. In that case, park the route-pair line
  and pivot to a materially different non-seed CVRP-owned mechanism.

## Launch Gate

Before launch:

- generate the run root with the existing CVRP launcher;
- patch only that run root's prepared manifest so both
  `research_focus.required_mechanism_ids` and typed
  `research_guidance_contract.required_mechanisms` require
  `route_pair_overlap_removal_protected_followup`;
- regenerate `prepared_run_manifest.md` and prepared handoff artifacts;
- verify `launch_research_guidance_payload(...).required_mechanism_ids` returns
  `["route_pair_overlap_removal_protected_followup"]`;
- completion preflight for local `gpt-5.5` must pass.
