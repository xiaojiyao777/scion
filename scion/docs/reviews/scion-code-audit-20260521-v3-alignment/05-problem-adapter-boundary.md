# 05 - Problem Adapter Boundary

Audit focus: whether CVRP research-object semantics live under adapter/provider/problem layers, and whether those layers provide enough extension points to keep Scion generic.

## P0 Findings

No P0 finding is assigned to the CVRP package itself. The CVRP adapter exposes the right kinds of hooks; the P0 issue is that generic proposal/runtime code has not fully consumed those hooks and still duplicates CVRP content outside the problem package.

## P1 Findings

### P1-1: CVRP adapter exposes the right provider hooks, but generic code still bypasses them

- File paths:
  - `scion/scion/problems/cvrp/adapter.py:53`
  - `scion/scion/problems/cvrp/adapter.py:60`
  - `scion/scion/problems/cvrp/adapter.py:65`
  - `scion/scion/problems/cvrp/adapter.py:72`
  - `scion/scion/problems/cvrp/adapter.py:79`
  - `scion/scion/proposal/agentic_code_context.py:201`
  - `scion/scion/runtime/telemetry_guard/contract.py:99`

- Problem:
  `CvrpAdapter` provides mechanism novelty, contract check, solver-design prompt, active solver design, and smoke providers. Those are the correct v3 boundary points. However, generic proposal and telemetry code still embeds CVRP solver-design guidance and telemetry semantics.

- Why this violates or deviates from v3:
  The adapter boundary exists but is not the exclusive source of problem semantics. v3 requires CVRP facts to be adapter/provider-owned, not merely duplicated in both provider and generic code.

- Suggested fix:
  Convert the provider hooks from optional enhancements into the sole source for CVRP object-model, prompt guidance, solver-design telemetry roles, smoke diagnostics, and integration repair hints. Generic code should fail closed if an adapter-backed solver-design surface lacks the required provider method.

- Suggested tests:
  Add a test that temporarily uses a synthetic adapter with a different solver layout and proves generic proposal/contract/runtime behavior comes entirely from provider declarations.

### P1-2: `CvrpSolverDesignProvider` is taking on too many responsibilities

- File path:
  - `scion/scion/problems/cvrp/solver_design_provider.py`

- Problem:
  `CvrpSolverDesignProvider` is 872 lines and appears to cover prompt rules, API manifests, integration-file guidance, smoke diagnostics, low-effort diagnostics, and solver-design lifecycle knowledge.

- Why this violates or deviates from v3:
  The content belongs in the CVRP layer, so this is not a boundary leak by itself. But a large monolithic provider makes it harder to enforce which facts are prompt-only, which are contract-critical, which are telemetry declarations, and which are diagnostics. That increases the chance generic code will re-copy provider content.

- Suggested fix:
  Split into smaller provider-owned modules, for example:
  - `solver_design_prompt_guidance.py`
  - `solver_design_api_manifest.py`
  - `solver_design_smoke_diagnostics.py`
  - `solver_design_telemetry_declarations.py`
  - `solver_design_contract_guidance.py`

- Suggested tests:
  Keep existing CVRP provider tests but split them by provider role. Add one integration test that composes the provider facade and proves the public adapter API remains stable.

## P2 Findings

### P2-1: CVRP stagnation markers are adapter-owned, but should remain bounded and documented

- File path:
  - `scion/scion/problems/cvrp/adapter.py:101`

- Problem:
  `stagnation_object_model_markers` correctly puts CVRP object-model strings behind the adapter. These markers include `_solution`, `_route`, `from_public`, `from_cvrp_solution`, and object-model error phrases.

- Why this violates or deviates from v3:
  This is aligned with v3 as long as generic stagnation code only consumes adapter-provided markers. It becomes risky if generic code also hardcodes the same markers elsewhere.

- Suggested fix:
  Keep this hook provider-owned. Add comments or tests making it explicit that generic stagnation logic must not contain CVRP markers.

- Suggested tests:
  Add a generic stagnation detector test with a synthetic adapter marker set and assert detection uses only adapter-provided markers.

### P2-2: CVRP mechanism novelty implementation and tests are large enough to slow review and ownership

- File paths:
  - `scion/scion/problems/cvrp/mechanism_novelty/destroy_repair.py`
  - `scion/scion/tests/unit/test_cvrp_mechanism_novelty_provider.py`
  - `scion/scion/tests/unit/test_mechanism_novelty.py`

- Problem:
  `destroy_repair.py` is 861 lines. The CVRP mechanism novelty provider test is 1035 lines, and the generic mechanism novelty test is 915 lines.

- Why this violates or deviates from v3:
  v3 onboarding flags files above 800 lines as review debt and above 1000 lines as active debt. Large modules make it harder to verify that CVRP-only semantics stay inside CVRP layers and that generic novelty logic remains problem-independent.

- Suggested fix:
  Split CVRP mechanism novelty by operator family or signature layer. Split tests into provider-boundary, destroy/repair signature, route-state compatibility, and generic novelty behavior files.

- Suggested tests:
  Preserve current behavioral coverage after the split and add a boundary test that generic mechanism novelty fixtures do not require CVRP terms unless explicitly testing the CVRP provider.

