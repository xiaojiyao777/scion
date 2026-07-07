# CVRP successor45 repair-placement tournament design - 2026-07-07

## Purpose

Successor45 is a CVRP-owned clean fork, not a rewrite of the VRP solver.
It keeps the existing ALNS/VNS baseline as the research substrate and changes
one problem-owned mechanism inside the repair-placement stage.

The immediate precondition is to remove the stale successor44 target binding
from CVRP guidance. Successor44d repaired the policy-effect warning hygiene
for `post_vns_best_anchor_acceptance_guard`, but its solver evidence is still
weak-positive below MDE and not a long-run candidate. The next slot must not
continue to force that mechanism unless a future design explicitly declares a
new acceptance-policy mechanism id and a new material-difference argument.

## Boundary

- Generic campaign, protocol, decision, and `DecisionFeatures` code stay
  unchanged.
- CVRP semantics stay in `scion/problems/cvrp`.
- The solver change is limited to `policies/baseline_modules/destroy_repair.py`
  with minimal scheduler registration/wiring if a live proposal chooses this
  mechanism.
- No case-specific logic is allowed in solver code; CMT2/CMT4 are measurement
  obligations, not hard-coded branches.

## Mechanism

Mechanism id: `bounded_repair_placement_tournament`

Owner: `policies/baseline_modules/destroy_repair.py`

Research idea: after a destroy step has produced one removed-customer set, keep
the normally selected repair candidate as the baseline repaired solution. Then
build a bounded alternate placement candidate for the same removed-customer
set. Replace the repaired solution only when the alternate is feasible,
route-count safe, and strictly improves post-repair total distance before VNS.

This is materially different from reviewed branches:

- not successor39/43/43b repair or destroy operator selection, because the
  selected destroy/repair operator can remain unchanged while placement inside
  the repair result is challenged;
- not successor24 insertion-cost lookahead, because the comparison is between
  completed repaired candidates for the same removed-customer set, not a local
  one-step insertion scoring rule;
- not route memory or route skeleton repair, because it does not replay
  complete historical routes or preserve a route skeleton template;
- not route-pair-overlap, capacity-tightness, angular/radial/farthest removal,
  because it does not change which customers are removed.

## Evidence Contract

The hypothesis must include:

- `material_difference.changed_dimensions`, `contrast`, and `evidence`;
- `expected_telemetry.effect` containing
  `bounded_repair_placement_tournament`;
- CMT2/CMT4 protected-case plan in
  `branch_lesson_usage.clean_fork_diversity_claim`.

Candidate telemetry should separate local repair gain from downstream final
evidence:

- direct repair-placement delta:
  `baseline_repaired_distance - selected_repaired_distance`;
- activation/activity counts under `bounded_repair_placement_tournament`;
- phase runtime for the bounded tournament;
- post-polish/final per-case `total_distance`, feasibility, route count, and
  CMT2/CMT4 results from the formal protocol.

Do not claim promotion from pre-VNS repair delta alone. The final solver claim
must come from protocol case/seed outcomes.

## Development Shape

When implemented by the live agent, keep it as a small module-owned policy
path:

- add the bounded tournament repair operator in `destroy_repair.py`;
- register it through the existing CVRP repair operator list;
- keep scheduler changes to operator wiring and trace propagation only;
- avoid generic helpers or cross-cutting abstractions.

The intended file sizes and ownership remain modular: a single mechanism
belongs to the CVRP baseline module where the placement logic is already
owned.

## Launch Plan

After guidance unbinding and tests pass, launch a short server-local
two-round run with local `gpt-5.5`. Treat it as screening only. Because a
two-round run is noisy, only consider a long run if the mechanism has active
direct repair-placement evidence, positive final protocol direction, and no
CMT2/CMT4 protected-case regression.
