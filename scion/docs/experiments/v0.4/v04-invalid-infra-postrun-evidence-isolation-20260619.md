# v0.4 Invalid Infra Postrun Evidence Isolation

Date: 2026-06-19

## Purpose

Postrun analysis must not treat copied resume-campaign artifacts or partial
post-start infrastructure failures as current-run research evidence. Preflight
failures were already isolated; this repair extends the same evidence boundary
to any root classified as `invalid_infra_only`.

## Change

- `postrun_artifact_inventory.py` now marks invalid-infra-only roots with
  `current_run_evidence=false` and
  `evidence_scope=invalid_infra_only_with_resume_snapshot`.
- Branch, event, hypothesis, LLM-trace, counter, and Phase 4 coverage summaries
  are zeroed for invalid-infra-only roots; copied artifacts remain available
  only under `resume_snapshot`.
- `postrun_analysis_brief.py` now classifies warehouse and CVRP problem-specific
  summaries as `invalid_infra_only_no_research_conclusion` when the run is
  infra-only.
- Warehouse/CVRP review axes are marked `not_actionable_invalid_infra_only`
  rather than prepared-only or current-run review-ready.

## Boundary Check

- This is report-only postrun evidence handling.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, budgets, or solver semantics.
- CVRP and warehouse interpretations remain problem-owned analysis summaries.

## Current Prepared Roots

The current launch-prepared roots remain the `399db52` roots. This repair does
not require regeneration because strict readiness reports the WSL checkout
differs only outside runtime guard paths.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-399db52-6r-gpt55-20260619T015826Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-399db52-1r-gpt55-20260619T015826Z-claw`

## Readiness Evidence

Both roots still report:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- detail: `checkout differs, but runtime guard paths are unchanged`
- `prepared_analysis_brief_current=ok`
- completion preflight `failed`
- HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`

The current blocker remains external `gpt-5.5` auth, not Scion static readiness.

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
# 75 passed
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
# 75 passed
```
