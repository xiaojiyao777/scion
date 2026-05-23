# Claude Code Code Edit Protocol Reference For Scion v3

*Date: 2026-05-23*

## Scope

This note answers a narrow question for the Scion code-stage protocol: Claude
Code's code modification design is closer to which model?

- patch/edit tool mode;
- complete-file write mode;
- a hybrid of the two.

It is based on the existing analysis documents under
`/home/clawd/research/claude-code-src/analysis/` plus targeted source inspection
of Claude Code's tool exposure, file editing, writing, diff rendering, tool
execution, and permission/error feedback paths.

## Bottom Line

Claude Code is a **hybrid**, but its default design is closer to a
**host-applied edit tool protocol** than to a model-emitted patch protocol.

The model does not normally emit a unified diff and ask the host to run
`git apply`. Instead, it calls typed tools:

- `Edit`: exact string replacement in an existing file;
- `Write`: complete file creation or complete rewrite;
- `NotebookEdit`: notebook-specific structured mutation;
- `Bash`: available, but prompt and permission logic steer file mutation away
  from `sed`, `awk`, heredocs, and redirection toward `Edit` and `Write`.

The important boundary is this:

```text
model chooses a typed edit/write operation
-> host validates schema and semantic preconditions
-> host asks/checks permission
-> host applies the change
-> host derives structured diff/audit UI from before/after contents
-> model receives a small tool_result observation
```

So Claude Code's "patch" is mostly a **derived audit/display artifact**, not
the primary model output. Complete-file write is present, but positioned as the
tool for creation or complete rewrites, not the preferred way to modify an
existing file.

## 1. How Tools Are Exposed To The Model

Claude Code tools are `ToolDef` objects built through `buildTool()` in
`src/Tool.ts`. A tool definition contains:

- `name`, `prompt()`, and `description()` for model-facing exposure;
- `inputSchema` and optional `outputSchema`;
- `validateInput()` for side-effect-free semantic validation;
- `checkPermissions()` for permission and policy checks;
- `call()` for execution;
- `mapToolResultToToolResultBlockParam()` for host-owned serialization back
  into the transcript;
- flags such as `strict`, `isReadOnly`, `isConcurrencySafe`, and
  `maxResultSizeChars`.

The model sees JSON-schema tools generated from Zod schemas. In `src/utils/api.ts`,
Claude Code serializes each tool as `name`, full prompt text, and `input_schema`.
When the tool is marked `strict` and the model/provider supports it, the API
tool schema is also marked strict. Tool schemas are cached for prompt-cache
stability.

Tool availability is assembled in `src/tools.ts`:

- `getAllBaseTools()` lists built-ins such as `Bash`, `Read`, `Edit`, `Write`,
  `NotebookEdit`, `Grep`, `Glob`, `Agent`, and web tools.
- `getTools()` filters by mode, environment, permission context, and feature
  flags.
- `assembleToolPool()` merges built-in and MCP tools while preserving stable
  ordering and filtering denied tools before the model sees them.

The tool descriptions are not cosmetic. `FileEditTool/prompt.ts`,
`FileWriteTool/prompt.ts`, and `BashTool/prompt.ts` form a routing policy:

- read files with `Read`;
- edit existing files with `Edit`;
- create or fully rewrite files with `Write`;
- do not use shell commands such as `sed`, `awk`, `cat <<EOF`, or `echo >` for
  normal file mutation.

This is backed by runtime checks, not left as prompt-only guidance.

## 2. Edit, Write, Patch, Diff Granularity

### Edit

`src/tools/FileEditTool/FileEditTool.ts` exposes the model-facing `Edit` tool.
Its input schema is intentionally small:

```text
file_path: absolute path
old_string: exact text to replace
new_string: replacement text
replace_all: optional boolean
```

Key properties:

- It is an exact replacement tool, not a diff parser.
- It requires the file to have been read first through `Read`.
- It rejects stale files when the file has changed since the last read.
- It rejects non-unique `old_string` unless `replace_all=true`.
- It can create a new file only through the special empty-file path
  (`old_string == ""`), but the prompt strongly prefers `Write` for creation.
- It rejects notebooks and redirects to `NotebookEdit`.
- It computes `structuredPatch` from before/after content after applying the
  exact replacement.

Internally, `FileEditTool/utils.ts` has `getPatchForEdit()` and
`getPatchForEdits()`. These functions apply edits and derive patch hunks for
display. That internal multi-edit capability is used by the UI/IDE flow, but in
this source tree there is no primary model-facing `MultiEdit` tool definition.
The only `MultiEdit` occurrence found is a bridge status label in
`src/bridge/sessionRunner.ts`. The model-facing edit tool is single-replacement
plus `replace_all`.

### Write

`src/tools/FileWriteTool/FileWriteTool.ts` exposes `Write`:

```text
file_path: absolute path
content: complete file content
```

Key properties:

- It writes complete content.
- It is intended for new files or complete rewrites.
- If the target already exists, the file must have been read first.
- It rejects stale files if the file changed after the read.
- It records `type=create|update`, original content, full content, and a
  derived structured patch for updates.
- The model-facing tool result is still a small success message, not the full
  code or patch.

### Patch And Diff

Claude Code uses diffs heavily, but mostly as host-derived artifacts:

- `src/utils/diff.ts` derives structured hunks from old/new content.
- `src/components/FileEditToolDiff.tsx`,
  `src/components/StructuredDiff.tsx`, and
  `src/components/diff/DiffDialog.tsx` render reviewable diffs.
- `/diff` opens a UI over transcript-derived changes.
- File edit/write outputs carry `structuredPatch`, `originalFile`, and sometimes
  `gitDiff`, but `mapToolResultToToolResultBlockParam()` returns a compact
  textual observation such as "file updated successfully."

There is no evidence in the inspected source that normal code edits are
implemented as "model emits unified diff, host applies patch." The host is the
patch generator, not a blind patch applier.

### Bash And Sed

`Bash` remains a powerful escape hatch, but the design deliberately reduces its
role in code editing:

- `BashTool/prompt.ts` instructs the model to use `Edit` and `Write` instead of
  shell editing commands.
- `BashTool/sedEditParser.ts`, `sedValidation.ts`, and the
  `SedEditPermissionRequest` path detect simple `sed -i` edits and render them
  as file-edit-style diffs.
- The `_simulatedSedEdit` field is internal-only, omitted from the model-facing
  schema, and injected by the permission flow after preview/approval so the
  host applies what was reviewed rather than blindly running an arbitrary sed
  command.

For Scion, this is a useful caution: shell-based edits should not be a code
phase primitive. If a shell compatibility path exists, it should be parsed into
the same host-owned patch preview and boundary checks.

## 3. Boundary Between Model Output And Host Application

Claude Code's boundary is sharp:

1. The model emits `tool_use` blocks, not free-text patch blobs.
2. Anthropic tool input streaming carries JSON through `input_json_delta`.
3. `normalizeContentFromAPI()` parses streamed tool input into an object.
4. `tool.inputSchema.safeParse()` validates shape before any side effect.
5. `tool.validateInput()` validates semantic preconditions.
6. permission and hooks run before execution.
7. `tool.call()` applies the change.
8. `mapToolResultToToolResultBlockParam()` serializes a host-owned result.

For code editing, the most important semantic precondition is "read before
write." `Read` records file content, mtime, offset, and limit in
`readFileState`; `Edit` and `Write` reject partial or missing reads and reject
stale file states. This prevents the model from editing a file it has not
actually seen and prevents overwriting user or formatter changes between read
and write.

Permission UI introduces one more boundary: the user may review or modify the
proposed diff in the IDE before accepting. The permission path can pass the
modified input into `call()`. The model's original request is therefore a
proposal; the host/user-approved input is what gets executed.

The tool result sent back to the model is deliberately compact. The model does
not receive responsibility for formatting the audit patch, and it does not
decide which execution data becomes transcript context. That decision is owned
by `mapToolResultToToolResultBlockParam()` plus tool-result storage/budgeting.

## 4. Error Feedback And Retry

Claude Code's edit protocol uses model-visible errors, but not a hidden automatic
"fix my edit" loop for normal file tools.

The main failure paths are:

- unknown tool: returns `tool_result` with `is_error=true`;
- schema parse failure: returns `InputValidationError` with formatted Zod paths;
- semantic validation failure: returns a tool error string and an error code;
- permission denial: returns a tool error or rejection observation;
- execution exception: catches, formats, and returns `tool_result(is_error=true)`;
- oversized tool result: persists full result to disk and gives a preview/path
  rather than truncating irreversibly.

The next model turn sees the error as an observation and can retry with corrected
arguments. For example:

- "File has not been read yet" should cause a `Read` call before retrying.
- "String to replace not found" should cause reread or a more exact
  `old_string`.
- "Found N matches" should cause more context or `replace_all=true`.
- "File has been modified since read" should cause reread before retry.

For structured final output outside normal file tools, Claude Code has a
separate `StructuredOutput` synthetic tool and Stop Hook enforcement with a
bounded retry count. That is highly relevant to Scion's final proposal output,
but it is separate from the mechanics of `Edit`/`Write`.

Concurrency is also boundary control. `toolOrchestration.ts` runs
concurrency-safe tools in batches but serializes non-read-only tools. File
editing tools are not concurrency-safe by default. This avoids overlapping
mutations and keeps `readFileState` meaningful.

## 5. What Scion Should Borrow

Scion should borrow the **protocol shape**, not Claude Code's broad execution
surface.

Useful patterns:

- expose code-phase actions as schema-backed tools, not free-text JSON blobs;
- keep tool exposure phase-specific and filtered before the model sees tools;
- require read-before-patch with source digest/mtime/content hash equivalents;
- make validation side-effect-free and run it before materialization;
- treat model output as a proposal, not an applied workspace change;
- have the host derive audit diff/patch artifacts from before/after content;
- return short, typed, repairable errors to the model;
- persist large observations and show compact previews;
- keep write operations sequential;
- record the full transcript separately from the API-visible compact view.

Patterns Scion should not copy directly:

- arbitrary shell access;
- direct writes into campaign or candidate workspaces from the agent;
- interactive user permission prompts as the normal campaign-control mechanism;
- allowing `Write`-style complete rewrites without a surface/path/digest gate;
- feeding free-text rationale, transcript, or tool observations into
  `DecisionFeatures`.

## 6. Recommended Scion Code-Stage Protocol

Scion's code stage should also be a **hybrid**, but with a different canonical
artifact than Claude Code:

- model-facing draft tools may use exact replacement or complete-file content;
- the canonical output to the existing Scion pipeline should be a typed
  `PatchSet` or existing `PatchProposal` object;
- host code should derive the audit diff, patch graph, touched symbols, and
  before/after hashes;
- workspace materialization remains owned by `WorkspaceLifecycle` after
  `ContractGate`.

Recommended code-stage tool set:

```text
context.read_target_file(surface_id, target_file, section?, max_chars?)
context.read_symbol(surface_id, target_file, symbol?)
patch.preview_replace(file_path, old_string, new_string, replace_all=false)
patch.preview_full_file(file_path, content)
patch.preview_patch_graph(changes[])
patch.contract_preview(changes[])
patch.submit_patch_set(premise_check, changes[], integration_edges[], evidence_refs[])
```

All tools should be problem-agnostic in core. They should talk in terms of:

- `surface_id`;
- declared target files;
- owned paths;
- before/after file hashes;
- symbol names;
- import/integration edges;
- generic contract rule IDs.

Problem-specific constraints, such as CVRP solver design ownership or allowed
runtime telemetry fields, should enter through problem providers and surface
declarations, not through generic code-stage logic.

### Canonical Change Shape

A Scion code-stage change should include:

```text
PatchSetChange
- file_path
- action: modify | create | delete
- source_digest: digest of file content the agent read, null for create
- edit_intent: exact_replace | full_file
- content_after: complete file content for materialization
- derived_diff_ref: host-generated
- evidence_refs: observations supporting this change
```

Even when the model proposes an exact replacement, the host should normalize it
into complete `content_after` before handing it to Contract/Workspace lifecycle.
This preserves Scion's current complete-file `PatchProposal` compatibility while
still letting the code phase use smaller, less error-prone edit operations.

The model should not submit a unified diff as the canonical artifact. Unified
diff can be accepted only as a display/export format derived by the host.

### Premise Revalidation

The final code-stage submit tool should require:

```text
premise_check:
  supported | contradicted | duplicate | wrong_owner
```

If the full target file contradicts the hypothesis, or shows the mechanism is
already implemented, the code stage should submit a typed non-patch result with
evidence refs. That should be a successful code-stage outcome, not a malformed
patch failure.

### Boundary Controls

The host must reject:

- paths outside declared surface ownership;
- missing or stale `source_digest`;
- patch sets that create imports without declared integration edges;
- changes that require problem-specific authority not provided by the active
  adapter/provider;
- attempts to read validation/frozen raw metrics;
- attempts to run Verification, Protocol, Decision, or promotion as tools.

This keeps the Scion v3 invariant intact:

```text
Creative Layer emits tainted proposal artifacts
-> ContractGate validates structure and boundary
-> WorkspaceLifecycle materializes candidate
-> Verification/Protocol produce evidence
-> SafeFeatureExtractor creates DecisionFeatures
-> DecisionEngine reads only DecisionFeatures
```

## 7. Error Feedback Shape For Scion

Claude Code's model-visible tool errors should become typed Scion observations:

```text
ProposalToolErrorObservation
- tool_call_id
- tool_name
- kind:
    schema_error
    permission_denied
    exposure_denied
    stale_source
    target_not_read
    old_string_not_found
    old_string_not_unique
    contract_preview_failed
    patch_graph_invalid
    runtime_exception
- file_path?
- json_pointer?
- rule_id?
- message
- repair_hint
- taint: proposal
- artifact_ref?
```

Retry policy should be bounded:

- schema or missing tool-output shape: up to 5 attempts for final submit;
- stale source: one reread and retry;
- old string not found/not unique: up to 2 repair attempts;
- contract preview failure: one targeted repair loop if the failure is within
  the selected surface;
- exposure or permission denial: no retry unless the agent narrows scope;
- repeated identical tool calls: terminate as `repeated_tool_loop`.

This should be session-level state, not ad hoc string concatenation in prompts.

## 8. Scion Design Implications

### Problem-Agnostic Core

Claude Code's file-edit core is generic because it owns file/path/diff mechanics
but not domain meaning. Scion needs the same split:

- generic core owns tool protocol, source digests, patch graph shape, contract
  preview routing, observation budgets, transcript, and artifact refs;
- problem providers own allowed surfaces, target paths, imports, smoke hooks,
  novelty providers, and domain-specific prompt/rendering details.

Core code should never know CVRP concepts such as route, customer, vehicle, or
ALNS/VNS unless they arrive as problem-owned metadata.

### Auditable Patch

Every submitted patch set should have:

- before hash and after hash per file;
- host-generated structured diff;
- source observations used by the model;
- contract-preview result;
- patch graph with file/symbol/import/integration edges;
- status for non-patch outcomes such as duplicate or contradicted premise.

This makes patch audit deterministic without trusting the model's prose.

### Boundary Control

Claude Code uses permissions, read-before-write, and stale-file checks because
the agent writes a user's repository. Scion should use analogous controls for a
different reason: to preserve research protocol boundaries.

The code-stage agent may draft. It must not:

- mutate a candidate workspace directly;
- run benchmark protocols;
- inspect forbidden holdout detail;
- promote, abandon, or schedule branches;
- smuggle free-text reasoning into decision inputs.

The result of code-stage success is "ready for ContractGate," not "accepted."

## Sources Read

Claude Code analysis documents:

- `/home/clawd/research/claude-code-src/analysis/01-overall-architecture.md`
- `/home/clawd/research/claude-code-src/analysis/07-error-handling.md`
- `/home/clawd/research/claude-code-src/analysis/08-output-parsing-design.md`
- `/home/clawd/research/claude-code-src/analysis/10-prompt-engineering.md`
- `/home/clawd/research/claude-code-src/analysis/11-tool-system.md`

Claude Code source files:

- `/home/clawd/research/claude-code-src/src/Tool.ts`
- `/home/clawd/research/claude-code-src/src/tools.ts`
- `/home/clawd/research/claude-code-src/src/utils/api.ts`
- `/home/clawd/research/claude-code-src/src/services/api/claude.ts`
- `/home/clawd/research/claude-code-src/src/utils/messages.ts`
- `/home/clawd/research/claude-code-src/src/services/tools/toolExecution.ts`
- `/home/clawd/research/claude-code-src/src/services/tools/toolOrchestration.ts`
- `/home/clawd/research/claude-code-src/src/services/tools/StreamingToolExecutor.ts`
- `/home/clawd/research/claude-code-src/src/tools/FileReadTool/FileReadTool.ts`
- `/home/clawd/research/claude-code-src/src/tools/FileEditTool/FileEditTool.ts`
- `/home/clawd/research/claude-code-src/src/tools/FileEditTool/prompt.ts`
- `/home/clawd/research/claude-code-src/src/tools/FileEditTool/types.ts`
- `/home/clawd/research/claude-code-src/src/tools/FileEditTool/utils.ts`
- `/home/clawd/research/claude-code-src/src/tools/FileWriteTool/FileWriteTool.ts`
- `/home/clawd/research/claude-code-src/src/tools/FileWriteTool/prompt.ts`
- `/home/clawd/research/claude-code-src/src/utils/diff.ts`
- `/home/clawd/research/claude-code-src/src/components/FileEditToolDiff.tsx`
- `/home/clawd/research/claude-code-src/src/components/StructuredDiff.tsx`
- `/home/clawd/research/claude-code-src/src/components/diff/DiffDialog.tsx`
- `/home/clawd/research/claude-code-src/src/components/permissions/FileEditPermissionRequest/FileEditPermissionRequest.tsx`
- `/home/clawd/research/claude-code-src/src/components/permissions/FileWritePermissionRequest/FileWritePermissionRequest.tsx`
- `/home/clawd/research/claude-code-src/src/hooks/useDiffInIDE.ts`
- `/home/clawd/research/claude-code-src/src/tools/BashTool/prompt.ts`
- `/home/clawd/research/claude-code-src/src/tools/BashTool/sedEditParser.ts`
- `/home/clawd/research/claude-code-src/src/tools/BashTool/sedValidation.ts`
- `/home/clawd/research/claude-code-src/src/components/permissions/SedEditPermissionRequest/SedEditPermissionRequest.tsx`

Scion reference documents:

- `scion/design/scion-architecture-v3.md`
- `scion/docs/engineering/agentic-proposal-reference/02-tool-model.md`
- `scion/docs/engineering/agentic-proposal-reference/04-scion-agentic-proposal-design-implications.md`
- `scion/docs/engineering/agentic-proposal-reference/05-claude-code-source-reference-for-scion-v3.md`
- `scion/docs/engineering/framework-code-map/02-proposal-context.md`
- `scion/docs/reviews/scion-v3-full-audit-20260521-round2/01-v3-boundary-and-core.md`
