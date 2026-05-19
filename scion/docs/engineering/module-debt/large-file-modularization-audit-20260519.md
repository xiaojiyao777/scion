# Large File Modularization Audit

*Date: 2026-05-19*
*Status: P0/P1 package-facade slices completed; remaining P2 CLI debt queued*
*Required reading: `scion/docs/AGENT_ONBOARDING.md` and
`scion/design/scion-architecture-v3.md`*

## Baseline

After the `context_manager` package split, tracked Python files above 1000
lines were:

| Lines | File | Priority | Direction |
|---:|---|---|---|
| 1987 | `scion/scion/protocol/experiment.py` | P0 | package/facade |
| 1540 | `scion/scion/core/proposal_pipeline.py` | P0 | package/facade |
| 1483 | `scion/scion/proposal/tools/feedback.py` | P1 | package/facade |
| 1417 | `scion/scion/proposal/engine.py` | P1 | package/facade |
| 1352 | `scion/scion/proposal/solver_design_smoke.py` | P1 | package/facade |
| 1286 | `scion/scion/cli/main.py` | P2 | command package |
| 1274 | `scion/scion/runtime/telemetry_guard.py` | P0 | package/facade |
| 1171 | `scion/scion/proposal/tools/surface.py` | P1 | package/facade |

`scion/scion/proposal/context_manager.py` was 2733 lines before this slice. It
is now a same-name package whose largest file is under the soft 800-line
guideline:

| Lines | File |
|---:|---|
| 717 | `context_manager/runtime.py` |
| 664 | `context_manager/guidance.py` |
| 571 | `context_manager/manager.py` |
| 343 | `context_manager/io.py` |
| 224 | `context_manager/code_context.py` |
| 194 | `context_manager/history.py` |
| 127 | `context_manager/__init__.py` |
| 71 | `context_manager/rendering.py` |

## P0 Queue

P0 has been implemented as package/facade migrations:

- `scion/scion/protocol/experiment.py` was replaced by
  `scion/scion/protocol/experiment/`. `ExperimentProtocol`, `SplitManager`,
  and `SeedLedger` remain import-compatible while stage orchestration,
  split/seed selection, runtime observation, selected-surface runtime summaries,
  failure taxonomy, and pair/case feedback aggregation live in focused modules.
- `scion/scion/core/proposal_pipeline.py` was replaced by
  `scion/scion/core/proposal_pipeline/`. `ProposalPipeline` remains
  import-compatible while agentic request assembly, output validation,
  failure lifecycle, lineage/session references, boundary checks, and
  classification live in focused modules.
- `scion/scion/runtime/telemetry_guard.py` was replaced by
  `scion/scion/runtime/telemetry_guard/`. Public guard APIs remain
  import-compatible while expected telemetry schemas, declarations, runtime
  paths, observations, evidence checks, issue formatting, and summary building
  live in focused modules.

After the P0 slices, tracked Python files above 1000 lines were:

| Lines | File | Priority | Direction |
|---:|---|---|---|
| 1483 | `scion/scion/proposal/tools/feedback.py` | P1 | package/facade |
| 1417 | `scion/scion/proposal/engine.py` | P1 | package/facade |
| 1352 | `scion/scion/proposal/solver_design_smoke.py` | P1 | package/facade |
| 1286 | `scion/scion/cli/main.py` | P2 | command package |
| 1171 | `scion/scion/proposal/tools/surface.py` | P1 | package/facade |

## P1 Queue

P1 has been implemented as package/facade migrations:

- `scion/scion/proposal/engine.py` was replaced by
  `scion/scion/proposal/engine/`. `CreativeLayer`,
  `ProposalValidationError`, parsing helpers, and context split helpers remain
  import-compatible while prompt rendering, solver-design provider glue,
  response parsing/bounds, trace writing, and fix-context rendering live in
  focused modules.
- `scion/scion/proposal/solver_design_smoke.py` was replaced by
  `scion/scion/proposal/solver_design_smoke/`. Historical helper imports used
  by preview tools remain compatible while workspace materialization, patch
  path safety, smoke case selection, solver-run subprocess adaptation, runtime
  audit, micro-benchmark comparison, effort checks, and repair guidance live in
  focused modules.
- `scion/scion/proposal/tools/feedback.py` and
  `scion/scion/proposal/tools/surface.py` were replaced by same-name packages.
  Registry tool names and public imports remain compatible while feedback
  memory/screening/holdout/runtime queries, provenance/scope guards, runtime
  attribution, diagnosis, surface metadata, code reads, support artifacts, and
  payload compaction live in focused modules.

The current tracked Python files above 1000 lines are now:

| Lines | File | Priority | Direction |
|---:|---|---|---|
| 1286 | `scion/scion/cli/main.py` | P2 | command package |

## P2 Queue

`cli/main.py` should become Typer app wiring with command groups under
`cli/commands/*`: run/init, inspect, reports, weights, postmortem, and
validation helpers.

## Migration Rules

- Design by module responsibility first; do not mechanically cut files by line
  count.
- Preserve public import paths through facade modules or package roots.
- Keep v3 boundaries intact: framework packages own control, protocol, audit,
  and exposure; problem semantics stay in problem packages/providers.
- Every package split needs focused tests for the boundary it touches before any
  experiment is started.
