# Governance, Evidence, and Lineage Audit

## Summary

Lineage and evidence recording are materially improved. Step summaries include raw metrics refs, runtime stats, reason codes, verification metadata, and final evidence refs can be attached at top level without changing step schema.

Governance is incomplete for formal claims because frozen holdout usage and final evidence close/readiness are not enforced.

## Findings

### Finding GEL1: Frozen holdout use limit is configuration-only

- Severity: P0
- Evidence: `FrozenConfig.max_uses_per_campaign` exists at `scion/scion/config/protocol_config.py:53-66`. `ExperimentProtocol.run_experiment()` selects frozen cases but does not consume a campaign-level frozen usage budget (`scion/scion/protocol/experiment.py:383-847`). `BranchStepRunner` schedules `READY_FROZEN`/`FROZEN_TESTING` without checking a frozen usage counter (`scion/scion/core/branch_step_runner.py:99-126`). Tests only assert config parsing (`scion/scion/tests/test_config.py:74-106`).
- Impact: Frozen holdout can be reused beyond the designed campaign budget, weakening the final promotion evidence and v3 auditability.
- Recommendation: Add `FrozenUsageLedger` persisted in campaign state/lineage. Consume on attempted frozen evaluation, expose remaining uses in status, and block scheduling when exhausted.
- Suggested tests: With `max_uses_per_campaign=1`, two frozen-ready branches should result in exactly one protocol frozen run; the second should not spend protocol budget and should get a deterministic reason code.

### Finding GEL2: Final evidence refs do not gate campaign close/readiness

- Severity: P0
- Evidence: `EvidenceRecorder.attach_final_evidence_refs()` only stores refs (`scion/scion/core/evidence_recorder.py:171-174`); summary includes them only if present (`scion/scion/core/evidence_recorder.py:420-424`); `CampaignLoop.run()` writes summaries before/after weight-opt wait with no final-evidence validation (`scion/scion/core/campaign_loop.py:66-72`).
- Impact: A formal campaign can produce a complete campaign summary without final quality/runtime evidence refs. This is acceptable for a running campaign, but not for formal readiness.
- Recommendation: Add a `FormalReadinessReport` or `CampaignCloseValidator` that checks final refs after the manual post-campaign evidence step. Do not auto-run final evaluation in the loop.
- Suggested tests: Incomplete final refs produce `formal_ready=false` with missing artifact names; complete refs produce `formal_ready=true`.

### Finding GEL3: Runtime and metrics refs are sufficiently persisted for audit

- Severity: Implemented
- Evidence: Protocol raw metrics snapshot contains cases, seeds, total/attempted/valid/failed pairs, candidate/champion failures, runtime stats, pairs, and failures (`scion/scion/protocol/experiment.py:422-444`). EvidenceRecorder lineage stores `protocol_raw_metrics_ref`, verification checks, runtime guard, runtime stats, and reason codes (`scion/scion/core/evidence_recorder.py:191-211`). Step summaries include runtime stats and raw metrics refs (`scion/scion/core/evidence_recorder.py:460-496`).
- Impact: For completed stages, audit can reconstruct pair-level runtime/objective evidence from raw metrics and summary/lineage references.
- Recommendation: Keep raw metrics paths stable and consider storing content hashes for long-term artifact integrity.
- Suggested tests: Add hash field to raw metrics refs if implemented; verify summary hash matches file content.

### Finding GEL4: Validation/frozen exposure controls protect per-case feedback

- Severity: Implemented
- Evidence: `EvaluationPipeline._sanitize_protocol_exposure()` strips validation/frozen `pair_feedback`, `case_feedback`, and `pattern_summary` (`scion/scion/core/evaluation_pipeline.py:172-193`). Protocol itself returns screening pair/case feedback only for screening (`scion/scion/protocol/experiment.py:828-847`). Tests assert validation/frozen aggregate-only exposure (`scion/scion/tests/unit/core/test_evaluation_pipeline.py:203-250`, `scion/scion/tests/unit/protocol/test_protocol_correctness.py:461-493`).
- Impact: LLM proposal context does not receive validation/frozen per-case details from protocol result objects.
- Recommendation: Continue enforcing raw metrics screening-only feedback in `ContextManager`; avoid adding validation/frozen raw metrics paths to proposal context.
- Suggested tests: Add a context-manager test with validation/frozen raw metrics refs and assert no per-case case ids/seeds appear in rendered prompt.

### Finding GEL5: Final evidence attachment preserves step schema

- Severity: Implemented
- Evidence: Final refs are top-level summary fields (`scion/scion/core/evidence_recorder.py:420-424`); tests assert step entries do not receive `final_evidence_refs` (`scion/scion/tests/test_cvrp_controlled_campaign.py:231-237`, `scion/scion/tests/test_cvrp_controlled_campaign.py:312-323`).
- Impact: Final evidence can be attached after campaign completion without rewriting per-step evidence.
- Recommendation: Preserve this top-level attachment model; add readiness validation around it.
- Suggested tests: Existing tests are sufficient for schema stability; add artifact completeness validation tests.

### Finding GEL6: Promotion lineage is recorded after promotion commit

- Severity: Implemented
- Evidence: `DecisionFinalizer._promote()` commits the promote plan first and records lineage after successful commit (`scion/scion/core/decision_finalizer.py:312-359`). Promotion precondition and prepare failure return non-promotion step results (`scion/scion/core/decision_finalizer.py:184-220`).
- Impact: Snapshot/commit failures are less likely to appear as promoted hypotheses or champion advances.
- Recommendation: Preserve this order when further decomposing promotion code.
- Suggested tests: Promotion commit failure should not mark hypothesis promoted, should not update champion store, and should record infra failure.
