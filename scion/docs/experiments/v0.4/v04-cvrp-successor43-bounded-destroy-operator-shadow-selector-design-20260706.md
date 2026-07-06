# CVRP successor43 bounded destroy-operator shadow selector design

Date: 2026-07-06

Status: preregistered target-intent design; ready for a two-round server-local
screening launch.

## Decision

Use successor43 for a clean fork named
`bounded_destroy_operator_shadow_selector`.

The intended owner is a new small CVRP solver module,
`policies/baseline_modules/destroy_operator_selector.py`, with only minimal
wiring from `policies/baseline_modules/scheduler.py`. This is a problem-owned
ALNS destroy-choice intervention. It must not touch generic Scion scheduler,
Decision, protocol, measurement, or lifecycle code.

For each eligible ALNS iteration, keep the adaptive-weight-selected
destroy/repair/q as the default candidate. When the remaining budget permits,
evaluate one alternate existing destroy operator on a copied current solution
with the same repair operator and q. Compare the default and alternate
post-repair candidates before embedded VNS or size70 polish. Select the
alternate only when it is feasible, does not increase route count, and improves
pre-VNS distance beyond a small margin; otherwise keep the default candidate.

## Why This Path

Successor42b repaired the prompt/schema/protected-case framework path, but
`elite_route_memory_repair` stayed marginal below MDE and failed CMT2/CMT4.
The next slot should therefore be a clean fork, not a same-mechanism tune.

`bounded_destroy_operator_shadow_selector` is materially distinct from reviewed
paths:

- not `elite_route_memory_repair`: no complete-route memory or template reuse;
- not `route_skeleton_regret_repair`: no route skeleton or continuity bias;
- not `bounded_dual_repair_selector`: it compares destroy choices, not repair
  choices;
- not route-pair-overlap, capacity-tight, edge-frequency, or other removal
  heuristics: it adds no new removal criterion and only selects among existing
  destroy operators;
- not bounded local search, construction seed selection, acceptance weighting,
  q scheduling, or embedded-VNS runtime allocation.

The direct evidence path is same-state and same-iteration: compare default
destroy+repair against alternate destroy+same-repair before downstream VNS can
blur attribution.

## Required Implementation Shape

Keep the implementation narrow and modular:

- Add at most one new focused module for the selector.
- Keep scheduler edits limited to constructing the selector input, invoking it
  after the default destroy/repair candidate is available, and passing the
  selected candidate into the existing polish, feasibility, acceptance, and
  adaptive-weight flow.
- Compare only one alternate destroy operator per eligible ALNS iteration.
- Skip shadow evaluation when the remaining budget is below the existing
  reserve guard.
- Reuse existing destroy and repair operators; do not add a new removal rule.
- Keep construction, repair implementations, local-search operators,
  simulated-annealing acceptance, adaptive scoring constants, and embedded-VNS
  cadence/runtime policy unchanged.

## Telemetry

The mechanism must emit direct pre-VNS objective evidence under
`bounded_destroy_operator_shadow_selector`:

- phase runtime for the shadow selector;
- default destroy, alternate destroy, repair operator, q, and selected label;
- default and alternate post-repair pre-VNS distances;
- default and alternate feasibility and route count;
- budget skip status;
- `record_move` attempted count, accepted alternate count, and
  `delta=max(0, default_distance - selected_distance)`;
- whether the selected pre-VNS candidate improves the current best distance.

Do not infer mechanism success from downstream ALNS/VNS improvements without
the direct selector telemetry above.

## CMT2/CMT4 Protection

Solver code must not hardcode case ids, BKS values, seeds, split membership, or
protected-case thresholds. CMT2/CMT4 protection comes from formal priority-case
coverage and postrun analysis.

The local guard is problem-agnostic: accept the alternate only when feasible,
route-count preserving, budget-safe, and pre-VNS improving. The postrun
analysis must report CMT2/CMT4 case-level `total_distance` deltas. Stable
negative CMT2 or CMT4 evidence parks the mechanism; do not follow with
same-mechanism threshold tuning.

## Acceptance Criteria

The experiment is valid only if:

- live target-intent and formal hypothesis use mechanism id
  `bounded_destroy_operator_shadow_selector`;
- `required_mechanism_ids` remains empty while
  `target_intent_required_mechanism_ids` binds only the target-intent preflight;
- target files are the new selector module and minimal scheduler wiring;
- the exact `material_difference.changed_dimensions`, `contrast`, and
  `evidence` schema appears in the accepted hypothesis;
- two screening rows complete without quality, model-call, telemetry,
  verification, or postrun failure;
- direct pre-VNS default-versus-alternate selector telemetry is present;
- CMT2/CMT4 effective priority coverage is present or an explicit measurement
  caveat is recorded.

Do not long-run successor43 unless screening shows row-level positive movement
with direct accepted selector effect and no protected-case collapse.
