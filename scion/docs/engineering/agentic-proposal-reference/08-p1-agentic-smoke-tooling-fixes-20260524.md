# P1 Agentic Smoke And Tooling Fixes

Date: 2026-05-24

## Purpose

This note records the P1 fixes after the standard four-round Scion v3 APS trace review and the first external APS comparison sample. The goal is not to loosen the v3 boundary. It is to convert useful external-agent behavior into controlled Scion capabilities: adapter-declared facts, exposure-controlled tools, compact ledgers, diagnostics, and branch memory.

Scion core remains problem-generic. Problem content, mechanisms, microcases, telemetry fields, and source allowlists continue to come from the adapter/problem provider.

## Smoke Telemetry Diagnostics

Proposal smoke now emits stable telemetry diagnostic types in addition to existing pass/diagnostic behavior:

- `observed_activation`: the declared mechanism triggered during tainted proposal smoke.
- `activation_unobserved_conditional`: activation was not seen, but the short smoke case or natural trigger may be insufficient.
- `activation_unobserved_wiring_suspect`: static/provider evidence suggests the mechanism should be reachable, but the smoke run did not observe activation.
- `effect_missing_observed_activation`: activation happened but positive effect telemetry did not.
- `telemetry_field_missing_or_misdeclared`: expected telemetry fields do not match adapter-declared runtime fields or roles.

These diagnostics also carry lifecycle-oriented signals where available:

- `valid_active_weak_positive`: activation was observed, or activation was observed but effect was missing/weak.
- `active_no_case_level_gate`: short smoke or later screening did not prove case-level promotion, but the mechanism should not be treated as absent.
- `active_pair_wins_but_case_fail`: formal screening has pair-level wins while case-level gate fails.
- `inactive_or_wiring_suspect`: adapter/static evidence suggests the mechanism should have activated but smoke did not observe it.

Conditional non-activation is diagnostic, not a hard fail. Wiring-suspect and misdeclared-field cases are repairable code/schema feedback. Effect-missing with observed activation can proceed to formal screening and should be interpreted as weak signal unless screening itself fails decisively.

The diagnostics are proposal-stage evidence only. They do not count as screened rounds unless the candidate enters formal screening.

## Screening Feedback And Weak Positives

Screening feedback now keeps pair-level and case-level summaries together. This prevents the agent from reading `5/16` pair wins as a case-level gate pass, while preserving weak positive signal when a non-promoting candidate still activates and wins some pairs.

The external APS sample motivates this distinction: a same-route Or-opt candidate activated and produced telemetry, passed preview/smoke/verification/canary/screening execution, but did not promote because case-level win rate was `0.25` and median delta was `0`. Pair-level evidence was `5` wins, `3` losses, `8` ties. That should become memory like “active but insufficient”, not an ordinary failed mechanism.

Branch lifecycle features now carry pair wins/losses/ties. A low case-win candidate with pair-level wins can keep the branch alive with `SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL` instead of being collapsed into neutral zero-win history.

## Code-Stage Target-Aware Tooling

The code-stage tool planner now receives explicit mandatory-visible source context:

- approved `target_file`
- integration files that will be rendered in final code prompt source sections
- already-visible/read-receipt files
- target-aware priority ordering
- duplicate-read rule

This does not forbid reading other allowlisted algorithm files. It makes the default ordering target-aware: target file, declared additional changes, integration files, branch-current files, recent failure files, then other allowlisted files when the mechanism needs them.

Repeated file reads return compact receipts that explicitly tell the planner not to reread the same source and to use branch-state or symbol tools when it needs different information.

## Hypothesis Target Grounding

Existing target grounding retry remains in place. Additionally, when the research boundary already provides an unambiguous forced solver-design target, the required preface reads that full target source before the first final hypothesis call. This is still research grounding, not early coding. It does not expose validation, frozen, or raw metrics.

If the target cannot be inferred unambiguously, Scion keeps the existing retry-based grounding path.

## Near-Field Memory

The hypothesis prompt now supports a near-field mechanism memory block for structured feedback:

- contradicted premise
- fact digest/provenance
- exact target/mechanism
- telemetry repairable diagnostic
- activation/effect status
- pair/case split
- why not promoted
- allowed follow-up variants

Only fact-contradicted premises become blacklist-style “do not claim missing” constraints. Weak-positive and telemetry-repairable memories say not to repeat an unchanged mechanism, while allowing variants such as trigger, schedule, threshold, or composition changes.

## Expected Telemetry Schema Guidance

Hypothesis prompts receive adapter-declared expected telemetry templates for the active research boundary. The examples are generated from surface/runtime role declarations and mechanism probes. They do not relax C11; they make valid patterns visible earlier so the model needs fewer schema retries.

`proposal.schema_preview` remains the lightweight preview/validation helper for exact C11 repair feedback.

## External Candidate Harness

The external APS sample used a broader workflow than internal Scion APS: full active source tree, provider code, tests, raw metrics, and a temporary harness. That extra access helped it understand VNS registry and target helper bodies, but Scion APS should not copy the raw-access model.

The controlled equivalent is better active-fact/source parity: proposal tools should make exact registry/helper bodies cheap to read when the adapter allows them, and code-stage mandatory-visible receipts should make target/integration files obvious. This preserves v3 boundaries while capturing the useful part of the external agent's workflow.

P2 design: add an official external-candidate evaluation harness/CLI that accepts:

- hypothesis payload
- patch or workspace
- base workspace
- protocol config
- output directory

It should reuse the same sequence as Scion candidates: schema/contract preview, proposal smoke, verification, canary, formal screening protocol, and decision feature extraction. It should also emit timeout preflight warnings when verification and runner timeout settings differ, including the V5/V9 hidden mismatch seen by the external sample.

This harness is for evaluation parity and reproducibility, not for expanding internal proposal-agent visibility.

## Boundary Summary

Core generic:

- diagnostic type vocabulary
- prompt/ledger placement
- target-aware planner policy
- pair/case split exposure
- lifecycle numeric features
- duplicate-read receipts

Adapter/provider owned:

- active algorithm facts
- source allowlists and integration-file manifests
- telemetry field declarations and roles
- mechanism probes
- optional microcase/probe hooks
- problem-specific smoke repair guidance

Validation/frozen data and raw metrics remain outside proposal-agent context.

## Acceptance Status

Implemented and covered by focused unit tests:

- Proposal-smoke telemetry diagnostics distinguish observed activation, conditional non-activation, wiring suspicion, effect-missing-after-activation, and field/schema mismatch.
- Diagnostic outcomes are repair/lifecycle signals; conditional non-activation and effect-missing-after-activation are not reclassified as ordinary hard failures.
- Code-stage tool planning is target-aware through mandatory-visible file receipts and priority hints, while still allowing reads of other adapter-allowlisted files.
- Forced solver-design target grounding reads unambiguous full target source before the first final hypothesis call; ambiguous targets still use the existing retry path.
- Near-field memory is generated from structured facts/rejections only. It records contradicted premises, digests/provenance, telemetry repair hints, pair/case split, and allowed variants without exposing raw trace, validation, or frozen data.
- Expected telemetry examples are adapter-declared templates rendered in a bounded prompt section; C11 strictness is unchanged.
- Branch lifecycle features include pair wins/losses/ties so active-but-non-promoting candidates can remain distinguishable from ordinary no-signal failures.

Validated with targeted smoke/telemetry/hypothesis/tool-policy tests, related branch-lifecycle/evaluation tests, `compileall`, and `git diff --check`.

## Remaining Risks And Next Round

Remaining P1 risk is behavioral, not structural: the diagnostics are generic heuristics and should be measured in short follow-up experiments to confirm fewer duplicate reads, fewer C11 retries, and better repair choices after activation/effect diagnostics.

Deferred to the next Aristotle-based or P2 design pass:

- Official external-candidate evaluation harness/CLI.
- Verification/runner timeout harmonization beyond documentation/preflight design.
- Richer adapter-owned microcase/probe hooks for effect-positive smoke diagnosis.
- Broader active-source parity work, limited to adapter-approved tools and facts rather than raw source expansion.
