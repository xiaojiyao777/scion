# Agentic Runtime Refactor Plan

*Date: 2026-06-13*
*Status: Planning and test-prep only; no runtime behavior change*
*Scope: `scion/scion/proposal/agentic_session_*`,
`scion/scion/proposal/tools/`, and proposal-pipeline integration points*
*Architecture baseline: `scion/design/scion-architecture-v3.md`*

## Purpose

Scion's agentic proposal session has reached a modularity limit. The current
implementation has many focused files, but the runtime is still assembled as a
large mixin class and driven by a single synchronous orchestration method.

This plan prepares a staged refactor that borrows agent-runtime structure from
minimal coding-agent harnesses such as Pi without turning Scion into a generic
agent framework. Scion remains a controlled optimization-research framework:
LLM output is proposal-only and tainted, while Contract, Verification,
Protocol, Safe Feature extraction, and Decision stay deterministic.

## Non-Goals

- Do not replace Scion APS with Pi or any external agent runtime.
- Do not introduce generic `read` / `write` / `bash` tools into the proposal
  layer.
- Do not change campaign scheduling, promotion, or DecisionFeatures inputs.
- Do not expose validation/frozen detail, raw metrics refs, or promotion
  lineage to proposal prompts.
- Do not change existing artifact schemas until replay compatibility tests are
  in place.

## Current Pressure Points

- `AgenticProposalSession` is composed from many mixins, but all mixins share
  a broad import surface through `agentic_session_common.py`.
- `AgenticProposalSession.run()` owns phase sequencing, early exits, tool-loop
  setup, hypothesis generation, code generation, preview repair, and output
  finalization.
- Tool-call execution currently mixes budget accounting, repeated-call fuses,
  timeout handling, registry dispatch, result compaction, transcript metadata,
  evidence ledger writes, and scratch artifact writes.
- Planner tool selection mixes model-selected calls, deterministic fallback,
  required-context completion, budget reservation, and code-phase deferral.
- Session transcript events exist, but there is no explicit event stream or
  subscriber boundary that can be reused by campaign logs, TUI surfaces, or
  artifact writers.

## Runtime Shape To Extract

The target is a small Scion-owned runtime kernel, not a product-level agent:

```text
AgenticProposalSession facade
  -> ScionAgentRuntime
     -> RuntimeState
     -> RuntimeEventSink
     -> ContextTransformer
     -> ToolSelectionLoop
     -> ProposalToolExecutor
     -> ArtifactSink
```

### RuntimeState

The existing `AgenticProposalSessionState` is the starting point. Keep the
session id, campaign id, branch id, transcript, ledgers, counters, wall-clock
budget, observation budget, and repeated-call fuse state. Additive refactors
may wrap it, but should not remove fields that replay and audit already use.

### RuntimeEventSink

Convert `state.note(...)` from an implementation detail into a stable event
source. Initial event names should be narrow:

- `session_start`
- `phase_start`
- `model_call_start`
- `model_call_end`
- `tool_call_start`
- `tool_call_end`
- `artifact_written`
- `session_end`

For the first stage, every emitted event should still append an
`AgenticTranscriptEvent` so existing artifacts remain unchanged.

### ContextTransformer

Create an explicit pipeline for prompt-visible context:

```text
raw session/campaign inputs
  -> exposure policy filter
  -> observation compaction
  -> prompt manifest accounting
  -> model-facing payload
```

This layer owns prompt-visible shape only. It must not decide branch lifecycle,
promotion, or experiment scheduling.

### ProposalToolExecutor

Move tool-call boundary logic out of the session mixins behind an executor with
three phases:

- `before_tool_call`: phase policy, permission checks, budget checks, repeated
  call fuse, timeout reserve checks.
- `execute_tool`: call `ProposalToolRegistry.call(...)`.
- `after_tool_call`: sanitize, compact, record ledger entries, emit events,
  write scratch artifacts, update budget counters.

`ProposalToolRegistry` remains the registry and schema/permission call
boundary. The executor should not weaken its read-only restriction.

### ToolSelectionLoop

Extract the planner loop into a deterministic loop controller. The creative
layer may suggest the next tool call or stop signal. The loop controller owns
allowed-tool enforcement, required-context completion, fallback selection,
budget reservation, and termination reasons.

### ArtifactSink

Keep artifact writes append-only and tainted. The first extraction should only
centralize existing calls. Artifact schema changes require a separate replay
migration plan.

## Staging Plan

### Stage 0: Preparation

- Add guard tests for current runtime boundaries.
- Document the refactor boundaries and non-goals.
- Do not change runtime code while other agents are actively using Scion.

### Stage 1: Event Sink

- Add a `RuntimeEvent` model and `RuntimeEventSink` protocol.
- Route `state.note(...)` through a default sink that preserves the current
  transcript.
- Add tests proving old transcript artifacts are unchanged for a representative
  APS run.

### Stage 2: Tool Executor

- Extract `_call_tool(...)` behavior into `ProposalToolExecutor`.
- Preserve all current metadata keys used by transcript, ledger, and artifact
  tests.
- Keep `ProposalToolRegistry` as the only tool schema/permission boundary.

### Stage 3: Context Transformer

- Extract prompt-visible context shaping and compaction from APS helper calls.
- Preserve prompt manifest accounting and forbidden raw-ref filtering.
- Keep validation/frozen exposure rules unchanged.

### Stage 4: Tool Selection Loop

- Extract planner selection and deterministic fallback into `ToolSelectionLoop`.
- Preserve existing stop reasons and failure categories.
- Add branch-local replay tests for malformed planner payloads, invalid tool
  selection, repeated-call fuse, and missing required context.

### Stage 5: Session Orchestration

- Replace the mixin-driven `run()` internals with runtime phase calls.
- Keep `AgenticProposalSession.run(request) -> AgenticProposalOutput` stable.
- Keep campaign-facing `ProposalPipeline` integration stable.

## Test Preparation Matrix

Before runtime extraction begins, the following tests should exist or be
strengthened:

| Boundary | Guard |
|---|---|
| Creative output remains tainted | `AgenticProposalOutput` has proposal fields, not decision/scheduling fields |
| Tool registry remains constrained | registry rejects non-read-only tools |
| Model-selectable tools stay bounded | framework preview tools and holdout summary are not planner-selectable |
| Transcript remains replayable | runtime events still append `AgenticTranscriptEvent` |
| Artifact compatibility | existing replay validation accepts old and new event plumbing |
| Exposure control | validation/frozen/raw refs are denied before prompt rendering |
| Budget control | repeated-call fuse, tool-call count, observation chars, and wall-time stops keep existing reason codes |

## Quiescence Barrier

Runtime extraction should wait until the active campaign/agent batch stops
creating proposal session artifacts. At that point:

1. Record the current commit and artifact directory being used by active runs.
2. Run the existing APS characterization suite.
3. Start the refactor on a dedicated branch/worktree.
4. Keep Stage 1 and Stage 2 changes additive until all current artifact replay
   tests pass.

## Acceptance Criteria

- Existing APS and proposal-pipeline tests pass.
- Existing agentic session artifacts continue to validate and replay.
- `AgenticProposalSession.run(...)` remains the public facade during the
  staged refactor.
- Decision layer still reads deterministic feature objects only.
- No generic framework layer imports problem-owned CVRP/warehouse/TSP
  semantics.
- No proposal prompt receives validation/frozen raw detail or promotion-only
  lineage.

