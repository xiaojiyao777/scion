# 08 - Large File Modularization Audit 2026-05-19

## Scope And Threshold

This audit covers Scion production Python files and test Python files. Test files are part of the maintainability surface: they must not become unstructured "屎山" just because they do not ship in runtime packages.

Governance target:

- Preferred maximum: every source or test file should stay under 800 lines.
- Any file over 800 lines must have an explicit ownership reason, a documented split plan, and a bounded timeline.
- Files over 1000 lines are active architecture debt and should not receive major new behavior before a split plan is in motion.
- Files over 3000 lines are blocking debt for the owning area unless they are in an already assigned migration, such as Bacon's `agentic_session` split.

Detailed review in this document focuses on the current files over 1000 lines. The 800-1000 line watchlist is included at the end because those files are already above the new threshold.

## Production File Findings

| Priority | File | Lines | Ownership | Current Responsibility / Why It Grew | Split Plan |
| --- | ---: | ---: | --- | --- | --- |
| P0 | `scion/scion/problems/cvrp/solver.py` | 9151 | CVRP problem-specific | Public `solve`, CLI, registry operators, policy loading, policy normalization, baseline integration, main search, local neighborhoods, bounded destroy/repair, route-pool recombination, runtime audit, and `solver_algorithm` context are all in one module. Behavior fixes repeatedly landed here because it is the active runtime path. | Keep a thin compatibility `solver.py`; split into `solver/api.py`, `solver/cli.py`, `solver/policy_loading.py`, `solver/policy_schema.py`, `solver/main_search/{planning,runtime,telemetry}.py`, `solver/neighborhoods/{local,route_pair,bdr,route_pool}.py`, and `solver/algorithm_runtime.py`. |
| P0 | `scion/scion/problems/cvrp/adapter.py` | 3356 | CVRP problem-specific | Adapter API, surface prose, static policy preview, AST checks, synthetic preview context, solver-algorithm preview, and solution checks are coupled. It grew because problem boundary rules were added near the adapter entrypoint instead of into problem-owned submodules. | Keep `CvrpAdapter` as facade. Move prose to `surface_rendering.py`, constants/schema to `policy_schema.py`, solution validation to `solution_checks.py`, and preview logic to `preview/{dispatch,construction,baseline,solver_algorithm,main_search,deep_policies}.py`. |
| P0 / Bacon | `scion/scion/proposal/agentic_session.py` | 4931 | Scion framework | One class owns session orchestration, planner loops, code loops, tool calls, budgets, timeouts, preview repair, outputs, persistence, and artifact handling. | Bacon owns this split. Do not start a parallel split in this phase. Expected modules: `orchestration`, `planner_loop`, `code_tools`, `tool_call`, `budget_runtime`, `timeouts`, `outputs`, `repair`, `observations`, and `persistence`. |
| P1 | `scion/scion/proposal/context_manager.py` | 3863 | Scion framework with CVRP leakage | Hypothesis/code/fix context, surface metadata, history rendering, runtime feedback, strategy guidance, solver-design guidance, and code reads are combined. Some solver-design guidance hard-codes CVRP implementation details. | Split into `context/{builder,surfaces,history,runtime_feedback,strategy_guidance,solver_design_guidance,code_reads}.py`. Move CVRP-specific guidance into a CVRP problem provider. |
| P1 | `scion/scion/contract/gate.py` | 3553 | Scion framework | `ContractGate` owns C1-C12 schema, target, file, AST, import, sensitive API, non-RNG random, complexity, novelty, surface helpers, and result assembly. Each new rule has been appended to the same class. | Keep `ContractGate` as orchestrator; split checks into `contract/checks/{schema,target,surface_interface,security,randomness,complexity,novelty,telemetry}.py`. Move problem-specific scale vocabulary out of core. |
| P1 | `scion/scion/proposal/tools/preview.py` | 2675 | Scion framework | Draft, schema, target permission, interface, contract preview, algorithm smoke tool, and compact agent payload rendering live together. It also imports many smoke helpers directly. | Split `tools/preview/{draft,schema,target_permission,interface,contract,algorithm_smoke_payload}.py`. Keep existing imports through re-export until callers migrate. |
| P1 | `scion/scion/protocol/experiment.py` | 1985 | Scion framework | Split/seed managers, canary, main experiment loop, runtime audit observation, surface runtime aggregation, case feedback aggregation, and pattern summaries are combined. `run_experiment` alone is too large. | Split into `experiment_runner.py`, `canary.py`, `runtime_observation.py`, `surface_runtime_summary.py`, and `case_feedback.py`. |
| P1 | `scion/scion/core/proposal_pipeline.py` | 1540 | Scion core/framework | Proposal pipeline, agentic session adapter, failure routing, resume context, lineage, and session refs are combined. | Split `core/proposal_pipeline/{pipeline,agentic_adapter,failure_routing,resume,lineage}.py`; keep public `ProposalPipeline` import stable. |
| P1 | `scion/scion/proposal/solver_design_smoke.py` | 1468 | CVRP semantics in proposal layer | Runtime smoke uses CVRP case manifest assumptions, CVRP solver_algorithm telemetry, and CVRP object-model repair guidance. This is problem behavior in framework location. | Move to `problems/cvrp/smoke/solver_design.py`. Proposal tools should call a problem adapter/provider hook. |
| P1 | `scion/scion/proposal/engine.py` | 1465 | Scion framework with CVRP leakage | Creative layer and prompt splitting are mixed with hard-coded CVRP solver-design prompt guidance, ALNS/VNS terms, `_ALNSVNSSolver`, and `_Solution` details. | Split generic prompt builders from problem prompt providers. CVRP prompt details should come from adapter/surface metadata. |
| P1 | `scion/scion/contract/checks/solver_design_integration.py` | 1265 | CVRP semantics in contract layer | The check is named generically but hard-codes `_ALNSVNSSolver`, scheduler APIs, CVRP state bridge methods, and solver-design file paths. | Move to `problems/cvrp/contract_checks/solver_design_integration.py` and register through problem/adapter metadata. Framework contract code should only dispatch. |
| P2 | `scion/scion/proposal/tools/feedback.py` | 1483 | Scion framework with some CVRP prioritization | Memory, screening, holdout, runtime feedback, diagnosis, and surface-priority logic are combined. Some CVRP solver-design priority rules live here. | Split `tools/feedback/{memory,screening,holdout,runtime,diagnosis}.py`; move CVRP priority rules to problem provider. |
| P2 | `scion/scion/cli/main.py` | 1286 | Scion framework | `init`, `run`, inspect commands, reports, postmortem, and weight optimization all live in one CLI file. | Split `cli/{init,run,inspect,report,postmortem,optimize}.py`; retain top-level command registration. |
| P2 | `scion/scion/runtime/telemetry_guard.py` | 1226 | Scion framework | Telemetry schema normalization, declared probes, runtime path resolution, summary building, and formatting are combined. | Split `runtime/telemetry/{schema,summary,path_resolution,formatting}.py`. |
| P2 | `scion/scion/proposal/tools/surface.py` | 1172 | Scion framework | Surface listing, payload compaction, interface summaries, code reads, solver-design support artifact reads, and path safety live together. | Split `tools/surface/{read_tool,payloads,compact,code_reader,support_artifacts}.py`. |

## Test File Findings

Status update: the active test-side line-count blocker is closed as of the
2026-05-19 cleanup. Every file listed below has been split into focused test
modules with a shared support module where needed, and the largest remaining
test file is 728 lines. The table is kept as the audit baseline that drove the
split, not as an open task list.

| Priority | File | Lines | Ownership | Current Responsibility / Why It Grew | Split Plan |
| --- | ---: | ---: | --- | --- | --- |
| P0 | `scion/scion/tests/test_cvrp_solver_operator_runtime.py` | 4880 | CVRP tests | Registry operators, policy surfaces, baseline policy, algorithm blueprint, main search, route-pool recombination, BDR, deep policy activation, runtime audit, and safety tests are all appended to one file. | Split into `test_cvrp_solver_registry.py`, `test_cvrp_solver_policy_runtime.py`, `test_cvrp_solver_algorithm_runtime.py`, `test_cvrp_main_search.py`, `test_cvrp_route_pool.py`, `test_cvrp_destroy_repair.py`, and `test_cvrp_solver_safety.py`. |
| P0 / Bacon | `scion/scion/tests/unit/test_agentic_proposal_tools_session.py` | 4735 | Framework tests | Session planner, required reads, budget, fallback, repair, preview failures, artifacts, replay, and tool errors are all in one file. | Bacon should split with `agentic_session.py`. Do not start an independent move in this phase. |
| P1 | `scion/scion/tests/unit/test_agentic_proposal_tools_solver_design.py` | 1916 | Cross-layer/CVRP tests | Active solver tools, algorithm smoke, smoke case resolution, prompt compacting, and solver-design repair guidance are mixed. | Split active-solver tool tests, smoke runtime tests, prompt/compact tests, and safe-data-root tests. CVRP-specific smoke tests should follow the CVRP smoke module. |
| P1 | `scion/scion/tests/test_verification.py` | 1840 | Framework tests | V1/V2/V3/V4/V5/V6/V8 checks and VerificationGate integration tests are combined. | Split by verification check: syntax, interface, feasibility, objective, solution consistency, state leak, perf guard, and integration. |
| P1 | `scion/scion/tests/unit/core/test_proposal_pipeline.py` | 1553 | Core/framework tests | Hypothesis generation, code generation, agentic failure routing, resume artifacts, lineage, and fix flow are combined. | Split into hypothesis, code, agentic failure, resume, lineage, and fix files. |
| P1 | `scion/scion/tests/test_contract.py` | 1534 | Framework tests | C1-C12, sensitive APIs, complexity bounds, non-RNG random, and novelty tests are in one file. | Split by contract check group. C9, C9b, and C9c should each have their own file. |
| P1 | `scion/scion/tests/unit/test_research_surfaces_solver_design_integration.py` | 1396 | CVRP/Cross-layer tests | CVRP solver-design identity, helper reachability, scheduler integration, baseline API, and invented bridge checks are combined. | Move alongside CVRP contract check tests; split identity/reachability, scheduler API, baseline API, and state bridge tests. |
| P1 | `scion/scion/tests/test_cvrp_adapter.py` | 1191 | CVRP tests | Adapter rendering, safe API exposure, policy preview, solver_algorithm preview, solution checks, and verification integration are combined. | Split adapter rendering/API, policy preview, solver_algorithm preview, solution checks, and verification integration. |
| P1 | `scion/scion/tests/unit/test_agentic_proposal_tools_schema.py` | 1183 | Cross-layer tests | Generic schema/preview behavior is mixed with CVRP active-boundary and policy-preview tests. | Split generic schema/contract preview tests from CVRP active-boundary tests. |
| P2 | `scion/scion/tests/test_campaign.py` | 1436 | Framework tests | Campaign basics, continue-explore, success path, contract failure, stale path, verification path, promotion hook, retry, and summary tests are combined. | Split lifecycle, success/promotion, failure/retry, summary/reporting, and verification-path tests. |
| P2 | `scion/scion/tests/test_protocol.py` | 1246 | Framework tests | Evaluation math, gates, split/seed managers, experiment loop, runtime telemetry, and canary tests are combined. | Split evaluation, gates, split/seed, experiment runtime, and canary tests. |
| P2 | `scion/scion/tests/unit/test_agentic_proposal_tools_feedback.py` | 1244 | Cross-layer tests | Memory query, screening feedback, runtime diagnosis, holdout protection, and CVRP solver-design prioritization are combined. | Split generic feedback tools from CVRP diagnosis/priority tests. |
| P2 | `scion/scion/tests/unit/test_sprint_k.py` | 1216 | Framework regression tests | Multiple sprint K stories share one file because they were added as a sprint bundle. | Split by K story or owning component; keep shared helpers in a small fixture module. |
| P2 | `scion/scion/tests/test_sprint_e2.py` | 1049 | Cross-layer regression tests | Frozen set, screening rebalance, family taxonomy, history, strategy guidance, runtime feedback, and CVRP taxonomy are mixed. | Split taxonomy/family, history/coverage, strategy guidance, and runtime feedback. |
| P2 | `scion/scion/tests/test_sprint_e3.py` | 1032 | Framework regression tests | Observability, richer case feedback, champion baseline hints, stagnation, diagnosis, and postmortem CLI are combined. | Split by story: T06, T09, T10, T25, T23, and T24. |

Test governance rule: a large test file is not acceptable simply because the individual tests are short. If one file forces a reviewer to page through unrelated fixtures, scenarios, and sprint history, it has the same maintainability failure as a large production module.

## CVRP Problem-Specific Versus Scion Framework Boundary

Problem-specific CVRP behavior belongs under `scion/scion/problems/cvrp/` or behind explicit problem adapter/provider hooks. Scion framework/core may understand generic concepts such as research surfaces, declared telemetry fields, contract hooks, smoke hooks, and runtime observations. It should not hard-code CVRP route, capacity, demand, ALNS/VNS, `_ALNSVNSSolver`, or CVRP state-model details.

Current boundary leaks:

- `scion/scion/proposal/engine.py` embeds CVRP solver-design prompt rules: ALNS/VNS, route-pool, destroy/repair, `_ALNSVNSSolver`, `CvrpSolution`, `_Solution`, `_Route`, and CVRP distance/demand guidance. These should be adapter-provided prompt sections.
- `scion/scion/proposal/context_manager.py` includes solver-design API guidance that names CVRP construction helpers and `_ALNSVNSSolver` integration details. This should move to a CVRP problem provider.
- `scion/scion/proposal/solver_design_smoke.py` is mostly CVRP smoke behavior in a proposal package. It knows CVRP manifest schema, solver_algorithm counters, and CVRP object-model repair guidance. It should live under the CVRP problem package and be called through a generic smoke hook.
- `scion/scion/contract/checks/solver_design_integration.py` hard-codes CVRP scheduler, state bridge, and solver-design runtime rules in a generic contract namespace. It should be a registered CVRP contract check.
- `scion/scion/contract/gate.py` contains legacy problem-scale names such as route/vehicle terms for complexity checks. The framework should ask the problem spec/adapter for scale vocabulary instead.
- `scion/scion/protocol/experiment.py` has explicit `solver_algorithm_*` runtime counters. This is acceptable only as a declared surface telemetry convention; the next step should make these fields surface-schema driven rather than hard-coded in the generic experiment loop.

Boundary target:

- CVRP owns CVRP object model guidance, solver-design API details, ALNS/VNS terms, route/demand/capacity vocabulary, and CVRP smoke/preview implementations.
- Framework owns generic orchestration: surface selection, hook dispatch, telemetry validation by declared schema, contract result aggregation, and proposal/session control flow.
- Prompt text should be generated from the same problem-owned metadata that powers preview, contract hooks, smoke hooks, and runtime audit.

## Historical Governance Failure Review

The current 3k/5k/9k line files exist because the project repeatedly accepted behavior fixes without enforcing structural constraints.

Root causes:

- No hard line threshold existed. "Split this later" was not backed by a measurable stop condition, so modules kept growing after each successful bug fix.
- Behavior fixes outranked architecture. Runtime failures, smoke failures, and experiment pressure made it faster to patch the active monolith than to create a clean module boundary first.
- Helper extraction was treated as success even when the owner file stayed huge. Moving a few utility functions out did not reduce the primary responsibility count.
- Parallel work created conflict avoidance. Agentic session work accumulated because splitting it risked collisions, so new behavior continued to land in the large file.
- Test files were not governed. Regression cases were appended to existing test files because fixtures were nearby, creating several 1k-5k line test files.
- Problem/framework leakage was not blocked. CVRP solver-design semantics were copied into prompt builders, ContractGate checks, feedback tools, and smoke utilities because those were the places where failures surfaced.
- Experiment pressure hid structure debt. Running more validation rounds felt like progress even when the codebase shape made future failures more likely.

Governance correction:

- Every file over 800 lines must have an owner and split issue.
- Every file over 1000 lines needs an active split plan before new feature work lands in it.
- Every file over 3000 lines needs a stop-the-line exception or an assigned migration.
- Test splits must be tracked alongside production splits.
- A "helper extracted" patch is not sufficient unless the original file's responsibility count and line count actually fall.

## Bacon Post-Review Update

Disconnected work was not accepted as complete until rechecked against the audit criteria. The initial Bacon split reduced the production file but left two problems: the matching 4k-line session test file was untouched, and `agentic_session_common.py` used a dynamic `globals()` export that could become a new hidden dependency bucket.

Post-review repair status:

- `scion/scion/proposal/agentic_session.py` is now a 17-line compatibility facade.
- Session behavior is split into focused `agentic_session_*.py` phase modules. The largest is `agentic_session_planner_loop.py` at 649 lines; `agentic_session_tools.py` is 700 lines.
- `agentic_session_common.py` now has an explicit transitional export set instead of `globals()`; follow-up work should keep shrinking this shared dependency surface rather than adding new names casually.
- `scion/scion/tests/unit/test_agentic_proposal_tools_session.py` is now a 6-line placeholder pointing to focused tests.
- Session tests are split into nine `test_agentic_session_*.py` files plus `agentic_session_test_support.py`; the largest focused test file is 728 lines.
- Verification run: `python -m compileall -q scion/scion/proposal scion/scion/tests/unit`, `python -m pytest scion/scion/tests/unit/test_agentic_session_*.py scion/scion/tests/unit/test_agentic_proposal_tools_session.py -q` passed with 78 tests, and `git diff --check` passed.

This closes Bacon's P0 line-count blocker for APS session orchestration and tests. It does not close the broader architecture-debt freeze: `problems/cvrp/solver.py`, `tests/test_cvrp_solver_operator_runtime.py`, `problems/cvrp/adapter.py`, `proposal/context_manager.py`, and `contract/gate.py` remain large active-debt files and should be handled before more validation experiments normalize this structure.

## CVRP Solver Runtime Test Split Update

The first CVRP-side P0 cleanup is complete for the oversized solver runtime test file:

- `scion/scion/tests/test_cvrp_solver_operator_runtime.py` is now a 6-line compatibility placeholder.
- Shared fixtures/helpers moved to `scion/scion/tests/cvrp_solver_runtime_support.py`.
- Runtime tests are split by behavior area into focused `test_cvrp_*_runtime.py` files: registry, policy defaults, solver-design algorithm runtime, main-search runtime, main-search gating/phase/recovery, route-pool runtime/scope/phase, mechanism-policy runtime, policy-surface runtime, and operator-safety runtime.
- The largest resulting file is `test_cvrp_mechanism_policy_runtime.py` at 707 lines.
- Verification run: `python -m pytest scion/scion/tests/test_cvrp_*_runtime.py scion/scion/tests/test_cvrp_solver_operator_runtime.py -q` passed with 72 tests.

This closes the P0 line-count blocker for that test file only. The production runtime module `scion/scion/problems/cvrp/solver.py` remains the main CVRP P0 blocker and still needs behavior-preserving modularization.

## CVRP Solver Runtime Production Split Update

The first behavior-preserving production extraction is complete:

- Added `scion/scion/problems/cvrp/solver_runtime/` as the CVRP-owned runtime implementation package.
- Moved dynamic policy-module loading helpers into `solver_runtime/policy_modules.py`.
- Moved solution coercion, feasibility/objective helper calls, lexicographic comparison, and objective delta helpers into `solver_runtime/solution_ops.py`.
- Moved time-budget and exit-reserve helpers into `solver_runtime/timing.py`.
- `scion/scion/problems/cvrp/solver.py` remains the public executable/import facade and re-exports the old private helper names by importing them explicitly.
- Verification run: `python -m compileall -q scion/scion/problems/cvrp scion/scion/tests` and `python -m pytest scion/scion/tests/test_cvrp_*_runtime.py scion/scion/tests/test_cvrp_solver_operator_runtime.py -q` passed with 72 tests.

This is intentionally a small first slice. `solver.py` is still over 9000 lines and remains the main P0 production blocker. Next production slices should move policy loaders/schemas, then neighborhoods, then main-search runtime/telemetry, preserving facade compatibility after each step.

## Broad Test Modularization Update

The broad test-side cleanup requested after the CVRP runtime split is complete:

- Former aggregate placeholders now remain for `test_verification.py`, `test_contract.py`, `test_campaign.py`, `test_protocol.py`, `test_cli.py`, `test_decision.py`, `test_sprint_e2.py`, `test_sprint_e3.py`, `unit/core/test_proposal_pipeline.py`, `unit/core/test_campaign_control_boundaries.py`, `unit/core/test_evidence_recorder.py`, `unit/test_research_surfaces_solver_design_integration.py`, `unit/test_agentic_proposal_tools_schema.py`, `unit/test_agentic_proposal_tools_solver_design.py`, `unit/test_agentic_proposal_tools_feedback.py`, and `unit/test_sprint_k.py`.
- Each old aggregate now has a sibling `*_test_support.py` fixture/helper module and focused test modules named after the behavior area under test.
- `find scion/scion/tests -name '*.py' ...` now reports a largest test file of 728 lines, below the preferred 800-line threshold.
- Verification runs: focused split regression passed with 643 tests; CVRP runtime/adapter/agentic-tool split regression passed with 192 tests.

This closes the active test-side architecture blocker. New tests should be added to the focused owner file for the behavior being exercised, not to the placeholder aggregate.

## Recommended Execution Order

Phase 0: close APS session split and protect active work.

- Bacon's APS production/test split is now post-reviewed and behavior-verified.
- Do not add new APS behavior to `agentic_session.py` or the old aggregate test placeholder.
- Keep `agentic_session_common.py` transitional and explicit; shrink it when touching a phase module.

Phase 1: unblock CVRP P0 without touching Bacon's split.

- Split `problems/cvrp/solver.py` into behavior-preserving modules with a thin compatibility facade.
- The former `tests/test_cvrp_solver_operator_runtime.py` aggregate has been split. Keep new runtime tests focused and below the threshold while `solver.py` itself is modularized.
- Split `problems/cvrp/adapter.py` into adapter facade, surface rendering, solution checks, policy schema, and preview modules.
- The former `tests/test_cvrp_adapter.py` aggregate has been split to mirror adapter responsibilities.

Phase 2: move CVRP semantics out of framework.

- Move `proposal/solver_design_smoke.py` implementation to `problems/cvrp/smoke/solver_design.py`.
- Move `contract/checks/solver_design_integration.py` to a CVRP registered contract check.
- Replace CVRP prompt text in `proposal/engine.py` and `proposal/context_manager.py` with problem-provider prompt sections.

Phase 3: split framework P1 files.

- Split `contract/gate.py` check groups.
- Split `proposal/tools/preview.py`.
- Split `protocol/experiment.py`.
- Split `core/proposal_pipeline.py`.

Phase 4: P2 cleanup and threshold watchlist.

- Split `feedback.py`, `surface.py`, `telemetry_guard.py`, and CLI command modules.
- Split sprint-era regression test files by story/component.
- Bring 800-1000 line files below threshold before they cross 1000.

## Stop-Line Rules

Do not proceed to another 6-round validation experiment when any of these conditions are true:

- A core/framework file over 1000 lines is receiving new behavior without an active split plan.
- A production or test file over 3000 lines is not assigned to an active migration owner.
- A fix adds CVRP/ALNS/VNS/route/capacity/demand/`_ALNSVNSSolver` semantics to `core`, `proposal`, `contract`, `protocol`, or `runtime` instead of a CVRP problem provider.
- A framework/problem boundary rule exists only in prompt text or tests, not in an executable adapter/provider/contract/smoke hook.
- A test file grows beyond 800 lines without a split plan.
- A patch claims modularization but leaves the original large file with the same broad responsibilities.

Validation experiments are useful after the architecture boundary is enforceable. They should not be used to normalize a state where core files are oversized, problem semantics leak across layers, and tests are too large to review safely.

## 800-1000 Line Watchlist

Production files already above the new threshold but below 1000 lines:

- `scion/scion/core/evidence_recorder.py` - 952 lines.
- `scion/scion/core/explore_step_pipeline.py` - 947 lines.
- `scion/scion/proposal/llm_client.py` - 876 lines.

Test files already above the new threshold but below 1000 lines: none as of the
2026-05-19 split. The largest remaining test file is
`scion/scion/tests/unit/test_agentic_session_model_planner.py` at 728 lines.

These files should not receive broad new behavior until they have either a short written reason to remain above 800 lines or a concrete split plan.
