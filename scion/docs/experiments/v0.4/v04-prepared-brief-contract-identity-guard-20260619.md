# v0.4 Prepared Brief Contract Identity Guard

Date: 2026-06-19

## Purpose

Prepared analysis briefs must not pass launch readiness when their embedded
`prepared_run_contract` is stale, incomplete, or from another prepared root.
The previous readiness guard verified prepared-only semantics, but it did not
prove that the analysis brief's contract identity matched the prepared-run
manifest being launched.

## Change

- `check_launch_readiness.py` now requires prepared analysis briefs to include a
  complete `prepared_run_contract`.
- The brief contract identity must match `prepared_run_manifest.v1.json` on
  manifest path, problem family, model, control-pair key,
  `resume_from_campaign`, and git commit.
- `postrun_artifact_inventory.py` now exposes `prepared_run_contract.git.commit`
  as the prepared manifest commit so regenerated briefs can pass that identity
  check without changing runtime state.
- Stale `4830d81` prepared roots correctly failed the new static check because
  their generated analysis briefs had `prepared_run_contract.git.commit=null`.

## Boundary Check

- This is report-only launch-readiness and delegated-review validation.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or solver semantics.
- It does not add budgets, truncation, compression, or generic gate tightening.
- CVRP and warehouse semantics remain in problem-owned prepared/postrun summary
  layers.

## Current Prepared Roots

WSL checkout: `399db52`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-399db52-6r-gpt55-20260619T015826Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-399db52-1r-gpt55-20260619T015826Z-claw`

Both roots are prepare-only and not started.

## Readiness Evidence

Both regenerated roots report:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `prepared_analysis_brief_current=ok`
- `problem_specific_prepared_handoff=ok`
- `prompt_context_readiness_complete=ok`
- completion preflight `failed`
- HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`
- auth pool `active=0`, `total=1`; the non-active account may appear as expired
  or refreshing across repeated preflights

The current blocker remains external `gpt-5.5` auth, not prepared-root static
readiness.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 73 passed
```

## Supersession

The `399db52` roots were later superseded after review-input boundary readiness
changed `scion/tools/check_postrun_acceptance.py`, a guarded runtime path.

Current refresh report:
`scion/docs/experiments/v0.4/v04-prepared-root-refresh-after-review-input-boundary-20260619.md`.

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 73 passed
```
