# Low-Signal Same-Branch Lesson Usage Repair

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`

## Summary

The scheduler can now select one low-signal same-branch observation sample as
`refine_active`, but proposal context still treated branch-local no-effect
lessons as sibling/clean-fork material. That meant the agent could continue the
same mechanism without receiving an explicit `branch_lesson_usage` requirement
to contrast the previous no-effect evidence.

This repair makes current active no-effect branch-local lessons eligible for
`same_branch_refinement`. The requirement remains advisory-only, proposal-only,
and excluded from `DecisionFeatures`; it asks the hypothesis to explain how the
next same-mechanism attempt changes a relevant dimension instead of repeating
the previous no-effect mechanism.

## Boundary Check

- No `DecisionFeatures`, gate, protocol, lifecycle, budget, or scheduler
  decision behavior changed.
- The new signal is derived from proposal-visible branch summaries and remains
  `proposal_guidance_only`.
- Weak-positive same-branch refinement behavior remains intact.
- Sibling and clean-fork no-effect pressure still requires material difference
  rather than same-branch refinement.

## Changed Files

- `scion/scion/proposal/context/cross_branch_research_support.py`
- `scion/scion/tests/unit/test_cross_branch_research.py`
- `scion/scion/tests/unit/core/test_branch_lesson_usage.py`

## Verification

Local:

```bash
python -m py_compile \
  scion/scion/proposal/context/cross_branch_research_support.py \
  scion/scion/core/explore_step/branch_lesson_usage.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/test_cross_branch_research.py \
  scion/scion/tests/unit/core/test_branch_lesson_usage.py \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py \
  scion/scion/tests/unit/test_branch_prompt_projection.py \
  scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py \
  scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py
```

Result: `125 passed`.

## Acceptance

Accepted as a narrow v0.4 proposal-context repair. It closes the gap between
low-signal scheduler selection and hypothesis-context lesson usage, so a
retained no-effect branch selected for same-mechanism refinement carries a
machine-readable lesson requirement into the next proposal.
