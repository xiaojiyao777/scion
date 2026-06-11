# Scion v0.4 Evidence Repair Task

*Branch: `codex/v04-evidence-repair-plan`*
*Status: implementation in progress*

This task supersedes the stale v0.3 Sprint N1 checklist. The current objective
is to close the v0.4 repair/readiness gap before v0.5 runs broad controlled
experiments.

## Required Reading

1. `scion/design/scion-architecture-v3.md`
2. `scion/docs/AGENT_ONBOARDING.md`
3. `scion/docs/status/current-state.md`
4. `scion/reports/v04-audit-agent-experiment-guide-20260609.md`
5. `scion/reports/v04-core-framework-review-20260611.md`
6. `scion/reports/v04-core-framework-code-review-20260611.md`
7. `scion/design/v0.5-evidence-uplift-roadmap.md`
8. `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`

## Workstreams

- R1 Measurement and practical delta:
  add problem-owned measurement/readiness declarations, resolve practical delta
  values into protocol gates, and build A/A noise-floor calibration.
- R2 Runtime governance:
  support budget-exhausting solver semantics, remove meaningless runtime replay
  for saturated ties, and preserve quality-tie runtime speedup promotion.
- R3 Branch depth:
  expose branch-depth and mechanism-family evidence, and keep marginal
  same-mechanism follow-up deep enough to learn without weakening fail-closed
  regressions.
- R4 Context signal density:
  profile and compact model-visible context while preserving problem mechanics,
  target source, branch history, runtime/screening feedback, and cross-branch
  lessons.
- R5 Focused validation:
  run VRP/CVRP and warehouse campaigns only after R1-R4 instrumentation is
  ready, then audit with the 2026-06-09 guide.

## Acceptance

- No CVRP/VRP/warehouse semantics leak into generic Decision input.
- `DecisionFeatures` remains free of measurement diagnostics, BKS/gap, case
  hardness, and LLM text.
- Focused tests cover each code repair before real-cost experiments.
- Experiment reports reconcile copied configs, counters, prompt visibility,
  pair-level metrics, branch lifecycle, and Decision evidence.
- Git changes are kept by slice; unrelated dirty files are not reverted.

## Current Status

- Implemented: problem-owned `measurement` schema, protocol practical-delta
  resolution, runtime model resolution, budget-exhausting runtime governance,
  V9 budget-compliance semantics, read-only branch research-shape diagnostics,
  prompt block-family accounting, and compact research signals in hypothesis
  prompts.
- Implemented: `scion/tools/calibrate_aa_noise.py` plus calibration math tests.
  CVRP controlled smoke passed at 5s/10s with `n_pairs=1`; this validates the
  chain but is not a formal MDE report.
- Pending: full CVRP and warehouse A/A calibration reports, then focused
  VRP/CVRP and warehouse validation campaigns audited with the 2026-06-09 guide.

## Current Coordination

Main thread owns integration, git hygiene, final task ordering, and experiment
launch decisions. Subagents may own disjoint code or analysis slices, but each
must report changed files and focused validation evidence.
