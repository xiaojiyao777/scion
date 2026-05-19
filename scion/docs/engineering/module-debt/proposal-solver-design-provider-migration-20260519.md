# Proposal Solver-Design Provider Migration 2026-05-19

## Boundary Target

Architecture v3 keeps generic `proposal` responsible for Creative Layer prompt
assembly, proposal-tool orchestration, provider dispatch, schema checks, taint
labels, and bounded audit aggregation. Problem packages own solver semantics:
object models, active algorithm paths, runtime smoke interpretation, prompt
guidance, telemetry field meanings, and problem-specific repair hints.

For CVRP this means terms such as ALNS/VNS, `_ALNSVNSSolver`, `_Solution`,
`_Route`, `policies/baseline_algorithm.py`, `policies/baseline_modules/*`, and
`solver_algorithm_*` evidence meanings should come from `scion/problems/cvrp/`
or a problem-owned provider hook, not from generic `scion/proposal`.

## Active Solver-Design Object

For CVRP solver-design, the active research object is
`policies/baseline_algorithm.py` plus `policies/baseline_modules/*`.
`policies/baseline_algorithm.py` is the stable entrypoint, and focused modules
under `policies/baseline_modules/` own construction, destroy/repair, local
search, acceptance, scheduling, and telemetry mechanisms.

Legacy surfaces are no longer optimization directions. This includes
`policies/solver_algorithm.py`, `main_search_strategy`, `algorithm_blueprint`,
operator surfaces, and older component-policy surfaces. They may appear in
compatibility, diagnostics, or historical context, but proposal/provider prompts
must not recommend them as candidate solver-design research paths.

## First Slice Implemented

Added `scion.problem.providers` as a small generic resolver. It can find optional
solver-design prompt and smoke providers directly from an adapter, from a
problem spec factory, or by instantiating the declared problem adapter import
path. It does not import CVRP or define CVRP behavior.

Added `scion.problems.cvrp.solver_design_provider.CvrpSolverDesignProvider`.
The provider now owns:

- CVRP solver-design hypothesis prompt guidance.
- CVRP active solver-design package guidance:
  `policies/baseline_algorithm.py` plus `policies/baseline_modules/*`.
- CVRP legacy-surface demotion for `policies/solver_algorithm.py`,
  `main_search_strategy`, `algorithm_blueprint`, operator surfaces, and old
  component-policy surfaces.
- CVRP code prompt rules for `_ALNSVNSSolver`, module ownership, support module
  wiring, object-model constraints, and telemetry expectations.
- CVRP compact-scope guidance and broad-term detection.
- CVRP algorithm-smoke runtime patch path recognition.
- CVRP zero-effort and low-effort smoke interpretation.
- CVRP runtime-error repair guidance for `_Solution`, `_Route`, and instance
  distance/object-model mistakes.

`CvrpAdapter` registers the provider through `solver_design_prompt_provider()`
and `solver_design_smoke_provider()`. This is intentionally a narrow
registration-only edit; adapter internals were not otherwise moved in this
slice.

`scion.proposal.engine` now dispatches solver-design prompt sections through the
optional prompt provider. Its fallback text is problem-agnostic and no longer
mentions CVRP, ALNS/VNS, `_ALNSVNSSolver`, `_Solution`, `_Route`, or concrete
CVRP policy paths.

`scion.proposal.solver_design_smoke` now dispatches runtime patch recognition,
search-effort claims, zero/low-effort issue text, and runtime repair guidance
through the smoke provider. The generic layer still assembles the tainted smoke
payload and preserves audit/result compaction.

## Not Migrated Yet

The full runtime smoke runner still lives in `scion/proposal/solver_design_smoke.py`.
It still handles temporary workspaces, subprocess execution, active split/seed
selection, safe data root resolution, and case provenance payloads.

`solver_algorithm_*` compact runtime payload fields are still listed in
`solver_design_smoke.py` for the tainted smoke result shape. Those should move
behind a telemetry/smoke provider once protocol/runtime telemetry is
surface-schema driven.

`proposal/context_manager.py` still builds solver-design API manifests and
branch-current integration-file context directly. That is Planck's area during
this cleanup and was intentionally not modified here.

CVRP adapter prompt rendering remains in `CvrpAdapter`; this slice only added
provider registration and a new provider module. Future adapter modularization
should move rendering and surface artifacts into CVRP-owned provider files.

Active surface filtering is still a separate adapter/context concern and was
not changed in this proposal/provider slice. Dirac owns follow-up filtering if
legacy surfaces need to disappear from adapter-provided inventories.

## Next Phase

1. Move safe-data-root and case manifest resolution from
   `proposal/solver_design_smoke.py` into a CVRP smoke provider, returning only
   bounded path provenance to proposal.
2. Move the CVRP subprocess smoke runner under `problems/cvrp/smoke/` and make
   `proposal.algorithm_smoke` call `run_algorithm_smoke(...)` through a provider.
3. Thread `solver_design_prompt_provider` into context construction instead of
   relying on callers to include `adapter` or `problem_prompt_provider` in prompt
   contexts.
4. Move remaining solver-design support artifact/API manifest assembly out of
   context-manager code into a problem-owned surface artifact provider.
5. Replace hard-coded `solver_algorithm_*` smoke compaction fields with
   provider-declared telemetry groups.

## Verification

Focused verification for this slice should include:

- `python -m compileall -q scion/scion/problem/providers.py scion/scion/problems/cvrp/solver_design_provider.py scion/scion/proposal/engine.py scion/scion/proposal/solver_design_smoke.py`
- `python -m pytest scion/scion/tests/unit/test_cvrp_solver_design_provider.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py scion/scion/tests/unit/test_agentic_solver_design_smoke_diagnostics.py scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py scion/scion/tests/unit/test_research_surfaces_cvrp_context.py -q`
- `git diff --check`
