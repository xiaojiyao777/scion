# Scion v0.4 Full Audit Executive Summary

Date: 2026-05-25

Scope: full framework audit against v3 baseline, current v0.4 state, active solver map / APS repair notes, typed edit protocol reference, and current source/tests. This review did not inspect raw traces as primary evidence and did not modify production code.

## Verdict

Scion v0.4 has made material progress toward the v3 framework shape, especially in typed edit normalization, active solver map tooling, observation ledgers, telemetry diagnostics, branch-local repair, and status heartbeat. It is still not ready for an 8+ round unattended validation run. The blocker is not one broken gate; it is the combination of remaining generic-layer solver-design path coupling, one typed-edit compatibility escape hatch, active-map parity gaps, and active large-file debt in proposal/control modules.

The strongest positive result is that Decision remains mostly deterministic and feature-based: proposal text and tool observations are treated as tainted context, while `SafeFeatureExtractor` builds numeric/enum `DecisionFeatures`. The strongest negative result is that generic `contract` and `proposal` layers still know too much about the current CVRP active algorithm package paths.

## Top Findings

### F-001: 8+ unattended validation is not yet justified

- Severity: P0 blocker for long validation, not a claim that short diagnostic runs are unsafe.
- Evidence: `scion/docs/status/current-state.md` says v0.4 is not ready for long CVRP solver-quality validation and prioritizes P0 architecture debt cleanup. `scion/docs/AGENT_ONBOARDING.md` says not to run longer validation while architecture debt is the active blocker.
- V3 judgment: v3 says hard boundaries and observability come before scaling search depth. Current code is close enough for focused regressions and short controlled validation, but not enough for 8+ unattended rounds.
- Suggested fix: close F-002, F-003, F-004, split P0 large files, run focused unit subsets plus full regression, then run a 3-4 round live validation before 8+.
- Suggested tests: add a CI-style "long-run readiness" checklist artifact that verifies boundary sentinel, typed-edit strict mode, active-fact parity, status heartbeat, and screened-round accounting before long live runs.

### F-002: generic layers still hardcode the active CVRP solver-design package shape

- Severity: P1 high; becomes P0 before adding new problem classes or declaring Scion problem-generic.
- Evidence: `ContractGate._is_solver_design_patch_path` hardcodes `policies/baseline_algorithm.py`, `policies/solver_algorithm.py`, and `policies/baseline_modules/*.py`; `contract.checks.security._context_baseline_call_violations_in_baseline_algorithm` hardcodes the same entrypoint; APS grounding/ledger helpers default several tools to `surface="solver_design"`.
- V3 judgment: violates the v3/provider boundary. `solver_design` as a generic surface kind is acceptable; CVRP active package paths and wrapper rules should be problem/provider-owned.
- Suggested fix: move package path predicates, entrypoint wrapper restrictions, and support-module globs behind a problem/surface provider contract. Generic Contract should ask a provider whether a path is part of the active algorithm package.
- Suggested tests: extend the existing v3 boundary sentinel to catch `policies/baseline_algorithm.py`, `policies/baseline_modules`, `solver_algorithm`, and default `solver_design` assumptions in generic layers unless explicitly allowlisted as temporary debt.

### F-003: typed edit protocol is substantially landed, but strictness depends on source context

- Severity: P1 high.
- Evidence: `_parse_patch` sets `reject_legacy_code_content_full_file_modify=True`; `normalize_patch_typed_edits` rejects existing-file `full_file` when source is host-visible; `test_full_file_fallback_remains_compatible` still accepts `code_content`/`full_file` modify when no source context is supplied.
- V3 judgment: partially conforms. The live APS path is designed to provide source context, but the protocol invariant is not enforced independently of that projection.
- Suggested fix: reject model-facing existing-file `full_file`/legacy `code_content` modifies based on declared action/path whenever the target is an editable existing file, unless an explicit host-internal compatibility flag is set.
- Suggested tests: add a direct raw parse regression for an existing target with missing source context; add an APS integration test proving every modify path has host-visible source or fails before Contract.

### F-004: active solver map and cross-stage ledger are the right direction, with active-map parity gaps

- Severity: P1 high.
- Evidence: `ActiveSolverMap` is a generic strict schema; `context.read_active_solver_map`, `context.read_operator_registry`, and `context.read_algorithm_slice` are read-only tools; observation ledger stores read receipts and source digests. However, novelty snapshot extraction still only reads `context.read_active_solver_design`, and ledger argument normalization defaults active solver tools to `surface="solver_design"`.
- V3 judgment: mostly conforms for current CVRP, but not fully problem-generic or fully active-map-first.
- Suggested fix: make active solver map the canonical source of active fact parity where available, and make ledger/default argument handling surface-agnostic.
- Suggested tests: non-`solver_design` active map reuse, novelty/premise rejection using map-only active facts, and gate-prompt parity when `read_active_solver_map` is the only active context tool.

### F-005: gates, telemetry, and lifecycle are now less over-controlling

- Severity: OK/P1 residual risk.
- Evidence: formal telemetry guard separates repairable diagnostics from hard failures; effect telemetry with observed activation is not a hard formal failure; branch lifecycle preserves weak-positive/pair-win/telemetry-diagnostic branches; status reports proposal attempts separately from effective screened rounds.
- V3 judgment: conforms to the latest v3 repair intent. Residual risk is implementation size and live validation coverage, not an obvious policy bug.
- Suggested fix: keep the hard gate line for schema/contract/runtime crashes, but keep activation/effect/activity misses branch-local unless protected/objective telemetry fails.
- Suggested tests: continue focused regressions for mixed hard+repairable telemetry, weak positive with runtime cost, no-effect memory, and repeated diagnostics exhaustion.

### F-006: modularity debt remains active

- Severity: P1 high.
- Evidence: production files still over 1000 lines include `proposal/agentic_session_hypothesis.py`, `proposal/engine/prompt_common.py`, `proposal/agentic_session_tools.py`, `problems/cvrp/active_solver_map_provider.py`, `proposal/agentic_grounding.py`, and `proposal/agentic_session_patch_flow.py`. Large tests remain over 800-1100 lines.
- V3 judgment: violates the onboarding maintainability bar. The old monoliths have been reduced, but several new control modules are now too broad.
- Suggested fix: split by stable responsibilities with compatibility facades, not only helper extraction.
- Suggested tests: keep existing behavior tests green after each split; add import/facade tests for public APIs used by campaign and APS.

## Immediate Fix Order

1. Move active algorithm package path rules out of generic Contract/APS and into CVRP provider hooks.
2. Close typed-edit no-context full-file modify compatibility for model-facing existing modifies.
3. Make active solver map the parity source for novelty/premise gates and remove hard default `solver_design` in generic ledger matching.
4. Split the 1000+ line proposal/control modules and oversized tests.
5. Run focused regressions, then full unit regression, then a 3-4 round live validation. Only after that run 8+ unattended validation.

