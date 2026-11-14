# Evaluation Orchestrator

## Scope

Current source reviewed:

- `scion/scion/core/evaluation_orchestrator.py`
- `scion/scion/core/evaluation_pipeline.py`
- `scion/scion/core/features.py`
- `scion/scion/core/decision_coordinator.py`
- `scion/scion/core/decision.py`
- selected lifecycle policy paths in `branch_lifecycle_policy.py`
- selected call sites in `campaign.py`, `campaign_adapters.py`,
  `campaign_composition.py`, and `branch_step_runner.py`
- selected tests in:
  - `scion/scion/tests/unit/core/test_evaluation_pipeline.py`
  - `scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py`
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py`

## Current Understanding

`EvaluationOrchestrator.evaluate(...)` owns the evaluation boundary between an
already verified candidate workspace and deterministic decision.

High-level flow:

```text
branch + workspace + hypothesis
  -> select stage from BranchController
  -> lock champion snapshot and stamp branch weight_revision
  -> frozen-budget pre-check for frozen stage
  -> build EvaluationRequest
  -> EvaluationPipeline runs canary + protocol experiment
  -> increment experiment/budget counters only for effective screened results
  -> increment telemetry failure counter for formal telemetry guard failures
  -> add lifecycle inputs to DecisionFeatures
  -> DecisionCoordinator / DecisionEngine / BranchLifecyclePolicy
  -> store decision reason codes and lifecycle action
  -> append post-decision diagnostic codes for telemetry effect-zero/runtime budget
```

`EvaluationPipeline` is the protocol execution shell. It creates default-pass
contract/verification results for this eval-only path, runs canary and
experiment when a protocol exists, annotates telemetry/runtime diagnostics, then
calls `SafeFeatureExtractor`.

`SafeFeatureExtractor` is the narrowing boundary from raw protocol output to
`DecisionFeatures`. It extracts numeric/enum fields, pair counts, runtime
evidence, telemetry flags, and budget ratio, then validates that the result does
not carry free text. `DecisionEngine.decide(...)` repeats that validation before
applying deterministic stage and lifecycle rules.

## Positive Boundary Observations

- Decision input is narrow and re-validated. `SafeFeatureExtractor.extract(...)`
  validates `DecisionFeatures`, and `DecisionEngine.decide(...)` validates them
  again before any decision rule runs.
- Validation/frozen protocol exposure is sanitized before feature extraction:
  per-pair and per-case feedback are stripped while aggregate stats, runtime,
  cache, and telemetry summaries remain. Tests cover this behavior.
- `selected_surface`, `expected_telemetry`, `mechanism_changes`, and
  `protected_objectives` are forwarded to protocols only when supported by the
  protocol method signature. `selected_surface` is additionally gated on the
  protocol exposing problem research surfaces.
- Repairable telemetry validation failures do not count as effective screened
  experiments or budget usage. Tests cover the non-counting behavior.
- Frozen budget is consumed before a frozen protocol attempt, and exhaustion
  produces a synthetic frozen `ProtocolResult` with a frozen-budget failure
  stage in the recorded step.
- Lifecycle policy ownership is clear in the main path: orchestrator injects
  lifecycle inputs and stores lifecycle action, but it does not run a second
  post-decision lifecycle policy. A unit test locks this boundary.

## Risks And Findings

### F-EVAL-001 [P1] Evaluation exception path bypasses DecisionEngine but records a normal-looking abandon

If `EvaluationPipeline.evaluate(...)` or protocol execution raises an exception,
`EvaluationOrchestrator` catches it, calls `handle_failure(...)`, stores
`("EVALUATION_FAILED",)`, and returns:

```text
Decision.ABANDON, protocol_result=None, CanaryResult(passed=True, reason="evaluation failed")
```

Evidence:

- `scion/scion/core/evaluation_orchestrator.py:160`
- `scion/scion/core/evaluation_orchestrator.py:163`
- `scion/scion/core/evaluation_orchestrator.py:164`
- `scion/scion/core/evaluation_orchestrator.py:165`
- `scion/scion/core/branch_step_runner.py:293`
- `scion/scion/core/branch_step_runner.py:307`
- `scion/scion/core/branch_step_runner.py:517`
- `scion/scion/core/models.py:667`

Why this matters:

- The returned `Decision.ABANDON` did not come from `DecisionEngine`.
- The returned canary says `passed=True`, even though evaluation failed.
- `BranchStepRunner._eval_failure_detail(...)` only derives a failure stage from
  frozen-budget protocol reason codes. With `protocol_result=None`, the
  recorded `StepRecord` gets no evaluation failure stage/detail.
- `StepRecord` documentation says a real `decision` means the step reached the
  Decision Engine; this path violates that evidence contract.

Impact:

- Run history can make an infrastructure/protocol exception look like a normal
  deterministic abandon.
- Downstream summaries, stagnation analysis, feedback generation, and audit
  tooling must infer the failure from `decision_reason_codes` instead of the
  structured `failure_stage`.

Suggested fix direction:

- Represent this as a structured evaluation failure, for example with
  `failure_stage="evaluation"` and a failing canary or synthetic protocol result.
- Keep `decision=None` if the invariant remains "decision is real only when
  DecisionEngine ran", or rename the field/contract if synthetic framework
  decisions are allowed.
- Add a regression test where protocol `run_experiment` raises and assert the
  resulting `StepRecord` cannot be mistaken for a normal protocol/decision path.

### F-EVAL-002 [P2] `decision_reason_codes` now mixes decision reasons, diagnostics, and bypass reasons

`EvaluationOrchestrator` first stores `coordinated.reason_codes`, then appends
post-decision telemetry effect-zero and runtime-budget diagnostic codes. It also
uses the same mapping for frozen-budget exhaustion and evaluation exception
paths, both of which bypass `DecisionCoordinator`.

Evidence:

- `scion/scion/core/evaluation_orchestrator.py:106`
- `scion/scion/core/evaluation_orchestrator.py:163`
- `scion/scion/core/evaluation_orchestrator.py:180`
- `scion/scion/core/evaluation_orchestrator.py:186`
- `scion/scion/core/evaluation_orchestrator.py:191`
- `scion/scion/core/models.py:670`
- `scion/scion/core/models.py:686`
- `scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py:759`
- `scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py:1025`

Why this matters:

- Tests show this is intentional for telemetry/runtime diagnostics, so this is
  not a simple implementation bug.
- The field name and `StepRecord` comments still claim these are DecisionEngine
  reason codes.
- Consumers may treat all codes as deterministic decision reasons even when
  some are post-decision diagnostics or pre-decision framework/budget bypasses.

Impact:

- Evidence summaries can blur "why the DecisionEngine chose X" with "what
  diagnostics were attached to this evaluated candidate".
- Future policy code may accidentally branch on diagnostic codes as if they were
  decision-layer reasons.

Suggested fix direction:

- Split the concept into `decision_reason_codes` and `diagnostic_reason_codes`,
  or rename the stored/step-level field to something broader like
  `outcome_reason_codes`.
- If a split is too large, update model comments and evidence docs so consumers
  know the field includes DecisionEngine, lifecycle, diagnostics, and bypass
  codes.

### F-EVAL-003 [P2] Lazy adapter construction is not equivalent to the main composition path

The main `campaign_composition.py` path constructs `EvaluationOrchestrator` with
telemetry diagnostic streak storage, frozen budget ledger, and production
`require_experiment_protocol`. The compatibility `_evaluation_orchestrator_for`
fallback in `campaign_adapters.py` omits those fields.

Evidence:

- Complete main construction:
  - `scion/scion/core/campaign_composition.py:421`
  - `scion/scion/core/campaign_composition.py:423`
  - `scion/scion/core/campaign_composition.py:454`
  - `scion/scion/core/campaign_composition.py:455`
- Incomplete fallback construction:
  - `scion/scion/core/campaign_adapters.py:318`
  - `scion/scion/core/campaign_adapters.py:330`
  - `scion/scion/core/campaign_adapters.py:347`

Why this matters:

- The normal `CampaignManager` composition path appears complete.
- The fallback path is still a callable construction path used by
  `_evaluation_orchestrator_for(owner)` when `owner._evaluation_orchestrator`
  does not already exist.

Impact if fallback is triggered:

- Frozen budget exhaustion would not be enforced by `EvaluationOrchestrator`.
- Production no-protocol fail-closed behavior could be disabled.
- Telemetry diagnostic streaks would use the orchestrator default dict rather
  than the campaign-owned `_branch_telemetry_diagnostic_streaks`.

Suggested fix direction:

- Either remove the lazy fallback if main composition is mandatory, or keep the
  fallback constructor field-for-field equivalent to the production constructor.
- Add a small test for `_evaluation_orchestrator_for(stub_owner)` that asserts
  frozen budget ledger, production protocol requirement, and telemetry
  diagnostic streak mapping are wired when present on the owner.

## Open Questions

- Should frozen-budget exhaustion remain a pre-decision bypass, or should it be
  modeled as a structured DecisionFeature/DecisionEngine outcome?
- Should evaluation exceptions be hard-abandon failures, retryable infra
  failures, or synthetic canary failures? The current path mixes parts of all
  three.
- Which downstream consumers truly need post-decision diagnostic codes in the
  same tuple as decision reasons?
- Is the compatibility adapter path still supported for real callers, or can it
  be simplified now that `campaign_composition.py` builds the orchestrator
  eagerly?
