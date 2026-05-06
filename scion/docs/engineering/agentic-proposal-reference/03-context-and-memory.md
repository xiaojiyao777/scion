# Context And Memory

## Core Separation

Claude Code's context system separates full history from API-visible history.
Scion needs the same split, but with a stronger evidence boundary:

```text
full proposal transcript        tainted, audit/debug
proposal memory                 tainted, Creative Layer guidance
campaign evidence               structured refs and summaries
DecisionFeatures                deterministic numeric/enumerated facts only
```

The proposal agent may read from controlled context views and write proposal
memory. It must not write Decision inputs.

## Message Boundary

Use four conceptual message classes:

| Message | Owner | May Enter Proposal Agent | May Enter Decision |
|---|---|---:|---:|
| System/developer policy | Scion framework | Yes | No |
| Problem/adaptor context | Problem package/framework | Yes | No directly |
| Tool observations | Proposal tools | Yes | No |
| Protocol/verification facts | Gates/protocol | Through controlled summaries | Through `SafeFeatureExtractor` only |

Decision should continue to see only `DecisionFeatures`, built from contract,
verification, protocol, runtime, budget, and stage facts. The proposal memory ref
may be recorded in lineage for audit, but not dereferenced by Decision.

## Exposure Control

Current Scion rules should remain:

- Hypothesis context can include screening detail and bounded runtime feedback.
- Validation context is aggregate-only.
- Frozen context is pass/fail/budget-only.
- Code/fix contexts exclude experiment stats and branch history.

Agentic sessions add risk because the model can ask tools for more. Therefore
tool permissions must encode exposure policy, not just prompt text.

Forbidden tool result categories:

```text
validation per-case metrics
frozen per-case metrics
raw validation/frozen metrics files
final evidence internals used as holdout detail
any benchmark answer/reference used as promotion oracle
```

Allowed with controls:

```text
screening case feedback
screening runtime ratios/failure causes
validation aggregate stats
frozen pass/fail and remaining budget
final BKS/gap only when explicitly report-only and not as proposal target
```

## Proposal Memory

Proposal memory should be a tainted store optimized for future proposal quality,
not for deterministic decisions.

Suggested record:

```text
ProposalMemoryEntry
- entry_id
- campaign_id
- branch_id?
- champion_version
- problem_id
- surface
- source_session_id
- entry_kind:
  surface_diagnosis | failed_plan | rejected_hypothesis | draft_patch |
  contract_preview | runtime_feedback_summary | compaction_summary |
- text_summary
- structured_tags
- artifact_ref?
- exposure_level
- created_at
```

Rules:

- It can store natural language.
- It can store draft code artifacts.
- It can store tool observations.
- It is always marked tainted.
- It can influence future proposal prompts.
- It cannot be read by `DecisionEngine`.
- If any field needs deterministic control, define a closed enum/numeric feature
  and route it through `SafeFeatureExtractor` from gate/protocol facts, not from
  memory text.

## How Tool Results Enter Proposal Memory

Flow:

```text
tool_result
-> ProposalObservation
-> transcript JSONL
-> optional ProposalMemoryEntry
-> compact proposal summary
-> next Creative Layer context
```

Decision flow remains separate:

```text
ContractResult / VerificationResult / ProtocolResult
-> SafeFeatureExtractor
-> DecisionFeatures
-> DecisionEngine
```

There should be no code path:

```text
ProposalObservation -> DecisionFeatures
```

If a proposal observation says "operator attempts=20 accepted=0", Decision still
does not read it from memory. Decision reads accepted/no-op/runtime facts only
when they are produced by protocol or verification and extracted as structured
features.

## Summary And Compaction

Scion can use structured compaction more than LLM compaction because campaign
artifacts are already typed. Recommended layers:

### Layer 1: Tool Result Budget

Large surface code, raw screening feedback, or trace fragments are persisted to
artifact files. The model receives preview + ref.

### Layer 2: Session Summary

When proposal session token usage crosses a threshold, summarize the session
into fixed sections:

```text
Primary request
Active branch/champion state
Selected research surface
Evidence observed
Rejected alternatives
Current hypothesis draft
Current patch draft
Contract-preview status
Open next step
Exposure denials / forbidden data requests
```

### Layer 3: Memory Consolidation

At session end, write durable proposal memory entries:

- one for final diagnosis;
- one for final output;
- one for each useful rejected alternative;
- one for failure mode if the session did not complete.

Do not let compaction summarize away explicit user/campaign constraints or
exposure-denial events.

## Permission And Visibility Controls

Context should be generated through named views:

```text
proposal_agent_view
code_generation_view
fix_generation_view
decision_feature_view
audit_view
```

`proposal_agent_view` may be broader than current hypothesis context because the
agent needs multi-step orientation, but it must still be narrower than
`audit_view`.

Suggested policy fields:

```text
ContextExposurePolicy
- allow_screening_case_detail: bool
- validation_exposure: none | aggregate
- frozen_exposure: none | pass_fail | aggregate
- allow_raw_metrics_refs: bool
- allow_raw_metrics_read: bool
- allow_champion_code_read: bool
- allow_candidate_workspace_read: bool
- allow_final_evidence_read: bool
```

Tools must consult this policy before returning results.

## Resume

Proposal sessions should be resumable only when their assumptions are still
valid:

```text
same campaign_id
same branch_id
same champion_version / weight_revision
same problem_spec hash
same exposure policy version
```

If any mismatch occurs, the session can still be used as historical proposal
memory, but not resumed as an active proposal. The agent must re-orient against
the new champion state.

## Avoiding Validation/Frozen Leakage

Concrete controls:

- No tool can open validation/frozen raw metrics paths.
- `ProtocolResult.raw_metrics_ref` is not expanded by proposal tools except for
  screening.
- Validation/frozen summaries are produced by `EvaluationPipeline` or
  `EvidenceRecorder`, not by an LLM reading raw files.
- Proposal memory entries carry `exposure_level`; compaction refuses to merge a
  forbidden detail into a lower-exposure summary.
- Final proposal output schema has no field for "holdout case insight."

The agent can know "validation failed aggregate runtime regression" if allowed.
It cannot know "case X in frozen failed because route Y did Z."

## Memory Drift

Proposal memory can go stale after:

- champion promotion;
- problem spec change;
- research surface schema change;
- adapter rendering change;
- validation/frozen budget exhaustion;
- CVRP policy/solver wrapper change.

Every memory entry should include enough version anchors to filter or warn:

```text
champion_version
weight_revision
problem_spec_hash
surface_schema_hash
context_policy_id
```

Old memory should be summarized as history, not treated as current fact.

## Recommended Rule

Treat proposal memory the way Scion treats LLM output:

```text
useful for creativity,
useful for audit,
useful for future prompts,
never sufficient for promotion.
```
