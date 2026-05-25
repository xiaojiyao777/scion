# Observability, Tests, Modularity, And Long-Run Readiness

Audit question: are experiments observable, are P0/P1 risks covered, what large files remain, and is v0.4 ready for 8+ unattended rounds?

## Finding OTM-1: status heartbeat is materially improved

- Severity: OK.
- Evidence: `scion/scion/core/evidence_recording/status.py::record_protocol_progress` stage-scopes protocol fields, tracks `child_pid`, `child_exit_code`, `child_elapsed_ms`, `child_phase`, `case`, `seed`, and `selected_surface`, and clears stale child process fields on stage changes/completion. `scion/scion/runtime/subprocess_runner.py::run_solver` emits child start and completion progress. `scion/scion/protocol/experiment/stages.py` emits case/seed/pair progress and raw metrics refs.
- V3 judgment: conforms. The operator can see in-flight branch/protocol progress, child process status, case/seed, and completion state without reading raw traces.
- Suggested fix: keep status public-ref redaction and add a live interrupted-run smoke after P0 fixes.
- Suggested tests: unit coverage already exists for child pid clearing and status redaction; add an integration test for SIGTERM during APS/code/protocol producing indexed failed stubs and coherent status.

## Finding OTM-2: current progress includes useful tainted context

- Severity: OK/P2 caution.
- Evidence: campaign progress includes hypothesis/action/target/mechanism summaries, while status writer redacts public refs. This is observability, not Decision input.
- V3 judgment: acceptable if status is treated as operator/audit output. It would be risky only if status were reused as a deterministic decision source or exposed externally without redaction.
- Suggested fix: document status as tainted operational telemetry. If status is published externally, replace full hypothesis text with a bounded summary and artifact ref.
- Suggested tests: status payload redaction test for prompt refs, raw metrics refs, and long hypothesis text if external publishing is added.

## Finding OTM-3: P0/P1 test coverage is broad

- Severity: OK.
- Evidence: notable coverage includes:
  - typed edit: `test_code_edit_protocol.py`
  - v3 boundary sentinel: `test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py`
  - active solver map: `test_active_solver_map.py`, `test_cvrp_active_solver_map_provider.py`
  - APS ledgers/tools: `test_agentic_observation_ledger.py`, `test_agentic_session_tool_selection.py`
  - telemetry guard: `test_runtime_telemetry_guard.py`, `test_runtime_telemetry_guard_mechanism_diagnostics.py`
  - branch lifecycle: `core/test_branch_lifecycle_policy.py`, `core/test_evaluation_orchestrator_telemetry.py`, `core/test_decision_finalizer_lifecycle.py`
  - status: `core/test_evidence_recorder_summary_status.py`, `core/test_evidence_recorder_runtime_surface.py`, `protocol/test_protocol_correctness.py`
- V3 judgment: testing is no longer shallow. The main gaps are targeted regressions for current residual debt.
- Suggested fix: add the missing regressions listed in OTM-4 before long validation.
- Suggested tests: see OTM-4.

## Finding OTM-4: important regression gaps remain

- Severity: P1 high.
- Evidence: current tests do not fully cover active package path leakage in generic layers, active-map-only novelty parity, non-`solver_design` ledger reuse, no-source full-file modify rejection, or an end-to-end multi-cycle live validation after the 2026-05-24 repairs.
- V3 judgment: these are exactly the invariants needed before unattended operation.
- Suggested fix: add focused tests before broad live runs.
- Suggested tests:
  - boundary sentinel rejects `policies/baseline_algorithm.py`, `policies/baseline_modules`, and `policies/solver_algorithm.py` in generic layers.
  - novelty/premise provider rejection cites a digest visible through `read_active_solver_map`.
  - inherited ledger reuse works for a dummy non-`solver_design` surface.
  - model-facing `_parse_patch` rejects existing-file full-file modify without source.
  - simulated campaign has proposal block, telemetry repairable, weak-positive screening, and clean status/lineage.

## Finding OTM-5: production large-file debt remains above the onboarding bar

- Severity: P1 high.
- Evidence: current line-count scan found production files at or above 800 lines:

| Lines | File | Reason to split |
|---:|---|---|
| 1806 | `scion/scion/proposal/agentic_session_hypothesis.py` | hypothesis planning, retries, gates, parity feedback, and output handling are too broad |
| 1801 | `scion/scion/proposal/engine/prompt_common.py` | prompt projection, dedupe, compaction, active facts, receipts, and preview feedback are mixed |
| 1188 | `scion/scion/proposal/agentic_session_tools.py` | tool orchestration and surface/path policy still too broad |
| 1094 | `scion/scion/problems/cvrp/active_solver_map_provider.py` | provider is correctly problem-owned but should split registries, slices, telemetry, facts |
| 1029 | `scion/scion/proposal/agentic_grounding.py` | solver-design grounding, active map preface, and validation logic should be separated |
| 1007 | `scion/scion/proposal/agentic_session_patch_flow.py` | code repair, visibility, preview, and self-report handling mixed |
| 984 | `scion/scion/proposal/edit_protocol/normalization.py` | typed-edit parser/composer/source-map logic nearing P1 debt |
| 980 | `scion/scion/problems/cvrp/mechanism_novelty/local_search.py` | CVRP-specific local search novelty rules need focused submodules |
| 880 | `scion/scion/core/campaign.py` | campaign manager still broad despite mixins |
| 879 | `scion/scion/runtime/telemetry_guard/summary.py` | telemetry summary/classification should split by role/reporting |
| 872 | `scion/scion/proposal/prompt_manifest.py` | manifest hashing/rendered prompt accounting should split from rendering helpers |
| 862 | `scion/scion/proposal/agentic_artifacts.py` | session artifact persistence/indexing has multiple responsibilities |
| 857 | `scion/scion/proposal/tools/previews/schema.py` | schema preview and feedback rules should split |
| 850 | `scion/scion/problems/cvrp/solver_design_provider.py` | CVRP prompt/smoke/provider logic remains broad |
| 832 | `scion/scion/proposal/tools/previews/telemetry_static.py` | static telemetry analysis is complex enough for role-specific modules |
| 813 | `scion/scion/proposal/agentic_code_context.py` | code prompt context and integration source policy should split |
| 810 | `scion/scion/proposal/agentic_preview.py` | preview orchestration and feedback packaging should split |

- V3 judgment: violates onboarding's "above 1000 is active debt, above 800 needs a split plan" guidance.
- Suggested fix: split P1 files by ownership boundary and keep public facades stable.
- Suggested tests: after each split, run focused tests for that module plus import compatibility tests.

## Finding OTM-6: oversized tests also need ownership splits

- Severity: P1 medium.
- Evidence: current tests at or above 800 lines:

| Lines | File | Split reason |
|---:|---|---|
| 1104 | `test_cvrp_mechanism_novelty_provider_local_random.py` | multiple local-random premise/novelty cases |
| 1044 | `core/test_evaluation_orchestrator_telemetry.py` | telemetry orchestration scenarios should split by outcome class |
| 931 | `test_agentic_session_tool_selection.py` | tool selection, grounding, retry, and budget cases mixed |
| 876 | `core/test_evidence_recorder_summary_status.py` | status/summary/child process/redaction scenarios mixed |
| 866 | `test_agentic_session_hypothesis_preview_retry.py` | preview retry and hypothesis quality cases mixed |
| 810 | `test_agentic_solver_design_algorithm_smoke_feedback.py` | smoke feedback and telemetry diagnostics mixed |
| 807 | `core/test_proposal_pipeline_quality_blocks.py` | quality block accounting cases mixed |

- V3 judgment: test files are architecture. These are now harder to review than necessary.
- Suggested fix: split by behavior, not by arbitrary line range.
- Suggested tests: preserve fixture reuse through small helper modules and keep each split file focused on one invariant family.

## Finding OTM-7: current readiness for 8+ unattended validation is negative

- Severity: P0 blocker.
- Evidence: current-state still says not ready for long solver-quality validation; residual P1 boundary/edit/projection risks remain; large-file debt remains over the onboarding threshold; live validation after latest repairs is pending.
- V3 judgment: do not scale the search until framework boundary, typed edit strictness, and observability are provably stable.
- Suggested fix: finish the prioritized plan in `07-prioritized-fix-plan.md`.
- Suggested tests: after fixes, run focused tests, full unit regression, one 3-4 round live validation with artifact review, then one 8+ unattended run.

