# Scion v0.4 Current State

Last updated: 2026-06-18

This file is the short operational resume point. Replace stale conclusions here
instead of appending event history. Detailed run evidence belongs in
`scion/docs/experiments/v0.4/`; `scion/docs/status/v0.4-history.md` is only a
curated milestone index.

## Operating Frame

- Active branch: `codex/v04-evidence-repair-plan`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- v0.4 closeout goal: make Scion stable enough that warehouse can recover
  continuous useful research and CVRP/VRP can produce evidence-backed solver
  hypotheses before v0.5 broad experiment matrices.
- Current posture: do not add broad budgets, truncation, compression, or generic
  gate tightening. Keep CVRP/warehouse semantics in problem-owned layers and
  keep generic `DecisionFeatures` problem-neutral.

## Current Truth

Framework:

- Campaign continuation and observability are repaired enough for focused
  follow-up. Copied campaigns restore champion, active branch, workspace,
  hypothesis, candidate patch, branch evidence, compact status/progress, reduced
  measurement readiness, and research-efficiency projections.
- These accepted repairs are continuation/reporting/launcher repairs. They do
  not change Decision, `DecisionFeatures`, scheduling, budgets, lifecycle
  policy, or problem semantics.
- Runtime semantics for budget-exhausting solvers are repaired in the narrow
  v0.4 sense: high aggregate `runtime_regression_rate` no longer blocks
  low-SNR trajectory-divergent screening expansion, drives lifecycle
  soft-abandon/repeated-signal noise, or creates strong prompt actionability
  when the problem declares `runtime_model=budget_exhausting`.
- Measurement integration is covered against real CVRP formal and warehouse
  production assets: problem-owned practical deltas, runtime model, pairing
  validity, and reduced readiness feed deterministic protocol config fields;
  raw calibration diagnostics stay outside `DecisionFeatures`; warehouse
  problem specs no longer hard-code local absolute surrogate paths.
- CVRP and warehouse launch helpers now support prepared follow-up roots,
  completion preflight, secret-safe API-key env wiring, runtime-source guards,
  campaign copy/resume, and default postrun report generation.

Warehouse:

- Warehouse has a v0.4 positive research-path checkpoint: champion `v2` promoted
  in the validation-transfer rerun, and the later cost-compression telemetry
  repair preserves real cost/improving-move effects without turning zero split
  delta into a false effect-zero diagnosis.
- The open warehouse question is continuous follow-on improvement, not basic
  viability.
- Prepared but not launched:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-6r-gpt55-lifecyclefix-6r-gpt55-20260618T103718Z-claw`.

CVRP/VRP:

- CVRP can now steer target intent, carry branch lessons into prompts, generate
  material solver code, complete formal screening, preserve mechanism telemetry,
  and reject weak or negative hypotheses with evidence.
- CVRP still has not met v0.4 effective-research acceptance: no current
  solver-design branch has produced continuous improvement or promotion.
- Avoid repeating unchanged broad VNS removal, pure ALNS/no-polish, simple
  initial-VNS disablement, raw cadence-2, recent-best/stall gating, fixed
  early-8, tested share70 cap/rescue variants, route-merge absorption,
  demand-slack regret insertion, cross-route 2-opt reconnect, cluster-biased
  worst removal, or route-limit seed diversification.
- Construction seed/portfolio mechanisms need direct effect attribution from a
  same-run seed baseline or same-mechanism accepted delta. Fallback activation,
  seed-pool size, or merely selecting a seed is only activation/design evidence.
- Prepared but not launched:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-1r-gpt55-lifecyclefix-1r-gpt55-20260618T103717Z-claw`.

Infrastructure:

- No LLM campaign is currently running.
- The next focused campaigns are blocked by LLM infrastructure. The WSL
  `gpt-5.5` chat-completion route most recently returned `401 Invalid proxy API
  key`; do not launch prepared roots until `/v1/chat/completions` returns HTTP
  `200` with non-empty output.
- WSL runs must use the synchronized WSL checkout and set
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`.

## Next Actions

1. Restore and verify the live `gpt-5.5` route with a real chat-completion
   preflight. `/v1/models` is not enough.
2. Launch the prepared CVRP post-pivot follow-up from the clean WSL checkout,
   then inspect target-intent, hypothesis, branch lesson transfer, protocol
   effect-vs-MDE, budget-exhausting runtime feedback, and postrun
   research-efficiency reports before accepting any conclusion.
3. Keep the prepared warehouse `v2` follow-up available as the simpler
   continuous-improvement check once LLM access is stable.
4. Keep status updates short: change this file only when the current operating
   truth or next action changes; put detailed evidence in experiment reports.

## Evidence Pointers

- Reset/audit basis:
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`, and
  `scion/design/scion-architecture-v3.md`.
- Current milestone index: `scion/docs/status/v0.4-history.md`.
- Current runtime-semantics repair:
  `scion/docs/experiments/v0.4/v04-budget-exhausting-runtime-regression-semantics-repair-20260618.md`
  and
  `scion/docs/experiments/v0.4/v04-budget-exhausting-decision-lifecycle-runtime-semantics-repair-20260618.md`.
- Current measurement-integration repair:
  `scion/docs/experiments/v0.4/v04-measurement-integration-real-asset-coverage-20260618.md`.
- WSL reference:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `RSYNC_PATHS.md`.
