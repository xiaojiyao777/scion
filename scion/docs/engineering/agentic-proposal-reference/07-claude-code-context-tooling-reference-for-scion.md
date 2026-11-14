# Claude Code Context And Tooling Reference For Scion

*Date: 2026-05-23*

## Executive Summary

Claude Code's relevant lesson for Scion is not "make Scion a general coding
assistant." The useful reference is a narrower production pattern:

```text
full audit transcript
-> host-built API-visible context projection
-> model emits typed tool_use blocks
-> host validates, executes, budgets, and records tool observations
-> next turn inherits compact state and selected observations
```

For Scion, this maps directly to the current APS problem: hypothesis and code
are still too easy to treat as separate calls that rediscover the same active
algorithm. Scion should instead make the hypothesis phase produce a reusable,
auditable observation ledger. The code phase should inherit that ledger as
source-hashed evidence and only re-read files when the ledger is stale,
incomplete, or target-specific.

The other major lesson is that Claude Code avoids context blowups by managing
observations as artifacts, summaries, and stable replacement decisions. Scion
already has active solver snapshots, fact packets, prompt manifests, and
observation budgets. The next step is to make them first-class phase transition
state rather than large prompt blobs.

The design should remain Scion-shaped:

- Core owns generic tool protocol, budgets, ledgers, phase transition, taint,
  audit, and boundary checks.
- Problem adapters/providers own active algorithm facts, mechanism identities,
  solver call graph, file/symbol manifest, and novelty/premise semantics.
- Decision remains blind to proposal memory and free text.

## Observed Claude Code Patterns

### Agent Loop And Cross-Step State

Claude Code's query loop is a deterministic state machine around model calls.
The loop keeps mutable cross-iteration state such as messages, tool context,
compaction tracking, output recovery counts, turn count, and pending tool-use
summaries. At the start of every iteration it builds `messagesForQuery`, calls
the model, collects assistant messages and tool-use blocks, executes tools, maps
tool results back into user messages, and continues until no follow-up tool call
is needed or a termination guard fires.

The important point is ownership:

- The model chooses tool calls and writes content.
- The host owns state transition, termination, context projection, tool
  validation, permission, execution, result serialization, and retry limits.

This is the right pattern for APS. The LLM can research and draft inside the
Creative Layer, but the host must own what counts as observed evidence and what
can cross from hypothesis into code.

### API-Visible Context Is A Projection

Claude Code does not send the whole transcript verbatim. Each turn rebuilds an
API-visible projection roughly as:

```text
latest compact-boundary slice
-> aggregate tool-result budget
-> snip if enabled
-> microcompact
-> context collapse if enabled
-> autocompact if needed
-> hard token blocking
-> model call
```

This gives Claude Code two histories:

- a fuller transcript for UI/audit/resume;
- a compact model-visible view for the next turn.

Scion should treat every APS prompt the same way. The prompt manifest should not
only say what sections were rendered. It should also record which observation
ids, source digests, fact-packet digests, and artifact refs were visible to that
phase.

### Tool Results Are Observations, Not Free Text

Claude Code tool execution is a real host protocol, not a prompt-only
convention. Tools have schemas, host-side validation, permission checks, calls,
and result mapping. Bad input becomes an `is_error` tool result with a useful
message; successful output is mapped by the tool into an API `tool_result`
block. Large results can be persisted to disk and replaced with a preview.

The model sees tool descriptions and chooses a tool, but the host decides:

- whether the call is well-typed;
- whether semantic preconditions are satisfied;
- whether the tool may run;
- what output shape enters the transcript;
- how much of the output enters the next prompt.

This is exactly the split Scion needs. APS tools should stay typed and
host-executed, not become "model writes JSON instructions that the next prompt
interprets."

### Reuse And De-Duplication Of Large Observations

Claude Code has several mechanisms that prevent old large observations from
being injected over and over:

- Per-tool `maxResultSizeChars` and large-result persistence.
- Aggregate per-message tool-result budgeting.
- A replacement state that freezes decisions for already-seen tool results, so
  a result that was previously shown in full is not later rewritten in a way
  that breaks prompt-cache consistency.
- Session memory and compaction summaries that retain current work, files,
  errors, and next steps without re-sending the full transcript.
- Read-before-write state for file edits, so the host knows what the model has
  actually read and rejects stale writes.

The closest Scion analogue is an observation ledger with source digests and
phase visibility. Scion should not make the code phase re-read the same
`context.read_active_solver_design`, call graph, and file previews if the
hypothesis phase already read them and the source digest still matches.

### Tool Calling Is Host Protocol Plus Model Guidance

Claude Code's tool use is not merely a "please output this format" prompt. It
uses provider tool blocks and host-owned schema validation. Natural-language
tool prompts still matter for routing, but they are advisory. The enforceable
part is the host protocol:

```text
model tool_use
-> input schema parse
-> tool-specific validation
-> permission and hooks
-> call
-> map result
-> size budget / persistence
-> append tool_result
```

Scion should keep this stricter than Claude Code. The useful transfer is the
protocol shape, not broad capabilities such as arbitrary shell or direct
workspace writes.

### Edit Application Is Host-Owned

Claude Code's edit path is relevant because it treats model edits as proposals.
For existing files, edit/write tools require a prior read and reject stale files.
The host applies changes, derives diffs, and returns compact success/error
observations.

For Scion this argues against making code phase emit unconstrained patch blobs
that also carry its own audit. The model should emit a typed patch proposal; the
host should derive patch graphs, import edges, target ownership, source digests,
and contract-preview observations.

## Scion-Relevant Design Recommendations

### 1. Add A Phase-Inherited Observation Ledger

Introduce an append-only `AgenticObservationLedger` for each APS session:

```text
AgenticObservationLedger
- session_id
- campaign_id, branch_id, champion_version, problem_spec_hash
- context_policy_id
- active_fact_anchor:
    source_observation_id
    snapshot_digest
    fact_packet_digest
    fact_ids[]
- observations[]
```

Each observation should carry enough metadata for phase reuse:

```text
LedgerObservation
- observation_id
- phase: hypothesis | code | preview | repair
- tool_name
- normalized_args
- args_hash
- source_digest
- fact_packet_digest?
- artifact_ref?
- prompt_payload_ref?
- summary
- compact_payload
- full_payload_ref?
- exposure_level
- taint
- reusable_by_phases[]
- prompt_visible_chars
- stale_if:
    champion_version changes
    source_digest changes
    context_policy_id changes
    problem_spec_hash changes
```

The code phase should receive a ledger manifest before raw observations:

```text
Hypothesis Phase Observed Evidence
- active fact packet: <digest>, fact ids [...]
- call graph: observation <id>, source digest <digest>
- algorithm files read:
  - path, role, digest, observation id, full/preview/symbol
- premise/novelty result:
  - supported | contradicted | duplicate | needs target read
```

This prevents code from wasting budget on "what did I already read?" It also
makes every claim auditable: the code phase can cite ledger observation ids
instead of restating unverifiable natural-language memory.

### 2. Make Code Phase Use Read Receipts Before Re-Reading

Add a host-owned read-receipt rule:

```text
same tool + same normalized args + same source_digest + allowed phase reuse
-> return compact already_observed observation
```

Example:

```text
context.read_algorithm_file(
  file_path="policies/baseline_modules/local_search.py",
  max_chars=24000
)
```

If hypothesis already read that file at the same digest, code should get:

```text
already_observed:
  source_observation_id: obs_123
  file_path: ...
  digest: ...
  available_artifact_ref: ...
  prompt_summary: "Full file read in hypothesis phase; use obs_123 unless
  you need a different symbol/slice."
```

The host can still allow a targeted re-read when code asks for a symbol or a
larger slice. The important change is that repeated reads become intentional,
not accidental.

Implementation status as of 2026-05-23:

- APS now persists a source-digested observation ledger and returns compact
  `already_observed` receipts for unchanged reusable reads.
- Code prompts render a bounded `Agentic Resume Context` instead of injecting
  raw resume ledgers.
- Prompt manifests now account for the rendered provider-visible prompt, while
  raw `prompt_context` is preserved only as an audit digest.
- The active fact packet remains the primary model-facing mechanism context;
  duplicate active-fact payloads are omitted from lower-priority raw tool
  observations.

### 3. Replace Fixed File Count Truncation With Manifest-First Budgeting

Active algorithm context should start with an adapter-owned manifest, not with
"first N files" or "largest preview until the budget runs out."

Recommended `ActiveAlgorithmManifest`:

```text
- snapshot_digest
- fact_packet_digest
- files:
    file_path
    module
    role: entrypoint | scheduler | construction | local_search |
          destroy_repair | acceptance | state | config | support | inactive
    active: bool
    size_chars
    digest
    symbols[]
    imports[]
    exported_symbols[]
    mechanism_ids[]
    editable: bool
    targetable: bool
- call_graph_edges[]
- mechanism_fact_index:
    mechanism_id -> fact_ids[] -> source paths/symbols
```

Budget policy should be role and target aware:

```text
Always include:
  active fact packet, manifest, snapshot digest, entrypoint summary,
  compact call graph.

Read in full:
  approved target file, or exact owner file for the claimed mechanism.

Read by symbol/slice:
  call-graph neighbors, imported helpers, registration functions, acceptance
  hooks, runtime telemetry hooks.

Keep as manifest/digest only:
  unrelated support files, inactive files, legacy surfaces, already-read files.
```

A simple scoring policy is enough for the first version:

```text
score(file) =
  + target_file match
  + source path appears in active facts for claimed mechanism
  + call-graph distance <= 1 from target
  + imports or exports used by target
  + branch-owned changed file
  + prior failure mentions file/symbol
  - inactive/legacy role
  - already fully read at same digest
```

This fixes the current failure mode where support-module previews are available
but key owner-file details are still buried in truncated raw observations.

### 4. Add Symbol-Level Algorithm Reads As First-Class Budget Units

`context.read_algorithm_file` is useful, but full-file reads are the wrong unit
for many algorithm objects. The manifest should expose symbols and the code
phase should be encouraged to request:

```text
context.read_algorithm_symbol(file_path, symbol)
context.read_algorithm_slice(file_path, start_symbol, end_symbol?)
context.read_algorithm_neighbors(symbol, radius=1)
```

Scion already has `context.read_algorithm_symbol`; the recommendation is to
make symbol reads part of the planner's default strategy for large files and
integration checks. For example, if the hypothesis targets acceptance reheat,
code should not need full construction and local-search bodies. It needs the
acceptance functions, scheduler integration edge, and telemetry recording hook.

### 5. Promote The Active Fact Packet Above Raw Observations

The active fact packet should be the primary factual context for hypothesis,
tool selection, code, and semantic gates. Raw tool observations should remain
audit/support.

Every LLM call that chooses owner files or decides whether context is sufficient
should receive a compact active-facts anchor:

```text
active_facts_anchor
- source_observation_id
- snapshot_digest
- fact_packet_digest
- fact_ids
- compact mechanism claims
- source paths/symbols
```

The gate and the agent must share the same packet. If a provider rejects a
premise, the rejection should cite fact ids and the same digest the model could
see. If the rejection comes from campaign history rather than adapter facts, it
should say so explicitly and cite previous hypothesis ids instead of presenting
it as provider fact contradiction.

### 6. Let Code Phase Contradict The Hypothesis

The code phase should not be forced to implement a hypothesis that its target
reads disprove. Add a required code-phase field:

```text
premise_check:
  supported | contradicted | duplicate | wrong_owner | needs_more_context

premise_evidence:
  observation_id
  file_path
  symbol?
  digest
  summary
```

If `premise_check` is `contradicted`, `duplicate`, or `wrong_owner`, the code
phase should return a structured non-patch result. That is a successful
research outcome and should become branch-local negative proposal memory, not a
generic code-generation failure.

### 7. Preserve Scion Boundaries While Expanding Research Depth

To let the agent research the whole algorithm object without contaminating core:

- Core defines generic tool contracts, ledger records, manifest schema,
  digest checks, budgets, and phase transition rules.
- Problem adapters/providers populate manifest rows, facts, mechanism ids,
  source symbols, and novelty/premise semantics.
- Semantic gates may only reject from facts visible in the ledger or from
  clearly labeled campaign-history matches.
- Contract/Verification/Protocol/Decision remain unchanged in authority.

This means Scion core can support deep algorithm research without knowing CVRP,
ALNS, VNS, route removal, Shaw removal, regret insertion, or acceptance
semantics. Those remain adapter-provided facts.

### 8. Treat Observation Budget As A Structured Allocation

Use named budget buckets instead of one flat observation character cap:

```text
agentic_context_budget
- active_fact_anchor: reserved, never truncated below digest/fact ids
- manifest_and_call_graph: reserved compact budget
- target_full_content: reserved for selected/approved target
- integration_symbols: bounded symbol reads
- feedback_memory: compact tainted research feedback
- raw_observation_audit: optional, first to omit
- self_check_reserve: held for contract/smoke/repair observations
```

Claude Code's large-result persistence is useful here: full payloads should be
artifact refs, while prompt-visible payloads should be compact and role-specific.

## Do Not Copy Blindly

### Do Not Copy General Workspace Power

Claude Code is an IDE agent. It can run shell commands, edit files, use MCP
servers, and ask users for permissions. Scion should not copy that surface.
Scion's proposal agent should not write campaign workspaces, run Verification,
run Protocol, inspect validation/frozen raw metrics, mutate lineage, or promote.

### Do Not Use LLM Compaction As The Primary Scientific Memory

Claude Code uses LLM summaries because its source material is open-ended
conversation. Scion has structured artifacts. Scion compaction should be
template and schema driven wherever possible:

- active fact packet;
- observation ledger;
- prompt manifest;
- hypothesis/premise status;
- patch graph;
- contract/smoke preview observations;
- branch-local negative memory.

LLM summaries can help produce readable notes, but they should not be the only
source of scientific continuity.

### Do Not Let Prompt Cache Concerns Drive Scientific State

Claude Code optimizes heavily around prompt cache stability. Scion should take
the useful idea of stable projections, but correctness and auditability matter
more than cache hit rate. A stale source digest must force re-orientation even
if reusing old context would be cheaper.

### Do Not Make The Gate Better Informed Than The Agent

A provider-level novelty or premise gate must not use hidden active algorithm
facts that were unavailable to the agent. If a fact can block a hypothesis, it
must be present in the fact packet or cited as a campaign-history repeat with
its own provenance.

### Do Not Treat All Rejections As Infrastructure Failures

Claude Code tool errors are observations the model can react to. Scion should
similarly keep agent-quality blocks separate from infra failures:

- premise contradicted;
- duplicate mechanism;
- wrong owner file;
- activation diagnostic invalid;
- structured-output schema repair failed.

These should feed branch-local proposal memory and guidance. They should not
automatically become global infra streaks.

### Do Not Hide Full Algorithm Understanding Behind Component Knobs

Component surfaces are useful, but they are not a substitute for studying the
active algorithm object. Scion should expose the complete algorithm through
adapter-owned manifests, facts, symbols, call graph, and target-aware reads,
while keeping the editable boundary and verification protocol controlled.

## Implementation Backlog

### P0: Ledger-Based Phase Transition

Add `AgenticObservationLedger` and render a compact ledger manifest into code
phase before raw observations. Include observation ids, tool names, args hashes,
source digests, fact-packet digest, artifact refs, exposure levels, prompt
visibility, and phase reuse flags.

Acceptance criteria:

- Code phase can cite hypothesis-phase observation ids.
- Code phase does not re-read active solver design or call graph when the same
  digest is already in the ledger.
- Prompt manifests record ledger observation ids and digests visible to each
  phase.

### P0: Read Receipts And Already-Observed Tool Results

Implement reusable observation lookup by:

```text
tool_name + normalized_args + source_digest + context_policy_id
```

Repeated reads should return compact `already_observed` results with the source
observation id and artifact ref.

Acceptance criteria:

- Repeated `context.read_algorithm_file` at the same digest is compact.
- A changed branch workspace digest forces a fresh read.
- The audit transcript still preserves the full first observation.

### P0: Manifest-First Active Algorithm Budget

Upgrade active algorithm file selection from fixed count/truncation to
manifest/digest/symbol/target-aware budgeting. Keep active fact packet and
manifest visible even under tight budgets.

Acceptance criteria:

- Prompt contains manifest file roles, digests, symbols, and active/inactive
  status.
- Approved target file receives full-content budget.
- Call-graph neighbor symbols are preferred over unrelated full-file previews.
- Inactive/legacy files cannot crowd out active owner files.

### P0: Code-Phase Premise Check

Add required `premise_check` and `premise_evidence` to code-phase output or
final patch-submission tool. Allow code phase to return no patch when the
hypothesis is contradicted, duplicate, or wrong-owner.

Acceptance criteria:

- No patch is emitted for contradicted premises.
- Rejection is stored as branch-local tainted proposal feedback.
- Failure classification distinguishes premise contradiction from code failure.

### P1: Tool-Selection Fact Anchor

Inject a compact active-facts anchor into any tool-selection LLM call that can
choose owner files, decide sufficiency, or stop reading.

Acceptance criteria:

- Tool-selection prompt manifest records `fact_packet_digest`.
- Planner decisions about target files can be audited against the same fact
  packet used by hypothesis/code/gates.

### P1: Symbol And Integration Neighbor Reads

Make symbol-level and call-graph-neighbor reads part of the default strategy for
large algorithm files.

Acceptance criteria:

- Planner can request target symbol, exported registration symbol, caller, and
  callee without reading every file in full.
- Budget reports distinguish full-file reads from symbol reads.

### P1: Rejection Provenance Split

Separate provider-fact rejections from campaign-history repeated-mechanism
rejections.

Acceptance criteria:

- Provider rejection includes fact ids, snapshot digest, fact-packet digest.
- History repeat includes previous hypothesis id, branch/step id, matched
  normalized ids, and no misleading provider-fact digest.

### P2: Structured Session Memory From Ledger

Build APS compaction from ledger fields rather than free-form transcript
summaries:

```text
Active facts anchor
Observed evidence
Rejected premises
Current hypothesis
Patch premise check
Open next step
```

Acceptance criteria:

- Compaction preserves digests and source observation ids.
- Validation/frozen forbidden details cannot be merged into lower-exposure
  summaries.
- Resume fails closed when champion, source digest, problem spec, or exposure
  policy changes.

### P2: Context Budget Diagnostics

Add per-session budget reports:

```text
active_fact_anchor chars
manifest/call_graph chars
target_content chars
symbol_reads chars
feedback/memory chars
raw_audit_observation chars
self_check_reserve chars
duplicates avoided
```

Acceptance criteria:

- Postrun analysis can tell whether failures came from missing facts, target
  file truncation, duplicate reads, or real algorithm quality.
- Budget policy can be tuned without reading raw transcripts.
