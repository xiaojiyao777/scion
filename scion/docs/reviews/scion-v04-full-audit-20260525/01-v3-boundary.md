# V3 Boundary And Problem Independence

Audit question: does Scion core remain problem-independent, and does CVRP/solver content stay in problem-owned providers?

## Finding V3-B1: generic Contract still knows CVRP active package paths

- Severity: P1 high.
- Evidence: `scion/scion/contract/gate.py::ContractGate._is_solver_design_patch_path` hardcodes `policies/baseline_algorithm.py`, `policies/solver_algorithm.py`, and `policies/baseline_modules/*.py`. `scion/scion/contract/checks/security.py::_context_baseline_call_violations_in_baseline_algorithm` hardcodes `policies/baseline_algorithm.py must not call context.baseline(...)`.
- V3 judgment: violates v3 boundary ownership. The framework may own "selected surface" and "editable target" governance, but active algorithm package paths and wrapper API rules are problem/surface-provider facts. Current code will bias any new problem toward the CVRP package layout.
- Suggested fix: add provider-facing hooks such as `is_algorithm_package_path`, `algorithm_entrypoints`, `support_module_globs`, and `forbidden_entrypoint_calls`. Have generic Contract consume those hooks. Keep `solver_design` as a generic surface kind only if it does not imply CVRP file paths.
- Suggested tests: extend `test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py` to reject CVRP package path strings in generic layers. Add CVRP provider tests proving the same paths and `context.baseline` rule are still enforced through `scion/problems/cvrp/contract_checks`.

## Finding V3-B2: legacy problem scale fallback leaks route/customer/vehicle terms

- Severity: P1 medium-high, because it is known legacy debt but remains in a hard gate.
- Evidence: `scion/scion/contract/gate.py::_LEGACY_PROBLEM_SCALE_NAMES` includes `routes`, `route`, `customers`, `customer_ids`, `orders`, `vehicles`, and `vehicle_ids`. The existing boundary sentinel explicitly allowlists this as legacy complexity scale debt.
- V3 judgment: partially violates v3. The comment explains it is for pre-v2 specs, but a generic Contract fallback still embeds CVRP/VRP-shaped scale terms.
- Suggested fix: remove the fallback after all active specs declare `bounds.complexity_scale_terms`; for missing metadata, emit a structured metadata error or use neutral abstract terms provided by the surface spec.
- Suggested tests: add a non-CVRP surface with declared scale terms and verify C9 complexity uses only those terms. Add a legacy/missing-metadata test documenting the intended failure or neutral fallback.

## Finding V3-B3: active solver map schema is problem-generic; CVRP facts are provider-owned

- Severity: OK, with modularity debt tracked elsewhere.
- Evidence: `scion/scion/proposal/active_solver_map/models.py::ActiveSolverMap` defines generic fields like `surface`, `subject_id`, `entrypoints`, `operator_registries`, `algorithm_slices`, `telemetry_fields`, and `known_mechanism_facts` with `extra="forbid"`. `scion/scion/problems/cvrp/active_solver_map_provider.py::CvrpActiveSolverMapProvider` owns CVRP identifiers such as `cvrp.solver_design.active_baseline`, `_ALNSVNSSolver`, and `policies/baseline_modules/*`.
- V3 judgment: conforms. Generic Scion carries schema, digest, and exposure control; CVRP fills problem-specific semantics in its provider package.
- Suggested fix: preserve this split while moving any remaining generic path checks into provider hooks. Split the CVRP provider into entrypoints, registries, slices, telemetry, and facts modules.
- Suggested tests: keep `test_active_solver_map.py` generic and `test_cvrp_active_solver_map_provider.py` problem-specific. Add a dummy non-CVRP provider fixture to prove the generic schema accepts another subject layout.

## Finding V3-B4: Decision input boundary is sound

- Severity: OK.
- Evidence: `scion/scion/core/features.py::SafeFeatureExtractor.extract` constructs `DecisionFeatures` from contract, verification, canary, protocol stats, runtime counters, and branch state. The implementation validates finite/statistical fields and keeps proposal text out of decision features.
- V3 judgment: conforms to the v3 "LLM is tainted, Decision reads only DecisionFeatures" rule.
- Suggested fix: keep `ProtocolResult.exposed_summary` prompt-facing only. Do not add free-text agent diagnosis or hypothesis text to `DecisionFeatures`.
- Suggested tests: add/keep a guard test that fails if `DecisionFeatures` gains free-text fields or if Decision reads raw proposal artifacts.

## Finding V3-B5: boundary sentinel exists but does not catch all current coupling

- Severity: P1 medium.
- Evidence: `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py` catches CVRP, ALNS/VNS, route/capacity/demand/customer/vehicle terms and some `solver_algorithm_*` fields. It does not currently fail on `policies/baseline_algorithm.py`, `policies/baseline_modules`, `policies/solver_algorithm.py`, or default `surface="solver_design"` assumptions.
- V3 judgment: the sentinel is valuable but incomplete for the current active package migration.
- Suggested fix: broaden the forbidden pattern list for generic layers and require narrow, dated allowlist entries for any temporary compatibility debt.
- Suggested tests: deliberately insert one forbidden active-package path in a generic test fixture and prove the sentinel reports it.

