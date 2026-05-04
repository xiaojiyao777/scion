# Runtime-Aware Optimization Audit

## Summary

Runtime-aware optimization is implemented in the main protocol/decision path: protocol records pair completeness and runtime facts, `SafeFeatureExtractor` admits structured runtime facts into `DecisionFeatures`, and `DecisionEngine` vetoes runtime failures/regressions.

The remaining gaps are about default enforcement and breadth:

- Programmatic campaigns can still skip V5-V9 runtime verification unless given a strict verification gate.
- Static complexity rejection is narrower than the design goal.
- Formal CVRP baseline fallback can hide a wrong baseline unless fixed.

## Implemented Runtime Evidence Flow

- Runtime/completeness fields exist in `EvalStats` (`scion/scion/core/models.py:127-136`) and `DecisionFeatures` (`scion/scion/core/models.py:219-232`).
- Protocol raw metrics write pair counts, runtime stats, raw pairs, and failures from the start of a stage (`scion/scion/protocol/experiment.py:422-446`).
- Candidate failures are counted as losses/failures (`scion/scion/protocol/experiment.py:491-543`).
- Runtime audit failures are converted into candidate/champion failed pairs (`scion/scion/protocol/experiment.py:603-690`).
- Validation/frozen fail closed on incomplete evidence (`scion/scion/protocol/experiment.py:782-788`).
- `SafeFeatureExtractor` copies runtime fields into `DecisionFeatures` (`scion/scion/core/features.py:98-160`).
- `DecisionEngine._runtime_veto()` abandons runtime guard timeouts/failures, candidate runtime failures, median runtime regressions, and validation/frozen incomplete evidence (`scion/scion/core/decision.py:177-206`).
- Proposal context receives bounded screening runtime feedback, not decision facts (`scion/scion/proposal/context_manager.py:1200-1321`).

## Findings

### Finding R1: Runtime verification is not default for programmatic CampaignManager construction

- Severity: P1
- Evidence: `CampaignManager` builds `VerificationGate(problem_spec, metrics_dir=..., adapter=..., max_runtime_ratio=...)` without runner, `strict_runtime_checks`, or `require_adapter_for_runtime` when no gate is passed (`scion/scion/core/campaign.py:185-193`). `VerificationGate.run()` skips runtime checks when runner/spec are unavailable unless strict mode is enabled (`scion/scion/verification/gate.py:130-147`). CLI construction is strict (`scion/scion/cli/main.py:181-197`).
- Impact: Runtime-aware optimization is true for CLI adapter campaigns, but not an unconditional framework default. Tests or scripts that instantiate `CampaignManager` directly with a real protocol can accidentally bypass V5-V9 during explore/reconcile verification.
- Recommendation: If `experiment_protocol` is supplied and has a runner, derive a strict `VerificationGate` by default. For adapter-backed problems, set `strict_runtime_checks=True` and `require_adapter_for_runtime=True` unless the caller explicitly opts into compatibility mode.
- Suggested tests: Programmatic campaign with adapter and real protocol but no `verification_gate` should run V9; same construction with missing champion workspace should fail closed.

### Finding R2: `V9_perf_guard` has fail-open skip branches outside strict validation

- Severity: P1
- Evidence: `check_perf()` returns passed when no perf/canary case is configured (`scion/scion/verification/perf_guard.py:31-35`), when the perf case is missing (`scion/scion/verification/perf_guard.py:36-37`), when champion workspace is unavailable (`scion/scion/verification/perf_guard.py:39-40`), or when champion run fails (`scion/scion/verification/perf_guard.py:110-125`). `VerificationGate` strict config catches some missing config before V9 (`scion/scion/verification/gate.py:138-147`).
- Impact: In non-strict paths, runtime guard may be recorded as passed/skipped instead of failing closed. That is acceptable for legacy compatibility but not for v0.4 production.
- Recommendation: Treat V9 skip-as-pass only as legacy mode. In adapter production mode, skip conditions should produce failed `V_runtime_config` or failed `V9_perf_guard`.
- Suggested tests: Non-strict legacy test can preserve skip behavior; strict adapter test should fail for missing perf case, missing champion workspace, and champion runtime audit failure.

### Finding R3: Static complexity governance is too narrow

- Severity: P1
- Evidence: Contract complexity check only detects `itertools.combinations` aliases with constant k > 2 or variable k (`scion/scion/contract/gate.py:416-460`, helper detection at `scion/scion/contract/gate.py:569-588`). Tests cover combinations only (`scion/scion/tests/test_contract.py:511-577`).
- Impact: The v0.4 design says static contract should reject unbounded high-order enumeration. Current code misses `permutations`, `product`, full nested route-pair/customer loops, uncapped `while True`, and exhaustive all-customer scans. A slow operator can reach runtime gates and burn evaluation budget.
- Recommendation: Add a conservative `ComplexityPolicy` with adapter-configurable allow/deny patterns and AST checks for permutations/product, nested loops over problem-scale collections, and uncapped while loops. Keep it advisory-to-fail for production but allow explicit bounded patterns.
- Suggested tests: Reject `permutations(customers)`, `product(routes, routes, customers)`, three-level loops over `instance.customer_ids`, and `while True` without a bounded break counter; allow top-k sliced lists and constant cap loops.

### Finding R4: Runtime feedback threshold is hardcoded in proposal context

- Severity: P2
- Evidence: Raw screening slow-case extraction treats `runtime_ratio <= 2.0` as not slow (`scion/scion/proposal/context_manager.py:1300-1308`) rather than using `ProtocolConfig.runtime.max_runtime_ratio`.
- Impact: If a problem tightens or relaxes runtime policy, proposal guidance can disagree with promotion governance.
- Recommendation: Pass runtime threshold into `ContextManager` or store it with protocol summary metadata.
- Suggested tests: With `max_runtime_ratio=1.25`, a 1.5x case appears in runtime feedback; with 3.0, a 2.5x case does not.

### Finding R5: Runtime audit failure conversion is a strong implemented boundary

- Severity: Implemented
- Evidence: Solver-side `operator_errors`, `operator_invalid_outputs`, and required baseline failures become structured audit failures in `scion/scion/runtime/audit.py:28-81`; protocol treats candidate audit failures as losses/failures at `scion/scion/protocol/experiment.py:603-655`; tests cover operator runtime errors and required baseline runtime failure metadata in `scion/scion/tests/test_protocol.py:424-483`.
- Impact: Operators that crash internally but return unchanged incumbent are not treated as objective ties.
- Recommendation: Preserve this boundary and extend it to formal baseline selection repair.
- Suggested tests: Keep regression tests for recovered operator exception, invalid output, and baseline fallback.
