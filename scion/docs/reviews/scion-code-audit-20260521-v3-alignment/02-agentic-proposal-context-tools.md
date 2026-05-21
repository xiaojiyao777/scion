# 02 - Agentic Proposal, Context, and Tools

Audit focus: whether agentic proposal generation uses tool-mediated, bounded, cache-friendly, branch-current context while keeping problem facts adapter-owned.

## P0 Findings

### P0-1: APS code-scope control has problem-specific solver architecture baked into generic context assembly

- File paths:
  - `scion/scion/proposal/agentic_code_context.py:40`
  - `scion/scion/proposal/agentic_code_context.py:201`
  - `scion/scion/proposal/agentic_code_context.py:223`
  - `scion/scion/proposal/agentic_code_context.py:241`
  - `scion/scion/proposal/agentic_code_context.py:332`

- Problem:
  The generic agentic code context detects broad terms such as ALNS/VNS, then emits CVRP-specific implementation instructions about `_ALNSVNSSolver`, scheduler constructor arguments, `baseline_algorithm.py`, `baseline_modules`, `_Solution`, `_Route`, `context.make_solution`, and target modules such as `destroy_repair.py`, `local_search.py`, and `construction.py`.

- Why this violates or deviates from v3:
  v3 allows generic proposal code to control exposure and enforce structured, bounded context. It does not allow proposal to define a problem's solver object model. Those facts are CVRP active algorithm facts and provider-owned code rules.

- Suggested fix:
  Replace hardcoded CVRP logic with a provider-returned `SolverDesignCodeGuidance` payload. The generic APS layer should merge bounded provider guidance into the prompt/tool context, preserving provenance and digest fields. CVRP can then own ALNS/VNS rules in `scion/scion/problems/cvrp/solver_design_provider.py` or smaller modules.

- Suggested tests:
  Add a generic APS rendering test using a synthetic solver-design provider that returns fake path/object-model rules, and assert those rules appear. Add a negative test that generic APS rendering without the CVRP provider contains no CVRP terms.

## P1 Findings

### P1-1: Real prompt-provider plumbing is incomplete

- File paths:
  - `scion/scion/proposal/context_manager/manager.py:493`
  - `scion/scion/proposal/context_manager/manager.py:498`
  - `scion/scion/proposal/context_manager/manager.py:504`
  - `scion/scion/proposal/engine/solver_design_prompts.py:232`

- Problem:
  The context manager resolves the CVRP prompt provider only for manifests and integration file summaries. The final prompt renderer searches the context for `solver_design_prompt_provider`, `problem_prompt_provider`, `prompt_provider`, `problem_spec`, or `adapter`, but the manager does not add any of these keys in this code path.

- Why this violates or deviates from v3:
  Agentic proposal should be grounded by adapter/provider context. If the real final prompt cannot reach the provider, context fidelity depends on generic fallbacks and test-only injection, not the v3 provider boundary.

- Suggested fix:
  Thread provider identity through the prompt-rendering call path in a way that does not serialize live objects into persisted context artifacts. One clean option is to render provider guidance during context construction into bounded, named prompt sections and pass only those rendered sections downstream.

- Suggested tests:
  Add an end-to-end unit test that starts at `ContextManager.build_code_context` with a CVRP adapter, renders a solver-design code prompt, and asserts provider-specific guidance appears. Add a synthetic adapter test to prove the same path is not CVRP-specific.

### P1-2: Tests currently lock in CVRP strings in generic solver-design prompts

- File path:
  - `scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py:124`

- Problem:
  The test asserts `_ALNSVNSSolver`, scheduler/class APIs, `_Solution`, `from_cvrp_solution`, and `context.make_solution(solution.routes_as_tuples())` in rendered generic solver-design prompt output.

- Why this violates or deviates from v3:
  Tests are part of architecture governance. These assertions preserve the exact boundary violation that v3 is trying to remove: CVRP object-model details in generic prompt rendering.

- Suggested fix:
  Move CVRP-specific prompt assertions to CVRP provider tests. Rewrite generic solver-design prompt tests to assert that provider-rendered blocks are included, bounded, and provenance-labeled, without asserting CVRP-specific content.

- Suggested tests:
  Add two tests: one generic synthetic-provider prompt test and one CVRP-provider prompt test. The generic test should fail if `_ALNSVNSSolver`, `CvrpSolution`, `ALNS`, or `VNS` appears without a CVRP provider.

### P1-3: Active solver facts are mostly branch-current, but the provider boundary should be the only source of algorithm facts

- File paths:
  - `scion/scion/proposal/active_solver_snapshot.py:195`
  - `scion/scion/proposal/active_solver_snapshot.py:279`
  - `scion/scion/proposal/agentic_code_context.py:201`

- Problem:
  `active_solver_snapshot.active_solver_source_root` correctly prefers branch workspace over champion snapshot, and `_algorithm_file_manifest` delegates file manifest construction to the active solver provider. However, generic `agentic_code_context.py` still injects solver facts independently of the provider.

- Why this violates or deviates from v3:
  Branch-current active algorithm facts are a v3 requirement, and this path is partially compliant. The remaining issue is that generic code and provider facts can diverge, causing stale or contradictory context.

- Suggested fix:
  Make the active solver provider the single source for algorithm object-model, import, entrypoint, and target-module guidance. Generic proposal should only attach provenance, digest, truncation, and exposure metadata.

- Suggested tests:
  Add a test that mutates a branch-workspace solver-design file and verifies the provider-sourced digest/provenance and rendered guidance both reflect the branch workspace, not champion or generic fallback strings.

## P2 Findings

### P2-1: Context truncation and cache friendliness are directionally good, but provider-rendered blocks need explicit budgets

- File paths:
  - `scion/scion/proposal/engine/solver_design_prompts.py:232`
  - `scion/scion/proposal/agentic_code_context.py:48`

- Problem:
  Tool observations are sanitized and compacted, and solver-design prompts already use bounded sections. Once CVRP guidance moves to providers, those provider-rendered blocks need the same explicit character budgets and digest/provenance metadata.

- Why this violates or deviates from v3:
  v3's context manager requires exposure control and cache friendliness. Moving content to providers fixes boundary leakage only if provider output remains bounded and stable.

- Suggested fix:
  Define provider output schemas with section names, max characters, digest, source root, and truncation flags. Make the generic renderer reject or truncate oversized provider sections deterministically.

- Suggested tests:
  Add provider-output truncation tests for long API manifests, integration files, and object-model guidance, including stable digest assertions.

