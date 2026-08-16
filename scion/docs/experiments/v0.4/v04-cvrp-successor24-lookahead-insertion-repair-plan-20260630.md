# CVRP Successor24 Lookahead Insertion Repair Plan - 2026-06-30

## Purpose

Define the next CVRP action after successor23. This is a design and
task-distribution artifact, not a run log.

Successor23 repaired observable q movement for
`stagnation_adaptive_destroy_size_schedule`, but it stayed solver-negative:
both screening rows were below MDE, the expanded row was negative, explicit
q-audit fields were missing, and the branch parked as quality regression.
Successor24 should therefore clean-fork to a different problem-owned solver
mechanism, not continue scheduler destroy-size policy work.

## Decision

Primary successor24 direction:

- implement `lookahead_insertion_cost_repair`;
- keep the primary target in
  `policies/baseline_modules/destroy_repair.py`;
- use `policies/baseline_modules/scheduler.py` only for minimal repair-operator
  registration and candidate-facing telemetry;
- keep q selection, acceptance, adaptive ALNS weights, construction, local
  search, protocol, generic core, and `DecisionFeatures` unchanged;
- interpret the result as destroy/repair repair-scoring evidence, not as a
  scheduler-policy or acceptance-temperature result.

This is a clean fork because the intended causal path is insertion-cost
externality during repair after destroy, not destroy size, removal geometry,
route merging, or local-search neighborhood expansion.

## Why This Is Different

Do not repeat unchanged reviewed paths. This design is not:

- successor21/22/23 scheduler destroy-size or q scheduling;
- route merge, route absorption, or route-limit seed diversification;
- demand-slack regret insertion based on demand similarity;
- angular, radial, polar, fragment, adjacency, route-pair, or timewarp removal;
- cross-route 2-opt reconnect, route-segment exchange, Or-opt, 3-opt, or
  ejection-chain local search;
- construction seed selection or exact short-route polish.

The mechanism changes the order and placement cost used when reinserting
already-removed customers. It should preserve the current destroy operators
and only add one bounded repair operator that competes with the existing
`greedy`, `regret2`, and `regret3` repairs.

## Causal Mechanism

The repair operator should estimate a one-step insertion externality before
committing each insertion:

1. start from the ruined candidate and the current `removed` list;
2. enumerate feasible insertion positions using the existing route/state APIs;
3. score a candidate insertion by its immediate cost plus a bounded estimate of
   how much it worsens the next remaining customers' cheapest feasible
   insertions;
4. prefer insertions that keep route capacity usable for subsequent customers
   and avoid premature new-route creation;
5. insert exactly one customer at a time, rebuild indexes through the existing
   state methods, and continue until all removed customers are reinserted.

The lookahead must remain bounded. It should cap the number of pending
customers, insertion positions, or secondary probes considered per step when
needed. It must not depend on case id, BKS, split membership, protected cases,
seed-specific shortcuts, or generic framework behavior.

## Module Boundary

Preferred implementation boundary for the Scion campaign candidate:

- primary target:
  `policies/baseline_modules/destroy_repair.py`
- minimal wiring:
  `policies/baseline_modules/scheduler.py`

Implementation guidance:

- add one coherent repair operator, for example
  `_lookahead_insertion_cost_repair(solution, removed, rng)`;
- use the existing `_Route` and `_Solution` methods instead of attaching
  dynamic state;
- keep helper growth minimal and local to the repair mechanism;
- register the operator in `repair_ops` under a clear name such as
  `lookahead_cost`;
- do not add generic helper modules, framework exceptions, new construction
  paths, new removal operators, or new local-search operators.

If the repair scoring logic becomes too large to audit in the existing file,
stop and make the next design step a focused destroy/repair package split
rather than adding a helper forest.

## Telemetry Contract

Required candidate-facing telemetry under `lookahead_insertion_cost_repair`:

- activation count when the repair operator is selected:
  `context.record_iteration("lookahead_insertion_cost_repair", 1)`;
- phase/runtime budget for the repair path:
  `context.record_phase("lookahead_insertion_cost_repair", elapsed_ms)`;
- direct effect when the repaired candidate improves the pre-VNS incumbent or
  best solution:
  `context.record_move("lookahead_insertion_cost_repair", attempted=1,
  accepted=1, delta=..., best_improved=...)`.

The strongest direct attribution is a bounded same-ruin comparison against an
existing repair such as `regret3`, recorded before downstream VNS can blur the
effect. If that comparison is too expensive, record only defensible pre-VNS
candidate improvement versus current/best and classify objective evidence
conservatively.

Existing ALNS iteration trace fields for repair operator and
`candidate_after_repair_distance` should remain available as diagnostic
support, but ordinary aggregate ALNS best updates are not a substitute for the
mechanism-id telemetry above.

## Static Quality Risks

Known risks:

- a scheduler-only patch that only changes repair weights is not this
  mechanism;
- a repair that is just demand-slack regret under a new name is reviewed and
  should be rejected;
- unbounded lookahead can consume the 30s screening budget and create runtime
  noise instead of quality evidence;
- activation-only evidence is insufficient if the repair operator rarely runs
  or never changes pre-VNS objective trajectory;
- CMT2 and CMT4 regressions remain material caveats even if aggregate evidence
  improves.

## Acceptance Evidence

Minimum evidence before interpretation:

- live hypothesis names `lookahead_insertion_cost_repair`;
- `target_file` is
  `policies/baseline_modules/destroy_repair.py`;
- scheduler edits, if present, are limited to import, `repair_ops`
  registration, and telemetry around the chosen repair;
- no proposal, contract, verification, telemetry, or infra failure;
- formal screening rows are complete and interpreted against CVRP A/A MDE;
- mechanism activation is observed;
- direct effect telemetry is present or the postrun explicitly classifies the
  missing attribution caveat;
- CMT2/CMT4 case-level deltas are visible;
- at least one row is positive at or above MDE before any solver-positive
  claim.

Outcome classifications:

- `solver-positive-at-MDE`: at least one row reaches MDE without unresolved
  protected-case regression.
- `activation-observed-below-MDE`: the repair runs and direct evidence exists,
  but formal rows stay below MDE.
- `inactive-or-miswired-repair`: the declared repair is not selected or lacks
  activation telemetry.
- `wrong-mechanism`: the candidate drifts to scheduler q, acceptance tuning,
  demand-slack regret, reviewed removal, construction seed, or local-search
  paths.
- `quality-regression`: aggregate or protected-case evidence regresses.

## Launch Shape

Use WSL for a two-round run after syncing this plan and the status docs:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 2 \
  --label v04-cvrp-successor24-lookahead-insertion-repair \
  --model gpt-5.5 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --completion-preflight \
  --force-surface solver_design \
  --force-action modify \
  --force-target-file policies/baseline_modules/destroy_repair.py \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments \
  --launch
```

## Main Session Responsibilities

- Keep `scion-architecture-v3.md` boundaries intact.
- Keep this as a CVRP-owned solver-design task.
- Sync the plan and status docs to WSL before launch.
- Check fresh WSL connectivity and completion preflight before trusting the run.
- Assign postrun analysis after the run finishes.
- Interpret the result against MDE, direct repair telemetry, ALNS trace support,
  and CMT protected-case evidence.

## Campaign-Agent Responsibilities

- Produce a normal Scion proposal through Contract and Verification.
- Name `lookahead_insertion_cost_repair` as the mechanism id.
- Keep the primary code change in `destroy_repair.py`.
- Use scheduler only for minimal operator-pool wiring and mechanism telemetry.
- Preserve feasibility, route-count constraints, seeded determinism, and runtime
  guards.
