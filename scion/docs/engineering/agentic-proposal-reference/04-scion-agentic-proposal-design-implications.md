# Scion Agentic Proposal Design Implications

## Minimum Viable Design

Add an `AgenticProposalSession` behind `ProposalPipeline`, not beside the
campaign controller.

```text
Campaign/BranchStepRunner
-> ProposalPipeline.generate_agentic_proposal(branch)
-> AgenticProposalSession
-> AgenticProposalOutput
-> existing ContractGate / WorkspaceLifecycle / Verification / Protocol / Decision
```

The session replaces the single-shot Creative Layer behavior only up to the
proposal boundary. Everything after `PatchProposal` remains governed by existing
Scion layers.

## Session Phases

Minimum phases:

1. `orient`: load problem summary, surfaces, objective policy, champion state.
2. `diagnose`: read allowed screening/runtime/search-memory feedback.
3. `choose_surface`: pick one declared research surface and action.
4. `draft_hypothesis`: produce a typed hypothesis.
5. `inspect_interface`: read target surface interface/current file.
6. `draft_patch`: produce complete file content.
7. `self_check`: run schema and contract-preview checks only.
8. `finalize`: emit final structured output.

The session can loop inside phases 2-6 within budgets. It must not run
VerificationGate, ExperimentProtocol, or DecisionEngine as tools.

## Output Schema

Recommended final schema:

```text
AgenticProposalOutput
- status:
  completed | partial_hypothesis_only | partial_patch_unchecked | failed
- session_id
- branch_id
- champion_version
- selected_surface
- action
- hypothesis: HypothesisProposalInput?
- patch: PatchProposalInput?
- rationale_summary
- evidence_used:
  - observation_id
  - exposure_level
  - summary
- rejected_alternatives[]
- self_check:
  schema_valid: bool
  contract_preview_passed: bool | null
  contract_preview_codes: list[str]
- tainted_artifact_refs[]
- termination_reason
```

`rationale_summary`, `evidence_used`, and `rejected_alternatives` are useful for
audit and proposal memory. They must not enter `DecisionFeatures`.

## Tool Set Needed For Upgrade

From single-shot hypothesis/code to agent session, Scion needs these tool groups:

### Context Tools

- list declared research surfaces;
- read adapter-rendered problem summary and solver mechanics;
- read objective policy and current champion summary;
- read surface interface/current target file;
- read active/rejected hypotheses and branch history;
- read search memory and research log;
- read screening/runtime feedback according to exposure policy.

### Drafting Tools

- draft hypothesis object;
- draft patch object;
- draft policy/config file content;
- finalize proposal.

### Static Self-Check Tools

- schema validation;
- target-file/action permission preview;
- surface interface preview;
- import whitelist and AST syntax preview;
- optional complexity guard preview.

### Persistence Tools

- write transcript;
- write scratch plan;
- persist large observations;
- write proposal memory entries.

No MVP tool should directly modify the campaign workspace.

## Read-Only vs Patch-Producing vs Workspace Writes

| Capability | Allow In Proposal Agent | Notes |
|---|---:|---|
| Read problem/spec/adapter rendering | Yes | Through exposure-controlled tools. |
| Read champion surface code | Yes | Current champion only, via target files. |
| Read screening feedback | Yes | Detailed if current policy allows. |
| Read validation/frozen raw metrics | No | Aggregate/pass-fail only. |
| Produce hypothesis | Yes | Tainted, Contract must validate. |
| Produce patch proposal | Yes | Artifact only, not applied. |
| Run contract preview | Yes | Static, no side effects. |
| Run verification/protocol | No | Existing framework stages only. |
| Write scratch artifacts | Yes | Session artifact directory only. |
| Write candidate workspace | No | Only WorkspaceLifecycle after Contract. |
| Write champion/evidence/lineage | No | Existing services only. |

## Proposal Memory And DecisionFeatures

Add `proposal_session_ref` and `proposal_memory_refs` to evidence artifacts if
useful for audit, but do not expose their content to `DecisionEngine`.

Allowed:

```text
StepRecord.proposal_session_ref = "artifacts/proposal_sessions/..."
CampaignSearchMemory.update_from_step(step)
ContextManager reads tainted proposal memory for future prompts
```

Forbidden:

```text
SafeFeatureExtractor reads proposal memory text
DecisionFeatures includes agent rationale/free-text
DecisionEngine branches on proposal-memory-derived strings
```

If an agent observation should matter for promotion, make it a deterministic
gate/protocol/runtime feature first.

## Failure Handling

Agent session failure should not crash the campaign controller. It should return
a typed result:

```text
proposal_fail
schema_fail
permission_fail
context_exposure_fail
max_turns
max_tokens
repeated_tool_loop
partial_output
```

Campaign behavior:

- if no valid hypothesis: record proposal failure step and let failure lifecycle
  handle retry/block;
- if hypothesis valid but no patch: store partial hypothesis as tainted memory,
  do not evaluate;
- if patch produced but contract preview failed: either allow one repair loop or
  return contract failure normally;
- if session maxes out repeatedly on same surface: lower that surface priority
  through proposal guidance, not Decision.

Use circuit breakers:

- 3 failed compactions;
- 3 identical tool calls;
- 5 malformed final-output attempts;
- session-level wall-time and turn budgets.

## CVRP Multi-Step Agent Workflow

The current CVRP issue is not only weak operator code. The problem package
exposes narrow post-baseline operator surfaces while the main ALNS+VNS baseline
does most of the search. Agentic proposal should make that diagnosis explicit.

Recommended CVRP workflow:

1. Read surfaces:
   `route_local`, `route_pair`, `ruin_recreate`, `search_policy`, and future
   portfolio/construction surfaces.
2. Read recent surface feedback:
   accepted moves, no-op rate, runtime ratio, operator errors, policy load
   errors, stop reasons.
3. Decide whether the next attempt should stay on an operator surface or shift
   to a policy/portfolio/construction surface.
4. For operator surfaces:
   inspect `CvrpOperator.execute(solution, instance, rng)`, current registry,
   bounded neighborhood guidance, and recent no-op causes.
5. For `search_policy`:
   inspect required module-level functions and current policy values.
6. For future portfolio/construction surfaces:
   inspect allowed components/modes, bounds, runtime audit fields, and solver
   invocation point.
7. Draft a hypothesis that names:
   surface, invocation point, expected behavior change, runtime cap, no-op
   condition, and protected objectives.
8. Draft patch proposal.
9. Run contract preview.
10. Finalize.

This turns "write another local operator" into a controlled design workflow:

```text
surface diagnosis -> surface choice -> bounded algorithm lever -> patch proposal
```

## Framework Extension Points

Keep changes generic:

### Proposal Layer

- `AgenticProposalSession` service.
- `ProposalToolRegistry`.
- `ProposalObservation` and transcript persistence.
- `AgenticProposalOutput` Pydantic schema.
- `ProposalPipeline.generate_agentic_proposal()`.

### Context Layer

- `ContextExposurePolicy`.
- `ContextManager.build_proposal_agent_view()`.
- surface-specific adapter rendering for agent tools.
- proposal memory query/render functions.

### Evidence Layer

- `StepRecord.proposal_session_ref`.
- `EvidenceRecorder` writes session refs and failure summaries.
- search memory update can ingest tainted proposal-session summaries only for
  future prompts.

### Contract Layer

- reusable contract-preview entry point that accepts proposed file content
  without writing workspace.
- surface-aware validation remains driven by `ProblemSpecV1.research_surfaces`.

### Problem Package Layer

- adapter renders surface interface and solver invocation point.
- solver emits surface-loaded/executed/behavior-change runtime audit fields.
- problem package owns CVRP portfolio/construction policy files and allowed
  components.

Avoid adding CVRP-specific checks to `DecisionEngine`, `SafeFeatureExtractor`,
`ExperimentProtocol`, `CampaignLoop`, or `BranchStepRunner`.

## Layer Ownership

### Must Stay In Tainted Creative Layer

- surface diagnosis narrative;
- hypothesis rationale;
- rejected alternatives;
- proposal memory;
- patch drafts;
- code comments and design notes;
- self-reported expected effect;
- agent summaries and compaction summaries.

### Contract Owns

- schema validity;
- target file/action permission;
- frozen-file rejection;
- AST syntax;
- import whitelist;
- operator/policy interface;
- static complexity guards.

### Verification Owns

- runtime syntax/import in isolated subprocess;
- adapter-backed consistency/feasibility/objective recomputation;
- nondeterminism;
- runtime/perf guard;
- fail-closed runtime audit interpretation.

### Protocol Owns

- canary/screening/validation/frozen execution;
- pair completeness;
- objective comparison using metric specs;
- runtime pair statistics;
- raw metrics refs.

### Decision Owns

- deterministic vetoes;
- stage transitions;
- promotion/abandon/expand decisions;
- reading only `DecisionFeatures`.

## MVP Acceptance Criteria

- Agent session can produce the same valid hypothesis/patch shapes as the
  current proposal path.
- Agent cannot directly write candidate workspaces.
- Agent tools cannot read validation/frozen raw metrics.
- Proposal transcript and compact memory are persisted as tainted artifacts.
- `DecisionFeatures` schema is unchanged or only extended with deterministic
  gate/protocol/runtime facts, never agent free text.
- Contract preview catches surface/action/interface errors before final output.
- CVRP agent workflow can choose `search_policy` instead of another operator
  when repeated no-op operator evidence is present.
- Existing Contract/Verification/Protocol/Decision tests remain the authority
  for promotion.
