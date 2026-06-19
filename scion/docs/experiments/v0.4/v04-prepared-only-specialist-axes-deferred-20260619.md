# v0.4 Prepared-Only Specialist Axes Deferred

Date: 2026-06-19

## Purpose

Prepared-only roots should not label post-launch solver/protocol review axes as
currently required. Before launch, CVRP and warehouse briefs can prove
handoff/readiness state, but they cannot prove whether the agent performed
effective research, plateau analysis, or bounded two-opt implementation work.

## Change

- Specialist summaries now distinguish prepared handoff sources from current-run
  protocol, measurement, runtime, and continuity summaries.
- Prepared-only warehouse summaries state that current-run summaries are absent
  before launch and show `Deferred post-launch warehouse review axes`.
- Prepared-only CVRP summaries state that current-run summaries are absent
  before launch and show `Deferred post-launch CVRP bounded two-opt review
  axes`.
- Deferred axes carry
  `not_actionable_before_launch_current_run_evidence_required`.
- Current-run roots keep the original `Required ... review axes` wording.

## Boundary Check

- This is report-only delegated-review guidance.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or problem solver semantics.
- It does not add budgets, truncation, compression, or generic gate tightening.
- CVRP and warehouse semantics stay in problem-owned summary/report layers.

## Prepared Roots For This Repair

WSL checkout: `cff825a`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-cff825a-6r-gpt55-20260619T013400Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-cff825a-1r-gpt55-20260619T013400Z-claw`

Both roots are prepare-only and not started.

## Artifact Evidence

Warehouse prepared analysis brief now reports:

- Source: prepared warehouse research-focus handoff; current-run protocol,
  measurement, runtime, and continuity summaries are absent before launch.
- `current_run_evidence=false`
- `interpretation=prepared_only_launch_required`
- `Deferred post-launch warehouse review axes`
- `not_actionable_before_launch_current_run_evidence_required`

CVRP prepared analysis brief now reports:

- Source: prepared CVRP large-twoopt research-focus handoff; current-run
  protocol, measurement, runtime, and continuity summaries are absent before
  launch.
- `current_run_evidence=false`
- `interpretation=prepared_only_launch_required`
- `Deferred post-launch CVRP bounded two-opt review axes`
- `not_actionable_before_launch_current_run_evidence_required`

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

Accepted as the prepared-only specialist-axis deferral repair.

Later current root:

- The `cff825a` roots were superseded after the specialist-axis deferral became
  structured JSON evidence and launch readiness began checking prepared analysis
  brief currency directly.
- Current warehouse root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-4830d81-6r-gpt55-20260619T014742Z-claw`.
- Current CVRP root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-4830d81-1r-gpt55-20260619T014742Z-claw`.
- Current refresh report:
  `scion/docs/experiments/v0.4/v04-prepared-analysis-brief-readiness-guard-20260619.md`.
