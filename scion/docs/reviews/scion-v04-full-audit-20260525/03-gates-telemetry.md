# Gates, Novelty, Schema, Contract, Telemetry, Smoke, Screening, And Decision

Audit question: are controls safe without blocking top model research unnecessarily?

## Finding GT-1: Contract remains the hard boundary for static risk

- Severity: OK.
- Evidence: `scion/scion/contract/gate.py::ContractGate.validate_patch` routes through schema, syntax, import/API, complexity, semantic novelty, interface, and solver-design integration checks. Security-sensitive checks such as dynamic imports, subprocesses, and environment access live under `scion/scion/contract/checks/security.py`.
- V3 judgment: conforms. Contract is deterministic and runs before workspace materialization/protocol evidence.
- Suggested fix: keep hard failures for schema, syntax, sensitive APIs, illegal imports, frozen paths, and unintegrated helper drops.
- Suggested tests: continue C6/C8/C9/C10/C11 regression coverage, including markdown-wrapper syntax regressions and support-module integration checks.

## Finding GT-2: one Contract hard rule is boundary-coupled

- Severity: P1 high.
- Evidence: `scion/scion/contract/checks/security.py::_context_baseline_call_violations_in_baseline_algorithm` is a valid CVRP active package rule, but it is implemented in generic security checks and hardcodes `policies/baseline_algorithm.py`.
- V3 judgment: the safety intent is correct, but the ownership is wrong. Generic sensitive API checks should not know CVRP package entrypoints.
- Suggested fix: move this rule behind a provider hard-check hook. Generic security can still provide reusable AST helpers for "forbid call X in path Y".
- Suggested tests: CVRP provider test still rejects `context.baseline(...)` in `policies/baseline_algorithm.py`; generic dummy problem with a different entrypoint can declare its own equivalent rule.

## Finding GT-3: proposal smoke telemetry is diagnostic when appropriate

- Severity: OK.
- Evidence: `scion/scion/proposal/tools/previews/algorithm_smoke_feedback.py` treats activation/telemetry misses as `diagnostic` when runtime smoke has no hard failure. Invalid helper signatures, crashes, and hard static failures still block.
- V3 judgment: conforms to recent design notes. Tiny proposal smoke should not force top models to fabricate telemetry just to pass a shallow sample.
- Suggested fix: preserve this distinction: smoke diagnostics should guide repair but not erase real runtime or contract failures.
- Suggested tests: proposal-smoke missing activation passes as diagnostic; invalid telemetry helper signature fails; runtime crash still fails.

## Finding GT-4: formal telemetry guard has a better hard-vs-repairable split

- Severity: OK/P1 residual.
- Evidence: `scion/scion/core/telemetry_validation.py::formal_telemetry_guard_failed` only reports hard formal failures. `is_repairable_telemetry_validation_failure` recognizes branch-local activation/effect/activity/budget diagnostic codes. `_is_hard_formal_failure` avoids hard failure for effect-not-observed when activation was observed.
- V3 judgment: conforms. Formal Protocol remains authoritative, but not every telemetry miss means the research direction is dead.
- Suggested fix: keep protected/objective/safety telemetry hard. Keep branch-local activation/effect/activity issues repairable only when all failing details are repairable.
- Suggested tests: mixed hard+repairable telemetry fails closed; effect miss with observed activation does not trigger endless retry; protected effect miss remains hard.

## Finding GT-5: Decision stays on deterministic features

- Severity: OK.
- Evidence: `scion/scion/core/features.py::SafeFeatureExtractor.extract` reads aggregate stats, runtime counters, gate outcomes, failure codes, and branch state. It does not read proposal free text, tool observations, or raw model reasoning.
- V3 judgment: conforms to Decision Input Guard.
- Suggested fix: do not add hypothesis text, LLM confidence, or narrative evidence summaries to `DecisionFeatures`.
- Suggested tests: unit sentinel that scans `DecisionFeatures` for `str` fields not constrained to enums/ids, and a Decision test with poisoned proposal text proving no behavior change.

## Finding GT-6: screening feedback is now semantically richer than pass/fail

- Severity: OK/P1 live risk.
- Evidence: screening feedback and branch memory tests cover weak-positive, no-effect, quality regression, runtime regression, and repeated same-family guidance. Branch lifecycle uses pair wins and low-signal preservation instead of a single `SCREENING_FAIL_WIN_RATE` outcome.
- V3 judgment: conforms to v3 branch-as-research-direction governance.
- Suggested fix: keep feedback compact and branch-local; do not feed raw validation/holdout detail into APS.
- Suggested tests: weak-positive with small runtime cost stays active; no-effect repeated mechanism is blocked or redirected; runtime-improving but objective-regressing branch is not promoted.

