# Test Coverage and Gaps

## Existing Strong Coverage

- Decision runtime vetoes: `scion/scion/tests/test_decision.py`
- Protocol runtime pair accounting and incomplete validation/frozen evidence: `scion/scion/tests/test_protocol.py:397-550`
- Strict verification config failures: `scion/scion/tests/test_verification.py:648-729`
- CVRP adapter semantics: `scion/scion/tests/test_cvrp_adapter.py`
- CVRPLIB parser with synthetic fixtures: `scion/scion/tests/test_cvrp_cvrplib_adapter.py`
- CVRP solver `.vrp` smoke: `scion/scion/tests/test_cvrp_solver_vrp_smoke.py`
- CVRP registry operator runtime audit: `scion/scion/tests/test_cvrp_solver_operator_runtime.py`
- Controlled CVRP campaign screening/validation/frozen/promote/final refs: `scion/scion/tests/test_cvrp_controlled_campaign.py`
- Formal manifest readiness without reading raw CVRPLIB files: `scion/scion/tests/test_cvrp_formal_readiness.py`
- Final quality package and final evidence refs: `scion/scion/tests/unit/evidence/*`

I did not run the full suite during this audit; this was a read-only review plus documentation write.

## Findings

### Finding T1: Missing test for formal `.vrp` required-baseline failure

- Severity: P0
- Evidence: Current `.vrp` data-root test asserts fallback is not required when synthetic data root has no `vrp/src` (`scion/scion/tests/test_cvrp_solver_vrp_smoke.py:157-177`). Runtime audit would fail required fallbacks only when `baseline_required=True` (`scion/scion/runtime/audit.py:97-105`).
- Impact: The exact formal failure mode is untested and currently encoded as acceptable behavior.
- Recommendation: Add a formal-mode synthetic fixture where `SCION_PROBLEM_DATA_ROOT` contains `cvrplib/...case.vrp` but no `src/solver.py`; assert `baseline_required=True` and runtime audit failure.
- Suggested tests: `test_formal_vrp_without_vrp_src_is_runtime_audit_failure`; `test_controlled_synthetic_vrp_keeps_baseline_required_false`.

### Finding T2: Missing frozen holdout usage budget tests

- Severity: P0
- Evidence: `max_uses_per_campaign` is only parsed in tests (`scion/scion/tests/test_config.py:74-106`); no tests match `max_uses_per_campaign` outside config/readiness assets.
- Impact: The campaign can overuse frozen holdout without any test failing.
- Recommendation: Add scheduler/campaign tests around a persisted frozen usage counter.
- Suggested tests: Two branches in `READY_FROZEN` with max use 1; restart campaign after one frozen attempt; reconcile stale branch after frozen budget exhausted.

### Finding T3: Missing formal close/readiness tests for final evidence refs

- Severity: P0
- Evidence: Tests validate attachment shape but not close/readiness enforcement (`scion/scion/tests/unit/evidence/test_final_evidence_refs.py`, `scion/scion/tests/test_cvrp_controlled_campaign.py:184-323`).
- Impact: A summary without final refs is still considered normal by tests.
- Recommendation: Add a formal readiness validator and tests for missing refs, incomplete artifact refs, and complete package.
- Suggested tests: `test_formal_readiness_fails_without_final_evidence_refs`; `test_formal_readiness_fails_when_runtime_summary_ref_missing`; `test_formal_readiness_passes_with_all_six_artifacts`.

### Finding T4: Missing programmatic strict-runtime construction test

- Severity: P1
- Evidence: CLI strict construction is tested indirectly; `CampaignManager` default gate construction remains non-strict/no-runner (`scion/scion/core/campaign.py:185-193`).
- Impact: Non-CLI production-like usage can skip runtime checks.
- Recommendation: Add a unit/integration test that constructs `CampaignManager` with adapter and `ExperimentProtocol` but no explicit verification gate, then asserts runtime gate execution.
- Suggested tests: Spy runner should observe V5/V6/V7/V8/V9 calls during explore; missing canary/champion should fail closed.

### Finding T5: Complexity guard tests cover only combinations

- Severity: P1
- Evidence: Complexity tests are only for `combinations` patterns (`scion/scion/tests/test_contract.py:511-577`); implementation only detects `combinations` (`scion/scion/contract/gate.py:416-460`).
- Impact: Expensive operators using other enumeration forms can pass contract.
- Recommendation: Extend tests before broadening implementation.
- Suggested tests: Reject `itertools.permutations`, `itertools.product`, three nested loops over `routes/customers`, and uncapped `while True`; allow capped top-k slices and fixed `for _ in range(8)`.

### Finding T6: Problem-boundary regression tests should cover legacy fallback blocking

- Severity: P1
- Evidence: Legacy objective fallback remains in `scion/scion/protocol/evaluation.py:6-58` and `scion/scion/protocol/experiment.py:201-230`.
- Impact: Adapter-backed problems could accidentally fall back to warehouse metrics if production construction changes.
- Recommendation: Add tests that adapter-backed protocols require metric specs by default.
- Suggested tests: CVRP `ExperimentProtocol(metric_specs=None, require_metric_specs=True)` raises; CLI CVRP run passes metric specs; legacy warehouse compatibility path is explicit.

### Finding T7: Runtime feedback threshold should be tested against protocol config

- Severity: P2
- Evidence: Slow-case extraction hardcodes 2.0 at `scion/scion/proposal/context_manager.py:1300-1308`.
- Impact: Prompt guidance can drift from runtime governance if threshold changes.
- Recommendation: Make threshold configurable and test both tighter and looser thresholds.
- Suggested tests: Rendered context includes 1.5x slow case with threshold 1.25 and excludes 2.5x with threshold 3.0.

### Finding T8: Missing route-count promotion regression

- Severity: P2
- Evidence: CVRP objective policy is implemented (`scion/scion/problems/cvrp/adapter.py:170-186`), and final fake-win evidence tests exist (`scion/scion/tests/unit/evidence/test_cvrp_final_evaluation.py:243-267`), but promotion-level route-count regression should be explicit.
- Impact: Future objective comparator changes could reintroduce distance-only wins with extra routes.
- Recommendation: Add protocol comparison test with candidate lower distance but higher `fleet_violation`.
- Suggested tests: Candidate with `fleet_violation=1,total_distance=80` loses to champion `fleet_violation=0,total_distance=100`.
