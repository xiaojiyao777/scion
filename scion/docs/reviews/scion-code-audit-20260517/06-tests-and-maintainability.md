# 06 - Tests And Maintainability

## Findings

### F-14 - Critical boundary rules are split across prompts, adapter preview, APS smoke, and core gates

- Severity: Medium
- Files:
  - `scion/scion/problems/cvrp/problem-v1.yaml:961`
  - `scion/scion/problems/cvrp/adapter.py:1247`
  - `scion/scion/proposal/solver_design_smoke.py:57`
  - `scion/scion/contract/gate.py:699`
  - `scion/scion/core/explore_step_pipeline.py:316`
- Problem: Some of the strongest solver-design rules are not enforced in the same layer. For example, the preferred-target `context.baseline` rule is in prompt text and adapter preview, while the core ContractGate accepts it. The `solver_algorithm` alias is recognized by ContractGate but not by smoke/runtime audit.
- Trigger path: Any path that does not run APS algorithm smoke/problem preview, or any path that uses a compatibility alias, sees a different contract than the prompt says.
- Impact: This makes regressions likely because tests can pass in one layer while another layer remains fail-open. It also makes review harder because the authoritative rule is not obvious.
- Suggested fix: Define surface invariants once as executable contract hooks. Prompts should describe those rules, but ContractGate/Verification/Protocol should enforce them. Add cross-layer tests for every declared solver-design invariant.

### F-15 - Large files concentrate unrelated responsibilities

- Severity: Low
- Files:
  - `scion/scion/problems/cvrp/solver.py:1` (9340 lines)
  - `scion/scion/proposal/tools.py:1` (4492 lines)
  - `scion/scion/proposal/agentic_session.py:1` (3994 lines)
  - `scion/scion/problems/cvrp/adapter.py:1` (3363 lines)
  - `scion/scion/contract/gate.py:1` (2576 lines)
  - `scion/scion/protocol/experiment.py:1` (1778 lines)
- Problem: Runtime loading, audit telemetry, adapter preview, smoke, tool schemas, prompt summaries, and static contracts are concentrated in very large modules.
- Trigger path: Adding a solver-design rule usually requires touching multiple large files and prompt strings. This increases the chance that a rule is added to APS preview but not ContractGate, or to runtime audit but not feedback summaries.
- Impact: The current code still works, but maintenance risk is high as v0.4 adds more problem-object boundaries and repair loops.
- Suggested fix: Split by executable boundary: `solver_design_contract.py`, `solver_design_runtime_audit.py`, `proposal_surface_reader.py`, `algorithm_smoke_runtime.py`, and `protocol_runtime_observation.py`. Keep prompt text generated from the same metadata where possible.

### F-16 - Missing regression tests for the strongest bypasses

- Severity: Medium
- Files:
  - `scion/scion/tests/test_contract.py:477`
  - `scion/scion/tests/unit/test_research_surfaces_solver_design_integration.py:149`
  - `scion/scion/tests/unit/test_agentic_proposal_tools_solver_design.py:634`
- Problem: Existing tests cover direct sensitive calls, many C9e integration paths, and APS smoke rejection of a preferred baseline wrapper. They do not cover the bypasses found in this audit.
- Trigger path: The current suite can pass while:
  - `__import__("os").system(...)` passes C9.
  - `unused = helper` passes C9e reachability.
  - `repr(instance)` bypasses C9d.
  - Core ContractGate accepts `baseline_algorithm.py` calling `context.baseline`.
  - `context.read_surface` returns champion code when branch workspace differs.
  - Champion-side Protocol failure branches skip progress emission.
- Impact: These regressions can remain invisible until a real campaign hits them.
- Suggested fix: Add focused unit tests for each bypass. Keep them short and layer-specific so failures point to the boundary that owns the rule.

## Suggested Test Additions

- `test_contract_rejects_dynamic_sensitive_imports`
- `test_contract_rejects_context_baseline_in_preferred_baseline_algorithm`
- `test_solver_design_integration_rejects_dead_helper_reference`
- `test_surface_instance_identity_rejects_repr_vars_dunder_dict`
- `test_read_surface_uses_branch_workspace_before_champion`
- `test_solver_algorithm_alias_normalized_for_smoke_and_runtime_audit`
- `test_protocol_emits_progress_after_champion_process_failure`
- `test_protocol_observation_includes_solver_algorithm_stop_reason`

## Maintenance Notes

- Prompt strings in `problem-v1.yaml`, `adapter.py`, `engine.py`, and `agentic_code_context.py` repeat similar solver-design instructions. This should be generated or at least smoke-tested against a shared invariant list.
- Runtime telemetry is spread between `solver.py`, `runtime/audit.py`, `protocol/experiment.py`, APS feedback tools, and evidence recorder summaries. A single typed solver-design telemetry schema would reduce drift.
- Experiment status/summary are good enough for recent runs, but final exit status for ad-hoc launch scripts remains best-effort outside repo-managed status reporting.

