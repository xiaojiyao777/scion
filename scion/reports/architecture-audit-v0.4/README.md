# Scion v0.4 Architecture Audit Notes

*Started: 2026-06-07*

This folder records the ongoing module-by-module architecture and code audit for
the current Scion v0.4 codebase.

## Ground Rules

- Treat existing engineering maps as indexes, not authoritative current facts.
- Re-check each module against current source before recording conclusions.
- Record only modules actually reviewed.
- Separate confirmed findings from questions that need follow-up.
- Keep Scion v3/v0.4 boundaries explicit:
  - LLM/proposal artifacts are tainted guidance.
  - Decision uses structured features, not free text.
  - Generic core must not absorb CVRP or solver-domain semantics.
  - Adapter/problem packages own domain facts, objective semantics, and runtime meanings.

## Severity

- P0: likely invalidates campaign evidence or promotion correctness.
- P1: likely breaks an important path or weakens an audit/control boundary.
- P2: semantic ambiguity, maintainability risk, or behavior needing confirmation.
- P3: documentation drift, naming confusion, or low-risk cleanup.

## Module Notes

| Module | File | Status |
|---|---|---|
| Campaign entry and outer loop | [01-campaign-entry-and-loop.md](01-campaign-entry-and-loop.md) | Initial pass |
| Explore step pipeline | [02-explore-step-pipeline.md](02-explore-step-pipeline.md) | Initial pass |
| Evaluation orchestrator | [03-evaluation-orchestrator.md](03-evaluation-orchestrator.md) | Initial pass |
| Decision finalizer | [04-decision-finalizer.md](04-decision-finalizer.md) | Initial pass |
| Promotion lifecycle/service/champion lineage | [05-promotion-lifecycle-service.md](05-promotion-lifecycle-service.md) | Initial pass |
| Evidence/status/summary/run validity | [06-evidence-status-summary-run-validity.md](06-evidence-status-summary-run-validity.md) | Initial pass |
| ProblemSpecV1 / ProblemAdapter boundary | [07-problem-spec-adapter-boundary.md](07-problem-spec-adapter-boundary.md) | Initial pass |
| ProposalPipeline / ContextManager / AgenticProposalSession | [08-proposal-pipeline-context-agentic-session.md](08-proposal-pipeline-context-agentic-session.md) | Initial pass |
| ContractGate and problem-owned contract checks | [09-contract-gate-problem-owned-checks.md](09-contract-gate-problem-owned-checks.md) | Initial pass |
| VerificationGate and runtime/adapter checks | [10-verification-gate-runtime-adapter-checks.md](10-verification-gate-runtime-adapter-checks.md) | Initial pass |
| ExperimentProtocol implementations / protocol-owned evaluation details | [11-experiment-protocol-evaluation-details.md](11-experiment-protocol-evaluation-details.md) | Initial pass |
| DecisionEngine / BranchLifecyclePolicy / lifecycle-aware scheduling | [12-decision-engine-branch-lifecycle-policy.md](12-decision-engine-branch-lifecycle-policy.md) | Initial pass |
| Runtime telemetry / telemetry guard / runtime feedback | [13-runtime-telemetry.md](13-runtime-telemetry.md) | Initial pass |
| Cross-module synthesis and remediation plan | [14-cross-module-synthesis.md](14-cross-module-synthesis.md) | Final synthesis |

## Open Audit Queue

- Module-by-module v0.4 architecture audit is complete for the selected scope.
- Remediation planning/implementation is tracked in
  [remediation-status.md](remediation-status.md), starting from
  [14-cross-module-synthesis.md](14-cross-module-synthesis.md).
- CVRP solver/design internals intentionally skipped for this audit track unless
  they are needed to explain a generic Scion boundary issue.

## Remaining Estimate

- Clear remaining modules from the current audit queue: 0.
- Suggested remaining audit rounds: 0.
