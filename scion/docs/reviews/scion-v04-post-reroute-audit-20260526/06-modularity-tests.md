# Modularity, Test Coverage, and Maintenance Risk

Audit question: which large-file or modularity debts truly affect architecture elegance and maintainability?

## Finding M-1: broad active control modules remain P1 debt

Severity: P1.

The following production files are over the onboarding warning threshold and sit directly on v3 control boundaries:

- `scion/scion/proposal/agentic_session_hypothesis.py`: 1806 lines. Owns hypothesis loop, grounding retries, novelty/C11 repair, identity drift, and telemetry guidance.
- `scion/scion/proposal/engine/prompt_common.py`: 1801 lines. Owns prompt projections, observation compaction, source projection, active solver map receipts, and manifest-facing sections.
- `scion/scion/proposal/agentic_session_tools.py`: 1243 lines. Owns tool routing, reuse checks, payload shaping, and observation validation.
- `scion/scion/runtime/telemetry_guard/summary.py`: 1220 lines. Owns activation/evaluation/effect diagnostics and severity mapping.
- `scion/scion/proposal/agentic_grounding.py`: 1033 lines. Owns required context tools, active solver grounding, budget compaction, and code-context evidence.
- `scion/scion/proposal/edit_protocol/normalization.py`: 1018 lines. Owns a critical safety protocol with many compatibility paths.
- `scion/scion/proposal/agentic_session_patch_flow.py`: 1007 lines. Owns patch generation, repair, premise rejection, identity checks, and code prompt visibility.

These are not mechanical line-count complaints. They are the files where the remaining P1 findings live. Split by invariant boundaries, not by arbitrary helper extraction.

Suggested split sequence:

1. Move provider-declared telemetry taxonomy and identity matching out of patch/hypothesis flow.
2. Split prompt projection into active facts, source visibility, observation compaction, and manifest-facing ledgers.
3. Split telemetry guard severity classification from summary rendering.
4. Split edit normalization into parse-shape compatibility, exact-replace application, and safety policy.

## Finding M-2: tests cover key repairs but not provider-generic variants

Severity: P2.

Good coverage exists for:

- Boundary sentinel against CVRP path terms: `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py`.
- Typed edit strictness: `scion/scion/tests/unit/test_code_edit_protocol.py`.
- Branch lifecycle reroute and round accounting: `scion/scion/tests/test_scheduler.py` and `scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py`.
- Code prompt visibility invariants: `scion/scion/tests/unit/test_agentic_code_stage_invariants.py` and `scion/scion/tests/unit/test_agentic_target_file_grounding.py`.

Missing or weak coverage:

- Non-CVRP provider with different mechanism/telemetry taxonomy.
- Active-map-only grounding path without legacy `read_active_solver_design`.
- Structural telemetry ids declared by provider versus hardcoded generic phases.
- Launch/readiness check that fails if docs, defaults, and tests disagree on proposal attempt budget.

This review did not run a full regression suite.

