# v0.4 Research Shape Prompt Signal Repair

Date: 2026-06-18

## Purpose

Postrun reports could audit branch depth, shallow branch scattering, and
mechanism-family continuity, but the live hypothesis prompt only had an empty
`research_shape` slot. That left the agent able to be judged for poor research
shape after the run without reliably seeing the compact shape signal while
planning the next proposal.

## Change

- Added `scion.proposal.context.research_shape` to derive a compact
  proposal-only `proposal_research_shape_prompt_summary.v1` from the existing
  cross-branch research map.
- `ContextManager.build_hypothesis_context()` now emits
  `research_shape_diagnostics`.
- `hypothesis_prompts._compact_research_signals()` renders structured
  `research_shape` content before broader rules.
- `minimal-research-context` ablation hides the new field with other research
  context.

The signal is generic and report/planning-only: branch counts, active branch
count, current/max branch depth, depth distribution, mechanism-family counts,
outcome-pattern counts, repeated non-positive families, shape label, and short
proposal guidance. It remains excluded from `DecisionFeatures`, Protocol gates,
promotion input, and scheduler state.

## Verification

Local:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/test_sprint_e2_context_runtime.py

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/test_research_surfaces_generic_context.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_session_controls.py
```

Results: `27 passed` and `43 passed`.

WSL checkout:

- Repository: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- Commit: `2f620ee`

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/test_sprint_e2_context_runtime.py \
  scion/scion/tests/unit/test_research_surfaces_generic_context.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_session_controls.py
```

Result: `70 passed`.

`py_compile` passed locally and on WSL for the changed proposal modules and
tests.

## Prepared Roots

The previous `b9836a6` prepared roots became stale after this repair because the
runtime guard paths include `scion/scion` proposal/context code. New WSL
prepared-only roots were generated from synchronized commit `2f620ee`:

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-shapesignal-2f620ee-1r-gpt55-20260618T210606Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-shapesignal-2f620ee-6r-gpt55-20260618T210606Z-claw`

Strict launch readiness with `--require-launch-ready --format json`:

- `static_ready=true` for both roots.
- `git_runtime_consistent=ok`, detail `checkout matches manifest commit`.
- `prepared_contract_complete=ok`.
- `prepared_only_not_started=ok`.
- `zero_current_run_counters=ok`.
- `launch_ready=false` only because completion preflight still fails.
- Completion preflight: HTTP `401`, classification `not_authenticated`,
  auth pool `active=0`, `expired=1`, `refreshing=0`, login URL present.

Do not launch either root until the same readiness command returns
`launch_ready=true`.
