# Scion v0.4 Post-Reroute Audit Summary

Date: 2026-05-26

Scope: post-reroute framework audit against the v3 architecture baseline, current-state notes, the 2026-05-25 full audit, and current `v0.4-dev` source. This review did not modify production code.

## Verdict

The post-reroute code is materially closer to the v3 blueprint than the 2026-05-25 audit target. The most important older blockers are largely repaired: CVRP active-package paths moved behind provider hooks, no-source full-file edit escapes are closed in the model-facing parse path, smoke/telemetry activation misses are diagnostics instead of hard failures, and branch-lifecycle policy blocks reroute to clean branches/forks without consuming effective rounds.

I did not find a new P0 deterministic safety breach. I do not recommend treating the default configuration as ready for an 8-effective-round validation yet. Two launch-blocking P1 issues should be fixed or explicitly mitigated first: generic proposal/runtime code still contains algorithm-phase vocabulary that belongs in providers, and the proposal-attempt default contradicts current docs and can stop before the requested effective rounds. A third P1, active control-path module size, remains an architecture-maintenance blocker but is less urgent than the first two for a short controlled run.

## P0

None found in this pass.

Operational note: this is not a green light for unattended 8+ round validation. It means the remaining blockers are P1 architecture/control issues rather than an obvious gate bypass or unsafe edit path.

## P1

### P1-1: generic layers still carry research-object taxonomy

The old CVRP path hardcoding is mostly gone, but generic proposal/runtime code still names concrete algorithm phases and families such as `local_search`, `destroy_repair`, `construction`, and `acceptance`.

Evidence:

- `scion/scion/proposal/mechanism_novelty.py:310-314` treats `solver_design`, `local_search`, and `destroy_repair` as special broad families.
- `scion/scion/proposal/agentic_session_patch_flow.py:21-30` hardcodes "generic" telemetry phases, then `scion/scion/proposal/agentic_session_patch_flow.py:838-840` subtracts them from code-stage telemetry identity mismatch checks.
- `scion/scion/proposal/agentic_session_hypothesis.py:1424-1432` drops hardcoded generic activation refs, with the hardcoded set at `scion/scion/proposal/agentic_session_hypothesis.py:1452-1464`.
- `scion/scion/proposal/context_manager/guidance.py:416-420` suggests concrete module names such as `construction.py`, `destroy_repair.py`, `local_search.py`, and `acceptance.py` from generic context guidance.
- `scion/scion/runtime/audit.py:111-123` and `scion/scion/runtime/audit.py:178-198` hard-classify construction/portfolio/policy/operator runtime counters.

V3 judgment: these names should be declared by a problem/surface telemetry taxonomy or provider. In current CVRP runs they mostly help, but they keep the generic core from being cleanly problem-generic and can weaken identity checks by allowing undeclared phase names.

### P1-2: proposal attempt budget does not match current-state documentation

`scion/docs/status/current-state.md:75-79` says default proposal attempts include repair headroom, but current code and tests lock the opposite behavior.

Evidence:

- `scion/scion/core/campaign_loop.py:333-355` defaults `proposal_attempt_limit` to `requested_rounds`.
- `scion/scion/core/campaign_loop.py:141-148` stops the campaign when consumed proposal attempts reach that limit.
- `scion/scion/core/campaign_loop.py:223-230` consumes proposal attempts for ordinary proposal blocks.
- `scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py:11-44` asserts the default proposal attempt limit equals requested rounds.

V3 judgment: attempt and effective-round accounting is explicit, but the default is underpowered for an 8-effective-round experiment if any ordinary proposal blocks occur. Either the docs/status should be corrected and launch instructions must set an explicit higher `SCION_PROPOSAL_ATTEMPT_LIMIT`, or the default should return to the documented repair-headroom policy.

### P1-3: active control-path modules remain too broad

The large-file issue is not cosmetic. The biggest files are active policy/control modules where prompt rendering, grounding, telemetry, edit protocol, and proposal lifecycle rules are coupled.

Evidence from line counts:

- `scion/scion/proposal/agentic_session_hypothesis.py`: 1806 lines.
- `scion/scion/proposal/engine/prompt_common.py`: 1801 lines.
- `scion/scion/proposal/agentic_session_tools.py`: 1243 lines.
- `scion/scion/runtime/telemetry_guard/summary.py`: 1220 lines.
- `scion/scion/proposal/agentic_grounding.py`: 1033 lines.
- `scion/scion/proposal/edit_protocol/normalization.py`: 1018 lines.
- `scion/scion/proposal/agentic_session_patch_flow.py`: 1007 lines.

V3 judgment: these modules are where v3 invariants must stay legible. The remaining P1 boundary and budget issues are harder to spot because these responsibilities are still concentrated.

## P2

- Schema preview can still diverge from final typed-edit strictness: `scion/scion/proposal/tools/previews/schema.py:439-442` normalizes typed edits for preview without setting the final parser's `reject_legacy_code_content_full_file_modify` flag; the final path in `scion/scion/proposal/engine/parsing.py:109-115` is safe, so this is a repair-loop efficiency issue, not a production edit safety issue.
- Legacy generic problem shapes remain allowlisted: `_LEGACY_PROBLEM_SCALE_NAMES` in `scion/scion/contract/gate.py:61-74` and `SolverOutput.vehicles` in `scion/scion/core/models.py:455-462`.
- APS grounding still requires the legacy `context.read_active_solver_design` path for `solver_design` alongside the active solver map (`scion/scion/proposal/agentic_grounding.py:27-31`, `scion/scion/proposal/agentic_grounding.py:335-360`). This is acceptable for current CVRP, but not fully active-map-first.
- Branch reroute ineligibility is intentionally sticky after a lifecycle policy block (`scion/scion/core/branch_hygiene.py:116-146`). Scheduler behavior is tested, but the "temporary" wording should be made precise.

## 8-Round Recommendation

Fix P1-1 and P1-2 before starting or finishing an 8-effective-round run. If the experiment must proceed immediately, launch with an explicit proposal attempt limit high enough for repair/proposal blocks and document that the run is CVRP-solver-design-specific, not proof that generic Scion v0.4 is v3-clean.
