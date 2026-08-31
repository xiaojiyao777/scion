# v0.4 Large-File Modularization Plan

*Date: 2026-06-29*
*Status: Design and task-prep; no runtime behavior change*
*Architecture baseline: `scion/design/scion-architecture-v3.md`*

## Purpose

This plan updates the large-file debt queue for the current v0.4 work. The goal
is not to move lines into helpers. The goal is to preserve Scion's v3 control
boundaries while turning large behavior clusters into coherent packages with
small public facades.

During active CVRP successor experiments, implementation must avoid hot
campaign paths unless a failing experiment makes a focused fix necessary. The
first development slice should therefore start in post-run reporting, where the
behavior is report-only and easier to regression-test against existing
artifacts.

## Current Large Files

Current line counts from the v0.4-dev checkout:

| Lines | File | Initial direction |
| ---: | --- | --- |
| 4243 | `scion/tools/postrun_analysis_brief.py` | P0 report-only package split |
| 2481 | `scion/scion/core/branch_step_runner.py` | P1 hot runtime, design first |
| 1805 | `scion/scion/core/decision_finalizer.py` | P1 hot decision boundary |
| 1730 | `scion/scion/core/research_efficiency_report.py` | P1 report package split |
| 1573 | `scion/scion/proposal/engine/hypothesis_prompts.py` | P1 prompt package split |
| 1560 | `scion/scion/proposal/context/cross_branch_research_support.py` | P1 context package split |
| 1557 | `scion/scion/problems/cvrp/solver_design_provider.py` | P1 CVRP-owned provider split |

## Boundary Rules

- Core framework modules stay problem-neutral. Do not add CVRP, warehouse,
  route, capacity, demand, depot, order, or picker semantics outside problem
  packages.
- Problem packages own problem semantics, prompt guidance, solver-design smoke
  interpretation, telemetry meanings, and repair hints.
- Large-file cleanup is not helper accretion. A slice is acceptable only when
  the extracted module has one stable responsibility and a narrow public API.
- Keep compatibility facades in place while call sites and tests migrate.
- Do not change artifact schemas, campaign scheduling, promotion logic, or
  DecisionFeatures inputs in the same slice as a mechanical package split.
- Prefer small modules under an owning package over a single generic
  `utils.py`.

## P0 Slice: Post-Run Brief Package

Target shape:

```text
scion/tools/postrun_analysis_brief.py
  -> CLI and compatibility facade only

scion/scion/postrun/brief/
  __init__.py
  builder.py
  markdown.py
  artifact_checklist.py
  branch_state.py
  protocol_accounting.py
  measurement_effects.py
  runtime_feedback.py
  failure_taxonomy.py
  prompt_visibility.py
  research_continuity.py
  problem_followups.py
```

The first implementation task should extract only these report-only clusters:

1. `protocol_accounting.py`
   - Move `_protocol_accounting_summary`, `_protocol_accounting_entry`,
     compactors, aggregate initialization, aggregate merge, and reconciliation
     status collection.
   - Keep return dictionaries and schema strings unchanged.

2. `measurement_effects.py`
   - Move `_measurement_effect_summary`, `_measurement_effect_entry`,
     protocol-effect compaction, aggregate initialization, and aggregate merge.
   - Keep MDE/effect field names unchanged.

3. `builder.py`
   - Keep `build_brief(...)` as the package-level orchestration entrypoint.
   - Import protocol accounting and measurement effects from their owning
     modules.

4. `markdown.py`
   - Move `render_markdown(...)` only after the data builders have tests.
   - Do not rewrite markdown content in the first slice.

`scion/tools/postrun_analysis_brief.py` should continue to expose the same CLI
behavior and import-compatible `build_brief` / `render_markdown` names during
the transition.

## Acceptance Tests

The first slice is acceptable only if all of the following pass:

- `PYTHONPATH=scion python -m compileall -q scion/scion/postrun/brief scion/tools/postrun_analysis_brief.py`
- Existing post-run brief tests, or a new focused regression fixture that
  asserts `build_brief(run_root)` produces the same
  `protocol_accounting_summary` and `measurement_effect_summary` before and
  after the split.
- A smoke run of `scion/tools/postrun_analysis_brief.py` against an existing
  v0.4 run root.
- `git diff --check`

No CVRP successor experiment should be relaunched merely to validate this
slice. Use existing artifacts for report-only regression.

## Deferred Runtime Slices

After the P0 report-only split lands, design the hot-path files before editing
them:

- `branch_step_runner.py`: split by stage responsibility only after mapping
  branch lifecycle, proposal, verification, protocol, and evidence recording
  side effects.
- `decision_finalizer.py`: split only around v3 Decision boundary concepts:
  safe feature extraction, deterministic decision payloads, lifecycle actions,
  and report-only summaries.
- `research_efficiency_report.py`: pair with post-run brief package interfaces
  so report artifacts do not invent a second accounting model.
- `solver_design_provider.py`: keep CVRP-owned, but split into prompt guidance,
  static quality/smoke guidance, successor evidence guidance, and active solver
  map rendering modules.

These later slices should wait until the current CVRP v0.4 successor evidence
thread has either produced a candidate result or a concrete blocker.
