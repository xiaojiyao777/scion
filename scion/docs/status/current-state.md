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

- The framework path is no longer catastrophically blocked: recent warehouse
  gates can reach Protocol, validation, and in some runs frozen holdout.
- Continuous improvement is still not recovered. The active bottleneck is
  proposal/code behavior for validation-transfer operators: candidates often
  preserve split count and compress cost, or omit executable split/cost
  diagnostics and bounded candidate policy.
- The latest local repair strengthened warehouse-owned guidance and code
  constraints for validation transfer: prefer split-positive moves; accept
  split-preserving cost-only moves only with executable `split_delta == 0` and
  `cost_delta > 0`; export deltas; no-op when no candidate qualifies.

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

- Warehouse short field gate is running on WSL from commit `ce5d884`.
  Launch report:
  [`../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-launch-20260617.md`](../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-launch-20260617.md).
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z`.
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z`.
- tmux session: `scion_wh_vt_contract_rerun6r_ce5d884_152944`.
- Shape: one warehouse production `6R` cell, `rep01/full_context`,
  measurement governance `on`, disabled early stop, WSL-local `gpt-5.5`, and
  no stage-drain/retry/session-timeout override.
- Initial health passed. The first observed signal was a problem-owned quality
  block for a missing `screening_or_lexicographic_guard`, which is behavior
  evidence only until the run completes.

## Next Actions

1. Finish the running warehouse gate: sync artifacts back, write a postrun, and
   judge behavior acceptance separately from research-quality acceptance.
2. Commit and sync the CVRP scheduler-local instrumentation slice after the
   running warehouse gate no longer depends on the WSL checkout state.
3. Run a compact no-LLM CVRP instrumentation validation matrix before any
   agentic CVRP campaign. Preferred first matrix: `P-n76-k4`, `CMT2`, `CMT4`,
   `M-n151-k12`; seeds `1..5`; mechanisms `canonical_alns_vns`,
   `embedded_vns_disabled`, and `pure_alns_no_polish`. Expand only if the new
   trace is informative.
4. Only after warehouse behavior is accepted and CVRP instrumentation is
   informative, decide whether to run longer warehouse/CVRP campaigns.

## Evidence Index

Core audits and plan:

- [`../../reports/v04-core-framework-review-20260611.md`](../../reports/v04-core-framework-review-20260611.md)
- [`../../reports/v04-core-framework-code-review-20260611.md`](../../reports/v04-core-framework-code-review-20260611.md)
- [`../../design/v0.5-evidence-uplift-roadmap.md`](../../design/v0.5-evidence-uplift-roadmap.md)
- [`../planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`](../planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md)

Warehouse current evidence:

- [`../experiments/v0.4/v04-warehouse-validation-transfer-acceptance-contract-repair-20260617.md`](../experiments/v0.4/v04-warehouse-validation-transfer-acceptance-contract-repair-20260617.md)
- [`../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-launch-20260617.md`](../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-launch-20260617.md)

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
