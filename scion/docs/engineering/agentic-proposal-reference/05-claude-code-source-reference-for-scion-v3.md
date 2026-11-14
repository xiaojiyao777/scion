# Claude Code Source Reference For Scion v3 Repairs

*Date: 2026-05-17*

## Scope

This note consolidates the Claude Code reference work requested after the
`v04-v3-control-closure-sonnet-6r-20260517T072124Z` experiment. The source
inspection was delegated to subagents; this document summarizes their findings
and maps them back to Scion v3. It also uses the existing Claude Code analysis
documents and the Scion postrun analysis:

- `/home/clawd/research/claude-code-src/analysis/*.md`
- `scion/docs/experiments/v0.4/v0.4-v3-control-closure-sonnet-6r-postrun-20260517.md`
- `scion/design/scion-architecture-v3.md`

The goal is not to make Scion a general-purpose coding agent. The goal is to
make the Creative Layer capable enough to research the active algorithm while
keeping Scion's Contract, Verification, Protocol, Decision, lineage, and audit
boundaries intact.

## Experiment-Driven Problem Statement

The six-round Sonnet run showed that Scion has moved past the old "postprocess a
baseline answer" failure mode: successful candidates now modify branch-owned
baseline modules directly. The remaining failure is more subtle and more
important.

Rounds 1-3 were not meaningful solver-quality failures. They were grounding
failures:

- construction was proposed because the agent believed the active baseline had
  only a nearest-neighbor seed;
- scheduler restart was proposed from an inaccurate description of existing
  adaptive weights;
- cross-route Or-opt was proposed even though the active local search already
  had the relevant route-crossing relocation mechanism.

Round 4 was the opposite: the recombination direction was closer to real
algorithm research, but the framework rejected a same-patch new module import.
Rounds 5-6 were normal algorithm attempts, but too local or not beneficial.

So the next repair is not "expose more component knobs." Scion needs a stronger
controlled path for understanding, modifying, and validating the active solver
implementation.

## Reference Patterns From Claude Code

### 1. Two Histories, One API-Visible Projection

Claude Code does not treat the full conversation log as the prompt. It keeps a
full audit/UI history and builds an API-visible transcript before each model
call. That projection is assembled through a fixed pipeline: compact boundary,
tool-result budget, snip/microcompact, collapse/autocompact, and hard blocking
limits.

Scion should use the same separation:

- full proposal transcript remains available for audit;
- each LLM call gets an explicit `api_visible_prompt_manifest`;
- the manifest records section names, artifact refs, source hashes,
  branch/champion provenance, prompt-visible character/token budgets, and
  omitted/compacted sections.

This directly addresses the current "the trace exists but it is hard to know
what the model actually saw" problem.

### 2. Recovery Attachments, Not Random Previews

Claude Code compact does not leave the next turn with arbitrary leftovers. It
rebuilds state through structured summaries and recovery attachments. For Scion,
the equivalent recovery attachment is the active solver snapshot:

```text
ActiveSolverSnapshot
- active surface: solver_design
- branch/champion provenance
- solve entrypoint
- active call graph
- construction path
- VNS/local-search operator list
- ALNS loop and adaptive selection path
- acceptance path
- integration modules
- legacy/inactive surfaces excluded from active view
```

The hypothesis stage should not infer these facts from an 800-character file
preview. It should either receive this snapshot automatically or be required to
call a tool that returns it.

### 3. Tools Are Host Protocol, Not Free Text

Claude Code's tool path is a host-controlled protocol: schema, semantic
validation, permissions, execution, result mapping, result budget, and error
feedback all belong to the host. The model asks for a tool call; the host
validates and returns a `tool_result`.

Scion should keep tools even stricter than Claude Code because Scion is a
controlled research system:

- no arbitrary shell;
- no direct repository writes;
- no direct promotion or validation-set inspection;
- phase-specific tool pools;
- every tool call, input, output, repair, and validator result gets an artifact
  id.

The useful transfer is the protocol shape, not broad execution power.

### 4. Errors Are Model-Visible Observations

Claude Code turns validation failures, permission failures, and execution errors
into structured tool results that the model can repair against. Scion should do
the same for proposal errors.

A failed observation should be short, typed, and actionable:

```text
kind
json_pointer
path
rule_id
message
repair_hint
tainted
artifact_ref
```

This matters for `additional_changes` and contract-preview repair. A generic
"schema invalid" response wastes retries; a precise rule/path/hint lets the code
phase repair the actual issue.

### 5. Structured Output Through a Submit Tool

Claude Code's structured-output path is effectively a hidden/synthetic tool:
the model must call a schema-backed output tool, and stop hooks can force a
retry if it ends without producing the required object.

Scion should stop relying on large free-text JSON blobs for code patches. The
final code phase should submit a typed patch-set object:

```text
submit_patch_set
- premise_check:
    supported | contradicted | duplicate | wrong_owner
- primary_change
- additional_changes[]
- created_files[]
- deleted_files[]
- integration_edges[]
- evidence_refs[]
- self_check_summary
```

If `premise_check` is `contradicted` or `duplicate`, no patch should be emitted.
That is a successful research outcome, not a code-generation failure.

### 6. Dynamic Tool Pools By Phase

Claude Code filters tool availability before the model sees tools. Scion needs
the same idea, but with Scion-specific boundaries:

- hypothesis phase: read active solver snapshot, read allowed algorithm files,
  query prior failures, run grounding preview;
- code phase: read branch-current files, submit patch set, run patch graph
  preview, run host-owned smoke/contract previews;
- verification phase: still host-owned, not an agent tool;
- decision phase: never an agent tool.

This keeps agent flexibility inside the Creative Layer while preserving v3's
separation between tainted generation and deterministic control.

## Required Scion Repairs

### P0: Active Solver Grounding

Add first-class active algorithm reading tools:

```text
context.read_active_solver_design
context.read_solver_call_graph
context.list_algorithm_files
context.read_algorithm_file
context.read_algorithm_symbol
```

The important distinction is provenance. These tools must say whether a fact
comes from branch-current code, champion reference, adapter metadata, legacy
surface text, or experiment memory.

Hypothesis output should gain a required `grounding` block:

```text
grounding
- active_entrypoint
- current_mechanism_summary
- claimed_gap
- evidence_refs
- not_already_implemented_reason
- target_module
- integration_path
```

Acceptance criterion: claims like "baseline only has nearest-neighbor",
"adaptive weights are uniform throughout", or "cross-route Or-opt is missing"
must be rejected before code generation when contradicted by the active solver
snapshot.

### P0: Mechanism Novelty Gate

Add a deterministic or semi-deterministic novelty gate before code generation:

```text
HypothesisGroundingGate
MechanismNoveltyGate
CapabilitySignature
```

This gate should compare the claimed gap against active mechanisms. It should
not decide whether the algorithm idea is good. It should only block proposals
that optimize a nonexistent gap or duplicate an existing mechanism.

Acceptance criterion: duplicate-mechanism attempts end as
`HYPOTHESIS_DUPLICATE_MECHANISM` and do not consume code or screening budget.

### P0: Code-Phase Premise Revalidation

The code phase must be allowed to invalidate the hypothesis after it reads the
full target or integration files.

Add a required code-phase result field:

```text
premise_check:
  supported | contradicted | duplicate | wrong_owner
```

If the full target content contradicts the hypothesis, the code phase should
return a structured rejection with evidence refs. This prevents the current
failure mode where the code model sees enough code to disprove the hypothesis
but still implements it.

### P0: Patch-Set Graph Validation

Round 4 showed that Scion is not yet validating patches as a graph. A patch set
must be modeled as:

- file nodes;
- symbol nodes;
- integration edges;
- import edges;
- evaluation/runtime edges;
- editable-boundary annotations.

Add:

```text
CandidatePatchGraph
PatchSetGraphValidator
PatchSetImportResolver
```

The import whitelist should be evaluated after the same-patch file graph is
known. A new module created in `policies/baseline_modules/` and imported from
another changed module in the same patch set should be allowed if the package
boundary and frozen constraints are respected.

Acceptance criterion: a patch that creates
`policies/baseline_modules/recombination.py` and wires it from `scheduler.py`
does not fail C8 merely because the import target is new in the same patch.

### P0: Structured Patch Output And Repair

Add a typed patch submission tool or equivalent structured-output adapter:

```text
StructuredPatchEmitter
PatchSetOutputTool
PatchFileArtifactRef
```

Separate repairs into two classes:

- mechanical normalization: JSON string to array, sorting, deduping, empty-array
  normalization, recorded as host repair;
- semantic repair: path violation, missing full content, orphan helper,
  boundary violation, failed import edge, returned to the model as a typed
  observation.

Acceptance criterion: `additional_changes` string/escaping failures should not
be reported as generic code-generation failure; they should be repaired
mechanically or returned as a precise structured-output error.

## P1 Repairs

### Observation Budgeting And De-Duplication

Add an `ObservationBudgeter`:

```text
Observation
- observation_id
- tool
- args_hash
- source_hash
- phase
- artifact_ref
- preview
- digest
- source_provenance
- prompt_visible_chars
```

Repeated calls with the same `{tool,args,source_hash,phase}` should return a
short "already read" reference instead of reinjecting the full observation. This
directly addresses repeated `context.read_surface` loops that crowd out required
branch-state or integration context.

### Surface Role Filtering

Add surface roles:

```text
active_boundary
implementation_hook
legacy_reference
inactive
```

For `solver_design` runs, legacy component surfaces may remain available as
auditable references, but they should not appear in the primary hypothesis view
as active evidence. This prevents stale defaults such as
`construction_methods = ["nearest_neighbor"]` from anchoring the agent away from
the actual active algorithm.

### Retry And Failure Attribution

Add a retry ledger with separated failure kinds:

```text
schema_output_failure
structured_output_retry_exhausted
contract_boundary_failure
patch_graph_failure
framework_policy_bug
model_repair_failed
tool_budget_exhausted
premise_contradicted
duplicate_mechanism
```

The campaign summary should preserve each attempt's first root cause and later
repair failures. This is necessary so future memory does not learn "recombination
failed" when the real event was "framework import graph rejected a legal same-
patch module."

## P2 Repairs

### Structured Session Memory

Use a fixed session-memory template for proposal sessions:

```text
Active Solver State
Observed Evidence
Rejected Premises
Current Hypothesis
Patch Premise Check
Open Next Step
```

When context needs compression, render this structure rather than asking an LLM
to summarize from scratch. Attach champion version, problem spec hash, surface
schema, and source provenance to every memory item so stale memory is not treated
as current branch truth.

### Surface Invariant Registry

`solver_design` invariants are currently spread across prompt text, adapter
rendering, contract checks, smoke checks, and protocol behavior. Add a single
registry:

```text
SurfaceInvariantRegistry
SolverDesignInvariantSuite
```

Every invariant should have one declaration source and at least one deterministic
enforcement layer.

## Source-Inspection References

Subagent source inspection reported these Claude Code source areas as the most
relevant references:

- `/home/clawd/research/claude-code-src/src/query.ts`: API-visible message
  projection and per-call context assembly.
- `/home/clawd/research/claude-code-src/src/services/compact/*.ts`: compact,
  autocompact, and session-memory compact.
- `/home/clawd/research/claude-code-src/src/utils/toolResultStorage.ts`: large
  tool-result persistence, previews, and stable replacement.
- `/home/clawd/research/claude-code-src/src/utils/messages.ts`: API message
  normalization and tool-use/tool-result pairing.
- `/home/clawd/research/claude-code-src/src/Tool.ts`: tool contract shape.
- `/home/clawd/research/claude-code-src/src/tools.ts` and
  `/home/clawd/research/claude-code-src/src/utils/toolPool.ts`: dynamic tool
  pool assembly and filtering.
- `/home/clawd/research/claude-code-src/src/services/tools/toolExecution.ts`:
  tool validation, permission, execution, and error-result pipeline.
- `/home/clawd/research/claude-code-src/src/tools/SyntheticOutputTool/`: schema
  backed structured-output submission.
- `/home/clawd/research/claude-code-src/src/utils/permissions/`: layered
  permissions and fail-closed classification.

Existing analysis documents that should remain the primary written reference:

- `/home/clawd/research/claude-code-src/analysis/02-query-engine.md`
- `/home/clawd/research/claude-code-src/analysis/04-compact-core.md`
- `/home/clawd/research/claude-code-src/analysis/05-microcompact-token.md`
- `/home/clawd/research/claude-code-src/analysis/06-query-context-management.md`
- `/home/clawd/research/claude-code-src/analysis/08-output-parsing-design.md`
- `/home/clawd/research/claude-code-src/analysis/10-prompt-engineering.md`
- `/home/clawd/research/claude-code-src/analysis/11-tool-system.md`
- `/home/clawd/research/claude-code-src/analysis/12-memory-and-compact-deep.md`
- `/home/clawd/research/claude-code-src/analysis/14-services-core.md`

## Next Experiment Gate

After implementing the P0 repairs, the next monitored experiment should pass
these framework-level criteria before running another six-round validation:

- every hypothesis has a grounded active solver summary;
- repeated active-mechanism mistakes are stopped before code generation;
- code phase can return `premise_check=duplicate` or `contradicted`;
- same-patch new modules can be imported inside the editable solver package;
- `additional_changes` shape errors produce structured repair, not generic
  code failure;
- repeated `read_surface` calls do not crowd out required observations;
- failures in the report distinguish grounding failure, framework gate failure,
  schema failure, smoke failure, and true screening loss.

Promotion is not required for this gate. The key signal is that failures move
from context/framework/protocol mistakes to real algorithmic outcomes.
