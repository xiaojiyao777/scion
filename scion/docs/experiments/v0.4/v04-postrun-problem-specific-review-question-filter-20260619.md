# v0.4 Postrun Problem-Specific Review Question Filter

Date: 2026-06-19

## Purpose

Prepared analysis briefs should ask delegated reviewers the specialist question
for the problem they are reviewing. The previous incomplete-handoff repair made
the right questions available, but every brief carried both the warehouse
follow-up question and the CVRP large-twoopt question. That extra cross-problem
question was report-only, but it added avoidable review noise.

## Change

- Split postrun required questions into common questions plus
  problem-specific warehouse/CVRP questions.
- Append the warehouse follow-up question only when
  `warehouse_followup_summary.available=true`.
- Append the CVRP large-twoopt question only when
  `cvrp_large_twoopt_summary.available=true`.
- Added regression coverage proving prepared warehouse briefs omit the CVRP
  question and prepared CVRP briefs omit the warehouse question.

## Boundary Check

- This is report-only delegated-review guidance.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or problem solver semantics.
- It does not add budgets, truncation, compression, or generic gate tightening.

## Current Prepared Roots

WSL checkout: `44f78e9`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-44f78e9-6r-gpt55-20260619T011450Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-44f78e9-1r-gpt55-20260619T011450Z-claw`

Both roots are prepare-only and not started.

## Artifact Evidence

The prepared analysis briefs report:

- Warehouse: `warehouse_question=true`, `cvrp_question=false`,
  `warehouse_followup_summary.interpretation=prepared_only_launch_required`.
- CVRP: `warehouse_question=false`, `cvrp_question=true`,
  `cvrp_large_twoopt_summary.interpretation=prepared_only_launch_required`.

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
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 70 passed
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
# 70 passed
```

## Acceptance

Accepted as the current postrun auditability and prepared-root refresh. Once
`gpt-5.5` auth is restored and strict launch readiness reports
`launch_ready=true`, these are the current warehouse and CVRP roots to launch.
