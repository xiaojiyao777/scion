# Context Manager Modularization Design

*Date: 2026-05-19*
*Status: Design plus phase-1 no-behavior extraction*
*Scope: `scion/scion/proposal/context_manager.py` and proposal context builders*
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

The module also exposes historical helper functions used by tests, tools, and
campaign services. These are not ideal public API, but they are currently
imported directly and must remain available through `context_manager.py` during
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

Phase 1 preserves these imports by re-exporting moved helpers from
`context_manager.py`.

The intended facade contract after modularization is:

- external callers instantiate `ContextManager(adapter=...)`
- external callers keep using `build_hypothesis_context`,
  `build_code_context`, and `build_fix_context`
- historical helper imports from `scion.proposal.context_manager` remain
  compatibility re-exports until call sites migrate
- new implementation modules live under `scion.proposal.context_builders`
  and are internal unless a helper is explicitly promoted to a documented API

## Current Responsibilities

`context_manager.py` currently mixes five responsibilities:

- active solver context: active problem-boundary selection, solver-design
  manifest rendering, branch-current integration file summaries, and active
  target expansion
- research surface rendering: surface list filtering, metadata rendering,
  forced-surface prompt constraints, novelty signature summaries, target/action
  permission text, and inactive legacy-surface warnings
- feedback and memory exposure: screening-only experiment history, case
  feedback, pattern summaries, champion baseline hints, runtime feedback,
  proposal-only quality blocks, search memory, research log, saturation, and
  weight feedback
- budget and compaction context: APS observation budgets, compact tool payload
  expectations, terminal preview reserves, and text-size controls currently
  spread across proposal tools and session modules
- problem adapter hooks: problem summary, problem object, solver mechanics,
  operator/research-surface interface rendering, objective policy rendering,
  and adapter/spec selection

This makes the file hard to review for exposure safety: problem-independent
context protocol code, problem-owned metadata rendering, proposal feedback
policy, and active solver diagnostics all live in one namespace.

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

Known debt remains in solver-design context rendering where framework code still
contains CVRP package file paths and target-specific guidance. That should move
behind adapter/problem-package hooks in a later phase; phase 1 does not change
behavior.

## Dependency Direction

Allowed dependency direction:

```text
core/proposal pipeline
  -> ContextManager facade
     -> context_builders.*
        -> generic core dataclasses / generic ProblemSpec / generic surface utils
        -> adapter/provider protocol calls
           -> problem package implementation
```

Disallowed dependency direction:

```text
context_builders.* -> scion.problems.cvrp.*
context_builders.* -> problem-owned solver modules
context_builders.* -> concrete campaign artifacts outside supplied inputs
problem package -> ContextManager internals
Decision/core protocol -> proposal-context free text
```

Builder import rules:

- `problem_adapter.py` may call adapter methods by protocol/duck typing, but it
  must not import any concrete adapter implementation.
- `research_surfaces.py` may read declared research-surface metadata and generic
  `core.forced_surface` helpers. It must not infer domain behavior from surface
  names beyond generic kinds/roles such as `solver_design`.
- future `active_solver.py` may render active algorithm context only from
  declared surfaces, branch/champion inputs, and adapter/provider hooks. Any
  problem-specific file map or target guidance must be provider-owned.
- future `feedback_memory.py` may read framework `StepRecord` and
  screening-stage normalized feedback. It must not expose validation/frozen
  per-case detail or raw metrics refs.
- future `budget_compaction.py` may define generic text/observation budgets and
  compaction policies. It must not make problem-quality decisions.

Proposal tools may temporarily import compatibility helpers from
`context_manager.py`, but new shared context logic should live in
`context_builders` and flow through the facade or explicit internal imports.

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

The context builder package should be split by ownership:

- `context_builders/problem_adapter.py`
  Adapter/spec hook calls and legacy generic fallbacks. This owns
  `render_problem_summary`, `render_problem_object`, `render_solver_mechanics`,
  and active research-surface interface rendering.

- `context_builders/research_surfaces.py`
  Problem-declared research-surface rendering and generic selection helpers:
  surface metadata, target/action permissions, novelty signature instructions,
  inactive legacy-surface exclusion, solver-design surface name detection by
  generic kind/role, and concrete target-file expansion helpers that do not read
  problem semantics.

- `context_builders/active_solver.py`
  Active solver/algorithm-object context. This should eventually own solver
  design manifests, branch-current integration summaries, active algorithm file
  listings, and call-graph/read helpers. Problem-specific algorithm file maps or
  target guidance must come from adapter hooks, not framework constants.

- `context_builders/feedback_memory.py`
  Screening-only history rendering, case feedback, pattern summary,
  proposal-only quality feedback, memory/research-log/saturation/weight
  exposure, and validation/frozen redaction policy.

- `context_builders/budget_compaction.py`
  Prompt/tool observation text budgets, compact renderers, terminal reserve
  helpers, and budget denial summaries. This module should share policy with
  APS session/tool code instead of duplicating limits.

`context_manager.py` should become a small orchestration facade: collect inputs,
call the builder modules, and return the same context dictionaries.

## Phase Plan

Phase 1, implemented with this design:

- add the `context_builders` package
- move pure research-surface rendering and generic adapter-hook helpers
- keep all helper names available from `context_manager.py`
- avoid behavioral changes and avoid edits to proposal preview or contract gate
  files

Phase 2:

- move screening feedback and memory exposure into `feedback_memory.py`
- add focused tests proving validation/frozen per-case feedback remains absent
- make `ContextManager.build_hypothesis_context` read like an orchestration
  sequence instead of a monolithic builder

Phase 3:

- move active solver-design context into `active_solver.py`
- replace framework-owned CVRP file maps and target-specific strings with
  adapter/problem-package hooks
- add generic tests using a non-CVRP problem spec to prove no domain nouns are
  emitted unless the adapter provides them

Phase 4:

- centralize APS/context budget and compaction policy
- keep proposal tools and prompt builders on the same compact rendering rules
- add regression tests for observation budget reserve behavior

Phase 5:

- evaluate direct imports of private helpers from other modules
- either formalize a small compatibility API or migrate call sites to the
  builder modules
- reduce `context_manager.py` to `ContextManager` plus intentional re-exports

## Phase-1 Safety Checks

Phase 1 should pass these context-focused tests:

- `scion/scion/tests/unit/test_research_surfaces_cvrp_context.py`
- `scion/scion/tests/unit/test_research_surfaces_generic_context.py`
- `scion/scion/tests/unit/test_agentic_session_tool_selection.py`

Recommended additional smoke coverage:

- `scion/scion/tests/unit/test_agentic_proposal_tools_context.py`
- `scion/scion/tests/unit/test_agentic_proposal_tools_feedback.py`
- `scion/scion/tests/unit/test_agentic_proposal_tools_solver_design.py`
