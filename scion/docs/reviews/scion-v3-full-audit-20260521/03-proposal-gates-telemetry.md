# Proposal Gates And Telemetry

v3 baseline: hypothesis, code, contract, smoke, screening, formal validation, and lifecycle decisions must be traceable and auditable. Diagnostic activation-missing at proposal smoke/screening should help repair the same branch, but formal validation semantics must remain clear.

## Finding GATE-P1-1 - Validation Activation-Missing Is Modeled As Ordinary `CONTINUE_EXPLORE`

Severity: P1

Type: framework generic problem.

Evidence:
- `scion/scion/core/telemetry_validation.py:37-51` classifies activation-not-observed as repairable for both `SCREENING` and `VALIDATION`.
- `scion/scion/core/decision.py:37-58` maps validation telemetry repairable to `Decision.CONTINUE_EXPLORE` with `VALIDATION_TELEMETRY_REPAIRABLE`.
- `scion/scion/core/decision_finalizer.py:314-383` preserves the workspace, marks the hypothesis `code_failed`, sets `attempt_kind="validation_telemetry_repairable"`, and sets `counts_toward_max_rounds=False`.
- `scion/scion/tests/unit/core/test_decision_coordinator.py:90-110` codifies validation repairable as `CONTINUE_EXPLORE`.
- `scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py:247-350` codifies workspace preservation and non-counting retry for validation telemetry repair.

Why this risks v3:
- v3 treats formal validation as a boundary with higher confidence requirements than screening/proposal smoke.
- "Activation missing" is a useful diagnostic, but in validation it should not look like a normal exploration decision. Otherwise formal validation can become a hidden repair loop with unclear attempt budget and promotion semantics.

Recommended fix:
- Introduce an explicit decision/state such as `VALIDATION_REPAIR_REQUIRED`, or a validation-specific repair budget recorded separately from screening/proposal retry loops.
- Require the next branch step to be a targeted telemetry repair candidate before validation resumes.
- If no explicit repair path is implemented, fail validation closed and preserve artifacts for diagnosis.

Suggested tests:
- Validation activation-missing must not be indistinguishable from weak screening `CONTINUE_EXPLORE`.
- Attempt accounting must expose validation repair attempts separately.
- Promotion must be impossible until a successful validation rerun observes declared activation.

## Finding GATE-P1-2 - Generic Proposal Smoke/Audit Compaction Knows CVRP Outcome Fields

Severity: P1

Type: framework generic problem.

Evidence:
- `scion/scion/proposal/tools/previews/algorithm_smoke_feedback_runtime.py:101-119` includes `solver_algorithm_total_distance` and `solver_algorithm_fleet_violation` in generic runtime counter compaction.
- `scion/scion/proposal/solver_design_smoke/audit.py:45-68` includes the same fields in a generic solver-design smoke payload.

Why this violates v3:
- Total distance and fleet violation are CVRP protected/outcome semantics.
- Generic proposal smoke can compact declared telemetry fields, but it should not name CVRP outcomes directly.
- This is the same boundary class as CORE-P1-1, but earlier in the proposal-smoke feedback path.

Recommended fix:
- Ask the selected surface/provider for compact smoke fields and protected outcome fields.
- Keep generic compaction to structural metadata: loaded, active, errors, declared activation fields, declared event fields, declared protected outcome ids.

Suggested tests:
- A non-CVRP smoke payload with declared fields should be compacted without `solver_algorithm_total_distance` or `fleet_violation`.
- A boundary sentinel should fail if generic proposal smoke modules mention CVRP outcome names.

## Finding GATE-P2-1 - Agent Quality Block Classification Still Depends On Detail Text

Severity: P2

Type: framework generic problem.

Evidence:
- `scion/scion/core/explore_step_pipeline.py:51-65` classifies agent-quality blocked details by substring matching such as `premise_check=duplicate`, `algorithm smoke did not pass`, and `runtime_smoke.telemetry_guard`.
- `scion/scion/core/proposal_pipeline/agentic_lifecycle.py:349-403` already stores structured rejection fields: `failure_code`, `gate_name`, `premise_check`, `fact_ids`, `fact_packet_digest`, provenance, spans, and guidance.
- `scion/scion/core/proposal_pipeline/facade.py:164-179` re-injects structured prior quality blocks and negative facts into the next context.

Why this risks v3:
- The structured data exists, but the pipeline still has a text classifier in the control path.
- If detail wording changes, branch-local tainted memory and attempt classification can drift even when structured rejection data is correct.

Recommended fix:
- Route agent-quality status from `AgenticProposalOutput.status`, `failure_category`, and `structured_rejection.failure_code` instead of parsing strings.
- Keep detail text only for human diagnostics.

Suggested tests:
- A structured rejection with altered prose should still be classified as agent-quality blocked.
- A normal infrastructure/provider failure containing similar words should not be classified as proposal-quality debt.

## Alignment - C9e/C11 Are Mostly Provider-Driven Now

Evidence:
- `scion/scion/contract/checks/solver_design_integration.py` dispatches solver-design integration checks to a problem-owned provider and fails closed when a provider is required but missing.
- `scion/scion/problems/cvrp/contract_checks/solver_design_integration.py` owns CVRP-specific C9e checks.
- `scion/scion/contract/gate.py:359-402` validates expected telemetry through declared telemetry contracts.
- `scion/scion/contract/gate.py:408-467` enforces `mechanism_changes` when the surface declares mechanism telemetry.
- `scion/scion/tests/test_contract_solver_design_provider.py:16-23` verifies generic C9e dispatches to a problem-owned provider.
- `scion/scion/tests/test_contract_solver_design_provider.py:55-70` verifies the generic C9e facade does not contain CVRP solver terms.

Assessment:
- The recent C9e/C11 direction is close to v3.
- Remaining violations are concentrated in runtime/protocol/proposal-smoke telemetry naming, not the C9e facade itself.

## Alignment - LLM 502/Transport Retry Is Addressed

Evidence:
- `scion/scion/proposal/llm_client.py:94-130` recognizes 500/502/503/504, HTML gateway pages, disconnects, and DNS/network transient markers.
- `scion/scion/proposal/llm_client.py:188-207` exposes `is_llm_transient_api_error`.
- `scion/scion/proposal/llm_client.py:420-487` retries transient provider errors separately from user/schema retries.

Assessment:
- The recent 502/transport retry problem appears covered for proposal generation. Keep this in regression coverage, but it is not a current P1 blocker.
