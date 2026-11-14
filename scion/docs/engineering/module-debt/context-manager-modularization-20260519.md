# Context Manager Modularization Design

*Date: 2026-05-19*
*Status: Package facade implemented; provider-owned solver-design context migrated*
*Scope: `scion/scion/proposal/context_manager/`,
`scion/scion/proposal/context/`, and compatibility context builders*
*Required reading: `scion/docs/AGENT_ONBOARDING.md`,
`scion/design/scion-architecture-v3.md`, and
`scion/docs/status/current-state.md`*

## Design Baseline

This split follows the v3 architecture rule: Scion core owns boundary control,
protocol control, exposure control, lineage, audit, and deterministic
decisions. Problem packages own objective semantics, feasibility, solver hooks,
allowed research surfaces, runtime audit field meanings, prompt rendering, and
problem-owned tests.

`ContextManager` is therefore not a semantic engine. Its job is a controlled
proposal-context facade:

- collect framework-owned proposal inputs
- select only information allowed for the current proposal phase
- call adapter/provider hooks for problem semantics
- render generic, bounded, tainted LLM context
- keep validation/frozen detail and raw metrics out of proposal prompts
- preserve the existing `build_*_context` API while internals move into
  responsibility modules

Decision filtering remains outside `ContextManager`; the v3
Safe Feature Extractor is still the only path into deterministic Decision.

## Current External API

`ContextManager` is the stable entry point for proposal prompt assembly:

- `build_hypothesis_context(...) -> dict[str, Any]`
- `build_code_context(...) -> dict[str, Any]`
- `build_fix_context(...) -> dict[str, Any]`

The package facade also exposes historical helper functions used by tests, tools, and
campaign services. These are not ideal public API, but they are currently
imported directly and must remain available through `context_manager` during
the split:

- family/coverage helpers: `assign_family_id`, `build_exploration_coverage`,
  `_extract_families_from_steps`, `_build_strategy_guidance`
- safe exposure helpers: `_filter_hypothesis_prompt_steps`,
  `_build_runtime_feedback`, `_build_runtime_failure_guidance`,
  `_build_agent_quality_feedback`
- problem/surface helpers: `_get_adapter_problem_spec`,
  `_get_research_surfaces`, `_build_problem_summary`,
  `_build_research_surface_interface_spec`
- formatting helpers used by tests: `_format_hypothesis`,
  `_render_case_feedback`, `_build_experiment_history`,
  `_build_consecutive_failure_diagnosis`, `_build_branch_direction_prompt`,
  `_build_failure_pattern_warning`, `_build_champion_baselines`

The package root preserves these imports by re-exporting moved helpers from
`scion.proposal.context_manager`.

The intended facade contract during modularization is:

- external callers instantiate `ContextManager(adapter=...)`
- external callers keep using `build_hypothesis_context`,
  `build_code_context`, and `build_fix_context`
- historical helper imports from `scion.proposal.context_manager` remain
  compatibility re-exports until call sites migrate
- `ContextManager` orchestration now lives in
  `scion.proposal.context_manager.manager`; supporting code-context, guidance,
  history, I/O, rendering, and runtime helpers live in the same package
- lower-level generic research-surface and feedback builders remain under
  `scion.proposal.context`
  and are internal unless a helper is explicitly promoted to a documented API
- `scion.proposal.context_builders` remains a temporary compatibility package
  that re-exports the new modules for tests/tools not yet migrated

## Current Responsibilities

The old single `context_manager.py` mixed five responsibilities that now live
behind package modules:

- `context_manager/code_context.py`: active solver context, solver-design
  manifest rendering, branch-current integration file summaries, and active
  target expansion
- `context/surfaces.py`: surface list filtering, metadata rendering,
  forced-surface prompt constraints, novelty signature summaries, target/action
  permission text, and inactive legacy-surface warnings
- `context/feedback.py` and `context_manager/history.py`: screening-only
  experiment history, case
  feedback, pattern summaries, champion baseline hints, runtime feedback,
  proposal-only quality blocks, search memory, research log, saturation, and
  weight feedback
- proposal/session tools: APS observation budgets, compact tool payload
  expectations, terminal preview reserves, and text-size controls currently
  spread across proposal tools and session modules
- `context/problem_adapter.py`: problem summary, problem object, solver mechanics,
  operator/research-surface interface rendering, objective policy rendering,
  and adapter/spec selection

The package split makes exposure review more localized: problem-independent
context protocol code, problem-owned metadata rendering, proposal feedback
policy, and active solver diagnostics no longer live in one file.

## v3 Boundary Rule

Scion context assembly must remain problem independent. The context layer may
assemble declared metadata, enforce exposure rules, and render generic protocol
facts. It must not encode research-object semantics for CVRP, warehouse
delivery, TSP, or any future problem.

Problem semantics must come from one of these sources:

- the loaded problem spec and its declared research surfaces
- the loaded adapter/problem package
- protocol/verification facts already normalized by framework-owned dataclasses

Framework prompt text may say "research surface", "objective", "runtime
evidence", "screening", or "active problem boundary". It must not introduce
domain nouns such as customer, vehicle, depot, route, order, warehouse, or any
specific algorithm family unless that text originated from the problem package.

Solver-design context rendering must use problem-owned provider hooks for
algorithm file maps and target-specific guidance. The generic context manager
may read the requested files and enforce exposure/path constraints, but it must
not know package-owned filenames or algorithm families.

## Dependency Direction

Allowed dependency direction:

```text
core/proposal pipeline
  -> ContextManager facade
     -> scion.proposal.context.*
        -> generic core dataclasses / generic ProblemSpec / generic surface utils
        -> adapter/provider protocol calls
           -> problem package implementation
```

Disallowed dependency direction:

```text
scion.proposal.context.* -> scion.problems.cvrp.*
scion.proposal.context.* -> problem-owned solver modules
scion.proposal.context.* -> concrete campaign artifacts outside supplied inputs
problem package -> ContextManager internals
Decision/core protocol -> proposal-context free text
```

Builder import rules:

- `problem_adapter.py` may call adapter methods by protocol/duck typing, but it
  must not import any concrete adapter implementation.
- `research_surfaces.py` may read declared research-surface metadata and generic
  `core.forced_surface` helpers. It must not infer domain behavior from surface
  names beyond generic kinds/roles such as `solver_design`.
- code-context helpers may render active algorithm context only from declared
  surfaces, branch/champion inputs, and adapter/provider hooks. Any
  problem-specific file map or target guidance must be provider-owned.
- future `feedback_memory.py` may read framework `StepRecord` and
  screening-stage normalized feedback. It must not expose validation/frozen
  per-case detail or raw metrics refs.
- future `budget_compaction.py` may define generic text/observation budgets and
  compaction policies. It must not make problem-quality decisions.

Proposal tools may temporarily import compatibility helpers from
`scion.proposal.context_manager`, but new shared context logic should live in
the responsible context package and flow through the facade or explicit
internal imports. Existing `context_builders` imports should be treated as
compatibility imports only.

## Forbidden Framework Semantics

The generic `core`, `proposal`, `contract`, `protocol`, and `runtime` layers
must not contain problem-owned semantics. In this context-manager split, the
following cannot be added to framework code:

- CVRP, warehouse, TSP, or future problem nouns as framework-authored guidance
- route, customer, depot, demand, capacity, vehicle, order, warehouse, or
  similar object-model assumptions
- ALNS/VNS, `_ALNSVNSSolver`, or named problem-solver lifecycle rules as generic
  proposal guidance
- concrete problem package paths such as package-owned policy/module filenames,
  except while preserving existing behavior before provider migration
- objective formulas, feasibility rules, parser assumptions, protocol split
  case names, seed meanings, or benchmark-data interpretations
- runtime audit field meanings unless they are declared by the problem spec or
  rendered by the adapter/provider
- prompt anti-patterns or target-specific implementation rules that originate
  from a single problem rather than adapter/provider metadata

Framework-owned text may still describe generic concepts: research surface,
target file, action permission, objective policy, screening feedback, active
problem boundary, branch state, budget, compact observation, and tainted
proposal context.

## Target Module Layout

The context-manager implementation package is
`scion.proposal.context_manager`. The old single
`scion/proposal/context_manager.py` file has been replaced by a same-name
package with a compatibility root. Historical imports such as
`from scion.proposal.context_manager import ContextManager` still work.

The lower-level `scion.proposal.context` package remains responsible for
generic research-surface and feedback helpers that predated the same-name
package migration.

The context package should be split by ownership:

- `context/problem_adapter.py`
  Adapter/spec hook calls and legacy generic fallbacks. This owns
  `render_problem_summary`, `render_problem_object`, `render_solver_mechanics`,
  and active research-surface interface rendering.

- `context/surfaces.py`
  Problem-declared research-surface rendering and generic selection helpers:
  surface metadata, target/action permissions, novelty signature instructions,
  inactive legacy-surface exclusion, solver-design surface name detection by
  generic kind/role, and concrete target-file expansion helpers that do not read
  problem semantics.

- `context/active_solver.py`
  Active solver/algorithm-object context. This should eventually own solver
  design manifests, branch-current integration summaries, active algorithm file
  listings, and call-graph/read helpers. Problem-specific algorithm file maps or
  target guidance must come from adapter hooks, not framework constants.

- `context/feedback.py`
  Screening-only history rendering, case feedback, pattern summary,
  proposal-only quality feedback, memory/research-log/saturation/weight
  exposure, and validation/frozen redaction policy.

- `context/budget.py`
  Prompt/tool observation text budgets, compact renderers, terminal reserve
  helpers, and budget denial summaries. This module should share policy with
  APS session/tool code instead of duplicating limits.

`context_manager/manager.py` is the orchestration facade: collect inputs, call
the builder modules, and return the same context dictionaries. The package
root re-exports compatibility helper names.

`context_builders/*` should be reduced to thin re-export modules and deleted in
a later cleanup after direct imports have moved.

## Phase Plan

Phase 1, implemented in commit `a2929b0`:

- add the `context_builders` package
- move pure research-surface rendering and generic adapter-hook helpers
- keep all helper names available from `scion.proposal.context_manager`
- avoid behavioral changes and avoid edits to proposal preview or contract gate
  files

Phase 2, implemented after `a2929b0`:

- move screening/proposal feedback rendering into
  `context_builders/feedback_memory.py`
- keep `ContextManager` as the compatibility facade for historical helper
  imports
- keep the extraction limited to behavior-preserving rendering of safe
  prompt-visible facts:
  screening-only step filtering, branch experiment history, pattern/case
  feedback, proposal-only agent-quality blocks, what-worked summaries,
  verification-failure diagnosis text, and champion baseline hints
- leave runtime feedback, search-control guidance, objective steering, and
  active solver-design code context in the compatibility module for later
  phases

Phase 2 is intentionally not a generic helper bucket. The new module owns one
stable responsibility: proposal-visible feedback/memory exposure. It may read
framework `StepRecord`/`ProtocolResult` structures and normalized
screening-stage feedback, but it may not interpret problem objects or infer
solver semantics. Case-feature labels are rendered from already-supplied
metadata keys and capped; their meaning remains problem-owned.

Phase 2 does not implement a problem-owned provider for solver-design prompt
guidance. That debt remains because the risky strings and path maps sit in the
active-solver/code-read context, not in the history/feedback renderer.

Phase 3, implemented package-boundary slice:

- introduce `scion.proposal.context` as the implementation package
- move the existing research-surface, adapter-hook, and feedback modules into
  the new package without changing behavior
- leave `scion.proposal.context_manager` as the public facade for
  `ContextManager` and historical helper imports
- leave `scion.proposal.context_builders` as compatibility re-export modules
- initially did not move active solver/code-read context, because it required
  problem-owned provider design before extraction

This was a package-boundary slice, not a line-count exercise. The follow-up
same-name package migration replaced `context_manager.py` with
`context_manager/` once the compatibility facade was ready.

Phase 4:

- implemented in the same-name package migration: active solver-design code
  context now lives in `scion.proposal.context_manager.code_context`
- framework-owned CVRP file maps and target-specific strings have moved behind
  `SolverDesignPromptProvider` hooks:
  `solver_design_api_manifest_files()`,
  `solver_design_integration_full_files()`,
  `solver_design_integration_summary_files()`, and
  `solver_design_target_api_guidance(target_file)`
- `scion.proposal.context_manager` was checked for CVRP/ALNS/VNS/domain terms;
  problem-owned terms now belong in `scion.problems.*`

Phase 5:

- centralize APS/context budget and compaction policy
- keep proposal tools and prompt builders on the same compact rendering rules
- add regression tests for observation budget reserve behavior

Phase 6:

- evaluate direct imports of private helpers from other modules
- either formalize a small compatibility API or migrate call sites to the
  builder modules
- keep `context_manager/__init__.py` as `ContextManager` plus intentional
  compatibility re-exports, then migrate private helper imports over time

## Phase-1 Safety Checks

Phase 1 should pass these context-focused tests:

- `scion/scion/tests/unit/test_research_surfaces_cvrp_context.py`
- `scion/scion/tests/unit/test_research_surfaces_generic_context.py`
- `scion/scion/tests/unit/test_agentic_session_tool_selection.py`

Recommended additional smoke coverage:

- `scion/scion/tests/unit/test_agentic_proposal_tools_context.py`
- `scion/scion/tests/unit/test_agentic_proposal_tools_feedback.py`
- `scion/scion/tests/unit/test_agentic_proposal_tools_solver_design.py`

## Phase-2 Safety Checks

Phase 2 should pass focused tests that exercise the compatibility facade and the
renderers moved into `feedback_memory.py`:

- `scion/scion/tests/unit/test_context_manager_modularization.py`
- `scion/scion/tests/test_sprint4_context.py`
- `scion/scion/tests/test_sprint_e2_guidance_history.py`
- `scion/scion/tests/test_sprint_e3_observability_feedback.py`
- `scion/scion/tests/test_sprint_e3_champion_baselines.py`
- `scion/scion/tests/unit/test_agentic_feedback_exposure.py`

The broader context smoke should still pass:

- `scion/scion/tests/unit/test_research_surfaces_cvrp_context.py`
- `scion/scion/tests/unit/test_research_surfaces_generic_context.py`

## Phase-3 Safety Checks

Phase 3 should pass focused package/facade tests:

- `scion/scion/tests/unit/test_context_manager_modularization.py`
- `scion/scion/tests/unit/test_research_surfaces_generic_context.py`

It should also pass the context smoke and feedback/tool-selection subsets used
for Phase 2:

- `scion/scion/tests/unit/test_research_surfaces_cvrp_context.py`
- `scion/scion/tests/test_sprint_e2_guidance_history.py`
- `scion/scion/tests/test_sprint_e3_observability_feedback.py`
- `scion/scion/tests/test_sprint_e3_champion_baselines.py`
- `scion/scion/tests/unit/test_agentic_feedback_exposure.py`
- `scion/scion/tests/unit/test_agentic_session_tool_selection.py`

## Remaining Debt After Package Migration

- Runtime feedback rendering now lives in
  `context_manager/runtime.py`. It is generic normalized feedback, but it
  remains large enough to deserve a separate exposure review if it grows.
- Objective steering and search-control guidance now live in
  `context_manager/guidance.py`. They are generic today, but should be split
  further only after confirming the adapter objective-policy boundary is
  sufficient.
- Historical direct imports from `scion.proposal.context_manager` remain as a
  compatibility surface. Later phases should either formalize these as facade
  exports or migrate call sites to explicit `scion.proposal.context` modules.
- Remaining large-file cleanup should move next to the P0 modules identified in
  the large-file modularization audit: protocol experiment orchestration,
  proposal pipeline, and telemetry guard.
