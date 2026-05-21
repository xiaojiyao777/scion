# 06 - Tests and Maintainability

Audit focus: whether tests cover the v3 boundaries that matter most, and whether large modules are becoming maintenance risk.

## P0 Findings

### P0-1: No generic-boundary sentinel prevents CVRP semantics from re-entering core/proposal/contract/runtime

- File paths:
  - `scion/scion/proposal/agentic_code_context.py:40`
  - `scion/scion/proposal/engine/hypothesis_prompts.py:160`
  - `scion/scion/proposal/schemas.py:15`
  - `scion/scion/runtime/telemetry_guard/contract.py:99`
  - `scion/scion/runtime/audit.py:92`

- Problem:
  Existing tests cover many CVRP repair behaviors, active fact anchors, and provider mechanics, but there is no architectural sentinel test that fails when CVRP/ALNS/VNS/route/capacity semantics appear in generic Scion layers.

- Why this violates or deviates from v3:
  v3 boundary governance is an invariant, not a best-effort convention. Without a sentinel, future repair work can keep patching generic prompt/contract/runtime code with CVRP facts.

- Suggested fix:
  Add a `test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py` style test. Scan generic modules under `core`, `proposal`, `contract`, `runtime`, `protocol`, and `verification`, excluding explicit legacy allowlist files/strings if needed. Fail on CVRP-specific terms outside `scion/scion/problems/cvrp`.

- Suggested tests:
  Include forbidden terms for `CVRP`, `CvrpSolution`, `_ALNSVNSSolver`, `ALNS`, `VNS`, `route`, `capacity`, `demand`, `solver_algorithm_fleet_violation`, `solver_algorithm_total_distance`, and `from_cvrp_solution`. Keep the allowlist small and documented.

## P1 Findings

### P1-1: Missing end-to-end provider prompt plumbing test

- File paths:
  - `scion/scion/proposal/context_manager/manager.py:493`
  - `scion/scion/proposal/engine/solver_design_prompts.py:232`
  - `scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py:124`

- Problem:
  Current prompt payload tests assert CVRP strings in rendered output, but they do not prove the real `ContextManager` path passes provider guidance to the renderer.

- Why this violates or deviates from v3:
  v3 requires provider-owned problem facts. A test that manually injects provider-like context or asserts generic CVRP strings does not protect the real boundary.

- Suggested fix:
  Add an integration unit test from `ContextManager(adapter=CvrpAdapter)` through solver-design prompt rendering. Then rewrite existing prompt assertions so generic prompt tests check structure/bounds/provenance, while CVRP provider tests check CVRP content.

- Suggested tests:
  Use a synthetic provider with unique non-CVRP marker strings and assert they appear in rendered prompt output. Then assert CVRP strings appear only when `CvrpAdapter` is used.

### P1-2: Missing lifecycle tests for regressive mid-low screening candidates

- File paths:
  - `scion/scion/core/decision.py:101`
  - `scion/scion/core/branch_lifecycle_policy.py:105`
  - `scion/scion/core/decision_finalizer.py:301`

- Problem:
  Tests appear to cover low-win lifecycle behavior, but the current code leaves a gap for candidates with a nonzero but poor win rate, negative median delta, or runtime regression.

- Why this violates or deviates from v3:
  v3 branch lifecycle should preserve weak positive/mostly-tie branches but abandon or discard clearly regressive branches. The test matrix should encode that distinction.

- Suggested fix:
  Add decision and finalizer tests for mid-low win rate scenarios around `win_rate=0.4`.

- Suggested tests:
  Cover:
  - nonzero win rate plus negative median delta;
  - nonzero win rate plus runtime slowdown;
  - mostly ties with no losses and non-negative delta;
  - candidate failed pairs.

### P1-3: Missing tests for declared telemetry fields on non-CVRP surfaces

- File paths:
  - `scion/scion/runtime/telemetry_guard/contract.py:99`
  - `scion/scion/runtime/telemetry_guard/expected_schema.py:55`
  - `scion/scion/protocol/experiment/runtime_observation.py:17`

- Problem:
  Telemetry tests are currently anchored around the `solver_algorithm_*` convention. They do not prove that a new problem adapter can declare different telemetry fields and get equivalent validation, lifecycle, and runtime summaries.

- Why this violates or deviates from v3:
  v3 extension requires new problem adapters without changing generic runtime code.

- Suggested fix:
  Add a synthetic problem adapter and research surface with non-CVRP telemetry fields. Test expected telemetry validation, summary classification, runtime audit, and lifecycle feedback using those declared fields.

- Suggested tests:
  Assert that `expected_telemetry.activation` accepts the synthetic mechanism field, rejects synthetic objective fields, and does not require any `solver_algorithm_*` names.

### P1-4: Missing guard test for free-text decision fields

- File paths:
  - `scion/scion/core/models.py:341`
  - `scion/scion/core/features.py:116`
  - `scion/scion/core/features.py:186`

- Problem:
  `DecisionFeatures.statistical_metric` can carry arbitrary strings without validation.

- Why this violates or deviates from v3:
  DecisionFeatures should be deterministic and free of raw LLM/free-text content.

- Suggested fix:
  Constrain `statistical_metric` to an enum or declared objective id, or remove it from `DecisionFeatures`.

- Suggested tests:
  Add a feature extraction test with a malicious/free-text statistical metric and assert rejection or normalization.

## P2 Findings

### P2-1: Large production modules exceed the onboarding size thresholds

- File paths:
  - `scion/scion/proposal/llm_client.py` - 1240 lines.
  - `scion/scion/core/explore_step_pipeline.py` - 1122 lines.
  - `scion/scion/core/evidence_recorder.py` - 1021 lines.
  - `scion/scion/problems/cvrp/solver_design_provider.py` - 872 lines.
  - `scion/scion/problems/cvrp/mechanism_novelty/destroy_repair.py` - 861 lines.
  - `scion/scion/proposal/schemas.py` - 858 lines.
  - `scion/scion/contract/gate.py` - 855 lines.

- Problem:
  Several active modules are above the 800-line warning threshold, and three generic production modules are above 1000 lines.

- Why this violates or deviates from v3:
  `AGENT_ONBOARDING.md` treats >800 lines as warning debt and >1000 lines as active debt. Large files blur ownership boundaries and make v3 invariants harder to audit.

- Suggested fix:
  Split by role:
  - `llm_client.py`: backend transport, retry/timeout policy, response parsing, schema validation.
  - `explore_step_pipeline.py`: hypothesis, code generation, contract/verification, protocol/evidence orchestration.
  - `evidence_recorder.py`: status updates, lineage refs, public summaries, telemetry refs.
  - `solver_design_provider.py`: prompt guidance, API manifest, telemetry declarations, smoke diagnostics.
  - `schemas.py`: hypothesis schema, patch schema, telemetry schema.
  - `gate.py`: surface checks, import checks, telemetry checks, legacy compatibility.

- Suggested tests:
  Split tests only after adding characterization coverage around public functions. Keep behavior snapshots small and module-specific.

### P2-2: Large tests slow targeted boundary review

- File paths:
  - `scion/scion/tests/unit/test_cvrp_mechanism_novelty_provider.py` - 1035 lines.
  - `scion/scion/tests/unit/test_mechanism_novelty.py` - 915 lines.
  - `scion/scion/tests/unit/test_agentic_session_model_planner.py` - 872 lines.
  - `scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py` - 826 lines.

- Problem:
  Large tests mix multiple concerns and make it harder to see which boundary invariant is protected.

- Why this violates or deviates from v3:
  v3 relies on boundary tests being easy to locate and hard to accidentally weaken.

- Suggested fix:
  Split tests by invariant:
  - active fact anchor/provenance;
  - tool selection and allowed context;
  - provider prompt rendering;
  - contract C9e/C11 behavior;
  - telemetry declaration validation;
  - CVRP mechanism novelty signatures.

- Suggested tests:
  After splitting, add one index test or README in the test package mapping each v3 invariant to the file that protects it.

### P2-3: Selected-surface forwarding needs a fail-closed test

- File path:
  - `scion/scion/core/evaluation_pipeline.py:317`

- Problem:
  Evaluation forwarding can skip `selected_surface` if protocol metadata does not match the expected shape.

- Why this violates or deviates from v3:
  Surface selection is part of the problem-boundary safety contract for adapter-backed runs.

- Suggested fix:
  Add a protocol-shape test for adapter-backed problems where the method accepts `selected_surface` but protocol metadata is incomplete.

- Suggested tests:
  Assert the pipeline fails closed, or explicitly records a hard lifecycle/audit failure, rather than silently running without selected-surface forwarding.

