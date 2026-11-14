# Budget-Exhausting Finalizer Retain-Head Repair

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`

## Purpose

Close a second budget-exhausting runtime semantics leak in the screening
finalizer. Decision and lifecycle policy can now choose `retain_head` for
non-regressive low-signal CVRP screening under
`runtime_model=budget_exhausting`, but the finalizer still had an independent
workspace-preservation guard that rejected retained low-signal branches when
aggregate runtime ratio or `runtime_regression_rate` looked slow.

That meant a branch could receive a valid low-SNR continuation decision yet
still lose its workspace and patch before the next same-branch follow-up,
directly harming the v0.4 goal of continuous, evidence-aware research.

## Change

- `scion/scion/core/decision_finalizer.py` now reads the protocol result's
  declared runtime model from `candidate_surface_runtime_summary`.
- When the runtime model is `budget_exhausting`, aggregate runtime ratio and
  aggregate `runtime_regression_rate` no longer veto low-signal
  `retain_head` workspace preservation.
- Candidate runtime failures, objective regressions, negative deltas, and
  non-positive confidence intervals still fail closed.

## Boundary Check

- This is a finalizer consistency repair, not a gate or budget change.
- It does not add runtime metrics to `DecisionFeatures` and does not make raw
  calibration diagnostics Decision input.
- Comparative runtime evidence keeps the existing behavior: confident
  aggregate slowdown can still prevent low-signal workspace preservation.

## Verification

Local focused verification passed:

```bash
python -m py_compile \
  scion/scion/core/decision_finalizer.py \
  scion/scion/proposal/screening_feedback.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/core/test_decision_finalizer_park_lifecycle.py \
  scion/scion/tests/unit/core/test_branch_lifecycle_policy.py \
  scion/scion/tests/test_decision_screening.py \
  scion/scion/tests/test_protocol_stats_gates.py \
  scion/scion/tests/unit/test_screening_feedback_tiers_memory.py \
  scion/scion/tests/unit/test_agentic_feedback_screening.py \
  scion/scion/tests/test_sprint_e2_context_runtime.py
```

Result:

```text
150 passed
```

The new finalizer test confirms a budget-exhausting, all-tie screening result
with high aggregate runtime ratio/rate keeps the branch workspace, patch, and
`active_no_effect` branch status when lifecycle selected `retain_head`.

## Residual Risk

This is code/test verified but not yet campaign-validated because the current
`gpt-5.5` route still fails the real completion preflight with HTTP `401`.
