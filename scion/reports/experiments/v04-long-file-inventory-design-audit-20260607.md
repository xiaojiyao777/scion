# Scion v0.4 Long-File Inventory Design Audit

Date: 2026-06-07

Scope: read-only design audit of Python files over 1000 lines under
`scion/scion`. This is an inventory and prioritization report, not an
instruction to mechanically split every long file.

Design anchors:

- `scion/design/scion-architecture-v3.md`
- `scion/docs/AGENT_ONBOARDING.md`

Reproduced commands:

```bash
rg --files scion/scion -g '*.py' | xargs wc -l | awk '$1 > 1000 && $2 != "total" {print $1, $2}' | sort -nr
rg --files scion/scion -g '*.py' | grep -v '/tests/' | xargs wc -l | awk '$1 > 1000 && $2 != "total" {print $1, $2}' | sort -nr
rg --files scion/scion/tests -g '*.py' | xargs wc -l | awk '$1 > 1000 && $2 != "total" {print $1, $2}' | sort -nr
```

No full test suite was run. The working tree already had active P1 edits before
this audit, so recommendations below intentionally avoid source changes until
that work stabilizes.

## Executive Conclusion

There are 26 production/source files and 16 test files over 1000 lines. The
line count is a design warning, not a standalone failure. Some files are large
because they are coherent compatibility facades, characterization suites, or
problem-owned fixture-like fact maps. Others are large because they mix stable
v3 boundaries that should be independently testable: tainted proposal
visibility, prompt/source manifests, Decision/lifecycle side effects,
screening/runtime evidence visibility, Protocol execution, and CVRP provider
facts.

Do not start a broad split campaign while the current P1 fixes are still
moving. Recommended order is:

1. Finish and commit/stabilize current P1 boundary/accounting/repair changes.
2. Add characterization tests around the exact behavior of the highest-risk
   long files before moving code.
3. Split one responsibility boundary at a time with compatibility facades.
4. Re-run focused tests after each slice; reserve full regressions for
   integration milestones.

The highest priorities are not the longest files alone. They are the files where
length intersects with v3 boundary risk:

- P1: `proposal/prompt_manifest.py`, `core/evidence_recording/summary.py`,
  `protocol/experiment/stages.py`, `core/decision_lifecycle_actions.py`,
  `core/decision_finalizer.py`, `core/explore_step/pipeline.py`,
  `core/screening_visibility.py`, and the already-identified
  `agentic_session_hypothesis.py` / `prompt_common.py` pair.
- P1/P2: `proposal/agentic_grounding.py`,
  `proposal/agentic_session_patch_flow.py`, and `proposal/agentic_session_planner_loop.py`.
- P2: CVRP problem-owned provider modules should be split inside
  `problems/cvrp`, not moved into generic core.

## Split Criteria

Split when at least one of these is true:

- responsibilities are mixed across stable architectural boundaries;
- multiple workers are likely to edit the same file frequently;
- behavior boundaries are unclear enough to make reviews risky;
- tests are hard to navigate or require unrelated fixtures;
- a v3 boundary is at risk: Decision reads tainted proposal text, raw
  validation/holdout data becomes visible to proposal context, CVRP/VRP facts
  leak into generic core, or Scheduler starts acting as a Decision layer.

Keep for now when:

- the file has one clear responsibility and a stable public surface;
- the file is low churn or mostly compatibility/format glue;
- the size comes from fixture/golden-like cases;
- splitting would obscure a single behavior matrix more than it would help.

## Production / Source Inventory

| Lines | File | Category | Priority | Short read |
|---:|---|---|---|---|
| 3049 | `scion/scion/proposal/agentic_session_hypothesis.py` | `split_candidate` | P1 | Existing single-file conclusion applies; >3000 lines means assigned migration needed. |
| 2181 | `scion/scion/proposal/engine/prompt_common.py` | `split_candidate` | P1 | Existing single-file conclusion applies; tainted prompt projection surface. |
| 2162 | `scion/scion/proposal/context/cross_branch_research.py` | `review_needed` | P2 | Existing single-file conclusion applies; keep tainted proposal memory separate from Decision. |
| 2108 | `scion/scion/proposal/prompt_manifest.py` | `split_candidate` | P1 | Prompt visibility ledger, source digests, projections, and prompt accounting are mixed. |
| 1990 | `scion/scion/core/evidence_recording/summary.py` | `split_candidate` | P1 | Campaign summary, step rendering, visibility audit, branch cards, cache stats. |
| 1973 | `scion/scion/core/scheduler.py` | `review_needed` | P1 | Existing conclusion applies; must stay resource/slot scheduler, not Decision layer. |
| 1575 | `scion/scion/proposal/edit_protocol/normalization.py` | `review_needed` | P2 | Cohesive edit normalization, but large enough to split source discovery vs exact-replace composition. |
| 1564 | `scion/scion/proposal/agentic_session_tools.py` | `review_needed` | P2 | Many small tool/session helpers; split by tool families if churn continues. |
| 1452 | `scion/scion/core/explore_step/pipeline.py` | `split_candidate` | P1 | Single large explore pipeline class coordinates proposal, contract, verification, evidence. |
| 1388 | `scion/scion/core/screening_visibility.py` | `split_candidate` | P1 | Runtime/observability visibility helpers guard non-Decision evidence exposure. |
| 1379 | `scion/scion/proposal/agentic_grounding.py` | `split_candidate` | P1/P2 | Solver-design grounding, required reads, target inference, and pre-hypothesis checks are combined. |
| 1333 | `scion/scion/proposal/agentic_session_patch_flow.py` | `split_candidate` | P1/P2 | Code generation, patch validation, preview repair, finalization, telemetry identity checks. |
| 1309 | `scion/scion/core/branch_cards.py` | `review_needed` | P2 | Branch cards plus branch hygiene guidance and formatting helpers. |
| 1225 | `scion/scion/problems/cvrp/solver_design_provider.py` | `split_candidate` | P2 | Problem-owned prompt/smoke/quality guidance; split within CVRP provider package. |
| 1220 | `scion/scion/runtime/telemetry_guard/summary.py` | `split_candidate` | P2 | Telemetry summary plus mechanism diagnostics and repair guidance. |
| 1142 | `scion/scion/core/decision_finalizer.py` | `split_candidate` | P1 | Applies deterministic Decision side effects; promotion/continue/archive paths need crisp boundaries. |
| 1131 | `scion/scion/proposal/tools/previews/schema.py` | `review_needed` | P2 | Schema/contract preview guidance is broad but still proposal-tainted. |
| 1094 | `scion/scion/problems/cvrp/active_solver_map_provider.py` | `generated_or_fixture_like` | P3 | Problem-owned active solver fact map; static/fact-map weight explains size. |
| 1069 | `scion/scion/core/campaign.py` | `review_needed` | P2 | Composition/facade hub after earlier decomposition; not current top split risk. |
| 1059 | `scion/scion/protocol/experiment/stages.py` | `split_candidate` | P1 | `run_experiment` is ~950 lines and owns protocol stage execution/raw metrics handling. |
| 1054 | `scion/scion/proposal/engine/code_prompts.py` | `review_needed` | P2 | Code prompt rendering, failure context, telemetry/edit guidance. |
| 1053 | `scion/scion/core/evidence_recording/accounting.py` | `review_needed` | P1/P2 | Proposal/effective-round accounting and reconciliation. Characterize before split. |
| 1047 | `scion/scion/core/decision_lifecycle_actions.py` | `split_candidate` | P1 | Lifecycle actions can alter branch fate; keep explicit Decision boundary. |
| 1043 | `scion/scion/proposal/agentic_session_planner_loop.py` | `split_candidate` | P2 | Tool-selection/planner loop class; relates to context/tooling cost. |
| 1012 | `scion/scion/proposal/agentic_artifacts.py` | `keep_for_now` | P3 | Artifact store/validation/resume is cohesive and just over threshold. |

### Production Detail

#### `proposal/agentic_session_hypothesis.py`

Responsibility: agentic hypothesis phase orchestration, target intent, schema
retry, preview feedback, grounding, and output persistence.

Why long: it accumulated phase control plus error/retry behavior after
`agentic_session` was split into mixins. A prior single-file audit already
identified it as a stop-the-line-scale module.

Optimization: worth doing, but after current P1 work stabilizes. Split by
phase: target intent/preflight, hypothesis generation/retry, preview parity
feedback, output/artifact persistence. Priority P1.

v3 risk: proposal text is tainted and must not become Decision input. Keep all
retry and feedback artifacts explicitly proposal-local.

#### `proposal/engine/prompt_common.py`

Responsibility: common prompt rendering, observation projection, compaction,
receipt/fact projection, and prompt helper utilities.

Why long: every prompt phase reused it as the shared dumping ground for active
facts, receipts, raw observations, preview feedback, and rendering helpers.

Optimization: worth doing. Split active-facts projection, observation
projection, receipt/source projection, preview feedback, and generic rendering.
Priority P1.

v3 risk: active facts and raw observations are tainted context; prompt helpers
must not blur exposure control or DecisionFeatures filtering.

#### `proposal/context/cross_branch_research.py`

Responsibility: proposal-facing cross-branch research map, portfolio guidance,
opportunity gaps, novelty pressure, and mechanism descriptors.

Why long: it aggregates many ways of turning historical branch evidence into
compact proposal guidance.

Optimization: review before splitting. It is proposal-layer and tainted, so the
primary design requirement is not line count but keeping it out of deterministic
Decision. Split only if churn continues, likely into research-map extraction,
portfolio/opportunity guidance, and novelty-pressure rendering. Priority P2.

v3 risk: cross-branch memory must remain proposal guidance and never substitute
for Protocol/Decision evidence.

#### `proposal/prompt_manifest.py`

Responsibility: build API-visible prompt manifests, source visibility ledgers,
tool-result visibility ledgers, content projections, prompt section accounting,
digests, provenance, and cacheability summaries.

Why long: it combines audit representation with source parsing/projection and
rendered prompt detection. It is also growing with every new visibility rule.

Optimization: high value. Split into `manifest_builder`, `visibility_ledger`,
`source_visibility`, `observation_visibility`, `content_projection`, and
`prompt_accounting` modules while preserving the public builder function.
Priority P1.

v3 risk: this is the audit surface proving that raw/frozen/holdout data was or
was not visible. It needs characterization tests before code movement.

#### `core/evidence_recording/summary.py`

Responsibility: campaign summary writing, step summary rendering, visibility
audit embedding, branch history cards, runtime diagnostics, and LLM cache stats.

Why long: evidence summary is the shared sink for accounting, observability,
branch state, raw metric refs, telemetry feedback, and cache reporting.

Optimization: high value. Split summary assembly, step rendering, visibility
audit, branch history cards, runtime diagnostics, and cache accounting.
Priority P1.

v3 risk: summary may expose raw metrics references and visibility audit records.
Keep raw artifacts marked internal/public-ref scoped and do not feed them back
into proposal or Decision outside the allowed projections.

#### `core/scheduler.py`

Responsibility: active slot selection/reconciliation, clean fork selection,
branch slot reclamation, plateau/runtime-pressure handling, and scheduling
metadata.

Why long: scheduler accumulated branch lifecycle metadata and evidence-aware
slot pressure rules.

Optimization: review needed, not a rushed split. Existing single-file audit
applies. Candidate modules: active-slot inventory, slot reclamation, clean-fork
audit, same-branch refinement sampling, and formatting/metadata helpers.
Priority P1 because of boundary sensitivity, not because Scheduler should
decide scientific outcomes.

v3 risk: Scheduler must not become Decision. It may allocate resources using
structured branch metadata and Decision-origin lifecycle markers, but promotion,
abandonment, and protocol-stage judgments must remain in Decision/Finalizer.

#### `proposal/edit_protocol/normalization.py`

Responsibility: normalize typed patch edits, compose same-file edits, enforce
exact-replace granularity, source digest checks, source discovery, and fallback
branch workspace reads.

Why long: source provenance, edit validation, exact replacement, and legacy
compatibility all sit in one cohesive normalization path.

Optimization: not urgent. Split if active churn continues: source manifest
extraction, exact-replace application, composition/sequence validation, and
error payload rendering. Priority P2.

v3 risk: low Decision risk. Main concern is keeping edit-source provenance
truthful so code proposals cannot modify unseen/stale source.

#### `proposal/agentic_session_tools.py`

Responsibility: agentic session tool support and tool-observation plumbing.

Why long: many small helpers are grouped around session tool execution,
observation normalization, frozen/holdout-safe projections, and prompt context.

Optimization: review rather than immediate split. Split by tool families or
observation payload handling only after the tool-selection ledger work clarifies
churn hotspots. Priority P2.

v3 risk: tool observations are tainted. Keep the taint marker and bounded
projection policy explicit.

#### `core/explore_step/pipeline.py`

Responsibility: explore step orchestration around hypothesis/code proposal,
material-difference requirements, contract/verification, and result routing.

Why long: a single `ExploreStepPipeline` class spans the entire creative-to-gate
transition.

Optimization: worth doing after characterization. Split material-difference
policy, proposal request/build, gate execution, failure routing, and step
result assembly. Priority P1.

v3 risk: this is the junction between tainted Proposal and deterministic gates.
Do not let proposal self-reports or preview diagnostics bypass Contract,
Verification, or Protocol.

#### `core/screening_visibility.py`

Responsibility: summarize runtime evidence, observability value, candidate
intent, mechanism evidence, opportunity diagnostics, and visibility policy for
screening/protocol outputs.

Why long: it centralizes many "visible but not Decision input" helper families.

Optimization: worth doing carefully. Split runtime evidence visibility,
observability-value visibility, candidate-intent extraction, mechanism evidence,
and opportunity diagnostics. Priority P1.

v3 risk: comments already state these summaries must not be copied into
DecisionFeatures. Preserve that invariant with tests.

#### `proposal/agentic_grounding.py`

Responsibility: required solver-design grounding tools, target-file inference,
pre-hypothesis reads, missing-grounding errors, and active solver map follow-up.

Why long: target grounding now spans existing target discovery, forced targets,
branch-current source, observations, active solver map, and preflight read
requirements.

Optimization: split candidate. Separate required context preface, target-file
inference, grounding validation/error payloads, and active-map follow-up reads.
Priority P1/P2.

v3 risk: grounding controls what source and active facts the tainted proposal
agent can see. It should remain a proposal exposure-control boundary, not a
Decision rule.

#### `proposal/agentic_session_patch_flow.py`

Responsibility: code generation, patch validation, contract/algorithm preview
repair loop, repeated failure handling, telemetry identity checks, and final
patch output.

Why long: patch flow accumulated code-phase orchestration and several repair
subsystems after session modularization.

Optimization: split candidate. Split initial code build, patch validation,
preview/repair loop, repeated-contract reroute, telemetry identity helpers, and
finalization. Priority P1/P2.

v3 risk: preview/smoke results are tainted diagnostics. They can repair or block
proposal output, but cannot replace formal gates.

#### `core/branch_cards.py`

Responsibility: branch prompt cards, branch hygiene context/guidance, evidence
code extraction, and compact formatting.

Why long: card rendering and hygiene guidance share many helper extractors.

Optimization: review needed. Split card extraction/rendering from hygiene and
guidance text only if workers keep editing both. Priority P2.

v3 risk: these are proposal-context projections. Keep tainted evidence summaries
out of Decision.

#### `problems/cvrp/solver_design_provider.py`

Responsibility: CVRP-owned solver-design prompt/smoke guidance, quality checks,
runtime smoke repair guidance, smoke comparison, and representative case
selection.

Why long: one provider class owns multiple CVRP facts and guidance services.

Optimization: split inside the CVRP package. Candidate modules: prompt guidance,
candidate-quality checks, runtime smoke guidance, smoke comparison, and smoke
case selection. Priority P2.

v3 risk: this is the correct ownership location for CVRP/VRP facts. Do not move
its ALNS/VNS/route/capacity semantics into generic core.

#### `runtime/telemetry_guard/summary.py`

Responsibility: build telemetry guard summaries, mechanism diagnostics,
mechanism repair guidance, and field coverage details.

Why long: summary generation and repair guidance are in one file.

Optimization: split into summary assembly, field coverage, mechanism
diagnostics, and repair-guidance rendering. Priority P2.

v3 risk: telemetry guard evidence may guide proposal repair, but it should not
become a Decision shortcut outside structured Protocol/Decision inputs.

#### `core/decision_finalizer.py`

Responsibility: apply deterministic decisions, continue/park/archive/abandon
side effects, promotion preparation/commit, lineage recording, and terminal
branch evidence sync.

Why long: Decision side effects and branch/evidence synchronization share one
class plus helper cluster.

Optimization: high value after current P1 decision-lifecycle work stabilizes.
Split promotion finalization, continue/park/archive side effects, terminal
evidence sync, and lineage recording behind a stable finalizer facade.
Priority P1.

v3 risk: finalizer must not reconstruct scientific decisions from legacy free
text or proposal artifacts. It should apply explicit `DecisionResult` /
structured lifecycle actions.

#### `proposal/tools/previews/schema.py`

Responsibility: hypothesis/patch schema preview tools and preview guidance for
branch continuation, semantic signatures, telemetry contracts, and failure
payloads.

Why long: several preview families share schema-preview infrastructure.

Optimization: review needed. Split hypothesis schema preview, patch schema
preview, telemetry contract preview, and semantic signature guidance if this
area keeps changing. Priority P2.

v3 risk: previews are proposal-tainted diagnostics, not formal gates.

#### `problems/cvrp/active_solver_map_provider.py`

Responsibility: CVRP-owned active solver map/fact provider, including operator
registry slices and algorithm fact summaries.

Why long: much of the size is fact-map/static registry-like material plus
problem-owned extraction code.

Optimization: keep for now unless churn grows. If split, keep it under
`problems/cvrp`: fact extraction, registry slices, and provider class.
Priority P3.

v3 risk: low as long as it remains problem-owned and exposes digest/provenance
to proposal/gates consistently.

#### `core/campaign.py`

Responsibility: campaign composition/facade, service wiring, compatibility
surface, and branch state synchronization helpers.

Why long: historic campaign manager was reduced, but the remaining composition
root still wires many services.

Optimization: review needed, not first. Split only around composition factory or
compatibility wrappers after current P1 work is committed. Priority P2.

v3 risk: low-to-medium. Keep generic campaign orchestration in core; do not add
CVRP semantics here.

#### `protocol/experiment/stages.py`

Responsibility: protocol stage execution, canary/screening/validation/frozen
looping, case/seed progress, raw metrics capture, and stage output assembly.

Why long: `run_experiment` is nearly the whole file.

Optimization: high value. Split stage loop, case/seed runner, raw metrics
capture, progress/evidence emission, and aggregate result assembly.
Priority P1.

v3 risk: Protocol writes aggregate evidence and raw metrics, but Decision should
read only allowed structured features. Proposal agents must not see raw
validation/frozen records.

#### `proposal/engine/code_prompts.py`

Responsibility: code prompt construction, context splitting, source visibility
sections, prior failure prompt, telemetry identity rules, and edit guidance.

Why long: code prompts carry source, patch protocol, telemetry, and repair
guidance in one renderer.

Optimization: review needed after `prompt_common.py` split. Candidate modules:
source sections, telemetry identity guidance, prior failure/repair sections,
and generic code constraints. Priority P2.

v3 risk: prompt text is tainted; keep telemetry identity rules as proposal
guidance plus deterministic Contract/preview checks.

#### `core/evidence_recording/accounting.py`

Responsibility: proposal attempt accounting, reconciliation fields, quality
block ledgers, effective/formal screening counts, LLM request counts, and trace
index artifact.

Why long: all run-accounting reconciliation families live together.

Optimization: review after current accounting P1 stabilizes. Split proposal
accounting, reconciliation, quality-block ledger, candidate/effective-round
counts, and LLM trace index. Priority P1/P2.

v3 risk: accounting fields are audit/control metadata. Do not let tainted
proposal text alter effective round counts or formal Decision features.

#### `core/decision_lifecycle_actions.py`

Responsibility: update branch lifecycle signal state, screening evidence
summary, plateau/runtime observations, activation zero-effect summaries, and
park-lineage metadata.

Why long: lifecycle action metadata and screening evidence summary evolved
together.

Optimization: high value. Split lifecycle state updates, screening evidence
summary, runtime/plateau gate observations, activation/no-effect summaries, and
park-lineage metadata. Priority P1.

v3 risk: lifecycle actions change branch fate. They must be explicit,
deterministic, and auditable as Decision/lifecycle output, not scheduler or
proposal side effects.

#### `proposal/agentic_session_planner_loop.py`

Responsibility: agentic tool-selection planner loop and stop/fallback/session
state control.

Why long: one mixin owns the whole planner-loop state machine.

Optimization: split candidate after tool-selection ledger instrumentation.
Candidate modules: default deterministic prefetch, LLM planner loop, stop
decision handling, observation dedupe, and fallback previews. Priority P2.

v3 risk: planner chooses tainted context only. It must not hide or rewrite
Decision/Protocol evidence.

#### `proposal/agentic_artifacts.py`

Responsibility: agentic session artifact persistence, validation, and resume.

Why long: store implementation, validation, and resume compatibility live
together.

Optimization: keep for now. It is cohesive and just over 1000 lines. Split
store implementation from validation/resume only if artifact format churn
continues. Priority P3.

v3 risk: artifact validation should preserve tainted/provenance markers.

## Test Inventory

| Lines | File | Category | Behavior-area split? | Read |
|---:|---|---|---|---|
| 2741 | `scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py` | `test_fixture_split_candidate` | Yes | Summary/status/accounting/branch-card cases are mixed. |
| 2406 | `scion/scion/tests/unit/test_agentic_target_file_grounding.py` | `test_fixture_split_candidate` | Yes | Large target-grounding scenario suite; split by preflight, retry, manifest, code prompt. |
| 1622 | `scion/scion/tests/unit/test_code_edit_protocol.py` | `review_needed` | Optional | Cohesive edit-protocol characterization; split only by edit family if churn grows. |
| 1575 | `scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py` | `test_fixture_split_candidate` | Yes | Smoke provider/runtime/evidence/compaction cases are separable. |
| 1425 | `scion/scion/tests/unit/test_agentic_session_preview_repair.py` | `test_fixture_split_candidate` | Yes | Preview taxonomy, telemetry repair, persistence, prompt manifest cases mixed. |
| 1422 | `scion/scion/tests/unit/test_research_surfaces_generic_context.py` | `test_fixture_split_candidate` | Yes | Generic context exposure, forced surfaces, raw validation/frozen protection. |
| 1421 | `scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py` | `review_needed` | Yes, later | Campaign-loop accounting scenarios; split after accounting P1 stabilizes. |
| 1283 | `scion/scion/tests/unit/test_agentic_session_hypothesis_preview_retry.py` | `test_fixture_split_candidate` | Yes | Hypothesis preview retry, C11, material difference, artifact serialization. |
| 1219 | `scion/scion/tests/unit/test_cvrp_mechanism_novelty_provider_local_random.py` | `generated_or_fixture_like` | Optional | Fixture-matrix-like CVRP novelty text cases; keep unless unreadable. |
| 1200 | `scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py` | `test_fixture_split_candidate` | Yes | Evaluation telemetry and branch-local diagnostic behaviors can split. |
| 1067 | `scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py` | `test_fixture_split_candidate` | Yes | Prompt payload, smoke compaction, retry guidance, telemetry identity cases. |
| 1064 | `scion/scion/tests/test_llm_client.py` | `keep_for_now` | Optional | LLM client/mock/retry tests; low architecture risk. |
| 1058 | `scion/scion/tests/unit/test_agentic_session_model_planner.py` | `test_fixture_split_candidate` | Yes | Planner status, target owner reads, active fact anchor, registry guidance. |
| 1047 | `scion/scion/tests/unit/test_agentic_session_tool_selection.py` | `review_needed` | Optional | Tool-selection cache/read-budget behavior is cohesive but over threshold. |
| 1034 | `scion/scion/tests/unit/test_cvrp_mechanism_novelty_provider_destroy_repair.py` | `generated_or_fixture_like` | Optional | CVRP novelty variant matrix; keep unless provider split needs matching tests. |
| 1003 | `scion/scion/tests/unit/test_agentic_session_core_flow.py` | `keep_for_now` | No immediate need | Just over threshold; core-flow scenarios remain readable. |

### Test-Side Guidance

Do not split test files only because they are long. The right question is
whether a reviewer must page through unrelated behavior areas or fragile shared
fixtures to understand a failure.

Recommended test split priorities:

1. P1 with production boundary work:
   `test_research_surfaces_generic_context.py`,
   `test_evidence_recorder_summary_status.py`,
   `test_retry_round_accounting_campaign_loop.py`.
2. P2 with agentic session/prompt/tooling work:
   `test_agentic_target_file_grounding.py`,
   `test_agentic_session_preview_repair.py`,
   `test_agentic_session_hypothesis_preview_retry.py`,
   `test_agentic_session_model_planner.py`,
   `test_agentic_solver_design_prompt_payloads.py`.
3. P3/optional:
   CVRP novelty provider matrix tests and `test_llm_client.py`; these are
   closer to fixture/golden-like behavior matrices and are acceptable if they
   remain easy to scan.

## v3 Boundary Risk Register

| Risk | Current long-file hotspots | Audit read |
|---|---|---|
| Decision boundary: Decision reads only structured deterministic features | `decision_finalizer.py`, `decision_lifecycle_actions.py`, `screening_visibility.py`, `scheduler.py`, `experiment/stages.py` | Highest priority. Keep lifecycle actions explicit and do not infer decisions from proposal/free text. |
| Tainted proposal visibility | `prompt_manifest.py`, `prompt_common.py`, `agentic_grounding.py`, `agentic_session_*`, `cross_branch_research.py`, `branch_cards.py` | Proposal text/tool observations may guide proposals, not promotions. Visibility ledgers need characterization tests. |
| Raw validation/frozen/holdout leakage into proposal context | `prompt_manifest.py`, `evidence_recording/summary.py`, `screening_visibility.py`, context/prompt tests | Keep raw metrics refs internal or public-ref scoped; proposal context gets bounded aggregates only. |
| CVRP/VRP generic-core leakage | `solver_design_provider.py`, `active_solver_map_provider.py`, CVRP novelty tests | Current owner is mostly correct: CVRP facts are problem-owned. Do not move ALNS/VNS/route/capacity semantics to generic core. |
| Scheduler becoming Decision layer | `scheduler.py`, `branch_cards.py`, `decision_lifecycle_actions.py` | Scheduler may allocate slots and clean forks; Decision/finalizer owns scientific branch fate. |
| Protocol evidence used outside gate contract | `protocol/experiment/stages.py`, `screening_visibility.py`, `evidence_recording/summary.py` | Split Protocol handling only with tests proving raw vs aggregate evidence boundaries. |

## Recommended Governance Sequence

1. Stabilize current P1 worker changes. The dirty working tree already touches
   Decision, evidence recording, proposal pipeline, prompt/agentic session, and
   tests. Avoid large-file movement until those patches are committed or parked.
2. For each P1 split candidate, first write characterization tests around the
   public behavior and v3 exposure invariant.
3. Start with pure extraction modules and compatibility facades. Avoid changing
   behavior and moving responsibility in the same patch.
4. Prefer one owner per boundary-sensitive module during migration:
   Decision/finalizer, Protocol stages, prompt manifest/visibility, and
   agentic session patch flow should not be edited by multiple workers at once.
5. Keep CVRP provider splits inside `scion/scion/problems/cvrp/`.
6. After each small migration, run focused tests for that module family. Do not
   run broad validation campaigns until core architecture debt and current P1
   boundary fixes are stable.

