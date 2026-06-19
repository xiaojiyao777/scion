# v0.4 Prepared-Only Review Question Filter

Date: 2026-06-19

## Purpose

Prepared launch roots should not ask delegated reviewers to answer current-run
research-quality questions before any campaign has started. The previous
problem-specific question filter removed cross-problem review noise, but
prepare-only briefs still included common postrun questions about completed
formal candidates, effective research, LLM tool-call usefulness, and
branch-level research behavior. This repair separates prepared-only review from
postrun review.

## Change

- Prepared-only analysis briefs now use launch/readiness/handoff required
  answers.
- Prepared-only required answers ask reviewers to prove zero current-run
  counters, no postrun acceptance evidence, prepared-run contract identity,
  launch markers, prompt bridge readiness, problem-specific report-only handoff,
  and actionable completion-preflight status.
- Prepared-only required answers explicitly say the next step is readiness
  recheck or launch, not a research-quality, plateau, or bounded-twoopt
  conclusion.
- Current-run postrun briefs keep the original research-quality required
  answers.

## Boundary Check

- This is report-only delegated-review guidance.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or problem solver semantics.
- It does not add budgets, truncation, compression, or generic gate tightening.

## Current Prepared Roots

WSL checkout: `9a343e9`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-9a343e9-6r-gpt55-20260619T012114Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-9a343e9-1r-gpt55-20260619T012114Z-claw`

Both roots are prepare-only and not started.

## Artifact Evidence

The prepared analysis briefs report:

- Warehouse: `question_count=6`, `prepared_only_question=true`,
  `research_quality_question=false`, `warehouse_question=true`,
  `cvrp_question=false`.
- CVRP: `question_count=6`, `prepared_only_question=true`,
  `research_quality_question=false`, `warehouse_question=false`,
  `cvrp_question=true`.

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

Accepted as the current prepared-root review and launch-readiness refresh. Once
`gpt-5.5` auth is restored and strict launch readiness reports
`launch_ready=true`, these are the current warehouse and CVRP roots to launch.
