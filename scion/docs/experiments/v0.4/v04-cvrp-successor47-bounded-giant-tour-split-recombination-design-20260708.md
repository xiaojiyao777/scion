# CVRP successor47 design: bounded giant-tour split recombination

Date: 2026-07-08

Mechanism id: `bounded_giant_tour_split_recombination`

Target boundary:

- Primary target: `policies/baseline_modules/giant_tour_split.py`
- Minimal wiring: `policies/baseline_modules/scheduler.py`

## Purpose

Successor46b repaired activation visibility for best-solution ruin/recreate,
but stayed below MDE and was unsafe on CMT2. The next slot must not continue
that same line.

Successor47 is a materially different CVRP-owned clean fork. Instead of tuning
destroy/repair selection, acceptance, construction seed choice, local swap
moves, or best-solution ruin/recreate, it tests a route-first/split
recombination path:

1. Build one or more bounded giant-tour sequences from the current global-best
   solution.
2. Use capacity-constrained split dynamic programming to repartition the
   sequence into feasible routes.
3. Accept only a final feasible route set with no route-count regression and a
   strict `total_distance` improvement.

## Required Material Difference

The hypothesis must use exact `material_difference` keys:

- `changed_dimensions`
- `contrast`
- `evidence`

Required contrast:

- Not successor46/46b best-solution ruin/recreate.
- Not pre-VNS repair-placement, repair selector, or destroy selector.
- Not route-pair overlap, route-pair crossover, route fragment recombination,
  edge-frequency repair scoring, route memory repair, route skeleton repair,
  construction seed selector, acceptance guard, runtime allocation, or reviewed
  bounded local-search swap/or-opt/3-opt/ejection-chain/two-for-one variants.
- Not unbounded large-instance two-opt fallback.

## Implementation Contract

The implementation must stay inside the CVRP solver-design subject.

- Add the mechanism in a new module, not as ad hoc code inside `scheduler.py`.
- Keep scheduler changes to minimal orchestration.
- Do not modify generic Scion core, protocol selection, DecisionFeatures,
  postrun acceptance, or measurement gates.
- Bound split effort by remaining time, route count, and customer count.
- Reject infeasible candidates, duplicate/missing customer candidates, route
  count regressions, and candidates that do not strictly improve final
  `total_distance`.
- Do not call unbounded two-opt or VNS as the claimed mechanism.

## Evidence Contract

Required telemetry:

- Activation iterations for
  `bounded_giant_tour_split_recombination`.
- Phase runtime for the mechanism.
- Attempted and accepted move counts.
- Rejected-no-improvement, rejected-infeasible, rejected-route-count, and
  budget-stopped counts.
- Final accepted `total_distance` delta after split reconstruction.
- Feasibility and route-count preservation.
- CMT2/CMT4 priority-case outcome evidence.

If CMT2 or CMT4 does not activate the mechanism, the postrun analysis must
record that as a mechanism-level protection caveat rather than treating a case
tie as protection evidence.

## Launch Rule

Use a short server-local `claw` screening run first. Do not long-run unless
the short run has positive-at-MDE or a defensible validation/frozen path with
protected-case safety.
