# v0.4 CVRP Measurement Opportunity Diagnostics Repair

Date: 2026-06-18

## Purpose

Close the Phase 2 context signal-density gap for CVRP proposal planning without
changing Decision, Protocol gates, lifecycle, scheduler, budgets, or promotion
semantics.

The June 11 audits found that CVRP prompts carried too much governance and
telemetry material while missing compact problem-owned guidance about measured
noise, residual opportunity, and already-rejected mechanism families. The
existing framework already had a proposal-only
`problem_measurement_diagnostics` hook; warehouse used it, but CVRP did not.

## Change

- Added `CvrpAdapter.render_problem_measurement_diagnostics()`.
- The CVRP adapter now provides proposal-only diagnostics for:
  - formal screening MDE (`9.9` raw `total_distance`) versus practical screen
    delta (`2.0`);
  - `runtime_model=budget_exhausting` and
    `pairing_validity=trajectory_divergent`;
  - aggregate screening headroom without raw case/BKS detail;
  - current default-avoid mechanism directions;
  - measurable opportunity classes and required effect evidence;
  - top-level `opportunity_diagnostics` reason codes for prompt planning.
- Updated `ContextManager` so adapter-supplied `opportunity_diagnostics` are
  projected into the existing top-level measurement diagnostics shape using the
  approved compact fields:
  `diagnostic_type`, `surface`, `mechanism_family`, `metric`, `summary`,
  `recommended_action`, `confidence`, and `reason_codes`.

## Boundary Check

- All new CVRP semantics live under `scion/problems/cvrp/adapter.py`.
- Generic `ContextManager` only projects adapter-owned diagnostics through the
  existing proposal diagnostics channel.
- The payload is marked `proposal_visibility_only` and
  `decision_features_excluded`.
- No `DecisionFeatures`, Protocol gate, lifecycle, scheduler, or promotion code
  was changed.
- Raw validation/frozen/holdout details and raw case/BKS records are not
  introduced into prompt diagnostics.

## Verification

Local:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/test_cvrp_measurement_diagnostics.py \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/unit/test_warehouse_target_preview.py
# 64 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/test_cvrp_solver_design_provider.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py \
  scion/scion/tests/test_models.py
# 72 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/scion/problems/cvrp/adapter.py \
  scion/scion/proposal/context_manager/manager.py \
  scion/scion/tests/unit/test_cvrp_measurement_diagnostics.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py
```

## Acceptance

Accepted as an offline v0.4 framework repair. It improves CVRP proposal signal
density before the next live campaign and preserves the v3 tainted-proposal /
deterministic-decision boundary.

The next WSL prepared roots must be regenerated after this code commit because
prepared-root runtime guards cover changed files under `scion/scion`.
