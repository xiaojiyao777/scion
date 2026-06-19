# v0.4 Postrun Incomplete-Handoff Review Question

Date: 2026-06-19

## Purpose

The previous postrun guard made CVRP and warehouse summaries refuse
review-ready interpretations when problem-specific handoff is incomplete. This
follow-up makes the delegated review prompt ask about the same condition
directly, so reviewers do not have to infer incomplete-handoff risk only from
the summary fields.

## Change

- The warehouse required review question now asks reviewers to distinguish
  quality-blocked evidence, protocol-evaluated evidence, incomplete handoff, and
  plateau-review-ready evidence.
- The CVRP large-twoopt required review question now asks reviewers to
  distinguish prepared-only roots, missing review inputs, missing mechanism
  signal, incomplete handoff, and bounded-twoopt review-ready evidence.
- Regression tests assert that prepared-only CVRP and warehouse postrun analysis
  briefs include those incomplete-handoff review cues.

## Boundary Check

- This is report-only delegated-review guidance.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or problem solver semantics.
- It does not add budgets, truncation, compression, or generic gate tightening.

## Current Prepared Roots

WSL checkout: `016bb39`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-016bb39-6r-gpt55-20260619T010221Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-016bb39-1r-gpt55-20260619T010221Z-claw`

Both roots are prepare-only and not started.

## Readiness Evidence

Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `problem_specific_prepared_handoff=ok`
- `prompt_context_readiness_complete=ok`
- completion preflight `failed`
- HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`
- auth pool `active=0`, `total=1`; the non-active state may appear as expired
  or refreshing across repeated preflights

The current blocker remains external `gpt-5.5` auth, not prepared-root static
readiness.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_launch_readiness.py
# 36 passed
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_launch_readiness.py
# 36 passed
```

## Acceptance

Accepted as the current postrun auditability and prepared-root refresh. Once
`gpt-5.5` auth is restored and strict launch readiness reports
`launch_ready=true`, these are the current warehouse and CVRP roots to launch.
