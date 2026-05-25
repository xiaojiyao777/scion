# Prioritized Fix Plan

This plan is ordered by risk to v3 correctness and unattended-run safety.

## 1. Move CVRP active package rules out of generic layers

- Severity: P1 high, prerequisite for 8+ and future problem classes.
- Evidence: generic `ContractGate._is_solver_design_patch_path`, generic C9 security, and APS grounding/ledger helpers know CVRP package paths or default to `solver_design`.
- V3 reason: problem packages own domain semantics and active object layout; core owns governance and asks providers for declared facts.
- Suggested fix:
  - Add provider hooks for active algorithm package paths, entrypoints, support globs, and forbidden entrypoint calls.
  - Move `policies/baseline_algorithm.py`, `policies/baseline_modules/*.py`, and old `policies/solver_algorithm.py` compatibility into CVRP provider/contract checks.
  - Keep generic helpers parameterized by selected surface/subject id.
- Suggested tests:
  - broaden generic boundary sentinel to catch active package paths;
  - CVRP provider tests retain current rejection behavior;
  - dummy non-CVRP problem uses different active package paths without generic code edits.

## 2. Enforce typed-edit strictness independent of source projection

- Severity: P1 high.
- Evidence: no-context `_parse_patch` still accepts full-file existing modifies for compatibility.
- V3 reason: model-facing existing-file changes should be small typed edits with source digest; full-file output was the failure mode that caused prior C6/C8/C9/C11 churn.
- Suggested fix:
  - reject `action=modify` with `full_file`, `content_after`, or legacy `code_content` when the path is known editable/existing but no source is available;
  - require an explicit host-internal compatibility flag for old callers;
  - keep canonical `PatchProposal.code_content` after parsing.
- Suggested tests:
  - direct parse rejects no-source full-file modify;
  - APS integration source missing for primary or additional modify fails before Contract;
  - creates/deletes still allow full-file content.

## 3. Make active solver map a first-class parity source

- Severity: P1 high.
- Evidence: `ActiveSolverMap` and tools exist, but semantic novelty extraction still only reads `context.read_active_solver_design`; ledger normalization defaults to `solver_design`.
- V3 reason: gates must not be better informed than the agent, and the active map is the current bounded context design.
- Suggested fix:
  - let novelty/premise providers consume active map facts/digests;
  - include active map packet digest/provenance in gate rejection payloads;
  - remove hard default `solver_design` from generic digest/reuse matching.
- Suggested tests:
  - active-map-only fact packet parity;
  - non-`solver_design` surface reuse;
  - stale active map digest forces reread or retry.

## 4. Resolve proposal attempt cap documentation/code mismatch

- Severity: P1 medium.
- Evidence: current-state says default proposal attempts include repair headroom; current `campaign_loop._proposal_attempt_limit` defaults to `requested_rounds` unless configured.
- V3 reason: proposal attempts and screened rounds must be explicit and predictable before long unattended runs.
- Suggested fix:
  - decide whether default should equal rounds or include repair headroom;
  - align current-state docs, CLI help, env behavior, and tests.
- Suggested tests:
  - `--rounds 3` default attempt cap expected value;
  - configured `SCION_PROPOSAL_ATTEMPT_LIMIT` override;
  - quality blocks do not count as effective screened rounds.

## 5. Split active 1000+ line modules

- Severity: P1 high.
- Evidence: six production modules remain above 1000 lines, with several more above 800.
- V3 reason: boundary logic is now too important to live in broad files where unrelated changes can hide policy regressions.
- Suggested fix:
  - split `agentic_session_hypothesis.py` into planning, gate parity, retry feedback, and output persistence;
  - split `prompt_common.py` into active facts, observation projection, receipt projection, preview feedback projection, and generic rendering;
  - split `agentic_session_tools.py` and `agentic_grounding.py` into surface-agnostic tool dispatch versus solver-design provider glue;
  - split CVRP active map provider into entrypoints/registries/slices/telemetry/facts;
  - split typed edit normalization once strictness is closed.
- Suggested tests:
  - import/facade tests for existing public module names;
  - focused behavior tests per extracted responsibility.

## 6. Add long-run readiness gate

- Severity: P1 medium.
- Evidence: current readiness is inferred from docs and unit tests, not a single executable readiness signal.
- V3 reason: unattended runs need a clear preflight that checks architecture invariants before spending LLM budget.
- Suggested fix:
  - add a documented preflight script or test marker that runs boundary sentinel, typed edit strictness tests, active-map parity tests, telemetry/lifecycle tests, and status heartbeat tests.
- Suggested tests:
  - preflight fails on a synthetic generic CVRP path leak;
  - preflight fails on model-facing full-file modify acceptance;
  - preflight passes on current clean state after fixes.

## 7. Validation sequence after fixes

- Severity: execution plan.
- Evidence: current-state says live validation is pending after recent repairs and long validation should wait.
- V3 reason: scale search only after framework behavior is stable.
- Suggested fix and tests:
  1. Run focused unit tests for changed areas.
  2. Run full unit regression.
  3. Run one 3-4 round live validation with explicit proposal attempt cap and status heartbeat review.
  4. Inspect artifacts: status, StepRecords, branch store, prompt manifests, observation ledger, typed edit raw traces, and telemetry decision details.
  5. Only then run 8+ unattended validation.

