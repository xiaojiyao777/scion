# Agentic Proposal Reference

This directory distills Claude Code production-agent design patterns into a
Scion-specific reference for upgrading the current two-call proposal path
(`hypothesis -> code`) into an Agentic Proposal Session.

The target is not to turn Scion into a general coding agent. The target is to
make Scion's tainted Creative Layer more capable while preserving the v3
invariants:

- LLM output is tainted.
- Contract, Verification, Protocol, and Decision remain separate control
  surfaces.
- Decision reads only bounded `DecisionFeatures`, never free-text proposal
  memory.
- Validation/frozen detail remains hidden from the proposal loop except through
  aggregate, exposure-controlled summaries.
- Candidate code enters the campaign only as a patch proposal that must pass the
  normal gates.

## Reference Value For Scion

Claude Code is useful as a production reference because it treats an agent as a
state machine around model calls, tools, permissions, message history, compaction,
failure recovery, and task coordination. That is exactly the missing layer
between Scion's current single-shot proposal calls and a future proposal agent
that can inspect surfaces, reason over failures, draft alternatives, and return a
bounded proposal.

The main lesson is architectural: agentic capability belongs inside Scion's
Creative Layer, not across the whole campaign. The agent may explore, summarize,
and draft. It must not directly promote, mutate champion state, read forbidden
holdout detail, or smuggle free text into `DecisionFeatures`.

## Documents

- `01-agent-loop-and-state.md`: proposal-session state machine, turn structure,
  termination, compaction, resume.
- `02-tool-model.md`: tool schema, permission classes, tool results, errors,
  retry, concurrency, and Scion Creative Layer tool mapping.
- `03-context-and-memory.md`: context views, memory, compaction, exposure
  control, and proposal-memory isolation from Decision.
- `04-scion-agentic-proposal-design-implications.md`: minimum viable Scion
  design, CVRP workflow, output schema, permission boundary, and extension
  points.
- `05-claude-code-source-reference-for-scion-v3.md`: source-inspection-backed
  reference for repairing Scion's active solver grounding, tool protocol,
  structured patch output, patch-set graph validation, and context projection.

## Sources Read

Claude Code analysis documents read:

- `/home/clawd/research/claude-code-src/analysis/00-summary.md`
- `/home/clawd/research/claude-code-src/analysis/01-overall-architecture.md`
- `/home/clawd/research/claude-code-src/analysis/02-query-engine.md`
- `/home/clawd/research/claude-code-src/analysis/04-compact-core.md`
- `/home/clawd/research/claude-code-src/analysis/05-microcompact-token.md`
- `/home/clawd/research/claude-code-src/analysis/06-query-context-management.md`
- `/home/clawd/research/claude-code-src/analysis/07-comprehensive-context-management.md`
- `/home/clawd/research/claude-code-src/analysis/07-error-handling.md`
- `/home/clawd/research/claude-code-src/analysis/08-output-parsing-design.md`
- `/home/clawd/research/claude-code-src/analysis/09-orchestration-and-meta-control.md`
- `/home/clawd/research/claude-code-src/analysis/11-tool-system.md`
- `/home/clawd/research/claude-code-src/analysis/12-memory-and-compact-deep.md`
- `/home/clawd/research/claude-code-src/analysis/13-tasks-and-coordination.md`
- `/home/clawd/research/claude-code-src/analysis/15-commands-hooks-state.md`

Scion design/code-map documents read:

- `/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md`
- `/home/clawd/research/or-autoresearch-agent/scion/design/scion-v0.3-design.md`
- `/home/clawd/research/or-autoresearch-agent/scion/design/v0.4/v0.4-design.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/status/current-state.md`
- `/home/clawd/research/or-autoresearch-agent/scion/design/v0.4/v0.4-cvrp-research-surface-design.md`
- `/home/clawd/research/or-autoresearch-agent/scion/design/v0.4/v0.4-algorithm-design-space-optimization.md`
- `/home/clawd/research/or-autoresearch-agent/scion/design/v0.4/v0.4-p0-campaign-controller-decomposition-design.md`
- `/home/clawd/research/or-autoresearch-agent/scion/design/v0.4/v0.4-p1-runtime-aware-optimization-design.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/engineering/framework-code-map/README.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/engineering/framework-code-map/02-proposal-context.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/engineering/framework-code-map/03-evaluation-decision.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/engineering/framework-code-map/04-evidence-lineage.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/engineering/framework-code-map/05-problem-adapter-boundary.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/engineering/framework-code-map/06-cvrp-package-map.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/engineering/framework-code-map/07-extension-points-and-risks.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/archive/v0.2/understanding/00-architecture-overview.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/archive/v0.2/understanding/02-three-layer-isolation.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/archive/v0.3/v0.3-engineering-assessment.md`

## Claude Code Source Read

Documents `01` through `04` were based on the analysis documents only. Document
`05` includes source-inspection conclusions delegated to subagents, at the
user's request, while preserving the Scion boundary that the main design work
uses those findings as references rather than copying a general coding-agent
execution model.
