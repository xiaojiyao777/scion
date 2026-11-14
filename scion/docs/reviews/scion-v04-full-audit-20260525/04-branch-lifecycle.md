# Branch Lifecycle, Lineage, Suspect State, And Attempt Accounting

Audit question: are lineage, suspect/diagnostic/repair focus, proposal attempts versus screened rounds, and soft/hard abandon behavior reasonable?

## Finding BL-1: branch-local repair for weak signals is implemented

- Severity: OK.
- Evidence: `scion/scion/core/branch_lifecycle_policy.py::BranchLifecyclePolicy.decide` keeps exploring when there are case wins below threshold or pair-level wins even if screening fails at the case gate. It soft-abandons only after zero-win streak exhaustion or clear negative/runtime conditions.
- V3 judgment: conforms. A branch is a research direction, not a single patch. Weak but non-regressive evidence should shape a same-branch follow-up.
- Suggested fix: keep pair-level wins visible in branch memory and proposal context.
- Suggested tests: weak-positive 1W/0L and active pair-win/case-fail cases continue; zero-win repeated no-effect exhausts after the configured streak.

## Finding BL-2: telemetry diagnostic lifecycle preserves same-branch repair

- Severity: OK.
- Evidence: `BranchLifecyclePolicy._decide_telemetry_diagnostic` returns retry for screening/validation telemetry diagnostics until the diagnostic streak limit, and only hard-abandons immediately on candidate runtime failures. `scion/scion/core/decision_finalizer.py::_continue_explore` marks repairable telemetry branches as `telemetry_wiring_suspect` with repair focus rather than discarding them.
- V3 judgment: conforms to the recent v0.4 repair intent. Activation/effect/activity telemetry diagnostics are branch-local repair signals, not solver-quality losses.
- Suggested fix: keep diagnostic streaks per branch and reset them on material code or telemetry repair.
- Suggested tests: repeated identical telemetry diagnostic exhausts; single diagnostic with poor win-rate still gets repair opportunity; candidate crash plus telemetry issue abandons.

## Finding BL-3: proposal attempts and effective screened rounds are visible separately

- Severity: OK/P1 policy risk.
- Evidence: `scion/scion/core/campaign_loop.py` tracks `proposal_attempts`, `effective_rounds_completed`, `telemetry_repairable_attempts`, `validation_repair_required_attempts`, and `quality_blocks`. `screened_experiment_effective` excludes repairable telemetry failures from effective screened rounds.
- V3 judgment: conforms. Proposal-quality blocks and repairable diagnostics should spend LLM budget but should not be counted as successful screened rounds.
- Suggested fix: keep a user-configurable proposal attempt cap for long runs. The current default in code returns `requested_rounds` unless configured; current-state documentation describes a later headroom policy. Resolve this documentation/code mismatch before unattended validation.
- Suggested tests: short run with multiple quality blocks reports zero effective rounds but nonzero proposal attempts; configured attempt limit larger than rounds allows repair headroom; default behavior is documented and tested.

## Finding BL-4: soft/hard abandon reasons are mostly sensible

- Severity: OK.
- Evidence: `BranchLifecyclePolicy._soft_abandon_reasons` abandons loss-without-win, candidate runtime failures, negative median delta, runtime slowdown, and high runtime regression. Telemetry diagnostic abandon currently only treats candidate runtime failure as severe, with streak exhaustion handling repeated diagnostics.
- V3 judgment: conforms. Clear regressions and crashes are hard enough to stop a direction; weak/diagnostic outcomes stay repairable.
- Suggested fix: keep objective-policy-specific tradeoffs problem/provider-owned. Do not let generic lifecycle decide that speed improvement compensates objective regression unless a problem policy explicitly says so.
- Suggested tests: runtime-improving but negative objective branch soft-abandons; problem policy override, if added, is provider-declared and tested.

## Finding BL-5: lineage exists, but long-run lineage needs a live validation pass

- Severity: P1 medium.
- Evidence: branch state records `branch_code_status`, telemetry outcome, direction text, zero-win streaks, and attempt kind. Status summaries expose current and last result fields. Current state says live validation is still pending after several repairs.
- V3 judgment: implementation shape is good, but confidence for 8+ unattended behavior requires live evidence across multiple interrupted/repair/screened cycles.
- Suggested fix: run a 3-4 round live validation after P0 fixes, inspect StepRecord, branch store, session artifacts, status, and prompt manifests for the same branch lineage.
- Suggested tests: integration fixture that simulates proposal block, telemetry repairable result, weak-positive screening, and eventual soft abandon/promote path with consistent branch id and attempt accounting.

