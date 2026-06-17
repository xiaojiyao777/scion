# Scion v0.4 Current State

Last updated: 2026-06-17

This file is the short operational snapshot for resuming work. It should not be
used as an append-only experiment log. Detailed run facts live in
[`../experiments/v0.4/`](../experiments/v0.4/); older milestone notes live in
[`v0.4-history.md`](v0.4-history.md).

## Operating Frame

- Active branch: `codex/v04-evidence-repair-plan`.
- Governing design: [`../../design/scion-architecture-v3.md`](../../design/scion-architecture-v3.md).
- v0.4 closeout goal: make Scion stable enough that warehouse can recover
  continuous useful research and CVRP/VRP can produce evidence-backed solver
  hypotheses before v0.5 broad experiment matrices.
- Do not use broad budgets, truncation, compression, or generic gate tightening
  as the next repair. Keep CVRP/warehouse semantics in problem-owned layers;
  keep generic `DecisionFeatures` problem-neutral.

## Current Conclusions

Warehouse:

- The short validation-transfer acceptance-contract WSL gate completed cleanly
  from commit `ce5d884` and is accepted as positive warehouse recovery
  evidence:
  [`../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md`](../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md).
- The run reached screening, validation, frozen holdout, and promoted champion
  `v2`: `6/6` effective rounds, `8` Protocol rows, stage counts
  `screening=5`, `validation=2`, `frozen=1`, `1` promotion, wrapper exit `0`,
  and run validity `valid`.
- The promoted `pack_compatible_vehicles` operator is a split-preserving
  cost-compression mechanism. It matched the repaired contract by computing
  `split_delta == 0`, `cost_delta > 0`, exporting diagnostics, bounding
  enumeration, and no-oping when no candidate qualifies.
- This is a warehouse recovery checkpoint, not a final continuous-promotion
  proof. The remaining measurement caveat is that diagnostics still emit
  `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC` for zero `split_delta_sum` even when the
  declared useful effect is cost compression.

CVRP/VRP:

- Scion can carry CVRP candidates through the repaired framework, but it has
  not yet produced effective CVRP research against canonical ALNS+VNS.
- Broad VNS removal, pure ALNS/no-polish, and size70/two-opt as broad
  replacements are rejected by no-LLM evidence.
- The deep `initial_vns_disabled` matrix rejected simple initial-VNS
  disablement: `160/160` rows, overall W/L/T `25/51/4`, median delta `+2.0`.
  Objective probes show the skipped initial work mostly shifts pressure into
  embedded VNS rather than creating stable ALNS benefit.
- CVRP scheduler-local budget/iteration instrumentation is locally implemented
  and accepted:
  [`../experiments/v0.4/v04-cvrp-scheduler-iteration-telemetry-repair-20260617.md`](../experiments/v0.4/v04-cvrp-scheduler-iteration-telemetry-repair-20260617.md).
  It fixes construction/initial-VNS phase accounting, adds `alns_core` timing,
  and records bounded `solver_algorithm_alns_iteration_trace`. Do not launch a
  long LLM CVRP campaign from the current evidence.

## Active Work

- No LLM campaign is currently running.
- WSL still needs to be fast-forwarded from the completed warehouse run commit
  to the latest pushed CVRP telemetry commit before launching the next no-LLM
  matrix.

## Next Actions

1. Fast-forward the WSL runner checkout to the latest pushed branch head.
2. Run a compact no-LLM CVRP instrumentation validation matrix before any
   agentic CVRP campaign. Preferred first matrix: `P-n76-k4`, `CMT2`, `CMT4`,
   `M-n151-k12`; seeds `1..5`; mechanisms `canonical_alns_vns`,
   `embedded_vns_disabled`, and `pure_alns_no_polish`. Expand only if the new
   trace is informative.
3. Use the CVRP matrix to decide whether the next CVRP repair is scheduler
   semantics, opportunity diagnostics, or a narrow agentic solver-design brief.
4. Keep a later warehouse repeat available to test whether champion `v2`
   enables continuous follow-on improvement.

## Evidence Index

Core audits and plan:

- [`../../reports/v04-core-framework-review-20260611.md`](../../reports/v04-core-framework-review-20260611.md)
- [`../../reports/v04-core-framework-code-review-20260611.md`](../../reports/v04-core-framework-code-review-20260611.md)
- [`../../design/v0.5-evidence-uplift-roadmap.md`](../../design/v0.5-evidence-uplift-roadmap.md)
- [`../planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`](../planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md)

Warehouse current evidence:

- [`../experiments/v0.4/v04-warehouse-validation-transfer-acceptance-contract-repair-20260617.md`](../experiments/v0.4/v04-warehouse-validation-transfer-acceptance-contract-repair-20260617.md)
- [`../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-launch-20260617.md`](../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-launch-20260617.md)
- [`../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md`](../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md)

CVRP current evidence:

- [`../experiments/v0.4/v04-cvrp-mechanism-matrix-and-size70-repair-20260617.md`](../experiments/v0.4/v04-cvrp-mechanism-matrix-and-size70-repair-20260617.md)
- [`../experiments/v0.4/v04-cvrp-focused5-mechanism-wsl-70dfc53-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-focused5-mechanism-wsl-70dfc53-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-p76-deepseed-wsl-14c2a34-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-p76-deepseed-wsl-14c2a34-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-vns-variant-telemetry-repair-20260617.md`](../experiments/v0.4/v04-cvrp-vns-variant-telemetry-repair-20260617.md)
- [`../experiments/v0.4/v04-cvrp-vns-variant-matrix-wsl-6d742c6-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-vns-variant-matrix-wsl-6d742c6-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-initial-vns-deepseed-wsl-6d742c6-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-initial-vns-deepseed-wsl-6d742c6-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-scheduler-iteration-telemetry-repair-20260617.md`](../experiments/v0.4/v04-cvrp-scheduler-iteration-telemetry-repair-20260617.md)

WSL coordination:

- `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
- `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/RSYNC_PATHS.md`
