# 01 - v3 Boundary Governance

Audit focus: whether Scion core/proposal/contract/runtime remain problem-independent under the v3 blueprint, and whether CVRP research-object semantics are isolated to adapter/provider/problem layers.

## P0 Findings

### P0-1: CVRP solver-design semantics are still embedded in generic proposal/context code

- File paths:
  - `scion/scion/proposal/agentic_code_context.py:40`
  - `scion/scion/proposal/agentic_code_context.py:201`
  - `scion/scion/proposal/agentic_code_context.py:223`
  - `scion/scion/proposal/agentic_code_context.py:241`
  - `scion/scion/proposal/agentic_code_context.py:332`
  - `scion/scion/proposal/engine/hypothesis_prompts.py:160`
  - `scion/scion/proposal/schemas.py:15`

- Problem:
  Generic proposal modules contain ALNS/VNS terminology, `_ALNSVNSSolver`, `policies/baseline_modules`, `CvrpSolution`, `_Solution`, `_Route`, `context.nearest_neighbor`, route conversion rules, and CVRP-shaped telemetry examples such as `solver_algorithm_fleet_violation` and `solver_algorithm_total_distance`.

- Why this violates or deviates from v3:
  v3 defines Scion as a problem-independent governed autoresearch framework. `AGENT_ONBOARDING.md` is explicit that CVRP/ALNS/VNS/route/capacity/demand semantics belong in `scion/problems/cvrp` or provider hooks only. Generic proposal/context/schema code may define taint controls, exposure rules, tool contracts, and structured schemas, but should not know CVRP object-model or solver architecture facts.

- Suggested fix:
  Move the CVRP-specific scope rules, import rules, entrypoint rules, object-model guidance, target-module rules, and telemetry examples into `CvrpSolverDesignProvider` or smaller CVRP provider modules. Generic proposal code should request provider-rendered guidance through stable methods such as solver-design scope guidance, object-model constraints, target-file ownership guidance, and declared telemetry role examples.

- Suggested tests:
  Add a boundary sentinel test that scans generic `scion/scion/core`, `scion/scion/proposal`, `scion/scion/contract`, `scion/scion/runtime`, `scion/scion/protocol`, and `scion/scion/verification` modules for forbidden problem terms, with an explicit allowlist for compatibility aliases. At minimum forbid `CVRP`, `CvrpSolution`, `ALNS`, `VNS`, `_ALNSVNSSolver`, `route`, `capacity`, `demand`, `solver_algorithm_fleet_violation`, and `solver_algorithm_total_distance` outside `scion/scion/problems/cvrp`.

## P1 Findings

### P1-1: Solver-design provider prompt guidance is resolved but not passed to the renderer on the real context path

- File paths:
  - `scion/scion/proposal/context_manager/manager.py:493`
  - `scion/scion/proposal/context_manager/manager.py:498`
  - `scion/scion/proposal/context_manager/manager.py:504`
  - `scion/scion/proposal/engine/solver_design_prompts.py:232`

- Problem:
  `ContextManager.build_code_context` resolves `solver_design_prompt_provider` to build the API manifest and branch-current integration file summary. It does not store `solver_design_prompt_provider`, `problem_spec`, or `adapter` in the context passed to `solver_design_prompts._solver_design_prompt_provider`. The prompt renderer can only find a provider if one of those keys is already present.

- Why this violates or deviates from v3:
  v3 expects problem-owned facts and rules to enter proposal through declared adapter/provider boundaries. If the real context path does not carry the provider to the prompt renderer, the system is incentivized to duplicate CVRP instructions in generic prompt code, which is exactly the current P0 leakage.

- Suggested fix:
  Pass a non-serialized provider handle through the prompt-rendering path, or pass enough adapter/problem-spec metadata for `resolve_solver_design_prompt_provider` to work at render time. Keep cacheable prompt payloads deterministic by rendering provider output into bounded text blocks before final prompt materialization.

- Suggested tests:
  Add an integration test that builds a CVRP solver-design code context using `ContextManager(adapter=CvrpAdapter)` and renders the final solver-design prompt without manually injecting `problem_prompt_provider`. Assert that CVRP guidance appears only through provider-rendered blocks and that the generic renderer still works for a synthetic non-CVRP problem.

### P1-2: Generic runtime telemetry conventions still encode the active CVRP solver surface

- File paths:
  - `scion/scion/runtime/telemetry_guard/contract.py:99`
  - `scion/scion/runtime/telemetry_guard/expected_schema.py:55`
  - `scion/scion/runtime/telemetry_guard/summary.py:318`
  - `scion/scion/runtime/audit.py:92`
  - `scion/scion/protocol/experiment/runtime_observation.py:17`

- Problem:
  Generic runtime/telemetry modules know `solver_algorithm_*` field names and classify specific fields such as fleet violation, total distance, solution routes, context records, phase runtime, and improving moves.

- Why this violates or deviates from v3:
  Field names, objective semantics, and protected-outcome roles are problem/surface declarations. Generic runtime code may validate that declared fields exist, are finite, are bounded, and are categorized consistently. It should not hardcode CVRP solver-design telemetry names.

- Suggested fix:
  Move telemetry field-role declarations to research-surface metadata or problem providers. Generic telemetry guard code should consume declared roles like `objective_outcome`, `mechanism_activity`, `mechanism_activation`, and `budget`, not hardcoded names.

- Suggested tests:
  Add a synthetic problem adapter with non-CVRP runtime fields and verify that telemetry contract validation, summary classification, and audit summaries work without any `solver_algorithm_*` names.

## P2 Findings

### P2-1: Legacy vehicle/order solution fallbacks remain in generic verification/runtime

- File paths:
  - `scion/scion/verification/state_mutation.py:1`
  - `scion/scion/verification/state_mutation.py:90`
  - `scion/scion/verification/state_mutation.py:166`
  - `scion/scion/core/models.py:439`

- Problem:
  Generic verification still contains legacy vehicle/order/assignment solution consistency logic, and `SolverOutput` carries `vehicles` and `assignment`.

- Why this violates or deviates from v3:
  The code is partly protected by adapter-required checks, so this is not a current P0 for adapter-backed problems. It remains boundary debt because new problem authors can still see non-generic logistics assumptions in generic verification/runtime models.

- Suggested fix:
  Move the legacy fallback and legacy output shape to a clearly named compatibility module, and make adapter-backed problem specs fail closed before reaching vehicle/order assumptions.

- Suggested tests:
  Add a new adapter-backed synthetic problem test showing that no legacy solution consistency fallback is used when an adapter is required. Keep a separate legacy compatibility test for pre-v2 specs.

### P2-2: Contract gate still contains legacy problem-scale names and solver-design patch-path aliases

- File paths:
  - `scion/scion/contract/gate.py:59`
  - `scion/scion/contract/gate.py:814`

- Problem:
  `ContractGate` keeps legacy scale names such as routes, customers, orders, and vehicles. It also treats `policies/baseline_algorithm.py`, `policies/solver_algorithm.py`, and `policies/baseline_modules/*.py` as solver-design patch paths.

- Why this violates or deviates from v3:
  The file comments identify the scale names as legacy fallbacks, and surface lookup mitigates the path issue. Still, generic contract code should ultimately derive solver-design editability and complexity scale terms from problem specs/surfaces rather than carrying CVRP-era path conventions.

- Suggested fix:
  Retain the aliases only behind an explicit legacy compatibility branch. For active v3 surfaces, use `surface_access.surface_for_patch_path` and declared `bounds.complexity_scale_terms` exclusively.

- Suggested tests:
  Add one test proving a non-CVRP solver-design surface can declare different paths and scale terms without relying on the legacy names, and one legacy test preserving compatibility where needed.

