# Scion v3 Alignment Code Audit - 2026-05-21

Scope: current workspace at commit `4cf0e80 Repair solver-design contract and telemetry guidance`.

Baseline documents read first:

- `scion/design/scion-architecture-v3.md`
- `scion/docs/AGENT_ONBOARDING.md`
- `scion/docs/experiments/v0.4/v0.4-p0-c9e-c11-premise-repair-20260521.md`

Constraints observed: this audit only reads design/engineering docs, code, and tests. It does not run experiments, does not inspect raw LLM traces or raw experiment data, and does not modify production or test code.

## Documents

- `01-v3-boundary-governance.md`: v3 blueprint and generic-core boundary findings.
- `02-agentic-proposal-context-tools.md`: agentic proposal, context, tools, and prompt-grounding findings.
- `03-contract-telemetry-gates.md`: contract gates, telemetry validation, and deterministic decision-surface findings.
- `04-branch-lifecycle-evaluation.md`: branch lifecycle, scheduling, evaluation forwarding, and workspace retention findings.
- `05-problem-adapter-boundary.md`: CVRP adapter/provider boundary and problem-owned implementation findings.
- `06-tests-maintainability.md`: test coverage, boundary sentinels, and large-file/module debt findings.

## Highest-Priority Conclusion

The largest remaining v3 misalignment is still semantic leakage from the CVRP solver-design research object into generic Scion layers. The clearest P0 examples are in generic proposal/prompt/schema code, especially `scion/scion/proposal/agentic_code_context.py`, `scion/scion/proposal/engine/hypothesis_prompts.py`, and `scion/scion/proposal/schemas.py`. They encode ALNS/VNS, `_ALNSVNSSolver`, route/capacity, CVRP object-model, and `solver_algorithm_*` telemetry semantics directly in generic proposal surfaces. That violates the v3 rule that Scion core/proposal/contract are problem-independent and that CVRP content belongs only in adapter/provider/problem packages.

The recent C9e/C11 repairs are directionally correct: problem-owned contract dispatch exists and CVRP provider hooks are present. However, provider-specific solver-design prompt guidance is not fully wired through the real context manager path, so generic proposal code still carries CVRP-specific prompt rules as a substitute.

## Must Fix Before More Experiments

1. Move CVRP solver-design prompt/context rules out of generic proposal modules.
   - Affected: `proposal/agentic_code_context.py`, `proposal/engine/hypothesis_prompts.py`, `proposal/schemas.py`.
   - Owner should be `scion/scion/problems/cvrp/solver_design_provider.py` or smaller provider modules under `scion/scion/problems/cvrp/`.
   - Add a generic-boundary sentinel test that fails if `CVRP`, `ALNS`, `VNS`, `_ALNSVNSSolver`, route/capacity object-model terms, or CVRP telemetry fields appear in generic core/proposal/contract/runtime modules outside an explicit allowlist.

2. Wire solver-design prompt providers through the real code-context path.
   - Affected: `proposal/context_manager/manager.py`, `proposal/engine/solver_design_prompts.py`.
   - The context manager resolves the provider to build manifests but does not pass `solver_design_prompt_provider`, `problem_spec`, or `adapter` into the context consumed by the prompt renderer.
   - Add an integration test from `ContextManager(adapter=CvrpAdapter)` to solver-design prompt rendering that proves CVRP guidance comes from the provider, not hardcoded generic strings.

3. Move generic telemetry guard semantics from hardcoded `solver_algorithm_*` fields to declared surface/provider metadata.
   - Affected: `runtime/telemetry_guard/contract.py`, `runtime/telemetry_guard/expected_schema.py`, `runtime/telemetry_guard/summary.py`, `runtime/audit.py`, `protocol/experiment/runtime_observation.py`.
   - Formal telemetry categories should validate declared runtime fields and field roles; generic code should not know CVRP objective or route fields.

4. Tighten branch lifecycle for regressive screening branches.
   - Affected: `core/decision.py`, `core/branch_lifecycle_policy.py`, `core/decision_finalizer.py`.
   - Current logic can keep exploring and preserve workspaces for low-to-mid win-rate candidates with negative median delta because only `win_rate < 0.3` enters the soft-abandon policy and any `win_rate > 0` preserves workspace.
   - Add tests for `win_rate=0.4`, negative median delta, losses/runtime slowdown, and weak-positive mostly-tie cases.

5. Reconsider validation-stage telemetry failures.
   - Affected: `core/telemetry_validation.py`, `core/decision.py`.
   - Validation telemetry guard failures are currently classified as repairable and preempt normal validation decisions into `CONTINUE_EXPLORE`. If validation is a formal gate, this should either fail closed or enter a distinct retry/repair lifecycle that cannot masquerade as an ordinary exploratory continuation.

## Can Optimize After Blocking Fixes

- Split large active files:
  - `scion/scion/proposal/llm_client.py` - 1240 lines.
  - `scion/scion/core/explore_step_pipeline.py` - 1122 lines.
  - `scion/scion/core/evidence_recorder.py` - 1021 lines.
  - `scion/scion/problems/cvrp/solver_design_provider.py` - 872 lines.
  - `scion/scion/problems/cvrp/mechanism_novelty/destroy_repair.py` - 861 lines.
  - `scion/scion/proposal/schemas.py` - 858 lines.
  - `scion/scion/contract/gate.py` - 855 lines.

- Split large tests:
  - `scion/scion/tests/unit/test_cvrp_mechanism_novelty_provider.py` - 1035 lines.
  - `scion/scion/tests/unit/test_mechanism_novelty.py` - 915 lines.
  - `scion/scion/tests/unit/test_agentic_session_model_planner.py` - 872 lines.
  - `scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py` - 826 lines.

- Isolate legacy non-adapter solution/scale fallbacks behind a legacy module or explicit compatibility layer, since new adapter-backed problems should not inherit vehicle/order/route assumptions from generic verification/runtime code.

