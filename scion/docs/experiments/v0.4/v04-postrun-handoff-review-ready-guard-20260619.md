# v0.4 Postrun Handoff Review-Ready Guard

Date: 2026-06-19

## Purpose

Warehouse follow-up and CVRP bounded large-twoopt postrun summaries must not
call a protocol-evaluated run review-ready if the problem-specific handoff is
incomplete. Before this repair, the summaries exposed the missing handoff as an
evidence gap, but the high-level interpretation could still report
`bounded_twoopt_review_ready` or `protocol_evaluated_plateau_review_ready` when
protocol evidence and review inputs were otherwise present.

## Change

- CVRP large-twoopt summary now returns
  `protocol_evaluated_handoff_incomplete` before
  `bounded_twoopt_review_ready` when handoff requirements are incomplete.
- Warehouse follow-up summary now returns
  `protocol_evaluated_handoff_incomplete` before
  `protocol_evaluated_plateau_review_ready` when handoff requirements are
  incomplete.
- Added regression tests for CVRP and warehouse protocol-evaluated runs with
  complete review inputs but intentionally incomplete problem-specific handoff.

## Boundary Check

- This is report-only delegated-review evidence.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or problem solver semantics.

## Current Prepared Roots

WSL checkout: `8c68347`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-8c68347-6r-gpt55-20260619T005550Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-8c68347-1r-gpt55-20260619T005550Z-claw`

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
- auth pool `active=0`, `expired=1`, `total=1`

The current blocker remains external `gpt-5.5` auth, not prepared-root static
readiness.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 69 passed
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 69 passed
```

## Acceptance

Accepted as a postrun auditability repair and current prepared-root refresh.
The prepared roots from WSL checkout `8c68347` were later superseded by
`scion/docs/experiments/v0.4/v04-postrun-incomplete-handoff-review-question-20260619.md`,
after the required delegated-review questions changed the same runtime guard
path and the roots were regenerated from WSL checkout `016bb39`.
Once `gpt-5.5` auth is restored, launch the warehouse v2 follow-up first, then
the CVRP bounded large-twoopt follow-up.
