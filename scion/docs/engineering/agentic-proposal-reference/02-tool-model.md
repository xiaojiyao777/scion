# Tool Model

## Claude Code Tool Pattern

The production tool pattern is:

```text
tool schema
-> input validation
-> permission check
-> optional risk classification
-> call
-> map result to tool_result
-> append observation
```

Two details matter for Scion:

- Validation and permission happen before side effects.
- Result serialization is owned by framework code, not by the model's free-text
  formatting.

Scion should use this pattern for proposal tools even if the tools are simple
Python functions behind `CreativeLayer`.

## Tool Definition Shape

Suggested Scion internal tool interface:

```python
class ProposalTool(Protocol):
    name: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    permission: ToolPermission
    read_only: bool
    concurrency_safe: bool
    max_result_chars: int

    def validate_input(self, raw: dict) -> ValidationResult: ...
    def check_permission(self, args, context) -> PermissionResult: ...
    def call(self, args, context) -> ToolResult: ...
    def map_result(self, result) -> ProposalObservation: ...
```

The `map_result()` step is a hard boundary: the LLM should not decide how tool
results enter context. This directly addresses the old failure mode where large
code content is embedded in fragile free-text JSON.

## Permission Classes

Use explicit permission classes rather than a generic "can run tool" flag:

| Class | Meaning | Examples |
|---|---|---|
| `read_public_context` | Read problem/campaign context already allowed for proposals. | problem summary, surface list |
| `read_tainted_memory` | Read prior proposal/search memory. | failed hypotheses, screening feedback |
| `read_champion_artifact` | Read current champion code or policy files. | `operators/*.py`, `policies/*.py` |
| `contract_preview` | Run deterministic static checks without materializing candidate. | schema/target/action/interface preview |
| `draft_patch` | Produce a patch proposal artifact. | complete file content |
| `write_scratch` | Write only session scratch/transcript artifacts. | plans, summaries |
| `forbidden` | Never exposed in proposal session. | validation/frozen raw metrics, campaign workspace write, promotion |

The default proposal agent should run with:

```text
read_public_context
read_tainted_memory
read_champion_artifact
contract_preview
draft_patch
write_scratch
```

It should not have direct workspace write, solver execution, verification,
protocol, champion, lineage mutation, or final evidence write permissions.

## Read-Only Tools

Minimum read-only tools:

```text
list_research_surfaces()
read_problem_summary()
read_problem_object()
read_solver_mechanics()
read_objective_policy()
read_champion_summary()
read_surface_interface(surface)
read_surface_file(surface, path)
query_branch_history(branch_id)
query_search_memory(filters)
query_screening_feedback(branch_id, surface?)
query_runtime_feedback(branch_id, surface?)
query_active_and_rejected_hypotheses()
```

Exposure rules:

- Screening details may be available when already allowed by current
  `ContextManager` policy.
- Validation should be aggregate-only.
- Frozen should be pass/fail or budget state only.
- Raw metrics refs may be mentioned as internal refs but not read or expanded by
  the agent unless the stage is screening and the exposure policy allows it.

## Patch-Producing Tools

Patch-producing tools should not write candidate workspaces. They return typed
artifacts:

```text
draft_hypothesis(...)
draft_surface_patch(...)
draft_policy_patch(...)
draft_registry_change(...)
finalize_agentic_proposal(...)
```

`draft_surface_patch` output should be complete file content plus metadata, not a
diff. The patch is tainted until `ContractGate` accepts it.

Recommended distinction:

- `draft_*` tools may be called multiple times and stored in proposal memory.
- `finalize_agentic_proposal` can be called only once successfully.
- Only the finalized artifact is handed to the existing `ProposalPipeline`
  output boundary.

## Should Agent Write Workspace Directly?

No, not the campaign workspace.

Allowed writes:

- session transcript JSONL;
- compact summaries;
- scratch notes;
- draft patch artifacts under an agent-session artifact directory.

Forbidden writes:

- active candidate workspace;
- champion snapshot;
- registry in campaign workspace;
- protocol/final evidence artifacts;
- lineage database;
- problem package source files outside the materialization flow.

Reason: direct workspace writes blur Creative Layer and gate boundaries. Scion
already has a safe path:

```text
PatchProposal
-> ContractGate
-> WorkspaceLifecycle materialization
-> VerificationGate
-> Protocol
-> SafeFeatureExtractor
-> DecisionEngine
```

The agent should feed that path, not bypass it.

## Tool Results Into Context

Every tool result should map to a small, typed observation:

```text
ProposalObservation
- tool_name
- tool_call_id
- observation_type
- summary
- structured_payload
- artifact_ref?
- taint: proposal
- exposure_level: screening_detail | validation_aggregate | frozen_aggregate |
  public_spec | champion_code | scratch
```

Large outputs should be persisted and summarized:

```text
full output -> artifact file
context -> preview + artifact_ref + checksum
```

This is the Scion version of Claude Code's "persist large tool result and show
preview" pattern. It prevents proposal memory from growing without permanently
discarding information.

## Errors, Refusals, Retry

Tool failures should be classified:

```text
schema_error
permission_denied
exposure_denied
not_found
stale_champion
contract_preview_failed
runtime_exception
result_too_large_persisted
timeout
```

For model-correctable failures, return an observation with `is_error=true` and a
short repair hint. For hard boundary failures, terminate the session or force a
different workflow step.

Retry rules:

- schema errors: up to 2 repair attempts for that tool call type;
- structured final output missing: up to 5 attempts, mirroring Claude Code's
  structured-output enforcement pattern;
- permission/exposure denial: no retry unless the agent changes requested
  surface or scope;
- stale champion: stop and request re-orient.

## Concurrency

Scion's first implementation should keep tool execution sequential for
simplicity, except for independent read-only tools.

Safe parallel group:

```text
read_problem_summary
read_problem_object
list_research_surfaces
read_champion_summary
query_search_memory
query_screening_feedback
```

Must be sequential:

```text
draft_hypothesis
draft_patch
contract_preview
finalize_agentic_proposal
```

The final proposal artifact should be derived from a single coherent session
state, not from racing patch drafts.

## Mapping To Scion Creative Layer Tools

Suggested MVP tool set:

| Tool | Permission | Notes |
|---|---|---|
| `context.read_problem` | read_public_context | Adapter-rendered summary plus optional problem object for instance/solution/objective/lifecycle/move/evidence semantics. |
| `context.list_surfaces` | read_public_context | Compact selection metadata from `ProblemSpecV1.research_surfaces`. |
| `context.read_surface` | read_champion_artifact | Compact-by-default surface contract with `summary` / `interface` / `bounds` / `evidence` / `novelty` / `target_preview` sections plus a bounded current target-file preview; APS normalizes session reads to compact `max_code_chars=1200`, and optional reads fail closed near the observation budget. |
| `memory.query` | read_tainted_memory | Search memory, research log, failed hypotheses. |
| `feedback.query_screening` | read_tainted_memory | Screening-only detailed feedback. |
| `feedback.query_holdout_summary` | read_tainted_memory | Validation aggregate, frozen pass/fail/budget only. |
| `proposal.draft_hypothesis` | draft_patch | Pydantic validated. |
| `proposal.draft_patch` | draft_patch | Complete file content artifact. |
| `proposal.contract_preview` | contract_preview | Static only, no workspace materialization. |
| `proposal.finalize` | draft_patch | Emits final session output. |

Everything else remains outside the proposal agent.

Tool-loop observation budgets are enforced at the APS boundary, not only inside
individual tools. A tool may still return a large payload or a large error, but
`AgenticProposalSession` must replace any over-budget observation with a bounded
`result_too_large` summary before counting or persisting it. New persisted
session artifacts should therefore satisfy
`tool_budget_used.observation_chars <= max_observation_chars`; replay validation
continues to reject older or malformed artifacts that exceed the configured
budget.

`context.read_surface` compact mode is the default for whole-algorithm surfaces.
It omits full prompt guidance blocks and full target-file content, returns a
deterministic `surface-contract.v1` section map, and caps long text/list/map
fields before the APS boundary sees the observation. `detail="full"` remains an
explicit debug opt-in. The default APS observation budget is 64,000 chars: large
enough for list/problem/feedback plus one compact whole-algorithm surface read,
while individual tool observations remain bounded and raw metrics refs remain
stripped. Terminal Contract preview keeps a compact deterministic pass/fail
summary when the full preview payload would exceed the remaining session
observation budget.
