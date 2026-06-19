# v0.4 Prepared Analysis Brief Readiness Guard

Date: 2026-06-19

## Purpose

Prepared roots must not pass launch readiness with stale prepared analysis
briefs. After the specialist-axis repair, the markdown showed deferred
warehouse/CVRP review axes, but the JSON summaries did not expose that deferral
as structured evidence. That made the deferral harder to audit and impossible
for launch readiness to enforce directly.

## Change

- CVRP and warehouse specialist summaries now expose structured
  `deferred_review_axes` and `review_axes_actionability`.
- Prepared-only summaries use
  `not_actionable_before_launch_current_run_evidence_required` until current-run
  evidence exists.
- `check_launch_readiness.py` now requires a current prepared analysis brief
  under `prepared_handoff/analysis_brief`.
- Launch readiness rejects missing prepared briefs, current-run required
  questions in prepared-only briefs, missing structured deferred axes, and
  mismatched prepared-only lifecycle/validity/boundary fields.

## Boundary Check

- This is report-only launch-readiness and delegated-review validation.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or problem solver semantics.
- It does not add budgets, truncation, compression, or generic gate tightening.
- CVRP and warehouse semantics remain in problem-owned prepared/postrun summary
  layers.

## Current Prepared Roots

WSL checkout: `4830d81`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-4830d81-6r-gpt55-20260619T014742Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-4830d81-1r-gpt55-20260619T014742Z-claw`

Both roots are prepare-only and not started.

## Artifact Evidence

Warehouse prepared analysis brief:

- `warehouse_followup_summary.interpretation=prepared_only_launch_required`
- `warehouse_followup_summary.review_axes_actionability=not_actionable_before_launch_current_run_evidence_required`
- `warehouse_followup_summary.deferred_review_axes` has 5 entries
- `warehouse_followup_summary.evidence_gaps=["launch_required_before_plateau_conclusion"]`

CVRP prepared analysis brief:

- `cvrp_large_twoopt_summary.interpretation=prepared_only_launch_required`
- `cvrp_large_twoopt_summary.review_axes_actionability=not_actionable_before_launch_current_run_evidence_required`
- `cvrp_large_twoopt_summary.deferred_review_axes` has 5 entries
- `cvrp_large_twoopt_summary.evidence_gaps=["launch_required_before_bounded_twoopt_conclusion"]`

## Readiness Evidence

Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `prepared_analysis_brief_current=ok`
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
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 72 passed
```

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
# 72 passed
```

## Acceptance

Accepted as the current prepared-root readiness guard and launch-prepared root
refresh. Once `gpt-5.5` auth is restored and strict launch readiness reports
`launch_ready=true`, these are the current warehouse and CVRP roots to launch.
