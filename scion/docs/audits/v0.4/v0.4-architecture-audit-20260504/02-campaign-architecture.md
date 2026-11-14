# Campaign Architecture Audit

## Summary

`campaign.py` is no longer the direct owner of branch execution, evaluation, promotion commit, finalization, and evidence writing. The v0.4 decomposition is real. However, the module remains a large composition root plus compatibility surface: 1196 lines, a constructor spanning `scion/scion/core/campaign.py:114-609`, and many private wrappers from `scion/scion/core/campaign.py:830-1196`.

The implementation is therefore partially aligned with the v0.4 decomposition design, not complete.

## Implemented Decomposition

- `CampaignLoop` owns the outer loop and final status/summary writes (`scion/scion/core/campaign_loop.py:13-72`).
- `BranchStepRunner` owns scheduler dispatch, eval-only, and stale reconcile (`scion/scion/core/branch_step_runner.py:27-64`, `scion/scion/core/branch_step_runner.py:66-359`).
- `ExploreStepPipeline` owns explore proposal/code/contract/verification/evaluation flow (`scion/scion/core/explore_step_pipeline.py:36-623`).
- `EvaluationOrchestrator` owns protocol execution glue, decision coordination, and soft abandon (`scion/scion/core/evaluation_orchestrator.py:29-159`).
- `DecisionFinalizer` owns decision side effects (`scion/scion/core/decision_finalizer.py:55-182`, `scion/scion/core/decision_finalizer.py:312-386`).
- `PromotionLifecycleService` owns promotion snapshot/commit/weight-opt handoff (`scion/scion/core/promotion_lifecycle.py:24-193`).
- `EvidenceRecorder` owns status, lineage payloads, summaries, and final evidence refs (`scion/scion/core/evidence_recorder.py:89-510`).

## Findings

### Finding C1: `campaign.py` remains a heavy dependency composition and mutable-state hub

- Severity: P1
- Evidence: `CampaignManager.__init__()` constructs or wires `ProblemRuntime`, gates, stores, evidence recorder, workspace lifecycle, promotion lifecycle, decision finalizer, evaluation orchestrator, explore pipeline, branch runner, proposal pipeline, governance, and campaign loop in one constructor (`scion/scion/core/campaign.py:114-609`). The file still has 1196 lines.
- Impact: The controller is no longer executing every step directly, but it still owns too much composition and shared mutable state. This keeps service boundaries hard to audit and encourages new responsibilities to be added through callbacks.
- Recommendation: Introduce a `CampaignRuntimeBundle` / `CampaignCompositionFactory` that builds services from explicit inputs. Keep `CampaignManager` as public facade plus state accessors. Move construction of evidence, governance, promotion, proposal, and branch services into focused factory functions.
- Suggested tests: Snapshot dependency wiring with a factory unit test; instantiate campaign through factory and assert same public state, same CLI smoke, and no behavioral change.

### Finding C2: Extracted services still reverse-depend on manager internals through callbacks

- Severity: P1
- Evidence: `CampaignManager` passes many lambdas/private callbacks into services: promotion service callbacks at `scion/scion/core/campaign.py:203-214`, decision finalizer callbacks at `scion/scion/core/campaign.py:385-412`, evaluation orchestrator callbacks at `scion/scion/core/campaign.py:413-449`, explore pipeline callbacks at `scion/scion/core/campaign.py:450-482`, branch runner callbacks at `scion/scion/core/campaign.py:483-519`.
- Impact: This satisfies staged extraction, but not the v0.4 design target that services accept explicit request/state inputs and return explicit outcomes. The callback shape makes it hard to reason about side effects and failure ordering.
- Recommendation: Convert callback clusters into typed collaborator objects: `BranchStateRepository`, `WorkspaceRepository`, `PromotionCommitter`, `EvidenceSink`, and `BudgetLedger`. Services should return outcome objects where possible.
- Suggested tests: Service-level tests that pass fake repositories instead of `CampaignManager`; verify promotion failure does not mutate branch/champion state.

### Finding C3: Compatibility adapters can mask missing service wiring

- Severity: P2
- Evidence: `campaign_adapters.py` creates fallback `BranchStepRunner` instances with no-op stores, missing callback shims, default pass/skip behavior, and private owner lookups (`scion/scion/core/campaign_adapters.py:53-165`). Similar fallback service creation continues after line 168.
- Impact: These adapters are useful for staged migration, but they can convert wiring mistakes into "skip" or placeholder behavior instead of failing clearly. That weakens auditability.
- Recommendation: Keep compatibility adapters only for legacy tests, mark them explicitly test/compat-only, and make production `CampaignManager` call owned service attributes directly.
- Suggested tests: A production campaign missing `_branch_step_runner` should fail fast rather than silently constructing a fallback runner; legacy compatibility tests can opt into adapter shims.

### Finding C4: BranchStepRunner is useful but already owns several lifecycle concerns

- Severity: P2
- Evidence: `BranchStepRunner.run_reconcile_step()` handles workspace setup, patch application, contract validation, verification, branch reconciliation, evaluation, decision finalization, hard-abandon bookkeeping, and step recording (`scion/scion/core/branch_step_runner.py:218-359`).
- Impact: The original weight moved from `CampaignManager` into a new service. It is still understandable, but stale reconcile is now a second mini-pipeline with many side effects.
- Recommendation: Extract stale reconcile into `StaleReconcilePipeline` or split into `ReconcilePreparation`, `ReconcileVerification`, and `ReconcileEvaluation` outcome methods.
- Suggested tests: Dedicated stale reconcile tests for patch missing, contract fail, verification fail, missing metadata, successful re-screen, and promotion after reconcile.

### Finding C5: Decision finalization ordering is stronger than v0.3

- Severity: Implemented
- Evidence: Promotion is prepared before mutable promotion commit in `DecisionFinalizer._prepare_promotion()` (`scion/scion/core/decision_finalizer.py:184-220`); promote lineage is recorded after `commit_promote_plan()` succeeds (`scion/scion/core/decision_finalizer.py:312-359`); `PromotionLifecycleService.require_promotable_branch()` requires `FROZEN_TESTING` (`scion/scion/core/promotion_lifecycle.py:85-90`).
- Impact: Promotion store/snapshot failures are less likely to leave inconsistent champion/branch/lineage side effects.
- Recommendation: Preserve this ordering while moving construction weight out of `campaign.py`.
- Suggested tests: Continue testing prepare failure and commit failure as non-promotion side-effect cases.
