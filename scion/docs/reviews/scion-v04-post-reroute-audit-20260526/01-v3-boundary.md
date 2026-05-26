# V3 Boundary and Generic Core

Audit question: does Scion generic core avoid research-object content, with object-specific facts and rules entering through adapters/providers?

## Positive Findings

The main 2026-05-25 boundary blocker is largely repaired.

- `ContractGate` now asks provider policy before classifying active solver-design patch paths: `scion/scion/contract/gate.py:609-634`.
- CVRP active package paths and `context.baseline` restrictions live under the CVRP provider: `scion/scion/problems/cvrp/contract_checks/solver_design_integration.py:32-60`.
- The generic boundary sentinel now explicitly fails CVRP/ALNS/VNS/path leaks and keeps the legacy allowlist visible: `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py:19-49` and `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py:51-91`.

This is the right v3 shape: generic Contract owns the control point; problem packages own active-object semantics.

## Finding B-1: algorithm taxonomy remains in generic proposal/runtime code

Severity: P1.

The remaining boundary leak is not the old hardcoded CVRP package path. It is generic code knowing concrete algorithm families/phases:

- `scion/scion/proposal/mechanism_novelty.py:310-314` special-cases `solver_design`, `local_search`, and `destroy_repair`.
- `scion/scion/proposal/agentic_session_patch_flow.py:21-30` declares hardcoded telemetry phases and `scion/scion/proposal/agentic_session_patch_flow.py:838-840` excludes them from telemetry identity mismatch detection.
- `scion/scion/proposal/agentic_session_hypothesis.py:1424-1432` filters activation refs through a hardcoded set at `scion/scion/proposal/agentic_session_hypothesis.py:1452-1464`.
- `scion/scion/proposal/context_manager/guidance.py:416-420` suggests concrete module names from generic guidance.
- `scion/scion/runtime/audit.py:111-123` and `scion/scion/runtime/audit.py:178-198` treat construction/portfolio/policy/operator counters as generic runtime failure categories.

Impact: current CVRP behavior is understandable, but the core is not fully problem-generic. More importantly, the telemetry identity gate can treat a hardcoded phase name as "generic" rather than requiring the proposal's declared mechanism id.

Suggested fix: introduce a provider-declared mechanism/telemetry taxonomy. Generic code should ask for structural phase ids, allowed broad family ids, runtime counter roles, and prompt examples. CVRP can declare `construction`, `acceptance`, `local_search`, and `destroy_repair`; generic Scion should not.

Suggested tests:

- A non-CVRP dummy problem whose provider declares different phase ids, proving generic APS does not mention CVRP-style names.
- A telemetry identity test where `record_phase("local_search")` is not accepted unless the active provider declares it structural.
- Boundary sentinel extension that checks provider-declared taxonomy rather than only CVRP path terms.

## Finding B-2: legacy generic shapes remain allowlisted

Severity: P2.

Residual allowlisted legacy fields remain:

- `_LEGACY_PROBLEM_SCALE_NAMES` in `scion/scion/contract/gate.py:61-74`.
- `SolverOutput.vehicles` and assignment/objective fields in `scion/scion/core/models.py:455-462`.

These do not appear to break current v0.4 CVRP runs, but they should stay visible as migration debt. New v2/v3 surfaces should not rely on these fallbacks.

