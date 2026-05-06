# Proposal Context

## Scope / Sources

Sources read: `scion/scion/core/proposal_pipeline.py`, `scion/scion/core/problem_runtime.py`, `scion/scion/proposal/context_manager.py`, `engine.py`, `schemas.py`, `search_memory.py`, `classifier.py`, `research_log.py`, `saturation.py`, `mechanism_labels.py`, plus `ProblemSpecV1` research surface/taxonomy fields in `scion/scion/problem/spec.py`.

## ProposalPipeline Boundary

`ProposalPipeline` owns LLM-facing lifecycle calls but not branch promotion/evaluation state. It exposes three operations:

- `generate_hypothesis(branch) -> (HypothesisProposal | None, HypothesisRecord | None)`
- `generate_code(branch, hypothesis, prior_failure=None) -> PatchProposal | None`
- `attempt_fix(branch, patch, verification_result) -> PatchProposal | None`

Inputs come from campaign services: current branch, champion snapshot, active/blacklisted hypotheses, sibling branches, step history, failure streaks, forced locus, search memory, saturation signals, latest weight optimization result, and research log. The pipeline delegates context construction to `ProblemRuntime`, which pre-fills the active `ProblemSpec` and optional adapter.

LLM failures are routed as proposal failures. `LLMBalanceError` marks balance exhausted; retry exhaustion, format errors, timeout, and schema validation errors increment circuit breaker state and call the campaign failure handler. Successful hypothesis generation creates a `HypothesisRecord` with classifier-derived family metadata.

As of RS2-5, `ProposalPipeline` also has an explicit opt-in Agentic Proposal
Session path (`use_agentic_proposal` or injected `agentic_session`). The default
path above remains the normal behavior. The APS-1 skeleton wraps the current
hypothesis/code generation flow. Hypothesis-phase sessions may return only an
unapproved `HypothesisProposal`; any completed output containing a patch before
external ContractGate approval is downgraded to a partial hypothesis and the
patch is discarded. Downstream contract, workspace, verification, protocol, and
decision services still see only the existing proposal dataclasses. Completed
agentic sessions are recorded as compact `proposal_session_ref` metadata on
step and campaign summaries, and `ProposalPipeline` emits tainted
`agentic_proposal_session` lineage events. Transcript, rationale, observations,
and patch content remain outside `DecisionFeatures`.

## CreativeLayer and Schemas

`CreativeLayer` in `scion/scion/proposal/engine.py` is the tainted LLM boundary. It uses tool schemas from `scion/scion/proposal/schemas.py` and parses tool outputs through Pydantic input models before producing core dataclasses:

- `HypothesisProposalInput` -> `HypothesisProposal`
- `PatchProposalInput` -> `PatchProposal`

The schema requires hypothesis text, research surface/locus, action, target file where applicable, objective intent, protected objectives, no-op condition, runtime intent, complexity claim, and runtime budget strategy. Patch output is complete file content, not a diff.

Trace writing under campaign `llm_traces` records prompt/tool/schema/response metadata for auditability. Trace writing is best-effort and does not define campaign semantics.

`AgenticProposalSession` in `scion/scion/proposal/agentic_session.py` is the
APS-1 tainted session shell. It defines session state, status and termination
enums, `AgenticProposalOutput`, transcript events, a minimal artifact-store
protocol, and `FileAgenticSessionArtifactStore`. The file store writes only
below its configured artifact directory. Completed outputs expose
`HypothesisProposal` and `PatchProposal`; failed or partial outputs stay typed
proposal failures and do not materialize candidate workspaces.

`ProposalToolRegistry` in `scion/scion/proposal/tools.py` is the APS-2/APS-3
tool boundary. It owns tool input validation, permission checks, and mapping
results to `ProposalObservation` objects. `ContextExposurePolicy` enforces
exposure in code: default policy allows screening detail and screening-derived
runtime guidance, hides validation/frozen holdout rows, does not expose raw
metrics refs, restricts champion artifact reads to declared research-surface
targets, and permits only side-effect-free drafting/static-preview tools.

The MVP registry exposes context, memory, screening feedback, holdout-summary,
runtime-feedback, `proposal.draft_hypothesis`, `proposal.draft_patch`,
`proposal.schema_preview`, `proposal.target_permission_preview`,
`proposal.interface_preview`, and `proposal.contract_preview`. Draft tools
return tainted typed artifacts and do not materialize candidate workspaces.
Preview tools validate in-memory hypothesis/patch content through schema checks
and existing `ContractGate` static checks where practical. The registry still
does not include Verification/Protocol/Decision execution or candidate-workspace
write tools.

## ContextManager Inputs

`ContextManager` in `scion/scion/proposal/context_manager.py` builds three context types:

- Hypothesis context: broad research context and campaign memory.
- Code context: approved hypothesis, target file, interface, imports, current champion code.
- Fix context: failed patch, verification details, interface/import constraints.

Hypothesis context includes:

- problem summary, preferably from `ProblemAdapter.render_problem_summary()`;
- solver mechanics, preferably from adapter `render_solver_mechanics()`;
- declared research surfaces from `ProblemSpec.research_surfaces` or `ProblemSpecV1.research_surfaces`;
- champion research-surface code and policy surface code;
- branch-specific history from `StepRecord`;
- blacklist and active hypothesis summaries;
- sibling branch summary;
- exploration coverage and strategy guidance;
- recent screening objective feedback and objective opportunity profile;
- runtime feedback from verification/screening facts;
- search memory and research log;
- saturation/weight optimization feedback;
- forced locus constraint when governance requests diversification.

Code and fix contexts deliberately exclude experiment history and protocol stats. They are implementation contexts, not research decision contexts.

## Exposure Control

The context manager enforces a data exposure matrix:

- Hypothesis context excludes validation/frozen per-case detail, raw metrics,
  and aggregate holdout stats by default.
- Hypothesis context includes screening aggregates from step history. It does
  not render validation/frozen aggregate stats such as win rate, median delta,
  or gate outcome from `ProtocolResult`; holdout exposure must stay at a
  separately documented safe summary level.
- Code context excludes experiment stats and branch history.
- Fix context excludes experiment stats and branch history.
- `EvaluationPipeline` separately sanitizes validation/frozen `ProtocolResult`
  objects by clearing pair/case feedback. Those sanitized holdout aggregates
  are still not proposal-context identity or history inputs by default.

This is central to preserving holdout integrity. Any future prompt feature should state whether it is screening-only, aggregate-only, or forbidden in proposal context.

## Research Surfaces

Research surfaces come from `ProblemSpecV1.research_surfaces` and are bridged into legacy `ProblemSpec` in `scion/scion/problem/bridge.py`. `ContextManager` renders them with name, kind, target files, required functions, and prompt hints. As of RS2-2 it also renders v2 metadata as problem-provided context: algorithm role/invocation point/description, target action permissions and singleton flag, interface return contract, bounds, required runtime evidence fields, novelty metadata, and prompt guidance. Core prompt text does not interpret problem-specific component names, scale terms, or runtime field names.

`ContractGate` also uses research surfaces:

- `C2` checks `change_locus` against problem-defined categories.
- `C3` enforces action/target-file compatibility and surface-level allow flags.
- `C7` validates operator class `execute` signatures and declared
  module-function surface interfaces, including policy, config, portfolio,
  construction, and acceptance/restart surfaces.
- Surface kind typos fail closed; supported generic kinds are `operator`,
  `policy`, `config`, `portfolio`, `construction`, and
  `acceptance_restart`.
- `semantic_signature` novelty uses only declared structured fields persisted
  on proposals/records. Free-text rationale fields do not affect identity.

This means algorithm design space expansion should start in problem package `problem-v1.yaml` and adapter rendering, not by hardcoding new loci in core.

## Search Memory and Taxonomy

`CampaignSearchMemory` is updated from every `StepRecord` by `EvidenceRecorder.record_step()`. It tracks family attempts, best screening win rate, exhausted families, promising families, coverage counts, recent hypothesis texts, and champion evolution.

Family labels are problem-taxonomy aware. `HypothesisFamilyClassifier` accepts `ProblemSpecV1.family_taxonomy` and falls back to keyword classification when LLM classification fails. The framework default taxonomy is intentionally domain-neutral; problem packages provide meaningful families and aliases.

`CampaignResearchLog` reads the lineage SQLite DB and renders campaign-level research journal sections. Its exposure rules are explicit: screening is detailed, validation aggregate, frozen pass/fail only.

## Prompt Assembly

`CreativeLayer` splits context into cacheable system blocks and dynamic user prompts:

- Hypothesis prompt: static role/problem/research surfaces/objective policy/solver mechanics, champion code/state, dynamic branch/search/history/task.
- Code prompt: static role/problem/interface/import rules, champion code, dynamic hypothesis/target/current file/reference files.
- Fix prompt: static problem/interface/import rules, dynamic failed code and verification details.

The split is an engineering optimization for prompt caching, but it also encodes stable separation between problem specification, champion state, and per-branch facts.

## Proposal Outputs

The proposal side produces only `HypothesisProposal`, `HypothesisRecord`, and `PatchProposal` for the normal candidate path. Agentic session artifacts, rationale, transcript, and rejected alternatives are tainted audit/proposal-memory material and are not inputs to `SafeFeatureExtractor` or `DecisionEngine`. The first framework gate after hypothesis creation is `ContractGate`; the first framework gate after code generation is also `ContractGate`, followed by workspace materialization and `VerificationGate`.

Current APS evidence integration stores only compact session refs in step and
campaign summaries. Those refs are audit/proposal-memory handles, not decision
inputs.
