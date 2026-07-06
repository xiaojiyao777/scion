# CVRP successor42 protected-case and schema repair design

Date: 2026-07-06

## Purpose

Successor41b showed that `route_skeleton_regret_repair` is exhausted as an
optimization candidate and exposed two research-entry issues before the next
clean fork:

- the exact CVRP hypothesis contract shape for `material_difference` must be
  prominent enough that the model does not use nearby aliases;
- CMT2/CMT4 protected-case intent must either be forced into screening or
  recorded as an explicit caveat.

This design repairs those entry conditions before launching successor42. It is
not a solver mechanism change.

## Boundary

The v3 boundary is preserved as follows:

- generic protocol selection may retain configured priority case ids, but it
  does not know CVRP, CMT, BKS, or protected-case semantics;
- CVRP owns the concrete CMT2/CMT4 declaration in
  `scion/problems/cvrp/formal/protocol.yaml`;
- proposal-visible schema wording stays in CVRP research guidance and CVRP
  hypothesis-quality contract;
- DecisionFeatures remain aggregate-only and do not receive case ids, CMT
  labels, or LLM prose.

## Implementation Shape

1. Extend the generic screening protocol config with
   `screening.priority_case_ids`, a deterministic list of case ids that must be
   retained when present in the stage split and when the selected case count is
   smaller than the split.
2. Reuse the existing selection priority resolver. It already resolves exact
   case ids and unique basenames, and it already preserves manifest order.
3. Record configured, requested, and effective priority-case metadata in raw
   protocol metrics so postrun analysis can distinguish "not requested" from
   "requested but unavailable".
4. Add CMT2/CMT4 to CVRP formal screening config.
5. Keep the CVRP exact `material_difference.changed_dimensions`,
   `material_difference.contrast`, and `material_difference.evidence` wording
   in problem-owned guidance and tests.

## Acceptance Criteria

- Formal CVRP `create_new` screening selection includes both
  `cvrplib/CMT/CMT2.vrp` and `cvrplib/CMT/CMT4.vrp`.
- Raw protocol metrics expose:
  - `configured_priority_case_ids`
  - `requested_priority_case_ids`
  - `effective_priority_case_ids`
- Prepared CVRP guidance still states the exact `material_difference` keys and
  the CMT2/CMT4 coverage requirement.
- No CVRP-specific case labels are introduced into generic Decision,
  Scheduler, or feature-extraction code.
- After tests pass, launch a short successor42 server-local experiment with
  local `gpt-5.5`.
