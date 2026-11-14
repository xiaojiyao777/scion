# 03 - Contract, Telemetry, and Gates

Audit focus: whether contract gates and telemetry validation implement v3 deterministic gates without problem-specific leakage or lifecycle ambiguity.

## P0 Findings

### P0-1: Generic telemetry contract classifies CVRP solver outcome fields directly

- File paths:
  - `scion/scion/runtime/telemetry_guard/contract.py:99`
  - `scion/scion/runtime/telemetry_guard/expected_schema.py:55`
  - `scion/scion/runtime/telemetry_guard/summary.py:318`
  - `scion/scion/proposal/schemas.py:15`
  - `scion/scion/proposal/engine/hypothesis_prompts.py:160`

- Problem:
  Generic telemetry schema and guard code contains exact CVRP solver-design field names and phase examples, including `solver_algorithm_fleet_violation`, `solver_algorithm_total_distance`, `solver_algorithm_solution_routes`, `solver_algorithm_context_records`, `solver_algorithm_phase_runtime_ms`, `.alns`, and `.vns`.

- Why this violates or deviates from v3:
  v3 says problem objectives, hard constraints, telemetry fields, and mechanism semantics are declared by the problem/surface contract. Generic telemetry gates should validate declared fields and field roles, not know CVRP objective or route fields.

- Suggested fix:
  Add a problem/surface telemetry declaration API that supplies:
  - declared runtime fields;
  - field role categories such as `mechanism_activity`, `mechanism_activation`, `objective_outcome`, `budget`, and `protected_outcome`;
  - mechanism-id matching rules;
  - examples for prompt text.

  Then rewrite generic telemetry guard validation to consume those declarations. CVRP can keep the current `solver_algorithm_*` semantics in its provider metadata.

- Suggested tests:
  Add a synthetic non-CVRP problem with fields such as `planner_stage_runtime_ms` and `search_node_count`. Verify telemetry contract validation rejects objective fields in activation, accepts declared mechanism fields, and produces summaries without `solver_algorithm_*` strings.

## P1 Findings

### P1-1: Runtime audit and observation summary hardcode solver-design telemetry counters

- File paths:
  - `scion/scion/runtime/audit.py:92`
  - `scion/scion/runtime/audit.py:153`
  - `scion/scion/runtime/audit.py:246`
  - `scion/scion/protocol/experiment/runtime_observation.py:17`
  - `scion/scion/protocol/experiment/runtime_observation.py:144`

- Problem:
  Generic runtime audit and protocol observation code directly reads `solver_algorithm_errors`, `solver_algorithm_events`, `solver_algorithm_phase_runtime_ms`, and other `solver_algorithm_*` fields.

- Why this violates or deviates from v3:
  Lifecycle diagnostics can be generic, but field names and phase semantics should be declared by the selected research surface or problem provider. Hardcoded field names make the CVRP solver-design surface a hidden core contract.

- Suggested fix:
  Introduce a runtime telemetry descriptor per research surface. Generic runtime audit should ask the descriptor for error counters, event fields, stop-reason fields, elapsed/runtime consistency fields, and summary-visible scalar prefixes.

- Suggested tests:
  Add a synthetic research surface with differently named error/event/runtime fields and verify audit failure classification, bounded runtime summaries, and stop-reason aggregation all work without `solver_algorithm_*`.

### P1-2: Validation telemetry failures are treated as repairable before stage-specific decisions

- File paths:
  - `scion/scion/core/telemetry_validation.py:32`
  - `scion/scion/core/decision.py:29`

- Problem:
  `is_repairable_telemetry_validation_failure` returns true for both screening and validation stages. `DecisionEngine.decide` checks `features.telemetry_validation_repairable` before stage-specific logic and returns `CONTINUE_EXPLORE`.

- Why this violates or deviates from v3:
  v3 treats validation/frozen evidence as formal gates. A telemetry activation failure during validation may be a useful repair signal, but it should not be indistinguishable from ordinary exploration. It should either fail the validation gate or enter a distinct repair/retry lifecycle with explicit budget/accounting.

- Suggested fix:
  Restrict repairable telemetry validation failures to screening, or introduce a distinct validation telemetry repair decision/state that does not count as successful validation and must re-run validation after repair. Make the lifecycle explicit in branch state and evidence records.

- Suggested tests:
  Add tests for screening telemetry activation failure, validation telemetry activation failure, and frozen telemetry failure. Assert screening can repair, validation follows the chosen explicit policy, and frozen fails closed.

### P1-3: Contract solver-design detection still has path-based CVRP compatibility assumptions

- File path:
  - `scion/scion/contract/gate.py:814`

- Problem:
  `ContractGate._is_solver_design_patch_path` recognizes `policies/baseline_algorithm.py`, `policies/solver_algorithm.py`, and `policies/baseline_modules/*.py` before falling back to declared surface access.

- Why this violates or deviates from v3:
  v3 solver-design contract checks should be selected by research-surface declarations. Hardcoded path names are compatibility assumptions from the CVRP solver layout.

- Suggested fix:
  Use declared research surfaces for active v3 problems and keep path aliases behind a compatibility flag for legacy specs. Prefer provider-owned integration checks, as already done in `contract/checks/solver_design_integration.py`.

- Suggested tests:
  Add a non-CVRP solver-design surface with non-`policies/` paths and verify C7/C8/C9e/C11 behavior is driven by surface declarations only.

## P2 Findings

### P2-1: `DecisionFeatures.statistical_metric` remains free text

- File paths:
  - `scion/scion/core/models.py:341`
  - `scion/scion/core/features.py:116`
  - `scion/scion/core/features.py:186`

- Problem:
  `DecisionFeatures.statistical_metric` is an optional `str` copied from protocol stats. `_validate_no_free_text` does not reject or constrain it.

- Why this violates or deviates from v3:
  v3 DecisionFeatures are supposed to be deterministic, typed, and free of LLM text. Even if `statistical_metric` is currently not used by `DecisionEngine`, carrying arbitrary strings in the decision snapshot weakens the no-free-text invariant.

- Suggested fix:
  Replace `statistical_metric` with a bounded enum or a declared objective id validated against problem/surface metadata. If decision logic does not need it, remove it from `DecisionFeatures`.

- Suggested tests:
  Add a guard test where protocol stats include an arbitrary text value in `statistical_metric`; assert feature extraction rejects it or normalizes it to a declared id.

### P2-2: Legacy solution consistency still contains vehicle/order semantics

- File paths:
  - `scion/scion/verification/state_mutation.py:90`
  - `scion/scion/verification/state_mutation.py:166`
  - `scion/scion/core/models.py:439`

- Problem:
  Adapter-required specs are protected, but legacy verification still interprets `vehicles`, `assignment`, and `order_ids`.

- Why this violates or deviates from v3:
  This is controlled compatibility debt, not an active gate failure. It should remain clearly unavailable to adapter-backed v3 problems.

- Suggested fix:
  Move the legacy verification path into an explicitly named legacy module and make all v3 adapter-backed problem specs require adapter verification.

- Suggested tests:
  Add an adapter-backed problem test that fails if legacy vehicle/order verification is reached.

