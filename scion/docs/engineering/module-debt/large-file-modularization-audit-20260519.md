# Large File Modularization Audit

*Date: 2026-05-19*
*Status: Context-manager P0 slice completed; remaining architecture debt queued*
*Required reading: `scion/docs/AGENT_ONBOARDING.md` and
`scion/design/scion-architecture-v3.md`*

## Baseline

After the `context_manager` package split, tracked Python files above 1000
lines are:

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

`protocol/experiment.py` is closest to v3 protocol reliability and
Decision-input boundaries. Keep `ExperimentProtocol` as the public facade and
split stage orchestration, split/seed selection, runtime observation, surface
runtime summary, failure taxonomy, and pair/case feedback aggregation.

`core/proposal_pipeline.py` sits on the tainted creative to deterministic
contract/protocol path. Keep `ProposalPipeline` as facade and split agentic
request assembly, output validation/sanitization, failure lifecycle,
lineage/session references, and repair orchestration.

`runtime/telemetry_guard.py` is a fail-closed evidence boundary. Keep the guard
facade and split expected schema normalization, declaration extraction, runtime
path parsing, observation collection, value checks, and issue formatting.

## P1 Queue

`proposal/engine.py` should keep `CreativeLayer` as facade while prompt
builders, provider glue, response parsing/bounds, trace writing, and fix-context
rendering move into focused modules.

`proposal/solver_design_smoke.py` should split by smoke lifecycle: workspace
materialization, patch application, smoke case selection, solver-run adapter,
telemetry audit, micro-benchmark comparison, and repair guidance. It may call
problem-owned providers, but generic smoke logic must not absorb problem
semantics.

`proposal/tools/feedback.py` and `proposal/tools/surface.py` should become
tool packages after the context-manager split is stable. Preserve registry tool
names while separating payload compaction, provenance/scope guards, runtime
attribution, surface metadata, code-file reading, and path-permission checks.

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
