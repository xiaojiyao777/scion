# Agent Loop And State

## Production Agent Loop Pattern

Claude Code's core loop can be abstracted as:

```text
session state
-> build API-visible context
-> call model
-> collect assistant text and tool_use blocks
-> if no tool_use: run stop hooks / terminate
-> validate and execute tools
-> append tool_result observations
-> update turn state
-> continue
```

The important production detail is that the loop is not "LLM decides
everything." Deterministic code owns state transitions, context budgeting,
permission checks, retry limits, and termination. The LLM chooses tool calls and
drafts content inside a bounded arena.

For Scion, this maps to an `AgenticProposalSession` inside `ProposalPipeline`.
It should replace or wrap the current single hypothesis/code calls, but its final
product is still only a tainted proposal object.

## Core State

A Scion proposal session should have explicit state, persisted as JSONL plus a
compact session summary:

```text
AgenticProposalSessionState
- session_id
- campaign_id, round_id, branch_id
- champion_version, champion_weight_revision
- problem_id, problem_spec_version
- active_stage: orient | diagnose | choose_surface | draft_hypothesis |
  inspect_interface | draft_patch | self_check | final
- message_history_ref
- proposal_memory_ref
- visible_context_policy_id
- tool_budget: max_turns, max_tool_calls, max_tokens, max_wall_time
- tool_call_counters and repeated_call_signatures
- compaction_state
- termination_reason
- final_output_ref
```

The state must distinguish durable evidence from tainted proposal context:

- `message_history_ref`: complete agent transcript for audit/debug.
- `proposal_memory_ref`: tainted session notes and observations available to
  future Creative Layer prompts.
- `final_output_ref`: structured `AgenticProposalOutput`.
- No direct write into `DecisionFeatures`.

## Turn Semantics

Each turn should have an append-only record:

```text
ProposalAgentTurn
- turn_index
- prompt_view_hash
- assistant_message_ref
- tool_uses[]
- tool_results[]
- token_usage
- elapsed_ms
- error_tag?
- continuation_reason?
```

This makes failures replayable without making them Decision inputs.

## Observation And Continuation

Tool outputs become observations in the next model call. The key rule is:

```text
tool result -> proposal memory / next Creative Layer turn
tool result -> never directly into DecisionFeatures
```

If a tool fails, the failure should normally be returned as a structured
observation so the agent can repair its plan. Only framework-level failures
should terminate the session:

- permission violation;
- forbidden exposure request;
- max turns or wall-time exhausted;
- repeated identical tool loop;
- compaction failure after bounded retries;
- malformed final output after bounded retries.

## Termination

Minimum termination reasons:

```text
completed
partial_hypothesis_only
partial_patch_unchecked
max_turns
max_tool_calls
max_wall_time
max_tokens
repeated_tool_loop
permission_denied
context_exposure_denied
structured_output_failed
compaction_failed
user_or_campaign_abort
```

Scion should treat `completed` as "ready for ContractGate", not "accepted."
Partial outputs may be stored for future proposal memory, but they should not
enter the branch evaluation path unless converted into a valid hypothesis/patch
and passed through normal gates.

## Continuation And Output Truncation

Claude Code handles long model output with bounded continuation. Scion should do
the same for final proposal generation:

1. If the model stops because of output length, retry once with a larger output
   cap if the provider supports it.
2. If still truncated, inject a continuation message that asks only for the
   missing structured field.
3. Stop after a small fixed count, for example 3 continuation attempts.
4. Preserve all partial content in transcript, but mark final output invalid
   until schema validation passes.

This matters for complete-file patch proposals because code content is the most
likely field to be truncated.

## Compaction And Resume

Claude Code's useful pattern is a two-view history:

- full transcript for UI/audit;
- compact API-visible view for the next model turn.

Scion should add the same distinction:

```text
full proposal transcript
-> compact proposal summary
-> recent detailed turns
-> next model context
```

Compaction prompt requirements should be Scion-specific:

- preserve user/campaign request exactly;
- preserve active research surface and why it was chosen;
- preserve current hypothesis draft and rejected alternatives;
- preserve tool observations as source-attributed facts;
- preserve permission/exposure denials;
- preserve current next step;
- exclude validation/frozen per-case detail by construction.

Compaction must be disabled recursively for the compaction call itself. After a
failed compaction, use a circuit breaker: after 3 failures, stop attempting
automatic compaction and terminate or return partial output.

Resume should be explicit:

```text
resume(session_id)
-> load last compact summary
-> load recent uncompacted turns
-> verify champion_version still current
-> if champion changed, mark session stale and require re-orient
-> continue or return stale_session
```

Stale resume is important because Scion branches can become stale after a
promotion.

## Agent Loop For Scion

Recommended minimum loop:

```text
1. Orient
   Read problem summary, research surfaces, champion summary, branch state.

2. Diagnose
   Read screening/runtime/search-memory feedback allowed for this branch.

3. Choose Surface
   Select one declared research surface and action.

4. Draft Hypothesis
   Produce a structured hypothesis candidate.

5. Inspect Interface
   Read only target surface interface/current file/reference snippets allowed by
   the problem package.

6. Draft Patch Proposal
   Produce complete file content or policy content as a patch proposal.

7. Self Check
   Run schema/contract-preview tools only. No verification/protocol shortcut.

8. Finalize
   Emit `AgenticProposalOutput`.
```

The loop may revisit steps 2-6, but only within fixed budgets and with repeated
call detection.

## Repeated Tool Calls

Agentic sessions are vulnerable to repeated "read same context, restate same
plan" loops. Add deterministic guards:

- hash each tool name + normalized input;
- count identical calls;
- after 2 identical calls, return cached result plus warning;
- after 3 identical calls without new final-output progress, terminate as
  `repeated_tool_loop`;
- keep per-tool budgets, such as max 10 read-context calls, max 3 patch drafts.

The guard should be recorded in proposal memory, not hidden, because it teaches
future proposal sessions that the branch got stuck.

## Implications For Scion

- Agentic proposal is a richer Creative Layer, not a new campaign controller.
- Agent state must be persisted separately from evidence state.
- All agent failures should produce auditable `StepRecord`/lineage refs when a
  campaign round was consumed.
- Partial work is valuable as proposal memory but must not skip Contract,
  Verification, Protocol, or Decision.
- Resume must check champion/stale state before continuing.
