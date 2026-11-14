# ProposalPipeline / ContextManager / AgenticProposalSession

## Scope

Current source reviewed:

- `scion/scion/core/proposal_pipeline/facade.py`
- `scion/scion/core/proposal_pipeline/agentic_requests.py`
- `scion/scion/core/proposal_pipeline/agentic_lifecycle.py`
- `scion/scion/core/proposal_pipeline/agentic_validation.py`
- `scion/scion/core/proposal_pipeline/agentic_refs.py`
- `scion/scion/core/proposal_pipeline/boundaries.py`
- `scion/scion/core/problem_runtime.py`
- `scion/scion/core/campaign_composition.py`
- `scion/scion/proposal/context_manager/manager.py`
- `scion/scion/proposal/context_manager/guidance.py`
- `scion/scion/proposal/engine/hypothesis_context_profiles.py`
- `scion/scion/proposal/search_memory.py`
- `scion/scion/proposal/tools/models.py`
- `scion/scion/proposal/tools/registry.py`
- `scion/scion/proposal/tools/utils.py`
- `scion/scion/proposal/tools/previews/schema.py`
- `scion/scion/proposal/tools/previews/contract.py`
- `scion/scion/proposal/tools/previews/algorithm_smoke.py`
- `scion/scion/proposal/agentic_session_preview_tools.py`
- `scion/scion/proposal/agentic_artifact_payloads.py`
- `scion/scion/proposal/agentic_artifacts.py`
- selected proposal, agentic-session, context-profile, and tool-exposure tests

## Current Understanding

The proposal stack is a tainted guidance producer, not a decision or promotion
owner.

```text
CampaignManager
  -> ProblemRuntime
       -> ContextManager
            -> full hypothesis/code context
  -> ProposalPipeline
       -> prompt-visible context projection
       -> creative LLM or AgenticProposalSession
       -> tainted HypothesisProposal / PatchProposal
  -> downstream ContractGate / VerificationGate / protocol / decision
```

`CampaignManager` constructs `ProblemRuntime` and `ProposalPipeline` together.
It also injects campaign/problem/split/seed anchors into the proposal pipeline.

Evidence:

- `ProblemRuntime` owns the legacy spec, adapter, and `ContextManager`:
  - `scion/scion/core/problem_runtime.py:24`
  - `scion/scion/core/problem_runtime.py:40`
- campaign composition wires the proposal pipeline and anchors:
  - `scion/scion/core/campaign_composition.py:544`
  - `scion/scion/core/campaign_composition.py:574`
- `ProposalPipeline.generate_hypothesis(...)` builds full context, adds
  branch hygiene and prior agentic feedback, then filters before generation:
  - `scion/scion/core/proposal_pipeline/facade.py:169`
  - `scion/scion/core/proposal_pipeline/facade.py:214`
- `generate_code(...)` uses code context only after a hypothesis exists:
  - `scion/scion/core/proposal_pipeline/facade.py:334`
  - `scion/scion/core/proposal_pipeline/facade.py:348`

## Positive Boundary Observations

- Hypothesis context is explicitly projected before prompt use. The projection
  removes full branch dossiers, research-log payloads, cross-branch audit/session
  metadata, and branch-followup payloads. It also marks the prompt context as
  proposal-only and excluded from decision features.
- ContextManager's current search memory implementation records proposal-visible
  memory from screening and pre-protocol failures, and hides champion evolution
  from the hypothesis view.
- Agentic requests carry campaign, branch, champion, problem, split, seed, and
  context-profile anchors.
- Agentic code context requires a ContractGate-approved hypothesis and rejects
  mismatched hypotheses before building code context.
- Agentic outputs are revalidated against branch/champion/problem/split/seed
  anchors and active boundary constraints before the pipeline accepts them.
- If an agentic hypothesis-phase session returns a patch before ContractGate
  approval, the pipeline downgrades it to `PARTIAL_HYPOTHESIS_ONLY` and strips
  the patch.
- The default tool registry accepts read-only tools only. Permission policy
  denies draft artifacts and contract previews by default.
- Draft patch/hypothesis tools return tainted scratch artifacts; they do not
  materialize workspace writes.
- Contract and algorithm-smoke previews mark their payloads as proposal-only,
  non-promotional, and not protocol/decision runs.
- Agentic artifacts are written below a bounded artifact root, indexed as tainted,
  and stored with artifact-dir-relative public refs.
- Agentic idempotency keys include campaign/branch/champion/problem/split/seed
  anchors plus policy and tool-loop config.
- Artifact replay validation checks required fields, monotonic tool step ids,
  tool budget bounds, transcript digest, and raw-reference markers.
- Resume context is sanitized and exposes a bounded model-facing projection.

Evidence:

- prompt projection:
  - `scion/scion/proposal/engine/hypothesis_context_profiles.py:75`
  - `scion/scion/proposal/engine/hypothesis_context_profiles.py:109`
  - `scion/scion/tests/unit/test_hypothesis_context_profiles.py:145`
  - `scion/scion/tests/unit/test_hypothesis_context_profiles.py:163`
- search memory screening/promotion separation:
  - `scion/scion/proposal/search_memory.py:169`
  - `scion/scion/proposal/search_memory.py:181`
  - `scion/scion/proposal/search_memory.py:371`
  - `scion/scion/proposal/search_memory.py:383`
- agentic request anchors and code-context approval guard:
  - `scion/scion/core/proposal_pipeline/agentic_requests.py:60`
  - `scion/scion/core/proposal_pipeline/agentic_requests.py:122`
- output validation and pre-contract patch stripping:
  - `scion/scion/core/proposal_pipeline/agentic_validation.py:47`
  - `scion/scion/core/proposal_pipeline/agentic_validation.py:154`
  - `scion/scion/core/proposal_pipeline/agentic_validation.py:156`
  - `scion/scion/core/proposal_pipeline/agentic_validation.py:175`
- lifecycle records refs only after validation/sanitization:
  - `scion/scion/core/proposal_pipeline/agentic_lifecycle.py:94`
  - `scion/scion/core/proposal_pipeline/agentic_lifecycle.py:146`
- read-only registry and permission policy:
  - `scion/scion/proposal/tools/registry.py:68`
  - `scion/scion/proposal/tools/registry.py:77`
  - `scion/scion/proposal/tools/models.py:51`
  - `scion/scion/proposal/tools/models.py:88`
- default deny / explicit allow tests:
  - `scion/scion/tests/unit/test_agentic_schema_permissions_budget.py:27`
  - `scion/scion/tests/unit/test_agentic_schema_permissions_budget.py:70`
- forbidden planner tool tests:
  - `scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py:82`
  - `scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py:171`
- artifact taint/idempotency/replay:
  - `scion/scion/proposal/agentic_artifact_payloads.py:185`
  - `scion/scion/proposal/agentic_artifact_payloads.py:284`
  - `scion/scion/proposal/agentic_artifact_payloads.py:403`
  - `scion/scion/proposal/agentic_artifact_payloads.py:465`
  - `scion/scion/proposal/agentic_artifacts.py:345`
  - `scion/scion/proposal/agentic_artifacts.py:447`
  - `scion/scion/proposal/agentic_artifacts.py:654`
  - `scion/scion/proposal/agentic_artifacts.py:708`
  - `scion/scion/proposal/agentic_artifacts.py:710`
  - `scion/scion/proposal/agentic_artifacts.py:798`
  - `scion/scion/proposal/agentic_artifacts.py:855`
  - `scion/scion/proposal/agentic_artifacts.py:1012`

## Risks And Findings

### F-PROPOSAL-001 [P2] Context/tool exposure safety is enforced per consumer, not at the proposal boundary

The prompt path and tool path have strong current tests, but the exposure model
is distributed. `ProposalToolContext` carries raw campaign objects, including
the full `StepRecord` tuple, `search_memory`, and `research_log`. Individual
tools are then responsible for projecting safe fields before returning
observations.

The registry strips forbidden keys from tool specs and error observations, but
successful observations are returned directly after size checks. Most current
tools call shared helpers or implement their own filtering, and tests cover many
current tools. The risk is extension drift: a new read-only tool or injected
memory implementation can accidentally expose validation/frozen/raw refs or
promotion-derived text into proposal guidance.

Evidence:

- tool context includes raw campaign objects:
  - `scion/scion/proposal/tools/models.py:90`
  - `scion/scion/proposal/tools/models.py:115`
  - `scion/scion/core/proposal_pipeline/agentic_requests.py:161`
  - `scion/scion/core/proposal_pipeline/agentic_requests.py:196`
- registry returns successful observations without a generic success sanitizer:
  - `scion/scion/proposal/tools/registry.py:175`
  - `scion/scion/proposal/tools/registry.py:210`
- shared stripping exists, but tools must use it on their own payloads:
  - `scion/scion/proposal/tools/utils.py:20`
  - `scion/scion/proposal/tools/utils.py:89`
- `ContextManager` directly injects rendered search memory into the hypothesis
  context:
  - `scion/scion/proposal/context_manager/manager.py:505`
  - `scion/scion/proposal/context_manager/manager.py:515`
  - `scion/scion/proposal/context_manager/manager.py:660`
- current `MemoryQueryTool` tests reject unsafe default memory, but that is a
  tool-path guard, not a general `ContextManager` injection guard:
  - `scion/scion/tests/unit/test_agentic_feedback_memory_holdout.py:36`
  - `scion/scion/tests/unit/test_agentic_feedback_memory_holdout.py:61`

Why this matters:

- Proposal guidance is tainted and excluded from decisions, but it still shapes
  future hypotheses. Leaked holdout/frozen/promotion information can bias search.
- "Read-only" is not enough as a model-safety boundary. A read-only tool can
  still leak data if it receives raw objects and returns an unsanitized payload.
- The current protections are broad but not centralized, so future tool additions
  need reviewers to remember several scattered invariants.

Suggested fix direction:

- Build a `SafeProposalToolContext` or `ProposalPromptEvidenceView` that contains
  already-projected screening-only histories instead of raw `StepRecord` objects.
- Add registry-level sanitization for every successful observation, including
  forbidden-key stripping and raw-marker string checks.
- Require a safe memory protocol for `ContextManager` injection, not just
  best-effort `render(view="hypothesis")`.
- Add a negative `ContextManager` test with a malicious custom `search_memory`
  renderer and assert holdout/raw/promotion markers are not prompt-visible.

### F-PROPOSAL-002 [P2] Generic proposal stack still hardwires solver-design / algorithm-smoke semantics

This repeats the boundary theme from the ProblemSpec/Adapter pass, but here the
special case appears inside the proposal machinery itself. Generic proposal code
detects `solver_design` and `solver_algorithm` surface kinds/roles, generates
solver-design plateau guidance, builds solver-design code-context fields, exposes
solver-design grounding helpers, and runs a deterministic `proposal.algorithm_smoke`
tool backed by `scion.proposal.solver_design_smoke`.

This may be an intentional v0.4 framework concept. If so, `solver_design` needs
to be documented as a generic first-class surface contract. If not, this is a
CVRP-era compatibility path that has become part of core proposal behavior.

Evidence:

- generic proposal boundary detection names solver-design explicitly:
  - `scion/scion/core/proposal_pipeline/boundaries.py:27`
  - `scion/scion/core/proposal_pipeline/boundaries.py:43`
- ContextManager resolves solver-design prompt providers and code-context fields:
  - `scion/scion/proposal/context_manager/manager.py:534`
  - `scion/scion/proposal/context_manager/manager.py:546`
  - `scion/scion/proposal/context_manager/manager.py:773`
  - `scion/scion/proposal/context_manager/manager.py:848`
- generic guidance has solver-design plateau logic:
  - `scion/scion/proposal/context_manager/guidance.py:365`
  - `scion/scion/proposal/context_manager/guidance.py:429`
  - `scion/scion/proposal/context_manager/guidance.py:603`
  - `scion/scion/proposal/context_manager/guidance.py:684`
- deterministic agentic self-check invokes `proposal.algorithm_smoke`:
  - `scion/scion/proposal/agentic_session_preview_tools.py:95`
  - `scion/scion/proposal/agentic_session_preview_tools.py:112`
- `AlgorithmSmokeTool` imports and re-exports solver-design-smoke helpers:
  - `scion/scion/proposal/tools/previews/algorithm_smoke.py:8`
  - `scion/scion/proposal/tools/previews/algorithm_smoke.py:90`
- algorithm-smoke artifacts/transcripts carry solver-design-specific metadata:
  - `scion/scion/proposal/agentic_artifact_payloads.py:82`
  - `scion/scion/proposal/agentic_artifact_payloads.py:114`

Why this matters:

- New problems with a different first-class algorithm surface name may not get
  grounding, plateau control, code-context support, or smoke preview unless they
  adopt the `solver_design` vocabulary.
- Boundary tests can miss this if `solver_design` is treated as "not CVRP" but
  still encodes the original solver-domain assumptions.
- It is hard to tell whether proposal behavior is generic framework logic or a
  problem/provider plugin.

Suggested fix direction:

- Decide explicitly whether `solver_design` is a generic Scion surface kind.
- If yes, document the generic contract and rename user-facing internals toward
  something like `algorithm_surface` or `runtime_preview_surface` where possible.
- If no, move algorithm smoke behind a problem-owned/provider-owned preview
  interface and keep CVRP/solver-specific smoke behavior in problem packages.
- Extend the generic-layer boundary test to cover `agentic_session_preview_tools`,
  `tools/previews/algorithm_smoke.py`, `context_manager/guidance.py`, and
  agentic artifact metadata allowlists.

### F-PROPOSAL-003 [P2] Tool phase policy is implicit and spread across registry, policy, planner, and fallback previews

The current behavior appears deliberately conservative: default policy denies
draft and contract-preview permissions, tests verify forbidden planner tool
requests are not executed, and first planner contexts can exclude preview tools.
However, the effective policy is not represented in one place. It emerges from:

- `ContextExposurePolicy`;
- the default registry containing all read-only tools, including draft and
  preview tools;
- the tool context constructed by `ProposalPipeline`;
- planner-phase filtering inside `AgenticProposalSession`;
- deterministic fallback preview calls.

That makes it easy for future changes to accidentally make a tool
model-selectable in the wrong phase, or to confuse "framework-only deterministic
self-check" with "LLM-selectable tool."

Evidence:

- policy defaults and permission mapping:
  - `scion/scion/proposal/tools/models.py:51`
  - `scion/scion/proposal/tools/models.py:88`
- pipeline enables contract preview in the agentic tool context:
  - `scion/scion/core/proposal_pipeline/agentic_requests.py:161`
  - `scion/scion/core/proposal_pipeline/agentic_requests.py:174`
- default registry includes public context tools, memory/feedback tools, draft
  tools, and preview tools:
  - `scion/scion/proposal/tools/registry.py:212`
  - `scion/scion/proposal/tools/registry.py:241`
- deterministic fallback preview calls are separate from planner choices:
  - `scion/scion/proposal/agentic_session_preview_tools.py:8`
  - `scion/scion/proposal/agentic_session_preview_tools.py:41`
  - `scion/scion/proposal/agentic_session_preview_tools.py:76`
  - `scion/scion/proposal/agentic_session_preview_tools.py:112`
- tests show default deny and planner rejection:
  - `scion/scion/tests/unit/test_agentic_schema_permissions_budget.py:27`
  - `scion/scion/tests/unit/test_agentic_schema_permissions_budget.py:70`
  - `scion/scion/tests/unit/test_agentic_session_model_planner.py:96`
  - `scion/scion/tests/unit/test_agentic_session_model_planner.py:107`
  - `scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py:82`
  - `scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py:171`

Why this matters:

- The registry name `default_read_only` is accurate for workspace mutation, but
  it is not a complete statement of model exposure or campaign-safety semantics.
- A new preview or draft-like tool can be read-only while still exposing powerful
  guidance or tainted scratch artifacts.
- Reviewers need a phase-by-phase view to audit what the model can call versus
  what the framework can run deterministically.

Suggested fix direction:

- Add an explicit phase policy table for orient, hypothesis planning, hypothesis
  self-check, code planning, code self-check, and repair.
- Separate `model_selectable_tools` from `framework_preview_tools`.
- Snapshot-test default production allowed tools for each phase.
- Keep draft tools behind an explicit opt-in flag or test-only fixture unless
  production needs model-selectable draft artifacts.

### F-PROPOSAL-004 [P3] Direct agentic-session injection can bypass production-anchor preflight if callers forget the flag

The normal campaign-composition path sets `require_agentic_problem_anchors` when
`use_agentic_proposal` and `production_campaign` are both true. But
`ProposalPipeline` also treats an injected `agentic_session` as enabling the
agentic path. In direct/programmatic construction, a caller can pass
`agentic_session` while leaving `use_agentic_proposal=False` and
`require_agentic_problem_anchors=False`.

Output validation still checks any expected anchors that exist, and tests cover
missing/mismatched anchors in the normal agentic path. The gap is preflight:
there is no single constructor-level invariant that says a production-like
agentic session must have problem/split/seed anchors before the session runs.

Evidence:

- agentic path is enabled by `use_agentic_proposal` or injected session:
  - `scion/scion/core/proposal_pipeline/agentic_requests.py:32`
  - `scion/scion/core/proposal_pipeline/agentic_requests.py:35`
- campaign composition derives the preflight flag only from
  `use_agentic_proposal` and `production_campaign`:
  - `scion/scion/core/campaign_composition.py:572`
  - `scion/scion/core/campaign_composition.py:574`
- preflight only runs when `require_agentic_problem_anchors` is true:
  - `scion/scion/core/proposal_pipeline/agentic_validation.py:20`
  - `scion/scion/core/proposal_pipeline/agentic_validation.py:32`
- tests cover explicit preflight and output-anchor rejection:
  - `scion/scion/tests/unit/core/test_proposal_pipeline_failure_paths.py:77`
  - `scion/scion/tests/unit/core/test_proposal_pipeline_failure_paths.py:156`
  - `scion/scion/tests/unit/core/test_proposal_pipeline_failure_paths.py:159`
  - `scion/scion/tests/unit/core/test_proposal_pipeline_failure_paths.py:185`
  - `scion/scion/tests/unit/core/test_proposal_pipeline_failure_paths.py:200`
  - `scion/scion/tests/unit/core/test_proposal_pipeline_failure_paths.py:235`

Why this matters:

- The main CLI/campaign path is probably safe. The risk is lower-level API drift
  and tests or tools that instantiate `ProposalPipeline` directly.
- Agentic artifacts and idempotency keys are much easier to audit when anchors
  are always present before the session starts.

Suggested fix direction:

- Derive preflight from "agentic enabled and production campaign", not just
  `use_agentic_proposal`.
- Add a `ProposalPipeline.__post_init__` guard or factory that rejects
  production-like agentic construction without expected anchors.
- Add a direct-construction regression test with `agentic_session` injected and
  `use_agentic_proposal=False`.

## Open Questions

- Is `solver_design` now a first-class generic Scion surface kind, or should it
  be treated as a CVRP-era provider/plugin path?
- Should `ContextManager` accept arbitrary `search_memory`/`research_log`
  renderers, or should these implement an explicit safe-view protocol?
- Should contract preview be a model-selectable tool in any production phase, or
  only a deterministic framework self-check?
- Should successful proposal-tool observations be sanitized at the registry
  boundary even when individual tools already call safe helpers?

## Suggested Next Audit Target

Next best target: `ContractGate` and problem-owned contract checks.

Reason: proposal/session output becomes actionable only after ContractGate. The
next pass should verify that tainted hypotheses and patches are converted into
structured, problem-owned contract checks without letting preview/self-check
results substitute for real contract validation.

