# Cross-Module Synthesis and Remediation Plan

## Scope

This is the final synthesis pass over the module audit notes in this folder:

- [01-campaign-entry-and-loop.md](01-campaign-entry-and-loop.md)
- [02-explore-step-pipeline.md](02-explore-step-pipeline.md)
- [03-evaluation-orchestrator.md](03-evaluation-orchestrator.md)
- [04-decision-finalizer.md](04-decision-finalizer.md)
- [05-promotion-lifecycle-service.md](05-promotion-lifecycle-service.md)
- [06-evidence-status-summary-run-validity.md](06-evidence-status-summary-run-validity.md)
- [07-problem-spec-adapter-boundary.md](07-problem-spec-adapter-boundary.md)
- [08-proposal-pipeline-context-agentic-session.md](08-proposal-pipeline-context-agentic-session.md)
- [09-contract-gate-problem-owned-checks.md](09-contract-gate-problem-owned-checks.md)
- [10-verification-gate-runtime-adapter-checks.md](10-verification-gate-runtime-adapter-checks.md)
- [11-experiment-protocol-evaluation-details.md](11-experiment-protocol-evaluation-details.md)
- [12-decision-engine-branch-lifecycle-policy.md](12-decision-engine-branch-lifecycle-policy.md)
- [13-runtime-telemetry.md](13-runtime-telemetry.md)

CVRP solver/design internals remain intentionally out of scope unless they
surface a generic Scion boundary issue.

## Executive Summary

No P0 issue was identified in this audit pass.

The core Scion v0.4 architecture is directionally sound:

- Proposal output is treated as tainted guidance.
- Contract, verification, protocol, decision, finalization, and evidence
  recording are separate stages.
- `DecisionFeatures` is structured and guarded against free text.
- Protocol evidence is case-level and deterministic on the main path.
- Telemetry and runtime signals are mostly generic, problem-declared, and
  surfaced to decision/feedback as structured fields.

The highest risk pattern is not a single bad module. It is cross-module
inconsistency:

- durable state can advance in one store while another durable surface misses
  the same fact;
- exception and compatibility paths can bypass the normal decision/evidence
  contract;
- problem/runtime facts are derived from one spec in the CLI path but can be
  mixed by direct construction;
- gate, lifecycle, and telemetry logic are correct locally but expose hidden or
  duplicated policy surfaces to the agent loop.

The recommended priority is to harden evidence durability first, then unblock
branch-local research context, then consolidate problem/runtime declarations and
gate policy.

## Priority Remediation Plan

### 1. Harden durable evidence, promotion, and terminal-status integrity [P1]

This is the most important remediation track. Several P1 findings share the
same failure mode: Scion can produce useful in-memory evidence while the durable
audit surfaces are incomplete, partially advanced, or misleading.

Related findings:

- [F-PROMOTE-001](05-promotion-lifecycle-service.md): promotion commit can
  partially advance durable champion state.
- [F-PROMOTE-002](05-promotion-lifecycle-service.md): champion
  `promotion_experiment_id` can point to a missing lineage row.
- [F-EVIDENCE-001](06-evidence-status-summary-run-validity.md): lineage write
  failures are invisible to run validity and formal readiness.
- [F-EVIDENCE-002](06-evidence-status-summary-run-validity.md): unexpected
  exceptions can bypass final campaign status and summary finalization.
- [F-FINALIZER-001](04-decision-finalizer.md): lifecycle archive/soft-abandon
  accounting depends on pre-finalizer branch state.
- [F-EVAL-001](03-evaluation-orchestrator.md): evaluation exceptions bypass
  `DecisionEngine` but are recorded like normal abandon decisions.

Target state:

- A campaign cannot end with a stale `running` status after an unhandled
  exception.
- A promotion cannot durably install a new champion without either completing
  branch/lineage state or leaving an explicit recovery marker.
- Lineage registry write failures are represented in run validity/status, not
  only debug logs.
- Evaluation exceptions are typed as evaluation failures, not normal decision
  outcomes.

Recommended work:

1. Add a campaign-level finalization guard around preflight and loop execution.
   Preserve the original exception, but write terminal status/summary with
   `stop_reason=unhandled_exception` or `preflight_exception`.
2. Track lineage write outcomes per step:
   `lineage_event_recorded`, `decision_lineage_recorded`, and redacted
   `lineage_recording_error`.
3. Make promotion commit phase-aware. Once the champion row is durable, later
   hook failures should enter committed-promotion recovery, not generic
   `decision=None` handling.
4. Persist a promotion commit marker or outbox entry before running mutable
   hooks. Use it to repair branch state and lineage idempotently on restart.
5. Make `DecisionFinalizer` abandon accounting lifecycle-aware so
   `archive_lineage`/`soft_abandon` does not accidentally count as hard abandon
   unless that is explicitly intended.

Tests to add first:

- fault-injection promotion tests for each hook after durable champion insert;
- registry failure tests for `record_event(...)` and `record_decision(...)`;
- protocol/evaluation exception test proving the resulting `StepRecord` has
  structured evaluation failure state;
- unhandled campaign exception test proving final status and summary are written.

### 2. Restore branch-local research context in the production explore path [P1]

One P1 finding is especially likely to block agent research without looking like
a system failure.

Related finding:

- [F-EXPLORE-001](02-explore-step-pipeline.md): `step_history` is not wired into
  `ExploreStepPipeline`.

Why this matters:

- same-branch repair can miss prior mechanism ids and touched files;
- patch contract can validate against stale base content instead of
  branch-current files;
- weak-positive follow-up and multi-file edits become harder than intended.

Recommended work:

1. Add `step_history` or a `get_step_history` callback to
   `ExploreStepPipeline`.
2. Wire it from `owner._step_history` in production composition and compatibility
   construction.
3. Add a production-style regression test where a branch-created file is used as
   `base_file_overrides` during a later same-branch patch contract check.

This should be fixed before tuning research policy. Without it, some policy
decisions may be acting on incomplete local branch context.

### 3. Build one coherent ProblemRuntimeBundle [P1/P2]

Multiple reports point to the same architecture gap: the CLI path builds a
coherent ProblemSpecV1-derived runtime configuration, but direct or fallback
paths can mix independently supplied pieces.

Related findings:

- [F-PROBLEM-001](07-problem-spec-adapter-boundary.md): production/runtime
  boundary validates presence, not one coherent ProblemSpecV1-derived bundle.
- [F-CONTRACT-003](09-contract-gate-problem-owned-checks.md): problem-owned
  provider consistency depends on legacy spec and adapter import path.
- [F-EVAL-003](03-evaluation-orchestrator.md): lazy adapter construction is not
  equivalent to the main composition path.
- [F-PROBLEM-002](07-problem-spec-adapter-boundary.md) and
  [F-PROTOCOL-001](11-experiment-protocol-evaluation-details.md): legacy
  objective fallback remains active for direct `ExperimentProtocol` use.
- [F-PROBLEM-004](07-problem-spec-adapter-boundary.md),
  [F-PROPOSAL-002](08-proposal-pipeline-context-agentic-session.md), and
  [F-CONTRACT-001](09-contract-gate-problem-owned-checks.md): generic proposal
  and contract layers still hardwire solver-design/algorithm-smoke semantics.

Target state:

- One runtime object derived from `ProblemSpecV1` carries:
  - v1 problem spec;
  - legacy compatibility spec, if still needed;
  - adapter;
  - metric specs;
  - objective policy;
  - operator execute signature;
  - active-subject provider;
  - contract provider;
  - telemetry declarations;
  - relevant SCION environment/cache identity digest.
- `CampaignManager`, contract gate, verification gate, protocol, proposal
  context, and lazy-adapter paths consume that bundle instead of independently
  reconstructing pieces.
- Direct compatibility paths must opt in explicitly to legacy semantics.

Recommended work:

1. Introduce `ProblemRuntimeBundle` or extend `ProblemSpecBridge` into the
   production runtime carrier.
2. Make production boundary verify identity, not just presence:
   adapter problem id, protocol metric specs, objective policy, operator
   signature, and problem spec all match.
3. Replace solver-design hardwiring in generic proposal/contract surfaces with
   problem-owned provider registration.
4. Make legacy objective fallback require explicit
   `allow_legacy_objective_fallback=True` and emit
   `objective_semantics=legacy_all_minimize` in protocol evidence.
5. Add direct-construction negative tests that intentionally mix adapters,
   metric specs, and problem ids and assert production boundary failure.

### 4. Make gates and lifecycle policy configurable and explainable [P2]

The gate stack is intentionally strict, which is good for protecting evidence.
The main usability risk is that strictness is spread across hard-coded defaults,
private flags, and lifecycle counters that are not always visible enough to the
agent.

Related findings:

- [F-VERIFICATION-003](10-verification-gate-runtime-adapter-checks.md): runtime
  gate budgets are hardcoded and can block valid research independent of
  protocol config.
- [F-DECISION-001](12-decision-engine-branch-lifecycle-policy.md): branch
  lifecycle thresholds are hard-coded and can become hidden research gates.
- [F-CONTRACT-002](09-contract-gate-problem-owned-checks.md): `C10_novelty`
  duplicate detection is diagnostic/pass, not a hard contract block.
- [F-VERIFICATION-005](10-verification-gate-runtime-adapter-checks.md):
  validation/frozen eval steps reuse screening verification instead of rerunning
  V1-V9.
- [F-VERIFICATION-002](10-verification-gate-runtime-adapter-checks.md): V9
  performance guard fails open when the champion run is unavailable or invalid.

Recommended work:

1. Add explicit config objects for verification runtime budgets and lifecycle
   thresholds. Defaults can remain unchanged.
2. Include active threshold values and current counter values in branch evidence
   summaries whenever lifecycle or verification policy blocks/reroutes a branch.
3. Decide whether novelty duplication should hard-block in the formal contract
   path. If it remains diagnostic, surface that as an intentional research
   policy, not an accidental pass.
4. Split verification evidence by stage or rerun the relevant strict checks
   before validation/frozen decisions.
5. Record V9 champion-unavailable as a structured inconclusive/performance
   evidence status rather than a silent pass-open path.

### 5. Unify runtime telemetry declarations and feedback semantics [P2/P3]

Runtime telemetry is one of the most important agent guidance surfaces. The
current implementation is strong locally, but it has duplicated declaration
logic and a few projection mismatches.

Related findings:

- [F-RUNTIME-TELEMETRY-001](13-runtime-telemetry.md): runtime telemetry
  declaration extraction is split and can drift.
- [F-RUNTIME-TELEMETRY-002](13-runtime-telemetry.md) and
  [F-PROTOCOL-002](11-experiment-protocol-evaluation-details.md): runtime audit
  and surface runtime summary disagree on false `*_active` fields.
- [F-RUNTIME-TELEMETRY-003](13-runtime-telemetry.md): runtime budget saturation
  is side-blind but guidance is candidate-directed.
- [F-VERIFICATION-004](10-verification-gate-runtime-adapter-checks.md): durable
  verification audit drops `detail` for most checks.

Recommended work:

1. Make one telemetry declaration module the source of truth for protocol,
   guard, contract, previews, and feedback.
2. Add parity tests covering required, optional, activity, activation, effect,
   budget, phase runtime, mechanism templates, and role maps.
3. Align surface runtime summary boolean failure semantics with runtime audit,
   including `*_active`.
4. Add side-specific runtime budget diagnostics:
   `candidate_runtime_budget_saturation`, `champion_runtime_budget_saturation`,
   and `both_sides_runtime_budget_saturation`.
5. Preserve concise verification and telemetry detail in durable audit records
   so agent feedback can explain why a gate blocked without reading raw logs.

### 6. Clarify decision, reason-code, and status provenance [P2/P3]

Several modules work correctly only because downstream consumers reinterpret
merged codes. That is brittle.

Related findings:

- [F-EVAL-002](03-evaluation-orchestrator.md): `decision_reason_codes` mixes
  decision reasons, diagnostics, and bypass reasons.
- [F-DECISION-002](12-decision-engine-branch-lifecycle-policy.md): coordinator
  drops structured decision-layer provenance.
- [F-EVIDENCE-003](06-evidence-status-summary-run-validity.md):
  `partial_in_flight` conflates incomplete campaign evidence with an actual
  in-flight protocol.
- [F-EVIDENCE-004](06-evidence-status-summary-run-validity.md): evidence
  snapshot generation can mutate campaign state.
- [R-CORE-001](01-campaign-entry-and-loop.md): scheduler documentation drift.
- [R-CORE-002](01-campaign-entry-and-loop.md): round-count terminology is
  operationally easy to misread.

Recommended work:

1. Split reason-code namespaces:
   - decision engine reason codes;
   - post-decision diagnostics;
   - bypass/framework failure codes;
   - lifecycle action codes;
   - proposal guidance codes.
2. Extend coordinated decision output and step records with
   `stage_decision`, `final_decision`, `decision_layer_source`, and
   `lifecycle_reason_codes`.
3. Rename or split `partial_in_flight` into `partial_campaign_evidence` and
   `protocol_in_flight`.
4. Make read-only evidence/status projections non-mutating.
5. Update scheduler and round-count docs after the structured provenance changes
   land.

### 7. Centralize proposal tool and preview policy [P2/P3]

Proposal-side safety exists, but it is enforced by multiple consumers rather
than by one policy projection.

Related findings:

- [F-PROPOSAL-001](08-proposal-pipeline-context-agentic-session.md): context/tool
  exposure safety is enforced per consumer, not at the proposal boundary.
- [F-PROPOSAL-003](08-proposal-pipeline-context-agentic-session.md): tool phase
  policy is implicit and spread across registry, policy, planner, and fallback
  previews.
- [F-PROPOSAL-004](08-proposal-pipeline-context-agentic-session.md): direct
  agentic-session injection can bypass production-anchor preflight if callers
  forget the flag.
- [F-CONTRACT-004](09-contract-gate-problem-owned-checks.md): contract previews
  and direct patch validation can skip stateful or hypothesis-bound checks.
- [F-CONTRACT-005](09-contract-gate-problem-owned-checks.md): active-subject
  policy lookup can fail open for some auxiliary checks.
- [F-VERIFICATION-001](10-verification-gate-runtime-adapter-checks.md): production
  custom gates are accepted by private flags, not verified behavior.

Recommended work:

1. Generate one proposal tool exposure plan at the proposal boundary and pass
   that immutable plan to prompt building, planner specs, registry execution,
   and previews.
2. Make production anchor preflight opt-out impossible for production sessions,
   or make bypass explicit in the session construction API and audit metadata.
3. Distinguish preview-only checks from formal stateful checks in tool results.
4. Replace private production flags for custom gates with a public, tested
   registration interface and behavior contract.

## Suggested Implementation Sequence

### Milestone A: Evidence Integrity

Primary goal: prevent misleading durable outcomes.

- Fix campaign exception finalization.
- Add lineage write outcome tracking.
- Add promotion phase marker/outbox or transaction boundary.
- Make evaluation exceptions structured failures.

Exit criteria:

- fault-injection tests prove no normal-looking abandon/promotion is recorded
  after infrastructure failure;
- run validity/status show lineage degradation;
- restart can detect and repair or clearly report partial promotion state.

### Milestone B: Agent Research Context

Primary goal: avoid accidental agent blockage on same-branch work.

- Wire `step_history` into `ExploreStepPipeline`.
- Add visible lifecycle/runtime threshold metadata to branch evidence/status.
- Preserve detailed verification failure summaries.

Exit criteria:

- same-branch file overrides are available through production construction;
- an agent-facing status card can explain why a lifecycle/gate policy blocked
  the branch and which threshold was hit.

### Milestone C: Problem Boundary Consolidation

Primary goal: make core-vs-problem ownership mechanically enforceable.

- Add `ProblemRuntimeBundle`.
- Move solver-design/algorithm-smoke hardwiring behind problem-owned providers.
- Make direct legacy objective fallback explicit.

Exit criteria:

- production boundary rejects mixed problem/adapters/metric specs;
- generic core can route non-CVRP surfaces without solver-design names;
- direct compatibility modes leave explicit evidence markers.

### Milestone D: Telemetry and Gate Semantics

Primary goal: make runtime telemetry a single source of truth.

- Unify telemetry declaration extraction.
- Align `*_active` summary failure semantics.
- Add side-specific runtime budget diagnostics.
- Decide and document expected `phase_runtime_fields` semantics.

Exit criteria:

- parity tests cover declaration extraction;
- runtime audit, protocol summary, guard summary, and feedback agree on the
  same declared fields and failure statuses.

### Milestone E: Provenance and Docs

Primary goal: reduce operational ambiguity after the fixes.

- Split reason-code namespaces.
- Persist decision-layer provenance.
- Rename ambiguous status labels.
- Update scheduler/round-count docs.

Exit criteria:

- postmortem can tell whether a code came from decision, diagnostic, bypass,
  lifecycle, or proposal guidance without string heuristics.

## Finding Index

### P1

- F-EXPLORE-001: `step_history` not wired into `ExploreStepPipeline`.
- F-EVAL-001: evaluation exception path bypasses `DecisionEngine` but records a
  normal-looking abandon.
- F-FINALIZER-001: lifecycle archive/soft-abandon accounting depends on
  pre-finalizer branch state.
- F-PROMOTE-001: promotion commit can partially advance durable champion state.
- F-PROMOTE-002: champion `promotion_experiment_id` can point to a missing
  lineage row.
- F-EVIDENCE-001: lineage write failures are invisible to run validity and
  formal readiness.
- F-EVIDENCE-002: unexpected exceptions can bypass final campaign status and
  summary finalization.
- F-PROBLEM-001: production/runtime boundary validates presence, not one
  coherent ProblemSpecV1-derived bundle.

### P2 Clusters

- Problem/runtime coherence and core boundary drift:
  F-PROBLEM-002, F-PROBLEM-003, F-PROBLEM-004, F-PROPOSAL-002,
  F-CONTRACT-001, F-CONTRACT-003, F-EVAL-003, F-PROTOCOL-001.
- Gate and lifecycle explainability:
  F-CONTRACT-002, F-VERIFICATION-002, F-VERIFICATION-003,
  F-VERIFICATION-004, F-VERIFICATION-005, F-DECISION-001.
- Runtime telemetry and evidence projection:
  F-PROTOCOL-002, F-RUNTIME-TELEMETRY-001, F-RUNTIME-TELEMETRY-002.
- Decision/evidence provenance:
  F-EVAL-002, F-FINALIZER-002, F-FINALIZER-003, F-EVIDENCE-003,
  F-EVIDENCE-004.
- Proposal/tool safety policy:
  F-PROPOSAL-001, F-PROPOSAL-003.
- Protocol/champion runtime evidence:
  F-PROTOCOL-003, F-PROTOCOL-004.

### P3 Cleanup

- Documentation and terminology drift:
  R-CORE-001, R-CORE-002.
- Direct/preview compatibility risks:
  F-PROPOSAL-004, F-CONTRACT-004, F-CONTRACT-005, F-VERIFICATION-001.
- Runtime/decision projection cleanup:
  F-DECISION-002, F-DECISION-003, F-PROTOCOL-005,
  F-RUNTIME-TELEMETRY-003.

## Final Assessment

The codebase has the right architectural bones for Scion v0.4. The important
next step is not broad refactoring. It is making the main invariants mechanical:

- durable evidence must either commit together or report degraded integrity;
- decision and bypass paths must be distinguishable in structured records;
- problem-owned facts must enter core through one runtime bundle and provider
  surface;
- gates and telemetry must expose the thresholds and declared fields they use.

Once those are fixed, later feature work should be less likely to silently
weaken evidence quality or trap the agent in a hard-to-explain research loop.

## Verification

No code was changed in this synthesis pass. Verification consisted of reviewing
the existing module reports and their recorded focused-test results.
