# Design Traceability

This file maps v3/v0.4 design goals to the current implementation state.

## Traceability Matrix

| Design goal | Status | Evidence | Gap |
|---|---|---|---|
| LLM output is tainted; Decision reads structured features only | Implemented | `DecisionFeatures` has only enums, booleans, numeric stats, and tuples in `scion/scion/core/models.py:202-240`; `SafeFeatureExtractor` validates enum/numeric bounds in `scion/scion/core/features.py:62-163` and `scion/scion/core/features.py:166-240`; `DecisionEngine.decide()` accepts only `DecisionFeatures` in `scion/scion/core/decision.py:18-40`. | No P0 gap found. |
| Contract, Verification, Protocol, Decision remain separate control surfaces | Mostly implemented | Contract in `scion/scion/contract/gate.py:96-116`; verification in `scion/scion/verification/gate.py:85-195`; protocol in `scion/scion/protocol/experiment.py:383-847`; decision in `scion/scion/core/decision.py:18-217`. | `EvaluationPipeline` default evaluators pass contract/verification when no injected evaluators are provided (`scion/scion/core/evaluation_pipeline.py:86-127`), so production safety depends on the orchestrating caller wiring real gates. |
| Runtime is a promotion constraint | Mostly implemented | Runtime fields in `EvalStats` and `DecisionFeatures` at `scion/scion/core/models.py:127-136` and `scion/scion/core/models.py:219-232`; runtime extraction at `scion/scion/core/features.py:98-160`; runtime veto at `scion/scion/core/decision.py:177-206`; protocol counts failures at `scion/scion/protocol/experiment.py:491-690` and fails validation/frozen incomplete evidence at `scion/scion/protocol/experiment.py:782-788`. | Programmatic `CampaignManager` can still build a non-strict, no-runner `VerificationGate`; static complexity checks are narrow. |
| Timeout/crash pairs are counted, not skipped | Implemented for protocol stages | Candidate solver failure is recorded as failed/loss pair at `scion/scion/protocol/experiment.py:491-543`; champion failure is recorded invalid at `scion/scion/protocol/experiment.py:545-577`; raw metrics snapshots include failure counts at `scion/scion/protocol/experiment.py:422-444`. | Missing-output pairs are `failed_pairs` but are not attributed to candidate/champion in `scion/scion/protocol/experiment.py:579-601`, which weakens diagnosis and screening veto semantics. |
| Validation/frozen fail closed on incomplete evidence | Implemented | `scion/scion/protocol/experiment.py:782-788` forces gate fail on failed pairs in validation/frozen; `DecisionEngine` also abandons validation/frozen when `failed_pairs > 0` at `scion/scion/core/decision.py:200-205`. | Screening is less strict by design, but candidate runtime failures are still vetoed through `candidate_failed_pairs`. |
| Frozen holdout evidence required for promotion | Partially implemented | Scheduler transitions validation to frozen and frozen decision can promote in `scion/scion/core/decision.py:147-171`; promotion requires `FROZEN_TESTING` state at `scion/scion/core/promotion_lifecycle.py:85-90`. | `FrozenConfig.max_uses_per_campaign` is not enforced; frozen evidence count/usage is not persisted as a budget. |
| Final quality/runtime evidence harness shared and separate from promotion | Implemented as optional harness | Six-file final package writer in `scion/scion/evidence/final_quality.py:178-234`; CVRP runner-backed final evaluation in `scion/scion/evidence/cvrp_final_evaluation.py:77-173`; refs attach through `scion/scion/evidence/final_evidence_refs.py:61-70`. | Final evidence attachment is optional and not a close/readiness gate. |
| CVRP promotion objective is fleet_violation then total_distance | Implemented | ProblemSpecV1 objectives at `scion/scion/problems/cvrp/problem-v1.yaml:52-60`; adapter recomputes `fleet_violation` and `total_distance` at `scion/scion/problems/cvrp/adapter.py:170-186`; operator acceptance uses lexicographic objective at `scion/scion/problems/cvrp/solver.py:191-202` and `scion/scion/problems/cvrp/solver.py:529-541`. | Formal baseline fallback can make objective evidence about the wrong baseline. |
| BKS/gap report-only, not promotion evidence | Implemented | BKS and BKS routes are loaded into instance metadata at `scion/scion/problems/cvrp/cvrplib.py:76-97`; promotion objective recomputation excludes BKS/gap at `scion/scion/problems/cvrp/adapter.py:170-186`; final quality has BKS/gap fields at `scion/scion/evidence/final_quality.py:63-78` and `scion/scion/evidence/final_quality.py:577-614`. | No direct promotion use of BKS/gap found. |
| CVRP adapter must fail closed on solver-reported feasibility/cost | Mostly implemented | Adapter deserializes routes, checks all customers/duplicates/depot/unknown ids/objective completeness at `scion/scion/problems/cvrp/adapter.py:79-151`; capacity and feasibility checks at `scion/scion/problems/cvrp/adapter.py:153-168`; objective recomputation at `scion/scion/problems/cvrp/adapter.py:170-186`. | `deserialize_solver_output()` records solver `feasible` but current checks recompute feasibility, so no P0 gap. |
| CampaignManager should not own branch-step execution, promotion commit, evidence writing | Partially implemented | Extracted services exist: `BranchStepRunner`, `ExploreStepPipeline`, `EvaluationOrchestrator`, `DecisionFinalizer`, `PromotionLifecycleService`, `EvidenceRecorder`. `CampaignManager.run()` and `run_one_step()` delegate at `scion/scion/core/campaign.py:711-717`. | `campaign.py` still owns heavy dependency construction, transient state, compatibility wrappers, and many side-effect callbacks (`scion/scion/core/campaign.py:114-609`, `scion/scion/core/campaign.py:830-1196`). |
| Problem objects isolated behind adapters | Mostly implemented for production | ProblemSpecV1 bridge at `scion/scion/problem/bridge.py:40-86`; adapter interface in `scion/scion/problem/contracts.py`; CLI loads adapter and metric specs at `scion/scion/cli/main.py:107-123`. | Legacy fallback comparison still hardcodes warehouse metrics in `scion/scion/protocol/evaluation.py:6-58` and `scion/scion/protocol/experiment.py:201-230`; search memory/classifier defaults remain warehouse-shaped. |

## Findings

### Finding D1: Formal readiness still depends on optional final-evidence metadata

- Severity: P0
- Evidence: `EvidenceRecorder.attach_final_evidence_refs()` only updates an in-memory dict (`scion/scion/core/evidence_recorder.py:171-174`); summary writes refs only if present (`scion/scion/core/evidence_recorder.py:420-424`); `CampaignLoop.run()` writes summaries without checking final refs (`scion/scion/core/campaign_loop.py:66-72`).
- Impact: A campaign can be declared complete without final quality/runtime evidence. This violates the v0.4 formal-readiness claim even though keeping final evaluation outside the loop is correct.
- Recommendation: Add a separate formal readiness validator that fails closed when final evidence refs or artifact files are missing.
- Suggested tests: Summary without final refs should be formal-not-ready; attaching incomplete refs should still fail; attaching all six artifacts should pass.

### Finding D2: Adapter-native strict verification is CLI-strong but not constructor-default

- Severity: P1
- Evidence: CLI constructs `VerificationGate` with runner, adapter, `strict_runtime_checks=True`, and `require_adapter_for_runtime=True` at `scion/scion/cli/main.py:181-197`; `CampaignManager` default creates `VerificationGate` without runner or strict flags at `scion/scion/core/campaign.py:185-193`.
- Impact: Programmatic callers can unintentionally run adapter campaigns where V5-V9 runtime checks skip, while believing runtime-aware optimization is default framework behavior.
- Recommendation: If `experiment_protocol` exposes a runner and adapter is present, default to a strict runtime gate; otherwise require callers to pass `verification_gate` explicitly for production runs.
- Suggested tests: Construct `CampaignManager(adapter=..., experiment_protocol=real_protocol)` without a verification gate and assert V5/V9 execute; construct with no runner and assert strict adapter campaigns fail closed.

### Finding D3: CVRP route-count comparability is correctly separated from BKS/gap

- Severity: Implemented
- Evidence: `fleet_violation` uses `allowed_routes` or `bks_routes` but BKS cost is excluded from promotion objective (`scion/scion/problems/cvrp/adapter.py:170-186`); final evidence computes gap/route_gap separately (`scion/scion/evidence/final_quality.py:577-614`); formal readiness policy says BKS/gap final-report-only (`scion/scion/tests/test_cvrp_formal_readiness.py:90-100`).
- Impact: Multi-route fake wins are blocked at final evidence comparability and route count is protected during promotion through `fleet_violation`.
- Recommendation: Preserve this boundary; add regression tests for promotion objective on cases where distance improves only by exceeding allowed routes.
- Suggested tests: Candidate with lower distance and higher routes should lose/tie by promotion objective when fleet violation increases.
