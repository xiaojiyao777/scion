# DecisionEngine, BranchLifecyclePolicy, and Lifecycle-Aware Scheduling

## Scope

Current source reviewed:

- `scion/scion/core/decision.py`
- `scion/scion/core/decision_coordinator.py`
- `scion/scion/core/models.py`
- `scion/scion/core/features.py`
- `scion/scion/core/branch_lifecycle_policy.py`
- `scion/scion/core/decision_lifecycle_actions.py`
- `scion/scion/core/decision_finalizer.py`
- `scion/scion/core/evaluation_orchestrator.py`
- `scion/scion/core/branch_hygiene.py`
- `scion/scion/core/scheduler.py`
- `scion/scion/core/scheduling/active_slots.py`
- `scion/scion/core/scheduling/signals.py`
- `scion/scion/core/branch_repair_policy.py`
- selected decision, lifecycle, finalizer, scheduler, proposal, evidence, and boundary tests

## Current Understanding

The decision path is deliberately layered:

```text
ProtocolResult
  -> SafeFeatureExtractor
  -> DecisionFeatures structured feature contract
  -> DecisionEngine
       -> preflight fail-closed gates
       -> runtime vetoes
       -> telemetry repair routing
       -> stage decision
       -> BranchLifecyclePolicy only for continue/repair decisions
  -> DecisionCoordinator
  -> EvaluationOrchestrator stores reason codes + lifecycle action
  -> DecisionFinalizer applies branch/workspace side effects
  -> Scheduler/active-slot policy excludes or parks low-value lineages
```

`BranchLifecyclePolicy` is not a promotion gate. It is a research-branch lifecycle
gate that decides when a low-win, diagnostic, repeated, or regressed branch should
keep its head, retain a checkpoint, roll back, park the lineage, or archive the
lineage. The policy is generic and consumes only structured `DecisionFeatures`
plus branch lifecycle counters.

Evidence:

- `DecisionEngine` validates structured features and fail-closes contract,
  verification, canary, runtime-veto, telemetry, and unknown-stage paths:
  - `scion/scion/core/decision.py:41`
  - `scion/scion/core/decision.py:47`
  - `scion/scion/core/decision.py:56`
  - `scion/scion/core/decision.py:96`
  - `scion/scion/core/decision.py:103`
- runtime vetoes run before stage and lifecycle decisions:
  - `scion/scion/core/decision.py:56`
  - `scion/scion/core/decision.py:258`
  - `scion/scion/core/decision.py:264`
  - `scion/scion/core/decision.py:273`
- lifecycle policy is applied only to `CONTINUE_EXPLORE` or
  `VALIDATION_REPAIR_REQUIRED`, and only for repairable telemetry or screening
  features with a win rate:
  - `scion/scion/core/decision.py:321`
  - `scion/scion/core/decision.py:326`
  - `scion/scion/core/decision.py:331`
- lifecycle archive/soft-abandon can rewrite the final decision to `ABANDON`;
  park/retain/rollback keep the stage decision and carry lifecycle codes:
  - `scion/scion/core/decision.py:354`
  - `scion/scion/core/decision.py:355`
  - `scion/scion/core/decision.py:366`
- `EvaluationOrchestrator` injects branch lifecycle counters into
  `DecisionFeatures` and stores the resulting lifecycle action:
  - `scion/scion/core/evaluation_orchestrator.py:171`
  - `scion/scion/core/evaluation_orchestrator.py:179`
  - `scion/scion/core/evaluation_orchestrator.py:181`
  - `scion/scion/core/evaluation_orchestrator.py:249`
- `DecisionFinalizer` turns explicit lifecycle actions into branch state,
  workspace, checkpoint, and status side effects:
  - `scion/scion/core/decision_finalizer.py:390`
  - `scion/scion/core/decision_finalizer.py:422`
  - `scion/scion/core/decision_finalizer.py:472`
  - `scion/scion/core/decision_finalizer.py:503`
  - `scion/scion/core/decision_finalizer.py:571`
- scheduler active-slot reconciliation requires a decision-origin park marker
  before it persists a branch as parked:
  - `scion/scion/core/scheduling/active_slots.py:121`
  - `scion/scion/core/scheduling/active_slots.py:336`
  - `scion/scion/core/scheduling/active_slots.py:346`
  - `scion/scion/core/scheduling/active_slots.py:371`

## Positive Boundary Observations

- The decision feature contract is structured and validates stage, action,
  protocol outcome, runtime evidence status/confidence, runtime ratios, metrics,
  counters, and known failure codes before decision logic runs.
- Runtime failures and large runtime regressions are first-class vetoes, not
  proposal text or post-hoc commentary.
- Lifecycle policy is scoped away from promotion decisions. Tests verify that
  screening pass, validation pass, and frozen promotion decisions are not rewritten
  by lifecycle policy.
- Low-confidence runtime evidence does not drive runtime soft-abandon. It becomes
  diagnostic pressure instead.
- Pair-level signal can keep a branch alive even when case-level screening fails,
  and fresh champion runtime follow-up is tracked as scheduler guidance.
- Finalizer does not park solely because a legacy lifecycle reason code is present;
  explicit `lifecycle_action` is required.
- Active-slot reconciliation cannot arbitrarily park low-value branches unless a
  decision-origin park marker exists.
- Agentic/proposal lifecycle blocks are recorded outside ordinary proposal/infra
  failure streaks, reducing false circuit-breaker pressure.
- Generic core files reviewed here do not embed CVRP-specific decision semantics.

Evidence:

- structured validation:
  - `scion/scion/core/features.py:237`
  - `scion/scion/core/features.py:271`
  - `scion/scion/core/features.py:300`
  - `scion/scion/core/features.py:347`
- lifecycle no-rewrite tests for validation/frozen/promotion:
  - `scion/scion/tests/test_decision_validation_frozen.py:43`
  - `scion/scion/tests/test_decision_validation_frozen.py:54`
- lifecycle structured rewrite test:
  - `scion/scion/tests/test_decision_screening.py:93`
  - `scion/scion/tests/test_decision_screening.py:104`
- low-confidence runtime behavior and pair-level preservation:
  - `scion/scion/tests/unit/core/test_branch_lifecycle_policy.py:134`
  - `scion/scion/tests/unit/core/test_branch_lifecycle_policy.py:200`
  - `scion/scion/tests/unit/core/test_branch_lifecycle_policy.py:319`
- finalizer explicit-action guard:
  - `scion/scion/tests/unit/core/test_decision_finalizer_park_lifecycle.py:641`
  - `scion/scion/tests/unit/core/test_decision_finalizer_park_lifecycle.py:730`
- active-slot marker guard:
  - `scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py:136`
  - `scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py:155`
- proposal lifecycle blocks are outside ordinary failure streaks:
  - `scion/scion/core/proposal_pipeline/facade.py:292`
  - `scion/scion/core/proposal_pipeline/agentic_lifecycle.py:354`
  - `scion/scion/core/proposal_pipeline/classification.py:240`

## Risks And Findings

### F-DECISION-001 [P2] Branch lifecycle thresholds are hard-coded in core policy and can become hidden research gates

`BranchLifecyclePolicy` has several fixed thresholds: zero-win streak limit,
no-effect follow-up limit, marginal/no-effect repeated-signature limit, rollback
budget limit, runtime slowdown threshold, runtime-regression threshold, telemetry
diagnostic streak limit, and diagnostic zero-win streak limit.

Those thresholds directly control whether agent research continues on the same
branch, rolls back, parks a lineage, or archives a lineage. They are well tested,
but they are not currently surfaced as campaign/protocol configuration on the
standard production construction path. That makes the policy safe from LLM text
but comparatively opaque when an agent appears "blocked" by repeated lifecycle
decisions.

Evidence:

- fixed lifecycle defaults:
  - `scion/scion/core/branch_lifecycle_policy.py:129`
  - `scion/scion/core/branch_lifecycle_policy.py:134`
  - `scion/scion/core/branch_lifecycle_policy.py:137`
- rollback, no-effect, repeated-signature, diagnostic, and zero-win gates:
  - `scion/scion/core/branch_lifecycle_policy.py:336`
  - `scion/scion/core/branch_lifecycle_policy.py:369`
  - `scion/scion/core/branch_lifecycle_policy.py:386`
  - `scion/scion/core/branch_lifecycle_policy.py:399`
  - `scion/scion/core/branch_lifecycle_policy.py:409`
- telemetry diagnostic streak can park or retain checkpoint:
  - `scion/scion/core/branch_lifecycle_policy.py:472`
- standard campaign composition injects only `ProtocolConfig` into
  `DecisionCoordinator`, and `DecisionEngine` creates a default lifecycle policy:
  - `scion/scion/core/campaign_composition.py:170`
  - `scion/scion/core/decision.py:36`
  - `scion/scion/core/decision.py:39`
- finalizer turns these lifecycle actions into real state/workspace effects:
  - `scion/scion/core/decision_finalizer.py:422`
  - `scion/scion/core/decision_finalizer.py:472`
  - `scion/scion/core/decision_finalizer.py:503`

Suggested fix direction:

- Add an explicit lifecycle-policy config section, even if defaults remain the
  same.
- Emit threshold values and current counter values into branch evidence summaries
  or status cards whenever lifecycle policy blocks or reroutes a branch.
- Add one integration test that constructs a campaign with non-default lifecycle
  thresholds and proves the values are honored through `EvaluationOrchestrator`.

### F-DECISION-002 [P3] Coordinator drops structured decision-layer provenance

`DecisionOutcome` has structured fields for `stage_decision`, `final_decision`,
`lifecycle_action`, `lifecycle_reason_codes`, and `decision_layer_source`.
`DecisionCoordinator` returns only the final decision, merged reason codes,
feature snapshot, rule, and lifecycle action. `EvaluationOrchestrator` then stores
only reason codes and lifecycle action.

This does not appear to break behavior because reason-code grouping reconstructs
many lifecycle observations later. The risk is auditability: when lifecycle policy
rewrites a stage `CONTINUE_EXPLORE` into final `ABANDON`, downstream records do
not retain the explicit stage-vs-final decision split unless they have direct
access to the raw `DecisionOutcome`.

Evidence:

- raw outcome has richer provenance:
  - `scion/scion/core/models.py:482`
  - `scion/scion/core/models.py:487`
  - `scion/scion/core/models.py:490`
  - `scion/scion/core/models.py:491`
- coordinator narrows the shape:
  - `scion/scion/core/decision_coordinator.py:11`
  - `scion/scion/core/decision_coordinator.py:39`
- orchestrator persists only reason codes and lifecycle action:
  - `scion/scion/core/evaluation_orchestrator.py:179`
  - `scion/scion/core/evaluation_orchestrator.py:180`
  - `scion/scion/core/evaluation_orchestrator.py:181`
- evidence later classifies merged codes but not the raw decision-layer source:
  - `scion/scion/core/reason_code_groups.py:111`
  - `scion/scion/core/evidence_recording/lineage.py:149`
  - `scion/scion/core/evidence_recording/summary.py:880`

Suggested fix direction:

- Extend `CoordinatedDecision` to carry the full provenance fields.
- Add optional `decision_layer_source`, `stage_decision`, `final_decision`, and
  `lifecycle_reason_codes` to `StepRecord` or evidence metadata.
- Keep merged reason codes for backward compatibility, but record the structured
  split for postmortem and gate debugging.

### F-DECISION-003 [P3] Candidate runtime-failure lifecycle reasons appear unreachable in the normal engine path

`DecisionEngine` runs `_runtime_veto(...)` before stage decisions and lifecycle
policy. Any `candidate_failed_pairs > 0` returns `CANDIDATE_RUNTIME_FAILURE`
immediately. `BranchLifecyclePolicy` separately contains candidate runtime-failure
soft-abandon and telemetry diagnostic reasons, and direct policy tests cover them.

This is not a safety problem; the normal path is stricter. The risk is
maintainability and diagnostic drift: direct `BranchLifecyclePolicy` behavior can
show lifecycle-specific candidate-runtime reason codes that the actual
`DecisionEngine` path will not emit.

Evidence:

- runtime veto preempts lifecycle:
  - `scion/scion/core/decision.py:56`
  - `scion/scion/core/decision.py:264`
  - `scion/scion/core/decision.py:321`
- lifecycle policy has candidate runtime-failure branches:
  - `scion/scion/core/branch_lifecycle_policy.py:542`
  - `scion/scion/core/branch_lifecycle_policy.py:565`
- tests cover both direct policy behavior and engine veto behavior:
  - `scion/scion/tests/unit/core/test_branch_lifecycle_policy.py:531`
  - `scion/scion/tests/test_decision_screening.py:35`

Suggested fix direction:

- If standalone `BranchLifecyclePolicy` use is intentional, add a comment or test
  documenting that the DecisionEngine path preempts these codes.
- Otherwise, simplify the lifecycle policy by removing unreachable runtime-failure
  branches and keeping runtime candidate failures exclusively in the engine veto.

## Open Questions

- Should lifecycle thresholds be part of `ProtocolConfig`, a new
  `BranchLifecycleConfig`, or campaign-level research-control config?
- Should lifecycle park/reclaim thresholds differ between automated LLM runs and
  human-guided debugging campaigns?
- Should evidence summaries include both "scheduler guidance only" runtime
  pressure and "decision feature" runtime pressure as separate counters?

## Verification

Focused tests run:

```text
pytest -q \
  scion/scion/tests/test_decision_screening.py \
  scion/scion/tests/test_decision_validation_frozen.py \
  scion/scion/tests/unit/core/test_branch_lifecycle_policy.py \
  scion/scion/tests/unit/core/test_decision_coordinator.py \
  scion/scion/tests/unit/core/test_decision_finalizer_park_lifecycle.py \
  scion/scion/tests/unit/core/test_decision_finalizer_rollback_lifecycle.py \
  scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py \
  scion/scion/tests/test_scheduler.py \
  scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py
```

Result: `164 passed in 0.68s`.
