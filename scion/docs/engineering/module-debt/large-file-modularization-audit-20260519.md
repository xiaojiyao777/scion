# Large File Modularization Audit

*Date: 2026-05-19*
*Status: P0/P1/P2 package-facade and command-package slices completed*
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

After the P1 slices, the remaining tracked Python file above 1000 lines was:

| Lines | File | Priority | Direction |
|---:|---|---|---|
| 1286 | `scion/scion/cli/main.py` | P2 | command package |

## P2 Queue

P2 has been implemented as a command-package migration:

- `scion/scion/cli/main.py` is now a small executable compatibility facade for
  `python -m scion.cli.main` and `from scion.cli.main import app`.
- `scion/scion/cli/app.py` owns Typer app/sub-app wiring.
- `scion/scion/cli/commands/` owns command registration by responsibility:
  run/init, inspect, reports, weights, postmortem, and shared validation
  helpers.
- CLI source-level regression tests that intentionally inspect implementation
  details now target the owning command module instead of the facade.

Current CLI line counts:

| Lines | File |
|---:|---|
| 393 | `scion/scion/cli/commands/init_run.py` |
| 336 | `scion/scion/cli/commands/postmortem.py` |
| 319 | `scion/scion/cli/commands/reports.py` |
| 292 | `scion/scion/cli/commands/inspect.py` |
| 263 | `scion/scion/cli/commands/weights.py` |
| 44 | `scion/scion/cli/commands/common.py` |
| 39 | `scion/scion/cli/app.py` |
| 31 | `scion/scion/cli/main.py` |

There are currently no tracked Python files above 1000 lines under
`scion/scion`.

## Migration Rules

- Design by module responsibility first; do not mechanically cut files by line
  count.
- Preserve public import paths through facade modules or package roots.
- Keep v3 boundaries intact: framework packages own control, protocol, audit,
  and exposure; problem semantics stay in problem packages/providers.
- Every package split needs focused tests for the boundary it touches before any
  experiment is started.
